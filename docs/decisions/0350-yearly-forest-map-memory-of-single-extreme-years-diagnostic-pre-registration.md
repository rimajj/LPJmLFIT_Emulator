# 0350 — Does the yearly forest map miss the aftermath of single extreme years? (diagnostic, pre-registration)

* **Status:** pre-registered 2026-10-21, before the diagnostic runs. Results: §4.
* **Owner question (2026-10-21, paper draft):** the forest maps are non-recursive, so a die-off after one extreme
  drought cannot carry into later years except through 1/30 of the climate window. STATE.md to-do 4: diagnostic
  first; only if missed, try lagged-extreme climate inputs (e.g. the worst year of the last 5), not recursion.
* **Code:** `scripts/diagnose_extreme_year_legacy.py` (new; reads the yearly states and the deployed map's
  predictions, no fitting).

## 1. What could be missed, and what cannot

The original is stochastic: a one-year drop in tree count at a 25-patch cell can be a mortality pulse that the
climate forces (then the other runs of the original, driven by the same weather, drop in the same year), or chance
(then they do not). An emulator of the expected state can only be asked to follow the first kind. So events are
classified by whether the second runs share them.

## 2. Definitions

* Cases: 15 (five held-out climate models × ssp126/370/585); truth = unseen run m4; second runs m1, m2, m3;
  emulator = the deployed yearly map's predictions for m4 (`xpanel/eval/yearly/preds_<g>.parquet`), as
  `final_structure_score.py`.
* Cells: dense by the anchor (per-year anchor ≥ 5 trees per patch in the event year), as ADR 0329.
* **Event** per (case, cell): the year y in 2025–2090 (the yearly tables start in 2020, so the five years before y exist only from 2025) with the truth's largest one-year relative drop in tree count,
  `d_T = 1 − T(y)/T(y−1)`; kept if `d_T ≥ 0.15`. The same is done separately for stand biomass (tree count × biomass
  per tree).
* **Shared** (climate-forced) if at least 2 of the 3 second runs drop by ≥ 0.5·`d_T` in the same year; otherwise
  **chance**.
* Measures, per event class:
  1. **drop capture** `d_X / d_T` (emulator) beside `d_R / d_T` (each second run), medians;
  2. **aftermath** `L = mean(y+1 … y+10) / mean(y−5 … y−1) − 1` for truth, emulator and second runs; the median
     |L_X − L_T| against the median |L_R − L_T|;
  3. **event-window error** median over cells of |X − T|/T in years y … y+10, divided by the same for the second
     runs, against the same ratio over the cells' other years (ratio of ratios).

## 3. Pre-registered reading

* **The map misses climate-forced aftermaths** (⇒ pre-register an arm with lagged-extreme climate inputs) if, for
  SHARED events with tree count: drop capture ≤ 0.5 of the second runs' median, AND the aftermath gap
  |L_X − L_T| ≥ 1.5 × the second runs' gap, AND there are ≥ 100 shared events over the 15 cases (otherwise it is too
  rare to matter for the area totals).
* **Nothing to fix** if shared events are < 100, or the aftermath gap is < 1.5 × the second runs'. Close the item.
* **Expectation (written before running):** drop capture of the emulator ~0.1–0.3 (a single year is 1/30 of its
  climate input), second runs 0.5–0.8 on shared events; shared events a minority (≤ 30 %) of all events with
  `d_T ≥ 0.15` — most single-year drops at 25 patches are chance. The aftermath gap is the deciding number and I do
  not have a confident expectation for it.
* Harness: the scoring of a second run (m5, outside the pool) as if it were the emulator must give drop capture and
  aftermath gap within 0.8–1.25 of the pool's own values; otherwise the measure, not the emulator, sets the number.

## 4. Results

(to be added after the run)
