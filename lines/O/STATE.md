# LINE O — online coupling: Terrarium + SpeedyWeather (branch `line/O`, worktree `wt-O`) — P4 + P5

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/O/JOURNAL.md` (append-only). Decisions: ADR block **0080–0089**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here

**O1 is DONE — ADR 0080 landed the P5 licensing basis, so P4 is unblocked.** The standing consequence you
must respect: outbound is **AGPL-3.0-or-later**; Terrarium/SpeedyWeather (**both EUPL-1.2**) enter as
**`[weakdeps]` + a package extension** only — never vendored, never runtime `[deps]` (ADR 0014), and adding
them to `Project.toml` is an **integrator** action you must request. Before touching any new dependency or
reference repo, run the **`dependency-license-gate`** skill (register: `docs/third_party_licensing.md`).

**O2 — write `docs/p4_online_coupling_design.md`, the missing design of record.** P4 is currently scoped only
in prose scattered across `ECOSYSTEM_AND_COUPLING.md` §2/§3/§5, `DEVELOPMENT_PLAN.md` §6 and
`STEERING_PROMPT.md`. **Validate every API claim against the real cloned Terrarium** at
`/p/tmp/jamirp/esm_reference_repos/Terrarium.jl` (commit `4f42508`, v0.1.3) — read the code, not your memory
of it — and start from the working templates `examples/simulations/speedy_{dry,wet}_land.jl`, where
`vegetation = nothing` is exactly the slot S+F fill. Cover:

- Which Terrarium `Abstract*` interfaces S / F / E each sit behind (8 vegetation interfaces exist; see
  §What already exists below) and which stay ours.
- The indirect-coupling variable list (`leaf_area_index`, `gross_primary_production`,
  `plant_available_water`, `carbon_vegetation`, `ground_temperature`) mapped onto the frozen
  `src/interface.jl` structs — which you consume **read-only** (line M owns that seam).
- **The timestep story:** F is daily, SpeedyWeather steps ~300 s. State the sub-cycling scheme explicitly.
- Float32 throughout (4 testitems already assert this — the only P4 prep that exists in code today).
- How `ClimBuf` gets its spin-up climatology on a **cold start** (no restart file exists online).
- The conservation story across the interface (water ~1e-12, carbon, energy ~1e-14 must survive coupling).
- Pin the Terrarium commit and say what churn is expected (v0.1.x, unstable API).

*Gate:* the design doc exists, every API claim is traceable to a file+line in the clone, and O3's spike is
implementable from it without further design work.

Then → **O3** (the de-risking spike: ONE process behind ONE Terrarium `Abstract*` interface, as an extension).
O2–O4 need nothing from any other line; **O5 needs line M's M1/M2**.

**Integration points to raise when you next touch `main`** (both found by the ADR 0080 audit, both
integrator-owned so line O deliberately left them alone):
1. `docs/make.jl` says "The repo is PRIVATE" — **stale**, it is public; its `linkcheck_ignore` for our own
   self-links may now be unnecessary. Can't be verified from a line (the `docs` gate doesn't run on branches).
2. ADR 0080 §4 — the owner still needs to file `LICENSE` (AGPL-3.0-or-later) + `Project.toml` `license` +
   `CITATION.cff` `license:` + README §License.

## Scope + ownership (ADR 0029)

**You own (exclusive):**
- `ext/SpeedyWeatherTerrariumExt.jl` (or whatever the extension is named) + any new `ext/` file — and `ext/`
  generally (`CLAUDE.md` §9: "`ext/` to O"), which includes the existing `ext/FDiffTrainingExt.jl`
- `docs/p4_online_coupling_design.md` (new — no P4 design doc exists today)
- `docs/third_party_licensing.md` (new, ADR 0080 — the inbound-licence register; keep it current)
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

**P5 is DONE (ADR 0080); P4 has zero code.** `ext/` contains only `FDiffTrainingExt.jl`; every
`SpeedyWeather` / `Terrarium` hit in `src/`+`test/` is a comment or a test name. `MEMORY.md` phase table:
**6 Online / SpeedyWeather = ⬜ not started**, **7 ESM packaging = ⬜ not started**. There is still **no P4
design doc** — P4 is scoped only in prose across `ECOSYSTEM_AND_COUPLING.md`, `DEVELOPMENT_PLAN.md` §6 and
`STEERING_PROMPT.md`. What changed on 2026-07-28: the licensing basis that gates *taking the dependency at
all* now exists and says yes (as a library dependency).

## Milestones

- **O1** ✅ **DONE (2026-07-28)** — the **P5 licensing ADR** ([0080](../../docs/decisions/0080-licensing-basis.md)):
  AGPL-3.0-or-later outbound (*forced* — LPJmL-FIT copyleft ∧ EUPL-1.2 Appendix), EUPL works consumed as
  **library dependencies only**, never vendored; READ/DEPEND/VENDOR separated; NeuralCrop method-only.
  Register + gate: `docs/third_party_licensing.md` + the `dependency-license-gate` skill. ADR 0017 annotated,
  not superseded. Residual = one named owner action (file `LICENSE`, ADR 0080 §4).
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
  line couples *through* Terrarium, it does not replace E's physics. ADR 0080 removed 0017's *licensing*
  objection for the DEPEND tier, but **not** its other two drivers (zero runtime `[deps]`; v0.1.x churn), so
  0017's outcome is unchanged — don't cite ADR 0080 as a reason to revisit it.
- **Never state a licence from memory** (`dependency-license-gate`): Terrarium AND SpeedyWeather are both
  **EUPL-1.2, not MIT**, and Terrarium's decisive Art.-5-for-library-use exception is in its **`NOTICE`**, not
  its `LICENSE`. **Vendoring** any third-party code needs its own ADR (ADR 0080 §2 Tier 3).
- Any long job → SLURM; the login node is hook-blocked for heavy Julia.
