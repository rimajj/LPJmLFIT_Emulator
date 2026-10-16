# Two-way coupling of SpeedyWeather.jl (0.23) to the learned LPJmL-FIT emulator (ADR 0345).
#
#   atmosphere -> land: each land column's daily mean surface air temperature, precipitation (rain + snow),
#                       downward shortwave, net longwave and lowest-level humidity, accumulated every time step;
#   land -> atmosphere: the emulator's daily evapotranspiration (interception + transpiration + soil
#                       evaporation) as the land surface humidity flux, held constant over the following day.
#                       SpeedyWeather's land energy balance takes its latent-heat cooling from that same flux.
#
# The emulator is the released Python package (python/src/lpjmlfit_emulator/landemu), called through PythonCall
# once per simulated day; scripts/online_coupling/landemu_coupler.py builds its start state and records everything
# it saw, so `landemu_coupler.py replay` can prove offline that the coupled emulator is the released one.
#
# Env knobs: MODE = coupled | control (control = SpeedyWeather's own land evaporation, same diagnostics) ·
#            YEARS (default 2) · TRUNC (31) · NLAYERS (8) · OUT (record directory, on /p/projects) ·
#            MAXDEG (3.0, largest distance from a column centre to the emulator cell that represents it) ·
#            DIURNAL = flat | sun (how a day's ET is spread over its time steps: constant, or in proportion to
#            the cosine of the solar zenith angle; both hand over exactly the day's total).
# Run with scripts/online_coupling/sbatch_speedy_landemu.sh (one core; PythonCall uses conda env py311_new).

using SpeedyWeather, PythonCall, Dates, Printf
import SpeedyWeather: initialize!, variables, callback!, finalize!, surface_humidity_flux!

const MODE = Symbol(get(ENV, "MODE", "coupled"))
const YEARS = parse(Int, get(ENV, "YEARS", "2"))
const TRUNC = parse(Int, get(ENV, "TRUNC", "31"))
const NLAYERS = parse(Int, get(ENV, "NLAYERS", "8"))
const MAXDEG = parse(Float64, get(ENV, "MAXDEG", "3.0"))
const DIURNAL = Symbol(get(ENV, "DIURNAL", "flat"))
const START = DateTime(2015, 1, 1)
const OUT = get(ENV, "OUT", "/p/projects/open/Jamir/esm_land_emulator_data/coupled/speedy_t$(TRUNC)_$(MODE)$(DIURNAL == :sun && MODE == :coupled ? "_sun" : "")_$(YEARS)y")
@assert MODE in (:coupled, :control) && DIURNAL in (:flat, :sun)
println("run_speedy_landemu: MODE=$MODE YEARS=$YEARS TRUNC=$TRUNC NLAYERS=$NLAYERS MAXDEG=$MAXDEG DIURNAL=$DIURNAL OUT=$OUT")
println("SpeedyWeather ", pkgversion(SpeedyWeather), "  threads=", Threads.nthreads()); flush(stdout)

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

# ---------------------------------------------------------------------------------------------- the coupler
"""Emulator day of a time: (year, 0-based day of a 365-day year); 29 February is folded into 28 February."""
function emday(t::DateTime)
    d = dayofyear(t) - 1
    (isleapyear(t) && dayofyear(t) >= 60) && (d -= 1)
    return (year(t), d)
end

const NV = 7   # accumulated per land column: tas, pr, rsds, lwnet, huss, humidity flux used, land fraction

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
    @inbounds for (k, ij) in enumerate(cb.cols)
        cb.acc[k, 1] += p.surface_air_temperature[ij] - 273.15
        cb.acc[k, 2] += (p.rain_rate[ij] + p.snow_rate[ij]) * 1000 * 86400          # m/s -> mm/day
        cb.acc[k, 3] += p.surface_shortwave_down[ij]
        cb.acc[k, 4] += p.surface_longwave_down[ij] - p.land.surface_longwave_up[ij]
        cb.acc[k, 5] += q[ij, nl]
        cb.acc[k, 6] += p.land.surface_humidity_flux[ij] * 86400                     # kg/m²/s -> mm/day
        cb.acc[k, 7] += lf[ij]
    end
    cb.nacc += 1
    return nothing
end

function finish_day!(cb::LandEmuCallback, t_now::DateTime)
    m = Float32.(cb.acc ./ cb.nacc)
    push!(cb.rec, m)
    if cb.py !== nothing
        F = Float64.(cb.acc[cb.emu, 1:5] ./ cb.nacc)
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
    end
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

function finalize!(cb::LandEmuCallback, vars, model)
    cb.nacc > 0 && finish_day!(cb, vars.prognostic.clock.time)          # close the last day (its ET is produced but never applied)
    wall = time() - cb.t_start
    rec = cat(cb.rec...; dims = 3)                                      # (ncols, NV, days)
    extra = Dict(
        "daily_means" => rec, "cols" => cb.cols, "emu" => cb.emu, "wall" => wall, "t_py" => cb.t_py,
        "applied" => cb.applied, "produced" => cb.produced, "nday_cal" => cb.nday_cal, "dt" => cb.Δt,
        "diurnal" => string(DIURNAL)
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
model = MODE == :coupled ?
    PrimitiveWetModel(sg; surface_humidity_flux = SurfaceHumidityFlux(sg; land = hf)) :
    PrimitiveWetModel(sg)
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
cb = LandEmuCallback(
    hf, cols, emu, py, zeros(length(cols), NV), 0, (0, 0), Matrix{Float32}[], 0,
    zeros(ne), zeros(ne), zeros(ne), 0.0, 0.0, 0.0,
    deg2rad.(Float64.(lats[cols[emu]])), deg2rad.(Float64.(lons[cols[emu]])), zeros(ne, 1), 0
)
add!(model, :landemu => cb)

ndays = Dates.value(Date(START + Year(YEARS)) - Date(START))
t = @elapsed run!(sim, period = Day(ndays))
@printf("run: %d calendar days (%d years) in %.0f s = %.0f core-s per simulated year\n", ndays, YEARS, t, t / YEARS)
flush(stdout)
