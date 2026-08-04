---
name: emulator-validation-figures
description: Produce the reproducible validation-figure set that PROVES how well the global Component-S emulator reproduces LPJmL-FIT — global maps (observed / predicted / bias tree density), per-row + per-cell prediction scatter, count-distribution comparison, and skill-by-latitude / skill-by-gdd5 breakdowns — from HONEST K-fold-by-cell out-of-sample predictions. Use whenever the historic OR future (SSP370) emulator is (re)trained, its features/DRF change, or you need publication-style proof-of-skill figures. Also the recruit-trait COPULA trait-distribution figures (ADR 0025): per-axis pooled marginals, per-cell median scatter, per-cell KS maps (figs 09-11 + metrics_traits.txt), gated on COPULA_OUT, from scripts/eval_slow_copula.jl K-fold-by-cell OOS. Names: scripts/eval_slow_drf.jl, scripts/eval_slow_copula.jl, scripts/plot_slow_emulator_validation.py, scripts/run_global_slow_copula.sh, preds_oos.f64, pred_<axis>.f64, COPULA_OUT, figures/emulator_validation/<scenario>/, cell 42490, grid.nc cellid orderA. Complements slow-drf-pipeline (which TRAINS the DRF + copula).
---

# emulator-validation-figures — reproducible proof-of-skill figures for the global Component-S emulator

Run this AFTER the global DRF is trained (see the `slow-drf-pipeline` skill). It shows how well the emulator
reproduces LPJmL-FIT tree density (`n_living` per patch) globally, using **out-of-sample** predictions so the
figures are genuine generalization, not in-sample fit. Rerun it verbatim whenever the emulator changes — the
whole thing is deterministic and parameterized by `SCENARIO`.

## THE one command for a whole generation (`scripts/run_slow_validation_figures.sh`)

Once the count `preds_oos.f64` and the copula `pred_<axis>.f64` exist for a generation, the entire figure set
across all three scenarios plus one self-contained HTML report is ONE submission:
```bash
VERSION=t8 scripts/run_slow_validation_figures.sh                      # historic + ssp370 + pooled + report
VERSION=t8 DEPENDENCY=afterany:<copula jids> scripts/run_slow_validation_figures.sh   # chain it
VERSION=t8 SCENARIOS=historic SUBMIT=no scripts/run_slow_validation_figures.sh        # inspect the jcf
```
The knowledge it carries is the **input-dir mapping**, which does not follow one pattern and was re-derived by
hand every time: `historic`/`ssp370` read `slow_runtime_<scen>_<VER>` + `slow_copula_<scen>_<VER>`, while
`pooled` reads **`slow_count_pooled_w20_<VER>`** + `slow_copula_pooled_w20_<VER>` (ADR 0026's transient pair).
It also SKIPS a scenario loudly instead of emitting a half-empty figure dir, and it knows the trap that
`eval_slow_copula.jl` writes every `pred_<axis>.f64` **only after the last fold**, so a killed eval leaves a
complete-looking table dir with no predictions — hence the explicit `pred_SLA.f64` precondition check.
Use `DEPENDENCY=afterany:` (not `afterok:`) when chaining several scenarios' jobs: one failed scenario then
still lets the others' figures be produced, and the per-scenario guards report the gap.

**VERIFY a generated report by stripping the images, not by eyeballing it.** The page is ~10 MB of which
~21 KB is content, so nothing is readable end-to-end and a markup bug hides perfectly. Strip the payloads and
inspect what is left — this found a caption containing a bare `<20 stems`, which a browser parses as an open
tag and which silently swallows the rest of that caption:
```bash
python3 - report.html <<'EOF'
import re, sys
s = re.sub(r'src="data:image/png;base64,[^"]+"', 'src="[PNG]"', open(sys.argv[1], encoding="utf-8").read())
print("tags:", sorted(set(re.findall(r'<(\w+)', s))))          # a NUMERIC "tag" == an unescaped `<`
print("external refs?", bool(re.search(r'https?://|@import|<script|<iframe|<link', s)))
print(s[:2000])
EOF
```
A numeric entry in the tag list is the tell. The second check matters because the page must stay
self-contained (the Artifact CSP blocks every external host, so a stray CDN reference fails silently).

**The HTML report — `scripts/build_slow_validation_report.py`.** Figure dirs are git-ignored and live only on
the cluster, so the report inlines every PNG as a data URI into ONE page (`report_<VER>.html`) that can be read
anywhere and published directly as an Artifact. It is a REPORTER: every number is read verbatim from the
`metrics*.txt` files, so it can never disagree with the figures.

## One command (disconnect-proof, SLURM)

The two steps below run heavy work → submit them as ONE SLURM job (survives a dropped connection; the
user's link is unstable — see [[slurm-only-unstable-connection]]). Template (exclude the known flaky node):
```bash
export SBATCH_EXCLUDE=csn14c163                       # [[slurm-flaky-node-exit53]]
TABLE=/p/tmp/jamirp/emulator_global/slow_runtime_<scen>   # <scen> = historic | ssp370
# jcf body (see JOURNAL 2026-07-24 for the exact heredoc used for the historic run, job 1581897):
#   OUT=$TABLE KFOLDS=5 NTREES=150 MAX_DEPTH=16 MIN_LEAF=20 SUBSAMPLE=200000 julia scripts/eval_slow_drf.jl
#   OUT=$TABLE SCENARIO=<scen> <py311> scripts/plot_slow_emulator_validation.py
```
~20–25 min (5 forest fits + plotting). Julia here is plain (DRF is zero-dep pure-Base, no `--project`). The
plot step is light and can also run on the login node once `preds_oos.f64` exists.

## Step 1 — honest OUT-OF-SAMPLE predictions (`scripts/eval_slow_drf.jl`)

K-fold-**by-cell** CV (default 5): each cell is predicted by a forest that never trained on it, so a global
map is real generalization (a row-holdout would leak a cell into train+test and read optimistically — same
lesson as the `HOLDOUT_FRAC` eval in `slow-drf-pipeline`). Reads `OUT/{X.f64,y.f64,cells.i64,manifest.txt}`,
writes `OUT/preds_oos.f64` (per-row OOS prediction, aligned to X rows). **Hyperparameters MUST match the
production train** (`slow-drf-pipeline` step 2 / `run_global_slow_training.sh` defaults) or the eval forest
differs from the shipped model. Requires `cells.i64` — the builder emits it; if absent, rebuild the table.

## Step 2 — figures (`scripts/plot_slow_emulator_validation.py`)

Reads `OUT/{y.f64,preds_oos.f64,cells.i64,cell_meta.parquet}` + `grid.nc` (cellid[lat,lon] = orderA Cell
index, VERIFIED `cellid[51.25,10.25]==42490` Hainich; never flatten-order — the 42490-vs-28008 trap). Values
are averaged over patches+years → one number per cell for the maps. Writes to
`figures/emulator_validation/<scenario>/` (git-ignored — regenerable, avoids binary churn):
- `01_map_observed / 02_map_predicted / 03_map_bias` — global 280×720 `pcolormesh` (no cartopy — it's flaky
  here; plain matplotlib on the regular grid). Bias uses a symmetric diverging scale.
- `04_scatter_density` (per-row hexbin, log) · `05_scatter_percell` (per-cell means) — with R²/RMSE.
- `06_distribution` — observed vs predicted count histogram (log-y).
- `07_error_by_latitude` · `08_error_by_gdd5` — RMSE + bias vs latitude / growing-degree-days (where it
  works / fails).
- `metrics.txt` — OOS per-row R², RMSE, per-cell-mean R², bias, n. **This is the headline proof number.**

## Trait-distribution figures — the recruit-trait copula (ADR 0025)

The count DRF above predicts `n_living`; the **recruit-trait copula** predicts the within-cell TRAIT
distribution (`{SLA, Wooddens, D95max, minwscal}`). Its OOS evaluator is `scripts/eval_slow_copula.jl`
(K-fold-BY-CELL, one copula draw per surviving stem per axis → `pred_<axis>.f64`); build+eval+train the
global copula in ONE SLURM job via `scripts/run_global_slow_copula.sh` (see `slow-drf-pipeline` step 4).
**Global-scale perf/monitoring (bit me):** the OOS quantile-draw loop dominates cost (~naxes·kfolds·n forest
traversals — hundreds of millions at the 133M-stem global table); it is `Threads.@threads`-parallel over
`JULIA_NUM_THREADS` (the orchestrator exports 32) and bit-identical to serial (per-(row,axis) RNG seed). If
the log looks frozen mid-eval, that's Julia BLOCK-BUFFERING the file, NOT a hang — confirm live compute with
`sstat -j <jobid>.batch --format=AveCPU,MaxRSS` (AveCPU≈wall ⇒ burning CPU). `pred_<axis>.f64` are written
only AFTER all folds finish, so a mid-run timeout yields NOTHING — size the wall to the parallel (not serial)
runtime, and keep the per-fold `flush(stdout)`.
Then set **`COPULA_OUT=<copula table dir>`** when running `plot_slow_emulator_validation.py` (alongside the
usual count `OUT=`) and it ALSO emits:
- `09_trait_marginals` — per-axis pooled observed-vs-OOS-predicted histograms (+ nqrmse, KS).
- `10_trait_percell_median` — per-axis per-cell predicted-vs-observed median (DENSITY hexbin + per-cell
  Pearson r / Spearman ρ in the title). **READ IT RIGHT (bit the owner):** 38k cells saturate a plain
  scatter and hide the diagonal → it LOOKS "totally off" when it isn't. The honest per-cell-median skill is
  axis-dependent — GLOBAL historic on the emulator's own basis: SLA **0.866**, minwscal 0.793, D95max 0.771,
  **Wooddens 0.567 (weak)**. *(The older 0.87/0.78/0.74/0.52 figures are the same run scored on a `Type<=6`
  cell set — see the noise-floor section: always state the population.)* **Quote the dispersion too:** the
  predicted per-cell spread is only **0.55×** observed for Wooddens (a second seed gives 1.00) ⇒ it regresses
  cells toward the global mean; a correlation alone hides that. Root cause is structural, not a bug: the copula
  conditions on flux+boundary and DELIBERATELY excludes stand-state (`live_flux_cond`, ADR 0025), and FIT draws
  traits from **per-PFT** intervals, so a per-cell trait median is a *composition* statistic that neither a
  composition covariate nor a per-PFT marginal is available to explain. Fixes, in order: **ADR 0031** (train on
  all seven tree PFTs — today's tables drop ids 0/6, so the tropics are absent) → per-PFT/mixture marginal (S3)
  → richer conditioning (S2; a frozen-`live_flux_cond`-contract change + global re-fit + ADR; degenerate at
  single-cell Hainich).
- `11_trait_ks_map` — per-axis per-cell KS map (spatial where the marginal is reproduced well/poorly).
- `metrics_traits.txt` — per-axis pooled nqrmse + pooled KS + median-per-cell KS + **median_percell_r /
  median_percell_spearman** (the paired per-cell-median skill — the honest per-cell number; pooled KS alone
  can look great while per-cell medians regress to the mean, see fig 10). **The headline trait proof numbers.** KS + 1-Wasserstein are dependency-light (no scipy). Only SLA/Wooddens feed dynamics;
  D95max/minwscal are sample+validate-only. (13-cell dev check: OOS pooled KS SLA 0.044, Wooddens 0.017,
  D95max 0.029, minwscal 0.021. GLOBAL historic OOS nqrmse SLA 0.016 / Wd 0.022 / D95max 0.028 / minwscal
  0.038 **on the pre-ADR-0031 `tree5` population**; the `tree7` retrain reads SLA 0.006 / Wd 0.008 /
  D95max 0.008 / minwscal 0.008; GLOBAL pooled+transient nqrmse 0.010-0.020, `tree7` pooled 0.004-0.016.)

## STAND BIOMASS + SIZE — figures 12/13 and `metrics_biomass.txt` (ADR 0036)

The opt-in `STRUCT_AXES=agb,Height` copula axes (see the `slow-drf-pipeline` skill) make the biomass and size
distributions first-class in this figure set. Two things appear:
- **figs 09/10/11 grow from 4 to 6 panels**, the two extra tagged **`[diag]`** in every panel title and given
  `kind=struct` in `metrics_traits.txt`. The panel grid is sized from the axis count — it was a hard-coded 2x2
  that would have silently dropped any axis past the fourth.
- **figs 12/13 + `metrics_biomass.txt`** — stand biomass, composed from the emulator's two halves, both OOS:
  `pred = mean_OOS(n_living) x mean_OOS(per-stem agb)` per cell, against the C's own per-patch `sum(agb)`
  (X column `agb`, index read from the manifest's `colnames`, never hard-coded).

**Read `basis_ratio` before quoting a biomass number.** `mean(N) x mean(A)` is not identically
`mean(N x A)` — they differ by the within-cell covariance of stem count and mean stem size, which is negative
(denser patches hold smaller trees). `basis_ratio = median(obs_prod / true_stand)` MEASURES that definitional
gap on the observed side instead of assuming it away; `[VERIFIED 2026-07-29]` it is **0.992**, i.e. the identity
holds to 0.8 %, so the composite is a fidelity claim rather than a diagnostic. If a future run reports
`basis_ok no`, the report page says so and the number becomes a diagnostic — do not quote it as fidelity.
- Report **both** `percell_r2` (linear) and `percell_r2_log10`. Stand AGB spans 3+ decades across cells, so the
  linear R² is dominated by the highest-biomass cells and is nearly blind to the semi-arid/boreal tail that is
  most of the land area.
- **For a heavy-tailed axis, read KS, not `nqrmse`.** Per-stem `agb` reads `nqrmse ≈ 0.68` while `KS ≈ 0.011`
  and the two histograms are visually indistinguishable — the IQR-normalized quantile RMSE is dominated by its
  q95 term when q95/IQR is of order 10. The panel title now says so itself. Same family as the warning below.
- Figures 09/10/12 switch to LOG axes automatically when an axis is heavy-tailed (detected as
  `p99.5/median > 20`), because on a linear axis 99 % of the mass lands in the first bin and BOTH curves look
  like one spike — which would hide a real mismatch rather than reveal it.

**⚠ `nqrmse` is IQR-NORMALIZED — never quote a before/after RATIO without checking the normalizer moved.**
`eval_slow_copula.jl:104`: `nqrmse = RMSE(q05..q95) / IQR(observed)` with `IQR = q75 − q25`. So **any change to
the POPULATION changes the denominator**, and the headline ratio misleads in *both* directions. Measured across
the ADR-0031 `tree5 → tree7` widening (`[VERIFIED 2026-07-28]`):
| axis | nqrmse | headline | IQR × | **real gain** (raw quantile RMSE) |
|---|---|---|---|---|
| SLA | 0.016 → 0.006 | 2.67× | 0.89× | **2.99×** — headline UNDERstates it |
| Wooddens | 0.022 → 0.008 | 2.75× | 1.13× | 2.44× |
| D95max | 0.028 → 0.008 | 3.50× | 1.20× | 2.92× |
| minwscal | 0.038 → 0.008 | **4.75×** | **2.47×** | **1.92×** — headline OVERstates it 2.5× |
Recover the comparable number with `raw_RMSE = nqrmse × IQR_obs` (the `obs_q` array is printed on the same log
line, so this needs no re-run). Same family as ADR 0030's lesson that a correlation is scale-blind: **a
scale-free metric can move because its scale moved.**

**A pooled-marginal number does NOT test between-cell composition.** `nqrmse`/pooled KS ask "is the global trait
histogram right", which is blind to whether the *right cells* got the right traits. A per-cell trait median is a
*composition* statistic (FIT draws traits from per-PFT `[low,high]` intervals), so a population change can
improve the pooled marginal while degrading per-cell skill. Use `median_percell_r` and the NOISE-FLOOR gate
below for that claim — and do not let a good pooled number stand in for it (that conflation is what fig 10 exists
to expose).

**Plot per-cell KS was O(ncells·N) → fixed to O(N log N) (sort-group once).** The old fig-11 loop did
`ccells == c` per cell (a full scan over all N stems each) → ~6e12 ops at 45009 cells × 133M stems → the plot
TIMED OUT at 1h. Now `np.argsort(ccells)` once + contiguous-group slices. Regenerating trait figs at global
scale is minutes; give the plot job a ≥1h wall anyway (it also reads 4×~1GB `pred_<axis>.f64`).

**HOLD-OUT-BY-SCENARIO evals (ADR 0026 §5, the unseen-regime proof — train on one regime, test the
held-out other).** COUNT: `scripts/eval_slow_scenario_holdout.jl` on a POOLED count table (needs
`scenario.i64` from `pool_slow_tables.py`) → per-direction R². COPULA/TRAITS:
`scripts/eval_slow_copula_scenario_holdout.jl` on a POOLED copula table → per-axis per-direction nqrmse + KS.
Run each on BOTH the transient- and static-boundary pooled tables — the static-vs-transient DELTA is what
attributes the boundary's payoff (the count scenario-holdout showed transient==static ⇒ the flux drivers,
not the boundary, carry COUNTS; the boundary's value, if any, must show on TRAITS here).

## NOISE-FLOOR gate (the P3 metric — is the emulator as good as the stochastic data allows?)

`scripts/noise_floor_vs_emulator.py` (SLURM: `TIME=01:00:00 NCPUS=32 scripts/sbatch_python.sh S-noisefloor
scripts/noise_floor_vs_emulator.py`, ~10 min) compares the emulator's per-cell skill to the
**seed1-vs-seed2** irreducible spread (LPJmL-FIT is stochastic — RAND48 + -DPERMUTE — so two seeds of the
SAME cell disagree). **ADR 0030 rewrote this gate; the pre-S1 numbers below the line are withdrawn.** It now
reports three BASES and two ceilings:

- **`copula` (definitive)** — seed1 `Y_<axis>` vs **seed2 `Y_<axis>`** from a second `MODE=copula SEED=2`
  build differing in NOTHING else (no `STEM_CAP` — it would subsample `Y`; the boundary window is free).
  Prereq artifact: `/p/tmp/jamirp/emulator_global/slow_copula_historic_seed2` (~70 s to rebuild, 32 cpus).
- **`tree5`** — the same population re-derived from the parquets; its `seed1-basis` column is a **hard gate
  (≥0.99, reads 1.000)**. A floor failing it is void — never quote its gap.
- **`tree7`** (`Type ≤ 6`) — FIT's COMPLETE tree set. **`Type ≤ 6` is CORRECT (ids 0-6 are all seven tree
  PFTs; 7/8/9 are grass, written with tree fields ZEROED); it is `TREE_TYPES=[1,2,3,4,5]` that is truncated
  (ADR 0031).** So this basis' floor is the real forest's, but its GAP is cross-population until 0031 lands.
### Running it on a scenario OTHER than historic (ADR 0043, 2026-08-04)

The two `ind` parquets are **env-overridable** — defaults are the historic pair, so an un-parameterized run
stays byte-identical to every published number:

```bash
export IND_SEED1=/p/tmp/jamirp/emulator_global/ind_ssp370_seed1_all.parquet \
       IND_SEED2=/p/tmp/jamirp/emulator_global/ind_ssp370_seed2_all.parquet \
       SKIP_COPULA=1 SKIP_LEGACY=1
TIME=03:00:00 NCPUS=32 scripts/sbatch_python.sh S-floor-ssp370 scripts/noise_floor_vs_emulator.py
```

Four things will bite:

- **`export` is mandatory.** These knobs are **not** in `sbatch_python.sh`'s explicit forward list, and
  `scripts/sbatch_*.sh` is **integrator-owned** (CLAUDE.md §9 Gap 3) so a line cannot add them. A bare
  `VAR=v scripts/sbatch_python.sh …` command-prefix reaches the *wrapper* but **not the job**, which then
  silently takes the defaults — i.e. you get the **historic** floor under an ssp370 tag. The log's first two
  lines echo the resolved parquet paths: **check them before believing any number.**
- **`SKIP_COPULA=1` gives a FLOOR-ONLY run** (no `emu_r`, no GAP, no verdict) because basis 1 needs a seed2
  *copula table* for that scenario. Legitimate and useful — but always say which basis a quoted floor is on.
- **Basis 1 for ssp370 is NOT just "build the seed2 table".** The existing seed1 `slow_copula_ssp370_t8` is
  **capped** (22.3M ≈ 400×58 683) where `slow_copula_historic_t8` is uncapped (197.7M), so both sides need
  rebuilding. The cap cannot simply be left on: `build_slow_runtime_table.py:380` hashes with the **data**
  `SEED` and subsamples whole **patch-years**, so two capped tables keep *different* clusters and the extra
  noise **lowers `floor_r`**, flattering the emulator. And uncapped ssp370 is ~870 M stems ⇒ 91 GiB in numpy
  alone before the polars frame (several hundred GB peak, twice). Decide deliberately; don't just submit.
- **More years ⇒ a mechanically HIGHER floor.** ssp370 pools 81 years/cell to historic's 20, so ~4× more
  averaging lifts `floor_r` on every axis. Read any cross-scenario Δ against that tailwind: measured ssp370
  `tree7` floor SLA 0.975 / Wooddens 0.944 / **D95max 0.837** / minwscal 0.978 vs historic 0.965 / 0.923 /
  0.895 / 0.973 — three axes rise, and D95max falling 0.058 *despite* the tailwind is the real finding.

- **Attenuation** — `floor_r` is a realization-vs-realization r, so it is NOT a predictor ceiling. `pred` is
  one RNG draw per row, so use its own split-half reliability `rel_P`: ceiling `= √(rel_P·rel_Y)`,
  `r_center = emu_r/ceiling`. Report `(GAP, r_center)` **plus `sd(pred)/sd(Y1)`** — correlation is
  scale-blind and the copula is badly UNDER-dispersed between cells (Wooddens 0.55 vs a second seed's 1.00).

**Result (2026-07-28, ADR 0030, job 1617055 — on the ids-1..5 population):** per-axis GAP to the reachable
ceiling **Wooddens +0.226 · minwscal +0.153 · SLA +0.115 · D95max +0.102** (`r_center` 0.72/0.84/0.88/0.88);
`tree5` floor 0.694/0.909/0.964/0.791; split-half 0.978-0.999 ⇒ the floor is **trajectory divergence**, not
finite-stem noise. COUNTS: floor r²=0.962 vs emu 0.9994, but that comparison is still NOT like-for-like
(per-cell pooled total vs per-(Cell,Patch,Year) `n_living`) — an order-of-magnitude statement only.
Re-run whenever the emulator is retrained, and **re-measure everything after the ADR 0031 re-derivation**
(the floor moves to the `tree7` numbers).

## Interpreting / what "works well" looks like

- `metrics.txt` OOS per-row R² should be ≈ the `HOLDOUT_FRAC` train/test R² from the DRF train (historic:
  ~0.985). A big drop vs in-sample ⇒ overfitting.
- `03_map_bias` near zero everywhere; `05_scatter_percell` tight on the 1:1 line; `06_distribution` overlapping.
- `07`/`08` reveal biome/latitude regimes where skill drops → the next modeling target.

## Scope + extension points (honest)

- Figures 01-08 validate the **count** (`n_living`) DRF; figures 09-11 validate the **recruit-trait copula**
  marginals (ADR 0025, gated on `COPULA_OUT`). A per-axis JOINT-correlation check (SLA-Wooddens scatter) and a
  copula-vs-fixed-sapling A/B are natural further additions.
- A **skill-vs-baseline** panel (the climate-only `DirectEmulator`, `tables/direct_count_global.parquet`; the
  ADR-0020 falsifiable test) and a **coupled in-loop global** figure (S+F+E vs C trajectories) are natural
  additions — wire them into `plot_slow_emulator_validation.py` as figures 09+.
- For `SCENARIO=ssp370`: derive `cell_year_{soilmoist,lai}_ssp.parquet` + train the ssp370 DRF first
  (`slow-drf-pipeline`), then run this with `SCENARIO=ssp370`.

## Rebuilding the public LaTeX report (`docs/component_s_public_report.tex`)

The general-audience report consumes these figures as renamed copies in `docs/figs/`
(`01_map_observed.png` → `count_map_observed.png`, `09_trait_marginals.png` → `trait_marginals.png`, etc. —
`\graphicspath{{figs/}}`). When you regenerate a generation's figures, re-copy them there or the report
silently keeps showing the OLD generation's plots. Confirm which generation `docs/figs/` currently holds by
comparing byte sizes against `figures/emulator_validation/<gen>/` — they are plain copies, so sizes match
exactly.

Build it (`pdflatex` is NOT on PATH):

```bash
source /etc/profile.d/00-modulepath.sh; source /etc/profile.d/modules.sh
module load texlive/2026
cd docs && pdflatex -interaction=nonstopmode component_s_public_report.tex   # twice, for refs/TOC
rm -f component_s_public_report.{aux,log,out,toc}     # build litter; .gitignore is INTEGRATOR-owned (§9 Gap 3)
```

The `.pdf` **is tracked** — commit it alongside the `.tex`, or the repo ships a PDF that disagrees with its
source.

Two traps, both of which cost a build:

- **A blank line inside `\caption{}` aborts the build**: `! Paragraph ended before \NR@gettitle was complete`
  (hyperref's nameref) or `\caption@prepareanchor` (the `caption` package). The report's captions are
  deliberately long and multi-paragraph — the fix that works is giving every figure a **short optional
  caption**, `\caption[one-line summary]{...long...}`, so the long text is never used as the PDF anchor.
  Loading `\usepackage{caption}` alone does **not** fix it.
- **Do not quote `basis_ratio`/`basis_frac_over_10pct` from `metrics_biomass.txt` as predictive accuracy.**
  They are the count-vs-trait *row-universe consistency* check (ADR 0033's algebraic identity), not a skill
  score. The accuracy fields are `percell_r2`, `percell_r2_log10`, `median_ratio`, and
  `obs_mean_stand_agb`/`pred_mean_stand_agb`. Note `median_ratio` > 1 while the mean ratio < 1 is the normal
  heavy-tailed signature (typical cell slightly over-predicted, the few huge-biomass cells under-predicted) —
  report both rather than picking whichever looks better.
