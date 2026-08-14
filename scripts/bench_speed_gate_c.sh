#!/usr/bin/env bash
# ── 5-pre · THE END-TO-END SPEED GATE, C ARM (line O; EXECUTION_PLAN.md §4, ADR 0093/0094) ────────────
#
# Measures **core-seconds per cell-year** for the LPJmL-FIT C binary — the model the emulator replaces —
# on a NAMED cell block over NAMED years, so it can be compared with `scripts/bench_speed_gate.jl`.
#
# WHY A GENERATOR AND NOT A FIXED CONFIG. The C's cost is dominated by how many individuals a cell
# carries (ADR 0093: `cost(cell-yr) = 0.125 + 0.00196*n_ind`), so a single number is meaningless without
# the cell block it was measured on. This script takes the block as arguments and prints the number with
# its own basis attached.
#
# ⚠ THE FIXED-COST TRAP, and how this script removes it. A whole-process wall time includes MPI start-up,
# reading a 67 420-cell restart file, and writing outputs — all of which are per-RUN, not per-cell-year.
# ADR 0093 divided one run's wall time by its cell-years and got 0.290; that is an UPPER bound on the
# marginal rate. This script runs the SAME cell block at TWO run lengths and takes the slope
#     rate = (wall_long - wall_short) / (ncell * (years_long - years_short))
# which cancels every per-run fixed cost exactly. Both the naive ratio and the slope are printed; quote
# the slope as the C's per-cell-year cost and the naive ratio only when comparing with ADR 0093.
#
# ⚠ THE OUTPUT-ARM TRAP. Writing the `ind` table costs real time and the emulator writes nothing
# comparable. `ARM=min` (the default) emits only `grid` + `globalflux`, which is the fair compute-only
# basis. `ARM=ind` adds the per-individual table and is there to price the I/O, not to be compared.
#
# ⚠ THIS IS A TIMING MEASUREMENT, NOT A FIDELITY ONE. A subset re-run is NOT a per-cell replica of the
# global run (ADR 0041) — the trajectory diverges. That is irrelevant here: cost per cell-year does not
# depend on which of two statistically identical trajectories is taken, and the individual counts that
# DO drive cost come from the shared restart file. Never score physics from this run's output.
#
# Usage:
#   scripts/bench_speed_gate_c.sh [C0] [C1] [YEARS_SHORT] [YEARS_LONG]
# defaults: 42480 42500 10 20   (21 cells around Hainich 42490 — ADR 0093's own block)
# env: ARM=min|ind · SUBMIT=1|0 · ROOT=<scratch dir> · PERF=1 (also run `perf record` for the profile)
#
# Collect:  tail -f <ROOT>/<tag>/bench.<jobid>.out   — last line `=== C BENCH DONE ===`
set -euo pipefail

C0="${1:-42480}"; C1="${2:-42500}"; YS="${3:-10}"; YL="${4:-20}"
ARM="${ARM:-min}"; SUBMIT="${SUBMIT:-1}"; PERF="${PERF:-0}"
# `priority` is usually empty and starts at once, but its QOS caps at cpu=64 per job, so `--exclusive`
# on a 128-cpu node can be rejected with "Job violates accounting/QOS policy" (CLAUDE.md §9). Default to
# priority WITHOUT exclusivity — which is also how ADR 0093's C figures were measured, so the numbers are
# like-for-like — and set EXCLUSIVE=1 PARTITION=standard QOS=short for a contention-free re-measure.
PARTITION="${PARTITION:-priority}"; QOS="${QOS:-priority}"; EXCLUSIVE="${EXCLUSIVE:-0}"
ROOT="${ROOT:-/p/tmp/jamirp/O_speedgate_c}"
LPJROOT="${LPJROOT:-/home/jamirp/lpjml56fit}"
GLOBAL="${GLOBAL:-/p/projects/waldspektrum/priesner/clustering/global}"
RESTART="${RESTART:-${GLOBAL}/Historical/ground_truth/model_output/transient_2000_2019_npatch25_nspinup1000_nspinyear30_random_seed1/restart/restart_1999.lpj}"
FY=2000                                  # the restart is the 1999 spin-up end ⇒ transient starts 2000
NCELL=$(( C1 - C0 + 1 ))
tag="${ARM}_c${C0}_${C1}_y${YS}_${YL}"
out="${ROOT}/${tag}"

[ -f "${RESTART}" ] || { echo "missing restart: ${RESTART}" >&2; exit 1; }
[ -x "${LPJROOT}/bin/lpjml" ] || { echo "missing binary: ${LPJROOT}/bin/lpjml" >&2; exit 1; }

mkdir -p "${out}/scripts" "${out}/out_short" "${out}/out_long"

cat > "${out}/scripts/input.js" <<EOF
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

# One config per run length. `outdir` differs so the two runs cannot overwrite each other's outputs.
write_cfg () {   # $1 = lastyear   $2 = output subdir
    local LY="$1" OD="$2"
    if [ "${ARM}" = "ind" ]; then
        OUTBLOCK='    { "id" : "grid",       "file" : { "fmt" : "cdf", "name" : "'"${OD}"'/grid.nc" }},
    { "id" : "globalflux", "file" : { "fmt" : "txt", "name" : "'"${OD}"'/globalflux.csv" }},
    { "id" : "ind",        "file" : { "fmt" : "txt", "name" : "'"${OD}"'/ind.csv" }},'
    else
        OUTBLOCK='    { "id" : "grid",       "file" : { "fmt" : "cdf", "name" : "'"${OD}"'/grid.nc" }},
    { "id" : "globalflux", "file" : { "fmt" : "txt", "name" : "'"${OD}"'/globalflux.csv" }},'
    fi
    cat > "${out}/scripts/lpjml_${OD}.js" <<EOF
{
  "sim_name" : "O speed gate", "sim_id" : "lpjml", "version" : "5.6",
  "individual" : true, "inheritance" : true, "inherit_startyear" : 0, "npatch" : 25,
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
#include "${out}/scripts/input.js"
  "grid_scaled" : false, "output_metafile" : true, "float_grid" : false,
  "crop_index" : "temperate cereals", "crop_irrigation" : false,
  "output" :
  [
${OUTBLOCK}
  ],
  "startgrid" : ${C0}, "endgrid" : ${C1},
  "nspinup" : 0, "nspinyear" : 30, "firstyear": ${FY}, "lastyear" : $(( FY + LY - 1 )),
  "outputyear": ${FY}, "restart" : true, "restart_filename" : "${RESTART}",
  "write_restart" : false, "write_restart_filename" : "restart/r.lpj", "restart_year": $(( FY + LY - 1 ))
}
EOF
}
write_cfg "${YS}" out_short
write_cfg "${YL}" out_long

cat > "${out}/bench.jcf" <<EOF
#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --account=waldspektrum
#SBATCH --partition=${PARTITION}
#SBATCH --qos=${QOS}
#SBATCH --job-name=O-cbench
#SBATCH --time=01:00:00
$( [ "${EXCLUSIVE}" = "1" ] && echo '#SBATCH --exclusive' )
#SBATCH -o ${out}/bench.%j.out
#SBATCH -e ${out}/bench.%j.out
# EXCLUSIVE=1 keeps a co-tenant from stealing cache/memory bandwidth; the node-contention factor
# measured on this cluster is 1.10x (ADR 0093 evidence dossier). Off by default — see the header.
source /etc/profile.d/00-modulepath.sh 2>/dev/null || true
source /etc/profile.d/modules.sh 2>/dev/null || true
module purge 2>/dev/null || true
module load intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 netcdf-c curl/8.4.0 expat/2.5.0
export LPJROOT=${LPJROOT} LPJOUTPATH=${out} LPJRESTARTPATH=${out}
cd ${out}
echo "=== SPEED GATE — C arm ==="
echo "binary : ${LPJROOT}/bin/lpjml  (\$(stat -c %y ${LPJROOT}/bin/lpjml))"
echo "cells  : ${C0}..${C1}  (${NCELL} cells, orderA 0-based)"
echo "years  : ${FY}..  short=${YS}yr  long=${YL}yr   npatch=25   arm=${ARM}"
echo "host   : \$(hostname)   cores=1 (single task, no MPI)"

# lpjcheck pre-flight — a parse/header error here is cheap, mid-run it is not.
for OD in out_short out_long; do
  ${LPJROOT}/bin/lpjcheck -DFROM_RESTART ${out}/scripts/lpjml_\${OD}.js > ${out}/lpjcheck_\${OD}.txt 2>&1 \\
    || { echo "FATAL lpjcheck failed for \${OD}"; tail -20 ${out}/lpjcheck_\${OD}.txt; exit 2; }
done
echo "lpjcheck: both configs OK"

run_one () {   # \$1 = out subdir ; echoes elapsed seconds
  local OD="\$1" t0 t1
  t0=\$(date +%s.%N)
  ${LPJROOT}/bin/lpjml -DFROM_RESTART ${out}/scripts/lpjml_\${OD}.js > ${out}/\${OD}.log 2>&1
  t1=\$(date +%s.%N)
  # NEVER judge a C run from its exit status (CLAUDE.md §3) — require the completion line.
  grep -q "lpjml successfully terminated, ${NCELL} grid cells processed." ${out}/\${OD}.log \\
    || { echo "FATAL: no completion line in \${OD}.log" >&2; tail -5 ${out}/\${OD}.log >&2; exit 3; }
  echo "\$t1 \$t0" | awk '{printf "%.3f", \$1-\$2}'
}

# Two timed repeats of each length; keep the MINIMUM (noise-robust on a shared cluster).
TS=999999; TL=999999
for rep in 1 2; do
  s=\$(run_one out_short); l=\$(run_one out_long)
  echo "rep \$rep: short=\${s}s  long=\${l}s"
  TS=\$(echo "\$TS \$s" | awk '{print (\$2<\$1)?\$2:\$1}')
  TL=\$(echo "\$TL \$l" | awk '{print (\$2<\$1)?\$2:\$1}')
done

echo
echo "RESULT — core-seconds per cell-year, ${NCELL} cells x npatch 25, single core"
awk -v ts="\$TS" -v tl="\$TL" -v n="${NCELL}" -v ys="${YS}" -v yl="${YL}" 'BEGIN{
  printf "  wall  short (%d yr) : %8.2f s   naive rate %.4f core-s/cell-yr\n", ys, ts, ts/(n*ys);
  printf "  wall  long  (%d yr) : %8.2f s   naive rate %.4f core-s/cell-yr\n", yl, tl, tl/(n*yl);
  printf "  MARGINAL (slope)    : %.4f core-s/cell-yr   <-- quote THIS\n", (tl-ts)/(n*(yl-ys));
  printf "  per-run fixed cost  : %8.2f s  (start-up + restart read + output; %.1f%% of the long run)\n",
         ts - (tl-ts)/(yl-ys)*ys, 100*(ts-(tl-ts)/(yl-ys)*ys)/tl;
}'
EOF

if [ "${PERF}" = "1" ]; then
cat >> "${out}/bench.jcf" <<EOF

echo
echo "=== PROFILE (perf, long run) ==="
perf record -F 199 --call-graph dwarf,4096 -o ${out}/perf.data -- \\
  ${LPJROOT}/bin/lpjml -DFROM_RESTART ${out}/scripts/lpjml_out_long.js > ${out}/perf_stdout.txt 2>&1
perf report -i ${out}/perf.data --stdio --children --percent-limit 0.5 -g none 2>/dev/null | head -50
EOF
fi

echo 'echo "=== C BENCH DONE ==="' >> "${out}/bench.jcf"

echo "generated ${out}/bench.jcf"
if [ "${SUBMIT}" = "1" ]; then
    jid=$(sbatch "${out}/bench.jcf" | awk '{print $NF}')
    echo "submitted job ${jid}"
    echo "  log: ${out}/bench.${jid}.out"
else
    echo "SUBMIT=0 — not submitted"
fi
