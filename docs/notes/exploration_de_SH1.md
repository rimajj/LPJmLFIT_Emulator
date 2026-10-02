# Germany emulator, shared item SH1: climate extension and frozen-mean climatology (v2)

Line X exploration note, 2026-10-01. Script: `scripts/explore_de_sh_climate_ext.py`. Data and README:
`/p/tmp/jamirp/X_de/shared/climate/` (`_README.md`, `_gates.json`, `_report.json`).

**v2 rebuild after the owner's decision to use only the correct 1985-2044 data.** SLURM job 2371081 built
everything; job 2371095 re-ran the checks after a one-line fix to a report filter. All 10 checks pass. The
first version was built before the decision. It is kept in `_superseded_v1_pre_owner_exclusion/` and must not be
used: its "outside the training climate" thresholds were computed with 2071-2100 training years.

## What changed in v2

* **Every climate year whose original-model run is unusable is now marked.** These are the ssp years
  2071-2100, where the run read relative humidity as specific humidity. The mark is taken from the shared
  registry, not typed in by hand. The climate rows themselves are kept, because the forcing is correct. The
  2045-2070 years are needed for an optional continuation of the free run, which is checked on cell totals.
  The 2071-2100 years will be needed if those runs are redone with the setting fixed.
* On the marked years the vapour-pressure-deficit inputs that describe "what the original model saw" are
  blank (null), so no model can train on them by accident. The helper `scan_ext()` drops the marked years by
  default.
* **The "outside the training climate" thresholds now come from 1985-2044 only.** The hottest training year
  sets the threshold on annual mean temperature:
  * main split (trained on MPI-ESM1-2-HR): 14.09 C (was 15.83 C);
  * split trained on ACCESS-CM2: 14.07 C (was 17.82 C);
  * same-model-version scenario split: unchanged at 14.09 C.
* The check that the temperature-stress death rule is reproduced exactly now reads only the 16 usable member
  windows. That is 917 million dev-cell tree rows, matched to print precision on 100.0000 % of rows. The 24
  unusable windows were not read.

## What is unchanged

* Per-tree-type cold/heat stress-day counts, days 15-365, against each type's thresholds from the live parameter
  file. They give the original model's temperature-stress death probability exactly.
* Anomalies against the same climate model's 1985-2014 mean in each cell.
* The frozen 1985-2014 per-cell climatology, which is the climate of the frozen-climate comparison arm. Its base
  period was always clean.

## What the clean climate can and cannot test (907 dev cells) [MEASURED]

* **The scenarios barely differ in 2015-2044.** Between-scenario difference in annual mean temperature:
  * SSP3-7.0 minus SSP1-2.6: +0.015 K (ACCESS-CM2) and +0.041 K (MPI-ESM1-2-HR), median over cells.
  * SSP2-4.5 minus SSP1-2.6: −0.17 K and −0.01 K.
  * No dev cell shows a difference larger than twice its year-to-year noise.
  * Summer rain, summer water balance, summer dryness of the air and frost-stress days behave the same way:
    0-4 % of cells.
  * Consequence: the response statistic the plan made primary (scenario minus scenario in 2015-2044) has no
    climate contrast behind it. Any difference the original model shows there is weather noise plus its own
    randomness, not a warming response. It cannot test whether an emulator responds to warming. This is a
    limit of the data, not a property of any emulator.
* **The change from 1985-2014 to 2015-2044 is a real signal.**
  * Warming: +0.90 to +0.93 K (MPI) and +1.37 to +1.55 K (ACCESS), above the noise in 100 % of cells.
  * Drier summer air above the noise in 38-100 % of cells.
  * Lower summer water balance above the noise in 46-88 % of cells (ACCESS) and 2-29 % (MPI).
  * This is the testable warming response in the clean data. It shares the same period as the CO2 rise in the
    original runs, which the emulator by design does not see.
* **2045-2070 does separate the scenarios.**
  * MPI SSP3-7.0 minus SSP1-2.6: +0.59 K, above the noise in all cells.
  * ACCESS SSP2-4.5 minus SSP1-2.6: +0.46 K, all cells.
  * ACCESS SSP3-7.0 minus SSP1-2.6: +0.25 K, 7.5 % of cells.
  * Those years have no tree table, only cell totals, so any scenario-contrast test there is on cell totals.
* **Outside the training climate.** No test cell-year in 2015-2044 is above the Germany-wide training maximum.
  Against each cell's own training maximum, 4.6-6.8 % of held-out ACCESS 2015-2044 cell-years are hotter. In a
  2045-2070 continuation that share is 19-39 % (ACCESS) and 9 % (MPI SSP3-7.0 under the same-model-version
  split).
