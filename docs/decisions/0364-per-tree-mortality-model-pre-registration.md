# 0364 — A per-tree mortality model: learn each tree's leaf carbon against its sapling threshold and its chance hazard (pre-registration)

* **Status:** pre-registered 2026-10-22, before any fit of this record (the training tables were being built). **Result (§6): not adopted — die-off capture 0.36 (bar 0.5), 30-year death rate 1.51 (bar 1.2); the run's own NPP lifts capture to 0.74.**
* **Owner instruction (2026-10-22):** "do a-c, all of it" — (b) = the cohort / per-tree leaf-carbon model that ADR
  0363 §6 (`BC`) and §10 named as the next mortality step.
* **Follows:** ADR 0357 (die-offs are the leaf-carbon hard kill), ADR 0363 §6–§10 (cell-level death-rate maps:
  `BMW` passes the yearly rate and the totals, misses the 30-year rate 1.32 and die-off capture 0.28; the original's
  own NPP (`BMN`) lifts capture to 0.59). R00234 (review corpus): learn the continuous quantity the model thresholds
  on and apply the threshold, rather than classifying the event.
* **Code:** `scripts/build_panel_tree_pairs.py` (tables), `scripts/explore_panel_treemort.py` (fit + score, new).

## 1. Two corrections found while designing this (verified 2026-10-22)

1. **The emitted `mort` is the death probability AFTER the hard kills: it is set to 1 when a tree's leaf carbon is
   below a sapling's or its bad-year counter reached 5** (`mortality_tree_ind.c:131-139`, `tree->mort_prob = mort`,
   written by `fwriteoutput_ind.c:156`). The draw `erand48 < mort` follows; trees can still die afterwards by
   `isneg_tree` and by fire (`fire_tree_ind`, after the mortality call, ADR 0356 §7). Consequences for ADR 0363:
   * `yearly2.exp_dead` (sum of `mort`) and the "chance-death rate" built from it INCLUDE the hard kills.
   * the "excess deaths" (n_dead − sum of `mort`, a third of all deaths) are **fire, `isneg_tree` and luck — not the
     hard kills.** ADR 0363 §1.3 ("a third of all deaths are excess deaths (hard kills …)") is wrong, and §8's
     decision rule read "excess-death capture" as the hard-kill channel. §10's conclusion ("a stand-level carbon
     signal is not enough for the hard kills ⇒ build `BC`") therefore rests on a mislabelled quantity: the hard-kill
     channel was never scored on its own. Building `BC` is still the owner's instruction, and §10's other number
     stands (the original's own NPP doubles die-off capture of the death rate, 0.28 → 0.59).
   * New tables (`yearly3/`) count the hard kills directly (`n_hard`: died, `mort` ≥ 1, chance hazards < 1).
2. **A tree's identity is (Cell, Patch, Type, ID), not (Cell, Patch, ID)** (ADR 0125 was measured on five cells): IDs
   are counted per plant type, so two trees of different types in one patch can share an ID (found at Hainich, cell
   42490 patch 4, 2034–2035). The builder keys on the type too and asserts uniqueness.

## 2. Data (`build_panel_tree_pairs.py`, every run m1–m6 × every leg)

At-risk trees of year y: types 0–6, alive and ≥ 5 m tall at the end of y−1 (the emulator's population, what its
virtual trees of y−1 stand for), with a row in y. Per (Cell, Year): `n_risk`, `n_dead`, `n_hard`, `sum_hz`, `sum_mort`.
Rates: **death rate** n_dead / n_risk; **hard-kill rate** n_hard / n_risk; **hazard rate** sum over the not
hard-killed trees of hz / n_risk, hz = min(1, the four hazards); **other rate** (n_dead − sum_mort) / n_risk (fire,
`isneg`, luck). A fixed 0.5 % sample of at-risk trees (hash of the identity) with the tree's y−1 state and y outcome.
Gates: the identity holds (every matched tree is exactly one year older — 1.0000 on the smoke leg; 0 ambiguous
tree-years after adding SLA); trees vanishing without a row reported. ~~hard-killed trees with r < 1 ≥ 0.94 (ADR
0357)~~ — struck before any fit, see §2a.

### 2a. Amendment before any fit (2026-10-22): which hard kill removes trees ≥ 5 m

The smoke leg (run m1, gfdl-esm4 ssp126) gave 32 % of hard-killed trees ≥ 5 m below r = 1, against ADR 0357's
94.5–97.7 %. Measured by height on that leg (2021–2100, every cell): trees < 5 m — 3.6 M hard kills, 98 % with r < 1
(median age 1: saplings); 5–10 m — 95 k, 35 %; ≥ 10 m — 16 k, 13 % (median r 136). So for trees ≥ 5 m in ordinary
years most hard kills are the five-bad-years counter, not the leaf threshold. **ADR 0357 mixed all heights; its
verdict was carried by the saplings.** In the die-off years of the shared events (run m4, three legs, trees ≥ 5 m)
the leaf threshold does dominate: 14 153 hard kills, 92 % with r < 1 (median 0.51), plus 10 274 deaths whose
chance hazards sum to ≥ 1 (vs 60 493 / 66 % and 13 613 in other years at the same cells). Consequences for §3,
fixed now: (i) a **counter-kill model** is added — per tree the probability of a hard kill with r ≥ 1 (binary
LightGBM, log loss, same inputs); the hard-kill probability becomes `1 − (1 − P_h)(1 − P_c)`; (ii) the gate on r < 1
becomes a reported number; (iii) the hazard model (target hz = min(1, the four hazards)) also carries the
"hazards ≥ 1" deaths of die-off years.

## 3. The per-tree model `BC`

Inputs per tree (exactly what a virtual tree of y−1 carries): Type, SLA, wood density, `D95max`, `minwscal`, height,
biomass, age at y−1. Inputs per cell and year: lat, lon, soil code; the 25 trailing 30-year climate means; this and
last year's weather z-scores (50, the release departure model's); the daily-bucket stress statistics (ADR 0355) —
i.e. exactly `BMW`'s cell inputs. LightGBM as everywhere (`explore_panel_a7.PARAMS`, 400 rounds).

* **Leaf-carbon model:** μ(x) = E[ln r_y]; σ(x) from a second model of |ln r_y − μ| (Gaussian: σ = √(π/2)·E|res|,
  fitted on the held-out half of the training trees, split by cell). Hard-kill probability `P_h = Φ(−μ/σ)` — the
  original's own rule (r < 1) applied to the learned quantity.
* **Hazard model:** E[hz_y] (target clipped to [0, 1]).
* **Other deaths:** a cell-level map of the other rate (`BMW`'s inputs) — not per tree.
* **Counter-kill model (§2a):** P_c = P(hard kill and r ≥ 1), binary.
* Per cell: death rate = mean over the at-risk trees of [P_k + (1 − P_k)·hz] + other rate, P_k = 1 − (1 − P_h)(1 − P_c).
* **`BCN` (bound, not deployable):** `BC` + the run's own yearly tree-NPP statistics of ADR 0363 §8 as cell inputs.

Training: runs m1, m2, m3, m5, m6 × the 27 legs of the nine climate models other than the held-out one × 2021–2100;
test: run m4 (truth) and m5 (harness) on the held-out model's three legs; held-out model = each of the first five
(15 cases), as ADR 0363.

**Reference `BMW3`:** ADR 0363's cell-level map refitted on the `yearly3` rates (same definitions as `BC`), arms
`BM3` (climate only), `BMW3` (+ weather), `BMN3` (+ NPP, bound).

## 4. Evaluation

* **E1 — the original's own trees** (run m4's at-risk trees of every held-out case, all of them): isolates the
  per-tree model.
* **E2 — the emulator's virtual trees of y−1** (ADR 0363 `AQ` quantiles, donor = the run's 2019 roster, no-repeat
  draw of ADR 0363 §12, tree count from the release): what would ship.
* Scores as ADR 0363 §7, ratio to the pooled second runs m1–m3 against m4, dense cells (anchor ≥ 5 trees per patch):
  yearly death rate, 30-year-mean death rate 2071–2100, area-weighted total deaths per year; **die-off capture** =
  Σ jump of the emulated rate / Σ jump of the truth over ADR 0350's shared tree-count events (jump = event year − the
  mean of the 5 years before), for the death rate and the hard-kill rate.
* **Calibration (E1):** Σ P_h over the test trees / observed hard kills, and Σ hz / observed sum of hz, per case.

## 5. Bars and reading (written before any fit)

* **Bars (dense, as ADR 0363 §7):** yearly death rate typical ≤ 1.5; 30-year death rate typical ≤ 1.2; total deaths
  within 5 % in ≥ 12 of 15 cases; die-off capture of the death rate ≥ 0.5. Calibration within ±10 % (E1).
* **Adoption:** `BC` on E2 passes every bar ⇒ it becomes the emulator's mortality output (new ADR for the release).
  If it fails a bar but beats `BMW3` on die-off capture by ≥ 0.1 with no other score worse by > 10 %, it is reported
  as better-than-the-map and the owner decides. `BCN` is a bound and never ships.
* **Expected:** E1 `BC` capture 0.35–0.55, `BCN` 0.6–0.8; E2 ~0.05–0.1 below E1; 30-year rate 1.1–1.3; `BMW3`
  capture of the hard-kill rate ≤ 0.3. If E1 `BCN` stays below 0.5, the per-tree structure is not what is missing
  and the next lever is the daily water–carbon model's own NPP as input (ADR 0363 §8, c3).

## 6. Results (2026-10-22; tables job 2670238/39, fits 2670267–79, predictions 2670364–73, score 2670403 →
`xpanel/eval/treemort/score_treemort.csv`)

Data: 186 run-legs, 14.8 M sampled at-risk trees (11.1 M per fold); identity gate 1.0000 everywhere, 0 ambiguous
tree-years after adding SLA, ≤ 0.08 % vanishing. Per year 4.4–5.0 % of at-risk trees die; hard kills are 14–21 % of
the deaths (0.78 % of trees), and 33 % of those have r < 1 (the rest: the counter, §2a). Harness (run m5 as the
emulator) 0.98–1.02 everywhere.

All ratios to the pooled second runs, dense cells, 15 held-out cases:

| arm | yearly death rate (≤ 1.5) | 30-yr death rate (≤ 1.2) | total deaths ±5 % (≥ 12/15) | die-off capture death rate (≥ 0.5) | capture hard-kill rate | hard-kill calibration E1 (±10 %) |
|---|---|---|---|---|---|---|
| `BC` E1 (original's trees) | 0.96 | 1.37 | 15 | 0.37 | 0.46 | 0.82 (0 of 15) |
| **`BC` E2 (virtual trees, deployable)** | **0.97 ✓** | **1.51 ✗** | **15 ✓** | **0.36 ✗** | 0.45 | — |
| `BCN` E1 (bound) | 0.91 | 1.25 | 15 | 0.74 | 1.17 | 0.95 (13 of 15) |
| `BCN` E2 (bound) | 0.93 | 1.48 | 15 | 0.74 | 1.16 | — |
| `BM3` (cell map, climate) | 1.10 | 1.39 | 13 | 0.00 | 0.00 | — |
| `BMW3` (cell map, + weather) | 1.01 | 1.34 | 14 | 0.28 | 0.27 | — |
| `BMN3` (cell map, + NPP, bound) | 0.94 | 1.25 | 15 | 0.60 | 0.77 | — |

Hazard-sum calibration (E1) 1.01 for both arms. The 30-year hard-kill rate is 1.46 (`BC`) / 1.23–1.27 (`BCN`).

**Reading (§5, applied as written):**
* `BC` on E2 fails the 30-year death rate (1.51), the die-off capture (0.36) and the hard-kill calibration (0.82) ⇒
  **not adopted**. The "better than the map" clause also fails: capture +0.085 over `BMW3` (needs ≥ 0.1) and its
  30-year rate is 12 % worse (1.51 vs 1.34; allowed 10 %). The release keeps no mortality output.
* Expectations: E1 `BC` capture 0.35–0.55 ✓ (0.37); `BCN` 0.6–0.8 ✓ (0.74); E2 0.05–0.1 below E1 ✗ — E2 equals E1
  (0.36 vs 0.37): building the at-risk trees from the emulated distributions costs nothing on capture, but costs on
  the 30-year level (1.51 vs 1.37). `BMW3` hard-kill capture ≤ 0.3 ✓ (0.27).
* `BCN` ≥ 0.5 ⇒ per §5 the per-tree structure is NOT the missing piece alone: with the run's own carbon balance the
  per-tree model captures 0.74 of the die-off jump against the cell map's 0.60 with the same input, and without it
  only 0.36. **The binding lever is the year's carbon signal.** The deployable version of it is the emulator's own
  daily NPP (ADR 0363 §8, c3). Cost of trying it: forcing arrays exist for runs m1–m4 on the first five climate models
  only; training needs the full emulator run on the 135 training run-legs (runs m1, m2, m3, m5, m6 × 27 legs), i.e.
  forcing for the five newer climate models and setups for runs m5/m6, ~25 core-hours of emulator runs. Not started
  (owner's call); and the emulated NPP is the daily model's weakest flux (3.9× a second run, ADR 0353), so the
  bound 0.74 is an upper limit for that route.
* No arm passes the 30-year death-rate bar (best 1.25, both NPP bounds). The year-to-year rate is easy (every arm
  ≤ 1.1); the long-term level under the late-century climate is not.
