# 0368 — Two transformer experiments: does the daily model lack long weather memory, and does a model that sees the whole patch predict tree deaths better? (pre-registration, SEPARATE EXPERIMENT)

* **Status:** pre-registered 2026-10-23, before any fit of this record. Results: §7, added after the runs.
* **SEPARATE EXPERIMENT — nothing of it enters the paper or the release package** (owner 2026-10-23: *"treat it as a
  seperate experiment. nothing enters the paper."*). Code lives under `scripts/xtf_*.py`, data under
  `esm_land_emulator_data/xtf/`.
* **Owner instructions (2026-10-23):** *"have you considerd building an transformer based emulator?"* → the two tests
  proposed in reply: *"yes, try 1 and 2"*; *"take the data you thik is best for the purpose and produce more data if
  you need it, just dont do full grid runs for now"*; *"for now we should only judge how well teh emulator reproduces
  the clusterd runs it was trained on"* (scored on the held-out cells of those runs, with the training-cell fit
  reported beside it — a training-cell score alone rewards memorising).
* **Data:** the clustered nitrogen-on runs of ADR 0342 (674 representative cells, 25 patches, transient CO2; 135
  held-out cells = `cells.parquet:heldout`). **New data made for this record:** the seed-3 2020–2100 legs (rising CO2)
  of the 8 climate models that had none (24 legs, jobs 2672244–67, `scripts/clu_emu_runs.sh legs 3 …`), so that a
  second run of the original exists for all 10 climate models × 3 scenarios. No full-grid run.
* **Follows:** ADR 0334/0336 (the daily model's remaining error is coverage of places; more samples null), ADR
  0364/0366 (per-tree mortality: die-off capture 0.36–0.43, bar 0.5).

## 1. Experiment 1 — does the daily model lack long weather memory?

**Hypothesis.** The deployed daily network sees today's weather, six hand-made running means (temperature 10/30 d,
radiation 30 d, rain 30/90/365 d), yesterday's water stores and the stand. If its error on held-out cells comes
from memory those means do not carry, a model that reads the raw past year of weather does better. If not, the
architecture is not the lever.

**Arms** (everything but the network identical to the clustered daily members `NC_s0–s4` of ADR 0342: 8 training
climate models × 4 legs of seed 2, the 485 training cells, 40 M samples, 10 epochs, batch 16 384, one-cycle Adam at
3e-3, the same 8 targets, loss, closed snow / top-metre / deep stores with the 365-day deep release, NPP = GPP − Ra,
humidity held at 0, CO2 input, the original's stand):

* **B** — the existing MLP (256 × 3), the five trained seeds `NC_s0–s4` as they are (no retraining). Their spread
  is the seed-noise yardstick.
* **TC (capacity control)** — a transformer encoder (width 128, 4 layers, 4 heads, feed-forward 256, pre-norm)
  whose input is ONE state token carrying exactly B's input vector, plus ONE token of today's raw weather. Same
  information as B; only the network differs.
* **TW (memory arm)** — the same transformer; the state token carries B's inputs WITHOUT the six running means; the
  weather sequence is the past 364 days of raw weather (temperature, log rain, shortwave, net longwave): the last 14
  days one token each + 50 weekly-mean tokens before that (64 tokens). Weekly rain token = log(1 + 7-day sum).
* 3 seeds each of TC and TW (0, 1, 2).

**Scores** (free run of the whole 2020–2100 leg, as `clu_emu_f2.py run`; per member k ∈ {2, 3} the network runs on
member k's own stand and starting stores, and is scored against member k; the second run is the other member):
held-out cells with 2021–2100 mean GPP ≥ 50 gC m⁻² yr⁻¹, every leg with both members (10 climate models × 3
scenarios). Per flux (GPP, ET, NPP, runoff): typical (median) error of the 30-year means 2021–2050 and 2071–2100
divided by the second run's; the same for single years (normalised by the cell's 2021–2100 mean); drift = the
2081–2100 over the 2021–2040 single-year ratio; area-total relative error. Reported in three groups: held-out cells ×
held-out climate models (IPSL, MPI — the strictest), held-out cells × training climate models, training cells
(in-sample reference). Cost: one core, the whole daily step for one cell-year (`f2_train.bench_speed` method).

**Decision (written before any fit):**
* *Seed spread* s = max − min over B's five seeds of the statistic, per flux and group.
* **Memory helps** if the TW seed mean beats the TC seed mean on the typical single-year ratio AND the late 30-year
  ratio by more than s for at least two of NPP, ET, runoff on held-out cells × held-out climate models, with drift
  not worse by more than s. ⇒ next step (a new record): carry that memory cheaply (learned running means or a
  distilled small network); the transformer itself is not a deployable candidate until its one-core cost is measured.
* **Transformer capacity helps** if TC beats B's seed mean by the same rule.
* **Neither** ⇒ architecture is not the lever for the daily model; stop, nothing else is built.
* A score within s is called "no measurable difference", never a gain.

## 2. Experiment 2 — does a model that sees the whole patch predict tree deaths better?

**Hypothesis.** A tree's death depends on its neighbours (light competition sets its NPP, and its leaf carbon
against the sapling threshold). A set transformer over all trees of a patch can learn that interaction; a per-tree
model with hand-made patch summaries may already carry it.

**Data** (`scripts/xtf_tree_pairs.py`, new): from the clustered `ind_<scen>.csv` of seeds 2 and 3, every leg with
both members. At-risk tree of year y = a tree of types 0–6, alive at the end of y−1 (the table carries trees ≥ 5 m).
Identity (Cell, Patch, Type, ID, SLA), asserted unique; every found tree must be exactly one year older (asserted).
**Outcome** = dies in y: a row with `isdead = 1`, or no row in y. ~~Measured on 60 cells of one leg: every tree
without a row in y belongs to a patch that lost ALL its trees that year (1 467 of 119 992 patch-years, 1.2 % of
at-risk trees) — a whole-patch kill.~~ **Struck (§2a): that check paired the year-2100 trees with a year 2101 that does
not exist; the 1 467 patch-years are those. Trees missing without a row are 0–1 per leg.** **Inputs per tree (state at the
end of y−1):** Type, height, maximum height, age, aboveground biomass, vegetation carbon, NPP, transpiration, SLA,
longevity, wood density, LAI, stem diameter, bark thickness, crown cover (`fpc_ind`), `minwscal`, D95, D95max,
NFixing. **Per cell and year:** latitude, CO2 of y, and from the daily weather of y and y−1: mean temperature,
warmest-month and coldest-month temperature, rain sum, driest-90-day rain sum, mean shortwave; the 30-year trailing
means of the same. Never the `mort*` columns (they are the original's own probabilities of year y — used only as the
oracle below).

**Arms:**
* **P0** — per-tree LightGBM (binary log loss, 400 rounds, the release parameters `explore_panel_a7.PARAMS`): tree +
  cell inputs.
* **P1** — P0 + hand-made patch summaries at y−1: number of trees, Σ crown cover, Σ biomass, the tree's height rank
  (0–1), crown cover of trees taller than it, the patch's mean and the tree's own NPP relative to the patch mean.
* **ST** — set transformer: tokens = the patch's trees (the P0 tree inputs, type embedding) + one context token (the
  cell inputs); width 128, 4 layers, 4 heads, no positional encoding (a set); per-tree output = logit of death.
  BCE loss, AdamW, 3 seeds.
* **Oracle (bound, not a model):** the original's own death probability of year y, ~~p = 1 − (1 − `mort`)(1 −
  `mort_fire`)~~ **p = min(1, `mort`)** (§2a).
  **Climatology:** the training-set death rate per tree type.

Training: seed 2, the 8 training climate models × 3 scenarios, training cells, 2021–2100 (every at-risk tree for ST;
the same trees for P0/P1). Test: held-out cells, seeds 2 and 3, all 10 climate models × 3 scenarios.

**Scores (teacher-forced one-year-ahead: each year starts from the original's own trees — this isolates the model,
it is not a free run):**
* **Skill** = (LL_clim − LL_arm) / (LL_clim − LL_oracle), LL = mean per-tree log loss on held-out cells; the share of
  the gap between knowing nothing and knowing the original's own probability that the arm closes. Also Brier and
  calibration (Σ p / deaths) per climate model.
* **30-year death rate** per cell (2071–2100, dense cells = ≥ 5 trees per patch at 2020): typical error vs member k,
  divided by the second run's (the other member).
* **Die-off capture** as ADR 0364 §4 (Σ jump of predicted rate / Σ jump of the truth; jump = event year − mean of the
  5 years before; events = cell-years whose death rate exceeds the cell's 2021–2100 median by more than 3× the
  cell's median absolute deviation and is ≥ 0.05, defined on member k's truth before any prediction).

**Decision:**
* **Neighbours matter** if P1's skill exceeds P0's by ≥ 0.05.
* **The set transformer is worth pursuing** (a free-running test in a new record) if ST's seed-mean skill exceeds
  P1's by ≥ 0.05 and by more than ST's seed spread, AND its die-off capture exceeds P1's by ≥ 0.05, AND its 30-year
  death-rate ratio is not worse than P1's by more than 10 %.
* Otherwise: hand-made summaries carry what the patch has to say; stop.

## 2b. Addition after the experiment-2 result (owner 2026-10-23, pre-registered before these fits)

Owner, on "die-offs stay mostly missed … what the models lack is the year's own carbon balance": *"and why dont you
fix that?"*. That reading was a hypothesis, not a measurement. Three set-transformer arms (ST architecture and
training, 2 seeds each) test it:
* **STCt (bound):** + the cell's year-y NPP and GPP from the original, and their departures from the previous 5
  years (÷ the cell's 2021–2100 mean |value|), `scripts/xtf_tree_carbon.py`.
* **STCe (deployable):** the same four inputs from the emulator's own free-running daily model (the mean of the five
  deployed clustered networks NC_s0–4, run on the original's stand — `xtf_daily.py run --arm B`). Train AND test on
  the emulated values. Caveat stated before the fit: on training cells the daily networks are in-sample, so the
  emulated inputs are better there than on held-out cells (NPP departure r(true, emulated) = 0.673 over all cells).
* **STTt (tightest bound):** + each tree's own year-y NPP from the original (per tree; not producible by the
  emulator).

**Reading rules (held-out cells × held-out climate models, against ST = 0.531 skill / 0.235 die-off capture):**
* the hypothesis holds if STCt or STTt reaches die-off capture ≥ 0.5; otherwise it is refuted and stated so.
* STCe is worth a free-running test if its die-off capture ≥ ST + 0.05 with skill not lower; the share of the bound's
  gain it keeps, (STCe − ST) / (STCt − ST), is reported either way.

## 2a. Amendments before any result (2026-10-23, written while the first fits were queued)

* **Experiment 1:** the transformer arms train in bf16 autocast with gradient-norm clipping at 1.0 (B has neither;
  a smoke fit on 2 legs / 2 M samples was stable at the pre-registered 3e-3 without needing a change of learning
  rate). Free runs are full fp32 for every arm.
* **Experiment 2, cell inputs:** instead of the six hand-picked statistics, the 25 yearly climate statistics the
  clustered maps already use (`clu_emu_maps.clim_cols`: mean / coldest / warmest month temperature, GDD5, frost days,
  hot days, rain and its half-year sum, PET, climatic water balance and its driest 3 months, longest dry spell,
  humidity, VPD, shortwave, net longwave, the seven per-type temperature-stress counts) for year y, year y−1 and
  their trailing 30-year means (`clu_emu_maps.window`), + CO2 of y + latitude. Same for every arm.
* **Experiment 2, sample:** the tables keep every patch-year of the held-out cells and a fixed 15 % of the other
  patch-years (hash of cell, patch, year). All three arms train on the same kept training-cell trees.
* **Experiment 2, no whole-patch losses:** the 1.2 % "whole-patch kill" of §2 was my check's error (year-2100 trees
  looked up in a non-existent 2101). In the real tables 0–1 trees per leg go missing without a row; they count as
  deaths and, having no oracle, are left out of skill / Brier / calibration (the build fails above 1e-5 of the
  at-risk trees). `patch_loss` is kept as a flag and is empty.
* **Experiment 2, oracle:** in the merged nitrogen-on model the per-tree `mort` ALREADY includes fire (trees with
  `mort_fire` 0.29 have `mort` 0.32 and die at 0.32; 120 cells of one leg). The pre-registered 1 − (1 − `mort`)(1 −
  `mort_fire`) counted fire twice (Σ p / deaths 1.11–1.26); **the oracle is min(1, `mort`)** (Σ / deaths 0.93, the
  rest is chance). Found from the first builds' calibration print, before any model was fitted; tables rebuilt.
* **Experiment 2, set size:** a patch-year with more than 128 at-risk trees is fed its first 128; the rest get the
  patch's mean prediction (their number is logged at training).

## 3. What this record does not do

No free-running tree model, no change to any release, no full-grid run, nothing in the paper. Both experiments are
offline and use the original's own stand / trees as inputs, so they bound what each architecture could add; they do
not show it ships.

## 7. Results

### 7.2 Experiment 2 — tree deaths (2026-10-23)

Data: 60 legs (seeds 2 and 3 × 10 climate models × 3 scenarios); training 22.8 M at-risk trees (2.9 M patch-years,
none with > 128 trees), held-out cells 20.9 M trees under the held-out climate models, 84.5 M under the training ones.
`xtf/treemort/score.csv`. Seed means; seed spread of the skill ≤ 0.002 for every network arm.

| arm | skill held-out cells × held-out models | × training models | training cells | calibration | 30-yr death rate vs 2nd run | die-off capture (8 111 events) |
|---|---|---|---|---|---|---|
| P0 per-tree LightGBM | 0.421 | 0.425 | 0.466 | 1.027 | 1.10 | 0.157 |
| P1 + hand-made patch summaries | 0.437 | 0.441 | 0.479 | 1.013 | 1.11 | 0.144 |
| **ST1** same network, one tree per set (post-hoc control) | 0.503 | 0.511 | 0.559 | 1.024 | 0.98 | 0.225 |
| **ST** set transformer (3 seeds) | **0.531** | 0.536 | 0.592 | 1.002 | **0.89** | **0.235** |
| ORACLE the original's own `mort` (post-hoc ceiling) | 1 | 1 | 1 | 0.957 | 0.68 | 0.697 |

(log loss held-out × held-out models: climatology 0.1863, P0 0.1646, P1 0.1638, ST 0.1590, oracle 0.1348.)

**Pre-registered decision:** neighbours matter (P1 − P0 ≥ 0.05)? +0.015 ⇒ **no**. Set transformer worth pursuing?
skill +0.094 over P1 (> 0.05 and > spread 0.002), die-off capture +0.091 (≥ 0.05), 30-yr ratio 0.89 vs 1.11 ⇒
**WORTH PURSUING** by the rule as written.

**Post-hoc controls (added after the result above, labelled as such):** the rule compared a neural network that sees
the patch with boosted trees that do not, i.e. two changes at once. **ST1** (the same network, every tree alone)
splits them: of ST's +0.094 skill over P1, **+0.066 is the network itself and +0.028 is seeing the other trees**; of
the +0.091 die-off capture, +0.081 vs +0.010; of the 30-yr rate gain (1.11 → 0.89), 1.11 → 0.98 vs 0.98 → 0.89. The
neighbour part is real (14× the seed spread) but small, and alone it would not have passed the pre-registered 0.05
bars. **The ceiling:** the original's own probability catches 0.70 of the die-off jumps; every arm catches ≤ 0.24.

**Reading.** (1) A per-tree neural network is a better per-tree death model than LightGBM on the same inputs; most of
the "transformer" gain is that. (2) Seeing the patch adds a little more and is the only arm whose 30-year death rate
is closer to the run than a second run is. (3) Die-offs stay mostly missed by every arm: what the original knows in
the die-off year and no arm does is the year's own carbon balance (all arms see only the end-of-previous-year state
and the year's climate), consistent with ADR 0364's bound (0.74 with the run's own NPP). (4) All of this is
teacher-forced (each year starts from the original's own trees); nothing here shows a free-running forest works.

### 7.2b The year's carbon balance as input (§2b, 2026-10-23)

| arm (2 seeds, spread ≤ 0.004) | skill held-out cells × held-out models | die-off capture | 30-yr rate vs 2nd run | × training models: skill / capture |
|---|---|---|---|---|
| ST (no carbon input, from 7.2) | 0.531 | 0.235 | 0.89 | 0.536 / 0.313 |
| **STCe** + cell NPP/GPP from the emulator's own daily model | 0.539 | 0.265 | 0.90 | 0.544 / 0.323 |
| **STCt** + cell NPP/GPP from the original (bound) | 0.566 | 0.350 | 0.88 | 0.566 / 0.390 |
| **STTt** + each tree's own NPP from the original (bound) | 0.652 | 0.458 | 0.83 | 0.646 / 0.487 |
| ORACLE (ceiling) | 1 | 0.697 | 0.68 | 1 / 0.714 |

**Pre-registered readings.** (1) Hypothesis "the year's carbon balance is what the models lack": the best bound
reaches 0.458 < 0.5 ⇒ **refuted as stated.** The carbon balance explains about half of the missing die-off signal
(the tree's own NPP closes (0.458 − 0.235)/(0.697 − 0.235) = 48 % of the gap to the ceiling; the cell's NPP 25 %);
the rest is what the original tracks per tree beyond one year's NPP (leaf carbon against the sapling threshold, the
five-bad-years counter) and chance. (2) STCe: capture +0.030 < 0.05 ⇒ **not worth a free-running test.** It keeps
(0.265 − 0.235)/(0.350 − 0.235) = **26 %** of the cell-carbon bound's gain — the same limit as ADR 0366 on the panel:
the emulated year-to-year NPP departures track the original's only at r = 0.673 (all cells; lower on held-out ones).
**So the lever for die-offs is a better daily NPP (its departures from normal), and beyond that a per-tree carbon
state; a better tree-death network alone cannot get there.**

