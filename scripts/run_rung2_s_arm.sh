#!/bin/bash
# Run one arm of RUNG 2 for LINE S: the SHIPPED Component-S count model deciding who dies inside
# LPJmL-FIT's own daily physics (ADR 0175/0176), on either scenario of the warming-response pair.
#
# Unlike scripts/run_rung2_armc.sh — which takes the count target from the ported hazard itself
# (RHO=expected, pinning theta=1) or from the recorded baseline's realized thinning (RHO=recorded), and so
# never asks the LEARNED model anything — this one takes rho from the production count DRF, evaluated on a
# feature row built off the roster the C publishes each year:
#
#   ARM=S0   f_i = rho for every tree     (the shipped uniform thinning, with a LEARNED target)
#   ARM=S0h  S0, but deaths FIT had already settled (`mort >= 1`) are not overridden — the DECOMPOSITION
#            CONTROL (ADR 0176): S1 differs from S0 in TWO ways and this arm changes only the first
#   ARM=S1   f_i = (1 - mort_i)^theta     (learned target, trait-hazard ordering — the S1 - S0 measurement)
#   ARM=NP   rho = 1 every year           (the PERSISTENCE NULL: keep the stand, learn nothing)
#   ARM=REC  no substitution at all       (the per-cell, per-scenario RECORDED BASELINE every arm is
#            scored against — see "WHY REC LIVES HERE" below)
#
# RUN THE NULLS FIRST, ALWAYS.  ADR 0112 showed a persistence null matches the production model on every
# response statistic OFFLINE.  If NP also ties S0/S1 here, this harness has no more power than the offline
# basis did and no S number from it means anything.  And run MODE=none of run_rung2_replay_arm.sh, which
# validates the TRANSPORT — a green null control plus a diverging arm means suspect the payload, not the
# interface (ADR 0121).
#
# Establishment always stays with the C (the harness answers ESTAB_C), so every number here is a MORTALITY
# result: the recruits half has a structural replay floor of 0.907 (ADR 0121).
#
# WHY `ARM=REC` LIVES HERE INSTEAD OF IN run_rung2_replay_arm.sh (load-bearing, 2026-08-12)
# ------------------------------------------------------------------------------------------
# That script's MODE=record hardcodes `bin/lpjml`, which is the CURRENT build and is no longer the binary
# these arms run: line M rebuilt `bin/lpjml` on 2026-08-12 21:12 to add the ADR-0130 `ind`-writer switches,
# so `bin/lpjml` is now v6 + those switches while the arms run `bin/lpjml_rung2_v6`.  Recording a baseline
# with one executable and running the arms with another puts the reference basis and the measurement on
# different builds — exactly what the ADR-0061 rebuild gate exists to prevent.  Keeping REC here means the
# baseline and its arms are pinned to the SAME `$BIN` by construction, not by remembering.
#
# ⚠ A SCENARIO-PAIR (RESPONSE) ARM MUST PASS A TRANSIENT BOUNDARY.  The harness's default boundary tail is
# the committed registry's PRESENT-DAY CLIMATOLOGY — one frozen vector.  Feeding that to an ssp370 leg shows
# the count model present-day climate for all 81 future years, so the response is driven to ~0 BY
# CONSTRUCTION.  This script builds the per-(cell,scenario,year) series automatically (BOUNDARY=auto) with
# scripts/build_rung2_boundary_series.py.  BOUNDARY=static reproduces ADR 0176's arms byte-for-byte.
#
# Env knobs:
#   ARM      S0 | S0h | S1 | NP | REC             (default: S1)
#   SCENARIO historic | ssp370                    (default: historic)
#              historic  2000-2019 from restart_1999.lpj
#              ssp370    2020-2100 from restart_2019.lpj  (81 yr — budget the wall time)
#   CELL     orderA cell index                    (default: 42490, Hainich)
#   NPREV    roster | predict                     (default: roster)
#              roster  — n_prev is the stand's OWN previous stem count, which is the quantity the count
#                        model was TRAINED on (ADR 0112) and the ADR-0175 fix.
#              predict — n_prev is the model's own previous prediction, i.e. the shipped coupled path.
#   SEED     integer, the harness's draw seed     (default: 1)
#   DRF      serialized count forest              (default: the POOLED two-scenario production artifact —
#            a response arm must use one model across both legs, or the "response" is partly a model swap)
#   BOUNDARY auto | frozen | static | <path.csv>  (default: auto)
#            frozen = the DRIFT CONTROL: the scenario's years at PRESENT-DAY climate, so
#            (transient - frozen) is the climate response with drift differenced out
#   BIN      the lpjml executable                 (default: bin/lpjml_rung2_v6)
#   PARTITION / QOS                              (default: standard / short — `priority` caps a USER at
#            10 concurrent jobs, which serialises a big campaign and starves the other lines)
#   SRC      run dir whose lpjml.js is reused     (default: generated for CELL+SCENARIO on demand)
#   TAG      run tag                              (default: S_r2s_<scenario>_c<cell>_<arm>_<nprev>_s<seed>)
#   TIME     SLURM wall limit                     (default: 00:40:00 historic / 04:00:00 ssp370)
#   SUBMIT   yes | no                             (default: yes)
#
# ⚠ Needs a v6 binary and a v6-recorded reference dump — the harness REFUSES a roster with no `rootzone_w`
# column rather than proxying `soilmoist` (the ADR-0035 trap).  Re-record with ARM=REC after a rebuild.
#
# Usage:  ARM=REC SCENARIO=ssp370 CELL=42490 bash scripts/run_rung2_s_arm.sh   # the baseline, first
#         ARM=NP  SCENARIO=ssp370 CELL=42490 bash scripts/run_rung2_s_arm.sh   # then the null
#         ARM=S1  SCENARIO=ssp370 CELL=42490 bash scripts/run_rung2_s_arm.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JULIA=/p/system/packages_rhel9/tools/julia/1.10.0/bin/julia
PYTHON=/home/jamirp/.conda/envs/py311_new/bin/python
ARM="${ARM:-S1}"
SCENARIO="${SCENARIO:-historic}"
CELL="${CELL:-42490}"
NPREV="${NPREV:-roster}"
SEED="${SEED:-1}"
DRF="${DRF:-/p/tmp/jamirp/emulator_global/drf_forest_global_pooled_w20_t8.drf}"
BOUNDARY="${BOUNDARY:-auto}"
BIN="${BIN:-/home/jamirp/lpjml56fit/bin/lpjml_rung2_v6}"
# ⚠ NOT the `priority` partition by default, despite it usually starting instantly: its QOS caps a user at
# **MaxJobsPU = 10 concurrent jobs** (`sacctmgr show qos`), which throttles a several-hundred-job arm
# campaign to ~9 finished runs a minute and monopolises those 10 slots against the other three lines for
# the duration. `short` on `standard` has NO per-user job limit, and both partitions are the same
# 128-cpu/700-GB hardware, so a 1-task run is identical on either. Use PARTITION=priority QOS=priority for
# a handful of interactive runs.
PARTITION="${PARTITION:-standard}"
QOS="${QOS:-short}"
SUBMIT="${SUBMIT:-yes}"

case "$ARM" in S0|S0h|S1|NP|REC) ;; *) echo "ARM must be S0, S0h, S1, NP or REC (got '$ARM')" >&2; exit 2 ;; esac
case "$SCENARIO" in historic|ssp370) ;; *)
  echo "SCENARIO must be historic or ssp370 (got '$SCENARIO')" >&2; exit 2 ;; esac
case "$NPREV" in roster|predict) ;; *)
  echo "NPREV must be roster or predict (got '$NPREV')" >&2; exit 2 ;; esac
[ -x "$BIN" ] || { echo "no executable lpjml at $BIN" >&2; exit 2; }
[ "$ARM" = REC ] || [ -f "$DRF" ] || { echo "no count forest at $DRF" >&2; exit 2; }

if [ "$SCENARIO" = ssp370 ]; then Y0=2020; Y1=2100; DEFTIME=04:00:00; else Y0=2000; Y1=2019; DEFTIME=00:40:00; fi
TIME="${TIME:-$DEFTIME}"
# The tag's scenario token gains `frz` for the frozen-climate control, so its dumps never collide with
# the transient arm's and the scorer can tell the two apart from the directory name alone.
SCENTAG="$SCENARIO"; [ "$BOUNDARY" = frozen ] && SCENTAG="${SCENARIO}frz"
TAG="${TAG:-S_r2s_${SCENTAG}_c${CELL}_${ARM}_${NPREV}_s${SEED}}"

# ---- the source config: generated once per (cell, scenario) and then REUSED by every arm ---------------
# Generating it per arm would be wasteful and, worse, would make the arms' configs merely "equivalent"
# rather than identical.  run_daily_subset.sh is the sanctioned generator for both scenarios (it carries
# the ssp370 forcing block, restart_2019.lpj and the constant-CO2 pin); SUBMIT=no only writes the config.
SRCTAG="S_r2base_c${CELL}"
SRC="${SRC:-/p/tmp/jamirp/esm_land_daily/daily_${Y0}_${Y1}_${SCENARIO}_${SRCTAG}_c${CELL}_${CELL}_seed1}"
if [ ! -f "$SRC/scripts_for_running_the_model/lpjml.js" ]; then
  echo "== generating the $SCENARIO config for cell $CELL (SUBMIT=no)"
  STARTGRID="$CELL" ENDGRID="$CELL" SCENARIO="$SCENARIO" NTASKS=1 RUNTAG="$SRCTAG" \
    SUBMIT=no RANDOM_SEED=1 bash "$REPO/scripts/run_daily_subset.sh" >/dev/null
  [ -f "$SRC/scripts_for_running_the_model/lpjml.js" ] || {
    echo "FATAL: expected a generated config at $SRC but found none" >&2; exit 3; }
fi

# ---- the transient boundary series (see the warning in the header) -------------------------------------
BCSV=""
if [ "$ARM" != REC ]; then
  case "$BOUNDARY" in
    static) BCSV="" ;;
    auto)
      BCSV="/p/tmp/jamirp/S_rung2/boundary/boundary_${SCENARIO}_c${CELL}.csv"
      [ -f "$BCSV" ] || "$PYTHON" "$REPO/scripts/build_rung2_boundary_series.py" \
          --cell "$CELL" --scenario "$SCENARIO" --out "$BCSV" >/dev/null
      [ -f "$BCSV" ] || { echo "FATAL: could not build a boundary series at $BCSV" >&2; exit 3; } ;;
    frozen)
      # The DRIFT control: the scenario's own years with the climate held at present day, so
      # `transient - frozen` is the arm's climate response with 61 years of drift differenced out.
      BCSV="/p/tmp/jamirp/S_rung2/boundary/boundary_${SCENARIO}frz_c${CELL}.csv"
      [ -f "$BCSV" ] || "$PYTHON" "$REPO/scripts/build_rung2_boundary_series.py" \
          --cell "$CELL" --scenario "$SCENARIO" --freeze --out "$BCSV" >/dev/null
      [ -f "$BCSV" ] || { echo "FATAL: could not build a frozen boundary series at $BCSV" >&2; exit 3; } ;;
    *) BCSV="$BOUNDARY"; [ -f "$BCSV" ] || { echo "no boundary series at $BCSV" >&2; exit 2; } ;;
  esac
fi

DST="/p/tmp/jamirp/esm_land_daily/daily_${Y0}_${Y1}_${SCENARIO}_${TAG}_c${CELL}_seed1"
APPLY="/p/tmp/jamirp/S_rung2/${TAG}_apply"
NEWDUMP="/p/tmp/jamirp/S_rung2/${TAG}_dump"

rm -rf "$DST" "$APPLY" "$NEWDUMP"
mkdir -p "$DST/output" "$DST/scripts_for_running_the_model" "$APPLY" "$NEWDUMP"
cp "$SRC/scripts_for_running_the_model/"*.js "$DST/scripts_for_running_the_model/"
for f in "$DST/scripts_for_running_the_model/"*.js; do sed -i "s|$SRC|$DST|g" "$f"; done

cat > "$DST/scripts_for_running_the_model/slurm.jcf" <<JCF
#!/bin/bash
#SBATCH --ntasks=1
#SBATCH --qos=${QOS}
#SBATCH --partition=${PARTITION}
#SBATCH -J ${TAG}
#SBATCH --time=${TIME}
#SBATCH -o $DST/lpjml.%j.out
#SBATCH -e $DST/lpjml.%j.err

source /etc/profile.d/00-modulepath.sh 2>/dev/null || true
source /etc/profile.d/modules.sh 2>/dev/null || true
module purge 2>/dev/null || true
module load intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1 openssl/3.6.0 netcdf-c curl/8.4.0 expat/2.5.0

export LPJROOT=/home/jamirp/lpjml56fit
export LPJOUTPATH=$DST
export LPJRESTARTPATH=$DST
export LPJ_RUNG2_DIR=$NEWDUMP
ulimit -c unlimited
JCF

if [ "$ARM" = REC ]; then
  # Observation hook only: no rendezvous, no harness.  This is the baseline the arms are scored against,
  # so it must exercise nothing the arms add — but it MUST run the same executable they do.
  cat >> "$DST/scripts_for_running_the_model/slurm.jcf" <<JCF

mpirun $BIN -DFROM_RESTART $DST/scripts_for_running_the_model/lpjml.js
RC=\$?
echo "=== lpjml rc=\$RC  arm=REC  scenario=$SCENARIO  cell=$CELL  dump=$NEWDUMP ==="
exit \$RC
JCF
  rmdir "$APPLY" 2>/dev/null || true
else
  cat >> "$DST/scripts_for_running_the_model/slurm.jcf" <<JCF
export LPJ_RUNG2_APPLY_DIR=$APPLY
export LPJ_RUNG2_APPLY_TIMEOUT=600

# The harness must be answering BEFORE the first rendezvous, or the C fails the whole run on the apply
# timeout.  Julia's load is seconds, not instant, so wait for its ready marker instead of sleeping a
# guessed interval.
cd $REPO
$JULIA --project=$REPO $REPO/scripts/rung2_s_demography_harness.jl \\
    --arm=$ARM --n-prev=$NPREV --seed=$SEED --cell=$CELL --drf=$DRF \\
    --boundary-csv=$BCSV \\
    --apply-dir=$APPLY --ready=$APPLY/harness.ready --max-idle=300 > $DST/harness.out 2>&1 &
HPID=\$!
for i in \$(seq 1 300); do
  [ -f "$APPLY/harness.ready" ] && break
  kill -0 \$HPID 2>/dev/null || { echo "FATAL: harness died before becoming ready"; cat $DST/harness.out; exit 9; }
  sleep 1
done
[ -f "$APPLY/harness.ready" ] || { echo "FATAL: harness not ready after 300 s"; cat $DST/harness.out; exit 9; }
echo "harness ready after \$i s"

mpirun $BIN -DFROM_RESTART $DST/scripts_for_running_the_model/lpjml.js
RC=\$?
sleep 2
kill \$HPID 2>/dev/null || true
wait \$HPID 2>/dev/null || true
echo "=== lpjml rc=\$RC  arm=$ARM  scenario=$SCENARIO  cell=$CELL  n_prev=$NPREV  seed=$SEED ==="
exit \$RC
JCF
fi

echo "arm=$ARM  scenario=$SCENARIO ($Y0-$Y1)  cell=$CELL  n_prev=$NPREV  seed=$SEED"
echo "  binary        : $BIN"
echo "  source config : $SRC"
echo "  run dir       : $DST"
[ "$ARM" = REC ] || echo "  count forest  : $DRF"
[ "$ARM" = REC ] || echo "  boundary      : ${BCSV:-STATIC (present-day climatology)}"
echo "  new dump      : $NEWDUMP"
[ "$ARM" = REC ] || echo "  rendezvous    : $APPLY"
if [ "$SUBMIT" = "yes" ]; then
  sbatch "$DST/scripts_for_running_the_model/slurm.jcf"
else
  echo "  (SUBMIT=no; sbatch $DST/scripts_for_running_the_model/slurm.jcf)"
fi
