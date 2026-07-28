# Retired session-prompt files

`NEXT_SESSION_PROMPT.md` (193 lines) and `DESIGN_CHECKPOINT_PROMPT.md` (86 lines) were **orphans** — not
referenced by `00_START_HERE.md` or `CLAUDE.md` §7, and stale (they predate ADR 0023–0029; e.g. they still
describe P1 as blocked). A fresh session that found one by name would onboard from wrong state, which is the
exact failure the router exists to prevent. Retired here 2026-07-28 (ADR 0028/0029), alongside the earlier
`HANDOFF_NEXT_SESSION.md` tombstone's anti-growth clause.

**Do not recreate this pattern.** Onboarding is: `00_START_HERE.md` (router) → `CLAUDE.md` (runbook) →
`lines/<X>/STATE.md` (your line's state + its `## NEXT` handoff) → `MEMORY.md` (shared facts). A session's
next action belongs in its line's `STATE.md`, surfaced automatically by the `SessionStart` hook — not in a
hand-maintained prompt file at the repo root.
