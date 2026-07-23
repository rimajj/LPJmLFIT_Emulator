---
name: lpjmlfit-cbinary
description: Build/run the LPJmL-FIT C binary (the numerical-regression oracle + daily data generator) on the PIK cluster — exact module set (json-c 0.13.1 not 0.17), restart-from-spinup subset runs, config-only daily output, lpjcheck pre-flight, SLURM templates, and the individual=true dead-code check. Use whenever running the C oracle, generating daily data, or reasoning about what the FIT config actually executes.
---

# lpjmlfit-cbinary — run the LPJmL-FIT oracle

The C binary is the **oracle** (F_diff must reproduce it — never validate F_diff against itself) and the
daily training-data generator. It is **not** the coupling path (ADR 0014). Source: `/home/jamirp/lpjml56fit`
(v5.6.004); binary `bin/lpjml` (rebuilt to emit daily grass GPP/NPP; pristine backup `bin/lpjml.pre_dgrass.bak`).

## Modules (exact — nothing else)

```bash
source /etc/profile.d/00-modulepath.sh; source /etc/profile.d/modules.sh   # non-interactive shells
module purge
module load intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 netcdf-c curl/8.4.0 expat/2.5.0
```

**json-c 0.13.1, NOT 0.17.** The login default auto-loads `json-c/0.17` (→ `libjson-c.so.5`) which
**aborts**; the binary needs `libjson-c.so.4` from 0.13.1. A source rebuild also needs a local
`json_object_iterator.h` shim on `CPATH` (this cluster's 0.13.1 headers are truncated).

## Pre-flight (validate without running)

```bash
cd <run_output_dir>       # relative output/ paths resolve here
/home/jamirp/lpjml56fit/bin/lpjcheck -DFROM_RESTART <config.js>
```
Checks parse + input/restart headers + disk estimate.

## Subset run from the full-grid restart

- Set integer **0-based POSITIONAL** `"startgrid"/"endgrid"` = grid-file row indices (not lat/lon, not
  1-based, not `"all"`). Per-cell seek is MPI-decomposition-independent; needs byte-identical grid/soil/
  input + matching physics config.
- **Hainich (DE-Hai) = global orderA index `42490`** (lat 51.25/lon 10.25). `28008` is Hainich only in
  the repo `-DSINGLESITE` grid (= Sonoran desert in the global grid).
- `restart_1999.lpj` = spin-up end → use for the Historical 2000–2019 daily re-run. `restart_2019.lpj` =
  historical end → only the SSP370 continuation.

## Daily output = config-only (never recompile for it)

Put `"timestep":"daily"` inside each output entry's `"file"` object; keep the `ind` tree table **annual**.

## SLURM helpers (run off the login node)

- `scripts/run_daily_subset.sh` — **env-var driven** (not positional): `STARTGRID`, `ENDGRID`, `SCENARIO`,
  `NTASKS`, `TIME`, `EXCLUSIVE`, `RUNTAG`, `SUBMIT`, `RANDOM_SEED`, optional `FIRSTYEAR`/`LASTYEAR`. Generates
  config from the production sections, runs `lpjcheck`, submits. Output → `/p/tmp/jamirp/esm_land_daily`. Now
  emits annual `lai_stand`/`fpc_stand` (the runtime-consistent S `lai` feature, replacing the proxy) alongside
  the daily water/carbon block.
  - **`SCENARIO=historic`** (default): obsclim GSWP3-W5E5, `restart_1999.lpj`, 2000–2019, VARYING TRENDY v12 CO2.
  - **`SCENARIO=ssp370`**: MPI-ESM1-2-HR ssp370 forcing (`ssp370/{tas,pr,rsds,lwnet,huss}_..._2015-2100_orderA.clm`),
    `restart_2019.lpj`, 2020–2100, **CONSTANT 409.63 ppm CO2** (2019 value held flat — the `with_nitrogen="no"`
    constant-CO2 regime, DEVELOPMENT_PLAN §3). Byte-consistent with the annual `ind_ssp370_seed1` run
    (`.../ssp370/ground_truth/.../transient_2020_2100_npatch25_random_seed1`). Full-global ≈ **768 GB**, ~2–3 h
    on 2048 tasks. Example: `SCENARIO=ssp370 STARTGRID=0 ENDGRID=67419 NTASKS=2048 EXCLUSIVE=yes TIME=08:00:00 RUNTAG=global SUBMIT=yes bash scripts/run_daily_subset.sh`.
- `scripts/run_fdiff_validation_cell.sh` — single-cell daily re-run adding daily FAPAR/NV_LAI + annual FPC/LAI_STAND (~9 s).
- `scripts/run_fdiff_grass_gpp_cell.sh` — single cell 2000–2019 daily grass GPP.
- `scripts/water_closure_check.py <run_dir>` — dask-lazy water closure verify.
- Keep the `.jl`/`.sh` and `--output` on shared `/p` (never `/tmp/claude-*`).

## Closure = the run itself

`-DSAFE` `check_fluxes.c` aborts a cell if `|balanceW| > 1.5 mm/yr` — **a clean run IS water closure.**
`swc` is FRACTIONAL saturation (no `wsats` output ⇒ absolute mm not reconstructable); `swe`/`rootmoist` are mm.

## Before porting any C routine as "the faithful fix"

This config runs `"individual":true`, `with_nitrogen="no"`, `landusetype=NATURAL`, carbon-only. **Many C
paths are gated `if(!config->individual)` or are diagnostic-only — confirm the routine actually executes**
(grep `config->individual` / `config->with_nitrogen` / `nitrogen_coupled` guards) before trusting it.
Known dead paths in this config: `light()`/`light_grass()` (grass cover/light competition — active
reduction is `reduce_grass`, fpc-only); per-PFT `gp_pft`/`gc_pft` into GPP (diagnostic; GPP uses stand-mean
`gp_stand`). Active param file is `par/pft_lpjmlfit.js` (beech = ANGIO allometry), NOT `par/pft.js`.
`-DPERMUTE` is active ⇒ daily PFT-depletion order is randomized (non-deterministic / order-averaged), which
is why a faithful per-PFT competitive-supply port is neither differentiable nor deterministic.
