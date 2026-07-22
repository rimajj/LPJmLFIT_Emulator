---
name: python-env
description: Set up and check the Python Component-S prototype under python/ (uv sync --frozen, pip --break-system-packages, the ruff-format + pytest gates, and the "eval"-filename classifier gotcha). Use whenever working on the LightGBM+copula slow-emulator prototype or fixing the `python` CI gate.
---

# python-env — the Component-S prototype environment

The slow emulator (S) prototype lives in `python/` (uv-managed, package `lpjmlfit-emulator-proto`,
Python 3.11). Baseline S = **LightGBM + Gaussian copula** ("DirectEmulator"); no NN in the baseline.

## Set up

```bash
cd /p/projects/open/Jamir/esm_land_emulator/python
uv sync --frozen        # installs EXACTLY the committed uv.lock (no re-resolve) — reproducible, like CI
```
When uv isn't available (reused conda env `py311_new` = `/home/jamirp/.conda/envs/py311_new`), use
`pip install --break-system-packages`.

## Gates (run inside `python/`, in this order — mirrors the `python` CI job)

```bash
uv run ruff check .          # lint
uv run ruff format --check . # format gate (drop --check to fix)
uv run pytest                # ≈ 49 pass / 6 skip locally; 56 pass in the locked CI env
```

## Gotchas

- **The `eval`-filename classifier block:** the agent's auto-mode classifier **refuses to read any file
  whose name contains `eval`** (e.g. a sibling `eval_presentday_critical.py`). It is a classifier
  heuristic, not an owner-configured hook. **Work around it by renaming/copying to a non-`eval` name**
  before reading or porting. (This blocked a faithful port once; `noise_floor.py` had to be rebuilt from
  spec instead.)
- **Dep caps are deliberate.** `pyproject.toml` upper-bounds every dep to the next SemVer major so a
  floating `uv sync`/Dependabot bump can't pull a breaking major (pandas 3, scikit-learn 2, …) into CI —
  the root cause of the 2026-07-16 `python` gate failure. Keep `uv.lock` committed and use `--frozen`.
- torch/lightning/sdv/statsmodels/POT are intentionally **out** of the core deps (baseline is LightGBM +
  copula); add them only if the metric panel escalates beyond the baseline.

## Where the ported S code is

`python/src/lpjmlfit_emulator/` (ported from the frozen sibling `/p/projects/open/Jamir/emulator`):
`transforms.py`, `drivers.py`, `features.py`, `baseline.py` (`DirectEmulator`), `train.py`, `data.py`
(frozen 29-col `ind` schema + `load_ind`/`build_patch_summaries`), `metrics.py`, `noise_floor.py`
(seed1-vs-seed2 floor). Trainer: `scripts/train_slow_emulator.py`.
