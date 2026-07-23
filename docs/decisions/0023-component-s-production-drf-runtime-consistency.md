---
status: "accepted"
date: 2026-07-23
deciders: "engineering agent (standing autonomous delegation, STEERING_PROMPT); reversible by the owner or a superseding ADR"
consulted: "ADR 0020 (S is flux-driven; conditioned at runtime on the channel it was trained on), ADR 0021 (S trained + run in native Julia), ADR 0022 (hand-rolled zero-dep DRF), ADR 0014 (runtime [deps] EMPTY), docs/p1_s_in_loop_design.md §6/§7, the Tier-1-Step-4 understanding workflow synthesis"
informed: "P1 Tier-1 Step 4 (production DRF artifact); src/drf.jl (serialization + copula); scripts/build_slow_runtime_table.py; scripts/train_slow_drf.jl; scripts/build_slow_oracle_reference.py; test/testitems/{drf_serialization,drf_copula,slow_production_drf,slow_oracle}_tests.jl; MEMORY.md; JOURNAL.md; CHANGELOG.md"
---

# Component S's production DRF loads from a serialized artifact and is trained on a RUNTIME-CONSISTENT feature table

> **Status note.** `accepted` 2026-07-23 under the standing autonomous delegation. It **implements P1
> Tier-1 Step 4** on top of ADR 0020/0021/0022 (S flux-driven, native-Julia, hand-rolled DRF) and ADR 0014
> (empty runtime `[deps]`). It does not change any of those; it records the mechanism + the feature-channel
> contract + one deliberate train/inference-consistency choice (the `age_mean` counter) and a documented
> proxy for two channels that need a Phase-2 data pipeline. Reversible by a superseding ADR.

## Context and Problem Statement

Through Tier-1 Step 3 the flux-driven `FluxDrivenSlowEmulator` runs in the coupled loop, but the DRF it
used was **built in-test** — there was no way to (a) train a DRF offline and hand the *same* model to the
coupled app, nor (b) guarantee the training features matched what the runtime feeds the model. ADR 0020 §6
requires S be **conditioned at runtime on the channel it was trained on**; a DRF trained on features that
do not match `src/components/slow.jl::flux_feature_vector` would be fed out-of-distribution inputs at
inference and predict nonsense (while still conserving carbon by construction — masking the error).

Two obstacles: (1) no serialization — a fitted `DRF.Forest` could not be persisted/loaded with the runtime
`[deps]` empty (ADR 0014); (2) three of the eleven runtime feature channels have no exact annual-`ind`
analog. The understanding-workflow synthesis flagged the **`age_mean` degeneracy** as the single biggest
correctness risk: at runtime `s.age` is a fixed-roster uniform counter (all cohorts advance +1/yr, never
reset on recruitment), so `age_mean ≡ elapsed-year counter`, **not** a demographic mean age. Training
`age_mean` as the mean living-tree `Age` from `ind` would teach a genuine age-structure dependence the
emulator can never reproduce — a silent train/inference feature-distribution shift on one of the 11 head
channels. Two further channels (`soilmoist`, `lai`) are coupled-state / stand-LAI quantities the 29-column
`ind` schema cannot reconstruct exactly (no `nind`/`leaf_c`; `soilmoist` is a WHC-fraction, `ind` carries
only water scalars).

## Decision

1. **Serialize the DRF as pure-Base text** (`DRF.save_forest`/`load_forest`, `src/drf.jl`): a
   self-describing whitespace stream with a `LPJMLFIT_DRF` magic + version header. Float64 fields use
   Julia's shortest round-trippable decimal (`string`/`parse`, exact since Julia 1.0), verified BITWISE by
   the round-trip testitem. No dependency (Serialization/JLD2 would need a `[deps]` entry and fail Aqua).
   Committed artifacts use the `.drf` extension — **never `*.bin`** (git-ignored). The coupled app builds
   `FluxDrivenSlowEmulator(fc, load_forest(path); boundary, n_init)`.

2. **Train on a RUNTIME-CONSISTENT feature table** whose columns are the exact `flux_feature_vector` order
   (`scripts/build_slow_runtime_table.py` → `scripts/train_slow_drf.jl`). Per-channel provenance from the
   annual `ind` ground truth (each row = one stem; `npp`/`agb` are already per-m² so per-patch row-sums are
   per-m² stand totals): `bm_inc_cell`=Σnpp (exact), `water_stress`=1−mean(wscal_mean) (exact-in-definition,
   **fixing** the old `mort_water`-inversion mismatch), `hmean`/`hmax`/`fpc`/`agb` (near-exact),
   `growth_eff`=bm_inc/lai (faithful), `n_prev`=prev-year count (AR).

3. **`age_mean` is trained as the elapsed-year counter, NOT mean tree Age** — matching what the runtime
   actually feeds (ADR-0022 "the model validated is the model that runs"). A follow-up ([TODO]) will promote
   the runtime `s.age` to a true per-cohort mean age (reset on recruitment) and retrain; until then, training
   on the counter is the correct, consistent choice.

4. **`soilmoist` and `lai` are DOCUMENTED PROXIES** at the demonstration scale: `soilmoist` = a constant
   matching the coupled `SharedState` init (0.7); `lai` = Σ per-crown ind LAI. The **runtime-consistent
   GLOBAL** table sources `soilmoist` from daily `swc` (fractional saturation) and `lai` from the C annual
   `LAI_STAND` output across cells — a Phase-2 SLURM data pipeline ([TODO], off this session's critical path).

5. **Ship a committed Hainich-scale demonstration artifact** (`test/testitems/references/drf_forest_hainich.drf`,
   40 trees, ~95 KB) + its meta/golden pairs, loaded by the in-loop testitem. It is **Hainich-only
   scaffolding** (guardrail #6), not multi-cell evidence; the global production forest lives on `/p/tmp`
   (DVC), not git.

6. **Gate-3 oracle basis** (`test/testitems/slow_oracle_tests.jl`): the coupled S size distribution (Height)
   is compared to the LPJmL-FIT C ground truth at Hainich as an IQR-normalized quantile-RMSE **drift alarm**
   (measured ~0.31, tolerance 0.40), framed honestly as recursive-coupled-S vs non-recursive-C-truth. The
   S-owned trait axes {SLA, Wooddens, beta_root} stay fixed-cohort until the copula recruit sampler's
   consumer (recruit-cohort APPEND) lands.

## Consequences

- **Positive.** The model that is validated is the model that runs (a serialized artifact, not an in-test
  DRF); the OOD-experiment water_stress mismatch is fixed for the runtime channel; the `age_mean` train/
  inference shift is closed by construction; the coupled S reproduces the C Hainich size distribution to
  ~0.31 IQR (Hainich-only). The Gaussian-copula recruit-trait sampler (`chol_lower`/`norminv`/`normcdf`/
  `GaussianCopula`/`sample_copula!`) is built + tested, ready for the append path.
- **Negative / deferred.** Two channels (`soilmoist`, `lai`) remain proxies until the global C-`LAI_STAND` +
  daily-`swc` pipeline runs; the committed artifact is Hainich-only; the copula is not yet wired into
  establishment (needs membership append/merge, design risk #5); `age_mean` stays a counter until the
  runtime `s.age` is promoted to a true mean age and S is retrained.

## Alternatives considered

- **Binary serialization (raw `reinterpret` bits).** Rejected: the text form already round-trips bitwise
  (Julia's shortest decimal), is human-inspectable, matches the all-text committed-fixture convention, and
  a committed `*.bin` is git-ignored. Binary stays the format for the large DVC-tracked global forest.
- **Train `age_mean` on mean `ind` Age.** Rejected — the biggest correctness risk (silent train/inference
  shift); see Decision §3.
- **Reconstruct `soilmoist`/`lai` from `ind`.** Impossible from the 29-col schema (no `nind`/`leaf_c`;
  `soilmoist` has no annual analog) — hence the documented proxies + the Phase-2 pipeline.
