# How to reproduce a result

> *Goal-oriented how-to. Reproducibility is mandatory (ENGINEERING_STANDARDS §7; `00_START_HERE.md`
> rule 8). Every result must be re-derivable from a git commit + a config.*

## The principle

Nothing is transcribed by hand. A result is a function of: the **code commit**, the **config**
(`config/*.yaml` — no magic numbers, no hard-coded paths), the **input data version**, and the
**random seeds**. Log all four and any result can be regenerated.

## The reproducibility ledger (log per dataset)

Record these for every generated dataset (`DESIGN.md` §4.4):

| Item | Value / source |
|---|---|
| LPJmL-FIT commit / version | `b2e5ca9` / v5.6.004 (`config/paths.yaml:lpjml.git_commit`) |
| Config JS | `lpjmlfit.js` + the generated `lpjml_*.js` |
| Input `.clm` + CO₂ | the exact files in `config/paths.yaml:lpjml.inputs` |
| RNG seed | `random_seed` (1 and 2 = the noise-floor pair) |
| Patches / spin-up | `npatch = 25`; `nspinup = 1000`, `nspinyear = 30` |
| Modules | `config/hpc_slurm.yaml:modules.lpjml_build_run` |
| Python/ML seed | **42** (fixed everywhere) |

## Julia (the package)

- **Commit `Project.toml` *and* `Manifest.toml`.** This is an application/experiment repo → the
  Manifest is pinned so the exact dependency graph is reproducible (ENGINEERING_STANDARDS §7;
  [ADR 0007](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0007-julia-primary-stack.md)).
- **`StableRNGs.jl`** for all stochastic code — the default Julia RNG streams are not stable across
  versions, so tests would be flaky otherwise.
- **`DrWatson.jl`** for config-driven runs: `tagsave` stamps every saved result with the git commit
  (and the patch, if the tree is dirty), so any artifact is reproducible by checkout.

## Python (the S prototype)

Reuse the existing environment — **do not create a new one** (`config/hpc_slurm.yaml:python_env`):

```bash
module load anaconda && source activate py311_new     # Python 3.11.9
# key: lightgbm 4.6.0, xgboost 3.2.0, copulas 0.14.1, polars 1.33.1, pyarrow 23.0.1, torch 2.5.1+cu124
```

Pin with a `uv` lockfile; fixed seed 42; lint/format with Ruff.

## Data & experiment provenance

- **DVC** tracks datasets/model weights as git-tracked pointers to remote storage — never commit
  `.clm`/`.nc`/`.parquet`/weights (the `.gitignore` enforces this).
- **MLflow** tracks experiment params/metrics so reports *query* the numbers live rather than pasting
  them.
- Reuse the sibling emulator's derived parquet tables (63,119 cells) and its noise-floor yardstick
  where possible (`config/paths.yaml:data.prior_derived`,
  [ADR 0011](https://github.com/rimajj/LPJmLFIT_Emulator/blob/main/docs/decisions/0011-reuse-global-ground-truth.md)).

## Reproduce the docs

The documentation itself is reproducible: `julia --project=docs docs/make.jl` re-runs every doctest,
`@example`, and code-derived diagram from the pinned environment — see
[Build the documentation](build_docs.md).
