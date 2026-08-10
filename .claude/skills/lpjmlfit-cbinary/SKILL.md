---
name: lpjmlfit-cbinary
description: Build/run the LPJmL-FIT C binary (the numerical-regression oracle + daily data generator) on the PIK cluster — exact module set (json-c 0.13.1 not 0.17), restart-from-spinup subset runs, config-only daily output, lpjcheck pre-flight, SLURM templates, and the individual=true dead-code check. Use whenever running the C oracle, generating daily data, or reasoning about what the FIT config actually executes. ALSO how to REBUILD the binary (target is `make main` not `lpjml`; a new source file needs three edits incl. src/lpj/Makefile; `-Werror`; the json_object_iterator.h shim on CPATH) and the gate you MUST run afterwards — a rebuild changes the reference basis every F-vs-C number is measured against, two builds are never byte-identical (getbuild.c stamps a date), and `cmp` on a NetCDF calls 20 of 21 outputs different for identical physics because LPJmL writes a timestamp into `history`; use scripts/diagnose_cbinary_rebuild_equality.py on DECODED variables with a matched cell set and --ntasks. ALSO the opt-in rung-2 demography hook (LPJ_RUNG2_DIR, patches/lpjmlfit_rung2_demography_hook.patch, ADR 0061): what the pre/post roster dump carries that the `ind` output cannot (water_stress, temp_stress, bm_inc_counter, bm_inc, nind, the carbon pools), that mort_* are valid only at `post`, that recruits enter at age 0, and that neither run wrapper emits `ind` or exports the variable.
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

## Judging a finished run — and the two traps that make a GOOD run look bad

Never judge a C run from SLURM state (the stock jcf always exits 0). Require
`lpjml successfully terminated, <ncell> grid cells processed.` in the log. Two follow-on traps
(ADR 0043, both cost real time):

- **After resubmitting a run, re-point every chained child's log path.** A resubmitted run writes a
  **new** `lpjml_<newjobid>.out`, so a child jcf pinning the old id reads the cancelled attempt's
  **0-byte corpse** — and since an empty log cannot be distinguished from an unfinished one, the child
  reports `no completion line at all` for a run that finished cleanly. Symptom to recognise: a chained
  gate that **fails in ~1 second with most of its data checks passing**, and grandchildren left
  `DependencyNeverSatisfied`. Prefer
  `scripts/diagnose_ind_seed_independence.py --log-dir <run_dir>` (resolves the newest **non-empty**
  `lpjml_*.out`) over naming a job id; an empty log is a provenance FATAL, not a physics verdict.
- **A file-level `cmp` on a NetCDF output is the WRONG equality test.** LPJmL writes a `history`
  attribute holding a wall-clock timestamp + the config path, so runs with identical physics differ in
  the header (the cross-build gate's `vegc` differed by 124 B at byte 172 while **all seven** variables
  hashed identically). Compare **decoded variables** (`netCDF4` + SHA-256 per variable), or the
  timestamp-free text outputs (`globalflux`, `ind`).

**Binary/config equivalence must be a matched-decomposition full-grid run** — a subset re-run cannot
answer it (ADR 0041: the decomposition confound exceeds the signal). The positive control is recorded in
ADR 0043: a faithful full-grid 2048-task re-run reproduced the ssp370 seed1 truth bit-for-bit, including
the 193 GB `ind` roster.

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

## REBUILDING the binary — the exact recipe, and the gate you MUST run afterwards (ADR 0061)

Nothing was gating C rebuilds until 2026-08-10, and the oracle binary is what every F-vs-C number on the
project is measured against. **A rebuild is a change to the reference basis (guardrail 7). Gate it.**

```bash
cd /home/jamirp/lpjml56fit
source /etc/profile.d/00-modulepath.sh; source /etc/profile.d/modules.sh
module purge; module load intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 \
       netcdf-c curl/8.4.0 expat/2.5.0
export CPATH="$PWD/json_compat:$CPATH"      # the local json_object_iterator.h shim
make main                                   # target is `main`, NOT `lpjml`; ~1 min incremental
```

Adding a **new source file** needs three edits: the `.c` under `src/lpj/`, its header under `include/`,
and `<name>.$O` appended to the object list in `src/lpj/Makefile`. The build is `-Werror`, so a warning is
a failure; and `include/errmsg.h` has no `OPEN_OUTPUT_ERR` — pick an existing code.

**Then the gate — a run comparison, because two builds are never byte-identical** (`getbuild.c` stamps a
build date). Re-run one cell with the new binary and compare against a run the previous binary made with
the *same config, same cell set and same `--ntasks`* (ADR 0041: a differently-decomposed run is a different
trajectory, so a mismatch would be unattributable):

```bash
RUNTAG=<line>_rebuild_gate SUBMIT=yes bash scripts/run_fdiff_validation_cell.sh   # ~7 s, cell 42490
python scripts/diagnose_cbinary_rebuild_equality.py --ref <old_run>/output --new <new_run>/output
```

⚠ **Do NOT judge this with `cmp`.** LPJmL writes a wall-clock timestamp + the config path into every
NetCDF's `history` attribute, so `cmp` calls **20 of 21 outputs different** for two runs with identical
physics (ADR 0043). The script hashes **decoded variables** instead and compares the text outputs
byte-for-byte. Measured on the 2026-08-10 rebuild: 138 variables + `globalflux` identical, 0 differ.

## The rung-2 demography hook (opt-in; inert by default) — ADR 0061

`patches/lpjmlfit_rung2_demography_hook.patch` adds `include/rung2hook.h` + `src/lpj/rung2_hook.c` and two
call sites in `annual_natural.c`. **Activated only by `export LPJ_RUNG2_DIR=<dir>`**; unset, every entry
point returns immediately (this is what makes the shipped `bin/lpjml` still the oracle). It writes
`<dir>/roster_rank%04d.txt` with three self-describing record kinds (`#H` header lines in the file):

* `P` — patch context (`npatch`, `patcharea`, `fpar_leafon_grass`, `treelen`, live trees, `aprec`)
* `T` — one line per tree, 49 fields, at two phases: **`pre`** = before turnover/allocation/mortality,
  **`post`** = the C's own answer after establishment
* `G` — one line per grass PFT

It carries what `ind` cannot: `water_stress`, `temp_stress`, `bm_inc_counter` (the accumulators three of
the four death rates read), `bm_inc`, `nind`, all seven carbon pools, `crownarea`, `boleht`, `fapar`.

Gotchas, each paid for once:

* **`mort_*` are meaningful only at `post`.** They are written by `mortality_tree_ind`, which runs after the
  `pre` dump; in the first year after a restart they hold uninitialised memory (a `6.9e-310` denormal).
* **Recruits appear at `post` with `age == 0`** — `annual_tree` does the `age++`, so they first read as age
  1 the following year. Dead trees stay in the patch list with `isdead = 1` and are gone by the next `pre`.
  Accounting closes exactly: `post`-alive of year *N* == `pre` of year *N+1*.
* **`run_fdiff_validation_cell.sh` and `run_daily_subset.sh` emit no `ind` table.** To cross-check the dump
  you must add `{ "id" : "ind", "file" : { "fmt" : "txt", "name" : "output/ind_<y0>_<y1>.csv" }}` to the
  generated `lpjml.js` by hand.
* Neither wrapper exports the variable either — generate with `SUBMIT=no`, insert
  `export LPJ_RUNG2_DIR=...` into the generated `slurm.jcf`, then `sbatch` it.
* Verify the dump with `scripts/diagnose_rung2_roster_vs_ind.py` (post + stems >5 m must reproduce the
  run's own `ind` table: identical tree sets, all 21 shared columns to ≤5e-6 — `ind`'s `%g` gives only six
  significant digits, so a tolerance below ~1e-5 is meaningless).
