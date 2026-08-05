# Multi-cell / biome generalization of the coupled S+F+E emulator (line M, milestone M1 — per-cell input
# provisioning). Drives the coupled loop (`run_coupled_cell`) with the REAL GSWP3-W5E5 committed forcing of
# five biome-representative cells (boreal / temperate / mediterranean / semi-arid / tropical), each now with
# ITS OWN soil column and ITS OWN reconstructed canopy:
#   references/M_cells.csv                    cell index + latitude (global run's grid.nc `cellid`)
#   references/M_soilcolumn_<name>.txt        scripts/extract_cell_soilcolumn.py
#   references/M_individuals_<name>_2010.csv  scripts/extract_cell_individuals.py
#   references/biome_forcing_<name>.csv       scripts/extract_biome_forcing.py
# Before M1 all five cells reused Hainich's soil and Hainich's canopy (deliberately, to isolate the climate
# effect). Asserts (1) the per-cell inputs are well-formed AND genuinely distinct — the regression guard
# against silently falling back to one cell's inputs, (2) the Phase-4 hard gate still holds EVERYWHERE with
# per-cell vegetation — energy closes to machine precision across the full climate envelope, and (3) the
# emergent partitioning still tracks the climate: tropical is LE-dominated (low Bowen), the dry biomes are
# H-dominated (high Bowen), and the wet/warm tropics evaporate far more than the cold boreal cell.

@testitem "Per-cell soil columns + canopies are well-formed and genuinely distinct" tags = [:validation, :coupling, :multicell] begin
    using LPJmLFITEmulator
    using Test

    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
        hdr = split(strip(lines[1]), ',')
        rows = [split(strip(l), ',') for l in lines[2:end]]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    function readsoil(path)
        sd = Float64[]; whcs = Float64[]; rd = Float64[]
        for ln in eachline(path)
            s = strip(ln)
            (isempty(s) || startswith(s, "#")) && continue
            x = parse.(Float64, split(s))
            push!(sd, x[2]); push!(whcs, x[3]); push!(rd, x[4])
        end
        return sd, whcs, rd
    end

    cells = readcsv(joinpath(refdir, "M_cells.csv"))
    names = String.(cells["name"])
    @test length(names) ≥ 5
    # ── name -> (cell, lat, lon) ROW-WISE, not as a set. A set comparison is order-blind,
    # so a two-value typo in the BIOMES registry regenerates every fixture consistently
    # MISLABELLED (e.g. `boreal_siberia,18371,13.75`) and still passes. lat/lon come from
    # grid.nc `cellid`, so pinning them pins the identity of the cell each name refers to.
    expect = Dict(
        "boreal_siberia" => (52059, 61.75, 104.75), "temperate_hainich" => (42490, 51.25, 10.25),
        "mediterranean_iberia" => (33335, 39.75, -4.25), "semiarid_sahel" => (18371, 13.75, 4.75),
        "tropical_amazon" => (12045, -3.25, -60.25),
    )
    for (nm, (cell, lat, lon)) in expect
        k = findfirst(==(nm), names)
        @test k !== nothing
        @test parse(Int, cells["cell"][k]) == cell
        @test parse(Float64, cells["lat"][k]) == lat
        @test parse(Float64, cells["lon"][k]) == lon
    end

    # LPJmL-FIT's cell-invariant layering (par/soil_20m.js) — the same for every cell
    soildepth_C = vcat([200.0, 300.0, 500.0], fill(1000.0, 19), [3000.0])
    whcs_all = Vector{Float64}[]; rd_all = Vector{Float64}[]
    for name in names
        sd, whcs, rd = readsoil(joinpath(refdir, "M_soilcolumn_$(name).txt"))
        @test length(sd) == LPJmLFITEmulator.NSOILLAYER
        @test sd == soildepth_C
        # a zero whcs would make F_diff's `rel = w / whcs` NaN and poison SharedState.w
        @test all(>(0.0), whcs)
        # F_diff's water supply scales LINEARLY with sum(rootdist), and `stand_structure_tof`'s
        # D95 loop never terminates below 0.95 — so the profile must be normalized. The extractor
        # normalizes to 1e-9; every committed column's PRINTED sum is within 1e-6, so 2e-6 is the
        # right bound (the 1.15e-5 worst-case print rounding of 23 values never materializes, and
        # a looser bound would admit the legacy form's below-column-bottom leak).
        @test all(≥(0.0), rd)
        @test isapprox(sum(rd), 1.0; atol = 2.0e-6)
        @test rd[end] == 0.0        # layer 22 (20-23 m) never holds roots (getrootdist.c)
        # ── the extractor's correctness GATE must have PASSED for this file (M1 review debt #2,
        # closed 2026-08-05 / ADR 0055). `GATE=no` used to warn on stderr and then emit a column
        # STRUCTURALLY INDISTINGUISHABLE from gated output, so an ungated fixture could be committed
        # later by someone who never saw the warning. The verdict now travels in the header, and this
        # asserts it — which is what makes the debt closed rather than merely mitigated.
        hdr = [l for l in readlines(joinpath(refdir, "M_soilcolumn_$(name).txt")) if startswith(l, "# GATE:")]
        @test length(hdr) == 1
        @test occursin("PASS", hdr[1])
        push!(whcs_all, whcs); push!(rd_all, rd)
    end

    # ── genuinely per-cell: every pair of cells differs in BOTH soil water and rooting ──
    for i in 1:length(names), j in (i + 1):length(names)
        @test whcs_all[i] != whcs_all[j]
        @test rd_all[i] != rd_all[j]
    end

    # ── the emergent rooting gradient (FIT's own trait distributions, not a tuned input) ──
    idx = Dict(n => k for (k, n) in enumerate(names))
    top1m(n) = sum(rd_all[idx[n]][1:3])
    @test top1m("semiarid_sahel") > top1m("temperate_hainich")   # semi-arid = shallow-rooted
    @test top1m("temperate_hainich") > top1m("tropical_amazon")  # tropical = deep-rooted
    @test top1m("mediterranean_iberia") < top1m("boreal_siberia")  # summer-dry => deeper roots

    # ── PROVENANCE PINS: which column belongs to which cell ──────────────────────────────
    # The ordering assertions above are permutation-INSENSITIVE: an adversarial sweep of all
    # 120 permutations of the five committed columns found 4 that satisfy every ordering
    # (identity, boreal<->sahel, med<->amazon, and the 4-cycle of both), so a mis-paired
    # column would ship green. Pin each cell's own plant-available water and rooting depth
    # to the value its OWN soil produced (`extract_cell_soilcolumn.py`, gate-verified), which
    # no permutation can satisfy. Tolerances are the `%.4f`/`%.6f` print resolutions.
    # Sums of the PRINTED columns (not the extractor's unrounded internals), so the
    # tolerances are the accumulated print rounding: 3 x 5e-5 and 23 x 5e-5 for whcs
    # (`%.4f`), 3 x 5e-7 for the root fraction (`%.6f`).
    pins = Dict(   # name => (top-1m whcs mm, total whcs mm, top-1m root fraction)
        "boreal_siberia" => (167.5311, 3507.0329, 0.885829),
        "temperate_hainich" => (177.2791, 4010.7629, 0.878308),
        "mediterranean_iberia" => (155.5565, 3483.9645, 0.614679),
        "semiarid_sahel" => (117.1036, 2657.4898, 0.992989),
        "tropical_amazon" => (162.8281, 3492.5362, 0.532435),
    )
    for (nm, (top1, tot, rfrac)) in pins
        k = idx[nm]
        @test sum(whcs_all[k][1:3]) ≈ top1 atol = 2.0e-4
        @test sum(whcs_all[k]) ≈ tot atol = 2.0e-3
        @test sum(rd_all[k][1:3]) ≈ rfrac atol = 2.0e-6
    end
    # Hainich's plant-available water is unchanged from the committed column it was derived from
    _, whcs_ref, _ = readsoil(joinpath(refdir, "hainich_soilcolumn.txt"))
    @test whcs_all[idx["temperate_hainich"]] == whcs_ref

    # ── per-cell canopies: distinct individual sets, each with its own reconstructed light shares ──
    ninds = Int[]
    for (k, name) in enumerate(names)
        ind = readcsv(joinpath(refdir, "M_individuals_$(name)_2010.csv"))
        n = length(ind["type"])
        @test n > 0
        @test all(0.0 .≤ parse.(Float64, ind["fpar_leafon"]) .≤ 1.0)
        @test any(parse.(Int, ind["type"]) .≤ 6)                # at least one tree
        @test n == parse(Int, cells["n_ind"][k])                # the registry matches the file
        # The reconstruction is LEAF-ON while the C's FAPAR is phenology-weighted, so the ratio
        # to the C's own annual peak is systematically > 1 — Hainich's committed value is 1.60.
        # Assert the BAND: it is the only check that the canopy reconstruction still reproduces
        # the C at all (a factor-2 light bug keeps every per-individual value inside [0,1]).
        recon = parse(Float64, cells["fapar_recon"][k])
        cpeak = parse(Float64, cells["fapar_C_peak"][k])
        @test recon ≈ sum(parse.(Float64, ind["fpar_leafon"])) / 25 atol = 1.0e-4
        @test 1.15 < recon / cpeak < 1.85
        push!(ninds, n)
    end
    @test length(unique(ninds)) > 1                             # not one canopy copied five times
end

@testitem "Coupled emulator generalizes across biomes with PER-CELL inputs — energy closes + climate-driven partitioning" tags = [:validation, :energy, :coupling, :scientific, :multicell] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
    using LPJmLFITEmulator.Allometry
    using Test

    _mean(x) = sum(x) / length(x)
    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
        hdr = split(strip(lines[1]), ',')
        rows = [split(strip(l), ',') for l in lines[2:end]]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    fcol(d, k) = parse.(Float64, d[k])

    function readsoil(path)
        sd = Float64[]; whcs = Float64[]; rd = Float64[]
        for ln in eachline(path)
            s = strip(ln)
            (isempty(s) || startswith(s, "#")) && continue
            x = parse.(Float64, split(s))
            push!(sd, x[2]); push!(whcs, x[3]); push!(rd, x[4])
        end
        return hainich_soilcolumn(; whcs = whcs, rootdist = rd, soildepth = sd)
    end

    "Dominant patch (most living trees) of a reconstructed individual set → (pools, templates)."
    function readcanopy(path)
        ind = readcsv(path)
        v(k, r) = parse(Float64, ind[k][r])
        nt(r) = parse(Int, ind["type"][r])
        prows = Dict{Int, Vector{Int}}()
        for r in eachindex(ind["type"])
            (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
        end
        rows = prows[argmax(Dict(k => length(vv) for (k, vv) in prows))]
        pools = [
            TreePools{Float64}(
                    v("leaf_c", r), v("sapwood_c", r),
                    max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0), v("root_c", r),
                    v("height", r), v("crownarea", r), v("nind", r), v("sla", r), v("wooddens", r), false
                ) for r in rows
        ]
        tmpls = [
            Individual{Float64}(
                    v("fpar_leafon", r), 0.0, v("alphaa", r), v("albedo_leaf", r), v("emax", r),
                    v("sapwood_c", r), v("root_c", r), 0.0, 0.02, 0.04, 0.1, 0.4, v("nind", r),
                    PhotoParams{Float64}(; path = :c3, issla = true, sla = v("sla", r)),
                    TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false
                ) for r in rows
        ]
        return pools, tmpls
    end

    σ = 5.670374419e-8
    cells = readcsv(joinpath(refdir, "M_cells.csv"))
    names = String.(cells["name"]); lats = fcol(cells, "lat")

    ann = Dict{String, NamedTuple}()
    for (k, name) in enumerate(names)
        f = readcsv(joinpath(refdir, "biome_forcing_$(name).csv"))
        tairK = fcol(f, "temp") .+ 273.15
        swd = fcol(f, "swdown"); lwn = fcol(f, "lwnet"); prec = fcol(f, "precip")
        huss = fcol(f, "huss"); co2 = fcol(f, "co2")
        n = min(length(tairK), 2 * 365)                # 2 years for CI speed
        forcings = [
            AtmForcing(;
                    swdown = swd[i], lwdown = lwn[i] + σ * tairK[i]^4, tair = tairK[i], qair = huss[i],
                    wind = 2.0, psurf = 1.0e5, precip = prec[i], co2 = co2[i]
                ) for i in 1:n
        ]
        soil = readsoil(joinpath(refdir, "M_soilcolumn_$(name).txt"))
        pools, tmpls = readcanopy(joinpath(refdir, "M_individuals_$(name)_2010.csv"))
        core = FDiffFastCore(pools, tmpls, soil, lats[k])
        clo = SEBEnergyClosure(; t_soil0 = _mean(tairK))
        state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
        out = run_coupled_cell(core, clo, state, forcings; days_per_year = 365)

        # ── the Phase-4 hard gate holds in EVERY climate regime, now with per-cell vegetation ──
        @test maximum(abs, out.resid) < 1.0e-6
        @test all(isfinite, out.t_skin) && all(isfinite, out.le) && all(isfinite, out.h) && all(isfinite, out.g)
        # Latent heat is non-negative up to a small, BOUNDED smooth-surrogate undershoot. F's ET is built
        # from `smoothmin` (fdiff_smoothops.jl), and `smoothmin(a, b, β) ≤ min(a, b)` dips below the true
        # minimum by ≤ log(2)/β EVEN for a, b ≥ 0. In a fully water-depleted dry-season corner
        # (`available → 0`, `demand → 0`) `et = smoothmin(et_demand, available, βw)` bottoms out a few
        # hundredths of a mm/day below zero ⇒ `le ≈ −0.6 W/m²` where the physical ET is 0 (this model has
        # no dew/condensation term). It is bounded and harmless to E's closure (H := Rn − LE − G absorbs
        # it). Assert the BOUND, not exact non-negativity — a genuine sign bug would be orders larger.
        @test all(≥(-2.0), out.le)
        @test all(0.0 .≤ out.albedo .≤ 1.0)
        @test all(>(0.0), out.z0)
        @test maximum(abs, out.t_skin .- tairK[1:n]) < 30.0   # skin bounded near air across all climates

        ann[name] = (
            le = _mean(out.le), h = _mean(out.h), rn = _mean(out.rn),
            gpp = _mean(out.gpp),
            bowen = _mean(out.h) / max(_mean(out.le), 1.0e-6),
        )
    end

    # ── emergent climate-driven partitioning, now with each cell's own vegetation + soil ──
    @test ann["tropical_amazon"].le > ann["boreal_siberia"].le           # wet warm tropics evaporate far more
    @test ann["tropical_amazon"].le > ann["semiarid_sahel"].le           # water availability drives ET
    @test ann["tropical_amazon"].bowen < ann["temperate_hainich"].bowen  # tropics LE-dominated
    @test ann["semiarid_sahel"].bowen > ann["tropical_amazon"].bowen     # dry biome → sensible-heat dominated
    @test ann["mediterranean_iberia"].bowen > ann["tropical_amazon"].bowen
    @test ann["tropical_amazon"].rn > ann["boreal_siberia"].rn           # more net radiation in the tropics

    # ── PER-CELL OUTPUT SIGNATURES (M1 review debt #1, closed 2026-07-30) ────────────────────
    # Everything above is closure + finiteness + qualitative ORDERINGS, and it was MEASURED to
    # pass verbatim when all five cells revert to Hainich's soil + canopy. Item 1's pins catch a
    # swapped FIXTURE but not a DRIVER-level fallback — e.g. an edit hoisting `soil`/`pools` out
    # of the per-cell loop, or a per-cell artifact silently resolving to Hainich's. These pin each
    # cell's OWN mean LE and GPP, so the model must actually have consumed that cell's inputs.
    # Bands are ±2 % (LE) / ±3 % (GPP) around the measured 2-year values — far tighter than the
    # spread BETWEEN cells (LE 24.9…119.3), so a fallback to any other cell's inputs fails, while
    # staying loose enough not to fire on a benign last-digit change.
    sig = Dict(    # name => (mean LE W/m², mean GPP gC/m²/day)
        "boreal_siberia" => (24.9117, 1.34002),
        "temperate_hainich" => (41.3672, 3.66247),
        "mediterranean_iberia" => (49.2742, 5.38191),
        "semiarid_sahel" => (33.4942, 0.381906),
        "tropical_amazon" => (119.264, 7.56402),
    )
    for (nm, (le_x, gpp_x)) in sig
        @test isapprox(ann[nm].le, le_x; rtol = 0.02)
        @test isapprox(ann[nm].gpp, gpp_x; rtol = 0.03)
    end
    # ...and the signatures must be mutually distinguishable at those tolerances, which is what
    # makes the pins a fallback detector rather than five independent smoke checks.
    let les = [ann[nm].le for nm in names]
        @test all(
            abs(les[i] - les[j]) > 0.02 * max(les[i], les[j])
                for i in eachindex(les) for j in (i + 1):length(les)
        )
    end
end

# ── M2 — the FLUX-DRIVEN Component S wired into the MULTI-CELL coupled driver ────────────────────────
# Until now the 5-biome driver ran `slow=nothing` (F+E only), so the coupled evidence for S was
# single-cell (slow_production_drf_tests.jl, Hainich) while the global evidence was OFFLINE (line S).
# This closes that gap on the coupling side: every biome cell builds its OWN `FluxDrivenSlowEmulator`
# from its OWN `n_init`/`age0`/slow-boundary (`references/M_cells.csv`, extracted by
# scripts/extract_cell_slow_init.py from the PINNED artifact's cell_meta.parquet) plus its OWN
# per-cell `ClimBuf`, and the S↔F handoff must conserve carbon in EVERY climate.
#
# WHY THE COMMITTED DEMO FOREST AND NOT THE PINNED GLOBAL ONE: the pinned production pair
# (`drf_forest_global_pooled_w20_t8.{drf}` + `.rcop`, ~180 MB) lives on /p/tmp (DVC), and CI runs on
# GitHub runners with no cluster. Conservation, determinism and the transient-boundary mechanism are
# ARTIFACT-INDEPENDENT, so the committed Hainich demo forest exercises all of them; the pinned global
# pair drives the per-cell SCIENCE (demography vs C truth), which is M3 and cluster-only. What this
# gate therefore does NOT claim: that the counts are right away from Hainich. A DRF prediction is a
# convex combination of training leaf means, so it can never leave `[y_min, y_max]` however
# out-of-domain the input — which is why the band assertion below is a STRUCTURAL check, not evidence
# of skill (ADR 0032/S1c: that is what `feature_history` vs the meta's feat_min/feat_max is for).
#
# WHY A ClimBuf PER CELL AND NOT ONE BAKED BOUNDARY ROW: the boundary's two climate columns
# (`eco_diag_gdd_5`, `tas_cold_month`) are SCENARIO-coupled — measured 1513 GDD / 8.84 °C apart between
# the historic and ssp370 tables of one pooled artifact — so a single baked row is a single-climate
# snapshot. `ClimBuf` recomputes exactly those two axes each year from the temperature F consumed
# (ADR 0026/0027), leaving `soil_depth`/`co2` untouched.

@testitem "M2 — per-cell flux-driven S in the multi-cell coupled loop (conservation + determinism + transient boundary)" tags = [:conservation, :coupling, :energy, :multicell, :scientific] begin
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
    fcol(d, k) = parse.(Float64, d[k])
    function readsoil(path)
        sd = Float64[]; whcs = Float64[]; rd = Float64[]
        for ln in eachline(path)
            s = strip(ln)
            (isempty(s) || startswith(s, "#")) && continue
            x = parse.(Float64, split(s))
            push!(sd, x[2]); push!(whcs, x[3]); push!(rd, x[4])
        end
        return hainich_soilcolumn(; whcs = whcs, rootdist = rd, soildepth = sd)
    end
    function readcanopy(path)
        ind = readcsv(path)
        v(k, r) = parse(Float64, ind[k][r])
        nt(r) = parse(Int, ind["type"][r])
        prows = Dict{Int, Vector{Int}}()
        for r in eachindex(ind["type"])
            (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
        end
        rows = prows[argmax(Dict(k => length(vv) for (k, vv) in prows))]
        pools = [
            TreePools{Float64}(
                    v("leaf_c", r), v("sapwood_c", r),
                    max(v("agb", r) / v("nind", r) - v("leaf_c", r) - v("sapwood_c", r), 0.0), v("root_c", r),
                    v("height", r), v("crownarea", r), v("nind", r), v("sla", r), v("wooddens", r), false
                ) for r in rows
        ]
        tmpls = [
            Individual{Float64}(
                    v("fpar_leafon", r), 0.0, v("alphaa", r), v("albedo_leaf", r), v("emax", r),
                    v("sapwood_c", r), v("root_c", r), 0.0, 0.02, 0.04, 0.1, 0.4, v("nind", r),
                    PhotoParams{Float64}(; path = :c3, issla = true, sla = v("sla", r)),
                    TempStressParams{Float64}(; temp_photos_low = 20.0, temp_photos_high = 30.0), false
                ) for r in rows
        ]
        return pools, tmpls
    end

    σ = 5.670374419e-8
    cells = readcsv(joinpath(refdir, "M_cells.csv"))
    names = String.(cells["name"]); lats = fcol(cells, "lat")

    # ── the per-cell S seed + boundary columns must EXIST for every cell (M2 step 2) ──
    # The extractor's completeness gate refuses to emit a partial table, so a missing value here
    # means the fixture was hand-edited or regenerated from an artifact that lacks the cell.
    for col in ("n_init", "age0", "eco_diag_gdd_5", "tas_cold_month", "soil_depth", "co2")
        @test haskey(cells, col)
        @test all(s -> !isempty(strip(s)), cells[col])
    end
    n_inits = fcol(cells, "n_init"); age0s = fcol(cells, "age0")
    bnd_of(k) = Float64[
        fcol(cells, "eco_diag_gdd_5")[k], fcol(cells, "tas_cold_month")[k],
        fcol(cells, "soil_depth")[k], fcol(cells, "co2")[k],
    ]
    @test all(>(0.0), n_inits)
    @test all(>(0.0), age0s)          # a 0 age0 is the pre-ADR-0024 degenerate seed (train/inference shift)

    # ── the committed demo forest + its meta ──
    forest = DRF.load_forest(joinpath(refdir, "drf_forest_hainich.drf"))
    meta_bnd = Float64[]; meta_ninit = 0.0; meta_age0 = 0.0; y_min = -Inf; y_max = Inf
    for ln in eachline(joinpath(refdir, "drf_forest_hainich_meta.txt"))
        (isempty(strip(ln)) || startswith(strip(ln), "#")) && continue
        parts = split(ln, '\t')
        parts[1] == "boundary" && (meta_bnd = parse.(Float64, split(strip(parts[2]))))
        parts[1] == "n_init" && (meta_ninit = parse(Float64, strip(parts[2])))
        parts[1] == "age0" && (meta_age0 = parse(Float64, strip(parts[2])))
        parts[1] == "y_min" && (y_min = parse(Float64, strip(parts[2])))
        parts[1] == "y_max" && (y_max = parse(Float64, strip(parts[2])))
    end
    @test length(meta_bnd) + 11 == forest.nfeat

    # ── PROVENANCE: M_cells.csv's Hainich row reproduces the demo artifact's OWN baked meta EXACTLY.
    # Both are the same quantity from the same upstream (line S's cell_meta.parquet), so this proves
    # scripts/extract_cell_slow_init.py pulled the right columns in the right ORDER — an off-by-one in
    # the boundary tail (or a scenario/version mix-up) would still produce four plausible numbers.
    # It is an equality, not a tolerance: the extractor emits `repr` (%.17g) round-trippable Float64.
    kh = findfirst(==("temperate_hainich"), names)
    @test kh !== nothing
    @test bnd_of(kh) == meta_bnd
    @test n_inits[kh] == meta_ninit
    @test age0s[kh] == meta_age0

    # 4 years, not 2: `reconcile_demography!` FORCES ρ = 1 in its year-0 call (`s.year == 0`, seeding
    # the recursive AR state), so the first year-end is a deliberate no-op and the first real
    # demographic change lands at the SECOND year-end. A 2-year run therefore applies its only change
    # after the last simulated day, and S provably cannot move F's fluxes — the S→F feedback assertion
    # below fails for a reason that is a property of the test, not of the model. 4 years leaves two
    # post-change years for the feedback to show up in NPP.
    nyears = 4
    results = Dict{String, NamedTuple}()
    for (k, name) in enumerate(names)
        f = readcsv(joinpath(refdir, "biome_forcing_$(name).csv"))
        tairK = fcol(f, "temp") .+ 273.15
        swd = fcol(f, "swdown"); lwn = fcol(f, "lwnet"); prec = fcol(f, "precip")
        huss = fcol(f, "huss"); co2 = fcol(f, "co2")
        n = nyears * 365
        @test length(tairK) >= n
        forcings = [
            AtmForcing(;
                    swdown = swd[i], lwdown = lwn[i] + σ * tairK[i]^4, tair = tairK[i], qair = huss[i],
                    wind = 2.0, psurf = 1.0e5, precip = prec[i], co2 = co2[i]
                ) for i in 1:n
        ]
        soil = readsoil(joinpath(refdir, "M_soilcolumn_$(name).txt"))
        pools, tmpls = readcanopy(joinpath(refdir, "M_individuals_$(name)_2010.csv"))
        mkcore() = FDiffFastCore(deepcopy(pools), deepcopy(tmpls), soil, lats[k])
        mkclo() = SEBEnergyClosure(; t_soil0 = _mean(tairK))
        mkstate() = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
        bnd0 = bnd_of(k)

        # (a) FIXED-N REFERENCE: F alone cannot move tree N. This is the control the mechanism
        #     assertion below is measured against, and it is also the `slow=nothing` path staying
        #     available and finite in every climate (guardrail 4).
        core_none = mkcore()
        nind0 = [p.nind for p in core_none.pools]
        out_none = run_coupled_cell(core_none, mkclo(), mkstate(), forcings; slow = nothing, days_per_year = 365)
        @test [p.nind for p in core_none.pools] == nind0
        @test maximum(abs, out_none.resid) < 1.0e-6

        # (b) S IN THE LOOP, with this cell's own seed/boundary and its own ClimBuf
        core = mkcore()
        cscale = sum(FDiff.vegc_full_ind(p) * p.nind for p in core.pools)
        s = FluxDrivenSlowEmulator(core, forest; boundary = copy(bnd0), n_init = n_inits[k], age0 = age0s[k], seed = 1)
        @test all(a -> isapprox(a, age0s[k]), s.age)        # the per-cell age0 seed took (ADR 0024 §3)
        cb = ClimBuf()                                      # gdd5_idx=1, tcm_idx=2 = this tail's order
        out = run_coupled_cell(core, mkclo(), mkstate(), forcings; slow = s, climbuf = cb, days_per_year = 365)

        # ── THE M2 GATE ────────────────────────────────────────────────────────────────────────
        @test maximum(abs, s.resid_history) <= 1.0e-6 * cscale     # carbon at the S↔F handoff
        @test maximum(abs, s.resid_history) < 1.0e-6
        @test maximum(abs, out.resid) < 1.0e-6                     # energy closes with S driving
        @test all(isfinite, out.t_skin) && all(isfinite, out.le) && all(isfinite, out.npp)
        @test length(s.target_history) == nyears && all(isfinite, s.target_history)
        # STRUCTURAL, not skill: a DRF cannot predict outside its trained target range.
        @test all(t -> y_min - 1.0e-9 <= t <= y_max + 1.0e-9, s.target_history)

        # ── the ClimBuf actually drove the boundary, and ONLY its two climate axes ──
        @test s.boundary[3] == bnd0[3]        # soil_depth static
        @test s.boundary[4] == bnd0[4]        # co2 static (ADR 0004)
        @test isfinite(s.boundary[1]) && isfinite(s.boundary[2])
        @test s.boundary[1] >= 0.0            # gdd5 is a sum of non-negative monthly excesses

        results[name] = (
            n0 = s.total_n_history[1], nend = s.total_n_history[end],
            gdd5 = s.boundary[1], tcm = s.boundary[2], bnd0 = bnd0,
            npp_none = _mean(out_none.npp), npp_s = _mean(out.npp),
            tn = copy(s.total_n_history), tg = copy(s.target_history),
        )

        # (c) DETERMINISM under seed — same inputs, same trajectory
        core2 = mkcore()
        s2 = FluxDrivenSlowEmulator(
            core2, DRF.load_forest(joinpath(refdir, "drf_forest_hainich.drf"));
            boundary = copy(bnd0), n_init = n_inits[k], age0 = age0s[k], seed = 1
        )
        run_coupled_cell(core2, mkclo(), mkstate(), forcings; slow = s2, climbuf = ClimBuf(), days_per_year = 365)
        @test s.total_n_history == s2.total_n_history
        @test s.target_history == s2.target_history
    end

    # ── MECHANISM: S moved the demography somewhere (F alone provably could not, assertion (a)) ──
    @test any(r -> r.tn[end] != r.tn[1], values(results))
    @test any(r -> r.npp_s != r.npp_none, values(results))

    # ── the online boundary is genuinely PER CELL, not one climate copied five times ──
    @test length(unique(round.([r.gdd5 for r in values(results)]; digits = 3))) == length(names)
    # ...and it tracks climate in the right direction: the ClimBuf's recomputed gdd5 must order the
    # cells the same way their baked (C-derived) gdd5 does. This is the check that the buffer is fed
    # the cell's OWN forcing — a driver-level fallback to one cell's forcing collapses the ordering.
    gd_online = [results[nm].gdd5 for nm in names]
    gd_baked = [results[nm].bnd0[1] for nm in names]
    @test sortperm(gd_online) == sortperm(gd_baked)
    # the coldest cell must stay coldest, the hottest hottest (Sahel/Amazon vs boreal)
    @test results["semiarid_sahel"].gdd5 > results["boreal_siberia"].gdd5
    @test results["tropical_amazon"].tcm > results["boreal_siberia"].tcm
end

# ── M3 S-SIDE (ADR 0054) — the committed C-truth demography/trait oracle for the same five cells. ─────
# The per-cell SKILL measurement itself cannot run here: it needs the pinned `_t8` `.drf`/`.rcop` pair
# (~180 MB on /p/tmp, DVC not git) and CI has no cluster. `scripts/biome_slow_oracle_probe.jl` is that
# measurement. What CI CAN and must guard is the REFERENCE the probe scores against — the fixture's basis,
# which is where the F side's two verdict-flipping errors lived (all-PFT vs tree-only; modal patch vs the
# 25-patch ensemble). Every assertion below is a basis check, not a science threshold.
@testitem "M3 S-side oracle reference — the C-truth demography/trait fixture is on the stated basis" tags = [:validation, :multicell, :scientific] begin
    using Test

    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
        hdr = split(strip(lines[1]), ',')
        rows = [split(strip(l), ',') for l in lines[2:end]]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end
    cnt = readcsv(joinpath(refdir, "M_slow_oracle_counts.csv"))
    trt = readcsv(joinpath(refdir, "M_slow_oracle_traits.csv"))
    cells = readcsv(joinpath(refdir, "M_cells.csv"))

    # ── COVERAGE: 5 cells x 10 years x 2 seeds, no gaps. A silently short fixture would make every
    #    per-year score a mean over whatever years happened to survive. ──
    @test length(cnt["name"]) == 5 * 10 * 2
    @test Set(cnt["name"]) == Set(cells["name"])
    for nm in cells["name"], sd in ("1", "2")
        yrs = [
            parse(Int, cnt["year"][i]) for i in eachindex(cnt["name"])
                if cnt["name"][i] == nm && cnt["seed"][i] == sd
        ]
        @test sort(yrs) == collect(2010:2019)
    end

    # ── BASIS CHECK 2 (the one that flipped an F-side verdict): the reference is PER-PATCH. Assert the
    #    identity that makes it so — a per-cell TOTAL is `npatch` times the per-patch mean, and `npatch`
    #    is the C's 25. If a future regeneration silently emitted per-cell numbers under the per-patch
    #    column names, `n_mean` would jump ~25x and this equality is what catches it. ──
    for i in eachindex(cnt["name"])
        np = parse(Int, cnt["npatch"][i])
        @test np == 25
        @test parse(Float64, cnt["n_mean"][i]) * np ≈ parse(Float64, cnt["n_cell_total"][i]) rtol = 1.0e-9
        @test parse(Int, cnt["n_min"][i]) ≤ parse(Float64, cnt["n_mean"][i]) ≤ parse(Int, cnt["n_max"][i])
    end

    # ── BASIS CHECK 1 (tree-only): cross-validate the population against an INDEPENDENT extractor. The
    #    2010 per-cell total here must equal `M_cells.csv`'s `n_trees`, which `extract_cell_individuals.py`
    #    derived from the same `ind` table through a different code path. Two extractors, one population —
    #    this is the evidence that `Type <= 6` + `isdead == 0` + the writer's >5 m filter agree end to end.
    #    A regression to the pre-ADR-0031 `[1,2,3,4,5]` list would drop ~32 % of stems and break it. ──
    for k in eachindex(cells["name"])
        nm = cells["name"][k]
        i = findfirst(
            j -> cnt["name"][j] == nm && cnt["year"][j] == "2010" && cnt["seed"][j] == "1",
            eachindex(cnt["name"])
        )
        @test i !== nothing
        @test parse(Int, cnt["n_cell_total"][i]) == parse(Int, cells["n_trees"][k])
    end

    # ── TRAITS: 6 axes (4 production copula axes + 2 diagnostic), quantiles monotone, and the grass-row
    #    tell. Grass is emitted with every tree field ZEROED, so a `Type` filter regression shows up as a
    #    zero spike: a strictly positive q05 on Wooddens is the cheap, decisive guard. ──
    @test Set(trt["axis"]) == Set(["SLA", "Wooddens", "D95max", "minwscal", "Height", "agb"])
    @test length(trt["axis"]) == 5 * 10 * 2 * 6
    for i in eachindex(trt["axis"])
        q = [parse(Float64, trt[c][i]) for c in ("q05", "q25", "q50", "q75", "q95")]
        @test issorted(q)
        @test q[1] > 0.0                      # no zeroed grass row leaked into any axis
        @test parse(Int, trt["n_stems"][i]) > 0
    end
    # Height: the `ind` writer emits ONLY stems > height_min = 5 m (fwriteoutput_ind.c:84). That filter is
    # the count target's population, so its violation would silently redefine every number scored here.
    for i in eachindex(trt["axis"])
        trt["axis"][i] == "Height" || continue
        @test parse(Float64, trt["q05"][i]) ≥ 5.0
    end
end
