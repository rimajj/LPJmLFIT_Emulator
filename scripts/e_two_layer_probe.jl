#!/usr/bin/env julia
# =====================================================================================================
# e_two_layer_probe.jl — line E, milestone **E7**: does a PROGNOSTIC two-layer ground-heat column fix
# what ADR 0073 diagnosed, WITHOUT fitting a coefficient?
#
# THE HYPOTHESIS (falsifiable, stated before the run — guardrail 7 / `residual-diagnosis`).
# ADR 0073 measured the default ground-heat term `G = λ_g(T_skin − t_soil)` as the dominant nocturnal-H
# error: `λ_g = 7.0` is a diurnal-amplitude conductance applied to a τ=30 d EWMA of AIR temperature, so
# sd(`G_m`) runs 5–7× sd(`G_o`), and it concluded that fitting `λ_g ≈ 1.0` repairs the DAILY step while
# genuine sub-daily skill needs "a force-restore / two-layer soil scheme". This probe tests exactly that:
#
#   H1  With the MITgcm land-package constants (λ_soil 0.42, z 0.2/2.0 m, C_dry 1.13e6, C_w 4.2e6,
#       γ 0.3) and NOTHING fitted, the two-layer scheme at the daily step reproduces the observed daily
#       sd(G_o) 4.3–6.3 W/m² and recovers daily H R² comparable to the FITTED λ_g = 1.0 arm
#       (DE-Hai 0.64, AU-ASM 0.74).
#       FALSIFIED IF daily sd(G_m) > 10 W/m², or daily H R² < 0.3, at DE-Hai or AU-ASM.
#   H2  At the native SUB-DAILY step the column carries a real diurnal wave, so nocturnal H improves on
#       ADR 0073's floor (night R² −1.0…−5.6; the best any `g_a` in a 100× bracket reached was −0.06).
#       This is the claim ADR 0073 said needed a design change — it is NOT expected to reach R² > 0,
#       because `ε_obs` scatter alone (sd 36 W/m² at DE-Hai) is the size of the night H RMSE.
#
# THE THREE ARMS, all scored on the same rows:
#   A  default            λ_g = 7.0, EWMA t_soil        (must reproduce ADR 0073's published numbers)
#   B  fitted             λ_g = 1.0, EWMA t_soil        (must reproduce them too — the harness check)
#   C  E7 two-layer       enable_two_layer = true       (UNFITTED, prognostic; the new scheme)
#
# Arm C is driven through the REAL `solve!` — the production coupled path, state and all — not a
# re-implementation, so what is scored is what `run.jl` would run.
#
# Score H at **DE-Hai and AU-ASM only** (ADR 0073: AU-Tum/AU-Rob have ε_obs −62.3/−47.5 W/m² and cannot
# score a closing model's H at all); all four stay valid for T_skin.
#
# Env: DRIVE_DIR · SITES (default all) · OUT (report path)
# Usage:  scripts/sbatch_julia.sh E-e7probe --project=. scripts/e_two_layer_probe.jl
# =====================================================================================================

include(joinpath(@__DIR__, "e_seb_drive_common.jl"))

"""
Drive the closure STATEFULLY through the production `solve!`, one row at a time in calendar order, so the
opt-in two-layer soil column actually integrates. `dt_seconds` is the length of one row's step.

Non-finite forcing rows are recorded as `NaN` and are **skipped without advancing the column** — a single
NaN in the prognostic state would otherwise poison every later step irrecoverably.
"""
function run_site_stateful(tbl, meta; dt_seconds, t_soil0, params_kwargs...)
    h_can = parse(Float64, meta["canopy_height_m"])
    z_ref = parse(Float64, meta["reference_height_m"])
    z0m = parse(Float64, meta["z0m_m"])
    p = SEBParams{Float64}(; z_ref = z_ref, dt_seconds = dt_seconds, params_kwargs...)
    clo = SEBEnergyClosure{Float64}(; params = p, t_soil0 = t_soil0)
    st = SharedState()
    bc = SToE(albedo = 0.15, z0 = z0m, lai = 4.0, height = h_can)

    n = length(tbl["tair"])
    h_mod = fill(NaN, n); ts_mod = fill(NaN, n); rn_mod = fill(NaN, n)
    g_mod = fill(NaN, n); ga_mod = fill(NaN, n)
    t1 = fill(NaN, n); t2 = fill(NaN, n)
    for i in 1:n
        drivers = (
            tbl["swdown"][i], tbl["lwdown"][i], tbl["tair"][i], tbl["psurf"][i],
            tbl["wind"][i], tbl["albedo"][i], tbl["le_in"][i],
        )
        all(isfinite, drivers) || continue
        # the tower's OWN albedo varies per row, so rebuild the S→E boundary each step
        bc_i = SToE(albedo = tbl["albedo"][i], z0 = z0m, lai = 4.0, height = h_can)
        ff = FToE(
            le = tbl["le_in"][i], gpp = 0.0, npp = 0.0, rh = 0.0,
            firec = 0.0, flux_estabc = 0.0, ground_heat = 0.0,
        )
        forc = AtmForcing(
            swdown = tbl["swdown"][i], lwdown = tbl["lwdown"][i], tair = tbl["tair"][i],
            qair = 0.008, wind = tbl["wind"][i], psurf = tbl["psurf"][i], precip = 0.0, co2 = 400.0,
        )
        (atm, tof) = solve!(clo, st, ff, bc_i, forc)
        h_mod[i] = atm.h; ts_mod[i] = atm.t_skin; g_mod[i] = atm.g; ga_mod[i] = tof.g_a
        rn_mod[i] = atm.le + atm.h + atm.g          # Rn = LE + H + G, closed by construction
        t1[i] = clo.t_soil1; t2[i] = clo.t_soil2
    end
    return (h = h_mod, t_skin = ts_mod, rn = rn_mod, g = g_mod, ga = ga_mod, t1 = t1, t2 = t2, clo = clo)
end

"Published ADR 0073 daily-step H R² per site, for the harness check (arm A default / arm B λ_g=1.0)."
const ADR0073_DAILY_H_R2 = Dict(
    "DE-Hai" => (0.03, 0.64), "AU-ASM" => (0.33, 0.74),
    "AU-Tum" => (-0.48, -0.35), "AU-Rob" => (0.07, -0.17),
)
"Published ADR 0073 observed daily sd(G_o) per site [W/m²]."
const ADR0073_DAILY_SD_GOBS = Dict("DE-Hai" => 4.3, "AU-Tum" => 4.3, "AU-Rob" => 6.0, "AU-ASM" => 6.3)

function report_site(site, tbl, meta, out::Vector{String})
    add(s) = push!(out, s)
    dt_sub = 60.0 * parse(Int, meta["timestep_min"])
    t0 = nanmean(tbl["tair"])                    # mean annual temperature — the documented t_soil0 seed

    add("")
    add("="^104)
    add(
        "$site — $(meta["igbp"]), $(meta["rows"]) rows, $(meta["years"]), " *
            "$(meta["timestep_min"]) min · t_soil0 = $(round(t0, digits = 2)) K"
    )
    add("="^104)

    # ---- 1. the model's NATIVE DAILY step: the three arms -------------------------------------------
    (dtbl, dayidx) = aggregate_daily(tbl, meta)
    dA = run_site(dtbl, meta)                                        # λ_g = 7.0 (default)
    dB = run_site(dtbl, meta; lambda_g = 1.0)                        # λ_g = 1.0 (fitted, ADR 0073)
    dC = run_site_stateful(dtbl, meta; dt_seconds = 86400.0, t_soil0 = t0, enable_two_layer = true)

    (pubA, pubB) = get(ADR0073_DAILY_H_R2, site, (NaN, NaN))
    add("")
    add("  [1] DAILY STEP (the step `run.jl::couple_day!` actually runs) — n_days = $(length(dtbl["tair"]))")
    add("      H  A default λ_g=7.0   $(fmt(skill(dA.h, dtbl["h_obs"])))   [ADR 0073 R² = $pubA]")
    add("      H  B fitted  λ_g=1.0   $(fmt(skill(dB.h, dtbl["h_obs"])))   [ADR 0073 R² = $pubB]")
    add("      H  C E7 two-layer      $(fmt(skill(dC.h, dtbl["h_obs"])))   <-- UNFITTED")
    add("")
    add("      G  A default λ_g=7.0   $(fmt(skill(dA.g, dtbl["g_obs"])))")
    add("      G  B fitted  λ_g=1.0   $(fmt(skill(dB.g, dtbl["g_obs"])))")
    add("      G  C E7 two-layer      $(fmt(skill(dC.g, dtbl["g_obs"])))")
    add("")
    add(
        "      sd(G) daily [W/m²]: obs $(round(nanstd(dtbl["g_obs"]), digits = 2)) " *
            "(ADR 0073: $(get(ADR0073_DAILY_SD_GOBS, site, NaN)))  |  " *
            "A $(round(nanstd(dA.g), digits = 2))  B $(round(nanstd(dB.g), digits = 2))  " *
            "C $(round(nanstd(dC.g), digits = 2))"
    )
    add(
        "      Rn daily R²: A $(round(skill(dA.rn, dtbl["rn_obs"]).r2, digits = 3))  " *
            "C $(round(skill(dC.rn, dtbl["rn_obs"]).r2, digits = 3))   " *
            "(Rn must NOT regress — it is the strongest existing result)"
    )
    # DAILY T_skin, arm A vs arm C. ADR 0074 §6 published T_skin only SUB-DAILY (and only at z1 = 0.2 m),
    # while `run.jl::couple_day!` solves once per DAY — so the operational T_skin cost of the scheme was
    # never pinned per site. It is the one metric that does not need the tower to close, so it counts at
    # all four sites.
    if haskey(dtbl, "t_skin_obs") && any(isfinite, dtbl["t_skin_obs"])
        add("      T_skin daily  A default   $(fmt(skill(dA.t_skin, dtbl["t_skin_obs"])))")
        add("      T_skin daily  C E7        $(fmt(skill(dC.t_skin, dtbl["t_skin_obs"])))")
    end

    # ---- 2. H1 verdict ------------------------------------------------------------------------------
    sdC = nanstd(dC.g)
    r2C = skill(dC.h, dtbl["h_obs"]).r2
    if site in ("DE-Hai", "AU-ASM")
        verdict = (isfinite(sdC) && sdC <= 10.0 && isfinite(r2C) && r2C >= 0.3) ? "H1 SUPPORTED" : "H1 FALSIFIED"
        add("      ==> $verdict at $site  (criteria: daily sd(G_m) ≤ 10 W/m² AND daily H R² ≥ 0.3)")
    else
        add("      (H scored for information only — ADR 0073: this tower's ε_obs cannot score a closing model's H)")
    end

    # ---- 3. the prognostic column: spin-up + drift --------------------------------------------------
    # A closed-bottom column has no restoring term, so a runaway would show here. The surface feedback
    # (T1 cold ⇒ G up ⇒ T1 warms) is what is expected to hold it; this measures whether it does.
    # Measured at the PROPOSED DEFAULT z1, and as ANNUAL MEANS with a second-half trend: a raw
    # (last − first)/years confounds the spin-up jump (the seed is an annual mean, so the first step in
    # January moves T1 several K) with any secular drift. Line M runs DECADAL coupled simulations, so a
    # closed-bottom column that drifts would be a defect, not a curiosity.
    for z1 in (0.2, 0.75)
        r = run_site_stateful(dtbl, meta; dt_seconds = 86400.0, t_soil0 = t0, enable_two_layer = true, z_soil1 = z1)
        years = sort(unique(first.(dayidx)))
        ymean(v) = [nanmean([v[i] for i in eachindex(dayidx) if first(dayidx[i]) == y]) for y in years]
        y1 = ymean(r.t1); y2 = ymean(r.t2)
        # least-squares trend over the SECOND HALF of the annual means (spin-up excluded)
        function trend(y)
            h = max(1, length(y) ÷ 2)
            idx = collect(h:length(y))
            ys = y[idx]
            ok = findall(isfinite, ys)
            length(ok) < 3 && return NaN
            x = Float64.(idx[ok]); v = ys[ok]
            x̄ = sum(x) / length(x); v̄ = sum(v) / length(v)
            return sum((x .- x̄) .* (v .- v̄)) / sum(abs2, x .- x̄)
        end
        add("")
        add("  [3] PROGNOSTIC COLUMN, z1 = $z1 m — seed $(round(t0, digits = 2)) K, $(length(years)) yr")
        add("      annual mean T1: " * join([string(round(v, digits = 2)) for v in y1], " "))
        add("      annual mean T2: " * join([string(round(v, digits = 2)) for v in y2], " "))
        add(
            "      2nd-half trend: T1 $(round(trend(y1), digits = 3)) K/yr   T2 $(round(trend(y2), digits = 3)) K/yr" *
                "   (a decadal coupled run must not drift)"
        )
        add(
            "      mean daily G: model $(round(nanmean(r.g), digits = 3)) vs obs " *
                "$(round(nanmean(dtbl["g_obs"]), digits = 3)) W/m²  (⟨G⟩ → 0 is the equilibrium condition)"
        )
    end

    # ---- 4. H2: the native SUB-DAILY step, nocturnal H ----------------------------------------------
    day = tbl["swdown"] .> 50.0
    night = .!day
    sA = run_site(tbl, meta)
    # `z_soil1 = 0.2` is passed EXPLICITLY. Omitting it silently tracked the PACKAGE DEFAULT, so once E7
    # set that default to 0.75 m this arm stopped being the 0.2 m arm its own label claimed (v1-v4 of the
    # report are genuine 0.2 m; v5's two thickness arms came out byte-identical for exactly this reason).
    # A control arm must PIN every value it is controlling for — never inherit one from a default.
    sC = run_site_stateful(tbl, meta; dt_seconds = dt_sub, t_soil0 = t0, enable_two_layer = true, z_soil1 = 0.2)
    add("")
    add("  [4] SUB-DAILY ($(meta["timestep_min"]) min) — NOCTURNAL H (SWdown ≤ 50 W/m², n=$(count(night)))")
    add("      night H  A default     $(fmt(skill(subset(sA.h, night), subset(tbl["h_obs"], night))))")
    add("      night H  C E7          $(fmt(skill(subset(sC.h, night), subset(tbl["h_obs"], night))))")
    add(
        "      night sd(G): obs $(round(nanstd(subset(tbl["g_obs"], night)), digits = 2))  " *
            "A $(round(nanstd(subset(sA.g, night)), digits = 2))  " *
            "C $(round(nanstd(subset(sC.g, night)), digits = 2))"
    )
    add(
        "      all-hours sd(G): obs $(round(nanstd(tbl["g_obs"]), digits = 2))  " *
            "A $(round(nanstd(sA.g), digits = 2))  C $(round(nanstd(sC.g), digits = 2))  " *
            "(the DIURNAL AMPLITUDE — H2's real target)"
    )
    add("      night G  C E7          $(fmt(skill(subset(sC.g, night), subset(tbl["g_obs"], night))))")

    # ---- 6. TOP-LAYER THICKNESS SWEEP at the daily step ---------------------------------------------
    # MITgcm's z1 = 0.2 m was chosen for a model that steps in MINUTES. At our daily step the layer-1
    # relaxation number is dt·(κ_g+Δ)/(z1·C) ≈ 1.03 for z1 = 0.2 m — i.e. the top layer equilibrates with
    # T_skin WITHIN one step, so `G ≈ κ_g(T_skin,today − T_skin,yesterday)` degenerates into a day-to-day
    # difference operator. That is the mechanism behind arm C's excess sd(G) and poor G correlation
    # (H is still good because its BIAS and magnitude are right). A thicker top layer resolves the
    # timescale properly. `κ_g = 2λ/z1` shrinks with z1 as well, so this is not a free amplitude knob.
    add("")
    add("  [6] TOP-LAYER THICKNESS SWEEP (daily step) — is z1 = 0.2 m under-resolved at dt = 1 d?")
    add("      z1[m]  dt·rate   H R²     H RMSE   G R²     sd(G_m)   T_skin R²   (obs sd(G) = $(round(nanstd(dtbl["g_obs"]), digits = 2)))")
    for z1 in (0.2, 0.3, 0.5, 0.75, 1.0, 1.5)
        ps = SEBParams{Float64}(enable_two_layer = true, z_soil1 = z1)
        cv = ps.c_water * ps.theta_soil * ps.field_capacity + ps.c_dry_soil
        rate = 86400.0 * (2 * ps.lambda_soil / z1 + 2 * ps.lambda_soil / (z1 + ps.z_soil2)) / (z1 * cv)
        r = run_site_stateful(dtbl, meta; dt_seconds = 86400.0, t_soil0 = t0, enable_two_layer = true, z_soil1 = z1)
        sh = skill(r.h, dtbl["h_obs"])
        sg = skill(r.g, dtbl["g_obs"])
        sts = haskey(dtbl, "t_skin_obs") && any(isfinite, dtbl["t_skin_obs"]) ?
            round(skill(r.t_skin, dtbl["t_skin_obs"]).r2, digits = 3) : "n/a"
        add(
            "      " * rpad(z1, 6) * " " * rpad(round(rate, digits = 3), 9) *
                rpad(round(sh.r2, digits = 3), 9) * rpad(round(sh.rmse, digits = 2), 9) *
                rpad(round(sg.r2, digits = 3), 9) * rpad(round(nanstd(r.g), digits = 2), 10) * "$sts"
        )
    end

    # ---- 7. does the SAME z1 serve the sub-daily step? ----------------------------------------------
    # At dt = 30/60 min even z1 = 0.2 m is well resolved (dt·rate ≈ 0.02), so if the daily-optimal
    # thickness also works sub-daily then E7 needs ONE parameter set, not a step-dependent one — which is
    # what line O's sub-daily coupling needs to inherit.
    sC75 = run_site_stateful(tbl, meta; dt_seconds = dt_sub, t_soil0 = t0, enable_two_layer = true, z_soil1 = 0.75)
    add("")
    add("  [7] SUB-DAILY at the daily-optimal z1 = 0.75 m (vs z1 = 0.2 m in [4])")
    add("      night H  C z1=0.75     $(fmt(skill(subset(sC75.h, night), subset(tbl["h_obs"], night))))")
    add(
        "      night sd(G): obs $(round(nanstd(subset(tbl["g_obs"], night)), digits = 2))  " *
            "z1=0.2 $(round(nanstd(subset(sC.g, night)), digits = 2))  " *
            "z1=0.75 $(round(nanstd(subset(sC75.g, night)), digits = 2))"
    )
    add(
        "      all-hours sd(G): obs $(round(nanstd(tbl["g_obs"]), digits = 2))  " *
            "z1=0.2 $(round(nanstd(sC.g), digits = 2))  z1=0.75 $(round(nanstd(sC75.g), digits = 2))"
    )
    add("      night G  C z1=0.75     $(fmt(skill(subset(sC75.g, night), subset(tbl["g_obs"], night))))")

    # ---- 5. T_skin (all four sites where observable) ------------------------------------------------
    if haskey(tbl, "t_skin_obs") && any(isfinite, tbl["t_skin_obs"])
        add("")
        add("  [5] T_skin (sub-daily, where LWup exists) — T_skin does NOT depend on the tower closing,")
        add("      so unlike H these numbers are interpretable at all four sites.")
        add("      A default              $(fmt(skill(sA.t_skin, tbl["t_skin_obs"])))")
        add("      C E7 z1=0.2            $(fmt(skill(sC.t_skin, tbl["t_skin_obs"])))")
        add("      C E7 z1=0.75           $(fmt(skill(sC75.t_skin, tbl["t_skin_obs"])))")
        add("      night A                $(fmt(skill(subset(sA.t_skin, night), subset(tbl["t_skin_obs"], night))))")
        add("      night C z1=0.2         $(fmt(skill(subset(sC.t_skin, night), subset(tbl["t_skin_obs"], night))))")
        add("      night C z1=0.75        $(fmt(skill(subset(sC75.t_skin, night), subset(tbl["t_skin_obs"], night))))")
    end
    return nothing
end

function main()
    sites_env = get(ENV, "SITES", "")
    sites = if isempty(sites_env)
        files = sort(filter(f -> startswith(f, "seb_drive_") && endswith(f, ".csv"), readdir(DRIVE_DIR)))
        [replace(f, "seb_drive_" => "", ".csv" => "") for f in files]
    else
        [strip(s) for s in split(sites_env, ',') if !isempty(strip(s))]
    end
    out = String[
        "Component E — E7: does a PROGNOSTIC two-layer ground-heat column fix ADR 0073's diagnosis",
        "without fitting a coefficient?  (line E; drive dir: $DRIVE_DIR)",
        "",
        "Arms: A = default λ_g 7.0 (EWMA t_soil) · B = fitted λ_g 1.0 (ADR 0073) · C = E7 two-layer, UNFITTED.",
        "Arms A/B reproduce ADR 0073's published numbers = the harness check. Arm C runs the real `solve!`.",
        "H is scored at DE-Hai + AU-ASM only (ADR 0073: ε_obs −62.3/−47.5 at AU-Tum/AU-Rob). Sites: $(join(sites, ", "))",
    ]
    for site in sites
        csv = joinpath(DRIVE_DIR, "seb_drive_$site.csv")
        mfile = joinpath(DRIVE_DIR, "seb_drive_$site.meta")
        if !isfile(csv) || !isfile(mfile)
            push!(out, "\n$site — SKIP (missing $(basename(csv)) or its .meta)")
            continue
        end
        report_site(site, read_drive_csv(csv), read_meta(mfile), out)
    end
    text = join(out, "\n") * "\n"
    print(text)
    dest = get(ENV, "OUT", joinpath(DRIVE_DIR, "e7_two_layer_probe.txt"))
    write(dest, text)
    println("\nreport: $dest")
    return nothing
end

main()
