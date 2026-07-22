#!/usr/bin/env bash
# =============================================================================
# sbatch_python.sh — submit a Python job to SLURM on a COMPUTE NODE so it
# SURVIVES session teardown (dropped SSH, agent restart, UI stop). The Python
# twin of scripts/sbatch_julia.sh. Uses the REUSED conda env py311_new
# (config/hpc_slurm.yaml: polars/pandas/pyarrow/numpy/netCDF4 all present).
#
# Usage:
#   scripts/sbatch_python.sh <TAG> <script.py> [args...]
#   NCELLS=4000 SEED=1 NO_DAILY=1 OUT=/p/tmp/jamirp/slow_count \
#     scripts/sbatch_python.sh count scripts/build_slow_count_table.py
#
# Env overrides: TIME (default 01:00:00), NCPUS (16), ACCOUNT (waldspektrum),
# PARTITION (standard), QOS (short). Any VAR=... you export is forwarded.
#
# Watch / collect (from ANY later session):
#   squeue -u "$USER"          tail -f logs/<TAG>.<jobid>.out
# Last line: "=== JOB DONE tag=<TAG> exit=<code> ===" (grep it).
# =============================================================================
set -euo pipefail

TAG="${1:?usage: sbatch_python.sh <TAG> <script.py> [args...]}"; shift
SCRIPT="${1:?usage: sbatch_python.sh <TAG> <script.py> [args...]}"; shift || true

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/jamirp/.conda/envs/py311_new/bin/python"
ACCOUNT="${ACCOUNT:-waldspektrum}"; PARTITION="${PARTITION:-standard}"; QOS="${QOS:-short}"
TIME="${TIME:-01:00:00}"; NCPUS="${NCPUS:-16}"
LOGDIR="${REPO}/logs"; mkdir -p "${LOGDIR}"

# forward the table-build env knobs explicitly (so they reach the batch shell)
FWD=""
for v in NCELLS SEED NO_DAILY OUT CELLS; do
    if [ -n "${!v:-}" ]; then FWD="${FWD} ${v}=${!v}"; fi
done

jcf="$(mktemp)"
cat > "${jcf}" <<EOF
#!/usr/bin/env bash
#SBATCH --job-name=py_${TAG}
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
export POLARS_MAX_THREADS=${NCPUS}
export OMP_NUM_THREADS=${NCPUS}
echo "=== py_${TAG} on \$(hostname) at \$(date) ==="
${FWD} ${PY} ${SCRIPT} $*
code=\$?
echo "=== JOB DONE tag=${TAG} exit=\${code} ==="
exit \${code}
EOF

jid="$(sbatch "${jcf}" | awk '{print $NF}')"
rm -f "${jcf}"
echo "submitted job ${jid}: python ${SCRIPT} $* (tag=${TAG}, ${PARTITION}/${QOS}, ${NCPUS} cpus, ${TIME})"
echo "  env:   ${FWD}"
echo "  log:   ${LOGDIR}/${TAG}.${jid}.out"
echo "  watch: tail -f ${LOGDIR}/${TAG}.${jid}.out   |   done?: grep -q 'JOB DONE' the log"
