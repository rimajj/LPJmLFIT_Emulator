# ADR 0111 — the yardstick was wrong in three independent ways; on one self-consistent basis it is TWO axes that under-respond, one that OVER-responds by ~30 %, and the worst axis is Wooddens, not D95max

- **Status:** accepted (line S, 2026-08-10)
- **Rung:** `EXECUTION_PLAN.md` **rung 0** ("fix the yardstick"), line S, all three deliverables. No new model
  runs; existing artefacts only, as the rung specifies.
- **Supersedes / corrects:** the numbers in **ADR 0093 §3c/§3d/§3e** and therefore the rung-0 text of
  `EXECUTION_PLAN.md` §3 that quotes them. ADR 0093's *strategy* is untouched and its cost anatomy (§2) is
  not in scope here. **Does NOT re-read ADR 0109's flip criterion** — see §6.
- **Related:** 0106 (the acceptance criterion — `max(10 %, the model's own two-run spread)`), 0030 (the
  basis-clean noise floor for the trait axes; this extends its discipline to counts, carbon and the
  *response*), 0036 §5b (streaming `group_by` key-set nondeterminism), 0108 §1 (the method rule: measure the
  baseline before arguing from structure), 0109 (the response arm whose slopes are re-scored here),
  0093 (the source of the numbers corrected here).
- **Artefacts:** `scripts/build_truth_yardstick_tables.py` (stage 1, the two-seed reduction; jobs **1743333**
  historic, **1743334** ssp370), `scripts/diagnose_truth_yardstick.py` (stage 2; jobs **1743409** capped
  basis, **1743410** uncapped basis), committed reference
  `test/testitems/references/S_truth_yardstick_summary.csv` (272 rows: floor × 2 bases × 2 scenarios × 6
  density strata, reliability, aggregate response × 5 latitude bands, and the re-scored emulator slopes).
- **Coverage:** **51 767 of the 54 020 tree-bearing cells** (95.8 %) — those with ≥ 30 stems in **all four**
  runs (2 seeds × 2 scenarios). Both scenarios and the response between them. This is not a five-cell result.

---

## 1. The defect: three independent errors, each of which alone changes a conclusion

The emulator is scored against one realisation of a stochastic model, and the correction for that — divide the
scored slope by the regressor's reliability λ — was published in ADR 0093 §3e as "it is TWO broken axes, not
four". Reproducing it turned up three separate problems.

**(a) Two rows of ADR 0093 §3e have λ and the deattenuated slope SWAPPED.** The λ values in that table come
from `/p/tmp/jamirp/npatch_analysis/crn_headroom.json` (`lambda_1seed`), which reads SLA 0.788, minwscal
0.697, Wooddens **0.628**, D95max **0.510**. The table's SLA and minwscal rows are consistent
(0.851/0.788 = 1.08 ✓, 0.689/0.697 = 0.99 ✓). Its Wooddens and D95max rows print λ = 0.55 / 0.32 and
"deattenuated" = 0.63 / 0.51 — but 0.63 and 0.51 *are* the λ values, and 0.55 = 0.346/0.628 and
0.32 = 0.163/0.510 are the quotients. So **on that ADR's own basis the deattenuated slopes are Wooddens 0.55
and D95max 0.32, not 0.63 and 0.51** — i.e. worse than published, and `EXECUTION_PLAN.md` §3 rung 0 carries
the swapped pair forward as the target to reproduce.

⚠ **The competing reading, and why it is rejected.** The published rows are *also* internally consistent if
one assumes λ really was 0.55/0.32 from some other source (0.346/0.55 = 0.63 ✓, 0.163/0.32 = 0.51 ✓), so
arithmetic alone does not decide it. What decides it is that the ADR's two "deattenuated" entries equal
`crn_headroom.json`'s `lambda_1seed` for those same two axes to three decimals (**0.628 → 0.63**,
**0.510 → 0.51**) while its other two rows use that file's λ verbatim (0.788 → 0.79, 0.697 → 0.70). Under the
competing reading that coincidence would have to happen twice, by chance, against numbers sitting in the same
file. **In any case defect (a) is not what the conclusions rest on:** defect (b) below means neither reading
was quotable, and §4's single-basis measurement supersedes both.

**(b) The λ and the slope were computed on DIFFERENT BASES, so their quotient was never quotable.** The λ is
log-space, single-year (hist 2019 → ssp 2099), cell-mean-of-per-patch values, ≥ 50 stems, 43 257 cells,
uncapped. The slope (ADR 0109) is linear-space, per-cell median **pooled over all years**, ≥ 30 stems,
52 074 cells, on a table built with `STEM_CAP=400`. A reliability is a property of a *statistic*; dividing one
statistic's slope by another statistic's reliability has no defined meaning. This is ADR 0030's basis rule
("a floor is only comparable to a score if BOTH select the same stems"), applied to the response instead of
the level — and it had not been applied there.

**(c) A per-patch density must be divided by the CONFIGURED patch count, never by the OCCUPIED one.** This
one is mine, found and fixed inside this work: dividing a cell's stem count by the number of patches that
happen to hold a tree lets a seed with fewer stems also get a smaller denominator, which cancels part of the
sampling noise. In the sparse stratum it understated the floor by **3×** (10.5 % instead of 27.0 %). The
committed script now divides by the configured `NPATCH=25` and asserts no cell-year exceeds it. Note that
`cell_npatch.parquet` is itself derived from occupied patches, so it is the wrong table for this job.

---

## 2. What was built

Two scripts, both line-S owned, both rerunnable, no `src/` change and therefore byte-identical everywhere
(guardrail 4 is not even engaged — nothing in the model changed):

- **Stage 1** reduces all four ground-truth `ind` parquets (2.55 × 10⁹ stem-year rows) to three small tables
  per (scenario, seed): per (Cell, Year) counts/carbon/yearly trait medians; per-Cell trait medians pooled
  over all years **uncapped**; and the same **after replicating `STEM_CAP=400`**, which is the basis the
  published slope was actually scored on. Whole run: **3.5 min** on 96 cores, because `Cell` predicate
  pushdown works on these files. Every aggregate asserts its own key uniqueness (ADR 0036 §5b: a streamed
  `group_by` can silently duplicate keys, and a row-count check cannot see it).
- **Stage 2** computes the floor on both bases, the reliability, the aggregate response, and — given a copula
  table's OOS predictions — the re-scored slopes.

**The basis alignment is verified, not assumed.** Re-scoring the shipped pin on the capped basis reproduces
ADR 0109's published slopes to within 1–3 % (SLA 0.872 vs 0.851, Wooddens 0.352 vs 0.346, D95max 0.168 vs
0.163, minwscal 0.678 vs 0.689). That is the ADR-0030 cross-check: without it, none of §4 would be a
correction rather than a different measurement.

---

## 3. Deliverable 1 — the noise floor, on TWO bases, because the question has two forms

Median over cells of `|x₁ − x₂| / mean(x₁,x₂)`; `tolerance` = ADR 0106's `max(10 %, that spread)`.

**Per cell, 20-year climatology** (historic; traits on the capped basis; 51 817 cells):

| quantity | ALL | <2 stems/patch | 2–5 | 5–10 | 10–20 | >20 |
|---|---|---|---|---|---|---|
| stems per patch | 6.77 % | **16.63 %** | 7.01 % | 6.56 % | 4.95 % | 2.89 % |
| above-ground C per patch | **10.16 %** | **25.29 %** | 13.32 % | 9.73 % | 7.29 % | 3.84 % |
| SLA median | 2.53 % | 3.83 % | 2.59 % | 2.51 % | 2.17 % | 0.92 % |
| Wooddens median | 3.84 % | 7.04 % | 4.70 % | 3.93 % | 2.70 % | 2.14 % |
| **D95max median** | **13.21 %** | **15.22 %** | **10.08 %** | **15.36 %** | **10.09 %** | **13.69 %** |
| minwscal median | 4.58 % | 5.81 % | 3.56 % | 5.36 % | 3.39 % | 1.61 % |
| Height median | 3.03 % | 2.13 % | 1.76 % | 4.57 % | 2.24 % | 1.19 % |
| Age median | 8.22 % | 9.09 % | 6.45 % | 9.84 % | 6.37 % | 2.90 % |

**Per (Cell, Year)** — a single year's full 25-patch roster, uncapped (historic; 1 036 662 cell-years):
stems per patch **8.59 %** (ALL) / **27.03 %** (<2 stratum); above-ground C **11.93 %** / **37.22 %**;
SLA 2.53 %, Wooddens 3.81 %, D95max 12.62 %, minwscal 4.53 %.

Three things follow, and all three are load-bearing:

1. **ADR 0093 §3c's `<2` stratum tolerances (count 31.6 %, carbon 42.7 %) are the PER-CELL-YEAR basis**, and
   are reproduced here as 27.0 % / 37.2 % (the residual is 2019-only vs 20 years pooled). On a
   **climatological** basis the same stratum is **16.6 % / 25.3 %** — a 20-year mean averages ~√20 of the
   noise away. Both are correct for their own question; quoting one as the tolerance for the other is a
   ~2–3× error in whichever direction you make it. **Say which basis a tolerance is on, every time.**
2. **`D95max` is the only quantity whose tolerance exceeds 10 % in EVERY density stratum** (10.1–15.4 %), and
   it does not improve with density — 13.7 % in the densest stratum. Its per-cell median is not a
   10 %-resolvable quantity in this reference data at `npatch=25`, on either basis.
3. Carbon at 10.2 % globally means ADR 0106's `max(10 %, …)` clause **binds for carbon almost everywhere**,
   not just in sparse cells.

ssp370 is quieter than historic on every quantity (counts 4.22 %, carbon 7.63 %, D95max 12.41 %) — the
80-year run reaches a less variable state than the 20-year historic window samples.

---

## 4. Deliverable 2 — reliability and the CORRECTED deattenuated slope

λ from the two paired single-seed responses `D_s = X_s(ssp370) − X_s(historic)`, in the same units, statistic
and cells as the slope (capped basis, 51 767 cells):

| quantity | per-cell S/N | λ (1 seed) | λ (2 seeds) | λ (4 seeds) | seeds disagree on SIGN |
|---|---|---|---|---|---|
| stems per patch | 3.14 | 0.908 | 0.952 | 0.975 | 21.1 % |
| above-ground C | 1.27 | 0.616 | 0.762 | 0.865 | 18.7 % |
| SLA median | 1.35 | 0.645 | 0.784 | 0.879 | 32.8 % |
| Wooddens median | 1.02 | 0.510 | 0.676 | 0.807 | 37.7 % |
| D95max median | **0.50** | **0.198** | 0.330 | 0.497 | **42.2 %** |
| minwscal median | 1.33 | 0.640 | 0.780 | 0.877 | 40.4 % |
| Height median | 0.68 | 0.315 | 0.480 | 0.648 | 30.3 % |
| Age median | 1.24 | 0.604 | 0.753 | 0.859 | 31.0 % |

The shipped pin (`_t8`), re-scored on ONE basis. `deatt` = slope/λ on the matching regressor; both bases are
shown because their agreement is the estimator's validation:

| axis | scored vs seed1 | vs 2-seed mean | deatt, 1-seed (capped / uncapped) | deatt, 2-seed (capped / uncapped) | ADR 0093 §3e said |
|---|---|---|---|---|---|
| SLA | 0.872 | 1.004 | **1.35 / 1.32** | **1.28 / 1.25** | 1.08 "already correct" |
| Wooddens | 0.352 | 0.444 | **0.69 / 0.68** | **0.66 / 0.66** | 0.63 (in fact 0.55) "broken" |
| D95max | 0.168 | 0.241 | **0.85 / 0.83** | **0.73 / 0.72** | 0.51 (in fact 0.32) "broken" |
| minwscal | 0.678 | 0.824 | **1.06 / 1.05** | **1.06 / 1.05** | 0.99 "already correct" |
| Height *(diagnostic)* | 0.332 | 0.393 | 1.05 / 0.85 | 0.82 / 0.72 | — |

**★ The correction is basis-ROBUST even though neither of its two factors is.** Between the capped and
uncapped bases the raw slope moves up to 21 % (D95max 0.168 → 0.204) and λ moves up to 25 % (0.198 → 0.247),
while the quotient moves **≤ 3 %** on all four production axes. That is exactly what an errors-in-variables
correction is supposed to do, and it is the strongest single piece of evidence that these deattenuated
numbers — not the raw slopes — are the quantity to steer by. **`Height` is the exception** (1.05 vs 0.85), so
it is reported as a range and never as a number.

**What the corrected panel says, and it is a different story from the plan's:**

- **`minwscal` is correct** (1.05–1.06), as previously believed.
- **`SLA` OVER-responds by 25–35 %** (1.25–1.35). It was previously read as "already correct at 1.08". This
  is new, and it matters for §6.
- **`Wooddens` is the WORST axis** (0.66–0.69): it produces two-thirds of the true response.
- **`D95max` is NOT the worst** (0.72–0.85). It was read as the worst (0.51, in fact 0.32) purely because its
  regressor is nearly noise (λ = 0.198 — its per-cell response S/N is **0.50**, the only quantity below 1).
  Its raw slope of 0.163 is mostly attenuation, not mostly model failure.
- **`Height`, a diagnostic axis nobody was gating on, is the real outlier** — see §5's aggregate ratio.

⚠ This re-ranking does **not** retract ADR 0110. That record acted on `D95max`'s **level** gap (28–33 % of
cells within 10 %, which stands) and on a measured physical mechanism, not on the response ranking. What
changes is the *response* story: the rooting-depth axis's response was oversold as broken.

### 4b. The COUNT response — the first quantity the acceptance criterion names — is FAITHFUL

Scored the same way from the pooled count table's own out-of-sample predictions
(`slow_count_pooled_w20_t8`, target `n_living`, 121 495 658 rows), on the same 51 767 cells:

| | value |
|---|---|
| basis cross-check `r`(count table's own seed1 response, this reduction's seed1 response) | **0.9948** |
| raw slope vs the count table's own truth / vs this seed1 / vs the 2-seed mean | 0.982 / 0.958 / 0.958 |
| λ (1 seed / 2 seeds) | 0.908 / 0.952 |
| **deattenuated slope** | **1.056 (1-seed) / 1.006 (2-seed)** |
| aggregate (area-mean) response, prediction ÷ truth | **0.691** |
| **the same by band** | tropical **−0.51** · subtropical +3.41 · temperate **+0.93** · boreal **+1.07** |

Two things worth having:

- **The per-cell tree-count response channel is open and correctly scaled** — deattenuated 1.01, and counts
  need the least correction of any quantity because their λ is the highest (0.908). Any statement that "the
  warming response is indistinguishable from zero" is **not** true of counts on this basis. The trait axes are
  where the response error lives.
- **But the global 0.691 is not a uniform under-response — it is a TROPICAL SIGN ERROR** (see §5b): the
  temperate (0.93) and boreal (1.07) bands are right and the tropics respond the **wrong way** (−0.51). Do
  not read the global number as "counts respond 31 % too weakly".
- **It is the mirror image of Wooddens.** Counts get the per-cell *pattern* right (slope ≈ 1) and under-shoot
  the *total* (area-mean 0.69×); Wooddens gets the total right (1.13×) and the pattern wrong (0.66). Those are
  different defects and they want different fixes — which is only visible because both statistics are now
  published side by side.
- The 0.9948 cross-check is the ADR-0030 discipline doing its job: the count table and this reduction are two
  independent code paths over the same run, so their agreement is what makes the count slope comparable to the
  trait panel rather than a different quantity.

---

## 5. Deliverable 3 — the aggregate response, and it becomes the PRIMARY response statistic

Area-weighted (cos φ) mean over the same 51 767 cells; noise from the two seeds' own aggregate difference:

| quantity | historic level | response | % | 2-seed noise | S/N | emulator's aggregate response ÷ truth's (`_t8`) |
|---|---|---|---|---|---|---|
| stems per patch | 7.053 | −0.122 | −1.74 % | 0.0042 | **29** | **0.71** |
| above-ground C per patch | 5496 | −29.9 | −0.54 % | 1.19 | **25** | — |
| vegetation C per patch | 7407 | −40.6 | −0.55 % | 0.83 | **49** | — |
| SLA median | 0.02441 | −3.86e−4 | −1.58 % | 7.9e−7 | **489** | **1.94** |
| Wooddens median | 238 695 | +1756 | +0.74 % | 43.9 | **40** | **1.06** |
| D95max median | 358.8 | +4.28 | +1.19 % | 0.075 | **57** | **1.75** |
| minwscal median | 0.2925 | +0.00371 | +1.27 % | 1.2e−4 | **32** | **2.95** |
| Height median | 7.862 | −0.0130 | −0.17 % | 0.0035 | **3.8 — weakest** | 2.88, **not determined** |
| Age median | 33.87 | −1.500 | −4.43 % | 0.041 | **36** | (no prediction) |

**Per-cell S/N is 0.5–3.1; area-weighted S/N is 25–489.** The response is a well-determined aggregate
quantity and a poorly-determined per-cell one, so **the aggregate is the primary and the per-cell map is a
reported secondary** — that is deliverable 3, and it is now the published definition.

The latitude-band panel is where the structure is: above-ground carbon responds **−1.47 %** (tropical),
−3.55 % (subtropical), −3.92 % (temperate) and **+19.4 %** (boreal) against a global −0.54 %. A global mean
alone would report "almost no carbon response" for a model that gains a fifth of its boreal stand carbon.
**Report the bands, not only the global number.**

### 5b. ★ THE BAND-WISE RATIO IS THE RESULT — a positive global ratio hides WRONG-SIGNED regional responses

A global aggregate is a ratio of near-CANCELLING sums (the truth's global mean count response is ~3 % of its
between-cell spread, because regional responses partly oppose each other), so it can look right while the
pattern is wrong. Area-weighted **prediction response ÷ truth response** by band, each with the band's own
two-seed signal-to-noise; **`n/d` = the truth's band response is not determined (S/N < 3), so no ratio is:**

| quantity | GLOBAL | tropical | subtropical | temperate | boreal |
|---|---|---|---|---|---|
| stems per patch | +0.71 | **−0.51** (S/N 6) | +3.41 | +0.93 | +1.07 |
| SLA median | +1.94 | +0.69 | **−3.91** | **−0.29** | +3.19 |
| Wooddens median | +1.06 | +0.86 | +1.23 | +0.43 | +1.40 |
| D95max median | +1.75 | **n/d** (S/N 1) | +1.09 | +3.08 | +1.75 |
| minwscal median | +2.95 | +3.62 | +1.80 | +1.22 | **−4.45** |
| Height median *(diagnostic)* | +2.88 (S/N **4**) | +1.51 | +1.00 | +1.42 | +0.92 |

- **Four wrong-SIGNED band responses that the global ratio hides:** tree counts in the **tropics** (−0.51),
  SLA in the **subtropics** (−3.91) and the **temperate** band (−0.29), and minwscal in the **boreal**
  (−4.45). Counts are the sharpest case: a global +0.71 that reads as a mild under-response is in fact a
  correct temperate (0.93) and boreal (1.07) response **plus a tropical response of the wrong sign**. That is
  a concrete, localised target, and it is invisible in every response statistic published before this record.
- **Wooddens is the best-behaved axis in aggregate** (0.43–1.40 across bands) despite having the *worst*
  per-cell slope (0.66) — the right total in the wrong places. §4 measures the per-cell *pattern*, §5b the
  regional *totals*; they are different questions and this is what it looks like when they disagree.
- **D95max's tropical band is undetermined** (the truth's own two-seed noise swamps its response, S/N 1), so
  no D95max claim may be made for the tropics on this reference data at `npatch=25`.

⚠ **THE GUARD CAUGHT ONE OF THIS RECORD'S OWN DRAFT CLAIMS, so it is stated rather than quietly fixed.** An
earlier draft of §5 reported "the emulator delivers **14 %** of the truth's height response", from an
*unweighted* mean-ratio. Area-weighted, the same quantity reads **2.88** — and Height's global S/N is **4**,
the weakest of any quantity, because its global aggregate is a near-zero residue. **Neither 0.14 nor 2.88 is a
result**, and the band ratios (0.92–1.51) say Height's response is in fact roughly right per band. Two rules
now enforced in the script: there is exactly **ONE** definition of the aggregate ratio (area-weighted), and a
ratio whose denominator is not determined prints **`n/d`**, never a number.

---

## 6. What this does and does NOT change about ADR 0109

Re-scored on the corrected yardstick, `_t9envT` (the transient-tail arm) has deattenuated 2-seed slopes SLA
**1.114**, Wooddens 0.638, D95max **0.757**, minwscal 1.065. Measured as distance from the faithful value 1,
the transient arm is better on SLA (0.11 vs 0.25) and D95max (0.24 vs 0.28) and marginally worse on Wooddens
(0.36 vs 0.35) and minwscal (0.065 vs 0.047) — so **ADR 0109's finding that the transient tail buys response
survives the correction, and gets stronger on the axis with the biggest margin.**

But one of its readings does not survive: **ADR 0109 treated a larger scored slope as better on all four
axes. Above 1.0 that is backwards** — and SLA and minwscal are above 1.0 once deattenuated, so the arm's
"+0.356 on SLA" is movement *away* from faithful, not towards it. **The target is 1.0, not "as high as
possible."**

**No flip, and no re-read of ADR 0109's criterion.** Rewriting a criterion after seeing its arm is ADR 0104's
error, and §5 of ADR 0109 already registers a corrected three-clause criterion for a NEW arm. What this ADR
adds is that clause's *statistic*: it must be `|deattenuated slope − 1|` against the multi-seed mean, not the
raw slope. `_t9envT` stays unpinned; M's `_t8` pin is untouched; nothing in `src/` moved.

---

## 7. Consequences, and the honest limits

- **`EXECUTION_PLAN.md` rung 0 is delivered** for line S: a per-cell per-quantity stratified floor on two
  stated bases, a deattenuated slope for every axis, and a published aggregate response metric — all on
  51 767 of 54 020 cells, both scenarios. **Its own rung-0 text now contains superseded numbers** (the
  swapped λ/deatt pair, and the `<2` stratum tolerances quoted without their basis). That file is
  integrator-owned ⇒ **integration point**, recorded in `lines/S/STATE.md`; a line does not edit it.
- **"Four broken axes" is retired, and so is "two broken axes at 0.63/0.51."** The panel is: one axis
  correct, one over-responding by ~30 %, two under-responding (0.66 and 0.72–0.85), one diagnostic axis
  nearly unresponsive.
- **The extra seeds are worth more than the table suggests.** λ(2 seeds) vs λ(1 seed) is 0.198 → 0.330 on
  D95max and 0.510 → 0.676 on Wooddens; at 4 seeds, 0.497 and 0.807. Two more members (already scheduled to
  the integrator by rung 0) roughly halve the attenuation on exactly the two axes that matter.
- **λ is estimated from 1 degree of freedom per cell**, pooled over 51 767 cells. The pooled estimate is
  well determined, but the errors-in-variables model assumes the response noise is independent of the
  response signal; the 1-seed-vs-2-seed disagreement (≤ 3 % on the trait axes, 24 % on Height) is the
  visible part of that assumption's error, and is why ranges are quoted.
- **The cap replication is approximate**: the production `STEM_CAP` is applied after a conditioning join that
  drops ≤ 2 % of stems; this one has no join. It bounds the cap's noise contribution rather than reproducing
  the production row set. Both bases are reported precisely so no conclusion rests on it.
- **These are OFFLINE numbers.** The predictions are K-fold-by-cell OOS from tables conditioned on the C's
  own features, so every slope here is an **upper bound** on the coupled model's (ADR 0105 §5). The coupled
  ensemble screen is still the blocker it has been.
- **`Age` has no prediction file**, so its truth-side reliability is published and its slope is not.
- **The aggregate pred÷truth ratio IS banded** (§5b) and carries a determinacy guard, after an unbanded,
  unweighted version produced a headline number that did not survive (see §5b's warning). Any criterion
  written against a response ratio must name the **band** and respect the `n/d` guard.
- Nothing here touches `src/`, any committed baseline, or any pinned artifact.

---

## 8. What rung 1 must now do differently

Rung 1 (S alone on the C's own per-tree fluxes) has a pre-registered flip criterion for `trait_mortality`
that reads *"improves the deattenuated Wooddens response slope by ≥ +0.10 over arm B"*. That is now
measurable exactly as written, and the numbers to beat are on the record: **arm-B-equivalent Wooddens
deattenuated 0.66 (2-seed) / 0.69 (1-seed)**, with the level guardrail read against §3's tolerances rather
than a literal 10 %. Run it with `scripts/diagnose_truth_yardstick.py PRED_DIR=<arm>` so every arm is scored
on this one basis.
