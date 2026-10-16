#!/bin/bash
# Create a POEM 1.2 run directory that starts on 1 January 1851 from the POEM group's preindustrial
# spin-up (spinup_6layers_maxsnowheight-20m, its end-of-1850 state), optionally with the learned
# land emulator inside LPJmL (ADR 0347). The POEM group's run directory is only read.
#
# Usage: setup_poem_run.sh RUN_DIR MODE YEARS [DIURNAL] [MONTHS]
#   MODE    stock   - the POEM group's own executable (POEM-1.2_20261013_6-layers), emulator absent
#           off     - our build (with the emulator bridge), LANDEMU unset: must equal stock
#           shadow  - our build, emulator runs and records, hands nothing back: must equal stock
#           coupled - our build, emulator ET -> atmosphere, emulator runoff -> rivers
#   YEARS   simulated years (one executable invocation; fixed CO2, so no yearly restarts)
#   DIURNAL sun | flat (coupled only; default sun)
#   MONTHS  optional: run only this many months (gate runs); overrides YEARS*12
# Then: cd RUN_DIR && sbatch 01_submit.sh
set -euo pipefail
RUN=${1:?run dir}; MODE=${2:?mode}; YEARS=${3:?years}; DIURNAL=${4:-sun}; MONTHS=${5:-}
SRC=/p/projects/poem/data/tuning-1.2/POEM_RUNS/0.2/spinup_6layers_maxsnowheight-20m
OURS=/p/projects/open/Jamir/poem_landemu/POEM-1.2_20261013_6-layers_landemu
STOCK=/p/projects/poem/data/tuning-1.2/POEM_PROGRAM/POEM-1.2_20261013_6-layers
REPO=$(cd "$(dirname "$(readlink -f "$0")")/../../.." && pwd)
case $MODE in stock|off|shadow|coupled) ;; *) echo "bad MODE $MODE"; exit 1;; esac
case $DIURNAL in sun|flat) ;; *) echo "bad DIURNAL $DIURNAL"; exit 1;; esac
[[ -e $RUN ]] && { echo "$RUN exists - refusing to overwrite"; exit 1; }
mkdir -p "$RUN"; cd "$RUN"
for f in 01_submit.sh 92_check_water_mass_balance.sh data_table diag_table field_table sim_config.sh; do
  cp -p "$SRC/$f" .
done
cp -rp "$SRC/par" "$SRC/submit_cores" .
cp -a "$SRC/INPUT-18510101" .           # restart files + symlinks to the forcing
ln -s INPUT-18510101 INPUT
mkdir -p restart RESTART history output
ln -s "$SRC/restart/restart_POEM_1850.lpj" restart/restart_POEM_1850.lpj
sed -i -e 's/^start_year=.*/start_year=1851/' -e "s/^sim_years=.*/sim_years=$YEARS/" \
       -e 's/^delete_bling=.*/delete_bling=true/' \
       -e 's/^debug_keep_history_artifacts=.*/debug_keep_history_artifacts=true/' sim_config.sh
POEM_ROOT=$([[ $MODE == stock ]] && echo $STOCK || echo $OURS)
cat > load_poem.sh <<EOT
# written by $REPO/scripts/online_coupling/poem/setup_poem_run.sh ($MODE)
export POEM=$POEM_ROOT
export POEM_DEPENDENCIES=submit_cores/load_poem_dependencies.sh
export POEM_EXEC=\$POEM/exec/pik-hpc2024-ifort/MOM_ATLANTES_LPJ_CM2/fms_MOM_ATLANTES_LPJ_CM2.x
EOT
{
  echo "# learned land emulator settings for this run ($MODE), sourced by 01_submit.sh before mpirun"
  case $MODE in
    shadow)  echo "export LANDEMU=shadow" ;;
    coupled) echo "export LANDEMU=1"; echo "export LANDEMU_DIURNAL=$DIURNAL" ;;
    *)       echo "unset LANDEMU" ;;
  esac
  if [[ $MODE == shadow || $MODE == coupled ]]; then
    echo "export LANDEMU_OUT=$RUN/landemu"
    echo "export LANDEMU_DIR=$REPO/scripts/online_coupling"
    echo "export LANDEMU_PYHOME=/home/jamirp/.conda/envs/py311_new"
  fi
} > landemu_env.sh
# job header: our account, one node, 28 tasks (POEM's hard-coded layout); and the env hook
sed -i -e 's/^#SBATCH --qos=.*/#SBATCH --account=waldspektrum\n#SBATCH --partition=priority\n#SBATCH --qos=priority/' \
       -e "s/^#SBATCH --job-name=.*/#SBATCH --job-name=poem-$MODE-$(basename $RUN)/" \
       -e '/^#SBATCH --mail-type/d' \
       -e "s/^#SBATCH --time=.*/#SBATCH --time=$([[ -n $MONTHS ]] && echo 01:00:00 || echo 1-00:00:00)/" 01_submit.sh
sed -i 's/^print_title "Running POEM"$/source "$WORKING_DIR\/landemu_env.sh"; env | grep "^LANDEMU" || echo "LANDEMU unset"\nprint_title "Running POEM"/' 01_submit.sh
if [[ -n $MONTHS ]]; then
  sed -i "s/^num_month=\$(( sim_year_increment \* 12 ))/num_month=$MONTHS  # gate run (setup_poem_run.sh)/" 01_submit.sh
fi
grep -q 'source "$WORKING_DIR/landemu_env.sh"' 01_submit.sh || { echo "env hook not inserted"; exit 1; }
grep -n "^#SBATCH\|landemu_env\|^num_month" 01_submit.sh
echo "run dir ready: $RUN ($MODE, $YEARS yr${MONTHS:+, $MONTHS months}, diurnal $DIURNAL, POEM $POEM_ROOT)"
