# Clear-sky longwave of SpeedyWeather's schemes against a correlated-k reference on IDENTICAL columns (stand-alone, no
# emulator): spin up a PrimitiveWetModel (prescribed SST; env LW/T0 as speedy_cold_bias_repro.jl) to get realistic
# columns, then for every grid point compute the clear-sky longwave of (1) FourBandLongwave with cloud cover 0,
# (2) the default grey OneBandLongwave, (3) NumericalRadiation's ClearSkyEcCKDRadiation (ecCKD gas optics, 32 g-points,
# H2O + CO2 + O3), all from the same temperature, humidity, surface pressure and surface temperature.
# Prints OLR, surface downward longwave and the longwave heating rate per layer [K/day], tropics and global.
#   julia --project=<env with the cold-bias branch + NumericalRadiation> speedy_longwave_vs_ecckd.jl [spinup_days=90]
# env CO2PPM (default 400) for ecCKD; FourBandLongwave has no CO2 dependence (speedy.f90's fixed CO2 band).
using SpeedyWeather, NumericalRadiation, Dates, Printf

const SPINUP = parse(Int, get(ARGS, 1, "90"))
const CO2 = parse(Float64, get(ENV, "CO2PPM", "400")) * 1.0e-6

sg = SpectralGrid(NF = Float64, truncation = 32, nlayers = 8)
kw = (; ocean = SeasonalOceanClimatology(sg))
get(ENV, "LW", "") == "fourband" && (kw = (; kw..., radiation = Radiation(sg; longwave = FourBandLongwave(sg))))
host = PrimitiveWetModel(sg; kw...)
sim = initialize!(host; time = DateTime(2015, 1, 1))
run!(sim, period = Day(SPINUP))
hv = sim.variables

# the three schemes, each in its own model so each has its own variables, fed the host's columns
fourband = FourBandLongwave(sg)
m4 = PrimitiveWetModel(sg; radiation = Radiation(sg; longwave = fourband), ocean = SeasonalOceanClimatology(sg))
grey = OneBandLongwave(sg)
m1 = PrimitiveWetModel(sg; radiation = Radiation(sg; longwave = grey), ocean = SeasonalOceanClimatology(sg))
ecckd = ClearSkyEcCKDRadiation(sg; mole_fractions = (; co2 = CO2))
mc = PrimitiveWetModel(sg; radiation = ecckd, ocean = SeasonalOceanClimatology(sg))
s4, s1, sc = initialize!(m4), initialize!(m1), initialize!(mc)

function copy_state!(dst, src)
    dst.grid.temperature .= src.grid.temperature
    dst.grid.humidity .= src.grid.humidity
    dst.dynamics.geopotential .= src.dynamics.geopotential
    dst.parameterizations.surface_pressure .= src.parameterizations.surface_pressure
    dst.prognostic.ocean.sea_surface_temperature .= src.prognostic.ocean.sea_surface_temperature
    dst.prognostic.land.soil_temperature .= src.prognostic.land.soil_temperature
    return nothing
end

_, lats = SpeedyWeather.RingGrids.get_londlatds(sg.grid)
Ω = SpeedyWeather.RingGrids.get_solid_angles(typeof(sg.grid), sg.grid.nlat_half)
w = zeros(length(lats))
for (j, ring) in enumerate(SpeedyWeather.RingGrids.eachring(sg.grid))
    w[ring] .= Ω[j]
end
nlayers, npoints = sg.nlayers, sg.npoints
g, cₚ = host.planet.gravity, host.atmosphere.heat_capacity
coord = host.geometry.vertical_coordinates

# heating [K/day] from interface fluxes up/down (k = 1 top ... nlayers + 1 surface)
heating(up, down, pₛ, k) = (up[k + 1] - up[k] + down[k] - down[k + 1]) * g / (cₚ * SpeedyWeather.pressure_thickness(k, pₛ, coord)) * 86400

results = Dict{Symbol, Any}()
for (name, m, s) in ((:fourband, m4, s4), (:grey, m1, s1), (:ecckd, mc, sc))
    v = s.variables
    copy_state!(v, hv)
    SpeedyWeather.reset_variables!(v)
    SpeedyWeather.global_parameterizations!(v, m)
    p = v.parameterizations
    dTdt = SpeedyWeather.get_tendency_step(v.tendencies.grid.temperature, m.time_stepping, m.radiation)
    H = zeros(npoints, nlayers)
    for ij in 1:npoints
        haskey(p, :cloud_cover) && (p.cloud_cover[ij] = 0)        # clear sky
        haskey(p, :cloud_top) && (p.cloud_top[ij] = nlayers + 1)
        if name == :ecckd
            SpeedyWeather.parameterization!(ij, v, m.radiation, m)
            up, down = p.ecckd.longwave_up[ij, :], p.ecckd.longwave_down[ij, :]
            pₛ = p.surface_pressure[ij]
            H[ij, :] .= [heating(up, down, pₛ, k) for k in 1:nlayers]
        else
            dTdt[ij, :] .= 0
            SpeedyWeather.parameterization!(ij, v, m.radiation.longwave, m)
            H[ij, :] .= dTdt[ij, :] .* 86400
        end
    end
    results[name] = (olr = copy(p.outgoing_longwave.data), down = copy(p.surface_longwave_down.data), H = H)
end

σ = host.geometry.σ_levels_full
println("\nclear-sky longwave on identical columns after $SPINUP days (host longwave = $(get(ENV, "LW", "grey"))), ecCKD CO2 $(CO2 * 1.0e6) ppm")
for (bname, sel) in (("tropics |lat| < 15", abs.(lats) .< 15), ("global", trues(npoints)), ("|lat| >= 60", abs.(lats) .>= 60))
    W = sum(w[sel])
    wm(x) = sum(w[sel] .* x[sel]) / W
    println("$bname:              four-band     grey    ecCKD")
    @printf("  OLR W/m²            %8.1f %8.1f %8.1f\n", (wm(results[n].olr) for n in (:fourband, :grey, :ecckd))...)
    @printf("  LW down sfc W/m²    %8.1f %8.1f %8.1f\n", (wm(results[n].down) for n in (:fourband, :grey, :ecckd))...)
    for k in 1:nlayers
        @printf("  σ %.3f  K/day      %8.2f %8.2f %8.2f\n", σ[k], (wm(results[n].H[:, k]) for n in (:fourband, :grey, :ecckd))...)
    end
end
flush(stdout)
