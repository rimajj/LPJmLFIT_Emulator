# 0364 — A per-tree mortality model: learn each tree's leaf carbon against its sapling threshold and its chance hazard (pre-registration)

* **Status:** pre-registered 2026-10-22, before any fit of this record (the training tables were being built).
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
