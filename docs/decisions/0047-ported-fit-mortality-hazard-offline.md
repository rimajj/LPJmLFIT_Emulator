# ADR 0047 — the LPJmL-FIT mortality hazard is ported OFFLINE, with ONE generated parameter table

* **Status:** Accepted
* **Date:** 2026-08-04
* **Line:** S (Component-S science) · ADR block 0030–0049
* **Decides:** Phase 3A **Stage 1** — how the trait-dependent mortality operator ADR 0046 confirmed as the
  lever enters the codebase: as a self-contained, fully-tested module with **no call site**, and with its
  per-PFT parameters read from the C at build time into ONE committed artifact that every consumer gates
  against. Wiring it into `slow.jl` is Stage 2 and is deliberately not decided here.
* **Related:** ADR 0046 (the mechanism verdict and the validation target), ADR 0031 (what two independent
  copies of a physical constant cost), ADR 0048 (the pre-flight measurements that clear Stage 2), ADR 0023
  (train/inference consistency), ADR 0014 (empty runtime `[deps]`)
* **Ships:** `src/trait_mortality.jl` · `scripts/build_mort_params_reference.py` →
  `test/testitems/references/S_pft_mortality_params.csv` · `test/testitems/slow_trait_mortality_tests.jl` ·
  `python/tests/test_mort_params_reference.py` · a gate in `scripts/build_slow_flux_table.py`

## Context

ADR 0046 decided **BUILD IT**: FIT's per-cell wood-density warming shift is 51.3 % within-PFT and
+112 % within-age-class selection, the emulator has exactly zero channel for it, and the fix is the
per-individual hazard. It also left a sharp warning: `mort_max` alone says "denser wood survives better",
but denser wood grows more slowly, lowering `greff` and *raising* `mort_npp` — FIT's one-year selection
differential is **negative for ids 0 and 3**. So the port has to be the whole hazard, and it has to be
checkable before anything depends on it.

Two independent risks had to be handled at once:

1. **Parameter provenance.** The hazard needs seven per-PFT parameter rows. Those values already exist in
   `scripts/build_slow_flux_table.py::PFT_PARAMS`, hand-transcribed. ADR 0031 is the measured record of
   what a second hand-maintained copy costs: a stale `TREE_TYPES = [1,2,3,4,5]` dropped 32.5 % of survivor
   tree stems and made 16.7 % of tree-bearing cells invisible to Component S **for months**, invalidating
   every global S number published before 2026-07-28. Adding a Julia copy would make three.
2. **Blast radius.** Guardrail 4 requires new physics to leave every committed baseline and the AD trainer
   byte-identical until deliberately enabled.

## Decision

### 1. The hazard is ported in full, into a module with no call site

`src/trait_mortality.jl` defines `module TraitMortality` — pure Base, type-generic, allocation-free,
nothing else in `src/` references it. It implements `mortality_tree_ind.c:89-133` exactly:

```
mort_max   = 10^(wdmort_1 + wdmort_2/(wooddens/1e6))                                    # :92
mort_npp   = min(1, mort_max/(1 + KMORT_2·exp(k_mort·bm_delta/leafarea))·(1+counter))    # :95-101
             ... = 1 when leafarea ≤ 1e-6
mort_age   = min(1, KMORTBG_LNF·(KMORTBG_Q+1)/L·(age/L)^KMORTBG_Q)                      # :40-44, :109-111
mort_water = min(1, mort_water_factor·water_stress/365·(1+counter))                      # :113-115
mort_temp  = min(1, mort_temp_factor·temp_stress/365)                                    # :117-119
mort       = min(1, mort_npp + mort_age + mort_water + mort_temp)                        # :122-124  ADDITIVE
             then mort = 1 if counter ≥ 5 (:128) or leaf_c < leaf_carbon_sapl(sla) (:132)
```

Four details that a paraphrase loses, all carried:

* the components are capped **individually and then again as a sum** — not once;
* `(1 + bm_inc_counter)` multiplies `mort_npp` **and** `mort_water`, but **not** `mort_temp`;
* `age` is the **PRE-increment** age (`annual_tree.c:46` increments after the call), so the emitted `Age`
  is one greater than the age that produced that row's `mort_age`;
* `leaf_carbon_sapl` depends on `sla`, so the ghost-tree kill is a **second, weaker trait channel**.

Three C paths are deliberately absent and say so in the docstrings: the dead `mort_max` read at `:87`
(overwritten at `:92`), the logging branch at `:141` (`nlogging` is 0 under `landusetype = NATURAL`), and
the two kills that sit *outside* this function — `isneg_tree` (`:148`) and the cell-level bioclimatic
`survive()` (`annual_tree.c:42`), which removes a whole PFT and is not trait-dependent.

`mortality_hazard` returns a `MortHazard` carrying the four components **separately**. That is not
cosmetic: ADR 0046 §3's whole point is that the trait dependence enters through `npp` in a direction that
can oppose the `mort_max` factor, so a validation harness has to read the parts.

### 2. The parameters are GENERATED from the C, into one artifact, and every consumer gates on it

`scripts/build_mort_params_reference.py` expands `$LPJROOT/par/pft_lpjmlfit.js` with **the same `cpp -P`
LPJmL itself pipes it through** (`src/lpj/openconfig.c:28` defines `cpp_cmd "cpp"`, invoked at `:467` via
`popen`), strips the trailing commas LPJmL's lenient parser tolerates, and `json.loads` the `"pftpar"`
array. Every value is then a direct read of the element at the 0-based index that IS the `ind` `Type`
column. No macro is re-typed by hand, so a future edit to `WD_mort1_temp` propagates on regeneration
instead of silently disagreeing.

Output: `test/testitems/references/S_pft_mortality_params.csv`, 7 rows × 31 columns. The six per-run
GLOBALS (`k_mort`, `kmort_2`, `kmortbg_lnf`, `kmortbg_q`, `bm_inc_counter_max`, `ndayyear`) are **repeated
on every row** so that a gate on either side is a plain per-row comparison and a global cannot drift
unnoticed.

Three consumers, one source:

| consumer | gate | runs when |
|---|---|---|
| `src/trait_mortality.jl::PFT_MORT_PARAMS` | `test/testitems/slow_trait_mortality_tests.jl`, field-by-field, **bitwise** | the `CI` gate |
| `scripts/build_slow_flux_table.py::PFT_PARAMS` | `gate_pft_params_against_reference()`, called at import | any run of the builder |
| — the same, under CI | `python/tests/test_mort_params_reference.py` | the `python` gate |

The pytest exists because `scripts/*.py` is watched by **no** CI gate (ADR 0090 / CLAUDE.md §5), so an
import-time assert inside the builder fires only when somebody runs the builder. It also contains a
**mutation test**: perturb one `wdmort_1` by 1e-3 and require the assert to fire. A gate that cannot fail
is not a gate — ADR 0032 is the record of a check that could never fail hiding a two-order-of-magnitude
basis shift for five days.

### 3. The lookup ERRORS on an unknown PFT id

`pft_mort_params(id)` raises rather than defaulting. This is load-bearing: `fc.pft_ids` exists
(`fast.jl:94`) but line M's drivers never pass it, so `FDiffFastCore` defaults every tree to
`pft_ids = 3` — beech. A lenient lookup would run the Amazon and the Sahel (`Type 0`) on beech `wdmort`
inside the very fix meant to correct per-PFT selection, i.e. it would reproduce the ADR-0031 defect class
in new code. Until M passes `pft_ids` (M integration point #1), an S-side harness must pass real ids.

## Two facts the generated parse turned up that nobody had recorded

* **PFT id 6 (larch) declares `aphen_min` and `aphen_max` TWICE.** `par/pft_lpjmlfit.js:1001-1002` sets the
  macro defaults (`APHEN_MIN` 60 / `APHEN_MAX` 245); `:1003-1004` then sets 10 / 200. LPJmL reads every
  parameter through json-c's hash lookup (`json_object_object_get_ex`), and json-c's tokener inserts each
  pair with `json_object_object_add`, which **replaces** — so the LAST occurrence wins and the effective
  larch values are **10 and 200**. `json.loads` does the same, which is the only reason this parse is
  faithful, so the builder **enumerates** the duplicates and asserts the set has not changed: a new
  duplicate silently overrides a parameter and must be read deliberately. Consequence: larch starts
  accumulating water stress (`waterstress_tree.c:31`) six times earlier in the season than every other
  tree PFT.
* **`sla_median` (0.01986) is a single global default and lies OUTSIDE `[low, high]` for ids 1, 2, 3 and
  5.** Recruit traits are drawn on `[low, high]` (ADR 0045), so `sla_median` must not be treated as a
  central value of the interval.

Neither changes the hazard. Both are the kind of fact that costs a session when discovered later.

## Consequences

* **Stage 1 is complete and inert.** No committed baseline, ReferenceTest, oracle CSV or AD path changes;
  the runtime `[deps]` stays empty (ADR 0014). Suite: see the JOURNAL entry for the job id.
* **The parameter values in `build_slow_flux_table.py` are now checked rather than trusted.** They were
  correct; that was previously an assertion in a comment.
* **Stage 2 (the call site) is unblocked by ADR 0048**, and its acceptance target is ADR 0046 §3's per-PFT
  age–wooddens gradient — *including the non-monotone shape for ids 0 and 3*. A ported operator that
  produces a monotone gradient everywhere is wrong even if `Rb` improves (ADR 0044 §5).
* **`bm_inc_counter` is not recoverable from the annual `ind` output** (it is one of the commented-out
  RAW-only columns), so no training table can carry it and a rollout must evolve it itself from 0. That
  is documented on `update_bm_inc_counter` and is a real constraint on Stage 2's design.
* **The hazard is stochastic in FIT** (a per-individual `erand48` draw), so `1 − total` is an EXPECTED
  survival. A deterministic Stage-2 application of the expectation is a modelling choice that will need
  its own justification, not a free simplification.

## Alternatives rejected

* **Hand-transcribing the seven rows into Julia.** Fastest, and exactly the ADR-0031 defect. Rejected on
  measured evidence, not on principle.
* **Loading the CSV from `src/` at runtime.** Would make the parameters unforgeable, but the file is a
  test fixture under `test/testitems/references/`, and `src/` reading a test fixture inverts the
  dependency (and breaks a packaged install). Literals + a bitwise gate gets the same guarantee.
* **Putting the hazard in `src/components/slow.jl`.** S owns that file, so it was allowed. Rejected: the
  file is already 823 lines and the hazard is self-contained with no dependence on any other `src` file,
  so a separate include in the line-S region is cleaner and keeps the diff reviewable.
* **Wiring the call site in the same commit.** Rejected by handoff item F and guardrail 4 — every arm lands
  separately with its own matched baseline. Bundling is what produced five prior wrong turns on this line.
* **Porting only `mort_max` as the trait channel.** Rejected by ADR 0046 §3 with a number: it gets ids 0
  and 3 backwards. `test/testitems/slow_trait_mortality_tests.jl` now pins the crossover growth efficiency
  (~172, inside FIT's measured `growth_eff` range, mean 146.7 / max 31 183) so this simplification cannot
  be reintroduced silently.
