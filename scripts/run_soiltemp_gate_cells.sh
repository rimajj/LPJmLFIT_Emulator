#!/bin/bash
# =============================================================================
# run_soiltemp_gate_cells.sh — single-cell C re-runs that add DAILY layer-1 SOIL
# TEMPERATURE, the oracle for item (c2) of line M's photosynthesis shortlist.
#
# WHY THIS EXISTS (line M, rung 3; `residual-diagnosis` §17). The C forces the GSI
# water-phenology filter fully OPEN while the soil is cold:
#
#     phenology_gsi.c:67   if(soil->temp[0] < 10) pft->phen_gsi.wscal = 1;
#
# F_diff's `rollout_daily_canopy` passes AIR temperature for that argument
# (`fdiff.jl:2220`, `f.temp` in the `soiltemp` slot), and soil temperature lags air
# substantially — so the gate opens in spring and closes in autumn on the wrong
# days, which is precisely the partial-leaf-day regime ADR 0136 showed F's GPP
# error concentrates in. Nothing in the repo has ever measured that lag.
#
# ⚠ The C's own comment on that line says "below 5 degree" while the code tests
# `< 10`. Trust the code (CLAUDE.md §3's comment/code mismatch family).
#
# WHY THIS OUTPUT IS THE RIGHT ORACLE, read at the accumulation line rather than
# from the variable's name (`residual-diagnosis` §3f):
#
#     update_daily.c:200   getoutput(...,SOILTEMP1,...) += patch->soil.temp[0]
#                              * stand->frac/stand->npatch * (1/(1-lakefrac-resfrac))
#
# i.e. it is EXACTLY the `soil->temp[0]` the gate branches on — not a derived or
# depth-averaged proxy — carried as the stand's patch-ensemble MEAN. `getmintimestep.c`
# returns DAILY for everything except VEGC/VEGN/GLOBALFLUX/CFTFRAC/SDATE, so a daily
# request is accepted with no recompile (CLAUDE.md §3: daily output is config-only).
#
# ⚠ ONE BASIS CAVEAT, stated rather than left implicit: the gate is evaluated
# PER PATCH and this output is the patch MEAN, so a day on which patches straddle
# the 10 degC threshold is averaged here. Layer-1 soil temperature is driven by the
# same cell forcing in every patch and differs between them only through the
# canopy/snow state, so the straddling band is narrow — but the measurement is a
# patch-mean gate, and any per-patch claim needs the roster, not this file.
#
# The base config is `run_fdiff_validation_cell.sh`'s (the exact production
# transient), so the vegetation state is the reproduced seed1 trajectory; only the
# output list differs. That wrapper is integrator-owned and has no knob for an extra
# output, so the entry is inserted here and the config is RE-VALIDATED afterwards —
# the wrapper lpjcheck'd it BEFORE the insert, so nothing had yet parsed what will
# actually run.
#
# Usage:
#   SUBMIT=yes bash scripts/run_soiltemp_gate_cells.sh              # all 5 biome cells
#   CELLS="temperate_hainich:42490" SUBMIT=yes bash scripts/run_soiltemp_gate_cells.sh
#   SUBMIT=no  bash scripts/run_soiltemp_gate_cells.sh              # generate + validate only
#
# Then score with:  scripts/diagnose_phenology_soiltemp_gate.py
# =============================================================================
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# ⚠ 2000, not 2010: the only restart available is `restart_1999.lpj` (spin-up end), so a run
# starting at 2010 would drive 2010-2019 forcing from a 1999 state. `lpjcheck` says so
# (WARNING005 "Year of restart file=1999 not equal start year") but does NOT fail on it, so this
# is a silent-wrong-trajectory trap, not a caught one. Score the 2010-2019 window, which is what
# the committed `biome_forcing_*.csv` fixtures cover.
FIRSTYEAR="${FIRSTYEAR:-2000}"
LASTYEAR="${LASTYEAR:-2019}"
RUNTAG="${RUNTAG:-M_soiltemp}"
SUBMIT="${SUBMIT:-yes}"
RUN_ROOT=/p/tmp/jamirp/esm_land_daily

# The canonical cell registry is Python's `extract_biome_forcing.BIOMES` — resolve it
# there rather than re-listing the cells here, so the two can never drift (ADR 0031).
PY=/home/jamirp/.conda/envs/py311_new/bin/python
mapfile -t SPEC < <(CELLS="${CELLS:-}" "${PY}" -c "
import os, sys
sys.path.insert(0, os.path.join('${REPO}', 'scripts'))
from extract_biome_forcing import cells_from_env
for name, cell in cells_from_env():
    print(f'{name} {cell}')
")

echo "== ${#SPEC[@]} cell(s), years ${FIRSTYEAR}-${LASTYEAR}, runtag ${RUNTAG}"

for row in "${SPEC[@]}"; do
  name="${row%% *}"
  cell="${row##* }"
  tag="${RUNTAG}_${name}"
  runname="daily_${FIRSTYEAR}_${LASTYEAR}_${tag}_c${cell}_seed1"
  outpath="${RUN_ROOT}/${runname}"
  scriptdir="${outpath}/scripts_for_running_the_model"

  CELL="${cell}" FIRSTYEAR="${FIRSTYEAR}" LASTYEAR="${LASTYEAR}" RUNTAG="${tag}" \
    SUBMIT=no bash "${REPO}/scripts/run_fdiff_validation_cell.sh" >/dev/null

  "${PY}" - "${scriptdir}" <<'PYEOF'
import sys

scriptdir = sys.argv[1]
cfg = scriptdir + "/lpjml.js"
s = open(cfg).read()

# ⚠ NOT an f-string: `}}` inside one collapses to a single `}`, which silently emits a
# config json-c rejects at the NEXT line ("quoted object property name expected").
entry = ('    { "id" : "soiltemp1", "file" : { "fmt" : "cdf", '
         '"name" : "output/d_soiltemp1.nc", "timestep" : "daily" }},\n')
if '"id" : "soiltemp1"' not in s:
    anchor = '  "output" :\n  [\n'
    assert anchor in s, "output block not found in the generated config"
    s = s.replace(anchor, anchor + entry, 1)
    open(cfg, "w").write(s)
print(f"patched {scriptdir}")
PYEOF

  ( cd "${outpath}" \
    && source /etc/profile.d/00-modulepath.sh && source /etc/profile.d/modules.sh \
    && module purge >/dev/null 2>&1 \
    && module load intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 \
         netcdf-c curl/8.4.0 expat/2.5.0 >/dev/null 2>&1 \
    && "${LPJROOT:-/home/jamirp/lpjml56fit}/bin/lpjcheck" -DFROM_RESTART \
         scripts_for_running_the_model/lpjml.js > "${outpath}/lpjcheck_patched.log" 2>&1 ) \
    || { echo "== FATAL: patched config does not parse — see ${outpath}/lpjcheck_patched.log"; \
         grep -m3 ERROR "${outpath}/lpjcheck_patched.log"; exit 1; }
  echo "== ${name}: patched config validates"

  if [ "${SUBMIT}" = "yes" ]; then
    ( cd "${scriptdir}" && sbatch slurm.jcf )
  else
    echo "== SUBMIT=no — generated + patched only: ${scriptdir}/slurm.jcf"
  fi
done

echo "== done. Poll with: squeue -u \$USER   then score with:"
echo "   ${PY} scripts/diagnose_phenology_soiltemp_gate.py"
