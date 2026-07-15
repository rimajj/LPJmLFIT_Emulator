# LPJmL-FIT Hybrid Land Component

*ESM-ready hybrid land-surface component derived from **LPJmL-FIT** (LPJmL 5.6.004 + flexible
individual tree traits), built to drive an Earth-System-Model atmosphere.*

This site is the **single source of truth** for the project (ENGINEERING_STANDARDS §4/§6). It is kept
honest by CI: if the code and the documentation diverge — a docstring goes missing, a doctest output
drifts, an embedded example stops running, a code-derived diagram goes stale — the build **fails**.
That loud failure is what lets the owner control and audit code they did not write.

## The model in one picture

Three components around **one authoritative shared state** ([`SharedState`](@ref)):

| | Component | Timescale | What it is |
|---|---|---|---|
| **S** | Slow trait/size **distribution** emulator | annual | **ML** — emulates the per-cell distribution over trees `p(traits, size ∣ drivers, state)` + count `N`. The scientific novelty. |
| **F** | Fast physical biophysical core | daily | **Kept from LPJmL-FIT** — photosynthesis → GPP → NPP, water balance, snow, soil thermal. Conserving water & carbon *by construction*. |
| **E** | Surface-energy-balance + skin-temperature closure | daily → sub-daily | **New** (reuse Terrarium.jl) — the ESM interface LPJmL-FIT lacks: solves `T_skin`, partitions available energy into `LE / H / G`. |

Water and carbon conservation are **inherited** from the physical core; the energy budget is **closed
by construction** in E. The coupling variables the land hands the atmosphere — `LE`, `H`, `G`,
`T_skin`, `NBP_atm`, roughness `z0` — are **derived, not co-predicted** (see
[Conservation by construction](explanation/conservation.md)).

## How to read this (for the owner / non-coder)

You do **not** need to read code. Read in this order — *explanation* and *reference* first, which is
what matters most for understanding and controlling the project:

1. **[Explanation](explanation/architecture.md)** — the concepts, in plain prose:
   [the three-component architecture](explanation/architecture.md),
   [conservation by construction](explanation/conservation.md),
   [why a hybrid at all](explanation/hybrid_rationale.md), and
   [the honest limitations](explanation/limitations.md).
2. **[Model description](model/model_description.md)** — the GMD-style scientific manuscript: the
   equations (each citing the paper it comes from), and the explicit split between **verification**
   (does the code do the maths right?) and **evaluation** (does the model match reality?). Plus the
   [ML model card for component S](model/model_card.md) and the dataset datasheets
   ([Historical](model/datasheets/historical_obsclim.md), [SSP370](model/datasheets/ssp370.md)).
3. **[Diagrams](diagrams.md)** — a picture of where every piece sits. Curated (owner-facing) diagrams
   plus code-derived diagrams that are regenerated on every build so they cannot silently go stale.
4. **Decisions (ADRs)** — *why* each non-trivial choice was made (problem → options → decision →
   consequences). This is the audit trail for AI-built code. Browse the
   [decision log on GitHub](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/README.md).
5. **[Reference](reference/api.md)** — the exhaustive [API](reference/api.md) (every symbol, linked to
   the exact source line) and the [glossary](reference/glossary.md) of terms and units.

The narrower **[how-to guides](howto/run_lpjml.md)** and **[tutorials](tutorials/index.md)** are for
whoever actually runs the model.

## Status

**Phase 0 (DESIGN) complete** — the shared-state vector, the S↔F↔E interface contract, and the data
schemas are *frozen*. The conservation helpers and interface types are real and tested; the modelling
components (S/F/E) are documented stubs that grow phase-by-phase. See the
[phased plan on GitHub](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/DEVELOPMENT_PLAN.md) (§6)
and the [frozen design](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/DESIGN.md).

!!! note "Julia package"
    The code is the Julia package **`LPJmLFITEmulator`**. Install the docs environment and build with
    the instructions in [Build the documentation](howto/build_docs.md).
