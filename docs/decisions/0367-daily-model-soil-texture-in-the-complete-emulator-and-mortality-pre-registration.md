# 0367 — Soil texture in the daily model of the complete emulator, and the per-tree mortality model re-scored with it (pre-registration)

* **Status:** pre-registered 2026-10-23, before any run of this record. **Results (§5): neither part adopted.** In the
  complete emulator texture cuts the NPP error by 12 % and 16 % (every one of 28 leg-windows in both seed pairs) at no
  cost, but fails the drift rule on the hottest leg (pair b) and sits exactly on the GPP limit (pair a). The mortality
  model fed the texture-emulated NPP is unchanged: die-off capture 0.433 vs 0.430, 30-year death rate 1.517 vs 1.517.
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

## 5. Results (2026-10-23)

**Builds and gates.** Releases `v2tex` + `fold_<g>_v3tex` (job 2672159): gate (1) numpy == PyTorch 1.28e-6, (T) soil
columns bit-exact for every setup (4 × 1 050 cells per release), (C) 25 copied files byte-identical, all six releases.
Emulator runs (job 2672161, 165 run-legs + 2 gates, 49 min on 64 cores): G2 `v2` reproduces its stored run bit for bit
after the package change; G2t `v2tex` reproduces `run_emulator.py`'s run bit for bit. Emulated NPP over the 1 050 cells:
history 483 gC/m²/yr (`v2`: 484), 2020–2100 459–470 (`v2`'s folds: 459–471) — texture moves cells, not the mean.
`BCET` training rows equal `BCE`'s exactly for all five held-out models (e.g. 11 074 323 for GFDL-ESM4).

### 5.1 Part A — complete emulator (jobs 2672155–8, `logs/f2-armTPD-score.2672158.out`, `logs/f2-armTPD-relscore.md`)

Median over 14 legs × 2 windows of CAND / REF typical-cell error (< 1 = texture better); worst leg-window; largest
rise of a leg's drift; one-core cost of the daily half:

| | GPP | NPP | ET | runoff | worst (flux, leg) | largest drift rise | cost (core-s / cell-yr) |
|---|---|---|---|---|---|---|---|
| pair a `PD_T_fx` / `PD_B_fx` | **1.050** (at limit) | **0.884** (28/28 < 1) | 0.958 | 0.970 | 1.232 (GPP, MPI ssp370 early) | +0.08 (ET, IPSL ssp585) | 6.42e-3 vs 6.39e-3 |
| pair b `PD_T2_fx` / `PD_D2_fx` | 0.994 | **0.844** (28/28 < 1) | 0.972 | 0.914 | 1.146 (GPP, IPSL ssp585 late) | **+0.10 ✗** (ET, IPSL ssp585: 1.07 → 1.17) | 6.42e-3 vs 6.40e-3 |
| rule (both pairs) | ≤ 1.05 | ≤ 0.95 | ≤ 1.05 | ≤ 1.05 | ≤ 1.25 | ≤ +0.08 | ≤ +5 % |

**Verdict: texture does not enter the release** (the release stays `v4`). Pair b fails the drift rule (ET on IPSL
ssp585 rises 0.10 above its reference); pair a meets every rule but sits exactly on the GPP limit (1.050 on 3-digit
ratios). Against the expectation: NPP 0.90–0.97 expected, **0.884 / 0.844 measured — the whole ADR 0348 gain survives
the emulated stand** (unlike the four-layer networks of ADR 0362); GPP 1.00–1.06 ✓; ET / runoff 0.97–1.02 ✓ / slightly
better. The weak spot is the same in both pairs and the same as in ADR 0348: the hottest leg (IPSL ssp585) late in the
century, where GPP (1.13 / 1.15) and ET (1.01 / 1.15) get worse and drift up — texture helps where the climate is
inside the training range and hurts slightly where it is furthest outside. Texture is a recorded, gated alternative
(`v2tex`, `fold_<g>_v3tex`; the package supports it).

### 5.2 Part B — mortality with the texture-emulated NPP (jobs 2672162–7; `xpanel/eval/treemort/score_treemort{,_clean}_0367.csv`)

The same score run reproduces ADR 0366's `BCE` numbers exactly (capture 0.430, 30-year rate 1.517), so the comparison
is like for like. Ratios to the pooled second runs, dense cells, 15 held-out cases (E2 = virtual trees, deployable):

| arm | yearly death rate (≤ 1.5) | 30-yr death rate (≤ 1.2) | total deaths ±5 % (≥ 12/15) | die-off capture (≥ 0.5) | capture hard-kill rate | hard-kill calibration E1 (±10 %) |
|---|---|---|---|---|---|---|
| `BCE` E2 (ADR 0366) | 0.966 | 1.517 | 15 | 0.430 | 0.611 | 0.865 (1 of 15) |
| **`BCET` E2** | **0.966 ✓** | **1.517 ✗** | **15 ✓** | **0.433 ✗** | 0.616 | 0.865 (2 of 15) |
| `BMW3` (cell map) | 1.009 | 1.343 | 14 | 0.278 | 0.267 | — |

Clean cells (the 240 the daily networks never saw, 943 events): capture `BCET` 0.538 vs `BCE` 0.543; 30-year rate
1.609 vs 1.677. Diagnostic: the emulated NPP z-score's correlation with the original's tree-NPP z-score per test leg is
0.620–0.661 (`BCE` 0.615–0.659), mean change **+0.002** (clean cells +0.005, range −0.002 … +0.009).

**Reading (§3, as written):** not adopted (30-year rate, capture). Capture gain +0.003 < 0.02 ⇒ **the texture gain does
not reach the yearly anomaly signal the die-offs need** — exactly the expected reason: texture improves each cell's
NPP LEVEL (the 30-year typical error), and the mortality inputs that carry the die-off signal are ratios and z-scores in
which a per-cell level cancels; the anomaly correlation did not move. Expectations: capture 0.43–0.47 ✓ (bottom),
correlation +0.00–0.03 ✓, 30-year rate unchanged ✓.

### 5.3 What this means for "NPP is the lever"

ADR 0366's "better emulated NPP is the lever" holds only for the yearly ANOMALY of NPP, not for its level. A daily-model
change should be judged for the mortality route by the anomaly correlation (0.63 now; the bound with the original's own
per-tree NPP gives capture 0.74), not by the 30-year error the daily-model yardstick measures. Not tested here: how much
capture a PERFECT stand-level NPP would give (the bound uses per-tree statistics); that number decides whether any daily
model can reach the 0.5 bar on this route.
