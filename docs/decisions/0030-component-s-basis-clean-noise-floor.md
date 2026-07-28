---
status: "accepted"
date: 2026-07-28
deciders: "engineering agent on line S (full autonomy per STEERING_PROMPT.md; no owner gate — the safety net is the ADR + the measurement itself)"
consulted: "ADR 0031 (the tree-PFT truncation this measurement uncovered — read them together), ADR 0025 (the recruit-trait copula whose fidelity this gate scores), ADR 0026/0027 (pooled multi-regime + transient boundary — the artifacts under test), guardrail 7 / the `residual-diagnosis` skill (state the reference basis before chasing a residual), CLAUDE.md §3 (the 29-col `ind` output + `individual=true` semantics), the S1 handoff in lines/S/STATE.md"
informed: "lines/S/STATE.md (§Status + the S2/S3 milestone targets, rewritten by this ADR), MEMORY.md, the `emulator-validation-figures` + `slow-drf-pipeline` skills (their noise-floor sections carried the wrong basis claim and are corrected), scripts/noise_floor_vs_emulator.py, scripts/diagnose_ind_type_composition.py, the S2 conditioning work (which this ADR gives its success metric)"
---

# The Component-S trait gate is scored on the emulator's OWN stem population, against an attenuation-corrected ceiling — not against the raw seed1-vs-seed2 correlation

> **Scope.** This ADR fixes *how* Component-S per-cell trait fidelity is measured, and restates the S2 targets
> in those terms. It changes no physics, no artifact, and no runtime code path — only the diagnostics
> `scripts/noise_floor_vs_emulator.py` and `scripts/diagnose_ind_type_composition.py` (line-S owned) and the
> shared `scripts/sbatch_python.sh` env-forwarding list. Every committed baseline is byte-identical
> (guardrail 4). The *defect* this measurement uncovered — the emulator's truncated tree-PFT population — is
> **ADR 0031**; the two must be read together.

## Context

The steering P3 gate for Component S is *"per-cell error vs the seed1-vs-seed2 noise floor"*. LPJmL-FIT is
stochastic (RAND48 + `-DPERMUTE`, CLAUDE.md §3), so seed1 and seed2 are two equally-valid realizations of the
same cell and climate; their per-cell disagreement bounds what any environment-conditioned emulator can do.
`scripts/noise_floor_vs_emulator.py` measures that for the four copula axes `{SLA, Wooddens, D95max,
minwscal}` (ADR 0025).

The pre-S1 measurement (2026-07-27) could not be read quantitatively. It reported a `seed1-basis`
cross-check — the same seed1 quantity computed two ways, which must be ≈1 for the comparison to mean
anything — of **0.973 (SLA) / 0.488 (Wooddens) / 0.761 (D95max) / 0.092 (minwscal)**. The script's docstring
attributed that to per-cell-median *instability* in discrete/year-variable axes and concluded the
emulator-vs-floor gap could only be read "qualitatively"; `lines/S/STATE.md` nonetheless carried the resulting
numbers as the S2 premise (floor 0.90–0.97 ⇒ "learnable, not RNG-limited") and set S2's target at *Wooddens
per-cell-median r ≥ 0.75*.

## Root cause: two different stem populations (not median instability)

The floor selected survivor stems with `Type <= 6`; the emulator's own tables select
`TREE_TYPES = [1,2,3,4,5]` (`scripts/build_slow_runtime_table.py:74`). In the active parameter file `Type` is
the 0-based `pftpar` index (`fscanpftpar.c:177`), and ids **0–6 are all seven tree PFTs** (7/8/9 grass, 10–21
crops) — so `Type <= 6` was *right* and the emulator's basis is a **truncation** that omits the tropical
broadleaved evergreen (id 0) and the boreal larch (id 6). That defect is ADR 0031. For *this* ADR the
consequence is narrower: floor and emulator were measured on different populations, so their difference was
not a gap.

The mechanism behind the specific cross-check numbers is now measured, not hypothesised. FIT draws each
trait **uniformly from a PER-PFT `[low, high]` interval** (`src/tree/new_tree.c:195-206` via `getrndinterval`,
`include/numeric.h:59` — the par file's `median` field is unused on this path — plus a parent-inheritance
corridor, `draw_new_trait`, `:39-62`), so a per-cell trait median is a *composition* statistic. Id 0's minwscal
is drawn from `[0.05, 0.75]` with a measured per-stem median of **0.497**, against 0.12–0.21 for the
temperate/boreal PFTs — reaching far outside the `[0.025, 0.30]` span the truncated tables cover at all.
Recomputing per-cell medians on both populations over the 38 009 cells that pass ≥20 stems on both
(`scripts/diagnose_ind_type_composition.py`, job 1616777) reproduces the pre-S1 cross-checks exactly:

| axis | r(all-trees, truncated) | sd(all-trees)/sd(truncated) |
|---|---|---|
| SLA | 0.973 | 0.92 |
| Wooddens | 0.494 | 1.47 |
| D95max | 0.762 | 1.29 |
| minwscal | 0.093 | 2.69 |

Those are the pre-S1 `seed1-basis` numbers (0.973/0.488/0.761/0.092) to three decimals. The published
"median instability" diagnosis was wrong: the medians were not flipping on tiny stem-set differences, they
were measuring different PFT mixtures — and the complete tree set carries **1.3–2.7× more between-cell
spread** on three of the four axes.

## The measurement, made basis-clean (evidence — job 1617055; identical numbers in 1616690 and 1617044)

Three bases, most authoritative first:

1. **`copula` (definitive for scoring today's emulator)** — seed1 `Y_<axis>.f64` vs seed2 `Y_<axis>.f64`,
   both written by `build_slow_runtime_table.py MODE=copula` with **only `SEED` differing** (static per-cell
   boundary, no `STEM_CAP`, same soilmoist/lai coverage gate). The emulator's observed values *are* seed1's
   `Y`, so floor and emulator share one stem-selection code path. New seed2 artifact:
   `/p/tmp/jamirp/emulator_global/slow_copula_historic_seed2` (133 562 549 stems / 45 072 cells vs seed1's
   133 542 295 / 45 009; 0.0000 coverage-gate drop; ~70 s on 32 cpus).
2. **`tree5`** — the same truncated population re-derived independently from the `ind` parquets. It
   reproduces basis 1 **to three decimals on every axis and statistic**, and its `seed1-basis` cross-check is
   **1.000 on all four axes** — two independent code paths agreeing is the verification, and the S1 gate.
3. **`tree7`** — `Type <= 6`, FIT's complete tree set: the population the emulator *should* cover, so its
   floor (SLA 0.965 / Wooddens 0.923 / D95max 0.895 / minwscal 0.973) is the real forest's. Its GAP column is
   cross-population and is explicitly *not* a gap until ADR 0031 lands.

**Split-half decomposition** (each cell's stems split by within-cell rank parity, Spearman-Brown corrected):
seed1's own median reliability is **0.978–0.999** while the floor is 0.694–0.964 ⇒ the seeds' disagreement is
**not** finite-stem sampling but genuine **trajectory divergence** (the RNG grows a different forest, not a
different sample of one forest).

**Attenuation.** `floor_r` is a *realization-vs-realization* correlation, so it is the ceiling only for a
predictor whose per-cell median is as noisy as one seed's. The emulator's is not: `pred_<axis>.f64` is one
RNG draw per row (`eval_slow_copula.jl:79-85` → `DRF.predict_quantile`), so its per-cell median carries draw
noise but **no** trajectory divergence, and its measured split-half reliability `rel_P` (0.907–0.997)
*exceeds* `rel_Y = floor_r`. With truth `m = μ(env) + δ(RNG realization)` and prediction `p = ν(env) +
ε(draw)`, `emu_r = r(ν,μ)·√rel_P·√rel_Y`, so the reachable ceiling (perfect center, this emulator's
dispersion) is `√(rel_P·rel_Y)`, and `r_center = emu_r/√(rel_P·rel_Y)`:

| axis | emu_r | rel_Y (=floor) | rel_P | **ceiling** | **GAP** | **r_center** | headroom |
|---|---|---|---|---|---|---|---|
| SLA | 0.866 | 0.964 | 0.997 | 0.981 | **+0.115** | 0.883 | 0.117 |
| Wooddens | 0.567 | 0.694 | 0.907 | 0.794 | **+0.226** | 0.715 | 0.285 |
| D95max | 0.771 | 0.791 | 0.962 | 0.873 | **+0.102** | 0.883 | 0.117 |
| minwscal | 0.793 | 0.909 | 0.986 | 0.947 | **+0.153** | 0.838 | 0.162 |

Two readings follow. The raw `floor_r − emu_r` gap **understates** the headroom on every axis, and **D95max is
not "at floor"** — its raw gap of +0.021 becomes +0.102 once the ceiling accounts for the emulator's own
stability. Second, `rel_P` vs seed1's split-half reliability shows Wooddens' predicted per-cell distribution
is **over-dispersed within cells** (0.907 vs 0.978).

**Between-cell dispersion** (correlation is scale-blind; this is not). A second realization has the same
between-cell spread as the first — `sd(Y2)/sd(Y1)` = 0.997–1.013 across all axes, the reference. The
emulator's is much smaller: `sd(pred)/sd(Y1)` = **0.946 (SLA) / 0.546 (Wooddens) / 0.732 (D95max) / 0.736
(minwscal)**. The copula regresses cells toward the global mean, reproducing barely half of the true
between-cell wood-density spread — the signature of missing between-cell conditioning, not of noise, and
consistent with the composition mechanism above.

## Decision

1. **The floor is defined on the emulator's OWN stem population**, realized as the `copula`-table basis:
   `Y_<axis>.f64` from two `build_slow_runtime_table.py MODE=copula` builds differing in **nothing but
   `SEED`**. `STEM_CAP` must stay off (it subsamples `Y` and would inject subsampling noise into the floor).
   The rule is *same population*, not *ids 1–5*: when ADR 0031 widens the training population to ids 0–6, the
   floor moves with it (to the `tree7` numbers) and every figure below must be re-measured.
2. **`seed1-basis ≥ 0.99` is a hard gate.** A floor whose independent re-derivation does not reproduce the
   emulator's own observed medians is void, and no gap may be quoted from it. `tree5` reads 1.000; `tree7`'s
   sub-1 value is now correctly interpreted as the *size of the truncation*, per axis.
3. **The headline trait metric is the attenuation-corrected pair `(GAP, r_center)`**, reported with `rel_Y`
   and `rel_P` so the ceiling is auditable, plus the between-cell dispersion ratio (a correlation alone hides
   a factor-of-two spread deficit). The raw `floor_r − emu_r` gap stays as a reported *lower* bound.
4. **S2's success criteria are restated in these terms** (superseding the `lines/S/STATE.md` wording): close
   ≥ 50 % of the Wooddens GAP to the ceiling, **and** bring `sd(pred)/sd(Y1)` to ≥ 0.75 on that axis, with
   pooled KS not degraded (≤ 0.02) and no other axis losing more than 0.01 of `r_center`. Absolute-r targets
   are retired: they are only meaningful against a stated population and ceiling, both of which move under
   ADR 0031.
5. **These numbers describe the CURRENT, truncated emulator** and are superseded by the post-ADR-0031
   re-measurement. S2 must not be tuned against them: ADR 0031's retrain comes first, because it changes both
   the floor (0.694 → 0.923 on Wooddens) and the training signal.
6. **No axis is declared finished.** Ranked headroom today: Wooddens (+0.226) > minwscal (+0.153) > SLA
   (+0.115) ≈ D95max (+0.102).

## Consequences

- S1 is met: the per-axis headroom is an exact, reproducible number with a named, gated basis — so S2's
  outcome will be measurable rather than arguable.
- **Two published claims are withdrawn.** (a) "the trait floor is 0.90–0.97 ⇒ learnable, not RNG-limited" is
  true only on the complete-tree population; on the population the emulator actually trains on, Wooddens'
  floor is **0.694**. (b) The committed "per-cell-median instability" explanation of the low cross-checks was
  wrong — the cause is PFT-composition truncation (ADR 0031). The *conclusion* (real headroom, not RNG
  saturation) survives on every axis and is in fact larger than claimed.
- Cost is negligible and repeatable: seed2 table ~70 s, the whole three-basis gate one ~10-min SLURM job, so
  re-running it on every retrain is now expected rather than exceptional.
- The count-floor caveat is **unchanged and still open**: the reported count floor pools a cell's survivor
  stems over all years and patches while the count emulator targets per-`(Cell,Patch,Year)` `n_living`, so
  "counts are at the floor" remains an order-of-magnitude statement, not a gate. Making it like-for-like is a
  scoped follow-up.
- Nothing here touches conservation, an artifact, or a contract surface, so this ADR alone is not an
  integration point with line M. (ADR 0031 is.)

## Alternatives considered

- **Split-half instead of a second seed** (no seed2 build). Rejected as a substitute: it measures
  finite-stem-sample noise only and reads 0.978–0.999, which as a floor would have claimed a ~0.99 ceiling
  and grossly overstated the headroom. Kept as the *decomposition* that proves the floor is trajectory
  divergence.
- **Keep raw `floor_r` as the ceiling** (simpler; matches "the emulator is a sampler, so it is a third
  realization"). Rejected as the headline because it demonstrably understates the headroom — it labelled
  D95max "at floor" at +0.021 when the reachable gap is +0.102 — but retained as a reported lower bound.
- **Rebuild seed2 with `BOUNDARY_WINDOW=20 STEM_CAP=400`** (the literal S1 handoff command). Rejected:
  `STEM_CAP` subsamples the trait targets, which would make the floor noisier than, and not parallel to, the
  emulator's own uncapped table. (That command also silently omitted `MODE`/`SCENARIO`, which
  `sbatch_python.sh` did not forward — fixed here by extending its forwarding list.)
- **A per-cell KS distance or quantile vector instead of the median.** Deferred, not rejected: pooled and
  per-cell KS panels already exist (ADR 0025 / the figures skill), and the median is what the S2 target is
  written against. Worth adding if S2's median gain proves basis-sensitive.
