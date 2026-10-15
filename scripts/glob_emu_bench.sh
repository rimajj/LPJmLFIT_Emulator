#!/usr/bin/env bash
# glob_emu_bench.sh prep|lpjmlstats|ilamb -- ADR 0341: the lpjml-fit benchmark tools (ILAMB + lpjmlstats, /home/jamirp/
# lpjml-fit/scripts/benchmark, used UNCHANGED) on FULL-GRID runs: the original (Billing's GFDL-ESM4 r1_1, Oct-2026
# build) against the retrained learned emulator, all 67 420 cells, no clusters (owner 2026-10-15).
#
# Models (scripts/glob_emu.py layout + assemble write bench/models/<m>/chunk_0/output/<fitname>_<phase>.nc, which the
# converter's `chunks:` source reads):
#   FIT   the original: historical output/ 1985-2014; futures output/ 2071-2100 (the run with the per-tree table)
#   Emu   the emulator: historical 1985-2014 (deployment fit), futures 2015-2100 (each by the fold that never saw it)
#   FIT2  the original's OTHER 2071-2100 realisation (futures output_transient/; same 2070 state, chaotic divergence
#         after) -- the size of a difference the original makes with itself. No stand leaf area in it.
# Periods: historical 1985-2014 (lpjmlstats + ILAMB), ssp126/ssp245/ssp370 2071-2100 (lpjmlstats).
# lpjmlstats drops a variable unless every model has it, so the futures get a second report with leaf area (FIT, Emu)
# and the two are joined with pdfunite (the lpjml-fit k674 drivers do the same).
set -euo pipefail
LF=/home/jamirp/lpjml-fit/scripts/benchmark
PY=/home/jamirp/.conda/envs/py311/bin/python3          # has netCDF4 (the converter's documented interpreter)
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH=/p/projects/open/Jamir/esm_land_emulator_data/global_emu/bench
VARS=mgpp,mnpp,mtransp,mevap,minterc,mrunoff,vegc,lai,fpc
VARS2=mgpp,mnpp,mtransp,mevap,minterc,mrunoff,vegc,fpc
IVARS=gpp,npp,et,runoff,biomass,lai,treeFrac
FUT="ssp126 ssp245 ssp370"

prep() {  # prep [historical|futures] (default both)
  local which=${1:-both}
  [ "$which" = futures ] || for m in FIT Emu; do
    "$PY" "$LF/prepare_benchmark.py" "chunks:$BENCH/models/$m" --unreduced --phase historical \
      --lpjmlstats "$BENCH/lpjmlstats/historical/$m" --vars "$VARS" --years 1985 2014
    "$PY" "$LF/prepare_benchmark.py" "chunks:$BENCH/models/$m" --unreduced --phase historical \
      --ilamb "$BENCH/ilamb/MODELS/$m" --vars "$IVARS"
  done
  [ "$which" = historical ] || for s in $FUT; do
    for m in FIT Emu; do
      "$PY" "$LF/prepare_benchmark.py" "chunks:$BENCH/models/$m" --unreduced --phase "$s" \
        --lpjmlstats "$BENCH/lpjmlstats/$s/$m" --vars "$VARS" --years 2071 2100
    done
    "$PY" "$LF/prepare_benchmark.py" "chunks:$BENCH/models/FIT2" --unreduced --phase "$s" \
      --lpjmlstats "$BENCH/lpjmlstats/$s/FIT2" --vars "$VARS2" --years 2071 2100
    # leaf area only (FIT2 has none): FITl / Emul hold lai + the grid files
    for m in FIT Emu; do
      d="$BENCH/lpjmlstats/$s/${m}l"; mkdir -p "$d"
      for f in lai.bin lai.bin.json grid.bin grid.bin.json terr_area.bin terr_area.bin.json; do
        [ -e "$d/$f" ] || ln -s "$BENCH/lpjmlstats/$s/$m/$f" "$d/$f"
      done
    done
  done
}

lpjmlstats() {
  local L=$BENCH/lpjmlstats J=()
  sub() {  # <y0> <y1> <out.pdf> <label=dir>...
    local y0=$1 y1=$2 out=$3; shift 3
    LPJMLSTATS_Y0=$y0 LPJMLSTATS_Y1=$y1 \
      LPJMLSTATS_NOTE="(TEXT ABOVE IS THE TEMPLATE'S: here every model is a FULL 67 420-cell run, no clusters; ADR 0341)" \
      sbatch --parsable --job-name=glob-lpjmlstats --output="$REPO/logs/glob-lpjmlstats.%j.out" "$LF/lpjmlstats.sh" \
      "$out" "$@"
  }
  J+=("$(sub 1985 2014 "$L/report_historical.pdf" FIT="$L/historical/FIT" Emu="$L/historical/Emu")")
  for s in $FUT; do
    J+=("$(sub 2071 2100 "$L/part_${s}_main.pdf" FIT="$L/$s/FIT" Emu="$L/$s/Emu" FIT2="$L/$s/FIT2")")
    J+=("$(sub 2071 2100 "$L/part_${s}_lai.pdf" FIT="$L/$s/FITl" Emu="$L/$s/Emul")")
  done
  echo "lpjmlstats jobs: ${J[*]}"
}

ilamb() {
  BM=$BENCH TITLE="LPJmL-FIT (Billing GFDL-ESM4 r1_1, Oct-2026 build) vs the learned emulator, full grid 1985-2014" \
    sbatch --parsable --job-name=glob-ilamb --output="$REPO/logs/glob-ilamb.%j.out" "$LF/ilamb.sh"
}

case "${1:-}" in
  prep) prep "${2:-both}" ;;
  lpjmlstats) lpjmlstats ;;
  ilamb) ilamb ;;
  join) for s in $FUT; do pdfunite "$BENCH/lpjmlstats/part_${s}_main.pdf" "$BENCH/lpjmlstats/part_${s}_lai.pdf" \
          "$BENCH/lpjmlstats/report_${s}.pdf"; done ;;
  *) echo "usage: $0 prep|lpjmlstats|ilamb|join"; exit 2 ;;
esac
