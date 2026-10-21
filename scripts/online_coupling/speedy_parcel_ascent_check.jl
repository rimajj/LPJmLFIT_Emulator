# Stand-alone check of BettsMillerConvection's parcel ascent (SpeedyWeather `pseudo_adiabat!`, no model run):
# one tropical column at T31 L8 (8 equal σ layers), parcel started from the lowermost layer, NoEntrainment, and an
# environment made cold aloft so the parcel stays buoyant to the top (the reference profile then IS the parcel).
# Compares the parcel temperature per layer with a fine integration of the SAME equations (same lapse-rate formula,
# saturation_humidity, dry adiabat; 2000 sub-steps per layer, pressure log-linear within a layer).
#   julia --project=<env with SpeedyWeather> speedy_parcel_ascent_check.jl
# Written to be pasted into an upstream SpeedyWeather issue (JOURNAL 2026-10-21 night/2026-10-22).
using SpeedyWeather, Printf

const NF = Float64
atm = EarthAtmosphere(NF)
nlayers = 8
σ = [(k - 0.5) / nlayers for k in 1:nlayers]          # 0.0625 ... 0.9375, SpeedyWeather's default L8
pₛ = 98740.0                                          # Pa, tropical mean surface pressure of a T31 L8 run
p = σ .* pₛ
# GFDL-ESM4 1985-2014 tropical (|lat| < 15) mean at these pressures: lowermost layer only matters for the parcel
T_surf_layer, q_surf_layer = 294.25, 12.856e-3
T_env = fill(200.0, 1, nlayers)                       # cold aloft: parcel buoyant to the top
q_env = fill(1.0e-6, 1, nlayers)
T_env[1, nlayers], q_env[1, nlayers] = T_surf_layer, q_surf_layer
(; κ, R_dry, R_vapor) = atm
Lᵥ, cₚ = atm.latent_heat_condensation, atm.heat_capacity

# geopotential of the layers from a moist-adiabatic-ish tropical column (hydrostatic with the GFDL-ESM4 profile)
T_gfdl = [205.76, 214.56, 242.33, 260.31, 272.15, 281.13, 288.29, 294.25]
Φ = zeros(1, nlayers)
Φ[1, nlayers] = R_dry * T_gfdl[nlayers] * log(pₛ / p[nlayers])
for k in (nlayers - 1):-1:1
    Φ[1, k] = Φ[1, k + 1] + R_dry * (T_gfdl[k] + T_gfdl[k + 1]) / 2 * log(p[k + 1] / p[k])
end

# 1. SpeedyWeather's own ascent
T_ref, q_ref = zeros(1, nlayers), zeros(1, nlayers)
lzb = SpeedyWeather.pseudo_adiabat!(1, T_ref, q_ref, T_env, q_env, Φ, pₛ, σ, atm, 0.7, NoEntrainment())

# 2. the same equations, finely integrated
function fine_ascent(nsub)
    T, q = T_surf_layer, q_surf_layer
    out = zeros(nlayers)
    out[nlayers] = T
    for k in (nlayers - 1):-1:1
        ΔΦ = (Φ[1, k] - Φ[1, k + 1]) / nsub
        for i in 1:nsub
            pa = p[k + 1] * (p[k] / p[k + 1])^((i - 1) / nsub)       # sub-step start / end pressure
            pb = p[k + 1] * (p[k] / p[k + 1])^(i / nsub)
            T_dry = T * (pb / pa)^κ
            if q < SpeedyWeather.saturation_humidity(T_dry, pb, atm)  # not saturated: dry adiabat
                T = T_dry
            else                                                     # saturated: pseudo-adiabat, as the code
                Tᵥ = T * (1 + (R_vapor / R_dry - 1) * q)
                A = q * Lᵥ / ((1 - q)^2 * R_dry)
                B = q * Lᵥ^2 / ((1 - q)^2 * cₚ * R_vapor)
                T -= ΔΦ / cₚ * (1 + A / Tᵥ) / (1 + B / T^2)
                q = SpeedyWeather.saturation_humidity(T, pb, atm)
            end
        end
        out[k] = T
    end
    return out
end
# 1b. on a branch with the opt-in sub-stepped ascent (coldfix-E), the same call with 10 sub-steps
T_sub = fill(NaN, 1, nlayers)
try
    SpeedyWeather.pseudo_adiabat!(1, T_sub, zeros(1, nlayers), T_env, q_env, Φ, pₛ, σ, atm, 0.7, NoEntrainment(), 10, false)
catch err
    err isa MethodError || rethrow()
end
fine = fine_ascent(2000)
fine10 = fine_ascent(10)

println("SpeedyWeather $(pkgversion(SpeedyWeather)): parcel from $(T_surf_layer) K, $(1000q_surf_layer) g/kg at $(round(p[end] / 100, digits = 1)) hPa, level of zero buoyancy = layer $lzb")
println("layer  σ       p hPa   pseudo_adiabat!   fine (2000 sub-steps)   difference | fine with 10 sub-steps - fine | branch ascent_substeps=10 - fine")
for k in nlayers:-1:1
    @printf(
        "  %d   %.4f  %6.1f   %8.2f K        %8.2f K               %+6.2f K   |  %+6.2f K   |  %+6.2f K\n", k, σ[k], p[k] / 100,
        T_ref[1, k], fine[k], T_ref[1, k] - fine[k], fine10[k] - fine[k], T_sub[1, k] - fine[k]
    )
end
