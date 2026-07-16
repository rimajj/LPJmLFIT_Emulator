# API reference

The complete API of `LPJmLFITEmulator`, assembled automatically from docstrings. Every entry links
to the exact source line on GitHub. The build is strict (`checkdocs=:exports`), so an exported symbol
without a docstring fails CI, and any renamed/added symbol appears here without hand-editing.

```@meta
CurrentModule = LPJmLFITEmulator
```

The block below lists every documented symbol in the package in one place — the module overview, the
[`SharedState`](@ref) type and its dimension constants, the S↔F↔E interface payloads, the
conservation helpers, the component abstract types, and the component/flux registry. It regenerates
automatically when the code changes.

```@autodocs
Modules = [LPJmLFITEmulator]
Order = [:module, :constant, :type, :function]
```

!!! note "Differentiable fast core (`F_diff`) API"
    The `F_diff` submodules — `Allometry` (shared diagnostics), `SmoothOps` (smooth surrogates), and
    `FDiff` (daily biophysics + rollout) — are documented in the source (`?LPJmLFITEmulator.FDiff.rollout`
    in the REPL) and summarized in `docs/phase3_fdiff_spike.md`. Rendering their API here (with the
    cross-module `@ref` links their docstrings use) is a small docs-infra follow-up (per-submodule
    `CurrentModule` pages). See ADR 0014 / 0015.
