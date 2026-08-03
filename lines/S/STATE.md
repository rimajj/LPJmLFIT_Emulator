# LINE S — Component-S science (branch `line/S`, worktree `wt-S`)

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/S/JOURNAL.md` (append-only). Decisions: ADR block **0030–0049**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here

**TWO TRACKS are open on line S. Two sessions ran CONCURRENTLY in this worktree on 2026-08-03 (an ADR-0028
violation — see Track B's note), so both handoffs are preserved here rather than one overwriting the other.**

- **Track A — the ssp370 second seed (ADR 0041).** TIME-CRITICAL: a 2048-task C run and two chained
  `afterok` jobs are in flight. Collect these first; a dead parent silently cancels its children.
- **Track B — the address null and blocked CV (ADR 0040).** Six pooled eval rungs in flight, two more to
  resubmit. The decision rule is PRE-REGISTERED and must not be rewritten after the results are read.

### TRACK A — the ssp370 second seed is finally running for real (ADR 0041)


**The ssp370 second seed is finally RUNNING for real. `random_seed` is INERT under `FROM_RESTART` —
a second seed is a second SPIN-UP.** That single fact is why every earlier attempt produced a
byte-copy of seed1. **ADR 0041** is the record. Read it before touching any seed/restart config.

**State at the end of the 2026-08-03 session — code MERGED, data NOT YET PRODUCED.** Code+docs merged to
`main` at **`20db6057`**, and `main`'s OWN CI is green on all six real gates (`docs`, `format`, `python`,
`test (lts)`, `test (1)`, `test (macOS, lts)`); only the allowed-to-fail `test (pre)` is red, for the
documented Julia-prerelease churn. The CI-faithful suite ran green independently on SLURM —
**107 394 pass / 0 fail / 4 broken, 98/98 items** (job 1678641) — which is what established the Julia
verdict, because the two concurrent sessions' pushes kept **cancelling** each other's GitHub Julia runs
(`cancelled`, not `failure`; don't read those as a break).
**But `1678574` had NOT started: it sat `QOSGrpCpuLimit` for the whole session.** qos=short's group
allowance is 18 000 CPUs and the partition was saturated (187 nodes running, six of them this worktree's
own Track-B rungs), so a 2048-CPU job had nothing to fit into. Nothing is wrong with it — **do not
"fix" it by lowering `--ntasks`**: 2048 is what the seed1 member used, and a changed decomposition
changes the trajectory (see the subset-replica finding below), which would destroy the very comparison
this member exists for. `qos=medium`/`long` have *smaller* group limits (12 000 / 6 000), so `short` is
already the right queue. Just let it schedule and collect the chain.

#### The bug, in one line

The old `transient_2020_2100_npatch25_random_seed2` set `"random_seed": 2` but restarted from the
**historic seed1** `restart_2019.lpj`. With `"new_seed": false` the per-cell RAND48 seeds come from
the restart file (`newgrid.c:507-513` → `freadcell.c:37`) and the `setseed` that would apply
`seed_start` is gated off (`newgrid.c:520-521`); `seed_start` is applied once at parse time
(`fscanconfig.c:231`) then overwritten from the restart header (`openrestart.c:139-140`). **And the
log says `Reading random seeds from restart file.`, never `Random seed: 2`** — so nothing warned.
Both `ind_2020_2100.csv` are 193 097 583 638 B with md5-identical sampled windows. A floor from it
gives `floor_r ≡ 1` = fabricated headroom. That directory now carries
`INVALID_NOT_A_SECOND_SEED.md`; ~326 GB there is reclaimable (nothing derived was built from it).

#### What is in flight — jobs to collect

| job | what | depends on |
|---|---|---|
| **1678574** | `S-FIT_ssp370_seed2` — the corrected member, 2048 tasks / 16 nodes, `qos=short`, 3:30 | — (was `QOSGrpCpuLimit`) |
| **1678595** | `S-ssp2-indep` — independence gate (must NOT be a copy) | `afterok:1678574` |
| **1678596** | `S-indparq-ssp2` — → `/p/tmp/jamirp/emulator_global/ind_ssp370_seed2_all.parquet` (~92 GB) | `afterok:1678595` |
| **1678579/1678580/1678592** | `S-bineq-A`/`-B`/`-cmp` — subset gate | **DONE — verdict VOID (exit 3), see below** |
| **1678607** | `S-crossbuild-gate` — the REPLACEMENT gate: full grid, 2048 tasks, seed1 inputs, Jul-21 binary | — |

Run dir: `.../ssp370/ground_truth/model_output/transient_2020_2100_npatch25_random_seed2_from_hist_seed2/`
Logs: `logs/S-*.<jobid>.out`; the C run's own log is `<run>/lpjml_2020_2100.1678574.out`.

**`afterok` means a dead parent leaves the children cancelled — a missing parquet may mean the C run
died, not that nothing was scheduled.** Check `sacct -j 1678574,1678595,1678596 --format=JobID,JobName%20,State,ExitCode,Elapsed`.

**Judge the C run from its LOG, never from SLURM state.** The stock job file ended `rc=0` + bare
`exit`, so it always exited 0 — a run dying mid-century leaves a plausible truncated 193 GB CSV
behind a green `sacct` row. I fixed it to `rc=$?` / `exit $rc`, but still require
`lpjml successfully terminated, 67420 grid cells processed.` Then: `ind_2020_2100.csv` within a few
percent of 193 097 583 638 B and **NOT exactly equal** to it (exact equality ⇒ the fix failed);
`restart/restart_2100.lpj` ≈ 1.34e11 B; `python scripts/water_closure_check.py <run_dir>`.
If it dies 0:53 / no log / 20× slow, that is the known flaky-node mode — resubmit with
`SBATCH_EXCLUDE=<node>`, do not re-debug the config.

#### The provenance is FOUR edits, not three — say all four when citing it

`restart_filename` → historic **seed2** restart (the fix) · the run directory · `random_seed` 1→2
(inert, documentary) · **the `co2` input path**. That last one was forced: the seed1 config reads
`/home/jamirp/scripts/clustering/climclusterpy_package/global_co2_ann_1700_2019_const_2100.txt`,
which **no longer exists** (that dir was repurposed for an unrelated project on 2026-07-28) —
`lpjcheck` failed `ERROR100`. Recovered and installed at
`/p/projects/waldspektrum/priesner/clustering/global/global_co2_ann_1700_2019_const_2100.txt`,
**md5 `ed5699b9c92d4d25857889f644b153db`**, 5212 B, 401 years. Identity proven four ways: the git
blob (its only version, spanning the Jul-15 run); a filesystem snapshot with **mtime 2026-07-07**,
predating the run; byte-exact reconstruction from TRENDY v12 (1700–2019 verbatim, then 2019 flat);
and agreement with ADR 0004's 409.63 ppm. **So the forcing is identical and the seed is the only
physical difference.** Per ADR 0004 these are `ssp370 climate, CO2 constant at 409.63 ppm from 2020`.
Line M / anyone re-running seed1 should know **the seed1 config as committed is unrunnable** until
its `input_2020_2100.js:23` is repointed at the `/p` copy (documentation-only; do not rerun seed1).

#### ⚠ NEW, AND IT INVALIDATES A CLASS OF VALIDATION: a subset re-run is NOT a per-cell replica

Measured at cell 42490 with the **same binary, same restart, same forcing**, varying only the cell set:

| run | cell set | `ind` rows for 42490 | first year ≠ global truth | years matching truth |
|---|---|---|---|---|
| A | 42490 alone | 18 530 | **2021** (first step) | 2 / 81 |
| B | 42480–42500 (21 cells) | 19 366 | **2035** | 16 / 81 (2020–2034 contiguous) |
| truth | all 67 420 @ 2048 tasks | 18 790 | — | — |

B is **bit-identical for 15 consecutive years** then diverges; A diverges immediately; at 2020 A and B
already differ in exactly `fpc_ind` and `isdead`. This is a stochastic gap model amplifying a tiny
perturbation — one individual dying/establishing differently makes the roster permanently different.
**The RNG is not the cause** (fully per-cell: `permute` takes `stand->cell->seed`, no `drand48()` anywhere
in `src/`, `config->seed` read only at `iterate.c:108/148/181`, all unreachable at
`nspinup:0`/`fix_climate:false`). **Mechanism UNESTABLISHED — do not claim one.**

Consequences: (a) CLAUDE.md §3's "per-cell seek is MPI-decomposition-independent" is true of the *seek*,
**false of the evolution** — the recorded ~1.6e-4 `whc_nat` discrepancy is this same effect through a
smoother variable; (b) **a seed pair is valid only at the same binary AND the same `--ntasks`** (seed2
satisfies the second by construction, `--ntasks=2048` copied from seed1); (c) **any single-cell re-run
scored against GLOBAL ground truth is comparing two different trajectories** — this bears directly on
line M's per-cell oracle work and the `fdiff-validate` skill. **Raise it with M** (that skill is M-owned;
the fact is in CLAUDE.md §3, which is shared).

#### THE ONE OPEN QUESTION — the cross-build gate (now job 1678607)

The seed1 member came from the **`Feb  5 2026`** build; the current `bin/lpjml` is **`Jul 21 2026`**.
That is **not** just the committed `patches/lpjmlfit_daily_grass_gpp.patch` — it is also a
**RHEL8→RHEL9 toolchain rebuild** (GCC 8.5.0→11.5.0, GLIBC_2.14→2.33/2.34, `__xstat`→`stat`,
`DT_NEEDED libjson-c.so.4`→unversioned). Two things are settled by reading, and are solid:

* **the patch is inert here** — for a 5-of-421-output run `initoutput.c:50-67` allocates a leading
  `maxsize` **trash** region and sets `outputmap[i]=0` for unopened outputs (real outputs at
  `index>=maxsize`), `outputsize(D_GRASS_*)==1` so `maxsize`/`totalsize` are unchanged ⇒ the
  unconditional `getoutput(output,D_GRASS_GPP,…)+=` writes only to trash, no RNG draw, no state;
* **no physics par drifted** — `find -newermt 2026-07-15` over `src/ include/ par/` returns exactly
  the patch's four files; `param_lpjmlfit.js`, `par/{lpjparam_fit,soil_20m,pft_lpjmlfit,manage_*}.js`
  and `Makefile.inc` (hence `-DPERMUTE`/`-DSAFE`) all predate the seed1 run. Only
  `par/outputvars.js` changed, by the same patch's two rows, matched to `NOUT 421`.

Neither is an empirical proof. The **subset** gate (A/B/cmp above) came back **VOID, exit 3** — the
decomposition confound is larger than the binary signal, so a subset re-run can never settle this.
It is replaced by **job 1678607**, the only design that can: full grid `"startgrid":"all"`, **2048
tasks**, the same 5-output set, the same forcing, restarting from the **historic seed1**
`restart_2019.lpj` with `random_seed 1` — a faithful re-run of the seed1 member itself, differing only
in `write_restart:false` (written after the last year ⇒ cannot affect the trajectory). Config +
job file in `/p/tmp/jamirp/S_crossbuild_gate/`.

**To collect it:** compare against the seed1 ground truth
* `output/globalflux_2020_2100.csv` (10.5 KB, 81-year GLOBAL aggregate — extremely sensitive: a sum
  over 67 420 cells) — `cmp` / `diff` it directly;
* `output/vegc_2020_2100.nc` (65 MB, per-cell annual vegetation carbon) — per-cell array equality.
Bit-identity on both ⇒ the builds are poolable and the seed is the only difference. A mismatch ⇒ the
RHEL8→RHEL9 rebuild moved the trajectory; fall back to `git checkout -- include/conf.h
par/outputvars.js src/lpj/daily_natural.c src/lpj/fwriteoutput.c` (restoring the matched 419/419 pair)
and re-running the member with `bin/lpjml.pre_dgrass.bak`, the actual producing binary.
The `ind` CSV that gate writes (193 GB in `/p/tmp/jamirp/S_crossbuild_gate/output/`) exists **only** so
the output set stays byte-identical to the producing run — it is not compared; **delete it** after.

**A mismatch does not invalidate the new seed2 member** — it is still a genuine second realization. It
invalidates *pooling it with seed1 as a pure seed pair*.

#### Then, in priority order

1. **An ssp370 seed2 parquet is NECESSARY BUT NOT SUFFICIENT for ADR-0030 criteria 1 and 4 on the
   pooled basis.** The pooled seed1 tables were built with `STEM_CAP=400` while ADR 0030 Decision 1
   requires the cap OFF for a floor, and the cap's rank key is
   `pl.struct(['Cell','Patch','Year']).hash(seed=seed)` (`build_slow_runtime_table.py:381`) ⇒ a
   `SEED=2` build keeps a **different set of whole patch-year clusters**, deflating the floor and
   flattering the emulator. Either rebuild both sides uncapped or state the deviation next to the
   criterion. Do not quote a pooled criterion 1/4 number without resolving this.
2. **The pooled seed2 copula tables**, then the floor: steps 1–3 of `run_pooled_slow_copula.sh`
   (`SCENARIO=historic SEED=2` and `SCENARIO=ssp370 SEED=2`, `BOUNDARY_WINDOW=20`,
   `STRUCT_AXES=agb,Height`) → `pool_slow_tables.py` → `noise_floor_vs_emulator.py` with
   `COPULA_DIR=/p/tmp/jamirp/emulator_global/capacity/pooled-env-qrf-b6x2M`,
   `COPULA2_DIR=.../slow_copula_pooled_w20_t8_seed2`, `SKIP_PARQUET=1`.
   These orchestrators DO take `DEPENDENCY=afterok:<jid>` as an env knob (the `sbatch_*.sh` wrappers
   do not) — chain them on **1678596**.
3. **STILL THE GATE ON PRODUCTION — and ANOTHER SESSION IS ALREADY RUNNING IT (2026-08-03 ~12:05–12:20).**
   A concurrent line-S session was active in this worktree while the seed2 work was committed: it holds
   uncommitted edits to `scripts/{eval_slow_copula,blocked_cv_folds_probe}.jl`,
   `scripts/{build_slow_copula_env_augment,build_slow_spatial_controls,diagnose_slow_neighbour_skill}.py`,
   `scripts/diagnose_copula_capacity.sh` and an untracked `scripts/diagnose_slow_address_prereg.py`, and it
   submitted `S-aug-{geo,perm,geo2}` + `S-cap-p{8,14}-{hash,blk15-buf5}-*` (jobs 1678605–1678616). **Its work
   is NOT in commit `66fb0149`** — I staged only my own files, so nothing of theirs was buried. Two things to
   know: (i) it also **bulk-renumbered every `ADR 0039` reference in the working tree to `ADR 0040`**, which is
   why my ADR took the free number **0041** — commit `01e6e248` reserves 0039 by in-code reference for the
   blocked-CV work and never wrote the file, so 0039/0040 are theirs to settle; (ii) that sweep rewrote the
   ADR reference *inside a section I had just written*, so **check the numbers in `slow-drf-pipeline` before
   trusting them**. This violates ADR 0028's one-session-per-line rule — reconcile before assuming either
   handoff is complete. Their jobs also share our `qos=short` group limit, which is why 1678574/1678607 sat
   `QOSGrpCpuLimit`.
   The remaining substance, unchanged: re-score
   `env-qrf-b6x2M` with contiguous lat/lon block folds instead of `mod(hash(cell), k)`
   (`eval_slow_copula.jl:143`), plus a lat/lon-only conditioning control. The six env columns have
   median within-cell sd **exactly 0 for 100 % of cells**, so they are a per-cell spatial ADDRESS,
   not a climate response; a 1-NN lookup on them reaches Wooddens r = 0.800 with the nearest
   training neighbour 1.00° away. By-cell folds leave the neighbours in the training set, so they
   score interpolation, not transfer. **Do not promote to M before this runs.**
   `recruit_copula_global_historic_t9.rcop` is the **historic-STATIC** artifact and the S2 evidence;
   it is NOT line M's production copula (M pins the **transient** `pooled_w20` basis, ADR 0027).
4. **A per-cell env sidecar** — no runtime plumbing supplies the six env values per cell; a caller
   hand-builds them from `cell_year_feats.parquet`, unreachable from CI and basis-sensitive. S emits
   `cell_env.parquet`; M folds it into `M_cells.csv`. Until it exists the 14-column artifact is not
   coupled-runnable outside a bespoke script.
5. **Depth is NOT exhausted at the production config** (t9, job 1648259): 33 449–46 036 leaves/tree
   but 52.3–67.0 % of stored values still depth-capped. One `6 x 2M, d32` rung settles whether the
   0.8696 asymptote moves. Depth is free in bytes.
6. **Re-run the shipped rung with `TRAIT_ONLY=0`** — `agb`/`Height` were trimmed out of 11 of 12
   rungs including the shipped one, and they carry the tightest margins (agb pooled KS 0.0116 vs the
   0.02 bound). "S2 met" must not be read as "biomass and size unchanged".
7. **The composed coupled path is still unexercised**: emulator + 14-col copula + `qrf=true` +
   establishment + carbon closure over a multi-year run. Construction is gated; the run is not.
8. **Carried (ADR 0036 §6):** emit `Year` in the `MODE=copula` table so the stand-biomass composite
   is computable on matched rows — blocks figures 12/13 for the POOLED pair. It is a table SCHEMA
   change ⇒ do it when a new generation is being built anyway, never as a standalone rebuild of a
   validated table (ADR 0036 §5b streaming key-set nondeterminism lands a rebuild on a different row
   universe). Related, don't re-derive: `STEM_CAP` is a patch-year **CLUSTER** subsample, not
   per-stem, which is why ssp370's basis spread is ~10× looser.

#### OPEN INTEGRATION POINT with line M (raise it before any re-pin)

`scripts/extract_cell_slow_init.py:142-146` checks `cond_cols[-4:] == BOUNDARY_COLS`. A 14-column
artifact fails that **by construction** — its last four are the env tail — so M's re-pin step
`sys.exit`s. The correct check is **positional**, `cond_cols[4:8]`. **That file is M-owned; S
requests, M lands.**

#### New reusable scripts (use them; do not re-derive)

- `scripts/build_slow_ind_parquet.py` — `ind_*.csv` → parquet, `SRC`/`OUT` positional. The only
  previous builder is the FROZEN sibling's `global_extract.py`, whose `--which` is argparse-locked to
  three hard-coded names, so a new scenario/seed **could not be named at all**. Keeps the load-bearing
  `schema_overrides` (polars infers `Wooddens` integer from the first rows) and asserts the frozen
  29-column `IND_COLUMNS`.
- `scripts/diagnose_ind_seed_independence.py` — run this on EVERY new ground-truth member before
  deriving anything. Equal file size to the sibling is the copy signature.
- `scripts/diagnose_ind_binary_equality.py` — per-cell bit-equality vs the global truth **with a
  decomposition control**. Use it whenever ground truth from two different builds would be pooled.

#### Traps found this session (do not re-derive)

- **`random_seed` is inert under `FROM_RESTART` and INVISIBLE in the log.** The whole of ADR 0041.
  A future "seed 3" made by bumping `random_seed` alone would fail the same silent way.
- **A "ground truth" input path can rot underneath a committed config.** The ssp370 co2 file vanished
  when an unrelated project reused its directory; the seed1 config has been unrunnable since
  2026-07-28 and nothing noticed. Recovery route worth remembering: `git log --all --diff-filter=D`
  in the repurposed repo, plus `/home/jamirp/.snapshot/{hourly,daily,weekly}.*` (mtimes are preserved,
  which is what let me prove the file predated the run).
- **`git status` in `/home/jamirp/lpjml56fit` holds UNTRACKED `param_lpjmlfit_newseedpool.js` and
  `par/lpjparam_fit_newseedpool.js` with `k_est_inherit` 0.02 → 2e-13 (11 orders of magnitude).**
  Nothing references them today, but `#include "param_lpjmlfit.js"` is the cpp QUOTE form, so a stray
  copy in any `scripts_for_running_the_model/` would silently shadow LPJROOT's and change the physics
  with no visible config diff.
- **CLAUDE.md §1's `par/param_lpjmlfit.js` does not exist** — the file is
  `/home/jamirp/lpjml56fit/param_lpjmlfit.js` (LPJROOT root, found via `-I$LPJROOT`). Fixed in §1.
- **CLAUDE.md §3's "json-c 0.17 aborts" applies to the Feb-5 build only.** The Jul-21 build imports
  *versioned* `JSONC_0.14` symbols, which 0.13.1, 0.17 and the system `libjson-c.so.5` all provide;
  `lpjcheck` exits 0 under both. The real bare-env failure is `libnetcdf.so.19` / `libudunits2.so.0`
  not found. Pin the documented module set **inside the job file** for that reason — the stock
  ground-truth jcfs pin nothing and inherit the submitting shell.
- **`bin/lpjml.pre_dgrass.bak` is not a drop-in** while the working tree is patched: it was built
  with `NOUT=419` and the live `par/outputvars.js` declares 421 (`ERROR232`/`ERROR201`).

**Not S's to chase:** `water_stress` (6.6× band) is line M's F core, ADR 0029. `fpc`'s residual is
dynamics (ADR 0035 §3.3).

### TRACK B — the address null was measured on the wrong basis (ADR 0040)


**ADR 0038's decision rule for the address question was WRONG, and it is now corrected and PRE-REGISTERED.
ADR 0040 is the record.** The rule said *"decays toward the 1-NN level (r≈0.80) ⇒ it is an address"*. But
0.80 is a pure address's skill under **hash** folds; the fold-mode-matched null under `block(15°,5°)` is
**0.140 / 0.210** (two colourings). The rule was wrong by ~0.63 in r **in the direction that would have
declared a strong response an address** — guardrail 7's reference-basis error, which ADR 0033 records this
line making twice before. Note `0039` was taken by a CONCURRENT line-S session (ssp370 seed2), so this is 0040.

#### The pre-registration (zero new compute, frozen BEFORE any forest log is read)

1-NN surrogate, per-cell medians, 57 719 pooled cells, fold designs **read from the Julia code the forests
run** (`mod(hash(tile),k)` is not reproducible in Python). Wooddens:

| fold design | `geo` = **NULL** | `env6` | `dyn7` | `both` | `DELTA` |
|---|---|---|---|---|---|
| `hash` (published) | **0.8369** | 0.8114 | 0.7992 | 0.8773 | **+0.0781** |
| `block(15,5)` s0 | **0.1400** | 0.5947 | 0.6069 | 0.6833 | **+0.0764** |
| `block(15,5)` s1 | **0.2102** | 0.5934 | 0.6280 | 0.6856 | **+0.0576** |

⇒ **The env tuple retains 73 % of its hash skill under blocking; a pure address retains 21 %.** The
conditioning DELTA is ~invariant (86 % retained). **The screen therefore PREDICTS the forests will find the
gain survives blocking** — if they do not, something other than information content is at work in the forest
and that is the finding. Rule, decided in advance (ADR 0040 §5): RESPONSE if `Δ_blocked ≥ 0.5·Δ_hash` AND
blocked `p14geo` ≪ blocked `p14env`; ADDRESS if `Δ_blocked → 0` or the two coincide; **NOT RESOLVABLE if the
two salts disagree by > 0.5·Δ_blocked** (the `geo` null's own salt spread is already 0.07).

#### THE BIGGER FINDING — the gate metric is nearly blind to what production needs

`emu_r` is a **level** statistic and `sd(Δobs)/sd(level)` is only **0.198–0.306**, so it is 3–5× more
sensitive to spatial interpolation than to the warming response a coupled run turns on. Measured from
EXISTING predictions (`--mode response`, 52 450 cells, tile-cluster bootstrap):

| axis | `Rr` = r(Δpred,Δobs) | ceiling | `Ra` | `Rb` = mean Δpred − Δobs | mean Δobs |
|---|---|---|---|---|---|
| SLA | +0.4389 | 0.958 | 1.017 | +1.32e−4 [+1.08e−4,+1.55e−4] | −5.31e−4 |
| **Wooddens** | **+0.4146** | **0.920** | **0.869** | **−892 [−1022,−756]** | **+2433** |
| D95max | +0.2424 | 0.871 | 0.954 | +0.565 [−0.113,+1.262] | +5.08 |
| minwscal | +0.6232 | 0.947 | 1.010 | +1.38e−3 [+1.13e−3,+1.62e−3] | +3.48e−3 |

**The shipped artifact damps the Wooddens warming shift by 37 %** (CI excludes 0), and the transient PATTERN
is only 24–62 % of ceiling on every axis — a large, previously unmeasured gap. **But the available comparison
arm is 4-lever confounded** (`slow_copula_pooled_w20_t8`'s in-place preds are 40×50k/d14/QRF0/mtry3, NOT
60-tree as STATE.md used to say — the 60 is `train_slow_copula.jl`'s setting printed later in the same log).
It reads `Rb` = **+263 [+92,+432]**, i.e. mildly amplified. So *"the env tail causes the damping"* is NOT
established — that is exactly what `p8-hash-mtry4` settles.

#### DO THIS FIRST — collect the in-flight matrix (submitted, pooled, ~1.4 h each)

`squeue -u $USER | grep S-cap-` · logs `logs/S-cap-<tag>.<jobid>.out`, last line `=== JOB DONE ... ===`.
Each is `6×2M/d22/min_leaf20/QRF=1/KFOLDS=5/TRAIT_ONLY=1`; blocked rungs are `BLOCK_DEG=15 BUFFER_DEG=5`.
`[3/3]` auto-routes to `score_slow_copula_dispersion.py` because the source is pooled.

| job | tag | table | ncond | fold | mtry |
|---|---|---|---|---|---|
| 1678608 | `p8-hash-mtry4` | `..._t8` | 8 | hash | **4** |
| 1678610 | `p14perm-hash` | `..._t8perm` | 14 | hash | 4 |
| 1678611 | `p8-blk15-buf5-mtry4` | `..._t8` | 8 | block s0 | **4** |
| 1678612 | `p14env-blk15-buf5` | `..._t8env` | 14 | block s0 | 4 |
| 1678637 | `p14geo-hash` | `..._t8geo` | 14 | hash | 4 |
| 1678638 | `p14geo-blk15-buf5` | `..._t8geo` | 14 | block s0 | 4 |

All six are submitted; the queue is `QOSGrpCpuLimit`-bound so expect them to start staggered.
**The two `p14geo` rungs were CANCELLED and RESUBMITTED** after `S-aug-geo2` (job 1678616, exit 0) rebuilt
`slow_copula_pooled_w20_t8geo` (`env_tail_tag geo_position_v2`, columns 0-7 re-verified bitwise-identical over
all 42 227 077 rows): the first geo basis was rank-degenerate (`geo_abs_lat` vs `geo_cos_lat` Spearman **−1.000000** — `cos` is
monotone in `|lat|`, so an axis-aligned tree saw ONE feature and the control was silently 5-D while declaring
`ncond=14`, biasing the experiment toward its own hypothesis). Sixth column is now `geo_x = cos(lat)cos(lon)`
and the builder GATES the basis (max |ρ| 0.954). The template for any further rung (note `CAPTAG` MUST encode the fold scheme, and the new guard REFUSES a
non-empty shadow dir unless `FORCE=1` — that guard already caught these two resubmissions):
```bash
B=/p/tmp/jamirp/emulator_global; COMMON="EVAL_NTREES=6 EVAL_SUBSAMPLE=2000000 MAX_DEPTH=22 MIN_LEAF=20 KFOLDS=5 QRF=1 TRAIT_ONLY=1 NCPUS=64 TIME=06:00:00"
env $COMMON CAPTAG=<tbl>-blk15-buf5-s1 SRC=$B/slow_copula_pooled_w20_<tbl> MTRY=<0|4> FOLD_MODE=block \
  BLOCK_DEG=15 BUFFER_DEG=5 BLOCK_SALT=1 CELL_LATLON=$B/tables/cell_latlon.txt scripts/diagnose_copula_capacity.sh
```

#### Then, in priority order

1. **The salt replicate pair** — `BLOCK_SALT=1` for `p8` and `p14env` at `block(15,5)`. One colouring is one
   draw and the "NOT RESOLVABLE" branch of the rule cannot be evaluated without it. `CAPTAG` must encode the
   salt (the shadow dir is wiped unconditionally; a reused CAPTAG destroys the earlier rung).
2. **A TRANSIENT env tail is the constructive fix, and nothing else can be.** The six columns are a
   2000–2019 climatology applied to every year INCLUDING ssp370 rows, so they cannot carry a response by
   construction. Apply ADR 0026's `BOUNDARY_WINDOW` treatment to them (a per-(Cell,Year) join instead of a
   per-Cell mean — the augment script's `ENV_PARQUET` seam already accepts it) and re-score BOTH gates.
   This is the thing that would actually let M pin a 14-column artifact.
3. **Test whether the damping is `mtry` dilution rather than the env columns.** At `(p=8, mtry=4)` a split
   considers ≥1 of the 4 time-varying flux drivers with probability **0.986**; at `(p=14, mtry=4)` only
   **0.790**. So the static tail dilutes the ONLY channel through which time enters (`co2` is dead, ADR 0004).
   One `p14env hash MTRY=7` rung (matched FRACTION) discriminates the two.
4. **ADR 0038's saturation fit and its "0.889 needs 1052× the table" claim are UNRESOLVED, not established**
   — they rest on +0.002/+0.003 `emu_r` increments against a spatial-sampling sd of order 0.01, and there is
   NO seed replication anywhere in the ladder (`seed = a` is hard-wired, at `ntrees = 6`). Do not build on
   them. Adding a `SEED_BASE` knob is ~5 lines in an S-owned file.
5. Carried from ADR 0038, unchanged: the per-cell env **sidecar** (`cell_env.parquet`) is still missing, so
   the 14-column artifact is not coupled-runnable outside a bespoke script · the `6×2M d32` depth rung ·
   `TRAIT_ONLY=0` on the shipped rung (`agb`/`Height` carry the tightest margins) · the composed coupled path
   is still unexercised · emit `Year` in the `MODE=copula` table (schema change ⇒ ride a new generation).

#### ⚠ A CONCURRENT LINE-S SESSION IS/WAS RUNNING IN THIS WORKTREE

Jobs `1678574 S-FIT_ssp370_seed2` → `1678595 S-ssp2-indep` → `1678596 S-indparq-ssp2` (chained `afterok`) and
`1678607 S-crossbuild-gate` were submitted from `/p/projects/open/Jamir/wt-S` at 11:55–12:02 on 2026-08-03,
by a session other than the one that wrote this block, together with `docs/decisions/0039-*`,
`changelog.d/S-ssp370-second-seed-spinup.md`, `scripts/build_slow_ind_parquet.py` and
`scripts/diagnose_ind_{binary_equality,seed_independence}.py`. That violates ADR 0028's one-session-per-line
rule and is the exact hazard worktrees exist to prevent. **This session committed ONLY its own files, by
explicit path — never `git add -A`.** Do the same, and check `git status` before any commit.

#### Traps found this session (do not re-derive)

- **`mod(hash(cell), kfolds)` folds give the neighbour-distance analysis NO leverage**: 99.5 % of test cells
  have a training cell within **0.75°** (q99 0.61°, median 0.41°). The far bins hold 12–117 cells and their
  deltas flip sign. The zero-compute stratification cannot substitute for a refit — it is what PROVES the
  refit is necessary (`scripts/diagnose_slow_neighbour_skill.py`).
- **The six env columns' east-neighbour correlation is 0.9595–0.9986** — near-perfect spatial redundancy
  between adjacent cells. That is why the address hypothesis was credible in the first place.
- **`BUFFER_DEG=0` does not remove the mechanism under test.** The block PERIMETER keeps adjacency: at
  `B=15`, 10.9 % of test cells still sit 0.5° from training data and 24.2 % within 1.0°.
- **`CAPTAG` is the ONLY thing separating two rungs** and `diagnose_copula_capacity.sh` wipes its shadow dir
  unconditionally — run concurrently it deletes the other job's input symlinks mid-flight, which the
  SRC-only leak guard cannot see. Now refused on a non-empty shadow / a same-tag `squeue` entry.
  `capacity/{,pooled-}env-qrf-b6x2M` are copied read-only to `capacity/frozen-*`: they were the ONLY
  prediction sets behind ADR 0038's numbers.
- **On a POOLED source, `noise_floor_vs_emulator.py` silently scores an intersection** — `SRC2` defaults to
  the HISTORIC seed2 and `percell_table` inner-joins on `Cell`. The driver now branches automatically.
- **A per-Cell `ENV_PARQUET` makes the augment script's `group_by("Cell").mean()` the IDENTITY**, so its
  duplicate-`Cell` guard becomes vacuous and a duplicated row would be silently AVERAGED into a tuple
  present in neither marginal. Gated on the input now.
- **Runic normalizes float literals**: `q(0.10)` → `q(0.1)`, `1e-9` → `1.0e-9`. The gate is repo-wide.

**Not S's to chase:** `water_stress` (6.6× band) is line M's F core, ADR 0029. `fpc`'s residual is dynamics
(ADR 0035 §3.3).


## Scope + ownership (ADR 0029)

**You own (exclusive):**
- `src/components/slow.jl`, `src/drf.jl`, `src/climbuf.jl`
- `scripts/*slow*`, `scripts/flux_ood_experiment.jl`, `scripts/diagnose_*`, `scripts/noise_floor_vs_emulator.py`
- `test/testitems/{slow_*,drf_*,recruit_copula_*,climbuf_*,carbon_ledger_*}`
- `lines/S/*`, `changelog.d/S-*.md`, ADRs 0030–0049

**Do NOT touch:** `src/run.jl`, `src/interface.jl` (line M owns the coupling seam) ·
`src/components/energy.jl` (line E) · `ext/` (line O) · `Project.toml` (integrator).
Shared, additive-only: `src/LPJmLFITEmulator.jl` (inside the `# ── line S ──` region), `CLAUDE.md`, `MEMORY.md`.

**SLURM tag prefix:** `S-` · **scratch:** write under `/p/tmp/jamirp/...` paths you created; other lines'
artifacts are **read-only**.

## The contract you must not silently break (S → M)

Line M runs your emulator inside the coupled loop. **Frozen:** `FluxDrivenSlowEmulator(fc, forest; …)` kwargs ·
the `flux_feature_vector` column order · the `live_flux_cond` subset (ADR 0025) · the `.drf`/`.rcop` format
(ADR 0023) · the `cell_meta.parquet` schema.
Train/inference consistency is load-bearing (ADR 0023), so **a conditioning change is by definition a
both-sides change**: write the ADR, bump a version in the artifact meta (never mutate an artifact in place),
and coordinate an integration point with M. Never re-point M's pinned artifact path from this line.

## Status (2026-07-28)

- **P1 is DONE**: the flux-driven S runs in the coupled loop, carbon-conserving to ~1e-12 gC (ADR 0018→0027).
- **The tree-PFT truncation is FIXED in code (ADR 0031, S1b).** `TREE_TYPES` now lives in ONE place
  (`lpjmlfit_emulator.data`) and `features.py` / `config.yaml` / all four `build_slow_*.py` /
  `noise_floor_vs_emulator.py` **import** it. The `growth_eff` `÷max(lai,EPS)` shift is fixed to the runtime
  rule (`fast.jl:369`) with a `GROWTH_EFF_MAX` assertion. Per-PFT mortality params are all seven `[VERIFIED]`.
  The **global re-derivation on the `t7` generation is IN FLIGHT** — see §NEXT for the job table.
- **⚠ EVERY global S number below with a "tree5" label is on the TRUNCATED population** (ids 1–5) and is
  superseded by its `t7` counterpart, not silently restated (ADR 0031 §5).
- *S1b `t7` job provenance (logs are in this worktree's `logs/`):* `1622131` historic copula + its chained
  ADR-0030 gate `1622436` · `1622337` pooled copula at `NCPUS=96` after `1622330` OOM-killed at 32 (exit 137) ·
  `1622134` pooled count DRF · `1622242` historic count + `1622305` its K-fold · `1622132` seed2 floor table.
  *S1c:* `1622718` regeneration + byte-identity gate · `1622724` after / `1622727` before re-measurement ·
  `1622741` + `1622792` (post-rebase) suite · `1622811` the gate re-run that returned **`PASS` (exit 0)** on the
  committed fixtures — S1c's binary success signal, so a `STALE-FIXTURE` exit 2 is now a NEW finding, not the
  expected state.
  *S1d cross-line:* line O's ADR 0082 §4 reached the SAME porosity-vs-WHC insight independently, online —
  and was calibrating against the RETIRED `swc` table (its quoted `mean 0.5075 / q50 0.4635` is exactly
  `cell_year_soilmoist_hist.parquet`). Notified in `lines/O/STATE.md` O3b. The two distributions have
  near-equal means (0.5075 vs **0.4780**) and completely different SHAPE — new: q10 **0.0000**, q25 0.0000,
  q50 0.4980, q75 0.8770, q90 0.9999. **A quarter of global cell-years have a fully dry root zone at year
  end**, which also answers whether a year-end reading is degenerate: it is not, globally (it saturates
  only at wet-winter cells like Hainich).
  *S1d:* `1622917` the root-zone soilmoist deriver (global, 1 348 400 rows) · `1622921` regeneration +
  drift control (`FAIL`/exit 1 = the CORRECT verdict — the edit is SUPPOSED to move the table here) ·
  `1622923` the gate-band re-measurement · `1622924` suite **107 076 pass / 0 fail / 4 broken**.
- **The committed Hainich demo artifacts are on ONE feature basis (S1c DONE, ADR 0032 closed → ADR 0034).**
  The `.rcop` + meta and both `hainich_slow_oracle_*.csv` regenerated **byte-identical**; only the count `.drf`
  + `_meta.txt` moved. The `.rcop`'s conditioning row is now inside the `.drf`'s trained band on **8/8** shared
  columns (0 violations), boundary tails equal. Suite **107 065 pass / 0 fail / 4 broken** (job 1622741).

  | Hainich gate quantity | assertion | proxy-basis `.drf` | **real-basis `.drf`** |
  |---|---|---|---|
  | Gate-3 Height `nqrmse` | ≤ 0.45 → **0.40** | 0.3895 | **0.2998** |
  | median Height ratio | 0.6 … 1.6 | 1.2463 | **1.1316** |
  | settled count ratio | 0.25 … 4.0 | 0.6734 | **1.2808** |
  | `target_history` band | 0.5…40 → meta `y`-band | 6.62 … 9.72 | 12.28 … 13.64 |
  | DIRECT draws SLA / Wooddens | ≤ 0.22 / ≤ 0.12 | 0.1274 / 0.0346 | **unchanged** (`.rcop` identical) |
  | coupled community SLA / Wooddens | ≤ 0.45 | 0.2558 / 0.2203 | 0.2634 / 0.2203 |

  Mechanism, one cause for all three headline moves: in-domain `bm_inc_cell`/`growth_eff` raise the settled
  count 6.8 → 12.9 stems/patch, and more stems on the same carbon are smaller trees ⇒ Height moves *down*
  toward the C truth. Re-measure with `scripts/measure_hainich_gate_bands_probe.jl` (`DRF_ART=` for a BEFORE
  column; it reproduced the documented 0.39/1.25/0.67 exactly, which is what validated the harness).
- **The demo emulator is runtime-consistent on 14 of 15 columns (S1d DONE, ADR 0035). The one remaining
  out-of-band column, `water_stress`, is LINE M's.** ADR 0034's four-column shift is closed on both S-owned
  causes — and neither was the cause ADR 0034 named (§S1d below). Measured job 1622923:

  | column | runtime | trained band | S1c excursion | **S1d** | cause / owner |
  |---|---|---|---|---|---|
  | `water_stress` | 0.323 … 0.331 | [0, 0.0432] | 6.6× | **6.60×** (unchanged) | F_diff vs the C — **line M** |
  | `soilmoist` | 0.9962 … 0.9968 | [0.7908, 1.0000] | 5.1× | **IN** | was the wrong VARIABLE — CLOSED |
  | `lai` | 3.63 … 5.12 | [0.7766, 4.7809] | 2.9× | **0.021×** (12-yr) / 0.086× (20-yr) | per-patch basis — CLOSED |
  | `fpc` | 0.607 … 0.791 | [0.1548, 0.7414] | 0.03× | 0.084× | never a basis error — DYNAMICS, see below |

  The pinned set in `slow_production_drf_tests.jl` is now **`Set(["water_stress"])`** alone, plus new bounds
  asserting `soilmoist` exactly inside and `lai`/`fpc` ≤ 0.2 band widths. **`fpc` is not S1d debt:** it was
  already `min(Σ fpc_ind, 1)` per-patch on both sides, so its residual is the coupled patch settling denser
  than the training upper tail — a dynamics outcome no basis fix can close. **Why the old gate never saw any
  of this is a proof, not a caveat:** a DRF prediction is a convex combination of training leaf means, so
  "predicted targets are inside the training band" can never fail — it is artifact integrity, not
  conditioning. Check the INPUT side.
- **S1d re-measurement (`[VERIFIED 2026-07-28]`, jobs 1622921 regeneration / 1622923 bands / 1622924 suite).**
  Both committed demo artifacts moved, regenerated TOGETHER from one table build; both oracle CSVs unchanged.
  The regeneration control confirms **only** `soilmoist`, `lai` and `growth_eff` (via its `lai` divisor)
  moved — every other column and the target `n_living` are byte-identical.

  | Hainich gate quantity | assertion | S1c | **S1d** |
  |---|---|---|---|
  | Gate-3 Height `nqrmse` | ≤ 0.40 | 0.2998 | **0.2990** |
  | median Height ratio | 0.6 … 1.6 | 1.1316 | 1.1547 |
  | settled count ratio | 0.25 … 4.0 | 1.2808 | **1.1597** |
  | `target_history` band | meta `y`-band [3, 19] | 12.28 … 13.64 | 11.66 … 12.52 |
  | DIRECT draws SLA / Wooddens | ≤ 0.22→**0.10** / ≤ 0.12→**0.06** | 0.1274 / 0.0346 | **0.0391 / 0.0273** |
  | coupled community SLA / Wooddens | ≤ 0.45 | 0.2634 / 0.2203 | unchanged |
  | carbon residual | < 1e-6 | 1.7e-12 | 1.9e-12 |
  | basis-agreement violations | 0 | 0 | **0** |

  **The Height drift did NOT move (0.2998 → 0.2990), and that is a finding:** the remaining Gate-3 residual
  is not a conditioning-basis artifact, so S5 must not budget a basis fix to pay for it. Two thresholds were
  **tightened**, none widened.

### Population widening — measured effect (historic copula table, seed2, `[VERIFIED]` job 1622132)

| | tree5 (pre-0031) | **tree7 (t7)** |
|---|---|---|
| survivor tree stems | 133 562 549 | **197 802 377** (+48 %) |
| cells | 45 072 | **54 058** (+8 986) |
| `minwscal` span | [0.025, **0.30**] | [0.025, **0.75**] — FIT's true range (id 0's interval) |
| `growth_eff` max / mean | 1.19e9 / 264 495 | **43 138 / 146.7** (the guard; seed1 reads 31 183 / 120.6) |

Seed1 equivalents `[VERIFIED]`: historic w20 = **197 721 867 stems / 54 020 cells** (exactly ADR 0031's census),
`growth_eff` max 31 183 with **0** `lai<=0` rows — the cross-seed-join diagnosis confirmed in production.
ssp370 w20 = **828 818 873 stems / 58 683 cells** (this is what OOM-kills a 32-cpu build; use `NCPUS=96`).

### Count DRF — before/after (like-for-like, same script + hyperparameters)

| metric | tree5 | **t7** | Δ | source |
|---|---|---|---|---|
| pooled table rows (historic+ssp370, w20) | 77 636 574 | **121 495 487** | +56 % | |
| pooled cells | 53 993 | **58 587** | +4 594 | |
| pooled held-out-BY-CELL TEST R² | 0.9852 | **0.9818** | −0.0034 | 1597387 → 1622134 |
| pooled in-sample R² | 0.9852 | **0.9819** | −0.0033 | |
| pooled by-cell OOS R² / RMSE | 0.9852 / 0.702 | **0.9819 / 0.707** | −0.0033 | |
| HOLD-OUT-BY-SCENARIO R², held out historic | 0.9847 (RMSE 0.714) | **0.9816** (0.709) | −0.0031 | 1600416 → 1622134 |
| HOLD-OUT-BY-SCENARIO R², held out ssp370 | 0.9847 (RMSE 0.714) | **0.9814** (0.716) | −0.0033 | |
| historic K-fold-by-cell per-row R² / RMSE | 0.9852 / 0.702 | **0.9821 / 0.699** | −0.0031 | 1581897 → 1622305 |
| historic **per-cell-mean R²** / bias | **0.9994** / 0.005 | **0.9987** / **0.001** | −0.0007 | |
| historic cells scored | 44 328 | **53 699** | **+9 371** | the previously-invisible tropical + larch cells |

### Trait POOLED-MARGINAL fidelity — before/after (K-fold-by-cell OOS, historic, `[VERIFIED 2026-07-28]`)

Jobs 1597648 (tree5) → 1622131 (tree7), same script + hyperparameters. `nqrmse = RMSE(q05..q95) / IQR(obs)`,
so it is **spread-normalized** — and the observed IQRs moved, which the headline ratio hides. Both are shown:

| axis | nqrmse tree5 | **nqrmse tree7** | headline | IQR ×  | raw RMSE tree5 → tree7 | **real gain** |
|---|---|---|---|---|---|---|
| SLA | 0.016 | **0.006** | 2.67× | 0.89× | 3.14e-4 → 1.05e-4 | **2.99×** |
| Wooddens | 0.022 | **0.008** | 2.75× | 1.13× | 1771 → 726 | **2.44×** |
| D95max | 0.028 | **0.008** | 3.50× | 1.20× | 7.29 → 2.50 | **2.92×** |
| minwscal | 0.038 | **0.008** | 4.75× | **2.47×** | 2.73e-3 → 1.42e-3 | **1.92×** |

**The improvement is real on every axis (1.9–3.0× in absolute quantile error), but do NOT quote the headline
ratios.** For `minwscal` the 4.75× is mostly its IQR growing 2.47× (the tropical PFT's `[0.05,0.75]` interval
entering the population); the honest number is 1.9×. `SLA` is the opposite case — its IQR *shrank*, so its
headline 2.67× **understates** a real 2.99×.

**This does NOT refute or confirm ADR 0031's degradation prediction.** ADR 0031 predicted that a single pooled
marginal per axis would be a *worse structural fit* once id 0's very different trait intervals were included —
that is a statement about **between-cell composition**, which is what ADR 0030's **per-cell-median** gate
measures. The table above is the **pooled global marginal**, a strictly weaker test that is blind to whether the
right cells got the right traits. The chained job **1622436** is the test of the actual prediction; until it
reports, the trait verdict is OPEN. Plausible reason the marginal improved anyway: 48 % more stems and 20 % more
cells is more training data per marginal DRF, and the truncated set was itself an awkward mixture to fit.

**Counts survive the widening essentially intact:** every count metric moves by ≈ −0.003 R² on a 56 %-larger,
markedly more heterogeneous population (the tropical belt + Siberian larch added), and the unseen-regime
generalization gap stays flat (holdout-by-scenario is within 0.0005 of the by-cell baseline, as before). So the
truncation was **not** materially inflating the count skill — the count DRF's headline claim is robust. The
trait side is where the population change was predicted to bite (ADR 0031), and that is what the in-flight
copula + 0030 re-measurement will show.
- **Trait per-cell medians — RE-MEASURED on `tree7` (`[VERIFIED 2026-07-28]`, ADR 0030 gate, job 1622436).**
  **Gate PASSED: `seed1-basis` = 1.000 on all four axes** (requirement ≥0.99), 52 165 cells scored (was
  36 228). Each population measured against its OWN floor and ceiling, which is what makes the columns
  comparable across a population change (ADR 0030 §4):

  | axis | emu_r | floor (rel_Y) | ceiling | **GAP** | r_center | sd(pred)/sd(Y1) |
  |---|---|---|---|---|---|---|
  | SLA | 0.866 → **0.885** | 0.964 → 0.973 | 0.981 → 0.986 | +0.115 → **+0.101** | 0.883 → **0.898** | 0.946 → 0.911 |
  | Wooddens | **0.567 → 0.807** | 0.694 → 0.937 | 0.794 → 0.965 | +0.226 → **+0.157** | 0.715 → **0.837** | **0.546 → 0.718** |
  | D95max | 0.771 → **0.812** | 0.791 → 0.833 | 0.873 → 0.909 | +0.102 → **+0.098** | 0.883 → **0.893** | 0.732 → 0.742 |
  | minwscal | **0.793 → 0.947** | 0.909 → 0.973 | 0.947 → 0.986 | +0.153 → **+0.039** | 0.838 → **0.960** | **0.736 → 0.970** |

  **ADR 0031's degradation prediction is FALSIFIED — see ADR 0033.** It expected a single pooled marginal to fit
  *worse* once id 0's very different trait intervals entered. Instead per-cell skill improved on **every** axis,
  and **most on the two that were worst**: Wooddens `emu_r` 0.567 → 0.807 and minwscal +0.153 → **+0.039 (near
  ceiling)**. The mechanism: the truncation was *destroying* composition signal, not hiding a need for per-PFT
  structure — the tropical belt is environmentally distinct (hot, wet, frost-free) AND carries id 0's distinct
  intervals, so with it present the environment↔composition link the copula conditions on is much *stronger*.
  So the "missing between-cell composition signal" diagnosis was largely an artifact of the truncated basis.
- Split-half 0.992–0.999 vs a floor of 0.833–0.973 ⇒ the floor remains **trajectory divergence**, not
  finite-stem noise. `rel_P` (0.993–0.999) still exceeds `rel_Y`, so the raw floor−emu gaps stay lower bounds.
- **The cross-population `tree5` row is the truncation's size, not a gap** — its `seed1-basis` reads
  0.976 / 0.556 / 0.814 / **0.174**, i.e. the script's own ≥0.99 guard correctly refuses it. That is the
  mechanism that made the pre-S1 numbers unreadable, now reproduced deliberately as a control.
- Seed2 floor artifact: `/p/tmp/jamirp/emulator_global/slow_copula_historic_seed2` (133 562 549 stems / 45 072
  cells; rebuild in ~70 s).
- Artifacts: `*_pooled_w20.{drf,rcop}` on `/p/tmp` (DVC); the committed `.drf`/`.rcop` are the Hainich demo.
- The online transient boundary (`src/climbuf.jl`, ADR 0027) is BUILT and offline-parity verified.

### `t8` — the GLOBAL generation on the ADR-0035 bases (`[VERIFIED 2026-07-30]`, ADR 0036)

Jobs: `1633248` ssp370 root-zone soilmoist deriver · `1633254`/`1633255` per-scenario count DRFs ·
`1633273` pooled count + scenario holdout · `1633275`/`1633276` count K-fold · `1641319` the STRUCT-axes
byte-identity gate · `1641321`/`1641322`/`1641323` the three copulas · `1641324` pooled count K-fold ·
`1641325` the seed2 companion · `1641372` the ADR-0030 gate · `1642638` the AR-rewrite gate ·
`1642642` the ssp370 rebuild · `1641863` the suite (**107 076 pass / 0 fail / 4 broken**).

**COUNT** — the population is intact and the basis move did not cost skill:

| | historic | ssp370 | pooled (w20 transient) |
|---|---|---|---|
| rows / cells | 22 467 348 / 53 699 | 99 028 310 / 58 496 | 121 495 658 / 58 588 |
| in-sample R² | 0.9827 | 0.9823 | 0.9824 |
| **K-fold-by-cell OOS R² / RMSE** | **0.9826 / 0.689** | **0.9823 / 0.698** | **0.9824 / 0.697** |
| held-out-CELL test R² | — | — | 0.9824 (5 744 cells) |
| hold-out-by-SCENARIO R² | 0.982 (held out historic) | 0.9818 (held out ssp370) | — |
| per-cell-mean R² / bias | 0.9988 / 0.0027 | — | — |

The pooled row count is exactly `22 467 348 + 99 028 310`, i.e. the pooled table always had the CORRECT
ssp370 row set — the streaming defect hit only the per-scenario static build (§NEXT).

**COPULA** — pooled OOS `nqrmse` (4 production traits) and the two diagnostic struct axes:

| scenario | SLA | Wooddens | D95max | minwscal | `agb` [diag] | `Height` [diag] |
|---|---|---|---|---|---|---|
| historic (uncapped, 197 721 867 stems / 54 020 cells) | 0.004 | 0.013 | 0.006 | 0.007 | 0.643 | 0.032 |
| ssp370 (`STEM_CAP=400`, 22 283 459 / 58 683) | 0.006 | 0.018 | 0.006 | 0.005 | 0.752 | 0.028 |
| pooled (`STEM_CAP=400`, 42 227 077 / 58 683) | 0.004 | 0.021 | 0.008 | 0.004 | 0.618 | 0.027 |

**`agb`'s `nqrmse` ≈ 0.6-0.75 is a METRIC ARTEFACT, not a miss** — read its quantiles: historic
`pred [10.15, 22.02, 47.53, 163.0, 2656]` vs `obs [10.30, 22.61, 49.51, 176.3, 2876]`, i.e. every quantile
within **1.5-7.6 %**, and pooled `KS ≈ 0.011`. `nqrmse` divides every quantile error by ONE IQR and per-stem
`agb` has `q95/IQR ≈ 10`. New `median_rel_q_err` reports it directly (**0.025**). Height matches to 0.2-1.2 %.

**ADR-0030 per-cell gate on `t8`** (historic, 52 165 cells, **`seed1-basis` = 1.000 on all six axes ⇒ PASS**):

| axis | emu_r | floor (rel_Y) | ceiling | GAP | r_center | sd(pred)/sd(Y1) |
|---|---|---|---|---|---|---|
| SLA | 0.881 | 0.973 | 0.986 | +0.104 | 0.894 | 0.907 |
| Wooddens | 0.814 | 0.937 | 0.964 | **+0.150** | 0.844 | **0.678** |
| D95max | 0.791 | 0.833 | 0.909 | +0.118 | 0.870 | 0.714 |
| minwscal | 0.945 | 0.973 | 0.986 | +0.041 | 0.958 | 0.970 |
| **`agb` [diag]** | 0.864 | 0.776 | 0.875 | **+0.011** | **0.987** | 0.822 |
| **`Height` [diag]** | 0.954 | 0.939 | 0.967 | **+0.013** | **0.986** | 0.967 |

**The VALIDATION FIGURE SET** (job 1641373 → `figures/emulator_validation/{historic,ssp370,pooled}_t8/`
+ `report_t8.html`; figures are git-ignored, the report inlines them all). Per-cell OOS skill, 6 axes:

| | count per-cell-mean R² | SLA | Wooddens | D95max | minwscal | **`agb`** | **`Height`** |
|---|---|---|---|---|---|---|---|
| historic — per-cell `r` | **0.9988** | 0.880 | 0.812 | 0.789 | 0.944 | **0.864** | **0.954** |
| ssp370 — per-cell `r` | **0.9989** | 0.903 | 0.814 | 0.770 | 0.962 | **0.869** | **0.954** |
| **pooled** — per-cell `r` | **0.9989** | 0.899 | 0.826 | 0.776 | 0.967 | **0.906** | **0.966** |
| pooled — median per-cell KS | — | 0.173 | 0.129 | 0.158 | 0.149 | **0.091** | **0.065** |
| pooled — pooled KS | — | 0.0039 | 0.0065 | 0.0020 | 0.0040 | 0.0099 | 0.0062 |
| pooled — median rel. quantile err | — | 0.0019 | 0.0059 | 0.0029 | 0.0050 | 0.0348 | 0.0048 |

**The two STRUCT axes have the LOWEST per-cell KS of all six** — the emulator reproduces a cell's biomass and
size distribution *better* than its trait distributions, which makes sense: `agb`/`Height` are dynamical
outcomes the flux conditioning speaks to directly, while a trait median is a PFT-composition statistic.

**STAND BIOMASS** (composite: OOS count × OOS per-stem `agb`, vs the C's own per-patch `sum(agb)`):

| | per-cell R² | log₁₀ R² | median pred:obs | basis_ratio | p10 / p90 | cells >10 % off | cells |
|---|---|---|---|---|---|---|---|
| historic | **0.931** | 0.945 | 1.020 | 0.995 | 0.961 / 1.004 | **3.0 %** | 53 699 |
| ssp370 | **0.920** | 0.963 | 1.013 | 0.982 | 0.868 / 1.124 | **30.7 %** | 58 496 |
| pooled | — REFUSED — | | | | | | |

**ssp370's 10× looser basis spread (30.7 % vs 3.0 %) is the `STEM_CAP` CLUSTER subsample showing up, exactly
as predicted** — historic is uncapped, ssp370 caps at 400 stems/cell and the cap keeps whole patch-years, so
its copula factor is over a different row subset than its count factor. The medians still agree (0.982), which
is why `basis_ok` passes; but quote ssp370's biomass number with that spread attached. **Pooled is REFUSED
outright** (its two tables weight the scenarios 81 % vs 53 % ssp370 — ADR 0036 §6).

**The trait axes are within ±0.02 of their `t7` values** (SLA 0.885→0.881, Wooddens 0.807→**0.814**,
D95max 0.812→0.791, minwscal 0.947→0.945) — expected, since `t8` changes the conditioning BASIS, not the
population. **Biomass and size are AT CEILING**: their per-cell medians are as reproducible as the model's own
seed-to-seed irreducibility allows. `agb`'s NEGATIVE raw gap (−0.088) is not a paradox — the emulator carries
no trajectory divergence, so it is *more* stable than one seed; the attenuation-corrected ceiling (0.875) is
the fair comparison and `emu_r` 0.864 sits just under it.

## Milestones

- **S1** Basis-clean noise floor → exact per-axis headroom. **DONE 2026-07-28 (ADR 0030)** — gate met
  (`seed1-basis` 1.000 ×4), headroom table in §Status, and it is what uncovered S1b.
- **S1b** **Widen the training population to FIT's complete tree set (ADR 0031).** Code + gates + docs **DONE
  2026-07-28**; the global re-derivation / re-validation / 0030 re-measurement is **IN FLIGHT** (§NEXT).
  Blocks S2. Side outcomes: the `lai==0` seed asymmetry is diagnosed (cross-seed feature join), all seven PFTs'
  mortality params are `[VERIFIED]` (ids 1/2/4/5 were also wrong, not just the two new ones), and the byte-identity
  gate exists as `scripts/verify_hainich_demo_artifacts.sh` + `scripts/diagnose_slow_table_drift.py`.
- **S1c** **Regenerate the committed Hainich demo `.drf` + `.rcop` onto ONE feature basis (ADR 0032).**
  **DONE 2026-07-28 (→ ADR 0034).** Both rebuilt from one table build; the `.rcop` + meta and both oracle CSVs
  came back byte-identical, only the count `.drf` moved. Basis agreement **8/8 shared columns, 0 violations**.
  Every drift threshold improved and the Gate-3 alarm was **tightened** 0.45 → 0.40 (numbers in §Status). Side
  outcome that became S1d: regenerating the artifact does NOT close the runtime↔training shift — 4 of 15
  columns are still out of band, from three causes, one of which is line M's.
- **S1d** **Put `soilmoist` and `lai` on ONE basis, runtime and training. DONE 2026-07-28 (ADR 0035).**
  Both of ADR 0034's S-owned diagnoses were **wrong**, and re-deriving them against the C source before
  writing the fix is what saved the milestone (`residual-diagnosis` §3):
  - **`soilmoist` was the wrong VARIABLE, not the wrong clock.** Training reduced the C `swc` = total water
    over **saturation** capacity; the runtime fed `state.w` = plant-available water over **WHC**. The
    handoff's "cheap side" (re-reduce `swc` to year-end) would have turned the alarm green over a mismatch.
    Both sides are now `ROOTMOIST / Σ_{l<3} whcs[l]` — root-zone, `whcs`-weighted, YEAR-END (a state, like
    the other seven state columns; the annual water integral is already `water_stress`). New deriver
    `scripts/build_rootmoist_soilmoist_feature.py`; new `root_zone_soilmoist` used at all three `slow.jl`
    sites. **Rejected** the ADR-0034 "clean" runtime annual-mean accumulator: it needs a daily hook in
    `run.jl`, which is line M's, so it would have parked this gate on another line's schedule.
  - **`lai` IS reconstructable per-patch** — the skill and the builder docstring both said it was not.
    `Σ LAI·fpc_ind/(1−exp(−k_pft·LAI))`, patcharea cancels; validated against the C's own crown allometry at
    median rel err **1.8e-8** (`scripts/diagnose_patch_lai_reconstruction.py`). Fixes the `growth_eff`
    divisor with it. **`fpc` needed no change** (already per-patch both sides — ADR 0034 mis-grouped it).
  *Gate met:* `soilmoist` IN band, `lai` 2.9× → 0.021×/0.086×, pinned set = `{water_stress}` alone, two
  thresholds tightened and none widened, suite green. Numbers in §Status; M notified in `lines/M/STATE.md`.
- **S2** **Close the trait headroom.** Expand the copula conditioning — `COPULA_COND_COLS` in
  `scripts/build_slow_runtime_table.py` **and** `live_flux_cond` in `src/components/slow.jl` **in lockstep** —
  with environment / PFT-composition covariates; global K-fold re-fit (`run_pooled_slow_copula.sh`); measure
  against the **re-measured** ADR-0030 gate. **Needs an ADR (0032) + an integration point with M** (artifact
  version bump). *Gate (ADR 0030 §4, replacing "r ≥ 0.75"):* close ≥50 % of the Wooddens GAP to the ceiling
  **and** lift `sd(pred)/sd(Y1)` to ≥0.75 on that axis, with pooled KS not degraded (≤0.02) and no other axis
  losing >0.01 of `r_center`. Report honestly if the conditioning does not deliver.
  **⚠ S1b already delivered a large share of this gate WITHOUT touching the conditioning (ADR 0033):** the
  Wooddens GAP closed 0.226 → 0.157 (**30 % of the way**, target 50 %) and `sd(pred)/sd(Y1)` went 0.546 →
  **0.718** (target ≥0.75 — nearly met), pooled nqrmse improved rather than degraded, and no axis lost
  `r_center`. So **re-baseline the S2 gate against the `tree7` numbers before starting**, or S2 will take credit
  for the population fix. The honest remaining target is the last ~20 % of the Wooddens GAP; minwscal (+0.039)
  and D95max/SLA (+0.098/+0.101, both `r_center` ≈ 0.89) have little left to win.
  **⚠ AND S1d comes first (ADR 0034 §5):** three of the columns S2 would condition on are still on the wrong
  aggregation basis, so an S2 run started now would again be crediting a basis fix — the same trap ADR 0033
  recorded when S1b silently delivered 30 % of this gate.
- **S3** Per-PFT / mixture copula. **DE-PRIORITIZED back to a fallback (ADR 0033 — reverses ADR 0031).** The
  argument for promoting it was that the copula predicted only 0.55 of the true between-cell Wooddens spread and
  had no composition covariate. On the complete population that dispersion ratio is **0.718** and `r_center`
  0.837 without any structural change, and minwscal went to near-ceiling — so the pooled marginal *does* capture
  composition once it can see the whole forest. Revisit only if S2's conditioning stalls above ~0.75 dispersion.
- **S4** **Grass ownership** (open risk #8): S owns grass demography; today grass stays F-side and S is
  TREE-only. Needs an ADR + a carbon-conservation gate for grass at the handoff.
- **S5** Whole-cohort **DROP** + the Gate-3 recursive drift (nqrmse 0.39 vs the documented 0.45 alarm).
- **S6** The **in-loop** OOD win — the offline 2.35× is `[VERIFIED]` (`flux_ood_experiment.jl`); the in-loop
  (recursive, coupled) OOD advantage is not yet demonstrated. Coordinate with M for the coupled harness.

## Line-local gotchas

- **Before arguing about AGGREGATION, check the two sides are the same QUANTITY (ADR 0035).** `soilmoist`
  spent a milestone mis-scoped as annual-mean-vs-year-end when the training column was the C `swc` (total
  water over SATURATION) and the runtime was `state.w` (plant-available over WHC). They overlap numerically
  (0.84–0.87 vs 0.79–1.00), which is exactly why the aggregation story looked right. See CLAUDE.md §3 for
  the `swc`/`rootmoist` formulas and why `swc` is not invertible.
- **"Quantity X is not reconstructable from the `ind` output" is a claim to RE-DERIVE, not to inherit
  (ADR 0035).** Both this skill and the builder docstring asserted per-patch LAI was unrecoverable; it was
  recoverable exactly, from two columns already emitted. Validate any such reconstruction against an
  INDEPENDENT C expression (crown area from `fpc_ind` vs from the height allometry), not against a quantity
  that differs from it for a *second* reason.
- **Anything inverted from the TXT `ind` table has a ~1e-5 precision floor** — `printind` uses `%g` = six
  significant digits (`fwriteoutput_ind.c:27`), and an inversion amplifies that. Don't set a tolerance below
  it; a genuinely wrong constant shows as a percent-level bias in the MEDIAN, not as a large max.
- **The `ind` writer emits only stems `height > height_min` = 5 m** (`fwriteoutput_ind.c:84`). Every training
  column is on that >5 m population, so it is self-consistent — but any comparison against an all-trees C
  grid output (`LAI_STAND`, `fpc_stand`) will show a biome-dependent deficit (0.77–1.01) that is NOT an error.
- **`age_mean` is the classic train/inference-shift trap** — train it as the nind-weighted mean cohort age
  (`mean(Age−1)`, start-of-year), NOT the elapsed-year counter (ADR 0024 supersedes 0023 §3).
- Never rename/clobber `test/testitems/references/drf_forest_hainich.drf` (+ `_meta.txt`) or
  `recruit_copula_hainich.rcop` — they are committed golden fixtures with bitwise round-trip tests.
- `*.drf`/`*.rcop` are **text** artifacts; `*.bin` is gitignored (writing one silently loses it).
- Diagnostic scripts must be `*_probe.jl` / `*_diagnosis.jl` / `*_decomp.jl` — a stray `*_test.jl` in
  `scripts/` fails the WHOLE suite at ReTestItems collection (and would red every other line).
- Read `.claude/skills/slow-drf-pipeline/SKILL.md` before touching the pipeline; it names every artifact.
