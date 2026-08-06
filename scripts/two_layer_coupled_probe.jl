#!/usr/bin/env julia
# ── ADR 0074's TWO-LAYER GROUND-HEAT COLUMN, IN THE COUPLED MULTI-CELL LOOP (line M, ADR 0058) ────────
#
# Line E measured `SEBParams.enable_two_layer` against 497 k PLUMBER2 tower steps and recommended line M
# enable it (ADR 0074). E's evidence is tower-side and stands. What only M can measure is what the scheme
# does INSIDE the coupled loop, and there are exactly two questions worth a job:
#
#   Q1  WHAT MOVES. The scheme changes G, and E's closure makes H the residual (`H := Rn − LE − G`), so H
#       must move. Does anything ELSE move — i.e. does the changed T_skin feed back through F into LE/GPP,
#       which is what would force a baseline regeneration?
#       PREDICTION (falsifiable, stated before the run): LE and GPP move by < 0.1 % — F's ET is water- or
#       demand-limited in all five climates and its T_skin sensitivity is weak — while H moves by O(1-10)
#       W/m². If LE/GPP move MORE than that, this is a coupled-physics change, not an H/G repartition, and
#       needs its own baseline regeneration.
#
#   Q2  DOES THE CLOSED COLUMN DRIFT. `step_soil_column!` has a CLOSED bottom (ADR 0074: "no deep restore"),
#       so the two layers integrate the net annual ground-heat flux with nothing pulling them back. Under a
#       CYCLIC forcing a physical soil column returns to its own initial state each year; a closed one only
#       does if the annual net G is exactly zero. Over the 60-100 yr rollouts this line gates
#       (`rollout_stability_tests.jl`, ADR 0055) a secular T2 drift would be a slow, silent bias in H.
#       PREDICTION: |dT2/dt| < 0.05 K/yr and decaying, i.e. the column equilibrates rather than running.
#       This is M's contribution to E's scheme — the tower experiment is 3 years long and cannot see it.
#
# Both arms are driven through the REAL `run_coupled_cell`; the only difference is `enable_two_layer`.
# Part 1 is on the 25-patch ENSEMBLE (ADR 0057); part 2 is single-member on purpose — a drift RATE is
# member-invariant and 60 yr × 25 patches × 2 arms buys nothing.
#
# Run (SLURM, per CLAUDE.md §2):
#   scripts/sbatch_julia.sh M-2layer --project=. scripts/two_layer_coupled_probe.jl
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
using LPJmLFITEmulator.Allometry
using Statistics, Printf

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const σ = 5.670374419e-8
const YEARS = 10           # part 1 horizon (the production driver's)
const NY_LONG = 60         # part 2 horizon (the rollout gate's)
const LONG_CELLS = ("boreal_siberia", "semiarid_sahel")   # the coldest and the hottest column

function readcsv(path)
    lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
    hdr = split(strip(lines[1]), ',')
    rows = [split(strip(l), ',') for l in lines[2:end]]
    return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
end
fcol(d, k) = parse.(Float64, d[k])

function readsoil(path)
    sd = Float64[]; whcs = Float64[]; rdist = Float64[]
    for ln in eachline(path)
        s = strip(ln)
        (isempty(s) || startswith(s, "#")) && continue
        x = parse.(Float64, split(s))
        push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
    end
    return hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)
end

function build_patch(ind, rows)
    v(k, r) = parse(Float64, ind[k][r])
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

function readcanopy_patches(path)
    ind = readcsv(path)
    v(k, r) = parse(Float64, ind[k][r])
    nt(r) = parse(Int, ind["type"][r])
    prows = Dict{Int, Vector{Int}}()
    for r in eachindex(ind["type"])
        (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    pk = sort(collect(keys(prows)))
    modal = argmax([length(prows[p]) for p in pk])
    return [build_patch(ind, prows[p]) for p in pk], modal
end

function forcings_of(name, nyear)
    f = readcsv(joinpath(REFDIR, "biome_forcing_$(name).csv"))
    tairK = fcol(f, "temp") .+ 273.15
    swd = fcol(f, "swdown"); lwn = fcol(f, "lwnet"); prec = fcol(f, "precip")
    huss = fcol(f, "huss"); co2 = fcol(f, "co2")
    n = min(length(tairK), nyear * 365)
    forc = [
        AtmForcing(;
                swdown = swd[i], lwdown = lwn[i] + σ * tairK[i]^4, tair = tairK[i], qair = huss[i],
                wind = 2.0, psurf = 1.0e5, precip = prec[i], co2 = co2[i]
            ) for i in 1:n
    ]
    return forc, tairK[1:n]
end

mkclo(t0, two) = SEBEnergyClosure(;
    t_soil0 = t0, params = SEBParams{Float64}(; enable_two_layer = two)
)

"One patch through the coupled loop; returns the flux means plus the closure's end soil state."
function run_patch(pools, tmpls, soil, lat, forc, tairK, two)
    core = FDiffFastCore(deepcopy(pools), deepcopy(tmpls), soil, lat)
    clo = mkclo(mean(tairK), two)
    state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    out = run_coupled_cell(core, clo, state, forc; days_per_year = 365)
    return (
        le = mean(out.le), h = mean(out.h), g = mean(out.g), rn = mean(out.rn),
        gpp = mean(out.gpp), tskin = mean(out.t_skin) - 273.15,
        res = maximum(abs, out.resid), t1 = clo.t_soil1 - 273.15, t2 = clo.t_soil2 - 273.15,
        gsd = std(out.g),
    )
end

cells = readcsv(joinpath(REFDIR, "M_cells.csv"))
names = String.(cells["name"]); lats = fcol(cells, "lat")

# ── PART 1 — Q1: what moves in the coupled loop, 25-patch ensemble, YEARS yr ─────────────────────────
@printf("=== PART 1 (Q1) — ADR 0074's two-layer column in the COUPLED loop, %d-patch ensemble, %d yr ===\n", 25, YEARS)
@printf("arms differ ONLY in SEBParams.enable_two_layer; slow=nothing; package-default params otherwise\n\n")
@printf(
    "%-22s %-6s %9s %9s %9s %9s %9s %9s %9s\n",
    "cell", "arm", "LE", "H", "G", "sd(G)", "Rn", "Tskin", "GPP"
)
res = Dict{Tuple{String, Bool}, NamedTuple}()
for (k, name) in enumerate(names)
    forc, tairK = forcings_of(name, YEARS)
    soil = readsoil(joinpath(REFDIR, "M_soilcolumn_$(name).txt"))
    patches, _ = readcanopy_patches(joinpath(REFDIR, "M_individuals_$(name)_2010.csv"))
    for two in (false, true)
        runs = [run_patch(p, t, soil, lats[k], forc, tairK, two) for (p, t) in patches]
        agg(f) = mean(f(r) for r in runs)
        e = (
            le = agg(r -> r.le), h = agg(r -> r.h), g = agg(r -> r.g), rn = agg(r -> r.rn),
            gsd = agg(r -> r.gsd), gpp = agg(r -> r.gpp), tskin = agg(r -> r.tskin),
            res = maximum(r.res for r in runs), t1 = agg(r -> r.t1), t2 = agg(r -> r.t2),
        )
        res[(name, two)] = e
        @printf(
            "%-22s %-6s %9.4f %9.4f %9.4f %9.4f %9.4f %9.4f %9.5f\n",
            name, two ? "2LAYER" : "def", e.le, e.h, e.g, e.gsd, e.rn, e.tskin, e.gpp
        )
    end
    flush(stdout)      # Julia block-buffers stdout to a file (CLAUDE.md §9)
end

@printf("\n--- Q1 VERDICT: relative change (2layer/def − 1), and the |ΔH| that pays for it ---\n")
@printf("%-22s %10s %10s %10s %10s %10s\n", "cell", "dLE/LE", "dGPP/GPP", "dH [W/m2]", "dG [W/m2]", "dTskin[K]")
for name in names
    a = res[(name, false)]; b = res[(name, true)]
    @printf(
        "%-22s %10.2e %10.2e %+10.3f %+10.3f %+10.4f\n",
        name, b.le / a.le - 1, b.gpp / a.gpp - 1, b.h - a.h, b.g - a.g, b.tskin - a.tskin
    )
end
@printf("PREDICTION was |dLE/LE|, |dGPP/GPP| < 1e-3 (an H/G repartition, not a coupled-physics change).\n")
@printf("max |energy residual| over every patch and arm = %.1e\n", maximum(r.res for r in values(res)))

# ── PART 2 — Q2: does the CLOSED column drift under a cyclic forcing? ────────────────────────────────
@printf("\n=== PART 2 (Q2) — %d-yr CYCLIC rollout, single member: does the closed column drift? ===\n", NY_LONG)
@printf("The committed forcing is one decade, so the rollout cycles it — a periodic forcing means any\n")
@printf("trend is the model's own. A physical column returns to its state each year; a CLOSED one only\n")
@printf("does if the annual net G is zero (ADR 0074: 'closed bottom — no deep restore').\n\n")
# ⚠ PHASE-MATCHED COMPARISONS ONLY. The forcing repeats with a `nyr_forc`-year period, so end-of-year
# values at different phases of that cycle differ by the SEASONal state, not by drift: boreal's raw
# `T1(y1) = −31.57` vs `T1(y60) = −25.73` is phase 1 vs phase 10 of the cycle, and a naive
# `(T2[end] − T2[end−9])/9` reported 0.222 K/yr for a column whose phase-matched series is flat to
# 1e-4 K/yr. Every trend below compares years `nyr_forc` apart, i.e. the SAME forcing year.
@printf(
    "%-22s %-6s %8s %8s %8s %8s %10s %10s %9s\n",
    "cell", "arm", "T1_c1", "T1_cend", "T2_c1", "T2_cend", "dT2/dt_all", "dT2/dt_tail", "AGBend/1"
)
for name in LONG_CELLS
    k = findfirst(==(name), names)
    forc, tairK = forcings_of(name, YEARS)
    nyr_forc = length(forc) ÷ 365
    soil = readsoil(joinpath(REFDIR, "M_soilcolumn_$(name).txt"))
    patches, modal = readcanopy_patches(joinpath(REFDIR, "M_individuals_$(name)_2010.csv"))
    pools, tmpls = patches[modal]
    for two in (false, true)
        core = FDiffFastCore(deepcopy(pools), deepcopy(tmpls), soil, lats[k])
        clo = mkclo(mean(tairK), two)
        st = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
        t1s = Float64[]; t2s = Float64[]; agb = Float64[]; resid = 0.0
        for y in 1:NY_LONG
            sy = mod1(y, nyr_forc)
            out = run_coupled_cell(
                core, clo, st, view(forc, ((sy - 1) * 365 + 1):(sy * 365)); days_per_year = 365
            )
            resid = max(resid, maximum(abs, out.resid))
            push!(t1s, clo.t_soil1 - 273.15); push!(t2s, clo.t_soil2 - 273.15)
            push!(
                agb, sum(
                    (Float64(p.leaf_c) + Float64(p.sapwood_c) + Float64(p.heartwood_c)) * Float64(p.nind)
                        for p in core.pools if !p.is_grass; init = 0.0
                )
            )
        end
        # PHASE-MATCHED: `cyc` holds one value per forcing cycle, all at the same phase (the cycle's last
        # year), so a difference between them is a trend and nothing else.
        cyc = collect(nyr_forc:nyr_forc:NY_LONG)
        rate_all = (t2s[cyc[end]] - t2s[cyc[1]]) / (cyc[end] - cyc[1])
        rate_tail = (t2s[cyc[end]] - t2s[cyc[end - 1]]) / (cyc[end] - cyc[end - 1])
        @printf(
            "%-22s %-6s %8.3f %8.3f %8.3f %8.3f %10.5f %10.5f %9.3f\n",
            name, two ? "2LAYER" : "def", t1s[cyc[1]], t1s[cyc[end]], t2s[cyc[1]], t2s[cyc[end]],
            rate_all, rate_tail, agb[end] / agb[1]
        )
        @printf("      max|energy resid| = %.1e   T2 phase-matched (yr %s): ", resid, join(cyc, ","))
        @printf("%s\n", join([@sprintf("%.4f", t2s[c]) for c in cyc], " "))
        @printf("      T1 phase-matched: %s\n", join([@sprintf("%.4f", t1s[c]) for c in cyc], " "))
        flush(stdout)
    end
end
@printf("\nPREDICTION was |dT2/dt| < 0.05 K/yr AND the tail rate well below the overall one (equilibration,\n")
@printf("not a runaway), on PHASE-MATCHED years. The `def` arm's T1/T2 are inert — printed as the control.\n")
