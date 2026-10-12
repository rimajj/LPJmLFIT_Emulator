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

## 4. Result (2026-10-12; chain 2463859 → 2463911, all steps exit 0)

Data: all 36 daily runs collected with PASS; arrays built; five members `C_3x256_seed0..4` trained; both ensembles
scored by `scripts/f2_relative_score.py HEdr_x CE_5seed` (full table:
`DATA/f2/runs/relative_score_HEdr_x_CE.md`). Harness rows as derived (second run 0.95–1.01, mean of three 0.80–0.85).
238 held-out cells per leg. Free runs.

**Primary — drift of GPP / NPP (2081–2100 ÷ 2021–2040 single-year error ratio), arm C vs control:**

| leg | GPP C (control) | NPP C (control) | ≤ 1.2 and below control? |
|---|---|---|---|
| UKESM ssp370 | 1.30 (1.29) | 1.41 (1.35) | no / no |
| IPSL ssp126 | 1.08 (1.06) | 1.14 (1.04) | ≤ 1.2 yes, below control no |
| IPSL ssp370 | 0.92 (1.00) | 1.08 (1.08) | GPP yes; NPP not below |
| IPSL ssp585 | 1.22 (1.26) | 1.27 (1.29) | no (> 1.2) |

**Primary FAILS on every leg.** **Falsifier fires:** on UKESM the GPP drift is within 0.01 of the control's and the
NPP drift is 0.06 *worse* (the falsifier was written as "within 0.05"; a worse result meets its intent — more climate
models did not reach the problem).

**Secondary — NPP typical ≤ 3× on MPI ssp126/370/585, both windows:** 2.99/3.03, 3.54/3.10, 2.87/3.24 — **fails**
(the control fails too: 3.38/2.70, 3.51/3.12, 3.14/2.86).

**Must not get worse — holds, and improves:** MPI GPP typical 1.89–2.26 (control 2.32–2.55), ET 1.55–2.36 (control
1.99–2.70); MPI drift 0.86–0.97.

**Against the expectations.** The MPI-leg scores did not worsen with 3× fewer samples per leg; GPP and ET levels
improved by ~10–20 % there and on UKESM late (GPP 3.20 → 2.73, ET 2.90 → 2.29) — but the early window improved as much,
so the drift ratio did not move. IPSL drift fell only for GPP on ssp370/585 (−0.08/−0.04). Two regressions not
pre-registered as tests, recorded: **NPP area totals worsened** from 0.3–2.5 % to 2.9–4.8 % (second run 0.2–0.5 %),
i.e. arm C has a systematic NPP bias of a few per cent on every leg, including the observed-weather control
(0.6 → 3.3 %); and the worst-10 % runoff error rose (≈ 6× → 8–11× a second run).

**Reading.** Widening the training climates lowers the daily model's level error everywhere but does not stop the gap
to the original growing under the two warmest unseen models, and on NPP it adds a small global bias. The growth is not
a coverage problem the data can fix at this network size; per §3 the next arm is a physically constrained carbon head
(GPP as light use × learned non-negative limiters), pre-registered separately.
