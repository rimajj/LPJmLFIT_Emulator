# 0336 — Learned daily model: early stopping left un-annealed members in seven ensembles (defect, repair, re-scores pre-registered)

* **Status:** Defect found and fixed 2026-10-13; repair jobs 2481050–62 submitted; re-scores pre-registered below,
  before any result. Results §4 (2026-10-13); replicate measurement pre-registered §5.
* **Found by:** arm D47 (ADR 0335 §4) scoring 5–9 % worse than arm D in the medians with 17 % *more* samples.

## 1. The defect

`scripts/f2_train.py` trains each member for 10 epochs on a one-cycle learning-rate schedule (`OneCycleLR` with
`total_steps = epochs × batches`: the rate rises to its peak in the first ~30 % and anneals to ~0 by the last epoch).
With the old default `--patience 2`, two epochs without a new best validation loss stop training and restore the
best state so far. Mid-cycle the rate is high and the validation loss is noisy, so a member could stop at epoch 5–8
holding a state that never saw the low-rate epochs. Measured over every member log in `DATA/f2/runs/`:

| member | epochs run | final val loss | (full members of the same arm) |
|---|---|---|---|
| C seed1 / seed4 | 6 / 9 | 0.0663 / 0.0566 | 0.054–0.056 |
| H seed0 | 8 | 0.0603 | — |
| L seed3 / seed4 | 7 / 9 | 0.0583 / 0.0555 | 0.0547–0.0557 |
| P seed2 | 7 | 0.0877 | — |
| U seed1 / seed2 | 6 / 7 | **0.0884** / 0.0600 | — |
| V seed4 | 7 | 0.0595 | 0.0559–0.0568 |
| D47 seed2 | 7 | 0.0602 | 0.0532–0.0552 |

**Clean ensembles: W and D only** (all 10 members ran 10 epochs). Every ensemble is an equal-weight mean of five
members, so one un-annealed member shifts the ensemble by a random amount that differs between arms. Every arm-vs-arm
comparison that involves C, H, L, P, U, V or D47 is therefore confounded by an amount not known until re-scored.

**Which conclusions are exposed.** ADR 0333 (W vs C, U vs C — the warm-climate coverage result and its swapped-role
confirmation, including the side remark that "one more leg on a fixed 40 M budget worsened early-window fits", which
rests on U, the worst-affected arm); ADR 0334 §4 (L and V both null); ADR 0335 §4 (D47). ADR 0335 §3 (D vs W) is
clean. H and P are older closed arms (not repaired now; their records should be read with this caveat).

## 2. Fix and repair

* `f2_train.py --patience` default **2 → 0 = never stop early** (the best-state restore stays). Members already
  trained are unchanged; anything trained from now on runs all epochs.
* `scripts/f2_repair_stopped.py <prefix> …` re-trains each stopped member from its own logged args under
  `<member>_full` with `--patience = epochs`, then re-runs the ensemble with its own logged args under
  `<prefix>Ef_5seed`. Nothing is overwritten. Submitted for **D47, V, L, C, U** (jobs 2481050–62).

## 3. Pre-registered re-scores (the criteria are the ones already written; only the run changes)

Each repaired ensemble is re-scored with `f2_relative_score.py` against the same criteria as its original record; the
repaired verdict replaces the original one.

* **D47Ef vs WE / DE — ADR 0335 §4 criteria.** If D47Ef passes, it is the deployment model; otherwise arm D is
  (pre-registered there).
* **VEf vs WE — ADR 0334 §3 arm-V criteria** (typical NPP early on UKESM / MPI ssp585 ≤ 2.84 / 3.03).
* **LEf vs WE — ADR 0334 §3 arm-L criteria** (southern respiration excess via `f2_carbon_split.py --blocks=0,1,2,4`;
  the GPP swing via `f2_season_residual.py LEf_5seed`).
* **CEf: ADR 0333 §4 reading** — UKESM GPP / NPP drift of W (1.15 / 1.25) vs repaired C. The coverage conclusion
  stands if W is still ≥ 0.05 below CEf on both. **UEf: ADR 0333 §6** — IPSL ssp585 GPP drift ≤ 1.2 and ≥ 0.05 below
  CEf's, NPP drift ≥ 0.05 below CEf's.
* **The "fixed budget" remark of ADR 0333 §6** (MPI ssp585 NPP early 2.87 → 3.81, ET 2.26 → 2.93 when U added a leg)
  is re-read from CEf vs UEf. Expectation: much of it disappears.
* **Expectation overall:** the repaired ensembles are 0–10 % better than the originals in typical errors; the drift
  verdicts of ADR 0333 survive (they were large: 0.10–0.16); the L and V nulls survive; D47Ef lands within a few per
  cent of arm D, i.e. the sample budget is not the limit.

## 4. Result (2026-10-13; jobs 2481050–62 all completed; season job 2481238)

All eight re-trained members ran 10 epochs and end at validation loss 0.0551–0.0563 (full members 0.053–0.057).
Scores: `DATA/f2/runs/relative_score_repair_ADR0336.md` (free runs, 238 held-out cells).

**Repaired ÷ original ensemble, median over legs × windows (GPP / NPP / ET / runoff):** D47 0.99 / 0.95 / 1.05 /
1.02; V 0.99 / 1.02 / 1.00 / 1.01; L 1.05 / 1.02 / 1.02 / 1.06; C 0.99 / 0.97 / 0.96 / 0.93; U 0.94 / 0.96 / **0.85** /
0.90. So one stopped member moved an ensemble's median by up to 15 % (U's ET), and by much more on single legs.

| record | criterion | original run | repaired run | verdict |
|---|---|---|---|---|
| 0335 §4 (D47) | worst shared-leg ET ratio vs W ≤ 1.15; medians ≤ 1.05 | 1.25; 1.05–1.09 | **1.28; GPP 1.07, NPP 1.04, ET 1.09** | fails; falsifier holds for 2 of 3 legs (MPI ssp126 fell by 0.065, threshold 0.062) ⇒ **arm D stays the deployment model** |
| 0334 §3 (V) | NPP early UKESM / MPI ssp585 ≤ 2.84 / 3.03 | 3.02 / 3.25 | 3.28 / 3.36 (×1.04 / ×1.00 of W) | **null stands** (falsifier: both within ±5 %) |
| 0334 §3 (L) | southern respiration excess ≤ half of W on 2 of 3 | 0.091 / 0.063 / 0.089 | 0.099 / 0.071 / 0.096 | **null stands** |
| 0334 §3 (L) | July − September GPP swing, blocks 2 / 4 ≤ half | 44.6 / 49.8 | 42.6 / 47.6 (W 40.9 / 46.4) | **null stands**; test-climate GPP 1.17–1.20× W's |
| 0333 §4 (W vs C) | UKESM GPP / NPP drift: W ≥ 0.05 below C on both | C 1.30 / 1.41 | **C 1.19 / 1.27** vs W 1.15 / 1.25 | **FAILS** — W is 0.04 / 0.02 below |
| 0333 §6 (U vs C) | IPSL ssp585 GPP drift ≤ 1.2 and ≥ 0.05 below C; NPP ≥ 0.05 below | U 1.12 / 1.13 vs C 1.22 / 1.27 | **U 1.06 / 1.14 vs C 1.13 / 1.20** | passes narrowly (0.07 / 0.06) |
| 0333 §6 remark | MPI ssp585 early NPP / ET, C → U ("fixed budget thins early fits") | 2.87 → 3.81 / 2.26 → 2.93 | 3.05 → 3.51 / 2.18 → 2.38 | smaller (+15 % / +9 %), not gone |

Southern blocks with the repaired arm V: respiration excess 0.130 / 0.095 / 0.120 (still worse than W).

**Reading.** The two nulls of ADR 0334 and arm D as the deployment model survive. The warm-climate coverage effect of
ADR 0333 was overstated by the stopped members of arm C: the growth of the UKESM carbon gap drops by 0.04 / 0.02 (not
0.15 / 0.16) when IPSL joins training, and IPSL's drops by 0.07 / 0.06 (not 0.10 / 0.14) when UKESM joins. Those are
now differences of 2–7 %, and **the spread between two ensembles trained with identical settings has never been
measured**, so none of them, nor arm D's 16–28 % early-window ET cost, can yet be read against it.

## 5. Replicate measurement, pre-registered 2026-10-13 before training: arm W2 = arm W with seeds 5–9

* `W2_3x256_seed5..9` → `W2E_5seed` (jobs 2481246–51; `f2_chain_arm.py --seeds 5-9`, same legs and settings as
  arm W; all of arm W's members already ran 10 epochs, so the new patience default makes no difference).
* **Statistic:** per leg × flux × window the ratio W2 ÷ W of the typical error, and the drift difference W2 − W.
  Their spread is the run-to-run noise of one five-member ensemble.
* **Reading rule (fixed now):** an arm-vs-arm difference counts as evidence only if it exceeds the 90th percentile of
  |W2 ÷ W − 1| (typical errors; per flux) or of |W2 − W| (drift) over all 14 legs. It is applied to: arm D's early-ET
  cost (×1.16–1.28), the coverage margins (UKESM 0.04 / 0.02, IPSL 0.07 / 0.06), D47Ef vs D, and the L/V nulls.
* **Expectation:** typical-error noise ±5–10 % (90th percentile), drift noise ~0.03–0.05 ⇒ the UKESM coverage margin
  is within noise, IPSL's at the edge, arm D's worst ET costs (1.28, 1.19) above it.

## 6. Result of the replicate

(to be appended)
