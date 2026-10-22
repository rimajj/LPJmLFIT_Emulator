# 0366 — The per-tree mortality model fed the emulator's OWN yearly NPP (pre-registration)

* **Status:** pre-registered 2026-10-22, before any emulator run or fit of this record. **Result (§5): not adopted — die-off capture 0.43 (bar 0.5; without NPP 0.36), 30-year death rate 1.52 (bar 1.2). The emulated NPP carries part of the signal: +0.07 on all cells, +0.10 on the cells the daily networks never saw; outright-kill capture 0.45 → 0.61.**
* **Owner instruction (2026-10-22):** "(m1) Give the mortality model the emulator's own NPP … do both!"
* **Follows:** ADR 0364 §6 — the per-tree model `BC` captures 0.36 of the die-off jump (bar 0.5) and misses the
  30-year death rate (1.51, bar 1.2); with the run's OWN tree-NPP statistics (`BCN`, not deployable) capture is 0.74.
  The binding lever is the year's carbon signal; the deployable version of it is the emulator's own daily NPP.
* **Code:** `scripts/build_emulator_forcing.py` (weather arrays), `scripts/run_emulator_npp.py` (setups m5/m6 +
  emulator runs + the emulated-NPP table), `scripts/explore_panel_treemort.py --arm BCE` (fit / predict / score).

## 1. What is new: arm `BCE`

`BC` (ADR 0364 §3, unchanged: same per-tree inputs, same cell inputs, same four sub-models, same LightGBM settings)
plus 12 cell inputs from the EMULATOR's yearly sums of its daily fluxes: for v ∈ {stand NPP, stand GPP} this year's
value (`n0`), its ratio to the trailing 30-year mean (`nr0`), its z-score against the 30 years before (`nz0`, ≥ 15
years, 0 where constant) and the same three of last year (`n1`, `nr1`, `nz1`) — exactly the construction of ADR 0363
§8's `npp_anomaly`, applied to the emulator's stand values instead of the original's per-tree values.

**History for the anomalies (2000–2019).** The original's anomalies were taken against 2000–2019 in front of the leg.
The emulator has no 2000–2019 run, so it gets one from its own parts: the daily model alone on the OBSERVED weather of
2000–2019 (1999 as the windows' warm-up), with the run's 2019 stand (`stand0`) frozen and the setup's top-metre
capacity. Then the standard 2020–2100 run starts fresh from the setup, so the 2020–2100 values are identical to
`run_emulator.py`'s (gate G2). Everything it needs is in the setup — deployable.

## 2. Which emulator produces the NPP (leak control)

* **Training legs** (runs m1 m2 m3 m5 m6 × all 30 scenario legs): the deployment release `v2`, cap fixed (deployment
  mode). One set shared by every fold. Disclosed leak: `v2`'s structure and stand maps were trained on every leg and
  every run including the held-out model's and run m4; it reaches the mortality fit only through `v2`'s fitted maps
  on the OTHER legs.
* **Test legs** (run m4 × the held-out model's three legs): the FOLD release of that model (structure and stand maps
  trained without it): `fold_gfdl-esm4_v3` exists; `fold_<g>_v3` for ipsl-cm6a-lr, mpi-esm1-2-hr, mri-esm2-0,
  ukesm1-0-ll are built now with the same command (`--hold-gcm <g> --departure dep`).
* **The daily networks are NOT held out by climate model** (release `D_3x256_seed*`: trained on runs m1–m4, 14 legs of
  the first five models, 810 of the 1 050 cells). So on the test legs the emulated NPP is in-sample for the daily model
  on 810 cells. Every score is therefore also reported on the **240 cells the daily networks never saw** (`f2`
  `cells.parquet` `heldout`); that variant is the clean one. Training a fold of the daily networks per model is out of
  scope (GPU days).

## 3. Inputs that have to be made (owner's list)

* **Weather arrays** for the 17 legs without them (`ukesm1-0-ll_ssp126/585`, the five newer climate models × three
  scenarios): `(1050, 82·365, 5)` float32, 2019 observed + 2020–2100 from the leg's `.clm` files, written to
  `f2/forc_leg/<leg>.npy`. Gate G1: the same code re-derives two existing legs (`gfdl-esm4_ssp370`,
  `ukesm1-0-ll_ssp370`) bit for bit equal to the f2 arrays the daily model was trained on.
* **Setups for runs m5 and m6** (`v2` has m1–m4). Copied from `v2`'s `setup_m1` (anchors, climate, observed warm-up
  are the same for every run — verified, bit-identical m1 vs m2) with the run's own `s0/*` and `memoff/*` from the
  same tables `write_setups` reads, and the run's own 2019 leaf area and vegetation carbon. **Substituted** (m5/m6 have
  no daily, `whc_nat` or `fpc_stand` output): top-metre capacity, Jan-1 soil water and snow = the cell's mean over
  m1–m4; the 2019 cover of the ten plant types (`stand0` columns 3–12) = the mean over m1–m4. These affect only the
  first emulated year's daily inputs (the stand map replaces the stand after year 1; the stores forget within months).
  Gate G3: the same procedure applied to run m1 (from m2's file) reproduces `v2/setup_m1.npz` exactly.
* **Runs:** 150 training run-legs + 15 test run-legs, one core each on `priority` (64 at a time), ~14 core-min each
  (81 years + the 20-year history) ⇒ ~40 core-hours, ~45 min wall. Gate G2: the runner on (`v2`, m1,
  `ukesm1-0-ll_ssp370`, cap fixed) reproduces `v2/runs/ukesm1-0-ll_ssp370_m1_capfixed.npz` exactly.

## 4. Evaluation, bars, reading (written before any fit)

* E1 (the original's own trees) and E2 (the emulator's virtual trees, deployable) and every score exactly as ADR 0364
  §4–5, 15 held-out cases (5 models × 3 scenarios), dense cells; plus the same table restricted to the 240 cells the
  daily networks never saw.
* Diagnostic: per test leg, correlation of the emulated NPP z-score `nz0` with the original's tree-NPP z-score (ADR
  0363 §8) over dense cell-years, and over ADR 0350's shared die-off events the mean of each.
* **Bars:** ADR 0364 §5 unchanged (yearly ≤ 1.5, 30-year ≤ 1.2, totals ±5 % in ≥ 12/15, die-off capture ≥ 0.5,
  calibration ±10 %).
* **Adoption:** `BCE` E2 passes every bar ⇒ it becomes the emulator's mortality output (new ADR for the release).
  It fails a bar but beats `BMW3` on die-off capture by ≥ 0.1 with no other score worse by > 10 % ⇒ reported as
  better than the map; owner decides.
* **Reading:** E2 capture − `BC` E2 capture (0.36): ≥ 0.10 ⇒ the emulated NPP carries the signal, the route is
  worth improving NPP for; < 0.05 ⇒ the emulated NPP does not carry the die-off signal and the route is closed at
  the current daily model; between ⇒ small, reported as such. If the clean-cell variant gains < half of the all-cell
  gain, the gain is the in-sample daily model and is not counted.
* **Expected:** E2 capture 0.40–0.50 (between `BC` 0.36 and the bound 0.74; the emulated NPP is a stand-level sum
  and its typical yearly error is ~3.9× a second run's); 30-year rate unchanged (1.4–1.5); the bars are not expected
  to pass.

## 5. Results (2026-10-22; forcing 2670984, setups 2671014, runs 2671019 + 2671197, table 2671198, fits 2671199–207,
predictions 2671200–208, scores 2671209/10 → `xpanel/eval/treemort/score_treemort{,_clean}.csv`)

**Gates.** G1: the weather arrays of two existing legs re-derived bit for bit. G3: run m1's setup rebuilt from m2's file
+ m1's own fields equals `v2/setup_m1.npz` in all 67 fields (first attempt failed on `memoff/*`: the deployment release
measures the run offset against the mean of ALL six runs, not the five training runs; fixed). G2: the runner reproduces
`v2`'s own run bit for bit (checked twice). The four fold releases built with every gate passed. 150 + 15 run-legs,
~775 core-s each (81 years + the 20-year history) ⇒ 35.5 core-hours. Emulated NPP over 1 050 cells: history 2000–2019
484 gC/m²/yr, 2020–2100 459–471 (fold releases) / 462 (v2). Training rows of `BCE` = `BC`'s exactly (11 074 323 trees
for the GFDL-ESM4 fold), so the only difference between the two arms is the 12 emulated-NPP inputs.

All ratios to the pooled second runs, dense cells, 15 held-out cases (E2 = virtual trees, deployable):

| arm | yearly death rate (≤ 1.5) | 30-yr death rate (≤ 1.2) | total deaths ±5 % (≥ 12/15) | die-off capture death rate (≥ 0.5) | capture hard-kill rate | hard-kill calibration E1 (±10 %) |
|---|---|---|---|---|---|---|
| `BC` E2 (ADR 0364) | 0.97 | 1.51 | 15 | 0.36 | 0.45 | 0.82 (0 of 15) |
| **`BCE` E1** | 0.95 | 1.39 | 15 | 0.44 | 0.64 | 0.87 (1 of 15) |
| **`BCE` E2 (deployable)** | **0.97 ✓** | **1.52 ✗** | **15 ✓** | **0.43 ✗** | 0.61 | — |
| `BCN` E2 (bound, ADR 0364) | 0.93 | 1.48 | 15 | 0.74 | 1.16 | 0.95 (13 of 15) |
| `BMW3` (cell map) | 1.01 | 1.34 | 14 | 0.28 | 0.27 | — |

**Clean cells** (the 240 cells the daily networks never saw; 943 die-off events): `BC` E2 capture 0.44, **`BCE` E2 0.54**
(hard-kill rate 0.57 → 0.78), `BMW3` 0.29; 30-year death rate `BCE` E2 1.68, `BC` E2 1.59, `BMW3` 1.48; hard-kill
calibration `BCE` E1 0.91 (8 of 15 within 10 %).

**Diagnostic.** The emulated stand-NPP z-score correlates 0.60–0.66 with the original's tree-NPP z-score over dense
cell-years (every test leg; 0.60–0.65 on the clean cells); in the die-off years the emulated z averages −1.3 to −2.6.

**Reading (§4, applied as written):**
* `BCE` E2 fails the 30-year death rate (1.52), the die-off capture (0.43) and the hard-kill calibration (0.87) ⇒ **not
  adopted**. The "better than the map" clause: capture +0.15 over `BMW3` (≥ 0.1 ✓) but the 30-year rate is 13 % worse
  (1.52 vs 1.34, allowed 10 %) ⇒ fails, as `BC` did. The release keeps no mortality output.
* Gain over `BC`: +0.067 on all cells ⇒ the "small, reported as such" band (0.05–0.10). On the clean cells +0.103,
  i.e. more than half the all-cell gain ⇒ the gain is not the in-sample daily model and counts.
* Expectations: capture 0.40–0.50 ✓ (0.43); 30-year rate unchanged ✓ (1.51 → 1.52).
* The emulated NPP closes about a fifth of the gap to the bound on the death rate ((0.43 − 0.36)/(0.74 − 0.36) = 0.18)
  and more on the outright kills ((0.61 − 0.45)/(1.16 − 0.45) = 0.23). What separates it from the bound is the NPP
  itself: a stand sum from a daily model whose 30-year NPP error is ~3.9× a second run's, against the original's own
  per-tree NPP, and their yearly anomalies agree at r ≈ 0.63. Better emulated NPP is therefore the lever for this route,
  and no input change fixes the 30-year death-rate level, which no arm reaches (best 1.48, the bound).
