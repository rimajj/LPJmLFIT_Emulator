---
name: trackd-data
description: >
  The Track-D data campaign of EXECUTION_PLAN.md revision 2 (ADR 0096): new runs of the ORIGINAL model
  (LPJmL-FIT) that make the warming response identifiable. Use whenever you need, extend, collect, re-run or
  explain (a) the Germany 2045-2100 re-runs with the humidity setting fixed (`germany_rh`, scripts/
  trackd_germany_rerun.py), (b) the global stratified PANEL (105 blocks x 10 contiguous orderA cells,
  test/testitems/references/S_D0_panel_blocks.csv, scripts/trackd_panel_select.py), (c) the panel runs under
  real ISIMIP3b climate of 5 models x ssp126/ssp370/ssp585, the two constant-climate controls ctl_obs /
  ctl_mpi370, and the four members m1-m4 incl. the two NEW spin-ups (scripts/trackd_panel.py), or (d) the
  orderA forcing for those models (scripts/trackd_regrid_forcing.sh). Also the traps that cost time while
  building it: the production 2071-2100 Germany config's fix_climate block (acts only after 2100), the
  Feb-2026 build = source b2e5ca9, a snapshot LPJROOT needs include/ for cpp, lpjcheck is built by
  `make utils` not `make main`, an output id may appear only once (daily vs monthly npp), and subset runs
  need CONTIGUOUS cell ranges.
---

# trackd-data — the response-identifying runs of the original model

**What exists and where (raw outputs are scratch; converted tables are durable):**

| part | raw run dirs | what |
|---|---|---|
| Germany re-runs (D2) | `/p/tmp/jamirp/trackD/germany_rh/<GCM>_<scen>_s<seed>/` | 12 members, 2045-2100 from production `restart_2044_nv.lpj`, humidity fixed, all production outputs + `ind` (all heights), restart at 2100 |
| build gate | `/p/tmp/jamirp/trackD/gate/` | Feb-2026 build vs production rows (`explore_de_crerun_gate.py`) |
| panel (D0/D1/D3/D4) | `/p/tmp/jamirp/trackD/panel/m<k>/<leg>/b<NNN>/` | 4 members x (spinup m3/m4, hist, 15 real-climate legs, 2 controls) x 105 blocks |
| forcing | `/p/tmp/jamirp/trackD/forcing/<scen>/` | orderA `.clm`, 5 models x 3 scenarios (MPI ssp126/370 = links to the ground-truth files) |
| binaries | `/p/tmp/jamirp/trackD/cbuild/` | `lpjml_feb2026` (b2e5ca9 + writer switch), `lpjml56fit_snapshot` (panel; PROVENANCE.txt has the md5) |
| durable tables | `/p/projects/open/Jamir/esm_land_emulator_data/trackD/` | parquet conversions + README (owner rule: data in /p/projects, not home) |

**Re-run / extend:**
```bash
python scripts/trackd_germany_rerun.py gate --gcm MPI-ESM1-2-HR --scen ssp245 --seed 1 --submit   # per BUILD
python scripts/trackd_germany_rerun.py d2 --gcm ACCESS-CM2 --scen ssp370 --seed 2 --submit
python scripts/trackd_panel_select.py            # regenerates the panel CSV (fixed seed => identical)
sbatch scripts/trackd_regrid_forcing.sh           # gate: re-derives the MPI ssp370 tas file byte-identically first
python scripts/trackd_panel.py make && python scripts/trackd_panel.py check && python scripts/trackd_panel.py submit
python scripts/trackd_panel.py status
```
A Germany member's build is READ from its production logs (`Version 5.6.004 (Feb  5 2026)` = ssp245 =
`lpjml_feb2026`; `Dec 17 2025` = everything else = line X's `lpjml_dec2025`) — never assume it.

**Traps (each cost a round trip):**
- The production `lpjml_2100_*` Germany config also sets `fix_climate` with `fix_climate_year 2100`; in
  `iterate.c` that applies only to `year > fix_climate_year`, so 2071-2100 are plain transient years and the
  only defect is the missing `"relative_humidity": true`. The 2045-2070 config (humidity on, no fix_climate,
  `ind` commented out) is the right template; re-running 2045-2100 in one go also fills the 2045-2070 tree gap.
- The same `fix_climate` mechanism IS the constant-climate control: `fix_climate_year 2019`,
  `fix_climate_interval [1990,2019]`, `fix_climate_shuffle true` (CO2 is then taken at 2019 = 409.63 ppm with
  the const file — identical to the scenario legs). The log line reads `fix climate after year 2019 shuffling
  years 1990-2019`.
- `make main` builds only `bin/lpjml`; `lpjcheck` needs `make utils` (same CPATH shim as build.sh).
- A copied LPJROOT needs `include/` as well as `par/` and the root `*.js`: `par/soil_20m.js` does
  `#include "../include/soilpar.h"` and cpp fails with ERROR228/ERROR001 otherwise.
- An output `id` may appear once per config: daily legs carry daily `npp` and drop the monthly one.
- LPJmL runs a CONTIGUOUS `startgrid..endgrid` only, so the panel unit is a 10-cell east-west strip (orderA
  is south->north bands, west->east inside a band). Panel results are a separate realisation from the global
  truth (ADR 0041): compare panel legs only with panel legs.
- Members 1/2 legs start from the GLOBAL restart_2019; members 3/4 from their own panel spin-up -> hist chain.
- `ERROR230: First year output is written=-1 ...` in a spin-up log is the benign output-year adjustment.
- LPJ_IND_TRUE_GPP=1 makes the `ind` `gpp` column REAL gross GPP (in the ground truth it is a copy of `npp`,
  ADR 0130); LPJ_IND_ALL_HEIGHTS=1 adds trees <= 5 m (filter `Height > 5` for the production format).
