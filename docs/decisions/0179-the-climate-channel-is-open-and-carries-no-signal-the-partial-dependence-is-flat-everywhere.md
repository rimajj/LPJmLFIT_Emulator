# 0179 — the count model's climate channel is structurally WIDE OPEN and carries almost no signal: the partial dependence is flat within cells AND over the entire global range

* Status: accepted
* Date: 2026-08-13
* Line: S (tier-3 block 0170–0189)
* **Answers the question ADR 0178 §6 left open** and closes it in the direction ADR 0178 pre-registered as
  hypothesis 2. Does not withdraw anything: ADR 0178's measurement (climate response ≈ 0 in the free-running
  loop) is confirmed from a completely independent direction — the artifact itself, with no LPJmL run.
* Scope: the shipped pooled count artifact `drf_forest_global_pooled_w20_t8.drf` (150 trees) — the exact file
  every ADR 0176/0177/0178 arm loaded — and its own training table `slow_count_pooled_w20_t8`
  (121 495 658 rows × 15 features). 15 rung-2 cells; 12 with a FIT truth response.
* Probe: `scripts/slow_climate_partial_dependence_probe.jl` (job 1771609, 4 min). Output:
  `/p/tmp/jamirp/emulator_global/S_climate_partial_dependence.csv`.

---

## 1. The question, and the three hypotheses

ADR 0178 measured the shipped count model's climate response inside FIT's own physics as ~0 (drift share
94–100 %, climate-vs-truth slope −0.031…+0.044) and named two candidate explanations, which send retraining
effort to opposite places: **the model never learned a climate dependence**, or **it learned one the
free-running loop cannot express**.

A third was added here before the run, because a pooled global fit makes it likely and a naive full-range
sweep would misread it as the second:

| | hypothesis | implication |
|---|---|---|
| **H1** | never learned it | the training target / feature set is the defect (ADR 0112 restart) |
| **H2** | learned it; the loop is blind to it | the artifact is fine, the loop is the defect |
| **H3** | learned climate as a **cell identifier** (a climatology map) — steep between cells, flat within one | the training DESIGN is the defect: the between-cell gradient is not the within-cell temporal contrast |

H3 matters because a forest pooled over 58 588 cells is *certain* to split hard on growing-degree-days: the
between-cell spread of stem count against climate is enormous, while the within-cell warming excursion is
small. A sweep over the full training range would then show a large dependence that reads as H2 while the
operative response is zero. So the probe emits the pooled and the within-cell panel **side by side from one
script on one row universe**, per the `residual-diagnosis` pooled-vs-within-group rule (ADR 0118).

## 2. The reference basis

* **Rows are the forest's own training rows**, restricted to each probe cell — genuine per-cell feature
  distributions, so "the rest of the row held at realistic per-cell values" holds by construction, not by
  assumption. (`X.f64` is row-major n×p; the mmap is indexed per sample.)
* **The climate move is the campaign's own**: the per-(cell, year) boundary CSVs the ADR 0177/0178 arms were
  actually fed, historic terminal (2019) → ssp370 terminal (2100). Not a synthetic ±X °C.
* **The yardstick is FIT's own terminal count response** at each cell, so a predicted Δ is reported as a
  fraction of the thing it is supposed to reproduce.
* **A live-channel scale anchor is mandatory**, or "flat" is unfalsifiable — it could mean the whole forest
  is flat. `n_prev` moved by its own observed historic→ssp370 shift at the same cell, on the same rows,
  serves as that anchor.
* Only features 12 (`eco_diag_gdd_5`) and 13 (`tas_cold_month`) are transient climate. 14 (`soil_depth`) is a
  per-cell constant; 15 (`co2`) is constant 369.0 **by design** (ADR 0004/0107 — the emulator does not see
  CO2; that is faithfulness, not a gap, and it is visible below as 0 splits).

## 3. The result: the channel is OPEN, and it carries nothing

**The structural check kills the simplest version of H1 outright.** The forest splits on the climate features
**77 440 times — 10.20 % of all splits** — with thresholds spanning essentially the whole global range
(gdd5 266.9–9743, tas_cold −45.7–28.9). It is not blind to climate by construction. The one feature that
genuinely is, is `co2`, at exactly 0 splits, exactly as designed.

| feat | name | splits | share |
|---|---|---|---|
| 5 | hmean | 109 918 | 14.48 % |
| 9 | fpc | 103 959 | 13.69 % |
| 11 | **n_prev** | 83 575 | **11.01 %** |
| 6 | hmax | 70 044 | 9.22 % |
| 8 | lai | 56 175 | 7.40 % |
| 10 | age_mean | 50 674 | 6.67 % |
| 7 | agb | 49 351 | 6.50 % |
| 12 | **eco_diag_gdd_5** | 41 393 | **5.45 %** |
| 1 | bm_inc_cell | 40 761 | 5.37 % |
| 2 | growth_eff | 38 009 | 5.01 % |
| 13 | **tas_cold_month** | 36 047 | **4.75 %** |
| 14 | soil_depth | 24 894 | 3.28 % |
| 3 | water_stress | 29 811 | 3.93 % |
| 4 | soilmoist | 24 693 | 3.25 % |
| 15 | **co2** | **0** | **0.00 %** |

**And yet every partial dependence is flat.** Over the *entire* global range the panel-A amplitudes are
**0.227 stems** (gdd5, sweeping 456 → 9949 growing-degree-days), **0.066** (tas_cold, −32.7 → +29.6 °C) and
**0.281** (both together). The curves are smooth and monotone-ish — 9.046 → 8.844 stems for gdd5 — i.e. the
model does carry a faint, correctly-signed cooling-is-denser gradient, and it is two orders of magnitude
smaller than the between-cell spread of the target it was fitted on.

**Over the operative within-cell warming excursion it is smaller still**: mean |Δ climate| = **0.0568 stems**
across 15 cells, against a mean |Δ n_prev| of **1.2777 stems** on the same rows — the climate channel is
**4.4 %** of a channel known to be live. Per cell, against FIT's own response:

| cell | gdd5 move | Δ climate | Δ n_prev (live ref) | FIT truth | Δclim / truth |
|---|---|---|---|---|---|
| 12045 | 8449 → 9245 | +0.0028 | +0.8458 | +0.320 | +0.009 |
| 12235 | 7859 → 8784 | +0.0016 | 0.0000 † | −0.800 | −0.002 |
| 18371 | 9043 → 9949 | +0.0492 | −0.5360 | −3.560 | −0.014 |
| 22732 | 7246 → 8163 | +0.0043 | −0.7857 | −0.240 | −0.018 |
| 22990 | 8352 → 9236 | +0.0338 | −1.9371 | +0.600 | +0.056 |
| 23318 | 5603 → 6571 | −0.0185 | 0.0000 † | n/a | n/a |
| 32628 | 3545 → 4308 | −0.0280 | −0.7655 | +0.880 | −0.032 |
| 33335 | 3778 → 4560 | −0.0126 | −1.4197 | n/a | n/a |
| 42490 | 1864 → 2573 | −0.0284 | −2.4959 | −0.200 | +0.142 |
| 42757 | 519 → 861 | −0.1296 | −2.5746 | −5.240 | +0.025 |
| 42973 | 2092 → 2818 | −0.0266 | −1.7520 | +0.600 | −0.044 |
| 44048 | 1447 → 2054 | −0.0657 | −2.0673 | +5.237 | −0.013 |
| 46336 | 1072 → 1553 | −0.0088 | −0.7362 | n/a | n/a |
| 52059 | 822 → 1291 | −0.0852 | −0.7550 | −0.560 | +0.152 |
| 57087 | 764 → 1229 | −0.3561 | −2.4941 | −3.000 | +0.119 |

**9 of 12 scored cells are below 10 % of FIT's own response; 0 of 12 are above 50 %.** The three cells with no
truth (23318, 33335, 46336) are exactly the ones ADR 0177 §C lost to the `ERROR043` duplicate-roster-key
crash — the absence is that known interface defect, not a new one.

† **Two cells return exactly 0.0000 on the live-channel anchor, and that is quantization, not a bug.** The
forest's `n_prev` split thresholds sit at half-integers (1.5 … 30.5) because per-patch stem counts are
integers; cell 12235's observed shift is 5.707 → 5.532 and cell 23318's 6.655 → 7.323, both of which stay
inside a single bin, so no tree changes leaf and the secant is identically zero. This is the piecewise-constant
trap ADR 0105 warns about, met here in the anchor rather than in the measurement. It biases `mean |Δ n_prev|`
**downward**, i.e. it makes the climate channel look *relatively larger* than it is — conservative for the
conclusion below.

**H3 is refuted as well as H2.** A cell sitting on a local plateau between two splits would explain a flat
within-cell response with a steep global surface; panel D swept the full range on each cell's *own* rows and
got a mean amplitude of 0.345 stems — larger than the pooled 0.281, as expected when averaging over less
heterogeneous rows, and still an order of magnitude below FIT's responses. There is no steep surface anywhere
to be locally flat on.

## 4. Decision

**The pre-registered verdict is H1: the count model's climate dependence is flat within cells and over the
entire global range, so the defect is in the training target / feature set, not in the coupled loop.** The
next work on the warming response goes to ADR 0112's teacher-forcing critique, as ADR 0178 §B2a
pre-registered. Do not spend further effort looking for a loop-side bug that would let an existing learned
response through: measured on the artifact, there is no such response to let through.

**But record the mechanism precisely, because the pre-registered H1 label is right and its stated mechanism is
not.** H1 was worded as "no splits, or a flat surface"; what is actually true here is the *second* clause only.
The forest splits on climate 77 440 times and those splits carry ~no marginal effect — climate reduces enough
variance at a node to be *chosen* from a 4-of-15 candidate draw, while the leaf values either side of it
barely differ. That is a claim about what is left to explain, and it points at one specific feature:
`n_prev` is FIT's own previous-year count for the same `(Cell, Patch)`, the teacher-forcing leak ADR 0112
identified, and the persistence null already scores R² 0.9622 on this target. If the target is nearly
determined before climate is consulted, a flat climate surface is what a correct fit *looks like*.

That is a hypothesis with a cheap falsifier, and stating it here rather than acting on it is deliberate:
**"the training target is the defect" is a conclusion this ADR supports; "removing `n_prev` will open the
climate channel" is not yet measured.** ADR 0180 is that measurement.

## 5. What this ADR does NOT claim

* **Not** that the emulator is insensitive to climate overall. Only the *count* model's own two transient
  climate features were probed. F's daily physics sees climate directly, and four of the count model's other
  features are computed from the live stand and move with it; ADR 0108 §1 is the standing warning against
  reading a structural fact about one input as a statement about the model.
* **Not** a statement about the trait axes. ADR 0111 §8 is explicit that the count and trait responses fail
  independently; this is the count channel only.
* **Not** a per-cell response measurement. A partial dependence is a property of the fitted function, not of
  the coupled trajectory — ADR 0178's arms remain the measurement of the latter. The two agreeing from
  independent directions is what makes the finding usable.
* The CO2 row is **not** a gap (ADR 0004/0107, standing, do-not-re-litigate). It appears above only because a
  liveness panel that prints every feature is how the zero on the climate features would have been detected
  had it been there.

## 6. Reusable

The probe generalises to any conditioning axis of any artifact in this repo, and two parts of it are worth
lifting rather than rewriting:

* **The liveness panel first** (ADR 0171 §3): split counts per feature, printing `NO SPLITS` explicitly. It
  costs one pass over the trees and it can end an investigation in one line. Here it did the opposite —
  it *prevented* the wrong conclusion, because "the model never learned climate" would have been written up
  as "there are no splits" without it.
* **A live-channel scale anchor in the same units, on the same rows.** Without panel C the flat climate
  numbers are unreadable: 0.057 stems is only meaningful against the 1.278 that a channel which *does* work
  produces through the same code path. Use an observed secant, not a derivative — a tree ensemble is
  piecewise constant (ADR 0105) — and check whether the observed shift clears the quantization step, which is
  what the two zero cells above are.

* Related: ADR 0178 (the frozen-climate control this answers), ADR 0112 (the teacher-forcing critique this
  points back to), ADR 0175 (the `n_prev` basis defect, resolved negatively by ADR 0178), ADR 0118
  (pooled-vs-within-group), ADR 0171 §3 (channel liveness), ADR 0105 (secant, not derivative),
  ADR 0004/0107 (CO2, standing).
