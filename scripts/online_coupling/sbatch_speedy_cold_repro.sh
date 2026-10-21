#!/bin/bash
# Submit scripts/online_coupling/speedy_cold_bias_repro.jl (SpeedyWeather alone, no emulator) on ONE core.
#   sbatch_speedy_cold_repro.sh <tag> <julia project> [slab|prescribed] [years=3]
# Projects: /p/tmp/jamirp/esm_online_coupling_sw023 (v0.23.0), /p/tmp/jamirp/speedy_main_env (main adf0d61),
#           /p/tmp/jamirp/speedy_coldfix_env (adf0d61 + the cold-bias fix branch, worktree speedy_coldfix_src).
# Env knobs forwarded if set: LW=analytic|fourband, LANDREF=<land reference csv>, PROFREF=<profile reference csv>, LWKW / CLOUDKW / CONVKW="name=value,...", T0=speedy, SIGMA=speedy. Log -> logs/<tag>.<jobid>.out.
set -eu
TAG="${1:?usage: sbatch_speedy_cold_repro.sh <tag> <project> [slab|prescribed] [years]}"
PROJ="${2:?julia project}"
OCN="${3:-slab}"
YRS="${4:-3}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
EXP=""
for v in LW LANDREF PROFREF WINTERREF LWKW SWKW CLOUDKW DRAGKW VDKW CONVKW T0 SIGMA CLEARSKY DAYS; do
  [ -n "${!v:-}" ] && EXP="$EXP export $v='${!v}';"
done
JOB=$(sbatch --parsable --job-name="$TAG" --account=waldspektrum --partition=${PARTITION:-priority} --qos=${QOS:-priority} \
  --nodes=1 --ntasks=1 --cpus-per-task=1 --time="${RUNTIME:-02:00:00}" --output="$REPO/logs/${TAG}.%j.out" \
  --wrap "set -eu; $EXP
    export JULIA_DEPOT_PATH=\$HOME/.julia JULIA_NUM_THREADS=1
    echo \"host=\$(hostname) project=$PROJ ocean=$OCN years=$YRS $EXP\"
    /p/system/packages_rhel9/tools/julia/1.10.10/bin/julia --project=$PROJ \
      '$REPO/scripts/online_coupling/speedy_cold_bias_repro.jl' $OCN $YRS
    echo \"=== JOB DONE exit=\$? ===\"")
echo "submitted $TAG as job $JOB -> $REPO/logs/${TAG}.${JOB}.out"
