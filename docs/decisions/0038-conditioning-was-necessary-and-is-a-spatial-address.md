---
status: "accepted"
date: 2026-07-31
deciders: "engineering agent on line S (full autonomy per STEERING_PROMPT.md). Four decisions: (1) the ADR-0030 §4 S2 criteria are MET, for the first time, by `env-qrf-b6x2M` — 6 trees x 2M subsample, max_depth 22, min_leaf 20, QRF=1, ncond 14 — measured on the historic-static basis; (2) ADR 0037's central thesis is SUPERSEDED: the estimator lever SATURATES at Wooddens 0.867, below the 0.889 threshold, so it cannot close the gap at any artifact size, and the conditioning expansion S2 was scoped around is what carries both criteria across — S2's premise is vindicated, not refuted; (3) the shipped artifact is `recruit_copula_global_historic_t9.rcop` and it is NOT handed to line M as the pooled production copula, because the +0.037 it gains is substantially a per-cell SPATIAL LOOKUP (the six env columns have within-cell sd exactly 0 for 100% of cells) and two of the four criteria are not computable for pooled at all; (4) three silent-failure paths found while shipping it are closed in code: `.rcop` format v2 carries `qrf`, the emulator rejects a conditioning-width mismatch at construction, and the ADR-0030 gate refuses a floor built from two seeds that are the same seed."
consulted: "ADR 0030 §4 (the four success criteria, verbatim, and the attenuation-corrected ceiling they are defined against), ADR 0037 (the accepted ADR this one supersedes in part), ADR 0033 (the twice-recorded warning that this line credits one change with another's effect — why every lever here is a matched pair), ADR 0023/0025 (the train/inference contract, the frozen 4-axis recruit-trait bundle and the pluggable `cond` policy), ADR 0027 (the transient-boundary basis, which is why the historic-static artifact is not the pooled one), ADR 0004 (the constant-CO2 regime, which makes `co2` a dead conditioning column), ADR 0036 §5b (polars streaming key-set nondeterminism — why `t9` REUSES the `t8` tables instead of rebuilding), CLAUDE.md §9 (versioned artifacts, per-line ownership, the `.rcop` contract)"
informed: "lines/S/STATE.md (NEXT + the corrected lever table), lines/M/STATE.md (an integration point is OPEN: `scripts/extract_cell_slow_init.py` hard-aborts on a 14-column `cond_cols` tail, and M must not re-pin onto t9 until the spatial-lookup question is settled), the slow-drf-pipeline + julia-test skills, MEMORY.md (the ssp370 seed2 duplication), changelog.d/S-copula-artifact-acceptance.md, changelog.d/S-conditioning-necessary-spatial-address.md"
---

# Conditioning was necessary after all — and the six columns that cross the gate are a spatial address

> **Status.** `accepted`. The S2 gate is **met on the historic-static basis** and the artifact is **not**
> promoted to line M's pinned production copula. Every code change is opt-in and default byte-identical
> (guardrail 4), verified rather than asserted: full CI-faithful suite **107 394 pass / 0 fail / 4 broken**
> (job 1647687), Runic 1.7.0 clean on 111 of 111 files, the committed v1 `.rcop` fixture still loads, and no
> committed baseline moved. Both new guards were self-tested in BOTH directions.

## 1. What was asked, and the shape of the answer

Milestone S2 was scoped as *expand the recruit copula's conditioning*. ADR 0037 measured the gap with a
per-cell LightGBM decomposition, concluded the cause was the ESTIMATOR rather than missing covariates, and
demoted conditioning to "a SECOND-order lever, ~4× smaller" (`ADR 0037:170-171`). It deliberately deferred
the production choice until a QRF × capacity matrix completed. That matrix is now complete — twelve rungs,
each a re-run of the K-fold-by-cell OOS evaluation on an **unchanged** copula table at a chosen
`(ntrees, subsample, max_depth, QRF, ncond)`, scored against the ADR-0030 gate.

The answer inverts ADR 0037's, and not by a small margin: **the estimator lever saturates below the
threshold and cannot reach it at any artifact size, while the conditioning expansion carries both failing
criteria across.** But the mechanism by which it does so is not the one the milestone assumed, and that is
the more important finding — §6.

**The criteria, verbatim from `ADR 0030:128-130`** (they are restated here because two prior sessions scored
the wrong statistic against them): *"close ≥ 50 % of the Wooddens GAP to the ceiling, and bring
`sd(pred)/sd(Y1)` to ≥ 0.75 on that axis, with pooled KS not degraded (≤ 0.02) and no other axis losing
more than 0.01 of `r_center`."* Baseline `t8`: Wooddens `emu_r` 0.814, ceiling 0.964, GAP 0.150 ⇒ the
criterion-1 threshold is `emu_r` **0.889**. Baseline `r_center` 0.894/0.844/0.870/0.958; baseline pooled KS
0.0051/0.0052/0.0069/0.0115.

## 2. The ladder

Wooddens rows, from each job's `ATTENUATION-CORRECTED headroom` and `BETWEEN-CELL DISPERSION` blocks;
pooled KS from the two `score_slow_copula_ks.py` sweeps (jobs 1646363 / 1646487).

| rung | ntrees × subsample, depth | QRF | ncond | `emu_r` | %GAP | `sd_ratio` | pooled KS SLA/W/D95/minw | C1 | C2 | C3 | C4 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `cap50k-baseline` 1644235 | 40 × 50k, d14 | 0 | 8 | 0.814 | — | 0.6775 | .0051/.0052/.0069/.0115 | — | ✗ | — | — |
| `d22-at-50k` 1646465 | 40 × 50k, d22 | 0 | 8 | 0.829 | 10.0 % | 0.6796 | .0021/.0024/.0025/.0057 | ✗ | ✗ | ✓ | ✓ |
| `qrf-at-baseline2` 1646346 | 40 × 50k, d14 | 1 | 8 | 0.827 | 8.7 % | 0.6749 | — | ✗ | ✗ | n/m | ✓ |
| `b12x500k-d14` 1646466 | 12 × 500k, d14 | 0 | 8 | 0.821 | 4.7 % | 0.7275 | .0074/.0024/.0040/.0070 | ✗ | ✗ | ✓ | ✓ |
| `b12x500k` 1644237 | 12 × 500k, d18 | 0 | 8 | 0.844 | 20.0 % | 0.7490 | .0041/.0024/.0033/.0074 | ✗ | ✗ | ✓ | ✓ |
| `b24x500k` 1644239 | 24 × 500k, d18 | 0 | 8 | 0.843 | 19.3 % | 0.7487 | .0051/.0029/.0043/.0078 | ✗ | ✗ | ✓ | ✓ |
| `b40x500k` 1644436 | 40 × 500k, d18 | 0 | 8 | 0.842 | 18.7 % | 0.7508 | .0055/.0032/.0047/.0082 | ✗ | ✓ | ✓ | ✓ |
| `b6x2M` 1644238 | 6 × 2M, d22 | 0 | 8 | 0.862 | 32.0 % | 0.7704 | all four improve | ✗ | ✓ | ✓ | ✓ |
| `qrf-b6x2M` 1644615 | 6 × 2M, d22 | 1 | 8 | 0.864 | 33.3 % | 0.7575 | .0058/.0016/.0022/.0019 | ✗ | ✓ | ✓ | ✓ |
| `qrf-b6x8M` 1646347 | 6 × 8M, d26 | 1 | 8 | **0.867** | 35.3 % | 0.7633 | — | ✗ | ✓ | n/m | ✓ |
| **`env-qrf-b6x2M` 1646354** | **6 × 2M, d22** | **1** | **14** | **0.901** | **58.0 %** | **0.8541** | **.0032/.0024/.0019/.0013** | **✓** | **✓** | **✓** | **✓** |
| `env-qrf-b6x8M` 1646355 | 6 × 8M, d26 | 1 | 14 | 0.903 | 59.3 % | 0.8551 | .0039/.0045/.0022/.0017 | ✓ | ✓ | ✓ | ✓ |

`n/m` = not measured; those two rungs were never KS-scored and this ADR does not claim otherwise.

**Criterion 1 is robust to the convention.** Five defensible readings all pass, minimum 56.7 %: fixed
baseline denominator `(0.901−0.814)/0.150` = 58.0 %; the rung's own ceiling `1−0.065/0.150` = 56.7 %;
`r_center` headroom `(0.933−0.844)/0.156` = 57.1 %; raw floor gap `1−0.036/0.123` = 70.7 %; raw Spearman
85.1 %. The margin is +0.012 `emu_r` on the threshold, against an analytic SE of ~0.0008 (r ≈ 0.9,
n = 52 165) and an empirical config-noise estimate of ±0.002 (the 12/24/40 × 500k trio: 0.844/0.843/0.842).
Every axis closed more than half its GAP: SLA 60.6 %, Wooddens 58.0 %, D95max 72.0 %, minwscal 70.7 %.

**The comparison is PAIRED, so the +0.087 is not draw luck.** `eval_slow_copula.jl:143` assigns folds as
`mod(hash(cell), kfolds)` — a function of cell id only, so `test_rows` are identical across rungs
(39489141 / 39321209 / 39463322 / 39419344 / 40028851 in both the baseline and 1646354) — and `:168` draws
the quantile level as `rand01!(Xoshiro256pp(i * 131 + a))`, a function of row index and axis only. Same row,
same `u`, different conditional. **The basis is identical at the inode level**, not merely numerically:
`Y_Wooddens.f64` is inode 33837919809 and `cells.i64` inode 33837919817 in the `t8` table, in the baseline
shadow and in the `env-qrf-b6x2M` shadow (a shadow → `t8env` → `t8` symlink chain), so the observed targets,
the 52 165-cell gate set and the seed2 floor are literally the same bytes.

## 3. The three levers, isolated — and why they must not be collapsed

Matched pairs only (rungs differing in exactly one factor).

| lever | matched path | Δ Wooddens `emu_r` | Δ `sd_ratio` | crosses the gate? |
|---|---|---|---|---|
| QRF at baseline capacity | `cap50k-baseline` → `qrf-at-baseline2` | +0.013 | **−0.003** | no |
| QRF at 2M | `b6x2M` → `qrf-b6x2M` | +0.002 | **−0.013** | no |
| capacity (subsample+depth), ncond 8, QRF=1 | 50k → 2M → 8M | +0.037, then **+0.003** | +0.0884 | **no — saturates at 0.867** |
| capacity, ncond 14, QRF=1 | 2M → 8M | **+0.002** | +0.001 | (already across) |
| **conditioning, at fixed 6 × 2M + QRF** | `qrf-b6x2M` → `env-qrf-b6x2M` | **+0.037** | **+0.0966** | **yes** |

Three things follow, and each is a correction to a published claim:

**(a) The estimator lever saturates BELOW the threshold.** Per-doubling return on the QRF=1 ladder fell from
+0.00695 (50k→2M) to **+0.00150** (2M→8M), a **4.6× collapse** in per-doubling return. Fitting
`r(k) = A − B·e^{−ck}` on the three points (`k` = doublings from 50k) gives **A = 0.8696**, half-life 1.82
doublings — **0.0194 short of 0.889 at *infinite* subsample**. Model-free cross-check: at the last observed
marginal rate, reaching 0.889 needs **14.7 further doublings ⇒ 2.08×10¹¹ rows/tree** against a 1.977×10⁸-row
table, i.e. **1052× the entire training set**. Exhausting the table itself (8M→197.7M, 4.63 doublings) gets
to **0.8692** on the fitted curve; a straight-line read at the terminal rate would say 0.874, but that
*exceeds the fitted asymptote* and is therefore an upper bound, not an estimate — either way it is short.
Sensitivity: the asymptote clears 0.889 only if `r(8M) ≥ 0.872`, five rounding units above the 0.867
measured. So capacity at `ncond` 8 *provably* cannot reach the gate; this is not merely unmeasured.
(Arithmetic independently re-derived, not taken from a report.)

**(b) The subsample lever is exhausted past ~2M rows/tree at BOTH widths** — +0.003 at ncond 8, +0.002 at
ncond 14. The *level* at which it plateaus is set by the conditioning (0.867 vs 0.903), not by capacity.
That is the general statement, and it is why 8M is never worth buying.

**(c) QRF's payoff shrinks as capacity grows, and the mechanism is measured.** +0.013 `emu_r` at 40 trees /
50k but only +0.002 at 6 trees / 2M, and it *costs* dispersion at 2M (−0.013). Direct measurement on the
artifacts (`rcop_leaf_geometry_probe.jl`, job 1648259) explains it: the pooled-default max-leaf weight share
is median 11.2 % at t8's 60 trees = **6.7× QRF's 1/T**, but median 48.9 % at t9's 6 trees = only **2.9×
1/T**. What QRF corrects is largely absent at 6 trees. **`qrf-b6x2M` was therefore NOT chosen for its skill
— it is within noise of `b6x2M` — but for consistency with the rung that was scored.**

**Do not restate "tree count is inert" as evidence of subsample saturation.** The 12/24/40 × 500k trio
(0.844/0.843/0.842, ±0.002 over a 3.3× tree count) varies *ntrees at fixed subsample*; it is the
tree-count-is-inert experiment and says nothing about the subsample curve, which at 500k was still buying
+0.018 per two doublings. Conflating them was an error in the previous handoff.

**In fairness to ADR 0037: its extrapolation was defensible on the data it had.** The QRF=0 ladder's two
segments are +0.00903 and +0.00900 per doubling — dead straight, and a 3-point saturating fit degenerates on
it. The 8M rung is *new information*, not an avoidable mistake.

## 4. What ships, and why `b6x2M` over `b6x8M`

**`env-qrf-b6x2M` → `recruit_copula_global_historic_t9.rcop`** (6 trees × 2M subsample, `max_depth` 22,
`min_leaf` 20, `QRF=1`, `ncond` 14), trained by `train_slow_copula.jl` on the EXISTING
`slow_copula_historic_t8env` table — never a rebuild, per ADR 0036 §5b.

`b6x8M` is rejected: +0.002 `emu_r` and +0.001 `sd_ratio` for **4× the bytes** and pooled KS *worse on all
four axes* (.0039/.0045/.0022/.0017 vs .0032/.0024/.0019/.0013). Load cost compounds it — `load_copula`
tokenizes the whole file, so t9's 59.2 M tokens already cost ~2.5–3 GB transient RSS, and 8M would be ~10 GB.

Measured properties of the shipped artifact:
- **507 985 666 B** (484.5 MiB). The size model `bytes ≈ C·ntrees·subsample·naxes` holds with **C = 10.58**
  (t8 gives 10.66); the previously quoted 10.7 over-predicts by 1.1 %.
- **Load 6.77 s = 71.6 MiB/s, MEASURED** in a fresh process. The "~12 s at 42 MB/s" in an earlier handoff
  was an unmeasured estimate — do not propagate it.
- **Reproducible**: an independent re-run at the same config and seeds gave a **byte-identical** `.rcop`
  (md5 `4c72ff33…`, job 1647662).
- **Accepted end to end** (`rcop_acceptance_probe.jl`, job 1647615/1647666): `nfeat` 14 on all four axis
  forests, sidecar agreement, all three golden pairs reproduced, the runtime `live_flux_cond_env(env)` row
  equal to the artifact's own fallback row, and 13-/15-/4-column rows all rejected.
- **t9 is the FIRST generation whose SHIPPED artifact is the estimator that was SCORED**
  (`[VERIFIED 2026-07-31]`). `run_global_slow_copula.sh` carries two tree knobs — `NTREES` (60, → the shipped
  `.rcop` via `train_slow_copula.jl`) and `EVAL_NTREES` (40, → the scored K-fold OOS via
  `eval_slow_copula.jl`) — so **every published t8 gate number describes a 40-tree estimator while the object
  line M pins is a 60-tree one.** Read off the artifacts themselves: t8 has `ntrees = 60` and 3 000 000 stored
  leaf values on axis 1 (= 60 × 50 000); t9 has `ntrees = 6` and 12 000 000 (= 6 × 2 000 000), matching its
  rung exactly. Tree count is nearly inert for skill (±0.002 over 3.3×), so the t8 mismatch barely moved the
  headline numbers — but it is **not** inert for the leaf-weight skew that the QRF story rests on (6.7× `1/T`
  at 60 trees vs 2.9× at 6), so any t8-era weighting figure must be attributed to the 60-tree *artifact*, not
  to the 40-tree scored estimator. This also resolves the apparent "40 vs 60" contradiction in
  `diagnose_copula_capacity.sh`'s size comment: both numbers are right, about different objects.
- **Leaf geometry at the production config, previously unmeasured** (job 1648259): 33 449–46 036 leaves/tree,
  **52.3–67.0 % of stored values still in a depth-capped leaf**, and only 84–86 % of large leaves at
  `max_depth` (against 99.9–100 % at 50k/d14). So depth is **not** exhausted at d22/2M and remains free in
  bytes — a named, cheap, open lever (§8).

**Criterion 3's reading is PINNED here**, as the previous handoff required: criterion 3 means the **numeric
bound**, pooled KS not worse than the same-scenario baseline by more than 0.02 — *not* a strict
"no increase on any axis". Rationale: 0.02 is what ADR 0030 wrote, and a strict no-increase reading would
fail rungs on a +0.0004 SLA movement that is inside run-to-run noise. It is moot for the shipped config,
which improves all four axes, but it must not be left ambiguous again. **Score the statistic the criterion
names**: pooled KS, never `nqrmse` — they disagree by ~55× in magnitude (`agb` 0.6432 vs 0.0116) *and in
direction* (`b12x500k` D95max: `nqrmse` 2.0× worse, KS 2.1× better), and scoring the wrong one put a false
verdict into ADR 0037. `score_slow_copula_ks.py` now reads the baseline from
`figures/emulator_validation/<scenario>_t8/metrics_traits.txt`, keyed on the manifest's `scenario`, so the
scenario baseline can no longer be mismatched by hand.

The decisive argument for pinning it in *words*: **`pooled_t8`'s own Wooddens `pooled_nqrmse` is 0.0208 —
already above 0.02.** Applying criterion 3's numeric bound to `nqrmse`, as ADR 0037 did, makes the pooled
*baseline itself* fail the criterion. No statistic-agnostic phrasing can survive that.

**But the choice of statistic hides a real, coherent SLA bias, and it goes on the record here rather than
being rediscovered.** At the shipped config, SLA's pooled KS *improves* (0.0051 → 0.0032) while its pooled
`nqrmse` gets **1.8× worse** (0.0040 → 0.0071). That is not noise: all five pooled SLA quantiles are biased
low by a coherent −0.4…−0.5 % (`pred_q=[0.01143, 0.01581, 0.02232, 0.03319, 0.04938]` vs
`obs_q=[0.01145, 0.01585, 0.02243, 0.03334, 0.04958]`), and a max-CDF-distance statistic barely penalizes a
uniform shift. Wooddens shows the same asymmetry in miniature (`nqrmse` 0.0133 → 0.0127 while its KS halves).
**Publish the `nqrmse` column beside pooled KS** so the shift stays visible; criterion 3 is scored on KS, but
KS is not a sufficient description of the marginal.

## 5. Superseding ADR 0037

ADR 0037 is immutable; these are the corrections this ADR carries.

| ADR 0037 | the claim | superseded by |
|---|---|---|
| `:9`, `:4` (title + thesis) | "The per-cell trait GAP is an ESTIMATOR defect, not missing conditioning — S2's premise is REFUTED as the primary cause" | The estimator lever is larger on `emu_r` (+0.050 vs +0.037) but **saturates at 0.867**, below the gate, at any artifact size. Conditioning is the larger lever on **criterion 2** (+0.0966 vs +0.0800) — the axis that was actually failing — and is what carries both criteria across. **S2's premise is vindicated as necessary.** The correct framing is neither label: the estimator had to be fixed *before* the conditioning could pay, because at 50k subsample there is ~0.93 rows/cell and six extra columns have no resolution in which to express themselves. |
| `:41-42` | "Wooddens reaches 0.916 from the EXISTING eight columns … The conditioning was never the binding constraint." | That 0.916 is a **per-cell LightGBM upper bound**, not a DRF result. No DRF rung at `ncond` 8 exceeded **0.867**, and the fitted asymptote is 0.870. The estimator-share/covariate-share decomposition did **not** transfer to the DRF and must not be used to predict what the DRF will gain. |
| `:170-171` | expanding the conditioning is "the smallest of the three levers (~4× smaller than the estimator terms)" | Refuted by a factor of ~4 **in the opposite direction** on criterion 2. |
| `:63-67`, `:71-73` | `b6x2M` "degraded the pooled marginal ~2×" | Measured on the wrong statistic. On **pooled KS** — what criterion 3 names — `b6x2M` **improves all four axes**: SLA 0.0051→0.0038, Wooddens 0.0052→0.0040, D95max 0.0069→0.0030, minwscal 0.0115→0.0051 (jobs 1646363/1646487). |
| `:91-98` | a large leaf is one that "stopped splitting early" / the max leaf takes "17-21 % ⇒ 10-12×" | Large leaves are **depth-capped**, not gain-exhausted: 99.9–100 % of leaves holding ≥ 2·`min_leaf` values sit at exactly `depth == max_depth`. The weight share is **median 11.1 % ⇒ 6.7× typical** (11.3× at q90); 17–21 % was the upper decile quoted as typical. |

**What ADR 0037 got RIGHT, and this ADR keeps:** (a) `DRF.predict_quantile` genuinely was not implementing
the QRF estimator it documented, and the leaf-size skew is real and directional — now re-measured at 6.7×
typical; (b) capacity really is a first-order lever, worth +0.050 `emu_r`; (c) resolution beats averaging —
tree count is inert (±0.002 over 3.3×) while subsample is not; (d) pooled-marginal metrics are structurally
blind to an under-resolved conditional; (e) the six-column tail was the right size (64–72 % of the full-28
gain without pushing `Xc` to ~57 GB); (f) shipping the conditioning as a policy **factory** rather than a
struct change — which is exactly why the 14-column artifact needed no format or interface change; (g) the
count DRF is unaffected.

Two further corrections carried from `lines/S/STATE.md`: **`b12x500k` closed 20.0 % of the GAP, not 28 %**
(formula pinned: `(emu_r − 0.814)/0.150`), and **`ncond` 8→14 gives `mtry` 4-of-14**.

## 6. Why this is NOT promoted to line M's production copula

This is the finding that matters most, and it was not in scope when the milestone was written.

**The six env columns are a per-cell static ADDRESS, not a climate response.** Measured directly on
`tables/cell_year_feats.parquet` (Year 2000–2019, 67 420 cells): the median within-cell standard deviation
is **exactly 0, for 100 % of cells, on all six columns** (`prec_mean`, `eco_diag_p_pet_ratio`,
`eco_diag_pet_mean`, `eco_diag_vpd_mean`, `pr_cv_monthly`, `humid_mean`), against between-cell sds of
731.5 / 0.625 / 62.5 / 0.685 / 0.376 / 0.00517. They are per-cell constants broadcast across years. Three
consequences:

1. **They cannot encode a warming response**, in training or at inference. In the pooled table a cell's
   historic rows and its ssp370 rows carry **bit-identical** env values, so within-cell cross-scenario
   variance is zero. Six of fourteen conditioning columns are a pure cell-level fixed effect. `co2` is
   already a literal constant 369.0 (`CO2_CONST`, the ADR-0004 constant-CO₂ regime), so it is a **dead**
   conditioning column that can never be split on — effective width is `ncond − 1`. Only the four live flux
   drivers separate the two scenarios. **No ssp370 source for these six variables exists anywhere.**
2. **K-fold-BY-CELL CV cannot distinguish a transferable response from spatial interpolation.** A 1-NN
   lookup of a held-out cell's Wooddens median from its nearest training-fold neighbour in standardized
   column space reaches r = **0.800** on the six env columns, with a median great-circle distance to that
   neighbour of **1.00°** (q25 = 0.50°, i.e. the *adjacent* cell) — against r = 0.445 and 14.51° for the
   three existing boundary constants. The env columns resolve to a geographic address, and by-cell folds
   leave the neighbours in the training set.
3. Therefore **the +0.037 is real but its generalization is unestablished.** It is a valid offline gain on
   the historic-static basis and a defensible static covariate in the same class as `soil_depth`; it is
   *not* evidence of a transferable environmental response, and it should not be assumed to survive into an
   ssp370 coupled run.

**Independently, two of the four criteria are not computable for the pooled artifact at all** — see §7.

**Decision:** `recruit_copula_global_historic_t9.rcop` ships as the **historic-static** artifact — the
ladder's endpoint and the S2 evidence — and line M does **not** re-pin onto it. Note the basis explicitly:
the ladder ran on `slow_copula_historic_t8` (static boundary, uncapped), whereas M pins the **transient**
`pooled_w20` basis (`BOUNDARY_WINDOW=20`, `STEM_CAP=400`; ADR 0027). The naming already distinguishes them,
as it did at t8; do not call the historic artifact "the production copula".

## 7. The floor is historic-only, and one "seed2" is not a seed2

**No pooled and no ssp370 seed2 table exists.** Only `slow_copula_historic_seed2{,_t7,_t8}`. The floor is
what defines the attenuation-corrected ceiling, so **criterion 1's `%GAP` and criterion 4's `r_center` are
not computable for the pooled artifact.** Criteria 2 and 3 need seed1 alone and are covered by
`score_slow_copula_dispersion.py` and `score_slow_copula_ks.py`. Their absence is **not** a pass.

Useful corollary: **`median_percell_r` in `metrics_traits.txt` IS `emu_r`** — the between-cell Pearson r of
per-cell medians, despite a name that reads like a within-cell statistic. Reproduced to 4 dp on an identical
cell count (pooled SLA 0.8994 / Wooddens 0.8261 on 57 719 cells); the basis offset to the gate's own number
is ~0.002 (historic Wooddens 0.8121 there vs 0.814 in the gate). So every scenario's `emu_r` baseline is
already published and needs no seed2.

**And the ssp370 `random_seed2` ground truth is a BIT-IDENTICAL COPY of seed1** (`[VERIFIED 2026-07-31]`).
`ind_2020_2100.csv` is 193 097 583 638 B in both, with equal md5 on 1 MB blocks at MB 0 / 30000 / 120000,
because the seed2 config sets `"random_seed": 2` but its `restart_filename` points at the **historic seed1**
`restart_2019.lpj`; under `-DFROM_RESTART` the per-cell RAND48 state is restored from that file, so the seed
setting is inert. The historic pair is genuinely independent by contrast — each config reads its own
*relative* `restart/restart_1999.lpj`, and the files differ in size and at every block sampled.

Building a floor from it would raise **no error** and would report `floor_r ≡ 1.000`, hence a ceiling of
~0.998 and fabricated headroom on every axis. Nothing existing catches it: the `seed1-basis ≥ 0.99` check
compares a copula table to the parquet of the *same* seed and reads 1.000. `noise_floor_vs_emulator.py` now
**aborts** on bit-identical per-cell medians and warns when > 50 % are exactly equal. Self-tested both ways
(job 1648005): the negative control (one table as both realizations) exits 1 with the FATAL; the positive
control (the real historic pair) exits 0 and reproduces the published baseline exactly (Wooddens `emu_r`
0.814, floor 0.937, ceiling 0.964, GAP 0.150, `r_center` 0.844, `sd_ratio` 0.6775), which also proves the
gate's arithmetic is unchanged.

## 8. Silent-failure paths closed in code

All three were found while shipping the artifact, not in review; each returned plausible in-range values.

1. **`qrf` lived only in the sidecar.** It selects a different conditional distribution from the same
   forests, and line M's contract pins a `.rcop` *path* — so a consumer that missed `qrf_weighting` got
   `RecruitCopula`'s `false` default and sampled the estimator that was *not* scored. Flipping it changes
   **all three** of t9's golden draws, so it is load-bearing. **`.rcop` format v2 embeds it.** v1 remains
   readable and means `qrf = false` (what v1-era artifacts were trained with), `qrf` is the sixth tuple
   element so all five 5-way `load_copula` call sites are untouched, `save_copula` defaults to `false`, and
   a forged v99 header is refused. **This is a VERSION BUMP of the frozen S→M `.rcop` contract, not a
   mutation:** no pinned artifact changes and nothing M holds needs regenerating.
2. **Nothing validated the conditioning width at construction.** `DRF._check_nfeat` fires only inside
   `sample_copula!`, reached only when a patch actually recruits — so a cell that thins every year, or an
   all-grass patch, never draws, and a mis-wired coupled run completes "successfully" while conserving
   carbon. The `FluxDrivenSlowEmulator` constructor is the only place holding both the boundary and the
   copula, so it now probes the policy once and errors with the arithmetic spelled out.
3. **The duplicate-seed floor**, §7.

Coverage added: a 14-column artifact with `qrf=true` is now constructed **through
`FluxDrivenSlowEmulator`** — a composition no test had ever built — alongside both crossed
width mismatches and a wrong-length boundary.

## 9. Consequences and what is deliberately still open

- **S2's gate is MET on the historic-static basis**, and the milestone's original premise is vindicated. It
  is **not** closed as a milestone: §6 leaves the generalization question open, which is what production
  turns on.
- **An integration point is OPEN with line M** and M must be told before any re-pin:
  `scripts/extract_cell_slow_init.py:142-146` checks `cond_cols[-4:] == BOUNDARY_COLS`, which a 14-column
  artifact fails by construction (its last four are the env tail) ⇒ guaranteed `sys.exit`. The correct check
  is **positional** (`cond_cols[4:8]`). That file is M-owned; S requests, M lands.
- **`[TODO]` the spatial-vs-response question, and it is the gate on production.** Score `env-qrf-b6x2M`
  under **spatially blocked** CV (contiguous lat/lon blocks, not `mod(hash(cell), k)`) and against a
  latitude/longitude-only conditioning control. If the gain survives blocking it is a response; if it decays
  to the 1-NN lookup level it is an address, and the honest framing of S2 changes again.
- **`[TODO]` a per-cell env sidecar.** There is no runtime plumbing that supplies the six values per cell —
  a caller hand-builds them from `cell_year_feats.parquet`, which is unreachable from CI and
  basis-sensitive. S must emit `cell_env.parquet` on the same no-year-filter basis; M folds it into
  `M_cells.csv`. Until then the 14-column artifact is not coupled-runnable outside a bespoke script.
- **`[TODO]` depth at the production config is not exhausted** — 52.3–67.0 % of stored values are still
  depth-capped at d22/2M, and depth is free in bytes. One `6 × 2M, d32` rung settles whether the ~0.870
  asymptote moves.
- **`[TODO]` a pooled seed2**, or an explicit decision to score the pooled artifact on criteria 2 and 3 only.
  An ssp370 seed2 additionally requires a genuine independent restart lineage (§7), not a re-run of the
  existing config.
- **`[TODO]` the composed coupled path** — emulator + 14-column copula + `qrf=true` + establishment +
  carbon closure over a multi-year run — is still unexercised. Construction is now gated; the run is not.
- **`[ASSUMPTION]` the env tail is scenario-invariant by construction and that is accepted**, in the same
  class as `soil_depth`. A transient env tail would need both an ssp370 source (none exists) and a runtime
  `env_series`, since `live_flux_cond_env` closes over `env` once at construction.
- **Not claimed — `agb`/`Height` are UNMEASURED at the shipped config.** `diagnose_copula_capacity.sh`'s
  `TRAIT_ONLY=1` trims `nstruct`/`struct_axes` out of the shadow manifest to cut the eval ~33 %, and it was
  set for **11 of the 12 rungs, including both env rungs** — only `capacity/cap50k-baseline/` carries
  `pred_agb.f64`/`pred_Height.f64`. So the two ADR-0036 diagnostic axes, which have the *tightest* baseline
  margins (agb pooled KS 0.0116 against the 0.02 bound; agb/Height `r_center` 0.987/0.986 with only
  0.011/0.013 of headroom), were not re-checked here. ADR 0036 §192 makes criterion 4's "no *other* axis"
  legitimately exclude them, so the verdict stands — but **"S2 met" must not be read as "biomass and size
  unchanged"**. Re-run the shipped rung with `TRAIT_ONLY=0` to close it.
  *Corrected in passing:* the gate printed "Rebuild the seed2 table with the same `STRUCT_AXES`" on this
  disagreement, which is misdirected — the seed2 tables **do** carry agb+Height; it is the seed1 shadow
  manifest that was trimmed. Following that advice costs a pointless multi-hour rebuild and fixes nothing.
  The message now names the narrower side and points at `TRAIT_ONLY`.
- **ADR 0030's own hard gate was inherited, not re-measured.** Every ladder log ends `SKIP_PARQUET set —
  copula basis only`, so decision 2 (`seed1-basis ≥ 0.99`, and "no gap may be quoted from" a basis that fails
  it) was last *printed* in job 1641372 (1.000 on all four axes, `tree7`). Inheriting it is legitimate here
  because the `Y_*`/`cells.i64` files are the *same inodes* (§2) — but that is an argument, not a measurement,
  and it should be re-printed on the next generation that rebuilds those files.
- Operational: the `_t8env` tables are **symlink farms** whose `Y_*`/`cells.i64`/`scenario.i64` point into
  their `_t8` source. Deleting or DVC-pruning a `_t8` table silently breaks every `t8env` table and the
  shadow dirs that link to them.
