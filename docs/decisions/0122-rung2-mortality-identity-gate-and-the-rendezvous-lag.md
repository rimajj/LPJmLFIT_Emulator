# ADR 0122 — The rung-2 mortality port is verified EXACTLY, and the rendezvous lag inverts the trait selection

- **Status:** accepted
- **Date:** 2026-08-11
- **Line:** M (multi-cell coupled S+F+E; ADR block 0120–0139)
- **Supersedes / amends:** nothing. Extends ADR 0061 (the observation hook), ADR 0120 (the substitution
  hook) and ADR 0121 (the three-phase dump + the corrected replay floor). Answers the free identity gate
  line S offered in ADR 0117 item 4.
- **Related:** ADR 0046 (the warming shift is within-PFT selection), ADR 0047→0049 (the ported hazard),
  ADR 0106 (the acceptance criterion), ADR 0117 (S's option (c) reply), ADR 0118 (the copula-selection
  confound and its owner-superseded item 4).

## 1. Context

Line S returned **option (c)** for the rung-2 demography interface (ADR 0117): S hands back a
per-individual survival factor `f_i = (1 − mort_i)^θ`, keyed by the `(pft_id, treeidx)` pair of M's `pre`
roster, and M draws the Bernoulli. S's existing opt-in `trait_mortality` operator
(`src/trait_mortality.jl`, ADR 0047→0049) already computes exactly that, and ADR 0049 item 2 records that
**θ = 1 recovers FIT exactly**. S offered the consequence as a free gate: *"S's operator must reproduce
your per-tree `mort`. No new code; any mismatch is a port error in `src/trait_mortality.jl`, caught before
a science number is quoted."*

That gate had never been run. `src/trait_mortality.jl` **has no call site anywhere in the package** (by
design — guardrail 4 ships it inert), and the one test that touches it,
`test/testitems/slow_trait_mortality_tests.jl`, gates its **parameter table** against
`S_pft_mortality_params.csv` and each component against a re-typed algebraic expression. Nothing had ever
scored it against the C binary's own per-individual answer on real state. It is about to become
load-bearing for every rung-2 trait number.

## 2. Decision

Run the gate, and **extend the rung-2 dump schema by the two columns needed to make it complete** rather
than settle for a partial one.

### 2.1 The schema change (`patches/lpjmlfit_rung2_hook_v4.patch`, supersedes v3)

Two `Real` fields on `Pfttree` — `bm_delta` and `leafarea_real` — assigned in `mortality_tree_ind` and
emitted as two extra `T`-record columns by the observation hook. They are **write-only from LPJmL's own
point of view**: nothing in the C reads them, so the stock binary is unaffected.

Why they were necessary, and this is the finding that forced the patch. The rendezvous at which S is asked
for `f_i` is `rung2_apply_begin_patch`, at the **top** of the annual demography block
(`annual_natural.c:64`) — the `pre` phase. The C computes its own hazard later, inside `annual_tree` →
`mortality_tree_ind`, **after** `turnover_tree` and `allocation_tree`. Measured against the recorded dump,
that ordering splits the four hazards in two:

| hazard | inputs at the `pre` roster |
|---|---|
| `mort_age` | **exact** — the `pre` age IS the pre-increment age the C used |
| `mort_water` | **exact** — `water_stress` is byte-identical `pre` vs `mort` in **all 9 951** records |
| `mort_temp` | **exact** — likewise `temp_stress` |
| `mort_npp` | **absent** — needs post-allocation `bm_delta = bm_inc.carbon/nind − turnover_ind.carbon` and `leafarea_real = ind.leaf.carbon·sla` |

And `bm_delta` is **not reconstructable** from the dumped columns. `turnover_tree` returns
`turn.leaf + turn.root + turn.sapwood + turn.sapwood_bg`; the two sapwood terms *are* recoverable (they
equal Δ`heartwood_c` between the `pre` and `mort` phases — verified exactly, which also pins
`turnover.sapwood = 0.04`), but `turn.leaf`/`turn.root` are daily-accumulated `tree->turn.*` fields, the
`isphen` branch (`turnover_tree.c:100-108`) is not dumped, and `turnover_tree` further **mutates**
`bm_inc.carbon` (reproduction cost, `cmass_excess`, debt payback) before `allocation_tree` mutates it
again. Reconstructing it would mean porting turnover **and** allocation — i.e. abandoning the narrow
interface that is rung 2's whole premise. Two dumped doubles is the cheap, exact alternative.

`mort_npp` is not an arbitrary fourth of the hazard: **`mort_max(wooddens)` enters the hazard only
through it**, so it is the entire trait channel — the reason arm C exists. Leaving it ungated would have
meant quoting a trait-selection result off an unverified port.

### 2.2 Both creation paths initialise the two fields

`new_tree.c` (establishment) and `fread_tree.c` (restart) set both to 0. This deliberately breaks with
their `mort_*` siblings, which ADR 0120 documented as uninitialised memory that the dump has to
special-case. The difference: **these two are READ by the external demography at the rendezvous**, so a
recruit whose first-year values were garbage would be handed a random hazard. Zeroed,
`leafarea_real == 0` is an unambiguous "no growth history yet" sentinel. The restart **format is
unchanged** — `fwrite_tree`/`fread_tree` serialize field by field, so the two fields are simply absent
from the list and `restart_1999.lpj` stays byte-compatible.

Measured effect: before the initialisers, `scripts/diagnose_rung2_dump_equality.py` reported
`bm_delta`/`leafarea_real` differences in 695–705 `pre` and 259–317 `post` records of an
otherwise-exact arm and returned **"the two dumps report DIFFERENT model state"** — a false FAIL on an
arm whose roster was identical in every year and whose cell state agreed in all 1 500 patch-years. After
the initialisers both arms read **"identical in every initialised column"**.

### 2.3 Gates run

- **Rebuild equality, twice** (once per rebuild), `scripts/diagnose_cbinary_rebuild_equality.py` on
  **decoded** variables against the v3 build's matched single-cell run (cell 42490, `--ntasks=1`, same
  config — the ADR-0041 decomposition control holds): **110 quantities identical, 0 differ**, including
  `ind_2000_2019.csv` and `globalflux_2000_2019.csv` byte-for-byte.
- **Baseline re-recorded** (`MODE=record`) — mandatory, because a schema change invalidates the reference
  basis every arm is scored against. New baseline `/p/tmp/jamirp/M_rung2/M_rung2rec_v4b_dump`.
- **The replay floor is unchanged**: `none` **1.000**, `kills` **1.000 — 376 vs 376, exact, no year
  differs**, identical in every initialised column and in every cell-state channel across all 1 500
  patch-years. ADR 0121's floor survives the schema change.

## 3. Result — the port is EXACT

`scripts/diagnose_rung2_hazard_identity.jl`, over all **9 951** tree-patch-years of the baseline dump
(cell 42490, 25 patches, 2000–2019, PFT ids 1/2/3/4/5/6 = 631/275/7 370/1 231/401/43 records):

| gated quantity | records | exceedances | max relative Δ |
|---|---|---|---|
| `mort_age` | 9 951 | 0 | 5.0e-16 |
| `mort_temp` | 9 951 | 0 | 1.7e-16 |
| `mort_water` | 9 951 | 0 | 2.2e-16 |
| `mort_npp` | 9 951 | 0 | 1.6e-15 |
| **`mortality_hazard.total`** | **9 951** | **0** | **1.6e-15** |
| `leafarea_real == leaf_c·sla` | 9 951 | 0 | 0 (bit-exact) |

Both hard kills are classified correctly too: 175 `bm_inc_counter ≥ 5` and 195 ghost-tree kills
(3.7 % of records), with the remaining 9 581 on the capped additive sum. Every number is at double
round-off, so this is an **identity**, not an agreement. **S's ported hazard reproduces the C binary's
per-individual annual mortality probability exactly**, and ADR 0049's θ = 1 claim is now measured rather
than asserted.

Two by-products worth keeping:

- The dump is **self-consistent**: the C's own `mort_prob` equals `min(1, Σ` its own four components `)`
  to 2.2e-16 on the 9 579 non-capped records.
- ADR 0049 item 4's limitation is **retired**. It zeroed `mort_water` and `mort_temp` because the
  emulator had neither of FIT's stress integrals; inside this harness both are exact, so the operator ran
  complete for the first time.

## 4. The finding that decides arm C — the rendezvous lag inverts the trait selection

The identity above is scored on the inputs `mortality_tree_ind` **actually used**. Arm C, running live,
gets only what the `pre` roster carries — and now that `bm_delta`/`leafarea_real` are persistent fields,
that is **last year's** growth outcome, plus last year's `bm_inc_counter` (the counter is updated *inside*
`mortality_tree_ind` from the sign of this year's `bm_delta`, and `pre` vs `mort` differ in **2 169 of
9 951** records, 21.8 %).

Scored on 9 009 records with a previous year available, per-patch-year Spearman ρ against the C's own
`mort_prob` is reassuring — **median 0.900** (p05 0.467). The trait statistic is not. Taking the one-year
wood-density selection differential (hazard-weighted mean `wooddens` minus the `nind`-weighted stand mean;
positive = denser wood dies more, i.e. ADR 0046 §3's `|live` differential with the sign flipped, and its
sign agrees with ADR 0046's independent finding for the beech-dominated cell):

| hazard basis | differential (gC/m³) | ratio to the C |
|---|---|---|
| the C itself | **+17 729** | 1.000 |
| the lagged rendezvous, i.e. **arm C as it would run today** | **−14 528** | **−0.819 ⚠ opposite sign** |
| … the same with both hard kills suppressed | −14 528 | −0.819 ⚠ (so the hard kills are *not* the cause) |
| … only `bm_delta`/`leafarea_real` lagged | **+17 750** | **+1.001** |
| … only `bm_inc_counter` lagged | −9 967 | −0.562 ⚠ |

**The growth-efficiency lag is harmless (+1.001). `bm_inc_counter` alone inverts the sign.** The mechanism
is plain once isolated: the counter **multiplies** `mort_npp` and `mort_water` by `(1 + counter)`, so a
tree that has been declining for three years carries 4× the hazard, and misassigning that multiplier by a
year re-weights exactly the trees whose wood density the differential is measuring.

⚠ **This is a limitation of the harness's rendezvous POINT, not of S's operator and not of the
emulator.** In the standalone emulator the fast core computes this year's growth *before* the slow
demography runs, so `bm_delta` — and therefore the counter — is current. The lag is an artifact of asking
for the whole patch's answer in one file exchange before any tree has grown.

**Consequence, pre-registered here so it cannot be reinterpreted after a run: arm C must not be scored on
the trait question from the current rendezvous.** A `C1 − C0` wood-density result taken today would carry
a channel of the wrong sign that has nothing to do with whether S's operator is right. Counts and the
ordering (ρ median 0.900) are a different matter and remain readable.

## 5. What follows

1. **Move the rendezvous behind the growth loop** (the scoped next C change). In `annual_tree`, with the
   apply hook on, return "alive" for every non-forced tree and record its current-year state; after the
   `foreachpft` loop and before the `mort` dump, do the rendezvous with the complete current-year roster
   and apply the kill set there — `litter_update` and the `mort_tree` counter move with it. Gated behind
   the apply hook so the stock binary is untouched, and **proven by `MODE=none` still reproducing exactly**.
   That removes the lag entirely and makes the identity of §3 the live basis rather than the offline one.
2. **Until then, arm C is runnable for counts and ordering only.** Quote the ADR-0121 floor beside it
   (`kills` 1.000, `recruits` 0.907, `both` 1.367), say **one cell of 54 020**, and say **4 of 7 trait
   axes substituted**.
3. **The identity is now a CI gate**, not a session result:
   `test/testitems/m_rung2_hazard_identity_tests.jl` re-scores the port against a 333-record PFT-stratified
   C-truth fixture (`test/testitems/references/M_rung2_hazard_identity.csv`, 61 hard kills, 6 PFT ids) on
   every run. `src/trait_mortality.jl` cannot regress against the C without a red gate.

## 6. The transferable lesson

**An interface's inputs are dated, and the date is part of the contract.** The rung-2 interface was
specified by *what* crosses it — who dies, who establishes — and reviewed for that; three ADRs
(0061/0117/0120) described the per-tree record as carrying "the accumulators three of the four death rates
read" without anyone asking *as of when*. ADR 0117 item 3 states the stronger version outright — *"your
`pre` record carries `water_stress`, `temp_stress`, `bm_inc_counter` and `bm_inc` ⇒ inside the harness all
four hazards are computable faithfully"* — and it is **wrong on the fourth**, because `bm_inc` at the
`pre` phase is the year's gross NPP while the hazard consumes the post-turnover, post-allocation residual
minus turnover.

The tell was available before any run and cost minutes to find: **diff the same field between two dump
phases of the same tree-year.** `water_stress` and `temp_stress` differed in 0 of 9 951 records,
`bm_inc_counter` in 2 169, `leaf_c` and `bm_inc_c` in all of them. A single-phase dump could not have
revealed it — the three-phase dump ADR 0121 added for a different reason is what made the interface's
own timing auditable.

Generalisation, and it is the same shape as ADR 0112's forcing-basis rule: **before trusting a learned or
ported component's inputs, ask who computed each one and at which point in the step** — then verify the
answer against two observations of the same state rather than against the field's name.
