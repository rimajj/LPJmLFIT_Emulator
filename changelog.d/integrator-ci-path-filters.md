### Changed

- **CI now runs only when the changed paths can change its verdict (ADR 0090, owner decision).** Every
  workflow was previously unfiltered, so the Julia matrix — four jobs at ~10 min each including macOS — ran
  identically for a change to `src/fdiff.jl` and for a sentence in a LaTeX report. Each gate now declares its
  inputs: `CI` ← `src/** ext/** test/** Project.toml docs/src/generated/**`; `format` ← any `**/*.jl`;
  `python` ← `python/**`; `docs` ← `docs/src/** docs/make.jl docs/Project.toml src/** Project.toml`.
  All four also gain `workflow_dispatch` so any gate can be forced on demand.
- **A prose/docs/skill/ADR/handoff-only commit now triggers no gate and is mergeable immediately.** Note the
  consequence: a workflow that does not trigger reports **no check-run at all** (not a "skipped" one), so a
  poll that waits for `test (lts)` to complete hangs forever. The merge ritual now derives the expected gate
  set from `git diff --name-only origin/main...HEAD`. Updated in `CLAUDE.md` §5/§9, the `repo-commit` skill,
  `ENGINEERING_STANDARDS.md`, `STEERING_PROMPT.md` and `MEMORY.md`.
- ADR numbering: the cross-cutting block 0001–0029 is exhausted; **0090–0099 is now the integrator block**.
