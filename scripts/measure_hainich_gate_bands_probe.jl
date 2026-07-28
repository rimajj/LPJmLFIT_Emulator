# Re-measure EVERY threshold the four committed-Hainich-fixture gates assert, in one run (milestone S1c,
# ADR 0032). Run this whenever `drf_forest_hainich.drf` / `recruit_copula_hainich.rcop` are regenerated:
# regenerating a golden artifact moves the drift alarms in slow_production_drf_tests.jl /
# slow_oracle_tests.jl / slow_oracle_traits_tests.jl, and those must be RE-MEASURED and documented, never
# widened silently (the residual-diagnosis discipline, CLAUDE.md guardrail 7).
#
# It reproduces the three coupled harnesses the testitems build (identical fixtures, cohort selection,
# forcing, seeds and year counts) and prints, for each, the quantity the corresponding @test bounds. It also
# does the two checks the tests structurally CANNOT do:
#
#   1. BASIS AGREEMENT between the two committed artifacts one emulator loads together. The count `.drf` and
#      the recruit `.rcop` share four conditioning columns (`live_flux_cond`); ADR 0032 is the defect where
#      they silently sat on different feature bases. Assert the `.rcop`'s fallback row lies inside the
#      `.drf`'s trained per-feature band and their boundary tails are equal.
#   2. RUNTIME-vs-TRAINED FEATURE BAND. A DRF prediction is a convex combination of training leaf means, so
#      it can never leave [y_min, y_max] however out-of-domain its input is — the "targets inside the
#      training band" assertion is therefore structurally blind to a conditioning shift, which is precisely
#      why the stale proxy basis survived every green gate for five days. The observable check is on the
#      INPUT side: compare `s.feature_history` (the exact rows the forest was fed) against the `feat_min`/
#      `feat_max` band in the artifact meta.
#
# Usage (SLURM — the guard blocks login-node probes, CLAUDE.md §2):
#   scripts/sbatch_julia.sh S-s1cbands --project=. scripts/measure_hainich_gate_bands_probe.jl
# ENV `DRF_ART`/`DRF_META` point it at a DIFFERENT count artifact than the committed one — that is how the
# BEFORE column of a before/after threshold table is measured (extract the old pair with `git show`, then
# re-run). A pre-S1c meta carries no `feat_min`/`feat_max`, which the report degrades gracefully around.
# Reads only committed fixtures; writes nothing. Hainich (cell 42490) only.

using LPJmLFITEmulator
using LPJmLFITEmulator.FDiff
using LPJmLFITEmulator.FDiff: PhotoParams, TempStressParams
using LPJmLFITEmulator.DRF

const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")
_mean(x) = sum(x) / length(x)

function readcsv(path)
    lines = [l for l in readlines(path) if !isempty(strip(l)) && !startswith(strip(l), "#")]
    hdr = split(strip(lines[1]), ',')
    rows = [split(strip(l), ',') for l in lines[2:end]]
    return Dict(String(hdr[j]) => [r[j] for r in rows] for j in eachindex(hdr))
end

# ── the shared Hainich harness, byte-for-byte the testitems' construction ──────────────────────────────
ind = readcsv(joinpath(REFDIR, "hainich_individuals_2010.csv"))
fcsv = readcsv(joinpath(REFDIR, "hainich_forcing_2010.csv"))
fc_(k) = parse.(Float64, fcsv[k])
v(k, r) = parse(Float64, ind[k][r])
nt(r) = parse(Int, ind["type"][r])
const NDAY = length(fc_("doy"))

sd = Float64[]; whcs = Float64[]; rdist = Float64[]
for ln in eachline(joinpath(REFDIR, "hainich_soilcolumn.txt"))
    s = strip(ln); (isempty(s) || startswith(s, "#")) && continue
    x = parse.(Float64, split(s)); push!(sd, x[2]); push!(whcs, x[3]); push!(rdist, x[4])
end
const SOIL = hainich_soilcolumn(; whcs = whcs, rootdist = rdist, soildepth = sd)

prows = Dict{Int, Vector{Int}}()
for r in eachindex(ind["type"])
    (nt(r) <= 6 && v("height", r) > 0) && push!(get!(prows, parse(Int, ind["patch"][r]), Int[]), r)
end
const ROWS = prows[argmax(Dict(k => length(vv) for (k, vv) in prows))]

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
const TAIR_K = fc_("temp") .+ 273.15
const σ = 5.670374419e-8
const YEAR_FORC = [
    AtmForcing(;
            swdown = fc_("swdown")[i], lwdown = fc_("lwnet")[i] + σ * TAIR_K[i]^4,
            tair = TAIR_K[i], qair = fc_("huss")[i], wind = 2.0, psurf = 1.0e5,
            precip = fc_("precip")[i], co2 = fc_("co2")[i]
        ) for i in 1:NDAY
]
mkcore() = FDiffFastCore([mkp(r) for r in ROWS], [mkt(r) for r in ROWS], SOIL, 51.25)
mkclo() = SEBEnergyClosure(; t_soil0 = _mean(TAIR_K))
mkstate() = SharedState(; w = fill(0.7, LPJmLFITEmulator.NSOILLAYER))

# ── the committed artifacts + their metas ─────────────────────────────────────────────────────────────
function read_meta(path)
    d = Dict{String, Any}()
    goldens = Vector{Tuple{String, Vector{String}}}()
    for ln in eachline(path)
        (isempty(strip(ln)) || startswith(strip(ln), "#")) && continue
        parts = split(ln, '\t')
        if parts[1] == "golden"
            push!(goldens, (String(strip(parts[2])), String.(split(strip(parts[3])))))
        elseif length(parts) >= 2
            d[String(parts[1])] = String(strip(parts[2]))
        end
    end
    d["_goldens"] = goldens
    return d
end
nums(s) = parse.(Float64, split(strip(s)))

const DRF_ART = get(ENV, "DRF_ART", joinpath(REFDIR, "drf_forest_hainich.drf"))
const DRF_META = get(ENV, "DRF_META", replace(DRF_ART, r"\.drf$" => "_meta.txt"))
drf_meta = read_meta(DRF_META)
rcop_meta = read_meta(joinpath(REFDIR, "recruit_copula_hainich_meta.txt"))
forest = DRF.load_forest(DRF_ART)
cop, af, xcop, ax_names, cond_cols = DRF.load_copula(joinpath(REFDIR, "recruit_copula_hainich.rcop"))

colnames = String.(split(strip(drf_meta["colnames"])))
boundary = nums(drf_meta["boundary"])
n_init = parse(Float64, drf_meta["n_init"])
age0 = parse(Float64, drf_meta["age0"])
has_band = haskey(drf_meta, "feat_min")
fmin = has_band ? nums(drf_meta["feat_min"]) : Float64[]
fmax = has_band ? nums(drf_meta["feat_max"]) : Float64[]
ymin = has_band ? parse(Float64, drf_meta["y_min"]) : NaN
ymax = has_band ? parse(Float64, drf_meta["y_max"]) : NaN

println("="^100)
println("S1c gate re-measurement — Hainich (cell 42490) committed demo artifacts")
println("="^100)
println("count artifact: ", DRF_ART)
println("forest: nfeat=$(forest.nfeat) ntrees=$(length(forest.trees))  n_init=$n_init  age0=$(round(age0, digits = 4))")
println("target band  y_min=$ymin  y_max=$ymax   (a DRF prediction is a convex combo of leaf means ⇒ it")
println("             can NEVER leave this band, whatever it is fed — see the header)")

# ── CHECK 1 — basis agreement between the .drf and the .rcop (the ADR-0032 defect) ────────────────────
function basis_agreement()
    println("\n", "-"^100)
    println("[1] BASIS AGREEMENT — the .rcop fallback row vs the .drf trained per-feature band")
    println("-"^100)
    if !has_band
        println("  (the count meta carries no feat_min/feat_max — a pre-S1c artifact; check unavailable)")
        return -1
    end
    xr = nums(rcop_meta["x"])
    ccols = String.(split(strip(rcop_meta["cond_cols"])))
    nbad = 0
    for (j, c) in enumerate(ccols)
        k = findfirst(==(c), colnames)
        if k === nothing
            println("  !! rcop cond col $c not in the .drf colnames"); nbad += 1; continue
        end
        lo, hi = fmin[k], fmax[k]
        inb = lo <= xr[j] <= hi
        inb || (nbad += 1)
        println(
            "  ", rpad(c, 16), " rcop x=", rpad(round(xr[j], sigdigits = 6), 12),
            " drf band=[", round(lo, sigdigits = 6), ", ", round(hi, sigdigits = 6), "]  ",
            inb ? "IN" : "**OUT OF BAND**"
        )
    end
    btail = xr[(end - length(boundary) + 1):end]
    println("  boundary tail equal: ", btail == boundary, "  (drf=", boundary, ")")
    println("  => shared-conditioning columns out of band: ", nbad, "  (0 ⇒ ONE basis; ADR 0032 closed)")
    return nbad
end
n_out = basis_agreement()

# ── the runtime-vs-trained-band reporter ──────────────────────────────────────────────────────────────
function report_feature_band(label, feats_hist)
    println("\n  RUNTIME feature band over $(length(feats_hist)) years vs the TRAINED band [$label]:")
    if !has_band
        println("  ", rpad("feature", 16), rpad("runtime min", 14), "runtime max")
        for j in eachindex(colnames)
            println(
                "  ", rpad(colnames[j], 16), rpad(round(minimum(f[j] for f in feats_hist), sigdigits = 6), 14),
                round(maximum(f[j] for f in feats_hist), sigdigits = 6)
            )
        end
        println("  (no trained band in this meta ⇒ no verdict; runtime rows shown for the before/after table)")
        return -1, NaN
    end
    println(
        "  ", rpad("feature", 16), rpad("runtime min", 14), rpad("runtime max", 14),
        rpad("trained min", 14), rpad("trained max", 14), "verdict"
    )
    worst = 0.0; nbad = 0; bad = String[]
    for j in eachindex(colnames)
        rmin = minimum(f[j] for f in feats_hist)
        rmax = maximum(f[j] for f in feats_hist)
        w = fmax[j] - fmin[j]
        # excursion in units of the trained band width (0 = inside; a degenerate band uses |value| scale)
        scale = w > 0 ? w : max(abs(fmin[j]), 1.0e-12)
        exc = max(fmin[j] - rmin, rmax - fmax[j], 0.0) / scale
        ok = exc <= 0.0
        ok || (nbad += 1; push!(bad, colnames[j]))
        worst = max(worst, exc)
        println(
            "  ", rpad(colnames[j], 16), rpad(round(rmin, sigdigits = 6), 14), rpad(round(rmax, sigdigits = 6), 14),
            rpad(round(fmin[j], sigdigits = 6), 14), rpad(round(fmax[j], sigdigits = 6), 14),
            ok ? "IN" : "OUT by $(round(exc, digits = 3))× band width"
        )
    end
    println(
        "  => $nbad of $(length(colnames)) columns out of band", isempty(bad) ? "" : " ($(join(bad, ", ")))",
        "; worst excursion $(round(worst, digits = 3))× band width"
    )
    return nbad, worst
end

# ── CHECK 2 — the slow_production_drf_tests.jl harness (12 years, no copula) ──────────────────────────
println("\n", "-"^100)
println("[2] slow_production_drf_tests.jl — 12-yr coupled decade, no copula")
println("-"^100)
core = mkcore()
cscale = sum(FDiff.vegc_full_ind(p) * p.nind for p in core.pools)
s12 = FluxDrivenSlowEmulator(core, forest; boundary = boundary, n_init = n_init, age0 = age0, seed = 1)
out12 = run_coupled_cell(core, mkclo(), mkstate(), repeat(YEAR_FORC, 12); slow = s12, days_per_year = NDAY)
println(
    "  target_history      min=", round(minimum(s12.target_history), digits = 4),
    " max=", round(maximum(s12.target_history), digits = 4),
    "   [asserted 0.5 ≤ t ≤ 40.0]"
)
println(
    "  max|resid|          ", maximum(abs, s12.resid_history), "   [asserted < 1e-6 and ≤ 1e-6·cscale=",
    round(1.0e-6 * cscale, sigdigits = 4), "]"
)
println("  max|energy resid|   ", maximum(abs, out12.resid), "   [asserted < 1e-6]")
println("  N moved             ", s12.total_n_history[1], " -> ", s12.total_n_history[end])
nbad12, worst12 = report_feature_band("12-yr", s12.feature_history)

# ── CHECK 3 — the slow_oracle_tests.jl harness (20 years, no copula) ──────────────────────────────────
println("\n", "-"^100)
println("[3] slow_oracle_tests.jl — 20-yr coupled run, Height distribution vs the C truth")
println("-"^100)
core20 = mkcore()
s20 = FluxDrivenSlowEmulator(core20, forest; boundary = boundary, n_init = n_init, age0 = age0, seed = 1)
run_coupled_cell(core20, mkclo(), mkstate(), repeat(YEAR_FORC, 20); slow = s20, days_per_year = NDAY)
const QS = (0.05, 0.25, 0.5, 0.75, 0.95)
tr = readcsv(joinpath(REFDIR, "hainich_slow_oracle_traits.csv"))
truth_q(axname) = begin
    ai = findfirst(==(axname), tr["axis"])
    [parse(Float64, tr[string("q", lpad(round(Int, q * 100), 2, '0'))][ai]) for q in QS]
end
hs = Float64[]; ws = Float64[]
for p in core20.pools
    (!p.is_grass && p.height >= 5.0) || continue
    push!(hs, p.height); push!(ws, p.nind)
end
ord = sortperm(hs); hs = hs[ord]; ws = ws[ord]; cw = cumsum(ws) ./ sum(ws)
coupled_h = [hs[findfirst(>=(q), cw)] for q in QS]
truth_h = truth_q("Height")
nqrmse_h = sqrt(sum((coupled_h .- truth_h) .^ 2) / length(QS)) / (truth_h[4] - truth_h[2])
cnt = readcsv(joinpath(REFDIR, "hainich_slow_oracle_counts.csv"))
truth_npatch = _mean(parse.(Float64, cnt["N_beech_per_patch_mean"]))
coupled_target = _mean(s20.target_history[(end - 4):end])
println("  coupled Height q  ", round.(coupled_h, digits = 3))
println("  C-truth Height q  ", round.(truth_h, digits = 3))
println("  nqrmse            ", round(nqrmse_h, digits = 4), "   [asserted ≤ 0.45]")
println("  median ratio      ", round(coupled_h[3] / truth_h[3], digits = 4), "   [asserted 0.6 … 1.6]")
println(
    "  count ratio       ", round(coupled_target / truth_npatch, digits = 4),
    "   [asserted 0.25 … 4.0]  (target=", round(coupled_target, digits = 3), " truth=", round(truth_npatch, digits = 3), ")"
)
nbad20, worst20 = report_feature_band("20-yr", s20.feature_history)

# ── CHECK 4 — the slow_oracle_traits_tests.jl harness (20 years, copula ON) ───────────────────────────
println("\n", "-"^100)
println("[4] slow_oracle_traits_tests.jl — 20-yr coupled run with the recruit copula ON")
println("-"^100)
rc = RecruitCopula{Float64}(cop, af, xcop, make_recruit_to_pools(ax_names), live_flux_cond)
corec = mkcore()
sc = FluxDrivenSlowEmulator(
    corec, forest; boundary = boundary, n_init = n_init, age0 = age0, seed = 1, recruit_copula = rc
)
run_coupled_cell(corec, mkclo(), mkstate(), repeat(YEAR_FORC, 20); slow = sc, days_per_year = NDAY)
println("  max|resid|        ", maximum(abs, sc.resid_history), "   [asserted < 1e-6]")
println("  cohorts           ", length(ROWS), " -> ", length(corec.pools), "   [asserted > ", length(ROWS), "]")

qd(vals) = (vv = sort(vals); [vv[clamp(round(Int, q * length(vv)), 1, length(vv))] for q in QS])
Ndraw = 4000
draws = [DRF.sample_copula!(DRF.Xoshiro256pp(sd_), cop, af, xcop) for sd_ in 1:Ndraw]
for (ai, axn, nqb, mrb) in ((1, "SLA", 0.22, (0.85, 1.15)), (2, "Wooddens", 0.12, (0.85, 1.15)))
    dq = qd([draws[k][ai] for k in 1:Ndraw]); tq = truth_q(axn)
    nq = sqrt(sum((dq .- tq) .^ 2) / length(QS)) / (tq[4] - tq[2])
    println(
        "  DIRECT draws ", rpad(axn, 9), " nqrmse=", rpad(round(nq, digits = 4), 8),
        "[≤ $nqb]   median ratio=", rpad(round(dq[3] / tq[3], digits = 4), 8), "[$(mrb[1]) … $(mrb[2])]"
    )
end
function community_q(getter)
    xs = Float64[]; wsv = Float64[]
    for p in corec.pools
        p.is_grass && continue
        push!(xs, getter(p)); push!(wsv, p.nind)
    end
    o = sortperm(xs); xs = xs[o]; wsv = wsv[o]; c = cumsum(wsv) ./ sum(wsv)
    return [xs[findfirst(>=(q), c)] for q in QS]
end
for (axn, getter) in (("SLA", p -> p.sla), ("Wooddens", p -> p.wooddens))
    cq = community_q(getter); tq = truth_q(axn)
    nq = sqrt(sum((cq .- tq) .^ 2) / length(QS)) / (tq[4] - tq[2])
    println(
        "  COUPLED community ", rpad(axn, 9), " nqrmse=", rpad(round(nq, digits = 4), 8),
        "[≤ 0.45]   median ratio=", rpad(round(cq[3] / tq[3], digits = 4), 8), "[0.7 … 1.4]"
    )
end
nbadc, worstc = report_feature_band("20-yr + copula", sc.feature_history)

println("\n", "="^100)
println("SUMMARY  out-of-band feature columns: 12-yr=$nbad12  20-yr=$nbad20  20-yr+copula=$nbadc")
println("         basis-agreement violations (.drf vs .rcop): $n_out")
println("="^100)
