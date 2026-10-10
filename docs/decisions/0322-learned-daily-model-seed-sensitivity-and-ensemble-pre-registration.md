# 0322 — Learned daily water–carbon model: the single network passes or fails by its seed; pre-registration of a five-seed ensemble

* **Status:** Accepted (2026-10-10). §1–§2 record results; §3 is a pre-registration written before arm A2E was
  trained. The bar is ADR 0320 §5, unchanged.
* **Follows:** ADR 0321 (arms A, A2). Runs under `/p/projects/open/Jamir/esm_land_emulator_data/f2/runs/`; one-table
  comparison `scripts/f2_compare.py`.

## 1. Results since ADR 0321

| arm | change vs A2 | L1 | L2 | L3 | R1 | worst L2 GPP / ET / NPP | worst \|L3\| | response slope ssp585 / UKESM |
|---|---|---|---|---|---|---|---|---|
| A2 (seed 0) | — | pass | fail | pass | pass | .031 / .030 / **.057** | .048 | 0.89 / 0.84 |
| A2_3x256_seed1 | seed 1 | pass | pass | pass | pass | .034 / .026 / .049 | .034 | 1.04 / 0.98 |
| A3 | 4× samples, stopped by early stopping mid-schedule | fail | fail | pass | fail | .051 / .041 / .085 | .040 | 0.97 / 0.94 |
| A3b | 4× samples, full schedule | pass | pass | **fail** | pass | .035 / .027 / .042 | **.099** (NPP) | 0.85 / 0.80 |

S1 is 1.3 × 10⁻³ core-s per cell-year for all of them.

## 2. What it means

1. **The A2 configuration sits on the bar, and which side it lands on depends on the random seed.** Seed 1 passes
   every pre-registered statistic; seed 0 fails one (NPP under the unseen climate model, 5.7 % vs 5 %). Choosing the
   passing seed after seeing both would be selection on the test set, so **neither run is claimed as a pass.**
2. **More rows from the same cells do not help.** A3b's validation error is worse than A2's (0.062 vs 0.058) while its
   training error is lower (0.035 vs 0.040), and its NPP area totals are 8.6–9.9 % low on **every** leg, one-step as
   well as free-running. The training rows come from 730 cells; the limit is the number of distinct places, not of
   days. (A3, the first try, stopped after 6 of 10 passes because validation error rose during the high-learning-rate
   phase, which is 4× longer in steps with 4× the data; it is not a valid test of anything.)
3. **The NPP level of a single network wanders by several per cent between training runs** (A2 seed 0 vs seed 1 vs
   A3b), while GPP and ET are stable. Averaging independently trained networks is the standard remedy for exactly this
   variance, and it is cheap here (5 networks ≈ 6.5 × 10⁻³ core-s per cell-year, under the 0.01 bar).

## 3. Pre-registration: arm A2E (five-seed ensemble)

* **Members:** the A2 configuration (3 × 256, 40 M samples, 10 passes, early-stopping patience 2) trained with seeds
  0, 1, 2, 3, 4 — seeds 0 and 1 are the runs above, reused unchanged; seeds 2–4 are trained now.
* **Ensemble:** every day, each of the five networks predicts the fluxes from the **same** inputs (the ensemble's own
  stores); the eight outputs are averaged; the averaged fluxes drive the one closed bucket. Averaging bounded outputs
  keeps every bound of ADR 0320 §3.
* **Bar:** ADR 0320 §5, unchanged, on the ensemble's free run. S1 is measured on the ensemble (all five networks).
* **Reported beside it:** each member's own pass flags (seeds 2–4 are scored individually too), so the single-network
  pass rate over five seeds is on record.
* **If A2E fails,** the failing statistic is the finding; no further seed or ensemble-size search follows without a
  new pre-registration.
