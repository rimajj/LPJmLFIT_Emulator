# 0319 — One development stream: the parallel work lines are retired

* **Status:** **Accepted (owner decision, 2026-10-10).**
* **Supersedes:** ADR 0028 (parallel session lines), ADR 0029 (line split and ownership map), the line-X charter
  (`lines/X/STATE.md` "explores, never implements; never writes into another line"), and CLAUDE.md §9's protocol.
  **Restores** ADR 0013's single-branch workflow (work on `main`), with everything ADR 0028 added that is not about
  lines kept (the CI path table of ADR 0090, changelog collation of ADR 0095, SLURM discipline).
* **Does not change:** the goal (ADR 0094/0106/0107, restated by the owner in ADR 0318), the guardrails (CLAUDE.md §6),
  the CO2 closure, the reuse/licensing closure.

## 1. The owner's words

> "change of plans. the otehr lines stem frmo the beginning of the project, where slow and fast part was deevlopte in
> parralel, as well as the coupling etc. abandon this. I want you to deveop all, no seperation in different lines"

## 2. Why the lines no longer fit (record)

The lines were created (2026-07-28) because one serial session was slow and the architecture had separable components
(slow demography S, fast daily physics F/M, energy E, online coupling O). Since then: the fast physics was measured to
be slower than the original (ADR 0084), the goal became a full learned emulator of structure **and** daily exchange
(ADR 0318), and the lines M, E and O have had no session since 2026-08-19 (S since 2026-10-08). Work items that span
the split — e.g. the learned daily water–carbon model, assigned to O but needing M's oracle — were left unstarted
because each side was the other's integration point. All five line branches were fully merged into `main` with nothing
uncommitted when this decision was taken (verified 2026-10-10).

## 3. What changes

| before | now |
|---|---|
| 5 line branches + worktrees (`wt-S/M/E/O/X`), `main` integration-only | **one branch, `main`, in `/p/projects/open/Jamir/esm_land_emulator`.** The `wt-*` worktrees and `line/*` branches stay as frozen history (not deleted; removal is the owner's call) |
| per-line `lines/<X>/STATE.md` + `JOURNAL.md` | **root `STATE.md`** (current state + the `## NEXT` handoff the SessionStart hook replays) and **root `JOURNAL.md`** (append). `lines/*/` are archived, read-only history |
| ownership map, integration points, additive-only regions | none: one developer owns every path. Additive regions in shared files may be tidied |
| ADR number blocks per line | **one sequence: the next free number** (0320 after this one) |
| `changelog.d/<X>-*.md` fragments, collated at merge | still allowed (`scripts/collate_changelog.py`, the `changelog` gate) — collate before each push to `main`; editing `CHANGELOG.md` directly is fine too |
| SLURM tag prefix per line | a short descriptive tag; no prefix required |
| rebase → force-push line branch → wait branch CI → flock merge | **commit on `main`, run the CI-equivalent checks your diff triggers (CLAUDE.md §5 path table), push, then check `main`'s CI** |

## 4. Consequences

* The order of work is `EXECUTION_PLAN.md` revision 3 (same commit): goal-first priorities instead of per-line
  assignments. Its tracks and decision points stay as the method inventory.
* Skills that describe the line protocol (`repo-commit` foremost) carry a superseded note until rewritten.
* `~/.claude/CLAUDE.md` (owner's global file) lists the `wt-*` paths and the old acceptance rule; updated in the same
  change so a fresh session does not reapply them.
