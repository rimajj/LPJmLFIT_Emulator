### Fixed

- **The committed Hainich demo count DRF is regenerated onto the REAL feature basis, so the two artifacts one
  emulator loads together are on ONE basis again (ADR 0032 closed, milestone S1c).**
  `test/testitems/references/drf_forest_hainich.drf` + `_meta.txt` were trained on the retired proxy features
  (`soilmoist = 0.7`, `lai = 21.2`, `growth_eff = 19`) while `recruit_copula_hainich.rcop` beside them was on
  the real ones — a live ADR-0023 train/inference shift on the artifact the in-loop gates read first. Both are
  now rebuilt from a single table build; the `.rcop`, its meta and both `hainich_slow_oracle_*.csv` came back
  **byte-identical**, and the `.rcop`'s conditioning row now lies inside the `.drf`'s trained band on all
  **8/8** shared columns (0 violations). Every re-measured Hainich drift threshold improved: Gate-3 Height
  `nqrmse` **0.3895 → 0.2998**, median Height ratio 1.2463 → 1.1316, settled count ratio 0.6734 → **1.2808**
  (the in-domain flux drivers raise the count from ~6.8 to ~12.9 stems/patch, and more stems sharing the same
  carbon are smaller trees). The Gate-3 alarm is **tightened 0.45 → 0.40** accordingly — no threshold widened.

### Added

- **Runtime-consistency is now observable and CI-gated, not inferred (ADR 0034).**
  `FluxDrivenSlowEmulator.feature_history` records the exact `flux_feature_vector` row handed to the forest
  each year (diagnostic only — no numerical change, every committed baseline byte-identical), and
  `scripts/train_slow_drf.jl` writes the trained `y_min`/`y_max`/`feat_min`/`feat_max` bands into every
  artifact meta. `slow_production_drf_tests.jl` now asserts the RUNTIME rows against that band. This replaces
  a check that could not fail: a DRF prediction is a convex combination of training leaf means, so "predicted
  targets are inside the training band" holds however out-of-domain the input is — which is exactly how a
  two-order-of-magnitude proxy-basis shift stayed invisible behind green gates.
- `scripts/measure_hainich_gate_bands_probe.jl` — re-measures every threshold the four committed-Hainich-fixture
  gates assert, in one run, plus the two checks the tests structurally cannot do (artifact-vs-artifact basis
  agreement, and runtime-vs-trained feature band). `DRF_ART`/`DRF_META` point it at an older artifact to
  produce the BEFORE column of a before/after table; it reproduced the documented pre-S1c numbers
  (0.39 / 1.25 / 0.67) exactly, which is what validates the harness.

### Changed

- **Measured, and documented as debt: 4 of 15 runtime feature columns are still outside the trained band
  (ADR 0034), from three separate causes** — `water_stress` 0.323–0.331 vs [0, 0.043] (an **F_diff-vs-C**
  difference; the F core is line M's), `soilmoist` 0.792–0.999 vs [0.842, 0.867] (a year-end instantaneous
  value against an annual-mean training basis), and `lai`/`fpc` (one patch against the C's cell-mean
  `LAI_STAND`). So the demo emulator is conditioned consistently on 11 of 15 columns, **not** fully
  runtime-consistent, and the Gate-3 improvement above must not be re-cited as such. The set is pinned by the
  new assertion, so a *new* column drifting out fails CI. Fixing the two S-side causes is milestone **S1d**,
  which precedes S2; `water_stress` is raised to line M.
