# 0331 — The stand map (structure → the daily model's stand inputs): result, and phase B pre-registered

* **Status:** stand map = accepted (measurement), 2026-10-12. Phase B = **pre-registered 2026-10-12, before its
  runs**; result appended below.
* **Depends on:** ADR 0330 (the year-by-year structure arm), ADR 0325 (the daily model's second-run yardstick and
  proposed numbers), ADR 0326/0327 (the daily ensemble used: no humidity input, deep store drains at D/365),
  ADR 0328 (running in parallel; it does not change this test).
* **Scripts:** `scripts/explore_panel_stand_map.py` (`fit --g [--hold k]`, `score`, `arrays`), `scripts/f2_train.py`
  (new opt-in `--stand-dir`: read `stand_<run>_<leg>.npy` from a subdirectory where present; default unchanged).
  Data: `xpanel/eval/stand/` (predictions, `stand_cases.csv`, `stand_years.csv`, `stand_score.txt`).

## 1. Why

The learned daily model has so far been handed the ORIGINAL's stand (leaf area, vegetation carbon, cover by plant
type) every year — which flatters its score (STATE). In the full emulator the stand must come from the structure
emulator.

## 2. The stand map (jobs 2467173–77, ~5 min each)

Extra yearly targets of the year-by-year structure arm (ADR 0330): same rows and features plus each stand quantity's own
per-year anchor, start level and start offset; one boosted-tree model per quantity (leaf area, vegetation carbon, cover
of each of the 10 plant types). Leaf area and vegetation carbon train on runs m1, m2, m3, m5, m6 × the 27 legs of the 9
other climate models; cover by type only exists for runs m1–m4 on the first five climate models, so those models train
on m1–m3 × 12 legs. Scored on the unseen run m4, every year, five held-out climate models (15 cases).

Dense cells (structure anchor ≥ 5 trees per patch), median over the 15 cases; ratio = typical-cell (or worst-10 %)
error / a second run's; level = 2071–2100; drift = 2081–2100 / 2051–2070:

| stand input | level, typical | level, worst 10 % | drift (cases ≤ 1.2) | area total 2071–2100, median / worst |
|---|---|---|---|---|
| leaf area | **1.37** | 1.95 | 1.08 (13/15) | −0.2 % / 2.6 % |
| vegetation carbon | **1.24** | 1.40 | 1.07 (13/15) | +1.1 % / 4.0 % |
| tree cover (types 1–7) | 1.55 | 2.32 | 1.07 (11/15) | +0.7 % / 4.3 % |
| grass cover (types 8–10) | 1.27 | 2.28 | 1.05 (12/15) | +0.5 % / 5.7 % |

All cells: leaf area 1.58, vegetation carbon 1.67, tree cover 1.74, grass cover 1.98 (sparse cells are worse, as for
the structure). Harness: another run scored as the emulator 1.00–1.01, drift 1.00; the mean of three runs 0.83 (derived
0.82). The anchor alone: 1.57–2.16, drift 1.25–1.29 — the learned shift removes most of that.
Against the expectations: levels within 1.0–1.6 (leaf area, carbon) and 1.0–1.8 (cover) **held**; median drift within
0.9–1.2 **held** (11–13 of 15 cases individually); area totals within 3 % held for leaf area, **missed** in the worst
case for carbon (4.0 %) and cover (4.3 / 5.7 %).

## 3. Phase B — PRE-REGISTERED (before its runs)

**One variable:** the stand the daily model reads in 2020–2100 — the original's (arm A) vs the stand map's (arm B).
Everything else fixed: the five no-humidity members `H_3x256_seed0..4`, deep store draining at D/365, 3 × 256, NPP =
GPP − respiration; free runs from the original's end-of-2019 state. **Stand for run k** = the stand map fitted with run
k unseen (`--hold k`, k = 1..4) AND the leg's climate model unseen (so no information about that climate model or that
run enters the stand). The end-of-2019 stand stays the original's (the known start).
**Test legs:** MPI ssp585 and UKESM ssp370 (the daily model's held-out legs that exist now; scorer
`scripts/f2_relative_score.py`, its held-out cells only, all four runs). IPSL ssp126/370/585 to follow once ADR 0328's
daily runs exist, under the same rule.
**Harness:** arm B run with the ORIGINAL's stand copied through the same `--stand-dir` path (`arrays --copy-only`)
must reproduce arm A's annual totals (relative difference < 1e-5).

**Pass (each test leg, GPP / ET / NPP / runoff):**
1. **Increment:** arm B's typical-cell error ratio (30-yr windows 2021–2050 and 2071–2100) ≤ **1.3 ×** arm A's — the
   emulated stand adds at most 30 % to the daily model's error.
2. **Level:** GPP and ET typical ≤ 3 × a second run (ADR 0325's proposed bar), both windows.
3. **Totals:** area totals within 5 % (ADR 0325).
4. **Drift:** arm B's drift (single-year ratio 2081–2100 / 2021–2040) ≤ arm A's + 0.1.

**Expectations:** GPP and NPP move most (leaf area is the daily model's main stand input, 1.37 × a second run on dense
cells; on all cells 1.58 ×): their typical ratio rises by a factor 1.05–1.25; ET by 1.0–1.15; runoff follows ET. The
UKESM drift (already 1.29 / 1.35 for GPP / NPP with the original's stand, ADR 0327) changes by < 0.1.
**Falsifier:** GPP's typical ratio rises by > 1.5 × on either leg ⇒ the stand error, not the daily model, would then
dominate the full emulator's carbon error, and the next work is on the stand map (e.g. leaf area as its own learned
quantity with a relative target), not on the daily model.
