# 0363 — Emulate the whole tree population: height, actual rooting depth, trait distributions with their joint structure, and mortality (pre-registration)

* **Status:** pre-registered 2026-10-22, before any fit of this record.
* **Owner instruction (2026-10-22):** "the emulator is far from finished. the goal was to be able to create the same
  output as the original model … tree height is missing. also the trait distributions, not only the means are needed
  for example for calculating biodiversity indices … [the actual rooting depth] is what we would need as well …
  mortality is still not emulated good enough. fix also that … have the papers collected for the review in mind."
* **Follows:** ADR 0340/0358 (the release emits tree count, biomass per tree, four trait MEDIANS, leaf area, vegetation
  carbon, plant-type cover — no height, no distribution, no actual rooting depth, no deaths); ADR 0350–0357 (drought
  die-offs: the forest map captures 18 % of the drop; the die-offs are each tree's leaf-carbon hard kill).
* **Code:** `scripts/build_panel_yearly_v2.py` (tables, done), `scripts/explore_panel_popmap.py` (arms, new),
  `scripts/fdiversity.py` (indices, new).

## 1. Facts this record rests on (verified 2026-10-22)

1. **Maximum rooting depth (`D95max`) is a trait, not the depth the tree has.** It is the depth above which 95 % of the
   roots would lie on the full 20 m soil column; it is drawn (or inherited) at establishment and sets the root profile
   `beta_root = getbetaroot(2000 cm, D95max)` (`new_tree.c:237`, `getbetaroot.c`). The **actual** rooting front grows
   with height, `rootdepth = 20 m / (1 + e^(−k_root·20·H)·(20/0.1 − 1))` with `k_root = 0.02` for every tree
   (`getrootdepth.c`, logistic root model, `lpjmlfit.js:74`): 0.7 m at H = 5 m, 4.3 m at 10 m, 18.8 m at 20 m. The
   emitted `D95` is the 95 % depth of that truncated profile (`fwriteoutput_ind.c:142`). Measured on 72 052 tree-years
   (40 cells, 2015–2019): `D95` recomputed from `D95max`'s `beta_root` and the tree's **previous-year** height
   reproduces the emitted value to a median relative 1.8e-6 (99th percentile 4.5e-5; same-year height: 3 %), because
   `allocation_tree.c:152` sets the depth from the height the tree enters the year with. For trees ≥ 5 m the actual
   `D95` is a median 0.77 of `D95max` (0.19 at the 10th percentile), so the two are different quantities.
2. **The drought threshold (`minwscal`) is a per-tree trait with two jobs.** (a) Leaf display: the water filter of the
   tree's phenology switches from open to closed when its daily water supply/demand ratio `wscal` falls below
   `minwscal` (`phenology_gsi.c:73-76`, a near step ~0.01 wide, CLAUDE.md §3). (b) Drought mortality: water stress
   accumulates on days with `wscal < mort_water_res − minwscal` (`waterstress_tree.c:31-37`) and enters the yearly
   death probability (`mortality_tree_ind.c:120`). A high `minwscal` sheds leaves early but is stressed later.
3. **Deaths in the original (trees ≥ 5 m, panel, two legs × four runs):** 4.8 % die per year; the sum of the C's own
   yearly death probabilities (`mort`) gives 3.2 % ⇒ **a third of all deaths are "excess" deaths** (hard kills: leaf
   carbon below a sapling's or five bad years in a row; and fire — ADR 0356 §7, 0357). Between two runs a cell's
   single-year death rate differs by a median 35 % (dense cells), its 30-year mean by 7 %. Height (median, 90th
   percentile) and actual `D95` median differ by 3–6 % between two runs per cell and year.
4. **The training tables already hold distributions.** `xpanel/yearly/` carries 1st–99th percentiles of the four
   traits, height and biomass per tree for every run, leg, cell and year; `yearly2/` adds actual `D95`, age, leaf
   longevity, means, deaths (total, by type, expected chance deaths). Gate: equal to version 1 on every shared column
   (126/126 member-legs at the time of writing, 0 mismatches). Per-tree rosters every 5 years:
   `/p/projects/reformit/Jamir/esm_land_emulator_data/xpanel_rosters/`.

## 2. The literature (review corpus `~/dgvm-review-corpus/`, 118 texts; outside-corpus methods named as such)

* **No corpus study emulates a within-cell size, trait or mortality distribution.** Closest: age-class bins carried
  by an LPJ-GUESS emulator (R00661) and inside LPJ-wsl (SB1_0492); stand-mean canopy height from ED (R00514, R01133).
* **Joint structure:** the only corpus joint-distribution method separates marginals from a dependence model, a copula
  (R00846, L777–786). Outside the corpus, the standard tool for restoring multivariate dependence after per-variable
  post-processing is the **Schaake shuffle** (Clark et al. 2004, J. Hydrometeorol. 5:243) / **ensemble copula
  coupling** (Schefzik, Thorarinsdottir & Gneiting 2013, Stat. Sci. 28:616): predicted marginal quantiles are
  re-ordered by the rank structure of a real sample. The indices: functional richness / evenness / divergence
  (Villéger, Mason & Mouillot 2008, Ecology 89:2290), dispersion (Laliberté & Legendre 2010, Ecology 91:299), Rao's Q
  (Rao 1982). Richness is sample-size dependent ⇒ the emulator must emit a sample of virtual trees, not moments.
* **Mortality:** R00234 (CNNs on LPX-Bern, L24–33): predicting extreme low-GPP years works when the **continuous**
  quantity is learned and thresholded, and fails as direct binary classification. Transfer: learn the quantity the
  original thresholds on (each tree's leaf carbon against a sapling's) and apply the original's rule. R01728 (Rammer &
  Seidl's learned state transitions for iLand) for the memory of a die-off; R01025 (censored regression for outputs
  with many zeros). Outside the corpus: integral projection models (Easterling, Ellner & Dixon 2000, Ecology 81:694),
  per-tree discrete-time hazard models.

## 3. Stage A — the population map (non-recursive, alongside the release's forest map)

Same rows, anchors, climate offset, start state and held-out design as the release's forest map (`fix`, ADR 0352):
training runs m1, m2, m3, m5, m6 × the 27 legs of the nine other climate models × every 4th year; test = run m4 (truth)
and m5 (harness) × the held-out model's three legs × every year; held-out model = each of the first five. LightGBM as
the release (`explore_panel_a7.PARAMS`, 400 rounds). Per quantity q the inputs are: the 25 trailing 30-year climate
means and their offsets from the anchor legs' climate; the anchors of q AND of the release's six quantities; q's own
2000–2019 level of the run and its offset from the training runs'; lat, lon, soil code. Target = q − anchor of q (log
ratio for biomass per tree, as the release).

**Variables** (living trees of types 0–6, height ≥ 5 m — the release's population): height, biomass per tree, SLA,
wood density, `D95max`, `minwscal`, actual `D95`, age; and the seven tree-type shares.

* **Null `A0`** — the anchor quantiles alone (the mean over the training runs and legs of each quantile).
* **Arm `AQ`** — one model per quantile level (1, 5, 10, 25, 50, 75, 90, 95, 99 %) and variable; crossing quantiles
  are sorted (monotone rearrangement).
* **Arm `ALS`** — location–scale: one model for the median, one for ln(90th − 10th percentile); the other levels =
  median + spread × the anchor's own standardised shape. Two models per variable, crossing impossible.
* Type shares: one model each (value − anchor), clipped at 0 and renormalised.
* **Harness `second`** — run m5 scored as if it were the emulator: ratio 0.9–1.1 to the pooled second runs.

## 4. Stage B — the joint structure and the virtual trees

For each cell and year a **virtual roster** of N = round(tree count per patch × 25) trees (the release's tree count,
so richness sees the right sample size): take a **donor roster** of real trees, draw N of them (stratified by the
emulated type shares), and replace each variable's value by the emulated quantile function at the donor tree's rank
within its variable (Schaake shuffle / ECC). Donors:

* `D0` — the run's own 2019 roster (what the setup of a continued run holds; deployable everywhere the release is).
* `DA` — a training run's roster of the same year on a training leg of the same scenario (run m6; the climate model
  = the next one in `explore_panel_prep.GCMS` order after the held-out one); deployable as a per-cell table.
* **Actual rooting depth**, two ways: `learned` (its own quantiles, as any variable) and `derived` — computed per
  virtual tree from its `D95max` and its height rank in the previous year's emulated height distribution through the
  original's formula (§1.1). `derived` keeps rooting depth physically consistent with height and trait by
  construction.

## 5. Biodiversity indices (`scripts/fdiversity.py`; the same code on the original's and the emulator's trees)

Traits standardised with fixed constants (ln SLA, wood density, ln `D95max`, `minwscal`; mean/sd of all trees of run
m1 in 2019): community-weighted mean and variance of each trait, functional richness (4-D convex-hull volume),
divergence, evenness (minimum spanning tree), dispersion (mean distance to the centroid), Rao's Q (mean pairwise
distance; ≤ 1 500 trees, else a fixed-seed subsample of 1 500), type Shannon and Simpson, height Shannon (5 m
classes), height Gini. Years 2020, 2030, …, 2100.

## 6. Stage C — mortality

Quantities per cell and year: **death rate** `n_dead / (n_living + n_dead)`, **chance-death rate** `exp_dead / at
risk`, **excess-death rate** = the difference (hard kills + fire), deaths by type (reported).

* **Null `B0`** — the anchor.
* **Arm `BM`** — the population map of §3 (30-year climate only).
* **Arm `BMW`** — `BM` + this and last year's weather anomaly (the release departure model's 50 z-scores) + the
  daily-bucket stress statistics (ADR 0355, this and last year, raw and z). Deaths are a yearly flux, not a state, so a
  non-recursive map may read this year's weather without any memory.
* **Arm `BC` (later, own addendum before its fit)** — the R00234 lesson applied: a cohort model of each tree group's
  leaf carbon relative to its sapling threshold, moved by the emulated yearly carbon balance, with the original's hard
  kill applied exactly (ADR 0357's rebuild of leaf carbon from the tree table gives the training target). It needs the
  daily networks run on the training legs (for the emulated NPP); built only if `BMW` misses §7's die-off bar.

## 7. Measures and bars (written before any fit)

Per held-out case (5 models × 3 scenarios = 15) and year, cells split dense (anchor ≥ 5 trees per patch) / sparse,
everything as a ratio to the pooled second runs m1–m3 against the truth m4 (ADR 0317):

* **Distribution error** of variable v: `W = mean over the 9 levels |q_X − q_T| / |q_T,50|` per cell-year; ratio =
  median over cells of W_X / the same for the second runs; reported for the 5 %, 50 %, 95 % levels alone too.
  **Bar (dense):** typical ratio ≤ 1.2 in ≥ 12 of 15 cases, worst tenth ≤ 1.5; **(sparse)** typical ≤ 3.
* **Indices:** the same ratio on each index's relative error. Bar: dense typical ≤ 1.5 for richness, dispersion,
  Rao's Q and the trait CWMs/CWVs; reported for the rest. Computed from `AQ`/`ALS` × `D0`/`DA` virtual trees.
* **Actual rooting depth:** `derived` must be within 10 % of `learned`'s ratio or better — then `derived` ships
  (consistency with height for free).
* **Mortality:** 30-year-mean death rate, dense: typical ratio ≤ 1.2; yearly death rate: typical ≤ 1.5; **die-off
  years** (ADR 0350's shared events): share of the original's excess deaths in the event year reproduced (capture)
  ≥ 0.5 for `BMW`, null `BM` expected ≤ 0.2. Area-weighted total deaths per year within 5 % (dense).
* **Expected (written before):** harness 0.9–1.1; `A0` ratios ~1.3–1.6 for height and traits (the anchor has the
  cell but not the run's offset or the held-out climate's shift); `AQ` ≈ `ALS` on medians, `AQ` better in the tails
  by ≤ 10 %; joint structure from `DA` ≥ `D0` on CWV/richness late in the century (composition moves away from 2019);
  `BMW` capture 0.3–0.6 (the bucket singles out die-off years at AUC 0.87, ADR 0355).
* **Adoption:** the best arm per stage that passes its bars goes into the package as NEW outputs; the release's
  existing outputs do not change (additive). An arm that misses a bar is reported with its numbers, not hidden.

## 8. Addendum (2026-10-22, written after the stage-A/C scores of §9, before this arm's fit): the NPP upper bound

`BMW` missed two mortality bars (§9): the 30-year-mean death rate (1.32× a second run, bar 1.2; the chance-death
part 1.41×) and the die-off capture (0.28 of the death-rate jump, 0.43 of the excess-death jump; bar 0.5). In the
original both parts are driven by the year's carbon balance: the chance-death probability rises as growth per leaf
area falls (`mortality_tree_ind.c:95-101`), and the hard kill fires when leaf carbon is not refilled. Before building
the cohort model `BC`, one diagnostic arm bounds what a carbon input can give:

* **Arm `BMN` (oracle, not deployable):** `BMW` + the run's own yearly NPP of its trees ≥ 5 m (sum over living + dying
  trees of the `ind` column `npp`, per tree at risk), this and last year: raw, ratio to its trailing 30-year mean
  (2000–2019 in front), z-score against the 30 years before; and the share of trees with negative NPP. Training rows
  use each training run's own NPP; the test row run m4's.
* **Reading (written before):** if `BMN` reaches excess-death capture ≥ 0.5 AND the 30-year chance-death rate ≤ 1.2,
  the fix is the emulated NPP as input (the daily networks run on the training legs, the previously listed c3) — build
  that next. If `BMN` stays below 0.5 capture, a stand-level carbon signal is not enough and the cohort leaf-carbon
  model `BC` is next. Expected: capture 0.5–0.7 (ADR 0357: the original's NPP crash singles out die-off years at AUC
  0.90).

## 9. Results of stages A, B and C (scored 2026-10-22, `explore_panel_popjoint.py score` job 2669107 →
`xpanel/eval/popmap/score_popmap.csv`; 5 held-out climate models × 3 scenarios = 15 cases, years 2021–2100)

All numbers are the median over cells of the emulator's error divided by a second run's error (1.0 = as close as a
second run of the original); "worst" = the worst tenth. Harness (run m5 scored as the emulator) is 0.98–1.02 in every
row, so the scorer is sound.

**Distributions (§3), dense cells, all nine levels.** `AQ` (one model per quantile level) passes every bar and beats
`ALS` everywhere: height 0.86, biomass per tree 0.85, SLA 0.80, wood density 0.70, `D95max` 0.60, `minwscal` 0.66,
actual `D95` 0.76, age 0.87 (worst tenth 0.63–0.90; 15 of 15 cases each). Sparse: 0.93–1.23. ⚠ **The bar has little
power here:** the anchor alone (`A0`) already scores 0.83–1.01 dense, because a smooth prediction of the expected
quantile is compared with a second run that carries its own chance variation. Expectation (§7: `A0` 1.3–1.6) was
wrong. `ALS` is worst on `D95max` (1.04) and sparse cells.

**Rooting depth (§4).** `learned` 0.78 (AQ) vs `derived` 1.09–1.13 (AQ donors D0/DA) and 1.25–1.29 (ALS) ⇒ `derived`
is ~40 % worse, outside §7's 10 % ⇒ **`learned` ships**. Reason (not measured separately): `derived` applies the exact
formula to two emulated quantities (`D95max`, last year's height) paired through the donor ranks, so their errors
compound; the learned map is fitted to the target directly.

**Virtual trees and indices (§4–5), dense, `AQ`.** Donors D0 and DA are indistinguishable (expectation "DA better late"
not borne out) ⇒ D0 (deployable from the run's own 2019 roster). Bars (≤ 1.5) passed: community-weighted means
0.58–0.81, variances 0.56–0.79, richness 1.28 (worst tenth 1.43), dispersion 0.71, Rao's Q 0.72, divergence 0.85,
type Shannon/Simpson 0.91/0.85, height Shannon/Gini 0.96/0.94. **Functional evenness fails (3.3×, every arm incl.
`A0`)**: virtual communities are a median 0.79 vs 0.82 in the original, a 4 % bias, while two runs differ by 1.5 %.
Not diagnosed; candidate: the piecewise-linear quantile function between nine levels clumps the virtual trees.

**Mortality (§6), dense.** `BMW`: yearly death rate 1.01 (bar 1.5, passes), area-weighted total deaths within 2.0 %
(15 of 15 within 5 %, passes), **30-year-mean death rate 1.32 (bar 1.2, FAILS; chance part 1.41)**, **die-off capture
0.28 of the death-rate jump, 0.43 of the excess-death jump (bar 0.5, FAILS)**. `BM` (no weather): capture 0.003.
⇒ by §7's adoption rule, no mortality arm ships yet.

## 10. Result of the NPP upper bound (§8, arm `BMN`, jobs 2668546–54)

`BMN` (the original's own NPP as input, not deployable): death-rate die-off capture **0.59** (BMW 0.28), yearly death
rate 0.95, 30-year death rate 1.23 (BMW 1.32), 30-year chance-death rate **1.25** (bar 1.2), **excess-death capture
0.42 (BMW 0.43, unchanged)**. §8's reading, applied as written: excess capture stays below 0.5 ⇒ a stand-level
carbon signal is not enough for the hard kills ⇒ **the cohort leaf-carbon model `BC` is next** (own addendum before its
fit). Carbon input does carry the chance-death part (capture doubles, the 30-year chance rate nearly reaches its bar),
so `BC` should take the emulated NPP too.

## 11. Note (2026-10-22, after §9, owner question): compute a dependent quantity, or learn it?

Owner: *"many traits have a direct mathematical relationship … learned quite well … but it might also be cheap to
calculate these. did you consider both cases?"* Only for actual rooting depth (§9: learned won). Measured since, on
3.6 M living trees ≥ 5 m (run m1, canesm5 ssp370 rosters): within a plant type, ln(biomass per tree) is a linear
function of ln height, ln wood density and ln SLA to **0.6–1.9 % median per-tree error (R² 0.998–0.999)**; height
alone 13–29 %; adding age gains ≤ 0.4 points. (Mechanism: pipe-model height `k_latosa·sapwood/(leaf·SLA·wooddens)`,
`allometry_tree.c:39`.) So biomass per tree could be computed per virtual tree instead of learned — cheaper (no nine
models) and consistent with height and traits by construction. Not yet compared with `AQ`'s learned biomass (0.85);
§9's rooting-depth result warns that the computed path compounds the errors of its inputs. The four traits themselves
are drawn independently at establishment (no formula links them); leaf longevity is a noisy function of SLA.
