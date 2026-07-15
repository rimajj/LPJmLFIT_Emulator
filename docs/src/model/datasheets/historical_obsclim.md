# Datasheet — Historical (obsclim GSWP3-W5E5) ground truth

> *A dataset datasheet (after Gebru et al., "Datasheets for Datasets") for the **training-baseline**
> LPJmL-FIT ground-truth run. Provenance from `DESIGN.md` §4 and `config/paths.yaml`. Absolute paths
> are the source of truth; never hard-code them elsewhere.*

## Motivation

The present-day training baseline for the hybrid: LPJmL-FIT driven by observational climate over
2000–2019. Provides the annual trait/size ground truth for **S**, the annual `globalflux` for the
**carbon**-closure check (available now, no re-run), and — after the Phase-1 daily re-run — the
fast-core validation set for **F/E**.

## Composition

- **Model.** LPJmL-FIT, LPJmL v5.6.004, git `b2e5ca9` (`config/paths.yaml:lpjml`).
- **Domain / grid.** 0.5°, **67,420 cells** (verified three ways: `soil_code_test.soil.bin` = 67,420
  bytes; every metafile `"ncell":67420`; `lpjcheck`), of which **63,119 carry tree data**.
- **Ensemble.** `npatch = 25` patches/cell (the RNG-seed-driven within-cell ensemble that S targets),
  two random seeds — **seed1 + seed2 are the noise-floor pair**.
- **Period.** Transient **2000–2019** (20 years), continued from a 1000-year spin-up
  (`nspinup=1000, nspinyear=30, shuffle_climate:true`).
- **Forcing (obsclim GSWP3-W5E5, ISIMIP3a; daily, noleap, 1901–2019):** `tas` (temperature), `pr`
  (precipitation), `lwnet` (net longwave, **downward-positive**), `rsds` (shortwave), `huss` (specific
  humidity — a hard dependency via VPD). CO₂ = TRENDY v12 (`global_co2_ann_1700_2022.txt`). Exact
  files in `config/paths.yaml:lpjml.inputs.historical`.
- **Key output tables (schemas frozen, `DESIGN.md` §3):** the `ind` individual-tree CSV = **29
  columns** (one row per living individual per year; carbon exposed only as `agb`/`vegc` — the
  disaggregated per-tree pools are commented out in the writer); `globalflux` CSV = 17–20 columns with
  **all carbon-closure fluxes present** (`estab`, `fire`, `NBP`).

## Collection process

Generated on the PIK cluster (Intel MPI) via the production run scripts
(`config/paths.yaml:lpjml.run_scripts_dir`), which write `input_*.js` + `lpjml_*.js` + `slurm_*.jcf`
and submit a spin-up → transient dependency chain. Modules:
`config/hpc_slurm.yaml:modules.lpjml_build_run`. **This data already exists on disk** (annual output
only); paths in `config/paths.yaml:lpjml.ground_truth.historical_seed{1,2}`.

## Sizes

- `ind` CSV ≈ **44 GB per seed** (20 years).
- Restart files ≈ **128 GB** each. **Critical distinction** (`config/paths.yaml`): `restart_1999.lpj`
  = spin-up end (use this to reproduce the 2000–2019 trajectory in a daily re-run); `restart_2019.lpj`
  = historical end (only the start of the SSP370 continuation).

## Preprocessing / derived tables

The sibling emulator has already materialised derived per-cell parquet feature/target tables (63,119
cells) at `config/paths.yaml:data.prior_derived` (`/p/tmp/jamirp/emulator_global`) — **reuse these**
rather than re-extracting
([ADR 0011](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0011-reuse-global-ground-truth.md)).
Derive offline: `Ra = GPP − NPP`, `LE = λ·ET`, `ET = transp + evap + interc + snow-sublimation`.

## Uses

- **Now:** train aggregate (Tier-1) S; verify the **carbon** budget closes on annual `globalflux`.
- **After the Phase-1 daily re-run** (config-only, restart from `restart_1999.lpj`, same seed/domain/
  `npatch`/binary): the fast-core validation set (daily fluxes + pool states) and the **water** budget
  check. For per-tree pools (Tier-2 S), add a RAW-format `ind` output.
- **Do not** use for CO₂-fertilization signals — CO₂ varies here historically but the *application*
  regime holds CO₂ constant ([SSP370 datasheet](ssp370.md)).

## Distribution & maintenance

Internal PIK storage (`/p/projects/waldspektrum/...`, `/p/tmp/jamirp/...`); **not** committed to git
(the `.gitignore` blocks `.clm/.nc/.bin/.parquet`), tracked instead via DVC pointers. Reproducibility
ledger per [Reproduce a result](../../howto/reproduce.md).
