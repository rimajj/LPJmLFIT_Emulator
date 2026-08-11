# ADR 0115 — the count recursion's drift is SCENARIO-ASYMMETRIC; it is not a chain-length artefact and the ratio target makes it worse

- **Status:** accepted (line S, 2026-08-11)
- **Rung:** `EXECUTION_PLAN.md` **rung 1**, line S — runs the two drift experiments ADR 0114 §5.3 pre-registered
  and closes the open gap ADR 0114 §5.4 left. One forest refit (4 min on 48 cpus) + three 24-cpu diagnostics.
- **Related:** 0114 (the drift this chases; **§2's stated cause is corrected here**, §5.3a/b are the two arms,
  §5.4 is the gap now closed), 0113 (arm A1, the level-target recursion), 0112 (the forcing labels and the
  persistence null), 0111 (the one-definition area-weighted ratio and the yardstick basis), 0106 (the
  acceptance criterion), 0102/0103/0105 (the level-anchor history this bears on).
- **Artefacts:** `scripts/rung1_count_ratio_arm.jl` (job **1753653**) → `rung1_count_arm_r0` /
  `rung1_count_arm_r1`; `scripts/diagnose_truth_yardstick.py` scoring all **five** count arms in ONE process
  (job **1753655**, `rung1_yardstick_ratio_arms.csv`, 291 rows); `scripts/rung1_response_decay.py` extended
  with the control's bands, a scenario-resolved drift panel and a matched-lead-depth panel (jobs **1753666**
  A1 / **1753667** R1 → `rung1_decay_{a1,r1}_v3.csv`).
- **Coverage:** all **121 495 658** rows of the frozen pooled count table, both scenarios; **53 607** cells on
  the decay script's own basis, **51 767** on the yardstick's. Nothing here is a five-cell result.

---

## 1. Arm (a) — training on the ratio `n_t / n_{t-1}` — is REFUTED, in both directions

ADR 0114 §5.3a asked whether the recursion's drift is an artefact of predicting a *level* from a *lagged
level*. `rung1_count_ratio_arm.jl` changes exactly the target (and the reconstruction that inverts it):
`y := n_t / n_{t-1}` — exact, since `n_prev >= 1` and `n_living >= 1` on every one of the 121 495 658 rows —
with the same features, the same K-fold-by-cell rule, the same forest hyper-parameters, the same seed and the
same chain machinery as arm A1. Two arms are produced so the target change is separable from the recursion:
**R0** teacher-forced (`n̂ = r̂ · n_prev`, FIT's own `n_prev`) and **R1** recursed (`n̂_t = r̂_t · n̂_{t-1}`,
with the predicted count fed back into the `n_prev` feature). A free end-to-end gate passes exactly:
`max |R1 − R0| = 0` over the **2 669 860** first-year rows, where the two paths must agree by construction.

All five count arms, ONE yardstick process, ONE cell set (51 767), basis `capped400`:

| arm | target | forcing | OOS R² | deatt. per-cell slope (2-seed) | **aggregate area-weighted response ratio** | tropical | subtropical | temperate | boreal |
|---|---|---|---|---|---|---|---|---|---|
| A0 production | level | one-step | **0.9824** | 1.006 | **+0.707** | −0.51 | +3.41 | +0.93 | +1.07 |
| A0-null persistence | — | one-step | 0.9622 | 1.029 | +0.685 | −0.43 | +2.83 | +0.95 | +0.95 |
| **R0** | **ratio** | one-step | 0.9742 | 1.026 | **+0.766** | **−0.15** | +3.17 | +0.95 | +1.06 |
| A1 | level | recursed | 0.9182 | 0.976 | −0.226 | −3.62 | +6.50 | +0.45 | +0.70 |
| **R1** | **ratio** | recursed | **0.6778** | 1.044 | **−1.099** | −6.06 | +5.37 | +0.55 | −0.56 |

**One-step, the ratio target is a small, real improvement on the response and a small loss on accuracy**
(+0.766 vs +0.707 aggregate, tropics −0.15 vs −0.51, at R² 0.974 vs 0.982). **Recursed, it is a disaster.**
Error vs lead time, same rows, arm against arm:

| lead (yr) | 1 | 5 | 12 | 20 | 40 | 80 |
|---|---|---|---|---|---|---|
| R1 bias (stems/patch) | +0.018 | +0.079 | +0.163 | **+0.408** | +0.433 | +0.182 |
| A1 bias | −0.014 | −0.029 | +0.041 | +0.155 | +0.131 | +0.082 |
| R1 RMSE | 0.740 | 1.637 | 2.464 | 2.968 | 3.377 | **3.855** |
| A1 RMSE | 0.596 | 1.109 | 1.413 | 1.520 | 1.640 | 1.717 |

and R1's largest prediction is **799.5 stems in a patch whose observed maximum anywhere in the table is 42** —
a genuine multiplicative runaway in the tail, which nothing was clamped to hide.

**Verdict: refuted, and the reason is worth keeping.** A forest that predicts the level has leaf values inside
the training range `[1, 42]`, so however wrong a self-fed level prediction becomes it cannot leave that
interval — **the level target IS the level anchor.** A forest that predicts a multiplier has no such bound, and
80 slightly-biased multipliers compound. This retro-explains ADR 0113 §2d ("no runaway to anchor") and
**strengthens ADR 0113's decision not to build a separate level anchor: the production model already has one,
for free, and giving it up costs 24 points of R².**

## 2. Arm (b) — matched lead depth — is REFUTED as the explanation, and this CORRECTS ADR 0114 §2

ADR 0114 §2 stated the drift "is not the same size in the two scenarios, **because** ssp370 chains run 80 years
and historic 19". That attribution is wrong. The decay script now builds each cell's two scenario means **lead
by lead, over only the leads present in BOTH scenarios, with equal weight per lead**, so a lead-dependent drift
cancels in the difference by construction. At the deepest matchable depth (mean **18.2** shared leads —
matched-lead comparison saturates at 19 because that is where the historic chains stop, which is why k = 20, 40
and 80 give identical rows):

| basis | A1 | R1 | one-step control, SAME rows |
|---|---|---|---|
| matched lead depth, GLOBAL | **−1.52** | **−4.91** | **+0.52** |
| tropical / temperate / boreal | +0.25 / +0.57 / +1.44 | −0.26 / +0.32 / +2.76 | +0.86 / +0.94 / +1.11 |

**The sign inversion survives exact lead matching.** It is a property of the recursion, not of the unequal
chain lengths.

## 3. What the drift actually is: the recursion's bias depends on the CLIMATE it is run under

The panel that shows it — the arm's bias at *exactly* lead `s`, resolved by scenario (stems/patch):

| lead (yr) | 1 | 3 | 5 | 8 | 12 | 15 | 18 |
|---|---|---|---|---|---|---|---|
| A1 bias, historic | −0.014 | −0.048 | −0.070 | −0.041 | −0.009 | +0.008 | +0.024 |
| A1 bias, ssp370 | −0.013 | −0.008 | +0.001 | +0.041 | +0.080 | +0.103 | **+0.150** |
| **A1 difference (ssp − historic)** | +0.002 | +0.040 | +0.071 | +0.082 | +0.089 | +0.095 | **+0.126** |
| one-step control's difference | +0.002 | +0.032 | +0.024 | +0.017 | +0.006 | +0.024 | +0.051 |
| **R1 difference (ssp − historic)** | −0.004 | +0.054 | +0.132 | +0.203 | +0.272 | +0.305 | **+0.386** |

A drift that were the *same* in both scenarios would cancel in the scenario difference and cost the response
nothing. This one does not cancel: it **grows monotonically with lead and is systematically more positive under
warming**. Put it beside the signal it has to leave alone — **LPJmL-FIT's own global count response is
≈ −0.14 stems/patch** (ADR 0111): at lead 18 the recursion manufactures **+0.126** of spurious, opposite-signed
response, i.e. **90 % of the true signal's magnitude**, of which **+0.074** is in excess of the one-step
control's own row-selection effect on the same rows. The ratio arm's **+0.386** is ~2.8× the entire true
response, which is exactly why R1's aggregate ratio is −1.10.

**This is the reframing the two arms bought.** The failure is not that the self-fed count is inaccurate — its
level bias stays under 2 % (ADR 0113) and it keeps 90 % of its spread (ADR 0114). The failure is that **its
error is climate-dependent**, so it eats the very difference the acceptance criterion is about (ADR 0106's
"especially under climate change"). R1 also decorrelates far faster than A1 (corr at lead 80: **0.726** vs
0.940) while its spread stays at or above the truth's (sd ratio 1.07), a second signature that the two arms
fail differently.

## 4. ADR 0114 §5.4 closed: the control's bands, and what they license

The one-step control is now printed per band on the same rows at every horizon. It is **flat**, while the arm
decays under it — control vs arm as k goes 1 → 80: temperate **1.07 → 0.95** vs 1.07 → 0.45; boreal
**0.99 → 0.91** vs 0.99 → 1.36 (k=20) → 0.51; tropical **0.90 → 0.76 (k=10) → 0.82 (k=40)** vs 0.90 → 0.29 →
−0.51; GLOBAL **+0.90 (k=2) → +0.83 (k=80)** vs +0.93 → −0.64. ⇒ **ADR 0114 §3's per-band
decay curve is confirmed as a property of the recursion, not of the row subset** — the restriction to short
leads also shortens the climate window, and that confound is now measured and is small.

Two by-products worth having on the record:

- **At lead 1, A1 and the control are identical to the printed precision in every band** (0.90 / 1.01 / 1.07 /
  0.99), an independent confirmation that the refit inside the arm script reproduces the production forest
  exactly. R1 differs there (tropical +1.00) precisely because its *target* differs, which is the intended
  contrast.
- **The retired discriminator stays retired** (ADR 0114 §3). Five arms now span an aggregate response ratio of
  **+0.766 → −1.099** — a sign flip and a factor of five — while their deattenuated per-cell slopes sit inside
  **0.976 – 1.044**. Three demonstrations; do not quote that slope as evidence about the response again.

## 5. A units correction in `rung1_response_decay.py` (ratios unaffected)

`n_living` in the count table **is already a per-patch stem count** (mean 8.28 over all rows); the script
divided it by the ensemble size a second time. Every **ratio** ever produced by it is unaffected — the factor
cancels in numerator and denominator, so ADR 0114's response ratios, sd ratios and correlations all stand — but
the **level** panels were 25× too small for the "stems/patch" label they carried. Fixed; ADR 0114 §1's
`mean(pred) / mean(truth)` row is on the old scaling (0.2559/0.2564 there = 6.40/6.41 here). Flagged rather
than silently re-scaled, because the ADR is immutable.

## 6. Decision

1. **Do not pursue further TARGET-FORM changes for the count recursion.** The ratio target is measured worse in
   accuracy, in drift, in scenario asymmetry and in the aggregate response. Any future proposal to change what
   the count model predicts must first beat §1's table.
2. **Stop attributing the response inversion to unequal chain lengths** (ADR 0114 §2's stated cause). It
   survives exact lead matching; report it as a scenario-asymmetric drift.
3. **The next count experiment targets the CONDITIONING channel that makes the drift climate-dependent**, and
   the cheapest well-posed one needs no refit: at a fixed lead, regress each cell's excess drift on that cell's
   ssp370-minus-historic change in each of the 15 conditioning features. That names which feature carries the
   scenario signal into the error, and it is the prerequisite for any arm that proposes to fix it.
4. **The validity horizon statement of ADR 0114 §5.2 is unchanged** and now has its control: *self-feeding, the
   stem-count warming response is faithful for ~3 years, degraded by 10, inverted by 40.*

## 7. What this does not settle

Only `n_prev` is recursed, so A1/R1 remain **strict lower bounds** on free-running error (six other
roster-state features still come from LPJmL-FIT). All of it is **offline**, so the coupled model can only be
worse (ADR 0105 §5). None of it reaches the **trait axes**, which no offline S-only arm can (ADR 0113 §2e). And
the decay script's ratios are on **its own basis** (the table's own seed-1 truth, 53 607 cells), not the
yardstick's — ADR 0114's warning stands: never quote a decay ratio against a yardstick number.
