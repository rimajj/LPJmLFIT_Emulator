# 0317 — Acceptance re-read: "as close as a second run of the original", measured as an error ratio

* **Status:** **Accepted — the TARGET (owner decision, 2026-10-09).** **Proposed — the exact measure and the
  threshold**: both are line X's proposal and wait on the owner's last answer (10 % or 20 %, §5). Line X.
  Tier-1 block 0310–0329. **Next free number: 0318.**
* **Amends:** ADR 0106 §3. ADR 0106 is owner-owned; the owner made the decision recorded here. §1 (fully emulate),
  §2's panel (counts, trait medians AND distributions, under climate change, on ALL cells, both scenarios and the
  response) are unchanged. What changes is **what "within tolerance" means**.
* **Not propagated.** Nothing is written into `MEMORY.md`, `EXECUTION_PLAN.md`, another line's STATE, or
  `~/.claude/CLAUDE.md` (which still carries ADR 0106 §3's default). Propagation is the owner's call (line X rule).
* **Depends on:** ADR 0316 §8 (the question), ADR 0315/0316 (venue, arms, nulls), ADR 0184 (derive nulls first).
* Script: `scripts/explore_tolerance_measure.py` (read-only, ~1 min). Output:
  `…/esm_land_emulator_data/xpanel/eval/tolerance_measure{,_groups}.csv`.

## 1. The owner's words (2026-10-09)

Asked whether the target should be "as close as a second run of the original" (ADR 0316 §8: two runs of the original
agree on all six quantities in only 17–21 % of cells under the current reading):

> "of course. the goal is to be as close as a secodn run of the orignal model. it is even fine if it s worse. find a
> good measure for what is enough in regard of what is possible/ what as achieved in lieterature and what is needed in
> order to couple to a esm. I would be happy if the emolator is not more than 10% worse thatn a second model run of
> the orignal"

and, mid-work: *"but maybe the threshold should be even 20%?? what do you think?"*

## 2. Why the per-cell pass/fail reading cannot be the test

ADR 0106 §3 asked every cell to pass `|E − C| ≤ max(10 %, spread)·C`. Two runs of the original then pass all six
quantities in 17–21 % of cells, because one cell's difference is one random draw. A per-cell yes/no on one draw cannot
separate a good emulator from a bad one. "Within X % of a second run" has to be a statement about the **distribution
of errors over all cells**, compared with the same distribution for a second run.

## 3. The measure

Per cell `c` and quantity `q`, against an unseen run `T` of the original:

* `e_E(c) = |E(c) − T(c)| / |T(c)|` for the emulator, and `e_R(c)` likewise for other runs `R` of the original
  (pooled over all available second runs).
* **Error ratio at centile k:** `ρ_k = P_k[e_E over cells] / P_k[e_R over cells]`, for **k = 50** (the typical cell)
  and **k = 90** (the bad cells; this is where "all cells" is enforced, since a median alone could hide a bad tail).
* The same two ratios on the **climate response** (scenario minus constant-climate control, absolute error), which is
  the climate-change clause.
* Every quantity in ADR 0106 §2's panel, each separately: tree count, biomass per tree, and every reported quantile
  of every trait (the probe below covers the six quantities the arms predict today: count, biomass per tree, four
  trait medians).
* Over **all** tree-bearing cells, **and** within each region / density class (so a bad region cannot hide in the
  global pool).
* `ρ = 1.00` is, by definition, a second run. `ρ ≤ 1 + threshold` is the pass.

**Plus one thing a per-cell ratio cannot see — area totals.** An ESM sees regional and global sums. A coherent bias
of a few per cent passes every per-cell ratio, because per-cell scatter of 6–12 % hides it, but it does not average
out in a sum. A second run's area totals differ by only **0.3 % (stems) and 0.8 % (biomass)** on the panel. "Within
10 % of that" would demand sub-per-cent totals, which no coupling use needs. **Proposed instead:** area totals of
stems and biomass, and of their climate response, within **5 %** per region, plus **no drift** in a free run of
≥ 100 years. Basis: the land models in the Global Carbon Budget disagree on the land carbon sink by 3.2 ± 0.9 GtC/yr
(2014–2023, ±1 sd over ~20 models, i.e. ~28 %), so 5 % is far inside the spread across land models while still
catching a systematic error. This number is line X's proposal, not the owner's.

## 4. Measured on the panel (held-out climate model, truth = run 4, second runs = runs 1–3, 1 050 cells, 13 cases)

**Harness / nulls, all as derived before the run:**

| candidate | expected | measured (median over cases, all six quantities) |
|---|---|---|
| a true second run (run 3 vs runs 1–2) | 0.90–1.10 | **0.95–1.03** (single cases 0.88–1.18, sd 0.05) |
| mean of runs 1–3 of the same climate (oracle) | ≈ 0.82 (Gaussian: √((1+⅓)/2)) | **0.82–0.85** on every quantity |
| lookup (same cell, other climate models) | > 1.2 on most | traits 0.89–1.12; stems **1.52**; biomass per tree **1.66** |

**The current best arm (A7r, ADR 0316, seed 1):**

| quantity | second run's typical error | ρ₅₀ | ρ₉₀ | response ρ₅₀ / ρ₉₀ |
|---|---|---|---|---|
| tree count | 6.4 % | **1.43** | **2.23** | 1.05 / 1.15 |
| biomass per tree | 12.0 % | **1.63** | **1.76** | 1.18 / 0.89 |
| SLA median | 2.2 % | 0.94 | 1.01 | 1.03 / 1.01 |
| wood density median | 3.4 % | 0.69 | 0.68 | 0.81 / 0.81 |
| rooting depth median | 10.0 % | 0.66 | 0.56 | 0.83 / 0.71 |
| water-stress trait median | 3.6 % | 0.72 | 0.64 | 0.86 / 0.78 |

Area totals off by 1.6 % (stems) and 3.2 % (biomass), against 0.3 % / 0.8 % for a second run (inside the proposed 5 %).

**Reading.** The four trait medians are already **better** than a second run (an average-predicting emulator gets
that for free: §5). Tree count and biomass per tree are **40–60 % worse at the typical cell and up to 2.2× at the
bad cells**, and barely better than the lookup null (1.43 vs 1.52; 1.63 vs 1.66). So the arm adds almost nothing
per cell on the demographic quantities. The difference between climate models in a given cell is what is missing.
The old conjunctive pass rate ("~0.9 of a second run", ADR 0316 §5) hid this, because the traits dominated it and
its stratum-median tolerance was loose. **Under the new measure the arm fails, on the two quantities that matter most
for carbon.** That is the binding gap now.

Caveats: one truth run, one seed, panel cells (1 050 of 54 020), six quantities rather than the full panel; the
response test uses the arm's own control prediction.

## 5. 10 % or 20 %? — the answer, and why

**Recommendation: keep 10 % as the verdict, computed on all cells; use 20 % only for single regions/classes.**

1. **The gap between 10 % and 20 % is smaller than it looks.** Our emulator predicts the *average* outcome, not one
   random realisation, so it starts ahead of a second run: a perfect average sits at ρ ≈ 0.71 (0.82 with three
   training runs, measured). For such an emulator with a systematic per-cell error `b` (in units of the original's
   own run-to-run scatter σ), ρ ≈ √((1 + b²)/2). **10 % allows b up to 1.19 σ; 20 % allows 1.37 σ** (1.04 σ / 1.24 σ when the average itself is estimated from three runs). Both already
   tolerate a systematic error larger than the original's own noise; 20 % adds only ~0.2 σ.
2. **The real reason to want 20 % is measurement noise, and it disappears with enough cells.** On 1 050 cells with one
   truth run, a genuine second run scores 0.88–1.18 (sd 0.05). It would fail a 10 % line on 13 % of checks and never
   fail a 20 % line. Over all 54 020 cells that noise shrinks roughly as 1/√cells (sd ≈ 0.01), so 10 % is cleanly
   testable for the global verdict. A single region of ~1 000 cells is as noisy as the panel, so there 20 % is the
   honest line. Alternatively, set the regional line from that region's own second-run scatter.
3. **Literature agrees on the reference, not on a number.** Nobody publishes a "10 %" or "20 %" rule. What is
   established is the yardstick: climate-model emulators are scored against the spread between ensemble members
   (ClimateBench, Watson-Parris et al. 2022), and an average-predicting emulator can and does beat that spread. Many
   ensemble members are needed to benchmark at all (Lütjens et al. 2025: with 3 members, internal variability skews
   rankings; they moved to 50). Model-port verification asks "statistically indistinguishable from an ensemble of the
   original" (CESM ensemble consistency test, Baker et al. 2015). So "≤ X % worse than a second run" is in line with
   the field, and the choice between 10 and 20 is the owner's.
4. **What an ESM needs is not the binding part.** The original's run-to-run scatter per cell (6 % stems, 12 %
   biomass per tree) is far below how much land models disagree with each other (~28 % on the land sink). Either line
   is comfortably good enough for coupling **as long as totals carry no coherent bias and nothing drifts**. That is
   why §3 adds the totals and the drift check.

## 6. What this changes, and what it does not

* The acceptance verdict becomes: every quantity of ADR 0106 §2, both scenarios and the response, **ρ₅₀ and ρ₉₀ ≤ 1.10
  over all cells, ≤ 1.20 in every region / density class (≥ ~1 000 cells), plus area totals within 5 % and no drift.**
  Pending the owner's final word on the two thresholds.
* Requires ≥ 2 runs of the original on every scored cell (one as truth, the rest as the second-run reference). Billing's
  global set has 6–8 runs per build; the panel has 4, soon 6.
* DP-G1 and the panel bar (0.5 × the mean-of-runs conjunctive pass rate) are round-1 screens and stay as they are
  until the owner adopts this; new results should report **both**.
* The "17–21 % of cells" figure is retired as an acceptance number. It remains a fact about the old reading.

## 8. Measured on the global venue (2026-10-09, addendum; `scripts/explore_glob_tolerance.py`, job 2454951)

Venue ADR 0315 GS370 in the deployment setting of ADR 0316 §5: one climate model (GFDL-ESM4), cells seen in training,
the scenario (ssp370) and the run (member 8) held out; 5 809 tree-bearing dev cells; second runs = Feb-build members
2,3,4,6,7. A7r is reported as the mean over LightGBM seeds 1–5 (seed sd 0.01–0.09). Predictions were committed before
the run (d7742c14).

| candidate | tree count ρ₅₀ / ρ₉₀ | biomass per tree ρ₅₀ / ρ₉₀ | traits ρ₅₀ (4 medians) | totals off: stems / biomass |
|---|---|---|---|---|
| a second run (member 7, harness) | 1.02 / 1.00 | 1.02 / 1.00 | 0.98–1.04 | 0.2 % / 0.2 % |
| mean of 5 runs (oracle) | 0.78 / 0.80 | 0.80 / 0.78 | 0.79–0.82 | 0.1 % / 0.4 % |
| lookup null (ssp245, mean of 4 runs) | 1.52 / 2.34 | 1.84 / 1.93 | 0.87–1.02 | 4.6 % / 15.0 % |
| **A7r, 4 training runs** | **1.44 / 3.62** | **1.96 / 2.75** | 0.59–1.05 | 1.5 % / **8.1 %** |
| A7r, 5 training runs | 1.44 / 3.59 | 1.95 / 2.80 | 0.59–1.05 | 1.2 % / 8.1 % |
| A7rcb (climate-blind), 4 runs | 1.97 / 2.69 | 2.68 / 2.80 | 0.55–0.98 | 8.9 % / 23.5 % |

Against the predictions: harness **held** (0.96–1.04); oracle **held** (0.77–0.85 vs 0.77); lookup **held** (tree count
1.52, biomass 1.84 > 1.2); climate-blind worse on the response **held** (tree-count response 1.66 vs 1.39).
**"The global venue is easier than the panel" is FALSIFIED** (tree count ρ₅₀ 1.44 ≥ the 1.43 falsifier; biomass per
tree 1.96 vs the panel's 1.63). The fifth training run moved ρ by ≤ 0.02 — inside the predicted 0.00–0.10, at its floor.

What it says:
1. **The best arm is not as close as a second run on tree count or biomass per tree, on either venue**, and on this
   venue it is **worse than the lookup null on biomass per tree** (1.96 vs 1.84 at the typical cell) and on the bad
   cells for tree count (3.62 vs 2.34). Its area-total biomass is 8 % off, outside the proposed 5 % line.
2. **The failure is concentrated in sparse cells.** Tree count ρ₅₀ by the truth's density: 6.4 (< 2 trees per patch,
   863 cells), 3.2 (2–5), 1.14 (5–10), 1.67 (10–20); a second run is 0.92–1.07 in every class. Biomass per tree is
   2.5–4.5 outside the 5–10 class.
3. **Traits below 1 are mostly averaging, not skill**: the lookup null, which knows nothing about ssp370, already
   reaches 0.87–1.02, and the mean of runs 0.79–0.82. A7r's 0.59–0.70 on rooting depth and wood density is better than
   both; its SLA (1.05, ρ₉₀ 1.15–1.22) is not.
4. **More runs of the same design do not move it** (4 → 5 runs: ≤ 0.02). This venue's limit is the arm, not the data.
   That does not prejudge the panel's more-data test (ADR 0316 §7), which adds climate models, not runs.
5. Hypothesis for the biomass-per-tree miss, **not yet tested**: the anchor averages the historical window with two
   future ones, while biomass per tree keeps rising through the century, so the anchor sits low and the learned
   correction does not close it. The cheap test is an anchor built from the future legs only, pre-registered first.

## References

* Baker, A. H. et al. (2015), *A new ensemble-based consistency test for the Community Earth System Model (pyCECT
  v1.0)*, Geosci. Model Dev. 8, 2829–2840, doi:10.5194/gmd-8-2829-2015.
* Watson-Parris, D. et al. (2022), *ClimateBench v1.0*, J. Adv. Model. Earth Syst. 14, e2021MS002954.
* Lütjens, B. et al. (2025), *The impact of internal variability on benchmarking deep learning climate emulators*,
  J. Adv. Model. Earth Syst., doi:10.1029/2024MS004619.
* Friedlingstein, P. et al. (2025), *Global Carbon Budget 2024*, Earth Syst. Sci. Data 17, 965 (land sink 2014–2023,
  3.2 ± 0.9 GtC/yr from ~20 land models).
