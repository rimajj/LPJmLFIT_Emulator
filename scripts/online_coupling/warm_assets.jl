# Warm SpeedyWeather's downloadable ASSETS (not just the Pkg depot) on the LOGIN node.
#
# WHY: `SpeedyWeather.EarthOrography` (the PrimitiveWetModel default) calls `RingGrids.get_asset` ->
# `Pkg.Artifacts.create_artifact` -> `Downloads.download` inside `initialize!`. Compute nodes have NO
# outbound network, so a SLURM job dies there with a curl RequestError. Running `initialize!` ONCE on the
# login node caches the artifact in ~/.julia/artifacts, after which the compute node finds it locally.
#
# Keep this cheap: build the model and initialize it, then stop. No time stepping.

using Terrarium
using Dates
import RingGrids
import SpeedyWeather as Speedy

const NF = Float32

for trunc in (24,)                       # add more truncations here if a run needs them
    ring_grid = RingGrids.FullGaussianGrid(trunc)
    spectral_grid = Speedy.SpectralGrid(ring_grid)
    grid = ColumnRingGrid(CPU(), NF, ExponentialSpacing(; N = 30, Δz_min = 0.05), ring_grid)
    soil = SoilEnergyWaterCarbon(eltype(grid), hydrology = SoilHydrology(eltype(grid)))
    tmodel = Terrarium.LandModel(grid; initializer = SoilInitializer(eltype(grid)), vegetation = nothing, soil)
    land = Speedy.LandModel(spectral_grid, tmodel; timestepper = ForwardEuler(eltype(grid)), Δt = 300.0)
    model = Speedy.PrimitiveWetModel(
        land.spectral_grid;
        land,
        surface_heat_flux = Speedy.SurfaceHeatFlux(land.spectral_grid, land = Speedy.PrescribedLandHeatFlux()),
        surface_humidity_flux = Speedy.SurfaceHumidityFlux(land.spectral_grid, land = Speedy.PrescribedLandHumidityFlux()),
        land_sea_mask = Speedy.RockyPlanetMask(land.spectral_grid),
        time_stepping = Speedy.Leapfrog(land.spectral_grid, Δt_at_T31 = Minute(15)),
    )
    println("initializing trunc=$trunc (downloads assets on first run) ...")
    Speedy.initialize!(model)
    println("  ok: trunc=$trunc assets cached")
end

println("=== ASSETS WARM ===")
