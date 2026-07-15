# How to build the documentation

> *Goal-oriented how-to. The docs are the single source of truth (ENGINEERING_STANDARDS §4); this
> shows how to build them locally and what the strict build guarantees.*

## Build locally

From the repository root:

```bash
# One-time: instantiate the docs environment (dev-links the package so source links resolve).
julia --project=docs -e 'using Pkg; Pkg.develop(path="."); Pkg.instantiate()'

# Build the site (runs doctests, executes @example/@eval blocks, regenerates derived diagrams).
julia --project=docs docs/make.jl
```

The rendered site is written to `docs/build/`; open `docs/build/index.html` in a browser.

!!! tip "Pretty URLs"
    `docs/make.jl` sets `prettyurls = get(ENV, "CI", "false") == "true"`. Locally (CI unset) pages are
    plain `.html` files that open directly from disk; in CI they get clean directory URLs for
    GitHub Pages.

## What the build enforces (strict — `warnonly = false`)

The build **fails** — it does not warn — if any of these drift, which is exactly what gives the owner
control over agent-written code:

- **Missing docs:** `checkdocs = :exports` — every exported symbol must have a docstring rendered in
  the [API reference](../reference/api.md).
- **Doctest drift:** `doctest = true` — every ` ```jldoctest ` block is executed and its printed
  output must match (e.g. the [`softmax_partition`](@ref) example).
- **Broken examples/diagrams:** `@example` / `@eval` blocks (including the code-derived
  [diagrams](../diagrams.md)) are re-executed on every build.
- **Broken cross-references:** every `[…](@ref)` and `[key](@cite)` must resolve.

## Citations

Bibliography entries live in `docs/src/refs.bib` and are cited with `[Key](@cite)`
(DocumenterCitations.jl, author–year style). The canonical `@bibliography` list is rendered at the end
of the [model description](../model/model_description.md). Add a reference by adding a BibTeX entry and
citing its key.

## Diagrams

Curated Mermaid diagrams live under `docs/src/assets/diagrams/*.mmd`; the **code-derived** diagrams
are emitted by `scripts/gen_diagrams.jl` from the package's own [`COMPONENTS`](@ref) / [`FLUXES`](@ref)
registry to `docs/src/generated/*.mmd`. Both are embedded here and render via DocumenterMermaid.jl. CI
re-runs `gen_diagrams.jl` and fails on `git diff --exit-code` if a committed derived diagram is stale —
the diff alarm. See [Diagrams](../diagrams.md) for the governance rule.

## Deploy

CI (`.github/workflows/docs.yml`, `julia-docdeploy@v1`) builds on every push, runs doctests + link
checks, and deploys to GitHub Pages on `main`; pull requests get **preview** builds
(`push_preview = true` in `deploydocs`). Deploy auth uses a `DOCUMENTER_KEY` SSH deploy key
([ADR 0009](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0009-ssh-deploy-key-auth.md)).

!!! note "Private repo"
    A private Documenter *site* needs GitHub Enterprise Cloud; otherwise the static `docs/build` HTML
    is published to an access-controlled location, and can be flipped to public GitHub Pages if the
    repo later goes public (ENGINEERING_STANDARDS §4).
