# 0330 — The structure map run year by year: the pre-registered drift rule fails as written, the error settles at about a second run's; and the structure half costs 7.8e-5 core-s per cell-year

* **Status:** accepted (measurement), 2026-10-12. STATE NEXT items 5 (year-by-year drift test) and 6 (speed, structure
  half). Pre-registration: header of `scripts/explore_panel_yearly_drift.py`, commit a0f2fb37, before any fit.
* **Depends on:** ADR 0316 §11–13 (A7rH), ADR 0318 (relaxed standard; its transient criterion T1 was "not yet defined
  numerically"), ADR 0325 §3 (the daily model's drift rule, mirrored here), ADR 0329 (dense cells defined before the
  run), ADR 0084 / 0086 (the original's cost and its patch-count law).
* **Scripts / data:** `scripts/explore_panel_yearly_drift.py` (`fit --g`, jobs 2467154–58, ~3 min each; `score`) →
  `xpanel/eval/yearly/{preds_<g>.parquet, drift_cases.csv, drift_years.csv, drift_score.txt}`;
  `scripts/explore_panel_lstm.py yearly` (job 2467151) built the missing yearly tables (now 6 runs × 32 legs);
  `scripts/bench_structure_speed.py` (job 2467166, log `logs/bench-structure.2467166.out`).

## 1. The year-by-year test

The best structure arm re-cast in the form an Earth-system model would call each year: the state of year y from the
trailing 30-year climate ending y, a per-year anchor (the training runs' mean over the training legs in year y), the
run's own 2000–2019 levels and the cell. Trained on runs m1, m2, m3, m5, m6 × the 27 legs of the 9 other climate
models, every 4th year; tested on the unseen run m4, every year 2020–2100, for each of the first five climate models
held out (15 cases). Measured: per year, the typical-cell error relative to a second run (`rho50`), dense cells defined
by the anchor (≥ 5 trees per patch). Drift (pre-registered, from the daily model's rule) = mean `rho50` 2081–2100 / mean
2021–2040. Differences from the window arm, stated before the run: no observed-climate control leg, single-year
targets. The observed climate table starts in 2000, so the windows ending 2020–2028 are 21–29 years long (found by the
smoke test; the window means were verified against a direct computation to 0.0).

**Harness and nulls — all as derived before the run** (dense cells, median over 15 cases):

| candidate | tree count `rho50` early → late | drift | expected |
|---|---|---|---|
| another run (m5) scored as the emulator | 0.98 → 1.01 | 1.04 (all six quantities 0.96–1.04) | 0.9–1.1 ✓ |
| mean of the 5 training runs on the same climate (oracle) | 0.79 → 0.79 | 1.00 | ratio ≈ 0.77, drift 0.9–1.1 ✓ |
| the unseen run's 2019 state carried forward (power) | 1.18 → 2.19 | 1.89 (all quantities 1.9–3.0, 15/15 > 1.5) | > 1.2 ✓ — the measure has power |
| the per-year anchor alone | 1.06 → 1.30 | 1.24 | reported |

**The emulator (YA), dense cells:**

| quantity | `rho50` 2021–40 | 2051–60 | 2091–2100 | drift (pre-registered) | cases ≤ 1.2 / > 1.5 |
|---|---|---|---|---|---|
| tree count | 0.92–0.93 | 1.10–1.12 | 1.13–1.21 | **1.17** | 8 / 0 |
| biomass per tree | 0.70–0.72 | 0.97–1.00 | 1.01–1.10 | **1.32** | 2 / 2 |
| wood density (median) | 0.46 | 0.60–0.61 | 0.69–0.70 | 1.36 | 0 / 0 |
| other traits | 0.40–0.60 | — | 0.62–0.85 | 1.43–1.53 | 0 / 3–12 |

(decade columns: the median over the five held-out models, one row per scenario, ranges over the three scenarios.)

**Verdict as pre-registered: FAIL** (tree count 8 of 15 cases ≤ 1.2, biomass per tree 2 of 15; the pass needed 13 of
15 for both and none above 1.5).

**What the numbers say.** The rule compares the end of the century with a start that is BETTER than a second run: in
2021–2040 the emulator knows the unseen run's own 2000–2019 state, so its error is 0.46–0.93 of a second run's. That
knowledge fades over ~30 years, and the error rises to a plateau: biomass per tree reaches ~1.0× a second run by the
2050s and stays there; traits stay below a second run all century (wood density 0.69 at the end). Two signs that this
is the fading start state and not climate extrapolation: drift does not depend on the scenario (tree count ssp126 1.17,
ssp585 1.20; biomass per tree 1.33 / 1.30), and the anchor-only null, which has no start state, rises steadily instead
(biomass per tree to 1.3–1.8). **What remains after the plateau is a slow creep in tree count**: 2051–2060 → 2091–2100
+0.01 (ssp126), +0.07 (ssp370), +0.12 (ssp585) — small, but larger with more warming, so it is the part that could be
real drift. Area totals (dense): tree count 2081–2100 median −0.7 %, biomass per tree −2.5 % (worst UKESM ssp370
−8.1 %).

**Not changed after the fact.** The pass number stays as written and failed. Proposed to the owner (not adopted): for
a map that starts from the run's known state, judge drift after the start state has faded — e.g. 2081–2100 against
2051–2070 — together with the level test (ADR 0318: dense typical ≤ 1.2× a second run; the 2091–2100 tree-count level
1.13–1.21 sits at that line). Descriptively, on that basis (per case) tree count is 0.93–1.10 (median 1.05) and biomass per tree 0.96–1.17
(median 1.05).

## 2. Cost of the structure half (single core, CPU time, per cell-year)

| part | core-s per cell-year |
|---|---|
| yearly climate statistics from one year of daily weather (114 statistics, 1 050 cells; synthetic arrays, branch-free code) | 2.4e-5 |
| 30-year running-window update | 1.8e-7 |
| the structure map, six boosted-tree models × 400 trees (A7rH) | 5.3e-5 |
| **structure half** | **7.8e-5** |
| learned daily water–carbon model, five-seed ensemble (ADR 0323/0324) | 6.4e-3 |
| **sum of the two halves** | **6.5e-3** |

Check that the arm ran (skill speed-gate): the refitted tree-count predictions reproduce the saved run's to 2e-15.
Offline training of the six models: 16 s at 16 threads.

Against the original (ADR 0084/0086, Hainich, one core, marginal rate): 0.267 core-s per cell-year at 25 patches (the
panel's count) → **about 41× less**; ≈ 6.7 at the ~500 patches of publication runs → **about 1 000× less**.
**Caveats, stated:** the total is a sum of separately timed parts, not an end-to-end coupled run (the map from structure
to the daily model's stand inputs does not exist yet; its cost should be of the structure map's order); the original's
cost was measured at one cell; the daily half is 99 % of the bill, so speed work belongs there.

## 3. Not done

* No stand map yet (structure → leaf area, vegetation carbon, cover per plant type): next item, natural form = extra
  targets of this year-by-year arm.
* The year-by-year arm without the start state (to separate memory from climate) was not run.
* Seed 1 of LightGBM only.
