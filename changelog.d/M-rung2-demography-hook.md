### Added

- **An opt-in demography observation hook in the LPJmL-FIT C binary** (`patches/lpjmlfit_rung2_demography_hook.patch`),
  the observation half of the rung-2 harness. Activated by the environment variable `LPJ_RUNG2_DIR`; with it
  unset the model is numerically identical to the previous build. Dumps each patch's tree roster at the top
  of the annual demography block and again after establishment, including the three per-tree accumulators
  three of the four death rates read (`water_stress`, `temp_stress`, `bm_inc_counter`) and all seven carbon
  pools — none of which the `ind` output carries. ADR 0061.
- `scripts/diagnose_cbinary_rebuild_equality.py` — the gate to run after **any** rebuild of the C binary.
  Compares **decoded NetCDF variables** (a file-level `cmp` is defeated by LPJmL's `history` timestamp,
  ADR 0043) plus the text outputs byte-for-byte.
- `scripts/diagnose_rung2_roster_vs_ind.py` — proves the hook's post-demography roster reproduces the C's
  own `ind` table on the same run (5 465 trees, identical tree sets, all 21 shared columns to ≤5.0e-6).

### Changed

- The C oracle binary `/home/jamirp/lpjml56fit/bin/lpjml` was rebuilt on 2026-08-10 and now contains the
  (inert) hook. Verified numerically identical to the previous build: 138 decoded NetCDF variables plus
  `globalflux` unchanged on a matched single-cell 2000–2019 run. A copy is kept as `bin/lpjml_rung2`.
