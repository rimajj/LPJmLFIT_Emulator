# 0353 — Leak-free restatement of the held-out-climate-model numbers: structure map, stand map, the whole emulator's daily fluxes, the fold release (pre-registration)

* **Status:** pre-registered 2026-10-21, before the stand-map refits and the daily run; **results §5 (2026-10-21): the
  restated numbers below replace ADR 0330 / 0337 / 0340's held-out-model numbers; release `v1` unchanged.**
* **Follows:** ADR 0352 §0 (the yearly structure map and the stand map trained on run m5 on the HELD-OUT climate
  model's legs; fixed in code; §6.1 measured the leak on the structure map: errors +7–12 %, relaxed standard 21 → 18
  of 22; §3's restatement trigger fired). Owner chose this step first (STATE NEXT option (a), 2026-10-21).
* **Restates:** ADR 0330 (structure drift), ADR 0331 / 0337 (stand map, the daily model fed the emulated stand =
  run `PD_B`), ADR 0340 §4.1–4.3 (the release verdict's panel structure, daily and drift numbers), and the paper
  draft (`docs/paper/`) wherever it quotes them. Not affected: release `v1` (deployment, no test legs), the global
  venue of ADR 0340 §4.1 (window map A7rH on Billing's runs, a different row builder), every daily-model-only score
  (`DE_5seed`, `PD_A`: they read the original's stand), the speed numbers, the nitrogen-on work (ADR 0342–0344:
  `clu_emu_maps.py stage_train`, a different builder — checked 2026-10-21: it trains on one run (seed 2) and only on
  the training climate models' legs, held-out cells removed; the scored runs are seed 2 on held-out models and seed 3).

## 1. What is re-run (one change: the leak-free training rows; nothing else)

| step | old | new (suffix `_fx`) |
|---|---|---|
| structure map, 5 held-out models | `preds_<g>.parquet` | `preds_<g>_fx.parquet` — **already done** (ADR 0352 arm `fix`, jobs 2641029–45) |
| stand map, 5 models × unseen run k = 1..4 (20 fits) | `stand/preds_<g>[_h<k>].parquet` | `stand/preds_<g>[_h<k>]_fx.parquet` |
| stand-map score (ADR 0331 measure) | `stand_cases.csv` | `stand_cases_fx.csv` |
| the daily model fed the emulated stand, 13 legs | `stand_emul/`, run `PD_B` | `stand_emul_fx/`, run `PD_B_fx` (same five networks `D_3x256_seed0..4`, same arguments) |
| fold release (GFDL-ESM4 held out) | `release/fold_gfdl-esm4_v1` | `release/fold_gfdl-esm4_v2` (+ `--check` vs `_fx` and `PD_B_fx`) |

`PD_A` (the same networks reading the original's stand) is unaffected and stays the reference for the stand's
increment B ÷ A.

## 2. Checks (harness)

* Every stand fit log: training rows = runs × training legs × training years × 1 050 cells (no held-out leg).
* The fold release `--check`: structure and stand reproduce the `_fx` predictions as v1 reproduced the old ones
  (ADR 0340 §3 tolerances), daily fluxes reproduce `PD_B_fx` to a median < 1e-2 (observed for v1: ~1e-6).

## 3. Expectations (written before running)

* Stand map (dense, typical cell, level 2071–2100 ÷ a second run): up by 5–12 % on leaf area and vegetation carbon,
  as the structure map; tree / grass cover up 3–12 %.
* Whole emulator's daily fluxes (`PD_B_fx` vs `PD_B`): the stand added a median 13–35 % over the daily model's own
  error (ADR 0337 §4), so a ~10 % larger stand error adds ~1–4 % to typical GPP / ET / NPP / runoff ratios; no
  criterion of ADR 0340 §4.2 changes pass/fail, except possibly ET typical (3.14, 5 of 13 legs) losing a leg or two.
* Structure drift (ADR 0352 §6.1, already measured): 0330 rule 1.22 / 1.41; mid → late stays ≤ 1.2 on ≥ 13 of 15.

## 4. What follows

The leak-free numbers replace the old ones in ADR 0340's verdict (as an amendment here, ADR 0340 stays immutable),
in `docs/emulator_release.md`, the paper draft and STATE. No adoption decision rides on this record.

## 5. Results (2026-10-21; stand fits 2642090–94, arrays 2643601, daily run `PD_B_fx` 2643602, fold release 2642097,
check 2643603; logs `logs/smfx-*`, `logs/f2-PD_B_fx.*`, `logs/relfx-*`; scores `f2/runs/relative_score_PD_ADR0353.md`)

### 5.1 Harness

* All 20 stand fits: 2 976 750 training rows = 5 runs × 27 training legs × 21 years × 1 050 cells ✓ (the leaky
  design had 3 231 900).
* `PD_B` re-scored in the same job reproduces ADR 0340 §4.2's table at every printed digit ✓ (so `PD_B_fx` vs `PD_B`
  is the stand alone).
* Fold release v2 `--check` (run m4, GFDL ssp370) against the `_fx` predictions and `PD_B_fx`: structure 6/6 and
  stand 10/12 OK, daily fluxes median 1.5–2.8e-4 relative; the two covers flagged (`fpc7` 99th pct 7 %, `fpc8` 6 %)
  are the **identical** flags v1's check raised against its own predictions (job 2502581: the same quantities and
  sizes to two digits — the training table's float32 hot-day threshold, ADR 0340 §3). ⇒ v2 reproduces its validated
  pipeline exactly as well as v1 did. One-core cost 7.49e-3 core-s per cell-year (v1 7.57e-3).

### 5.2 Structure (relaxed standard, 2071–2100, 15 cases; was → leak-free)

| | dense by the anchor | dense by the held-out run |
|---|---|---|
| D1 tree count | 1.16, 11/15 ✗ → **1.26, 5/15 ✗** | 1.12, 9/15 ✗ → 1.20, 7/15 ✗ |
| D1 biomass per tree | 1.07, 14/15 ✓ → **1.18, 9/15 ✗** | 1.06 ✓ → 1.16, 9/15 ✗ |
| D1 four trait medians | 0.60–0.83 ✓ → 0.59–0.86 ✓ | 0.59–0.86 ✓ |
| D2 worst 10 %: tree count / biomass | 1.29 / 1.01 ✓ → **1.47, 10/15 ✗** / 1.10 ✓ | 1.27 / 1.00 → 1.39 ✓ / 1.07 ✓ |
| D3 dense totals stems / biomass (signed median, case range) | −0.1 % / −1.5 % ✓ → −0.2 % (−2.9…+1.2) / −1.5 % (−7.6…+4.4; 3 cases > 5 %) ✓ | −2.2 % / −1.6 % ✓ |
| S1 sparse tree count / biomass | 2.74 ✓ / 1.34 ✓ → **3.00, 7/15 ✗** / 1.47 ✓ | 3.15, 6/15 ✗ / 1.45 ✓ |
| S2 sparse totals stems / biomass | −2.3 % / −5.7 % ✓ → −5.2 % (−15…+14) / −4.5 % (−23…+9) ✓ | **+20.0 %, 11/15 ✗** / +4.9 % ✓ |
| **criteria passing** | **21 → 18 of 22** | **19 → 17 of 22** |

Harness (run m5 scored as the emulator, leak-free): 0.95–1.03 on every criterion ✓.

### 5.3 No drift in the forest state (dense, typical cell ÷ a second run; ADR 0330's decade table)

| | 2021–40 | 2051–60 | 2091–2100 | pre-registered (2081–2100 ÷ 2021–40) | mid (2051–70) → late (2081–2100) |
|---|---|---|---|---|---|
| tree count | 0.98–1.00 | 1.10–1.12 → 1.12–1.15 | 1.13–1.21 → **1.20–1.24** | 1.17 (8/15) → **1.22 (7/15 ≤ 1.2; 0 > 1.5)** ✗ | ×1.05 → **×1.06 (15/15 ≤ 1.2)** |
| biomass per tree | 0.79–0.80 | 0.97–1.00 → 1.02–1.06 | 1.01–1.10 → **1.09–1.14** | 1.32 (2/15) → **1.41 (1/15; 5 > 1.5)** ✗ | ×1.05 → **×1.05 (13/15)** |
| trait medians | | | late level 0.62–0.85 → 0.63–0.88 | | ×1.10–1.19 → ×1.11–1.20 |

Scenario independence of the pre-registered ratio holds (tree count ssp126 1.22, ssp585 1.23; biomass per tree 1.43 /
1.41). The tree-count creep 2051–60 → 2091–2100 is **+0.05 / +0.10 / +0.12** (ssp126 / 370 / 585; was +0.01 / +0.07
/ +0.12). The reference arms (second run, oracle, anchor, 2019 carried forward) do not depend on the leak and are
unchanged. (The 2021–40 column above is this record's recomputation; the published ADR 0330 table gives 0.92–0.93 /
0.70–0.72 for the leaky fit on a slightly different early window and is left as it is.)

### 5.4 Stand map (ADR 0331 measure, dense cells, level 2071–2100 ÷ a second run, median of 15)

| | leaf area | vegetation carbon | tree cover | grass cover |
|---|---|---|---|---|
| typical cell | 1.37 → **1.45** (15/15 worse) | 1.24 → **1.31** (15/15) | 1.55 → 1.55 | 1.27 → 1.27 |
| worst 10 % | 1.95 → 2.07 | 1.40 → 1.53 | 2.32 → 2.32 | 2.28 → 2.28 |
| mid → late drift | 1.08 → 1.10 | 1.07 → 1.10 | 1.07 → 1.07 | 1.05 → 1.05 |
| \|area total\| late | 1.1 → 1.5 % | 1.9 → 2.2 % | 2.0 → 2.0 % | 1.6 → 1.6 % |

**Cover by plant type is unchanged** (to the third decimal): only runs m1–m4 carry it, so the leaked run m5 was never
in its training rows. Leaf area and vegetation carbon get 5–6 % worse, as expected (§3: 5–12 %).

### 5.5 The whole emulator's daily fluxes (`PD_B_fx`, 13 legs, 238 held-out cells; ADR 0340 §4.2 criteria)

| flux | typical ≤ 3× | worst 10 % ≤ 3× | climate response ≤ 1.5× | totals ≤ 5 % | drift ≤ 1.2 |
|---|---|---|---|---|---|
| GPP | 2.37 → **2.36** ✓ (13/13) | 2.38 → 2.52 ✓ | 1.91 → 1.94 ✗ (1/13) | 1 % ✓ | 1.01 → 1.03 (11/13; IPSL ssp585 1.28, UKESM ssp370 1.26) |
| NPP | 3.85 → **3.94** ✗ (0/13) | 3.03 → 3.03 (6/13) | 2.04 → 2.09 ✗ | 1 % ✓ | 1.03 → 1.04 ✓ |
| ET | 3.14 → **3.09** (5 → 4 of 13) | 1.88 → 1.96 ✓ | 1.80 → 1.82 ✗ | 1 % ✓ | 0.95 → 0.94 ✓ |
| runoff | 5.21 → **5.22** ✗ | 6.53 → 6.56 ✗ | 2.50 → 2.43 ✗ | 2 % ✓ (worst 2.9 %) | 0.90 → 0.90 ✓ |

Leg by leg `PD_B_fx` ÷ `PD_B`: median GPP 1.002, NPP 1.004, ET 1.009, runoff 1.008 (worst 1.12). The stand's increment
over the original's stand (`PD_B_fx` ÷ `PD_A`, ADR 0337 §3 criterion 1): median GPP 1.12, NPP 1.13, ET 1.37, runoff
1.19 (was 1.13 / 1.15 / 1.35 / 1.20); 37 of 104 values > 1.3 (was 32); **the falsifier still fires on the same two
legs** (late GPP IPSL ssp370 1.53, IPSL ssp585 1.75; was 1.58 / 1.74). Every pass/fail of ADR 0340 §4.2 is unchanged
except ET typical losing one leg (5 → 4 of 13) — as expected (§3).

### 5.6 Reading

The leak mattered for the forest **structure** (+7–12 %, three relaxed-standard criteria lost) and for leaf area and
vegetation carbon (+5–6 %), and **not** for the daily fluxes (+0–1 %): the stand's added daily error comes mostly from
plant-type cover (ADR 0338), which the leak never touched. The restated release verdict: structure **18 of 22**
criteria (dense typical tree count AND biomass per tree, dense worst-10 % tree count and sparse typical tree count
fail); no drift after the start state fades (×1.05–1.06 mid → late), but the pre-registered drift rule fails more
clearly (1.22 / 1.41); daily fluxes as before. Release `v1` (deployment) is unchanged; `fold_gfdl-esm4_v2` replaces
`fold_gfdl-esm4_v1` as the validated set-up (v1 kept, never overwritten).
