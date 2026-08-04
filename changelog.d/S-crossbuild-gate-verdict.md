### Added

- **ADR 0043 — the cross-build gate PASSES: the `Feb  5 2026` and `Jul 21 2026` LPJmL-FIT builds are
  trajectory-identical and may be pooled as a pure seed pair.** Closes the question ADR 0041 specified
  but could not run to a verdict. The matched-decomposition gate (full-grid 67 420 cells / 2048 tasks,
  a faithful re-run of the ssp370 seed1 member) reproduces the seed1 ground truth bit-for-bit:
  `globalflux` `cmp`-identical, `vegc` identical across all seven variables by SHA-256, and the 193 GB
  per-individual `ind` roster `cmp`-identical over all 81 years — a far stronger result than the gate
  required, since `ind` is the finest grain the model emits.
- `scripts/diagnose_ind_seed_independence.py` gains **`--log-dir <run_dir>`**, which resolves the newest
  non-empty `lpjml_*.out` instead of taking a pinned job id, and now treats a 0-byte log as a distinct
  provenance FATAL rather than a gate failure.

### Fixed

- The ssp370 seed2 **independence gate had failed spuriously**: when the hung member was resubmitted, its
  chained gate jcf still named the *cancelled* attempt's 0-byte log, so it reported `no completion line at
  all` for a C run that had in fact terminated cleanly over all 67 420 cells — and left the 93 GB parquet
  conversion stranded on `DependencyNeverSatisfied`. Re-run against the real log, the member **passes all
  four checks** and is confirmed a genuine second realization.

### Changed

- CLAUDE.md §3 gains two C-oracle gotchas: a chained child that hardcodes a parent's job id is not
  resubmit-safe (and an empty log is indistinguishable from an unfinished run unless called out), and a
  file-level `cmp` on a NetCDF output is the wrong equality test because LPJmL writes a timestamped
  `history` attribute.
- Reclaimed ~181 GB by deleting the cross-build gate's redundant `ind_2020_2100.csv`, retained only until
  its bit-identity to the seed1 original was proven.
