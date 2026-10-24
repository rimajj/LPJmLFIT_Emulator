# 0373 — Deployment release `non_v2mept`: the running-means daily networks retrained on all 10 climate models become the current nitrogen-on release

* **Status:** accepted 2026-10-24. Owner instruction: *"Retrain on all 10 climate models and make it the current
  nitrogen-on release."* (option v1 of ADR 0372's handoff).
* **Supersedes** `release/non_v1` (ADR 0344) as the CURRENT nitrogen-on release. `non_v1` and every other release stay
  on disk unchanged; nothing is overwritten.

## 1. What changes

ADR 0372 chose the trailing running-means daily network (MEPt: the deployed MLP 256×3 + 32 exponential running means
of the weather + a 52-number description of the place over the 30 years before each year) and packaged it as the
FOLD release `non_fold_v2mept`, trained like the scored fold (8 climate models, 80 % of cells). A deployment release
must be trained on everything, as `non_v1`'s daily networks `NCD_s0–4` were (ADR 0344):

* **Networks `xtf/daily/runs/MEPtD_s0–4`** — `xtf_daily.py train --arm MEPt --deploy --seed s`: exactly MEPt's
  design, settings and seeds, but every cell (606 train / 68 validation blocks / none held out, `f2_train.ALL_CELLS`)
  and the 58 legs of `f2_non/runs/NCD_s0/legs.json` (10 climate models × ssp126/370/585 rising CO2 + the 28 CO2-fixed
  legs), 40 M training rows as before.
* **Release `release/non_v2mept`** — `build_release_daily_mep.py --base non_v1 --out non_v2mept --arm MEPt --deploy`:
  a copy of `non_v1` with only `daily.npz`, the setup's place summaries and `release.json` changed; the yearly maps
  (`deploy` arm, all legs, all cells) are `non_v1`'s, byte for byte.

## 2. What it cannot show

A deployment release has no held-out climate model or cell, so its accuracy cannot be scored out of sample. **Its
skill is the fold release's** (ADR 0372 §6: error vs the previous daily networks GPP −12.5 %, NPP −17 %, ET −10 %,
runoff −9.5 %, still better 2071–2100 for every flux), exactly as `non_v1`'s skill was `non_fold_v1`'s. What is
checked here is that the build is correct (gates) and that nothing broke (an in-sample run beside `non_v1` and the
fold release on one leg, against the original and its second run).

## 3. Results

Jobs 2705973 (training, one packed 4-GPU job) and 2705974 (build + runs, chained `afterok`).

**Training:** cells 606 train / 68 validation / 0 held out, 58 legs, ~40 M rows — the same split and legs as
`NCD_s0–4`. Best validation loss 0.040–0.042 (seeds 0–4). Not comparable with the fold networks' 0.067–0.070: the
validation blocks now share climate models with the training data.

**Gates** (`build_release_daily_mep.py --deploy`): numpy == PyTorch 5.4e-7 (extras included); the package's online
running means + place description == the training arrays 9.3e-8 over 3 years and 2 year ends; the setup's arrays
unchanged and its warm-up year == the training arrays' 2019; 19 copied files (the yearly maps, `annual.json`)
byte-identical to `non_v1`'s.

**In-sample sanity** (MPI-ESM1-2-HR ssp370, a leg every deployment network trained on; complete emulator, yearly
capacity; median over cells of the 30-yr-mean error ÷ the original's second run's; GPP / ET / NPP / runoff;
`run_emulator_non.py` + a throwaway comparison):

| | 2021–2050, all cells | 2071–2100, all cells |
|---|---|---|
| `non_v1` (previous deployment) | 1.65 / 2.63 / 1.78 / 4.53 | 1.61 / 2.32 / 1.80 / 4.91 |
| **`non_v2mept`** | **1.21 / 1.86 / 1.29 / 3.71** | **1.33 / 1.95 / 1.29 / 4.23** |
| `non_fold_v2mept` (this leg held out) | 1.44 / 2.06 / 1.37 / 3.99 | 1.52 / 2.30 / 1.46 / 4.92 |

Both deployment releases trained on this leg, so the first two rows compare like with like: the new one is closer to
the original in every flux and both windows. This is a check that nothing broke, not a skill estimate (§2). The
deep-store cell mean sits near 0 mm (−0 to 25 mm over the century; the fold version −5 to 19 mm, `non_v1` 11–28 mm)
— the store may go negative by construction (deficits are taken from it) and this matches the scored fold version.

**Cost** (one core, whole emulator, forcing read excluded, same node back to back): `non_v1` 7.17e-3,
**`non_v2mept` 8.12e-3 core-s per cell-year (1.13×)**; ≈ 117× fewer core-seconds than the original (0.95).

## 4. Decision

`release/non_v2mept` is the **current nitrogen-on release** (user guide `docs/emulator_release.md`, skill
`emulator-release`). `non_v1` stays as the previous deployment. Open: the CO2-fixed late-century runoff (ADR 0372 §6:
1.06× the previous networks' error on 4 held-out legs) is untested further; the nitrogen-off releases (`v4`) do not
have weather memory.
