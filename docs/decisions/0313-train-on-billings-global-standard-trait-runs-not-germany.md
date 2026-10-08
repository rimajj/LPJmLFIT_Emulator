# 0313 — Train the emulators on M. Billing's global standard-trait LPJmL-FIT runs, not on the Germany runs; the Germany humidity re-run is cancelled

* **Status:** **accepted — owner instruction** (2026-10-08). Changes the training venue of `EXECUTION_PLAN.md`
  revision 2 (Track D row D2 and line X's assignment); the plan edit lands with this record.
* **Date:** 2026-10-08.
* **Line:** X. Tier-1 block 0310–0329. **Next free number: 0314.**
* **Owner, verbatim (2026-10-08):** *"look in /home/billing/ for the last used scripts for model runs. I think billing
  recently made some global runs with the trait-vector lpjmlfit version. find out which runs he did and where they are
  saved. ignore the ones where he actually used trait vectors, I am looking for normal runs with randomly initialized
  traits. if you find suitable global runs, use them for training the emulators instead of the germany runs that you
  are planning"* — then *"It does not matter whether his model version aligns with the one we used so far for the
  emulators. the emulator needs to work with every model version"* — then *"don't forget to cancel the germany runs if
  you think we have better data now with the global runs already on disk"*.

## 1. What exists (all `[VERIFIED 2026-10-08]` from the run directories, configs and logs)

Model code: `/home/billing/LPJmLFit_global_final` (git branch `trait_vector`, remote `gitlab.pik-potsdam.de/bloh/LPJmLFit`).
Every job file sets `LPJROOT` to that ONE live directory, which is rebuilt and re-tuned in place (latest build
2026-10-08 10:42, with uncommitted edits to `par/pft_lpjmlfit.js` and `src/tree/mortality_tree_ind.c`) — so a run's
model version is identified by the **build date printed in its own `lpjml.*.out`**, never by the directory.

Runs: `/p/projects/pbscience/billing/LPJmLFIT/global/`. Billing's own protocol
(`run/FD_EF/simulation_protocol.txt`) names the families: **r1 = "full diversity: standard LPJmL-FIT"** (random
draws + inheritance; config `"prescribe_estab": false`, `param_lpjmlfit_fulldiv.js`); r0 = everything-is-everywhere;
**r2–r6, rSLA, r2_<trait> = traits prescribed from r1** (the trait-vector runs the owner said to ignore). Only r1 is used.

| set | members used | climate | per-tree table | build |
|---|---|---|---|---|
| GCM historical | r1_2,3,4,6,7,8,9,10 | GFDL-ESM4 (ISIMIP3b) 1901–2014 | 1985–2014 | Feb-5-2026 (2–8), May-26-2026 (9,10) |
| GCM ssp126 / ssp245 / ssp370 | same 8, each from ITS OWN `restart_2014_nv.lpj` | GFDL-ESM4 2015–2100, CO2 constant from 2014 | **2071–2100 only** | same as its historical leg |
| reanalysis | r1_1,2,3,5,6,7 | GSWP3-W5E5 obsclim 1901–2019 | 1990–2019 | Oct-1/6/7/8-2026 (Billing's current development model) |

All: 67 420 cells, **25 patches**, `individual`+`inheritance` on, 1000-yr spin-up per member with `random_seed` = member
number (so members are genuinely independent — ADR 0041's "a new seed under restart is a clone" does not apply),
`"relative_humidity": false` with `huss` (specific-humidity) files — **consistent, i.e. free of the defect that
corrupted the Germany production runs after 2070**. Every leg used ends `lpjml successfully terminated, 67420 grid
cells processed.` The per-tree table is the stock 29-column `ind` writer (only trees > 5 m, plus grass), identical in
schema to every table this repo already reads. 2015–2070 of the scenario legs has annual gridded outputs only
(`output_transient/`: vegc, agb, fpc, soilc, litc, firec, monthly gpp/npp/rh/transp/…), no per-tree table.

**Excluded, with reasons:** r1_1 (its scenario legs ran on a Dec-2025 build from a historical run later overwritten
by a Jan-2026 re-run, so the historical table on disk is not their parent); r1_5 (its historical leg was re-run in
Jun 2026 over the restart its Feb-build ssp126/245 legs started from, and its ssp370 re-run failed); reanalysis r1_4
(run failed). These could be recovered for single-period use, but not as a historical→future pair.

⚠ **Cell index:** these runs use `/p/projects/biodiversity/input_VERSION2/grid.bin` (longitude-major; **Hainich =
28008**, verified `(10.25, 51.25)`), NOT the orderA grid of the repo's existing global ground truth (Hainich = 42490)
— CLAUDE.md §1. Never join the two on `Cell` without a remap. The GFDL-ESM4 `.clm` forcing these runs read
(`/p/projects/lpjml/input/scenarios/ISIMIP3bv2/<scen>/GFDL-ESM4/`, historical under `.../historical/`) is in the same
`grid.bin` order, so climate features built from those files align with the tables directly.

## 2. Decision

1. **The training data for the emulator arms is this global set**, converted once to parquet with line X's own
   converter (`scripts/explore_glob_convert.py` → `scripts/explore_de_convert.py`) at
   `/p/projects/open/Jamir/esm_land_emulator_data/billing_global/ind/<gcm>/<scen>/s<m>/<window>/cb=NN/`
   (+ `ind_dev/` = `Cell % 10 == 0`). 38 member-windows: 8 × {h1985, ssp126/245/370 w2071} + 6 × h1990.
2. **Mixed builds are kept, labelled, not filtered** — owner: the emulator must work with every model version. The
   build is carried per member (`_gates.csv` + this record) so a version effect can be measured instead of assumed
   away; the Feb-2026 members (2,3,4,6,7,8) are the largest same-build group.
3. **The Germany 2045–2100 humidity re-run (Track D row D2) is CANCELLED.** 18 SLURM jobs (8 re-runs × 2048 cores, the
   ssp245 build gate and its evaluation, 8 conversions), job ids 2440305–2440313 and 2440805–2440813, all still
   PENDING — no compute was spent and nothing was lost; `scripts/trackd_germany_rerun.py` can resubmit any member.
   Reason: the global set gives **8 independent members on 3 scenarios** (Germany: 2 seeds), all land cells, and no
   humidity defect, which is what D2 was for. The one thing Germany had that this set lacks — a second climate model —
   is supplied globally by line S's real-scenario panel (D4: five models), which is **not** cancelled.
4. The existing Germany tables stay on disk and the Germany scorer stays usable; they are no longer the primary venue.

## 3. Conversion gates (first table, `GFDL-ESM4_historical_s2_h1985`, job 2445643_0)

`conversion_ok = True`: 351 176 725 CSV lines = rows written = rows read back, 0 nulls, 0 order violations.
Two gate checks fail **by design of global data, not of the conversion**: (a) `unique` — 235 repeated
`(Cell, Patch, Type, ID)` keys, **0** once the two immutable traits are added (`gate_pass_traitkey` key), the same
writer property the Germany tables have; (b) `census` — 4 807 cells never appear vs 3 180 rock cells: of the 1 627
extra, **1 616 have VegC exactly 0 over 1985–2014** in the run's own `vegc.nc` (high Arctic, hyper-arid) and 11 a trace
(≤ 30 gC/m² vs a median 1 997), plus 2 207 (cell, year) holes in present cells — bare land, which the Germany-era check
(every non-rock cell vegetated) does not anticipate.
Two converter changes were needed, both **byte-identical for Germany**: the `Cell` dtype is taken from `SCHEMA`
instead of a hard-coded `Int16` (global cells reach 67 419 > 32 767), and the two whole-table sort keys use a year
multiplier of 1e9 instead of 1e7 (`Cell·256` reaches 1.7e7 globally, which made the dev-file check report false
order violations).

## 4. Consequences / open

* Line X's Germany round 1 of A2–A7 moves to this set. Decision point DP-A1 was written for Germany (held-out climate
  model, 1985 → 2044); with one GCM the held-out axis here is the **member** and the **scenario** (e.g. hold out
  ssp245 or ssp370), and the across-model test stays with line S's panel — an integration point for the plan.
* A free run from 2014 can be scored per tree only at 2071–2100; 2015–2070 is checkable only on stand/grid level
  through `output_transient/`. Germany's 2015–2044 tree tables had no such gap.
* 25 patches here vs 250 in Germany: per-cell distributions are noisier; the eight members are what compensates.
* Climate features for the GFDL-ESM4 legs still have to be built (same `grid.bin` order; ISIMIP3bv2 `.clm` files).
* Billing's directory is live: nothing here copies his model, so re-reading a config later may show a different
  state than the runs used — trust the run directory's own copied `lpjml_*.js` and logs.
