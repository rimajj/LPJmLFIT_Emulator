---
status: "accepted"
date: 2026-07-28
deciders: "Jamir Priesner (owner) — direct instruction; analysis by line O"
consulted: "ADR 0017 (self-contained E), ADR 0014, ADR 0020/0023/0026/0027 (Component S), ADR 0080/0081, docs/p4_online_coupling_design.md §5, the installed Terrarium 0.1.3 source"
informed: "line S (soil-moisture retraining is an integration point), line M (the run.jl/interface.jl seam), line E (Component E keeps the offline path)"
supersedes: "—"
---

# The ONLINE configuration is ESM-first: Terrarium owns skin temperature + soil, we own vegetation + ET, and it is validated against OBSERVATIONS — not against LPJmL-FIT

## Context and Problem Statement

`docs/p4_online_coupling_design.md` §5 left two questions open on purpose: **who owns soil water and skin
temperature** when both this project (F_diff's bucket, Component E) and Terrarium have an implementation, and
**how `ClimBuf` gets its climatology on a coupled cold start**. Both are modelling decisions, not wiring, and
the design doc warned they must not be settled implicitly by whichever slot was convenient.

The owner settled them on 2026-07-28 with a decisive scoping statement: *"for the online version the goal is
best possible ESM, not LPJmLFIT fidelity. validation should be on observed climate/vegetation, not necessarily
on lpjmlfit."* Plus: do the soil-moisture validation/retraining for Component S.

## Decision Drivers

- **Two purposes were being served by one configuration.** "Faithfully emulate LPJmL-FIT" and "be the best
  possible ESM land component" genuinely conflict: LPJmL's simple bucket and our residual-H closure *are*
  what fidelity means (the Hainich C-oracle validation), while a 30-layer soil with phase change and an
  implicitly-consistent surface energy balance is what quality means.
- **`[VERIFIED]` Terrarium solves LE and T_skin implicitly TOGETHER; our Component E does not.**
  `processes/surface/surface_energy_balance.jl:128` computes `latent_heat_flux` *through* the
  evapotranspiration scheme inside the skin-temperature solve, and :149-151 then **recomputes the ET
  component fluxes from the final skin temperature**. Component E instead takes LE from F — evaluated at a
  *different* temperature — and makes H the residual, which ADR 0017 records as "the documented 'no
  privileged residual' exception". Offline that is a caveat; online it is a defect, because SpeedyWeather
  computes its own surface humidity flux and will disagree with the water F thinks it lost.
- **`[VERIFIED]` `AbstractEvapotranspiration` is a pluggable slot** (`models/surface/surface_hydrology_model.jl:14/29`,
  default `BareGroundEvaporation`, with `PALADYNCanopyEvapotranspiration` showing a canopy scheme is the
  expected shape). So our distinguishing ET physics has a proper home *below* the SEB rather than beside it.
- **Terrarium's soil is better than ours where an ESM is judged**: 30 layers, SURFEX hydraulics with
  Brooks–Corey retention and unsaturated conductivity, **two-phase heat conduction with freeze curves**,
  infiltration as a real boundary condition. We have no freeze/thaw at all, and boreal/permafrost land is
  not optional in a global ESM.
- **One water budget, or drift.** With SpeedyWeather supplying precipitation and the land supplying
  evaporation and runoff, two competing hydrologies is how a coupled model drifts.
- **The C binary cannot be the oracle for a model that is deliberately not LPJmL-FIT.** An ESM-first online
  configuration must be scored against reality.

## Decision Outcome

**Two explicit configurations with different owners, different physics and different validation bases.**
This is not a compromise between them; it is a refusal to compromise either.

### 1. Ownership

| Concern | OFFLINE (fidelity) | ONLINE (ESM-first) |
|---|---|---|
| Skin temperature, turbulent fluxes, SEB closure | **Component E** (`SEBEnergyClosure`) — unchanged | **Terrarium** `SurfaceEnergyBalance` + `ImplicitSkinTemperature` |
| Soil water + soil thermal | **F_diff** bucket (LPJmL-FIT's) — unchanged | **Terrarium** `SoilEnergyWaterCarbon` + `SoilHydrology` |
| Evapotranspiration / water limitation | F_diff (Priestley–Taylor demand/supply) | **OURS**, as an `AbstractEvapotranspiration` implementing LPJmL-FIT's demand/supply water limitation |
| Photosynthesis, respiration | F_diff | **OURS**, behind `AbstractPhotosynthesis` (the O3 spike) |
| Trait/size distribution + demography | **S** (the novelty) | **S** (the novelty) |
| Atmosphere | prescribed forcing | **SpeedyWeather** |

Our scientific contribution online is **vegetation**: the S trait/size emulator, FIT's photosynthesis, and
FIT's water-limited ET. We stop competing with Terrarium on soil and surface energy, and gain its implicit
LE↔T_skin consistency and its freeze/thaw physics in exchange.

### 2. Validation basis — the substantive reframing

- **OFFLINE keeps guardrail 3 exactly as written:** the LPJmL-FIT C binary is the oracle; F_diff is validated
  against it and never against itself. Nothing about the offline path is relaxed by this ADR.
- **ONLINE is validated against OBSERVATIONS**, not against LPJmL-FIT: observed climate and observed
  vegetation. Concretely — PLUMBER2/FLUXNET for the energy and water fluxes (line E's reference set already
  being staged, ADR 0070/0072); observed LAI/biomass/tree-cover products for the vegetation state; observed
  climatology for the atmosphere. **A divergence from LPJmL-FIT in the online configuration is not
  automatically a bug** — it may be an improvement, and must be judged against data.
- **Guardrail 3 is SCOPED, not weakened.** It continues to bind every claim about F_diff and the offline
  emulator. What changes is that the online configuration is a different model with a different reference.
  Conservation guardrail 2 (water, carbon, energy closure) binds **both** configurations unconditionally.
- The offline↔online difference becomes a **reported quantity**, not an embarrassment: run both on the same
  forcing and publish the gap.

### 3. `ClimBuf` cold start — spin up on SpeedyWeather's OWN climate

**Rejected:** seeding `gdd5`/`tas_cold_month` from the offline obsclim climatology. SpeedyWeather's simulated
climate is not Earth's climate, so an observation-seeded establishment gate would be out of step with the
climate the model actually produces for a full trailing window — a bias precisely where establishment is
decided.

**Chosen:** a **two-stage spin-up**. Run SpeedyWeather with simple/prescribed land for ~20–30 model years,
accumulate `ClimBuf` from *its* climate, checkpoint it, and use that as the ClimBuf initial condition for
coupled runs. Self-consistent, and cheap — SpeedyWeather's speed is the reason it was chosen. Keep the
obsclim seed only as a comparison case, flagged as prescribed in output metadata.

This composes with **ADR 0027**: because the boundary is transient (trailing window), a seeded start
*converges* to the model's own climate over the window rather than staying frozen — the property 0027 chose
deliberately for physical correctness under warming.

### 4. Component S's `soilmoist` must be re-derived and re-validated — an integration point with line S

`soilmoist` is a **load-bearing trained feature** (ADR 0023: train/inference consistency). At runtime it is
`sum(state.w) / length(state.w)` (`slow.jl:191`) — the unweighted mean over LPJmL's 23 soil layers of `w`,
the **fraction of water-holding capacity** (a plant-available basis).

**`[VERIFIED]` The naive mapping is wrong and the right one exists.** Terrarium's `saturation_water_ice` is a
fraction of **porosity** (θ/θ_sat) — a *different normalization*, so substituting it would be a definitional
mismatch, not merely a distribution shift. But `FieldCapacityLimitedPAW` computes
`W = min((θw − θwp)/(θfc − θwp), 1)` (`processes/vegetation/hydraulics/plant_available_water.jl`) — which is
**exactly LPJmL's `w` semantics**. So:

> **Map `soilmoist` ← the layer-mean of Terrarium's `plant_available_water`, NOT `saturation_water_ice`.**

That choice is what makes the trained conditioning transferable at all. It still must be *proven*, not
assumed: the layer count (30 vs 23), the depth weighting, and the retention parameterization all differ.

#### `[VERIFIED 2026-07-28]` Finding from step 1 — a real soil-texture map is a HARD PREREQUISITE

The diagnosis (job 1622830) ran the coupled model for 2 days and got the soil state out cleanly
(`saturation_water_ice`, `liquid_water_fraction`, both `(4608, 1, 30)`), then hit the substantive problem:

**Terrarium's DEFAULT stratigraphy is pure sand, which degenerates the SURFEX water-retention formulas to
zero.** `ConstantSoilHorizon(NF, name)` defaults to `texture = SoilTexture(NF)` = `sand=1.0, clay=0.0`, and
`SoilHydraulicsSURFEX` computes

```julia
wilting_point   = 37.13e-3 * sqrt(clay * 100)      # = 0 when clay = 0
field_capacity  = 89.0e-3  * (clay * 100)^0.35     # = 0 when clay = 0
```

So `θfc = θwp = 0` **exactly**, and
`PAW = max(min(1, (θw − θwp)/(θfc − θwp)), 0) = max(min(1, θw/0), 0)` **≡ 1.0 wherever θw > 0**
(and `NaN` only where bone dry). It does not error — **it silently reports "fully unstressed" everywhere.**

This is the dangerous failure mode, not a blocking one: online vegetation would run with **no water
limitation at all**, producing plausible-looking output with the drought response deleted. It would also
silently feed Terrarium's own `soil_moisture_limiting_factor` → `LUEPhotosynthesis` chain, which is further
evidence that the vegetation path is unexercised upstream (cf. the `MedlynStomatalConductance` VPD ≥ 0
assertion crash, also found 2026-07-28).

**Consequence — promoted onto the critical path:** prescribing a **real soil-texture (clay fraction) and
porosity field** is a *prerequisite* for online Component S, not a later refinement. Terrarium provides
`PrescribedSoilHorizon` and a `TerrariumRastersExt` for exactly this. Until it is in place:
- `soilmoist` cannot be derived online, so the §4 distribution comparison cannot be completed;
- **any online run with default soil has no water stress** and must not be used to judge vegetation.
Add an explicit guard that rejects a soil configuration whose `field_capacity ≤ wilting_point`.

**Required work (integration point — `src/components/slow.jl`, `src/drf.jl`, `scripts/*slow*` are line S's
exclusive paths, ADR 0029):**
1. **Diagnose (line O):** dump Terrarium's layer-mean `plant_available_water` from a coupled run and compare
   its distribution against the training table's `soilmoist` column. Quantify the shift (KS, quantiles, per-cell).
2. **Decide from the evidence:** if the distributions align, the existing DRF/copula transfer and only a
   documented mapping is needed. If they do not, **retrain S's DRF + copula on Terrarium-derived
   `soilmoist`** — a version bump of the `.drf`/`.rcop` artifacts, never an in-place mutation (ADR 0029's
   S→M contract), yielding an *online* artifact alongside the offline one.
3. Either way `soilmoist` stops being a "documented proxy" for the online path.

### Consequences

- Good: the online model gets freeze/thaw, a real unsaturated-zone hydrology, and an implicitly consistent
  LE↔T_skin — three things we do not have and would not have built well.
- Good: our novelty is sharpened rather than diluted. S plus FIT's photosynthesis and water-limited ET is a
  genuine contribution; a second mediocre soil column is not.
- Good: validating online against observations is the honest test of "best possible ESM", and it unblocks
  scoring against PLUMBER2/FLUXNET rather than against a model that itself has known biases.
- Bad: **two configurations to maintain and test**, and they will diverge. The divergence must be measured
  every time either side changes, or the offline fidelity claim and the online quality claim drift apart
  silently. This is the main cost and it is real.
- Bad: S's conditioning is trained on LPJmL hydrology. Until §4 is done, **online demography is not
  trustworthy** — that is a hard gate on O5, not a caveat.
- Bad: ADR 0017's outcome now holds only for the offline path. It is **not** superseded (its zero-runtime-deps
  and v0.1.x-churn drivers still justify a self-contained offline E, and E becomes the independent
  cross-check on Terrarium's SEB — two closures agreeing on one forcing is real evidence), but its scope is
  narrowed and that must not be forgotten when reading it.
- Neutral: observed-vegetation validation needs datasets not yet on disk (LAI/biomass/tree-cover products).
  That is a data-sourcing task, and it is now on the critical path for the online claim.

## More Information

- Implements the open items in `docs/p4_online_coupling_design.md` §5; that doc is updated to point here.
- The immediate next steps are unchanged in order: the O3 photosynthesis spike (still the right first
  mechanical step, and unaffected by this decision), then the `AbstractEvapotranspiration` implementation,
  then §4's soil-moisture diagnosis, then the ClimBuf two-stage spin-up.
- Revisit if Terrarium's soil or SEB turns out to be worse than ours on the PLUMBER2 comparison — in which
  case the ownership table in §1 is the thing to change, and this ADR should be superseded rather than edited.
