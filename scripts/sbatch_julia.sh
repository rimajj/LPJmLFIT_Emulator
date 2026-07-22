#!/usr/bin/env bash
# =============================================================================
# sbatch_julia.sh — submit ANY Julia work to SLURM as a batch job on a COMPUTE
# NODE, so it SURVIVES session teardown (dropped SSH, agent restart, UI stop).
#
# WHY: the login-node shell dies with the interactive/agent session. Anything
# launched there (a `julia` foreground run, `nohup ... &`, a background Bash tool
# call) is lost when the session breaks — you come back to a half-finished run and
# no result. A SLURM job runs independently on a compute node, writes its log to
# shared /p (readable by any future session), and its status survives via
# squeue/sacct. THIS IS THE DEFAULT for anything that takes more than a few
# seconds (the suite, benchmarks, probes, training, decadal coupled runs).
#
# Usage:
#   scripts/sbatch_julia.sh <TAG> [julia args...]
# examples:
#   scripts/sbatch_julia.sh bench --project=. scripts/bench_slow_speedup.jl
#   scripts/sbatch_julia.sh probe --project=. scripts/foo_probe.jl
#   scripts/sbatch_julia.sh quick --project=. -e 'using LPJmLFITEmulator; @info "ok"'
#
# Env overrides: TIME (default 01:00:00), NCPUS (4), ACCOUNT (waldspektrum),
# PARTITION (standard), QOS (short), JULIA (1.10.0 lts), WARMUP (1 => a login-node
# `Pkg.instantiate` of --project=. first, so the compute node needs no network;
# set WARMUP=0 to skip). The job reuses the shared warm depot JULIA_DEPOT_PATH=
# $HOME/.julia — compute nodes CAN reach the Julia pkg-server (tarballs), only
# GitHub git-clones are blocked, so a warm depot => zero network on the node.
#
# Watch / collect (from ANY later session):
#   squeue -u "$USER"
#   tail -f logs/<TAG>.<jobid>.out
#   sacct -j <jobid> --format=JobID,State,Elapsed,ExitCode,MaxRSS
# The job prints "=== JOB DONE tag=<TAG> exit=<code> ===" as its last line, so a
# future session can grep the log to know it finished (and with what status)
# without a live process to poll.
# =============================================================================
set -euo pipefail

TAG="${1:?usage: sbatch_julia.sh <TAG> [julia args...]}"; shift
[ "$#" -ge 1 ] || { echo "error: no julia args given (e.g. --project=. script.jl)" >&2; exit 1; }

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JULIA="${JULIA:-/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia}"
ACCOUNT="${ACCOUNT:-waldspektrum}"; PARTITION="${PARTITION:-standard}"; QOS="${QOS:-short}"
TIME="${TIME:-01:00:00}"; NCPUS="${NCPUS:-4}"; WARMUP="${WARMUP:-1}"
LOGDIR="${REPO}/logs"; mkdir -p "${LOGDIR}"

# Login-node warm-up (network-safe here): make sure --project=. deps are present +
# precompiled in the shared depot so the compute node needs no egress. Idempotent,
# usually a fast no-op once the depot is warm. Skipped if WARMUP=0.
if [ "${WARMUP}" = "1" ]; then
    echo "warming shared depot on the login node (Pkg.instantiate/precompile --project=.) ..."
    JULIA_DEPOT_PATH="${JULIA_DEPOT_PATH:-$HOME/.julia}" "${JULIA}" --project="${REPO}" \
        -e 'import Pkg; Pkg.instantiate(); Pkg.precompile()' || \
        echo "  (warm-up non-fatal error; continuing — the node will try the pkg-server)"
fi

jcf="$(mktemp)"
# shellcheck disable=SC2086
cat > "${jcf}" <<EOF
#!/usr/bin/env bash
#SBATCH --job-name=jl_${TAG}
#SBATCH --account=${ACCOUNT}
#SBATCH --partition=${PARTITION}
#SBATCH --qos=${QOS}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=${NCPUS}
#SBATCH --time=${TIME}
#SBATCH --output=${LOGDIR}/${TAG}.%j.out
#SBATCH --error=${LOGDIR}/${TAG}.%j.out
set -uo pipefail
cd "${REPO}"
export JULIA_DEPOT_PATH="\${JULIA_DEPOT_PATH:-\$HOME/.julia}"
export JULIA_NUM_THREADS=${NCPUS}
echo "=== jl_${TAG} on \$(hostname) at \$(date) ==="
${JULIA} $*
code=\$?
echo "=== JOB DONE tag=${TAG} exit=\${code} ==="
exit \${code}
EOF

jid="$(sbatch "${jcf}" | awk '{print $NF}')"
rm -f "${jcf}"
echo "submitted job ${jid}: julia $* (tag=${TAG}, ${PARTITION}/${QOS}, ${NCPUS} cpus, ${TIME})"
echo "  log:   ${LOGDIR}/${TAG}.${jid}.out"
echo "  watch: squeue -u ${USER} -j ${jid}   |   tail -f ${LOGDIR}/${TAG}.${jid}.out"
echo "  done?: grep -q 'JOB DONE' ${LOGDIR}/${TAG}.${jid}.out   (last line has the exit code)"
