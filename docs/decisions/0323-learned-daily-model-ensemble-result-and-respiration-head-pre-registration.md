# 0323 — Learned daily model: the five-seed ensemble fails narrowly, on NPP only; pre-registration of a respiration head (arm R)

* **Status:** Accepted (2026-10-10). §1–§2 score arm A2E as pre-registered in ADR 0322 §3; §3 is a pre-registration
  written before arm R was trained. The bar is ADR 0320 §5, unchanged.
* Runs: `/p/projects/open/Jamir/esm_land_emulator_data/f2/runs/A2_3x256{,_seed1..4}`, `A2E_5seed`; table:
  `python scripts/f2_compare.py`.

## 1. Result: arm A2E fails

| | L1 biome level | L2 typical held-out cell | L3 area totals | R1 biome response | S1 |
|---|---|---|---|---|---|
| A2E (mean of 5 seeds) | **fail** — NPP 3 of 5 (Sahel −5.8 %, Iberia +5.6 %) | **fail** — NPP on the unseen model 0.053 | **fail** — NPP on the unseen model −5.4 % | pass, 4 of 5 (Sahel powerless) | pass, 6.4e-3 core-s per cell-year |

**Every failure is NPP, and each is by less than one percentage point.** GPP and ET pass every statistic with
margin: worst typical-cell error 3.0 % (GPP) and 2.4 % (ET) over all five legs; every biome cell within 4.0 % (GPP)
and 3.6 % (ET); area totals within 2 %.

Single networks pass **1 of 5** seeds (seed 1). Seed 2 is poor on its own (NPP typical error 10.8 %, area total
−11 %; Sahel NPP −17 %) and pulls the mean down. Per ADR 0322 §3, no further seed or ensemble-size search follows.

Beside the bar, the ensemble is the best arm so far on everything the bar does not decide:
* **Warming response per cell** (GPP change 2071–2100 minus 2021–2050, held-out cells): correlation 0.96–0.98, slope
  0.91–0.99 on all four scenario legs, RMSE 33 / 33 / 58 / 92 gC m⁻² yr⁻¹ (ssp126 / ssp370 / ssp585 / unseen
  model) — 20–30 % lower than single networks, still 3.5–9× the original's member noise (~7–10).
* Top-metre water: typical daily error 7.9 mm (single networks ~11 mm).
* Deep store still biased: 1.8 m over 81 years vs 0.22 m in the original.

## 2. Reading

NPP is the bottleneck, and specifically NPP where it is a small difference of large terms (dry cells, the unseen
climate model). Averaging networks removes seed noise but not this bias. The network predicts NPP as a free signed
head, unconnected to its GPP head; but in the original, **daily respiration (GPP − NPP) is never negative** (0 of
31.0 M cell-days, one member/leg checked) and its annual share of GPP is stable within a cell (median within-cell sd
of the annual respiration fraction 0.029). A head that predicts respiration ≥ 0 and forms NPP = GPP − respiration ties
NPP to the well-predicted GPP and imposes a constraint the original obeys.

## 3. Pre-registration: arm R (respiration head)

* **One change from A2:** the NPP output becomes `npp = gpp − ra` with `ra = softplus(head) · sd(npp)` ≥ 0.
  Everything else (inputs, 3 × 256 network, 40 M samples, 10 passes, patience 2, loss on the same eight targets
  including NPP) is identical. Flag: `scripts/f2_train.py --npp-head ra`.
* **Seeds and scoring (the protocol ADR 0322 forces):** seeds 0–4 trained; **the arm is the five-seed ensemble**
  (mean of daily outputs, one bucket), scored against ADR 0320 §5. Each seed's own flags are reported; the single-seed
  pass rate is stated.
* **Comparison:** A2E is the reference (same protocol, direct NPP head). R is better only if it passes, or, failing
  both, if its worst NPP statistics are lower than A2E's on the same table.
* **If R fails,** record which statistic; the next candidates (only with a measured reason) are spatial regularisation
  (the limit is the 730 training cells, ADR 0322 §2) and the deep/runoff split.
