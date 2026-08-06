# What is in `docs/`

Five different kinds of thing live under `docs/`, and they are not interchangeable. This file says
which is which, so nobody has to guess again.

| Path | What it is | Published? | Triggers CI? |
|---|---|---|---|
| `src/` | **The documentation website source** (Documenter.jl page tree). The published, strict-built docs. | yes — GitHub Pages | `docs` gate |
| `src/generated/` | **Auto-generated** Mermaid diagrams. Do not hand-edit; regenerate with `scripts/gen_diagrams.jl`. | yes | `CI` + `docs` |
| `src/assets/diagrams/` | **Hand-curated** Mermaid diagrams (the owner's mental model). | yes | `docs` |
| `make.jl`, `Project.toml` | The docs build itself. | — | `docs` gate |
| `decisions/` | **Decision records.** Immutable once accepted — supersede, never edit. | no | none |
| `notes/` | **Engineering notes** — design specs, phase validation write-ups, data specs. Working documents, referenced by name from source files and tests. | no | none |
| `report/` | The general-audience LaTeX report + its figures (`report/figs/`). | no | none |
| `archive/` | Retired prompts and pre-consolidation snapshots. Kept for provenance. | no | none |
| `third_party_licensing.md` | The reuse + citation register (one of four citation surfaces). | no | none |
| `build/` | Local build output. **Git-ignored** — never commit it. | — | — |

## Two things that surprise people

**Most of `docs/` triggers no CI at all.** Only `docs/src/**`, `docs/make.jl` and `docs/Project.toml`
are watched by the `docs` gate. The decision records, the notes, the LaTeX report and its figures all
sit under `docs/` but are in no Documenter page, so changing them produces **no check-run whatsoever** —
not a skipped one. A merge poll that waits for a named check to complete will hang forever on such a
commit. Work out the expected gate set from `git diff --name-only origin/main...HEAD` first.

**`notes/` is not the website.** Files there are not built, not link-checked and not published. They are
long-form working documents that source files and tests point at by name (for example
`notes/phase3_fdiff_cbinary_validation.md` is cited from `src/fdiff.jl` and about ten test files). Treat
a section number in one of them as a durable reference.

## Where a new document belongs

- Something the owner or an outside reader should be able to *read as documentation* → `docs/src/`,
  and add it to the page list in `docs/make.jl` (a file not in that list is never built).
- A decision, with its rationale and alternatives → a new numbered record in `docs/decisions/`
  (number blocks are assigned per work line — see `CLAUDE.md` §9).
- A long engineering write-up, spec or validation log → `docs/notes/`.
- Session narrative → `lines/<X>/JOURNAL.md`, not here.
- Durable current state → `lines/<X>/STATE.md`, or the repo-root `MEMORY.md` if cross-cutting.

## Note on a 2026-08-06 reorganisation

The engineering notes and the LaTeX report used to sit loose at the top level of `docs/`, mixed in with
the website source. They moved to `docs/notes/` and `docs/report/` on 2026-08-06; the report's figures
moved with it to `docs/report/figs/`. References were updated everywhere except in **append-only
history** — `CHANGELOG.md`, `JOURNAL.md`, `docs/archive/**` and the immutable numbered decision records
— which correctly describe where the files were at the time of writing. If an older entry says
`docs/phase3_...md` or `docs/figs/...`, look under `docs/notes/` or `docs/report/figs/`.
