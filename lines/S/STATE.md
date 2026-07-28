# LINE S — Component-S science (branch `line/S`, worktree `wt-S`)

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/S/JOURNAL.md` (append-only). Decisions: ADR block **0030–0049**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here

**S1b is CODE-COMPLETE and MERGED; finish the TRAIT half of the re-validation.** The ADR-0031 widening, the
`growth_eff` runtime guard, the per-PFT params, the versioning knob and the byte-identity gate all landed
(see §Status for the before/after tables). **The count side is DONE and holds up** (every metric within ≈0.003 R²
on a 56 %-larger population, +9 371 cells scored). What is left is the trait side, which is exactly where
ADR 0031 predicted the population change would bite.

### 1. Collect the in-flight jobs (they were running when the session ended)

| job | tag / log | produces | status at handoff |
|---|---|---|---|
| 1622131 | `logs/gcopula_historic_t7.*` | `slow_copula_historic_t7/` (197.8 M stems) + `pred_<axis>.f64` K-fold OOS + `recruit_copula_global_historic_t7.rcop` | RUNNING (K-fold, ~5 folds × 4 axes) |
| 1622330 | `logs/gpcop_slow_t7.*` | `slow_copula_pooled_w20_t7/` + **`recruit_copula_global_pooled_w20_t7.rcop`** (the artifact M pins) | RUNNING |

`grep -E 'JOB DONE|VERDICT' logs/<tag>.*.out`; last line carries the exit code. **If either died on a node
fault** (exit `0:53`/no log — see MEMORY.md) just resubmit: `VERSION=t7 SCENARIO=historic
scripts/run_global_slow_copula.sh` / `VERSION=t7 scripts/run_pooled_slow_copula.sh`. Everything is versioned,
so a resubmit cannot clobber a pre-0031 artifact.

### 2. Re-measure the ADR-0030 trait gate on the new population

Both halves must be `tree7`. The seed2 floor table is **already built** (job 1622132,
`slow_copula_historic_seed2_t7`, 197.8 M stems / 54 058 cells):
```bash
COPULA_DIR=/p/tmp/jamirp/emulator_global/slow_copula_historic_t7 \
COPULA2_DIR=/p/tmp/jamirp/emulator_global/slow_copula_historic_seed2_t7 \
  TIME=02:00:00 NCPUS=32 scripts/sbatch_python.sh S-noisefloor-t7 scripts/noise_floor_vs_emulator.py
```
The script now derives which of its `tree7`/`tree5` bases is `same_population` from the **imported**
`TREE_TYPES`, so `tree7` is the basis carrying the quotable GAP and `tree5` is the cross-population
before/after row. **Gate: `seed1-basis ≥ 0.99` on `tree7`** — below that, STOP (`residual-diagnosis` §3b).
Expect the floor to move to the `tree7` numbers (ADR 0031 predicted Wooddens 0.694 → ~0.923), so **every
headroom figure in §Status's trait table is superseded by this run** — replace it, don't append.

### 3. Trait figures + the before/after trait table

`COPULA_OUT=/p/tmp/jamirp/emulator_global/slow_copula_historic_t7` → figs 09–11 + `metrics_traits.txt`
(see the `emulator-validation-figures` skill). Then extend §Status with a trait before/after table in the same
shape as the count one. Pooled marginal KS was **0.004–0.015** on tree5 — ADR 0031 expects it to WORSEN, because
one pooled marginal per axis is a poorer structural fit once id 0's very different trait intervals are in
(`minwscal` now spans `[0.025, 0.75]`, not `[0.025, 0.30]`). **Report that honestly if it happens** — it is
evidence FOR S3, not a regression to hide.

### 4. Hand the artifacts to M, then unblock S2/S3

`lines/M/STATE.md` already carries the integration point. Once the pooled `.rcop` exists, tell M the `t7` pair
is complete (`drf_forest_global_pooled_w20_t7.drf` is **already built + validated**) so M re-pins deliberately.

Then → **S2/S3**. ADR 0031's census plus the count/trait asymmetry make **S3 the leading hypothesis, not S2**:
per-cell trait medians are *composition* statistics (FIT samples traits from per-PFT `[low,high]` intervals),
the copula has neither a composition covariate nor a per-PFT marginal, and the widening just made the
composition spread much larger. Consider running S3 *with* S2 rather than after it.

**Also open, independent of the above: S1c (ADR 0032)** — the committed Hainich demo `.drf` is on the retired
PROXY feature basis while the `.rcop` beside it is on the REAL one. Don't fold it into S2/S3; it needs
re-measured drift thresholds and a joint landing with M. `scripts/verify_hainich_demo_artifacts.sh` reports
exit 2 (`STALE-FIXTURE`) until it is done — that is **expected**, not a new failure.

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

**Counts survive the widening essentially intact:** every count metric moves by ≈ −0.003 R² on a 56 %-larger,
markedly more heterogeneous population (the tropical belt + Siberian larch added), and the unseen-regime
generalization gap stays flat (holdout-by-scenario is within 0.0005 of the by-cell baseline, as before). So the
truncation was **not** materially inflating the count skill — the count DRF's headline claim is robust. The
trait side is where the population change was predicted to bite (ADR 0031), and that is what the in-flight
copula + 0030 re-measurement will show.
- **The open gap — trait per-cell medians, now EXACT (`[VERIFIED 2026-07-28]`, ADR 0030, job 1617055;
  ids-1..5 population).** Both sides on the copula basis (`seed1-basis` = **1.000** on all 4 axes ⇒
  apples-to-apples; the pre-S1 0.49/0.09 cross-checks were the truncation, not "median instability"):

  | axis | emu_r | floor (rel_Y) | rel_P | ceiling √(rel_P·rel_Y) | **GAP** | r_center | sd(pred)/sd(Y1) |
  |---|---|---|---|---|---|---|---|
  | SLA | 0.866 | 0.964 | 0.997 | 0.981 | **+0.115** | 0.883 | 0.946 |
  | Wooddens | 0.567 | 0.694 | 0.907 | 0.794 | **+0.226** | 0.715 | **0.546** |
  | D95max | 0.771 | 0.791 | 0.962 | 0.873 | **+0.102** | 0.883 | 0.732 |
  | minwscal | 0.793 | 0.909 | 0.986 | 0.947 | **+0.153** | 0.838 | 0.736 |

  Every axis has real headroom (D95max was NOT "at floor" — the raw floor−emu gap of +0.021 is a lower bound;
  `floor_r` is a realization-vs-realization r, not a predictor ceiling). Split-half 0.978–0.999 vs a floor of
  0.694–0.964 ⇒ the floor is **trajectory divergence**, not finite-stem noise. The copula reproduces only
  **0.55** of the true between-cell Wooddens spread (a second seed reproduces 1.00) ⇒ it regresses cells toward
  the global mean: missing between-cell *composition* signal, exactly as ADR 0025's caveat predicted.
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
- **S3** Per-PFT / mixture copula. **Now the LEADING hypothesis, not a fallback** (ADR 0031): FIT draws traits
  from per-PFT `[low,high]` intervals, so a per-cell trait median is a *composition* statistic — and the copula
  has neither a composition covariate nor a per-PFT marginal, while predicting only 0.55 of the true
  between-cell Wooddens spread. Consider running S3 *with* S2 rather than after it.
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
