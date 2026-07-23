#!/usr/bin/env bash
# SessionStart hook. Inject the live skill inventory + the standing rule that a
# matching skill MUST be consulted before doing a task by hand. This is the
# "make sure created skills actually get used" mechanism — a skill that exists
# but is forgotten is the failure mode this closes.
set -uo pipefail
PROJ="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
SK_DIR="$PROJ/.claude/skills"

INV=""
for f in "$SK_DIR"/*/SKILL.md; do
  [ -f "$f" ] || continue
  n="$(basename "$(dirname "$f")")"
  d="$(sed -n 's/^description:[[:space:]]*//p' "$f" | head -1 | cut -c1-140)"
  INV="${INV}- ${n}: ${d}"$'\n'
done
[ -z "$INV" ] && INV="(no project skills yet)"$'\n'

read -r -d '' MSG <<EOF
SKILL USAGE RULE (this project depends on skills to avoid re-deriving procedures):
Before starting a task, check whether one of these covers it and invoke it — using a
matching skill is expected, not optional. If you re-derive a procedure a skill already
describes, that skill's description is too weak: sharpen it (\`skill-creator\`). If a
recurring task has no skill, create one.

Project skills (.claude/skills/):
${INV}
EOF

jq -n --arg c "$MSG" '{hookSpecificOutput:{hookEventName:"SessionStart", additionalContext:$c}}'
exit 0
