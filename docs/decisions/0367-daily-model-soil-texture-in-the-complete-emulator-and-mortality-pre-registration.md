# 0367 — Soil texture in the daily model of the complete emulator, and the per-tree mortality model re-scored with it (pre-registration)

* **Status:** pre-registered 2026-10-23, before any run of this record. Results: §5 (empty until measured).
* **Owner instruction (2026-10-23):** *"Improve the daily model's NPP, which is the lever for mortality. Soil texture as
  an input already cut the NPP error by 13–16 % in an earlier test, but it is not in the release. Then re-score this
  model with it."* (= option n1 of the 2026-10-22 handoff.)
* **Follows:** ADR 0348 §4.1 (texture as four daily inputs: NPP typical error 0.868 / 0.841 of the release networks'
  in two seed pairs, GPP 1.056 / 1.009, ET 0.988 — not adopted on its pre-registered water criterion; the NPP gain was
  unexpected and left to the owner), ADR 0366 (per-tree mortality with the emulator's own NPP, arm `BCE`: die-off
  capture 0.43, bar 0.5; "better emulated NPP is the lever"), ADR 0362 (a network gain measured with the original's
  stand mostly vanished in the complete emulator: NPP −6…−13 % → −6 %).
* **Code:** `landemu.daily` (optional soil-texture columns), `scripts/build_release_daily_swap.py` (new),
  `scripts/run_emulator_npp.py --variant tex`, `scripts/explore_panel_treemort.py --arm BCET`.

## 1. What changes

The five texture networks of ADR 0348 (`T_3x256_seed0..4`: the release recipe of arm D + sand, clay, ln Ks, ln Sf of
the cell's soil type; every member ran 10 of 10 epochs) replace the release networks `D_3x256_seed0..4`. Nothing else
changes and nothing is retrained.

* **Package.** `daily.npz` may carry `soil_table` (13 soil codes × the four columns, float32, computed exactly as
  `f2_train.soil_columns`); a release that has it appends the four columns after every other input (after CO2, as the
  trainer). A release without it runs exactly as before (guardrail: every existing release unchanged).
* **Releases** (copies; never in place): `v2tex` = `v2`, `fold_<g>_v3tex` = `fold_<g>_v3` for the five climate models,
  each with only `daily.npz` replaced and `release.json` annotated. Not deployment releases.
* **Gates.** (1) numpy == PyTorch on 20 000 real teacher-forced input rows WITH texture (< 1e-5, as ADR 0340);
  (T) the package's soil columns for the 1 050 panel cells equal `f2_train.soil_columns` bit for bit; (C) every file
  but `daily.npz` / `release.json` is byte-identical to the base release; (G2t) `run_emulator_npp.py` on
  (`v2tex`, m1, `ukesm1-0-ll_ssp370`, cap fixed) equals `run_emulator.py`'s run of the same, bit for bit; plus the
  ADR 0366 gate G2 (`v2` reproduces its own run) re-run to show the package change leaves texture-free releases alone.

## 2. Part A — does the NPP gain survive in the complete emulator?

Venue = `PD_B_fx` (ADR 0353/0362): the daily ensemble fed the leak-free EMULATED stand (`stand_emul_fx`), 14 legs, 240
held-out cells, `f2_relative_score.py`, compared with `f2_relscore_compare.py` (median over legs × windows of the
CAND / REF typical-cell error). Two seed pairs, because one ensemble's run-to-run noise is ±9 % on NPP per leg
(ADR 0336 §6):

* pair a: `PD_T_fx` (members `T_3x256_seed0..4`) vs `PD_B_fx` (existing, `D_3x256_seed0..4`);
* pair b: `PD_T2_fx` (`T2_3x256_seed5..9`) vs `PD_D2_fx` (new, `D2_3x256_seed5..9`).

**Texture enters the release** (a later record builds `v5` = `v4` + texture) only if BOTH pairs have: median NPP
≤ 0.95; GPP, ET and runoff ≤ 1.05; no flux's worst leg > 1.25; no leg's drift more than 0.08 above REF's; daily cost
within +5 %. Otherwise the release stays `v4` and texture is reported as an alternative.

**Expected:** NPP 0.90–0.97 (part of the 13–16 % survives, as ADR 0362's −6 % did); GPP 1.00–1.06 (pair a's GPP
worsening of ADR 0348 may recur and then fails the rule); ET / runoff 0.97–1.02.

## 3. Part B — the per-tree mortality model with the texture-emulated NPP (arm `BCET`)

`BCET` = `BCE` (ADR 0366 §1–2) with every emulated-NPP input taken from the texture releases instead: training legs
from `v2tex` × runs m1 m2 m3 m5 m6 × all 30 scenario legs, test legs from `fold_<g>_v3tex` × run m4. Same setups
(m5/m6 from ADR 0366), same 2000–2019 emulated history construction, same 12 inputs, same tree rows, same LightGBM
settings, same four sub-models, same E1/E2 predictions and scorer → `xpanel/eval/treemort/enpp_tex/enpp.parquet`,
`<g>_BCET/`, `pred_<g>_BCET.parquet`. Part B runs whatever Part A shows (the owner asked for the re-score).

* **Bars:** ADR 0364 §5 unchanged (yearly death rate ≤ 1.5, 30-year ≤ 1.2, total deaths ±5 % in ≥ 12 of 15 cases,
  die-off capture ≥ 0.5, hard-kill calibration ±10 %). All cells and the 240 cells the daily networks never saw.
* **Adoption:** `BCET` E2 passes every bar ⇒ the emulator gets a mortality output (new record). Fails a bar but beats
  the cell map `BMW3` on capture by ≥ 0.1 with no other score worse by > 10 % ⇒ reported, owner decides.
* **Reading:** capture gain over `BCE` E2 (0.43 all cells; 0.54 clean): ≥ 0.05 ⇒ a better daily model moves the
  mortality route and more NPP work is worth it; < 0.02 ⇒ the texture gain (a gain in the 30-year NPP LEVEL) does not
  reach the yearly anomaly signal the die-offs need; between ⇒ small, reported as such. Diagnostic: the correlation of
  the emulated NPP z-score with the original's tree-NPP z-score (`BCE`: 0.60–0.66 per test leg) — the direct measure
  of whether the anomaly got better.
* **Expected:** capture 0.43–0.47, correlation +0.00–0.03, 30-year rate unchanged (~1.5) — because the mortality inputs
  are dominated by ratios and z-scores, in which a per-cell constant NPP offset cancels, while ADR 0348's gain is a
  30-year typical (level) error.

## 4. Cost

Part A: three GPU jobs of ~1 h. Part B: 165 emulator run-legs × ~775 core-s ≈ 36 core-hours on `priority`, five fits
and predictions as in ADR 0366.

## 5. Results

(to be filled in)
