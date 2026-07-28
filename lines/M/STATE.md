# LINE M — multi-cell coupled S+F+E (branch `line/M`, worktree `wt-M`) — P3

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/M/JOURNAL.md` (append-only). Decisions: ADR block **0050–0069**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here

**M1 is DONE (2026-07-28, ADR 0050).** Every biome cell now runs its OWN soil column, canopy, forcing and
latitude; both extractors are committed and gated (the soil-column extractor reproduces the committed
`hainich_soilcolumn.txt` **byte-identically**). To add a cell, use the **`provision-coupled-cell`** skill —
do not re-derive the procedure.

**M2 — wire the flux-driven Component S into the multi-cell driver.** The next blocker: the driver still runs
`slow=nothing`, so the coupled evidence for S is offline-only (line S), not coupled.

1. **Pin a versioned S artifact** (frozen S→M contract — never adopt a re-trained artifact silently, ADR 0023).
   Candidates on `/p/tmp/jamirp/emulator_global/` (read-only to this line):
   `drf_forest_global_pooled_w20.drf` + `recruit_copula_global_pooled_w20.rcop` (newest, 2026-07-27, pooled
   historic+ssp) vs `drf_forest_global_historic.drf` + `recruit_copula_global_historic.rcop`. Read the
   `*_meta.txt` beside each, confirm the `flux_feature_vector` order it was trained on matches
   `src/components/slow.jl`'s runtime order, and record the chosen path + its sha **in this file**. A mismatch
   is an integration point with line S, not a local fix.
2. **Per-cell S initial state** from `/p/tmp/jamirp/emulator_global/slow_runtime_historic/cell_meta.parquet`
   (schema `Cell, n_init, age0, eco_diag_gdd_5, tas_cold_month, soil_depth, co2, n_rows`; 44,328 cells; all
   five biome cells present — Hainich = `n_init 11, age0 43.56`). Fold these columns into
   `references/M_cells.csv` (extend `scripts/extract_cell_individuals.py` or add a sibling) so the driver reads
   one table. **`age_mean` is a runtime elapsed-year counter, not mean `Age`** — the train/inference-shift trap.
3. **Per-cell `ClimBuf`** through the `climbuf=` kwarg `src/run.jl` already owns.
4. *Gate:* carbon ≤1e-6·C_scale **and** energy ≤1e-6 W/m² in **every** cell, deterministic under seed, and
   **`slow=nothing` still byte-identical** (guardrail 4). Add it as a third test item in
   `test/testitems/biome_coupled_tests.jl` beside the two that are there now.

**Cheap win available while doing M2:** the four new single-cell C runs
`/p/tmp/jamirp/esm_land_daily/daily_2000_2019_M_biome_val_c{52059,33335,18371,12045}_seed1` also carry
`a_lai_stand` / `a_fpc_stand` / `d_gpp` / `d_transp` / `d_swc` / `d_fapar` — i.e. a **per-cell F_diff-vs-C
oracle for four new biomes**, the raw material for M3's per-cell validation with no new HPC run.

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
- **From E — OPEN INTEGRATION POINT raised 2026-07-28 (line E milestone E5, ADR 0071):** real daily
  **wind + surface pressure** now exist for the 5 orderA biome cells —
  `test/testitems/references/wind_psurf_<biome>.csv` (`year,doy,wind,psurf`, 2010–2019 × 365 d, obsclim
  GSWP3-W5E5, mapping proven by a `tas` round-trip). The coupled driver still builds `AtmForcing` with a
  CONSTANT wind and a fixed psurf, and `src/run.jl` is **yours** — so wiring these in is an M-side change
  E cannot make. Expect the coupled Hainich/biome baselines to MOVE when it lands (deliberate, not a
  regression): Bowen and the 2018-drought numbers are wind-sensitive. Land it with E (see
  `lines/E/STATE.md` E5).
- **From E — SECOND OPEN INTEGRATION POINT raised 2026-07-28 (line E milestone E3):** the
  **sublimation-λ split** cannot be done inside `energy.jl`. `src/components/fast.jl:236` forms
  `le = et/86400 · LAMBDA_VAPORIZATION` from `et = transp + evap + interc` — one λ for everything, and
  that ET sum has no snow/ice component to split; `FToE` carries no snow mass or snow fraction, so E
  cannot see which part of `le` left snow. Both files are **yours** (F core + the seam). Doing it right
  needs F to partition ET into a snow/ice part and either a new `FToE` field or the λ choice applied next
  to the partition (`conservation.jl::latent_heat(et; sublimation)` already exists for it). Opt-in,
  default byte-identical (guardrail 4). E will not attempt it alone — guessing a snow fraction inside E
  would be invented physics.
- `src/climbuf.jl` (`ClimBuf`, line S) is consumed via the `climbuf=` kwarg you already own in `run.jl`.

## Status (2026-07-28)

- `run_coupled_cell` runs the full S+F+E daily loop for **one** cell; carbon conserves at the S↔F handoff to
  ~1e-12 gC, energy closes to ~1e-14 W/m², and the opt-in `climbuf=` refreshes S's transient boundary.
- `test/testitems/biome_coupled_tests.jl` drives **5 biome cells** (boreal/temperate/mediterranean/semi-arid/
  tropical) with real GSWP3-W5E5 forcing — energy closes in every climate and the Bowen ordering is
  climate-correct — and since **M1 (ADR 0050)** each cell runs its **own soil column + own canopy + own
  latitude** (`references/M_soilcolumn_<name>.txt`, `M_individuals_<name>_2010.csv`, `M_cells.csv`), no longer a
  common Hainich patch. Still **`slow=nothing`**.
- **M1 evidence:** soil-column extractor gate = byte-identical reproduction of the committed
  `hainich_soilcolumn.txt` (`max|Δwhcs| 3.7e-5 mm`); emergent top-1 m root fraction 99.3 % (Sahel) → 53.2 %
  (Amazon), effective D95 72 → 690 cm; vegetation+soil effect vs the legacy common canopy = **+10.8 W/m² LE**
  (Amazon), **−7.6** (Sahel), mediterranean Bowen **1.27 → 0.65**; energy still closes ≤2.8e-14 W/m² everywhere.
  Suite 106,987 pass / 0 fail / 4 broken.
- **New oracle data this line owns (read-only to others):**
  `/p/tmp/jamirp/esm_land_daily/daily_2000_2019_M_biome_val_c{52059,33335,18371,12045}_seed1` — single-cell
  daily re-runs of the four non-Hainich biome cells with `d_fapar` + `a_lai_stand` + `a_fpc_stand` +
  per-cell `whc_nat`. Water-closure checked (multi-year fractional imbalance ≤3.5 %).
- So: **F+E generalize across biomes with per-cell vegetation; the coupled S does not run multi-cell yet.** The
  global evidence for S is offline (line S), not coupled.
- Resilience battery is scaffold only: 3 `@test_skip false` in `resilience_battery_tests.jl` + 1 in
  `rollout_stability_tests.jl` (the `lag1_autocorr` estimator itself is real and tested).

## Milestones

- **M1** Per-cell input provisioning. **DONE 2026-07-28** (ADR 0050; skill `provision-coupled-cell`).
- **M2** **Wire the flux-driven S into the multi-cell driver**: the global pooled `.drf`/`.rcop` (pinned
  version), a per-cell `ClimBuf`, and per-cell `n_init`/`age0`/boundary from `cell_meta.parquet`.
  *Gate:* carbon ≤1e-6·C_scale **and** energy ≤1e-6 W/m² in **every** cell, deterministic under seed,
  `slow=nothing` still byte-identical. *(NEXT, above)*
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
- **Per-cell inputs come from the cell's OWN single-cell C run, not the global one** (ADR 0050): `whc_nat`
  differs between the 512-task global run and a single-cell re-run by up to 1.6e-4 relative in layer 0 under
  `-DPERMUTE`, which is 40× the fixture print resolution. `WHC_SRC=percell` is the default for that reason.
- **A `rootdist` that does not sum to 1 is silently physical**, not an error: F_diff's water supply scales
  linearly with `sum(rootdist)` (`src/fdiff.jl:846,928`) and `stand_structure_tof`'s D95 loop
  (`src/run.jl:65`) never terminates below 0.95. `hainich_soilcolumn` validates none of this — the extractor
  and `biome_coupled_tests.jl` do.
- **Never hard-code the repo root in a script** — it writes into the integrator worktree from here
  (CLAUDE.md §9 item 6). Derive it from `__file__` / `@__FILE__`.
