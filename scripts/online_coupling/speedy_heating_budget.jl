# Temperature budget by process for SpeedyWeather (stand-alone, no emulator): spin the default PrimitiveWetModel up
# with the prescribed SST climatology, then at regular snapshots recompute every column parameterization's
# temperature tendency SEPARATELY on the model state (as in SpeedyWeather#1279's humidity budget) and average
# them per layer over a latitude band, in K/day. The dynamics is not included (it is the residual).
#   julia --project=<env> speedy_heating_budget.jl [spinup_days=120] [snapshots=40] [hours_between=6]
# Same env knobs as speedy_cold_bias_repro.jl: LW=fourband, T0=speedy (cold-bias fix branch). Band: |lat| < 15.
using SpeedyWeather, Dates, Printf

const SPINUP = parse(Int, get(ARGS, 1, "120"))
const NSNAP = parse(Int, get(ARGS, 2, "40"))
const HOURS = parse(Int, get(ARGS, 3, "6"))

spectral_grid = SpectralGrid(truncation = 32, nlayers = 8)
kw = (; ocean = SeasonalOceanClimatology(spectral_grid))
get(ENV, "LW", "") == "fourband" && (kw = (; kw..., radiation = Radiation(spectral_grid; longwave = FourBandLongwave(spectral_grid))))
get(ENV, "T0", "") == "speedy" && (
    kw = (;
        kw..., boundary_layer = BoundaryLayer(
            spectral_grid;
            surface_condition = SurfaceCondition(spectral_grid; actual_lapse_rate = true),
        ),
    )
)
model = PrimitiveWetModel(spectral_grid; kw...)
simulation = initialize!(model; time = DateTime(2015, 1, 1))
run!(simulation, period = Day(SPINUP))

vars = simulation.variables
params = SpeedyWeather.get_parameterizations(model)
names = keys(params)
_, lats = SpeedyWeather.RingGrids.get_londlatds(model.spectral_grid.grid)
Ω = SpeedyWeather.RingGrids.get_solid_angles(typeof(model.spectral_grid.grid), model.spectral_grid.grid.nlat_half)
w = zeros(length(lats))
for (j, ring) in enumerate(SpeedyWeather.RingGrids.eachring(model.spectral_grid.grid))
    w[ring] .= Ω[j]
end
band = findall(abs.(lats) .< 15)
nlayers = model.spectral_grid.nlayers
budget = Dict(n => zeros(nlayers) for n in names)
Tmean = zeros(nlayers)
dTdt = SpeedyWeather.get_tendency_step(vars.tendencies.grid.temperature, model.time_stepping, model.radiation)
T = SpeedyWeather.get_prognostic_step(vars.grid.temperature, model.time_stepping, model.radiation)
W = sum(w[band])

for s in 1:NSNAP
    run!(simulation, period = Hour(HOURS))
    SpeedyWeather.reset_variables!(vars)
    SpeedyWeather.global_parameterizations!(vars, model)
    for n in names
        dTdt .= 0
        for ij in 1:model.spectral_grid.npoints
            SpeedyWeather.parameterization!(ij, vars, params[n], model)
        end
        for k in 1:nlayers
            budget[n][k] += sum(w[ij] * dTdt[ij, k] for ij in band) / W * 86400 / NSNAP
        end
    end
    for k in 1:nlayers
        Tmean[k] += sum(w[ij] * T[ij, k] for ij in band) / W / NSNAP
    end
end

σ = model.geometry.σ_levels_full
println("\ntemperature tendency by process, |lat| < 15, K/day, $NSNAP snapshots every $HOURS h after $SPINUP days")
println("knobs: LW = $(get(ENV, "LW", "grey")), T0 = $(get(ENV, "T0", "dry adiabat"))")
shown = [n for n in names if any(!iszero, budget[n])]
@printf("%-6s %-8s", "σ", "T [K]")
foreach(n -> @printf("%12s", first(string(n), 11)), shown)
@printf("%10s\n", "sum")
for k in 1:nlayers
    @printf("%-6.3f %-8.2f", σ[k], Tmean[k])
    foreach(n -> @printf("%12.3f", budget[n][k]), shown)
    @printf("%10.3f\n", sum(budget[n][k] for n in shown))
end
flush(stdout)
