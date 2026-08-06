#!/usr/bin/env julia
# ── ADR 0051 PROBE — is the coupled `water_stress` shift the C's leaf-on `wscal` definition? ─────────
#
# REFERENCE BASIS (residual-diagnosis §1). Two columns both named `water_stress`, both formed as
# `1 − wscal_mean`, on the SAME cell/years (Hainich, orderA 42490, seed1, 2000–2019):
#   * TRAINING  `build_slow_runtime_table.py:424,436` = `1 − mean_over_living_tree_stems(ind.wscal_mean)`,
#     where the C emits `wscal_mean = pft->wscal_mean/NDAYYEAR` (`fwriteoutput_ind.c:119`) and accumulates
#     `pft->wscal_mean += pft->wscal` EVERY day (`water_stressed.c:140`). Trained band, Hainich demo
#     artifact meta: `water_stress ∈ [0, 0.04315]`.
#   * RUNTIME   `fast.jl:372` = `1 − wscal_acc/nday`, `wscal` from `daily_step_canopy`.
#
# HYPOTHESIS (§2, falsifiable). The C's `pft->wscal` is NOT the realized supply/demand ratio; it is a
# POTENTIAL, phenology-INDEPENDENT index (`water_stressed.c:130-138`) that equals **1** on a no-demand day.
# F_diff instead used `min(1, Σsupply·fpc / Σdemand·fpc)`, whose numerator carries `phen` SQUARED, so every
# leaf-off day scores ~0 = maximal stress. Predictions:
#   P1  the DEFAULT daily `wscal` series at Hainich is ~0 on leaf-off days and high in the growing season;
#   P2  the leaf-off day fraction ≈ the reported annual `water_stress` (0.323–0.331);
#   P3  the C-faithful `wscal_leafon=true` annual `water_stress` lands INSIDE the trained [0, 0.04315].
# P3 is the decisive one: it is the number the count DRF is actually fed.
#
# Run (CLAUDE.md §2 — never the login node):
#   scripts/sbatch_julia.sh M-wscal --project=. scripts/wscal_leafon_probe.jl
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams, WaterParams, FDiffParams
using LPJmLFITEmulator.DRF
using Statistics, Printf

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const σ = 5.670374419e-8
const YEARS = 10
const T8_DRF = "/p/tmp/jamirp/emulator_global/drf_forest_global_pooled_w20_t8.drf"
const T8_META = "/p/tmp/jamirp/emulator_global/drf_forest_global_pooled_w20_t8_meta.txt"
const WS_IDX = 3            # `water_stress` position in `flux_feature_vector` (colnames verified below)

# ── readers (same layout as scripts/run_coupled_biomes.jl) ───────────────────────────────────────────
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

# CANOPY BASIS (ADR 0057 §4): the MODAL patch. Kept ON PURPOSE so this probe still REPRODUCES the numbers
# ADR 0051 published. Both arms run the same patch and differ only in `wscal_leafon`, so the comparison is
# member-invariant; only an absolute level would need the 25-patch ensemble mean.
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

function forcings_of(name)
    f = readcsv(joinpath(REFDIR, "biome_forcing_$(name).csv"))
    tairK = fcol(f, "temp") .+ 273.15
    swd = fcol(f, "swdown"); lwn = fcol(f, "lwnet"); prec = fcol(f, "precip")
    huss = fcol(f, "huss"); co2 = fcol(f, "co2")
    n = min(length(tairK), YEARS * 365)
    forc = [
        AtmForcing(;
                swdown = swd[i], lwdown = lwn[i] + σ * tairK[i]^4, tair = tairK[i], qair = huss[i],
                wind = 2.0, psurf = 1.0e5, precip = prec[i], co2 = co2[i]
            ) for i in 1:n
    ]
    return forc, tairK[1:n]
end

"Parse a `feat_min`/`feat_max`/`colnames` triple out of a DRF meta text file."
function readband(path)
    cn = String[]; lo = Float64[]; hi = Float64[]
    for ln in eachline(path)
        p = split(ln, '\t')
        length(p) < 2 && continue
        p[1] == "colnames" && (cn = String.(split(strip(p[2]))))
        p[1] == "feat_min" && (lo = parse.(Float64, split(strip(p[2]))))
        p[1] == "feat_max" && (hi = parse.(Float64, split(strip(p[2]))))
    end
    return cn, lo, hi
end

# Start from the ACTIVE calibrated parameter set (`tebs_params`, what FDiffFastCore defaults to) and flip
# ONLY `water.wscal_leafon` — building a bare `FDiffParams()` would silently swap every other constant.
function mkparams(leafon)
    p = FDiff.tebs_params(Float64)
    w = p.water
    fns = fieldnames(typeof(w))
    nt = NamedTuple{fns}(map(f -> getfield(w, f), fns))
    w2 = typeof(w)(; merge(nt, (; wscal_leafon = leafon))...)
    return FDiffParams{Float64}(p.photo, p.tstress, w2, p.resp, p.allom, p.nlambda, p.ω)
end

# ── PART 1 — the DAILY mechanism (P1/P2): replicate run_coupled_cell's day loop, record `fc.water_avail`
#    (= `fl.wscal`, set at fast.jl:210) after every real `couple_day!`. `slow=nothing` so demography is
#    held out and the two runs differ ONLY in the wscal definition. ────────────────────────────────────
function daily_wscal(name, lat, soil, pools, tmpls, forc, tairK, leafon)
    core = FDiffFastCore(pools, tmpls, soil, lat; params = mkparams(leafon))
    clo = SEBEnergyClosure(; t_soil0 = mean(tairK))
    state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    bc_f = LPJmLFITEmulator.stand_structure_tof(core)
    ws = Float64[]; gpp = Float64[]
    for (i, f) in enumerate(forc)
        (ftoe, _, _, _) = LPJmLFITEmulator.couple_day!(core, clo, state, bc_f, f; feedback = true)
        push!(ws, core.water_avail); push!(gpp, ftoe.gpp)
        i % 365 == 0 && LPJmLFITEmulator.annual_step!(core, state)
    end
    return ws, gpp
end

# ── PART 2 — the CONSEQUENCE (P3): the full coupled S+F+E run on the PINNED `_t8` forest, reading the
#    exact `water_stress` the count DRF was fed each year out of `s.feature_history`. ─────────────────
function coupled_ws(forest, lat, soil, pools, tmpls, forc, tairK, n_init, age0, bnd, leafon)
    core = FDiffFastCore(pools, tmpls, soil, lat; params = mkparams(leafon))
    clo = SEBEnergyClosure(; t_soil0 = mean(tairK))
    state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    s = FluxDrivenSlowEmulator(core, forest; boundary = copy(bnd), n_init = n_init, age0 = age0, seed = 1)
    out = run_coupled_cell(core, clo, state, forc; slow = s, climbuf = ClimBuf(), days_per_year = 365)
    ws = [row[WS_IDX] for row in s.feature_history]
    return ws, s, out
end

# ── setup ───────────────────────────────────────────────────────────────────────────────────────────
cells = readcsv(joinpath(REFDIR, "M_cells.csv"))
names = String.(cells["name"]); lats = fcol(cells, "lat")
n_inits = fcol(cells, "n_init"); age0s = fcol(cells, "age0")
bnds = [
    [
            parse(Float64, cells["eco_diag_gdd_5"][k]), parse(Float64, cells["tas_cold_month"][k]),
            parse(Float64, cells["soil_depth"][k]), parse(Float64, cells["co2"][k]),
        ] for k in eachindex(names)
]

hcn, hlo, hhi = readband(joinpath(REFDIR, "drf_forest_hainich_meta.txt"))
gcn, glo, ghi = readband(T8_META)
@assert hcn[WS_IDX] == "water_stress" "Hainich meta col $WS_IDX is $(hcn[WS_IDX]), not water_stress"
@assert gcn[WS_IDX] == "water_stress" "_t8 meta col $WS_IDX is $(gcn[WS_IDX]), not water_stress"
@printf(
    "trained band `water_stress`:  Hainich demo [%.5f, %.5f]   |   global _t8 [%.5f, %.5f]\n",
    hlo[WS_IDX], hhi[WS_IDX], glo[WS_IDX], ghi[WS_IDX]
)

# ── PART 1 output ───────────────────────────────────────────────────────────────────────────────────
@printf("\n=== PART 1 — DAILY `wscal` at Hainich, %d yr, slow=nothing (P1/P2) ===\n", YEARS)
@printf(
    "%-22s %8s %8s %8s %8s %9s %9s\n",
    "cell", "leafoff%", "ws_off", "ws_on", "ws_mean", "1-ws_mean", "band_hi"
)
for (k, name) in enumerate(names)
    forc, tairK = forcings_of(name)
    soil = readsoil(joinpath(REFDIR, "M_soilcolumn_$(name).txt"))
    pools, tmpls = readcanopy(joinpath(REFDIR, "M_individuals_$(name)_2010.csv"))
    for leafon in (false, true)
        ws, gpp = daily_wscal(name, lats[k], soil, pools, tmpls, forc, tairK, leafon)
        # "leaf-off" = a day the canopy assimilates essentially nothing (φ→0). Basis-free split.
        off = gpp .<= 0.05
        @printf(
            "%-22s %8.1f %8.4f %8.4f %8.4f %9.4f %9s  [%s]\n",
            name, 100 * count(off) / length(off),
            isempty(ws[off]) ? NaN : mean(ws[off]), isempty(ws[.!off]) ? NaN : mean(ws[.!off]),
            mean(ws), 1 - mean(ws), k == 2 ? @sprintf("%.5f", hhi[WS_IDX]) : "-",
            leafon ? "wscal_leafon=TRUE" : "default"
        )
    end
end

# ── PART 2 output ───────────────────────────────────────────────────────────────────────────────────
@printf("\n=== PART 2 — the `water_stress` the count DRF is FED, coupled S on pinned _t8 (P3) ===\n")
t0 = time(); forest = DRF.load_forest(T8_DRF)
@printf("loaded %s in %.1f s (%d trees, nfeat=%d)\n", basename(T8_DRF), time() - t0, length(forest.trees), forest.nfeat)
@printf(
    "%-22s %9s %9s %9s %9s %8s %8s  %s\n",
    "cell", "ws_min", "ws_mean", "ws_max", "exc_glob", "N_end", "dN%", "config"
)
for (k, name) in enumerate(names)
    forc, tairK = forcings_of(name)
    soil = readsoil(joinpath(REFDIR, "M_soilcolumn_$(name).txt"))
    pools, tmpls = readcanopy(joinpath(REFDIR, "M_individuals_$(name)_2010.csv"))
    nref = NaN
    for leafon in (false, true)
        ws, s, _ = coupled_ws(
            forest, lats[k], soil, pools, tmpls, forc, tairK,
            n_inits[k], age0s[k], bnds[k], leafon
        )
        # exceedance of the GLOBAL _t8 band, in band widths (0 ⇒ inside the trained range)
        w = ghi[WS_IDX] - glo[WS_IDX]
        exc = max(glo[WS_IDX] - minimum(ws), maximum(ws) - ghi[WS_IDX], 0.0) / w
        nend = Float64(s.n_prev)
        leafon || (nref = nend)
        @printf(
            "%-22s %9.4f %9.4f %9.4f %9.3f %8.0f %8.1f  %s\n",
            name, minimum(ws), mean(ws), maximum(ws), exc, nend,
            100 * (nend - nref) / max(nref, 1.0), leafon ? "wscal_leafon=TRUE" : "default"
        )
    end
end

@printf(
    "\nVERDICT KEY — P3 holds iff `wscal_leafon=TRUE` puts Hainich's mean inside [%.5f, %.5f];\n",
    hlo[WS_IDX], hhi[WS_IDX]
)
@printf("the dN%% column is the DEMOGRAPHIC consequence of the conditioning shift (why this gates M3).\n")
