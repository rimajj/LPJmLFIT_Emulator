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
