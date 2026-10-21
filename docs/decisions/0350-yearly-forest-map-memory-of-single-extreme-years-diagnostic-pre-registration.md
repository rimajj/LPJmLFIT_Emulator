# 0350 — Does the yearly forest map miss the aftermath of single extreme years? (diagnostic, pre-registration)

* **Status:** pre-registered 2026-10-21, before the diagnostic runs. **Result (§4): the map MISSES climate-forced
  die-offs and their aftermath** — opposite to the expectation; follow-up arm pre-registered in ADR 0351.
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

## 4. Results (2026-10-21; job 2638639, `xpanel/eval/extreme_legacy_events.parquet`)

| events (dense cells, 15 cases) | tree count, shared | tree count, chance | stand biomass, shared | stand biomass, chance |
|---|---|---|---|---|
| number | **3 291** | 192 | 3 670 | 2 608 |
| truth's drop d_T (median) | 0.31 | 0.20 | 0.32 | 0.20 |
| truth's 10-yr aftermath L_T (median) | −0.25 | −0.17 | −0.30 | −0.20 |
| drop capture: map / second runs / harness m5 | **0.031** / 0.939 / 0.947 | 0.008 / 0.40 / 0.45 | 0.070 / 0.883 / 0.868 | 0.033 / 0.18 / 0.20 |
| aftermath gap: map / second runs / harness | 0.246 / 0.055 / 0.055 (**4.4×**) | 0.18 / 0.11 / 0.10 (1.7×) | 0.254 / 0.079 / 0.083 (3.2×) | 0.16 / 0.14 / 0.13 (1.2×) |
| map error vs second runs: event window / the cells' other years | 3.48 / 1.99 | 1.84 / 1.13 | 2.27 / 1.51 | 1.09 / 0.93 |

* **Harness ✓:** the spare run m5 scored as the emulator matches the second-run pool (capture 0.947 vs 0.939, gap
  0.055 vs 0.055) — the measure is sound.
* **Verdict (pre-registered §3): MISSES.** 3 291 shared tree-count events (≥ 100), capture 0.031 ≤ 0.5 × 0.939,
  aftermath gap 4.4× ≥ 1.5×.
* **My expectation was wrong on the decisive part:** large one-year tree-count drops are NOT mostly chance — 94 % are
  shared by the other runs of the original (they reproduce 94 % of the drop), i.e. forced by the weather.
* **Not a scheduling artefact:** the shared events spread over 66 calendar years; no case's busiest year holds more
  than 9 % of its events.
* **They are droughts.** Median anomaly of the event year against the cell's own 2020–2100 years (in standard
  deviations): annual rain −1.25, climatic water balance −1.20, relative humidity −1.18, net longwave −1.00, shortwave
  +0.93, air dryness in the growing season +0.73 / last 10 days +0.83, potential evaporation +0.58, mean temperature
  +0.27; the year before is dry too (rain −0.51, water balance −0.46); two years before is near normal. 35–38 % of
  events have a rain / water-balance / humidity anomaly beyond 1.5 SD.
* **Why the map misses them:** its climate input is a trailing 30-year mean, so a drought year moves it by 1/30; the
  per-year anchor (the other climate models' runs at the cell) has its own droughts in other years and averages
  them away.
* **Consequence for the release numbers:** the 30-year-mean scores of ADR 0340 hide this (a die-off and its
  recovery average out over 30 years), but year by year the map's error in the 11 years from a die-off is 3.5× a
  second run's against 2.0× in the same cells' other years — and an Earth-system model sees the year-by-year state.
