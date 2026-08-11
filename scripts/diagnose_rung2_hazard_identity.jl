#!/usr/bin/env julia
# THE θ=1 IDENTITY GATE for the rung-2 mortality interface (line M).
#
# WHY THIS EXISTS.  Line S returned option (c) for the rung-2 demography interface (ADR 0117): S hands
# back a per-individual survival factor `f_i = (1 − mort_i)^θ` keyed by the `(pft_id, treeidx)` pair of
# M's `pre` roster, and M draws the Bernoulli.  ADR 0049 item 2 records that **θ = 1 recovers FIT
# exactly**, so before any `C1 − C0` number is quoted, S's ported hazard — `src/trait_mortality.jl`,
# which has no call site anywhere and has therefore never been scored against the C on real per-tree
# state — must reproduce the C's own per-individual `mort_prob`.  S offered this gate as free; this
# script is it.  It needs no LPJmL run: the recorded rung-2 dump (ADR 0121, `MODE=record`) already
# carries the C's own four hazard components per tree per patch-year.
#
# WHAT IS AND IS NOT GATED.  The gate itself scores the ported hazard against the C's own per-tree
# `mort_*` columns and is basis-independent.  What the two rendezvous probes at the end measure is
# different: what the interface can compute AT THE MOMENT IT IS ASKED.  That used to be the `pre` dump
# phase, at the TOP of the annual demography block, while the C computes its own hazard later inside
# `annual_tree` → `mortality_tree_ind`, AFTER `turnover_tree` and `allocation_tree` — which split the
# four hazards in two:
#
#   * `mort_age`, `mort_water`, `mort_temp` — every input is present, unchanged, in the `pre` roster
#     (`water_stress`/`temp_stress` are byte-identical between the `pre` and `mort` phases in all
#     9 951 tree-patch-years of the baseline dump), so these three are gated EXACTLY here.
#   * `mort_npp` — needs `bm_delta = bm_inc.carbon/nind − turnover_ind.carbon` and
#     `leafarea_real = ind.leaf.carbon·sla`, both evaluated POST-allocation
#     (`mortality_tree_ind.c:66-67`).  Neither exists at the rendezvous, and neither is reconstructable
#     from the dumped columns: `turnover_tree` returns
#     `turn.leaf + turn.root + turn.sapwood + turn.sapwood_bg`, of which only the two sapwood terms are
#     recoverable (they equal Δheartwood between the `pre` and `mort` phases, verified exactly), while
#     `turn.leaf`/`turn.root` are daily-accumulated `tree->turn.*` fields and the `isphen` branch
#     (`turnover_tree.c:100-108`) is not dumped.  **That is why the dump schema gained the two
#     write-only columns `bm_delta`/`leafarea_real` (ADR 0122):** with them the fourth hazard, the whole
#     `mortality_hazard` total and both hard kills are gated exactly too, and the trait channel
#     `mort_max(wooddens)` — the entire reason arm C exists — is verified rather than bounded.  On a
#     pre-v4 dump the two columns are absent and this script falls back to the one-sided bound
#     `mort_npp/(1+counter) < mort_max(wooddens)` plus the implied-`greff` distribution, which is NOT
#     an identity; it says so in the output.
#
# `bm_inc_counter` is the third asymmetry: `mortality_tree_ind.c:71-81` UPDATES the counter from the sign
# of `bm_delta` and then uses the updated value, so the `pre` roster carries the PREVIOUS one (they differ
# in 2 171 of 9 951 records).  This script scores `mort_water` on BOTH bases — the `mort`-phase counter
# tests the ported FORMULA against the C, the `pre`-phase counter tests what the OLD rendezvous could
# achieve — because conflating them would hide a port error behind a basis error, or the reverse.
#
# THAT LAG IS NOW FIXED, AND BOTH PROBES ARE PRINTED SO THE FIX IS VISIBLE (ADR 0123).  Measured on the
# `pre` basis the counter lag INVERTS the sign of the one-year wood-density selection differential
# (ratio -0.825; the growth-efficiency lag alone is harmless at +1.001) — which is why arm C could not be
# scored on the trait question (ADR 0122 §4).  The rendezvous has since moved BEHIND the growth loop and
# publishes the new `grow` dump phase, on which the same probe returns Spearman ρ = 1.000 at every
# percentile and a differential ratio of +1.000: the interface now sees exactly what the C's own hazard
# saw.  A dump recorded before that move has no `grow` phase and the second probe says so.
#
# USAGE
#     julia --project=. scripts/diagnose_rung2_hazard_identity.jl [--dump DIR] [--csv PATH] [--tol 1e-13]
#                                                                 [--fixture PATH]
#
# `--fixture` writes the per-PFT-stratified committed CI fixture
# `test/testitems/references/M_rung2_hazard_identity.csv`, which
# `test/testitems/m_rung2_hazard_identity_tests.jl` re-scores on every CI run so the port cannot regress
# against C truth without a red gate.  Regenerate it only from a gated re-record.
#
# Exit 0 = every gated component identical within `--tol` (relative).  Exit 1 = a mismatch, i.e. a port
# error in `src/trait_mortality.jl` or a basis error here.  Exit 2 = the dump is unusable.

using Printf

const REPO = dirname(@__DIR__)
include(joinpath(REPO, "src", "trait_mortality.jl"))
using .TraitMortality

# ── argument parsing (no deps; ADR 0014 keeps the runtime [deps] empty) ───────────────────────────────
function parse_args(argv)
    opts = Dict{String, String}(
        "dump" => "/p/tmp/jamirp/M_rung2/M_rung2rec_v5_dump",
        "csv" => "",
        "tol" => "1e-13",
        "fixture" => "",
    )
    for a in argv
        m = match(r"^--([a-z_]+)=(.*)$", a)
        m === nothing && error("unrecognised argument '$a' (expected --key=value)")
        haskey(opts, m.captures[1]) || error("unknown option --$(m.captures[1])")
        opts[m.captures[1]] = m.captures[2]
    end
    return opts
end

# ── the dump reader.  Self-describing: the '#H T' line carries the column names, so nothing here
#    hard-codes the 49-field schema (the same rule scripts/rung2_replay_harness.py follows). ──────────
struct Roster
    cols::Dict{String, Int}
    rows::Vector{Vector{String}}
end

function read_dump(dir::AbstractString)
    files = sort(filter(f -> occursin(r"^roster_rank\d+\.txt$", f), readdir(dir)))
    isempty(files) && (@error "no roster_rank*.txt under $dir"; exit(2))
    cols = Dict{String, Int}()
    rows = Vector{Vector{String}}()
    for f in files
        for line in eachline(joinpath(dir, f))
            if startswith(line, "#H T ")
                names = split(line)[3:end]
                new = Dict(n => i for (i, n) in enumerate(names))
                if !isempty(cols) && new != cols
                    @error "the dump files disagree on the T-record schema"
                    exit(2)
                end
                cols = new
                continue
            end
            isempty(line) && continue
            line[1] == 'T' || continue
            isempty(cols) && (@error "$f: a T record before its '#H T' header"; exit(2))
            f2 = split(line)
            length(f2) == length(cols) + 1 ||
                (@error "$f: T record has $(length(f2) - 1) fields, header says $(length(cols))"; exit(2))
            push!(rows, f2[2:end])
        end
    end
    return Roster(cols, rows)
end

g(r::Roster, row, name) = row[r.cols[name]]
gf(r::Roster, row, name) = parse(Float64, g(r, row, name))
gi(r::Roster, row, name) = parse(Int, g(r, row, name))

# ── error bookkeeping ────────────────────────────────────────────────────────────────────────────────
mutable struct Acc
    n::Int
    nexc::Int
    maxabs::Float64
    maxrel::Float64
    worst::String
end
Acc() = Acc(0, 0, 0.0, 0.0, "")

function note!(a::Acc, got, want, tol, label)
    a.n += 1
    ae = abs(got - want)
    re = ae / max(abs(want), 1.0e-300)
    if ae > a.maxabs
        a.maxabs = ae
    end
    # an exact zero on both sides is a match; a zero truth with a nonzero prediction is an absolute miss
    exceeds = want == 0.0 ? ae > tol : re > tol
    if want != 0.0 && re > a.maxrel
        a.maxrel = re
        a.worst = label
    elseif want == 0.0 && ae > 0.0 && a.worst == ""
        a.worst = label
    end
    exceeds && (a.nexc += 1)
    return nothing
end

report(name, a::Acc) = @printf(
    "  %-22s n=%-6d exceed=%-6d max|Δ|=%.3e max relΔ=%.3e  %s\n",
    name, a.n, a.nexc, a.maxabs, a.maxrel, a.nexc > 0 ? "worst: " * a.worst : "OK"
)

# ── the rendezvous-basis probe.  NOT A GATE — it answers the question the gate above cannot: what can
#    line S's operator actually compute at the moment it is asked?  The rendezvous is the `pre` roster,
#    so the traits, the pre-increment age and both stress integrals are exact, but `bm_delta`,
#    `leafarea_real` and `bm_inc_counter` are the values LAST year's `mortality_tree_ind` left on the
#    tree.  Arm C's selection channel is therefore a ONE-YEAR-LAGGED hazard, and how much of the C's own
#    per-tree ordering that recovers is a measurement, not an assumption.
#
#    Two statistics, both chosen because they are what arm C is judged on:
#      * Spearman ρ within each patch-year between the lagged hazard and the C's own `mort_prob` — given
#        a count target ρ from the learned model, WHO dies is decided by the ordering alone.
#      * the one-year wood-density selection differential (ADR 0046 §3) under each hazard, as a ratio.
#        That is the axis ADR 0049's flip criterion is written on, so a ratio far from 1 bounds what a
#        `C1 − C0` difference can be credited with before the arm is ever run.
function spearman(x::Vector{Float64}, y::Vector{Float64})
    n = length(x)
    n < 3 && return NaN
    rank(v) = begin
        p = sortperm(v)
        rk = zeros(Float64, n)
        i = 1
        while i <= n
            j = i
            while j < n && v[p[j + 1]] == v[p[i]]
                j += 1
            end
            avg = (i + j) / 2
            for k in i:j
                rk[p[k]] = avg
            end
            i = j + 1
        end
        rk
    end
    rx, ry = rank(x), rank(y)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx .- mx) .* (ry .- my))
    den = sqrt(sum((rx .- mx) .^ 2) * sum((ry .- my) .^ 2))
    return den == 0 ? NaN : num / den
end

function rendezvous_probe(r::Roster, rdv, mrt, keys_common; lagged::Bool = true)
    # per patch-year: the C's hazard, the rendezvous hazard, nind and wooddens
    groups = Dict{Tuple{Int, Int}, NTuple{7, Vector{Float64}}}()
    n_no_prev = 0
    for k in keys_common
        (year, patch, pft_id, treeidx) = k
        prow, mrow = rdv[k], mrt[k]
        if lagged
            # the `pre` roster's bm_delta/leafarea/counter are last year's -> require the tree to have
            # been through mortality_tree_ind at least once, or the columns are uninitialised memory
            # (ADR 0120).
            prev = (year - 1, patch, pft_id, treeidx)
            if !haskey(mrt, prev)
                n_no_prev += 1
                continue
            end
        end
        p = pft_mort_params(pft_id)
        bmd = gf(r, prow, "bm_delta")
        larea = gf(r, prow, "leafarea_real")
        (isfinite(bmd) && isfinite(larea) && larea > 0) || (n_no_prev += 1; continue)
        # `pre` carries the PRE-increment age (annual_tree has not run); `grow` is dumped after it, so
        # its age is post-increment and the hazard's basis is age-1.  Getting this wrong is the ADR-0035
        # age off-by-one in a new place.
        age_rdv = gi(r, prow, "age") - (lagged ? 0 : 1)
        h = mortality_hazard(
            p; wooddens = gf(r, prow, "wooddens"), sla = gf(r, prow, "sla"),
            age = age_rdv, bm_delta = bmd, leafarea = larea,
            leaf_c = gf(r, prow, "leaf_c"), water_stress = gf(r, prow, "water_stress"),
            temp_stress = gf(r, prow, "temp_stress"), bm_inc_counter = gi(r, prow, "bm_inc_counter")
        )
        # ATTRIBUTION: which lagged term inverts the trait differential?  Two one-at-a-time variants,
        # both otherwise fed the C's own current-year values, so the difference is the lag alone.
        #   soft  — the lagged hazard with the two HARD kills suppressed (they carry weight 1, and the
        #           lagged counter/leaf_c reclassify some of them, which could dominate on its own)
        #   npplag— everything current EXCEPT bm_delta/leafarea, i.e. the greff lag in isolation
        h_soft = !lagged ? h.total : min(
                1.0,
                mort_npp(p, gf(r, prow, "wooddens"), bmd, larea; bm_inc_counter = gi(r, prow, "bm_inc_counter")) +
                mort_age(p, age_rdv) +
                mort_water(p, gf(r, prow, "water_stress"); bm_inc_counter = gi(r, prow, "bm_inc_counter")) +
                mort_temp(p, gf(r, prow, "temp_stress"))
            )
        h_npplag = !lagged ? h.total : mortality_hazard(
                p; wooddens = gf(r, mrow, "wooddens"), sla = gf(r, mrow, "sla"),
                age = age_rdv, bm_delta = bmd, leafarea = larea,
                leaf_c = gf(r, mrow, "leaf_c"), water_stress = gf(r, mrow, "water_stress"),
                temp_stress = gf(r, mrow, "temp_stress"), bm_inc_counter = gi(r, mrow, "bm_inc_counter")
            ).total
        #   ctrlag — everything CURRENT except bm_inc_counter, which is the one piece of per-tree state
        #            whose update rule (mortality_tree_ind.c:71-81) needs THIS year's growth SIGN
        h_ctrlag = !lagged ? h.total : mortality_hazard(
                p; wooddens = gf(r, mrow, "wooddens"), sla = gf(r, mrow, "sla"),
                age = age_rdv, bm_delta = gf(r, mrow, "bm_delta"),
                leafarea = gf(r, mrow, "leafarea_real"), leaf_c = gf(r, mrow, "leaf_c"),
                water_stress = gf(r, mrow, "water_stress"), temp_stress = gf(r, mrow, "temp_stress"),
                bm_inc_counter = gi(r, prow, "bm_inc_counter")
            ).total
        g = get!(groups, (year, patch), ntuple(_ -> Float64[], 7))
        push!(g[1], gf(r, mrow, "mort_prob"))
        push!(g[2], h.total)
        push!(g[3], gf(r, mrow, "nind"))
        push!(g[4], gf(r, mrow, "wooddens"))
        push!(g[5], h_soft)
        push!(g[6], h_npplag)
        push!(g[7], h_ctrlag)
    end
    rhos = Float64[]
    # hazard-weighted wooddens numerators/denominators for the four hazards, and the stand mean
    num = zeros(5)
    den = zeros(5)
    wbar_num = 0.0
    wbar_den = 0.0
    ntree = 0
    for (_, (mc, mr, nind, wd, msoft, mnpp, mctr)) in groups
        ρ = spearman(mc, mr)
        isfinite(ρ) && push!(rhos, ρ)
        ntree += length(mc)
        for i in eachindex(mc)
            for (j, m) in enumerate((mc[i], mr[i], msoft[i], mnpp[i], mctr[i]))
                num[j] += m * nind[i] * wd[i]
                den[j] += m * nind[i]
            end
            wbar_num += nind[i] * wd[i]
            wbar_den += nind[i]
        end
    end
    println()
    if lagged
        println("RENDEZVOUS-BASIS PROBE (`pre`, the OLD rendezvous) — NOT A GATE:")
        println("  exact at the rendezvous : traits, pre-increment age, water_stress, temp_stress")
        println("  ONE YEAR LAGGED         : bm_delta, leafarea_real, bm_inc_counter (last year's values)")
    else
        println("RENDEZVOUS-BASIS PROBE (`grow`, the LIVE rendezvous since ADR 0123) — NOT A GATE:")
        println("  the rendezvous is behind the growth loop, so every input is the current year's;")
        println("  a ratio of 1.000 below is the point of the move, not a coincidence.")
    end
    @printf("  records usable / skipped: %d / %d\n", ntree, n_no_prev)
    if !isempty(rhos)
        s = sort(rhos)
        q(f) = s[clamp(1 + round(Int, f * (length(s) - 1)), 1, length(s))]
        @printf("  Spearman ρ (rendezvous vs the C's own mort_prob), per patch-year over %d groups:\n", length(s))
        @printf("      p05 %.3f   median %.3f   p95 %.3f   min %.3f\n", q(0.05), q(0.5), q(0.95), s[1])
    end
    if wbar_den > 0 && all(den .> 0)
        wbar = wbar_num / wbar_den
        s = num ./ den .- wbar
        labels = lagged ?
            (
                "the C itself                    ",
                "lagged rendezvous (arm C as-was)",
                "  ... hard kills suppressed     ",
                "  ... ONLY bm_delta/leafarea lagged",
                "  ... ONLY bm_inc_counter lagged  ",
            ) :
            (
                "the C itself                    ",
                "the live rendezvous (arm C)     ",
                "", "", "",
            )
        @printf("  one-year wood-density selection differential (gC/m3, hazard-weighted minus stand mean;\n")
        @printf("  positive = denser wood dies more, i.e. ADR 0046's |live differential with sign flipped):\n")
        for j in 1:(lagged ? 5 : 2)
            @printf("      %s %+9.1f", labels[j], s[j])
            j > 1 && @printf("   ratio %+.3f%s", s[j] / s[1], sign(s[j]) == sign(s[1]) ? "" : "   ⚠ OPPOSITE SIGN")
            println()
        end
    end
    return nothing
end

# ── the committed CI fixture.  A PFT-stratified subsample of the C's own per-tree hazard, so
#    `test/testitems/m_rung2_hazard_identity_tests.jl` can re-score the port on every CI run without the
#    20 MB dump (which lives on /p/tmp and is not in git).  Deterministic: an every-k-th stride within
#    each PFT id, no RNG, so regenerating from the same gated dump reproduces the file byte-for-byte.
function write_fixture(path, r::Roster, pre, mrt, keys_common, per_pft::Int)
    bypft = Dict{Int, Vector{NTuple{4, Int}}}()
    for k in keys_common
        push!(get!(bypft, k[3], NTuple{4, Int}[]), k)
    end
    chosen = NTuple{4, Int}[]
    for id in sort(collect(keys(bypft)))
        ks = bypft[id]
        stride = max(1, cld(length(ks), per_pft))
        append!(chosen, ks[1:stride:end])
    end
    sort!(chosen)
    open(path, "w") do fh
        println(fh, "# C-truth fixture for the rung-2 theta=1 mortality identity gate (line M, ADR 0122).")
        println(fh, "# Source: the LPJmL-FIT C binary's own mortality_tree_ind, cell 42490, 25 patches,")
        println(fh, "# 2000-2019, recorded through the rung-2 observation hook (MODE=record, v4 schema).")
        println(fh, "# Regenerate ONLY from a rebuild-gated re-record:")
        println(fh, "#   julia --project=. scripts/diagnose_rung2_hazard_identity.jl --dump <dir> --fixture <this file>")
        println(fh, "# Columns 1-11 are the inputs mortality_tree_ind used; 12-16 are its own answers.")
        println(
            fh,
            "year,patch,pft_id,treeidx,age_pre,wooddens,sla,bm_delta,leafarea_real,leaf_c," *
                "water_stress,temp_stress,bm_inc_counter,c_mort_npp,c_mort_age,c_mort_water,c_mort_temp,c_mort_prob"
        )
        for k in chosen
            prow, mrow = pre[k], mrt[k]
            @printf(
                fh, "%d,%d,%d,%d,%d,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%d,%.17g,%.17g,%.17g,%.17g,%.17g\n",
                k[1], k[2], k[3], k[4], gi(r, prow, "age"), gf(r, prow, "wooddens"), gf(r, prow, "sla"),
                gf(r, mrow, "bm_delta"), gf(r, mrow, "leafarea_real"), gf(r, mrow, "leaf_c"),
                gf(r, prow, "water_stress"), gf(r, prow, "temp_stress"), gi(r, mrow, "bm_inc_counter"),
                gf(r, mrow, "mort_npp"), gf(r, mrow, "mort_age"), gf(r, mrow, "mort_water"),
                gf(r, mrow, "mort_temp"), gf(r, mrow, "mort_prob")
            )
        end
    end
    @printf("  fixture written: %s  (%d records over %d PFT ids)\n", path, length(chosen), length(bypft))
    return nothing
end

function main(argv)
    opts = parse_args(argv)
    tol = parse(Float64, opts["tol"])
    dump = opts["dump"]
    println("rung-2 θ=1 mortality identity gate")
    println("  dump      : ", dump)
    println("  operator  : src/trait_mortality.jl (line S, ADR 0047→0049), θ = 1")
    println("  tolerance : ", tol, " relative")
    println()

    r = read_dump(dump)
    # key = (year, patch, pft_id, treeidx); phase-split
    pre = Dict{NTuple{4, Int}, Vector{String}}()
    grw = Dict{NTuple{4, Int}, Vector{String}}()
    mrt = Dict{NTuple{4, Int}, Vector{String}}()
    for row in r.rows
        k = (gi(r, row, "year"), gi(r, row, "patch"), gi(r, row, "pft_id"), gi(r, row, "treeidx"))
        ph = g(r, row, "phase")
        ph == "pre" && (pre[k] = row)
        ph == "grow" && (grw[k] = row)
        ph == "mort" && (mrt[k] = row)
    end
    keys_common = sort(collect(intersect(keys(pre), keys(mrt))))
    @printf("  %d `pre` records, %d `mort` records, %d matched\n\n", length(pre), length(mrt), length(keys_common))
    isempty(keys_common) && (@error "no matched pre/mort tree records — is this a v3+ dump?"; exit(2))

    # v4 dumps (ADR 0122) publish the two post-allocation inputs of mort_npp; earlier ones do not.
    has_bm = haskey(r.cols, "bm_delta") && haskey(r.cols, "leafarea_real")
    println(
        "  schema    : ", has_bm ? "v4+ (bm_delta/leafarea_real present — mort_npp GATED)" :
            "pre-v4 (mort_npp bounded only)"
    )
    println()

    a_age = Acc()
    a_wat_m = Acc()
    a_wat_p = Acc()
    a_tmp = Acc()
    a_sum = Acc()
    a_npp = Acc()
    a_tot = Acc()
    a_larea = Acc()
    # mort_npp: one-sided bound + implied greff (the pre-v4 fallback)
    n_npp = 0
    n_npp_cap = 0
    n_bound_viol = 0
    greffs = Float64[]
    n_counter_shift = 0
    n_hard = Dict{Symbol, Int}(:none => 0, :bm_inc_counter => 0, :ghost_tree => 0)
    ids = Dict{Int, Int}()
    csv = isempty(opts["csv"]) ? nothing : open(opts["csv"], "w")
    csv !== nothing && println(
        csv,
        "year,patch,pft_id,treeidx,age_pre,wooddens,sla,water_stress,temp_stress," *
            "counter_pre,counter_mort,c_mort_npp,c_mort_age,c_mort_water,c_mort_temp,c_mort_prob," *
            "s_mort_age,s_mort_water_mort,s_mort_water_pre,s_mort_temp,s_mort_max,greff_implied," *
            "s_mort_npp,s_mort_total,s_hard_kill"
    )

    for k in keys_common
        (year, patch, pft_id, treeidx) = k
        prow, mrow = pre[k], mrt[k]
        ids[pft_id] = get(ids, pft_id, 0) + 1
        p = pft_mort_params(pft_id)

        age_pre = gi(r, prow, "age")                 # PRE-increment age: what mort_age was computed from
        wooddens = gf(r, prow, "wooddens")
        sla = gf(r, prow, "sla")
        ws = gf(r, prow, "water_stress")
        ts = gf(r, prow, "temp_stress")
        c_pre = gi(r, prow, "bm_inc_counter")
        c_mort = gi(r, mrow, "bm_inc_counter")
        c_pre != c_mort && (n_counter_shift += 1)

        c_npp = gf(r, mrow, "mort_npp")
        c_age = gf(r, mrow, "mort_age")
        c_wat = gf(r, mrow, "mort_water")
        c_tmp = gf(r, mrow, "mort_temp")
        c_prob = gf(r, mrow, "mort_prob")

        lbl = "y$year p$patch pft$pft_id t$treeidx"
        s_age = mort_age(p, age_pre)
        s_wat_m = mort_water(p, ws; bm_inc_counter = c_mort)
        s_wat_p = mort_water(p, ws; bm_inc_counter = c_pre)
        s_tmp = mort_temp(p, ts)
        note!(a_age, s_age, c_age, tol, lbl)
        note!(a_wat_m, s_wat_m, c_wat, tol, lbl)
        note!(a_wat_p, s_wat_p, c_wat, tol, lbl)
        note!(a_tmp, s_tmp, c_tmp, tol, lbl)

        # the dump's own self-consistency: mort_prob is the capped sum unless a hard kill fired
        s_sum = min(1.0, c_npp + c_age + c_wat + c_tmp)
        if c_prob < 1.0
            note!(a_sum, s_sum, c_prob, tol, lbl)
        end

        # mort_npp: one-sided test of the ported mort_max, plus the greff it implies
        mm = mort_max(p, wooddens)
        n_npp += 1
        gimp = NaN
        if c_npp >= 1.0
            n_npp_cap += 1
        else
            f = c_npp / (1 + c_mort)
            if f >= mm
                n_bound_viol += 1     # impossible under mort_npp = mort_max/(1+0.2·exp(k·greff))·(1+c)
            else
                gimp = log((mm / f - 1) / TraitMortality.KMORT_2) / TraitMortality.K_MORT
                push!(greffs, gimp)
            end
        end

        # v4: the full hazard, gated.  Every input is the value mortality_tree_ind itself used, taken
        # from the `mort` phase — bm_delta and leafarea_real are the C's own locals, leaf_c is the
        # post-allocation pool the ghost-tree kill tests, and the counter is the UPDATED one.
        s_npp = NaN
        s_tot = NaN
        hard = :none
        if has_bm
            bmd = gf(r, mrow, "bm_delta")
            larea = gf(r, mrow, "leafarea_real")
            leaf_c = gf(r, mrow, "leaf_c")
            # free cross-check: the C's own leafarea_real must be leaf_c·sla
            note!(a_larea, leaf_c * sla, larea, tol, lbl)
            s_npp = mort_npp(p, wooddens, bmd, larea; bm_inc_counter = c_mort)
            note!(a_npp, s_npp, c_npp, tol, lbl)
            h = mortality_hazard(
                p; wooddens = wooddens, sla = sla, age = age_pre, bm_delta = bmd,
                leafarea = larea, leaf_c = leaf_c, water_stress = ws, temp_stress = ts,
                bm_inc_counter = c_mort
            )
            s_tot = h.total
            hard = h.hard_kill
            n_hard[hard] = get(n_hard, hard, 0) + 1
            note!(a_tot, s_tot, c_prob, tol, lbl)
        end

        csv !== nothing && @printf(
            csv, "%d,%d,%d,%d,%d,%.17g,%.17g,%.17g,%.17g,%d,%d,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%s\n",
            year, patch, pft_id, treeidx, age_pre, wooddens, sla, ws, ts, c_pre, c_mort,
            c_npp, c_age, c_wat, c_tmp, c_prob, s_age, s_wat_m, s_wat_p, s_tmp, mm, gimp,
            s_npp, s_tot, hard
        )
    end
    csv !== nothing && close(csv)

    println("PFT ids exercised: ", join(["$k=>$(ids[k])" for k in sort(collect(keys(ids)))], "  "))
    println()
    println("GATED EXACTLY — every input present unchanged in the `pre` roster:")
    report("mort_age", a_age)
    report("mort_temp", a_tmp)
    report("mort_water [c=mort]", a_wat_m)
    println()
    if has_bm
        println("GATED EXACTLY — the two v4 columns close the fourth hazard and the total:")
        report("leafarea_real=leaf_c·sla", a_larea)
        report("mort_npp", a_npp)
        report("mortality_hazard.total", a_tot)
        @printf(
            "  hard kills classified: none=%d  bm_inc_counter=%d  ghost_tree=%d\n",
            n_hard[:none], n_hard[:bm_inc_counter], n_hard[:ghost_tree]
        )
        println()
    end
    println("BASIS PROBE — not a gate; what the rendezvous alone can reach:")
    report("mort_water [c=pre]", a_wat_p)
    @printf(
        "  bm_inc_counter differs pre vs mort in %d of %d records (%.1f %%)\n",
        n_counter_shift, length(keys_common), 100 * n_counter_shift / length(keys_common)
    )
    println()
    println("DUMP SELF-CONSISTENCY — the C's own mort_prob vs its own four components:")
    report("min(1,Σ components)", a_sum)
    if has_bm
        rendezvous_probe(r, pre, mrt, keys_common; lagged = true)
        # `grow` = the roster the rendezvous publishes since it moved behind the growth loop
        # (ADR 0123).  Absent from any dump recorded before that, in which case only the lagged
        # basis above can be reported.
        if isempty(grw)
            println()
            println("  (no `grow` phase in this dump: it predates the rendezvous move, so the LIVE")
            println("   rendezvous basis cannot be scored here — re-record with the current binary.)")
        else
            rendezvous_probe(r, grw, mrt, sort(collect(intersect(keys(grw), keys(mrt)))); lagged = false)
        end
    end

    if !isempty(opts["fixture"])
        has_bm || (@error "a fixture needs a v4+ dump (bm_delta/leafarea_real)"; exit(2))
        println()
        write_fixture(opts["fixture"], r, pre, mrt, keys_common, 60)
    end

    println()
    println(
        has_bm ? "CONTEXT — the pre-v4 one-sided bound, kept as a cross-check:" :
            "NOT GATED — mort_npp needs post-allocation bm_delta/leafarea (see the header):"
    )
    @printf("  records                          : %d\n", n_npp)
    @printf("  mort_npp capped at 1             : %d\n", n_npp_cap)
    @printf("  mort_max lower-bound violations  : %d   (a nonzero count refutes the ported mort_max)\n", n_bound_viol)
    if !isempty(greffs)
        s = sort(greffs)
        q(f) = s[clamp(1 + round(Int, f * (length(s) - 1)), 1, length(s))]
        @printf(
            "  implied greff  min/p05/med/p95/max: %.4g / %.4g / %.4g / %.4g / %.4g\n",
            s[1], q(0.05), q(0.5), q(0.95), s[end]
        )
    end
    println()

    gated = Any[("mort_age", a_age), ("mort_temp", a_tmp), ("mort_water", a_wat_m)]
    has_bm && append!(
        gated, Any[("leafarea_real", a_larea), ("mort_npp", a_npp), ("mortality_hazard.total", a_tot)]
    )
    bad = [n for (n, a) in gated if a.nexc > 0]
    if n_bound_viol > 0
        push!(bad, "mort_max bound")
    end
    if a_sum.nexc > 0
        push!(bad, "dump self-consistency")
    end
    if isempty(bad)
        if has_bm
            println("VERDICT: PASS — θ=1 reproduces the C's per-individual mortality probability EXACTLY,")
            println("         all four hazards and both hard kills, on every record. The port is verified.")
        else
            println("VERDICT: PASS — θ=1 reproduces the C exactly on all three fully-determined hazards.")
            println("         mort_npp remains UNGATED; it needs `bm_delta` + `leafarea_real` in the dump.")
        end
        return 0
    end
    println("VERDICT: FAIL — ", join(bad, ", "))
    return 1
end

exit(main(ARGS))
