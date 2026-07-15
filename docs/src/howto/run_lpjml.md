# How to run LPJmL-FIT & generate training data

> *Goal-oriented how-to. Authoritative details: `DESIGN.md` §4 (build + run recipe) and §7 (the narrow
> Phase-1 gap); paths in `config/paths.yaml`; SLURM/modules in `config/hpc_slurm.yaml`. All paths are
> read from `config/` — never hard-code them.*

!!! warning "Never run heavy compute on the login node"
    Spin-up, data generation, and training are submitted via `sbatch` on the PIK cluster. The login
    node is for building, `bin/lpjml -h`, and tiny checks only.

## Prerequisites (already resolved in Phase 0)

- **Source tree:** `/home/jamirp/lpjml56fit` (LPJmL 5.6.004 + FIT, git `b2e5ca9`), `LPJROOT` already
  set in `Makefile.inc`.
- **Binary:** `/home/jamirp/lpjml56fit/bin/lpjml` — already built, runtime-validated.
- **Modules** (`config/hpc_slurm.yaml:modules.lpjml_build_run`):
  `intel/oneAPI/2024.0.0`, `udunits/2.2.28`, `json-c/0.13.1`, `openssl/3.6.0`, `netcdf-c/4.9.2`,
  `curl/8.4.0`, `expat/2.5.0`. With these loaded, `bin/lpjml -h` reports `C Version 5.6.004`.

## 1. Confirm the binary

```bash
export LPJROOT=/home/jamirp/lpjml56fit
# load the modules from config/hpc_slurm.yaml first
"$LPJROOT/bin/lpjml" -h        # expect: lpjml C Version 5.6.004
```

## 2. Enable daily output (config-only — never edit C source)

Daily flux/pool output is a **runtime config flag**, not a code change (`DESIGN.md` §1.1). In the
chosen `"output"` `"file"` objects set `"timestep":"daily"` and a per-day `"unit"`. Enable the
fast-layer variables F and E need (`DESIGN.md` §3.3):

```
transp, evap, interc, runoff, runoff_surf, runoff_lat, perc, seepage,
swc (23-band), soiltemp (23-band), swe, gpp, npp, rh, pet, albedo
(+ firec, flux_estabc on the ANNUAL channel for carbon closure)
```

Keep the `ind` tree table **annual** — it is the cost driver. Simulation CPU is unchanged; only I/O
grows. For per-tree carbon pools (Tier-2 S), add a **RAW-format** `ind` output.

## 3. Prototype re-run (daily fluxes for F / E)

The design is **global multi-cell** (67,420 cells × 25 patches); the prototype is a small
**biome-stratified multi-cell** set — *not* a single cell — so S has an across-cell climate gradient
to fit (`DESIGN.md` §5, [ADR 0010](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0010-s-prototype-biome-stratified.md)).
F1 integration and E may be proven on **one** cell first (candidate Hainich `startgrid:28008`).

**Restart from the spin-up end, not the historical end** (`config/paths.yaml`):

- ✅ `restart_1999.lpj` = end of spin-up → use this to reproduce the 2000–2019 Historical trajectory
  the annual ground truth is built on, with the **same** `random_seed`, domain, `npatch=25`, binary.
- ❌ `restart_2019.lpj` = historical end → only for the SSP370 2020–2100 continuation.

Authoritative recipe = the production run scripts (`config/paths.yaml:lpjml.run_scripts_dir`), which
write `input_*.js` + `lpjml_*.js` + `slurm_*.jcf` into `scripts_for_running_the_model/` and submit a
**spin-up → transient** dependency chain (`--dependency=afterany`). The stale repo `.jcf` files point
at old `/home/billing/…` paths — do not use them.

### SLURM (from `config/hpc_slurm.yaml`)

- **Single-site smoke test:** `--qos=short --ntasks=1`,
  `mpirun bin/lpjml -DSPINUP -DSINGLESITE lpjmlfit.js` then `-DTRANSIENT -DSINGLESITE` (shorten
  `nspinup` for a quick daily-output check — this is a smoke test, not a gate).
- **Global ground truth:** `--qos=short --exclusive`, `--ntasks` 46 (historical) / 2048 (ssp370),
  account `waldspektrum`. Spin-up `nspinup=1000, nspinyear=30`. **Do not probe partitions
  interactively.**

Daily re-runs write to `config/paths.yaml:lpjml.daily_output_run_root` (`/p/tmp/jamirp/esm_land_daily`).

## 4. The split Phase-1 gate — verify budgets close

The Phase-1 checkpoint is **both budgets close** (`DESIGN.md` §7, `DEVELOPMENT_PLAN.md` §5):

- **Carbon — now, on existing annual `globalflux`, no re-run.** `Ra = GPP − NPP`;
  `ΔC = NPP − Rh − firec + flux_estabc`; `NBP_atm = Rh + firec − NPP − flux_estabc`. Fire is on, so
  `firec`/`flux_estabc` are mandatory — a fire-free `NEE = Rh − NPP` will not close. Use
  [`carbon_budget_residual`](@ref) / [`nbp_atm`](@ref).
- **Water — on the daily re-run.** `P = ET + runoff + drainage + ΔS`, matched to LPJmL's internal
  `balanceW` terms. Use [`water_budget_residual`](@ref).

## 5. Log the reproducibility ledger

For every dataset, record (per `DESIGN.md` §4.4 and the [reproduce guide](reproduce.md)): LPJmL commit
`b2e5ca9` / v5.6.004, the config JS files, the input `.clm` + CO₂ files, the RNG `random_seed`
(1 and 2 = the noise-floor pair), `npatch=25`, spin-up `nspinup=1000 / nspinyear=30`, and the module
versions. Fixed seed **42** for all Python/ML.

See the [Historical](../model/datasheets/historical_obsclim.md) and
[SSP370](../model/datasheets/ssp370.md) datasheets for the exact input inventory and provenance.
