#!/bin/bash
#SBATCH --job-name=S-D4regrid
#SBATCH --account=waldspektrum
#SBATCH --partition=standard
#SBATCH --qos=short
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=06:00:00
#SBATCH --output=/p/projects/open/Jamir/wt-S/logs/S-D4regrid.%j.out
#
# trackd_regrid_forcing.sh — Track D4 (EXECUTION_PLAN.md rev. 2, ADR 0096): put the ISIMIP3b climate of five
# climate models x three scenarios into the orderA cell order the global restart files are written in.
#
# This is the SAME permutation that produced the MPI-ESM1-2-HR ssp126/ssp370 forcing the global ground truth ran
# on (~/scripts/clustering/global/bash_run_model/regrid_ssp370_to_orderA.sh): LPJmL's own `regridclm` from grid.bin
# ("order B", the ISIMIP order) to soil_code_test.grid.clm ("orderA"), lossless (identical cell set), huss as
# float (-size4), the other four as the source's int16. Source: /p/projects/lpjml/input/scenarios/ISIMIP3bv2.
#
# GATE FIRST: re-derive the existing MPI-ESM1-2-HR ssp370 tas orderA file and require it byte-identical with the
# one the ground truth used. Then convert every missing (model, scenario, variable); the two existing MPI sets are
# linked, not regenerated.
#
# Output: /p/tmp/jamirp/trackD/forcing/<scen>/<var>_<gcm-lower>_<scen>_2015-2100_orderA.clm
set -euo pipefail
source /etc/profile.d/00-modulepath.sh; source /etc/profile.d/modules.sh
module purge
module load intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 netcdf-c curl/8.4.0 expat/2.5.0
export LD_LIBRARY_PATH=/p/system/packages_rhel9/libraries/json-c/0.13.1/lib:${LD_LIBRARY_PATH:-}
export PATH=/p/projects/biodiversity/bloh/git/master_bsq/bin:$PATH

GRID_OLD=/p/projects/biodiversity/input_VERSION2/grid.bin
GRID_NEW=/p/projects/waldspektrum/priesner/clustering/global/soil_code_test.grid.clm
SRC=/p/projects/lpjml/input/scenarios/ISIMIP3bv2
GT=/p/projects/waldspektrum/priesner/clustering/global
OUT=/p/tmp/jamirp/trackD/forcing
GCMS="GFDL-ESM4 IPSL-CM6A-LR MPI-ESM1-2-HR MRI-ESM2-0 UKESM1-0-LL"
SCENS="ssp126 ssp370 ssp585"
VARS="tas pr lwnet rsds huss"
mkdir -p "$OUT"/{ssp126,ssp370,ssp585} "$OUT/_gate"

flag() { [ "$1" = huss ] && echo "-size4" || echo ""; }

echo "=== GATE: re-derive MPI-ESM1-2-HR ssp370 tas orderA ==="
regridclm "$GRID_OLD" "$GRID_NEW" "$SRC/ssp370/MPI-ESM1-2-HR/tas_mpi-esm1-2-hr_ssp370_2015-2100.clm" \
  "$OUT/_gate/tas_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"
if cmp -s "$OUT/_gate/tas_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm" "$GT/ssp370/tas_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"; then
  echo "GATE PASS: byte-identical to the ground-truth forcing"
  rm -f "$OUT/_gate/tas_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"
else
  echo "GATE FAIL: differs from the ground-truth forcing — stopping"; exit 3
fi

jobs_file=$(mktemp)
for sc in $SCENS; do for g in $GCMS; do
  gl=$(echo "$g" | tr 'A-Z' 'a-z')
  for v in $VARS; do
    dst="$OUT/$sc/${v}_${gl}_${sc}_2015-2100_orderA.clm"
    existing="$GT/$sc/${v}_${gl}_${sc}_2015-2100_orderA.clm"
    if [ -f "$existing" ]; then ln -sfn "$existing" "$dst"; continue; fi
    [ -s "$dst" ] && continue
    echo "regridclm $(flag $v) $GRID_OLD $GRID_NEW $SRC/$sc/$g/${v}_${gl}_${sc}_2015-2100.clm $dst.part && mv $dst.part $dst" >> "$jobs_file"
  done
done; done
echo "=== converting $(wc -l < "$jobs_file") files, 8 at a time ==="
xargs -P 8 -I{} bash -c '{}' < "$jobs_file"
rm -f "$jobs_file"

echo "=== verify: every (model, scenario, variable) present, headers sane ==="
fail=0
for sc in $SCENS; do for g in $GCMS; do gl=$(echo "$g" | tr 'A-Z' 'a-z'); for v in $VARS; do
  f="$OUT/$sc/${v}_${gl}_${sc}_2015-2100_orderA.clm"
  if [ ! -s "$f" ]; then echo "MISSING $f"; fail=1; continue; fi
  src="$SRC/$sc/$g/${v}_${gl}_${sc}_2015-2100.clm"
  [ "$(stat -L -c %s "$f")" = "$(stat -L -c %s "$src")" ] || { echo "SIZE MISMATCH $f"; fail=1; }
done; done; done
[ $fail = 0 ] && echo "ALL FORCING PRESENT" || { echo "FORCING INCOMPLETE"; exit 4; }
echo "=== JOB DONE ==="
