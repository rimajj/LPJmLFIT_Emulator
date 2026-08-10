#!/usr/bin/env julia
# ── M3 F-SIDE — F_diff vs the C oracle for the 5 biome cells (carbon / water / structure) ─────────────
#
# REFERENCE BASIS (`residual-diagnosis` §1 — every quantity below is on a DELIBERATELY matched basis; the
# C side is built by `scripts/extract_biome_fdiff_oracle.py`, read here from the committed
# `M_fdiff_oracle_biomes.csv`. Read that script's docstring before changing anything here.)
#
#   GPP    — THE HEADLINE, and the only fully clean one. C side is `d_gpp - d_grass_gpp`, i.e. grass
#            removed EXACTLY via the custom per-PFT daily output (conf.h id 419), because F_diff's canopy
#            here is tree-only (`M_individuals_*_2010.csv` keeps `type <= 6`) and the C cell's grass carries
#            up to 42.4 % of GPP. Both sides gC/m²/day (`FToE.gpp`, `interface.jl:46`).
#   ET     — C side `d_transp + d_evap + d_interc`, which is exactly F's `et = transp + evap + interc`
#            (`fast.jl:234`). Recovered here from `FToE.le` (the only ET the seam exposes) by inverting
#            `le = et/86400·λ`. CONTAMINATED: the C's transpiration includes grass, F's does not. The
#            per-cell grass GPP share is the honest upper bound and is printed alongside.
#   FPC    — ⚠ CORRECTED 2026-08-06 (ADR 0060). F side = `stand_structure_tof().fpc` = Σ `ind.fpc`, capped
#            at 1 — the sum of individual CROWN COVERS (`src/allometry.jl::fpc` = `fpc_tree.c:28`). The C
#            emits TWO different FPCs and this probe originally scored the WRONG one:
#              `fpc_tree_crown` (= `a_fpc`, `annual_natural.c:209` `+= pft->fpc/npatch`) IS the same
#                              quantity as F's — score against THIS one. Primary column below.
#              `fpc_tree`       (= `a_fpc_stand`, `annual_natural.c:218,248`) sums per-PFT LEAF AREA and
#                              applies one Beer-Lambert saturation over the whole patch — the C's own
#                              comment is "effective FPC as if tree crowns where spread over the whole
#                              forest patch". A DIFFERENT functional form, 1.4-2.4x larger in these cells.
#            Both are printed so the substitution can never be silent again. ADR 0053 finding 4 ("F
#            under-predicts tree FPC in all five cells, 0.31-0.72x") was this artifact and is WITHDRAWN.
#   LAI    — reported LAST and flagged, because the basis is only partly matchable. F's `SToF.lai` is
#            Σ `lai_i·fpc_i` = the cover-weighted WITHIN-CROWN LAI, which is NOT a stand LAI; the stand
#            value needs the `1/(1-exp(-k·LAI))` crown-area factor (CLAUDE.md §3, and F already forms
#            exactly this as `plai_i` at `fast.jl:219`), so that reconstruction is applied here. The C's
#            `a_lai_stand` is nevertheless a single ALL-PFT band, so it still carries grass — bounded, again,
#            by the grass GPP share. Treat as indicative, never as a headline number.
#
# PATCH BASIS (the second artifact, and the one that flips a verdict — see `readcanopy_patches`). Every
# quantity is reported on the C's OWN basis, the **25-patch ensemble mean**: each patch is run independently
# and the outputs averaged. The MODAL patch that `run_coupled_biomes.jl` picks is 1.12–1.72× denser in FPC,
# which is the same magnitude as the biases measured here; PART 1's `mod/ens` column keeps that visible.
#
# LEVEL vs DRIFT (the third artifact). Under `slow = nothing` F's canopy is free-running and drifts −13.5 %
# to +64.5 % in FPC over the window, so a 10-yr-mean ratio mixes flux physics with structural drift. PART 5
# therefore scores F year k against the C year k and prints the whole series: a ratio walking monotonically
# away from 1 is DRIFT, a flat-but-offset ratio is a genuine flux-level bias. Read the shape, not the mean.
#
# CONFIG. `slow = nothing` — kernel isolation (`fdiff-validate`): demography is held at the C-derived 2010
# canopy so a GPP gap localizes to F's flux physics instead of compounding with S's counts. `wscal_leafon =
# true` — ADR 0051's C-faithful leaf-on index. It is now also the PACKAGE DEFAULT (ADR 0059, 2026-08-06),
# but it is still passed EXPLICITLY here so this probe's label stays true if a default moves again; every
# number below is a `wscal_leafon=true` number and must be reported as such.
#
# CARRY THESE ADR-0052 CAVEATS INTO ANY HEADLINE (they are physics limits, not tuning targets):
#   * `boreal_siberia` — F_diff has NO soil ice, so its root-zone water never collapses and every
#     water-stress-like term is unreliable there. Do not average it into a cross-cell mean.
#   * dry cells — F_diff's root-zone water runs too DRY (Sahel/mediterranean), so it OVER-stresses there.
#
# Run (CLAUDE.md §2 — never the login node):
#   scripts/sbatch_julia.sh M-oracle --project=. scripts/biome_fdiff_oracle_probe.jl
using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams, WaterParams, FDiffParams
using Statistics, Printf

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
const σ = 5.670374419e-8
const YEARS = 10
const Y0 = 2010                                                      # first year of the committed forcing
const MONTH_LEN = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]   # noleap 365

# ── readers (same layout as scripts/run_coupled_biomes.jl / wscal_leafon_probe.jl) ────────────────────
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

"""
Every patch's (pools, tmpls), plus the index of the MODAL patch (most stems) the other M drivers pick.

THE BASIS THIS FIXES. `run_coupled_biomes.jl` / `wscal_leafon_probe.jl` build ONE core from the modal
patch, but the C's `d_gpp`/`d_transp`/`a_fpc_stand` are **25-patch ensemble means**, and the modal patch is
systematically DENSER than that ensemble — measured on the committed fixtures: FPC 1.48× (boreal), 1.12×
(Hainich), 1.19× (mediterranean), **1.72×** (Sahel), 1.14× (Amazon). That is the same magnitude as the
flux biases being measured, so a modal-patch level comparison cannot separate F's physics from the patch
choice. Patches do not share light in the C either (`getfpar.c` is per-patch), so the correct emulator-side
ensemble is *run each patch independently, then average the outputs* — never one core holding 25 patches'
stems, which would make them compete for light inside a single canopy.
"""
function readcanopy_patches(path)
    ind = readcsv(path)
    v(k, r) = parse(Float64, ind[k][r])
    nt(r) = parse(Int, ind["type"][r])
    prows = Dict{Int, Vector{Int}}()
    for r in eachindex(ind["type"])
        (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
    end
    pkeys = sort(collect(keys(prows)))
    modal = argmax([length(prows[p]) for p in pkeys])
    return [build_patch(ind, prows[p]) for p in pkeys], modal
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

"The C-side monthly climatology, keyed `(name, month)`."
function read_oracle()
    d = readcsv(joinpath(REFDIR, "M_fdiff_oracle_biomes.csv"))
    o = Dict{Tuple{String, Int}, Dict{String, Float64}}()
    for r in eachindex(d["name"])
        k = (String(d["name"][r]), parse(Int, d["month"][r]))
        cols = (
            "gpp_tree", "gpp_grass", "gpp_total", "transp_total", "et_total",
            "fpc_tree", "fpc_tree_crown", "lai_stand_total",
        )
        o[k] = Dict(c => parse(Float64, d[c][r]) for c in cols)
    end
    return o
end

"The C-side ANNUAL series, keyed `(name, year)` — lets the level comparison be year-matched."
function read_annual()
    d = readcsv(joinpath(REFDIR, "M_fdiff_oracle_biomes_annual.csv"))
    o = Dict{Tuple{String, Int}, Dict{String, Float64}}()
    for r in eachindex(d["name"])
        k = (String(d["name"][r]), parse(Int, d["year"][r]))
        o[k] = Dict(
            c => parse(Float64, d[c][r])
                for c in ("gpp_tree", "et_total", "fpc_tree", "fpc_tree_crown", "lai_stand_total")
        )
    end
    return o
end

# Start from the ACTIVE calibrated set (`tebs_params`) and flip ONLY `water.wscal_leafon` — building a bare
# `FDiffParams()` would silently swap every other constant (the trap ADR 0051's probe documents).
function mkparams(leafon)
    p = FDiff.tebs_params(Float64)
    w = p.water
    fns = fieldnames(typeof(w))
    nt = NamedTuple{fns}(map(f -> getfield(w, f), fns))
    w2 = typeof(w)(; merge(nt, (; wscal_leafon = leafon))...)
    return FDiffParams{Float64}(p.photo, p.tstress, w2, p.resp, p.allom, p.nlambda, p.ω)
end

"Stand LAI on the C's basis: Σ lai_i·fpc_i/(1-exp(-k·lai_i))  (CLAUDE.md §3; = `fast.jl:219`'s `plai_i`)."
function stand_lai(fc)
    s = 0.0
    k = fc.allom.k_beer
    for ind in fc.inds
        ind.is_grass && continue
        l = Float64(ind.lai)
        l <= 0 && continue
        den = 1 - exp(-k * l)
        den > 1.0e-12 && (s += l * Float64(ind.fpc) / den)
    end
    return s
end

# ── the run: replicate run_coupled_cell's day loop, recording the daily flux pair + annual structure ──
function run_patch(lat, soil, pools, tmpls, forc, tairK)
    core = FDiffFastCore(pools, tmpls, soil, lat; params = mkparams(true))
    clo = SEBEnergyClosure(; t_soil0 = mean(tairK))
    state = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))
    bc_f = LPJmLFITEmulator.stand_structure_tof(core)
    # t=0 crown cover, BEFORE any daily physics or `annual_step!`. Without it the yr-1 column mixes the
    # canopy RECONSTRUCTION with one year of F's own growth, and those need different fixes (ADR 0060).
    fpc0 = bc_f.fpc
    gpp = Float64[]; et = Float64[]; fpc = Float64[]; lai = Float64[]
    ngrass = 0
    for (i, f) in enumerate(forc)
        (ftoe, _, _, _) = LPJmLFITEmulator.couple_day!(core, clo, state, bc_f, f; feedback = true)
        push!(gpp, ftoe.gpp)
        # invert `le = et/86400·λ` (fast.jl:236) — the seam exposes no ET field of its own
        push!(et, ftoe.le * 86400 / LPJmLFITEmulator.LAMBDA_VAPORIZATION)
        if i % 365 == 0
            LPJmLFITEmulator.annual_step!(core, state)
            bc_f = LPJmLFITEmulator.stand_structure_tof(core)
            push!(fpc, bc_f.fpc); push!(lai, stand_lai(core))
            ngrass = count(ind -> ind.is_grass, core.inds)
        end
    end
    return gpp, et, fpc, lai, ngrass, fpc0
end

"""
Run EVERY patch independently and average the outputs — the C's own output basis (patch-ensemble mean).
Returns the ensemble series plus the modal-patch series, so the artifact's size is visible in one table.
"""
function run_cell(lat, soil, patches, modal, forc, tairK)
    runs = [run_patch(lat, soil, p, t, forc, tairK) for (p, t) in patches]
    ens = (
        gpp = mean(getindex.(runs, 1)), et = mean(getindex.(runs, 2)),
        fpc = mean(getindex.(runs, 3)), lai = mean(getindex.(runs, 4)),
        ngrass = sum(getindex.(runs, 5)), npatch = length(runs),
        fpc0 = mean(getindex.(runs, 6)),
    )
    m = runs[modal]
    return ens, (; gpp = m[1], et = m[2], fpc = m[3], lai = m[4])
end

"Month index 0..11 of each day-of-year in a noleap 365 calendar."
const DOY_MONTH = vcat([fill(m, MONTH_LEN[m]) for m in 1:12]...)

"Monthly climatology of a daily series spanning whole 365-day years."
monthly(v) = [mean(v[[d for d in eachindex(v) if DOY_MONTH[mod(d - 1, 365) + 1] == m]]) for m in 1:12]

# ── setup ────────────────────────────────────────────────────────────────────────────────────────────
cells = readcsv(joinpath(REFDIR, "M_cells.csv"))
names = String.(cells["name"]); lats = fcol(cells, "lat")
oracle = read_oracle()
annual = read_annual()

@printf("=== M3 F-SIDE — F_diff vs the C oracle, 5 biome cells, %d yr, slow=nothing, ", YEARS)
@printf("wscal_leafon=TRUE ===\n")
@printf("(wscal_leafon is ALSO the package default since ADR 0059; passed explicitly so the label holds)\n")
@printf("(FPC is scored against the C's CROWN-cover output a_fpc, not a_fpc_stand — ADR 0060)\n\n")

# ── PART 1 — GPP, the clean headline ────────────────────────────────────────────────────────────────
@printf("--- PART 1: TREE GPP (gC/m2/day). C = d_gpp - d_grass_gpp, grass removed EXACTLY. CLEAN. ---\n")
@printf("    F_ens = the 25-patch ensemble mean = the C's OWN output basis. F_mod = the modal patch the\n")
@printf("    other M drivers use; `mod/ens` is the size of that basis artifact (see readcanopy_patches).\n")
@printf(
    "%-22s %8s %8s %8s %7s %8s %8s   %s\n",
    "cell", "F_ens", "C_tree", "bias", "ratio", "F_mod", "mod/ens", "monthly r"
)
res = Dict{String, Any}()
modres = Dict{String, Any}()
for (k, name) in enumerate(names)
    forc, tairK = forcings_of(name)
    soil = readsoil(joinpath(REFDIR, "M_soilcolumn_$(name).txt"))
    patches, modal = readcanopy_patches(joinpath(REFDIR, "M_individuals_$(name)_2010.csv"))
    ens, mod = run_cell(lats[k], soil, patches, modal, forc, tairK)
    res[name] = ens
    modres[name] = mod
    cg = [oracle[(name, m)]["gpp_tree"] for m in 1:12]
    @printf(
        "%-22s %8.3f %8.3f %+8.3f %7.2f %8.3f %8.2f   %6.3f\n",
        name, mean(ens.gpp), mean(cg), mean(ens.gpp) - mean(cg), mean(ens.gpp) / mean(cg),
        mean(mod.gpp), mean(mod.gpp) / mean(ens.gpp), cor(monthly(ens.gpp), cg)
    )
end

# ── PART 2 — ET (contaminated by the C's grass transpiration; bound printed) ─────────────────────────
@printf("\n--- PART 2: ET (mm/day). C = d_transp + d_evap + d_interc = F's transp+evap+interc. ---\n")
@printf("    CONTAMINATED: the C's transp includes grass, F's does not => expect F < C by ~the grass share.\n")
@printf(
    "%-22s %8s %8s %8s %7s %8s   %s\n",
    "cell", "F_ens", "C_ET", "bias", "ratio", "C_transp", "monthly r"
)
for name in names
    ce = [oracle[(name, m)]["et_total"] for m in 1:12]
    fe = res[name].et
    @printf(
        "%-22s %8.3f %8.3f %+8.3f %7.2f %8.3f   %6.3f\n",
        name, mean(fe), mean(ce), mean(fe) - mean(ce), mean(fe) / max(mean(ce), 1.0e-9),
        mean([oracle[(name, m)]["transp_total"] for m in 1:12]), cor(monthly(fe), ce)
    )
end
@printf("    `C_transp` is the transpiration-only part of C_ET, shown so the grass-contaminated fraction\n")
@printf("    of the comparison is visible: only that column carries grass, evap/interc do not.\n")

# ── PART 3 — structure: FPC on BOTH C bases, then stand LAI (flagged) ────────────────────────────────
# `C_crown` is the comparable one (ADR 0060): F's `fpc` is a sum of individual crown covers, which is the
# C's `a_fpc`. `C_BLstand` is `a_fpc_stand`, a leaf-area Beer-Lambert form — printed only so the size of
# the substitution stays visible; `ratio_BL` is the number ADR 0053 finding 4 was read off, and it is NOT
# an F-vs-C fidelity statement.
@printf("\n--- PART 3: STRUCTURE. FPC scored on the C's CROWN-COVER output (ADR 0060). LAI C side ALL-PFT. ---\n")
@printf(
    "%-22s %8s %8s %8s | %9s %9s %9s %7s | %7s %6s\n",
    "cell", "fpc_F", "C_crown", "ratio", "C_BLstand", "ratio_BL", "crown/BL", "lai_F", "lai_C*", "grass"
)
for name in names
    fp = res[name].fpc; la = res[name].lai
    cf = oracle[(name, 1)]["fpc_tree_crown"]
    cbl = oracle[(name, 1)]["fpc_tree"]
    cl = oracle[(name, 1)]["lai_stand_total"]
    @printf(
        "%-22s %8.3f %8.3f %8.2f | %9.3f %9.2f %9.2f %7.3f | %7.3f %6d\n",
        name, mean(fp), cf, mean(fp) / cf, cbl, mean(fp) / cbl, cf / cbl,
        mean(la), cl, res[name].ngrass
    )
end
@printf("    `ratio` (vs C_crown) is the FIDELITY number. `ratio_BL` compares against a DIFFERENT C\n")
@printf("    quantity and is shown only to size the ADR-0053 basis error; do not quote it as a miss.\n")
@printf("    * lai_C is a_lai_stand = ALL-PFT stand LAI (grass included, not splittable); lai_F is\n")
@printf("      tree-only on the C's stand basis (the 1/(1-exp(-k·LAI)) reconstruction). Indicative only.\n")
@printf("    `grass` = the count of is_grass individuals in F's core (0 ⇒ F is genuinely tree-only).\n")

# ── PART 4 — drift: is the comparison canopy still the C's 2010 one? ────────────────────────────────
@printf("\n--- PART 4: F-side canopy DRIFT over the %d yr (slow=nothing ⇒ F's own growth only) ---\n", YEARS)
@printf("    F's canopy drifts under slow=nothing, so a 10-yr-mean ratio mixes flux physics with drift.\n")
@printf("    Each F year is therefore scored against the C's SAME year (M_fdiff_oracle_biomes_annual.csv).\n")
#    `Cdrift%` is the C's OWN crown-FPC change over the same years, so F's drift is read against the
#    reference's drift rather than against zero — the C's canopy is not static either (ADR 0060).
@printf(
    "%-22s %8s %8s %7s %8s | %8s %8s %8s %8s\n",
    "cell", "fpc_y1", "fpc_y10", "drift%", "Cdrift%", "gpp_y1/C", "gpp_y10/C", "best_yr", "best"
)
for name in names
    fp = res[name].fpc
    fg = [mean(res[name].gpp[((y - 1) * 365 + 1):(y * 365)]) for y in 1:YEARS]
    cg = [annual[(name, Y0 + y - 1)]["gpp_tree"] for y in 1:YEARS]
    cf1 = annual[(name, Y0)]["fpc_tree_crown"]
    cf2 = annual[(name, Y0 + YEARS - 1)]["fpc_tree_crown"]
    rat = fg ./ cg
    bi = argmin(abs.(rat .- 1))
    @printf(
        "%-22s %8.3f %8.3f %+7.1f %+8.1f | %8.2f %8.2f %8d %8.2f\n",
        name, fp[1], fp[end], 100 * (fp[end] - fp[1]) / max(fp[1], 1.0e-9),
        100 * (cf2 - cf1) / max(cf1, 1.0e-9),
        rat[1], rat[end], Y0 + bi - 1, rat[bi]
    )
end
@printf("\nYEAR-MATCHED LEVEL VERDICT (the least-confounded one available): the yr-1 column, since F starts\n")
@printf("from the C's OWN reconstructed 2010 canopy and has drifted least. Later years drift away from it.\n")

@printf("\n--- PART 5: YEAR-MATCHED ratios, every year (F year k / C year k) ---\n")
yearcols(vals) = join([@sprintf("%7s", v) for v in vals])
@printf("%-22s%s\n", "cell", yearcols(Y0:(Y0 + YEARS - 1)))
for name in names
    fg = [mean(res[name].gpp[((y - 1) * 365 + 1):(y * 365)]) for y in 1:YEARS]
    rat = [@sprintf("%.2f", fg[y] / annual[(name, Y0 + y - 1)]["gpp_tree"]) for y in 1:YEARS]
    @printf("%-22s%s\n", name, yearcols(rat))
end
@printf("A ratio that walks monotonically away from 1 is DRIFT (a structural problem); one that is flat but\n")
@printf("offset is a genuine flux-level bias. The two need different fixes — read the row shape, not a mean.\n")

# ── PART 6 — the same year-matched treatment for FPC, on the CROWN basis (ADR 0060) ─────────────────
# This is the table ADR 0053 finding 4 should have been read off. yr-1 is the least-confounded column:
# F starts from the C's own reconstructed 2010 canopy, so a yr-1 ratio far from 1 is an INITIALISATION
# or allometry gap, while a row walking away from 1 is F's growth diverging from the C's.
@printf("\n--- PART 6: YEAR-MATCHED FPC ratios (F year k / C `a_fpc` crown cover year k) ---\n")
@printf("%-22s%7s%s%9s%9s\n", "cell", "t0", yearcols(Y0:(Y0 + YEARS - 1)), ">5m_frac", "t0/>5m")
for name in names
    fp = res[name].fpc
    rat = [@sprintf("%.2f", fp[y] / annual[(name, Y0 + y - 1)]["fpc_tree_crown"]) for y in 1:YEARS]
    # What fraction of the C's OWN 2010 crown cover is present in the >5 m population F is built from:
    # the `ind` writer drops stems below `height_min = 5 m` (CLAUDE.md §3), so F's stand is missing that
    # part by construction and its ratio is biased DOWN by exactly this factor.
    rows = readcsv(joinpath(REFDIR, "M_individuals_$(name)_2010.csv"))
    acc = Dict{String, Float64}()
    for i in eachindex(rows["patch"])
        parse(Int, rows["type"][i]) <= 6 || continue
        acc[rows["patch"][i]] = get(acc, rows["patch"][i], 0.0) + parse(Float64, rows["fpc_ind"][i])
    end
    frac = (sum(values(acc)) / length(acc)) / annual[(name, Y0)]["fpc_tree_crown"]
    # `t0` is F's crown cover BEFORE any physics, over the C's own 2010 a_fpc. Dividing it by `>5m_frac`
    # asks the only question the reconstruction can be held to: given the stems F was actually handed,
    # does F reproduce THEIR crown cover? 1.00 = yes. Anything else is allometry, not growth.
    t0 = res[name].fpc0 / annual[(name, Y0)]["fpc_tree_crown"]
    @printf("%-22s%7.2f%s%9.2f%9.2f\n", name, t0, yearcols(rat), frac, t0 / frac)
end
@printf("`>5m_frac` = (Σ fpc_ind over the committed 2010 individuals, patch mean) / the C's own a_fpc for\n")
@printf("that year. It is < 1 because the `ind` writer emits only stems above 5 m, so F's stand cannot\n")
@printf("contain the sub-5 m crown cover the C's output includes. Read every ratio against THIS, not 1.0.\n")
@printf("`t0/>5m` SEPARATES the two failure modes: it is F's canopy RECONSTRUCTION scored against the\n")
@printf("exact stems it was given (1.00 = faithful), with no growth in it. The walk from the 2010 column\n")
@printf("to 2019 is then F's GROWTH diverging from the C's. They need different fixes.\n")
