---
name: provision-coupled-cell
description: Provision the PER-CELL inputs the multi-cell coupled S+F+E driver needs for a new grid cell (line M / M1) — daily forcing, the per-layer soil column (whcs from the C's own whc_nat, rootdist from the community-mean getrootdist profile), the reconstructed representative-individual canopy, and the lat/cell registry. Use whenever adding a cell to the coupled biome set, regenerating M_soilcolumn_*/M_individuals_*/M_cells.csv, deciding what "this cell's soil column" or "this cell's root profile" IS, or scaling the coupled driver from 5 cells toward global. Names scripts/extract_cell_soilcolumn.py (and its GATE against hainich_soilcolumn.txt), scripts/extract_cell_individuals.py, scripts/extract_biome_forcing.py (the canonical BIOMES registry + cells_from_env), scripts/run_fdiff_validation_cell.sh RUNTAG=M_biome_val for the per-cell d_fapar oracle, ADR 0050, and the whc_nat float32 / single-cell-vs-global provenance traps. ALSO how to ADOPT/RE-PIN a versioned Component-S artifact for the coupled driver (M2): scripts/extract_cell_slow_init.py folds per-cell n_init/age0 + the 4-column slow boundary out of cell_meta.parquet into the committed M_cells.csv, requires a COMPLETE .drf+.rcop pair, re-checks colnames/cond_cols against flux_feature_vector/live_flux_cond, and GATES on cell coverage (the old pooled_w20 pin never saw semiarid_sahel; the _t7/_t8 tables cover all 5) — plus why n_init/age0 are version-coupled medians while the boundary is scenario-coupled.
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

### 5b. A/B-ing an F-core change across all five cells — COPY, don't re-derive

Whenever you change F physics or add a `WaterParams`/`FDiffParams` flag, the honest measurement is the same
five-cell A/B every time, and `residual-diagnosis` §3g is explicit that one cell will name the wrong
dominant mechanism. **`scripts/wscal_leafon_probe.jl` (ADR 0051) is the canonical driver — copy it.** It
already has: the four per-cell readers, a `mkparams(flag)` that starts from `FDiff.tebs_params` and flips
**only** your field, a daily loop replicating `run_coupled_cell`'s (`couple_day!` + `fc.water_avail`) for
per-day diagnostics with `slow=nothing`, and a full coupled `FluxDrivenSlowEmulator` run on the pinned
`_t8` forest reading `s.feature_history` for the exact row the DRF was fed, plus `s.n_prev` for the
demographic consequence.

Three traps it encodes, each of which cost a failed run:

- **`mkparams` must start from `FDiff.tebs_params(Float64)`, never a bare `FDiffParams{Float64}()`** — the
  fast core defaults to the *calibrated* set, so a bare constructor silently swaps every other constant
  (e.g. `emax` 10.0 → 5.0) and the A/B measures the wrong thing. Rebuild the inner params via
  `NamedTuple`+`merge` and the POSITIONAL `FDiffParams` constructor (field order `photo, tstress, water,
  resp, allom, nlambda, ω`).
- **The per-cell readers are duplicated in four places** (`run_coupled_biomes.jl`, the three
  `biome_coupled_tests.jl` items, and this probe) because testitems must be self-contained. Copy the block;
  do not try to factor it into a module the testitems can share.
- **`Statistics` is NOT in the test env.** Scripts may `using Statistics`; a `@testitem` must define
  `_mean(x) = sum(x)/length(x)` (the sibling convention) or it errors at load.

The reference side is `scripts/wscal_c_truth_diagnosis.py`: derive the C's own column per cell/year
**exactly as the training-table builder forms it**, and report error in units of the **seed1-vs-seed2 noise
floor** — filtering to 5 cells makes the aggregate small enough to `collect()` non-streaming, which also
sidesteps CLAUDE.md §4's streaming key-set nondeterminism (assert your key set anyway).

## 6. The per-cell Component-S seed + boundary (M2) — and how to ADOPT an S artifact version

A cell also needs the S side: `n_init`, `age0`, and the 4-column slow boundary
`[eco_diag_gdd_5, tas_cold_month, soil_depth, co2]` (the `flux_feature_vector` tail order, which is also
`live_flux_cond`'s conditioning tail). These come from line S's `cell_meta.parquet` sidecar on `/p/tmp`, which
**CI cannot reach** — so fold them into the committed `M_cells.csv`:

```bash
SC=/p/tmp/jamirp/emulator_global
META=$SC/slow_runtime_historic_t8/cell_meta.parquet \
META_TXT=$SC/drf_forest_global_pooled_w20_t8_meta.txt \
  /home/jamirp/.conda/envs/py311_new/bin/python scripts/extract_cell_slow_init.py
# env: CELLS="name:idx,..."  OUT  ALLOW_BOUNDARY_FROM=<2nd cell_meta>  GATE=no
```
(`_t8` is the pin as of 2026-07-30 — always use the CURRENT one from `lines/M/STATE.md`'s pin table,
which is authoritative; the version tag in this example ages.)

**Adopting (or re-pinning) an S artifact is a deliberate, two-sided act (ADR 0023) — never silent.** The order:

1. **Require a COMPLETE pair** — a `.drf` *and* its matching `.rcop`. A half-published retrain is common
   because S trains the count DRF and the copula as separate jobs; adopting the `.drf` alone is the trap.
2. **Re-check both feature orders against the runtime**, don't assume: the DRF meta's `colnames` tail vs
   `slow.jl::flux_feature_vector`, and the copula meta's `cond_cols` tail vs `live_flux_cond`. `META_TXT=`
   makes the extractor do this and abort on a mismatch (a mismatch is an integration point, not a local fix).
3. **Check CELL COVERAGE before anything else** — `cell_meta` tables do NOT all cover the same cells, and a
   DRF cannot serve a cell it never saw. This is what the extractor's completeness gate is for, and it is the
   check that actually blocked an M2 session. Measured: the pre-`_t7` tables
   (`slow_*_historic_w20` / `slow_runtime_historic`) hold 44,328 cells = **3 of the 5 biome cells** (no Sahel,
   no Amazon) and `slow_*_ssp370_w20` 53,566 = **4/5** (no Sahel), so `drf_forest_global_pooled_w20`
   structurally could not serve `semiarid_sahel`; every **`_t7`/`_t8`** table covers **5/5**
   (53,699 historic / 58,495-58,496 ssp370). Read the coverage out of the parquet yourself — do not infer it
   from the cell count quoted in a meta or a handoff note.
4. **Record the path + sha256 + the coverage verdict** in `lines/M/STATE.md`, and note the swap in
   `lines/S/STATE.md` too.

**Two facts about these columns — they decide what you may and may not borrow across versions:**

- **`n_init`/`age0` are version-COUPLED. Never mix them across artifact versions.** They are the per-cell
  **median over the training years** of the count target `n_living` and of `age_mean`
  (`build_slow_runtime_table.py:320-332`, `MIN_YEARS=3`) — statistics of the *training window*, not properties
  of the cell. Across the 44,328 cells shared by `slow_runtime_historic` and its `_t7` retrain: `n_init`
  differs for 15,665 cells (max |Δ| **24** individuals), `age0` for 22,542 (max |Δ| **85** years). Corollary
  worth knowing before you design around it: they are therefore **not** recoverable from the committed
  single-year `M_individuals_<name>_2010.csv` canopy either — different statistic.
- **The 4 boundary columns are invariant across VERSIONS of one scenario, but NOT across SCENARIOS.**
  Same scenario, different training version: byte-identical on all 44,328 shared cells. historic vs ssp370:
  `eco_diag_gdd_5` differs by up to **1513** GDD and `tas_cold_month` by **8.84 °C** on 43,901 shared cells —
  correctly, they are climate diagnostics of *different climates*. Two consequences: `ALLOW_BOUNDARY_FROM` may
  only borrow within a scenario (the extractor PROVES invariance on the overlap first and refuses otherwise),
  and **a POOLED artifact has two boundary rows per cell**, so one baked `boundary` is a single-climate
  snapshot ⇒ use the per-cell `ClimBuf` (`climbuf=` in `run.jl`) or a baked `boundary_series` (ADR 0026/0027).

**The CI gate must load the COMMITTED demo forest** (`references/drf_forest_hainich.drf`), never the pinned
`/p/tmp` artifact — CI has no cluster. That is fine because closure/determinism are artifact-independent, and
a DRF prediction is a mean over leaf values so it cannot leave its training target range even when
extrapolating. Template: `test/testitems/slow_production_drf_tests.jl` (fixed-N reference vs S-driven
mechanism, carbon ≤1e-6·C_scale, energy, determinism under seed) — and, for the multi-cell version,
`biome_coupled_tests.jl`'s M2 item (per-cell seed + per-cell `ClimBuf`).

**Emit the fixture at `repr` (`%.17g`), never `%.6f`.** These values are compared against DRF split
thresholds, so display precision is not good enough: `%.6f` truncated Hainich's `eco_diag_gdd_5`
1863.695068359375 → 1863.695068. With exact output, `M_cells.csv`'s Hainich row comes out **bit-identical**
to the committed `drf_forest_hainich_meta.txt`'s own baked `boundary`/`n_init`/`age0` — the same quantity
from the same upstream — which turns a fuzzy provenance check into an exact `==`. Assert it: an off-by-one
in the boundary tail, or a scenario/version mix-up, still produces four plausible-looking numbers.

**Verify the artifact yourself; do not take the publishing line's word for it.** S's handoff note is written
in good faith and has been accurate, but the whole point of the ADR-0023 pin is that M owns what it runs. Two
checks, both seconds: deserialize both halves (`DRF.load_forest` → `nfeat`/`ntrees`; `DRF.load_copula` →
`axis_names`, `cond_cols`, and `nfeat` per axis forest — that last one is what actually proves the ADR-0036
diagnostic axes `agb`/`Height` are absent from the `.rcop`, since the meta only *claims* it), and read the
cell coverage out of `cell_meta.parquet` rather than trusting a stated cell count.

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
- **A gate whose verdict does not travel with the artifact is not a gate** (M1 review debt #2, closed
  2026-08-05 / ADR 0055). `GATE=no` warned on stderr and then emitted a soil column **structurally
  indistinguishable** from gated output — so an ungated file could be committed weeks later by someone who
  never saw the warning. `extract_cell_soilcolumn.py` now stamps `# GATE: PASS …` / `# GATE: NOT RUN …`
  into every column header **and** a `gate` key into `M_soilcolumn_meta.json`, and
  `biome_coupled_tests.jl` asserts each committed column carries a PASS. Apply the same pattern to any new
  extractor here: emit the verdict INTO the artifact, then assert it in a test. Regenerating for the stamp
  is safe — the data rows came out byte-identical, only the header line is new.
- **⚠ `M_cells.csv` HAS TWO WRITERS, AND ONE OF THEM USED TO EAT THE OTHER'S COLUMNS (line M, 2026-08-12,
  ADR 0125).** `extract_cell_individuals.py` owns the first ten columns; `extract_cell_slow_init.py`
  APPENDS six more (`n_init`, `age0` + the four-column slow boundary — the pinned Component-S per-cell
  seed). The individuals extractor rewrote the file from its OWN header and dropped every row whose field
  count differed from it, so any re-run — e.g. to add a year or a cell — silently deleted the artifact pin,
  with no error and no diff to look at until the coupled driver came up wrong. **Fixed:** its merge now
  reads the file's own header, preserves columns and comment lines it does not own, and a re-run over the
  live registry is byte-identical. **The rule for any new extractor that writes a shared registry: read the
  existing header, union it with yours, and never key a row parse off your own column count.** Verify with
  a round-trip (`cp` the live file to a scratch `OUT=`, re-run, `diff`) before committing.
- **Per-year rosters are a one-line loop, and they unlock a per-STEM comparison.** `YEAR=<y>
  OUT=/p/tmp/jamirp/M_canopy_drift/individuals` gives the C's stand at the end of any year (~10 s each,
  50 KB each — keep them on `/p/tmp`, do NOT commit). Since 2026-08-12 the emitted rows also carry `id`
  and `age`, and `(Cell, Patch, ID)` is a stable cross-year identity (CLAUDE.md §3), so year y's roster can
  be scored stem-by-stem against year y+1's. **The `ind` row for year y is written at the END of year y**,
  so the stand entering year y is the year-(y−1) file — driving the year-y file with year-y forcing is an
  off-by-one, and it was in `biome_fdiff_oracle_probe.jl` for a month.
