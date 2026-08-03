# ADR 0041 — `random_seed` is inert under `FROM_RESTART`: a second seed is a second SPIN-UP

* **Status:** Accepted
* **Date:** 2026-08-03
* **Line:** S (Component-S science) · ADR block 0030–0049
* **Supersedes / amends:** amends ADR 0030 §"seed2 floor" (which assumed an ssp370 seed2 basis
  could be produced by bumping `random_seed`); records the fix for the trap first flagged in
  `lines/S/STATE.md` (2026-07-30)
* **Related:** ADR 0004 (constant-CO2 regime), ADR 0030 (clean noise floor), ADR 0031 (complete
  tree-PFT basis), ADR 0036 §5b (streaming key-set nondeterminism)

## Context

ADR 0030 criteria 1 and 4 need a **seed-vs-seed noise floor**: two ground-truth members that
differ *only* in the stochastic seed, so the irreducible spread can be separated from emulator
error. Only the `historic` scenario had a usable pair; the `ssp370` member labelled
`random_seed2` was found (2026-07-30) to be a **bit-identical copy of seed1**, so every
criterion computed against it would have reported `floor_r ≡ 1` — fabricated headroom, with no
error raised anywhere. Repeated earlier attempts to produce the member failed because they
changed the seed and not the spin-up.

## The mechanism (re-derived from the C source, not assumed)

Under `-DFROM_RESTART` with `"new_seed": false`:

* the per-cell RAND48 seeds are **restored from the restart file** — `newgrid.c:507-513` →
  `freadcell.c:37` `freadseed(file, cell->seed, swap)` (writer: `fwritecell.c:38`);
* the only code that would apply `random_seed` instead is **gated off** —
  `newgrid.c:520-521`, `if(!config->ischeckpoint && config->new_seed) setseed(grid[i].seed,
  config->seed_start + (i+config->startgrid)*36363)`; likewise `newgrid.c:266-267`;
* `config->seed_start` *is* applied once at parse time (`fscanconfig.c:231`) but is then
  **unconditionally overwritten** from the restart header (`openrestart.c:139-140`), with no
  consumer in between. Its only trajectory-relevant consumers (`iterate.c:108/148/181`) are
  unreachable here: `nspinup:0`, `fix_climate:false`, no `fix_deposition`.

So **`random_seed` is inert in any `FROM_RESTART` run.** The historic pair's independence comes
from elsewhere: their 1000-year spin-ups ran *without* `-DFROM_RESTART`, taking the
`newgrid.c:460` branch whose `setseed(grid[i].seed, seed_start + (i+startgrid)*36363)` is **not**
gated by `new_seed`. That is arithmetically visible in the restart bytes — cell 156's stored
per-cell seed is `(13070,36533,86)` in seed1 and `(13070,36534,86)` in seed2, exactly
`setseed(seed_start + 156*36363)` for `seed_start` 1 and 2, reproduced through
`setseed.c:24-27` including the signed-int wraparound that `67419*36363 > INT_MAX` requires.

**Why it was silent:** with `new_seed:false` the log prints `Reading random seeds from restart
file.` rather than `Random seed: 2` (`fprintconfig.c:748-751`). Nothing in the config, the log,
or SLURM distinguishes a genuine second seed from a clone.

## Decision

1. **A second seed is a second SPIN-UP, carried forward.** The ssp370 seed-N member is produced
   by pointing `restart_filename` at the **historic seed-N** `restart_2019.lpj`. `new_seed` stays
   `false`. `random_seed` is kept in the config as documentation only, and is explicitly
   understood to be inert.
2. **Do not "fix" this by setting `new_seed: true`.** It would fire `newgrid.c:266-267`/`520-521`
   and discard 1020 years of evolved RNG state at the 2019/2020 boundary — a discontinuity
   neither the historic transients nor the ssp370 seed1 member has — making the two members
   differ in seed value *and* protocol, and re-executing the int-overflowing
   `seed_start + global_cell*36363`.
3. **State the ensemble semantics honestly.** These are **whole-experiment macro-replicates**
   (independently seeded 1000-year spin-ups carried through 2000–2019 and on into 2020–2100), not
   2019 branch-point perturbations. The floor they measure is accordingly the *full* structural
   spread of the stochastic gap model, which is the right basis for ADR 0030 but must not be
   described as a small-perturbation ensemble.
4. **Never validate completion from SLURM state.** The stock job file ended `rc=0 # save return
   code of srun` / bare `exit`, i.e. it always exited 0; a run dying mid-century leaves a
   plausible truncated 193 GB CSV behind a green `sacct` row. Judge success from
   `lpjml successfully terminated, 67420 grid cells processed.` The job file now propagates
   `rc=$?`.
5. **Gate a new member on independence before deriving anything from it.**
   `scripts/diagnose_ind_seed_independence.py` checks the completion line, the final year, that
   the size *differs* from the sibling's, and that sampled MB windows differ at every offset.
   Equal size is the copy signature.

## The corrected member

`.../ssp370/ground_truth/model_output/transient_2020_2100_npatch25_random_seed2_from_hist_seed2/`

Exactly **four** edits relative to the seed1 config — all four must be stated when citing its
provenance:

| # | edit | inert? |
|---|---|---|
| 1 | `restart_filename` → historic **seed2** `restart_2019.lpj` | **no — this is the fix** |
| 2 | run directory (includes, `LPJOUTPATH`, `LPJRESTARTPATH`, `-o/-e`, `-D`) | yes |
| 3 | `"random_seed"` 1 → 2 | yes (inert, documentary) |
| 4 | `co2` input path → `/p/projects/waldspektrum/priesner/clustering/global/global_co2_ann_1700_2019_const_2100.txt` | yes, **content-proven** |

Edit 4 was **forced**: the seed1 config's co2 path
(`/home/jamirp/scripts/clustering/climclusterpy_package/…`) no longer exists — that directory was
repurposed for an unrelated project on 2026-07-28 — and `lpjcheck` failed `ERROR100` on it. The
file was recovered and its identity established **four independent ways**: the git blob
`140de8ba…` (its only version in that repo's history, added 2026-07-13, deleted 2026-07-28, so it
spans the 2026-07-15 seed1 run unchanged); the filesystem snapshot
`/home/jamirp/.snapshot/weekly.2026-07-26_0015/` whose **mtime 2026-07-07 13:50 predates the
run**; byte-exact reconstruction from `/p/projects/lpjml/inputs/co2/global/TRENDY/v12/
global_co2_ann_1700_2022.txt` (1700–2019 verbatim, then 2019 held flat); and agreement with the
documented `CO2_CONST`. Installed md5 **`ed5699b9c92d4d25857889f644b153db`**, 5212 B, 401 years.
Per ADR 0004 these members are `ssp370 climate with CO2 held constant at 409.63 ppm from 2020`.

## The cross-build question (and why it needed its own gate)

The seed1 ssp370 member was produced by the **`Feb  5 2026`** build; the current `bin/lpjml` is a
**`Jul 21 2026`** rebuild. That difference is *not* only the committed
`patches/lpjmlfit_daily_grass_gpp.patch` — it is additionally a **RHEL8 → RHEL9 toolchain
rebuild** (GCC 8.5.0 → 11.5.0 system headers, GLIBC_2.14 → 2.33/2.34, `__xstat`→`stat`,
`__libc_csu_*` removed, `DT_NEEDED libjson-c.so.4` → unversioned `libjson-c.so`). If the rebuild
moved the trajectory, the seed1-vs-seed2 comparison is contaminated by more than the seed.

Two things are settled by reading:

* **The patch itself is inert for this config.** It touches four files and adds only two output
  slots. For a run that opens 5 of 421 outputs, `initoutput.c:50-67` allocates a leading `maxsize`
  **trash** region and sets `outputmap[i]=0` for every unopened output, with real outputs at
  `index >= maxsize`; `outputsize(D_GRASS_*)==1` so `maxsize`/`totalsize` and the allocation are
  unchanged. The unconditional `getoutput(output,D_GRASS_GPP,config)+=…` in `daily_natural.c`
  therefore writes only into trash, consumes no RNG draw, and touches no cell/stand/pft state.
* **No physics parameter drifted.** `find -newermt 2026-07-15` over `src/ include/ par/` returns
  *exactly* the patch's four files, and `git status` shows exactly those four modified.
  `param_lpjmlfit.js`, `par/lpjparam_fit.js`, `par/soil_20m.js`, `par/pft_lpjmlfit.js`,
  `par/manage_*.js` and `Makefile.inc` (so the `-DPERMUTE`/`-DSAFE` flags) all predate the seed1
  run. The one runtime-read par file that changed is `par/outputvars.js`, by the same patch's two
  catalogue rows, matched to `NOUT 421`.

Neither argument is an *empirical* proof of trajectory equality, so it was measured directly:

* **gate A** — cell 42490 alone, ssp370 2020–2100, from the **historic seed1** restart with the
  Jul-21 binary, i.e. reproducing the seed1 member's own inputs;
* **gate B** — the same, over the 21-cell block 42480–42500: the **decomposition control**.

Comparison is on the 29 `ind` columns as `%g` text — `fwriteoutput_ind.c:27` writes 6 significant
digits, so string equality is the strongest test the file supports and any tolerance below ~1e-5
is meaningless. Harness: `scripts/diagnose_ind_binary_equality.py`.

### The control fired: a SUBSET RE-RUN CANNOT ANSWER THIS QUESTION (`[VERIFIED 2026-08-03]`)

Cell 42490, same binary, same restart, same forcing, varying **only the cell set**:

| run | cell set | rows for cell 42490 | first year ≠ global truth | years matching truth |
|---|---|---|---|---|
| A | 42490 alone | 18 530 | **2021** (the first step) | 2 / 81 |
| B | 42480–42500 (21 cells) | 19 366 | **2035** | 16 / 81 (2020–2034 contiguous) |
| truth | all 67 420, 2048 tasks | 18 790 | — | — |

So the cell's trajectory **depends on which other cells share the job**, and the dependence weakens
as the cell set approaches the global one: B is *bit-identical for 15 consecutive years* and then
diverges, while A diverges immediately. At year 2020 A and B already differ in exactly two columns,
`fpc_ind` and `isdead`.

That pattern is the signature of a **stochastic gap model amplifying a tiny perturbation**: once a
single individual dies or establishes differently, the roster differs permanently and the row count
never re-converges. The RNG itself is *not* the cause — it is fully per-cell (`permute` takes
`stand->cell->seed`; there is no `drand48()`/`lrand48()` anywhere in `src/`; `config->seed` is read
only in `iterate.c:108/148/181`, all unreachable at `nspinup:0` / `fix_climate:false`). **The
mechanism is not established, and this ADR does not claim one.**

Consequences, both load-bearing:

1. **A subset re-run is not a per-cell replica of the global run.** CLAUDE.md §3's "per-cell seek is
   MPI-decomposition-independent" is true of the *seek* — you do get the right cell's initial state
   — but **not of the evolution**. Any validation that compares a single-cell re-run against global
   ground truth is comparing two different trajectories, and the previously recorded ~1.6e-4
   `whc_nat` discrepancy is the same effect seen through a smoother variable.
2. **The subset gate is VOID for the cross-build question** (exit 3): the decomposition confound is
   larger than the binary signal. It is replaced by a **matched-decomposition** gate — a full-grid
   67 420-cell / **2048-task** re-run from the historic seed1 restart with `random_seed 1`, the same
   5-output set and the same forcing, i.e. a faithful re-run of the seed1 member, compared against
   the seed1 ground truth's `globalflux_2020_2100.csv` (81-year global aggregate) and
   `vegc_2020_2100.nc` (per-cell annual). Only `write_restart` is dropped, which is written after
   the last year and cannot affect the trajectory.

### The rule

**Two ground-truth members may be compared as a seed pair only if they were run with the same binary
AND the same `--ntasks`.** The corrected seed2 member satisfies the second condition by construction
(`--ntasks=2048`, copied from the seed1 job file); the first is what the matched-decomposition gate
measures. A FAIL there does **not** invalidate the new member — it is still a genuine second
realization — it invalidates *pooling it with seed1 as a pure seed pair*.

## Consequences

* The ssp370/pooled bases can have a real ADR-0030 floor for the first time.
* **An ssp370 seed2 parquet is necessary but not sufficient for criteria 1 and 4 on the pooled
  basis.** The pooled seed1 tables were built with `STEM_CAP=400` while ADR 0030 Decision 1
  requires the cap OFF for a floor, and the cap's rank key is
  `pl.struct(['Cell','Patch','Year']).hash(seed=seed)` — so a `SEED=2` build retains a *different*
  set of whole patch-year clusters, deflating the floor and flattering the emulator. Either
  rebuild both sides uncapped or state the deviation with the ADR-0030 criterion.
* `bin/lpjml.pre_dgrass.bak` cannot be used as a drop-in alternative while the working tree is
  patched: it was built with `NOUT=419` and the live `par/outputvars.js` declares 421 entries
  (`ERROR232`/`ERROR201`). Reverting the four files would restore the matched pair.
* CLAUDE.md §3's "json-c 0.17 **aborts**" note applies to the Feb-5 build. The Jul-21 build imports
  *versioned* `JSONC_0.14` symbols, which 0.13.1, 0.17 and the system `libjson-c.so.5` all provide;
  the real bare-environment failure is `libnetcdf.so.19`/`libudunits2.so.0` not found. Pin the
  documented module set in the job file for that reason.
