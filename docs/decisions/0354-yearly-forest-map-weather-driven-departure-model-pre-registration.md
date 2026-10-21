# 0354 — Yearly forest map: a weather-driven departure model on top of the level map, for drought die-offs (pre-registration)

* **Status:** pre-registered 2026-10-21, before any fit of this record. **Result (§7): not adopted** — drop capture 0.03 → 0.18 (bar 0.30), aftermath gap 4.5× → 3.75× (bar 2.0×); the null without weather stays at 0.03; general scores 18 → 20 of 22 criteria with nothing lost and drift unchanged.
* **Owner instruction (2026-10-21):** "continue with the emulator"; the NEXT handoff listed this as option (b), the
  forest map's biggest known miss (ADR 0352 §6.3).
* **Follows:** ADR 0350 (94 % of the original's big one-year tree-count drops are drought years its other runs share;
  the map captures 3 % of the drop, 10-year aftermath gap 4.4× a second run's), ADR 0351 (single-year and 10-year-
  extreme climate as extra inputs to the LEVEL map: capture ~0.14, gap 3.8–4.4×), ADR 0352 (the forest's own last-year
  state as an input: the state carries a start error for 10–20 years but the drop itself is still missed, gap 3.8–4.0×).
  The reading there: the bottleneck is the drop year itself, and a fix should target the one-year change directly.
* **Code:** `scripts/explore_panel_yearly_drift.py fit --state dep|depnw` (new), scored by
  `scripts/score_yearly_map_variant.sh` as every earlier arm.

## 1. Why a separate model, and why the earlier arms could not do this

The level map is trained on single-year values with squared error on (value − anchor). Its loss is dominated by the
differences BETWEEN cells (tree count per patch spans 0–60); a drought year moves one cell by ~30 % for a few years, a
small share of that loss, so 25 single-year climate columns among 138 inputs barely enter the fit (ADR 0351: 0.14 of
the drop). Fed its own state (ADR 0352), it remembers but still does not produce the drop. Here the drop is the ONLY
thing a second model is asked to learn: the map keeps its job (the level), and a small model learns the forest's
year-to-year departure from that level from the year's weather anomaly.

## 2. The arm `dep`

* **Level** `M_q(y)` = the leak-free map `fix` (ADR 0352), unchanged (same rows, same features, same fit). Harness:
  its predictions must equal the stored `preds_<g>_fx.parquet` (max relative difference ≤ 1e-6; ADR 0349 found
  LightGBM reruns equal at float level).
* **Departure, the quantity learned**, for tree count per patch and biomass per tree (`q` ∈ {n, a}):
  `d_q = ln((T_q + 1) / (M_q + 1))` for each training run on each training leg, with `M_q` the level map's
  **cross-fitted** prediction (3 folds by training climate model, as ADR 0352's `lagd`: fitted on the other two
  folds' training years, predicted on this fold's legs in every year), so the departure is measured against a map that
  never saw that run's leg. **Forced departure** `D_q(leg, cell, y)` = mean of `d_q` over the five training runs
  (they share the leg's weather, so their mean keeps the weather-forced part and averages out chance), then minus its
  own 2020–2100 mean per (leg, cell). The de-meaning keeps the departure from correcting the level map's own lasting
  errors — this arm changes only the year-to-year course, not the long-run level.
* **Departure model** `F_q`: LightGBM (as the map: `explore_panel_a7.PARAMS`, 400 rounds), one per quantity, target
  `D_q(y)`, inputs:
  - last year's departures `D_n(y−1)`, `D_a(y−1)` (0 in 2020: the map has no 2019 value);
  - the weather anomaly of this year and last year: for each of the map's 25 yearly climate statistics,
    `z = (x(y) − mean) / sd` over the 30 years before y (observed 2000–2019 in front of the leg, as the map's window;
    ≥ 15 years; `z = 0` where the statistic does not vary) — 50 columns;
  - what the drought hits: the level map's `M_n(y)`, `M_a(y)` and the 25 trailing 30-year climate means.
  Training rows: training legs × cells × every year 2020–2100 (one row per leg and cell, ≈ 2.3 M), teacher-forced
  (true `D(y−1)`).
* **Run time:** year by year from 2020 per (run, leg, cell), last year's departure = the model's own; the output is
  `X_q = (M_q + 1)·exp(D̂_q) − 1` (tree count ≥ 0). The four trait medians stay the map's.
* **Null `depnw`:** the same without the 50 weather columns. It must capture none of the drop (≤ 0.05) — if it does,
  the gain is not the weather. It also shows what the context and the memory alone do to the general scores.

## 3. Measures (all as ADR 0352 §2, against `fix`)

* **Die-off** (ADR 0350, shared tree-count events): drop capture and aftermath gap (|L_X − L_T| / second runs').
* **Must not get worse** (`compare_structure_variants.py _fx <arm>`): median ratio arm / `fix` ≤ 1.02 on every
  quantity and group; no criterion that `fix` passes lost (18 of 22).
* **Drift** (`score` stage, dense, tree count and biomass per tree): median drift ≤ `fix` + 0.05 (1.269 / 1.457), and
  median late level `rho50_late` ≤ 1.05 × `fix`'s.
* **Start-error test** (`retention` stage): the run is repeated with last year's tree-count departure in 2020 set to
  ln 0.7 (a 30 % die-off at the start). Retained share must never grow (max ≤ 1.1) and must fade (mean 2081–2100 ≤ 0.5).
* Reported: the event-window error ratio of ADR 0350 §2 item 3, and the stand-biomass events.

## 4. Pre-registered verdict

* **Adopt `dep`** if: drop capture ≥ 0.30 AND aftermath gap ≤ 2.0× a second run's AND must-not-worsen AND both drift
  conditions AND the start-error test AND the null `depnw` captures ≤ 0.05.
* Capture ≥ 0.30 but gap > 2.0× ⇒ "follows the drop, not the recovery": not adopted; report how much of the gap
  remains and whether it is the recovery speed (the aftermath curve of the event years).
* Capture < 0.30 ⇒ the year's 25 annual statistics do not carry what the original's mortality responds to; the next
  candidate is a daily-resolved stress input (the original accumulates its water stress from a fixed calendar day,
  CLAUDE.md §3) — owner's call.
* The level harness (§2) must pass first; if it fails, no result of this record is read.

## 5. Expectations (written before running)

* Level harness: equal to ≤ 1e-6 (same rows, same order, same thread count).
* `dep`: capture 0.3–0.6 (the second runs reproduce 0.94, so the forcing is there; whether 25 annual statistics carry
  it is the open question); aftermath gap 2–3× (the original keeps ~0.8 of a die-off over a decade; the model must
  learn that persistence from `D(y−1)`); must-not-worsen within ±2 % (most years have small departures); drift equal
  to `fix` ± 0.03 (the de-meaned departure is bounded); start cut retained ~0.9 in 2021, ~0.5 by 2030, ≤ 0.2 late.
* `depnw`: capture ≤ 0.03, gap 4–4.5×, general scores within ±1 % of `fix`.
* My best guess: `dep` lifts the capture well past every earlier arm and narrows the gap, but does not reach 2.0×.
  I do not have a confident expectation for the gap.

## 5a. Amendment to the level harness (2026-10-21, after the first fit, BEFORE any score was read)

The first fit (gfdl-esm4, job 2651330) gave a level max relative difference of 2.4e-2 against `preds_gfdl-esm4_fx`,
so §2's "≤ 1e-6" fails as written. Where it comes from: 99.85 % (wood density) to 100 % (the other quantities) of the
510 300 rows agree to ≤ 1e-6 and the median difference is 0; wood density differs in 0.15 % of rows (max 1.7e-3),
rooting depth in 0.02 % (max 2.4e-2) — a split decided differently in a few trees, LightGBM's multithreaded
float-level rerun difference (ADR 0349 found the same between two reruns of one map). My threshold on the single
worst row was too strict for that. Read instead: median difference 0 and ≥ 99.5 % of rows within 1e-6 on every
quantity. The same fit's one-step diagnostic (tree count, held-out legs, true last-year departure): correlation of
the one-year change 0.53, median 0.25 of the 7 824 drops ≥ 0.15 captured — reported, not scored.

## 6. If adopted

The package (`landemu`) would carry two numbers per cell from year to year (the departures) and a 30-year mean and
standard deviation of its yearly climate statistics (it already keeps the 30-year window); the release gates gain a
year-by-year replay. The stand map (leaf area, cover) would get the same treatment in a separate step.

## 7. Results (2026-10-21; fits 2651330, 2651337–45, score 2651346, `logs/yst-dep*.out`)

Level harness (§5a reading): median difference 0 and 99.85–100 % of rows within 1e-6 on every quantity, all five
held-out models (tree count and biomass per tree rebuilt from the output and the saved departure) — passes; every
difference below is the departure model's.

| median over 15 cases, dense cells | `fix` | `dep` | `depnw` (null) | pre-registered |
|---|---|---|---|---|
| die-off drop capture, shared tree-count events (second runs 0.939) | 0.027 | **0.183** | 0.027 | ≥ 0.30 ✗; null ≤ 0.05 ✓ |
| aftermath gap / second runs' | 4.53× | **3.75×** | 4.53× | ≤ 2.0× ✗ |
| stand-biomass events: capture / gap | 0.070 / 3.2× | 0.162 / 2.98× | 0.064 / 3.34× | reported |
| event-window error / the cells' other years (vs second runs) | 3.48 / 1.99 | 3.00 / 1.98 | 3.63 / 2.10 | reported |
| one-step capture on held-out legs (true last-year departure, §5a) | — | 0.22–0.25 | 0.045–0.051 | reported |
| dense tree count / biomass per tree, ratio to `fix` | — | 1.009 / 1.002 | 1.001 / 1.008 | ≤ 1.02 ✓ |
| sparse tree count / biomass per tree, ratio to `fix` | — | 0.986 / 0.998 | 0.974 / 1.012 | ≤ 1.02 ✓ |
| criteria passing (of 22) | 18 | **20** (+ dense tree count worst 10 %, + sparse tree count typical), none lost | 18 | none lost ✓ |
| drift tree count / biomass per tree | 1.219 / 1.407 | 1.201 / 1.412 | 1.234 / 1.405 | ≤ 1.269 / 1.457 ✓ |
| late level tree count / biomass per tree | 1.204 / 1.108 | 1.165 / 1.119 | 1.206 / 1.113 | ≤ 1.05× ✓ |
| start cut retained 2021 / 2025 / 2030 / 2050 / late | — | 0.94 / 0.45 / −0.04 / −0.47 / −0.14 | — | max ≤ 1.1, late ≤ 0.5 ✓ |

**Verdict (§4): not adopted.** Every condition passes except the two the arm was built for: capture 0.18 < 0.30 and
aftermath gap 3.75× > 2.0×. By §4 this is the "capture < 0.30" branch.

Reading:
* **The weather does carry part of the drop, and it is the weather:** capture rises 0.03 → 0.18 (the best of every
  arm since ADR 0350; ADR 0351/0352 reached 0.13–0.19 only with errors worse elsewhere), the null without weather stays
  at 0.03, and the year-to-year change correlation on held-out legs is 0.50–0.53 with weather against 0.22–0.24
  without. But 25 annual statistics explain about a quarter of a drought die-off; the original's other runs reproduce
  94 % of it, so most of what decides the drop is not in those annual numbers.
* **Free-running loses some:** 0.22–0.25 of the drop with the true last-year departure, 0.18 when the model carries its
  own.
* **The recovery overshoots:** after a 30 % start cut the model's tree count is back by 2030 and then 40–47 % of the
  cut ABOVE the uncut run in 2040–2060, fading to 14 % late. The original's own response to a start cut was not
  measured, so whether a post-die-off surge is real is open; the start-error test passes as written.
* **A general gain without the die-off:** 20 of 22 criteria (from 18), nothing lost, drift unchanged, late tree-count
  level ×0.97. Larger than `fx10`'s (19 of 22) and from the same kind of input (the recent weather), but by a model
  that only moves the year-to-year course. Not adopted under this record; shipping it for the general gain is a
  separate decision (it adds two numbers per cell carried from year to year and the 30-year mean and spread of the
  climate statistics).
* §4's next candidate: a daily-resolved stress input (e.g. the year's water-stress integral on the original's own
  calendar, CLAUDE.md §3) — owner's call.
