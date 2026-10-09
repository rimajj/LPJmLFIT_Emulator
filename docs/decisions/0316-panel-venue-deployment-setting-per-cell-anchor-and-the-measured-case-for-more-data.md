# 0316 — The panel venue, the deployment setting, the per-cell anchor, and the measured case for more data

* **Status:** **exploratory** (2026-10-09). Line X. Tier-1 block 0310–0329. **Next free number: 0317.**
* **Depends on:** ADR 0315 (the global venue, DP-G1 and its amendments), ADR 0246 (line S's Track-D panel runs),
  ADR 0106 (the acceptance criterion), ADR 0184 (derive what a null must return before the run).
* **Owner, 2026-10-09, verbatim:** *"continue. the goal stays the same. do everything you need to do to reach it.
  including producing more data if that is mandatory and we have solid results that support the assumption that more
  data gives the breakthroug."*
* Scripts: `scripts/explore_panel_prep.py`, `explore_panel_a7.py`, `explore_panel_envelope.py`,
  `explore_panel_lstm.py`, `explore_panel_runs.py`, `explore_glob_a7r.py`. Data: `…/esm_land_emulator_data/xpanel/`
  (derived tables, scores) and `…/xpanel_runs/` (the new runs, §7).

## 1. Why the panel

On Billing's global set the two leading arms failed DP-G1 (a) mainly where the test scenario lay outside the training
scenarios (ADR 0315 §9: the direct map scores 0.162 with ssp370 in training, 0.131 held out). Line S's Track-D panel
(ADR 0246: 1 050 orderA cells = 105 contiguous 10-cell blocks, four independent members, 25 patches, constant CO2,
5 climate models × ssp126/370/585, two constant-climate controls, a per-tree table **every year 2020–2100**) is the data
in which that can be tested with a held-out climate model and a held-out warming amplitude. Nobody had trained on it.

## 2. The venue (`explore_panel_prep.py`, all gates pass)

Members m1–m3 train, **m4 is the truth** (an unseen run), m3 is the replica for the tolerance and the single-run
ceiling. Folds 1–5 by block (21 blocks each, balanced over the 20 climate strata). Per-cell statistics are the ADR 0315
reduction (`living` = trees ≥ 5 m, NPATCH 25). Climate features = the global venue's definitions on the orderA forcing
the runs read. Gates: 1 050 cells; every climate column finite; net longwave negative and humidity 0.67–0.69 on every
leg; the panel's 2000–2019 temperature equals a direct read of the observed file to 4e-9.
The constant-climate control `ctl_obs` draws observed years 1990–2019 with replacement; the drawn sequence was
**recovered exactly** from each member's daily precipitation (difference 0.0 mm on every day; identical across the 105
blocks of a member, different between members; `xpanel/ctl_obs_draws.json`). `ctl_mpi370` wrote no daily output, so
its draws are unknown — used only as a window mean.
Two legs had died of a cluster launch failure (`srun: Socket timed out`), not the model: m3 MPI ssp585 (29/105 blocks)
and m4 UKESM ssp585 (15/105). Resubmitted unchanged (jobs 2451101/03, collectors 2451102/04); until they land those two
legs are absent from every score below.

## 3. First result: the direct map with cells held out fails, and the falsifier fired as written

`explore_panel_a7.py core` (job 2451116; expectations in its header). On a held-out climate model (HG) A7s passes
**0.053–0.088** of cells on ssp370 against a bar of ~0.13, **below the lookup null** (0.058–0.114), totals within 4 %.
E1 failed and the falsifier ("A7s fails on ssp370 for ≥ 3 of 5 models ⇒ the global gap was not extrapolation")
**fired as written.** What the expectation did not anticipate: the split holds out the CELLS as well as the climate
model, so the arm learns place from ~840 cells (global venue ~4 650), while the lookup null reads the same test cells
from other runs.

## 4. The deployment setting, and a per-cell anchor

**The change, stated plainly because it is a change to what the arm may know.** An emulator inside an Earth-system
model is trained on the original's runs of **every** cell, then runs those same cells under a new climate and a new
random draw. Holding out the cell tests a requirement the goal does not have (the acceptance criterion is on the
cells the original was run on). The nulls (`lookup`, `ceiling_mean`) already read the test cells. So the realistic test
holds out the **run** and the **climate model**, not the cell. Thresholds are unchanged; both settings stay reported.
⚠ This is a venue change made after a failure. It was pre-registered in the script header before its own run, and it is
an owner-visible decision: if the emulator must also work on cells the original was never run on, §3 is the binding
number, not §5.

Two one-variable steps: **A7s-seen** (same arm, all cells in training) and **A7r** (+ a per-cell anchor: for each
quantity, the mean over the training runs × training legs of the same cell, leave-one-leg-out in training rows; the
leg's climate minus the anchor legs' climate; the run's own 2000–2019 offset from the training runs' mean; target = value
minus anchor). **A7rcb** is its climate-blind twin.

## 5. Results in the deployment setting — five LightGBM seeds, deterministic row order

**Draw noise, found on the way (job 2451605):** two fits in one process are bit-identical, but polars' `group_by`
emits rows in a different order in each new process, LightGBM's row bagging then draws different rows, and the pass
rate moves by ±0.004. ⚠ **ADR 0315 §8's A7s 0.131 was a favourable draw: its 5-seed mean is 0.126 ± 0.003.** Every
verdict below uses the 5-seed mean, rows sorted.

**Panel, held-out climate model (HG), m4** (`a7_seen_s1..5.csv`):

| test case | A7r | its twin | lookup | ceiling (a second run) | bar = 0.5 × ceiling_mean |
|---|---|---|---|---|---|
| GFDL ssp126 / 370 / 585 | 0.216 / 0.188 / 0.188 | 0.126 / 0.169 / 0.177 | 0.110 / 0.114 / 0.086 | 0.175 / 0.208 / 0.204 | 0.147 / 0.128 / 0.141 |
| IPSL ssp126 / 370 / 585 | 0.182 / 0.162 / **0.124** | 0.163 / 0.121 / 0.062 | 0.125 / 0.106 / 0.080 | 0.181 / 0.183 / 0.198 | 0.130 / 0.134 / 0.134 |
| MPI ssp126 / 370 | 0.155 / 0.163 | 0.099 / 0.162 | 0.099 / 0.102 | 0.167 / 0.179 | 0.127 / 0.124 |
| MRI ssp126 / 370 / 585 | 0.158 / 0.178 / 0.149 | 0.120 / 0.179 / 0.151 | 0.132 / 0.107 / 0.084 | 0.165 / 0.180 / 0.181 | 0.119 / 0.127 / 0.131 |
| UKESM ssp126 / 370 | 0.169 / **0.109** | 0.146 / 0.058 | 0.082 / 0.058 | 0.185 / 0.201 | 0.125 / 0.151 |

* **A7r passes the bar on 11 of 13 test cases** (pre-registered: ≥ 3 of 5 models on ssp370 — held for 4 of 5) and
  beats the lookup on all 13. Seed sd 0.002–0.010. Totals: stems 0.96–1.05, biomass per tree 0.98–1.07 (all within
  ±10 %). On the in-range cases it agrees with the unseen run on **~90 % as many cells as a second run of the original
  does** (e.g. MRI ssp370 0.178 vs 0.180; MPI 0.163 vs 0.179).
* The two failures are the two hottest test cases. UKESM ssp370 (panel-mean 16.4 °C) is warmer than every training leg
  when UKESM is held out; IPSL ssp585 (15.8 °C) is not (UKESM ssp585, 17.1 °C, is in its training) — see §6.
* Response vs the constant-climate control (deattenuated tree-count slope): A7r 0.65–0.77 on ssp370 vs the twin's
  0.31–0.56 — the pre-registered margin > 0.2 holds for 3 of 5 models (IPSL +0.30, MRI +0.20, UKESM +0.38; GFDL +0.18,
  MPI +0.17); on ssp126 the twin is as good or better (weak
  scenarios carry little climate signal). ⚠ The twin is not a zero-response null here: its anchor encodes the average
  future of the training legs.
* A7s-seen vs A7s (cells held out): +0.06 on HG ssp370 (expected ≥ +0.01).
* H585G (ssp585 of the held-out model, no ssp585 at all in training) vs HG (other models' ssp585 in training), on the
  three models with both: pass 0.135 vs 0.154 (−0.019; the pre-registered ≥ 0.02 penalty missed by 0.001), biomass per
  tree +4.4 % vs +3.6 %.

**Global venue, GS370, member 8** (`explore_glob_a7r.py`, job 2451614, `scores_A7r_GS370_mean.csv`; the held-out
scenario is warmer than every training scenario):

| arm | pass (5 seeds) | stems | biomass per tree | tree-count response slope |
|---|---|---|---|---|
| A7s (cells held out) | 0.126 ± 0.003 | 0.98 | 1.12 | 0.63 |
| A7s-seen | 0.139 ± 0.002 | 0.99 | 1.11 | 0.82 |
| **A7r** | **0.140 ± 0.004** | 1.02 | 1.07 | 0.90 |
| A7rcb (twin) | 0.087 ± 0.002 | 0.91 | 1.36 | 0.55 |

DP-G1: (a) **on the bar** (0.140 vs 0.140; not a pass), (b) passes, (c) passes (0.90 vs 0.55), (d) not applicable.
Harness: the re-run A7s seed mean is 2 sd below the stored 0.1307 — recorded as FAIL as written; the cause is §5's draw
noise, not code or data (the inputs and code are unchanged since the stored run).

**A fifth training run on the global venue** (`A7R_TRAIN=2,3,4,6,7`, job 2451988; pre-registered in the script header:
expected +0.005 to +0.01, falsifier < +0.003). Member 7 (the tolerance's replica, same build) joins training; it carries
no information about member 8. A7r **0.1431 ± 0.0034** vs 0.1401 with four runs: **+0.0030** (paired by seed: +0.004,
+0.002, +0.010, −0.005, +0.003). Expectation not met; falsifier exactly at its line — **inconclusive**: this venue
responds weakly to one more run. On these numbers A7r clears DP-G1 (a) by 0.003 (≈ one seed sd), passes (b) (stems
1.012, biomass per tree 1.068) and (c) (0.90 vs the twin's 0.55); (d) does not apply (no stepping). **A marginal pass,
not a robust one.** Harness: the spatial A7s seed mean 0.1285 ± 0.0038 is within 2 sd of the stored 0.1307 (PASS).

## 6. Is it the climate coverage? Two tests

**Cell level, within a test case** (`explore_panel_envelope.py`, job 2451711; harness: recomputed per-cell pass equals
`score()` on every case). A cell is "outside" when its 2071–2100 climate is hotter (mean, warmest, coldest month) or
drier (precipitation, water balance) than every training window of the same cell. Pooled over the 13 cases: A7r reaches
**0.92** of the ceiling inside (11 372 cells) and **0.66** outside (2 164). But within cases the direction holds in only
7 of 13, and the two failing cases are bad **inside** too (0.57, 0.63). Pre-registered E (≥ 0.15 pooled AND ≥ 2/3 of
cases) **failed** on the second condition; the falsifier did not fire. ⇒ the hot test cases are hard for a reason the
per-cell climate range does not capture (the size of the change from the anchor, or a model-specific pattern).

**Data curves** (`explore_panel_a7.py curves_seen`, job 2451628; expectations in the header). A7r, HG ssp370, mean over
held-out models and all combinations:

| more of … | steps | pass |
|---|---|---|
| climate models in training | 1 → 2 → 3 → 4 | 0.114 → 0.137 → 0.148 → **0.162** |
| runs of the original in training | 1 → 2 → 3 | 0.097 → 0.152 → **0.162** |
| the hottest scenario (ssp585) in training | without → with | 0.142 → **0.162** |

**All three pre-registered expectations held:** the last step adds +0.014 (models; bar ≥ 0.005, every held-out model
gains), +0.010 (runs; bar ≥ 0.003), +0.021 (ssp585; bar ≥ 0.01). No curve has flattened. Part of the runs curve is
the anchor becoming less noisy — which is exactly how more runs help this method.

## 7. Decision: produce more panel data (`explore_panel_runs.py`)

Under the owner's instruction above, §6's curves are the solid result that supports it, and the runs are cheap
(~6 core-h per climate leg, ~80 core-h per spin-up; ~1.5 k core-h in total):
* **five more ISIMIP3b climate models** — CanESM5, CNRM-CM6-1, CNRM-ESM2-1, EC-Earth3, MIROC6 — × ssp126/370/585 for
  members 1–4 (orderA forcing by LPJmL's `regridclm`; gate: the ground-truth MPI ssp370 temperature file re-derived
  **byte-identically**, job 2451723);
* **two new independent members, 5 and 6** (own 1000-yr spin-up per block, seeds 5/6), under all 30 climate legs and
  `ctl_obs` (daily precipitation kept so its draws can be recovered).
Same binary snapshot and configuration as line S's campaign; the configuration differs from line S's member-3 file only
in the seed, the restart path and two dropped diagnostic outputs (verified by `cpp` diff); 62 of 62 checkable configs
pass `lpjcheck`. The `ind` writer emits only trees > 5 m (the scored population). Nothing of line S is written; its
restarts, forcing and collector are read or run unchanged. Jobs 2451916–27 (first submitted pinned to one node as 2451818–29; the scheduler put a free node ~3 days out, so they were
resubmitted spread over free cores — the pin matters only for reproducing an existing run row by row). Line S's two dead
legs were resubmitted the same way (2451928/30, both 105/105). The test of the prediction is chained:
statistics 2452216 (after all six collectors) → `explore_panel_a7.py more` with seeds 1–5 (2452217–21).

**Prediction, written before the runs exist:** A7r on the 5 original held-out models' ssp370, trained on the other 9
models and runs m1, m2, m3, m5, m6: mean pass ≥ 0.182 (≥ +0.02 over 0.162), the bar passed on ≥ 12 of 13 HG cases.
**Falsifier:** gain < 0.01 ⇒ the curves saturate here and more panel data is not the lever.

## 8. For the owner — the acceptance criterion, measured

Two independent runs of the original agree on all six quantities in only **17–21 % of cells** (panel and global,
25 patches), and the mean of three runs in 24–30 %. So "everything within 10 % (or the two-run spread) on every cell",
read with the tolerance this venue uses (the spread is the *median* over a density stratum, so a second run fails about
half of the cells per quantity by construction), is not met by **the original model itself**. This record does not
change the criterion (ADR 0106 is owner-owned). It proposes that the owner decide which reading is meant:
(i) per-cell tolerance from the cell's own two-run spread (then a second run passes by construction and the emulator's
target is "as close as a second run"), or (ii) the current stratum-median reading, under which no method, including
the original, can reach "all cells". Numbers to decide with: in-range, the anchored map reaches ~0.9 of a second run's
agreement (§5).

## 9. Not done / open

* **The recurrent arm on the panel** (`explore_panel_lstm.py`, held-out cells, no anchor; 75 fold models, every one beats
  carrying 2019 forward on its validation blocks; scored by job 2451440, harness replay 0.962 with totals exactly 1.000).
  ⚠ A first summary averaged the models and read "totals 2.2×"; per held-out model the picture is two-sided:
  **stable for GFDL, IPSL, MPI** (HG ssp370 stems 0.94–0.98, biomass per tree 1.05–1.08; IPSL ssp585 1.21) and
  **runaway for MRI and UKESM** (stems up to 6–8× — including under the constant-climate control, so a property of
  those fold models' free run, not of the climate), and for three of five H585G fits. Yearly predictions of a stable
  model track the truth decade by decade (GFDL ssp370: total stems 0.94–0.97, biomass 0.97–1.01, 2025–2100).
  Level pass 0.034–0.095 on the scenarios — **below the held-out-cell direct map on all 5 models**; its
  scenario-minus-control tree-count slope (0.38–0.55 where stable) is above that map's for 4 of 5. Within the training
  years (free from 2000, at 2019): stems 0.96, biomass per tree 1.01. The pre-registered falsifier (no pass advantage
  on ≥ 3 of 5 AND no response advantage) did not fire (response half). E1 (scenario-minus-control slope ≥ 0.5 on ≥ 4 of
  5) failed (2 of 5). **Parked**: far behind the anchored map, and half its fits are unstable over 81 free years.
* The per-tree arm is not retried here (ADR 0315 §16.7 stands).
* No global (all-cell) runs under more climate models: §6 measures data value on 1 050 cells; whether the same holds at
  54 020 cells, and what it would cost in disk (the per-tree table dominates), is the next decision, not taken here.

## 10. The more-data prediction, scored (2026-10-10; jobs 2452216–21, `explore_panel_a7.py more`, 5 seeds)

All new legs arrived (m5/m6 present; line S's two dead legs, MPI and UKESM ssp585 of m4, now exist, so there are **15**
held-out-model test cases instead of 13). Mean over LightGBM seeds 1–5 (seed sd 0.004–0.007); seed-mean table
`xpanel/eval/a7_more_mean.csv`. The bar is unchanged (0.5 × mean-of-m1–m3 pass rate AND above the lookup of the same
training set).

| A7r on HG, mean over the 5 held-out models | base (4 models, 3 runs) | mod (9 models, 3 runs) | run (4 models, 5 runs) | both (9 models, 5 runs) |
|---|---|---|---|---|
| pass, ssp126 | 0.175 | 0.188 | 0.183 | **0.193** |
| pass, ssp370 | 0.161 | 0.184 | 0.166 | **0.193** |
| pass, ssp585 | 0.135 | 0.161 | 0.141 | **0.164** |
| lookup of the same training set, ssp370 | 0.097 | 0.108 | 0.098 | 0.108 |
| bar passed, the original 13 cases | 11 | 12 | 11 | **12** |
| bar passed, all 15 cases | 12 | 13 | 12 | **13** |

* **Harness:** `base` re-measures curves_seen's 0.162 as **0.161**.
* **Prediction HELD on both conditions:** `both` − `base` on ssp370 = **+0.033** (≥ +0.02 required; falsifier < +0.01),
  and the bar is passed on **12 of the 13** original cases (≥ 12 required). Per model on ssp370: GFDL +0.034, IPSL +0.029,
  MPI +0.025, MRI **+0.060**, UKESM +0.014.
* **The gain is the climate models, not the runs:** `mod` +0.023, `run` +0.005 (ssp370); the two add nearly linearly
  (+0.028 vs the measured +0.033).
* **The one remaining failure is the hottest held-out case, UKESM ssp370** (0.134 vs bar 0.151; it was 0.120), and its
  ssp585 is far off (0.073 vs 0.143) — UKESM is the warmest model and, held out, lies outside every training model.
* Totals unchanged and fine (stems 0.98–0.99, biomass per tree 1.02–1.03). The ssp370 response slope vs the
  constant-climate control drops slightly with more models (0.72 → 0.67); the climate-blind twin of `both` is 0.37, so
  the margin (0.30) still clears the pre-registered 0.2.

**On the second-run error-ratio measure (ADR 0317; `PRED_SET=<set> explore_tolerance_measure.py`, seed 1, expectations
written in its header before the run).** Ratios of the emulator's per-cell error to a second run's (1.0 = as close as a
second run), median over the five held-out models, ssp370:

| | tree count, typical cell / bad cells | biomass per tree, typical / bad |
|---|---|---|
| lookup null | 1.56 / 2.80 | 1.66 / 1.84 |
| A7r `base` | 1.39 / 2.23 | 1.64 / 1.77 |
| A7r `mod` | 1.35 / 2.02 | 1.43 / 1.77 |
| A7r `run` | 1.41 / 2.21 | 1.58 / 1.73 |
| **A7r `both`** | **1.35 / 2.08** | **1.42 / 1.71** |

Harness (`base` ≈ the earlier HG run): within 0.05 on the all-case medians, 0.07 on one ssp370 centile (biomass per
tree, bad cells) — a different process draws different LightGBM rows (§5). Against the expectation: biomass per tree fell
**−0.22** (≥ 0.05 required: **held**); tree count **−0.04** (≥ 0.05 required: **missed**, but above the 0.02 falsifier).
The traits stay below 1 (0.61–0.87 typical cell). Again the climate models carry it; the two extra runs do almost nothing.

**What it says.** More climate models is a real lever and the panel has not saturated: the pass rate rose by as much as the
whole 1 → 4-model curve had promised, and the biomass-per-tree ratio fell from 1.64 to 1.42. **But it is nowhere near
enough:** at 9 training models the emulator's typical-cell error is still 1.35× a second run's on tree count and 1.42× on
biomass per tree, and 2.1× / 1.7× on the bad cells, against the owner's target of ≤ 1.1–1.2. Even if each further
model helped as much as these five did (data curves usually flatten), biomass per tree would reach 1.2 at ~14 training
models, tree count at ~28 (typical cell) and ~40 (bad cells) — and the panel already uses all ten ISIMIP3b models
(9 in training + the held-out one). So **more data of this kind is necessary but not sufficient**: the arm itself must
improve. The case to price all-cell runs under more climate models (§9) is strengthened on the pass rate, not settled on
the second-run measure. Two extra runs per cell are not worth producing for this arm.
