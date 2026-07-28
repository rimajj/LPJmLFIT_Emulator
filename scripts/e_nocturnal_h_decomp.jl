#!/usr/bin/env julia
# =====================================================================================================
# e_nocturnal_h_decomp.jl — line E, milestone **E6**: decompose Component E's NOCTURNAL sensible-heat
# error into the only three terms it can possibly come from.
#
# WHY A DECOMPOSITION AND NOT A PARAMETER SWEEP.  In `solve_seb`, H is not predicted by a bulk formula —
# it is the **exact residual** `H_m = Rn_m − LE − G_m` (LE prescribed from the tower in Experiment A).
# So with the tower's own non-closure defined as
#
#     ε_obs ≡ Rn_o − LE − H_o − G_o            (0 only if the tower's corrected fluxes close with Rn, Qg)
#
# the H error obeys, IDENTICALLY (algebra, not a hypothesis):
#
#     ΔH  ≡  H_m − H_o  =  (Rn_m − Rn_o)  −  (G_m − G_o)  +  ε_obs
#                       =      ΔRn        −      ΔG       +  ε_obs
#
# Every W/m² of the nocturnal H failure (ADR 0072: night R² −1.0…−5.6 at all four sites) MUST be a
# radiation error, a ground-heat error, or the tower's own failure to close. `g_a` appears in NONE of the
# three terms — it can only act indirectly, by moving the solved `T_skin` and hence `Rn_m` and `G_m`.
# That is what Parts 5–6 quantify, and it is why "tune `stab_amp`" was never going to be the answer.
#
# PARTS
#   1  harness check — the model's own closure to machine precision, and a reproduction of ADR 0072's
#      night-H numbers through THIS script (residual-diagnosis §3: reproduce a trusted number first)
#   2  the identity above, evaluated night / day / all — the attribution
#   3  G scored directly against the tower's measured `Qg` (positive INTO ground), day and night
#   4  Rn scored NIGHT-ONLY (the P2 report only ever gave the all-hours number, which is day-dominated)
#   5  the g_a LEVER BRACKET — how far can *any* aerodynamic conductance move nocturnal H? Run neutral
#      (`enable_stability=false`) with wind × m: with stability off, g_a ∝ wind exactly, so this is an
#      exact g_a multiplier applied through the REAL `solve_seb` — no diagnostic re-implementation.
#   6  g_a from the tower's MEASURED u* — `g_a* = 1/(U/u*² + ln(z0m/z0h)/(k·u*))` — injected through the
#      real solver as the equivalent neutral wind `U_eq = g_a*·lm·lh/k²`, plus a direct model-vs-measured
#      g_a comparison. This is the handoff's "run that first" experiment; Part 5 already brackets it.
#
# Env: DRIVE_DIR (default from the P2 pipeline) · SITES (default: all found) · OUT (report path)
# Usage:  scripts/sbatch_julia.sh E-e6decomp --project=. scripts/e_nocturnal_h_decomp.jl
# =====================================================================================================

using LPJmLFITEmulator

const DRIVE_DIR = get(
    ENV, "DRIVE_DIR",
    "/p/tmp/jamirp/esm_land_emulator_data/fluxnet_plumber2/derived/seb_validation",
)
const KARMAN = 0.41
const Z0H_RATIO = 0.1

"Read a `KEY=VALUE` .meta file into a Dict{String,String} (pure Base — no JSON dependency)."
function read_meta(path)
    meta = Dict{String, String}()
    for line in eachline(path)
        i = findfirst('=', line)
        i === nothing && continue
        meta[line[1:(i - 1)]] = line[(i + 1):end]
    end
    return meta
end

"Read the driving CSV into a Dict of column name => Vector{Float64} (`NaN` for empty/non-numeric cells)."
function read_drive_csv(path)
    cols = String[]
    data = Vector{Vector{Float64}}()
    open(path) do io
        header = split(strip(readline(io)), ',')
        cols = String.(header)
        data = [Float64[] for _ in cols]
        for line in eachline(io)
            isempty(strip(line)) && continue
            fields = split(line, ',')
            length(fields) == length(cols) || continue
            for (j, f) in enumerate(fields)
                v = tryparse(Float64, f)
                push!(data[j], v === nothing ? NaN : v)
            end
        end
    end
    return Dict(cols[j] => data[j] for j in eachindex(cols))
end

# ---- metrics (identical definitions to validate_e_seb_vs_plumber2.jl, so numbers are comparable) -----
struct Skill
    n::Int
    bias::Float64
    rmse::Float64
    mae::Float64
    r2::Float64
    slope::Float64
end

function skill(model::Vector{Float64}, obs::Vector{Float64})
    ok = findall(i -> isfinite(model[i]) && isfinite(obs[i]), eachindex(model))
    n = length(ok)
    n < 10 && return Skill(n, NaN, NaN, NaN, NaN, NaN)
    m, o = model[ok], obs[ok]
    d = m .- o
    ō = sum(o) / n
    sse = sum(abs2, d)
    sst = sum(abs2, o .- ō)
    m̄ = sum(m) / n
    sxy = sum((o .- ō) .* (m .- m̄))
    sxx = sum(abs2, o .- ō)
    return Skill(
        n, sum(d) / n, sqrt(sse / n), sum(abs, d) / n,
        sst > 0 ? 1 - sse / sst : NaN, sxx > 0 ? sxy / sxx : NaN,
    )
end

fmt(s::Skill) = string(
    "n=", lpad(s.n, 7), "  bias=", lpad(round(s.bias, digits = 2), 8),
    "  RMSE=", lpad(round(s.rmse, digits = 2), 7), "  MAE=", lpad(round(s.mae, digits = 2), 7),
    "  R²=", lpad(round(s.r2, digits = 3), 7), "  slope=", lpad(round(s.slope, digits = 3), 7),
)

subset(v::Vector{Float64}, m::AbstractVector{Bool}) = v[m]
"Mean over the finite entries only (the tables carry NaN where an observation is missing)."
function nanmean(v)
    f = filter(isfinite, v)
    return isempty(f) ? NaN : sum(f) / length(f)
end
"Standard deviation over the finite entries only."
function nanstd(v)
    f = filter(isfinite, v)
    length(f) < 2 && return NaN
    μ = sum(f) / length(f)
    return sqrt(sum(abs2, f .- μ) / (length(f) - 1))
end
r2s(x) = lpad(round(x, digits = 2), 8)

# ---- geometry, matching `aerodynamic_conductance` exactly --------------------------------------------
"The two log-law factors `(lm, lh)` and `z−d` for a site, computed exactly as `aerodynamic_conductance` does."
function loglaw(z0m, height, z_ref)
    z0m_e = max(z0m, 0.01)
    d = 0.67 * max(height, 0.0)
    z = max(z_ref, d + z0m_e + 2.0)
    return (log((z - d) / z0m_e), log((z - d) / (Z0H_RATIO * z0m_e)), z - d)
end

"""
Run `solve_seb` over every row of a site's driving table.

`wind_override` replaces the driving wind column — the mechanism this script uses to inject an arbitrary
`g_a` through the REAL solver: with `enable_stability=false`, `g_a = k²·U/(lm·lh)` is exactly proportional
to wind, so scaling wind scales `g_a`, and `U_eq = g_a·lm·lh/k²` reproduces any target `g_a`.
"""
function run_site(tbl, meta; wind_override = nothing, params_kwargs...)
    h_can = parse(Float64, meta["canopy_height_m"])
    z_ref = parse(Float64, meta["reference_height_m"])
    z0m = parse(Float64, meta["z0m_m"])
    p = SEBParams{Float64}(; z_ref = z_ref, params_kwargs...)
    wind = wind_override === nothing ? tbl["wind"] : wind_override
    n = length(tbl["tair"])
    h_mod = Vector{Float64}(undef, n); ts_mod = Vector{Float64}(undef, n)
    rn_mod = Vector{Float64}(undef, n); g_mod = Vector{Float64}(undef, n)
    ga_mod = Vector{Float64}(undef, n)
    @inbounds for i in 1:n
        (Ts, Rn, H, G, _le, ga, _c) = solve_seb(
            p, tbl["swdown"][i], tbl["lwdown"][i], tbl["tair"][i], tbl["psurf"][i], wind[i],
            tbl["albedo"][i], z0m, h_can, tbl["le_in"][i], tbl["t_soil"][i],
        )
        h_mod[i] = H; ts_mod[i] = Ts; rn_mod[i] = Rn; g_mod[i] = G; ga_mod[i] = ga
    end
    return (h = h_mod, t_skin = ts_mod, rn = rn_mod, g = g_mod, ga = ga_mod)
end

function report_site(site, tbl, meta, out::Vector{String})
    add(s) = push!(out, s)
    day = tbl["swdown"] .> 50.0
    night = .!day
    h_can = parse(Float64, meta["canopy_height_m"])
    z_ref = parse(Float64, meta["reference_height_m"])
    z0m = parse(Float64, meta["z0m_m"])
    (lm, lh, _zmd) = loglaw(z0m, h_can, z_ref)
    res = run_site(tbl, meta)

    add("")
    add("="^104)
    add(
        "$site — $(meta["igbp"]), $(meta["rows"]) rows, $(meta["years"]), $(meta["timestep_min"]) min " *
            "(night = SWdown ≤ 50 W/m², n=$(count(night)); day n=$(count(day)))"
    )

    # ---- 1. harness check ---------------------------------------------------------------------------
    add("")
    add("  [1] HARNESS CHECK — is this script the same experiment ADR 0072 ran?")
    selfres = maximum(abs.(res.h .- (res.rn .- tbl["le_in"] .- res.g)))
    add("    model self-closure  max|H_m − (Rn_m − LE − G_m)| = $(selfres) W/m²   (must be ~0: H IS the residual)")
    sn = skill(subset(res.h, night), subset(tbl["h_obs"], night))
    add("    night H reproduced  $(fmt(sn))")
    add("      ↳ compare to the ADR 0072 report for this site; identical ⇒ the basis below is the P2 basis")

    # ---- 2. the identity ----------------------------------------------------------------------------
    dH = res.h .- tbl["h_obs"]
    dRn = res.rn .- tbl["rn_obs"]
    dG = res.g .- tbl["g_obs"]
    eps_obs = tbl["rn_obs"] .- tbl["le_in"] .- tbl["h_obs"] .- tbl["g_obs"]
    ident = dH .- (dRn .- dG .+ eps_obs)
    add("")
    add("  [2] THE EXACT DECOMPOSITION   ΔH = ΔRn − ΔG + ε_obs   [W/m², mean over the subset]")
    add("      ε_obs = Rn_o − LE − H_o − G_o is the TOWER's own non-closure — an error the closure")
    add("      cannot remove, because it must close what the tower does not.")
    add(
        "      identity check: max|ΔH − (ΔRn − ΔG + ε_obs)| = " *
            "$(maximum(filter(isfinite, abs.(ident))))  (algebra ⇒ ~0)"
    )
    add("")
    add("      subset        ΔH       =     ΔRn      −     ΔG      +   ε_obs      |  sd(ΔRn) sd(ΔG) sd(ε_obs)")
    for (nm, m) in (("night ", night), ("day   ", day), ("all   ", trues(length(day))))
        add(
            "      $nm  $(r2s(nanmean(subset(dH, m))))   $(r2s(nanmean(subset(dRn, m))))  " *
                " $(r2s(nanmean(subset(dG, m))))   $(r2s(nanmean(subset(eps_obs, m))))      |  " *
                "$(r2s(nanstd(subset(dRn, m)))) $(r2s(nanstd(subset(dG, m)))) $(r2s(nanstd(subset(eps_obs, m))))"
        )
    end

    # ---- 3. G against the measured Qg ---------------------------------------------------------------
    add("")
    add("  [3] GROUND HEAT G [W/m²] — modelled λ_g(T_skin − t_soil) vs the tower's measured `Qg`")
    add("      night  $(fmt(skill(subset(res.g, night), subset(tbl["g_obs"], night))))")
    add("      day    $(fmt(skill(subset(res.g, day), subset(tbl["g_obs"], day))))")
    add(
        "      mean G: model night $(round(nanmean(subset(res.g, night)), digits = 2)) vs obs " *
            "$(round(nanmean(subset(tbl["g_obs"], night)), digits = 2))  |  model day " *
            "$(round(nanmean(subset(res.g, day)), digits = 2)) vs obs " *
            "$(round(nanmean(subset(tbl["g_obs"], day)), digits = 2))"
    )
    add(
        "      sd   G: model $(round(nanstd(res.g), digits = 2)) vs obs $(round(nanstd(tbl["g_obs"]), digits = 2))" *
            "   (a diurnal-amplitude check: `t_soil` is a 30-DAY EWMA, so G_m's only diurnal signal is T_skin's)"
    )
    # G_res — the BUDGET-IMPLIED non-turbulent sink. A soil heat-flux plate at 5–8 cm misses the heat stored
    # in the soil above it and, at a tall forest, the canopy/biomass/air storage entirely; that missing
    # storage IS ε_obs. A model that closes exactly must supply the WHOLE non-turbulent sink, so `G_res =
    # Rn_o − LE − H_o = G_o + ε_obs` is the right target population for G (residual-diagnosis §3b: match the
    # quantity the model must reproduce, not merely the one that is easy to measure). This also collapses
    # the decomposition to two terms:  ΔH = ΔRn − (G_m − G_res).
    g_res = tbl["rn_obs"] .- tbl["le_in"] .- tbl["h_obs"]
    add("      vs the BUDGET-IMPLIED sink G_res = Rn_o − LE − H_o (= G_o + ε_obs; the storage a plate misses):")
    add("        night  $(fmt(skill(subset(res.g, night), subset(g_res, night))))")
    add("        day    $(fmt(skill(subset(res.g, day), subset(g_res, day))))")
    add(
        "        mean G_res night $(round(nanmean(subset(g_res, night)), digits = 2)) vs measured G_o " *
            "$(round(nanmean(subset(tbl["g_obs"], night)), digits = 2))  ⇒ they agree only where ε_obs ≈ 0"
    )

    # ---- 4. Rn at night -----------------------------------------------------------------------------
    add("")
    add("  [4] NET RADIATION Rn [W/m²] — NIGHT-ONLY (the P2 report gave only the day-dominated all-hours number)")
    add("      night  $(fmt(skill(subset(res.rn, night), subset(tbl["rn_obs"], night))))")
    add("      day    $(fmt(skill(subset(res.rn, day), subset(tbl["rn_obs"], day))))")

    # ---- 5. the g_a lever bracket -------------------------------------------------------------------
    add("")
    add("  [5] g_a LEVER BRACKET — neutral g_a scaled ×m (stability OFF ⇒ g_a ∝ wind exactly).")
    add(
        "      How far can ANY aerodynamic conductance move nocturnal H? (the default is stability ON, bias " *
            "$(round(sn.bias, digits = 2)))"
    )
    add("        ×m     mean g_a     night H bias   night H RMSE    night H R²")
    for m in (0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 10.0)
        r = run_site(tbl, meta; wind_override = tbl["wind"] .* m, enable_stability = false)
        s = skill(subset(r.h, night), subset(tbl["h_obs"], night))
        add(
            "      $(rpad(m, 6)) $(lpad(round(nanmean(subset(r.ga, night)), digits = 5), 9))   " *
                "$(r2s(s.bias))       $(r2s(s.rmse))      $(r2s(s.r2))"
        )
    end

    # ---- 6. g_a from the measured u* ----------------------------------------------------------------
    if haskey(tbl, "ustar") && any(isfinite, tbl["ustar"])
        u = tbl["ustar"]
        U = max.(tbl["wind"], 0.1)
        # bulk aerodynamic conductance for HEAT from the measurement: r_ah = U/u*² + kB⁻¹/(k·u*)
        ga_obs = [
            isfinite(u[i]) && u[i] > 0 ?
                1.0 / (U[i] / u[i]^2 + log(1 / Z0H_RATIO) / (KARMAN * u[i])) : NaN
                for i in eachindex(u)
        ]
        # inject it through the real solver as the equivalent NEUTRAL wind
        ueq = [isfinite(ga_obs[i]) ? ga_obs[i] * lm * lh / KARMAN^2 : tbl["wind"][i] for i in eachindex(ga_obs)]
        nfloor = count(i -> isfinite(ga_obs[i]) && ueq[i] < 0.1, eachindex(ueq))
        r = run_site(tbl, meta; wind_override = ueq, enable_stability = false)
        add("")
        add("  [6] g_a FROM THE TOWER'S MEASURED u*  —  g_a* = 1/(U/u*² + ln(z0m/z0h)/(k·u*))")
        add("      the handoff's \"run this first\" experiment: it replaces the whole neutral-log-law × tanh(Ri)")
        add("      chain with the measurement, so it embeds the REAL stability.")
        add(
            "      measured vs modelled g_a at night [m/s]: obs $(round(nanmean(subset(ga_obs, night)), digits = 5))" *
                " vs model $(round(nanmean(subset(res.ga, night)), digits = 5))" *
                "  (ratio $(round(nanmean(subset(ga_obs, night)) / nanmean(subset(res.ga, night)), digits = 3)))"
        )
        add("      steps where U_eq hit the 0.1 m/s wind floor: $nfloor of $(count(isfinite, ga_obs))")
        add("      night H with the MEASURED g_a  $(fmt(skill(subset(r.h, night), subset(tbl["h_obs"], night))))")
        add("      night H with the default model $(fmt(sn))")
        if haskey(tbl, "t_skin_obs") && any(isfinite, tbl["t_skin_obs"])
            add("      night T_skin measured-g_a     $(fmt(skill(subset(r.t_skin, night), subset(tbl["t_skin_obs"], night))))")
            add("      night T_skin default          $(fmt(skill(subset(res.t_skin, night), subset(tbl["t_skin_obs"], night))))")
        end
    end
    # ---- 7. the model's NATIVE step ------------------------------------------------------------------
    # `run.jl::couple_day!` calls `solve!` ONCE PER DAY (src/run.jl:93), so the operational closure is a
    # daily one. Parts 1–6 drive it at 30/60 min, which is a diagnosis of a regime the coupled model never
    # runs in. Here the drive table is aggregated to daily means FIRST and the closure solved once per day
    # — the same experiment the coupled driver performs — and scored against daily-mean observations.
    steps_per_day = round(Int, 1440 / parse(Int, meta["timestep_min"]))
    need = ceil(Int, 5 * steps_per_day / 6)
    keys_day = Dict{Tuple{Int, Int}, Vector{Int}}()
    for i in eachindex(tbl["year"])
        push!(get!(keys_day, (Int(tbl["year"][i]), Int(tbl["doy"][i])), Int[]), i)
    end
    dayidx = sort([k for (k, v) in keys_day if length(v) >= need])
    dmean(col) = [nanmean([tbl[col][i] for i in keys_day[k]]) for k in dayidx]
    dtbl = Dict{String, Vector{Float64}}(
        c => dmean(c) for c in
            ("swdown", "lwdown", "tair", "psurf", "wind", "albedo", "t_soil", "le_in", "h_obs", "rn_obs", "g_obs")
    )
    dres = run_site(dtbl, meta)
    ddH = dres.h .- dtbl["h_obs"]
    ddRn = dres.rn .- dtbl["rn_obs"]
    ddG = dres.g .- dtbl["g_obs"]
    deps = dtbl["rn_obs"] .- dtbl["le_in"] .- dtbl["h_obs"] .- dtbl["g_obs"]
    add("")
    add("  [7] THE MODEL'S NATIVE STEP — closure solved ONCE PER DAY on daily-mean forcing")
    add("      (`run.jl::couple_day!` calls `solve!` once per day; Parts 1–6 diagnose a sub-daily regime the")
    add("       coupled model never runs in). n=$(length(dayidx)) days with ≥5/6 of their steps present.")
    add("      H daily-step   $(fmt(skill(dres.h, dtbl["h_obs"])))")
    add("      G daily-step   $(fmt(skill(dres.g, dtbl["g_obs"])))")
    add("      Rn daily-step  $(fmt(skill(dres.rn, dtbl["rn_obs"])))")
    add(
        "      decomposition  ΔH $(r2s(nanmean(ddH))) = ΔRn $(r2s(nanmean(ddRn))) − ΔG $(r2s(nanmean(ddG)))" *
            " + ε_obs $(r2s(nanmean(deps)))"
    )
    add(
        "      sd: G model $(round(nanstd(dres.g), digits = 2)) vs obs $(round(nanstd(dtbl["g_obs"]), digits = 2))" *
            "  (cf. the sub-daily sd in [3] — the diurnal swing is what the 30-day-EWMA reference cannot damp)"
    )

    # ---- 8. the λ_g the tower implies ----------------------------------------------------------------
    # Least-squares λ_g through the origin: G_obs ≈ λ·(T_skin_model − t_soil). Reported sub-daily AND
    # daily. DIAGNOSTIC — refitting λ_g under a form that has no diurnal soil inertia would codify the
    # wrong form (residual-diagnosis §3b), so this quantifies the gap, it does not prescribe a value.
    function fit_lambda(ts, tsoil, gobs)
        x = ts .- tsoil
        ok = findall(i -> isfinite(x[i]) && isfinite(gobs[i]), eachindex(x))
        isempty(ok) && return NaN
        return sum(x[i] * gobs[i] for i in ok) / sum(x[i]^2 for i in ok)
    end
    dg_res = dtbl["rn_obs"] .- dtbl["le_in"] .- dtbl["h_obs"]
    add("")
    add("  [8] THE λ_g THE TOWER IMPLIES — least-squares fit of the observed sink on (T_skin_model − t_soil)")
    add("      [W/m²/K; `SEBParams.lambda_g` default = 7.0]. Fitted against BOTH targets: the measured plate")
    add("      `G_o` and the budget-implied `G_res` (what a closing model must actually supply).")
    add(
        "      vs measured G_o    sub-daily $(round(fit_lambda(res.t_skin, tbl["t_soil"], tbl["g_obs"]), digits = 3))" *
            "   night $(round(fit_lambda(subset(res.t_skin, night), subset(tbl["t_soil"], night), subset(tbl["g_obs"], night)), digits = 3))" *
            "   day $(round(fit_lambda(subset(res.t_skin, day), subset(tbl["t_soil"], day), subset(tbl["g_obs"], day)), digits = 3))" *
            "   DAILY STEP $(round(fit_lambda(dres.t_skin, dtbl["t_soil"], dtbl["g_obs"]), digits = 3))"
    )
    add(
        "      vs budget G_res    sub-daily $(round(fit_lambda(res.t_skin, tbl["t_soil"], g_res), digits = 3))" *
            "   night $(round(fit_lambda(subset(res.t_skin, night), subset(tbl["t_soil"], night), subset(g_res, night)), digits = 3))" *
            "   day $(round(fit_lambda(subset(res.t_skin, day), subset(tbl["t_soil"], day), subset(g_res, day)), digits = 3))" *
            "   DAILY STEP $(round(fit_lambda(dres.t_skin, dtbl["t_soil"], dg_res), digits = 3))"
    )
    # ---- 9. what would a different λ_g buy? ----------------------------------------------------------
    # DIAGNOSTIC ONLY. `lambda_g` is a `SEBParams` default; changing it moves the coupled and 5-biome
    # baselines, so it is an INTEGRATION POINT with line M (guardrail 4). This part exists to give M the
    # number, not to flip the default — this script never writes a parameter.
    add("")
    add("  [9] λ_g SENSITIVITY — H skill at the model's NATIVE daily step, and nocturnal H sub-daily")
    add("      DIAGNOSTIC ONLY: λ_g is a default; a change is an integration point with line M.")
    add("       λ_g    | daily-step H: bias   RMSE     R²   slope | sd(G_m) | sub-daily night H: bias  RMSE     R²")
    for lg in (0.5, 1.0, 2.0, 3.5, 7.0, 14.0)
        dr = run_site(dtbl, meta; lambda_g = lg)
        sd_ = skill(dr.h, dtbl["h_obs"])
        sr = run_site(tbl, meta; lambda_g = lg)
        sn2 = skill(subset(sr.h, night), subset(tbl["h_obs"], night))
        add(
            "      $(rpad(lg, 6))  | $(r2s(sd_.bias)) $(r2s(sd_.rmse)) $(r2s(sd_.r2)) $(r2s(sd_.slope)) |" *
                " $(r2s(nanstd(dr.g))) | $(r2s(sn2.bias)) $(r2s(sn2.rmse)) $(r2s(sn2.r2))" *
                (lg == 7.0 ? "   <- DEFAULT" : "")
        )
    end
    add("      (observed sd of the daily G_o = $(round(nanstd(dtbl["g_obs"]), digits = 2)) W/m² — the target for sd(G_m))")
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
        "Component E — E6 NOCTURNAL-H DIAGNOSIS: the exact decomposition of the H error (line E)",
        "drive dir: $DRIVE_DIR",
        "H is the EXACT residual Rn_m − LE − G_m, so  ΔH = ΔRn − ΔG + ε_obs  identically.",
        "g_a is in none of those terms — it can only act by moving T_skin. Sites: $(join(sites, ", "))",
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
    dest = get(ENV, "OUT", joinpath(DRIVE_DIR, "e6_nocturnal_h_decomp.txt"))
    write(dest, text)
    println("\nreport: $dest")
    return nothing
end

main()
