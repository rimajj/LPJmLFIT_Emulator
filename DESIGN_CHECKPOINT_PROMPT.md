# DESIGN-checkpoint prompt addendum — engineering, docs & Git standards

Paste this to the coding agent **when it reaches the DESIGN checkpoint** (end of Phase 0), so the engineering scaffolding is built in from the start, not retrofitted. It complements `00_START_HERE.md`; the authoritative spec is `esm_land_emulator/ENGINEERING_STANDARDS.md`.

---

```
Before writing modelling code, stand up this project as a state-of-the-art, auditable
software product. The full spec is esm_land_emulator/ENGINEERING_STANDARDS.md — read it
and follow it. The owner does NOT write code and must be able to control and understand
everything, so documentation must LINK to the exact code and must break CI when code and
docs diverge; diagrams of the model and data flow must auto-update; and tests/CI are gates
you cannot bypass.

FIXED DECISIONS (owner-confirmed):
- Stack: Julia-primary (Enzyme/Lux/SciML), Python only for the slow-emulator prototype.
- Repo: PRIVATE, on the owner's GitHub. The owner will create the empty repo and provide
  the URL + push auth. Use a repo-scoped SSH deploy key OR a fine-grained PAT (Contents:
  read/write, single repo, short expiry); NEVER put a token in a remote URL or commit
  secrets/data/weights. Fill the placeholders <REPO_URL> / auth in config; if missing, ask.
- Documentation ONLY for now (owner decision): Documenter.jl is the single SOURCE OF TRUTH
  (doctest-verified, cannot hallucinate) — searchable site, narrative, math, code links,
  diagrams. Do NOT set up any AI code-wiki (DeepWiki/OpenDeepWiki) at this stage. It can be
  added later with no rework, so make the Documenter docs genuinely complete and browsable
  enough to stand alone.

ESTABLISH NOW (scaffold-first; commit as the initial project skeleton, then keep green):
1. Git/GitHub: initialize the private repo; trunk-based + short-lived branches + PRs;
   branch protection on main (require PR + green checks + signed commits, no force-push);
   Conventional Commits; SemVer in Project.toml; CHANGELOG.md (Keep a Changelog); SSH commit
   signing; commit at every meaningful step and push at least each checkpoint/session.
2. Testing (Julia): build the pyramid — a BROAD BASE OF UNIT TESTS first (every non-trivial
   function tested in isolation on known/hand-computed values, edge cases, and error paths:
   allometry & diagnostics, unit conversions [gC/kg, °C/K, λ vaporization vs sublimation],
   softmax/allocation helpers, config parsing, data loaders, index/date math, small numerical
   kernels; a one-line unit test would have caught the real 272.15-vs-273.15 K bug in the
   reference repo) → then integration tests (S<->F interface) → then system tests (full run/
   rollout). Framework: Test + TestItems/ReTestItems; add Aqua.jl and JET.jl package checks;
   wire Supposition.jl (property-based), ReferenceTests.jl (numerical regression),
   DifferentiationInterfaceTest.jl + FiniteDifferences.jl (AD-gradient correctness),
   AllocCheck.jl, StableRNGs.jl (determinism), Coverage->Codecov. Python: pytest + Hypothesis
   + Ruff. Create placeholder @testitems for the MUST-have scientific tests so they grow with
   the code: conservation closure (water/carbon incl. firec + flux_estabc, and the asserted
   energy budget — single-step AND rollout), gradient correctness (AD vs finite diff, no
   NaN/Inf), numerical regression, rollout/autoregressive stability (bounded, no oscillation/
   "AC gap"), determinism, data validation, invariance/metamorphic, physical boundedness
   (non-negativity, softmax fractions sum to 1), type stability, limiting cases, and the
   LPJ_resilience battery (autocorrelation-vs-climate, recovery rate, shuffle test).
3. CI (GitHub Actions): CI.yml (matrix lts + 1, +pre allowed-fail; buildpkg, runtest,
   coverage->Codecov); format.yml (Runic.jl); docs.yml (julia-docdeploy: build + DOCTEST +
   linkcheck + deploy); python.yml (ruff + pytest); TagBot.yml; dependabot.yml (julia +
   github-actions + uv). Make these checks REQUIRED for merge.
4. Documentation (Documenter.jl = truth): docstrings with source links; jldoctests as a CI
   gate; @example blocks that regenerate figures; KaTeX math; DocumenterCitations.jl so every
   model equation cites its paper; Literate.jl tutorials (runnable = tested); a Quarto
   GMD-style model-description manuscript (equations + regenerated figures) rendered into the
   site. Diátaxis structure. Create docs/decisions/ and write an ADR (MADR template) for
   every non-trivial decision already made (hybrid choice; flux-then-integrate carbon
   conservation; reuse of Terrarium SEB; constant-CO2 regime; etc.) and for each new one.
   Add a Model Card + dataset Datasheets. (Private-site note in ENGINEERING_STANDARDS §4.)
5. Diagrams (auto-current): (a) curated Mermaid in the docs + README — components (S/F/E),
   fast<->slow coupling (Daily/Annual subgraphs with state pools as arrows), data/flux flow;
   one D2 poster. (b) scripts/gen_diagrams.jl that emits Mermaid/DOT from the model's OWN
   component registry / flux table / config (parse the LPJmL .js config for the data-flow),
   run in CI with `git diff --exit-code` fail-if-stale AND/OR generated live via a Documenter
   @eval block. Curated = owner's mental model; derived = source of truth + diff alarm.
6. Reproducibility: commit Project.toml + Manifest.toml; StableRNGs everywhere; DrWatson.jl
   provenance (tagsave stamps git commit); config-driven (no magic numbers); DVC for data/
   weights; MLflow for experiments; uv.lock for Python.
7. Docs homepage: add a README + docs landing page for the owner (non-coder): a short
   "how to read this" guide pointing to the Explanation + Reference sections and the model
   diagrams. No AI code-wiki for now (see decision above).

ACCEPTANCE (every merged PR from here on): CI + format + docs (doctests + linkcheck) green;
docs/docstrings updated for any code change; derived diagrams regenerated (no stale-diagram
failure); an ADR added/updated for non-trivial decisions; CHANGELOG updated; MEMORY.md and
JOURNAL.md current. Record the whole engineering setup as ADRs and in MEMORY.md, then resume
the phased plan (DEVELOPMENT_PLAN.md §6) with this standard applied throughout.

Confirm one open item with the owner before proceeding: the private repo URL + push auth
(repo-scoped SSH deploy key or fine-grained PAT). (No AI-wiki decision needed — docs only.)
```

---

*Rationale and full tool list: `ENGINEERING_STANDARDS.md`. Research basis: 2026 SOTA for Julia scientific-ML testing/CI, Documenter.jl doc-as-code, and diagrams-as-code + code-derived diagrams. Owner decision: documentation only for now (no AI code-wiki); an AI wiki (DeepWiki/OpenDeepWiki) can be added later without rework if wanted — see `ENGINEERING_STANDARDS.md` §6.*
