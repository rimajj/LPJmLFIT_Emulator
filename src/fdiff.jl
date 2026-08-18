# ── F_diff — the differentiable fast physical core (ADR 0014) ────────────────────────────────────
# The daily CONTINUOUS biophysics of LPJmL-FIT, reimplemented in AD-friendly Julia with the SAME
# equations: photosynthesis→GPP→NPP (C3/C4, Haxeltine & Prentice 1996), the λ (ci:ca) supply/demand
# solve, Priestley–Taylor PET/ET, a soil-water bucket + snow, and maintenance/growth respiration.
# Physics constants are the LPJmL-FIT C-source values (the F1 binary is the numerical-regression
# oracle; the NeuralCrop *crop* constants differ and are NOT used). Ported per ADR 0015 from
# LPJmL-hybrid-photosynthesis (MIT — photosynthesis kernel + differentiable λ pattern), cross-checked
# against the LPJmL-FIT C source. NeuralCrop.jl is cited as a METHOD reference only for the PET/ET/
# respiration formulations and the daily-rollout idiom — it is CC BY-NC, which cannot combine with this
# repo's AGPL-3.0-or-later outbound licence, so no code is taken from it (ADR 0080 §2/§3).
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
    PhenParams, PhenState, phenology_gsi_step, tebs_phenparams, pft_phenparams, per_pft_phenology,
    petpar_daylength, patch_albedo,
    AllocParams, TreePools, tebs_allocparams, grow_individual, individual_from_pools, rollout_canopy_years,
    rollout_canopy_years_gpp,
    betaroot_from_d95max, jackson_rootdist, per_tree_rootdists, individuals_from_pools, # ADR 0110
    grass_allocparams, grass_treepools, grow_grass_individual,
    pft_respparams, pft_tempstressparams, pft_allocparams, pft_allometry, # ADR 0126
    pft_canopy_traits, PFTPhys, pft_phys,
    GrassEstabParams, grass_estabparams,
    agb_ind, vegc_ind,
    FluxHooks

# ── unit helpers (LPJmL-FIT include/units.h; 273.15 K — NOT the reference's 272.15 bug) ──────────
ppm2bar(co2) = co2 * 1.0e-6          # ppmv → bar  (units.h:23)
ppm2Pa(co2) = co2 * 1.0e-1          # ppmv → Pa   (units.h:24; assumes p = 1e5 Pa)
hour2sec(h) = h * 3600              # h → s
hour2day(h) = h / 24                # h → day-fraction
degCtoK(t) = t + 273.15            # °C → K  (units.h:22 — 273.15 exactly)

# ── NN hooks (hybrid ML corrections) — dependency-free injection points (scale-up step 7b) ───────
# Optional LEARNED multiplicative corrections to the two photosynthesis levers the hybrid trains:
# Vcmax (`vm`) and the ci:ca ratio λ (the gradient-based online-rollout-training milestone; ADR 0016).
# Each field is either `nothing` (pure physics — the identity fast path, so EVERY regression baseline
# is byte-identical) or a callable `feat -> scale` mapping the day's driver feature vector to a
# positive multiplicative scale (≈ 1). The FEATURE VECTOR handed to a hook is, in fixed order,
# `T[temp_°C, swdown, daylength_h, apar, w_soil, co2_ppm]` (the drivers in scope at the photosynthesis
# call in [`daily_step`](@ref)); the learned model (a Lux MLP built in the `FDiffTrainingExt` package
# extension) owns its OWN input normalization. `vm` scales Vcmax — and hence, consistently, the
# potential conductance and leaf respiration that derive from it; `λ` scales the solved ci:ca ratio,
# re-clamped to the physical bracket [`_LAMBDA_LO`, `_LAMBDA_HI`]. The runtime stays dependency-free:
# `FDiff` only ever *calls* the hook (a plain function); `Lux`/`Zygote`/`Optimisers` live in the
# extension + the test env, never in `src/`.
"""
    FluxHooks(; vm=nothing, λ=nothing)

Optional learned multiplicative corrections to the Vcmax (`vm`) and ci:ca-ratio (`λ`) levers of the
photosynthesis kernel. Each is `nothing` (pure physics; identity fast path) or a callable
`feat -> scale` (`feat` = `[temp, swdown, daylength, apar, w_soil, co2]`, `scale ≈ 1`). Threaded through
[`daily_step`](@ref) / [`rollout`](@ref) / [`annual_npp`](@ref); the default [`_NO_HOOKS`](@ref) leaves
the physics untouched. Build the learned hooks with the `FDiffTrainingExt` extension (needs `Lux`).
"""
struct FluxHooks{V, L}
    vm::V
    λ::L
end
FluxHooks(; vm = nothing, λ = nothing) = FluxHooks(vm, λ)

"The no-op hooks (pure physics) — the default everywhere; skips feature construction entirely."
const _NO_HOOKS = FluxHooks(nothing, nothing)

@inline _has_hooks(::FluxHooks{Nothing, Nothing}) = false
@inline _has_hooks(::FluxHooks) = true

# Physical bracket for the ci:ca ratio λ (water_stressed.c; λmax = 0.8 < 0.85). Shared by the λ Newton
# solve ([`solve_lambda`](@ref)) and the learned-λ hook clamp so both confine λ to the same interval.
const _LAMBDA_LO = 0.02
const _LAMBDA_HI = 0.85

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
    # §26 grass photosynthesis DEMAND-GATE (default off ⇒ byte-identical). The C skips grass
    # photosynthesis entirely when the canopy demand is below threshold (`water_stressed.c:196`
    # `if(gpd>1e-5)` ⇒ `agd=0`, no leaf respiration), so a deep-shade grass makes ~zero NET carbon —
    # its `mresp` is ALREADY phen-scaled (`autotrophic_respiration`, matching `npp_grass.c`'s
    # `mresp·phen`), so a leaf-off grass barely respires. F_diff's shared softplus `βflux` instead keeps a
    # light-insensitive ~log(2)/50 = 0.0139 gC/m²/day (≈2.9 gC/m²/yr) GPP floor at ~zero forest-floor
    # demand (the deep-shade grass overshoot, docs §24-26). REFUTED §25 lever: a large grass-only `βflux`
    # ("hard floor" `max(0,agd)`) drives deep-shade grass NPP strongly NEGATIVE — flooring the DEMAND
    # `gpd→0` collapses `fac`, so the fixed-graph λ-solve returns a degenerate low λ that suppresses `agd`
    # while `rd` stays normal ⇒ `agd−rd ≪ 0` (docs §26 co-calibration probe). The faithful fix is this
    # smooth sigmoid gate on the pre-floor demand `gpd`, which zeroes BOTH grass GPP and `rd` as demand→0
    # while the λ-solve keeps the bounded soft-`βflux` `fac` (no degeneracy). Grass-gated ⇒ the VALIDATED
    # tree path (decadal GPP ×1.066, §21) is byte-identical.
    grass_demand_gate::Bool = false
    βgpd_gate::T = 2.0e4     # sigmoid sharpness of the demand gate (in `gpd` units, ≈ 1/threshold)
    gpd_gate::T = 1.0e-5     # C demand threshold (`water_stressed.c:196` `gpd>1e-5`)
    # ── THE SAME GATE FOR TREES (ADR 0131; default off ⇒ byte-identical) ─────────────────────────
    # `water_stressed.c:196`'s gate is NOT grass-specific: it is per-`Pft`, and in this configuration
    # (`individual:true`) every TREE is its own `Pft` entry, so the C applies it per individual tree too.
    # `water_stressed.c:83` zeroes `*rd` on entry and the `else` branch at `:260` sets `agd=0`, so on a
    # gated day the C's tree contributes NEITHER gross assimilation NOR leaf respiration. F_diff has
    # always run the tree path ungated (the `grass_demand_gate` above is `ind.is_grass`-gated), which is
    # the "`rd` is not conductance-gated on rare water-stress-collapse days" v1 simplification recorded in
    # `docs/notes/phase3_fdiff_cbinary_validation.md` §13 and `sapwood_bg_design.md` §1/§6. The gate closes
    # when the canopy's own demand `gpd = hour2sec(dl)·(gc·fpc − gmin·fpar)` collapses — i.e. when supply
    # falls far below demand (`canopy_conductance` drives `gc→0`) — so it fires on DROUGHT days, not on
    # leaf-off days (where `apar→0` already takes `vm`, and hence `rd = b·vm`, to ~0 smoothly; F has no
    # `isphoto(tstress)` branch because `tstress` multiplies `c1`/`c1o` linearly, so that HALF of the C's
    # gate is already emulated). The other half is not, and F pays `rd` with a collapsed `agd` on those
    # days ⇒ it biases tree NPP DOWN and tree GPP UP (the `βflux` softplus floor).
    # ⚠ The `isphoto` half above is no longer a structural argument — it is MEASURED and CLOSED
    # (ADR 0138). `agd`/`rd`/`vm` are exactly proportional to `tstress` (verified against this kernel to
    # 1.6e-9), so the C's `tstress<1e-2` branch discards at most 1 % of that day's full-suitability value;
    # and `k3 = ln(99)/(temp_co2_high − temp_photos_high)` makes the threshold coincide with the
    # `temp ≥ temp_co2_high` hard cutoff `gate_co2` already carries, so only the COLD end is live (below
    # −6 °C for every tree but the tropical evergreen, which is +3 °C). Assimilation-weighted, that is
    # 0.046 % of the annual total at `boreal_siberia` — where 47 % of DAYS are gated — and 0 at three of
    # the five biome cells, whose temperature never reaches the threshold. Not portable, not a flag:
    # 65× below the residual it was shortlisted to explain. Scorer: `diagnose_tstress_photo_gate.py`.
    # ⚠ SIGN: switching this ON therefore RAISES F's CUE (already high) and LOWERS F's GPP (already high) —
    # it is a faithfulness fix that moves the two channels of ADR 0129/0130's split in OPPOSITE directions.
    # Measured per cell in ADR 0131; do not assume it helps.
    # ⚠ SCOPE: like `grass_demand_gate`, this flag is honoured ONLY on the multi-individual canopy path
    # [`daily_step_canopy`](@ref) — which is the one `FDiffFastCore` and the coupled driver run. The
    # single-individual `daily_step` / `daily_step_ml` kernels (`fdiff.jl:774`/`:1217`) apply neither gate
    # and are byte-identical with either flag set.
    # ⚠ `βgpd_gate` is SHARED with the grass gate, and `_with_grass_gate` pins it to the C's hard-step
    # `1e8` whenever the grass gate is switched on (which `FDiffFastCore` does by default) — so in the
    # coupled core this gate runs at the sharp step, and standalone with `grass_demand_gate=false` it runs
    # at the soft `2e4`. Keep it OFF on the Enzyme/`rollout_canopy_years_gpp` path: a 1e8 sigmoid is
    # gradient-hostile, and that path reads `p.water` directly with no reconstruction.
    tree_demand_gate::Bool = true
    # ── C-FAITHFUL LEAF-ON WATER SCALAR (ADR 0051; default off ⇒ byte-identical) ────────────────
    # `wscal` is NOT the realized supply/demand ratio in the C — it is a *potential*, phenology-INDEPENDENT
    # soil-water-supply index (`water_stressed.c:130-138`):
    #     wscal = (eeq>0 && gp_stand_leafon>0 && fpc>0) ?
    #             min(1, emax·wr / (eeq·ALPHAM/(1 + GM·ALPHAM/gp_stand_leafon))) : 1
    # Three differences from the `sup_acc/dem_acc` form F_diff used through ADR 0050, ALL biasing the
    # annual mean the same way: (1) the C numerator is `emax·wr` with **no `phen`**, while F_diff's
    # `sup_acc = Σ emax·wr·φ·fpc·φ` carries `phen` SQUARED (once via `supply_i`, once via `fpc_i`);
    # (2) the C denominator uses `gp_stand_leafon` — the conductance at FULL leaf cover, FPC-normalized by
    # the **plain** `Σfpc` (`gp_sum.c:57-67`) — not the actual phen-weighted `gp_stand`, and omits the
    # `(1−wet)` wet-canopy reduction; (3) on a no-demand day the C sets `wscal = 1` (UNSTRESSED), whereas
    # `sup_acc/(dem_acc+1e-9)` degenerates to **0** (maximal stress) because supply vanishes faster than
    # demand as `φ→0`. Consequence at Hainich: every leaf-off day scored as fully water-stressed, giving an
    # annual `1−wscal_mean` of 0.323–0.331 against a C truth of [0, 0.0432] (ADR 0034 §1 / ADR 0051).
    # This matters TWICE: `wscal_mean` is both Component S's `water_stress` conditioning feature AND the
    # F-core's leaf:root allocation driver `lmtorm` (`allocation_tree.c:233` uses the same accumulator).
    # DEFAULT FLIPPED TO `true` 2026-08-06 (ADR 0059). It shipped opt-in under guardrail 4 while ADR 0051
    # measured it, and then sat off for a week with each line recording the flip as the other's to
    # schedule — the "opt-in whose default is known wrong" case CLAUDE.md §6 guardrail 4's corollary names.
    # Line S gave an explicit GO (its own gate now admits both states, so no synchronised two-sided commit
    # is needed) and endorsed it on M's measurement: Hainich's annual `water_stress` goes 0.3050 → 0.0034
    # against a C truth of 0.0014 and a trained band of [0, 0.04315], i.e. the flip closes S's last
    # out-of-band conditioning column rather than merely being more faithful. Guardrail 4 is now served by
    # the OPT-OUT — `wscal_leafon = false` reproduces the pre-ADR-0051 expression exactly.
    wscal_leafon::Bool = true
    # ── THE TWO REMAINING `gp_sum` BASIS DIFFERENCES (ADR 0136; both default off ⇒ byte-identical) ──
    # ADR 0051's "Consequences" section registered these two as a separate opt-in change with their own
    # re-measure, and they stayed unmeasured for two weeks. Both live in `gp_sum.c:36-68`, the pass that
    # sets `pft->vmax` and returns the stand-mean potential conductance, and both act ONLY on
    # partial-leaf days (`phen < 1`); at `phen ≡ 1` each is an exact identity, which is how they are
    # unit-tested.
    #
    # (1) `gp_stand_leafon_basis` — the C computes each PFT's `gp` at FULL leaf cover (`apar ∝ pft->fpc`,
    #     **no `phen`**, and `gmin·pft->fpc` likewise), then accumulates `gp_stand += gp·pft->phen` and
    #     normalizes by the **plain** `Σ pft->fpc` (`gp_sum.c:57-67`). F_diff folds `φ` into the pass-1
    #     `apar` and into `gmin`, and divides by the **phen-weighted** `Σ fpc·φ`. If `adtmm` were exactly
    #     linear in `apar` the numerators would agree and the ratio would be `1/φ̄`, i.e. F_diff's
    #     `gp_stand` is BIASED HIGH on any partial-leaf day ⇒ larger `demand`, larger `gc`, larger `gpd`,
    #     larger `fac`, higher solved `λ`, more GPP. Turning this on uses the C's own numerator
    #     `Σ gp_leafon·φ` over `Σ fpc` — both of which F_diff already accumulates for `wscal_leafon`.
    # (2) `lambda_vm_gp` — the C's λ bisection runs `photosynthesis(..., compvm=FALSE)` with
    #     `data.vmax = pft->vmax` **as left by `gp_sum`**, i.e. a Vcmax computed at the crown-cover,
    #     no-phen `apar` (`water_stressed.c:204`), while its `data.apar` (and hence `je`) is the layered,
    #     phen-scaled absorption. F_diff recomputes `vm` at the layered `apar` and uses that in the
    #     residual. The C's FINAL call recomputes Vcmax at the layered `apar` on both sides
    #     (`compvm=TRUE`, `water_stressed.c:206`), and Vcmax does not depend on λ, so **only the solved λ
    #     differs — not the Vcmax the reported `agd`/`rd` are computed with**. Since `apar_leafon ≥ apar`
    #     the C's residual generally carries the LARGER `vm` ⇒ larger `adtmm(λ)` ⇒ the root of
    #     `fac·(1−λ) − adtmm(λ)` moves DOWN ⇒ less GPP. ⚠ That sign is conditional, not structural:
    #     `∂adt/∂vm ∝ c2·∂agd/∂jc − b`, so it inverts wherever the individual is Rubisco-saturated
    #     (`∂agd/∂jc < b/c2`). Do not state it as signed without the measurement (ADR 0131's lesson).
    # ⚠ SCOPE: like the two demand gates, both are honoured ONLY on the multi-individual canopy path
    # [`daily_step_canopy`](@ref) — the one `FDiffFastCore` and the coupled driver run. The
    # single-individual `daily_step` / `daily_step_ml` kernels are byte-identical with either flag set.
    # ⚠ (1) IS NOW ON BY DEFAULT (ADR 0137, 2026-08-13) — this is the C-faithful basis, and on the
    # shipping configuration it improves every biome cell and all four aggregates (4-cell mean
    # `|GPP_F/GPP_C − 1|` 0.0824 → 0.0328). Guardrail 4 is served by the OPT-OUT:
    # `gp_stand_leafon_basis = false` reproduces the pre-ADR-0136 expression exactly, and the arms that
    # mean the old basis all say so explicitly. A first flip attempt was reverted on 2026-08-13 because
    # its blast radius — **23 assertions of 275 621** across EIGHT test files, against 3-5 for each of the
    # previous four flips — was not enumerated and one casualty (`slow_level_anchor_tests.jl:181`) is a
    # line-S-owned gate; S gave an explicit GO before this landed. See `logs/M-flip0137.1775524.out`.
    gp_stand_leafon_basis::Bool = true
    lambda_vm_gp::Bool = false
    # ── ADR 0110: PER-TREE ROOT PROFILES AND PER-TREE WATER STATUS ──────────────────────────────────
    # Off ⇒ every individual shares one cell-average root profile collapsed to one scalar `wr`, so two
    # trees differing only in rooting depth are identical in the water balance and drought response
    # cannot exist. On ⇒ each individual with a rooting trait (`TreePools.d95max > 0`, carried into
    # the `rootdists` argument built by `per_tree_rootdists`) gets its own root-weighted moisture, its own
    # supply, its own water scalar, and withdraws down its own profile.
    #
    # This is a FAITHFUL port, not an approximation: the C's per-individual `wr`, `supply` and
    # `pft->wscal` are all **order-INDEPENDENT** (`soil.w[]` is frozen for the whole permuted loop and
    # written once per patch-day afterwards in `soil/waterbalance.c:117-138`), so the `-DPERMUTE` daily
    # depletion-order randomness that blocks a faithful `aet_cor` port does NOT touch any of them.
    # See ADR 0110 §3 for the full order-dependence table.
    per_tree_roots::Bool = false
    # The C's ORDER-FREE first cap (`lpj/water_stressed.c:159-161`): no individual may draw more from a
    # layer than its own FPC share of that layer's available water. Depends only on the individual and
    # the frozen `soil.w[]`, and fires routinely in summer once the top layer drops below ~0.4 — it is
    # NOT the order-dependent residue cap (`:162-166`), which stays out of scope (ADR 0110 §5).
    # Only active together with `per_tree_roots`.
    #
    # ⚠ SCOPED LIMITATION: the C also feeds the capped supply BACK into the GPP solve (it overwrites
    # `supply` at `:177` and re-solves `gc`), which would need a second pass over the individuals. That
    # feedback is order-free and portable, but is NOT implemented here — Phase 1 applies cap (i) to the
    # WITHDRAWAL (mass balance) only. This is deliberate and costs nothing for the drought-mortality
    # channel, because the C's own `pft->wscal` is built from the UNCORRECTED supply (`:130-140`).
    per_tree_fpc_cap::Bool = true
    # ADR 0110 Phase 2: switch on the two climate-driven death risks ADR 0049 §3 set to ZERO for want of a
    # per-tree water status. ⚠ ADR 0244 flipped this default `false → true` and corrected what it requires:
    #
    #   * the TEMPERATURE integral (`mort_temp`) needs NOTHING but the day's air temperature and the PFT's
    #     own `temp_stressed` interval (`tempstress_tree.c:29`), so it is live under this flag ALONE — and
    #     it is EXACT: recomputed on the C's own reset window it reproduces the C's own emitted
    #     `temp_stress` at 4 334 of 4 334 (cell, year, PFT) groups, integer for integer (ADR 0244 §3).
    #   * the WATER integral (`mort_water`) still needs `per_tree_roots` for a per-individual daily
    #     `wscal`; with that off `water_stress_acc` stays identically 0 and `mort_water` with it. That half
    #     is deliberately still off by default — its runtime cost is unmeasured (speed is goal #2) and
    #     ADR 0110 §6's step-2 flip criteria have never been measured.
    #
    # ⚠ The specific-humidity caveat below binds only on the WATER branch (VPD is read nowhere else), so it
    # does not bind at this default: needs a REAL `DailyForcing.humid` / `AtmForcing.qair`, since the
    # default 0 reads as bone-dry air and inflates VPD. See `getvpd`.
    #
    # Opt OUT with `trait_drought_mortality = false` to reproduce the pre-ADR-0244 hazard exactly (both
    # integrals zero), which is what every control arm that MEANS the old basis now states explicitly
    # rather than taking by omission (ADR 0136 §7's lesson).
    trait_drought_mortality::Bool = true
end

"""
    RespParams{T}

Autotrophic-respiration constants (Lloyd–Taylor `gtemp`, LPJmL-FIT `npp_tree.c`; Sitch et al. 2003).
Tissue maintenance respiration is `respcoeff·k·(C_tissue/CN_tissue)·gtemp(temp)` over sapwood and
fine root, using **tissue-specific C:N ratios** (wood N-poor, `CN_sapwood≈330`; fine root N-rich,
`CN_root≈29`) — a single leaf-like N:C over-respires the large woody pool. Faithful to `npp_tree.c:51`,
the **fine-root term is PHEN-GATED** (roots respire only while leaves are displayed; the sapwood term
runs year-round). `k` is the maintenance rate per unit tissue N (gC gN⁻¹ day⁻¹). Growth respiration is
`r_growth·max(0, GPP − Rleaf − Rmaint)` (`npp_tree.c:52`), the `max(0,·)` floor sharpened by `βgrowth`.
`βgate` smooths the low-T cutoff.
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
    βgrowth::T = 50.0        # sharpness of the growth-resp `max(0,·)` floor (npp_tree.c:52 hard branch)
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
    humid::T = 0.0                # SPECIFIC humidity, kg/kg (the C's `climate->humid` under
    # `"relative_humidity": false`). Already the 7th column (`huss`) of every
    # committed forcing fixture — it simply never reached this struct. Consumed
    # ONLY by [`getvpd`](@ref) for the ADR-0110 drought-stress accumulator, which
    # is opt-in, so the default 0 changes nothing (every existing kwarg call site
    # is byte-identical). ⚠ 0 means "unknown", and `getvpd` reads it as bone-dry
    # air ⇒ maximal VPD — never enable the drought hazard on unset humidity.
end

"""
    getvpd(temp, humid) -> vpd (Pa)

Port of the C's `spitfire/getvpd.c` on the `relative_humidity = false` branch — which is the one this
configuration takes (`lpjmlfit.js:51`). Saturation vapour pressure by **Goff–Gratch**, then

```
rh  = 0.263 · 1013.25 · humid / exp(17.67·T_C / (T_K − 29.65))      (capped at 1)
vpd = 10^Z · (1 − rh) · 101324.6
```

with `T_K = T_C + 273.16` (the C's own constant — note it is 273.16, not 273.15) and `humid` the
**specific** humidity in kg/kg. Used by the ADR-0110 drought-stress accumulator, which divides it by
1000 (`tree/waterstress_tree.c:34`).

⚠ `humid = 0` (the [`DailyForcing`](@ref) default, meaning "not supplied") yields `rh = 0` ⇒ the largest
possible VPD. That is deliberately loud rather than silently mild: never run the drought hazard on a
forcing whose humidity was never plumbed through.
"""
function getvpd(temp::Real, humid::Real)
    T = float(promote_type(typeof(temp), typeof(humid)))
    Ts = T(373.16)
    tk = T(temp) + T(273.16)
    Z = T(-7.90298) * (Ts / tk - one(T)) +
        T(5.02808) * log(Ts / tk) / log(T(10)) +
        T(-1.3816e-7) * (T(10)^(T(11.344)^(one(T) - tk / Ts)) - one(T)) +
        T(8.1328e-3) * (T(10)^(-(T(3.49149)^(Ts / tk - one(T)))) - one(T))
    rh = T(0.263) * T(1013.25) * T(humid) / exp(T(17.67) * T(temp) / (tk - T(29.65)))
    rh > one(T) && (rh = one(T))
    return T(10)^Z * (one(T) - rh) * T(101324.6)
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
    photosynthesis(p::PhotoParams, λ, tstress, co2_Pa, temp, apar, daylength; comp_vm=true, vm=0, kin=photo_kinetics(p, temp)) -> (agd, rd, vm, adtmm)

Daily photosynthesis (`photosynthesis.c:36-166`), returning gross daytime assimilation `agd`
(gC/m²/day), leaf respiration `rd` (gC/m²/day), Vcmax `vm`, and the CO₂-flux form `adtmm`
(mm/m²/day) used in the λ residual. `comp_vm=true` computes `vm` at the optimal λ (the C `gp_sum`
pass); `comp_vm=false` uses the passed-in `vm` (the λ-solve residual pass). `kin` carries the
temperature-only Michaelis-Menten kinetics `(fac_kin, gammastar)`; its default recomputes them, so a
caller looping at one temperature can hoist `photo_kinetics` out and pass the result unchanged (same
arithmetic, evaluated once). Non-smooth ops replaced
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

# Temperature-dependent Michaelis-Menten kinetics (`photosynthesis.c:66-70`), split out of
# `photosynthesis` so a caller that evaluates the kernel repeatedly at ONE temperature can hoist
# them out of its loop. `ko`/`kc`/`tau` depend on `temp` ALONE — not on λ, `apar`, `vm` or the
# individual — yet the λ solve re-evaluates them on each of its ~78 kernel calls per individual-day,
# which the profile attributes 26.5 % of total runtime to (ADR 0084 §5). Returns the only two derived
# quantities the kernel consumes, as a `Tuple` of scalars: stack-allocated, so this is NOT the
# heap-allocated-field-on-a-differentiated-struct shape that aborts the suite under Enzyme (ADR 0110).
@inline function photo_kinetics(p::PhotoParams, temp)
    ko = p.ko25 * p.q10ko^((temp - 25) * 0.1)
    kc = p.kc25 * p.q10kc^((temp - 25) * 0.1)
    fac_kin = kc * (one(temp) + p.po2 / ko)
    tau = p.tau25 * p.q10tau^((temp - 25) * 0.1)
    gammastar = p.po2 / (2 * tau)
    return (fac_kin, gammastar)
end

function photosynthesis(
        p::PhotoParams{T}, λ, tstress, co2_Pa, temp, apar, daylength;
        comp_vm::Bool = true, vm = zero(T), vm_scale = one(T),
        kin = photo_kinetics(p, temp)
    ) where {T}
    θ = p.theta
    # temperature-dependent kinetics (photosynthesis.c:66-70) — identical arithmetic whether computed
    # here by the default kwarg or hoisted by the caller and passed in (`photo_kinetics` above).
    fac_kin, gammastar = kin

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
            # `vm_scale` = the learned Vcmax correction (identity `1` when no NN hook; FluxHooks).
            vm = vm_scale * _sla_vm_cap(p, (1 / b) * (c1o / c2o) * ((2θ - 1) * s - (2θ * s - c2o) * σ) * apar * p.cmass * p.cq, temp)
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
            vm = vm_scale * _sla_vm_cap(p, (1 / b) * (c1o / c2o) * ((2θ - 1) * s - (2θ * s - c2o) * σ) * apar * p.cmass * p.cq, temp)
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
    lo = T(_LAMBDA_LO); hi = T(_LAMBDA_HI)
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
    autotrophic_respiration(p::RespParams, temp, gpp, rd, c_sapwood, c_root; phen=1.0) -> (npp, ra)

Net primary production `NPP = GPP − Ra`, `Ra = Rleaf + Rmaint + Rgrowth`. `Rmaint = respcoeff·k·
gtemp(temp)·(C_sap/CN_sap + phen·C_root/CN_root)` with the Lloyd–Taylor `gtemp = exp(e0·(1/(Tr+10) −
1/(temp+Tr)))` (low-T cutoff smoothed by a sigmoid, per NeuralCrop's AD-safe variant); the fine-root
term is **phen-gated** (`npp_tree.c:51`). `Rgrowth = r_growth·max(0, GPP − Rleaf − Rmaint)`
(`npp_tree.c:52`), the floor a SHARP softplus (`p.βgrowth`) — a soft β≈1 floor over-counts growth resp
for every carbon-negative individual/day, which aggregated over the multi-PFT canopy drives NPP strongly
negative. `rd` is the leaf respiration already returned by [`photosynthesis`](@ref).
"""
function autotrophic_respiration(p::RespParams, temp, gpp, rd, c_sapwood, c_root; phen = one(temp), c_sapwood_bg = zero(temp))
    gate = sigmoid(10 * (temp + 40))                       # smooth of temp ≥ −40 °C
    gtemp = gate * exp(p.e0 * (1 / (p.temp_response + 10) - 1 / (temp + p.temp_response)))
    # Aboveground sapwood maintenance runs year-round (gtemp_air, NO phen); the fine-root AND the
    # below-ground root-sapwood (`c_sapwood_bg`) terms are PHEN-GATED on the (proxied) soil-temperature
    # response (`npp_tree.c:51` `(root·nc_root + sapwood_bg·nc_sapwood)·…·gtemp_soil·phen`) — a deciduous
    # canopy stops respiring its below-ground pools when leaves are off. `gtemp_soil` is proxied by
    # `gtemp_air` (no soil-thermal model). `c_sapwood_bg` defaults to 0 ⇒ every caller without a seeded
    # below-ground sapwood pool is byte-identical; the pool respires at the N-poor sapwood C:N (`cn_sapwood`).
    rmaint = p.respcoeff * p.k * gtemp * (c_sapwood / p.cn_sapwood + phen * (c_root / p.cn_root + c_sapwood_bg / p.cn_sapwood))
    # Growth respiration only on POSITIVE net-of-maintenance carbon: `npp_tree.c:52`
    # `(assim<mresp) ? assim−mresp : (assim−mresp)·(1−r_growth)` ⇒ `rgrowth = r_growth·max(0, assim−mresp)`.
    # A SHARP softplus (βgrowth) — a soft β≈1 floor injects a spurious ~log(2) growth resp into every
    # carbon-negative individual/day and drives the aggregated canopy NPP strongly negative.
    rgrowth = p.r_growth * softplus(gpp - rd - rmaint, p.βgrowth)
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
# the C-binary validation (docs/notes/phase3_fdiff_cbinary_validation.md).
_apar(par, str::Structure, ::Nothing, fpar_internal) = par * (one(par) - str.albedo) * str.alphaa * fpar_internal
_apar(par, str::Structure, fapar::Real, fpar_internal) = par * str.alphaa * fapar

function daily_step(
        p::FDiffParams, st::FDiffState, str::Structure, f::DailyForcing;
        c_sapwood = 3000.0, c_root = 800.0, fapar = nothing, hooks::FluxHooks = _NO_HOOKS
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

    # --- NN hooks: learned multiplicative Vcmax / λ corrections (identity when no hook — see FluxHooks).
    # The feature vector is built ONCE per day and only when a hook is active (identity fast path skips
    # it entirely, so the physics — and every regression baseline — is byte-identical when hooks off).
    vm_scale = one(T)
    λ_scale = one(T)
    if _has_hooks(hooks)
        feat = T[f.temp, f.swdown, f.daylength, apar, st.w, f.co2]
        hooks.vm === nothing || (vm_scale = convert(T, hooks.vm(feat)))
        hooks.λ === nothing || (λ_scale = convert(T, hooks.λ(feat)))
    end

    # --- temperature stress + photosynthesis machinery ---
    ts = temp_stress(p.tstress, f.temp, f.daylength)
    co2_Pa = ppm2Pa(f.co2)
    # potential (unstressed) photosynthesis at λ_opt → Vcmax and potential conductance (Vcmax scaled by
    # the learned hook, which propagates consistently into `gp_pot`, the λ solve, `rd`, and GPP)
    (_, _, vm, adtmm_opt) = photosynthesis(p.photo, w.lambda_opt, ts, co2_Pa, f.temp, apar, f.daylength; comp_vm = true, vm_scale = vm_scale)
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
    # learned ci:ca correction (identity when no hook), re-clamped to the physical bracket
    λ = clamp(λ * λ_scale, T(_LAMBDA_LO), T(_LAMBDA_HI))
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
    # identity collapses to infil+snowfall−melt = rain+snowfall = precip (see docs/notes/phase3_fdiff_spike).
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
    (npp, _) = autotrophic_respiration(p.resp, f.temp, gpp, rd, c_sapwood, c_root; phen = str.phen)

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
        c_sapwoods = nothing, c_roots = nothing, hooks::FluxHooks = _NO_HOOKS
    )
    T = promote_type(_wt(p), _wt(st0), _wt(str), _wt(first(forcings)))
    st = FDiffState{T}(; w = convert(T, st0.w), snowpack = convert(T, st0.snowpack))
    npp = zero(T); gpp = zero(T); transp = zero(T); evap = zero(T); runoff = zero(T); precip = zero(T)
    for (i, f) in enumerate(forcings)
        fp = fapars === nothing ? nothing : fapars[i]        # per-day C FAPAR (or internal)
        cs = c_sapwoods === nothing ? c_sapwood : c_sapwoods[i]
        cr = c_roots === nothing ? c_root : c_roots[i]
        (st, fl) = daily_step(p, st, str, f; c_sapwood = cs, c_root = cr, fapar = fp, hooks = hooks)
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
        c_sapwoods = nothing, c_roots = nothing, hooks::FluxHooks = _NO_HOOKS
    )
    T = promote_type(_wt(p), _wt(st0), _wt(str), _wt(first(forcings)))
    st = FDiffState{T}(; w = convert(T, st0.w), snowpack = convert(T, st0.snowpack))
    days = Vector{typeof(daily_step(p, st, str, first(forcings); c_sapwood = c_sapwood, c_root = c_root)[2])}()
    sizehint!(days, length(forcings))
    for (i, f) in enumerate(forcings)
        fp = fapars === nothing ? nothing : fapars[i]
        cs = c_sapwoods === nothing ? c_sapwood : c_sapwoods[i]
        cr = c_roots === nothing ? c_root : c_roots[i]
        (st, fl) = daily_step(p, st, str, f; c_sapwood = cs, c_root = cr, fapar = fp, hooks = hooks)
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
# MULTI-LAYER SOIL WATER (scale-up step 2 — docs/notes/phase3_fdiff_cbinary_validation.md §7)
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
    soildepth::Vector{T}    # per-layer thickness, mm (retained for D95 rooting-depth diagnostics; see `stand_structure_tof`)
end

# ── PER-TREE ROOT PROFILES (ADR 0110) ────────────────────────────────────────────────────────────────
# The C gives every individual its OWN root profile — `pft->beta_root` is set per individual from that
# individual's own sampled `D95max` (`tree/new_tree.c:229-230`, always taken since `"isD95max": true`),
# and `getrootdist` is called per individual, every day. Component S already predicts and validates
# `D95max`; until ADR 0110 nothing consumed it and every individual shared one cell-average profile.
#
# ⚠ Both functions run ONCE PER YEAR (traits are immutable after establishment and size advances
# annually), so the daily loop — and the Enzyme reverse path through it — sees the resulting profile as a
# CONSTANT. Nothing here is on the differentiated path.

"""
    betaroot_from_d95max(d95max_cm, bottom_cm; xtol=1e-4, maxiter=60) -> β

Port of the C's `soil/getbetaroot.c`: solve `(1 − β^D95) / (1 − β^bottom) = 0.95` for the Jackson
profile parameter β by bisection on `[0, 0.9999]`. `d95max_cm` is the individual's sampled rooting-depth
trait and `bottom_cm` the soil column's full depth, both in **cm** (the C converts its mm `layerbound`
with `*0.1`). The C uses `xtol = 1e-4` and 20 iterations (`getbetaroot.c:19,38`); the default 60 here
converges to machine tolerance and is a strict refinement — β is only ever used to build a profile that
is then renormalized, so a tighter root is never less faithful.
"""
function betaroot_from_d95max(d95max::Real, bottom::Real; xtol = 1.0e-4, maxiter::Int = 60)
    T = float(promote_type(typeof(d95max), typeof(bottom)))
    d95 = T(d95max)
    bot = T(bottom)
    (d95 <= 0 || bot <= 0 || d95 >= bot) && return T(0.9999)   # degenerate ⇒ effectively uniform-to-bottom
    f(β) = (one(T) - β^d95) / (one(T) - β^bot) - T(0.95)
    lo, hi = T(1.0e-6), T(0.9999)
    flo = f(lo)
    for _ in 1:maxiter
        mid = (lo + hi) / 2
        fm = f(mid)
        if (fm < 0) == (flo < 0)
            lo, flo = mid, fm
        else
            hi = mid
        end
        (hi - lo) < xtol && break
    end
    return (lo + hi) / 2
end

"""
    jackson_rootdist(β, soildepth, rootdepth_mm) -> Vector

Port of the C's `lpj/getrootdist.c:27-47`: the Jackson et al. (1996) asymptotic root profile
`rootdist[l] ∝ β^(z_{l-1}/10) − β^(z_l/10)` (mm→cm via `/10`), **renormalized to the deepest layer this
individual actually reaches**. `rootdepth_mm` is the individual's realized rooting depth
(`tree/allocation_tree.c:152` `getrootdepth(height, k_root, logistic)`), which grows with the tree — so
small trees genuinely root shallower than large ones even at equal `D95max`.

Layers below `rootdepth` get exactly zero, and the profile sums to 1 over the reached layers. The C's
count `num_layer_new` is capped at `BOTTOMLAYER-1`, reproduced here as `length(soildepth)-1`, so the
deepest layer is never the normalization bottom.

⚠ A profile that does not sum to 1 is silently physical in F_diff — the water supply scales linearly
with `sum(rootdist)` (`_transpire_total`, and ADR 0050's gotcha). This function always returns a
normalized profile; the caller must not rescale it.
"""
function jackson_rootdist(β::Real, soildepth::AbstractVector, rootdepth::Real)
    T = float(promote_type(typeof(β), eltype(soildepth), typeof(rootdepth)))
    N = length(soildepth)
    rd = zeros(T, N)
    b = min(T(β), T(0.9999))                       # the C's `if (beta==1.000) beta = 0.9999`
    lb = cumsum(convert.(T, soildepth))            # layer LOWER boundaries, mm
    nmax = N - 1                                   # the C's BOTTOMLAYER-1 cap
    last = 0
    for l in 1:nmax
        convert(T, rootdepth) > lb[l] && (last = l)
    end
    last = max(last, 1)                            # a sapling still roots in layer 1
    total = one(T) - b^(lb[last] / 10)
    total <= zero(T) && (rd[1] = one(T); return rd)
    rd[1] = (one(T) - b^(lb[1] / 10)) / total
    for l in 2:last
        rd[l] = (b^(lb[l - 1] / 10) - b^(lb[l] / 10)) / total
    end
    return rd
end

"""
    per_tree_rootdists(pools, soil) -> Vector{Vector} | nothing

Build one root profile per individual from its own `TreePools.d95max` and its own current `height`, for
[`individual_from_pools`](@ref). Returns `nothing` when **no** individual carries a rooting trait
(`d95max <= 0`), which is the pre-ADR-0110 state and keeps the shared-profile path byte-identical.

Individuals without a trait (`d95max <= 0`, e.g. grass — the C's `grass/new_grass.c:40,42` gives grass a
fixed full-depth profile, and the C's `ind` writer zeroes tree fields on grass rows) get an empty profile
and fall back to the shared `soil.rootdist` in [`daily_step_canopy`](@ref).

Realized rooting depth follows the C's logistic root model (`tree/getrootdepth.c:34-35`,
`"root_model": "logistic"`): `S/(1 + exp(−k_root·S·h)·(S/h₀ − 1))·1000` mm with `S = 20`, `h₀ = 0.1`.
`k_root` is drawn per individual in the C; F_diff has no per-tree `k_root`, so `k_root_default` is used
for every tree — a documented simplification, NOT a faithful port of that second per-tree channel.
"""
function per_tree_rootdists(pools::AbstractVector, soil::SoilColumn{T}; k_root = 0.15) where {T}
    any(p -> getfield(p, :d95max) > 0, pools) || return nothing
    bottom_cm = sum(convert.(T, soil.soildepth)) / 10
    S = T(20)
    h0 = T(0.1)
    out = Vector{Vector{T}}(undef, length(pools))
    for (i, p) in enumerate(pools)
        d95 = convert(T, p.d95max)
        if d95 <= 0
            out[i] = T[]                                    # no trait ⇒ shared profile
            continue
        end
        h = max(convert(T, p.height), T(1.0e-6))
        rdepth = S / (one(T) + exp(-T(k_root) * S * h) * (S / h0 - one(T))) * 1000   # mm
        β = betaroot_from_d95max(d95, bottom_cm)
        out[i] = jackson_rootdist(β, soil.soildepth, rdepth)
    end
    return out
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

# ── C-faithful POTENTIAL leaf-on water scalar (`water_stressed.c:130-138`; ADR 0051) ────────────────
# The C's `pft->wscal` is NOT the realized supply/demand ratio — it asks "if this canopy were at FULL leaf
# cover, could the soil supply meet the evaporative demand?", so it carries no `phen`, no `(1−wet)`, and
# equals 1 (unstressed) whenever there is no demand at all. Per-PFT there, the only PFT-dependent term is
# `pft->emax` (`wr` and `gp_stand_leafon` are stand-level once F_diff's shared community root profile is
# used, ADR 0050), so this evaluates the C expression per individual and returns the **fpc-weighted** mean
# of the capped values. That weighting is the one used throughout `daily_step_canopy`; the training column
# aggregates the C's per-individual `wscal_mean` UNWEIGHTED over living tree stems
# (`build_slow_runtime_table.py:424`), and the two coincide wherever the `min(...,1)` cap binds — which at
# Hainich is almost every day. `smoothmin` (not `min`) keeps the path AD-safe.
#
# ⚠ ADR 0110 UPDATES THE PARENTHETICAL ABOVE. "`wr` … stand-level once F_diff's shared community root
# profile is used (ADR 0050)" was true only while every individual shared one profile. With
# `per_tree_roots` on, `wr_ind[ii]` is THIS individual's own root-weighted moisture, so `wscal` becomes
# genuinely per-tree — which is the whole point: the C's `pft->wscal` is per-individual, it is
# ORDER-INDEPENDENT (built from the UNCORRECTED supply at `water_stressed.c:130-140`, before the
# permuted cap), and it is what `tree/waterstress_tree.c` integrates into the drought-death hazard.
# `out`, when given, receives the per-individual values for that hazard (Phase 2); the returned scalar
# is unchanged in meaning and byte-identical when `wr_ind === nothing`.
function _wscal_leafon(
        w::WaterParams{TW}, inds, eeq::TE, wr::TR, gp_leafon, fpc_plain;
        wr_ind = nothing, out = nothing,
    ) where {TW, TE, TR}
    T = promote_type(TW, TE, TR)
    # `water_stressed.c:130` — no demand ⇒ UNSTRESSED (this is the branch F_diff previously scored as 0)
    if eeq <= zero(eeq) || gp_leafon <= zero(gp_leafon) || fpc_plain <= zero(fpc_plain)
        out === nothing || fill!(out, one(T))
        return one(T)
    end
    demand_leafon = eeq * w.ALPHAM / (one(T) + w.GM * w.ALPHAM / gp_leafon)
    if demand_leafon <= zero(demand_leafon)
        out === nothing || fill!(out, one(T))
        return one(T)
    end
    acc = zero(T)
    wsum = zero(T)
    for (ii, ind) in enumerate(inds)
        fpc_i = convert(T, ind.fpc)
        wr_i = wr_ind === nothing ? wr : convert(T, wr_ind[ii])   # ADR 0110
        ws_i = smoothmin(one(T), convert(T, ind.emax) * wr_i / demand_leafon, w.βwscal)
        out === nothing || (out[ii] = ws_i)
        acc += ws_i * fpc_i
        wsum += fpc_i
    end
    return wsum > T(1.0e-20) ? acc / wsum : one(T)
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

    (npp, _) = autotrophic_respiration(p.resp, f.temp, gpp, rd, c_sapwood, c_root; phen = str.phen)

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
    hainich_soilcolumn(::Type{T}=Float64; whcs, rootdist, soildepth, soildepth_evap=300.0, soil_infil=2.0) -> SoilColumn{T}

Build a [`SoilColumn`](@ref) from per-layer plant-available capacities `whcs` (mm), root fractions
`rootdist`, and per-layer thicknesses `soildepth` (mm), computing the soil-evaporation layer weights
`frac_evap` from `soildepth_evap` (mm) and `soildepth`. `soildepth` is also retained on the column (for
the D95 rooting-depth diagnostic in `stand_structure_tof`). Used by the C-binary multi-layer validation
(the Hainich column is committed in `test/testitems/references/hainich_soilcolumn.txt`).
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
    return SoilColumn{T}(T.(whcs), T.(rootdist), frac_evap, T(soil_infil), T.(soildepth))
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
# SELF-COMPUTED RADIATION + PHENOLOGY (scale-up step 5 — docs/notes/phase3_fdiff_cbinary_validation.md §11)
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

GSI ("new phenology") leaf-phenology parameters (`src/lpj/phenology_gsi.c`; **`par/pft_lpjmlfit.js`** per
PFT — the ACTIVE FIT parameter file, `lpjmlfit.js:133 → param_lpjmlfit.js`, NOT the standard `par/pft.js`;
see [`pft_phenparams`](@ref)). Four limiting functions — cold-temperature `tmin`, heat-stress `tmax`,
`light`, water `wscal` — each a logistic `sigmoid(sl·(x−base))` low-passed toward the previous day by rate
`tau`; `phen` is their product. Defaults are the temperate broadleaved summergreen tree (beech, PFT id 3,
`par/pft_lpjmlfit.js:514-574`). `wscal_base` is the C's individual-mode water inflection `minwscal·100`
(`phenology_gsi.c:64-66` uses `pft->minwscal·100`, NOT the par-file `wscal.base`, when `config->individual`
— TRUE for this FIT run); beech `minwscal` median 0.2096 → 20.96. `soiltemp_gate`/`βgate` implement the C's
`soil→temp[0] < 10 °C ⇒ wscal factor forced open` rule (`phenology_gsi.c:67`), driven here by air
temperature (LPJmL uses air temp as the soil top boundary condition). `εfloor` is the C `max(epsilon, ·)`
factor floor.
"""
Base.@kwdef struct PhenParams{T <: Real}
    tmin_sl::T = 4.0               # beech: par/pft_lpjmlfit.js tmin slope (was 2.0 from the STANDARD pft.js)
    tmin_base::T = 8.5             # beech: par/pft_lpjmlfit.js tmin base  (was 8.0 from the STANDARD pft.js)
    tmin_tau::T = 0.2
    tmax_sl::T = 1.74
    tmax_base::T = 41.51
    tmax_tau::T = 0.2
    light_sl::T = 58.0
    light_base::T = 40.0
    light_tau::T = 0.2
    wscal_sl::T = 5.24
    wscal_base::T = 20.96          # = minwscal (0.2096) × 100 (individual-mode inflection)
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

# Per-individual leaf-display accessor: the canopy `phen` may be a single patch-wide scalar (every
# committed baseline + the Enzyme trainer, which pass a scalar) OR a per-individual vector (per-PFT
# phenology). `_phen_at` dispatches on the argument TYPE, so the scalar path constant-folds to the plain
# value — the scalar specialization of `daily_step_canopy`/`patch_albedo` compiles to the identical IR it
# had before per-individual phen existed (byte-identical, Enzyme-transparent), while a vector indexes.
@inline _phen_at(ph::AbstractVector, i::Integer) = @inbounds ph[i]
@inline _phen_at(ph, ::Integer) = ph
_pheltype(ph::AbstractVector) = isempty(ph) ? Float64 : eltype(ph)
_pheltype(ph) = typeof(ph)

"""
    tebs_phenparams(::Type{T}=Float64) -> PhenParams{T}

GSI phenology parameters for the beech (TeBS, PFT id 3) — the Hainich prototype's dominant PFT. Equal to
`pft_phenparams(3, T)` (the [`PhenParams`](@ref) defaults).
"""
tebs_phenparams(::Type{T} = Float64) where {T <: Real} = PhenParams{T}()

# is a natural PFT id a grass? (LPJmL-FIT `par/pft_lpjmlfit.js` scan order: 0–6 trees, 7–9 grasses,
# 10+ crops). Grass runs the SAME GSI four-limiter product, differing only in the light-limiter driver
# (forest-floor `fpar_grass·light`, `phenology_gsi.c:30-35`) — see [`per_pft_phenology`](@ref).
_pft_is_grass(id::Integer) = id >= 7

"""
    pft_phenparams(id::Integer, ::Type{T}=Float64) -> PhenParams{T}

GSI leaf-phenology parameters for LPJmL-FIT natural PFT `id` (0-based scan order of the ACTIVE
`par/pft_lpjmlfit.js`), the authoritative FIT file (`lpjmlfit.js` sets `"new_phenology":true` +
`"individual":true`, so **every** natural PFT — trees AND grasses — runs the four-limiter GSI product;
the "evergreen"-named PFTs are NOT static). Each PFT's `tmin/tmax/light` slope/base/tau come straight
from its `par/pft_lpjmlfit.js` block; `wscal_base` is the individual-mode inflection, which the C
takes from the stem's own sampled `minwscal` trait (`phenology_gsi.c:64-66`; the par-file
`wscal.base` is inert under `config->individual`). Supported ids:

| id | PFT (`par/pft_lpjmlfit.js`)                    | par `"median"` | par `[low, high]` | realised median |
|----|-----------------------------------------------|:------------:|:---------:|:-----:|
| 0  | tropical broadleaved evergreen tree (TrBE)    | 0.60 | [0.05, 0.75] | 0.669 Sahel / 0.560 Amazon |
| 1  | temperate needleleaved evergreen tree (TeNE)  | 0.10 | [0.025, 0.20] | 0.188 Iberia |
| 2  | temperate broadleaved evergreen tree (TeBE)   | 0.10 | [0.025, 0.20] | 0.137 Iberia |
| 3  | temperate broadleaved summergreen tree (TeBS, **beech**) | 0.2096 | [0.10, **0.15**] | 0.119 Hainich |
| 4  | boreal needleleaved evergreen tree (BoNE)     | 0.25 | [0.05, 0.30] | 0.071 boreal |
| 5  | boreal broadleaved summergreen tree (BoBS)    | 0.25 | [0.10, **0.15**] | 0.125 boreal |
| 6  | boreal needleleaved summergreen tree (BoNS)   | 0.35 | [0.05, **0.15**] | 0.133 boreal |
| 7  | tropical C4 grass                             | 0.20 | scalar | — |
| 8  | temperate C3 grass                            | 0.20 | scalar | — |
| 9  | polar C3 grass                                | 0.20 | scalar | — |

⚠ **`wscal_base` is `100 ×` the par file's interval `"median"` field, NOT a realised median** — an
earlier version of this docstring claimed the latter. ADR 0047's trap applies: for **ids 3, 5 and 6
that `"median"` exceeds the interval's own `high`** (bold above), so it is not a possible central
value of the trait the C samples, and the realised medians measured off the C's own per-stem output
sit 9.1 / 12.5 / 21.7 percentage points below it. **This is inert at four of the five biome cells**
because the limiter is saturated there (the transition width is only `2·ln(9)/(100·sl)` ≈ 0.0084 in
water availability, so it is nearly a step at `w = minwscal`), but at `semiarid_sahel` the realised
water availability falls BETWEEN F's inflection and the C's ⇒ F's filter reads 1.0 where the C's
reads 0.0. Measured in ADR 0139; harness `scripts/diagnose_phenology_water_inflection.py`.

Crops (id ≥ 10, `cropgreen`) use a different routine (`phenology.c`, not `phenology_gsi`) and are out of
scope for the natural-vegetation canopy. The Hainich prototype (cell 42490) contains ids 1, 2, 3, 4, 5, 8.
"""
function pft_phenparams(id::Integer, ::Type{T} = Float64) where {T <: Real}
    # (tmin_sl, tmin_base, tmin_tau, tmax_sl, tmax_base, tmax_tau, light_sl, light_base, light_tau,
    #  wscal_sl, wscal_base = minwscal_med·100, wscal_tau) — verbatim from par/pft_lpjmlfit.js.
    p = if id == 0            # tropical broadleaved evergreen
        (1.01, 10.0, 0.2, 1.86, 38.64, 0.2, 77.17, 55.53, 0.52, 5.14, 60.0, 0.44)
    elseif id == 1           # temperate needleleaved evergreen
        (1.0, -30.0, 0.1, 1.83, 35.26, 0.2, 20.0, 40.872, 0.2, 5.0, 10.0, 0.01)
    elseif id == 2           # temperate broadleaved evergreen
        (1.0, -5.0, 0.2, 1.6, 41.12, 0.2, 18.83, 2.0, 0.2, 5.0, 10.0, 0.1)
    elseif id == 3           # temperate broadleaved summergreen (beech) — the PhenParams defaults
        return PhenParams{T}()
    elseif id == 4           # boreal needleleaved evergreen
        (0.5, -80.0, 0.2, 0.4, 28.0, 0.2, 15.0, 0.001, 0.1, 5.0, 25.0, 0.01)
    elseif id == 5           # boreal broadleaved summergreen
        (2.0, 8.0, 0.2, 1.74, 28.0, 0.2, 58.0, 55.0, 0.2, 5.24, 25.0, 0.1)
    elseif id == 6           # boreal needleleaved summergreen
        (1.0, 7.0, 0.1, 0.5, 28.0, 0.2, 58.0, 59.78, 0.2, 5.0, 35.0, 0.8)
    elseif id == 7           # tropical C4 grass
        (0.91, 6.418, 0.2, 1.47, 29.16, 0.2, 64.23, 69.9, 0.4, 0.1, 20.0, 0.17)
    elseif id == 8           # temperate C3 grass
        (1.0, 6.0, 0.1011, 0.24, 32.04, 0.2, 23.0, 75.94, 0.22, 0.5222, 20.0, 0.1)
    elseif id == 9           # polar C3 grass
        (0.311, 4.79, 0.11, 0.24, 20.0, 0.2, 23.0, 50.0, 0.38, 0.88, 20.0, 0.94)
    else
        throw(ArgumentError("pft_phenparams: unsupported natural PFT id $id (supported 0–9; crops out of scope)"))
    end
    return PhenParams{T}(;
        tmin_sl = T(p[1]), tmin_base = T(p[2]), tmin_tau = T(p[3]),
        tmax_sl = T(p[4]), tmax_base = T(p[5]), tmax_tau = T(p[6]),
        light_sl = T(p[7]), light_base = T(p[8]), light_tau = T(p[9]),
        wscal_sl = T(p[10]), wscal_base = T(p[11]), wscal_tau = T(p[12]),
    )
end

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
    # `phen` may be a scalar (patch-wide) or a per-individual vector (per-PFT phenology) — see `_phen_at`.
    T = promote_type(isempty(inds) ? Float64 : _wt(first(inds)), _pheltype(phen), typeof(snowpack))
    (_, sfr) = _snow_state(convert(T, snowpack))
    cfs = T(C_FSTEM)
    albstot = zero(T)
    fpc_sum = zero(T)
    for (ii, ind) in enumerate(inds)
        ph = convert(T, _phen_at(phen, ii))
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
# MULTI-INDIVIDUAL / MULTI-PFT CANOPY (scale-up step 3 — docs/notes/phase3_fdiff_cbinary_validation.md §7)
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
#    the canopy total absorbs its layered fraction (≈0.83 leafon at Hainich) rather than the fpc/albedo
#    `d_fapar` OUTPUT (≈0.49) the single-individual drive mistakenly used — recovering GPP.
#    ⚠ ADR 0135: that 0.83 is F's OWN absorption, NOT a C reference — `d_fapar`/`FAPAR` is built from
#    `pft->fpc` + the albedos (`albedo_tree.c:75`), i.e. ADR 0060's crown-cover family, so it cannot
#    validate the layered `pft->fpar`. The output that DOES constrain this basis is `LAI_STAND`, and
#    the port is scored against it in `scripts/diagnose_layered_light_basis.py` (0.87–0.98 at four of
#    five biome cells, below 1 by exactly the `ind` writer's 5 m cut). The density here is faithful to
#    `getfpar.c`'s LIVE line, `min(leaf_c·sla/(h−bole), 40)·nind` — the per-CROWN variants in that file
#    are inside `/* test: */` comment blocks and a `grep` lands in them.
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
# absent from `ind`, and per-individual root distribution approximated by the shared cell profile (see
# `docs/notes/water_supply_perpft_design.md` — the faithful per-individual supply is SCOPED/DEFERRED
# because the C depletes layers in a daily-reshuffled random order under `-DPERMUTE`, which is neither
# deterministic nor differentiable).
# ⚠ CORRECTION (2026-08-06): this list used to end "and interception/wet-canopy omitted (as in
# `daily_step_ml`)". That is STALE and it misled a docs pass into publishing it as a live limitation.
# `daily_step_canopy` DOES model interception: `_wet_interc` runs per individual (:1533 for the
# evaporated flux removed from infiltration, :1627 for the demand-reducing `wet`), and `interc` is a
# term of the returned water-balance closure `precip = transp + evap + interc + runoff + Δ(Σw + snow)`.
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
    c_sapwood_bg::T               # below-ground root-sapwood maintenance pool (gC/individual; formed per-m²
    # via nind at the call site, `npp_tree.c:51`). 0 by default (the pre-
    # sapwood_bg 16-arg constructor ⇒ byte-identical); seeded from the C_LATERAL
    # demand — see [`TreePools`](@ref) / docs/notes/sapwood_bg_design.md.
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
# ⚠ ADR 0110: the per-individual root profile is deliberately NOT a field here. It was, briefly, and a
# `Vector{T}` inside this struct made the Enzyme reverse pass abort the whole test process with SIGABRT
# (no Julia error — a bare LLVM-level abort, right after the grass Enzyme training item). `Individual` is
# differentiated through; a heap-allocated field in it is exactly the AD hazard
# `docs/water_supply_perpft_design.md` §4.3 warned about. The profiles now travel as a SEPARATE
# `rootdists` argument, which Enzyme sees as constant data.

# Backward-compatible constructor (pre-`c_sapwood_bg`): fills the below-ground root-sapwood pool with 0, so
# every existing 16-arg call site is byte-identical. Seed the pool with the explicit 17-arg constructor.
Individual{T}(
    fpar, fpc, alphaa, albedo_leaf, emax, c_sapwood, c_root, lai, intc, albedo_stem,
    albedo_litter, snowcanopyfrac, nind, photo::PhotoParams, tstress::TempStressParams, is_grass::Bool,
) where {T <: Real} = Individual{T}(
    fpar, fpc, alphaa, albedo_leaf, emax, c_sapwood, c_root, zero(T), lai, intc, albedo_stem,
    albedo_litter, snowcanopyfrac, nind, photo, tstress, is_grass,
)

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

# ── ADR 0110: withdraw an ALREADY per-layer-resolved demand from the shared column ────────────────
# The per-tree path builds `want[l] = Σ_i t_i·rootdist_i[l]·rel[l]/wr_i` (optionally with the C's
# order-free FPC-share cap already applied per tree) inside the individual loop, so the only thing left
# here is the shared column's own per-layer availability clamp — the C's `water_stressed.c:269-271`
# `if (aet_layer[l] > w[l]*whcs[l]) aet_layer[l] = w[l]*whcs[l]`. Order-free: `want` is a plain sum.
function _transpire_layers(w::AbstractVector{T}, want::AbstractVector, βw) where {T}
    N = length(w)
    wnew = similar(w)
    actual = zero(T)
    for l in 1:N
        take = smoothmin(convert(T, want[l]), w[l], βw)
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
daily PET (`pet_C/α_PT`) for the kernel-isolation comparison of §10. `hooks` ([`FluxHooks`](@ref)) adds
optional learned PER-INDIVIDUAL Vcmax/λ corrections (identity fast path when off ⇒ byte-identical to
pure physics); this is the coupled-canopy training path (scale-up step 7b-canopy, Enzyme reverse). Returns the new state and stand
daily fluxes `(gpp, npp, transp, evap, interc, eeq, runoff, rootmoist, fapar, fpc, wscal, npp_ind)`
(per m² of patch; `wscal` = the stand water scalar feeding next day's GSI water phenology; `npp_ind` =
the per-individual daily NPP vector, whose annual sum is each individual's `bm_inc` for
[`grow_individual`](@ref)). Water closes exactly:
`precip = transp + evap + interc + runoff + Δ(Σw + snow)`.

`pftphys` (ADR 0126) is an optional per-individual `Vector{`[`PFTPhys`](@ref)`}` supplying each
individual's OWN maintenance-respiration coefficient (`resp.respcoeff`) and minimum canopy conductance
(`gmin`) — both per-PFT in the C and both single-valued in `p`. `nothing` (the default) uses `p.resp`
and `p.water.gmin` for every individual ⇒ BYTE-IDENTICAL to the pre-ADR-0126 step, which is also what
keeps the Enzyme trainer and every committed baseline unchanged.
"""
function daily_step_canopy(
        p::FDiffParams, inds::AbstractVector{<:Individual}, soil::SoilColumn, st::FDiffStateML,
        f::DailyForcing; phen = 1.0, n_top1m::Int = 3, eeq_ext = nothing, hooks::FluxHooks = _NO_HOOKS,
        rootdists = nothing, pftphys = nothing,
    )
    T = promote_type(_wt(p), _wt(st), _wt(soil), _wt(f), isempty(inds) ? Float64 : _wt(first(inds)))
    # `phen` is EITHER a single patch-wide scalar (every committed baseline + the Enzyme trainer pass one
    # — byte-identical to pre-per-PFT behaviour) OR a per-individual vector (per-PFT phenology; see
    # `per_pft_phenology`/`rollout_daily_canopy`). Each per-individual loop reads its own leaf-display
    # factor `phi = convert(T, _phen_at(phen, ii))`; `_phen_at` dispatches on type so the scalar path
    # constant-folds to the plain value (identical IR ⇒ Enzyme-transparent).
    w = p.water
    # eeq: by default self-computed from the DYNAMIC patch albedo (patch_albedo — the albedo_stand.c
    # port), so standalone F_diff needs no C-PET crutch (§11). `eeq_ext` (= pet_C/α_PT) still overrides
    # it for the kernel-isolation comparison of §10 (the C binary's own daily albedo_patch).
    eeq = if eeq_ext === nothing
        beta = patch_albedo(inds, phen, st.snowpack)
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
    for (ii, ind) in enumerate(inds)
        phi = convert(T, _phen_at(phen, ii))
        (_, interc_i) = _wet_interc(convert(T, ind.intc), convert(T, ind.lai), phi, convert(T, ind.fpc), eeq, rain, w.α_PT)
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
    # ADR 0110: PER-INDIVIDUAL root-weighted moisture. The C computes `wr` inside its per-individual loop
    # from that individual's own `rootdist_n` (`lpj/water_stressed.c:87-100`), and it is ORDER-INDEPENDENT
    # (it reads only the frozen `soil.w[]`). Off, or for an individual with no profile (grass, or any
    # pre-0110 `Individual`), `wr_i ≡ wr` ⇒ byte-identical. `wr` itself stays the shared value everywhere
    # else (the `FluxHooks` feature vector, the fallback), so hooks-on runs are unchanged too.
    per_tree = w.per_tree_roots && rootdists !== nothing
    wr_ind = if per_tree
        v = Vector{T}(undef, length(inds))
        for ii in eachindex(inds)
            rdi = rootdists[ii]
            if isempty(rdi)
                v[ii] = wr                       # no rooting trait (grass) ⇒ the shared profile
            else
                acc = zero(T)
                for l in 1:N
                    acc += convert(T, rdi[l]) * rel1[l]
                end
                v[ii] = acc
            end
        end
        v
    else
        nothing
    end

    par = 0.5 * w.dayseconds * f.swdown
    co2_Pa = ppm2Pa(f.co2)
    dl = f.daylength
    condfac = ppm2bar(f.co2) * (one(T) - w.lambda_opt) * hour2sec(dl)

    # --- NN hooks: PER-INDIVIDUAL learned Vcmax / λ multiplicative corrections (identity when no hook —
    # see FluxHooks). Each individual's scale is evaluated ONCE per day from its own feature vector
    # `[temp, swdown, daylength, apar_i, wr, co2]` (`apar_i` = its LAYERED absorbed PAR — the physically
    # relevant lever, matching daily_step's single feature; `wr` = the shared root-zone relative
    # moisture), then applied CONSISTENTLY to both the potential-conductance Vcmax (pass 1) and the
    # GPP/λ Vcmax (pass 2), exactly as daily_step propagates `vm_scale` into `gp_pot`, the λ solve, and
    # `rd`. The identity fast path (no hook) leaves the scales `nothing` and skips feature construction
    # entirely, so the physics — and every committed canopy baseline — is byte-identical when hooks off.
    vm_scales = _has_hooks(hooks) ? Vector{T}(undef, length(inds)) : nothing
    λ_scales = _has_hooks(hooks) ? Vector{T}(undef, length(inds)) : nothing
    if _has_hooks(hooks)
        for (ii, ind) in enumerate(inds)
            phi = convert(T, _phen_at(phen, ii))
            apar_i = par * (one(T) - convert(T, ind.albedo_leaf)) * convert(T, ind.alphaa) * (convert(T, ind.fpar) * phi)
            feat = T[f.temp, f.swdown, dl, apar_i, wr, f.co2]
            vm_scales[ii] = hooks.vm === nothing ? one(T) : convert(T, hooks.vm(feat))
            λ_scales[ii] = hooks.λ === nothing ? one(T) : convert(T, hooks.λ(feat))
        end
    end

    # ── pass 1: gp_sum — per-individual potential conductance (FPC-based light, λ_opt) → stand mean ──
    gp_stand_acc = zero(T)
    fpc_tot = zero(T)
    # C-faithful leaf-on aggregates (`gp_sum.c:57-67`), accumulated only under `w.wscal_leafon`: the
    # conductance at FULL leaf cover (φ≡1) and the **plain** Σfpc the C normalizes both gp's by.
    gp_leafon_acc = zero(T)
    gp_stand_c_acc = zero(T)      # the C's OWN `gp_stand` numerator, `Σ gp_leafon·phen` (gp_sum.c:65)
    fpc_plain = zero(T)
    # ADR 0136: the leaf-on (`φ ≡ 1`, crown-cover) pass is what `gp_sum.c` actually computes, so BOTH new
    # basis flags need it as well as `wscal_leafon`. `vm_leafon` is the C's `pft->vmax` — captured only
    # when the λ-solve arm asks for it, so the identity path allocates nothing and stays byte-identical.
    need_leafon = w.wscal_leafon || w.gp_stand_leafon_basis || w.lambda_vm_gp
    vm_leafon = w.lambda_vm_gp ? Vector{T}(undef, length(inds)) : nothing
    for (ii, ind) in enumerate(inds)
        phi = convert(T, _phen_at(phen, ii))
        fpc_i = convert(T, ind.fpc) * phi
        apar_gp = par * (one(T) - convert(T, ind.albedo_leaf)) * convert(T, ind.alphaa) * fpc_i
        tsi = temp_stress(ind.tstress, f.temp, dl)
        vms = vm_scales === nothing ? one(T) : vm_scales[ii]
        # ADR 0126: `gmin` is PER-PFT in the C (`gp_sum.c` reads `pft->par->gmin`; 0.3–1.6 across the
        # seven trees). `pftphys === nothing` ⇒ the single `w.gmin` for every individual (byte-identical).
        gmin_i = pftphys === nothing ? w.gmin : convert(T, pftphys[ii].gmin)
        (_, _, _, adtmm_gp) = photosynthesis(ind.photo, w.lambda_opt, tsi, co2_Pa, f.temp, apar_gp, dl; comp_vm = true, vm_scale = vms)
        gp_i = 1.6 * adtmm_gp / condfac + gmin_i * fpc_i
        gp_stand_acc += gp_i
        fpc_tot += fpc_i
        if need_leafon
            # the same expression at φ ≡ 1 — the C computes `gp` from `par·pft->fpc·alphaa·(1−albedo)`
            # (NO phen) and only then forms `gp_stand += gp·phen` vs `gp_stand_leafon += gp`.
            fpc_lo = convert(T, ind.fpc)
            apar_lo = par * (one(T) - convert(T, ind.albedo_leaf)) * convert(T, ind.alphaa) * fpc_lo
            (_, _, vm_lo, adtmm_lo) = photosynthesis(ind.photo, w.lambda_opt, tsi, co2_Pa, f.temp, apar_lo, dl; comp_vm = true, vm_scale = vms)
            vm_leafon === nothing || (vm_leafon[ii] = vm_lo)
            gp_lo_i = 1.6 * adtmm_lo / condfac + gmin_i * fpc_lo
            gp_leafon_acc += gp_lo_i
            gp_stand_c_acc += gp_lo_i * phi
            fpc_plain += fpc_lo
        end
    end
    # ADR 0136: the C's own expression is `Σ gp_leafon·φ / Σ fpc` gated on BOTH that numerator and the
    # plain `Σ fpc` (`gp_sum.c:67`) — the same two-sided gate `gp_leafon` below already mirrors.
    gp_stand = if w.gp_stand_leafon_basis
        (gp_stand_c_acc < T(1.0e-20) || fpc_plain < T(1.0e-20)) ? zero(T) : gp_stand_c_acc / fpc_plain
    else
        fpc_tot > T(1.0e-20) ? gp_stand_acc / fpc_tot : zero(T)
    end
    # `gp_sum.c:67` gates BOTH returns on the phen-weighted `gp_stand` and on the plain `fpc_total`, so a
    # fully leaf-off canopy yields `gp_stand_leafon = 0` and hence the C's `else wscal = 1` branch below.
    # The gate MUST use the C's own numerator `Σ gp_leafon·phen` (`gp_stand_c_acc`), NOT F_diff's
    # `gp_stand_acc`: the latter sums gp's built from a phen-scaled `apar`, and `photosynthesis(apar=0)`
    # does not return exactly 0, so at `phen ≡ 0` it stays above the 1e-20 threshold and the no-demand
    # branch would never fire (caught by `wscal_leafon_tests.jl`'s exact-zero-phen assertion).
    gp_leafon = (!w.wscal_leafon || gp_stand_c_acc < T(1.0e-20) || fpc_plain < T(1.0e-20)) ?
        zero(T) : gp_leafon_acc / fpc_plain

    # ── pass 2: per-individual layered-light photosynthesis (water-limited by gp_stand) + transp ──
    gpp_tot = zero(T); npp_tot = zero(T); transp_demand_tot = zero(T); fapar_tot = zero(T)
    sup_acc = zero(T); dem_acc = zero(T)        # fpc-weighted supply/demand → stand water scalar (phenology)
    npp_inds = Vector{T}(undef, length(inds))   # per-individual daily NPP (per-m², patch basis) → bm_inc
    # ADR 0110: per-layer withdrawal accumulator, allocated ONLY on the per-tree path (off ⇒ `nothing` ⇒
    # the scalar `transp_demand_tot` path below is untouched and byte-identical).
    want_layer = per_tree ? zeros(T, N) : nothing
    for (ii, ind) in enumerate(inds)
        phi = convert(T, _phen_at(phen, ii))
        fpc_i = convert(T, ind.fpc) * phi
        fpar_i = convert(T, ind.fpar) * phi                 # layered absorbed fraction (phen-scaled)
        apar = par * (one(T) - convert(T, ind.albedo_leaf)) * convert(T, ind.alphaa) * fpar_i
        tsi = temp_stress(ind.tstress, f.temp, dl)
        vms = vm_scales === nothing ? one(T) : vm_scales[ii]
        (_, _, vm, _) = photosynthesis(ind.photo, w.lambda_opt, tsi, co2_Pa, f.temp, apar, dl; comp_vm = true, vm_scale = vms)
        wr_i = wr_ind === nothing ? wr : wr_ind[ii]      # ADR 0110: this tree's own root-weighted moisture
        supply_i = convert(T, ind.emax) * wr_i * phi
        # wet-canopy demand reduction (1 − wet); water_stressed.c re-caps wet at 0.99
        (wet_i, _) = _wet_interc(convert(T, ind.intc), convert(T, ind.lai), phi, convert(T, ind.fpc), eeq, rain, w.α_PT)
        wet_dem = smoothmin(wet_i, T(0.99), w.βw)
        (gc, demand) = canopy_conductance(w, eeq, gp_stand, supply_i; wet = wet_dem)   # demand uses the STAND mean gp
        sup_acc += supply_i * fpc_i
        dem_acc += demand * fpc_i
        # §26 grass demand-gate: the C skips grass photosynthesis when demand `gpd ≤ 1e-5`
        # (`water_stressed.c:196` ⇒ `agd=0`, no leaf resp), so a deep-shade grass makes ~zero NET carbon.
        # F_diff keeps the shared soft `βflux` on the λ-solve input (bounded-positive `fac` ⇒ finite
        # agd/rd, NO degenerate solve) and instead multiplies the grass GPP + `rd` OUTPUTS by a smooth
        # sigmoid of the pre-floor demand `gpd_raw`. Default off (`grass_demand_gate=false` ⇒ gate ≡ 1,
        # byte-identical). Replaces the REFUTED §25 hard-floor lever (which drove deep-shade grass NPP
        # negative via the degenerate low-`fac` solve) — see `WaterParams`.
        # ADR 0131: the C's gate is per-`Pft` and therefore per TREE too in this `individual:true` config,
        # so `tree_demand_gate` (also default off ⇒ byte-identical) applies the SAME sigmoid to trees.
        gmin_i = pftphys === nothing ? w.gmin : convert(T, pftphys[ii].gmin)      # ADR 0126, per-PFT
        gpd_raw = hour2sec(dl) * (gc * fpc_i - gmin_i * fpar_i)
        gated = ind.is_grass ? w.grass_demand_gate : w.tree_demand_gate
        gate = gated ? stable_sigmoid(w.βgpd_gate * (gpd_raw - w.gpd_gate)) : one(T)
        gpd = softplus(gpd_raw, w.βflux)
        fac = gpd / 1.6 * ppm2bar(f.co2)
        # POSITIONAL constructor (field order: photo, tstress, water, resp, allom, nlambda, ω) — NOT the
        # keyword `FDiffParams{T}(; …)`: Enzyme reverse (the canopy trainer, scale-up step 7b-canopy)
        # cannot statically type-analyze the kwarg constructor on Julia 1.11 (`EnzymeNoTypeError` via the
        # `#_#10` kwarg method), while the plain positional inner constructor is transparent to it.
        # Behaviour-identical (same object) — the identity/regression baselines are unchanged.
        p_i = FDiffParams{T}(ind.photo, ind.tstress, w, p.resp, p.allom, p.nlambda, p.ω)
        # ADR 0136: the C's bisection residual carries `pft->vmax` from `gp_sum` (crown-cover, no-phen
        # `apar`) while its `je` uses the layered `data.apar` — so ONLY the λ that comes out changes; the
        # final `photosynthesis` call below keeps the layered `vm` on both sides, exactly as the C's
        # `compvm=TRUE` final call does.
        vm_λ = vm_leafon === nothing ? vm : vm_leafon[ii]
        λ = solve_lambda(p_i, fac, tsi, co2_Pa, f.temp, apar, dl, vm_λ)
        # learned ci:ca correction (identity when no hook), re-clamped to the physical bracket (a no-op
        # in the identity path — solve_lambda already confines λ to [_LAMBDA_LO, _LAMBDA_HI]).
        λs = λ_scales === nothing ? one(T) : λ_scales[ii]
        λ = clamp(λ * λs, T(_LAMBDA_LO), T(_LAMBDA_HI))
        (agd, rd, _, _) = photosynthesis(ind.photo, λ, tsi, co2_Pa, f.temp, apar, dl; comp_vm = false, vm = vm)
        gpp_i = softplus(agd, w.βflux) * gate                 # §26 grass demand-gate (≡ gpp_i when off)
        rd = rd * gate                                        # gate leaf resp with GPP (else deep-shade NPP<0)
        gpp_tot += gpp_i
        fapar_tot += fpar_i
        # transpiration: min(supply, demand_stand)·fpc (water_stressed.c:153 after the per-layer sum)
        t_i = smoothmin(supply_i, demand, w.βtransp) * fpc_i
        transp_demand_tot += t_i
        if want_layer !== nothing
            # ADR 0110: distribute THIS tree's transpiration down ITS OWN profile — the C's
            # `aet·rootdist_n[l]·trf[l]` with `aet = min(supply,demand)/wr·fpc` (`water_stressed.c:266`).
            # Optionally apply the C's ORDER-FREE cap (i) (`:159-161`): this tree may not draw more from a
            # layer than its own FPC share of that layer's water. It depends only on this tree and the
            # frozen `w1`, so this is a plain per-(tree,layer) `smoothmin` — NOT a loop-carried
            # read-modify-write, and NOT the order-dependent residue cap. `want_layer` is a pure
            # accumulation (a vectorized `+=`), so no iteration changes another's result.
            rdi = isempty(rootdists[ii]) ? soil.rootdist : rootdists[ii]
            share = t_i / (wr_i + T(1.0e-12))
            for l in 1:N
                c = share * convert(T, rdi[l]) * rel1[l]
                if w.per_tree_fpc_cap
                    c = smoothmin(c, fpc_i * w1[l], w.βw)
                end
                want_layer[l] += c
            end
        end
        # maintenance respiration is PER-M² (patch basis): the C multiplies the per-individual sapwood/
        # root carbon by `nind` (`npp_tree.c:51` `mresp = nind·(sapwood·… + root·…)`), consistent with
        # the per-m² `gpp_i`/`rd` here — so `bm_inc = Σ npp_i` accumulates on the same patch basis the
        # annual allocation (`allocation_tree.c:236` `bm_inc_ind = bm_inc/nind`) divides back out.
        nind_i = convert(T, ind.nind)
        c_sap = ind.is_grass ? zero(T) : convert(T, ind.c_sapwood) * nind_i
        c_sapbg = ind.is_grass ? zero(T) : convert(T, ind.c_sapwood_bg) * nind_i   # bg root-sapwood (per-m²), trees only
        # ADR 0126: `respcoeff` is PER-PFT (0.2 tropical / 1.2 temperate+boreal — a 6× spread that put F's
        # annual carbon balance NEGATIVE at both hot biome cells). `nothing` ⇒ the single `p.resp`.
        resp_i = pftphys === nothing ? p.resp : pftphys[ii].resp
        (npp_i, _) = autotrophic_respiration(resp_i, f.temp, gpp_i, rd, c_sap, convert(T, ind.c_root) * nind_i; phen = phi, c_sapwood_bg = c_sapbg)
        npp_tot += npp_i
        npp_inds[ii] = npp_i
    end

    # ── shared soil: withdraw the total transpiration demand (per-layer capped), then soil evap ──
    (w2, transp) = want_layer === nothing ?
        _transpire_total(w1, convert.(T, soil.whcs), convert.(T, soil.rootdist), wr, transp_demand_tot, w.βw) :
        _transpire_layers(w1, want_layer, w.βw)     # ADR 0110: each tree already drew down its own profile
    cover = smoothmin(fpc_tot, one(T), w.βevap)            # total canopy cover (≤ 1)
    (w3, soil_evap) = _soil_evap(w2, convert.(T, soil.whcs), convert.(T, soil.frac_evap), eeq, w.α_PT, cover, w.βevap, w.βw)

    runoff = drainage
    rootmoist = zero(T)
    for l in 1:min(n_top1m, N)
        rootmoist += w3[l]
    end
    # stand water scalar — feeds next day's GSI water phenology, the annual `wscal_mean` that drives the
    # leaf:root allocation `lmtorm`, and Component S's `water_stress` feature. Default: the realized
    # `min(1, Σsupply·fpc / Σdemand·fpc)`. Opt-in `wscal_leafon`: the C's POTENTIAL leaf-on index (ADR 0051).
    # ADR 0110: on the per-tree path also emit each individual's OWN water scalar (`wscal_ind`) — the
    # quantity `tree/waterstress_tree.c` gates against that individual's own `minwscal`. `nothing` off.
    wscal_ind = per_tree && w.wscal_leafon ? Vector{T}(undef, length(inds)) : nothing
    wscal = w.wscal_leafon ?
        _wscal_leafon(w, inds, eeq, wr, gp_leafon, fpc_plain; wr_ind = wr_ind, out = wscal_ind) :
        smoothmin(one(T), sup_acc / (dem_acc + T(1.0e-9)), w.βwscal)
    st′ = FDiffStateML{T}(w3, convert(T, snowpack′))
    fluxes = (
        gpp = convert(T, gpp_tot), npp = convert(T, npp_tot), transp = convert(T, transp),
        evap = convert(T, soil_evap), interc = convert(T, interc_tot), eeq = convert(T, eeq),
        runoff = convert(T, runoff), rootmoist = convert(T, rootmoist),
        fapar = convert(T, fapar_tot), fpc = convert(T, fpc_tot), wscal = convert(T, wscal),
        npp_ind = npp_inds,       # per-individual daily NPP (per-m², patch basis) — the flux-then-integrate bm_inc source
        wscal_ind = wscal_ind,    # ADR 0110: per-individual water scalar (`nothing` unless per_tree_roots);
        # the daily quantity `waterstress_tree.c` gates against each tree's own `minwscal`
        wr_ind = wr_ind,          # ADR 0110: per-individual root-weighted soil moisture (`nothing` off)
    )
    return (st′, fluxes)
end

# Advance each DISTINCT PFT's four GSI filters one day and return the per-distinct-PFT `phen`. `states`
# (a `Vector{PhenState}`, one per distinct PFT) is updated in place; grasses (`isg[k]`) drive the light
# limiter with the forest-floor light `grass_lf·swdown` (`phenology_gsi.c:30-35`), trees with full
# `swdown`. Pure w.r.t. the numeric inputs (ForwardDiff-safe); NOT on the Enzyme training path.
function _step_pft_phen_day!(
        states::Vector{PhenState{T}}, params::Vector{PhenParams{T}}, isg::Vector{Bool},
        temp, swdown, water_avail, soiltemp, grass_lf
    ) where {T}
    phen = Vector{T}(undef, length(states))
    for k in eachindex(states)
        light_in = isg[k] ? convert(T, grass_lf) * convert(T, swdown) : convert(T, swdown)
        (states[k], ph) = phenology_gsi_step(params[k], states[k], temp, light_in, water_avail, soiltemp)
        phen[k] = ph
    end
    return phen
end

"""
    per_pft_phenology(pft_ids, forcings; phen_params_by_pft=nothing, water_avails=nothing,
                      grass_light_frac=nothing) -> phens::Vector{Vector}

Per-PFT GSI leaf phenology for a patch of individuals with 0-based `pft_lpjmlfit.js` PFT ids `pft_ids`,
returning the per-day × per-individual leaf-display factor `phens[d][i] ∈ [0,1]`. Each DISTINCT PFT
advances its own [`PhenState`](@ref) filters with its [`pft_phenparams`](@ref); individuals of the same
PFT share the trajectory (the per-individual `minwscal` sampling of the C's individual mode is a
documented v1 simplification — the median is used). Grasses (id ≥ 7) drive the light limiter with the
forest-floor light `grass_light_frac·swdown` (`phenology_gsi.c:30-35`); `grass_light_frac` (scalar or
per-day vector) defaults to `1` (open field) and is supplied canopy-attenuated by
[`rollout_daily_canopy`](@ref) when phenology is co-solved with the structure. `water_avails[d]` (the
previous day's stand water scalar) drives the water limiter; it defaults to moist `1` (open-loop — the
closed-loop self-driven form lives in [`rollout_daily_canopy`](@ref)). Pure / AD-safe (ForwardDiff);
this is the standalone per-PFT phenology used for validation and to feed `daily_step_canopy`'s
per-individual `phen` vector.
"""
function per_pft_phenology(
        pft_ids, forcings; phen_params_by_pft = nothing, water_avails = nothing, grass_light_frac = nothing
    )
    T = isempty(forcings) ? Float64 : _wt(first(forcings))
    uids = unique(pft_ids)
    slot = Dict{Int, Int}(id => k for (k, id) in enumerate(uids))
    params = PhenParams{T}[phen_params_by_pft === nothing ? pft_phenparams(id, T) : phen_params_by_pft(id) for id in uids]
    states = PhenState{T}[PhenState{T}() for _ in uids]
    isg = Bool[_pft_is_grass(id) for id in uids]
    phens = Vector{Vector{T}}(undef, length(forcings))
    for (d, f) in enumerate(forcings)
        wav = water_avails === nothing ? one(T) : convert(T, water_avails[d])
        glf = grass_light_frac === nothing ? one(T) :
            (grass_light_frac isa Number ? convert(T, grass_light_frac) : convert(T, grass_light_frac[d]))
        phen_slot = _step_pft_phen_day!(states, params, isg, f.temp, f.swdown, wav, f.temp, glf)
        phens[d] = T[phen_slot[slot[id]] for id in pft_ids]
    end
    return phens
end

"""
    rollout_daily_canopy(p, st0, inds, soil, forcings; phens=nothing, eeqs=nothing,
                         phen_params=nothing, phen_state=nothing, pft_ids=nothing, n_top1m=3) -> (st, days)

Fold [`daily_step_canopy`](@ref) over a vector of [`DailyForcing`](@ref) for ONE patch canopy `inds`,
carrying the shared per-layer soil water and snow. **By default (standalone, crutch-free) F_diff
computes both the phenology and the `eeq` albedo itself** (§11): the daily leaf-display factor `phen`
comes from the GSI phenology ([`phenology_gsi_step`](@ref) with `phen_params`, default
[`tebs_phenparams`](@ref)), advanced from the air temperature, shortwave, and the previous day's stand
water scalar (the soil-temp gate uses air temp as its proxy); and `eeq` from the dynamic
[`patch_albedo`](@ref). Passing `phens` (e.g. `fapar_C/peak`) and/or `eeqs` (the C's `pet_C/α_PT`)
overrides these with the C-binary-driven values for kernel-isolation comparison (§9/§10). `phen_state`
optionally seeds the GSI filters (e.g. for multi-year continuity); it defaults to the LPJmL cold-start
(`newpft.c:44-45`). **`pft_ids`** (0-based `pft_lpjmlfit.js` ids, one per individual) switches the
self-computed phenology from a single patch-wide beech GSI to PER-PFT: each individual gets its own PFT's
GSI leaf-display ([`pft_phenparams`](@ref)/[`per_pft_phenology`](@ref)), co-solved with the stand water
feedback and a lag-1 forest-floor light attenuation for grass (`grass_lf = 1 − Σ_trees fpar_i·phen_i`).
`pft_ids === nothing` (default) keeps the beech-patch-wide behaviour (byte-identical). `pft_ids` is
ignored when `phens` (the C-FAPAR crutch) is supplied. Returns the final [`FDiffStateML`](@ref) and the
per-day stand flux `NamedTuple`s.
"""
function rollout_daily_canopy(
        p::FDiffParams, st0::FDiffStateML, inds::AbstractVector{<:Individual}, soil::SoilColumn,
        forcings; phens = nothing, n_top1m::Int = 3, eeqs = nothing,
        phen_params = nothing, phen_state = nothing, pft_ids = nothing, hooks::FluxHooks = _NO_HOOKS,
        phen_params_by_pft = nothing, grass_lf_mode::Symbol = :linear, rootdists = nothing   # ADR 0110
    )
    T = promote_type(_wt(p), _wt(st0), _wt(soil), _wt(first(forcings)), isempty(inds) ? Float64 : _wt(first(inds)))
    st = FDiffStateML{T}(convert.(T, st0.w), convert(T, st0.snowpack))
    pp = phen_params === nothing ? tebs_phenparams(T) : phen_params
    ps = phen_state === nothing ? PhenState{T}() : phen_state
    # per-PFT self-phen (only when self-computing AND pft_ids supplied): one PhenState per DISTINCT PFT.
    # `phen_params_by_pft` (id → PhenParams) overrides the default `pft_phenparams` (e.g. a co-calibrated
    # grass light limiter, docs §26); `nothing` uses the ACTIVE `par/pft_lpjmlfit.js` values.
    per_pft = pft_ids !== nothing && phens === nothing
    uids = per_pft ? unique(pft_ids) : Int[]
    pft_slot = Dict{Int, Int}(id => k for (k, id) in enumerate(uids))
    pft_params = PhenParams{T}[phen_params_by_pft === nothing ? pft_phenparams(id, T) : convert(PhenParams{T}, phen_params_by_pft(id)) for id in uids]
    kl_ff = T(0.5)                                 # k_lambert forest-floor extinction (getfpar.c fpar_grass)
    pft_states = PhenState{T}[PhenState{T}() for _ in uids]
    pft_isg = Bool[_pft_is_grass(id) for id in uids]
    grass_lf = one(T)                             # lag-1 forest-floor light fraction for grass
    water_avail = one(T)                          # previous day's stand water scalar (moist cold-start)
    ph1 = phens === nothing ? one(T) : convert(T, phens[1])
    ee1 = eeqs === nothing ? nothing : eeqs[1]
    days = Vector{typeof(daily_step_canopy(p, inds, soil, st, first(forcings); phen = ph1, n_top1m = n_top1m, eeq_ext = ee1, hooks = hooks, rootdists = rootdists)[2])}()
    sizehint!(days, length(forcings))
    for (i, f) in enumerate(forcings)
        # phenology: supplied crutch (phens) OR self-computed — per-PFT (per-individual vector) or the
        # single patch-wide beech GSI (scalar). ⚠ `f.temp` is passed TWICE: as air temperature and, in
        # the last slot, as the C's `soil->temp[0]` for the 10 °C water-filter gate
        # (`phenology_gsi.c:67`). MEASURED, not assumed (ADR 0139): layer-1 soil temperature tracks air
        # with a best-fit lag of 0 days and |mean(soil−air)| ≤ 0.13 °C at four of the five biome cells,
        # so the substitution is exact there. It is NOT at `boreal_siberia` (mean +4.40 °C, sd 10.8 —
        # snow insulation in winter, thermal damping in summer, not a lag), which flips the gate's
        # verdict on 10.5 % of days carrying 18.7 % of the annual light. That bound is credible only if
        # the water filter would have been CLOSED on those days, and it is saturated OPEN there
        # (`w` ≈ 0.69 against an inflection ≈ 0.13) — so no port and no flag. Harness
        # `scripts/diagnose_phenology_soiltemp_gate.py`; dampener still open: the realised DAILY `w`.
        phen_arg = if phens !== nothing
            convert(T, phens[i])
        elseif per_pft
            phen_slot = _step_pft_phen_day!(pft_states, pft_params, pft_isg, f.temp, f.swdown, water_avail, f.temp, grass_lf)
            T[phen_slot[pft_slot[id]] for id in pft_ids]     # per-individual leaf-display vector
        else
            (ps, ph) = phenology_gsi_step(pp, ps, f.temp, f.swdown, water_avail, f.temp)
            ph
        end
        ee = eeqs === nothing ? nothing : eeqs[i]
        (st, fl) = daily_step_canopy(p, inds, soil, st, f; phen = phen_arg, n_top1m = n_top1m, eeq_ext = ee, hooks = hooks, rootdists = rootdists)
        water_avail = fl.wscal                    # today's water status → tomorrow's water phenology
        if per_pft                                # update lag-1 grass light fraction from this day's tree leaf display
            if grass_lf_mode === :exp
                # FAITHFUL forest-floor transmission `exp(-k_lambert·Σ_trees plai_i·phen_i)` (getfpar.c:165,
                # phen-scaled tree LAI). Patch-basis tree LAI recovered from the leaf-on `fpc`/`lai`:
                # `fpc = crownarea·nind·(1−e^{−k_beer·lai})` ⇒ `crownarea·nind = fpc/(1−e^{−k_beer·lai})`, so
                # `plai_i = lai·crownarea·nind`. Differs from `:linear` only while trees transition (phen<1);
                # at full leaf (phen=1) both equal `exp(−k·plai_leafon)` (the layered partition telescopes).
                plai_phen = zero(T)
                for (ii, ind) in enumerate(inds)
                    ind.is_grass && continue
                    lai_i = convert(T, ind.lai)
                    lai_i <= zero(T) && continue
                    denom = one(T) - exp(-convert(T, p.allom.k_beer) * lai_i)
                    plai_i = denom > T(1.0e-12) ? lai_i * convert(T, ind.fpc) / denom : zero(T)
                    plai_phen += plai_i * _phen_at(phen_arg, ii)
                end
                grass_lf = exp(-kl_ff * plai_phen)
            else
                absorbed = zero(T)
                for (ii, ind) in enumerate(inds)
                    ind.is_grass || (absorbed += convert(T, ind.fpar) * _phen_at(phen_arg, ii))
                end
                grass_lf = clamp(one(T) - absorbed, zero(T), one(T))
            end
        end
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
#   • grasses now grow their leaf/root pools via a faithful port of the NATURAL-veg branch of
#     `allocation_grass.c` + `turnover_grass.c` ([`grow_grass_individual`](@ref)); the per-area grass
#     convention (`crownarea = nind = 1`) carries the leaf/root carbon per-m². v1 simplifications there:
#     the pool→structure light recompute shares the beech `k_beer`, grass maintenance respiration reuses
#     the beech `RespParams`, and the reproduction growing-days fraction is taken as 1 (as for trees);
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
    sapwood_bg_c::T               # below-ground root-sapwood pool (gC/individual; the C's `Treephys2.sapwood_bg`).
    # Pays phen-gated maintenance (`npp_tree.c:51`) + grows from the C_LATERAL
    # demand (`allocation_tree.c:163-209`). 0 by default (the pre-sapwood_bg
    # 10-arg constructor ⇒ byte-identical); seed at init via
    # [`reconstruct_sapwood_bg`](@ref) — see docs/notes/sapwood_bg_design.md §4.1/§8.
    heartwood_bg_c::T             # below-ground HEARTwood pool (gC/individual; the C's `Treephys2.heartwood_bg`).
    # The sink half of the below-ground wood pair: `turnover_tree.c:124-130` moves
    # `sapwood_bg·turnover.sapwood` into it every year and it NEVER respires and
    # never leaves the plant. It exists because the pair is a producer/consumer —
    # without it the annual below-ground turnover either destroys carbon or is
    # charged maintenance the C does not charge (ADR 0127 §6). 0 by default (the
    # pre-`heartwood_bg` 13-arg constructor ⇒ byte-identical); grown only by
    # [`grow_individual`](@ref) with `bg_growth = true`.
    height::T
    crownarea::T
    nind::T
    sla::T
    wooddens::T
    d95max::T                     # rooting-depth trait, cm (the C's `Pfttree.D95max`, sampled per recruit
    # in `tree/new_tree.c:170-202` and used at `:229-230` to set that individual's
    # OWN `beta_root`). Component S predicts and validates this axis; ADR 0110 gives
    # it a consumer. **0 = UNSET** ⇒ that individual falls back to the shared cell
    # profile (grass always, since the C zeroes tree fields on grass rows; and every
    # pre-ADR-0110 call site ⇒ byte-identical).
    minwscal::T                   # drought tolerance, – (the C's `pft->minwscal`). Sets that individual's
    # OWN drought-death threshold `mort_water_res − minwscal`
    # (`tree/waterstress_tree.c:32`). Also sampled + validated by S; consumed by the
    # Phase-2 hazard. **0 = UNSET** (safe: the C's per-PFT intervals start at 0.025).
    is_grass::Bool
end
_wt(::TreePools{T}) where {T} = T

# Backward-compatible constructor (pre-`heartwood_bg_c`, ADR 0132): fills the below-ground HEARTwood pool
# with 0, so every existing 13-arg call site is byte-identical. ⚠ It is also the silent-drop hazard: a call
# site that REBUILDS a tree with this arity (a demography merge, an S-side recruit mix) discards a grown
# `heartwood_bg_c`. Every such site inside F carries the pool explicitly; `src/components/slow.jl` does not
# yet (line-S integration point, ADR 0132 §7) — which is safe only while `bg_growth` is off there.
TreePools{T}(
    leaf_c, sapwood_c, heartwood_c, root_c, sapwood_bg_c, height, crownarea, nind, sla, wooddens,
    d95max, minwscal, is_grass::Bool,
) where {T <: Real} = TreePools{T}(
    leaf_c, sapwood_c, heartwood_c, root_c, sapwood_bg_c, zero(T), height, crownarea, nind, sla, wooddens,
    d95max, minwscal, is_grass,
)

# Backward-compatible constructor (pre-`d95max`/`minwscal`, ADR 0110): leaves both traits UNSET (0), so the
# individual keeps the shared cell root profile and carries no drought threshold — every existing 11-arg
# call site is byte-identical. Pass them explicitly with the 14-arg constructor.
TreePools{T}(
    leaf_c, sapwood_c, heartwood_c, root_c, sapwood_bg_c, height, crownarea, nind, sla, wooddens,
    is_grass::Bool,
) where {T <: Real} = TreePools{T}(
    leaf_c, sapwood_c, heartwood_c, root_c, sapwood_bg_c, zero(T), height, crownarea, nind, sla, wooddens,
    zero(T), zero(T), is_grass,
)

# Backward-compatible constructor (pre-`sapwood_bg_c`): fills the below-ground sapwood pool with 0, so every
# existing 10-arg call site is byte-identical. Seed the pool with the explicit 11-arg constructor.
TreePools{T}(
    leaf_c, sapwood_c, heartwood_c, root_c, height, crownarea, nind, sla, wooddens, is_grass::Bool,
) where {T <: Real} = TreePools{T}(
    leaf_c, sapwood_c, heartwood_c, root_c, zero(T), zero(T), height, crownarea, nind, sla, wooddens,
    zero(T), zero(T), is_grass,
)

"aboveground biomass of one individual (gC): leaf + sapwood + heartwood (`agb_tree_sum`, `tree.h:249`)."
agb_ind(t::TreePools) = t.leaf_c + t.sapwood_c + t.heartwood_c
# NB: the two below-ground wood pools are deliberately NOT in `vegc_ind` — that is what `vegc_full_ind` is
# for, and every conservation consumer in `src/` already routes on it (`conservation.jl`, `components/*.jl`).
# Keeping `vegc_ind` at the historic 4-pool sum means a seeded/grown pool cannot move a committed baseline
# that reads it; the C-faithful pool set is `vegc_full_ind` (ADR 0132 §4).
"total vegetation carbon of one individual (gC): + fine root (bg sapwood/heartwood excluded — `vegc_full_ind`)."
vegc_ind(t::TreePools) = t.leaf_c + t.sapwood_c + t.heartwood_c + t.root_c

"""
    vegc_full_ind(t::TreePools) -> Real

Total vegetation carbon of one individual INCLUDING **both** below-ground wood pools `sapwood_bg_c` and
`heartwood_bg_c` (gC/individual) — i.e. the C's own `vegc` pool set (`veg_sum_tree.c:25`, `tree.h:257`),
less the debt/excess/fruit terms F does not carry. Use this — **not** [`vegc_ind`](@ref) — wherever carbon
must CONSERVE across the S↔F demographic handoff (mortality routing, the flux-then-integrate ledger):
`vegc_ind` omits both (a v1 simplification, see its note), so routing mortality carbon on `vegc_ind`
would silently leak a seeded or grown below-ground pool.
"""
vegc_full_ind(t::TreePools) = vegc_ind(t) + t.sapwood_bg_c + t.heartwood_bg_c

"""
    reconstruct_sapwood_bg(sapwood_c, height, wooddens, rootdist, soildepth) -> Real

Reconstruct the below-ground root-sapwood pool `sapwood_bg` (gC/individual) as the C's C_LATERAL
allocation demand `root_sapwood_layer` at this individual's sapwood cross-sectional area
(`allocation_tree.c:163-189`): per soil layer `l`, a vertical requirement `(soildepth[l]/1000)·
sap_xs_area·root_sum·wooddens` plus a lateral requirement scaled by `2π/C_LATERAL²` (C_LATERAL=0.9),
where `sap_xs_area = sapwood_c/wooddens/height` and `root_sum` is the cumulative root fraction at-and-below
layer `l`. The C only grows/seeds the pool once it is already `> 0` (`allocation_tree.c:206`); the
emulator's demography is FIXED, so the pool must be seeded here at init to this equilibrium demand — see
docs/notes/sapwood_bg_design.md §4.1/§8. `rootdist` is the per-layer root fraction, `soildepth` the per-layer
thickness (mm). Grass (no woody sapwood) seeds 0. Verified by `scripts/sapwood_bg_quantification_probe.jl`.
"""
function reconstruct_sapwood_bg(sapwood_c, height, wooddens, rootdist::AbstractVector, soildepth::AbstractVector)
    (height <= 0 || wooddens <= 0 || sapwood_c <= 0) && return zero(sapwood_c * height)
    C_LATERAL = 0.9                                        # allocation_tree.c:113
    lateral = 2 * π / (C_LATERAL * C_LATERAL)              # ≈ 7.757 (allocation_tree.c:180)
    sap_xs_area = max(sapwood_c / wooddens / height, zero(sapwood_c))   # :163, :170-171
    root_sum = sum(rootdist)                               # :165-167
    rsl = zero(sap_xs_area * wooddens)
    for l in eachindex(rootdist)
        dz = soildepth[l] / 1000                           # mm → m
        rsl += dz * sap_xs_area * root_sum * wooddens                    # vertical (:179)
        rsl += dz * sap_xs_area * rootdist[l] * wooddens * lateral       # lateral  (:180)
        root_sum -= rootdist[l]                            # :186
        root_sum < 0 && (root_sum = zero(root_sum))        # :187-188
    end
    return rsl
end

"""
    sapwood_bg_seed(alloc::AllocParams, sapwood_c, height, wooddens, rootdist, soildepth) -> Real

The below-ground root-sapwood pool a stem in the C is actually **holding** at the start of a year, given
its emitted state — i.e. what to initialise `TreePools.sapwood_bg_c` with. It is
`(1 − turnover_sapwood) ×` [`reconstruct_sapwood_bg`](@ref), and that 4 % is not cosmetic (ADR 0132 §5).

The C pins the pool to the demand computed at the **post-turnover** sapwood (`allocation_tree.c:163`
runs after `turnover_tree`), and then `turnover_tree.c:126` takes `turnover_sapwood` off it again at the
start of the next year. So a stem entering year `y` holds `(1−r)·D`, not `D`. Seeding it at the bare `D`
makes the pool and the demand shrink in lockstep — post-turnover pool `(1−r)·D` versus a demand
`(1−r)·D` recomputed on the same shrunken sapwood — so the top-up `allocation_tree.c:191-193` computes is
**exactly zero**, and the below-ground sink silently disappears from any single-year or year-re-seeded
comparison. With this seed the same stem charges the honest steady-state `r·D` instead.

The underlying identity (verified in `test/testitems/sapwood_bg_growth_tests.jl`): for any
pipe-model-consistent stem the demand is **proportional to leaf carbon**,
`D = c · leaf_c · sla · wooddens / k_latosa` with `c = Σ_l dz_l·(root_sum_l + rootdist_l·2π/C_LATERAL²)`
a pure soil-geometry constant — so the annual top-up is
`(c·sla·wooddens/k_latosa)·(leaf_y − (1−r)·leaf_{y−1})`, i.e. **the sink is paid on the growth of the
leaf pool**, and a harness that re-initialises each year from the same year's state has already
discarded the quantity it is trying to measure.
"""
sapwood_bg_seed(alloc::AllocParams, sapwood_c, height, wooddens, rootdist::AbstractVector, soildepth::AbstractVector) =
    (one(alloc.turnover_sapwood) - alloc.turnover_sapwood) *
    reconstruct_sapwood_bg(sapwood_c, height, wooddens, rootdist, soildepth)

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

# Sentinel default for the below-ground soil geometry: a concretely-typed EMPTY vector, not `nothing` — a
# `Union{Nothing,AbstractVector}` kwarg would need field-narrowing at every read (the JET trap in CLAUDE.md
# §2) and buys nothing here, since "no geometry supplied" and "empty column" are the same instruction.
const _NO_BG_GEOM = Float64[]

"""
    grow_individual(alloc::AllocParams, allom::Allometry.TreeAllometry, tree::TreePools, bm_inc_ind, wscal_mean;
                    bg_growth=false, bg_rootdist=Float64[], bg_soildepth=Float64[]) -> TreePools

Advance one tree individual's carbon pools + geometry by one year (the LPJmL-FIT annual sequence
`turnover_tree` → `allocation_tree` → `allometry_tree`, `annual_tree.c:29-30`), given the accumulated
per-individual biomass increment `bm_inc_ind` (gC/individual = Σ daily NPP / `nind`) and the annual-mean
stand water scalar `wscal_mean ∈ [0,1]` (drives `lmtorm`). Returns the grown [`TreePools`](@ref). Pure
and differentiable (the pipe-model allocation solve is [`_solve_leaf_inc`](@ref); the height cap
sapwood→heartwood transfer is a smooth-a.e. `min`). Grasses are returned unchanged (v1). See the section
header for the v1 simplifications.

**Below-ground wood (`bg_growth = true`, opt-in, ADR 0132).** Runs the two below-ground pools the C
carries and F did not grow: (1) the below-ground half of `turnover_tree.c:124-130` — `sapwood_bg` sheds
`turnover_sapwood` of itself into `heartwood_bg`, which never respires and never leaves the plant; and
(2) the C_LATERAL demand of `allocation_tree.c:163-209 / :268-277` — the pool is topped back up to
[`reconstruct_sapwood_bg`](@ref) at this year's POST-turnover sapwood and last year's height, and that
top-up is **deducted from the assimilate before** the leaf/root/sapwood split, exactly as the C deducts
it. `bg_rootdist` is this individual's own per-layer root fraction (the C calls `getrootdist` per tree)
and `bg_soildepth` the per-layer thickness in mm; both must be non-empty for the block to run.

Three properties this is built to have. **It conserves**: the deduction from the assimilate equals the
increase in `sapwood_bg_c + heartwood_bg_c` exactly, which is why the sink pool cannot be dropped
(a one-field port either destroys `turnover_sapwood·sapwood_bg` per year or charges maintenance on
carbon the C does not charge — ADR 0127 §6). **It is default-inert twice over**: `bg_growth = false`
returns byte-identical results, and even with it on the C's own gate `allocation_tree.c:206` grows
nothing while the pool is 0, so an unseeded roster is unchanged. **It does not model the carbon debt**
(`allocation_tree.c:288-297`) — F carries no `debt` pool, so a carbon-starved tree takes no loan here;
in F that tree hits the stagnation guard below instead.
"""
function grow_individual(
        alloc::AllocParams, allom::Allometry.TreeAllometry, tree::TreePools{T0}, bm_inc_ind, wscal_mean;
        bg_growth::Bool = false, bg_rootdist::AbstractVector = _NO_BG_GEOM, bg_soildepth::AbstractVector = _NO_BG_GEOM,
    ) where {T0}
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
    # BELOW-GROUND half of the same turnover (`turnover_tree.c:126,131,135`): `sapwood_bg` sheds the SAME
    # rate into `heartwood_bg`. Internal to the below-ground bucket ⇒ carbon-neutral by construction; the
    # point of it is that only the sapwood half respires, so this is what makes the pool's maintenance
    # charge decay between the annual top-ups. Inert with `bg_growth = false` (pools carried through).
    sbg = convert(T, tree.sapwood_bg_c)
    hbg = convert(T, tree.heartwood_bg_c)
    if bg_growth
        turn_sbg = sbg * convert(T, alloc.turnover_sapwood)
        sbg -= turn_sbg
        hbg += turn_sbg
    end
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
    # ── below-ground root-sapwood demand (allocation_tree.c:191-209, :268-280) ──────────────────────────
    # The C tops `sapwood_bg` back up to the C_LATERAL demand at THIS year's post-turnover sapwood cross
    # section (`:163` reads `tree->ind.sapwood` after `turnover_tree` ran) and last year's height, and pays
    # for it out of the assimilate BEFORE the leaf/root/sapwood split. Two faithful details: the top-up
    # happens only when the pool is already `> 0` (`:206` — the reason the pool must be seeded at init,
    # design §4.1), and when the assimilate cannot cover `leaf_min + root_min + demand` the C takes only
    # the surplus above `leaf_min + root_min` (`:275-278`), leaving the above-ground minimum intact.
    if bg_growth && !isempty(bg_rootdist) && !isempty(bg_soildepth)
        dmd = convert(T, reconstruct_sapwood_bg(sm, H, wd, bg_rootdist, bg_soildepth))
        tinc_bg = (dmd > sbg && sbg > zero(T) && dmd > zero(T)) ? dmd - sbg : zero(T)
        floor_lr = leaf_min + root_min
        if bm_net >= floor_lr + tinc_bg
            bm_net -= tinc_bg
            sbg += tinc_bg
        elseif bm_net > floor_lr
            sbg += bm_net - floor_lr
            bm_net = floor_lr
        end
    end
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
    # `sbg`/`hbg` are the below-ground wood pair — carried through unchanged with `bg_growth = false` (the
    # static-seed behaviour), advanced by the turnover + C_LATERAL top-up above when it is on.
    # ADR 0110: carry the rooting-depth and drought-tolerance traits through growth. They are IMMUTABLE
    # after establishment in the C (`new_tree.c` sets them once), so growth must not touch them — but it
    # must not DROP them either: the 11-arg constructor would silently reset both to the unset 0 and
    # delete the per-tree rooting channel one year after establishment.
    return TreePools{T}(
        lm, sm, hm, rm, sbg, hbg, height_new, crownarea_new, convert(T, tree.nind), sla, wd,
        tree.d95max, tree.minwscal, tree.is_grass,
    )
end

"""
    grass_allocparams(::Type{T}=Float64) -> AllocParams{T}

Allocation/turnover parameters for the temperate C3 grass (PFT id 8) — the Hainich understory grass —
verbatim from the ACTIVE `par/pft_lpjmlfit.js`: `lmro_ratio` 0.8, `lmro_offset` 0.5, leaf turnover rate
1.0 (`turnover.leaf` 1.0 → full annual leaf renewal), root turnover rate 0.5 (`turnover.root` 2.0 →
`1/2` after the `fscanpft_grass.c:124` reciprocal), `reprod_cost` 0.1. The woody/Newton fields are unused
by [`grow_grass_individual`](@ref) (grass has no sapwood/heartwood/allometry solve).
"""
grass_allocparams(::Type{T} = Float64) where {T <: Real} =
    AllocParams{T}(; lmro_ratio = 0.8, lmro_offset = 0.5, turnover_leaf = 1.0, turnover_root = 0.5, reprod_cost = 0.1)

# ─────────────────────────────────────────────────────────────────────────────────────────────
# PER-PFT parameter sets (ADR 0126) — the physiology F applies PER INDIVIDUAL
# ─────────────────────────────────────────────────────────────────────────────────────────────
# Everything above ships ONE parameter set per core, and `FDiffFastCore` handed every tree beech's
# (`fast.jl`'s `pft_ids` default `t.is_grass ? 8 : 3`). ADR 0125 measured what that costs: `respcoeff`
# is 0.2 for the tropical broadleaved evergreen tree (id 0) and 1.2 for all six temperate/boreal trees,
# so at the two hot biome cells — 100 % id 0 by sapwood — F over-respired every stem 6× and its annual
# carbon balance went NEGATIVE (−223 gC/m²/yr against a truth of +1073). Four more differ materially:
# the Beer–Lambert `lightextcoeff` (0.45 needleleaved / 0.59 broadleaved), the photosynthesis optimum
# `temp_photos` (15/25 °C for the three boreal trees, 20/30 for the other four), the CO₂-assimilation
# limits `temp_co2`, and leaf/root residence (1, 2 or 4 yr). The mortality half of the same table is
# `TraitMortality.pft_mort_params` (ADR 0047).
#
# THE NUMBERS LIVE ONCE. The literals in `_pft_fdiff_row` are gated value-by-value against the
# committed `test/testitems/references/M_pft_fdiff_params.csv`, generated from the live
# `par/pft_lpjmlfit.js` by `scripts/build_pft_fdiff_params_reference.py` with `cpp -P` — the same
# preprocessor LPJmL pipes its own parameter files through (CLAUDE.md §3: never read a `.js` value by
# eye). A drifting C parameter reds the gate instead of silently disagreeing (ADR 0031).
#
# `id == 3` (beech) RETURNS TODAY'S SHIPPED DEFAULTS EXACTLY — `pft_respparams(3) == tebs_params().resp`,
# `pft_tempstressparams(3) == tebs_params().tstress`, `pft_allocparams(3) == tebs_allocparams()`,
# `pft_allometry(3) == TreeAllometry()` — and `pft_allocparams(8) == grass_allocparams()`. That is what
# makes a beech-only (or Hainich) run byte-identical whether or not the per-PFT sets are wired in.

# One row of the per-PFT table, in the fixed order the accessors below unpack. `turn_sap_yr` is `NaN`
# for grass (no woody pool). Grass tree-allometry fields are the leaftype default and unused by
# `grow_grass_individual`; grass `k_beer` is NOT unused — `_patch_fpars_soa`'s forest-floor branch and
# `_treepools_fpc` both read it.
function _pft_fdiff_row(id::Integer)
    #    respcoeff, gmin, emax, intc, alphaa, albedo_leaf, albedo_stem, albedo_litter, snowcanopyfrac,
    #    k_beer, tphot_lo, tphot_hi, tco2_lo, tco2_hi, turn_leaf_yr, turn_sap_yr, turn_root_yr,
    #    lmro_ratio, lmro_offset, reprod_cost, needleleaved, c4
    return if id == 0            # tropical broadleaved evergreen tree
        (0.2, 1.6, 10.0, 0.02, 0.6, 0.13, 0.1, 0.1, 0.4, 0.59, 20.0, 30.0, 2.0, 55.0, 2.0, 30.0, 2.0, 1.0, 0.5, 0.1, false, false)
    elseif id == 1               # temperate needleleaved evergreen tree
        (1.2, 1.0, 12.9, 0.02, 0.575, 0.137, 0.04, 0.1, 0.1, 0.45, 20.0, 30.0, -4.0, 42.0, 4.0, 25.0, 4.0, 1.0, 0.5, 0.1, true, false)
    elseif id == 2               # temperate broadleaved evergreen tree
        (1.2, 1.5, 10.0, 0.02, 0.575, 0.15, 0.04, 0.1, 0.4, 0.59, 20.0, 30.0, -4.0, 42.0, 1.0, 25.0, 1.0, 1.0, 0.5, 0.1, false, false)
    elseif id == 3               # temperate broadleaved summergreen tree (beech) — F's shipped defaults
        (1.2, 1.0, 10.0, 0.02, 0.55, 0.15, 0.04, 0.1, 0.4, 0.59, 20.0, 30.0, -4.0, 38.0, 1.0, 25.0, 1.0, 1.0, 0.5, 0.1, false, false)
    elseif id == 4               # boreal needleleaved evergreen tree
        (1.2, 0.8, 12.9, 0.06, 0.45, 0.18, 0.1, 0.1, 0.15, 0.45, 15.0, 25.0, -4.0, 38.0, 4.0, 25.0, 4.0, 1.0, 0.5, 0.1, true, false)
    elseif id == 5               # boreal broadleaved summergreen tree
        (1.2, 0.8, 10.0, 0.06, 0.4, 0.18, 0.1, 0.1, 0.15, 0.59, 15.0, 25.0, -4.0, 38.0, 1.0, 25.0, 1.0, 1.0, 0.5, 0.1, false, false)
    elseif id == 6               # boreal needleleaved summergreen tree (larch)
        (1.2, 0.3, 12.9, 0.06, 0.45, 0.12, 0.05, 0.01, 0.15, 0.45, 15.0, 25.0, -4.0, 38.0, 1.0, 25.0, 1.0, 1.0, 0.5, 0.1, true, false)
    elseif id == 7               # tropical C4 grass
        (0.2, 1.5, 10.0, 0.01, 0.5, 0.21, 0.15, 0.1, 0.4, 0.4, 20.0, 45.0, 6.0, 55.0, 1.0, NaN, 2.0, 0.6, 0.5, 0.1, false, true)
    elseif id == 8               # temperate C3 grass — F's shipped `grass_allocparams`
        (1.2, 0.8, 10.0, 0.01, 0.5, 0.23, 0.15, 0.1, 0.4, 0.5, 10.0, 30.0, -4.0, 45.0, 1.0, NaN, 2.0, 0.8, 0.5, 0.1, false, false)
    elseif id == 9               # polar C3 grass
        (1.2, 0.8, 10.0, 0.01, 0.4, 0.23, 0.1, 0.1, 0.4, 0.5, 10.0, 25.0, -4.0, 38.0, 1.0, NaN, 2.0, 0.6, 0.5, 0.1, false, false)
    else
        throw(ArgumentError("per-PFT F_diff parameters: unsupported natural PFT id $id (supported 0–9; crops out of scope)"))
    end
end

"""
    pft_respparams(id::Integer, ::Type{T}=Float64) -> RespParams{T}

Autotrophic-respiration parameters for LPJmL-FIT natural PFT `id` (the 0-based `par/pft_lpjmlfit.js`
scan order that IS the `ind` output's `Type` column). The only per-PFT field is **`respcoeff`**: 0.2 for
the tropical broadleaved evergreen tree (id 0) and the tropical C4 grass (id 7), 1.2 for every other
natural PFT — a 6× spread that ADR 0125 measured as the whole tropical half of F's growth error. The
tissue C:N ratios are the same for all natural PFTs (`cn_ratio` leaf/sapwood/root = 30/330/30), so
`cn_sapwood`/`cn_root` are set from the C for every id and the remaining kernel constants keep their
[`RespParams`](@ref) defaults. `pft_respparams(3) == tebs_params().resp`.
"""
function pft_respparams(id::Integer, ::Type{T} = Float64) where {T <: Real}
    r = _pft_fdiff_row(id)
    return RespParams{T}(; respcoeff = T(r[1]), cn_sapwood = T(330.0), cn_root = T(30.0))
end

"""
    pft_tempstressparams(id::Integer, ::Type{T}=Float64) -> TempStressParams{T}

Photosynthesis temperature limits for natural PFT `id` — the `temp_photos` optimum interval and the
`temp_co2` assimilation limits that between them set the `temp_stress.c:38-40` shape constants. Both are
per-PFT: the three boreal trees (ids 4–6) optimise at **15/25 °C** against 20/30 for the other four, the
tropical tree's `temp_co2` runs to **2/55 °C** against beech's −4/38, and the three grasses differ again.
⚠ These are NOT the `temp_stressed` MORTALITY interval (that is `TraitMortality.pft_mort_params`) and not
the `temp` establishment gate — three confusable keys (CLAUDE.md §3). `tmax`/`βgate` keep their
[`TempStressParams`](@ref) defaults. `pft_tempstressparams(3) == tebs_params().tstress`.
"""
function pft_tempstressparams(id::Integer, ::Type{T} = Float64) where {T <: Real}
    r = _pft_fdiff_row(id)
    return TempStressParams{T}(;
        temp_photos_low = T(r[11]), temp_photos_high = T(r[12]),
        temp_co2_low = T(r[13]), temp_co2_high = T(r[14]),
    )
end

"""
    pft_allocparams(id::Integer, ::Type{T}=Float64) -> AllocParams{T}

Annual allocation/turnover parameters for natural PFT `id`. The C stores turnover as a **residence time
in years** and F as a **rate per year**, so the rates here are `1/turnover.{leaf,sapwood,root}`: leaf/root
residence is 1 yr (ids 2, 3, 5, 6 and every grass leaf), **2 yr** (id 0), or **4 yr** (ids 1, 4), and
sapwood residence is 25 yr for every tree except the tropical evergreen's **30**.

`is_deciduous` stays `true` for all, and `turnover_leaf` is consumed only on the grass path. ⚠ The
reason is NOT that the PFTs are declared `summergreen` (they are, all seven — but under
`new_phenology:true` that key is never read: `daily_natural.c:123` dispatches to `phenology_gsi`, so
`phenology_tree.c`'s phenology switch is dead code). The C's real gate is the runtime latch
`tree->isphen`, and its non-latched branch drips at `1/max(pft->longevity, 1.05)`
(`turnover_daily_tree.c:38`) — **clamped to the latched branch's own 0.9524/yr**. So the two branches
coincide for any stem with leaf longevity ≤ 1.05 yr, which measured is 99.9 % of `boreal_siberia` and
99.2 % of `semiarid_sahel` stems, but only 33 % of `tropical_amazon` and 12 % of
`mediterranean_iberia` (ADR 0134). ⚠ And `pft->longevity` is a PER-INDIVIDUAL trait drawn from the
stem's own SLA (`new_tree.c:215`, emitted as the `ind` column `Longevity`), **not** the
`turnover_leaf` residence stored here — wiring this field into a non-latched branch would retain 0.75
where the truth is 0.44. Grass has no woody pool, so its
`turnover_sapwood` keeps the default. `pft_allocparams(3) == tebs_allocparams()` and
`pft_allocparams(8) == grass_allocparams()`.
"""
function pft_allocparams(id::Integer, ::Type{T} = Float64) where {T <: Real}
    r = _pft_fdiff_row(id)
    sap = isnan(r[16]) ? AllocParams{T}().turnover_sapwood : T(1.0 / r[16])
    return AllocParams{T}(;
        lmro_ratio = T(r[18]), lmro_offset = T(r[19]), reprod_cost = T(r[20]),
        turnover_leaf = T(1.0 / r[15]), turnover_sapwood = sap, turnover_root = T(1.0 / r[17]),
    )
end

"""
    pft_allometry(id::Integer, ::Type{T}=Float64) -> Allometry.TreeAllometry{T}

Tree allometry constants for natural PFT `id`: the needleleaved trees (ids 1, 4, 6) get the gymnosperm
set (`allom1` 101.34, `allom2` 31.4093, `allom3` 0.665, `kpr` 1.4163) and the broadleaved ones the
angiosperm default, with each PFT's own Beer–Lambert `k_beer` (`lightextcoeff`) written in — including
the grasses' (0.4 for tropical C4, 0.5 for the two C3), which is read by `_patch_fpars_soa`'s
forest-floor branch and by [`individual_from_pools`](@ref)'s `fpc`. `sla`/`wooddens` keep their defaults:
both are per-INDIVIDUAL traits carried by [`TreePools`](@ref) and [`grow_individual`](@ref) reads them
from the tree, never from here. `pft_allometry(3) == Allometry.TreeAllometry{T}()`.
"""
function pft_allometry(id::Integer, ::Type{T} = Float64) where {T <: Real}
    r = _pft_fdiff_row(id)
    base = r[21] ? Allometry.gymnosperm(Allometry.TreeAllometry{T}) : Allometry.TreeAllometry{T}()
    fns = fieldnames(Allometry.TreeAllometry{T})
    nt = NamedTuple{fns}(map(f -> getfield(base, f), fns))
    return Allometry.TreeAllometry{T}(; merge(nt, (; k_beer = T(r[10])))...)
end

"""
    pft_canopy_traits(id::Integer, ::Type{T}=Float64) -> NamedTuple

The per-PFT constants a caller needs to build one [`Individual`](@ref) template (plus `gmin`, which
lives in [`WaterParams`](@ref) rather than on the individual): `(; gmin, emax, intc, alphaa,
albedo_leaf, albedo_stem, albedo_litter, snowcanopyfrac, k_beer, path)`. `path` is `:c3` for every tree
and for the two C3 grasses, `:c4` for the tropical C4 grass (id 7).

Use this instead of hard-coding beech's values when reconstructing a stand: `alphaa`, `albedo_leaf` and
`emax` are also emitted PER STEM by the C's `ind` output (prefer those when you have them — they are the
individual's own), but `intc`, `albedo_stem`, `albedo_litter`, `snowcanopyfrac` and `gmin` are not, and
they are genuinely per-PFT (`intc` 0.02 vs 0.06 between temperate and boreal trees, `gmin` 0.3–1.6).
"""
function pft_canopy_traits(id::Integer, ::Type{T} = Float64) where {T <: Real}
    r = _pft_fdiff_row(id)
    return (;
        gmin = T(r[2]), emax = T(r[3]), intc = T(r[4]), alphaa = T(r[5]), albedo_leaf = T(r[6]),
        albedo_stem = T(r[7]), albedo_litter = T(r[8]), snowcanopyfrac = T(r[9]), k_beer = T(r[10]),
        path = r[22] ? :c4 : :c3,
    )
end

"""
    PFTPhys{T}

The per-PFT parameter bundle F applies to ONE individual: `resp` ([`RespParams`](@ref), i.e.
`respcoeff`), `alloc` ([`AllocParams`](@ref), i.e. turnover), `allom`
([`Allometry.TreeAllometry`](@ref), i.e. the crown/height coefficients and `k_beer`), `tstress`
([`TempStressParams`](@ref), i.e. the `temp_photos`/`temp_co2` limits) and the minimum canopy
conductance `gmin` (a [`WaterParams`](@ref) field, read per-PFT by `gp_sum.c`).

`tstress` is the one field that IS already carried per-`Individual`: it is in the bundle so that
enabling the channel applies **every** per-PFT parameter F knows about rather than a subset —
[`individuals_from_pools`](@ref) writes it into each rebuilt individual, overriding the template's.
Partial application is the failure mode this design exists to prevent (a stand running its own
`respcoeff` while still optimising photosynthesis at beech's 20/30 °C would be a mixed basis, and
ADR 0060 is the record of what a mixed basis costs). `photo` deliberately stays the caller's: its `sla`
is a per-INDIVIDUAL trait from the roster and its C3/C4 `path` is a caller decision
([`pft_canopy_traits`](@ref) exposes the C's value).

Built per individual by [`pft_phys`](@ref) and travelling as a plain `Vector{PFTPhys{T}}` ALONGSIDE the
roster — deliberately not a field of `Individual`, for the same two reasons `rootdists` is not
(ADR 0110): a heap-allocated field on a struct the Enzyme reverse pass differentiates through aborts the
test process, and an extra `Individual` field would need a back-compatible constructor whose default
CANNOT be byte-identical (the shipped `p.resp.respcoeff` is 1.2 from `tebs_params`, while
`RespParams()`'s own default is 1.0). Passing it as `nothing` therefore means "use the core's single
shared set", which is exactly the pre-ADR-0126 behaviour. `PFTPhys` is isbits, so Enzyme sees the vector
as constant data.
"""
struct PFTPhys{T <: Real}
    resp::RespParams{T}
    alloc::AllocParams{T}
    allom::Allometry.TreeAllometry{T}
    tstress::TempStressParams{T}
    gmin::T
end
_wt(::PFTPhys{T}) where {T} = T

"""
    pft_phys(id::Integer, ::Type{T}=Float64) -> PFTPhys{T}
    pft_phys(ids::AbstractVector, ::Type{T}=Float64) -> Vector{PFTPhys{T}}

The [`PFTPhys`](@ref) bundle for natural PFT `id`, or one per entry of `ids` (the per-individual form the
canopy consumes). `pft_phys(3)` is exactly F's shipped beech configuration, so a beech-only stand is
byte-identical with or without the bundle.
"""
pft_phys(id::Integer, ::Type{T} = Float64) where {T <: Real} = PFTPhys{T}(
    pft_respparams(id, T), pft_allocparams(id, T), pft_allometry(id, T),
    pft_tempstressparams(id, T), T(_pft_fdiff_row(id)[2]),
)
pft_phys(ids::AbstractVector, ::Type{T} = Float64) where {T <: Real} =
    PFTPhys{T}[pft_phys(Int(id), T) for id in ids]

"""
    GrassEstabParams{T}

Grass annual establishment/re-seeding increment (`establishment_grass.c` individual mode). Each year, if
the total patch FPC `fpc_total < 1`, every establishing grass PFT adds sapling biomass
`sapl_leaf·est_pft` (leaf) and `sapl_root·est_pft` (root) with `est_pft = (1−fpc_total)/n_est`
(`establishment_grass.c:38-49`; `n_est` = number of establishing grass PFTs). This is the mechanism that
maintains the C's DIM-patch grass where the light-limited NPP alone is below the annual turnover (the
grass would otherwise go extinct — docs §25/§26). `sapl_leaf = lai_sapl/sla`, `sapl_root =
sapl_leaf/lmro_ratio` (`fscanpft_grass.c:140-141`; temperate C3 grass id 8: `lai_sapl` 0.1, `sla`
0.042242, `lmro_ratio` 0.8 ⇒ `sapl_leaf ≈ 2.367`, `sapl_root ≈ 2.959` gC/m²).
"""
struct GrassEstabParams{T <: Real}
    sapl_leaf::T
    sapl_root::T
end

"""
    grass_estabparams(::Type{T}=Float64) -> GrassEstabParams{T}

Temperate C3 grass (PFT id 8) establishment increment from the ACTIVE `par/pft_lpjmlfit.js`
(`lai_sapl` 0.1, `sla` 0.042242, `lmro_ratio` 0.8) via `fscanpft_grass.c:140-141`. See
[`GrassEstabParams`](@ref).
"""
function grass_estabparams(::Type{T} = Float64) where {T <: Real}
    sapl_leaf = T(0.1) / T(0.042242)             # lai_sapl / sla.median
    return GrassEstabParams{T}(sapl_leaf, sapl_leaf / T(0.8))   # sapl_root = sapl_leaf / lmro_ratio
end

"""
    grass_treepools(agb, vegc, sla; nind=1.0, wooddens=0.0) -> TreePools

Reconstruct a per-area grass [`TreePools`](@ref) from the LPJmL-FIT `ind`-output `agb`/`vegc` (gC/m², the
`hainich_individuals_*.csv` grass columns). Grass leaf carbon = `agb` (`agb_grass.c:25` = `leaf·nind`,
i.e. `lai/sla` per-m²); root carbon = `vegc − agb` (grass has no woody pools, so `vegc = leaf + root`).
The **per-area convention** carries `crownarea = nind = 1` so the pool→structure recompute reproduces the
grass canopy: `lai = leaf_c·sla` and `fpc = 1 − e^{−k·lai}` (both [`individual_from_pools`](@ref) and
[`_patch_fpars_soa`](@ref) require `crownarea > 0` and `nind > 0`); `height = sapwood_c = heartwood_c = 0`.
Advance one year with [`grow_grass_individual`](@ref).
"""
function grass_treepools(agb, vegc, sla; nind = 1.0, wooddens = 0.0)
    T = promote_type(typeof(float(agb)), typeof(float(vegc)), typeof(float(sla)))
    leaf = convert(T, agb); root = max(convert(T, vegc) - leaf, zero(T))
    return TreePools{T}(leaf, zero(T), zero(T), root, zero(T), one(T), convert(T, nind), convert(T, sla), convert(T, wooddens), true)
end

"""
    grow_grass_individual(alloc::AllocParams, tree::TreePools, bm_inc_ind, wscal_mean) -> TreePools

Advance one GRASS cohort's leaf/root carbon by one year — a faithful differentiable port of the LPJmL-FIT
NATURAL-vegetation annual grass sequence `turnover_grass.c` → `allocation_grass.c` (`annual_grass.c:29-30`,
`landusetype == NATURAL`). Given the accumulated per-area biomass increment `bm_inc_ind` (gC/m² = Σ daily
NPP, the per-m² grass basis with `nind = 1`) and the annual-mean stand water scalar `wscal_mean ∈ [0,1]`
(drives `lmtorm`). Pure and differentiable — closed-form carbon math (no allometry solve). Returns the
grown grass [`TreePools`](@ref) (`sapwood_c = heartwood_c = height = 0` preserved; `crownarea`/`nind`/`sla`
carried). Non-grass individuals are returned unchanged (grow trees with [`grow_individual`](@ref)).

Turnover (NATURAL, no-N): leaf turns over DAILY (`turnover_daily_grass.c`) and root MONTHLY
(`turnover_monthly_grass.c`), each accumulating against the within-year-constant pool → the annual pool is
reduced by `pool·turnover_rate` (`leaf → leaf·(1 − r_leaf)`, `root → root·(1 − r_root)`). Reproduction
(`turnover_grass.c:45`) removes `bm·reprod_cost` before allocation (the growing-days fraction is exactly 1
on the NATURAL path — `daily_natural.c:82`). Allocation (`allocation_grass.c:87-118`, natural-veg full-reallocation, `with_nitrogen=no`
⇒ `vscal = 1`): `lmtorm = lmro_ratio·(lmro_offset + (1−lmro_offset)·min(1, wscal))`; the leaf increment
solves today's `lmtorm` (`inc_leaf = (bm + root − leaf/lmtorm)/(1 + 1/lmtorm)`) with the no-reallocation
caps (`inc_leaf ∈ [·, bm]`) and the negative-leaf reduction branch (`allocation_grass.c:97-110`). The
`min(1, wscal)` is the AD-safe `smoothmin` (as [`grow_individual`](@ref)).
"""
function grow_grass_individual(alloc::AllocParams, tree::TreePools{T0}, bm_inc_ind, wscal_mean) where {T0}
    tree.is_grass || return tree
    T = promote_type(T0, typeof(float(bm_inc_ind)), typeof(float(wscal_mean)))
    bm = convert(T, bm_inc_ind)
    leaf = convert(T, tree.leaf_c); root = convert(T, tree.root_c)
    # ── turnover_grass.c (NATURAL, no-N): annual pool reduction = pool·rate (leaf daily, root monthly) ──
    leaf_t = leaf * (one(T) - convert(T, alloc.turnover_leaf))   # temperate C3: rate 1.0 ⇒ full annual leaf renewal
    root_t = root * (one(T) - convert(T, alloc.turnover_root))   # rate 0.5 ⇒ 2-yr root residence
    # ── reproduction reserve removed from bm_inc before allocation (turnover_grass.c:45; the growing-days
    # fraction = patch->growing_days/NDAYYEAR is EXACTLY 1 on the NATURAL path — growing_days increments
    # unconditionally each day, daily_natural.c:82, reset only at year end) ──
    bm_net = bm >= 0 ? bm * (one(T) - convert(T, alloc.reprod_cost)) : bm
    # ── allocation_grass.c natural-veg branch (with_nitrogen=no ⇒ vscal=1 ⇒ min(vscal,wscal)=min(1,wscal)) ──
    lmtorm = convert(T, alloc.lmro_ratio) *
        (convert(T, alloc.lmro_offset) + (one(T) - convert(T, alloc.lmro_offset)) * smoothmin(one(T), convert(T, wscal_mean), T(30.0)))
    inc_leaf = zero(T); inc_root = zero(T)
    if lmtorm < T(1.0e-10)
        inc_leaf = zero(T); inc_root = bm_net                       # allocation_grass.c:89-93
    else
        inc_leaf = (bm_net + root_t - leaf_t / lmtorm) / (one(T) + one(T) / lmtorm)   # :96
        if inc_leaf < zero(T)                                       # negative allocation to leaf (:97-110)
            inc_root = bm_net
            inc_leaf = (root_t + inc_root) * lmtorm - leaf_t
        else
            (bm_net > 0 && inc_leaf > bm_net) && (inc_leaf = bm_net)   # no reallocation from roots to leaves (:113-114)
            inc_root = bm_net - inc_leaf                            # :115
        end
    end
    leaf_new = leaf_t + inc_leaf                                    # allocation_grass.c:125
    root_new = root_t + inc_root                                    # :126
    return TreePools{T}(
        leaf_new, zero(T), zero(T), root_new, zero(T), convert(T, tree.crownarea),
        convert(T, tree.nind), convert(T, tree.sla), convert(T, tree.wooddens), true,
    )
end

"""
    _turnover_litter(alloc::AllocParams, tree::TreePools, bm_inc_ind) -> (reprod, leaf_shed, root_shed)

The carbon (gC/individual) that LEAVES one individual's pools during a single annual growth step
([`grow_individual`](@ref) for trees, [`grow_grass_individual`](@ref) for grass) — as accounted
reproduction + leaf/root turnover litter fluxes, computed WITHOUT re-running or mutating growth. This is
the INDEPENDENT measurement used to (a) verify that growth conserves carbon and (b) feed the
flux-then-integrate carbon ledger (`conservation.jl`) so the S↔F demographic handoff neither creates nor
destroys carbon.

For a growing individual the annual balance is `Δvegc_full_ind = bm_net − (leaf_shed + root_shed)`, with
`bm_net = bm_inc_ind·(1 − reprod_cost)` (for `bm_inc_ind ≥ 0`) and reproduction
`reprod = bm_inc_ind·reprod_cost` a SEPARATE flux (→ establishment/litter). Sapwood→heartwood turnover and
the height-cap transfer are INTERNAL (pool↔pool, not litter). Turnover: tree summergreen leaf shed =
`leaf_c/deciduous_leaf_div` (else `leaf_c·turnover_leaf`), grass leaf shed = `leaf_c·turnover_leaf`, root
shed = `root_c·turnover_root`. A stagnating tree (`bm_net ≤ 0` or `height ≤ 0`) is frozen by
[`grow_individual`](@ref)'s early return ⇒ all three terms are 0; grass has no stagnation guard (it always
turns over).

NOTE (edge branches): in the rare negative-leaf allocation branches (`allocation_tree.c:341` /
`allocation_grass.c:97`) the pool re-derivation can move a little extra leaf carbon to litter beyond these
three terms. The carbon LEDGER routes per-cohort litter as the EXACT growth residual
`bm_applied − Δvegc_full` (branch-agnostic, conserves regardless); THIS formula is exact on the normal
(dominant) growth path — the litter-closure gate asserts the two agree there.
"""
function _turnover_litter(alloc::AllocParams, tree::TreePools{T}, bm_inc_ind) where {T}
    bm = convert(T, bm_inc_ind)
    rc = convert(T, alloc.reprod_cost)
    if tree.is_grass
        reprod = bm >= zero(T) ? bm * rc : zero(T)
        leaf_shed = convert(T, tree.leaf_c) * convert(T, alloc.turnover_leaf)
        root_shed = convert(T, tree.root_c) * convert(T, alloc.turnover_root)
        return (reprod, leaf_shed, root_shed)
    end
    # tree stagnation guard mirrors grow_individual (bm_net ≤ 0 or height ≤ 0 ⇒ frozen ⇒ no turnover)
    bm_net = bm >= zero(T) ? bm * (one(T) - rc) : bm
    (convert(T, tree.height) <= zero(T) || bm_net <= zero(T)) && return (zero(T), zero(T), zero(T))
    reprod = bm * rc
    leaf_shed = alloc.is_deciduous ?
        convert(T, tree.leaf_c) / convert(T, alloc.deciduous_leaf_div) :
        convert(T, tree.leaf_c) * convert(T, alloc.turnover_leaf)
    root_shed = convert(T, tree.root_c) * convert(T, alloc.turnover_root)
    return (reprod, leaf_shed, root_shed)
end

# ── per-patch layered Beer–Lambert light (getfpar.c) → per-individual leaf-on fpar ────────────────
# Recomputes each tree's absorbed-PAR fraction as heights change across years (the light competition
# feedback). Fixed `nlayers` loop (AD-safe; layers above the tallest tree contribute 0 naturally). The
# height/boleht layer-membership tests compare by value under ForwardDiff, so the arithmetic derivatives
# (atoh, exp, the uptake distribution) flow through. Grasses take the transmitted forest-floor light.
#
# ENZYME NOTE (scale-up step 7b-multiyear, docs §17). The layered light is implemented on a
# STRUCT-OF-ARRAYS interface ([`_patch_fpars_soa`](@ref), plain `Vector{T}` field arrays), NOT directly on
# `Vector{TreePools}`. On the MULTI-YEAR structure-feedback path (where the trees fed here are the ACTIVE
# outputs of [`grow_individual`](@ref)), Enzyme reverse cannot type-analyze a `Vector{TreePools}` whose
# branchy struct elements are field-scattered (`trees[i].height → scratch[i]`) — the struct's trailing
# `is_grass::Bool` + padding read as `Anything` and the reverse pass raises `EnzymeNoTypeError`. Keeping
# the differentiated state as plain float arrays avoids the struct memcpy entirely (Enzyme-vs-FD match
# 1e-12 through the coupled multi-year rollout). The `Vector{TreePools}` method below is a thin unpacking
# wrapper (the diagnostic/non-AD path — numerically identical); it is NOT on the Enzyme multi-year path.
function _patch_fpars(trees::AbstractVector{TreePools{T}}, allom::Allometry.TreeAllometry; kwargs...) where {T}
    n = length(trees)
    heights = T[t.height for t in trees]; leafcs = T[t.leaf_c for t in trees]
    slas = T[t.sla for t in trees]; ninds = T[t.nind for t in trees]
    crownareas = T[t.crownarea for t in trees]; isgrass = Bool[t.is_grass for t in trees]
    return _patch_fpars_soa(heights, leafcs, slas, ninds, crownareas, isgrass, allom; kwargs...)
end

"""
    _patch_fpars_soa(heights, leafcs, slas, ninds, crownareas, isgrass, allom;
                     nlayers=60, vstep=2.0, k_lambert=0.5) -> Vector

Struct-of-arrays core of the per-patch layered Beer–Lambert light ([`_patch_fpars`](@ref)) — the
per-individual pool fields are passed as plain `Vector{T}` arrays (`heights`, `leafcs`=leaf_c, `slas`,
`ninds`, `crownareas`) + a `Vector{Bool}` grass mask. This form is Enzyme-typeable on the multi-year
structure-feedback path (see the `_patch_fpars` ENZYME NOTE); the arithmetic is byte-identical to the
`Vector{TreePools}` method.
"""
function _patch_fpars_soa(
        heights::AbstractVector{T}, leafcs::AbstractVector, slas::AbstractVector, ninds::AbstractVector,
        crownareas::AbstractVector, isgrass::AbstractVector{Bool}, allom::Allometry.TreeAllometry;
        nlayers::Int = 60, vstep = 2.0, k_lambert = 0.5, kbeers = nothing
    ) where {T}
    vs = T(vstep); kl = T(k_lambert)
    n = length(heights)
    fpars = zeros(T, n)
    # per-tree leaf-area-per-height (atoh) and bole/top heights; grass excluded from the tree canopy
    atoh = zeros(T, n); top = zeros(T, n); bole = zeros(T, n); istree = fill(false, n)
    for i in 1:n
        (isgrass[i] || heights[i] <= 0 || leafcs[i] <= 0) && continue
        istree[i] = true
        top[i] = heights[i]
        bole[i] = (one(T) - allom.crownlength) * heights[i]
        cd = max(heights[i] - bole[i], T(1.0e-6))
        atoh[i] = min(leafcs[i] * slas[i] / cd, T(40.0)) * ninds[i]        # leaf area density × nind (patch basis)
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
    # grasses: transmitted forest-floor light × their own Beer–Lambert absorption. ADR 0126: `kbeers`
    # (per-individual, from the PFT's own `lightextcoeff`) overrides the shared `allom.k_beer`; `nothing`
    # ⇒ byte-identical. Only the grass branch reads it — the TREE canopy above attenuates with the
    # patch-level `k_lambert` (`light_ind.c`), which is not a PFT parameter.
    for i in 1:n
        if isgrass[i] && leafcs[i] > 0
            lai_g = crownareas[i] > 0 ? leafcs[i] * slas[i] / crownareas[i] : zero(T)
            kb = kbeers === nothing ? allom.k_beer : kbeers[i]
            fpars[i] = fpar_bottom * (one(T) - exp(-convert(T, kb) * lai_g))
        end
    end
    return fpars
end

"""
    individual_from_pools(tmpl::Individual, tree::TreePools, allom, fpar; k_beer=allom.k_beer) -> Individual

Build the daily-canopy [`Individual`](@ref) from prognostic [`TreePools`](@ref): recompute `lai =
leaf_c·sla/crownarea` (`lai_tree.c`) and `fpc = crownarea·nind·(1−e^{−k·lai})` (`fpc_tree.c`), carry the
pools into `c_sapwood`/`c_root`, and reuse the PFT constants from the template individual `tmpl`. `fpar`
is the (recomputed) layered absorbed-PAR fraction from [`_patch_fpars`](@ref).

`k_beer` overrides the Beer–Lambert extinction used for THIS individual's `fpc` (ADR 0126): it is per-PFT
in the C (`lightextcoeff` 0.45 needleleaved / 0.59 broadleaved / 0.4–0.5 grass, i.e. the `K_LAMBERT_BEER_*`
macros), while `allom` carries one value. `tstress` likewise replaces the template's photosynthesis
temperature limits with this individual's PFT set (`temp_photos` 15/25 °C for the three boreal trees vs
20/30 for the other four). Both defaults reproduce the shared/template behaviour exactly.
"""
function individual_from_pools(
        tmpl::Individual{T}, tree::TreePools{T}, allom::Allometry.TreeAllometry, fpar::T;
        k_beer = allom.k_beer, tstress = tmpl.tstress,
    ) where {T}
    ca = tree.crownarea
    laival = (tree.leaf_c > 0 && ca > 0) ? tree.leaf_c * tree.sla / ca : zero(T)
    fpc_i = ca > 0 ? ca * tree.nind * (one(T) - exp(-convert(T, k_beer) * laival)) : zero(T)
    return Individual{T}(
        fpar, fpc_i, tmpl.alphaa, tmpl.albedo_leaf, tmpl.emax, tree.sapwood_c, tree.root_c, tree.sapwood_bg_c,
        laival, tmpl.intc, tmpl.albedo_stem, tmpl.albedo_litter, tmpl.snowcanopyfrac, tree.nind,
        tmpl.photo, tstress, tree.is_grass,
    )
end

"""
    individuals_from_pools(tmpls, pools, allom, fpars, soil; per_tree=false, pftphys=nothing) -> Vector{Individual}

Rebuild the whole per-individual roster for a year, returning `(inds, rootdists)`. The ONE place the
per-tree root profiles ([`per_tree_rootdists`](@ref)) are built, so every annual-rebuild call site behaves
identically and a new one cannot silently omit them. `per_tree=false` (the default, and what every
pre-ADR-0110 call site gets) returns `rootdists === nothing` ⇒ byte-identical.

`rootdists` is deliberately returned ALONGSIDE the roster rather than stored inside `Individual`: a
`Vector` field in that struct aborts the Enzyme reverse pass (see the note on `Individual`). Pass it to
[`daily_step_canopy`](@ref) as the `rootdists` keyword, where it is constant data.

Called once a year, so the profile construction — including the `betaroot_from_d95max` bisection — is
outside the daily loop and off the Enzyme reverse path.

`pftphys` (a per-individual `Vector{`[`PFTPhys`](@ref)`}`, ADR 0126) gives each individual its OWN
Beer–Lambert `k_beer` for the `fpc` recompute and its own photosynthesis temperature limits `tstress`
(overriding the template's); `nothing` keeps the shared `allom.k_beer` and each template's own `tstress`
⇒ byte-identical.
"""
function individuals_from_pools(
        tmpls, pools::AbstractVector, allom::Allometry.TreeAllometry, fpars, soil::SoilColumn{T};
        per_tree::Bool = false, pftphys = nothing,
    ) where {T}
    inds = Individual{T}[
        individual_from_pools(
                tmpls[i], pools[i], allom, fpars[i];
                k_beer = pftphys === nothing ? allom.k_beer : pftphys[i].allom.k_beer,        # ADR 0126
                tstress = pftphys === nothing ? tmpls[i].tstress : pftphys[i].tstress,        # ADR 0126
            ) for i in eachindex(pools)
    ]
    return (inds, per_tree ? per_tree_rootdists(pools, soil) : nothing)
end

"""
    rollout_canopy_years(p, alloc, allom, st0, trees0, tmpls, soil, yearly_forcings;
                         phen_params=nothing, nlayers=60, n_top1m=3) -> (trees, st, pools_by_year, annual)

Multi-year COUPLED rollout of one patch canopy: for each year, (1) recompute per-individual layered
`fpar` from the current [`TreePools`](@ref) heights ([`_patch_fpars`](@ref)); (2) build the daily
[`Individual`](@ref)s ([`individual_from_pools`](@ref)); (3) run the differentiable daily canopy
([`rollout_daily_canopy`](@ref)) accumulating each individual's per-m² `bm_inc = Σ npp_ind` and the
annual-mean stand water scalar; (4) GROW each individual from its per-individual `bm_inc/nind` — trees via
[`grow_individual`](@ref) (pipe-model allocation), grasses via [`grow_grass_individual`](@ref) (the
`allocation_grass.c` natural-veg branch; `galloc` = the grass allocation/turnover params). This is the
flux-then-integrate S↔F loop (DESIGN §8) with the allocation as the carbon handoff. Soil water carries
across years (continuous); GSI phenology cold-starts each year (v1). Returns
the final `TreePools`, final soil state, the per-year pools trajectory, and per-year cell aggregates
`(gpp, npp, agb, vegc, mean_height, wscal_mean)` (per-m²/m).

`bm_inc_ext` (optional; a per-year vector of per-individual per-m² `bm_inc`) overrides the self-computed
`Σ npp_ind` — retained as a kernel-isolation lever (as sessions 5–7 used for the FAPAR/PET C-outputs) to
isolate the allocation/structure growth from the canopy NPP. As of docs §13 the self-computed canopy NPP
is CALIBRATED (positive, CUE≈0.52 vs the C's 0.46), so the DEFAULT (`bm_inc_ext=nothing`) is fully
self-driven — the crutch is no longer load-bearing.

**Grass defaults (docs §26.3).** The validated-faithful grass config is ON by default: the §26.2
photosynthesis `grass_demand_gate` (reconstructs `p` at the C's sharp `βgpd_gate=1e8`, so the
self-driven grass gets the daily-flux physics validated against the C's own daily grass NPP) and §22
`grass_estab` establishment (re-seeding that keeps dim-patch grass from extincting). Both are
grass-only ⇒ a tree-only rollout is byte-identical, and the Enzyme/decadal path
[`rollout_canopy_years_gpp`](@ref) is unchanged. Pass `grass_demand_gate=false` / `grass_estab=nothing`
for the pre-§26.3 gate-off reference.
"""
# foliar projective cover of a `TreePools` (fpc_tree.c / per-area grass), the formula
# `individual_from_pools` uses (`crownarea·nind·(1−e^{−k_beer·lai})`, `lai = leaf_c·sla/crownarea`) —
# reused for the grass-establishment `fpc_total` gate without rebuilding the daily `Individual`.
function _treepools_fpc(tree::TreePools{T}, allom::Allometry.TreeAllometry; k_beer = allom.k_beer) where {T}
    ca = tree.crownarea
    (tree.leaf_c <= zero(T) || ca <= zero(T)) && return zero(T)
    lai = tree.leaf_c * tree.sla / ca
    return ca * tree.nind * (one(T) - exp(-convert(T, k_beer) * lai))
end

# §26.3 — the VALIDATED-faithful grass photosynthesis DEMAND-GATE (`water_stressed.c:196` `gpd>1e-5`;
# docs §26/§26.2) as a reconstructed-`p` toggle for [`rollout_canopy_years`](@ref). Returns `p` with its
# `WaterParams.grass_demand_gate` set to `on`; when turning ON it also pins the sharp `βgpd_gate=1e8`
# (the C's hard step — exactly the value `scripts/grass_daily_curve_fdiff.jl` validated against the C's
# NEW daily grass NPP output). `rollout_canopy_years` is the NON-differentiable diagnostic/self-driven
# path, so the steep sigmoid costs NO gradient there; the Enzyme/decadal path `rollout_canopy_years_gpp`
# reads `p.water` directly and is UNCHANGED (stays gate-off + gradient-stable). Reconstruction is
# fieldnames-driven (robust to future `WaterParams` fields) and returns `p` UNCHANGED when already in the
# requested state — so a gate-off request on a gate-off `p` is byte-identical. The gate is grass-gated in
# [`daily_step_canopy`](@ref) (`ind.is_grass ? w.grass_demand_gate : w.tree_demand_gate`), so a TREE-ONLY
# rollout is byte-identical regardless of this toggle — UNLESS `tree_demand_gate` is also on (ADR 0131),
# in which case turning the grass gate ON re-pins the SHARED `βgpd_gate` to `1e8` and thereby sharpens the
# tree gate too. That is the intended coupled-core behaviour (the C's step is hard), but it means a
# `tree_demand_gate` arm must record which `βgpd_gate` it ran at.
const _GRASS_GATE_βSHARP = 1.0e8
function _with_grass_gate(p::FDiffParams{T}, on::Bool) where {T}
    w0 = p.water
    (w0.grass_demand_gate == on && (!on || w0.βgpd_gate == T(_GRASS_GATE_βSHARP))) && return p
    w = WaterParams{T}(
        Any[
            f === :grass_demand_gate ? on :
                (f === :βgpd_gate && on ? T(_GRASS_GATE_βSHARP) : getfield(w0, f))
                for f in fieldnames(WaterParams)
        ]...,
    )
    return FDiffParams{T}(p.photo, p.tstress, w, p.resp, p.allom, p.nlambda, p.ω)
end

function rollout_canopy_years(
        p::FDiffParams, alloc::AllocParams, allom::Allometry.TreeAllometry, st0::FDiffStateML,
        trees0::AbstractVector{TreePools{T}}, tmpls::AbstractVector{Individual{T}}, soil::SoilColumn,
        yearly_forcings; phen_params = nothing, nlayers::Int = 60, n_top1m::Int = 3, bm_inc_ext = nothing,
        galloc::AllocParams = grass_allocparams(T), hooks::FluxHooks = _NO_HOOKS, pft_ids = nothing,
        grass_estab = grass_estabparams(T), grass_demand_gate::Bool = true,
        grass_lf_mode::Symbol = :linear, phen_params_by_pft = nothing, bg_growth::Bool = false
    ) where {T}
    # §26.3 — the coupled multi-year rollout DEFAULTS to the validated-faithful grass config: the §26.2
    # photosynthesis demand-gate (`grass_demand_gate=true`, reconstructing `p` at the C's sharp step) and
    # §22 grass establishment (`grass_estab` on). Together they give the SELF-DRIVEN grass the flux physics
    # §26.2 validated against the C's daily grass NPP AND the anti-extinction re-seeding §22 needs. They are
    # coupled: WITHOUT the gate the deep-shade grass over-shoots on the light-insensitive soft floor; WITH the
    # gate but WITHOUT establishment the (now-suppressed) dim-patch grass extincts (11/25 self-driven, docs
    # §26.3) — so each mechanism alone is worse, and only the pair gives the gate-corrected level with no
    # extinction. Both are GRASS-gated / grass-only ⇒ a tree-only rollout is byte-identical, and the
    # Enzyme/decadal path `rollout_canopy_years_gpp` (which reads `p.water` directly, gate off) is untouched.
    # Pass `grass_demand_gate=false` / `grass_estab=nothing` for the gate-off, no-establishment reference.
    p = _with_grass_gate(p, grass_demand_gate)
    trees = collect(trees0)
    st = st0
    n = length(trees)
    # PER-PFT GSI phenology (the FIT config's `new_phenology:true`): each individual advances its own PFT's
    # GSI leaf-display, and — decisively for the coupled rollout — a GRASS drives its light limiter with the
    # tree-attenuated forest-floor light (`phenology_gsi.c:30-35`), so a shaded understory grass is leaf-on
    # far LESS than the canopy trees. Without this the grass ran the patch-wide BEECH GSI and its self-driven
    # leaf over-grew ~×4 at moderate shade (docs §24-25). `pft_ids` defaults to the Hainich mapping
    # grass→8 (temperate C3), tree→3 (beech): the beech GSI `pft_phenparams(3) === tebs_phenparams`, so the
    # id-3 trees' leaf display is BYTE-IDENTICAL to the previous patch-wide-beech behaviour (per-PFT and
    # scalar make the same call for id 3) — only the grass changes. Pass explicit `pft_ids` for other PFTs.
    pids = pft_ids === nothing ? Int[t.is_grass ? 8 : 3 for t in tmpls] : pft_ids
    # ADR 0132 below-ground wood geometry, hoisted once: same-eltype EMPTY vectors are the "off" sentinel,
    # so the `grow_individual` kwargs stay concretely typed on both branches.
    bg_none = similar(soil.rootdist, 0)
    bg_sd = bg_growth ? soil.soildepth : similar(soil.soildepth, 0)
    pools_by_year = Vector{Vector{TreePools{T}}}()
    annual = NamedTuple[]
    for (yr, forc) in enumerate(yearly_forcings)
        fpars = _patch_fpars(trees, allom; nlayers = nlayers)
        (inds, rdists) = individuals_from_pools(tmpls, trees, allom, fpars, soil; per_tree = p.water.per_tree_roots)   # ADR 0110
        (st, days) = rollout_daily_canopy(
            p, st, inds, soil, forc; phen_params = phen_params, n_top1m = n_top1m, hooks = hooks,
            pft_ids = pids, grass_lf_mode = grass_lf_mode, phen_params_by_pft = phen_params_by_pft,
            rootdists = rdists,   # ADR 0110 — rebuilt with the roster each year, constant within it
        )
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
        # Σ npp_ind — a kernel-isolation lever (as sessions 5–7 used for the FAPAR/PET C-outputs). As of
        # docs §13 the self-computed canopy NPP is CALIBRATED (the growth-resp floor βgrowth + fine-root
        # phen-gating took annual self-NPP −25 → +663 gC/m²/yr), so the DEFAULT is fully self-driven.
        bm_year = bm_inc_ext === nothing ? bm_perm2 : convert.(T, bm_inc_ext[yr])
        newtrees = Vector{TreePools{T}}(undef, n)
        for i in 1:n
            tr = trees[i]
            bm_ind = bm_year[i] / (tr.nind + T(1.0e-12))
            # ADR 0132: with `bg_growth` on, each tree tops its below-ground root-sapwood pool up to the
            # C_LATERAL demand computed on ITS OWN root profile when one exists (`rdists`, ADR 0110 — the
            # C calls `getrootdist` per individual, `allocation_tree.c:159`), else the shared cell profile.
            bg_rd = !bg_growth ? bg_none : (rdists === nothing ? soil.rootdist : rdists[i])
            newtrees[i] = tr.is_grass ? grow_grass_individual(galloc, tr, bm_ind, wscal_mean) :
                grow_individual(
                    alloc, allom, tr, bm_ind, wscal_mean;
                    bg_growth = bg_growth, bg_rootdist = bg_rd, bg_soildepth = bg_sd,
                )
        end
        # GRASS ESTABLISHMENT / re-seeding (establishment_grass.c, individual mode): if the total patch FPC
        # is below 1, each grass PFT gains sapling biomass `sapl·(1−fpc_total)/n_est` — the mechanism that
        # maintains the C's DIM-patch grass where the light-limited NPP is below the annual turnover (docs
        # §26). Off by default (`grass_estab === nothing`); grass-specific (no tree pool touched).
        if grass_estab !== nothing
            n_est = 0
            for i in 1:n
                newtrees[i].is_grass && (n_est += 1)
            end
            if n_est > 0
                fpc_total = zero(T)
                for i in 1:n
                    fpc_total += _treepools_fpc(newtrees[i], allom)
                end
                est_pft = max(zero(T), one(T) - fpc_total) / n_est     # establishment_grass.c:38 (fpc_total<1)
                if est_pft > zero(T)
                    for i in 1:n
                        g = newtrees[i]
                        g.is_grass || continue
                        newtrees[i] = TreePools{T}(
                            g.leaf_c + convert(T, grass_estab.sapl_leaf) * est_pft, g.sapwood_c, g.heartwood_c,
                            g.root_c + convert(T, grass_estab.sapl_root) * est_pft, g.height, g.crownarea,
                            g.nind, g.sla, g.wooddens, g.is_grass,
                        )
                    end
                end
            end
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

"""
    rollout_canopy_years_gpp(p, alloc, allom, st0, trees0, tmpls, soil, yearly_forcings;
                             phens_by_year=nothing, nlayers=60, n_top1m=3, hooks=_NO_HOOKS)
        -> gpp_by_year::Vector

**Enzyme-differentiable** multi-year coupled canopy rollout that returns the per-year annual **stand GPP**
`gpp_by_year[yr]` (gC/m²/yr) — the object a MULTI-YEAR training loss descends THROUGH the structure/
allocation feedback (docs §17; scale-up step 7b-multiyear). Same physics as [`rollout_canopy_years`](@ref)
— for each year: recompute the layered `fpar` from the current heights, build the daily
[`Individual`](@ref)s, fold [`daily_step_canopy`](@ref) accumulating each individual's per-m²
`bm_inc = Σ npp_ind` + the annual-mean stand water scalar, then GROW each individual (trees via
[`grow_individual`](@ref); grasses via [`grow_grass_individual`](@ref), `galloc` = grass alloc params) —
but the evolving per-individual pool state is carried as **struct-of-arrays**
(plain `Vector{T}` field arrays, NOT a `Vector{TreePools}`). This is what makes the reverse pass
Enzyme-typeable: on the multi-year path the trees are the ACTIVE outputs of `grow_individual`, and a
`Vector{TreePools}` field-scatter (`trees[i].height → scratch[i]`) raises `EnzymeNoTypeError` (the struct's
trailing `is_grass::Bool` + padding read as `Anything`) — see the [`_patch_fpars`](@ref) ENZYME NOTE. The
soil water carries across years; `hooks` supplies the learned Vcmax/λ correction (identity when off).
`phens_by_year[yr][d]` = the fixed daily leaf-display factor for year `yr`, day `d` (kernel isolation, e.g.
`fapar_C/peak` — the same crutch discipline as §9/§16); when `nothing`, full leaf display (`phen=1`) is
used. The `Vector{TreePools}` diagnostics ([`rollout_canopy_years`](@ref)) remain for the non-AD validation
path; this function returns only the per-year GPP the trainer needs.
"""
function rollout_canopy_years_gpp(
        p::FDiffParams, alloc::AllocParams, allom::Allometry.TreeAllometry, st0::FDiffStateML,
        trees0::AbstractVector{TreePools{T}}, tmpls::AbstractVector{Individual{T}}, soil::SoilColumn,
        yearly_forcings; phens_by_year = nothing, nlayers::Int = 60, n_top1m::Int = 3,
        galloc::AllocParams = grass_allocparams(T), hooks::FluxHooks = _NO_HOOKS
    ) where {T}
    n = length(trees0)
    # initial per-individual pool state as struct-of-arrays (iteration over the Const trees0 — never a
    # differentiated `Vector{TreePools}` field-scatter). `slas`/`ninds`/`wds`/`isgrass` are the per-tree
    # constants (not differentiated); the pool fields evolve across years.
    leafcs = T[t.leaf_c for t in trees0]; sapcs = T[t.sapwood_c for t in trees0]
    heartcs = T[t.heartwood_c for t in trees0]; rootcs = T[t.root_c for t in trees0]
    heights = T[t.height for t in trees0]; crowns = T[t.crownarea for t in trees0]
    ninds = T[t.nind for t in trees0]; slas = T[t.sla for t in trees0]
    wds = T[t.wooddens for t in trees0]; isgrass = Bool[t.is_grass for t in trees0]
    # the soil state is carried across years as its FIELDS (`wcol`::Vector, `snow`::scalar), NOT as the
    # `FDiffStateML` struct: an Enzyme reverse pass cannot type-analyze a `{Vector, Float64}` struct phi
    # carried around the OUTER (year) loop (the same struct-in-memory limitation the `_patch_fpars` ENZYME
    # NOTE describes), whereas a plain Vector + scalar carry types cleanly. Continuity is preserved — each
    # year rebuilds `FDiffStateML` from the carried column (soil water carries across years, as in
    # [`rollout_canopy_years`](@ref)).
    wcol = convert.(T, st0.w); snow = convert(T, st0.snowpack)
    # per-year daily leaf-display factors (the kernel-isolation crutch, e.g. `fapar_C/peak`). Materialized
    # UP FRONT to a CONCRETE `Vector{Vector{T}}` (full display `1` when not supplied) — a
    # `Union{Nothing,Vector}` `phens` local carried into the daily loop is an untypeable `{Pointer,Float64}`
    # phi for the Enzyme reverse pass (same struct-in-memory limitation as the `_patch_fpars` ENZYME NOTE).
    phens_arr = phens_by_year === nothing ? [ones(T, length(f)) for f in yearly_forcings] :
        [T[convert(T, x) for x in pv] for pv in phens_by_year]
    NY = length(yearly_forcings)
    gpp_by_year = Vector{T}(undef, NY)
    for yr in 1:NY
        forc = yearly_forcings[yr]
        fpars = _patch_fpars_soa(heights, leafcs, slas, ninds, crowns, isgrass, allom; nlayers = nlayers)
        # build the daily Individuals from the current SoA structure (a SINGLE TreePools per individual,
        # consumed immediately — no `Vector{TreePools}` round-trip). `individual_from_pools` recomputes
        # lai/fpc from the grown pools (lai_tree.c/fpc_tree.c).
        inds = Vector{Individual{T}}(undef, n)
        for i in 1:n
            tri = TreePools{T}(leafcs[i], sapcs[i], heartcs[i], rootcs[i], heights[i], crowns[i], ninds[i], slas[i], wds[i], isgrass[i])
            inds[i] = individual_from_pools(tmpls[i], tri, allom, fpars[i])
        end
        phens = phens_arr[yr]
        # scalar-accumulating daily fold (Enzyme-friendly — no per-day flux vector); carries the per-layer
        # soil water across days (the `FDiffStateML` struct is local to the year), and accumulates the
        # per-individual bm_inc.
        st = FDiffStateML{T}(wcol, snow)
        bm_perm2 = zeros(T, n); gpp_yr = zero(T); wsum = zero(T); nd = 0
        for (d, f) in enumerate(forc)
            ph = phens[d]
            (st, fl) = daily_step_canopy(p, inds, soil, st, f; phen = ph, n_top1m = n_top1m, hooks = hooks)
            for i in 1:n
                bm_perm2[i] += fl.npp_ind[i]
            end
            gpp_yr += fl.gpp; wsum += fl.wscal; nd += 1
        end
        wcol = st.w; snow = st.snowpack       # carry the soil column into next year (as fields, not the struct)
        gpp_by_year[yr] = gpp_yr
        wscal_mean = wsum / max(nd, 1)
        # GROW each individual via SoA: rebuild a single TreePools, advance it (trees via the pipe-model
        # `grow_individual`; grasses via the `allocation_grass.c` `grow_grass_individual`), scatter the grown
        # fields back into fresh arrays (the next year's structure). No `Vector{TreePools}` field-scatter.
        nh = zeros(T, n); nl = zeros(T, n); nsap = zeros(T, n); nheart = zeros(T, n); nroot = zeros(T, n); nc = zeros(T, n)
        for i in 1:n
            tri = TreePools{T}(leafcs[i], sapcs[i], heartcs[i], rootcs[i], heights[i], crowns[i], ninds[i], slas[i], wds[i], isgrass[i])
            bm_ind = bm_perm2[i] / (ninds[i] + T(1.0e-12))
            g = isgrass[i] ? grow_grass_individual(galloc, tri, bm_ind, wscal_mean) :
                grow_individual(alloc, allom, tri, bm_ind, wscal_mean)
            nh[i] = g.height; nl[i] = g.leaf_c; nsap[i] = g.sapwood_c
            nheart[i] = g.heartwood_c; nroot[i] = g.root_c; nc[i] = g.crownarea
        end
        heights = nh; leafcs = nl; sapcs = nsap; heartcs = nheart; rootcs = nroot; crowns = nc
    end
    return gpp_by_year
end

end # module FDiff
