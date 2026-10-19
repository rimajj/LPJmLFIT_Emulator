#!/bin/bash
# clu_emu_runs.sh inputs | hist <seed> [dependency] | legs <seed> "<GCM ...>" "<ssp ...>" [rising|fixed] [dependency]
# -- the original-model runs for the warming-response proof (ADR 0342): merged LPJmL-FIT, NITROGEN ON (no phosphorus),
# TRANSIENT CO2, on the 674-cell representative grid (scripts/clu_emu.py grid) with 25 forest patches per cell. Uses
# the lpjml-fit tooling UNCHANGED (cut_inputs.py, fit_input_list.py, cut_scenario.py, clustered_run.sh,
# scenario_run.sh); the model is the frozen snapshot of /home/jamirp/port-wt-nitrogen-on at ef38b509e.
#   inputs   cut the historical inputs + every (GCM, SSP) scenario climate to the grid (one SLURM job)
#   hist     spin-up (1000 yr) + 1901-2019 for one seed -> $RUNS/emu-non-rep-s<seed>; lean output list via
#            scripts/clu_emu_hook.sh (daily fluxes as per-cell binary, no trait histograms)
#   legs     2020-2100 continuations from that run's 2019 state, ONE BRANCH DIRECTORY PER CLIMATE MODEL
#            ($RUNS/emu-non-rep-s<seed>__<gcm>; scenario_run.sh names outputs by SSP only, so two climate models in
#            one directory would overwrite each other). CO2 rising (the SSP's) or fixed at 2019 (twin).
set -euo pipefail
LF=/home/jamirp/lpjml-fit/scripts/clustered
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
G=/p/projects/reformit/Jamir/lpjml-fit-clustered/grids/k674_lowrank_hist_rep1_seed1
TREE=/p/projects/reformit/Jamir/lpjml-fit-clustered/trees/nitrogen-on-ef38b509e
RUNS=/p/projects/reformit/Jamir/lpjml-fit-clustered/runs
PY311=/home/jamirp/.conda/envs/py311/bin/python3
GCMS_ALL="GFDL-ESM4 IPSL-CM6A-LR MPI-ESM1-2-HR MRI-ESM2-0 UKESM1-0-LL CanESM5 CNRM-CM6-1 CNRM-ESM2-1 EC-Earth3 MIROC6"
SSPS_ALL="ssp126 ssp370 ssp585"
dep() { [ -n "${1:-}" ] && echo "--dependency=afterok:$1 --kill-on-invalid-dep=yes" || true; }

case "${1:-}" in
inputs)
  sbatch --parsable --job-name=emu-clu-cut --account=waldspektrum --partition=standard --qos=short --cpus-per-task=2 \
    --mem=32G --time=03:00:00 --output="$REPO/logs/emu-clu-cut.%j.out" --wrap "set -e; cd /home/jamirp/lpjml-fit
    $PY311 -u $LF/cut_inputs.py $G $TREE
    $PY311 -u $LF/fit_input_list.py $G
    for s in $SSPS_ALL; do for g in $GCMS_ALL; do $PY311 -u $LF/cut_scenario.py $G \$s \$g; done; done
    echo '=== JOB DONE exit=0 ==='" ;;
hist)
  SEED=${2:?seed}
  # shellcheck disable=SC2046
  TREE=$TREE NAME=emu-non-rep-s$SEED SEED=$SEED NPATCH_CELL=25 CONFIG_HOOK="$REPO/scripts/clu_emu_hook.sh" \
    sbatch --parsable --export=ALL --time=05:00:00 --job-name=emu-clu-hist-s$SEED \
    --output="$REPO/logs/emu-clu-hist-s$SEED.%j.out" $(dep "${3:-}") "$LF/clustered_run.sh" "$G" ;;
legs)
  SEED=${2:?seed}; GCMS=${3:?gcms}; SSPS=${4:?ssps}; CO2=${5:-rising}; D=${6:-}
  BASE=$RUNS/emu-non-rep-s$SEED
  for g in $GCMS; do
    gl=$(echo "$g" | tr 'A-Z' 'a-z'); B=${BASE}__$gl
    for s in $SSPS; do
      # shellcheck disable=SC2046
      sbatch --parsable --job-name="emu-clu-$s-$gl-s$SEED${CO2/rising/}" --account=waldspektrum --partition=priority \
        --qos=standby --nodes=1 --ntasks=128 --cpus-per-task=1 --mem=300G --time=02:00:00 $(dep "$D") \
        --output="$REPO/logs/emu-clu-leg-$s-$gl-s$SEED-$CO2.%j.out" --wrap "set -e
        mkdir -p $B/output $B/restart
        ln -sfn $BASE/restart/restart_2019_nv.lpj $B/restart/restart_2019_nv.lpj
        ln -sfn $BASE/historical.stdout $B/historical.stdout
        [ -e $B/lpjmlfit_config.cjson ] || cp $BASE/lpjmlfit_config.cjson $B/ || true
        TREE=$TREE CO2=$CO2 bash $LF/scenario_run.sh $G $B $s $g"
    done
  done ;;
*) sed -n 2,12p "$0"; exit 2 ;;
esac
