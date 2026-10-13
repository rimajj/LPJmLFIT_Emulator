# 0336 — Learned daily model: early stopping left un-annealed members in seven ensembles (defect, repair, re-scores pre-registered)

* **Status:** Defect found and fixed 2026-10-13; repair jobs 2481050–62 submitted; re-scores pre-registered below,
  before any result. Results appended in §4.
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

## 4. Result

(to be appended)
