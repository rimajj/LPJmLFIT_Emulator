# ADR 0121 — The rung-2 replay floor was a defect in the kill list, not a property of the interface: it claimed fire's victims. Corrected, the kills half replays EXACTLY.

* Status: **accepted**
* Date: 2026-08-11
* Line: **M** (tier-2 block 0120–0139)
* Supersedes: **ADR 0120 §5's replay numbers** (`kills` 1.37×, `both` 1.30×) and **closes ADR 0120 §5's
  open question**. ADR 0120's four gates, its interface design, and its uninitialised-memory findings all
  stand unchanged.
* Scope: **one cell (42490, Hainich), 25 patches, 2000–2019 — 1 of 54 020 tree-bearing cells (guardrail 6).**

---

## 1. The question this answers, as it was pre-registered

ADR 0120 §5 left one thing open and refused to guess at it:

> the `kills` arm's state at the end of 2001 is identical to the recorded run in every dumped column, yet
> in 2002 the C's own hazard draw wants **33** kills where the record has **29**. Gate C rules out the
> rendezvous, so either the per-cell RAND48 stream or cell-level state *outside* the dump — most likely the
> top-AGB seedbank `cell->treelist` — has moved. **Decisive and cheap: add the cell's RAND48 seed and
> `treelen` to the `P` record and re-run `MODE=kills`.**

That experiment was run. It answered neither of the two branches it offered, and pointed at a third thing
that was wrong in the experiment itself.

## 2. What was added to the dump

The `P` (patch-context) record now carries the three channels of **cell-level state that no per-tree record
can carry**, all of which the demography reads:

| new `P` column | what it is |
|---|---|
| `seed` | the per-cell RAND48 stream position (`cell->seed`, hex triple) |
| `gasdev_iset` | the parity of `gasdev()`'s **process-global** spare-deviate cache |
| `sb_agb` `sb_trait` `sb_year` `sb_id` | order-independent checksums of the seedbank `cell->treelist` contents |

`treelen` was already dumped. Two notes on the additions:

* **`gasdev()` caches a spare normal deviate in file-local statics** (`src/numeric/gasdev.c`: deviates are
  generated in pairs, the second is returned on the next call). That cache is **not per-cell and not per-
  patch** — it is process state. Two runs whose model state agrees exactly still draw different normals if
  an odd number of `gasdev()` calls separates them, so it had to be observable before "same state,
  different answer" could be claimed. It is exposed by a pure getter (`gasdev_iset()`), declared in
  `include/rung2hook.h` so the stock headers stay untouched; the statics were hoisted from function scope
  to file scope, which changes neither lifetime nor initialisation.
* **`cell->treelen_old` / `treelist_old` are deliberately NOT dumped, because they are uninitialised
  memory in every real run.** Their only writer is `getsapling.c:57-58`, behind `if(config->isequal)`, and
  `isequalcoord` returns TRUE only when **every cell in the run shares identical coordinates** (and is
  hardwired FALSE for `nall == 1`) — so the branch is dead, `mergesapling()` has **no caller anywhere in
  `src/`**, and the field is garbage. It was dumped in the first iteration of this work and read 29 458 000
  next to a `treelen` of 19 650, which is what prompted the check. Shipping it would have added a third
  garbage column of exactly the kind ADR 0120 had to withdraw.

## 3. The measurement, and why it refuted both offered branches

`MODE=kills`, scored by `scripts/diagnose_rung2_cellstate_equality.py`. The divergence onset is **2002,
patch 2**, and the two phases of that one patch-year settle it:

| at 2002 patch 2 | `seed` | `gasdev_iset` | `treelen` | `sb_agb` | `sb_trait` | live trees |
|---|---|---|---|---|---|---|
| **`pre`** (before the hazards) | identical | identical | identical | identical | identical | 25 = 25 |
| **`post`** (after establishment) | **differs** | identical | identical | identical | identical | **22 vs 21** |

So at the moment the demography starts, the arm and the recorded run agree in **every** observable: the
random stream position, the seedbank contents, the pair-cache parity, and the roster. By the end of the
same patch-year the stream has moved and one more tree is dead. **The divergence is created inside that
patch-year — it is neither an inherited stream offset nor a seedbank that had drifted.** Both hypotheses
ADR 0120 offered are refuted, and the seedbank difference that does appear (from 2003) is downstream of
the stream having already moved.

The C's own audit localises it further: at 2002 patch 2, `n_kill_c = 2` (the C's own hazards wanted two
deaths) while `n_kill_applied = 3` (the recorded kill list held three), with `n_forced_dead = 0` and
`n_spared_certain = 0`. From provably identical state the C cannot have drawn differently — therefore the
third entry in the kill list was **never a death the hazards made**.

## 4. The mechanism: `isdead` has more than one author, and one of them is downstream of the hook

The harness derived its kill set as *"any `post` row with `isdead == 1`"*. `isdead` is set in two places
that matter here, and only one of them is the demography:

* `src/tree/annual_tree.c` — the demographic hazards: `mortality_tree_ind`, the allocation kill, the
  bioclimatic `!survive`, the cut year. **This is what the hook sees and owns.**
* `src/tree/fire_tree_ind.c:33` — **fire**, called from `firepft` at `annual_natural.c:129-135`, i.e.
  **after** the hook's decision point and before the `post` dump. Fire is a disturbance the C keeps; it is
  not part of the narrow interface (ADR 0093's narrow-interface principle, ADR 0120's design).

So the kill list silently contained fire's victims, and replaying them is wrong twice over. It claims a
death the interface does not own — and it **moves the random stream**, because of one short-circuit:

```c
if(!tree->isdead && erand48(pft->patch->stand->cell->seed) < (1-pft->par->resist)**fireprob)
```

`fire_tree_ind` draws **only for trees that are not already dead**. Pre-killing fire's victim inside
`annual_tree` therefore changes *how many* `erand48` draws fire consumes, which shifts the per-cell stream
for everything after it — and fire, now drawing from a different position, kills a different tree. Both
observations fall out of this single line: the extra death, and a stream that diverges exactly at the
`post` of the first patch-year in which any kill was applied.

This is why the null control could not catch it. `MODE=none` defers both halves, so the kill list is never
served — the machinery is inert and the run reproduces exactly, which is precisely what gate C measured
and reported. **A null control validates the transport, not the specification of the payload.**

## 5. The fix, and the corrected replay floor

The dump gains a **third phase, `mort`**, written after the demographic hazards and **before fire**
(`annual_natural.c`, one call, no-op unless `LPJ_RUNG2_DIR` is set). The harness derives kills from `mort`
and recruits from `post` as before, and asserts every kill names a tree of the `pre` roster.

Re-measured on the corrected basis (same cell, same 25 patches, same 20 years, terminal stems
replay ÷ recorded):

| arm | ADR 0120 (kills read off `post`) | **corrected (kills read off `mort`)** | first year the roster differs |
|---|---|---|---|
| `none` (null control) | 1.000 | **1.000** | none |
| `kills` | 1.37 | **1.000 — 376 vs 376 stems, EXACT** | **none** |
| `recruits` | 0.91 | **0.907** | 2000 |
| `both` | 1.30 | **1.367** | 2000 |

**The kills half of the interface now has no intrinsic divergence at all.** Over 1 500 patch-year records
(20 years × 25 patches × 3 phases) the arm is identical to the recorded run in every initialised per-tree
column *and* in every cell-state column — same random stream, same seedbank, same live count, every year.
The 1.37× was entirely the defect above.

Three things this changes for how rung 2 is read:

1. **The "naive ID replay is upward-biased by construction" caveat is now much narrower than ADR 0120
   stated.** It is real, but it applies only *once a trajectory has already parted*: `recruits` alone gives
   0.907, and adding the exactly-faithful kills half on top gives 1.367 — because the substituted recruits
   move the roster, after which recorded kill IDs stop matching live trees, go unserved, and the stand
   under-thins. The bias is a consequence of the other half diverging, not a property of ID replay per se.
2. **The replay floor to quote beside any future rung-2 result is: kills 1.000 (exact), recruits 0.907,
   both 1.367 — one cell.** A substituted mortality operator can now be credited with *any* difference it
   makes, because the transport contributes none. A substituted establishment operator still cannot be
   credited below the 0.907 floor, and that floor is structural, not a defect: the substituted recruit path
   skips the C's Poisson and inheritance draws and substitutes 4 of the 7 sampled trait axes (ADR 0120).
3. **The interface's boundary is now stated where the code puts it.** The demography owns the hazards in
   `annual_tree`; fire stays with the C. Any future widening (turnover, allocation, growth) has to name
   which authors of the affected state it takes over, and the `mort` phase is where that boundary is read.

## 6. Gates

* **Rebuild equality (ADR 0061's gate A), run after EACH of the three rebuilds this work needed**
  (seed/seedbank columns; removing the dead `treelen_old`; the `mort` phase): with both environment
  variables unset, **139 decoded quantities + `globalflux` identical, 0 differ**, against the ADR-0120
  binary on a matched cell-42490 / 2000–2019 / `--ntasks=1` run
  (`scripts/diagnose_cbinary_rebuild_equality.py`). The physics did not move.
* **The dumped state is unchanged by the writer changes** — the re-recorded baseline is identical to the
  ADR-0120 dump in every initialised column, from **two independent runs**
  (`scripts/diagnose_rung2_dump_equality.py`).
* **Null control re-run on the new schema and the new basis:** identical in every initialised column over
  20 years. Run it first, always.
* Cost unchanged: ~10 s per arm; the third phase makes the dump ~1.5× larger (20 MB for 20 yr × 25 patches).

## 7. What this does not say

* **One cell.** Every number here is cell 42490. The mechanism (fire's short-circuited draw) is
  cell-independent code, but the *magnitude* of the corrected floors is not, and fire frequency varies
  enormously across the grid — a fire-prone cell would have shown this defect far more violently, and a
  fire-free cell would never have shown it at all.
* **This is a harness result, not a fidelity result.** No emulator has been through the interface yet; the
  quantity measured is the transport's own error, which is now zero for the mortality half.
* **`MODE=record` was added to `scripts/run_rung2_replay_arm.sh`** because the recorded dump is the
  reference basis every arm is scored against, so a rebuild that changes the dump schema invalidates it —
  re-record before re-running an arm, or the two sides are on different schemas.

## 8. Files

* C (opt-in, inert with the environment variables unset): `patches/lpjmlfit_rung2_hook_v3.patch`
  (supersedes `..._v2.patch`, kept for provenance) — the `mort` phase call site, the `P`-record cell-state
  columns, `gasdev_iset()`.
* `scripts/diagnose_rung2_cellstate_equality.py` — **new**; the randomness-vs-state decision, with the
  onset patch-year printed in full.
* `scripts/rung2_replay_harness.py` — kills now derived from the `mort` phase, with the reason in the
  docstring and a fatal error on a dump that predates the phase.
* `scripts/run_rung2_replay_arm.sh` — `MODE=record`.
* Skill `lpjmlfit-cbinary` — the fire trap, the three phases, `MODE=record`.
