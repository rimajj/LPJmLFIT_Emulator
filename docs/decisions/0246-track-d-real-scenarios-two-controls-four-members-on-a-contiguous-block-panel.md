# 0246 — Track D is produced: real climate-model scenarios instead of synthetic rescaling, two constant-climate controls, four members, on a 105-block contiguous panel; and the Germany 2045-2100 re-run

* **Status:** accepted (owner instruction 2026-10-08: *"1.: yes, produce all data that you need"*, answering the
  question whether to re-run Germany 2071-2100, and the plan revision of the same day, ADR 0096).
* **Date:** 2026-10-08
* **Line:** S (tier-4 block 0240-0259). Produced by an integrator-launched session working on `line/S`, because
  line X had a live session and line S's worktree was idle.
* **Implements:** `EXECUTION_PLAN.md` revision 2, Track D (D0-D4). **Changes D4's design** (below) — raised to the
  integrator in the same merge.
* **Tooling:** `scripts/trackd_germany_rerun.py`, `scripts/trackd_panel_select.py`, `scripts/trackd_panel.py`,
  `scripts/trackd_regrid_forcing.sh`, `scripts/trackd_collect_panel.py`, `scripts/trackd_convert_germany.py`;
  skill `trackd-data`; data README `/p/projects/open/Jamir/esm_land_emulator_data/trackD/README.md`.

## 1. D4 uses REAL scenarios of five climate models, not a rescaled single model

The plan specified SSP370's change pattern scaled x0.5 / x1.5 plus a swap of the two models' patterns. Two facts
changed that:

1. **The real thing is on disk.** `/p/projects/lpjml/input/scenarios/ISIMIP3bv2` holds LPJmL-ready ISIMIP3b
   climate for ten models under historical / ssp126 / ssp370 / ssp585, in the same format the ground truth's MPI
   files were made from (`regrid_ssp370_to_orderA.sh`: a lossless `regridclm` permutation to orderA).
2. **The literature warns against the synthetic design.** Stylised factorial perturbations "failed to extrapolate
   effectively to the real CMIP6 climate scenarios ... combinations ... too far removed from those expected in
   realistic settings" (R00430 L1096-1100; `docs/review_comparison.md`).

So D4 = the five ISIMIP3b primary models (GFDL-ESM4, IPSL-CM6A-LR, MPI-ESM1-2-HR, MRI-ESM2-0, UKESM1-0-LL) x
{ssp126, ssp370, ssp585}. Every panel cell sees 15 realistic futures with different warming amounts and patterns,
which breaks the "one climate per place" confounding (ADR 0311's 76.4 %) by construction. **ssp585 replaces the
synthetic x1.5 as the out-of-distribution amplitude**, and whole models can be held out. Forcing: 65 new orderA
files; the procedure was gated by re-deriving the ground truth's MPI ssp370 tas file **byte-identically** first.

## 2. Two constant-climate controls, both with the model's own `fix_climate`

`iterate.c`: for `year > fix_climate_year` the climate year is drawn from `fix_climate_interval` (shuffled if
`fix_climate_shuffle`), and CO2 is taken at `fix_climate_year` — with the constant-CO2 file that is 409.63 ppm,
identical to every scenario leg. So:
* `ctl_obs` — observed GSWP3-W5E5 weather of 1990-2019, shuffled, recycled 2020-2100 (the plan's D1);
* `ctl_mpi370` — MPI-ESM1-2-HR ssp370 weather of 2015-2034, shuffled, recycled (a same-model control, because the
  scenario legs switch from observed to model weather in 2020).
Not detrended (the plan said detrended): the built-in mechanism cannot detrend, and a 30-year shuffled window has
a stationary mean. Recorded as a deviation.

## 3. Four members; two are new spin-ups

m1/m2 = the two ground-truth members, starting from their global restart_2019. m3/m4 = new members: every block is
spun up from scratch for 1000 years with random_seed 3 / 4 (ADR 0041: a new seed under restart is a clone; only a
new spin-up is a new member), then 2000-2019, then the legs. The per-cell seed uses the GLOBAL cell index
(`newgrid.c:460`), so a block's spin-up equals what a global spin-up with that seed would give those cells, up to
the decomposition effect.

## 4. The panel is 105 CONTIGUOUS 10-cell blocks

LPJmL runs a contiguous `startgrid..endgrid` range only, and orderA runs south->north in latitude bands, west->east
inside a band, so a valid 10-cell block is a compact 5 deg strip. Selection (`trackd_panel_select.py`, fixed seed):
>= 8 of 10 cells tree-bearing; 20 climate strata (temperature quintiles x precipitation quartiles); distinct 15 deg
tiles within a stratum and globally unused tiles preferred, visited round-robin; the five biome cells' blocks
forced in. Result: 105 blocks, 1 050 cells, **96 distinct 15 deg tiles** (a first draw without the global tile
preference reached only 64). `test/testitems/references/S_D0_panel_blocks.csv`.
Panel runs are their own realisation and are compared only with panel runs (ADR 0041).

## 5. Outputs

Every panel run writes the per-tree table with **all heights** (`LPJ_IND_ALL_HEIGHTS`) and **real per-tree gross
GPP** (`LPJ_IND_TRUE_GPP`; ADR 0130 — in the ground truth the `gpp` column is a copy of `npp`), annual vegc /
lai_stand / fpc_stand, monthly swc by layer, and — on six legs (hist, MPI x 3 scenarios, UKESM ssp370, ctl_obs) —
daily prec, transp, evap, interc, runoff, swe, rootmoist, pet, npp, gpp. Daily output is not written on every leg
to keep the volume sensible; the six give the daily water/carbon model four members and the full amplitude range.

## 6. The Germany re-run (D2)

All 12 members re-run 2045-2100 in ONE continuous run from production `restart_2044_nv.lpj` with the production
2045-2070 config (humidity on, `fix_climate` off), outputs from 2045, the per-tree table switched on (2045-2070 had
none), restart written at 2100. The production 2071-2100 config's own `fix_climate` block acts only for years >
2100, so the humidity key is the only defect. Each member uses the build its production run used, read from its
logs: ssp245 = Feb-2026 (source b2e5ca9, built for this; gated against production rows before its four members
are submitted, automatically), the rest = Dec-2025 (line X's gated rebuild). Converted with line X's own converter
(window `w2045`), so line X's code reads it unchanged.

## 7. Cost (derived, to be replaced by the measured numbers in the next STATE entry)

Panel: ~2-3 s per block-year on one core => ~1 000 core-h for everything incl. the two spin-ups. Germany: ~2 h on
2 048 cores per member (the per-tree table dominates), ~50 000 core-h for twelve.

## What is NOT decided here

Nothing about which method wins. These are data; the scoring rules are `EXECUTION_PLAN.md` §4/§8.
