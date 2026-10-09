# Porting the Germany per-tree stepper (TAB) to the global venue — the data contract and its blockers

Line X, 2026-10-09. Prerequisite for the recursive per-tree arms A3 (dataset aggregation), A4 (free-run calibration)
and A6 (the margin / NPP route) on the global venue of ADR 0315: all three are built on TAB, and TAB has only ever run
on the Germany tables. This note is the map of what the TAB chain reads, what is Germany-specific, and the minimum
change set. Source: a read of every module in the chain (`explore_de_{engine,sh_registry,sh_climate_ext,sh_rules,
sh_trans,sh_patch,sh_init,sh_patchheads,tab_features,tab_heads,tab_eval,tab_stepper,tab_g2,tab_margin,grass2,
hidden_cover,gquant,nppmodel,nppmodel2,gsign_info,bmdelta,reference,score,sh_eval}.py`), file:line references
current at commit `df2b9b2a`.

## 1. Verdict

`XDE_ROOT` alone does **not** port it. The chain is registry-driven and most of its contract can be met by building
a new data root in the Germany format, but eight things need code or a remodel.

| # | blocker | where | fix |
|---|---|---|---|
| B1 | `Cell` cast to **Int16** in ~20 places; global ids reach 67 419 | `engine.py:96`, `sh_trans.py:466`, `sh_patch.py:131,237`, `sh_init.py:159`, `sh_patchheads.py:170,219,240`, `tab_features.py:182,243,369,449`, `tab_stepper.py:636,640,739`, `tab_g2.py:51`, `tab_heads.py:405`, `grass2.py:102,287`, `nppmodel2.py:60`, `gsign_info.py:136,139` | renumber the dev cells to 0..N−1 in the new root (`registry/cell_map.parquet`), map back before scoring — no code change |
| B2 | `LAST_SIM_YEAR = 2070` (a Germany owner decision: its 2071+ truth was unusable) | `engine.py:91,199,617` | env override to 2100 |
| B3 | recruit types `RECR_TYPES = [1..5]` ⇒ Types 0 and 6 can never recruit | `tab_features.py:327` | → `[0..6]` (env / derived from data) |
| B4 | ONE grass type (`GRASS_TYPES = [8]`) in every grass model and the cover closure; global has 7, 8, 9 | `tab_features.py:85`, `tab_heads.py:368-390`, `tab_stepper.py:720-751`, `grass2.py:49`, closure | **remodel**: one head per grass or a multi-grass closure; until then grasses 7/9 stay frozen at the start value |
| B5 | SH4 reads the trans file of y−1 for the first year of an ssp window — there is no 2070 table | `sh_patch.py:226-231` | null `n_recruit_y` when y−1 is absent; **SH4 crashes on every global ssp member without it** |
| B6 | SH3/SH4 treat 2014 as the chain predecessor of the ssp window (Germany's w2015) | `sh_trans.py:265,346-355` | `pair_ok = False` for 2071 in the segments table (data fix) |
| B7 | the margin arm's weather frames are a cell-year aggregate of the TRUTH table ⇒ none exist for 2015–2070 | `nppmodel2.py:57-62`, `gsign_info.py:55-83`; also `lwdown` (global has `lwnet`) `gsign_info.py:39`, `range(4)` :134 | rebuild the frames from climate for every year |
| B8 | rule parameters (SH2) are read from the LOCAL `par/` files | `sh_rules.py:127,200-202` | see §3 — the Feb/May builds match on every checkable value |

Smaller: `tab_eval.py:475` traits fit hard-codes build `"dec2025"`; `tab_features.py:477` audit hard-codes 2014 and an
ssp member with a 2014 row; split names default to `"DEV-A"` across grass2 / hidden_cover / gquant / nppmodel2
(`MDIR` `nppmodel2.py:43`) — name the global split `DEV-A` in its own root; `nppmodel.py:32-34` hard-codes MPI/ACCESS
member names; every `submit` hard-codes account / partition / 4 h; the Germany scorer (`explore_de_reference` /
`explore_de_score`) does not transfer (seed pairing `3 − ts` at `reference.py:413`, NPATCH 250, w2015) — score with
`explore_glob_eval.reduce/score` after mapping Cell back.

## 2. The data root to construct (one `XDE_ROOT`, no per-stage overrides)

1. `registry/cell_map.parquet` (Cell16, Cell_orig) — dev cells, `Cell % 10 == 0`, not rock.
2. `ind_dev/<member>.parquet` — the 29-column stock schema, Cell16; member names `GFDL-ESM4_Historical_s<k>_h1985`,
   `GFDL-ESM4_ssp<x>_s<k>_w2071` (SH2 reads them BY NAME, `sh_rules.py:125`). Feb + May GFDL members only (the GSWP3
   members have no Historical parent and a 30-column layout).
3. `registry/members.parquet` — member, gcm, scen (`"Historical"` capitalised), seed, win, npatch = 25,
   years_complete, usable_pair_years, ind_path, ind_dev_path, build, `bin_feb2026 = 1`, `rh_on = 1`, excluded = False,
   exclusion_reason, excluded_by, truncated, src_csv.
4. `registry/segments.parquet` — per (gcm, traj, seed, Year): Historical 1985–2014; each ssp trajectory 1985–2100;
   rh_on 1, bin_feb2026 1, clim_scen (`Historical` ≤ 2014), clim_year, clim_recycled False, excluded False,
   `pair_ok` = Historical 1985–2013, ssp 2072–2099 (2071 False, B6).
5. `registry/folds.parquet` (existing 5° blocks and folds, Cell16), `registry/splits.parquet` (Germany schema; split
   `DEV-A` = train seeds 2,3,4,6 Historical + ssp126/245; test_truth 8; test_ref 7).
6. `climate/cell_year.parquet` — the four GFDL files, `historical` → `Historical`, Cell16.
7. `shared/climate/cell_year_ext.parquet` — + excluded / exclusion_reason / truth_usable and the anomalies the global
   tables lack: `anom_{tcold_month,twarm_month,gdd5}_tr20`, `anom_tstress_pft0..6`, `anom_vpd_jja_eff`.
8. `shared/climate/clim8514.parquet` — (gcm, Cell) + the 1985–2014 mean of every numeric column.
9. `climate/cell_static.parquet` — Cell, soil_code, lon, lat.

Stage order (all with the new `XDE_ROOT`, split `DEV-A`): SH2 `params`, `allometry` → SH3 `build` (Historical first)
→ SH4 `build` (needs B5) → SH5 `build --start …_1985` and `_2014` → SH13 `prep`, `fit` → A1 `samples`, `recruits` →
A2–A5 `train --head gsign gmag_neg gmag_pos dagb dvegc dlai dfpc dd95 surv surv_phys grass rtype`, `traits` → A6 `prep`
→ engine `submit --start 1985 --end 2100 --legs ssp126,ssp245,ssp370` (needs B2) → global scorer.

## 3. Are the rule parameters the ones the Feb/May runs used? (B8, measured)

Billing's runs include `param_lpjmlfit_fulldiv.js` from `/home/billing/LPJmLFit_global_final` (run scripts
`…/global/run/FD_EF/run_GCM_{hist,future}.sh`, `lpjfolder=`), which includes `par/{lpjparam_fit,soil_20m,
pft_lpjmlfit}.js`. Parsed with `cpp -P` and compared to the local `/home/jamirp/lpjml56fit` files: **155 PFT values and
5 global values differ** (e.g. longevity `age` 400 → 750 boreal needleleaved, 125 → 150 boreal broadleaved
summergreen; `k_root` scalar → sampled interval; `mort_temp_factor` 5 → 4; `max_age` 50 → 10; `n_max` 7 → 6). But
`pft_lpjmlfit.js` was modified **2026-10-08** and `lpjparam_fit.js` **2026-09-26** — after the Feb and May runs —
and ADR 0314 §4 already established the directory is edited in place. So the live files describe the October builds.

What the Feb/May runs actually used, recovered from their own per-tree output (2014, all tree rows with
0 < mort_age < 1 and Age > 20, members 2 (Feb) and 9 (May), ~790 000 trees each):

| quantity | inferred from output | local par | Billing's live par |
|---|---|---|---|
| longevity, Types 0–4, 6 | 400.000 (min 399.9994, max 400.0006) | 400 | 400 / 750 |
| longevity, Type 5 | 125.000 | 125 | 150 |
| `k_root` | one value, 0.02, every tree | 0.02 scalar | interval 0.02–0.06 |
| `mort_temp_factor`, tropical cold limit (ADR 0314) | 5.0, 12.5 °C | 5.0, 12.5 | 4.0, 14 |

⇒ on every value checkable from the output, **the Feb and May builds ran the local parameter set**; SH2's
`params.json` built from `/home/jamirp/lpjml56fit` is the right one for them. Not checkable from output: `alpha_r`,
`alphaa`, `flam`, `resist`, `inherit_corridor`, `k_est_inherit`, `max_age`, `n_max`, `tmin`, `minwscal` bounds,
`emax`, `height_max`. Of these the rules use `resist` (fire) and the seedbank `max_age`; the trait ranges are
checkable (§4 below) when the port's trait gate runs. The October builds need their own parameter set (ADR 0315 §11).

## 4. What does not transfer at all

* **No per-tree truth 2015–2070.** The scored free run is 1985 → 2014 → fork → 2100, 115 steps (Germany: 59), of
  which 56 are driven by climate alone with no training pairs and no check year. Heads train on 1985–2013 and
  2072–2099 pairs only. The only check of the arm's state between 2014 and 2071 is the stand totals against each
  run's gridded `output_transient/` (reported, not gated, ADR 0315 §3).
* **A 2071 start state has no history** (no prior-year growth, no cover-loss lags).
* **25 patches** — per-cell statistics ~10× noisier than Germany's 250; patch-level heads see 10× fewer patch-years
  per cell.
* **Segment flags change meaning**: `rh_on = 1` must mean "humidity read correctly" although Billing's config says
  `relative_humidity: false` (it reads specific humidity, ADR 0314 §2); `bin_feb2026 = 1` must mean "after the
  stale-slot trait fix" (both builds postdate it; to be gated on the trait ranges).
