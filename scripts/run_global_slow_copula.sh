#!/usr/bin/env bash
# =============================================================================
# run_global_slow_copula.sh — end-to-end GLOBAL recruit-trait COPULA build +
# validate + train as ONE SLURM job (ADR 0025, Phase 4; disconnect-proof, the
# CLAUDE.md §2 path). In sequence, inside a single allocation:
#   1. build_slow_runtime_table.py MODE=copula — the per-STEM trait table whose
#      conditioning is the runtime live_flux_cond subset (4 flux drivers + per-cell
#      boundary), broadcast onto every SURVIVING stem's {SLA,Wooddens,D95max,minwscal}.
#   2. eval_slow_copula.jl — K-fold-BY-CELL OOS per-axis marginal predictions
#      (each cell predicted by forests that never saw it) -> pred_<axis>.f64.
#   3. train_slow_copula.jl — fit + serialize the pooled global copula to a
#      SEPARATE artifact (RCOP_OUT_PATH; NEVER the committed Hainich demo .rcop).
# Figures come after (locally): scripts/plot_slow_emulator_validation.py.
#
# Usage:
#   SCENARIO=historic scripts/run_global_slow_copula.sh              # submit
#   SCENARIO=historic SUBMIT=no scripts/run_global_slow_copula.sh    # print jcf only
#   SCENARIO=ssp370 scripts/run_global_slow_copula.sh                # after its features exist
# Env: SCENARIO (historic|ssp370; default historic), SEED (1), KFOLDS (5),
#      NTREES (60), MAX_DEPTH (14), MIN_LEAF (20), SUBSAMPLE (50000),
#      EVAL_NTREES (40), EVAL_SUBSAMPLE (50000), TIME (04:00:00), NCPUS (32), SUBMIT (yes).
# Artifacts: /p/tmp/jamirp/emulator_global/{slow_copula_<scen>/, recruit_copula_global_<scen>.rcop}.
# =============================================================================
set -euo pipefail

SCENARIO="${SCENARIO:-historic}"
case "${SCENARIO}" in historic|ssp370) ;; *) echo "FATAL: SCENARIO must be historic|ssp370"; exit 1;; esac
SEED="${SEED:-1}"; KFOLDS="${KFOLDS:-5}"
NTREES="${NTREES:-60}"; MAX_DEPTH="${MAX_DEPTH:-14}"; MIN_LEAF="${MIN_LEAF:-20}"; SUBSAMPLE="${SUBSAMPLE:-50000}"
EVAL_NTREES="${EVAL_NTREES:-40}"; EVAL_SUBSAMPLE="${EVAL_SUBSAMPLE:-50000}"
TIME="${TIME:-04:00:00}"; NCPUS="${NCPUS:-32}"; SUBMIT="${SUBMIT:-yes}"
ACCOUNT="${ACCOUNT:-waldspektrum}"; PARTITION="${PARTITION:-standard}"; QOS="${QOS:-short}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/jamirp/.conda/envs/py311_new/bin/python"
JULIA="${JULIA:-/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia}"   # DRF is zero-dep pure-Base
LOGDIR="${REPO}/logs"; mkdir -p "${LOGDIR}"

TABLE_DIR="/p/tmp/jamirp/emulator_global/slow_copula_${SCENARIO}"
RCOP_OUT="/p/tmp/jamirp/emulator_global/recruit_copula_global_${SCENARIO}.rcop"
mkdir -p "${TABLE_DIR}"

DEPENDENCY="${DEPENDENCY:-}"
dep_directive=""
[ -n "${DEPENDENCY}" ] && dep_directive="#SBATCH --dependency=${DEPENDENCY}"

jcf="$(mktemp)"
cat > "${jcf}" <<EOF
#!/usr/bin/env bash
#SBATCH --job-name=gcopula_${SCENARIO}
#SBATCH --account=${ACCOUNT}
#SBATCH --partition=${PARTITION}
#SBATCH --qos=${QOS}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=${NCPUS}
#SBATCH --time=${TIME}
#SBATCH --output=${LOGDIR}/gcopula_${SCENARIO}.%j.out
#SBATCH --error=${LOGDIR}/gcopula_${SCENARIO}.%j.out
${dep_directive}
set -uo pipefail
cd "${REPO}"
export POLARS_MAX_THREADS=${NCPUS} OMP_NUM_THREADS=${NCPUS}
export JULIA_DEPOT_PATH="\${JULIA_DEPOT_PATH:-\$HOME/.julia}" JULIA_NUM_THREADS=${NCPUS}
echo "=== gcopula_${SCENARIO} on \$(hostname) at \$(date) ==="

echo "--- [1/3] build global ${SCENARIO} copula table -> ${TABLE_DIR} ---"
MODE=copula SCENARIO=${SCENARIO} SEED=${SEED} OUT=${TABLE_DIR} ${PY} scripts/build_slow_runtime_table.py
rc=\$?; [ \$rc -ne 0 ] && { echo "=== JOB DONE tag=gcopula_${SCENARIO} exit=\$rc (table build failed) ==="; exit \$rc; }

echo "--- [2/3] K-fold-by-cell OOS trait-distribution eval -> pred_<axis>.f64 ---"
OUT=${TABLE_DIR} KFOLDS=${KFOLDS} NTREES=${EVAL_NTREES} MAX_DEPTH=${MAX_DEPTH} MIN_LEAF=${MIN_LEAF} \
  SUBSAMPLE=${EVAL_SUBSAMPLE} ${JULIA} scripts/eval_slow_copula.jl
rc=\$?; [ \$rc -ne 0 ] && { echo "=== JOB DONE tag=gcopula_${SCENARIO} exit=\$rc (eval failed) ==="; exit \$rc; }

echo "--- [3/3] train + serialize global copula -> ${RCOP_OUT} ---"
OUT=${TABLE_DIR} RCOP_OUT_PATH=${RCOP_OUT} NTREES=${NTREES} MAX_DEPTH=${MAX_DEPTH} \
  MIN_LEAF=${MIN_LEAF} SUBSAMPLE=${SUBSAMPLE} ${JULIA} scripts/train_slow_copula.jl
rc=\$?
echo "=== JOB DONE tag=gcopula_${SCENARIO} exit=\${rc} ==="
exit \${rc}
EOF

if [ "${SUBMIT}" = "yes" ]; then
  jid="$(sbatch "${jcf}" | awk '{print $NF}')"
  rm -f "${jcf}"
  echo "submitted global ${SCENARIO} copula job ${jid} (${NCPUS} cpus, ${TIME})"
  echo "  table: ${TABLE_DIR}    rcop: ${RCOP_OUT}"
  echo "  log:   ${LOGDIR}/gcopula_${SCENARIO}.${jid}.out"
  echo "  done?: grep 'JOB DONE' ${LOGDIR}/gcopula_${SCENARIO}.${jid}.out"
else
  echo "== SUBMIT=no — generated jcf:"; cat "${jcf}"; rm -f "${jcf}"
fi
