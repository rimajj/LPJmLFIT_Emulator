# 0343 — Why the stand map's warming response is worse on cells it never saw: four one-change arms (pre-registration)

* **Status:** accepted 2026-10-15 — measures, arms, expectations and decision rule written BEFORE any arm was trained.
  Results: §6, added after the run.
* **Depends on:** ADR 0342 (the experiment, data, held-out models/cells, second run = seed 3; arm `main2` is the
  baseline here), ADR 0341 (a global run: every cell is new to the maps).
* **Code:** `scripts/clu_emu_maps.py` (arms below; `train` / `predict` / `score` stages unchanged otherwise),
  `scripts/diagnose_clu_stand_damping.py`.

## 1. The finding that motivates it (diagnostic, after ADR 0342 §8)

`diagnose_clu_stand_damping.py` splits the per-cell response slope (emulated 2071–2100 minus 1990–2019 change
regressed on the original's, seed 2) by training/held-out climate model × training/held-out cell. Arm `main2`,
legs without ssp126:

| quantity | train model × train cells | test model × train cells | train model × held-out cells | test model × held-out cells |
|---|---|---|---|---|
| leaf area | 0.87–0.89 | 0.81–0.82 | 0.56–0.63 | 0.53–0.58 |
| tree cover | 0.92 | 0.85–0.87 | 0.63–0.69 | 0.57–0.62 |
| vegetation carbon | 0.81–0.84 | 0.73–0.80 | 0.54–0.65 | 0.51–0.65 |

(range = CO2 fixed / rising). The damping is a **cell** effect, not a climate-model effect: on cells it trained on
the map follows the original nearly as well under an unseen climate model as under a seen one; on the 135 held-out
cells it loses ~0.3 of slope even under seen models. In error terms (held-out cells, the 8 test legs = MPI/IPSL ×
ssp370/585 × CO2 rising/fixed): leaf-area RMSE **1.42–2.07×** the second run's (median 1.82), tree cover
**1.80–2.83×** (median 2.20), vegetation carbon 0.82–0.98× (fine). On all 674 cells the same legs give 1.03–1.25×
and 1.09–1.39×. A global run consists only of unseen cells, so the held-out numbers are the deployment numbers.

Note on the slope measure: the slope of prediction on truth equals `r × sd_e/sd_t`; for an ideal conditional-mean
predictor that explains a fraction R² of the cell-to-cell variance it is ≈ R², so a low slope on unseen cells can
mean MISSING INFORMATION rather than a bias. The primary measure below is therefore the error (RMSE) relative to a
second run, which cannot be improved by merely inflating the predicted change.

## 2. Hypotheses → one arm each (each differs from `main2` in ONE thing; same legs, cells, rows, seed)

| arm | change | hypothesis it tests |
|---|---|---|
| `m2_leaf` | LightGBM `min_data_in_leaf` 20 → 20 000 (a cell has ~2 000 training rows ⇒ every leaf spans ≥ ~10 cells) | the map memorises each training cell (its per-cell constant anchors identify it) instead of learning a response that transfers |
| `m2_nogeo` | drop lat, lon, soil code from the features | geographic coordinates let the map interpolate neighbours' responses, which smooths a held-out cell's |
| `m2_sens` | + the cell's own year-to-year sensitivity in its 1990–2019 historical run: for leaf area, tree cover and vegetation carbon, the coefficients of a regression of the detrended yearly value on detrended yearly mean temperature and climatic water balance, and the detrended yearly standard deviation (9 features) | the response is set by which stress limits the cell, information the 30-yr climate means and the state anchors do not carry |
| `m2_trend` | + the cell's own linear trend 1990–2019 of leaf area, tree cover and vegetation carbon in its historical run (3 features) | the cell's realised response to the historical warming and CO2 rise predicts its future response |

All four features come from the original's historical run, which a deployment needs anyway for the anchors (ADR
0341), so none uses future output.

## 3. Measures (scored by `clu_emu_maps.py score`, `eval/response_maps.csv`)

Per arm, over the 8 test legs (MPI-ESM1-2-HR, IPSL-CM6A-LR × ssp370, ssp585, ssp370co2fix, ssp585co2fix):

* **primary:** median over the 8 legs of the per-cell RMSE ratio to the second run on the **135 held-out cells**,
  for leaf area and tree cover. `main2`: **1.82** and **2.20**.
* secondary: the same for vegetation carbon (`main2` 0.90 median); the same on all 674 cells (`main2` leaf area
  1.11, tree cover 1.24, vegetation carbon 0.70); per-cell slope and r on held-out cells; the global change ratio.

## 4. Decision rule and expectations

* An arm **helps** if its held-out primary median drops by ≥ 15 % for BOTH leaf area and tree cover, while its
  all-cell medians do not rise by more than 0.05 and the held-out vegetation-carbon median does not rise by more
  than 0.05. Several arms helping ⇒ combine them in one follow-up arm, scored the same way (no new criterion).
* **Expectations (written before):** `m2_leaf` −5 to −15 % held-out, all-cell slightly worse; `m2_nogeo` within
  ±10 %; `m2_sens` −10 to −20 %; `m2_trend` the largest, ≥ −15 %.
* **Falsifier of the "missing information" reading:** if neither `m2_sens` nor `m2_trend` lowers either primary
  median by ≥ 10 %, the per-cell information is not in the historical run's yearly behaviour either, and the next
  lever is more training cells (a denser clustering), not features.

## 5. Not changed

The daily model, the structure-map quantities' scoring, ADR 0342's results and verdict. If an arm helps, its stand
is fed through the daily model (as ADR 0342 §7.3 `NC_B3`) in a separate, stated step.

## 6. Results

(added after the run)
