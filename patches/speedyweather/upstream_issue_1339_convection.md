**Summary.** Two things in `BettsMillerConvection`'s parcel ascent (`pseudo_adiabat!`) make the reference profile too warm in the upper troposphere, and the column relaxes to it. At T31 L8 the tropical (|lat| < 15) 300–550 hPa temperature comes out 4–9 K warmer than a reference climate. Fixing both brings it to within 2 K, and most of that comes from the first fix. Both fixes are small. We have them as default-off options on a branch and can open a PR if you want them.

Context: this came up while chasing the cold/warm biases in #1333. The model runs below use that issue's setup (T31 L8, Float32, 40-min step) on `main` + #1332 + #1284 + #1283 + #1262, plus two things of ours that are not upstream: a port of speedy.f90's four-band longwave and speedy.f90's near-surface air temperature. The parcel check in section 1 needs none of that; it runs on plain `main`. Code references are to `main` bf31a2fc; `convection.jl` is unchanged since #1221.

## 1. One explicit step per layer, moist from the bottom of the layer in which the parcel saturates

Below saturation, the parcel takes a dry-adiabatic trial step over the whole layer. If that would saturate it, `saturated` is set, and the layer is then ascended **moist from its bottom**:

```julia
if !saturated
    temp_parcel_dry = temp_parcel * (σ[k] / σ[k + 1])^κ
    sat_humid = saturation_humidity(temp_parcel_dry, σ[k] * pres, atmosphere)
    saturated = humid_parcel >= sat_humid
end
if saturated
    Γ = (1 + A / Tᵥ) / (1 + B / T^2)              # at level k+1
    ΔΦ = geopotential[ij, k] - geopotential[ij, k + 1]
    temp_parcel = temp_parcel - ΔΦ / cₚ * Γ
```

This has two effects:
* In the layer where the parcel reaches its condensation level, it follows the moist lapse rate over the whole layer instead of the dry one up to the condensation level. In a typical tropical column (lowest layer at RH ≈ 78 %) this leaves the parcel ~3 K too warm one layer up, and moist adiabats fan out with height.
* Above that, each step uses the lapse rate at its bottom, i.e. that of the warmest, moistest air. With 8 layers a step spans ~120 hPa and 1.5–3 km, so the parcel cools too little there too.

Stand-alone check, no model run (script below). One tropical column; the parcel starts from the lowest layer at 294.25 K and 12.86 g/kg. It uses `NoEntrainment` and an environment cold enough aloft that the parcel stays buoyant to the top. The comparison is against a fine integration of exactly the same equations (same `Γ` formula, same `saturation_humidity`, dry below saturation), 2000 sub-steps per layer:

| layer | p [hPa] | `pseudo_adiabat!` on main | fine integration | main − fine | 10 sub-steps (dry to the saturating sub-step) − fine |
|---|---|---|---|---|---|
| 7 | 802 | 288.84 K | 285.88 K | +2.96 K | +0.39 K |
| 6 | 679 | 282.98 K | 279.34 K | +3.65 K | +0.48 K |
| 5 | 555 | 275.66 K | 270.83 K | +4.83 K | +0.65 K |
| 4 | 432 | 265.92 K | 258.83 K | +7.09 K | +0.97 K |
| 3 | 309 | 251.71 K | 240.00 K | **+11.70 K** | +1.56 K |
| 2 | 185 | 227.49 K | 208.52 K | **+18.97 K** | +2.09 K |

Sub-stepping only the moist part does not fix it. We tried that first: 10 moist sub-steps from the bottom of the saturating layer gave +3.37 / +9.08 / +11.73 K at 802 / 309 / 185 hPa. The condensation level has to be resolved within the layer.

## 2. Entrainment mixes T and q, then re-saturates without evaporative cooling

With `LinearEntrainment` (the default since #1221), after each saturated step:

```julia
temp_parcel = (1 - ε) * temp_parcel + ε * temp_env
humid_parcel = (1 - ε) * humid_parcel + ε * humid_env
```

At the next level, `humid_parcel` is reset to saturation at the new temperature. When unsaturated environmental air mixes into a saturated parcel, part of the parcel's condensate evaporates to re-saturate the mixture, and that cools it. The scheme carries no condensate, so it skips that step. The q deficit of the mixed parcel is discarded at the next level. Dry air therefore never cools the parcel. In the tropical mid troposphere the environment is close to the parcel's temperature but much drier, so the mixing does almost nothing.

The usual way around this is to mix moist static energy, `h = cₚT + Lᵥq` (same level, so geopotential cancels), and keep the parcel saturated, i.e. solve `cₚT + Lᵥ q⋆(T, p) = h` for `T`. This converges in 2–4 Newton steps:

```julia
h = (1 - ε) * (cₚ * temp_parcel + Lᵥ * humid_parcel) + ε * (cₚ * temp_env + Lᵥ * humid_env)
for _ in 1:4
    qs = saturation_humidity(temp_parcel, σ[k] * pres, atmosphere)
    dqsdT = qs * Lᵥ / (R_vapor * temp_parcel^2)
    temp_parcel -= (cₚ * temp_parcel + Lᵥ * qs - h) / (cₚ + Lᵥ * dqsdT)
end
humid_parcel = saturation_humidity(temp_parcel, σ[k] * pres, atmosphere)
```

On top of the fixed ascent this cools the tropical 308 hPa layer by a further 2.8 K, at the default `σ_entrainment = 0.5` (table below).

## 3. Effect in the model (T31 L8, tropics |lat| < 15)

The reference is GFDL-ESM4 historical r1i1p1f1, 1985–2014 band means interpolated in log p to the model's own layer pressures. It is a model, not observations, but it is a well-evaluated one. Single realisations; prescribed SST = `SeasonalOceanClimatology`, 3 years with years 2–3 scored; slab = default `SlabOcean`, 5 years with years 2–5 scored.

| | T bias 308 / 431 / 555 hPa [K] | column water vapour [kg/m²] (ref 40.3) |
|---|---|---|
| as is (`main` convection), prescribed SST | +9.0 / +6.6 / +4.1 | 50.6 |
| 10 sub-steps, prescribed SST | +1.0 / +2.5 / +2.0 | 42.2 |
| 10 sub-steps + MSE entrainment (default σ_entrainment 0.5), prescribed | **−1.8 / +0.1 / +0.6** | **38.0** |
| 10 sub-steps + MSE entrainment, σ_entrainment = 0, prescribed | −3.8 / −1.9 / −0.3 | 35.4 |
| as is, slab | +12.2 / +8.3 / +5.7 | 59.5 |
| 10 sub-steps + MSE entrainment (σ_entrainment 0.5), slab | +1.8 / +2.7 / +2.1 | 42.4 |

So the sub-stepping with the condensation level placed correctly does most of the work. With MSE entrainment at the default depth the tropical 300–550 hPa profile is within 2 K of the reference, and the column is slightly too dry. Entraining all the way to the top now overshoots (too cold and too dry). The layer at ~185 hPa stays several K too warm in all versions. The slab still drifts warm (+0.35 K/yr in year 5, TOA +2.2 W/m²), which we think is mostly the cloud/radiation side; that is a separate issue.

## Proposed change

Both as options on `BettsMillerConvection`, default off, so `main` results stay bit-identical. We checked this by diffing a full 3-year diagnostic output against the control.

- `ascent_substeps::Int = 1`: sub-steps of the ascent per layer. Each step uses the lapse rate at its start, with pressure log-linear within the layer. A parcel that saturates within the layer rises dry up to the sub-step at which it saturates.
- `entrainment_mse::Bool = false`: entrain by mixing moist static energy and keep the parcel saturated.

<details><summary>diff against main (convection.jl only)</summary>

```diff
diff --git a/SpeedyWeather/src/parameterizations/convection.jl b/SpeedyWeather/src/parameterizations/convection.jl
index 8dd0ec9b..2a54d0d7 100644
--- a/SpeedyWeather/src/parameterizations/convection.jl
+++ b/SpeedyWeather/src/parameterizations/convection.jl
@@ -15,6 +15,12 @@ in their paper. Fields and options are $(TYPEDFIELDS)"""
     "[OPTION] Entrainment profile mixing environmental air into the rising parcel"
     @component entrainment::Entrainment = LinearEntrainment(DEFAULT_NF)
 
+    "[OPTION] Sub-steps of the parcel ascent per layer (1 = one explicit step with the lapse rate of the lower level, and moist over the whole layer in which the parcel saturates; > 1 also places the condensation level to the sub-step)"
+    ascent_substeps::Int = 1
+
+    "[OPTION] Entrain by mixing moist static energy and keep the parcel saturated (true), instead of mixing T and q and resetting q to saturation at the next level without evaporative cooling (false)"
+    entrainment_mse::Bool = false
+
     "[OPTION] Convert convective rain below freezing to snow?"
     snow::Bool = true
 
@@ -78,6 +84,7 @@ and relaxes current vertical profiles to the adjusted references."""
     level_zero_buoyancy = pseudo_adiabat!(
         ij, temp_ref_profile, humid_ref_profile, temp, humid,
         geopotential, pₛ, σ, atmosphere, convection.relative_humidity, convection.entrainment,
+        convection.ascent_substeps, convection.entrainment_mse,
     )
 
     Pq::NF = 0        # precipitation due to drying
@@ -213,6 +220,8 @@ column then need no branch to skip those levels, they contribute zero on their o
         atmosphere,
         relative_humidity,
         entrainment,
+        substeps::Int = 1,
+        entrainment_mse::Bool = false,
     )
     NF = eltype(temp_ref_profile)             # number format
     nlayers = length(σ)                       # number of vertical layers
@@ -241,6 +250,9 @@ column then need no branch to skip those levels, they contribute zero on their o
         humid_env = humid_environment[ij, k]
 
         if buoyant                          # calculate moist adiabat while buoyant till top
+            # with sub-steps, a parcel that saturates within this layer rises dry up to the sub-step at which
+            # it saturates (its condensation level), not moist from the bottom of the layer
+            dry_start = !saturated && substeps > 1
             if !saturated                   # if not saturated yet follow dry adiabat
                 # dry adiabatic ascent and saturation humidity of that temperature
                 temp_parcel_dry = temp_parcel * (σ[k] / σ[k + 1])^κ
@@ -252,18 +264,36 @@ column then need no branch to skip those levels, they contribute zero on their o
             end
 
             if saturated
-                # calculate moist/pseudo adiabatic lapse rate, dT/dΦ = -Γ/cp
-                T, Tᵥ, q = temp_parcel, temp_virt_parcel, humid_parcel  # for brevity
-                A = q * Lᵥ / ((1 - q)^2 * R_dry)
-                B = q * Lᵥ^2 / ((1 - q)^2 * cₚ * R_vapor)
-                Γ = (1 + A / Tᵥ) / (1 + B / T^2)
-
-                ΔΦ = geopotential[ij, k] - geopotential[ij, k + 1]        # vertical gradient in geopotential
-                temp_parcel = temp_parcel - ΔΦ / cₚ * Γ                     # new temperature of parcel at k
-
-                # at new (lower) temperature condensation occurs immediately
-                # new humidity equals to that saturation humidity
-                humid_parcel = saturation_humidity(temp_parcel, σ[k] * pres, atmosphere)
+                # moist/pseudo adiabatic ascent from layer k+1 to k in `substeps` explicit steps of equal
+                # geopotential, each with the lapse rate at its start (substeps = 1: one step with the lapse
+                # rate of the lower level, which under-cools the parcel over thick layers)
+                ΔΦ = (geopotential[ij, k] - geopotential[ij, k + 1]) / substeps   # geopotential step
+                for i in 1:substeps
+                    # sub-step start and end pressure, log-linear between the layers
+                    pₐ = σ[k + 1] * pres * (σ[k] / σ[k + 1])^(NF(i - 1) / substeps)
+                    pᵢ = i == substeps ? σ[k] * pres : σ[k + 1] * pres * (σ[k] / σ[k + 1])^(NF(i) / substeps)
+                    if dry_start                # below the condensation level within this layer: dry adiabat
+                        temp_dry = temp_parcel * (pᵢ / pₐ)^κ
+                        if humid_parcel < saturation_humidity(temp_dry, pᵢ, atmosphere)
+                            temp_parcel = temp_dry
+                            temp_virt_parcel = virtual_temperature(temp_parcel, humid_parcel, atmosphere)
+                            continue
+                        end
+                        dry_start = false       # saturates during this sub-step: moist from its start
+                    end
+                    # calculate moist/pseudo adiabatic lapse rate, dT/dΦ = -Γ/cp
+                    T, Tᵥ, q = temp_parcel, temp_virt_parcel, humid_parcel  # for brevity
+                    A = q * Lᵥ / ((1 - q)^2 * R_dry)
+                    B = q * Lᵥ^2 / ((1 - q)^2 * cₚ * R_vapor)
+                    Γ = (1 + A / Tᵥ) / (1 + B / T^2)
+                    temp_parcel = temp_parcel - ΔΦ / cₚ * Γ                 # new temperature of parcel
+
+                    # at new (lower) temperature condensation occurs immediately
+                    # new humidity equals to that saturation humidity, at the sub-step's end pressure
+                    # (exactly σ[k] * pres at the last sub-step)
+                    humid_parcel = saturation_humidity(temp_parcel, pᵢ, atmosphere)
+                    temp_virt_parcel = virtual_temperature(temp_parcel, humid_parcel, atmosphere)
+                end
                 sat_humid = humid_parcel               # reused below for the reference humidity
 
                 if entraining(entrainment)             # compiled away entirely for NoEntrainment
@@ -271,8 +301,20 @@ column then need no branch to skip those levels, they contribute zero on their o
                     # buoyancy and moisture; sat_humid is recomputed at the mixed temperature so
                     # the reference humidity below stays consistent with the (now mixed) T_ref
                     ε = entrainment(σ[k])
-                    temp_parcel = (1 - ε) * temp_parcel + ε * temp_env
-                    humid_parcel = (1 - ε) * humid_parcel + ε * humid_env
+                    if entrainment_mse
+                        # mix moist static energy cₚT + Lᵥq (same level, geopotential cancels) and keep the
+                        # parcel saturated: solve cₚT + Lᵥ q⋆(T) = h by Newton, so entrained dry air cools it
+                        h = (1 - ε) * (cₚ * temp_parcel + Lᵥ * humid_parcel) + ε * (cₚ * temp_env + Lᵥ * humid_env)
+                        for _ in 1:4
+                            qs = saturation_humidity(temp_parcel, σ[k] * pres, atmosphere)
+                            dqsdT = qs * Lᵥ / (R_vapor * temp_parcel^2)
+                            temp_parcel -= (cₚ * temp_parcel + Lᵥ * qs - h) / (cₚ + Lᵥ * dqsdT)
+                        end
+                        humid_parcel = saturation_humidity(temp_parcel, σ[k] * pres, atmosphere)
+                    else
+                        temp_parcel = (1 - ε) * temp_parcel + ε * temp_env
+                        humid_parcel = (1 - ε) * humid_parcel + ε * humid_env
+                    end
                     sat_humid = saturation_humidity(temp_parcel, σ[k] * pres, atmosphere)
                 end
             else
```
</details>

<details><summary>stand-alone parcel check (script)</summary>

```julia
# Stand-alone check of BettsMillerConvection's parcel ascent (SpeedyWeather `pseudo_adiabat!`, no model run):
# one tropical column at T31 L8 (8 equal σ layers), parcel started from the lowermost layer, NoEntrainment, and an
# environment made cold aloft so the parcel stays buoyant to the top (the reference profile then IS the parcel).
# Compares the parcel temperature per layer with a fine integration of the SAME equations (same lapse-rate formula,
# saturation_humidity, dry adiabat; 2000 sub-steps per layer, pressure log-linear within a layer).
#   julia --project=<env with SpeedyWeather> speedy_parcel_ascent_check.jl
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
```
</details>

Happy to open a PR with tests, or to change the defaults if you prefer. Cost: a 3-year T31 L8 run took 38.6 min with 10 sub-steps vs 36.1 min without (single runs on one core, our diagnostics included).
