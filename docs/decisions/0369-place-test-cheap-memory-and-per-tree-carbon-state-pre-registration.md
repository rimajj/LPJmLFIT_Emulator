# 0369 — Three follow-ups of the transformer experiments: is the memory gain just a description of the place, can the deployed daily network carry the memory cheaply, and does a per-tree carbon state catch the die-offs? (pre-registration, SEPARATE EXPERIMENT)

* **Status:** pre-registered 2026-10-23, before any fit of this record. Results: §6, added after the runs.
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

## 5. Amendments

(none yet)

## 6. Results

(to be added after the runs)
