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
# shared depot on the login node for BOTH the main project AND the test env (the
# latter matters because Pkg.test() re-resolves a SANDBOX of test/Project.toml on
# the node — see the warm step below), so the fresh re-resolve finds every dep
# cached and needs no network. The only residual risk is a dep version so new the
# pkg-server hasn't mirrored it yet
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
export JULIA_DEPOT_PATH="${JULIA_DEPOT_PATH:-$HOME/.julia}"
# (1) the MAIN project env.
"${JULIA}" --project="${REPO}" \
    -e 'import Pkg; Pkg.instantiate(); Pkg.precompile()' || \
    echo "  (main-env warm-up non-fatal; the node will fall back to the pkg-server)"
# (2) the TEST env — LOAD-BEARING, and the subtle part. `Pkg.test()` does NOT use `test/Project.toml`
# in place: it builds a SANDBOX env from it and RE-RESOLVES that sandbox to newest-allowed versions.
# That resolve happens on the COMPUTE NODE, which has no GitHub egress and (for a version the pkg-server
# hasn't mirrored) no way to fetch at all — so every test-only dep (Lux/Zygote/Enzyme/JET/Aqua → NNlib …)
# must ALREADY be in the shared depot at the version the fresh resolve will pick. Warming only the main
# project (as this script did originally) left that to luck: it worked in a long-lived checkout whose depot
# had accumulated the versions, and FAILED on a fresh git worktree ("failed to clone from
# https://github.com/FluxML/NNlib.jl.git … Network is unreachable" inside Pkg's `sandbox(...)`) — which is
# exactly what a new work line (ADR 0028) starts with. Resolving the test env here pulls those versions into
# the depot first.
REPO_ROOT="${REPO}" "${JULIA}" --project="${REPO}/test" \
    -e 'import Pkg; Pkg.develop(path = ENV["REPO_ROOT"]); Pkg.instantiate(); Pkg.precompile()' || \
    echo "  (test-env warm-up non-fatal; a fresh sandbox resolve on the node may then need the pkg-server)"
# The warm above CREATES test/Manifest.toml with a machine-specific dev path; `Pkg.test()` then dies with
# "can not merge projects" (CLAUDE.md §2) and it must never be committed (it is gitignored). Remove it so the
# node re-resolves cleanly — the point of the warm is the populated DEPOT, not the manifest.
rm -f "${REPO}/test/Manifest.toml"

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
