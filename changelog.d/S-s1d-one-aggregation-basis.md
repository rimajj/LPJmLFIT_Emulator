### Changed

- **Component S (S1d, ADR 0035): `soilmoist` and `lai` are on ONE basis in the training table and the
  coupled runtime — and neither fix is the one ADR 0034 predicted.**
  - `soilmoist` was not a time-aggregation mismatch but the **wrong variable**: the training column reduced
    the C `swc` output (total water over SATURATION capacity, `update_daily.c:411`) while the runtime fed
    `state.w` (plant-available water as a fraction of WHC). `swc` cannot be inverted back — LPJmL-FIT emits
    no `wsats`/`wpwps`. Both sides now use the root-zone (`forrootmoist`, top 1 m), `whcs`-weighted mean of
    `w` at year end: new deriver `scripts/build_rootmoist_soilmoist_feature.py` (from `d_rootmoist.nc` +
    `whc_nat.nc`) and new `LPJmLFITEmulator.root_zone_soilmoist` in `src/components/slow.jl`, which all
    three `slow.jl` call sites use. This finally matches `FToS.soilmoist`'s own documented definition.
  - `lai` is now the **per-patch** stand LAI, reconstructed in-row from the emitted `LAI` + `fpc_ind`
    (`build_slow_runtime_table.py::patch_stand_lai_expr`), replacing the C `LAI_STAND` cell-mean join that
    was broadcast onto per-patch rows. Contrary to the previously documented limitation, this IS
    reconstructable from the 29-column `ind` output; the new
    `scripts/diagnose_patch_lai_reconstruction.py` validates it against the C's own crown allometry
    (median relative error 1.8e-8 over 22 498 stems in five biomes). `growth_eff`'s divisor inherits the
    fix, so its numerator and denominator are finally the same patch and the same stem population.
- `flux_feature_vector` takes the fast core's `SoilColumn` as a sixth positional argument (it had no caller
  outside `slow.jl`). The frozen S→M contract — feature-column ORDER, `live_flux_cond`, the `.drf`/`.rcop`
  format, `FluxDrivenSlowEmulator` kwargs — is unchanged.
- Committed Hainich demo artifacts `drf_forest_hainich.drf` (+ meta) and `recruit_copula_hainich.rcop`
  (+ meta) regenerated **together from one table build**; the two oracle reference CSVs are unchanged.
- `scripts/build_swc_soilmoist_feature.py` and `scripts/build_laistand_lai_feature.py` marked SUPERSEDED
  (retained so the pre-0035 tables and artifacts stay reproducible). The new `soilmoist` table is written
  to a new `_ye` path; no existing artifact is overwritten in place.

### Fixed

- The `lai == 0 → growth_eff` blow-up class (ADR 0031) is now structurally impossible rather than guarded:
  `lai` is derived from the same `ind` rows being aggregated, so it can no longer come from a different
  seed's trajectory via a cross-seed join.

### Gates

- `soilmoist` is **inside** the trained band (was 5.1× band width); `lai` fell from 2.9× to 0.021× (12-yr)
  / 0.086× (20-yr). The pinned out-of-band set in `slow_production_drf_tests.jl` shrinks to
  `{water_stress}` alone — an F_diff-vs-C difference owned by line M — with new bounds asserting
  `soilmoist` exactly inside and `lai`/`fpc` ≤ 0.2 band widths.
- Thresholds **tightened, none widened**: DIRECT copula draws SLA 0.22 → 0.10 (measured 0.1274 → 0.0391)
  and Wooddens 0.12 → 0.06 (0.0346 → 0.0273). Gate-3 Height `nqrmse` 0.2998 → 0.2990 (alarm stays 0.40),
  settled count ratio 1.2808 → 1.1597, carbon residual 1.9e-12, artifact basis-agreement violations 0.
