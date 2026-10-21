# 0353 — Leak-free restatement of the held-out-climate-model numbers: structure map, stand map, the whole emulator's daily fluxes, the fold release (pre-registration)

* **Status:** pre-registered 2026-10-21, before the stand-map refits and the daily run; results in §5.
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

## 5. Results

(to be filled)
