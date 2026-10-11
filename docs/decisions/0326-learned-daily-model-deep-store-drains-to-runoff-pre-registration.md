# 0326 — Learned daily model: the deep store drains into runoff (pre-registration)

* **Status:** Pre-registered 2026-10-11, before any run. **Result (same day, §4): partial — the split is fixed and stable, runoff still fails at 3.9–5.5× (limit 3×) because what is left is the evaporation error carried through.**
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

## 4. Result (2026-10-11; runs `RE_dr365`, `RE_dr30`; logs `f2-RE-dr365.2463411`, `f2-RE-dr30.2463412`)

* **Harness check holds:** GPP, ET and NPP annual totals are bit-identical to RE_5seed (max difference 0.0).
* **Runoff, typical cell, 30-year means** (emulator error ÷ second-run error, early/late window):

  | leg | RE_5seed | **RE_dr365** | RE_dr30 |
  |---|---|---|---|
  | MPI ssp126 | 12.8 / 11.4 | **4.5 / 4.0** | 4.4 / 4.1 |
  | MPI ssp370 | 13.8 / 10.8 | **4.8 / 3.9** | 5.1 / 3.9 |
  | MPI ssp585 | 13.6 / 11.5 | **4.6 / 5.2** | 4.5 / 4.9 |
  | UKESM ssp370 (unseen) | 12.9 / 12.6 | **5.0 / 5.5** | 5.1 / 5.6 |

  Worst-10 % cells 4.5–7.4 ✗. **Fails the 3× limit**, 2.5–3× better than before.
* Area totals within 1.1–1.8 % (MPI) ✓, 3.7 % (UKESM) ✓. No drift: 0.78–1.01 ✓. Deep store, median |81-year change|:
  45–68 mm (T = 365) against the original's **85–279 mm** in the same runs ✓ (the original's own deep store moves
  more than the "0.22 m" of ADR 0321 on most legs; its worst-10 % cells move ~2 m, which a draining store cannot
  reproduce). Daily runoff goes slightly negative on a few days (minimum −2.5 to −10 mm), when the store is drawn
  below zero.
* **T matters only for single years**, as expected: single-year runoff ratios 7.5–10.6 at T = 365, 10–14 at T = 30
  (the original holds a wet year's drainage in its deep layers for longer than a month).
* **Why runoff still fails (measured, MPI ssp370 and UKESM, both windows):** across held-out cells the 30-year runoff
  error is the negative of the ET error, correlation **+0.84 to +0.92**. In a typical cell runoff (161–198 mm/yr) is
  much smaller than ET, so ET's error (2–3× a second run in ET terms) is **4.8–7.5 % of runoff**, while the part not
  explained by ET is **1.9–2.2 %**, about 1.2–1.4× a second run's runoff spread (1.4–1.8 %). The split error is
  gone; the rest of runoff can only improve through ET.

**Verdict:** adopt `--deep-tau 365` for every later arm (stability fixed; nothing else changes). Runoff stays failing
until ET gets about 1.5× closer to the original. Whether a 3× runoff limit is consistent with a 3× ET limit — it
is not, when runoff is a small residual of rainfall minus ET — is a question for the owner (ADR 0325 §3 numbers are
proposed, not accepted).
