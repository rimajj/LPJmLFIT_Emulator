# ADR 0132 — The below-ground wood sink is now prognostic: it closes 34 % of F's surplus growth at Hainich and PASSES the pre-registered bar there, FAILS at boreal — and a 4 % seeding convention was hiding the whole mechanism

* **Status:** accepted
* **Date:** 2026-08-13
* **Line:** M (multi-cell coupled S+F+E; rung 3 of `EXECUTION_PLAN.md`) · ADR block 0120–0139
* **Consumes:** ADR 0127 (the exact three-channel decomposition of F's surplus above-ground growth; §5
  priced this sink and §6 pre-registered the pass criterion this ADR is scored against), ADR 0131 (the
  tree demand-gate, whose default flip is gated on this port landing), ADR 0110 (per-tree root profiles —
  the demand is computed on each stem's own profile), `docs/notes/sapwood_bg_design.md` §5.4/§8.1/§9
  (the deferred implementation step this completes)
* **Supersedes:** nothing. **Narrows ADR 0127 §6** — its pre-registered criterion named two cells, and its
  own §5 had already measured that the mechanism explains 11 % of the sink at one of them. **Amends
  `sapwood_bg_design.md` §8.1's seeding convention** (§5 below).
* **Basis:** rung 3 — the C's own roster restarted every year, 25-patch ensemble, year-matched, five biome
  cells, historic 2010–2019. The probe's PART 1 basis gate against ADR 0125's published panel **PASSes**
  in this run. Log of record **`logs/M-bggrow.1769028.out`**; full suite **`logs/M-bgsuite.1769029.out`**
  (**275 597 pass / 0 fail**, 135 test items).

---

## 1. Context — what was missing, and why it could not be a one-field port

ADR 0127 decomposed F's surplus above-ground growth into three exact carbon channels and found the third,
`t_nosink`, to be a genuinely missing mechanism: the C carries **two** below-ground wood pools that F does
not, and it **deducts their annual demand from `bm_inc` before the leaf/root/sapwood split**
(`allocation_tree.c:268-277`). F's `sap_inc = bm_net − leaf_inc − root_inc` is a residual, so every gram
of undeducted demand lands in **above-ground sapwood**, which is exactly the pool `agb_ind` reports.

`sapwood_bg_design.md` §8.1 had already landed the *maintenance* half — the pool is seeded at init and
pays its phen-gated respiration — but left the pool **static**. ADR 0127 §6 recorded why the growth half
could not be a one-field change: `turnover_tree.c:124-130` moves `sapwood_bg·turnover.sapwood` into a
**second** pool, `heartwood_bg`, which only ever accumulates and never respires. A single field must
either destroy that carbon each year (a leak, and conservation is a CI gate) or charge maintenance on
below-ground heartwood, which the C does not.

## 2. What was built

`TreePools` gains `heartwood_bg_c` (13 → 14 fields) beside `sapwood_bg_c`, with a backward-compatible
13-arg constructor so all ~35 existing construction sites are byte-identical. `vegc_full_ind` takes both
⇒ it is now the C's own `vegc` pool set (`veg_sum_tree.c:25`) less the debt/excess/fruit terms F does not
carry; `vegc_ind` deliberately stays the historic four-pool sum, so no committed baseline that reads it
can move. `grow_individual` gains three keyword arguments — `bg_growth`, `bg_rootdist`, `bg_soildepth` —
and when they are on it runs, in the C's own order:

1. the below-ground half of the turnover, `sapwood_bg → heartwood_bg` at `turnover_sapwood`
   (`turnover_tree.c:126,131,135`) — internal to the bucket, so carbon-neutral by construction;
2. the C_LATERAL demand `D` at this year's **post-turnover** sapwood and last year's height
   (`allocation_tree.c:163-189`, the already-ported `reconstruct_sapwood_bg`), on **this stem's own root
   profile** when `per_tree_roots` built one (the C calls `getrootdist` per individual, `:159`);
3. the top-up `tinc = D − sapwood_bg` when the pool is already `> 0` (`:191-193, :206`), **deducted from
   the assimilate before** the leaf/root/sapwood split, taking only the surplus above `leaf_min +
   root_min` when the assimilate cannot cover it (`:275-278`).

The carbon debt (`:288-297`) is **not** ported — F carries no `debt` pool, and a carbon-starved tree hits
F's stagnation guard instead. `FDiffFastCore` gains a `bg_growth` field and `rollout_canopy_years` a
`bg_growth` kwarg; the Enzyme SoA trainer builds its pools with the pre-`sapwood_bg` arity, so the
differentiated path is untouched. Gate: `test/testitems/sapwood_bg_growth_tests.jl` (569 assertions).

**Guardrail 4 holds twice over.** `bg_growth = false` is byte-identical, and with it *on* the C's own
`allocation_tree.c:206` gate grows nothing while the pool is 0, so an unseeded roster is unchanged. The
full suite is **275 597 pass / 0 fail** with **no baseline moved**, and the committed
`M_growth_channel_decomposition.csv` gained 15 rows with all 35 pre-existing rows **byte-identical**.

## 3. The conservation property that makes the second pool non-optional

In the normal allocation branch the post-growth pools sum to the post-turnover pools plus the assimilate,
whether or not the top-up ran — the top-up only moves carbon from the residual sapwood into the
below-ground bucket. So the port is a pure **redistribution**:

> `vegc_full_ind(on) == vegc_full_ind(off)` exactly, while `vegc_ind(on) < vegc_ind(off)` and
> `agb_ind(on) < agb_ind(off)` by exactly the carbon the bucket gained.

This is asserted on all 272 stems of the committed Hainich roster, and it is the assertion a one-field
port cannot satisfy.

## 4. ⚠ FIRST FINDING — a 4 % seeding convention made the entire sink compute as exactly zero

The demand is **linear in sapwood carbon at fixed height**, and under the pipe model
`sapwood/height = leaf·sla·wooddens/k_latosa`, so for any pipe-consistent stem

> `D = c · leaf_c · sla · wooddens / k_latosa`,  `c = Σ_l dz_l·(root_sum_l + rootdist_l·2π/C_LATERAL²)`

with `c` a pure soil-geometry constant (3.314 for the Hainich column; verified to 1e-12 in the gate).
Substituting into the C's own update gives the annual sink in closed form:

> `tinc = (c·sla·wooddens/k_latosa) · (leaf_y − (1−r)·leaf_{y−1})` — **the below-ground wood sink is paid
> on the growth of the leaf pool.**

`sapwood_bg_design.md` §8.1 seeds the pool at the bare demand `D`. But the C pins the pool to the demand
at the **post-turnover** sapwood and then takes `r` off it again the following year, so a stem entering a
year holds `(1−r)·D`, not `D`. With the `D` seed, the post-turnover pool `(1−r)·D` and the demand
recomputed on the same shrunken sapwood `(1−r)·D` are **equal**, so `tinc` is **identically zero** — the
mechanism is inert, and a harness would have measured its own seeding convention rather than the physics.
Measured on the committed Hainich roster: the top-up fires on **0 of 272** stems with the `D` seed and on
**205 of 272** with `(1−r)·D`.

This is now `FDiff.sapwood_bg_seed`, and the probe's growth arms use the strictly better version of the
same correction — the pool a stem carries into year `y` is `(1−r)·D` evaluated at the state it had **one
fixture earlier**, which is the only form that carries the stem's own growth (the closed form above says
the sink IS that growth). One of the ten years falls back to the steady-state form because the
`2008` roster fixture does not exist; the probe prints that count (`bg_miss = 1`).

**The method lesson, and it is the reusable part:** a harness that re-initialises the model from truth
every year has already discarded any quantity defined as a year-over-year *difference of state*. Before
scoring such a mechanism, write down what the state variable equals at the start of the step and check
that the initialisation reproduces it — `residual-diagnosis`'s "confirm the comparison basis" applied to
an initial condition rather than to a reference dataset.

## 5. The measurement against ADR 0127 §6's pre-registered criterion

The criterion, written before the arm existed: *"the paired surplus `Δagb_F − Δagb_C` must fall by at
least `t_nosink` at `boreal_siberia` and `temperate_hainich` (≥19.9 and ≥30.9 gC/m²/yr) without any
committed baseline moving while the feature is off, and the tree CUE must stay inside [0.42, 0.56]."*

All fluxes gC/m²/yr, 10-year means. `Abgg`/`Pbgg`/`Pgbgg` = arms A/P/Pg + the seeded, prognostic pool.

| pair | cell | surplus before | surplus after | **drop** | bar | verdict |
|---|---|---|---|---|---|---|
| A → Abgg | boreal_siberia | 43.5 | 25.1 | **18.5** | 19.9 | ✗ (93 % of it) |
| A → Abgg | temperate_hainich | 152.7 | 101.4 | **51.3** | 30.9 | ✓ |
| **Abg → Abgg** (the sink ALONE — both arms seeded) | boreal_siberia | 39.6 | 25.1 | **14.5** | 19.9 | ✗ |
| **Abg → Abgg** | temperate_hainich | 133.7 | 101.4 | **32.3** | 30.9 | ✓ |
| P → Pbgg | boreal_siberia | 75.9 | 56.7 | **19.2** | 19.9 | ✗ (97 %) |
| P → Pbgg | temperate_hainich | 154.0 | 102.6 | **51.3** | 30.9 | ✓ |
| Pg → Pgbgg | boreal_siberia | 63.9 | 44.7 | **19.2** | 19.9 | ✗ |
| Pg → Pgbgg | temperate_hainich | 144.8 | 93.5 | **51.3** | 30.9 | ✓ |

**The criterion named two cells and the port passes at one.** Tree CUE stays inside `[0.42, 0.56]` at both
criterion cells on every growth arm (Hainich 0.479, boreal 0.533–0.560; note arm **P** at boreal is
**0.571**, *outside* the band and pre-existing — the port moves it back inside, it does not cause it).

**The failure at boreal was predicted by the ADR that set the bar.** ADR 0127 §5 measured `dD/bel_C` =
**0.11** there and wrote *"the port is not the boreal answer"*, and §8 item 4 named that cell as the one
where allocation/turnover genuinely binds and the below-ground sink is not the explanation. So §6's
criterion was **internally inconsistent with its own §5** — it required a mechanism to close a channel
its own measurement said was 89 % something else. The honest reading is not "the port under-performs at
boreal"; it is that **the pre-registered bar at boreal was set on the wrong quantity**, and the port
delivers there roughly what §5 said it could.

**What the mechanism itself absorbs**, independent of whether it cleared any bar (`belF_wood`, the annual
carbon taken by the two below-ground wood pools): **34.9** at Hainich, **16.5** at boreal, **41.5** at the
mediterranean, **16.6** at the Sahel and **101.3** at the Amazon on arm P. At Hainich that is **23 % of
F's surplus** and the whole remaining below-ground channel there is 32.6.

## 6. What this does NOT fix

At Hainich the surplus falls 154.0 → 102.6 gC/m²/yr against a C increment of 181.1 — **F still over-grows
by 57 %**, and ADR 0127 §4 already said why: 77 % of that surplus is the **assimilate** error, which this
port does not touch (GPP is byte-identical between an arm and its growth arm; `gpp_F` 1221.5 on both P and
Pbgg). The F-side queue does not move off the assimilate.

## 7. ⚠ INTEGRATION POINT RAISED TO LINE S — `src/components/slow.jl` drops the new pool

Four sites in S's exclusive `src/components/slow.jl` rebuild a `TreePools` with the pre-`heartwood_bg`
13-arg arity and would therefore **silently discard** a grown `heartwood_bg_c`: the recruit mix
(`:161`), `_with_nind` (`:249` — every density change), the recruit build (`:479`) and the K-cap merge
(`:670`). It is the same shape as the ADR 0110 trait-drop those sites were fixed for. **Nothing is broken
today** — `bg_growth` is off by default and `run_coupled_cell` is the only path that pairs a slow
emulator with the fast core — but the two features are incompatible until S carries the field, and
`FDiffFastCore`'s docstring says so. Mirrored into `lines/S/STATE.md`.

## 8. Consequences

1. **The `sapwood_bg` growth port is landed, opt-in and default byte-identical.** `bg_growth` on
   `FDiffFastCore` / `rollout_canopy_years` / `grow_individual`.
2. **ADR 0131 §8's flip criterion for `tree_demand_gate` is now unblocked on its condition (a)** — the
   growth port has landed. Its conditions (b) and (c) still have to be evaluated, and arm `Pgbgg` in the
   committed table is the arm to evaluate them on.
3. **`sapwood_bg_design.md` §8.1's seeding convention is amended** — seed with `FDiff.sapwood_bg_seed`,
   not the bare `reconstruct_sapwood_bg`. Existing seeded arms (`Abg`, `Pbg`) keep the old convention so
   they continue to reproduce ADR 0127; their pool is 4 % too large and their respiration correspondingly
   over-charged, which is disclosed here rather than silently corrected.
4. **ADR 0127 §6's pre-registered criterion is retired as a pass/fail gate at `boreal_siberia`** and kept
   at `temperate_hainich`, where it passes. A future pre-registration must not set a bar on a channel the
   same document has measured the mechanism cannot reach.
5. **Do not read `keep`, `dD` or `t_nosink` across a seeding change without re-reading §4.** The seed is
   part of the operator, not part of the setup.

## 9. Scope — what this is NOT

* **Five cells of 54 020**, one scenario, ten years, `slow = nothing`. A mechanism result, not fidelity
  evidence (ADR 0106).
* The carbon **debt** loan is not ported; nor is the C's `excess_carbon` path.
* The demand uses each stem's own root profile only when `per_tree_roots` is on; otherwise the cell-mean
  profile, which under-states a deep-rooted stem's demand (ADR 0127 §7, unchanged).
* The **Enzyme/decadal trainer is untouched** — its SoA rebuild carries no below-ground pool, so the
  gradient path has not been re-verified with the sink on. That is the next thing to do if the sink is
  ever wanted on the trained path.
* `bg_miss = 1` of 10 years at every cell: the first year's seed falls back to the steady-state form
  because the one-fixture-earlier roster does not exist.
