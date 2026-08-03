---
status: "accepted"
date: 2026-08-03
deciders: "engineering agent on line S (full autonomy per STEERING_PROMPT.md). Five decisions: (1) ADR 0040's pre-registered rule is APPLIED AS WRITTEN to the completed salt-0 forest matrix and returns **RESPONSE — the six env columns are not a spatial address** on the criterion-1 axis, `[PROVISIONAL]` because clause 3 needs a second colouring; the salt-1 flip thresholds are fixed in §4 BEFORE the deciding rung landed; (2) ADR 0040 §4's attribution of the 37 % Wooddens transient damping TO THE ENV TAIL is **refuted** by the matched `p8` arm it itself asked for — the matched ncond-8 baseline damps 39.9 % on its own and the tail moves `Rb` *toward* zero — so §5 bullet 4's promotion gate is simultaneously **met and mis-specified**, and is re-specified here on `Rb` AND `Rr` AND `|Ra-1|` at BOTH fold modes; (3) line M's re-pin refusal STANDS but is **re-grounded**: not \"it might be an address\" (settled: it is not) and not \"the tail damps the transient\" (measured: it does not), but that on the honest fold design the tail buys +0.031 of level skill while COSTING 0.031 of transient pattern correlation — the two gates dissociate; (4) three quiet defects found and fixed, each of which silently manufactured a plausible number: an inert `BLOCK_SALT` that would have fabricated a perfectly-agreeing replicate and forced a false RESOLVED, a Float32 accumulation that put a runtime-provisioned env tail 3.35e-07 off the trained values, and a bootstrap whose cluster labels were not row-aligned with the statistic; (5) the per-cell env sidecar `cell_env.parquet` ships, gated bit-exactly against the shipped artifact's own `Xc`, clearing the mechanical half of M's blocker."
consulted: "ADR 0040 (the pre-registration this adjudicates — its rule is applied verbatim, and three of its own statements are corrected here), ADR 0038 (whose +0.037 gain is shown to be reproducible by a PURE ADDRESS under the published fold design), ADR 0030 §4 (criteria 1/2 and why Wooddens is the adjudicating axis), ADR 0033 (this line crediting one change with another's effect — now the third recorded instance), ADR 0023 (train/inference consistency — the Float32 finding is that trap at its quietest), ADR 0041 (the inert `random_seed`, the same failure shape as the inert `BLOCK_SALT`), ADR 0026/0027 (the transient boundary basis), ADR 0004 (constant CO2), CLAUDE.md §6 guardrails 4 and 7"
informed: "lines/S/STATE.md (NEXT), lines/M/STATE.md (the re-pin refusal stands on new grounds; `cell_env.parquet` now exists; the `cond_cols[-4:]` positional-check request is unchanged), the slow-drf-pipeline skill, CLAUDE.md §1/§4, changelog.d/S-{blocked-cv-verdict,block-salt-passthrough,cell-env-sidecar}.md"
---

# The env tail transfers across a severed neighbourhood — but its transient benefit was interpolation

> **Status.** `accepted`. The verdict on the address-vs-response question is **RESPONSE**, `[PROVISIONAL]`
> pending one outstanding colouring whose flip thresholds are fixed in §4 below. No shipped artifact changes.
> ADR 0040's rule is applied exactly as written; where this ADR disagrees with ADR 0040 it disagrees with its
> *measurements and attributions*, never with its criterion.

## 1. The matrix — seven arms, one row universe

All arms `NTREES=6 SUBSAMPLE=2000000 MAX_DEPTH=22 MIN_LEAF=20 QRF=1 KFOLDS=5 TRAIT_ONLY=1`, pooled row
universe `n = 42 227 077`, 58 766 cells, **57 719 scored at ≥20 stems**, seed1 ≥MINSTEM basis.
`emu_r / sd_ratio`, every value read from the named log.

| arm | ncond · tail | fold | log | SLA | **Wooddens** | D95max | minwscal |
|---|---|---|---|---|---|---|---|
| **A** `p8-hash-mtry4` | 8 base | hash | `1678608:86-89` | 0.9288 / 0.9244 | **0.8693 / 0.7083** | 0.8333 / 0.7743 | 0.9766 / 0.9849 |
| **B** `pooled-env-qrf-b6x2M` | 14 env | hash | `1647661:108-114` | 0.9504 / 0.9686 | **0.9095 / 0.8493** | 0.8759 / 0.8604 | 0.9803 / 0.9875 |
| **C** `p8-blk15-buf5-mtry4` | 8 base | blk s0 | `1678611:87-90` | 0.8008 / 0.8762 | **0.7340 / 0.6523** | 0.7401 / 0.7325 | 0.9596 / 0.9703 |
| **D** `p14env-blk15-buf5` | 14 env | blk s0 | `1678612:87-90` | 0.8305 / 0.9454 | **0.7654 / 0.7423** | 0.7907 / 0.8399 | 0.9574 / 0.9649 |
| **E** `p14geo-hash` | 14 geo | hash | `1678637:86-89` | 0.9565 / 0.9730 | **0.9231 / 0.8503** | 0.8831 / 0.8685 | 0.9817 / 0.9869 |
| **F** `p14geo-blk15-buf5` | 14 geo | blk s0 | `1678638:87-90` | 0.6594 / 0.7986 | **0.5786 / 0.5690** | 0.6825 / 0.7997 | 0.9351 / 0.9406 |
| **G** `p14perm-hash` | 14 perm | hash | `1678610:86-89` | 0.9177 / 0.9068 | **0.8492 / 0.6658** | 0.8136 / 0.7539 | 0.9740 / 0.9826 |
| **C′** `p8-blk…-s1-mtry4` | 8 base | blk **s1** | `1680712:87-90` | 0.8033 / 0.8748 | **0.7476 / 0.6377** | 0.7402 / 0.7508 | 0.9570 / 0.9636 |

Three basis facts, each verified rather than assumed:

- **Arm B is the SECOND gate table in `1647661`.** The first (`:100-107`, Wooddens 0.8261) is the confounded
  40-tree/50k/d14/QRF=0/mtry3 in-place baseline and is used nowhere here. B's own header line
  (`1647661:3`) states `ncond=14, 6 trees x 2M subsample, d22, min_leaf 20, QRF=1`, and its `@info` block
  reports `naxes=4, nstruct=0, kfolds=5` — capacity-matched to the 2026-08-03 arms.
- **Effective `mtry` is 4 in all seven arms.** `src/drf.jl:257` is
  `mtry_eff = mtry <= 0 ? max(1, round(Int, sqrt(p))) : mtry`, and `round(sqrt(8)) = 3` while
  `round(sqrt(14)) = 4`. A and C pass `MTRY=4` explicitly; D/E/F/G log `MTRY=0` ⇒ 4 at p = 14; B predates the
  knob and takes the same default. The hidden fourth lever of ADR 0040 §6.4 is therefore held fixed.
- **Fold designs are matched within each mode.** Hash `test_cells [11728, 11757, 11694, 11720, 11867]`,
  `buffered_rows 0`, identical across A/B/E/G *and* reproducing ADR 0040's published set. Blocked salt 0
  `test_cells [15285, 10995, 11199, 8014, 13273]`, `train_cells` mean **28 802**,
  `buffered_rows [16.4M, 12.1M, 11.4M, 11.6M, 13.9M]` — character-identical across C, D and F.
  `SUBSAMPLE = 2e6 < train_rows` in every fold of every arm, so per-tree capacity is matched too.

## 2. Derived quantities, with a MEASURED noise scale

Paired 166-tile cluster bootstrap, `NBOOT = 4000`, computed twice independently (two seeds agreeing to
0.0002), and **gated on reproducing all 28 logged `emu_r` and all 28 logged `sd_ratio` from the stored
`pred_*.f64` to max |Δ| 5.8e-5** before any inference. Evidence: `logs/S-power5.1682121.out`,
`logs/S-tileboot.1682719.out`.

| axis | Δ_hash = B−A | Δ_blocked = D−C | ratio | 0.5·Δ_hash | gap D−F | address E−A | width G−A | F−C |
|---|---|---|---|---|---|---|---|---|
| SLA | +0.0216 ± 0.0043 | +0.0297 ± 0.0158 | 1.375 ± 0.62 | +0.0108 | +0.1711 ± 0.0294 | +0.0277 ± 0.0057 | −0.0111 ± 0.0020 | −0.1414 ± 0.0331 |
| **Wooddens** | **+0.0402 ± 0.0061** | **+0.0315 ± 0.0157** | **0.783 ± 0.411** | **+0.0201** | **+0.1868 ± 0.0386** | **+0.0538 ± 0.0067** | **−0.0201 ± 0.0022** | **−0.1553 ± 0.0362** |
| D95max | +0.0426 ± 0.0042 | +0.0506 ± 0.0126 | 1.188 ± 0.255 | +0.0213 | +0.1082 ± 0.0156 | +0.0497 ± 0.0045 | −0.0197 ± 0.0019 | −0.0576 ± 0.0132 |
| minwscal | +0.0038 ± 0.0010 | −0.0022 ± 0.0022 | −0.577 ± 0.79 | +0.0019 | +0.0223 ± 0.0058 | +0.0052 ± 0.0011 | −0.0026 ± 0.0004 | −0.0245 ± 0.0053 |

Wooddens tail probabilities: `P(Δ_blocked ≤ 0) = 0.021` · **`P(clause 1 fails) = 0.244`** ·
`P(gap D−F ≥ 0) = 0.0000` · `P(criterion-2 blocked pass) = 0.416`.

**This supersedes ADR 0040 §7's single "spatial-sampling sd of order 0.01."** Measured, it is **0.004–0.006
under hash folds and 0.012–0.016 under 15°/5° blocking** — 1.6× too large for the hash case and 1.6× too
small for the blocked one. It is a *lower* bound: fold colouring and forest seed add to it, and arm C′ now
puts a number on the colouring term (§4).

**Δ_blocked is one-fold-dominated, and this bounds every blocked claim below.** Per-fold Wooddens Δ inside
each held-out fold's own test cells (`S-power5:158-174`):

| fold mode | f0 | f1 | f2 | f3 | f4 | pooled | sd/√5 |
|---|---|---|---|---|---|---|---|
| hash | +0.0401 | +0.0415 | +0.0360 | +0.0422 | +0.0409 | +0.0402 | **0.0011** |
| **block s0** | **+0.1253** | +0.0312 | +0.0130 | +0.0028 | **−0.0117** | +0.0315 | **0.0243** |

Fold 0 carries ~84 % of the blocked delta from 26 % of the cells, and it is the fold with the **fewest**
training cells (20 973) and the **most** buffered rows (16.4 M). D95max blocked behaves the same way
(`+0.0813 / +0.0011 / +0.0836 / +0.0536 / +0.0060`). Under hash folds the same quantity is stable to 0.0011
across folds — so the instability is a property of blocking, not of the estimator.

## 3. The pre-registered rule, applied as written

ADR 0040 §5's rule is on `emu_r`, and its adjudicating axis is **Wooddens**: ADR 0030 §4 defines criteria 1
and 2 on Wooddens alone, and ADR 0040's own advance expectations (`Δ` retains ~86 %, `geo` null 0.14–0.21)
are quoted in Wooddens numbers. §5 names **no axis set and no vote count**, so no per-axis tally is read into
it.

| clause | test | Wooddens | result |
|---|---|---|---|
| **RESPONSE** | `Δ_blocked ≥ 0.5·Δ_hash` | +0.0315 ≥ +0.0201, margin **+0.0114** | **met** |
| | blocked `p14geo` far below blocked `p14env` | 0.5786 vs 0.7654 — gap **+0.1868 = 5.9 × Δ_blocked**, `P(fail) = 0.0000`, and it holds in all five folds | **met** |
| **ADDRESS** | `Δ_blocked → 0` | +0.0315, `P(≤0) = 0.021` | not met |
| | blocked `p14geo` ≈ blocked `p14env` | 0.5786 vs 0.7654; geo is also **0.1553 BELOW the no-tail baseline C** | not met |
| **NOT RESOLVABLE** | the two salts disagree by > `0.5·Δ_blocked` = **0.0157** | arm C′ has landed, arm D′ has not | **PENDING — §4** |

Corroboration on the three non-adjudicating axes: clause 1 is also met on SLA (+0.0297 ≥ +0.0108) and D95max
(+0.0506 ≥ +0.0213), and **not** met on minwscal (−0.0022 vs +0.0019) — where the axis sits at 0.96–0.98,
within 0.04 of its ceiling, and Δ_hash is only +0.0038. Clause 2 is met on all four axes at
`P(fail) = 0.0000`.

The surrogate screen in ADR 0040 §3 predicted, in advance, that the gain would survive with ~86 % retention.
Measured retention is 78 % (Wooddens), 137 % (SLA), 119 % (D95max) — the forests behaved as the screen
predicted or better on every axis with a resolvable delta. That the *screen* and the *forests* agree, having
been frozen in that order, is the strongest single piece of evidence here.

## 4. VERDICT, and the flip thresholds fixed in advance

> **RESPONSE — the six env columns are not merely a spatial address.** `[PROVISIONAL — pending arm D′]`
>
> Severing the 15°/5° neighbourhood leaves the conditioning gain positive on the criterion-1 axis —
> `Δ_blocked = +0.0315`, CI95 `[+0.0011, +0.0633]`, `P(≤0) = 0.021` — clearing the pre-registered bar
> `0.5·Δ_hash = +0.0201`. The pure-position control on the identical rows collapses **0.1868 below the
> treatment and 0.1553 below no tail at all**. The `geo` tail's sign flip with fold design (**+0.0538** hash
> → **−0.1553** blocked) cannot be a weak-encoding artifact, because the identical basis on the identical
> rows is the **strongest of all seven arms** under hash folds.

**What "RESPONSE" means, precisely, and what it does not.** It means what the rule tested: a present-day
static covariate that transfers across a severed neighbourhood rather than acting as a lookup key. It says
**nothing about time**. The tail is a 2000–2019 climatology applied to every row including ssp370 rows, so it
cannot carry a transient response by construction — and §5 shows the transient is exactly where the artifact
is weak. Reporting this verdict without that sentence attached would mislead line M.

**The salt-1 thresholds, fixed here before arm D′ landed.** Arm C′ (`1680712`, salt 1) gives
`p8-blk-s1 = 0.7476`, so with `Δ_blocked(s0) = +0.0314` and a clause-3 tolerance of `0.5·Δ = 0.0157`:

| arm D′ (`p14env-blk15-buf5-s1`) `emu_r` lands | Δ_blocked(s1) | verdict becomes |
|---|---|---|
| **≥ 0.7677** and ≤ 0.7947 | in [+0.0201, +0.0471] | **RESPONSE, final** — salts agree and both clear clause 1 |
| in [0.7633, 0.7677) | in [+0.0157, +0.0201) | salts agree but clause 1 holds on one colouring only. The rule does not cover this; the honest reading is **NOT RESOLVABLE**, recorded as a **gap in the pre-registration** rather than settled by picking a colouring |
| < 0.7633 or > 0.7947 | outside [+0.0157, +0.0471] | **NOT RESOLVABLE** — clause 3 fires |

Two ambiguities in §5's wording, flagged rather than resolved in our favour: it says "disagree by more than
`0.5 · Δ_blocked`" without saying *which* `Δ_blocked` — the table above uses salt 0's (0.0157); and it gives
no axis set. Both readings are stated so a future session cannot silently pick the convenient one.

**Clause 3 is at material risk, and arm C′ quantifies why.** Re-colouring alone moved the *baseline* arm by
**+0.0136** in Wooddens (C 0.7340 → C′ 0.7476) and by −0.0026 to +0.0025 on the other axes. A colouring
effect on one arm of the same order as the delta between arms is precisely the regime clause 3 was written
for. Independently: the surrogate's own two-salt spread on the blocked Δ is 0.0188 (ADR 0040 §3), already
larger than the 0.0157 tolerance; the measured spatial sd of Δ_blocked is 0.0157, i.e. the clause compares
two draws with a tolerance of exactly one sd of the statistic; and §2 shows Δ_blocked is effectively one
tile-group's result, which is the thing re-colouring re-partitions.

## 5. The second gate: ADR 0040 §4's attribution is refuted, and the gate itself was mis-specified

ADR 0040 §4 measured that the shipped artifact damps the mean Wooddens warming shift by 37 %
(`Rb = −892` against an observed `+2433`) and — correctly flagging its own four-lever confound — deferred
causation to "the matched `p8` rung in §5". That rung ran this session. Wooddens, `meanDobs = +2432.9`,
split-half ceiling 0.9201:

All CIs below are from job **1683182**, i.e. **after** the §7.3 cluster-label fix, and both gates passed that
job's reproducibility check (two runs byte-identical at the fixed seed). The pre-fix intervals printed by jobs
1680715 / 1681338 were understated roughly 3–5× and **must not be quoted** — this table supersedes them.

| arm | `Rr` [CI95] | `Ra` | `Rb` [CI95] |
|---|---|---|---|
| A `p8-hash-mtry4` | +0.3751 [+0.311, +0.435] | 1.0728 | **−971.5 [−1820, −153]** |
| B `p14env-hash` | +0.4146 [+0.332, +0.498] | 0.8694 | **−892.0 [−1369, −328]** |
| G `p14perm-hash` | +0.3598 [+0.300, +0.417] | 1.0192 | −680.3 [−1502, **+152**] |
| E `p14geo-hash` | +0.4361 [+0.356, +0.513] | 0.9079 | −1313.2 [−1826, −815] |
| C `p8-blk` s0 | +0.2953 [+0.252, +0.342] | 1.1189 | −896.6 [−1937, **+345**] |
| D `p14env-blk` s0 | +0.2648 [+0.210, +0.318] | 0.8629 | −733.4 [−1588, **+186**] |
| F `p14geo-blk` s0 | +0.2173 [+0.176, +0.260] | 0.8495 | −1507.6 [−2419, −593] |

1. **ADR 0040 §4's attribution of the damping to the env tail is UNSUPPORTED — but the honest statement is
   weaker than "the tail reduces damping".** The matched ncond-8 baseline damps **39.9 % on its own**
   (`Rb` −971.5, CI excluding 0), so the damping exists without any env tail and cannot be attributed to it.
   The tail's point estimate moves `Rb` *toward* zero (+79.5 hash, +163.2 blocked) — but with correctly
   clustered CIs those inter-arm gaps sit far inside the marginal intervals, so **the ordering of A vs B is a
   point-estimate result, not a resolved difference.** The missing statistic is a **paired** bootstrap of the
   difference `Rb(B) − Rb(A)` on common tiles; the marginal CIs above are the wrong instrument for it and it
   is not computed. Two further consequences of the corrected intervals: under **blocked** folds the damping
   itself is no longer significant (C and D both include 0), and `p14perm`'s near-zero damping is likewise
   unresolved. What survives unambiguously is the **hash-fold** damping of A, B and E, and the fact that E
   (pure address) damps *more* than either, with a CI excluding 0 at both fold modes.
   Regardless of resolution, ADR 0040's §5 bullet-4 gate *as literally worded* ("the env tail does not
   significantly damp `Rb`") is **met** — nothing in this table shows the tail damping relative to the matched
   baseline. This is the **third** recorded instance on this line of crediting one change with another's
   effect (ADR 0033), and all three were caught the same way: by building the matched arm.
2. **The gate was therefore mis-specified**, because it is passable by a change that makes the transient
   worse. Re-specified: a matched `p8`-vs-`p14env` comparison **at both fold modes**, on `Rb` **and** `Rr`
   **and** `|Ra − 1|`. Under that gate the tail **fails**:
   - **`Rr` flips sign with the fold design** — env−p8 is **+0.0395** at hash but **−0.0305** at blocked. The
     tail's apparent transient-pattern benefit does not survive honest transfer; under blocking it is a
     penalty. This is the central dissociation of this ADR: **the level delta survives blocking, the
     transient-pattern delta does not.** Same caveat as above — the marginal `Rr` CIs overlap at both fold
     modes, so the *sign reversal of the point estimates* is the claim, and a paired difference bootstrap is
     needed to call either arm significantly better. What the sign reversal does establish, robustly, is that
     **an `Rr` advantage measured under hash folds cannot be assumed to hold under blocking** — which is
     enough to forbid promoting on the hash-fold number.
   - **Shift amplitude is worse at both fold modes**, and this one needs no CI because `Ra` is a ratio of
     dispersions rather than a difference of noisy means: `|Ra − 1|` goes 0.0728 → 0.1306 (hash) and
     0.1189 → 0.1371 (blocked).
3. **`Rb` closer to zero is not automatically better, and `p14perm` proves it.** The zero-information
   permuted tail has the *least* damping of any hash arm (−680.3) together with the *worst* pattern
   (`Rr` 0.3598). Less damping can be bought with noise, so `Rb` must never be read alone.
4. **A pure address is the worst arm on the mean shift** (−1313 hash, −1508 blocked) while being the best on
   hash-fold `Rr` (+0.4361). Position helps place the shift when neighbours are in the training set and
   anchors predictions to the cell's historic distribution otherwise.
5. **`Rr` is 0.217–0.436 against a 0.920 ceiling in every single arm.** The transient pattern is poorly
   captured by everything tested, which is a larger gap than any lever measured here.

## 6. Consequences for line M — the refusal stands, on different grounds

**Do not re-pin the 14-column artifact.** The previously cited reason is refuted and must not be repeated.
The grounds now are:

- The tail is a **frozen present-day hydrological envelope** — all six columns are moisture/aridity
  variables, built as a per-`Cell` mean over the historic-only `cell_year_feats.parquet` with **no scenario
  branch**, so an ssp370 row carries the historic climatology.
- On the honest fold design it buys **+0.031** of level skill while **costing 0.031** of transient pattern
  correlation and worsening shift amplitude at both fold modes, inside an artifact whose `Rr` is 0.22–0.44
  against a 0.92 ceiling.
- Clause 3 is unevaluated, and §4 shows re-colouring alone moves an arm by half the delta.
- Criterion 1's %GAP and criterion 4's `r_center` remain **unmeasured** — there is no pooled seed2, as every
  gate log states. Absence is not a pass.

**Two things did move in M's favour**, and they are independent of the verdict:

- `tables/cell_env.parquet` now exists (67 420 cells — a superset of the pinned table's 58 766), **gated on
  exact float64 equality against the shipped artifact's own `Xc` tail over 200 000 random real rows**. The
  mechanical blocker "the 14-column artifact is not coupled-runnable outside a bespoke script" is cleared for
  any future 14-column artifact, transient or not.
- The request to M is unchanged: `scripts/extract_cell_slow_init.py:142-146` checks
  `cond_cols[-4:] == BOUNDARY_COLS`, which a 14-column artifact fails **by construction** because its last
  four are the env tail. The correct check is positional, `cond_cols[4:8]`. That file is M-owned; S requests,
  M lands.

## 7. Three quiet defects, each of which manufactured a plausible number

Grouped because they share one shape: **a setting or a value that is never echoed back is unfalsifiable.**

1. **`BLOCK_SALT` was silently inert.** `eval_slow_copula.jl` reads it from `ENV`, but
   `diagnose_copula_capacity.sh` listed `FOLD_MODE`/`BLOCK_DEG`/`BUFFER_DEG`/`MTRY`/`CELL_LATLON` on the
   Julia command line and **not** `BLOCK_SALT`, so a salt-1 rung rode on `sbatch --export=ALL` inheritance
   and the `=== FOLDS:` header did not echo it. Had it stayed inert, arm C′ would have been a byte-copy of
   arm C — a replicate agreeing *exactly*, which does not weaken clause 3 but **inverts** it into a false
   RESOLVED. Fixed (passed explicitly + echoed); **proven at runtime** by C′'s
   `block_salt = 1` and its fold sizes `[14066, 8302, 13575, 11241, 11582]` genuinely differing from salt
   0's `[15285, 10995, 11199, 8014, 13273]`. Same shape as ADR 0041's `random_seed`.
2. **A Float32 accumulation put a runtime-provisioned env tail 3.35e-07 off the trained values.** Four of the
   six env columns are stored `Float32` in `cell_year_feats.parquet` and polars' `group_by().mean()`
   accumulates in `Float32`; the obvious aggregation missed on **199 093 of 200 000** probed rows (max |diff|
   7.63e-05 on `eco_diag_pet_mean` = exactly `5·2⁻¹⁶`), while the two `Float64` columns matched bit-exactly
   and thereby fingerprinted the mechanism. `.cast(pl.Float64)` before the mean reproduces the shipped tail
   bit-exactly. This is ADR 0023's train/inference shift at its quietest: too small to look wrong, too large
   to be zero, invisible to every coverage, finiteness and duplicate-key check in the pipeline. The general
   rule it establishes: **gate a provisioning artifact against the SHIPPED table, never against a re-run of
   the code that produced it** — the latter reproduces its own bugs.
3. **The response gate's bootstrap cluster labels were not row-aligned with the statistic.**
   `diagnose_slow_address_prereg.py` built them via `ll.join(DataFrame(Cell=…), on="Cell", how="inner")`,
   which returns rows in **`ll`'s** order while `dp`/`dy` are in `group_by` output order, and a
   `tl = tl[:min(len(tl), len(dy))]` truncation absorbed any length mismatch. Scrambled cluster labels make a
   tile bootstrap degenerate toward an independent-cell bootstrap and **understate** the spatial sd — the
   exact error the clustering was introduced to remove. Point estimates never touch the labels, so only the
   CIs were wrong, which is why it survived. **The detector was reproducibility**: `cluster_boot` has a fixed
   `seed = 12345`, yet two runs over identical inputs (jobs 1681338 and 1681925) printed identical point
   estimates and different CIs — possible only via the row-order dependence. Fixed with a cell-indexed
   lookup + a length assertion, and **verified by reproducibility**: job **1683182** runs each gate twice and
   diffs the output — both now byte-identical at the fixed seed.
   The re-measured intervals are **3–5× wider** and they change what §5 may claim, which is why §5 quotes only
   the post-fix numbers. Specifically: the hash-fold damping of A/B/E survives (CIs exclude 0), the **blocked**
   damping does **not** (C and D now include 0), and the inter-arm gaps (+79.5 in `Rb`, −0.0305 in `Rr`) are
   **not resolvable** with marginal CIs. This is a case where a defect in an *uncertainty* estimate, with every
   point estimate untouched, was the difference between a supported and an unsupported claim.

## 8. Corrections to ADR 0040's own text (it is immutable; these supersede)

1. **§3(b) / §6.4 mischaracterise `eco_diag_gdd_5` and `tas_cold_month` on the table the forests read.** On
   `slow_copula_pooled_w20_*` these are **time- and scenario-varying**: with `BOUNDARY_WINDOW=20` — which
   `run_pooled_slow_*.sh` require, and which `pooled_w20` is named for — they come from
   `cell_year_boundary_<scenario>_w20.parquet` joined on `["Cell","Year"]`
   (`build_slow_runtime_table.py:231-250`). They are per-cell constants only in `cell_year_feats.parquet`.
   §6.4's *arithmetic* (driver-touch probability 0.986 → 0.790) stands; its claim that the static tail dilutes
   "the ONLY channel through which time can enter" does not.
2. **§7's "spatial-sampling sd of order 0.01" is superseded** by the measured 0.004–0.006 (hash) /
   0.012–0.016 (blocked) of §2. Its *conclusion* — that ADR 0038's +0.002/+0.003 ladder increments are
   unresolved — is strengthened, not weakened: under hash folds those increments sit at well under one sd.
3. **"The env tuple retains 73 %/78 % of its skill" must not be written as a finding.** The retention ratio
   is `0.783 ± 0.411`, CI95 `[+0.05, +1.64]`, and clause 1 fails in **24.4 %** of paired tile resamples with
   the colouring held fixed. It is also scale-dependent: the same seven numbers give 0.534 on `emu_rho` and
   0.370 on Fisher-z. The rule named `emu_r`, so the **verdict stands**; the *gloss* must be the sign claim —
   "the gain does not vanish when adjacency is removed."
4. **Do not quote blocked `sd_ratio` 0.7423 against ADR 0030's criterion-2 threshold of 0.75.** Two
   independent reasons: the gate log forbids it four lines above the number (`1678612:80-82` — this basis is
   seed1 ≥MINSTEM, not the gate's seed1-INNER-seed2 basis, and no pooled seed2 exists), and even at face
   value it is `0.7423 ± 0.0307`, `P(pass) = 0.416`. The valid statement is the **delta**: the tail adds
   **+0.0900** of dispersion under blocking, +0.1410 at hash.

## 9. Also settled, so it is not re-litigated

- **The published hash-fold gain is not evidence of an environmental response.** `p14geo-hash` **0.9231**
  exceeds `p14env-hash` **0.9095** on Wooddens and on all four axes; the address gain E−A is
  **+0.0538 ± 0.0067 (z = 8.0)** against the env gain's +0.0402. Six pure-geometry columns reproduce *and
  exceed* the entire ADR-0038 gain under `mod(hash(cell), k)` folds. ADR 0038's doubt was well founded. The
  defensible conditioning figure is the **blocked +0.0315**, not +0.0402 and not ADR 0038's +0.0834.
- **Width is not free at matched `mtry`.** `p14perm-hash` scores **below** `p8-hash-mtry4` on every axis
  (−0.0111 to −0.0201, Wooddens −0.0201 ± 0.0022, z = 9). Fourteen zero-information columns are worse than
  eight, so the env tail's +0.0402 is net of a ~−0.020 width penalty and its information contribution is
  nearer +0.060. Caveat: this is measured **only at hash folds**, and this matrix proved fold-mode sign flips
  are real, so it must not be assumed fold-mode-invariant.
- **LPJmL-FIT selects WITHIN a PFT on wood density**, so "all trait variance is composition variance" is
  false: `src/tree/mortality_tree_ind.c` computes
  `mort_max = pow(10, wdmort_1 + wdmort_2/((wooddens*1)/1000000))` feeding `tree->mort_npp`. The uniform
  per-PFT recruit draw (CLAUDE.md §3) constrains the **prior**, not the emitted survivor marginal. Both
  channels — composition *and* within-PFT selection — run through the live flux/stress columns.

## 10. Surviving caveats, ranked, each with its cheapest decisive test

| # | caveat | cheapest decisive test | cost |
|---|---|---|---|
| 1 | **Clause 3 unevaluated ⇒ no verdict is final.** | Arm D′ `1680713` (`RUNNING`), thresholds fixed in §4. Response gate chained (`1681717`). | 0 — in flight |
| 2 | **Clause 1's ratio is unresolved** (`P(fail) = 0.244`) **and Δ_blocked is one-fold-dominated** (fold 0 = 84 % of it, from the fold with the fewest training cells). | More **colourings**, not more bootstrap: blocked pair at `BLOCK_SALT=2,3`. | 4 rungs × 1.4 h |
| 3 | **Δ_blocked has no width control** — the `perm` null exists only at hash folds. | One `p14perm-blk15-buf5` rung; `_t8perm` already exists. | 1 rung |
| 4 | **Blocking confounds "adjacency removed" with "39 % of training cells removed"** (47 013 → 28 802 mean train cells). Caveat 2's fold-0 correlation points at exactly this. | Two hash-fold rungs subsampled to ~28 800 train cells/fold — needs a ~10-line `TRAIN_CELL_FRAC` knob on `eval_slow_copula.jl` (S-owned). | 2 rungs + patch |
| 5 | **Forest-seed noise is entirely unmeasured** (`seed = a` hard-wired, `ntrees = 6`); no existing artifact can yield a replicate, and it **adds** to §2's sd. | Blocked pair at a bumped seed; a `SEED_BASE` knob is ~5 lines. | 2 rungs + patch |
| 6 | **The geo control is degraded, in the direction of the hypothesis.** The geo arms are the only arms with realized leaves **below `MIN_LEAF=20`** (`19/17/17/20` and `20/17/16/7`; every other arm's minimum is exactly 20 in all 16 fits). Mechanism: `src/drf.jl:128` guards on the sorted scan but `:137` sets `best_thr = 0.5*(xj + xj1)`, so ULP-adjacent distinct values from trig transforms collapse the midpoint onto `xj1`. Finer leaves = more address-memorisation capacity ⇒ inflates E, deflates F. | Rebuild `cell_geo_tail.parquet` **rank-transformed to consecutive integers** (split-equivalent for an axis-aligned tree; integer midpoints `k+0.5` are exact and strictly interior) and re-run the two geo rungs. **Do not patch `src/drf.jl`** — it moves fitted forests and committed baselines (guardrail 4). | rebuild + 2 rungs |
| 7 | **`mtry` dilution vs env information is still open** as the mechanism behind §5's amplitude cost. | `p14env hash MTRY=7` (matched fraction) and `MTRY=8` (matched driver-touch probability 0.985 vs the baseline's 0.986) — **both in flight**, jobs `1680827` / `1681596`. | 0 — in flight |
| 7b | **The response gate reports MARGINAL CIs, so no inter-arm difference is resolvable** (§5.1). Every arm-vs-arm claim on `Rb`/`Rr` is currently a point-estimate ordering. | Add a **paired** tile-cluster bootstrap of the difference on common tiles — the two arms share the same 52 450 cells and the same tiles, so the paired statistic is far tighter than the difference of marginals. ~15 lines in `diagnose_slow_address_prereg.py` (S-owned); the §2 `emu_r` bootstrap already does exactly this and can be copied. **Zero new forest compute.** | minutes |
| 8 | **Criterion 1 %GAP and criterion 4 `r_center` unmeasured** — no pooled seed2. | An ssp370 second spin-up (ADR 0041) — in flight as job `1678574`. | large |
| 9 | **A transient env tail is the constructive fix and is NOT the small job the handoff described.** It needs per-(Cell,Year) env features for 2020–2100 **and** a join key the tables do not have. `ENV_PARQUET` accepts a per-**Cell** tail only (`group_by("Cell").mean()`, broadcast by cell index), and the copula tables carry `cells.i64` + `scenario.i64` but **no `Year`** — so a fully transient join needs a schema change, which must ride a new generation (ADR 0036 §5b). | **A scenario-resolved tail is the tractable middle path**: key on `(Cell, scenario)`, which `scenario.i64` already supplies per row, so no schema change. All five ssp370 forcings exist (`tas/pr/huss/rsds/lwnet …orderA.clm`) with matching historic ones, and `climclusterpy.features` still imports, so the six columns can be recomputed by the canonical method. That is sufficient for the response gate, which is a two-block difference. | new derivation + 2 rungs |

## 11. Decision record

1. **The verdict is RESPONSE, `[PROVISIONAL]`**, with §4's thresholds binding. `[DECISION]`
2. **ADR 0040 §4's attribution is refuted; its §5 bullet-4 gate is met and mis-specified, and is
   re-specified** on `Rb` + `Rr` + `|Ra − 1|` at both fold modes, with §7.3's CI fix landed first.
   `[DECISION]`
3. **Line M does not re-pin**, on the §6 grounds. `[DECISION]`
4. **`cell_env.parquet` ships** as the runtime provisioning artifact, gated bit-exactly. `[DECISION]`
5. ADR **0039 is permanently vacant** — reserved by in-code reference during the 2026-08-03 concurrent-session
   collision and never written; nothing references it. This ADR takes **0042** rather than backfilling 0039,
   because a number that post-dates 0040/0041 in time should not pre-date them in the record. `[DECISION]`
