# ADR 0360 — The coupled emulator on the fixed SpeedyWeather atmosphere, fed a 2 m air temperature (pre-registration)

- Status: Proposed (pre-registration; results section to be appended)
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

## Results

(to be appended)
