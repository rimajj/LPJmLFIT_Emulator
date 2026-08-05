### Added

- **Component E: opt-in two-layer prognostic ground-heat column** (`SEBParams.enable_two_layer`, default
  `false` ⇒ every baseline byte-identical). Replaces the single conductance against a 30-day EWMA of *air*
  temperature with a prognostic two-layer soil column (`G = κ_g(T_skin − T1)`, `κ_g = 2λ_soil/z1`, the
  MITgcm land-package `T1`/`T2` update), so the ground reference is the surface's own thermal state.
  An **independent implementation** of the MITgcm formulation, cross-read against SpeedyWeather.jl's
  `LandBucketTemperature` and Terrarium.jl's half-cell skin temperature; no code copied, no new dependency
  (ADR 0074, ADR 0017). `SEBParams` also gains an explicit `dt_seconds`, which is what makes a sub-daily
  step well-defined.
- `scripts/e_two_layer_probe.jl` + `scripts/e_seb_drive_common.jl` (shared PLUMBER2 drive-table readers and
  metrics, extracted so future probes stop copying them).

### Changed

- `solve_seb` gained a trailing `lambda_g =` keyword defaulting to `p.lambda_g` — the default call is
  bit-for-bit the previous computation.
- `docs/src/explanation/architecture.md`: the component-E section still claimed E **reuses** Terrarium.jl's
  `SurfaceEnergyBalance`. ADR 0017 superseded that in July — E is self-contained. Corrected, with the
  Terrarium/SpeedyWeather relationship (coupling substrate, cross-read only) stated accurately.

### Verified

- **E7 beats the fitted `λ_g = 1.0` it was only asked to match**, with nothing fitted (497k PLUMBER2 tower
  steps, 4 sites; harness reproduces ADR 0073's published numbers digit for digit). Daily step, at the two
  sites whose towers can score H: DE-Hai H R² 0.035 → 0.645 (fitted arm 0.637) and G R² −39.4 → 0.717
  (0.657); AU-ASM H R² 0.329 → 0.775 (0.745) and G R² −15.4 → 0.614 (0.477). `Rn` unchanged within ±0.005.
- Sub-daily, the diurnal amplitude of `G` becomes correct at closed-canopy sites (DE-Hai all-hours sd(G)
  5.75 vs observed 5.66, against the default's 34.7) and **night `G` R² turns positive at DE-Hai (+0.394)**.
  Nocturnal **H** R² stays negative (−0.324) exactly as ADR 0073's `ε_obs` bound requires.
- No secular drift: at the 16-year AU-Tum record the second-half annual-mean trend is −0.059 K/yr (T1) and
  −0.015 K/yr (T2), with mean daily `G` 0.001–0.072 W/m² — the closed-bottom column self-equilibrates, so
  no deep-restore term is needed.
- Known limitations, quoted rather than hidden: one global `z1` cannot serve both a closed canopy and a
  sparse desert (AU-ASM's observed all-hours sd(G) is 64 W/m²), and sub-daily `T_skin` degrades at
  AU-Tum/AU-Rob.
