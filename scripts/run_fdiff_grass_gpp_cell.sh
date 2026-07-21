#!/bin/bash
# =============================================================================
# run_fdiff_grass_gpp_cell.sh  —  single-cell DAILY re-run of the Historical
# 2000-2019 transient (restart_1999.lpj) that ADDITIONALLY emits the NEW
# grass-only daily GPP/NPP outputs (d_grass_gpp / d_grass_npp, conf.h ids
# 419/420 — added to the LPJmL-FIT C source this session) so the F_diff grass
# NPP LEVEL gap can be decomposed against the C's OWN daily grass GPP (which no
# stock LPJmL output provided — a per-PFT daily GPP output had to be built).
# Same base config as run_fdiff_validation_cell.sh (structure + light context);
# only the output list gains the two grass daily fields + annual pft_npp.
#
# WHY a fresh re-run (not the existing 186 GB global daily set):
#  - The 186 GB set has NO canopy-structure/light fields (only water + carbon
#    fluxes). F_diff consumes canopy LAI/FPC/FAPAR as its S->F boundary; without
#    the C run's ACTUAL daily light absorption a GPP comparison confounds
#    "different physics" with "different canopy" (phenology is the dominant
#    confound — RANK 1). This run adds daily FAPAR + NV_LAI so the comparison is
#    apples-to-apples (see docs/phase3_fdiff_cbinary_validation.md).
#  - daily FAPAR IS filled for NATURAL vegetation (src/lpj/daily_natural.c:219,
#    pft->fapar from src/tree/albedo_tree.c:75) and FAPAR is NOT annual-capped
#    (src/lpj/getmintimestep.c) -> requesting "daily" is accepted.
#  - The dedicated slots D_LAI/D_PHEN/D_CLEAF are crop-only (never filled for a
#    forest cell -> zeros); NV_LAI/PFT_LAI are the daily forest LAI outputs, and
#    FPC_STAND/LAI_STAND update annually.
#
# PROTOTYPE CELL: Hainich (DE-Hai) temperate broadleaf beech = GLOBAL orderA grid
# 0-based index 42490 (lat 51.25, lon 10.25). NB: 28008 is Hainich only in the
# repo default single-site grid; in the global grid 28008 = Sonoran desert.
#
# Base config = the EXACT production transient (sections I & II byte-identical to
# scripts/run_daily_subset.sh, which reproduced the ground-truth trajectory), so
# this single-cell re-run reproduces the same physics/vegetation state; only the
# output list (IV) and run window (V) differ.
#
# Usage (defaults target Hainich, full 2000-2019, single task):
#   SUBMIT=yes bash scripts/run_fdiff_validation_cell.sh
#   CELL=42490 FIRSTYEAR=2000 LASTYEAR=2019 SUBMIT=yes bash scripts/run_fdiff_validation_cell.sh
# Set SUBMIT=no to only generate + lpjcheck-validate.
# =============================================================================
set -euo pipefail

CELL="${CELL:-42490}"                 # Hainich (global orderA grid, 0-based)
FIRSTYEAR="${FIRSTYEAR:-2000}"
LASTYEAR="${LASTYEAR:-2019}"
NTASKS="${NTASKS:-1}"                  # single cell
RUNTAG="${RUNTAG:-grassgpp}"
SUBMIT="${SUBMIT:-no}"
RANDOM_SEED="${RANDOM_SEED:-1}"       # seed1 = the reproduced Historical trajectory
TIME="${TIME:-00:20:00}"
EXCLUSIVE="${EXCLUSIVE:-no}"

LPJROOT=/home/jamirp/lpjml56fit
GLOBAL=/p/projects/waldspektrum/priesner/clustering/global
RESTART_1999="${GLOBAL}/Historical/ground_truth/model_output/transient_2000_2019_npatch25_nspinup1000_nspinyear30_random_seed1/restart/restart_1999.lpj"
RUN_ROOT=/p/tmp/jamirp/esm_land_daily

runname="daily_${FIRSTYEAR}_${LASTYEAR}_${RUNTAG}_c${CELL}_seed${RANDOM_SEED}"
outpath="${RUN_ROOT}/${runname}"
out_script="${outpath}/scripts_for_running_the_model"
mkdir -p "${outpath}/output" "${outpath}/restart" "${out_script}"

echo "== run: ${runname}"
echo "   cell ${CELL} (single), years ${FIRSTYEAR}-${LASTYEAR}, ntasks ${NTASKS}"
echo "   restart: ${RESTART_1999}"
echo "   outpath: ${outpath}"

[ -f "${RESTART_1999}" ] || { echo "FATAL: restart_1999.lpj not found"; exit 1; }

# ---- input file (identical global Historical obsclim inputs) -----------------
cat > "${out_script}/input.js" <<EOF
"inpath" : "${GLOBAL}/",
"soilmap" : [null,"clay", "silty clay", "sandy clay", "clay loam", "silty clay loam",
             "sandy clay loam", "loam", "silt loam", "sandy loam", "silt",
             "loamy sand", "sand", "rock and ice"],
"input" :
{
  "soil" :      { "fmt" : "raw", "name" : "soil_code_test.soil.bin"},
  "coord" :     { "fmt" : "clm", "name" : "soil_code_test.grid.clm"},
  "temp" :      { "fmt" : "clm", "name" : "temperature_test.clm"},
  "soildepth" : { "fmt" : "clm", "name" : "soil_depth_test.clm"},
  "prec" :      { "fmt" : "clm", "name" : "precipitation_test.clm"},
  "lwnet" :     { "fmt" : "clm", "name" : "long_wave_radiation_test.clm"},
  "swdown" :    { "fmt" : "clm", "name" : "short_wave_radiation_test.clm"},
  "humid" :     { "fmt" : "clm", "name" : "humid_test.clm"},
  "co2" :       { "fmt" : "txt", "name" : "/p/projects/lpjml/inputs/co2/global/TRENDY/v12/global_co2_ann_1700_2022.txt"},
},
EOF

# ---- lpjml config (sections I & II verbatim from the production transient) ---
cat > "${out_script}/lpjml.js" <<EOF
/* F_diff C-binary validation single-cell DAILY re-run (run_fdiff_validation_cell.sh).
   Sections I & II are byte-for-byte the production transient config; only IV
   (outputs: + daily FAPAR/NV_LAI + annual FPC_STAND/LAI_STAND) and V (run window,
   single cell) differ. Invoke with -DFROM_RESTART. */

{   /* LPJmL configuration in JSON format */

/*==== I. Simulation description and type section ====*/
  "sim_name" : "LPJmL-FIT F_diff validation cell",
  "sim_id"   : "lpjml",
  "version"  : "5.6",
  "individual" : true,
  "inheritance" : true,
  "inherit_startyear" : 0,
  "npatch" : 25,
  "cut_year": -9999,
  "tree_year": -1,
  "isD95max" : true,
  "random_prec" : false,
  "random_seed" : ${RANDOM_SEED},
  "radiation" : "radiation",
  "fire" : "fire",
  "fire_on_grassland" : false,
  "fdi" : "nesterov",
  "relative_humidity": false,
  "firewood" : false,
  "new_phenology" : true,
  "new_trf" : false,
  "river_routing" : false,
  "extflow" : false,
  "no_grass" : false,
  "logging" : false,
  "percolation_heattransfer" : true,
  "pft_est" : false,
  "with_days" : true,
  "permafrost" : true,
  "johansen" : true,
  "soilpar_option" : "no_fixed_soilpar",
  "with_nitrogen" : "no",
  "store_climate" : true,
  "const_climate" : false,
  "shuffle_climate" : true,
  "const_deposition" : false,
  "depos_year_const" : 1901,
  "fix_climate" : false,
  "fix_landuse" : false,
  "root_model" : "logistic",
  "new_seed" : false,
  "population" : false,
  "landuse" : "no",
  "landuse_year_const" : 2000,
  "reservoir" : true,
  "wateruse" : "no",
  "equilsoil" : false,
  "istrack" : false,
  "prescribe_burntarea" : false,
  "prescribe_landcover" : "no_landcover",
  "sowing_date_option" : "fixed_sdate",
  "sdate_fixyear" : 1970,
  "intercrop" : false,
  "residue_treatment" : "fixed_residue_remove",
  "residues_fire" : false,
  "irrigation" : "lim",
  "laimax_interpolate" : "laimax_par",
  "tillage_type" : "all",
  "till_startyear" : 1850,
  "black_fallow" : false,
  "pft_residue" : "temperate cereals",
  "no_ndeposition" : false,
  "rw_manage" : false,
  "laimax" : 5,
  "fertilizer_input" : "yes",
  "manure_input" : true,
  "fix_fertilization" : false,
  "others_to_crop" : true,
  "grazing" : "default",
  "grazing_others" : "default",
  "cft_temp" : "temperate cereals",
  "cft_tropic" : "maize",
  "grassonly" : false,
  "istimber" : true,
  "grassland_fixed_pft" : false,
  "grass_harvest_options" : false,
  "mowing_days" : [152, 335],
  "crop_resp_fix" : false,
  "crop_phu_option" : "new",
  "cropsheatfrost" : false,
  "double_harvest" : true,
  "ma_bnf" : true,

/*==== II. Input parameter section ====*/
#include "param_lpjmlfit.js"

/*==== III. Input data section ====*/
#include "${out_script}/input.js"

/*==== IV. Output data section ====*/
  "grid_scaled" : false,
  "output_metafile" : true,
  "float_grid" : false,
  "crop_index" : "temperate cereals",
  "crop_irrigation" : false,

  "output" :
  [
    { "id" : "grid",       "file" : { "fmt" : "cdf", "name" : "output/grid.nc" }},
    { "id" : "globalflux", "file" : { "fmt" : "txt", "name" : "output/globalflux_${FIRSTYEAR}_${LASTYEAR}.csv" }},
    /* --- daily CARBON fluxes (validation targets) --- */
    { "id" : "gpp",      "file" : { "fmt" : "cdf", "name" : "output/d_gpp.nc",      "timestep" : "daily" }},
    { "id" : "npp",      "file" : { "fmt" : "cdf", "name" : "output/d_npp.nc",      "timestep" : "daily" }},
    /* --- NEW: daily GRASS-only GPP/NPP (natural PFTs) — the F_diff grass level-gap validation target --- */
    { "id" : "d_grass_gpp", "file" : { "fmt" : "cdf", "name" : "output/d_grass_gpp.nc", "timestep" : "daily" }},
    { "id" : "d_grass_npp", "file" : { "fmt" : "cdf", "name" : "output/d_grass_npp.nc", "timestep" : "daily" }},
    /* --- annual per-PFT NPP (grass ground-truth context, per natural PFT) --- */
    { "id" : "pft_npp",  "file" : { "fmt" : "cdf", "name" : "output/a_pft_npp.nc",  "timestep" : "annual" }},
    /* --- daily LIGHT + canopy STRUCTURE (the S->F boundary F_diff needs) --- */
    { "id" : "fapar",    "file" : { "fmt" : "cdf", "name" : "output/d_fapar.nc",    "timestep" : "daily" }},
    { "id" : "nv_lai",   "file" : { "fmt" : "cdf", "name" : "output/d_nv_lai.nc",   "timestep" : "daily" }},
    /* --- daily WATER-balance terms (validation targets, mm/day) --- */
    { "id" : "transp",   "file" : { "fmt" : "cdf", "name" : "output/d_transp.nc",   "timestep" : "daily" }},
    { "id" : "evap",     "file" : { "fmt" : "cdf", "name" : "output/d_evap.nc",     "timestep" : "daily" }},
    { "id" : "interc",   "file" : { "fmt" : "cdf", "name" : "output/d_interc.nc",   "timestep" : "daily" }},
    { "id" : "runoff",   "file" : { "fmt" : "cdf", "name" : "output/d_runoff.nc",   "timestep" : "daily" }},
    { "id" : "pet",      "file" : { "fmt" : "cdf", "name" : "output/d_pet.nc",      "timestep" : "daily" }},
    { "id" : "prec",     "file" : { "fmt" : "cdf", "name" : "output/d_prec.nc",     "timestep" : "daily" }},
    /* --- daily soil-water STATE (for the soil-water trajectory comparison) --- */
    { "id" : "swe",      "file" : { "fmt" : "cdf", "name" : "output/d_swe.nc",      "timestep" : "daily" }},
    { "id" : "swc",      "file" : { "fmt" : "cdf", "name" : "output/d_swc.nc",      "timestep" : "daily" }},
    { "id" : "rootmoist","file" : { "fmt" : "cdf", "name" : "output/d_rootmoist.nc","timestep" : "daily" }},
    /* --- ANNUAL canopy structure + soil capacity (context) --- */
    { "id" : "fpc",         "file" : { "fmt" : "cdf", "name" : "output/a_fpc.nc",         "timestep" : "annual" }},
    { "id" : "fpc_stand",   "file" : { "fmt" : "cdf", "name" : "output/a_fpc_stand.nc",   "timestep" : "annual" }},
    { "id" : "lai_stand",   "file" : { "fmt" : "cdf", "name" : "output/a_lai_stand.nc",   "timestep" : "annual" }},
    { "id" : "vegc",        "file" : { "fmt" : "cdf", "name" : "output/a_vegc.nc",        "timestep" : "annual" }},
    { "id" : "whc_nat",     "file" : { "fmt" : "cdf", "name" : "output/whc_nat.nc" }},
  ],

/*==== V. Run settings section ====*/
  "startgrid" : ${CELL},
  "endgrid" : ${CELL},

  "nspinup" : 0,
  "nspinyear" : 30,
  "firstyear": ${FIRSTYEAR},
  "lastyear" : ${LASTYEAR},
  "outputyear": ${FIRSTYEAR},
  "restart" :  true,
  "restart_filename" : "${RESTART_1999}",
  "write_restart" : false,
  "write_restart_filename" : "restart/restart_${LASTYEAR}.lpj",
  "restart_year": ${LASTYEAR}
}
EOF

# ---- slurm job ---------------------------------------------------------------
excl_directive=""
[ "${EXCLUSIVE}" = "yes" ] && excl_directive="#SBATCH --exclusive"
cat > "${out_script}/slurm.jcf" <<EOF
#!/bin/bash
#SBATCH --ntasks=${NTASKS}
#SBATCH --qos=short
${excl_directive}
#SBATCH -J FIT_fdiffval
#SBATCH --time=${TIME}
#SBATCH -o ${outpath}/lpjml.%j.out
#SBATCH -e ${outpath}/lpjml.%j.err

source /etc/profile.d/00-modulepath.sh 2>/dev/null || true
source /etc/profile.d/modules.sh 2>/dev/null || true
module purge 2>/dev/null || true
module load intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 netcdf-c curl/8.4.0 expat/2.5.0

export LPJROOT=${LPJROOT}
export LPJOUTPATH=${outpath}
export LPJRESTARTPATH=${outpath}
ulimit -c unlimited

mpirun ${LPJROOT}/bin/lpjml -DFROM_RESTART ${out_script}/lpjml.js
exit \$?
EOF

echo "== generated config + input + slurm in ${out_script}"

# ---- pre-flight: lpjcheck validates config + inputs WITHOUT running ----------
echo "== lpjcheck pre-flight"
source /etc/profile.d/00-modulepath.sh 2>/dev/null || true
source /etc/profile.d/modules.sh 2>/dev/null || true
module purge 2>/dev/null || true
module load intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 netcdf-c curl/8.4.0 expat/2.5.0 || true
export LPJROOT=${LPJROOT} LPJOUTPATH="${outpath}" LPJRESTARTPATH="${outpath}"
if ( cd "${outpath}" && "${LPJROOT}/bin/lpjcheck" -DFROM_RESTART "${out_script}/lpjml.js" ); then
  echo "== lpjcheck: PASS"
else
  echo "== lpjcheck: FAIL — not submitting"; exit 2
fi

if [ "${SUBMIT}" = "yes" ]; then
  jid=$(sbatch "${out_script}/slurm.jcf" | awk '{print $NF}')
  echo "== submitted SLURM job ${jid}"
  echo "${jid}" > "${outpath}/.jobid"
else
  echo "== SUBMIT=no — generated + validated only. To submit:"
  echo "   sbatch ${out_script}/slurm.jcf"
fi
