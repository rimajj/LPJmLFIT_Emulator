# ADR 0104 — the pre-registered flip criterion was scored on the wrong quantity: the anchor acts on the STAND, not on the prediction

* **Status:** Accepted
* **Date:** 2026-08-06
* **Line:** S (Component-S science) · ADR block 0100–0119 (tier 2)
* **Supersedes, in part:** **ADR 0103 §6**'s flip criterion clauses (i) and (ii), and its `Decides` (4)
  recommendation of `anchor = 0.1`. **ADR 0103 §1–§5 stand unchanged** — the constant, the mechanism, the
  opt-in shipping decision, the Hainich retention measurement and the `patch_area`-travels-with-the-artifact
  rule are all unaffected. What is corrected here is only the **yardstick** the criterion named, and the
  recommended value that was derived on it.
* **Decides:** **(1)** the ADR-0103 §6 criterion, evaluated exactly as written, **FAILS** — independently
  reproduced by line S (job 1716500) and line M (job 1716489) to the same digits; **(2)** it fails because
  it is scored on `s.target_history`, the count model's **prediction**, which the anchor does not act on —
  the anchor acts on the **roster density**, and its effect on the prediction is a second-order feedback;
  **(3)** the criterion is **re-specified** to score the physical stand against the C's per-patch mean ÷
  `patch_area`, an argument that follows from the update equation and does **not** depend on the results;
  **(4)** on the corrected yardstick the anchor improves **all five cells at all three settings tested**
  (`a` = 0.1 / 0.25 / 0.5), mean score **0.679 → 0.478 / 0.361 / 0.329**; **(5)** the default is
  **NOT flipped in this session** — two named confounds must clear first (§5), and neither is a matter of
  judgement; **(6)** the revised recommendation is **`anchor = 0.25`**, not 0.1.
* **Concurrent and agreeing:** **ADR 0056** (line M), written the same day from the same runs without
  coordination. M reaches the same verdict (criterion FAILS, clause (i) mis-specified, do not tune `a`) and
  independently identifies Sahel as a **closed feedback loop** `density → fpc → target → density` that the
  open-loop ratio never closed. **The two ADRs differ on one number and the difference is the yardstick:**
  M's "the anchor fires perfectly — 1.001 in all five cells" is stand ÷ its own count model's *target*
  (self-consistency); §3 below is stand ÷ *the C's truth* (accuracy). On the truth measure `a = 0.5` leaves
  Sahel at 0.33×, which is why the recommendation here is 0.25 and M's is 0.5. Neither is wrong; they answer
  different questions. M's stability check (read the per-year `fpc` shape for a monotone collapse) is adopted
  into §7.
* **Related:** ADR 0103 (the anchor; §6 corrected here), ADR 0102 (the defect), ADR 0054/0055 (line M's
  coupled oracle and resilience battery, the harnesses used), ADR 0053 (the reference-basis checks),
  ADR 0031 (the defect class this session was trying not to repeat: a global default flipped on
  single-cell evidence), CLAUDE.md §6 guardrail 4 and its corollary, and the `residual-diagnosis` skill
  (state the reference basis **before** the hypothesis — the rule this ADR is an instance of failing).
* **Evidence:** `scripts/biome_slow_oracle_probe.jl` REPORT 7, opt-in via `ANCHOR=<a>`. Jobs **1716498**
  (`a`=0.1), **1716499** (0.25), **1716500** (0.5), all five biome cells, historic 2010–2019, pinned `_t8`
  artifact pair, `wscal_leafon = true`, scored against the C `ind` truth in seed1-vs-seed2 noise floors.
  Line M's independent run of the same criterion: job **1716489**. Memory arm:
  `scripts/biome_resilience_probe.jl` arms `lvl0`/`lvl1`, job **1716491**.

## 1. What the criterion said, and what happened

ADR 0103 §6 pre-registered the flip, which is the right instinct and is why this ADR can be written at all:

> Flip the default to `anchor = 0.1` iff (i) the monotone drift is removed in the three drifting cells,
> (ii) the two cells at the noise floor STAY there, and (iii) carbon still closes ≤1e-6·C_scale in all five.
> **If it fails in any cell, that failure is the finding**; tell S rather than tuning `a` to make it pass.

Evaluated verbatim, at `a = 0.5` on the 10-year horizon §6 itself specified:

| cell | role | drift free | drift anchored | gate metric free | gate metric anchored | clause |
|---|---|---|---|---|---|---|
| boreal_siberia | drift | 1.561 | 1.460 | 11.1 | 9.9 | FAIL |
| temperate_hainich | drift | 1.298 | 1.201 | 4.5 | 3.2 | FAIL |
| mediterranean_iberia | drift | 1.842 | 1.245 | 13.9 | 5.8 | FAIL |
| semiarid_sahel | floor | 0.795 | 0.277 | 1.4 | **3.7** | FAIL |
| tropical_amazon | floor | 1.030 | 1.016 | 0.5 | 0.6 | PASS |

Clause (i) fails: the three drifting cells flatten (15 %, 30 %, 64 % of the log-drift removed) but none
reaches 1.00. Clause (ii) fails: `semiarid_sahel` goes from 1.4 noise floors to 3.7. Clause (iii) passes
everywhere (max handoff residual ≤ 1e-9 · the tolerance, all arms, both lines' runs).

**The failure is not a `a = 0.5` artifact.** Sahel degrades monotonically in `a`: 1.4 → **1.9** (0.1) →
**2.3** (0.25) → **3.7** (0.5). Nothing here was tuned; the sweep was run to characterise the failure, and
it made it worse-looking, not better.

## 2. Why the criterion cannot decide this — the argument from the update equation

`slow.jl:1066-1070` is the entire intervention:

```julia
a = s.anchor
if a > 0 && dtree > 0 && s.patch_area > 0
    d_want = target / s.patch_area
    d_want > 0 && (r = r^(1 - a) * (d_want / dtree)^a)
end
```

`r` multiplies the **roster** (`dtree`, stems/m²). `target` appears only on the right-hand side, as the
thing being aimed at. **The anchor never writes `target`.** So `s.target_history` — which the criterion
scores — can move only through a second-order loop: the anchor moves the stand, the stand changes the
canopy features (`fpc`, `lai`, `agb`, `age_mean`, `n_prev`) that `flux_feature_vector` builds, and the DRF
is then fed a different row next year. Scoring `target_history` measures **that feedback**, not the
intervention, and the feedback has its own sign per cell.

This is not a post-hoc rationalisation of an inconvenient result: it is readable off the seven lines above
without running anything, and it would have been just as true if every cell had passed. It is a plain
instance of the `residual-diagnosis` rule — *state the reference basis before the hypothesis* — applied to
a criterion instead of to a residual. §6 was written in the same session that built the anchor, against the
metric that harness already printed, and nobody asked whether that metric was the one the change acts on.

Line M's own run makes the point without needing this argument. Their last table asks "did the anchor
fire?" — stand density × `patch_area` ÷ the DRF's own target, 2019:

| cell | free | `a` = 0.5 | `a` = 0.1 |
|---|---|---|---|
| boreal_siberia | 1.459 | **1.001** | 1.158 |
| temperate_hainich | 1.486 | **1.001** | 1.166 |
| mediterranean_iberia | 1.665 | **1.001** | 1.218 |
| semiarid_sahel | 1.635 | **1.001** | 1.210 |
| tropical_amazon | 2.214 | **1.002** | 1.361 |

The anchor does exactly what it was built to do, in every cell, to three digits — while the criterion
scores it FAIL in four of five. Two tables that disagree that completely are not measuring one thing.

## 3. The corrected yardstick, and the result on it

The quantity the anchor acts on is the roster density. Its truth is the C's per-patch ensemble mean
`n_mean` ÷ `patch_area` — the same stems/m² basis, and the same per-patch quantity the count DRF was
trained on (ADR 0053's reference-basis check, unchanged). Score:

> `score = mean_y | ln( density_y / truth_y ) |`

a year-matched log error, **symmetric in over- and under-shoot**, so an anchor that overshoots is penalised
exactly as hard as the over-density it replaced. Lower is better; 0 is perfect.

| cell | free | `a` = 0.1 | `a` = 0.25 | `a` = 0.5 |
|---|---|---|---|---|
| boreal_siberia | 0.740 | 0.605 | 0.499 | **0.405** |
| temperate_hainich | 0.618 | 0.434 | 0.320 | **0.242** |
| mediterranean_iberia | 0.802 | 0.619 | 0.449 | **0.237** |
| semiarid_sahel | 0.607 | 0.377 | **0.373** | 0.557 |
| tropical_amazon | 0.627 | 0.352 | **0.165** | 0.203 |
| **MEAN** | **0.679** | 0.478 | **0.361** | 0.329 |

**Every cell improves at every setting.** The terminal density ratio (stand / truth) tells the same story:
boreal 2.55× → 1.63×, Hainich 2.03× → 1.26×, mediterranean 3.01× → 1.22×, Amazon 1.90× → 0.85× at
`a` = 0.5. Sahel is the one non-monotone cell — 1.55× → 0.78× / 0.53× / **0.33×** — it crosses the truth
between `a` = 0.1 and 0.25 and overshoots badly at 0.5, which is why its score turns back up.

**Hence `a = 0.25`, not `a = 0.1`.** 0.25 is the best mean score of the settings whose worst cell is still
an improvement, and it is the best setting for Sahel specifically. 0.5 wins the mean but only by pushing
Sahel from a 55 % over-density to a 67 % **under**-density, which is a worse stand by any symmetric measure
and is exactly the "relax, don't force" caution ADR 0103 §3 already recorded at Hainich.

## 4. Sahel is a real defect, and it is not the anchor's

Sahel deserves naming rather than absorbing into a mean. It is the only cell where the anchor makes the
count model's own prediction worse, and it does so by a mechanism worth writing down: pulling the stand
down lowers the canopy features, the DRF then predicts fewer trees, and the anchor chases its own falling
target. Free-running, Sahel's prediction is nearly right (0.95× the C) while its stand is 1.55× too dense —
the two disagree. The anchor makes them agree, at 0.33× of truth. **It converted a disagreement into a
consistent wrong answer**, which is a more dangerous failure mode than the disagreement, because
self-consistency reads as correctness.

This is the count model's sensitivity to its own canopy features exceeding the anchor's restoring strength
in the driest cell of the set — a **training-side** property (the exposure bias of ADR 0102's defect (A),
already S's #1 remaining item), surfaced by the anchor rather than caused by it. The anchor is what made it
visible: unanchored, this cell looked fine on the gate metric while carrying a 55 % level error nothing
could see.

## 5. Why the default is NOT flipped today

Neither reason is judgement; both are measurable and both are already scheduled.

1. **The modal-patch confound.** The driver initialises from the **modal** patch, 1.12–1.72× denser in FPC
   than the 25-patch ensemble mean the DRF was trained on (line M's STATE item 2). Every free arm above
   therefore starts 1.56–1.95× above its truth, and part of what the anchor "fixes" is that initialisation
   offset rather than recursion drift. The corrected criterion must be re-run **on the ensemble driver**,
   which is M's pending change, before the improvement can be attributed. Note this cuts both ways: it
   means the anchor's measured benefit here is an **upper** bound, and the underlying level defect is real
   regardless (ADR 0103 §2 measured it at Hainich under constant forcing with no such confound).
2. **The memory arm** (§6) had to be run and read, because a level fix bought by flattening the emulator's
   own year-to-year dynamics is not a fix.

**Guardrail 4's corollary applies and is explicitly not being used as cover.** `anchor = 0` remains a
known-wrong default — the free-running column of §3 is the size of it, 1.9–3.0× the right density in five
of five cells. This ADR extends the measurement cycle by exactly one arm; it does not reopen the question
of whether to enable.

## 6. The memory arm

`scripts/biome_resilience_probe.jl` gains `lvl0`/`lvl1` — the level anchor on ordered and on shuffled
forcing — opt-in on the same `ANCHOR` variable. They are **not** the existing `anchor0` arm, and conflating
the two would have wasted the run: `anchor0` is **teacher forcing**, which overwrites the AR feature with
an externally measured series and therefore *injects* that series' memory. That is why line M's ADR-0055
battery found `anchor0` degrades the lag-1 autocorrelation (`tropical_amazon` 0.066 against a C of 0.501).
The level anchor writes no feature at all, so M4's caveat — "whatever S lands must be scored on the AC as
well as the level" — is answered by `lvl1`, not by `anchor0`.

**Result — the anchor does NOT cost the memory (job 1716491, `a` = 0.5, shuffled forcing, lag-1 AC,
5 cells × {`n`, `agb`}).** The right statistic is the distance to the **oracle**, not to the free arm: the
free arm sits *above* the C's autocorrelation in 9 of 10 pairs, so a change that lowers the AC moves toward
the truth while showing as a negative `lvl − free`.

| statistic over the 10 cell-variable pairs | `free1` | `pin1` (no count AR) | `lvl1` (anchored) |
|---|---|---|---|
| mean \|AC − C's AC\| | 0.0439 | 0.0975 | **0.0405** |

The anchored arm is **closer to the oracle than the free arm in 6 of 10 pairs and better on the mean**. The
largest individual moves are toward the C, not away: boreal `n` 0.637 → 0.548 against a C of 0.568, boreal
`agb` 0.600 → 0.565 against 0.569, Sahel `agb` 0.653 → 0.620 against 0.557. No pair collapses toward the
no-recursion control (`lvl − pin` is ≥ −0.19 and mostly near zero).

**Contrast with teacher forcing, which is why the two had to be separated:** `anchor0` drives Amazon `n` to
**0.066** against a C of 0.501; the level anchor leaves it at **0.549**. M4's caveat is real for the arm it
was measured on and **does not transfer** to this one.

**One clause of the re-registered criterion below already fails on today's data, and is recorded rather
than softened.** The 100-year cycled-forcing biomass drift (honest answer 1.00) is improved in 2 cells
(Hainich 3.14 → 2.46, Sahel 4.65 → 3.13), unchanged in 1 (boreal 5.15 → 5.14) and *worse* in 2
(mediterranean 2.87 → 3.01, Amazon 1.39 → 1.49). That is consistent with the mechanism and is not a
surprise: the anchor fixes the **count** level, while this drift is in **biomass**, which is F's carbon
pools. It does say plainly that the anchor is not a fix for long-horizon biomass drift, and nothing in
ADR 0103 or here should be read as claiming it is.

## 7. Re-registered criterion (for the next cycle — pre-registered again, on the corrected yardstick)

Flip the default to `anchor = 0.25` iff, **on the patch-ensemble driver**:

1. the stand score of §3 improves in **all five** cells and no cell's terminal density ratio crosses from
   over- to under-shoot by more than it improves in log terms (the Sahel guard, stated as a threshold and
   not as a judgement);
2. the mean \|AC − C's AC\| over the 10 cell-variable pairs is **no worse** than the free arm's, and no
   single pair moves *away* from the C by more than 0.05. **Stated against the ORACLE and not against the
   free arm**, because the free arm is not the truth — the same mistake this whole ADR is about, and it
   would have been made again here: `lvl − free` reads as a degradation in 8 of 10 pairs while the distance
   to the C improves. (Passes today at `a` = 0.5 on the mean; the per-pair clause is new and untested.)
3. carbon still closes ≤ 1e-6 · C_scale in all five (unchanged; it has passed in every arm of every run so
   far, both lines'), **and** — adopted from ADR 0056 — the anchored arm's per-year `fpc` shows no monotone
   collapse in any cell. This is a **stability** clause beside the skill ones, and Sahel is why it exists:
   a setting can improve the level score while closing a runaway loop, and only the shape shows it.
4. **no clause on the 100-year biomass drift.** It was in the first draft of this list and is deliberately
   removed: §6 measures it as 2 better / 1 flat / 2 worse, and the mechanism says it should be — that drift
   is in F's carbon pools, which the anchor does not touch. Gating a count-level fix on a biomass-drift
   metric would be the same category error a second time. It stays **reported** in every anchored run, as a
   fact about the coupled model that the anchor neither causes nor cures.

If any clause fails, that failure is the finding — and this time the yardstick has been checked against the
update equation first.

## 8. The method rule, which is the durable part

**A pre-registered criterion is only as good as its yardstick, and the yardstick has to be derived from the
change, not from the harness that happens to be at hand.** Pre-registration protected against tuning `a`
until it passed — it worked, and it should stay. What it cannot protect against is measuring the wrong
quantity, because the commitment is made at the moment of least information about the intervention.

The cheap check that would have caught this, and which should be applied to every future pre-registration:
**read the diff, name the variable the change writes to, and confirm the criterion's metric is a function
of that variable.** Here the change writes `r`, which multiplies `dtree`; the criterion scored
`target_history`, which the change never writes. Seven lines of code and one question, before the run.

Its sibling rule, from §6: **when a control arm and a truth disagree, score against the truth.** The memory
arm was about to be read as `lvl − free`, which would have reported a degradation in 8 of 10 pairs on a
statistic where the anchored arm is in fact *closer to the oracle*.
