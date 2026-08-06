# Online transient bioclimatic boundary — the coupled-run "Climbuf" (ADR 0026/0027; the online counterpart
# of the offline `boundary_series`). docs/notes/online_transient_boundary_climbuf.md is the design of record.
#
# Offline (ADR 0026), Component S reads a pre-baked per-(cell,year) boundary vector; online, climate evolves
# as the coupled run proceeds, so the two TIME-VARYING boundary axes (`gdd5`, `tas_cold_month`) must be
# recomputed each year from the temperature F actually consumes — otherwise the establishment gate freezes at
# the initial climatology (the static case ADR 0027 keeps only as the fallback). `ClimBuf` is a per-cell
# trailing-W-year climate buffer that mirrors LPJmL-FIT's own ~20-yr `Climbuf` establishment memory: the
# driver accumulates daily temperature into calendar-month buckets, finalizes one monthly-mean row per model
# year into a ring, and each year end recomputes `gdd5`/`tas_cold_month` from the trailing-window monthly
# climatology — the EXACT quantities `scripts/build_transient_boundary.py` bakes offline (Thom-1966 monthly
# GDD_5 + coldest monthly mean over a W-year window), so train (offline table) and inference (online loop)
# stay consistent (ADR 0023). Cost is negligible (~a few thousand FLOPs/cell/yr vs F's millions); zero deps;
# it is a CONDITIONING feature only — it touches no carbon/water/energy, so it cannot affect conservation.
#
# Relationship to `SharedState`: `state.jl` already scaffolds the LPJmL Climbuf MIRROR fields
# (`climbuf_mtemp20`/`climbuf_mprec20`/`climbuf_atemp_mean20`, window `CLIMBUFSIZE == 20`) as inert Phase-0
# placeholders. `ClimBuf` here is the ACTIVE online mechanism that produces the S establishment boundary; its
# window climatology (`climbuf_window_climatology`) is exactly the quantity `climbuf_mtemp20` would hold. It
# is kept as its own driver-side object (not a `SharedState` field) so S's dependency surface stays minimal
# (S only ever reads `s.boundary`) and the mechanism mirrors the offline `boundary_series` path 1:1; populating
# the `SharedState` mirror from it (so E's soil-temp init can consume the live 20-yr mean) is a clean follow-up.

"noleap days per calendar month — the offline builder's `DPM` (`build_transient_boundary.py`)."
const CLIMBUF_DPM = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

"0-based day-of-year bounds `[0,31,59,…,365]` (`cumsum(DPM)`); month `m` covers 0-based days `[b[m], b[m+1])`."
const CLIMBUF_MONTH_BOUNDS = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365)

"""
    climbuf_month_of(doy) -> Int

Calendar month (1..12) of a 1-based noleap day-of-year `doy` (1..365), matching the offline builder's month
binning (month `m` covers 0-based days `[CLIMBUF_MONTH_BOUNDS[m], CLIMBUF_MONTH_BOUNDS[m+1])`). `doy` outside
`[1,365]` clamps into range (a defensive guard; the coupled driver only calls it for a 365-day year).
"""
function climbuf_month_of(doy::Integer)
    d0 = clamp(Int(doy) - 1, 0, 364)           # 0-based day index
    @inbounds for m in 1:12
        d0 < CLIMBUF_MONTH_BOUNDS[m + 1] && return m
    end
    return 12
end

"""
    ClimBuf{T}

Per-cell trailing-W-year climate buffer for the online transient boundary (ADR 0026/0027). Holds a ring of
the past `filled ≤ W` model years' monthly-mean temperatures (`monthly_ring`, °C), the within-year daily
accumulators (`month_sum`/`month_cnt`, reset each year), a day-of-year cursor, and the boundary-tail indices
of the two time-varying axes it overwrites (`gdd5_idx`/`tcm_idx`, the production contract = 1/2 for the
`[gdd5, tas_cold_month, soil_depth, co2]` tail, `build_slow_runtime_table.py::BOUNDARY_COLS`). Deterministic;
zero-dependency; conditioning-only (no carbon/water/energy). Build with [`ClimBuf`](@ref); drive it via
[`climbuf_accumulate!`](@ref) (daily) + [`climbuf_finalize_year!`](@ref) (year end) + [`climbuf_boundary`](@ref).
"""
mutable struct ClimBuf{T <: AbstractFloat}
    W::Int
    monthly_ring::Matrix{T}       # (W, 12) ring of past years' monthly-mean temperature (°C)
    filled::Int                   # years accumulated so far (< W during spin-up)
    head::Int                     # ring write cursor (1..W, points at the NEXT row to overwrite)
    month_sum::Vector{T}          # (12,) running sum of daily T in each calendar month, current year
    month_cnt::Vector{Int}        # (12,) day count per month, current year
    gdd5_idx::Int
    tcm_idx::Int
end

"""
    ClimBuf{T}(; W=CLIMBUFSIZE, gdd5_idx=1, tcm_idx=2) -> ClimBuf
    ClimBuf(; W=CLIMBUFSIZE, gdd5_idx=1, tcm_idx=2)    -> ClimBuf{Float64}

Construct an EMPTY Climbuf: a `W`-year ring, no years filled yet. `W` defaults to `CLIMBUFSIZE` (20 yr,
mirroring FIT's Climbuf and the offline builder's default; `W→∞` recovers the static boundary). Seed the ring with a spin-up climatology via
[`climbuf_seed!`](@ref) so year 1 already sees a full window (matching how the offline `boundary_series`
uses a trailing window of PRE-run climate for the earliest target years); an unseeded buffer uses a
shrinking window during its first `< W` years (the offline builder's short-window edge, ADR 0026 §2).
"""
function ClimBuf{T}(; W::Integer = CLIMBUFSIZE, gdd5_idx::Integer = 1, tcm_idx::Integer = 2) where {T <: AbstractFloat}
    W >= 1 || error("ClimBuf: W must be ≥ 1 (got $W)")
    return ClimBuf{T}(
        Int(W), zeros(T, Int(W), 12), 0, 1, zeros(T, 12), zeros(Int, 12), Int(gdd5_idx), Int(tcm_idx),
    )
end
ClimBuf(; kwargs...) = ClimBuf{Float64}(; kwargs...)

"""
    climbuf_push_monthly!(cb::ClimBuf, Tm) -> cb

Push one year's 12-vector of monthly-mean temperatures `Tm` (°C) into the ring (advancing `head`/`filled`,
overwriting the oldest row once full — a sliding W-year window). The low-level ring write shared by
[`climbuf_finalize_year!`](@ref) and [`climbuf_seed!`](@ref).
"""
function climbuf_push_monthly!(cb::ClimBuf{T}, Tm::AbstractVector) where {T}
    length(Tm) == 12 || error("climbuf_push_monthly!: Tm must have length 12 (got $(length(Tm)))")
    @inbounds for m in 1:12
        cb.monthly_ring[cb.head, m] = convert(T, Tm[m])
    end
    cb.head = cb.head == cb.W ? 1 : cb.head + 1
    cb.filled = min(cb.filled + 1, cb.W)
    return cb
end

"""
    climbuf_seed!(cb::ClimBuf, monthly_rows) -> cb

Seed the ring from a spin-up climatology: push each 12-vector in `monthly_rows` (an iterable of per-year
monthly-mean rows, OLDEST first) so the coupled cold start already has a trailing window (design sketch
§Spin-up). Pushing the W years ending just before the run's first model year makes year 1's online boundary
reproduce the offline `boundary_series`'s first row (whose window is that same pre-run climate).
"""
function climbuf_seed!(cb::ClimBuf, monthly_rows)
    for Tm in monthly_rows
        climbuf_push_monthly!(cb, Tm)
    end
    return cb
end

"""
    climbuf_accumulate!(cb::ClimBuf, temp_C, doy) -> cb

Accumulate one day's mean temperature `temp_C` (**°C** — the driver converts F's Kelvin `forcing.tair` by
`tair - 273.15`, matching F's own `components/fast.jl` conversion) into the calendar-month bucket of the
1-based noleap day `doy`. One add + one count per day.
"""
function climbuf_accumulate!(cb::ClimBuf{T}, temp_C, doy::Integer) where {T}
    m = climbuf_month_of(doy)
    @inbounds cb.month_sum[m] += convert(T, temp_C)
    @inbounds cb.month_cnt[m] += 1
    return cb
end

"""
    climbuf_finalize_year!(cb::ClimBuf) -> Vector{T}

Close the current model year: reduce the daily accumulators to this year's 12 monthly means (`month_sum ./
month_cnt`), push them into the ring, RESET the accumulators, and return the monthly-mean row. Call once per
model year AFTER the last day and BEFORE reading the boundary, so the trailing window includes this year (the
offline builder's window `[Y-W+1, Y]` is inclusive of the target year `Y`). A month with no accumulated days
(a partial/degenerate year) contributes `0.0` — the driver only calls this after a full 365-day year.
"""
function climbuf_finalize_year!(cb::ClimBuf{T}) where {T}
    Tm = Vector{T}(undef, 12)
    @inbounds for m in 1:12
        Tm[m] = cb.month_cnt[m] > 0 ? cb.month_sum[m] / cb.month_cnt[m] : zero(T)
    end
    climbuf_push_monthly!(cb, Tm)
    fill!(cb.month_sum, zero(T))
    fill!(cb.month_cnt, 0)
    return Tm
end

"""
    climbuf_window_climatology(cb::ClimBuf) -> Vector{T}

The trailing-window monthly-mean climatology: the mean over the `filled` ring rows (the last `min(years, W)`
model years) — the online equivalent of the offline builder's `mby[lo:iY+1].mean(axis=0)` (mean of the
per-year monthly means over the window). Errors if no year has been finalized yet.
"""
function climbuf_window_climatology(cb::ClimBuf{T}) where {T}
    cb.filled > 0 || error("climbuf_window_climatology: no year finalized yet (filled=0)")
    clim = zeros(T, 12)
    @inbounds for r in 1:cb.filled, m in 1:12
        clim[m] += cb.monthly_ring[r, m]
    end
    inv = one(T) / cb.filled
    @inbounds for m in 1:12
        clim[m] *= inv
    end
    return clim
end

"""
    climbuf_gdd5_tcm(cb::ClimBuf) -> (gdd5, tas_cold_month)

Recompute the two time-varying boundary axes from the trailing-window monthly climatology, bit-for-method
identical to `build_transient_boundary.py::gdd5_tcm`: Thom-1966 monthly growing-degree-days above 5 °C
`gdd5 = Σ_m max(T_m − 5, 0) · DPM[m]` and the coldest monthly mean `tas_cold_month = min_m T_m`. Both in the
buffer's `T` (use `ClimBuf{Float32}` to match the offline builder's float32 reduction most closely).
"""
function climbuf_gdd5_tcm(cb::ClimBuf{T}) where {T}
    clim = climbuf_window_climatology(cb)
    gdd5 = zero(T)
    tcm = typemax(T)
    @inbounds for m in 1:12
        gdd5 += max(clim[m] - T(5), zero(T)) * T(CLIMBUF_DPM[m])
        clim[m] < tcm && (tcm = clim[m])
    end
    return (gdd5, tcm)
end

"""
    climbuf_boundary(cb::ClimBuf, template) -> Vector{Float64}

Return a COPY of the boundary-tail `template` (the emulator's current `s.boundary` = the per-cell static
tail, e.g. `[gdd5, tas_cold_month, soil_depth, co2]`) with only the two time-varying axes overwritten by the
freshly recomputed window `gdd5`/`tas_cold_month` (at `cb.gdd5_idx`/`cb.tcm_idx`); the static components
(`soil_depth`, `co2`) pass through unchanged (ADR 0004: co2 constant). Always `Float64` (the DRF/copula
conditioning channel). This is what the coupled driver assigns to `s.boundary` each year end BEFORE
`reconcile_demography!` builds the feature row.
"""
function climbuf_boundary(cb::ClimBuf, template::AbstractVector)
    b = collect(Float64, template)
    (gdd5, tcm) = climbuf_gdd5_tcm(cb)
    b[cb.gdd5_idx] = Float64(gdd5)
    b[cb.tcm_idx] = Float64(tcm)
    return b
end
