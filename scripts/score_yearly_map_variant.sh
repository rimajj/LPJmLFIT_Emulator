#!/bin/bash
# score_yearly_map_variant.sh <suffix> [fit args...] -- every score of one yearly forest-map variant (ADR 0349-0352),
# reading xpanel/eval/yearly/preds_<g><suffix>.parquet for the five held-out climate models:
#   drift (explore_panel_yearly_drift.py score, ADR 0330), relaxed standard (final_structure_score.py, ADR 0340),
#   drought die-offs (diagnose_extreme_year_legacy.py, ADR 0350), start-error test (retention stage, ADR 0352).
# The fit args must be the ones the variant was fitted with (they rebuild its suffix), e.g.
#   scripts/score_yearly_map_variant.sh _recentx10_statelag_fx --recent x10 --state lag
# Compare afterwards with: python scripts/compare_structure_variants.py <ref_suffix> <suffix> ...
# Seconds to a few minutes; submit with scripts/sbatch_python.sh-style SLURM (it is run inside a job by the chains).
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY=${PY:-/home/jamirp/.conda/envs/py311_new/bin/python}
SUF="${1:?usage: score_yearly_map_variant.sh <suffix> [fit args...]}"; shift
cd "$REPO"
echo "### variant ${SUF} (fit args: $*)"
$PY scripts/explore_panel_yearly_drift.py score "$@"
SUFFIX="$SUF" $PY scripts/final_structure_score.py
SUFFIX="$SUF" $PY scripts/diagnose_extreme_year_legacy.py
$PY scripts/explore_panel_yearly_drift.py retention "$@"
echo "### done ${SUF}"
