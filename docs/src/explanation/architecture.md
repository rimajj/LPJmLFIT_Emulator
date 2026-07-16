# The three-component architecture

```@meta
CurrentModule = LPJmLFITEmulator
```

> *Explanation — the concepts and the reasoning. For the exact signatures see the
> [API reference](../reference/api.md); for the frozen schemas see `DESIGN.md` §2 and §8.*

LPJmL-FIT [Sakschewski2016](@cite) is a demographic, flexible-trait dynamic global vegetation model
(DGVM): it simulates many individual trees per patch, each with its own traits (SLA, wood density,
leaf longevity, …) and size, and lets a trait *continuum* sort itself out under competition. That
individual-tree bookkeeping — establishment, allocation, growth, mortality over many individuals ×
patches — is the expensive, path-dependent part. The daily *biophysics* (photosynthesis, water,
soil thermal) is comparatively cheap and already conserves mass.

The hybrid splits the model along exactly that seam into **three components that share one state**.

## S — the slow distribution emulator (ML, annual)

**S is the scientific novelty.** Instead of stepping thousands of individual trees, S emulates the
per-cell **distribution** over trees `p(traits, size ∣ drivers, state)` together with a count `N` —
the "Trait Probability Density" view of a community [Carmona2016](@cite). It is conditioned on the
annual climate summary, CO₂, soil, the 20-year climate memory (`Climbuf`), the previous-year
distribution summary, stand age, the NPP the fast core actually delivered (`bm_inc`), and the four
LPJmL-FIT mortality drivers (water, temperature, growth-efficiency, age).

Crucially, S does **not** regenerate a fresh snapshot each year. It **advances the existing
population** with increments that sum to the delivered NPP — see
[Conservation by construction](conservation.md). The abstract interface is
[`AbstractSlowEmulator`](@ref).

## F — the fast physical core (kept from LPJmL-FIT, daily)

F is LPJmL-FIT's own daily biophysical core, **kept unchanged**: photosynthesis → GPP → NPP (per
representative individual, preserving the trait → flux link), the water balance (transpiration,
soil/interception evaporation, runoff, drainage), snow, and the enthalpy-based soil thermal solve.
Because it is the real physical code, water and carbon are conserving *by construction*; F is the
reason the hybrid can inherit closure rather than re-learn it. The abstract interface is
[`AbstractFastCore`](@ref).

F is parameterised by S (it receives *structure*, not fluxes) and, at year-end, hands S back the
single conserved quantity [`FToS`](@ref)`.bm_inc`.

## E — the surface-energy-balance closure (new, daily → sub-daily)

LPJmL-FIT has **no surface energy balance**: no sensible heat `H`, no net-radiation closure, no skin
temperature (`DESIGN.md` §1.2 verifies this against the source). An ESM atmosphere needs all of them.
E adds them: it solves for one skin temperature `T_skin` from
`Rn(T_skin) = SWdown(1−α) + LWdown − εσT_skin⁴` and closes `Rn = LE + H + G`. Rather than build this
from scratch, the plan **reuses Terrarium.jl's** `SurfaceEnergyBalance` + `ImplicitSkinTemperature`
(see `ECOSYSTEM_AND_COUPLING.md` §2 and [ADR 0006](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0006-reuse-terrarium-seb.md)).
The abstract interface is [`AbstractEnergyClosure`](@ref).

Because LPJmL's ET is water-limited (not energy-balance-derived), `LE = λ·ET` is *given* and **H is
the residual** — a deliberate, documented exception to the "no privileged residual" rule, validated
hardest against flux towers ([Conservation by construction](conservation.md)).

## One authoritative shared state

The load-bearing rule (`00_START_HERE.md` rule 1; `DESIGN.md` §2): **every prognostic state exists
exactly once**, in [`SharedState`](@ref). No component keeps a private copy.

- **F owns and integrates** soil water (`w`, `w_fw`, `w_evap`, `rw_buffer`), snow (`snowpack`), the
  soil thermal state (volumetric enthalpy `enth`, the fundamental quantity), and the SOM/litter
  carbon pools (`som_fast`, `som_slow`, `litc`).
- **S owns the vegetation distribution** and *allocates* into vegetation carbon (`vegc`).
- The cell climate memory (`climbuf_mtemp20`, `climbuf_mprec20`, `climbuf_atemp_mean20`) conditions S.

Array shapes are keyed to the LPJmL-FIT constants, never to literals — [`NSOILLAYER`](@ref) = 23,
[`LASTLAYER`](@ref) = 22, [`NHEATGRIDP`](@ref) (= `NSOILLAYER × `[`GPLHEAT`](@ref)),
[`NTREEPOOLS`](@ref) = 7, [`CLIMBUFSIZE`](@ref) = 20 — so a rebuild that changes, say, `GPLHEAT`
changes the thermal dimension automatically. [`checkdims`](@ref) enforces the frozen shapes.

## The interface contract (who hands what to whom)

The S↔F↔E handoffs are *codeable* payload structs (`DESIGN.md` §8); each field has a unit and maps to
a shared-state field or an LPJmL output id.

| Direction | Payload type | Role | Conserved? |
|---|---|---|---|
| S → F (annual) | [`SToF`](@ref) | structural boundary conditions (LAI, height, `z0`, rooting depth, Vcmax proxy, FPC, albedo) | no — structure, re-derived by allometry |
| S → E (annual) | [`SToE`](@ref) | structure for `Rn` and aerodynamic conductance | no |
| F → S (annual) | [`FToS`](@ref) | the conserved NPP increment `bm_inc` + stress/state drivers | **yes** — S allocates exactly `bm_inc` |
| F → E (daily; +annual) | [`FToE`](@ref) | `LE = λ·ET` and the four carbon terms E needs for `NBP_atm` | **yes** |
| E → F (daily) | [`EToF`](@ref) | the one `T_skin` (mandatory top thermal BC) + consistent `G` | no |
| E → ATM (sub-daily) | [`EToATM`](@ref) | `LE, H, G, T_skin, NBP_atm, z0` — the ESM interface | **yes** (`Rn = LE+H+G`) |
| ATM → F/E | [`AtmForcing`](@ref) | forcing; `wind` and `psurf` are NEW inputs LPJmL-FIT ignores | no |

The registry [`COMPONENTS`](@ref) / [`FLUXES`](@ref) encodes exactly this graph in code and is the
source of truth for the code-derived [diagrams](../diagrams.md).

## Data flow across timescales

- **Slow → fast** passes *boundary conditions* (structure), never fluxes. S derives LAI, canopy
  height, roughness `z0`, rooting depth, a Vcmax proxy, FPC and albedo from the distribution via
  LPJmL-FIT's *own allometry* — they are not co-predicted.
- **Fast → slow** passes the single *conserved* carbon increment `bm_inc`. S must allocate exactly
  that; carbon cannot be invented at the handoff.
- **Fast ↔ energy** shares one surface temperature so that `Rn`, `H`, and `G` refer to the *same*
  surface. The `E → F` skin-temperature feedback is therefore **mandatory**, not optional: it
  replaces F's native air-temperature Dirichlet boundary condition.
- **Energy → atmosphere** is the ESM interface: `LE`, `H`, `G`, `T_skin`, `NBP_atm` (diagnostic), and
  roughness `z0`.

For the coupling ecosystem this plugs into (SpeedyWeather.jl + Terrarium.jl + NumericalEarth.jl) see
`ECOSYSTEM_AND_COUPLING.md`.
