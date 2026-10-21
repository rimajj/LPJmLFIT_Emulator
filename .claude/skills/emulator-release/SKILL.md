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

## Run / reproduce / time (one core, ~11 min for 1 050 cells x 81 years)
```bash
python scripts/run_emulator.py --release <dir> --run 4 --leg gfdl-esm4_ssp370_daily --check   # fold release
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
* Score the YEAR-BY-YEAR map (what ships) with `final_structure_score.py`, not the 30-yr window map's
  `explore_relaxed_standard.py` numbers.
