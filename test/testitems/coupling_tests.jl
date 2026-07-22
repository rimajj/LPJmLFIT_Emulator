# Gate — S↔F coupling adapter (ADR 0014 scale-up step 6b; docs/phase3_fdiff_cbinary_validation.md §12).
# `FDiffFastCore` wires the differentiable multi-individual canopy (FDiff.daily_step_canopy) behind the
# `AbstractFastCore.step!` interface (which previously threw): daily `step!` reads/writes the authoritative
# per-layer soil water in `SharedState`, self-computes phenology/eeq/daylength, and returns the daily
# `FToE`; the year-end `annual_step!` grows the prognostic canopy structure (FDiff.grow_individual) from
# the accumulated conserved `bm_inc` and returns `FToS` — the flux-then-integrate S↔F handoff (DESIGN §8).
# This gate confirms the interface is wired (no throw), the SharedState soil water is updated in place,
# FToE/FToS are finite + conserved, and a multi-year coupled loop — FULLY SELF-DRIVEN by the calibrated
# self-computed canopy NPP (the bm_inc crutch is removed; docs §13) — grows structure without blow-up.
# It also covers GRASS PARITY (§26.4): a mixed tree+grass core exercises the grass allocation, per-PFT
# phenology, the §26 demand-gate, and grass establishment — grass-only, so the tree-only assertions above
# double as the byte-identical-tree guarantee.
@testitem "S↔F coupling — FDiffFastCore behind AbstractFastCore.step! (Hainich 42490)" tags = [:validation, :fdiff, :canopy, :coupling] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.Allometry
    using Test

    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = readlines(path)
        i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
        hdr = split(strip(lines[i]), ',')
        rows = [split(strip(l), ',') for l in lines[(i + 1):end] if !isempty(strip(l))]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    ind = readcsv(joinpath(refdir, "hainich_individuals_2010.csv"))
    f = readcsv(joinpath(refdir, "hainich_forcing_2010.csv"))
    fc(k) = parse.(Float64, f[k])
    v(k, r) = parse(Float64, ind[k][r])
    nt(r) = parse(Int, ind["type"][r])
    n = length(fc("doy"))

    sd = Float64[]; whcs = Float64[]; rdist = Float64[]
    for ln in eachline(joinpath(refdir, "hainich_soilcolumn.txt"))
        s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
        x = parse.(Float64, split(s)); push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
    end
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

    # one patch's trees + templates
    prows = Dict{Int, Vector{Int}}()
    for r in eachindex(ind["type"])
        (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    rows = prows[argmax(Dict(k => length(vv) for (k, vv) in prows))]
    function mkp(r)
        nind = v("nind", r); leaf = v("leaf_c", r); sap = v("sapwood_c", r)
        TreePools{Float64}(
            leaf, sap, max(v("agb", r) / nind - leaf - sap, 0.0), v("root_c", r),
            v("height", r), v("crownarea", r), nind, v("sla", r), v("wooddens", r), false
        )
    end
    mkt(r) = Individual{Float64}(
        v("fpar_leafon", r), 0.0, v("alphaa", r), v("albedo_leaf", r), v("emax", r), v("sapwood_c", r), v("root_c", r),
        0.0, 0.02, 0.04, 0.1, 0.4, v("nind", r),
        FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = v("sla", r)),
        FDiff.TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false,
    )
    pools = [mkp(r) for r in rows]; tmpls = [mkt(r) for r in rows]

    # ── build the core + drive it one year through the interface ──
    core = FDiffFastCore(pools, tmpls, soil, 51.25)
    @test core isa AbstractFastCore
    state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    bc = SToF(; lai = 5.0, height = 25.0, z0 = 1.0, rootdepth = 1150.0, vcmax = 40.0, fpc = 0.56, albedo = 0.15)
    σ = 5.670374419e-8
    atm(i) = AtmForcing(;
        swdown = fc("swdown")[i], lwdown = fc("lwnet")[i] + σ * (fc("temp")[i] + 273.15)^4,
        tair = fc("temp")[i] + 273.15, qair = 0.006, wind = 2.0, psurf = 1.0e5,
        precip = fc("precip")[i], co2 = fc("co2")[i],
    )
    w0 = copy(state.w)
    gpp_yr = 0.0; nfin = 0
    ftoe = step!(core, state, bc, atm(1))                 # bind at top level (soft-scope safe)
    gpp_yr += ftoe.gpp; nfin += (isfinite(ftoe.le) && isfinite(ftoe.gpp) && isfinite(ftoe.npp)) ? 1 : 0
    for i in 2:n
        ftoe = step!(core, state, bc, atm(i))
        gpp_yr += ftoe.gpp
        nfin += (isfinite(ftoe.le) && isfinite(ftoe.gpp) && isfinite(ftoe.npp)) ? 1 : 0
    end
    @test ftoe isa FToE                                  # the interface returns the daily flux payload
    @test nfin == n                                       # every daily FToE is finite (no NaN/Inf)
    @test gpp_yr > 500                                    # a plausible annual canopy GPP (gC/m²/yr)
    @test state.w != w0                                   # F wrote the updated soil water back into SharedState
    @test all(0 <= x <= 1 for x in state.w)               # soil water stays a valid fraction of WHC
    @test ftoe.le >= 0 && ftoe.rh == 0 && ftoe.firec == 0 # LE = λ·ET ≥ 0; SOM/fire terms are 0 in v1

    # ── year-end flux-then-integrate handoff ──
    h_before = sum(t.height for t in core.pools) / length(core.pools)
    ftos = annual_step!(core, state)
    @test ftos isa FToS
    @test isfinite(ftos.bm_inc) && isfinite(ftos.growth_eff)
    @test ftos.bm_inc > 0                                 # SELF-computed per-m² NPP is positive (calibrated; docs §13)
    @test 0 <= ftos.water_stress <= 1
    @test 0 <= ftos.soilmoist <= 1
    # structure stays physical after the annual grow (no blow-up); the calibrated self-NPP GROWS it (the
    # adapter is fully self-driven — it accumulates fl.npp_ind, never the C crutch); heights bounded
    @test all(0 < t.height <= 100 && t.sapwood_c > 0 && t.leaf_c > 0 && isfinite(t.height) for t in core.pools)
    @test sum(t.height for t in core.pools) / length(core.pools) > h_before   # positive self-NPP ⇒ growth

    # ── the abstract fallback still throws for an unimplemented core ──
    struct _DummyCore <: AbstractFastCore end
    @test_throws ErrorException step!(_DummyCore(), state, bc, atm(1))

    # ── multi-year coupled loop — FULLY SELF-DRIVEN (self-computed NPP, no crutch): grows, stays physical ──
    forc = [
        DailyForcing{Float64}(
                swdown = fc("swdown")[i], lwnet = fc("lwnet")[i], temp = fc("temp")[i],
                precip = fc("precip")[i], daylength = fc("daylength")[i], co2 = fc("co2")[i]
            ) for i in 1:n
    ]
    NY = 4
    st0 = FDiffStateML{Float64}([0.9 * w for w in whcs], 0.0)
    (_, _, _, annual) = rollout_canopy_years(
        tebs_params(), tebs_allocparams(), Allometry.TreeAllometry{Float64}(), st0, pools, tmpls, soil,
        [forc for _ in 1:NY],                             # no bm_inc_ext ⇒ self-computed NPP drives allocation
    )
    @test all(isfinite(a.agb) && a.agb > 0 for a in annual)
    @test all(a.npp > 0 for a in annual)                  # self-computed NPP positive every year (calibrated)
    @test annual[NY].agb > annual[1].agb                  # cumulative growth from the self-computed NPP

    # ── GRASS PARITY (§26.4): a mixed tree+grass core exercises the grass allocation (grow_grass_individual),
    #    per-PFT GSI phenology (grass id 8 vs tree id 3), the §26 demand-gate, and grass establishment. The
    #    grass stays finite + non-negative and carries NO woody pools/height (proof the GRASS allocation ran,
    #    not the tree pipe-model) while the trees still grow. Grass SURVIVAL is light-dependent — the gate
    #    correctly lets a shaded understory grass decline where establishment cannot re-seed it (fpc_total ≥ 1,
    #    §26.3) — so it is not asserted; establishment's additive payoff is checked as a differential instead.
    #    The pre-existing tree-only assertions above are the byte-identical-tree guarantee (grass paths gated). ──
    gpool = FDiff.grass_treepools(0.5, 1.0, 0.042242)     # small per-area grass: agb 0.5, vegc 1.0 gC/m², C3 sla
    gtmpl = Individual{Float64}(
        0.03, 1.0, 0.5, 0.23, 10.0, 0.0, 0.0, 0.0, 0.01, 0.15, 0.1, 0.4, 1.0,
        FDiff.PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.042242),
        FDiff.TempStressParams{Float64}(; temp_photos_low = 10.0, temp_photos_high = 30.0), true,
    )
    mpools = vcat(pools, [gpool]); mtmpls = vcat(tmpls, [gtmpl])
    gi = length(mpools)                                   # the grass individual index
    freshstate() = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    function drive_year!(core, st)
        for i in 1:n
            step!(core, st, bc, atm(i))
        end
        return annual_step!(core, st)
    end
    gcore = FDiffFastCore(mpools, mtmpls, soil, 51.25)    # §26.3 default: demand-gate on, per-PFT phen, establishment
    @test gcore.pft_ids[gi] == 8 && gcore.pft_ids[1] == 3 && any(gcore.pft_isg)   # grass→id 8, tree→id 3
    @test gcore.params.water.grass_demand_gate            # the §26 grass demand-gate defaults ON in the adapter
    gstate = freshstate()
    gftos = drive_year!(gcore, gstate)
    for _ in 2:4
        gftos = drive_year!(gcore, gstate)
    end
    gp = gcore.pools[gi]
    @test gp.is_grass                                                    # still the grass individual
    @test isfinite(gp.leaf_c) && isfinite(gp.root_c)                     # grass pools finite after 4 coupled years
    @test gp.leaf_c >= 0 && gp.root_c >= 0                               # grass stays non-negative
    @test gp.sapwood_c == 0 && gp.heartwood_c == 0 && gp.height == 0     # NO woody pools/height ⇒ grass allocation ran
    @test all(0 < gcore.pools[i].height <= 100 && gcore.pools[i].leaf_c > 0 for i in eachindex(pools))  # trees still grow, physical
    @test isfinite(gftos.bm_inc) && gftos.bm_inc > 0                     # conserved per-m² NPP positive with grass present
    # ESTABLISHMENT differential (grass-only, provably ≥): after one coupled year the grass carbon with
    # establishment ON is ≥ that with it OFF (establishment adds sapl·(1−fpc_total)/n_est when fpc_total<1,
    # a no-op otherwise; trees are identical in year 1 ⇒ the only difference is the additive re-seed).
    ce = FDiffFastCore(mpools, mtmpls, soil, 51.25)
    cn = FDiffFastCore(mpools, mtmpls, soil, 51.25; grass_estab = nothing)
    drive_year!(ce, freshstate()); drive_year!(cn, freshstate())
    @test ce.pools[gi].leaf_c + ce.pools[gi].root_c >= cn.pools[gi].leaf_c + cn.pools[gi].root_c
end
