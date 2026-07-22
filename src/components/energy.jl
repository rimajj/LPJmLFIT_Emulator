# Component E — surface-energy-balance + skin-temperature closure (new). DEVELOPMENT_PLAN §2.4.
# The ESM interface LPJmL-FIT lacks (no H, no Rn closure, no skin temperature — DESIGN §1.2).
#
# IMPLEMENTATION (ADR 0017): SELF-CONTAINED, not a Terrarium.jl dependency. ADR 0006 chose to *reuse*
# Terrarium's `SurfaceEnergyBalance`/`ImplicitSkinTemperature`, but flagged (a) an OPEN licensing blocker
# (LPJmL AGPL-3.0 ↔ Terrarium EUPL-1.2 — embedding code across repos needs a legal read) and (b) that
# Terrarium is v0.1.x/unstable. Combined with this package's deliberately EMPTY runtime `[deps]` and the
# offline compute nodes (no pkg-server), the same call ADR 0014 made for the fast core applies here:
# reimplement the (compact, well-specified) physics from scratch, AD-friendly and dependency-free. ADR
# 0017 records this as superseding 0006's *implementation* choice while keeping its physics decisions
# (one consistent skin temperature; H the documented residual; LE water-limited from F).

"""
    AbstractEnergyClosure

Interface for the energy closure E. Solves one skin temperature `T_skin` from
`Rn(T_skin) = SWdown(1−α) + ε·LWdown − εσT_skin⁴` and closes `Rn = LE + H + G` with
`H = ρ c_p g_a (T_skin − Tair)`. **LE is fixed by water availability** (from F), so **H is the
residual** — a documented, deliberate exception to "no privileged residual" (validate hardest vs
FLUXNET). Returns [`EToATM`](@ref) for the atmosphere and [`EToF`](@ref) (the mandatory skin-T
feedback) so F's ground heat is consistent with the one surface temperature.
"""
abstract type AbstractEnergyClosure end

"""
    SEBParams{T}

Frozen physical constants and solver settings for the self-contained surface-energy-balance closure
[`SEBEnergyClosure`](@ref) (DEVELOPMENT_PLAN §2.4; ADR 0017). All values are standard land-surface
constants; the two tunables (`lambda_g`, `tau_soil`) govern the ground-heat term and its deep-soil
reference temperature and are the only knobs a FLUXNET calibration of G would touch.
"""
Base.@kwdef struct SEBParams{T <: AbstractFloat}
    emissivity::T = 0.97            # surface longwave emissivity, – (vegetation/soil)
    sigma::T = 5.670374419e-8       # Stefan–Boltzmann constant, W/m²/K⁴
    c_p::T = 1004.6                 # specific heat of air at constant pressure, J/kg/K
    R_d::T = 287.05                 # gas constant of dry air, J/kg/K
    karman::T = 0.41                # von Kármán constant, –
    z_ref::T = 10.0                 # nominal forcing/reference height, m (raised above the canopy if needed)
    d_frac::T = 0.67                # zero-plane displacement as a fraction of canopy height, –
    z0m_min::T = 0.01               # floor on momentum roughness length, m (bare/short surfaces)
    z0h_ratio::T = 0.1              # heat vs momentum roughness: z0h = z0h_ratio · z0m, – (kB⁻¹ ≈ 2.3)
    ga_min::T = 0.001               # floor on aerodynamic conductance, m/s (avoid decoupling / 1/0)
    ga_max::T = 1.0                 # cap on aerodynamic conductance, m/s
    lambda_g::T = 7.0               # soil thermal conductance for G = λ_g·(T_skin − T_soil), W/m²/K
    tau_soil::T = 30.0              # deep-soil temperature EWMA timescale, days
    n_newton::Int = 12              # FIXED Newton iterations (fixed computational graph ⇒ AD-friendly)
    omega::T = 1.0                  # Newton damping factor, –
    min_wind::T = 0.1               # floor on wind speed, m/s
    # Demand cap (DEVELOPMENT_PLAN §2.4): cap LE ≤ Rn − G in demand-limited cases. OFF by default: F
    # already water-limits ET, so `le` is the REAL water-limited flux, and when Rn − G < 0 (e.g. a
    # radiatively cooling night with nonzero ET) the energy for LE is supplied by sensible-heat
    # convergence (H < 0) — the documented "H is the residual" mechanism. Capping there would DISCARD
    # water F committed to (violating conservation) because the unused-water return to F is not wired in
    # v1. Enable only alongside that return path (a later refinement). Default uncapped ⇒ exact closure,
    # conservation-safe, H the pure residual.
    enable_cap::Bool = false
end

"""
    aerodynamic_conductance(p::SEBParams, wind, z0m, height) -> g_a

Bulk aerodynamic conductance `g_a` (m/s) from the neutral logarithmic wind profile
(Monin–Obukhov, neutral limit):

    g_a = k² · U / [ ln((z − d)/z0m) · ln((z − d)/z0h) ]

with von Kármán `k`, reference height `z` (raised to clear the canopy + displacement so the logs stay
positive for tall forests), displacement `d = d_frac · height`, momentum roughness `z0m` (from S /
allometry), and heat roughness `z0h = z0h_ratio · z0m`. Wind and `g_a` are floored/capped for
robustness. Neutral-only in v1 (a bounded Richardson-number stability correction is the documented
refinement, DEVELOPMENT_PLAN §2.4). Units: `H = ρ c_p g_a ΔT` ⇒ W/m² with `g_a` in m/s. ✓
"""
function aerodynamic_conductance(p::SEBParams{T}, wind, z0m, height) where {T <: AbstractFloat}
    z0m_e = max(z0m, p.z0m_min)
    d = p.d_frac * max(height, zero(T))
    z = max(p.z_ref, d + z0m_e + T(2))          # keep the reference above canopy+displacement
    z0h = p.z0h_ratio * z0m_e
    lm = log((z - d) / z0m_e)
    lh = log((z - d) / z0h)
    ga = p.karman^2 * max(wind, p.min_wind) / (lm * lh)
    return clamp(ga, p.ga_min, p.ga_max)
end

"""
    solve_seb(p::SEBParams, swdown, lwdown, tair, psurf, wind, albedo, z0m, height, le, t_soil)
        -> (t_skin, Rn, H, G, le_out, g_a, capped)

Pure, AD-friendly core of the closure. Solves one skin temperature `t_skin` (K) from the closed
surface energy balance by a **fixed-iteration damped Newton with a fixed computational graph** (the
same AD-safe pattern as `FDiff.solve_lambda`):

    f(Tₛ)  = SW↓(1−α) + ε·LW↓ − ε·σ·Tₛ⁴ − LE − ρc_p g_a (Tₛ − Tair) − λ_g (Tₛ − T_soil)
    f'(Tₛ) = −4εσTₛ³ − ρc_p g_a − λ_g            (strictly < 0 ⇒ unique root; Newton robust)

`LE` (from F, `= λ·ET`) is **fixed, not free**; after the solve, `H = Rn − LE − G` is the **residual**
that closes `Rn = LE + H + G` to machine precision (the documented exception, DEVELOPMENT_PLAN §2.4).
Air density `ρ = psurf/(R_d·Tair)`. `t_soil` is the deep-soil reference for the ground heat `G`.
**Demand cap:** if `LE > Rn − G` (rare, demand-limited), `LE` is capped to the available energy and
`capped=true` is returned so the caller can return the unused evaporative demand to F's water balance
(water and energy stay consistent — §2.4); `H` then closes with the capped `LE`.
"""
function solve_seb(
        p::SEBParams{T}, swdown, lwdown, tair, psurf, wind, albedo, z0m, height, le, t_soil
    ) where {T <: AbstractFloat}
    ρ = psurf / (p.R_d * tair)
    ga = aerodynamic_conductance(p, wind, z0m, height)
    hcoef = ρ * p.c_p * ga                        # W/m²/K
    swnet = (one(T) - albedo) * swdown
    lwin = p.emissivity * lwdown
    Ts = tair                                     # physical initial guess (skin near air temperature)
    for _ in 1:p.n_newton
        Rn = swnet + lwin - p.emissivity * p.sigma * Ts^4
        H = hcoef * (Ts - tair)
        G = p.lambda_g * (Ts - t_soil)
        f = Rn - le - H - G
        df = -T(4) * p.emissivity * p.sigma * Ts^3 - hcoef - p.lambda_g
        Ts = Ts - p.omega * f / df
    end
    Rn = swnet + lwin - p.emissivity * p.sigma * Ts^4
    G = p.lambda_g * (Ts - t_soil)
    avail = Rn - G                                # energy available for turbulent fluxes
    # Demand cap OFF by default (see `SEBParams.enable_cap`): trust F's water-limited LE, let H be the
    # pure residual (can be negative when Rn − G < 0). When enabled, cap LE to the (non-negative)
    # available energy in the demand-limited case.
    capped = p.enable_cap && le > avail && avail ≥ zero(T)
    le_out = capped ? avail : le
    H = Rn - le_out - G                           # RESIDUAL — closes Rn = LE + H + G exactly
    return (Ts, Rn, H, G, le_out, ga, capped)
end

"""
    SEBEnergyClosure{T} <: AbstractEnergyClosure

Concrete self-contained energy closure (ADR 0017). Holds the frozen [`SEBParams`](@ref) and the one
piece of prognostic state E owns: the **deep-soil reference temperature** `t_soil` (K), an exponential
moving average of air temperature on the `tau_soil`-day timescale that anchors the ground-heat term
`G = λ_g·(T_skin − T_soil)`. Build one per cell and drive it with [`solve!`](@ref) each (sub-)daily
step alongside the fast core. `t_soil` is lazily initialised to the first day's air temperature.
"""
mutable struct SEBEnergyClosure{T <: AbstractFloat} <: AbstractEnergyClosure
    params::SEBParams{T}
    t_soil::T
    initialized::Bool
end

"""
    SEBEnergyClosure{T}(; params=SEBParams{T}(), t_soil0=nothing) -> SEBEnergyClosure
    SEBEnergyClosure(; ...) ≡ SEBEnergyClosure{Float64}(; ...)

Construct the closure. Pass `t_soil0` (K) to seed the deep-soil reference temperature (e.g. the site's
20-yr mean annual temperature from `SharedState.climbuf_atemp_mean20`); otherwise it initialises to the
first day's air temperature on the first [`solve!`](@ref).
"""
function SEBEnergyClosure{T}(; params::SEBParams{T} = SEBParams{T}(), t_soil0 = nothing) where {T <: AbstractFloat}
    seeded = t_soil0 !== nothing
    return SEBEnergyClosure{T}(params, seeded ? T(t_soil0) : zero(T), seeded)
end
SEBEnergyClosure(; kwargs...) = SEBEnergyClosure{Float64}(; kwargs...)

"""
    solve!(E::SEBEnergyClosure, state::SharedState, from_f::FToE, bc::SToE, forcing::AtmForcing)
        -> (EToATM, EToF)

Advance the deep-soil reference temperature one step (EWMA toward `forcing.tair`), solve the surface
energy balance for one `T_skin` given F's latent heat `from_f.le` and the structural boundary
conditions `bc` (albedo, z0, height) from S, and return the atmosphere-facing payload [`EToATM`](@ref)
(`Rn = LE + H + G` closed by construction, H the residual, `NBP_atm` from F's carbon terms) and the
mandatory skin-temperature feedback [`EToF`](@ref) (`T_skin`, `G(T_skin)`, `g_a`) for F's top thermal
boundary. Pure physics in [`solve_seb`](@ref).
"""
function solve!(
        E::SEBEnergyClosure{T}, state::SharedState, from_f::FToE, bc::SToE, forcing::AtmForcing
    ) where {T <: AbstractFloat}
    tair = T(forcing.tair)
    if !E.initialized
        E.t_soil = tair
        E.initialized = true
    else
        a = one(T) / E.params.tau_soil
        E.t_soil = (one(T) - a) * E.t_soil + a * tair
    end
    (Ts, Rn, H, G, le_out, ga, capped) = solve_seb(
        E.params, T(forcing.swdown), T(forcing.lwdown), tair, T(forcing.psurf), T(forcing.wind),
        T(bc.albedo), T(bc.z0), T(bc.height), T(from_f.le), E.t_soil,
    )
    nbp = nbp_atm(rh = from_f.rh, firec = from_f.firec, npp = from_f.npp, flux_estabc = from_f.flux_estabc)
    atm = EToATM{T}(le = le_out, h = H, g = G, t_skin = Ts, nbp_atm = nbp, z0 = T(bc.z0))
    tof = EToF{T}(t_skin = Ts, ground_heat = G, g_a = ga)
    return (atm, tof)
end

"""
    energy_residual(atm::EToATM, Rn) -> residual

Diagnostic closure residual `Rn − (LE + H + G)`. By construction of [`solve_seb`](@ref) (H is the
residual) this is ≈ 0 to machine precision — the Phase-4 hard gate. `Rn` is the net radiation at the
solved skin temperature (returned by `solve_seb`).
"""
energy_residual(atm::EToATM, Rn) = Rn - (atm.le + atm.h + atm.g)

# Abstract fallback: any closure that has not implemented `solve!` errors (keeps the interface honest).
solve!(::AbstractEnergyClosure, ::SharedState, ::FToE, ::SToE, ::AtmForcing) =
    error("This AbstractEnergyClosure has no `solve!` method — use `SEBEnergyClosure` (ADR 0017).")
