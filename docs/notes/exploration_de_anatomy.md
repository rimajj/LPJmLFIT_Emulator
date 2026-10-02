# Exploration (line X, Germany): the anatomy of one LPJmL-FIT forest year in the `ind` table

*Exploratory note, 2026-09-30. Not a decision. Script: `scripts/explore_de_anatomy.py`. Data and results:
`/p/tmp/jamirp/X_de/anatomy/{full,sub,results}/`. Machine-readable report: `/p/tmp/jamirp/X_de/_reports/anatomy.json`.*

## Basis (applies to every number below unless stated otherwise)

* One member only: **MPI-ESM1-2-HR, random_seed_1**. Three windows:
  * **H1** Historical `ind_.csv` 1985-2014;
  * **S44** ssp370 `ind_2044.csv` 2015-2044 (restarted from the same seed's Historical `restart_2014`);
  * **S100** ssp370 `ind_2100.csv` 2071-2100 (restarted from `restart_2070`; no tree table exists for 2045-2070).
* **Whole Germany** (9 065 cells with rows, 250 patches each) for 11 transitions: 1985→86…1988→89, **2014→2015
  (across the Historical/ssp370 file boundary)**, 2015→16, 2016→17, 2071→72…2074→75. About 19-22 M tree rows per year.
* **Cell subsample** `Cell % 10 == 0` (907 cells, 30 years per window, all 29 transitions per window) for everything
  that needs a long series. 53-61 M living tree stem-years per window.
* TREE = `Type <= 6` (only types 1-5 occur in Germany); LIVING = `isdead == 0`. Everything is on the > 5 m population the
  `ind` writer emits. **§9 (added 2026-10-01) repeats the subsample battery on ALL 40 member-windows** (both GCMs,
  both seeds, Historical + ssp126/245/370, windows 2015-44 / 2071-2100 / 3071-3100) from the converted dev parquet
  (`/p/tmp/jamirp/X_de/ind_dev/`, same `Cell % 10 == 0` subset); §1-§8 are MPI seed 1 unless §9 says otherwise.
* C-source statements are marked [SOURCE] and were read in `/home/jamirp/lpjml56fit/src`. **The production binary is
  the Dec 17 2025 build** (the run logs print `Version 5.6.004 (Dec 17 2025)`) = git commit `fcd3a30`; the routines cited
  below are unchanged between that commit and HEAD except where said (the only later commit, `b2e5ca9` 2026-01-28, fixes
  `new_tree.c`, see §1).

## 1. Identity

* [MEASURED] Across every consecutive-year pair of living stems matched on (Cell, Patch, Type, ID): **Age increases by
  exactly 1 on 100.0000 %** (e.g. 21 553 581 of 21 553 581 pairs 1985→86; same in all 11 whole-Germany transitions), and
  **all six traits (SLA, Wooddens, D95max, minwscal, Longevity, beta_root) are bit-identical on 100 %** of pairs. The
  2014→2015 file boundary behaves exactly like a within-file year (age +1 on 100 %, no cells lost): Historical and ssp370
  seed 1 are one continuous trajectory.
* [MEASURED] (Cell, Patch, Type, ID) is **not quite unique within a year**: excess rows 32-47 per year in 1985-1989, 5-6 in
  2014-2017, and ~1 400 per year after the 2070 restart (0.007 % of rows). Adding (SLA, Wooddens) to the key leaves
  **0 duplicates** in every year. Dropping Type from the key adds only ~300 collisions per year (so Type matters, but ID is
  nearly unique within a patch anyway).
* [MEASURED] ID reuse across years: over 30 years of the subsample, keys seen again after being flagged dead: 6 (H1), 63
  (S44), 411 (S100); keys carrying two different SLA values: 7 / 93 / 558. **It grows after each restart.**
* [SOURCE, explains the above] `new_tree.c` (production build): the ID is taken from the *establishing* PFT's counter
  (`tree->index = treepar->index++`) and only afterwards, on the inheritance branch, is `pft->par` switched to the parent's
  PFT — so the printed Type and the counter that issued the ID can differ. On restart `fread_tree.c:65` resets each
  counter to (max ID among trees of that Type read by the task) + 1, which can re-issue numbers. [ASSUMPTION] this is the
  mechanism of the duplicates; not verified tree by tree.
* [SOURCE + MEASURED] **Production-binary inheritance quirk.** In the same branch `treepar` is not refreshed after
  `pft->par` changes (the fix is commit `b2e5ca9`, made *after* the production runs), so an inherited recruit's Wooddens and
  D95max are reflected at the **establishing** PFT's interval bounds while SLA and minwscal use the parent's. Measured
  signature: **Wooddens outside its own Type's [low, high] on 2.5-3.0 % of tree rows and D95max on 5.0-5.3 %, SLA and
  minwscal on exactly 0.000 %** (all 11 whole-Germany years). An emulator trained on this data learns this quirk; it is
  part of what the original model does.

**Recipe:** identity key = (Cell, Patch, Type, ID, SLA, Wooddens) with the float32 value of the printed 6-digit numbers,
or (Cell, Patch, Type, ID) with every key that is duplicated in either year dropped from the pairing.
⚠ Even 0.007 % of mis-paired keys is enough to destroy a variance statistic: my first growth-persistence numbers for
2072-2100 came out at R² 0.01-0.2 purely because a few duplicated keys paired a 5 m tree with a 20 m tree. After dropping
duplicated keys the same statistic is 0.84-0.92 (§6).

## 2. Fate of every living stem, y → y+1

[MEASURED] Whole Germany, 11 transitions, 19.2-21.6 M living stems each:

| | range over transitions |
|---|---|
| present at y+1, still living | 92.5-98.0 % |
| present at y+1, flagged dead (died during y+1) | 2.0-7.5 % |
| **absent at y+1** | **0.004-0.11 %** (subsample 30-yr mean: 0.050 % H1, 0.040 % S44, 0.038 % S100) |
| absent stems with height < 5.5 m at y | 99.2-100 % |
| absent stems with height ≥ 10 m | **0** in every transition |
| flagged-dead stems (isdead = 1 at y) present at y+1 | 0 (historic, 2015-17), 1-2 per year after 2071 (ID reuse, §1) |
| whole (Cell, Year) blocks missing | **0** (9 065 cells every year, 907 of 907 in every subsample year; cells 31-32 never appear, rock/ice) |

* Silent disappearance is **threshold flicker at 5 m, not death**: height can decrease (0.6-2.2 % of surviving stems per
  year shrink), a stem dips below 5 m and is no longer printed. Over 30 years 13 208 (H1), 9 027, 8 931 keys have a gap;
  height before the gap median 5.10 m; gaps last 2-29 years; about 40 % of the vanished stems reappear within the window.
* [SOURCE] Deaths are never silent: every kill path sets `tree->isdead = TRUE` in year y, the annual output is written, and
  only then are dead trees deleted (`iterateyear.c:293-306`). So a stem is printed once with `isdead = 1`, with the growth of
  its death year, and is never seen again.

## 3. Death channels

[SOURCE] In this configuration (`"fire": "fire"`, `individual: true`) a tree can be killed in year y by, in order:
(a) the allocation kill (negative pools, `allocation_tree`), (b) the hazard draw `erand48 < mort` in
`mortality_tree_ind.c:152`, where the printed `mort` already includes the hard kills (`mort = 1` when the counter reaches 5
or leaf carbon < sapling leaf carbon), (c) the bioclimatic `survive()` test, (d) **fire**: `annual_natural.c:121` calls
`firepft()` (not `firepft_ind`), which calls `fire_tree_ind()` for every tree: **each living tree dies independently with
probability (1 − resist) × fire_frac and is flagged `isdead`** (pools kept until deletion; the whole-patch `delpft` in
`firepft.c` is inside `#if 0`). `fire_prob.c` **never returns less than 0.001** (whenever fire_frac < 0.001 or
above-ground litter < 200 gC/m²). resist = 0.12 (types 0, 1, 4, 6), 0.3 (3 beech, 5), 0.5 (2). So there is a **background
fire kill of 0.05-0.088 % per tree per year everywhere**. A fire-killed tree looks exactly like any other flagged death
(same row, printed `mort` = its hazard, not 1).

[MEASURED] Subsample, 30 years per window (62.7 / 55.1 / 57.2 M tree rows):

| | H1 1985-2014 | S44 2015-2044 | S100 2071-2100 |
|---|---|---|---|
| mean isdead | 0.0320 | 0.0347 | 0.0333 |
| mean printed hazard `mort` | 0.0306 | 0.0334 | 0.0314 |
| **share of deaths described by the printed hazard** (Σmort/Σisdead) | **0.954** | **0.962** | **0.945** |
| of all deaths: hard kills (`mort = 1`; ~all are counter = 5) | 0.358 (0.04-0.72 by year) | 0.410 (0.06-0.71) | 0.395 (0.03-0.63) |
| of all deaths: expected from the 0.001 fire floor | 0.021 | 0.020 | 0.020 |
| residual excess beyond hazard + fire floor | 0.025 | 0.019 | 0.035 |
| bioclimatic whole-(cell, PFT) die-offs | 0 | 0 | 0 |

* Whole Germany per year: hazard share 0.898-0.987.
  ⇒ **In Germany the printed hazard describes ~95 % of deaths, not the ~76 % of the global runs.**
* [MEASURED] **The residual is not patch-clustered**, so it is not stand-replacing fire. Test: simulate every tree dying
  independently with its hazard + the fire floor, compare patch-level death counts with observed, per year, 5 replicates.
  Variance of deaths per patch observed/null: median ratio 1.018 (H1), 1.012, 1.021; patch-years with ≥ 50 % of ≥ 3 stems
  killed: 62 773 deaths observed vs 62 583 null over 30 years (H1), 52 202 vs 52 045 (S44), 36 650 vs 36 311 (S100).
  The residual (2-3.5 % of deaths) is diffuse. ~~Not separable from the table~~ **— superseded by §9.3: it is fire above the
  0.001 floor** (year-to-year correlation with the run's own fire carbon flux 0.976 over 1 133 member-years, slope 1.02,
  intercept at the floor), and allocation kills are ≈ 0.
* [MEASURED] The printed `mort_*` are **not garbage** in the first year of any restarted segment (1985, 2015, 2071), nor in any
  other year: out-of-range values 0, `mort ≠ min(1, Σ parts)` (excluding hard kills) 0, `mort_age` ≠ recomputation from
  `Age − 1` and the per-type longevity 0, on all ~21 M rows of each of the 14 whole-Germany years.

## 4. Recruitment (a key present at y+1 and absent at y)

[MEASURED] Whole Germany: 0.53-0.83 M recruits per year = 2.5-4.0 % of the living stems (subsample 30-yr: 3.2 / 2.9 /
3.3 %).
* Per patch-year: mean 0.24-0.37, var/mean 1.27-1.29 (overdispersed), up to 7+ per patch; per cell-year median 59-91,
  minimum 25-39, **never zero**.
* Height at entry: median 5.06-5.09 m, q99 5.4-5.6 m, max 6.3 m. **Age at entry: median 12-13 yr (historic), 9-10 yr
  (2071+)**, q95 32-40 yr, max ~160. So a recruit established on average a decade earlier.
* 2-3 % of recruits are already flagged dead in their first printed year. 0.1-0.7 % of "recruits" are flicker re-entries of
  a key seen two years earlier.
* PFT mix: beech (type 3) is 81-84 % of recruits vs 88-90 % of living stems; types 1 and 2 are over-represented among
  recruits (e.g. 2073: 1: 7.8 %, 2: 12.6 % of recruits).
* **Gaps drive recruitment strongly.** Mean recruits next year by the patch's living crown cover (Σ fpc_ind) at y
  (subsample H1, 6.6 M patch-years): 1.71 (0-0.1), 1.02 (0.1-0.25), 0.33 (0.25-0.5), 0.11 (0.5-0.75). Correlation within
  cell-year −0.37 (all three windows). Event study (patch loses ≥ 50 % of its crown cover in one year, 48-61 k events per
  window): recruits entering the next year jump from 0.29-0.32 (the year before) to **0.92-1.06 immediately** and decay
  over ~20 years (0.60 at +10, 0.42 at +15, 0.30 at +20, H1). ⇒ the model carries an **invisible pool of sub-5 m trees
  that is released by a gap within one year**. Deaths counted as numbers barely correlate with later recruitment
  (−0.03..0.00); lost crown cover does (+0.10 at lag 0 falling to +0.01 at lag 20).
* **Recruit traits are local to the cell, not only PFT-typical** (subsample, standing trees at the window's first year vs
  recruits of the next 10 years, per (cell, type) group with ≥ 30 standing and ≥ 10 recruits; ~3 200 groups, 0.53-0.67 M
  recruits). Slope of the recruits' cell-mean trait on the standing trees' cell-mean trait, across cells, within type, vs a
  permutation null (SD 0.03-0.13):
  * beech (type 3, 905 cells): SLA 0.85-0.95, Wooddens 0.91-1.07, D95max 0.88-0.91, minwscal 0.71-0.73, Longevity 0.86-0.93;
    correlation 0.68-0.99;
  * minority types: 0.03-0.79, mostly 0.1-0.7 (weaker; smaller between-cell spread and fewer stems).
  * Slopes on the top-10 %-biomass trees only are *lower* (beech 0.31-0.92) than on all standing trees.
  * A nearest-neighbour test (recruit vs a uniform draw from the type's interval) gives 89 % of recruits closer than the
    uniform draw, but a random same-type tree from **another** cell is as close as the own cell (50.4-51.2 %) — that test
    has no power to see locality; the group-mean test above does.
  ⇒ recruit traits can be sampled from **the cell's own living same-type trees** (plus noise); a PFT-interval draw is wrong
  and a PFT-wide pool loses the between-cell signal.

## 5. Hidden state

* [MEASURED] The consecutive-bad-growth-years counter is recovered exactly from each row:
  `c = max(0, ceil(mort_npp / mort_max − 1e-9) − 1)`, `mort_max = 10^(wdmort_1[Type] + wdmort_2[Type] / (Wooddens/1e6))`
  (`test/testitems/references/S_pft_mortality_params.csv`). Gates on every year: `mort_npp < 1` on 100.000 % of living
  stems (every row informative); forbidden-band rate **0.000 %**; the recursion `c(y+1) ∈ {0, c(y)+1}` holds on all but
  30 of 60 682 568 pairs (H1), 77 of 53 121 478 (S44), 699 of 55 294 597 (S100).
* [MEASURED] It matters: 1.8-32.8 % of living stems carry c ≥ 1 depending on the year (mean 11-12 %), it moves in
  Germany-wide synchronised waves (e.g. 988 528 stems at c = 4 in 1985 → 948 731 hard kills in 1986 = 68 % of that year's
  deaths), and hard kills are 36-41 % of all deaths over 30 years.
* [SOURCE] Carried by the C and not in the table: all trees < 5 m (the sub-5 m pool that feeds recruitment; not measured
  here — at the global Hainich cell it was 47 % of stems); per-tree carbon pools (leaf, root, sapwood, heartwood,
  below-ground sapwood and heartwood, debt, excess); the leaf-recycle latch `isphen`; the within-year stress accumulators
  (reset on a fixed calendar day, so they are annual, not multi-year); the per-cell **seedbank** (top-biomass trees of the
  last 50 years) that inheritance draws from; litter and `fire_sum` (fire danger); soil water, temperature, carbon; the
  20-year climate buffer used by establishment and survival; the per-PFT ID counters; each cell's random-number state.

## 6. Patch and stand structure; how deterministic growth is

* [MEASURED] 250 patches per cell (Patch 0-249). Living > 5 m stems per patch: median 8-9, q01 2, q99 18-20, max 31-32;
  patches with no living > 5 m tree 0.005-0.03 %.
* Grass: **exactly one row per (cell, patch)** of type 8 (C3 grass; type 9 in ~300 patches), ID = Height = Age = 0, all
  tree traits and hazards 0, carrying agb, vegc, LAI, fpc_ind, D95, beta_root, SLA, npp, transp. So the table has a
  per-patch grass state.
* Growth persistence (surviving stems in three consecutive years, duplicated keys dropped, subsample, per year):
  **R² of this year's biomass change on last year's 0.82-0.95** (all windows, e.g. H1 0.83-0.92, S44 0.90-0.95, S100
  0.84-0.92); the zero-parameter copy "Δ next = Δ this" scores R² 0.70-0.91. Height change is much less persistent
  (R² 0.09-0.41). Biomass changes sign between consecutive years on only 2-5 % of stems; 1.2-4.5 % of stems lose biomass.
* Height is a function of state: log Height on log agb, log Wooddens, log SLA by type R² 0.992-0.9998.

## 7. State vs annual flux (matched living stems, lag-1 R² of the column on itself, whole Germany 1985/2015/2071)

| column | lag-1 R² | nondecreasing | role |
|---|---|---|---|
| Height | 0.999 | 98-99 % | state (derived from agb + traits) |
| agb, vegc | 0.9998 | 96-99 % | state |
| fpc_ind | 0.9997 | 85-94 % | state |
| LAI | 0.992-0.995 | 43-66 % | state-like, oscillates |
| D95 | 0.997-0.998 | 99 % | state |
| mort_age | 0.9996 | 100 % | deterministic from Age |
| npp, transp | 0.97-0.998 | 20-74 % | annual flux, but highly persistent |
| mort_npp | 0.70-0.84 | | flux × counter (carries the hidden counter) |
| wscal_mean, mort_water, mort_temp | 0.00-0.37 | | annual flux (mostly exactly 1 / 0); mort_water was 0 for all matched stems in 2071-72 |
| mort | 0.10-0.41 | | annual |

## 8. What failed or was not done

* ~~One member only~~ — §9 extends the subsample battery to all 40 member-windows; the whole-Germany numbers (§1-§2, §6-§7)
  remain MPI seed 1 only.
* Fire deaths cannot be identified per tree; the floor (exact, from the C), the absence of patch clustering and (§9.3) the
  year-to-year match of the residual with the fire flux are measured. Per-patch fire_frac is not observable.
* The ID-counter mechanism for duplicated keys is inferred from the source, not traced per tree.
* The sub-5 m pool size in Germany is unmeasured (it needs a re-run with the all-heights writer switch).
* The event study counts a patch once per event (patches with several events contribute several times).
* The first-pass growth-persistence values in `results/sub_*.json` / `full_transitions_*.json` are **corrupted by
  duplicated keys** and superseded by `results/extras_growth_*.json`.

## 9. Cross-member robustness (added 2026-10-01): all 40 member-windows

[MEASURED] Same battery as §2-§5 (`stage_analyze_sub`), run on each converted dev parquet (`Cell % 10 == 0`, 907 cells,
30 years, 29 transitions per window). Gate: on MPI ssp370 s1 2015-2044 the converted-parquet run reproduces the earlier
raw-CSV run exactly (0 differences in live/recruit/absent/death counts and hazard shares; identical key histories).
Script stage `members` / `summarize_members`; table `results/members/members_summary.csv` (one row per member-window);
per-member detail `results/members/sub_<member>.json`. Ranges below are min/median/max over the 10 member-windows of each
window type (2 GCMs × 4 or 1 scenarios × 2 seeds), excluding the truncated MPI ssp370 s2 3071 member where it matters.

### 9.1 Everything structural holds in every member

| quantity | 1985-2014 | 2015-2044 | 2071-2100 | 3071-3100 |
|---|---|---|---|---|
| census holes (cell-years missing) | 0 | 0 | 0 | 0 (except the truncated member) |
| Age +1 on matched pairs; six traits bit-identical | 100 % | 100 % | 100 % | 100 % |
| living stems: alive / flagged dead next year | 0.967 / 0.032 | 0.965 / 0.034 | 0.966 / 0.034 | 0.966 / 0.034 |
| absent next year | 0.027-0.051 % | 0.024-0.064 % | 0.038-0.048 % | 0.026-0.07 % |
| absent stems with H < 5.5 m / with H ≥ 10 m | 99.9 % / 0 | 99.9 % / 0 | 99.9 % / 0 | 99.9 % / 0 |
| flagged-dead keys seen again next year (ID reuse) | 0 | 0-4 | 4-22 | 0-2 |
| key excess rows per year, (Cell,Patch,Type,ID) | 1.2-3.3 | 7.7-13.6 | 106-219 | 0-9 |
| same with SLA + Wooddens added | 0 | 0 | 0 | 0 |
| printed hazard share of deaths (30 yr) | 0.954-0.960 | 0.958-0.965 | 0.936-0.958 | 0.925-0.965 |
| hard kills (mort = 1) share of deaths | 0.358-0.391 | 0.375-0.410 | 0.368-0.395 | 0.338-0.400 |
| fire-floor expectation share of deaths | 0.021 | 0.019-0.020 | 0.019-0.022 | 0.019-0.022 |
| residual share of deaths (= fire above floor, §9.3) | 0.019-0.025 | 0.016-0.022 | 0.021-0.045 | 0.015-0.055 |
| bioclimatic whole-(cell,PFT) die-offs | 0 | 0-1 | 0 | 0 |
| mort_* garbage, first year or any year | 0 | 0 | 0 | 0 |
| counter: forbidden-band rate / informative rows | 0 / 100 % | 0 / 100 % | 0 / 100 % | 0 / 100 % |
| counter recursion violations / pairs | 30-53 / ~59 M | 59-407 / ~52 M | 90-4 683 / ~51 M | 55-5 616 / ~53 M |
| stems with counter ≥ 1 (mean over years) | 9.4-11.2 % | 10.6-13.5 % | 11.3-13.0 % | 10.8-14.6 % |
| recruits per year / living stems | 3.1-3.2 % | 2.9-3.2 % | 3.3-3.8 % | 2.8-3.8 % |
| recruits per patch-year: mean, var/mean | 0.28-0.30, 1.27-1.29 | 0.23-0.25, 1.26-1.29 | 0.25-0.30, 1.29-1.32 | 0.26-0.32, 1.27-1.31 |
| cell-years with zero recruits | 0 | 0 | 0 | 0 |
| recruits flagged dead in first printed year | 2.2 % | 2.1-2.3 % | 1.9-2.0 % | 2.0-2.1 % |
| within-cell-year corr(recruits next yr, patch live fpc) | −0.37..−0.38 | −0.37..−0.38 | −0.38..−0.40 | −0.34..−0.39 |
| event study (patch loses ≥ 50 % crown cover): recruits next yr, year before → year of → +10 → +20 | 0.33 → 1.07 → 0.60 → 0.27 | 0.29 → 0.95 → 0.52 → 0.25 | 0.27 → 0.90 → 0.56 → 0.26 | 0.27 → 0.92 → 0.59 → 0.30 |

The counter recursion violations rise to 0.002-0.01 % of pairs in the late windows of the ACCESS ssp370/ssp245 members
(4 663-5 616); these are the ID-reuse pairs (the same windows have the most duplicated keys), not a failure of the algebra.

### 9.2 ssp245 was run with a DIFFERENT C binary (the inheritance fix) — the other scenarios were not

* [SOURCE] Every `lpjml.*.out` log prints its build. **All ssp245 segments of both GCMs and both seeds (2015-3100) ran
  `Version 5.6.004 (Feb 5 2026)`**; every Historical, ssp126 and ssp370 segment ran `(Dec 17 2025)` (MPI ssp245 logs dated
  2026-02-19..25; ACCESS ssp245 2026-02-05/06, after two aborted Dec-17 attempts in the same directory). The only source
  commit between the two builds is `b2e5ca9` (2026-01-28, one line in `new_tree.c`: `treepar=pft->par->data;` after an
  inherited recruit switches PFT), assuming the Feb 5 build had no uncommitted changes [ASSUMPTION]. Pre-fix, an inherited
  recruit takes its Wooddens/D95max reflection bounds **and its sapling allocation fractions** (`falloc`, `new_tree.c:220`)
  from the establishing slot's PFT.
* [MEASURED] The signature fades exactly as that predicts. Share of recruits with Wooddens outside their own Type's interval:
  ssp126/ssp370 2015-44 0.033-0.046, 2071-2100 0.037-0.050, 3071-3100 0.031-0.039; **ssp245 2015-44 0.019-0.027, 2071-2100
  0.009-0.012, 3071-3100 0.0000** (all four ssp245 members; D95max likewise 0.038-0.044 → 0.023-0.028 → 0.0000). The
  residue in ssp245 is inherited from parents that were themselves out of interval (the restart_2014 was written by the
  Dec 17 build).
* ⇒ **The ssp245-vs-other-scenario difference contains a model-version difference, not only climate.** Its demographic size
  is not separable here (in 2015-44, where climates are close, ssp245 recruitment, death rate and hard-kill share lie inside
  the ssp126/ssp370 range: e.g. recruits/live 0.030-0.032 vs 0.029-0.032). A builder must either exclude ssp245 from the
  response test, or give the binary version as a known covariate, or at least report ssp245 separately.

### 9.3 The death residual is fire above the 0.001 floor

* [MEASURED] Per year and member, residual death rate (deaths − Σ printed hazard − fire-floor expectation, per tree, on
  the subsample) against the run's own whole-Germany fire carbon flux scaled by the burnable stock,
  f_eff = `fire` / (`LitC` + `VegC`) from `globalflux_*.csv`: **correlation 0.976 over 1 133 member-years** (per member
  0.907-0.985), **slope 1.017, intercept −0.00085** (f_eff at the floor is 0.00089-0.0011, so the residual is ≈ 0 exactly
  where fire is at its floor: residual at the minimum-f_eff year −0.00012). The printed hazard is uncorrelated with f_eff
  (−0.08). Stage `fire_check`; rows in `results/members/fire_vs_residual_by_year.csv`.
* [MEASURED] It is driven by summer drought: per cell-year (subsample, all non-3071 members, 761 880 cell-years joined to the
  climate table) the residual rate by June-August precipitation sextile-bins: 0.0019 (< 124 mm), 0.0014, 0.0010, 0.0006,
  0.0003, 0.00013 (> 330 mm), while the hazard rate is flat (0.031-0.034). Correlation with JJA precipitation −0.14, with
  JJA temperature +0.12 (cell-year level, noisy because the rate is per mille). The top 10 % of (member, cell) 30-yr
  totals hold 29 % of the positive residual (moderately concentrated, not a few fire cells). Stage `cellyear_deaths`;
  `results/members/cellyear_deaths.parquet` (per member, Cell, Year: n, deaths, hazard, floor, hard, resid).
* ⇒ **Total fire share of deaths ≈ 3.5-7.5 %** (floor 2 % + above-floor 1.5-5.5 %), rising in the late warm windows
  (residual share 0.016-0.025 in 1985-2044 → up to 0.045 in ssp370 2071-2100 and 0.055 in 3071-3100). This is a
  **climate-responsive death channel the printed hazard does not contain**; small, but it grows with warming. Allocation
  kills are ≈ 0 (no residual left at the floor).

### 9.4 The truncated member, measured

MPI ssp370 seed 2 `ind_3100.csv` holds 3071, 3072 and **half of 3073** (cells up to ~4505; 456 of the 907 subsample cells
missing in 3073). A naive pairing reads the 3072→3073 transition as **51 % of living stems vanishing** — exactly the
whole-block trap; its `fate_absent` of 0.254 in `members_summary.csv` is that artefact. Use 3071→3072 only, or drop it.
