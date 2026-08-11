### Added

- **The ported LPJmL-FIT establishment rule — recruit traits computed from the C's parameter files instead
  of learned from its output ([ADR 0119](docs/decisions/0119-port-fits-establishment-rule-instead-of-learning-a-recruit-marginal.md)).**
  Implements an explicit owner steer: which trees are *born* in FIT is a parameter-file fact (uniform draws
  on each PFT's own trait intervals, mixed with inheritance from the cell's rolling top-AGB seedbank at the
  closed-form weight `4/(4 + n_elig)` — ≈44 % inherited in a five-PFT cell, ≈80 % in a single-PFT one), so
  only *who survives* has to be learned. This removes by construction the double count
  [ADR 0118](docs/decisions/0118-the-recruit-copula-already-carries-the-selection-arm-c-would-add.md)
  measured at **+12.18 % on `Wooddens`**, where the survivor-trained recruit copula already carries the
  selection the `trait_mortality` operator adds. New `Establishment` submodule (pure Base, zero new deps)
  ports the eligibility gate (`establish.c:29-33`), both channels' rates
  (`establishmentpft_ind.c:97-140`), the uniform draw (`numeric.h:59`), the inheritance diffusion
  (`new_tree.c:38-61`) and the 50-year rolling top-AGB seedbank (`getsapling.c`); the opt-in
  `FluxDrivenSlowEmulator(...; recruit_establishment = RecruitEstablishment(...))` hook feeds it the
  emulator's OWN roster each year and records a per-year `EstabDiag` (channel, eligible count, seedbank
  state) — reading which is a stated precondition for interpreting any arm. **Default `nothing` ⇒ every
  committed baseline, the AD gate and every pinned artifact byte-identical**, and the flip criterion is
  pre-registered in the same ADR (§6) with the kill condition that matters: the recruit channel must not
  reproduce the count recursion's climate-dependent error
  ([ADR 0112-0116](docs/decisions/0116-the-count-recursions-drift-is-a-one-sided-failure-to-follow-stem-losses.md)).
  Three departures from the C are stated rather than hidden — the port is distributional (FIT's RAND48
  stream and `gasdev` cache are not reproducible), one cohort per year replaces FIT's Poisson counts, and
  the drawn PFT identity reaches the roster only behind a second flag because the canopy template still
  carries the donor cohort's physiology. Also **corrects ADR 0045's wording**: the interval-violation rule
  is not a reflection but an inward uniform redraw between the parent and the crossed bound, with a point
  mass on the bound — which is exactly where the boreal `minwscal`/`d95max` intervals live. Parameters live
  in ONE generated artifact (`test/testitems/references/S_pft_estab_params.csv` via
  `scripts/build_estab_params_reference.py`, reusing the existing `cpp -P` parser rather than a second
  copy), gated row-by-row by `test/testitems/slow_establishment_tests.jl`.
