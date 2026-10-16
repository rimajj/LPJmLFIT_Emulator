# 0346 — SpeedyWeather's cold land, explained; albedo and roughness channels added to the coupling

* **Status:** accepted 2026-10-16.
* **Depends on:** ADR 0345 (the day-by-day coupling of the learned emulator to SpeedyWeather 0.23; corrected in §5).
* **Code:** `scripts/online_coupling/run_speedy_landemu.jl` (switches `OCEAN`, `ALBEDO`, `ROUGH`, `Z0_*`; new
  components `EmulatorLandAlbedo`, `EmulatorSurfaceRoughness`; climate diagnostics in every run),
  `landemu_coupler.py` (`Coupler.surface()`), `diagnose_speedy_climate.py` (new), `sbatch_speedy_landemu.sh`.
* **Data:** `/p/projects/open/Jamir/esm_land_emulator_data/coupled/speedy_t31_*_10y/` (7 new runs) and
  `climate_diagnosis.json` beside them.

## 1. Question

ADR 0345 found SpeedyWeather's land 6.7 °C colder than GFDL-ESM4 1985–2014 and showed with a control run that the
coupling does not cause it. It did not say why, nor whether GFDL-ESM4 or SpeedyWeather is the odd one out. The owner
asked for the explanation and for more coupled channels.

## 2. Experiment (T31 L8, 2015–2024, one core each, one realisation per arm)

| run | ocean | land → atmosphere |
|---|---|---|
| control | free 50 m slab (SpeedyWeather 0.23 default) | SpeedyWeather's own land |
| control, prescribed SST | SpeedyWeather's seasonal SST climatology (sea ice follows it) | SpeedyWeather's own land |
| coupled | slab | emulator evapotranspiration (ADR 0345) |
| + albedo | slab | + land albedo from the emulator's tree cover, grass cover and snow |
| + roughness | slab | + land roughness length from the emulator's tree / grass / bare cover |
| + both | slab | both channels |
| + both, prescribed SST | prescribed SST | both channels |

Scored over the 1 197 emulated land columns, cos-latitude × land-fraction weighted, years 2–10, against three
references computed the same way from daily weather at the same 0.5° cells: GSWP3-W5E5 observations 1985–2014,
GFDL-ESM4 historical 1985–2014, GFDL-ESM4 ssp370 2015–2024 (`diagnose_speedy_climate.py`).

**Channels (design).** *Albedo:* SpeedyWeather's own `LandSnowAlbedo` formula (bare 0.4, high vegetation 0.15, low
0.2, + 0.4 × snow cover, snow cover = S/(S + 0.05 m)), with SpeedyWeather's vegetation climatology replaced by the
emulator's tree cover (sum of plant types 1–7 of the stand map) and grass cover (types 8–10), updated yearly, and
SpeedyWeather's snow by the emulator's snow water equivalent, updated daily — same formula, the emulator's land state.
*Roughness:* z₀ = exp(Σ f·ln z₀ᵢ) over tree / grass / bare fractions with z₀ = 2.0 / 0.2 / 0.013 m (typical
per-type values of weather-model land schemes; SpeedyWeather's default is 0.5 m on all land). Both channels are on
from the first step (the start stand and snow are known). Gate: the offline replay of the recorded weather must
still reproduce the coupled emulator exactly.

## 3. Results — why SpeedyWeather's land is cold

| years 2–10 | land air T | warmest month | coldest month | precip | downward SW | net LW |
|---|---|---|---|---|---|---|
| **W5E5 observations 1985–2014** | 17.11 °C | 24.97 | 8.30 | 941 mm | 203.0 W/m² | −69.2 W/m² |
| GFDL-ESM4 hist 1985–2014 | 17.12 | 25.10 | 8.18 | 922 | 202.6 | −68.9 |
| control (slab) − obs | **−6.60** | −8.80 | −3.53 | −225 | **+8.1** | **−18.0** |
| control, prescribed SST − obs | **−8.21** | −10.84 | −4.35 | −192 | **+14.6** | **−28.4** |

1. **GFDL-ESM4 is not the odd one out.** At these cells it equals the observations to 0.01 °C (it is ISIMIP3b,
   bias-adjusted to W5E5). SpeedyWeather is ~6.6 °C colder than the real climate, coldest in summer (−8.8 °C).
2. **Mountains explain nothing.** SpeedyWeather's T31 orography under the emulated columns is on average 57 m
   *below* the real cell elevation (mean absolute difference 267 m): +0.4 °C at 6.5 K/km, the wrong sign.
3. **The ocean is not the cause.** The free slab ocean drifts *warm* (global mean SST 20.4 °C climatology →
   22.5–23.5 °C in years 2–10), while sea ice grows from 3.1 % to 5.5–5.8 % of the ocean (no ocean heat transport:
   warm tropics, cold poles). Prescribing the observed SST makes the land **colder**, −6.6 → −8.2 °C. By latitude
   (slab → prescribed): tropics −6.6 → −11.4 °C, 23.5–50° −4.9 → −6.4 °C, poleward of 50° −10.8 → −3.7 °C — the
   free ocean's cold poles explain the high-latitude part of the bias, and its warm drift *hides* part of a larger
   tropical one.
4. **Radiation is where it shows.** The land gets 8–15 W/m² *more* sunshine than observed and still loses 18–28
   W/m² *more* net longwave. In the source (SpeedyWeather 0.23 defaults): the longwave scheme is the grey scheme of
   Frierson et al. (2006) whose atmospheric optical depth is a **fixed function of latitude only** (6 at the equator
   → 1.5 at the poles) — it sees neither the model's water vapour, nor its clouds, nor CO2 — while clouds act only on
   the shortwave. So clouds cool the land by shading it but never warm it by sending longwave back down.
5. **The cold is in the air, not the ground.** SpeedyWeather's top soil layer averages 19.8 °C over these columns
   (close to the observed *air* temperature), 9.3 °C warmer than its own near-surface air (10.5 °C), with a 37 W/m²
   sensible heat flux from land to air. SpeedyWeather's "surface air temperature" is its lowest model layer brought
   down along the dry adiabat (`SurfaceCondition`), so this is the lowest atmospheric layer being too cold.
   [ASSUMPTION — not tested by a run] the lowest layer is over-cooled by the latitude-only longwave scheme; proving
   it needs an arm with a different longwave scheme or optical depth, which is tuning SpeedyWeather (§6).

## 4. Results — the extra channels (years 2–10, vs the moisture-only coupling)

| | land air T | land albedo | absorbed SW | sensible heat | ET | GPP (emulator) |
|---|---|---|---|---|---|---|
| coupled (moisture only) | 10.57 °C | 0.26 | 158.7 W/m² | 36.8 W/m² | 601 mm | 154.8 PgC/yr |
| + albedo | 10.51 | 0.24 | 161.7 | 38.3 | 591 | 156.1 |
| + roughness | 10.56 | 0.26 | 158.9 | 35.8 | 595 | 153.2 |
| + both | 10.65 | 0.24 | 162.3 | 37.9 | 586 | 155.1 |
| + both, prescribed SST | 9.42 | 0.24 | 167.8 | 31.4 | 608 | 155.7 |

* **Correct:** in all five coupled runs the offline replay reproduces every daily and yearly emulator output with
  zero difference, and water closes to the leap days (+0.079 … +0.082 %, expected 0.082 %).
* **Small:** the emulator's land is darker than SpeedyWeather's climatology (albedo 0.24 vs 0.26, +3 W/m² absorbed),
  but land air temperature moves by −0.06 … +0.08 °C, inside the year-to-year spread of one run (0.09–0.19 °C) —
  single 10-year realisations cannot resolve it. Emulator GPP moves ≤ 1 %. **Neither channel touches the cold bias.**
* **Prescribed SST:** the coupled land is then 1.2 °C colder still (9.42 °C, −7.7 °C vs observations), but the
  emulator's vegetation carbon is stable (831 → 831 PgC over the 10 years) where it falls on the slab ocean
  (832 → 818–820).
* **Cost:** 118–140 core-s per simulated year for every arm (node-to-node noise); the channels add nothing measurable.

## 5. Correction to ADR 0345

ADR 0345 §3 compares the coupled emulator with "the same emulator offline on GFDL-ESM4 ssp370, same 1 197 cells and
weights": GPP 154.6 vs 143.2, NPP 80.4 vs 60.8, vegetation carbon 820 vs 876 PgC. **These offline numbers do not
reproduce from the committed scorer**: `score_speedy_landemu.py::offline_totals` sums the emulator over the whole
0.5° grid (every cell of the global run, not the 1 197 cells), and gives GPP 174.1 PgC/yr and vegetation carbon
1 005 → 1 020 PgC, on both ADR 0345's own run and the rerun. The coupled and offline totals are therefore over
different land areas, and the ×1.08 / ×1.32 / ×0.94 ratios should not be quoted. The coupled totals themselves
(GPP 154.6, vegetation carbon 832 → 819 PgC) do reproduce.

## 6. Limits and what this does not do

1. The cold bias is **not fixed**. Options, owner to choose: (a) feed the emulator bias-corrected weather
   (observed climatology + SpeedyWeather's anomaly), the usual cure; (b) test SpeedyWeather's longwave (optical
   depth or another scheme) — this is tuning the atmosphere, not the land; (c) a different atmosphere.
2. Roughness constants are per-type literature-style values, not derived from the emulator's leaf area or height.
3. SpeedyWeather's albedo formula adds snow albedo on top of forest albedo (snowy forest 0.55; real ≈ 0.2–0.3,
   canopy masking) — inherited unchanged so the channel isolates the land state, not the formula.
4. Each column takes the cover of its nearest tree-bearing 0.5° cell, so cover is biased towards trees relative to
   the 3.75° column.
5. SpeedyWeather's own snow model keeps running for snow insulation and melt cooling; only the albedo uses the
   emulator's snow. Runoff is still not routed; the emulator's soil water is not passed (in SpeedyWeather it only
   sets the land heat capacity).
6. One 10-year realisation per arm; T31 only.
