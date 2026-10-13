# 0335 — Learned daily model: deployment candidate trained on all five climate models (pre-registration)

* **Status:** Pre-registered 2026-10-13, before training. Result §3 (not passed: early-window ET worse on three
  legs); follow-up arm D47 pre-registered §4; its first run was confounded (§5,
  ADR 0336).
* **Follows:** ADR 0334 §4 (arms L and V both null; the remaining respiration excess is generalisation to places, not
  a calendar input or the sample budget), STATE item 2 ("once arms L / V settle, train on all five climate models").
  Tool change: `scripts/f2_train.py --test-legs none` (no climate model held out; the default is unchanged).

## 1. The arm

**Arm D** (`D_3x256_seed0..4`, ensemble `DE_5seed`): exactly arm W (ADR 0333: 3 × 256 network, `--npp-head ra`,
humidity input dropped, 40 M samples, deep drainage 365 d, 5-member ensemble, calendar season input), with the two
legs held out so far added to training — **all 14 legs**: observed weather plus MPI-ESM1-2-HR ssp126/370/585,
GFDL-ESM4, MRI-ESM2-0 and IPSL-CM6A-LR ssp126/370/585, UKESM1-0-LL ssp370. The cell split is unchanged (730 train,
80 validation, 240 held-out cells in held-out blocks), so **the only out-of-sample check left is by cell (place)**:
every score below is on the 240 held-out cells, on climates the network has now seen. A number from this arm must
never be quoted as skill on an unseen climate model; ADR 0333's arms W/U remain the evidence for that.

## 2. Pre-registered numbers (free runs, held-out cells, ADR 0325 yardstick, `f2_relative_score.py WE_5seed DE_5seed`)

* **Primary (adopt as the deployment model):** on the two newly included legs (UKESM ssp370, MPI ssp585), the typical
  (30-yr p50) NPP error early (2021–50) is at most arm W's (3.16 / 3.37), and UKESM GPP / NPP drift ≤ 1.15 / 1.25
  (arm W's values, i.e. not worse).
* **Must not get worse:** on the 12 legs shared with arm W, the median over legs of the typical GPP, NPP and ET error
  (early and late) ≤ 1.05 × arm W's; no single leg's value > 1.15 × arm W's.
* **Failure reading:** if the primary fails, adding a climate model to training does not help the cells it does not
  cover ⇒ the deployment model is still arm D (more training data cannot be the wrong default), but say that the
  held-out-climate numbers of arm W are the honest error estimate for it.
* **Expectation:** primary passes with small gains (NPP error on the two legs 5–15 % lower, UKESM NPP drift
  ~1.10–1.20); shared legs unchanged within ±5 %; the southern-block respiration excess (ADR 0334) unchanged, since it
  is about places, not climates.

## 3. Result (2026-10-13; jobs 2480788–93 completed)

`f2_relative_score.py WE_5seed DE_5seed`, free runs, 238 held-out cells with GPP ≥ 50 (out of sample by place only).

| criterion | arm W | arm D | required | |
|---|---|---|---|---|
| NPP typical error early, UKESM ssp370 | 3.16 | 3.00 | ≤ 3.16 | ✓ |
| NPP typical error early, MPI ssp585 | 3.37 | 3.41 | ≤ 3.37 | ✗ (+1.2 %) |
| UKESM GPP / NPP drift | 1.15 / 1.25 | 1.13 / 1.17 | ≤ 1.15 / 1.25 | ✓ |
| 12 shared legs, median ratio D / W, GPP / NPP / ET (early + late) | — | 1.012 / 1.008 / 1.011 | ≤ 1.05 | ✓ |
| 12 shared legs, worst single ratio, GPP / NPP / ET | — | 1.14 / 1.11 / **1.28** | ≤ 1.15 | ✗ (ET) |

The ET failures are all in the EARLY window (2021–50) on MPI / GFDL legs: GFDL ssp585 2.16 → 2.76 (×1.28), MPI ssp126
2.15 → 2.55 (×1.19), GFDL ssp126 2.09 → 2.43 (×1.16); late-window ET is ≤ 1.11× everywhere. Runoff (the residual of
ET) follows: median ×1.06, worst ×1.21. Southern-block respiration excess unchanged, as expected (0.094 / 0.070 /
0.092 vs arm W 0.095 / 0.074 / 0.096). **Verdict: not passed as pre-registered** — the added climate model helps
where it was added (UKESM drift 1.25 → 1.17) and costs early-window ET on three other legs. Same shape as arm U
(ADR 0333 §6): one more leg on a fixed 40 M-sample budget worsened early-window fits.

## 4. Follow-up, pre-registered 2026-10-13 before training: arm D47 (samples per leg as in arm W)

* **Arm D47** (`D47_3x256_seed0..4`, ensemble `D47E_5seed`): arm D with `--nsamp 46666667` = 40 M × 14 / 12, i.e.
  the same rows per leg as arm W. One change against arm D.
* **Pass (D47 becomes the deployment model):** worst single-leg ET ratio vs arm W on the 12 shared legs ≤ 1.15
  (arm D 1.28), the medians of §2 still ≤ 1.05, and UKESM GPP / NPP drift ≤ 1.15 / 1.25.
* **Falsifier:** the three early-window ET ratios (GFDL ssp585, MPI ssp126, GFDL ssp126) each fall by less than a
  third of their excess over 1 ⇒ it is not the per-leg budget but a trade-off between climate models in one network.
  Then **arm D is still adopted as the deployment model** (coverage of every climate model is the stated priority,
  ADR 0333; its median cost is 1 %), and the early-window ET cost is quoted beside it.
* **Expectation:** null or partial. Arm V (ADR 0334) found 80 M rows did not help at 12 legs, so the budget is
  probably not the limit; arm U's early-window losses are the only evidence that it is.

## 5. Arm D47 result (2026-10-13; jobs 2480924–29) — CONFOUNDED, superseded by the repaired run (ADR 0336)

Raw: shared-leg medians vs arm W GPP / NPP / ET / runoff 1.073 / 1.090 / 1.054 / 1.223 (arm D 1.012 / 1.008 / 1.011 /
1.066); worst ET 1.25; UKESM drift 1.13 / 1.16. Worse than arm D almost everywhere with 17 % more samples — because
member seed2 stopped at epoch 7 (validation loss 0.0602 vs 0.053–0.055) under the old early-stopping default, which
ADR 0336 found in seven ensembles. **No verdict is drawn from this run**; the repaired ensemble `D47Ef_5seed` is
scored against §4 instead.

**Repaired D47 (ADR 0336 §4):** fails §4 (worst ET 1.28, medians GPP 1.07 / ET 1.09); falsifier holds on two of
three legs ⇒ **arm D is the deployment model**, with its early-window ET cost (×1.16–1.28 on three legs) quoted
beside it until the run-to-run noise measurement (ADR 0336 §5) says whether that cost is real.
