# The two remaining `gp_sum` basis differences (`WaterParams.gp_stand_leafon_basis` / `lambda_vm_gp`,
# ADR 0136). ADR 0051's "Consequences" section registered both as *"a separate opt-in change with their own
# re-measure"*; this file pins the MECHANISM and guardrail 4, and ADR 0136 carries the fidelity numbers.
#
# Both act ONLY through the pass-1 (`gp_sum.c:36-68`) quantities:
#   * `gp_stand_leafon_basis` — the C builds each PFT's `gp` at FULL leaf cover (`apar ∝ pft->fpc`, no
#     `phen`; `gmin·pft->fpc` likewise), accumulates `gp_stand += gp·pft->phen`, and normalizes by the
#     PLAIN `Σ pft->fpc`. F_diff folds `φ` into the pass-1 `apar` and `gmin` and divides by `Σ fpc·φ`.
#   * `lambda_vm_gp` — the C's λ bisection runs with `data.vmax = pft->vmax` as left by `gp_sum`, i.e. a
#     Vcmax at the CROWN-COVER, NO-PHEN `apar`, while `data.apar` (hence `je`) is the layered phen-scaled
#     absorption (`water_stressed.c:198-206`). Only the solved λ differs: the C's FINAL call recomputes
#     Vcmax at the layered `apar` (`compvm=TRUE`) exactly as F_diff does, and Vcmax does not depend on λ.
#
# ⚠ The EXACT-BOUNDARY identities below are the point of the file (`residual-diagnosis` §3g: assert each
# ported guard at its exact boundary, not just the aggregate it feeds). They are BITWISE, and each has a
# matched "the flag actually fires" partner so a green identity can never be an inert code path
# (ADR 0048 §3).
@testitem "gp_sum basis flags — opt-in, exact at their boundaries, live off them" tags = [:validation, :fdiff, :canopy, :structure] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: hainich_soilcolumn, tebs_params, WaterParams, FDiffParams,
        grass_treepools, _patch_fpars, individual_from_pools, daily_step_canopy
    using LPJmLFITEmulator.Allometry
    using Test

    soil = hainich_soilcolumn(;
        whcs = [37.0, 53.0, 88.0, 175.0, 175.0], rootdist = [0.41, 0.32, 0.2, 0.07, 0.0],
        soildepth = [200.0, 300.0, 500.0, 1000.0, 1000.0],
    )
    allom = Allometry.TreeAllometry{Float64}()
    mktree(leaf, sap, heart, root, h, ca, nind) = TreePools{Float64}(leaf, sap, heart, root, h, ca, nind, 0.01986, 2.0e5, false)
    mktmpl(sla, isg) = Individual{Float64}(
        0.0, 0.0, 0.5, 0.15, 10.0, 0.0, 0.0, 0.0, isg ? 0.01 : 0.02, isg ? 0.15 : 0.04, 0.1, 0.4, isg ? 1.0 : 1 / 120,
        FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = sla),
        FDiff.TempStressParams{Float64}(; temp_photos_low = (isg ? 10.0 : 20.0), temp_photos_high = 30.0), isg,
    )
    trees0 = [
        mktree(4000.0, 40000.0, 150000.0, 4000.0, 20.0, 20.0, 1 / 120),
        mktree(1500.0, 12000.0, 40000.0, 1500.0, 12.0, 8.0, 1 / 120),
        grass_treepools(4.0, 10.0, 0.042242),
    ]
    tmpls = [mktmpl(0.01986, false), mktmpl(0.025, false), mktmpl(0.042242, true)]
    n = length(trees0)
    fp0 = _patch_fpars(trees0, allom)
    inds = Individual{Float64}[individual_from_pools(tmpls[i], trees0[i], allom, fp0[i]) for i in 1:n]
    # the boundary roster for `lambda_vm_gp`: `fpar ≡ fpc` makes the crown-cover `apar` and the layered
    # `apar` the SAME expression at `φ = 1`, so the C's `pft->vmax` and F_diff's are bitwise equal.
    # ⚠ This is a constructed boundary, NOT the physical regime: in the real roster above the layered
    # `fpar` EXCEEDS `fpc` for the dominant stem (0.282 vs 0.151), because the layered integration shares
    # ALL the light the stand absorbs among the stems by leaf area while `fpc` saturates per crown. So the
    # sign of `lambda_vm_gp` is NOT structural — see the two-sided assertion below.
    indsE = Individual{Float64}[individual_from_pools(tmpls[i], trees0[i], allom, inds[i].fpc) for i in 1:n]

    p0 = tebs_params()
    "copy `p0.water` with fields replaced (fieldnames-driven, so a future field cannot silently shift)."
    function with_water(p, kv::NamedTuple)
        w = WaterParams{Float64}(map(k -> haskey(kv, k) ? kv[k] : getfield(p.water, k), fieldnames(WaterParams))...)
        return FDiffParams{Float64}(p.photo, p.tstress, w, p.resp, p.allom, p.nlambda, p.ω)
    end
    # ── guardrail 4: both ship OFF, and the shipped calibrated set takes the default ──
    @test WaterParams{Float64}().gp_stand_leafon_basis == false
    @test WaterParams{Float64}().lambda_vm_gp == false
    @test p0.water.gp_stand_leafon_basis == false
    @test p0.water.lambda_vm_gp == false

    pbase = with_water(p0, (;))
    pgs = with_water(p0, (; gp_stand_leafon_basis = true))
    pvm = with_water(p0, (; lambda_vm_gp = true))
    pboth = with_water(p0, (; gp_stand_leafon_basis = true, lambda_vm_gp = true))

    # WELL-WATERED, bright, mild: `gc = gp_stand` (not supply-limited), which is the regime in which
    # `gp_stand_leafon_basis` can reach GPP at all — under water limitation `gc` is set by supply and the
    # flag moves only `demand`.
    f = DailyForcing{Float64}(swdown = 220.0, lwnet = -40.0, temp = 20.0, precip = 6.0, daylength = 14.0, co2 = 380.0)
    st0 = FDiffStateML{Float64}([0.8 * wc for wc in soil.whcs], 0.0)
    FLUXES = (:gpp, :npp, :transp, :evap, :interc, :eeq, :runoff, :rootmoist, :fapar, :fpc, :wscal)
    same(a, b) = all(getfield(a, k) === getfield(b, k) for k in FLUXES)

    # ── BOUNDARY 1 — at `φ ≡ 1` the two `gp_stand` bases are the SAME EXPRESSION, bitwise ──
    # `fpc_i = fpc·1`, `apar_gp = apar_lo`, so `Σ gp·φ / Σ fpc` and `Σ gp / Σ fpc·φ` are formed from
    # bitwise-equal terms in the same order.
    (s1, a1) = daily_step_canopy(pbase, inds, soil, st0, f; phen = 1.0)
    (s2, a2) = daily_step_canopy(pgs, inds, soil, st0, f; phen = 1.0)
    @test same(a1, a2)
    @test s1.w == s2.w && s1.snowpack === s2.snowpack

    # ── BOUNDARY 2 — at `φ ≡ 1` AND `fpar ≡ fpc`, the C's `pft->vmax` IS F_diff's, bitwise ──
    (_, e1) = daily_step_canopy(pbase, indsE, soil, st0, f; phen = 1.0)
    (_, e2) = daily_step_canopy(pvm, indsE, soil, st0, f; phen = 1.0)
    @test same(e1, e2)

    # ── AND THE FLAGS ACTUALLY FIRE OFF THOSE BOUNDARIES (a green identity must not be an inert path) ──
    (_, b7) = daily_step_canopy(pbase, inds, soil, st0, f; phen = 0.45)
    (_, g7) = daily_step_canopy(pgs, inds, soil, st0, f; phen = 0.45)
    (_, v7) = daily_step_canopy(pvm, inds, soil, st0, f; phen = 0.45)
    (_, x7) = daily_step_canopy(pboth, inds, soil, st0, f; phen = 0.45)
    @test g7.gpp != b7.gpp
    @test v7.gpp != b7.gpp
    @test x7.gpp != g7.gpp && x7.gpp != v7.gpp
    # `lambda_vm_gp` fires at `φ = 1` too (the roster's `fpar ≠ fpc`), which is what BOUNDARY 2 isolates:
    # the identity there is the Vcmax basis, not the phenology.
    (_, v1) = daily_step_canopy(pvm, inds, soil, st0, f; phen = 1.0)
    @test v1.gpp != a1.gpp

    # ── DIRECTION — signed for `gp_stand_leafon_basis`, DELIBERATELY NOT for `lambda_vm_gp` ──
    # F_diff's `gp_stand` divides a numerator built from a phen-scaled `apar` by the phen-weighted
    # `Σ fpc·φ`; the C divides its leaf-on numerator by the plain `Σ fpc`. `adtmm` is concave but not far
    # from linear in `apar`, so F_diff's ratio is biased HIGH by ≈ 1/φ̄ on a partial-leaf day ⇒ larger
    # `demand`/`gc`/`gpd`/`fac` ⇒ higher solved λ ⇒ more GPP. Switching to the C's basis must LOWER it.
    for φ in (0.7, 0.45, 0.2)
        (_, bb) = daily_step_canopy(pbase, inds, soil, st0, f; phen = φ)
        (_, gg) = daily_step_canopy(pgs, inds, soil, st0, f; phen = φ)
        @test gg.gpp < bb.gpp
    end
    # `lambda_vm_gp` has NO asserted sign: `∂adt/∂vm ∝ c2·∂agd/∂jc − b` inverts under Rubisco saturation,
    # and `apar_leafon − apar` itself changes sign with the stand's leaf-area concentration (see `indsE`
    # above). ADR 0136 measures it per cell; a sign assertion here would be a guess wearing a test.
    @test isfinite(v7.gpp) && v7.gpp > 0
end
