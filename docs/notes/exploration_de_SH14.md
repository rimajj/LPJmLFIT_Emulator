# SH14 — scorer amendments demanded by the round-1 critic (Germany emulator, round 2, 2026-10-01)

> **SUPERSEDED IN PART — OWNER DECISION 2026-10-01 (read this section first).** The 2071–2100 and 3071–3100
> runs of the original model used the wrong humidity setting, so the owner decided to use only 1985–2044. Every
> number further down that involves w2071 / w3071 / r2071 / c2071 (incl. the "PRIMARY c2071" statements and the
> pre-registration values derived from them) is **withdrawn**. The clean numbers below replace them.

## Repair 2 (after the second verifier round, `_reports/r2_verify_SH14.json`) — read with the clean section below

Job **2371484** (exit 0; `_jobs/X-de-SH14r2-rebuild.jcf`): every null re-scored, selftest **31/31** (new checks
N1–N6), the verifier's bad inputs replayed through the command line, all tables rebuilt. The reference tables
themselves did not change (not rebuilt; selftest M4 re-confirms clean = full on every non-calibrated column).

**1. The primary response test needs scenario legs that share the random numbers [MEASURED].** The original model's
three scenario runs start from one 2014 state and draw the same random numbers afterwards, so their difference is
nearly free of run-to-run noise. An arm whose legs do not share both cannot pass the block-scale scenario-contrast
test at this noise level: both brackets the scorer computes for "legs from different states" are **0.000** for
all-cell blocks (both GCMs, both calibrations) and 0.000–0.077 on dev blocks. The case in between (one shared 2014
state, independent random numbers afterwards) has no measured ceiling: it can only be measured with the emulator
itself, from two runs that differ only in their random streams. The scorer now has a command for that
(`armnoise --manifest-a A.csv --manifest-b B.csv`).
`--legs-branched` now takes `yes|state-only|no|unknown`. **Only `yes` (one 2014 state of the arm's own run AND
common random-number streams, e.g. keyed by cell, patch, year and draw) makes the primary test assessable;** every
other arm gets the verdict `not_assessable`, never "failed".

**2. The primary test is now read like for like and printed as one row per GCM (`primary_gate.csv`).** The arm's
panel pass fraction in a tolerance column is compared with 0.9 × the second seed's pass fraction **in the same
column on the same rows**. The binding column is the calibration fitted on the other GCM (`cal_xg`); the in-sample
calibration (`cal`) is printed beside it. Values on the held-out GCM (ACCESS-CM2, ssp370 − ssp126, panel106,
truth seed 1):

| cell set | second seed `cal_xg` (bar = 0.9×) | second seed `cal` | zero contrast `cal_xg` | uniform `cal_xg` | frozen rosters `cal_xg` | different-state brackets |
|---|---|---|---|---|---|---|
| all 9065 cells, 52 blocks | **0.654** (0.589) | 1.000 | 0.000 | 0.019 | 0.000 | 0.000 / 0.000 |
| 907 dev cells, 52 blocks | **0.731** (0.658) | 1.000 | 0.365 | 0.288 | 0.365 | 0.000 / 0.077 |
| fold-5 dev cells (11 blocks) | 0.091 | 1.000 | 0.000 | 0.000 | 0.000 | 0 / 0 |

So on the dev cells the zero-contrast null reaches half of the bar; on all cells it reaches none of it. The fold-5
subset has no usable ceiling. MPI-ESM1-2-HR ssp370 is a training member: its row is labelled `not_held_out`.
Table: `shared/scorer/sh14_primary_gate_nulls.csv`.

**3. The hold-out truth seed comes from the split registry.** The scorer reads `shared/registry/test_pairs.parquet`
(`--split`, default DEV-A). MPI ssp245 is now scored against seed 2 without being asked; `--truth-seed 1` is refused
with an explanation unless `--truth-seed-override` is given; a call mixing members with different truth seeds is
refused. Replaying the verifier's probe: MPI ssp245 seed-1 levels on the dev cells used to score 1.000 against
themselves; they now score 0.932 (w2015, panel106, `cal`) against seed 2, and `coverage.json` records the seed and
where it came from.

**4. Every summary carries the member's role** (`role`, `in_sample`, `held_out` from `splits.parquet`), and
`headline.csv` keeps only rows whose truth member is a registry test truth (`headline_all.csv` keeps everything).
Under truth seed 1 the held-out rows are ACCESS-CM2's; MPI ssp245 seed 1 is `test_ref` (neither in nor out).

**5. The signal-to-noise numbers now sit beside their pure-noise value.** With no true signal and two exchangeable
seeds, |(C+R)/2| / |C−R| has median 0.50; 29.5 % of units exceed 1 and 10.5 % reach 3; the seeds agree on the sign
half of the time. The derivation was checked by simulation (`sh14_snr_null_check.json`: 0.4999 / 0.2954 / 0.1056 /
0.4999). Measured beside it, for ssp370 − ssp126 in 2015–2044 across the 31 panel quantities × 2 GCMs:
* **per cell:** median S/N 0.57, 33 % of cells above 1. That is barely above pure noise. 21 of 62 quantity×GCM rows
  are indistinguishable from zero signal (every minwscal quantile on both GCMs, every D95max quantile on MPI, the
  lower Wooddens quantiles and the Wooddens median on ACCESS-CM2), 39 are above noise but undetermined in most cells,
  and only 2 are determined (tree count and median biomass, both MPI). **So the earlier "33 % of
  cells above the noise, 12 % at 3×, signs agree in 49–67 %" describes almost pure noise, not a weak signal.**
* **dev blocks:** 45 of 62 determined, 12 indistinguishable from zero (minwscal on both GCMs, the D95max median
  on MPI, lower Wooddens quantiles on ACCESS-CM2).
* **all-cell blocks:** 57 of 62 determined, 4 indistinguishable from zero.
* **Germany aggregate (S/N 19.7):** one draw per GCM, so it has no distribution; it is flagged as such.

**6. Per-window ceilings (`sh14_ceiling_per_window.csv`).** The block level calibration reaches its target only
when pooled over windows. Second seed, panel106, all-cell blocks: h1985 ACCESS 1.000 / MPI **0.750** (`cal`) and
1.000 / **0.596** (`cal_xg`); dev blocks 0.962 / 0.865 and 0.962 / 0.615. Quote the matching per-window ceiling
beside any block-scale level number.

**7. Edge cases and hard-coded values.** A submission with no year in 1985–2044 is refused with a message, not a
traceback. Years outside every window (e.g. 2045–2070 of a run continued to 2070) are listed in
`coverage.json: years_outside_windows`, which points to the 2045–2070 cell-aggregate check tables
(`shared/gap/check`). The docstring no longer lists the excluded windows as scored. The roster reduction uses the
configured partition size (`XDE_CELLS_PER_PARTITION`; selftest N4 shows a different size gives identical numbers).
The dev block reference is recognised by the cells it was built on, not by "Cell % 10". The whole-domain region name
is a setting (`XDE_REGION_ALL`, default DE).

**Not done:** measuring the shared-state ceiling (needs two emulator runs with different random streams); a
per-window block calibration (the per-window ceilings are reported instead); re-gating the legacy full reference.

## CLEAN reference set (owner decision 2026-10-01) — what changed, gates, null values, signal-to-noise

**Confirmation [MEASURED, job 2371077, `scripts/explore_de_sh_scorer_confirm_exclusion.py`]:** on the 907 dev cells,
the share of living trees with a water-stress death hazard > 0 is **exactly 0 in every year of all 12 w2071 and all
12 w3071 members** (360 + 333 member-years), against 0.003–15.6 % (h1985, 4 members) and 0.0003–23.1 % (w2015, 12
members) of living trees per year in the correct segments. This independently confirms the orchestrator's config/log
finding. Files: `shared/scorer/sh14_exclusion_confirmation.{json,csv}`.

**What the scorer now does (additive; old behaviour reachable with `--refset full` / `XDE_REFSET=full`):**
* New reference set `reference/clean/` = the DEFAULT for `explore_de_score.py` and `explore_de_reference.py
  assemble|calibrate|blocks`. Windows h1985 + w2015 only; targets h1985, w2015, r2015, c2015 (ssp370|ssp245 − ssp126).
  `stats/`, `cell_year/`, `frozen/` are shared with the full set. The full (legacy) files in `reference/` are kept
  untouched (rebuilt by the SH14 repair at 12:21–12:23) and every summary scored on them is labelled "EXCLUDED BY
  OWNER DECISION".
* Every calibration multiplier is refitted on 1985–2044 targets only (the full set's pooled the corrupted windows).
* Submitted 2071–2100 / 3071–3100 years (roster) or w2071/w3071 rows (stats) are **dropped, never scored**, with a
  printed WARNING and `coverage.json: excluded_windows_dropped`; `coverage.json` also carries `reference_set`,
  `scored_targets`, `excluded_targets`, `primary_response`.
* Whole criterion = h1985 + w2015 + response target (r2015 or c2015), `targets_needed` 3. Primary response = c2015
  ssp370 (`target_note` "PRIMARY response"). Equilibrium null (w3071) only in the full set.
* Persistence and frozen-2014 nulls predict w2015 only.

**Gates [MEASURED]:** `gate_clean` PASS (13 comparisons, `shared/scorer/sh14_clean_gate.json`): clean levels =
full levels on 1985–2044 (6 381 760 rows, identical); every NON-calibrated tolerance column identical at cell (7 179 480
rows), block and block_dev (41 184 rows each), truth seed 1 and 2; block masks identical; no excluded target in any
clean table. Selftest **25/25** (`reference/clean/scores/selftest.json`), incl. new M1–M4: no excluded target in the
clean reference; a roster with 2071–2100 rows scores only w2015 and flags 30 dropped (gcm, scen, year); a stats file
with w2071 rows drops and flags 880 rows; clean = full on every non-calibrated column (7 179 480 rows). The contrast
recompute from levels is exact (797 720 c2015 rows, max rel 0). Comparison helper `_cmp_cells` made NaN/inf-aware.

**Amendment 1 on the clean set (replica = other seed, panel106, median over (gcm, scen), all 9065 cells):** literal
per-cell rule cell levels h1985 **0.510** / w2015 **0.532** → symmetric `allowed_cell_abs` **1.000** (by
construction; responses and contrasts were already 1.000); stratum rule 0.321/0.294 → symmetric spread 0.324/0.294
(responses/contrasts 0 → 0); block levels literal 0.798/0.990 → 1.000. An INDEPENDENT run as good as the second seed
is expected to pass (exchangeability, lower bound): per-cell levels 0.22–0.31 of panels, responses/contrasts 0.00
(each quantity ~0.50) — the literal rule is attainable only by the run that defines it.

**Calibration [MEASURED]:** cell scale: replica panel106 conj 0.950 (level/response/contrast fitted to 0.95);
out-of-sample (multiplier fitted on the other GCM) 0.911–0.939. Block scale (52 blocks): the per-quantity calibration
lands at **1.000** for responses and contrasts (order-statistic coarseness) and **does not transfer across GCMs**:
replica under `allowed_cal_xg` 0.71 (r2015) / 0.64 (c2015 ssp370) all cells, 0.68/0.66 dev blocks. The one-multiplier
`allowed_cal1` transfers (0.95–0.97) but **loses all power**: at cell scale the nulls pass MORE than the replica
(w2015: frozen-2014 0.993, persistence 0.984 vs replica 0.956), at block scale the zero contrast passes 0.587 (all
cells) / 0.923 (dev). ⇒ **never use `cal1` as a gate.** Refitting on 1985–2044 changed the per-quantity multipliers
little (median ratio clean/full 1.00; 5–95 % 0.68–1.56) but cut the single-multiplier ones (cell contrast ×0.15,
response ×0.28): the full set's single k was set by the corrupted late windows.

**NULL VALUES (replace every pre-registration value; `shared/scorer/sh14_prereg_null_values.csv`,
`sh14_clean_key_nulls.csv`; panel106, calibrated `allowed_cal`, truth seed 1, median over (gcm, scen); contrasts ssp370 only;
"oos" = the replica under the cross-GCM calibration, the honest ceiling):**

| target | scale, cells | replica (oos) | zero / persistence | uniform (DE mean) | frozen-1985 own / other | frozen-2014 own / other |
|---|---|---|---|---|---|---|
| c2015 (PRIMARY) | block, all 9065 | 1.000 (0.635) | 0.010 | 0.058 | 0.010 / 0.010 | 0.010 / 0.010 |
| c2015 | block, dev 907 | 1.000 (0.663) | 0.308 | 0.606 | 0.308 / 0.308 | 0.308 / 0.308 |
| c2015 | block, fold-5 dev 185 (11 blocks) | 1.000 | 0.136 | — | — | — |
| c2015 | cell, all / dev | 0.950 / 0.948 | **0.979 / 0.977** | 0.987 / 0.988 | = zero | = zero |
| r2015 | block, all | 1.000 (0.712) | 0.000 | 0.317 | 0.000 | 0.000 / 0.000 |
| r2015 | block, dev | 1.000 (0.683) | 0.000 | 0.673 | 0.000 | 0.000 / 0.000 |
| r2015 | cell, all / dev | 0.948 / 0.951 | 0.200 / 0.203 | 0.968 / 0.970 | 0.200 | 0.765 / 0.328 |
| h1985 | cell, all / dev | 0.943 / 0.949 | — | 0.302 / 0.302 | **0.919 / 0.742** ; dev 0.916 / 0.733 | — |
| h1985 | block, all / dev | 0.875 / 0.913 | — | 0.298 / 0.288 | 0.510 / 0.038 ; dev 0.481 / 0.106 | — |
| w2015 | cell, all / dev | 0.953 / 0.954 | 0.028 / 0.021 | 0.315 / 0.308 | 0.005 / 0.001 | 0.370 / 0.404 ; dev 0.373 / 0.397 |
| w2015 | block, all / dev | 0.981 / 0.971 | 0.000 | 0.212 / 0.192 | 0.000 | 0.000 ; dev 0.019 / 0.000 |
| criterion c2015 | cell, all / dev | 0.877 / 0.882 | 0.018 / 0.015 | 0.269 / 0.269 | 0.003 / 0.000 | 0.315 / 0.334 |
| criterion c2015 | block, all / dev | 0.856 / 0.856 | 0.000 | 0.019 / 0.135 | 0.000 | 0.000 |
| criterion r2015 | cell, all / dev | 0.884 / 0.888 | 0.016 / 0.013 | 0.269 / 0.268 | 0.002 / 0.000 | 0.300 / 0.162 |

Aggregate (Germany + latitude terciles, same cells, determined rows only): c2015 all cells — replica 1.00 (by
construction), expected independent equal run 0.87, floor-only ceiling 0.73; zero 0.056, uniform 0.48. Dev cells:
0.81 / 0.63; zero 0.065, uniform 0.44. r2015 dev: 0.78 / 0.55; zero 0.053, uniform 0.64, frozen-2014 0.12–0.14.

**Signal-to-noise of the early-century responses [MEASURED, `shared/scorer/sh14_clean_snr{,_panel,_compact}.csv`;
signal |(C+R)/2|, noise |C−R|, panel106 medians over quantities and GCMs]:**

| statistic | cell (9065) | block_dev (~18 cells) | block (~175 cells) | Germany aggregate |
|---|---|---|---|---|
| c2015 ssp370−ssp126: median S/N | **0.57** | 1.39 | 3.43 | 19.7 |
| … share of units with S/N > 1 / ≥ 3 | 0.33 / 0.12 | 0.62 / 0.29 | 0.85 / 0.56 | 1.00 / 1.00 (94 % of quantity×GCM ≥ 3) |
| c2015 ssp245−ssp126 (scenario + binary) | 0.56 | 1.25 | 2.87 | 9.2 |
| r2015 = w2015 − h1985 (ssp370) | 1.60 | 4.39 | 6.15 | 8.7 |

Per cell, the early-century scenario contrast is **not determined above the two-seed noise in two thirds of cells**,
the two seeds agree on its sign in only 49–67 % of cells (minwscal_q50 49 %, coin-flip), and the zero-contrast null
passes the calibrated per-cell test MORE often than the second seed (0.979 vs 0.950). minwscal_q50 is undetermined
even at full block scale (S/N 0.63). The contrast is a block-and-aggregate statistic only; on the 907 dev cells it is
weak even at block scale (zero 0.31, uniform 0.61). r2015 is much stronger but contains the 1985→2020 CO2 rise (and
the stands' own development since 1985), which the emulator does not see. **This limits what the clean data can test:
the warming signal by 2044 is small; it is not a failure of any emulator.**

## (Pre-decision record, kept for provenance — late-window numbers withdrawn)

Scripts: `scripts/explore_de_reference.py`, `scripts/explore_de_score.py` (both edited, additive), new
`scripts/explore_de_sh_scorer_gate.py` (old-vs-new gate + null table) and `scripts/explore_de_sh_scorer_power.py`
(what an independent, equally good run would pass). Pre-edit scripts + reference outputs backed up at
`/p/tmp/jamirp/X_de/shared/scorer/backup_pre_SH14/` (md5 of the old scripts in `scripts/MD5SUMS`).
Jobs: 2370684 (assemble/blocks/frozen/nulls), 2370776, 2370801 (nulls rerun + gate + selftest), 2370789 (power).

## What changed (every round-1 column and default behaviour is unchanged — gated, see below)

1. **Symmetric tolerances.** New columns `allowed_cell_abs = max(0.1|C|, |C−R|)` (shares ≥ 0.005; identical to
   `allowed_cell` for responses), `allowed_c`/`allowed_q90_c` (stratum median / q90 of `|C−R|/|C|`),
   `allowed_cal_c` (calibrated on that spread); pass columns `pass_cell_abs`, `pass_c`, `pass_q90_c`, `pass_cal_c`;
   conjunctive `all_<pass>_frac`; headline tolerance names `cell_abs`, `c`, `q90_c`, `cal_c`.
2. **`--truth-seed {1,2}`** (reference `*_t2` files: C = seed 2, R = seed 1). `--start-seed` is recorded in
   `coverage.json` with `start_state_shared_with_truth`.
3. **Between-scenario contrasts** `c2071`, `c2015` = X(scen, w) − X(ssp126, w), scen ∈ {ssp370, ssp245}, same gcm,
   same seed (target_kind `contrast`, own calibration). Computed from the submission's own levels when one call
   carries ssp126 and the other scenario (multi-scen roster or `--manifest`). Every summary has `target_note`;
   ssp245 contrasts are labelled "scenario + binary, not for H4". Whole criterion is reported for both
   `response_target` r2071 and c2071.
4. **Frozen nulls** `null_f_frozen1985_from_s{k}` (h1985 + w2015) and `null_g_frozen2014_from_s{k}` (w2015 +
   w2071), from the truth seed's own roster and from the other seed's roster; window statistics of the replicated
   roster in `reference/frozen/<gcm>_s<seed>_y<year>.parquet`.
5. **Held-out-place scoring.** `--cells FILE` now filters (it used to abort on rows of other cells) for roster and
   stats; `--manifest` = pooled cross-fit (rows `pred, [format, gcm, scen, cells, fold]`, each row restricted to its
   own cells / fold in `shared/registry/folds.parquet`, pooled, duplicate cell-targets rejected).
6. **Ceiling on the same rows**: `ceiling_same_*` = the other seed scored on exactly the submission's rows (cell
   and block, conjunctive and criterion). The round-1 `ceiling_*` are all-cell values and are wrong for subsets.
7. **Aggregate on the same cells**: `aggregate_response.csv` gains `*_same` columns (truth, replica and prediction
   aggregated over the scored cells). The round-1 columns compare a subset's aggregate with the all-cell truth.

## Gates [MEASURED]

* Old-vs-new: 35 comparisons (levels_long; tolerance/calibration/mask at cell, block, block_dev; the four round-1
  nulls' conjunctive/criterion/quantity summaries at cell + block): every round-1 column identical. One round-1
  defect surfaced and fixed: null (a)'s own `ceiling_*` were read from its previous output (stale by one rebuild;
  up to 0.81 off on the per-cell column); now equal to its own fractions.
* Selftest: 18/18 checks (roster path = reference; pass flags = null (a); replica passes `allowed_cell_abs` at 1.0
  on cell and block for both truth seeds; contrasts through a two-row manifest equal the reference contrast
  exactly at cell and block; truth-seed-2 roster = null_a_t2; 5-fold pooled cross-fit = unsplit score exactly;
  `--cells` = row subset; frozen roster through the roster path = reference/frozen to 2e-16).

## Findings [MEASURED]

* Symmetric per-cell rule: replica passes 1.00 everywhere — **tautologically** (its own deviation is the
  tolerance). An independent run exactly as good as the second seed is expected to pass, per cell: levels 0.28–0.31
  of panels (product over quantities, a lower bound), responses and contrasts **0.00** (each response quantity
  passes with probability 0.50–0.53). So the literal rule is passed only by the run that defines it.
* Stratum-median rule with the symmetric spread changes almost nothing (cell levels 0.32 → 0.32, responses 0 → 0).
* Calibrated rule: an independent equally good run is expected to pass 0.93–0.95 (cell) / 0.91–0.96 (block) —
  the in-sample 0.95 is not just an in-sample artefact.
* Contrast signal: per-cell c2071 S/N median 0.5–2.0 (seeds agree on the sign in 50–85 % of cells); the zero-
  contrast null passes 0.94 of cells (calibrated, ceiling 0.955) — no per-cell power. Block scale on all 9065
  cells: ceiling 0.971, zero 0.000, uniform 0.087 — good power. **On the 907 dev cells the block c2071 test is
  weak: ceiling 1.000, zero 0.144, uniform 0.779** (fold-5 dev, 11 blocks: 1.000 / 0.091 / 0.545).
* Truth-initialised frozen rosters: the do-nothing 1985 roster passes the calibrated h1985 cell-level panel at
  0.91 (ceiling 0.93); from the other seed's 1985 roster 0.75. The frozen 2014 roster passes w2015 cell levels at
  0.37–0.47 and r2015 at 0.77 (own seed) / 0.32 (other seed). H2 on h1985 for a 1985-start arm is uninformative.
* Pre-registered N2 identity: exact for counts, shares, agb_stand; for quantiles the 30-year frozen window differs
  from the single-year statistic by up to 13.9 % (SLA_q05, sparse cells; median 1.5e-5). Compare FROZEN runs with
  `reference/frozen/*`, not with the single-year cell-year table.

Tables: `/p/tmp/jamirp/X_de/shared/scorer/sh14_null_table.csv` (every null × cell set × scale × tolerance ×
window), `sh14_prereg_null_values.csv` (the pre-registration rows), `sh14_independent_run_expectation.csv`,
`sh14_gate.json`; null outputs in `/p/tmp/jamirp/X_de/reference/scores{,_dev,_fold5dev}/null_*`.
