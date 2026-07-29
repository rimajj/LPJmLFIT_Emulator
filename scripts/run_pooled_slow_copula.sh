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
# STRUCT_AXES — the two opt-in DIAGNOSTIC per-stem axes, BIOMASS (`agb`) and SIZE
# (`Height`), built and OOS-evaluated exactly like the 4 production trait axes but
# APPENDED after them and NEVER written into the serialized .rcop (train_slow_copula.jl
# reads the manifest's `axes` line, which keeps meaning the production axes; line M pins
# that artifact and slow.jl::make_recruit_to_pools maps exactly those 4 onto carbon
# pools — ADR 0025, a frozen cross-line contract). Same deliberate asymmetry as
# run_global_slow_copula.sh: `build_slow_runtime_table.py` defaults it EMPTY so its own
# output stays byte-identical (guardrail 4), while this orchestrator defaults it ON
# because producing the validation generation is its purpose. `STRUCT_AXES=` opts out.
# BOTH scenarios are built with the SAME value — pool_slow_tables.py refuses to pool
# tables whose struct sets differ, so an asymmetric build fails loud at step 3.
#
# Usage:
#   scripts/run_pooled_slow_copula.sh                 # submit (W=20, STEM_CAP=400)
#   SUBMIT=no scripts/run_pooled_slow_copula.sh       # print the jcf only
#   NCPUS=96 scripts/run_pooled_slow_copula.sh        # REQUIRED on the complete tree set
# Env: WINDOW (20), STEM_CAP (400), STRUCT_AXES (agb,Height), SEED (1), NTREES (60) MAX_DEPTH (14) MIN_LEAF (20)
#      SUBSAMPLE (50000), EVAL_NTREES (40) EVAL_SUBSAMPLE (50000), KFOLDS (5),
#      TIME (06:00:00), NCPUS (32), SUBMIT (yes).
# Collect: tail -f logs/gpcop_slow[_<VERSION>].<jobid>.out ; last line "=== JOB DONE ... ===".
# Artifacts: /p/tmp/jamirp/emulator_global/{slow_copula_<scen>_w<W>/, slow_copula_pooled_w<W>/,
#            recruit_copula_global_pooled_w<W>.rcop}  (DVC, not git).
# =============================================================================
set -euo pipefail

WINDOW="${WINDOW:-20}"; STEM_CAP="${STEM_CAP:-400}"; SEED="${SEED:-1}"; KFOLDS="${KFOLDS:-5}"
STRUCT_AXES="${STRUCT_AXES-agb,Height}"         # diagnostic biomass/size axes; `STRUCT_AXES=` opts out
NTREES="${NTREES:-60}"; MAX_DEPTH="${MAX_DEPTH:-14}"; MIN_LEAF="${MIN_LEAF:-20}"; SUBSAMPLE="${SUBSAMPLE:-50000}"
EVAL_NTREES="${EVAL_NTREES:-40}"; EVAL_SUBSAMPLE="${EVAL_SUBSAMPLE:-50000}"
TIME="${TIME:-06:00:00}"; NCPUS="${NCPUS:-32}"; SUBMIT="${SUBMIT:-yes}"
ACCOUNT="${ACCOUNT:-waldspektrum}"; PARTITION="${PARTITION:-standard}"; QOS="${QOS:-short}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/jamirp/.conda/envs/py311_new/bin/python"
JULIA="${JULIA:-/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia}"
LOGDIR="${REPO}/logs"; mkdir -p "${LOGDIR}"
BASE="/p/tmp/jamirp/emulator_global"

# VERSION (default empty = the legacy unsuffixed paths): appends `_<VERSION>` to every table dir, the .rcop and
# the log name. ADR 0029/0031 — line M PINS `recruit_copula_global_pooled_w<W>.rcop`, so a retrain on a changed
# basis MUST write a new versioned file and let M re-pin deliberately. `VERSION=t7` = ADR 0031's complete tree set.
VERSION="${VERSION:-}"; VER_SFX="${VERSION:+_${VERSION}}"
HIST_DIR="${BASE}/slow_copula_historic_w${WINDOW}${VER_SFX}"
SSP_DIR="${BASE}/slow_copula_ssp370_w${WINDOW}${VER_SFX}"
POOL_DIR="${BASE}/slow_copula_pooled_w${WINDOW}${VER_SFX}"
RCOP_OUT="${BASE}/recruit_copula_global_pooled_w${WINDOW}${VER_SFX}.rcop"
mkdir -p "${HIST_DIR}" "${SSP_DIR}" "${POOL_DIR}"

# DEPENDENCY=afterok:<jid> — injected as a `#SBATCH` DIRECTIVE, which is the only thing that works: the
# `SBATCH_DEPENDENCY` env var does NOT propagate through this script's own `sbatch` call and silently comes
# up `Dependency=(null)` (CLAUDE.md §9). Same knob as the other three orchestrators. Confirm a submitted job
# with `scontrol show job <jid> | grep -o 'Dependency=[^ ]*'`.
DEPENDENCY="${DEPENDENCY:-}"
dep_directive=""
[ -n "${DEPENDENCY}" ] && dep_directive="#SBATCH --dependency=${DEPENDENCY}"

jcf="$(mktemp)"
cat > "${jcf}" <<EOF
#!/usr/bin/env bash
#SBATCH --job-name=gpcop_slow${VER_SFX}
#SBATCH --account=${ACCOUNT}
#SBATCH --partition=${PARTITION}
#SBATCH --qos=${QOS}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=${NCPUS}
#SBATCH --time=${TIME}
#SBATCH --output=${LOGDIR}/gpcop_slow${VER_SFX}.%j.out
#SBATCH --error=${LOGDIR}/gpcop_slow${VER_SFX}.%j.out
${dep_directive}
set -uo pipefail
cd "${REPO}"
export POLARS_MAX_THREADS=${NCPUS} OMP_NUM_THREADS=${NCPUS}
export JULIA_DEPOT_PATH="\${JULIA_DEPOT_PATH:-\$HOME/.julia}" JULIA_NUM_THREADS=${NCPUS}
echo "=== gpcop_slow${VER_SFX} on \$(hostname) at \$(date)  W=${WINDOW} STEM_CAP=${STEM_CAP} STRUCT_AXES=${STRUCT_AXES} ==="

echo "--- [1/5] build historic transient copula table -> ${HIST_DIR} ---"
MODE=copula SCENARIO=historic SEED=${SEED} BOUNDARY_WINDOW=${WINDOW} STEM_CAP=${STEM_CAP} STRUCT_AXES="${STRUCT_AXES}" OUT=${HIST_DIR} ${PY} scripts/build_slow_runtime_table.py
rc=\$?; [ \$rc -ne 0 ] && { echo "=== JOB DONE tag=gpcop_slow${VER_SFX} exit=\$rc (historic build failed) ==="; exit \$rc; }

echo "--- [2/5] build ssp370 transient copula table -> ${SSP_DIR} ---"
MODE=copula SCENARIO=ssp370 SEED=${SEED} BOUNDARY_WINDOW=${WINDOW} STEM_CAP=${STEM_CAP} STRUCT_AXES="${STRUCT_AXES}" OUT=${SSP_DIR} ${PY} scripts/build_slow_runtime_table.py
rc=\$?; [ \$rc -ne 0 ] && { echo "=== JOB DONE tag=gpcop_slow${VER_SFX} exit=\$rc (ssp370 build failed) ==="; exit \$rc; }

echo "--- [3/5] pool -> ${POOL_DIR} ---"
IN_DIRS=${HIST_DIR},${SSP_DIR} TAGS=historic,ssp370 OUT=${POOL_DIR} ${PY} scripts/pool_slow_tables.py
rc=\$?; [ \$rc -ne 0 ] && { echo "=== JOB DONE tag=gpcop_slow${VER_SFX} exit=\$rc (pool failed) ==="; exit \$rc; }

echo "--- [4/5] K-fold-by-cell OOS trait-distribution eval -> pred_<axis>.f64 ---"
OUT=${POOL_DIR} KFOLDS=${KFOLDS} NTREES=${EVAL_NTREES} MAX_DEPTH=${MAX_DEPTH} MIN_LEAF=${MIN_LEAF} \
  SUBSAMPLE=${EVAL_SUBSAMPLE} ${JULIA} scripts/eval_slow_copula.jl
rc=\$?; [ \$rc -ne 0 ] && { echo "=== JOB DONE tag=gpcop_slow${VER_SFX} exit=\$rc (eval failed) ==="; exit \$rc; }

echo "--- [5/5] train + serialize ONE pooled+transient copula -> ${RCOP_OUT} ---"
OUT=${POOL_DIR} RCOP_OUT_PATH=${RCOP_OUT} NTREES=${NTREES} MAX_DEPTH=${MAX_DEPTH} \
  MIN_LEAF=${MIN_LEAF} SUBSAMPLE=${SUBSAMPLE} ${JULIA} scripts/train_slow_copula.jl
rc=\$?
echo "=== JOB DONE tag=gpcop_slow${VER_SFX} exit=\${rc} ==="
exit \${rc}
EOF

if [ "${SUBMIT}" = "yes" ]; then
  jid="$(sbatch "${jcf}" | awk '{print $NF}')"
  rm -f "${jcf}"
  echo "submitted POOLED+TRANSIENT copula job ${jid} (W=${WINDOW}, STEM_CAP=${STEM_CAP}, STRUCT_AXES=${STRUCT_AXES:-none}, ${NCPUS} cpus, ${TIME}${DEPENDENCY:+, dependency=${DEPENDENCY}})"
  echo "  tables: ${HIST_DIR} + ${SSP_DIR} -> ${POOL_DIR}    rcop: ${RCOP_OUT}"
  echo "  log:    ${LOGDIR}/gpcop_slow${VER_SFX}.${jid}.out"
  echo "  done?:  grep -E 'JOB DONE|pooled OOS|STEM_CAP' ${LOGDIR}/gpcop_slow${VER_SFX}.${jid}.out"
else
  echo "== SUBMIT=no — generated jcf:"; cat "${jcf}"; rm -f "${jcf}"
fi
