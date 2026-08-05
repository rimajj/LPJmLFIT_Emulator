#!/usr/bin/env julia
# =====================================================================================================
# e_seb_drive_common.jl — shared helpers for driving Component E off the PLUMBER2 "seb_drive" tables.
#
# These readers / metrics / geometry helpers are EXTRACTED VERBATIM from `e_nocturnal_h_decomp.jl` (which
# in turn matches `validate_e_seb_vs_plumber2.jl`) so that every probe reports numbers on the same basis
# and a new probe can be checked against the published ADR 0072 / ADR 0073 values as a harness check.
# The two older scripts keep their own inline copies deliberately: they are the frozen artifacts behind
# ADR 0072 / 0073 and are not worth the churn. NEW probes should `include` this file instead of copying.
#
# Not a test file, not a module — `include(joinpath(@__DIR__, "e_seb_drive_common.jl"))`.
# Skill: `plumber2-reference`. Table generator: `scripts/build_e_seb_validation_table.py`.
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

# ---- metrics (identical definitions to the two older scripts, so numbers are comparable) -------------
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

# ---- geometry, matching `aerodynamic_conductance` exactly --------------------------------------------
"The two log-law factors `(lm, lh)` and `z−d` for a site, computed exactly as `aerodynamic_conductance` does."
function loglaw(z0m, height, z_ref)
    z0m_e = max(z0m, 0.01)
    d = 0.67 * max(height, 0.0)
    z = max(z_ref, d + z0m_e + 2.0)
    return (log((z - d) / z0m_e), log((z - d) / (Z0H_RATIO * z0m_e)), z - d)
end

"""
Run the STATELESS `solve_seb` over every row of a site's driving table, using the table's own precomputed
`t_soil` column (a τ=30 d EWMA of daily-mean Tair) as the ground reference — i.e. the default
single-conductance ground-heat form. `params_kwargs` are forwarded to `SEBParams` (e.g. `lambda_g = 1.0`).
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

"""
Aggregate a driving table to DAILY means, keeping only days with ≥5/6 of their steps present — the
model's native step (`run.jl::couple_day!` calls `solve!` once per day). Returns `(dtbl, dayidx)` with
`dayidx` the sorted `(year, doy)` keys, so a stateful driver can step the days in calendar order.
"""
function aggregate_daily(tbl, meta; cols = nothing)
    steps_per_day = round(Int, 1440 / parse(Int, meta["timestep_min"]))
    need = ceil(Int, 5 * steps_per_day / 6)
    keys_day = Dict{Tuple{Int, Int}, Vector{Int}}()
    for i in eachindex(tbl["year"])
        push!(get!(keys_day, (Int(tbl["year"][i]), Int(tbl["doy"][i])), Int[]), i)
    end
    dayidx = sort([k for (k, v) in keys_day if length(v) >= need])
    want = cols === nothing ?
        (
            "swdown", "lwdown", "tair", "psurf", "wind", "albedo", "t_soil", "le_in",
            "h_obs", "rn_obs", "g_obs", "t_skin_obs",
        ) :
        cols
    dmean(col) = [nanmean([tbl[col][i] for i in keys_day[k]]) for k in dayidx]
    dtbl = Dict{String, Vector{Float64}}(c => dmean(c) for c in want if haskey(tbl, c))
    return (dtbl, dayidx)
end
