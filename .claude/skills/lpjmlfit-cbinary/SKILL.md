---
name: lpjmlfit-cbinary
description: Build/run the LPJmL-FIT C binary (the numerical-regression oracle + daily data generator) on the PIK cluster — exact module set (json-c 0.13.1 not 0.17), restart-from-spinup subset runs, config-only daily output, lpjcheck pre-flight, SLURM templates, and the individual=true dead-code check. Use whenever running the C oracle, generating daily data, or reasoning about what the FIT config actually executes. ALSO how to REBUILD the binary (target is `make main` not `lpjml`; a new source file needs three edits incl. src/lpj/Makefile; `-Werror`; the json_object_iterator.h shim on CPATH) and the gate you MUST run afterwards — a rebuild changes the reference basis every F-vs-C number is measured against, two builds are never byte-identical (getbuild.c stamps a date), and `cmp` on a NetCDF calls 20 of 21 outputs different for identical physics because LPJmL writes a timestamp into `history`; use scripts/diagnose_cbinary_rebuild_equality.py on DECODED variables with a matched cell set and --ntasks. ALSO the opt-in rung-2 demography hooks (patches/lpjmlfit_rung2_hook_v3.patch, ADR 0061 + 0120 + 0121) — BOTH the OBSERVATION half (LPJ_RUNG2_DIR: the THREE-phase pre/mort/post roster dump, what it carries that the `ind` output cannot — water_stress, temp_stress, bm_inc_counter, bm_inc, nind, the carbon pools — plus the cell-level channels seed / gasdev_iset / seedbank checksums; that recruits enter at age 0; that neither run wrapper emits `ind` or exports the variable) and the SUBSTITUTION half (LPJ_RUNG2_APPLY_DIR: the K/R/MORT_C/ESTAB_C wire protocol, run an arm with scripts/run_rung2_replay_arm.sh, MODE=record to re-record the baseline after a rebuild, ALWAYS run MODE=none as the null control first, and the replay floor to quote: kills 1.000 exact, recruits 0.907, both 1.367). ALSO the theta=1 IDENTITY GATE every rung-2 mortality result depends on (scripts/diagnose_rung2_hazard_identity.jl, ADR 0122): S's ported hazard reproduces the C's own per-individual mort_prob to 1.6e-15 over all 9 951 tree-patch-years, why mort_npp needed the two v4 dump columns bm_delta/leafarea_real (post-allocation, and turnover_ind is NOT reconstructable from the pools), and the trap that follows — the rendezvous carries LAST year's growth outcome, which keeps the ordering (Spearman 0.900) but INVERTS the sign of the wood-density selection differential, and the culprit is bm_inc_counter, not the growth lag. Carries the traps: READ A KILL SET FROM THE `mort` PHASE, NEVER FROM `post`, because `isdead` has more than one author and fire_tree_ind sets it AFTER the hook point while drawing erand48 only for trees not already dead — replaying fire's victims as demographic kills both claims a death the interface does not own and moves the per-cell random stream; a null control validates the TRANSPORT, not the payload, which is why MODE=none stayed green through that; the kill key is (pft_id, treeidx) not treeidx because tree->index is a PER-PFT counter; a recruit has SEVEN sampled trait axes and only four are substituted; `sapwood_old` is a DEAD FIELD, `cell->treelen_old` is uninitialised because its writer sits behind the dead config->isequal branch and mergesapling() has no caller, and the mort_* columns are uninitialised for any tree not yet through mortality_tree_ind INCLUDING every recruit at its own post — so a consistency check between two readers of one buffer cannot detect uninitialised memory, only two independent runs can; a local named `v` will not compile because discharge.h does #define v; and piping a `module load` runs it in a subshell so the build loses its compiler.
---

# lpjmlfit-cbinary — run the LPJmL-FIT oracle

The C binary is the **oracle** (F_diff must reproduce it — never validate F_diff against itself) and the
daily training-data generator. It is **not** the coupling path (ADR 0014). Source: `/home/jamirp/lpjml56fit`
(v5.6.004); binary `bin/lpjml` (rebuilt to emit daily grass GPP/NPP; pristine backup `bin/lpjml.pre_dgrass.bak`).

## Modules (exact — nothing else)

```bash
source /etc/profile.d/00-modulepath.sh; source /etc/profile.d/modules.sh   # non-interactive shells
module purge
module load intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 netcdf-c curl/8.4.0 expat/2.5.0
```

**json-c 0.13.1, NOT 0.17.** The login default auto-loads `json-c/0.17` (→ `libjson-c.so.5`) which
**aborts**; the binary needs `libjson-c.so.4` from 0.13.1. A source rebuild also needs a local
`json_object_iterator.h` shim on `CPATH` (this cluster's 0.13.1 headers are truncated).

## Pre-flight (validate without running)

```bash
cd <run_output_dir>       # relative output/ paths resolve here
/home/jamirp/lpjml56fit/bin/lpjcheck -DFROM_RESTART <config.js>
```
Checks parse + input/restart headers + disk estimate.

## Subset run from the full-grid restart

- Set integer **0-based POSITIONAL** `"startgrid"/"endgrid"` = grid-file row indices (not lat/lon, not
  1-based, not `"all"`). Per-cell seek is MPI-decomposition-independent; needs byte-identical grid/soil/
  input + matching physics config.
- **Hainich (DE-Hai) = global orderA index `42490`** (lat 51.25/lon 10.25). `28008` is Hainich only in
  the repo `-DSINGLESITE` grid (= Sonoran desert in the global grid).
- `restart_1999.lpj` = spin-up end → use for the Historical 2000–2019 daily re-run. `restart_2019.lpj` =
  historical end → only the SSP370 continuation.

## Daily output = config-only (never recompile for it)

Put `"timestep":"daily"` inside each output entry's `"file"` object; keep the `ind` tree table **annual**.

## SLURM helpers (run off the login node)

- `scripts/run_daily_subset.sh` — **env-var driven** (not positional): `STARTGRID`, `ENDGRID`, `SCENARIO`,
  `NTASKS`, `TIME`, `EXCLUSIVE`, `RUNTAG`, `SUBMIT`, `RANDOM_SEED`, optional `FIRSTYEAR`/`LASTYEAR`. Generates
  config from the production sections, runs `lpjcheck`, submits. Output → `/p/tmp/jamirp/esm_land_daily`. Now
  emits annual `lai_stand`/`fpc_stand` (the runtime-consistent S `lai` feature, replacing the proxy) alongside
  the daily water/carbon block.
  - **`SCENARIO=historic`** (default): obsclim GSWP3-W5E5, `restart_1999.lpj`, 2000–2019, VARYING TRENDY v12 CO2.
  - **`SCENARIO=ssp370`**: MPI-ESM1-2-HR ssp370 forcing (`ssp370/{tas,pr,rsds,lwnet,huss}_..._2015-2100_orderA.clm`),
    `restart_2019.lpj`, 2020–2100, **CONSTANT 409.63 ppm CO2** (2019 value held flat — the `with_nitrogen="no"`
    constant-CO2 regime, DEVELOPMENT_PLAN §3). Byte-consistent with the annual `ind_ssp370_seed1` run
    (`.../ssp370/ground_truth/.../transient_2020_2100_npatch25_random_seed1`). Full-global ≈ **768 GB**, ~2–3 h
    on 2048 tasks. Example: `SCENARIO=ssp370 STARTGRID=0 ENDGRID=67419 NTASKS=2048 EXCLUSIVE=yes TIME=08:00:00 RUNTAG=global SUBMIT=yes bash scripts/run_daily_subset.sh`.
- `scripts/run_fdiff_validation_cell.sh` — single-cell daily re-run adding daily FAPAR/NV_LAI + annual FPC/LAI_STAND (~9 s).
- `scripts/run_fdiff_grass_gpp_cell.sh` — single cell 2000–2019 daily grass GPP.
- `scripts/water_closure_check.py <run_dir>` — dask-lazy water closure verify.
- Keep the `.jl`/`.sh` and `--output` on shared `/p` (never `/tmp/claude-*`).

## Judging a finished run — and the two traps that make a GOOD run look bad

Never judge a C run from SLURM state (the stock jcf always exits 0). Require
`lpjml successfully terminated, <ncell> grid cells processed.` in the log. Two follow-on traps
(ADR 0043, both cost real time):

- **After resubmitting a run, re-point every chained child's log path.** A resubmitted run writes a
  **new** `lpjml_<newjobid>.out`, so a child jcf pinning the old id reads the cancelled attempt's
  **0-byte corpse** — and since an empty log cannot be distinguished from an unfinished one, the child
  reports `no completion line at all` for a run that finished cleanly. Symptom to recognise: a chained
  gate that **fails in ~1 second with most of its data checks passing**, and grandchildren left
  `DependencyNeverSatisfied`. Prefer
  `scripts/diagnose_ind_seed_independence.py --log-dir <run_dir>` (resolves the newest **non-empty**
  `lpjml_*.out`) over naming a job id; an empty log is a provenance FATAL, not a physics verdict.
- **A file-level `cmp` on a NetCDF output is the WRONG equality test.** LPJmL writes a `history`
  attribute holding a wall-clock timestamp + the config path, so runs with identical physics differ in
  the header (the cross-build gate's `vegc` differed by 124 B at byte 172 while **all seven** variables
  hashed identically). Compare **decoded variables** (`netCDF4` + SHA-256 per variable), or the
  timestamp-free text outputs (`globalflux`, `ind`).

**Binary/config equivalence must be a matched-decomposition full-grid run** — a subset re-run cannot
answer it (ADR 0041: the decomposition confound exceeds the signal). The positive control is recorded in
ADR 0043: a faithful full-grid 2048-task re-run reproduced the ssp370 seed1 truth bit-for-bit, including
the 193 GB `ind` roster.

## Closure = the run itself

`-DSAFE` `check_fluxes.c` aborts a cell if `|balanceW| > 1.5 mm/yr` — **a clean run IS water closure.**
`swc` is FRACTIONAL saturation (no `wsats` output ⇒ absolute mm not reconstructable); `swe`/`rootmoist` are mm.

## Before porting any C routine as "the faithful fix"

This config runs `"individual":true`, `with_nitrogen="no"`, `landusetype=NATURAL`, carbon-only. **Many C
paths are gated `if(!config->individual)` or are diagnostic-only — confirm the routine actually executes**
(grep `config->individual` / `config->with_nitrogen` / `nitrogen_coupled` guards) before trusting it.
Known dead paths in this config: `light()`/`light_grass()` (grass cover/light competition — active
reduction is `reduce_grass`, fpc-only); per-PFT `gp_pft`/`gc_pft` into GPP (diagnostic; GPP uses stand-mean
`gp_stand`). Active param file is `par/pft_lpjmlfit.js` (beech = ANGIO allometry), NOT `par/pft.js`.
`-DPERMUTE` is active ⇒ daily PFT-depletion order is randomized (non-deterministic / order-averaged), which
is why a faithful per-PFT competitive-supply port is neither differentiable nor deterministic.

## REBUILDING the binary — the exact recipe, and the gate you MUST run afterwards (ADR 0061)

Nothing was gating C rebuilds until 2026-08-10, and the oracle binary is what every F-vs-C number on the
project is measured against. **A rebuild is a change to the reference basis (guardrail 7). Gate it.**

```bash
cd /home/jamirp/lpjml56fit
source /etc/profile.d/00-modulepath.sh; source /etc/profile.d/modules.sh
module purge; module load intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 \
       netcdf-c curl/8.4.0 expat/2.5.0
export CPATH="$PWD/json_compat:$CPATH"      # the local json_object_iterator.h shim
make main                                   # target is `main`, NOT `lpjml`; ~1 min incremental
```

Adding a **new source file** needs three edits: the `.c` under `src/lpj/`, its header under `include/`,
and `<name>.$O` appended to the object list in `src/lpj/Makefile`. The build is `-Werror`, so a warning is
a failure; and `include/errmsg.h` has no `OPEN_OUTPUT_ERR` — pick an existing code.

**Then the gate — a run comparison, because two builds are never byte-identical** (`getbuild.c` stamps a
build date). Re-run one cell with the new binary and compare against a run the previous binary made with
the *same config, same cell set and same `--ntasks`* (ADR 0041: a differently-decomposed run is a different
trajectory, so a mismatch would be unattributable):

```bash
RUNTAG=<line>_rebuild_gate SUBMIT=yes bash scripts/run_fdiff_validation_cell.sh   # ~7 s, cell 42490
python scripts/diagnose_cbinary_rebuild_equality.py --ref <old_run>/output --new <new_run>/output
```

⚠ **Do NOT judge this with `cmp`.** LPJmL writes a wall-clock timestamp + the config path into every
NetCDF's `history` attribute, so `cmp` calls **20 of 21 outputs different** for two runs with identical
physics (ADR 0043). The script hashes **decoded variables** instead and compares the text outputs
byte-for-byte. Measured on the 2026-08-10 rebuild: 138 variables + `globalflux` identical, 0 differ.

## The rung-2 demography hook (opt-in; inert by default) — ADR 0061

**Use `patches/lpjmlfit_rung2_hook_v4.patch`** — it carries BOTH halves (observation + substitution) and
supersedes `..._v3.patch`, `..._v2.patch` and `patches/lpjmlfit_rung2_demography_hook.patch`, which are kept
only for the provenance of the binaries ADR 0121 / 0120 / 0061 gated. The observation half adds `include/rung2hook.h` +
`src/lpj/rung2_hook.c` and three call sites in `annual_natural.c`. **Activated only by
`export LPJ_RUNG2_DIR=<dir>`**; unset, every entry point returns immediately (this is what makes the
shipped `bin/lpjml` still the oracle). It writes `<dir>/roster_rank%04d.txt` with three self-describing
record kinds (`#H` header lines in the file):

* `P` — patch context (`npatch`, `patcharea`, `fpar_leafon_grass`, `treelen`, live trees, `aprec`) **plus
  the three channels of cell-level state no per-tree record can carry** (ADR 0121): `seed` = the per-cell
  RAND48 stream position, `gasdev_iset` = the parity of `gasdev()`'s **process-global** spare-deviate cache
  (not even per-cell — normals are drawn in pairs and the spare is returned from a file-local static, so an
  odd number of intervening calls shifts every later trait diffusion), and `sb_agb`/`sb_trait`/`sb_year`/
  `sb_id` = checksums of the seedbank `cell->treelist` contents. Score two runs on these with
  `scripts/diagnose_rung2_cellstate_equality.py` — it prints the onset patch-year in full, which is what
  turns "same state, different answer" from a claim into a measurement.
* `T` — one line per tree, **51** fields (v4 added `bm_delta`/`leafarea_real`), at **THREE** phases: **`pre`** = before turnover/allocation/mortality,
  **`mort`** = after the demographic hazards and **BEFORE FIRE** (added by ADR 0121 — read the kill set
  here, see the fire trap below), **`post`** = the C's own answer after establishment
* `G` — one line per grass PFT

It carries what `ind` cannot: `water_stress`, `temp_stress`, `bm_inc_counter` (the accumulators three of
the four death rates read), `bm_inc`, `nind`, all seven carbon pools, `crownarea`, `boleht`, `fapar`, and
since v4 **`bm_delta` + `leafarea_real`** — the two post-allocation inputs of `mort_npp`.

### The θ=1 identity gate — run it before quoting ANY rung-2 mortality result (ADR 0122)

```bash
julia --project=. scripts/diagnose_rung2_hazard_identity.jl [--dump DIR] [--csv PATH] [--fixture PATH]
```
Scores line S's ported hazard (`src/trait_mortality.jl`) against the C's OWN per-individual `mort_prob` from
a recorded dump — no LPJmL run needed. **Result: an identity, max relative Δ 1.6e-15 over all 9 951
tree-patch-years**, all four hazards, the capped total and both hard kills, PFT ids 1–6. Locked into CI by
`test/testitems/m_rung2_hazard_identity_tests.jl` + a 333-record fixture, so the port cannot regress silently.

⚠ **`mort_npp` NEEDED A SCHEMA CHANGE, and the reason generalises: an interface's inputs are DATED.** The
rendezvous is the `pre` phase at the TOP of the annual block, but the C's hazard runs AFTER `turnover_tree`
and `allocation_tree`. So `mort_age`/`mort_water`/`mort_temp` have every input present unchanged at the
rendezvous (`water_stress`/`temp_stress` differ in **0 of 9 951** records between the `pre` and `mort`
phases), while `mort_npp` needs `bm_delta = bm_inc.carbon/nind − turnover_ind.carbon` and
`leafarea_real = ind.leaf.carbon·sla`, both post-allocation. **Do not try to reconstruct `bm_delta`** — only
the two sapwood turnover terms are recoverable (they equal Δ`heartwood_c` between the phases, which also
pins `turnover.sapwood = 0.04`); `turn.leaf`/`turn.root` are daily accumulators, `isphen` is not dumped, and
`turnover_tree` **mutates** `bm_inc.carbon` (reproduction cost, `cmass_excess`, debt payback) before
allocation mutates it again. Dump the two doubles instead.
**The cheap tell for any question of this shape: diff the same field between two dump phases of the same
tree-year.** `water_stress`/`temp_stress` 0 of 9 951 · `bm_inc_counter` 2 169 · `leaf_c`/`bm_inc_c` all.

⚠ **THE RENDEZVOUS IS ONE YEAR STALE, AND FOR THE TRAIT QUESTION THAT INVERTS THE ANSWER (ADR 0122 §4).**
Live, the `pre` roster carries LAST year's `bm_delta`/`leafarea_real`/`bm_inc_counter`. Per-tree ORDERING
survives it (per-patch-year Spearman ρ vs the C's own hazard: median **0.900**), but the one-year
wood-density selection differential does not — the C **+17 729** gC/m³ vs the lagged basis **−14 528**,
**ratio −0.819, opposite sign**. Attributed one term at a time: hard kills suppressed −0.819 (not them),
only `bm_delta`/`leafarea` lagged **+1.001** (harmless), only `bm_inc_counter` lagged **−0.562** ⇒ **it is
the counter**, because it MULTIPLIES `mort_npp` and `mort_water` by `(1+counter)` (`mortality_tree_ind.c:71-81`
updates it from THIS year's `bm_delta` sign, so the rendezvous has the previous value in 21.8 % of records).
⇒ **an emulator arm is scorable on counts and ordering, NOT on the trait response, until the rendezvous moves
behind the growth loop.** This is the harness's rendezvous point, not a defect in the ported operator and not
a property of the standalone emulator (there the fast core grows the trees before the demography runs).

⚠ **A NEW DUMP COLUMN THAT THE EXTERNAL DEMOGRAPHY WILL READ MUST BE INITIALISED ON BOTH TREE-CREATION
PATHS** — `new_tree.c` (establishment) **and** `fread_tree.c` (restart). The `mort_*` columns get away with
being uninitialised because only the dump reads them; a column the harness feeds to an operator would hand a
recruit a random hazard. Adding a field to `Pfttree` does **not** break the restart file, because
`fwrite_tree`/`fread_tree` serialize field by field — just leave it out of their lists. Before the
initialisers were added, `diagnose_rung2_dump_equality.py` returned a **false FAIL** ("DIFFERENT model
state", 695–705 `pre` + 259–317 `post` records) on an arm whose roster was identical in every year and whose
cell state agreed in all 1 500 patch-years.

Gotchas, each paid for once:

* ⚠ **TWO columns of the dump are UNINITIALISED MEMORY. Never read them** (ADR 0120, which corrects the
  narrower ADR-0061 version of this):
  * **`sapwood_old` is a DEAD FIELD** — `Pfttree.sapwood_old` is declared in `include/tree.h` and is
    **never written or read anywhere in LPJmL-FIT**, and `new_tree` does not zero it. Garbage at BOTH
    phases, in EVERY year.
  * **`mort_prob`/`mort_npp`/`mort_age`/`mort_water`/`mort_temp` are garbage for any tree that has not
    yet been through `mortality_tree_ind`** — every tree at the first `pre` after a restart (a
    `6.9e-310` denormal), **and every RECRUIT at the `post` of its own establishment year**, because
    `establishmentpft_ind` runs after mortality and `new_tree` does not zero them. So "valid at `post`"
    holds only for trees that were already alive that year.
  * **Why ADR 0061's gate could not find either:** it compared the dump against the run's own `ind`
    table, and both readers read the SAME struct memory, so they agree on the garbage too. **A
    consistency check between two readers of one buffer cannot detect uninitialised memory — only a
    comparison of two independent RUNS can.** Use `scripts/diagnose_rung2_dump_equality.py`, which
    separates the uninitialised columns from real state and is the right check after any rebuild or
    any change to the writer.
  * ⚠ **A THIRD field is uninitialised, and it is cell-level: `cell->treelen_old` / `treelist_old`**
    (ADR 0121). Sole writer is `getsapling.c:57-58` behind `if(config->isequal)`, and `isequalcoord`
    returns TRUE only when **every cell in the run shares identical coordinates** (hardwired FALSE for
    `nall == 1`) — so the branch is dead, **`mergesapling()` has no caller anywhere in `src/`**, and the
    field is garbage (read 29 458 000 against a `treelen` of 19 650). It is deliberately NOT dumped. The
    generalisable check: before dumping any field, find its writer and confirm the writer's guard is live
    in `individual=true` — the same "is this path executed?" discipline as porting C physics.
* ⚠ **`isdead` HAS MORE THAN ONE AUTHOR, AND ONE OF THEM IS DOWNSTREAM OF THE HOOK — read a kill set from
  the `mort` phase, NEVER from `post`** (ADR 0121; this cost the whole ADR-0120 replay floor).
  `src/tree/annual_tree.c` sets it from the demographic hazards (`mortality_tree_ind`, the allocation kill,
  the bioclimatic `!survive`, the cut year) — that is what the hook sees and owns. But
  **`src/tree/fire_tree_ind.c:33` also sets it**, from `firepft` at `annual_natural.c:129-135`, i.e. AFTER
  the decision point and before the `post` dump. So "any `post` row with `isdead == 1`" silently includes
  fire's victims, and replaying those is wrong twice over: it claims a death the narrow interface does not
  own, **and it moves the per-cell random stream**, because
  `if(!tree->isdead && erand48(cell->seed) < ...)` draws **only for trees not already dead** — pre-killing
  fire's victim changes how many draws fire consumes, so fire then kills a different tree. Symptom: the
  arm's `pre` roster is identical in every column including the seed, and its `post` differs, in the first
  patch-year that applies any kill. Reading kills from `mort` instead turned the `kills` arm from 1.37×
  denser at 20 years into an **exact** reproduction.
* **Recruits appear at `post` with `age == 0`** — `annual_tree` does the `age++`, so they first read as age
  1 the following year. Dead trees stay in the patch list with `isdead = 1` and are gone by the next `pre`.
  Accounting closes exactly: `post`-alive of year *N* == `pre` of year *N+1*.
* **`run_fdiff_validation_cell.sh` and `run_daily_subset.sh` emit no `ind` table.** To cross-check the dump
  you must add `{ "id" : "ind", "file" : { "fmt" : "txt", "name" : "output/ind_<y0>_<y1>.csv" }}` to the
  generated `lpjml.js` by hand.
* Neither wrapper exports the variable either — generate with `SUBMIT=no`, insert
  `export LPJ_RUNG2_DIR=...` into the generated `slurm.jcf`, then `sbatch` it.
* Verify the dump with `scripts/diagnose_rung2_roster_vs_ind.py` (post + stems >5 m must reproduce the
  run's own `ind` table: identical tree sets, all 21 shared columns to ≤5e-6 — `ind`'s `%g` gives only six
  significant digits, so a tolerance below ~1e-5 is meaningless).

## The rung-2 SUBSTITUTION hook (the read-back half) — ADR 0120

`export LPJ_RUNG2_APPLY_DIR=<dir>` (independent of `LPJ_RUNG2_DIR`; both unset ⇒ stock binary). Per
patch-year the C writes `req_r<rank>_y<year>_p<patch>.txt` (+ a `.ready` marker) holding the `pre`
roster in the SAME format as the dump, spin-waits for `rsp_....ready`, then reads:

```
K <pft_id> <treeidx>                              kill this tree
R <pft_id> <sla> <wooddens> <D95max> <minwscal>   one recruit
MORT_C | ESTAB_C                                  defer that half back to the C
END
```

Any roster tree not named by a `K` lives; the `R` lines are the COMPLETE tree recruit set. The C writes
`audit_r<rank>.txt` recording what it actually did. `LPJ_RUNG2_APPLY_TIMEOUT` (default 600 s) makes a
hung harness fail loudly instead of hanging the job.

Run an arm with `scripts/run_rung2_replay_arm.sh` (`MODE=kills|recruits|both|none|record`), which generates
the jcf, starts the harness in the background of the same job, and runs lpjml. Score with
`scripts/diagnose_rung2_replay_identity.py` (roster identity + terminal ratio),
`scripts/diagnose_rung2_dump_equality.py` (per-tree columns) and
`scripts/diagnose_rung2_cellstate_equality.py` (the cell-level channels).

**`MODE=record` re-records the baseline dump with no substitution at all, and a REBUILD makes that
mandatory:** the recorded dump is the reference basis every arm is scored against, so a rebuild that adds
or removes a dump column leaves the two sides on different schemas. Re-record first, then re-run the arm. Current baseline: `/p/tmp/jamirp/M_rung2/M_rung2rec_v4b_dump`.

**The replay floor, and it is one cell** (42490, 25 patches, 2000–2019, terminal stems replay ÷ recorded;
ADR 0121 supersedes ADR 0120's numbers): `none` **1.000** · `kills` **1.000, exact — identical in every
initialised per-tree column and every cell-state column, no year differs** · `recruits` **0.907** · `both`
**1.367**. So a substituted mortality operator can be credited with any difference it makes; a substituted
establishment operator cannot be credited below 0.907, which is structural (the C's Poisson and inheritance
draws are skipped and only 4 of 7 trait axes are substituted).

Six things that will bite:

* **The kill key is `(pft_id, treeidx)`, NOT `treeidx` alone.** `tree->index` is a **per-PFT** counter
  (`new_tree.c`: `tree->index = treepar->index++`, `treepar = pft->par->data`), so two trees of different
  PFTs in one patch can collide. The hook asserts uniqueness per patch-year and dies rather than
  mis-attributing a kill.
* **A recruit has SEVEN sampled trait axes, not four.** `new_tree` draws `sla`, `wooddens`, `D95max`,
  `minwscal`, `emax`, `k_root`, `beta_2` and derives leaf `longevity` from `sla`. The hook substitutes
  the four the Component-S copula supplies, re-derives `beta_root` from the new `D95max` and `longevity`
  from the new `sla` (as `new_tree` does), and leaves `emax`/`k_root`/`beta_2` on the C's own draw. **Say
  "4 of 7 axes" in any result.**
* **A kill the C's own state cannot un-make wins over a "live" verdict** — the `allocation_tree` kill,
  the cut year, `!survive`, `isneg_tree` — and is counted (`n_forced_dead`). Reviving such a tree would
  break carbon, because `litter_update` is called inline the moment `annualpft` returns TRUE.
* ⚠ **A NULL CONTROL VALIDATES THE TRANSPORT, NOT THE PAYLOAD.** `MODE=none` defers both halves, so it
  never serves the kill list — which is why it stayed green while the kill list itself was mis-specified
  (the fire trap above). Green null control + diverging arm ⇒ suspect what you are FEEDING the interface
  before you suspect the interface.
* **ALWAYS run `MODE=none` first as the null control.** Rendezvous active, both halves deferred: it must
  reproduce the recorded run in every initialised column. That is what separates "the harness perturbs
  the run" from a real result.
* **Naive ID replay is upward-biased once a trajectory has ALREADY parted** — but only then, and ADR 0121
  narrowed this claim a lot. Recorded kills that name trees which no longer exist go unserved while the
  recruit list replays in full, so the stand under-thins: `recruits` alone is 0.907, and adding the
  **exactly faithful** kills half on top gives 1.367. It is a consequence of the other half diverging, not
  a property of ID replay itself — with only the kills half substituted the replay is exact. (ADR 0120's
  `kills` 1.37× / `both` 1.30× were measured on the broken `post`-phase kill list; do not quote them.)

⚠ **A single-letter local named `v` will not compile anywhere in this tree** — `include/discharge.h`
does `#define v 86400.0`, so the compiler sees a numeric literal and reports a baffling
`too many arguments to function call, expected 1`. The same applies to any other short name that
collides with a macro in the transitively included headers.

⚠ **`module load ... | tail` runs the shell FUNCTION in a subshell, so the environment never reaches
`make`** — the build then fails with `mpiicx: No such file or directory`. Never pipe or redirect a
`module` command in a build script.
