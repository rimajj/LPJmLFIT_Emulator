# The learned LPJmL-FIT emulator — release guide (version 1, ADR 0340)

One Python object, `LandEmulator`, runs the whole emulator: daily weather in; daily carbon and water fluxes plus
yearly forest structure and stand out. Run-time dependencies: **numpy and LightGBM only** (no deep-learning
framework, no Julia, no C binary).

Code: `python/src/lpjmlfit_emulator/landemu/` · build a release: `scripts/build_emulator_release.py` · run one:
`scripts/run_emulator.py` · tests: `python/tests/test_landemu.py`.

## What it computes each year

1. **Daily water–carbon model** (365 steps): a five-network ensemble (3 × 256, numpy port of the PyTorch arm D of
   ADR 0335/0336) predicts interception, transpiration, soil evaporation, runoff, snow change, deep drainage, GPP
   and NPP from the day's weather, trailing weather windows (10/30/90/365 days), calendar, latitude, the water
   stores, the top-metre capacity and **last year's stand** (leaf area, vegetation carbon, cover of 10 plant types).
   A closed bucket (snow, top metre, a deep store draining with a 365-day time constant into runoff) keeps water
   conserved exactly: rain = Δstores + interception + transpiration + evaporation + runoff, every day.
2. **Yearly climate statistics** (25 columns: temperature means/extremes, degree days, frost and hot days, rain,
   potential evaporation, water balance, dry spells, humidity, vapour pressure deficit, radiation, the seven tree
   types' temperature-stress day counts), from the same daily weather, pushed into a 30-year trailing window.
3. **Structure map** (6 gradient-boosted models): tree count per patch, biomass per tree, median SLA, wood density,
   maximum rooting depth, minimum water scalar. **Stand map** (12 models): leaf area, vegetation carbon, cover of the
   10 plant types — which become next year's daily-model input.

The structure and stand maps are **not recursive**: a year's state is a function of the climate window and the
cell's fixed setup, so their errors cannot accumulate. The only state carried from year to year is the daily model's
water stores, its weather windows and the stand vector.

## Inputs (`Setup`, one file per continued run of the original)

| field | meaning |
|---|---|
| `cell, lat, lon, soil_code` | the cells (orderA index) |
| `anc[q]` (cells × years 2020–2100) | **anchor**: the original's mean over its training runs of quantity q for that cell and year |
| `aclim` (cells × years × 25) | the anchor runs' trailing 30-year climate |
| `s0[q], memoff[q]` | the continued run's own 2000–2019 levels and their offset from the training runs' mean |
| `clim_hist` (20 × cells × 25) | yearly climate statistics 2000–2019 (seeds the 30-year window) |
| `cap` | top-metre plant-available water capacity, mm |
| `W0, S0, D0, stand0, warm` | water stores, the stand at the end of 2019, the 365 days of weather before 2020 |

⚠ **The anchors are what limit where the emulator can run.** It needs the original to have been run, under some
scenarios, on every cell it emulates (that is how it was validated: held-out climate model and run, cells seen) and
the anchor table ends in 2100. Release v1 carries setups for the **1 050 panel cells** only. Running it on the full
grid requires yearly 2020–2100 output of the original on every cell (M. Billing's global runs store per-tree output
only for 1985–2014 and 2071–2100); running past 2100 requires an anchor rule beyond the training scenarios.

## Use

```python
import numpy as np
from lpjmlfit_emulator.landemu import LandEmulator, Setup

emu = LandEmulator.load("/p/projects/open/Jamir/esm_land_emulator_data/release/v1")
su = Setup.load(".../release/v1/setup_m1.npz")
state = emu.start(su)
for year in range(2020, 2101):
    forcing = ...                      # (cells, 365, 5): tas degC, pr mm/day, rsds W/m2, lwnet W/m2, huss kg/kg
    daily, annual = emu.step_year(state, forcing)
    # daily: gpp, npp, interc, transp, evap, runoff, swe, soilw, deep -> (cells, 365)
    # annual: n_per_patch, agb_per_stem, SLA_p50, Wooddens_p50, D95max_p50, minwscal_p50,
    #         lai_stand, vegc, fpc1..fpc10 -> (cells,)
```

**Day by day (for an atmosphere model, ADR 0345):** `step_year` is exactly

```python
emu.begin_year(state)                    # (co2=ppm for a CO2 release; cap=... optional)
for d in range(365):
    day = emu.step_day(state, f_d)       # f_d (cells, 5) one day's weather -> dict name -> (cells,)
ann = emu.end_year(state)                # yearly climate statistics, structure and stand maps
```

so an ESM calls `step_day` once per simulated day (365-day years) and `end_year` on 31 December. The
SpeedyWeather coupling built on it: `scripts/online_coupling/run_speedy_landemu.jl` (skill `online-coupling-env`).

`scripts/run_emulator.py --release DIR --run k --leg <leg> [--check]` does this over the panel forcing, times it on
one core and, for a fold release, checks the outputs against the scored predictions.

## Releases

| directory (under `/p/projects/open/Jamir/esm_land_emulator_data/release/`) | what |
|---|---|
| `v1/` | **deployment**: every run (m1–m6) × every leg of all ten climate models trains the structure and stand maps |
| `fold_gfdl-esm4_v2/` | the validated setup with GFDL-ESM4 held out, built on the leak-free training rows (ADR 0352 §0, 0353) — exists to prove the package equals the scored pipeline; `run_emulator.py --check --check-tag PD_B_fx` |
| `fold_gfdl-esm4_v1/` | superseded: the same, built before the leak fix (its maps trained on a sibling of the test run under the held-out model); kept, not for new numbers |

A release is never overwritten (`build_emulator_release.py` refuses an existing directory). Every build runs three
gates first: the numpy daily ensemble equals the PyTorch one (max |diff| ≈ 1e-6 of each output's range), the
package's climate statistics equal the training pipeline's exactly, and (fold) the setup's anchors equal the
validated test rows' exactly.

## How good it is

See ADR 0340 §4 for the full verdict against the goal (structure on the relaxed standard, daily fluxes against a
second run of the original, drift, speed) and §5 for what does not pass.

⚠ **Restated 2026-10-21 (ADR 0353 §5):** ADR 0340's held-out-model structure and stand numbers were flattered by a
training leak. Leak-free: structure 18 of 22 criteria (dense tree count 1.26× and biomass per tree 1.18× a second
run's error, both failing the 1.2 limit; sparse tree count 3.00×), stand leaf area 1.45×, vegetation carbon 1.31×;
daily fluxes unchanged within 1 % (GPP 2.36×, NPP 3.94×, ET 3.09×, runoff 5.22×). Quote those, not ADR 0340 §4.1–4.3.

## Nitrogen-on releases with a CO2 input (ADR 0344)

Emulator of the **merged LPJmL-FIT with nitrogen on (no phosphorus) and transient CO2**, 25 patches, trained on the
clustered runs of ADR 0342 (674 representative cells, one per climate region; 10 climate models × ssp126/370/585,
rising and fixed CO2). Same package; the release says `"co2_input": true` and every year needs the year's CO2:

```python
emu = LandEmulator.load(".../release/non_v1")
su = Setup.load(".../release/non_v1/setup_s2.npz")      # 674 cells, start = end of 2019
state = emu.start(su)
for year in range(2020, 2101):     # anchors are per cell: runs past 2100 work but leave the training climate
    daily, annual = emu.step_year(state, forcing, co2=ppm[year])   # ppm: global yearly mean
```

The daily model reads the year's CO2; the yearly maps read its trailing 30-year mean and that mean's offset from
1990–2019 (378.42 ppm). A release without the input (v1, the global Billing-trained ones: nitrogen off) refuses
`co2=`; a CO2 release refuses a call without it.

| directory | trained on | purpose |
|---|---|---|
| `non_fold_v1/` | 8 climate models (MPI-ESM1-2-HR, IPSL-CM6A-LR held out), 80 % of cells | reproduces the scored results exactly |
| `non_v1/` | all 10 climate models' 58 legs, all 674 cells | **deployment** |

Build: `scripts/build_emulator_release_non.py --kind fold|deploy --out DIR` (seconds; three gates). Run, time and
check: `scripts/run_emulator_non.py --release DIR --leg mpi-esm1-2-hr_ssp370 [--cap fixed] --check`. Measured:
7.3e-3 core-s per cell-year on one core, ≈ 115–130× fewer core-seconds than the original on the same cells.
Skill = ADR 0342 §7–8 / 0343. Limits: setups exist for the 674 cells only (a new cell needs the original's
1990–2019 state there); the top-metre water capacity stays at its 2019 value.
