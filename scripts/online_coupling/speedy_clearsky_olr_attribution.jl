# Clear-sky OLR attribution (stand-alone, no emulator): which part of SpeedyWeather's state makes its clear-sky OLR
# ~14 W/m² lower than CERES (JOURNAL 2026-10-22)? Spin up a host PrimitiveWetModel (prescribed SST, FourBandLongwave,
# the cold-bias branch's convection: ascent_substeps = 10, entrainment_mse = true), then compute clear-sky longwave with
# FourBandLongwave and NumericalRadiation's ecCKD on the host's columns, and again with the host's temperature and/or
# humidity replaced by the GFDL-ESM4 1985-2014 band-mean profile (PROFREF, by |lat| band, log-p interpolated to each
# column's layer pressures; surface temperatures kept). If ecCKD on GFDL-ESM4's state gives ~CERES, the state is at
# fault; the T-only and q-only swaps say which part.
#   julia --project=<env with the cold-bias branch + NumericalRadiation> speedy_clearsky_olr_attribution.jl [spinup_days=120]
using SpeedyWeather, NumericalRadiation, Dates, Printf

const SPINUP = parse(Int, get(ARGS, 1, "120"))
const CO2 = parse(Float64, get(ENV, "CO2PPM", "400")) * 1.0e-6

# env NLAYERS (default 8): vertical resolution of host and radiation columns; with spin-up 0 the swapped GFDL-ESM4 rows
# measure the radiation of the SAME reference atmosphere at different layer counts (vertical-resolution test)
sg = SpectralGrid(NF = Float64, truncation = 32, nlayers = parse(Int, get(ENV, "NLAYERS", "8")))
host = PrimitiveWetModel(
    sg; ocean = SeasonalOceanClimatology(sg), radiation = Radiation(sg; longwave = FourBandLongwave(sg)),
    convection = BettsMillerConvection(sg; ascent_substeps = 10, entrainment_mse = true)
)
sim = initialize!(host; time = DateTime(2015, 1, 1))
SPINUP > 0 && run!(sim, period = Day(SPINUP))
hv = sim.variables

fourband = FourBandLongwave(sg)
m4 = PrimitiveWetModel(sg; radiation = Radiation(sg; longwave = fourband), ocean = SeasonalOceanClimatology(sg))
ecckd = ClearSkyEcCKDRadiation(sg; mole_fractions = (; co2 = CO2))
mc = PrimitiveWetModel(sg; radiation = ecckd, ocean = SeasonalOceanClimatology(sg))
s4, sc = initialize!(m4), initialize!(mc)

# GFDL-ESM4 band profiles
const REF = Dict{Tuple{String, String}, Vector{Tuple{Float64, Float64}}}()
for l in readlines(ENV["PROFREF"])[2:end]
    b, v, p, x = split(l, ',')
    (pp = parse(Float64, p)) > 0 || continue
    xx = parse(Float64, x)
    isfinite(xx) && push!(get!(REF, (String(b), String(v)), Tuple{Float64, Float64}[]), (pp, xx))
end
foreach(sort!, values(REF))
function refat(band, var, p_hPa)
    t = REF[(band, var)]
    p_hPa <= t[1][1] && return t[1][2]
    p_hPa >= t[end][1] && return t[end][2]
    i = searchsortedfirst([x[1] for x in t], p_hPa)
    (p0, x0), (p1, x1) = t[i - 1], t[i]
    a = (log(p_hPa) - log(p0)) / (log(p1) - log(p0))
    return (1 - a) * x0 + a * x1
end

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

band_of(lat) = abs(lat) < 15 ? "trop" : abs(lat) < 30 ? "sub" : abs(lat) < 60 ? "mid" : "pol"
function swap!(v, swapT, swapq)
    for ij in 1:npoints
        pₛ = v.parameterizations.surface_pressure[ij]
        b = band_of(lats[ij])
        for k in 1:nlayers
            pk = SpeedyWeather.pressure(k, pₛ, coord) / 100
            swapT && (v.grid.temperature[ij, k, :] .= refat(b, "T_K", pk))   # every stored time step
            swapq && (v.grid.humidity[ij, k, :] .= refat(b, "q_gkg", pk) / 1000)
        end
    end
    return nothing
end

println("\nclear-sky OLR [W/m²], $(sg.nlayers) layers, after $SPINUP days spin-up, host = FourBandLongwave + sub-stepped MSE-entraining convection, ecCKD CO2 $(CO2 * 1.0e6) ppm")
println("CERES EBAF Ed4.0 clear-sky (cloud-free scenes) global 268.1")
println("state                         |   four-band: global  |lat|<15  15-30  30-60  >=60   |   ecCKD: global  |lat|<15  15-30  30-60  >=60")
for (label, swT, swq) in (("model T, model q", false, false), ("GFDL T, model q", true, false), ("model T, GFDL q", false, true), ("GFDL T, GFDL q", true, true))
    row = Float64[]
    for (name, m, s) in ((:fourband, m4, s4), (:ecckd, mc, sc))
        v = s.variables
        copy_state!(v, hv)
        swap!(v, swT, swq)
        SpeedyWeather.reset_variables!(v)
        SpeedyWeather.global_parameterizations!(v, m)
        p = v.parameterizations
        for ij in 1:npoints
            haskey(p, :cloud_cover) && (p.cloud_cover[ij] = 0)
            haskey(p, :cloud_top) && (p.cloud_top[ij] = nlayers + 1)
            if name == :ecckd
                SpeedyWeather.parameterization!(ij, v, m.radiation, m)
            else
                SpeedyWeather.parameterization!(ij, v, m.radiation.longwave, m)
            end
        end
        olr = p.outgoing_longwave.data
        for sel in (trues(npoints), abs.(lats) .< 15, 15 .<= abs.(lats) .< 30, 30 .<= abs.(lats) .< 60, abs.(lats) .>= 60)
            push!(row, sum(w[sel] .* olr[sel]) / sum(w[sel]))
        end
    end
    @printf("%-28s  |   %8.1f %8.1f %6.1f %6.1f %6.1f   |   %8.1f %8.1f %6.1f %6.1f %6.1f\n", label, row...)
end
flush(stdout)
