# Gate — below-ground root-sapwood pool `sapwood_bg` (docs/sapwood_bg_design.md §8; scale-up step 11 follow-up #11).
# Wires the §8 quantification-probe result into the model. F_diff omitted the C's below-ground root-sapwood
# pool `sapwood_bg`, so it never paid that pool's phen-gated maintenance respiration (`npp_tree.c:51`) and its
# tree CUE (NPP/GPP) sat ~0.51 vs the C's ~0.46. This step adds the pool (opt-in, default `sapwood_bg_c=0` ⇒
# byte-identical) + its maintenance term in `autotrophic_respiration`, and seeds it from the C's C_LATERAL
# allocation demand (`reconstruct_sapwood_bg`, `allocation_tree.c:163-189`). The pool is static-seeded this
# step (its prognostic C_LATERAL growth + carbon-debt is the deferred design-§5.4 item), so the multi-year
# rollouts + the Enzyme trainer are byte-identical (they never seed it).
#
# This gate locks in the wired behaviour against the committed Hainich 2010 structure (no HPC dependency):
#  (a) UNSEEDED cell CUE is unchanged (= the `multi_individual` gate value ~0.512);
#  (b) GPP is byte-identical seeded vs unseeded (maintenance changes NPP, not GPP);
#  (c) seeding LOWERS NPP → CUE, moving it toward the C's 0.46 (lands ~0.497 — the growth-respiration-rebated
#      decrement the model applies inside `autotrophic_respiration`), and it stays inside the CUE band
#      [0.42, 0.56] with margin (the design §4.2 floor-break fear is refuted);
#  (d) the reconstructed pool matches the probe (cell-mean ~531 gC/m² = ~23% of aboveground sapwood).
@testitem "sapwood_bg — seeding + phen-gated maintenance moves tree CUE toward the C (Hainich 42490, 2010)" tags = [:validation, :fdiff, :canopy] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using Test
    import LPJmLFITEmulator.FDiff: reconstruct_sapwood_bg, Individual, PhotoParams, TempStressParams

    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = readlines(path)
        i = findfirst(l -> !startswith(strip(l), "#") && !isempty(strip(l)), lines)
        hdr = split(strip(lines[i]), ',')
        rows = [split(strip(l), ',') for l in lines[(i + 1):end] if !isempty(strip(l))]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    fcol(d, k) = parse.(Float64, d[k])
    function readtable(path)
        D = Float64[]; W = Float64[]; R = Float64[]
        for ln in eachline(path)
            s = strip(ln)
            (isempty(s) || startswith(s, "#")) && continue
            v = parse.(Float64, split(s))
            push!(D, v[2]); push!(W, v[3]); push!(R, v[4])
        end
        return (D, W, R)
    end

    f = readcsv(joinpath(refdir, "hainich_forcing_2010.csv"))
    ind = readcsv(joinpath(refdir, "hainich_individuals_2010.csv"))
    (soildepth, whcs, rootdist) = readtable(joinpath(refdir, "hainich_soilcolumn.txt"))
    soil = hainich_soilcolumn(; whcs = whcs, rootdist = rootdist, soildepth = soildepth)
    n = length(f["doy"])
    @test n == 365
    @test all(k -> haskey(ind, k), ("sapwood_c", "height", "wooddens", "nind", "type"))

    forc = [
        DailyForcing{Float64}(
                swdown = fcol(f, "swdown")[i], lwnet = fcol(f, "lwnet")[i], temp = fcol(f, "temp")[i],
                precip = fcol(f, "precip")[i], daylength = fcol(f, "daylength")[i], co2 = fcol(f, "co2")[i],
            ) for i in 1:n
    ]

    patches = sort(unique(parse.(Int, ind["patch"])))
    prows = Dict(p => Int[] for p in patches)
    for r in eachindex(ind["patch"])
        push!(prows[parse(Int, ind["patch"][r])], r)
    end
    pft_intc(typ) = typ <= 3 ? 0.02 : (typ <= 6 ? 0.06 : 0.01)
    function pft_albedo(typ)
        typ == 1 && return (0.04, 0.1, 0.1)
        typ in (2, 3) && return (0.04, 0.1, 0.4)
        typ in (4, 5) && return (0.1, 0.1, 0.15)
        typ == 6 && return (0.05, 0.01, 0.15)
        return (0.15, 0.1, 0.4)
    end

    # per-individual `sapwood_bg` seed from the C_LATERAL demand (trees only; grass has no woody sapwood)
    bgseed(r) = reconstruct_sapwood_bg(
        parse(Float64, ind["sapwood_c"][r]), parse(Float64, ind["height"][r]),
        parse(Float64, ind["wooddens"][r]), rootdist, soildepth,
    )
    # build an Individual EXACTLY as the multi_individual CUE gate's `mkind`, with an optional seeded pool
    function mkind(r; seed = false)
        sla = parse(Float64, ind["sla"][r]); typ = parse(Int, ind["type"][r])
        (ast, alt, scf) = pft_albedo(typ)
        cbg = (seed && typ < 7) ? bgseed(r) : 0.0
        return Individual{Float64}(
            parse(Float64, ind["fpar_leafon"][r]), parse(Float64, ind["fpc_ind"][r]),
            parse(Float64, ind["alphaa"][r]), parse(Float64, ind["albedo_leaf"][r]), parse(Float64, ind["emax"][r]),
            parse(Float64, ind["sapwood_c"][r]), parse(Float64, ind["root_c"][r]), cbg,
            parse(Float64, ind["lai"][r]), pft_intc(typ), ast, alt, scf, parse(Float64, ind["nind"][r]),
            PhotoParams{Float64}(; path = :c3, issla = true, sla = sla),
            TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0),
            typ >= 7,
        )
    end

    # cell-mean annual GPP + NPP over the 25 patches (the CUE gate basis), unseeded vs seeded
    function cellflux(seed)
        gpp = 0.0; npp = 0.0
        for pnum in patches
            inds = [mkind(r; seed = seed) for r in prows[pnum]]
            st0 = FDiffStateML{Float64}([0.9 * wc for wc in whcs], 0.0)
            (_, days) = rollout_daily_canopy(tebs_params(), st0, inds, soil, forc)
            gpp += sum(days[i].gpp for i in 1:n) / length(patches)
            npp += sum(days[i].npp for i in 1:n) / length(patches)
        end
        return (gpp, npp)
    end

    (gpp0, npp0) = cellflux(false)
    (gpp1, npp1) = cellflux(true)
    cue0 = npp0 / gpp0
    cue1 = npp1 / gpp1

    # reconstructed pool (cell-mean, per m²) + aboveground sapwood (per m²)
    bg_perm2 = 0.0; sap_perm2 = 0.0
    for pnum in patches, r in prows[pnum]
        parse(Int, ind["type"][r]) >= 7 && continue
        ni = parse(Float64, ind["nind"][r])
        bg_perm2 += bgseed(r) * ni / length(patches)
        sap_perm2 += parse(Float64, ind["sapwood_c"][r]) * ni / length(patches)
    end

    # (a) unseeded cell CUE unchanged (= the multi_individual gate value ~0.512)
    @test 0.42 <= cue0 <= 0.56
    @test isapprox(cue0, 0.5118; atol = 0.01)

    # (b) GPP byte-identical seeded vs unseeded — the maintenance term changes NPP, never GPP
    @test gpp1 == gpp0

    # (c) seeding lowers NPP → CUE, toward the C's 0.46, and stays IN-BAND (floor-break fear refuted)
    @test npp1 < npp0
    @test cue1 < cue0
    @test 0.42 <= cue1 <= 0.56
    @test isapprox(cue1, 0.497; atol = 0.008)     # 0.512 → ~0.497 (growth-resp-rebated; probe §8: 0.4973)

    # (d) reconstructed pool matches the §8 probe (~531 gC/m² = ~23% of aboveground sapwood)
    @test isapprox(bg_perm2, 531.4; rtol = 0.05)
    @test isapprox(bg_perm2 / sap_perm2, 0.227; rtol = 0.05)

    # sapwood_bg is a TREE pool: every grass individual seeds 0 even under `seed=true` (the `typ<7` guard)
    let seeded = [mkind(r; seed = true) for p in patches for r in prows[p]]
        grassinds = [x for x in seeded if x.is_grass]
        @test !isempty(grassinds)                           # Hainich has understory grass
        @test all(x -> x.c_sapwood_bg == 0.0, grassinds)    # grass never seeds a below-ground sapwood pool
        @test any(x -> x.c_sapwood_bg > 0.0, seeded)        # trees DO seed a positive pool
    end
end
