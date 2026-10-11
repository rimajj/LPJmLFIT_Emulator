# 0328 — Learned daily model trained on more climate models (data + pre-registration)

* **Status:** Pre-registered 2026-10-11, before the new runs of the original had finished. Result appended below.
* **New data (runs of the original):** the panel legs of GFDL-ESM4, IPSL-CM6A-LR and MRI-ESM2-0 × ssp126 / ssp370 /
  ssp585, members 1–4, re-run with daily output (36 runs). Leg names `<model>_<scen>_daily`
  (`scripts/trackd_panel.py make --no-chain` + `submit-legs`): the same climate, restart, binary and physics as the
  existing annual-only legs; the config differs only in the output list (checked by diff). Existing runs untouched.
* Tooling: `scripts/f2_train.py --train-legs / --test-legs` (writes `runs/<tag>/legs.json`, which
  `scripts/f2_relative_score.py` now reads), chain `scripts/f2_chain_new_legs.py`.

## 1. Why

Under UKESM ssp370 the gap to the original in GPP / NPP grows 1.29× / 1.35× over the century (ADR 0327, with humidity
removed). Every held-out cell ends that century 2.5 °C warmer than any training climate, and 66 % with more leaf
area than any training run; the error grows where the stand overshoot is largest (Spearman +0.41 GPP / +0.46 NPP)
— ADR 0327 §4 and the probe log `f2-extrap2`. The network has seen one climate model (MPI) plus observed weather.
More climate models in training widen both the climate and the stand it is handed.

## 2. Arms (only the training data differ)

Both: 3 × 256 network, NPP = GPP − respiration, humidity removed (ADR 0327), deep store drains at D/365 (ADR 0326),
40 M training samples in total (the same budget as before, so 3× fewer per leg), verdict on a five-seed ensemble.

* **Control `HEdr_x`:** the existing ADR 0327 members (trained on observed weather + MPI ssp126/370), re-scored.
* **Arm C `CE_5seed`** (members `C_3x256_seed0..4`): trained on observed weather + MPI ssp126/370 + **GFDL and MRI,
  all three scenarios**.
* **Test legs, both arms:** MPI ssp585, **UKESM ssp370** and **IPSL ssp126/370/585** — two climate models neither arm
  ever saw (IPSL and UKESM are the two warmest of the five). The control is also scored on the GFDL / MRI legs, to
  show how far off it is on models it never saw but arm C trained on.

## 3. Pre-registered numbers (ADR 0325 yardstick)

* **Primary:** arm C's GPP and NPP drift (single-year error ratio 2081–2100 ÷ 2021–2040) ≤ 1.2 on UKESM ssp370 and on
  each IPSL leg, **and** lower than the control's on the same leg.
* **Secondary:** NPP typical-cell error ≤ 3× a second run on both windows of MPI ssp126/370/585.
* **Must not get worse than the control:** GPP / ET typical on the MPI legs (≤ 3×); MPI drift ≤ 1.2.
* **Falsifier:** arm C's UKESM GPP and NPP drift within 0.05 of the control's ⇒ more climate models do not reach the
  problem, and the next arm is a physically constrained carbon head.
* **Expectation:** the drift falls on IPSL more than on UKESM (UKESM's late-century climate is outside even the
  widened range at most cells); MPI-leg scores move little or worsen slightly (fewer samples per leg).
