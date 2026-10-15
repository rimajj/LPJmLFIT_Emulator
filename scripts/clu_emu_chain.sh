#!/bin/bash
# clu_emu_chain.sh <seed-2 leg job ids, colon-separated> <seed-3 leg job ids> <climate job id>
# -- the processing chain of ADR 0342 after the original-model runs, each step afterany/afterok-chained:
#   targets s2 + f2 arrays s2  (afterany: a failed leg is skipped and reported, not a stalled chain)
#   maps train main / wrong -> predict -> emulated-stand arrays
#   daily model: 5 members (GPU, CO2 input, trained on the 8 training climate models' 32 legs, every cell but the
#                held-out 20 %) -> phase A (original stand) and phase B (emulated stand) free runs + scores
#   targets s3 + f2 arrays s3 (the second run) -> maps score
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
P=/home/jamirp/.conda/envs/py311_new/bin/python
S2=${1:?seed-2 leg jobs}; S3=${2:?seed-3 leg jobs}; CL=${3:?climate job}
F2N=/p/projects/open/Jamir/esm_land_emulator_data/f2_non
TRAIN_GCMS="gfdl-esm4 mri-esm2-0 ukesm1-0-ll canesm5 cnrm-cm6-1 cnrm-esm2-1 ec-earth3 miroc6"
LEGS=$(for g in $TRAIN_GCMS; do for t in ssp126 ssp370 ssp585 ssp370co2fix; do echo -n "${g}_$t,"; done; done)
LEGS=${LEGS%,}
cpu() {  # <tag> <dependency> <ncpus> <mem> <time> <command...>
  local tag=$1 dep=$2 n=$3 mem=$4 t=$5; shift 5
  sbatch --parsable --job-name="emu-$tag" --account=waldspektrum --partition=priority --qos=priority \
    --cpus-per-task="$n" --mem="$mem" --time="$t" ${dep:+--dependency=$dep} --kill-on-invalid-dep=yes \
    --output="$REPO/logs/emu-$tag.%j.out" --wrap "cd $REPO; $*; echo === JOB DONE exit=\$? ==="
}
gpu() {
  local tag=$1 dep=$2; shift 2
  sbatch --parsable --job-name="emu-$tag" --account=waldspektrum --partition=gpu --qos=gpushort --gres=gpu:1 \
    --cpus-per-task=32 --time=12:00:00 ${dep:+--dependency=$dep} --kill-on-invalid-dep=yes \
    --output="$REPO/logs/emu-$tag.%j.out" --wrap "cd $REPO; $*; echo === JOB DONE exit=\$? ==="
}
T2=$(cpu clu-targets-s2 "afterany:$S2" 8 120G 03:00:00 $P scripts/clu_emu_maps.py targets --seed 2)
B2=$(cpu clu-f2build-s2 "afterany:$S2:$CL" 8 200G 03:00:00 $P scripts/clu_emu_f2.py build --seed 2)
TM=$(cpu clu-train-main "afterok:$T2:$CL" 32 200G 03:00:00 $P scripts/clu_emu_maps.py train --arm main)
TW=$(cpu clu-train-wrong "afterok:$T2:$CL" 32 200G 03:00:00 $P scripts/clu_emu_maps.py train --arm wrong)
PM=$(cpu clu-pred-main "afterok:$TM" 8 100G 01:00:00 $P scripts/clu_emu_maps.py predict --arm main)
PW=$(cpu clu-pred-wrong "afterok:$TW" 8 100G 01:00:00 $P scripts/clu_emu_maps.py predict --arm wrong)
SB=$(cpu clu-standB "afterok:$PM:$B2" 8 60G 01:00:00 $P scripts/clu_emu_f2.py standB --arm main)
MEM=""
for i in 0 1 2 3 4; do
  j=$(gpu clu-daily-m$i "afterok:$B2" $P scripts/f2_train.py --tag NC_s$i --seed $i --data-dir $F2N --members 2 --co2 \
      --hidden 256 --layers 3 --npp-head ra --deep-tau 365 --drop-inputs huss --train-legs "$LEGS" --test-legs none \
      --train-only)
  MEM="$MEM:$j"
done
T3=$(cpu clu-targets-s3 "afterany:$S3" 8 60G 02:00:00 $P scripts/clu_emu_maps.py targets --seed 3)
B3=$(cpu clu-f2build-s3 "afterany:$S3:$CL" 8 120G 02:00:00 $P scripts/clu_emu_f2.py build --seed 3)
SC=$(cpu clu-score-maps "afterok:$PM:$PW:$T3" 8 60G 01:00:00 $P scripts/clu_emu_maps.py score)
NETS=NC_s0,NC_s1,NC_s2,NC_s3,NC_s4
RA=$(gpu clu-daily-runA "afterok$MEM:$B3" $P scripts/clu_emu_f2.py run --tag NC_A --members $NETS --co2)
RB=$(gpu clu-daily-runB "afterok$MEM:$B3:$SB" $P scripts/clu_emu_f2.py run --tag NC_B --members $NETS --co2 \
     --stand-dir stand_emul_main)
echo "targets s2 $T2 | f2 s2 $B2 | train main $TM wrong $TW | predict $PM $PW | standB $SB | daily members${MEM//:/ }"
echo "targets s3 $T3 | f2 s3 $B3 | score maps $SC | daily runs A $RA B $RB"
