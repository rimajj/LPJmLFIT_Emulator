# ADR 0083 — The online soil carries the LPJmL-FIT texture map, behind a degeneracy guard

- **Status:** accepted
- **Date:** 2026-08-05
- **Line:** O (online coupling) — implements ADR 0082 §4, milestone O3a
- **Supersedes / superseded by:** none. Implements ADR 0082; does not touch ADR 0017.

## Context

`[VERIFIED 2026-07-28, job 1622830]` Terrarium's default soil stratigraphy is
`HomogeneousSoilStratigraphy(NF)` → `ConstantSoilHorizon` with `SoilTexture(NF)` =
**`sand = 1.0, clay = 0.0`**. The default hydraulics are `SoilHydraulicsSURFEX`, which computes

```
wilting_point  = 37.13e-3 · √(clay·100)
field_capacity = 89.0e-3  · (clay·100)^0.35
```

Both are **exactly zero** at `clay = 0`. `FieldCapacityLimitedPAW` then evaluates

```
plant_available_water = max(min(1, (θw − θwp)/(θfc − θwp)), 0)  ≡  1.0    wherever θw > 0
```

This **does not error**. It silently reports *fully unstressed everywhere*, deleting the drought
response while every diagnostic still looks plausible, and it feeds Terrarium's own
`soil_moisture_limiting_factor` → photosynthesis chain. It is the most dangerous of the two
silent failures found in Terrarium's vegetation path (the other being the `MedlynStomatalConductance`
`@assert abs(vpd) > 0` crash, ADR 0082 / trap 5).

Two consequences follow. First, **no online run on the default soil may be used to judge
vegetation** — which blocks ADR 0082 §4's `soilmoist` comparison, since a degenerate PAW ≡ 1
cannot be compared against anything. Second, the failure mode is a *class*, not an instance: any
future texture or porosity configuration can re-enter it, so a one-off fix is insufficient.

## Decision

### 1. Prescribe the LPJmL-FIT ground-truth soil texture

The online soil uses a **single `PrescribedSoilHorizon` named `:soil`** spanning the whole column,
whose `sand_fraction` / `silt_fraction` / `clay_fraction` input fields are the LPJmL-FIT
ground-truth soil map nearest-neighbour-mapped onto the ring grid.

Source, and why this one rather than SoilGrids 2.0:

- `.../clustering/global/soil_code_test.soil.bin` — the per-cell LPJmL *soilcode* the ground-truth
  run actually read (1 byte per cell; `newgrid.c:449` does `soil_id = soilmap[soilcode] − 1`).
- `par/soil_20m.js` `soilpar` — the sand/silt/clay mass fractions the C oracle itself uses.
- `.../clustering/global/soil_code_test.grid.clm` — the **orderA** coordinates (v3 .clm, float32,
  HDR 51, scalar 1.0; header parsed, never assumed).

Using the C oracle's own texture keeps the online soil texturally consistent with the offline
oracle **and** with the `soilmoist` training reference the O3b comparison scores against, so a
distribution difference is attributable to the hydrology rather than to the soil map. SoilGrids
2.0 (the upstream `SoilGridsStratigraphy` path) is a better absolute dataset but would confound
exactly that comparison, needs `NumericalEarth.jl` + several hundred MB downloaded at first use —
impossible on compute nodes with no egress — and resolves six depth horizons that LPJmL's
single-texture column has no counterpart for. It stays the natural upgrade once O3b is settled.

Porosity is `SoilPorositySURFEX` (`0.49 − 0.11·sand`) rather than the `ConstantSoilPorosity(0.49)`
default, so porosity and the retention curve are derived from the same texture.

**One horizon, not six**, because LPJmL prescribes one texture per cell for the whole column; a
six-horizon stratigraphy would only replicate that texture six times. Its thickness is a finite
1000 m rather than the library default `Inf`: with a single horizon the depth selection in
`with_soil_horizon` is unconditional either way, and this keeps `Inf` arithmetic out of the kernel.

### 2. The prescription must go through `fields`, not `inputs`

`SpeedyWeatherTerrariumExt` constructs its `ModelIntegrator` with an **empty `InputSources(NF)`**,
so the `InputSource`-based prescription used by Terrarium's own
`examples/simulations/soil_heat_global_soilgrids.jl` is **silently dropped** under SpeedyWeather —
the horizon would fall back to its `sand_fraction` default of 1.0, i.e. straight back into the
degeneracy. Only `TerrariumLand.fields` is forwarded (→ `Terrarium.initialize(...; fields)` →
`StateVariables`, which resolves `ns_fields = get(fields, varname(ns), (;))` per namespace). So the
texture is passed as `fields = (soil = (sand_fraction = …, silt_fraction = …, clay_fraction = …),)`,
and a gate asserts the fields actually arrived in the model state (non-zero **and** spatially
varying `clay_fraction`) rather than trusting that they did.

### 3. A guard, so this class of degeneracy fails loudly

`assert_nondegenerate_soil` (`scripts/online_coupling/soil_texture.jl`) evaluates Terrarium's own
`field_capacity` and `wilting_point` for every column's texture and **throws** if
`field_capacity − wilting_point <= 1e-4` anywhere, naming the offending column. It runs inside
`prescribed_texture_soil`, before the model is built. The run-level gate additionally asserts that
PAW has real spread across cells and is not pinned at 1.0.

### 4. PAW is evaluated with Terrarium's own kernel function, not a re-derivation

The `soilmoist` comparison calls `Terrarium.compute_plant_available_water(i, 1, k, grid, state, …)`
post-hoc on the coupled state. That routes through Terrarium's `soil_volume`, so the organic
fraction and the per-column prescribed texture enter exactly as they would inside the vegetation
stack. The previous hand-rolled reconstruction (`θw = sat·liq·porosity`, ignoring the organic
fraction) is dropped — an independent re-derivation of the quantity under test is precisely what
guardrail 5 warns against.

## Consequences

- ADR 0082 §4's `soilmoist` comparison is unblocked *as far as the soil configuration goes*, but is
  **not yet answerable** — see the two blockers below. Its target is **ADR 0035's**, not ADR 0082's
  original wording (verified here against `src/components/slow.jl:227` rather than taken on trust):
  `root_zone_soilmoist` is the `whcs`-weighted mean of the plant-available fraction over the top
  **3 LPJmL layers = 1.0 m**, read at year end, and the live reference table is
  `cell_year_soilmoist_ye_hist.parquet` (q50 0.498, mean 0.478) — **not** the retired `swc`-derived
  one (mean 0.5075), which is porosity-normalized and is exactly the basis this ADR's mapping
  avoids. Because this configuration has a single horizon, `θfc − θwp` is depth-constant within a
  column and the `whcs` weighting reduces exactly to thickness weighting over the root zone; that
  equivalence is a property of the one-horizon setup and would not survive a multi-horizon
  stratigraphy.
- **Blocker 1 — the default hydrology is `NoFlow`.** `[VERIFIED job 1706262]` layer-mean saturation
  was `min == max == 0.8917` over all 4608 columns after two coupled days: the `SaturationWaterTable`
  initializer, unchanged, despite the adapter pushing `rainfall`/`snowfall` in every step. Any
  distribution measured under the default hydrology is the initializer, not a model result.
  `RichardsEq` is verified to work coupled (`[VERIFIED job 1706324, exit 0]`).
- **Blocker 2 — spin-up.** `[VERIFIED job 1706324]` 10 days of `RichardsEq` from a near-saturated
  433 m column is still mid-drainage (mean PAW 0.104 unweighted / 0.225 over 2 m). Together with the
  `NoFlow` run (0.949) the two *bracket* the reference; neither is a spin-up, and neither may be
  quoted. RRE costs ~110 s per simulated day on that column, so the spin-up is a real budget item.
  Mitigation: `ExponentialSpacing`'s `Δz_max = 2.5` gives a ≈19.5 m column matching LPJmL's geometry,
  which both fixes the whole-column contrast and equilibrates ~20× faster.
- Ocean columns under `RockyPlanetMask` have no LPJmL counterpart; they receive the global-median
  LPJmL type (loam, clay 0.18) and are excluded from the comparison via the returned `is_land`
  mask. The fallback is reported, never silently assumed to be data.
- **Correction to CLAUDE.md §1** (verified here): `/p/projects/biodiversity/input_VERSION2/grid.bin`
  — the coord file named in the repo checkout's `input_GSWP3-W5E5.js` — is a **global** 67 420-cell
  grid in **longitude-major** order in which Hainich is index **28008**. 28008 is not a
  "`-DSINGLESITE` grid" index. orderA (Hainich = 42490) is a different ordering, supplied by the
  ground-truth run's own `soil_code_test.grid.clm`. The two soil files are **not interchangeable
  row-for-row**; pairing orderA indices with `grid.bin` shifts every cell silently.
- Worth reporting upstream (the owner is in TUM-PIK-ESM): a `clay = 0` default that silently makes
  `plant_available_water ≡ 1` should at minimum warn, and the SpeedyWeather adapter dropping
  `InputSources` means the documented Terrarium input path does not work under SpeedyWeather.

## Artifacts

- `scripts/online_coupling/build_soil_texture_field.py` — soilcode + soilpar + orderA grid → the
  per-cell texture table (`/p/tmp/jamirp/esm_online_coupling/lpjml_soil_texture_orderA.csv`).
- `scripts/online_coupling/soil_texture.jl` — the ring-grid mapping, the `PrescribedSoilHorizon`
  soil, and `assert_nondegenerate_soil`.
- `scripts/online_coupling/diagnose_soilmoist_shift.jl` — the coupled run, the O3a gate and the
  O3b `soilmoist` comparison.
