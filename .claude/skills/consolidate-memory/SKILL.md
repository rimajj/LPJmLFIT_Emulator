---
name: consolidate-memory
description: The every-~5-sessions reshape of the repo-root MEMORY.md back to durable-state-only under its cap (≤400 lines / ≤15k tokens), plus skill hygiene — audit the skill set for duplicates and never-used skills, sharpen weak descriptions, promote recurring JOURNAL notes into skills. Use when MEMORY.md has grown past its cap or accreted session narrative, on the ~5-session cadence, or when the skill set needs a dedup/prune pass so the workspace isn't flooded with overlapping or dead skills.
---

# consolidate-memory — reshape MEMORY.md + prune the skill set

Two jobs on the same ~5-session cadence: keep `MEMORY.md` (repo root) to *current durable state only*, and
keep `.claude/skills/` lean (no duplicates, no dead skills). Both fight the same failure mode — bloat that
makes onboarding slower and buries the signal.

## Part A — reshape MEMORY.md

`MEMORY.md` is the repo-root durable-state file (NOT `JOURNAL.md`, NOT the runbook `CLAUDE.md`). Cap:
**≤ 400 lines / ≤ 15k tokens** (stated in its own header).

1. **Measure.** `wc -l MEMORY.md` and eyeball the token size. If under cap and still durable-state-only,
   stop — don't reshape for its own sake.
2. **Keep only durable state:** verified facts (`[VERIFIED]`), the frozen-decision *index* (one line per
   ADR, pointing at `docs/decisions/`, not the reasoning), phase status, open `[TODO]`s.
3. **Move everything else out — don't delete it:**
   - session narrative / "what happened this session" → append to `JOURNAL.md`;
   - the story behind one change → `CHANGELOG.md`;
   - a resolved decision's full reasoning → its ADR (MEMORY keeps just the index line).
4. **Archive big removals** (don't delete — git has it, but leave a human pointer): write the pre-reshape
   copy to `docs/archive/MEMORY_<YYYY-MM-DD>_pre-consolidation.md` and note it in the MEMORY.md header
   (follow the existing `2026-07-22` pointer as the pattern).
5. **Re-check the cap** after reshaping. Convert any relative dates to absolute while you're in there.

## Part B — skill hygiene (flood control — this is why the workspace doesn't fill with dead skills)

1. **Inventory:** `for f in .claude/skills/*/SKILL.md; do sed -n '2,3p' "$f"; done` (name + description).
2. **Usage:** if `.claude/skill-usage.log` exists, tally invocations. A skill with **zero** invocations
   across many sessions is a candidate to **delete** (or its description is too weak to trigger — decide
   which; see step 4).
3. **Dedup / merge:** two skills covering overlapping procedures → merge into one and delete the other.
   Prefer one well-scoped skill over two half-scoped ones (the `skill-creator` rule: update, don't fork).
4. **Sharpen, don't just delete:** a never-used skill whose *task* still recurs usually has a weak
   `description` (the field that decides whether it triggers). Rewrite the description with the exact verbs
   and artifact names of the task (use the `skill-creator` skill), then keep it one more cycle before
   deciding to delete.
5. **Promote:** recurring notes/scripts that keep reappearing in `JOURNAL.md` but have no skill → create
   one (via `skill-creator`).
6. **Record what you removed** in `JOURNAL.md` (deleted/merged skill X because zero use over N sessions),
   so the decision is auditable.

## Wrap

Commit the reshaped `MEMORY.md`, any archived copy, and skill changes together (main-only, ADR 0013;
`repo-commit` skill). Note in the commit body what was archived and which skills were merged/deleted.
This skill did not exist before 2026-07-23 — the docs referenced it (`STEERING_PROMPT.md`, `repo-commit`)
before it was written.
