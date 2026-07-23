#!/bin/bash
# =============================================================================
# run_daily_subset.sh  —  Phase-1 (P3b) DAILY-output re-run of the Historical
# 2000-2019 transient, restarting from the EXISTING spinup-end restart_1999.lpj
# over a CONTIGUOUS SUBSET of the global 67420-cell grid, to verify WATER
# CLOSURE (and sub-annual carbon).
#
# WHY this shape (all source-verified against /home/jamirp/lpjml56fit):
#  - Daily output = runtime only, no recompile: add "timestep":"daily" INSIDE
#    each output entry's "file" object (readfilename.c:240-250, fscanoutput.c:390).
#  - Restart a contiguous cell SUBSET from the full-grid restart: set integer
#    "startgrid"/"endgrid" (0-based positional row indices into the grid file;
#    NOT "all", NOT lat/lon). The restart read seeks per-cell via an index, so a
#    sub-range works and is MPI-decomposition-independent (openrestart.c:193-203,
#    fwriterestart.c:96-119). REQUIRES the byte-identical grid/soil/input files
#    and matching physics config as the run that WROTE restart_1999.
#  - Water balance is ENFORCED per-cell/year by check_fluxes.c under -DSAFE
#    (in this binary): |balanceW| <= 1.5 mm/yr or the run aborts with
#    INVALID_WATER_BALANCE_ERR. So a clean run == per-cell water closure.
#    For this config it reduces to:
#       prec == transp + evap + interc + runoff + excess_water + d(soilwater)
#    (river_routing:false, landuse:no -> no lake/reservoir/irrig/discharge terms).
#    NOTE: the check is ANNUAL, not daily. swc is FRACTIONAL saturation; convert
#    to mm with whc_nat. swe (snow) is already mm. excess_water (permafrost thaw)
#    has no gridded output -> it is the only unobservable residual term.
#
# Config base: the EXACT production config that read restart_1999 and produced
# the annual ground truth (.../transient_2000_2019.../scripts_for_running_the_model/
# lpjml_2000_2019.js) — sections I & II copied verbatim for restart consistency.
#
# Usage:
#   STARTGRID=45000 ENDGRID=45999 FIRSTYEAR=2000 LASTYEAR=2002 \
#   NTASKS=16 RUNTAG=boreal_val SUBMIT=no bash scripts/run_daily_subset.sh
# Set SUBMIT=yes to sbatch; otherwise it only generates + lpjcheck-validates.
# =============================================================================
set -euo pipefail

# ---- parameters (env-overridable) -------------------------------------------
STARTGRID="${STARTGRID:?set STARTGRID (0-based grid row)}"
ENDGRID="${ENDGRID:?set ENDGRID (>= STARTGRID, <= 67419)}"
SCENARIO="${SCENARIO:-historic}"  # historic (obsclim 2000-2019, restart_1999, VARYING TRENDY CO2)
                                  #  |  ssp370 (MPI-ESM1-2-HR ssp370 2020-2100, restart_2019, CONSTANT 409.63 ppm CO2)
NTASKS="${NTASKS:-16}"
RUNTAG="${RUNTAG:-subset}"
SUBMIT="${SUBMIT:-no}"
RANDOM_SEED="${RANDOM_SEED:-1}"
TIME="${TIME:-00:30:00}"          # SLURM wall limit (full-global needs more, e.g. 02:00:00)
EXCLUSIVE="${EXCLUSIVE:-no}"      # yes -> whole-node allocation (recommended for large jobs)

LPJROOT=/home/jamirp/lpjml56fit
GLOBAL=/p/projects/waldspektrum/priesner/clustering/global
HIST_RESTART_DIR="${GLOBAL}/Historical/ground_truth/model_output/transient_2000_2019_npatch25_nspinup1000_nspinyear30_random_seed1/restart"
RUN_ROOT=/p/tmp/jamirp/esm_land_daily

# ---- scenario dispatch: forcing block, restart, CO2, default years ----------
# Both scenarios keep the SAME physics config (sections I & II) as their production
# transient, so the daily re-run is byte-consistent with the annual `ind` truth.
case "${SCENARIO}" in
  historic)
    RESTART="${HIST_RESTART_DIR}/restart_1999.lpj"     # spinup end -> 2000-2019 re-run
    FIRSTYEAR="${FIRSTYEAR:-2000}"; LASTYEAR="${LASTYEAR:-2019}"
    # obsclim GSWP3-W5E5 inputs (relative to GLOBAL/); VARYING TRENDY v12 CO2
    read -r -d '' FORCING_BLOCK <<EOF || true
  "temp" :      { "fmt" : "clm", "name" : "temperature_test.clm"},
  "prec" :      { "fmt" : "clm", "name" : "precipitation_test.clm"},
  "lwnet" :     { "fmt" : "clm", "name" : "long_wave_radiation_test.clm"},
  "swdown" :    { "fmt" : "clm", "name" : "short_wave_radiation_test.clm"},
  "humid" :     { "fmt" : "clm", "name" : "humid_test.clm"},
  "co2" :       { "fmt" : "txt", "name" : "/p/projects/lpjml/inputs/co2/global/TRENDY/v12/global_co2_ann_1700_2022.txt"},
EOF
    ;;
  ssp370)
    RESTART="${HIST_RESTART_DIR}/restart_2019.lpj"     # historical end -> 2020-2100 SSP370 continuation
    FIRSTYEAR="${FIRSTYEAR:-2020}"; LASTYEAR="${LASTYEAR:-2100}"
    # MPI-ESM1-2-HR ssp370 forcings (relative to GLOBAL/); CONSTANT 409.63 ppm CO2 (2019 value,
    # held flat 2020-2100 -> the with_nitrogen="no" constant-CO2 regime, DEVELOPMENT_PLAN §3).
    # EXACT match to the annual run: .../ssp370/ground_truth/.../transient_2020_2100_npatch25_random_seed1.
    read -r -d '' FORCING_BLOCK <<EOF || true
  "temp" :      { "fmt" : "clm", "name" : "ssp370/tas_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"},
  "prec" :      { "fmt" : "clm", "name" : "ssp370/pr_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"},
  "lwnet" :     { "fmt" : "clm", "name" : "ssp370/lwnet_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"},
  "swdown" :    { "fmt" : "clm", "name" : "ssp370/rsds_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"},
  "humid" :     { "fmt" : "clm", "name" : "ssp370/huss_mpi-esm1-2-hr_ssp370_2015-2100_orderA.clm"},
  "co2" :       { "fmt" : "txt", "name" : "/home/jamirp/scripts/clustering/climclusterpy_package/global_co2_ann_1700_2019_const_2100.txt"},
EOF
    ;;
  *) echo "FATAL: SCENARIO must be 'historic' or 'ssp370' (got '${SCENARIO}')"; exit 1 ;;
esac

runname="daily_${FIRSTYEAR}_${LASTYEAR}_${SCENARIO}_${RUNTAG}_c${STARTGRID}_${ENDGRID}_seed${RANDOM_SEED}"
outpath="${RUN_ROOT}/${runname}"
out_script="${outpath}/scripts_for_running_the_model"
mkdir -p "${outpath}/output" "${out_script}"

echo "== run: ${runname}  (scenario=${SCENARIO})"
echo "   cells [${STARTGRID},${ENDGRID}] (n=$((ENDGRID-STARTGRID+1))), years ${FIRSTYEAR}-${LASTYEAR}, ntasks ${NTASKS}"
echo "   restart: ${RESTART}"
echo "   outpath: ${outpath}"

[ -f "${RESTART}" ] || { echo "FATAL: restart file not found: ${RESTART}"; exit 1; }

# ---- input file (scenario forcing; soil/coord/soildepth identical global grid) --
cat > "${out_script}/input.js" <<EOF
"inpath" : "${GLOBAL}/",
"soilmap" : [null,"clay", "silty clay", "sandy clay", "clay loam", "silty clay loam",
             "sandy clay loam", "loam", "silt loam", "sandy loam", "silt",
             "loamy sand", "sand", "rock and ice"],
"input" :
{
  "soil" :      { "fmt" : "raw", "name" : "soil_code_test.soil.bin"},
  "coord" :     { "fmt" : "clm", "name" : "soil_code_test.grid.clm"},
  "soildepth" : { "fmt" : "clm", "name" : "soil_depth_test.clm"},
${FORCING_BLOCK}
},
EOF

# ---- lpjml config (sections I & II verbatim from the production transient) ---
cat > "${out_script}/lpjml.js" <<EOF
/* P3b DAILY-output subset re-run (generated by run_daily_subset.sh). Sections I
   & II are byte-for-byte the production transient config; only IV (outputs) and
   V (run settings) differ. Invoke with -DFROM_RESTART. */

{   /* LPJmL configuration in JSON format */

/*==== I. Simulation description and type section ====*/
  "sim_name" : "LPJmL-FIT P3b daily subset",
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
    /* daily water-balance terms (mm/day) */
    { "id" : "prec",     "file" : { "fmt" : "cdf", "name" : "output/d_prec.nc",     "timestep" : "daily" }},
    { "id" : "transp",   "file" : { "fmt" : "cdf", "name" : "output/d_transp.nc",   "timestep" : "daily" }},
    { "id" : "evap",     "file" : { "fmt" : "cdf", "name" : "output/d_evap.nc",     "timestep" : "daily" }},
    { "id" : "interc",   "file" : { "fmt" : "cdf", "name" : "output/d_interc.nc",   "timestep" : "daily" }},
    { "id" : "runoff",   "file" : { "fmt" : "cdf", "name" : "output/d_runoff.nc",   "timestep" : "daily" }},
    /* storage terms: swe (snow, mm), swc (fractional/layer), whc_nat (capacity mm), rootmoist (mm) */
    { "id" : "swe",      "file" : { "fmt" : "cdf", "name" : "output/d_swe.nc",      "timestep" : "daily" }},
    { "id" : "swc",      "file" : { "fmt" : "cdf", "name" : "output/d_swc.nc",      "timestep" : "daily" }},
    { "id" : "rootmoist","file" : { "fmt" : "cdf", "name" : "output/d_rootmoist.nc","timestep" : "daily" }},
    { "id" : "whc_nat",  "file" : { "fmt" : "cdf", "name" : "output/whc_nat.nc" }},
    /* diagnostics + sub-annual carbon */
    { "id" : "pet",      "file" : { "fmt" : "cdf", "name" : "output/d_pet.nc",      "timestep" : "daily" }},
    { "id" : "npp",      "file" : { "fmt" : "cdf", "name" : "output/d_npp.nc",      "timestep" : "daily" }},
    { "id" : "gpp",      "file" : { "fmt" : "cdf", "name" : "output/d_gpp.nc",      "timestep" : "daily" }},
    /* ANNUAL stand structure -> the runtime-consistent S features (replaces the lai proxy; ADR 0023/0024).
       lai_stand = FIT stand LAI; fpc_stand = FIT effective stand FPC. Cheap (annual) even at global scale. */
    { "id" : "lai_stand","file" : { "fmt" : "cdf", "name" : "output/lai_stand.nc" }},
    { "id" : "fpc_stand","file" : { "fmt" : "cdf", "name" : "output/fpc_stand.nc" }},
  ],

/*==== V. Run settings section ====*/
  "startgrid" : ${STARTGRID},
  "endgrid" : ${ENDGRID},

  "nspinup" : 0,
  "nspinyear" : 30,
  "firstyear": ${FIRSTYEAR},
  "lastyear" : ${LASTYEAR},
  "outputyear": ${FIRSTYEAR},
  "restart" :  true,
  "restart_filename" : "${RESTART}",
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
#SBATCH -J FIT_p3b_${RUNTAG}
#SBATCH --time=${TIME}
#SBATCH -o ${outpath}/lpjml.%j.out
#SBATCH -e ${outpath}/lpjml.%j.err

# Deterministic module env (purge the login default stack first). json-c/0.13.1
# provides libjson-c.so.4 that this binary is linked against (0.17 -> .so.5 fails);
# openssl/3.6.0 matches the newer production (SSP) recipe. netcdf-c -> 4.9.2.
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
echo "== lpjcheck pre-flight (parse + input-header + restart-header validation)"
source /etc/profile.d/00-modulepath.sh 2>/dev/null || true
source /etc/profile.d/modules.sh 2>/dev/null || true
module purge 2>/dev/null || true
module load intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 netcdf-c curl/8.4.0 expat/2.5.0 || true
export LPJROOT=${LPJROOT} LPJOUTPATH="${outpath}" LPJRESTARTPATH="${outpath}"
# run from outpath so relative "output/" resolves (dir exists there)
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
