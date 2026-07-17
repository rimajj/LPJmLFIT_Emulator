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
    Individual, daily_step_canopy, rollout_daily_canopy,
    PhenParams, PhenState, phenology_gsi_step, tebs_phenparams, petpar_daylength, patch_albedo,
    AllocParams, TreePools, tebs_allocparams, grow_individual, individual_from_pools, rollout_canopy_years,
    agb_ind, vegc_ind

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
    # AD-smoothing sharpness for the C's hard `(adt≤0)?0` net-daytime-assimilation floor
    # (`photosynthesis.c:166`) that converts to the mm-units `adtmm` driving canopy conductance. This
    # ONLY affects `adtmm` (the 4th return / the λ-solve residual + `gp_sum` potential conductance),
    # NOT `agd` (GPP). It MUST be sharp: a soft floor `log(2)/βadt` is injected as spurious net
    # assimilation into every LIGHT-STARVED individual (`adt ≈ 0`), and because `gp_i ∝ adtmm` while its
    # fpc is tiny, the understory's `gp_i/fpc` explodes and inflates the fpc-normalized stand
    # conductance `gp_stand = Σgp_i/Σfpc_i` (the earlier `β=0.5` floor of 1.386 gC lifted `gp_stand`
    # ~8× → transpiration demand ~+30 %). `βadt=20` keeps the floor ≤ 0.035 gC (≈0.07 mm adtmm);
    # the dominant individuals have `adt ≫ floor` so their conductance and the GPP baseline are
    # unchanged.
    βadt::T = 20.0
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
    # adt≤0 → 0 (photosynthesis.c:166), smoothed with a SHARP floor (see PhotoParams.βadt): a coarse
    # floor injects spurious net assimilation into light-starved individuals and inflates gp_stand.
    adt_pos = softplus(adt, p.βadt)
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
    canopy_conductance(p, eeq, gp_pot, supply; wet = p.wet) -> (gc, demand)

Actual canopy conductance from the supply/demand regime (`water_stressed.c:180-189`). `wet` is the
wet-canopy fraction (`interception.c`) that reduces atmospheric demand by `(1 − wet)`; the single-
individual paths default to `p.wet` (0), the multi-individual canopy passes each individual's wet. The
hard
`supply≥demand ? gp_pot : water-limited` switch is replaced by a smooth cap: the water-limited
back-solve `gc_w = GM·ALPHAM·supply/((1−wet)·eeq·ALPHAM − supply)` equals `gp_pot` at `supply=demand`
and exceeds it when not water-limited, so `gc = smoothmin(gc_w, gp_pot)` recovers both regimes
continuously. The denominator is kept positive by a softplus guard (so `gc_w → +∞`, not a NaN, when
not water-limited, where `smoothmin` then selects `gp_pot`).
"""
function canopy_conductance(p::WaterParams, eeq, gp_pot, supply; wet = p.wet)
    demand = eeq > 0 ? (one(eeq) - wet) * eeq * p.ALPHAM / (one(eeq) + p.GM * p.ALPHAM / gp_pot) : zero(eeq)
    denom_raw = (one(eeq) - wet) * eeq * p.ALPHAM - supply
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
# SELF-COMPUTED RADIATION + PHENOLOGY (scale-up step 5 — docs/phase3_fdiff_cbinary_validation.md §11)
# Removes the two C-output "crutches" the canopy validation had leaned on:
#   • `phen` was driven by the C binary's daily FAPAR (`phens = fapar_C/peak`);
#   • `eeq` was driven by the C binary's daily PET (`eeqs = pet_C/1.32`, which embeds `albedo_patch`).
# Here F_diff computes BOTH itself — the GSI leaf phenology (`phenology_gsi.c`) and the dynamic surface
# albedo (`albedo_stand.c`/`albedo_tree.c`/`albedo_grass.c` → `petpar2.c` `eeq`) — plus daylength from
# latitude (`petpar2.c`), so the daily rollout needs only the atmospheric forcing + the S-supplied
# structure. All ports are differentiable (the GSI limiters are already sigmoids; the hard `acos`
# polar-day/night and `exp`-overflow branches are replaced by clamped surrogates).
# ─────────────────────────────────────────────────────────────────────────────────────────────

# LPJmL surface-albedo constants (fixed C `#define`s — never AD parameters). `include/soil.h`
# (`c_albsnow`, `c_albsoil`, `c_watertosnow`), `src/tree/albedo_tree.c` (`c_fstem`),
# `src/soil/snow.c` (`c_roughness`).
const C_ALBSNOW = 0.65          # snow albedo (soil.h:54)
const C_ALBSOIL = 0.3          # bare-soil albedo, live non-FMS path (soil.h:55)
const C_FSTEM = 0.7            # ground masking by stems/branches when leafless (albedo_tree.c:21)
const C_WATERTOSNOW = 6.7      # mm water → m snow depth (soil.h:58)
const C_ROUGHNESS = 0.06        # sub-canopy roughness height, m (snow.c:18)

deg2rad_(deg) = deg * π / 180   # include/units.h:20

"""
    petpar_daylength(lat, doy) -> hours

Daylength (h) from latitude (°) and day-of-year (1–365), the LPJmL-FIT radiation routine
(`src/numeric/petpar2.c:47-59`): solar declination `δ = −23.4°·cos(2π(doy+10)/365)`, `u = sinφ·sinδ`,
`v = cosφ·cosδ`, `daylength = 24/π·acos(−u/v)`. The C's three-way polar-day (`u≥v`) / polar-night
(`u≤−v`) / normal branch is the exact equivalent of clamping the `acos` argument to `[−1,1]`, so it is
implemented branch-free here. `lat`/`doy` are constants (not AD parameters), so the `clamp` and `acos`
are gradient-safe. Reproduces the daylength currently supplied as forcing (validated to ~0 on Hainich).
"""
function petpar_daylength(lat, doy)
    δ = deg2rad_(-23.4 * cos(2π * (doy + 10.0) / 365.0))
    u = sin(deg2rad_(lat)) * sin(δ)
    v = cos(deg2rad_(lat)) * cos(δ)
    arg = clamp(-u / v, -one(u), one(u))          # −1 → 24 h (polar day), +1 → 0 h (polar night)
    return 24 * acos(arg) / π
end

"""
    PhenParams{T}

GSI ("new phenology") leaf-phenology parameters (`src/lpj/phenology_gsi.c`; `par/pft.js` per PFT).
Four limiting functions — cold-temperature `tmin`, heat-stress `tmax`, `light`, water `wscal` — each a
logistic `sigmoid(sl·(x−base))` low-passed toward the previous day by rate `tau`; `phen` is their
product. Defaults are the temperate broadleaved summergreen tree (beech, PFT id 3, `par/pft.js:527-550`;
`wscal_base = minwscal·100 = 20.96`). `soiltemp_gate`/`βgate` implement the C's `soil→temp[0] < 10 °C ⇒
wscal factor forced open` rule (`phenology_gsi.c:67`), driven here by air temperature (LPJmL uses air
temp as the soil top boundary condition). `εfloor` is the C `max(epsilon, ·)` factor floor.
"""
Base.@kwdef struct PhenParams{T <: Real}
    tmin_sl::T = 2.0
    tmin_base::T = 8.0
    tmin_tau::T = 0.2
    tmax_sl::T = 1.74
    tmax_base::T = 41.51
    tmax_tau::T = 0.2
    light_sl::T = 58.0
    light_base::T = 40.0
    light_tau::T = 0.2
    wscal_sl::T = 5.24
    wscal_base::T = 20.96          # = minwscal (0.2096) × 100
    wscal_tau::T = 0.1
    soiltemp_gate::T = 10.0
    βgate::T = 1.0                 # smoothing of the 10 °C soil-temp water gate
    εfloor::T = 1.0e-7
end

"""
    PhenState{T}

The four recurrent GSI low-pass filter values (`Phenology` struct, `include/pft.h:78-84`). LPJmL
initialises the cold-temperature and light filters closed (`0`) and the heat/water filters open (`1`)
(`src/lpj/newpft.c:44-45`).
"""
Base.@kwdef struct PhenState{T <: Real}
    tmin::T = 0.0
    tmax::T = 1.0
    light::T = 0.0
    wscal::T = 1.0
end
_wt(::PhenState{T}) where {T} = T

"""
    tebs_phenparams(::Type{T}=Float64) -> PhenParams{T}

GSI phenology parameters for the beech (TeBS, PFT id 3) — the Hainich prototype's dominant PFT.
"""
tebs_phenparams(::Type{T} = Float64) where {T <: Real} = PhenParams{T}()

"""
    phenology_gsi_step(pp, ps, temp, swdown, water_avail, soiltemp) -> (ps′, phen)

One day of the GSI leaf phenology (`phenology_gsi.c:50-84`). Given the persisted filter state `ps`
([`PhenState`](@ref)), daily-mean air `temp` (°C), shortwave-down `swdown` (W/m²), plant water
availability `water_avail ∈ [0,1]` (the previous day's water scalar; `pft->wscal`), and `soiltemp` (°C,
air-temp proxy), advance the four filters and return the new state and `phen = tmin·tmax·light·wscal`.
Each filter is `f += (target − f)·tau` with `target = sigmoid(±sl·(x−base))` ([`stable_sigmoid`](@ref)
guards the steep-slope `exp` overflow that the C handles with its `<200` branch), then floored at
`εfloor`. The water filter is forced open (`= 1`) below `soiltemp_gate` °C, blended smoothly by `βgate`.
"""
function phenology_gsi_step(pp::PhenParams, ps::PhenState, temp, swdown, water_avail, soiltemp)
    T = promote_type(_wt(ps), typeof(temp), typeof(swdown), typeof(water_avail), typeof(soiltemp))
    ε = convert(T, pp.εfloor)
    # cold-temperature (rising in temp) — sigmoid(sl·(T−base))
    tmin_t = stable_sigmoid(pp.tmin_sl * (temp - pp.tmin_base))
    tmin = max(ps.tmin + (tmin_t - ps.tmin) * pp.tmin_tau, ε)
    # heat stress (falling in temp) — 1/(1+exp(+sl·(T−base))) = sigmoid(−sl·(T−base))
    tmax_t = stable_sigmoid(-pp.tmax_sl * (temp - pp.tmax_base))
    tmax = max(ps.tmax + (tmax_t - ps.tmax) * pp.tmax_tau, ε)
    # light (rising in shortwave) — the C's `<200` overflow branch (relax toward 0) is exactly the
    # clamped sigmoid's saturated value, so no explicit branch is needed.
    light_t = stable_sigmoid(pp.light_sl * (swdown - pp.light_base))
    light = max(ps.light + (light_t - ps.light) * pp.light_tau, ε)
    # water (rising in availability, %) with the soil-temp gate: cold ⇒ forced open (=1)
    wsc_t = stable_sigmoid(pp.wscal_sl * (100 * water_avail - pp.wscal_base))
    gate = stable_sigmoid(pp.βgate * (soiltemp - pp.soiltemp_gate))   # ≈0 cold → open; ≈1 warm → sigmoid
    wsc_warm = ps.wscal + (wsc_t - ps.wscal) * pp.wscal_tau
    wscal = max(gate * wsc_warm + (one(T) - gate) * one(T), ε)
    ps′ = PhenState{T}(convert(T, tmin), convert(T, tmax), convert(T, light), convert(T, wscal))
    phen = tmin * tmax * light * wscal
    return (ps′, convert(T, phen))
end

# ── snow state from the snowpack (src/soil/snow.c:120-126) ───────────────────────────────────────
# HS = c_watertosnow·(snowpack/1000) m; snowfraction = HS/(HS + 0.5·c_roughness). Both → 0 as
# snowpack → 0 (the C's `snowpack>epsilon` branch is a no-op here since the smooth form already
# vanishes), so no branch is needed.
@inline function _snow_state(snowpack::T) where {T <: Real}
    HS = T(C_WATERTOSNOW) * snowpack / 1000
    sfr = HS / (HS + T(0.5) * T(C_ROUGHNESS))
    return (HS, sfr)
end

"""
    patch_albedo(inds, phen, snowpack) -> beta

Dynamic patch surface albedo `beta` (`src/lpj/albedo_stand.c:56-64`), the value LPJmL feeds to
`petpar2`'s `eeq` (via `swnet = (1−beta)·swdown`). Each individual contributes
`fpc·(frs·c_albsnow + (1−frs)·albveg)`, where the leaf-on/off vegetation albedo is
`phen·albedo_leaf + (1−phen)·(c_fstem·albedo_stem + (1−c_fstem)·albedo_litter)` for a tree and
`phen·albedo_leaf + (1−phen)·albedo_litter` for grass (no stem; `albedo_tree.c:56-68`,
`albedo_grass.c:40-49`). The exposed-ground fraction `max(1−Σfpc, 0)` gets
`snowfraction·c_albsnow + (1−snowfraction)·c_albsoil`. The canopy snow-burial term `frs2`
(`albedo_tree.c:44-52`, snow deeper than the canopy base) is neglected — a v1 simplification that
requires per-individual height and is negligible at temperate Hainich (snow ≪ crown base); the
dominant snow effect (ground snow via the exposed fraction, and `frs1`) is exact. For a leaf-on beech
patch (`Σfpc ≈ 0.56`) this gives `beta ≈ 0.56·0.15 + 0.44·0.30 ≈ 0.22`, vs the fixed `0.15` the earlier
canopy runs used — exactly the ~7 % PET overshoot the C-`eeq` drive had been correcting.
"""
function patch_albedo(inds, phen, snowpack)     # `inds`::AbstractVector{<:Individual} (defined below)
    T = promote_type(isempty(inds) ? Float64 : _wt(first(inds)), typeof(phen), typeof(snowpack))
    ph = convert(T, phen)
    (_, sfr) = _snow_state(convert(T, snowpack))
    cfs = T(C_FSTEM)
    albstot = zero(T)
    fpc_sum = zero(T)
    for ind in inds
        fpc_i = convert(T, ind.fpc)
        al = convert(T, ind.albedo_leaf)
        ast = convert(T, ind.albedo_stem)
        alt = convert(T, ind.albedo_litter)
        scf = convert(T, ind.snowcanopyfrac)
        if ind.is_grass
            albveg = ph * al + (one(T) - ph) * alt
            frs = sfr * (ph * scf + (one(T) - ph))                     # grass frs1 (no stem term)
        else
            albveg = ph * al + (one(T) - ph) * (cfs * ast + (one(T) - cfs) * alt)
            frs = sfr * (ph * scf + (one(T) - ph) * (one(T) - cfs))    # tree frs1 (frs2 neglected, v1)
        end
        albstot += fpc_i * (frs * T(C_ALBSNOW) + (one(T) - frs) * albveg)
        fpc_sum += fpc_i
    end
    fbare = softplus(one(T) - fpc_sum, T(50.0))                        # max(1−Σfpc, 0), smooth
    return albstot + fbare * (sfr * T(C_ALBSNOW) + (one(T) - sfr) * T(C_ALBSOIL))
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
maintenance-respiration pools, `lai` = its leaf-on crown LAI (`leaf_c·sla/crownarea`) and `intc` = the
PFT interception coefficient (`par->intc`) — together these give the wet-canopy fraction
`wet = min(intc·lai·phen·rain/(eeq·1.32), 0.9999)` (`interception.c`) that reduces transpirative demand
by `(1 − wet)` and evaporates `eeq·1.32·wet·fpc` off the wet canopy. `albedo_stem`/`albedo_litter`/
`snowcanopyfrac` are the PFT surface-albedo constants (`par/pft.js`) feeding the dynamic patch albedo
[`patch_albedo`](@ref) that lets standalone F_diff compute its own `eeq` (no `pet_C` drive). `nind` is
the individual density (indiv/m², patch basis) — used so maintenance respiration is formed per-m²
(`nind·pool`, `npp_tree.c:51`) and so the accumulated per-m² `bm_inc` maps to the per-individual
allocation (`bm_inc/nind`, [`grow_individual`](@ref)). `photo`/
`tstress` are the per-PFT [`PhotoParams`](@ref) / [`TempStressParams`](@ref) (the SLA-Vcmax cap uses
this individual's `sla`). `is_grass` skips woody respiration and the stem-albedo term. Build the Hainich
set from `test/testitems/references/hainich_individuals_2010.csv`.
"""
struct Individual{T <: Real}
    fpar::T                       # layered absorbed-PAR fraction (leafon, patch basis)
    fpc::T                        # foliar projective cover (patch basis)
    alphaa::T
    albedo_leaf::T
    emax::T
    c_sapwood::T
    c_root::T
    lai::T                        # leaf-on crown LAI (leaf_c·sla/crownarea) → actual_lai = lai·phen
    intc::T                       # PFT interception coefficient (par->intc)
    albedo_stem::T                # PFT stem/branch albedo (leaf-off; par->albedo_stem)
    albedo_litter::T              # PFT litter background albedo (par->albedo_litter)
    snowcanopyfrac::T             # PFT max snow coverage in green canopy (par->snowcanopyfrac)
    nind::T                       # individual density, indiv/m² (patch basis; = 1/patcharea per tree)
    photo::PhotoParams{T}
    tstress::TempStressParams{T}
    is_grass::Bool
end
_wt(::Individual{T}) where {T} = T

# ── wet-canopy interception (interception.c) ─────────────────────────────────────────────────────
# Relative canopy wetness `wet = min(intc·actual_lai·rain/(eeq·α_PT), 0.9999)` with `actual_lai = lai·phen`
# and the interception-store cap `int_store = min(intc·actual_lai, 0.9999)`; the intercepted water that
# evaporates off the wet canopy is `eeq·α_PT·wet·fpc` (mm). Returns `(wet, interc_flux)`; both zero when
# `eeq` or `fpc` vanish (interception.c:24-27). Hard `min` (physical caps, AD selects the live branch).
@inline function _wet_interc(intc, lai, phen, fpc, eeq, rain, α_PT)
    T = promote_type(typeof(intc), typeof(lai), typeof(phen), typeof(fpc), typeof(eeq), typeof(rain))
    (eeq < T(1.0e-4) || fpc <= zero(T)) && return (zero(T), zero(T))
    int_store = min(intc * lai * phen, T(0.9999))
    wet = min(int_store * rain / (eeq * α_PT), T(0.9999))
    interc = eeq * α_PT * wet * fpc
    return (convert(T, wet), convert(T, interc))
end

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
evaporation → per-individual respiration. Wet-canopy interception (`_wet_interc`,
`interception.c`) evaporates off each individual (removed from infiltration) and reduces each
individual's demand by `(1 − wet)`. By default `eeq` is self-computed from the DYNAMIC patch albedo
([`patch_albedo`](@ref)), so no C-PET crutch is needed; `eeq_ext` overrides it with the C binary's own
daily PET (`pet_C/α_PT`) for the kernel-isolation comparison of §10. Returns the new state and stand
daily fluxes `(gpp, npp, transp, evap, interc, eeq, runoff, rootmoist, fapar, fpc, wscal, npp_ind)`
(per m² of patch; `wscal` = the stand water scalar feeding next day's GSI water phenology; `npp_ind` =
the per-individual daily NPP vector, whose annual sum is each individual's `bm_inc` for
[`grow_individual`](@ref)). Water closes exactly:
`precip = transp + evap + interc + runoff + Δ(Σw + snow)`.
"""
function daily_step_canopy(
        p::FDiffParams, inds::AbstractVector{<:Individual}, soil::SoilColumn, st::FDiffStateML,
        f::DailyForcing; phen = 1.0, n_top1m::Int = 3, eeq_ext = nothing
    )
    T = promote_type(_wt(p), _wt(st), _wt(soil), _wt(f), isempty(inds) ? Float64 : _wt(first(inds)))
    ph = convert(T, phen)
    w = p.water
    # eeq: by default self-computed from the DYNAMIC patch albedo (patch_albedo — the albedo_stand.c
    # port), so standalone F_diff needs no C-PET crutch (§11). `eeq_ext` (= pet_C/α_PT) still overrides
    # it for the kernel-isolation comparison of §10 (the C binary's own daily albedo_patch).
    eeq = if eeq_ext === nothing
        beta = patch_albedo(inds, ph, st.snowpack)
        priestley_taylor_eeq(w, f.swdown, f.lwnet, f.temp, f.daylength, beta)
    else
        convert(T, eeq_ext)
    end

    # shared snow + interception + infiltration into the column
    frac_rain = sigmoid(w.βsnow * (f.temp - w.tsnow))
    rain = frac_rain * f.precip
    snowfall = (one(T) - frac_rain) * f.precip
    melt_potential = w.melt_factor * softplus(f.temp - w.tsnow, w.βmelt)
    melt = smoothmin(melt_potential, st.snowpack + snowfall, w.βmelt)
    snowpack′ = st.snowpack + snowfall - melt
    # wet-canopy interception: sum the evaporated flux (removed from infiltration); the demand-reducing
    # per-individual `wet` is recomputed in pass 2 (deterministic in eeq/rain/phen/lai/intc).
    interc_tot = zero(T)
    for ind in inds
        (_, interc_i) = _wet_interc(convert(T, ind.intc), convert(T, ind.lai), ph, convert(T, ind.fpc), eeq, rain, w.α_PT)
        interc_tot += interc_i
    end
    interc_tot = smoothmin(interc_tot, rain, w.βw)          # cannot intercept more than the rain
    infil = rain + melt - interc_tot
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
    sup_acc = zero(T); dem_acc = zero(T)        # fpc-weighted supply/demand → stand water scalar (phenology)
    npp_inds = Vector{T}(undef, length(inds))   # per-individual daily NPP (per-m², patch basis) → bm_inc
    for (ii, ind) in enumerate(inds)
        fpc_i = convert(T, ind.fpc) * ph
        fpar_i = convert(T, ind.fpar) * ph                 # layered absorbed fraction (phen-scaled)
        apar = par * (one(T) - convert(T, ind.albedo_leaf)) * convert(T, ind.alphaa) * fpar_i
        tsi = temp_stress(ind.tstress, f.temp, dl)
        (_, _, vm, _) = photosynthesis(ind.photo, w.lambda_opt, tsi, co2_Pa, f.temp, apar, dl; comp_vm = true)
        supply_i = convert(T, ind.emax) * wr * ph
        # wet-canopy demand reduction (1 − wet); water_stressed.c re-caps wet at 0.99
        (wet_i, _) = _wet_interc(convert(T, ind.intc), convert(T, ind.lai), ph, convert(T, ind.fpc), eeq, rain, w.α_PT)
        wet_dem = smoothmin(wet_i, T(0.99), w.βw)
        (gc, demand) = canopy_conductance(w, eeq, gp_stand, supply_i; wet = wet_dem)   # demand uses the STAND mean gp
        sup_acc += supply_i * fpc_i
        dem_acc += demand * fpc_i
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
        # maintenance respiration is PER-M² (patch basis): the C multiplies the per-individual sapwood/
        # root carbon by `nind` (`npp_tree.c:51` `mresp = nind·(sapwood·… + root·…)`), consistent with
        # the per-m² `gpp_i`/`rd` here — so `bm_inc = Σ npp_i` accumulates on the same patch basis the
        # annual allocation (`allocation_tree.c:236` `bm_inc_ind = bm_inc/nind`) divides back out.
        nind_i = convert(T, ind.nind)
        c_sap = ind.is_grass ? zero(T) : convert(T, ind.c_sapwood) * nind_i
        (npp_i, _) = autotrophic_respiration(p.resp, f.temp, gpp_i, rd, c_sap, convert(T, ind.c_root) * nind_i)
        npp_tot += npp_i
        npp_inds[ii] = npp_i
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
    # stand water scalar (min(1, Σsupply·fpc / Σdemand·fpc)) — feeds next day's GSI water phenology
    wscal = smoothmin(one(T), sup_acc / (dem_acc + T(1.0e-9)), w.βwscal)
    st′ = FDiffStateML{T}(w3, convert(T, snowpack′))
    fluxes = (
        gpp = convert(T, gpp_tot), npp = convert(T, npp_tot), transp = convert(T, transp),
        evap = convert(T, soil_evap), interc = convert(T, interc_tot), eeq = convert(T, eeq),
        runoff = convert(T, runoff), rootmoist = convert(T, rootmoist),
        fapar = convert(T, fapar_tot), fpc = convert(T, fpc_tot), wscal = convert(T, wscal),
        npp_ind = npp_inds,       # per-individual daily NPP (per-m², patch basis) — the flux-then-integrate bm_inc source
    )
    return (st′, fluxes)
end

"""
    rollout_daily_canopy(p, st0, inds, soil, forcings; phens=nothing, eeqs=nothing,
                         phen_params=nothing, phen_state=nothing, n_top1m=3) -> (st, days)

Fold [`daily_step_canopy`](@ref) over a vector of [`DailyForcing`](@ref) for ONE patch canopy `inds`,
carrying the shared per-layer soil water and snow. **By default (standalone, crutch-free) F_diff
computes both the phenology and the `eeq` albedo itself** (§11): the daily leaf-display factor `phen`
comes from the GSI phenology ([`phenology_gsi_step`](@ref) with `phen_params`, default
[`tebs_phenparams`](@ref)), advanced from the air temperature, shortwave, and the previous day's stand
water scalar (the soil-temp gate uses air temp as its proxy); and `eeq` from the dynamic
[`patch_albedo`](@ref). Passing `phens` (e.g. `fapar_C/peak`) and/or `eeqs` (the C's `pet_C/α_PT`)
overrides these with the C-binary-driven values for kernel-isolation comparison (§9/§10). `phen_state`
optionally seeds the GSI filters (e.g. for multi-year continuity); it defaults to the LPJmL cold-start
(`newpft.c:44-45`). Returns the final [`FDiffStateML`](@ref) and the per-day stand flux `NamedTuple`s.
"""
function rollout_daily_canopy(
        p::FDiffParams, st0::FDiffStateML, inds::AbstractVector{<:Individual}, soil::SoilColumn,
        forcings; phens = nothing, n_top1m::Int = 3, eeqs = nothing,
        phen_params = nothing, phen_state = nothing
    )
    T = promote_type(_wt(p), _wt(st0), _wt(soil), _wt(first(forcings)), isempty(inds) ? Float64 : _wt(first(inds)))
    st = FDiffStateML{T}(convert.(T, st0.w), convert(T, st0.snowpack))
    pp = phen_params === nothing ? tebs_phenparams(T) : phen_params
    ps = phen_state === nothing ? PhenState{T}() : phen_state
    water_avail = one(T)                          # previous day's stand water scalar (moist cold-start)
    ph1 = phens === nothing ? one(T) : convert(T, phens[1])
    ee1 = eeqs === nothing ? nothing : eeqs[1]
    days = Vector{typeof(daily_step_canopy(p, inds, soil, st, first(forcings); phen = ph1, n_top1m = n_top1m, eeq_ext = ee1)[2])}()
    sizehint!(days, length(forcings))
    for (i, f) in enumerate(forcings)
        # phenology: supplied crutch (phens) OR self-computed GSI (soil-temp gate ≈ air temp)
        if phens === nothing
            (ps, ph) = phenology_gsi_step(pp, ps, f.temp, f.swdown, water_avail, f.temp)
        else
            ph = convert(T, phens[i])
        end
        ee = eeqs === nothing ? nothing : eeqs[i]
        (st, fl) = daily_step_canopy(p, inds, soil, st, f; phen = ph, n_top1m = n_top1m, eeq_ext = ee)
        water_avail = fl.wscal                    # today's water status → tomorrow's water phenology
        push!(days, fl)
    end
    return (st, days)
end

# ═════════════════════════════════════════════════════════════════════════════════════════════
# DYNAMIC (PROGNOSTIC WITHIN-YEAR) CANOPY STRUCTURE (scale-up step 6 — docs §12)
# ═════════════════════════════════════════════════════════════════════════════════════════════
# Steps 3–5 fixed each individual's structure at its year-END value for the whole year (a daily
# phenology factor scaled leaf display, but crown/leaf/sapwood were static). Here the per-individual
# carbon pools become PROGNOSTIC state that (a) accumulate the daily bm_inc (= Σ daily NPP, per-m² patch
# basis — see the `npp_ind` flux) and (b) at the annual boundary GROW via a faithful differentiable port
# of the LPJmL-FIT year-end sequence `turnover_tree.c` → `allocation_tree.c` → `allometry_tree.c`
# (`annual_tree.c:29-30`). This is the flux-then-integrate carbon handoff (DESIGN §8): F delivers the
# conserved `bm_inc`; the allocation partitions it into the pools subject to the pipe-model
# (leaf-area:sapwood-area, `k_latosa`), the leaf:root ratio (`lmtorm`, water-stress-modulated), and the
# Jucker-2022 crown/height allometry; then height/crownarea/LAI/FPC are re-derived. Verified line-by-line
# against /home/jamirp/lpjml56fit v5.6.004 (with_nitrogen=no, FIT individual mode, PFT 3 beech; the
# `par/pft_lpjmlfit.js` ANGIO constants are the `Allometry.TreeAllometry` defaults).
#
# v1 simplifications (documented; NOT bit-exact to the C):
#   • below-ground root-sapwood (`sapwood_bg`, `allocation_tree.c:163-209`, `C_LATERAL` lateral demand)
#     is neglected — it reduces `bm_inc` before the aboveground allocation; a FIT root-sapwood
#     correction, second-order to the aboveground structure the `ind` output records;
#   • the carbon-debt loan (`allocation_tree.c:288-297`) is off (debt=0 for a healthy growing tree —
#     only fires when `bm_inc < min` leaf+root demand);
#   • daily-accumulated leaf/root turnover (`turnover_daily_tree.c`) is applied at the annual PFT rates
#     (`turnover.{leaf,sapwood,root}`); the summergreen full-leaf-drop uses the individual-mode
#     `leaf/1.05` form (`turnover_tree.c:102`);
#   • the raingreen `cmass_excess` (`turnover_tree.c:83`) is skipped (≤0 for beech: `longevity·365 > 365 ≥
#     aphen`, verified);
#   • grasses hold structure fixed (no woody allocation — `grass_allocation.c` is a separate v2 item);
#   • establishment + whole-tree mortality are S's demography, held fixed (fixed-N prototype).
# ─────────────────────────────────────────────────────────────────────────────────────────────
"""
    AllocParams{T}

Annual carbon-allocation + turnover parameters (`allocation_tree.c` / `turnover_tree.c`; beech PFT 3,
`par/pft_lpjmlfit.js`). `lmro_ratio`/`lmro_offset` set the leaf:root ratio `lmtorm = lmro_ratio·(lmro_offset
+ (1−lmro_offset)·min(1, wscal))`; `reprod_cost` is the reproduction reserve removed from `bm_inc` before
allocation; the `turnover_*` are the annual tissue-turnover RATES (= 1/residence-time: beech leaf 1.0,
sapwood 0.04 = 1/25 yr, root 1.0); `deciduous_leaf_div` is the summergreen individual-mode annual leaf
turnover divisor (`turn.leaf = leaf/1.05`). `niter`/`ω`/`h` control the fixed-graph damped-Newton
allocation solve.
"""
Base.@kwdef struct AllocParams{T <: Real}
    lmro_ratio::T = 1.0
    lmro_offset::T = 0.5
    reprod_cost::T = 0.1
    turnover_leaf::T = 1.0            # 1/yr (residence 1 yr; summergreen)
    turnover_sapwood::T = 0.04        # = 1/25 yr
    turnover_root::T = 1.0            # 1/yr
    deciduous_leaf_div::T = 1.05      # summergreen isphen leaf turnover: turn.leaf = leaf/1.05
    is_deciduous::Bool = true         # summergreen ⇒ full annual leaf recycle (else leaf·turnover_leaf)
    niter::Int = 60                   # allocation-solve fixed-graph Newton iterations
    ω::T = 0.5                        # Newton damping
    h::T = 1.0e-7                     # central-FD step for the residual derivative
end

"""
    tebs_allocparams(::Type{T}=Float64) -> AllocParams{T}

Allocation/turnover parameters for the beech (TeBS, PFT id 3) — the Hainich prototype's dominant PFT.
"""
tebs_allocparams(::Type{T} = Float64) where {T <: Real} = AllocParams{T}()

"""
    TreePools{T}

Prognostic per-individual carbon pools + geometry (the state the annual allocation advances). Carbon
`gC/individual`: `leaf_c`, `sapwood_c`, `heartwood_c`, `root_c`; `height` (m), `crownarea` (m²), `nind`
(indiv/m², patch basis). `sla` (m²/gC) and `wooddens` (gC/m³) are the per-individual allometry inputs
(the reconstruction draws them per tree); `is_grass` skips woody allocation. Built for the Hainich set
from `test/testitems/references/hainich_individuals_2010.csv` and advanced by [`grow_individual`](@ref).
"""
struct TreePools{T <: Real}
    leaf_c::T
    sapwood_c::T
    heartwood_c::T
    root_c::T
    height::T
    crownarea::T
    nind::T
    sla::T
    wooddens::T
    is_grass::Bool
end
_wt(::TreePools{T}) where {T} = T

"aboveground biomass of one individual (gC): leaf + sapwood + heartwood (`agb_tree_sum`, `tree.h:249`)."
agb_ind(t::TreePools) = t.leaf_c + t.sapwood_c + t.heartwood_c
"total vegetation carbon of one individual (gC): + fine root (bg sapwood/heartwood neglected, v1)."
vegc_ind(t::TreePools) = t.leaf_c + t.sapwood_c + t.heartwood_c + t.root_c

# ── the allocation residual f(leaf_inc)=0 (allocation_tree.c:120-125) ─────────────────────────────
# f(x) = k1·(b − x·lm_coef + ind_heart) − ((b − x·lm_coef)/(ind_leaf + x)·k3)^(1 + 2/allom3)
# (eq 15 stem-allometry height^(1+2/allom3) minus eq 21 pipe-model height^(1+2/allom3)). The power base
# is floored at 0 (a non-integer power of a negative base is NaN; the C's bracket guards keep it ≥0, and
# the floor's derivative for the exponent >1 vanishes as base→0 — AD-safe).
@inline function _alloc_residual(x, b, lm_coef, k1, k3, ind_leaf, ind_heart, allom3)
    T = promote_type(typeof(x), typeof(b))
    num = b - x * lm_coef
    base = num / (ind_leaf + x) * k3
    base = max(base, zero(T))
    return k1 * (num + ind_heart) - base^(one(T) + 2 / allom3)
end

# ── differentiable allocation solve (fixed-graph damped Newton + bracket clamp; solve_lambda pattern) ─
# The C uses leftmostzero (NSEG scan for the first sign change) + bisection; bisection midpoints are not
# smooth in the parameters, so — exactly as for the λ solve — we use a FIXED-ITERATION damped Newton
# with a FIXED computational graph and a plain `clamp` to the physical bracket [x1,x2]. At convergence
# the total derivative equals the implicit-function result regardless of the (finite-difference) g′; the
# clamp discards any divergent-branch derivative. A short primal scan over the bracket seeds Newton at
# the segment with the smallest |f| (robust to the residual's non-monotonicity), matching leftmostzero's
# left-to-right intent.
function _solve_leaf_inc(x1::T, x2::T, b, lm_coef, k1, k3, ind_leaf, ind_heart, allom3, niter::Int, ω, h) where {T}
    lo = min(x1, x2); hi = max(x1, x2)
    # degenerate-bracket guard (allocation_tree.c:318-320) → no leaf increment
    if (x1 == 0 && x2 == 0) || (b - x1 * lm_coef < 0) || (ind_leaf + x1 <= 0) ||
            (b - x2 * lm_coef < 0) || (ind_leaf + x2 <= 0)
        return zero(T)
    end
    fx(x) = _alloc_residual(x, b, lm_coef, k1, k3, ind_leaf, ind_heart, allom3)
    # seed at the bracket segment (of NSEG=20) with the smallest |f| (leftmostzero-style)
    nseg = 20
    x = lo; best = abs(fx(lo))
    for s in 1:nseg
        xs = lo + (hi - lo) * s / nseg
        v = abs(fx(xs))
        if v < best
            best = v; x = xs
        end
    end
    for _ in 1:niter
        gx = fx(x)
        dg = (fx(x + h) - fx(x - h)) / (2h)
        # guard a vanishing derivative (softplus-free): fall back to a tiny step when |dg| underflows
        step = abs(dg) > T(1.0e-30) ? ω * gx / dg : zero(T)
        x = clamp(x - step, lo, hi)
    end
    return x
end

"""
    grow_individual(alloc::AllocParams, allom::Allometry.TreeAllometry, tree::TreePools, bm_inc_ind, wscal_mean) -> TreePools

Advance one tree individual's carbon pools + geometry by one year (the LPJmL-FIT annual sequence
`turnover_tree` → `allocation_tree` → `allometry_tree`, `annual_tree.c:29-30`), given the accumulated
per-individual biomass increment `bm_inc_ind` (gC/individual = Σ daily NPP / `nind`) and the annual-mean
stand water scalar `wscal_mean ∈ [0,1]` (drives `lmtorm`). Returns the grown [`TreePools`](@ref). Pure
and differentiable (the pipe-model allocation solve is [`_solve_leaf_inc`](@ref); the height cap
sapwood→heartwood transfer is a smooth-a.e. `min`). Grasses are returned unchanged (v1). See the section
header for the v1 simplifications.
"""
function grow_individual(alloc::AllocParams, allom::Allometry.TreeAllometry, tree::TreePools{T0}, bm_inc_ind, wscal_mean) where {T0}
    tree.is_grass && return tree
    # promote to the working (AD) type so differentiating w.r.t. bm_inc/wscal makes T a Dual while the
    # Float64 pool state widens into it (the daily-step pattern).
    T = promote_type(T0, typeof(float(bm_inc_ind)), typeof(float(wscal_mean)))
    bm = convert(T, bm_inc_ind)
    sla = convert(T, tree.sla); wd = convert(T, tree.wooddens)
    H = convert(T, tree.height)
    # reproduction reserve (only if bm_inc≥0): bm_inc·reprod_cost leaves the pools (→ estab/litter)
    bm_net = bm >= 0 ? bm * (one(T) - convert(T, alloc.reprod_cost)) : bm
    # STAGNATION guard: a carbon-deficit individual (bm_net ≤ 0) is held FIXED (v1). For a summergreen the
    # leaves are shed annually and must be REGROWN from bm_inc; with no positive increment the tree cannot
    # regrow them, and stripping leaf→~0 while re-deriving `height = k_latosa·sapwood/(leaf·sla·wd)` would
    # blow height up. In LPJmL such a tree hits `isneg_tree` and DIES; here whole-tree mortality is S's
    # demography (fixed-N prototype), so the deficit individual simply stagnates (no growth, no death).
    (H <= 0 || bm_net <= 0) && return tree

    # ── turnover_tree.c (no-N, individual mode, summergreen): sapwood→heartwood + leaf/root recycle ──
    turn_sap = convert(T, tree.sapwood_c) * convert(T, alloc.turnover_sapwood)
    sm = convert(T, tree.sapwood_c) - turn_sap
    hm = convert(T, tree.heartwood_c) + turn_sap
    lm = alloc.is_deciduous ? convert(T, tree.leaf_c) - convert(T, tree.leaf_c) / convert(T, alloc.deciduous_leaf_div) :
        convert(T, tree.leaf_c) * (one(T) - convert(T, alloc.turnover_leaf))
    rm = convert(T, tree.root_c) * (one(T) - convert(T, alloc.turnover_root))

    # ── allocation_tree.c (with_nitrogen=no) ──
    lmtorm = convert(T, alloc.lmro_ratio) *
        (convert(T, alloc.lmro_offset) + (one(T) - convert(T, alloc.lmro_offset)) * smoothmin(one(T), convert(T, wscal_mean), T(30.0)))
    k_latosa = allom.k_latosa; allom2 = allom.allom2; allom3 = allom.allom3
    leaf_inc = zero(T); root_inc = zero(T); sap_inc = zero(T); heart_inc = zero(T)
    # minimum leaf/root to maintain current sapwood (eq 27)
    leaf_min = k_latosa * sm / (wd * H * sla) - lm
    root_min = k_latosa * sm / (wd * H * sla * lmtorm) - rm
    normal = (root_min >= 0 && leaf_min >= 0 && (root_min + leaf_min <= bm_net))
    if normal
        b = sm + bm_net - lm / lmtorm + rm
        lm_coef = one(T) + one(T) / lmtorm
        k1 = allom2^(2 / allom3) * 4 * (one(T) / π) / wd
        k3 = k_latosa / wd / sla
        x2 = (bm_net - (lm / lmtorm - rm)) / lm_coef
        x1 = lm < T(1.0e-10) ? x2 / 20 : zero(T)
        leaf_inc = _solve_leaf_inc(x1, x2, b, lm_coef, k1, k3, lm, hm, allom3, alloc.niter, convert(T, alloc.ω), convert(T, alloc.h))
        root_inc = leaf_inc < 0 ? zero(T) : (leaf_inc + lm) / lmtorm - rm
        # proportional cap if leaf+root exceed bm (allocation_tree.c:327-331; faithful quirk: the
        # leaf rescale uses the ALREADY-updated root_inc denominator)
        if root_inc + leaf_inc > bm_net
            tot = root_inc + leaf_inc
            root_inc = bm_net * root_inc / tot
            leaf_inc = bm_net * leaf_inc / (root_inc + leaf_inc)
        end
        sap_inc = bm_net - leaf_inc - root_inc
        heart_inc = zero(T)
    else
        # abnormal allocation (allocation_tree.c:341-354): leaves + roots only, sapwood→heartwood
        leaf_inc = (bm_net + rm - lm / lmtorm) / (one(T) + one(T) / lmtorm)
        if leaf_inc > 0
            root_inc = bm_net - leaf_inc
        else
            root_inc = bm_net
            leaf_inc = (rm + root_inc) * lmtorm - lm
        end
        sap_inc = (leaf_inc + lm) * wd * H * sla / k_latosa - sm
        heart_inc = -sap_inc
    end
    lm += leaf_inc; rm += root_inc; sm += sap_inc; hm += heart_inc

    # ── allometry_tree.c: height from pipe model, height cap sapwood→heartwood, crownarea ──
    height_new = (sm <= 0 || lm <= 0) ? zero(T) : k_latosa * sm / (lm * sla * wd)
    if height_new > allom.height_max
        sm_temp = sm
        sm = lm * convert(T, allom.height_max) * wd * sla / k_latosa
        hm = hm + (sm_temp - sm)
        height_new = convert(T, allom.height_max)
    end
    crownarea_new = height_new > 0 ? min(allom.allom1 * (height_new / allom2)^(allom.kpr / allom3), convert(T, allom.crownarea_max)) : zero(T)
    return TreePools{T}(lm, sm, hm, rm, height_new, crownarea_new, convert(T, tree.nind), sla, wd, tree.is_grass)
end

# ── per-patch layered Beer–Lambert light (getfpar.c) → per-individual leaf-on fpar ────────────────
# Recomputes each tree's absorbed-PAR fraction as heights change across years (the light competition
# feedback). Fixed `nlayers` loop (AD-safe; layers above the tallest tree contribute 0 naturally). The
# height/boleht layer-membership tests compare by value under ForwardDiff, so the arithmetic derivatives
# (atoh, exp, the uptake distribution) flow through. Grasses take the transmitted forest-floor light.
function _patch_fpars(trees::AbstractVector{TreePools{T}}, allom::Allometry.TreeAllometry; nlayers::Int = 60, vstep = 2.0, k_lambert = 0.5) where {T}
    vs = T(vstep); kl = T(k_lambert)
    n = length(trees)
    fpars = zeros(T, n)
    # per-tree leaf-area-per-height (atoh) and bole/top heights; grass excluded from the tree canopy
    atoh = zeros(T, n); top = zeros(T, n); bole = zeros(T, n); istree = falses(n)
    for i in 1:n
        t = trees[i]
        (t.is_grass || t.height <= 0 || t.leaf_c <= 0) && continue
        istree[i] = true
        top[i] = t.height
        bole[i] = (one(T) - allom.crownlength) * t.height
        cd = max(t.height - bole[i], T(1.0e-6))
        atoh[i] = min(t.leaf_c * t.sla / cd, T(40.0)) * t.nind        # leaf area density × nind (patch basis)
    end
    plai = zero(T); fpar_bottom = one(T)
    for layer in (nlayers - 1):-1:0
        lowb = layer * vs; highb = lowb + vs
        fpar_top = fpar_bottom
        plai_layer = zero(T)
        la = zeros(T, n)
        for i in 1:n
            if istree[i] && top[i] > lowb && bole[i] < highb && (top[i] - bole[i]) > T(1.0e-6)
                frac = one(T)
                top[i] < highb && (frac -= (highb - top[i]) / vs)
                bole[i] > lowb && (frac -= (bole[i] - lowb) / vs)
                la[i] = atoh[i] * frac * vs
                plai_layer += la[i]
            end
        end
        plai += plai_layer
        fpar_bottom = exp(-kl * plai)
        uptake = fpar_top - fpar_bottom
        if plai_layer > T(1.0e-12)
            for i in 1:n
                fpars[i] += uptake * la[i] / plai_layer
            end
        end
    end
    # grasses: transmitted forest-floor light × their own Beer–Lambert absorption
    for i in 1:n
        t = trees[i]
        if t.is_grass && t.leaf_c > 0
            lai_g = t.crownarea > 0 ? t.leaf_c * t.sla / t.crownarea : zero(T)
            fpars[i] = fpar_bottom * (one(T) - exp(-convert(T, allom.k_beer) * lai_g))
        end
    end
    return fpars
end

"""
    individual_from_pools(tmpl::Individual, tree::TreePools, allom, fpar) -> Individual

Build the daily-canopy [`Individual`](@ref) from prognostic [`TreePools`](@ref): recompute `lai =
leaf_c·sla/crownarea` (`lai_tree.c`) and `fpc = crownarea·nind·(1−e^{−k·lai})` (`fpc_tree.c`), carry the
pools into `c_sapwood`/`c_root`, and reuse the PFT constants from the template individual `tmpl`. `fpar`
is the (recomputed) layered absorbed-PAR fraction from [`_patch_fpars`](@ref).
"""
function individual_from_pools(tmpl::Individual{T}, tree::TreePools{T}, allom::Allometry.TreeAllometry, fpar::T) where {T}
    ca = tree.crownarea
    laival = (tree.leaf_c > 0 && ca > 0) ? tree.leaf_c * tree.sla / ca : zero(T)
    fpc_i = ca > 0 ? ca * tree.nind * (one(T) - exp(-convert(T, allom.k_beer) * laival)) : zero(T)
    return Individual{T}(
        fpar, fpc_i, tmpl.alphaa, tmpl.albedo_leaf, tmpl.emax, tree.sapwood_c, tree.root_c, laival,
        tmpl.intc, tmpl.albedo_stem, tmpl.albedo_litter, tmpl.snowcanopyfrac, tree.nind,
        tmpl.photo, tmpl.tstress, tree.is_grass,
    )
end

"""
    rollout_canopy_years(p, alloc, allom, st0, trees0, tmpls, soil, yearly_forcings;
                         phen_params=nothing, nlayers=60, n_top1m=3) -> (trees, st, pools_by_year, annual)

Multi-year COUPLED rollout of one patch canopy: for each year, (1) recompute per-individual layered
`fpar` from the current [`TreePools`](@ref) heights ([`_patch_fpars`](@ref)); (2) build the daily
[`Individual`](@ref)s ([`individual_from_pools`](@ref)); (3) run the differentiable daily canopy
([`rollout_daily_canopy`](@ref)) accumulating each individual's per-m² `bm_inc = Σ npp_ind` and the
annual-mean stand water scalar; (4) GROW each tree ([`grow_individual`](@ref)) from its per-individual
`bm_inc/nind`. This is the flux-then-integrate S↔F loop (DESIGN §8) with the allocation as the carbon
handoff. Soil water carries across years (continuous); GSI phenology cold-starts each year (v1). Returns
the final `TreePools`, final soil state, the per-year pools trajectory, and per-year cell aggregates
`(gpp, npp, agb, vegc, mean_height, wscal_mean)` (per-m²/m).

`bm_inc_ext` (optional; a per-year vector of per-individual per-m² `bm_inc`) overrides the self-computed
`Σ npp_ind` — a kernel-isolation crutch (as sessions 5–7 used for the FAPAR/PET C-outputs) that isolates
the allocation/structure growth from F_diff's self-computed canopy NPP, which currently over-respires
(pre-existing, un-gated; see docs §12). Calibrating the self-NPP (removing this crutch) is the follow-up.
"""
function rollout_canopy_years(
        p::FDiffParams, alloc::AllocParams, allom::Allometry.TreeAllometry, st0::FDiffStateML,
        trees0::AbstractVector{TreePools{T}}, tmpls::AbstractVector{Individual{T}}, soil::SoilColumn,
        yearly_forcings; phen_params = nothing, nlayers::Int = 60, n_top1m::Int = 3, bm_inc_ext = nothing
    ) where {T}
    trees = collect(trees0)
    st = st0
    n = length(trees)
    pools_by_year = Vector{Vector{TreePools{T}}}()
    annual = NamedTuple[]
    for (yr, forc) in enumerate(yearly_forcings)
        fpars = _patch_fpars(trees, allom; nlayers = nlayers)
        inds = Individual{T}[individual_from_pools(tmpls[i], trees[i], allom, fpars[i]) for i in 1:n]
        (st, days) = rollout_daily_canopy(p, st, inds, soil, forc; phen_params = phen_params, n_top1m = n_top1m)
        bm_perm2 = zeros(T, n)
        gpp_yr = zero(T); npp_yr = zero(T); wsum = zero(T)
        for d in days
            for i in 1:n
                bm_perm2[i] += d.npp_ind[i]
            end
            gpp_yr += d.gpp; npp_yr += d.npp; wsum += d.wscal
        end
        wscal_mean = wsum / length(days)
        # `bm_inc_ext` (optional per-year, per-individual per-m² bm_inc) OVERRIDES the self-computed
        # Σ npp_ind — the same kernel-isolation "crutch" methodology sessions 5–7 used for the FAPAR/PET
        # C-outputs. It isolates the ALLOCATION (structure growth) from F_diff's self-computed canopy NPP,
        # which currently over-respires (a pre-existing, un-gated leaf-respiration aggregation issue that
        # the per-m² maintenance fix only partly closed — see docs §12). Removing this crutch (calibrating
        # the self-NPP to the C's ~512 gC/m²/yr) is the immediate follow-up before fully self-driven coupling.
        bm_year = bm_inc_ext === nothing ? bm_perm2 : convert.(T, bm_inc_ext[yr])
        newtrees = Vector{TreePools{T}}(undef, n)
        for i in 1:n
            tr = trees[i]
            bm_ind = bm_year[i] / (tr.nind + T(1.0e-12))
            newtrees[i] = grow_individual(alloc, allom, tr, bm_ind, wscal_mean)
        end
        agb = sum(agb_ind(newtrees[i]) * newtrees[i].nind for i in 1:n)
        vegc = sum(vegc_ind(newtrees[i]) * newtrees[i].nind for i in 1:n)
        htree = [newtrees[i].height for i in 1:n if !newtrees[i].is_grass && newtrees[i].height > 0]
        push!(
            annual, (
                gpp = gpp_yr, npp = npp_yr, bm_inc = npp_yr, agb = agb, vegc = vegc,
                mean_height = isempty(htree) ? zero(T) : sum(htree) / length(htree), wscal_mean = wscal_mean,
            )
        )
        push!(pools_by_year, newtrees)
        trees = newtrees
    end
    return (trees, st, pools_by_year, annual)
end

end # module FDiff
