# Two-way coupling of SpeedyWeather.jl (0.23) to the learned LPJmL-FIT emulator (ADR 0345).
#
#   atmosphere -> land: each land column's daily mean surface air temperature, precipitation (rain + snow),
#                       downward shortwave, net longwave and lowest-level humidity, accumulated every time step;
#   land -> atmosphere: the emulator's daily evapotranspiration (interception + transpiration + soil
#                       evaporation) as the land surface humidity flux, held constant over the following day.
#                       SpeedyWeather's land energy balance takes its latent-heat cooling from that same flux;
#                       optionally (ALBEDO = emulator) the land albedo from the emulator's tree cover, grass cover
#                       and snow, and (ROUGH = emulator) the land roughness length from its tree/grass cover.
#
# The emulator is the released Python package (python/src/lpjmlfit_emulator/landemu), called through PythonCall
# once per simulated day; scripts/online_coupling/landemu_coupler.py builds its start state and records everything
# it saw, so `landemu_coupler.py replay` can prove offline that the coupled emulator is the released one.
#
# Env knobs: MODE = coupled | control (control = SpeedyWeather's own land evaporation, same diagnostics) ·
#            YEARS (default 2) · TRUNC (31) · NLAYERS (8) · OUT (record directory, on /p/projects) ·
#            MAXDEG (3.0, largest distance from a column centre to the emulator cell that represents it) ·
#            DIURNAL = flat | sun (how a day's ET is spread over its time steps: constant, or in proportion to
#            the cosine of the solar zenith angle; both hand over exactly the day's total) ·
#            OCEAN = slab | prescribed (SpeedyWeather's default free-running 50 m slab ocean, or its seasonal
#            sea-surface-temperature climatology: the test of how much of its cold land comes from the ocean) ·
#            ALBEDO = speedy | emulator · ROUGH = speedy | emulator (coupled only; ADR 0346) ·
#            Z0_HIGH / Z0_LOW / Z0_BARE (roughness lengths of tree, grass and bare cover, m; 2.0 / 0.2 / 0.013) ·
#            AIR = model | 2m (the air temperature the emulator is fed: SpeedyWeather's surface air temperature, which in
#            an inversion is the lowermost layer's ~550 m up, or the diagnostic 2 m air temperature of speedy_air2m.jl;
#            the 2 m value is recorded either way, daily_means column 12) ·
#            the atmosphere fixes of the SpeedyWeather cold-bias side track (branch coldfix-E; run with
#            PROJ=/p/tmp/jamirp/speedy_landemu_fix_env, see sbatch_speedy_landemu.sh), same knobs as
#            speedy_cold_bias_repro.jl: LW = grey | fourband (+ LWKW, CLOUDKW, SWKW = "name=value,..."),
#            CONVKW (BettsMillerConvection / LinearEntrainment parameters, e.g. "ascent_substeps=10,entrainment_mse=1"),
#            T0 = speedy (surface air temperature from the actual lapse rate). All unset = the stock model.
# Every run also records per land column the land albedo, sensible heat flux, top soil temperature, SpeedyWeather's
# own snow and the column's orography, and global daily means + yearly fields of air and sea-surface temperature and
# sea ice, so a run can be scored for SpeedyWeather's own climate drift (scripts/online_coupling/diagnose_speedy_climate.py).
# Run with scripts/online_coupling/sbatch_speedy_landemu.sh (one core; PythonCall uses conda env py311_new).

using SpeedyWeather, PythonCall, Dates, Printf
import SpeedyWeather: initialize!, variables, callback!, finalize!, surface_humidity_flux!, albedo!, surface_roughness!

const MODE = Symbol(get(ENV, "MODE", "coupled"))
const YEARS = parse(Int, get(ENV, "YEARS", "2"))
const TRUNC = parse(Int, get(ENV, "TRUNC", "31"))
const NLAYERS = parse(Int, get(ENV, "NLAYERS", "8"))
const MAXDEG = parse(Float64, get(ENV, "MAXDEG", "3.0"))
const DIURNAL = Symbol(get(ENV, "DIURNAL", "flat"))
const OCEAN = Symbol(get(ENV, "OCEAN", "slab"))
const ALBEDO = Symbol(get(ENV, "ALBEDO", "speedy"))
const ROUGH = Symbol(get(ENV, "ROUGH", "speedy"))
const Z0 = (
    high = parse(Float64, get(ENV, "Z0_HIGH", "2.0")), low = parse(Float64, get(ENV, "Z0_LOW", "0.2")),
    bare = parse(Float64, get(ENV, "Z0_BARE", "0.013")),
)
const AIR = Symbol(get(ENV, "AIR", "model"))
const LW = Symbol(get(ENV, "LW", "grey"))
parsekw(s) = isempty(s) ? (;) : NamedTuple(
        Symbol(k) => (v in ("true", "false") ? v == "true" : parse(Float64, v))
        for (k, v) in (split(x, '=') for x in split(s, ','))
    )
const LWKW, CLOUDKW, SWKW, CONVKW = (parsekw(get(ENV, k, "")) for k in ("LWKW", "CLOUDKW", "SWKW", "CONVKW"))
const T0 = get(ENV, "T0", "")
const START = DateTime(2015, 1, 1)
const SUFFIX = string(
    DIURNAL == :sun && MODE == :coupled ? "_sun" : "", OCEAN == :prescribed ? "_sst" : "",
    ALBEDO == :emulator ? "_alb" : "", ROUGH == :emulator ? "_z0" : "", AIR == Symbol("2m") ? "_t2m" : "",
    LW == :fourband ? "_lw4" : "", isempty(CONVKW) ? "" : "_conv"
)
const OUT = get(ENV, "OUT", "/p/projects/open/Jamir/esm_land_emulator_data/coupled/speedy_t$(TRUNC)_$(MODE)$(SUFFIX)_$(YEARS)y")
@assert MODE in (:coupled, :control) && DIURNAL in (:flat, :sun) && OCEAN in (:slab, :prescribed)
@assert ALBEDO in (:speedy, :emulator) && ROUGH in (:speedy, :emulator)
@assert AIR in (:model, Symbol("2m")) && LW in (:grey, :fourband) && T0 in ("", "speedy")
@assert MODE == :coupled || (ALBEDO == :speedy && ROUGH == :speedy) "the emulator channels need MODE=coupled"
println(
    "run_speedy_landemu: MODE=$MODE YEARS=$YEARS TRUNC=$TRUNC NLAYERS=$NLAYERS MAXDEG=$MAXDEG DIURNAL=$DIURNAL ",
    "OCEAN=$OCEAN ALBEDO=$ALBEDO ROUGH=$ROUGH Z0=$Z0 AIR=$AIR LW=$LW LWKW=$LWKW CLOUDKW=$CLOUDKW SWKW=$SWKW ",
    "CONVKW=$CONVKW T0=$(isempty(T0) ? "dry adiabat" : T0) OUT=$OUT"
)
println("SpeedyWeather ", pkgversion(SpeedyWeather), " at ", pkgdir(SpeedyWeather), "  threads=", Threads.nthreads()); flush(stdout)
include(joinpath(@__DIR__, "speedy_air2m.jl"))   # air_2m(ij, vars, model, soilT) [K]

# ---------------------------------------------------------------------------------------------- land evaporation
"""Land surface humidity flux: the emulator's daily evapotranspiration where `use[ij]`, SpeedyWeather's own bulk
formula (`bulk`) elsewhere. `flux` [kg/m²/s] is written once per day by `LandEmuCallback`."""
struct EmulatorLandHumidityFlux{NF, B} <: SpeedyWeather.AbstractSurfaceHumidityFlux
    bulk::B
    use::Vector{Bool}
    flux::Vector{NF}
end
EmulatorLandHumidityFlux(SG::SpectralGrid) =
    EmulatorLandHumidityFlux(SurfaceLandHumidityFlux(SG), fill(false, SG.npoints), zeros(SG.NF, SG.npoints))
variables(h::EmulatorLandHumidityFlux) = variables(h.bulk)
initialize!(h::EmulatorLandHumidityFlux, model::PrimitiveWet) = initialize!(h.bulk, model)

@inline function surface_humidity_flux!(ij, vars, h::EmulatorLandHumidityFlux, model)
    h.use[ij] || return surface_humidity_flux!(ij, vars, h.bulk, model)
    # as SpeedyWeather's PrescribedLandHumidityFlux, with the flux from the emulator
    land_fraction = model.land_sea_mask.land_fraction[ij]
    pₛ = vars.parameterizations.surface_pressure[ij]
    surface = model.geometry.nlayers
    flux_land = h.flux[ij]
    vars.parameterizations.land.surface_humidity_flux[ij] = flux_land     # unweighted, used by the land model
    flux_land *= land_fraction
    vars.parameterizations.surface_humidity_flux[ij] += flux_land
    dqdt = SpeedyWeather.get_tendency_step(vars.tendencies.grid.humidity, model.time_stepping, h)
    dqdt[ij, surface] += SpeedyWeather.surface_flux_to_tendency(flux_land, pₛ, model)
    return nothing
end

# ---------------------------------------------------------------------------------------------- land albedo
"""Land albedo: SpeedyWeather's own `LandSnowAlbedo` formula (bare land, high and low vegetation, plus snow
cover), but where `use[ij]` with the emulator's tree cover (`high`), grass cover (`low`) and snow water equivalent
(`snow`, m) instead of SpeedyWeather's vegetation climatology and its own snow. Set once per day by `LandEmuCallback`."""
struct EmulatorLandAlbedo{NF, B} <: SpeedyWeather.AbstractAlbedo
    base::B
    use::Vector{Bool}
    high::Vector{NF}
    low::Vector{NF}
    snow::Vector{NF}
end
EmulatorLandAlbedo(SG::SpectralGrid) = EmulatorLandAlbedo(
    LandSnowAlbedo(SG), fill(false, SG.npoints), zeros(SG.NF, SG.npoints), zeros(SG.NF, SG.npoints), zeros(SG.NF, SG.npoints)
)
variables(a::EmulatorLandAlbedo) = variables(a.base)
initialize!(a::EmulatorLandAlbedo, model::SpeedyWeather.PrimitiveEquation) = initialize!(a.base, model)

@inline function albedo!(ij, albedo, vars, a::EmulatorLandAlbedo, model)
    a.use[ij] || return albedo!(ij, albedo, vars, a.base, model)
    b = a.base
    high, low = a.high[ij], a.low[ij]
    albedo[ij] = high * b.albedo_high_vegetation + low * b.albedo_low_vegetation + b.albedo_land * (1 - high - low)
    albedo[ij] += b.snow_cover(a.snow[ij], b.snow_depth_scale) * b.albedo_snow
    return nothing
end

# ---------------------------------------------------------------------------------------------- land roughness
"""Surface roughness length: as SpeedyWeather's `ConstantSurfaceRoughness` (0.5 m on all land), but where
`use[ij]` the land roughness `z0[ij]` from the emulator's tree / grass / bare cover (`Z0`, blended in log space,
which is what the drag coefficient ∝ 1/ln(z/z₀)² sees). Set once per year by `LandEmuCallback`."""
struct EmulatorSurfaceRoughness{NF, B} <: SpeedyWeather.AbstractSurfaceRoughness
    base::B
    use::Vector{Bool}
    z0::Vector{NF}
end
EmulatorSurfaceRoughness(SG::SpectralGrid) =
    EmulatorSurfaceRoughness(ConstantSurfaceRoughness(SG), fill(false, SG.npoints), fill(SG.NF(0.5), SG.npoints))
initialize!(::EmulatorSurfaceRoughness) = nothing
initialize!(::EmulatorSurfaceRoughness, ::SpeedyWeather.PrimitiveEquation) = nothing

@inline function surface_roughness!(ij, vars, r::EmulatorSurfaceRoughness, land_sea_mask)
    land_fraction = land_sea_mask.land_fraction[ij]
    z₀_land = r.use[ij] ? r.z0[ij] : r.base.roughness_length_land
    z₀_ocean = r.base.roughness_length_ocean
    (; land, ocean) = vars.parameterizations
    land.surface_roughness[ij] = ifelse(land_fraction > 0, z₀_land, zero(z₀_land))
    ocean.surface_roughness[ij] = ifelse(land_fraction < 1, z₀_ocean, zero(z₀_ocean))
    vars.parameterizations.surface_roughness[ij] = land_fraction * land.surface_roughness[ij] +
        (1 - land_fraction) * ocean.surface_roughness[ij]
    return nothing
end

"""Land roughness length [m] of a column with tree cover `h` and grass cover `l` (the rest bare), log blend."""
z0_of(h, l) = exp(h * log(Z0.high) + l * log(Z0.low) + max(1 - h - l, 0) * log(Z0.bare))

# ---------------------------------------------------------------------------------------------- the coupler
"""Emulator day of a time: (year, 0-based day of a 365-day year); 29 February is folded into 28 February."""
function emday(t::DateTime)
    d = dayofyear(t) - 1
    (isleapyear(t) && dayofyear(t) >= 60) && (d -= 1)
    return (year(t), d)
end

# accumulated per land column: tas, pr, rsds, lwnet, huss, humidity flux used, land fraction (the first 7 are what
# score_speedy_landemu.py reads), then land albedo, land sensible heat flux [W/m²], top soil temperature [°C] and
# SpeedyWeather's own snow [m water equivalent], diagnostic 2 m air temperature [°C] (speedy_air2m.jl)
const NV = 12
const NG = 5   # global daily means: air temperature (all / land / ocean points), sea-surface temperature, sea ice area

mutable struct LandEmuCallback <: SpeedyWeather.AbstractCallback
    hf::Any                     # EmulatorLandHumidityFlux (coupled) or nothing (control)
    cols::Vector{Int}           # ij of every land column (land fraction > 0)
    emu::Vector{Int}            # positions in cols of the emulated columns
    py::Any                     # Python Coupler (coupled) or nothing
    acc::Matrix{Float64}        # (ncols, NV) sums of the current emulator day
    nacc::Int
    day::Tuple{Int, Int}
    rec::Vector{Matrix{Float32}}  # one (ncols, NV) daily mean per emulator day
    nday_cal::Int               # calendar days completed (for the leap-day accounting)
    applied::Vector{Float64}    # water given to the atmosphere over emulated columns [kg/m²], per emulated column
    produced::Vector{Float64}   # the emulator's ET over the days whose flux has been applied [kg/m²]
    pending::Vector{Float64}    # the emulator's latest ET [kg/m²/day], applied during the current day
    Δt::Float64
    t_py::Float64
    t_start::Float64
    latr::Vector{Float64}       # emulated columns' latitude / longitude [rad] (DIURNAL = sun)
    lonr::Vector{Float64}
    wts::Matrix{Float64}        # (emulated, steps per day): share of the day's ET given in each step, Σ = 1
    jstep::Int                  # step of the current ET day
    alb::Any                    # EmulatorLandAlbedo or nothing
    rough::Any                  # EmulatorSurfaceRoughness or nothing
    wg::Vector{Float64}         # cos(latitude) of every grid point (global means)
    gacc::Vector{Float64}       # global sums of the current emulator day
    grec::Vector{Vector{Float64}}  # one global daily mean per emulator day
    yfld::Array{Float64, 3}     # (npoints, 3, YEARS): yearly sums of air temperature, SST, sea ice
    ny::Vector{Int}             # steps summed per calendar year
    latall::Vector{Float64}     # every grid point: latitude, longitude [deg], land fraction
    lonall::Vector{Float64}
    lfall::Vector{Float64}
    orog::Vector{Float64}       # land columns' orography [m]
end

"""Cosine of the solar zenith angle (simple astronomy: declination from the day of year, hour angle from UTC)."""
function cos_zenith(latr, lonr, t::DateTime)
    δ = -deg2rad(23.44) * cos(2π * (dayofyear(t) + 10) / 365)
    h = 2π * (Dates.value(t - DateTime(Date(t))) / 86_400_000) + lonr - π
    return sin(latr) * sin(δ) + cos(latr) * cos(δ) * cos(h)
end

"""Weights of the next steps-per-day steps starting at `t`: ∝ max(cos zenith, 0), uniform in polar night."""
function day_weights!(cb::LandEmuCallback, t::DateTime)
    nsd = size(cb.wts, 2)
    for m in eachindex(cb.latr)
        for j in 1:nsd
            cb.wts[m, j] = DIURNAL == :sun ?
                max(cos_zenith(cb.latr[m], cb.lonr[m], t + Millisecond(round(Int, (j - 0.5) * cb.Δt * 1000))), 0.0) : 1.0
        end
        s = sum(@view cb.wts[m, :])
        s > 0 ? (cb.wts[m, :] ./= s) : (cb.wts[m, :] .= 1 / nsd)
    end
    return nothing
end

function set_flux!(cb::LandEmuCallback)
    nsd = size(cb.wts, 2)
    j = mod1(cb.jstep, nsd)               # 29 February repeats the day's shape
    for (m, k) in enumerate(cb.emu)
        cb.hf.flux[cb.cols[k]] = cb.pending[m] / 86400 * nsd * cb.wts[m, j]
    end
    return nothing
end

function initialize!(cb::LandEmuCallback, vars, model)
    cb.Δt = model.time_stepping.Δt_millisec.value / 1000
    nsd = round(Int, 86400 / cb.Δt)
    @assert nsd * cb.Δt == 86400 "time step does not divide a day"
    cb.wts = ones(length(cb.emu), nsd) ./ nsd
    cb.day = emday(vars.prognostic.clock.time)
    cb.t_start = time()
    println(
        "callback: Δt = $(cb.Δt) s, start $(vars.prognostic.clock.time), $(length(cb.cols)) land columns, ",
        "$(length(cb.emu)) emulated"
    ); flush(stdout)
    return nothing
end

function callback!(cb::LandEmuCallback, vars, model)
    p = vars.parameterizations
    q = SpeedyWeather.get_prognostic_step(vars.grid.humidity, model.time_stepping, cb)
    nl = model.geometry.nlayers
    lf = model.land_sea_mask.land_fraction
    # water given to the atmosphere in the step just taken, with the flux it used (before any update below)
    if cb.hf !== nothing
        @inbounds for (m, k) in enumerate(cb.emu)
            cb.hf.use[cb.cols[k]] && (cb.applied[m] += cb.hf.flux[cb.cols[k]] * cb.Δt)
        end
    end
    t_mid = vars.prognostic.clock.time - Millisecond(round(Int, cb.Δt * 500))   # middle of the step just taken
    d = emday(t_mid)
    if d != cb.day
        finish_day!(cb, vars.prognostic.clock.time)
        cb.day = d
    elseif cb.hf !== nothing && any(cb.hf.use)
        cb.jstep += 1
        set_flux!(cb)                      # the flux for the next step
    end
    cb.nday_cal = Dates.value(Date(t_mid) - Date(START))
    lstep = SpeedyWeather.time_stepper(model.time_stepping, :land)
    ostep = SpeedyWeather.time_stepper(model.time_stepping, :ocean)
    soilT = SpeedyWeather.get_prognostic_step(vars.prognostic.land.soil_temperature, lstep, cb)
    snow = SpeedyWeather.get_prognostic_step(vars.prognostic.land.snow_depth, lstep, cb)
    sst = SpeedyWeather.get_prognostic_step(vars.prognostic.ocean.sea_surface_temperature, ostep, cb)
    ice = SpeedyWeather.get_prognostic_step(vars.prognostic.ocean.sea_ice_concentration, ostep, cb)
    iy = clamp(year(t_mid) - year(START) + 1, 1, size(cb.yfld, 3))
    cb.ny[iy] += 1
    @inbounds for ij in eachindex(cb.wg)
        w, l, ta = cb.wg[ij], lf[ij], p.surface_air_temperature[ij] - 273.15
        cb.gacc[1] += w * ta
        cb.gacc[2] += w * l * ta
        cb.gacc[3] += w * (1 - l) * ta
        cb.gacc[4] += w * (1 - l) * (sst[ij] - 273.15)
        cb.gacc[5] += w * (1 - l) * ice[ij]
        cb.yfld[ij, 1, iy] += ta
        cb.yfld[ij, 2, iy] += sst[ij] - 273.15
        cb.yfld[ij, 3, iy] += ice[ij]
    end
    @inbounds for (k, ij) in enumerate(cb.cols)
        cb.acc[k, 1] += p.surface_air_temperature[ij] - 273.15
        cb.acc[k, 2] += (p.rain_rate[ij] + p.snow_rate[ij]) * 1000 * 86400          # m/s -> mm/day
        cb.acc[k, 3] += p.surface_shortwave_down[ij]
        cb.acc[k, 4] += p.surface_longwave_down[ij] - p.land.surface_longwave_up[ij]
        cb.acc[k, 5] += q[ij, nl]
        cb.acc[k, 6] += p.land.surface_humidity_flux[ij] * 86400                     # kg/m²/s -> mm/day
        cb.acc[k, 7] += lf[ij]
        cb.acc[k, 8] += p.land.albedo[ij]
        cb.acc[k, 9] += p.land.sensible_heat_flux[ij]
        cb.acc[k, 10] += soilT[ij, 1] - 273.15
        cb.acc[k, 11] += snow[ij]
        cb.acc[k, 12] += air_2m(ij, vars, model, soilT) - 273.15
    end
    cb.nacc += 1
    return nothing
end

function finish_day!(cb::LandEmuCallback, t_now::DateTime)
    m = Float32.(cb.acc ./ cb.nacc)
    push!(cb.rec, m)
    if cb.py !== nothing
        F = Float64.(cb.acc[cb.emu, [AIR == :model ? 1 : 12, 2, 3, 4, 5]] ./ cb.nacc)
        t0 = time()
        et = pyconvert(Vector{Float64}, cb.py.day(F))                 # mm/day = kg/m²/day
        cb.t_py += time() - t0
        if any(cb.hf.use)
            cb.produced .+= cb.pending                                  # the ET whose flux was just applied
        end
        cb.pending .= et
        day_weights!(cb, t_now)              # the next steps-per-day steps carry this ET
        cb.jstep = 1
        set_flux!(cb)
        for k in cb.emu
            cb.hf.use[cb.cols[k]] = true                               # day 1 ran on SpeedyWeather's own formula
        end
        (cb.alb !== nothing || cb.rough !== nothing) && set_surface!(cb)
    end
    sw = sum(cb.wg)
    sl = sum(cb.wg .* cb.lfall)
    so = sw - sl
    push!(cb.grec, [cb.gacc[1] / sw, cb.gacc[2] / sl, cb.gacc[3] / so, cb.gacc[4] / so, cb.gacc[5] / so] ./ cb.nacc)
    fill!(cb.gacc, 0)
    fill!(cb.acc, 0)
    cb.nacc = 0
    nd = length(cb.rec)
    if nd % 30 == 0
        el = time() - cb.t_start
        @printf("  emulator day %d (%s): %.0f s elapsed, %.1f s in the emulator\n", nd, string(cb.day), el, cb.t_py)
        flush(stdout)
    end
    return nothing
end

"""The emulator's land surface after the day just computed: tree and grass cover (as of the last completed year) for
the albedo and roughness, snow water equivalent (end of the day, m) for the albedo — used from the next step on."""
function set_surface!(cb::LandEmuCallback)
    S = pyconvert(Matrix{Float64}, cb.py.surface())                   # (emulated, 3): tree, grass cover, snow [m]
    for (m, k) in enumerate(cb.emu)
        ij = cb.cols[k]
        if cb.alb !== nothing
            cb.alb.high[ij], cb.alb.low[ij], cb.alb.snow[ij] = S[m, 1], S[m, 2], S[m, 3]
            cb.alb.use[ij] = true
        end
        if cb.rough !== nothing
            cb.rough.z0[ij] = z0_of(S[m, 1], S[m, 2])
            cb.rough.use[ij] = true
        end
    end
    return nothing
end

function finalize!(cb::LandEmuCallback, vars, model)
    cb.nacc > 0 && finish_day!(cb, vars.prognostic.clock.time)          # close the last day (its ET is produced but never applied)
    wall = time() - cb.t_start
    rec = cat(cb.rec...; dims = 3)                                      # (ncols, NV, days)
    extra = Dict(
        "daily_means" => rec, "cols" => cb.cols, "emu" => cb.emu, "wall" => wall, "t_py" => cb.t_py,
        "applied" => cb.applied, "produced" => cb.produced, "nday_cal" => cb.nday_cal, "dt" => cb.Δt,
        "diurnal" => string(DIURNAL), "ocean" => string(OCEAN), "albedo" => string(ALBEDO), "rough" => string(ROUGH),
        "global_daily" => reduce(hcat, cb.grec), "yearly_fields" => cb.yfld ./ reshape(max.(cb.ny, 1), 1, 1, :),
        "grid_lat" => cb.latall, "grid_lon" => cb.lonall, "grid_landfrac" => cb.lfall, "col_orog" => cb.orog,
        "z0" => [Z0.high, Z0.low, Z0.bare], "air" => string(AIR), "lw" => string(LW),
        "atmos_knobs" => "LWKW=$LWKW CLOUDKW=$CLOUDKW SWKW=$SWKW CONVKW=$CONVKW T0=$T0",
        "speedy_dir" => pkgdir(SpeedyWeather)
    )
    if cb.py !== nothing
        cb.py.finish(pydict(Dict(k => (v isa AbstractArray ? pyimport("numpy").asarray(v) : v) for (k, v) in extra)))
    else
        np = pyimport("numpy")
        mkpath(OUT)
        np.savez(joinpath(OUT, "control_record.npz"); (Symbol(k) => (v isa AbstractArray ? np.asarray(v) : v) for (k, v) in extra)...)
    end
    @printf("finalize: %d emulator days, wall %.0f s, of which emulator %.1f s\n", length(cb.rec), wall, cb.t_py)
    flush(stdout)
    return nothing
end

# ---------------------------------------------------------------------------------------------- build and run
sg = SpectralGrid(truncation = TRUNC + 1, nlayers = NLAYERS)   # T31 = truncation 32 in 0.23
hf = MODE == :coupled ? EmulatorLandHumidityFlux(sg) : nothing
alb = ALBEDO == :emulator ? EmulatorLandAlbedo(sg) : nothing
rough = ROUGH == :emulator ? EmulatorSurfaceRoughness(sg) : nothing
kw = Dict{Symbol, Any}()
hf !== nothing && (kw[:surface_humidity_flux] = SurfaceHumidityFlux(sg; land = hf))
OCEAN == :prescribed && (kw[:ocean] = SeasonalOceanClimatology(sg))   # sea ice then follows the prescribed SST
alb !== nothing && (kw[:albedo] = OceanLandAlbedo(sg; land = alb))
blkw = Dict{Symbol, Any}()
rough !== nothing && (blkw[:surface_roughness] = rough)
T0 == "speedy" && (blkw[:surface_condition] = SurfaceCondition(sg; actual_lapse_rate = true))
isempty(blkw) || (kw[:boundary_layer] = BoundaryLayer(sg; blkw...))
if !isempty(CONVKW)    # as in speedy_cold_bias_repro.jl
    ent = (; (k => v for (k, v) in pairs(CONVKW) if k in (:surface_entrainment, :σ_entrainment))...)
    bm = (; (k => v for (k, v) in pairs(CONVKW) if k == :relative_humidity)...)
    haskey(CONVKW, :ascent_substeps) && (bm = (; bm..., ascent_substeps = round(Int, CONVKW.ascent_substeps)))
    haskey(CONVKW, :entrainment_mse) && (bm = (; bm..., entrainment_mse = CONVKW.entrainment_mse == 1))
    haskey(CONVKW, :time_scale_hours) && (bm = (; bm..., time_scale = Second(round(Int, 3600 * CONVKW.time_scale_hours))))
    kw[:convection] = BettsMillerConvection(sg; entrainment = LinearEntrainment(sg; ent...), bm...)
end
LW == :fourband && (
    kw[:radiation] = Radiation(
        sg;
        shortwave = TwoBandShortwave(
            sg; clouds = DiagnosticClouds(sg; CLOUDKW...), radiative_transfer = TwoBandShortwaveRadiativeTransfer(sg; SWKW...)
        ),
        longwave = FourBandLongwave(sg; LWKW...)
    )
)
model = PrimitiveWetModel(sg; kw...)
println(
    "ocean: ", typeof(model.ocean).name.name, ", albedo: ", typeof(model.albedo.land).name.name,
    ", roughness: ", typeof(model.boundary_layer.surface_roughness).name.name,
    ", radiation: ", typeof(model.radiation.longwave).name.name, ", convection: ", typeof(model.convection).name.name
); flush(stdout)
sim = initialize!(model; time = START)

lf = model.land_sea_mask.land_fraction
cols = findall(>(0), lf.data)
lons, lats = SpeedyWeather.RingGrids.get_londlatds(sg.grid)   # degrees, lon in [0, 360)
py = nothing
emu = Int[]
if MODE == :coupled
    pyimport("sys").path.insert(0, @__DIR__)
    lc = pyimport("landemu_coupler")
    py = lc.Coupler(
        pyimport("numpy").asarray(Float64.(lats[cols])), pyimport("numpy").asarray(Float64.(lons[cols])),
        OUT; max_deg = MAXDEG, start_year = year(START)
    )
    emu = findall(pyconvert(Vector{Bool}, py.mask))
end
ne = length(emu)
npts = length(lf.data)
cb = LandEmuCallback(
    hf, cols, emu, py, zeros(length(cols), NV), 0, (0, 0), Matrix{Float32}[], 0,
    zeros(ne), zeros(ne), zeros(ne), 0.0, 0.0, 0.0,
    deg2rad.(Float64.(lats[cols[emu]])), deg2rad.(Float64.(lons[cols[emu]])), zeros(ne, 1), 0,
    alb, rough, cosd.(Float64.(lats)), zeros(NG), Vector{Float64}[], zeros(npts, 3, YEARS), zeros(Int, YEARS),
    Float64.(lats), Float64.(lons), Float64.(lf.data), Float64.(model.orography.orography.data[cols])
)
add!(model, :landemu => cb)
# the start stand and snow are known before day 1: the albedo / roughness channels are on from the first step
MODE == :coupled && (alb !== nothing || rough !== nothing) && set_surface!(cb)

ndays = Dates.value(Date(START + Year(YEARS)) - Date(START))
t = @elapsed run!(sim, period = Day(ndays))
@printf("run: %d calendar days (%d years) in %.0f s = %.0f core-s per simulated year\n", ndays, YEARS, t, t / YEARS)
flush(stdout)
