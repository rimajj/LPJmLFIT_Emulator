# O3 de-risk step 1: reproduce the UPSTREAM SpeedyWeather <-> Terrarium coupling on this cluster,
# with `vegetation = nothing`, BEFORE inserting any LPJmL-FIT physics.
#
# Adapted from Terrarium.jl/examples/simulations/speedy_wet_land.jl, with CUDA / Rasters / NCDatasets /
# CairoMakie / GeoMakie stripped (headless compute node, no GPU, no plotting) — we assert on numbers instead.
# The point is a pass/fail answer to "does the stack run here at all?", so it stays deliberately small.

using Terrarium
using Dates
using Statistics
import RingGrids
import SpeedyWeather as Speedy

const NF = Float32     # the coupling type our 4 Float32 testitems already gate for

println("Terrarium ", pkgversion(Terrarium), " | SpeedyWeather ", pkgversion(Speedy), " | ", VERSION)

# ── grids ────────────────────────────────────────────────────────────────────────────────────────
ring_grid = RingGrids.FullGaussianGrid(24)          # as upstream's example
spectral_grid = Speedy.SpectralGrid(ring_grid)
Nz, Δz_min = 30, 0.05
grid = ColumnRingGrid(CPU(), NF, ExponentialSpacing(; N = Nz, Δz_min), ring_grid)
println("grid: ", typeof(grid).name.name, "  nlayers=", Nz)

# ── the Terrarium land model, vegetation slot EMPTY (upstream default) ────────────────────────────
soil_initializer = SoilInitializer(eltype(grid))
soil = SoilEnergyWaterCarbon(eltype(grid), hydrology = SoilHydrology(eltype(grid)))
terrarium_model = Terrarium.LandModel(grid; initializer = soil_initializer, vegetation = nothing, soil)

# ── wrap as a SpeedyWeather land component (this is SpeedyWeatherTerrariumExt) ────────────────────
land = Speedy.LandModel(
    spectral_grid, terrarium_model;
    timestepper = ForwardEuler(eltype(grid)),
    Δt = 300.0,
)

land_sea_mask = Speedy.RockyPlanetMask(land.spectral_grid)
surface_heat_flux = Speedy.SurfaceHeatFlux(land.spectral_grid, land = Speedy.PrescribedLandHeatFlux())
surface_humidity_flux = Speedy.SurfaceHumidityFlux(land.spectral_grid, land = Speedy.PrescribedLandHumidityFlux())
time_stepping = Speedy.Leapfrog(land.spectral_grid, Δt_at_T31 = Minute(15))

model = Speedy.PrimitiveWetModel(
    land.spectral_grid;
    land, surface_heat_flux, surface_humidity_flux, land_sea_mask, time_stepping,
)

# ── run ──────────────────────────────────────────────────────────────────────────────────────────
sim = Speedy.initialize!(model)
period = Hour(6)
println("running for $period ...")
@time Speedy.run!(sim, period = period)

# ── assert it produced finite, physically plausible land state ────────────────────────────────────
ls = sim.variables.prognostic.land.terrarium
Terrarium.checkfinite!(ls.prognostic)

Tskin = Array(interior(ls.skin_temperature)[:, 1])
H     = Array(interior(ls.sensible_heat_flux)[:, 1])
LE    = Array(interior(ls.latent_heat_flux)[:, 1])
Tsoil = Array(interior(ls.temperature)[:, 1, end])

for (nm, v) in (("T_skin", Tskin), ("H", H), ("LE", LE), ("T_soil_top", Tsoil))
    fin = filter(isfinite, v)
    @assert !isempty(fin) "$nm is entirely non-finite"
    println(rpad(nm, 11), " n=", length(fin), "/", length(v),
        "  min=", round(minimum(fin); digits = 3),
        "  mean=", round(sum(fin) / length(fin); digits = 3),
        "  max=", round(maximum(fin); digits = 3))
end
@assert all(isfinite, Tskin) "T_skin has non-finite entries"
# TERRARIUM STATE IS IN °C, NOT KELVIN. `celsius_to_kelvin` is applied only at the Thermodynamics
# boundary (processes/thermodynamics/thermodynamics.jl:34), so stored temperatures are Celsius.
# A first version of this check asserted 150..350 K and failed on a perfectly good run.
@assert -60 < sum(Tskin) / length(Tskin) < 60 "mean T_skin implausible (expect °C)"
@assert -90 < minimum(Tskin) && maximum(Tskin) < 70 "T_skin outside plausible °C range"
println("eltype(T_skin) = ", eltype(Tskin), "  (Float32 expected)")
@assert eltype(Tskin) === NF "coupling did not stay in $NF"

println("=== REFERENCE COUPLING OK ===")
