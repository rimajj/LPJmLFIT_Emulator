# `data/` — DVC-tracked, never in git

**No data, model weights, or LPJmL restarts are committed to git** (`.gitignore` + `.dvcignore`).
This directory holds only **DVC pointer files** (`*.dvc`) and this README; the bytes live on remote
storage / the PIK filesystem and are pulled with `dvc pull`.

## Where the real data lives (resolved in `config/paths.yaml`)

- **LPJmL-FIT ground truth** (annual `ind` CSV, `globalflux`, restarts): under
  `/p/projects/waldspektrum/priesner/clustering/global/` (Historical obsclim 2000–2019 seed1+seed2;
  SSP370 MPI-ESM1-2-HR 2020–2100). 67,420-cell 0.5° grid; ~44–180 GB `ind` files; ~120 GB restarts.
- **Daily-output re-run** (Phase 1, to be generated): `/p/tmp/jamirp/esm_land_daily`.
- **Sibling emulator derived tables** (reusable): `/p/tmp/jamirp/emulator_global`.
- **Energy-closure reference** (FLUXNET/PLUMBER2, Phase 4): to be acquired.

## Layout (git-ignored except pointers)

```
data/
├── raw/         # immutable source extracts (DVC)
├── interim/     # intermediate (DVC)
└── processed/   # model-ready tables: slow_emulator_table, fast_core_validation (DVC)
```

## Reproducibility

- Every generated dataset logs the exact LPJmL-FIT commit (`b2e5ca9`, v5.6.004), config JS, input
  `.clm` files, and RNG `random_seed` (see `MEMORY.md` §4 and `DESIGN.md` §4.4).
- Julia experiments use **DrWatson** `tagsave` (stamps the git commit on every saved result);
  Python uses fixed seed 42 and (later) **MLflow** for param/metric tracking.
