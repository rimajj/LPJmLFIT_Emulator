# LINE S — Component-S science (branch `line/S`, worktree `wt-S`)

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/S/JOURNAL.md` (append-only). Decisions: ADR block **0030–0049**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here

**S1 — basis-clean noise floor (do this first; cheap, high information).**
Rebuild the **seed2** copula table so the per-axis trait headroom becomes an exact number instead of a
qualitative one:
```bash
# in wt-S, per the slow-drf-pipeline skill; writes a SEPARATE dir (never clobber seed1)
MODE=copula SEED=2 BOUNDARY_WINDOW=20 STEM_CAP=400 \
  OUT=/p/tmp/jamirp/emulator_global/slow_copula_historic_seed2 \
  scripts/sbatch_python.sh S-copula2 scripts/build_slow_runtime_table.py
```
Then extend `scripts/noise_floor_vs_emulator.py` to read the seed2 **copula-table** basis (instead of the
all-years parquet median) so the `seed1-basis` cross-check clears >0.9 on all four axes.
**Why:** today that cross-check is 0.97 (SLA) but **0.49 (Wooddens) / 0.09 (minwscal)** — those two axes'
floor-vs-emulator gap is only qualitative, so S2's success metric isn't yet exactly measurable.
*Gate:* `seed1-basis` r > 0.9 for all 4 axes; report the exact per-axis emulator-vs-floor gap.

Then → **S2** (the big one, below).

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
- **GLOBAL offline validation** (K-fold-BY-CELL, 45009 cells, real features): counts per-cell-mean
  **r²=0.9994**, held-out-BY-SCENARIO **R²=0.9847**; trait pooled marginals KS **0.004–0.015**.
- **The open gap — trait per-cell medians.** `[VERIFIED 2026-07-27]` per-cell-median Pearson r:
  SLA **0.87** · minwscal **0.78** · D95max **0.74** · **Wooddens 0.52**; the seed1-vs-seed2 **noise floor is
  0.90–0.97** ⇒ the signal is **learnable, not RNG-limited** ⇒ genuine model headroom. Cause (not a bug): the
  copula conditions on flux+boundary and *deliberately excludes stand-state* (ADR 0025), which
  under-determines PFT/biome-composition-driven axes (wood density most).
- Artifacts: `*_pooled_w20.{drf,rcop}` on `/p/tmp` (DVC); the committed `.drf`/`.rcop` are the Hainich demo.
- The online transient boundary (`src/climbuf.jl`, ADR 0027) is BUILT and offline-parity verified.

## Milestones

- **S1** Basis-clean noise floor → exact per-axis headroom. *(NEXT, above)*
- **S2** **Close the trait headroom.** Expand the copula conditioning — `COPULA_COND_COLS` in
  `scripts/build_slow_runtime_table.py` **and** `live_flux_cond` in `src/components/slow.jl` **in lockstep** —
  with environment / PFT-composition covariates; global K-fold re-fit (`run_pooled_slow_copula.sh`); measure
  the per-cell-median r recovered against the S1 floor. **Needs an ADR (0030) + an integration point with M**
  (artifact version bump). *Gate:* Wooddens per-cell-median r materially up (target ≥0.75) with pooled KS not
  degraded (≤0.02); report honestly if the conditioning does not deliver.
- **S3** Per-PFT / mixture copula, if S2 under-delivers — wood density is set by PFT composition, so a
  per-PFT-mixture marginal may be the right structure rather than more covariates.
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
