#!/bin/bash
# Build the POEM-1.2 (20261013, 6 layers) copy that carries the learned-land-emulator bridge
# (esm_land_emulator ADR 0347). Usage: sbatch compile_poem_landemu.sh [POEM_ROOT]
# A full build takes ~19 min; after a source change the same command rebuilds incrementally (~20 s).
#SBATCH --account=waldspektrum
#SBATCH --partition=priority
#SBATCH --qos=priority
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=03:00:00
#SBATCH --job-name=poem-landemu-compile
#SBATCH --output=/p/projects/open/Jamir/poem_landemu/compile.%j.log
set -e
ROOT=${1:-/p/projects/open/Jamir/poem_landemu/POEM-1.2_20261013_6-layers_landemu}
source /etc/profile.d/00-modulepath.sh 2>/dev/null || true
source /etc/profile.d/modules.sh
source /p/projects/poem/data/tuning-1.2/POEM_PROGRAM/poem-integration/compile/POEM_LOADER.sh --scenario=LOAD_ALL --poem-root=$ROOT
export LANDEMU_PYTHON=/home/jamirp/.conda/envs/py311_new
# a directory holding ONLY libpython (linking with the environment's lib/ on the search path picks
# up its shared netCDF/HDF5 instead of POEM's static ones -> abort in NC4_open; ADR 0347)
export LANDEMU_PYLIB=/p/projects/open/Jamir/poem_landemu/pylib
mkdir -p $LANDEMU_PYLIB
ln -sf $LANDEMU_PYTHON/lib/libpython3.11.so.1.0 $LANDEMU_PYLIB/libpython3.11.so.1.0
ln -sf $LANDEMU_PYTHON/lib/libpython3.11.so.1.0 $LANDEMU_PYLIB/libpython3.11.so
cd $ROOT/exp
date
./POEM_compile.csh --type MOM_ATLANTES_LPJ_CM2 --platform pik-hpc2024-ifort 2>&1 | tee compile.log | tail -40
date
ls -la $ROOT/exec/*/MOM_ATLANTES_LPJ_CM2/
