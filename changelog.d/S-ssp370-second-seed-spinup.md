### Fixed

- **The ssp370 `random_seed2` ground truth was a bit-identical copy of seed1; produced the real
  one.** `random_seed` is **inert** in any `-DFROM_RESTART` run: with `"new_seed": false` the
  per-cell RAND48 seeds are restored from the restart file (`newgrid.c:507-513` →
  `freadcell.c:37`) and the code that would apply `config->seed_start` is gated off
  (`newgrid.c:520-521`); `seed_start` is applied once at parse time (`fscanconfig.c:231`) and then
  overwritten from the restart header (`openrestart.c:139-140`). The broken member set
  `random_seed: 2` but restarted from the **historic seed1** `restart_2019.lpj`, so it inherited
  seed1's exact state — and because `new_seed` is false the log prints `Reading random seeds from
  restart file.` instead of `Random seed: 2`, so nothing warned. A noise floor built from it
  reports `floor_r ≡ 1`, i.e. fabricated emulator headroom. **A second seed is a second SPIN-UP
  carried forward**, not a changed `random_seed` (ADR 0041).

### Added

- `scripts/build_slow_ind_parquet.py` — the missing `ind_*.csv` → parquet step, parameterized by
  `SRC`/`OUT`. Previously reachable only via the FROZEN sibling repo's `global_extract.py`, whose
  `--which` is argparse-restricted to a hard-coded three-entry dict, so a new scenario/seed could
  not be named at all. Asserts the frozen 29-column `IND_COLUMNS` header and keeps the
  load-bearing `schema_overrides` (polars infers `Wooddens` as integer from the first rows).
- `scripts/diagnose_ind_seed_independence.py` — gate a new ground-truth member before deriving
  anything from it: completion line (not SLURM state), final year, size *differs* from the sibling,
  and sampled MB windows differ at every offset. Equal size is the copy signature.
- `scripts/diagnose_ind_binary_equality.py` — per-cell bit-equality of a subset re-run against the
  global ground truth, **with a decomposition control** (single cell vs a block containing it), so
  a mismatch is attributable to the binary rather than to the MPI decomposition. Needed because the
  current `bin/lpjml` is not merely "Feb-5 source + the daily-grass-GPP patch" but also a
  RHEL8→RHEL9 toolchain rebuild.
- Recovered the ssp370 CO2 forcing that the seed1 run read and installed it durably at
  `/p/projects/waldspektrum/priesner/clustering/global/global_co2_ann_1700_2019_const_2100.txt`
  (md5 `ed5699b9c92d4d25857889f644b153db`). Its original path was inside a scripts directory that
  was repurposed for an unrelated project, so the seed1 config had become unrunnable. Identity
  established four independent ways (git blob, a filesystem snapshot whose mtime predates the run,
  reconstruction from the TRENDY v12 source, and the documented 409.63 ppm constant).
