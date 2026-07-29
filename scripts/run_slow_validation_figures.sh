#!/usr/bin/env bash
# =============================================================================
# run_slow_validation_figures.sh — the WHOLE Component-S validation figure set for a
# trained generation, as ONE SLURM job: per-scenario figures 01-13 + metrics*.txt, then
# one self-contained HTML report inlining all of them.
#
# It exists because the figure set is now three scenarios x 13 figures x 3 metrics files
# and was being re-derived by hand each time (the count OUT dir and the copula table dir
# are DIFFERENT dirs whose names do not follow one pattern — see the case block below,
# which is the actual knowledge this script carries).
#
# Prerequisites per scenario (the script CHECKS them and skips a scenario loudly rather
# than emitting a half-empty figure dir):
#   count   OUT/preds_oos.f64   <- scripts/eval_slow_drf.jl        (K-fold BY CELL)
#   copula  COPULA_OUT/pred_<axis>.f64 <- scripts/eval_slow_copula.jl
# Figures 12/13 (stand BIOMASS) additionally need the copula table to carry the opt-in
# STRUCT axes (`agb`), i.e. it must have been built with STRUCT_AXES=agb,Height.
#
# Usage:
#   VERSION=t8 scripts/run_slow_validation_figures.sh
#   VERSION=t8 SCENARIOS=historic scripts/run_slow_validation_figures.sh
#   VERSION=t8 DEPENDENCY=afterok:1641321:1641322:1641323 scripts/run_slow_validation_figures.sh
#   VERSION=t8 SUBMIT=no scripts/run_slow_validation_figures.sh      # print the jcf
# Env: VERSION (required in practice; empty = the legacy unsuffixed dirs), SCENARIOS
#      (historic,ssp370,pooled), REPORT (yes), TIME (04:00:00), NCPUS (16), DEPENDENCY, SUBMIT (yes).
# Collect: logs/S-figs<_VERSION>.<jobid>.out ; last line "=== JOB DONE ... ===".
# Artifacts: figures/emulator_validation/<scen><_VERSION>/ (git-ignored) + report.html.
# =============================================================================
set -euo pipefail

VERSION="${VERSION:-}"; VER_SFX="${VERSION:+_${VERSION}}"
SCENARIOS="${SCENARIOS:-historic,ssp370,pooled}"
REPORT="${REPORT:-yes}"
TIME="${TIME:-04:00:00}"; NCPUS="${NCPUS:-16}"; SUBMIT="${SUBMIT:-yes}"
ACCOUNT="${ACCOUNT:-waldspektrum}"; PARTITION="${PARTITION:-standard}"; QOS="${QOS:-short}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/jamirp/.conda/envs/py311_new/bin/python"
LOGDIR="${REPO}/logs"; mkdir -p "${LOGDIR}"
BASE="/p/tmp/jamirp/emulator_global"

DEPENDENCY="${DEPENDENCY:-}"
dep_directive=""
[ -n "${DEPENDENCY}" ] && dep_directive="#SBATCH --dependency=${DEPENDENCY}"

# Resolve each scenario's two INPUT dirs. This mapping is the knowledge worth keeping: the count table and the
# copula table live in differently-named dirs, and `pooled` uses the w20 transient-boundary pair (ADR 0026)
# whose count dir is `slow_count_pooled_w20_*` — NOT a `slow_runtime_*` dir, and it carries no cell_meta.parquet
# (so figure 08 is legitimately absent there).
resolve() {
  case "$1" in
    historic) COUNT_DIR="${BASE}/slow_runtime_historic${VER_SFX}"; COP_DIR="${BASE}/slow_copula_historic${VER_SFX}" ;;
    ssp370)   COUNT_DIR="${BASE}/slow_runtime_ssp370${VER_SFX}";   COP_DIR="${BASE}/slow_copula_ssp370${VER_SFX}" ;;
    pooled)   COUNT_DIR="${BASE}/slow_count_pooled_w20${VER_SFX}"; COP_DIR="${BASE}/slow_copula_pooled_w20${VER_SFX}" ;;
    *) echo "FATAL: unknown scenario '$1' (want historic|ssp370|pooled)"; return 1 ;;
  esac
}

body=""
labels=""
IFS=',' read -r -a scens <<< "${SCENARIOS}"
for s in "${scens[@]}"; do
  resolve "${s}"
  FIGDIR="figures/emulator_validation/${s}${VER_SFX}"
  labels="${labels}${labels:+,}${s}${VER_SFX}"
  body="${body}
echo \"--- figures: ${s} ---\"
if [ ! -f ${COUNT_DIR}/preds_oos.f64 ]; then
  echo \"   SKIP ${s}: ${COUNT_DIR}/preds_oos.f64 missing (run scripts/eval_slow_drf.jl on that table first)\"
elif [ ! -f ${COP_DIR}/manifest_copula.txt ]; then
  echo \"   SKIP ${s}: ${COP_DIR}/manifest_copula.txt missing (the copula job has not produced a table)\"
elif [ ! -f ${COP_DIR}/pred_SLA.f64 ]; then
  echo \"   SKIP ${s}: ${COP_DIR}/pred_SLA.f64 missing — the table exists but eval_slow_copula.jl has not\"
  echo \"        finished (it writes every pred_<axis>.f64 only AFTER the last fold, so a killed eval leaves\"
  echo \"        a complete-looking table dir with no predictions at all).\"
else
  grep -q '^struct_axes' ${COP_DIR}/manifest_copula.txt \\
    || echo \"   NOTE ${s}: copula table has no STRUCT axes -> figures 12/13 (biomass) will be absent\"
  OUT=${COUNT_DIR} COPULA_OUT=${COP_DIR} SCENARIO=${s} FIGDIR=${FIGDIR} ${PY} scripts/plot_slow_emulator_validation.py
  rc=\$?; [ \$rc -ne 0 ] && { echo \"   *** ${s} FAILED (exit \$rc)\"; fail=\$rc; }
fi
"
done

if [ "${REPORT}" = "yes" ]; then
  body="${body}
echo \"--- one self-contained HTML report over: ${labels} ---\"
SCENARIOS=${labels} GENERATION=${VERSION:-legacy} OUT=figures/emulator_validation/report${VER_SFX}.html \\
  ${PY} scripts/build_slow_validation_report.py
rc=\$?; [ \$rc -ne 0 ] && { echo \"   *** report FAILED (exit \$rc)\"; fail=\$rc; }
"
fi

jcf="$(mktemp)"
cat > "${jcf}" <<EOF
#!/usr/bin/env bash
#SBATCH --job-name=S-figs${VER_SFX}
#SBATCH --account=${ACCOUNT}
#SBATCH --partition=${PARTITION}
#SBATCH --qos=${QOS}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=${NCPUS}
#SBATCH --time=${TIME}
#SBATCH --output=${LOGDIR}/S-figs${VER_SFX}.%j.out
#SBATCH --error=${LOGDIR}/S-figs${VER_SFX}.%j.out
${dep_directive}
set -uo pipefail
cd "${REPO}"
export POLARS_MAX_THREADS=${NCPUS} OMP_NUM_THREADS=${NCPUS} MPLBACKEND=Agg
fail=0
echo "=== S-figs${VER_SFX} on \$(hostname) at \$(date)  scenarios=${SCENARIOS} ==="
${body}
echo "=== JOB DONE tag=S-figs${VER_SFX} exit=\${fail} ==="
exit \${fail}
EOF

if [ "${SUBMIT}" = "yes" ]; then
  jid="$(sbatch "${jcf}" | awk '{print $NF}')"
  rm -f "${jcf}"
  echo "submitted validation-figure job ${jid} (scenarios=${SCENARIOS}${DEPENDENCY:+, dependency=${DEPENDENCY}})"
  echo "  figures: figures/emulator_validation/<scen>${VER_SFX}/    report: .../report${VER_SFX}.html"
  echo "  log:     ${LOGDIR}/S-figs${VER_SFX}.${jid}.out"
else
  echo "== SUBMIT=no — generated jcf:"; cat "${jcf}"; rm -f "${jcf}"
fi
