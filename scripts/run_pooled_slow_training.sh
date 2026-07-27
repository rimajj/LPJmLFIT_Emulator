#!/usr/bin/env bash
# =============================================================================
# run_pooled_slow_training.sh — the POOLED MULTI-REGIME + TRANSIENT-boundary
# Component-S COUNT DRF (ADR 0026) as ONE SLURM job on a compute node
# (disconnect-proof, CLAUDE.md §2). In sequence, inside one allocation:
#   1. build historic transient count table  (BOUNDARY_WINDOW=W)
#   2. build ssp370   transient count table  (BOUNDARY_WINDOW=W)
#   3. pool_slow_tables.py → ONE pooled table + per-row scenario.i64 tag
#   4. train_slow_drf.jl on the pooled table → ONE cell-agnostic count DRF
#      (HOLDOUT_FRAC ⇒ also a held-out-BY-CELL generalization R²)
#   5. eval_slow_scenario_holdout.jl → the HOLD-OUT-BY-SCENARIO unseen-regime proof
#
# The transient boundary (ADR 0026) is REQUIRED for pooling: without it the SSP
# rows would carry the historic climatological gate (frozen), defeating the
# multi-regime goal. Each scenario's table is built independently so its AR
# `n_prev` join never crosses the historic↔ssp discontinuity.
#
# Usage:
#   scripts/run_pooled_slow_training.sh                 # submit (W=20, both scenarios)
#   SUBMIT=no scripts/run_pooled_slow_training.sh       # print the jcf only
# Env: WINDOW (20), SEED (1), NTREES (150) MAX_DEPTH (16) MIN_LEAF (20) SUBSAMPLE (200000),
#      HOLDOUT_FRAC (0.1), TIME (08:00:00), NCPUS (32), SUBMIT (yes).
# Collect: tail -f logs/gpool_slow.<jobid>.out ; last line "=== JOB DONE ... ===".
# Artifacts: /p/tmp/jamirp/emulator_global/{slow_count_<scen>_w<W>/, slow_count_pooled_w<W>/,
#            drf_forest_global_pooled_w<W>.drf}  (DVC, not git).
# =============================================================================
set -euo pipefail

WINDOW="${WINDOW:-20}"; SEED="${SEED:-1}"
NTREES="${NTREES:-150}"; MAX_DEPTH="${MAX_DEPTH:-16}"; MIN_LEAF="${MIN_LEAF:-20}"; SUBSAMPLE="${SUBSAMPLE:-200000}"
HOLDOUT_FRAC="${HOLDOUT_FRAC:-0.1}"
TIME="${TIME:-08:00:00}"; NCPUS="${NCPUS:-32}"; SUBMIT="${SUBMIT:-yes}"
ACCOUNT="${ACCOUNT:-waldspektrum}"; PARTITION="${PARTITION:-standard}"; QOS="${QOS:-short}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/jamirp/.conda/envs/py311_new/bin/python"
JULIA="${JULIA:-/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia}"
LOGDIR="${REPO}/logs"; mkdir -p "${LOGDIR}"
BASE="/p/tmp/jamirp/emulator_global"

HIST_DIR="${BASE}/slow_count_historic_w${WINDOW}"
SSP_DIR="${BASE}/slow_count_ssp370_w${WINDOW}"
POOL_DIR="${BASE}/slow_count_pooled_w${WINDOW}"
DRF_OUT="${BASE}/drf_forest_global_pooled_w${WINDOW}.drf"
mkdir -p "${HIST_DIR}" "${SSP_DIR}" "${POOL_DIR}"

jcf="$(mktemp)"
cat > "${jcf}" <<EOF
#!/usr/bin/env bash
#SBATCH --job-name=gpool_slow
#SBATCH --account=${ACCOUNT}
#SBATCH --partition=${PARTITION}
#SBATCH --qos=${QOS}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=${NCPUS}
#SBATCH --time=${TIME}
#SBATCH --output=${LOGDIR}/gpool_slow.%j.out
#SBATCH --error=${LOGDIR}/gpool_slow.%j.out
set -uo pipefail
cd "${REPO}"
export POLARS_MAX_THREADS=${NCPUS} OMP_NUM_THREADS=${NCPUS}
export JULIA_DEPOT_PATH="\${JULIA_DEPOT_PATH:-\$HOME/.julia}" JULIA_NUM_THREADS=${NCPUS}
echo "=== gpool_slow on \$(hostname) at \$(date)  W=${WINDOW} ==="

echo "--- [1/5] build historic transient count table -> ${HIST_DIR} ---"
SCENARIO=historic SEED=${SEED} BOUNDARY_WINDOW=${WINDOW} OUT=${HIST_DIR} ${PY} scripts/build_slow_runtime_table.py
rc=\$?; [ \$rc -ne 0 ] && { echo "=== JOB DONE tag=gpool_slow exit=\$rc (historic build failed) ==="; exit \$rc; }

echo "--- [2/5] build ssp370 transient count table -> ${SSP_DIR} ---"
SCENARIO=ssp370 SEED=${SEED} BOUNDARY_WINDOW=${WINDOW} OUT=${SSP_DIR} ${PY} scripts/build_slow_runtime_table.py
rc=\$?; [ \$rc -ne 0 ] && { echo "=== JOB DONE tag=gpool_slow exit=\$rc (ssp370 build failed) ==="; exit \$rc; }

echo "--- [3/5] pool -> ${POOL_DIR} ---"
IN_DIRS=${HIST_DIR},${SSP_DIR} TAGS=historic,ssp370 OUT=${POOL_DIR} ${PY} scripts/pool_slow_tables.py
rc=\$?; [ \$rc -ne 0 ] && { echo "=== JOB DONE tag=gpool_slow exit=\$rc (pool failed) ==="; exit \$rc; }

echo "--- [4/5] train ONE pooled+transient count DRF -> ${DRF_OUT} ---"
OUT=${POOL_DIR} DRF_OUT_PATH=${DRF_OUT} NTREES=${NTREES} MAX_DEPTH=${MAX_DEPTH} \
  MIN_LEAF=${MIN_LEAF} SUBSAMPLE=${SUBSAMPLE} HOLDOUT_FRAC=${HOLDOUT_FRAC} ${JULIA} scripts/train_slow_drf.jl
rc=\$?; [ \$rc -ne 0 ] && { echo "=== JOB DONE tag=gpool_slow exit=\$rc (train failed) ==="; exit \$rc; }

echo "--- [5/5] HOLD-OUT-BY-SCENARIO unseen-regime eval ---"
OUT=${POOL_DIR} NTREES=${NTREES} MAX_DEPTH=${MAX_DEPTH} MIN_LEAF=${MIN_LEAF} SUBSAMPLE=${SUBSAMPLE} \
  ${JULIA} scripts/eval_slow_scenario_holdout.jl
rc=\$?
echo "=== JOB DONE tag=gpool_slow exit=\${rc} ==="
exit \${rc}
EOF

if [ "${SUBMIT}" = "yes" ]; then
  jid="$(sbatch "${jcf}" | awk '{print $NF}')"
  rm -f "${jcf}"
  echo "submitted POOLED+TRANSIENT slow-training job ${jid} (W=${WINDOW}, ${NCPUS} cpus, ${TIME})"
  echo "  tables: ${HIST_DIR} + ${SSP_DIR} -> ${POOL_DIR}    drf: ${DRF_OUT}"
  echo "  log:    ${LOGDIR}/gpool_slow.${jid}.out"
  echo "  done?:  grep -E 'JOB DONE|HOLD-OUT-BY-SCENARIO|R²' ${LOGDIR}/gpool_slow.${jid}.out"
else
  echo "== SUBMIT=no — generated jcf:"; cat "${jcf}"; rm -f "${jcf}"
fi
