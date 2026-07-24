#!/usr/bin/env bash
# =============================================================================
# run_global_slow_training.sh — end-to-end GLOBAL Component-S training as ONE
# SLURM job on a compute node (survives session teardown; the disconnect-proof
# path per CLAUDE.md §2). Does, in sequence, inside a single allocation:
#   1. build_slow_runtime_table.py  — the runtime-consistent GLOBAL training table
#      (streams the annual `ind` parquet; inner-joins the REAL soilmoist [daily
#      swc] + lai [LAI_STAND] features; bakes per-cell climatological boundary +
#      cell_meta.parquet). SCENARIO=historic|ssp370.
#   2. train_slow_drf.jl            — fit + serialize the pooled cell-agnostic
#      count DRF to a SEPARATE artifact (DRF_OUT_PATH; NEVER the committed
#      Hainich fixture).
#
# One job = atomic + no SLURM dependency chaining; if the connection drops the
# whole pipeline still finishes on the node and logs to shared /p.
#
# Usage:
#   SCENARIO=historic scripts/run_global_slow_training.sh            # submit
#   SCENARIO=historic SUBMIT=no scripts/run_global_slow_training.sh  # print jcf only
#   SCENARIO=ssp370 scripts/run_global_slow_training.sh              # future (after its daily run)
#
# Env: SCENARIO (historic|ssp370, required-ish; default historic), SEED (1),
#      NTREES (150), MAX_DEPTH (16), MIN_LEAF (20), SUBSAMPLE (200000),
#      TIME (04:00:00), NCPUS (32), SUBMIT (yes).
# Collect from any later session: tail -f logs/gslow_<scen>.<jobid>.out ;
#      last line "=== JOB DONE ... ===". Artifacts land in
#      /p/tmp/jamirp/emulator_global/{slow_runtime_<scen>/, drf_forest_global_<scen>.drf}.
# =============================================================================
set -euo pipefail

SCENARIO="${SCENARIO:-historic}"
case "${SCENARIO}" in historic|ssp370) ;; *) echo "FATAL: SCENARIO must be historic|ssp370"; exit 1;; esac
SEED="${SEED:-1}"
NTREES="${NTREES:-150}"; MAX_DEPTH="${MAX_DEPTH:-16}"; MIN_LEAF="${MIN_LEAF:-20}"; SUBSAMPLE="${SUBSAMPLE:-200000}"
TIME="${TIME:-04:00:00}"; NCPUS="${NCPUS:-32}"; SUBMIT="${SUBMIT:-yes}"
ACCOUNT="${ACCOUNT:-waldspektrum}"; PARTITION="${PARTITION:-standard}"; QOS="${QOS:-short}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/jamirp/.conda/envs/py311_new/bin/python"
JULIA="${JULIA:-/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia}"  # DRF is zero-dep pure-Base
LOGDIR="${REPO}/logs"; mkdir -p "${LOGDIR}"

TABLE_DIR="/p/tmp/jamirp/emulator_global/slow_runtime_${SCENARIO}"
DRF_OUT="/p/tmp/jamirp/emulator_global/drf_forest_global_${SCENARIO}.drf"
mkdir -p "${TABLE_DIR}"

jcf="$(mktemp)"
cat > "${jcf}" <<EOF
#!/usr/bin/env bash
#SBATCH --job-name=gslow_${SCENARIO}
#SBATCH --account=${ACCOUNT}
#SBATCH --partition=${PARTITION}
#SBATCH --qos=${QOS}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=${NCPUS}
#SBATCH --time=${TIME}
#SBATCH --output=${LOGDIR}/gslow_${SCENARIO}.%j.out
#SBATCH --error=${LOGDIR}/gslow_${SCENARIO}.%j.out
set -uo pipefail
cd "${REPO}"
export POLARS_MAX_THREADS=${NCPUS} OMP_NUM_THREADS=${NCPUS}
export JULIA_DEPOT_PATH="\${JULIA_DEPOT_PATH:-\$HOME/.julia}" JULIA_NUM_THREADS=${NCPUS}
echo "=== gslow_${SCENARIO} on \$(hostname) at \$(date) ==="

echo "--- [1/2] build global ${SCENARIO} table -> ${TABLE_DIR} ---"
SCENARIO=${SCENARIO} SEED=${SEED} OUT=${TABLE_DIR} ${PY} scripts/build_slow_runtime_table.py
rc=\$?; [ \$rc -ne 0 ] && { echo "=== JOB DONE tag=gslow_${SCENARIO} exit=\$rc (table build failed) ==="; exit \$rc; }

echo "--- [2/2] train + serialize global DRF -> ${DRF_OUT} ---"
OUT=${TABLE_DIR} DRF_OUT_PATH=${DRF_OUT} NTREES=${NTREES} MAX_DEPTH=${MAX_DEPTH} \
  MIN_LEAF=${MIN_LEAF} SUBSAMPLE=${SUBSAMPLE} ${JULIA} scripts/train_slow_drf.jl
rc=\$?
echo "=== JOB DONE tag=gslow_${SCENARIO} exit=\${rc} ==="
exit \${rc}
EOF

if [ "${SUBMIT}" = "yes" ]; then
  jid="$(sbatch "${jcf}" | awk '{print $NF}')"
  rm -f "${jcf}"
  echo "submitted global ${SCENARIO} slow-training job ${jid} (${NCPUS} cpus, ${TIME})"
  echo "  table: ${TABLE_DIR}    drf: ${DRF_OUT}"
  echo "  log:   ${LOGDIR}/gslow_${SCENARIO}.${jid}.out"
  echo "  done?: grep 'JOB DONE' ${LOGDIR}/gslow_${SCENARIO}.${jid}.out"
else
  echo "== SUBMIT=no — generated jcf:"; cat "${jcf}"; rm -f "${jcf}"
fi
