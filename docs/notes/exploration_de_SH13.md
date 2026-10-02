# SH13 — shared boosted patch-level heads (Germany emulator, line X) — DEV-A

Script `scripts/explore_de_sh_patchheads.py` (stages prep / fit / gates / submit; `SH13_SMOKE=1` for a 91-cell
5-year end-to-end run), helper `scripts/explore_de_sh_patchheads_apitest.py`. Outputs
`/p/tmp/jamirp/X_de/shared/patchheads/{_features,DEV-A}/`, gates `DEV-A/_gates.json`, report
`/p/tmp/jamirp/X_de/_reports/r2_SH13.json`. Only the clean 1985-2044 truth is used; CO2, wind, lon/lat and cell ids
are never inputs.

## What the heads are
Each head = a booster on patch/cell **state** (B0) plus a booster on **climate of year y+1** fitted on B0's residual
(B1, piecewise-linear leaves); score = base + B0 + kappa·B1, kappa picked on the validation fold
(fire 1.25, recruits 1.0; kappa = 0 is the climate-blind head).

* **Fire fraction f** (patch, per step). The original model kills each non-hard survivor of the hazard draw with
  probability (1 − resist[Type])·f, f ≥ 0.001. Target = observed excess deaths E (non-hard deaths − summed non-hard
  hazards), E[E] = f·D. E is negative in ~85 % of patch-years (hazard-draw noise ~0.35 per patch vs a signal of
  ~0.01), so clipping is wrong (it keeps only positive noise). Shipped fit: Poisson on the **excess over the floor**,
  label E/D − 0.001 unclipped, weight D, f = 0.001 + e^score; every leaf reproduces its own total. A first version
  using the exact likelihood of that link matched totals only weighted, and over-predicted Germany-wide fire excess
  by 9-10 % (kept as `_gates_v1_floorweighted_fire.json`). E also contains death channels the rule library lacks
  (negative-pool kill, bioclimatic survival kill, sapling leaf-carbon kill), so f = "fire + unexplained non-hazard
  deaths" — what a stepper applying the rule hazards then f needs.
* **Recruit count** per patch (Poisson mean, negative-binomial dispersion per predicted-mean decile).
* **Entry state**: quantile heads q05..q95 of Height − 5 m and ln Age, and an empirical joint table of
  (Height, Age, counter c, growth efficiency G, censor code) by Type × tercile of y+1 annual mean temperature.

## Split and basis
Train: MPI-ESM1-2-HR seed 1, Historical 1985-2013 + ssp126 + ssp370 2014-2043, dev cells of folds 1-3
(16.1 M patch-years incl. validation); early stopping on fold 4; no refit. Scored: fold 5 (185 dev cells,
4.1 M patch-years) of the training members; held-out climate model ACCESS-CM2 seed 1 (Historical, ssp126/245/370);
MPI ssp245 seeds 1 and 2 and MPI Historical seed 2 — each on fold 5 and on all 907 dev cells.

## Gates (fold 5 of the training members unless stated)
| gate | result |
|---|---|
| 1 fire, yearly Germany sum of predicted vs observed excess, r ≥ 0.9 | **0.821 FAIL** — but the best any predictor can reach against that noisy observation is **0.893** (hazard-draw noise), so the gate is infeasible on this basis. All dev cells (in-sample): 0.929 (ceiling 0.977). Held-out GCM pooled, all dev: 0.899. |
| 1b independent: vs the run's own Germany-wide fire-carbon output (`globalflux`, all ~9067 cells) | predicted mean f **0.919**; the observed excess itself only 0.808; constant-f null −0.09 |
| 1c totals: Σ predicted f·D / Σ E | 1.028 (fold 5), 1.034 in-sample, 1.026 held-out pooled; yearly ratio 10-90 % range 0.80-1.44 |
| 2 release after ≥ 50 % one-year cover loss (32 154 event patch-years) | model ×3.33 vs truth ×3.28 (+1.7 %) **PASS**; every test member within 5 %. Judge band 3.6-4.1: missed by the truth too. |
| 3 cell-year recruit totals from NB draws never 0 | **PASS** (16 465 cell-years, min 17; every test member min ≥ 12) |
| 4 per-decile calibration (both counts) | **PASS** on fold 5; fails on some held-out-GCM members (recruits under-predicted 10-17 % in the five lowest deciles for ACCESS ssp370; fire top decile +13 %) |

Nulls (derived beforehand, then measured): fire constant f — yearly r 0.24 (expected < 0.3), loss 0.0073 vs model
0.0062. Recruits — Poisson deviance model 0.613; constant 0.860; per-cell mean using the scored cell's own truth
0.856; last-year persistence 1.67 (MSE 0.533 vs model 0.240, ≈2× as expected); release ratio of the per-cell-mean
null ×0.86 and persistence ×1.00 (both fail, as expected). Entry: mean pinball loss model vs per-Type null
0.0166 vs 0.0206 (height), 0.094 vs 0.127 (ln age); q05-q95 coverage 0.90.

**Climate adds little.** Climate-blind vs full: recruit deviance 0.618 vs 0.613 and release ×3.33 either way;
fire yearly r 0.36 vs 0.82 (the year-to-year fire signal is climate). The 2015-2044 scenario contrast is weak in
the forcing, so no scenario response can be read off these heads.

## Rollout audit
Every input is regenerable from the engine state (`FEATURE_AUDIT` in `meta.json`); `patch_frame_from_state`
rebuilds them from a `RosterState` and matched the table-built features to float32 precision (20 cells, 1985).
The stepper must (i) decide this step's deaths and hidden trees before calling the recruit head (fpc of survivors
and this step's cover loss are inputs), and (ii) keep the agb of the trees it flagged dead in `aux_patch` (fuel
input of the fire head; at the start year read SH4's `agb_dead_y`).

## API
`import explore_de_sh_patchheads as ph; H = ph.load_heads("DEV-A")`; `X = ph.patch_frame_from_state(state,
clim_y1, step_isdead, step_hidden, agb_dead_y)`; `H.fire_f(X)`, `H.recruit_mean(X)`, `H.recruit_draw(mu, u)`,
`H.entry_quantiles(Xr)`, `H.entry_draw(Xr, u_h, u_a)`, `H.clim_tercile(tmean_ann_y1)`,
`H.entry_sample(type, tercile, u)`; every method takes `kappa=` (0 = climate-blind).
