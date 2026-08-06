#!/usr/bin/env bash
# =============================================================================
# run_moisture_conditioning_arm.sh — the ADR-0108 MOISTURE-CONDITIONING arm: does
# making the six moisture descriptors TRANSIENT (per cell-year, trailing 20-yr
# window) instead of frozen at each cell's present-day climatology change the
# recruit-trait emulator — and does it open a climate-change response channel?
#
# WHY IT IS ITS OWN ORCHESTRATOR AND NOT A FLAG ON run_pooled_slow_copula.sh.
# The question needs TWO 14-column tables that differ in the tail's time basis and
# in NOTHING else. Building them independently would not do: the copula build's
# `collect(engine="streaming")` is non-deterministic in its emitted KEY SET at this
# scale (ADR 0036 §5b — two ssp370 builds differed by 4 913 rows with 12 cells
# DUPLICATED), so two builds land on two row universes and any measured difference
# is confounded with that. So: build the 8-column base ONCE, then APPEND each tail
# to the same frozen base (build_slow_copula_env_augment.py, which verifies the
# base columns survive bitwise and symlinks Y_*/cells/years so they cannot drift).
# Perfect isolation — the ADR-0033 attribution error this line has made twice.
#
# In sequence (one SLURM job; the t8 equivalent took 27 min on 96 cpus):
#   1. build historic 8-col base table   (BOUNDARY_WINDOW=W, + years.i64)
#   2. build ssp370   8-col base table   (BOUNDARY_WINDOW=W, + years.i64)
#   3. pool -> ONE base table + scenario.i64 + years.i64
#   4. augment STATIC   tail -> _env   (per-cell means; the ADR-0037 shipped basis)
#   5. augment TRANSIENT tail -> _envT (per-(Cell,Year); ADR 0108)
#   6. K-fold-by-cell OOS eval of the TRANSIENT table  (the arm)
#   7. K-fold-by-cell OOS eval of the STATIC table     (the control)
#   8. train + serialize the TRANSIENT .rcop
# Steps 6 and 7 use IDENTICAL folds (the fold map is a hash of Cell, and the two
# tables have the same cells.i64 bytes), so the two OOS scores are paired per cell.
#
# ⚠ THE ARTIFACT FROM STEP 8 NEEDS A DIFFERENT RUNTIME POLICY. A transient-tail
# .rcop has the SAME ncond and the SAME cond_cols as a static-tail one, so the
# runtime width probe passes for either pairing; it must be consumed via
# `live_flux_cond_env_series(series)`, never `live_flux_cond_env(env)`. The
# manifest's `env_basis` line is the only discriminator. Adopting it is an ADR-0023
# BOTH-SIDES change with line M (§9): version the artifact, never mutate in place.
#
# Usage:
#   scripts/run_moisture_conditioning_arm.sh                  # submit (W=20, VERSION=t9)
#   SUBMIT=no scripts/run_moisture_conditioning_arm.sh        # print the jcf only
#   SKIP_BASE=yes ... # reuse an existing base table set (steps 1-3) and go straight to 4
# Env: WINDOW (20), VERSION (t9), STEM_CAP (400), STRUCT_AXES (agb,Height), SEED (1),
#      ENV_COLS (the 6 moisture descriptors), KFOLDS (5), NTREES (60) MAX_DEPTH (14)
#      MIN_LEAF (20) SUBSAMPLE (50000), EVAL_NTREES (40) EVAL_SUBSAMPLE (50000),
#      TIME (08:00:00), NCPUS (96), SUBMIT (yes), DEPENDENCY (afterok:<jid>), SKIP_BASE (no).
# Collect: tail -f logs/S-moisture_<VERSION>.<jobid>.out ; last line "=== JOB DONE ... ===".
# =============================================================================
set -euo pipefail

WINDOW="${WINDOW:-20}"; VERSION="${VERSION:-t9}"; STEM_CAP="${STEM_CAP:-400}"; SEED="${SEED:-1}"
STRUCT_AXES="${STRUCT_AXES-agb,Height}"
ENV_COLS="${ENV_COLS:-prec_mean,eco_diag_p_pet_ratio,eco_diag_pet_mean,eco_diag_vpd_mean,pr_cv_monthly,humid_mean}"
KFOLDS="${KFOLDS:-5}"
NTREES="${NTREES:-60}"; MAX_DEPTH="${MAX_DEPTH:-14}"; MIN_LEAF="${MIN_LEAF:-20}"; SUBSAMPLE="${SUBSAMPLE:-50000}"
EVAL_NTREES="${EVAL_NTREES:-40}"; EVAL_SUBSAMPLE="${EVAL_SUBSAMPLE:-50000}"
TIME="${TIME:-08:00:00}"; NCPUS="${NCPUS:-96}"; SUBMIT="${SUBMIT:-yes}"; SKIP_BASE="${SKIP_BASE:-no}"
ACCOUNT="${ACCOUNT:-waldspektrum}"; PARTITION="${PARTITION:-standard}"; QOS="${QOS:-short}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/jamirp/.conda/envs/py311_new/bin/python"
JULIA="${JULIA:-/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia}"
LOGDIR="${REPO}/logs"; mkdir -p "${LOGDIR}"
BASE="/p/tmp/jamirp/emulator_global"

HIST_DIR="${BASE}/slow_copula_historic_w${WINDOW}_${VERSION}"
SSP_DIR="${BASE}/slow_copula_ssp370_w${WINDOW}_${VERSION}"
POOL_DIR="${BASE}/slow_copula_pooled_w${WINDOW}_${VERSION}"
STAT_DIR="${POOL_DIR}env"      # ..._t9env   : STATIC per-cell tail  (the control)
TRAN_DIR="${POOL_DIR}envT"     # ..._t9envT  : TRANSIENT per-cell-year tail (the arm)
RCOP_OUT="${BASE}/recruit_copula_global_pooled_w${WINDOW}_${VERSION}envT.rcop"
TAG="S-moisture_${VERSION}"

DEPENDENCY="${DEPENDENCY:-}"
dep_directive=""
[ -n "${DEPENDENCY}" ] && dep_directive="#SBATCH --dependency=${DEPENDENCY}"

jcf="$(mktemp)"
cat > "${jcf}" <<EOF
#!/usr/bin/env bash
#SBATCH --job-name=${TAG}
#SBATCH --account=${ACCOUNT}
#SBATCH --partition=${PARTITION}
#SBATCH --qos=${QOS}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=${NCPUS}
#SBATCH --time=${TIME}
#SBATCH --output=${LOGDIR}/${TAG}.%j.out
#SBATCH --error=${LOGDIR}/${TAG}.%j.out
${dep_directive}
set -uo pipefail
cd "${REPO}"
export POLARS_MAX_THREADS=${NCPUS} OMP_NUM_THREADS=${NCPUS}
export JULIA_DEPOT_PATH="\${JULIA_DEPOT_PATH:-\$HOME/.julia}" JULIA_NUM_THREADS=${NCPUS}
echo "=== ${TAG} on \$(hostname) at \$(date)  W=${WINDOW} STEM_CAP=${STEM_CAP} SKIP_BASE=${SKIP_BASE} ==="
echo "=== env cols: ${ENV_COLS}"
die() { echo "=== JOB DONE tag=${TAG} exit=\$1 (\$2) ==="; exit \$1; }

if [ "${SKIP_BASE}" != "yes" ]; then
  echo "--- [1/8] build historic 8-col base table -> ${HIST_DIR} ---"
  mkdir -p "${HIST_DIR}"
  MODE=copula SCENARIO=historic SEED=${SEED} BOUNDARY_WINDOW=${WINDOW} STEM_CAP=${STEM_CAP} \
    STRUCT_AXES="${STRUCT_AXES}" OUT=${HIST_DIR} ${PY} scripts/build_slow_runtime_table.py
  rc=\$?; [ \$rc -ne 0 ] && die \$rc "historic base build failed"

  echo "--- [2/8] build ssp370 8-col base table -> ${SSP_DIR} ---"
  mkdir -p "${SSP_DIR}"
  MODE=copula SCENARIO=ssp370 SEED=${SEED} BOUNDARY_WINDOW=${WINDOW} STEM_CAP=${STEM_CAP} \
    STRUCT_AXES="${STRUCT_AXES}" OUT=${SSP_DIR} ${PY} scripts/build_slow_runtime_table.py
  rc=\$?; [ \$rc -ne 0 ] && die \$rc "ssp370 base build failed"

  echo "--- [3/8] pool the base tables -> ${POOL_DIR} ---"
  mkdir -p "${POOL_DIR}"
  IN_DIRS=${HIST_DIR},${SSP_DIR} TAGS=historic,ssp370 OUT=${POOL_DIR} ${PY} scripts/pool_slow_tables.py
  rc=\$?; [ \$rc -ne 0 ] && die \$rc "pool failed"
else
  echo "--- [1-3/8] SKIPPED (SKIP_BASE=yes) — reusing ${POOL_DIR} ---"
  [ -f "${POOL_DIR}/years.i64" ] || die 1 "SKIP_BASE=yes but ${POOL_DIR}/years.i64 is absent (pre-ADR-0108 table)"
fi

echo "--- [4/8] augment STATIC per-cell tail (the control) -> ${STAT_DIR} ---"
rm -rf "${STAT_DIR}"
SRC=${POOL_DIR} OUT=${STAT_DIR} SCENARIO=pooled COPULA_ENV_COLS="${ENV_COLS}" \
  TAIL_TAG=static_control ${PY} scripts/build_slow_copula_env_augment.py
rc=\$?; [ \$rc -ne 0 ] && die \$rc "static augment failed"

echo "--- [5/8] augment TRANSIENT per-(Cell,Year) tail (the arm) -> ${TRAN_DIR} ---"
rm -rf "${TRAN_DIR}"
SRC=${POOL_DIR} OUT=${TRAN_DIR} SCENARIO=pooled COPULA_ENV_COLS="${ENV_COLS}" \
  ENV_WINDOW=${WINDOW} TAIL_TAG=transient_w${WINDOW} ${PY} scripts/build_slow_copula_env_augment.py
rc=\$?; [ \$rc -ne 0 ] && die \$rc "transient augment failed"

echo "--- [6/8] K-fold-by-cell OOS eval of the TRANSIENT table (the arm) ---"
OUT=${TRAN_DIR} KFOLDS=${KFOLDS} NTREES=${EVAL_NTREES} MAX_DEPTH=${MAX_DEPTH} MIN_LEAF=${MIN_LEAF} \
  SUBSAMPLE=${EVAL_SUBSAMPLE} ${JULIA} scripts/eval_slow_copula.jl
rc=\$?; [ \$rc -ne 0 ] && die \$rc "transient eval failed"

echo "--- [7/8] K-fold-by-cell OOS eval of the STATIC table (the control) ---"
OUT=${STAT_DIR} KFOLDS=${KFOLDS} NTREES=${EVAL_NTREES} MAX_DEPTH=${MAX_DEPTH} MIN_LEAF=${MIN_LEAF} \
  SUBSAMPLE=${EVAL_SUBSAMPLE} ${JULIA} scripts/eval_slow_copula.jl
rc=\$?; [ \$rc -ne 0 ] && die \$rc "static control eval failed"

echo "--- [8/8] train + serialize the TRANSIENT copula -> ${RCOP_OUT} ---"
OUT=${TRAN_DIR} RCOP_OUT_PATH=${RCOP_OUT} NTREES=${NTREES} MAX_DEPTH=${MAX_DEPTH} \
  MIN_LEAF=${MIN_LEAF} SUBSAMPLE=${SUBSAMPLE} ${JULIA} scripts/train_slow_copula.jl
rc=\$?
echo "=== JOB DONE tag=${TAG} exit=\${rc} ==="
exit \${rc}
EOF

if [ "${SUBMIT}" = "yes" ]; then
  jid="$(sbatch "${jcf}" | awk '{print $NF}')"
  rm -f "${jcf}"
  echo "submitted MOISTURE-CONDITIONING arm ${jid} (W=${WINDOW}, VERSION=${VERSION}, ${NCPUS} cpus, ${TIME}${DEPENDENCY:+, dependency=${DEPENDENCY}})"
  echo "  base:  ${HIST_DIR} + ${SSP_DIR} -> ${POOL_DIR}"
  echo "  arms:  ${STAT_DIR} (static control) | ${TRAN_DIR} (transient)"
  echo "  rcop:  ${RCOP_OUT}"
  echo "  log:   ${LOGDIR}/${TAG}.${jid}.out"
else
  echo "== SUBMIT=no — generated jcf:"; cat "${jcf}"; rm -f "${jcf}"
fi
