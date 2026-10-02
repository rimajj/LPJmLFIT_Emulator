# Germany emulator, structured track (B-STRUCT): growth heads, response gates, recruitment kernel

Line X exploration, 2026-10-02. Items B1, B2 and B3 of the structured design: only the climate-to-growth map is
learned; deaths, the bad-growth counter, temperature and water mortality, establishment eligibility and recruit-trait
inheritance are the original model's own rules (`scripts/explore_de_sh_rules.py`). All numbers are on the 907
development cells (every tenth cell of Germany), 1985-2044 only (owner decision 2026-10-01). Everything here is
**teacher-forced**: each prediction is made from the original model's own tree state of the previous year. None of it
is a free-running result. The rollout stepper and the re-calibration of the persistence term are later steps.

Split: trained on MPI-ESM1-2-HR seed 1 (Historical 1985-2013 transitions, plus ssp126 and ssp370 2014-2043), dev cells
of block folds 1-4 (722 cells, 41 blocks), with a stratified 3 % tree sample (6.7 M rows; rare negative-growth and
water-stress rows up to 15 %). Held out: fold 5 (185 cells, 11 blocks), every ACCESS-CM2 member (a climate model it
never saw), MPI ssp245 and every seed-2 member.

## B1 — growth heads (`scripts/explore_de_struct_heads.py`, report `/p/tmp/jamirp/X_de/_reports/r2_B1.json`)

Eleven LightGBM models with piecewise-linear leaves. Inputs: the tree's type, traits, size, age, bad-growth counter,
patch crowding, grass, soil type, and the climate of this and the next year (monthly temperature and precipitation,
growing-degree days, summer water balance, summer vapour-pressure deficit, hot days, radiation, the tree type's cold-
stress days), each as a level and as an anomaly from the same climate model's 1985-2014 mean. Deliberately absent:
last year's NPP, transpiration, water scalar, growth efficiency and hazards (the copy-last-year shortcut).

Heads: growth efficiency next year (its sign, its mean, and the two sign-conditional magnitudes used for sampling),
water stress (occurs at all / how much), and five size changes given growth efficiency (log biomass, log vegetation
carbon, leaf-area index change, log crown cover, log rooting depth). Height comes from the rule library's allometry.

Pre-registered null expectation (written before the nulls were run): with last year's and this year's value of equal
mean and variance, copy-last-value R² = 2·sqrt(persistence R²) − 1, so copy ≤ persistence always. Measured: the
absolute biomass-change copy null sits on that bound to within 0.01 in every set (e.g. ACCESS Historical: persistence
0.892, copy 0.890, bound 0.889), and round 1's ranges are reproduced (persistence 0.79-0.90, copy 0.78-0.89 here).

Held-out skill (range over 29 evaluation sets: fold-5 cells of the three training members, all dev cells of the 13
other members; model R² beside persistence / copy-last on the same rows):

| quantity | model | persistence | copy-last |
|---|---|---|---|
| growth efficiency next year | 0.93-0.96 | 0.67-0.77 | 0.64-0.76 |
| its sign (negative = counter step) | AUC 0.975-0.991, accuracy 0.95-0.97 | — | sign accuracy 0.89-0.94 |
| biomass change (round-1 basis), via predicted growth efficiency | 0.96-0.99 | 0.79-0.90 | 0.78-0.89 |
| log biomass change, via predicted growth efficiency | 0.95-0.97 | 0.48-0.60 | 0.34-0.52 |
| log vegetation-carbon change | 0.96-0.98 | 0.81-0.85 | 0.78-0.83 |
| leaf-area change | 0.76-0.82 | 0.02-0.19 | −0.68 to −0.11 |
| log crown-cover change | 0.90-0.94 | 0.40-0.53 | 0.27-0.45 |
| log rooting-depth change | 0.99 | 0.24-0.44 | −0.06 to 0.28 |
| height change (allometry on predicted biomass) | 0.66-0.75 | (round 1: 0.09-0.41) | |
| water stress: occurs at all | AUC 0.99 | — | AUC 0.56-0.67 |
| water stress: amount | **fails**: R² −4.3 to 0.38 raw; log amount where present 0.07 (ACCESS Historical) to 0.55 (MPI ssp370) | 0.00-0.09 | negative |

ACCESS-CM2 (unseen climate model) is 0.02-0.03 below the MPI fold-5 numbers for growth efficiency; held-out cells of the
training climate model lose nothing.

Persistence (latent residual): out-of-fold normal scores, AR(1) per tree type × height class (5 classes) from
3.83 M consecutive-year pairs. Overall: growth efficiency rho = 0.63, water stress 0.53 (estimated from joint
occurrence, because a zero carries no residual), size changes −0.19 to 0.26 (given growth efficiency, size residuals
barely persist). Innovation correlation matrix -> Cholesky factor per class.

Defect found and fixed: the piecewise-linear leaves extrapolate; on unseen climate the log water-stress mean reached
e^28. All regression means are now clipped to their training-target range (`ranges` stage). The out-of-fold residual
tables were built before the clip; the clip only affects extreme rows.

## B2 — response gates (`scripts/explore_de_struct_gates.py`, report `_reports/r2_B2.json`)

* Germany-mean yearly share of trees with negative growth next year, ACCESS-CM2 Historical seed 1, 29 years, all dev
  cells: r = 0.860 (gate >= 0.8, **pass**). Mean predicted share 0.122 vs 0.111 observed. The two original-model seeds
  agree at r = 0.9995 on this series, so it is almost entirely climate-driven and 0.86 is well below what is possible.
  ACCESS ssp126 alone: r = 0.748.
* Climate block, within-cell year-to-year anomalies of the cell-year mean growth efficiency: ACCESS Historical (all dev
  cells, 26 303 cell-years, ~133 sampled trees each) R² 0.81 with the real climate vs −0.69 with each cell's years
  shuffled -> partial R² 0.89; MPI fold-5 0.99 vs −0.74 -> 0.99. Share-negative: partial 0.75 / 0.97.
* Hottest 10 % of training cell-years (annual mean > 11.08 °C) held out against a random 10 % control: error ratio
  hot / control 1.23 for the sign (Brier), 2.06 for mean growth efficiency (1 − R² ratio 1.72), bias +1.2 units in the
  hot set. Skill survives (R² 0.94 hot vs 0.96 control) but degrades at the warm edge.
* Scenario response on fold-5 cells, ssp370 minus ssp126, same cell-year, 2015-2044 (5 550 cell-years). Where the
  observed seed-1 difference exceeds its two-seed spread (68-74 % of cell-years), the predicted difference has the
  observed sign in: ACCESS-CM2 86 % (share-negative) and 90 % (mean growth efficiency); MPI 98 % / 99 %. With the SAME
  trees under the two climates (state differences removed: the learned climate response alone): ACCESS 82 % / 82 %,
  MPI 91 % / 91 %. Caveat: in 2015-2044 the two scenarios differ only by weather (no forced contrast yet), so this
  tests the year-to-year weather response, not warming. One miss: ACCESS's fold-5 mean difference in growth efficiency
  over all cell-years is +0.70 observed and −0.81 predicted (per-cell 30-year signs still agree on 89 % of determined
  cells).

## B3 — recruitment kernel (`scripts/explore_de_struct_kernel.py`, report `_reports/r2_B3.json`)

Proposal generator on the rule library: inheritance with probability 4/(4 + number of eligible tree types), parent
drawn from the cell's seed bank weighted by its years in the bank, traits by the inheritance rule with the binary of
the establishment year; otherwise a uniform draw over eligible types. Longevity from the leaf-area corridor, root
parameter from rooting depth. Truth parents = bank rebuilt from the original model's printed trees; it equals the
2014 seed bank of the shared initial states exactly (62 250 015 tree-years, 0 of 4 531 cell x type groups differ).
Basis: 4 members (MPI/ACCESS ssp370 = Dec-2025 build, MPI/ACCESS ssp245 = Feb-2026 build), recruits established
2015-2034 and printed by 2044, 0.74-0.84 M per member.

All five gates pass. Wood density / rooting depth outside the own type's interval (pooled, matched to each observed
recruit's cell-year and type) are within max(25 %, 3 SE), **but the kernel is 20-25 % low on all 8 comparisons**
(Dec-2025 wood density 0.033/0.043 vs 0.044/0.056 observed; Feb-2026 0.014/0.020 vs 0.018/0.026), i.e. at the edge of
the tolerance; leaf-area and water-scalar traits are never outside, on both sides. Longevity–leaf-area correlation is
inside −0.98…−0.66 for types 1-5 (kernel −0.78 to −0.92, visible recruits −0.85 to −0.91; corridor residual spread
0.88 vs 0.86-0.89); larch, never visible in Germany, has −0.54 (not gated). Root parameter exact. Eligibility shares
equal the round-1 probe exactly. As expected from the selection on the way to 5 m: the kernel proposes 52-59 % beech
and 4-8 % larch, while visible recruits are 87 % beech and 0 % larch; per-type out-of-interval shares fail for types
1, 2 and 5. A later acceptance step must learn that filter.

## API a stepper calls

```python
import explore_de_struct_heads as hd, explore_de_struct_kernel as kn
H = hd.StructHeads.load("DEV-A")
feat = H.features(frame)       # frame: tree state + patch context + gcm, Cell, Type + H.climate_columns() (<lev>_y, _y1)
X = H.X(feat); s = hd.size_class(Height)
z = H.stationary(Type, s, normals)              # recruits / 1985 start;  z0 = H.residual_z(X, Type, s, G, W, sizes)
draw = H.sample(X, z, Type, s)                  # -> G, W, dlagb, dlvegc, dlai, dlfpc, dld95 (+ p_gneg, q_w)
z = H.ar_step(z, Type, s, normals)              # next year's latent
K = kn.RecruitKernel(); out = K.propose(K.bank_from_frame(bank_of_cell), n, elig_row, build, rng)
```

Check (`scripts/explore_de_struct_apicheck.py`): `residual_z(sample(z))` returns z to 1e-14; one sampled year
reproduces the share of negative growth (0.126 vs 0.130), water-stress occurrence (0.022 vs 0.024) and mean log
biomass change (0.073 vs 0.076) on ACCESS ssp370. Cost: 1.5 ms of CPU per tree-year for the eleven ~1 500-tree models,
i.e. ~3 core-seconds per 250-patch cell-year at ~2 000 trees. Compare at the SAME patch count: the original costs
12.4 core-s per cell-year at 250 patches (Germany production run), so this is ~4x cheaper there; the original's
0.29-0.38 core-s (five biome sites) is at 25 patches, where this design would cost ~0.3 if it scales with tree count —
about EQUAL to the original, i.e. no speed gain. (Corrected by the parent session: the first draft compared the
250-patch cost with the 25-patch original and called it "10x slower".) Either way a large speed problem for the ESM
goal; fewer or shallower trees, or distillation, would be the first fix. Measured on the code path only, not with the
SH10 harness.

## What failed or is open

* Water-stress amount is not predicted on the raw scale (only its occurrence is).
* Per-type visible recruit traits miss (selection); the pooled out-of-interval shares are 20-25 % low.
* Warm-edge degradation (MSE x2 for the hottest decile).
* The heads are slow (see above); most models stopped at the 1 500-round cap, still improving.
* The persistence terms are estimated one step ahead from out-of-fold residuals; free-run re-calibration is not done.
* Grass cover is an input but no head updates it; a stepper must carry it (or freeze it) explicitly.

## B5 — the free-running stepper, first runs (`scripts/explore_de_struct_stepper.py`, report `_reports/r2_B5.json`)

**What it is.** An engine stepper that, each year and for every tree, builds the B1 inputs from the emulator's own
state (never from the original model's), samples next year's growth efficiency, water stress and size changes with
a per-tree persistent random term, applies the original model's death rules (bad-growth counter, the four hazards,
the 5-year kill, the bioclimatic survival test, then fire with the learned patch rate), hides trees that fall below
the 5 m print cut, and adds recruits: how many per patch from the learned patch head, which type and traits from
the original model's inheritance rule (B3, no acceptance filter yet), entry height/age from the learned entry
heads, entry biomass from the inverse height allometry, and the other entry sizes from a small per-type log-linear
fit on training recruits (stage `entry`; R² 0.99 vegetation carbon, 0.77-0.90 leaf area, 0.84-0.92 crown cover,
0.49-0.64 rooting depth). Grass is carried unchanged (no head updates it). Arms: main = no acceptance filter;
"no persistence" = the random term redrawn every year (same spread, no year-to-year memory); "climate-blind" = the
same code run on the engine's frozen-climatology provider (`--clim frozen_mean`: each cell's own 1985-2014 mean
climate, anomalies zero) — no stepper hack. The persistence parameters are the uncalibrated out-of-fold ones; an
optional calibration file (`struct/cal/<split>.json`) is read if it exists and was NOT created.

**Smoke (20 dev cells, MPI-ESM1-2-HR seed 1, ssp370, 1985-2044, 1 180 cell-years).** No NaN anywhere; living stem
count 0.85-1.00 of the original's every year (0.90 in 2044); death rate 3.3 %/yr vs 3.1 %; share of living trees
with a bad-growth counter ≥ 1: 11.7-12.1 % (target 9.6-13.7 %, in range); hard kills (hazard = 1, here almost all
the 5-year counter kill) 1.06 %/tree-yr (target 1.1-1.4 %, just below). The no-persistence arm: 0.97 %/tree-yr,
12.2 %, count ratio 0.86-1.00 — persistence barely matters for these rates. Cost 3.42 core-s per cell-year
(process CPU over 16 threads; 0.23 s wall per cell-year), vs 0.121 for the lookup (28x) and ~12 for the original at
the same 250 patches.

**Free runs (ACCESS-CM2 = the climate model never trained on, seed 1, 907 dev cells, 1985 start, three scenario legs
forked at 2014, to 2044; 107 933 cell-years each; 10 chunks x ~34 min on 16 cores; 2.86 core-s per cell-year).**
Germany-wide (dev cells): living stems 0.83-1.00 of the original, 0.84-0.88 in 2044; death rate 3.59 %/yr vs 3.44 %,
year-to-year correlation with the original's 0.76-0.79 (climate-blind twin: 0.20-0.25, so the yearly death signal is
the climate response); new stems 3.67 % of living per year vs 3.20 % (+14 %); bad-growth prevalence 10.4 %; hard
kills 1.42 %/tree-yr (in the target band at Germany scale, unlike the 20-cell smoke).

**Scored on the 185 held-out fold-5 cells (the only evidence), full conjunctive panel, other-seed ceiling beside:**
1985-2014 history 0 % of cells pass (ceiling 95 %; lookup 86 %); 2015-2044 every scenario 0 % (ceiling 92-93 %;
lookup 6-10 %). The per-cell scenario-contrast row (ssp370 − ssp126) gives 56 % vs a 96 % ceiling, but the
climate-blind twin scores 99 % on it — that row has no power and is not evidence. The block-scale primary response
gate fails for every arm including the lookup (ceiling 9 %). **Why it fails (28 of 88 quantities):** (1) trees grow
too fast in free run — median above-ground biomass 1.4x the original's in 1985-2014 and ~2x in 2015-2044, median
height +7 %, stem density 17 % low by 2015-2044; (2) without the acceptance filter the kernel's type mix and trait
tails reach the visible stand: beech share 0.81 vs 0.93, boreal needle-leaf 5 % vs 0.9 %, low-SLA / long-leaf-life
tails (5 % SLA quantile 0.0145 vs 0.0243; 95 % leaf longevity 2.2 vs 1.1 yr). Both were expected to be the
weak points (acceptance not built; growth persistence not calibrated in free run); the size of the growth drift was
not known before. Teacher-forced skill (B1) did not carry over to the free run.
