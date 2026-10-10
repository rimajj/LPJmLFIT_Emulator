#!/usr/bin/env bash
# SessionStart hook — ONE DEVELOPMENT STREAM (ADR 0319, owner decision 2026-10-10; supersedes the parallel-lines
# hook of ADR 0028/0029). Replays the `## NEXT — start here` block of the root STATE.md, the single handoff.
#
# The corollary duty: the ENDING session refreshes that block. This hook only surfaces what that session wrote.
# File name kept so .claude/settings.json needs no change.
set -uo pipefail
PROJ="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$PROJ" 2>/dev/null || exit 0
MAIN=/p/projects/open/Jamir/esm_land_emulator

BRANCH="$(git -C "$PROJ" symbolic-ref --short -q HEAD 2>/dev/null || echo '(detached HEAD)')"

WARN=""
case "$BRANCH" in
    main) ;;
    line/*) WARN="⚠️ You launched in a RETIRED line worktree (\`${PROJ}\`, branch \`${BRANCH}\`). The parallel lines were abandoned on 2026-10-10 (ADR 0319). Do NOT develop here — work in \`${MAIN}\` on \`main\`. This worktree is frozen history." ;;
    *) WARN="⚠️ HEAD is on \`${BRANCH}\`, not \`main\`. The project develops on \`main\` (ADR 0319); finish or abort whatever left HEAD here before feature work." ;;
esac

# Always the MAIN checkout's STATE.md: a retired worktree carries a stale copy (or none).
STATE="$MAIN/STATE.md"
if [ -f "$STATE" ]; then
    NEXT="$(awk '
        /^```/            { fence = !fence }
        /^## NEXT/        { f = 1 }
        f && !fence && /^## / && !/^## NEXT/ { exit }
        f
    ' "$STATE")"
else
    NEXT="(STATE.md is missing — read ADR 0319 and recreate it before feature work.)"
fi
[ -z "$NEXT" ] && NEXT="(no '## NEXT — start here' block in STATE.md — the previous session left no handoff.)"

DIRTY="$(git -C "$PROJ" status --porcelain 2>/dev/null | head -12)"
DIRTY_NOTE=""
[ -n "$DIRTY" ] && DIRTY_NOTE=$'\n''UNCOMMITTED WORK IS ALREADY HERE (a previous session left it) — review before editing:'$'\n'"${DIRTY}"$'\n'
AHEAD="$(git -C "$PROJ" rev-list --count "origin/main..HEAD" 2>/dev/null || echo '?')"
BEHIND="$(git -C "$PROJ" rev-list --count "HEAD..origin/main" 2>/dev/null || echo '?')"

read -r -d '' MSG <<EOF
== LPJmL-FIT emulator — ONE DEVELOPMENT STREAM (ADR 0319) ==
worktree \`${PROJ}\` · branch \`${BRANCH}\` · ${AHEAD} ahead / ${BEHIND} behind \`origin/main\`
${WARN}${DIRTY_NOTE}
YOUR NEXT ACTION (verbatim from STATE.md — the previous session's handoff):

${NEXT}

WORKING RULES (full: CLAUDE.md §9)
- One developer owns every path; there are no lines, ownership maps or integration points any more.
- Read STATE.md in full first (goal, relaxed pass standard, where each part stands), then EXECUTION_PLAN.md.
- Narrative -> JOURNAL.md (append). State + NEXT -> STATE.md. Cross-cutting facts -> MEMORY.md. Decisions -> an ADR
  with the next free number. Changelog -> CHANGELOG.md or a changelog.d/ fragment collated before pushing.
- Commit on main (Conventional Commits, one logical change), run the CI-equivalent checks your diff triggers
  (CLAUDE.md §5 path table), push, then check main's own CI.
- Anything longer than a few seconds -> SLURM (hook-enforced). Data never in /home (owner rule).
- BEFORE THE SESSION ENDS: refresh the NEXT block in STATE.md and commit it.
EOF

jq -n --arg c "$MSG" '{hookSpecificOutput:{hookEventName:"SessionStart", additionalContext:$c}}'
exit 0
