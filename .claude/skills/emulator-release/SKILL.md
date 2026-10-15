---
name: emulator-release
description: Build, gate, run and time a RELEASE of the whole learned LPJmL-FIT emulator (ADR 0340) — the numpy + LightGBM package python/src/lpjmlfit_emulator/landemu (LandEmulator, Setup), scripts/build_emulator_release.py (deployment `v1` or a `--hold-gcm` fold release; three gates numpy==PyTorch, climate stats==pipeline, anchors==test rows), scripts/run_emulator.py (81-year run from daily weather, one-core timing, `--check` reproduction against the scored predictions), and the final scorers scripts/final_structure_score.py (relaxed standard on the year-by-year map the emulator runs) and scripts/final_daily_score.py (ADR 0325 numbers from f2_relative_score output). Use whenever retraining/rebuilding the emulator, changing any of its parts (daily networks, structure/stand maps, cover mode), quoting its accuracy or speed, or wiring it into an ESM.
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

## Traps
* A gate scaled by a 90th-percentile size fails falsely on snow change (~0 on most days): scale by the column's max.
* `--check` structure/stand differences in rare cell-years are the training table's float32 0.1 °C scale counting
  exactly-30.0 °C days as hot (ADR 0340 §3), not a package error; daily fluxes must agree to ~1e-3.
* The anchors limit where it runs: setups exist only for the 1 050 panel cells and years 2020–2100.
* Score the YEAR-BY-YEAR map (what ships) with `final_structure_score.py`, not the 30-yr window map's
  `explore_relaxed_standard.py` numbers.
