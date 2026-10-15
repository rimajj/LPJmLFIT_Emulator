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

## 7. Results

(added after the run)
