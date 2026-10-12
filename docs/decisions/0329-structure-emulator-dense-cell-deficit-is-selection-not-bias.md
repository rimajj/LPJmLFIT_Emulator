# 0329 — The structure emulator's dense-cell deficit is a selection effect, not a bias; the real limit is the per-cell climate response

* **Status:** accepted (measurement), 2026-10-12. Discharges STATE NEXT item 4 ("remove the dense-cell low bias —
  measure first, then one pre-registered treatment") and EXECUTION_PLAN rev. 3 priority 2's first half. **No treatment
  is pre-registered**: the measurement shows there is no systematic bias to treat.
* **Depends on:** ADR 0316 §11–13 (the best arm A7rH; the dense-cell totals "low in all 15 cases"), ADR 0318 §2 (the
  relaxed standard, dense = truth ≥ 5 trees per patch), ADR 0184 (derive what a null must return).
* **Scripts:** `scripts/explore_panel_dense_bias.py` (decomposition, knob `SEED`; output
  `xpanel/eval/dense_bias_s<seed>.{txt,csv}`, `dense_bias_calib_s<seed>.csv`), `scripts/explore_panel_lin_response.py` (per-cell linear-response probe;
  `xpanel/eval/lin_response.csv`). Both read saved predictions (A7rH, seed 1, mode `cnt`) and level tables; seconds.

## 1. Question

ADR 0316 §13 found A7rH's dense-cell tree-count area total LOW in all 15 held-out-climate-model cases (−0.5 to −5.1 %;
a second run within 0.5 %). Is that the anchor, the learned climate shift, the warming, or the unseen run itself?

## 2. Decomposition (tree count, 2071–2100, area-weighted totals)

T = the unseen run (m4); P = A7rH; A = its per-cell anchor (mean of the 5 training runs × 28 training legs); O = the
oracle expected value (mean of the 5 training runs on the SAME held-out leg — never available to the emulator).
P − T = (P − A) learned shift + (A − O) minus the true shift + (O − T) the unseen run's own deviation.

Harness: the `dense_T` set reproduces ADR 0316 §13's 15 numbers (−0.46 … −5.06 %).

| dense set defined by | P − T, 15 cases | P − O (shift error) | O − T | second run R − T |
|---|---|---|---|---|
| truth ≥ 5 (ADR 0318's set) | −0.5 … −5.1 %, **15/15 low** | +0.4 … −4.8 %, 11/15 below −1 % | −0.1 … −1.2 % | −0.0 … −1.0 % |
| oracle ≥ 5 (same leg, no truth) | −0.2 … −4.9 %, 15/15 low | +0.3 … −4.9 % | −0.8 … +0.3 % | −0.7 … +0.3 % |
| **anchor ≥ 5 (known before the run)** | **−3.7 … +1.5 %, 8 low / 7 high, median 0.0 %** | −3.9 … +1.5 % | −0.9 … +0.2 % | −0.8 … +0.2 % |

* The unseen run's own deviation is small (O − T within 1 %), and m4's 2000–2019 dense total is only +0.4 % above the
  training runs': **not the member.**
* No growth with warming: anchor-dense medians ssp126 +0.3 %, ssp370 −1.8 %, ssp585 +0.5 %. **Not the warming.**
* **The "all 15 low" is a selection effect.** Defining dense cells on the held-out leg's own outcome (the truth, or the
  oracle on that same climate) selects cells that THIS climate pushed into the dense class — exactly the cells whose
  response the emulator only partly predicts, so they come out low. Defined on information available before the run
  (the anchor), the error has no sign. The second run is immune because its error is independent of the leg's
  response. The all-cell total is likewise unbiased (median −0.4 %).
* **The same on all five LightGBM seeds:** truth-defined set 15/15 low on every seed (medians −1.6 to −2.0 %);
  anchor-defined set 7–8 of 15 low, medians −0.05 to +0.13 %, ranges within −3.7 … +1.9 %; share of the per-cell shift
  carried 0.29–0.30, true-on-learned 1.10–1.14 (medians over the 15 cases).

## 3. What is actually limiting: the per-cell climate response

Per-cell calibration against the oracle (`dense_bias_calib.csv`, medians over the 5 held-out models):

| | ctl_obs (a training climate) | ssp126 | ssp370 | ssp585 |
|---|---|---|---|---|
| share of each cell's true shift the learned shift carries (slope of learned on true) | 0.79 | 0.49 | **0.27** | 0.34 |
| share of the oracle's shift variance that is signal, not 5-run noise | 0.97 | 0.97 | 0.96 | 0.96 |
| true shift regressed on learned shift (1 = calibrated) | 1.15 | 1.17 | 1.16 | 1.06 |

So the oracle's per-cell response is real (96 % signal), the learned shift is nearly calibrated in scale (true ≈
1.06–1.17 × learned), but it explains only ~25–50 % of how cells differ in their response to an unseen climate model.
That is unexplained variance, not shrinkage: inflating the learned shift by the 1.15 seen on the training control would
recover little.

**The per-cell linear-response probe (pre-registered in its header):** OLS of each cell's tree count on the leg climate
(tmean; tmean + climatic water balance; tmean + precipitation) over the same training rows the anchor averages,
predicted at the held-out climate. It carries **0.13 / 0.34 / 0.35** of the true shift (A7rH 0.29); its anchor-free
dense total is within 1.5 % of the oracle in 3–6 of 15 cases (A7rH 7). **Falsifier fired as written (< 0.4)**: a
per-cell linear temperature/water response is NOT the missing information, so the sensitivity-feature arm named in ADR
0316 §12 is not run.

## 4. Decision

* No dense-cell bias correction. Any additive or multiplicative dense correction would bias the anchor-dense and
  all-cell totals, which are unbiased now.
* ADR 0318's dense total criterion (D3) keeps its definition (truth ≥ 5, as the owner's "dense cells" means), but its
  reading changes: a deficit on that set is partly selection; report the anchor-defined total beside it.
* The structure item in the plan becomes: **explain more of the per-cell response to an unseen climate.** The only
  lever with evidence so far is more climate models in training (4 → 9 models: pass rate +0.023, ADR 0316 §10). Next on
  the structure side is the year-by-year no-drift test and the global venue, not a bias treatment.

## 5. Not done

* Biomass per tree was not decomposed (tree count only).
* Why an unseen climate model's per-cell response is idiosyncratic (which climate statistics carry it) is not
  measured.
