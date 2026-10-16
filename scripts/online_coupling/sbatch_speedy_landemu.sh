#!/bin/bash
# Submit scripts/online_coupling/run_speedy_landemu.jl (SpeedyWeather 0.23 + the learned emulator) on ONE core.
#   sbatch_speedy_landemu.sh <tag>        env knobs forwarded: MODE YEARS TRUNC NLAYERS MAXDEG DIURNAL OUT TIME
# Project /p/tmp/jamirp/esm_online_coupling_sw023 (SpeedyWeather 0.23.0, PythonCall; assets warmed on the login node).
# Logs -> logs/<tag>.<jobid>.out in this repo. PythonCall uses the conda env py311_new (no CondaPkg, no network).
set -eu
TAG="${1:?usage: sbatch_speedy_landemu.sh <tag>}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PROJ=/p/tmp/jamirp/esm_online_coupling_sw023
RUNTIME="${TIME:-04:00:00}"
EXP=""
for v in MODE YEARS TRUNC NLAYERS MAXDEG DIURNAL OUT; do
  [ -n "${!v:-}" ] && EXP="$EXP export $v='${!v}';"
done
JOB=$(sbatch --parsable --job-name="$TAG" --account=waldspektrum --partition=priority --qos=priority \
  --nodes=1 --ntasks=1 --cpus-per-task=1 --time="$RUNTIME" --output="$REPO/logs/${TAG}.%j.out" \
  --wrap "set -eu; $EXP
    export JULIA_DEPOT_PATH=\$HOME/.julia JULIA_NUM_THREADS=1
    export JULIA_CONDAPKG_BACKEND=Null JULIA_PYTHONCALL_EXE=/home/jamirp/.conda/envs/py311_new/bin/python
    export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
    echo \"=== host=\$(hostname) tag=$TAG $EXP ===\"
    /p/system/packages_rhel9/tools/julia/1.10.10/bin/julia --project=$PROJ '$REPO/scripts/online_coupling/run_speedy_landemu.jl'
    echo \"=== JOB DONE tag=$TAG exit=\$? ===\"")
echo "submitted $TAG as job $JOB -> $REPO/logs/${TAG}.${JOB}.out"
