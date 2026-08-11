### Added

- **Per-cell(-year) bioclimatic eligible-PFT table for the ported establishment rule**
  (`scripts/build_estab_eligibility.py`, ADR 0170): all 67 420 cells × 20 historic years, from FIT's own
  gate inputs (`temp_min20`/`temp_max20` = 20-yr running means of each year's coldest/warmest monthly
  mean, the current year's daily GDD5 and precipitation total), gated against FIT's own `ind` output at a
  0.076 % residual. Committed single-cell fixture `test/testitems/references/S_hainich_estab_eligibility.csv`.
- **`ARM=recruit` dimension on `scripts/trait_mortality_arm_probe.jl`** — the response 2×2 with the
  contrast axis switched from `trait_mortality` to the recruit channel (R0 = pinned copula, R1 = the
  ADR-0119 ported rule), plus a mechanism panel that reads the DRAWN recruit marginal per scenario, and a
  per-year eligibility policy fed from the fixture above.
- `EstabDiag` now records the four drawn trait values, so the recruit marginal can be tracked directly
  instead of being inferred from the standing community (gated by the establishment testitem).

### Changed

- `scripts/summarize_response_seed_ensemble.py` is arm-aware: it labels the arm, applies the recruit
  arm's own preconditions (the rule must have drawn, and the seedbank must have filled), and refuses to
  average two different arms into one ensemble.

### Fixed

- Documented that `n_elig == 0` does **not** mean "nothing establishes here": FIT's inheritance channel
  (`establishmentpft_ind.c:125`) is not bioclimatically gated, so a cell whose gate has closed keeps
  recruiting its resident genotypes. The ported sampler already behaved correctly; the description of the
  gate did not.
