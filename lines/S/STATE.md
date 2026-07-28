# LINE S — Component-S science (branch `line/S`, worktree `wt-S`)

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/S/JOURNAL.md` (append-only). Decisions: ADR block **0030–0049**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here

**S1b — widen the training population to FIT's COMPLETE tree set (ADR 0031). This now BLOCKS S2.**
S1 is DONE (see §Status) and it uncovered a defect that makes S2 premature: every `build_slow_*.py` filters
`TREE_TYPES=[1,2,3,4,5]`, but `Type` is the 0-based `pftpar` index and **ids 0–6 are all seven tree PFTs**, so
we drop id 0 (tropical broadleaved evergreen) + id 6 (boreal larch) = **32.5 % of 197.7 M survivor tree stems**,
and **9 011 of 54 020 tree-bearing cells (16.7 %) are invisible to Component S** — the tropical belt and the
Siberian larch zone. Read **ADR 0031** (full census, provenance, ordered plan) and **ADR 0030** (the gate you
re-measure at the end) first. Census reproducer: `scripts/diagnose_ind_type_composition.py` (~2 min).

Order matters — do NOT publish anything from a mixed-basis state:
1. **One imported constant.** Correct `python/src/lpjmlfit_emulator/data.py::TREE_TYPES` and
   `python/config/config.yaml` to `[0..6]`, and replace the hard-coded copies in
   `scripts/build_slow_{runtime_table,count_table,flux_table,oracle_reference}.py` with an import so they can
   never drift again (each site currently carries an ADR-0031 pointer comment). Watch
   `build_slow_flux_table.py::PFT_PARAMS` — it assumes TEMPERATE mortality params for every id, so ids 0/6
   need their own from `par/pft_lpjmlfit.js`, not just a longer key list.
2. **Add the `lai == 0` guard FIRST** (also ADR 0031): `growth_eff = applied_npp/max(lai,EPS)` divides by
   `EPS=1e-6` where the joined `LAI_STAND` is exactly 0 (**202 106 of 1 348 400** historic cell-years,
   verified). Measured (`/p/tmp/jamirp/emulator_global/probe_growth_eff_lai0.py`, job 1617052): the seed1
   **production table is CLEAN** (max 31 183, zero rows >1e6 ⇒ no published number is affected), but the seed2
   table has **204 867 rows (0.15 %) >1e6, max 1.19e9**. That asymmetry is **unexplained** — same lai table
   both times; falsify this first: the rows may exist in both but with `applied_npp == 0` in seed1, where
   `0/EPS = 0` hides them. The coverage guards CANNOT catch any of it (the feature tables are complete, so a
   zero is *present*, not missing). Add an explicit `lai > 0` guard + a `growth_eff` max assertion. ADR 0030's
   floor is unaffected either way (it reads `Y` only, never `Xc`).
3. **Re-derive → retrain → re-validate:** count + copula tables (historic, ssp370, pooled) →
   `run_global_slow_{training,copula}.sh` → K-fold-by-cell OOS + hold-out-by-scenario → figures.
   **Version, never overwrite** (`…_t7.drf` / `…_t7.rcop` or a meta version bump): line M pins these, so this
   is an **integration point** — note it in `lines/M/STATE.md` as well and land both sides together.
4. **Re-measure the ADR-0030 gate:** `TIME=01:00:00 NCPUS=32 scripts/sbatch_python.sh S-noisefloor
   scripts/noise_floor_vs_emulator.py`, after building a SEED=2 copula table on the NEW population
   (`MODE=copula SCENARIO=historic SEED=2 OUT=…_seed2`, ~70 s — and note `sbatch_python.sh` now forwards
   `MODE`/`SCENARIO`/`STEM_CAP`/`BOUNDARY_WINDOW`, which it silently did NOT before). The floor moves to the
   `tree7` numbers (Wooddens 0.694 → 0.923), so every headroom figure in §Status is superseded by that run.

*Gate:* Hainich demo artifacts + golden fixtures **byte-identical** (Hainich has only ids 1–5 — if they move,
STOP and find out why); `seed1-basis ≥ 0.99` on the new population; cell coverage ≈ 54 020; and a documented
before/after table of every fidelity number that changed.

Then → **S2/S3** (below). ADR 0031's census makes **S3 the leading hypothesis, not S2**: per-cell trait
medians are *composition* statistics (FIT samples traits from per-PFT intervals), and the copula has neither a
composition covariate nor a per-PFT marginal.

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
- **⚠ The training population is TRUNCATED — ADR 0031 (found 2026-07-28, S1's main outcome).** Every global S
  number above and below is on ids 1–5 / **45 009** of 54 020 tree cells: id 0 (tropical broadleaved evergreen)
  and id 6 (larch) are dropped = 32.5 % of survivor tree stems, 16.7 % of tree cells invisible. Not a decision
  — a stale-yaml port defect. **S1b fixes it and everything below must then be re-measured.**
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
- **S1b** **Widen the training population to FIT's complete tree set (ADR 0031).** *(NEXT, above.)* Blocks S2.
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
