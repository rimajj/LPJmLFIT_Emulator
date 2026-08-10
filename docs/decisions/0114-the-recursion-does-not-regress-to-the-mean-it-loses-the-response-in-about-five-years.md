# ADR 0114 — the count recursion does NOT regress to a conditional mean; it keeps 90 % of its spread and loses the warming response in about five years of self-feeding

- **Status:** accepted (line S, 2026-08-10)
- **Rung:** `EXECUTION_PLAN.md` **rung 1**, line S — answers the one question ADR 0113 §6 left open, from
  artefacts already on disk. No forest refit, no model run: one 24-cpu job, ~2 min.
- **Related:** 0113 (the A1 arm this diagnoses; §6 is the question), 0112 (the forcing-basis labels), 0111 (the
  one-definition rule for the aggregate ratio, applied here too), 0106 (the acceptance criterion), 0105
  (offline bounds coupled).
- **Artefacts:** `scripts/rung1_response_decay.py` (job **1747677**), output
  `/p/tmp/jamirp/emulator_global/rung1_response_decay.csv` (52 rows).
- **Coverage:** all 121 495 658 rows / 53 607 cells of the frozen pooled count table, both scenarios. ⚠ **Its
  own basis, and it is NOT the yardstick's** — see §4.

---

## 1. The recursion is not regressing to a conditional mean — so do not "fix" it with a variance-preserving predictor

At each exact lead time (years since the chain was last handed LPJmL-FIT's own count), over the arm's own
predictions:

| lead (yr) | 1 | 5 | 12 | 20 | 40 | 80 |
|---|---|---|---|---|---|---|
| mean(pred) / mean(truth) | 0.2559 / 0.2564 | 0.2914 / 0.2926 | 0.3274 / 0.3258 | 0.3356 / 0.3294 | 0.3507 / 0.3455 | 0.3614 / 0.3581 |
| **sd(pred) / sd(truth)** | **0.983** | 0.958 | 0.945 | 0.944 | 0.921 | **0.904** |
| corr(pred, truth) | 0.994 | 0.978 | 0.964 | 0.959 | 0.950 | **0.940** |
| same ratio for the one-step arm | 0.983 | 0.979 | 0.980 | 0.981 | 0.976 | 0.975 |

The regression-to-the-mean signature would be a collapsing `sd(pred)` with a flat mean. **It is not there:** after
**80 years** of feeding on itself the prediction still carries **90 %** of the truth's between-patch spread and
correlates with it at **0.94**, against 0.975/— for the one-step arm at the same lead. ⇒ **ADR 0113 §6's first
hypothesis is refuted. Do not build a variance-preserving or distribution-sampling count predictor to fix this**
— the spread is already there. (The "determinism dividend" of ADR 0093 §5 is a separate, still-valid idea about
predicting the ensemble expectation instead of a draw; it is not a fix for *this*.)

## 2. What does break: a lead-dependent bias the same size as the entire warming response

The mean bias grows with lead and then flattens — `+0.155` stems/patch at lead 20, `+0.13` at 40, `+0.08` at 80
(ADR 0113 §2d). Put that next to the quantity it has to not disturb: **LPJmL-FIT's own global count response is
−1.74 % of stems per patch ≈ −0.14 stems/patch** (ADR 0111). **The recursion's own drift is the same size as the
signal, and it is not the same size in the two scenarios**, because the ssp370 chains run up to 80 years while
the historic chains run 19. A difference of two biases at different lead depths is what the response statistic
then reports.

So the defect is neither lost information nor a collapsed distribution: it is a **small, slowly-saturating,
lead-dependent level drift that is large relative to a very small climate signal**. That reframes the fix —
what must be controlled is the drift's *dependence on lead*, not the predictor's variance.

## 3. The response half-life: about 3–5 years of self-feeding, mostly gone by 10–20

Area-weighted prediction/truth response ratio using only rows at lead ≤ k (so k = 1 is the one-step arm by
construction), per latitude band, with the one-step arm scored on the **same rows** as a control:

| k (yr) | tropical | subtropical | temperate | boreal | GLOBAL (arm) | GLOBAL (one-step, same rows) |
|---|---|---|---|---|---|---|
| 1 | +0.90 | +1.01 | +1.07 | +0.99 | n/d | n/d |
| 2 | n/d | +1.03 | +1.07 | +1.00 | +0.93 | +0.905 |
| 3 | +0.52 | +0.98 | +1.03 | +1.02 | +1.27 | +1.204 |
| 5 | n/d | +0.86 | +0.95 | +1.08 | n/d | n/d |
| 10 | +0.29 | +0.49 | +0.77 | +1.18 | n/d | n/d |
| 20 | +0.16 | n/d | +0.59 | +1.36 | n/d | n/d |
| 40 | −0.51 | +1.81 | +0.53 | n/d | −0.63 | +0.769 |
| 80 | n/d | +1.96 | +0.45 | +0.51 | −0.64 | +0.835 |

**(a) At one step the count response is right in every band — 0.90 to 1.07.** That is the strongest statement
yet that the count model *has* a warming response; it is simply not preserved through self-feeding.
**(b) It decays over roughly 3–5 years and most of it is gone by 10–20.** Temperate 1.07 → 1.03 → 0.95 → 0.77 →
0.59 → 0.45; tropical 0.90 → 0.52 → 0.29 → 0.16 → wrong-signed. **(c) Boreal is the exception** — it holds and
overshoots (0.99 → 1.18 → 1.36) before collapsing at k = 80, which is consistent with the boreal band being the
one with a large real carbon/count response (ADR 0111: +19.4 % boreal above-ground C).
**(d) The confound-controlled comparison is the last two columns**, because restricting to lead ≤ k also
shortens the *climate window*, which changes the truth's own response. Arm ÷ one-step on identical rows:
**1.03** at k = 2, **1.06** at k = 3, then **−0.82** at k = 40 and **−0.76** at k = 80. Up to ~3 years the
recursion is indistinguishable from being handed the truth; by 40 it has inverted.
⚠ The control column is `n/d` at k = 5–20 (the truth's *global* band S/N < 3 on those windows) and the script
does not yet print the control's *bands*, which is the one gap in this diagnostic — the per-band decay above is
therefore arm-only, and the k ≤ 3 vs k ≥ 40 contrast is what the control actually establishes.

## 4. ⚠ This ADR's ratios are on a DIFFERENT BASIS from ADR 0111/0113 — do not mix them

This script scores against **the count table's own seed-1 `y`, on 53 607 cells**, because the two-seed
deattenuation and the ≥ 30-stem paired set are not defined on a lead-restricted subset. ADR 0111/0113's
`+0.707` / `−0.226` are the **two-seed mean truth on 51 767 cells**. The same quantity, both bases:
**one-step +0.835 here vs +0.707 there; A1 −0.635 here vs −0.226 there.** Both bases agree on every sign and on
the ordering; the magnitudes differ by up to 2.8×, which is exactly the size of basis effect ADR 0111 documented.
**Quote a decay ratio only with "seed-1 truth, 53 607 cells" attached, and never against the yardstick's
number.**

## 5. Decision

1. **Do not pursue a variance-preserving / distribution-sampling count predictor as a fix for the recursion.**
   §1 measures the spread intact at 0.90 after 80 years. Any proposal of that shape must first refute §1.
2. **The count emulator has a validity horizon, and it is short.** State it: *self-feeding, the stem-count
   warming response is faithful for ~3 years, degraded by 10, and inverted by 40.* This is the honest form of
   the acceptance statement for counts under ADR 0106, and it is the number a century-long ESM run cares about.
3. **The next count experiment targets the LEAD-DEPENDENT DRIFT, not the response directly.** Two candidates,
   both cheap on existing artefacts and to be run as separate arms: (a) train the model on the *ratio*
   `n_t / n_{t-1}` rather than on `n_t` (the AR target already cancels the level — check whether the drift is an
   artefact of predicting a level from a lagged level), and (b) measure the drift's scenario-dependence
   directly by scoring historic and ssp370 chains **at matched lead depth** instead of matched calendar window.
4. **Print the control's bands** in `rung1_response_decay.py` before this table is quoted per band again (§3d).

## 6. What this does not settle

Only `n_prev` is recursed (ADR 0113's lower bound still applies), the arm is offline, and the diagnostic is a
count-side one — §1's variance panel says nothing about the trait axes, which no offline S-only arm can reach
(ADR 0113 §2e).
