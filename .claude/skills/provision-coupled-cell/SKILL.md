---
name: provision-coupled-cell
description: Provision the PER-CELL inputs the multi-cell coupled S+F+E driver needs for a new grid cell (line M / M1) — daily forcing, the per-layer soil column (whcs from the C's own whc_nat, rootdist from the community-mean getrootdist profile), the reconstructed representative-individual canopy, and the lat/cell registry. Use whenever adding a cell to the coupled biome set, regenerating M_soilcolumn_*/M_individuals_*/M_cells.csv, deciding what "this cell's soil column" or "this cell's root profile" IS, or scaling the coupled driver from 5 cells toward global. Names scripts/extract_cell_soilcolumn.py (and its GATE against hainich_soilcolumn.txt), scripts/extract_cell_individuals.py, scripts/extract_biome_forcing.py (the canonical BIOMES registry + cells_from_env), scripts/run_fdiff_validation_cell.sh RUNTAG=M_biome_val for the per-cell d_fapar oracle, ADR 0050, and the whc_nat float32 / single-cell-vs-global provenance traps.
---

# provision-coupled-cell — per-cell inputs for the multi-cell coupled driver

Everything the coupled driver needs per cell, and the order to build it in. The *decision* basis (what
"this cell's whcs / rootdist" means, and why) is **ADR 0050** — read it before changing a derivation.

## 1. Register the cell (single source of truth)

Add `"<name>": <orderA 0-based index>` to `BIOMES` in **`scripts/extract_biome_forcing.py`**. Every
per-cell extractor imports `cells_from_env()` from there, so this is the only place a cell list lives.
Override per invocation with `CELLS="name:idx,..."`. Resolve the index from the global run's `grid.nc`
`cellid[lat,lon]` — never assume a raster order.

## 2. Generate that cell's C oracle (≈ 9 s of compute, needed for the canopy check)

```bash
CELL=<idx> FIRSTYEAR=2000 LASTYEAR=2019 RUNTAG=M_biome_val SUBMIT=yes \
  bash scripts/run_fdiff_validation_cell.sh          # -> /p/tmp/jamirp/esm_land_daily/daily_2000_2019_M_biome_val_c<idx>_seed1
```
This adds `d_fapar` + `a_lai_stand` + `a_fpc_stand` + a **single-cell `whc_nat.nc`** that the stock global
run's ensemble does not give you (see the provenance trap below). Then
`python scripts/water_closure_check.py <run_dir>` — a clean run IS water closure.

## 3. Extract the three input files (login node, seconds)

```bash
PY=/home/jamirp/.conda/envs/py311_new/bin/python
$PY scripts/extract_biome_forcing.py        # -> references/biome_forcing_<name>.csv     (GSWP3-W5E5 daily)
$PY scripts/extract_cell_soilcolumn.py      # -> references/M_soilcolumn_<name>.txt      (+ meta json)
$PY scripts/extract_cell_individuals.py     # -> references/M_individuals_<name>_2010.csv, M_cells.csv
```
`extract_cell_individuals.py` imports the reconstruction physics (PFT table, allometry, the `getfpar.c`
layered-light port) from `extract_fdiff_individuals.py` — extend *that* if the physics changes, never
duplicate it.

## 4. Check it before trusting it

- **The soil-column gate runs by default** and must print `GATE PASS`: re-extracting cell 42490 in
  `ROOTDIST=d95_scalar D95_CM=115` mode reproduces all 23 printed rows of the committed
  `hainich_soilcolumn.txt`. Gate only: `EMIT=no python scripts/extract_cell_soilcolumn.py`.
- **Canopy:** `extract_cell_individuals.py` prints reconstructed cell FAPAR vs that cell's own C peak
  (top-30 days). The reconstruction is LEAF-ON, so the ratio is systematically **~1.3–1.6** — Hainich's
  committed value is 1.60 (1.71 on the older DOY-150–240 basis). A cell far outside that band is the signal
  to investigate, not the ratio itself.
- **Then the suite:** `scripts/run_tests_slurm.sh M-<tag>`. `biome_coupled_tests.jl` asserts the columns are
  well-formed (23 layers, `whcs > 0`, `sum(rootdist) ≈ 1`), **pairwise distinct** (the guard against
  silently falling back to Hainich's inputs), and that the rooting gradient stays ecologically ordered.
- **The mapping check the Hainich gate CANNOT give you.** A wrong `cellid` lookup or the wrong per-cell run
  still reproduces Hainich, so cross-check the new cell against its **soil code**
  (`soil_code_test.soil.bin`, 1 uint8/cell, orderA-indexed): the DEEP layers carry ~no organic matter, so
  Saxton–Rawls leaves `whc = f(sand, clay)` — **cells sharing a soil code must share their deep-layer
  `whc` to ~1e-5, and cells with different codes must differ.** [VERIFIED 2026-07-28] boreal 52059 /
  mediterranean 33335 / tropical 12045 are all code 7 (loam) on three continents and agree to 3.6e-5
  (0.15124–0.15128), vs code 4 clay loam 0.17421 (Hainich) and code 9 sandy loam 0.11545 (Sahel). The **top**
  layer legitimately differs within one code (the organic-matter term: 0.2099 boreal vs 0.1676 Iberia).

## 5. Wire it in

`scripts/run_coupled_biomes.jl` and `test/testitems/biome_coupled_tests.jl` both read `M_cells.csv` for
(name, cell, lat, lon) and then `M_soilcolumn_<name>.txt` / `M_individuals_<name>_2010.csv` /
`biome_forcing_<name>.csv` by name — a registered + extracted cell needs no Julia edit. The driver also runs
the legacy common-Hainich configuration, so its `dLE`/`dBowen` columns isolate the vegetation+soil effect.

## Traps (each one cost real time)

- **`whc_nat` provenance:** the committed Hainich column came from the **single-cell** run, NOT the 512-task
  global run. Under `-DPERMUTE` they differ by up to 1.6e-4 relative in layer 0 (whc depends on the
  stochastic patch soil-carbon ensemble), which is 40× the print resolution. `WHC_SRC=percell` (default)
  prefers a single-cell run and falls back to global; a gate against the global file cannot pass.
- **float32 accumulation is load-bearing.** Take the 240-month mean on the float32 array as read; promoting
  to float64 first changes 5 of the 23 printed values.
- **`whc_nat` is monthly and time-varying** (`whc = wfc − wpwp` is recomputed twice a day from the evolving
  soil carbon), despite living in a `daily_*` run directory. The time mean is a documented CHOICE.
- **`depth(layer)` in the NetCDF is the layer CENTRE.** Thickness = `(depth_bnds[:,1] − depth_bnds[:,0])*1000`.
- **Do not derive per-cell soil depth from `soil_depth_test.clm`:** `newgrid.c:282` overwrites it with a flat
  20 m for every cell, and the layer thicknesses are a C global (`par/soil_20m.js`).
- **Tree test is `D95max > 0`, not a `Type` number.** `Type` ids differ by biome (42490 has {1,2,3,4,5,8};
  18371/12045 have {0,7}), so `python/.../data.py`'s `TREE_TYPES=(1,2,3,4,5)` is not portable.
- **Never regenerate `hainich_soilcolumn.txt` or `hainich_individuals_2010.csv`** — they feed many committed
  baselines, so that is an integration point (guardrail 4 / ADR 0029). Emit `M_*`-named files and diff.
- **Emitted rows must hold exactly 4 whitespace-separated numeric fields** (`%d %.1f %.4f %.6f`): the Julia
  readers `parse.(Float64, split(s))` the WHOLE row, so a 5th column fails the entire suite at collection.
- **A script writing to a hard-coded `/p/projects/open/Jamir/esm_land_emulator` path writes into the
  INTEGRATOR worktree** when run from a per-line `git worktree`. Derive the repo root from `__file__`
  (fixed in `extract_biome_forcing.py`; check any script you reuse).
