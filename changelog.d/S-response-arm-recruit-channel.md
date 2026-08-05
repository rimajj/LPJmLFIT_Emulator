### Added

- **Component S / Phase 3A Stage 3 — the RESPONSE arm (ADR 0100).** `scripts/trait_mortality_arm_probe.jl`
  gained `MODE=response`: a 2×2 of {`trait_mortality` on, off} × {historic, ssp370 forcing}, all four rollouts
  advanced in one process at matched year indices, scored as a double difference. New extractor
  `scripts/build_hainich_response_forcing.py` pulls **real** daily forcing for both scenarios from the same
  orderA `.clm` files the two LPJmL-FIT ground-truth runs read (+2.45 K, +709 gdd5 at Hainich), behind three
  hard gates — it reproduces the committed `climbuf_hainich_boundary_w20.csv` and `hainich_forcing_2010.csv`,
  and asserts ADR 0004's flat ssp370 CO2. New committed fixture
  `test/testitems/references/S_hainich_response_boundary.csv` (per-scenario-year transient boundary + the
  per-year forcing means, so the uncommitted daily forcing is verifiable without shipping it).
- **Line S ADR block tier 2.** `docs/decisions/README.md` and `CLAUDE.md` §9 now pre-allocate a second ADR
  block per line (S 0100–0119 · M 0120–0139 · E 0140–0149 · O 0150–0159 · integrator 0160–0169); ADR 0049
  had exhausted line S's tier-1 block 0030–0049 mid-milestone.

### Changed

- `scripts/trait_mortality_arm_probe.jl`: the response headline is a **window mean** (`SCORE_WINDOW`, default
  the last 20 yr) rather than a terminal-year read — with real interannual forcing the year-to-year
  interaction swings by more than the signal — and `K_CAP` is exposed so the k-cap merge can be held dormant.
  `MODE=stage2` is unchanged and reproduces every ADR-0049 headline number (job 1700483).

### Fixed

- Nothing in shipped code: `trait_mortality` remains opt-in and default-off, so every committed baseline,
  ReferenceTest and AD path is byte-identical and runtime `[deps]` stays empty.
