#!/usr/bin/env bash
# =============================================================================
# run_tests_slurm.sh — run the CI-faithful Julia test suite as a SLURM job on a
# COMPUTE NODE, so a full `Pkg.test()` (~6-10 min) SURVIVES session teardown.
#
# This is the durable counterpart of the login-node command in CLAUDE.md §2. It
# preserves the CI-faithful contract (delete test/Manifest.toml first => fresh
# re-resolve to newest-allowed deps, exactly like CI) but runs it off the login
# node so a dropped session no longer loses the result.
#
# Network safety (the CLAUDE.md §2 caveat): compute nodes have NO GitHub egress
# but CAN reach the Julia pkg-server (tarballs). This script first WARMS the
# shared depot on the login node (instantiate + precompile --project=.), so the
# fresh re-resolve on the node finds every dep cached and needs no network. The
# only residual risk is a dep version so new the pkg-server hasn't mirrored it yet
# (a git-clone-only race) — that fails with a clear "Network is unreachable" in
# the log; the fallback is the plain login-node run in CLAUDE.md §2.
#
# Usage:  scripts/run_tests_slurm.sh [RUNTAG]      (default tag: test_suite)
# Watch:  squeue -u "$USER"  |  tail -f logs/<tag>.<jobid>.out
# Result: the log's LAST line is "=== JOB DONE tag=<tag> exit=<code> ===" and the
#         ReTestItems summary ("N pass, M fail") is just above it — a future
#         session greps the log; no live process needed.
# =============================================================================
set -euo pipefail

RUNTAG="${1:-test_suite}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JULIA="${JULIA:-/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia}"
ACCOUNT="${ACCOUNT:-waldspektrum}"; PARTITION="${PARTITION:-standard}"; QOS="${QOS:-short}"
TIME="${TIME:-00:40:00}"; NCPUS="${NCPUS:-8}"
LOGDIR="${REPO}/logs"; mkdir -p "${LOGDIR}"

echo "warming the shared depot on the login node (network-safe) ..."
JULIA_DEPOT_PATH="${JULIA_DEPOT_PATH:-$HOME/.julia}" "${JULIA}" --project="${REPO}" \
    -e 'import Pkg; Pkg.instantiate(); Pkg.precompile()' || \
    echo "  (warm-up non-fatal; the node will fall back to the pkg-server)"

jcf="$(mktemp)"
cat > "${jcf}" <<EOF
#!/usr/bin/env bash
#SBATCH --job-name=jltest_${RUNTAG}
#SBATCH --account=${ACCOUNT}
#SBATCH --partition=${PARTITION}
#SBATCH --qos=${QOS}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=${NCPUS}
#SBATCH --time=${TIME}
#SBATCH --output=${LOGDIR}/${RUNTAG}.%j.out
#SBATCH --error=${LOGDIR}/${RUNTAG}.%j.out
set -uo pipefail
cd "${REPO}"
export JULIA_DEPOT_PATH="\${JULIA_DEPOT_PATH:-\$HOME/.julia}"
echo "=== CI-faithful Pkg.test() on \$(hostname) at \$(date) ==="
rm -f test/Manifest.toml                       # CI-faithful: fresh re-resolve (CLAUDE.md §2)
${JULIA} --project=. -e 'import Pkg; Pkg.test()'
code=\$?
echo "=== JOB DONE tag=${RUNTAG} exit=\${code} ==="
exit \${code}
EOF

jid="$(sbatch "${jcf}" | awk '{print $NF}')"
rm -f "${jcf}"
echo "submitted CI-faithful suite job ${jid} (tag=${RUNTAG}, ${PARTITION}/${QOS}, ${NCPUS} cpus, ${TIME})"
echo "  log:   ${LOGDIR}/${RUNTAG}.${jid}.out"
echo "  watch: squeue -u ${USER} -j ${jid}   |   tail -f ${LOGDIR}/${RUNTAG}.${jid}.out"
echo "  done?: grep -E 'JOB DONE|Test Summary|[0-9]+ pass' ${LOGDIR}/${RUNTAG}.${jid}.out"
