# SH12 (v2) — cell-level check tables 1985-2070 from the correct gridded outputs

Line X, Germany emulator, round 2 shared infrastructure. Repurposed 2026-10-01 after the owner decision to use only
correct data ("double check if the runs after 2070 were really corrupted with the wrong settings. if its true, lets
only use the earlier data that is correct, for now."). The v1 item (2044 -> 2071 survivor tables) read the excluded
late-century runs; its outputs and its note are kept under
`/p/tmp/jamirp/X_de/shared/gap/_superseded_v1_pre_owner_exclusion/` and must not be used.

Script: `scripts/explore_de_sh_gap.py` (v2). Data and the consumer README: `/p/tmp/jamirp/X_de/shared/gap/`.

## What it gives the tracks

The original model ran 2045-2070 (the `lpjml_2070` segment, humidity read correctly) but wrote no tree table for
it. Its annual gridded outputs exist. SH12 maps them to cells and turns them into check tables, so an emulator's free
run 1985 -> 2070 can be checked on cell aggregates for 2045-2070 against both seeds of the original:

* the vegetation carbon of all trees of 5 m and taller (`hm_ge5`, the primary check, exactly what a roster sums to),
* the mass-weighted median tree height (`hm_ge5_medH`) and rooting depth (`d95_med_cm`),
* tree crown cover per tree type, AGB, VegC, litter and soil carbon (context),
* per cell and per one-degree block, with the original's own two-seed spread beside each value.

A helper `roster_check_aggregates(roster, npatch)` computes the same quantities from any roster, so every track uses
one definition.

## Verified [MEASURED, dev = 907 cells unless noted; full Germany in `_gates_all.json`]

* Humidity setting of every segment read (4 Historical runs, 12 x 2015-2044, 12 x 2045-2070): the writer job's own
  log lists the humidity input as `rhumid`, its config sets `"relative_humidity": true`, and SH0 agrees — 40 of 40.
  No `_2100`, `_3100` or `_3070` file is opened (the reader refuses), and no table holds a year after 2070.
* Every file is a raw LPJmL output, covers exactly its years, has no fill at any of the 9067 grid cells, and was
  written by the single job SH0 lists for those years; the restart chain 1985-2014 -> 2015-2044 -> 2045-2070 is
  clean for all 12 ssp trajectories (24 links).
* Raster-to-cell map: cell ids 0-9066 once each; lat/lon match the input grid file to 2e-6 degrees; every
  member's own grid file (40 of them) has the identical cell-id raster.
* Units: pools gC/m2, histograms gC/m2/bin, noleap calendar, time axes start at each segment's first year.
* `height_mass` is the vegetation carbon of all trees, including those flagged dead that year, binned by 1-m height:
  summed over bins of 5 m and above it reproduces the roster to at most 3.4e-7 relative (9.1 M bins, 435 360
  cell-years), while live-only vegetation carbon (median 2.7 % off) and AGB (median 24 % off) do not fit.
* `D95_mass` holds the same tree population: its total equals the height histogram's total to 1.2e-7 relative in
  every cell-year 1985-2070 (10.4 M cell-years, all trajectories) — so this identity also holds in the years with no
  tree table. Its bins are 18 CM wide although the file labels the axis "mm": the 18-cm reading puts 100 % of the
  roster's bins inside the gridded bins, the "18 mm" reading 32 %.
* The helper reproduces the gridded `hm_ge5` from the truth roster to <= 3.4e-7 relative and the median height to
  <= 1.4e-6 m in 99 % of cell-years (max 0.037 m); every one of the 2 386 cell-years with a difference above 1e-4 m
  contains a tree whose printed height is an exact integer, whose bin cannot be told from the table.
* Below 5 m: 0.7 % of tree vegetation carbon (median cell-year, p99 1.8 %); 0.5 % of AGB.

## Response signal-to-noise on cell aggregates [MEASURED, dev cells]

Contrast ssp370 minus ssp126, same GCM and C build, each seed; 'determined' = the two-seed mean exceeds the
two-seed difference. With no real response this happens in 29.5 % of units (derived from Gaussian seed noise).

| | cells (907) 2015-44 | cells 2045-70 | blocks (52) 2015-44 | blocks 2045-70 | Germany hm_ge5, 2015-44 / 2045-70 / 2061-70 |
|---|---|---|---|---|---|
| MPI-ESM1-2-HR | 0.45 | 0.89 | 0.69 | 1.00 | +1.7 % / -11.8 % / -20.1 % |
| ACCESS-CM2 | 0.42 | 0.38 | 0.75 | 0.62 | -2.2 % / -1.2 % / -2.5 % |

Full Germany (9065 cells, 52 blocks of ~175 cells; `check/response_snr_all.parquet`), hm_ge5, ssp370 - ssp126:

| GCM | window | cells determined | blocks determined | median block signal / seed difference |
|---|---|---|---|---|
| MPI-ESM1-2-HR | 2015-2044 | 0.43 | 0.85 | +1.3 % / 0.20 % |
| MPI-ESM1-2-HR | 2045-2070 | 0.86 | 1.00 | -11.5 % / 0.43 % |
| MPI-ESM1-2-HR | 2061-2070 | 0.97 | 1.00 | -20.0 % / 0.55 % |
| ACCESS-CM2 | 2015-2044 | 0.44 | 0.90 | -2.0 % / 0.29 % |
| ACCESS-CM2 | 2045-2070 | 0.37 | 0.83 | -0.9 % / 0.43 % |
| ACCESS-CM2 | 2061-2070 | 0.39 | 0.85 | -1.7 % / 0.47 % |

Block numbers are much better determined on all cells than on the 907 dev cells (a dev block holds ~17 cells).
OBSERVATION (mechanism not established): MPI ssp245's two seeds drift apart by 2-3 % of Germany-wide tree carbon
from about 2020 on (configs identical except seed and restart), while every other scenario's seeds agree to <= 0.5 %;
so the MPI ssp245 contrasts have a 10x larger seed difference (block 2015-2044 determined 0.31, Germany not determined).

The 2015-2044 response is barely above the no-signal rate at cell level and only partly determined at block level;
it is determined Germany-wide but small (about 2 %), and of opposite sign in the two GCMs. In 2045-2070 the MPI
response is large (12-20 % less tree carbon under ssp370) and determined in almost every cell. ACCESS shows almost
none. So extending the free runs to 2070 and checking these aggregates is the strongest clean warming-response test
this data permits — at aggregate level only, and the strong signal comes from the GCM whose scenarios are in the
DEV-A training set (its 2045-2070 years are not).

## Amendments to the pre-registered gates (both recorded in the gate file beside the original verdict)

* Humidity gate: the pre-registered segment count was 28; the correct count is 40 (each of the 12 ssp trajectories
  re-reads its seed's Historical files). The criterion itself is unchanged; all 40 pass.
* Helper gate: pre-registered "median height difference p99.9 < 0.01 m" failed (0.0147 m). The tail is entirely the
  integer-height ambiguity (2 386 of 2 386 cases); amended to "every difference above 1e-4 m explained by that, max
  < 0.5 m". `pass_preregistered = false` stays in the record.

## Not done / caveats

* No tree count or trait-distribution check is possible for 2045-2070 (no tree table there).
* The late-century runs remain unusable until re-run with the humidity setting fixed.
* The response numbers are on cell aggregates, not on the tree-level statistics the scorer uses for 2015-2044.
* ACCESS ssp245 has a forcing-driven mortality pulse in 2045 (after a 147-mm summer in 2044); it is real model
  behaviour, so the 2045 join looks like an outlier in the continuity diagnostic.
