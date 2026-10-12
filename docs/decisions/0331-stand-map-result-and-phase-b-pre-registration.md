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

## 4. Phase B result (2026-10-12; jobs 2467202–04, CPU; runs `PB_A`, `PB_B`, `PB_Bh`)

**Harness exact:** the copy-through run reproduces arm A's annual totals with difference **0.0** on every leg and
kind; the legs whose stand was not swapped are identical in all three runs. Stand arrays: every cell-year replaced
(1 050 × 81 × 12), none kept from the original; mean leaf area moves < 1 %.

Free runs, held-out cells (238), typical-cell error ÷ a second run's, 30-yr windows early / late:

| leg | flux | arm A (original's stand) | arm B (emulated stand) | B ÷ A | drift A → B |
|---|---|---|---|---|---|
| MPI ssp585 | GPP | 2.46 / 2.55 | 2.70 / 3.23 | 1.10 / 1.27 | 0.93 → 1.06 |
| | ET | 2.52 / 1.99 | 2.98 / 2.70 | 1.18 / **1.36** | 0.85 → 0.95 |
| | NPP | 3.14 / 2.86 | 3.45 / 3.39 | 1.10 / 1.19 | 0.93 → 1.06 |
| | runoff | 4.68 / 4.55 | 5.30 / 5.08 | 1.13 / 1.12 | 0.82 → 0.86 |
| UKESM ssp370 | GPP | 2.44 / 3.20 | 2.91 / 3.85 | 1.19 / 1.20 | 1.29 → 1.32 |
| | ET | 2.18 / 2.90 | 2.56 / 3.39 | 1.17 / 1.17 | 1.06 → 1.04 |
| | NPP | 3.21 / 4.23 | 3.95 / 5.52 | 1.23 / **1.30** | 1.35 → 1.37 |
| | runoff | 4.96 / 4.41 | 5.50 / 6.18 | 1.11 / **1.40** | 0.99 → 1.02 |

Area totals, arm B: 0.4–3.0 % (second run 0.2–0.4 %).

**Verdict as pre-registered: FAIL.** (1) increment ≤ 1.3×: fails for MPI ET late (1.36), UKESM NPP late (1.30) and
UKESM runoff late (1.40); (2) GPP and ET ≤ 3× a second run: fails (MPI GPP late 3.23; UKESM GPP 2.91 / 3.85 and ET late
3.39 — UKESM GPP late was already 3.20 with the original's stand); (3) totals within 5 %: **holds**; (4) drift ≤ arm A
+ 0.1: fails on MPI for GPP and NPP (+0.13 each, values still ≤ 1.06), holds on UKESM. Falsifier (GPP × > 1.5) did not
fire. Against the expectations: GPP / NPP rose 1.10–1.30 (expected 1.05–1.25, roughly held); **ET rose 1.17–1.36,
more than the 1.0–1.15 expected** — evaporation and transpiration lean on the stand more than assumed.

**Reading.** With the stand emulated as well, the full learned emulator's daily fluxes are 2.6–3.9× (GPP, ET),
3.4–5.5× (NPP) and 5–6× (runoff) a second run's typical error, area totals within 3 %. The emulated stand adds 10–40 %
to the daily model's error; the daily model's own error (2–3×) still dominates, so the larger lever stays the daily
model — but the stand is no longer negligible, and ET is where it bites most. Next: the IPSL legs under the same rule
once ADR 0328's daily arrays exist; and, if the owner wants the stand's share cut, a stand map aimed at the daily
model's inputs (e.g. leaf area per plant type rather than totals) — not pre-registered here.

## 5. Phase B on the IPSL legs (2026-10-13; jobs 2474185–87, CPU; runs `PB_B_ipsl`, `PB_Bh_ipsl`)

Same rule as §4: the control ensemble (H members) fed the emulated stand (stand map fitted with each run and IPSL
unseen) vs the original's stand (arm A = `HEdr_x`). **Harness exact:** the copy-through run reproduces `HEdr_x`'s IPSL
rows digit for digit on every flux and statistic.

Typical-cell error ÷ a second run's, 30-yr windows early / late, arm A → arm B (B ÷ A):

| leg | GPP | ET | NPP | runoff |
|---|---|---|---|---|
| IPSL ssp126 | 2.29/2.69 → 2.87/2.93 (1.25/1.09) | 3.07/2.73 → 4.18/3.42 (**1.36**/1.25) | 3.30/3.43 → 3.36/3.51 (1.02/1.02) | 6.67/4.36 → 7.11/5.16 (1.07/1.18) |
| IPSL ssp370 | 2.18/2.52 → 2.64/3.00 (1.21/1.19) | 3.04/2.37 → 3.97/2.75 (**1.31**/1.16) | 3.21/3.63 → 3.60/3.72 (1.12/1.02) | 5.73/4.70 → 5.52/5.15 (0.96/1.10) |
| IPSL ssp585 | 2.25/2.73 → 2.64/3.58 (1.17/**1.31**) | 3.02/2.98 → 3.80/3.54 (1.26/1.19) | 3.17/3.77 → 3.55/4.45 (1.12/1.18) | 5.11/6.53 → 5.70/7.64 (1.12/1.17) |

Drift A → B: GPP 1.06/1.00/1.26 → 1.08/1.07/**1.38**; NPP 1.04/1.08/1.29 → 1.07/1.08/1.32; ET 0.89/0.88/1.08 →
0.98/0.89/1.17. Area totals, arm B: 0.2–2.8 % (second run 0.2–0.5 %).

**Verdict as pre-registered: FAIL, same shape as §4.** (1) increment ≤ 1.3×: fails for ET early on ssp126 (1.36) and
ssp370 (1.31) and GPP late on ssp585 (1.31); (2) GPP and ET ≤ 3×: fails for ET on all three (3.42–4.18) and GPP late
on ssp585 (3.58); (3) totals within 5 %: holds; (4) drift ≤ arm A + 0.1: fails for GPP on ssp585 (+0.12), holds
elsewhere. Across all five unseen-model legs the emulated stand adds 2–36 % to the daily error, most in ET.
