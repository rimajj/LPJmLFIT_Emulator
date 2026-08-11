---
status: "accepted"
date: 2026-08-11
deciders: "engineering agent, line S (standing autonomous delegation, STEERING_PROMPT); reversible by the owner or a superseding ADR"
consulted: "ADR 0025 §3 (the recruit copula is trained on FIT's SURVIVING stems, with a stated expiry condition), ADR 0045/0046 (recruit traits are inherited; the warming trait shift is 51.3 % within-PFT selection with an age-Wooddens fingerprint), ADR 0047/0049 (the ported trait_mortality operator and its pre-registered flip criterion), ADR 0093 §5.2-5.3 (trait-dependent mortality and the bounded-Beta marginal family), ADR 0111 (the yardstick + the one-ratio-definition rule), ADR 0112/0115/0116 (a score's forcing basis determines what it means; a climate-DEPENDENT error is the failure mode that matters), ADR 0117 (the S->M rung-2 interface = per-individual survival; arm C runs on M's harness)"
informed: "line M (rung-2 arms C0/C1 and the recruit set: lines/M/STATE.md INBOUND); scripts/diagnose_copula_selection_confound.py; lines/S/STATE.md; EXECUTION_PLAN.md rung 1 arm list (integrator-owned -- raised, not edited)"
---

# The recruit copula is trained on survivors, so it already carries the selection arm C proposes to add — the double count is real on Wooddens and negligible on the other three axes

> **Status note.** `accepted` 2026-08-11 under the standing autonomous delegation. Evaluates an expiry
> condition ADR 0025 §3 wrote into itself and that no later ADR checked. **No code, artifact, default or
> committed baseline changes here** — this is a measurement plus a pre-registered correction to how arm C's
> headline number may be read. Reversible by a superseding ADR.

## Context

ADR 0025 §3 chose the recruit copula's training target and, unusually, wrote its own expiry condition into
the decision (verbatim):

> "Because mortality is trait-blind, the emulated community distribution equals the establishment
> distribution — so drawing recruits from FIT's *surviving* marginal makes the community converge to FIT's
> survivor distribution by construction. **(Trait-dependent mortality is a much larger, separate change; if
> ever added, this training target must change.)**"

Arm C **is** that change. ADR 0117 answered line M's rung-2 interface with a per-individual survival factor,
and the operator that produces it (`trait_mortality`, ADR 0047→0049) exists precisely to make mortality
trait-dependent. **No ADR in that chain — 0047, 0049, 0117 — cites ADR 0025.** The condition has sat
unevaluated since 2026-07-27, and arm C is now the next thing line M runs.

The concern is a double count. Recruits drawn from the marginal of FIT's *survivors* already carry FIT's
accumulated selection; applying a trait-selective survival rule on top applies it twice. The asymmetry is
what makes it bite: **C0 (uniform thinning) is unaffected** — it is exactly the trait-blind design the
survivor marginal was matched to — so the bias lands entirely on the arm and not on its null, i.e. directly
on the headline `C1 − C0`.

## Decision drivers

* ADR 0049's flip criterion for `trait_mortality` is stated on the **deattenuated Wooddens response slope**
  (≥ +0.10 over the arm's control, from a recorded 0.66). If the double count moves Wooddens, the criterion
  can be met by the bias rather than by a working selection channel — the ADR 0104 failure mode (a flip
  criterion scored on the wrong quantity) in a new place.
* ADR 0115/0116 established the discriminator that matters: a large but climate-*independent* error largely
  cancels in a response, while a climate-*dependent* one does not. A level displacement and its
  scenario-difference are therefore two separate verdicts, not one.
* ADR 0111 §5b: keep exactly one ratio definition per panel; a ratio against an undetermined or
  differently-based denominator is not a number.

## What was measured

`scripts/diagnose_copula_selection_confound.py` (jobs 1754705, and 1754709 after a cosmetic fix; ~7 min
each on the `priority` partition, no refit and no new model run). Both scenarios, **both ground-truth
members**, all 4 live copula axes, 197.7 M historic and 828.8 M ssp370 surviving tree stems.

**Basis.** Committed `ind` parquets; `Type` in the imported `TREE_TYPES` (ADR 0031); survivors
(`isdead == 0`); no stem-count filter on the pooled panel. That is **byte-for-byte the population
`build_slow_runtime_table.py::copula_table` fits the marginals on** (the same two predicates), which is what
makes the pooled column the copula's actual training target rather than a neighbouring statistic. Age bins
are `build_age_wooddens_gradient_reference.py`'s edges, so the two tables line up bin-by-bin.

Two quantities per axis and scenario: `d` = mean(all survivors) − mean(youngest bin, Age < 10), the
entry→survivor displacement already inside the training target; and `dD` = `d`(ssp370) − `d`(historic), the
part of it that does **not** cancel in a response, read against `R` = FIT's own survivor-marginal warming
response for that axis.

Two aggregations, because they answer different questions: **pooled** (every stem pooled — the copula's own
fit basis) and **per-(Cell,Type)** (the displacement formed *within* each cell-PFT group, then averaged;
this controls the composition confound, i.e. young and old stems simply living in different cells).

## Results

**1. Seed agreement is excellent, so every number below is a property of FIT and not of a draw.** Across the
two ground-truth members every displacement reproduces to ≲ 2 % (e.g. per-cell Wooddens `d` = 32 618 vs
32 583 gC/m³ historic; 34 703 vs 34 678 ssp370). This is the variability audit the `residual-diagnosis` skill
requires before a panel is read, and it passes cleanly — unusually so for this line.

**2. The composition control overturns the naive reading on two of four axes.** Pooled, `D95max` and
`minwscal` look catastrophically displaced (**−49.6 %** and **−35.9 %** of the mean). Within cell-PFT groups
those collapse to **−2.4 %** and **+0.4 %**. So ~95 % of their apparent displacement is *where young stems
live*, not selection — and the copula is conditioned per cell-year, so it already handles that. **Had only
the pooled panel been run, this ADR would have reported a five-axis crisis that does not exist.**

**3. Wooddens is the real one, and it goes the other way — controlling for composition makes it BIGGER.**

| axis | pooled `d`/mean | per-cell `d`/mean | per-cell `dD` | per-cell \|dD/R\| |
|---|---|---|---|---|
| SLA | +1.10 % | +0.80 % | +2.3e-05 | 0.06 |
| **Wooddens** | +5.37 % | **+12.18 %** | **+2085 gC/m³** | **0.56** |
| D95max | −49.55 % | −2.35 % | +2.94 cm | 0.31 |
| minwscal | −35.85 % | +0.44 % | −2.1e-04 | 0.12 |

(historic, seed 1; the seed-2 column agrees to ≲ 2 %.) **Within a cell, FIT's standing wood-density marginal
sits 12.2 % above its own young-stem marginal** — and that is exactly the axis arm C is about, exactly the
`age–Wooddens` gradient ADR 0046 identified as the fingerprint of within-PFT selection, and exactly the axis
ADR 0049's flip criterion is written on.

**4. It does not cancel in a response.** The displacement grows from historic to ssp370 (+32 618 → +34 703
within cell-PFT), so `dD` = **+2085 gC/m³** — **0.56 of that subset's own Wooddens response**. On the pooled
basis the same comparison is `dD` = +7074 against `R` = +1848, i.e. **3.8×** the response. ⚠ The two panels
have genuinely different denominators (the `n_young ≥ 30` floor selects a young-stem-rich subsample of
34 256 of 54 020 cells, whose own `R` is **−3698**, opposite in sign to the pooled +1848), so the ratios are
formed against each panel's own `R` and **must not be blended** — but both say the non-cancelling part is a
large fraction of, or larger than, the entire signal.

**5. Every number here is a LOWER BOUND.** The `ind` writer emits only stems above 5 m
(`fwriteoutput_ind.c:84`), so all selection between establishment and that height is invisible. The true
entry→survivor displacement is larger than measured, on every axis.

**6. One consistency observation, offered as a check and not as a gate.** The pooled Wooddens response
+1848 on a mean of 247 580 is **+0.75 %**, against ADR 0111's published global aggregate of **+0.74 %**.
The two are different statistics (a stem-pooled mean here, an area-weighted per-cell median there), so the
agreement is reassuring rather than probative — do not quote it as a reproduction.

## Decision

1. **Record that ADR 0025 §3's expiry condition has now fired, and that its premise is measurably false for
   Wooddens.** The training target's "mortality is trait-blind" premise ceases to hold the moment arm C runs;
   the affected axis is Wooddens, at +12.2 % within cell, with 0.56 of the response not cancelling.

2. **Arm C's `C1 − C0` MAY NOT be reported as "how much of the trait response is selection".** It measures
   selection applied to an already-selected marginal, minus none. It remains a legitimate and worthwhile
   arm — it is still the only way to test whether the operator moves the trait response at all — but the
   claim it licenses is narrower, and any Wooddens number from it carries a **known positive bias**.

3. **ADR 0049's flip criterion is NOT re-scoped, but it is now qualified — pre-registered here so it cannot
   be reinterpreted after the fact.** A `C1 − C0` Wooddens improvement of ≥ +0.10 deattenuated slope is
   **not sufficient** on its own, because a double count pushes the same direction. Two additional
   conditions, both already computable in the harness:
   * **read θ first** (ADR 0117 §6.i): at Hainich the tilt was θ median 8.5e-12, active in 18 of 132
     thinning years, so the operator may barely fire. A near-zero θ means `C1 ≈ C0` and the arm measured
     nothing; a large θ means the double count is live. **The confound and the arm's power scale together**,
     and neither is interpretable without θ beside it;
   * **the sign test**: a genuine selection channel should improve the *age–Wooddens gradient shape* per
     PFT — including getting ids 0 and 3 **non-monotone** (ADR 0049's committed fixture
     `S_age_wooddens_gradient.csv`) — whereas a double count inflates the level roughly uniformly. The
     gradient is the ID-free target; the slope alone cannot separate the two.

4. **The clean fix is a recruit-marginal training target, and it is NOT free — do not assume it is a
   re-fit.** The obvious repair (train the marginals on entering individuals rather than survivors) is
   **not available from the `ind` parquet at all**: it emits only stems above 5 m, so true recruits are
   never observed. The youngest bin is a proxy, not the target. The real routes are (a) line M's rung-2
   `pre`/`post` roster dump, which *does* see recruits at `age == 0` (ADR 0061/0120), or (b) accepting the
   bias and reporting it. **Route (a) is the one worth scoping**, and it is a rung-2 artifact, so it costs
   nothing new to collect — but it changes the S→M contract (a new copula version), so it is an integration
   point, not a patch.

5. **Arm D inherits this unchanged, and separately needs its own headline number re-established.** Arm D is
   defined as "C + the bounded-Beta family replacing the copula marginals", so it carries the same double
   count. Two further facts scoped here: ADR 0093 §5.3's motivating result (per-cell KS **0.042–0.073** vs
   the copula's 0.129–0.173) **has no committed reproducer in this repo** — no script, no fixture — and its
   phrase "two-moment fit, no fitting procedure" indicates the Beta was matched to each cell's **observed**
   moments, whereas the copula's 0.129–0.173 is a **K-fold-by-cell out-of-sample** number from
   `score_slow_copula_ks.py`. If so the comparison is oracle-conditioned against out-of-sample and the 2–3×
   is an **upper bound**, not a realizable gain: a deployed Beta still needs a learned map from features to
   (mean, variance), which is the cost the copula's forests are already paying. **Arm D must re-establish
   that comparison like-for-like before it is run**, or it will repeat ADR 0112's lesson — a score whose
   forcing basis was never stated.

## Consequences

* **Positive.** A pre-registered condition that had been silently skipped for two weeks is closed before the
  arm it invalidates was run, rather than after. The composition control stopped a five-axis false alarm.
  Arm D's motivating number is now known to be unreproducible from the repo, before it was built on.
* **Negative / accepted.** Arm C's headline claim is narrower than ADR 0117 §2 stated. This ADR does not fix
  the confound — it sizes it, bounds it below, and constrains the reading. The clean fix needs a rung-2
  artifact and a copula version bump.
* **Neutral.** Nothing ships. `trait_mortality` stays default OFF; the `_t8` artifact pair is untouched and
  remains the pinned S→M contract.
* **Raised as integration points, not edited here.** (i) `EXECUTION_PLAN.md`'s rung-1 arm list describes
  arm C as measuring the selection channel — that wording needs decision 2's qualification; the file is
  integrator-owned. (ii) Line S's ADR block **0100–0119 is now down to one number (0119)** — the next block
  must be allocated in CLAUDE.md §9 before the next session needs it.

## Reproducing

```bash
NCPUS=64 TIME=03:00:00 PARTITION=priority QOS=priority \
  scripts/sbatch_python.sh S-confound scripts/diagnose_copula_selection_confound.py
# env: SEEDS (1,2), SCENARIOS (historic,ssp370), MIN_STEMS (30), OUT (per-PFT/bin CSV)
```
