# Engineering Standards: tests, documentation, diagrams, CI, Git

State-of-the-art (2026) software-engineering standard for this project, so it is built as a trustworthy, auditable software product — **not** retrofitted. The governing constraint: the owner does **not** write the code and must be able to **control and understand everything**. That means (a) documentation that **links to the exact code** and **cannot silently go stale**, (b) **visual, auto-current** model/data-flow diagrams, (c) a test/CI regime that acts as **gates the agent cannot bypass**, and (d) a clean Git history on the owner's private GitHub.

Recommendations are tool-specific but the tool landscape moves fast — the agent must **verify current status/versions at setup** (flagged items below). Stack is **Julia-primary** (per `ECOSYSTEM_AND_COUPLING.md`), Python for the slow-emulator prototype.

**Set this up in Phase 0/1 (scaffold-first), before heavy modelling code exists.** Conservation, tests, docs, and diagrams are cheap to grow with the code and expensive to bolt on later.

---

## 0. The core principle: control comes from CI gates, not from trust

"Auto-updating docs" means two things, and we want both:
- **Structural auto-update** — new/renamed functions appear in the API reference automatically.
- **Consistency enforcement** — every embedded example, printed output, figure, and code-derived diagram is **re-executed/re-generated on every push**, and **CI fails** if code changed but the doc/diagram didn't. This loud failure is what actually gives a non-coder control.

Honest limit: prose narrative and the equation↔code mapping are still human/agent-written. The guarantee is that anything embedded in them (doctests, `@example`, Quarto cells, derived diagrams) breaks CI when the code diverges. AI wikis (below) **can hallucinate** and are explorers, never the source of truth.

---

## 1. Repository & Git workflow (private repo)

- **One private repo** on the owner's GitHub (owner creates it and provides URL + auth; see §8 for safe HPC auth). The `esm_land_emulator/` planning docs live in it alongside the code.
- **Trunk-based, short-lived branches + Pull Requests**, even solo. The agent works on a branch → opens a PR → **required CI checks must be green to merge**. Direct pushes to `main` disabled. This turns CI into a hard safety gate around agent output.
- **Branch protection on `main`:** require PR, require status checks (`test (lts)`, `test (1)`, `format`, `docs`, coverage), require signed commits, dismiss stale approvals, no force-push.
- **Conventional Commits** (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`, `BREAKING CHANGE:`) → drives SemVer. One logical change per commit; keep formatting-only and refactor commits separate from behavior changes.
- **Commit/push cadence:** commit at every meaningful step with a descriptive message; push the branch regularly (at least at each checkpoint and end of work session) so the owner always sees current state. Never commit data, model weights, or secrets (`.gitignore` + DVC + a secret-scanning pre-commit hook).
- **Signed commits:** SSH commit signing (`git config gpg.format ssh; commit.gpgsign true`) for the "Verified" badge — simpler than GPG on an HPC.
- **SemVer 2.0.0** for `Project.toml` version; **Keep a Changelog** `CHANGELOG.md` (agent maintains the Unreleased section); **TagBot** for release notes on tags.

## 2. Testing (unit-test base + scientific gates on top)

**The testing pyramid — unit tests are the foundation, not an afterthought.** The scientific
gates further down sit *on top of* a broad base of ordinary **unit tests**: every non-trivial
function tested in isolation for correct output on known inputs, edge cases, and error paths.
Scientific/ML code needs this base *especially*, because a wrong unit conversion or allometry
constant produces plausible-looking output that a conservation or accuracy test can miss —
e.g. the LPJmL-hybrid-photosynthesis reference repo shipped a `272.15` vs `273.15` K bug in
its °C↔K conversion; a one-line unit test on a hand-computed value catches that instantly, a
rollout test would not. Target the classic shape: **many fast unit tests → fewer integration
tests (component interfaces, e.g. S↔F) → few system/end-to-end tests (full runs, rollouts)**,
plus the cross-cutting property/conservation/regression gates.

**Unit tests to write for THIS project** (deterministic, independently checkable — the base layer):
- **Allometry & diagnostics** vs hand-computed values and limits: height, crown area,
  `LAI = leafC·SLA/crownarea`, FPC (Beer–Lambert), stem diameter — e.g. zero leaf carbon ⇒
  LAI 0, monotonic in inputs, matches a closed-form value.
- **Unit conversions** (gC↔kg, mm↔m, °C↔K, per-day↔per-year, λ vaporization vs sublimation)
  — exact known values.
- **Softmax / allocation helpers** — fractions sum to 1, non-negative, handle extreme/
  degenerate logits; pool add/subtract bookkeeping exact.
- **Config parsing** (LPJmL `.js`-with-comments; project YAML) vs fixtures, incl. malformed
  input → informative error.
- **Data loaders** — shapes/dtypes/units, NaN/missing handling, boundary cases (empty patch,
  single tree, zero snow).
- **Index / coordinate / date math** — soil-layer indexing, `(cell, patch-index)` keys,
  day-of-year/leap handling.
- **Small numerical kernels** — interpolation, diurnal-downscaling weights (must conserve the
  daily mean), Newton solves converge on a known case.
- **Error handling** — out-of-range inputs (negative pools, implausible CO₂), malformed state
  → raise clear errors, never silent NaN.

Coverage on this base layer is meaningful (aim high on pure functions); on the model as a
whole, coverage is a hygiene signal, not a target (Goodhart).

**Julia stack** (all free/OSS):
- **`Test` + TestItems.jl `@testitem`**, run in parallel by **ReTestItems.jl** in CI (hermetic test items → agent-generated tests can't leak global state).
- **Aqua.jl** (`Aqua.test_all`) — catches the exact bug classes agents introduce: method ambiguities, undefined exports, unbound type params, stale deps, type piracy.
- **JET.jl** (`test_package`, `@test_opt`) — static type/error analysis; flags instabilities and latent errors.
- **Supposition.jl** — property-based testing with shrinking (Hypothesis-style) for scientific invariants over randomly generated *valid* states.
- **ReferenceTests.jl** (`@test_reference`) — numerical/plot regression vs saved baselines; catches silent drift after refactors.
- **DifferentiationInterfaceTest.jl** / **ChainRulesTestUtils.jl** with **FiniteDifferences.jl** ground truth — AD-gradient correctness (Enzyme/Zygote vs finite differences).
- **AllocCheck.jl** / `@test @allocated` — allocation guardrails for hot kernels.
- **StableRNGs.jl** — deterministic seeded tests (default Julia RNG streams are NOT stable across versions → flaky otherwise).
- **Coverage.jl → Codecov** — hygiene signal, not a target (Goodhart).

**The MUST-have scientific/ML tests** (each a `@testitem`; this is what makes the model *trustworthy*, beyond accuracy):
1. **Conservation closure** — water/carbon (incl. fire `firec` + establishment `flux_estabc`) and the asserted energy budget close to tolerance, on a single step **and** over a full rollout. Use Supposition over valid states.
2. **Gradient correctness** — AD vs finite differences at multiple points incl. near boundaries; assert no NaN/Inf gradients (critical for the differentiable core / online training).
3. **Numerical regression** — `@test_reference` against saved baselines.
4. **Rollout / autoregressive stability** — long-horizon boundedness, no blow-up, **no spurious oscillations / "AC gap"** (the stiff carbon+population failure mode from LPJ_resilience), bounded drift vs a reference trajectory.
5. **Determinism** — fixed seed ⇒ reproducible results.
6. **Data validation** — schema/range/shape/units, no NaN, reject malformed batches (every loader).
7. **Invariance / metamorphic** — known symmetries/relations hold (gate on domain validity + tolerances).
8. **Physical boundedness** — non-negativity, fractions sum to 1 (softmax allocations), monotonicity where required.
9. **Type stability & shapes** — `@test_opt`, `@inferred`, across batch sizes and Float32/Float64.
10. **Limiting-case sanity** — zero forcing ⇒ zero/steady response; closed-form toy cases.
11. **Resilience battery** (from `DEVELOPMENT_PLAN.md` §5 / LPJ_resilience) — autocorrelation-vs-climate, recovery rate, and the **shuffle test** (memory internal vs inherited).

**Python prototype:** pytest + **Hypothesis** (property-based) + **Ruff** (lint+format) + coverage.

## 3. CI / CD (GitHub Actions; all free for the repo)

Workflows under `.github/workflows/`:
- **`CI.yml`** — matrix `version: [lts, '1']` (+ `pre` allowed-to-fail, + one macOS): `setup-julia@v2`, `cache@v2`, `julia-buildpkg`, `julia-runtest` (`annotate: true`), `julia-processcoverage`, `codecov-action@v5`.
- **`format.yml`** — **Runic.jl** via `runic-action` (zero-config, deterministic — eliminates style churn in agent output). JuliaFormatter is the configurable alternative.
- **`docs.yml`** — `julia-docdeploy@v1`; builds docs, **runs doctests, checks links, deploys** (see §4).
- **`python.yml`** — `ruff check` + `ruff format --check` + `pytest` (via `uv`).
- **`TagBot.yml`** — releases/changelog on tag.
- **`.github/dependabot.yml`** — `package-ecosystem: julia` + `github-actions` + `uv`, weekly. (Dependabot now supports Julia natively; CompatHelper's README recommends migrating to it — verify at setup.)
- Optional **`benchmark.yml`** — AirspeedVelocity PR time+memory deltas.

## 4. Documentation (Documenter.jl = source of truth)

- **Documenter.jl** (current stable v1.17.x — verify): API reference auto-assembled from docstrings with **source links to the exact GitHub line**; **doctests that fail CI on output mismatch** (the core doc↔code consistency gate); executed `@example`/`@repl` blocks (figures regenerated, never pasted); LaTeX/KaTeX math; `linkcheck`; one-command versioned deploy to GitHub Pages. Set `modules=[...]` so undocumented functions warn; keep `warnonly` off (strict).
- **DocumenterCitations.jl** — BibTeX bibliography so **every model equation cites the paper it came from** (`[Key](@cite)`), rendered in HTML/PDF.
- **Literate.jl** — annotated `.jl` tutorials that are executed doc pages **and** runnable tests (can't rot); injects `EditURL` to source.
- **Quarto** (native `julia` engine) — the "paper-like" **GMD-style model-description manuscript**: scientific narrative + equations + regenerated figures + citations, exported to `commonmark` and fed into the Documenter site (one build). This is the document the owner reads to understand the science; its embedded cells re-run each build.
- **Information architecture: Diátaxis** (tutorials / how-to / reference / explanation) — for the owner, *explanation* + *reference* matter most.
- **ADRs** (Architecture Decision Records, MADR template, `docs/decisions/`) — numbered, immutable-once-accepted records of *problem → options → decision → consequences*. **This is the single most important artifact for auditing AI-built code**: it turns "why did the agent build it this way?" into a reviewable trail. One ADR per non-trivial design decision (e.g. "chose flux-then-integrate for carbon conservation", "reused Terrarium SEB").
- **Scientific-record norms:** a **GMD-style model description** (detailed enough to re-implement; explicit *verification* vs *evaluation*; exact code version DOI-archived on Zenodo for any paper), a **Model Card** for the ML component, and a **Datasheet** for each dataset.
- **Private-site note:** a private Documenter *site* needs GitHub Enterprise Cloud; otherwise publish the static `docs/build` HTML to an access-controlled server (or keep it internal and flip to GitHub Pages if the repo goes public later).

## 5. Diagrams of model & data flow (must auto-update)

Two sets, per `ECOSYSTEM_AND_COUPLING.md`-style reasoning:
- **(i) Curated conceptual diagrams (owner-facing, small, readable)** — hand-authored **Mermaid** (`.mmd`, versioned) rendered natively on GitHub and in the Documenter site (via **DocumenterMermaid.jl**): a **components overview** (S / F / E, the ML pieces highlighted), the **fast↔slow coupling** (two subgraphs Daily/Annual with the state pools as the crossing arrows), and the **data/flux flow**. One polished **D2** poster for slides/paper.
- **(ii) Code/config-derived diagrams (always-true, auto-regenerated)** — a small Julia script (`scripts/gen_diagrams.jl`) that reads the model's **own** component registry / flux table / config (or ModelingToolkit dependency graphs if used) and **emits Mermaid/DOT**, run in CI on every push. Keep them honest with **fail-if-stale** (`git diff --exit-code -- docs/src/generated`) and/or generate **live in the docs build** via a Documenter `@eval` block returning a `Markdown.MD` mermaid fence (staleness then impossible). Parse the LPJmL-style `.js` config to auto-draw the input-drivers → model → output-fluxes data flow.
- **Governance rule that resolves the tension:** curated diagrams are the owner's mental model; derived diagrams are the source of truth and act as a **diff alarm** — if the auto-generated graph changes, that's the signal to update the curated one.
- **Caveats:** Mermaid degrades past ~50–100 nodes (keep derived graphs subsystem-level; drop to D2/Graphviz for dense views); GitHub's Mermaid does **not** render C4 (use flowchart/`architecture-beta`); commit diagram **text**, not rendered SVG, to keep diffs reviewable. Doxygen+Graphviz can auto-emit call graphs for the C reference (LPJmL) for free.

## 6. Documentation only for now — no AI code-wiki (owner decision)

**Decision:** use **Documenter.jl as the single source of truth** (§4) and do **not** set up any AI code-wiki (DeepWiki/OpenDeepWiki/Google Code Wiki) at this stage. Rationale: keeps everything in the owner's control, no third-party code upload, no hallucination risk, no extra ops. The cost is that the owner browses/searches the Documenter site rather than chatting with an AI over the repo.

Implication for the build: make the Documenter docs genuinely **complete and self-standing** — strong Explanation + Reference sections (Diátaxis), the Quarto model-description manuscript, curated + auto-generated diagrams, and code links on every documented symbol — so a non-coder can navigate and understand without an AI layer.

**Deferred (can be added later with zero rework if wanted):** an AI wiki as a *browsable explorer only* (never the source of truth — AI wikis hallucinate: documented wrong build systems, invented integrations, wrong pipeline diagrams). The free options for a private repo, for future reference: **DeepWiki** via a free Devin account (zero-ops, but uploads code to Cognition's cloud — needs IP sign-off), or self-hosted **OpenDeepWiki** with a local LLM (Ollama; offline, needs Docker). **Google Code Wiki** is public-only today. If ever adopted, the rule is: read Documenter as truth; use the wiki to explore and click through its code links to verify.

## 7. Reproducibility

- Commit **`Project.toml` + `Manifest.toml`** (this is an application/experiment repo → pin the Manifest; version-specific `Manifest-v1.x.toml` supported).
- **StableRNGs.jl** for all stochastic code; fixed seeds logged.
- **DrWatson.jl** for config-driven runs + provenance: `tagsave` stamps every saved result with the git commit (and patch if dirty), so any result is reproducible by checkout.
- **Config-driven** everything (no magic numbers in code — use the `config/` files); log the exact LPJmL-FIT commit + config + input files per dataset (already required in `00_START_HERE.md`).
- **DVC** for dataset/model versioning (git-tracked pointers to remote storage); **MLflow** for experiment/param/metric tracking (reports query it live, not transcribed numbers).
- Python: `uv` lockfile (`uv.lock`).

## 8. Safe GitHub auth from the HPC

- Prefer a **repository SSH deploy key with write access** (bound to exactly one repo) **or** a **fine-grained PAT scoped to the single repo** with **Contents: read/write** and a short expiry. Never an org-wide/classic PAT in an HPC job.
- Store the private key `chmod 600`, use an `ssh-agent`/`~/.ssh/config` host alias, or inject the PAT via the scheduler's secret store + a git credential helper — **never** put a token in a `git remote` URL (it leaks to reflogs/CI logs).
- `DOCUMENTER_KEY` (SSH deploy key from `DocumenterTools.genkeys`) for docs deploy; `GITHUB_TOKEN` with `contents: write` also works for same-repo deploys.

## 9. What "done to a state-of-the-art standard" means here (acceptance)

Every merged PR: passes `CI` (tests incl. the §2 scientific gates), `format`, and `docs` (doctests + linkcheck) green; updates docs/docstrings for any code change; regenerates derived diagrams (no stale-diagram CI failure); adds/updates an ADR for any non-trivial decision; updates `CHANGELOG.md`; and keeps `MEMORY.md`/`JOURNAL.md` current. The owner can, at any time, open the Documenter site, follow a link to the exact code, read the ADR explaining why it exists, see a current diagram of where it sits, and ask the wiki about it.

## Key tool URLs
Documenter.jl https://documenter.juliadocs.org/stable/ · DocumenterCitations.jl https://juliadocs.org/DocumenterCitations.jl/ · DocumenterMermaid.jl https://github.com/JuliaDocs/DocumenterMermaid.jl · Literate.jl https://fredrikekre.github.io/Literate.jl/ · Quarto (Julia) https://quarto.org/docs/computations/julia.html · Diátaxis https://diataxis.fr/ · MADR https://adr.github.io/madr/ · TestItems/ReTestItems https://github.com/JuliaTesting/ReTestItems.jl · Aqua.jl https://github.com/JuliaTesting/Aqua.jl · JET.jl https://github.com/aviatesk/JET.jl · Supposition.jl https://github.com/Seelengrab/Supposition.jl · ReferenceTests.jl https://github.com/JuliaTesting/ReferenceTests.jl · DifferentiationInterface(Test).jl https://github.com/JuliaDiff/DifferentiationInterface.jl · FiniteDifferences.jl https://github.com/JuliaDiff/FiniteDifferences.jl · AllocCheck.jl https://github.com/JuliaLang/AllocCheck.jl · StableRNGs.jl https://github.com/JuliaRandom/StableRNGs.jl · Runic.jl https://github.com/fredrikekre/Runic.jl · Ruff https://docs.astral.sh/ruff/ · julia-actions https://github.com/julia-actions · DrWatson.jl https://juliadynamics.github.io/DrWatson.jl/ · DVC https://dvc.org/ · MLflow https://mlflow.org/ · Mermaid https://mermaid.js.org/ · D2 https://d2lang.com/ · DeepWiki https://deepwiki.com/ · OpenDeepWiki https://github.com/AIDotNet/OpenDeepWiki · Conventional Commits https://www.conventionalcommits.org/ · Keep a Changelog https://keepachangelog.com/
