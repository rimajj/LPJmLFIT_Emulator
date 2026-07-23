#!/usr/bin/env bash
# PreToolUse / Bash guard. BLOCK heavy jobs launched directly on the LOGIN NODE (the
# interactive Claude Code shell) and redirect to the durable SLURM wrappers — so the
# login node isn't overloaded and the work survives a dropped session. Blocking IS the
# right behavior here (contrast the non-blocking skill-capture gate). Enforces the
# CLAUDE.md §2 "anything over a few seconds goes to SLURM" rule that prose alone didn't.
set -uo pipefail

INPUT="$(cat)"
CMD="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null)"
[ -z "$CMD" ] && exit 0

# Already inside a SLURM allocation → command runs on a compute node; allow.
[ -n "${SLURM_JOB_ID:-}" ] && exit 0

# Deliberate documented override for a genuinely quick check or the pkg-server-not-mirrored
# fallback (CLAUDE.md §2): prefix the command with ALLOW_LOGIN_HEAVY=1.
printf '%s' "$CMD" | grep -q 'ALLOW_LOGIN_HEAVY=1' && exit 0

# Allow SLURM tooling and the sanctioned wrapper scripts (they submit to a compute node).
printf '%s' "$CMD" | grep -qE '\b(sbatch|srun|salloc|squeue|sacct|scancel|scontrol|sinfo)\b' && exit 0
printf '%s' "$CMD" | grep -qE 'scripts/([a-z0-9_]*(slurm|sbatch)[a-z0-9_]*|run_daily_[a-z0-9_]+|run_fdiff_[a-z0-9_]+)\.(sh|py)' && exit 0

deny() {
  jq -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
}
TAIL="Run it on a compute node instead (spares the login node; survives a dropped session). Genuine seconds-long check or the pkg-server fallback? Prefix ALLOW_LOGIN_HEAVY=1. See CLAUDE.md §2."

# a) Full Julia test suite (the #1 offender).
if printf '%s' "$CMD" | grep -qE '\bjulia\b' && printf '%s' "$CMD" | grep -qE 'Pkg\.test|runtests\.jl|\bruntests[[:space:]]*\('; then
  deny "LOGIN-NODE BLOCK: this runs the full Julia test suite (~5–6 min) on the login node. Submit it: scripts/run_tests_slurm.sh [tag] — then poll 'squeue -u \$USER' and 'tail -f logs/<tag>.<jobid>.out'. $TAIL"
fi
# b) The LPJmL-FIT C binary run directly (execution position, not a file read).
if printf '%s' "$CMD" | grep -qE '(^|[;&|][[:space:]]*|mpirun[[:space:]][^;&|]*|time[[:space:]]+)(\S*/)?bin/lpjml([[:space:]]|$)'; then
  deny "LOGIN-NODE BLOCK: this runs the LPJmL-FIT C binary directly on the login node. Submit it via scripts/run_daily_subset.sh (or the lpjmlfit-cbinary skill's SLURM template). $TAIL"
fi
# c) nohup / backgrounded Julia — dies with the session AND loads the login node.
if printf '%s' "$CMD" | grep -qE '\bnohup\b[^|]*\bjulia\b|\bjulia\b[^|]*&[[:space:]]*$'; then
  deny "LOGIN-NODE BLOCK: a nohup/backgrounded Julia job still dies with the session and loads the login node. Submit it: scripts/sbatch_julia.sh <tag> --project=. <script.jl>. $TAIL"
fi
# d) Heavy foreground Julia script (train/bench/probe/coupled/decadal/validation/…).
if printf '%s' "$CMD" | grep -qE '\bjulia\b[^|]*\b(train|bench|decad|coupl|probe|validat|build_slow|spinup|rollout|experiment|ood|biome)[a-z0-9_]*\.jl'; then
  deny "LOGIN-NODE BLOCK: this looks like a heavy Julia job on the login node. Submit it: scripts/sbatch_julia.sh <tag> --project=. <script.jl> (NN training → scripts/sbatch_train.sh). $TAIL"
fi

exit 0
