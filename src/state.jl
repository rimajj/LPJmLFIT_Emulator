# Shared state vector — the single source of truth (DESIGN.md §2, START_HERE rule 1).
# Dimensions are keyed to LPJmL-FIT constants verified in DESIGN.md §2.1.

"Number of soil layers (LPJmL `NSOILLAYER`, `include/soil.h:30`). Thicknesses [200,300,500,1000×19,3000] mm."
const NSOILLAYER = 23
"Index of the last SOM layer (LPJmL `LASTLAYER = NSOILLAYER-1`, `soil.h:32`)."
const LASTLAYER = NSOILLAYER - 1
"Heat-conduction gridpoints per soil layer (LPJmL `GPLHEAT`, `soil.h:38`)."
const GPLHEAT = 1
"""
    NHEATGRIDP

Thermal grid size (LPJmL `NHEATGRIDP = NSOILLAYER*GPLHEAT`, `soil.h:41`). Equals 23 only because
`GPLHEAT==1`; the emulator's thermal dimension is keyed to this, never a literal 23 (a `GPLHEAT>1`
build changes it).
"""
const NHEATGRIDP = NSOILLAYER * GPLHEAT
"Per-tree carbon(+N) pools (LPJmL `Treephys2`, `tree.h:48-51`): leaf, sapwood, heartwood, root, sapwood_bg, heartwood_bg, debt."
const NTREEPOOLS = 7
"Running-climate-memory window in years (LPJmL `CLIMBUFSIZE`, `climbuf.h:20`)."
const CLIMBUFSIZE = 20
"Months per year."
const NMONTH = 12

"""
    SharedState{T<:AbstractFloat}

The one authoritative copy of every prognostic state, mirroring the LPJmL-FIT structs
(DESIGN.md §2). F owns/integrates soil water, snow, soil thermal, and the SOM/litter pools;
S owns the vegetation distribution and *allocates* into vegetation carbon. **No component keeps
a private copy.**

This Phase-0 type fixes the shapes/units; field physics grows with the components. Vegetation is
represented by S as a *distribution* over trees (see [`AbstractSlowEmulator`](@ref)), summarised
here by aggregate pools until the distribution machinery lands.

# Fields (units)
- `w::Vector{T}`         soil water per layer, fraction of WHC   `[NSOILLAYER]`
- `w_fw::Vector{T}`      free/gravitational water, mm            `[NSOILLAYER]`
- `w_evap::T`            evaporation-layer water, mm
- `rw_buffer::T`         rainwater buffer, mm
- `snowpack::T`          snow water equivalent, mm
- `enth::Vector{T}`      volumetric soil enthalpy, J/m³ (fundamental thermal state) `[NHEATGRIDP]`
- `som_fast::Vector{T}`  fast SOM carbon per layer, gC/m²        `[LASTLAYER]`
- `som_slow::Vector{T}`  slow SOM carbon per layer, gC/m²        `[LASTLAYER]`
- `litc::T`              litter carbon, gC/m²
- `vegc::T`              vegetation carbon (aggregate), gC/m²
- `climbuf_mtemp20::Vector{T}` 20-yr mean monthly temperature, °C `[NMONTH]`
- `climbuf_mprec20::Vector{T}` 20-yr mean monthly precip, mm      `[NMONTH]`
- `climbuf_atemp_mean20::T`    20-yr mean annual temperature, °C
"""
struct SharedState{T <: AbstractFloat}
    w::Vector{T}
    w_fw::Vector{T}
    w_evap::T
    rw_buffer::T
    snowpack::T
    enth::Vector{T}
    som_fast::Vector{T}
    som_slow::Vector{T}
    litc::T
    vegc::T
    climbuf_mtemp20::Vector{T}
    climbuf_mprec20::Vector{T}
    climbuf_atemp_mean20::T
end

# Explicit keyword constructors (NOT `Base.@kwdef`): the `@kwdef`-generated zero-parameter
# constructor would evaluate `zeros(T, …)` defaults with `T` unbound (a real bug JET caught), and
# patching it with an extra method triggers "method overwriting during precompilation". These two
# constructors keep `T` bound and add no duplicate: `SharedState{T}(; …)` and the default-eltype
# `SharedState(; …) ≡ SharedState{Float64}(; …)`.
function SharedState{T}(;
        w = zeros(T, NSOILLAYER),
        w_fw = zeros(T, NSOILLAYER),
        w_evap = zero(T),
        rw_buffer = zero(T),
        snowpack = zero(T),
        enth = zeros(T, NHEATGRIDP),
        som_fast = zeros(T, LASTLAYER),
        som_slow = zeros(T, LASTLAYER),
        litc = zero(T),
        vegc = zero(T),
        climbuf_mtemp20 = zeros(T, NMONTH),
        climbuf_mprec20 = zeros(T, NMONTH),
        climbuf_atemp_mean20 = zero(T)
    ) where {T <: AbstractFloat}
    return SharedState{T}(
        w, w_fw, w_evap, rw_buffer, snowpack, enth, som_fast, som_slow,
        litc, vegc, climbuf_mtemp20, climbuf_mprec20, climbuf_atemp_mean20
    )
end

SharedState(; kwargs...) = SharedState{Float64}(; kwargs...)

"""
    checkdims(s::SharedState)

Validate that a [`SharedState`](@ref) has the frozen array shapes. Returns `true` or throws
`DimensionMismatch` — used by data-validation tests (ENGINEERING_STANDARDS §2 gate 6).
"""
function checkdims(s::SharedState)
    length(s.w) == NSOILLAYER || throw(DimensionMismatch("w must be length NSOILLAYER=$(NSOILLAYER)"))
    length(s.w_fw) == NSOILLAYER || throw(DimensionMismatch("w_fw must be length NSOILLAYER"))
    length(s.enth) == NHEATGRIDP || throw(DimensionMismatch("enth must be length NHEATGRIDP=$(NHEATGRIDP)"))
    length(s.som_fast) == LASTLAYER || throw(DimensionMismatch("som_fast must be length LASTLAYER=$(LASTLAYER)"))
    length(s.som_slow) == LASTLAYER || throw(DimensionMismatch("som_slow must be length LASTLAYER"))
    length(s.climbuf_mtemp20) == NMONTH || throw(DimensionMismatch("climbuf_mtemp20 must be length NMONTH=$(NMONTH)"))
    length(s.climbuf_mprec20) == NMONTH || throw(DimensionMismatch("climbuf_mprec20 must be length NMONTH"))
    return true
end
