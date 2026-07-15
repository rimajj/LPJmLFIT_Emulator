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

The `pyproject.toml` (build backend **hatchling**) and the eventual **`uv.lock`** exist to
**pin an exact, reproducible dependency set for CI** and archival reproducibility
(`ENGINEERING_STANDARDS.md` §7: Python uses a `uv` lockfile). They are **not** the way you
run day-to-day work here — that is the reused conda env above. To (re)generate the lockfile
on a machine **with network** (do not run in the offline HPC job):

```bash
uv sync              # resolves deps + dev group, writes uv.lock
uv run pytest -q     # runs the suite in the locked env
uv run ruff check .  # lint (E,F,I,UP,B); uv run ruff format --check .
```

Runtime deps mirror `py311_new`; dev group = `pytest`, `pytest-cov`, `hypothesis`, `ruff`.
Config: Ruff (line-length 100, target py311, select `E,F,I,UP,B`), pytest
(`testpaths=["tests"]`, `addopts="-q"`, `pythonpath=["src"]`). Hypothesis has no native
pyproject table; its deterministic profile (`derandomize=True`, `deadline=None`) is
registered in `conftest.py`.

## Reused from the PRIOR sibling emulator

The sibling project **`/p/projects/open/Jamir/emulator`** already established the evaluation
discipline this prototype **reuses rather than re-derives**:

- **`emulator/src/metrics.py`** — the full metric library (1-D Wasserstein, KS, per-quantile
  errors, multivariate energy distance + its seed-split null floor, correlation-matrix
  Frobenius distance, moment NRMSE/bias/R²). `src/lpjmlfit_emulator/metrics.py` here is a
  small, pure-numpy, tested **subset**; port/import the sibling module as the panel grows.
- **Noise-floor discipline** — the **seed1-vs-seed2 noise floor** is the yardstick, not zero
  error (published per-cell floor ≈ `{Height: 0.020, agb: 0.113, npp: 0.062, LAI: 0.025}`;
  **~11 % on cell-mean agb**). **Report per-cell error magnitude against the per-cell floor
  FIRST**, never lead with a pooled metric (see `DESIGN.md` §"Reuse", `emulator/src/eval_presentday_critical.py`).

## Package layout

```
python/
├── pyproject.toml                     # hatchling build; deps mirror py311_new; ruff/pytest config
├── .python-version                    # 3.11
├── README.md                          # this file
├── conftest.py                        # src/ on sys.path; deterministic Hypothesis profile
├── src/lpjmlfit_emulator/
│   ├── __init__.py                    # package docstring + __version__ = "0.1.0"
│   ├── metrics.py                     # pure-numpy distributional metrics + noise floor
│   └── data.py                        # frozen 29-column `ind` schema validation (DESIGN.md §3.1)
└── tests/
    ├── test_metrics.py                # pytest + Hypothesis property tests
    └── test_data.py                   # pytest + Hypothesis property tests
```
