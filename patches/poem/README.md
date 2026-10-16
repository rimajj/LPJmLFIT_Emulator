# POEM 1.2 with the learned land emulator inside LPJmL (ADR 0347)

Base: the POEM group's build `/p/projects/poem/data/tuning-1.2/POEM_PROGRAM/POEM-1.2_20261013_6-layers`
(POEM `b882fcd`, LPJmL `74a006207`). Our build: `/p/projects/open/Jamir/poem_landemu/POEM-1.2_20261013_6-layers_landemu`,
local branch `landemu` in both repositories (POEM root and `src/land_atlantes/LPJmL`).

- `poem-1.2_20261013_landemu_poem.patch` — POEM: the coupler always computes the 2-m air temperature and
  humidity (`flux_exchange.F90`) and hands them to the land (`land_types.F90`, `land_model.F90`,
  `lpj_driver.F90`); the build links `libpython3.11` (`exp/POEM_compile.csh`, `exp/lpj_compile.csh`).
- `poem-1.2_20261013_landemu_lpjml.patch` — LPJmL: `src/landemu_py.c` (the only file that includes Python.h),
  `include/landemu.h`, the glue in `src/lpj_climber4.c`, its rule in `src/Makefile`.

Rebuild from scratch: copy the base tree without `exec/`, replace its absolute root in
`src/land_atlantes/LPJmL/{Makefile.inc,bin/lpj_paths.sh,bin/lpj_paths.csh}`, apply both patches
(`git apply`), then `sbatch scripts/online_coupling/poem/compile_poem_landemu.sh <root>`.
Runs: `scripts/online_coupling/poem/setup_poem_run.sh`; Python half `scripts/online_coupling/poem_landemu.py`.

Run time switch `LANDEMU`: unset = stock POEM (gated bit-identical), `shadow` = emulator runs and records,
hands nothing back (gated bit-identical), `1` = coupled.
