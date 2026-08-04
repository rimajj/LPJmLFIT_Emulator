# ADR 0043 — the cross-build gate PASSES: the Feb-5 and Jul-21 builds are bit-identical and poolable

* **Status:** Accepted
* **Date:** 2026-08-04
* **Line:** S (Component-S science) · ADR block 0030–0049
* **Closes:** the open cross-build question posed by **ADR 0041** §"The cross-build question"
  (which specified this gate but could not run it to a verdict)
* **Related:** ADR 0030 (clean noise floor — the consumer of the seed pair), ADR 0041 (`random_seed`
  is inert under `FROM_RESTART`; the subset gate is VOID for this question)

## Context

ADR 0041 established that **two ground-truth members may be compared as a seed pair only if they
were run with the same binary AND the same `--ntasks`**, and that the subset gate it first tried is
**VOID** for the binary question because the decomposition confound is larger than the signal being
measured (a 1-cell re-run diverges from global truth at the first step; a 21-cell block stays
bit-identical for 15 years and then diverges).

The `ssp370` seed1 member was produced by the **`Feb  5 2026`** build. The current `bin/lpjml` is a
**`Jul 21 2026`** RHEL8 → RHEL9 toolchain rebuild (GCC 8.5.0 → 11.5.0, GLIBC_2.14 → 2.33/2.34,
`__xstat`→`stat`, `__libc_csu_*` removed, `DT_NEEDED libjson-c.so.4` → unversioned) plus the
committed `patches/lpjmlfit_daily_grass_gpp.patch`. ADR 0041 argued from the source that both
changes are inert for this config, but explicitly declined to treat that as empirical proof.

ADR 0041 therefore specified the replacement: a **matched-decomposition** gate — a full-grid
67 420-cell / **2048-task** re-run from the historic seed1 restart with `random_seed 1`, the same
5-output set and the same forcing, i.e. a faithful re-run of the seed1 member itself, with only
`write_restart` dropped (written after the last year, so it cannot affect the trajectory).

## What was run

Job **`1678607`** (`S-crossbuild-gate`), `--ntasks=2048 --exclusive`, `-DFROM_RESTART`, config
`/p/tmp/jamirp/S_crossbuild_gate/lpjml_2020_2100.js`. **COMPLETED** in 01:17:11 with the mandated
log verdict `lpjml successfully terminated, 67420 grid cells processed.` (ADR 0041 / CLAUDE.md §3 —
never judge a C run from SLURM state).

## Verdict — PASS, and stronger than the gate required (`[VERIFIED 2026-08-04]`)

| artifact | what it is | result |
|---|---|---|
| `globalflux_2020_2100.csv` | 81-year global carbon/water aggregate, 10 545 B | **bit-identical** (`cmp`) |
| `vegc_2020_2100.nc` | per-cell annual vegetation carbon, 81 × 280 × 720 | **data bit-identical**; file differs by 124 B in the `history` attribute only |
| `ind_2020_2100.csv` | the **per-individual roster**, 193 097 583 638 B | **bit-identical** (`cmp` over all 193 GB) |

The `vegc` file-level `cmp` reports a difference at byte 172, which is entirely the NetCDF `history`
attribute — a wall-clock timestamp plus the config path:

```
< :history = "Wed Jul 15 11:45:15 2026: … /transient_2020_2100_npatch25_random_seed1/scripts_for_running_the_model/lpjml_2020_2100.js"
> :history = "Mon Aug  3 18:12:13 2026: … /p/tmp/jamirp/S_crossbuild_gate/lpjml_2020_2100.js"
```

The old path string is 124 B longer, which accounts for the whole size delta. Every other header
line is identical, and a per-variable SHA-256 over the decoded arrays matches for **all seven**
variables including the full `VegC` field (`c71f03e05783a5a6`).

**So a file-level `cmp` on a NetCDF output is not the right test — it fails on provenance metadata
that the model is required to write.** Compare the decoded variables, or compare the text/CSV
outputs, which carry no timestamp.

The `ind` result is the load-bearing one and it was **not** part of the gate ADR 0041 specified.
That file is the per-individual roster — 193 GB of `%g` text at 6 significant digits, the finest
grain the model emits, and precisely the quantity ADR 0041 showed amplifies any perturbation into a
permanently different row count. Its bit-identity over all 81 years is a far stronger statement than
the aggregate comparisons: **the two builds do not merely agree in the global mean, they produce the
same individuals.**

## Decision

**The `Feb  5 2026` and `Jul 21 2026` builds are trajectory-identical for this config, and ssp370
members produced by either may be pooled as a pure seed pair.** ADR 0041's source-level arguments
(the patch writes only into `initoutput.c`'s trash region; no physics parameter drifted) are now
empirically confirmed rather than merely plausible.

This clears the binary half of ADR 0041's rule. The `--ntasks` half is satisfied by construction for
the corrected seed2 member (`--ntasks=2048`, copied from the seed1 job file).

## Consequences

* **The ssp370 / pooled bases can carry a real ADR-0030 noise floor** — the last blocker on the
  binary side is gone. The corrected seed2 member (ADR 0041) is a genuine second realization
  (independence gate: sizes differ 0.1255 %, all 6 sampled windows differ, `restart_2100.lpj`
  1.336e11 B, log reports 67 420 cells) and is now also known to be *comparable* to seed1.
* **The `STEM_CAP` caveat from ADR 0041 still stands and is now the only remaining blocker** on
  criteria 1 and 4: the pooled seed1 tables were built with `STEM_CAP=400` while ADR 0030 Decision 1
  requires the cap **OFF** for a floor, and the cap's rank key
  (`pl.struct(['Cell','Patch','Year']).hash(seed=seed)`) is seed-dependent, so a `SEED=2` build
  retains a *different* set of whole patch-year clusters — deflating the floor and flattering the
  emulator. Rebuild **both** sides uncapped, or state the deviation next to the ADR-0030 criterion.
* **The gate's own 193 GB `ind` CSV has served its purpose and is deleted.** Its only function was
  to keep the output set byte-identical to the producing run; its content is now proven identical to
  the seed1 truth, which is retained. Reclaimed ~181 GB from `/p/tmp/jamirp/S_crossbuild_gate`.
* CLAUDE.md §3's "a subset re-run is not a per-cell replica" note is unaffected — this ADR does not
  rehabilitate subset re-runs. It confirms that a **matched-decomposition** re-run reproduces the
  original bit-for-bit, which is the positive control that makes ADR 0041's negative result
  interpretable: the divergence there was the cell set, not nondeterminism in the model.

## What it immediately unlocked — the first ssp370 noise floor (`[VERIFIED 2026-08-04]`)

With the pair gated and poolable, the floor was measured on the `tree7` parquet basis (job `1689437`,
57 295 cells with ≥20 survivor stems in both seeds; the fabricated-floor and duplicate-key guards both
stayed silent):

| axis | ssp370 `floor_r` | historic `floor_r` | Δ |
|---|---|---|---|
| SLA | 0.975 | 0.965 | +0.010 |
| Wooddens | 0.944 | 0.923 | +0.021 |
| **D95max** | **0.837** | 0.895 | **−0.058** |
| minwscal | 0.978 | 0.973 | +0.005 |

ssp370 pools **81** years per cell to historic's **20**, so ~4× more averaging should raise `floor_r`
*mechanically* on every axis. Three axes do; **`D95max` falls despite that tailwind**, so the true
degradation exceeds −0.058: rooting-depth trait medians are genuinely less reproducible between realizations
under warming. This is the `tree7` basis, **not** basis 1 — a real floor for the emulator's population but
not byte-identically stem-matched to the emulator's `Y` — so it carries no GAP and must never be quoted
against an `emu_r`. Basis 1 for ssp370 remains blocked on the `STEM_CAP` decision above.

## The chaining trap this run exposed (recorded because it cost a silent gate failure)

The seed2 member's chained independence gate (`1684568`) **failed in 1 second** with
`log does not report 67420 cells (found: no completion line at all)` — while the C run had in fact
completed cleanly. Cause: when the hung member was resubmitted (ADR 0041's `--exclude=cso14c74`
fix), the children were re-chained onto the new job id, but the child jcf's
`--log …/lpjml_2020_2100.1678574.out` still named the **cancelled** job's log, which is 0 bytes.
The gate was reading the corpse of the run it was meant to judge, and its three data checks passed
while its provenance check failed on a stale path.

**A jcf that hardcodes a parent's job id in a path is not resubmit-safe.** `scripts/`'s gate wrappers
now resolve the newest `lpjml_*.out` in the run directory instead of taking a pinned job id — see
the `lpjmlfit-cbinary` skill. Re-running the gate against the real log passed all four checks.
