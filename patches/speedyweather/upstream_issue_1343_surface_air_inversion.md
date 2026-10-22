# Near-surface air temperature in an inversion is the lowermost layer's: most of a +13 K high-latitude winter bias is this definition

(SpeedyWeather/SpeedyWeather.jl#1343, filed 2026-10-22 as rimajj)

**Summary.** `surface_air_temperature` is the lowermost layer's temperature (σ ≈ 0.94 at L8, ~550 m up) brought down to the surface along the dry adiabat. In a stable boundary layer, such as a high-latitude winter inversion, that is not a near-surface (2 m) temperature: it is several K warmer than the air at the ground. In our runs about two thirds of a +13 K high-latitude coldest-month bias is this definition, not the model climate. We propose two things:
1. An opt-in speedy.f90 surface air temperature: extrapolate with the actual lapse rate between the two lowermost layers, and keep the lowermost layer's temperature in an inversion. It is on a branch.
2. A diagnostic 2 m air temperature output, used for output and comparison with observations only. A sketch is below.

We also tested stronger stable mixing near the surface, which does not help.

Context: #1333, and the model setup there (T31 L8, `main` d6e3286d + #1332 + #1284 + #1283 + #1262). On top of it are our four-band longwave port (#1342) and the #1339 convection options (`ascent_substeps = 10, entrainment_mse = true`). Prescribed seasonal SST, 3 years, years 2–3 scored, single realisations. The reference is GFDL-ESM4 historical r1i1p1f1 1985–2014, interpolated to the model's layer pressures. Its `tas` matches W5E5 observations over land to 0.01 K at these columns.

## 1. Where the high-latitude winter excess sits

These are the 322 T31 land columns poleward of 50°, each in its own GFDL-ESM4 coldest month. The table shows model − GFDL-ESM4:

| level | bias [K] |
|---|---|
| 414 hPa | +0.0 |
| 532 hPa | +0.8 |
| 650 hPa | +2.9 |
| 768 hPa | +4.9 |
| 889 hPa (lowermost layer) | +7.6 |
| `surface_air_temperature` | **+13.0** |
| diagnostic 2 m air temperature (below) | **+4.4** |
| top soil layer vs GFDL-ESM4 skin `ts` | +4.0 |

In the model, the reported surface air is +9.0 K warmer than its own top soil layer. In GFDL-ESM4, `tas − ts` is +0.1 K. So the model's near-surface air is the inversion top, not the air at the ground. About 8.6 of the 13 K disappear when the temperature is evaluated at 2 m. The remaining ~4.4 K is a real excess. It sits in the atmosphere, not at the land surface: the lower troposphere (650–890 hPa) is 3–8 K too warm there, and over ice-free ocean ≥ 50° the surface air is 1.2 K warmer than the prescribed SST.

(The 2 m values in this run come from a first version of the diagnostic that also applied the log profile in unstable air. Both versions are identical whenever the air is warmer than the ground, which is the case here: +9 K in the mean.)

## 2. Stronger stable mixing does not fix it

Raising the critical Richardson number from 1 to 3 (the "long-tail" stability functions of operational models) does not help. Coldest month, poleward of 50°, model − GFDL-ESM4; columns are lowermost layer / reported surface air / 2 m diagnostic / soil:

| | lowermost layer | surface air | 2 m | soil |
|---|---|---|---|---|
| control | +7.6 | +13.0 | +4.4 | +4.0 |
| surface drag Ri_c 1 → 3 | +6.8 | +11.7 | +6.1 | +5.7 |
| + vertical diffusion Ri_c 1 → 3 | +7.3 | +12.5 | +6.6 | +6.1 |

More mixing brings the inversion's warmth down into the soil.

## 3. Proposed changes

**(a) Opt-in speedy.f90 surface air temperature** (`surface_fluxes.f90`, `ftemp0 = 1`). This is a small change in `SurfaceCondition`, default off and bit-identical:

```diff
+    "[OPTION] Surface air temperature as in speedy.f90: extrapolated with the actual lapse rate between the two lowermost layers (to `σ_surface_air`), or the lowermost layer's temperature in an inversion, instead of along the dry adiabat"
+    actual_lapse_rate::Bool = false
+
+    "[OPTION] σ of the surface air for `actual_lapse_rate` (speedy.f90: 0.99) [1]"
+    σ_surface_air::NF = 0.99
 ...
-    T *= σ⁻ᵏ                                        # lower to surface assuming dry adiabatic lapse rate
+    if surface_condition.actual_lapse_rate && nlayers > 1
+        # speedy.f90 surface_fluxes.f90 1.2 (ftemp0 = 1): extrapolate with the actual lapse rate,
+        # linear in log σ, if temperature decreases with height, else (inversion) the lowermost layer's
+        T₁ = temperature[ij, nlayers - 1]
+        lnσ₁ = log(pressure(nlayers - 1, pₛ, coord) / pₛ)
+        w = (log(surface_condition.σ_surface_air) - log(σ)) / (log(σ) - lnσ₁)
+        T = T > T₁ ? T + w * (T - T₁) : T
+    else
+        T *= σ⁻ᵏ                                    # lower to surface assuming dry adiabatic lapse rate
+    end
```

In an inversion this avoids the extra ~5 K the dry adiabat adds between the lowermost layer and the surface. Prescribed SST, land vs W5E5, annual / warmest / coldest month: +3.7 / +2.6 / +6.0 K without it, +2.1 / +1.4 / +4.0 K with it (four-band longwave, `main` convection).

**(b) A diagnostic 2 m air temperature output** (not fed back into the fluxes). The version we use:
- **Profile:** a surface-layer profile between the top soil (or SST) temperature and `surface_air_temperature` at the lowermost layer's height z₁. It is log-linear Monin–Obukhov, `ln(z/z₀ₕ) + β z/L`, with heat roughness z₀ₕ = z₀/10.
- **Stability:** z₁/L is matched to the model's own drag, `C = C_neutral (1 − Ri/Ri_c)²`, so `β z₁/L = ln(z₁/z₀) r/(1 − r)` with `r = 1 − sqrt(C/C_neutral)`.
- **Only in stable air:** it applies only when the air is warmer than the ground. In unstable or neutral air it returns `surface_air_temperature`, because the mixed layer keeps the near-surface air close to it. A neutral log profile there leans towards the hot ground (+3 K in the warmest month in our runs).

<details><summary>Julia sketch (land; per column)</summary>

```julia
function air_2m(ij, vars, model, soilT)
    p = vars.parameterizations
    g, κ = model.planet.gravity, 0.4
    z₀ = max(p.land.surface_roughness[ij], 1.0e-3)   # momentum roughness, as in the model's drag
    z₁ = max(vars.dynamics.geopotential[ij, size(vars.dynamics.geopotential, 2)] / g - model.orography.orography[ij], 10z₀)
    C_n = (κ / log(z₁ / z₀))^2
    r = clamp(1 - sqrt(max(p.boundary_layer_drag[ij], 0) / C_n), 0.0, 0.999)
    X = log(z₁ / z₀) * r / (1 - r)                   # β z₁/L
    z₀ₕ = z₀ / 10                                     # heat roughness
    F = (log(2 / z₀ₕ) + 2 / z₁ * X) / (log(z₁ / z₀ₕ) + X)
    Tₛ, Tₐ = soilT[ij, 1], p.surface_air_temperature[ij]
    return Tₐ <= Tₛ ? Tₐ : Tₛ + F * (Tₐ - Tₛ)
end
```
</details>

In the coldest month it gives +4.4 K vs GFDL-ESM4 `tas` instead of +13.0 K (table in §1). In a run that differs only in its cloud and clear-sky shortwave settings, it gives land annual +1.1 K vs W5E5 (+3.5 K poleward of 50°), against +2.4 K (+7.4 K) for `surface_air_temperature`.

Caveats: it has no displacement height, so it is not valid over tall canopies. Where the ground is evaporatively cooled to the air temperature (a wet, strongly evaporating surface), its stable branch fires often and pulls the value down. With a land model evaporating ~3× more than SpeedyWeather's bucket in the tropics, we saw it come out 2.4 K below the air there. So we suggest it as an output diagnostic and would not feed it to a land model as is.

Happy to make (a) a PR, and (b) an output variable if you want it.
