# Phase 3 (ADR 0025) — the single-cell TRAIT-distribution gate for the recruit-trait copula. The coupled
# flux-driven Component S, with the committed demo copula (recruit_copula_hainich.rcop) switched ON, is
# compared to the LPJmL-FIT C GROUND-TRUTH beech trait marginals at Hainich (hainich_slow_oracle_traits.csv,
# built by scripts/build_slow_oracle_reference.py).
#
# HONEST FRAMING (residual-diagnosis + the copula design): at a SINGLE beech cell the trait axes are
# near-degenerate, so this is a WIRING + sanity gate, NOT proof of cross-cell distributional skill (that is
# the multi-cell OOS eval, Phase 4). It nonetheless exercises the full production path end to end — load the
# `.rcop`, rebuild `to_pools` from the axis names, condition each year via `live_flux_cond`, draw + append
# recruits, conserve carbon — and checks the emulated community SLA/Wooddens distribution lands on the C
# survivor marginal (which it should: recruits are drawn from exactly that flux-conditioned marginal, and
# the emulator's mortality is trait-blind so the community distribution == the establishment distribution).
# S1d re-measurement (ADR 0035, job 1622923) — the current numbers. Unlike S1c, where the `.rcop` came back
# byte-identical, S1d moved two of the copula's four `live_flux_cond` conditioning columns onto their real
# bases (`soilmoist` = root-zone year-end `w`; `growth_eff` via the per-patch `lai` divisor), so the copula
# was retrained and the DIRECT draws moved — markedly CLOSER to the C oracle:
#   DIRECT   SLA 0.1274 → 0.0391 (ratio 0.9715 → 0.9985) · Wooddens 0.0346 → 0.0273 (1.0000 → 1.0032)
#   COUPLED  SLA 0.2634 (ratio 1.0624) · Wooddens 0.2203 (1.1113) — both UNCHANGED from S1c
# Only the two DIRECT bounds move, and both TIGHTEN (0.22 → 0.10, 0.12 → 0.06); nothing here is widened.

@testitem "Gate-3 traits — coupled S recruit-copula community SLA/Wooddens vs LPJmL-FIT C truth (Hainich 42490)" tags = [:scientific, :coupling] begin
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
    v(k, r) = parse(Float64, ind[k][r]); nt(r) = parse(Int, ind["type"][r])
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
    tair_K = fc_("temp") .+ 273.15; σ = 5.670374419e-8
    year_forc = [
        AtmForcing(;
                swdown = fc_("swdown")[i], lwdown = fc_("lwnet")[i] + σ * tair_K[i]^4,
                tair = tair_K[i], qair = fc_("huss")[i], wind = 2.0, psurf = 1.0e5,
                precip = fc_("precip")[i], co2 = fc_("co2")[i]
            ) for i in 1:n
    ]

    # count DRF + its meta (boundary/n_init/age0) — same as the size-distribution oracle gate
    forest = DRF.load_forest(joinpath(refdir, "drf_forest_hainich.drf"))
    boundary = Float64[]; n_init = 1.0; age0 = 0.0
    for ln in eachline(joinpath(refdir, "drf_forest_hainich_meta.txt"))
        (isempty(strip(ln)) || startswith(strip(ln), "#")) && continue
        parts = split(ln, '\t')
        parts[1] == "boundary" && (boundary = parse.(Float64, split(strip(parts[2]))))
        parts[1] == "n_init" && (n_init = parse(Float64, strip(parts[2])))
        parts[1] == "age0" && (age0 = parse(Float64, strip(parts[2])))
    end
    @test age0 > 0.0

    # ── the recruit-trait copula: load the committed .rcop, rebuild to_pools from axis names, live conditioning ──
    cop, af, xcop, axes, cond_cols = DRF.load_copula(joinpath(refdir, "recruit_copula_hainich.rcop"))
    @test axes == ["SLA", "Wooddens", "D95max", "minwscal"]        # the 4 live FIT trait primaries (ADR 0025)
    @test cond_cols[1:4] == ["bm_inc_cell", "growth_eff", "water_stress", "soilmoist"]   # live_flux_cond order
    @test length(af) == length(axes) && all(fo -> fo.nfeat == length(cond_cols), af)
    rc = RecruitCopula{Float64}(cop, af, xcop, make_recruit_to_pools(axes), live_flux_cond)

    # ── golden (seed,x)->draw pairs from the meta: the committed artifact reproduces its draws BITWISE ──
    gx = xcop; goldens = Tuple{Int, Vector{Float64}}[]
    for ln in eachline(joinpath(refdir, "recruit_copula_hainich_meta.txt"))
        (isempty(strip(ln)) || startswith(strip(ln), "#")) && continue
        parts = split(ln, '\t')
        parts[1] == "x" && (gx = parse.(Float64, split(strip(parts[2]))))
        if parts[1] == "golden"
            push!(goldens, (parse(Int, strip(parts[2])), parse.(Float64, split(strip(parts[3])))))
        end
    end
    @test !isempty(goldens)
    for (seed, draw) in goldens
        @test DRF.sample_copula!(DRF.Xoshiro256pp(seed), cop, af, gx) == draw   # artifact drift alarm (bitwise)
    end

    # ── coupled decade with the copula ON ──
    core = FDiffFastCore([mkp(r) for r in rows], [mkt(r) for r in rows], soil, 51.25)
    s = FluxDrivenSlowEmulator(core, forest; boundary = boundary, n_init = n_init, age0 = age0, seed = 1, recruit_copula = rc)
    forcings = repeat(year_forc, 20)
    run_coupled_cell(
        core, SEBEnergyClosure(; t_soil0 = _mean(tair_K)),
        SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER)), forcings; slow = s, days_per_year = n
    )
    @test maximum(abs, s.resid_history) < 1.0e-6                   # copula recruits still conserve carbon
    @test length(core.pools) > length(rows)                       # recruits appended via the copula

    # nind-weighted community quantiles for the two F_diff-CONSUMED trait axes (SLA, Wooddens)
    qs = (0.05, 0.25, 0.5, 0.75, 0.95)
    tr = readcsv(joinpath(refdir, "hainich_slow_oracle_traits.csv"))
    function community_q(getter)
        xs = Float64[]; ws = Float64[]
        for p in core.pools
            p.is_grass && continue
            push!(xs, getter(p)); push!(ws, p.nind)
        end
        ord = sortperm(xs); xs = xs[ord]; ws = ws[ord]; cw = cumsum(ws) ./ sum(ws)
        return [xs[findfirst(>=(q), cw)] for q in qs]
    end
    function nqrmse_axis(axname, getter)
        coupled = community_q(getter)
        ai = findfirst(==(axname), tr["axis"])
        truth = [parse(Float64, tr[string("q", lpad(round(Int, q * 100), 2, '0'))][ai]) for q in qs]
        iqr = truth[4] - truth[2]
        nq = sqrt(sum((coupled .- truth) .^ 2) / length(qs)) / iqr
        @info "Gate-3 traits ($axname)" coupled = round.(coupled, sigdigits = 4) truth = round.(truth, sigdigits = 4) nqrmse = round(nq, digits = 3) median_ratio = round(coupled[3] / truth[3], digits = 3)
        return nq, coupled[3] / truth[3], iqr
    end

    # ── PRIMARY fidelity check: the DIRECT copula-draw marginals vs the C oracle. Uses ONLY the deterministic
    #    RNG + the .rcop forest leaves + norminv/normcdf (Julia's bundled openlibm) → BITWISE-reproducible
    #    across platforms, so it carries the TIGHT tolerance. A marginal regression or a stale/rebuilt .rcop
    #    trips it; a creep toward the bound is a signal to re-measure.
    #    RE-MEASURED 2026-07-28 (S1d / ADR 0035, job 1622923) and both bounds TIGHTENED, neither widened —
    #    putting `soilmoist` and `growth_eff` (two of the copula's four `live_flux_cond` columns) on their
    #    real bases moved the draws markedly CLOSER to the C oracle:
    #      SLA       nqrmse 0.1274 → 0.0391  (median ratio 0.9715 → 0.9985);  bound 0.22 → 0.10
    #      Wooddens  nqrmse 0.0346 → 0.0273  (median ratio 1.0000 → 1.0032);  bound 0.12 → 0.06
    #    Each new bound keeps a >2× cushion over the measurement — deliberately not shrink-wrapped, since a
    #    future basis change should be able to move these a little without a red suite.
    qd(vals) = (v = sort(vals); [v[clamp(round(Int, q * length(v)), 1, length(v))] for q in qs])
    Ndraw = 4000
    draws = [DRF.sample_copula!(DRF.Xoshiro256pp(sd_), cop, af, xcop) for sd_ in 1:Ndraw]
    function draw_nqrmse(axname, ai)
        dq = qd([draws[k][ai] for k in 1:Ndraw])
        oi = findfirst(==(axname), tr["axis"])
        tq = [parse(Float64, tr[string("q", lpad(round(Int, q * 100), 2, '0'))][oi]) for q in qs]
        nq = sqrt(sum((dq .- tq) .^ 2) / length(qs)) / (tq[4] - tq[2])
        @info "Gate-3 traits — DIRECT copula draws ($axname)" draw = round.(dq, sigdigits = 4) truth = round.(tq, sigdigits = 4) nqrmse = round(nq, digits = 3) median_ratio = round(dq[3] / tq[3], digits = 3)
        return nq, dq[3] / tq[3]
    end
    dnq_sla, dmr_sla = draw_nqrmse("SLA", 1)          # axis 1 = SLA
    dnq_wd, dmr_wd = draw_nqrmse("Wooddens", 2)       # axis 2 = Wooddens
    @test dnq_sla ≤ 0.1
    @test 0.85 ≤ dmr_sla ≤ 1.15
    @test dnq_wd ≤ 0.06
    @test 0.85 ≤ dmr_wd ≤ 1.15

    # ── COARSE coupled-community alarm (platform-sensitive → generous, like the Gate-3 Height oracle's 0.45).
    #    The 20-yr Float64 coupled trajectory's tails diverge by CPU microarch (SLA nqrmse ≈ 0.13 login vs
    #    ≈ 0.26 compute), so the nqrmse bound is loose; the stable signal is the MEDIAN ratio (≈ 1.02–1.11
    #    across platforms). This confirms the copula recruits shape the coupled community sensibly — it is
    #    NOT cross-cell distributional skill (that is the multi-cell OOS eval, Phase 4). Hainich-only.
    nq_sla, mr_sla, iqr_sla = nqrmse_axis("SLA", p -> p.sla)
    @test iqr_sla > 0
    @test nq_sla ≤ 0.45
    @test 0.7 ≤ mr_sla ≤ 1.4

    nq_wd, mr_wd, iqr_wd = nqrmse_axis("Wooddens", p -> p.wooddens)
    @test iqr_wd > 0
    @test nq_wd ≤ 0.45
    @test 0.7 ≤ mr_wd ≤ 1.4
end
