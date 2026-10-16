# 0345 — Two-way coupling of the learned emulator to SpeedyWeather (first version)

* **Status:** accepted 2026-10-16.
* **Depends on:** ADR 0341 (the global nitrogen-off emulator, `global_emu/release/fold_none`, own 1985–2014
  anchors; its historical run's end-of-2014 state), ADR 0340 (the release package), ADR 0004/0107 (no CO2 input for
  the nitrogen-off model — unchanged: SpeedyWeather's CO2 is never passed).
* **Code:** `python/src/lpjmlfit_emulator/landemu/emulator.py` (`begin_year` / `step_day` / `end_year`),
  `scripts/online_coupling/{run_speedy_landemu.jl, landemu_coupler.py, score_speedy_landemu.py,
  sbatch_speedy_landemu.sh}`; test `python/tests/test_landemu.py::test_day_by_day_equals_step_year`.
* **Environment:** `/p/tmp/jamirp/esm_online_coupling_sw023` (SpeedyWeather 0.23.0 + PythonCall, Julia 1.10.10;
  PythonCall uses conda `py311_new` with `JULIA_CONDAPKG_BACKEND=Null`). Skill `online-coupling-env`.
* **Data:** `/p/projects/open/Jamir/esm_land_emulator_data/coupled/speedy_t31_{coupled,coupled_sun,control}_10y/`.

## 1. Decision

The emulator is coupled to SpeedyWeather **day by day**, directly (not through Terrarium: Terrarium is a 300-s
process-model socket, the emulator is a daily model):

* **Package:** `LandEmulator.step_year` is now `begin_year` + 365 × `step_day` + `end_year`. An atmosphere calls
  `step_day(state, f)` with one day's weather (N, 5) and gets that day's fluxes and stores back; `end_year` runs the
  yearly climate statistics and the structure / stand maps. Gate: the refactored package reproduces the old one
  **bit for bit** (1 046 global cells × 2 years, all 54 outputs) and a unit test pins day-by-day == yearly.
* **Atmosphere → land:** every 40-min step the coupler sums, per land column, surface air temperature, rain + snow
  rate, downward shortwave, net longwave (down − land up; the emulator's `lwnet` is net downward, negative), and
  lowest-level specific humidity. At each midnight the day's means go to the emulator. 29 February is folded into
  28 February (the emulator runs 365-day years).
* **Land → atmosphere:** the day's evapotranspiration (interception + transpiration + soil evaporation) becomes the
  land surface humidity flux of the following day — a new SpeedyWeather component `EmulatorLandHumidityFlux`
  (prescribed flux where a column is emulated, SpeedyWeather's own bulk formula elsewhere). SpeedyWeather's land
  energy balance (`LandBucketTemperature`) takes its latent-heat cooling from the same flux, so water and energy are
  consistent. `DIURNAL=flat` holds it constant, `DIURNAL=sun` spreads it over the day ∝ max(cos zenith, 0); both hand
  over exactly the day's total. Day 1 runs on SpeedyWeather's own formula (no emulator day yet).
* **Columns:** each SpeedyWeather land column (land fraction > 0) is represented by the **nearest** 0.5° emulator
  cell within 3°; at T31, 1 197 of 1 363 land columns (the rest: Antarctica, ice, small islands keep SpeedyWeather's
  own evaporation). Start 2015-01-01 from the global historical run's own end-of-2014 state (stores, stand), the
  1985–2014 GFDL-ESM4 yearly climate in the 30-year window, the 2014 GFDL-ESM4 weather as the daily model's
  trailing year.
* **Language bridge:** the released Python package through PythonCall, one call per simulated day — no port, so no
  second implementation to keep equal.

## 2. Experiment (T31 L8, 2015–2024, one core each, `priority` partition)

Three 10-year runs: coupled `flat`, coupled `sun`, and a **control** (SpeedyWeather's own land evaporation, the
same diagnostics recorded). Scorer `score_speedy_landemu.py`.

## 3. Results

**Correctness.**
* Replay gate: the recorded weather run offline through `step_year` reproduces every daily and yearly output of the
  coupled emulator with **zero** difference (27 outputs × 10 years, both coupled runs) — the coupled emulator is the
  released one.
* Water: the atmosphere received **+0.081 %** of what the emulator produced; expected 3 leap days / 3 650 = 0.082 %
  (each 29 February repeats the previous day's flux). The one-year run without a leap day closes to −7e-5, which is
  the last day's 1-of-36-steps end effect.

**SpeedyWeather's land climate is far from the climate the emulator was built on.** Over the emulated columns
(area × land-fraction weighted) SpeedyWeather is **6.7 °C colder** than GFDL-ESM4 1985–2014 (10.5 vs 17.1 °C) and
**10 % drier** (mean absolute precipitation difference 56 %); at single columns it is 6–12 °C colder in summer (the
Amazon column 16.8 vs 27.1 °C). **This is SpeedyWeather's own climate, not the coupling:** the control run's land is
10.50 °C, the coupled runs' 10.55 / 10.52 °C (year-to-year spread ±0.3 °C).

**What the coupling changes in the atmosphere (years 2–10, coupled flat vs control).**

| | control | coupled flat | coupled sun |
|---|---|---|---|
| land evapotranspiration, mm/yr | 409 (still rising 357 → 416) | 601 (flat from year 2) | 587 |
| land precipitation, mm/yr | 716 | 828 | 814 |
| land air temperature, °C | 10.50 | 10.55 | 10.52 |

More land evaporation (+47 %) recycles into more land rain (+16 %); annual temperature unchanged; June about +1 °C
and January −0.7 °C (9 years per run — tentative). Spreading the flux with the sun changes almost nothing at
monthly scale.

**What SpeedyWeather's weather does to the land (same 1 197 cells and weights; offline = the same emulator on
GFDL-ESM4 ssp370 weather, ADR 0341).** GPP 154.6 vs 143.2 PgC/yr (×1.08), NPP 80.4 vs 60.8 (×1.32: colder ⇒ less
respiration), transpiration ×0.98, interception ×1.01, soil evaporation ×1.90, runoff ×0.57, vegetation carbon
820 vs 876 PgC (×0.94, falling: the yearly maps read the 7 °C colder window as climate change, and at year 10 only
a third of the 30-year window is SpeedyWeather years — the decline will continue). Leaf area 2.00 vs 2.07.

**Cost.** The emulator takes **8.8 s per simulated year** for 1 197 columns = 7.3e-3 core-s per column-year (the
offline figure), ~7 % of the coupled run. Whole runs: coupled 1 149 / 1 231 s for 10 years, control 1 334 s on a node
of the same type — the coupling adds nothing measurable beyond the emulator's own cost (node-to-node noise is larger
than the difference; no claim that coupled is faster).

## 4. Limits (what this version does not do)

1. **Climate bias enters the emulator as a climate signal.** SpeedyWeather's land is ~7 °C colder than the climate
   every emulator setup was built on; the forest maps will drift towards that climate over 30 years. The usual cure
   is anomaly coupling (feed the emulator observed climatology + SpeedyWeather's anomaly) — not done.
2. Only the moisture/latent-heat channel is coupled. The emulator sets no albedo, roughness or snow cover for the
   atmosphere; runoff goes nowhere (no rivers in this SpeedyWeather setup); SpeedyWeather's own soil-moisture bucket
   and snow keep running underneath (its soil moisture only enters the land heat capacity).
3. One emulator cell represents a 3.75° column (nearest cell); running all 0.5° cells under a column and
   area-averaging would cost ~54× more emulator time (~470 s per simulated year, ~4× the atmosphere).
4. The daily flux is lagged one day (a day's weather must be complete before the emulator can compute it).
5. Nitrogen-off model only (no CO2 input), as ADR 0341; the nitrogen-on CO2 release (ADR 0344) has setups for 674
   representative cells only and is not wired.
6. 10 years, one realisation per arm: the seasonal temperature differences are within plausible internal
   variability.
