# 0340 — Emulator release v1: the whole learned emulator as one package, and the verdict against the goal

* **Status:** accepted 2026-10-15 (the package, the release and the measurements). The verdict in §4 is a measurement;
  which of the open items in §5 to pursue is the owner's call.
* **Owner instruction (2026-10-15):** *"continue and finally finish the emulator!! you have been working for weeks on
  this now. its time to finish"*.
* **Depends on:** ADR 0318 (goal and relaxed standard), 0325 (daily-flux numbers), 0330 (year-by-year structure map),
  0331/0337 (stand map, phase B), 0335/0336 (deployment daily model arm D), 0338/0339 (stand attribution, cover fits).
* **Code:** `python/src/lpjmlfit_emulator/landemu/` (package), `scripts/build_emulator_release.py`,
  `scripts/run_emulator.py`, `scripts/final_structure_score.py`, `scripts/final_daily_score.py`,
  `scripts/explore_glob_levels_all.py` + `scripts/explore_glob_allcells.py` (all cells of the global venue);
  guide `docs/emulator_release.md`; tests `python/tests/test_landemu.py`.

## 1. What "finished" meant here

Until now every part existed only as experiment scripts reading training tables: the structure map, the stand map and
the daily model were joined in one timing loop (`bench_coupled_speed.py`) whose forest models read their climate
statistics from the training table, not from the weather. This record closes that: one object, `LandEmulator`,
runs the whole emulator from daily weather alone, with numpy and LightGBM as its only run-time dependencies; it is
gated against the validated pipeline; and every criterion of the goal is measured on the thing that ships.

## 2. The package and the releases

`LandEmulator.step_year(state, forcing)` per year: (1) the daily model (five 3 × 256 networks, numpy port of the
PyTorch arm D) runs 365 days on last year's stand, with the closed snow / top-metre / deep bucket; (2) 25 yearly
climate statistics from the same weather enter a 30-year window; (3) 6 structure and 12 stand LightGBM models predict
the year; the stand feeds next year. `Setup` holds the per-cell inputs (anchors per cell-year, the anchor runs'
climate, the continued run's 2000–2019 levels, stores, the 2019 stand and weather).

Releases (`/p/projects/open/Jamir/esm_land_emulator_data/release/`, never overwritten):

| release | trained on | purpose |
|---|---|---|
| `v1` | runs m1–m6 × all 30 legs of ten climate models (3.97 M rows) | **deployment** |
| `fold_gfdl-esm4_v1` | the validated setup: runs m1,m2,m3,m5,m6 × the nine other models | proves package == scored pipeline |

Size 183 MB per release (four per-run setups of 42 MB; models 25 MB).

## 3. Gates (all measured, jobs 2502573 / 2502581 / 2502582)

| gate | result |
|---|---|
| numpy daily ensemble vs PyTorch, 20 000 real input rows | max \|diff\| = 1.0e-6 of each output's range ✓ (a first threshold scaled by the 90th-percentile snow change, ~0, failed falsely; fixed) |
| package climate statistics vs `explore_glob_climate.year_features`, same weather | identical (max diff 0) ✓ |
| setup anchors vs the validated test rows' anchors (fold) | identical, 255 150 rows ✓ |
| fold release, run m4, GFDL ssp370, 81 years, vs the scored predictions | daily GPP / ET / NPP / runoff: median per-cell difference 1.6–2.9e-4, 90th pct ≤ 3.3e-3, totals ≤ 7e-4 ✓; structure and stand: median difference 0, 99th pct 0.1–7 % of each quantity's size |
| deployment release `v1`, run m1, UKESM ssp370, 81 years, fixed capacity (job 2502719; in-sample, a run check not a score) | ran clean, 7.49e-3 core-s per cell-year; cross-cell mean snow 24 → 12 mm and tree count 7.6 → 8.4 per patch over the century |
| water closure (unit test) | rain = Δstores + interception + transpiration + evaporation + runoff to 1e-6 mm/yr ✓ |

**The residual structure/stand differences have one identified cause, not a package error.** The panel forcing is
stored in 0.1 °C steps; the training table converted it with a float32 scale factor, so a day at exactly 30.0 °C
became 30.0000004 and counted as "above 30" — up to 11 such days per cell-year. The package (fed the float32 copy the
daily model reads) does not count them, so `days_gt30`, `vpd_win10_sum` and the stress-day counts differ by a few
days in 9–38 % of cell-years while every mean agrees to 1e-6. Continuous forcing (any Earth-system model) never sits
exactly on a threshold; not imitated.

## 4. The verdict against the goal

### 4.1 Faithful — forest structure (relaxed standard, ADR 0318 §2)

**Panel, the model the emulator runs** (year-by-year map, `final_structure_score.py`, job 2502580; 1 050 cells;
climate model AND run held out; 15 cases; mean of 2071–2100; harness = a training run scored as the emulator:
0.95–1.03 everywhere ✓). A criterion passes at median ≤ limit AND ≥ 12 of 15 cases.

| | dense defined before the run (anchor ≥ 5 trees/patch) | dense defined by the held-out run itself |
|---|---|---|
| D1 dense typical, tree count (≤ 1.2) | 1.16, **11/15 ✗** (one case short) | 1.12, 9/15 ✗ |
| D1 biomass per tree | 1.07, 14/15 ✓ | 1.06, 14/15 ✓ |
| D1 four trait medians | 0.60–0.83 ✓ | 0.59–0.83 ✓ |
| D2 dense worst 10 % | tree count 1.29, biomass 1.01, traits 0.47–0.83 ✓ | 1.27 / 1.00 / 0.47–0.82 ✓ |
| D3 dense totals (5 %) | stems −0.1 %, biomass −1.5 % (signed medians) ✓ | stems −2.0 %, biomass −1.6 % ✓ |
| S1 sparse typical (≤ 3) | tree count 2.74, biomass 1.34, traits 0.83–0.99 ✓ | tree count 2.95, **8/15 ✗**; rest ✓ |
| S2 sparse totals (25 %) | stems −2.3 %, biomass −5.7 % ✓ | **stems +17.7 %, 11/15 ✗**; biomass ✓ |
| **criteria passing** | **21 of 22** | 19 of 22 |

ADR 0329 showed the run-defined split selects on the held-out run's own outcome; the anchor-defined one is the fair
reading. This is better than the 30-year-window map's numbers on record (ADR 0318 §3: tree count 1.23, biomass 1.18,
sparse stems 19.5 %).

**All 57 726 tree-bearing cells, global venue** (M. Billing's runs, GFDL-ESM4 only, 25 patches; window map A7rH,
because these runs store per-tree output only for 1985–2014 and 2071–2100, so the year-by-year map cannot be built
there; jobs 2502519–2502611; harness: A7r on dev cells reproduces ADR 0317 §8 at 1.44 / 1.99 ✓, a second run
0.97–1.04 ✓; all-cell levels bit-identical to the dev-cell ones where they overlap ✓; 76 % of cells dense):

| | run AND scenario held out (ssp370 unseen) | only the run held out (3 scenarios) |
|---|---|---|
| D1 tree count / biomass per tree | **1.24 ✗ / 1.47 ✗** | 0.92 / 0.92 ✓ |
| D2 tree count / biomass per tree | 1.25 ✓ / **1.505 ✗** (±0.03) | 0.91 / 0.86 ✓ |
| D3 totals stems / biomass | −2.2 % ✓ / **+7.1 % ✗** | −0.9 % / −0.8 % ✓ |
| S1 tree count / biomass per tree | **3.79 ✗** / 1.72 ✓ | 1.85 / 1.20 ✓ |
| S2 totals stems / biomass | **+52 % ✗** / +18 % ✓ | +8.7 % / −3.2 % ✓ |
| four trait medians, every criterion | ✓ (0.44–1.14) | ✓ |

Moving from the 10 % dev sample to all cells changed the numbers by ≤ 0.06 — the dev cells were representative. Under
an unseen scenario on this venue the structure map fails; with the scenario seen it passes, but there the mean of the
training runs at the same scenario is better still (0.80 vs 0.92 dense) — partly a choice in the anchor (it left out
the cell's own scenario, untested).

### 4.2 Faithful — daily carbon/water exchange (ADR 0325 §3; the whole emulator, i.e. the daily model fed the
emulated stand, run `PD_B`; 13 climate-model legs; 238 held-out cells; `final_daily_score.py`)

| flux | typical error ≤ 3× | worst 10 % ≤ 3× | climate response ≤ 1.5× | totals ≤ 5 % | drift ≤ 1.2 |
|---|---|---|---|---|---|
| GPP | 2.37 ✓ (13/13) | 2.38 ✓ | 1.91 ✗ (1/13) | 1 % ✓ | 1.01 (11/13; UKESM ssp370, IPSL ssp585 1.26) |
| NPP | **3.85 ✗** (0/13) | 3.03 (6/13) | 2.04 ✗ | 1 % ✓ | 1.03 ✓ (13/13) |
| ET | 3.14 (5/13) | 1.88 ✓ | 1.80 ✗ | 1 % ✓ | 0.95 ✓ |
| runoff | **5.21 ✗** | 6.53 ✗ | 2.50 ✗ | 2 % ✓ | 0.90 ✓ |

In plain units a second run differs by 1.0–1.6 % on a cell's 30-year GPP / ET / NPP, so the emulator's typical cell
is ~3–6 % off on GPP/ET, ~5–6 % on NPP; area totals are within 1–3 %.

### 4.3 No drift in transient runs

* Structure (ADR 0330 data, re-read): from mid-century (2051–2070) to late (2081–2100), after the known 2000–2019
  start state has faded, the error grows ×1.05 for tree count and ×1.05 for biomass per tree (15/15 cases ≤ 1.2);
  traits ×1.10–1.19 while staying at 0.62–0.85× a second run. The pre-registered rule (late vs 2021–2040) fails
  (1.17 / 1.32) because the early error is artificially low — the start state is known then.
* Daily: no drift on 13 of 13 legs for NPP / ET / runoff; GPP drifts 1.26 on the two warmest legs.
* Water stores: the deep store is stable (ADR 0326); in the package run (81 years) the top-metre store stays at
  80–91 mm and snow at 18–29 mm across-cell means.

### 4.4 Faster — measured end to end on the package (job 2502581, one core, 1 050 cells × 81 years)

**7.57e-3 core-seconds per cell-year** for everything (daily model 97 %), against the original's 0.267 at 25
patches (**35× less**) and ~6.7 at the ~500 patches of publication runs (**~900× less**). Inside the T31 / T63
allowances of `EXECUTION_PLAN.md` §0 (0.0135 / 0.030) by 1.8× / 4×. The package's numpy daily networks cost ~15 %
more than the PyTorch single-thread timing of ADR 0337 §5 (6.55e-3). No GPU, no batching across years: both are
open speed levers (the cost is one matrix product per day per network).

### 4.5 Coupled to an Earth-system model — not done

The package runs offline on prescribed weather. Nothing is exchanged with SpeedyWeather; the energy-balance closure
(ADR 0073–0085) is not part of it.

## 5. What does not pass, and what it would take

1. **Daily NPP, ET and runoff above 3× a second run, and every flux's climate response above 1.5×.** Most of the
   stand's added error is plant-type cover (ADR 0338); two cheaper cover fits did nothing (ADR 0339). Run-to-run
   noise of one daily ensemble is ±9–20 % per leg (ADR 0336 §6), so arm margins below that cannot be read.
2. **Dense-cell tree count** misses by one case on the panel; **sparse cells** overshoot stems by +52 % globally under
   an unseen scenario.
3. **Where it can run:** the anchors need the original's yearly 2020–2100 output on every emulated cell. Release v1
   has setups for the 1 050 panel cells only; a global release needs yearly runs of the original on all cells (or a
   different anchor), and running past 2100 needs an anchor rule beyond the training scenarios.
4. **Coupling** (§4.5).

## 6. Decision

Release v1 is the emulator as of today: complete in function (structure, stand and daily exchange from weather
alone), gated against the validated pipeline, 35–900× cheaper than the original, conserving water by construction,
no drift in structure once the start state has faded. It does **not** meet every proposed number: §5 lists each miss.
Further work is a choice among §5's items, not unfinished plumbing.
