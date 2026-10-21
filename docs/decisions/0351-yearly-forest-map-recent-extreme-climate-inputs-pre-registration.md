# 0351 — Yearly forest map: recent-year and recent-extreme climate inputs, to follow drought die-offs (pre-registration)

* **Status:** pre-registered 2026-10-21, before the fits. Results: §4.
* **Follows:** ADR 0350 §4 — 94 % of the original's large one-year tree-count drops are drought die-offs shared by its
  other runs; the deployed map captures 3 % of the drop (second runs 94 %) and its 10-year aftermath gap is 4.4× a
  second run's, because its climate input is a 30-year mean. STATE.md to-do 4 named the remedy to try first:
  lagged-extreme climate inputs, not recursion (the map stays non-recursive, so its no-drift property is kept).
* **Code:** `scripts/explore_panel_yearly_drift.py fit --recent {none,y1,x10}` (default `none` = the deployed map);
  `score --recent ...` (drift of a variant); `SUFFIX=_recent<y1|x10>` for `final_structure_score.py` and
  `diagnose_extreme_year_legacy.py`; `compare_structure_variants.py _rerun _recenty1 _recentx10`.

## 1. Arms (each against the rerun of ADR 0349, which equals the deployed map to three decimals)

| arm | added inputs (all from the weather an Earth-system model supplies; none from the forest) |
|---|---|
| `y1` | the 25 climate statistics of THIS year and of LAST year as single-year values (50 columns) |
| `x10` | `y1` + over the last 10 years (this year included): the minimum of annual rain, growing-season rain, annual / growing-season / driest-3-month water balance, relative humidity; the maximum of potential evaporation, days above 30 °C, longest dry spell, growing-season air dryness, last-10-day air dryness, mean temperature; and the number of years since the driest year (lowest annual water balance) of those 10 (13 columns) |

`y1` tests whether the drop year itself is learnable; `x10` adds the memory that should carry the aftermath. Not
one-variable against each other by design (`x10` contains `y1`), so the reading is nested: `y1` against the rerun,
`x10` against `y1`.

## 2. Pre-registered measures and verdict

* **Primary — the die-off (ADR 0350's diagnostic, shared tree-count events):** an arm FIXES the miss if drop capture
  ≥ 0.30 (rerun 0.031; second runs 0.94) AND the aftermath gap ≤ 2.0× the second runs' (rerun 4.4×).
* **Must not get worse (relaxed standard, `compare_structure_variants.py`, dense by the anchor):** median ratio
  arm / rerun ≤ 1.02 on every quantity and group; no criterion passing in the rerun lost.
* **No drift (ADR 0330 measure, `score` stage):** median drift of tree count and of biomass per tree (dense) not
  more than 0.05 above the rerun's.
* **Adopt** the arm (`x10` preferred over `y1` if both qualify and `x10` has the lower aftermath gap) if primary,
  must-not-worsen and drift all hold. If the primary partly holds (capture ≥ 0.30 but gap > 2.0×), report it as
  "the drop is learnable, the aftermath is not from climate inputs alone" — the next step would then be a state
  input, which needs the owner's view because it makes the map recursive.
* **Expectation (written before running):** `y1` capture 0.3–0.6 (the drought year is visible, but LightGBM at
  every-4th-year training rows sees few events), aftermath gap 2.5–3.5×; `x10` capture similar, gap 1.5–2.5×. The
  30-year-mean scores move little (±2 %), since events are a minority of cell-years; drift unchanged.

## 3. If adopted

The package (`landemu`) must compute the same inputs at run time: it already computes the 25 yearly statistics and
keeps a 30-year window of them, so this year's, last year's and the 10-year extremes are available without new state
from the forest. The stand map (leaf area, cover — the daily model's input) is a separate follow-up arm.

## 4. Results

(to be added after the fits)
