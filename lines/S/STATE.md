# LINE S — Component-S science (branch `line/S`, worktree `wt-S`)

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/S/JOURNAL.md` (append-only). Decisions: ADR block **0030–0049**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here

**S1b is COMPLETE (ADR 0031 + 0033). Start with S1c (ADR 0032) — its blocking condition has now expired.**

Everything S1b promised is measured and merged: the widening, the `growth_eff` runtime guard, the per-PFT
params, artifact versioning, the byte-identity gate, the count before/after table, the trait before/after table,
and the ADR-0030 gate re-measured and **PASSED** (`seed1-basis` = 1.000 ×4). Headline: counts held (≈0.003 R²),
and traits **improved on every axis**, falsifying ADR 0031's degradation prediction → **ADR 0033**, which also
de-prioritizes S3 and re-baselines the S2 gate. All numbers are in §Status; don't re-derive them.

**Why S1c is now first:** its only reason for deferral was basis entanglement with S1b's before/after tables.
Those are published, so the reason is gone. Carrying it into S2 would re-entangle it with a conditioning change.
The full step list, the four gates to re-measure and the binary success signal are in **§5 below** — that is the
whole task; nothing needs re-deriving. It is **S-executable** (all four fixture consumers are S-owned; notify M,
don't wait for M).

*Everything below in §1–§4 is DONE — kept only as the audit trail for the numbers in §Status.*

### S1b audit trail (all DONE — kept for provenance; the NUMBERS live in §Status)

| gate item (ADR 0031 §3) | outcome |
|---|---|
| Hainich fixtures byte-identical | **investigated, not merely passed** → ADR 0032. The `.drf` moved; the control build proved the edits a no-op here (max\|abs diff\| = **0**, all 15 columns + target) ⇒ the fixture was ALREADY stale. Oracle CSVs + `.rcop` byte-identical. → **S1c**, §5 |
| cell coverage ≈ 54 020 | ✅ **exactly 54 020** (historic w20 seed1) |
| `seed1-basis ≥ 0.99` on the new population | ✅ **1.000 on all four axes** (job 1622436) |
| before/after table — counts | ✅ §Status |
| before/after table — traits | ✅ §Status + **ADR 0033** |

Jobs: `1622131` historic copula (+ its chained gate `1622436`) · `1622337` pooled copula at **NCPUS=96** after
`1622330` was **OOM-killed** (exit 137 — `STEM_CAP` does NOT bound peak memory; gotcha in the
`slow-drf-pipeline` skill) · `1622134` pooled count DRF · `1622242`+`1622305` historic count + K-fold ·
`1622132` seed2 floor table.

**Published + load-verified `t7` artifacts** (line M informed in `lines/M/STATE.md`, and M's own coverage gate
independently confirmed the payoff: `semiarid_sahel` 18371 is in **neither** pre-0031 table, so only `_t7`
serves all five biome cells, 5/5 vs 3/5):
`drf_forest_global_pooled_w20_t7.drf` (150 trees, `nfeat=15`) · `recruit_copula_global_pooled_w20_t7.rcop`
(128 MB, 4 axes, 8 cond cols in `live_flux_cond` order) · `drf_forest_global_historic_t7.drf` ·
`recruit_copula_global_historic_t7.rcop` · tables `slow_{count,copula,runtime}_*_t7/`.

**Not done, cheap, optional:** trait FIGURES 09–11 on `tree7`
(`COPULA_OUT=/p/tmp/jamirp/emulator_global/slow_copula_historic_t7`, `emulator-validation-figures` skill).

### THE TASK: S1c (ADR 0032) — start here, the deferral condition has expired

The committed Hainich demo `.drf` is on the retired PROXY feature basis (`soilmoist` 0.7, `lai` 21.2,
`growth_eff` 19) while the `.rcop` beside it is on the REAL one (0.85, 3.07, ~151) — one emulator, two
conditioning bases, a live ADR-0023 shift masked by the DRF's OOD leaf-clamping.

**The deferral condition has EXPIRED (2026-07-28).** The only argument for waiting was that regenerating the
fixture inside the ADR-0031 widening would leave two entangled causes behind every moved Hainich number
(ADR 0031 §3). S1b's before/after tables are now published, so that is gone. **Do not carry S1c into S2/S3** —
it would then entangle with a conditioning change instead. **Not started only because a half-executed S1c leaves
regenerated golden fixtures sitting in the worktree with no re-measurement** — worse than a clean start.

**Scope is smaller than ADR 0032 implies** (`[VERIFIED 2026-07-28]` by grep): every consumer of the committed
fixtures is **S-owned** — `test/testitems/{slow_oracle_tests,slow_oracle_traits_tests,slow_production_drf_tests,
drf_serialization_tests}.jl`. **No M-owned test loads them today** (M only *plans* to, for its M2 CI gate). So
this is S-executable with a NOTIFICATION to M, not a both-sides landing. Tell M before you push, because M's
M2 gate design assumes the current fixture.

Steps:
1. **Rebuild both demo tables from ONE build** so they cannot disagree again: `CELLS=42490 SEED=1` with
   `MODE=count` → `/p/tmp/jamirp/slow_runtime`, and `MODE=copula` → `/p/tmp/jamirp/slow_copula_hainich`.
2. **Retrain BOTH artifacts together** to their committed paths: `train_slow_drf.jl` (→ `drf_forest_hainich.drf`
   + `_meta.txt`) and `train_slow_copula.jl` (→ `recruit_copula_hainich.rcop` + `_meta`). Regenerating the
   artifact and its meta together is what keeps the golden pairs consistent.
3. **Assert the fix, don't assume it:** the two metas must now agree on the shared conditioning columns
   (`growth_eff`, `soilmoist`, and the boundary tail). That agreement IS the defect being closed — check it
   explicitly. The `.rcop` is already on the real basis, so expect it byte-identical; if it MOVES, stop.
4. **Re-measure the four gates, and document every threshold that moves** (`residual-diagnosis` — never widen
   an alarm silently):
   - `drf_serialization_tests.jl` — bitwise round-trip + committed golden pairs (structural; should pass).
   - `slow_production_drf_tests.jl` — the "targets INSIDE the training band" assertion. The band moves with the
     basis, so re-derive its bounds from the NEW meta. This is the assertion that was quietly toothless.
   - `slow_oracle_tests.jl` — the IQR-normalized quantile-RMSE drift alarm (documented ~0.31; 0.39 observed vs
     a 0.45 threshold, §Milestones S5). **Direction is genuinely unpredictable**: the DRF will be in-domain for
     the first time (should help), but the threshold was tuned against the OOD-clamped behaviour.
   - `slow_oracle_traits_tests.jl` — the `.rcop` gates; untouched if the `.rcop` is byte-identical.
5. **Full suite CI-faithfully on SLURM** (`scripts/run_tests_slurm.sh S-s1c`), then commit as ONE change with a
   before/after threshold table, and notify M in `lines/M/STATE.md`.

*Gate — cleanly checkable:* `scripts/verify_hainich_demo_artifacts.sh` flips from **exit 2 (`STALE-FIXTURE`)**
to **exit 0 (`PASS`)**, the two metas agree on the shared conditioning, the suite is green, and every moved
threshold has a written measurement. Until then exit 2 is **expected**, not a new failure
(`[VERIFIED 2026-07-28]`, job 1622370). The gate does not restore what it writes — afterwards:
`git checkout -- test/testitems/references/`.

## Scope + ownership (ADR 0029)

**You own (exclusive):**
- `src/components/slow.jl`, `src/drf.jl`, `src/climbuf.jl`
- `scripts/*slow*`, `scripts/flux_ood_experiment.jl`, `scripts/diagnose_*`, `scripts/noise_floor_vs_emulator.py`
- `test/testitems/{slow_*,drf_*,recruit_copula_*,climbuf_*,carbon_ledger_*}`
- `lines/S/*`, `changelog.d/S-*.md`, ADRs 0030–0049

**Do NOT touch:** `src/run.jl`, `src/interface.jl` (line M owns the coupling seam) ·
`src/components/energy.jl` (line E) · `ext/` (line O) · `Project.toml` (integrator).
Shared, additive-only: `src/LPJmLFITEmulator.jl` (inside the `# ── line S ──` region), `CLAUDE.md`, `MEMORY.md`.

**SLURM tag prefix:** `S-` · **scratch:** write under `/p/tmp/jamirp/...` paths you created; other lines'
artifacts are **read-only**.

## The contract you must not silently break (S → M)

Line M runs your emulator inside the coupled loop. **Frozen:** `FluxDrivenSlowEmulator(fc, forest; …)` kwargs ·
the `flux_feature_vector` column order · the `live_flux_cond` subset (ADR 0025) · the `.drf`/`.rcop` format
(ADR 0023) · the `cell_meta.parquet` schema.
Train/inference consistency is load-bearing (ADR 0023), so **a conditioning change is by definition a
both-sides change**: write the ADR, bump a version in the artifact meta (never mutate an artifact in place),
and coordinate an integration point with M. Never re-point M's pinned artifact path from this line.

## Status (2026-07-28)

- **P1 is DONE**: the flux-driven S runs in the coupled loop, carbon-conserving to ~1e-12 gC (ADR 0018→0027).
- **The tree-PFT truncation is FIXED in code (ADR 0031, S1b).** `TREE_TYPES` now lives in ONE place
  (`lpjmlfit_emulator.data`) and `features.py` / `config.yaml` / all four `build_slow_*.py` /
  `noise_floor_vs_emulator.py` **import** it. The `growth_eff` `÷max(lai,EPS)` shift is fixed to the runtime
  rule (`fast.jl:369`) with a `GROWTH_EFF_MAX` assertion. Per-PFT mortality params are all seven `[VERIFIED]`.
  The **global re-derivation on the `t7` generation is IN FLIGHT** — see §NEXT for the job table.
- **⚠ EVERY global S number below with a "tree5" label is on the TRUNCATED population** (ids 1–5) and is
  superseded by its `t7` counterpart, not silently restated (ADR 0031 §5).

### Population widening — measured effect (historic copula table, seed2, `[VERIFIED]` job 1622132)

| | tree5 (pre-0031) | **tree7 (t7)** |
|---|---|---|
| survivor tree stems | 133 562 549 | **197 802 377** (+48 %) |
| cells | 45 072 | **54 058** (+8 986) |
| `minwscal` span | [0.025, **0.30**] | [0.025, **0.75**] — FIT's true range (id 0's interval) |
| `growth_eff` max / mean | 1.19e9 / 264 495 | **43 138 / 146.7** (the guard; seed1 reads 31 183 / 120.6) |

Seed1 equivalents `[VERIFIED]`: historic w20 = **197 721 867 stems / 54 020 cells** (exactly ADR 0031's census),
`growth_eff` max 31 183 with **0** `lai<=0` rows — the cross-seed-join diagnosis confirmed in production.
ssp370 w20 = **828 818 873 stems / 58 683 cells** (this is what OOM-kills a 32-cpu build; use `NCPUS=96`).

### Count DRF — before/after (like-for-like, same script + hyperparameters)

| metric | tree5 | **t7** | Δ | source |
|---|---|---|---|---|
| pooled table rows (historic+ssp370, w20) | 77 636 574 | **121 495 487** | +56 % | |
| pooled cells | 53 993 | **58 587** | +4 594 | |
| pooled held-out-BY-CELL TEST R² | 0.9852 | **0.9818** | −0.0034 | 1597387 → 1622134 |
| pooled in-sample R² | 0.9852 | **0.9819** | −0.0033 | |
| pooled by-cell OOS R² / RMSE | 0.9852 / 0.702 | **0.9819 / 0.707** | −0.0033 | |
| HOLD-OUT-BY-SCENARIO R², held out historic | 0.9847 (RMSE 0.714) | **0.9816** (0.709) | −0.0031 | 1600416 → 1622134 |
| HOLD-OUT-BY-SCENARIO R², held out ssp370 | 0.9847 (RMSE 0.714) | **0.9814** (0.716) | −0.0033 | |
| historic K-fold-by-cell per-row R² / RMSE | 0.9852 / 0.702 | **0.9821 / 0.699** | −0.0031 | 1581897 → 1622305 |
| historic **per-cell-mean R²** / bias | **0.9994** / 0.005 | **0.9987** / **0.001** | −0.0007 | |
| historic cells scored | 44 328 | **53 699** | **+9 371** | the previously-invisible tropical + larch cells |

### Trait POOLED-MARGINAL fidelity — before/after (K-fold-by-cell OOS, historic, `[VERIFIED 2026-07-28]`)

Jobs 1597648 (tree5) → 1622131 (tree7), same script + hyperparameters. `nqrmse = RMSE(q05..q95) / IQR(obs)`,
so it is **spread-normalized** — and the observed IQRs moved, which the headline ratio hides. Both are shown:

| axis | nqrmse tree5 | **nqrmse tree7** | headline | IQR ×  | raw RMSE tree5 → tree7 | **real gain** |
|---|---|---|---|---|---|---|
| SLA | 0.016 | **0.006** | 2.67× | 0.89× | 3.14e-4 → 1.05e-4 | **2.99×** |
| Wooddens | 0.022 | **0.008** | 2.75× | 1.13× | 1771 → 726 | **2.44×** |
| D95max | 0.028 | **0.008** | 3.50× | 1.20× | 7.29 → 2.50 | **2.92×** |
| minwscal | 0.038 | **0.008** | 4.75× | **2.47×** | 2.73e-3 → 1.42e-3 | **1.92×** |

**The improvement is real on every axis (1.9–3.0× in absolute quantile error), but do NOT quote the headline
ratios.** For `minwscal` the 4.75× is mostly its IQR growing 2.47× (the tropical PFT's `[0.05,0.75]` interval
entering the population); the honest number is 1.9×. `SLA` is the opposite case — its IQR *shrank*, so its
headline 2.67× **understates** a real 2.99×.

**This does NOT refute or confirm ADR 0031's degradation prediction.** ADR 0031 predicted that a single pooled
marginal per axis would be a *worse structural fit* once id 0's very different trait intervals were included —
that is a statement about **between-cell composition**, which is what ADR 0030's **per-cell-median** gate
measures. The table above is the **pooled global marginal**, a strictly weaker test that is blind to whether the
right cells got the right traits. The chained job **1622436** is the test of the actual prediction; until it
reports, the trait verdict is OPEN. Plausible reason the marginal improved anyway: 48 % more stems and 20 % more
cells is more training data per marginal DRF, and the truncated set was itself an awkward mixture to fit.

**Counts survive the widening essentially intact:** every count metric moves by ≈ −0.003 R² on a 56 %-larger,
markedly more heterogeneous population (the tropical belt + Siberian larch added), and the unseen-regime
generalization gap stays flat (holdout-by-scenario is within 0.0005 of the by-cell baseline, as before). So the
truncation was **not** materially inflating the count skill — the count DRF's headline claim is robust. The
trait side is where the population change was predicted to bite (ADR 0031), and that is what the in-flight
copula + 0030 re-measurement will show.
- **Trait per-cell medians — RE-MEASURED on `tree7` (`[VERIFIED 2026-07-28]`, ADR 0030 gate, job 1622436).**
  **Gate PASSED: `seed1-basis` = 1.000 on all four axes** (requirement ≥0.99), 52 165 cells scored (was
  36 228). Each population measured against its OWN floor and ceiling, which is what makes the columns
  comparable across a population change (ADR 0030 §4):

  | axis | emu_r | floor (rel_Y) | ceiling | **GAP** | r_center | sd(pred)/sd(Y1) |
  |---|---|---|---|---|---|---|
  | SLA | 0.866 → **0.885** | 0.964 → 0.973 | 0.981 → 0.986 | +0.115 → **+0.101** | 0.883 → **0.898** | 0.946 → 0.911 |
  | Wooddens | **0.567 → 0.807** | 0.694 → 0.937 | 0.794 → 0.965 | +0.226 → **+0.157** | 0.715 → **0.837** | **0.546 → 0.718** |
  | D95max | 0.771 → **0.812** | 0.791 → 0.833 | 0.873 → 0.909 | +0.102 → **+0.098** | 0.883 → **0.893** | 0.732 → 0.742 |
  | minwscal | **0.793 → 0.947** | 0.909 → 0.973 | 0.947 → 0.986 | +0.153 → **+0.039** | 0.838 → **0.960** | **0.736 → 0.970** |

  **ADR 0031's degradation prediction is FALSIFIED — see ADR 0033.** It expected a single pooled marginal to fit
  *worse* once id 0's very different trait intervals entered. Instead per-cell skill improved on **every** axis,
  and **most on the two that were worst**: Wooddens `emu_r` 0.567 → 0.807 and minwscal +0.153 → **+0.039 (near
  ceiling)**. The mechanism: the truncation was *destroying* composition signal, not hiding a need for per-PFT
  structure — the tropical belt is environmentally distinct (hot, wet, frost-free) AND carries id 0's distinct
  intervals, so with it present the environment↔composition link the copula conditions on is much *stronger*.
  So the "missing between-cell composition signal" diagnosis was largely an artifact of the truncated basis.
- Split-half 0.992–0.999 vs a floor of 0.833–0.973 ⇒ the floor remains **trajectory divergence**, not
  finite-stem noise. `rel_P` (0.993–0.999) still exceeds `rel_Y`, so the raw floor−emu gaps stay lower bounds.
- **The cross-population `tree5` row is the truncation's size, not a gap** — its `seed1-basis` reads
  0.976 / 0.556 / 0.814 / **0.174**, i.e. the script's own ≥0.99 guard correctly refuses it. That is the
  mechanism that made the pre-S1 numbers unreadable, now reproduced deliberately as a control.
- Seed2 floor artifact: `/p/tmp/jamirp/emulator_global/slow_copula_historic_seed2` (133 562 549 stems / 45 072
  cells; rebuild in ~70 s).
- Artifacts: `*_pooled_w20.{drf,rcop}` on `/p/tmp` (DVC); the committed `.drf`/`.rcop` are the Hainich demo.
- The online transient boundary (`src/climbuf.jl`, ADR 0027) is BUILT and offline-parity verified.

## Milestones

- **S1** Basis-clean noise floor → exact per-axis headroom. **DONE 2026-07-28 (ADR 0030)** — gate met
  (`seed1-basis` 1.000 ×4), headroom table in §Status, and it is what uncovered S1b.
- **S1b** **Widen the training population to FIT's complete tree set (ADR 0031).** Code + gates + docs **DONE
  2026-07-28**; the global re-derivation / re-validation / 0030 re-measurement is **IN FLIGHT** (§NEXT).
  Blocks S2. Side outcomes: the `lai==0` seed asymmetry is diagnosed (cross-seed feature join), all seven PFTs'
  mortality params are `[VERIFIED]` (ids 1/2/4/5 were also wrong, not just the two new ones), and the byte-identity
  gate exists as `scripts/verify_hainich_demo_artifacts.sh` + `scripts/diagnose_slow_table_drift.py`.
- **S1c** **Regenerate the committed Hainich demo `.drf` + `.rcop` onto ONE feature basis (ADR 0032).** The
  committed `.drf` is on the RETIRED PROXY features (`soilmoist` 0.7, `lai` 21.2, `growth_eff` 19) while the
  `.rcop` beside it is on the REAL ones (0.85, 3.07, ~151) — one emulator, two conditioning bases, a live
  ADR-0023 shift masked by the DRF's OOD leaf-clamping. **Proven independent of S1b** (control build agrees to
  max|abs diff| = 0 on all 15 columns). Regenerate BOTH from one table build; **re-measure** the
  `slow_production_drf_tests.jl` + `slow_oracle_tests.jl` drift thresholds and document the move
  (`residual-diagnosis`) — never widen them silently. **Integration point with M**; do NOT fold into another
  milestone (that is exactly what ADR 0031 §3 forbids).
- **S2** **Close the trait headroom.** Expand the copula conditioning — `COPULA_COND_COLS` in
  `scripts/build_slow_runtime_table.py` **and** `live_flux_cond` in `src/components/slow.jl` **in lockstep** —
  with environment / PFT-composition covariates; global K-fold re-fit (`run_pooled_slow_copula.sh`); measure
  against the **re-measured** ADR-0030 gate. **Needs an ADR (0032) + an integration point with M** (artifact
  version bump). *Gate (ADR 0030 §4, replacing "r ≥ 0.75"):* close ≥50 % of the Wooddens GAP to the ceiling
  **and** lift `sd(pred)/sd(Y1)` to ≥0.75 on that axis, with pooled KS not degraded (≤0.02) and no other axis
  losing >0.01 of `r_center`. Report honestly if the conditioning does not deliver.
  **⚠ S1b already delivered a large share of this gate WITHOUT touching the conditioning (ADR 0033):** the
  Wooddens GAP closed 0.226 → 0.157 (**30 % of the way**, target 50 %) and `sd(pred)/sd(Y1)` went 0.546 →
  **0.718** (target ≥0.75 — nearly met), pooled nqrmse improved rather than degraded, and no axis lost
  `r_center`. So **re-baseline the S2 gate against the `tree7` numbers before starting**, or S2 will take credit
  for the population fix. The honest remaining target is the last ~20 % of the Wooddens GAP; minwscal (+0.039)
  and D95max/SLA (+0.098/+0.101, both `r_center` ≈ 0.89) have little left to win.
- **S3** Per-PFT / mixture copula. **DE-PRIORITIZED back to a fallback (ADR 0033 — reverses ADR 0031).** The
  argument for promoting it was that the copula predicted only 0.55 of the true between-cell Wooddens spread and
  had no composition covariate. On the complete population that dispersion ratio is **0.718** and `r_center`
  0.837 without any structural change, and minwscal went to near-ceiling — so the pooled marginal *does* capture
  composition once it can see the whole forest. Revisit only if S2's conditioning stalls above ~0.75 dispersion.
- **S4** **Grass ownership** (open risk #8): S owns grass demography; today grass stays F-side and S is
  TREE-only. Needs an ADR + a carbon-conservation gate for grass at the handoff.
- **S5** Whole-cohort **DROP** + the Gate-3 recursive drift (nqrmse 0.39 vs the documented 0.45 alarm).
- **S6** The **in-loop** OOD win — the offline 2.35× is `[VERIFIED]` (`flux_ood_experiment.jl`); the in-loop
  (recursive, coupled) OOD advantage is not yet demonstrated. Coordinate with M for the coupled harness.

## Line-local gotchas

- **`age_mean` is the classic train/inference-shift trap** — train it as the nind-weighted mean cohort age
  (`mean(Age−1)`, start-of-year), NOT the elapsed-year counter (ADR 0024 supersedes 0023 §3).
- Never rename/clobber `test/testitems/references/drf_forest_hainich.drf` (+ `_meta.txt`) or
  `recruit_copula_hainich.rcop` — they are committed golden fixtures with bitwise round-trip tests.
- `*.drf`/`*.rcop` are **text** artifacts; `*.bin` is gitignored (writing one silently loses it).
- Diagnostic scripts must be `*_probe.jl` / `*_diagnosis.jl` / `*_decomp.jl` — a stray `*_test.jl` in
  `scripts/` fails the WHOLE suite at ReTestItems collection (and would red every other line).
- Read `.claude/skills/slow-drf-pipeline/SKILL.md` before touching the pipeline; it names every artifact.
