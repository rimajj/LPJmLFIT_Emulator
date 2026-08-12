### Added

- **Two opt-in C-oracle switches that give the `ind` table the whole stand and REAL per-stem GPP**
  (`patches/lpjmlfit_ind_true_gpp.patch`, ADR 0130). `LPJ_IND_ALL_HEIGHTS` drops the writer's 5 m
  emission cut; `LPJ_IND_TRUE_GPP` swaps in a new `Pft.agpp_gross` accumulating the same `gpp` that
  feeds the `D_GPP` output. Both are **inert unless set** — `agpp`, `printind` and the frozen
  29-column schema are untouched, and neither field is in `fwritepft`/`freadpft`, so
  `restart_1999.lpj` still loads. Rebuild gated on a matched A/B against the preserved previous
  binary: **139 decoded quantities + `globalflux` identical, 0 differ**.
- `scripts/run_ind_true_gpp_cells.sh` — provisions the runs (inserts the `ind` output entry and the
  exports the integrator-owned wrappers do not forward, and **re-validates with `lpjcheck` after
  patching**, which the wrapper's own pre-insert check cannot do). ~10 s per cell.
- `scripts/diagnose_ind_true_gpp.py` + `test/testitems/references/M_ind_true_gpp_reference.csv` —
  the scorer and its committed fixture. Its gate is also a completeness proof: the sum of
  per-individual `gpp` over all PFTs reproduces the run's own annual `d_gpp` to **4.4e-07 over 100
  cell-years**.
- `scripts/biome_sapwood_bg_probe.jl` PART 5d — the split recomputed with both C columns on F's own
  population, printed beside the old ones with `ln(NPP)` as an invariance check.

### Fixed

- **ADR 0129's photosynthesis-vs-respiration split was a bracket (38–78 %); it is now closed at
  ≈43–47 % photosynthesis / ≈57–53 % respiration at the prototype cell** (ADR 0130). The upper end
  is refuted, so the GSI phenology is not the single cause of F's assimilate error.

### Documented

- **The `ind` table's `gpp` column is a second copy of `npp`, and LPJmL-FIT emits no per-individual
  GPP at all** — `daily_natural.c:193` does `pft->agpp += npp;`, so a per-stem `npp/gpp` is exactly
  1.0000 in all 11 967 tree rows at the five biome cells. This is why removing the height cut alone
  would not have closed the bracket. No published number is affected (every consumer reads `npp`).
  Recorded in `CLAUDE.md` §3 and the `lpjmlfit-cbinary` skill, which also gains the
  build-your-own-A/B rebuild-gate rule and the `ind`-TXT reading traps (it has a header; pin the
  dtypes, because the uninitialised `mort_*` columns defeat type inference).
