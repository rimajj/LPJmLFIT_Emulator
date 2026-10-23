# 0369 — Three follow-ups of the transformer experiments: is the memory gain just a description of the place, can the deployed daily network carry the memory cheaply, and does a per-tree carbon state catch the die-offs? (pre-registration, SEPARATE EXPERIMENT)

* **Status:** pre-registered 2026-10-23, before any fit of this record. Results: §6, added after the runs. **A: the place explains PART of the memory gain (56–91 %). B: no cheap-memory network passes (single-year errors −10 %, 30-yr gains within seed noise), cost 1.4–1.7e-3 core-s/cell-year; die-offs unchanged. C: the true per-tree carbon state reaches die-off capture 0.51 (bound), the deployable route 0.28–0.29 — not worth a free-running test.**
* **SEPARATE EXPERIMENT — nothing of it enters the paper or the release package** (owner 2026-10-23 for the
  transformer experiments of ADR 0368, which this record continues). Code: `scripts/xtf_daily.py` (new arms),
  `scripts/xtf_tree_pairs.py` (tables v2 with the carbon state), `scripts/xtf_tree_models.py` (new arms),
  `scripts/xtf_tree_carbon.py`; data under `esm_land_emulator_data/xtf/`.
* **Owner instruction (2026-10-23), verbatim:** *"Place test: check whether "describing the place" explains the memory
  gain. That's a few GPU-hours and stays cheap if it works. Cheap memory: carry weather memory cheaply in the deployed
  daily network, using learned running averages or a small network that updates its memory once a day. Per-tree
  carbon state: the leaf-carbon and bad-years sub-model you parked on 21 October, which the tree-death results point
  to. Stop here."*
* **Data, splits, scorers:** exactly those of ADR 0368 (clustered nitrogen-on runs, 674 cells, 135 held-out; 8
  training / 2 held-out climate models; free runs on members 2 and 3 of the 30 rising-CO2 legs; scored as typical
  error ÷ a second run's; the decision group is held-out cells × held-out climate models). Judged on the clustered
  runs only (owner, 2026-10-23); no full-grid run.

## 1. Experiment A — place test

ADR 0368 §7.1a: the transformer over the past year of raw weather (TW) beat the same transformer without it (TC) by
20–30 % on each cell's level, but not on the year-to-year departures. Hypothesis: the past year mostly tells the
network WHERE it is (seasonal cycle, variability), not what happened recently.

* **TP** = TC + a fixed description of the place in its state token: the mean seasonal cycle (12 equal bins of the
  year) of temperature, log(1 + rain), shortwave and net longwave + the SD of their daily values (52 numbers), from the
  leg's own forcing 2020–2049, fixed for the whole run. (It peeks at the first 30 years of the leg; it carries no
  information about any particular recent day. An ESM would take it from an observed climatology.) 3 seeds, training
  and free runs exactly as TC.
* **Gain share** g = (TC − TP) / (TC − TW), seed means, on the single-year ratio and on the late (2071–2100) 30-year
  ratio, per flux.
* **Decision:** place **explains the memory gain** if g ≥ 0.75 on both statistics for at least two of NPP, ET, runoff;
  place **explains none of it** if TC − TP ≤ B's seed spread on both statistics for at least two of the three;
  otherwise **partly** (g reported). The year-to-year departure correlation (`xtf_daily_anomaly.py`) reported beside.

## 2. Experiment B — cheap memory in the deployed daily network

Same MLP as the deployed members (256 × 3, SiLU, same head, loss, data, 40 M samples, 10 epochs, one-cycle Adam 3e-3,
fp32, no gradient clipping — `f2_train.train`'s settings), inputs = B's input vector + extras:
* **MR** — no extras: B retrained in this script (pipeline control; the baseline of this experiment).
* **MP** — + the place description of §1 (52).
* **ME** — + a bank of exponential running means (learned running averages: the network learns how to weight 8 time
  scales 3, 7, 15, 30, 60, 120, 240, 480 days of the four weather variables; 32 numbers, each updated once a day by
  m ← m + (x − m)/τ, started at the 2019 warm-up year's mean).
* **MM** — + the past 12 months as 30-day means of the four variables (48 numbers; a 360-day ring updated once a day).
* **MEP**, **MMP** — ME / MM + the place description.
3 seeds each. Free runs, scorer and drift rule as ADR 0368 §1a. One-core cost measured with the extras' own daily
update included (the bench checks the online update against the free-run inputs).

* *Spread* s = max(B's, MR's) seed spread of the statistic.
* An arm **carries memory cheaply** if it beats MR's seed mean by more than s on the single-year AND the late 30-year
  ratio for at least two of NPP, ET, runoff, with |drift − 1| not worse than MR's by more than s, AND its one-core
  cost is ≤ 2× B's (≤ 2.6e-3 core-s per cell-year on the bench of ADR 0368).
* The **chosen** arm: among qualifying arms the one with the lowest NPP single-year ratio; if none qualifies, the arm
  with the lowest NPP single-year ratio is still re-scored below (owner asked for the re-score), labelled
  "not qualifying". Reported: the share of TW's gain it keeps, (MR − arm) / (MR − TW).
* **Die-off re-score:** STC&lt;arm&gt; = ADR 0368's STCe with the chosen arm's cell NPP/GPP (mean of its 3 seeds' free
  runs; STCe used 5 B seeds, so the comparison slightly favours B), 2 seeds. Reading: the cheaper memory helps the
  die-offs if capture ≥ STCe + 0.03. Also STK&lt;arm&gt; of §3.
* Nothing changes in any release here. A qualifying arm becomes a release candidate in a new record (scored in the
  complete emulator on the emulated stand, as ADR 0367).

## 3. Experiment C — per-tree carbon state

ADR 0368 §7.2b: the year's carbon balance explains about half of the missing die-off signal; the rest is what the
original tracks per tree. The merged model's hard kills (`mortality_tree_ind.c`): leaf carbon below a sapling's
(`ghost tree fix`) and the bad-years counter reaching 10 (`BM_INC_COUNTER_MAX`; +1 in a year whose biomass increment
after turnover is negative, else reset).

**The state is exact from the `ind` table** (tables v2, `xtf_tree_pairs.py`; checked before this record on one leg,
gfdl-esm4 ssp126 seed 2): r = leaf carbon / a sapling's from LAI, `fpc_ind`, SLA and the type's allometry; the counter
c = the run of consecutive bad years along the tree's own history, a bad year being exactly mort_npp / mort_max > 1/1.2
(the growth-efficiency factor crosses 1/1.2 when the increment changes sign). Every bad-year row's c lies inside the
interval its own `mort_npp` allows (100 %); 98.6 % of the leg's 9 137 hard kills have r < 1 or c ≥ 10 (46 % / 54 %),
and all 9 177 trees with r < 1 or c ≥ 10 die. (A one-row inversion is ambiguous above c = 5 — found and fixed before
this record.)

* **Carbon-state model CS** (set transformer as ST, 3 outputs: next year's log r, P(bad year), P(r < 1)), inputs =
  the tree at y−1 + its r and c at y−1 + the cell inputs + the year's cell NPP/GPP and departures. Variants **CSc**
  (the original's cell carbon — isolates the daily model) and **CSe** (the deployed daily networks' — deployable),
  cross-fitted: the training cells split in two folds by cell, each fold's rows predicted by the model of the other
  fold, the validation and held-out cells by the mean of both, so the death models never train on in-sample
  predictions.
* **Death arms** (ST architecture and training, 2 seeds each, teacher-forced one year ahead as ADR 0368):
  * **STK** — ST + r and c at y−1 (deployable if the emulator carries them per tree).
  * **STKt** — STK + the true r, bad-year flag and c of year y (bound: a perfect carbon-state model).
  * **STKCe** — STK + the deployed daily networks' cell carbon (= STCe + state; control for the next one).
  * **STKe** — STKCe + CSe's three predictions (the deployable carbon-state route).
  * **STKc** — STK + the original's cell carbon + CSc's predictions (the same route with a perfect daily NPP).
* **Decision** (held-out cells × held-out climate models; ST 0.531 skill / 0.235 capture, STCe 0.539 / 0.265):
  * the per-tree carbon state **carries the die-off signal** if STKt reaches die-off capture ≥ 0.5;
  * the state alone helps if STK − ST ≥ 0.03 capture;
  * the carbon-state route is **worth a free-running test** (a new record) if STKe's capture ≥ STCe + 0.05 with skill
    ≥ STCe's and a 30-year death-rate ratio not worse than STCe's by more than 10 %;
  * the carbon-state model adds beyond feeding its inputs if STKe − STKCe ≥ 0.03;
  * reported either way: the share of the bound it keeps, (STKe − ST) / (STKt − ST), and the daily model's limit
    STKc − STKe.

## 4. What this record does not do

No change to any release, no free-running tree model, no full-grid run, nothing in the paper. Experiment C is
teacher-forced: each year starts from the original's own trees and their true state at y−1.

## 5. Amendments (all before any score of the arm they touch)

* **Tables v2, zero-leaf trees:** 671 rows per leg have LAI 0 in the death year (leaf margin 0/0 = NaN); the loader
  sets their log margin to the floor log(1e-3) instead of letting `nan_to_num` turn it into margin 1. Found on the
  first built table, before any carbon-state fit.
* **Bench:** the smoke-test costs (MMP 6.5e-3, MEP 4.3e-3) timed the one-off set-up of the online extras (30-year
  place description, warm-up of the running means) inside the timed loop, and the 12-month blocks were re-averaged
  over the whole ring each day. Fixed before the real bench: set-up outside the loop, 12 running block sums
  (2 × 48 additions per cell per day), checked against the free-run inputs. The first real bench failed (`taskset`
  to a core outside the allocation) and was rerun with one thread.
* **Smoke-test outputs** (`*_s99` daily runs, `STKe_s9` / `STKt_s9`) deleted before scoring.

## 6. Results (2026-10-23)

Decision group = held-out cells × held-out climate models (IPSL, MPI), seed means; ratio = typical error ÷ a second
run's. Files: `xtf/daily/score_summary.csv`, `anomaly.csv`, `logs/xtf-369bench.2696298.out`,
`xtf/treemort/score.csv`, `logs/xtf-369tscore.2693630.out`, `logs/xtf-369mep.score.2696305.out`;
`scripts/xtf_0369_decide.py` applies §1–3.

### 6.1 Daily networks

| arm | NPP single-yr | NPP 30-yr late | ET single-yr | ET 30-yr | runoff single-yr | runoff 30-yr | GPP single-yr | NPP departure r | one-core cost (core-s / cell-yr) |
|---|---|---|---|---|---|---|---|---|---|
| B deployed (5 seeds) | 1.82 | 2.05 | 1.71 | 2.39 | 8.28 | 5.41 | 1.30 | 0.72 | 1.30e-3 |
| MR retrained control | 1.81 | 2.06 | 1.71 | 2.35 | 8.18 | 5.29 | 1.31 | 0.71 | 1.50e-3 |
| MP + place | 1.71 | 1.83 | 1.78 | 2.55 | 8.03 | 5.54 | 1.26 | 0.75 | 1.42e-3 |
| ME + running-mean bank | 1.64 | 1.75 | 1.50 | 2.08 | 7.74 | 4.90 | 1.22 | 0.77 | 1.57e-3 |
| MM + past 12 months | 1.63 | 1.75 | 1.60 | 2.19 | 7.92 | 4.96 | 1.20 | 0.75 | 1.75e-3 |
| **MEP** bank + place | **1.63** | 1.89 | 1.53 | 2.10 | 7.72 | 4.94 | 1.17 | **0.81** | 1.53e-3 |
| MMP 12 months + place | 1.66 | 1.83 | 1.67 | 2.32 | 7.87 | 5.43 | 1.22 | 0.74 | 1.73e-3 |
| TC transformer, no memory | 1.64 | 1.79 | 1.46 | 2.05 | 7.53 | 5.02 | 1.19 | 0.80 | 1.12e-2 (ADR 0368) |
| **TP** TC + place | **1.41** | **1.55** | **1.27** | **1.70** | 7.00 | 4.65 | 1.08 | **0.82** | 1.15e-2 |
| TW transformer, past year | 1.31 | 1.47 | 1.18 | 1.63 | 6.95 | 4.37 | 1.01 | 0.81 | 0.45 (ADR 0368) |

(Seed spreads, single-year / 30-yr: NPP 0.16 / 0.34, ET 0.10 / 0.29, runoff 0.39 / 0.63 — max of B's and MR's.
Drift 0.90–0.96 for every arm, none worse than MR beyond the spread; area totals within 0.2–2 %. The held-out cells ×
training climate models give the same order: NPP single-year B 1.77, MR 1.77, MEP 1.54, TC 1.56, TP 1.37, TW 1.28.)

**A, place test — PARTLY.** Gain share (TC − TP)/(TC − TW), single-year / 30-yr: NPP 0.69 / 0.76, ET 0.67 / 0.83,
runoff 0.91 / 0.56. No flux reaches 0.75 on both, none is within the spread, so by the rule: partly. In words: a fixed
52-number description of the place's climate recovers roughly two thirds to three quarters of what the past year of
raw weather gave the transformer; the rest is genuine memory. TP's year-to-year NPP departures track the original
as well as TW's (0.82 vs 0.81) at 1/40 of its cost.

**B, cheap memory — no arm qualifies.** Every memory arm beats MR on single-year errors by more than the spread for
at least one flux (ME and MEP for NPP, ET and runoff), but no arm's late 30-year gain exceeds the 30-year seed spread
(0.29–0.63), so the "both statistics" rule fails everywhere. All are cheap (1.4–1.75e-3, ≤ 1.35× B). They keep about
a third of the transformer-with-memory's gain (MEP: NPP 0.37, ET 0.34, runoff 0.37). The place description helps the
MLP much less than it helps the transformer (MP 1.71 vs TP 1.41 NPP single-year). Chosen for the die-off re-score
(lowest NPP single-year): **MEP, not qualifying**. Its NPP departures r = 0.81 (B 0.72; all cells 0.740 vs 0.673).

### 6.2 Tree deaths with the per-tree carbon state (teacher-forced one year ahead)

| arm (2 seeds; spread ≤ 0.004 skill, ≤ 0.013 capture) | skill | die-off capture | 30-yr rate vs 2nd run | × training models: skill / capture |
|---|---|---|---|---|
| ST (ADR 0368) | 0.531 | 0.235 | 0.89 | 0.536 / 0.313 |
| STCe (ADR 0368) | 0.539 | 0.265 | 0.90 | 0.544 / 0.323 |
| STK + margin & counter at y−1 | 0.602 | 0.253 | 0.84 | 0.612 / 0.324 |
| STKCe + the deployed networks' cell carbon | 0.612 | 0.282 | 0.81 | 0.621 / 0.334 |
| STKe + carbon-state model (deployed networks' carbon) | 0.624 | 0.283 | 0.84 | 0.634 / 0.341 |
| STKc + carbon-state model (the original's cell carbon) | 0.651 | 0.385 | 0.78 | 0.657 / 0.428 |
| STKt + the TRUE state of year y (bound) | **0.804** | **0.508** | 0.76 | 0.803 / 0.533 |
| STCmep = STCe with MEP's carbon | 0.543 | 0.265 | 0.92 | — |
| STKmep = STKe with MEP's carbon | 0.626 | 0.291 | 0.85 | — |
| ORACLE (the original's own probability) | 1 | 0.697 | 0.68 | 1 / 0.714 |

Carbon-state model, held-out × held-out models: next year's log margin r = 0.994; bad-year log loss 0.196 (deployed
networks' carbon) / 0.177 (original's) / 0.195 (MEP's) vs 0.441 for the base rate 0.161.

**Pre-registered readings.** (1) The true per-tree state carries the die-off signal: STKt 0.508 ≥ 0.5 — **yes** (and
skill 0.80, the largest of any arm); even a perfect state leaves 0.19 of the oracle's capture, which is chance and the
hazards' own dependence on the counter. (2) State alone: STK − ST = +0.018 capture (< 0.03) but +0.07 skill. (3) Worth
a free-running test: STKe 0.283 vs STCe + 0.05 = 0.315 — **no**. (4) The carbon-state model adds beyond feeding its
inputs: STKe − STKCe = +0.001 — **no**. (5) Share of the bound kept (STKe − ST)/(STKt − ST) = **0.18**; with a
perfect daily NPP the same route reaches 0.385 (the daily model's limit is 0.10 of capture). (6) The cheaper memory
does not help the die-offs: STCmep − STCe = +0.001, STKmep − STKe = +0.007, although its NPP departures are better
(r 0.74 vs 0.67).

**Reading.** The die-offs are decided by the per-tree carbon state (the leaf-carbon margin and the run of bad years),
and the state's year-y value follows the year's carbon balance almost deterministically (r 0.994 for the margin). What
breaks the deployable chain is the year's NPP: the emulated cell NPP — from the deployed networks or the cheaper
memory ones — is not accurate enough in the bad years to move trees across the two thresholds (capture 0.28–0.29
vs 0.385 with the original's NPP and 0.51 with the true state). Improving the daily NPP's typical error (MEP: −10 %)
or its departure correlation (0.67 → 0.74) did not move the die-off capture; what matters is the NPP of the few
extreme years.

