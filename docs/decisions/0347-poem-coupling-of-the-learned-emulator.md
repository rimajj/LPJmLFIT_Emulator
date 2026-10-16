# 0347 — The learned emulator coupled to POEM 1.2's atmosphere (inside its LPJmL)

* **Status:** accepted 2026-10-16 (§8 = the corrected runs, appended when they finish).
* **Depends on:** ADR 0341 (global nitrogen-off emulator release `global_emu/release/fold_none`), ADR 0345 (the
  SpeedyWeather coupling and its replay gate), ADR 0346 (SpeedyWeather's land is 6.6 °C too cold — the reason
  for this ADR: owner, 2026-10-16, *"since speedyweahter is too cold, lets now couple the emulator to poem's
  atmosphere model"*).
* **Code:** POEM side `patches/poem/` (build `/p/projects/open/Jamir/poem_landemu/POEM-1.2_20261013_6-layers_landemu`,
  local branch `landemu` in POEM and LPJmL); `scripts/online_coupling/poem_landemu.py` (Python half),
  `score_poem_landemu.py`, `poem/{setup_poem_run.sh,compile_poem_landemu.sh,compare_poem_runs.py}`; skill
  `poem-landemu`.
* **Data:** `/p/projects/open/Jamir/esm_land_emulator_data/coupled/poem/` (`poem_*_10y/`, `gate_*_1m/`,
  `poem_scores.json`).

## 1. POEM and where the emulator goes

POEM 1.2 (unpublished; builds under `/p/projects/poem/data/tuning-1.2/POEM_PROGRAM/`): AM2 physics on the FV
core, 3.75° × 3°, 24 levels, 1-hour step; MOM5 ocean with BLING; LPJmL 5.9 land at 0.5°, 90 881 cells. LPJmL is
a C library called **every hour** (`lpj_climber4.c::lpj_update_`): hourly snow, soil heat, canopy humidity,
evapotranspiration; once a day the vegetation and the river routing to the ocean. Compiled with
`-DUSE_LPJ_FLUX_OVERWRITE`, the coupler hands the atmosphere LPJmL's hourly land evaporation as a prescribed
flux (`flux_exchange.F90`). Calendar 365 days. Preindustrial control: fixed CO2 284.3 ppm, 1850 aerosols and
ozone. Start state: the POEM group's spin-up `spinup_6layers_maxsnowheight-20m` at the end of 1850 (read only).

Unlike SpeedyWeather, POEM's land grid IS the emulator's grid: each LPJmL cell is represented by the emulator
cell at the same 0.5° position (58 436 cells; the 32 445 others — Antarctica, Greenland, other ice and rock —
keep LPJmL's fluxes). No nearest-column approximation.

## 2. The coupling (run-time switch `LANDEMU`)

* The emulator runs in every land MPI rank through an embedded, isolated Python interpreter
  (`landemu_py.c`, the only file including Python.h). Floating-point traps (LPJmL enables `FE_INVALID`) and the
  Intel build's flush-to-zero are switched off around each call and restored, so the emulator computes exactly
  what it computes offline.
* Every hour the day's weather is accumulated: **2-m air temperature and humidity** (new coupler fields
  `t_ref`/`q_ref`, computed always at 2 m — POEM feeds LPJmL its *skin* temperature, and its own 2-m
  diagnostic is computed only when requested), precipitation, downward shortwave, net longwave.
* At the last step of the day the emulator runs that day. Its **runoff replaces LPJmL's in the river routing**
  (so it reaches the ocean; the difference is booked as an external flux in LPJmL's cell water balance, which
  therefore still closes). Its **evapotranspiration becomes the land moisture flux of the whole next day**
  (one-day lag, as ADR 0345), spread over the 24 steps flat or in proportion to the cosine of the solar zenith
  angle (`LANDEMU_DIURNAL=flat|sun`, both exactly the day's total), and the latent heat in LPJmL's surface
  energy balance (`cell->evap1`). Lakes, surface temperature, albedo, roughness, canopy humidity and snow stay
  LPJmL's; LPJmL's own soil water and vegetation keep running underneath (as SpeedyWeather's own land did).
* `LANDEMU=shadow`: the emulator runs and records the same way but hands nothing back — stock POEM plus a full
  record (the control run AND the one-way result in one run). Unset: stock.

## 3. Gates (all passed)

| gate | result |
|---|---|
| POEM reproduces itself (stock vs stock, 1 month) | identical, 1 050 of 1 050 decoded variables in 99 restart / history / LPJmL-output files |
| our build, emulator off, vs stock | identical, 1 050 / 1 050 (on the final binary too) |
| shadow (emulator inside, records only) vs stock | identical, 1 050 / 1 050 |
| coupled vs stock (1 month) | differs in 335 of 1 050 (the coupling acts) |
| offline replay of all 15 ranks' records, 3 runs × 10 years | identical (max difference 0.0 on every daily and yearly output) |
| emulator water balance over 10 years, every cell | closes to 4e-5 mm of ~6 700 mm precipitation |
| LPJmL's own cell water-balance check (yearly) | 0 errors in all runs (stock: 0) |

## 4. Runs (1851–1860, 28 tasks on one node each, one realisation per arm)

`poem_shadow_10y` (control), `poem_coupled_sun_10y`, `poem_coupled_flat_10y` (both with LPJmL's evaporation
derivative set to zero — see §6).

## 5. Results (years 2–10)

**POEM's climate is not cold.** At the 58 436 emulated cells (area weighted, the emulator's own forcing record):

| control minus | 2-m T | warmest month | coldest month | precipitation | downward SW | net LW |
|---|---|---|---|---|---|---|
| GFDL-ESM4 historical **1850–1879** (like-for-like preindustrial) | **+0.04 °C** | +0.98 | −0.16 | −130 mm (−15 %) | +1.6 W/m² | −4.3 W/m² |
| W5E5 observations 1985–2014 | −0.51 °C | +0.59 | −0.99 | −88 mm | +5.9 | −6.2 |

By latitude vs W5E5: tropics −0.13 °C, 23.5–50° −0.51, poleward of 50° −1.09. Compare SpeedyWeather: −6.6 °C
(ADR 0346). POEM's remaining bias is a land that is ~15 % too dry.

**Coupled vs control** (POEM's own monthly output over ALL land, years 2–10; year-to-year sd of the control
0.11 °C, 0.05 mm/day):

| | land 2-m T | land precip | land evap | sunshine | convective precip | global 2-m T |
|---|---|---|---|---|---|---|
| control (shadow) | 9.02 °C | 1.858 mm/d | 1.151 | 191.0 W/m² | 1.414 | 13.59 °C |
| coupled, sun-shaped | 9.12 | 1.896 (+2 %) | 1.204 (+5 %) | 190.8 | 1.443 | 13.63 |
| coupled, flat | **7.90** | **1.476 (−21 %)** | 1.012 (−12 %) | **176.9** | **0.994 (−30 %)** | 13.12 |

Emulator at its cells (PgC/yr; 1000 km³/yr):

| | GPP | NPP | ET | runoff | precip | veg. carbon 1851 → 1860 | LPJmL's own ET / runoff, same weather |
|---|---|---|---|---|---|---|---|
| control (one-way) | 143.3 | 60.5 | 59.0 | 37.2 | 96.4 | 845 → 810 (−4.1 %) | 54.9 / 41.3 |
| coupled, sun | 147.6 | 63.0 | 60.5 | 37.7 | 98.3 | 847 → 818 (−3.4 %) | 58.6 / 39.6 |
| coupled, flat | 125.0 | 53.4 | 51.4 | 23.9 | 75.4 | 841 → 778 (−7.5 %) | 50.6 / 24.8 |

1. **With sun-shaped hours the coupling is benign**: land 0.1 °C warmer (inside 1 sd of a year), 5 % more
   land evaporation (the emulator, trained on LPJmL-FIT, evaporates 8 % more than POEM's standard LPJmL 5.9
   under the same weather: 59.0 vs 54.9), 2 % more land rain.
2. **Spreading the day's evaporation evenly over day and night changes the climate**: nights 2.2 °C colder
   (monthly-mean daily minimum −2.65 vs −0.49 °C; daily maximum unchanged), land convective rain −30 % (tropics
   −34 %), sunshine −14 W/m², 21 % less land rain, the land 1.1 °C and the globe 0.5 °C colder by year 10, the
   ocean beginning to cool. [ASSUMPTION — not tested by a dedicated run] the mechanism is the timing: half the
   evaporative cooling at night, half the moisture missing when daytime convection starts. **The hour shape is
   therefore not a detail in an hourly atmosphere; `sun` is the right default, and a coupled emulator should
   eventually provide its own diurnal cycle.**
3. **Vegetation carbon falls in every run, the one-way control included** (−4 % per decade). The emulator's
   climate window starts filled with GFDL-ESM4 1985–2014, and POEM's preindustrial climate is 15 % drier and
   ~0.5 °C colder; the emulator reads that as climate change. Not a coupling effect (it is there one-way).

**Speed.** Wall time per simulated year (rank 10, year 1): control 1 409 s, coupled-sun 1 399 s, coupled-flat
1 423 s, of which the emulator 30–40 s (2–3 %, including writing its full daily record). The POEM group's own
50-year stock run: 1 322 s per year, of which atmosphere 57 %, the whole land 28 % (LPJmL's hourly step 21 %,
its regridding 3 %), the land–ice–atmosphere coupler 13 %. **The coupling is not faster than POEM with LPJmL:
LPJmL still runs.** Replacing LPJmL entirely could save at most ~25 % of POEM's time (≈1.3× faster), and only
if its hourly surface physics were replaced too — the emulator has no hourly energy balance.

## 6. Defect found and fixed: single-hour surface overheating

Both coupled runs logged LPJmL surface temperatures above 80 °C (POEM's clamp) — 29 999 (sun) and 23 442 (flat)
cell-hours in 10 years, ~6 per million, in the tropics and subtropics (19 °S – 35 °N), from year 2 on and
growing; the control and the POEM group's 50-year run: 0. Monthly means are unaffected (no cell drifts), so the
§5 climate numbers stand, but it is unphysical. The emulator's evaporation is never negative (0–8 mm/day), so
it is not latent heating. Cause (by elimination, confirmed or not in §8): the coupling set LPJmL's derivative of
evaporation with respect to surface temperature (`cell->dedt`) to zero, because the handed-over flux no longer
responds to temperature — which removed the damping LPJmL's hourly implicit surface-temperature step relies on.
Fix: keep LPJmL's derivative in that step (`LANDEMU_DEDT=lpj`, now the default; `zero` reproduces §4–5). It
only shapes how the step converges; the energy balance itself still uses the emulator's latent heat.

## 7. Limits

1. One realisation per arm, 10 years, preindustrial; no second POEM member to measure internal variability
   beyond the control's year-to-year spread.
2. Only the water channel is coupled. Surface temperature, albedo and roughness are LPJmL's; LPJmL's own soil
   water and vegetation keep running (and cost what they cost).
3. The emulator is the nitrogen-off release (no CO2 input); POEM's preindustrial CO2 is not seen, which is
   faithful to that model (ADR 0004/0107).
4. The emulator's climate memory starts in 1985–2014 GFDL-ESM4, not POEM's climate (§5.3). Anchoring it on a
   POEM spin-up, or spinning it up in shadow mode first, is the clean start.
5. 2-m humidity over land is interpolated towards LPJmL's canopy-air humidity (the coupler's surface value).

## 8. The corrected runs (LANDEMU_DEDT=lpj) — appended on completion
