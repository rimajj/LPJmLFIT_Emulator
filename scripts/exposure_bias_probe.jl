#!/usr/bin/env julia
# ── EXPOSURE BIAS — measured OFFLINE from the existing `_t8` tables, before buying any retrain ────────
#
# THE DEFECT (ADR 0102 defect (A), line S's #1 remaining item; ADR 0104 §4 named `semiarid_sahel` its
# sharpest test case). In the training table `n_prev` is the C's OWN previous `n_living`
# (`build_slow_runtime_table.py:572`) — never a prediction. A coupled rollout has no C to read, so it
# feeds the count DRF its own previous output. The model is therefore evaluated off the basis it was
# trained on, and any one-step bias is re-entered as an input and compounds.
#
# WHY THIS RUNS BEFORE A RETRAIN. A retrain (scheduled sampling, or dropping `n_prev` from the feature
# set) is an ADR-0023 BOTH-SIDES change with line M: new `.drf` + new `.rcop` + a re-pin. That is worth
# buying only if the compounded error is large, and "large" is decidable from the tables that already
# exist. The recursion is, to first order, a scalar AR(1) in the count error:
#
#       e_t  =  b  +  g · e_{t-1}          e = pred − truth
#
#   b = the ONE-STEP bias, measured with the model fed the TRUE `n_prev` (its trained basis) — §A
#   g = the AR GAIN ∂ pred / ∂ n_prev, a property of the fitted forest alone                  — §B
#
# and that fixes both the horizon behaviour and the ceiling without running anything coupled:
#
#       e_k  =  b · (1 − g^k)/(1 − g)          e_∞  =  b/(1 − g)     for g < 1
#
# So the decision this probe informs is not "is there a bias" (there is) but which of the two terms
# dominates. If |g| is small the bias does not compound and a retrain buys little; if g is near 1 the
# recursion is the defect and dropping `n_prev` (g ≡ 0) is the intervention, at the cost of whatever
# one-step skill that feature carries. §C prices exactly that trade.
#
# REFERENCE BASIS (`residual-diagnosis` §1), stated before any number:
#   * ROWS are (Cell, Patch, Year) of the C's OWN run — the per-patch basis the DRF was trained on and
#     the same basis `M_slow_oracle_counts.csv` reports (ADR 0053). Not per-cell totals.
#   * `preds_oos.f64` is the HONEST held-out-CELL K-fold prediction written by `scripts/eval_slow_drf.jl`
#     for THIS table's own forest. The deployed `pooled_w20_t8` forest saw these historic cells in
#     training, so its bias on them is IN-SAMPLE and is reported as such, beside the OOS one. Both are
#     given because they answer different questions and neither substitutes for the other.
#   * `g` is measured by a SECANT, not a derivative: a forest is piecewise constant, so an infinitesimal
#     perturbation returns 0 for almost every row and would report "no feedback" from a model that has
#     plenty. The step is a fixed fraction of the row's own `n_prev`, two-sided.
#
# Run (CLAUDE.md §2 — never the login node; reads a 2.7 GB X.f64):
#   TIME=01:00:00 PARTITION=priority QOS=priority scripts/sbatch_julia.sh S-expbias \
#       --project=. scripts/exposure_bias_probe.jl
using LPJmLFITEmulator
using LPJmLFITEmulator.DRF
using Statistics, Printf, Random

const ART = "/p/tmp/jamirp/emulator_global"
const TABLE = get(ENV, "TABLE", joinpath(ART, "slow_runtime_historic_t8"))
const DRF_PATH = get(ENV, "DRF_PATH", joinpath(ART, "drf_forest_global_pooled_w20_t8.drf"))
const NSUB = parse(Int, get(ENV, "NSUB", "400000"))     # rows for the gain secant
const STEPS = (0.05, 0.1, 0.25)                        # relative perturbations of n_prev
const I_NPREV = 11                                      # flux_feature_vector position, re-asserted below
const REFDIR = joinpath(@__DIR__, "..", "test", "testitems", "references")

function read_manifest(path)
    d = Dict{String, String}()
    for ln in eachline(path)
        (isempty(strip(ln)) || startswith(strip(ln), "#")) && continue
        parts = split(strip(ln), '\t')
        length(parts) >= 2 && (d[parts[1]] = join(parts[2:end], '\t'))
    end
    return d
end

man = read_manifest(joinpath(TABLE, "manifest.txt"))
n = parse(Int, man["n"]); p = parse(Int, man["p"])
colnames = split(man["colnames"])
@assert colnames[I_NPREV] == "n_prev" "column $(I_NPREV) is $(colnames[I_NPREV]), not n_prev"
@printf("table   %s\n  n=%d  p=%d  scenario=%s  ncells=%s\n", TABLE, n, p, man["scenario"], get(man, "ncells", "?"))

# X.f64 is ROW-major (n×p) on disk → read into a p×n column-major buffer and index [j, i].
t0 = time()
Xt = Array{Float64}(undef, p, n); read!(joinpath(TABLE, "X.f64"), Xt)
y = Vector{Float64}(undef, n); read!(joinpath(TABLE, "y.f64"), y)
cells = Vector{Int64}(undef, n); read!(joinpath(TABLE, "cells.i64"), cells)
@printf("read X/y/cells in %.1f s\n", time() - t0); flush(stdout)

oos_path = joinpath(TABLE, "preds_oos.f64")
have_oos = isfile(oos_path)
poos = have_oos ? (v = Vector{Float64}(undef, n); read!(oos_path, v); v) : Float64[]

t0 = time(); forest = DRF.load_forest(DRF_PATH)
@printf("loaded %s in %.1f s — %d trees, nfeat=%d\n", basename(DRF_PATH), time() - t0, length(forest.trees), forest.nfeat)
@assert forest.nfeat == p "forest nfeat=$(forest.nfeat) != table p=$p"
flush(stdout)

# ── the five coupled biome cells, so the offline number lands next to the coupled measurement ─────────
const BIOMES = [
    ("boreal_siberia", 52059), ("temperate_hainich", 42490), ("mediterranean_iberia", 33335),
    ("semiarid_sahel", 18371), ("tropical_amazon", 12045),
]

# ── §A — THE ONE-STEP BIAS `b`, model fed the TRUE `n_prev` ───────────────────────────────────────────
# Both an absolute (stems/patch/yr) and a relative (fraction of the truth) form, because the compounding
# above is linear in the ABSOLUTE error while "a 5 %/yr bias" is how it has been discussed. The median is
# printed beside the mean: n_living is right-skewed and a mean bias can be carried by a thin tail.
@printf("\n=== §A — ONE-STEP BIAS b (model fed the TRUE n_prev = its trained basis) ===\n")
sub = randperm(Random.MersenneTwister(20260806), n)[1:min(NSUB, n)]
Xs = Matrix{Float64}(undef, length(sub), p)
for (r, i) in enumerate(sub), j in 1:p
    Xs[r, j] = Xt[j, i]
end
ys = y[sub]
t0 = time(); pin = DRF.predict(forest, Xs)
@printf("predicted %d rows in %.1f s\n\n", length(sub), time() - t0); flush(stdout)
e_in = pin .- ys
@printf("%-30s %10s %10s %10s %10s\n", "basis", "mean b", "median", "mean rel", "RMSE")
@printf(
    "%-30s %10.4f %10.4f %9.2f%% %10.4f\n", "deployed forest, IN-SAMPLE",
    mean(e_in), median(e_in), 100 * mean(e_in ./ max.(ys, 1.0)), sqrt(mean(e_in .^ 2))
)
if have_oos
    e_oos = poos .- y
    @printf(
        "%-30s %10.4f %10.4f %9.2f%% %10.4f\n", "held-out-CELL OOS (this table)",
        mean(e_oos), median(e_oos), 100 * mean(e_oos ./ max.(y, 1.0)), sqrt(mean(e_oos .^ 2))
    )
end
@printf("\nb > 0 = the model over-predicts the next year's stem count on its OWN trained basis. This is the\n")
@printf("term a coupled rollout re-enters as an input; it is NOT visible in R^2, which is scale-free.\n")

# ── §B — THE AR GAIN `g` = ∂ pred / ∂ n_prev ──────────────────────────────────────────────────────────
# Two-sided secant at three step sizes. A forest is piecewise constant, so the step matters and reporting
# one step alone would be a tuning knob; three make the answer's robustness readable. Rows whose n_prev is
# at the table's floor (1.0) are kept — a coupled rollout visits them too.
@printf("\n=== §B — AR GAIN g = d(pred)/d(n_prev), two-sided secant, %d rows ===\n\n", length(sub))
@printf("%-10s %10s %10s %10s %10s %10s\n", "rel step", "mean g", "median g", "q05", "q95", "frac g>0")
gains = Dict{Float64, Vector{Float64}}()
for s in STEPS
    Xp = copy(Xs); Xm = copy(Xs)
    for r in 1:size(Xs, 1)
        d = s * Xs[r, I_NPREV]
        Xp[r, I_NPREV] = Xs[r, I_NPREV] + d
        Xm[r, I_NPREV] = max(Xs[r, I_NPREV] - d, 0.0)
    end
    pp = DRF.predict(forest, Xp); pm = DRF.predict(forest, Xm)
    g = Float64[]
    for r in 1:size(Xs, 1)
        den = Xp[r, I_NPREV] - Xm[r, I_NPREV]
        den > 0 && push!(g, (pp[r] - pm[r]) / den)
    end
    gains[s] = g
    sg = sort(g)
    @printf(
        "%-10.2f %10.4f %10.4f %10.4f %10.4f %9.1f%%\n", s, mean(g), median(g),
        sg[max(1, round(Int, 0.05 * length(sg)))], sg[min(length(sg), round(Int, 0.95 * length(sg)))],
        100 * count(>(0), g) / length(g)
    )
    flush(stdout)
end
@printf("\ng ~ 0 => the count model barely uses its own previous count and the bias does NOT compound.\n")
@printf("g ~ 1 => a one-step error is carried forward intact and the recursion is the defect.\n")
@printf("g > 1 => the recursion AMPLIFIES and there is no finite fixed point (the unstable case).\n")

# ── §C — WHAT THE RECURSION DOES WITH THOSE TWO NUMBERS ───────────────────────────────────────────────
# The arithmetic is deliberately trivial and stated in full, because its whole value is that it needs no
# coupled run: e_k = b(1-g^k)/(1-g). The 10-year row is the horizon `biome_slow_oracle_probe.jl` scores.
@printf("\n=== §C — the implied compounding, e_k = b·(1-g^k)/(1-g) ===\n\n")
gm = mean(gains[0.1])
b_in = mean(e_in)
@printf("using b = %.4f (in-sample one-step) and g = %.4f (10 %% secant)\n\n", b_in, gm)
@printf("%-8s %12s %12s\n", "k (yr)", "e_k", "e_k / b")
for k in (1, 2, 5, 10, 20)
    ek = abs(gm - 1) < 1.0e-9 ? b_in * k : b_in * (1 - gm^k) / (1 - gm)
    @printf("%-8d %12.4f %12.2f\n", k, ek, ek / b_in)
end
if gm < 1
    @printf("%-8s %12.4f %12.2f\n", "inf", b_in / (1 - gm), 1 / (1 - gm))
else
    @printf("%-8s %12s %12s\n", "inf", "divergent", "-")
end
@printf("\ne_k/b is the AMPLIFICATION the exposure bias buys over k years — 1.00 would mean the one-step\n")
@printf("bias never compounds at all and a retrain would buy only the one-step term.\n")

# ── §D — PER-CELL, for the five coupled biome cells ───────────────────────────────────────────────────
# The coupled probe's five cells, so this offline estimate can be read directly against the measured
# coupled over-density (`biome_slow_oracle_probe.jl` REPORT 8). Whole-cell rows, not the subsample.
@printf("\n=== §D — per-cell b, g and the implied 10-year excess, for the 5 coupled biome cells ===\n\n")
@printf("%-22s %8s %9s %9s %9s %9s %10s\n", "cell", "rows", "b", "b_rel", "g", "e_10", "e_10/mean_y")
for (nm, cid) in BIOMES
    idx = findall(==(cid), cells)
    if isempty(idx)
        @printf("%-22s %8s  (not in this table)\n", nm, "-")
        continue
    end
    Xc = Matrix{Float64}(undef, length(idx), p)
    for (r, i) in enumerate(idx), j in 1:p
        Xc[r, j] = Xt[j, i]
    end
    yc = y[idx]
    pc = DRF.predict(forest, Xc)
    bc = mean(pc .- yc)
    Xp = copy(Xc); Xm = copy(Xc)
    for r in 1:size(Xc, 1)
        d = 0.1 * Xc[r, I_NPREV]
        Xp[r, I_NPREV] = Xc[r, I_NPREV] + d
        Xm[r, I_NPREV] = max(Xc[r, I_NPREV] - d, 0.0)
    end
    pp = DRF.predict(forest, Xp); pm = DRF.predict(forest, Xm)
    gs = Float64[]
    for r in 1:size(Xc, 1)
        den = Xp[r, I_NPREV] - Xm[r, I_NPREV]
        den > 0 && push!(gs, (pp[r] - pm[r]) / den)
    end
    gc = isempty(gs) ? 0.0 : mean(gs)
    e10 = abs(gc - 1) < 1.0e-9 ? bc * 10 : bc * (1 - gc^10) / (1 - gc)
    @printf(
        "%-22s %8d %9.4f %8.2f%% %9.4f %9.3f %9.2f%%\n",
        nm, length(idx), bc, 100 * bc / mean(yc), gc, e10, 100 * e10 / mean(yc)
    )
    flush(stdout)
end
@printf("\ne_10/mean_y is the offline PREDICTION of the coupled 10-year count excess for that cell, from the\n")
@printf("table alone. Read it against REPORT 8's free-running density ratio: they are the same quantity by\n")
@printf("two routes, and a large disagreement means the AR(1) reduction is missing a term (the canopy\n")
@printf("feedback `density -> fpc -> target`, which this linearisation deliberately does not carry).\n")

@printf("\nDONE — §A is what a retrain on the one-step basis would fix; §B decides whether dropping `n_prev`\n")
@printf("is worth its cost; §C+§D are the size of the prize.\n")
flush(stdout)
