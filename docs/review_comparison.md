# The LPJmL-FIT emulator compared with the published state of the art, and what to try next

*Written 2026-10-07. The comparison is against the systematic review of DGVM and land-surface-model emulators at
`~/dgvm-review-corpus/` (115 included studies). This is an exploration note: it is not a decision record, changes
no code, and schedules nothing. Every project number below was read from this repository's code, committed reference
tables, logs or decision records (decision records are cited as "ADR nnnn" pointers, not as explanations). Every
literature claim carries the corpus record ID and a verbatim quote with its line number in
`fulltext/txt/<id>.txt` (L…). Numbers I derived myself are marked "(derived)".*

**How fresh the project facts are.** The learned demography, the physics core, the energy closure, the coupled
driver and the online-coupling work were last changed on 2026-08-17/18. Since then only the exploration work stream
(line X) has been active. Its most recent work is the Germany build (2026-09-30 → today). The separate successor
project `vegemu` (a direct climate → equilibrium-state map) is summarised in §1.9 because it is part of the same
programme. It is not the subject of this comparison.

---

## Contents

0. [Summary in one page](#0-summary-in-one-page)
1. [What has been tried here](#1-what-has-been-tried-here)
2. [Dimension-by-dimension comparison with the literature](#2-dimension-by-dimension-comparison-with-the-literature)
3. [Gaps, theme by theme](#3-gaps-theme-by-theme)
4. [Ranked proposals](#4-ranked-proposals)
5. [Where this project is already ahead of the published state of the art](#5-where-this-project-is-already-ahead-of-the-published-state-of-the-art)
6. [What not to do](#6-what-not-to-do)
7. [Papers outside the corpus worth retrieving](#7-papers-outside-the-corpus-worth-retrieving)

---

## 0. Summary in one page

**Where the project stands against the literature.** No published study emulates what this project emulates: the
demography of an individual-tree DGVM, with trait distributions, together with daily carbon, water and energy fluxes
for coupling. The review finds no emulator of tree-count, size or trait distributions or of individual mortality,
and none of LPJmL or LPJmL-FIT vegetation dynamics. Four of this project's practices are stricter than anything in
the corpus:

- its honesty apparatus: seed noise floors, a persistence null, pre-registered nulls, and a loop with the original
  model's physics plugged in;
- its conservation gates (water and carbon to ~1e-12, energy to ~1e-14);
- its coverage of the coupling interface (sensible and latent heat, skin temperature, ground heat, albedo and
  roughness together with carbon);
- its scenario hold-out tests. None of the 7 full emulators in the corpus tests a climate outside its training
  range.

**Where it is behind.** On the three failures that matter most, the published work points to known remedies the
project has not used:

1. **Rollout drift.** The annual demography operator is a one-step-trained tree ensemble. That is exactly the
   configuration the ECMWF land-emulator study found to drift, while networks trained on their own multi-step
   rollouts did not: "XGB specifically drifts at long lead times" (R00067 L1225). The project's free-running
   warming response flips sign (+0.707 one-step → −0.226 free-running; ADR 0113–0116). The fixes in the literature
   are a rollout loss with increment targets (R00067, R00593), fitting the dynamics on the free-running trajectory
   (R00661), or a signed zero-sum loss over short teacher-forced segments (R01133). None has been tried here.

2. **No identifiable warming response in the data.**
   - Across the global grid, 76.4 % of a cell's warming is predictable from its baseline climate (ADR 0311).
   - In the Germany data, the scenarios separate only in the years that were run with a humidity setting error.
   - The literature shows that present-day fidelity says nothing about the warming response (R00289). It also shows
     that stylised temperature/precipitation factorial training data do not transfer to real scenarios (R00430).

   So the training data need climate contrasts that stay close to realistic ones. The model architecture is the
   secondary problem.

3. **Speed.** The emulator is **4.62× slower** than the original per cell-year (1.233 vs 0.267 core-s at 25 patches;
   ADR 0084, which supersedes the earlier 3.8×). No speed change has landed since 2026-08-07. In the literature the
   large speed-ups come from replacing the expensive iterative solver or the whole daily physics step with a learned
   one, not from re-implementing it:
   - 18× for a learned groundwater solver (R02497);
   - +3 % runtime for a polynomial canopy-temperature emulator inside LPJmL (R00568);
   - ~4800× for a small network replacing ecLand's step (R00067, derived).

   In this project, 83 % of the emulator's runtime is one iterative solve, and in the original model leaf gas
   exchange plus soil water take 51–69 % of runtime, while the demography takes 0.4–1.1 % (ADR 0084, 0312).

**What to try next, ranked by benefit against effort** (details in §4):

| # | proposal | serves | benefit | effort |
|---|---|---|---|---|
| 1 | Make the warming response testable: a constant-climate control run of the original model, re-run the Germany 2071–2100 years with the corrected humidity setting, and add a third and fourth independent member | fidelity (the binding clause) | very high | low (model runs with existing scripts) |
| 2 | Train the annual dynamics on their own free runs (rollout loss / free-run calibration / data aggregation), scored against persistence, frozen-climate and climate-blind nulls | fidelity | high | medium |
| 3 | A designed transient climate-contrast ensemble on ~1000 stratified cells, built from real GCM patterns rescaled, not stylised factorial deltas | fidelity, out-of-distribution | high | medium (~10² core-h at 25 patches, derived) |
| 4 | Land the photosynthesis-solver speed fix that is already measured (analytic derivative + fewer iterations) | speed | medium (≈1.4–4×) | low |
| 5 | A long-run stability gate under recycled climate, then an equilibrium initialiser feeding a forward emulator | coupling, fidelity | medium-high | low (gate) / medium (fix) |
| 6 | Separate the atmosphere-facing fluxes (few patches) from the demography (many-patch ensemble expectation) | speed | high | medium |
| 7 | Test a learned daily water–carbon flux model with an explicit soil-water state (aiLand pattern), first offline on the existing ~1 TB daily dataset | speed (the only route to the ESM target), fidelity | very high if it works | high (phase A: weeks) |
| 8 | Close the coupler interface: export reflected shortwave, upward longwave, runoff and snow; use real wind and pressure; add soil respiration and fire so net CO2 exchange is complete | coupling | medium | low–medium |
| 9 | Calibrated uncertainty: score predictive distributions against the spread between independent runs; hand the coupler the ensemble expectation | fidelity, coupling | medium | low–medium |
| 10 | Before any online science: a coupled self-test and a "no-learned-process" null | coupling | low now | low |

If only one large item can be funded:

- **#7** for speed: it is the only proposal that can plausibly reach the 0.0135–0.030 core-s per cell-year targets.
- **#1 + #3** for fidelity: without them no architecture can be judged on the warming-response clause.

---

## 1. What has been tried here

### 1.1 Target model and outputs

- **Target:** LPJmL-FIT v5.6.004, run in individual-tree mode. Each 0.5° cell has 25 patches; there are 67 420 cells,
  of which 54 020 carry trees.
- **Configuration:** natural vegetation only, carbon only (nitrogen off), stochastic establishment and mortality.
  CO2 is constant in the future runs, by design (see §1.2).

The **acceptance criterion** (ADR 0106) covers four things:

- tree counts, trait medians and trait quantiles (q05–q95), each within `max(10 %, the original model's own two-run
  spread)`;
- on all 54 020 tree-bearing cells;
- in both scenarios;
- **and in the change between the scenarios.**

The architecture has three components:

| component | step | what it outputs | how |
|---|---|---|---|
| **Learned demography** ("S") | annual | count of living trees >5 m per patch (1–48); recruit traits on 4 axes (SLA, wood density, maximum rooting depth D95max, drought threshold minwscal); which cohorts die | count: a distributional random forest; traits: a Gaussian copula; deaths: the original model's own mortality hazard, ported exactly (5e-18 error over 1.57 M stem-years; ADR 0183) |
| **Fast physics** ("F") | daily, plus annual growth | GPP, NPP, transpiration, evaporation, interception, 23-layer soil water, snow, phenology, layered canopy light, per-individual allocation and growth | a from-scratch differentiable Julia re-implementation of LPJmL-FIT's physics (`src/fdiff.jl`, 3 541 lines) |
| **Energy closure** ("E") | daily | skin temperature, sensible heat (as the residual), ground heat, net radiation | a surface energy balance that LPJmL-FIT lacks (`src/components/energy.jl`) |

Two facts that are often missed (`src/components/fast.jl:402-405`):

- Heterotrophic respiration, fire and establishment carbon are **hard-wired to zero** in the physics core, so the
  coupled net CO2 flux reduces to −NPP.
- Runoff and snow are computed but not exported.

### 1.2 Inputs and forcing

- **Daily forcing.** GSWP3-W5E5, in a 365-day calendar: air temperature, precipitation, downward shortwave, net
  longwave and specific humidity. Day length comes from latitude.
- **Wind and surface pressure.** These feed only the energy closure. They were remapped from ISIMIP3a (ADR 0071),
  but the coupled driver still runs **constant 2 m/s and 1e5 Pa** (`scripts/run_coupled_biomes.jl:115`).
- **CO2.** It is a field of the interface, but it is held constant on purpose (ADR 0004, 0107). LPJmL-FIT runs
  constant CO2 in its future runs, because with nitrogen limitation off its own CO2 fertilisation is unbounded. The
  emulator's lack of a CO2 response is therefore faithful, not a gap. This report proposes nothing involving CO2.

The learned count model uses 15 raw-unit features, with no normalisation:

| group | features |
|---|---|
| annual flux drivers from the physics (4) | carbon increment, growth efficiency, water stress, root-zone soil moisture |
| stand aggregates (6) | mean height, maximum height, biomass, per-patch LAI, crown cover, mean age |
| last year's count | `n_prev` |
| site and climate (4) | 20-year growing degree days and coldest-month temperature, soil depth, constant CO2 |

The trait copula conditions on 8 of these columns. Flux conditioning beat climate-only conditioning on a warm and
dry hold-out: R² 0.76 vs −0.16 (ADR 0020).

### 1.3 Training data

| what | volume / design | source |
|---|---|---|
| Runs | 1000-yr spin-up → historic 2000–2019 (from the 1999 restart) → SSP370 2020–2100 (from the 2019 restart); 2 independent members (seeds) | CLAUDE.md §1; ADR 0041/0043 (the first SSP370 "seed 2" was a byte-identical clone and was replaced) |
| Count-model table | 121.5 M rows, 58 588 cells, historic + SSP370 pooled, seed 1 | `slow_count_pooled_w20_t8` |
| Trait-copula table | 42.2 M surviving-stem rows, ≤400 stems per cell | ADR 0025 |
| Underlying tree table | 2.55 × 10⁹ stem-years | `ind_hist_seed{1,2}_all.parquet` and the SSP370 equivalents |
| Daily flux data | 198.7 GB historic + 805.6 GB SSP370, all 67 420 cells, **seed 1 only** (so the daily side has no two-run spread) | ADR 0310 |
| Extra scenario | SSP126, both seeds, a different model binary; used in no training table | — |
| Germany set (exploration, 2026-09-30 →) | 9 067 cells × 250 patches; MPI and ACCESS climate models; historical + SSP126/245/370; up to 2 seeds. **Only 1985–2044 is usable**: the 2071–2100 segments were run with the humidity setting missing (water-stress mortality exactly 0) | `lines/X/STATE.md` §00✦ |
| Perturbed-parameter or climate-perturbation ensemble | **none** for the forward emulator. Two extra reference members were planned on 2026-08-07 but never run | EXECUTION_PLAN §3 |

The effective number of independent places is about **161 populated 15°×15° tiles**, not 54 020 cells (ADR 0310 §7).

### 1.4 Architectures tried

| model | details | outcome |
|---|---|---|
| Count forest | Distributional random forest written natively in Julia: 150 trees, depth 16, min leaf 20, subsample 2e5, mtry 4 | one-step held-out-by-cell R² 0.9824 |
| Ratio-target count model | Predicts `n_t / n_{t−1}` | refuted: free-run R² 0.678, predictions up to 799 stems where the maximum is 48 (ADR 0115) |
| Gaussian-copula trait sampler | 60 trees, depth 14, one global correlation matrix, trained on survivors | shipped. Survivor training adds +12.18 % to wood density (ADR 0174) |
| Bounded Beta marginals | — | descoped: compared like for like, worse on all four axes (ADR 0173) |
| Ported establishment rule | — | off: response sign varies by cell (ADR 0170–0172) |
| Level anchor | — | rejected (ADR 0105, 0113) |
| Python LightGBM + copula "direct emulator" | — | kept as the out-of-distribution benchmark only |
| Learned corrections inside the physics | Zero-initialised MLPs scaling Vcmax and λ (the ratio of leaf-internal to ambient CO2), bounded `1 + 0.6·tanh` | Hainich GPP ratio 1.093 → 1.010. Trained through 3 years of rollout with Enzyme/Zygote. Off by default, used nowhere (`ext/FDiffTrainingExt.jl`) |
| **Germany, per-tree boosted trees (TAB)** | — | free-run pass 0.34–0.46 vs lookup 0.07–0.11; **a climate-blind twin does almost as well** |
| **Germany, learned growth + the original's death/recruit rules** | — | free run 0.00 |
| **Germany, cell-level 2×64 LSTM over yearly cell statistics + climate** | — | **0.79–0.91** of held-out cells pass from 1985 on a held-out climate model (seed-to-seed ceiling 0.92–0.93); about 2.4e-6 core-s; emits no trees; collapses on resampled historical weather |
| Germany, neural set model | — | built, tensors round-trip exactly; scoring in progress |
| Germany, per-tree "margin" model | log(gain/loss) per tree | timing of bad years on unseen weather: correlation 0.505 → 0.838; stand biomass per stem −19 to −25 % |

**No neural network was ever tried in the global learned demography.**

### 1.5 State, memory and spin-up

The learned demography carries four things from year to year:

- a roster of density-weighted cohorts (capped by a merge that, under real forcing, destroyed 54 % of the response);
- last year's count;
- each cohort's run of consecutive bad-growth years;
- the random-number state.

The physics core carries:

- per-individual carbon pools (7);
- the 23-layer soil water and the snowpack;
- the per-PFT phenology filter states;
- stress accumulators that reset on the coldest day of the year, as in the original.

**There is no spin-up of any kind:**

- The canopy is reconstructed from the original model's 2010 tree table (stems >5 m only), faithfully: crown cover at
  t = 0 is 0.995–1.038 of the original's.
- Soil water starts at 0.7 of capacity.
- Nothing predicts an equilibrium state.
- The coupled model has **no steady state** under exactly periodic forcing: above-ground biomass drifts 1.39–5.15×
  per 100 years (up to 12.45× at the boreal cell; ADR 0055).

### 1.6 Constraints

- **Water:** closes by construction in the soil bucket (~1e-12).
- **Carbon:** conserved by "flux then integrate" plus a ledger at the hand-off between physics and demography
  (~1e-12 gC).
- **Energy:** closes by construction, because sensible heat is the residual (1.4e-14 W/m²).
- All three are continuous-integration gates.
- There are no distribution-level constraints in the learned demography.

### 1.7 Train/test splits, leakage, metrics

**Splits used:**

- 5-fold by cell (hash-assigned);
- held out by scenario;
- spatial blocks for the conditioning question (ADR 0040/0042);
- in Germany, also held out by climate model.

**Leakage found by the project itself:**

- Every published global score of the learned demography is a **one-step, teacher-forced** score, because all 15
  features, including last year's count, come from the original model's own row (ADR 0112).
- At runtime the model sees its own previous count next to features from the live roster (ADR 0175).

**Metrics:**

- R² against a **persistence null**: 0.9824 vs 0.9622. The null ties the model on every count-response statistic.
- A per-cell, per-quantity two-run noise floor: stems 6.8 % (16.6 % in sparse cells), carbon 10.2 %, D95max 13.2 %.
- **Deattenuated response slopes**, corrected for seed noise (ADR 0111): SLA 1.28, wood density 0.66, D95max 0.73,
  minwscal 1.06.
- Per-cell KS distances.
- Fraction of cells inside the 10 % band.
- Validity horizon: how long a free run keeps a faithful response.

### 1.8 Rollouts, what worked, what failed

**Rollout length:**

- Offline free runs over 81 years (SSP370).
- Coupled runs at five biome cells: 10 years.
- One 300-year coupled run at Hainich.

**Free-running learned demography (ADR 0113–0116):**

- R² 0.982 → 0.918.
- Area-weighted warming-response ratio +0.707 → **−0.226**.
- The response is faithful for about 3 years and inverted by year 40.
- The mechanism is **rectification**: the recursion follows 86.7 % of a large decline but 96.2 % of a large rise.
  The resulting drift, +0.155 stems/patch, is the size of the original's entire global count response.

**The learned demography with the original model's own physics in the loop** (ADR 0175–0189, 0240–0245):

- Almost the whole apparent warming response was drift (ADR 0178).
- The climate input's effect is flat (ADR 0179).
- A count target cannot carry a gross mortality budget: the precision needed is 1.1–1.2 % per patch-year, against an
  irreducible 4.1–4.6 % (ADR 0241). The count model was therefore retired from the mortality path.
- Applying the original's per-tree hazard **as a rate** meets the criterion (stems +4.4 %, biomass +4.1 %) as a
  *ceiling* (ADR 0242).
- On the emulator's own inputs the hazard delivers only 0.78 of the mortality flux. The heat-stress integral is now
  supplied exactly. The water integral is the open item (ADR 0243–0245).

**Fast physics against the original:**

- Seasonal phase: monthly correlation 0.87–0.999.
- GPP on the most faithful configuration: 1.02–1.05 at four of five cells, **1.61 at the Mediterranean cell**, cause
  unidentified (ADR 0136, 0139).
- Annual growth of matched stems: 1.6–4× too fast at cold, temperate and Mediterranean cells (ADR 0125).
- **Warming response of GPP:** 8 % of the original's decline at Hainich, and the wrong sign at the Sahel (ADR 0128).

**Coupled demography + physics + energy (ADR 0105):**

- Terminal tree density over truth: 1.35 / 1.15 / 1.38 / 0.52 / 1.04 at the five biome cells.
- Feeding the true count back each year made it **worse at all five**.
- "Offline bias predicts the coupled error with the wrong size in every cell and the wrong sign in two."

**Energy closure against PLUMBER2 towers:**

- Net radiation R² 0.986–0.996.
- Daily skin temperature RMSE 1.4–2.0 K.
- Daily sensible heat R² 0.65–0.78 with the two-layer ground-heat column.
- Night-time sensible heat R² still negative (ADR 0072–0075).

**Online coupling (SpeedyWeather + Terrarium):**

- Only a run without vegetation completed.
- No physics from this project has run online.
- Terrarium's soil costs ~10 h per simulated year (ADR 0083, 0085).

**Speed (1 core, 25 patches, ADR 0084):**

- Full emulator 1.233 core-s per cell-year vs the original's 0.267, i.e. **4.62× slower**.
- 83 % of the emulator's time is the λ solve. It uses a finite-difference Newton derivative, i.e. about 78
  photosynthesis calls per individual per day.
- Per individual, the daily step costs 51× the original's.
- Three solver iterations instead of 25 give 4.10× with GPP −0.03 %. GPP is non-monotone in the iteration count
  (±2.1 %).
- **Never landed.**

**Speed of the original model:**

- Its cost is exactly proportional to the patch count. At the ~500 patches used in publications it costs 7.06 core-s
  per cell-year, 99.9 % of that being the patch ensemble.
- Atmosphere-facing fluxes converge within 1.7–6.6 % even at one patch (ADR 0086).
- Leaf gas exchange is 36–46 % of its runtime, soil water 15–27 %, the annual demography **0.4–1.1 %** (ADR 0312).

**Speed targets:**

- ≤0.030 (T63-class) and ≤0.0135 (T31-class) core-s per cell-year.
- These are a convention set at 10 % of a measured SpeedyWeather coupled cost, not an owner budget.

### 1.9 Related efforts in the same programme (summary only)

- **`/p/projects/open/Jamir/emulator` (frozen 2026-07-15).**
  - Approach: a direct, non-recursive climate+soil → per-cell distribution emulator (LightGBM + copula), adopted
    after an autoregressive individual-based prototype drifted.
  - Present day: pooled distributions near the seed noise floor; per-cell spatial correlation 0.94–0.97.
  - Per-cell biomass: about 1.8× the noise floor.
  - Its "SSP370 fails" verdict was retracted: the truth it was scored against was corrupted. On the fixed rerun,
    blind extrapolation works (per-cell r ~0.9, ~15 % high at 2100).
- **`/p/projects/open/Jamir/vegemu` (since 2026-09-02).**
  - Approach: a direct 30-year climate summary → equilibrium state map, which writes a byte-loadable LPJmL-FIT restart
    file.
  - Training data: a designed **spin-up climate-perturbation ensemble** (pilot: 200 cells × 30 climates).
  - Passes: restart round trip, warming-response kill test, species-mix test.
  - Fails: the owner's "as good as a rerun" test (vegetation carbon in band in 24.7–42.7 % of cells vs a rerun's
    85.9 %).
  - Its records call this repository the "retired predecessor". Its own memory file records an owner rule that this
    repository must not be changed; that rule is enforced only inside `vegemu`. Line X has continued to commit here.

---

## 2. Dimension-by-dimension comparison with the literature

"Tier A" = the 7 full or multi-output emulators. "Tier B" = the 19 hybrids and differentiable models. "Tier C" = the
89 partial emulators.

| dimension | this project | Tier A practice | Tier B/C evidence | verdict |
|---|---|---|---|---|
| **Target and outputs** | Individual-tree demography (counts, 4 trait distributions, mortality) + daily carbon/water + energy closure | Stand-level means (ED: height, biomass, LAI, GPP, NPP, Rh; R01133, R00514); soil states + turbulent fluxes (ecLand; R00067, R00593); biome carbon stocks (R00661); equilibrium slow pools (R01211) | "No study emulates a size distribution, trait distribution, stem density or individual mortality of a DGVM" (corpus search). The only distributional emulator of an individual-based model is iLand's state-transition network (R01728) | **ahead in scope**; no precedent to borrow from for the demography target |
| **Inputs and encoding** | 15 raw-unit features incl. lagged count; 20-yr climate windows; no normalisation | Per-variable z-scores; increments divided by their own standard deviation (R00067 L532-535; R00593 L334-341); age-trend inputs (R01133) | R00312 keeps lagged soil moisture out of the inputs to avoid persistence leakage | **behind**: no increment scaling; the lagged-state leak was found here only after the fact (ADR 0112) |
| **Training data** | 2 seeds × historic + SSP370 (global); Germany: 2 climate models × 3–4 scenarios; no climate-contrast design | 1 trajectory (R00067, R00593); 8–15 initial stand ages (R01133, R00514); 48 factorial runs incl. a recycled-climate control (R00661); 3 000-member parameter ensemble (R00004) | Delta-change grid works for total NPP but not species NPP (R00201); stylised factorial runs fail to transfer (R00430); GCM-pattern changes relative to each cell's baseline (R00013/R01025) | **behind** on designed climate contrast; **ahead** on independent members |
| **Architecture** | Distributional forest (count) + copula (traits) + ported hazard; differentiable physics; Germany: boosted trees, LSTM, set model | LSTM (R01133), conditional diffusion (R00514), MLP/LSTM/XGBoost (R00067), 6×512 residual MLP (R00593), LSTM+CNN+Transformer (R01211), regression (R00661), polynomial chaos (R00004) | Tree ensembles cannot predict outside their training targets (R00430's random forest under-predicts late-century GPP) | **behind** for the dynamic operator (one-step tree ensemble); the Germany LSTM is the first rollout-capable learner |
| **State / memory / spin-up** | Explicit cohort roster + pools; no spin-up; no stable fixed point under periodic forcing | Autoregressive states (R00067, R00593, R01133); explicit pools (R00661); equilibrium predictor + real-model relaxation (R01211) | Predict slow pools, then re-run the original model 100–350 yr (R00211); "no study pairs an equilibrium predictor with an emulator that integrates forward" | **at par** on explicit state; **behind** on initialisation and long-run stability |
| **Rollout and stability tricks** | One-step training; free-running 81 yr; drift diagnosed precisely | Increment + rollout loss (R00067 Eq. 3); 4 → 8-step curriculum, gradient clipping 5.0 (R00593 L359-364); signed zero-sum segment loss (R01133 L556-562); free-run trajectory fit (R00661 L997-1006); non-autoregressive generation (R00514) | Re-anchoring by assimilation (R00099); periodic restart (R02497) | **behind** on remedies; **ahead** on diagnosis (one-step R² next to a free-run score, which no Tier A study reports) |
| **Conservation** | By construction, gated at 1e-12 / 1e-14 | Residual updates + bounds (R00593); softplus non-negativity + soft NPP = GPP − Ra penalty (R01211); explicit pool recursions (R00661) | Hybrids keep balance equations (R00532, R00755, R00383); only 25/115 studies check conservation | **ahead** |
| **Train/test split** | By cell, scenario, spatial block, climate model; effective sample quantified | Random 50/50 (R01133); random 80/20 (R01211); ≥1° separation (R00514); temporal (R00067, R00593) | k-fold inflates r by ~0.2 against independent cells (R00289) | **ahead** |
| **Metrics** | Noise floor, deattenuated response slope, persistence null, validity horizon, KS | RMSE / R² / CRPS; persistence and climatology baselines (R00067) | Ensemble-range threshold (R00167); emulator-vs-model sensitivity check (R01202) | **ahead** |
| **Out-of-distribution climate** | Scenario hold-out; held-out climate model; warming response is the criterion | **0 of 7** test it (review RQ4) | 12/115 test it; present-day perfect, warming response wrong (R00289); interpolation between scenarios works, extrapolation does not (R00430) | **ahead in testing**, not yet in passing |
| **Coupling fluxes** | Sensible and latent heat, skin temperature, ground heat, albedo, roughness, NPP. Missing: Rh/fire (so net CO2 is incomplete), runoff/snow export, momentum flux | aiLand: latent and sensible heat + skin temperature, no carbon (R00593); ED/LPJ-GUESS emulators: carbon only | Only a differentiable CLM-ml-v2 with no learned parts reproduces all coupling fluxes, at one site (R00975) | **ahead**, with clear gaps |
| **Uncertainty** | Seed noise floor; copula sampling; patch ensemble | Diffusion CRPS against single deterministic runs, no calibration check (R00514) | GP coverage 94.8–95.6 % of nominal (R00157); evidential networks under-dispersed (R00613) | **at par**; no calibrated predictive spread |
| **Speed** | 4.62× **slower** than the original; per-tree daily step 51× | 44–4800× (R00067); ~9600× (R01133, CPU-h vs GPU-h); "≥60×" spin-up, really ~10× including the authors' own relaxation run (R01211, derived) | Re-implementing a column model can be ~2× faster than Fortran (R00975); emulating the iterative solver gives the big wins (R02497 18×, R00568 +3 % cost); 16/115 studies count training cost | **behind**; but the most honest cost accounting in the corpus |
| **Coupled / online** | Online harness runs without this project's physics; error-isolation loop with the original's physics plugged in | None coupled (0/7) | Offline skill collapses online for ML fire models (R00342: 0.98 → 0.59) | **ahead** in feedback-aware evaluation; **at par** online |

---

## 3. Gaps, theme by theme

### 3.1 Autoregressive stability and error accumulation

**What the literature shows.** The single sharpest piece of evidence is the ECMWF comparison (R00067):

- XGBoost was trained "only from one time step to the next" (L559), and "XGB specifically drifts at long lead times"
  (L1225). A tree ensemble also cannot be trained on a rollout loss: "XGB is not differentiable" (L1311-1312).
- The MLP was trained on increments plus an autoregressive rollout loss (Eq. 3, L513-543) and did not drift that way.

aiLand (R00593) adds three things:

- **Rollout curriculum.** It trains on 4-step, then 8-step rollouts at a 10× lower learning rate, with gradient
  clipping and standard-deviation-scaled increments (L359-364, L338-341).
- **Long free runs stay stable.** It reports a free 4-year run with "no upward trend" (L591-593).
- **The loss itself can create drift.** It names a mechanism exactly like this project's rectification: a +0.40 K
  bias "consistent with a conditional-mean offset induced by the Smooth L1 loss under the right-skewed
  soil-temperature increment distribution" (L847). The authors separated this from climate shift by running the
  free integration inside the training period (L845-847).

The two demography emulators handle the same problem differently:

- **CLASH** (R00661) fits its dynamic equations "by minimizing the sum of the squared errors between the LPJ-GUESS
  result and values simulated using the fit over the whole time frame (1900–2100)" (L997-1002).
- **Deep-ED** (R01133) keeps one-step-style training but adds a term that "enforce[s] a zero-sum loss on the sum of
  the signed errors" over short teacher-forced segments (L556-562). It also warns that horizon-averaged RMSE hides
  the accumulation (L720-722).
- **EcoDiffusion** (R00514) avoids recursion altogether and reports the least error accumulation among nine
  candidates. It needs the whole forcing sequence in advance, which conflicts with online coupling.

**Gap here.**

- The project's demography operator is in exactly the configuration that drifts, and the rectification it measured
  (86.7 % of declines vs 96.2 % of rises) is a signed, state-dependent bias, which is what both aiLand's loss
  mechanism and Deep-ED's zero-sum term address.
- The Germany results are consistent with this. The cell-level LSTM (a recurrent learner with a multi-year view)
  passes 0.79–0.91 of held-out cells from 1985, while the one-step per-tree boosted trees pass 0.34–0.46.
- But the LSTM emits no trees, and it collapses on resampled historical weather. So it is not yet the answer.
- The project is ahead on diagnosis: no Tier A study reports a one-step score next to a free-run score.

### 3.2 Carrying slow pools and memory

**What the literature shows.**

- **Explicit pools with mass-balance recursions** (R00661; hybrids R00383, R00532) are the consensus for
  conservation.
- **A learned recurrent state that replaces a pool loses the budget.** H2CM has no soil-carbon pool, and its
  respiration comes from an LSTM, so carbon closure is untracked (R00755 §2.2.2).
- **Equilibrium prediction** (R01211) avoids the trajectory altogether. But its "≥60×" leaves out its own required
  100-year relaxation run (≈10×, derived).
- **ORCHIDEE spin-up** (R00211): "the poorer the performance of the ML prediction … the longer the length of the
  re-run".
- **No stationary state.** Even LPJ-GUESS itself has "internal variability … where true steady state is never
  reached" (R00293).

**Gap here.**

- The explicit roster and pools are right.
- What is missing is (a) any way to produce an initial state that is in balance with a *new* climate, and (b) a
  long-run stability property: the coupled model has no fixed point under periodic forcing (ADR 0055). An ESM
  integrates for centuries, so (b) matters more than any present-day score.
- Line X's finding that the per-tree bad-growth counter is exactly recoverable from the printed table, and
  propagable by a model that first produces next year's per-tree state (ADR 0311; its adversarial verification never
  completed), shows that hidden per-tree memory can be carried explicitly rather than learned as a latent state.

### 3.3 Conservation

**What the literature shows.** Learned components should predict rates or fluxes while the host keeps the balance
equations. In the ELM and JSBACH4 fire hybrids, the machine-learning model predicts burned area and the host
reallocates the pools (R00342, R00278), so conservation is independent of the learned rate.

**Gap here.** The project already follows this pattern. Its finding that applying the ported hazard *as a rate*
meets the criterion while a count target cannot (ADR 0241, 0242) is the same lesson, arrived at independently and
with stronger evidence. The only conservation gap is accounting, not architecture: soil respiration, fire and
establishment carbon are zero in the physics, so the net CO2 flux handed to an atmosphere is incomplete.

### 3.4 Out-of-distribution climate

**What the literature shows.**

- **R00289 (ecosys, Alaska).** 2010–2019 agreement was near perfect (NPP 214.3 vs 214.0 gC m⁻² yr⁻¹), yet by 2100
  the model "underestimates Rh by 104 and NPP by 204 gC m⁻² yr⁻¹". The authors attribute this to "changes … that
  have impacts on C fluxes which cannot be inferred from the training data" (L83).
- **R00430 (LPJ-GUESS).**
  - Interpolation between training scenarios works, but "extrapolation beyond this range would require additional
    training".
  - The neural net extrapolated better than the random forest.
  - Stylised factorial training "failed to extrapolate effectively to the real CMIP6 climate scenarios … combinations
    … too far removed from those expected in realistic settings" (L1096-1100).
- **R00013/R01025 (LPJmL).** They predict *change relative to each cell's own baseline* from several GCM patterns.
  This is a design that partly separates response from place.

**Gap here.**

- The identification limit (76.4 % of the warming predictable from baseline climate; ADR 0311) is the same
  confounding R00289 suffered.
- In Germany, the usable 1985–2044 window carries almost no scenario contrast: line X recorded the two scenarios
  differing by +0.015 K in the block it scored. Every arm, including "no difference", fails the contrast test there,
  so the test has no power. The years where the scenarios separate (2071–2100) are exactly the ones run with the
  humidity setting missing.
- So the project is not short of models. It is short of data in which the warming response is identifiable.

### 3.5 Coupling fluxes

**What the literature shows.**

- **None closes the interface.** The review's requirement 2: an ESM land component must return sensible and latent
  heat, upward radiation, momentum roughness and net CO2 flux every coupling step, "but none closes it".
- **Re-diagnose fluxes from the state.** aiLand recomputes its fluxes from the current prognostic state every step
  instead of carrying them, so flux error barely grows with lead time (1.0–1.1× from day 1 to day 90; "effectively
  re-diagnosed from the prognostic state at each step", L585).

**Gap here.** The project covers more of the interface than any published emulator. The open items are
bookkeeping, not science:

- export reflected shortwave and upward longwave (both already computed inside the energy closure);
- export runoff and snow;
- feed real wind and pressure;
- add soil respiration and fire.

### 3.6 Uncertainty

**What the literature shows.**

- **EcoDiffusion** (R00514) scores its predictive spread only by CRPS against single deterministic runs, with no
  calibration check.
- **GP-based surrogates** report coverage, e.g. 94.8–95.6 % of a nominal 95.4 % interval (R00157).
- **TRIFFID study** (R00167): uses an initial-condition ensemble's range as the threshold below which effects are
  not interpreted, i.e. a noise floor.
- **The gap in the corpus:** "no emulator predicts the target's seed spread and scores it against seed pairs".

**Gap here.**

- The project has the noise floor and deattenuation, which puts it ahead.
- It lacks (a) enough independent members to calibrate a predictive distribution: two members give one difference
  per cell, and they disagree on the per-cell response sign in 18.7–42.2 % of cells.
- It also lacks (b) a stated policy on what the coupler receives: the ensemble expectation, worth +2.9 to +14.4 pp of
  cells inside the band at zero cost, is measured but not implemented.

### 3.7 Training-data design

**What the literature shows.**

- **Perturbed-parameter ensembles** dominate the corpus (calibration surrogates). They are not relevant here: the
  target is one fixed parameter set.
- **Climate-contrast designs** are the relevant ones:
  - CLASH's factorial with a control of "climate from years 1901–1930, randomly sampled" (R00661 L943-945), verified
    by "With a constant climate … the densities remain relatively constant" (L1065-1066);
  - R00201's delta-change grid, 31 500 runs: total NPP R² 0.62–0.68, species NPP R² < 0.34;
  - R01728's baseline / warmer / warmer+drier factorial.
- **Data volume.** Skill saturates with about 100+ training sites (R00289) or about 25 training years (R00129).
  Diversity within a batch matters more than raw size (R01133).

**Gap here.**

- Volume is not the problem (2.55 × 10⁹ stem-years); independence and contrast are.
- No transient climate-contrast ensemble exists for the forward emulator.
- `vegemu`'s spin-up perturbation ensemble is the equilibrium-side analogue.

### 3.8 Speed-up, including training cost

**What the literature shows.**

- **Re-implementation need not be slow.** The only like-for-like re-implementation in the corpus (R00975, a JAX port
  of CLM-ml-v2) is ~2.2–2.4× *faster* than Fortran for a single run on CPU. That port has no per-individual loop.
- **The large factors come from emulating the expensive iterative solver or the whole step:**
  - a learned groundwater solver, 18.24× overall (R02497);
  - a polynomial emulator of LPJmL's iterative canopy energy balance, +3 % runtime (R00568);
  - an MLP of ecLand's step, ≈4800× (R00067, derived; hardware not matched).
- **Training cost is rarely counted:** only 16/115 studies include it.
- **No study reports an emulator slower than its target.**

**Gap here.**

- The emulator's cost is dominated by one iterative solve with a finite-difference derivative. That is the textbook
  candidate for an analytic or implicit derivative (R00975's implicit-function fix for exploding solver gradients)
  or a closed-form surrogate.
- At the original model's 500-patch production setting, the patch ensemble is 99.9 % of its cost and is a pure
  variance knob (ADR 0086). Fewer patches on the flux side is therefore a lever the literature does not even
  discuss.
- Derived estimate for a learned daily step: an aiLand-sized MLP (1.3 M weights) costs about 2.6 MFLOP per cell per
  step, i.e. ≈0.95 GFLOP per cell-year at a daily step, about 0.02–0.03 core-s. A smaller network (the Germany LSTM
  costs 2.4e-6 core-s) would sit well below the target.

---

## 4. Ranked proposals

Ranked by expected benefit relative to effort, given the owner's goal order: (1) faithful, especially the warming
response, on all cells; (2) fast enough for an ESM; (3) coupled. Each item says what to change, why (with the
evidence), how to test it, and the risk. "Effort" assumes the existing scripts.

### #1 — Make the warming response testable before choosing any architecture

**What.** Three runs of the original model, no emulator changes:

- **(a) A constant-climate control leg.** Continue from the 2019 restart over 2020–2100, with the 1990–2019 weather
  detrended and recycled, the same seeds, and CO2 constant as now. The original's own warming response is then
  *SSP370 − control*, not *SSP370 terminal − historic terminal*.
  - The emulator-side "frozen-climate" control (ADR 0178) already showed that the emulator's apparent response was
    mostly drift.
  - The original model's own 2020–2100 change has never been split into climate response and the model's continuing
    stand dynamics.
- **(b) Re-run the Germany 2071–2100 segments with the corrected humidity setting.** That window is the only place in
  the Germany data where the scenarios separate. This is the owner's decision (recorded in `lines/X/STATE.md`
  2026-10-01).
- **(c) A third and a fourth independent member**, each a separate spin-up (ADR 0041: a new seed under
  restart-from-file is a byte-identical clone). Do this at least on a stratified subset of ~1000 cells, and include
  the daily outputs, so the daily fluxes get a two-run spread for the first time.

**Why.**

- **R00661** isolates the response with exactly this control: "climate from years 1901–1930, randomly sampled"
  (L943-945), checked by "With a constant climate … the densities remain relatively constant" (L1065-1066).
- **R00289** shows that present-day agreement says nothing about the 2100 response.
- **R00167** uses an initial-condition ensemble range as the interpretation threshold.
- **This project:**
  - in Germany, every model arm and the "no difference" arm fail the contrast test, because the usable window has
    almost no contrast (`lines/X/STATE.md`, thirteenth session);
  - globally, two members disagree on the per-cell response sign in 18.7–42.2 % of cells.

**How to test.**

1. First a power analysis on the new runs: the signal-to-noise ratio of the original's own response
   (scenario − control) per biome and per stratum, with 3–4 members.
2. Then pre-register which aggregate response statistic has power (for example, signal-to-noise >2).
3. Score every existing arm on that statistic: the count forest, the hazard-as-rate arm, the Germany boosted trees,
   the LSTM and the set model.

**Effort and cost.**

- **Germany:** at ~0.014 core-s per patch per cell-year (ADR 0086), 250 patches × 9 067 cells × 30 yr is roughly
  ~270 core-h per leg, and ~6 000 core-h for all ~24 legs (derived).
- **Global control:** priced by ADR 0093's measurement (~35 000 core-h for two complete global members including
  spin-up); a transient-only control is a fraction of that.
- **Subset members:** 1000 cells × 1100 yr × 0.27 core-s ≈ 80 core-h per member (derived from the per-cell rate).

**Risk.**

- Binary consistency: in Germany, SSP245 ran a different binary.
- Re-runs must be pinned to one processor type to reproduce production (CLAUDE.md §3, 2026-10-06).
- The control's detrending choice changes what "response" means. Pre-register it.

### #2 — Train the annual dynamics on their own free runs

**What.** Three options, scored as separate arms with one variable each:

- **(a) Differentiable learner with a rollout loss.** Use a stand- or cell-level recurrent or MLP learner: either the
  Germany LSTM given a per-tree output stage, or a small network on the stand state.
  - Target the *increments*, scaled by their own standard deviation.
  - Use a combined one-step + rollout loss with a curriculum of rollout length (4 → 8 → 16 years), gradient clipping,
    and a lower learning rate in the long-rollout phase. An 81-year SSP370 horizon means 16-year windows already cover
    a fifth of deployment.
- **(b) Keep the tree ensembles but retrain them on states their own free runs visit, with targets from the
  original model.** The project already has the machinery: the harness that plugs the original's physics into the
  emulator loop can produce the original's one-year response from an emulator-visited state. This is "dataset
  aggregation"; it is not tested anywhere in the corpus (see §7).
- **(c) Calibrate a handful of bias/response parameters on the free run.** Add them on top of the one-step model, in
  the spirit of CLASH's trajectory fit or Deep-ED's signed zero-sum term. This targets the rectification
  (86.7 % vs 96.2 %) directly.

**Why.**

- **R00067:** "XGB specifically drifts at long lead times" (L1225), while the rollout-trained MLP did not.
- **R00593:** stable over a 4-year free run with "no upward trend" (L591-593) after a 4 → 8-step curriculum
  (L359-364).
- **R00661:** fitted "over the whole time frame (1900–2100)" (L997-1002).
- **R01133:** "enforce a zero-sum loss on the sum of the signed errors" (L561-562).
- **R00342 / R00911:** a learner trained on states the host produced, then run on states it changes, degrades
  because feedback "alters the fuel condition differently from the training set" (R00342 L741). This is the
  emulator's own failure shape.

**How to test.** Use the Germany development cells (held-out places and the held-out climate model) and the global
12/674-cell panels.

| | |
|---|---|
| Metrics | free-running area-weighted response ratio (today −0.226; target within the original's seed band of 1.0); validity horizon (today ~3 yr); per-cell pass rate at leads 5/20/40/80 yr |
| Nulls, always beside the score | persistence; the frozen-climate twin; the climate-blind twin; aiLand's within-training-period free run (a free run inside 2000–2019, so step bias is separated from extrapolation) |
| Baseline | today's free-running count forest and the Germany boosted trees |
| Pre-registered pass | response ratio inside the band on the #1 statistic, and no more than 1 pp loss of cells inside the level band |

**Risk.**

- Without #1/#3 a better rollout learner can still have no climate response: the Germany LSTM beats its frozen-climate
  twin by only 0.04–0.16 and collapses on resampled weather.
- A differentiable learner loses the forest's distributional output, so it needs a distributional head.
- Rollout training through a per-tree roster is expensive; at stand or cell level it is cheap.

### #3 — A designed transient climate-contrast ensemble, built from realistic patterns

**What.** About 1000 cells, stratified by biome and climate and spread over the ~161 independent 15° tiles, all
starting from the 2019 state, run over 2020–2100. Climate legs:

- the real SSP370 and SSP126;
- the #1 control;
- SSP370 change patterns from **both** available climate models, swapped between cells' baselines;
- SSP370 with its change pattern scaled ×0.5 and ×1.5, which keeps the realistic co-variation of temperature,
  humidity, radiation and precipitation.

Use ≥2 members and constant CO2. Train on *change relative to each cell's own baseline* (the R00013/R01025 design).
Hold out the ×1.5 amplitude and one climate model as the out-of-distribution test.

**Why.**

- **The identification limit:** 76.4 % of a cell's warming is predictable from its baseline climate (ADR 0311),
  because each place has one climate.
- **R00430:** purely stylised factorials fail ("too far removed from those expected in realistic settings",
  L1096-1100). Anchoring the perturbations on real GCM patterns is the corpus's implied remedy.
- **R00201 / R01728:** delta and factorial grids work for totals but not for composition. That is a warning for the
  trait axes, so score them separately.
- **`vegemu`** found its warming-response kill test passable only with a designed perturbation ensemble, on the
  equilibrium side.

**How to test.** Two training sets, one variable:

- (i) today's spatial-only data;
- (ii) today's data + the ensemble.

Metrics: the response ratio, the deattenuated response slopes per trait axis, and the fraction of cells inside the
band, on the held-out amplitude and the held-out climate model. Pre-register a minimum gain (for example, response
ratio moves ≥0.2 toward 1 on the held-out amplitude).

**Effort and cost.**

- Forcing writers exist (`scripts/build_hainich_response_forcing.py`; the header-driven `.clm` reader/writer).
- 1000 cells × 81 yr × ~8 legs × 2 members × 0.27 core-s ≈ 100 core-h at 25 patches; ≈1 300 core-h at 250 patches (derived; corrected 2026-10-08 from a mis-stated 1 200 core-h at 25 patches).

**Risk.**

- Scaling a change pattern can still produce physically odd combinations, e.g. vapour-pressure deficit. Scale in
  consistent variables (temperature and relative humidity, then convert).
- A subset re-run diverges from the global run after some years (ADR 0041). This is irrelevant here, because all
  legs share the subset, but never compare them to the global truth row by row.
- Per-cell composition responses may stay unlearnable (R00201).

### #4 — Land the solver speed fix that is already measured (quick win)

**What.** In the physics core's λ solve (`src/fdiff.jl:685-707`):

- replace the central finite-difference Newton derivative (3 photosynthesis calls per iteration) with an analytic
  derivative or an implicit-function derivative;
- wire in the precomputed temperature kinetics (two lines, measured to be worth ≈1.36×; ADR 0087);
- replace the fixed 25 iterations with a convergence test.

**Why.**

- **This project's measurements:** the solve is 82.7 % of the runtime, and 3 iterations give 4.10× at −0.03 % GPP
  (ADR 0084).
- **R00975** fixes exploding gradients through iterative solvers with the implicit-function theorem, which also makes
  the derivative exact.
- **R00568 and R02497:** the large wins come from treating the iterative solver specially.

**How to test.**

- The speed harness (`scripts/bench_speed_gate.jl`) at the 5 biome cells.
- GPP, ET and growth ratios against the original unchanged within ±0.5 %.
- The gradient gate (Enzyme vs finite differences).
- The full suite.
- Make the speed harness a required gate in the same step (a standing, unwired request).

**Risk.**

- It reaches at best parity with the original (~0.3 core-s per cell-year), not the ESM target.
- It is wasted effort if #7 replaces the per-tree daily physics.
- The ±2.1 % non-monotonicity in GPP across iteration counts means the current solution may not be converged.
  Resolve that first; it is also a fidelity question.

### #5 — A long-run stability gate, then an equilibrium initialiser

**What.**

- **(a) Gate.** Run the coupled emulator for 300–500 years under recycled climate. Require a stationary state (drift
  below a pre-registered fraction per century) that lies within the noise band of the original model's own spin-up
  equilibrium at those cells. Today biomass drifts 1.39–5.15× per century (ADR 0055).
- **(b) Initialiser for coupling.** Initialise the forward emulator with an equilibrium predictor (`vegemu`'s map is
  exactly this product) under the *coupled atmosphere's* climate, which is not GSWP3. Check it with the functional
  restart test: write the emulated state into a restart, let the original model continue, and measure the relaxation.

**Why.**

- **The review's requirement 1:** "combining them, so that a surrogate supplies an equilibrated initial state and a
  second emulator integrates it forward, is a natural next step".
- **R01211:** only PHASE's predicted restarts ran at all; baselines produced negative pools that crashed ELM.
- **R00211:** the poorer the prediction, the longer the re-run.
- **DifferLand** (R00383) penalises "spurious exponential growth and decay in carbon and water pools".
- An emulator with no fixed point cannot be initialised from any equilibrium map.

**How to test.** (a) is a run plus a stationarity statistic. For (b), compare the relaxation length and the end state
against a 1000-year spin-up of the original under the same climate, at the five biome cells and then a stratified
set.

**Risk.**

- Fixing (a) may need structural change (where is the drift coming from: physics growth bias? learned demography?)
  and may expose problems that 10-year coupled runs hide.
- (b) depends on a separate project whose own owner acceptance test currently fails.

### #6 — Separate the atmosphere-facing fluxes from the patch ensemble

**What.**

- Run the daily flux side (physics + energy) on one or a few representative patches per cell, whose canopy is the
  emulator's ensemble-mean stand.
- Let the learned demography supply the many-patch ensemble statistics: its expectation for the coupler, and its
  distribution for the trait output.

**Why.**

- **This project:**
  - the original's cost is exactly proportional to the patch count, and the patch ensemble is 99.9 % of its cost at
    500 patches;
  - atmosphere-facing fluxes converge within 1.7–6.6 % at a single patch, while vegetation carbon and establishment
    are 34–97 % off at low patch counts (ADR 0086). So the variance belongs to the demography, not to the fluxes.
- **Literature:**
  - LPJ-GUESS's 25-patch stochasticity forced its emulator to average to "500 replicate patches" (R00201);
  - iLand's emulator predicts transition probabilities and averages over replicates (R01728).
- **The determinism dividend** (predicting the expectation) is worth +2.9 to +14.4 pp of cells in band at zero cost
  (ADR 0093).

**How to test.**

- At the 5 biome cells and in Germany (250 patches): fluxes from 1/3/5 representative patches against the 25- and
  250-patch original (latent heat, GPP, NPP, sensible heat).
- The demography statistics from the emulator against the original's ensemble.
- Cost against the 500-patch original, quoted with the atmosphere resolution named.

**Risk.**

- The mean of the patch fluxes is not the flux of the mean canopy (a nonlinear canopy), largest in open or
  heterogeneous stands (Sahel). Measure that gap explicitly.
- Fire and disturbance statistics need the ensemble.

### #7 — Test a learned daily water–carbon flux model (the strategic bet for speed)

**What.**

- **Phase A, offline, weeks: test whether a learned model can reproduce the original's daily fluxes.**
  - Targets: daily GPP, NPP, transpiration, evaporation, interception and runoff.
  - State: soil water carried as a residual-updated state, with the bucket update done by construction so water
    closes exactly.
  - Inputs: daily forcing plus the annual stand state (LAI, crown cover, height and trait summaries from the tree
    table).
  - Data: the existing ~1 TB daily dataset.
  - Split: spatial blocks, plus the scenario hold-out.
- **Phase B, only if A passes:** put it in the coupled loop in place of the per-tree daily physics for the
  atmosphere-facing fluxes. Hand the per-tree growth partition to a per-tree NPP model of the kind line X is now
  building.
- Energy stays physics: there is no energy target in LPJmL-FIT (ADR 0310).

**Why.**

- **Speed:**
  - in the original, leaf gas exchange plus soil water are 51–69 % of runtime and the demography 0.4–1.1 % (ADR 0312).
    No single process replacement in the original reaches 2×. Only replacing the daily step as a whole changes the
    order of magnitude;
  - the emulator's per-tree daily step is 51× the original's.
- **Literature:**
  - aiLand's residual states with fluxes re-diagnosed each step keep flux error near-constant over 90 days (L585) and
    stay stable for 4 years (L591-593);
  - the ECMWF MLP runs ≈4800× faster than ecLand (R00067, derived).
- **Fidelity:** the physics core's remaining GPP error at the Mediterranean cell (1.61×) and its wrong warming
  response (8 % at Hainich, wrong sign at the Sahel) have no identified cause after an exhausted shortlist (ADR 0139).
  A model learned from the original's own daily output sidesteps an unexplained re-implementation residual.
- ADR 0310 already concluded "data exist; learnability untested".

**How to test (phase A).**

- Daily and annual skill against the original at the 5 biome cells, then on held-out spatial blocks and the SSP370
  leg, side by side with the physics core's skill on the same cells.
- The within-training-period free run of soil water (the aiLand test).
- Transfer error plotted against distance in climate-feature space (aiLand: r = 0.68 between the two; rainforest →
  desert transfer was 4.9× the in-biome error).
- Cost per cell-year on one core.

Pre-register these pass bars:

- annual GPP and ET within the band the physics core achieves at its four good cells (±5 %);
- the SSP370 change in GPP within the original's two-scenario response at ≥4 of 5 cells;
- ≤0.01 core-s per cell-year.

**Risk.**

- No two-run spread exists for the daily target until #1(c).
- Its error compounds with the annual state's error, which has never been estimated.
- Out-of-distribution warm climates.
- It gives up the interpretability of the differentiable physics. The physics core remains the oracle-faithful
  reference and the place where the energy closure lives.

### #8 — Close the coupler interface

**What.**

- Export what is already computed: reflected shortwave, upward longwave, runoff, snow.
- Feed real wind and pressure into the coupled driver (the energy line's open item E5).
- Add heterotrophic respiration with explicit litter and soil pools, plus fire, so the net CO2 flux is complete:
  either port the original's decomposition (4.6–6.6 % of the original's runtime, so affordable as physics) or learn
  the rates on explicit pools.

**Why.**

- **The review's requirement 2:** defining "the coupler interface as the emulation target, rather than a convenient
  subset of diagnostics, would make emulators comparable and pluggable".
- **R00755:** replacing a pool with a learned memory loses the carbon budget. Keep explicit pools.

**How to test.**

- Annual net CO2 flux against the original's flux identity at the 5 cells.
- The conservation gates.
- One coupled SpeedyWeather run.

**Risk.** Soil pools need spin-up (ties to #5). The impact on the acceptance criterion is low; this matters for
coupling.

### #9 — Calibrated uncertainty against independent runs

**What.**

- Make the learned demography's per-cell predictive distribution (counts, trait quantiles) calibrated against the
  spread between independent members. Score with rank histograms and interval coverage on 3–4 members (needs #1(c)).
- State the coupler policy: the ensemble expectation goes to the atmosphere; the distribution goes to the trait
  output.

**Why.**

- **R00157:** calibrated coverage of 94.8–95.6 % of nominal.
- **R00514:** a probabilistic emulator without a calibration check.
- The corpus gap: no emulator scores its spread against seed pairs.
- **This project:** the two-run spread is 16.6 % on stems in sparse cells, and 31.6 % on counts and 42.7 % on
  carbon in the sparsest stratum (<2 stems per patch).

**How to test.** Coverage of nominal 80/95 % intervals per stratum, and response-sign agreement against
member-to-member agreement.

**Risk.** Two members are not enough to calibrate anything. Do not start before #1(c).

### #10 — Before online science: a coupled self-test and a "no-learned-process" null

**What.**

- When any learned component goes online, first run the coupling self-test: train on the host's own output, couple
  it, and confirm the host's trajectory is reproduced, including secondary states that feed back.
- Score coupled runs against a configuration without the learned process (for example, static vegetation).

**Why.**

- **R00602:** the gain over the host flips sign between offline and online at several sites (FR-LBr GPP
  +0.02 → −0.23). Its self-test separates broken coupling machinery from a wrong learned function.
- **R02497:** a hybrid counts as acceptable only while it beats "physics without the process".

**Risk / timing.** Low priority until #7 or #4 makes the coupled model fast enough to run online at all (Terrarium's
soil alone costs ~10 h per simulated year today).

---

## 5. Where this project is already ahead of the published state of the art

1. **The target itself.**
   - The corpus has no emulator of tree-count, size or trait distributions, or of individual mortality, of any DGVM.
   - Composition outputs degrade most wherever they are tried (R00191: R² 1.0 → 0.75; R00201: species NPP R² < 0.34).
   - The trait copula and the exactly ported per-tree hazard have no precedent.
2. **Feedback-aware evaluation.**
   - The loop that plugs the original model's own physics into the emulator, and the error-isolation programme around
     it, measure the failure the corpus documents only after the fact: offline skill that collapses under feedback
     (R00342: 0.98 → 0.59).
   - No Tier A or B study trains or scores a learned vegetation component with the host's physics in the loop over
     decades under warming.
3. **Honesty apparatus.**
   - Seed noise floors, deattenuated response slopes, a persistence null quoted beside every one-step score,
     pre-registered nulls, and a quantified effective spatial sample (~161 tiles).
   - No Tier A study reports a one-step score next to a free-run score.
   - The corpus's most common test design is a random split (50 studies).
4. **Out-of-distribution testing.** Scenario hold-out and held-out climate models are standard here, while 0/7 Tier A
   and 0/19 Tier B studies test climates outside their training range.
5. **Conservation.**
   - By construction, and gated in continuous integration at 1e-12 (water, carbon) and ~1e-14 (energy).
   - No corpus study reports budget-closure residuals at that level; only 25/115 check conservation at all.
6. **Coupling interface.**
   - Sensible and latent heat, skin temperature, ground heat, albedo and roughness, together with carbon, in one
     system.
   - No Tier A emulator delivers energy fluxes together with carbon; aiLand delivers energy without carbon.
   - The energy closure is validated against flux towers, comparable to aiLand's observational fine-tuning.
7. **Cost accounting.**
   - Matched-hardware, marginal-rate, per-cell-year timing of both the emulator and the original, plus the
     original's cost law in patches.
   - The corpus reports speed inconsistently, rarely counts training (16/115) and never reports an emulator slower
     than its target. This project's slower-than-the-original number is evidence of honest measurement, not of
     unusual failure.
8. **Differentiability.**
   - A full daily physics core with gradients verified against finite differences through a 365-day rollout.
   - A learned correction trained through it (Hainich GPP 1.093 → 1.010).
   - This is comparable to the differentiable models in Tier B (R00383, R01005, R00975), and done for an
     individual-tree canopy.

---

## 6. What not to do

- **Do not invest further in one-step accuracy.** Persistence already scores R² 0.962 against the model's 0.982 and
  ties it on every count-response statistic (ADR 0113/0115).
- **Do not train only on stylised temperature/precipitation factorials** (R00430 L1096-1100). Anchor perturbations on
  real GCM patterns (#3).
- **Do not build a perturbed-parameter ensemble.** The target is one parameter set; parameter ensembles serve
  calibration, which is not this project's question.
- **Do not add CO2 inputs, varying-CO2 runs or a CO2 response.** This is a standing owner decision; the absence of a
  CO2 response is faithful to LPJmL-FIT's constant-CO2 future runs.
- **Do not adopt a diffusion or other probabilistic architecture before a calibration test exists** (#9). The one
  published case (R00514) never checks calibration.
- **Do not let a learned recurrent state replace an explicit carbon or water pool** (R00755). Learn rates; keep
  pools.
- **Do not quote any speed-up** without the matched-hardware, per-cell-year number and the atmosphere resolution it is
  measured against, or any fidelity claim on five cells without saying "5 of 54 020".

---

## 7. Papers outside the corpus worth retrieving

Cited by corpus papers (titles/DOIs as cited there; not looked up):

- Keisler, R. (2022). Forecasting global weather with graph neural networks. arXiv:2202.07575. *Source of the
  increment scaling and rollout loss used by R00067/R00593.*
- Kochkov, D. et al. (2024). Neural general circulation models for weather and climate. *Nature* 632:1060–1066,
  doi:10.1038/s41586-024-07744-y. *R00975: online training is "the only configuration shown to yield stable hybrid
  climate integrations".*
- Brenowitz, N. D. et al. (2020). Interpreting and stabilizing machine-learning parametrizations of convection.
  arXiv:2011.03081. *Offline vs coupled skill.*
- Beucler, T. et al. (2021). Enforcing analytic constraints in neural networks emulating physical systems. *Phys.
  Rev. Lett.* 126, 098302, doi:10.1103/PhysRevLett.126.098302.
- Franke, J. A. et al. (2020). The GGCMI Phase 2 emulators. *GMD* 13:3995, doi:10.5194/gmd-13-3995-2020. *The
  factorial-emulator template R00430 found not to transfer.*
- Rammer, W. & Seidl, R. (2019). A scalable model of vegetation transitions using deep neural networks. *Methods
  Ecol. Evol.* 10:879–890. *Basis of the only distributional emulator of an individual-based model (R01728).*
- Fang, J. & Gentine, P. (2024). Exploring optimal complexity for water stress representation in terrestrial carbon
  models. *JAMES* 16, e2024MS004308, doi:10.1029/2024ms004308. *Source of DifferLand's penalty on pool drift.*
- Hoedt, P.-J. et al. (2021). MC-LSTM: Mass-conserving LSTM. ICML. *A recurrent network that conserves mass by
  construction; relevant if #2(a) or #7 use recurrence.*
- Blondel, M. et al. (2022). Efficient and modular implicit differentiation. NeurIPS 35. *For #4.*
- Davenport, E. H. et al. (2026). JCM v1.0: a differentiable, intermediate-complexity atmospheric model. EGUsphere,
  doi:10.5194/egusphere-2025-6266. *SPEEDY physics in JAX, the closest relative of a SpeedyWeather coupling.*
- Sun, Y. et al. (2023). Machine learning for accelerating process-based computation of land biogeochemical cycles.
  *Global Change Biology* 29(11):3221–3234. *The closest precedent for ML-accelerated spin-up (#5).*
- Ma, L. et al. (2022). Global evaluation of the Ecosystem Demography model (ED v3.0). *GMD* 15:1971–1994. *The ED
  version both ED emulators target.*
- The FINN forest gap model with neural growth, mortality and regeneration (screened out of the review as record
  R00686 only because its target is not a DGVM). *The closest published learned demography.*

Not cited in the corpus; my own suggestion for #2(b):

- Ross, S., Gordon, G. & Bagnell, J. A. (2011). A reduction of imitation learning and structured prediction to
  no-regret online learning (DAgger). AISTATS.
- Venkatraman, A., Hebert, M. & Bagnell, J. A. (2015). Improving multi-step prediction of learned time series models
  ("Data as Demonstrator"). AAAI. *Retrains a one-step model on its own rollout states. It is exactly the remedy for
  a tree ensemble that cannot take a rollout loss.*
