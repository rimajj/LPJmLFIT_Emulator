# ADR 0061 — The rung-2 demography hook: observe first, substitute second — and the C rebuild is gated, not assumed

* **Status:** accepted
* **Date:** 2026-08-10
* **Line:** M (multi-cell coupled S+F+E)
* **Supersedes / superseded by:** — (extends `EXECUTION_PLAN.md` §3 rung 2; uses ADR 0041's decomposition
  rule and ADR 0043's "compare decoded variables, not files" rule)
* **Related:** ADR 0041 (a subset re-run is not a per-cell replica), ADR 0043 (a file-level `cmp` on a
  NetCDF output is the wrong equality test), ADR 0093/0094 (the ladder and the goal re-ranking),
  ADR 0045/0046 (what establishment and mortality actually do in this config)

---

## 1. Context

`EXECUTION_PLAN.md` puts line M on **rung 2**: run the emulator's demography against the **real C fast
part** in a closed annual loop, replacing **only who dies and who establishes** and leaving turnover,
allocation and growth to the C. The plan names the hook point (`src/lpj/annual_natural.c:55-232`), the
mechanics precedent (`patches/lpjmlfit_daily_grass_gpp.patch` + rebuild) and the constraint (opt-in; the
stock binary must stay byte-identical). It also says, correctly, that this is a **throwaway harness**.

Two things had to be settled before any substitution could be written, and neither is a matter of taste:

1. **Is the state the emulator needs actually present at that point in the C?** Three of the four death
   rates read per-tree accumulators the emulator does not produce (`tree->water_stress`,
   `tree->temp_stress`, `tree->bm_inc_counter`), and the `ind` output — the only per-individual thing the
   C emits today — carries **none of them**, nor `bm_inc`, `nind` or the carbon pools (ADR "tier-2 RAW
   cannot yield bm_inc/nind/turnover", CLAUDE.md §3).
2. **Does rebuilding the C binary move the physics?** The oracle binary is the reference every F-vs-C
   number on this line is measured against. Adding a source file and recompiling it is not free of risk,
   and nothing in the repo was gating it.

## 2. Decision

**Split rung 2 into an observation half and a substitution half, and land the observation half first,
gated.** Concretely:

* Add an **opt-in demography observation hook** to the C, activated by the environment variable
  **`LPJ_RUNG2_DIR`**. When it is unset every entry point returns immediately and nothing is written.
  Source: `include/rung2hook.h` + `src/lpj/rung2_hook.c`; two one-line call sites in
  `annual_natural.c` (top of the per-patch block = `pre`, end of the per-patch block = `post`) and one
  object added to `src/lpj/Makefile`. Committed here as
  **`patches/lpjmlfit_rung2_demography_hook.patch`**.
* **An environment variable, not a config key.** The plan said "config flag". A config key means editing
  `fscanconfig.c` + `fprintconfig.c` and re-issuing every run config; an env var costs one `getenv` per
  process and leaves every `.js` in the repo byte-identical. For a throwaway harness that is the right
  trade. Recorded as a deliberate deviation, not an oversight.
* **The hooked build does not replace the oracle silently.** It is gated against the previous build on a
  real run before anything is measured with it (§4), and a copy is kept as `bin/lpjml_rung2`.

## 3. What the hook emits

Three record kinds per (cell, year, patch, phase), each with its own `#H` header line in the file itself
so a reader never carries a hard-coded schema:

| kind | content |
|---|---|
| `P` | patch context: `npatch`, `patcharea`, `fpar_leafon_grass`, `treelen`, live tree count, `aprec` |
| `T` | one line per tree individual — 49 fields (below) |
| `G` | one line per grass PFT: `fpc`, `nind`, `bm_inc`, `anpp`, `agpp` |

`phase = pre` is the state **before** turnover/allocation/mortality/establishment; `phase = post` is the
C's **own answer** for that year, after establishment.

The `T` record carries, beyond what `ind` emits: the **four accumulators the death rates read**
(`water_stress`, `temp_stress`, `bm_inc_counter`), the **carbon pools** (leaf/sapwood/heartwood/root and
both belowground pools, plus `debt`), `bm_inc`, `nind`, `crownarea`, `boleht`, `fapar`/`afpar`, `gddtw`,
`aphen_raingreen`, `sapwood_old`, `leaf_old`. **So the answer to question 1 is yes** — everything the
narrow interface needs is live at the hook point and now readable.

⚠ **`mort_prob` / `mort_npp` / `mort_age` / `mort_water` / `mort_temp` are meaningful only in the `post`
phase.** They are written by `mortality_tree_ind`, which runs after the `pre` dump; in the first year
after a restart they hold uninitialised memory (observed: a `6.9e-310` denormal). Do not read them at
`pre`.

## 4. The two gates, and both passed

**Gate A — the rebuild did not move the physics.** Single cell 42490, 2000–2019, `--ntasks=1`,
`-DFROM_RESTART`, hook **off**, against the run the previous build produced with the identical config
(ADR 0041's decomposition condition is met: same cell set, same task count). A file-level `cmp` calls
**20 of 21 outputs different** — exactly ADR 0043's `history` timestamp artefact. On **decoded
variables**: **138 NetCDF variables across 20 files plus the `globalflux` text output are identical, 0
differ.** Harness, new and reusable: `scripts/diagnose_cbinary_rebuild_equality.py`.

**Gate B — the dump says what the C says.** The same run emitting both the roster and the `ind` table.
Restricted to `post` and to stems > 5 m (the `ind` writer's own cut, `fwriteoutput_ind.c:84`): **the two
tree sets are identical — 5 465 trees, 0 rows on either side alone** — and **all 21 columns the two
representations share agree** to ≤ 5.0e-6 relative, i.e. at the 6-significant-digit floor `ind`'s `%g`
imposes. That includes all four hazard components and `mort_prob`. Harness:
`scripts/diagnose_rung2_roster_vs_ind.py`.

**Accounting closure, from the dump alone:** `post`-alive of year *N* equals `pre` of year *N+1* in all
19 transitions; recruits appear in `post` with **`age == 0`** (the `age++` is in `annual_tree`, so they
first show as age 1 the following year); dead trees stay in the patch list with `isdead = 1` and are gone
by the next `pre`.

**Cost: none measurable.** 7 s wall for the 20-year single cell with the hook on, versus 6–7 s off;
13.4 MB of text for 20 years × 25 patches.

## 5. The mistake this ADR exists to record

**A join on two tables that share nine column names silently compared nine columns against themselves,
and reported them all as perfect.** Gate B's first run printed `0.000e+00` for `mort_npp`, `mort_age`,
`mort_water`, `mort_temp`, `isdead`, `minwscal`, `k_root`, `beta_root` and `D95max` — the most reassuring
possible output — because polars' join kept one column per colliding name and the checker then compared
the roster's column with the roster's column. The only reason it was caught is that the **tenth**
colliding case had a unit conversion in it (`wscal_mean`, divided by 365 on one side), so the
self-comparison produced `0.9973 = 1 − 1/365` instead of zero and looked wrong.

**Rule: before comparing two tables, prefix one side's columns wholesale.** A `0.000e+00` on a
floating-point comparison of two independently written representations is evidence of an aliasing bug,
not of agreement — the honest signature of "the same number written twice" is the format floor (here
~5e-6), not zero. Every exact zero in gate B's final output is now on an integer column, which is where
an exact zero belongs.

## 6. Consequences

* Rung 2's **substitution half** can now be specified against a measured interface rather than a guessed
  one. What it needs from line S is the *shape* of the reply (`EXECUTION_PLAN.md` §6: "S owns its shape;
  M owns the harness") — given a `pre` roster, which individuals die and which recruits appear with which
  traits. The `post` records are the control that reply is scored against.
* **The oracle binary at `/home/jamirp/lpjml56fit/bin/lpjml` was rebuilt on 2026-08-10** and now contains
  the hook. It is numerically identical to the previous build with `LPJ_RUNG2_DIR` unset (§4 gate A), so
  it remains a valid oracle for every other line — but the fact is recorded in `CLAUDE.md` and
  `MEMORY.md` rather than left to be discovered. A copy is at `bin/lpjml_rung2`.
* **Nothing in `src/` (the Julia package) changed**; no committed baseline, artifact or default moved.
* Two reusable gates now exist where there were none: a rebuild-equality gate for the C binary and a
  roster-vs-`ind` gate for the hook. Both are pointed at from the `lpjmlfit-cbinary` skill.

## 7. What this does NOT claim

This is one cell (42490 of 54 020) and one scenario. It is a **harness**, not a fidelity result: no
number here says anything about how well the emulator reproduces LPJmL-FIT. The rung-2 *verdict* requires
the substitution half, ≥ 5 cells and 20 years, reported next to rung 1's — `EXECUTION_PLAN.md` §2.
