#!/usr/bin/env bash
# =============================================================================
# diagnose_copula_capacity.sh — isolate ESTIMATOR CAPACITY as a cause of the
# recruit-trait copula's per-cell under-dispersion (milestone S2).
#
# WHY THIS EXISTS
# ---------------
# `scripts/diagnose_copula_cond_ceiling.py` decomposed the ADR-0030 per-cell GAP
# and found the DOMINANT term is not a missing covariate but the ESTIMATOR: a
# direct per-cell regressor on the SAME 8 conditioning columns reaches
# r=0.893 / sd_ratio=0.877 on Wooddens where the copula reaches 0.814 / 0.678.
#
# The concrete mechanism to test: `eval_slow_copula.jl` defaults
# EVAL_SUBSAMPLE=50000 while the historic table has ~158M training rows over
# ~54k cells — i.e. each tree sees roughly ONE row per cell, and with
# MAX_DEPTH=14 / MIN_LEAF=20 it can only resolve ~1250 leaves for 54 020 cells.
# The conditioning space is UNDER-RESOLVED by the subsample, not
# under-informed by the feature list. Raising the subsample and the depth
# costs almost nothing at predict time (leaf value counts stay similar) and
# needs NO conditioning change, NO artifact-format change, and NO cross-line
# contract change.
#
# This script re-runs the K-fold-by-cell OOS evaluation at a chosen capacity on
# an UNCHANGED table and scores the ADR-0030 gate, so capacity is measured in
# ISOLATION from any conditioning change. That ordering is deliberate: ADR 0033
# records this line twice crediting one change with another's effect.
#
# SAFETY — this is the load-bearing part
# --------------------------------------
# `eval_slow_copula.jl` writes `pred_<axis>.f64` INTO its OUT dir. Pointing it
# at the real `slow_copula_historic_t8` dir would OVERWRITE the validated t8
# predictions that ADR 0036 and the whole figure set rest on. So we build a
# SHADOW dir of read-only symlinks to the inputs (Xc/Y_*/cells/manifest) and
# let the predictions land there as real files. `pred_*` is NEVER symlinked —
# a symlinked pred would make the write follow the link back into the source
# dir, which is exactly the accident this guards against. Asserted below.
#
# Usage:
#   CAPTAG=cap500k EVAL_SUBSAMPLE=500000 MAX_DEPTH=18 scripts/diagnose_copula_capacity.sh
#   CAPTAG=cap2M   EVAL_SUBSAMPLE=2000000 MAX_DEPTH=22 EVAL_NTREES=60 NCPUS=64 \
#     scripts/diagnose_copula_capacity.sh
#
# Env: CAPTAG (required), SRC (seed1 table dir, default the t8 historic),
#      SRC2 (seed2 floor dir), EVAL_NTREES (40), EVAL_SUBSAMPLE (50000),
#      MAX_DEPTH (14), MIN_LEAF (20), KFOLDS (5), TIME (04:00:00),
#      NCPUS (64), SUBMIT (yes),
#      TRAIT_ONLY (0; 1 = write a trimmed manifest WITHOUT nstruct/struct_axes so
#        only the 4 PRODUCTION trait axes are evaluated -- the ADR-0030 gate axes.
#        Cuts the eval ~33%. The struct axes are diagnostic (ADR 0036) and cannot
#        change the gate's verdict, so dropping them costs the experiment nothing.)
#
# COST -- read before choosing a rung. Fit cost per (fold, axis) scales as
# ntrees*subsample; predict cost over all ~198M rows scales as ntrees. Raising the
# subsample at CONSTANT ntrees gets expensive fast (NTREES=40 SUBSAMPLE=500000 was
# measured at ~4x the 50k baseline per axis-fold and would overrun a 4 h wall),
# whereas trading trees for depth+subsample at a FIXED `ntrees*subsample` budget is
# CHEAPER than the baseline on the predict side while multiplying leaf resolution.
# The fixed-budget rungs are therefore both the affordable experiment AND the
# realistic production artifact: .rcop bytes ~= 10.7 * ntrees * subsample * naxes
# (measured on t8: 122 MB at 60 x 50000 x 4 = 1063 leaves/tree, 47 values/leaf).
# Collect: logs/S-cap-<CAPTAG>.<jobid>.out — the ADR-0030 gate table is at the end.
# =============================================================================
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE=/p/tmp/jamirp/emulator_global

CAPTAG="${CAPTAG:?set CAPTAG (a short capacity label, e.g. cap500k)}"
SRC="${SRC:-${BASE}/slow_copula_historic_t8}"
SRC2="${SRC2:-${BASE}/slow_copula_historic_seed2_t8}"
EVAL_NTREES="${EVAL_NTREES:-40}"; EVAL_SUBSAMPLE="${EVAL_SUBSAMPLE:-50000}"
MAX_DEPTH="${MAX_DEPTH:-14}"; MIN_LEAF="${MIN_LEAF:-20}"; KFOLDS="${KFOLDS:-5}"
TIME="${TIME:-04:00:00}"; NCPUS="${NCPUS:-64}"; SUBMIT="${SUBMIT:-yes}"
TRAIT_ONLY="${TRAIT_ONLY:-0}"
ACCOUNT="${ACCOUNT:-waldspektrum}"; PARTITION="${PARTITION:-standard}"; QOS="${QOS:-short}"
JULIA="${JULIA:-/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia}"   # DRF is zero-dep pure-Base
PY="${PY:-/home/jamirp/.conda/envs/py311_new/bin/python}"

SHADOW="${BASE}/capacity/${CAPTAG}"
LOGDIR="${REPO}/logs"; mkdir -p "${LOGDIR}"

[ -d "${SRC}" ]  || { echo "ERROR: SRC not a dir: ${SRC}" >&2; exit 1; }
[ -d "${SRC2}" ] || { echo "ERROR: SRC2 not a dir: ${SRC2}" >&2; exit 1; }

# ---- build the shadow dir: inputs symlinked, predictions NOT -----------------
mkdir -p "${SHADOW}"
# Clear any previous shadow content so a stale pred_ from an earlier capacity run
# can never be silently re-scored as this run's result.
find "${SHADOW}" -mindepth 1 -maxdepth 1 -exec rm -f {} +
ln -s "${SRC}/Xc.f64"               "${SHADOW}/Xc.f64"
ln -s "${SRC}/cells.i64"            "${SHADOW}/cells.i64"
if [ "${TRAIT_ONLY}" = "1" ]; then
    # A REAL (not symlinked) manifest with the struct-axes keys stripped. eval_slow_copula.jl
    # treats absent nstruct/struct_axes as 0/empty -- documented there as byte-identical to its
    # pre-struct-axes self -- so this evaluates exactly the 4 production trait axes the
    # ADR-0030 gate scores. Writing a real file here also means we never mutate SRC's manifest.
    grep -vE '^(nstruct|struct_axes)\b' "${SRC}/manifest_copula.txt" > "${SHADOW}/manifest_copula.txt"
    echo "  manifest : TRIMMED to the 4 production trait axes (TRAIT_ONLY=1)"
else
    ln -s "${SRC}/manifest_copula.txt"  "${SHADOW}/manifest_copula.txt"
fi
for y in "${SRC}"/Y_*.f64; do ln -s "${y}" "${SHADOW}/$(basename "${y}")"; done

# THE GUARD: no pred_* may be a symlink in the shadow dir, or eval_slow_copula.jl
# would write straight through it into the source table and destroy the t8 preds.
if find "${SHADOW}" -maxdepth 1 -name 'pred_*' | grep -q .; then
    echo "ERROR: a pred_* entry exists in ${SHADOW} — refusing to run (it could alias ${SRC})" >&2
    exit 1
fi
# And the source must still hold its own real (non-symlink) predictions afterwards;
# LC_ALL=C is LOAD-BEARING: the login node collates in en_US.UTF-8 (case-insensitive)
# and the SLURM batch shell in C (uppercase first), so the SAME six untouched files
# hash differently on the two nodes and the guard fires a FALSE "shadow leaked".
# record their checksums now so the job can prove it did not touch them.
SRC_PRED_SUM="$(cd "${SRC}" && ls pred_*.f64 2>/dev/null | LC_ALL=C sort | xargs -r stat -c '%n %s %Y' | md5sum | cut -d' ' -f1)"

echo "shadow dir : ${SHADOW}"
echo "  inputs   : symlinked from ${SRC} ($(find "${SHADOW}" -maxdepth 1 -type l | wc -l) links)"
echo "  capacity : NTREES=${EVAL_NTREES} SUBSAMPLE=${EVAL_SUBSAMPLE} MAX_DEPTH=${MAX_DEPTH} MIN_LEAF=${MIN_LEAF} KFOLDS=${KFOLDS}"

TAG="S-cap-${CAPTAG}"
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
set -uo pipefail
cd "${REPO}"
export POLARS_MAX_THREADS=${NCPUS} OMP_NUM_THREADS=${NCPUS}
export JULIA_DEPOT_PATH="\${JULIA_DEPOT_PATH:-\$HOME/.julia}" JULIA_NUM_THREADS=${NCPUS}
echo "=== ${TAG} on \$(hostname) at \$(date) ==="
echo "=== CAPACITY: NTREES=${EVAL_NTREES} SUBSAMPLE=${EVAL_SUBSAMPLE} MAX_DEPTH=${MAX_DEPTH} MIN_LEAF=${MIN_LEAF} ==="
echo "=== shadow=${SHADOW}  src=${SRC} (inputs symlinked; preds land in the shadow) ==="

echo; echo "== [1/3] K-fold-by-cell OOS at this capacity =========================="
OUT=${SHADOW} KFOLDS=${KFOLDS} NTREES=${EVAL_NTREES} MAX_DEPTH=${MAX_DEPTH} \\
  MIN_LEAF=${MIN_LEAF} SUBSAMPLE=${EVAL_SUBSAMPLE} ${JULIA} scripts/eval_slow_copula.jl
rc=\$?; [ \$rc -ne 0 ] && { echo "eval_slow_copula.jl FAILED rc=\$rc"; echo "=== JOB DONE tag=${TAG} exit=\$rc ==="; exit \$rc; }

echo; echo "== [2/3] the source table's own predictions must be UNTOUCHED ========="
now="\$(cd ${SRC} && ls pred_*.f64 2>/dev/null | LC_ALL=C sort | xargs -r stat -c '%n %s %Y' | md5sum | cut -d' ' -f1)"
if [ "\$now" != "${SRC_PRED_SUM}" ]; then
    echo "FATAL: ${SRC} predictions CHANGED (\$now != ${SRC_PRED_SUM}) — the shadow MAY have leaked!"
    echo "   CURRENT triples (name size mtime) — if the mtimes still match the generation"
    echo "   time, this is a guard artefact, not a leak (check LC_ALL collation first):"
    (cd ${SRC} && ls pred_*.f64 | LC_ALL=C sort | xargs -r stat -c '     %n %s %Y')
    echo "=== JOB DONE tag=${TAG} exit=9 ==="; exit 9
fi
echo "   OK: ${SRC} pred_*.f64 unchanged (md5 of name/size/mtime = \$now)"
echo "   shadow preds written here:"
ls -la ${SHADOW}/pred_*.f64 | sed 's/^/     /'

echo; echo "== [3/3] the ADR-0030 per-cell gate, on THIS capacity's predictions ==="
COPULA_DIR=${SHADOW} COPULA2_DIR=${SRC2} SKIP_PARQUET=1 SKIP_LEGACY=1 \\
  ${PY} scripts/noise_floor_vs_emulator.py
rc=\$?
echo "=== JOB DONE tag=${TAG} exit=\${rc} ==="
exit \${rc}
EOF

if [ "${SUBMIT}" = "yes" ]; then
    jid="$(sbatch "${jcf}" | awk '{print $NF}')"
    rm -f "${jcf}"
    echo "submitted capacity probe ${jid} (tag=${TAG}, ${NCPUS} cpus, ${TIME})"
    echo "  log:   ${LOGDIR}/${TAG}.${jid}.out"
    echo "  watch: grep -q 'JOB DONE' ${LOGDIR}/${TAG}.${jid}.out"
else
    echo "--- jcf (SUBMIT=no) ---"; cat "${jcf}"; rm -f "${jcf}"
fi
