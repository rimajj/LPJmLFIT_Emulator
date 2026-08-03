---
status: "accepted"
date: 2026-08-03
deciders: "engineering agent on line S (full autonomy per STEERING_PROMPT.md). Four decisions: (1) ADR 0038's proposed decision rule for the address-vs-response question — *\"decays toward the 1-NN level (r ~ 0.80) => it is an address\"* — is REJECTED as a reference-basis error: 0.80 is a pure address's skill under `mod(hash(cell), k)` folds, and the correct fold-mode-matched null for spatially blocked CV is **0.14-0.21**, so the rule was wrong by ~0.63 in r and would have declared a strong response an address; (2) the corrected null, the env tuple's blocked retention, and the surrogate conditioning delta are PRE-REGISTERED here, computed at zero compute and frozen BEFORE any blocked forest result is read; (3) a SECOND gate is added — the warming Delta-response — because `emu_r` is a level statistic and the transient signal is only 20-31 % of the spatial signal, so the existing gate is ~3-5x more sensitive to spatial interpolation than to the thing a coupled warming run depends on; measured, the shipped env-conditioned artifact DAMPS the mean Wooddens warming shift by 37 % (CI excludes zero) while improving the shift's pattern correlation; (4) the blocked-CV machinery ships opt-in and default byte-identical, with `BUFFER_DEG=0` explicitly demoted to a sensitivity rung because a blocked split alone leaves 24 % of test cells within 1 deg of training data."
consulted: "ADR 0038 (the accepted ADR whose decision rule this one rejects, and whose caveat it acts on), ADR 0030 §4 (the four S2 criteria and the attenuation-corrected ceiling), ADR 0033 (the twice-recorded warning that this line credits one change with another's effect — why `MTRY` is now a knob), ADR 0036 §5b (polars streaming key-set nondeterminism — why every control table is an APPEND to one validated row universe, never a rebuild), ADR 0026/0027 (the transient boundary basis, and why a static env tail is the thing that cannot carry a response), ADR 0004 (constant CO2 — `co2` is a dead conditioning column), ADR 0014 (empty runtime `[deps]` — why the fold table is plain text), CLAUDE.md §6 guardrails 4 and 7 (opt-in/byte-identical; state the reference basis before chasing a residual)"
informed: "lines/S/STATE.md (NEXT), lines/M/STATE.md (the re-pin block stands and is now stronger: the artifact damps the transient response), the slow-drf-pipeline skill, changelog.d/S-blocked-cv-machinery.md"
---

# The address null was measured on the wrong basis — and the gate metric is nearly blind to warming

> **Status.** `accepted`. This ADR **rejects a decision rule** proposed in accepted ADR 0038 and replaces it
> with a pre-registered one. It does not change any shipped artifact, and it does not yet answer
> address-vs-response with forests — the forest matrix is in flight (§5). Every code change is opt-in and
> **verified** byte-identical: with all new knobs unset, all six `pred_<axis>.f64` on the 50-cell smoke table
> are `cmp`-identical to the pre-change predictions, and the `hash` branch reproduces the published pooled
> fold sizes `[11728, 11757, 11694, 11720, 11867]` exactly.

## 1. What ADR 0038 asked for, and the error in how it asked

ADR 0038 shipped a 14-column recruit-trait copula, established that its +0.037 Wooddens `emu_r` comes from
six per-cell env columns whose median **within-cell sd is exactly 0 for 100 % of cells**, and correctly
refused to promote it, writing the follow-up as:

> *"Re-score `env-qrf-b6x2M` with contiguous lat/lon block folds … Survives blocking ⇒ a real environmental
> response, promote it. Decays toward the 1-NN level (r≈0.80) ⇒ it is an address."*

The instruction is right. **The threshold in it is wrong, and wrong in the direction that would have
produced a confident false verdict.** `r ≈ 0.80` is what a nearest-neighbour lookup achieves *under
`mod(hash(cell), k)` folds* — a design in which, measured here, **99.5 % of test cells have a training cell
within 0.75°** and the q99 is 0.61°. Blocking is precisely the manipulation that destroys that adjacency, so
it necessarily lowers the address's own skill too. Comparing a *blocked* emulator against a *hash-fold*
address baseline compares two different bases, which is guardrail 7's failure mode, and ADR 0033 records
this line making the same class of error twice before.

The size of the error is larger than the effect being measured: the fold-mode-matched null is **0.14–0.21**,
not 0.80 (§3). A blocked p14env landing at, say, 0.78 would have been reported as *"decayed to the address
level ⇒ it is an address"* when 0.78 against a 0.17 null is overwhelming evidence for the opposite.

## 2. What is pre-registered here, and why the ordering matters

Everything in §3 and §4 is computed from artifacts that **already existed**, with no forest fit, and is
frozen in this ADR before any blocked forest log is opened. That ordering is the only mechanism that
prevents the decision rule being written once the outcome is known — which is a live risk on this line,
because the framing of this result has already changed twice (ADR 0037 → 0038).

Scripts: `scripts/diagnose_slow_address_prereg.py` (both read-outs),
`scripts/blocked_cv_folds_probe.jl` (the fold designs and their verification),
`scripts/build_slow_spatial_controls.py` (the position artifacts).

## 3. The corrected null — a 1-NN surrogate under the SAME fold designs the forests use

Per-cell median target, 1-NN transferred from each fold's training set (buffered cells excluded), 57 719
cells at ≥20 stems, on the pooled `w20_t8` row universe. Four conditioning spaces: `geo` = unit-sphere
position (**a pure address, and the null**), `env6` = the six env columns IQR-standardised (the static
climate *envelope*), `dyn7` = per-cell means of the seven live base columns, `both` = `dyn7 + env6`.

The fold designs are **read from maps written by the Julia code the forests run** (`cell fold bufmask`),
not recomputed in Python — `mod(hash(tile), k)` is Julia's `hash(::Int64)` and a Python reimplementation
would silently score a different experiment.

**Wooddens** (the criterion-1 axis):

| fold design | mean train cells/fold | `geo` = **NULL** | `env6` | `dyn7` | `both` | `DELTA` = both−dyn7 |
|---|---|---|---|---|---|---|
| `hash` (the published design) | 46 175 | **0.8369** | 0.8114 | 0.7992 | 0.8773 | **+0.0781** |
| `block(15°, 5°)` salt 0 | 28 265 | **0.1400** | 0.5947 | 0.6069 | 0.6833 | **+0.0764** |
| `block(15°, 5°)` salt 1 | 27 722 | **0.2102** | 0.5934 | 0.6280 | 0.6856 | **+0.0576** |

All four axes, `geo` null → blocked (salt 0 / salt 1): SLA 0.914 → 0.265/0.403 · Wooddens 0.837 →
0.140/0.210 · D95max 0.747 → 0.339/0.389 · minwscal 0.950 → 0.723/0.706. Blocked `DELTA`: SLA
+0.006/+0.021 · Wooddens +0.076/+0.058 · D95max +0.061/+0.050 · minwscal +0.005/+0.011.

Three facts follow, and they are the pre-registration:

1. **The address null under blocking is 0.14–0.21 for Wooddens, not 0.80.** ADR 0038's rule is rejected.
2. **The env tuple's information largely SURVIVES blocking; a pure address does not.** `env6` retains 73 %
   of its hash-fold skill (0.811 → 0.594), `geo` retains 21 % (0.837 → 0.140). Whatever the six columns are,
   they are not *merely* a lookup key: they transfer across a severed neighbourhood.
3. **The conditioning DELTA is close to invariant under blocking** — +0.078 (hash) → +0.076 / +0.058
   (blocked), i.e. ~86 % retained on the mean of two colourings. So the surrogate screen **predicts, in
   advance, that the forest runs will find the gain survives**. If they do not, something other than
   information content is doing the work in the forest and that is the finding.

Honest limits, stated because they bound the claim. (a) 1-NN is a weak learner, so this is a *conservative
screen* of information content, not a forecast of the forest's numbers. (b) `dyn7` is itself
address-contaminated — three of its seven columns (`eco_diag_gdd_5`, `tas_cold_month`, `soil_depth`) are
per-cell constants — so the contrast is "3-column envelope vs 9-column envelope", not "no address vs
address". (c) The `geo` null's salt-to-salt spread is large (0.140 vs 0.210), which is exactly why
`BLOCK_SALT` exists and why the matrix runs the blocked pair at two colourings.

## 4. The second gate: `emu_r` is nearly blind to what production depends on

The pooled table carries `scenario.i64`, so the historic→ssp370 per-cell shift is computable from the
existing predictions. Per-cell medians taken separately in each scenario block, 52 450 cells with ≥20 stems
in **both**, tile-cluster bootstrap (15° tiles — the naive per-cell bootstrap understates the spatial
sampling sd of these statistics several-fold), `ceil = sqrt(reliability)` from a rank-parity split-half of
the observed shift:

| axis | `sd(Δobs)/sd(level)` | `Rr` = r(Δpred, Δobs) | ceiling | `Ra` amplitude | `Rb` = mean Δpred − mean Δobs | mean Δobs |
|---|---|---|---|---|---|---|
| SLA | 0.231 | +0.4389 [.4235, .4521] | 0.958 | 1.017 | +1.317e−4 [+1.08e−4, +1.55e−4] | −5.31e−4 |
| **Wooddens** | **0.306** | **+0.4146 [.4022, .4271]** | **0.920** | **0.869** | **−892 [−1022, −756]** | **+2433** |
| D95max | 0.289 | +0.2424 [.2258, .2579] | 0.871 | 0.954 | +0.565 [−0.113, +1.262] | +5.08 |
| minwscal | 0.198 | +0.6232 [.6006, .6457] | 0.947 | 1.010 | +1.38e−3 [+1.13e−3, +1.62e−3] | +3.48e−3 |

Three readings:

1. **The gate metric is the wrong instrument for production.** `sd(Δobs)/sd(level)` is **0.20–0.31**: the
   warming signal is a fifth to a third of the spatial signal, so a *level* correlation like `emu_r` is
   roughly 3–5× more sensitive to spatial interpolation than to the transient response. `emu_r` passing says
   little about a coupled warming run. Blocked CV tests whether the published number is *honest*; it does
   not test *production risk*. They are now two separate gates.
2. **The shipped artifact DAMPS the Wooddens warming shift by 37 %** — `Rb` = −892 against an observed mean
   shift of +2433, CI [−1022, −756] excluding zero. `SLA` and `minwscal` are *amplified* relative to their
   (small, opposite-signed) observed means. This is the concrete production risk the spatial question was
   standing in for, and it is measurable today.
3. **The transient PATTERN is poorly captured by everything.** `Rr` reaches only 0.24–0.62 against ceilings
   of 0.87–0.96 — Wooddens recovers 45 % of its ceiling. This is a large, previously unmeasured gap and it
   is not a conditioning-width artifact.

**What is NOT concluded.** The comparison arm available today (`slow_copula_pooled_w20_t8`'s in-place
predictions: `Rb` = **+263** [+92, +432], i.e. mildly *amplified*, and `Rr` lower on every axis) is at
**40 trees / 50 k / d14 / QRF=0 / mtry 3** — a **four-lever** gap to the shipped `6 × 2M / d22 / QRF=1 /
mtry 4 / ncond 14`. So *"the env tail causes the damping"* is **not** established here; that is precisely
what the matched `p8` rung in §5 is for. Note also that `lines/S/STATE.md` recorded this baseline as
"60-tree": the 60 is `train_slow_copula.jl`'s artifact setting, printed later in the same log — the
evaluation ran at 40.

## 5. The pre-registered decision rule, and the run matrix

All rungs: pooled row universe, `NTREES=6 SUBSAMPLE=2000000 MAX_DEPTH=22 MIN_LEAF=20 QRF=1 KFOLDS=5
TRAIT_ONLY=1`, ~1.4 h × 64 CPU. Blocked rungs are `BLOCK_DEG=15 BUFFER_DEG=5`. Every 14-column table is an
**append** to the same validated `Xc` (columns 0–7 verified bitwise-identical over all 42 227 077 rows), so
the four arms differ in the conditioning tail and nothing else.

| tag | table | ncond | fold | mtry | role |
|---|---|---|---|---|---|
| `p8-hash-mtry4` | `..._t8` | 8 | hash | **4** | the matched narrow baseline — **it did not exist** |
| *(have)* `pooled-env-qrf-b6x2M` | `..._t8env` | 14 | hash | 4 | `emu_r` 0.9095 / `sd_ratio` 0.8493 |
| `p8-blk15-buf5-mtry4` | `..._t8` | 8 | block s0 | **4** | blocked narrow baseline |
| `p14env-blk15-buf5` | `..._t8env` | 14 | block s0 | 4 | blocked treatment |
| `p14geo-blk15-buf5` | `..._t8geo` | 14 | block s0 | 4 | address control, blocked |
| `p14geo-hash` | `..._t8geo` | 14 | hash | 4 | does a pure address reproduce the *published* gain? |
| `p14perm-hash` | `..._t8perm` | 14 | hash | 4 | width/capacity null: same `p`, same `mtry`, same cell-level 6-way joint, zero information |

**Decided in advance:**

- **RESPONSE** if `Δ_blocked ≥ 0.5 · Δ_hash` **and** the blocked `p14geo` arm sits far below the blocked
  `p14env` arm. Surrogate expectation: `Δ` retains ~86 %, `geo` null 0.14–0.21.
- **ADDRESS** if `Δ_blocked` collapses toward 0 **or** blocked `p14geo` ≈ blocked `p14env`.
- **NOT RESOLVABLE** if the two salts disagree by more than `0.5 · Δ_blocked` — one tile→fold colouring is
  one draw, and the `geo` null's own salt spread (0.07) is already comparable to `Δ`.
- **Independently of all three**, promotion to line M additionally requires the §4 response gate: a matched
  `p8`-vs-`p14env` comparison in which the env tail does not significantly damp `Rb`. **On today's evidence
  the artifact fails that gate**, so ADR 0038's refusal to re-pin M stands and is now better founded.

## 6. Machinery, and the design facts that were measured rather than assumed

`FOLD_MODE` / `BLOCK_DEG` / `BUFFER_DEG` / `BLOCK_SALT` / `CELL_LATLON` / `MTRY` on
`eval_slow_copula.jl`; `ENV_PARQUET` / `TAIL_TAG` on `build_slow_copula_env_augment.py`; the knobs plus a
login-node pre-flight, a `CAPTAG`-collision refusal and a pooled-source gate branch on
`diagnose_copula_capacity.sh`.

1. **`BUFFER_DEG=0` is a sensitivity rung, not the test.** A blocked split leaves the block **perimeter**
   adjacent to training data: at `B=15`, **10.9 %** of test cells still have a training cell at 0.5° and
   **24.2 %** within 1.0°. All `D=0` rungs are therefore excluded from the verdict.
2. **The buffer is verified independently.** `blocked_cv_folds_probe.jl` re-derives the realized
   nearest-training-cell distance by great-circle brute force — a *different metric* from the eval's grid
   dilation — giving min 2.23° / 5.27° / 10.16° at `D` = 2 / 5 / 10. The dilation scales its longitude radius
   by `1/cos(lat)` so `D` is a physical width, and its two passes are sequential, making the removed set a
   conservative **superset** of the great-circle ball: it can never manufacture a false "survives blocking".
3. **The block size trades fold balance against training retention, and both are held constant across
   arms**, so neither biases a delta: `B=10` balance 1.41 / 35.5 % retained at `D=5`; **`B=15` 1.91 /
   49.0 %** (chosen); `B=20` 2.60 / 58.0 %. Hash folds balance at ~1.02.
4. **`mtry` was a hidden fourth lever.** `DRF.fit_forest` uses `mtry_eff = round(Int, sqrt(p))` ⇒ **3** at
   ncond 8, **4** at ncond 14, so every published ncond-8-vs-14 comparison varied `mtry` too. `MTRY=4` on the
   narrow arm makes the lever a matched pair. It also gives the damping in §4 a candidate mechanism worth
   testing: at `(p=8, mtry=4)` a split considers ≥1 of the four time-varying flux drivers with probability
   0.986, but at `(p=14, mtry=4)` only 0.790 — the static tail dilutes the only channel through which time
   can enter the model, since `co2` is dead.
5. **The `p14geo` basis was rank-degenerate on first build and is fixed.** `geo_abs_lat` and `geo_cos_lat`
   have Spearman **−1.000000**: `cos` is strictly monotone in `|lat|`, so an axis-aligned tree sees *one*
   feature and the control was silently five-dimensional while declaring `ncond=14`. That handicaps the
   control in the direction of the hypothesis under test. The sixth column is now
   `geo_x = cos(lat)·cos(lon)`, a genuine lat×lon interaction, and the builder **gates** the basis (no pair
   above |ρ| 0.99; measured max 0.954). The two affected rungs were cancelled and resubmitted.
6. **The `p14perm` tail is a bijection of the true tail over the 6-way JOINT** (lexicographic sort of both
   `(58766, 6)` arrays), and its east-neighbour correlation collapses from the true tail's **0.9595–0.9986**
   to **0.0025–0.0212**. Those true-tail numbers are themselves worth recording: the six env columns are
   almost perfectly redundant between adjacent cells, which is *why* the address hypothesis was credible.
7. **The prediction sets behind ADR 0038 are now frozen.** `diagnose_copula_capacity.sh` wipes
   `capacity/$CAPTAG` unconditionally, so a single `CAPTAG` reuse would have destroyed the only artifacts
   backing the shipped numbers; they are copied read-only to `capacity/frozen-*`.

## 7. Consequences

- ADR 0038's §"DO THIS FIRST" item 3 is **superseded in its threshold** but confirmed in its intent.
- **A note on ADR 0038's ladder.** The saturation fit and the "0.889 needs 1052× the table" extrapolation
  rest on rungs separated by **+0.002 / +0.003** `emu_r`. A paired tile-cluster bootstrap of a Δ`emu_r` of
  this kind gives a spatial-sampling sd of order 0.01 — several times those increments — and no seed
  replication exists anywhere in the ladder (`seed = a` is hard-wired, at `ntrees = 6`). Those two claims
  should be treated as **unresolved**, not established. This ADR does not restate them.
- Line M: do not re-pin. The reason is now stronger and more specific than "it might be an address" — on
  today's (confounded) evidence the artifact damps the Wooddens transient response by 37 %.
- The constructive follow-up this exposes: the env tail is a **2000–2019 climatology applied to every year**,
  including ssp370 rows, so it cannot carry a response by construction. A `BOUNDARY_WINDOW`-style
  **transient** env tail (ADR 0026's treatment applied to the six columns) is the only version that could,
  and it is not built.
