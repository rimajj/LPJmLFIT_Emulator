# 0337 — Phase B with the deployment daily model (arm D): the daily model fed the emulated stand, pre-registered

* **Status:** pre-registered 2026-10-14, before its runs. Result appended below.
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
