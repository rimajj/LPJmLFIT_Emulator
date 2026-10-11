# 0327 — Learned daily model without the humidity input (measurement + pre-registration)

* **Status:** Measurement done and pre-registration written 2026-10-11, before any run of the arm. Result appended
  below once measured.
* Opt-in `scripts/f2_train.py --drop-inputs huss` (the column is held at 0; default unchanged).
* Diagnostic: `scripts/f2_extrapolation_probe.py RE_5seed` (log `logs/f2-extrap.2463417.out`).

## 1. Measurement (before the arm): where does the carbon error grow under the unseen climate model?

ADR 0325: under UKESM ssp370 (a climate model never trained on) the best arm's GPP / NPP gap to the original grows
1.3× / 1.4× from 2021–2040 to 2081–2100; on the MPI legs it does not. Per held-out cell (238, GPP ≥ 50), the
2081–2100 climate against the range of every 20-year window the network trained on at that cell:

| leg | cells outside the training range: temperature (median excess) | specific humidity (median excess) | GPP / NPP drift (ADR 0325) |
|---|---|---|---|
| UKESM ssp370 (unseen model) | 100 % (+2.5 °C, p90 +5.2) | 100 % (+1.45 g/kg) | 1.32 / 1.42 |
| MPI ssp585 (trained model, hotter scenario) | 96 % (+0.76 °C) | 98 % (+0.30 g/kg) | 0.94 / 1.01 |

Across cells, the growth of the error (late minus early, relative to the cell's mean) follows the **humidity**
excess (Spearman: UKESM GPP +0.49, NPP +0.37; MPI ssp585 +0.29 / +0.33), and much less the temperature excess
(+0.14 / +0.15; MPI ssp585 +0.01 / −0.22) or the warming itself (≈ 0).

## 2. The original does not use humidity in the daily exchange

In this configuration (`relative_humidity: false`, `fire: "fire"` = the simple fire scheme, not SPITFIRE) the daily
humidity is read in `climate/dailyclimate.c:57` and used in exactly one live place: `tree/waterstress_tree.c:36`,
the tree **water-stress accumulator that feeds the annual mortality** (via `spitfire/getvpd.c`). It does not enter
photosynthesis, respiration, evapotranspiration, interception, snow, soil water or runoff. So for the fluxes this
network emulates, humidity is not a cause; the network uses it as a stand-in for things it correlates with in the
training climates (season, temperature, wetness), and that stand-in has no reason to hold once humidity leaves the
training range — which under warming it does at every cell.

## 3. Arm and pre-registered numbers

* **Arm H:** five seeds (0–4) of the current best setup (3 × 256 network, NPP = GPP − respiration), trained and run
  exactly as ADR 0323's arm R except `--drop-inputs huss`; verdict on their five-member ensemble **HE_5seed**,
  compared with **RE_5seed** on `scripts/f2_relative_score.py`. Deep-store drainage stays off, so only one thing
  differs from RE_5seed.
* **Primary (item 2 of the handoff):** UKESM ssp370 drift (2081–2100 ÷ 2021–2040 single-year error ratio) ≤ 1.2 for
  GPP and NPP (RE: 1.32 / 1.42).
* **Secondary:** NPP typical-cell error ≤ 3× a second run on both windows of the three MPI future legs (RE: 2.9–3.6).
* **Must not get worse:** GPP and ET typical ≤ 3× on the MPI legs; drift ≤ 1.2 on the MPI legs; area totals as in
  ADR 0325 §3.
* **Falsifier:** UKESM GPP / NPP drift still ≥ 1.3 ⇒ humidity was not the channel (the humid cells are also the
  tropical ones, so the correlation of §1 may be confounded), and the temperature excess (+2.5 °C) is the next
  suspect.
* **Expectation:** the drift falls but may not reach 1.2, because temperature is also out of range everywhere.
