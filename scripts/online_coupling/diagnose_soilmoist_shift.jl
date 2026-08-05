# O3a + O3b — prescribe a REAL soil texture for the online soil, prove it is non-degenerate, and
# quantify the `soilmoist` train/inference shift for Component S.  (ADR 0082 §4 steps 1-2.)
#
# WHY O3a IS A PREREQUISITE, NOT A REFINEMENT
# Terrarium's DEFAULT stratigraphy is pure sand (`clay = 0`), which collapses SURFEX's
# `wilting_point = 37.13e-3·√(clay·100)` and `field_capacity = 89.0e-3·(clay·100)^0.35` to EXACTLY
# zero, so `plant_available_water = max(min(1, (θw−θwp)/(θfc−θwp)), 0) ≡ 1` wherever θw > 0.  It
# does not error — it silently reports "fully unstressed everywhere".  [VERIFIED 2026-07-28, job
# 1622830; `online-coupling-env` trap 6.]  So this script now runs on a `PrescribedSoilHorizon`
# carrying the LPJmL-FIT ground-truth texture (`soil_texture.jl`), behind a guard that rejects any
# configuration with `field_capacity <= wilting_point`.
#
# WHY THE `soilmoist` COMPARISON MATTERS
# `soilmoist` is a LOAD-BEARING trained feature of Component S (ADR 0023 — train/inference
# consistency is the worst silent failure mode here).  Online the soil is Terrarium's, so we must
# supply the same QUANTITY, not merely a wetness index.
#
# ⚠️ BOTH SIDES OF THIS COMPARISON MOVED IN ADR 0035 (line S, 2026-07-28). Verified here against
# `src/components/slow.jl:227` before retargeting — do not revert to the older basis:
#   * The RUNTIME target is no longer `sum(state.w)/length(state.w)` (an unweighted mean over all
#     23 LPJmL layers). It is `root_zone_soilmoist(state, soil)` = the **`whcs`-weighted mean of
#     `state.w` over the top `ROOT_ZONE_LAYERS = 3` layers** — LPJmL's 200 + 300 + 500 mm, i.e.
#     exactly **1.0 m** — read at YEAR END.
#   * The REFERENCE distribution is no longer the `swc`-derived table (mean 0.5075): that was total
#     water over SATURATION capacity, i.e. the porosity-normalized quantity we are deliberately
#     avoiding. The live table is `tables/cell_year_soilmoist_ye_hist.parquet`.
#
# THE MAPPING (ADR 0082 §4): Terrarium's `saturation_water_ice` is a fraction of POROSITY
# (θ/θ_sat) — a DIFFERENT normalization, so using it would be a definitional mismatch.
# `FieldCapacityLimitedPAW` computes W = min((θw − θwp)/(θfc − θwp), 1), which IS LPJmL's `w`
# semantics.  This script computes BOTH so the choice is settled by evidence, not assertion.
#
# WHY WE DO *NOT* SWITCH ON TERRARIUM'S VEGETATION TO GET PAW DIRECTLY:
#   `plant_available_water` is an auxiliary of the PAW process inside `VegetationCarbon`. Enabling
#   `vegetation = VegetationCarbon(NF)` in a coupled run CRASHES:
#     AssertionError: vapor pressure deficit must be greater than zero
#   from MedlynStomatalConductance (medlyn_stomatal_conductance.jl:51, `@assert abs(vpd) > 0`). Saturated air
#   (VPD = 0) is physically realizable in a coupled atmosphere, so Terrarium's DEFAULT vegetation is not
#   coupled-run-robust — which is precisely why the upstream template ships `vegetation = nothing`, leaving
#   that slot unexercised. [VERIFIED 2026-07-28, job 1622826.] Worth reporting upstream.
#   So: run with `vegetation = nothing` (the configuration known to work) and evaluate PAW POST-HOC
#   by calling Terrarium's OWN `compute_plant_available_water` kernel function on the coupled state.

using Terrarium
using Dates
using DelimitedFiles
import RingGrids
import SpeedyWeather as Speedy

include(joinpath(@__DIR__, "soil_texture.jl"))

const NF = Float32
const OUTDIR = "/p/tmp/jamirp/esm_online_coupling"

# Knobs (env, so one script serves the O3a gate and the O3b spin-up):
#   FLOW   = "noflow" (Terrarium's default immobile water) | "rre" (Richardson-Richards)
#   DAYS   = simulated days
#   DZMAX  = bottom layer thickness (m), which sets the COLUMN DEPTH. Terrarium's default
#            `Δz_max = 100` gives a **433 m** column for N = 30 — 20× LPJmL's 20 m. The root-zone
#            measure below is depth-restricted so it is insensitive to this, but the whole-column
#            contrast and the DRAINAGE TIMESCALE are not: a 433 m column started near saturation is
#            still draining after 10 days. `DZMAX=2.5` gives ≈19.5 m, matching LPJmL's geometry and
#            equilibrating ~20× faster. It also puts more layers inside the top 1 m.
#   TAG    = suffix for the output CSV
const FLOW = get(ENV, "FLOW", "rre")
const DAYS = parse(Int, get(ENV, "DAYS", "10"))
const DZMAX = parse(Float64, get(ENV, "DZMAX", "100.0"))
const TAG = get(ENV, "TAG", FLOW)

println("Terrarium ", pkgversion(Terrarium), " | SpeedyWeather ", pkgversion(Speedy), " | ", VERSION)

ring_grid = RingGrids.FullGaussianGrid(24)
spectral_grid = Speedy.SpectralGrid(ring_grid)
vert = ExponentialSpacing(; N = 30, Δz_min = 0.05, Δz_max = DZMAX)
grid = ColumnRingGrid(CPU(), NF, vert, ring_grid)

# ── O3a: the real soil ────────────────────────────────────────────────────────────────────────
# `prescribed_texture_soil` runs `assert_nondegenerate_soil` internally and throws if SURFEX's
# field capacity is not strictly above its wilting point anywhere.
vertical_flow = FLOW == "rre" ? Terrarium.RichardsEq() : Terrarium.NoFlow()
println("FLOW=", FLOW, " (", typeof(vertical_flow), ")  DAYS=", DAYS)
soil, soil_fields, is_land, texture = prescribed_texture_soil(grid; vertical_flow)
println("clay fraction on the ring grid: min=", minimum(texture.clay), " max=", maximum(texture.clay))

terrarium_model = Terrarium.LandModel(
    grid;
    initializer = SoilInitializer(eltype(grid)), vegetation = nothing, soil
)
land = Speedy.LandModel(
    spectral_grid, terrarium_model;
    timestepper = ForwardEuler(eltype(grid)), Δt = 300.0,
    # `fields`, NOT `inputs`: SpeedyWeatherTerrariumExt builds its ModelIntegrator with an EMPTY
    # `InputSources(NF)`, so an InputSource-based texture prescription is silently dropped under
    # SpeedyWeather. Only `TerrariumLand.fields` reaches `Terrarium.initialize`.
    fields = soil_fields,
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
ls = sim.variables.prognostic.land.terrarium

# GATE 0 — the prescribed texture actually landed in the state (a silently-dropped prescription
# would leave the `sand_fraction` default of 1.0 / `clay_fraction` of 0.0 everywhere).
state_clay = vec(Array(interior(ls.soil.clay_fraction)))
println("state clay_fraction: min=", minimum(state_clay), " max=", maximum(state_clay), " mean=", sum(state_clay) / length(state_clay))
@assert maximum(state_clay) > 0.01 "clay_fraction is ~0 in the model state — the `fields` prescription did not reach Terrarium"
@assert maximum(state_clay) - minimum(state_clay) > 0.01 "clay_fraction is spatially constant — the texture map did not reach Terrarium"

period = Day(DAYS)
println("running for $period ...")
@time Speedy.run!(sim, period = period)

ls = sim.variables.prognostic.land.terrarium
Terrarium.checkfinite!(ls.prognostic)

# ── PAW from Terrarium's OWN kernel function, evaluated post-hoc on the coupled state ──────────
strat = Terrarium.get_stratigraphy(soil)
hydrology = Terrarium.get_hydrology(soil)
bgc = Terrarium.get_biogeochemistry(soil)
paw_proc = Terrarium.FieldCapacityLimitedPAW(NF)

sat = Array(interior(ls.saturation_water_ice))          # fraction of POROSITY, [cell, 1, layer]
ncol, _, nz = size(sat)
println("soil state size = ", size(sat), "  (", ncol, " columns × ", nz, " layers)")

paw = Array{Float64}(undef, ncol, nz)
for k in 1:nz, i in 1:ncol
    paw[i, k] = Terrarium.compute_plant_available_water(i, 1, k, grid, ls, paw_proc, strat, hydrology, bgc)
end

# Layer thicknesses (m) in OCEANANIGANS index order. `ColumnRingGrid` builds its z axis as
# `vcat(-reverse(cumsum(get_spacing(vert))), 0)`, i.e. `get_spacing` is ordered surface-first while
# the Oceananigans k index runs deepest (k=1) to surface (k=nz) — so reverse it.
Δz = reverse(Float64.(Terrarium.get_spacing(vert)))
@assert length(Δz) == nz "vertical spacing has $(length(Δz)) layers but the state has $nz"
depth_bottom = [sum(@view Δz[k:end]) for k in 1:nz]     # depth below the surface of layer k's BOTTOM
println(
    "column: ", nz, " layers, total depth ", round(sum(Δz); digits = 2), " m, ",
    "top layer ", round(Δz[end]; digits = 3), " m"
)

# ── the candidate mappings ─────────────────────────────────────────────────────────────────────
# (a2) THE TARGET (ADR 0035): `root_zone_soilmoist` = the `whcs`-weighted mean of the
#      plant-available fraction over the top **1.0 m** (LPJmL's ROOT_ZONE_LAYERS = 3 layers of
#      200 + 300 + 500 mm). Terrarium's per-layer analogue of `whcs[l]` is the plant-available
#      capacity `(θfc − θwp)·Δz`. With a SINGLE `PrescribedSoilHorizon` the texture — and hence
#      `θfc − θwp` — is depth-constant within a column, so that factor cancels in the normalized
#      weighted mean and the capacity weighting reduces EXACTLY to thickness weighting. That
#      equivalence is a property of this one-horizon configuration; it would NOT hold under a
#      multi-horizon stratigraphy, where the capacity weights must be carried explicitly.
# (a1) whole-column unweighted mean — the PRE-ADR-0035 basis, kept only as a labelled contrast to
#      show how far off it is. It is NOT the target: the column is 433 m deep by default, so it is
#      dominated by deep permanently saturated layers.
# (b)  fraction of porosity — reported only to show it is the wrong QUANTITY (porosity- vs
#      WHC-normalized, ADR 0082 §4), which is also what the retired `swc`-derived reference was.
const ROOT_ZONE_DEPTH_M = 1.0
rootzone = depth_bottom .<= ROOT_ZONE_DEPTH_M
w_rz = Δz .* rootzone
@assert sum(w_rz) > 0 "no layer bottom lies within $(ROOT_ZONE_DEPTH_M) m — check Δz_min/DZMAX"
m_paw_unw = vec(sum(paw, dims = 2)) ./ nz
m_paw_rz = vec(paw * w_rz) ./ sum(w_rz)
m_sat = vec(sum(sat, dims = 3)) ./ nz
println(
    "root zone: ", count(rootzone), " of ", nz, " layers within ", ROOT_ZONE_DEPTH_M, " m ",
    "(", round(sum(w_rz); digits = 3), " m of soil)"
)

function report(nm, m, sel)
    fin = filter(isfinite, m[sel])
    if isempty(fin)
        println(rpad(nm, 38), "ALL NON-FINITE")
        return
    end
    s = sort(fin)
    q(p) = s[clamp(round(Int, p * length(s)), 1, length(s))]
    println(
        rpad(nm, 38),
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
    return
end

println("\n=== TERRARIUM soil-moisture candidates, LAND columns only (n=", count(is_land), " of ", ncol, ") ===")
println("LPJmL TRAINING REFERENCE (historic, 1348400 cell-years):")
println("  LIVE  soilmoist_ye (ADR 0035)          min=0.0    q10=0.0  q25=0.0    q50=0.498  q75=0.877  q90=0.9999 max=1.0078 mean=0.478")
println("  (RETIRED swc-derived, do NOT score against it: q50=0.4635 mean=0.5075 — porosity-normalized)")
println()
report("plant_available_water (a1 unweighted)", m_paw_unw, is_land)
report("plant_available_water (a2 ROOT ZONE 1 m)", m_paw_rz, is_land)
report("saturation_water_ice  (b naive)", m_sat, is_land)

# ── THE O3a GATE: the SOIL CONFIGURATION must not be degenerate ───────────────────────────────
# Trap 6 is a property of the soil CONFIGURATION, not of any particular water state: at clay = 0
# the PAW denominator is identically zero, so PAW is 1 by construction and cannot respond to water
# at all. The gate therefore tests exactly that — that PAW is a real function of the soil state:
#   (i)  the denominator fc − wp is strictly positive with real spatial spread (checked in the
#        guard, above), and
#   (ii) PAW actually varies across columns rather than being pinned at 1 everywhere.
# How MUCH of the domain sits at PAW = 1 is a property of the WATER state (initializer + flow
# scheme + spin-up), not of the soil configuration — it is reported, not gated.
paw_land = m_paw_unw[is_land]
frac_at_one = count(>=(0.999), paw_land) / length(paw_land)
spread = maximum(paw_land) - minimum(paw_land)
println(
    "\nO3a GATE: PAW spread over land columns = ", round(spread; digits = 4),
    "; fraction pinned at 1.0 = ", round(100 * frac_at_one; digits = 2), " %"
)
@assert spread > 0.05 "PAW is effectively constant across cells ($spread) — the soil is still degenerate"
println(
    "O3a GATE PASS — PAW is a genuine, spatially varying function of the soil state ",
    "(under the default sand soil it is identically 1.0 by construction)."
)

# ── O3b readiness: is the WATER STATE itself informative? ──────────────────────────────────────
# A run whose soil water never moves cannot be compared against LPJmL's `soilmoist` at all: the
# distribution would be the initializer's, not the model's.
sat_land = m_sat[is_land]
sat_spread = maximum(sat_land) - minimum(sat_land)
println(
    "water-state check: layer-mean saturation spread over land = ", round(sat_spread; digits = 5),
    " (flow scheme = ", FLOW, ")"
)
if sat_spread < 1.0e-4
    println(
        "O3b NOT MEANINGFUL: the soil water is spatially uniform — this is the SoilInitializer's ",
        "`SaturationWaterTable` (vadose 0.75 / saturated below 5 m), unchanged. With `NoFlow` the ",
        "water is immobile no matter how much rainfall the adapter pushes in. Re-run with FLOW=rre ",
        "and a spin-up before quoting any `soilmoist` comparison."
    )
else
    println("O3b: the soil water has developed spatial structure; the comparison above is a model result.")
end

out = joinpath(OUTDIR, "terrarium_soilmoist_candidates_$(TAG).csv")
open(out, "w") do io
    writedlm(io, [["paw_unweighted" "paw_rootzone_1m" "sat_layermean" "clay" "is_land"]], ',')
    writedlm(io, hcat(m_paw_unw, m_paw_rz, m_sat, texture.clay, Int.(is_land)), ',')
end
println("\nwrote $out")
println("=== SOILMOIST DIAGNOSIS DONE ===")
