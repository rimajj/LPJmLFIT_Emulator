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

## 10. GV — the model-version split, measured (`scripts/explore_glob_gv.py`, job 2445825; expectations in its header)

Dev cells (every 10th), level pass at `max(10 %, two-member spread)`. Three one-variable parts.

**A — Feb-5 vs May-26 build, same GFDL-ESM4 climate, no model.** The two builds are indistinguishable on this panel.

| truth | scored against | historical | ssp126 | ssp245 | ssp370 |
|---|---|---|---|---|---|
| May member 9 / 10 | the other May member | 0.171 / 0.167 | 0.177 / 0.177 | 0.188 / 0.189 | 0.190 / 0.194 |
| May member 9 / 10 | one Feb member (8) | 0.164 / 0.167 | 0.177 / 0.177 | 0.181 / 0.182 | 0.192 / 0.180 |
| May member 9 / 10 | mean of Feb 2,3,4,6,7 | 0.276 / 0.267 | 0.284 / 0.276 | 0.290 / 0.283 | 0.287 / 0.280 |
| Feb member 8 (reference) | mean of Feb 2,3,4,6,7 | 0.270 | 0.282 | 0.280 | **0.281** (= §9's `ceiling_mean`: harness check passed) |

Area totals Feb-mean / May within 0.2 % (stems) and 0.8 % (biomass per tree); response slopes 0.95–1.07. The
pre-registered "inert" outcome holds.

**B — A7/A7s trained on Feb 2,3,4,6,7 (all legs), predicting May members 9, 10 and Feb member 8.** A7s at ssp370:
0.168 / 0.164 on May vs 0.166 on Feb 8; at ssp126/245 0.181–0.193 vs 0.193–0.198. No transfer loss. (A7s's
historical row, ~0.30, is not a result: its input is its own 1985–2014 state, which is the target there.)

**C — the October-build reanalysis family (GSWP3-W5E5, 1990–2019).** Forcing AND build differ from training, so the
Feb-vs-Oct numbers mix the two; within the Oct family the forcing is identical, so differences there are version only.

| truth (Oct-1 member) | other Oct-1 member | mean of the other five Oct members | Feb historical mean | Feb-trained A7 |
|---|---|---|---|---|
| pass rate | 0.164–0.165 | 0.213–0.216 | **0.004–0.005** | **0.003** |
| biomass per tree, prediction / truth | 0.99–1.02 | 0.86–0.87 | 0.68–0.69 | 0.73–0.74 |

Per member, relative to Feb member 2's GFDL historical window (area-weighted, dev cells):

| member (build) | stems | biomass per tree | median rooting depth (cm) | median min. water scalar |
|---|---|---|---|---|
| Feb 2 / May 9 | 1.000 / 0.999 | 1.000 / 1.006 | 256 / 258 | 0.157 / 0.158 |
| Oct 1, 2, 3 (Oct-1 build) | 0.956–0.959 | **1.46–1.48** | 181–183 | 0.128–0.129 |
| Oct 5 (Oct-6) | 0.970 | **1.22** | 196 | 0.128 |
| Oct 6 (Oct-7) | 0.976 | **1.04** | 204 | 0.128 |
| Oct 7 (Oct-8) | 0.963 | **1.11** | 187 | 0.129 |

* ⚠ **The October "family" is four models, not one.** On identical forcing, biomass per tree differs by up to 30 %
  between the Oct-1 build and the Oct-7 build. ADR 0314 §4 already found the parameters are read from a directory
  edited in place; this is the size of it.
* A Feb-trained emulator is useless on the October builds (0.3 % of cells vs the 16 % two Oct-1 runs agree on) —
  no better than the "nothing changes" null. Biomass per tree is the dominant miss; rooting depth and the minimum
  water scalar medians fail too.
* The pre-registered sign (boreal stems Oct/Feb > 1, from the weaker temperature mortality) is **falsified**: 0.90
  boreal, 0.96 temperate, 1.02 tropics. Confounded with the forcing change, so it says nothing about the parameter
  change alone.

**Reading for the owner's "work with every model version":** a version that does not change the panel (Feb → May)
costs nothing. A version that does (any October build) cannot be learned from other versions' runs; supporting it
needs its own runs or an input that tells the emulator which parameter values it is emulating, and the October builds
would each count as a separate version.

## 11. Correction by the owner: the requirement is per-version retraining, not transfer (2026-10-09)

Owner, verbatim: *"dude. of course an eulator trained on one model verison cant be used for another. it only works for
one model verision. but for any model version"*.

* **§2's GV row and §10's "reading for the owner" misread the requirement.** "Work with every model version" means the
  METHOD must reach the same skill on any build when it is trained on that build's own runs. It does not mean that one
  trained emulator must transfer across builds. §10's measurements stand as facts about the data (the Feb and May builds
  are indistinguishable; the October builds are four different models). Its transfer verdict answers a question nobody
  asked. **GV is redefined:** train on one build's runs, score on a held-out run of the SAME build, for every build,
  with the same amount of training data, and compare skill relative to each build's own run-to-run ceiling.
* **What that makes a defect:** anything version-specific baked into the method — a feature computed with one build's
  parameter values (`tstress_pft0` uses the Feb tropical cold limit 12.5 °C; the Oct builds use 14 °C, ADR 0314 §4), a
  hard-coded per-tree column (`wscal_mean` is absent in the Oct layout), or a hyper-parameter tuned on one build.
  Parameter-dependent features must be derived from each run's own parameter files.
* **The data limit, stated:** the Oct-1 build has three runs and one present-day window (no scenario legs); the
  Oct-6/7/8 builds have one run each. So per-version tests on those builds are present-day level only, and for the
  single-run builds only within-run (held-out places) at a flat 10 %. A warming-response test per version exists only
  for the Feb and May builds.
* The per-version test is `scripts/explore_glob_pv.py` (job 2445892), expectations in its header.

### 11.1 Result (job 2445892, `eval/scores_PV.csv`): the method retrains equally well on every build tested

One training member per build; pass rates at each build's own tolerance; "ceiling" = two runs of the same build.

| test | build | ceiling | A7s | A7s / ceiling | A7s biomass per tree | A7s tree-count response (deatt.) |
|---|---|---|---|---|---|---|
| ssp370, train 2 / 3 → 8 | Feb | 0.173 | 0.150 / 0.153 | 0.87 / 0.88 | 1.042 / 1.052 | 0.64 / 0.65 |
| ssp370, train 9 → 10 / 10 → 9 | May | 0.194 / 0.190 | 0.147 / 0.156 | 0.76 / 0.82 | 1.042 / 1.049 | 0.65 / 0.67 |
| ssp245, same pairs | Feb | 0.179 | 0.181 / 0.186 | 1.01 / 1.04 | 1.000 / 1.001 | 0.59 / 0.60 |
| ssp245, same pairs | May | 0.189 / 0.188 | 0.182 / 0.179 | 0.96 / 0.95 | 1.001 / 1.004 | 0.60 / 0.62 |

| present day, A7 (climate + place) | ceiling | A7 | A7 / ceiling |
|---|---|---|---|
| Oct-1, train 1 / 2 → 3 | 0.164 | 0.055 / 0.055 | 0.34 / 0.34 |
| Feb, train 2 / 3 → 8 | 0.172 | 0.049 / 0.047 | 0.28 / 0.27 |

Single run per build, A7 trained on the run's other places, flat 10 %: Oct-1 0.026–0.030 · Oct-6 0.039 · Oct-7 0.044
· Oct-8 0.035 · Feb 0.034–0.037. Area totals within 2.1 % of truth in every one of these rows.

* **Against the pre-registered test, literally:** the May ratio at ssp370 (0.76–0.82) and the Oct-1 present-day ratio
  (0.34) fall outside the Feb two-draw spread (0.87–0.88; 0.27–0.28), in opposite directions. In absolute terms the
  arm's numbers are the same on Feb and May to within 0.01 (pass, biomass, response); what differs is the denominator —
  May's two runs happen to agree more often (0.19 vs 0.17). The test was badly posed: its spread varied only the
  training member, not the noise in the ceiling itself. Recorded as written, not relabelled.
* **Reading:** no build shows a version-specific failure. The method's skill is set by the method (A7 is weak
  everywhere), not by which build it was trained on. The known version-specific input (`tstress_pft0` at the Feb
  threshold) did not visibly cost the Oct builds anything here; it stays a defect to fix (§11).
* **Not tested:** the warming response per version beyond Feb/May (no scenario legs exist for Oct builds); the
  recurrent arm per version (next, on the May build with one training member).

## 12. Arm A2g — the cell-level LSTM with a gap-crossing rollout (`scripts/explore_glob_lstm.py`, jobs 2445840/41)

Trained on members 2,3,4,6 × (historical + ssp126, historical + ssp245): 30-year segment curriculum, then free runs
from a random year ≤ 2014 through 2100, loss only where per-tree truth exists. All ten fold models beat carrying the
2014 state forward on held-out blocks (validation loss 0.077–0.088 vs 0.196–0.207). Cost ≈ 6–7 × 10⁻⁶ core-s per
cell-year (one core, inference). Harness check passed: member 8's own yearly statistics through the window
aggregator pass 0.975 of cells, totals identical to 1e-15.

GS370 (member 8, ssp370, 2071–2100, 5 809 dev cells):

| arm | pass | trees P/T | biomass per tree P/T | tree-count response: aggregate / deatt. slope | wood-density response: aggregate / slope |
|---|---|---|---|---|---|
| **lstm**, from the 2014 state | **0.125** | 0.994 | **1.054** | 0.95 / **0.86** | 0.96 / **0.99** |
| lstmCB (climate-blind twin) | 0.102 | 0.917 | 1.245 | 0.33 / 0.69 | 0.96 / 0.88 |
| lstm, free from 1985 | 0.113 | 0.997 | 1.037 | 1.09 / 0.80 | 0.72 / 0.75 |
| A7s (benchmark, §8) | 0.131 | 0.985 | 1.124 | 0.84 / 0.63 | 0.65 / 0.44 |

Within training years (free from 1985, scored at 2014): trees 0.974, biomass per tree 1.001.

**DP-G1 verdict:** (a) **fails** — 0.125 < 0.5 × `ceiling_mean` = 0.140 (and < A7s's 0.131); (b) passes (−0.6 %,
+5.4 %); (c) passes on the letter (0.86 vs the twin's 0.69; the member noise in the slope is ≈ 0.01); (d) passes
(−2.6 %, +0.1 %). ⇒ **does not survive round 1**, on (a) only. It beats A7s on totals and on both responses; the
binding per-quantity passes are stems (0.44) and biomass per tree (0.36).

⚠ **The climate-blind twin "responds".** Pre-registered expectation: ≈ 0. Measured: deattenuated tree-count slope
0.69 and the full wood-density aggregate (0.96, the same as the real arm's). A recurrent model with frozen climate
still knows how many years have passed, and every training scenario warms, so it learns the warming *pattern* as a
function of elapsed time (the Germany "warming as a clock" finding, ADR 0311, again). What climate adds on ssp370 is
the **size** of the tree-count change (aggregate 0.95 vs 0.33) and the totals (biomass per tree +5 % vs +25 %); the
wood-density response is not attributable to climate at all in this arm. So the twin of a recurrent arm is not the
zero-response null §4 assumed; (c) must be read as "climate adds 0.17 of slope", not "the arm responds with 0.86".
The ESM consequence: a model that reads the calendar would respond to a cooling or a stabilised scenario as if it
warmed. Test that before any recurrent arm is trusted: a scenario that does NOT warm (the constant-climate control
line S has, or ssp126's late plateau).

## 13. A2g retrained per build, one training run each (jobs 2445979/80, `eval/scores_A2g_pvF2.csv`, `_pvM9.csv`)

Same method and settings as §12, trained on ONE run (historical + ssp126 + ssp245), scored on a held-out run of the
same build under ssp370. All ten fold models beat 2014 persistence on held-out blocks (0.081–0.089 vs 0.187–0.231).

| build: train → test | ceiling (two runs) | pass | trees | biomass per tree | tree-count response (deatt.) | wood-density response |
|---|---|---|---|---|---|---|
| Feb: 2 → 8 | 0.173 | 0.115 | 1.001 | 1.078 | 0.78 | 0.95 |
| May: 9 → 10 | 0.194 | 0.101 | 0.994 | 1.097 | 0.71 | 0.97 |
| (Feb, four training runs, §12) | 0.173 | 0.125 | 0.994 | 1.054 | 0.86 | 0.99 |

Within training years (free from 1985, at 2014): Feb trees 0.979 / biomass 1.013; May 0.984 / 1.018.

* The retrained method behaves the same on both builds; May is slightly worse on every quantity (pass −0.014,
  biomass +2 points, response −0.07). With one draw per build the LSTM's own draw-to-draw spread is unmeasured, so
  this gap cannot be attributed to the build. (A7's draw spread, §11.1, was 0.003 in pass.)
* One training run instead of four costs 0.010 of pass and 0.08 of response slope (Feb).
* Untested per build: the Oct builds (no scenario legs to train a gap-crossing model on).

## 14. Does A2g read the climate or the calendar? — and an input leak in §12 (`scripts/explore_glob_clock.py`, jobs 2447108/09/10)

Expectations and the decision rule were written in the script header before the run. No retraining: the §12 fold
models were reloaded. Harness checks all passed: the reloaded models reproduce the stored predictions exactly (max
relative difference 0); the recomputed 20-year trailing climate means match the stored ones (≤ 5e-4); the twin's
scenario contrast is exactly 0; the panel's constant-climate and ssp370 legs start within 1.5 % of each other in stems.

⚠ **§14.1's "clean" rows and the leak price drawn from them are superseded by §15.1** (a retrain shows the leak was worth ≈ 0.01 of slope, not 0.21).

**14.1 An input leak in §12, found while writing the probe.** The prediction input fills missing state values forward
and then BACKWARD over the whole leg. A cell with no trees in 1985–2014 has no trait quantiles or species shares there,
so they were back-filled from the test member's own 2071–2100 truth. 303 of the 6 420 dev cells are exposed — the cells
trees colonise under warming (3.1 % of late-century stems). Training inputs carry the same fill (from training members,
so not a test leak, but the model learned to use it). Re-predicted with 2015–2100 masked before filling:

| arm, input | pass | trees P/T | biomass per tree P/T | tree-count response (deatt. slope) | wood-density response |
|---|---|---|---|---|---|
| lstm, as published (§12) | 0.125 | 0.994 | 1.054 | **0.86** | 0.99 |
| lstm, clean | 0.125 | 0.975 | 1.072 | **0.65** | 0.99 |
| lstmCB, as published | 0.102 | 0.917 | 1.245 | 0.69 | 0.88 |
| lstmCB, clean | 0.102 | 0.904 | 1.261 | 0.53 | 0.88 |

⇒ §12's tree-count response slope 0.86 was inflated by the leak; the clean value is **0.65**, the same as A7s (0.63),
and climate adds **0.12** of slope over the twin, not 0.17. The DP-G1 verdict is unchanged (fails (a); (b) and (c) still
pass on the clean numbers; (d), the free run from 1985, carries the same fill at its first year and was not re-run). §13's per-build runs use the same code and carry the same leak. The Germany LSTM
(`explore_de_rec_lstmstats.py`, prediction at line 777) has the same fill pattern; its exposure is not measured.

**14.2 Scenario contrast (truth exists): ssp370 minus ssp126 at 2071–2100, member 8, clean input.** Same start state
and same number of years in both legs, so elapsed time cancels.

| | stems: aggregate / deatt. slope | biomass per tree | SLA median | wood-density median |
|---|---|---|---|---|
| truth noise share (members 7 vs 8) | 0.13 | 0.37 | 0.47 | **0.59 — noise-dominated, not read** |
| ceiling (member 7) | 1.01 / 0.98 | 1.00 / 1.04 | 0.68 / 0.97 | — |
| **lstm** | **1.08 / 0.30** | 0.82 / 0.66 | −0.02 / 0.20 | — |
| lstmCB (twin) | 0 / 0 (harness) | 0 / 0 | 0 / 0 | — |
| A7s, ssp370 IN training (GM) | 0.94 / 0.51 | 0.69 / 0.76 | −0.26 / 0.26 | — |

On the 1985–2014 baseline, the ssp126 response as a share of the ssp370 response: stems truth 0.32 / lstm 0.10;
biomass per tree truth −0.13 / lstm −0.17. A model that only counted years would give ≈ 1.

* **The lstm does separate the scenarios** — the area total of the stems difference is right (1.08), and its weak
  scenario responds less than its strong one (more so than the truth). That is not a calendar.
* **But where the difference falls is mostly wrong:** the per-cell slope of the stems contrast is 0.30, below the
  pre-registered 0.5 ⇒ by the rule, stems are flagged; biomass per tree (0.66) is not; SLA (0.20) is flagged (its
  noise share 0.47 is just under the 0.5 reading limit). The direct window map, with ssp370 in training, does somewhat
  better on stems (0.51).

**14.3 No-warming drive vs the original model's constant-climate control (different build and cell set).** Changes
2071–2100 minus the first free decade, as a share of the same arm's ssp370 change (area-weighted):

| | stems | biomass per tree | wood-density median |
|---|---|---|---|
| lstm, no warming (6 420 dev cells, Feb build) | −0.22 | −0.38 | 0.83 |
| lstm, ssp126 | −0.22 | −0.18 | 0.58 |
| original, constant climate (panel, 1 050 cells, mean of m1–m3) | −1.05 | −0.61 | 0.43 (members 0.50 / 0.05 / 0.52) |
| original, ssp126 (panel) | −0.59 | −0.31 | 0.60 |

* The pre-registered rule (lstm minus original > 0.3) **fires for stems (+0.83) and wood density (+0.40)**, not for
  biomass per tree (+0.23). Recorded as written.
* ⚠ **The basis does not support reading it as a calendar effect**, and this was seen only after the run: the lstm
  vs panel gap is as large for **ssp126** (−0.22 vs −0.59) as for no warming, so it is a difference between the two
  cell sets/builds/baselines, not something specific to a non-warming climate. On the 88 cells the two sets share the
  ratios swing by several units between members (unreadable). This arm of the probe is therefore inconclusive.
* **What the panel does establish about the original model:** under constant climate its stems FALL by about as much
  as they rise under ssp370 (−0.34 vs +0.33 stems per patch), and its wood-density median drifts in the same direction
  as under warming (shares 0.05–0.52 by member). ⇒ **Part of the original's "warming response" in wood density is drift
  shared by every scenario**; a twin that reproduces it from elapsed time is partly reproducing real drift, not only
  faking a response. §12's reading ("the wood-density response is not attributable to climate at all") is therefore
  not evidence of a defect by itself.

**14.4 Reading.** The calendar hypothesis in its strong form is falsified for stems (the arm separates scenarios, with
the right total). Its weak form holds for where the response falls (per-cell slope 0.30). The leak fix removes a quarter
of the published tree-count response skill. A clean retrain (masking the fill during training too) is required before
any recurrent arm is scored again. Outputs: `eval/clock_leak.csv`, `eval/clock_contrast.csv`, `eval/clock_nowarm.csv`.

## 15. A2g retrained with a causal input fill — §14.1's "clean" numbers were a train/inference mismatch (jobs 2447157/58, 2447277; `eval/scores_A2g_causal.csv`)

`explore_glob_lstm.py --fill causal` (now the default): missing inputs are filled FORWARD ONLY, in training and in
prediction, so an input of year t never carries a value from a later year. That also closes a second, smaller leak
§14.1 did not: §14.1's "clean" input still filled backward inside 1985–2014, so the free run from 1985 (S85) saw later
historical years at its first step. `--fill leaky` reproduces §12. Same settings, seeds and folds as §12. All ten fold
models beat carrying the 2014 state forward (validation 0.083–0.092 vs 0.210–0.242). Harness checks as §12 (replay
pass 0.975, totals to 1e-15).

**Pre-registered (script header, before the run):** lstm pass ≈ 0.125 ± 0.01; tree-count response slope ≈ 0.65 (the
§14.1 re-prediction), read ± 0.1 as "the same"; twin ≈ 0.53; "well above 0.75 would mean the backward fill had also been
hurting it". **Measured — the slope expectation was WRONG:**

| GS370, member 8, ssp370 | pass | trees P/T | biomass per tree P/T | tree-count response (deatt. slope) | wood-density response |
|---|---|---|---|---|---|
| lstm, §12 (leaky training + input) | 0.125 | 0.994 | 1.054 | 0.86 | 0.99 |
| lstm, §14.1 (leaky model, clean input) | 0.125 | 0.975 | 1.072 | 0.65 | 0.99 |
| **lstm, causal retrain** | **0.119** | **0.996** | **1.068** | **0.85** | **0.97** |
| lstmCB, §12 | 0.102 | 0.917 | 1.245 | 0.69 | 0.88 |
| lstmCB, §14.1 | 0.102 | 0.904 | 1.261 | 0.53 | 0.88 |
| **lstmCB, causal retrain** | **0.112** | **0.919** | **1.228** | **0.59** | **0.86** |
| lstm causal, free from 1985 (S85) | 0.102 | 0.999 | 1.051 | 0.80 | 0.72 |

Within training years (S85 scored at 2014): trees 0.986, biomass per tree 0.990 (§12: 0.974 / 1.001).

**15.1 Why the expectation was wrong — measured, not inferred.** Late-century stems (2071–2100) predicted over truth,
area-weighted, on the 303 cells that are treeless in 1985–2014 and colonised later (3.1 % of late stems) vs all others:

| | exposed 303 cells | all other cells |
|---|---|---|
| lstm §12 (sees the future traits) | 1.014 | 0.993 |
| lstm §14.1 (leaky model, clean input) | **0.221** | 0.993 |
| lstm causal retrain | **0.951** | 0.997 |
| lstmCB §12 / §14.1 / causal | 0.557 / 0.002 / 0.303 | 0.926 / 0.926 / 0.934 |

The leak-trained model had only ever seen a treeless cell carrying (future) trait values; fed the training mean there
instead, it predicted almost no colonisation. That is an input it never saw in training — the ADR 0023
train/inference-shift trap — so §14.1 measured the mismatch, not the leak. Retrained on the input it gets at
prediction, the model predicts 95 % of colonisation from climate (the twin 30 %). **⇒ The leak was real but worth
≈ 0.01 of tree-count slope, not 0.21. §14.1's table, §14.1's "the leak fix removes a quarter of the published
response skill" and §14.4's sentence of the same content are superseded by this section.** The general lesson (now in
the `residual-diagnosis` skill's spirit): a leak cannot be priced by removing it at prediction time only; the honest
price is a retrain.

**15.2 DP-G1 on the causal retrain:** (a) **fails** — 0.119 < 0.140 (and < A7s 0.131; above the best null 0.100);
(b) passes (−0.4 %, +6.8 %); (c) passes — 0.85 vs the twin's 0.59, climate adds **0.26** of slope (member noise ≈ 0.01);
(d) passes (−1.4 %, −1.0 %). Verdict unchanged: **does not survive round 1, on (a) only.**

**15.3 Calendar test (§14.2) repeated on the causal models** (`explore_glob_clock.py --tag _causal`; harness-1 exact,
harness-2/3/4 pass). ssp370 minus ssp126 at 2071–2100, member 8:

| | stems: aggregate / deatt. slope | biomass per tree | SLA median |
|---|---|---|---|
| ceiling (member 7) | 1.01 / 0.98 | 1.00 / 1.04 | 0.68 / 0.97 |
| lstm, §14.2 (leaky model, clean input) | 1.08 / 0.30 | 0.82 / 0.66 | −0.02 / 0.20 |
| **lstm, causal retrain** | **1.19 / 0.47** | 0.79 / 0.64 | 0.02 / 0.22 |
| A7s, ssp370 IN training | 0.94 / 0.51 | 0.69 / 0.76 | −0.26 / 0.26 |

By the pre-registered rule stems are still flagged (0.47 < 0.5, noise share 0.13), now by a hair, and the aggregate
overshoots by 19 %. SLA stays flagged (0.22). Wood density is noise-dominated (share 0.58) and not read; its ratios in
`clock_nowarm_causal.csv` have a near-zero denominator (the arm's own ssp370 wood-density change) and are meaningless.
§14.3's no-warming comparison stays inconclusive for the reason §14.3 gave (cell set/build gap as large for ssp126).
**Reading:** the recurrent arm reads the climate for totals and partly for where the scenario difference falls; it is
still worse than the direct window map at placing it. Outputs: `eval/clock_*_causal.csv`.

**15.4 The Germany LSTM is not exposed.** `scripts/explore_de_lstm_leak_probe.py` (job 2447175): 0 of 907 test cells,
both GCMs, all three scenarios, have a state value missing at 1985 — Germany is forested from the first year — so its
backward fill never had anything to fill. Its published numbers stand.

**15.5 The per-build runs of §13, retrained with the causal fill** (jobs 2447168/69, `eval/scores_A2g_pvF2c.csv`,
`_pvM9c.csv`; one training run each, ssp370 on a held-out run of the same build):

| build: train → test | pass §13 → causal | trees | biomass per tree | tree-count response (deatt.) | wood-density response |
|---|---|---|---|---|---|
| Feb: 2 → 8 | 0.115 → **0.103** | 1.001 → 0.993 | 1.078 → 1.081 | 0.78 → **0.83** | 0.95 → 0.94 |
| May: 9 → 10 | 0.101 → **0.097** | 0.994 → 1.016 | 1.097 → 1.092 | 0.71 → **0.77** | 0.97 → 0.99 |

Within training years (free from 1985, at 2014): Feb 0.977 / 1.014, May 0.976 / 1.033. Same direction on all three
retrains: pass down 0.004–0.012, tree-count response up 0.05 (Feb/May) or unchanged (four-run model). The LSTM's own
draw-to-draw spread is still unmeasured, so these shifts are not attributed to the fill. §13's conclusion (the method
behaves the same on both builds, May slightly worse) stands.
