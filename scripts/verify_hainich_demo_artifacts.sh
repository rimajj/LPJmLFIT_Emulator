#!/usr/bin/env bash
# =============================================================================
# verify_hainich_demo_artifacts.sh — the BYTE-IDENTITY gate for guardrail 4
# ("opt-in, default byte-identical") whenever a Component-S data-pipeline change
# is supposed to be a NO-OP at the prototype cell.
#
# Hainich (global-grid cell 42490) contains only tree PFT ids 1-5 + grass 8, so a
# change to the tree-PFT POPULATION cannot touch it; a change to a FEATURE
# definition can. That asymmetry is exactly what let ADR 0031's truncation hide
# for months — every single-cell gate stayed green while the global tables were
# built on a third less forest. So the no-op has to be MEASURED, not assumed.
#
# Regenerates all four committed Hainich demo artifacts from the current code,
# in one SLURM job (disconnect-proof, CLAUDE.md §2), writing them to their real
# committed paths:
#   test/testitems/references/hainich_slow_oracle_{counts,traits}.csv
#   test/testitems/references/drf_forest_hainich.drf (+ _meta.txt)
#   test/testitems/references/recruit_copula_hainich.rcop (+ _meta.txt)
# then prints `git status`/`git diff --stat` for that directory. A CLEAN tree is
# the pass. Anything else means the change moved a golden fixture — STOP and find
# out why before retraining anything global (ADR 0031 §3).
#
# The verdict is TWO-TIER, because "the fixtures moved" alone does not say WHY. Step 5 runs
# scripts/diagnose_slow_table_drift.py, which rebuilds the table with the builder as of
# CONTROL_REF and diffs it against the working tree's:
#   exit 0  PASS          fixtures byte-identical.
#   exit 2  STALE-FIXTURE fixtures moved, but the control says the edit is a no-op for cell
#                         42490 ⇒ the fixtures were already out of date (this is the real state
#                         of drf_forest_hainich.drf as of 2026-07-28 — ADR 0032).
#   exit 1  FAIL          the control confirms the edit itself moved the table. STOP.
#
# The artifacts are git-tracked, so a FAILED gate is trivially recoverable:
#   git checkout -- test/testitems/references/
#
# Usage:
#   scripts/verify_hainich_demo_artifacts.sh              # submit
#   SUBMIT=no scripts/verify_hainich_demo_artifacts.sh    # print the jcf only
# Env: SEED (1), CONTROL_REF (HEAD), TIME (01:00:00), NCPUS (16), SUBMIT (yes).
# Watch: tail -f logs/hainich_verify.<jobid>.out ; last line "=== JOB DONE ... ==="
# =============================================================================
set -euo pipefail

SEED="${SEED:-1}"
CONTROL_REF="${CONTROL_REF:-HEAD}"   # the control builder for the "is my edit a no-op?" comparison
TIME="${TIME:-01:00:00}"; NCPUS="${NCPUS:-16}"; SUBMIT="${SUBMIT:-yes}"
ACCOUNT="${ACCOUNT:-waldspektrum}"; PARTITION="${PARTITION:-standard}"; QOS="${QOS:-short}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/home/jamirp/.conda/envs/py311_new/bin/python"
JULIA="${JULIA:-/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia}"   # DRF is zero-dep pure-Base
LOGDIR="${REPO}/logs"; mkdir -p "${LOGDIR}"

COUNT_DIR="/p/tmp/jamirp/slow_runtime"          # the Hainich demo COUNT table (train_slow_drf.jl default)
COP_DIR="/p/tmp/jamirp/slow_copula_hainich"     # the Hainich demo COPULA table (train_slow_copula.jl default)
mkdir -p "${COUNT_DIR}" "${COP_DIR}"

jcf="$(mktemp)"
cat > "${jcf}" <<EOF
#!/usr/bin/env bash
#SBATCH --job-name=hainich_verify
#SBATCH --account=${ACCOUNT}
#SBATCH --partition=${PARTITION}
#SBATCH --qos=${QOS}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=${NCPUS}
#SBATCH --time=${TIME}
#SBATCH --output=${LOGDIR}/hainich_verify.%j.out
#SBATCH --error=${LOGDIR}/hainich_verify.%j.out
set -uo pipefail
cd "${REPO}"
export POLARS_MAX_THREADS=${NCPUS} OMP_NUM_THREADS=${NCPUS}
export JULIA_DEPOT_PATH="\${JULIA_DEPOT_PATH:-\$HOME/.julia}" JULIA_NUM_THREADS=${NCPUS}
echo "=== hainich_verify on \$(hostname) at \$(date) ==="
echo "--- git HEAD: \$(git rev-parse --short HEAD) ---"
rc_all=0

echo ""
echo "--- [1/5] Gate-3 oracle reference (counts + traits CSV) ---"
SEED=${SEED} ${PY} scripts/build_slow_oracle_reference.py || rc_all=1

echo ""
echo "--- [2/5] Hainich demo COUNT table (CELLS=42490) -> ${COUNT_DIR} ---"
CELLS=42490 SEED=${SEED} OUT=${COUNT_DIR} ${PY} scripts/build_slow_runtime_table.py || rc_all=1

echo ""
echo "--- [3/5] retrain the demo DRF -> committed drf_forest_hainich.drf ---"
OUT=${COUNT_DIR} ${JULIA} scripts/train_slow_drf.jl || rc_all=1

echo ""
echo "--- [4/5] Hainich demo COPULA table + .rcop ---"
MODE=copula CELLS=42490 SEED=${SEED} OUT=${COP_DIR} ${PY} scripts/build_slow_runtime_table.py || rc_all=1
OUT=${COP_DIR} ${JULIA} scripts/train_slow_copula.jl || rc_all=1

echo ""
echo "--- [5/6] CONTROL: did the working tree change the table at all? (vs REF=${CONTROL_REF}) ---"
# Two-tier verdict. A byte-identity gate alone CONFLATES "your edit moved Hainich" with "the committed
# fixture was already stale" — and the latter is real: the committed .drf was trained on the Hainich PROXY
# features (soilmoist 0.7 / lai 21.2) and any regeneration now yields the REAL joined ones (0.85 / 3.07).
# So run the control comparison and let it decide which failure a moved fixture actually is.
CELL=42490 REF=${CONTROL_REF} SEED=${SEED} ${PY} scripts/diagnose_slow_table_drift.py
drift_rc=\$?
echo "--- control exit=\${drift_rc} (0 = the edit is a no-op for this cell) ---"

echo ""
echo "--- [6/6] BYTE-IDENTITY VERDICT on test/testitems/references/ ---"
git status --porcelain -- test/testitems/references/ > /tmp/hainich_verify_\$\$.status 2>&1
if [ -s /tmp/hainich_verify_\$\$.status ]; then
    echo "!! FIXTURES MOVED. Files:"
    cat /tmp/hainich_verify_\$\$.status
    echo ""
    echo "--- git diff --stat ---"
    git diff --stat -- test/testitems/references/
    echo ""
    echo "--- git diff (text fixtures; first 200 lines) ---"
    git diff -- test/testitems/references/ | head -200
    echo ""
    if [ \${drift_rc} -eq 0 ]; then
        echo "VERDICT: STALE-FIXTURE — fixtures moved but the CONTROL says the working tree is a NO-OP for"
        echo "         cell 42490, so these fixtures were ALREADY out of date w.r.t. the builder. This is not"
        echo "         caused by the change under test. Record it (ADR 0032) and regenerate DELIBERATELY as an"
        echo "         integration point with line M — never as a side effect of another milestone."
        rc_all=2
    else
        echo "VERDICT: FAIL — the CONTROL confirms the change under test moved the table (ADR 0031 §3)."
        echo "         STOP; do not retrain global on a moved basis."
        rc_all=1
    fi
    echo "Recover the fixtures with: git checkout -- test/testitems/references/"
else
    echo "VERDICT: PASS — all committed Hainich fixtures regenerated BYTE-IDENTICAL."
    [ \${drift_rc} -ne 0 ] && { echo "         (but the CONTROL flagged table drift — investigate.)"; rc_all=1; }
fi
rm -f /tmp/hainich_verify_\$\$.status
echo "=== JOB DONE tag=hainich_verify exit=\${rc_all} ==="
exit \${rc_all}
EOF

if [ "${SUBMIT}" != "yes" ]; then cat "${jcf}"; rm -f "${jcf}"; exit 0; fi
jid="$(sbatch "${jcf}" | awk '{print $NF}')"
rm -f "${jcf}"
echo "submitted job ${jid}: Hainich demo-artifact byte-identity gate (${NCPUS} cpus, ${TIME})"
echo "  log:   ${LOGDIR}/hainich_verify.${jid}.out"
echo "  watch: tail -f ${LOGDIR}/hainich_verify.${jid}.out"
echo "  pass?: grep -E 'VERDICT: (PASS|FAIL)' ${LOGDIR}/hainich_verify.${jid}.out"
