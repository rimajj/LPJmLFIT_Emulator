# LINE M — multi-cell coupled S+F+E (branch `line/M`, worktree `wt-M`) — P3

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/M/JOURNAL.md` (append-only). Decisions: ADR block **0050–0069**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here

**M1 — per-cell input provisioning (the actual blocker; everything else in this line waits on it).**
The coupled driver is already N-cell-agnostic — `run_coupled_cell(core, clo, state, forcings; …)` takes a
per-cell `FDiffFastCore` + latitude. What is missing is per-cell **inputs**: today all five biome cells reuse
**Hainich's** soil column and **Hainich's** individuals, and the driver runs `slow=nothing`.

Start with the one piece that has no script at all — a **per-cell soil-column extractor** producing the same
3-column layout as `test/testitems/references/hainich_soilcolumn.txt`
(`layer soildepth_mm whcs_mm rootdist`):
- `whcs_mm` = per-layer plant-available capacity = `whc_nat`(fraction) × `soildepth`(mm). Sources per
  `config/paths.yaml`: `soil_code_test.soil.bin`, `soil_depth_test.clm`, and the C run's own `whc_nat` output.
  (`grep -rl whc_nat scripts/` → nothing exists yet.)
- `rootdist` = Jackson-1996 beta profile from D95 — **vegetation-dependent**, so co-derive it per cell.
*Gate:* re-extracting cell **42490** reproduces the committed `hainich_soilcolumn.txt` to round-off — that is
the correctness proof before trusting any other cell.

Then the rest of M1: generalize `scripts/extract_fdiff_individuals*.py` to an arbitrary cell; plumb latitude
from `grid.nc` (`cell_latlon()` already exists in `scripts/extract_biome_forcing.py`); replace the hard-coded
`BIOMES` dict with an N-cell list; large fixtures → `/p/tmp` (keep the committed set small).

## Scope + ownership (ADR 0029)

**You own (exclusive):**
- **`src/run.jl`, `src/interface.jl`** — the coupling seam. Other lines request changes here through you.
- `scripts/{run_coupled_biomes.jl,extract_biome_forcing.py}` + the new per-cell extractors
- `test/testitems/{biome_coupled,coupled_run,resilience_battery,rollout_stability}_tests.jl`
- `lines/M/*`, `changelog.d/M-*.md`, ADRs 0050–0069

**Do NOT touch:** `src/components/slow.jl`, `src/drf.jl`, `src/climbuf.jl` (line S) ·
`src/components/energy.jl` (line E) · `ext/` (line O) · `Project.toml` (integrator).
Shared, additive-only: `src/LPJmLFITEmulator.jl` (inside `# ── line M ──`), `CLAUDE.md`, `MEMORY.md`.

**SLURM tag prefix:** `M-` · other lines' `/p/tmp` artifacts are **read-only**.

## The contracts you consume (frozen — do not edit the other side)

- **From S:** `FluxDrivenSlowEmulator(fc, forest; boundary=, boundary_series=, n_init=, age0=, k_cap=,
  recruit_copula=, seed=)`, the `flux_feature_vector` order, `live_flux_cond`, the `.drf`/`.rcop` format, the
  `cell_meta.parquet` schema. **Pin a specific versioned artifact path** in your driver; if S needs to change
  the feature contract it is an integration point (both sides land together) — never adopt a re-trained
  artifact silently, because train/inference consistency is load-bearing (ADR 0023).
- **From E:** the `SEBEnergyClosure(...)` constructor + `solve!` signature.
- `src/climbuf.jl` (`ClimBuf`, line S) is consumed via the `climbuf=` kwarg you already own in `run.jl`.

## Status (2026-07-28)

- `run_coupled_cell` runs the full S+F+E daily loop for **one** cell; carbon conserves at the S↔F handoff to
  ~1e-12 gC, energy closes to ~1e-14 W/m², and the opt-in `climbuf=` refreshes S's transient boundary.
- `test/testitems/biome_coupled_tests.jl` drives **5 biome cells** (boreal/temperate/mediterranean/semi-arid/
  tropical) with real GSWP3-W5E5 forcing — energy closes in every climate and the Bowen ordering is
  climate-correct — but with **`slow=nothing`** and a **common Hainich canopy + Hainich soil**, deliberately,
  to isolate the climate effect.
- So: **F+E generalize across biomes; the coupled S does not run multi-cell yet.** The global evidence for S
  is offline (line S), not coupled.
- Resilience battery is scaffold only: 3 `@test_skip false` in `resilience_battery_tests.jl` + 1 in
  `rollout_stability_tests.jl` (the `lag1_autocorr` estimator itself is real and tested).

## Milestones

- **M1** Per-cell input provisioning. *(NEXT, above)*
- **M2** **Wire the flux-driven S into the multi-cell driver**: the global pooled `.drf`/`.rcop` (pinned
  version), a per-cell `ClimBuf`, and per-cell `n_init`/`age0`/boundary from `cell_meta.parquet`.
  *Gate:* carbon ≤1e-6·C_scale **and** energy ≤1e-6 W/m² in **every** cell, deterministic under seed,
  `slow=nothing` still byte-identical.
- **M3** **Coupled multi-cell validation vs the C truth** — per-cell demography + trait distributions against
  the annual `ind` parquet, scored against the seed1-vs-seed2 noise floor (reuse
  `scripts/noise_floor_vs_emulator.py`, line S's script — read-only). **This is the P3 gate.** Report per-cell
  error vs floor, and held-out **cells and scenarios**.
- **M4** **Resilience battery** — fill the 4 stubs: (a) lag-1 autocorrelation vs climate (the documented
  ~0.2-wet → ~0.75-dry gradient), (b) recovery/restoring rate from a pool-perturbation experiment,
  (c) the **shuffle test** (S0 vs S1 — proves the memory is genuinely internal, not inherited from
  autocorrelated climate; an AR emulator can cheat this, so it is mandatory), (d) the long-horizon AC-gap /
  oscillation check in `rollout_stability_tests.jl`. **Reimplement from Bathiany et al. 2024
  (doi:10.1111/gcb.17613) — LPJ_resilience has NO license, so its code must not be copied.** Also resolve the
  live inconsistency: MEMORY/STEERING place this in P3, the test comments say "Phase 6".
- **M5** Biome-calibrated PFT params + spin-up (today every biome runs beech ANGIO params from
  `par/pft_lpjmlfit.js`).
- **M6** Provide the coupled multi-cell harness line O needs for O5 (online multi-cell).

## Line-local gotchas

- **Hainich is `42490` in the global orderA grid** — `28008` is Sonoran desert there (it is Hainich only in the
  repo's `-DSINGLESITE` grid). Every per-cell extractor must use the orderA index.
- `.clm` readers must **parse the header** (v3 float32 HDR=51 vs v2 int16 HDR=43 with `scalar 0.1` ⇒ °C×10) —
  never assume float32/HDR=51. Reuse `scripts/build_transient_boundary.py::open_clm`.
- Committed fixtures under `test/testitems/references/` are **shared** — new ones take an `M`-ish/cell-specific
  name; **regenerating an existing baseline is an integration point** (guardrail 4: opt-in, default
  byte-identical).
- The 5-biome test uses a bounded negative-LE tolerance (`@test all(≥(-2.0), out.le)`) for the smooth-min
  undershoot in the fully-depleted Sahel corner — keep that reasoning if you touch the assertions.
