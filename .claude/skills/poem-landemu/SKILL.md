---
name: poem-landemu
description: Build, run and score POEM 1.2 (the PIK Earth System Model - AM2 atmosphere on the FV core 3.75x3 deg, MOM5 ocean, LPJmL 5.9 land at 0.5 deg) with the LEARNED LPJmL-FIT emulator embedded inside its LPJmL (ADR 0347) - the patched POEM copy /p/projects/open/Jamir/poem_landemu/POEM-1.2_20261013_6-layers_landemu (branch `landemu`, patches/poem/), the embedded-Python bridge landemu_py.c, the LANDEMU=unset|shadow|1 run-time switch (stock / record-only / coupled), scripts/online_coupling/poem/{setup_poem_run.sh,compile_poem_landemu.sh,compare_poem_runs.py}, scripts/online_coupling/{poem_landemu.py,score_poem_landemu.py}, runs under esm_land_emulator_data/coupled/poem/, and the traps that each cost a failed job (libpython link dir shadows POEM's static netCDF/HDF5 -> HDF5 abort in NC4_open; LPJmL's FE_INVALID traps vs numpy NaNs; Intel FTZ/DAZ vs bit-identical replay; the land rank that holds only Antarctica; all-lake cells 0/0; POEM feeds LPJmL SKIN temperature not air temperature; mpirun across two nodes fails in MPI_Init). Use whenever coupling the emulator to POEM, rebuilding or extending the POEM build, adding a channel (albedo, roughness, CO2, snow) to it, running or scoring a POEM run, or asking how the emulator behaves under POEM's climate. The SpeedyWeather coupling is the separate skill online-coupling-env.
---

# poem-landemu — the learned emulator inside POEM 1.2 (ADR 0347)

**What POEM is (`[VERIFIED 2026-10-16]`, owner: the newest POEM is unpublished, read it on the HPC, not
online):** builds `/p/projects/poem/data/tuning-1.2/POEM_PROGRAM/POEM-1.2_<date>`, runs
`/p/projects/poem/data/tuning-1.2/POEM_RUNS/0.2/`. Git checkouts need `git -c safe.directory='*'`.
The land is LPJmL 5.9 (C) called from `src/land_atlantes/lpj_driver.F90` **every fast step (1 h)** through
`lpj_update_` in `src/land_atlantes/LPJmL/src/lpj_climber4.c`: hourly `update_fast()` (snow, soil heat,
canopy humidity, ET, `cell->evap1`), and at the last step of the day (`goodnight`) `update_daily()` (the
vegetation) and `drain()` (rivers -> `runoff_out` -> ocean). With `-DUSE_LPJ_FLUX_OVERWRITE` (on for
`MOM_ATLANTES_LPJ_CM2`) the coupler **replaces the atmosphere's land moisture flux by LPJmL's
`evap1_out`** (`flux_exchange.F90`, `evap_flux_overwrite`) — the hook the emulator uses.
Calendar NOLEAP (= the emulator's 365-day years). With fixed CO2 (`interactive_carbon=false`) a whole
segment is ONE executable invocation (no yearly restart). 28 MPI tasks on one node; 20 atmosphere/land
ranks (layout 1x20 = latitude bands; rank 0 holds only Antarctica). ~22 min wall per simulated year.

## The coupling (LANDEMU=1)
- Each LPJmL 0.5-degree cell = the emulator cell at the same position (`poem_landemu.py`, `MAX_DEG` 0.01;
  ~4 100-4 400 of 4 544 cells per rank). Unmatched cells (Antarctica, ice, rock) keep LPJmL's fluxes.
- Hourly: accumulate 2-m air T and q (NEW coupler fields `t_ref`/`q_ref`), precipitation, downward SW,
  net LW. Last step of the day: the emulator runs that day; its **runoff replaces LPJmL's in the river
  routing** (difference booked in `balance.awater_flux` so LPJmL's cell water check still closes); its
  **ET becomes the land moisture flux of the next day** (`LANDEMU_DIURNAL=sun|flat`, exact daily total)
  and the latent heat in LPJmL's surface energy balance (`cell->evap1`; `cell->dedt` is 0 in stock LPJmL anyway). Lakes, surface
  temperature, albedo, roughness, canopy humidity, snow stay LPJmL's.
- `LANDEMU=shadow`: same, but nothing handed back -> stock POEM + a full emulator record (control run and
  the one-way result in one). Unset: stock.
- Gates (`compare_poem_runs.py`, decoded variables of RESTART + history + LPJmL output): stock vs stock
  identical (1 050 variables, POEM is deterministic); our build with LANDEMU unset identical; shadow
  identical; coupled differs (335 of 1 050). Offline replay of the records: `score_poem_landemu.py replay`.

## Build / run
```bash
sbatch scripts/online_coupling/poem/compile_poem_landemu.sh      # ~19 min full, ~20 s incremental (NO --vec: the POEM group's build is not vectorised)
scripts/online_coupling/poem/setup_poem_run.sh <run_dir> stock|off|shadow|coupled <years> [sun|flat] [months]
cd <run_dir> && sbatch 01_submit.sh                               # priority partition: 64 cpus/user = two runs at once
python scripts/online_coupling/poem/compare_poem_runs.py <run_a> <run_b>
python scripts/online_coupling/score_poem_landemu.py <run_dir>...  # climate vs W5E5 / GFDL-ESM4 1850-1879, land totals, water closure
python scripts/online_coupling/score_poem_landemu.py replay <run_dir> 20
```
A gate run (`months` set) "FAILS" in its post-processing (no LPJmL year-end restart) — expected; the
model output is there. Starts from the POEM group's `spinup_6layers_maxsnowheight-20m` end-of-1850 state
(read only; its restart is symlinked).

## Traps (each cost a failed job)
1. **Never put the Python env's `lib/` on the link search path.** `-L$PY/lib` made `-lnetcdf`/`-lhdf5`
   resolve to the env's SHARED libraries instead of POEM's static ones; the run died in `NC4_open`
   (`libhdf5` abort) before any emulator code ran — even with LANDEMU unset. Link from
   `/p/projects/open/Jamir/poem_landemu/pylib` (symlinks to libpython only). Check: `readelf -d` NEEDED =
   stock list + `libpython3.11.so.1.0`.
2. **LPJmL runs with `feenableexcept(FE_INVALID)` and the Intel build sets FTZ/DAZ.** `landemu_py.c`
   switches traps off and clears FTZ/DAZ around every Python call and restores both (numpy produces NaNs
   legitimately; FTZ would break the bit-identical replay).
3. **Python inside MPI ranks:** isolated `PyConfig` (ignores PYTHON* env; POEM's run script activates its
   own conda Python 3.12), home `LANDEMU_PYHOME`, `install_signal_handlers = 0`; one thread per rank.
   An embedding probe that spreads tasks over two nodes dies in `MPI_Init` (OFI address vector) — POEM
   runs `--nodes 1`.
4. **A rank can have zero emulator cells** (rank 0 = Antarctica band) -> `poem_landemu.NoCells`.
5. **All-lake cells have land fraction 0** -> per-land-area divisions are 0/0 and trap (`floating invalid`
   at `lpj_climber4.c` in `le_goodnight`).
6. **POEM feeds LPJmL the SKIN temperature (`bnd%t_surf`) as its air temperature** (`land_model.F90`);
   the emulator was trained on 2-m air temperature, hence the new `t_ref`/`q_ref` (computed ALWAYS at
   `z_ref_heat` in `sfc_boundary_layer`; POEM's own diagnostic block computes them only on request and at
   `z_ref_mom` when `t_ref` is not requested).
7. `lpj_fms.h`'s `lpj_update_` prototype must match the definition (two new `const double *`).
8. **The coupled runs overheat single hours past 80 degC, cause OPEN — and `LANDEMU_DEDT` is NOT the fix**
   (ADR 0347 sec. 8, 2026-10-19). ~6 per million cell-hours, tropics/subtropics, from year 1 (log line
   `ERR_CLIMBER: final soiltemp too large`; shadow/stock: 0). It was blamed on zeroing `cell->dedt`, but stock
   LPJmL in POEM sets `cell->dedt = 0` itself every step (`lpj/humidity.c:445`), so `LANDEMU_DEDT=zero|lpj`
   are bit-identical (4.8 coupled years, every global total and every overheating count). **Before blaming any
   LPJmL term, check the stock code does not already set it** — `grep -rn "<field>\s*=" src/lpj`. Count it in
   every coupled run with `cat fms.out-* | grep -o "soiltemp too large" | wc -l`, and compare per year with
   `Date:`-line binning (the shadow run is the zero reference).
9. **The hour shape of the handed-over ET changes the climate**: flat (night = day) cut land convective rain
   30 % and cooled the land 1.1 degC in 10 years; use `sun`.

10. **Disk: a 10-yr run is ~39 GB in the run dir; the `/p/projects/open` quota can fill mid-run** (2026-10-16:
   both 10-yr runs died at year 4.8 with `nc__enddef failed with 122: Disk quota exceeded` in
   `sbatch.64.<jobid>.out`; SLURM just says FAILED 1:0, like a gate run's harmless post-processing failure, so
   always grep that log for `quota`). The quota is not readable here (`mmlsquota`: no quota-enabled fs); a
   50 MB `dd` write test is the only check. A full quota also kills `sbatch_python.sh` jobs (their log is in
   the repo's `logs/`): exit 120, `OSError: [Errno 122]` — write such a job's log to `/p/tmp`.

## Cost (measured)
POEM-1.2 stock: 1 322 s wall per simulated year; atmosphere 57 %, whole land 28 % (LPJmL hourly step 21 %,
regridding 3 %), land-ice-atmosphere coupler 13 % (FMS clock table at the end of `fms.out-1-28-0-*`). The
coupling adds the emulator (30-40 s per rank-year, 2-3 %) on top of LPJmL: it is NOT faster. Removing LPJmL
entirely would save at most ~25 % (and needs a replacement hourly surface energy balance).
