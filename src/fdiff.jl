# ── F_diff — the differentiable fast physical core (ADR 0014) ────────────────────────────────────
# The daily CONTINUOUS biophysics of LPJmL-FIT, reimplemented in AD-friendly Julia with the SAME
# equations: photosynthesis→GPP→NPP (C3/C4, Haxeltine & Prentice 1996), the λ (ci:ca) supply/demand
# solve, Priestley–Taylor PET/ET, a soil-water bucket + snow, and maintenance/growth respiration.
# Physics constants are the LPJmL-FIT C-source values (the F1 binary is the numerical-regression
# oracle; the NeuralCrop *crop* constants differ and are NOT used). Ported per ADR 0015 from
# LPJmL-hybrid-photosynthesis (photosynthesis kernel + differentiable λ pattern) and NeuralCrop.jl
# (PET/ET/respiration + the daily-rollout idiom), cross-checked against the LPJmL-FIT C source.
#
# SCOPE (spike): one cell, one representative tree individual, continuous state = soil water + snow;
# canopy STRUCTURE (LAI, FPC, height) is a fixed S→F boundary condition (S owns the discrete
# demography — ADR 0014). Multi-layer soil, full petpar daylength, and SharedState wiring are
# documented scale-up items. Float64 (the C core is `double`); AD verified in the gradient gate.

"""
    FDiff

Differentiable daily fast core. Entry points: [`daily_step`](@ref) (one pure day) and
[`rollout`](@ref) (a 365-day fold accumulating annual fluxes), plus the [`FDiffParams`](@ref) /
[`FDiffState`](@ref) / [`Structure`](@ref) / [`DailyForcing`](@ref) types. The λ (ci:ca) root-find is
[`solve_lambda`](@ref); non-smooth ops use [`SmoothOps`](@ref) surrogates.
"""
module FDiff

using ..Allometry
using ..SmoothOps

export FDiffParams, FDiffState, Structure, DailyForcing,
    photosynthesis, priestley_taylor_eeq, solve_lambda, temp_stress,
    daily_step, rollout, rollout_daily, annual_npp,
    tebs_params, tebs_structure,
    SoilColumn, FDiffStateML, daily_step_ml, rollout_daily_ml, hainich_soilcolumn,
    Individual, daily_step_canopy, rollout_daily_canopy

# ── unit helpers (LPJmL-FIT include/units.h; 273.15 K — NOT the reference's 272.15 bug) ──────────
ppm2bar(co2) = co2 * 1.0e-6          # ppmv → bar  (units.h:23)
ppm2Pa(co2) = co2 * 1.0e-1          # ppmv → Pa   (units.h:24; assumes p = 1e5 Pa)
hour2sec(h) = h * 3600              # h → s
hour2day(h) = h / 24                # h → day-fraction
degCtoK(t) = t + 273.15            # °C → K  (units.h:22 — 273.15 exactly)

# ─────────────────────────────────────────────────────────────────────────────────────────────
# Parameters (LPJmL-FIT C-source values: photosynthesis.c #defines, lpjparam_fit.js, soil.h)
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""
    PhotoParams{T}

Haxeltine & Prentice (1996) photosynthesis constants, LPJmL-FIT values (`src/lpj/photosynthesis.c`
`#define`s + `par/lpjparam_fit.js`). `path=:c3` or `:c4` selects the branch; `b` is the PFT leaf
respiration fraction of Vcmax. `βσ`/`βcol` are the AD-smoothing sharpnesses for the σ / co-limitation
sqrt floors.
"""
Base.@kwdef struct PhotoParams{T <: Real}
    po2::T = 20.9e3          # O2 partial pressure, Pa
    p_atm::T = 1.0e5         # atmospheric pressure, Pa
    q10ko::T = 1.2
    q10kc::T = 2.1
    q10tau::T = 0.57
    tau25::T = 2600.0
    ko25::T = 3.0e4          # Pa
    kc25::T = 30.0           # Pa
    cmass::T = 12.0          # gC/mol
    cq::T = 4.6e-6           # mol quanta / J
    alphac3::T = 0.08
    alphac4::T = 0.053
    theta::T = 0.7           # co-limitation shape (C source; NeuralCrop's 0.9 is crop-specific)
    lambdamc3::T = 0.8       # optimal/max λ, C3
    lambdamc4::T = 0.4       # optimal λ, C4
    bc3::T = 0.015           # leaf resp as fraction of Vmax, C3
    bc4::T = 0.035           # C4
    path::Symbol = :c3
    εσ::T = 1.0e-9           # floor under the σ sqrt
    # SLA-dependent Vcmax cap (`photosynthesis.c:92-97`), ACTIVE in LPJmL-FIT `individual:true` mode
    # (`issla=TRUE`): `vm ≤ vm_n = 11.205·sla^-0.383·1.0368·exp(0.069·(temp-25))`. Defaults keep it OFF
    # (`issla=false`) so the spike baseline is unchanged; the beech TeBS validation set turns it on.
    issla::Bool = false      # apply the SLA Vcmax cap (LPJmL-FIT individual mode)
    sla::T = 0.01986         # specific leaf area, m²/gC (drives the cap; = TeBS value)
    # AD-smoothing sharpness for the `min(vm, vm_n)` Vcmax cap (1/[gC/m²/day]). Vcmax operates at
    # O(1–700) gC/m²/day and the cap `vm_n` at ~30–40, so `β=1` keeps the near-cap deviation
    # (`≤ log(2)/β ≈ 0.69`) negligible AND — crucially — leaves *uncapped* small-Vcmax individuals
    # unbiased (a too-soft β biases `smoothmin(small_vm, vm_n)` DOWN by up to `log(2)/β`, which for
    # the earlier `β=0.05` reached ≈14 and drove light-starved understory individuals to NEGATIVE
    # assimilation once the canopy light was distributed — masked in the single-lumped-individual
    # spike because its Vcmax was always far above the cap).
    βvm::T = 1.0
end

"""
    TempStressParams{T}

Temperature-stress limits (`temp_stress.c`; per-PFT `temp_co2`/`temp_photos`). Defaults are a
temperate/boreal broadleaf tree. `tmax` is the hard high-T cutoff (45 °C C3 / 55 °C C4). `βgate` is
the smoothing sharpness for the daylength/high-T gates.
"""
Base.@kwdef struct TempStressParams{T <: Real}
    temp_co2_low::T = -4.0
    temp_co2_high::T = 38.0
    temp_photos_low::T = 15.0
    temp_photos_high::T = 25.0
    tmax::T = 45.0
    βgate::T = 5.0
end

"""
    WaterParams{T}

Water/PET constants (`include/soil.h`, `lpjparam_fit.js`). **Two Priestley–Taylor coefficients**:
`α_PT=1.32` for soil/PET evaporation and `ALPHAM=1.391` for transpirative demand (a single-α port
is wrong — spec 07 §12). Radiation constants are the Magnus slope / psychrometric / latent-heat
forms. `melt_factor` is the degree-day snowmelt rate; `β*` are AD-smoothing sharpnesses.
"""
Base.@kwdef struct WaterParams{T <: Real}
    α_PT::T = 1.32           # Priestley–Taylor, soil evap / PET
    ALPHAM::T = 1.391        # Priestley–Taylor-like, transpirative demand
    GM::T = 3.26             # empirical conductance param
    lambda_opt::T = 0.8      # λ for potential conductance
    gmin::T = 0.3            # min canopy conductance, mm/s
    wet::T = 0.0             # wet-canopy fraction on leaves
    emax::T = 5.0            # max transpiration (PFT), mm/day
    dayseconds::T = 86400.0
    # Priestley–Taylor eeq radiation forms (petpar.c / NeuralCrop radiation.jl)
    s_num::T = 2.503e6       # Pa, slope-of-esat numerator
    s_a::T = 17.269
    s_b::T = 237.3           # °C
    gamma_c0::T = 65.05      # Pa/K, psychrometric
    gamma_c1::T = 0.064
    lambda_v0::T = 2.495e6   # J/kg, latent heat of vaporization
    lambda_v1::T = 2380.0
    eeq_max::T = 15.0        # mm/day cap
    tsnow::T = 0.0           # °C rain/snow threshold
    melt_factor::T = 3.0     # mm/°C/day degree-day melt
    # AD-smoothing sharpnesses — each has units 1/[argument], so they are scaled per quantity
    # (deviation from the exact op is ≤ log(2)/β at that quantity's scale).
    βeeq::T = 5.0            # eeq [0,15] clamp (mm/day)
    βsnow::T = 1.0           # rain/snow split around 0 °C
    βmelt::T = 1.0           # snowmelt (mm/day)
    βcond::T = 1.0           # supply/demand conductance cap (mm/s)
    βden::T = 5.0            # conductance denominator guard
    βtransp::T = 5.0         # transpiration min (mm/day)
    βwscal::T = 30.0         # water-stress ratio (dimensionless ∈ [0,~2])
    βevap::T = 20.0          # soil-evap cover soft-max (fraction)
    βw::T = 20.0             # soil-water storage clamp (mm)
    βflux::T = 50.0          # flux non-negativity floors (gC or mm)
end

"""
    RespParams{T}

Autotrophic-respiration constants (Lloyd–Taylor `gtemp`, LPJmL `npp.c`; Sitch et al. 2003). Tissue
maintenance respiration is `respcoeff·k·(C_tissue/CN_tissue)·gtemp(temp)` summed over sapwood and
fine root, using **tissue-specific C:N ratios** (wood is N-poor, `CN_sapwood≈330`; fine root
N-rich, `CN_root≈29`) — a single leaf-like N:C over-respires the large woody pool. `k` is the
maintenance rate per unit tissue N (gC gN⁻¹ day⁻¹). Growth respiration is
`r_growth·(GPP − Rleaf − Rmaint)⁺`. `βgate` smooths the low-T cutoff.
"""
Base.@kwdef struct RespParams{T <: Real}
    e0::T = 308.56           # Lloyd–Taylor activation temp
    temp_response::T = 56.02 # Lloyd–Taylor offset, °C
    k::T = 0.0548            # gC/gN/day maintenance rate constant per unit tissue N
    cn_sapwood::T = 330.0    # sapwood C:N (N-poor wood)
    cn_root::T = 29.0        # fine-root C:N
    respcoeff::T = 1.0
    r_growth::T = 0.25
    βgate::T = 1.0
end

"""
    FDiffParams{T}

Bundle of all F_diff parameter groups plus the shared [`Allometry.TreeAllometry`](@ref). This is the
single object AD differentiates parameters through.
"""
# NOT `Base.@kwdef`: the @kwdef-generated zero-parameter constructor `FDiffParams()` would evaluate
# the field defaults `PhotoParams{T}()` etc. with `T` UNBOUND (JET flags this — the same trap
# documented for `SharedState` in state.jl). Two explicit constructors instead: the parametric
# `FDiffParams{T}(; …)` keeps `T` bound, and the default-eltype `FDiffParams(; …) ≡ FDiffParams{Float64}`.
struct FDiffParams{T <: Real}
    photo::PhotoParams{T}
    tstress::TempStressParams{T}
    water::WaterParams{T}
    resp::RespParams{T}
    allom::Allometry.TreeAllometry{T}
    nlambda::Int             # λ-solve Newton iterations (fixed graph for clean AD)
    ω::T                     # Newton damping (fixed constant → fixed computational graph)
end
function FDiffParams{T}(;
        photo = PhotoParams{T}(),
        tstress = TempStressParams{T}(),
        water = WaterParams{T}(),
        resp = RespParams{T}(),
        allom = Allometry.TreeAllometry{T}(),
        nlambda = 25,
        ω = T(0.9)
    ) where {T <: Real}
    return FDiffParams{T}(photo, tstress, water, resp, allom, nlambda, ω)
end
FDiffParams(; kwargs...) = FDiffParams{Float64}(; kwargs...)

# ─────────────────────────────────────────────────────────────────────────────────────────────
# State, structure (S→F boundary), forcing
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""
    FDiffState{T}

The continuous prognostic state F_diff carries across the daily rollout (the only autoregressive
coupling): `w` = root-zone soil water as a fraction of water-holding capacity `∈ [0,1]`, `snowpack` =
snow water equivalent `mm`. (Discrete vegetation demography is S's, not carried here — ADR 0014.)
"""
Base.@kwdef struct FDiffState{T <: Real}
    w::T = 0.5
    snowpack::T = 0.0
end

"""
    Structure{T}

The S→F structural boundary condition (fixed within the spike rollout): canopy `lai`, foliar
projective cover `fpc`, surface `albedo`, phenology `phen ∈ [0,1]`, soil water-holding capacity
`whc` (mm), and the Beer–Lambert extinction `k_beer`.
"""
Base.@kwdef struct Structure{T <: Real}
    lai::T = 4.0
    fpc::T = 0.8
    albedo::T = 0.15
    phen::T = 1.0
    whc::T = 200.0
    k_beer::T = 0.5
    # PAR-use / light-absorption efficiency `alphaa` (`alphaa_tree.c`; `water_stressed.c:204`
    # `apar = par·(1-albedo_leaf)·alphaa·fpar`). With N off it is the PFT constant (TeBS = 0.55).
    # Default `1.0` keeps the spike baseline (which folded no alphaa into APAR) unchanged.
    alphaa::T = 1.0
end

"""
    DailyForcing{T}

Trivial daily atmospheric forcing for the spike: `swdown` (W/m²), `lwnet` (net longwave W/m², sign
convention: positive downward-available), `temp` (°C), `precip` (mm/day), `daylength` (h), `co2`
(ppm). (Full petpar daylength-from-latitude is a documented scale-up item; here daylength is
supplied to keep the rollout free of the `acos` polar-day/night branches.)
"""
Base.@kwdef struct DailyForcing{T <: Real}
    swdown::T = 200.0
    lwnet::T = -40.0
    temp::T = 15.0
    precip::T = 3.0
    daylength::T = 12.0
    co2::T = 380.0
end

# ─────────────────────────────────────────────────────────────────────────────────────────────
# Temperature stress — temp_stress.c:25-41 (smooth-gated)
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""
    temp_stress(p::TempStressParams, temp, daylength) -> tstress ∈ [0,1]

Photosynthesis temperature-stress scalar (`temp_stress.c`). The low/high logistic pieces are already
smooth; the hard cutoffs (`daylength<0.01`, `temp>tmax`, `temp≥temp_co2_high`) are replaced by
sigmoid gates ([`SmoothOps.sigmoid`](@ref)) so the scalar is differentiable in `temp`. Exact-op
match away from the thresholds; deviation is confined to a `O(1/βgate)`-wide band at each cutoff.
"""
function temp_stress(p::TempStressParams, temp, daylength)
    # shape constants from the PFT CO2/photosynthesis limits (temp_stress.c:38-40)
    k1 = 2 * log(1 / 0.99 - 1) / (p.temp_co2_low - p.temp_photos_low)
    k2 = p.temp_co2_low + 0.5 * p.temp_photos_low
    k3 = log(0.99 / 0.01) / (p.temp_co2_high - p.temp_photos_high)
    low = inv(one(temp) + exp(k1 * (k2 - temp)))
    high = one(temp) - 0.01 * exp(k3 * (temp - p.temp_photos_high))
    ts = low * high
    # smooth gates replacing the hard regime cutoffs
    gate_day = sigmoid(p.βgate * (daylength - 0.01))
    gate_tmax = sigmoid(p.βgate * (p.tmax - temp))
    gate_co2 = sigmoid(p.βgate * (p.temp_co2_high - temp))
    return ts * gate_day * gate_tmax * gate_co2
end

# ─────────────────────────────────────────────────────────────────────────────────────────────
# Photosynthesis kernel — photosynthesis.c:36-166 (Haxeltine & Prentice 1996)
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""
    photosynthesis(p::PhotoParams, λ, tstress, co2_Pa, temp, apar, daylength; comp_vm=true, vm=0) -> (agd, rd, vm, adtmm)

Daily photosynthesis (`photosynthesis.c:36-166`), returning gross daytime assimilation `agd`
(gC/m²/day), leaf respiration `rd` (gC/m²/day), Vcmax `vm`, and the CO₂-flux form `adtmm`
(mm/m²/day) used in the λ residual. `comp_vm=true` computes `vm` at the optimal λ (the C `gp_sum`
pass); `comp_vm=false` uses the passed-in `vm` (the λ-solve residual pass). Non-smooth ops replaced
by [`SmoothOps`](@ref) surrogates: the σ floor (`sqrt_floor`), the C4 `phipi<1` mask (sigmoid), and
the `adt≤0` floor (softplus). The co-limitation discriminant `(je+jc)²−4θ·je·jc ≥ (je−jc)² ≥ 0` is
positive by construction (θ<1), so its sqrt needs only a round-off floor.
"""
# SLA-dependent Vcmax cap (photosynthesis.c:92-97), smoothed for AD. Only binds when `issla` is set
# (LPJmL-FIT individual mode); a soft `min(vm, vm_n)` so the cap is differentiable near the kink.
function _sla_vm_cap(p::PhotoParams, vm, temp)
    p.issla || return vm
    vm_n = 11.205 * p.sla^(-0.383) * 1.0368 * exp(0.069 * (temp - 25))
    return smoothmin(vm, vm_n, p.βvm)
end

function photosynthesis(
        p::PhotoParams{T}, λ, tstress, co2_Pa, temp, apar, daylength;
        comp_vm::Bool = true, vm = zero(T)
    ) where {T}
    θ = p.theta
    # temperature-dependent kinetics (photosynthesis.c:66-70)
    ko = p.ko25 * p.q10ko^((temp - 25) * 0.1)
    kc = p.kc25 * p.q10kc^((temp - 25) * 0.1)
    fac_kin = kc * (one(temp) + p.po2 / ko)
    tau = p.tau25 * p.q10tau^((temp - 25) * 0.1)
    gammastar = p.po2 / (2 * tau)

    if p.path === :c3
        α = p.alphac3
        b = p.bc3
        if comp_vm
            # Vcmax at optimal λ (photosynthesis.c:71-91)
            pi_opt = p.lambdamc3 * co2_Pa
            c1o = tstress * α * (pi_opt - gammastar) / (pi_opt + 2 * gammastar)
            c2o = (pi_opt - gammastar) / (pi_opt + fac_kin)
            s = (24 / daylength) * b
            σ = sqrt_floor(one(temp) - (c2o - s) / (c2o - θ * s), p.εσ)
            vm = _sla_vm_cap(p, (1 / b) * (c1o / c2o) * ((2θ - 1) * s - (2θ * s - c2o) * σ) * apar * p.cmass * p.cq, temp)
        end
        # c1, c2 at the (actual) λ (photosynthesis.c:99-105)
        pi_ = λ * co2_Pa
        c1 = tstress * α * (pi_ - gammastar) / (pi_ + 2 * gammastar)
        c2 = (pi_ - gammastar) / (pi_ + fac_kin)
        je = c1 * apar * p.cmass * p.cq / daylength
        jc = c2 * hour2day(vm)
        b_resp = b
    else  # :c4
        α = p.alphac4
        b = p.bc4
        if comp_vm
            c1o = tstress * α
            c2o = one(temp)
            s = (24 / daylength) * b
            σ = sqrt_floor(one(temp) - (c2o - s) / (c2o - θ * s), p.εσ)
            vm = _sla_vm_cap(p, (1 / b) * (c1o / c2o) * ((2θ - 1) * s - (2θ * s - c2o) * σ) * apar * p.cmass * p.cq, temp)
        end
        # C4 CO2-limitation factor: smooth min(1, λ/λmc4)  (photosynthesis.c:123-125)
        ratio = λ / p.lambdamc4
        gate = sigmoid(-30 * (ratio - 1))
        phipi = gate * ratio + (one(ratio) - gate)
        c1 = tstress * phipi * α
        je = c1 * apar * p.cmass * p.cq / daylength
        jc = hour2day(vm)          # c2 ≡ 1
        b_resp = b
    end

    # co-limitation (photosynthesis.c:150) — discriminant ≥ (je−jc)² ≥ 0
    X = je + jc
    disc = X * X - 4 * θ * je * jc
    agd = (X - sqrt_floor(disc, 1.0e-12)) / (2θ) * daylength
    rd = b_resp * vm
    adt = agd - hour2day(daylength) * rd
    # adt≤0 → 0 (photosynthesis.c:166), smoothed
    adt_pos = softplus(adt, T(0.5))
    adtmm = adt_pos / p.cmass * 8.314 * degCtoK(temp) / p.p_atm * 1000
    return (agd, rd, vm, adtmm)
end

# ─────────────────────────────────────────────────────────────────────────────────────────────
# Priestley–Taylor equilibrium evaporation — petpar.c / NeuralCrop radiation.jl
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""
    priestley_taylor_eeq(p::WaterParams, swdown, lwnet, temp, daylength, albedo) -> eeq

Equilibrium (Priestley–Taylor) evapotranspiration (mm/day):
`eeq = dayseconds·(s/(s+γ)/λ)·(swnet + lwnet·daylength/24)`, with the Magnus slope `s`, psychrometric
`γ(temp)` and latent heat `λ(temp)`. The α_PT (1.32) / ALPHAM (1.391) multipliers are applied
downstream (soil evap / transpirative demand), NOT here. Clamped to `[0, eeq_max]` via
[`SmoothOps.smooth_clamp`](@ref).
"""
function priestley_taylor_eeq(p::WaterParams, swdown, lwnet, temp, daylength, albedo)
    s = p.s_num * exp(p.s_a * temp / (p.s_b + temp)) / (p.s_b + temp)^2
    γ = p.gamma_c0 + p.gamma_c1 * temp
    λv = p.lambda_v0 - p.lambda_v1 * temp
    swnet = (one(albedo) - albedo) * swdown
    eeq = p.dayseconds * (s / (s + γ) / λv) * (swnet + lwnet * (daylength / 24))
    return smooth_clamp(eeq, zero(eeq), p.eeq_max, p.βeeq)
end

# ─────────────────────────────────────────────────────────────────────────────────────────────
# λ (ci:ca) supply/demand solve — water_stressed.c residual g(λ)=fac·(1−λ)−adtmm(λ)  (ADR 0015)
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""
    solve_lambda(p::FDiffParams, fac, tstress, co2_Pa, temp, apar, daylength, vm) -> λ

Solve the ci:ca ratio λ from `g(λ) = fac·(1−λ) − adtmm(λ) = 0` (Eqn 18, Haxeltine & Prentice 1996;
`water_stressed.c:26-48`). The reference differentiates this via the implicit-function-theorem
adjoint (`SteadyStateAdjoint`+`EnzymeVJP`) — never through the bisection iterations. Here, since the
residual is smooth-a.e. and monotone on the bracket `[0.02, 0.85]`, we use a **fixed-iteration damped
Newton with a FIXED computational graph** (no data-dependent branch or convergence-`break`): the
graph is identical for every parameter value, so forward-/reverse-mode AD flows through it cleanly
and — at convergence — the total derivative equals the implicit-function result. `g'(λ)` is obtained
by a central finite difference in λ (pure arithmetic, no nested AD), which only drives the primal
solve; the outer AD gradient w.r.t. parameters is exact at convergence regardless of `g'` accuracy.
See ADR 0014 for the trade-off vs the SteadyStateAdjoint scale-up path.
"""
function solve_lambda(p::FDiffParams{T}, fac, tstress, co2_Pa, temp, apar, daylength, vm) where {T}
    g(λ) = fac * (one(λ) - λ) -
        photosynthesis(p.photo, λ, tstress, co2_Pa, temp, apar, daylength; comp_vm = false, vm = vm)[4]
    h = T(1.0e-6)
    λ = T(0.7)                       # fixed interior initial guess (∈ [0.02, 0.85])
    # The Newton iterate is confined to the physical bracket [0.02, 0.85] by a PLAIN `clamp`. Why not
    # a smooth surrogate: in the degenerate low-light regime (e.g. deep winter with a fixed summer
    # canopy) adtmm is pinned at its softplus floor ⇒ dg≈0 ⇒ the raw Newton step `ω·gλ/dg` diverges;
    # a `smooth_clamp` returns the right PRIMAL but `softplus(β·huge)` overflows to `exp(Inf)` and
    # NaNs the AD dual. A hard `clamp` instead DISCARDS the divergent branch's derivative (min/max
    # keeps only the selected operand's dual), so both ForwardDiff and Enzyme stay finite. In the
    # normal regime λ is interior (≤ λmax = 0.8 < 0.85), so `clamp` is the identity (derivative 1) —
    # the gradient gate and the regression baseline are unchanged. The kink is on an INTERNAL solver
    # iterate in a regime where GPP≈0 and the gradient is physically immaterial (cf. the reference's
    # SteadyStateAdjoint, which likewise does not differentiate through solver internals).
    lo = T(0.02); hi = T(0.85)
    for _ in 1:p.nlambda
        gλ = g(λ)
        dg = (g(λ + h) - g(λ - h)) / (2h)
        λ = clamp(λ - p.ω * gλ / dg, lo, hi)
    end
    return λ
end

# ─────────────────────────────────────────────────────────────────────────────────────────────
# Canopy conductance + transpiration demand/supply — water_stressed.c / gp_sum.c (smooth-gated)
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""
    canopy_conductance(p, eeq, gp_pot, supply) -> (gc, demand)

Actual canopy conductance from the supply/demand regime (`water_stressed.c:180-189`). The hard
`supply≥demand ? gp_pot : water-limited` switch is replaced by a smooth cap: the water-limited
back-solve `gc_w = GM·ALPHAM·supply/((1−wet)·eeq·ALPHAM − supply)` equals `gp_pot` at `supply=demand`
and exceeds it when not water-limited, so `gc = smoothmin(gc_w, gp_pot)` recovers both regimes
continuously. The denominator is kept positive by a softplus guard (so `gc_w → +∞`, not a NaN, when
not water-limited, where `smoothmin` then selects `gp_pot`).
"""
function canopy_conductance(p::WaterParams, eeq, gp_pot, supply)
    demand = eeq > 0 ? (one(eeq) - p.wet) * eeq * p.ALPHAM / (one(eeq) + p.GM * p.ALPHAM / gp_pot) : zero(eeq)
    denom_raw = (one(eeq) - p.wet) * eeq * p.ALPHAM - supply
    denom = softplus(denom_raw, p.βden) + 1.0e-6
    gc_w = p.GM * p.ALPHAM * supply / denom
    gc = smoothmin(gc_w, gp_pot, p.βcond)
    gc = softplus(gc, p.βflux)      # ≥ 0
    return (gc, demand)
end

# ─────────────────────────────────────────────────────────────────────────────────────────────
# Respiration → NPP — Lloyd–Taylor gtemp + maintenance + growth (npp; NeuralCrop respiration.jl)
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""
    autotrophic_respiration(p::RespParams, temp, gpp, rd, c_sapwood, c_root) -> (npp, ra)

Net primary production `NPP = GPP − Ra`, `Ra = Rleaf + Rmaint + Rgrowth`. `Rmaint = respcoeff·k·
(N:C)·gtemp(temp)·(C_sap + C_root)` with the Lloyd–Taylor `gtemp = exp(e0·(1/(Tr+10) − 1/(temp+Tr)))`
(low-T cutoff smoothed by a sigmoid, per NeuralCrop's AD-safe variant); `Rgrowth = r_growth·(GPP −
Rleaf − Rmaint)⁺` (softplus floor). `rd` is the leaf respiration already returned by
[`photosynthesis`](@ref).
"""
function autotrophic_respiration(p::RespParams, temp, gpp, rd, c_sapwood, c_root)
    gate = sigmoid(10 * (temp + 40))                       # smooth of temp ≥ −40 °C
    gtemp = gate * exp(p.e0 * (1 / (p.temp_response + 10) - 1 / (temp + p.temp_response)))
    tissue_n = c_sapwood / p.cn_sapwood + c_root / p.cn_root
    rmaint = p.respcoeff * p.k * gtemp * tissue_n
    rgrowth = p.r_growth * softplus(gpp - rd - rmaint, one(gpp))
    ra = rd + rmaint + rgrowth
    return (gpp - ra, ra)
end

# ─────────────────────────────────────────────────────────────────────────────────────────────
# One pure daily step
# ─────────────────────────────────────────────────────────────────────────────────────────────
# Working (AD) element type — the promotion of every input's element type. Keyed per-struct (each
# is internally uniform), so differentiating w.r.t. ANY single input (a parameter, the initial
# state, structure, or a forcing field) makes only that struct `Dual`-typed and `T` becomes `Dual`,
# while the others stay `Float64`. Returned-state fields that don't depend on the active variable
# (e.g. snow when differentiating co₂) are `convert`ed to `T` so the state stays type-uniform.
_wt(::FDiffParams{T}) where {T} = T
_wt(::FDiffState{T}) where {T} = T
_wt(::Structure{T}) where {T} = T
_wt(::DailyForcing{T}) where {T} = T

"""
    daily_step(p::FDiffParams, st::FDiffState, str::Structure, f::DailyForcing;
               c_sapwood=5000.0, c_root=2000.0) -> (st′, fluxes)

Advance F_diff one day (pure, out-of-place). Chain: Priestley–Taylor `eeq` → rain/snow split + snow
bucket → temperature stress → APAR → Vcmax → potential conductance → supply/demand → λ solve → GPP →
transpiration + soil evaporation → soil-water bucket update (with smooth overflow drainage) →
respiration → NPP. Returns the new [`FDiffState`](@ref) and a `NamedTuple` of daily fluxes
`(gpp, npp, transp, evap, eeq, runoff, λ, wscal)` (gC/m²/day or mm/day). `c_sapwood`/`c_root` are the
S-provided carbon pools used for maintenance respiration.

Water closure holds by construction: `precip = transp + evap + runoff + Δ(soil water + snowpack)`.
"""
# APAR (absorbed PAR energy, J/m²/day). Internal path: `par·(1-albedo)·alphaa·fpar` (Beer–Lambert fpar
# from structure — `water_stressed.c:204`). External path (`fapar` supplied): drive APAR with the C
# binary's ACTUAL daily FAPAR output. Since that output already carries `(1-albedo_leaf)` and, at full
# canopy (`phen≈1`, no snow), `FAPAR_out = fpc·(1-albedo_leaf)` while `fpar = fpc`, the C
# `apar = par·(1-albedo)·alphaa·fpar` collapses to `par·alphaa·FAPAR_out` — so the external path is
# `par·alphaa·fapar` (no second `(1-albedo)`). This is the "same physics" kernel-isolation drive used by
# the C-binary validation (docs/phase3_fdiff_cbinary_validation.md).
_apar(par, str::Structure, ::Nothing, fpar_internal) = par * (one(par) - str.albedo) * str.alphaa * fpar_internal
_apar(par, str::Structure, fapar::Real, fpar_internal) = par * str.alphaa * fapar

function daily_step(
        p::FDiffParams, st::FDiffState, str::Structure, f::DailyForcing;
        c_sapwood = 3000.0, c_root = 800.0, fapar = nothing
    )
    # working (AD) type from the model inputs only — the carbon-pool kwargs are `convert`ed to it so
    # a Float64 default does not silently upcast a Float32 rollout (nor a Dual AD pass).
    T = promote_type(_wt(p), _wt(st), _wt(str), _wt(f))
    c_sapwood = convert(T, c_sapwood)
    c_root = convert(T, c_root)
    w = p.water
    # --- radiation / PET ---
    eeq = priestley_taylor_eeq(w, f.swdown, f.lwnet, f.temp, f.daylength, str.albedo)

    # --- snow: smooth rain/snow split at tsnow, degree-day melt ---
    frac_rain = sigmoid(w.βsnow * (f.temp - w.tsnow))
    rain = frac_rain * f.precip
    snowfall = (one(T) - frac_rain) * f.precip
    melt_potential = w.melt_factor * softplus(f.temp - w.tsnow, w.βmelt)
    melt = smoothmin(melt_potential, st.snowpack + snowfall, w.βmelt)
    snowpack′ = st.snowpack + snowfall - melt
    infil = rain + melt                                   # water reaching the soil, mm/day

    # --- canopy radiation absorption ---
    par = 0.5 * w.dayseconds * f.swdown                   # PAR energy, J/m²/day (half of SW)
    fpar = str.fpc * (one(T) - exp(-str.k_beer * str.lai))
    apar = _apar(par, str, fapar, fpar)                   # internal (fapar=nothing) or C-FAPAR-driven

    # --- temperature stress + photosynthesis machinery ---
    ts = temp_stress(p.tstress, f.temp, f.daylength)
    co2_Pa = ppm2Pa(f.co2)
    # potential (unstressed) photosynthesis at λ_opt → Vcmax and potential conductance
    (_, _, vm, adtmm_opt) = photosynthesis(p.photo, w.lambda_opt, ts, co2_Pa, f.temp, apar, f.daylength; comp_vm = true)
    gp_pot = 1.6 * adtmm_opt / (ppm2bar(f.co2) * (one(T) - w.lambda_opt) * hour2sec(f.daylength)) + w.gmin * str.fpc

    # --- supply / demand → conductance → λ ---
    wr = st.w                                             # root-zone water (fraction of WHC)
    supply = w.emax * wr * str.phen                       # mm/day
    (gc, demand) = canopy_conductance(w, eeq, gp_pot, supply)
    fpar_min = fpar                                       # min-conductance surface (fpar_tree)
    gpd = hour2sec(f.daylength) * (gc * str.fpc - w.gmin * fpar_min)
    gpd = softplus(gpd, w.βflux)
    fac = gpd / 1.6 * ppm2bar(f.co2)
    λ = solve_lambda(p, fac, ts, co2_Pa, f.temp, apar, f.daylength, vm)
    (agd, rd, _, _) = photosynthesis(p.photo, λ, ts, co2_Pa, f.temp, apar, f.daylength; comp_vm = false, vm = vm)
    gpp = softplus(agd, w.βflux)                          # GPP, gC/m²/day (agd≥0)

    # --- ET demand: transpiration = min(supply, demand); soil evaporation (moisture-limited) ---
    transp_demand = smoothmin(supply, demand, w.βtransp)
    wscal = smoothmin(one(T), supply / (demand + T(1.0e-9)), w.βwscal)
    moisture = wr / (wr + T(0.3))                         # smooth soil-moisture evap limitation
    evap_demand = eeq * w.α_PT * smoothmax(one(T) - fpar, T(0.05), w.βevap) * moisture * (one(T) - str.fpc)
    et_demand = transp_demand + evap_demand

    # --- soil-water bucket: ET is supply-capped, runoff is the non-negative overflow drainage ---
    # Closure is EXACT by construction: precip = ET + runoff + Δ(soil water + snowpack). Derivation:
    # available = w₀+infil; ET=min(demand,available); w′=available−ET−over; runoff=over ⇒ the
    # identity collapses to infil+snowfall−melt = rain+snowfall = precip (see docs/phase3_fdiff_spike).
    whc = str.whc
    w0_mm = st.w * whc
    available = w0_mm + infil
    et = smoothmin(et_demand, available, w.βw)            # cannot evaporate more than is available
    after_et = available - et
    over = softplus(after_et - whc, w.βw)                 # overflow above field capacity → drainage
    w_new_mm = after_et - over
    w′ = w_new_mm / whc
    runoff = over                                         # ≥ 0 (physical)
    # split the (possibly supply-limited) actual ET back into its transpiration / evaporation parts
    et_frac = et / (et_demand + T(1.0e-12))
    transp = transp_demand * et_frac
    soil_evap = evap_demand * et_frac

    # --- respiration → NPP ---
    (npp, _) = autotrophic_respiration(p.resp, f.temp, gpp, rd, c_sapwood, c_root)

    st′ = FDiffState{T}(; w = convert(T, w′), snowpack = convert(T, snowpack′))
    fluxes = (
        gpp = convert(T, gpp), npp = convert(T, npp), transp = convert(T, transp),
        evap = convert(T, soil_evap), et = convert(T, et), eeq = convert(T, eeq),
        runoff = convert(T, runoff), lambda = convert(T, λ), wscal = convert(T, wscal),
    )
    return (st′, fluxes)
end

# ─────────────────────────────────────────────────────────────────────────────────────────────
# Annual rollout (365-day fold) — the autoregressive coupling is soil water → water stress
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""
    rollout(p::FDiffParams, st0::FDiffState, str::Structure, forcings; c_sapwood, c_root) -> (st, totals)

Fold [`daily_step`](@ref) over a vector of [`DailyForcing`](@ref) (one per day), carrying soil-water
and snow state. Returns the final state and annual totals `(npp, gpp, transp, evap, runoff, precip)`
(gC/m²/yr or mm/yr). This is the differentiable object the gradient gate exercises.
"""
function rollout(
        p::FDiffParams, st0::FDiffState, str::Structure, forcings;
        c_sapwood = 3000.0, c_root = 800.0, fapars = nothing,
        c_sapwoods = nothing, c_roots = nothing
    )
    T = promote_type(_wt(p), _wt(st0), _wt(str), _wt(first(forcings)))
    st = FDiffState{T}(; w = convert(T, st0.w), snowpack = convert(T, st0.snowpack))
    npp = zero(T); gpp = zero(T); transp = zero(T); evap = zero(T); runoff = zero(T); precip = zero(T)
    for (i, f) in enumerate(forcings)
        fp = fapars === nothing ? nothing : fapars[i]        # per-day C FAPAR (or internal)
        cs = c_sapwoods === nothing ? c_sapwood : c_sapwoods[i]
        cr = c_roots === nothing ? c_root : c_roots[i]
        (st, fl) = daily_step(p, st, str, f; c_sapwood = cs, c_root = cr, fapar = fp)
        npp += fl.npp; gpp += fl.gpp; transp += fl.transp; evap += fl.evap; runoff += fl.runoff
        precip += convert(T, f.precip)
    end
    totals = (npp = npp, gpp = gpp, transp = transp, evap = evap, runoff = runoff, precip = precip)
    return (st, totals)
end

# ─────────────────────────────────────────────────────────────────────────────────────────────
# Daily-trajectory rollout (returns every day's fluxes) — used by the C-binary validation driver
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""
    rollout_daily(p, st0, str, forcings; fapars=nothing, c_sapwoods=nothing, c_roots=nothing,
                  c_sapwood=3000.0, c_root=800.0) -> (st, days)

Like [`rollout`](@ref) but returns the full per-day flux trajectory `days` (a `Vector` of the
`daily_step` flux `NamedTuple`s) instead of only annual totals. `fapars` / `c_sapwoods` / `c_roots`
are optional per-day vectors (the C binary's actual daily FAPAR and carbon pools) that override the
internal Beer–Lambert FAPAR and the scalar pool defaults — this is what drives the "same physics"
daily comparison against the LPJmL-FIT C outputs.
"""
function rollout_daily(
        p::FDiffParams, st0::FDiffState, str::Structure, forcings;
        c_sapwood = 3000.0, c_root = 800.0, fapars = nothing,
        c_sapwoods = nothing, c_roots = nothing
    )
    T = promote_type(_wt(p), _wt(st0), _wt(str), _wt(first(forcings)))
    st = FDiffState{T}(; w = convert(T, st0.w), snowpack = convert(T, st0.snowpack))
    days = Vector{typeof(daily_step(p, st, str, first(forcings); c_sapwood = c_sapwood, c_root = c_root)[2])}()
    sizehint!(days, length(forcings))
    for (i, f) in enumerate(forcings)
        fp = fapars === nothing ? nothing : fapars[i]
        cs = c_sapwoods === nothing ? c_sapwood : c_sapwoods[i]
        cr = c_roots === nothing ? c_root : c_roots[i]
        (st, fl) = daily_step(p, st, str, f; c_sapwood = cs, c_root = cr, fapar = fp)
        push!(days, fl)
    end
    return (st, days)
end

"""
    annual_npp(p::FDiffParams, st0, str, forcings; kwargs...) -> Real

Convenience scalar: the annual NPP (gC/m²/yr) produced by [`rollout`](@ref). This is the simple
output whose gradient w.r.t. an input/parameter the spike verifies against finite differences.
"""
annual_npp(p, st0, str, forcings; kwargs...) = rollout(p, st0, str, forcings; kwargs...)[2].npp

# ═════════════════════════════════════════════════════════════════════════════════════════════
# MULTI-LAYER SOIL WATER (scale-up step 2 — docs/phase3_fdiff_cbinary_validation.md §7)
# ═════════════════════════════════════════════════════════════════════════════════════════════
# Replaces the single bucket with LPJmL-FIT's N-layer soil column so that (a) the shallow layers dry
# preferentially under concentrated root uptake + top-30 cm soil evaporation, collapsing the
# root-weighted moisture `wr` in summer and correctly SUPPLY-LIMITING transpiration (the single bucket
# blends wet deep water with dry shallow water and stays demand-limited → the measured +40 % transp
# bias), and (b) the per-layer soil water can be compared to the C binary's `d_swc`/`d_rootmoist`.
#
# Faithful DAILY approximation (v1): each layer tracks PLANT-AVAILABLE water `w[l] ∈ [0, whcs[l]]` mm
# (between wilting point and field capacity). Percolation in LPJmL only moves water ABOVE field
# capacity (`percthres=1.0`) and drains it fast, so at daily resolution a fill-to-field-capacity
# infiltration CASCADE (excess flows to the next layer; bottom excess → drainage; saturation-excess at
# the top → surface runoff) is the daily limit of that free-water percolation. Root uptake is the
# Jackson-1996 β root distribution; soil evaporation is drawn from the top `soildepth_evap` with the
# LPJmL quadratic moisture limiter. Documented v1 simplifications (NOT bit-exact to the C):
# the Saxton–Rawls pedotransfer Ks/β exponential percolation timescale + explicit free-water (`w_fw`)
# store, permafrost ice blocking percolation, litter evaporation, and the energy-balance snow melt.
# `whcs`/`rootdist` come from the C run's own `whc_nat` output + the D95 β profile (dependency-free).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""
    SoilColumn{T}

Fixed per-layer soil boundary for the multi-layer core: `whcs` = per-layer plant-available capacity
(field capacity − wilting point, mm), `rootdist` = per-layer root fraction (Jackson-1996 β profile,
sums ≈ 1), `frac_evap` = fraction of each layer within the top `soildepth_evap` (soil-evaporation
weights), and `soil_infil` = the LPJmL infiltration exponent (surface runoff `∝ 1−(1−S₀)^{1/soil_infil}`).
Build the Hainich column with [`hainich_soilcolumn`](@ref).
"""
struct SoilColumn{T <: Real}
    whcs::Vector{T}
    rootdist::Vector{T}
    frac_evap::Vector{T}
    soil_infil::T
end

"""
    FDiffStateML{T}

Multi-layer prognostic state: per-layer plant-available soil water `w[l]` (mm, `0 ≤ w[l] ≤ whcs[l]`)
and snow water equivalent `snowpack` (mm). The multi-layer analogue of [`FDiffState`](@ref).
"""
struct FDiffStateML{T <: Real}
    w::Vector{T}
    snowpack::T
end

_wt(::SoilColumn{T}) where {T} = T
_wt(::FDiffStateML{T}) where {T} = T

# ── infiltration: fill-to-field-capacity cascade; excess past the bottom → drainage ──────────────
# Because F_diff tracks only PLANT-AVAILABLE water (capped at field capacity), each layer fills toward
# `whcs[l]` and the excess percolates to the next layer (the daily limit of LPJmL's fast free-water
# percolation, `percthres=1.0`); whatever passes the bottom layer is drainage. There is no FC-blocking
# of infiltration (a v1 that blocked at FC bounced rain off a full top layer into spurious surface
# runoff → over-drained the root zone). Surface/infiltration-excess runoff is a documented v2 item
# (needs the free-water saturation range); here total `runoff` ≡ bottom drainage. Closure is EXACT:
# `infil = Σ(fills) + drainage`. `smoothmin` for the fill; overflow is the residual `influx − fill`.
function _infiltrate(w::AbstractVector{T}, whcs, infil, βw) where {T}
    N = length(w)
    wnew = similar(w)
    influx = infil
    for l in 1:N
        space = whcs[l] - w[l]
        fill = smoothmin(influx, space, βw)
        wnew[l] = w[l] + fill
        influx = influx - fill
    end
    drainage = influx                                    # leftover past the bottom layer
    return (wnew, drainage)
end

# ── root-weighted transpiration withdrawal (per layer ∝ rootdist·relative-moisture, capped) ──────
function _transpire(w::AbstractVector{T}, whcs, rootdist, emax, phen, demand, βw) where {T}
    N = length(w)
    rel = w ./ whcs                                      # relative moisture per layer
    wr = zero(T)
    for l in 1:N
        wr += rootdist[l] * rel[l]
    end
    supply = emax * wr * phen
    transp_tot = smoothmin(supply, demand, βw)
    wscal = smoothmin(one(T), supply / (demand + T(1.0e-9)), T(30.0))
    wnew = similar(w)
    actual = zero(T)
    invwr = inv(wr + T(1.0e-12))
    for l in 1:N
        want = transp_tot * (rootdist[l] * rel[l]) * invwr     # share ∝ root-weighted moisture
        take = smoothmin(want, w[l], βw)                        # cannot exceed layer water
        wnew[l] = w[l] - take
        actual += take
    end
    return (wnew, actual, wr, wscal)
end

# ── bare-soil evaporation from the top `soildepth_evap` (quadratic moisture limiter; waterbalance.c) ─
function _soil_evap(w::AbstractVector{T}, whcs, frac_evap, eeq, α_PT, cover, βevap, βw) where {T}
    N = length(w)
    w_evap = zero(T); whcs_evap = zero(T)
    for l in 1:N
        w_evap += frac_evap[l] * w[l]
        whcs_evap += frac_evap[l] * whcs[l]
    end
    moisture = (w_evap / (whcs_evap + T(1.0e-9)))^2                 # quadratic (w_evap/whcs_evap)²
    evap_energy = eeq * α_PT * smoothmax(one(T) - cover, T(0.05), βevap)
    evap_dem = evap_energy * moisture
    evap = smoothmin(evap_dem, w_evap, βw)                          # supply-capped
    wnew = similar(w)
    frac = evap / (w_evap + T(1.0e-12))
    for l in 1:N
        wnew[l] = w[l] - frac * frac_evap[l] * w[l]                 # withdraw ∝ frac_evap·w
    end
    return (wnew, evap)
end

"""
    daily_step_ml(p, st::FDiffStateML, str::Structure, soil::SoilColumn, f::DailyForcing;
                  c_sapwood, c_root, fapar=nothing) -> (st′, fluxes)

One multi-layer day. Same canopy/photosynthesis/λ path as [`daily_step`](@ref), but the soil water is
the [`SoilColumn`](@ref): infiltration cascade → root-weighted transpiration (per-layer withdrawal) →
top-layer soil evaporation. Returns the new [`FDiffStateML`](@ref) and daily fluxes
`(gpp, npp, transp, evap, eeq, runoff, rootmoist, lambda, wscal)` (rootmoist = top-1 m available mm).
Water closes exactly: `precip = transp + evap + runoff + Δ(Σw + snowpack)`.
"""
function daily_step_ml(
        p::FDiffParams, st::FDiffStateML, str::Structure, soil::SoilColumn, f::DailyForcing;
        c_sapwood = 3000.0, c_root = 800.0, fapar = nothing, n_top1m::Int = 3
    )
    T = promote_type(_wt(p), _wt(st), _wt(str), _wt(soil), _wt(f))
    c_sapwood = convert(T, c_sapwood); c_root = convert(T, c_root)
    w = p.water
    eeq = priestley_taylor_eeq(w, f.swdown, f.lwnet, f.temp, f.daylength, str.albedo)

    # snow (degree-day; v1) + water reaching the soil
    frac_rain = sigmoid(w.βsnow * (f.temp - w.tsnow))
    rain = frac_rain * f.precip
    snowfall = (one(T) - frac_rain) * f.precip
    melt_potential = w.melt_factor * softplus(f.temp - w.tsnow, w.βmelt)
    melt = smoothmin(melt_potential, st.snowpack + snowfall, w.βmelt)
    snowpack′ = st.snowpack + snowfall - melt
    infil = rain + melt

    # canopy light + photosynthesis machinery (identical to daily_step)
    par = 0.5 * w.dayseconds * f.swdown
    fpar = str.fpc * (one(T) - exp(-str.k_beer * str.lai))
    apar = _apar(par, str, fapar, fpar)
    ts = temp_stress(p.tstress, f.temp, f.daylength)
    co2_Pa = ppm2Pa(f.co2)
    (_, _, vm, adtmm_opt) = photosynthesis(p.photo, w.lambda_opt, ts, co2_Pa, f.temp, apar, f.daylength; comp_vm = true)
    gp_pot = 1.6 * adtmm_opt / (ppm2bar(f.co2) * (one(T) - w.lambda_opt) * hour2sec(f.daylength)) + w.gmin * str.fpc

    # 1) infiltration cascade
    (w1, drainage) = _infiltrate(convert.(T, st.w), convert.(T, soil.whcs), infil, w.βw)

    # 2) supply/demand → conductance → λ → GPP  (root-weighted supply from the layers)
    N = length(w1)
    rel1 = w1 ./ convert.(T, soil.whcs)
    wr = zero(T)
    for l in 1:N
        wr += convert(T, soil.rootdist[l]) * rel1[l]
    end
    supply = w.emax * wr * str.phen
    (gc, demand) = canopy_conductance(w, eeq, gp_pot, supply)
    gpd = hour2sec(f.daylength) * (gc * str.fpc - w.gmin * fpar)
    gpd = softplus(gpd, w.βflux)
    fac = gpd / 1.6 * ppm2bar(f.co2)
    λ = solve_lambda(p, fac, ts, co2_Pa, f.temp, apar, f.daylength, vm)
    (agd, rd, _, _) = photosynthesis(p.photo, λ, ts, co2_Pa, f.temp, apar, f.daylength; comp_vm = false, vm = vm)
    gpp = softplus(agd, w.βflux)

    # 3) transpiration (per-layer withdrawal) then 4) soil evaporation (top layers)
    (w2, transp, _, wscal) = _transpire(w1, convert.(T, soil.whcs), convert.(T, soil.rootdist), w.emax, str.phen, demand, w.βw)
    cover = str.fpc * str.phen
    (w3, soil_evap) = _soil_evap(w2, convert.(T, soil.whcs), convert.(T, soil.frac_evap), eeq, w.α_PT, cover, w.βevap, w.βw)

    (npp, _) = autotrophic_respiration(p.resp, f.temp, gpp, rd, c_sapwood, c_root)

    runoff = drainage                                     # v1: bottom drainage (surface runoff = v2)
    rootmoist = zero(T)                                    # top-1 m plant-available water (mm)
    for l in 1:min(n_top1m, N)
        rootmoist += w3[l]
    end
    st′ = FDiffStateML{T}(w3, convert(T, snowpack′))
    fluxes = (
        gpp = convert(T, gpp), npp = convert(T, npp), transp = convert(T, transp),
        evap = convert(T, soil_evap), eeq = convert(T, eeq), runoff = convert(T, runoff),
        rootmoist = convert(T, rootmoist), lambda = convert(T, λ), wscal = convert(T, wscal),
    )
    return (st′, fluxes)
end

"""
    rollout_daily_ml(p, st0::FDiffStateML, str, soil, forcings; fapars=nothing, kwargs...) -> (st, days)

Fold [`daily_step_ml`](@ref) over a vector of [`DailyForcing`](@ref), carrying the per-layer soil water
and snow. Returns the final state and the per-day flux `NamedTuple`s. `fapars`/`c_sapwoods`/`c_roots`
are optional per-day override vectors (as in [`rollout_daily`](@ref)).
"""
function rollout_daily_ml(
        p::FDiffParams, st0::FDiffStateML, str::Structure, soil::SoilColumn, forcings;
        c_sapwood = 3000.0, c_root = 800.0, fapars = nothing, c_sapwoods = nothing, c_roots = nothing,
        n_top1m::Int = 3
    )
    T = promote_type(_wt(p), _wt(st0), _wt(str), _wt(soil), _wt(first(forcings)))
    st = FDiffStateML{T}(convert.(T, st0.w), convert(T, st0.snowpack))
    days = Vector{typeof(daily_step_ml(p, st, str, soil, first(forcings); c_sapwood = c_sapwood, c_root = c_root, n_top1m = n_top1m)[2])}()
    sizehint!(days, length(forcings))
    for (i, f) in enumerate(forcings)
        fp = fapars === nothing ? nothing : fapars[i]
        cs = c_sapwoods === nothing ? c_sapwood : c_sapwoods[i]
        cr = c_roots === nothing ? c_root : c_roots[i]
        (st, fl) = daily_step_ml(p, st, str, soil, f; c_sapwood = cs, c_root = cr, fapar = fp, n_top1m = n_top1m)
        push!(days, fl)
    end
    return (st, days)
end

"""
    hainich_soilcolumn(::Type{T}=Float64; whcs, rootdist, soildepth_evap=300.0, soil_infil=2.0) -> SoilColumn{T}

Build a [`SoilColumn`](@ref) from per-layer plant-available capacities `whcs` (mm) and root fractions
`rootdist`, computing the soil-evaporation layer weights `frac_evap` from `soildepth_evap` (mm) and the
per-layer thicknesses `soildepth` (mm). Used by the C-binary multi-layer validation (the Hainich column
is committed in `test/testitems/references/hainich_soilcolumn.txt`).
"""
function hainich_soilcolumn(
        ::Type{T} = Float64; whcs, rootdist, soildepth, soildepth_evap = 300.0, soil_infil = 2.0
    ) where {T <: Real}
    N = length(whcs)
    frac_evap = zeros(T, N)
    remaining = T(soildepth_evap)
    for l in 1:N
        d = T(soildepth[l])
        take = min(d, max(remaining, zero(T)))
        frac_evap[l] = d > 0 ? take / d : zero(T)         # fraction of layer l within the top soildepth_evap
        remaining -= take
    end
    return SoilColumn{T}(T.(whcs), T.(rootdist), frac_evap, T(soil_infil))
end

# ─────────────────────────────────────────────────────────────────────────────────────────────
# LPJmL-FIT temperate-broadleaf-summergreen (TeBS, PFT id 3 — beech) parameter set. The kernel
# constants (θ, α_c3, ALPHAM, GM, α_PT, resp k, e0, …) already match the C source; this switches on
# the PFT-specific values the confound analysis flagged (`par/pft_lpjmlfit.js` PFT 3): photosynthesis
# T-optimum (temp_photos 20/30), max transpiration `emax=10`, min conductance `gmin=1.0`, the SLA
# Vcmax cap (`issla=true`), woody respcoeff 1.2, fine-root C:N 30. Used by the C-binary validation.
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""
    tebs_params(::Type{T}=Float64; nlambda=25, ω=0.9) -> FDiffParams{T}

F_diff parameters for the LPJmL-FIT temperate broadleaved summergreen tree PFT (beech, PFT id 3) —
the Hainich prototype's dominant PFT. See [`tebs_structure`](@ref) for the matching S→F boundary.
"""
function tebs_params(::Type{T} = Float64; nlambda::Int = 25, ω = T(0.9)) where {T <: Real}
    return FDiffParams{T}(;
        photo = PhotoParams{T}(; path = :c3, issla = true, sla = T(0.01986)),
        tstress = TempStressParams{T}(; temp_photos_low = T(20.0), temp_photos_high = T(30.0)),
        water = WaterParams{T}(; emax = T(10.0), gmin = T(1.0)),
        resp = RespParams{T}(; respcoeff = T(1.2), cn_root = T(30.0)),
        nlambda = nlambda, ω = T(ω),
    )
end

"""
    tebs_structure(::Type{T}=Float64; lai=5.7, fpc=0.56, whc=230.0, phen=1.0) -> Structure{T}

S→F structural boundary for the beech (TeBS) PFT: leaf albedo `0.15`, broadleaf Beer–Lambert
`k_beer=0.59`, PAR-use `alphaa=0.55`. `lai`/`fpc`/`whc`/`phen` are the cell/day-specific canopy state
(defaults are the Hainich 2010 growing-season aggregate).
"""
function tebs_structure(
        ::Type{T} = Float64; lai = T(5.7), fpc = T(0.56), whc = T(230.0), phen = T(1.0)
    ) where {T <: Real}
    return Structure{T}(;
        lai = T(lai), fpc = T(fpc), albedo = T(0.15), phen = T(phen),
        whc = T(whc), k_beer = T(0.59), alphaa = T(0.55),
    )
end

# ═════════════════════════════════════════════════════════════════════════════════════════════
# MULTI-INDIVIDUAL / MULTI-PFT CANOPY (scale-up step 3 — docs/phase3_fdiff_cbinary_validation.md §7)
# ═════════════════════════════════════════════════════════════════════════════════════════════
# Replaces the single representative tree with the cell's REAL set of individuals (per patch: a
# size/PFT distribution of trees + grass, reconstructed from the `ind` output — see
# scripts/extract_fdiff_individuals.py), sharing ONE multi-layer soil column. This closes the two
# level gaps the single-individual validation measured (GPP −42 %, transp +45 %) because LPJmL-FIT
# computes BOTH per individual, then sums to the stand:
#
#  • GPP light is the FIT vertical layered Beer–Lambert competition (`getfpar.c`): the tall dominant
#    trees absorb PAR first, the suppressed ones get the transmitted light. Each individual's
#    photosynthesis sees `apar_i = par·(1−albedo_i)·alphaa_i·fpar_i·phen` (`water_stressed.c:204`),
#    where `fpar_i` is its LAYERED absorbed fraction (Σ_i fpar_i = canopy-absorbed PAR). Distributing
#    the light across individuals means the SLA-Vcmax cap no longer saturates one over-lit tree, and
#    the canopy total absorbs the true layered fraction (≈0.83 leafon) rather than the fpc/albedo
#    `d_fapar` OUTPUT (≈0.49) the single-individual drive mistakenly used — recovering GPP.
#  • Transpiration demand is STAND-level (`gp_sum.c` returns the fpc-normalized MEAN potential
#    conductance `gp_stand = Σ_i gp_i·phen / Σ_i fpc_i`, with each `gp_i` from FPC-based light), and
#    each individual transpires `min(supply_i, demand_stand)·fpc_i` (`water_stressed.c:153` after the
#    per-layer sum cancels the `/wr·Σ(rootdist·trf)=wr`). Summing over individuals gives
#    `min(supply, demand_stand)·Σfpc` — the fpc-weighting + mean-conductance normalization the single
#    individual (which used its full-light `gp_pot` and no `·fpc`) got wrong, over-transpiring.
#
# The soil column is shared: total per-layer withdrawal is capped at the layer's available water
# (`water_stressed.c:269`; combined-then-capped, the ordering effect is negligible — verified). This
# is the same-physics port; the light distribution + the stand aggregation are the only changes from
# `daily_step_ml`. AD: ForwardDiff flows through the per-individual loop (fixed graph). Documented v1
# simplifications: fixed (year-end) canopy structure with a daily phenology factor, sub-5 m saplings
# absent from `ind`, per-individual root distribution approximated by the shared cell profile, and
# interception/wet-canopy omitted (as in `daily_step_ml`).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""
    Individual{T}

One canopy individual (a tree or grass cohort in a patch) for the multi-PFT core. `fpar` = its LAYERED
absorbed-PAR fraction (patch basis, phen = 1; from the FIT `getfpar.c` layered-light port), `fpc` = its
foliar projective cover, `alphaa`/`albedo_leaf`/`emax` the PFT constants, `c_sapwood`/`c_root` the
maintenance-respiration pools, and `photo`/`tstress` the per-PFT [`PhotoParams`](@ref) /
[`TempStressParams`](@ref) (the SLA-Vcmax cap uses this individual's `sla`). `is_grass` skips woody
respiration. Build the Hainich set from `test/testitems/references/hainich_individuals_2010.csv`.
"""
struct Individual{T <: Real}
    fpar::T                       # layered absorbed-PAR fraction (leafon, patch basis)
    fpc::T                        # foliar projective cover (patch basis)
    alphaa::T
    albedo_leaf::T
    emax::T
    c_sapwood::T
    c_root::T
    photo::PhotoParams{T}
    tstress::TempStressParams{T}
    is_grass::Bool
end
_wt(::Individual{T}) where {T} = T

# ── withdraw a given TOTAL transpiration demand from the shared column, per-layer capped ──────────
# The per-individual demand/supply limiting is already applied (transp_tot); here the shared soil caps
# the combined withdrawal at each layer's available water (water_stressed.c:269). Withdrawal per layer
# ∝ rootdist·relative-moisture (the C's `aet·rootdist·trf`), consistent with [`_transpire`](@ref).
function _transpire_total(w::AbstractVector{T}, whcs, rootdist, wr, transp_tot, βw) where {T}
    N = length(w)
    rel = w ./ whcs
    wnew = similar(w)
    actual = zero(T)
    invwr = inv(wr + T(1.0e-12))
    for l in 1:N
        want = transp_tot * (rootdist[l] * rel[l]) * invwr
        take = smoothmin(want, w[l], βw)
        wnew[l] = w[l] - take
        actual += take
    end
    return (wnew, actual)
end

"""
    daily_step_canopy(p, inds, soil, st, f; phen=1.0, n_top1m=3) -> (st′, fluxes)

Advance a multi-individual patch canopy one day. `inds` is the patch's [`Individual`](@ref) set, `soil`
the shared [`SoilColumn`](@ref), `st` the [`FDiffStateML`](@ref) soil state, `f` the [`DailyForcing`](@ref),
`phen ∈ [0,1]` the daily phenology factor (scales leaf display). Chain: shared PET/snow/infiltration →
per-individual FPC-light potential conductance → stand mean `gp_stand` → per-individual layered-light
photosynthesis (water-limited via `gp_stand`) + λ solve → sum GPP; per-individual
`min(supply, demand_stand)·fpc` transpiration → shared-soil withdrawal (per-layer capped) → soil
evaporation → per-individual respiration. Returns the new state and stand daily fluxes
`(gpp, npp, transp, evap, eeq, runoff, rootmoist, fapar, fpc)` (per m² of patch). Water closes exactly.
"""
function daily_step_canopy(
        p::FDiffParams, inds::AbstractVector{<:Individual}, soil::SoilColumn, st::FDiffStateML,
        f::DailyForcing; phen = 1.0, n_top1m::Int = 3
    )
    T = promote_type(_wt(p), _wt(st), _wt(soil), _wt(f), isempty(inds) ? Float64 : _wt(first(inds)))
    ph = convert(T, phen)
    w = p.water
    albedo = T(0.15)
    eeq = priestley_taylor_eeq(w, f.swdown, f.lwnet, f.temp, f.daylength, albedo)

    # shared snow + infiltration into the column
    frac_rain = sigmoid(w.βsnow * (f.temp - w.tsnow))
    rain = frac_rain * f.precip
    snowfall = (one(T) - frac_rain) * f.precip
    melt_potential = w.melt_factor * softplus(f.temp - w.tsnow, w.βmelt)
    melt = smoothmin(melt_potential, st.snowpack + snowfall, w.βmelt)
    snowpack′ = st.snowpack + snowfall - melt
    infil = rain + melt
    (w1, drainage) = _infiltrate(convert.(T, st.w), convert.(T, soil.whcs), infil, w.βw)

    # shared root-weighted relative soil moisture (cell rootdist for all individuals, v1)
    N = length(w1)
    rel1 = w1 ./ convert.(T, soil.whcs)
    wr = zero(T)
    for l in 1:N
        wr += convert(T, soil.rootdist[l]) * rel1[l]
    end

    par = 0.5 * w.dayseconds * f.swdown
    co2_Pa = ppm2Pa(f.co2)
    dl = f.daylength
    condfac = ppm2bar(f.co2) * (one(T) - w.lambda_opt) * hour2sec(dl)

    # ── pass 1: gp_sum — per-individual potential conductance (FPC-based light, λ_opt) → stand mean ──
    gp_stand_acc = zero(T)
    fpc_tot = zero(T)
    for ind in inds
        fpc_i = convert(T, ind.fpc) * ph
        apar_gp = par * (one(T) - convert(T, ind.albedo_leaf)) * convert(T, ind.alphaa) * fpc_i
        tsi = temp_stress(ind.tstress, f.temp, dl)
        (_, _, _, adtmm_gp) = photosynthesis(ind.photo, w.lambda_opt, tsi, co2_Pa, f.temp, apar_gp, dl; comp_vm = true)
        gp_i = 1.6 * adtmm_gp / condfac + w.gmin * fpc_i
        gp_stand_acc += gp_i
        fpc_tot += fpc_i
    end
    gp_stand = fpc_tot > T(1.0e-20) ? gp_stand_acc / fpc_tot : zero(T)

    # ── pass 2: per-individual layered-light photosynthesis (water-limited by gp_stand) + transp ──
    gpp_tot = zero(T); npp_tot = zero(T); transp_demand_tot = zero(T); fapar_tot = zero(T)
    for ind in inds
        fpc_i = convert(T, ind.fpc) * ph
        fpar_i = convert(T, ind.fpar) * ph                 # layered absorbed fraction (phen-scaled)
        apar = par * (one(T) - convert(T, ind.albedo_leaf)) * convert(T, ind.alphaa) * fpar_i
        tsi = temp_stress(ind.tstress, f.temp, dl)
        (_, _, vm, _) = photosynthesis(ind.photo, w.lambda_opt, tsi, co2_Pa, f.temp, apar, dl; comp_vm = true)
        supply_i = convert(T, ind.emax) * wr * ph
        (gc, demand) = canopy_conductance(w, eeq, gp_stand, supply_i)   # demand uses the STAND mean gp
        gpd = hour2sec(dl) * (gc * fpc_i - w.gmin * fpar_i)
        gpd = softplus(gpd, w.βflux)
        fac = gpd / 1.6 * ppm2bar(f.co2)
        p_i = FDiffParams{T}(;
            photo = ind.photo, tstress = ind.tstress, water = w, resp = p.resp,
            allom = p.allom, nlambda = p.nlambda, ω = p.ω,
        )
        λ = solve_lambda(p_i, fac, tsi, co2_Pa, f.temp, apar, dl, vm)
        (agd, rd, _, _) = photosynthesis(ind.photo, λ, tsi, co2_Pa, f.temp, apar, dl; comp_vm = false, vm = vm)
        gpp_i = softplus(agd, w.βflux)
        gpp_tot += gpp_i
        fapar_tot += fpar_i
        # transpiration: min(supply, demand_stand)·fpc (water_stressed.c:153 after the per-layer sum)
        transp_demand_tot += smoothmin(supply_i, demand, w.βtransp) * fpc_i
        c_sap = ind.is_grass ? zero(T) : convert(T, ind.c_sapwood)
        (npp_i, _) = autotrophic_respiration(p.resp, f.temp, gpp_i, rd, c_sap, convert(T, ind.c_root))
        npp_tot += npp_i
    end

    # ── shared soil: withdraw the total transpiration demand (per-layer capped), then soil evap ──
    (w2, transp) = _transpire_total(w1, convert.(T, soil.whcs), convert.(T, soil.rootdist), wr, transp_demand_tot, w.βw)
    cover = smoothmin(fpc_tot, one(T), w.βevap)            # total canopy cover (≤ 1)
    (w3, soil_evap) = _soil_evap(w2, convert.(T, soil.whcs), convert.(T, soil.frac_evap), eeq, w.α_PT, cover, w.βevap, w.βw)

    runoff = drainage
    rootmoist = zero(T)
    for l in 1:min(n_top1m, N)
        rootmoist += w3[l]
    end
    st′ = FDiffStateML{T}(w3, convert(T, snowpack′))
    fluxes = (
        gpp = convert(T, gpp_tot), npp = convert(T, npp_tot), transp = convert(T, transp),
        evap = convert(T, soil_evap), eeq = convert(T, eeq), runoff = convert(T, runoff),
        rootmoist = convert(T, rootmoist), fapar = convert(T, fapar_tot), fpc = convert(T, fpc_tot),
    )
    return (st′, fluxes)
end

"""
    rollout_daily_canopy(p, st0, inds, soil, forcings; phens=nothing, n_top1m=3) -> (st, days)

Fold [`daily_step_canopy`](@ref) over a vector of [`DailyForcing`](@ref) for ONE patch canopy `inds`,
carrying the shared per-layer soil water and snow. `phens` is an optional per-day phenology vector
(defaults to 1.0). Returns the final [`FDiffStateML`](@ref) and the per-day stand flux `NamedTuple`s.
"""
function rollout_daily_canopy(
        p::FDiffParams, st0::FDiffStateML, inds::AbstractVector{<:Individual}, soil::SoilColumn,
        forcings; phens = nothing, n_top1m::Int = 3
    )
    T = promote_type(_wt(p), _wt(st0), _wt(soil), _wt(first(forcings)), isempty(inds) ? Float64 : _wt(first(inds)))
    st = FDiffStateML{T}(convert.(T, st0.w), convert(T, st0.snowpack))
    ph1 = phens === nothing ? 1.0 : phens[1]
    days = Vector{typeof(daily_step_canopy(p, inds, soil, st, first(forcings); phen = ph1, n_top1m = n_top1m)[2])}()
    sizehint!(days, length(forcings))
    for (i, f) in enumerate(forcings)
        ph = phens === nothing ? 1.0 : phens[i]
        (st, fl) = daily_step_canopy(p, inds, soil, st, f; phen = ph, n_top1m = n_top1m)
        push!(days, fl)
    end
    return (st, days)
end

end # module FDiff
