(comment on SpeedyWeather/SpeedyWeather.jl#1339, 2026-10-22, https://github.com/SpeedyWeather/SpeedyWeather.jl/issues/1339#issuecomment-6340715593)

Three more tests around this, in case they save someone the time. Same setup as above (four-band longwave, prescribed SST, years 2–3, tropics |lat| < 15, GFDL-ESM4 reference), single realisations.

**1. Lowering the Betts–Miller target humidity fixes the humidity, not the temperature.** With `main`'s ascent, `relative_humidity` 0.7 → 0.5:
- Humidity: column water vapour drops from 50.6 to 37.7 kg/m² (reference 40.3), and the 431–555 hPa relative-humidity bias drops from +20 to +3 points.
- Temperature: the 308 / 431 / 555 hPa bias changes only from +9.0 / +6.6 / +4.1 K to +7.2 / +5.7 / +3.5 K.
- Clouds: cloud cover falls from 0.67 to 0.48 (reference 0.65).

So the warm upper troposphere is not a humidity-target problem. With the fixed ascent and MSE entrainment, a target of 0.6 changes the 300 hPa relative humidity by almost nothing (72.5 %) and the clear-sky OLR by +0.9 W/m². That moisture is not put there by the convection.

**2. With T-and-q mixing, the entrainment depth does nothing.** With an earlier version of the sub-stepped ascent, moving `σ_entrainment` from 0.5 to 0.25 and then 0 changed the 308 hPa bias only from +7.4 to +6.9 and +6.5 K. That is defect 2 above: mixing environmental T into a parcel that is already close to it has no effect, and the q deficit is discarded. With MSE mixing, the same depth change matters: −1.8 → −3.8 K at 308 hPa (table above).

**3. On a slab ocean, `main`'s ascent convects into the top layer.** In a 5-year slab run with `main`'s convection, the uppermost layer (~62 hPa) ends up +22 K too warm with 240× the reference humidity. With sub-stepping (10 sub-steps, before the condensation-level fix) it is +4 K and 18×. The stratosphere then stays a stratosphere. This may be related to the upper-troposphere moistening and runaway discussed in #1279.
