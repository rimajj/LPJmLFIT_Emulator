#!/usr/bin/env bash
# PostToolUse / Skill hook. Append one line per skill invocation so consolidate-memory
# can find never-used skills (flood control) and duplicates worth merging. Logging only
# — no stdout, never blocks.
set -uo pipefail
PROJ="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
LOG="$PROJ/.claude/skill-usage.log"

cat | jq -c '{ts:(now|todate), skill:(.tool_input.skill // .tool_input.name // "?"), event:.hook_event_name}' >> "$LOG" 2>/dev/null || true
exit 0
