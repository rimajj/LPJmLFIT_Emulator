---
name: daily-model
description: Build, train, free-run and score the LEARNED daily water-carbon model (EXECUTION_PLAN arm F2; ADR 0320 pre-registration, ADR 0321 results) — the network that replaces the original's daily GPP/NPP/transpiration/evaporation/interception/runoff/snow/soil-water step, with snow, top-metre and deep water stores closed by construction. Use whenever (re)building its training arrays from the panel runs of the original, training a new arm (network size, sample count, new inputs/targets), free-running it, scoring it against the bar (since ADR 0325: error RELATIVE TO A SECOND RUN of the original + no drift relative to the original, scripts/f2_relative_score.py; the old ±5 % of ADR 0320 is superseded), timing its per-cell-year cost, or answering "how good is the learned daily exchange". Names scripts/f2_build_daily_table.py, scripts/f2_train.py, /p/projects/open/Jamir/esm_land_emulator_data/f2/ (forc_/daily_/stand_/cap_m<k>_<leg>.npy, cells.parquet, runs/<tag>/summary.md), the held-out blocks and legs, and the traps: the rising-CO2 hist leg, the shuffled control years, and the ill-conditioned area-summed response ratio.
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
#    --seed N for a replicate. Ensemble (ADR 0322, no training; averages the members' daily fluxes, one bucket):
#    scripts/f2_train.py --tag <new> --hidden 256 --layers 3 --ensemble tagA,tagB,...
#    Chain it after the member jobs with DEPENDENCY=afterok:<jid>:<jid> (wrapper knob).
#    --deep-tau 365 (ADR 0326, ADOPT for every new arm): the deep store drains D/365 per day into runoff; only
#      runoff + the deep store change (re-score an existing tag/ensemble under a NEW tag, no retraining).
#    --drop-inputs huss (ADR 0327): hold a raw forcing input at 0 (pass it again for the ensemble run).
#    --train-only: save model.pt and stop — for ensemble members (the GPU QOS runs ~2 jobs at a time, and a
#      member's own 20-min free runs are not needed when the verdict is on the ensemble).
#    python scripts/f2_extrapolation_probe.py <tag>: per held-out cell, how far each leg's 2081-2100 climate is
#      outside the training range vs where the carbon error grows (minutes; ADR 0327 §1).
#    --train-legs / --test-legs a,b,c (ADR 0328): any legs with f2 arrays, e.g. the `<model>_<scen>_daily` re-runs
#      (written to runs/<tag>/legs.json; f2_relative_score.py scores each run on its own legs).
#    scripts/f2_chain_new_legs.py: after new daily runs of the original, chains collect -> build -> train -> score.
#    --carbon-head physical (ADR 0332): GPP = eps * rsds * (1-exp(-0.5 LAI)) * four bounded limiters with
#      disjoint inputs, NPP from the original's respiration form; chain scripts/f2_chain_carbon_head.py.
# 2b. compare arms in one table:  python scripts/f2_compare.py [tags...]   (old ADR 0320 ±5 % bar)
# 2c. THE CURRENT YARDSTICK (ADR 0325): python scripts/f2_relative_score.py [tags...]  -> per leg/flux the
#     emulator error / second-run error (30-yr typical + worst-10 %, response, per-decade single-year),
#     drift = last-20-yr / first-20-yr ratio (owner: drift is the gap to the original GROWING, not the values
#     changing), area totals; harness rows must read ~1.0 (second run) and ~0.82 (mean of three runs).
# 2d. WHICH HALF OF THE CARBON GAP: python scripts/f2_carbon_split.py [tags...] -> per leg, emulator / original
#     summed over held-out cells for GPP and plant respiration (GPP - NPP), early vs late, + share of cells low.
#     Read it before designing a carbon fix: ADR 0332 found a late-century GPP shortfall (UKESM 0.970) AND a
#     separate constant respiration excess (1.5-3 % on every leg, observed weather included).
# 3. read DATA/runs/<tag>/summary.md (+ summary.json: pass flags, per-cell response, bucket diagnostics)
```
Re-score saved annual totals without a model: `import f2_train as F; F.score(ann, cells_df)` with `ann` from
`runs/<tag>/annual.npz` (keys `<kind>__<leg>`, kinds truth/free/onestep/clim).

## Venue and splits (fixed by ADR 0320 — do not change for a new arm)

Panel runs of the original (skill `trackd-data`): 1 050 cells, 4 members; legs with daily output used:
`ctl_obs`, `mpi-esm1-2-hr_ssp126/370` (train), `mpi-esm1-2-hr_ssp585`, `ukesm1-0-ll_ssp370` (held out). Since ADR
0328 also `{gfdl-esm4,ipsl-cm6a-lr,mri-esm2-0}_{ssp126,ssp370,ssp585}_daily` (arm C trains on GFDL + MRI; IPSL and
UKESM are the unseen models). 24
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
- **A single network's NPP level wanders by several % between seeds** (ADR 0322): never claim a pass from one
  seed — replicate, or pre-register an ensemble. More rows from the same cells did not help (the limit is places).
- Speed (S1) is measured on one CPU core with a batch over all panel cells and incrementally updated running
  windows. It is the daily half only; never quote it as an emulator-vs-original speed-up (skill `speed-gate`).
- **Runoff is a small residual of rain minus ET** (ADR 0326 §4): in a typical cell runoff is 160–200 mm/yr, so an
  ET error of 2–3× a second run is 4–7 % of runoff = 4–5× a second run's runoff spread. With the deep store
  draining, the runoff error is the negative of the ET error (cell correlation +0.84–0.92). Fix ET to fix runoff.
- **Humidity does not enter the original's daily exchange** (only `waterstress_tree.c:36`, the annual tree
  mortality accumulator; `relative_humidity: false`, fire = the simple scheme). Under warming it leaves the
  training range at every cell (UKESM 2081–2100: +1.45 g/kg beyond, ADR 0327).
