#!/usr/bin/env bash
# ── DOES THE SHARED GENE POOL'S DIVERSITY COLLAPSE AT LOW PATCH COUNT? (line O, 2026-08-17) ────────────
#
# WHY THIS EXISTS — the mechanism nobody had named. The patches in a cell are NOT independent replicates.
# Reading the source (`src/lpj/getsapling.c`, `src/tree/new_tree.c:126-137`):
#
#   * the inheritance seed bank is a CELL-level list, `cell->treelist` / `cell->treelen`, built by
#     `getsapling()` which loops over ALL patches in the cell and admits every tree whose above-ground
#     biomass exceeds `getmaxagb(stand, param.n_max * stand->npatch * param.patcharea/100)` — i.e. the
#     top `7 * 2.25 * npatch = 15.75 * npatch` trees — accumulated over a rolling `param.max_age = 50` yr;
#   * every inherited recruit draws a parent from it as a UNIFORM sample at exactly ONE call site,
#     `new_tree.c:137`: `index = (int)(erand48(cell->seed) * treelen)`;
#   * the inherited channel's weight is 4/(4+n_eligible_PFTs) ~ 44 % at Hainich, ~80 % where diversity is low.
#
# So the gene pool's SIZE IS PROPORTIONAL TO THE PATCH COUNT: ~15 candidate trees per year at npatch=1
# against ~7,875 at npatch=500. That is a structural, patch-count-dependent degradation of the trait
# diversity every recruit inherits from — and it is a DIFFERENT mechanism from the exp(-LAI) Jensen gap
# that this project had assumed was the whole story behind the measured 21-81 % recruitment loss at low
# patch count. This script measures it directly.
#
# WHY IT MATTERS FOR SPEED. The patch ensemble is ~99.7 % of the cost at the production npatch=500
# (measured: cost(J) = a + b*J with a ~ 0), so running fewer patches is the ONLY route to an
# order-of-magnitude speedup. If the dominant few-vs-many difference is the gene pool -- a low-dimensional
# object (7 PFTs x ~8 sampled trait axes) that is only ever SAMPLED FROM, at one call site -- then it can
# be represented at its many-patch richness while the physics runs on few patches. That is a one-call-site
# intervention, and it is the kind of thing a statistical model can supply honestly, because the target is
# a POOLED distribution over thousands of trees rather than a single noisy count.
#
# WHAT IT MEASURES. Per patch count, from the `ind` table over a short transient: the spread (sd, IQR) and
# the effective number of distinct values of each inherited trait among YOUNG trees (the recruits, whose
# traits still reflect the pool they were drawn from), plus the PFT composition. If the mechanism is real,
# spread and distinct-value counts fall monotonically as the patch count falls.
#
# ⚠ Reuses the restarts written by scripts/probe_c_patch_scaling.sh -- run that first (it is what pays for
#   the one spin-up per patch count that npatch being restart-pinned forces).
# ⚠ `ind` is emitted with a HEADER line and the mort_* columns are uninitialised garbage at the top of a
#   restarted run (CLAUDE.md §3) -- the reader below pins dtypes and never touches mort_*.
# ⚠ TIMING IS NOT THE POINT HERE: this arm writes the `ind` table, which costs real time. Never quote a
#   core-seconds figure from this script.
#
# Usage:  scripts/probe_c_genepool_diversity.sh [CELL] [YEARS]
# env: NPATCHES · SRC (dir holding rst_j<J>.lpj) · ROOT · SUBMIT · DEPEND=<jobid>
set -euo pipefail

CELL="${1:-42490}"; YRS="${2:-3}"
NPATCHES="${NPATCHES:-1 5 10 25 50 100}"
SRC="${SRC:-/p/tmp/jamirp/O_patchscaling}"
ROOT="${ROOT:-/p/tmp/jamirp/O_genepool}"
SUBMIT="${SUBMIT:-1}"; DEPEND="${DEPEND:-}"
PARTITION="${PARTITION:-priority}"; QOS="${QOS:-priority}"
LPJROOT="${LPJROOT:-/home/jamirp/lpjml56fit}"
GLOBAL="${GLOBAL:-/p/projects/waldspektrum/priesner/clustering/global}"
FY=2001

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

for J in ${NPATCHES}; do
  mkdir -p "${ROOT}/ind_j${J}"
  cat > "${ROOT}/scripts/ind_j${J}.js" <<EOF
{
  "sim_name" : "O gene pool", "sim_id" : "lpjml", "version" : "5.6",
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
    { "id" : "grid", "file" : { "fmt" : "cdf", "name" : "ind_j${J}/grid.nc" }},
    { "id" : "ind",  "file" : { "fmt" : "txt", "name" : "ind_j${J}/ind.csv" }}
  ],
  "startgrid" : ${CELL}, "endgrid" : ${CELL},
  "nspinup" : 0, "nspinyear" : 30, "firstyear": ${FY}, "lastyear" : $(( FY + YRS - 1 )),
  "outputyear": ${FY}, "restart" : true, "restart_filename" : "${SRC}/rst_j${J}.lpj",
  "write_restart" : false, "write_restart_filename" : "unused.lpj", "restart_year": ${FY}
}
EOF
done

cat > "${ROOT}/genepool.jcf" <<EOF
#!/usr/bin/env bash
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --account=waldspektrum
#SBATCH --partition=${PARTITION}
#SBATCH --qos=${QOS}
#SBATCH --job-name=O-genepool
#SBATCH --time=01:00:00
$( [ -n "${DEPEND}" ] && echo "#SBATCH --dependency=afterok:${DEPEND}" )
#SBATCH -o ${ROOT}/genepool.%j.out
#SBATCH -e ${ROOT}/genepool.%j.out
source /etc/profile.d/00-modulepath.sh 2>/dev/null || true
source /etc/profile.d/modules.sh 2>/dev/null || true
module purge 2>/dev/null || true
module load intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 netcdf-c curl/8.4.0 expat/2.5.0
export LPJROOT=${LPJROOT} LPJOUTPATH=${ROOT} LPJRESTARTPATH=${ROOT}
cd ${ROOT}
echo "=== GENE-POOL DIVERSITY vs PATCH COUNT ==="
echo "cell ${CELL}   ${YRS} yr from each patch count's own restart in ${SRC}"
echo "the shared seed bank admits the top 15.75*npatch trees, so its size scales with npatch"
echo

for J in ${NPATCHES}; do
  [ -f ${SRC}/rst_j\${J}.lpj ] || { echo "  J=\${J}: SKIP (no restart at ${SRC}/rst_j\${J}.lpj)"; continue; }
  ${LPJROOT}/bin/lpjml -DFROM_RESTART ${ROOT}/scripts/ind_j\${J}.js > ${ROOT}/ind_j\${J}.log 2>&1
  if grep -q "lpjml successfully terminated, 1 grid cells processed." ${ROOT}/ind_j\${J}.log; then
    echo "  J=\${J}: ok (\$(wc -l < ${ROOT}/ind_j\${J}/ind.csv) rows)"
  else
    echo "  J=\${J}: FAILED"; tail -4 ${ROOT}/ind_j\${J}.log
  fi
done

echo
python3 - <<'PYEOF'
import csv, glob, math, os, re, statistics as st
ROOT = "${ROOT}"
# The inherited trait axes actually stored in the seed bank (getsapling.c) and copied by new_tree.c.
TRAITS = ["SLA", "Wooddens", "D95max", "minwscal"]
runs = {}
for f in sorted(glob.glob(os.path.join(ROOT, "ind_j*/ind.csv")),
                key=lambda p: int(re.search(r"ind_j(\d+)", p).group(1))):
    J = int(re.search(r"ind_j(\d+)", f).group(1))
    rd = csv.DictReader(open(f), skipinitialspace=True)
    rows, seen = [], set()
    for r in rd:
        try:
            if int(float(r["Type"])) > 6:      # tree filter: ids 0-6 are the seven tree PFTs
                continue
            if int(float(r.get("isdead", 0))): # drop stems flagged dead
                continue
            # ⚠ DEDUPE BY (Patch, ID). The `ind` table is ANNUAL, so a stem alive for N years is emitted
            # N times, and a naive "distinct trait values / n_rows" then just measures 1/N (it came out
            # ~0.35 for every patch count on a 3-yr run — an artifact, not a diversity signal). (Cell,
            # Patch, ID) is a stable cross-year individual identity (ADR 0125), so keep each stem ONCE.
            key = (int(float(r.get("Patch", -1))), int(float(r.get("ID", -1))))
            if key in seen:
                continue
            seen.add(key)
            rows.append({k: float(r[k]) for k in (TRAITS + ["Age", "Type"]) if k in r})
        except (KeyError, ValueError, TypeError):
            continue
    if rows:
        runs[J] = rows

if not runs:
    print("no ind data parsed"); raise SystemExit

def summarize(rows, trait):
    xs = [r[trait] for r in rows if trait in r]
    if len(xs) < 3: return None
    mu = sum(xs)/len(xs)
    sd = st.pstdev(xs)
    xs_s = sorted(xs)
    q1 = xs_s[len(xs_s)//4]; q3 = xs_s[(3*len(xs_s))//4]
    return dict(n=len(xs), mean=mu, sd=sd, cv=100*sd/abs(mu) if mu else float("nan"),
                iqr=q3-q1, ndist=len(set(round(x, 10) for x in xs)))

Js = sorted(runs)
print("=== ALL LIVING TREE STEMS ===")
for trait in TRAITS:
    print("\n  " + trait)
    print("      J    n_stems    mean        sd       CV %      IQR    distinct   distinct/n")
    for J in Js:
        s = summarize(runs[J], trait)
        if not s: continue
        print("   %4d  %8d  %10.5g %10.4g %8.2f %10.4g %8d %10.3f"
              % (J, s["n"], s["mean"], s["sd"], s["cv"], s["iqr"], s["ndist"], s["ndist"]/s["n"]))

print("\n=== YOUNG STEMS ONLY (Age <= 15): these carry the pool they were drawn from ===")
for trait in TRAITS:
    print("\n  " + trait + "  (young)")
    print("      J    n_young     mean        sd       CV %      IQR    distinct")
    for J in Js:
        young = [r for r in runs[J] if r.get("Age", 1e9) <= 15]
        s = summarize(young, trait)
        if not s: continue
        print("   %4d  %8d  %10.5g %10.4g %8.2f %10.4g %8d"
              % (J, s["n"], s["mean"], s["sd"], s["cv"], s["iqr"], s["ndist"]))

print("\n=== PFT COMPOSITION (how many of the 7 tree PFTs survive at each patch count) ===")
print("      J   n_PFTs  present")
for J in Js:
    ids = sorted({int(r["Type"]) for r in runs[J]})
    print("   %4d  %6d  %s" % (J, len(ids), ids))

print("\n=== SMALL-SAMPLE WARNING (read before believing any trend in the young-stem table) ===")
print("A CV estimated from a handful of stems is biased LOW, and the low-patch-count runs have few young")
print("stems by construction -- so small-sample bias pushes in the SAME direction as the hypothesis being")
print("tested. Any young-stem group with n < 30 is not evidence. Counts per patch count:")
for J in Js:
    ny = len([r for r in runs[J] if r.get("Age", 1e9) <= 15])
    print("   J=%4d : %4d young stems%s" % (J, ny, "   <-- TOO FEW, not evidence" if ny < 30 else ""))

print("\n=== READING ===")
print("⚠ CHOOSE THE CELL DELIBERATELY. The inherited channel's weight is 4/(4+n_eligible_PFTs), so it is")
print("~44 % at Hainich (5 eligible tree types) but ~80 % at a low-diversity cell (Amazon 12045, Sahel")
print("18371, where 1 type is eligible). The rest of the recruits come from the UNIFORM background channel,")
print("which refreshes trait diversity independently of the pool's size. Hainich is therefore the cell")
print("where this mechanism is WEAKEST -- a flat result there is not a refutation, and a test at Hainich")
print("alone cannot settle it. Measured at Hainich: standing-stand spread is FLAT in patch count for SLA,")
print("wood density and minwscal; only rooting depth rises (CV 37.6 -> ~58). Run 12045 to decide.")
print()
print("If trait spread (sd / CV / IQR) and the PFT count fall MONOTONICALLY with patch count, the shared")
print("seed bank -- whose size is 15.75*npatch -- is a genuine patch-count-dependent bias channel, distinct")
print("from the exp(-LAI) plot-averaging effect. It is then also the CHEAPEST one to fix, because the pool")
print("is only ever sampled from, at one call site (new_tree.c:137).")
print("If the spread is FLAT in patch count, the mechanism is not operating at this cell and the")
print("few-vs-many difference is dominated by something else -- say so and drop this line of attack.")
PYEOF
echo "=== GENE POOL DONE ==="
EOF

echo "generated ${ROOT}/genepool.jcf"
if [ "${SUBMIT}" = "1" ]; then
    jid=$(sbatch "${ROOT}/genepool.jcf" | awk '{print $NF}')
    echo "submitted job ${jid}"; echo "  log: ${ROOT}/genepool.${jid}.out"
    [ -n "${DEPEND}" ] && scontrol show job "${jid}" | grep -o 'Dependency=[^ ]*' || true
else
    echo "SUBMIT=0 — not submitted"
fi
