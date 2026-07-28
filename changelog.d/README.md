# `changelog.d/` — changelog fragments (ADR 0029)

`CHANGELOG.md` is written by **inserting at the top**, so two concurrent work lines (ADR 0028) editing it
produce overlapping hunks on the *same lines*, in 20–40-line prose blocks — the worst merge conflict in this
repo (~54 of the first 128 commits touched that file). Fragments remove the conflict entirely: each line
writes its **own new file** here, and the integrator collates them into `CHANGELOG.md`.

## Write a fragment (instead of editing `CHANGELOG.md`)

One file per logical change, named **`<LINE>-<kebab-slug>.md`** — e.g. `S-percell-trait-conditioning.md`,
`M-percell-soil-extractor.md`, `E-wind-cross-grid-remap.md`, `O-terrarium-process-spike.md`.

Start it with the Keep-a-Changelog category as a heading, then the entry exactly as it should read in
`CHANGELOG.md` (same voice and level of detail as existing entries — state the evidence, the numbers, and the
honest caveats):

```markdown
### Added

- **<what landed> ([ADR 00NN](docs/decisions/00NN-....md)).** <what it does, why, the gate it passed with
  numbers, and any honest limitation.> Gated by `test/testitems/<file>.jl`.
```

Categories: `Added` · `Changed` · `Fixed` · `Removed` · `Deprecated` · `Security`.

## Rules

- **Never edit `CHANGELOG.md` from a line branch.** That file is integrator-owned.
- One fragment per logical change; commit it in the **same commit** as the change (Conventional Commits and
  the one-logical-change-per-commit rule are retained from ADR 0013 via ADR 0028).
- The `<LINE>-` prefix is what keeps two lines' filenames disjoint — always include it.

## Collation (integrator, at an integration point)

Merge the lines, then fold every fragment into the top of `CHANGELOG.md`'s `## [Unreleased]` under the right
`###` category, grouping by category rather than by line, and delete the collated fragments in the same
commit. `changelog.d/README.md` itself is never collated or deleted.
