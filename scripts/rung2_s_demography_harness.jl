#!/usr/bin/env julia
# rung2_s_demography_harness.jl — RUNG 2 for LINE S: the SHIPPED Component-S demography deciding who dies
# and who establishes inside LPJmL-FIT's OWN daily physics, year after year, in a closed loop.
#
# WHY THIS EXISTS AND WHY IT IS NOT ARM C
# ---------------------------------------
# `scripts/rung2_armc_harness.jl` serves a decision from the ported FIT hazard with the count target taken
# either from that hazard itself (`RHO=expected`, which pins theta = 1) or from the recorded baseline's own
# realized thinning (`RHO=recorded`).  Neither asks the count model anything.  So arm C measured the
# ORDERING interface and left the actual deliverable — the learned demography — untested against real
# physics.  This harness closes that: rho comes from the production count DRF, evaluated on a feature row
# built from the live roster the C publishes, and the recruit traits come from the production copula.
#
# It exists because rung 1 (ADR 0174) found the count channel's warming response FAILS ON SIGN when the
# emulator runs free (+0.707 one-step -> -0.226 free-running, validity horizon ~3 yr), and because rung 1
# could not decide whether that is a property of the demography or of the OFFLINE construction it was
# measured in.  Arm A1 (ADR 0112) recursed a scalar count while holding the six roster-state features at
# FIT's values — nobody would deploy that, and its own header calls itself a strict lower bound.  Here the
# state is a real stand: every feature is read off it, so `n_prev` is the stand's own previous count instead
# of the model's previous prediction (`--n-prev=roster`, the ADR-0175 fix), and there is no scalar to drift.
#
# THE ARMS.  Report all of them; each is one substitution more than the last.
#   S0  learned count target + UNIFORM thinning + establishment left to the C   (the shipped default)
#   S0h S0, except deaths FIT's own hazard had already settled (`mort >= 1`) are not overridden — the
#       DECOMPOSITION CONTROL (ADR 0176).  S1 differs from S0 in two ways at once, and this arm splits
#       them: `S0h - S0` is worth the interface behaviour alone, `S1 - S0h` is worth trait ordering.
#   S1  learned count target + the trait hazard's ORDERING + establishment left to the C
#   S2  S1 + recruit traits from the production copula — NOT WIRED HERE YET; establishment stays with the
#       C in every arm below, so `nrec` is 0 by construction and no S number here is a recruit result.
# and the two controls, which are what make any of it attributable:
#   N0  no substitution at all (`MODE=none` of run_rung2_replay_arm.sh) — the transport null
#   NP  the PERSISTENCE null: rho = 1 every year, i.e. keep the stand, learn nothing.  ADR 0112 showed a
#       persistence null matches the production model on every response statistic OFFLINE; if it also does
#       so HERE then this harness has no more power than the offline basis did, and that is the first thing
#       to check before believing S0-S2.
#
# THE `G*` ARMS — THE SAME THREE OPERATORS, SPENDING A GROSS KILL BUDGET FROM A RUNNING ACCOUNT
# (ADR 0189 §7 pre-registered them; ADR 0240 builds them).  `G0`/`G0h`/`G1` are `S0`/`S0h`/`S1` with ONE
# thing changed — the MAGNITUDE they are asked for, not who they pick.
#   Why.  An `S*` arm's budget is `(1 - rho)*n`, and rho is a NEXT-YEAR COUNT ratio, so what it spends is
#   the NET count change `K - R`.  The flux that moves biomass is the GROSS `K`, and because establishment
#   is deferred to the C (`ESTAB_C`) the recruits `R` arrive regardless.  Measured on FIT's own roster over
#   12 cells (ADR 0188 §4): gross kills 5.65/5.96 %/yr against a spendable budget of 0.78-1.02 %/yr, i.e.
#   6.4-7.6x short, with FIT's NON-NEGOTIABLE deaths alone overdrawing the whole budget 4.1-5.3x.  That is
#   why the discretionary kill rate lands at 0.5-0.6 %/yr against FIT's 2.05 (ADR 0187) and the biomass runs
#   +90 % (ADR 0186) while the COUNT is on target.
#   What changes.  The budget becomes `(n - target) + Rhat` with `Rhat = #{stems of age == 1}` — last year's
#   recruit cohort, countable off the roster already in hand, EXACTLY (29 700 of 29 700 patch-years, ADR
#   0189 §2, skill trap 5j), so this needs no dump-format change and no interface request to line M.  It is
#   spent from a per-patch RUNNING ACCOUNT rather than rectified per year: a year the count model says
#   "grow" REPAYS an earlier overspend instead of being clipped to zero, and a forced overshoot suppresses
#   later kills.  ⚠ The account is not a refinement — rectifying per patch-year is CONVEX, so an
#   unbiased-but-noisy budget OVER-kills (total mortality +17 % on FIT's stand, +66 % on the arm's own,
#   roster to 0.62x/0.11x over the ssp370 leg), which the account fixes (5.817 vs FIT's 5.961 %/yr, roster
#   1.70x).  Reference arithmetic: `capacity()`'s `_acct` branch in scripts/diagnose_rung2_gross_budget_lag.py.
#   ⚠ Expect the criterion to be MARGINAL, and that is PRE-REGISTERED, not a surprise: the same panel puts
#   the accounting form's discretionary capacity on the arm's OWN stand at 1.493 ± 0.180 %/yr against a
#   1.5 %/yr criterion — 0.04 sigma BELOW it (ADR 0189 §7, item 17).  And capacity is NECESSARY, NOT
#   SUFFICIENT: it is what the operator could afford, not what it realizes, so 0189's numbers are
#   "capacity" and only an arm's own are a "rate".
#   `G0` keeps `S0`'s derivable self-test: the draw is uniform at `1 - b/n`, so `E[n_kill] = b` exactly.
#
# THE `H*` ARMS — NO COUNT TARGET AT ALL: FIT's OWN PER-TREE HAZARD APPLIED AS A *RATE* (ADR 0241 §7)
# ------------------------------------------------------------------------------------------------------
# ADR 0241 retired the learned count model from the MORTALITY path, and not on a tuning argument: a kill
# budget is a DIFFERENCE of counts, so the count model's error is multiplied by the level-to-flux ratio
# (~17 here).  The precision that would be needed is 1.13/1.18 % per patch-year, against an irreducible
# realisation floor of 4.1/4.6 % (FIT's own per-stem Bernoulli), a cell-year conditioning floor of 39-42 %,
# and an INTEGER ATOM larger than the tolerance itself (FIT kills 1.22/1.03 stems per patch-year, so a
# +-20 % budget is +-0.2 of a stem).  No learner and no budget form escapes that.  So these arms form no
# budget at all:
#
#   H1   f_i = 1 - mort_i            every stem faces its own hazard.  No target, no budget, no account,
#        no `rho >= 1` gate.  This is `survival_prob` from the SHIPPED `TraitMortality` — i.e. exactly the
#        Bernoulli LPJmL-FIT itself realizes (`mortality_tree_ind.c:145`), which is why ADR 0189's
#        `perfect` arm reproduces FIT's gross AND net kills at |diff| 0.0000 and ADR 0183 measured the
#        port at |dhazard| 5e-18 with certain-set recall = precision = 1.0000.
#   H0   f_i = 1 - hbar              the UNIFORM-RATE control: hbar = sum(nind*mort)/sum(nind), so the
#        EXPECTED removed density is identical to H1's, stem for stem of total, with every per-stem
#        ordering removed.
#   H0h  f_i = 0 for a certain stem (`mort >= 1`), else `1 - hbar_disc` over the non-certain stems.
#        The decomposition control, the same role S0h plays for S1: `H0h - H0` is worth honouring the
#        deaths FIT had already settled, `H1 - H0h` is worth per-stem ordering among the rest.
#
# ⚠ ALL THREE HAVE THE SAME EXPECTED GROSS FLUX ON THE SAME ROSTER, EXACTLY.  `sum(nind_i*(1-f_i))` is
#   `sum(nind_i*mort_i)` for each of them (for H0h because the certain stems contribute their own `nind*1`
#   and the weighted mean over the rest is taken over exactly the rest).  That is a DERIVABLE a-priori
#   self-test — `kill_exp` must equal `haz_exp` row by row for all three — and it is what makes the
#   decomposition clean: on a given stand they differ ONLY in who is picked, never in how many.
#   ⚠⚠ IT IS A PER-PATCH-YEAR IDENTITY AND *NOT* A LEG-TOTAL ONE, because the stands diverge — skill trap
#   5 in a new place.  Measured at Hainich historic: H0's leg total `haz_exp` is 4.915 against H1's 2.585,
#   1.9x, because H0 spares certain-death stems that then linger at `mort ~ 1` and inflate hbar every year
#   after.  So NEVER read a leg-summed flux difference between these arms as an operator difference; the
#   identity to gate is row by row, and the leg totals are a RESULT.
#
# ⚠ WHAT AN `H*` NUMBER IS AND IS NOT.  In rung 2 the hazard reads FIT's own stress integrals through the
#   rendezvous, so these arms measure the CEILING: what an EXACT hazard buys, given inputs the standalone
#   emulator does not have offline (ADR 0049 item 4).  They do not by themselves close the standalone
#   emulator.  Say which of the two any number is on.
#
# ⚠ `rho`/`target` ARE STILL COMPUTED AND LOGGED FOR AN `H*` ARM, AND ARE NOT CONSULTED.  The count model
#   still runs (it costs nothing beside the rendezvous, it keeps the log schema identical for every
#   scorer, and it is the free counterfactual "what would the retired budget have asked for here").  A
#   reader must not infer from a populated `rho` column that an `H*` arm used it: `rho_eff` is 1.0 and the
#   operator never forms a budget.  The count model's OTHER consumers are untouched by ADR 0241.
#
# WHAT THE C STILL OWNS in every arm here: turnover, allocation, growth, fire, the non-demographic hard
# kills (negative pools, `isneg_tree`, bioclimatic `survive()`, `cut_year`), AND establishment.  So every
# number this harness produces is a MORTALITY result on a real stand; when S2 is wired, only 4 of the 7
# sampled recruit trait axes are substitutable (`emax`/`k_root`/`beta_2` stay the C's) and the recruits half
# carries a structural replay floor of 0.907 (ADR 0121).
#
# THE FEATURE ROW IS BUILT BY THE SHIPPED FUNCTION, NOT BY A COPY.  `flux_feature_vector` and
# `DRF.predict` are reached as private names off the package, exactly as the arm-C harness reaches
# `TraitMortality.mortality_hazard`.  A second copy of the row assembly would make this file the thing being
# measured (the ADR-0023 train/inference-shift trap in a new place).
#
# TWO BASES ARE LOGGED SIDE BY SIDE, DELIBERATELY (ADR 0060).  The shipped runtime recomputes
# hmean/hmax/agb/lai/fpc from its own allometry, while the TRAINING columns came off the C's own `ind`
# aggregates.  Both rows are written to the log (`runtime` vs `ctrain`), because the gap between them is a
# train/inference shift that already exists in the deployed emulator and must be measured rather than
# hidden by picking one.  The DRF is fed the RUNTIME row — that is what deployment does.
#
# THE >5 m CUT IS LOAD-BEARING.  The count model's target and its `n_prev` are trained on the `ind` table,
# whose writer emits only stems `height > 5 m` (`fwriteoutput_ind.c:84`).  The rung-2 roster carries every
# tree.  So the count features and the count target apply the same 5 m cut, while the THINNING acts on the
# whole roster.  Dropping the cut inflates `n_prev` by the sub-5 m cohort and biases rho low every year.
#
# USAGE (in the background of the same job as the substituted lpjml; see scripts/run_rung2_s_arm.sh)
#     julia --project=. scripts/rung2_s_demography_harness.jl --arm=S1 --apply-dir=DIR --cell=42490 \
#           [--drf=PATH] [--rcop=PATH] [--n-prev=roster|predict] [--seed=1] [--log=PATH] [--ready=PATH]

using Printf
using Random

using LPJmLFITEmulator
const EM = LPJmLFITEmulator
const TM = LPJmLFITEmulator.TraitMortality
const FD = LPJmLFITEmulator.FDiff
const DRF = LPJmLFITEmulator.DRF

const REPO = normpath(joinpath(@__DIR__, ".."))
const HEIGHT_MIN = 5.0        # fwriteoutput_ind.c:84 — the `ind` writer's emission cut
const NDAYYEAR = 365          # the model calendar; the divisor the `ind` writer applies to wscal_mean

# ── arguments ─────────────────────────────────────────────────────────────────────────────────────────
function parse_args(argv)
    opts = Dict{String, String}(
        "arm" => "S1",
        "apply_dir" => "",
        "cell" => "42490",
        "drf" => joinpath(REPO, "test/testitems/references/drf_forest_hainich.drf"),
        "rcop" => joinpath(REPO, "test/testitems/references/recruit_copula_hainich.rcop"),
        "cells_csv" => joinpath(REPO, "test/testitems/references/M_cells.csv"),
        # Per-YEAR boundary tail (scripts/build_rung2_boundary_series.py). REQUIRED for a scenario-pair
        # response arm; empty keeps the static registry tail so ADR 0176's arms reproduce byte-for-byte.
        "boundary_csv" => "",
        "n_prev" => "roster",
        "seed" => "1",
        "log" => "",
        "ready" => "",
        "max_idle" => "300",
        "poll" => "0.002",
    )
    for a in argv
        m = match(r"^--([a-z-_]+)=(.*)$", a)
        m === nothing && error("unrecognised argument '$a' (expected --key=value)")
        key = replace(m.captures[1], '-' => '_')
        haskey(opts, key) || error("unknown option --$(m.captures[1])")
        opts[key] = m.captures[2]
    end
    opts["arm"] in ("S0", "S0h", "S1", "NP", "G0", "G0h", "G1", "H0", "H0h", "H1") || error(
        "--arm must be S0, S0h, S1, NP, one of the gross-budget arms G0, G0h, G1, or one of the " *
            "RATE arms H0, H0h, H1 (got '$(opts["arm"])')"
    )
    opts["n_prev"] in ("roster", "predict") ||
        error("--n-prev must be roster or predict (got '$(opts["n_prev"])')")
    isempty(opts["apply_dir"]) && error("--apply-dir is required")
    return opts
end

# ── the per-cell slow boundary tail, off the committed registry ────────────────────────────────────────
"""
    cell_boundary(csv, cell) -> Vector{Float64}

The four-column slow bioclimatic tail (`eco_diag_gdd_5`, `tas_cold_month`, `soil_depth`, `co2`) in the
runtime order, read from `test/testitems/references/M_cells.csv` — the committed per-cell registry
`scripts/extract_cell_slow_init.py` writes, which is version-coupled to the pinned artifact.

Read, never transcribed: a second copy of a per-cell constant is ADR 0031's failure mode.
"""
function cell_boundary(csv::AbstractString, cell::Int)
    hdr = String[]
    for line in eachline(csv)
        startswith(line, "#") && continue
        if isempty(hdr)
            hdr = String.(split(strip(line), ','))
            continue
        end
        f = String.(split(strip(line), ','))
        idx(n) = findfirst(==(n), hdr)
        parse(Int, f[idx("cell")]) == cell || continue
        return Float64[
            parse(Float64, f[idx(c)]) for
                c in ("eco_diag_gdd_5", "tas_cold_month", "soil_depth", "co2")
        ]
    end
    return error("cell $cell not found in $csv")
end

# ── the TRANSIENT per-year boundary series (ADR 0026), keyed by YEAR ───────────────────────────────────
"""
    boundary_series(csv) -> Dict{Int, Vector{Float64}}

Per-simulated-year slow boundary tails, read from a CSV built by
`scripts/build_rung2_boundary_series.py` (`Year,eco_diag_gdd_5,tas_cold_month,soil_depth,co2`).

WHY THIS IS REQUIRED FOR A SCENARIO-PAIR (RESPONSE) ARM, AND OPTIONAL OTHERWISE.  `cell_boundary` above
returns the committed registry's tail, which is the per-cell 2000-2019 CLIMATOLOGY — one frozen vector.
Feeding that to every year of an ssp370 leg shows the count model PRESENT-DAY climate for all 81 future
years, so the historic and future legs differ only through the roster and the measured warming response is
driven to ~0 BY CONSTRUCTION.  That is an unfalsifiable experiment, not a null result.

The shipped runtime does not have the defect: `FluxDrivenSlowEmulator.boundary_series` +
`reconcile_demography!` advance `s.boundary` to the year's row before the feature row is built (ADR 0026),
and the pooled production forest was TRAINED on exactly that per-(Cell,Year) treatment
(`BOUNDARY_WINDOW=20`).  Using it here is what keeps train and inference on one basis (ADR 0023).

KEYED BY YEAR, NOT BY ROW POSITION: the C's first simulated year is a property of the restart file, so a
positional series would silently offset the whole climate channel by however many years the two disagree.
Unset (`--boundary-csv=`) the harness keeps the static registry tail, so every ADR-0176 arm reproduces
byte-for-byte (guardrail 4).
"""
function boundary_series(csv::AbstractString)
    series = Dict{Int, Vector{Float64}}()
    hdr = String[]
    want = ("eco_diag_gdd_5", "tas_cold_month", "soil_depth", "co2")
    for line in eachline(csv)
        (isempty(strip(line)) || startswith(line, "#")) && continue
        if isempty(hdr)
            hdr = String.(split(strip(line), ','))
            for c in ("Year", want...)
                c in hdr || error("boundary series $csv has no '$c' column (found $(hdr))")
            end
            continue
        end
        f = String.(split(strip(line), ','))
        idx(n) = findfirst(==(n), hdr)
        year = parse(Int, f[idx("Year")])
        haskey(series, year) && error("duplicate Year $year in boundary series $csv")
        series[year] = Float64[parse(Float64, f[idx(c)]) for c in want]
    end
    isempty(series) && error("boundary series $csv has no data rows")
    return series
end

# ── the roster reader ─────────────────────────────────────────────────────────────────────────────────
struct Tree
    pft_id::Int
    treeidx::Int
    nind::Float64
    height::Float64
    sla::Float64
    wooddens::Float64
    d95max::Float64
    minwscal::Float64
    crownarea::Float64
    leaf_c::Float64
    sapwood_c::Float64
    heartwood_c::Float64
    root_c::Float64
    sapwood_bg_c::Float64
    anpp::Float64
    wscal_mean::Float64
    age::Int              # the `grow` roster's POST-increment age
    fpc_c::Float64        # the C's own fpc, for the ctrain basis only — never an input to the operator
    agb_c::Float64        # the C's own agb  (leaf + sapwood + heartwood), likewise
    mort::Float64         # the ported hazard on this year's state
    hard::Symbol
end

"""
    read_request(path) -> (year, patch, trees, rootzone_w)

Parse one rendezvous request: the `grow`-phase roster plus the `P` record's root-zone soil moisture.

`grow` is mandatory. On the pre-ADR-0123 `pre` rendezvous the roster's `bm_inc_counter` was a year stale,
which INVERTED the sign of the wood-density selection differential (ADR 0122/0123) — so a silently accepted
`pre` request would yield a plausible, wrong answer. `rootzone_w` is mandatory too: without it the
`soilmoist` feature would have to be proxied, and it is one of the four flux drivers (ADR 0035).
"""
function read_request(path::AbstractString)
    tcols = Dict{String, Int}()
    pcols = Dict{String, Int}()
    trees = Tree[]
    year = -1
    patch = -1
    rzw = NaN
    for line in eachline(path)
        if startswith(line, "#H T ")
            tcols = Dict(n => i for (i, n) in enumerate(split(line)[3:end]))
            continue
        elseif startswith(line, "#H P ")
            pcols = Dict(n => i for (i, n) in enumerate(split(line)[3:end]))
            continue
        end
        isempty(line) && continue
        if line[1] == 'P'
            isempty(pcols) && error("$path: a P record before its '#H P' header")
            f = split(line)[2:end]
            f[pcols["phase"]] == "grow" || continue
            haskey(pcols, "rootzone_w") || error(
                "$path has no `rootzone_w` column: this binary predates the v6 hook " *
                    "(patches/lpjmlfit_rung2_hook_v6.patch). The `soilmoist` flux driver cannot be built " *
                    "from the roster without it, and proxying it is the ADR-0035 trap. Refusing to serve."
            )
            rzw = parse(Float64, f[pcols["rootzone_w"]])
            # ⚠ THE (year, patch) IDENTITY COMES FROM THE `P` RECORD, NOT FROM THE TREES — an EMPTY
            #   patch emits no `T` record at all (skill trap 7) and used to leave both at their
            #   sentinel −1, so the answer was written to `rsp_..._y-0001_p-01` while the C waited for
            #   the real name and died 600 s later on ERROR043 `no answer for year <Y> patch <P>`.
            #   A deadlock, from one absent line. It stayed latent because no `S*` arm ever emptied a
            #   patch; the ADR-0240 gross-budget arms do (ADR 0240 §6).
            year = parse(Int, f[pcols["year"]])
            patch = parse(Int, f[pcols["patch"]])
            continue
        end
        line[1] == 'T' || continue
        isempty(tcols) && error("$path: a T record before its '#H T' header")
        f = split(line)[2:end]
        gs(n) = f[tcols[n]]
        gf(n) = parse(Float64, gs(n))
        gi(n) = parse(Int, gs(n))
        gs("phase") == "grow" || error(
            "$path: rendezvous phase is '$(gs("phase"))', not 'grow'. This binary predates the " *
                "rendezvous move behind the growth loop (ADR 0123); its roster is a year stale in " *
                "bm_inc_counter, which INVERTS the trait selection differential. Refusing to serve it."
        )
        # The trees carry the same (year, patch); disagreeing with the `P` record would mean two
        # patch-years in one request file, so check rather than overwrite.
        (gi("year"), gi("patch")) == (year, patch) || error(
            "$path: a T record says (year $(gi("year")), patch $(gi("patch"))) but the P record says " *
                "($year, $patch) — one request file must be exactly one patch-year."
        )
        p = TM.pft_mort_params(gi("pft_id"))
        h = TM.mortality_hazard(
            p; wooddens = gf("wooddens"), sla = gf("sla"), age = gi("age") - 1,
            bm_delta = gf("bm_delta"), leafarea = gf("leafarea_real"), leaf_c = gf("leaf_c"),
            water_stress = gf("water_stress"), temp_stress = gf("temp_stress"),
            bm_inc_counter = gi("bm_inc_counter")
        )
        push!(
            trees, Tree(
                gi("pft_id"), gi("treeidx"), gf("nind"), gf("height"), gf("sla"), gf("wooddens"),
                gf("D95max"), gf("minwscal"), gf("crownarea"), gf("leaf_c"), gf("sapwood_c"),
                gf("heartwood_c"), gf("root_c"), gf("sapwood_bg_c"), gf("anpp"), gf("wscal_mean"),
                gi("age"), gf("fpc"),
                gf("leaf_c") + gf("sapwood_c") + gf("heartwood_c") - gf("debt_c"),
                h.total, h.hard_kill
            )
        )
    end
    isnan(rzw) && error("$path: no `grow`-phase P record, so no rootzone_w")
    # The response FILENAME is built from these two, so a sentinel value here is a silent deadlock
    # rather than an error: the C would wait 600 s for a name that is never written. Fail loudly.
    (year >= 0 && patch >= 0) || error(
        "$path: parsed (year $year, patch $patch) — the request carries no `grow`-phase identity, and " *
            "answering it would write the response under a name the C is not waiting for."
    )
    sort!(trees, by = t -> (t.pft_id, t.treeidx))
    return year, patch, trees, rzw
end

# ── the emulator-facing view of the roster ────────────────────────────────────────────────────────────
"""
    pools_of(trees) -> Vector{FDiff.TreePools}

A `FDiff.TreePools` per tree, so the shipped feature assembly can be called on the real stand.

⚠ **Call this on the EMITTED (>5 m) subset when building the feature row.** Every one of the six state
columns in the training table is an aggregate over the `ind` table's rows, and that writer emits only stems
above 5 m (`fwriteoutput_ind.c:84`) — so a row built on the C's FULL roster is on a different population
than the forest was trained on. Measured at Hainich: including the sub-5 m cohort halves `age_mean` (31.9
against 74.5 at 2019, a persistent factor of ~1.9), because saplings are young and the runtime mean is
nind-weighted. `agb` happens to survive (5224 vs 5211, 0.25 %) since young stems carry little carbon, which
is exactly why this is the kind of error that shows up in one feature and not its neighbours.

The thinning still acts on the WHOLE roster — the C owns every tree, and a sub-5 m stem can still be killed.
Only the feature row and the count target are on the emitted population.
"""
pools_of(trees::Vector{Tree}) = [
    FD.TreePools{Float64}(
            t.leaf_c, t.sapwood_c, t.heartwood_c, t.root_c, t.sapwood_bg_c,
            t.height, t.crownarea, t.nind, t.sla, t.wooddens, t.d95max, t.minwscal, false
        ) for t in trees
]

"""
    flux_drivers(trees) -> (bm_inc_cell, growth_eff, water_stress)

The three annual integrals, on the SAME definitions `scripts/build_slow_runtime_table.py` used for the
training columns, restricted to the emitted (>5 m) stem population:

  bm_inc_cell  = sum(npp)                                      (`anpp`, the `ind` table's `npp`)
  growth_eff   = lai > 0 ? sum(npp | npp>0 & height>0) / lai : 0
  water_stress = 1 - mean(wscal_mean)                           (unweighted mean over stems)

`lai` here is the same `sum(leaf_c*sla*nind)` the runtime forms, which is algebraically identical to the
training table's per-patch reconstruction `sum(LAI*fpc_ind/(1-exp(-k*LAI)))` (ADR 0035): `fpc_ind` divided
by its own saturation factor is `crownarea*nind`, and `LAI*crownarea = leaf_c*sla`. So the two bases agree
here exactly, which is why only this one is formed.
"""
function flux_drivers(trees::Vector{Tree})
    emitted = [t for t in trees if t.height > HEIGHT_MIN]
    isempty(emitted) && return (0.0, 0.0, 0.0)
    bm_inc = sum(t.anpp for t in emitted)
    applied = sum((t.anpp > 0 && t.height > 0) ? t.anpp : 0.0 for t in emitted)
    lai = sum(t.leaf_c * t.sla * t.nind for t in emitted)
    ge = lai > 0 ? applied / lai : 0.0
    # ⚠ THE DUMP'S `wscal_mean` IS THE RAW DAILY ACCUMULATOR, NOT the `ind` table's column.
    # `water_stressed.c:140` adds to `pft->wscal_mean` every day and `fwriteoutput_ind.c:119` divides by
    # NDAYYEAR on the way out; the rung-2 hook writes the struct field directly, so it arrives ~365x too
    # large.  Undivided it gives `water_stress = 1 - 365 = -364` on an unstressed year, which is how this
    # was caught — but a reader that silently accepted it would feed the count model a feature 365x outside
    # its training range.  Divide here, once, at the boundary.
    ws = 1.0 - sum(t.wscal_mean for t in emitted) / (length(emitted) * NDAYYEAR)
    return (bm_inc, ge, ws)
end

"""
    ctrain_state(trees) -> (hmean, hmax, agb, lai, fpc, age_mean)

The same six state columns on the C's OWN aggregates over the emitted (>5 m) stems — the TRAINING basis,
logged beside the runtime row so the gap between them is measured rather than assumed away (ADR 0060).

Two of these are only approximately the training column, and the approximation is stated rather than
hidden:

* **`agb`.** The `ind` column is `agb_tree` = `(agb_tree_sum(ind) − debt + excess_carbon)·nind −
  turn_litt.leaf.carbon` (`src/tree/agb_tree.c:25`), i.e. **already per m²** — so the training table's
  `sum(agb)` and the runtime's `agb_ind·nind` are the SAME basis and there is no scale mismatch. But
  `excess_carbon` and `turn_litt` are not dumped, so this reconstruction is
  `(leaf + sapwood + heartwood − debt)·nind` and will sit slightly above the true column.
* **`age_mean`.** The training column is `(Age − 1).mean()` over the patch's `ind` rows: **unweighted, and
  over emitted stems only**. The runtime's is `_mean_age_weighted`: **nind-weighted, over every cohort**.
  Those are different definitions, not different roundings, and this pair is the way to size the difference.
"""
function ctrain_state(trees::Vector{Tree})
    emitted = [t for t in trees if t.height > HEIGHT_MIN]
    isempty(emitted) && return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    fpcsum = sum(t.fpc_c for t in emitted)
    hmean = fpcsum > 0 ? sum(t.height * t.fpc_c for t in emitted) / fpcsum : 0.0
    hmax = maximum(t.height for t in emitted)
    agb = sum(t.agb_c * t.nind for t in emitted)
    lai = sum(t.leaf_c * t.sla * t.nind for t in emitted)
    age = sum(t.age - 1 for t in emitted) / length(emitted)
    return (hmean, hmax, agb, lai, min(fpcsum, 1.0), age)
end

"Stems per patch on the count model's own basis: the >5 m population, `Σ nind · patch_area`."
n_emitted(trees::Vector{Tree}, patch_area::Float64) =
    sum(t.nind for t in trees if t.height > HEIGHT_MIN; init = 0.0) * patch_area

# ── main loop ─────────────────────────────────────────────────────────────────────────────────────────
const REQ_RE = r"req_r(\d+)_y(\d+)_p(\d+)\.ready$"

function main(argv)
    opts = parse_args(argv)
    arm = opts["arm"]
    apply_dir = opts["apply_dir"]
    seed = parse(Int, opts["seed"])
    cell = parse(Int, opts["cell"])
    max_idle = parse(Float64, opts["max_idle"])
    poll = parse(Float64, opts["poll"])
    patch_area = 225.0                                  # param.patcharea, par/lpjparam_fit.js
    mkpath(apply_dir)
    log_path = isempty(opts["log"]) ? joinpath(apply_dir, "s_arm_log.txt") : opts["log"]

    forest = DRF.load_forest(opts["drf"])
    bseries = isempty(opts["boundary_csv"]) ? nothing : boundary_series(opts["boundary_csv"])
    # The STATIC registry tail is read ONLY when there is no per-year series.
    #
    # ⚠ It MUST NOT be read unconditionally: `M_cells.csv` is the five-cell coupled-driver registry, so
    # `cell_boundary` ERRORS on any other cell — which killed every arm at the 10 non-canonical cells of the
    # response set the instant the harness started, before the C's first rendezvous ("FATAL: harness died
    # before becoming ready"). The series already carries the tail for every cell and every year, so when
    # one is given the registry is not needed at all, and the width check below uses the series itself.
    boundary = bseries === nothing ? cell_boundary(opts["cells_csv"], cell) :
        bseries[minimum(keys(bseries))]
    allom = EM.TreeAllometry{Float64}()   # the shipped default; the roster's own crown areas are the C's

    println("rung-2 LINE-S demography harness, arm $arm")
    println("  count model : ", opts["drf"], "  (", forest.nfeat, " features)")
    println("  recruits    : left to the C (ESTAB_C) in every arm here")
    if bseries === nothing
        println("  boundary    : STATIC (present-day climatology) cell $cell -> ", boundary)
        println("                ⚠ a scenario-pair RESPONSE arm must pass --boundary-csv, or the future")
        println("                  leg sees present-day climate and the response is ~0 by construction.")
    else
        yrs = sort(collect(keys(bseries)))
        println(
            "  boundary    : TRANSIENT (ADR 0026) ", opts["boundary_csv"],
            "  years $(first(yrs))-$(last(yrs)) (", length(yrs), ")"
        )
        println("                first ", bseries[first(yrs)], "\n                last  ", bseries[last(yrs)])
        # Every year must carry the SAME tail width, or one year would silently build a shorter feature
        # row than the forest expects. (The width itself is checked against the artifact below.)
        let w = length(bseries[first(yrs)])
            all(length(bseries[y]) == w for y in yrs) || error(
                "the boundary series has a ragged tail width across years — every row must have $w columns"
            )
        end
    end
    println(
        "  n_prev      : ", opts["n_prev"], opts["n_prev"] == "roster" ?
            "  (the stand's own previous count — ADR 0175)" : "  (the model's own previous prediction)"
    )
    println("  seed        : ", seed)
    println("  apply dir   : ", apply_dir)
    flush(stdout)

    forest.nfeat == 11 + length(boundary) || error(
        "artifact/boundary width mismatch: the forest wants $(forest.nfeat) features but 11 head + " *
            "$(length(boundary)) boundary columns give $(11 + length(boundary)). The boundary tail is " *
            "part of the pinned artifact's contract (ADR 0020 §6)."
    )

    log = open(log_path, "w")
    println(
        log,
        # The four `G*` columns and the fifth `H*` one are APPENDED at the end on purpose: every consumer
        # of this file parses positions off this header line rather than hardcoding them (skill trap 1),
        # so an additive column cannot move an existing one.  They are written for every arm — NaN/0
        # where the arm has no account — so the schema does not depend on the arm.
        "#H L year patch n_tree n_emit n_prev target rho theta shortfall n_kill n_recruit " *
            "bm_inc growth_eff water_stress soilmoist " *
            "hmean_rt hmax_rt agb_rt lai_rt fpc_rt age_rt " *
            "hmean_c hmax_c agb_c lai_c fpc_c age_c " *
            "n_age1 budget rho_eff acct haz_exp kill_nind kill_exp kill_var"
    )
    isempty(opts["ready"]) || close(open(opts["ready"], "w"))

    # `n_prev` per patch, carried across years.  In `roster` mode it is overwritten from the live stand
    # every year and this dictionary is only a fallback for the FIRST year of each patch, where there is no
    # previous roster; in `predict` mode it is the shipped recursion and this IS the state.
    n_prev = Dict{Int, Float64}()

    # The `G*` arms' per-patch KILL ACCOUNT (ADR 0240), in stems.  Starts empty, i.e. at 0 for every patch,
    # and each leg is its own run — so an account never carries across the scenario pair, exactly as the
    # feasibility panel modelled it.  Left untouched (and unlogged as an account) by the `S*`/`NP` arms.
    acct = Dict{Int, Float64}()

    served = Set{String}()
    clamped_warned = Set{Int}()          # years reported as outside the boundary series (report once each)
    last_seen = time()
    nserved = 0
    while time() - last_seen < max_idle
        hits = 0
        for ready in sort(filter(f -> occursin(REQ_RE, f), readdir(apply_dir; join = true)))
            (ready in served) && continue
            m = match(REQ_RE, basename(ready))
            rank = parse(Int, m.captures[1])
            req_txt = ready[1:(end - length(".ready"))] * ".txt"
            isfile(req_txt) || continue
            year, patch, trees, rzw = read_request(req_txt)

            # the FULL roster (what the thinning acts on) and the EMITTED subset (what the count model was
            # trained on) are deliberately separate — see `pools_of`
            pools = pools_of(trees)
            emitted = [t for t in trees if t.height > HEIGHT_MIN]
            pools_emit = pools_of(emitted)
            n_emit = n_emitted(trees, patch_area)
            bm_inc, ge, ws = flux_drivers(trees)

            # `n_prev`: the stand's own previous count (the fix), or the model's previous prediction (the
            # shipped recursion).  The first year of a patch has no previous roster either way, so it seeds
            # from the live stand — a one-step start, identical in both modes, and it is the ONLY year in
            # which `predict` mode is not the recursion.
            npv = if opts["n_prev"] == "roster"
                n_emit
            else
                get(n_prev, patch, n_emit)
            end

            # ── the RUNTIME feature row, assembled by the SHIPPED function on the real stand.  `state`/
            #    `soil` exist only to carry `soilmoist` through `root_zone_soilmoist`, which reads
            #    `state.w` weighted by `soil.whcs` over the top 3 layers — equal weights on a constant `w`
            #    return that `w` exactly, so the feature equals the C's own root-zone fraction. ──
            state = EM.SharedState{Float64}(w = fill(rzw, EM.NSOILLAYER))
            soil = FD.SoilColumn{Float64}(
                fill(1.0, 3), fill(1 / 3, 3), fill(1 / 3, 3), 0.0, fill(1000.0, 3)
            )
            grow = (bm_inc_cell = bm_inc, growth_eff = ge, water_stress = ws)
            ages = Float64[t.age - 1 for t in emitted]
            # THIS year's bioclimate. Mirrors `reconcile_demography!`'s ADR-0026 treatment, including its
            # clamp: a year outside the series reuses the nearest end row rather than failing a live run,
            # but it is reported once because the usual cause is a series built for the other scenario.
            byear = if bseries === nothing
                boundary
            elseif haskey(bseries, year)
                bseries[year]
            else
                yrs = sort(collect(keys(bseries)))
                yc = clamp(year, first(yrs), last(yrs))
                if !(year in clamped_warned)
                    push!(clamped_warned, year)
                    println(
                        "  ⚠ year $year is outside the boundary series $(first(yrs))-$(last(yrs)); " *
                            "clamped to $yc (ADR 0026 semantics)"
                    )
                    flush(stdout)
                end
                bseries[yc]
            end
            feats = EM.flux_feature_vector(byear, ages, npv, grow, pools_emit, state, allom, soil)
            target = DRF.predict(forest, feats)

            ρ = arm == "NP" ? 1.0 : clamp(target / (npv + 1.0e-12), 0.7, 1.3)

            # ── the KILL BUDGET: what the operator is ASKED for, before anyone picks who (ADR 0240) ──
            # `ρ` above is a next-year COUNT ratio, so an `S*` arm spends the NET change `K - R`.  A `G*`
            # arm spends the GROSS budget from a per-patch running account and hands the SAME operators a
            # different magnitude:
            #
            #     acct += (1 - ρ)·n_tree + R̂ ,  R̂ = #{age == 1}       the gross increment
            #     b     = clamp(acct, 0, n_tree)                        what it may spend THIS year
            #     ρ_dec = 1 - b/n_tree                                  the fraction the operators use
            #     acct -= n_kill                                        charge what was actually removed
            #
            # Three things are load-bearing and each was paid for.  (1) `R̂` is `age == 1` and not a model:
            # `age` at `grow` is POST-increment and establishment sets 0, so the count is EXACT (ADR 0189
            # §2).  (2) The account, not a per-year `max(0, ·)`: rectification makes a noisy budget over-kill
            # by convexity (ADR 0189 §6), and clamping `b` — not `acct` — is what lets a "grow" year repay.
            # (3) The charge is the REALIZED `n_kill`, not the modelled `max(b, n_cert)` the feasibility
            # panel used, because that is what the C actually removes; for `G0h`/`G1` the certain stems have
            # `f = 0` so a realized charge is ≥ `n_cert` automatically, and for `G0` it equals `b` in
            # expectation.  The C's own hard kills are outside the account in every arm — it cannot see them.
            #
            # ⚠ `ρ` stays in the log as the count model's own ratio; `ρ_dec` is what the draw ran at.  A
            # scorer that wants the realized thinning of a `G*` arm must read `rho_eff`, not `rho`.
            gross = arm in ("G0", "G0h", "G1")
            rate = arm in ("H0", "H0h", "H1")
            # Counted for EVERY arm, not only the ones that spend it: it costs nothing over a ~10-30 stem
            # roster, and logging 0 where it was simply not computed would be a wrong value dressed as a
            # measurement.  For an `S*` arm it is the free recruit observable the log did not carry before.
            n_age1 = count(t -> t.age == 1, trees)
            # FIT's OWN expected gross removal on this patch-year's roster, `Σ nind·mort` — the flux the
            # `H*` arms are built to realize and the reference flux every other arm is short of. Logged
            # for EVERY arm because it is a property of the roster, not of the operator (so an `S*` leg
            # gets the comparison for free), and because it is the derivable a-priori self-test for the
            # rate arms: all three have this exact expected removed density, so realized/`haz_exp` must
            # come out 1.00 for each.
            haz_exp = sum(t.nind * t.mort for t in trees; init = 0.0)
            # ⚠ NOT 1.0 and NOT ρ: a rate arm forms no thinning ratio at all, and printing one would be a
            # missing measurement dressed as a measured value (ADR 0240's own lesson).
            ρ_dec = rate ? NaN : ρ
            budget = NaN
            if gross
                a = get(acct, patch, 0.0) + (1.0 - ρ) * length(trees) + n_age1
                budget = clamp(a, 0.0, Float64(length(trees)))
                acct[patch] = a
                ρ_dec = isempty(trees) ? 1.0 : 1.0 - budget / length(trees)
            end

            # ── the decision ──
            # Every arm below reads `ρ_dec`, which IS `ρ` for the `S*`/`NP` arms — so those arms are
            # byte-identical to the pre-0240 harness by construction, not by inspection (guardrail 4).
            #
            # ⚠ THE GATE IS PART OF THE COUNT-BUDGET ARCHITECTURE, SO A RATE ARM MUST NOT INHERIT IT.
            # `ρ_dec < 1.0` says "act only in a year the count model asks the stand to shrink", which left
            # 42–46 % of patch-years with an EMPTY kill list — and on such a year the certain deaths were
            # spared too (ADR 0188 §3, skill trap 5l). An `H*` arm has no target to be gated on, so it
            # enters the block on every non-empty patch-year; the log's `rho_eff` stays 1.0 to say so.
            kills = Tuple{Int, Int}[]
            θ = NaN
            shortfall = 0.0
            # The arm's OWN implied removal `Σ nind·(1−f)` and the EXACT variance of its draw
            # `Σ nind²·f(1−f)`, both accumulated from the `f` the arm actually used. They are 0 where no
            # draw happens, and that is a measurement, not a gap: no draw removes nothing, with certainty.
            # ⚠ These make the realized-vs-implied self-test EXACT for every arm, σ included — ADR 0188's
            # `1.004 ± 0.009` had to hand-roll its SE from a uniform-draw assumption that only `S0` meets,
            # and ADR 0187 §5f is the standing instruction to derive the sampling SE before choosing a
            # tolerance. Cheap here, impossible offline.
            kill_exp = 0.0
            kill_var = 0.0
            rng = Xoshiro(hash((seed, year, patch)))
            if !isempty(trees) && (rate || ρ_dec < 1.0)
                nind = [t.nind for t in trees]
                n_now = sum(nind)
                f = Vector{Float64}(undef, length(trees))
                if rate
                    # ── ADR 0241 §7: FIT's own per-tree hazard as a RATE. No target is read here. ──
                    haz = [t.mort for t in trees]
                    if arm == "H1"
                        for i in eachindex(trees)
                            f[i] = 1.0 - haz[i]
                        end
                    elseif arm == "H0"
                        # the nind-weighted mean hazard: identical EXPECTED removed density to H1's
                        # `Σ nind·mort`, with every per-stem ordering removed
                        h̄ = n_now <= 0.0 ? 0.0 :
                            sum(nind[i] * haz[i] for i in eachindex(trees)) / n_now
                        fill!(f, 1.0 - h̄)
                    else
                        # H0h — certain deaths honoured, the REST uniform at their own weighted mean
                        # hazard, so the total expected removal is again exactly `Σ nind·mort`
                        certain = [haz[i] >= 1.0 for i in eachindex(trees)]
                        n_free = sum(nind[i] for i in eachindex(trees) if !certain[i]; init = 0.0)
                        hsum = sum(
                            nind[i] * haz[i] for i in eachindex(trees) if !certain[i]; init = 0.0
                        )
                        h̄d = n_free <= 0.0 ? 0.0 : hsum / n_free
                        for i in eachindex(trees)
                            f[i] = certain[i] ? 0.0 : 1.0 - h̄d
                        end
                    end
                elseif arm == "S0" || arm == "NP" || arm == "G0"
                    fill!(f, ρ_dec)                               # the shipped uniform thinning
                elseif arm == "S0h" || arm == "G0h"
                    # THE DECOMPOSITION CONTROL (ADR 0176).  S1 beats S0 for two reasons at once and the
                    # audit cannot separate them: `f = (1-haz)^θ` is zero wherever FIT's own hazard is
                    # CERTAIN (`mort >= 1`), so S1 stops overriding deaths the C had already settled — and
                    # only on top of that does it order the survivors by trait.  S0 spares ~1 950 certain
                    # trees per run, S1 ~358.  This arm honours the certain deaths and then thins the REST
                    # uniformly, hitting the SAME count target, so `S0h - S0` is the interface effect and
                    # `S1 - S0h` is what trait ordering is actually worth.
                    certain = [t.mort >= 1.0 for t in trees]
                    n_cert = sum(nind[i] for i in eachindex(trees) if certain[i]; init = 0.0)
                    # the survivors the target still has room for, spread over the non-certain stems
                    n_free = n_now - n_cert
                    c = n_free <= 0.0 ? 0.0 : clamp(ρ_dec * n_now / n_free, 0.0, 1.0)
                    shortfall = ρ_dec * n_now < n_now - n_free ?
                        (n_now - n_free - ρ_dec * n_now) / n_now : 0.0
                    for i in eachindex(trees)
                        f[i] = certain[i] ? 0.0 : c
                    end
                else
                    haz = [t.mort for t in trees]
                    tp = [
                        FD.TreePools{Float64}(
                                1.0, 1.0, 1.0, 1.0, 0.0, 1.0, 1.0, t.nind, t.sla, t.wooddens, false
                            ) for t in trees
                    ]
                    θ, shortfall = EM._hazard_tilt(haz, tp, ρ_dec * n_now, n_now)
                    for i in eachindex(trees)
                        w = 1.0 - haz[i]
                        f[i] = w <= 0.0 ? 0.0 : w^θ
                    end
                end
                for i in eachindex(trees)
                    kill_exp += nind[i] * (1.0 - f[i])
                    kill_var += nind[i]^2 * f[i] * (1.0 - f[i])
                    rand(rng) > f[i] && push!(kills, (trees[i].pft_id, trees[i].treeidx))
                end
            end
            # The nominated stems' DENSITY, not their count — `n_kill` beside it is a count, and the
            # expected-flux identity above is stated on `Σ nind`, so without this column the derivable
            # self-test would have to ASSUME every stem in a patch carries the same `nind`. It does not
            # cost a dump scan to measure, so it is measured.
            killset = Set(kills)
            kill_nind = sum(
                t.nind for t in trees if (t.pft_id, t.treeidx) in killset; init = 0.0
            )
            # Charge the account with what was actually nominated — including 0 on a gated patch-year, where
            # the kill list is empty and so the certain deaths are spared too (harness's own comment below;
            # skill trap 5l).  An unspent budget therefore stays on the account and is available next year.
            gross && (acct[patch] -= length(kills))

            # ── the answer ──
            # The kill list IS the mortality answer, including when it is empty: with rho >= 1 the count
            # model says the stand grows, so S kills nobody and the C's own hazard is overridden to spare
            # everyone.  `MORT_C` is deliberately never served — deferring mortality back to the C would
            # make this not an S arm.  Establishment always defers (`ESTAB_C`), so `n_recruit` is 0 by
            # construction and this harness cannot be quoted on recruits.
            nrec = 0
            base = joinpath(apply_dir, @sprintf("rsp_r%04d_y%05d_p%03d", rank, year, patch))
            open(base * ".txt", "w") do fh
                println(fh, "# arm $arm, year $year patch $patch (n_prev=$(opts["n_prev"]), seed=$seed)")
                for (pft_id, treeidx) in kills
                    println(fh, "K $pft_id $treeidx")
                end
                println(fh, "ESTAB_C")
                println(fh, "END")
            end
            close(open(base * ".ready", "w"))

            hm, hx, ab, la, fp, ag = feats[5], feats[6], feats[7], feats[8], feats[9], feats[10]
            chm, chx, cab, cla, cfp, cag = ctrain_state(trees)
            # Written as a joined line, NOT a `@printf`: the row is 34 fields wide and `@printf` needs its
            # format as ONE string literal, so a concatenated format is a load-time `ArgumentError` — and
            # `Meta.parseall` does NOT catch it, because macro expansion happens after parsing. A
            # parse-check is not a load-check for this file.
            fields = Any[
                year, patch, length(trees), n_emit, npv, target, ρ, θ, shortfall,
                length(kills), nrec,
                bm_inc, ge, ws, rzw, hm, hx, ab, la, fp, ag,
                chm, chx, cab, cla, cfp, cag,
                n_age1, budget, ρ_dec, get(acct, patch, 0.0), haz_exp, kill_nind, kill_exp, kill_var,
            ]
            println(
                log,
                "L " * join((v isa Integer ? string(v) : repr(Float64(v)) for v in fields), " ")
            )
            flush(log)
            n_prev[patch] = target
            push!(served, ready)
            hits += 1
            nserved += 1
        end
        if hits > 0
            last_seen = time()
        else
            sleep(poll)
        end
    end
    close(log)
    @printf("harness: served %d patch-years, log -> %s\n", nserved, log_path)
    flush(stdout)
    return 0
end

# Guarded so this file can be `include`d for its DEFINITIONS without starting a rendezvous server.
# `Tree`, `pools_of`, `flux_drivers`, `n_emitted`, `HEIGHT_MIN` and `boundary_series` are the exact
# quantities the arms were actually run with, so an offline scorer that wants "the row this arm's stand
# would produce" must reach them HERE rather than re-deriving them — the same ADR-0023 rule that makes
# this file call `EM.flux_feature_vector` instead of assembling the row itself. A copy would make the
# copy the thing being measured. Reused by `scripts/diagnose_rung2_map_on_rec_stand.jl`.
if abspath(PROGRAM_FILE) == @__FILE__
    exit(main(ARGS))
end
