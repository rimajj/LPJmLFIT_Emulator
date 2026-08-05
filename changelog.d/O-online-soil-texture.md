### Added

- **Line O / O3a — a real, spatially varying soil texture for the online (Terrarium) soil, plus a guard
  against the silent degeneracy it fixes** ([ADR 0083](docs/decisions/0083-online-soil-texture-and-degeneracy-guard.md)).
  Terrarium's default stratigraphy is pure sand (`clay = 0`), which collapses SURFEX's wilting point and
  field capacity to *exactly zero* and makes `plant_available_water ≡ 1` everywhere — no error, just
  "fully unstressed everywhere". The online soil now uses a single `PrescribedSoilHorizon` carrying the
  LPJmL-FIT ground-truth soil-texture map (`scripts/online_coupling/build_soil_texture_field.py` →
  `soil_texture.jl`), with SURFEX porosity, and `assert_nondegenerate_soil` throws on any configuration
  where `field_capacity <= wilting_point`.
- The texture must be supplied through `TerrariumLand`'s `fields`, **not** `InputSources`:
  `SpeedyWeatherTerrariumExt` builds its `ModelIntegrator` with an empty `InputSources`, so the input
  path used by Terrarium's own SoilGrids example is silently dropped under SpeedyWeather. A gate asserts
  the texture actually reached the model state.

### Changed

- `scripts/online_coupling/diagnose_soilmoist_shift.jl` now runs on the prescribed soil, evaluates
  plant-available water with Terrarium's own `compute_plant_available_water` (instead of a hand-rolled
  re-derivation that ignored the organic fraction), and reports the ADR 0082 §4 `soilmoist` comparison
  over land columns only, as both an unweighted layer mean and a thickness-weighted top-2 m mean.

### Fixed

- `CLAUDE.md` §1: `28008` is Hainich's index in `input_VERSION2/grid.bin` — a **longitude-major global**
  grid — not in a `-DSINGLESITE` grid. That file and the orderA `soil_code_test.grid.clm` are not
  interchangeable row-for-row, nor are their paired soil-code files.
