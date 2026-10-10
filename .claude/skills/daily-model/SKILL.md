---
name: daily-model
description: Build, train, free-run and score the LEARNED daily water-carbon model (EXECUTION_PLAN arm F2; ADR 0320 pre-registration, ADR 0321 results) — the network that replaces the original's daily GPP/NPP/transpiration/evaporation/interception/runoff/snow/soil-water step, with snow, top-metre and deep water stores closed by construction. Use whenever (re)building its training arrays from the panel runs of the original, training a new arm (network size, sample count, new inputs/targets), free-running it, scoring it against the pre-registered bar, timing its per-cell-year cost, or answering "how good is the learned daily exchange". Names scripts/f2_build_daily_table.py, scripts/f2_train.py, /p/projects/open/Jamir/esm_land_emulator_data/f2/ (forc_/daily_/stand_/cap_m<k>_<leg>.npy, cells.parquet, runs/<tag>/summary.md), the held-out blocks and legs, and the traps: the rising-CO2 hist leg, the shuffled control years, and the ill-conditioned area-summed response ratio.
---

# daily-model — the learned daily water–carbon model (phase A, offline)

**What it is.** One small network per day per cell: inputs = today's weather (tas, pr, rsds, lwnet, huss) +
trailing windows (tas 10/30 d, rsds 30 d, prec 30/90/365 d) + calendar/latitude/day length + yesterday's stores +
the previous year's stand (lai_stand, vegc, fpc_stand bands 1–10). Outputs feed a closed bucket (snow, top metre
with capacity Σ_{l<3} whc_nat·dz, deep store) so `prec − ET − runoff = Δ(stores)` exactly. Design and bar: ADR 0320.
Results so far: ADR 0321 (and later records citing it).

## Run it

```bash
# 1. arrays (once; ~2 min on 32 cpus, 35 GB; gates: forcing == the run's own daily prec at every cell/day)
PARTITION=priority QOS=priority NCPUS=32 TIME=04:00:00 scripts/sbatch_python.sh f2-build scripts/f2_build_daily_table.py
# 2. an arm: train + 81-yr free runs of 4 members x 5 legs + one-step + climatology null + score + 1-core timing
PARTITION=gpu QOS=gpushort GRES=gpu:1 NCPUS=16 TIME=04:00:00 \
  scripts/sbatch_python.sh f2-train-<tag> scripts/f2_train.py --tag <tag> [--hidden 256 --layers 3 --nsamp 40000000]
#    160 M samples needs NCPUS=32 (host RAM). Rerunning a tag whose model.pt exists skips training (re-scores).
# 3. read DATA/runs/<tag>/summary.md (+ summary.json: pass flags, per-cell response, bucket diagnostics)
```
Re-score saved annual totals without a model: `import f2_train as F; F.score(ann, cells_df)` with `ann` from
`runs/<tag>/annual.npz` (keys `<kind>__<leg>`, kinds truth/free/onestep/clim).

## Venue and splits (fixed by ADR 0320 — do not change for a new arm)

Panel runs of the original (skill `trackd-data`): 1 050 cells, 4 members; legs with daily output used:
`ctl_obs`, `mpi-esm1-2-hr_ssp126/370` (train), `mpi-esm1-2-hr_ssp585`, `ukesm1-0-ll_ssp370` (held out). 24
held-out blocks = the five biome blocks + the lowest non-biome block of every stratum with ≥ 2 blocks.

## Traps

- **The `hist` leg runs with RISING CO2** (TRENDY file) while every other leg is constant 409.63 ppm. The emulator
  must not see CO2 (ADR 0004/0107) → `hist` is never trained or scored on; it only supplies the end-of-2019 stand
  and capacity.
- **`ctl_obs` years are shuffled, with a DIFFERENT sequence per member.** The builder recovers it by matching each
  year's daily prec against observed 1990–2019 (exact, 0.0 error); `manifest.json` stores it. Never assume member 1's
  sequence for another member.
- **Do not score the warming response as a ratio of area-summed changes.** Tropical losses cancel boreal gains, so
  the original's net change is 5–12 % of its summed per-cell change and the ratio swings from −2 to +3 on tiny
  errors (ADR 0321 §3.1 — it produced a wrong "under-responds" reading once). Use the per-cell correlation / slope
  / RMSE that `summary.json` reports under `response_per_cell`.
- **±5 % (the plan's bar) is looser than the original's own run-to-run spread (~1 %).** Quote both.
- `rootmoist` tops out at the capacity computed from **that month's** whc_nat; the arrays store a year mean, so
  `rootmoist/cap` reaches 1.002 — a few mm/yr of overflow in a free run are this, not a model fault.
- The deep store `D` is never an input (it has no known level); its drift is a diagnostic of the deep/runoff
  split, and the original's own is a median 0.22 m over 81 years.
- Speed (S1) is measured on one CPU core with a batch over all panel cells and incrementally updated running
  windows. It is the daily half only; never quote it as an emulator-vs-original speed-up (skill `speed-gate`).
