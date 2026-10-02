# Germany emulator: the scoring harness and the scores of the trivial baselines (line X, 2026-10-01)

Scripts: `scripts/explore_de_reference.py` (reference statistics, tolerances, block scale, independent check) and
`scripts/explore_de_score.py` (scores any emulator output; nulls; self-test; headline table).
Data: `/p/tmp/jamirp/X_de/reference/` (2.7 GB). Definition file: `reference/_DEFINITION.md`.
Status/handoff: `/p/tmp/jamirp/X_de/_status/score.md`. Report: `/p/tmp/jamirp/X_de/_reports/score.json`.

## 1. What is scored (ADR 0106 + ADR 0111, adapted)

* **Population** [SOURCE: ADR 0106 §2, repo CLAUDE.md]: living trees = `Type <= 6`, `isdead == 0`, `Height >= 5 m`
  (the height cut removes 0 rows from the C output in all 40 member-windows [MEASURED]; it exists so an emulator
  roster that also carries small trees is comparable).
* **Statistics per (gcm, scen, seed, window, Cell)**, pooled over the window's 30 years, stem-year weighted:
  `n_per_patch` (living stem-years / (years x 250 CONFIGURED patches), ADR 0111 (c)), `agb_stand`, the seven
  per-PFT stem shares, and q05/q25/q50/q75/q95 of SLA, Wooddens, D95max, minwscal, Longevity, Height, agb.
  ADR 0106's "distribution" metric is the 10 % bound on EACH of the five quantiles; that is what is implemented.
  Quantiles are not scored below 30 living stem-years in the window (ADR 0111's >= 30 stems rule).
* **Panels**: `panel106` = n_per_patch + 5 quantiles x {SLA, Wooddens, D95max, minwscal, Height, agb} (31
  quantities, ADR 0106 §2 exactly, minus its flux row which has no `ind` counterpart). `extended` = panel106 +
  Longevity quantiles + agb_stand + 7 PFT shares (44). Sub-panels (count, medians, distributions, shares) are
  reported separately.
* **Targets**: levels h1985 (1985-2014), w2015 (2015-2044), w2071 (2071-2100), w3071 (3071-3100, equilibrium
  only), and responses r2071 = w2071 - h1985 and r2015 = w2015 - h1985 per scenario and seed (each seed's
  1985-2100 is one continuous trajectory). The **whole criterion** per (gcm, ssp, cell) = every panel quantity
  passes in h1985 AND w2015 AND w2071 AND r2071.
* **Tolerance** = allowed |E - C| with C = seed 1, R = seed 2, `max(10 %, two-seed spread)`, four variants carried
  side by side (columns `allowed`, `allowed_cell`, `allowed_q90`, `allowed_cal`):
  * `allowed` (PRIMARY, ADR 0111's estimator): spread = median over the cell's density stratum of
    |C - R| / mean(C, R) (levels), |dC - dR| / |mean historical level| (responses), |C - R| (shares; floor 0.005).
  * `allowed_cell`: the literal per-cell spread (ADR 0106's wording, "in that cell").
  * `allowed_q90`: the stratum 90th percentile.
  * `allowed_cal` (an ADDITION, not in either ADR): one multiplier per (quantity, level/response) on the stratum
    spread, all at the same quantile p of seed 2's own deviation ratio, p chosen so seed 2 passes ALL panel106
    quantities in 95 % of (target, cell) pairs. In-sample for the other-seed null by construction.
  * every pass test is `|E - C| <= allowed * (1 + 1e-9)`.
* **Block scale** (added because of §3.3): 52 blocks of ~1 degree (54-274 cells, median 196); block value =
  area-weighted mean of the per-cell statistic over the cells where both seeds have a value; the identical
  tolerance construction with blocks in place of cells. `reference/block_dev/` is the same built from the dev
  cells (Cell % 10 == 0) for dev-subset arms (`--scope covered`).
* **Aggregate response** (ADR 0111 §5, its primary response statistic): area-weighted Germany mean and latitude
  terciles (south < 50.15 N < central < 52.05 N < north), tolerance max(10 %, |aggC - aggR|), S/N >= 3 guard.

### Adaptations, stated
1. 30-year windows instead of ADR 0111's 20-year climatology (the data come in 30-year blocks).
2. 250 patches instead of 25, so every spread is about sqrt(10) smaller than ADR 0111's numbers [MEASURED: count
   spread median 2.4 % vs ADR 0111's 6.8 % at 25 patches].
3. Density strata are nearly degenerate in Germany: every cell is in 5-10 (167 842 cell-targets) or 10-20 (4 393)
   stems per patch [MEASURED], so the stratum median is close to a single pooled median.
4. "The response within 10 %" with a two-seed floor: the response spread is normalised by the historical LEVEL,
   not by the response itself (a per-cell response is often near zero, so a response-relative spread is
   undefined). The 10 % part is 10 % of |dC|.
5. Latitude terciles stand in for ADR 0111's global latitude bands; the 1-degree blocks add a finer spatial test.
6. MPI-ESM1-2-HR ssp370 seed 2 3071-3100 is truncated at source and NOT used: its w3071 tolerance is borrowed from
   the same GCM's ssp126 + ssp245 w3071 spreads (column `tol_source`). Cells 31-32 (rock/ice) have no trees in any
   member: 9 065 of the grid's 9 067 cells are scored.
7. ADR 0106's flux row (GPP/NPP, LE, closures) is not scored: the `ind` table has no GPP and no water flux.

## 2. The emulator output contract

Either (A) a per-tree annual **roster** in the `ind` parquet's columns (required: Year, Cell, Type, isdead,
Height, SLA, Wooddens, D95max, minwscal, Longevity, agb; plus gcm/scen columns or `--gcm/--scen`), or (B) the
per-cell **window statistics** (long: gcm, scen, window, Cell, quantity, value; or wide). Both go through the same
reduction code as the reference (proved by the self-test, §4). Details: the `explore_de_score.py` docstring.

```
python scripts/explore_de_score.py score --pred <file|dir|glob> --format roster|stats --label <name> \
       [--gcm G --scen S] [--scope all|covered] [--cells FILE] [--npatch 250]
python scripts/explore_de_score.py headline --label <name>[,<name2>...]
```
Output `reference/scores/<label>/` (cell scale) and `<label>/block/` (block scale): `cells.parquet` (every target x
cell x quantity with C, R, E, all four allowed columns, pass flags), `summary_quantity.csv`,
`summary_conjunctive.csv` (with `ceiling_*` = the other seed's pass fraction under the same tolerance),
`summary_criterion.csv`, `aggregate_response.csv`, `coverage.json`. Scoring a full-Germany submission takes
about 10-15 s after reduction [MEASURED on the nulls]; run on SLURM.

## 3. Results

### 3.1 The original model's own two-run spread [MEASURED, all 40 member-windows, 9 065 cells, levels pooled]
Median per-cell |C - R| / mean: n_per_patch 2.4 %, agb_stand 3.3 %, SLA q50 0.5 %, Wooddens q50 1.0 %,
D95max q50 4.0 %, minwscal q50 0.7 %, Longevity q50 1.2 %, Height q50 1.2 %, agb q50 4.7 %. Cells whose spread
exceeds 10 %: D95max q50 11.5 %, agb q50 16.1 %, n_per_patch 0.7 %, Wooddens/minwscal/Height q50 0 %.
**So for LEVELS the 10 % floor binds almost everywhere** at 250 patches.
Per-cell RESPONSE (r2071) signal-to-noise, median over cells: Wooddens q50 0.82, minwscal q50 0.66, D95max q50 0.79,
Height q50 2.4, agb_stand 2.7, n_per_patch 4.4, SLA q50 8.9; the two seeds disagree on the SIGN of the per-cell
response in 35-41 % of cells for Wooddens, minwscal and D95max medians. At block scale the same S/N is 4.5-24.

### 3.2 The baselines (median over the 6 gcm x scenario pairs; min-max in brackets) [MEASURED]
Conjunctive pass fraction, panel106, CALIBRATED tolerance:

| null | scale | h1985 | w2015 | w2071 | r2015 | r2071 | w3071 |
|---|---|---|---|---|---|---|---|
| (a) other seed (ceiling) | cell | 0.93 | 0.96 | 0.96 | 0.95 | 0.95 | 0.95 |
| (a) other seed | block | 0.93 | 0.98 | 1.00 | 0.97 | 0.96 (0.90-0.98) | 0.85 |
| (b) persistence (h1985 -> later) | cell | - | 0.03 (0.00-0.13) | 0.04 (0.00-0.17) | 0.20 | 0.05 (0.00-0.48) | - |
| (b) persistence | block | - | 0.00 | 0.00 | 0.00 | 0.00 | - |
| (c) zero response = (b)'s responses | | | | | | | |
| (d) 2071-2100 predicts 3071-3100 | cell | | | | | | 0.05 (0.00-0.45) |
| (d) | block | | | | | | 0.00 (0.00-0.02) |
| (e) Germany-wide mean, every cell | cell | 0.29 | 0.33 | 0.36 | **0.97** | **0.92** | 0.46 |
| (e) | block | 0.31 | 0.21 | 0.22 | 0.39 | 0.06 | 0.21 |

Whole criterion (h1985 + w2015 + w2071 + r2071, panel106, calibrated), range over the 6 pairs: per cell, other
seed 0.84-0.86, persistence 0.00-0.025, Germany mean 0.20-0.28; per block, other seed 0.83-0.96, persistence 0,
Germany mean 0.00-0.06. Extended panel, calibrated: other seed 0.53-0.56 per cell, 0.58-0.92 per block.

Under the PRIMARY (stratum-median, ADR 0111) tolerance the other seed passes panel106 in only 0.19-0.38 of cells
per level window (0.80-1.00 of blocks) and in **0 % of cells and blocks for every response**, so its whole-criterion
pass is 0. Under the literal per-cell spread (`allowed_cell`) the other seed passes every response by construction
(the tolerance IS its deviation) and 0.38-0.65 of level cells (it fails where C < R, because ADR 0106's spread is
relative to the two-run mean while the error is relative to C).

Aggregate response, DE + 3 latitude terciles, all 44 quantities x 6 pairs: other seed passes 100 % (by
construction: the tolerance is max(10 %, its own deviation)); persistence/zero response 5-9 %; Germany-mean null
100 % for DE (by construction), 38-74 % per tercile.

### 3.3 What the numbers say about the yardstick
1. **The ADR-faithful tolerance cannot be read as pass/fail.** A second run of the original passes 0 % of the
   per-cell responses and 19-38 % of the per-cell level panels under it, because a median-based spread lets half
   of a replica's deviations exceed it and the panel is a conjunction of 31 quantities. Every arm must be read
   against the other seed's pass fraction under the same tolerance (`ceiling_*` columns), or with `allowed_cal`.
2. **`allowed_cal` makes the ceiling 95 % but is in-sample** for the other seed (calibrated on it). A perfect
   stochastic replica of the original would pass about 95 %; a deterministic emulator of the mean should do better.
3. **The per-cell RESPONSE test has no power against a spatially uniform response.** Under `allowed_cal`, giving
   every cell the Germany-mean response passes 92-97 % of cells, as well as the other seed. At 1-degree block
   scale the same null passes 6 % (r2071) while the other seed passes 96 %. **Use the block-scale response (and
   the aggregate) as the response evidence; never quote the per-cell response pass fraction alone.**
4. **The 10 % level bound has limited spatial power for traits**: a spatially flat prediction (Germany mean in
   every cell) passes 29-46 % of per-cell level panels and 21-31 % of block level panels, because Germany's
   spatial contrast in many trait quantiles is under 10 %.
5. Persistence fails everything at block scale (0 %), so any credible arm must beat 0 on w2015/w2071/r2071 there.

## 4. Gates [MEASURED]
* Reduction: 40/40 member-windows reduced; reduced living-tree rows equal the conversion gate's living-tree row
  count in every member; every aggregate asserts key uniqueness; height cut removed 0 rows.
* Independent check (`verify`): duckdb SQL straight from the `ind` parquet reproduces 2 208 statistics (4
  members x 12 cells x 46) with 0 mismatches, max relative difference 5.9e-8 (float32 interpolation).
* Self-test: the roster contract reduces the dev cells of MPI Historical seed 2 to the reference values exactly
  (39 908 values, max diff 0); its pass flags match the other-seed null's for those cells (0 mismatches); its
  block values equal the dev block reference exactly; the other-seed null's block values equal the block
  reference's seed-2 values exactly (43 472 rows, diff 0).

## 5. Defects found and fixed in this round (2026-10-01)
* Float rounding: `dev <= allowed` failed by ~2e-16 in 3.2 % of the other seed's per-cell response rows under
  `allowed_cell`. Fixed with a 1e-9 relative slack.
* The first `verify` listed the same parquet file 9 times (a loop variable that was already the block index was
  divided by 500 again), giving 9x counts. Fixed, plus an assert that duckdb returns every requested cell.
* Block reference for the dev cells built no blocks (all boxes had < 50 dev cells). The block geometry is now
  always built from all cells and then restricted.

## 6. Not done
* No CO2 anything (owner decision). No flux quantities (no source in `ind`).
* No scoring of the climate-blind null: it needs an emulator.
* The calibration is in-sample; with only two seeds there is no held-out replica to validate the 95 % ceiling.
* Block S/N and block calibration rest on 52 blocks; the response calibration's bisection landed at 96.5 %, not
  95 %, because the conjunctive fraction is coarse with 52 blocks x 12 targets.
