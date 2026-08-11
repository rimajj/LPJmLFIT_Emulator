# ADR 0116 — the count recursion's scenario-asymmetric drift runs through the STAND-STATE channel, and it is a ONE-SIDED failure to follow LPJmL-FIT's stem LOSSES

- **Status:** accepted (line S, 2026-08-11)
- **Rung:** `EXECUTION_PLAN.md` **rung 1**, line S — runs the single diagnostic ADR 0115 §6.3 pre-registered
  ("at a fixed lead, regress each cell's excess drift on that cell's ssp370-minus-historic change in each of
  the 15 conditioning features"), plus the mean-bearing extension §4 that the pre-registered form cannot
  deliver. **No forest refit, no new model run**; three 24-cpu jobs of ~4 min each.
- **Related:** 0115 (pre-registers this; its §3 control row is corrected in §1 below), 0114 (the decay panel
  and the `lead_index` chain definition reused here), 0113 (arm A1 — the recursion whose drift this explains;
  §3's retirement of the per-cell slope, which is **not** reopened), 0112 (the one-step forcing label and the
  persistence null), 0111 (the one area-weighted ratio definition), 0107 (`co2` constant by construction),
  0106 (the acceptance criterion this bears on).
- **Artefacts:** `scripts/rung1_drift_attribution.py` → `/p/tmp/jamirp/emulator_global/rung1_drift_attribution.csv`
  (210 rows); jobs **1753852** (§1–§4 attribution), **1753855** (adds the response decomposition),
  **1753886** (adds the stem-count-level control) — `logs/S-driftattr3.1753886.out` is the complete panel.
- **Coverage:** all **121 495 658** rows of the frozen pooled count table, both scenarios. The per-cell panels
  use **52 613 / 50 830 / 49 282** cells at leads **5 / 12 / 18** (every cell with rows at that exact lead in
  *both* scenarios), area-weighted by cos(lat). Nothing here is a five-cell result.
- **Basis:** the count table's **own seed-1 truth** (`y.f64`), stems/patch — *not* the yardstick's basis.
  ADR 0114 §5.5 stands: never quote one of these numbers against `S_truth_yardstick_summary.csv`.

---

## 1. The panel reproduces ADR 0115 §3 exactly — and finds one transcription slip in it

Before attributing a drift, the drift has to be the same one. The script's §0 recomputes ADR 0115 §3's
row-level bias from the arm's predictions, the control's predictions and the keys, through the *imported*
`lead_index` (not a re-derived copy):

| lead | 5 | 12 | 18 |
|---|---|---|---|
| A1 bias difference (ssp370 − historic), **here** | +0.0705 | +0.0887 | +0.1255 |
| A1 bias difference, **ADR 0115 §3** | +0.071 | +0.089 | +0.126 |
| one-step control's difference, **here** | +0.0308 | +0.0061 | +0.0513 |
| one-step control's difference, **ADR 0115 §3** | **+0.024** | +0.006 | +0.051 |

The arm row agrees to the printed precision at every lead. The control row agrees at leads 12 and 18 and
**disagrees at lead 5**: ADR 0115 §3 prints **+0.024**, which is the value its own producing CSV
(`rung1_decay_a1_v3.csv`) carries at lead **4** (0.023876) — a one-row slip while transcribing a table whose
columns skip lead 4. The correct value is **+0.031**. **Nothing downstream moves:** ADR 0115's prose quotes
only the lead-18 excess (+0.126 − 0.051 = +0.074), which is unaffected, and its conclusions rest on the arm
row. Recorded here rather than edited there (ADRs are immutable — supersede, don't edit).

## 2. The channel is STAND STATE, not climate

At each lead, per cell: `drift_arm = mean(pred−truth | ssp370) − mean(pred−truth | historic)`, the same for
the one-step control, `excess = drift_arm − drift_ref`, and `dX_j` = the cell's ssp370-minus-historic change
in each conditioning feature. `soil_depth` and `co2` have `dX ≡ 0` by construction (a per-cell constant, and
ADR 0107) and drop out, leaving 13. Weighted univariate correlations with the **excess** drift, at lead 18:

| feature | `n_prev` | `age_mean` | `hmean` | `hmax` | `agb` | `eco_diag_gdd_5` | `lai` | `tas_cold_month` | `water_stress` | `bm_inc_cell` | `fpc` | `soilmoist` | `growth_eff` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| r(excess) | **−0.336** | **+0.330** | +0.269 | +0.121 | +0.089 | −0.084 | +0.075 | −0.043 | −0.042 | +0.040 | −0.028 | +0.025 | +0.001 |

Greedy forward selection on weighted R² (the collinearity-robust reading) picks the same two first at both
deep leads — lead 18: `n_prev` (0.113) → `age_mean` (0.163) → `fpc` (0.171) → `agb` (0.191); lead 12:
`n_prev` (0.119) → `age_mean` (0.170). **Every climate and flux feature is at |r| ≤ 0.084**, an order of
magnitude below the two state features.

**The control is what makes this a finding rather than a description of the rows.** Scored on the identical
cells, the one-step control's own scenario asymmetry decomposes differently and far more weakly — R² **0.096**
against the excess drift's **0.250**, its first-selected feature is `growth_eff` (a flux), and its correlation
with `n_prev` is ≈ 0 (**−0.038**). So the previous-count / mean-age channel belongs to the **recursion**, not
to the row selection: the one-step error runs through the fluxes, the recursion's extra error runs through the
stand state.

Two cautions that are part of the result:

* **Do not read the height/cover coefficients individually.** `hmean` +0.91 and `hmax` −0.88 in the multiple
  regression are a collinear pair (VIF 16.5 and 15.3; `fpc` 19.1, `lai` 12.7). Forward selection puts `hmean`
  no higher than 5th. Quote the selection path, not the betas.
* **The pattern is global, not tropical.** Across the four latitude bands `r(excess, n_prev)` spans −0.28 to
  −0.38 and `r(excess, age_mean)` +0.27 to +0.39, with mean excess +0.076 to +0.088. Despite ADR 0113's
  wrong-signed tropics, **this channel is the same everywhere** — a band-specific fix is not indicated.

## 3. What the pre-registered form cannot answer — stated, because it is a limit of the design

The regression explains **R² 0.14 / 0.25 / 0.25** of the excess drift's cross-cell spread at leads 5 / 12 / 18,
so three quarters of the spatial pattern is not carried by any conditioning feature's scenario change. More
fundamentally: it is fitted on weighted-**centred**, z-scored columns, so it explains the drift's *spread* and
is **blind to its mean** — and the mean (+0.081 at lead 18) is the entire reason the aggregate response
inverts. The diagnostic as pre-registered names a channel; it cannot by itself say where the mean comes from.
§4 is the extension that can, and it is what changes the picture.

## 4. THE FINDING: the drift is one-sided — the recursion follows FIT's stem gains, not its losses

By construction `drift = (prediction's response) − (truth's response)`, so bin cells by **FIT's own** count
response `dy` at that lead. A *linear* reading explains little (slope of the arm's drift on `dy` = −0.103,
r = −0.37, R² 0.14 at lead 18). The **decile table** shows why — lead 18, area-weighted, stems/patch:

| decile of FIT's own response | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| FIT's response `dy` | −4.32 | −1.97 | −1.20 | −0.72 | −0.35 | +0.00 | +0.37 | +0.83 | +1.56 | +4.17 |
| cell's own stem count | 10.59 | 8.99 | 7.95 | 7.26 | 6.94 | 6.40 | 6.43 | 6.57 | 6.95 | 8.15 |
| **arm's drift** | **+0.575** | +0.443 | +0.367 | +0.265 | +0.136 | +0.026 | −0.075 | −0.142 | −0.162 | **−0.157** |
| one-step control's drift | +0.198 | +0.109 | +0.081 | +0.064 | +0.031 | +0.015 | −0.008 | −0.022 | −0.025 | −0.012 |
| **excess drift** | **+0.377** | +0.334 | +0.287 | +0.201 | +0.105 | +0.011 | −0.068 | −0.120 | −0.137 | **−0.145** |
| arm's drift ÷ stem count | +0.0555 | +0.0532 | +0.0516 | +0.0389 | +0.0177 | −0.0009 | −0.0186 | −0.0285 | −0.0265 | −0.0187 |

At **comparable magnitude of FIT's response** (−4.32 vs +4.17), the arm's drift is **3.7× larger on the losing
side**. Read as the fraction of FIT's own response the arm reproduces, this is:

| lead | large DECLINE (decile 1) | large INCREASE (decile 10) | shortfall ratio |
|---|---|---|---|
| 5 | 89.9 % | 98.1 % | 5.3× |
| 12 | 87.1 % | 94.6 % | 2.4× |
| 18 | **86.7 %** | **96.2 %** | **3.5×** |

**The self-feeding count model reproduces ~87–90 % of a large stem decline but ~95–98 % of a large increase.**
Because LPJmL-FIT's own global count response is a net **loss** (−0.156 stems/patch at lead 18, −0.062 at 12),
this rectified error lands almost entirely on the loss side and surfaces as a net **positive** drift — which is
exactly the wrong-signed aggregate response ADR 0113 measured. The mean is not a mystery once the error is
seen to be one-sided.

Three checks that the asymmetry is real:

1. **It is not the truth's own noise.** `drift` contains `−Δtruth`, so binning any drift on `Δtruth`
   correlates mechanically. The **excess** column is immune by construction: `excess = drift_arm − drift_ref`
   cancels the truth term exactly, leaving `Δpred_arm − Δpred_ref`. The asymmetry is quoted on it
   (+0.377 vs −0.145, **2.6×**) as well as on the raw drift.
2. **It is not a stem-count level effect.** The obvious alternative — declining cells simply being the dense
   ones — is refuted: the two extreme deciles differ by only **1.3×** in stem count (10.59 vs 8.15), and after
   dividing the drift by the cell's own count the asymmetry is still **3.0×** for the arm (+0.0555 vs −0.0187)
   and **2.2×** for the excess.
3. **The control is flat by comparison.** Its decile range is 0.21 against the arm's 0.73, i.e. the one-step
   predictor's drift is nearly symmetric in the same bins.

It holds at all three leads (raw asymmetry 4.4× / 2.2× / 3.7× at leads 5 / 12 / 18; level-normalised
2.6× / 1.6× / 3.0×) and is not a single-lead artefact.

⚠ The per-decile percentages above are **aggregate ratios within a stratum** (ratio of weighted means, the
ADR 0111 §5b definition applied inside a bin). They are **not** the per-cell deattenuated slope, which
ADR 0113 §3 retired as a discriminator and which stays retired.

## 5. Decision

1. **The next count arm must be evaluated on the loss side specifically.** Pre-registered criterion: a
   proposed fix works if the arm's **decile-1 excess drift falls from +0.377** (lead 18) **without decile 10's
   magnitude rising** — the aggregate response ratio alone cannot distinguish a real fix from a
   compensating positive bias. Regenerate with `scripts/rung1_drift_attribution.py` (same leads, same
   `lead_index`).
2. **Do not propose adding or re-weighting a climate or flux conditioning feature to fix this.** No climate
   feature carries the scenario signal into the recursion's error (|r| ≤ 0.084 against the state features'
   0.33), and the control shows the flux channel is where the *one-step* error lives. A proposal to change the
   conditioning must refute §2's table first.
3. **Any future drift attribution carries a mean-bearing panel beside the regression.** A regression on
   centred columns cannot explain a mean; §3 is the record of that costing this diagnostic its headline until
   §4 was added.
4. **Do not read collinear feature coefficients individually** (VIF ≥ 12 for `hmean`/`hmax`/`fpc`/`lai`) —
   report the forward-selection path.
5. **ADR 0115 §3's control row at lead 5 should read +0.031, not +0.024** (§1). No conclusion changes.

## 6. What this does not settle

* This is an **association over cells**, not a mechanism. It names the channel the scenario signal enters
  through; it does not prove why the recursion is rectifying. The obvious mechanism-level candidate — that a
  forest predicting a level from a lagged level cannot chase a declining state downward as fast as it follows
  a rising one — is consistent with ADR 0115 §1's "the level target is itself the level anchor", but is
  **not tested here**.
* The regressors are **LPJmL-FIT's own** feature changes (the frozen `X.f64`), not the arm's recursed state.
  That is deliberate (the exogenous version of the question), but it means `dX(n_prev)` is FIT's previous-year
  count change, not the arm's.
* Only `n_prev` is recursed, so this remains a **strict lower bound** on free-running error (ADR 0113 §7).
* All of it is **offline** — the coupled model can only be worse (ADR 0105 §5) — and none of it reaches the
  **trait axes**, which no offline S-only arm can (ADR 0113 §2e).
* Leads 5/12/18 only. Lead 18 is the deepest lead both scenarios reach, so the asymmetry is **not** measured
  at the ssp370 chains' full 80-year depth, where no historic counterpart exists.
