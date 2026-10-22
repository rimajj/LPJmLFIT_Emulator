# ADR 0360 — The coupled emulator on the fixed SpeedyWeather atmosphere, fed a 2 m air temperature (pre-registration)

- Status: Accepted — the 2 m feed is NOT adopted (results below, 2026-10-22)
- Date: 2026-10-22
- Context: ADR 0345 (coupling), ADR 0346 (SpeedyWeather's cold land), JOURNAL 2026-10-21/22 (cold-bias side track:
  convection fix on branch coldfix-E, upstream SpeedyWeather #1339; clouds; high-latitude winter)

## Context

Every coupled emulator run so far (ADR 0345/0346) used stock SpeedyWeather 0.23, whose land is 6.6 °C colder than the
real climate at the emulated cells; the emulator reads that as climate change (vegetation carbon −6 % and falling over
10 years). The cold-bias side track has since produced an atmosphere that is warm instead (branch coldfix-E 6ae14204:
four-band longwave with clouds and water vapour, surface air from the actual lapse rate, Betts–Miller convection with
the parcel ascent in 10 sub-steps and moist-static-energy entrainment = the "E3ent50" base). Stand-alone, its land air
is +2.4 K above W5E5 (slab ocean), and two thirds of the high-latitude winter excess is a definition: SpeedyWeather's
surface air temperature is the lowermost layer's (~550 m up) in an inversion. A diagnostic 2 m air temperature
(surface-layer profile between top soil and that air, stability matched to the model's own drag; now
`scripts/online_coupling/speedy_air2m.jl`, shared with the reproducer) gave land annual +1.1 K, high-latitude coldest
month +3.5 K vs GFDL-ESM4.

## What is run (all 10 years from 2015, T31 L8, prescribed seasonal SST, emulator albedo + roughness channels)

| arm | atmosphere | land | emulator fed |
|---|---|---|---|
| S (exists: `coupled/speedy_t31_coupled_sst_alb_z0_10y`) | stock 0.23 | emulator | SpeedyWeather surface air |
| A | fixed (E3ent50) | emulator | SpeedyWeather surface air (`AIR=model`) |
| B | fixed (E3ent50) | emulator | 2 m air (`AIR=2m`) |
| C | fixed (E3ent50) | SpeedyWeather's own (control) | — (2 m recorded) |

Driver: `scripts/online_coupling/run_speedy_landemu.jl` with the new knobs `AIR`, `LW`, `CONVKW`, `T0`
(+ `LWKW`/`CLOUDKW`/`SWKW`), environment `PROJ=/p/tmp/jamirp/speedy_landemu_fix_env` (the coldfix-E source + PythonCall).
All knobs unset = the stock run (checked: a 1-year stock run must reproduce the first year of arm S's record).

## Scores (years 2–10, emulated columns, cos-latitude × land-fraction weighted)

`diagnose_speedy_climate.py` (now also scores the recorded 2 m temperature) and `score_speedy_landemu.py` (replay and
water gates; must pass for A and B).

## Decision rule (adopt `AIR=2m` for coupled runs on the fixed atmosphere)

The temperature the emulator is fed, B vs A, against W5E5 observations 1985–2014:
1. annual |bias| smaller by ≥ 0.5 K;
2. coldest-month bias poleward of 50° at most half of A's;
3. no latitude band (< 23.5°, 23.5–50°, > 50°) with an annual or warmest-month |bias| worse than A's by > 0.5 K.

Expected from the stand-alone runs: 1 and 2 pass (annual ~+2 → ~+1 K; > 50° coldest month roughly halved), 3 passes
because the 2 m value equals the model air whenever the ground is warmer than the air.

Reported without a rule: whether the fixed atmosphere (A, C) is closer to the real land climate than stock (S); the
emulator's vegetation carbon, GPP and ET trajectories in S, A, B (does the drift of ADR 0345 shrink?); the coupling's
effect on the atmosphere (A or B vs C).

## Results (2026-10-22; jobs 2661272–4, scored by 2662733–5; `coupled/climate_diagnosis_adr0360.json`)

Gates: stock check passed (1-yr stock run = year 1 of S, bit for bit); replay identical and water closed to the leap days
in A and B (relative 7.7e-4 / 7.6e-4, as S's 7.9e-4).

**Temperature the emulator is fed, minus W5E5 1985–2014, years 2–10 (K):**

| | annual | warmest month | coldest month | < 23.5° annual / warmest | 23.5–50° annual / warmest | > 50° annual / coldest |
|---|---|---|---|---|---|---|
| S stock (surface air) | −7.69 | −9.94 | −4.06 | −10.94 / −12.02 | −5.70 / −9.20 | −3.29 / +2.74 |
| A fixed, surface air | **+1.44** | +2.41 | +1.80 | −0.73 / +0.20 | +1.05 / +3.20 | +8.51 / +14.65 |
| B fixed, 2 m air | **−1.21** | +1.25 | −2.40 | −2.83 / −1.34 | −1.34 / +2.19 | +3.69 / +4.26 |
| C fixed control (surface air; 2 m) | +2.31; +1.04 | +2.29; +1.99 | +3.19; +0.55 | +0.69; +0.23 | +2.10; +1.00 | +7.36; +3.46 / +14.12; +4.94 |

Rule: (1) annual |bias| 1.44 → 1.21, smaller by 0.23 K < 0.5 ✗; (2) > 50° coldest month 14.65 → 4.26 ≤ half ✓;
(3) tropics annual worse by 2.10 K and warmest month by 1.14 K ✗ (mid-latitudes annual +0.29, inside). **Not adopted.**

**Why it fails where it passed stand-alone (post hoc, not separated by a run):** the stable-air branch of the 2 m
formula pulls the 2 m value towards the ground whenever the air is warmer than the top soil. With the emulator's
evapotranspiration (tropics 2.34 mm/day vs SpeedyWeather's own land 0.72) the ground is evaporatively cooled to about
the air temperature (tropics air − soil −0.25 K vs −3.61 K in the control), so the daily-mean air is warmer than the
ground on 55 % of tropical days (control 16 %) and the 2 m value falls 2.4 K below the air (control 0.5 K). The
emulator's forest roughness (up to 2.0 m vs SpeedyWeather's constant 0.5 m) puts "2 m" inside the canopy of the
log profile and strengthens the same pull. Which of the two dominates is not measured (a run with `AIR=2m` and stock
roughness would separate them). The formula has no displacement height, so it is not valid over tall canopies as is.

**Reported without a rule:**
- The fixed atmosphere puts the coupled land within +1.4 K of the real climate (stock −7.7 K): the emulator is no
  longer driven by a 7–8 K cold signal. High-latitude land stays +8.5 K warm in the annual mean (+14.7 K coldest month)
  — the inversion definition plus the warm lower troposphere found stand-alone.
- The coupling cools the land air by 0.9 K (A vs C) and makes it wet: precipitation +182 mm/yr above W5E5 in A (+141 in
  B) against +8 in the control; the emulator's ET is 590–616 mm/yr against SpeedyWeather's own ~180.
- Emulator: vegetation carbon over the T31 land falls 866 → 842 PgC in A and 859 → 835 in B over the 10 years (−2.8 %,
  −2.9 %), while stock S is flat (831 → 831); NPP is 64–70 PgC/yr in A and 68–73 in B vs 81–84 in S, GPP similar
  (150–161). So the warmer, wetter fixed atmosphere does not stop the vegetation-carbon decline; the cause (warmer
  respiration, high-latitude warmth, too much rain) is not diagnosed here.
- Cost: 225 core-s per simulated year coupled on the fixed atmosphere (stock 157; emulator 8.7 s of it), 201 control.

**Defaults unchanged:** `AIR=model`. The 2 m value stays recorded in every run.
