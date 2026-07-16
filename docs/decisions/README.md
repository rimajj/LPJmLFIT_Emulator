# Architecture Decision Records (ADRs)

This directory is the **audit trail** for the project — the single most important artifact for
reviewing AI-built code (ENGINEERING_STANDARDS §4). Each ADR is a numbered, **immutable-once-accepted**
record of one non-trivial decision: *problem → options → decision → consequences*. It turns "why did
the agent build it this way?" into a reviewable trail.

Format: **[MADR](https://adr.github.io/madr/)**. Start from [`0000-template.md`](0000-template.md).

## Rules

- **One ADR per non-trivial decision.** Numbered sequentially, `NNNN-kebab-title.md`.
- **Immutable once accepted.** To change a decision, write a **new** ADR that supersedes the old one
  (update the old one's `status:` to `superseded by ADR-XXXX`); never rewrite history.
- **Cite the source.** Every ADR links the relevant `DESIGN.md` / `DEVELOPMENT_PLAN.md` /
  `RESEARCH_SURVEY.md` / `ECOSYSTEM_AND_COUPLING.md` sections.

## Index — the FROZEN Phase-0 decisions

| # | Decision | Status |
|---|---|---|
| [0001](0001-phased-hybrid.md) | Build a phased hybrid (emulate slow S, keep physical F, add energy E) | accepted |
| [0002](0002-emulate-distributions.md) | Emulate the trait/size **distribution**, not individual trees | accepted |
| [0003](0003-flux-then-integrate-carbon.md) | Flux-then-integrate carbon conservation (with fire + establishment) | accepted |
| [0004](0004-constant-co2-regime.md) | Constant-CO₂ regime (inherited from `with_nitrogen="no"`) | accepted |
| [0005](0005-drf-baseline-escalation.md) | DRF baseline for S + an escalation ladder | accepted |
| [0006](0006-reuse-terrarium-seb.md) | Reuse Terrarium.jl's SEB + skin temperature for component E | accepted |
| [0007](0007-julia-primary-stack.md) | Julia-primary stack (Python only for the S prototype) | accepted |
| [0008](0008-documentation-only.md) | Documentation-only (Documenter.jl); no AI code-wiki | accepted |
| [0009](0009-ssh-deploy-key-auth.md) | SSH deploy-key auth from the HPC | accepted |
| [0010](0010-s-prototype-biome-stratified.md) | S prototype = biome-stratified multi-cell (F/E single cell) | accepted |
| [0011](0011-reuse-global-ground-truth.md) | Reuse existing global (annual) ground truth; daily re-run is the gap | accepted |
| [0012](0012-canonical-slow-emulator-here.md) | Canonicalize component S here; port the sibling once, then abandon it | accepted |
| [0013](0013-main-only-workflow.md) | Work on `main` directly — no branches/PRs/branch-protection (relaxes §1) | accepted |
