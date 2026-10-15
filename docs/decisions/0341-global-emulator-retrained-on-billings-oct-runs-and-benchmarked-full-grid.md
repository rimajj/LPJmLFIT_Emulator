# 0341 — The emulator retrained on M. Billing's Oct-2026 GFDL-ESM4 runs, run on the full grid, benchmarked with ILAMB + lpjmlstats

* **Status:** accepted 2026-10-15 (design + pre-registration, written BEFORE training and scoring). Results: §6, added
  after the run.
* **Owner instruction (2026-10-15):** *"run the emulator globally now and benchmark it against the original. for that,
  use maik billings runs for training and benchmarking ... GCM/{historical,ssp126,ssp245,ssp370}/GFDL-ESM4/r1_1 ...
  once you retrained and run the emulator globally, do the benchmarking with ilamb and lpjmlstats as done in this
  project /home/jamirp/lpjml-fit/ (but using full grid simulations and not clustered simulations)"*.
* **Depends on:** ADR 0340 (release v1 package), 0313/0314/0315 (Billing's runs, climate inputs, venue), 0325 (daily
  numbers relative to a second run), 0318 (relaxed standard), 0004/0107 (CO2).
* **Code:** `scripts/glob_emu.py` (all stages), `scripts/explore_glob_convert.py` (member s1 added).
  Data: `/p/projects/open/Jamir/esm_land_emulator_data/global_emu/`.

## 1. The runs (audited 2026-10-15)

Billing re-ran GFDL-ESM4 r1_1 on 2026-10-10…14 with the build `Oct 8 2026` and moved every earlier GFDL-ESM4 run into
`GCM/<scen>/GFDL-ESM4/old/`. All four legs: `successfully terminated, 67420 grid cells processed` in both logs;
each future leg's `restart_filename` is this historical run's `restart_2014_nv.lpj`. Per-tree table (30-column Oct
layout): historical 1985–2014, futures 2071–2100. Gridded annual/monthly output: historical 1985–2014 (`output/`);
futures 2015–2100 in `output_transient/` (a subset: no stand leaf area, which `pft_lai_weighted` does NOT reproduce —
its sum is ~8× `lai_stand`), and 2071–2100 again in `output/`.

**The futures contain a second copy of 2071–2100 — but NOT a second run (corrected after scoring, see §6).**
`output/` is a re-run of 2071–2100 restarted from the continuous run's 2070 state. As written before the run, this
section called it a second realisation, from one cell's 4 700 gC/m² vegetation-carbon difference. Measured on all
cells: the two are **identical on ~92 % of cells** (GPP differs in 5 259 of 67 420 cells under ssp126, 5 016 under
ssp370); the restart reproduces the continuous run except a minority that diverges. So it is no second-run
yardstick, and the `second` columns of `eval/scores.csv` (typical error 0.000) carry no information. The benchmark
truth is `output/` (it holds the per-tree table).

Historical CO2 rises (TRENDY, 345 → 397 ppm over 1985–2014); the futures hold it at the 2014 level. The emulator has
no CO2 input (ADR 0004/0107, standing) and its daily model was trained at 409.63 ppm constant. Validity-envelope
disclosure, not a defect to fix.

## 2. What is retrained, what is not

* **Structure map (6 models) and stand map (12 models): retrained** on these four runs, all non-rock cells.
* **Daily water–carbon model: NOT retrained.** These runs write monthly, not daily, output; the deployed ensemble
  (release v1, trained on the panel's daily runs of the original under ten climate models incl. GFDL-ESM4) is used
  unchanged. So the benchmark's carbon/water fluxes are out of sample with respect to this build and every cell
  outside the panel's 1 050.
* Top-metre water capacity per cell: these runs emit no `whc_nat`; it comes from the orderA global run's 2000–2019
  `whc_nat` (the same soil map — soil codes agree on 100 % of land cells at the same lat/lon).

## 3. The anchor: the cell's own historical state (design change from release v1)

Release v1 predicts each year as a departure from an ANCHOR = the original's mean over its training runs for that
cell and year, 2020–2100. With one run per scenario, that anchor is either the benchmark truth itself (circular) or
another scenario's future (ADR 0340 §4.1: fails under an unseen scenario, and needs the original run on every cell
for every future year). Here the anchor is what any coupled deployment has anyway: **the original's own 1985–2014
state of the cell** (its spin-up product), constant in time; the anchor climate is the 1985–2014 window, so `dclim`
is the climate change since then. The start-level features (`s0`, `memoff`) are dropped (they would equal the anchor
and zero). Features: 25 trailing-30-yr climate statistics, their change since 1985–2014, the 18 anchors, lat, lon,
soil code. Targets, loss and LightGBM settings as release v1 (A7 params, 400 rounds; log target for biomass per tree).

**Held out:** leave-one-SCENARIO-out. Fold `ssp126` trains on historical + ssp245 + ssp370, etc.; each future leg is
emulated by the fold that never saw it. A deployment fit (`none`, all four legs) runs the historical period, which
is therefore IN SAMPLE for the structure and stand maps (it is the anchor period) — the historical benchmark tests
the daily fluxes, not the forest state.

## 4. The global run

All 64 240 non-rock cells. Historical: 1975–2014 (10 warm-up years from the 1985 state of the original, so the water
stores and the stand settle), daily forcing = the runs' own ISIMIP3b GFDL-ESM4 `.clm` files. Each future leg
continues 2015–2100 from the emulated end-of-2014 state (stores, stand, last year's weather, 1985–2014 climate
window). Output: monthly GPP, NPP, transpiration, evaporation, interception, runoff; yearly stand and structure,
written as LPJmL-style NetCDF on the 0.5° grid so the lpjml-fit benchmark converters read it like a model run.

## 5. Pre-registered expectations (what each comparison should return)

Measures per future leg on 2071–2100 cell means (the `output/` truth): typical-cell error = median over cells of
|E − T| / T; the same for the second realisation S; **ratio = emulator / second**. Area totals signed. Dense cells =
anchor ≥ 5 trees per patch (defined before the run).

| comparison | expectation |
|---|---|
| ~~harness: S scored as the emulator~~ | withdrawn — S is not an independent run (§1) |
| null `persist` (1985–2014 state carried forward) | the emulator must beat it on vegetation carbon and tree count in ≥ 2 of 3 future legs; if not, the stand/structure maps add nothing over the anchor |
| GPP, ET, runoff, NPP (typical-cell ratio) | GPP/ET 2–6× the second realisation (it shares the 2070 state, so its error is small); runoff and NPP worse; area totals within 5 % for GPP/ET, futures. Historical GPP total HIGH by +3 … +15 % (no CO2 input; trained at 410 ppm) |
| structure, unseen scenario | dense tree count / biomass per tree typical error 10–30 %; ssp370 (the warmest, extrapolated) the worst fold |
| ILAMB (historical, observations) | emulator overall scores within ±0.05 of the original's on gpp, et, lai, biomass, runoff; any larger gap is the daily model, since the stand is anchored |
| lpjmlstats | descriptive: global sums and maps of emulator − original per variable and period |

No pass/fail is attached to the ILAMB or lpjmlstats numbers: they are the comparison the owner asked for. The ratio
measures are reported against ADR 0318/0325's numbers (≤ 3× typical for fluxes, relaxed structure standard) for
orientation, with the second-realisation caveat of §1.

## 6. Results (2026-10-15; jobs 2503866–69 train, 2504319/2504385–87 run, 2506464 score, 2504793/2506483–85 lpjmlstats, 2504794 ILAMB)

**Run.** 64 240 land cells; historical 1975–2014 (output 1985–2014) + each future 2015–2100; 64 one-core chunks per
leg. Cost **7.65e-3 core-s per cell-year** (as release v1); the package's yearly climate equals the training table's
exactly on every chunk (gate max 0). Output: `global_emu/bench/models/Emu/` (LPJmL-style NetCDF), `global_emu/emu/`.

**Historical 1985–2014 (structure and stand IN SAMPLE — anchored; fluxes out of sample), lpjmlstats global totals:**
GPP 156.3 vs 156.3 PgC/yr (+0.04 %), NPP +1.1 %, transpiration **−8.5 %**, soil evaporation +0.9 %, interception
+1.7 %, runoff **+5.8 %**; vegetation carbon, leaf area, every plant-type cover within 0.8 %. **The original's GPP
rises 151 → 162 PgC/yr over 1985–2014 (rising CO2); the emulator's is flat** — the pre-registered +3…+15 % level bias
did not appear; the missing CO2 effect shows as a missing TREND instead (validity envelope, ADR 0004/0107). The
transpiration deficit is the daily model (not retrained; panel build), water going to runoff instead.

**ILAMB (historical, against observations, global overall scores):** emulator − original within **±0.03 on all 27
dataset comparisons** (pre-registered ±0.05 ✓): GPP +0.003…+0.017 (8 datasets), biomass −0.002…+0.005, leaf area
0.000…+0.002, ET −0.002…−0.010, tree cover −0.004/−0.012, runoff −0.004 (LORA) / **−0.027 (Dai)**, the largest gap,
from the runoff excess. Build: `global_emu/bench/ilamb/_build/`.

**Futures, each scenario UNSEEN in training, 2071–2100 cell means vs the original** (typical = median over cells of
|E − T|/T; persist = the 1985–2014 state carried forward; full table `global_emu/eval/scores.csv`):

| | ssp126 emu / persist | ssp245 emu / persist | ssp370 emu / persist |
|---|---|---|---|
| GPP typical | 6.0 % / 11.2 % | 6.0 % / 13.2 % | 6.4 % / 15.1 % |
| NPP | 7.4 / 8.4 | 7.7 / 10.1 | 10.0 / 13.9 |
| ET | 4.8 / 7.3 | 4.4 / 9.4 | 4.4 / 11.7 |
| runoff | 9.4 / 12.7 | 9.1 / 16.6 | 9.9 / 20.2 |
| vegetation carbon | 11.4 / 18.0 | 11.5 / 20.5 | 15.4 / 25.5 |
| tree count, dense cells | 6.7 / 10.2 | 6.6 / 10.5 | 7.8 / 11.4 |
| tree count, sparse | 24.5 / 41.6 | 24.0 / 48.6 | 29.5 / 57.5 |
| biomass per tree, dense | 14.6 / 25.4 | 14.2 / 25.2 | 18.2 / 29.6 |
| four trait medians, dense | 1.6–7.1 / 1.7–7.5 | 1.6–7.2 / 1.7–7.6 | 1.7–7.4 / 1.8–7.9 |

The emulator beats persistence on every flux, stand and structure quantity in all three legs (pre-registered: vegetation
carbon and tree count in ≥ 2 of 3 ✓), but on the trait medians only marginally (traits barely change in the original
either). Structure under an unseen scenario: dense tree count 7–8 %, biomass per tree 14–18 % (pre-registered 10–30 %);
ssp370 the worst fold, as expected.

**Climate response, global totals, change 1985–2014 → 2071–2100 (original / emulator):**

| | GPP | NPP | ET | runoff | vegetation carbon |
|---|---|---|---|---|---|
| ssp126 | +5.6 / +2.3 % | +3.3 / −0.9 % | +2.7 / +3.2 % | +3.9 / +3.2 % | +8.9 / +5.8 % |
| ssp245 | +3.2 / +0.1 % | −1.2 / −5.5 % | +1.4 / +2.1 % | +6.5 / +5.3 % | +2.7 / +0.8 % |
| ssp370 | −3.5 / −4.9 % | −10.2 / −14.9 % | −4.3 / −1.5 % | +2.3 / −1.6 % | **−9.2 / −2.8 %** |

Signs agree in 13 of 15. The carbon responses are biased low by ~3–5 points (GPP/NPP) — partly the historical
baseline, where the original's GPP still carries the end of the CO2 rise and the emulator's does not. Under ssp370 —
the warmest, extrapolated fold — the emulator **misses two thirds of the original's vegetation-carbon loss** (−2.8 vs
−9.2 %; late-century level +7.1 %): a tree model trained on two milder scenarios cannot extrapolate the climate
departure. Late-century area totals: GPP −1…−3 %, ET −3…−5 %, runoff +2…+5 %, vegetation carbon −3…+7 %.

**lpjmlstats reports** (FIT = original baseline, Emu under test): `global_emu/bench/lpjmlstats/report_<period>.pdf`.

**Not done / limits:** the daily model is not retrained (no daily output in these runs); no second run of this build
exists, so no ratio to the original's own noise can be formed (§1); cells that gain trees after 2014 (~3 000 by
2100) get a tree count but no biomass-per-tree or trait values (no historical anchor); top-metre capacity from another
run's `whc_nat` (same soil map); the historical stand is anchored, so ILAMB's biomass/LAI/cover scores test the
original, not the emulator.
