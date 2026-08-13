# ADR 0103 — the LEVEL ANCHOR. Pins the two properties that make it safe to ship, in the two directions a
# future change could break them.
#
# WHY THIS EXISTS. `reconcile_demography!` advances the stand by a pure RATIO (`target/n_prev`), so the
# roster evolves as `D_T = D_0·Πρ_t` and the count DRF's ABSOLUTE prediction never reaches it. ADR 0102
# measured the consequence: a 4× perturbation of the initial density is still 4.21× after 300 identical
# forcing years (retention 1.036, a NON-ZERO asymptote — no restoring force), and the stand settles 1.41×
# denser than its own count model says. ADR 0103 ships the fix as an opt-in `anchor`, using the fact that
# the count↔density conversion is a documented CONSTANT (`param.patcharea` = 225 m² = 15×15 in
# `par/lpjparam_fit.js`; `new_tree.c:209` gives every individual `nind = 1/patcharea`).
#
# WHAT IS PINNED, and why each direction matters:
#   1. `anchor = 0` is EXACTLY today's behaviour — same trajectory to the last bit, not merely close. This
#      is guardrail 4 as a measurement rather than an assertion about the code, and it is what lets the
#      feature ship without regenerating a single committed baseline.
#   2. `anchor > 0` ACTUALLY ANCHORS — the stand lands on `target/patch_area`. Without this direction the
#      test would pass on a no-op, which is the ADR-0048 failure mode (an operator that never fired
#      returning a clean null). A tolerance is used, not equality: the anchored run is a different, valid
#      trajectory whose own `target` is re-predicted from its own features.
#   3. `patch_area` is LOAD-BEARING when the anchor is on — halving it must move the anchored level. This
#      guards the "constant travels with the artifact" contract (ADR 0103 §4): stock LPJmL-FIT uses 100.0,
#      and an artifact trained on such a run needs its own value passed.
# Hainich (DE-Hai, cell 42490) demonstration artifact; short horizon (the anchor acts within a few years at
# a = 0.5, so a long rollout is not needed to see it).

@testitem "Level anchor: anchor=0 is byte-identical, anchor>0 lands the stand on the DRF's absolute target (ADR 0103)" tags = [:coupling, :scientific] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
    using LPJmLFITEmulator.DRF
    using Test

    _mean(x) = sum(x) / length(x)
    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
        hdr = split(strip(lines[1]), ',')
        rows = [split(strip(l), ',') for l in lines[2:end]]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    ind = readcsv(joinpath(refdir, "hainich_individuals_2010.csv"))
    f = readcsv(joinpath(refdir, "hainich_forcing_2010.csv"))
    fc_(k) = parse.(Float64, f[k])
    v(k, r) = parse(Float64, ind[k][r])
    nt(r) = parse(Int, ind["type"][r])
    n = length(fc_("doy"))

    sd = Float64[]; whcs = Float64[]; rdist = Float64[]
    for ln in eachline(joinpath(refdir, "hainich_soilcolumn.txt"))
        s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
        x = parse.(Float64, split(s)); push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
    end
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

    prows = Dict{Int, Vector{Int}}()
    for r in eachindex(ind["type"])
        (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    rows = prows[argmax(Dict(k => length(vv) for (k, vv) in prows))]
    mkp(r) = TreePools{Float64}(
        v("leaf_c", r), v("sapwood_c", r),
        max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0), v("root_c", r),
        v("height", r), v("crownarea", r), v("nind", r), v("sla", r), v("wooddens", r), false,
    )
    mkt(r) = Individual{Float64}(
        v("fpar_leafon", r), 0.0, v("alphaa", r), v("albedo_leaf", r), v("emax", r),
        v("sapwood_c", r), v("root_c", r), 0.0, 0.02, 0.04, 0.1, 0.4, v("nind", r),
        PhotoParams{Float64}(; path = :c3, issla = true, sla = v("sla", r)),
        TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false,
    )
    tair_K = fc_("temp") .+ 273.15
    σ = 5.670374419e-8
    year_forc = [
        AtmForcing(;
                swdown = fc_("swdown")[i], lwdown = fc_("lwnet")[i] + σ * tair_K[i]^4,
                tair = tair_K[i], qair = fc_("huss")[i], wind = 2.0, psurf = 1.0e5,
                precip = fc_("precip")[i], co2 = fc_("co2")[i]
            ) for i in 1:n
    ]
    pft_ids = [nt(r) for r in rows]
    mkcore() = FDiffFastCore(
        [mkp(r) for r in rows], [mkt(r) for r in rows], soil, 51.25; pft_ids = pft_ids
    )

    forest = DRF.load_forest(joinpath(refdir, "drf_forest_hainich.drf"))
    meta = Dict{String, String}()
    for ln in eachline(joinpath(refdir, "drf_forest_hainich_meta.txt"))
        (isempty(strip(ln)) || startswith(strip(ln), "#")) && continue
        p = split(ln, '\t')
        length(p) >= 2 && p[1] != "golden" && (meta[String(p[1])] = String(strip(p[2])))
    end
    bnd = parse.(Float64, split(strip(meta["boundary"])))
    n_init = parse(Float64, meta["n_init"])
    age0 = parse(Float64, meta["age0"])

    treedens(core) = sum(p.nind for p in core.pools if !p.is_grass; init = 0.0)

    "Run `years` coupled years and return the density trajectory + the emulator."
    function rollout(; anchor, years::Int = 25, patch_area = 225.0, dscale = 1.0)
        core = if dscale == 1.0
            mkcore()
        else
            FDiffFastCore(
                [
                    (
                            q = mkp(r);
                            TreePools{Float64}(
                                q.leaf_c, q.sapwood_c, q.heartwood_c, q.root_c, q.height,
                                q.crownarea, dscale * q.nind, q.sla, q.wooddens, false
                            )
                        ) for r in rows
                ],
                [mkt(r) for r in rows], soil, 51.25; pft_ids = pft_ids
            )
        end
        s = FluxDrivenSlowEmulator(
            core, forest; boundary = bnd, n_init = n_init, age0 = age0, seed = 1,
            anchor = anchor, patch_area = patch_area
        )
        clo = SEBEnergyClosure(; t_soil0 = _mean(tair_K))
        st = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
        dens = Float64[treedens(core)]
        for _ in 1:years
            run_coupled_cell(core, clo, st, year_forc; slow = s, days_per_year = n)
            push!(dens, treedens(core))
        end
        return (; s, core, dens)
    end

    # ── 1. `anchor = 0` is BYTE-IDENTICAL to not passing it at all ──────────────────────────────────────
    # Not "close": the branch must not be evaluated, so every year's density must match to the last bit.
    base = rollout(; anchor = 0.0)
    ref = let                                            # constructed WITHOUT the kwarg — the pre-0103 call
        core = mkcore()
        s = FluxDrivenSlowEmulator(
            core, forest; boundary = bnd, n_init = n_init, age0 = age0, seed = 1
        )
        clo = SEBEnergyClosure(; t_soil0 = _mean(tair_K))
        st = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
        d = Float64[treedens(core)]
        for _ in 1:25
            run_coupled_cell(core, clo, st, year_forc; slow = s, days_per_year = n)
            push!(d, treedens(core))
        end
        (; s, d)
    end
    @test base.dens == ref.d                                     # === , not isapprox (guardrail 4)
    @test base.s.target_history == ref.s.target_history
    @test base.s.n_prev === ref.s.n_prev

    # ── 2. `anchor > 0` lands the stand on the DRF's ABSOLUTE target ────────────────────────────────────
    # The unanchored run does NOT (measured 1.41× at 150 yr); the anchored one must, or the operator is a
    # no-op and this test would be passing on nothing (the ADR-0048 never-fired-null failure mode).
    PATCH_AREA = 225.0                          # par/lpjparam_fit.js; new_tree.c:209 nind = 1/patcharea
    anc = rollout(; anchor = 0.5)
    want = anc.s.target_history[end] / PATCH_AREA
    @test isapprox(anc.dens[end], want; rtol = 0.05)             # on target
    unanc_ratio = base.dens[end] / (base.s.target_history[end] / PATCH_AREA)
    @test unanc_ratio > 1.15                                     # the defect is present without the anchor
    @test abs(anc.dens[end] / want - 1) < abs(unanc_ratio - 1)   # and the anchor strictly improves it

    # ── 3. the anchor FORGETS the initial condition; the unanchored run does not ────────────────────────
    # ⚠ CONVERGENCE IS NOT MONOTONE, and this test was written wrong the first time by assuming it was.
    # Measured over 150 yr (job 1707785), retention against horizon:
    #     a = 0.5 :  yr 5 0.154 | yr 10 0.243 | yr 25 0.486 | yr 50 0.103 | yr 100 0.051 | yr 150 0.051
    #     a = 0.1 :  yr 5 0.720 | yr 10 0.622 | yr 25 0.603 | yr 50 0.103 | yr 100 0.049 | yr 150 0.051
    #     a = 0.0 :                                                                        yr 150 1.036
    # `a = 0.5` collapses within ~5 yr (the 1/a time constant), then RE-DIVERGES to a transient peak near
    # yr 25 before settling by yr 50-100. An assertion at yr 25 alone lands on the worst point of that
    # transient — which is exactly what the first version of this test did (it demanded < 0.3 and measured
    # 0.425). So BOTH horizons are asserted here: the early collapse and the (looser) transient bound.
    # The floor is ~0.05, not 0, because the per-arm terminal TARGETS differ by 7.3 % — the DRF's target is
    # state-dependent, so each arm is anchored to a slightly different level. See ADR 0103 §5.
    function retention(anchor, idx)
        lo = rollout(; anchor = anchor, dscale = 0.5).dens[idx]
        hi = rollout(; anchor = anchor, dscale = 2.0).dens[idx]
        return log(hi / lo) / log(4.0)
    end
    ret_a5, ret_05 = retention(0.5, 6), retention(0.0, 6)         # dens[1] is yr 0 ⇒ dens[6] is yr 5
    ret_a25, ret_025 = retention(0.5, 26), retention(0.0, 26)
    # ⚠ RE-PINNED 0.7 → 0.55 on 2026-08-13 for line M's `gp_stand_leafon_basis` DEFAULT FLIP (ADR 0137),
    # with line S's explicit GO (S is this file's owner; the authorisation is in `lines/M/STATE.md`).
    # Measured 0.618996 under the flip, against > 0.7 before it. This is a re-measure, not a widening: the
    # quantity is physics-dependent and the old number was pinned against a different conductance basis.
    # It is also the horizon the comment block above flags in capitals as non-monotone and as the worst
    # point of the transient, whereas ADR 0103's actual claim is the yr-150 separation (unanchored 1.036
    # vs anchored 0.051, ~20×) — and all four contrast assertions below stayed green under the flip, so
    # "the anchor strictly beats no-anchor" is untouched. ⚠ THE yr-150 UNANCHORED RETENTION UNDER THE FLIP
    # IS UNMEASURED (it needs its own 150-yr job); if it fell below ~0.8 the reading above would change.
    @test ret_025 > 0.55                  # unanchored: the 4× initial spread is largely retained
    @test ret_a5 < 0.35                   # anchored, yr 5: the fast collapse (measured 0.154)
    @test ret_a25 < 0.7                   # anchored, yr 25: the transient peak (measured 0.486)
    @test ret_a5 < ret_05                 # strictly better than unanchored at BOTH horizons
    @test ret_a25 < ret_025

    # ── 4. `patch_area` is load-bearing when the anchor is on, inert when it is off ─────────────────────
    # Guards ADR 0103 §4: the constant travels with the ARTIFACT (stock LPJmL-FIT uses 100.0, not 225.0).
    half = rollout(; anchor = 0.5, patch_area = 0.5 * PATCH_AREA)
    @test !isapprox(half.dens[end], anc.dens[end]; rtol = 0.05)
    @test rollout(; anchor = 0.0, patch_area = 1.0).dens == base.dens      # inert when off

    # ── 5. the anchor does not break the invariants the rest of the loop relies on ──────────────────────
    @test all(isfinite, anc.dens)
    @test all(>(0), anc.dens)
    @test abs(anc.s.last_resid) < 1.0e-6                                   # carbon still closes
    @test rollout(; anchor = 0.5).dens == anc.dens                         # deterministic under seed

    # ── 6. the kwarg is validated ───────────────────────────────────────────────────────────────────────
    @test_throws ErrorException FluxDrivenSlowEmulator(
        mkcore(), forest; boundary = bnd, n_init = n_init, age0 = age0, anchor = 1.5
    )
    @test_throws ErrorException FluxDrivenSlowEmulator(
        mkcore(), forest; boundary = bnd, n_init = n_init, age0 = age0, anchor = -0.1
    )
end
