# 0326 — Learned daily model: the deep store drains into runoff (pre-registration)

* **Status:** Pre-registered 2026-10-11, before any run. Result appended below once measured.
* **Amends nothing.** Opt-in `scripts/f2_train.py --deep-tau T` (days); `T = 0` (default) is the old bucket exactly.
* Scored on the yardstick of ADR 0325 (`scripts/f2_relative_score.py`).

## 1. The problem (ADR 0325 §4)

The best arm (RE = five-seed ensemble with NPP = GPP − respiration) moves 2.0–2.8 m of water into its deep store over
81 years where the original moves a median 0.22 m, and its runoff is 11–14× as far from the original as a second run
(30-year cell means, typical cell). 2.0–2.8 m over 81 years is 25–35 mm/yr, the same order as the runoff deficit.

## 2. Hypothesis

The bucket clamps the top-metre store to `[0, capacity]`, so over years the network's runoff + deep flux together
equal `prec − ET − Δstores`; with ET within 2–3× a second run that total is right. Only the **split** is wrong: the
network routes 25–35 mm/yr too much into "deep" and too little into runoff. In the original the deep layers are in
near balance (inflow ≈ their drainage, which is part of runoff). So: let the deep store drain into runoff at
`D/T` per day. Then long-run runoff = the network's runoff + its deep flux ≈ `prec − ET − Δstores` − (the original's
small deep change), and the deep store stays near `T ×` the split bias.

## 3. Arm and pre-registered numbers

* **Arm RE_dr365:** the RE ensemble (same five networks, no retraining), `--deep-tau 365`. One year is chosen a priori:
  it keeps the store to about one year of split bias (≈ 30 mm) and lags annual runoff by under a year.
  **Sensitivity, not a selection:** `--deep-tau 30` (RE_dr30) is run alongside and reported; the verdict is on T = 365.
* **Harness check (must hold or the run is void):** GPP, ET and NPP annual totals identical to RE_5seed's (the change
  touches only runoff and the deep store, neither of which the network sees).
* **Pass (ADR 0325 §3 limits):** runoff typical-cell error ≤ 3× a second run on both 30-year windows of the three MPI
  future legs; worst-10 % ≤ 3×; area totals within 5 % (MPI) / 25 % (unseen climate model); no drift (error ratio
  2081–2100 ÷ 2021–2040 ≤ 1.2) on every leg; median |deep-store change| over 81 years ≤ 2× the original's (measured
  in the same run).
* **Expectation:** runoff typical 2–4× (it inherits the ET error in mm, divided by a smaller runoff total); a miss in
  dry cells, where runoff is small, would show in the worst-10 % column.
* **Honest framing.** The deep-store criterion is met largely by construction once the store drains. The real test is
  runoff, and whether the split error was the cause of the 11–14×. If runoff stays far off, the cause is elsewhere
  (e.g. the timing of the network's runoff, or the top-metre store) and this record says so.
