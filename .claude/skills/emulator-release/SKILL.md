---
name: emulator-release
description: Build, gate, run and time a RELEASE of the whole learned LPJmL-FIT emulator (ADR 0340) — the numpy + LightGBM package python/src/lpjmlfit_emulator/landemu (LandEmulator, Setup), scripts/build_emulator_release.py (deployment `v1` or a `--hold-gcm` fold release; three gates numpy==PyTorch, climate stats==pipeline, anchors==test rows), scripts/run_emulator.py (81-year run from daily weather, one-core timing, `--check` reproduction against the scored predictions), and the final scorers scripts/final_structure_score.py (relaxed standard on the year-by-year map the emulator runs) and scripts/final_daily_score.py (ADR 0325 numbers from f2_relative_score output). ALSO the nitrogen-on releases with a CO2 input (ADR 0344: scripts/build_emulator_release_non.py, scripts/run_emulator_non.py, step_year(..., co2=ppm), release/non_v1 + non_fold_v1). Use whenever retraining/rebuilding the emulator, changing any of its parts (daily networks, structure/stand maps, cover mode), quoting its accuracy or speed, or wiring it into an ESM.
---

# Emulator release

Guide for users: `docs/emulator_release.md`. Verdict and gates: ADR 0340.

## Build (SLURM; ~5 min, ~120 GB for the training table)
```bash
NCPUS=48 TIME=04:00:00 scripts/sbatch_python.sh release-<tag> scripts/build_emulator_release.py \
    --out /p/projects/open/Jamir/esm_land_emulator_data/release/<name> [--hold-gcm gfdl-esm4] [--cover-mode additive]
```
Refuses an existing directory (never overwrite). Gates abort the build before anything else is written.
`--departure dep` (ADR 0358, the current releases `v2` and `fold_gfdl-esm4_v3`): adds the weather-driven
departure model of tree count and biomass per tree (trained by `explore_panel_yearly_drift.fit_departure`, GATE (4)
z-scores package == training table); `--check` then compares the structure with `preds_<g>_statedep_fx`
(`release.json` `struct_pred_suffix`). Measured: check OK except the known fpc7/fpc8; 7.0e-3 core-s per cell-year.
`--daily-members <prefix>` (default `D_3x256_seed`, ADR 0362): which five f2 networks ship; depth is read from each
saved network. `DCL4_3x256_seed` = the 4-layer ensemble (ADR 0359) → `release/v3` + `fold_gfdl-esm4_v4`, 9.8e-3 core-s
per cell-year; check its fold with `--check-tag PD_L4_fx`. NOT current: v2 / fold v3 stay the releases (owner, ADR 0362 — same accuracy in the complete emulator, 40 % slower).

## Swap ONLY the daily networks of an existing release (ADR 0367; seconds per release, no retraining)
```bash
python scripts/build_release_daily_swap.py --base .../release/v2 --out .../release/v2tex \
    --daily-members T_3x256_seed --soil-texture        # texture networks of ADR 0348
```
Copies every file but `daily.npz` / `release.json` (not `runs/`), exports `<prefix>0..4`; gates (1) numpy==torch,
(T) package soil columns == `f2_train.soil_columns` for every setup's cells, (C) copies byte-identical. Texture
releases: `daily.npz` carries `soil_table` (13 codes x sand, clay, ln Ks, ln Sf; float32 as the trainer computes them)
and `release.json` `soil_texture: true` — `LandEmulator` asserts the two agree and looks the setup's `soil_code` up;
releases without the table run exactly as before. Built: `v2tex`, `fold_<g>_v3tex` (5 models). Not deployment
releases unless ADR 0367 Part A adopts texture. `run_emulator_npp.py --variant tex` runs them for the mortality model
(arm `BCET` of `explore_panel_treemort.py`; score with `--out-suffix` so earlier score files stay).

## Weather-memory daily networks (ADR 0372): `release/non_fold_v2mept` (nitrogen-on, fold split)

```bash
python scripts/build_release_daily_mep.py --base .../release/non_fold_v1 --out .../release/non_fold_v2mept --arm MEPt
python scripts/run_emulator_non.py --release .../release/non_fold_v2mept --leg mpi-esm1-2-hr_ssp370 --check \
    --check-tag none --check-ens .../xtf/daily/ens/MEPt__stand_emul_main2/annual.npz   # NC_B3 check is the OLD nets
```
Networks = `xtf/daily/runs/MEPt_s0..4` (`xtf_daily.py train --arm MEPt`): the deployed MLP + 32 exponential running
means of the weather + a 52-number place description of the 30 years before EACH year (MEPh = fixed 1990–2019).
`daily.npz` declares `ema_tau` + `place_mode`; setups gain `place_mon/s1/s2` (30 yearly summaries: observed GSWP3-W5E5
1990–2018 from `xtf_daily.hist_raw()` + the setup's own 2019 `warm`); `DailyState.end_year` rolls the trailing
description. Releases without those keys run bit for bit as before. Gates in the builder: (1) numpy==torch with the
extras, (E) online extras == `xtf_daily.Extras` over 3 years, (S) setup arrays unchanged — compare NaN-aware, the
anchors carry NaN for treeless cells — (C) copies. Measured: error vs `non_fold_v1`'s networks GPP −12.5 %, NPP −17 %,
ET −10 %, runoff −9.5 %; end-to-end 8.03e-3 vs 7.14e-3 core-s per cell-year. A deployment build on all 10 climate
models does not exist yet (retrain MEPt on all legs first).

## Tree-population outputs (ADR 0363 + 0365): release `v4` = v2 + population, `fold_gfdl-esm4_v5` = fold v3 + it
```bash
NCPUS=32 TIME=02:00:00 scripts/sbatch_python.sh poprel-<tag> scripts/build_population_release.py \
    --base .../release/<base> --out .../release/<new>      # copies the base unchanged, adds 79 lgb_pop_* + popsetups
python scripts/run_emulator.py --release <dir> --run 1 --leg ukesm1-0-ll_ssp370 --cap fixed --population
python scripts/run_emulator.py --release .../fold_gfdl-esm4_v5 --run 4 --leg gfdl-esm4_ssp370_daily --population \
    --check --check-tag PD_B_fx     # + pop_* vs eval/popmap/preds_<g>_<var>.parquet AQ, indices vs idx_emu_<g>_unique
```
Outputs are prefixed `pop_` (the four trait medians also exist as structure outputs — an unprefixed first version
overwrote them). Gates: fold anchors exact; 7 of 8 variables reproduce the scored models to ~1e-15; **Age's LightGBM
fit is not reproducible run to run** (two refits differ, median 0.18 yr) ⇒ its gate is ≤ 2× the refit-to-refit spread
(needs `POPMAP_SFX=_refit` and `_refit2` refits of `explore_panel_popmap.py fit --g <g> --group Age`). Cost +7 %
(7.67e-3 vs 7.14e-3 core-s per cell-year); virtual trees + indices 6.8e-3 each time requested. Pipelines behind it:
skill `tree-population`.

## Run / reproduce / time (one core, ~11 min for 1 050 cells x 81 years)
```bash
python scripts/run_emulator.py --release <dir> --run 4 --leg gfdl-esm4_ssp370_daily --check --check-tag PD_B_fx  # fold release
python scripts/run_emulator.py --release <dir> --run 1 --leg ukesm1-0-ll_ssp370 --cap fixed    # deployment
```
Legs are the f2 array names (`*_daily` for GFDL/IPSL/MRI). Measured: 7.5e-3 core-s per cell-year.

## Global (full-grid) retrain + run on Billing's runs (ADR 0341)
`scripts/glob_emu.py` stages `static → yearly/stand <scen> → train --fold {none,ssp126,ssp245,ssp370} → prep →
runall --scen historical (then each ssp) → assemble --scen → layout → score`; data
`/p/projects/open/Jamir/esm_land_emulator_data/global_emu/`. Anchor = the cell's own 1985–2014 state (constant),
leave-one-scenario-out folds; daily model = release v1's (these runs have no daily output). `runall` = 64 one-core
chunk processes on one `priority` node (~6 min historical, ~12 min per 86-yr leg). Benchmark with the lpjml-fit tools
UNCHANGED: `scripts/glob_emu_bench.sh prep|lpjmlstats|ilamb|join` (converter `chunks:` source + `--unreduced`).

## Nitrogen-on releases with a CO2 input (ADR 0344)
```bash
P=/home/jamirp/.conda/envs/py311_new/bin/python   # build: seconds; run: ~7 min on one core
$P scripts/build_emulator_release_non.py --kind fold|deploy --out .../release/<name>
$P scripts/run_emulator_non.py --release <dir> --leg mpi-esm1-2-hr_ssp370 [--cap fixed] --check
```
`fold` = maps `clu_non/maps/main2` + daily `f2_non/runs/NC_s0-4` (check vs `main2/preds.parquet` and `NC_B3`:
maps bit-identical, daily 1e-7); `deploy` = maps arm `deploy` (`clu_emu_maps.py train/predict --arm deploy`) +
`NCD_s0-4` (`f2_train.py ... --co2 --all-cells --train-legs <all 58>`). `step_year(..., co2=ppm)` is required by a
CO2 release and refused by nitrogen-off ones (`release.json` and `daily.npz` `co2_input` must agree). One setup
`setup_s2.npz` (674 cells, fixed per-cell anchors ⇒ no last year); the run script reads forcing from the `.clm`
files exactly as the training climate table did, and overrides the setup's Jan-1 stores with the leg's own.

## Traps
* A gate scaled by a 90th-percentile size fails falsely on snow change (~0 on most days): scale by the column's max.
* `--check` structure/stand differences in rare cell-years are the training table's float32 0.1 °C scale counting
  exactly-30.0 °C days as hot (ADR 0340 §3), not a package error; daily fluxes must agree to ~1e-3.
* **Set the one-thread BLAS limit BEFORE numpy is imported** when running many chunk processes on one node: set
  inside `main()` it is too late and each process starts ~200 threads (load 1 000+ on 128 cores, 2× slower).
* The anchors limit where it runs: release v1 setups exist only for the 1 050 panel cells and years 2020–2100;
  the nitrogen-on setups only for the 674 clustered cells (fixed anchors, any year).
* ⚠ **Held-out-leg leak, fixed 2026-10-21 (ADR 0352 §0):** before then the yearly structure map and the stand map
  trained on run m5 ON THE HELD-OUT LEGS (m5 is a training run AND the test-side harness), flattering held-out-model
  errors by 7–12 % (relaxed standard 21 → 18 of 22 once fixed). Leak-free predictions end `_fx`
  (`SUFFIX=_fx`); quote structure accuracy only from those. Sanity check on any fit log: training rows must equal
  runs × training legs × training years × 1 050 cells. All scores of one variant:
  `scripts/score_yearly_map_variant.sh <suffix> [fit args]`.
* **Drought die-off arms (ADR 0354/0355, none adopted):** `explore_panel_yearly_drift.py fit --state dep|depnw|depw`
  keeps the map as the level and adds a departure model run forward year by year (`dep` 20 of 22, capture 0.18;
  `depw` adds the daily bucket statistics of `scripts/build_panel_bucket_stress.py calib|build|check|events`,
  capture 0.25). Their fit log prints a LEVEL HARNESS line that says FAIL on max difference — read it as ADR 0354
  §5a (median 0, ≥ 99.5 % of rows ≤ 1e-6; LightGBM rerun noise). Score with
  `scripts/score_yearly_map_variant.sh _statedep_fx --state dep` (or `_statedepw_fx --state depw`).
  ⇒ the validated fold release is **`fold_gfdl-esm4_v2`** (leak-free, ADR 0353); its `release.json` carries
  `pred_suffix: "_fx"`, which `--check` reads. Its check flags `fpc7`/`fpc8` "DIFFERS" exactly as v1's did (the hot-day
  threshold trap above) — that is the expected result, not a regression. Leak-free stand-map files end `_fx` too
  (`explore_panel_stand_map.FX`), the leak-free whole-emulator daily run is `PD_B_fx` (`f2/runs/relative_score_PD_ADR0353.md`).
* Score the YEAR-BY-YEAR map (what ships) with `final_structure_score.py`, not the 30-yr window map's
  `explore_relaxed_standard.py` numbers.
