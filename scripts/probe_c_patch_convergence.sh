#!/usr/bin/env bash
# ── HOW MANY PATCHES DOES EACH OUTPUT ACTUALLY NEED? (line O; owner question 2026-08-17) ───────────────
#
# WHY THIS EXISTS. The patch ensemble is ~99.7 % of LPJmL-FIT's cost at the production npatch=500
# (measured: cost(J) = 0.019 + 0.0110*J core-s per cell-year, so the per-cell work outside the patch loop
# is 0.35 % of the bill at J=500). Therefore the ONLY route to an order-of-magnitude speedup is to run
# fewer patches. The question that decides whether that is possible is not "how noisy is the ensemble" but
# **which output needs how many patches** — because the answer is wildly different per variable, and the
# outputs an ATMOSPHERE consumes are not the outputs the FOREST SCIENCE consumes.
#
# A first look (one realisation per patch count) showed carbon uptake and evapotranspiration varying only
# 1.7-6.6 % between 1 and 25 patches while net ecosystem production varied 40.6 % and establishment 96.5 %.
# That is the expected signature of a MEAN versus a SMALL RESIDUAL OF TWO LARGE NUMBERS, but with one
# realisation per patch count it cannot be separated from the luck of that patch count's own spin-up. This
# script fixes that: R independent seeds at each patch count, so the spread ACROSS SEEDS at fixed J is the
# estimator's own standard deviation at J, which must fall as 1/sqrt(J).
#
# WHAT IT PRODUCES. For every quantity in `globalflux`, the coefficient of variation as a function of J,
# a fitted 1/sqrt(J) law, and — the actionable output — **the number of patches needed to reach 10 %, 5 %
# and 2 % relative error** for that quantity. That table is the compute budget of LPJmL-FIT, per purpose.
#
# ⚠ EVERY SEED IS A SEPARATE SPIN-UP. `random_seed` is INERT in a restart run (CLAUDE.md §3): with
# "new_seed": false the per-cell RAND48 state is restored from the restart file, so bumping the seed on a
# restart run yields a byte-identical clone. Independent members therefore require independent spin-ups,
# which is what dominates this script's cost.
#
# ⚠ npatch IS RESTART-PINNED (`newgrid.c:477` is the non-restart branch), so each (J, seed) pair needs its
# own spin-up too. That is why the run matrix is J x seeds and not J + seeds.
#
# Usage:  scripts/probe_c_patch_convergence.sh [CELL] [NSPIN] [YEARS]
# defaults: 42490 200 10
# env: NPATCHES="1 5 25 100" · SEEDS="1 2 3 4 5" · SUBMIT · ROOT · PARTITION · QOS
#
# Collect: tail -f <ROOT>/conv.<jobid>.out — last line `=== PATCH CONVERGENCE DONE ===`
set -euo pipefail

CELL="${1:-42490}"; NSPIN="${2:-200}"; YRS="${3:-10}"
NPATCHES="${NPATCHES:-1 5 25 100}"
SEEDS="${SEEDS:-1 2 3 4 5}"
SUBMIT="${SUBMIT:-1}"
PARTITION="${PARTITION:-priority}"; QOS="${QOS:-priority}"
ROOT="${ROOT:-/p/tmp/jamirp/O_patchconv}"
LPJROOT="${LPJROOT:-/home/jamirp/lpjml56fit}"
GLOBAL="${GLOBAL:-/p/projects/waldspektrum/priesner/clustering/global}"
FY=2000

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

# $1 npatch  $2 tag  $3 nspinup  $4 firstyear  $5 lastyear  $6 restart(bool)  $7 restart_in  $8 write(bool)  $9 seed
write_cfg () {
    local J="$1" TAG="$2" NSP="$3" F="$4" L="$5" RIN="$6" RFILE="$7" WOUT="$8" SD="$9"
    cat > "${ROOT}/scripts/${TAG}.js" <<EOF
{
  "sim_name" : "O patch convergence", "sim_id" : "lpjml", "version" : "5.6",
  "individual" : true, "inheritance" : true, "inherit_startyear" : 0, "npatch" : ${J},
  "cut_year": -9999, "tree_year": -1, "isD95max" : true, "random_prec" : false,
  "random_seed" : ${SD}, "radiation" : "radiation", "fire" : "fire",
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
  "write_restart" : ${WOUT}, "write_restart_filename" : "rst_j${J}_s${SD}.lpj", "restart_year": ${L}
}
EOF
}

for J in ${NPATCHES}; do for SD in ${SEEDS}; do
    mkdir -p "${ROOT}/spin_j${J}_s${SD}" "${ROOT}/run_j${J}_s${SD}"
    write_cfg "${J}" "spin_j${J}_s${SD}" "${NSPIN}" "${FY}" "${FY}" false "${ROOT}/unused.lpj" true "${SD}"
    write_cfg "${J}" "run_j${J}_s${SD}"  0 "$((FY+1))" "$((FY+YRS))" true "${ROOT}/rst_j${J}_s${SD}.lpj" false "${SD}"
done; done

cat > "${ROOT}/conv.jcf" <<EOF
#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --account=waldspektrum
#SBATCH --partition=${PARTITION}
#SBATCH --qos=${QOS}
#SBATCH --job-name=O-patchconv
#SBATCH --time=04:00:00
#SBATCH -o ${ROOT}/conv.%j.out
#SBATCH -e ${ROOT}/conv.%j.out
source /etc/profile.d/00-modulepath.sh 2>/dev/null || true
source /etc/profile.d/modules.sh 2>/dev/null || true
module purge 2>/dev/null || true
module load intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 netcdf-c curl/8.4.0 expat/2.5.0
export LPJROOT=${LPJROOT} LPJOUTPATH=${ROOT} LPJRESTARTPATH=${ROOT}
cd ${ROOT}
echo "=== HOW MANY PATCHES DOES EACH OUTPUT NEED? ==="
echo "cell ${CELL}   spin-up ${NSPIN} yr per (patch count, seed)   scored over ${YRS} yr"
echo "patch counts: ${NPATCHES}    seeds: ${SEEDS}    host \$(hostname)"
echo "NOTE: every seed is an independent spin-up (random_seed is inert on restart)."
echo

run_one () {
  local TAG="\$1"
  ${LPJROOT}/bin/lpjml ${ROOT}/scripts/\${TAG}.js > ${ROOT}/\${TAG}.log 2>&1
  grep -q "lpjml successfully terminated, 1 grid cells processed." ${ROOT}/\${TAG}.log \\
    || { echo "FATAL: no completion line in \${TAG}.log" >&2; tail -8 ${ROOT}/\${TAG}.log >&2; return 3; }
}

for J in ${NPATCHES}; do for SD in ${SEEDS}; do
  t0=\$(date +%s)
  run_one "spin_j\${J}_s\${SD}" || exit 3
  run_one "run_j\${J}_s\${SD}"  || exit 3
  echo "  J=\${J} seed=\${SD}: \$(( \$(date +%s) - t0 ))s"
done; done

echo
python3 - <<'PYEOF'
import csv, glob, re, math, os
ROOT = "${ROOT}"
NP   = [int(x) for x in "${NPATCHES}".split()]
data = {}   # (J, seed) -> {col: mean over years}
cols = None
for f in glob.glob(os.path.join(ROOT, "run_j*_s*/globalflux.csv")):
    m = re.search(r"run_j(\d+)_s(\d+)", f)
    J, sd = int(m.group(1)), int(m.group(2))
    rows = [r for r in csv.reader(open(f)) if r]
    cols = rows[0]
    vals = [[float(x) for x in r] for r in rows[2:] if r[0].strip().isdigit()]
    if not vals:
        continue
    n = len(vals)
    data[(J, sd)] = {c: sum(v[i] for v in vals) / n for i, c in enumerate(cols)}

print("=== COEFFICIENT OF VARIATION ACROSS INDEPENDENT SEEDS, BY PATCH COUNT ===")
print("(CV = sd/|mean| across seeds; this IS the estimator's own error at that patch count)")
hdr = "quantity".ljust(12) + "".join(("J=%d" % J).rjust(11) for J in NP) + "   fitted    patches needed for"
print(hdr)
print(" " * 12 + "".join("  CV %".rjust(11) for J in NP) + "   c/sqrtJ    10%     5%     2%")
print("-" * (len(hdr) + 12))

need = {}
for c in cols:
    if c == "Year":
        continue
    cvs, used = [], []
    for J in NP:
        xs = [data[(J, s)][c] for s in range(1, 99) if (J, s) in data]
        if len(xs) < 2:
            cvs.append(float("nan")); continue
        mu = sum(xs) / len(xs)
        sd = math.sqrt(sum((x - mu) ** 2 for x in xs) / (len(xs) - 1))
        if mu == 0:
            cvs.append(float("nan")); continue
        cv = abs(sd / mu) * 100
        cvs.append(cv); used.append((J, cv))
    # fit CV = c / sqrt(J)  ->  c = mean(cv_J * sqrt(J))
    cc = sum(cv * math.sqrt(J) for J, cv in used) / len(used) if used else float("nan")
    row = c.ljust(12) + "".join(("%11.2f" % v) if v == v else "        nan" for v in cvs)
    if cc == cc:
        row += "%10.1f" % cc
        for tgt in (10.0, 5.0, 2.0):
            row += "%7.0f" % math.ceil((cc / tgt) ** 2)
        need[c] = cc
    print(row)

print()
print("=== READING ===")
print("A quantity's patch requirement is (c/target)^2. Quantities the ATMOSPHERE sees (GPP, NPP,")
print("transp, evap, interc) versus quantities the FOREST SCIENCE sees (VegC, estab, NEP, NBP):")
atmos  = [c for c in ("GPP","NPP","transp","evap","interc") if c in need]
forest = [c for c in ("VegC","LitC","SoilC","estab","NEP","NBP","fire") if c in need]
for label, group in (("atmosphere-facing", atmos), ("forest-science", forest)):
    if not group: continue
    worst = max(group, key=lambda c: need[c])
    print("  %-18s worst quantity = %-8s  needs %5.0f patches for 5%%, %5.0f for 2%%"
          % (label, worst, math.ceil((need[worst]/5.0)**2), math.ceil((need[worst]/2.0)**2)))
PYEOF
echo "=== PATCH CONVERGENCE DONE ==="
EOF

echo "generated ${ROOT}/conv.jcf"
if [ "${SUBMIT}" = "1" ]; then
    jid=$(sbatch "${ROOT}/conv.jcf" | awk '{print $NF}')
    echo "submitted job ${jid}"; echo "  log: ${ROOT}/conv.${jid}.out"
else
    echo "SUBMIT=0 — not submitted"
fi
