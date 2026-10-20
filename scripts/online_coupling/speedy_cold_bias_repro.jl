# Minimal, stand-alone reproducer of SpeedyWeather's cold near-surface air (no emulator, no coupling code): the
# DEFAULT PrimitiveWetModel at T31 L8, optionally with the prescribed seasonal SST climatology, and one diagnostics
# callback that reads model state only. Written to be pasted into an upstream SpeedyWeather issue (ADR 0346).
#   julia --project=<env with SpeedyWeather> speedy_cold_bias_repro.jl [slab|prescribed] [years=3]
# Prints, for years 2..N (year 1 is spin-up), area-weighted means (exact quadrature weights of the grid):
#   global near-surface air temperature; ice-free ocean air vs SST by latitude band; land air vs top-soil temperature;
#   and NH land 55-73 N (Greenland excluded) still snow-covered on 31 August of the last year.
using SpeedyWeather, Dates, Printf
import SpeedyWeather: initialize!, callback!, finalize!

const OCEAN = Symbol(get(ARGS, 1, "slab"))
const YEARS = parse(Int, get(ARGS, 2, "3"))
const START = DateTime(2015, 1, 1)

mutable struct ColdDiag <: SpeedyWeather.AbstractCallback
    w::Vector{Float64}      # area weight of every grid point
    lat::Vector{Float64}
    lon::Vector{Float64}
    acc::Dict{Symbol, Vector{Float64}}   # name => [Σ w·x, Σ w]
    snow_aug::Vector{Float64}
end
ColdDiag() = ColdDiag(Float64[], Float64[], Float64[], Dict{Symbol, Vector{Float64}}(), Float64[])

function initialize!(cb::ColdDiag, vars, model)
    grid = model.spectral_grid.grid
    Ω = SpeedyWeather.RingGrids.get_solid_angles(typeof(grid), grid.nlat_half)
    lons, lats = SpeedyWeather.RingGrids.get_londlatds(grid)
    cb.lat, cb.lon = Float64.(lats), Float64.(lons)
    cb.w = zeros(length(lats))
    for (j, ring) in enumerate(SpeedyWeather.RingGrids.eachring(grid))
        cb.w[ring] .= Ω[j]
    end
    return nothing
end

acc!(cb, k, x, w) = (a = get!(cb.acc, k, zeros(2)); a[1] += w * x; a[2] += w; nothing)

function callback!(cb::ColdDiag, vars, model)
    t = vars.prognostic.clock.time
    year(t) - year(START) < 1 && return nothing                  # year 1 = spin-up
    p = vars.parameterizations
    lf = model.land_sea_mask.land_fraction
    sst = SpeedyWeather.get_prognostic_step(vars.prognostic.ocean.sea_surface_temperature,
        SpeedyWeather.time_stepper(model.time_stepping, :ocean), cb)
    ice = SpeedyWeather.get_prognostic_step(vars.prognostic.ocean.sea_ice_concentration,
        SpeedyWeather.time_stepper(model.time_stepping, :ocean), cb)
    lstep = SpeedyWeather.time_stepper(model.time_stepping, :land)
    soilT = SpeedyWeather.get_prognostic_step(vars.prognostic.land.soil_temperature, lstep, cb)
    snow = SpeedyWeather.get_prognostic_step(vars.prognostic.land.snow_depth, lstep, cb)
    for ij in eachindex(cb.w)
        w, l, ta = cb.w[ij], lf[ij], p.surface_air_temperature[ij] - 273.15
        acc!(cb, :air_global, ta, w)
        l > 0 && acc!(cb, :air_land, ta, w * l)
        if l > 0.99
            acc!(cb, :soil_land, soilT[ij, 1] - 273.15, w)
            acc!(cb, :air_land_pure, ta, w)
        end
        if l == 0 && ice[ij] < 0.01                              # ice-free open ocean
            band = abs(cb.lat[ij]) < 15 ? :trop : abs(cb.lat[ij]) < 30 ? :sub : abs(cb.lat[ij]) < 50 ? :mid : :high
            acc!(cb, Symbol(:air_, band), ta, w)
            acc!(cb, Symbol(:sst_, band), sst[ij] - 273.15, w)
        end
    end
    if year(t) == year(START) + YEARS - 1 && month(t) == 8 && day(t) == 31 && isempty(cb.snow_aug)
        greenland = (cb.lon .> 285) .& (cb.lon .< 350) .& (cb.lat .> 59)
        m = (lf .> 0.5) .& (cb.lat .> 55) .& (cb.lat .< 73) .& .!greenland
        cov = [snow[ij] > 1e-3 for ij in findall(m)]
        push!(cb.snow_aug, sum(cb.w[m] .* cov) / sum(cb.w[m]), maximum(snow[ij] for ij in findall(m)))
    end
    return nothing
end

mean_of(cb, k) = cb.acc[k][1] / cb.acc[k][2]

function finalize!(cb::ColdDiag, vars, model)
    @printf("\nSpeedyWeather %s, T31 L8 default PrimitiveWetModel, ocean = %s, years 2-%d\n",
        pkgversion(SpeedyWeather), OCEAN, YEARS)
    @printf("global mean near-surface air temperature : %6.2f °C\n", mean_of(cb, :air_global))
    @printf("land (fraction-weighted) air temperature : %6.2f °C\n", mean_of(cb, :air_land))
    @printf("all-land points: air %6.2f °C, top soil layer %6.2f °C\n", mean_of(cb, :air_land_pure), mean_of(cb, :soil_land))
    println("ice-free open ocean:           air °C    SST °C    air - SST")
    for (b, name) in ((:trop, "|lat| <  15"), (:sub, "|lat| 15-30"), (:mid, "|lat| 30-50"), (:high, "|lat| >= 50"))
        a, s = mean_of(cb, Symbol(:air_, b)), mean_of(cb, Symbol(:sst_, b))
        @printf("  %s               %7.2f   %7.2f   %7.2f\n", name, a, s, a - s)
    end
    isempty(cb.snow_aug) || @printf(
        "31 Aug of year %d: %.0f %% of land 55-73 N (Greenland excluded) snow-covered, max snow %.2f m water equiv.\n",
        YEARS, 100cb.snow_aug[1], cb.snow_aug[2])
    flush(stdout)
    return nothing
end

spectral_grid = SpectralGrid(truncation = 32, nlayers = 8)   # T31 L8 (the 0.23 defaults)
model = OCEAN == :prescribed ?
    PrimitiveWetModel(spectral_grid; ocean = SeasonalOceanClimatology(spectral_grid)) :
    PrimitiveWetModel(spectral_grid)
add!(model, :cold_diag => ColdDiag())
simulation = initialize!(model; time = START)
run!(simulation, period = Day(Dates.value(Date(START + Year(YEARS)) - Date(START))))
