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

**The futures contain a second run.** `output/` is a re-run of 2071–2100 restarted from the continuous run's 2070
state; the two disagree from 2071 on (vegetation carbon up to 4 700 gC/m² in a cell, the original's own chaotic noise,
ADR 0041). The per-tree table belongs to `output/`, so that is the benchmark truth; `output_transient/`'s 2071–2100 is
a **second realisation** for the gridded quantities. It shares the 2070 state, so its distance to the truth is a
LOWER bound on two independent runs' distance for the slow pools — ratios against it are conservative.

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
| harness: S scored as the emulator | ratio 1 by construction; S's own typical error on GPP/ET 0.5–3 %, vegetation carbon 1–5 % (shares the 2070 state) |
| null `persist` (1985–2014 state carried forward) | the emulator must beat it on vegetation carbon and tree count in ≥ 2 of 3 future legs; if not, the stand/structure maps add nothing over the anchor |
| GPP, ET, runoff, NPP (typical-cell ratio) | GPP/ET 2–6× the second realisation (it shares the 2070 state, so its error is small); runoff and NPP worse; area totals within 5 % for GPP/ET, futures. Historical GPP total HIGH by +3 … +15 % (no CO2 input; trained at 410 ppm) |
| structure, unseen scenario | dense tree count / biomass per tree typical error 10–30 %; ssp370 (the warmest, extrapolated) the worst fold |
| ILAMB (historical, observations) | emulator overall scores within ±0.05 of the original's on gpp, et, lai, biomass, runoff; any larger gap is the daily model, since the stand is anchored |
| lpjmlstats | descriptive: global sums and maps of emulator − original per variable and period |

No pass/fail is attached to the ILAMB or lpjmlstats numbers: they are the comparison the owner asked for. The ratio
measures are reported against ADR 0318/0325's numbers (≤ 3× typical for fluxes, relaxed structure standard) for
orientation, with the second-realisation caveat of §1.

## 6. Results

(added after the run)
