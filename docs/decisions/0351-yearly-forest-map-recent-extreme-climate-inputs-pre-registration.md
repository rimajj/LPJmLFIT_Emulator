# 0351 — Yearly forest map: recent-year and recent-extreme climate inputs, to follow drought die-offs (pre-registration)

* **Status:** pre-registered 2026-10-21, before the fits. **Result (§4, §5): no arm adopted.** Climate inputs
  alone do not let this map follow a drought die-off; the remaining remedy needs the forest's own state (owner's call).
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

## 4. Results (2026-10-21; fits 2638693–705, scores 2638698–709)

| | rerun (deployed map) | `y1` | `x10` | pre-registered |
|---|---|---|---|---|
| drop capture, shared tree-count events (second runs 0.939) | 0.031 | 0.148 | 0.140 | ≥ 0.30 ✗ |
| aftermath gap / second runs' | 4.44× | 4.37× | 3.83× | ≤ 2.0× ✗ |
| stand-biomass events: capture / gap | 0.070 / 3.22× | 0.141 / 3.21× | 0.130 / 2.94× | — |
| relaxed standard, median ratio to rerun (all quantities, both groups) | — | 0.983–1.012 | 0.960–1.018 (dense tree count 0.985) | ≤ 1.02 ✓ |
| criteria passing | 21/22 | 21/22 | 22/22 (dense tree count 11 → 12 cases) | none lost ✓ |
| drift, dense tree count / biomass per tree (median of 15) | 1.168 / 1.322 | 1.190 / 1.317 | 1.183 / 1.321 | ≤ +0.05 ✓ |

**Verdict: neither arm adopted** (primary fails). The single-year inputs make the drop year visible (capture ×5) but
the map still recovers almost none of it, and the 10-year memory inputs shave only 13 % off the aftermath gap.

## 5. Addendum, pre-registered 2026-10-21 BEFORE its fits: train on every year (arm `x10a`)

The map trains on every 4th year (`TRAIN_YEARS`, step 4), so ~3/4 of the die-off years and every other year of each
aftermath never appear as training rows. **Arm `x10a`** = `x10` with training rows every year (`--train-step 1`), one
change. Same measures and thresholds as §2. Expectation: capture 0.2–0.4, gap 2.5–3.5× — i.e. likely still short,
in which case the reading is that the map's form (a cell's level from the other runs' mean plus a learned shift)
cannot carry a die-off's aftermath from climate inputs, and the remaining remedy (the forest's own state as an input,
which makes the map recursive) goes to the owner rather than being started here.

### 5.1 Result of `x10a` (fits 2638928–32, scores 2638933–35)

Capture 0.141 (≥ 0.30 ✗), aftermath gap 3.90× (≤ 2.0× ✗) — no better than `x10` (0.140 / 3.83×) — and it makes the
map WORSE elsewhere: dense biomass per tree ×1.052 and sparse ×1.054 against the rerun (≤ 1.02 ✗), drift 1.198 /
1.372 (rerun 1.168 / 1.322; biomass per tree +0.05, at the limit). Not adopted.

### 5.2 Reading

Three climate-only arms (single years; + 10-year extremes; + every-year training) all lift the drop capture from
0.03 to ~0.14 and none takes the aftermath gap below 3.8× a second run's. The second runs reproduce 94 % of each drop
because they share the weather AND carry their own forest through it: whether a drought kills depends on the stand
it meets (a stand just thinned by the last drought has little left to lose), and how the cell recovers depends on
what died. A map that predicts each year from climate plus the other runs' mean cannot know either. **The remaining
remedy is to give the map the forest's own recent state (e.g. last year's predicted tree count), which makes it
recursive** — exactly the property the year-by-year map was chosen to avoid (ADR 0330: no drift because nothing is
fed back). That trade-off is the owner's to make; it is not started here. Until then the deployed map is unchanged,
and the miss is disclosed: on the 30-year means of ADR 0340 it does not show, year by year it is 3.5× a second run's
error in the 11 years after a die-off.
