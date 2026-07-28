# LINE O — online coupling: Terrarium + SpeedyWeather (branch `line/O`, worktree `wt-O`) — P4 + P5

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/O/JOURNAL.md` (append-only). Decisions: ADR block **0080–0089**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here

**O1 — the P5 licensing ADR (write it first; it is what unblocks taking a Terrarium dependency at all).**
`STEERING_PROMPT.md` P5 is explicit: *"document a good-faith EUPL↔AGPL↔MIT licensing basis in the ADR and
proceed on it (a formal legal review remains an owner or external action but is **not a blocker for research
use**)"*. So this is a writing task the agent can complete, not an owner dependency.

Write **ADR 0080** covering:
- This repo's own license and what it can consume; Terrarium.jl's license + `NOTICE`
  (`/p/tmp/jamirp/esm_reference_repos/Terrarium.jl/{LICENSE,NOTICE}`) and SpeedyWeather's; the EUPL↔AGPL↔MIT
  compatibility reasoning; the distinction between **reading** a reference implementation, **depending** on a
  package, and **vendoring** code.
- Why NeuralCrop.jl stays **method-only** (CC BY-NC 4.0 — a hard code blocker) and LPJ_resilience stays
  **reimplement-from-paper** (no license at all).
- The consequence for ADR 0017 (whose premise rests on this read) and for `MEMORY.md`'s open
  *"EUPL↔AGPL↔MIT licensing read is still unresolved"* TODO.
- The mechanism: Terrarium/SpeedyWeather enter as **`[weakdeps]` + a package extension**, never runtime
  `[deps]` (ADR 0014 keeps those empty). Adding them to `Project.toml` is an **integrator** action — request it.

*Gate:* ADR 0080 accepted; the `MEMORY.md` licensing TODO resolved or narrowed to a named owner action.

Then → **O2** (write the missing P4 design doc) — O1–O4 need nothing from any other line.

## Scope + ownership (ADR 0029)

**You own (exclusive):**
- `ext/SpeedyWeatherTerrariumExt.jl` (or whatever the extension is named) + any new `ext/` file
- `docs/p4_online_coupling_design.md` (new — no P4 design doc exists today)
- `lines/O/*`, `changelog.d/O-*.md`, ADRs 0080–0089

**Do NOT touch:** `src/components/slow.jl`, `src/drf.jl`, `src/climbuf.jl` (line S) ·
`src/components/energy.jl` (line E) · `src/run.jl`, `src/interface.jl` (line M — **you consume these
read-only**) · `Project.toml` (integrator — a weakdep needs ADR 0080 + an integration point).
Shared, additive-only: `src/LPJmLFITEmulator.jl` (inside `# ── line O ──`), `CLAUDE.md`, `MEMORY.md`.

**SLURM tag prefix:** `O-` · other lines' `/p/tmp` artifacts are **read-only**.

## What already exists (read this before designing anything)

- **Reference clones** at `/p/tmp/jamirp/esm_reference_repos/` (read-only, cloned 2026-07-16):
  - `Terrarium.jl/` — the coupling substrate. 61 `Abstract*` types, including all 8 vegetation interfaces
    (`AbstractPhotosynthesis`, `AbstractStomatalConductance`, `AbstractAutotrophicRespiration`,
    `AbstractPhenology`, `AbstractVegetationCarbonDynamics`, `AbstractVegetationDynamics`,
    `AbstractRootDistribution`, `AbstractPlantAvailableWater`) plus `AbstractSurfaceEnergyBalance` /
    `AbstractSkinTemperature` / `AbstractEnergyClosure` / `AbstractAerodynamics` / `AbstractTurbulentFluxes`.
    Depends on `SpeedyWeatherInternals`. Docs under `docs/extending/{core_interfaces,implementing_processes,
    coupling_processes,state_variables}.md`.
  - **The templates that matter: `Terrarium.jl/examples/simulations/speedy_{dry,wet}_land.jl`** — working
    end-to-end SpeedyWeather↔Terrarium coupling. `speedy_wet_land.jl` builds
    `RingGrids.FullGaussianGrid` → `Speedy.SpectralGrid` → `ColumnRingGrid` → `Terrarium.LandModel(grid;
    initializer, vegetation=nothing, soil)` → `Speedy.LandModel(spectral_grid, terrarium_model; timestepper,
    Δt)` → `Speedy.PrimitiveWetModel(...; land, surface_heat_flux=…PrescribedLandHeatFlux(), …)`.
    **`vegetation = nothing` is exactly the slot this project's S+F fill** — and it is unexercised in the template.
  - `LPJmL-hybrid-photosynthesis/` (MIT — reuse already done for differentiable λ);
    `NeuralCrop.jl/` (**CC BY-NC 4.0 — method only, do not copy code**).
  - **SpeedyWeather.jl itself is NOT cloned** — clone it read-only if needed (login node has network; compute
    nodes do not).
- **The repo side of the contract is frozen and ready:** `src/interface.jl` (`SToF`, `SToE`, `FToS`, `FToE`,
  `EToF`, `EToATM`, `AtmForcing` with units) + `DESIGN.md` §8 + `DEVELOPMENT_PLAN.md` §2.5.
- **The plan of record:** `ECOSYSTEM_AND_COUPLING.md` §2/§3/§5 — **indirect coupling first** (share
  `leaf_area_index`, `gross_primary_production`, `plant_available_water`, `carbon_vegetation`,
  `ground_temperature`), then `SpeedyWeather.LandModel(spectral_grid, external_model)`;
  `PrescribedLandHeatFlux`/`PrescribedLandHumidityFlux` inject H/LE as atmospheric tendencies; multi-cell via
  `ColumnRingGrid` on a RingGrid. §Immediate-actions names the de-risking spike: *"implement one LPJmL-FIT
  process behind a Terrarium `Abstract*` interface, indirectly coupled"*.
- **Float32 readiness is already gated** — 4 testitems assert Float32 type-stability explicitly labelled
  *"(SpeedyWeather-coupling type)"*; that is the only P4 preparation that exists in code today.
- Known caveats to design around: SpeedyWeather has **no carbon cycle** (NEE is diagnostic-only — a non-issue
  per ADR 0004), its skin temperature is currently the top-soil-layer T, and its default drag ignores the
  roughness field.

## Status (2026-07-28)

**Zero online-coupling code exists.** `ext/` contains only `FDiffTrainingExt.jl`; every `SpeedyWeather` /
`Terrarium` hit in `src/`+`test/` is a comment or a test name. `MEMORY.md` phase table: **6 Online /
SpeedyWeather = ⬜ not started**, **7 ESM packaging = ⬜ not started**. There is also **no P4 design doc** —
P4 is scoped only in prose across `ECOSYSTEM_AND_COUPLING.md`, `DEVELOPMENT_PLAN.md` §6 and `STEERING_PROMPT.md`.

## Milestones

- **O1** The **P5 licensing ADR** (0080). *(NEXT, above)*
- **O2** **Write `docs/p4_online_coupling_design.md`** — the missing design of record: which Terrarium
  `Abstract*` interfaces S/F/E sit behind, the indirect-coupling variable list, the sub-cycling/timestep story
  (F is daily; SpeedyWeather steps ~300 s), Float32 throughout, how `ClimBuf` gets its spin-up climatology on a
  cold start, and the conservation story across the interface. Validate the design **against the real API** in
  the cloned Terrarium, not from memory.
- **O3** **The de-risking spike**: ONE LPJmL-FIT process behind ONE Terrarium `Abstract*` interface, indirectly
  coupled — no new science, no new data. Ships as a package **extension** (weakdeps), runtime `[deps]` stays
  empty. *Gate:* it runs inside a Terrarium `LandModel` and reproduces the standalone F_diff result for that
  process.
- **O4** **Wrap the existing single-cell `run_coupled_cell` as a SpeedyWeather `LandModel`** using
  `speedy_wet_land.jl` as the template, filling the `vegetation` slot. *Gate:* a short single-column coupled
  run completes, conserves, and stays Float32-stable.
- **O5** **Multi-cell online** — **needs line M's M1/M2** (per-cell inputs + the coupled multi-cell harness).
  The true P4 gate: a stable **multi-year free run** — no drift, no oscillation / AC-gap — conserving, with
  gradients still flowing; plus OOD warming at constant CO₂.
- **O6** (P7, optional) ESM packaging: the documented external-land interface + sub-daily outputs.

## Line-local gotchas

- **Runtime `[deps]` MUST stay empty (ADR 0014)** — Terrarium/SpeedyWeather are `[weakdeps]` + an extension,
  requested from the integrator. Aqua enforces no stale deps.
- **Compute nodes have NO GitHub egress** (pkg-server tarballs only) and GitHub HTTPS is blocked everywhere —
  clone/instantiate on the **login node** to warm the shared depot, then run.
- Terrarium is **v0.1.x / unstable API** (one of ADR 0017's two reasons for not depending on it for E). Pin a
  commit in the design doc and expect churn.
- Don't reintroduce a Terrarium dependency for **component E** — ADR 0017 decided E stays self-contained; this
  line couples *through* Terrarium, it does not replace E's physics.
- Any long job → SLURM; the login node is hook-blocked for heavy Julia.
