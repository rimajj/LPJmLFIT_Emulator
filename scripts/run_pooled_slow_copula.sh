#!/usr/bin/env bash
# =============================================================================
# run_pooled_slow_copula.sh — the POOLED MULTI-REGIME + TRANSIENT-boundary
# recruit-trait COPULA (ADR 0025 + 0026) as ONE SLURM job. In sequence:
#   1. build historic transient copula table  (MODE=copula BOUNDARY_WINDOW=W STEM_CAP)
#   2. build ssp370   transient copula table  (MODE=copula BOUNDARY_WINDOW=W STEM_CAP)
#   3. pool_slow_tables.py → ONE pooled copula table + per-row scenario.i64
#   4. eval_slow_copula.jl → K-fold-by-cell OOS trait-distribution (pred_<axis>.f64)
#   5. train_slow_copula.jl → ONE serialized global pooled .rcop
#
# The trait MARGINAL per cell is fully estimated by a few hundred stems, so
# STEM_CAP (default 400/cell) keeps the pooled table tractable — the un-capped
# pooled copula is ~730M stems (historic 133M + ssp ~600M) which busts the 4h
# qos; STEM_CAP=400 → ~18M stems, and the per-cell KS / pooled marginals are
# preserved. The transient boundary (ADR 0026) is REQUIRED (BOUNDARY_WINDOW): a
# frozen SSP gate would defeat the multi-regime goal. Each scenario is built
# independently (no cross-scenario stem mixing before the copula fit).
#
# Usage:
#   scripts/run_pooled_slow_copula.sh                 # submit (W=20, STEM_CAP=400)
#   SUBMIT=no scripts/run_pooled_slow_copula.sh       # print the jcf only
# Env: WINDOW (20), STEM_CAP (400), SEED (1), NTREES (60) MAX_DEPTH (14) MIN_LEAF (20)
#      SUBSAMPLE (50000), EVAL_NTREES (40) EVAL_SUBSAMPLE (50000), KFOLDS (5),
#      TIME (06:00:00), NCPUS (32), SUBMIT (yes).
# Collect: tail -f logs/gpcop_slow.<jobid>.out ; last line "=== JOB DONE ... ===".
# Artifacts: /p/tmp/jamirp/emulator_global/{slow_copula_<scen>_w<W>/, slow_copula_pooled_w<W>/,
#            recruit_copula_global_pooled_w<W>.rcop}  (DVC, not git).
# =============================================================================
set -euo pipefail

WINDOW="${WINDOW:-20}"; STEM_CAP="${STEM_CAP:-400}"; SEED="${SEED:-1}"; KFOLDS="${KFOLDS:-5}"
NTREES="${NTREES:-60}"; MAX_DEPTH="${MAX_DEPTH:-14}"; MIN_LEAF="${MIN_LEAF:-20}"; SUBSAMPLE="${SUBSAMPLE:-50000}"
EVAL_NTREES="${EVAL_NTREES:-40}"; EVAL_SUBSAMPLE="${EVAL_SUBSAMPLE:-50000}"
TIME="${TIME:-06:00:00}"; NCPUS="${NCPUS:-32}"; SUBMIT="${SUBMIT:-yes}"
ACCOUNT="${ACCOUNT:-waldspektrum}"; PARTITION="${PARTITION:-standard}"; QOS="${QOS:-short}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/jamirp/.conda/envs/py311_new/bin/python"
JULIA="${JULIA:-/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia}"
LOGDIR="${REPO}/logs"; mkdir -p "${LOGDIR}"
BASE="/p/tmp/jamirp/emulator_global"

HIST_DIR="${BASE}/slow_copula_historic_w${WINDOW}"
SSP_DIR="${BASE}/slow_copula_ssp370_w${WINDOW}"
POOL_DIR="${BASE}/slow_copula_pooled_w${WINDOW}"
RCOP_OUT="${BASE}/recruit_copula_global_pooled_w${WINDOW}.rcop"
mkdir -p "${HIST_DIR}" "${SSP_DIR}" "${POOL_DIR}"

jcf="$(mktemp)"
cat > "${jcf}" <<EOF
#!/usr/bin/env bash
#SBATCH --job-name=gpcop_slow
#SBATCH --account=${ACCOUNT}
#SBATCH --partition=${PARTITION}
#SBATCH --qos=${QOS}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=${NCPUS}
#SBATCH --time=${TIME}
#SBATCH --output=${LOGDIR}/gpcop_slow.%j.out
#SBATCH --error=${LOGDIR}/gpcop_slow.%j.out
set -uo pipefail
cd "${REPO}"
export POLARS_MAX_THREADS=${NCPUS} OMP_NUM_THREADS=${NCPUS}
export JULIA_DEPOT_PATH="\${JULIA_DEPOT_PATH:-\$HOME/.julia}" JULIA_NUM_THREADS=${NCPUS}
echo "=== gpcop_slow on \$(hostname) at \$(date)  W=${WINDOW} STEM_CAP=${STEM_CAP} ==="

echo "--- [1/5] build historic transient copula table -> ${HIST_DIR} ---"
MODE=copula SCENARIO=historic SEED=${SEED} BOUNDARY_WINDOW=${WINDOW} STEM_CAP=${STEM_CAP} OUT=${HIST_DIR} ${PY} scripts/build_slow_runtime_table.py
rc=\$?; [ \$rc -ne 0 ] && { echo "=== JOB DONE tag=gpcop_slow exit=\$rc (historic build failed) ==="; exit \$rc; }

echo "--- [2/5] build ssp370 transient copula table -> ${SSP_DIR} ---"
MODE=copula SCENARIO=ssp370 SEED=${SEED} BOUNDARY_WINDOW=${WINDOW} STEM_CAP=${STEM_CAP} OUT=${SSP_DIR} ${PY} scripts/build_slow_runtime_table.py
rc=\$?; [ \$rc -ne 0 ] && { echo "=== JOB DONE tag=gpcop_slow exit=\$rc (ssp370 build failed) ==="; exit \$rc; }

echo "--- [3/5] pool -> ${POOL_DIR} ---"
IN_DIRS=${HIST_DIR},${SSP_DIR} TAGS=historic,ssp370 OUT=${POOL_DIR} ${PY} scripts/pool_slow_tables.py
rc=\$?; [ \$rc -ne 0 ] && { echo "=== JOB DONE tag=gpcop_slow exit=\$rc (pool failed) ==="; exit \$rc; }

echo "--- [4/5] K-fold-by-cell OOS trait-distribution eval -> pred_<axis>.f64 ---"
OUT=${POOL_DIR} KFOLDS=${KFOLDS} NTREES=${EVAL_NTREES} MAX_DEPTH=${MAX_DEPTH} MIN_LEAF=${MIN_LEAF} \
  SUBSAMPLE=${EVAL_SUBSAMPLE} ${JULIA} scripts/eval_slow_copula.jl
rc=\$?; [ \$rc -ne 0 ] && { echo "=== JOB DONE tag=gpcop_slow exit=\$rc (eval failed) ==="; exit \$rc; }

echo "--- [5/5] train + serialize ONE pooled+transient copula -> ${RCOP_OUT} ---"
OUT=${POOL_DIR} RCOP_OUT_PATH=${RCOP_OUT} NTREES=${NTREES} MAX_DEPTH=${MAX_DEPTH} \
  MIN_LEAF=${MIN_LEAF} SUBSAMPLE=${SUBSAMPLE} ${JULIA} scripts/train_slow_copula.jl
rc=\$?
echo "=== JOB DONE tag=gpcop_slow exit=\${rc} ==="
exit \${rc}
EOF

if [ "${SUBMIT}" = "yes" ]; then
  jid="$(sbatch "${jcf}" | awk '{print $NF}')"
  rm -f "${jcf}"
  echo "submitted POOLED+TRANSIENT copula job ${jid} (W=${WINDOW}, STEM_CAP=${STEM_CAP}, ${NCPUS} cpus, ${TIME})"
  echo "  tables: ${HIST_DIR} + ${SSP_DIR} -> ${POOL_DIR}    rcop: ${RCOP_OUT}"
  echo "  log:    ${LOGDIR}/gpcop_slow.${jid}.out"
  echo "  done?:  grep -E 'JOB DONE|pooled OOS|STEM_CAP' ${LOGDIR}/gpcop_slow.${jid}.out"
else
  echo "== SUBMIT=no — generated jcf:"; cat "${jcf}"; rm -f "${jcf}"
fi
