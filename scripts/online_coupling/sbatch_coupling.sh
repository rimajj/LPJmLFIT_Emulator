#!/bin/bash
# Submit an online-coupling Julia script to SLURM (line O). Usage:
#   sbatch_coupling.sh <tag> <script.jl>
# Logs to /p/tmp/jamirp/esm_online_coupling/logs/<tag>.<jobid>.out (shared /p — readable from any session).
#
# Env knobs: TIME (default 00:40:00) · QOS (default short) · PASS (space-separated NAME=VALUE pairs
# exported into the job, e.g. PASS="FLOW=rre DAYS=30").
#
# Uses Julia 1.10.10, NOT 1.10.0: on 1.10.0 Pkg's extension resolution throws
# `KeyError: key "KernelAbstractions" not found` while precompiling RingGrids/SpeedyWeather/Terrarium
# (and `KeyError: "Dates"` from Pkg.status()). 1.10.10 precompiles all 272 deps cleanly.
set -eu
TAG="${1:?usage: sbatch_coupling.sh <tag> <script.jl>}"
SCRIPT="${2:?usage: sbatch_coupling.sh <tag> <script.jl>}"
PROJ=/p/tmp/jamirp/esm_online_coupling
TIME="${TIME:-00:40:00}"
QOS="${QOS:-short}"
PASS="${PASS:-}"
mkdir -p "$PROJ/logs"

EXPORTS=""
for kv in $PASS; do EXPORTS="$EXPORTS
    export $kv"; done

JOB=$(sbatch --parsable \
  --job-name="$TAG" \
  --account=waldspektrum \
  --partition=standard \
  --qos="$QOS" \
  --nodes=1 --ntasks=1 --cpus-per-task=8 \
  --time="$TIME" \
  --output="$PROJ/logs/${TAG}.%j.out" \
  --wrap "set -eu
    export JULIA_DEPOT_PATH=\$HOME/.julia
    export JULIA_NUM_THREADS=8$EXPORTS
    echo \"=== host=\$(hostname) tag=$TAG script=$SCRIPT ${PASS} ===\"
    /p/system/packages_rhel9/tools/julia/1.10.10/bin/julia --project=$PROJ '$SCRIPT'
    echo \"=== JOB DONE tag=$TAG exit=\$? ===\"")
echo "submitted $TAG as job $JOB"
echo "log: $PROJ/logs/${TAG}.${JOB}.out"
