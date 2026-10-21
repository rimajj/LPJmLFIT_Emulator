#!/bin/bash
# run_design_sensitivity.sh -- submit every arm of ADR 0359 (design-choice sensitivity of the learning set-up).
#   map arms        one job per arm: fit the level map for the 5 held-out climate models, then every structure score
#                   (scripts/score_yearly_map_variant.sh); suffix _dc_<ARM>_fx
#   departure arms  the same with --state dep; suffix _dc_<ARM>_statedep_fx
#   daily screen    one GPU job per arm and seed: scripts/f2_train.py --train-only as the release members (arm D),
#                   tag DC_<ARM>_s<seed>; read with scripts/summarise_design_sensitivity.py
# Usage: scripts/run_design_sensitivity.sh [map|dep|daily|all] [--dry-run]
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
WHAT="${1:-all}"; DRY="${2:-}"
PY=/home/jamirp/.conda/envs/py311_new/bin/python
GCMS="gfdl-esm4 ipsl-cm6a-lr mpi-esm1-2-hr mri-esm2-0 ukesm1-0-ll"

submit() {  # name ncpus time partition qos gres body
  local name=$1 ncpu=$2 time=$3 part=$4 qos=$5 gres=$6 body=$7 jcf="logs/$1.jcf"
  {
    echo "#!/bin/bash"
    echo "#SBATCH --job-name=$name"
    echo "#SBATCH --account=waldspektrum"
    echo "#SBATCH --partition=$part"
    echo "#SBATCH --qos=$qos"
    [ -n "$gres" ] && echo "#SBATCH --gres=$gres"
    echo "#SBATCH --nodes=1"
    echo "#SBATCH --ntasks=1"
    echo "#SBATCH --cpus-per-task=$ncpu"
    echo "#SBATCH --time=$time"
    echo "#SBATCH --output=$REPO/logs/$name.%j.out"
    echo "#SBATCH --error=$REPO/logs/$name.%j.out"
    echo "cd $REPO"
    echo "export POLARS_MAX_THREADS=$ncpu OMP_NUM_THREADS=$ncpu"
    echo "echo \"=== $name on \$(hostname) at \$(date) ===\""
    echo "set -e"
    echo "$body"
    echo "echo \"=== JOB DONE tag=$name exit=\$? ===\""
  } > "$jcf"
  if [ "$DRY" = "--dry-run" ]; then echo "would submit $jcf"; else sbatch "$jcf"; fi
}

map_arm() {  # ARM state "fit args"
  local arm=$1 state=$2 args=$3 sfx
  if [ "$state" = "dep" ]; then sfx="_dc_${arm}_statedep_fx"; else sfx="_dc_${arm}_fx"; fi
  local body=""
  for g in $GCMS; do
    body+="$PY scripts/explore_panel_yearly_drift.py fit --g $g --state $state $args --suffix $sfx"$'\n'
  done
  body+="scripts/score_yearly_map_variant.sh $sfx --state $state $args --suffix $sfx"
  submit "dc-$arm" 32 06:00:00 standard short "" "$body"
}

if [ "$WHAT" = map ] || [ "$WHAT" = all ]; then
  map_arm L15 none "--lgb num_leaves=15"
  map_arm L63 none "--lgb num_leaves=63"
  map_arm R200 none "--rounds 200"
  map_arm R800 none "--rounds 800"
  map_arm LR025 none "--lgb learning_rate=0.025"
  map_arm LR10 none "--lgb learning_rate=0.1"
  map_arm F10 none "--lgb feature_fraction=1.0,bagging_fraction=1.0"
  map_arm MD100 none "--lgb min_data_in_leaf=100"
  map_arm W10 none "--clim-window 10"
  map_arm W20 none "--clim-window 20"
  map_arm W50 none "--clim-window 50"
  map_arm S2 none "--train-step 2"
  map_arm S8 none "--train-step 8"
  map_arm NOS0 none "--drop-feats s0,memoff"
  map_arm NODC none "--drop-feats dclim"
  map_arm NOANC none "--drop-feats anc"
fi
if [ "$WHAT" = dep ] || [ "$WHAT" = all ]; then
  map_arm DL15 dep "--dep-lgb num_leaves=15"
  map_arm DL63 dep "--dep-lgb num_leaves=63"
  map_arm DR200 dep "--dep-rounds 200"
  map_arm DR800 dep "--dep-rounds 800"
  map_arm DZ15 dep "--z-window 15"
  map_arm DZ20 dep "--z-window 20"
fi
if [ "$WHAT" = daily ] || [ "$WHAT" = all ]; then
  LEGS="ctl_obs,mpi-esm1-2-hr_ssp126,mpi-esm1-2-hr_ssp370,mpi-esm1-2-hr_ssp585,gfdl-esm4_ssp126_daily"
  LEGS+=",gfdl-esm4_ssp370_daily,gfdl-esm4_ssp585_daily,mri-esm2-0_ssp126_daily,mri-esm2-0_ssp370_daily"
  LEGS+=",mri-esm2-0_ssp585_daily,ipsl-cm6a-lr_ssp126_daily,ipsl-cm6a-lr_ssp370_daily,ipsl-cm6a-lr_ssp585_daily"
  LEGS+=",ukesm1-0-ll_ssp370"
  declare -A A=(
    [BASE]="" [H128]="--hidden 128" [H512]="--hidden 512" [L2]="--layers 2" [L4]="--layers 4"
    [RELU]="--act relu" [GELU]="--act gelu" [TANH]="--act tanh" [E5]="--epochs 5" [E20]="--epochs 20"
    [LR1]="--lr 1e-3" [LR10]="--lr 1e-2" [B4K]="--batch 4096" [B64K]="--batch 65536"
    [NOWIN]="--drop-inputs huss,tas10,tas30,rsds30,pr30,pr90,pr365"
    [NOPWIN]="--drop-inputs huss,pr30,pr90,pr365" [NOTWIN]="--drop-inputs huss,tas10,tas30,rsds30")
  for arm in "${!A[@]}"; do
    for s in 0 1 2; do
      # the release members' settings (f2_chain_new_legs.COMMON) first; the arm's flag overrides (argparse: last wins)
      body="$PY scripts/f2_train.py --tag DC_${arm}_s$s --seed $s --train-only --train-legs $LEGS --test-legs none"
      body+=" --hidden 256 --layers 3 --npp-head ra --drop-inputs huss ${A[$arm]}"
      submit "dc-daily-$arm-s$s" 32 01:30:00 gpu gpushort gpu:1 "$body"
    done
  done
fi
