#!/bin/bash
# Run one arm of the rung-2 ARM C experiment (line M; line S's option-(c) interface, ADR 0117).
#
# Unlike scripts/run_rung2_replay_arm.sh — which serves the C its OWN recorded decision back and
# measures the transport — this serves a COMPUTED decision from the ported FIT hazard:
#
#   ARM=C0   f_i = rho for every tree            (the shipped uniform thinning = the NO-SELECTION NULL)
#   ARM=C1   f_i = (1 - mort_i)^theta            (the count target pinned; the hazard sets the ordering)
#
# C1 - C0 is the measurement: how much of FIT's trait response is differential survival.  Run BOTH, and
# run each at several SEEDs — the decision is a Bernoulli draw, so one seed is one realization and the
# C's own single-seed truth is not an observable (CLAUDE.md, ADR 0106).
#
# Establishment always stays with the C (the harness answers ESTAB_C): the recruits half has a structural
# replay floor of 0.907 (ADR 0121) and substituting it would spend the exactness that makes a mortality
# difference attributable.
#
# Env knobs:
#   ARM      C0 | C1                             (default: C1)
#   RHO      expected | recorded                 (default: expected)
#              expected — rho = the operator's own mean survival on the live roster.  Pins theta to 1
#                         analytically, so the arm doubles as a LIVE identity check of the whole chain.
#              recorded — rho = the recorded baseline's REALIZED survival at that patch-year, so theta
#                         scatters around 1 and the bisection is exercised.
#   SEED     integer, the harness's draw seed    (default: 1)
#   DUMP     LPJ_RUNG2_DIR of the RECORDED run   (default: the v5 Hainich baseline; needed by RHO=recorded)
#   SRC      run dir whose lpjml.js is reused    (default: the same run's)
#   TAG      run tag                             (default: M_r2armc_${ARM}_${RHO}_s${SEED})
#   SUBMIT   yes | no                            (default: yes)
#
# Usage:  ARM=C1 SEED=1 bash scripts/run_rung2_armc.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JULIA=/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia
ARM="${ARM:-C1}"
RHO="${RHO:-expected}"
SEED="${SEED:-1}"
DUMP="${DUMP:-/p/tmp/jamirp/M_rung2/M_rung2rec_v5_dump}"
SRC="${SRC:-/p/tmp/jamirp/esm_land_daily/daily_2000_2019_historic_M_rung2ind_c42490_42490_seed1}"
TAG="${TAG:-M_r2armc_${ARM}_${RHO}_s${SEED}}"
SUBMIT="${SUBMIT:-yes}"

case "$ARM" in C0|C1) ;; *) echo "ARM must be C0 or C1 (got '$ARM')" >&2; exit 2 ;; esac
case "$RHO" in expected|recorded) ;; *) echo "RHO must be expected or recorded (got '$RHO')" >&2; exit 2 ;; esac
[ -d "$DUMP" ] || { echo "no recorded dump at $DUMP" >&2; exit 2; }
[ -f "$SRC/scripts_for_running_the_model/lpjml.js" ] || { echo "no lpjml.js under $SRC" >&2; exit 2; }

DST="/p/tmp/jamirp/esm_land_daily/daily_2000_2019_historic_${TAG}_c42490_seed1"
APPLY="/p/tmp/jamirp/M_rung2/${TAG}_apply"
NEWDUMP="/p/tmp/jamirp/M_rung2/${TAG}_dump"

rm -rf "$DST" "$APPLY" "$NEWDUMP"
mkdir -p "$DST/output" "$DST/scripts_for_running_the_model" "$APPLY" "$NEWDUMP"
cp "$SRC/scripts_for_running_the_model/"*.js "$DST/scripts_for_running_the_model/"
for f in "$DST/scripts_for_running_the_model/"*.js; do sed -i "s|$SRC|$DST|g" "$f"; done

cat > "$DST/scripts_for_running_the_model/slurm.jcf" <<JCF
#!/bin/bash
#SBATCH --ntasks=1
#SBATCH --qos=priority
#SBATCH --partition=priority
#SBATCH -J ${TAG}
#SBATCH --time=00:40:00
#SBATCH -o $DST/lpjml.%j.out
#SBATCH -e $DST/lpjml.%j.err

source /etc/profile.d/00-modulepath.sh 2>/dev/null || true
source /etc/profile.d/modules.sh 2>/dev/null || true
module purge 2>/dev/null || true
module load intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 netcdf-c curl/8.4.0 expat/2.5.0

export LPJROOT=/home/jamirp/lpjml56fit
export LPJOUTPATH=$DST
export LPJRESTARTPATH=$DST
export LPJ_RUNG2_DIR=$NEWDUMP
export LPJ_RUNG2_APPLY_DIR=$APPLY
export LPJ_RUNG2_APPLY_TIMEOUT=600
ulimit -c unlimited

# The harness must be answering BEFORE the first rendezvous, or the C fails the whole run on the apply
# timeout.  Julia's load is seconds, not instant, so wait for its ready marker instead of sleeping a
# guessed interval.
cd $REPO
$JULIA --project=$REPO $REPO/scripts/rung2_armc_harness.jl \\
    --arm=$ARM --rho=$RHO --seed=$SEED --dump=$DUMP \\
    --apply-dir=$APPLY --ready=$APPLY/harness.ready --max-idle=300 > $DST/harness.out 2>&1 &
HPID=\$!
for i in \$(seq 1 120); do
  [ -f "$APPLY/harness.ready" ] && break
  kill -0 \$HPID 2>/dev/null || { echo "FATAL: harness died before becoming ready"; cat $DST/harness.out; exit 9; }
  sleep 1
done
[ -f "$APPLY/harness.ready" ] || { echo "FATAL: harness not ready after 120 s"; cat $DST/harness.out; exit 9; }
echo "harness ready after \$i s"

mpirun /home/jamirp/lpjml56fit/bin/lpjml -DFROM_RESTART $DST/scripts_for_running_the_model/lpjml.js
RC=\$?
sleep 2
kill \$HPID 2>/dev/null || true
wait \$HPID 2>/dev/null || true
echo "=== lpjml rc=\$RC  arm=$ARM  rho=$RHO  seed=$SEED ==="
exit \$RC
JCF

echo "arm=$ARM  rho=$RHO  seed=$SEED  run=$DST"
echo "  recorded dump : $DUMP"
echo "  new dump      : $NEWDUMP"
echo "  rendezvous    : $APPLY"
if [ "$SUBMIT" = "yes" ]; then
  sbatch "$DST/scripts_for_running_the_model/slurm.jcf"
else
  echo "  (SUBMIT=no; sbatch $DST/scripts_for_running_the_model/slurm.jcf)"
fi
