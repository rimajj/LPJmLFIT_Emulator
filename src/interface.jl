# Fast↔slow↔energy interface contract (DESIGN.md §8). These are the codeable I/O signatures:
# every field has a unit and maps to a shared-state field or an LPJmL output id.
#
# Rules encoded here (START_HERE §3):
#   S→F/E : boundary conditions (structure), NOT fluxes — re-derived from the distribution via allometry.
#   F→S   : the conserved carbon increment `bm_inc` — S allocates exactly this (flux-then-integrate).
#   F→E   : LE=λ·ET plus the four carbon terms E needs to form NBP_atm.
#   E→F   : the ONE skin temperature (mandatory top thermal BC) so Rn/H/G share one surface.
#   E→ATM : LE,H,G,T_skin,NBP_atm,z0 — Rn(T_skin)=LE+H+G closed by construction; H is the residual.

"S → F (annual): structural boundary conditions, re-derived from the trait/size distribution."
Base.@kwdef struct SToF{T<:AbstractFloat}
    lai::T          # leaf area index, m²/m²
    height::T       # canopy height, m
    z0::T           # roughness length, m
    rootdepth::T    # rooting depth (D95), mm
    vcmax::T        # photosynthetic capacity proxy, µmol/m²/s
    fpc::T          # foliar projective cover, –
    albedo::T       # surface albedo, –
    # representative individuals (weighted trait sample) attached at Phase 3
end

"S → E (annual): structure for Rn and aerodynamic conductance."
Base.@kwdef struct SToE{T<:AbstractFloat}
    albedo::T       # –
    z0::T           # m
    lai::T          # m²/m² (canopy structure for g_a)
    height::T       # m
end

"F → S (annual): the CONSERVED carbon increment + stress/state drivers. S allocates exactly `bm_inc`."
Base.@kwdef struct FToS{T<:AbstractFloat}
    bm_inc::T       # annual NPP increment delivered by F, gC/m²/yr (the conserved quantity)
    water_stress::T # –
    temp_stress::T  # –
    growth_eff::T   # growth efficiency (bm_inc / leaf-area history), –
    soilmoist::T    # root-zone soil moisture state, fraction of WHC
end

"""
F → E (daily; +annual channel): LE plus ALL four carbon terms E needs for NBP_atm.
`flux_estabc` arrives on the annual channel; the rest are daily (DESIGN.md §8, review finding 8).
"""
Base.@kwdef struct FToE{T<:AbstractFloat}
    le::T           # latent heat = λ·ET, W/m² (derived, not predicted)
    gpp::T          # gross primary production, gC/m²/day
    npp::T          # net primary production, gC/m²/day  (Ra = GPP − NPP)
    rh::T           # heterotrophic respiration, gC/m²/day
    firec::T        # fire carbon emission, gC/m²/day
    flux_estabc::T  # establishment carbon influx, gC/m²/yr  (ANNUAL channel)
    ground_heat::T  # ground-heat term for the thermal update, W/m²
end

"E → F (daily): the ONE skin temperature (mandatory top thermal BC) + consistent ground heat."
Base.@kwdef struct EToF{T<:AbstractFloat}
    t_skin::T       # skin/surface temperature, K  (replaces F's air-temp Dirichlet BC)
    ground_heat::T  # G(T_skin), W/m²
    g_a::T          # aerodynamic conductance, m/s
end

"E → ATM (sub-daily): the ESM interface. `Rn(T_skin)=LE+H+G` closed by construction; H is the residual."
Base.@kwdef struct EToATM{T<:AbstractFloat}
    le::T           # latent heat, W/m²
    h::T            # sensible heat (RESIDUAL = Rn − G − LE), W/m²
    g::T            # ground heat, W/m²
    t_skin::T       # skin temperature, K
    nbp_atm::T      # atmosphere-facing net C flux = Rh+firec−NPP−flux_estabc, gC/m²/day (diagnostic)
    z0::T           # roughness length, m
end

"ATM → F/E: forcing. `wind` and `psurf` are NEW inputs LPJmL-FIT ignores (used only in E)."
Base.@kwdef struct AtmForcing{T<:AbstractFloat}
    swdown::T       # downward shortwave, W/m²
    lwdown::T       # downward longwave, W/m²
    tair::T         # air temperature, K
    qair::T         # specific humidity, kg/kg
    wind::T         # wind speed, m/s        (NEW — component E only)
    psurf::T        # surface pressure, Pa   (NEW — component E only)
    precip::T       # precipitation, mm/day
    co2::T          # CO₂ partial pressure, ppm (held constant — see DESIGN.md §9)
end
