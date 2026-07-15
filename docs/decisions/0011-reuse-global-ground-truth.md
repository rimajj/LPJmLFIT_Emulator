---
status: "accepted"
date: 2026-07-15
deciders: "Jamir Priesner (owner)"
consulted: "DESIGN.md §0/§3/§5/§7, DEVELOPMENT_PLAN.md §3, config/paths.yaml"
informed: "ADR 0010, the datasheets"
---

# Reuse the existing global (annual) ground truth; the daily re-run is the only real gap

## Context and Problem Statement

Generating LPJmL-FIT ground truth is the most expensive step. How much new compute does the hybrid
actually need, given that global runs already exist on disk? See `DESIGN.md` §0.3/§5/§7.

## Decision Drivers

- Avoid re-generating data that already exists (44 GB/seed Historical; 180 GB SSP370).
- Be honest about what the existing data does **not** contain.
- Keep the Phase-1 compute minimal and gated.

## Considered Options

- **Re-generate everything** (annual + daily, all pools) from scratch.
- **Reuse the existing annual ground truth**, add only a **daily-output re-run** for the fast-layer
  fluxes F/E need (config-only), and decide per-tree-pool granularity separately.
- **Reuse annual only**, skip daily (insufficient for F/E validation and the water budget).

## Decision Outcome

Chosen: **reuse the existing annual global ground truth; add a config-only daily-output re-run for the
narrow gap.** The annual `ind` CSV suffices to train **aggregate (Tier-1) S** and the annual
`globalflux` lets the **carbon** budget be verified now, with no re-run. The daily re-run (restart
from `restart_1999.lpj`, same seed/domain/`npatch`/binary) materializes the fast-core validation set
and enables the **water** budget check — so the Phase-1 gate is **split** (carbon now; water after the
re-run).

### Consequences

- Good: minimal new compute; reuse of the sibling project's derived parquet tables (63,119 cells) and
  noise-floor yardstick.
- Bad (honest cost): the CSV **omits the disaggregated per-tree carbon pools**. So the
  LPJ_resilience memory mechanism (explicit sapwood + heartwood) needs **either** (a) allometric
  reconstruction via the pipe model (cheap, approximate, no re-run) **or** (b) a RAW `ind`
  re-generation (exact, a global re-run). Default: attempt (a), validate against a small RAW check
  cell, fall back to (b) only if inadequate.
- Bad: therefore "the data already exists" is true for **Tier-1 aggregate S only**, not the
  pool-resolved (Tier-2) variant — do not present both as unconditionally true.
- Bad: the SSP370 seed-2 (OOD noise-floor pair) is still generating — gate OOD-distribution
  evaluation on its completion.

## More Information

Paths, sizes, and the `restart_1999` vs `restart_2019` distinction are in `config/paths.yaml` and the
[Historical](../src/model/datasheets/historical_obsclim.md) / [SSP370](../src/model/datasheets/ssp370.md)
datasheets. Simulation CPU for the daily re-run is unchanged; only I/O grows (`DESIGN.md` §1.1).
