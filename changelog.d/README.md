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

## Collation — WHOEVER MERGES TO `main` DOES IT, IN THE SAME `flock` (ADR 0095)

**Run the script; do not collate by hand:**

```bash
python3 scripts/collate_changelog.py            # fold fragments in, delete them
python3 scripts/collate_changelog.py --check     # exit 1 if main carries uncollated fragments
python3 scripts/collate_changelog.py --dry-run   # print the block, change nothing
```

It folds every fragment into the top of `## [Unreleased]`, grouped by category rather than by line,
inserting **one new group of `### <Category>` sections** (matching the file's existing shape — it does not
reorganise what is already there, so the diff is purely additive), and deletes the collated fragments.
`changelog.d/README.md` itself is never collated or deleted. Re-running with no fragments is a no-op.

**The trigger is the merge, not a role.** The earlier rule — *"the integrator collates at an integration
point"* — named no event that reliably happens, because every line self-merges (ADR 0028) and there is no
central orchestrator to attend such a point. 56 fragments then accumulated over 13 days while `CHANGELOG.md`
was edited three times. So: **the session that merges its line to `main` collates whatever fragments are on
`main`, inside the same `flock`, and pushes the collation with the merge.** That does not violate
"never edit `CHANGELOG.md` from a line branch" — you are editing it *on `main`*, in the integration
worktree, which is the integrator role, held for the moment you hold the lock.

**Safety net:** the `changelog` CI gate runs `--check` on `main` only (a fragment on a *line* branch is
correct — that is where fragments are authored; it is debt only once it reaches `main`). If a merge skips
collation, `main` goes red with the exact list, so the debt can never again be invisible.

**Categories** are validated against a fixed list in the script, so a typo cannot silently invent a section:
the six Keep-a-Changelog ones plus the extras this project already uses — `Documentation`, `Validation`,
`Verified`, `Measured`, `Verdict`, `Gates`, `Notes` (`Documented` is an alias of `Documentation`). Adding one
is a deliberate edit to `CANONICAL_ORDER`. A heading may carry a parenthetical qualifier, e.g.
`### Verdict (497 936 tower steps, 4 sites)`; it is preserved as an italic lead-in above that chunk's bullets.
A fragment may contain **several** `###` sections — most do.
