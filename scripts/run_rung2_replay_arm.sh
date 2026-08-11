#!/bin/bash
# Run one arm of the rung-2 replay experiment (line M, ADR 0061 + read-back half).
#
# Feeds LPJmL-FIT its OWN recorded demography back through the substitution hook
# and records what the substituted run then does.  Three arms, and running them
# separately is the whole point — a divergence is only attributable if each half
# of the interface is exercised on its own:
#
#   MODE=kills     the recorded kill set is applied; establishment stays with the C
#   MODE=recruits  the recorded recruit set is applied; mortality stays with the C
#   MODE=both      both halves substituted
#
# Env knobs (all optional except where noted):
#   MODE      kills | recruits | both            (default: both)
#   DUMP      LPJ_RUNG2_DIR of the RECORDED run  (default: the Hainich 42490 dump)
#   SRC       run dir whose lpjml.js is reused   (default: the same run's)
#   TAG       run tag                            (default: M_rung2replay_$MODE)
#   SUBMIT    yes | no                           (default: yes)
#
# Usage:  MODE=kills bash scripts/run_rung2_replay_arm.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${MODE:-both}"
DUMP="${DUMP:-/p/tmp/jamirp/M_rung2/dump_ind_c42490}"
SRC="${SRC:-/p/tmp/jamirp/esm_land_daily/daily_2000_2019_historic_M_rung2ind_c42490_42490_seed1}"
TAG="${TAG:-M_rung2replay_${MODE}}"
SUBMIT="${SUBMIT:-yes}"

case "$MODE" in
  kills|recruits|both|none) ;;
  *) echo "MODE must be kills, recruits, both or none (got '$MODE')" >&2; exit 2 ;;
esac
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
#SBATCH --time=00:30:00
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
export LPJ_RUNG2_APPLY_TIMEOUT=300
ulimit -c unlimited

python3 $REPO/scripts/rung2_replay_harness.py --mode $MODE \\
    --dump $DUMP --apply-dir $APPLY --max-idle 300 > $DST/harness.out 2>&1 &
HPID=\$!
sleep 5

mpirun /home/jamirp/lpjml56fit/bin/lpjml -DFROM_RESTART $DST/scripts_for_running_the_model/lpjml.js
RC=\$?
sleep 2
kill \$HPID 2>/dev/null || true
wait \$HPID 2>/dev/null || true
echo "=== lpjml rc=\$RC  mode=$MODE ==="
exit \$RC
JCF

echo "mode=$MODE  run=$DST"
echo "  recorded dump : $DUMP"
echo "  new dump      : $NEWDUMP"
echo "  rendezvous    : $APPLY"
if [ "$SUBMIT" = "yes" ]; then
  sbatch "$DST/scripts_for_running_the_model/slurm.jcf"
else
  echo "  (SUBMIT=no; sbatch $DST/scripts_for_running_the_model/slurm.jcf)"
fi
