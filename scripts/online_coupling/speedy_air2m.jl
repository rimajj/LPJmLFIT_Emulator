# Diagnostic 2 m air temperature over land [K] for SpeedyWeather (not used by the model itself). Shared by
# speedy_cold_bias_repro.jl (scoring) and run_speedy_landemu.jl (AIR = 2m: what the emulator is fed).
#
# Why: SpeedyWeather's surface air temperature is the lowermost layer's (~550 m up at L8) brought down to the surface;
# in a winter inversion that is several K warmer than a 2 m temperature (JOURNAL 2026-10-22 night: two thirds of the
# +13 K high-latitude coldest-month bias is this definition).
#
# The surface-layer profile (heat roughness z₀/10) between the top soil temperature and the model's surface air
# temperature (what its sensible heat flux uses, at the lowermost layer's height z₁), log-linear Monin-Obukhov form
# ln(z/z₀) + β z/L with the stability z₁/L matched to the model's own Frierson (2006) drag C = C_neutral (1 - Ri/Ri_c)²,
# i.e. β z₁/L = ln(z₁/z₀) r/(1 - r) with r = 1 - sqrt(C/C_neutral). Neutral or unstable: the model's own surface air
# temperature (see below); strongly stable: close to linear in z, i.e. close to the soil temperature.
function air_2m(ij, vars, model, soilT)
    p = vars.parameterizations
    g, κ = model.planet.gravity, 0.4
    z₀ = max(p.land.surface_roughness[ij], 1.0e-3)   # momentum roughness, as in the model's drag
    z₁ = max(vars.dynamics.geopotential[ij, size(vars.dynamics.geopotential, 2)] / g - model.orography.orography[ij], 10z₀)
    C_n = (κ / log(z₁ / z₀))^2
    r = clamp(1 - sqrt(max(p.boundary_layer_drag[ij], 0) / C_n), 0.0, 0.999)
    X = log(z₁ / z₀) * r / (1 - r)                   # β z₁/L
    z₀ₕ = z₀ / 10                                     # heat roughness, ln(z₀/z₀ₕ) ≈ 2.3
    F = (log(2 / z₀ₕ) + 2 / z₁ * X) / (log(z₁ / z₀ₕ) + X)
    Tₛ, Tₐ = soilT[ij, 1], p.surface_air_temperature[ij]
    # unstable or neutral (air not warmer than the ground): the mixed layer keeps the near-surface air close to the
    # model's surface air temperature (a neutral log profile would lean towards the hot ground: +3 K in the warmest month)
    return Tₐ <= Tₛ ? Tₐ : Tₛ + F * (Tₐ - Tₛ)
end
