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

## 6. Results (2026-10-15, jobs 2510636–44; `scripts/summarize_clu_arms.py`)

Median over the 8 test legs of the per-cell error relative to a second run:

| arm | leaf area, held-out cells | tree cover, held-out | veg. carbon, held-out | leaf area / tree cover / veg. carbon, all cells |
|---|---|---|---|---|
| `main2` (baseline) | 1.82 | 2.20 | 0.90 | 1.11 / 1.24 / 0.70 |
| `m2_leaf` | 1.86 (+2.0 %) | 2.13 (−2.8 %) | 0.93 | 1.24 / 1.37 / 0.78 |
| `m2_nogeo` | 1.78 (−2.4 %) | 2.13 (−2.9 %) | 0.92 | 1.09 / 1.22 / 0.71 |
| `m2_sens` | 1.91 (+4.9 %) | 2.27 (+3.4 %) | 0.92 | 1.13 / 1.27 / 0.70 |
| `m2_trend` | 1.90 (+4.3 %) | 2.19 (−0.4 %) | 0.91 | 1.13 / 1.24 / 0.70 |
| second run | 1 | 1 | 1 | 1 |

Held-out per-cell r (leaf area): `main2` 0.79, arms 0.74–0.81; second run 0.94.

**No arm helps** (none reaches −15 %, none even −5 %). `m2_leaf` makes the training cells worse (+0.13 all-cell)
without helping unseen ones, so memorisation is not the cause; coordinates neither help nor hurt; the expectations
for `m2_sens` (−10 to −20 %) and `m2_trend` (≥ −15 %) were wrong. **The §4 falsifier fired:** the per-cell
information that sets the response is not in the historical run's yearly behaviour either (the features themselves
are reproducible: r 0.67–0.95 between seeds 2 and 3 for leaf area / tree cover). Per §4 the next lever is more
training cells — §7 checks whether that can work before any new run of the original is made.

## 7. Amendment (2026-10-15, written after §6, before the runs it governs): learning curve in training cells

Arms `m2_half` and `m2_quarter` = `main2` trained on the training cells with `Cell % 2 == 0` (≈ 270) and
`Cell % 4 == 0` (≈ 135); everything else identical; scored on the same 135 held-out cells.
**Reading, stated before:** if held-out error falls by ≥ 10 % from quarter → half AND from half → full (539 cells),
error is still falling with cell count and a denser clustering (more training regions) is worth new original-model
runs; extrapolate the step per doubling. If half → full gains < 5 %, more cells of this kind will not close the gap
and the information is missing from the inputs (e.g. soil / state detail a region-mean cell does not carry).
**Expectation:** quarter → half −10 to −15 %, half → full −5 to −10 % (diminishing).

## 8. Results of §7 (jobs 2510785–91)

Held-out-cell error relative to a second run (median of the 8 test legs), by number of training cells:

| training cells | leaf area | tree cover | veg. carbon |
|---|---|---|---|
| 135 (`m2_quarter`) | 2.22 | 2.60 | 1.03 |
| 269 (`m2_half`) | 2.07 (−6.9 %) | 2.34 (−10.0 %) | 1.01 (−2.7 %) |
| 539 (`main2`) | 1.82 (−11.9 %) | 2.20 (−6.3 %) | 0.90 (−10.4 %) |

**Reading against §7:** in between the two stated outcomes. Error still falls with every doubling (−6 to −12 %,
not diminishing for leaf area), so more training cells DO help; but neither quantity fell ≥ 10 % on both steps.
Extrapolating ~−9 % per doubling, reaching 1.2× a second run for leaf area (1.5× for tree cover) needs ~4.5 more
doublings, i.e. ~12 000 training regions — the scale of a full-grid training set, not of a denser clustering
(one split, one seed: the per-step numbers carry a few per cent of noise). Expectation (quarter → half −10 to
−15 %, half → full −5 to −10 %): partly wrong — the gain did not diminish for leaf area.

## 9. Conclusion

1. The stand map's weak response on unseen cells is not memorisation (`m2_leaf`), not coordinates (`m2_nogeo`), and
   not fixable from the cell's own historical behaviour (`m2_sens`, `m2_trend`) — all within ±5 %.
2. It is a sample-size effect: 539 region-cells are too few examples of how a place responds; the error falls
   ~6–12 % per doubling of training cells.
3. Consequence for deployment: an emulator trained on a full-grid run of the original (as ADR 0341, every land cell
   in training, scenarios held out) never meets an unseen cell on that grid, so this miss does not apply to it;
   it applies to an emulator trained on clustered runs and then run on the full grid. The warming-response proof of
   ADR 0342 should therefore be repeated with training on many more cells (a full-grid nitrogen-on run, or the
   distributed 1-patch clustering with thousands of cells) if it is to support a global deployment.
