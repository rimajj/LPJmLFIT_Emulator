# 0372 — The running-means daily network as a release candidate: owner decision on the drift criterion, and a place description from PAST weather (pre-registration)

* **Status:** pre-registered 2026-10-24, before any fit or run of this record. Results: §6, added after the runs.
* **Owner decision (2026-10-24), after ADR 0371:** *"well, the goal is to have the best possible emulator. if the new
  networks deliver 15% better results at 1.2 times the cost i think that is a good candidate"*. ⇒ For choosing the
  daily network, the per-leg drift clause of ADR 0367 (no leg's drift more than 0.08 above the deployed networks') is
  **replaced** by: the candidate must not be worse than the deployed networks at the END of the century (late-window
  error), plus a worst-leg limit calibrated on ADR 0371's same-design null. A candidate whose advantage shrinks over
  the century but which stays better is acceptable. This applies to the daily-network choice; the emulator's own
  "no drift against the original" goal is unchanged and still checked against the second run of the original.
* **Not for the paper** unless the owner says so (continues ADR 0368–0371).

## 1. Why a new network is needed first

MEP (ADR 0369/0370) describes each place by the mean seasonal cycle and daily spread of its weather over **2020–2049
of the same run** — 30 years ahead of most of the days it is used on. An emulator inside a climate model does not have
that. Two versions that use only the past, everything else exactly as MEP (MLP 256×3, the exponential running-mean
bank, `xtf_daily.py train`, 5 seeds s0–4):

* **MEPh** — the description of the 30 observed years before the run, 1990–2019 (GSWP3-W5E5, the history every leg
  shares), fixed for the whole run. Deployment: the setup carries 52 numbers per cell (or the ESM computes them from
  its own spin-up climate).
* **MEPt** — the description of the 30 years before EACH year, rebuilt once a year (2020 uses 1990–2019, 2050 uses
  2020–2049 of the run's own weather, …), so it follows the climate. Deployment: 30 years × 56 numbers per cell, one
  update a year.

`xtf_daily.trailing_place`; checked before any fit: its 2020 row equals the old formula on 1990–2019 to 2e-6 and its
2050 row equals MEP's description to 2e-5.

## 2. Venue

ADR 0370 §2 unchanged: 5-member ensemble, member 2, emulated stand `stand_emul_main2`, 2020–2100, 30 rising-CO2 legs
(CO2-fixed reported), held-out cells with mean GPP ≥ 50, against the deployed ensemble B; q = typical error ÷ B's per
leg × window × flux. Cost: one network's daily step on one core (`xtf_daily.py bench`), ÷ B's.

## 3. Rule (per candidate; the owner's criterion made checkable)

1. median q over legs × windows: NPP ≤ 0.95, GPP / ET / runoff ≤ 1.05 (ADR 0367's accuracy part);
2. median q over legs in the LATE window (2071–2100) ≤ 1.00 for every flux (not worse than the deployed networks at
   the end of the century);
3. worst leg-window q ≤ max(1.25, the same-design null's largest max(q, 1/q)) = GPP 1.27, NPP 1.25, ET 1.26, runoff
   1.28 (ADR 0371 §5, N1);
4. cost ≤ 1.35 × B's.

(For reference, the look-ahead MEP passes 1–4.) **Choice:** among MEPh and MEPt the passing one with the lowest mean
of the four median q; if both pass and differ by < 0.01, the simpler MEPh. If neither passes, nothing is packaged.

## 4. If one passes — the package (separate commit, gated)

(a) `landemu` gets the running-mean bank (32 numbers per cell, updated daily, started from the warm-up year as in
training) and the place description (fixed, or the yearly trailing version) as an **opt-in daily input declared in
`daily.npz`**; a release without it runs exactly as before (gate: the current nitrogen-on releases reproduce their
outputs bit for bit). (b) A fold release copy `non_fold_v2<arm>` = `non_fold_v1` with only the daily networks
replaced, gated numpy == PyTorch on the daily step (max relative difference ≤ 1e-5) and on the extras (online daily
update == the training arrays). (c) Its end-to-end one-core cost per cell-year (`run_emulator_non.py`, ADR 0344
basis), against the release's 7.29e-3 and the original's 0.95. The networks are trained on the 8 training climate
models (the fold split); a deployment release on all 10 would be a follow-up. No current release is replaced without
the owner's word.

## 5. What this record does not do

No full-grid run; no paper text; no change to the tree-death work.
