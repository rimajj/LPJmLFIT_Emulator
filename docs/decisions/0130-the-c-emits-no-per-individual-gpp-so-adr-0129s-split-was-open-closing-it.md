# ADR 0130 — LPJmL-FIT emits NO per-individual GPP (the `ind` `gpp` column is a second copy of NPP), which is why ADR 0129's photosynthesis-vs-respiration split was a bracket; two opt-in C switches close it

* **Status:** accepted
* **Date:** 2026-08-12
* **Line:** M (multi-cell coupled S+F+E; rung 3 of `EXECUTION_PLAN.md`)
* **Supersedes:** nothing. **Narrows:** ADR 0129 §3 (the bracket) and §4 (the discriminator with no power).
* **Basis:** rung 3 — the C's own roster restarted every year, 25-patch ensemble, year-matched.

---

## 1. Context — what ADR 0129 could not decide, and why

ADR 0129 split F_diff's assimilate error by the exact identity `bmi = GPP·CUE`, i.e.
`ln(bmi_F/bmi_C) = ln(GPP_F/GPP_C) + ln(CUE_F/CUE_C)`, and found **both channels live** — but could
only report a **bracket, 38–78 % photosynthesis**, because its two C columns were on **different
populations**:

* `GPP_C` came from the daily `d_gpp` output minus grass, which contains **every tree**;
* `CUE_C` came from the per-stem `npp` of the `ind` table, which the writer emits **only for stems
  above `param.height_min` = 5 m** (`fwriteoutput_ind.c`).

Both biases are the same factor with opposite signs, so the **product — every published `bmi`
number — was untouched**, and only the split was undetermined. ADR 0129 §4 tried to identify the
factor by regressing the GPP ratio on the crown-cover `gt5m` across years and correctly reported
that the test **has no power** (detrended `SE(slope)` 3.63 at Hainich, 41.8 boreal).

## 2. Decision

**Close the bracket on the C side, by measurement, behind two opt-in switches on a rebuilt oracle.**
No emulator arm can close it: the missing quantity is the C's own.

## 3. The finding that made it a two-part change, not one

The obvious step — remove the writer's 5 m cut — is **not sufficient**, because of a second fact
that had been noted in one script comment (`scripts/extract_fdiff_individuals.py:26`) and never
carried into a decision record or the runbook:

> **`src/lpj/daily_natural.c:193` does `pft->agpp += npp;`.**

The per-individual accumulator named `agpp` holds **NPP**, not GPP — the field's own upstream
docstring in `include/pft.h` says "annual NPP" too. `fwriteoutput_ind.c` then writes it into the
`ind` table's **`gpp` column**. So:

* **the `ind` table's `gpp` column is a bit-identical duplicate of its `npp` column.** Measured on
  the global historic seed1 parquet at the five biome cells: a per-stem `npp/gpp` is **exactly
  1.0000 in all 11 967 tree rows**, 0 differing;
* **LPJmL-FIT has no per-individual GPP output at all**, so a per-stem carbon-use efficiency was
  never computable from any existing artifact, and the local `gpp` variable that *is* the real
  thing reaches only the stand-level `GPP`/`D_GPP` outputs and the cell-level `balance.agpp`.

**No published number in this repo is affected** — the `ind` `gpp` column is used nowhere as GPP
(every consumer reads `npp`), and the two probes that mention it already flag it. But it is why the
bracket existed, and it is now recorded here and in `CLAUDE.md` §3 rather than in one comment.

## 4. What was built (`patches/lpjmlfit_ind_true_gpp.patch`)

Two **independent** env switches, each **inert unless set**, so an unset run is stock LPJmL-FIT
(guardrail 4; same pattern as the rung-2 hooks):

| switch | effect |
|---|---|
| `LPJ_IND_ALL_HEIGHTS` | emit **every** tree, not only those above 5 m. `Height` is column 4, so a consumer can reproduce the stock cut exactly and the two populations stay separable. |
| `LPJ_IND_TRUE_GPP` | put a **new** accumulator `Pft.agpp_gross` in the `gpp` column instead of `agpp`. It accumulates the *same* `gpp` that `daily_natural.c` passes to `npp()` and adds to `D_GPP`, so it is gross-before-`rd` — exactly the stand GPP output's basis. |

Five points of design that are load-bearing:

1. **`agpp` itself is untouched.** Every committed reference basis in this repo is measured against
   it; "fixing" it would move them all silently.
2. **`agpp_gross` is diagnostic only** — nothing in the physics reads it, so the switches cannot
   change a trajectory even when set.
3. **It is not in `fwritepft`/`freadpft`.** Those serialize **field by field**, and like
   `anpp`/`agpp` this is an annual accumulator zeroed by `init_annual` → `init_tree`/`init_grass`
   (`init_annual.c:61-62` dispatches `init(pft)` **every year** — that is what makes `anpp` annual
   despite being zeroed only in the three creation/init functions). ⇒ **`restart_1999.lpj` still
   loads**; a wholesale `fwrite(sizeof(Pft))` would have broken it.
4. **The MPI pre-count must use the same height condition as `getind`.** The non-root rank sizes its
   buffer in one pass and fills it in the next; a mismatch overflows it. Both call the same helper.
5. **The 29-column schema and `printind` are unchanged**, so every existing parser keeps working.

## 5. The rebuild gate (mandatory; ADR 0061)

A rebuild changes the basis every F-vs-C number is measured against. Gated on a **matched pair** —
same config, same cell (42490), same `--ntasks=1`, **only the executable differing** (the previous
binary was preserved as `bin/lpjml.pre_indgpp.bak` and the "old" job file re-pointed at it, so this
is a true A/B and not a comparison against an older run whose output set predates the daily-grass
patch):

> **139 decoded quantities + `globalflux` identical, 0 differ** — with both switches unset.
> `scripts/diagnose_cbinary_rebuild_equality.py` (decoded variables, never `cmp` on a NetCDF — ADR 0043).

## 6. The result — the bracket is closed, and it lands near the middle

Five biome cells, historic 2000–2019, `npatch=25`, both switches on
(`scripts/run_ind_true_gpp_cells.sh` → `scripts/diagnose_ind_true_gpp.py`; fixture
`test/testitems/references/M_ind_true_gpp_reference.csv`).

**Its own gate, which is also a completeness proof.** The sum of per-individual `gpp` over **all**
PFT rows must reproduce the run's own annual `d_gpp` — two different code paths over the same daily
variable, and a tree missing from the roster would show up as a shortfall:

> **worst relative disagreement 4.4e-07 over 100 cell-years** (tolerance 2e-5, the writer's own
> `%g` six-significant-digit floor). **PASS.**

**What the 5 m cut hides** (decadal, patch-ensemble means):

| cell | >5 m share of tree GPP | CUE on >5 m | CUE on all trees | grass share of GPP | >5 m share of stem COUNT |
|---|---|---|---|---|---|
| `temperate_hainich` | **0.9812** | **0.4436** | 0.4439 | 0.075 | 0.530 |
| `tropical_amazon` | 0.9967 | 0.4062 | 0.4063 | 0.001 | 0.659 |
| `mediterranean_iberia` | 0.9708 | 0.2657 | 0.2686 | 0.289 | 0.426 |
| `boreal_siberia` | 0.7973 | 0.5490 | 0.5545 | 0.491 | 0.221 |
| `semiarid_sahel` | 0.7875 | 0.4001 | 0.4003 | 0.254 | 0.325 |

Three things to take from the table:

1. **At the prototype cell the sub-5 m trees carry only 1.9 % of tree GPP** while being **47 % of
   the stems.** The bracket's two ends assumed this factor was 1.0 and the crown-cover `gt5m`
   (~0.95 at Hainich, per ADR 0060's `a_fpc` ratio); the truth is 0.9812.
2. **The independent confirmation.** ADR 0129's `CUE_C` = 0.435 was `npp(>5 m)/gpp(all trees)`;
   dividing it by the measured share gives 0.435/0.9812 = **0.4433**, against the **directly
   measured 0.4436** — 0.07 % apart, from a different run and a different code path. That is what
   makes the correction a measurement rather than an assumption.
3. **`CUE` barely differs between the two populations** (0.4436 vs 0.4439 at Hainich) — so the
   population mismatch acted almost entirely through the **GPP** column, as ADR 0129 §3 predicted.

**The closed split at the prototype cell.** Recomputed in-process by
`scripts/biome_sapwood_bg_probe.jl` **PART 5d** (job `logs/M-gppclose.1767354.out`), which prints the
old and corrected columns side by side with `ln(NPP)` as an invariance check:

| basis | `GPP_F/GPP_C` | `CUE_C` | `CUE_F/CUE_C` | **photosynthesis share** |
|---|---|---|---|---|
| ADR 0129, mixed populations (PART 5b) | 1.080 | 0.435 | 1.140 | **38 %** |
| this ADR, both on F's >5 m roster (PART 5d) | **1.101** | **0.4378** | **1.134** | **43 %** |
| arm Pbg, same correction | 1.102 | 0.4378 | 1.092 | 52 % |

> **⇒ ≈43 % photosynthesis / ≈57 % respiration at Hainich (arm A); 52/48 on arm Pbg.**
> A hand re-scaling of ADR 0129's published panel by the measured share gives 47 %. **Quote the
> range 43–47 %, not a single figure** — the three routes differ by the basis residual below.

⚠ **THE INVARIANCE CHECK IS NOT EXACT, AND THAT IS INFORMATION, NOT NOISE.** `ln(NPP)` should be
untouched by this correction (the two factors are reciprocal), and it moves **0.2116 → 0.2215** —
i.e. the implied `NPP_C` is **0.99 % lower** than the global parquet's. The shift is **identical on
both arms** (arm Pbg: 0.1758 → 0.1857, also −0.99 %), which proves it is a property of the C
reference and not of any emulator arm: PART 5d takes `CUE_C` from these new single-cell runs while
PART 5b took `npp_C` from the **global** run's `ind`, and basis fact 3 already measures those two C
runs as agreeing to **<1.2 %** at four of five cells. So the check did its job — it detected the
basis substitution and priced it at the documented magnitude. **It also means PART 5d is now the
first version of this panel with all three C quantities on ONE run**, which is the better basis; the
residual is the size of the improvement, not an error in it.

⇒ **The bracket's upper end is refuted.** ADR 0129 §6 flagged that a 78 %-photosynthesis answer
would land within a point of the independently documented **+17 % GSI-phenology GPP level** and said
"if the writer-cut change confirms the upper end, the phenology is where to look first". **It does
not confirm it** — the measured GPP excess is **+10.1 %**, not +18 % — so **the phenology is not the
single cause**, and the respiration channel is the slightly larger half at the prototype cell.

⚠ **Two cells' levels are still not like-for-like.** `boreal_siberia` and `semiarid_sahel` have a
**~0.79** share, i.e. a fifth of their tree GPP is below the writer's cut and therefore absent from
F's roster too. The split is now *defined* there; the *level* is not a stand comparison. Read the
share beside every number.

## 7. Consequences

* **The `sapwood_bg` port and the `rd` gate act on the CUE channel**, now measured at 53 % of the
  assimilate error rather than ADR 0129's 62 % (or its 38 % lower end read the other way). ADR 0129
  §5's re-pricing stands in shape; its justification remains the **allocation** criterion `t_nosink`
  (ADR 0127 §6), not CUE.
* **Any future `ind`-derived stand aggregate can drop the ">5 m" caveat** by setting
  `LPJ_IND_ALL_HEIGHTS` and re-running the cell (~10 s). The caveat in ADR 0060/0125/0127 is not
  retired retroactively — those numbers stay on their own basis — but no new one needs to carry it.
* **The switches are opt-in with a default that is CORRECT, not known-wrong**, so guardrail 4's
  corollary (a flip criterion must be pre-registered) does not apply: the stock behaviour is the
  reference basis on purpose, and a run wanting the diagnostic sets the variable.
* **Line S shares this C tree and this binary.** The rebuild happened with their queue empty, their
  previous binary is preserved at `bin/lpjml.pre_indgpp.bak`, and the equality gate above covers
  their arms too (both switches unset ⇒ identical). Raised in their `STATE.md`.

## 8. Alternatives rejected

* **Remove only the height cut.** Insufficient — without a real per-stem GPP the CUE column stays
  uncomputable and a per-stem `npp/gpp` remains exactly 1.
* **Fix `agpp += npp` to `agpp += gpp` in place.** Rejected: it silently redefines an existing
  output column that committed fixtures are built on. The new field is additive.
* **A new `ind` column for gross GPP.** Rejected: it breaks the frozen 29-column `IND_COLUMNS`
  schema and every reader of it. The switch reuses the existing (mislabelled) column, and the
  default is unchanged.
* **Estimate the sub-5 m GPP share from crown cover.** That *is* ADR 0129's upper bracket end, and
  the measurement shows it wrong at Hainich (0.9812 measured vs ~0.95 assumed) — a small absolute
  gap that moves the split by ~9 points.
* **Regress the ratio on `gt5m` harder / with more years.** ADR 0129 §4 already showed the estimator
  has no power at this window length; more of the same statistic cannot fix `SE(slope)` 3.63.
