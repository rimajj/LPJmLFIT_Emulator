### Changed

- **`WaterParams.gp_stand_leafon_basis` now defaults to `true`** — F_diff's multi-individual canopy path
  builds each individual's potential conductance at FULL leaf cover and normalizes the phen-weighted sum
  by the PLAIN `Σ fpc`, exactly as `gp_sum.c:53-67` does. F previously folded `phen` into the pass-1
  `apar` and into `gmin` and divided by the phen-weighted `Σ fpc·φ`, biasing stand conductance high by
  ≈`1/φ̄` on every partial-leaf day and carrying that into `demand`, `gc`, `gpd`, `fac`, the solved λ and
  GPP. Guardrail 4 is served by the opt-out (`gp_stand_leafon_basis = false` reproduces the previous
  expression exactly). Scope is unchanged and confirmed by measurement: the single-individual
  `daily_step` / `daily_step_ml` baselines reproduce EXACTLY
  ([ADR 0137](docs/decisions/0137-gp-stand-leafon-basis-default-flip.md), executing
  [ADR 0136](docs/decisions/0136-the-two-gp-sum-basis-differences-measured-one-helps-one-hurts.md) §7).
- `test/testitems/references/hainich_canopy_baseline_2010.txt` — regenerated for the flip:
  `gpp_annual` 1237.437115 → 1143.375187 (−7.60 %), `transp_annual` −4.38 %, `evap_annual` +0.93 %,
  `rootmoist_mean` +0.38 %, `interc_annual` unmoved. The producing run's `gps = false` control arm
  reproduced the previous `gpp_annual` to every printed digit in the same run.
- `test/testitems/biome_coupled_tests.jl` — the five coupled biome LE/GPP signatures re-measured; the
  `GPSTAND=0` control arm returned all ten pre-flip numbers to every printed digit. GPP moves −11.6 %
  (`boreal_siberia`), −6.0 %, −2.8 %, −0.5 %, −0.5 %, i.e. ordered by how much of the year each cell
  spends below full leaf, which is the mechanism's own prediction. Latent heat also falls at every cell
  (−1.05 % to −0.03 %) but not in that ordering, since it carries soil evaporation and interception too.
- `test/testitems/decadal_validation_tests.jl` — the decadal GPP level band re-stated `[1.0, 1.12]` →
  `[0.92, 1.02]` at a measured 0.964132 (width unchanged). F now sits ~3.6 % below the C over the decade
  rather than ~4 % above.
- `test/testitems/sapwood_bg_tests.jl`, `test/testitems/grass_structure_tests.jl`,
  `test/testitems/wscal_leafon_tests.jl`, `test/testitems/gpsum_basis_tests.jl` — pins, bands and
  guardrail-4 assertions re-pointed at the new default, each with the measured value and the reason.
- `test/testitems/slow_level_anchor_tests.jl` (line-S-owned) — the unanchored yr-25 retention floor
  re-pinned 0.7 → 0.55 (measured 0.618996) under line S's explicit authorisation. All four
  anchored-vs-unanchored contrast assertions were unaffected.

### Fixed

- Two assertions that were written as `all(...)` over a vector — the decadal per-year GPP ratios and the
  annual water-stress series — now assert on the extremum instead, so a failure prints the number that
  moved rather than a bare `false`. The previous form cost a whole extra job to learn a magnitude.

### Notes

- The default flip was attempted once and reverted on the same day because its blast radius had not been
  enumerated; it came back at **23 assertions of 275 621 across eight files**, against 3–5 for each of the
  previous four flips. Ten of those were VACUOUS rather than wrong — the gate file's own control arm took
  the package default by omission and became a second copy of the treatment arm at the flip.
- ⚠ The canopy baseline's control arm reproduces the previous `gpp_annual` exactly but the four water rows
  only to ≤ 5.1e-4 relative. That drift is pre-existing and provably not the flip (all three arms in the
  producing run agree on `interc_annual` bitwise); this regeneration absorbs it so the next drift
  measurement starts from zero.
- **UNMEASURED, stated rather than implied:** the yr-150 unanchored retention under the flip. The suite
  reports yr 5 and yr 25 only. Line S has queued the long-horizon assertion in its own file.
