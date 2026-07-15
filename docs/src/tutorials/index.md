# Tutorials

> *Diátaxis: tutorials are learning-oriented, hands-on walkthroughs. This section is a placeholder in
> Phase 0 — there is nothing to run end-to-end yet (S/F/E are documented stubs).*

## What will live here

Tutorials arrive **with the components they teach**, and each one will be a
[Literate.jl](https://fredrikekre.github.io/Literate.jl/) source file: an annotated `.jl` script that
is simultaneously (a) an executed documentation page and (b) a runnable test, so it **cannot rot** —
if the API changes and the tutorial breaks, CI fails. Literate injects an `EditURL` back to the
source, and the executed output/figures are regenerated on every build.

Planned tutorials, mapped to the phased plan (`DEVELOPMENT_PLAN.md` §6):

| Phase | Tutorial | Teaches |
|---|---|---|
| 1 | Enable daily output and verify budgets close | the data-generation loop; [`carbon_budget_residual`](@ref) / [`water_budget_residual`](@ref) |
| 2 | Fit the DRF slow emulator on the prototype cells | building the slow table; the distributional metric panel |
| 2 | Allocate NPP with softmax + flux-then-integrate | [`softmax_partition`](@ref), [`flux_then_integrate`](@ref) — carbon conservation at the handoff |
| 3 | Couple S ↔ F on a prototype cell | the [`SToF`](@ref) / [`FToS`](@ref) interface |
| 4 | Close the surface energy balance and derive `LE = λ·ET` | component E; [`latent_heat`](@ref) |

## Where the source files go

Literate sources will live under `docs/literate/` (or `examples/`) and be run through Literate in
`docs/make.jl` to emit Markdown into `docs/src/generated/`. Until the first component lands, start
from the [Explanation](../explanation/architecture.md) and [Model description](../model/model_description.md)
sections, and the [how-to guides](../howto/run_lpjml.md).
