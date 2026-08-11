# ADR 0120 — Rung 2's substitution half: the C accepts a replacement demography, and the harness is measured against the C's own answer first

- **Status:** accepted
- **Date:** 2026-08-11
- **Line:** M (multi-cell coupled S+F+E). ADR block 0120–0139 (tier 2, opened here).
- **Supersedes / extends:** ADR 0061 (the observation half). Patch file
  `patches/lpjmlfit_rung2_hook_v2.patch` supersedes `patches/lpjmlfit_rung2_demography_hook.patch`,
  which is retained for the provenance of the previously gated binary.

## 1. Context

ADR 0061 built rung 2's **observation** half: an opt-in hook (`LPJ_RUNG2_DIR`) that dumps each patch's
tree roster at the top of the annual demography block (`pre`) and again after establishment (`post`),
carrying the three per-tree accumulators three of the four death rates read and which the `ind` output
does not have. It answered the feasibility question — everything the narrow interface needs is live at
that point — but the C could only *offer* the roster, not *accept* a replacement.

`EXECUTION_PLAN.md` rung 2 is: **S plus the real C fast part, closed annual loop**, with the
owner-delegated narrow interface — replace only **who dies** and **who establishes**, leave turnover,
allocation and growth to the C, because that keeps the C's own per-tree accumulators intact and halves
the interface surface so a failure is attributable.

The S→M integration point (what exactly S returns) was raised on 2026-08-10 and **S has not yet
replied**. The read-back does not depend on that answer — see §5.

## 2. Decision

Add a second opt-in hook, `LPJ_RUNG2_APPLY_DIR` (`include/rung2apply.h`, `src/lpj/rung2_apply.c`),
that hands the `pre` roster to an external process, blocks for its answer, and applies it.

**Protocol** — one rendezvous per patch-year, files plus a spin-wait (chosen over FIFOs for
debuggability; the harness runs few cells and per-year file I/O was measured free in ADR 0061):

```
C   writes  <dir>/req_r<rank>_y<year>_p<patch>.txt   (the pre roster, IDENTICAL format to the dump)
    then    ...req_....ready
C   blocks until  ...rsp_....ready
C   reads   <dir>/rsp_....txt:
      K <pft_id> <treeidx>                              a tree to kill
      R <pft_id> <sla> <wooddens> <D95max> <minwscal>   a recruit
      MORT_C  / ESTAB_C                                 defer that half back to the C
      END
```

Any tree of the `pre` roster **not** named by a `K` line is intended to live; the `R` lines are the
**complete** tree recruit set for that patch-year. The C appends a per-patch-year audit line
(`audit_r<rank>.txt`) with what it actually did.

Four choices inside this are load-bearing:

1. **The kill key is `(pft_id, treeidx)`, not `treeidx`.** `tree->index` is a **per-PFT** counter
   (`new_tree.c`: `tree->index = treepar->index++`, and `treepar` is `pft->par->data`), so two trees of
   different PFTs in one patch can share an index. ADR 0061's `ind`-vs-dump gate keyed on `treeidx`
   alone and passed only because Hainich's per-PFT counters happen to be far apart. The hook asserts
   key uniqueness per patch-year and dies loudly rather than mis-attributing a kill.
2. **A kill the C's own state cannot un-make wins over a "live" verdict, and is counted.** `hard` =
   the `allocation_tree` kill (negative pools), the logging cut year, bioclimatic limits (`!survive`),
   or `isneg_tree`. Everything else — including the hazard-saturated `mort_prob == 1` cases — is
   demography and belongs to the substitute; those are counted separately (`n_spared_certain`) as the
   clearest measure of how far the substitution departs from the C.
3. **`MORT_C` / `ESTAB_C` per patch-year.** Without them a divergence cannot be attributed to a half.
4. **The request reuses the observation hook's roster writer** (`rung2_write_header` /
   `rung2_write_patch`, exported from `rung2hook.h`) rather than carrying a second copy of the
   49-field schema.

## 3. What the interface does NOT control — state this in any rung-2 result

**A recruit carries seven sampled trait axes, not four.** `new_tree.c` draws `sla`, `wooddens`,
`D95max` (or `beta_root`), `minwscal`, `emax`, `k_root` and `beta_2`, and derives leaf `longevity`
from `sla` via `corr_corridor` (itself a draw). Component S's production copula supplies **four**
(SLA, Wooddens, D95max, minwscal). The hook stamps those four on after `addpft`, re-derives
`beta_root` from the substituted `D95max` and `longevity` from the substituted `sla` — because the C
derives them that way — and leaves `emax`, `k_root`, `beta_2` on the C's own uniform draw. Values
outside the PFT's own interval are clamped and counted.

So a rung-2 arm substitutes 4 of 7 recruit axes. That is a property of the S artefact, not of the
hook, and it must be declared rather than discovered later.

## 4. Gates (all run; cell 42490, 25 patches, 2000–2019, `--ntasks=1`)

| Gate | Result |
|---|---|
| **A — the rebuild did not move the physics.** New binary vs the ADR-0061 binary, both hooks' env vars unset, matched cell/config/`--ntasks` | **139 decoded quantities + `globalflux` identical, 0 differ.** Run twice (after each of the two rebuilds this ADR made). `scripts/diagnose_cbinary_rebuild_equality.py` |
| **B — the observation dump is unchanged** by the writer refactor. Two independent RUNS, new binary vs recorded | **identical in every initialised column**, 20 259 tree records. `scripts/diagnose_rung2_dump_equality.py` |
| **C — the null control.** Rendezvous active for all 500 patch-years, both halves deferred (`MORT_C` + `ESTAB_C`) | **identical in every initialised column** over 20 years ⇒ the request/spin-wait/parse machinery perturbs nothing |
| **D — replay identity.** The C fed its own recorded kill and recruit sets | §5 |

Cost: 10 s wall clock vs 7 s for the plain run, over 500 rendezvous.

### 4b. Two columns of the dump are uninitialised memory — found by gate B, and gate B is the only kind of test that could find them

`scripts/diagnose_rung2_dump_equality.py` compares two builds column by column and separates the
uninitialised columns from real state. It has to, because two of them differ between builds of
identical physics:

* **`sapwood_old` is a DEAD FIELD.** `Pfttree.sapwood_old` is declared in `include/tree.h` and is
  **never written or read anywhere in LPJmL-FIT**, and `new_tree` does not zero it. Its dump column is
  garbage at **both** phases in **every** year. Never read it.
* **`mort_*` are garbage for any tree that has not yet been through `mortality_tree_ind`** — which is
  every tree at the first `pre` after a restart (ADR 0061 knew this) **and every recruit at the `post`
  of its own establishment year** (recruits are added by `establishmentpft_ind`, which runs *after*
  mortality, and `new_tree` does not zero those fields). ADR 0061's "valid only at `post`" is
  therefore too generous and is corrected here: valid at `post`, **for trees that were already alive
  that year**.

**The generalisable point.** ADR 0061's gate compared the dump against the run's own `ind` table and
found all 21 shared columns agreeing to 5e-6. That could not have caught either of these, because both
readers read the **same struct memory** and therefore agree on the garbage too. A consistency check
between two readers of one buffer cannot detect uninitialised memory — only a comparison of two
independent **runs** can. (Same shape as the ADR-0061 aliasing bug where nine columns were compared
against themselves and printed exact zeros.)

## 5. The replay result — the harness's own noise floor, and one open question

The read-back is exercised by replaying the C's **own** recorded decisions
(`scripts/rung2_replay_harness.py`, `scripts/run_rung2_replay_arm.sh`, scored by
`scripts/diagnose_rung2_replay_identity.py`). This is the one decision whose right answer is known, so
whatever gap it leaves is the floor no later rung-2 arm can be credited with beating.

Terminal (2019) live stems, replay ÷ recorded, one cell, 25 patches, 20 years:

| arm | substituted | 2000 roster | first differing year | 2019 ratio |
|---|---|---|---|---|
| `none` | nothing (null control) | identical | — | **1.000** (identical throughout) |
| `kills` | who dies | **identical** (583 = 583, every tree shared) | 2002 | **1.37** |
| `recruits` | who establishes | differs (583 vs 586) | 2000 | **0.91** |
| `both` | both | 583 = 583 but keys differ | 2000 | **1.30** |

Readings that are established:

* **The mechanism works and the machinery is transparent** (gates A–C, and the `kills` arm reproducing
  the recorded roster exactly for 2000 and 2001 with all 31 and all 20 recorded kills applied).
* **The `both` and `recruits` arms differ at 2000 for a benign reason**: recruit `treeidx` values come
  from a per-PFT global counter, and the substituted path calls `addpft` in a different order from the
  C's per-PFT background loop plus inheritance loop, so the same set of indices is handed out to
  different individuals. Per-year key sets are what should be compared, not per-patch assignment.
* **Naive ID replay is upward-biased by construction.** Once trajectories separate, part of the
  recorded kill set names trees that no longer exist and cannot be applied, while the recruit list is
  replayed in full — so the stand gets denser. Do not read the 1.30–1.37 as a property of the
  interface; it is a property of replaying *identifiers*, which no real emulator arm does.

**OPEN, and deliberately not guessed at.** In the `kills` arm the state at the end of 2001 is identical
to the recorded run in every dumped column, yet in 2002 the C's own hazard draw wants **33** kills where
the record has **29**. Gate C rules out the rendezvous. So either the per-cell RAND48 stream or some
cell-level state outside the dump (the top-AGB **seedbank**, `cell->treelist`, which is rebuilt yearly
and is *not* in the roster records) has moved. **Decisive next experiment, cheap:** add the cell's
RAND48 seed and `treelen` to the `P` record and re-run the `kills` arm — if the seeds agree at the 2002
`pre` and the answer still differs, it is state, not randomness; if they disagree, walk back to the
first year they do. Do not build on the 1.37 until this is closed.

## 6. Consequences

- Rung 2 is now runnable end-to-end: the C offers a roster, an external process answers, the C applies
  it, and the arm is scoreable against a measured null.
- Guardrail 4 holds by construction and is gated twice: both env vars unset ⇒ byte-identical physics.
- **Any rung-2 fidelity claim must quote the replay floor beside it**, name the cell count (this is
  **1** of 54 020 — guardrail 6 and ADR 0106), and state that 4 of 7 recruit trait axes are substituted.
- The `mort_prob`-ranked victim rule (option (b) of the S→M proposal) is now known to be awkward:
  at the rendezvous the current year's hazards have not been computed yet, so a rule keyed on the C's
  own `mort_prob` would rank on a **one-year-stale** hazard, or need the kill decision deferred until
  after `mortality_tree_ind` — which `litter_update`'s inline call makes intrusive. This is a reason to
  prefer option (a) or (c), and it is being carried back to line S.
