# Minimal, stand-alone reproducer of SpeedyWeather's cold near-surface air (no emulator, no coupling code): the
# DEFAULT PrimitiveWetModel at T31 L8, optionally with the prescribed seasonal SST climatology, and one diagnostics
# callback that reads model state only. Written to be pasted into an upstream SpeedyWeather issue (ADR 0346).
#   julia --project=<env with SpeedyWeather> speedy_cold_bias_repro.jl [slab|prescribed] [years=3]
# Prints, for years 2..N (year 1 is spin-up), area-weighted means (exact quadrature weights of the grid):
#   global near-surface air temperature; ice-free ocean air vs SST by latitude band; land air vs top-soil temperature;
#   and NH land 55-73 N (Greenland excluded) still snow-covered on 31 August of the last year.
# env LANDREF=<csv from build_speedy_land_reference.py>: also land air temperature and precipitation at the 1 197
#   T31 land columns of ADR 0346 against GSWP3-W5E5 observations 1985-2014 (same columns and weights).
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
    ref::Dict{String, Vector{Float64}}   # LANDREF columns: ij, lat, weight, observed tas/t_warm/t_cold/pr
    mon_sum::Matrix{Float64}             # model land-column air T summed per calendar month
    mon_n::Vector{Int}
    pr_sum::Vector{Float64}              # model precipitation rate summed over scored steps
    rad_sum::Matrix{Float64}             # model downward SW, net LW at the land columns, summed
    soil_mon::Matrix{Float64}            # model top-soil temperature at the land columns, per calendar month
end
ColdDiag() = ColdDiag(
    Float64[], Float64[], Float64[], Dict{Symbol, Vector{Float64}}(), Float64[],
    Dict{String, Vector{Float64}}(), zeros(0, 12), zeros(Int, 12), Float64[], zeros(0, 2), zeros(0, 12)
)

function read_landref!(cb, path)
    lines = readlines(path)
    names = split(lines[1], ',')
    cols = [parse.(Float64, split(l, ',')) for l in lines[2:end]]
    for (i, n) in enumerate(names)
        cb.ref[n] = [c[i] for c in cols]
    end
    n = length(cols)
    cb.mon_sum, cb.pr_sum, cb.rad_sum, cb.soil_mon = zeros(n, 12), zeros(n), zeros(n, 2), zeros(n, 12)
    return nothing
end

function initialize!(cb::ColdDiag, vars, model)
    grid = model.spectral_grid.grid
    Ω = SpeedyWeather.RingGrids.get_solid_angles(typeof(grid), grid.nlat_half)
    lons, lats = SpeedyWeather.RingGrids.get_londlatds(grid)
    cb.lat, cb.lon = Float64.(lats), Float64.(lons)
    cb.w = zeros(length(lats))
    for (j, ring) in enumerate(SpeedyWeather.RingGrids.eachring(grid))
        cb.w[ring] .= Ω[j]
    end
    haskey(ENV, "LANDREF") && read_landref!(cb, ENV["LANDREF"])
    return nothing
end

acc!(cb, k, x, w) = (a = get!(cb.acc, k, zeros(2)); a[1] += w * x; a[2] += w; nothing)

function callback!(cb::ColdDiag, vars, model)
    t = vars.prognostic.clock.time
    p = vars.parameterizations
    y = year(t) - year(START) + 1                                # per-year global means, all years, to see drift
    for ij in eachindex(cb.w)
        acc!(cb, Symbol(:yair_, y), p.surface_air_temperature[ij] - 273.15, cb.w[ij])
        acc!(cb, Symbol(:yosr_, y), p.outgoing_shortwave[ij], cb.w[ij])
        acc!(cb, Symbol(:yolr_, y), p.outgoing_longwave[ij], cb.w[ij])
    end
    y < 2 && return nothing                                      # year 1 = spin-up
    lf = model.land_sea_mask.land_fraction
    sst = SpeedyWeather.get_prognostic_step(
        vars.prognostic.ocean.sea_surface_temperature,
        SpeedyWeather.time_stepper(model.time_stepping, :ocean), cb
    )
    ice = SpeedyWeather.get_prognostic_step(
        vars.prognostic.ocean.sea_ice_concentration,
        SpeedyWeather.time_stepper(model.time_stepping, :ocean), cb
    )
    lstep = SpeedyWeather.time_stepper(model.time_stepping, :land)
    soilT = SpeedyWeather.get_prognostic_step(vars.prognostic.land.soil_temperature, lstep, cb)
    snow = SpeedyWeather.get_prognostic_step(vars.prognostic.land.snow_depth, lstep, cb)
    q = SpeedyWeather.get_prognostic_step(vars.grid.humidity, model.time_stepping, cb)
    coord = model.geometry.vertical_coordinates
    nlayers = size(q, 2)
    for ij in eachindex(cb.w)
        w, l, ta = cb.w[ij], lf[ij], p.surface_air_temperature[ij] - 273.15
        # zonal bands, all points: OLR, reflected SW, cloud cover, column water vapour [kg/m²]
        zb = abs(cb.lat[ij]) < 15 ? :ztrop : abs(cb.lat[ij]) < 30 ? :zsub : abs(cb.lat[ij]) < 60 ? :zmid : :zpol
        pₛ = p.surface_pressure[ij]
        pw = sum(q[ij, k] * SpeedyWeather.pressure_thickness(k, pₛ, coord) for k in 1:nlayers) / model.planet.gravity
        for (k, x) in (
                (:olr, p.outgoing_longwave[ij]), (:osr, p.outgoing_shortwave[ij]), (:pw, pw),
                (:clc, haskey(p, :cloud_cover) ? p.cloud_cover[ij] : NaN),
                (:cth, haskey(p, :cloud_top_height) ? p.cloud_top_height[ij] / 1000 : NaN),
            )
            acc!(cb, Symbol(k, zb), x, w)
            acc!(cb, Symbol(k, :zall), x, w)
        end
        acc!(cb, :air_global, ta, w)
        acc!(cb, :olr, p.outgoing_longwave[ij], w)
        if abs(cb.lat[ij]) < 15                                  # tropical profiles: p, T, q per layer
            Tg = SpeedyWeather.get_prognostic_step(vars.grid.temperature, model.time_stepping, cb)
            for k in 1:nlayers
                acc!(cb, Symbol(:prof_p_, k), SpeedyWeather.pressure(k, pₛ, coord) / 100, w)
                acc!(cb, Symbol(:prof_T_, k), Tg[ij, k], w)
                acc!(cb, Symbol(:prof_q_, k), 1000 * q[ij, k], w)
            end
        end
        l > 0 && acc!(cb, :air_land, ta, w * l)
        if l > 0.99
            acc!(cb, :soil_land, soilT[ij, 1] - 273.15, w)
            acc!(cb, :air_land_pure, ta, w)
        end
        if l == 0 && ice[ij] < 0.01                              # ice-free open ocean
            band = abs(cb.lat[ij]) < 15 ? :trop : abs(cb.lat[ij]) < 30 ? :sub : abs(cb.lat[ij]) < 50 ? :mid : :high
            acc!(cb, Symbol(:air_, band), ta, w)
            acc!(cb, Symbol(:sst_, band), sst[ij] - 273.15, w)
            # surface energy budget of the open ocean [W/m², positive = into the ocean]
            for (k, x) in (
                    (:swnet, p.surface_shortwave_down[ij] - p.ocean.surface_shortwave_up[ij]),
                    (:lwdown, p.surface_longwave_down[ij]), (:lwup, -p.ocean.surface_longwave_up[ij]),
                    (:sh, -p.ocean.sensible_heat_flux[ij]),
                    (:lh, -model.atmosphere.latent_heat_condensation * p.ocean.surface_humidity_flux[ij]),
                )
                acc!(cb, Symbol(k, :_all), x, w)
                abs(cb.lat[ij]) < 15 && acc!(cb, Symbol(k, :_trop), x, w)
            end
        end
    end
    if !isempty(cb.ref)
        m = month(t)
        cb.mon_n[m] += 1
        for (c, ij) in enumerate(cb.ref["ij"])
            ij = Int(ij)
            cb.mon_sum[c, m] += p.surface_air_temperature[ij] - 273.15
            cb.pr_sum[c] += p.rain_rate[ij] + (haskey(p, :snow_rate) ? p.snow_rate[ij] : 0.0)
            cb.soil_mon[c, m] += soilT[ij, 1] - 273.15
            cb.rad_sum[c, 1] += p.surface_shortwave_down[ij]
            cb.rad_sum[c, 2] += p.surface_longwave_down[ij] - p.land.surface_longwave_up[ij]
        end
    end
    if year(t) == year(START) + YEARS - 1 && month(t) == 8 && day(t) == 31 && isempty(cb.snow_aug)
        greenland = (cb.lon .> 285) .& (cb.lon .< 350) .& (cb.lat .> 59)
        m = (lf .> 0.5) .& (cb.lat .> 55) .& (cb.lat .< 73) .& .!greenland
        cov = [snow[ij] > 1.0e-3 for ij in findall(m)]
        push!(cb.snow_aug, sum(cb.w[m] .* cov) / sum(cb.w[m]), maximum(snow[ij] for ij in findall(m)))
    end
    return nothing
end

mean_of(cb, k) = cb.acc[k][1] / cb.acc[k][2]

function finalize!(cb::ColdDiag, vars, model)
    @printf(
        "\nSpeedyWeather %s, T31 L8 default PrimitiveWetModel, ocean = %s, years 2-%d\n",
        pkgversion(SpeedyWeather), OCEAN, YEARS
    )
    @printf("global mean near-surface air temperature : %6.2f °C\n", mean_of(cb, :air_global))
    @printf("land (fraction-weighted) air temperature : %6.2f °C\n", mean_of(cb, :air_land))
    @printf("all-land points: air %6.2f °C, top soil layer %6.2f °C\n", mean_of(cb, :air_land_pure), mean_of(cb, :soil_land))
    println("ice-free open ocean:           air °C    SST °C    air - SST")
    for (b, name) in ((:trop, "|lat| <  15"), (:sub, "|lat| 15-30"), (:mid, "|lat| 30-50"), (:high, "|lat| >= 50"))
        a, s = mean_of(cb, Symbol(:air_, b)), mean_of(cb, Symbol(:sst_, b))
        @printf("  %s               %7.2f   %7.2f   %7.2f\n", name, a, s, a - s)
    end
    println("ice-free open ocean surface budget [W/m², + = into ocean]: SW net, LW down, LW up, sensible, latent, sum")
    for (b, name) in ((:all, "all       "), (:trop, "|lat| < 15"))
        x = [mean_of(cb, Symbol(k, :_, b)) for k in (:swnet, :lwdown, :lwup, :sh, :lh)]
        @printf("  %s  %7.1f %7.1f %7.1f %7.1f %7.1f   %7.1f\n", name, x..., sum(x))
    end
    @printf("global mean outgoing longwave at the top: %6.1f W/m²\n", mean_of(cb, :olr))
    println("by latitude (all points):     OLR    refl.SW   cloud cover   water vapour kg/m²   cloud top km (0 = none)")
    for (b, name) in ((:zall, "global     "), (:ztrop, "|lat| < 15 "), (:zsub, "|lat| 15-30"), (:zmid, "|lat| 30-60"), (:zpol, "|lat| >= 60"))
        @printf("  %s  %7.1f  %7.1f    %7.3f      %7.1f          %6.2f\n", name, (mean_of(cb, Symbol(k, b)) for k in (:olr, :osr, :clc, :pw, :cth))...)
    end
    println("tropical mean profile (|lat| < 15): layer, pressure hPa, temperature K, humidity g/kg")
    for k in 1:100
        haskey(cb.acc, Symbol(:prof_p_, k)) || break
        @printf("  %2d %7.1f %7.2f %8.4f\n", k, (mean_of(cb, Symbol(:prof_, v, :_, k)) for v in (:p, :T, :q))...)
    end
    S4 = model.planet.solar_constant / 4
    println("per year: global air °C, reflected SW, OLR, net down at top (S₀/4 - both) [W/m²]")
    for y in 1:YEARS
        haskey(cb.acc, Symbol(:yair_, y)) || continue
        osr, olr = mean_of(cb, Symbol(:yosr_, y)), mean_of(cb, Symbol(:yolr_, y))
        @printf("  year %2d  %6.2f  %6.1f  %6.1f  %6.1f\n", y, mean_of(cb, Symbol(:yair_, y)), osr, olr, S4 - osr - olr)
    end
    if !isempty(cb.ref)
        mon = cb.mon_sum ./ cb.mon_n'                            # (columns, 12) monthly means
        tas = vec(sum(cb.mon_sum, dims = 2)) ./ sum(cb.mon_n)
        warm, cold = vec(maximum(mon, dims = 2)), vec(minimum(mon, dims = 2))
        pr = cb.pr_sum ./ sum(cb.mon_n) .* 1000 .* 86400 .* 365  # m/s -> mm/yr
        w, lat = cb.ref["weight"], abs.(cb.ref["lat"])
        wm(x, sel = trues(length(w))) = sum(w[sel] .* x[sel]) / sum(w[sel])
        println("land columns vs W5E5 observations 1985-2014 ($(length(w)) T31 columns, ADR 0346 weights): model, obs, model - obs")
        for (name, x, o) in (
                ("annual air T °C ", tas, cb.ref["tas"]), ("warmest month °C", warm, cb.ref["t_warm"]),
                ("coldest month °C", cold, cb.ref["t_cold"]), ("precip mm/yr    ", pr, cb.ref["pr"]),
            )
            @printf("  %s %7.2f %7.2f %7.2f\n", name, wm(x), wm(o), wm(x) - wm(o))
        end
        if haskey(cb.ref, "rsds")
            rsds, lwnet = cb.rad_sum[:, 1] ./ sum(cb.mon_n), cb.rad_sum[:, 2] ./ sum(cb.mon_n)
            @printf("  SW down W/m²     %7.2f %7.2f %7.2f\n", wm(rsds), wm(cb.ref["rsds"]), wm(rsds) - wm(cb.ref["rsds"]))
            @printf("  net LW W/m²      %7.2f %7.2f %7.2f\n", wm(lwnet), wm(cb.ref["lwnet"]), wm(lwnet) - wm(cb.ref["lwnet"]))
        end
        for (name, sel) in (("|lat| < 23.5", lat .< 23.5), ("23.5-50     ", 23.5 .<= lat .< 50), ("> 50        ", lat .>= 50))
            @printf("  annual air T model - obs, %s %7.2f K", name, wm(tas, sel) - wm(cb.ref["tas"], sel))
            @printf("   warmest %6.2f  coldest %6.2f", wm(warm, sel) - wm(cb.ref["t_warm"], sel), wm(cold, sel) - wm(cb.ref["t_cold"], sel))
            # the month that is coldest in the observations' sense: the model's own coldest air month per column
            soil = cb.soil_mon ./ cb.mon_n'
            soil_cold = [soil[c, argmin(mon[c, :])] for c in axes(soil, 1)]
            @printf("   top soil in coldest month - obs air %6.2f", wm(soil_cold, sel) - wm(cb.ref["t_cold"], sel))
            haskey(cb.ref, "rsds") && @printf(
                "   SW down %6.1f  net LW %6.1f",
                wm(cb.rad_sum[:, 1] ./ sum(cb.mon_n), sel) - wm(cb.ref["rsds"], sel), wm(cb.rad_sum[:, 2] ./ sum(cb.mon_n), sel) - wm(cb.ref["lwnet"], sel)
            )
            println()
        end
    end
    isempty(cb.snow_aug) || @printf(
        "31 Aug of year %d: %.0f %% of land 55-73 N (Greenland excluded) snow-covered, max snow %.2f m water equiv.\n",
        YEARS, 100cb.snow_aug[1], cb.snow_aug[2]
    )
    flush(stdout)
    return nothing
end

spectral_grid = SpectralGrid(truncation = 32, nlayers = 8)   # T31 L8 (the 0.23 defaults)
# env SIGMA=speedy: speedy.f90's 8 sigma levels (2 thin stratospheric layers) instead of 8 equal layers
# env LW=analytic: NumericalRadiation's water-vapour/CO2 AnalyticBandLongwave instead of the default grey
# Frierson longwave (needs SpeedyWeather main + NumericalRadiation in the project); LW=fourband see below; default = grey
const LW = Symbol(get(ENV, "LW", "grey"))
if LW == :analytic
    using NumericalRadiation
end
kw = (;)
OCEAN == :prescribed && (kw = (; kw..., ocean = SeasonalOceanClimatology(spectral_grid)))
LW == :analytic && (kw = (; kw..., radiation = Radiation(spectral_grid; longwave = AnalyticBandLongwave(spectral_grid))))
# env LW=fourband: SPEEDY's four-band longwave with clouds and water vapour (cold-bias fix branch only), with
# LWKW="name=value,..." for FourBandLongwave and CLOUDKW="name=value,..." for the shortwave's DiagnosticClouds;
# T0=speedy: speedy.f90's surface air temperature (SurfaceCondition(actual_lapse_rate = true), same branch)
parsekw(s) = isempty(s) ? (;) : NamedTuple(
        Symbol(k) => (v in ("true", "false") ? v == "true" : parse(Float64, v))
        for (k, v) in (split(x, '=') for x in split(s, ','))
    )
const LWKW, CLOUDKW = parsekw(get(ENV, "LWKW", "")), parsekw(get(ENV, "CLOUDKW", ""))
LW == :fourband && (
    kw = (;
        kw..., radiation = Radiation(
            spectral_grid;
            shortwave = TwoBandShortwave(spectral_grid; clouds = DiagnosticClouds(spectral_grid; CLOUDKW...)),
            longwave = FourBandLongwave(spectral_grid; LWKW...)
        ),
    )
)
get(ENV, "T0", "") == "speedy" && (
    kw = (;
        kw..., boundary_layer = BoundaryLayer(
            spectral_grid;
            surface_condition = SurfaceCondition(spectral_grid; actual_lapse_rate = true)
        ),
    )
)
get(ENV, "SIGMA", "") == "speedy" && (
    kw = (;
        kw..., geometry = Geometry(
            spectral_grid;
            vertical_coordinates = SigmaCoordinates(spectral_grid, [0, 0.05, 0.14, 0.26, 0.42, 0.6, 0.77, 0.9, 1])
        ),
    )
)
println("knobs: LWKW = $LWKW, CLOUDKW = $CLOUDKW, T0 = $(get(ENV, "T0", "dry adiabat")), SIGMA = $(get(ENV, "SIGMA", "equal"))")
println("ocean = $OCEAN, longwave = $LW")
model = PrimitiveWetModel(spectral_grid; kw...)
add!(model, :cold_diag => ColdDiag())
simulation = initialize!(model; time = START)
run!(simulation, period = Day(Dates.value(Date(START + Year(YEARS)) - Date(START))))
