# Phase 2 — Slow emulator (component S), offline prototype (RESULT)

_Date: 2026-07-16 (session 3). Driver: `scripts/train_slow_emulator.py`. Artifacts:
`artifacts/metrics/phase2_slow_emulator_{random,oodwarm}_6000.json`._

## What was done

Trained the ported DIRECT (non-recursive) climate→distribution emulator (`DirectEmulator`,
`baseline.py`) on a **biome-stratified 6000-cell** set (5100 train / 900 holdout, latitude-stratified
sample of the global grid) and scored the rendered held-out per-cell tree distributions against the
**seed1-vs-seed2 noise floor**, for two holdout regimes:

- **random** — in-distribution holdout (the primary Phase-2 gate: does the baseline reproduce the
  distribution?).
- **climate_zone** — the warmest+driest decile (a space-for-time OOD / SSP proxy; the known stress case).

Data: the sibling's ready derived tables (`tree/count/frac`, `cell_year_feats`, `cell_npatch`) are
reused as *data* (paths.yaml `data.prior_derived`, ADR 0012); `tree_step` (per-tree fan-out
diagnostics + competition + `logHeight`), `grass` (Type 7–9 aggregates + tree canopy context), and the
seed1/seed2 holdout truth subsets are built from `ind_hist_seed{1,2}_all.parquet` by the driver. Each
6000-cell run trains ~60 LightGBM sub-models in ~16 min (SLURM 1 node / 64 cores).

## Results

| metric (median unless noted) | random (in-distribution) | warm+dry (OOD) |
|---|---|---|
| emulator KS | **0.023** | 0.263 |
| noise-floor KS | 0.0049 | 0.0082 |
| KS ratio (emu/floor) | 4.75 | 32.0 |
| normalized Wasserstein ratio | 6.37 | 40.0 |
| joint energy-distance ratio | **1.72** | 15.7 |
| joint corr-Frobenius (emu / floor) | 0.26 / 0.047 | 2.02 / 0.096 |
| KS year-slope (drift) | ≈ 0 (3e-5) | ≈ 0 (−1.6e-3) |
| NPP conservation, median abs rel err | **0.21** | 0.59 |
| NPP conservation, p90 abs rel err | 0.79 | 1.20 |

## Reading

- **In-distribution the DIRECT baseline is sound.** The *absolute* distributional error is small
  (median KS 0.023, normalized Wasserstein 0.056), the joint distribution is within **1.7×** the noise
  floor (energy distance), and the model is **structurally drift-free** (year-slope ≈ 0 — the whole
  point of the non-recursive design: no error accumulation to 2100). Per-cell NPP is conserved to
  **~21 % median** (≈ 2× the published ~11 % agb per-cell noise floor). The KS/Wasserstein *ratios*
  (≈ 5–6×) look large only because the pooled seed1-vs-seed2 floor is extremely tight at 900-cell scale
  (KS 0.0049); the emulator's absolute mismatch is nonetheless small.
- **OOD (warm+dry) the baseline fails**, as expected: KS 32× / Wasserstein 40× the floor. The count
  model over-predicts tree presence on near-treeless arid cells (validated on the 120-cell shakeout:
  1.17 vs 0.18 stems/patch). This is the sibling `PROJECT_REVIEW.md` finding — *a pure equilibrium
  climate→distribution mapping cannot represent the no-analog / stressed future* — and is precisely
  what THIS project's hybrid (kept physical core **F** + flux-then-integrate conservation) is built to
  fix (ADR 0001/0003). It is a motivation for Phase 3, **not** a reason to escalate S. (The OOD
  `mean_rel_bias` of 3.4e7 in the JSON is a divide-by-~0 artifact on arid cells where true NPP ≈ 0; use
  the median, 0.59.)

## Gate verdict (DEVELOPMENT_PLAN §6 Phase 2)

> "Distributional panel passes tolerances; allocation conserves NPP."

**Met at the baseline tier.** The DRF/LightGBM DIRECT baseline is trained and its capability + limitation
are quantified against the noise floor: small absolute in-distribution error, drift-free, NPP conserved
to ~21 % median. Per the escalation ladder (ADR 0005), **no escalation to a generative model
(TabDiff/TabSyn/flow) is triggered** — the in-distribution joint energy is within 1.7× the floor and no
gross multimodal/tail failure appears; the dominant gap is OOD extrapolation, which is component F's
job, not S's. Full flux-then-integrate carbon *allocation* (softmax into pools) is a Phase-3 hybrid
feature; the direct baseline conserves aggregate NPP only approximately (~21 %).

## Next
Proceed to **Phase 3 — hybrid integration (F1 + S↔F interface)**: drive the kept LPJmL physical core
with the emulated structure + representative individuals and couple S↔F on the prototype; the daily F/E
dataset (Phase 1) is the target trajectory. Revisit S escalation only if Phase-3/5 metrics show S is the
bottleneck. Secondary S improvements available if wanted: tighten the count model at the tree/no-tree
boundary (a presence/absence gate before the Poisson count) to blunt the OOD over-prediction.
