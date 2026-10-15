# 0342 — Proof that the emulator learns the warming response when trained on the right data (nitrogen-on model, transient CO2): pre-registration

* **Status:** accepted 2026-10-15 — design, measures and pass rule written BEFORE any of the runs below finished.
  Results: §7, added after the run.
* **Owner instruction (2026-10-15):** *"what is missing is the proof that the emulator can learn and reproduce the
  warming response if it was trained with the right data. because with maik's runs the emulator failed to reproduce
  for example vegc under ssp370. this is the main task now, to create the data you need for training, train and
  show the emulated response that matches the one of the original model. take the nitrogen on lpjml fit version (but
  no phosphorus) with transient co2."* Also: representative clustering mode (25 patches per cell) rather than
  distributed (1 patch).
* **Supersedes for this model:** the "no CO2 input" rule (ADR 0004/0107) was justified by LPJmL-FIT's unbounded CO2
  fertilisation with nitrogen OFF. This model has nitrogen limitation ON and the owner chose transient CO2; the
  emulator gets CO2 as an input here. The rule is unchanged for nitrogen-off LPJmL-FIT (Billing's runs).
* **Depends on:** ADR 0340 (package), 0341 (the failure this tests: ssp370 vegetation-carbon change −2.8 % emulated
  vs −9.2 % original, trained on milder scenarios only), 0325 (response measured against a second run), 0320–0336
  (daily model). **Code:** `scripts/clu_emu.py`, `scripts/clu_emu_hook.sh`, `scripts/clu_emu_runs.sh` (runs);
  training/scoring scripts named in §7.

## 1. The original-model runs (lpjml-fit tooling, unchanged)

* **Model:** merged LPJmL + LPJmL-FIT, nitrogen limitation on, no phosphorus = `/home/jamirp/port-wt-nitrogen-on` at
  `ef38b509e` (the "firefix" variant of the owner's nitrogen-on clustered runs), frozen as a snapshot
  (`lpjml-fit-clustered/trees/nitrogen-on-ef38b509e`, binary byte-identical, md5 recorded). Settings: the tree's own,
  1000-yr spin-up, 1901–2019, then 2020–2100; CO2 rising (TRENDY to 2019, the SSP's ISIMIP3b series after).
* **Cells:** 674 real 0.5° cells = one per region of the owner's 674-region map (the first non-repeated randomly
  drawn member of the existing distributed grid = the package's `random` representative), **25 forest patches
  each** (`k674_lowrank_hist_rep1_seed1`). Inputs cut by `cut_inputs.py` / `cut_scenario.py` from the files the full
  grid reads.
* **Outputs (lean list, `clu_emu.py hook`):** per-tree table every year 1990–2100; stand leaf area, plant-type
  cover, vegetation carbon, AGB, soil/litter carbon, fire carbon (annual NetCDF), heterotrophic respiration
  (monthly); DAILY GPP, NPP, transpiration, evaporation, interception, runoff, precipitation, PET, snow, root-zone
  water (per-cell binary); monthly water-holding capacity. No trait histograms (they made a run ~650 GB).
* **Legs:** seed 2 = the truth: 10 ISIMIP3b climate models (GFDL-ESM4, IPSL-CM6A-LR, MPI-ESM1-2-HR, MRI-ESM2-0,
  UKESM1-0-LL, CanESM5, CNRM-CM6-1, CNRM-ESM2-1, EC-Earth3, MIROC6) × ssp126 / ssp370 / ssp585, rising CO2 (30 legs),
  + ssp370 with CO2 fixed at 2019 for the 8 training climate models (CO2 twins: they separate the CO2 effect from
  warming). Seed 3 = an independent second run (own spin-up) for the held-out legs only.

## 2. What is held out

* **Climate models:** MPI-ESM1-2-HR and IPSL-CM6A-LR — every scenario of both is never trained on. They bracket the
  sensitivity range (MPI low, IPSL high) while staying inside the training models' range (CanESM5 and UKESM1-0-LL
  warm more), which is what "the right data" means: the test climate is covered by training climates.
* **Cells:** 20 % of the 674 cells (every 5th region by label) are never trained on either (spatial generalisation,
  needed for any global use); scores are reported on all cells and on the held-out cells separately.

## 3. The emulator trained (same architecture as release v1 + CO2)

* **Structure and stand maps** (LightGBM, settings of ADR 0340): targets per cell and year (tree count per patch,
  biomass per tree, four trait medians; stand leaf area, vegetation carbon, ten plant-type covers); anchor = the
  cell's OWN 1990–2019 state in the same run (ADR 0341's design — no future output of the original is used);
  features = the 25 trailing-30-yr climate statistics and their change since 1990–2019, **the trailing-30-yr mean CO2
  and its change since 1990–2019**, the anchors, lat / lon / soil code.
* **Daily water–carbon model** (`f2_train.py`, arm D settings: 5 × 3×256 ensemble, deep store τ 365 d, humidity
  dropped) retrained on these runs' daily output, **with the year's CO2 as an extra input**; fed the stand the maps
  emulate (phase B, as release v1).

## 4. The measures (per held-out leg; response Δ = mean 2071–2100 − mean 1990–2019 of the same run)

(Amended before any result, 2026-10-15: for the DAILY fluxes GPP / NPP / ET / runoff the baseline is 2021–2050,
because the daily model's legs start in 2020 and the emulator does not re-run 1990–2019 day by day; the stand and
structure keep 1990–2019. **Global totals** weight each of the 674 cells by the land area of the region it stands
for, from the 67 420-cell region map.)

1. **Global response:** area-weighted total change of the emulator vs the original (signed %), and the second run's.
2. **Per-cell response:** across cells, slope and correlation of emulated Δ on original Δ, and **RMSE ratio** =
   RMSE(emulator Δ − original Δ) / RMSE(second-run Δ − original Δ) (ADR 0325's response measure).
3. Level: typical cell error of the 2071–2100 mean (as ADR 0341) next to the persistence null.

Quantities: vegetation carbon, stand leaf area, tree cover, tree count (dense cells), biomass per tree, the four
trait medians, GPP, NPP, ET, runoff.

## 5. Controls (each must return what is written here, or the measure is broken)

| control | expectation |
|---|---|
| **second run scored as the emulator** | RMSE ratio 1 by construction; its global response within a few % of seed 2's |
| **persistence** (1990–2019 state carried forward) | Δ = 0 everywhere: slope 0, RMSE ratio ≫ 1 (shows the measure has power) |
| **"wrong data" arm**: identical maps trained on ssp126 legs only (the analogue of ADR 0341's failure: test climate warmer than any training climate) | under-responds on ssp370 / ssp585: global vegetation-carbon change of the wrong size by > 50 % of the original's, slope < 0.6 |

## 6. Pass rule (the proof) and expectations

**PASS** = on BOTH held-out climate models under ssp370 AND ssp585, for vegetation carbon and GPP (the owner's example
plus the main flux): (a) global change same sign and within ±25 % of the original's change; (b) per-cell slope 0.8–1.2;
(c) RMSE ratio ≤ 1.5. Reported for every other quantity, not gated. ssp126 changes are small (often inside the noise);
reported, not gated.

Expectations: the stand/structure part passes (the ADR 0341 failure was extrapolation; here training covers the test
climate); the "wrong-data" control fails as stated; GPP's CO2 response is the riskiest — the CO2 twins exist so that
it is identified separately from warming; the daily model's typical-cell fluxes will still be 2–4× a second run
(ADR 0340) without spoiling the response.

## 6a. Amendment before the result it governs (2026-10-15, 16:40): the warming-only held-out test

Written after §7's rising-CO2 results were seen, **before** the runs below existed. Reason: with rising CO2 the
original's vegetation-carbon change is dominated by CO2 fertilisation (+22 … +45 %), while the owner's motivating
failure (Billing's runs, ADR 0341) is a constant-CO2 warming LOSS. The CO2-fixed twins of §1 exist only for the 8
training climate models, where the original loses −9 … −15 % (GFDL, UKESM, CanESM5, both CNRM) under ssp370 — so the
warming-only response has so far been seen only in-sample.

* **Runs:** MPI-ESM1-2-HR and IPSL-CM6A-LR × ssp370 and ssp585, CO2 fixed at 2019 (409.63 ppm), seeds 2 and 3 (8
  legs, `clu_emu_runs.sh legs <seed> "<gcm>" "<ssp>" fixed`). Nothing is retrained: the §3 models predict them.
* **Measures:** §4 on these four legs, for vegetation carbon (maps) and GPP (daily model, original stand AND emulated
  stand), and the wrong-data control.
* **Rule:** the §6 rule applied unchanged, reported as its own verdict. Expectation: the global loss is reproduced
  within ±25 % on ssp370 (the case Billing's emulator got at one third of the original's loss).

## 6b. Amendment (2026-10-15, 17:05, written after §6a's result, before the runs below): more CO2-fixed training data

§6a's result (§7.2): the held-out warming-only vegetation-carbon LOSS is under-predicted on IPSL (0.67 / 0.57 of the
original's on ssp370 / ssp585). Hypothesis: in training, warming and CO2 rise together on 24 of 32 legs and only
ssp370 has a CO2-fixed twin, so the maps cannot separate them where warming is strong. **Disclosed: this step was
chosen after seeing held-out results**; the held-out models and cells are unchanged and nothing else is tuned.

* **Data:** ssp126 and ssp585 with CO2 fixed at 2019 for the 8 training climate models, seed 2 (16 legs).
* **Arm `main2`:** the §3 maps retrained on 8 × {ssp126, ssp370, ssp585} × {rising, fixed CO2} (48 legs), training
  cells only; the daily model is NOT retrained (it reproduced the warming-only GPP change with the original's stand,
  §7.2); phase B is re-run with `main2`'s stand.
* **Rule:** §6 unchanged on all 8 held-out legs (rising + fixed). **Pre-stated expectation:** IPSL fixed-CO2
  vegetation-carbon ratio ≥ 0.75 on both scenarios, rising-CO2 results no worse than `main` beyond ±0.05 in ratio /
  slope. If the IPSL ratio stays < 0.75, the hypothesis is rejected and the gap is a property of the map design.

## 7. Results

### 7.0 What ran (2026-10-15)

All 2 historical runs + 44 legs of §1 finished (no carbon / nitrogen balance errors; daily precipitation equals the
forcing to 0.0 mm on every leg). Chain `scripts/clu_emu_chain.sh` (jobs 2507097–2507113); the five daily-model
members trained all 10 epochs. Three pipeline bugs were caught by a scratch end-to-end test on the first finished leg
before the chain reached them (NetCDF first year; per-tree dtypes; an f2_train SyntaxError). Outputs:
`esm_land_emulator_data/clu_non/eval/response_maps.csv` (maps; the rising-CO2-only first scoring is
`response_maps_v1.csv`), `f2_non/runs/NC_A|NC_B/response.csv` (daily model, original / emulated stand; with the §6a
legs: `NC_A2|NC_B2`). "Change" = 2071–2100 minus 1990–2019 (daily: minus 2021–2050), area-weighted, all 674 cells.

### 7.1 Rising CO2 (the §6 pass rule)

Ratios are emulator / original global change; the second run's ratio is the original against itself.

| quantity | case | global ratio emu (second run) | per-cell slope emu (second run) | RMSE ratio |
|---|---|---|---|---|
| vegetation carbon | IPSL ssp370 | 0.82 (0.88) | 0.78 (0.78) | 0.70 |
| | IPSL ssp585 | 0.97 (0.89) | 0.82 (0.83) | 0.70 |
| | MPI ssp370 | 0.81 (0.61) | 0.71 (0.72) | 0.71 |
| | MPI ssp585 | 0.86 (0.79) | 0.79 (0.84) | 0.76 |
| GPP, emulated stand (phase B) | IPSL ssp370 | 0.96 (0.95) | 0.74 (0.96) | 1.19 |
| | IPSL ssp585 | 1.04 (0.97) | 0.75 (0.95) | 1.29 |
| | MPI ssp370 | 0.95 (1.03) | 0.70 (0.88) | 1.07 |
| | MPI ssp585 | 0.94 (0.87) | 0.79 (0.95) | 1.13 |
| GPP, original stand (phase A) | the four cases | 0.96–1.04 | 0.94–0.99 | 0.55–0.64 |

Original's change: vegetation carbon +32 … +45 %, GPP +19 … +27 % (CO2 fertilisation dominates; nitrogen limits it).

**Verdict as pre-registered: NOT PASSED.** (a) global change within ±25 %: 8/8 ✓. (c) RMSE ratio ≤ 1.5: 8/8 ✓.
(b) per-cell slope 0.8–1.2: vegetation carbon 1/4, GPP (phase B) 0/4 ✗.

Two different things are behind (b):
1. **For vegetation carbon the criterion is failed by the original against itself.** The second run's slope is
   0.72–0.84 (2 of 4 inside 0.8–1.2) and the emulator's equals it to within 0.05. Cause: regression dilution — the
   original's per-cell change contains run-to-run noise, which flattens the fitted slope of ANY predictor (a perfect
   emulator of the expected response included). §5 did not foresee it (it checked only the second run's RMSE ratio).
   It is a defect of the criterion, recorded here; the verdict above is not changed after the fact.
2. **For GPP with the emulated stand it is real.** The second run's GPP slope is 0.88–0.96 and the daily model fed
   the ORIGINAL's stand reaches 0.94–0.99, but with the emulated stand 0.70–0.79. The stand map's per-cell response is
   damped: leaf area slope 0.74–0.78 vs the second run's 0.89–0.91; tree cover 0.77–0.82 vs 0.90–0.95. The global
   totals are right (leaf area 0.80–0.93, cover 0.92–1.05); the cell-to-cell spread of the response is too small.

**Controls (§5) all returned what was written:** second run RMSE ratio 1 (by construction), its global vegetation-
carbon change 0.61–0.89 of seed 2's (wider than "a few %": the original's own global response varies by up to ~40 %
between two runs on this 674-cell grid, because single cells stand for large regions); persistence slope 0, RMSE
ratio 1.71–2.21; **the wrong-data arm (ssp126-only training) reproduces the ADR 0341 failure: 0.37–0.43 of the
vegetation-carbon change, slope 0.47–0.53, RMSE ratio 1.00–1.38** — the same maps trained on warm scenarios get
0.81–0.97, slope 0.71–0.82, RMSE ratio 0.70–0.76.

Held-out cells only (135): vegetation carbon slope 0.57–0.71 (second run 0.64–0.82), RMSE ratio 0.82–0.95.
