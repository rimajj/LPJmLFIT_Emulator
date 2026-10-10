# 0324 — Learned daily model, arm R (respiration head): fails on one statistic, typical-cell NPP under the unseen climate model

* **Status:** Accepted — result (2026-10-10). Scores arm R exactly as pre-registered in ADR 0323 §3 (five seeds,
  the ensemble is the arm). The bar is ADR 0320 §5, unchanged.
* Runs: `/p/projects/open/Jamir/esm_land_emulator_data/f2/runs/R_3x256_seed{0..4}`, `RE_5seed` (jobs 2460054–2460059).

## 1. Result

| arm | L1 biome level | L2 typical held-out cell | L3 area totals | R1 biome response | S1 |
|---|---|---|---|---|---|
| A2E (direct NPP head, ADR 0323) | fail (NPP 3 of 5) | fail (NPP 0.053) | fail (NPP −5.4 %) | pass | 6.4e-3 |
| **RE (respiration head)** | **pass** (4 of 5 for each flux) | **fail** — NPP on the unseen climate model **0.057** | **pass** (worst 2.3 %) | **pass** (4 of 5) | **pass**, 6.4e-3 |

RE's only failure: typical-cell NPP on `ukesm1-0-ll_ssp370` 0.057 (one-step already 0.051); the other legs are 0.035 /
0.040 / 0.049 / 0.048. Biome-cell NPP: Amazon −2.4 %, Sahel +2.0 %, **Iberia +7.3 %** (the one miss), Hainich −1.9 %,
Siberia −0.4 %. Response (R1): Amazon, Sahel (powerless), Iberia, Hainich inside the original's band; Siberia +57 vs
+27…+36 (overshoot, as in every arm). Single seeds pass all statistics in **1 of 5** (seed 3) — the same rate as the
direct head.

**Pre-registered comparison (ADR 0323 §3: better only if it passes, or if its worst NPP statistics are lower):**
mixed, so **not "better" by that rule**. Its worst NPP area total is much lower (2.3 % vs 5.4 %) and it passes the
biome cells (4 of 5 vs 3 of 5), but its worst typical-cell NPP is slightly higher (0.057 vs 0.053), and GPP / ET
typical errors are slightly higher (worst 3.6 % / 2.8 % vs 3.0 % / 2.4 %). It passes three of the four fidelity
statistics where A2E passes one.

Per-cell warming response (GPP, held-out cells): r 0.92–0.98, slope 0.88–0.98, RMSE 19 / 36 / 39 / 58 / 91 gC m⁻² yr⁻¹
(control / ssp126 / ssp370 / ssp585 / unseen model) — equal to A2E within noise. Top-metre water error 7.3 mm.
Deep store 2.1 m over 81 years (original 0.22 m): still biased.

## 2. Reading

What remains is **NPP under a climate model the network has never seen**, and it is a one-step error (0.051 one-step,
0.057 free). Neither capacity, more rows from the same cells, seed averaging nor the respiration constraint moved it
below 5 %. The remaining candidates from ADR 0322–0323: spatial regularisation (the limit is the 730 training cells),
and — a design question for the owner, not a method — whether a climate model held out entirely should be required
to meet the same ±5 % as the training climates, given the original's own run-to-run spread is ~1 %.
