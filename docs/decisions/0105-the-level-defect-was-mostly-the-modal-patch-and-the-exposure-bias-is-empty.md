# ADR 0105 — the anchor does NOT get the default: on the patch ensemble the level defect is 4× smaller, the anchor makes it worse, and the exposure bias behind it is measured empty

* **Status:** Accepted
* **Date:** 2026-08-06
* **Line:** S (Component-S science) · ADR block 0100–0119 (tier 2)
* **Supersedes, in part:** **ADR 0104 §3** (the corrected-yardstick result and its `Decides` (4)/(6)
  recommendation of `anchor = 0.25`) and **ADR 0104 §5**'s framing of `anchor = 0` as a known-wrong default
  on a timer. Both were measured on the **modal patch**, which ADR 0104 §5 itself named as an open confound
  and called an **upper bound** — closing it removes most of the effect and reverses the sign of the
  recommendation. **ADR 0103 §1–§5 still stand**: the constant, the mechanism, the opt-in shipping decision
  and the 300-year Hainich retention measurement are all unaffected by this ADR (§6 below says exactly
  which part of ADR 0103 survives and why).
* **Also corrects:** **ADR 0102 §2 / ADR 0054**'s reading of teacher forcing. On the ensemble basis,
  overwriting `s.n_prev` with the C's own previous count makes the physical stand **worse in all five
  cells**, not better (§4).
* **Decides:**
  **(1)** ADR 0104 §7's re-registered criterion, run on the **25-patch ensemble**, **FAILS at all three
  settings** (`a` = 0.1 / 0.25 / 0.5) — clause 1 at every setting, clause 3b at 0.25 and 0.5, and clause 2
  at the recommended 0.25. **The default stays `anchor = 0`.** No code, artifact, baseline or default moves
  in this ADR.
  **(2)** ADR 0104 §3's headline — "the anchor improves all five cells at all three settings" — is an
  **artifact of the modal-patch basis**. On the ensemble it improves 3 of 5 and **worsens the mean**
  (0.159 → 0.166 / 0.181 / 0.194).
  **(3)** The free-running level error is **4× smaller** than the modal basis showed (mean score 0.679 →
  **0.159**; terminal density ratios 1.90–3.01× → **1.04–1.38×**, with `semiarid_sahel` at **0.52×**, i.e.
  under-dense, where the modal basis said 1.55× over). ⇒ **`anchor = 0` is NOT a known-wrong default at a
  10-year coupled horizon** and guardrail 4's corollary no longer has a pending flip to enforce. §6 says
  what remains, and it is not nothing.
  **(4)** The **exposure bias** (ADR 0102 defect (A)), line S's #1 remaining item and the thing a global
  retrain was being contemplated for, is **MEASURED EMPTY on its own terms**: one-step bias **−0.0014**
  stems/patch/yr held-out-cell OOS on counts of ~10, AR gain **g = 0.56** ⇒ a **bounded** amplification of
  **2.28×** to an asymptote of −0.038 stems. **Do not buy the retrain.**
  **(5)** The residual is **the count model fed F's own canopy features**, not anything in the count
  model's training. That is a coupling/F-fidelity question, and it is where the next work goes.
* **Related:** ADR 0104 (the criterion this closes), ADR 0103 (the anchor), ADR 0102 (the defect
  decomposition), ADR 0057 (line M, which moved the coupled driver to the ensemble and made this
  measurable), ADR 0053 (the reference-basis checks and the modal/ensemble FPC artifact), ADR 0056 and
  ADR 0054/0055 (line M), CLAUDE.md §6 guardrail 4 and guardrail 7, and the `residual-diagnosis` skill.
* **Evidence:** `scripts/biome_slow_oracle_probe.jl` REPORTS 8 and 9 (new; the modal REPORTS 1–7 are
  unchanged and reproduce ADR 0104's published numbers in the same run), jobs **1717190** and **1717247**
  (the second adds the forced ensemble arm) — 5 biome cells × **25 members** × 10 years × 5 arms, historic
  2010–2019, pinned `_t8` pair, `wscal_leafon = true`, scored against the C `ind` truth.
  `scripts/exposure_bias_probe.jl` (new), job **1717208** — 22 467 348 rows of
  `slow_runtime_historic_t8`, 400 000-row subsample for the gain secant.
  `scripts/biome_resilience_probe.jl` (e), job **1717189** — the memory clause at `a` = 0.25.

## 1. The reference basis, stated first — and it has TWO axes, which is the whole lesson

The C simulates each cell as **25 replicate patches** and reports their mean. Two separate things have to
match that before a coupled number means anything:

1. **the metric** — score the quantity the change writes. ADR 0104 fixed this: the anchor multiplies the
   roster, so the metric is the roster's density against the C's per-patch mean ÷ `patch_area`, scored
   `mean_y |ln(density/truth)|`. Unchanged here, and still correct.
2. **the canopy basis** — run the same 25 patches the C ran. ADR 0104 did **not** fix this. Its driver
   started from the single **modal** (densest) patch, so every free arm began 1.56–1.95× above its own
   truth. ADR 0104 §5 named this, called the measured benefit an **upper bound**, and then published a
   recommended value anyway.

This ADR closes axis 2. The harness check that makes it a measurement rather than a re-record: the
ensemble's own year-2010 stem count reproduces the C's per-patch mean **exactly** in all five cells
(11.04 / 10.88 / 8.56 / 11.28 / 4.88 against C 11.04 / 10.88 / 8.56 / 11.28 / 4.88) — an identity, and
therefore a check that the reader is looking at the basis the label claims.

## 2. The result: the criterion fails, and the effect it was measuring was mostly the confound

Terminal density ÷ truth, 2019 — the same table ADR 0104 §3 published, now on the ensemble:

| cell | free (modal, ADR 0104) | **free (ensemble)** | a = 0.1 | a = 0.25 | a = 0.5 |
|---|---|---|---|---|---|
| boreal_siberia | 2.55 | **1.35** | 1.31 | 1.31 | 1.31 |
| temperate_hainich | 2.03 | **1.15** | 1.11 | 1.10 | 1.10 |
| mediterranean_iberia | 3.01 | **1.38** | 1.19 | 1.09 | 1.07 |
| semiarid_sahel | 1.55 | **0.52** | 0.41 | 0.36 | 0.33 |
| tropical_amazon | 1.90 | **1.04** | 0.91 | 0.85 | 0.83 |

Score `mean_y |ln(density/truth)|`, lower is better:

| cell | free | a = 0.1 | a = 0.25 | a = 0.5 | anchor helps? |
|---|---|---|---|---|---|
| boreal_siberia | 0.149 | 0.135 | 0.131 | **0.128** | yes |
| temperate_hainich | 0.086 | 0.063 | 0.053 | **0.049** | yes |
| mediterranean_iberia | 0.180 | 0.112 | 0.058 | **0.036** | yes |
| semiarid_sahel | **0.349** | 0.464 | 0.544 | 0.607 | **NO** |
| tropical_amazon | **0.029** | 0.058 | 0.117 | 0.150 | **NO** |
| **MEAN** | **0.159** | 0.166 | 0.181 | 0.194 | **NO** |

**Clause 1 fails at every setting** (two cells get worse, and the mean gets worse). **Clause 1's Sahel
guard also fails at every setting, on `tropical_amazon`** — a cell whose free-running stand is at
1.04× of truth is pushed to 0.83–0.91×, which is exactly the over-to-under crossing the guard was
written to catch, just not in the cell it was named for. **Clause 3a (carbon) passes** by eight orders of
margin on the worst member of every arm. **Clause 3b (stability) fails at `a` = 0.25 and 0.5**:
`semiarid_sahel`'s anchored `fpc` is monotone non-increasing and ends below half its first year
(0.185 → 0.092 at 0.25, → 0.084 at 0.5), which is the runaway shape ADR 0056 identified and this clause
was adopted to reject. It **passes at `a` = 0.1**, so the loop is closable — but 0.1 fails clause 1 too.

**Clause 2 (memory) also fails at `a` = 0.25** — the setting ADR 0104 recommended — and it fails on both
its parts. Mean |AC − the C's AC| over the 10 cell-variable pairs is **0.0491 anchored vs 0.0439 free**
(`pin1`, the no-recursion control, 0.0973), closer to the oracle in **3 of 10** pairs, and the worst single
pair (`tropical_amazon` `n`) moves **+0.0509** away from the C, just over the 0.05 tolerance. ⚠ **This is
not the same answer ADR 0104 §6 got at `a` = 0.5** (0.0405, an improvement) — the memory statistic is
**not monotone in `a`**, so §6's pass was a property of that setting and not of the anchor. It is recorded
here rather than resolved: with clause 1 failing at every setting the memory clause cannot change the
verdict, and characterising a non-monotonicity in a statistic whose per-pair sampling SE is ~0.32 off 10
annual points (the probe's own header says so) would be measuring noise.

**Nothing here was tuned.** The clause-1 direction is monotone in `a` in every cell, and the arms are
**paired** (same 25 patches, same per-member seeds, same forcing), so the arm-to-arm differences are far
better determined than the between-member spread (`sd/mean` 0.38–1.02) would suggest for any single arm.

## 3. Why the anchor helps in three cells and hurts in two — the mechanism, which is now unified

The anchor does exactly what ADR 0103 built it to do: it lands the stand on the count model's **absolute**
target. Whether that is an improvement depends entirely on whether that target is right.

Given **F's own canopy features** — not the C's — the count model's absolute prediction is **below** the
C's truth. So:

* where the free-running stand sits **above** truth (boreal 1.35, Hainich 1.15, mediterranean 1.38), pulling
  it down toward the target helps;
* where the free-running stand is already **at or below** truth (Amazon 1.04, Sahel 0.52), pulling it down
  toward the same target makes it worse, monotonically in `a`.

`semiarid_sahel` is the sharpest case and it **reverses ADR 0104 §4's reading of it**. On the modal patch
it looked like a cell whose stand was 1.55× too dense and whose prediction was nearly right. On the
ensemble it is **48 % UNDER-dense free-running**, and the anchor drives it to 67 % under. It was never an
over-density; the modal patch was.

## 4. Teacher forcing makes it WORSE — which inverts ADR 0054's finding and explains the ratio update

The forced arm (`s.n_prev` overwritten each year with the C's own per-patch mean, ADR 0054's attribution
arm) on the ensemble, scored on the same stand-vs-truth basis:

| cell | free_19 | forced_19 | score free | **score forced** |
|---|---|---|---|---|
| boreal_siberia | 1.348 | 1.976 | 0.149 | **0.277** |
| temperate_hainich | 1.154 | 1.316 | 0.086 | **0.153** |
| mediterranean_iberia | 1.379 | 1.772 | 0.180 | **0.259** |
| semiarid_sahel | 0.522 | 0.373 | 0.349 | **0.460** |
| tropical_amazon | 1.041 | 1.086 | 0.029 | **0.069** |

**Teacher forcing is worse in all five cells**, by 1.8× on the mean score. ADR 0054 measured it removing
**59–72 %** of the count error in every cell — on the modal patch, and scored on `target_history`, the
prediction. Both differences matter and they compound; the conclusion does not survive either fix.

The mechanism follows from §3 and is worth stating because it **inverts ADR 0102's framing**. The update
is a ratio, `ρ = target_t / n_prev`. Free-running, `n_prev` is the model's own previous target, so the
model's absolute level **cancels** and only its year-on-year change reaches the stand. Forced, `n_prev` is
the C's truth, so a target that is systematically below that truth re-enters as a persistent `ρ < 1` — or,
here, drives the stand the other way in cells where the sign runs the other direction — every single year.

⇒ **The multiplicative ratio update is not simply a defect that "discards the level" (ADR 0102 §1). On the
correct basis it is what protects the stand from a biased target.** ADR 0103's anchor deliberately
re-introduces that level, which is precisely why it hurts in the two cells where the free stand was
already right. The level *is* discarded, and ADR 0103 §2's measurement of the consequence stands (§6);
what is withdrawn is the claim that discarding it is the dominant coupled error at this horizon.

## 5. The exposure bias is measured empty — the retrain is not worth buying

The remaining member of ADR 0102's decomposition, measured **offline from the tables that already exist**,
before spending anything on a retrain (`scripts/exposure_bias_probe.jl`, 22.5 M rows). The recursion
reduces to a scalar AR(1) in the count error, `e_t = b + g·e_{t-1}`:

| quantity | value | how |
|---|---|---|
| one-step bias `b`, deployed forest, in-sample | **−0.0166** stems/patch/yr | fed the TRUE `n_prev` |
| one-step bias `b`, **held-out-CELL OOS** | **−0.0014** stems/patch/yr | `preds_oos.f64` |
| AR gain `g` = ∂pred/∂n_prev | **0.562** (0.10 secant), 0.593 (0.25), 0.321 (0.05) | two-sided secant |
| amplification `1/(1−g)` | **2.28×**, converged by year 5 | — |
| implied 10-yr excess | **−0.038 stems** = −0.4 % of the mean count | `b(1−g^10)/(1−g)` |

**On counts of ~10 stems/patch, a held-out one-step bias of 0.0014 stems compounding to 0.038 is nothing.**
`g` is comfortably below 1, so the recursion is a **bounded** amplifier, not a divergent one — the case
ADR 0102 could not rule out and this measures directly.

The per-cell version is the decisive part, because it can be read against the coupled measurement:

| cell | `b` | `b` rel | `g` | offline 10-yr excess | **coupled free (REPORT 8)** |
|---|---|---|---|---|---|
| boreal_siberia | +0.158 | +1.5 % | 0.647 | **+4.2 %** | **+35 %** |
| temperate_hainich | −0.203 | −1.9 % | 0.679 | **−5.9 %** | **+15 %** |
| mediterranean_iberia | +0.183 | +2.3 % | 0.810 | **+10.5 %** | **+38 %** |
| semiarid_sahel | −0.000 | −0.00 % | 0.468 | **−0.0 %** | **−48 %** |
| tropical_amazon | +0.004 | +0.09 % | 0.532 | **+0.2 %** | **+4 %** |

The offline prediction is **the wrong size in every cell and the wrong sign in two**. Since the offline
number is computed with the model fed **the C's own features and the C's own previous count**, the gap
between the two columns is, by construction, everything the coupled loop adds — which is **F's canopy
features differing from the C's**. The modal REPORT 5 in the same run shows that directly: over 2010–2019
F's `fpc` moves 1.56× where the C's moves 0.90× (boreal), 1.27× vs 1.00× (Hainich), 0.71× vs 1.23×
(Sahel). The count model is being fed a canopy the C never had.

## 6. What is NOT withdrawn

Stating this explicitly, because the temptation after a reversal is to throw out the whole family.

* **ADR 0103 §2's retention measurement stands and is unaffected by this ADR.** A 4× perturbation of
  initial density still being 4.21× after 300 identical-forcing years is a property of the **response to a
  perturbation**, a ratio of two runs on the same basis — the modal/ensemble choice cancels out of it.
  There is no restoring force, and `anchor` still removes it (retention 1.036 → 0.051). What this ADR
  shows is that **at a 10-year horizon on real forcing, that missing restoring force is not what dominates
  the coupled level error** — the count model's target being wrong is. Those are compatible: the anchor
  fixes a real structural property, and doing so at this horizon costs more than it buys because it makes
  the stand track a target that is worse than where the stand already was.
* **The anchor stays shipped, opt-in, unchanged**, with its testitem (`slow_level_anchor_tests.jl`) and its
  `anchor = 0` byte-identity pin. It is the right instrument for the long-horizon property above, and it is
  the instrument that will demonstrate the fix once the target is right.
* **Sahel remains a real defect**, now correctly signed: the coupled loop puts it at **0.52× of the C's
  density**, the largest error in the set, and the anchor makes it worse rather than causing it.
* **ADR 0056 (line M) is unaffected in its verdict** — it said do not flip, and this says do not flip.
  Its `density → fpc → target → density` loop is confirmed on the ensemble (clause 3b fires at `a` ≥ 0.25).
  Its stated reason (the anchor is under-delivering on drift) is superseded by §3's: the anchor delivers
  exactly what it promised, onto a target that is wrong.

## 7. Consequences — the queue, re-ordered on a measurement for the second time

1. **The anchor's default question is CLOSED, not deferred.** There is no pending flip, no criterion
   outstanding, and no measurement owed by any line. Anyone reading ADR 0103 §6 or ADR 0104 §5 as an open
   action should stop here. Re-opening it requires a *new* reason — specifically, a count model whose
   absolute target is right, which is item 2.
2. **The exposure-bias retrain is CANCELLED, not deferred** (§5). This was line S's #1 remaining item and
   it is measured empty at a cost of one 4-minute job. It is the third member of ADR 0102's decomposition
   to be measured empty (defect (B) was the first, in ADR 0102 itself) — of the three, only (C) was ever
   real, and §2 now bounds how much of the coupled error even (C) carries.
3. **The residual is a COUPLING/F-fidelity item, not a Component-S training item** (§5's last paragraph).
   F's canopy diverges from the C's over ten years in a way the count model then faithfully responds to.
   `src/fdiff.jl` / `components/fast.jl` are **line M's** paths (CLAUDE.md §9), and ADR 0053 already
   measured the F-side canopy bias. **This is raised to M as an integration point, with the measurement
   attached** — S cannot and should not fix it.
4. **S2 (the conditioning set) is once again the top S-owned item**, by elimination rather than by
   promotion. ADR 0102 demoted it because an unanchored level "compounds without bound"; §5 measures the
   compounding as bounded and small, so that reason is withdrawn. S2's own honest target is unchanged and
   still modest (ADR 0042 §4).

## 8. The method rule, which is the durable part

**A reference basis has more than one axis, and naming a confound is not closing it.**

ADR 0104 applied the rule it had just earned — read the diff, name the variable the change writes, confirm
the metric is a function of it — and got the *metric* axis right. It then named the *canopy* axis as an
open confound in §5, correctly, called the measured benefit an upper bound, correctly, and **published a
recommended `a` from the confounded arm anyway**. That recommendation is what this ADR reverses. The
number was never wrong; it was never a measurement of the thing it was used to decide.

So, as a standing rule for this repo:

> When you write "⚠ this confound means the measured effect is an upper bound", you have not measured the
> effect. Do not publish a recommended value, a default, or a tuned parameter from that arm. Either close
> the confound first, or publish the finding **without** the recommendation and say what would close it.

Its corollary, which §4 is an instance of: **an attribution arm inherits every basis error of the harness
it runs in.** ADR 0054's teacher forcing was measured on the modal patch against the prediction, and it
reversed under *either* correction. A diagnostic arm is not more robust than a skill measurement just
because it is diagnostic.

And a third, cheaper than either: **price a retrain offline before buying it.** §5 is 200 lines of Julia
and one 4-minute job against a global two-artifact retrain and an ADR-0023 both-sides re-pin with line M.
The tables to do it with already existed.
