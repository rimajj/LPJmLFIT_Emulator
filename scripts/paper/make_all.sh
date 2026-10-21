#!/usr/bin/env bash
# Rebuild every figure and the PDF of the emulator paper (docs/paper). Login node is fine (each step < 2 min),
# except run_daily_example.py, which must already have run on SLURM:
#   PARTITION=priority QOS=priority NCPUS=2 scripts/sbatch_python.sh paper-daily scripts/paper/run_daily_example.py
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY=/home/jamirp/.conda/envs/py311_new/bin/python
cd "$REPO/scripts/paper"
for f in fig_runtime fig_design fig_cell_example fig_structure fig_drift fig_daily_series fig_daily_scores \
         fig_response fig_global fig_speed; do
  "$PY" "$f.py"
done
source /etc/profile.d/00-modulepath.sh; source /etc/profile.d/modules.sh; module load texlive/2026
cd "$REPO/docs/paper/schematics"
for t in fig01_overview fig_designpath; do pdflatex -interaction=nonstopmode -halt-on-error "$t.tex" >/dev/null; cp "$t.pdf" ../figs/; done
cd "$REPO/docs/paper"
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex >/dev/null
echo "built $REPO/docs/paper/main.pdf"
