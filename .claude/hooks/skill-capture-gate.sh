#!/usr/bin/env bash
# PostToolUse / Bash hook. After a successful `git commit`, inject a NON-BLOCKING
# checklist that makes the model EVALUATE whether a skill should be created/updated
# — not auto-create one. The anti-flood judgment (dedup, skip one-offs) lives in the
# injected text; the model does the judging because only it has the session context.
set -uo pipefail
PROJ="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

INPUT="$(cat)"
CMD="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null)"

# Only react to a real `git commit` invocation — at command start or after a shell
# separator (catches `git add … && git commit …`), NOT the phrase inside a message/echo.
printf '%s' "$CMD" | grep -qE '(^|[;&|])[[:space:]]*git[[:space:]]+commit' || exit 0

# Live skill inventory so the model can check "is this already covered?"
SKILLS="$(ls -1 "$PROJ/.claude/skills" 2>/dev/null | sort | paste -sd, -)"
[ -z "$SKILLS" ] && SKILLS="(none yet)"

read -r -d '' MSG <<EOF
SKILL-CAPTURE CHECK (post-commit — evaluate, do NOT reflexively create).
Ask, about the work in this commit:
  1. Did it include a rerunnable script, a non-obvious fix, or a procedure a future session would repeat? If NO → do nothing.
  2. If YES — is it already covered by an existing skill? Existing skills: ${SKILLS}.
       • Covered → UPDATE that skill (add the gotcha/variant); do NOT create a near-duplicate.
       • Not covered AND likely to recur → create it with the \`skill-creator\` skill.
       • One-off, or unlikely to be reused → do NOT create a skill (an unused/duplicate skill is debt).
  3. If you create or update one, commit it as an immediate follow-up ("chore(skill): <name>").
Bias: this project historically UNDER-creates skills — when in genuine doubt and it will recur, capture it.
EOF

jq -n --arg c "$MSG" '{hookSpecificOutput:{hookEventName:"PostToolUse", additionalContext:$c}}'
exit 0
