#!/bin/bash
# run_rung2_response_matrix.sh — submit the whole rung-2 WARMING-RESPONSE experiment (line S).
#
# THE DELIVERABLE.  Not "how close is the emulator's demography at present day" (ADR 0176 answered that at
# one cell) but "does it MOVE THE RIGHT WAY, AND BY THE RIGHT AMOUNT, when the climate warms".  For each
# cell the experiment runs BOTH legs of the scenario pair under the same demography and compares the
# CHANGE between them against FIT's own change:
#
#     response(arm, cell) = terminal(arm, ssp370) - terminal(arm, historic)
#     truth(cell)         = terminal(REC, ssp370) - terminal(REC, historic)
#
# Per ADR 0041 a single-cell re-run may NOT be scored against the global ground truth, which is why every
# cell gets its own `ARM=REC` baseline in EACH scenario rather than borrowing the global run's numbers.
#
# WHAT IS SUBMITTED, per cell and per scenario:
#   REC              1 run   the per-cell, per-scenario recorded baseline (the reference basis)
#   NP               1 run   the PERSISTENCE null. ONE seed on purpose: rho = 1 never reaches `rand`, so
#                            its seeds are provably identical (ADR 0176 verified this with
#                            diagnose_rung2_dump_equality.py). Running 5 would be 4 duplicate jobs.
#   S0, S0h, S1      SEEDS each   the shipped uniform thinning, the decomposition control, and the trait
#                            ordering. ADR 0176: reporting only S0 and S1 MIS-ATTRIBUTES the result — 85 %
#                            of S1's advantage is "stop overriding deaths the C had settled", which is
#                            exactly what S0h isolates. Never drop S0h to save jobs.
#
# so 2 + 3*SEEDS runs per cell-scenario, x 2 scenarios x the cells in the committed set.
#
# Env knobs:
#   CELLS    comma-separated cell list   (default: the committed S_rung2_response_cells.csv)
#   SEEDS    seeds per stochastic arm    (default: 5, matching ADR 0176)
#   ARMS     arms to run                 (default: "REC NP S0 S0h S1")
#   SCEN     scenarios                   (default: "historic ssp370")
#   MAXQ     max of MY jobs in flight    (default: 40 — four lines share this account and queue)
#   SUBMIT   yes | no                    (default: yes; no = print the plan and exit)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON=/home/jamirp/.conda/envs/py311_new/bin/python
CELLS_CSV="$REPO/test/testitems/references/S_rung2_response_cells.csv"
SEEDS="${SEEDS:-5}"
ARMS="${ARMS:-REC NP S0 S0h S1}"
SCEN="${SCEN:-historic ssp370}"
MAXQ="${MAXQ:-40}"
# BOUNDARY is forwarded verbatim to the arm runner. `frozen` runs the DRIFT CONTROL: the same scenario
# years with the climate held at present day, so (transient - frozen) is the arm's climate response with
# 61 years of free-running drift differenced out. REC is meaningless there — the C always sees the real
# forcing, so there is no such thing as a frozen-climate baseline run — and it is dropped automatically.
BOUNDARY="${BOUNDARY:-auto}"
SUBMIT="${SUBMIT:-yes}"

if [ -n "${CELLS:-}" ]; then
  CELL_LIST="${CELLS//,/ }"
else
  [ -f "$CELLS_CSV" ] || { echo "no cell set at $CELLS_CSV (run scripts/select_rung2_response_cells.py)" >&2; exit 2; }
  CELL_LIST="$(awk -F, '!/^#/ && NR>0 && $1!="Cell" {print $1}' "$CELLS_CSV" | tr '\n' ' ')"
fi
NCELL=$(echo "$CELL_LIST" | wc -w)

# ---- pre-build every boundary series in ONE python call ------------------------------------------------
# 30 separate interpreter starts each re-scanning a 5.5 M-row parquet is minutes of pure overhead, and a
# missing series is the one failure that would silently fall back to a frozen present-day climate.
if [ "$SUBMIT" = "yes" ]; then
  BLIST="$(echo "$CELL_LIST" | tr ' ' ',' | sed 's/,$//')"
  for s in $SCEN; do
    echo "== building the $s boundary series for $NCELL cells"
    FRZ=""; [ "$BOUNDARY" = frozen ] && FRZ="--freeze"
    "$PYTHON" "$REPO/scripts/build_rung2_boundary_series.py" \
      --cells "$BLIST" --scenario "$s" $FRZ --outdir /p/tmp/jamirp/S_rung2/boundary | tail -3
  done
fi

njob=0
for cell in $CELL_LIST; do
  for scen in $SCEN; do
    for arm in $ARMS; do
      if [ "$BOUNDARY" = frozen ] && [ "$arm" = REC ]; then continue; fi
      if [ "$arm" = REC ] || [ "$arm" = NP ]; then seeds="1"; else seeds="$(seq 1 "$SEEDS")"; fi
      for sd in $seeds; do
        njob=$((njob + 1))
        if [ "$SUBMIT" != "yes" ]; then
          echo "  would submit: cell=$cell scen=$scen arm=$arm seed=$sd"
          continue
        fi
        # Throttle on MY OWN jobs only (name prefix), so a sibling line's queue neither stalls this
        # submission loop nor is flooded by it — four lines share one account and one queue.
        while [ "$(squeue -u "$USER" -h -o '%j' | grep -c '^S_r2s_')" -ge "$MAXQ" ]; do sleep 10; done
        ARM="$arm" SCENARIO="$scen" CELL="$cell" SEED="$sd" BOUNDARY="$BOUNDARY" SUBMIT=yes \
          bash "$REPO/scripts/run_rung2_s_arm.sh" >/dev/null 2>&1 || {
            echo "FAILED to submit cell=$cell scen=$scen arm=$arm seed=$sd" >&2; }
      done
    done
  done
  echo "== cell $cell submitted ($njob jobs so far)"
done

echo "== $njob job(s) over $NCELL cell(s), scenarios: $SCEN, arms: $ARMS, seeds: $SEEDS"
[ "$SUBMIT" = "yes" ] && echo "   watch: squeue -u $USER -o '%.10i %.40j %.9T %.10M' | grep S_r2s_"
exit 0
