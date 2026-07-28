### Changed

- **The ONLINE configuration is now ESM-first and validated against OBSERVATIONS, not LPJmL-FIT
  ([ADR 0082](docs/decisions/0082-online-esm-first-ownership-and-validation.md), owner decision).** Two
  explicit configurations replace one compromised model. **OFFLINE** is unchanged and keeps guardrail 3 (the C
  binary is the oracle). **ONLINE** hands skin temperature, the surface energy balance and the soil
  water/thermal column to **Terrarium**, and is scored against PLUMBER2/FLUXNET fluxes and observed
  LAI/biomass/tree-cover — so a divergence from LPJmL-FIT online is no longer automatically a bug.
  Conservation (guardrail 2) binds both. Our contribution online is **vegetation**: Component S, FIT
  photosynthesis behind `AbstractPhotosynthesis`, and FIT's water-limited ET behind the pluggable
  **`AbstractEvapotranspiration`** slot. The deciding evidence for handing over the SEB: Terrarium computes LE
  *through* the ET scheme **inside** its skin-temperature solve and then recomputes ET at the converged
  T_skin (`surface_energy_balance.jl:128/149-151`), so LE and T_skin are mutually consistent — whereas
  Component E takes LE from F evaluated at a *different* temperature and makes H the residual (ADR 0017's
  documented "no privileged residual" exception). Offline that is a caveat; online it is a defect, because
  SpeedyWeather computes its own humidity flux. We also inherit two-phase heat conduction with freeze curves,
  which we do not have and which is not optional for boreal/permafrost land. **`ClimBuf`** cold-starts from a
  ~20–30 yr SpeedyWeather-only spin-up on **its own** climate; obsclim seeding is rejected because
  SpeedyWeather's climate is not Earth's, which would bias the establishment gate for a full trailing window.
  ADR 0017's scope narrows to offline **without** being superseded — Component E remains the offline closure
  and an independent cross-check on Terrarium's SEB.
- **`soilmoist` must map to the layer-mean of Terrarium's `plant_available_water`, not
  `saturation_water_ice`.** The latter is normalized by **porosity** (θ/θ_sat) while LPJmL's `w` is a fraction
  of **water-holding capacity**, so substituting it is a *definitional* mismatch rather than a distribution
  shift; `FieldCapacityLimitedPAW` computes `min((θw−θwp)/(θfc−θwp), 1)`, which is exactly LPJmL's semantics.
  Training reference measured for comparison (historic, 1 348 400 cell-years): `soilmoist` min 0.017,
  q50 0.464, mean 0.508. Re-validating — and if needed retraining — Component S on Terrarium-derived
  `soilmoist` is an **integration point with line S** (a version-bumped online artifact, never an in-place
  mutation), and is a hard gate on online demography.
