#!/usr/bin/env julia
# diagnose_rung2_ported_certain_set.jl — DOES THE PORTED HAZARD'S CERTAIN-KILL SET REPRODUCE FIT'S OWN?
# ADR 0176 §4's pre-registered `trait_mortality` flip criterion, measured. Dumps on disk only, no run.
#
# ── THE CRITERION, VERBATIM FROM ADR 0176 §4 (pre-registered there, not here) ─────────────────────────
#   "on >= 12 named cells, the ported hazard's certain set (`mort >= 1`) against FIT's own on the SAME
#    rosters must reach recall >= 0.8 with precision >= 0.8; the harness already sees both, so this costs
#    one comparison pass and no new run. If it passes, flip; if it fails, the finding is that the port's
#    hazard needs the stress integrals before its ordering is worth anything."
# Positives = certain kills. FIT's own set is the reference, so
#     recall    = |ported ∩ FIT| / |FIT|        (of the stems FIT was certain about, how many the port is)
#     precision = |ported ∩ FIT| / |ported|     (of the stems the port is certain about, how many FIT is)
#
# ⚠ AND IT CORRECTS ADR 0176 §4's PREMISE, WHICH IS WRONG ON A POINT OF CODE. That section says the ~85 %
# of `S1`'s advantage that comes from honouring certain kills was obtained from "FIT's own `mort >= 1`,
# read off the C's roster", and that the coupled flip therefore rests on the port reproducing it. But
# `rung2_s_demography_harness.jl:539` computes `certain = [t.mort >= 1.0 for t in trees]`, and `Tree.mort`
# (its own field comment, :206) is `TM.mortality_hazard` — THE PORTED HAZARD, evaluated at :262 on the
# roster's state. The harness never reads the dump's `mort_prob` at all; only its inline comment at :533
# calls that field "FIT's own hazard". So the S0h/S1 advantage ADR 0176 measured was ALREADY the port's,
# and this measurement is not a gate the flip is waiting on — it prices how much of the port's certain
# set is FIT-faithful rather than the port's own accident. What the coupled flip still rests on is a
# different thing: whether the coupled fast core can SUPPLY the hazard's inputs (`bm_delta`,
# `leafarea_real`, `water_stress`, `temp_stress`, `bm_inc_counter`), which here are read off the C.
#
# ── REFERENCE BASIS (stated before any number is read) ────────────────────────────────────────────────
#   rosters   : the `REC` dumps = LPJmL-FIT's own roster through the pure-observation path, one per cell
#               per scenario. Headline is REC because there FIT's hazard is uncontaminated by any
#               substitution; the `S1` rosters are scored beside it as a secondary check (an arm's own
#               roster is what the operator would act on, but it is a stand the emulator has altered).
#   phase     : `grow`, where the roster carries THIS year's hazard: `mortality_tree_ind` runs inside the
#               growth loop, ahead of the `grow` dump (patches/lpjmlfit_rung2_hook_v5.patch). Verified
#               against the `mort`-phase records: for a stem present in both, all five `mort_*` columns
#               are bit-identical. The hook's own warning that `mort_*`/`bm_delta`/`leafarea_real` are
#               uninitialised garbage applies to `pre` and to a recruit's establishment year, not here.
#   ported    : `LPJmLFITEmulator.TraitMortality.mortality_hazard`, reached as the shipped name with the
#               SAME call the harness makes (`age = age - 1`: the emitted age is post-increment while the
#               C's own hazard used the pre-increment age — the ADR-0031 off-by-one). No second copy of
#               the hazard exists in this file; that is the point.
#   FIT's own : the dump's `mort_prob` column = the C's `min(1, mort_npp+mort_age+mort_water+mort_temp)`.
#   guard     : a stem whose `mort_prob` is not finite and in [0, 1] is DROPPED and counted, because the
#               field is uninitialised for a stem that has not been through `mortality_tree_ind`.
#
# ENV: DUMPS (default /p/tmp/jamirp/S_rung2), ARMS (default "REC S1"), OUT (a CSV; optional)
# Run: TIME=00:40:00 scripts/sbatch_julia.sh S-certain --project=. \
#          scripts/diagnose_rung2_ported_certain_set.jl
# Exit 0 always: this is a measurement, not a gate.

using Printf

using LPJmLFITEmulator
const TM = LPJmLFITEmulator.TraitMortality

const DUMPS = get(ENV, "DUMPS", "/p/tmp/jamirp/S_rung2")
const ARMS = split(get(ENV, "ARMS", "REC S1"))
const OUT = get(ENV, "OUT", "")

# the pre-registered pass thresholds — ADR 0176 §4's, not this file's
const PASS_RECALL = 0.8
const PASS_PRECISION = 0.8
const MIN_CELLS = 12

struct Tally
    tp::Int          # ported certain AND FIT certain
    fp::Int          # ported certain, FIT not
    fn::Int          # FIT certain, ported not
    tn::Int
    dropped::Int     # mort_prob not finite in [0, 1]
    nstem::Int
end

Tally() = Tally(0, 0, 0, 0, 0, 0)
Base.:+(a::Tally, b::Tally) = Tally(
    a.tp + b.tp, a.fp + b.fp, a.fn + b.fn, a.tn + b.tn, a.dropped + b.dropped, a.nstem + b.nstem
)
recall(t::Tally) = (t.tp + t.fn) == 0 ? NaN : t.tp / (t.tp + t.fn)
precision(t::Tally) = (t.tp + t.fp) == 0 ? NaN : t.tp / (t.tp + t.fp)

"""
    score_dump(path) -> (t, sumabs, nhaz, t0, sumabs0, mass_wt, mass_all)

Stream one roster dump's `grow` records; for each stem, evaluate the ported hazard and compare its
certain-kill verdict with the C's own. Also returns the summed absolute hazard difference and the stem
count behind it, so the certain-set agreement can be read against how close the two hazards are overall
(a certain set can agree while the hazards differ everywhere else, and vice versa).

`t0` / `sumabs0` are THE SAME COMPARISON FOR THE ZEROED-STRESS PORT — the hazard re-evaluated with
`water_stress = temp_stress = 0`, which is EXACTLY what the coupled emulator feeds it: `slow.jl`'s
`_trait_hazards!` passes zeros for both unless `FDiffFastCore`'s `trait_drought_mortality` is also on
(:865-869), because F has neither of FIT's daily stress integrals on FIT's basis (ADR 0049 §3, ADR 0051).
So `t` prices the hazard FUNCTION and `t0` prices the hazard AS THE COUPLED LOOP WOULD RUN IT. `mass_wt`
/ `mass_all` are FIT's own `mort_water + mort_temp` and total hazard mass, summed over stems, for the
same reason: an input that carries no hazard mass at these cells cannot be what blocks a flip.
"""
function score_dump(path::AbstractString)
    tcols = Dict{String, Int}()
    t = Tally()
    t0 = Tally()
    sumabs = 0.0
    sumabs0 = 0.0
    mass_wt = 0.0
    mass_all = 0.0
    nhaz = 0
    for line in eachline(path)
        if startswith(line, "#H T ")
            tcols = Dict(n => i for (i, n) in enumerate(split(line)[3:end]))
            continue
        end
        startswith(line, "T grow") || continue
        f = split(line)
        # the n-th NAME is field n+1 of the record: field 1 is the "T" tag itself
        gf(n) = parse(Float64, f[tcols[n] + 1])
        gi(n) = parse(Int, f[tcols[n] + 1])
        mfit = gf("mort_prob")
        if !isfinite(mfit) || mfit < 0.0 || mfit > 1.0
            t += Tally(0, 0, 0, 0, 1, 1)
            continue
        end
        p = TM.pft_mort_params(gi("pft_id"))
        h = TM.mortality_hazard(
            p; wooddens = gf("wooddens"), sla = gf("sla"), age = gi("age") - 1,
            bm_delta = gf("bm_delta"), leafarea = gf("leafarea_real"), leaf_c = gf("leaf_c"),
            water_stress = gf("water_stress"), temp_stress = gf("temp_stress"),
            bm_inc_counter = gi("bm_inc_counter")
        )
        h0 = TM.mortality_hazard(
            p; wooddens = gf("wooddens"), sla = gf("sla"), age = gi("age") - 1,
            bm_delta = gf("bm_delta"), leafarea = gf("leafarea_real"), leaf_c = gf("leaf_c"),
            water_stress = 0.0, temp_stress = 0.0,
            bm_inc_counter = gi("bm_inc_counter")
        )
        cp = h.total >= 1.0
        cf = mfit >= 1.0
        c0 = h0.total >= 1.0
        t += Tally(cp && cf, cp && !cf, !cp && cf, !cp && !cf, 0, 1)
        t0 += Tally(c0 && cf, c0 && !cf, !c0 && cf, !c0 && !cf, 0, 1)
        sumabs += abs(h.total - mfit)
        sumabs0 += abs(h0.total - mfit)
        mass_wt += gf("mort_water") + gf("mort_temp")
        mass_all += mfit
        nhaz += 1
    end
    return t, sumabs, nhaz, t0, sumabs0, mass_wt, mass_all
end

function main()
    println("="^100)
    println("DOES THE PORTED HAZARD'S CERTAIN-KILL SET REPRODUCE FIT'S OWN?  (ADR 0176 §4's criterion)")
    println("  positives = certain kills (hazard >= 1); FIT's own set is the reference.")
    @printf(
        "  PRE-REGISTERED (ADR 0176 §4): PASS if recall >= %.2f AND precision >= %.2f on >= %d cells\n",
        PASS_RECALL, PASS_PRECISION, MIN_CELLS
    )
    println("  ⚠ see the header: ADR 0176 §4's premise about WHICH hazard the arms used is wrong;")
    println("    this measurement prices the port's fidelity, it is not the flip's blocker.")
    println("="^100)

    rx = r"^S_r2s_(historic|ssp370frz|ssp370)_c(\d+)_(REC|NP|S0h|S0|S1)_roster_s(\d+)_dump$"
    found = Tuple{String, Int, String, Int, String}[]
    for name in sort(readdir(DUMPS))
        m = match(rx, name)
        m === nothing && continue
        String(m.captures[3]) in ARMS || continue
        m.captures[1] == "ssp370frz" && continue
        p = joinpath(DUMPS, name, "roster_rank0000.txt")
        isfile(p) || continue
        push!(
            found, (
                String(m.captures[3]), parse(Int, m.captures[2]),
                String(m.captures[1]), parse(Int, m.captures[4]), p,
            )
        )
    end
    # one seed per (arm, cell, scenario): the hazard is a deterministic function of the roster, so extra
    # seeds add rosters, not independent verdicts on the same rosters. Keep the lowest seed.
    sort!(found, by = x -> (x[1], x[2], x[3], x[4]))
    keep = Tuple{String, Int, String, Int, String}[]
    seen = Set{Tuple{String, Int, String}}()
    for f in found
        k = (f[1], f[2], f[3])
        k in seen && continue
        push!(seen, k)
        push!(keep, f)
    end
    println("\nscoring $(length(keep)) dumps (arms $(join(ARMS, "/")); lowest seed each)")
    flush(stdout)

    per = Dict{Tuple{String, Int, String}, Any}()
    for (arm, cell, scen, _seed, p) in keep
        per[(arm, cell, scen)] = score_dump(p)
        flush(stdout)
    end

    rows = String[]
    for arm in ARMS
        for scen in ("historic", "ssp370")
            sel = sort([k for k in keys(per) if k[1] == arm && k[3] == scen], by = x -> x[2])
            isempty(sel) && continue
            println("\n" * "-"^100)
            println("-- arm $arm, $scen leg — per cell")
            @printf(
                "   %8s %10s %8s %8s %10s %10s %10s | %8s %10s %10s %10s\n",
                "cell", "stems", "FITcert", "PORTcert", "recall", "precision", "mean|Δhaz|",
                "0Scert", "0Srecall", "0Sprec", "wt/all"
            )
            tot = Tally()
            tot0 = Tally()
            sa = 0.0
            sa0 = 0.0
            mwt = 0.0
            mall = 0.0
            nh = 0
            for k in sel
                t, sm, n, t0, sm0, wt, allm = per[k]
                tot += t
                tot0 += t0
                sa += sm
                sa0 += sm0
                mwt += wt
                mall += allm
                nh += n
                @printf(
                    "   %8d %10d %8d %8d %10.4f %10.4f %10.2e | %8d %10.4f %10.4f %10.5f\n",
                    k[2], t.nstem, t.tp + t.fn, t.tp + t.fp,
                    recall(t), precision(t), n == 0 ? NaN : sm / n,
                    t0.tp + t0.fp, recall(t0), precision(t0), allm == 0 ? NaN : wt / allm
                )
                push!(
                    rows, string(
                        arm, ",", scen, ",", k[2], ",", t.nstem, ",", t.tp + t.fn, ",",
                        t.tp + t.fp, ",", t.tp, ",", recall(t), ",", precision(t), ",",
                        n == 0 ? NaN : sm / n, ",", t.dropped, ",", t0.tp + t0.fp, ",",
                        recall(t0), ",", precision(t0), ",",
                        n == 0 ? NaN : sm0 / n, ",", allm == 0 ? NaN : wt / allm
                    )
                )
            end
            @printf(
                "   %8s %10d %8d %8d %10.4f %10.4f %10.2e | %8d %10.4f %10.4f %10.5f\n",
                "POOLED", tot.nstem, tot.tp + tot.fn, tot.tp + tot.fp,
                recall(tot), precision(tot), nh == 0 ? NaN : sa / nh,
                tot0.tp + tot0.fp, recall(tot0), precision(tot0), mall == 0 ? NaN : mwt / mall
            )
            ncell = length(sel)
            r, pr = recall(tot), precision(tot)
            r0, pr0 = recall(tot0), precision(tot0)
            verdict = if ncell < MIN_CELLS
                "NO VERDICT — $ncell cells, the criterion names >= $MIN_CELLS"
            elseif !isnan(r) && !isnan(pr) && r >= PASS_RECALL && pr >= PASS_PRECISION
                "PASSES ADR 0176 §4's criterion (recall $(round(r, digits = 3)) / " *
                    "precision $(round(pr, digits = 3)))"
            else
                "FAILS ADR 0176 §4's criterion (recall $(round(r, digits = 3)) / " *
                    "precision $(round(pr, digits = 3)))"
            end
            println("   VERDICT [$arm/$scen, $ncell cells]: $verdict")
            v0 = if isnan(r0) || isnan(pr0)
                "not scoreable"
            elseif r0 >= PASS_RECALL && pr0 >= PASS_PRECISION
                "ALSO PASSES with the stress integrals ZEROED (recall $(round(r0, digits = 3)) / " *
                    "precision $(round(pr0, digits = 3))) — i.e. as the COUPLED loop would run it, " *
                    "so the missing integrals do not block the flip at these cells"
            else
                "FAILS once the stress integrals are ZEROED (recall $(round(r0, digits = 3)) / " *
                    "precision $(round(pr0, digits = 3))) — the coupled flip needs " *
                    "`trait_drought_mortality` too, not just `trait_mortality`"
            end
            println("   ZEROED-STRESS ARM [$arm/$scen]: $v0")
            @printf(
                "   FIT's own mort_water + mort_temp is %.3f %% of its total hazard mass here.\n",
                100 * (mall == 0 ? NaN : mwt / mall)
            )
            println("   VERDICT [$arm/$scen, $ncell cells]: $verdict")
        end
    end

    if !isempty(OUT)
        mkpath(dirname(OUT))
        open(OUT, "w") do io
            println(
                io, "arm,scenario,cell,stems,fit_certain,ported_certain,tp,recall," *
                    "precision,mean_abs_dhaz,dropped,zs_certain,zs_recall,zs_precision," *
                    "zs_mean_abs_dhaz,water_temp_mass_share"
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
