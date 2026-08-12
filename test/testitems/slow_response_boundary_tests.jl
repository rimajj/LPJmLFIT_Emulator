# The Phase-3A Stage-3 RESPONSE-arm fixture (ADR 0100) — `S_hainich_response_boundary.csv`.
#
# WHY THIS TEST EXISTS. The fixture is the ONLY committed part of the response arm's forcing: the daily
# `.clm`-derived forcing it summarises lives on `/p/tmp` (1.7 MB/scenario, sources 4-12 GB), so this file is
# what a later session checks a rebuild against. A committed fixture with no test rots silently — and this one
# carries the arm's whole climate contrast, so a wrong regeneration would move an ADR-quoted number with
# nothing failing. The gates below are the fixture's MEANING, not just its shape:
#
#   • it is usable as a `boundary_series` (ADR 0026) of the artifact's own boundary width, per scenario;
#   • its historic tail agrees with `climbuf_hainich_boundary_w20.csv`, the fixture ADR 0027's ClimBuf is
#     itself tested against — so the two cannot be regenerated apart without this failing;
#   • it carries the warming signal the arm depends on (ssp370 gdd5 and coldest-month mean both above
#     historic), so a scenario mix-up or a flat forcing cannot pass;
#   • ssp370 co2 is flat 409.63 (ADR 0004) — the tell for the wrong forcing file.

@testitem "Response-arm boundary fixture (ADR 0100): shape, ClimBuf agreement, and the warming signal" tags = [:scientific] begin
    using LPJmLFITEmulator
    using LPJmLFITEmulator.FDiff
    using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
    using LPJmLFITEmulator.DRF
    using Test

    refdir = joinpath(@__DIR__, "references")
    function readcsv(path)
        lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
        hdr = split(strip(lines[1]), ',')
        rows = [split(strip(l), ',') for l in lines[2:end]]
        return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
    end

    d = readcsv(joinpath(refdir, "S_hainich_response_boundary.csv"))
    for c in (
            "scenario", "year", "gdd5", "tas_cold_month", "co2", "temp_mean", "swdown_mean",
            "lwnet_mean", "precip_mean", "huss_mean",
        )
        @test haskey(d, c)
    end

    # ── (a) shape: two scenarios, contiguous years, MATCHED lengths (the arms difference at matched indices) ──
    scen = d["scenario"]
    yrs = parse.(Int, d["year"])
    ih = findall(==("historic"), scen)
    is = findall(==("ssp370"), scen)
    @test !isempty(ih) && !isempty(is)
    @test length(ih) == length(is)              # matched year indices — ADR 0100 §1
    @test length(ih) + length(is) == length(scen)
    for idx in (ih, is)
        @test yrs[idx] == collect(yrs[idx][1]:yrs[idx][end])   # contiguous, ascending
    end
    @test yrs[is][1] == yrs[ih][end] + 1        # the two windows abut: historic ends, ssp370 begins

    gdd_h = parse.(Float64, d["gdd5"][ih]); gdd_s = parse.(Float64, d["gdd5"][is])
    tcm_h = parse.(Float64, d["tas_cold_month"][ih]); tcm_s = parse.(Float64, d["tas_cold_month"][is])
    @test all(isfinite, gdd_h) && all(isfinite, gdd_s)
    @test all(isfinite, tcm_h) && all(isfinite, tcm_s)
    @test all(>(0), gdd_h) && all(>(0), gdd_s)

    # ── (b) CROSS-FIXTURE agreement with the ClimBuf boundary fixture over their shared years ───────────────
    #    Same cell, same trailing W=20, same Thom-1966 method; the only difference is the print precision of
    #    two float32s, so the tolerance is a print artefact and nothing else.
    cb = readcsv(joinpath(refdir, "climbuf_hainich_boundary_w20.csv"))
    cby = parse.(Int, cb["year"])
    shared = intersect(cby, yrs[ih])
    @test length(shared) >= 20                  # the ClimBuf fixture's whole 2000-2019 span
    for Y in shared
        j = findfirst(==(Y), cby)
        k = findfirst(==(Y), yrs[ih])
        @test parse(Float64, cb["gdd5"][j]) ≈ gdd_h[k] atol = 1.0e-3
        @test parse(Float64, cb["tas_cold_month"][j]) ≈ tcm_h[k] atol = 1.0e-5
    end

    # ── (c) THE WARMING SIGNAL the arm depends on — a scenario mix-up or a flat forcing must fail here ──────
    @test sum(gdd_s) / length(gdd_s) > sum(gdd_h) / length(gdd_h) + 200.0
    @test sum(tcm_s) / length(tcm_s) > sum(tcm_h) / length(tcm_h) + 1.0
    tmp_h = parse.(Float64, d["temp_mean"][ih]); tmp_s = parse.(Float64, d["temp_mean"][is])
    @test sum(tmp_s) / length(tmp_s) > sum(tmp_h) / length(tmp_h) + 1.0      # ≥1 K warmer, measured +2.45 K
    @test all(t -> -30.0 < t < 40.0, vcat(tmp_h, tmp_s))                     # °C, not K

    # ── (c2) NO TRUNCATED-WINDOW STEP at the start of either scenario (added 2026-08-12, ADR 0171) ──────────
    # THE DEFECT THIS CATCHES, and why it needs a shape test rather than a value test. The builder gives each
    # scenario a W-1 year monthly LEAD-IN so year 1's trailing window is a real climatology; the ssp370 side
    # was missing it, so its first years were averaged over 1, 2, 3 … years instead of 20. That made 19 of the
    # 81 conditioning years a different quantity from the one the DRF/copula were TRAINED on — up to +210 gdd5
    # (+10.7 %) and +1.94 °C. The builder now gates this directly against the global trailing-W table, but that
    # table lives on `/p/tmp` and CI cannot read it, so the committed fixture needs a self-contained tell.
    # A truncated first window shows up as a STEP: a 20-year climatology moves by ~10 gdd5/yr, while dropping
    # the 1-year window for a 2-year one moved 2020→2021 by 158. Measured ratios of the largest year-on-year
    # jump to the series' own median jump: **13.1 (gdd5) / 17.6 (tcm) before the fix, 4.0 / 5.8 after** — so 8
    # separates them with margin on both sides. The test is on ALL years, not just the first, because the same
    # step appears wherever a window starts short.
    for (nm, v) in (
            ("historic gdd5", gdd_h), ("historic tas_cold_month", tcm_h),
            ("ssp370 gdd5", gdd_s), ("ssp370 tas_cold_month", tcm_s),
        )
        @testset "$nm: no truncated-window step" begin
            jumps = abs.(diff(v))
            med = sort(jumps)[cld(length(jumps), 2)]
            @test med > 0                               # a constant series is not a transient boundary
            @test maximum(jumps) <= 8.0 * med           # no truncated-window step — see the block above
        end
    end

    # ── (d) ADR 0004: the ssp370 forcing co2 is FLAT 409.63 ────────────────────────────────────────────────
    @test all(≈(409.63), parse.(Float64, d["co2"][is]))
    @test parse(Float64, d["co2"][ih][1]) < parse(Float64, d["co2"][ih][end])   # historic co2 rises

    # ── (e) it is USABLE as a `boundary_series`: the two moving axes + the artifact's own static tail ───────
    meta = Dict{String, String}()
    for ln in eachline(joinpath(refdir, "drf_forest_hainich_meta.txt"))
        p = split(ln, '\t')
        (length(p) >= 2 && p[1] != "golden" && !startswith(strip(ln), "#")) && (meta[String(p[1])] = String(strip(p[2])))
    end
    bnd = parse.(Float64, split(strip(meta["boundary"])))
    series = [vcat([gdd_s[k], tcm_s[k]], bnd[3:end]) for k in eachindex(gdd_s)]
    @test all(r -> length(r) == length(bnd), series)
    forest = DRF.load_forest(joinpath(refdir, "drf_forest_hainich.drf"))
    sd = Float64[]; whcs = Float64[]; rdist = Float64[]
    for ln in eachline(joinpath(refdir, "hainich_soilcolumn.txt"))
        t = strip(ln)
        (isempty(t) || startswith(t, "#")) && continue
        x = parse.(Float64, split(t))
        push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
    end
    core = FDiffFastCore(
        [TreePools{Float64}(200.0, 4000.0, 8000.0, 300.0, 14.0, 6.0, 0.02, 0.02, 2.0e5, false)],
        [
            Individual{Float64}(
                0.5, 0.0, 0.5, 0.1, 5.0, 4000.0, 300.0, 0.0, 0.02, 0.04, 0.1, 0.4, 0.02,
                PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.02),
                TempStressParams{Float64}(), false
            ),
        ],
        hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd), 51.25; pft_ids = [3]
    )
    # ADR 0026's seeding rule, pinned in BOTH directions: an EXPLICIT `boundary` is kept as given (the series
    # only takes over once `reconcile_demography!` advances `s.year`), while an OMITTED one is seeded from the
    # series' first row. Getting these the wrong way round is the kind of silent year-0 offset that would put
    # the first simulated year on the wrong bioclimate.
    s = FluxDrivenSlowEmulator(
        core, forest; boundary = bnd, n_init = parse(Float64, meta["n_init"]), seed = 1,
        boundary_series = series
    )
    @test s.boundary == bnd
    @test length(s.boundary_series) == length(series)

    s0 = FluxDrivenSlowEmulator(
        FDiffFastCore(
            [TreePools{Float64}(200.0, 4000.0, 8000.0, 300.0, 14.0, 6.0, 0.02, 0.02, 2.0e5, false)],
            [
                Individual{Float64}(
                    0.5, 0.0, 0.5, 0.1, 5.0, 4000.0, 300.0, 0.0, 0.02, 0.04, 0.1, 0.4, 0.02,
                    PhotoParams{Float64}(; path = :c3, issla = true, sla = 0.02),
                    TempStressParams{Float64}(), false
                ),
            ],
            hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd), 51.25; pft_ids = [3]
        ),
        forest; n_init = parse(Float64, meta["n_init"]), seed = 1, boundary_series = series
    )
    @test s0.boundary == series[1]
    # and the series carries a real transient: its first and last rows differ on both moving axes
    @test series[1][1] != series[end][1] && series[1][2] != series[end][2]
    @test series[1][3:end] == bnd[3:end] && series[end][3:end] == bnd[3:end]   # static tail untouched
end
