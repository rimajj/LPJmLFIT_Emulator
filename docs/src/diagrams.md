# Diagrams

```@meta
CurrentModule = LPJmLFITEmulator
```

A picture of where every piece sits. There are **two sets** of diagrams, and the governance rule that
resolves the tension between them is the important part (ENGINEERING_STANDARDS §5).

## Governance: curated vs derived

| | **Curated** | **Derived** |
|---|---|---|
| Author | hand-drawn by a human/agent | generated from the code's own registry |
| Purpose | the owner's **mental model** — small, readable | the **source of truth** — always true |
| Source | `docs/src/assets/diagrams/*.mmd` (versioned Mermaid text) | `docs/src/generated/*.mmd`, emitted by `scripts/gen_diagrams.jl` from [`COMPONENTS`](@ref)/[`FLUXES`](@ref) |
| Staleness | possible → caught by the diff alarm | impossible — CI fails on `git diff --exit-code` if the committed copy is stale |

**The rule:** curated diagrams are the owner's mental model; the derived diagrams are the source of
truth and act as a **diff alarm**. `scripts/gen_diagrams.jl` reads the model's own component/flux
registry (`src/registry.jl`) and emits Mermaid to `docs/src/generated/`; CI re-runs it and fails on
`git diff --exit-code` if the committed copy diverged. When the auto-generated graph changes, that is
the signal to update the curated diagrams by hand. We commit diagram **text** (`.mmd`), never rendered
SVG, so diffs stay reviewable.

!!! note "Caveats (ENGINEERING_STANDARDS §5)"
    Mermaid degrades past ~50–100 nodes — keep derived graphs subsystem-level and drop to D2/Graphviz
    for dense views. GitHub's Mermaid does not render C4; use `flowchart`/`architecture-beta`.

## Curated conceptual diagrams (owner-facing)

Authored as versioned Mermaid text under `docs/src/assets/diagrams/` and embedded here, so the page
and the `.mmd` files never duplicate. (If a file is not yet committed, a placeholder shows until it
lands.)

### Components overview — S / F / E and the one shared state

```@eval
using Markdown
f = joinpath("assets", "diagrams", "components.mmd")
isfile(f) ? Markdown.parse("```mermaid\n" * read(f, String) * "\n```") :
    Markdown.parse("*Curated diagram `docs/src/assets/diagrams/components.mmd` pending — will render here once committed (see governance above).*")
```

### Fast ↔ slow coupling (Daily / Annual tiers; the crossing arrows are the shared-state handoffs)

```@eval
using Markdown
f = joinpath("assets", "diagrams", "coupling.mmd")
isfile(f) ? Markdown.parse("```mermaid\n" * read(f, String) * "\n```") :
    Markdown.parse("*Curated diagram `docs/src/assets/diagrams/coupling.mmd` pending — will render here once committed (see governance above).*")
```

### Data / flux flow (input drivers → model → output fluxes, with the conserved budgets)

```@eval
using Markdown
f = joinpath("assets", "diagrams", "dataflow.mmd")
isfile(f) ? Markdown.parse("```mermaid\n" * read(f, String) * "\n```") :
    Markdown.parse("*Curated diagram `docs/src/assets/diagrams/dataflow.mmd` pending — will render here once committed (see governance above).*")
```

## Code-derived diagrams (source of truth)

Emitted by `scripts/gen_diagrams.jl` from the package's own [`COMPONENTS`](@ref) / [`FLUXES`](@ref)
registry (`src/registry.jl`) and committed under `docs/src/generated/`. They cannot drift unnoticed:
CI regenerates them and fails on any `git diff`. Embedded live below, so this page always shows the
committed source of truth.

### Derived — component overview

```@eval
using Markdown
f = joinpath("generated", "components.mmd")
isfile(f) ? Markdown.parse("```mermaid\n" * read(f, String) * "\n```") :
    Markdown.parse("*Derived diagram `docs/src/generated/components.mmd` pending — run `julia --project=. scripts/gen_diagrams.jl` (see governance above).*")
```

### Derived — data-flow graph (conserved handoffs highlighted)

```@eval
using Markdown
f = joinpath("generated", "dataflow.mmd")
isfile(f) ? Markdown.parse("```mermaid\n" * read(f, String) * "\n```") :
    Markdown.parse("*Derived diagram `docs/src/generated/dataflow.mmd` pending — run `julia --project=. scripts/gen_diagrams.jl` (see governance above).*")
```

The same registry underlies the [interface-contract table](explanation/architecture.md) and the
[conservation](explanation/conservation.md) helpers. For the atmosphere/coupling ecosystem this graph
plugs into, see `ECOSYSTEM_AND_COUPLING.md`.
