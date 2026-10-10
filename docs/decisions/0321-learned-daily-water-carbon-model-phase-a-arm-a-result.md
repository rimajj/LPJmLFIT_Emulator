# 0321 — Learned daily water–carbon model, phase A: arms A and A2 against the pre-registered bar

* **Status:** Accepted — result (2026-10-10). Scores the arms exactly as pre-registered in ADR 0320 (commit d2e9acc2,
  pushed before any training). The bar was not changed. Arm A2 was added **after** arm A's score was seen; it
  changes one variable (network size) and is held to the same bar.
* Runs: `scripts/f2_train.py --tag A` (job 2459446) and `--tag A2_3x256 --hidden 256 --layers 3` (job 2459491), one
  GPU for training, ~15 min each end to end. Outputs: `/p/projects/open/Jamir/esm_land_emulator_data/f2/runs/<tag>/`
  (`summary.md`, `summary.json`, `annual.npz`, `model.pt`, `log.txt`).

## 1. Verdict

| | L1 biome level | L2 held-out-cell level | L3 area totals | R1 biome response | S1 cost | all |
|---|---|---|---|---|---|---|
| **A** (2 × 64) | pass | **fail** (NPP 0.050–0.079) | **fail** (NPP −5.0 % ssp585, −6.1 % UKESM) | **fail** (3 of 5, one powerless) | pass, 4.0e-4 | **fail** |
| **A2** (3 × 256) | pass | **fail** — only NPP on the unseen climate model, 0.057 | pass | pass (4 of 5, one powerless) | pass, 1.3e-3 | **fail** |

By ADR 0320 §3 the rollout-trained arm B is **not** run: its trigger (free-run ET error ≥ 2× one-step) never fires
(ratio 1.2–1.5 for A, ≤ 1.2 for A2), and the failing statistics fail one-step too. **The defect is in the daily step,
not in the stores drifting.**

## 2. Numbers (free run, held-out blocks; 238 held-out cells with GPP ≥ 50 gC m⁻² yr⁻¹)

L2, median absolute relative error of the 2021–2100 cell mean, legs ctl_obs / mpi126 / mpi370 / **mpi585 (held out)** /
**ukesm370 (unseen model)**; bar ≤ 0.05:

| | GPP | ET | NPP |
|---|---|---|---|
| A | .030 .033 .035 .035 .034 | .033 .028 .027 .024 .028 | .050 .051 .053 .052 **.079** |
| A2 | .031 .029 .027 .024 .030 | .030 .025 .026 .023 .026 | .043 .043 .046 .047 **.057** |
| original's own member spread | .009–.018 | .009–.022 | .010–.020 |
| climatology null (scenario legs) | .040–.153 | .029–.138 | .042–.125 |

L3 area totals (A2): GPP −2.1 … +0.5 %, ET −1.8 … +0.1 %, NPP −4.8 … −1.0 % (all within ±5 %).

L1 (biome cells, mpi370), A2: GPP +0.1 / +3.1 / +4.6 / −0.2 / +0.1 % (Amazon, Sahel, Iberia, Hainich, Siberia); ET
−0.2 / +1.5 / +4.9 / +1.5 / +1.0 %; NPP −1.5 / −2.2 / **+6.5** / −2.0 / +0.7 %. Arm A missed the Sahel by +13 to
+19 %.

R1 (GPP change 2071–2100 minus 2021–2050, mpi370), A2 vs the original's four-member band: Amazon −234 (−248…−193) in;
Sahel +1 (−20…+66) in, **band contains 0, no power**; Iberia +60 (+4…+62) in, at the edge; Hainich +75 (+66…+117) in;
Siberia +53 (+27…+36) **out — overshoot**. Arm A had Iberia at −30 (wrong sign).

## 3. Findings beyond the bar

1. **The per-cell warming response is captured; the aggregate response ratio is not a usable statistic here.**
   Over held-out cells, emulator vs original GPP change per cell (2071–2100 minus 2021–2050):
   correlation 0.92–0.97 and slope 0.84–0.99 for A2 (A: 0.91–0.95, slope 0.77–0.87 — it under-responds by ~20 %).
   The area-summed ratio reported in `summary.json` (A2: 0.01 to 3.19 by leg) is meaningless: the original's net
   aggregate change is only 5–12 % of its summed absolute per-cell change (tropical losses cancel boreal gains), so
   tiny errors swing the ratio. ⚠ A draft of this record read that ratio as "the model under-responds even
   one-step"; that was wrong and is withdrawn. Any later response statistic must be per cell (correlation, slope,
   RMSE) or per sign class, never a ratio of net sums.
2. **The level error is ~2–4× the original's own run-to-run difference.** Per-cell response RMSE is 42–137 gC m⁻² yr⁻¹
   against a member noise of ~10. By ADR 0318's yardstick (≤ 1.2× a second run) this model fails where it passes ADR
   0320's ±5 %. The ±5 % bar of EXECUTION_PLAN §6 is the looser of the two; say so wherever these numbers are quoted.
3. **The deep exchange is biased.** The original's top-metre-to-deep store changes by a median 0.22 m over 81 years
   (one member, mpi370); the emulator's by 2.7 m (A) and 1.8 m (A2). Total ET is right, so the excess goes through
   runoff. Runoff is not in the bar but is a coupling variable; fix before phase B.
4. The stores are stable: typical daily error of top-metre water ~11 mm in every free run; overflow 5–13 mm/yr.
5. NPP is the hardest flux (largest errors in the most productive cells, where it is a small difference of large
   terms). A2 overfits: training loss 0.040 vs validation 0.058 (A: 0.069 / 0.077).
6. Cost: A2 is 1.3 × 10⁻³ core-s per cell-year (one CPU core, batch over 1 050 cells, network + running windows +
   bucket). For scale only: the original costs 0.267 core-s per cell-year at 25 patches (ADR 0084) for everything it
   does; the stand still comes from the original here, so this is not an emulator-vs-original speed-up.

## 4. Next (one variable at a time)

A3 = A2 with 4× the training samples (160 M instead of 40 M; job 2459518), because A2 overfits and fails only on NPP
under the unseen model. Then, only with a measured reason: the deep/runoff split; the boreal response overshoot. The
bar of ADR 0320 applies unchanged.
