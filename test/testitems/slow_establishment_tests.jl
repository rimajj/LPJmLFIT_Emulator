# Component S — the PORTED LPJmL-FIT establishment rule (ADR 0119).
#
# Two items, split the way the trait-mortality pair is: the first gates the RULE (its parameters against
# the generated C reference, and each ported equation against the C source's own behaviour), the second
# gates the OPERATOR (what happens when `reconcile_demography!` actually draws recruits with it).
#
# What has to be proven, in order of how expensive getting it wrong would be:
#
#   1. THE PARAMETERS ARE THE C's. `PFT_ESTAB_PARAMS` is literals in Julia; the source of record is
#      `references/S_pft_estab_params.csv`, generated from the live `.js` files. ADR 0031 is the record of
#      what two independent copies of a per-PFT table cost (a stale `TREE_TYPES` hid 32.5 % of the tree
#      population for months), so the gate is row-by-row and includes the run globals.
#   2. THE BOUNDARY RULE IS NOT A REFLECTION. `new_tree.c:55-59` replaces an out-of-interval diffusion
#      draw with a uniform draw BETWEEN THE PARENT AND THE VIOLATED BOUND. An earlier summary in this repo
#      called it "reflected at the interval edges"; a reflection would put mass on the far side of the
#      parent and change the stationary shape exactly at the edges where the boreal intervals live.
#   3. THE MIXTURE WEIGHT IS THE CLOSED FORM, and it is realised. `4/(4 + n_elig)` (ADR 0045) is exact
#      only because both channels' `f_sap` cancels; the operator must actually draw inherited recruits at
#      that rate, and must NOT be able to draw them at all while the seedbank is empty.
#   4. THE DEFAULT IS INERT (guardrail 4) and carbon still closes (guardrail 2).
#
# It also pins the two places this port departs from the C on purpose — an UNSET parent axis falls back to
# the uniform channel instead of diffusing a value that does not exist, and a parent outside its own PFT's
# interval is clamped on insertion — because both are invariants FIT gets for free and the emulator does
# not, and a silent violation of either puts a recruit outside its own parameter range.

@testitem "Ported FIT establishment (ADR 0119) — parameters vs the C reference, and the ported equations" tags = [:scientific, :slow] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.DRF
    using Test
    const E = LPJmLFITEmulator.Establishment

    # ── (1) the parameter gate: every literal against the generated CSV, row by row ──────────────────
    path = joinpath(@__DIR__, "references", "S_pft_estab_params.csv")
    lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
    hdr = String.(split(strip(lines[1]), ','))
    col(row, name) = row[findfirst(==(name), hdr)]
    rows = [String.(split(strip(l), ',')) for l in lines[2:end]]
    @test length(rows) == 7                                   # ids 0-6 are the complete tree set (ADR 0031)
    @test Set(keys(E.PFT_ESTAB_PARAMS)) == Set(0:6)
    for r in rows
        id = parse(Int, col(r, "pft_id"))
        p = E.pft_estab_params(id)
        for (jl, csv) in (
                (p.sla_low, "sla_low"), (p.sla_high, "sla_high"),
                (p.wooddens_low, "wooddens_low"), (p.wooddens_high, "wooddens_high"),
                (p.d95max_low, "d95max_low"), (p.d95max_high, "d95max_high"),
                (p.minwscal_low, "minwscal_low"), (p.minwscal_high, "minwscal_high"),
                (p.inherit_corridor, "inherit_corridor"),
                (p.temp_low, "temp_low"), (p.temp_high, "temp_high"),
                (p.gdd5min, "gdd5min"), (p.aprec_min, "aprec_min"),
            )
            @test jl == parse(Float64, col(r, csv))
        end
        # the run globals ride on every row precisely so neither copy can drift on them unnoticed
        @test E.K_EST_INHERIT == parse(Float64, col(r, "k_est_inherit"))
        @test E.K_EST_INHERIT_BG == parse(Float64, col(r, "k_est_inherit_bg"))
        @test E.ALPHA_R == parse(Float64, col(r, "param_alpha_r"))
        @test E.PATCHAREA == parse(Float64, col(r, "patcharea"))
        @test E.MAX_AGE == parse(Int, col(r, "max_age"))
        @test E.N_MAX == parse(Int, col(r, "n_max"))
    end
    # a grass id is NOT defaultable — the intervals differ so much between PFTs that a beech fallback is a
    # measurable defect (id 3's `sla` interval does not even intersect id 1's)
    @test_throws ErrorException E.pft_estab_params(8)
    @test_throws ErrorException E.pft_estab_params(-1)

    # ── (2) the closed-form mixture weight (ADR 0045) ────────────────────────────────────────────────
    @test E.w_inherit(5) ≈ 4 / 9 rtol = 1.0e-12               # ≈44 % — a five-PFT cell (Hainich)
    @test E.w_inherit(1) ≈ 4 / 5 rtol = 1.0e-12               # 80 % — a single-PFT cell (Amazon, Sahel)
    @test E.w_inherit(0) == 1.0                               # no background channel can fire
    @test all(E.w_inherit(n) ≈ 4 / (4 + n) for n in 1:7)
    @test issorted([E.w_inherit(n) for n in 1:7]; rev = true)  # more eligible PFTs ⇒ less inheritance

    # ── (3) the bioclimatic gate, ported from establish.c:29-33 + establishmentpft_ind.c:88 ──────────
    # the tree-only clause: a 20-yr mean warmest month at or below 10 °C admits NO tree at all
    @test isempty(E.eligible_pfts(-5.0, 10.0, 2000.0))
    @test isempty(E.eligible_pfts(-5.0, 9.9, 2000.0))
    # boreal ids have temp_high = 0 ⇒ they drop out as soon as the mean coldest month is above freezing
    @test E.eligible_pfts(1.0, 20.0, 2000.0) == [1, 2, 3]
    @test E.eligible_pfts(-1.0, 20.0, 2000.0) == [1, 2, 3, 4, 5, 6]
    # `gdd5min` is the other axis, and it is what makes `n_elig` cell-dependent (0/350/900/1200)
    @test E.eligible_pfts(-1.0, 20.0, 400.0) == [4, 5, 6]
    @test E.eligible_pfts(-1.0, 20.0, 300.0) == Int[]
    @test 0 in E.eligible_pfts(20.0, 28.0, 8000.0)            # tropical: temp_low 2.5 passes
    @test !(0 in E.eligible_pfts(-1.0, 20.0, 2000.0))
    # the aprec gate (default Inf ⇒ treated as satisfied; only sub-100 mm cells are affected)
    @test isempty(E.eligible_pfts(-1.0, 20.0, 2000.0; aprec = 50.0))
    @test !isempty(E.eligible_pfts(-1.0, 20.0, 2000.0; aprec = 150.0))

    # ── (4) the background channel's draw: `getrndinterval` = low + (high−low)·U ─────────────────────
    rng = DRF.Xoshiro256pp(11)
    xs = [E.rnd_interval(rng, 2.0, 6.0) for _ in 1:20_000]
    @test all(2.0 .<= xs .<= 6.0)
    @test abs(sum(xs) / length(xs) - 4.0) < 0.05              # uniform ⇒ mean at the interval centre
    @test E.rnd_interval(rng, 3.0, 3.0) == 3.0

    # ── (5) the inheritance diffusion, new_tree.c:38-61 ──────────────────────────────────────────────
    rng = DRF.Xoshiro256pp(23)
    lo, hi, old = 0.0242, 0.0547, 0.03                        # id 3's sla interval, a mid-interval parent
    ys = [E.draw_new_trait(rng, old, lo, hi, 0.1) for _ in 1:50_000]
    @test all(lo .<= ys .<= hi)                               # the child NEVER leaves the interval
    @test abs(sum(ys) / length(ys) - old) < 0.15 * old        # and stays centred near the parent
    @test 0.005 < sum((ys .- old) .^ 2) / length(ys) / old^2 < 0.02   # spread ≈ corridor² = 0.01
    # a degenerate interval returns the parent unchanged (the `trait_min == trait_max` guard at :53)
    @test E.draw_new_trait(rng, 0.03, 0.02, 0.02, 0.1) == 0.03
    # corridor 0 ⇒ the parent, exactly (no diffusion, so no boundary case either)
    @test all(E.draw_new_trait(rng, old, lo, hi, 0.0) == old for _ in 1:50)

    # ⚠ THE BOUNDARY RULE IS AN INWARD REDRAW, NOT A REFLECTION. With the parent sitting ON the lower
    # bound, a reflection would scatter children ABOVE it while the C's rule collapses every violating
    # draw back onto the bound itself (`low + (old − low)·U` with `old == low`). So a parent at the bound
    # must produce children that are never below it AND a point mass exactly AT it — the signature that
    # separates the two rules.
    rng = DRF.Xoshiro256pp(29)
    at_lo = [E.draw_new_trait(rng, lo, lo, hi, 0.1) for _ in 1:20_000]
    @test all(at_lo .>= lo)
    @test count(==(lo), at_lo) > 4_000                        # ≈ half the draws (s < 0) land exactly here
    @test count(>(lo), at_lo) > 4_000                         # and the other half diffuse upward
    # mirrored at the upper bound
    at_hi = [E.draw_new_trait(rng, hi, lo, hi, 0.1) for _ in 1:20_000]
    @test all(at_hi .<= hi)
    @test count(==(hi), at_hi) > 4_000
    # and for an interior parent the violating draws land BETWEEN the parent and the bound, never beyond
    rng = DRF.Xoshiro256pp(31)
    near = [E.draw_new_trait(rng, lo + 1.0e-4, lo, hi, 0.5) for _ in 1:20_000]
    @test all(near .>= lo)

    # ── (6) the rolling top-AGB seedbank, getsapling.c + getmaxagb.c ─────────────────────────────────
    @test E.default_n_top() == 15                             # trunc(7·1·225/100)
    @test E.default_n_top(25) == 393                          # the 25-patch ground-truth ensemble
    sb = E.Seedbank{Float64}()
    @test sb.max_age == 50 && isempty(sb.entries)
    # three cohorts, only the top `n_top = 15` individuals' worth may enter, largest AGB first
    tr = [(0.03, 2.0e5, 400.0, 0.12), (0.012, 3.0e5, 800.0, 0.05), (0.03, 2.5e5, 300.0, 0.11)]
    E.seedbank_update!(sb, 0, [1000.0, 500.0, 2000.0], [4.0, 20.0, 6.0], [3, 1, 5], tr)
    @test E.seedbank_weight(sb) == 15.0                       # exactly FIT's yearly count, not more
    @test [e.pft_id for e in sb.entries] == [5, 3, 1]         # AGB descending: 2000, 1000, 500
    @test [e.weight for e in sb.entries] == [6.0, 4.0, 5.0]   # the crossing cohort capped at the remainder
    # a cohort with no individuals, a non-tree id, or a non-positive AGB never enters
    sb2 = E.Seedbank{Float64}()
    @test E.seedbank_update!(sb2, 0, [1000.0, 1000.0, 0.0], [0.0, 5.0, 5.0], [3, 8, 3], tr) == 0
    # PRUNING at `max_age` uses `>=` (getsapling.c:38): a 50-year-old seed is gone, a 49-year-old is not
    sb3 = E.Seedbank{Float64}(; max_age = 50)
    E.seedbank_update!(sb3, 0, [1000.0], [3.0], [3], [tr[1]])
    E.seedbank_update!(sb3, 49, Float64[], Float64[], Int[], NTuple{4, Float64}[])
    @test length(sb3.entries) == 1
    E.seedbank_update!(sb3, 50, Float64[], Float64[], Int[], NTuple{4, Float64}[])
    @test isempty(sb3.entries)
    # an UNSET (0) or non-finite parent axis is recorded as NaN, and a finite one is clamped into the
    # parent PFT's interval — the two invariants FIT gets for free (see `_seed_trait`)
    sb4 = E.Seedbank{Float64}()
    E.seedbank_update!(sb4, 0, [1000.0], [3.0], [3], [(0.5, 2.0e5, 0.0, -1.0)])
    e4 = sb4.entries[1]
    @test e4.sla == E.pft_estab_params(3).sla_high            # 0.5 clamped down into id 3's interval
    @test isnan(e4.d95max) && isnan(e4.minwscal)             # UNSET stays UNSET, not clamped up to 51

    # ── (7) the rule itself: channel mix, weighting, and the two forced-channel cases ────────────────
    rng = DRF.Xoshiro256pp(101)
    # an EMPTY seedbank can only draw background (establishmentpft_ind.c:122 requires treelen > 0)
    empty_sb = E.Seedbank{Float64}()
    bg = [E.draw_recruit!(rng, empty_sb, [1, 3]) for _ in 1:500]
    @test !any(d.inherited for d in bg)
    @test all(d.pft_id in (1, 3) for d in bg)
    # NO eligible PFT but a filled bank ⇒ inheritance only (a warmed cell whose gate has closed)
    ds = [E.draw_recruit!(rng, sb, Int[]) for _ in 1:200]
    @test all(d.inherited for d in ds)
    # neither ⇒ an error, not a silent default: a patch that can establish nothing must not be asked
    @test_throws ErrorException E.draw_recruit!(rng, empty_sb, Int[])
    # the realised inherited share is the closed form, and inheritance samples parents ∝ weight
    rng = DRF.Xoshiro256pp(202)
    N = 40_000
    draws = [E.draw_recruit!(rng, sb, [1, 2, 3]) for _ in 1:N]
    @test abs(count(d -> d.inherited, draws) / N - E.w_inherit(3)) < 0.01
    inh = filter(d -> d.inherited, draws)
    for (id, w) in ((5, 6.0), (3, 4.0), (1, 5.0))
        @test abs(count(d -> d.pft_id == id, inh) / length(inh) - w / 15.0) < 0.02
    end
    # every drawn trait lies inside its OWN PFT's interval — the property that makes the port safe to
    # hand to `_recruit_pools` (whose clamp is the union of intervals and would hide a per-PFT violation)
    for d in draws
        p = E.pft_estab_params(d.pft_id)
        @test p.sla_low <= d.sla <= p.sla_high
        @test p.wooddens_low <= d.wooddens <= p.wooddens_high
        @test p.d95max_low <= d.d95max <= p.d95max_high
        @test p.minwscal_low <= d.minwscal <= p.minwscal_high
    end
    # DETERMINISM given the seed (the whole rule is one RNG stream, no global state)
    a = [E.draw_recruit!(DRF.Xoshiro256pp(7), sb, [1, 2, 3]) for _ in 1:1]
    b = [E.draw_recruit!(DRF.Xoshiro256pp(7), sb, [1, 2, 3]) for _ in 1:1]
    @test a[1].pft_id == b[1].pft_id && a[1].sla == b[1].sla && a[1].wooddens == b[1].wooddens
end

@testitem "Ported FIT establishment (ADR 0119) — operator: default inert, recruits from the C's own rule (Hainich 42490)" tags = [:conservation, :coupling, :scientific, :slow] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
    using LPJmLFITEmulator.DRF
    using Test
    const E = LPJmLFITEmulator.Establishment

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
    nday = length(fc_("doy"))

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
            ) for i in 1:nday
    ]
    pft_ids = [nt(r) for r in rows]
    mkcore() = FDiffFastCore([mkp(r) for r in rows], [mkt(r) for r in rows], soil, 51.25; pft_ids = pft_ids)
    mkclo() = SEBEnergyClosure(; t_soil0 = _mean(tair_K))
    mkstate() = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))

    # a controllable DRF keyed on the AR feature (column 11) ⇒ ρ ≈ c; c > 1 forces ESTABLISHMENT every year
    nbound = 3
    nfeat = 11 + nbound
    function ratio_forest(c; seed = 7)
        r = DRF.Xoshiro256pp(seed)
        m = 3000
        X = Matrix{Float64}(undef, m, nfeat); y = Vector{Float64}(undef, m)
        for i in 1:m
            for ff in 1:nfeat
                X[i, ff] = DRF.rand01!(r)
            end
            ar = 0.5 + 59.5 * DRF.rand01!(r)
            X[i, 11] = ar
            y[i] = c * ar + 0.005 * (DRF.rand01!(r) - 0.5)
        end
        return DRF.fit_forest(
            X, y; ntrees = 60, subsample = 1500, max_depth = 16, min_leaf = 6, mtry = nfeat, seed = seed
        )
    end
    boundary = [0.3, 0.5, 0.7]
    forest = ratio_forest(1.15)
    nyear = 6
    forcings = repeat(year_forc, nyear)

    # ── (1) THE DEFAULT IS INERT (guardrail 4): no hook ⇒ no diagnostics, and every recruit carries the
    #        fixed sapling's traits exactly, i.e. the pre-ADR-0119 code path. ──
    ctl_core = mkcore()
    ctl = FluxDrivenSlowEmulator(ctl_core, forest; boundary = boundary, n_init = 10.0, seed = 1)
    run_coupled_cell(ctl_core, mkclo(), mkstate(), forcings; slow = ctl, days_per_year = nday)
    @test isempty(establishment_diag(ctl))
    @test ctl.recruit_establishment === nothing
    @test length(ctl_core.pools) > length(pft_ids)              # it really did recruit
    for i in (length(pft_ids) + 1):length(ctl_core.pools)
        @test ctl_core.pools[i].sla == ctl.sapl.sla
        @test ctl_core.pools[i].wooddens == ctl.sapl.wooddens
    end

    # ── (2) THE RULE FIRES, and every recruit's traits come from the C's own intervals ──
    arm_core = mkcore()
    arm = FluxDrivenSlowEmulator(
        arm_core, forest; boundary = boundary, n_init = 10.0, seed = 1,
        recruit_establishment = RecruitEstablishment(; eligible = [1, 2, 3, 4, 5]),
    )
    run_coupled_cell(arm_core, mkclo(), mkstate(), forcings; slow = arm, days_per_year = nday)
    dg = establishment_diag(arm)
    @test !isempty(dg)                                          # the operator actually drew
    @test all(d.drew for d in dg)
    @test all(d.n_elig == 5 for d in dg)
    @test all(d.w_inherit ≈ 4 / 9 for d in dg)
    @test all(d.pft_id in 1:5 for d in dg)
    # the seedbank FILLS from the emulator's own roster (this is the feedback loop ADR 0119 §5 flags)
    @test dg[1].sb_weight > 0
    @test dg[end].sb_weight >= dg[1].sb_weight
    @test dg[end].sb_entries > dg[1].sb_entries
    # the first year cannot inherit unless the bank already holds parents; by the last year it can, and
    # DOES for at least some draws in a bank this size — the mix is what makes the arm interpretable
    @test any(d.inherited for d in dg)
    # every appended recruit's traits are a real draw, not the fixed sapling, and lie in the union of the
    # C's per-PFT intervals (`_recruit_pools`'s clamp) with the two ADR-0110 axes now SET
    recruits = arm_core.pools[(length(pft_ids) + 1):end]
    @test !isempty(recruits)
    @test any(p.sla != arm.sapl.sla for p in recruits)
    for p in recruits
        @test 0.005 <= p.sla <= 0.07
        @test 7.0e4 <= p.wooddens <= 6.5e5
        @test 51.0 <= p.d95max <= 1800.0
        @test 0.025 <= p.minwscal <= 0.75
        @test p.height > 0 && p.crownarea > 0
    end
    # `set_pft_id = false` (the default) leaves the roster's ids alone — the drawn id is recorded only,
    # because the canopy TEMPLATE still carries the donor cohort's per-PFT physiology
    @test all(id in pft_ids for id in arm_core.pft_ids)

    # ── (3) CARBON STILL CLOSES (guardrail 2) and the roster stays in lockstep ──
    @test abs(arm.last_resid) < 1.0e-6 * max(1.0, sum(FDiff.vegc_full_ind(p) * p.nind for p in arm_core.pools))
    @test length(arm_core.pools) == length(arm_core.tmpls) == length(arm_core.pft_ids) == length(arm.age)

    # ── (4) DETERMINISM: same seed ⇒ the same recruits, the same diagnostics ──
    rep_core = mkcore()
    rep = FluxDrivenSlowEmulator(
        rep_core, forest; boundary = boundary, n_init = 10.0, seed = 1,
        recruit_establishment = RecruitEstablishment(; eligible = [1, 2, 3, 4, 5]),
    )
    run_coupled_cell(rep_core, mkclo(), mkstate(), forcings; slow = rep, days_per_year = nday)
    @test [d.pft_id for d in establishment_diag(rep)] == [d.pft_id for d in dg]
    @test [d.inherited for d in establishment_diag(rep)] == [d.inherited for d in dg]
    @test [p.sla for p in rep_core.pools] == [p.sla for p in arm_core.pools]

    # ── (5) `set_pft_id = true` writes the DRAWN id into the roster. Deliberately measured, not on:
    #        the recruit's template is still the donor cohort's, so this is an inconsistent individual
    #        until a per-PFT template registry exists (the integration point with line M). ──
    #        It is bounded by the fast core: an id absent from `fc.pft_slot` would be rejected by
    #        `_commit_membership!`, so the constructor refuses it up front instead of failing in whichever
    #        later year the background channel first draws it.
    #        The contrast is made DETERMINISTIC by switching the inheritance channel off (`n_top = 0` ⇒
    #        nothing ever enters the seedbank ⇒ every draw is a background draw), so a single eligible id
    #        that the donor cohort does NOT carry must appear on every recruit. Leaving the channel mix in
    #        would make this a coin flip on the seed — the arm drew id 3 five times out of five at one
    #        seed simply because beech dominates the Hainich seedbank.
    roster_ids = sort(unique(pft_ids))
    off_core = mkcore()
    off = FluxDrivenSlowEmulator(
        off_core, forest; boundary = boundary, n_init = 10.0, seed = 3,
        recruit_establishment = RecruitEstablishment(; eligible = roster_ids),
    )
    run_coupled_cell(off_core, mkclo(), mkstate(), forcings; slow = off, days_per_year = nday)
    off_ids = off_core.pft_ids[(length(pft_ids) + 1):end]
    @test !isempty(off_ids)
    @test length(unique(off_ids)) == 1                           # the DONOR cohort's id, every year
    donor = off_ids[1]
    other = first(filter(!=(donor), roster_ids))
    pid_core = mkcore()
    pid = FluxDrivenSlowEmulator(
        pid_core, forest; boundary = boundary, n_init = 10.0, seed = 3,
        recruit_establishment = RecruitEstablishment(;
            seedbank = LPJmLFITEmulator.Establishment.Seedbank{Float64}(; n_top = 0),
            eligible = [other], set_pft_id = true,
        ),
    )
    run_coupled_cell(pid_core, mkclo(), mkstate(), forcings; slow = pid, days_per_year = nday)
    dpid = establishment_diag(pid)
    @test !isempty(dpid)
    @test all(!d.inherited for d in dpid)                        # n_top = 0 ⇒ background channel only
    @test all(d.sb_weight == 0 && d.sb_entries == 0 for d in dpid)
    @test all(d.pft_id == other for d in dpid)
    # every recruit cohort carries the id its own draw produced, in append order — that IS what
    # `set_pft_id` does, and it is the only way to see it (a diagnostic alone would not prove the write)
    @test pid_core.pft_ids[(length(pft_ids) + 1):end] == [d.pft_id for d in dpid]
    @test all(==(other), pid_core.pft_ids[(length(pft_ids) + 1):end])   # ≠ the donor id the OFF arm wrote
    @test other != donor
    # an id outside the fast core's registry is refused AT CONSTRUCTION, not mid-run
    @test_throws ErrorException FluxDrivenSlowEmulator(
        mkcore(), forest; boundary = boundary,
        recruit_establishment = RecruitEstablishment(; eligible = [0, 6], set_pft_id = true),
    )

    # ── (6) the two samplers are MUTUALLY EXCLUSIVE — both set the recruit marginal, from bases that
    #        differ by a measured +12.18 % on Wooddens (ADR 0118 §2), so the constructor refuses. ──
    cop = DRF.GaussianCopula([1.0 0.0; 0.0 1.0])
    rc = RecruitCopula{Float64}(
        cop, DRF.Forest[], zeros(Float64, 4 + nbound), make_recruit_to_pools(["SLA", "Wooddens"])
    )
    @test_throws ErrorException FluxDrivenSlowEmulator(
        mkcore(), forest; boundary = boundary, recruit_copula = rc,
        recruit_establishment = RecruitEstablishment(),
    )

    # ── (7) a non-tree eligible id is refused when the sampler is BUILT, not on whichever later year the
    #        Bernoulli channel draw first happens to pick it (grass ids carry zeroed tree fields, so a
    #        lenient lookup would hand a recruit a 0-wide interval) ──
    @test_throws ErrorException RecruitEstablishment(; eligible = [8])
    @test_throws ErrorException RecruitEstablishment(; eligible = [3, 22])
    @test_throws ErrorException RecruitEstablishment(; eligible = Int[])   # neither channel could fire
end
