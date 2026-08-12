# 0171 — The recruit arm at THREE cells: the level shift is the robust finding, the response contribution is not even SIGN-stable across cells or artifacts — and a train/inference defect in the ssp370 conditioning basis, found and fixed one step before it could bite

* Status: accepted
* Date: 2026-08-12
* Line: S (tier-3 block 0170–0189)
* Supersedes: nothing. **Narrows ADR 0170 §2** (its response-sign statement is Hainich-and-demo-artifact
  specific — measured here, not argued) and **corrects ADR 0170's handoff item 3** (the Amazon/Sahel are not
  the `n_elig = 1` regime) and **ADR 0170 §4c's reading** (warming does not always hand recruits to the
  seedbank; at a cold cell the gate OPENS). Extends ADR 0119 §6 (the pre-registered flip criterion),
  ADR 0101 (one run is not a measurement), ADR 0026 (the transient boundary), ADR 0023 (train/inference
  consistency).
* Reproduce (each `40` seeds, ~2 min/job, `TRAIT_MORT=0 K_CAP=400 SCORE_WINDOW=20 ARM=recruit`):
  `scripts/run_response_seed_ensemble.sh S-rbfixH 40` (Hainich, demo pair) ·
  `DRF_ART=…/drf_forest_global_pooled_w20_t8.drf RCOP_ART=…/recruit_copula_global_pooled_w20_t8.rcop
  N_INIT=11.0 AGE0=43.55555555555556 … S-rbpoolH 40` · the same with
  `BND_FIXTURE=/p/tmp/jamirp/emulator_global/S_response_boundary_prefix0171_42490.csv … S-rbpoolHpre 40` ·
  `SITE=tropical_amazon … S-rbAMZ 40` · `SITE=boreal_siberia … S-rbSIB 40`. Jobs 1761398–1761399 (the
  refactor-inertness pair), 1761401–1761402 (eligibility), 1761408–1761657. Per-seed record:
  `test/testitems/references/S_recruit_multicell_seed_ensembles.csv`.

---

## 0. Reconciliation with the ADR this extends (the panel every extension opens with, ADR 0116 §4)

ADR 0170 measured the recruit arm at Hainich on the committed demo artifact pair and concluded: the kill
condition does not fire (R0's own warming response is wrong-signed at **−0.75 ± 0.24 ×FIT** and the port turns
it **+2.66 ± 1.01**), it does not clear either (the response overshoots and the **level moves +8.5 %**), and
its handoff named *"do it at MORE CELLS, not more seeds"* as the next step, plus a claim that the
Amazon/Sahel are a `n_elig = 1`, `w_inherit = 0.8` regime.

This ADR runs that next step. **The level finding survives at every cell tested and is the reason the flip
stays refused. The response-sign finding does not survive** — it reverses when the artifact changes at the
same cell, and again when the cell changes at the same artifact. The `n_elig = 1` claim was wrong. Nothing
about the ported rule's code changed, and no default moved.

**Scope, stated before any number: three cells of 54 020 (guardrail 6), one scenario pair, `trait_mortality`
off (the shipped configuration), offline — so ADR 0049 item 4 still holds (`mort_water`/`mort_temp` are
zeroed offline). This is not the flip test; that is rung 2, on line M's harness.**

---

## 1. The measurement, and the one thing that had to be built first

`scripts/trait_mortality_arm_probe.jl` was Hainich-hardcoded in seven places (individuals, 2010 forcing,
soil column, latitude, the daily scenario file name, the transient boundary, the eligible-set fixture). It
now takes **`SITE`** — a name in the committed `M_cells.csv` — and reads that cell's `M_individuals_*`,
`M_soilcolumn_*`, `biome_forcing_*` fixtures (line M's coupled-driver provisioning), its own
`S_response_boundary_<site>.csv` and `S_estab_eligibility_<site>.csv`, and its `n_init`/`age0`/static
boundary from `M_cells.csv`.

**`SITE` unset is byte-identical to every earlier run, and that is verified rather than asserted:** the
pre-refactor and post-refactor probes were run on the same seed and their outputs differ in exactly two
lines, both of them the scope label that deliberately now names the cell (jobs 1761398/1761399); and the
full 40-seed Hainich demo-pair ensemble reproduces **ADR 0170 arm A to every digit** — level effect
+19 700.802 ± 1 280.900 gC/m³ (ADR 0170: +19 701 ± 1 281), R0 −0.747 ± 0.236, R1 +2.660 ± 1.010,
contribution +3.407 ± 1.009, inherited share 40.845 %.

⚠ **A non-default site takes `n_init`/`age0`/`boundary` from `M_cells.csv` and NOT from the artifact meta.**
The committed demo meta carries **Hainich's** values, so consulting it at another cell would silently start
that cell's forest on Hainich's stem count — the "someone else's forest" failure the probe's own error message
has warned about since ADR 0101 without being able to prevent it. At the default site the historical
precedence (ENV → meta) is unchanged.

---

## 2. THE DEFECT: 19 of the 81 ssp370 conditioning years were not the quantity the artifacts were trained on

Found while adding a per-cell gate, not while looking for it. `scripts/build_hainich_response_forcing.py`
gave the **historic** side of its transient boundary a `W−1` year monthly lead-in, so year 1's trailing window
is a real 20-year climatology, and gated the result against the committed ClimBuf fixture. The **ssp370** side
had no lead-in, and a comment asserted that omission was deliberate — that `build_transient_boundary.py`
*"accepts the short window for 2020-2034 as a documented edge, so replicating it is what keeps this fixture
consistent with the boundary table the artifacts were TRAINED against."*

**Measured, that was false.** The global builder averages its monthly climatology over the **whole** `.clm`
from its own first year (2015) and then takes `lo = max(0, iY − W + 1)`, so its 2020 window is 2015–2020,
while this script's was **2020 alone**. Against `cell_year_boundary_ssp370_w20.parquet` at Hainich:

| year | script's gdd5 | trained basis | Δ | script's tas_cold_month | trained | Δ |
|---|---|---|---|---|---|---|
| 2020 | 2177.70 | 1967.72 | **+209.98** | 2.890 | 0.952 | **+1.939** |
| 2021 | 2020.05 | 1947.71 | +72.34 | 0.589 | 0.865 | −0.276 |
| 2030 | 1954.56 | 1946.98 | +7.58 | 0.935 | 0.801 | +0.134 |
| 2039–2100 | — | — | **0 (exact)** | — | — | **0 (exact)** |

**19 of 81 years** (2020–2038) differed, by up to **+10.7 % in gdd5** and **+1.94 °C**. That is the ADR-0023
train/inference-shift trap: the DRF and copula were fitted on one quantity and the arm fed them another.

**Why no published number moved, and this is measured too.** The probe prints a **boundary-channel liveness**
check — `max |Δwd|` between the transient and the static boundary under the same forcing. On the committed
**demo** artifact it reads **exactly 0.0**: both boundary axes are constant in that artifact's training data,
so no split exists on them and the artifact **cannot** express a boundary-mediated response at all. Every
number in ADR 0100/0101/0170 was measured on that pair ⇒ **the defect could not have reached them**, and the
40-seed reproduction in §1 confirms it empirically.

**Where it would have bitten is exactly where this ADR was going.** On the global `pooled_w20_t8` pair the same
check reads **2022–2406 gC/m³** — the channel is live — and every cross-cell arm below uses that pair. So the
defect was found one step before the first measurement it could have corrupted.

**And its measured size, where the channel is live** (Hainich, pooled pair, the same 40 seeds, corrected vs
pre-fix basis — the only difference between the two ensembles):

| quantity | corrected | pre-ADR-0171 | Δ | the ensemble's own SEM |
|---|---|---|---|---|
| level effect, historic | +5 163.768 | +5 163.768 | **0** (the historic basis did not change) | 1 005.9 |
| level effect, ssp370 | +2 988.643 | +3 066.564 | −77.9 gC/m³ = 0.032 ×FIT | 403.0 |
| R0's warming response | +0.272 | +0.255 | +0.017 ×FIT | 0.135 |
| the port's contribution | −0.894 | −0.862 | −0.032 ×FIT | 0.323 |

**The fix moves the arm by ~1/10 of its own sampling error.** That is the honest statement: the defect was
real, the fix is correct and now gated, and its consequence for this arm is negligible against seed noise —
*not* because the channel is dead (it carries up to 2 406 gC/m³) but because the early-year window error is
small where it matters and decays to exactly zero over the scored window.

**Three things now prevent a regression.** (a) The ssp side takes the lead-in, clamped to the `.clm`'s own
coverage. (b) **GATE 1b**, new: the ssp370 boundary is compared to the trained table for the run's own cell
and the build **dies** on a mismatch (it reproduces it to **0, exactly**, at all three cells). (c) A CI-safe
tell in `slow_response_boundary_tests.jl`, because the trained table lives on `/p/tmp` and CI cannot read it:
a truncated first window shows up as a **step**, and the ratio of the largest year-on-year jump to the
series' own median jump was **13.1 (gdd5) / 17.6 (tcm) before the fix and 4.0 / 5.8 after**, so the test
allows 8. `SSP_LEAD=2020` + `ALLOW_UNTRAINED_SSP_BASIS=1` reproduces the pre-fix fixture bit-for-bit, which
is how the control arm above exists at all — and the escape hatch prints a warning naming the basis.

⚠ **An observation this uncovered but does NOT resolve.** `build_estab_eligibility.py` backfills its ssp370
20-year running means from the **historic** `.clm` (mirroring the C's own ClimBuf, which carries state across
the restart), while the trained boundary table reaches back only into the ssp `.clm`'s 2015. So the eligible
set and the DRF's boundary are on **different early-window conventions** — the emulator's conditioning must
match its training basis, and the gate must match the C. Both are correct for their own consumer; the
inconsistency is in the training data (ADR 0026 §2's "documented edge"), not in this fixture. Not chased here.

---

## 3. THE CROSS-CELL RESULT — the artifact held fixed at `pooled_w20_t8`, 40 seeds each, mean ± SEM

| cell | R0's level | level effect R1−R0, historic | R0's warming response | R1's | **the port's contribution** | inherited share (closed form) |
|---|---|---|---|---|---|---|
| **temperate_hainich** 42490 | 234 904 | **+5 164 ± 1 006** (t 5.1) | +0.272 ± 0.135 | −0.622 ± 0.274 | **−0.894 ± 0.323** (t −2.8) | 41.9 % (40.0) |
| **tropical_amazon** 12045 | 205 292 | **+10 117 ± 1 705** (t 5.9) | +0.297 ± 0.408 (n.s.) | +2.276 ± 0.800 | **+1.979 ± 0.930** (t 2.1) | 52.9 % (50.0) |
| **boreal_siberia** 52059 | 215 079 | **+10 749 ± 1 978** (t 5.4) | **+1.941 ± 0.210** (t 9.2) | +0.035 ± 0.492 (n.s.) | **−1.905 ± 0.532** (t −3.6) | 57.0 % (57.1) |

All in gC/m³ or ×FIT's +2432.9 per-cell median historic→ssp370 wood-density shift (ADR 0046 §1). Every
ensemble was 40 of 40 usable: **zero** hard kills, **zero** count-override years, **zero** k-cap merges, so
ADR 0048's and ADR 0101's preconditions hold everywhere and no row was excluded.

**1. THE LEVEL EFFECT IS THE ROBUST FINDING, AND IT BLOCKS THE FLIP AT EVERY CELL TESTED.** The ported rule
raises the standing community's mean wood density at all three cells, significantly (t 5.1–5.9): **+2.20 %
(Hainich), +4.93 % (Amazon), +5.00 % (Siberia)** of the control's own level, i.e. **2.1× to 4.4× FIT's entire
warming shift, as a static offset**. ADR 0170's +8.5 % was the demo-artifact figure at one cell; the effect is
smaller on the production artifact but it is the same sign, the same order and the same conclusion. **This is
now a three-cell result, and it is the reason `recruit_establishment` stays off.**

**2. THE CONTRIBUTION TO THE WARMING RESPONSE IS NOT SIGN-STABLE — the sign changes with the cell AND with the
artifact.** At the same cell (Hainich), swapping the demo pair for the production pair moves the contribution
from **+3.407 ± 1.009** to **−0.894 ± 0.323**. At the same artifact, moving cell moves it from **−0.894**
(Hainich) to **+1.979** (Amazon) to **−1.905** (Siberia). Both reversals are far outside the SEMs. The probe's
own header already warned that the artifact pair is part of the measurement (ADR 0101 §3 measured
opposite-signed *baselines* at Hainich, −1.23× vs +0.42×); this ADR shows the same for the recruit arm's
*contribution*. ⇒ **ADR 0170 §2's "the port removes a wrong-signed response" is a statement about Hainich on
the demo artifact and must not be generalised.** A single-cell response number for this channel carries no
information about the channel.

**3. THE BASELINE THE PORT IS SCORED AGAINST IS ITSELF WILDLY CELL-DEPENDENT** — R0, the *shipped* copula
recruit channel, gives +0.27 (n.s.-ish), +0.30 (n.s.) and **+1.94 ± 0.21 ×FIT**. At Siberia the shipped
configuration already **overshoots FIT's warming shift by 94 %**, and the port **destroys** that response
(R1 = +0.035, n.s.) rather than adding one. So "does the port improve the response?" has three different
answers at three cells, and at one of them the honest reading is that it removes a response that was already
too large. **Do not read a contribution's sign without its baseline beside it.**

**4. THE SAMPLER BEHAVES AS ADR 0045 PREDICTS IN ALL THREE REGIMES.** The realised inherited share matches the
closed form `4/(4+n_elig)` to within 2.9 points at every cell (41.9 vs 40.0 · 52.9 vs 50.0 · 57.0 vs 57.1),
across `n_elig` 6 → 4 → 3 and a 4× range of stem counts. Whatever is wrong with the port, the mixture weight
is not it.

**5. ⚠ THE GATE MOVES IN OPPOSITE DIRECTIONS WITH WARMING, AND ADR 0170 §4c's WORDING GENERALISED THE WRONG
WAY.** ADR 0170 measured Hainich's eligible set CLOSING under ssp370 ({1,…,6} → {1,2,3}, inherited share
0.400 → 0.571) and read it as *"warming hands more of the recruit population to the cell's own seedbank."* At
**boreal_siberia the gate OPENS**: {4,5,6} (26 yr) → {1,4,5,6} (20 yr) → {1,3,4,5,6} (35 yr), inherited share
**0.571 → 0.444**. The mechanism is symmetric and now explicit: warming pushes a cell's 20-year cold-month
mean **up**, which **expels** the three boreal ids (their `temp_high` is 0.0 °C) from a temperate cell and
**admits** temperate ids into a cold one. The Amazon's set is static ({0,1,2,3} all 81 years). ⇒ the transient
gate is a **direction-of-travel** statement about each cell's own climatology, never a global one.

---

## 4. The `n_elig` correction — ADR 0170's handoff named the wrong cells for the low-diversity regime

ADR 0170's handoff item 3 proposed *"a low-diversity cell (Amazon/Sahel, `n_elig` 1, `w_inherit` 0.8)"*.
Measured on the eligibility table it built: the **Amazon and the Sahel both have `n_elig` = 4** (mask
{0,1,2,3}, `w_inherit` 0.5), historically constant. The belief traces to a comment in the probe that conflated
the PFT ids FIT actually *established* at those cells (`{0}` plus grass) with the ids the bioclimatic gate
*admits* — four of them, of which one wins.

Where the regimes actually are, over the **52 451 tree-bearing cells** (2010, `Type ≤ 6`):

| `n_elig` | tree-bearing cells | share | median stems | what it is |
|---|---|---|---|---|
| 0 | 5 882 | 11.2 % | 29 | **pure inheritance** (`w_inherit` = 1) — the qualitatively different regime |
| 1 | **124** | **0.24 %** | 254 | a rare corner, not "the Amazon" |
| 2 | 69 | 0.13 % | 311 | |
| 3 | 11 012 | 21.0 % | 264 | boreal (Siberia) |
| **4** | **25 708** | **49.0 %** | 167 | **the modal cell** (Amazon, Sahel, Iberia) |
| 5 | 3 223 | 6.1 % | 218 | |
| 6 | 6 433 | 12.3 % | 224 | Hainich — a 12 % tail, not a typical cell |

Two consequences. **(a)** The three cells measured in §3 span the modal regime (49 %), the boreal regime
(21 %) and Hainich's tail (12 %) — 82 % of tree-bearing cells by regime, which is why the sign instability is
worth taking seriously rather than treating as three anecdotes. **(b)** The regime where the inheritance
channel genuinely dominates is `n_elig = 0`, **11.2 % of tree-bearing cells**, and it is untested — and those
cells have a median of **29 stems**, so they are also where the C's own noise floor is worst (ADR 0093:
31.6 % on counts below 2 stems/patch). That is the next cell class to measure, and it needs its own noise
floor quoted with it.

---

## 5. Decision

1. **`recruit_establishment` stays OFF by default.** ADR 0119 §6's flip criterion and ADR 0170's two added
   conditions are unchanged and unmet. §3 item 1 strengthens the LEVEL condition from one cell to three.
2. **A THIRD condition is added to the flip criterion, pre-registered here:** the arm must be run at **at
   least one cell per gate regime** (`n_elig` 0, 3–4, 6) with the **artifact pair held fixed and named**, and
   the contribution's **sign must agree across them**. §3 item 2 is the evidence that a single-cell arm cannot
   support a flip decision: the sign reverses under a change of artifact at a fixed cell.
3. **The ssp370 conditioning basis is corrected, gated on both scenarios, and the pre-fix basis is retained
   as a named control** (`BND_FIXTURE` + `SSP_LEAD` + `ALLOW_UNTRAINED_SSP_BASIS`). No published number is
   restated: the arms that produced them are provably blind to the axes that changed (§2).
4. **Do not quote ADR 0170 §2's response signs without "Hainich, demo artifact".** The ADR text stands as
   written; this is a scope narrowing, recorded here and in `docs/decisions/README.md`.
5. **What this does NOT license.** Three cells is not 54 020 (ADR 0106). `trait_mortality` was **off** in
   every arm, so §3 says nothing about the paired flip; ADR 0170 §3 item 3's requirement to run both mortality
   settings is unchanged and still owed by the rung-2 arm raised with line M. The level effect is measured
   against the emulator's own control, **not** against FIT's own per-cell level at these cells — that
   comparison needs the per-cell truth trajectory the offline harness does not carry.
