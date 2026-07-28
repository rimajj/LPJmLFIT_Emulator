# ADR 0082 §4 step 1 — quantify the `soilmoist` train/inference shift for Component S.
#
# WHY: `soilmoist` is a LOAD-BEARING trained feature (ADR 0023 — train/inference consistency is the worst
# silent failure mode here). At runtime S is fed `soilmoist = sum(state.w)/length(state.w)` (slow.jl:191) —
# the UNWEIGHTED mean over LPJmL's 23 layers of `w`, the FRACTION OF WATER-HOLDING CAPACITY (plant-available
# basis). Online the soil is Terrarium's, so we must supply the same QUANTITY, not merely a wetness index.
#
# THE MAPPING (ADR 0082 §4): Terrarium's `saturation_water_ice` is a fraction of POROSITY (θ/θ_sat) — a
# DIFFERENT normalization, so using it would be a definitional mismatch. `FieldCapacityLimitedPAW` computes
# W = min((θw − θwp)/(θfc − θwp), 1), which IS LPJmL's `w` semantics. This script computes BOTH from a live
# coupled run so the choice is settled by evidence rather than assertion.
#
# WHY WE DO *NOT* SWITCH ON TERRARIUM'S VEGETATION TO GET PAW DIRECTLY:
#   `plant_available_water` is an auxiliary of the PAW process inside `VegetationCarbon`. Enabling
#   `vegetation = VegetationCarbon(NF)` in a coupled run CRASHES:
#     AssertionError: vapor pressure deficit must be greater than zero
#   from MedlynStomatalConductance (medlyn_stomatal_conductance.jl:51, `@assert abs(vpd) > 0`). Saturated air
#   (VPD = 0) is physically realizable in a coupled atmosphere, so Terrarium's DEFAULT vegetation is not
#   coupled-run-robust — which is precisely why the upstream template ships `vegetation = nothing`, leaving
#   that slot unexercised. [VERIFIED 2026-07-28, job 1622826.] Worth reporting upstream.
#   So: run with `vegetation = nothing` (the configuration known to work) and reconstruct PAW POST-HOC from
#   the soil state using Terrarium's OWN hydraulic-property functions.

using Terrarium
using Dates
using DelimitedFiles
import RingGrids
import SpeedyWeather as Speedy

const NF = Float32

println("Terrarium ", pkgversion(Terrarium), " | SpeedyWeather ", pkgversion(Speedy), " | ", VERSION)

ring_grid = RingGrids.FullGaussianGrid(24)
spectral_grid = Speedy.SpectralGrid(ring_grid)
grid = ColumnRingGrid(CPU(), NF, ExponentialSpacing(; N = 30, Δz_min = 0.05), ring_grid)

soil = SoilEnergyWaterCarbon(eltype(grid), hydrology = SoilHydrology(eltype(grid)))
terrarium_model = Terrarium.LandModel(
    grid;
    initializer = SoilInitializer(eltype(grid)), vegetation = nothing, soil
)
land = Speedy.LandModel(
    spectral_grid, terrarium_model;
    timestepper = ForwardEuler(eltype(grid)), Δt = 300.0
)
model = Speedy.PrimitiveWetModel(
    land.spectral_grid;
    land,
    surface_heat_flux = Speedy.SurfaceHeatFlux(land.spectral_grid, land = Speedy.PrescribedLandHeatFlux()),
    surface_humidity_flux = Speedy.SurfaceHumidityFlux(land.spectral_grid, land = Speedy.PrescribedLandHumidityFlux()),
    land_sea_mask = Speedy.RockyPlanetMask(land.spectral_grid),
    time_stepping = Speedy.Leapfrog(land.spectral_grid, Δt_at_T31 = Minute(15)),
)

sim = Speedy.initialize!(model)
period = Day(2)          # long enough for the hydrology to relax off its initial condition
println("running for $period ...")
@time Speedy.run!(sim, period = period)

ls = sim.variables.prognostic.land.terrarium
Terrarium.checkfinite!(ls.prognostic)

# ── the soil state we have ───────────────────────────────────────────────────────────────────────
sat = Array(interior(ls.saturation_water_ice))          # fraction of POROSITY, [cell, 1, layer]
liq = Array(interior(ls.liquid_water_fraction))         # liquid fraction of total water
println("sat size = ", size(sat), "   liq size = ", size(liq))

# ── Terrarium's own hydraulic properties for this (constant) horizon ──────────────────────────────
strat = Terrarium.get_stratigraphy(soil)
hyd = Terrarium.get_hydrology(soil)
hydraulics = hyd.hydraulic_properties
horizon = first(strat.horizons)
texture = Terrarium.texture(horizon)
θfc = Terrarium.field_capacity(hydraulics, texture)
θwp = Terrarium.wilting_point(hydraulics, texture)
por = Terrarium.mineral_porosity(Terrarium.porosity(horizon), texture)
println("hydraulics: porosity=", por, "  θ_fc=", θfc, "  θ_wp=", θwp)

# ── the two candidate mappings ────────────────────────────────────────────────────────────────────
# (a) THE CLAIMED-CORRECT ONE: plant-available fraction, i.e. LPJmL `w` semantics
θw = sat .* liq .* por                                   # volumetric liquid water content
paw = clamp.((θw .- θwp) ./ (θfc .- θwp), 0, 1)
# (b) THE NAIVE ONE: fraction of porosity
satfrac = sat

layermean(v) = ndims(v) == 3 ? vec(sum(v, dims = 3) ./ size(v, 3)) : vec(v)

function report(nm, v)
    m = Float64.(layermean(v))
    fin = filter(isfinite, m)
    isempty(fin) && (println(rpad(nm, 34), "ALL NON-FINITE"); return m)
    s = sort(fin)
    q(p) = s[clamp(round(Int, p * length(s)), 1, length(s))]
    println(
        rpad(nm, 34),
        " n=", length(fin),
        "  min=", round(minimum(fin); digits = 4),
        " q10=", round(q(0.1); digits = 4),
        " q25=", round(q(0.25); digits = 4),
        " q50=", round(q(0.5); digits = 4),
        " q75=", round(q(0.75); digits = 4),
        " q90=", round(q(0.9); digits = 4),
        " max=", round(maximum(fin); digits = 4),
        " mean=", round(sum(fin) / length(fin); digits = 4)
    )
    return m
end

println("\n=== TERRARIUM soil-moisture candidates (layer-mean over 30 layers, per cell) ===")
println("LPJmL TRAINING REFERENCE (historic, 1348400 cell-years):")
println("  soilmoist                        min=0.0167 q10=0.22 q25=0.3186 q50=0.4635 q75=0.6644 q90=0.808 max=0.9886 mean=0.5075")
println()
m_paw = report("plant_available_water (a)", paw)
m_sat = report("saturation_water_ice  (b)", satfrac)

out = "/p/tmp/jamirp/esm_online_coupling/terrarium_soilmoist_candidates.csv"
open(out, "w") do io
    writedlm(io, [["paw_layermean" "sat_layermean"]], ',')
    writedlm(io, hcat(m_paw, m_sat), ',')
end
println("\nwrote $out")
println("=== SOILMOIST DIAGNOSIS DONE ===")
