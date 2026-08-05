# ADR 0102 — "the count recursion is unanchored" is THREE defects: the clamp incoherence is empty, the exposure bias is training-side, and the one that dominates is a missing LEVEL anchor

* **Status:** Accepted
* **Date:** 2026-08-05
* **Line:** S (Component-S science) · ADR block 0100–0119 (tier 2)
* **Answers:** **ADR 0054** (line M, M3's S side) — the inbound integration point *"the count recursion is
  unanchored; any fix touches `src/components/slow.jl` = line S's exclusive path, so raise it with S"*.
  M's diagnosis is confirmed, its name for the defect is the right one, and — after M's **same-day
  refinement** (`9ad8721b`, 2026-08-05 13:07, which landed while this probe was running) — its
  decomposition is right too. **Credit where it is due: M already separated the two effects.** Their
  refinement splits the +36–81 % ten-year excess into a **recursion factor** `free₂₀₁₉/forced₂₀₁₉` of
  **×1.26–1.53** (a compounding 2.6–4.9 %/yr) and a **year-1 level offset** of **×1.05–1.12**, and states
  that "neither is the whole number". What this ADR adds is not the existence of the level term but its
  **fate**: M measured a level offset *at year 1* and reasonably read it as an initialisation artifact.
  It is not one. It is **permanent**, and so is any level error acquired at any later time, because the
  coupled loop contains **no mechanism whatever** for correcting a level.
* **Decides:** **(1)** the defect is decomposed into three named mechanisms with three different owners and
  three different fixes, and future work is routed accordingly; **(2)** mechanism (B), state incoherence
  between the clamped ρ and the unclamped `n_prev`, is **measured empty** and is closed — no session should
  spend time on it; **(3)** mechanism (C), the absent level anchor, is recorded as the **dominant** defect
  in the coupled configuration and as the highest-value remaining S+M item, ranked **above** the
  trait-conditioning work of milestone S2; **(4)** the fix for (C) is **specified but deliberately not
  landed**, because it requires the count↔density conversion at the S↔F seam — an `interface.jl` addition,
  which is line M's — and moves every committed coupled baseline; **(5)** line M's `wscal_leafon` default
  flip is **pre-authorised from S's side** and unblocked in code.
* **Related:** ADR 0054 (the finding this answers), ADR 0024 (the dynamic roster and the `age_mean`
  train/inference trap — the same defect class one field over), ADR 0023 (train/inference consistency;
  mechanism (A) is that trap in the AR state), ADR 0101 §5 (the `n_init`/`age0` 4.5×-FIT swing — the same
  structural property seen as an artifact quirk), ADR 0048 (the constant-forcing relaxation and the merge
  dormancy protocol), ADR 0051 (the `wscal_leafon` port and the measurement that pre-authorises the flip),
  ADR 0029 (the ownership map that makes this an integration point rather than an edit), CLAUDE.md §6
  guardrails 4, 6 and 7
* **Evidence:** `scripts/diagnose_count_recursion_anchor.jl`. Jobs **1705514** (sections a/b),
  **1705626** (a/b/c, 150 yr), **1705645** (300 yr horizon sweep). Hainich cell 42490 only, constant
  repeated-2010 forcing (the ADR-0048/0049 basis), committed demo artifact pair
  `drf_forest_hainich.drf` + `recruit_copula_hainich.rcop`, `n_init` 11.0 / `age0` 43.5556, seed 1.

## Context

ADR 0054 measured that a free-running coupled rollout integrates a ~5 %/yr one-step count bias into
**+36–81 % over ten years**, and that overwriting `s.n_prev` with the C's own per-patch count each year —
teacher forcing — removes **59–72 %** of the total coupled count error in all five biome cells and flattens
the drift. M correctly refused to fix it inside `slow.jl` and raised it.

Two things about that result are worth stating before the measurement, because they are what this ADR turns
on. First, "unanchored" is a name for a symptom, and at least three distinct mechanisms produce it. Second,
**teacher forcing removing only 59–72 % is itself a clue that was not read**: if the whole defect were the
compounding of the AR state's own error, putting the truth back into the AR state every year would remove
substantially all of it. Something the teacher-forced arm does not touch is carrying the remainder.

## Decision

### 1. Three mechanisms, three owners

| | mechanism | where | owner | measured here |
|---|---|---|---|---|
| **A** | **Exposure bias.** The training `n_prev` is the C's own previous `n_living` (`build_slow_runtime_table.py:572`, a `shift(1)` of the truth); the runtime feeds the DRF its own output (`slow.jl:1110`). | training basis | **training-side** — scheduled sampling, or dropping `n_prev` from the feature set. Needs a global retrain. | present, not quantified here |
| **B** | **State incoherence.** `slow.jl:1026` clamps `ρ = clamp(target/n_prev, 1−max_mort, 1+max_estab)` and applies the **clamped** ρ to the roster; `slow.jl:1110` then assigns the **unclamped** `target` to `n_prev`. A clamp-binding year desynchronises the AR state from the physical stand permanently. | `slow.jl` | **S** | **EMPTY — 0 of 150 years** |
| **C** | **No level anchor.** ρ is unit-free and the roster is advanced multiplicatively, `D_T = D_0·Πρ_t`. The DRF's *absolute* count skill is used only through year-on-year ratios; its **level is discarded by construction**. Nothing in the loop states what `D` should be. | `slow.jl` + the S↔F seam | **S + M** | **retention 1.04** |

### 2. Mechanism (B) is measured empty, and this is a refuted hypothesis, recorded as one

(B) was S's leading hypothesis on reading ADR 0054, and it is attractive: it is a real code-level
inconsistency, it is S-owned, it needs no retrain, and a fix for it would have been byte-identical exactly
where the current behaviour is already coherent. It is also **wrong**. Over 150 years the clamp binds **0
times**, and the roster tracks the ρ it was handed to `max |coherence − 1| = 1.5e-13`. There is nothing to
fix.

Measuring it before implementing it cost one 4-minute job and saved shipping a fix for a defect that does
not occur — the same move, and the same lesson, as ADR 0048's "check the operator fired before believing a
null" and ADR 0100 §5's correct-measurement-wrong-cause. **A code-level inconsistency is a hypothesis about
the trajectory, not a defect, until the branch is shown to execute** (CLAUDE.md §3's `individual=true`
dead-path rule, applied to the emulator's own code rather than the C's).

One residual is worth naming so it is not rediscovered as a bug: the cumulative divergence is **1.0970**,
and all of it is year 1, where `s.year == 0` forces ρ = 1 while `n_prev` still takes the DRF's first
`target`. That is a one-time **re-basing** of the count↔density mapping, not a drift — only ratios are used
thereafter — and it is what the constructor docstring means by `n_init` "only sets the year-0 feature".

### 3. Mechanism (C) is the dominant defect, and it is new

`ρ` is a ratio and the roster is advanced by it multiplicatively. `slow.jl:779` documents this as a
*feature* — the unit-free ratio is what lets a per-patch count target drive a cohort-density roster without
knowing the patch area. The measurement is of what that costs.

**Perturb the initial stand density and hold everything else fixed** — same forcing, same seed, same
artifact, same `n_init`. A stand with a level anchor relaxes back:

| `D₀` scale | treedens[50] | treedens[100] | treedens[150] |
|---|---|---|---|
| 0.50 | 0.018340 | 0.020114 | 0.022336 |
| 0.75 | 0.028383 | 0.029246 | 0.028679 |
| 1.00 | 0.042812 | 0.042281 | 0.042281 |
| 1.50 | 0.071096 | 0.070214 | 0.070214 |
| 2.00 | 0.095148 | 0.093968 | 0.093968 |

A **4.00×** spread in initial density is still a **4.21×** spread after 150 identical-forcing years —
**retention 1.036**. Not damped; very slightly amplified.

**The horizon sweep is what makes this conclusive** (job 1705645, 300 yr). A weak restoring force with a
long time constant would show as retention decaying steadily toward 0. It does not: it *rises* to a peak of
**1.40 at year 25** — the perturbation is transiently **amplified** — then relaxes to **1.036 by year 150**
and then **stops**, holding flat to year 300.

| year | 10 | 25 | 50 | 100 | 150 | 200 | 250 | 300 |
|---|---|---|---|---|---|---|---|---|
| retention | 1.072 | **1.401** | 1.188 | 1.112 | 1.036 | 1.037 | 1.046 | **1.037** |
| spread (×) | 4.42 | 6.97 | 5.19 | 4.67 | 4.21 | 4.21 | 4.26 | 4.21 |

Retention converges to a **non-zero asymptote of ≈ 1.04**, not to 0, and holds it for a further 150 years.
The initial level is retained essentially in full, permanently. There is no restoring force — not a weak
one, none.

**The dissociation that makes this a finding rather than a restatement.** An `n_init` sweep (7 → 15, a 73 %
spread) shows the **AR state** converging almost completely — terminal `target` spread 6.7 %, retention
**0.092**, with four of five seeds landing on an identical 6.7529 — while the **physical density** those
same runs carry retains **60.2 %** of its spread. So the constructor docstring's claim that `n_init` is
"self-corrected by the `max_*` clamp thereafter" is **true of the AR state and false of the stand**. The
DRF's target has an attractor; the roster does not, because the target's level never reaches it.

**This is what explains M's 59–72 %, and it completes M's own decomposition.** Teacher forcing repairs the
**ratio** each year by putting the C's count back into the feature row. It does not repair the **level**,
because the level is `D₀·Πρ` and no value of `n_prev` enters that product except through ratios. So M's
**×1.05–1.12 year-1 level offset** survives teacher forcing untouched — which is precisely why their forced
arm flattens the *drift* (boreal 1.12→1.74 becomes a flat 1.12–1.17) while **retaining the offset it started
with**: 1.12, not 1.00. That flat-but-displaced trace is the level anchor's absence, visible in M's own
published numbers.

M attributed the year-1 offset partly to the modal-patch initialisation, which is right about where it comes
from. The measurement here is about what happens to it afterwards: **nothing**. It neither decays nor is
corrected, and the same is true of any level error the run acquires later — from a clamp-binding year, a
k-cap merge, a hazard shortfall, or simply an imperfect year. Each one is added to the level permanently.
An initialisation artifact that never decays is not an initialisation artifact; it is a free parameter.

### 4. The fix is specified and deliberately not landed

Anchoring the roster to the DRF's absolute target requires the count↔density conversion — the per-cell
patch area — at the S↔F seam. That is precisely the quantity the ratio formulation was designed to avoid
needing, so this is a contract change, not a patch:

* an addition to `src/interface.jl` (**line M's exclusive path**) to carry patch area, or an equivalent
  per-cell scalar in `cell_meta.parquet`;
* a change in `reconcile_demography!` (**S's**) to blend the multiplicative update toward the absolute
  target rather than replacing it outright — a partial anchor with a stated relaxation time is the right
  shape, since a hard anchor would discard F's own stand dynamics and re-introduce the count↔density
  calibration error as a level error;
* **it moves every committed coupled baseline** ⇒ a deliberate regeneration under guardrail 4, in its own
  commit, with its own matched control;
* and it must be scored on the teacher-forced arm as well as the free arm, or the ratio and level effects
  will be confounded again.

It is not landed here because a one-session unilateral change to a cross-line contract is exactly what
ADR 0029 exists to prevent, and because the arm that would validate it is line M's five-cell coupled probe.
It is raised in `lines/M/STATE.md` and recorded as the first action of a resumed S line.

### 5. Line M's `wscal_leafon` flip is pre-authorised and unblocked in code

Unrelated to the recursion, but blocking M and recorded in `lines/M/STATE.md` as "S's to schedule":
`slow_production_drf_tests.jl` asserted the out-of-band conditioning set is **exactly** `{water_stress}`, so
flipping `WaterParams.wscal_leafon` to its C-faithful default would have turned S's suite red and therefore
needed a synchronised two-sided commit. The assertion now admits **exactly the two admissible states** —
`{water_stress}` with the flag off, the **empty set** with it on — and still fails on any third outcome. S
endorses the flip on M's own measurement (ADR 0051): Hainich's `water_stress` goes **0.3050 → 0.0034**
against a C truth of 0.0014 and a trained band of [0, 0.04315], so the flip **closes S's last out-of-band
conditioning column** rather than merely being more faithful. M can now land it alone.

## Consequences

* **Milestone S2 is no longer the top of the queue.** ADR 0101 left the recruit conditioning as "the only
  lever the finding points at". That was true of the *response* defect. It is not true of the coupled
  configuration, where an unanchored level makes the stand's density a function of its initialisation
  forever — a defect that compounds without bound and that no amount of conditioning skill can correct,
  because the channel that would carry the correction is discarded upstream of the conditioning.
* **`n_init` is a first-class parameter of every coupled answer, not an initialisation detail.** ADR 0101 §5
  measured a 4.5×-FIT swing from `n_init` 11.0 → 7.0 and treated it as a property of a badly-specified
  artifact. It is a property of the **recursion**: retention ≈ 1 means every per-cell seed is carried
  forever. This raises the stakes on integration point #2 (the pooled artifact's missing `cell_meta.parquet`)
  from a provenance defect to a correctness one.
* **Line M's M4 resilience battery needs this caveat.** M already noted that an unanchored AR recursion
  produces autocorrelation and slow recovery, and warned that the shuffle test could not otherwise separate
  internal memory from recursion memory. The measurement sharpens it: with retention ≈ 1 the level is a free
  integrator, so recovery-rate and lag-1 statistics from the free arm are upper bounds and the battery must
  be run on both arms.
* **Nothing in the shipped emulator changes.** No committed baseline, artifact, fixture or default moved;
  the only code change is the widened assertion of §5, which passes identically under today's default.
  Runtime `[deps]` stays empty.
* **M's proposed teacher-forced re-run of the ADR-0100 2×2 is DECLINED, and the reason is a superseded
  premise, not the merit of the arm.** M suggested it on the grounds that ADR 0100 found the baseline
  warming response wrong-signed at −2.44× FIT on free-running 81-year rollouts, so an unanchored recursion
  is "a candidate contributor … separable at zero training cost". That reasoning was sound when written,
  but **ADR 0101 withdrew the premise**: on the deployment artifact `R_ctl` is `−0.000 ± 0.367`, and the
  −2.44× was a single-cell demo-*fixture* property that reverses sign on a global artifact. There is no
  wrong-signed response left to attribute. The arm would now be measuring a recursion contribution to a
  response that is already indistinguishable from zero, at 12 seeds a corner to see past the noise. If it
  is ever run, it must be as an ensemble (ADR 0101 §1), never as one draw.
* **Reporting.** `docs/component_s_public_report.tex` listed recursive stability as "not yet tested — no
  evidence either way". There is now evidence and it is negative; the report is corrected in the same
  commit rather than left to imply an open question.

## Alternatives rejected

* **Ship the (B) re-sync anyway, "since it is free and obviously more correct".** It is free and it is more
  correct, and it would have been a fix with no measured defect behind it, in a file whose every change
  costs a baseline regeneration and a review. The clamp binds 0 of 150 years; if a configuration is ever
  found where it binds, this ADR is the record of what to do.
* **Anchor `D` to the absolute target unilaterally, inside `slow.jl`, using `n_prev` as the scale.** This is
  the tempting one-line version and it is wrong: `n_prev` is in per-patch count space and `D` in density
  space, and their ratio is exactly the unknown patch area. Using one as the other silently substitutes a
  calibration constant of 1 and would convert a level *drift* into a level *bias* — worse, because it would
  look anchored.
* **Retrain without `n_prev` to kill (A), and call the recursion fixed.** (A) is real, but the measurement
  says the level is unanchored *regardless* of how good the one-step prediction is: retention is 1.04 with
  the existing forest and would stay ~1 with a perfect one. Removing `n_prev` would remove the compounding
  and leave the free integrator in place, at the cost of a global retrain.
* **Report M's 59–72 % as the size of the S-side defect.** It is the size of the *ratio* defect. Quoting it
  as the whole would have hidden the level component, which is the part that does not saturate.
