# What sets SpeedyWeather's tropical upper-troposphere temperature: recompute the Betts-Miller convection's internals
# (Frierson 2007, SpeedyWeather convection.jl) on the model's own columns. Spin the PrimitiveWetModel up with the
# prescribed SST climatology, then at snapshots, for every |lat| < 15 column: the parcel reference profile
# (pseudo_adiabat!, with the configured entrainment), the column sums PT (temperature deficit) and Pq (moisture excess
# over the reference humidity) in σ units, and the deep-convection shift of the reference temperature
#   ΔT = (PT - Pq·L/cₚ) / Δσ_LZB   (T_ref = adiabat - ΔT; ΔT < 0 lifts T_ref ABOVE the parcel adiabat).
# Prints the fraction of columns in deep / shallow / no convection, the mean ΔT and level of zero buoyancy of the deep
# ones, and per layer the mean environment T, the parcel adiabat and the shifted reference in deep columns.
#   julia --project=<env> speedy_convection_diag.jl [spinup_days=120] [snapshots=40] [hours_between=6]
# Env knobs as speedy_cold_bias_repro.jl: LW=fourband, T0=speedy,
# CONVKW="relative_humidity=..,surface_entrainment=..,ascent_substeps=.." (ascent_substeps: cold-bias branch only).
using SpeedyWeather, Dates, Printf

const SPINUP = parse(Int, get(ARGS, 1, "120"))
const NSNAP = parse(Int, get(ARGS, 2, "40"))
const HOURS = parse(Int, get(ARGS, 3, "6"))

parsekw(s) = isempty(s) ? (;) : NamedTuple(Symbol(k) => parse(Float64, v) for (k, v) in (split(x, '=') for x in split(s, ',')))
spectral_grid = SpectralGrid(truncation = 32, nlayers = 8)
kw = (; ocean = SeasonalOceanClimatology(spectral_grid))
get(ENV, "LW", "") == "fourband" && (
    kw = (;
        kw..., radiation = Radiation(
            spectral_grid; shortwave = TwoBandShortwave(spectral_grid), longwave = FourBandLongwave(spectral_grid)
        ),
    )
)
get(ENV, "T0", "") == "speedy" && (
    kw = (;
        kw..., boundary_layer = BoundaryLayer(
            spectral_grid; surface_condition = SurfaceCondition(spectral_grid; actual_lapse_rate = true)
        ),
    )
)
const CONVKW = parsekw(get(ENV, "CONVKW", ""))
if !isempty(CONVKW)
    ent = (; (k => v for (k, v) in pairs(CONVKW) if k in (:surface_entrainment, :σ_entrainment))...)
    bm = (; (k => v for (k, v) in pairs(CONVKW) if k == :relative_humidity)...)
    haskey(CONVKW, :ascent_substeps) && (bm = (; bm..., ascent_substeps = round(Int, CONVKW.ascent_substeps)))
    haskey(CONVKW, :entrainment_mse) && (bm = (; bm..., entrainment_mse = CONVKW.entrainment_mse == 1))
    kw = (; kw..., convection = BettsMillerConvection(spectral_grid; entrainment = LinearEntrainment(spectral_grid; ent...), bm...))
end
println("knobs: LW = $(get(ENV, "LW", "grey")), T0 = $(get(ENV, "T0", "dry adiabat")), CONVKW = $CONVKW")
model = PrimitiveWetModel(spectral_grid; kw...)
simulation = initialize!(model; time = DateTime(2015, 1, 1))
run!(simulation, period = Day(SPINUP))

vars = simulation.variables
conv = model.convection
_, lats = SpeedyWeather.RingGrids.get_londlatds(spectral_grid.grid)
Ω = SpeedyWeather.RingGrids.get_solid_angles(typeof(spectral_grid.grid), spectral_grid.grid.nlat_half)
w = zeros(length(lats))
for (j, ring) in enumerate(SpeedyWeather.RingGrids.eachring(spectral_grid.grid))
    w[ring] .= Ω[j]
end
band = findall(abs.(lats) .< 15)
lf = model.land_sea_mask.land_fraction
nlayers = spectral_grid.nlayers
σ, σ_half, Δσ = model.geometry.σ_levels_full, model.geometry.σ_levels_half, model.geometry.σ_levels_thick
L, cₚ = model.atmosphere.latent_heat_condensation, model.atmosphere.heat_capacity

Tref = zeros(spectral_grid.npoints, nlayers)
qref = zeros(spectral_grid.npoints, nlayers)
W = Dict(s => 0.0 for s in (:all, :deep, :shallow, :deep_land))
S = Dict{Symbol, Float64}()
P = Dict(n => zeros(nlayers) for n in (:T_all, :T_deep, :Tad_deep, :Tref_deep, :q_deep, :qref_deep))
add!(k, x, wt) = (S[k] = get(S, k, 0.0) + wt * x)

for s in 1:NSNAP
    run!(simulation, period = Hour(HOURS))
    T = SpeedyWeather.get_prognostic_step(vars.grid.temperature, model.time_stepping, conv)
    q = SpeedyWeather.get_prognostic_step(vars.grid.humidity, model.time_stepping, conv)
    Φ = vars.dynamics.geopotential
    for ij in band
        wt = w[ij]
        pₛ = vars.parameterizations.surface_pressure[ij]
        lzb = SpeedyWeather.pseudo_adiabat!(
            ij, Tref, qref, T, q, Φ, pₛ, σ, model.atmosphere, conv.relative_humidity, conv.entrainment,
            hasproperty(conv, :ascent_substeps) ? conv.ascent_substeps : 1,
            hasproperty(conv, :entrainment_mse) ? conv.entrainment_mse : false
        )
        PT = Pq = Qref = 0.0
        for k in 1:nlayers
            Pq += (q[ij, k] - qref[ij, k]) * Δσ[k]
            PT -= (T[ij, k] - Tref[ij, k]) * Δσ[k]
            k >= lzb && (Qref -= qref[ij, k] * Δσ[k])
        end
        deep, shallow = Pq > 0 && PT > 0, Pq <= 0 && PT > 0
        W[:all] += wt
        P[:T_all] .+= wt .* T[ij, :]
        if deep
            Δσ_lzb = σ_half[nlayers + 1] - σ_half[lzb]
            ΔT = (PT - Pq * L / cₚ) / Δσ_lzb
            W[:deep] += wt
            lf[ij] > 0.5 && (W[:deep_land] += wt)
            add!(:ΔT, ΔT, wt)
            add!(:PT, PT / Δσ_lzb, wt)
            add!(:PqL, Pq * L / cₚ / Δσ_lzb, wt)
            add!(:lzb, lzb, wt)
            add!(:sfcT, T[ij, nlayers], wt)
            add!(:sfcq, 1000 * q[ij, nlayers], wt)
            for k in 1:nlayers
                P[:T_deep][k] += wt * T[ij, k]
                P[:Tad_deep][k] += wt * Tref[ij, k]
                P[:Tref_deep][k] += wt * (Tref[ij, k] - (k >= lzb ? ΔT : 0.0))
                P[:q_deep][k] += wt * 1000 * q[ij, k]
                P[:qref_deep][k] += wt * 1000 * qref[ij, k]
            end
        elseif shallow
            W[:shallow] += wt
        end
    end
end

println("\nBetts-Miller internals, |lat| < 15, $NSNAP snapshots every $HOURS h after $SPINUP days")
@printf(
    "column fraction: deep %.3f (of which land %.3f), shallow %.3f, none %.3f\n",
    W[:deep] / W[:all], W[:deep_land] / max(W[:deep], eps()), W[:shallow] / W[:all], 1 - (W[:deep] + W[:shallow]) / W[:all]
)
d = W[:deep]
@printf(
    "deep columns: mean ΔT %+.2f K (T deficit PT/Δσ %.2f K, moisture excess Pq·L/cₚ/Δσ %.2f K), mean LZB layer %.2f\n",
    S[:ΔT] / d, S[:PT] / d, S[:PqL] / d, S[:lzb] / d
)
@printf("deep columns: lowest layer T %.2f K, q %.2f g/kg\n", S[:sfcT] / d, S[:sfcq] / d)
println("layer  σ      T all   T deep  adiabat  T_ref(shifted)  q deep  q_ref  [K, g/kg]")
for k in 1:nlayers
    @printf(
        "  %d  %.3f  %7.2f %7.2f %7.2f %9.2f      %7.3f %7.3f\n", k, σ[k], P[:T_all][k] / W[:all],
        (P[n][k] / d for n in (:T_deep, :Tad_deep, :Tref_deep, :q_deep, :qref_deep))...
    )
end
flush(stdout)
