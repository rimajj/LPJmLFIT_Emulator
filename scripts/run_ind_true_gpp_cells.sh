#!/bin/bash
# =============================================================================
# run_ind_true_gpp_cells.sh — single-cell C re-runs that emit the `ind` tree table
# with the TWO diagnostic switches on: every tree (no 5 m cut) and REAL per-stem
# gross GPP.
#
# WHY THIS EXISTS (line M, rung 3; ADR 0129 left a bracket this closes).
# Splitting F_diff's assimilate error into photosynthesis vs respiration needs the
# C's GPP and NPP on the SAME population. Two facts of the stock C prevented that:
#
#   1. the `ind` writer emits only stems above `param.height_min` = 5 m
#      (`fwriteoutput_ind.c`), so every stand aggregate built from `ind` is missing
#      the short trees that the stand-level daily GPP output contains; and
#   2. there is NO per-individual GPP anywhere in LPJmL-FIT's outputs — the `ind`
#      table's `gpp` column is a second copy of NPP, because `daily_natural.c`
#      accumulates `npp` into `pft->agpp`. A per-stem NPP/GPP therefore comes out
#      as exactly 1.0000, which is what it does in the global `ind` parquet.
#
# So `GPP_F/GPP_C` was biased down and `CUE_F/CUE_C` up by the same unknown factor:
# the product (the `bmi` ratio every published number is on) was untouched, but the
# SPLIT was undetermined between 38 % and 78 % photosynthesis.
#
# Both switches are OPT-IN env vars on a rebuilt binary and are INERT unless set —
# gated on a matched single-cell pair (same config, cell and --ntasks, only the
# executable differing): 139 decoded quantities + `globalflux` identical, 0 differ.
# Source change: `patches/lpjmlfit_ind_true_gpp.patch`.
#
# WHAT ONE RUN GIVES YOU, and the identity that validates it:
#   * `Σ over ALL PFT rows of gpp` must reproduce the run's own `d_gpp` output —
#     that is the gate, not a plausibility check, because the two come from
#     different code paths over the same daily `gpp` variable.
#   * `Σ over tree rows above 5 m / Σ over all tree rows` IS the >5 m share of tree
#     GPP — the bracket's unknown, measured instead of bounded.
#   * `Σ npp / Σ gpp` over the >5 m trees is the C's carbon-use efficiency on
#     exactly the population F's roster is built from.
#   * grass rows carry true GPP too, so the tree/grass split needs no
#     `d_grass_gpp` output and no FPC-share assumption (ADR 0053).
#
# ⚠ THIS IS A SINGLE-CELL RE-RUN, so its roster is NOT the global run's (ADR 0041:
# the per-cell seek is decomposition-independent, the evolution is not). Read the
# WITHIN-RUN ratios above, which are internally consistent; do not pair a stem here
# with a stem of the global `ind` parquet. The `gpp_tree` oracle in
# `M_fdiff_oracle_biomes_annual.csv` is itself on the single-cell basis, so the GPP
# side of the comparison is unchanged by this.
#
# Usage (login node; ~10 s per cell, submitted to SLURM):
#   bash scripts/run_ind_true_gpp_cells.sh                 # the 5 biome cells
#   CELLS="temperate_hainich:42490" bash scripts/run_ind_true_gpp_cells.sh
#   RUNTAG=M_indgpp SUBMIT=no bash scripts/run_ind_true_gpp_cells.sh
# Env: CELLS (name:idx,... — defaults to the canonical BIOMES registry), RUNTAG,
#      FIRSTYEAR, LASTYEAR, SUBMIT (default yes).
# Score with: scripts/diagnose_ind_true_gpp.py
# =============================================================================
set -eu

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTAG="${RUNTAG:-M_indgpp}"
FIRSTYEAR="${FIRSTYEAR:-2000}"
LASTYEAR="${LASTYEAR:-2019}"
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

  # Generate + lpjcheck-validate only; the wrapper neither emits an `ind` table nor
  # exports the switches, and it is integrator-owned, so both are inserted here.
  CELL="${cell}" FIRSTYEAR="${FIRSTYEAR}" LASTYEAR="${LASTYEAR}" RUNTAG="${tag}" \
    SUBMIT=no bash "${REPO}/scripts/run_fdiff_validation_cell.sh" >/dev/null

  "${PY}" - "${scriptdir}" "${FIRSTYEAR}" "${LASTYEAR}" <<'PYEOF'
import sys
scriptdir, y0, y1 = sys.argv[1], sys.argv[2], sys.argv[3]

# 1. the annual `ind` tree table (kept ANNUAL — only the daily blocks take a timestep)
# ⚠ NOT an f-string: `}}` inside one collapses to a single `}`, which silently emits a
# config that json-c rejects at the NEXT line ("quoted object property name expected").
cfg = scriptdir + "/lpjml.js"
s = open(cfg).read()
entry = ('    { "id" : "ind",       "file" : { "fmt" : "txt", '
         '"name" : "output/ind_' + y0 + '_' + y1 + '.csv" }},\n')
if '"id" : "ind"' not in s:
    anchor = '  "output" :\n  [\n'
    assert anchor in s, "output block not found in the generated config"
    s = s.replace(anchor, anchor + entry, 1)
    open(cfg, "w").write(s)

# 2. the two switches, immediately before the launch line so they are unmissable
jcf = scriptdir + "/slurm.jcf"
s = open(jcf).read()
if "LPJ_IND_TRUE_GPP" not in s:
    anchor = "\nmpirun "
    assert anchor in s, "launch line not found in the generated job file"
    s = s.replace(
        anchor,
        "\n# the two opt-in `ind` diagnostic switches (inert unless set; ADR 0130)\n"
        "export LPJ_IND_ALL_HEIGHTS=1\nexport LPJ_IND_TRUE_GPP=1\n" + anchor,
        1,
    )
    open(jcf, "w").write(s)
print(f"patched {scriptdir}")
PYEOF

  # RE-VALIDATE. The wrapper lpjcheck'd the config BEFORE the `ind` entry was inserted,
  # so nothing has yet parsed what will actually run. A malformed insert is reported
  # against the FOLLOWING line, which is why this is a gate and not a formality.
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
echo "   ${PY} scripts/diagnose_ind_true_gpp.py"
