# 0172 — The recruit arm at FIVE cells: the level shift is confirmed and still blocks the flip; the response contribution disagrees between cells *within one eligibility regime*, so ADR 0171 §5's flip condition is grouped on the wrong variable — and ADR 0171 §4's own regime table means something different from what it says

* Status: accepted
* Date: 2026-08-12
* Line: S (tier-3 block 0170–0189)
* Supersedes: nothing. **Replaces ADR 0171 §5's third pre-registered flip condition** (measured, not argued:
  the grouping it conditions on does not organise the quantity it conditions). **Corrects the reading of
  ADR 0171 §4's regime table** (its `n_elig` is a 20-year minimum, not the 2010 snapshot its header implies)
  and gives that table its first committed reproducer. Extends ADR 0170 (the arm), ADR 0119 §6 (the flip
  criterion), ADR 0101 (one run is not a measurement), ADR 0093 §3c (the noise floor by stem density).
* Reproduce (each `40` seeds, ~2 min/job, `ARM=recruit MODE=response TRAIT_MORT=0 K_CAP=400
  SCORE_WINDOW=20`, artifact pair `drf_forest_global_pooled_w20_t8.drf` +
  `recruit_copula_global_pooled_w20_t8.rcop`):
  `SITE=semiarid_sahel scripts/run_response_seed_ensemble.sh S-rbSAH 40` (jobs 1762007–1762047) ·
  `SITE=mediterranean_iberia … S-rbIBE 40` (jobs 1762048–1762088). Prerequisites, both cells:
  `SITE=<name> python3 scripts/build_hainich_response_forcing.py`; `CELLS=18371,33335 GATE=0` +
  `SCENARIO={historic,ssp370}` `scripts/build_estab_eligibility.py` (jobs 1761997/1761998), split with
  `scripts/split_estab_eligibility_percell.py`; appended with
  `scripts/append_response_ensemble_reference.py`. Statistics:
  `python3 scripts/score_recruit_crosscell_heterogeneity.py`. Regime table:
  `scripts/sbatch_python.sh S-regime scripts/build_estab_regime_table.py` (job 1762319). Per-seed record:
  `test/testitems/references/S_recruit_multicell_seed_ensembles.csv` (7 ensembles, 280 rows).

---

## 0. Reconciliation with the ADR this extends (the panel every extension opens with, ADR 0116 §4)

ADR 0171 measured the recruit arm at three cells on the pinned `pooled_w20_t8` pair and found: the **level**
effect survives everywhere (+2.20 / +4.93 / +5.00 %), the **response contribution's sign** does not (−0.89 /
+1.98 / −1.91 ×FIT, and +3.41 → −0.89 at a fixed cell when the artifact pair changes). It pre-registered a
third flip condition — *"one cell per eligibility regime, artifact fixed and named, sign must agree"* — and
named the untested `n_elig = 0` regime, *"11.2 % of tree-bearing cells, median 29 stems"*, as the next class
to measure.

This ADR adds the two remaining provisioned cells, making five. **The level finding is confirmed and is now a
five-cell result.** The response finding is sharpened in a way that invalidates ADR 0171's own flip condition
rather than satisfying it: with three cells inside the *same* eligibility regime, they disagree beyond seed
noise, so "sign must agree within a regime" cannot be met and, more importantly, is conditioning on a
variable that does not organise the effect. And building the reproducer for ADR 0171 §4's regime table showed
the table classifies cells by a 20-year **minimum**, not by the snapshot its header names — which changes
which cells the "11.2 %" refers to by a factor of about three. No code changed; no default moved;
`recruit_establishment` stays **OFF**.

---

## 1. The five-cell table, pinned artifact, 40 seeds each, 200/200 usable rows

All five ensembles ran with zero hard kills, zero count overrides and zero k-cap merges (the ADR-0048/0101
usability preconditions), so nothing is excluded. `n_elig` is that cell's historic modal eligible-PFT count
from its own committed series. Contribution = the 2×2 double difference (arm − control, ssp − historic),
in units of FIT's own +2432.9 gC/m³ per-cell wood-density shift (ADR 0046 §1).

| cell | `n_elig` | level effect, historic | as % of the control's level | baseline `R_ctl` ×FIT | contribution ×FIT | resolved? |
|---|---|---|---|---|---|---|
| temperate_hainich (42490) | 6 | +5 164 gC/m³ | **+2.21 %** | +0.272 ± 0.135 | **−0.894 ± 0.323** | yes |
| tropical_amazon (12045) | 4 | +10 117 | **+5.02 %** | +0.297 ± 0.408 | **+1.979 ± 0.930** | yes |
| boreal_siberia (52059) | 3 | +10 749 | **+5.09 %** | **+1.941 ± 0.210** | **−1.905 ± 0.532** | yes |
| semiarid_sahel (18371) | 4 | +23 406 | **+7.14 %** | +0.732 ± 0.740 | −1.667 ± 1.310 | **NO** |
| mediterranean_iberia (33335) | 4 | +21 581 | **+8.28 %** | −0.018 ± 0.755 | **+3.563 ± 1.469** | yes |

Both new cells' prerequisites passed their gates exactly: the historic **and** ssp370 transient boundaries
reproduce the trained global table for the run's own cell at **worst |diff| = 0**, and the 2010 daily forcing
reproduces each cell's committed fixture to ≤ 1.8e-05.

---

## 2. THE LEVEL EFFECT IS THE ROBUST FINDING, AND IT IS WHY THE FLIP STAYS REFUSED

At every one of the five cells the ported establishment rule raises the standing community's mean wood
density against a matched control under identical forcing, by **+2.21 % to +8.28 %** (t = 6.1–7.9;
+5 164 to +23 406 gC/m³). Expressed against the quantity the acceptance criterion cares about, that is a
static offset of **2.1× to 9.6× FIT's entire historic→ssp370 warming shift**, present with no climate change
at all. ADR 0106's tolerance is 10 % on trait medians; a systematic offset of this size on the axis
ADR 0046 fingerprinted as the selection signal is a level defect, and the two new cells are the two largest
offsets measured so far. `recruit_establishment` stays **OFF** — now for five cells rather than three.

Note what this is measured against and what it is not: the control is *the emulator's own* copula-driven
recruit channel under the same forcing, not FIT's per-cell level. This is a controlled contrast between two
recruit models, not a fidelity statement about either (guardrail 6; 5 of 54 020 cells).

---

## 3. THE FINDING THAT CHANGES A PRE-REGISTERED CONDITION: same regime, different answer

Three of the five cells — Amazon, Sahel, Iberia — sit in the **same** eligibility regime (`n_elig = 4`, the
modal class at 49 % of tree-bearing cells, `w_inherit = 0.5`). If the regime set the response, they should
agree. They do not:

* **Cochran's Q on the contribution, within `n_elig = 4` only: Q = 8.03, df 2, p = 0.018, I² = 75.1 %.** The
  between-cell spread is larger than 40 seeds of within-cell noise can produce.
* Pairwise (Welch): Amazon vs Sahel **differ** (Δ = +3.65 ×FIT, p = 0.023); Sahel vs Iberia **differ**
  (Δ = −5.23, p = 0.008); Amazon vs Iberia not resolved (p = 0.36).
* Across all five cells: contribution Q = 22.58, df 4, **p = 1.5e-04**, I² = 82.3 %.

**⇒ ADR 0171 §5's third condition — "one cell per eligibility regime, artifact fixed and named, sign must
agree" — is retired.** It is unsatisfiable, but the reason matters more than the fact: it groups on a
variable that does not organise the quantity being tested. Replacement, pre-registered below.

### 3a. The contrast that makes this a property of the PORT, not of the harness

The same test on the **shipped** channel's own warming response (`R_ctl`) within the same three cells finds
**no heterogeneity at all: Q = 0.51, df 2, p = 0.77, I² = 0.0 %** — one common effect of +0.322 ×FIT is not
excluded. So the eligibility regime *does* organise the copula channel's response across these cells, and
does *not* organise the ported rule's contribution. Whatever cell-level structure the ported rule is
responding to, it is not the bioclimatic eligibility gate — which is the one cell-level input the port adds
over the copula. That is a falsifiable pointer for any future attempt: the mechanism to look for is in the
**seedbank** (the cell's own biggest trees, i.e. the emulator's own state — the feedback loop ADR 0025 §4
excluded on principle and ADR 0118 §5 flagged as this port's replacement risk), not in the gate.

### 3b. One cell is honestly unresolved, and it is reported as such rather than as a zero

The Sahel's contribution is **−1.667 ± 1.310** (95 % half-width 2.57 ×FIT) — it does not exclude zero, and
resolving its point estimate at 80 % power would take **≈ 194 seeds**, not 40. ADR 0170 §2's lesson applies
in the other direction here: a non-significant arm is not an inert one, and it must not be read as agreeing
with either sign. The heterogeneity result above does not depend on it — Amazon vs Iberia alone would not
have shown disagreement, but Sahel vs Iberia does, and Q uses all three with their own precisions.

### 3c. The pooled number, with the caveat that makes it almost unquotable

The inverse-variance weighted mean contribution over the five cells is **−0.805 ×FIT** against FIT's +1, i.e.
pooled across cells the ported rule moves the warming response the *wrong way*. With I² = 82 % a
fixed-effect pooled mean is not a meaningful summary of five disagreeing cells and **must not be quoted as
"the port's response"**. It is recorded only because someone will otherwise compute it and quote it without
the I².

---

## 4. ADR 0171 §4's REGIME TABLE SAYS SOMETHING DIFFERENT FROM WHAT IT MEANS — and now has a reproducer

ADR 0171 §4 published a regime table over *"the 52 451 tree-bearing cells (2010, `Type ≤ 6`)"* with **no
committed reproducer** — the same defect ADR 0118 decision 5 had recorded against ADR 0093 §5.3 one day
earlier, in a new place and by this line. `scripts/build_estab_regime_table.py` is that reproducer, and
writing it to gate against the published numbers is what exposed the following.

**The cell universe reproduces exactly (52 451). The classification does not: it is the MINIMUM of `n_elig`
over the 20 historic years, not the 2010 snapshot the header names.** Gated:

| classification of the same 52 451 cells | `n_elig = 0` cells | share | median stems/cell |
|---|---|---|---|
| **min over 2000–2019** (ADR 0171 §4's actual basis — now gated) | **5 882** | **11.21 %** | **29** |
| the 2010 snapshot (what its header reads as) | 1 931 | 3.68 % | 24 |

Under the minimum, `n_elig = 0` means *"the bioclimatic gate is closed in at least one of twenty years"* —
not *"this cell is in the pure-inheritance regime"*. Persistence, on the cells the pinned artifact can
actually be run at (53 607 with a trained row in both scenarios):

| the gate is closed in … | cells | share | median stems/cell | gate opens under ssp370 |
|---|---|---|---|---|
| **all 20 historic years** | **739** | **1.4 %** | **25** (= 1 stem/patch) | 635 of 739 |
| 10–19 years | 1 587 | 3.0 % | 37.5 | 1 584 |
| 1–9 years | 4 479 | 8.4 % | 25 | 4 479 |
| never | 46 802 | 87.3 % | 175 | — |

**Two consequences for ADR 0171's handoff item 2.** (a) The persistent pure-inheritance regime is **1.4 %,
not 11.2 %** — the 11.2 % is a dip-into-it-once class of which 87 % of members have an open gate in most
years. (b) The persistent class sits at a **median of one stem per patch**, i.e. entirely inside ADR 0093
§3c's `< 2 stems/patch` stratum where the C's own two-run spread is **31.6 % on counts / 42.7 % on carbon**.
Of its 739 members only 2 reach `n_init = 18`; 502 of 739 are at `n_init = 1`. And of the 104 cells whose
gate is closed in *both* scenarios' every year, the maximum `n_init` is **3**.

⇒ **a 40-seed response arm at a persistently-closed cell would be measuring dice, and this ADR does not run
one.** That is a measured decision, not a deferral: §3b already shows 40 seeds leaving a 4.2-stem/patch cell
(Sahel, `n_init = 11`) unresolved at ±2.57 ×FIT; a 1-stem/patch cell is strictly worse conditioned. The
regime remains untested and the honest statement of why is now on the record, with the cell counts that make
it checkable.

---

## 5. Decision

1. **`recruit_establishment` stays OFF.** The five-cell level effect (§2) is the blocking evidence.
2. **ADR 0171 §5's third flip condition is REPLACED** by the following, pre-registered here:
   * **arm** — the recruit arm (`ARM=recruit MODE=response`, mortality setting held common and stated) on a
     **named set of ≥ 12 cells drawn across the `n_elig` classes, each with ≥ 40 seeds and each cell's own
     `n_init` reported**, artifact pair fixed and named.
   * **pass condition** — (i) the inverse-variance weighted mean contribution over those cells is within
     **[0.9, 1.1] ×FIT**, **and** (ii) **Cochran's Q over the cells is not significant at p < 0.05** (i.e.
     the cells agree, rather than averaging to the right answer by cancellation), **and** (iii) the level
     effect of §2 is within ADR 0106's 10 % band at every cell in the set.
   * **why the Q clause is load-bearing** — without it, five cells spanning −1.9 to +3.6 ×FIT could pool to
     +1.0 and be reported as a pass. This is ADR 0113 §3's lesson (a statistic three very different arms all
     score alike has no power) applied before the fact rather than after.
   * **do NOT** substitute a per-regime cell for the ≥ 12-cell set: §3 measures that the regime does not
     organise the effect.
3. **The `n_elig = 0` regime is formally descoped for the OFFLINE arm**, with §4's stem-count evidence as the
   reason. If it is ever wanted, it needs either a cell with `n_init ≥ 5` and a persistently closed gate
   (30 of 739 exist) or ≈ 200 seeds, and its noise floor must be quoted beside it.
4. **`test/testitems/references/S_estab_regime_table.csv` is the committed regime table**, carrying both
   classifications and both cell bases; ADR 0171 §4's numbers are reproduced under the min-over-window
   classification and that classification must be named whenever the 11.2 % is quoted.

---

## 6. What is NOT claimed

* Nothing here is fidelity evidence. Five cells of 54 020; `trait_mortality` off in every arm; the level
  effect is measured against the emulator's own control, not against FIT's per-cell level (guardrail 6).
* §3a's pointer at the seedbank is a **direction**, not a measurement: this ADR shows the gate does not
  explain the heterogeneity, not that the seedbank does.
* The response contributions in §1 are for **one artifact pair**. ADR 0171 §3 measured that the pair alone
  can flip a sign at a fixed cell (+3.41 → −0.89 ×FIT at Hainich), and the demo-pair rows are excluded from
  every statistic in §3 for exactly that reason.
* The rung-2 arm raised with line M (ADR 0170/0171) is unaffected and still owed by M. Offline results cannot
  settle it — §3 is a further reason why, not a substitute.
