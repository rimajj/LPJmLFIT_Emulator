# TwoBandShortwave has no clear-sky (Rayleigh) scattering; clouds reflect ~33 W/m² too much to compensate

(SpeedyWeather/SpeedyWeather.jl#1344, filed 2026-10-22 as rimajj)

**Summary.** SpeedyWeather's shortwave has no clear-sky scattering: no Rayleigh scattering by air, and no aerosol. With the speedy.f90 two-band shortwave of #1262, the clear sky reflects ~33 W/m² against CERES' 53. The total reflection is about right only because the clouds reflect ~33 W/m² too much (the cloud albedo of 0.43/0.5 inherited from SPEEDY was presumably tuned to cover the missing clear-sky part). One visible effect is too much sunshine at the land surface, mostly in the mid-latitudes. We added an opt-in Rayleigh reflectance and tested it together with lower cloud albedos. The shortwave split can be made realistic, but no setting we tried also keeps the energy budget closed. The reason is on the longwave side (clear-sky OLR at 8 layers, #1345). So we propose the option but no default change.

Context: #1333 and #1262. Setup: T31 L8, `main` d6e3286d + #1332 + #1284 + #1283 + #1262, with our four-band longwave port (#1342) and the #1339 convection options (`ascent_substeps = 10, entrainment_mse = true`). Prescribed seasonal SST, 3 years, years 2–3 scored, single realisations. Clear-sky fluxes are recomputed on a copy of the state every 7th step. The reference is CERES EBAF Ed4.0, Jul 2005–Jun 2015 global means (Loeb et al. 2018, J. Climate 31, Table 5). CERES clear-sky is for cloud-free scenes, while the model's is the same column with clouds removed, so a few W/m² of the difference are definition.

## Results (global, W/m²)

| | reflected SW | clear-sky reflected | SW cloud effect | OLR | clear-sky OLR | LW cloud effect | net TOA |
|---|---|---|---|---|---|---|---|
| CERES EBAF | 99.1 | 53.3 | −45.8 | 240.1 | 268.1 | 27.9 | +0.7 |
| base (no Rayleigh) | 111.8 | **33.3** | **−78.5** | 223.2 | 253.8 | 30.5 | +5.8 |
| R1: Rayleigh 0.647 | 133.0 | 62.2 | −70.8 | 221.1 | 251.7 | 30.6 | −13.1 |
| R2: R1 + cloud albedos × 0.6 | 103.4 | 61.6 | −41.9 | 224.0 | 254.3 | 30.3 | +13.4 |
| R3: R1 + cloud albedos × 0.75 | 114.6 | 61.8 | −52.8 | 222.7 | 253.3 | 30.6 | +3.5 |
| R4: Rayleigh 0.32 + cloud albedos × 0.7 | 98.7 | 47.2 | −51.5 | 224.5 | 254.7 | 30.2 | +17.6 |
| R5: Rayleigh 0.5 + cloud albedos × 0.75 | 109.3 | 55.2 | −54.0 | 223.3 | 253.9 | 30.5 | +8.4 |

"Cloud albedos" means both the cloud albedo and the stratocumulus albedo of `DiagnosticClouds`.

Surface shortwave down over land vs W5E5 observations, all land / 23.5–50° / > 50° (W/m²):

| | all land | 23.5–50° | > 50° |
|---|---|---|---|
| base | +8.8 | +18.9 | +12.6 |
| R1 | −11.0 | −5.5 | −3.0 |
| R2 | +16.1 | +17.6 | +21.1 |
| R3 | +6.4 | +9.2 | +12.4 |
| R4 | +20.7 | +24.9 | +25.2 |
| R5 | +11.5 | +14.7 | +16.2 |

Reading:
- **The split can be fixed.** R5 brings clear-sky reflection within 2 W/m² of CERES and the SW cloud effect within 8. The base is off by 20 and 33.
- **The budget cannot be closed this way.** The clear-sky OLR is ~14 W/m² below CERES in every arm. So reducing the total reflection lets in more energy than the model can emit: R5 is at +8.4 W/m² against the base's +5.8. On a slab ocean, R5 warms ~1 K more than the base within 5 years (year 5: +3.5 vs +2.2 W/m² net TOA). R3 has the best land sunshine, but its clear-sky reflection is 8.5 W/m² too high.
- **Drying the convection is not the lever.** A drier convective target (Betts–Miller `relative_humidity` 0.7 → 0.6) raises the clear-sky OLR by only 0.9 W/m², and the 300 hPa relative humidity stays at ~72 %.

## Proposed change

An opt-in clear-sky backscatter in `TwoBandShortwaveRadiativeTransfer`, default 0 (bit-identical). It uses the Lacis & Hansen (1974) Rayleigh reflectance of the visible beam, `R(μ) = a / (1 + b μ)` with a = 0.219, b = 0.816, applied at the top of the atmosphere before the clouds:

```diff
 @parameterized @kwdef struct TwoBandShortwaveRadiativeTransfer{NF} <: AbstractShortwaveRadiativeTransfer
     "[OPTION] Fraction of incoming solar radiation in the near-infrared band (SPEEDY fband2) [1]"
     @param near_infrared_fraction::NF = 0.05 (bounds = 0 .. 1,)
+
+    "[OPTION] Fraction of incoming solar radiation subject to clear-sky (Rayleigh) backscatter at the top of the atmosphere, 0 = off (Lacis and Hansen, 1974: 0.647) [1]"
+    @param rayleigh_fraction::NF = 0 (bounds = 0 .. 1,)
+
+    "[OPTION] Rayleigh reflectance R(μ) = rayleigh_a / (1 + rayleigh_b μ) with μ the cosine of the solar zenith angle, coefficient a (Lacis and Hansen, 1974) [1]"
+    @param rayleigh_a::NF = 0.219 (bounds = 0 .. 1,)
+
+    "[OPTION] Rayleigh reflectance coefficient b, see `rayleigh_a` [1]"
+    @param rayleigh_b::NF = 0.816 (bounds = Nonnegative,)
 end
 ...
     D_nir = radiation.near_infrared_fraction * D_toa
     D = D_toa - D_nir
 
+    # clear-sky (Rayleigh) backscatter of the visible band, applied at the top of the atmosphere
+    # (Lacis and Hansen, 1974); zero with the default rayleigh_fraction = 0
+    U_rayleigh = D_toa * radiation.rayleigh_fraction * radiation.rayleigh_a / (1 + radiation.rayleigh_b * cos_zenith)
+    D -= U_rayleigh
+
 ...
-    vars.parameterizations.outgoing_shortwave[ij] = U
+    vars.parameterizations.outgoing_shortwave[ij] = U + U_rayleigh
```

Applying all of it at the top is a simplification: real Rayleigh scattering is spread over the column and interacts with the clouds below it. The full Lacis–Hansen strength (0.647) overshoots the clear-sky reflection by 9 W/m² here, probably partly because of that. A fraction around 0.5 gives the CERES clear-sky value.

The option should probably be considered together with the clear-sky OLR shortfall (#1345). Turning it on alone, with lower cloud albedos, warms the model. We can open a PR for the option if useful.
