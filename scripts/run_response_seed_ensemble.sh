#!/usr/bin/env bash
# =============================================================================
# run_response_seed_ensemble.sh — submit a SEED ENSEMBLE of the Phase-3A response
# 2x2 (`trait_mortality_arm_probe.jl MODE=response`) for ONE artifact pair.
#
# WHY THIS EXISTS (ADR 0101). The 2x2 double difference
#   interaction = [wd(arm,ssp) - wd(arm,hist)] - [wd(ctl,ssp) - wd(ctl,hist)]
# is a difference of four SMALL-SAMPLE stochastic rollouts: ~17 initial cohorts at
# Hainich plus a few tens of copula-drawn recruits over 81 years. Its SEED spread is
# 0.67-1.74x the FIT reference shift — i.e. the SAME SIZE AS THE EFFECT. A single-seed
# read is one draw, not a measurement, and ADR 0100's +1.40x was exactly that (it sits
# 0.03 from its own artifact's 8-seed mean, so it was a FAIR draw whose stated
# precision was ~6x too good). Holding the seed common across the four corners does
# NOT pair them: the rosters diverge after year 1, so the seed stream is consumed
# differently in each corner and the noise does not cancel.
#
# ⇒ NEVER quote a response number from one seed. Run this, then summarize with
#   scripts/summarize_response_seed_ensemble.py, and quote mean +/- SEM with n.
#
# Power, measured (ADR 0101): with sd ~1.0x FIT, ~8 seeds resolve a 1x-FIT effect at
# 80 % power, ~115 resolve the 0.26x that was actually measured. 12 is the practical
# default: enough to exclude 1x, not enough to confirm 0.26x.
#
# Usage:
#   scripts/run_response_seed_ensemble.sh <TAGPREFIX> [NSEEDS]
# Env (all forwarded to the probe; see its header):
#   DRF_ART/RCOP_ART  the artifact pair (default = the committed Hainich demo pair)
#   N_INIT/AGE0       per-cell count/age seeds — REQUIRED for a global artifact, whose
#                     meta keeps them in a cell_meta.parquet sidecar. ⚠ ADR 0101: the
#                     POOLED artifact ships NO cell_meta at all and its two sub-tables
#                     disagree at Hainich (11.0/43.556 vs 7.0/46.0); the 7.0 branch
#                     fires hard kills and swings the interaction by 4.5x FIT, so state
#                     which one you used and check the hard-kill count is 0.
#   BOUNDARY          "gdd5 tcm soil_depth co2" for THIS cell (global artifact only)
#   K_CAP             raise until the merge count is 0 (ADR 0048/0100); 400 at Hainich
#   SCORE_WINDOW      20 (ADR 0100)
# Collect:
#   scripts/summarize_response_seed_ensemble.py 'logs/<TAGPREFIX>*.out'
# =============================================================================
set -euo pipefail

TAGPREFIX="${1:?usage: run_response_seed_ensemble.sh <TAGPREFIX> [NSEEDS]}"
NSEEDS="${2:-12}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "submitting ${NSEEDS} seeds, tag prefix ${TAGPREFIX}"
echo "  drf  = ${DRF_ART:-<committed Hainich demo>}"
echo "  rcop = ${RCOP_ART:-<committed Hainich demo>}"
echo "  n_init=${N_INIT:-<from meta>} age0=${AGE0:-<from meta>} k_cap=${K_CAP:-<production default>}"
for sd in $(seq 1 "${NSEEDS}"); do
    # WARMUP only on the first submission — the login-node Pkg.instantiate is idempotent
    # but costs ~20 s, and every seed shares one depot.
    SEED="${sd}" MODE=response WARMUP="$([ "${sd}" -eq 1 ] && echo 1 || echo 0)" \
        "${REPO}/scripts/sbatch_julia.sh" "${TAGPREFIX}${sd}" \
        --project=. scripts/trait_mortality_arm_probe.jl 2>&1 | grep -E '^  log:' || true
done
echo
echo "when squeue drains:  scripts/summarize_response_seed_ensemble.py 'logs/${TAGPREFIX}*.out'"
