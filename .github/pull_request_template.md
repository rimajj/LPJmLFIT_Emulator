<!--
Acceptance criteria from ENGINEERING_STANDARDS.md §9 ("done to a state-of-the-art
standard"). Every box must be checked (or explicitly N/A with a one-line reason)
before this PR can merge. Required CI checks: `test (lts)`, `test (1)`, `format`,
`docs`.
-->

## Summary

<!-- What does this PR change, and why? Link the issue / ADR / DESIGN section. -->

## Acceptance checklist (ENGINEERING_STANDARDS §9)

### CI gates are green
- [ ] `CI` passes — tests, including the §2 scientific gates (conservation, invariants, reference tests), not just coverage %.
- [ ] `format` passes — code is Runic-formatted.
- [ ] `docs` passes — Documenter builds with **doctests** and **linkcheck** green (the doc↔code consistency gate).
- [ ] `python` passes (if `python/` changed) — `ruff check`, `ruff format --check`, `pytest`.

### Documentation stays true to the code
- [ ] Docstrings added/updated for every new or changed public symbol.
- [ ] Documenter pages (Explanation / Reference, and any tutorials) updated for the change.
- [ ] Every new model equation cites its source paper (`[Key](@cite)`), if applicable.

### Diagrams
- [ ] Derived diagrams regenerated (`scripts/gen_diagrams.jl`) — **no stale-diagram CI failure**.
- [ ] Curated conceptual Mermaid diagrams updated if the derived graph changed.

### Auditability & provenance
- [ ] ADR added/updated in `docs/decisions/` for any non-trivial design decision (problem → options → decision → consequences).
- [ ] `CHANGELOG.md` **Unreleased** section updated (Keep a Changelog format).
- [ ] `MEMORY.md` and `JOURNAL.md` are current.
- [ ] Reproducibility respected: config-driven (no magic numbers), fixed/logged RNG seeds, `Project.toml`/`Manifest.toml` committed.

## Notes for the reviewer / owner

<!--
Point the owner to the exact code, the relevant ADR, and the diagram showing
where this sits — so a non-coder can follow the trail end to end.
-->
