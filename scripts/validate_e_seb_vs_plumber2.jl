#!/usr/bin/env julia
# =====================================================================================================
# validate_e_seb_vs_plumber2.jl — Component E's P2 validation, **Experiment A**: the surface-energy-balance
# closure driven by a FLUXNET/OzFlux tower's own forcing AND its own measured LE, scored against the tower's
# H and (where observable) T_skin.  Line E, milestone E4.
#
# WHY THIS ISOLATES E.  `FToE` hands E `le` already formed as λ·ET (`src/components/fast.jl:236`), so LE is
# **F's** number — E's own predictions are `T_skin`, `H` (the residual) and `G`. Feeding the closure the
# TOWER's LE removes F's ET error from the comparison entirely: whatever H and T_skin miss by here is the
# closure's own error. (Experiment B, still to come, feeds F's LE; the A−B difference *is* F's ET error.)
#
# Everything the closure needs is taken from the observations where an observation exists — the driving
# variables, the LE, the albedo (tower Σ SWup / Σ SWdown), the canopy height and, crucially, the
# **measurement height** (`SEBParams.z_ref` is overridden per site: DE-Hai's forcing is measured at 43.5 m,
# not the 10 m default, and `g_a` depends on that level).  Input tables + provenance:
# `scripts/build_e_seb_validation_table.py` (see its docstring for the t_soil / albedo conventions).
#
# Reported per site:
#   H       bias, RMSE, MAE, R², OLS slope — ALL / DAYTIME (SWdown>50) / NIGHTTIME, plus the fraction of
#           steps inside PLUMBER2's own joint uncertainty `|h_cor_uc|` (the E4 acceptance band; FLUXNET2015
#           sites only — the OzFlux files ship no uncertainty)
#   T_skin  bias, RMSE, R² against the LWup-derived observation (OzFlux sites only), day/night split
#   Rn      model vs observed net radiation — a check of the radiation path under an OBSERVED albedo
#   diurnal the mean diurnal cycle of modelled vs observed H (and T_skin), the sub-daily gate
#   stability  the SAME metrics with `enable_stability=false`, because `SEBParams`' own comment says the
#           bounded-Richardson surrogate must be validated against PLUMBER2 before nocturnal H is trusted.
#           With STAB_SWEEP=1 a small (stab_amp, stab_k) grid is scored — DIAGNOSTIC ONLY: changing a default
#           is an integration point with line M (guardrail 4), so this script never writes parameters.
#
# Env:
#   DRIVE_DIR  dir holding seb_drive_<site>.csv + .meta  (default from config/paths.yaml)
#   SITES      comma list (default: every site found in DRIVE_DIR)
#   STAB_SWEEP 1 = also score a small (stab_amp, stab_k) grid   (default 0)
#   OUT        report path (default DRIVE_DIR/e4_experimentA_report.txt)
# Usage (minutes for 4 sites × full records — submit it):
#   scripts/sbatch_julia.sh E-e4a --project=. scripts/validate_e_seb_vs_plumber2.jl
#   SITES=DE-Hai STAB_SWEEP=1 julia --project=. scripts/validate_e_seb_vs_plumber2.jl
# =====================================================================================================

using LPJmLFITEmulator

const DRIVE_DIR = get(
    ENV, "DRIVE_DIR",
    "/p/tmp/jamirp/esm_land_emulator_data/fluxnet_plumber2/derived/seb_validation",
)

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

# ---- metrics ----------------------------------------------------------------------------------------
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
    # OLS slope of model on obs (through-origin-free: the usual regression of y=model on x=obs)
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

subset(v::Vector{Float64}, mask::AbstractVector{Bool}) = v[mask]

# ---- the run ----------------------------------------------------------------------------------------
"""
Run `solve_seb` over every row of a site's driving table and return the modelled columns.

`t_soil` comes from the table (a τ=30 d EWMA of DAILY-mean Tair — the sub-daily-τ trap: applying `solve!`'s
per-step recursion at 30 min would decay ~48× too fast). `z_ref` is the site's measurement height and `z0m`
= 0.1·canopy height; albedo is the tower's own.
"""
function run_site(tbl, meta; params_kwargs...)
    h_can = parse(Float64, meta["canopy_height_m"])
    z_ref = parse(Float64, meta["reference_height_m"])
    z0m = parse(Float64, meta["z0m_m"])
    p = SEBParams{Float64}(; z_ref = z_ref, params_kwargs...)
    n = length(tbl["tair"])
    h_mod = Vector{Float64}(undef, n)
    ts_mod = Vector{Float64}(undef, n)
    rn_mod = Vector{Float64}(undef, n)
    g_mod = Vector{Float64}(undef, n)
    ga_mod = Vector{Float64}(undef, n)
    @inbounds for i in 1:n
        (Ts, Rn, H, G, _le, ga, _capped) = solve_seb(
            p, tbl["swdown"][i], tbl["lwdown"][i], tbl["tair"][i], tbl["psurf"][i], tbl["wind"][i],
            tbl["albedo"][i], z0m, h_can, tbl["le_in"][i], tbl["t_soil"][i],
        )
        h_mod[i] = H; ts_mod[i] = Ts; rn_mod[i] = Rn; g_mod[i] = G; ga_mod[i] = ga
    end
    return (h = h_mod, t_skin = ts_mod, rn = rn_mod, g = g_mod, ga = ga_mod, params = p)
end

function report_site(site, tbl, meta, out::Vector{String})
    add(s) = push!(out, s)
    day = tbl["swdown"] .> 50.0
    night = .!day
    res = run_site(tbl, meta)

    add("")
    add("="^104)
    add("$site — $(meta["igbp"]), $(meta["rows"]) rows, $(meta["years"]) , $(meta["timestep_min"]) min")
    add(
        "  driving: tower `swdown/lwdown/tair/psurf/wind`; LE = tower `$(meta["le_column"])`; " *
            "H target = tower `$(meta["h_column"])`"
    )
    add(
        "  boundary: albedo = tower Σ SWup/Σ SWdown (mean $(meta["mean_albedo"])), " *
            "canopy $(meta["canopy_height_m"]) m, z0m $(round(parse(Float64, meta["z0m_m"]), digits = 2)) m, " *
            "z_ref = $(meta["reference_height_m"]) m (measurement height, overriding the 10 m default)"
    )
    add(
        "  mean LE in = $(meta["mean_le_in"]) W/m², mean H obs = $(meta["mean_h_obs"]) W/m², " *
            "modelled mean H = $(round(sum(res.h) / length(res.h), digits = 3)) W/m²"
    )

    add("")
    add("  SENSIBLE HEAT H [W/m²] — E's own prediction (the residual PLUMBER2 calls the hardest flux)")
    add("    all      $(fmt(skill(res.h, tbl["h_obs"])))")
    add("    daytime  $(fmt(skill(subset(res.h, day), subset(tbl["h_obs"], day))))")
    add("    night    $(fmt(skill(subset(res.h, night), subset(tbl["h_obs"], night))))")
    if haskey(tbl, "h_uc") && any(isfinite, tbl["h_uc"])
        ok = findall(
            i -> isfinite(res.h[i]) && isfinite(tbl["h_obs"][i]) && isfinite(tbl["h_uc"][i]),
            eachindex(res.h)
        )
        inside = count(i -> abs(res.h[i] - tbl["h_obs"][i]) <= tbl["h_uc"][i], ok)
        okd = filter(i -> day[i], ok)
        insided = count(i -> abs(res.h[i] - tbl["h_obs"][i]) <= tbl["h_uc"][i], okd)
        add(
            "    INSIDE PLUMBER2's own |h_cor_uc| band: " *
                "$(round(100 * inside / max(length(ok), 1), digits = 1))% of $(length(ok)) steps " *
                "(daytime $(round(100 * insided / max(length(okd), 1), digits = 1))% of $(length(okd)); " *
                "mean band ±$(round(sum(tbl["h_uc"][ok]) / max(length(ok), 1), digits = 2)) W/m²)"
        )
    else
        add("    (no uncertainty band at this site — OzFlux files ship no `*_cor_uc`)")
    end

    if haskey(tbl, "t_skin_obs") && any(isfinite, tbl["t_skin_obs"])
        add("")
        add("  SKIN TEMPERATURE T_skin [K] — vs the LWup-derived observation (ε=0.97, matching the closure)")
        add("    all      $(fmt(skill(res.t_skin, tbl["t_skin_obs"])))")
        add("    daytime  $(fmt(skill(subset(res.t_skin, day), subset(tbl["t_skin_obs"], day))))")
        add("    night    $(fmt(skill(subset(res.t_skin, night), subset(tbl["t_skin_obs"], night))))")
        dmod = res.t_skin .- tbl["tair"]
        dobs = tbl["t_skin_obs"] .- tbl["tair"]
        f(v, m) = round(
            sum(x -> isfinite(x) ? x : 0.0, subset(v, m)) /
                max(count(isfinite, subset(v, m)), 1), digits = 3
        )
        add(
            "    T_skin − Tair: model day $(f(dmod, day)) K vs obs $(f(dobs, day)) K   |   " *
                "night model $(f(dmod, night)) K vs obs $(f(dobs, night)) K"
        )
    else
        add("")
        add("  T_skin: not observable at this site (no LWup — FLUXNET2015/LaThuile-sourced PLUMBER2 file)")
    end

    if haskey(tbl, "rn_obs") && any(isfinite, tbl["rn_obs"])
        add("")
        add("  NET RADIATION Rn [W/m²] — the radiation path under the tower's own albedo")
        add("    all      $(fmt(skill(res.rn, tbl["rn_obs"])))")
    end

    add("")
    add(
        "  MEAN DIURNAL CYCLE (the sub-daily gate) — hour: H model / H obs" *
            (any(isfinite, tbl["t_skin_obs"]) ? " | T_skin model / obs" : "")
    )
    for hh in 0:2:22
        m = [tbl["hour"][i] >= hh && tbl["hour"][i] < hh + 2 for i in eachindex(tbl["hour"])]
        count(m) == 0 && continue
        hm = sum(subset(res.h, m)) / count(m)
        ho = let v = subset(tbl["h_obs"], m)
            f = filter(isfinite, v); isempty(f) ? NaN : sum(f) / length(f)
        end
        line = "    $(lpad(hh, 2)):00–$(lpad(hh + 2, 2)):00   " *
            "$(lpad(round(hm, digits = 1), 7)) / $(lpad(round(ho, digits = 1), 7))"
        if any(isfinite, tbl["t_skin_obs"])
            tm = sum(subset(res.t_skin, m)) / count(m)
            to = let v = subset(tbl["t_skin_obs"], m)
                f = filter(isfinite, v)
                isempty(f) ? NaN : sum(f) / length(f)
            end
            line *= "   |   $(lpad(round(tm, digits = 2), 7)) / $(lpad(round(to, digits = 2), 7))"
        end
        add(line)
    end

    # ---- DAILY means: the model's NATIVE timestep, and how a land model is normally scored ----------
    # The emulator integrates daily (only the soil-heat substep is sub-daily), so the operationally
    # relevant score is the daily mean, not the half-hour. Days are kept only when >=5/6 of their steps
    # survived the completeness filter — the same `daily_ok` rule the PLUMBER2 loader applies.
    add("")
    add("  DAILY MEANS (the model's native step; days with ≥5/6 of their steps present)")
    steps_per_day = round(Int, 1440 / parse(Int, meta["timestep_min"]))
    keys_day = Dict{Tuple{Int, Int}, Vector{Int}}()
    for i in eachindex(tbl["year"])
        push!(get!(keys_day, (Int(tbl["year"][i]), Int(tbl["doy"][i])), Int[]), i)
    end
    dmod = Float64[]; dobs = Float64[]; dband = Float64[]; dtsm = Float64[]; dtso = Float64[]
    for (_k, idx) in keys_day
        length(idx) >= ceil(Int, 5 * steps_per_day / 6) || continue
        push!(dmod, sum(res.h[i] for i in idx) / length(idx))
        push!(dobs, sum(tbl["h_obs"][i] for i in idx) / length(idx))
        b = filter(isfinite, [tbl["h_uc"][i] for i in idx])
        push!(dband, isempty(b) ? NaN : sum(b) / length(b))
        tsm = [res.t_skin[i] for i in idx]
        tso = filter(isfinite, [tbl["t_skin_obs"][i] for i in idx])
        push!(dtsm, sum(tsm) / length(tsm))
        push!(dtso, length(tso) == length(idx) ? sum(tso) / length(tso) : NaN)
    end
    add("    H daily  $(fmt(skill(dmod, dobs)))")
    if any(isfinite, dband)
        okd = findall(i -> isfinite(dband[i]), eachindex(dband))
        inside = count(i -> abs(dmod[i] - dobs[i]) <= dband[i], okd)
        add(
            "    H daily INSIDE the |h_cor_uc| day-mean band: " *
                "$(round(100 * inside / max(length(okd), 1), digits = 1))% of $(length(okd)) days " *
                "(mean band ±$(round(sum(dband[okd]) / max(length(okd), 1), digits = 2)) W/m²)"
        )
    end
    any(isfinite, dtso) && add("    T_skin daily  $(fmt(skill(dtsm, dtso)))")

    # ---- the stability question SEBParams itself flags ----------------------------------------------
    add("")
    add(
        "  STABILITY CORRECTION — `SEBParams` says to validate `stab_amp`/`stab_k` against PLUMBER2 before " *
            "trusting nocturnal H. DIAGNOSTIC ONLY (a default change is an integration point with line M):"
    )
    off = run_site(tbl, meta; enable_stability = false)
    add("    ON  (default 0.75/15) night $(fmt(skill(subset(res.h, night), subset(tbl["h_obs"], night))))")
    add("    OFF (neutral g_a)     night $(fmt(skill(subset(off.h, night), subset(tbl["h_obs"], night))))")
    add("    ON  day  $(fmt(skill(subset(res.h, day), subset(tbl["h_obs"], day))))")
    add("    OFF day  $(fmt(skill(subset(off.h, day), subset(tbl["h_obs"], day))))")
    if get(ENV, "STAB_SWEEP", "0") == "1"
        add("    sweep (RMSE all / night, W/m²):")
        for amp in (0.25, 0.5, 0.75, 0.9), k in (5.0, 15.0, 30.0)
            r = run_site(tbl, meta; stab_amp = amp, stab_k = k)
            add(
                "      amp=$(rpad(amp, 4)) k=$(rpad(k, 4))  " *
                    "all RMSE $(round(skill(r.h, tbl["h_obs"]).rmse, digits = 3))   " *
                    "night RMSE $(round(skill(subset(r.h, night), subset(tbl["h_obs"], night)).rmse, digits = 3))"
            )
        end
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
        "Component E — P2 validation, EXPERIMENT A: the closure alone, tower-forced (line E, milestone E4)",
        "drive dir: $DRIVE_DIR",
        "LE is F's number (`components/fast.jl:236` forms λ·ET), so this scores E's OWN outputs — H, T_skin, G",
        "— by feeding the closure the TOWER's LE. Sites: $(join(sites, ", "))",
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
    dest = get(ENV, "OUT", joinpath(DRIVE_DIR, "e4_experimentA_report.txt"))
    write(dest, text)
    println("\nreport: $dest")
    return nothing
end

main()
