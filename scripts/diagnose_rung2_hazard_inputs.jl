#!/usr/bin/env julia
# diagnose_rung2_hazard_inputs.jl — HOW MUCH OF THE RATE OPERATOR SURVIVES ON EMULATOR-SIDE INPUTS?
#
# ADR 0243, whose §1-4 are the pre-registration and were committed before this script produced a number.
# Dumps on disk only, NO model run. ADR 0242 measured a CEILING: inside rung 2 the ported hazard reads
# FIT's own two daily stress integrals through the rendezvous, which the standalone emulator does not
# have on that basis (ADR 0049 §3, ADR 0051). The operator is settled; what it READS is not. This prices
# exactly that gap by re-evaluating the SHIPPED hazard on the SAME roster rows under five input variants.
#
# ── THE VARIANTS (ADR 0243 §3) — only the hazard's ARGUMENTS change, never the roster or the code ─────
#   full        water/temp/counter all the C's       = the H1 campaign's own hazard. THE SELF-TEST.
#   zeroW       water 0, temp the C's               isolates the water integral
#   zeroT       water the C's, temp 0               isolates the temp integral
#   zeroWT      water 0, temp 0                     THE SHIPPED COUPLED DEFAULT (slow.jl:865, since
#                                                   `WaterParams.trait_drought_mortality` is false)
#   zeroWT_c0   + bm_inc_counter 0                  the counter a fresh rollout bootstraps — INFORMATION
#
# ⚠ THE REGIME THIS CANNOT MEASURE, NAMED IN THE PRE-REGISTRATION: ADR 0110 Phase 2 already accumulates
# each individual's OWN integrals in `fast.jl::_accumulate_stress!` from F's daily `wscal`/temperature,
# gated on `trait_drought_mortality`. Those are F's VALUES, not the C's, so no dump can carry them. This
# scorer BRACKETS that regime:  zeroWT  <=  F's own integrals  <=  full (= ADR 0242's ceiling).
#
# ── THE BLESSED STATISTIC AND ITS DERIVED NULLS (ADR 0243 §4.1; all three written before the run) ─────
#   Phi(variant) = sum(nind*h_variant) / sum(nind*mort_prob), pooled per leg and printed per cell.
#   1. Phi(full) == 1.0000 EXACTLY (ADR 0183: |dhazard| 5e-18 over 1.57 M stem-years). If it misses by
#      more than 1e-9 the scorer is wrong and NO other number here is read.
#   2. a do-nothing arm has Phi == 0 by construction, so Phi(zeroWT) is in (0, 1).
#   3. a DERIVABLE INEQUALITY, free and independent: zeroing the stresses can only lower the summed
#      hazard and cannot change either hard-kill class, so per stem h_full - h_zeroWT <= mort_water +
#      mort_temp, hence 1 - Phi(zeroWT) <= S_wt, FIT's own water+temp share of hazard mass. The SLACK is
#      what the min(1,.) cap and the hard kills absorb, and it is printed.
#   THRESHOLD, derived from ADR 0187's own measured mapping (flux 0.58 -> biomass 2.90x over 81 yr,
#   log-linear => k = ln(2.90)/0.42 = 2.535) against ADR 0242's |dAGB| < 40 % clause:
#      PASS  Phi >= 0.930 (the no-feedback bound exp(m*T*(1-Phi)), m = 0.0596/yr, T = 81)
#      FAIL  Phi <= 0.867 (the feedback-calibrated bound)
#      in between => NO CLEAN VERDICT, reported as a straddle. The band is NOT narrowed after the fact.
#
# ── ORDERING (ADR 0243 §4.2), because ADR 0242's H0 spent FIT's own flux on the wrong stems and
#    annihilated the >5 m stand: a variant that keeps Phi and loses the ordering is NOT a pass ─────────
#   certain set : positives h >= 1 against FIT's mort_prob >= 1; PRESERVED if recall >= 0.9 AND
#                 precision >= 0.9. Null: `full` is 1.0000/1.0000 by identity.
#   quintiles   : Phi within each quintile of the roster's own nind-weighted HEIGHT distribution;
#                 ORDERING PRESERVED if every quintile is within +-0.15 of that leg's pooled Phi (a
#                 level shift is recoverable by a scale factor, a tilt is not — ADR 0187's rule).
#   selectivity : lambda = flux-weighted / count-weighted mean per-stem mass, formed PER PATCH-YEAR then
#                 flux-weighted over patch-years, pooled printed beside it (skill trap 5e). SANITY RANGE
#                 ONLY: ADR 0187's FIT 0.900 is on realized discretionary kills, this is on total
#                 nominated hazard — different bases, so it gates nothing.
#
# ── REFERENCE BASIS (ADR 0243 §2) ─────────────────────────────────────────────────────────────────────
#   rosters : `predict`-mode `grow` rosters of REC (FIT's own stand — the PRIMARY basis) and H1 (the
#             stand the rate operator built — the corroboration), seed 1, 12 cells x 2 legs each.
#             Coverage: seed 1 is complete at all 12 cells on both legs (the 9 DEAD H* legs are all
#             seeds 2-5). The statistic is PER-STEM, so a truncated leg would still be scoreable.
#   phase   : `grow`, the rendezvous — it carries THIS year's hazard.
#   ported  : LPJmLFITEmulator.TraitMortality.mortality_hazard, reached as the SHIPPED name, with the
#             harness's own call (`age - 1`, the ADR 0031 off-by-one). No second copy of the hazard.
#   FIT's   : the dump's `mort_prob` column.
#   guard   : a stem whose mort_prob is not finite in [0,1] is DROPPED and counted.
#   ⚠ every variant is evaluated on the SAME roster row, so the stand cancels exactly and skill trap 5
#     (the C grows the stand, so a stand statistic is inherited by every arm) does not apply here.
#
# ENV: DUMPS (default /p/tmp/jamirp/S_rung2), ARMS (default "REC H1"), NPREV (default "predict"),
#      SEED (default 1), OUT (a CSV; optional)
# Run: TIME=01:00:00 scripts/sbatch_julia.sh S-hazinputs --project=. \
#          scripts/diagnose_rung2_hazard_inputs.jl
# Exit 0 always: this is a measurement, not a CI gate.

using Printf
using Statistics

using LPJmLFITEmulator
const TM = LPJmLFITEmulator.TraitMortality

const DUMPS = get(ENV, "DUMPS", "/p/tmp/jamirp/S_rung2")
const ARMS = split(get(ENV, "ARMS", "REC H1"))
const NPREV = get(ENV, "NPREV", "predict")
const SEED = parse(Int, get(ENV, "SEED", "1"))
const OUT = get(ENV, "OUT", "")

const VARIANTS = ("full", "zeroW", "zeroT", "zeroWT", "zeroWT_c0")
const NV = length(VARIANTS)
const IFULL = 1
const IZWT = 4

# the pre-registered thresholds — ADR 0243 §4, derived there, not chosen here
const PHI_PASS = 0.93          # the no-feedback bound
const PHI_FAIL = 0.867          # ADR 0187's feedback-calibrated bound
const IDENTITY_TOL = 1.0e-9     # null 1: Phi(full) must be 1 to this
const CERT_MIN = 0.9            # recall AND precision for "the certain set is preserved"
const QUINT_TOL = 0.15          # per-quintile departure from the pooled Phi
const NQ = 5

const HARD_CLASSES = (:none, :bm_inc_counter, :ghost_tree)

"""
One dump's accumulated panels. Every field is a sum over `T grow` stem-years of ONE roster, so two
variants' entries are on identical rows by construction.
"""
mutable struct Panels
    nstem::Int
    dropped::Int
    fitflux::Float64                     # sum nind*mort_prob                     — the denominator of Phi
    mass_npp::Float64                    # sum nind*mort_npp
    mass_age::Float64                    # sum nind*mort_age
    mass_wt::Float64                     # sum nind*(mort_water + mort_temp)      — null 3's bound
    flux::Vector{Float64}                # per variant: sum nind*h
    tp::Vector{Int}                      # certain-set confusion vs FIT's own
    fp::Vector{Int}
    fn::Vector{Int}
    hard::Matrix{Int}                    # variant x hard-kill class
    qfit::Vector{Float64}                # per height quintile: sum nind*mort_prob
    qflux::Matrix{Float64}               # per height quintile x variant: sum nind*h
    lam_num::Vector{Float64}             # per variant: flux-weighted sum of per-patch-year lambda
    lam_den::Vector{Float64}
    lam_pool_fm::Vector{Float64}         # pooled lambda: sum nind*h*mass
    lam_pool_f::Vector{Float64}          #                sum nind*h
    lam_pool_nm::Float64                 #                sum nind*mass
    lam_pool_n::Float64                  #                sum nind
    # the wscal_mean-vs-water_stress relation, accumulated per (cell, pft) so `r` is WITHIN-group
    wsr::Dict{Int, NTuple{6, Float64}}   # pft => (n, Sx, Sy, Sxx, Syy, Sxy), x = 1 - wscal_mean
    wsr_pool::NTuple{6, Float64}
end

Panels() = Panels(
    0, 0, 0.0, 0.0, 0.0, 0.0, zeros(NV), zeros(Int, NV), zeros(Int, NV), zeros(Int, NV),
    zeros(Int, NV, length(HARD_CLASSES)), zeros(NQ), zeros(NQ, NV), zeros(NV), zeros(NV),
    zeros(NV), zeros(NV), 0.0, 0.0, Dict{Int, NTuple{6, Float64}}(), ntuple(_ -> 0.0, 6)
)

_bump(t::NTuple{6, Float64}, x, y) =
    (t[1] + 1, t[2] + x, t[3] + y, t[4] + x * x, t[5] + y * y, t[6] + x * y)

function _pearson(t::NTuple{6, Float64})
    n, sx, sy, sxx, syy, sxy = t
    n < 3 && return NaN
    cov = sxy - sx * sy / n
    vx = sxx - sx * sx / n
    vy = syy - sy * sy / n
    (vx <= 0 || vy <= 0) && return NaN
    return cov / sqrt(vx * vy)
end

# `maximum(...; init = NaN)` would swallow the answer — `max(NaN, x)` is NaN in Julia, so an empty-safe
# maximum has to filter first and only then decide the fallback.
function _maxdev(devs::Vector{Float64})
    d = filter(isfinite, devs)
    return isempty(d) ? NaN : maximum(d)
end

recall(tp, fn) = (tp + fn) == 0 ? NaN : tp / (tp + fn)
precision(tp, fp) = (tp + fp) == 0 ? NaN : tp / (tp + fp)

"""
    hazards(f, tcols) -> (mfit, nind, mass, height, pft, ws, ts, hs, hard)

Evaluate the SHIPPED hazard on one dumped stem-year under all five input variants. `hs[1]` is the
`full` variant, i.e. the value the rung-2 harness itself used, which is why it doubles as the identity
self-test against the dump's own `mort_prob`.
"""
function hazards(f::Vector{<:AbstractString}, tcols::Dict{String, Int})
    # the n-th NAME is field n+1 of the record: field 1 is the "T" tag itself (skill trap 1)
    gf(n) = parse(Float64, f[tcols[n] + 1])
    gi(n) = parse(Int, f[tcols[n] + 1])
    p = TM.pft_mort_params(gi("pft_id"))
    ws = gf("water_stress")
    ts = gf("temp_stress")
    bmc = gi("bm_inc_counter")
    common = (
        wooddens = gf("wooddens"), sla = gf("sla"), age = gi("age") - 1,
        bm_delta = gf("bm_delta"), leafarea = gf("leafarea_real"), leaf_c = gf("leaf_c"),
    )
    args = (
        (ws, ts, bmc), (0.0, ts, bmc), (ws, 0.0, bmc), (0.0, 0.0, bmc), (0.0, 0.0, 0),
    )
    hs = ntuple(
        k -> TM.mortality_hazard(
            p; common..., water_stress = args[k][1], temp_stress = args[k][2],
            bm_inc_counter = args[k][3]
        ), NV
    )
    # ADR 0241 §6's per-stem mass definition, the one gated against ADR 0240's published dPER
    mass = gf("leaf_c") + gf("sapwood_c") + gf("heartwood_c") - gf("debt_c")
    return (
        gf("mort_prob"), gf("nind"), mass, gf("height"), gi("pft_id"), ws, ts,
        gf("wscal_mean"), gf("mort_npp"), gf("mort_age"), gf("mort_water"), gf("mort_temp"), hs,
    )
end

"""
    score_dump(path) -> (Panels, maxabs_identity)

One streaming pass for everything that needs no grouping, plus in-memory per-stem vectors for the two
panels that do: the height quintiles (edges are the roster's OWN nind-weighted height distribution) and
the per-patch-year mass selectivity (skill trap 5e — the operator draws once per patch-year, so that is
the only level at which the null is exact).
"""
function score_dump(path::AbstractString)
    tcols = Dict{String, Int}()
    P = Panels()
    maxabs = 0.0
    # kept for the two grouped panels
    hgt = Float64[]
    nind = Float64[]
    mass = Float64[]
    fitv = Float64[]
    hv = [Float64[] for _ in 1:NV]
    py = Int[]                     # a packed (year, patch) key
    for line in eachline(path)
        if startswith(line, "#H T ")
            tcols = Dict{String, Int}(String(n) => i for (i, n) in enumerate(split(line)[3:end]))
            continue
        end
        startswith(line, "T grow") || continue
        f = split(line)
        mfit = parse(Float64, f[tcols["mort_prob"] + 1])
        if !isfinite(mfit) || mfit < 0.0 || mfit > 1.0
            P.dropped += 1
            P.nstem += 1
            continue
        end
        (mp, ni, ms, ht, pft, ws, ts, wsm, mnpp, mage, mw, mt, hs) = hazards(f, tcols)
        P.nstem += 1
        P.fitflux += ni * mp
        P.mass_npp += ni * mnpp
        P.mass_age += ni * mage
        P.mass_wt += ni * (mw + mt)
        cf = mp >= 1.0
        for k in 1:NV
            h = hs[k].total
            P.flux[k] += ni * h
            cp = h >= 1.0
            cp && cf && (P.tp[k] += 1)
            cp && !cf && (P.fp[k] += 1)
            !cp && cf && (P.fn[k] += 1)
            ci = findfirst(==(hs[k].hard_kill), HARD_CLASSES)
            ci === nothing || (P.hard[k, ci] += 1)
            P.lam_pool_fm[k] += ni * h * ms
            P.lam_pool_f[k] += ni * h
        end
        P.lam_pool_nm += ni * ms
        P.lam_pool_n += ni
        maxabs = max(maxabs, abs(hs[IFULL].total - mp))
        # the annual-proxy relation, WITHIN (cell, pft): x = 1 - wscal_mean (what the emulator has as
        # `grow.water_stress`), y = the C's own unbounded integral. Information only — ADR 0243 §4.3.
        if isfinite(wsm) && isfinite(ws)
            x = 1.0 - wsm
            P.wsr[pft] = _bump(get(P.wsr, pft, ntuple(_ -> 0.0, 6)), x, ws)
            P.wsr_pool = _bump(P.wsr_pool, x, ws)
        end
        push!(hgt, ht)
        push!(nind, ni)
        push!(mass, ms)
        push!(fitv, mp)
        for k in 1:NV
            push!(hv[k], hs[k].total)
        end
        push!(py, parse(Int, f[tcols["year"] + 1]) * 100 + parse(Int, f[tcols["patch"] + 1]))
    end

    # ── height quintiles, nind-weighted on this roster's own distribution ─────────────────────────
    if !isempty(hgt)
        ord = sortperm(hgt)
        tot = sum(nind)
        cum = 0.0
        for i in ord
            q = min(NQ, 1 + Int(floor(NQ * cum / tot)))
            P.qfit[q] += nind[i] * fitv[i]
            for k in 1:NV
                P.qflux[q, k] += nind[i] * hv[k][i]
            end
            cum += nind[i]
        end
    end

    # ── per-patch-year mass selectivity, flux-weighted over patch-years ───────────────────────────
    if !isempty(py)
        ord = sortperm(py)
        i = 1
        while i <= length(ord)
            j = i
            key = py[ord[i]]
            while j <= length(ord) && py[ord[j]] == key
                j += 1
            end
            idx = @view ord[i:(j - 1)]
            sn = sum(nind[t] for t in idx)
            snm = sum(nind[t] * mass[t] for t in idx)
            if sn > 0 && snm > 0
                mbar = snm / sn
                for k in 1:NV
                    sf = sum(nind[t] * hv[k][t] for t in idx)
                    sfm = sum(nind[t] * hv[k][t] * mass[t] for t in idx)
                    if sf > 0
                        P.lam_num[k] += sf * ((sfm / sf) / mbar)
                        P.lam_den[k] += sf
                    end
                end
            end
            i = j
        end
    end
    return P, maxabs
end

function merge_panels!(a::Panels, b::Panels)
    a.nstem += b.nstem
    a.dropped += b.dropped
    a.fitflux += b.fitflux
    a.mass_npp += b.mass_npp
    a.mass_age += b.mass_age
    a.mass_wt += b.mass_wt
    a.flux .+= b.flux
    a.tp .+= b.tp
    a.fp .+= b.fp
    a.fn .+= b.fn
    a.hard .+= b.hard
    a.qfit .+= b.qfit
    a.qflux .+= b.qflux
    a.lam_num .+= b.lam_num
    a.lam_den .+= b.lam_den
    a.lam_pool_fm .+= b.lam_pool_fm
    a.lam_pool_f .+= b.lam_pool_f
    a.lam_pool_nm += b.lam_pool_nm
    a.lam_pool_n += b.lam_pool_n
    for (k, v) in b.wsr
        o = get(a.wsr, k, ntuple(_ -> 0.0, 6))
        a.wsr[k] = ntuple(i -> o[i] + v[i], 6)
    end
    a.wsr_pool = ntuple(i -> a.wsr_pool[i] + b.wsr_pool[i], 6)
    return a
end

phi(P::Panels, k::Int) = P.fitflux == 0 ? NaN : P.flux[k] / P.fitflux

function verdict_phi(p::Float64)
    isnan(p) && return "NOT SCOREABLE"
    p >= PHI_PASS && return @sprintf("PASS (Phi %.4f >= %.3f, the no-feedback bound)", p, PHI_PASS)
    p <= PHI_FAIL && return @sprintf(
        "FAIL (Phi %.4f <= %.3f, ADR 0187's calibrated bound)", p, PHI_FAIL
    )
    return string(
        "NO CLEAN VERDICT — STRADDLE (",
        @sprintf("%.3f < Phi %.4f < %.3f", PHI_FAIL, p, PHI_PASS),
        "); the pre-registered escalation is a coupled arm, not another offline panel"
    )
end

function main()
    println("="^108)
    println("HOW MUCH OF THE RATE OPERATOR SURVIVES ON EMULATOR-SIDE INPUTS?   (ADR 0243)")
    println("  the SHIPPED hazard re-evaluated on the SAME roster rows under 5 input variants; no run.")
    @printf(
        "  PRE-REGISTERED (ADR 0243 §4): Phi >= %.3f PASS · Phi <= %.3f FAIL · in between = STRADDLE\n",
        PHI_PASS, PHI_FAIL
    )
    @printf(
        "  DERIVED NULLS: Phi(full) == 1 to %.0e · do-nothing == 0 · 1 - Phi(zeroWT) <= S_wt\n",
        IDENTITY_TOL
    )
    println("  variants: " * join(VARIANTS, " · "))
    println("  ⚠ CEILING/BRACKET: zeroWT <= F's own integrals (ADR 0110 Ph2) <= full. The middle term")
    println("    is NOT measurable from a dump — it needs a coupled run, and no claim is made about it.")
    println("="^108)

    rx = Regex(
        "^S_r2s_(historic|ssp370)_c(\\d+)_(REC|NP|S0h|S0|S1|G0h|G0|G1|H0h|H0|H1)_" *
            NPREV * "_s$(SEED)_dump\$"
    )
    keep = Tuple{String, Int, String, String}[]
    for name in sort(readdir(DUMPS))
        m = match(rx, name)
        m === nothing && continue
        String(m.captures[3]) in ARMS || continue
        p = joinpath(DUMPS, name, "roster_rank0000.txt")
        isfile(p) || continue
        push!(keep, (String(m.captures[3]), parse(Int, m.captures[2]), String(m.captures[1]), p))
    end
    sort!(keep, by = x -> (x[1], x[3], x[2]))
    println("\nscoring $(length(keep)) dumps (arms $(join(ARMS, "/")), NPREV=$NPREV, seed $SEED)")
    flush(stdout)

    per = Dict{Tuple{String, String, Int}, Panels}()
    ident = Dict{Tuple{String, String, Int}, Float64}()
    for (arm, cell, scen, p) in keep
        P, ma = score_dump(p)
        per[(arm, scen, cell)] = P
        ident[(arm, scen, cell)] = ma
        @printf(
            "   scored %-4s %-9s c%-6d  %9d stems  max|h_full - mort_prob| %.3e\n",
            arm, scen, cell, P.nstem, ma
        )
        flush(stdout)
    end

    rows = String[]
    for arm in ARMS
        for scen in ("historic", "ssp370")
            sel = sort([k for k in keys(per) if k[1] == arm && k[2] == scen], by = x -> x[3])
            isempty(sel) && continue
            tot = Panels()
            worst_id = 0.0
            for k in sel
                merge_panels!(tot, per[k])
                worst_id = max(worst_id, ident[k])
            end
            ncell = length(sel)

            println("\n" * "="^108)
            println(
                "ARM $arm — $scen leg — $ncell cells, $(tot.nstem) tree stem-years " *
                    "($(tot.dropped) dropped on the mort_prob guard)"
            )
            println("="^108)

            # ── PANEL A — the identity self-test. Nothing else is read if this fails ──────────────
            pf = phi(tot, IFULL)
            ok = worst_id <= 1.0e-9 && abs(pf - 1.0) <= IDENTITY_TOL
            println("\n-- PANEL A  identity self-test (ADR 0243 §4.1 null 1)")
            @printf(
                "   max|h_full - mort_prob| = %.3e over all cells; Phi(full) = %.10f\n",
                worst_id, pf
            )
            println(
                "   " * (
                    ok ? "PASS — the port IS FIT's own hazard on these rows (reproduces ADR 0183)." :
                        "FAIL — THE SCORER IS WRONG; no other panel below is to be read."
                )
            )

            # ── PANEL B — the blessed statistic ──────────────────────────────────────────────────
            println("\n-- PANEL B  the nomination-flux ratio Phi = sum(nind*h) / sum(nind*mort_prob)")
            @printf("   %-12s %12s %12s   %s\n", "variant", "Phi", "1 - Phi", "verdict")
            for k in 1:NV
                p = phi(tot, k)
                v = k == IZWT ? verdict_phi(p) : (k == IFULL ? "(the self-test)" : "(diagnostic)")
                @printf("   %-12s %12.4f %12.4f   %s\n", VARIANTS[k], p, 1 - p, v)
            end
            s_wt = tot.fitflux == 0 ? NaN : tot.mass_wt / tot.fitflux
            pz = phi(tot, IZWT)
            println("   NULL 3 (derivable): 1 - Phi(zeroWT) <= S_wt, FIT's own water+temp mass share;")
            println("     the slack is what the min(1,.) cap and the hard kills absorb.")
            @printf(
                "     1 - Phi = %.4f <= S_wt = %.4f  -> %s   (slack %.4f)\n",
                1 - pz, s_wt, (1 - pz) <= s_wt + 1.0e-12 ? "HOLDS" : "VIOLATED — scorer bug",
                s_wt - (1 - pz)
            )
            @printf(
                "   FIT's own hazard-mass shares: npp %.4f · age %.4f · water+temp %.4f\n",
                tot.mass_npp / tot.fitflux, tot.mass_age / tot.fitflux, s_wt
            )
            println("\n   per cell (Phi):")
            @printf("   %8s %10s", "cell", "stems")
            for v in VARIANTS
                @printf(" %11s", v)
            end
            println()
            for k in sel
                P = per[k]
                @printf("   %8d %10d", k[3], P.nstem)
                for kk in 1:NV
                    @printf(" %11.4f", phi(P, kk))
                end
                println()
                push!(
                    rows, string(
                        arm, ",", scen, ",", k[3], ",", P.nstem, ",", P.dropped, ",",
                        join([phi(P, kk) for kk in 1:NV], ","), ",",
                        P.fitflux == 0 ? NaN : P.mass_wt / P.fitflux, ",",
                        join([recall(P.tp[kk], P.fn[kk]) for kk in 1:NV], ","), ",",
                        join([precision(P.tp[kk], P.fp[kk]) for kk in 1:NV], ",")
                    )
                )
            end

            # ── PANEL C — the certain set ────────────────────────────────────────────────────────
            println(
                "\n-- PANEL C  certain set (h >= 1) against FIT's own; PRESERVED needs both >= " *
                    "$(CERT_MIN)"
            )
            @printf(
                "   %-12s %10s %10s %10s %10s   %s\n",
                "variant", "FITcert", "VARcert", "recall", "precision", "read"
            )
            for k in 1:NV
                r = recall(tot.tp[k], tot.fn[k])
                pr = precision(tot.tp[k], tot.fp[k])
                read = if isnan(r) || isnan(pr)
                    "not scoreable"
                elseif r >= CERT_MIN && pr >= CERT_MIN
                    "PRESERVED"
                else
                    "NOT preserved"
                end
                @printf(
                    "   %-12s %10d %10d %10.4f %10.4f   %s\n",
                    VARIANTS[k], tot.tp[k] + tot.fn[k], tot.tp[k] + tot.fp[k], r, pr, read
                )
            end
            println("\n   hard-kill class census (stem-years):")
            @printf("   %-12s %14s %16s %14s\n", "variant", "none", "bm_inc_counter", "ghost_tree")
            for k in 1:NV
                @printf(
                    "   %-12s %14d %16d %14d\n",
                    VARIANTS[k], tot.hard[k, 1], tot.hard[k, 2], tot.hard[k, 3]
                )
            end

            # ── PANEL D — ordering: quintiles + selectivity ──────────────────────────────────────
            println(
                "\n-- PANEL D  ordering. Phi within each quintile of the roster's own " *
                    "nind-weighted HEIGHT distribution"
            )
            @printf("   %-12s", "variant")
            for q in 1:NQ
                @printf(" %10s", "Q$q")
            end
            @printf(" %10s %12s   %s\n", "pooled", "max|dev|", "read")
            for k in 1:NV
                p = phi(tot, k)
                devs = Float64[]
                @printf("   %-12s", VARIANTS[k])
                for q in 1:NQ
                    pq = tot.qfit[q] == 0 ? NaN : tot.qflux[q, k] / tot.qfit[q]
                    push!(devs, abs(pq - p))
                    @printf(" %10.4f", pq)
                end
                md = _maxdev(devs)
                @printf(
                    " %10.4f %12.4f   %s\n", p, md,
                    isnan(md) ? "not scoreable" :
                        (
                            md <= QUINT_TOL ? "ORDERING PRESERVED (level shift only)" :
                            "TILTED — not recoverable by a scale factor"
                        )
                )
            end
            println(
                "\n   mass selectivity of the nominated flux (SANITY RANGE ONLY — a different " *
                    "basis from ADR 0187's FIT 0.900):"
            )
            @printf("   %-12s %16s %16s\n", "variant", "lambda(per-p-y)", "lambda(pooled)")
            for k in 1:NV
                ls = tot.lam_den[k] == 0 ? NaN : tot.lam_num[k] / tot.lam_den[k]
                lp = if tot.lam_pool_f[k] == 0 || tot.lam_pool_n == 0
                    NaN
                else
                    (tot.lam_pool_fm[k] / tot.lam_pool_f[k]) / (tot.lam_pool_nm / tot.lam_pool_n)
                end
                @printf("   %-12s %16.4f %16.4f\n", VARIANTS[k], ls, lp)
            end

            # ── PANEL E — information: can an annual proxy stand in for the daily integral? ──────
            println(
                "\n-- PANEL E  INFORMATION, NOT A GATE: does the C's own annual (1 - wscal_mean) " *
                    "track its own water_stress integral?"
            )
            println(
                "   ⚠ the POOLED r is not quotable as skill — adding units raises a " *
                    "cross-sectional correlation (skill trap 5j). Only the within-(cell,PFT) r is read."
            )
            @printf("   pooled over all stems: r = %.4f\n", _pearson(tot.wsr_pool))
            rs = Float64[]
            for pft in sort(collect(keys(tot.wsr)))
                r = _pearson(tot.wsr[pft])
                n = tot.wsr[pft][1]
                isfinite(r) && n >= 100 && push!(rs, r)
                @printf("     pft %2d  n = %9.0f   r = %8.4f\n", pft, n, r)
            end
            if !isempty(rs)
                @printf(
                    "   within-PFT (pooled over cells, n >= 100): median r = %.4f  [%.4f, %.4f], %d PFTs\n",
                    median(rs), minimum(rs), maximum(rs), length(rs)
                )
            end

            # ── the ADR 0243 §4.4 decision line ─────────────────────────────────────────────────
            rz = recall(tot.tp[IZWT], tot.fn[IZWT])
            pz2 = precision(tot.tp[IZWT], tot.fp[IZWT])
            devs = [
                abs((tot.qfit[q] == 0 ? NaN : tot.qflux[q, IZWT] / tot.qfit[q]) - pz) for q in 1:NQ
            ]
            mdz = _maxdev(devs)
            cert_ok = !isnan(rz) && !isnan(pz2) && rz >= CERT_MIN && pz2 >= CERT_MIN
            quint_ok = !isnan(mdz) && mdz <= QUINT_TOL
            println("\n-- DECISION [$arm/$scen] on the SHIPPED default (zeroWT), ADR 0243 §4.4")
            @printf(
                "   Phi %.4f · certain set %s (recall %.4f / precision %.4f)\n",
                pz, cert_ok ? "PRESERVED" : "NOT preserved", rz, pz2
            )
            @printf(
                "   quintile ordering %s (max|dev| %.4f)\n", quint_ok ? "PRESERVED" : "TILTED", mdz
            )
            println("   " * verdict_phi(pz))
            if pz >= PHI_PASS && cert_ok && quint_ok
                println(
                    "   => §4.4 PASS branch: wire the rate operator with the stresses ZEROED; " *
                        "leave `trait_drought_mortality` off; NO integration point with line M."
                )
            elseif pz <= PHI_FAIL || !cert_ok || !quint_ok
                println(
                    "   => §4.4 FAIL branch: the integrals are load-bearing. Read zeroW vs " *
                        "zeroT above for WHICH one. The accumulator already exists in `fast.jl`, so an"
                )
                println(
                    "      S-side arm can switch it on through the existing kwarg with no " *
                        "integration point; only moving the shipped DEFAULT is a request to line M."
                )
            else
                println("   => §4.4 STRADDLE branch: no verdict; escalate to a coupled arm.")
            end
        end
    end

    if !isempty(OUT)
        mkpath(dirname(OUT))
        open(OUT, "w") do io
            println(
                io, "arm,scenario,cell,stems,dropped," *
                    join(["phi_" * v for v in VARIANTS], ",") * ",water_temp_mass_share," *
                    join(["recall_" * v for v in VARIANTS], ",") * "," *
                    join(["precision_" * v for v in VARIANTS], ",")
            )
            for r in rows
                println(io, r)
            end
        end
        println("\nwrote $(length(rows)) rows -> $OUT")
    end
    return 0
end

main()
