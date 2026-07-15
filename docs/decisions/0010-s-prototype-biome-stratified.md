---
status: "accepted"
date: 2026-07-15
deciders: "Jamir Priesner (owner)"
consulted: "DESIGN.md §5, DEVELOPMENT_PLAN.md §3/§6"
informed: "ADR 0011, Phase-1/2 checkpoints"
---

# S prototype = biome-stratified multi-cell; F/E prototype = single cell

## Context and Problem Statement

The prototype must be cheap but scientifically meaningful. The handover framed the prototype as
"~50,000 realizations of one location", but the real design is global multi-cell (67,420 cells × 25
patches). What is the prototype scope for each component? See `DESIGN.md` §5.

## Decision Drivers

- S's whole purpose — and the exact thing the sibling emulator failed at — is the **climate/state-
  conditional** distribution, which a single cell cannot exercise (no across-cell climate gradient).
- The 25-patch single-cell noise floor is statistically weak.
- F1 integration and E energy closure *can* be proven cheaply on one cell.

## Considered Options

- **Single cell for everything** (as the handover implied).
- **Single cell for F/E; biome-stratified multi-cell (~10–50 cells) for S.**
- **Full global from the start.**

## Decision Outcome

Chosen: **F1 integration and E on one cell first (candidate Hainich `startgrid:28008`); S on a small
biome-stratified multi-cell set (~10–50 cells) from the start.** A single cell is sufficient to prove
the daily biophysics + energy closure, but a single-cell Phase-2 gate for S would be near-vacuous for
the conditional response. So the Phase-2 single-cell check for S is scoped to **marginal reproduction
+ allocation conservation only**, and the **conditional response is evaluated on the multi-cell set**.

### Consequences

- Good: cheap F/E proof; a scientifically meaningful S gate (there is a climate gradient to fit and
  hold out).
- Good: drawn from the existing global ground truth — no `npatch` change or single-site re-run for S
  (see [ADR 0011](0011-reuse-global-ground-truth.md)).
- Bad: multi-cell handling (loaders, stratification, held-out cells/scenarios) is needed earlier than
  a single-cell prototype would require.
- Bad: full multi-cell generalization remains a separate gated phase (Phase 5) — the prototype does
  not certify it.

## More Information

The daily-output re-run F/E needs restarts from `restart_1999.lpj` with matched seed/domain/`npatch`
(`DESIGN.md` §7). Code is written to generalize to many cells from day one.
