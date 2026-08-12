#!/bin/bash
# Run one arm of RUNG 2 for LINE S: the SHIPPED Component-S count model deciding who dies inside
# LPJmL-FIT's own daily physics (ADR 0175).
#
# Unlike scripts/run_rung2_armc.sh — which takes the count target from the ported hazard itself
# (RHO=expected, pinning theta=1) or from the recorded baseline's realized thinning (RHO=recorded), and so
# never asks the LEARNED model anything — this one takes rho from the production count DRF, evaluated on a
# feature row built off the roster the C publishes each year:
#
#   ARM=S0   f_i = rho for every tree     (the shipped uniform thinning, with a LEARNED target)
#   ARM=S1   f_i = (1 - mort_i)^theta     (learned target, trait-hazard ordering — the S1 - S0 measurement)
#   ARM=NP   rho = 1 every year           (the PERSISTENCE NULL: keep the stand, learn nothing)
#
# RUN THE NULLS FIRST, ALWAYS.  ADR 0112 showed a persistence null matches the production model on every
# response statistic OFFLINE.  If NP also ties S0/S1 here, this harness has no more power than the offline
# basis did and no S number from it means anything.  And run MODE=none of run_rung2_replay_arm.sh, which
# validates the TRANSPORT — a green null control plus a diverging arm means suspect the payload, not the
# interface (ADR 0121).
#
# Establishment always stays with the C (the harness answers ESTAB_C), so every number here is a MORTALITY
# result: the recruits half has a structural replay floor of 0.907 (ADR 0121).
#
# Env knobs:
#   ARM      S0 | S1 | NP                        (default: S1)
#   NPREV    roster | predict                    (default: roster)
#              roster  — n_prev is the stand's OWN previous stem count, which is the quantity the count
#                        model was TRAINED on (ADR 0112) and the ADR-0175 fix.
#              predict — n_prev is the model's own previous prediction, i.e. the shipped coupled path.
#                        Run this as the contrast arm: it is what ADR 0113-0116 measured.
#   SEED     integer, the harness's draw seed    (default: 1)
#   CELL     orderA cell index                   (default: 42490, Hainich)
#   DRF      serialized count forest             (default: the committed Hainich artifact)
#   SRC      run dir whose lpjml.js is reused    (default: the v6 record run's)
#   TAG      run tag                             (default: S_r2s_${ARM}_${NPREV}_s${SEED})
#   SUBMIT   yes | no                            (default: yes)
#
# ⚠ Needs a v6 binary and a v6-recorded reference dump — the harness REFUSES a roster with no `rootzone_w`
# column rather than proxying `soilmoist` (the ADR-0035 trap).  Re-record with MODE=record after a rebuild.
#
# Usage:  ARM=NP bash scripts/run_rung2_s_arm.sh   # the null, first
#         ARM=S1 bash scripts/run_rung2_s_arm.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JULIA=/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia
ARM="${ARM:-S1}"
NPREV="${NPREV:-roster}"
SEED="${SEED:-1}"
CELL="${CELL:-42490}"
DRF="${DRF:-$REPO/test/testitems/references/drf_forest_hainich.drf}"
SRC="${SRC:-/p/tmp/jamirp/esm_land_daily/daily_2000_2019_historic_S_rung2rec_v6_c42490_seed1}"
TAG="${TAG:-S_r2s_${ARM}_${NPREV}_s${SEED}}"
SUBMIT="${SUBMIT:-yes}"

case "$ARM" in S0|S1|NP) ;; *) echo "ARM must be S0, S1 or NP (got '$ARM')" >&2; exit 2 ;; esac
case "$NPREV" in roster|predict) ;; *)
  echo "NPREV must be roster or predict (got '$NPREV')" >&2; exit 2 ;; esac
[ -f "$DRF" ] || { echo "no count forest at $DRF" >&2; exit 2; }
[ -f "$SRC/scripts_for_running_the_model/lpjml.js" ] || { echo "no lpjml.js under $SRC" >&2; exit 2; }

DST="/p/tmp/jamirp/esm_land_daily/daily_2000_2019_historic_${TAG}_c${CELL}_seed1"
APPLY="/p/tmp/jamirp/S_rung2/${TAG}_apply"
NEWDUMP="/p/tmp/jamirp/S_rung2/${TAG}_dump"

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
$JULIA --project=$REPO $REPO/scripts/rung2_s_demography_harness.jl \\
    --arm=$ARM --n-prev=$NPREV --seed=$SEED --cell=$CELL --drf=$DRF \\
    --apply-dir=$APPLY --ready=$APPLY/harness.ready --max-idle=300 > $DST/harness.out 2>&1 &
HPID=\$!
for i in \$(seq 1 120); do
  [ -f "$APPLY/harness.ready" ] && break
  kill -0 \$HPID 2>/dev/null || { echo "FATAL: harness died before becoming ready"; cat $DST/harness.out; exit 9; }
  sleep 1
done
[ -f "$APPLY/harness.ready" ] || { echo "FATAL: harness not ready after 120 s"; cat $DST/harness.out; exit 9; }
echo "harness ready after \$i s"

mpirun /home/jamirp/lpjml56fit/bin/lpjml_rung2_v6 -DFROM_RESTART $DST/scripts_for_running_the_model/lpjml.js
RC=\$?
sleep 2
kill \$HPID 2>/dev/null || true
wait \$HPID 2>/dev/null || true
echo "=== lpjml rc=\$RC  arm=$ARM  n_prev=$NPREV  seed=$SEED  cell=$CELL ==="
exit \$RC
JCF

echo "arm=$ARM  n_prev=$NPREV  seed=$SEED  cell=$CELL  run=$DST"
echo "  count forest  : $DRF"
echo "  new dump      : $NEWDUMP"
echo "  rendezvous    : $APPLY"
if [ "$SUBMIT" = "yes" ]; then
  sbatch "$DST/scripts_for_running_the_model/slurm.jcf"
else
  echo "  (SUBMIT=no; sbatch $DST/scripts_for_running_the_model/slurm.jcf)"
fi
