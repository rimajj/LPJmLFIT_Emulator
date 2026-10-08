---
name: billing-global-runs
description: Find, audit and convert M. Billing's GLOBAL LPJmL-FIT runs (the emulator training set since ADR 0313) — where they live (/p/projects/pbscience/billing/LPJmLFIT/global/{GCM,reanalysis}), which run families are standard random/inherited traits (r1) vs trait-vector/prescribed-trait runs to ignore (r0, r2–r6, rSLA, r2_<trait>), how to read a run's model build, check its historical→future restart parentage, and convert its ind.csv to parquet with scripts/explore_glob_convert.py. Use whenever training or scoring an emulator on the global GFDL-ESM4 / GSWP3-W5E5 members, adding a new Billing run or member, or when someone says "billing's runs", "the global runs", "r1_<n>", "LPJmLFit_global_final", "trait_vector".
---

# Billing's global LPJmL-FIT runs (ADR 0313)

**Code:** `/home/billing/LPJmLFit_global_final` (branch `trait_vector`). Every job sets `LPJROOT` to this ONE live
directory, rebuilt and re-tuned in place ⇒ a run's version = the build date in its own `lpjml.*.out`
(`lpjml C Version 5.6.004 (<date>)`), never the directory. git needs `git -c safe.directory=<dir>`.
His shell history is not readable; `run/FD_EF/simulation_protocol.txt` is the run catalogue.

**Runs:** `/p/projects/pbscience/billing/LPJmLFIT/global/`
- `GCM/<historical|ssp126|ssp245|ssp370>/GFDL-ESM4/<run>/`, `reanalysis/<run>/` (GSWP3-W5E5), each with its own
  copied `lpjml_*.js` + `input_*.js`, `slurm_*.jcf`, `lpjml.<jobid>.out`, `output/ind.csv(.json)`, `restart/`.
- Families: **r1 = standard LPJmL-FIT (use)**; r0 everything-is-everywhere; r2–r6 / rSLA / r2_<trait> = traits
  prescribed from r1 (the trait-vector runs — ignore). Standard runs have `"prescribe_estab": false`.

**Audit a member before using it** (all four must hold):
1. `grep 'successfully terminated, 67420' <run>/lpjml.*.out` on the two newest logs (spin-up + transient; never trust
   SLURM state — the jcfs always exit 0).
2. Build date of each leg (`grep -oh 'Version 5.6.004 ([^)]*)'`).
3. Scenario leg's `"restart_filename"` points at the SAME member's historical `restart_2014_nv.lpj`, and that
   historical run was not re-run afterwards (compare build dates / `ls -l --time-style=+%F` of the restart). This is
   why r1_1 and r1_5 are excluded.
4. `ind.csv.json` years: historical 1985–2014, scenarios 2071–2100 (2015–2070 only gridded, `output_transient/`),
   reanalysis 1990–2019.

**Convert:** `scripts/explore_glob_convert.py` (members listed at its top; add new ones there) wraps line X's
`scripts/explore_de_convert.py`:
```bash
P=/home/jamirp/.conda/envs/py311_new/bin/python
$P scripts/explore_glob_convert.py list
$P scripts/explore_glob_convert.py submit 0-37%4 priority priority 16 01:00:00   # ~2–3 min per 66–76 GB table
$P scripts/explore_glob_convert.py collect      # → .../billing_global/ind/_gates.csv
```
Output `/p/projects/open/Jamir/esm_land_emulator_data/billing_global/`. Judge by `conversion_ok`, not `gate_pass`:
`census` fails by design (≈1 600 bare-land cells with VegC == 0 never appear, plus occasional (cell, year) holes) and
`unique` fails on the raw `(Cell, Patch, Type, ID)` key exactly as in Germany (0 with the trait key).

**Traps:** cells are in `/p/projects/biodiversity/input_VERSION2/grid.bin` order (Hainich = 28008) — never join on
`Cell` with orderA tables (Hainich = 42490). Soil file `soil_new_67420.bin` is raw uint8, no header (code 13 = rock).
Global `Cell` needs Int32 (> 32 767). 25 patches. `"relative_humidity": false` with `huss` = consistent (no Germany
humidity defect). CO2 constant from 2014 in the scenarios.
