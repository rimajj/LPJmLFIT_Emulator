#!/usr/bin/env bash
# ── THE PATCH-SCALING LAW OF THE LPJmL-FIT C BINARY (line O; owner question 2026-08-17) ────────────────
#
# WHY THIS EXISTS. Every speed verdict in this project so far — ADR 0093's "the patch ensemble is NOT the
# bottleneck", ADR 0084's "patch reduction is a clean ~3x worth nothing to argue about now", and line O's
# kill of the few-patch->many-patch surrogate — was computed at **npatch = 25**. The owner states that
# publication-grade LPJmL-FIT runs use **~500 patches per cell**, and that 25 was a testing convenience.
# If cost is linear in patch count, then at 500 patches the ensemble is 95-99.8 % of the entire bill and
# every one of those verdicts inverts. That is a factual question about the C code and it is cheap to
# settle, so settle it instead of arguing from the 25-patch numbers.
#
# WHAT IT MEASURES. cost(cell-year) as a function of npatch, as
#     cost(J) = a + b*J
# where `a` is the genuinely per-CELL work (climate read/interpolation, soil temperature forcing, the
# cell-level output accumulation) and `b*J` is the per-PATCH work. The ratio a/(a+b*J) at J=500 is the
# hard Amdahl ceiling on any patch-reduction scheme — if `a` is tiny, patch reduction is the whole game.
#
# ⚠ THE npatch-ON-RESTART TRAP, and why this script spins up its own restarts. `npatch` is only consulted
# in the NON-restart branch (`newgrid.c:477 addstand(...,config->npatch)`); a `-DFROM_RESTART` run takes
# its patch count from the restart file, so pointing five configs with five different `npatch` at the
# shared `restart_1999.lpj` would silently time **25 patches five times**. That is exactly the class of
# error ADR 0084 caught in ADR 0093's harness (a label with no arm behind it), so this script pays for one
# spin-up per patch count and asserts the resulting stand density is patch-count-independent.
#
# ⚠ THE FIXED-COST TRAP (inherited from bench_speed_gate_c.sh). Each patch count is run at TWO transient
# lengths from its own restart and the wall times are DIFFERENCED, so MPI start-up, the restart read and
# output writing cancel exactly. Never quote the naive ratio.
#
# ⚠ THIS IS A TIMING MEASUREMENT, NOT A FIDELITY ONE (ADR 0041): a subset re-run is not a per-cell replica
# of the global run. Cost per cell-year does not care which of two statistically identical trajectories is
# taken. Never score physics from this run's output. The one physics quantity read here is cell `vegc`,
# used ONLY as a same-stand-density fairness check between the patch counts.
#
# Usage:  scripts/probe_c_patch_scaling.sh [CELL] [NSPIN] [YEARS_SHORT] [YEARS_LONG]
# defaults: 42490 (Hainich) 300 5 10
# env: NPATCHES="1 5 10 25 50 100" · SUBMIT=1|0 · ROOT · PARTITION · QOS · EXCLUSIVE · REPS=2
#
# Collect: tail -f <ROOT>/scaling.<jobid>.out  — last line `=== PATCH SCALING DONE ===`
set -euo pipefail

CELL="${1:-42490}"; NSPIN="${2:-300}"; YS="${3:-5}"; YL="${4:-10}"
NPATCHES="${NPATCHES:-1 5 10 25 50 100}"
SUBMIT="${SUBMIT:-1}"; REPS="${REPS:-2}"
PARTITION="${PARTITION:-priority}"; QOS="${QOS:-priority}"; EXCLUSIVE="${EXCLUSIVE:-0}"
ROOT="${ROOT:-/p/tmp/jamirp/O_patchscaling}"
LPJROOT="${LPJROOT:-/home/jamirp/lpjml56fit}"
GLOBAL="${GLOBAL:-/p/projects/waldspektrum/priesner/clustering/global}"
FY=2000                                   # spin-up ends here; the timed transient starts at FY+1

[ -x "${LPJROOT}/bin/lpjml" ] || { echo "missing binary: ${LPJROOT}/bin/lpjml" >&2; exit 1; }
mkdir -p "${ROOT}/scripts"

cat > "${ROOT}/scripts/input.js" <<EOF
"inpath" : "${GLOBAL}/",
"soilmap" : [null,"clay","silty clay","sandy clay","clay loam","silty clay loam",
             "sandy clay loam","loam","silt loam","sandy loam","silt",
             "loamy sand","sand","rock and ice"],
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

# $1 npatch  $2 tag  $3 nspinup  $4 firstyear  $5 lastyear  $6 restart?  $7 restart_in  $8 write_restart?
write_cfg () {
    local J="$1" TAG="$2" NSP="$3" F="$4" L="$5" RIN="$6" RFILE="$7" WOUT="$8"
    cat > "${ROOT}/scripts/${TAG}.js" <<EOF
{
  "sim_name" : "O patch scaling", "sim_id" : "lpjml", "version" : "5.6",
  "individual" : true, "inheritance" : true, "inherit_startyear" : 0, "npatch" : ${J},
  "cut_year": -9999, "tree_year": -1, "isD95max" : true, "random_prec" : false,
  "random_seed" : 1, "radiation" : "radiation", "fire" : "fire",
  "fire_on_grassland" : false, "fdi" : "nesterov", "relative_humidity": false,
  "firewood" : false, "new_phenology" : true, "new_trf" : false,
  "river_routing" : false, "extflow" : false, "no_grass" : false, "logging" : false,
  "percolation_heattransfer" : true, "pft_est" : false, "with_days" : true,
  "permafrost" : true, "johansen" : true, "soilpar_option" : "no_fixed_soilpar",
  "with_nitrogen" : "no", "store_climate" : true, "const_climate" : false,
  "shuffle_climate" : true, "const_deposition" : false, "depos_year_const" : 1901,
  "fix_climate" : false, "fix_landuse" : false, "root_model" : "logistic",
  "new_seed" : false, "population" : false, "landuse" : "no",
  "landuse_year_const" : 2000, "reservoir" : true, "wateruse" : "no",
  "equilsoil" : false, "istrack" : false, "prescribe_burntarea" : false,
  "prescribe_landcover" : "no_landcover", "sowing_date_option" : "fixed_sdate",
  "sdate_fixyear" : 1970, "intercrop" : false,
  "residue_treatment" : "fixed_residue_remove", "residues_fire" : false,
  "irrigation" : "lim", "laimax_interpolate" : "laimax_par", "tillage_type" : "all",
  "till_startyear" : 1850, "black_fallow" : false, "pft_residue" : "temperate cereals",
  "no_ndeposition" : false, "rw_manage" : false, "laimax" : 5,
  "fertilizer_input" : "yes", "manure_input" : true, "fix_fertilization" : false,
  "others_to_crop" : true, "grazing" : "default", "grazing_others" : "default",
  "cft_temp" : "temperate cereals", "cft_tropic" : "maize", "grassonly" : false,
  "istimber" : true, "grassland_fixed_pft" : false, "grass_harvest_options" : false,
  "mowing_days" : [152, 335], "crop_resp_fix" : false, "crop_phu_option" : "new",
  "cropsheatfrost" : false, "double_harvest" : true, "ma_bnf" : true,
#include "param_lpjmlfit.js"
#include "${ROOT}/scripts/input.js"
  "grid_scaled" : false, "output_metafile" : true, "float_grid" : false,
  "crop_index" : "temperate cereals", "crop_irrigation" : false,
  "output" :
  [
    { "id" : "grid",       "file" : { "fmt" : "cdf", "name" : "${TAG}/grid.nc" }},
    { "id" : "globalflux", "file" : { "fmt" : "txt", "name" : "${TAG}/globalflux.csv" }}
  ],
  "startgrid" : ${CELL}, "endgrid" : ${CELL},
  "nspinup" : ${NSP}, "nspinyear" : 30, "firstyear": ${F}, "lastyear" : ${L},
  "outputyear": ${F}, "restart" : ${RIN}, "restart_filename" : "${RFILE}",
  "write_restart" : ${WOUT}, "write_restart_filename" : "rst_j${J}.lpj", "restart_year": ${L}
}
EOF
}

for J in ${NPATCHES}; do
    mkdir -p "${ROOT}/spin_j${J}" "${ROOT}/short_j${J}" "${ROOT}/long_j${J}"
    # spin-up from bare ground -> writes rst_j<J>.lpj holding exactly J patches
    # restart_filename is unused when "restart":false, but the parser still needs a valid string literal —
    # an empty one written as '""' expands to `""""` and dies with ERROR228 (object value separator).
    write_cfg "${J}" "spin_j${J}"  "${NSPIN}" "${FY}"        "${FY}"                 false "${ROOT}/unused.lpj"         true
    # two timed transient lengths, both from that restart
    write_cfg "${J}" "short_j${J}" 0          "$((FY+1))"    "$((FY+YS))"            true  "${ROOT}/rst_j${J}.lpj"      false
    write_cfg "${J}" "long_j${J}"  0          "$((FY+1))"    "$((FY+YL))"            true  "${ROOT}/rst_j${J}.lpj"      false
done

cat > "${ROOT}/scaling.jcf" <<EOF
#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --account=waldspektrum
#SBATCH --partition=${PARTITION}
#SBATCH --qos=${QOS}
#SBATCH --job-name=O-patchscale
#SBATCH --time=03:00:00
$( [ "${EXCLUSIVE}" = "1" ] && echo '#SBATCH --exclusive' )
#SBATCH -o ${ROOT}/scaling.%j.out
#SBATCH -e ${ROOT}/scaling.%j.out
source /etc/profile.d/00-modulepath.sh 2>/dev/null || true
source /etc/profile.d/modules.sh 2>/dev/null || true
module purge 2>/dev/null || true
module load intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 netcdf-c curl/8.4.0 expat/2.5.0
export LPJROOT=${LPJROOT} LPJOUTPATH=${ROOT} LPJRESTARTPATH=${ROOT}
cd ${ROOT}
echo "=== PATCH-SCALING LAW OF THE C BINARY ==="
echo "binary   : ${LPJROOT}/bin/lpjml  (\$(stat -c %y ${LPJROOT}/bin/lpjml))"
echo "cell     : ${CELL} (orderA 0-based)   host \$(hostname)   cores=1"
echo "spin-up  : ${NSPIN} yr from bare ground, per patch count (npatch is ignored on restart)"
echo "transient: short=${YS} yr  long=${YL} yr, both from that patch count's own restart"
echo "npatches : ${NPATCHES}    reps=${REPS}"
echo

run_one () {   # \$1 = tag ; echoes elapsed seconds ; requires the completion line
  local TAG="\$1" t0 t1
  t0=\$(date +%s.%N)
  ${LPJROOT}/bin/lpjml ${ROOT}/scripts/\${TAG}.js > ${ROOT}/\${TAG}.log 2>&1
  t1=\$(date +%s.%N)
  grep -q "lpjml successfully terminated, 1 grid cells processed." ${ROOT}/\${TAG}.log \\
    || { echo "FATAL: no completion line in \${TAG}.log" >&2; tail -8 ${ROOT}/\${TAG}.log >&2; exit 3; }
  echo "\$t1 \$t0" | awk '{printf "%.3f", \$1-\$2}'
}

: > ${ROOT}/scaling.csv
echo "npatch,wall_short_s,wall_long_s,marginal_core_s_per_cell_yr,naive_long,vegc_gC_m2" >> ${ROOT}/scaling.csv

for J in ${NPATCHES}; do
  echo "--- npatch = \${J} ---"
  # one spin-up per patch count; this is the price of npatch being restart-pinned
  ts0=\$(date +%s)
  run_one "spin_j\${J}" > /dev/null
  echo "  spin-up (${NSPIN} yr): \$(( \$(date +%s) - ts0 ))s -> rst_j\${J}.lpj"
  [ -f ${ROOT}/rst_j\${J}.lpj ] || { echo "FATAL: no restart written for npatch=\${J}"; exit 4; }

  TS=999999; TL=999999
  for rep in \$(seq 1 ${REPS}); do
    s=\$(run_one "short_j\${J}"); l=\$(run_one "long_j\${J}")
    echo "  rep \$rep: short=\${s}s  long=\${l}s"
    TS=\$(echo "\$TS \$s" | awk '{print (\$2<\$1)?\$2:\$1}')
    TL=\$(echo "\$TL \$l" | awk '{print (\$2<\$1)?\$2:\$1}')
  done
  # FAIRNESS CHECK: globalflux vegc is already per-unit-area (flux_sum divides by npatch), so it must be
  # ~patch-count-independent. If it is not, the patch counts are not comparable stands and the scaling
  # law measured here is confounded by stand density. Report it, do not silently proceed.
  VEGC=\$(awk -F',' 'NR>1{v=\$0} END{print v}' ${ROOT}/long_j\${J}/globalflux.csv 2>/dev/null | tr ',' '\n' | awk 'NR>1' | head -40 | sort -g | tail -1)
  awk -v j="\$J" -v ts="\$TS" -v tl="\$TL" -v ys="${YS}" -v yl="${YL}" -v vg="\$VEGC" 'BEGIN{
    m=(tl-ts)/(yl-ys);
    printf "  MARGINAL: %.5f core-s/cell-yr   (naive long %.5f)\n", m, tl/yl;
    printf "%d,%.3f,%.3f,%.6f,%.6f,%s\n", j, ts, tl, m, tl/yl, vg >> "'${ROOT}'/scaling.csv";
  }'
done

echo
echo "=== THE LAW ==="
# ⚠ READ cost/J FIRST, NOT AN UNCONSTRAINED LINE FIT. Measured at Hainich, the per-patch cost is FLAT in
# J (0.01385 +- 4.7 %), i.e. cost is PROPORTIONAL to patch count with no resolvable per-cell fixed cost —
# and an unconstrained least-squares line through such data returns a small NEGATIVE intercept (measured
# -0.0078), which then makes "per-cell share" and "ceiling = cost(500)/a" print as negative nonsense.
# That was a real defect in the first version of this script. So: report cost/J and its scatter, fit
# through the ORIGIN, and BOUND the fixed cost from the J=1 point instead of extrapolating to it.
awk -F',' 'NR>1{n++; J[n]=\$1; c[n]=\$4; xy+=\$1*\$4; xx+=\$1*\$1; p=\$4/\$1; s+=p; ss+=p*p; if(jmin==0||\$1<jmin){jmin=\$1; cmin=\$4}}
END{
  if(n<2){print "  <2 points, no fit"; exit}
  m=s/n; sd=sqrt(ss/n-m*m);
  print "  per-patch cost, measured directly as cost/J:";
  for(i=1;i<=n;i++) printf "    J=%4d  cost %9.5f  ->  %.5f core-s per patch-year\n", J[i], c[i], c[i]/J[i];
  printf "    mean %.5f   sd %.5f   (%.1f %% scatter)\n", m, sd, 100*sd/m;
  if(100*sd/m < 15) print "    ==> FLAT in J: cost is PROPORTIONAL to patch count, no per-cell floor detected.";
  else print "    ==> NOT flat: the cost is not proportional to patch count — investigate before extrapolating.";
  b=xy/xx;   # fit through the origin
  printf "\n  b (per-PATCH, fit through the origin) = %.6f core-s/patch-yr\n", b;
  printf "  the patch-count-independent part is AT MOST the whole J=%d cost (%.4f core-s),\n", jmin, cmin;
  printf "  i.e. at most %.3f %% of the %d-patch bill — a BOUND, not an estimate.\n", 100*cmin/(b*500), 500;
  printf "\n  cost per cell-year, and the global bill over 54020 tree-bearing cells:\n";
  split("1 5 10 25 50 100 250 500 1000", g, " ");
  for(k=1;k<=9;k++){ j=g[k]+0; printf "    npatch %5d : %9.4f core-s/cell-yr   %8.1f core-h per simulated year\n", j, b*j, b*j*54020/3600 }
  printf "\n  speedup from 500 patches (exactly 500/J — no Amdahl floor was detected):\n";
  split("100 50 25 10 5 2", h, " ");
  for(k=1;k<=6;k++){ j=h[k]+0; printf "    -> %4d patches : %6.1fx   (cost %.4f core-s/cell-yr)\n", j, 500.0/j, b*j }
  printf "\n  at 500 patches (%.2f core-s/cell-yr) versus the compute targets:\n", b*500;
  printf "    %-56s %7.0fx over\n", "project convention 0.030 (small fast atmosphere)*", b*500/0.030;
  printf "    %-56s %7.1fx over\n", "10 %% of a CMIP-class 1-deg atmosphere (~5.0)", b*500/5.0;
  print  "    * a CONVENTION (10 % of a measured SpeedyWeather cost), NOT an owner requirement.";
}' ${ROOT}/scaling.csv
echo
echo "  FAIRNESS CHECK — cell vegetation carbon must be ~flat across patch counts, or the stands being"
echo "  compared are not equivalent and the scaling law is confounded by stand density:"
awk -F',' 'NR>1{n++; s+=\$6; if(n==1||\$6<lo)lo=\$6; if(n==1||\$6>hi)hi=\$6}
END{ if(n<2)exit; printf "    vegc spread %.1f %% over %d patch counts", 100*(hi-lo)/(s/n), n;
     print (100*(hi-lo)/(s/n) < 15) ? "  -> comparable stands, comparison is fair" : "  -> NOT comparable, do not trust the law" }' ${ROOT}/scaling.csv
echo
cat ${ROOT}/scaling.csv
echo "=== PATCH SCALING DONE ==="
EOF

echo "generated ${ROOT}/scaling.jcf"
if [ "${SUBMIT}" = "1" ]; then
    jid=$(sbatch "${ROOT}/scaling.jcf" | awk '{print $NF}')
    echo "submitted job ${jid}"
    echo "  log: ${ROOT}/scaling.${jid}.out"
else
    echo "SUBMIT=0 — not submitted"
fi
