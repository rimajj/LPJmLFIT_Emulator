# 0362 — Release v3 / fold v4: the four-layer daily networks (built; whole-emulator gain small — owner to confirm)

* **Status:** proposed 2026-10-22. Both releases built and gated; which one is the CURRENT release (v3 or v2) is left to
  the owner, because the measured gain in the complete emulator is much smaller than in the test that adopted it (§3)
  while the cost rises 31 % (§4), and speed is the project's second goal.
* **What:** ADR 0359 §6 adopted 4 × 256 daily networks (`DCL4_3x256_seed0–4`, trained exactly as `D_3x256_seed0–4`
  with `--layers 4`) by its pre-registered rule. New releases, both `--departure dep`, everything else as v2 / fold v3:
  `release/v3` (deployment) and `release/fold_gfdl-esm4_v4` (validated fold), built by
  `scripts/build_emulator_release.py --daily-members DCL4_3x256_seed` (new option; network depth now read from each
  saved network, commits 2729e91b + 580c9827). `release/v2` and `fold_gfdl-esm4_v3` are untouched.

## 1. Gates (jobs 2665238 / 2665239)

numpy == PyTorch daily ensemble 5.1e-7 (bar 1e-5); yearly climate statistics exact; fold anchors exact (255 150 rows);
departure z-scores 3.1e-11 / 3.7e-11.

## 2. Reproduction (fold v4, run m4, GFDL-ESM4 ssp370; job 2665243)

`run_emulator.py --check --check-tag PD_L4_fx`: structure 6 / 6 OK (tree count median 2.3e-4, same as v3's check),
stand 10 / 12 OK with the known `fpc7` / `fpc8` flags (float32 hot-day threshold of the training table, ADR 0340 §3 —
the same quantities and sizes as every earlier check), daily GPP / ET / NPP / runoff 30-yr means per cell median
1.5–2.7e-4 relative to the whole-emulator run `PD_L4_fx`. ⇒ the package reproduces its validated pipeline.

## 3. Accuracy in the complete emulator (`PD_L4_fx` vs `PD_B_fx`; job 2665242, `logs/f2-PD_L4_fx-relscore.md`)

`PD_L4_fx` = `PD_B_fx` (ADR 0353: the daily networks fed the leak-free EMULATED stand, 240 held-out cells, 14 legs)
with only the ensemble swapped. `final_daily_score.py`, 13 legs, × a second run's error (median; legs passing):

| flux | typical cell (≤ 3) | worst 10 % (≤ 3) | climate response (≤ 1.5) | area total | drift (≤ 1.2) |
|---|---|---|---|---|---|
| GPP | 2.36 → 2.42 (13/13) | 2.52 → 2.33 | 1.94 → 1.76 (1 → 2 /13) | 0.01 → 0.01 | 1.03 → 1.01 (11/13) |
| NPP | 3.94 → 3.77 (0/13) | 3.03 → 3.20 (6 → 5 /13) | 2.09 → 2.04 | 0.01 → 0.01 | 1.04 → 1.03 |
| ET | 3.09 → 3.29 (4/13) | 1.96 → 1.82 | 1.82 → 1.76 | 0.01 → 0.01 | 0.94 → 0.97 |
| runoff | 5.22 → 4.99 (0/13) | 6.56 → 6.37 | 2.43 → 2.38 | 0.02 → 0.01 | 0.90 → 0.91 |

Per leg × window (`f2_relscore_compare.py PD_B_fx PD_L4_fx`, median of the ratio): GPP 1.004, NPP 0.942, ET 1.004,
runoff 0.974. With the original's own stand (ADR 0359 §6) the same networks gave 0.92–0.94 / 0.87–0.94 / 0.94–0.99 /
0.84–0.90. **Reading:** once the stand is emulated, its error dominates (ADR 0353: +13–35 % over the daily model's
own) and the deeper network's gain shrinks to NPP −6 %, runoff −3 %, GPP and ET unchanged; the climate response
improves on all four (−2 to −9 %); typical ET is 6 % worse and worst-10 % NPP 6 % worse. One replicate per side, and
the two baseline replicates of ADR 0359 differed by 2–8 % from each other, so only the NPP gain is clearly outside
that noise. No pass count changes except GPP response (1 → 2 of 13) and NPP worst-10 % (6 → 5 of 13).

## 4. Speed (one core, 1 050 cells × 81 years)

Deployment v3, UKESM1-0-LL ssp370 (job 2665302): **9.80e-3 core-s per cell-year** (v2: 7.0e-3, ADR 0358); fold v4
9.82e-3 (fold v2 7.49e-3). +31–40 %; still within the T31-class allowance 0.0135, and 27× / ~680× below the original
at 25 / 500 patches.

## 5. Decision needed

(a) make v3 / fold v4 current (ADR 0359's rule; better NPP and climate response, +31–40 % cost), or (b) keep v2 /
fold v3 current and record that the gain does not survive into the complete emulator. Until decided, the docs, the
paper's results and the coupling runs stay on v2.
