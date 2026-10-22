# At 8 layers the clear-sky OLR is 6–9 W/m² lower than at 32 layers for the same atmosphere; the L8 slab drifts warm

(SpeedyWeather/SpeedyWeather.jl#1345, filed 2026-10-22 as rimajj)

**Summary.** At 8 layers, the clear-sky OLR is 6 W/m² lower globally (9 W/m² in the tropics) than at 32 layers for the same atmosphere. We find this with a correct radiation code (ecCKD, NumericalRadiation extension), so it is a property of the vertical discretisation, not of a particular longwave scheme. It adds a greenhouse effect of a few W/m² that no cloud or gas tuning can remove honestly. With a radiation and convection setup that otherwise gets the tropical temperature profile right, the L8 slab ocean keeps warming by ~0.35 K/yr in year 5. Reported as a measurement. We have no fix to propose beyond more layers, which currently run into #793 / #956, or an explicit correction.

Context: #1333, #1339, and #1344 (clear-sky shortwave). Setup: T31, `main` d6e3286d + #1332 + #1284 + #1283 + #1262, with our port of speedy.f90's four-band longwave (#1342) and the #1339 convection options (`ascent_substeps = 10, entrainment_mse = true`).

## 1. Same atmosphere, 8 vs 32 layers

GFDL-ESM4 historical 1985–2014 band-mean temperature and humidity profiles (by |lat| band) are interpolated in log p to each column's layer pressures. The host is spun up for one day only, and its surface temperatures are kept. Clear-sky OLR, W/m²:

| | global | |lat| < 15 | 15–30 | 30–60 | ≥ 60 |
|---|---|---|---|---|---|
| ecCKD, L8 | 249.2 | 269.2 | 272.2 | 239.9 | 197.6 |
| ecCKD, L32 | 255.2 | 278.5 | 280.7 | 243.5 | 199.4 |
| four-band, L8 | 253.6 | 275.0 | 277.9 | 243.2 | 199.7 |
| four-band, L32 | 261.7 | 286.9 | 288.2 | 248.9 | 203.3 |

At L8, the tropopause region is two thick layers (σ 0.125–0.25 and 0.25–0.375). The emission from the cold upper troposphere is then misplaced. Both codes lose 6–8 W/m² globally and 9–12 W/m² in the tropics against 32 layers. The four-band scheme at L8 happens to sit within 2 W/m² of ecCKD at L32, i.e. its speedy.f90 tuning compensates for the coarse layers.

None of these reach CERES' clear-sky 268.1 W/m² (EBAF Ed4.0, 2005–2015). The rest is probably the reference comparison: band-mean profiles lose the humidity variance of dry subsidence regions, and CERES clear-sky samples cloud-free, drier scenes.

## 2. What it is not

After a 120-day spin-up, we replaced the model's own T and/or q with the GFDL-ESM4 profiles at L8. Clear-sky OLR, global:

| state | four-band | ecCKD |
|---|---|---|
| model T, model q | 255.7 | 250.6 |
| GFDL T, model q | 255.4 | 250.3 |
| model T, GFDL q | 258.7 | 253.4 |
| GFDL T, GFDL q | 257.9 | 252.9 |

The model's own state costs only ~3 W/m² (its upper troposphere is somewhat too moist: 300 hPa RH ~73 % in the tropics vs ~40 % in GFDL-ESM4). The longwave code is not the cause either: at L8 the four-band scheme is 4–5 W/m² *above* ecCKD, i.e. on the side of more emission.

## 3. Consequence on a slab ocean (L8, default 50 m `SlabOcean`, 5 years)

| year | global air [°C] | reflected SW | OLR | net TOA [W/m²] |
|---|---|---|---|---|
| 1 | 16.53 | 108.7 | 225.9 | +6.6 |
| 2 | 16.56 | 113.2 | 224.5 | +3.5 |
| 3 | 16.94 | 113.2 | 225.3 | +2.8 |
| 4 | 17.27 | 112.9 | 225.7 | +2.6 |
| 5 | 17.64 | 112.3 | 226.7 | +2.2 |

The total reflection (112 W/m², CERES 99) is already high, and the clear-sky OLR (257.7, CERES 268.1) is low. So the clouds compensate for the missing clear-sky emission, and the TOA cannot be balanced within the shortwave (#1344).

Things that would help us interpret this: are L16/L32 climate runs with the wet model expected to be stable now (#793, #956)? And would an explicit clear-sky OLR correction for coarse vertical resolution be acceptable, or is the preferred route more layers? Single realisations throughout. The column-swap script (`speedy_clearsky_olr_attribution.jl`, needs NumericalRadiation) is available if useful.
