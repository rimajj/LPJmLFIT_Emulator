#!/usr/bin/env bash
# SessionStart hook — PARALLEL WORK LINES (ADR 0028/0029).
#
# This is the handoff mechanism. A session's LINE identity is the branch checked out in the worktree it was
# launched from (`/p/projects/open/Jamir/wt-S` has `line/S`, ...), so the owner never has to say which line a
# fresh session is on — the directory already did. This hook resolves branch -> line and injects that line's
# ownership block plus its `## NEXT — start here` action (verbatim from `lines/<X>/STATE.md`) into the new
# session's context.
#
# The corollary duty, enforced in the repo-commit skill: the ENDING session refreshes its own STATE.md NEXT
# block. This hook only surfaces what that session wrote — it cannot invent continuity.
set -uo pipefail
PROJ="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$PROJ" 2>/dev/null || exit 0

BRANCH="$(git -C "$PROJ" symbolic-ref --short -q HEAD 2>/dev/null || true)"

# DETACHED HEAD recovery (adversarial review, 2026-07-28). Mid-rebase/bisect/`checkout <sha>` leaves HEAD
# detached, `rev-parse --abbrev-ref HEAD` then returns the literal "HEAD", the `line/*` case below misses, and
# the session would be told it is the INTEGRATOR while sitting in a line worktree with a half-finished rebase —
# losing the handoff exactly when it matters most. Recover the intended branch from the in-progress operation,
# then from the worktree directory name (`…/wt-S` -> line/S), and say so loudly.
DETACHED_NOTE=""
if [ -z "$BRANCH" ]; then
    gitdir="$(git -C "$PROJ" rev-parse --git-dir 2>/dev/null || echo '')"
    for f in rebase-merge/head-name rebase-apply/head-name; do
        if [ -n "$gitdir" ] && [ -f "$gitdir/$f" ]; then
            BRANCH="$(sed 's|^refs/heads/||' "$gitdir/$f" 2>/dev/null || true)"
            [ -n "$BRANCH" ] && DETACHED_NOTE="A REBASE/AM IS IN PROGRESS in this worktree (HEAD is detached; intended branch \`${BRANCH}\`). Finish it (\`git rebase --continue\`) or abort it (\`git rebase --abort\`) BEFORE doing feature work."
            break
        fi
    done
    if [ -z "$BRANCH" ]; then
        base="$(basename "$PROJ")"                       # wt-S -> S
        case "$base" in
            wt-?) BRANCH="line/${base#wt-}"
                DETACHED_NOTE="HEAD is DETACHED in this worktree and no rebase/am state was found; the line was inferred from the directory name (\`${base}\`). Restore it with \`git switch ${BRANCH}\` (or \`git bisect reset\`) before committing — a commit made on a detached HEAD belongs to no branch and is easy to lose." ;;
            *) BRANCH="(detached HEAD)" ;;
        esac
    fi
fi

# Line letter from the branch name (`line/S` -> S). Empty => not a line worktree.
LINE=""
case "$BRANCH" in
    line/*) LINE="${BRANCH#line/}" ;;
esac

if [ -z "$LINE" ]; then
    read -r -d '' MSG <<EOF
PARALLEL WORK LINES (ADR 0028/0029) — LINE: none (branch \`${BRANCH}\`, integrator worktree).

You are NOT on a work line, so feature work does not belong here. This worktree is for INTEGRATION and
shared/cross-cutting edits only: merging lines, collating \`changelog.d/*\` into \`CHANGELOG.md\`, reconciling
the shared \`MEMORY.md\`, \`Project.toml\` dependency changes, and cross-cutting ADRs (block 0001-0029).

To work a line, launch a session in ITS worktree instead:
  cd /p/projects/open/Jamir/wt-S   # line/S — Component-S science
  cd /p/projects/open/Jamir/wt-M   # line/M — multi-cell coupled S+F+E (P3)
  cd /p/projects/open/Jamir/wt-E   # line/E — Component E vs observations (P2)
  cd /p/projects/open/Jamir/wt-O   # line/O — online coupling: Terrarium + SpeedyWeather (P4/P5)

Protocol: \`CLAUDE.md\` §9. Ownership map + frozen cross-line contracts: ADR 0029. Line state: \`lines/<X>/STATE.md\`.
EOF
    jq -n --arg c "$MSG" '{hookSpecificOutput:{hookEventName:"SessionStart", additionalContext:$c}}'
    exit 0
fi

STATE="$PROJ/lines/$LINE/STATE.md"
if [ ! -f "$STATE" ]; then
    read -r -d '' MSG <<EOF
PARALLEL WORK LINES (ADR 0028/0029) — you are on branch \`${BRANCH}\` (LINE ${LINE}), but
\`lines/${LINE}/STATE.md\` is MISSING. Do not guess the line's scope: read ADR 0029 (the ownership map) and
\`CLAUDE.md\` §9, then recreate the STATE.md before doing feature work.
EOF
    jq -n --arg c "$MSG" '{hookSpecificOutput:{hookEventName:"SessionStart", additionalContext:$c}}'
    exit 0
fi

# Line title = the STATE.md H1, minus the leading "# " (it already reads "LINE X — <scope> (branch …)").
TITLE="$(sed -n '1s/^#[[:space:]]*//p' "$STATE")"
[ -z "$TITLE" ] && TITLE="LINE $LINE"

# The NEXT block: from the `## NEXT` heading to (but excluding) the following `## ` heading. A ``` fenced
# block inside NEXT is tracked, so a line starting with `## ` INSIDE a code fence (a shell comment, a diff
# hunk) no longer truncates the handoff mid-way (adversarial review, 2026-07-28).
NEXT="$(awk '
    /^```/            { fence = !fence }
    /^## NEXT/        { f = 1 }
    f && !fence && /^## / && !/^## NEXT/ { exit }
    f
' "$STATE")"
[ -z "$NEXT" ] && NEXT="(no '## NEXT — start here' block in lines/$LINE/STATE.md — the previous session did not leave a handoff. Read the Milestones section and pick up the first unfinished one.)"

# Uncommitted work left behind by a previous session in this worktree (a real handoff hazard).
DIRTY="$(git -C "$PROJ" status --porcelain 2>/dev/null | head -12)"
DIRTY_NOTE=""
if [ -n "$DETACHED_NOTE" ]; then
    DIRTY_NOTE=$'\n''⚠️ '"${DETACHED_NOTE}"$'\n'
fi
if [ -n "$DIRTY" ]; then
    DIRTY_NOTE="${DIRTY_NOTE}"$'\n''UNCOMMITTED WORK IS ALREADY IN THIS WORKTREE (a previous session left it) — review before editing:'$'\n'"${DIRTY}"$'\n'
fi

# How far this branch has drifted from main (rebase early, merge often — ADR 0028).
BEHIND="$(git -C "$PROJ" rev-list --count "HEAD..origin/main" 2>/dev/null || echo '?')"
AHEAD="$(git -C "$PROJ" rev-list --count "origin/main..HEAD" 2>/dev/null || echo '?')"

read -r -d '' MSG <<EOF
== ${TITLE} ==
worktree \`${PROJ}\` · ${AHEAD} commit(s) ahead of / ${BEHIND} behind \`origin/main\`
${DIRTY_NOTE}
YOUR NEXT ACTION (verbatim from lines/${LINE}/STATE.md — the previous session's handoff):

${NEXT}

WORKING RULES FOR THIS LINE (full protocol: \`CLAUDE.md\` §9; ownership map: ADR 0029)
- Read \`lines/${LINE}/STATE.md\` in full before starting — it carries this line's scope, the paths you own,
  the paths you MUST NOT touch, the frozen cross-line contracts, and this line's gotchas.
- Stay inside your owned paths. Editing another line's exclusive path is a protocol violation — raise it as an
  integration point instead. Shared files (\`src/LPJmLFITEmulator.jl\`, \`CLAUDE.md\`, \`MEMORY.md\`) are
  additive-only, inside your \`# ── line ${LINE} ──\` region where one exists.
- Narrative -> \`lines/${LINE}/JOURNAL.md\` (append). Durable line state -> \`lines/${LINE}/STATE.md\`.
  Cross-cutting durable facts -> \`MEMORY.md\`. Changelog -> a NEW \`changelog.d/${LINE}-<slug>.md\` fragment
  (NEVER edit \`CHANGELOG.md\` from a line). Decisions -> an ADR from THIS line's block.
- SLURM tag prefix \`${LINE}-\` so \`squeue\` and \`logs/\` stay attributable. Other lines' \`/p/tmp\` artifacts
  are read-only.
- Commit/merge ritual — \`repo-commit\` skill has the full version; the load-bearing parts:
  (1) \`git pull --rebase origin main\` in THIS worktree; (2) \`git push --force-with-lease origin ${BRANCH}\`
  (the rebase rewrote already-pushed commits, so a plain push is REJECTED non-fast-forward; the lease is safe
  because one session owns this line); (3) branch CI green on THAT sha (\`test (lts)\`, \`test (1)\`, \`format\`,
  \`python\`; \`test (pre)\` is allowed-to-fail and currently red for unrelated prerelease churn) — a pre-rebase
  green verdict does NOT carry over; (4) integrate WITHOUT switching branches here (\`git switch main\` FAILS in
  a line worktree: main is checked out in the integration worktree) —
  \`flock <INT>/.git/esm-integrate.lock bash -eu -c 'git -C "\$0" pull --ff-only origin main; git -C "\$0" merge --no-ff --no-edit origin/${BRANCH}; git -C "\$0" push origin main' /p/projects/open/Jamir/esm_land_emulator\`
  — merging \`origin/${BRANCH}\` guarantees the exact CI-verified sha lands, and the lock serialises the one
  shared main worktree; (5) then check **main's own latest** CI run (format/docs/python/Aqua/JET are
  whole-package gates, so green branches do not guarantee a green main; and GitHub keeps only one *pending* run
  per branch, so a rapid follow-up push can cancel an intermediate main verdict — the newest sha is the one that
  reports). Merge at every milestone, never hoard.
- BEFORE THIS SESSION ENDS (or when context runs low): refresh the \`## NEXT — start here\` block in
  \`lines/${LINE}/STATE.md\` and commit it. That block IS the handoff to the next session — this message is
  generated from it.
EOF

jq -n --arg c "$MSG" '{hookSpecificOutput:{hookEventName:"SessionStart", additionalContext:$c}}'
exit 0
