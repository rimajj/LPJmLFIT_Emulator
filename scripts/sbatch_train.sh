#!/usr/bin/env bash
# =============================================================================
# sbatch_train.sh — submit an F_diff NN-training driver as a SLURM BATCH JOB on a
# compute node (NOT the login node), so long Enzyme-reverse training runs are
# DURABLE (survive a dropped interactive session) and off the shared login node.
#
# The training drivers (scripts/train_fdiff_*.jl) are single-process but heavy:
# the Enzyme-reverse compile of the multi-year canopy rollout is ~7 min and a full
# cell × multi-year fit is ~30-40 min. Run them here, not inline.
#
# Usage:
#   scripts/sbatch_train.sh <driver.jl> [RUNTAG] [TIME] [NCPUS]
# e.g.
#   scripts/sbatch_train.sh scripts/train_fdiff_cell_multiyear.jl cellmy 02:00:00 8
#
# Then watch it:
#   squeue -u "$USER"                 # queue/run state
#   tail -f logs/train_<tag>.<jobid>.out
#   sacct -j <jobid> --format=JobID,State,Elapsed,MaxRSS
#
# Defaults: partition=standard, qos=short (≤1 day), 1 node, 8 CPUs, 2 h walltime.
# JULIA_DEPOT_PATH=$HOME/.julia (the warmed depot); runs against --project=test
# (Lux/Zygote/Optimisers/Enzyme + the package dev'd in — the same env the driver
# docstrings specify). Enzyme reverse ⇒ Julia 1.10 (lts).
# =============================================================================
set -euo pipefail

DRIVER="${1:?usage: sbatch_train.sh <driver.jl> [RUNTAG] [TIME] [NCPUS]}"
RUNTAG="${2:-$(basename "${DRIVER}" .jl)}"
TIME="${3:-02:00:00}"
NCPUS="${4:-8}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JULIA="${JULIA:-/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia}"
ACCOUNT="${ACCOUNT:-waldspektrum}"
PARTITION="${PARTITION:-standard}"
QOS="${QOS:-short}"
LOGDIR="${REPO}/logs"
mkdir -p "${LOGDIR}"

[ -f "${REPO}/${DRIVER}" ] || [ -f "${DRIVER}" ] || { echo "driver not found: ${DRIVER}" >&2; exit 1; }

jcf="$(mktemp)"
cat > "${jcf}" <<EOF
#!/usr/bin/env bash
#SBATCH --job-name=fdiff_train_${RUNTAG}
#SBATCH --account=${ACCOUNT}
#SBATCH --partition=${PARTITION}
#SBATCH --qos=${QOS}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=${NCPUS}
#SBATCH --time=${TIME}
#SBATCH --output=${LOGDIR}/train_${RUNTAG}.%j.out
#SBATCH --error=${LOGDIR}/train_${RUNTAG}.%j.out
set -euo pipefail
cd "${REPO}"
export JULIA_DEPOT_PATH="\${JULIA_DEPOT_PATH:-\$HOME/.julia}"
export JULIA_NUM_THREADS=${NCPUS}
# ensure the test env is instantiated with the package dev'd in (idempotent);
# then delete test/Manifest.toml afterwards is NOT needed here (this is not Pkg.test()).
${JULIA} --project=test -e 'import Pkg; Pkg.develop(path="."); Pkg.instantiate()'
echo "=== running ${DRIVER} on \$(hostname) at \$(date) ==="
exec ${JULIA} --project=test "${DRIVER}"
EOF

jid="$(sbatch "${jcf}" | awk '{print $NF}')"
rm -f "${jcf}"
echo "submitted job ${jid}: ${DRIVER} (tag=${RUNTAG}, ${PARTITION}/${QOS}, ${NCPUS} cpus, ${TIME})"
echo "  watch: squeue -u ${USER} -j ${jid}   |   tail -f ${LOGDIR}/train_${RUNTAG}.${jid}.out"
