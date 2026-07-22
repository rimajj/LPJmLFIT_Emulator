---
status: "accepted"
date: 2026-07-22
deciders: "Jamir Priesner (owner)"
consulted: "ADR 0006, ADR 0014, DEVELOPMENT_PLAN.md §2.4/§6, DESIGN.md §2.4, ECOSYSTEM_AND_COUPLING.md §2"
informed: "component E, ADR 0007, ADR 0015"
supersedes: "0006 (implementation choice only — physics decisions retained)"
---

# Implement Component E self-contained (reimplement the SEB physics), superseding ADR 0006's Terrarium reuse

## Context and Problem Statement

ADR 0006 chose to **reuse Terrarium.jl's** `SurfaceEnergyBalance` + `ImplicitSkinTemperature` for
component E (the surface-energy-balance + skin-temperature closure LPJmL-FIT lacks). By the time E was
actually built (Phase 4), three facts made reuse the wrong call:

1. **Open licensing blocker (ADR 0006 flagged it).** LPJmL-FIT is AGPL-3.0, Terrarium is EUPL-1.2;
   embedding Terrarium code across repos needs a written legal read that has not happened. This is a
   *hard* blocker, not a caveat.
2. **Zero-runtime-deps stance + offline compute nodes.** This package's runtime `[deps]` is deliberately
   EMPTY (ADR 0014 — the AD stack is a test/train-time extension only). The HPC compute nodes have no
   GitHub egress and only a partial pkg-server mirror (documented: fresh re-resolves fail on the compute
   nodes). Adding Terrarium — a v0.1.x package with a deep dependency tree — as a runtime dependency
   would break the offline deployment path and the "physics core has no deps" invariant.
3. **Terrarium is v0.1.x / unstable** (ADR 0006: "expect breakage; treat as co-development, not a frozen
   dependency"). Co-developing an unstable external dependency is a poor fit for a component whose physics
   is compact and fully specified.

## Decision Drivers

- The E physics is **small and completely specified** (DEVELOPMENT_PLAN §2.4): one Newton solve for a
  single skin temperature, a neutral-log-law aerodynamic conductance, a conductance ground-heat term, and
  the residual-H closure. There is nothing large or novel to "reuse away".
- **Exact precedent.** ADR 0014 already made this call for the fast core: rather than call the compiled
  LPJmL-FIT C binary at runtime, F was reimplemented from scratch as the differentiable, dependency-free
  `FDiff`. Component E vs Terrarium is the identical situation one layer up.
- Must keep one consistent skin temperature (Rn, H, G on the same surface) and AD-friendliness — both are
  achievable in a self-contained solver.

## Considered Options

- **Reuse Terrarium.jl** as a runtime dependency (ADR 0006's choice).
- **Reimplement the SEB physics self-contained**, dependency-free and AD-friendly (this ADR).
- Vendor a copy of Terrarium's SEB into the repo (rejected: same AGPL↔EUPL licensing problem as reuse,
  plus maintenance drift).

## Decision Outcome

Chosen: **reimplement Component E self-contained** (`src/components/energy.jl`: `SEBEnergyClosure`,
`SEBParams`, the pure `solve_seb` / `aerodynamic_conductance` kernels). ADR 0006's **physics decisions are
retained unchanged** — one consistent skin temperature; `Rn(T_skin) = SW(1−α) + ε·LW − εσT_skin⁴`;
`Rn = LE + H + G` with `H = ρc_p g_a(T_skin − Tair)` the **residual** (LE is water-limited from F,
the documented "no privileged residual" exception); `G` evaluated under `T_skin`; the mandatory E→F
skin-temperature feedback. Only the *implementation vehicle* changes: reimplement, don't depend.

### Consequences

- Good: **no licensing blocker** (no cross-repo code embedding), **runtime stays dependency-free**
  (works offline on the compute nodes), fully under our control, AD-friendly (fixed-graph Newton, verified
  ForwardDiff-vs-FiniteDifferences), and immediately usable — the coupled S+F+E run closes energy to
  machine precision on the Hainich cell (Phase-4 gate met).
- Good: consistent with ADR 0014; the whole model is now one dependency-free Julia core.
- Bad: we own the SEB physics (but it is small and tested); a future SpeedyWeather/Terrarium *coupling*
  can still adopt Terrarium's interfaces at the coupling boundary without embedding its code here.
- Bad: `H` remains the documented residual and the least-controlled flux — validate hardest vs
  FLUXNET/PLUMBER2 (unchanged from ADR 0006).

## More Information

The ML role in E is still an optional **bounded** correction to `g_a`/`T_skin` inside the closed balance
(never break `Rn = LE + H + G`) — unchanged from ADR 0006, and enabled by the AD-friendly kernel. The
demand cap (`LE ≤ Rn − G`) is implemented but OFF by default: F already water-limits ET, so capping would
discard water F committed to (the unused-water return to F is not yet wired); default is uncapped, exact
closure, H the pure residual. Gates: `test/testitems/energy_closure_tests.jl` (closure by construction,
plausibility, AD, Float32) and `test/testitems/coupled_run_tests.jl` (end-to-end coupled Hainich year).
Deployment demonstration: `scripts/run_coupled_cell.jl` (decadal cell-mean ESM outputs).
