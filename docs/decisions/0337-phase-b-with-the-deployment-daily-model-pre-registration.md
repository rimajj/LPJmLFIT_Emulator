# 0337 — Phase B with the deployment daily model (arm D): the daily model fed the emulated stand, pre-registered

* **Status:** pre-registered 2026-10-14, before its runs; result §4 (FAIL, falsifier fired on two legs); end-to-end timing §5.
* **Depends on:** ADR 0331 (the stand map and phase B on the control ensemble, same rule), ADR 0335/0336 (arm D =
  the deployment daily model, `DE_5seed`; the run-to-run noise of one ensemble, §6), ADR 0325 (the second-run
  yardstick and the proposed bars).
* **Scripts:** `scripts/explore_panel_stand_map.py` (`fit --g <model> --hold k`, `arrays`), `scripts/f2_train.py
  --ensemble D_3x256_seed0..4 --stand-dir`, `scripts/f2_relative_score.py`, `scripts/f2_relscore_compare.py`.

## 1. Why

ADR 0331 measured the cost of the emulated stand on the control ensemble (`H` members, trained on observed weather +
two MPI scenarios). The model that will be deployed is now arm D (all 14 legs in training). Its own errors are smaller
on most legs, so the same stand error may add relatively more; and ADR 0331 covered only the five legs of climate
models the control ensemble had not seen. This record measures the full learned emulator's daily fluxes — arm D fed
the structure emulator's stand — on all 13 climate-model legs.

## 2. Design (one variable: the stand arm D reads in 2020–2100)

* **Arm A** = arm D reading the ORIGINAL's stand through the same `--stand-dir` path (`arrays --copy-only` into
  `stand_orig`; legs not present there fall back to the original's anyway). **Arm B** = arm D reading the stand map's
  prediction (`stand_emul`).
* **Stand for run k** (k = 1..4): the stand map fitted with run k unseen (`--hold k`) AND the leg's climate model
  unseen (ADR 0331 §3). New fits needed for GFDL-ESM4 and MRI-ESM2-0, holds 1–3 (hold 4 exists). The end-of-2019
  stand stays the original's.
* **Legs:** the 13 climate-model legs of arm D (MPI ssp126/370/585, GFDL ×3, MRI ×3, IPSL ×3, UKESM ssp370).
  `ctl_obs` keeps the original's stand in both arms (the stand map has no constant-climate predictions) and is not
  scored for the verdict.
* **Venue:** free runs from the original's end-of-2019 state, held-out cells only (238 scored), all four runs, GPU as
  `DE_5seed`. Arm D has seen every climate model, so the only out-of-sample axis of the daily model is place; the
  stand map adds unseen-run and unseen-climate-model error.
* **Harness:** arm A must reproduce `DE_5seed`'s score table (every typical, worst-10 %, drift and total entry equal at
  the printed two decimals; GPU run-to-run arithmetic may differ in the last digits).
* **Noise:** A and B use the same five networks, so the ensemble-to-ensemble noise of ADR 0336 §6 does NOT apply to
  B ÷ A — the difference is caused by the stand alone. It does apply when B's level is compared with any other
  ensemble.

## 3. Pass (each of the 13 legs; GPP / ET / NPP / runoff; 30-yr windows 2021–2050 and 2071–2100)

1. **Increment:** B's typical-cell error ratio ≤ **1.3 ×** A's (as ADR 0331).
2. **Level:** GPP and ET typical ≤ **3 ×** a second run, both windows (ADR 0325, the bar for trained climate models —
   arm D has trained on all of them).
3. **Totals:** area totals within 5 %.
4. **Drift:** B's drift ≤ A's + 0.1.

**Expectations (from ADR 0331 §4–5, where B ÷ A was GPP 1.09–1.31, ET 1.16–1.36, NPP 1.02–1.30, runoff 0.96–1.40):**
arm D's own errors are 5–25 % smaller than the control ensemble's on the shared legs, the stand error is unchanged, so
B ÷ A is expected 1.1–1.45 for GPP and ET, 1.05–1.35 for NPP; criterion 1 fails on 3–7 of the 13 legs, mostly ET
early; criterion 2 holds for GPP on ≥ 10 legs and fails for ET early on 3–6 legs (arm D's ET early is already
2.3–3.0); totals hold everywhere; drift changes by < 0.1 on ≥ 11 legs. The legs of climate models the stand map
never saw in any of its training sets are not different in kind here — every leg's stand is from an unseen model.
**Falsifier (as ADR 0331):** GPP's B ÷ A > 1.5 on any leg ⇒ the stand error, not the daily model, dominates the full
emulator's carbon error, and the next work is on the stand map.

**What follows either way:** this is the error of the full learned emulator's daily fluxes (structure + stand +
daily model) on the panel, the number to quote for the coupled end-to-end model until a coupled run exists.

## 4. Result (2026-10-14; jobs 2483325–34; runs `PD_A`, `PD_B`; `DATA/f2/runs/relative_score_PD_ADR0337.md`)

Six new stand fits (GFDL and MRI, runs 1–3 unseen) and the arrays: every cell-year of the eight new legs replaced
(1 020 600 values per run and leg, none kept). **Harness exact:** arm A reproduces `DE_5seed`'s score table in all 56
free-run rows and every column.

Typical-cell error ÷ a second run's, 13 legs, median (range) — arm A (original's stand) → arm B (emulated stand):

| flux | early 2021–2050 | late 2071–2100 | B ÷ A, median / worst | drift A → B, median / max |
|---|---|---|---|---|
| GPP | 2.09 → 2.30 (2.01–2.64) | 1.80 → 2.17 (1.94–2.88) | 1.13 / 1.74 (IPSL ssp585 late) | 0.95 → 1.01 / 1.13 → 1.26 |
| ET | 2.55 → 3.14 (2.50–3.85) | 1.97 → 2.88 (2.11–3.59) | **1.35** / 1.66 (IPSL ssp585 late) | 0.85 → 0.95 / 0.98 → 1.06 |
| NPP | 3.36 → 3.78 (3.35–4.55) | 3.02 → 3.70 (3.33–4.30) | 1.15 / 1.46 (GFDL ssp370 late) | 0.94 → 1.03 / 1.17 → 1.16 |
| runoff | 4.51 → 5.15 (4.04–6.46) | 3.72 → 4.60 (3.87–7.65) | 1.20 / 1.57 (IPSL ssp585 late) | 0.83 → 0.90 / 1.02 → 1.13 |

Area totals, arm B: ≤ 2.5 % on every leg and flux (arm A ≤ 2.9 %).

**Verdict as pre-registered: FAIL.** (1) increment ≤ 1.3×: **0 of 13 legs** pass on all eight values (32 of 104 values
fail; ET late fails on 12 of 13 legs); (2) GPP and ET ≤ 3×: 5 of 13 legs pass (10 of 52 values fail, all of them ET:
early on 8 legs, late on 2; GPP stays ≤ 2.88 everywhere); (3) totals within 5 %: **13 of 13**; (4) drift ≤ A
+ 0.1: 3 of 13 legs (17 of 52 values fail — but B's drift is ≤ 1.06 for ET and runoff everywhere; the increase is
mostly from below 1 to about 1). **Falsifier FIRED** on two legs: GPP late B ÷ A = 1.58 (IPSL ssp370) and 1.74 (IPSL
ssp585). Against the expectations: GPP and NPP within the expected 1.1–1.45 / 1.05–1.35 at the median; ET's median
1.35 sits inside the range but its late window is worse (1.33–1.66) than expected; criterion 1 failed on 13 legs, not
3–7; criterion 2 failed on 8 legs (ET early), not 3–6; drift moved > 0.1 on 10 legs, not ≤ 2.

**Reading.** Arm D fed the emulated stand — the full learned emulator's daily fluxes — sits at GPP 2.0–2.9×, ET
2.1–3.9×, NPP 3.3–4.6× and runoff 3.9–7.7× a second run's typical error, totals within 2.5 %, the gap growing by at
most 1.26× over the century (GPP, IPSL ssp585 and UKESM). Arm D's own errors are lower than the control ensemble's,
so the same stand error is now a larger share: the stand adds a median 13–35 % and on the warmest IPSL leg it adds to late
GPP three quarters of the daily model's own error (1.55 → 2.69 × a second run). As the falsifier says, the next lever is the stand map, and ET is
where it bites. Which stand input carries the added error is not known yet — pre-registered in ADR 0338.

## 5. End-to-end timing of the whole learned emulator (2026-10-14; job 2483368; `scripts/bench_coupled_speed.py`)

One process, one core (CPU time / wall time 0.99), AMD EPYC 9554; the structure map, the stand map and arm D run year
by year over 81 years × 1 050 panel cells (GFDL ssp370, run m4), the stand each year's daily run reads being the stand
map's prediction of the year before:

| part | core-s per cell-year | share |
|---|---|---|
| learned daily model (365 days, five-network ensemble, closed bucket) | 6.38e-3 | 97.3 % |
| yearly climate statistics from the year's daily weather | 3.4e-5 | 0.5 % |
| 30-year window update + feature matrices | 1.7e-6 | 0.0 % |
| structure map (six boosted-tree models) | 5.3e-5 | 0.8 % |
| stand map (twelve boosted-tree models) | 8.7e-5 | 1.3 % |
| **end to end** | **6.55e-3** | |

Checks: the loop's annual GPP / ET / NPP / runoff reproduce the scored GPU run `PD_B` (run m4) to a median 1e-6 relative
per cell (totals ≤ 5e-7); 17 of 18 refitted boosted-tree models reproduce the saved predictions to ≤ 0.5 % of the
quantity's size, the 18th (cover of the boreal needle-leaved evergreen tree) to 1.3 % (pre-stated 1 %: LightGBM's
multithreaded training is not bit-reproducible; the stand map's output is not changed in substance). The end-to-end
number equals the earlier sum of separately timed parts (6.5e-3, ADR 0330): coupling the parts costs nothing measurable.
Stated simplifications: the boosted-tree models read the training table's climate columns (same function, same weather;
the online statistics are computed and paid for); the daily model reads the original's soil water capacity each year
(it changes 2019 → 2100 by a median 0.1–0.2 %, at most 4–6 % in one cell, so a fixed per-cell table would serve); wind
is synthetic in the climate statistics (the cost does not depend on values); no I/O.

**Against the original** (ADR 0084/0086: one cell, Hainich, one core, marginal rate): 0.267 core-s per cell-year at the
panel's 25 patches → **41× less**; ≈ 6.7 at the ~500 patches of publication runs → **≈ 1 000× less**. Against the
compute allowances of EXECUTION_PLAN §0 — a convention (10 % of a measured SpeedyWeather coupled cost), not an owner
requirement — ≤ 0.0135 core-s per cell-year at T31-class and ≤ 0.030 at T63-class: inside both, by 2.1× and 4.6×. The
ensemble is 97 % of the bill; each network costs ≈ 1.3e-3, so the noise/cost trade-off of ADR 0336 §6 is linear in
the number of members (ten members ≈ 1.3e-2, at the T31 allowance).
