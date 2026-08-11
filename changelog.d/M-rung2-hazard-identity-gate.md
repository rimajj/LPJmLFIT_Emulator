### Added

- **Line M — the rung-2 mortality port is verified against the C binary EXACTLY, and it is now a CI gate**
  (ADR 0122). `scripts/diagnose_rung2_hazard_identity.jl` scores line S's ported per-individual mortality
  hazard (`src/trait_mortality.jl`, which has no call site and had never been checked against the C on real
  per-tree state) against the LPJmL-FIT C binary's own `mortality_tree_ind` on all 9 951 tree-patch-years of
  the recorded rung-2 dump (cell 42490, 25 patches, 2000–2019, PFT ids 1–6). All four hazards, the capped
  total and both hard kills agree to double round-off (max relative Δ **1.6e-15**, 0 exceedances; 175
  growth-failure kills and 195 ghost-tree kills classified correctly). This is the free identity gate line S
  offered in ADR 0117 item 4, and it makes ADR 0049's "θ = 1 recovers FIT exactly" a measurement rather than
  an assertion. `test/testitems/m_rung2_hazard_identity_tests.jl` re-scores the port on every CI run against a
  333-record PFT-stratified C-truth fixture (`test/testitems/references/M_rung2_hazard_identity.csv`).
- **Line M — two dump columns that make the fourth hazard observable**
  (`patches/lpjmlfit_rung2_hook_v4.patch`, supersedes v3). `bm_delta` and `leafarea_real` are published as
  write-only `Pfttree` fields, because `mort_npp` — the hazard through which the whole wood-density trait
  channel enters — needs post-allocation quantities that are not reconstructable from the previous schema.
  Both are initialised on both tree-creation paths, unlike their `mort_*` siblings, since the external
  demography reads them. The restart-file format is unchanged. Two rebuilds, each gated on decoded variables:
  110 quantities identical, 0 differ, with the `ind` and `globalflux` text outputs byte-for-byte.

### Fixed

- **Line M — the rung-2 dump-equality gate no longer reports a false failure on an exact arm** (ADR 0122).
  Uninitialised first-year values of the two new columns made it call an arm whose roster was identical in
  every year, and whose cell state agreed in all 1 500 patch-years, "DIFFERENT model state". The ADR-0121
  replay floor survives the schema change unchanged: null control 1.000, kills arm 1.000 exact, no year differs.

### Changed

- **Line M — arm C is pre-registered as NOT scorable on the trait question from the current rendezvous**
  (ADR 0122). The external demography is asked for its answer at the top of the annual block, so it sees last
  year's growth outcome. Per-tree ordering survives that (Spearman ρ median 0.900 against the C's own hazard),
  but the one-year wood-density selection differential flips sign: the C's +17 729 gC/m³ against the lagged
  basis's −14 528 (ratio −0.819). Attributed one term at a time, it is the consecutive-growth-failure counter,
  not the growth-efficiency lag (which comes out at ratio +1.001) and not the hard kills. The fix is a change
  to where the rendezvous happens, not to the ported operator; the lag does not exist in the standalone
  emulator, where the fast core computes the year's growth before the demography runs.
