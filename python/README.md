# `lpjmlfit-emulator-proto` — slow distributional emulator (component S), Python prototype

Python-first **prototype** of the LPJmL-FIT **slow trait/size distribution emulator**
(component **S**). S emulates the per-cell object `p(traits, size | drivers, state)`
over trees plus the tree count `N` — the scientific novelty of the project
(see repo-root `DESIGN.md` §"S's target object" and `README.md`).

## Role of this package (Python-first, then ported to Julia/Lux)

Per repo-root `ECOSYSTEM_AND_COUPLING.md` §"Framework: pivot to Julia-first", the
**target ESM stack is Julia + Enzyme AD end-to-end**. The fast differentiable core (F)
and the coupled, online-trainable system are built in Julia (Enzyme.jl, Lux.jl/Flux.jl,
SciML, KernelAbstractions). The **slow emulator S is prototyped here in Python** because
the relevant methods (LightGBM, Gaussian copula, DRF, tabular diffusion) are Python-mature,
and is then **ported to Julia/Lux.jl for the coupled system**. This package is therefore a
maturity/experimentation vehicle, not the production coupling code.

- **Baseline method:** LightGBM (marginals/conditioning) + **Gaussian copula** (joint
  dependence). No neural nets / diffusion unless the metric panel demands escalation.
- **Fixed seed 42** for all stochastic work (determinism gate, `ENGINEERING_STANDARDS.md` §2/§7).

## Running: REUSE the existing conda env (do not create a new one)

All runs use the already-provisioned env **`/home/jamirp/.conda/envs/py311_new`**
(Python 3.11.9; numpy, scipy, pandas, polars, pyarrow, scikit-learn, lightgbm 4.6.0,
xgboost 3.2.0, copulas 0.14.1, xarray, netcdf4, matplotlib, torch 2.5.1). Do **not**
build a new environment to run the prototype.

```bash
module load anaconda
source activate py311_new

# run the tests against the reused env (from the repo root):
python -m pytest python/tests -q
```

> Note: `hypothesis` may not be installed in `py311_new`. The property-based tests are
> written to **skip gracefully** (not fail) when Hypothesis is absent; the plain pytest
> cases always run. Install the dev group (below) to enable them.

## `pyproject.toml` / `uv.lock` are for reproducible CI + lockfile only

The `pyproject.toml` (build backend **hatchling**) and the **committed `uv.lock`** pin an
exact, reproducible dependency set for CI and archival reproducibility
(`ENGINEERING_STANDARDS.md` §7). Runtime deps carry **upper-bound caps** (e.g. `pandas<3`,
`pyarrow<25`, `pytest<9`, `ruff<0.15`) so a floating resolve can't pull a breaking major; the
`python` CI job runs `uv sync --frozen`. They are **not** the way you run day-to-day work here
— that is the reused conda env above. To exercise the locked env / regenerate the lock on a
machine **with network** (not in the offline HPC job):

```bash
uv sync --frozen     # install exactly uv.lock (CI's command); drop --frozen to re-resolve
uv run pytest -q     # runs the suite in the locked env
uv run ruff check .  # lint (E,F,I,UP,B); uv run ruff format --check .
uv lock              # re-resolve + rewrite uv.lock after editing pyproject deps
```

Runtime deps mirror `py311_new`; dev group = `pytest`, `pytest-cov`, `hypothesis`, `ruff`.
Config: Ruff (line-length 100, target py311, select `E,F,I,UP,B`), pytest
(`testpaths=["tests"]`, `addopts="-q"`, `pythonpath=["src"]`). Hypothesis has no native
pyproject table; its deterministic profile (`derandomize=True`, `deadline=None`) is
registered in `conftest.py`.

## Ported once from the (now-frozen) sibling emulator — single source of truth

Component **S** was **ported once on 2026-07-16** from the prior sibling project
**`/p/projects/open/Jamir/emulator`** (newest sibling source mtime 2026-07-14). **This repo is
now the single source of truth for S**; the sibling is **frozen** — it is not a dependency,
submodule, or sync target, and it is never edited or re-imported (ADR
`docs/decisions/0012-canonical-slow-emulator-here.md`). What was ported, and from where:

| this package | ported from (sibling `src/`) |
| --- | --- |
| `metrics.py` | `metrics.py` (full metric library + noise floor) |
| `transforms.py` | `transforms.py` |
| `drivers.py` | `parse_drivers.py` (generalized; xarray guarded) |
| `features.py` | `direct_features.py` + `eco_features.py` (climclusterpy/NetCDF guarded) |
| `baseline.py` | `direct_emulator.py` + (`ResidualRegressor`, `add_competition`, `LGB_COMMON` from `ibm_model.py`) |
| `train.py` | `direct_train_eval.py` (generalized; matplotlib guarded) |
| `data.py` | frozen 29-col schema (DESIGN.md §3.1) + `build_patch_summaries` from `data_prep.py` |

Intentionally **not** ported (abandoned/one-off; see ADR 0012): `ibm_model.IBMEmulator`,
`train_baseline.py`, `direct_zone*`, `direct_scale_eval`, `phaseF/H_*`, `shap_analysis`, `eda`,
`moving_normals`, `ssp_*`, `g1/g2*`, `make_global_split`, `global_*`, `convert_to_parquet`, `infer.py`.
Trained models (`models/*`, 262 MB–1.1 GB) and any dataset/parquet/`.clm`/`.lpj` are **never** copied.

- **Noise-floor discipline** — the **seed1-vs-seed2 noise floor** is the yardstick, not zero
  error (published per-cell floor ≈ `{Height: 0.020, agb: 0.113, npp: 0.062, LAI: 0.025}`;
  **~11 % on cell-mean agb**, `metrics.PUBLISHED_NOISE_FLOOR`). **Report per-cell error magnitude
  against the per-cell floor FIRST**, never lead with a pooled metric (see `DESIGN.md` §"Reuse").

## Package layout

```
python/
├── pyproject.toml                     # hatchling build; deps mirror py311_new; ruff/pytest config
├── .python-version                    # 3.11
├── README.md                          # this file
├── conftest.py                        # src/ on sys.path; deterministic Hypothesis profile
├── config/config.yaml                # ported prototype config (paths marked; see repo-root config/)
├── src/lpjmlfit_emulator/
│   ├── __init__.py                    # package docstring, __version__, curated public API
│   ├── metrics.py                     # distributional metrics (Wasserstein, KS, energy dist)
│   ├── noise_floor.py                 # seed1-vs-seed2 noise-floor diagnostics (the yardstick)
│   ├── data.py                        # frozen 29-col `ind` schema + loader + patch summaries
│   ├── transforms.py                  # signed-log + monotone (isotonic) trait links
│   ├── drivers.py                     # annual climate/CO2 driver aggregation (xarray guarded)
│   ├── features.py                    # per-(Cell,Year) climate features + eco diagnostics (guarded)
│   ├── baseline.py                    # DIRECT (non-recursive) climate->distribution emulator
│   └── train.py                       # training / holdout / evaluation (matplotlib guarded)
└── tests/
    ├── test_metrics.py                # distributional metrics + noise floor
    ├── test_noise_floor.py            # seed-split floor (asserts published numbers)
    ├── test_data.py                   # schema validation + loader + patch summaries
    ├── test_transforms.py             # log transforms + monotone links (determinism)
    └── test_features.py               # feature schema + build_cell_year_feats
```
