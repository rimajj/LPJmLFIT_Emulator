(comment on SpeedyWeather/SpeedyWeather.jl#1333, 2026-10-22, https://github.com/SpeedyWeather/SpeedyWeather.jl/issues/1333#issuecomment-6340715250)

Follow-up: what the open PRs do to this bias, stacked one at a time on `main` d6e3286d, plus three changes of ours. This may help with deciding the merge order. Same setup as above (default `PrimitiveWetModel`, T31 L8, Float32, 40-min step). Single realisations.
- **Prescribed SST:** 3 years, years 2–3 scored.
- **Slab ocean:** default 50 m `SlabOcean`, 5 years, years 2–5 scored.
- **Land:** model − W5E5 observations 1985–2014 at the 1 197 T31 land columns, cos-latitude × land-fraction weights.

| stage | TOA net, prescribed [W/m²] | ocean air − SST, tropics / ≥ 50° [K] | land annual / warmest / coldest month [K] | land precip [mm/yr] | slab: global air [°C] / TOA net in year 5 [W/m²] |
|---|---|---|---|---|---|
| `main` | −26.0 | −4.8 / −3.4 | −2.2 / −4.1 / +0.8 | −31 | 5.3 / −5.1 (still cooling) |
| + #1332 + #1284 | −26.4 | −4.5 / −3.4 | −2.0 / −3.5 / +1.1 | −30 | |
| + #1283 | −39.1 | −2.6 / −1.9 | 0.0 / −2.0 / +3.3 | +7 | 3.7 / −5.9 (still cooling) |
| + #1262 | −48.9 | −3.7 / −2.4 | −1.0 / −3.5 / +2.5 | +8 | 3.2 / −5.3 (still cooling) |
| + #1279's provisional tuning | −23.7 | −0.6 / −0.3 | +2.6 / +1.1 / +5.7 | −118 | 10.1 / −3.8 (still cooling) |
| #1262 stage + four-band longwave (new issue, instead of the tuning) | +4.6 | +0.1 / +2.7 | +3.7 / +2.6 / +6.0 | −173 | 18.3 / +0.8 (steady) |
| + speedy.f90 surface air temperature (new issue) | +6.3 | −2.6 / +1.0 | +2.1 / +1.4 / +4.0 | −182 | |
| + #1339 convection options | +5.8 | −2.2 / +1.2 | +2.2 / +2.3 / +3.5 | −4 | 17.1 / +2.2 (+0.35 K/yr) |

The rows are cumulative; the four-band row builds on the #1262 stage, not on #1279's tuning.

Reading:
- **#1283 and #1262 widen the TOA deficit** with the grey longwave. #1279's tuning narrows it, but every grey-longwave stage still cools on a slab ocean.
- **The longwave was the main cause.** Replacing the grey longwave by a port of speedy.f90's four-band longwave closes the budget and gives a steady slab climate. With `main`'s convection it is too warm, and the tropical upper troposphere 4–9 K too warm (#1339).
- **With the #1339 convection options,** the tropical 300–550 hPa profile is within ~2 K of GFDL-ESM4 and land precipitation is close to observed.
- **What remains:**
  - High-latitude land is too warm in winter. Most of that is the definition of the near-surface air temperature in an inversion.
  - The slab drifts warm at +0.35 K/yr. Part of that is the clear-sky OLR at 8 layers.
  - The clouds compensate for missing clear-sky shortwave scattering.

  Each now has its own issue: #1342 (four-band longwave), #1343 (near-surface air temperature in inversions), #1344 (clear-sky shortwave scattering), #1345 (clear-sky OLR at 8 layers).
