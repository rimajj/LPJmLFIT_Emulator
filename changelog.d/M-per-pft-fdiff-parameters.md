### Added

- **Per-PFT parameters for the fast core, so each tree cohort runs its own physiology instead of beech's
  ([ADR 0126](docs/decisions/0126-per-cohort-pft-parameters-for-the-fast-core.md)).** `FDiffFastCore` gave
  **every tree in every cell** the temperate-beech parameter set. The measured cost (ADR 0125): the
  maintenance-respiration coefficient `respcoeff` is **0.2** for the tropical broadleaved evergreen tree
  (PFT id 0) and **1.2** for all six temperate/boreal trees, so at the two hot biome cells — 100 % id 0 by
  sapwood — F over-respired every stem sixfold and its annual carbon balance went **negative** where the
  C model's was +1073 gC/m²/yr. Four more parameters differ materially: the Beer–Lambert extinction
  `lightextcoeff` (0.45 needleleaved / 0.59 broadleaved), the photosynthesis optimum `temp_photos` (15/25 °C
  for the three boreal trees vs 20/30 for the other four), the minimum canopy conductance `gmin`
  (0.3–1.6), and leaf/root residence (1, 2 or 4 years; sapwood 25 or 30).
  New in `FDiff`: `pft_respparams` / `pft_tempstressparams` / `pft_allocparams` / `pft_allometry` /
  `pft_canopy_traits`, and the per-individual bundle `PFTPhys` / `pft_phys(ids)`. The consuming path takes
  them as an optional per-individual vector (`daily_step_canopy(...; pftphys=)`,
  `individuals_from_pools(...; pftphys=)`, `individual_from_pools(...; k_beer=, tstress=)`,
  `_treepools_fpc(...; k_beer=)`, `_patch_fpars(...; kbeers=)`) and `FDiffFastCore(...; per_pft_params=true)`
  builds it from real per-cohort `pft_ids`.
  **Opt-in and default byte-identical** (guardrail 4): `nothing`/`false` keeps the single shared set, and
  `pft_*(3)` returns F's shipped beech configuration *exactly* (`pft_allocparams(8) ==
  grass_allocparams()` likewise), so a beech-only stand is bit-for-bit unchanged with the channel on — the
  property `test/testitems/per_pft_params_tests.jl` asserts on a full simulated year. The numbers live in
  exactly one place: `test/testitems/references/M_pft_fdiff_params.csv`, generated from the live
  `par/pft_lpjmlfit.js` by `scripts/build_pft_fdiff_params_reference.py` with `cpp -P` (the preprocessor
  LPJmL itself pipes its parameter files through), and gated value-by-value against the Julia literals.
  ⚠ **F-side only:** `run_coupled_cell` REFUSES `per_pft_params=true` together with a slow emulator,
  because S's demography rebuilds the roster with the single shared allometry — that would run two
  `k_beer` bases in one simulation. Wiring the per-cohort sets through `src/components/slow.jl` is an
  integration point raised to line S.
  **The pre-registered pass criterion FAILED and the default was NOT flipped.** Measured at the five biome
  cells (historic 2010–2019, `slow = nothing`, per-stem paired against the C's own individuals): the two hot
  cells are fixed — the Amazon's annual carbon balance goes from **−223 to +1199 gC/m²/yr** against a truth
  of **+1073**, and the Sahel's from −0.457× to **1.132×** — while boreal_siberia moves **1.049 → 1.275**
  and mediterranean_iberia **2.727 → 3.056**, i.e. away from the truth. These are the model's own
  parameters, so the failure is not an argument to revert: it says the criterion required one change to
  also close two defects that were already attributed elsewhere (a 1.5–1.9× allocation/turnover gap and the
  Mediterranean cell's independent 1.3–1.5× photosynthesis bias). Eight single-variable arms attribute it:
  the respiration coefficient is the whole tropical fix on its own (Amazon −0.21 → 1.13), the boreal cell is
  moved by the photosynthesis temperature optimum and the minimum canopy conductance, and the
  Mediterranean cell by the phenology alone.

### Fixed

- **Every tree in the five-cell fast-core probe was running beech's leaf phenology, including the larch and
  the tropical evergreen ([ADR 0126](docs/decisions/0126-per-cohort-pft-parameters-for-the-fast-core.md)
  §5).** `FDiffFastCore` has taken per-cohort `pft_ids` — which select each PFT's own growing-season index
  filters — since long before this change, and the probe simply never passed them. Passing them, with
  nothing else changed, moves the Sahel cell's annual assimilate ratio by **+1.01** (−0.457 → 0.557) and the
  Mediterranean cell's by **+0.38**. Any five-cell fast-core number in this repo that predates ADR 0126
  should be read as being on beech phenology. It also narrows ADR 0125's Sahel reading: about a third of the
  shortfall there was this, not the dry-cell root zone.
