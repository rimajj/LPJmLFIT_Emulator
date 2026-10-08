# 0315 — The global round-1 venue for the emulator arms: splits, folds, and the decision point written BEFORE any arm is scored

* **Status:** **proposed — pre-registration** (2026-10-08). Line X's own venue definition under ADR 0313. The change it
  implies to `EXECUTION_PLAN.md` (DP-A1 was written for Germany) is an **integration point**, not an edit: the plan is
  integrator-owned and line X does not write into it.
* **Date:** 2026-10-08.
* **Line:** X. Tier-1 block 0310–0329. **Next free number: 0316.**
* **Depends on:** ADR 0313 (the data), ADR 0314 (the climate inputs), ADR 0106 (the
  acceptance criterion and its tolerance), ADR 0184 (derive the nulls' values before the run), plan §4 (Track Y).

## 1. Why a new decision point

DP-A1 (plan §9) tests a Germany arm on a **held-out climate model**, 1985 → 2044, with per-tree truth every year. The
global set (ADR 0313) has **one** climate model, **eight** independent members, **three** scenarios, and per-tree
truth only in **1985–2014** and **2071–2100** — never 2015–2070. So the held-out axis must change (member, scenario,
model build), and the free run must cross 56 years with no per-tree truth. Writing the new test now, before any
arm has a number on this set, is the point of this record.

## 2. The registry (`scripts/explore_glob_registry.py`, outputs under `…/billing_global/registry/`)

* **members.parquet** — 38 member-windows, each with the build date read from its own run log.
* **folds.parquet** — every cell's 5°×5° block and fold 1–5. Blocks are assigned greedily (largest tree-bearing count
  first, SHA-256 of the block id breaking ties) to balance tree-bearing cells across folds. `is_dev` = `Cell % 10 == 0`
  (the converted `ind_dev/` tables). Every score is cross-fitted: train on folds ≠ k, score fold k, all five k.
* **splits.parquet** — the four splits below, per member-window.
* Built 2026-10-08 (job 2445735), all six registry checks passing: 38 member-windows, builds Feb-5 (24), May-26 (8),
  Oct-1/6/7/8 (6); historical and scenario legs share one build per member; **58 187 tree-bearing cells**, folds of
  11 637–11 638 (1 154–1 178 dev cells each); no rock cell carries trees.

| split | train | val | test | what it tests |
|---|---|---|---|---|
| **GS370** (primary) | Feb-build members 2,3,4,6 — historical + ssp126 + ssp245 | member 7, same legs | **member 8, ssp370** | warming beyond the training scenarios, on an unseen member |
| GS245 | members 2,3,4,6 — historical + ssp126 + ssp370 | member 7 | member 8, ssp245 | interpolation between scenarios |
| GM | members 2,3,4,6, all legs | member 7 | member 8, all legs | an unseen member only (noise) |
| GV | Feb members 2,3,4,6,7 | member 8 | May-build members 9,10 (all legs) and the Oct-build reanalysis members | a different model build (owner: *"the emulator needs to work with every model version"*) |

## 3. The free run that is scored

From the test member's **own 2014 per-tree state** (the last year of its historical table — the state its scenario
legs restarted from), the arm runs **2015 → 2100** on that scenario's GFDL-ESM4 climate with no access to truth, and
is scored on **2071–2100** (30-year per-cell means) on the held-out fold's tree-bearing cells. Beside it, always: the
**within-training free run** 1985 → 2014 from the 1985 state (separates step bias from extrapolation, plan §4.3).
2015–2070 can be checked only on stand totals against `output_transient/` (vegetation carbon, cover); that check is
reported, not gated.

## 4. Statistics and nulls (plan §4, unchanged in kind)

* **Level:** per-cell fraction inside `max(10 %, the two-member spread)` for stems (> 5 m, the writer's population),
  biomass per stem, and the medians of SLA, wood density, maximum rooting depth and minimum water scalar. The two-member
  spread is members 7 vs 8 on the same cells and years. ⚠ At 25 patches that spread is wider than Germany's 250-patch
  one, which **loosens** the tolerance; every pass rate is therefore reported **twice** — at `max(10 %, spread)` and at
  a flat 10 %.
* **Response:** per cell, (scenario 2071–2100) − (historical 1985–2014), arm vs truth, deattenuated slope and the
  area-weighted aggregate (ADR 0111). This is scenario − historic, labelled so (no constant-climate control exists in
  this set).
* **Nulls, in the same table:** persistence (the 2014 state carried unchanged to 2071–2100); the lookup null (the
  training members' mean of the same cell and leg — for GS370 the ssp245 leg, the nearest training scenario); the
  **climate-blind twin** (the same arm with climate frozen to its 1985–2014 cell mean); the other member as the ceiling.
* **Values the nulls must return, written before the run (ADR 0184):** persistence's response is **exactly 0** by
  construction, so its deattenuated response slope is 0; the climate-blind twin's response is whatever the arm's own
  free-run drift is — if it is not ≈ 0 the arm drifts, and the twin's slope is the drift's share of any response
  claimed; the ceiling's level pass rate is ≤ 1 and is **measured, not assumed** (it is the denominator in DP-G1 (a)).

## 5. DP-G1 — the decision point (replaces DP-A1 for the global venue; thresholds may be tightened, never loosened)

An arm **survives round 1** on GS370 if all of:

* **(a)** its level pass rate is **≥ 0.5 × the member-7-vs-8 ceiling** on the same cells (both tolerances reported;
  the gate uses `max(10 %, spread)`, as ADR 0106 does);
* **(b)** area-weighted stems and biomass per stem at 2071–2100 are within **±10 %** of the truth's;
* **(c)** its response **beats the climate-blind twin by more than the member-to-member spread of the response**
  (members 7 vs 8), on the deattenuated slope;
* **(d)** its within-training free run passes (b) at 2014 — an arm that drifts inside its own training years has not
  earned an extrapolation verdict.

GS245 and GM are reported with the same statistics, ungated. **GV is reported, not gated, in round 1:** the pass rate on
the May/Oct-build members relative to the Feb ceiling, so a version effect is *measured*. Speed (core-s per cell-year,
one core) is reported for every arm beside its score.

## 6. What this does not decide

* It does not drop any arm; DP-G1 is applied when an arm has a free run on this venue.
* It does not replace the across-climate-model test, which stays with line S's five-model panel.
* It does not touch the acceptance criterion (ADR 0106): passing DP-G1 is "survives round 1", never "finished".
* The plan edit (DP-A1 → DP-G1 for line X's venue) is raised as an integration point.

## 7. Baselines measured before any arm, and one tightening (2026-10-08, `scripts/explore_glob_eval.py`, job 2445751)

Scored on GS370: 5 809 dev cells carrying trees in member 8's 1985–2014 or 2071–2100 window (dev = every 10th cell;
**not** the all-cell basis of the acceptance criterion). Harness check passed: carrying 1985–2014 forward gives a
response of exactly 0.

| baseline | cells passing all six | flat 10 % | trees (area-weighted, P/T) | biomass per tree | tree-count response, aggregate / deattenuated slope |
|---|---|---|---|---|---|
| ceiling (member 7) | **0.173** | 0.136 | 0.998 | 0.999 | 0.98 / 0.99 |
| 1985–2014 carried forward | 0.060 | 0.046 | 0.877 | 1.298 | 0 / 0 |
| 2014 snapshot carried forward | 0.057 | 0.045 | 0.907 | 1.283 | 0.24 / 0.09 |
| lookup: training members' ssp245 | **0.100** | 0.076 | 0.954 | 1.205 | 0.63 / 0.83 |

⚠ **Two independent runs of the original model agree in only 17 % of cells on all six quantities** (stems 68 %,
biomass per tree 50 %, rooting-depth median 51 %): at 25 patches the per-cell criterion is near the original's own
noise. ⚠ **DP-G1 (a) as written (≥ 0.5 × 0.173 = 0.087) is passed by the lookup null (0.100)** — no power. Tightened,
as §5 permits: **(a) also requires a pass rate above the best null's (0.100)**. Honest timing: decided after the
baselines and stated to the owner before the first arm finished, but written here after it; it changes no verdict
below (A7s passes (a) either way, A7 fails either way).

## 8. First arm on the venue: A7, the direct window map (`scripts/explore_glob_a7.py`, job 2445762)

| variant | pass | trees P/T | biomass per tree P/T | tree-count response agg / deatt. slope | wood-density response agg / slope |
|---|---|---|---|---|---|
| A7 (window climate + place) | 0.039 | 1.002 | 1.060 | 1.08 / 0.65 | 0.37 / 0.51 |
| A7cb (climate-blind twin) | 0.036 | 0.914 | 1.293 | 0 / 0 | 0 / 0 |
| **A7s** (+ the member's own 1985–2014 state) | **0.131** | 0.985 | **1.124** | 0.84 / 0.63 | 0.65 / 0.44 |
| A7scb (its twin) | 0.099 | 0.915 | 1.290 | 0 / 0 | 0 / 0 |

**DP-G1 verdicts:** A7 fails (a). **A7s passes (a)** (0.131 > 0.100 and > 0.087), **fails (b)** (biomass per tree
+12.4 % > 10 %), passes (c) (response slope 0.63 vs its twin's 0; the ceiling's deattenuated slope is 0.99, so member
noise is far smaller than the gap), (d) not applicable (no stepping). ⇒ **A7s does not survive round 1 as specified;
it is the benchmark the recursive arms now have to beat** (pass 0.131, response slope 0.63).

## 9. A7 on the other splits (job 2445785) — and a defect in the ceiling ratio

| split · test scenario | ceiling | A7s | A7scb | A7 | A7s biomass per tree | A7s tree-count response (deatt.) | A7s wood-density response |
|---|---|---|---|---|---|---|---|
| GS245 · ssp245 | 0.179 | **0.186** | 0.161 | 0.055 | 1.003 | 0.57 | 0.46 |
| GM · ssp126 | 0.179 | **0.195** | 0.168 | 0.062 | 0.971 | 0.49 | 0.31 |
| GM · ssp245 | 0.179 | **0.191** | 0.169 | 0.061 | 1.006 | 0.60 | 0.47 |
| GM · ssp370 | 0.173 | 0.162 | 0.117 | 0.049 | 1.048 | 0.66 | 0.47 |
| GS370 · ssp370 | 0.173 | 0.131 | 0.099 | 0.039 | 1.124 | 0.63 | 0.44 |

* **The biomass-per-tree failure on GS370 is extrapolation error:** with ssp370 in training (GM) it is +4.8 %, held out
  +12.4 %.
* **The response shortfall is not:** ~0.5–0.66 of the truth's even with the scenario in training ⇒ a property of the
  direct map (it shrinks toward the training mean), not of the held-out climate.
* ⚠ **"≥ k × the ceiling" is not a ceiling for a model that predicts the ensemble expectation.** A7s beats member 7 on
  three of five rows: a mean prediction sits closer to any one member than another member does. So DP-G1 (a), and
  plan §4's "read every arm as a ratio to the ceiling", reward smoothing. (b) and (c) are unaffected.
* **Measured (job 2445815):** the ORACLE expectation — the mean of members 2,3,4,6,7 under ssp370 — passes **0.281**
  of cells (flat 10 %: 0.226) against the single member's 0.173; totals 0.999 / 1.006, response slopes 0.99 / 1.02.
  (An earlier draft of this section proposed scoring the q05–q95 distribution as the fix; that is wrong — an averaged
  quantile is as smooth as an averaged median.)
* **Amendment to DP-G1 (a):** an arm that predicts the ensemble expectation (A7, any deterministic regressor) is held
  to **0.5 × `ceiling_mean`** (0.140 on GS370); an arm that samples one realization to 0.5 × `ceiling` (0.087); both
  must beat the best null. A tightening, as §5 permits. **A7s (0.131) now fails (a) as well as (b).**
