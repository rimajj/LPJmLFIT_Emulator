"""lpjmlfit-emulator (prototype): the slow distributional emulator, component S.

Python-first PROTOTYPE of the LPJmL-FIT slow trait/size *distribution* emulator:
the per-cell object ``p(traits, size | drivers, state)`` over trees plus the tree
count ``N`` (DESIGN.md §"S's target object"). Per ``ECOSYSTEM_AND_COUPLING.md`` the
target ESM stack is Julia + Enzyme AD; this package is the Python prototype
(LightGBM + Gaussian copula baseline, no NN/diffusion unless the metric panel
demands it) to be ported to Julia/Lux.jl for the coupled, online-trainable system.

This package is the SINGLE SOURCE OF TRUTH for component S. Its modules were ported
once on 2026-07-16 from the now-frozen sibling emulator at
``/p/projects/open/Jamir/emulator`` (ADR docs/decisions/0012); the sibling is not a
dependency and is never synced back. Fixed seed 42 for all stochastic work.

Layout:
  - ``metrics``     distributional metrics + the seed1-vs-seed2 noise floor (the yardstick)
  - ``data``        frozen 29-column ``ind`` schema + validated loader + patch summaries
  - ``transforms``  signed-log + monotone (isotonic) trait links
  - ``drivers``     annual climate/CO2 driver aggregation (xarray guarded)
  - ``features``    per-(Cell,Year) climate features + guarded eco diagnostics
  - ``baseline``    the DIRECT (non-recursive) climate->distribution emulator
  - ``train``       training / holdout / evaluation helpers (matplotlib guarded)
"""

from __future__ import annotations

from . import baseline, data, drivers, features, metrics, train, transforms
from .baseline import DirectEmulator, ResidualRegressor, add_competition
from .data import (
    IND_COLUMNS,
    build_patch_summaries,
    ind_columns,
    load_ind,
    validate_ind_schema,
)
from .features import AXES, FEATURES, build_cell_year_feats
from .metrics import PUBLISHED_NOISE_FLOOR, noise_floor, per_cell_relative_error
from .transforms import MonotoneLink, VarTransformer, expm1_clip, log1p_signed

__version__ = "0.1.0"

# NB: ``TREE_TYPES`` intentionally NOT re-exported here — ``data.TREE_TYPES`` (the
# schema tree PFTs 1-5) and ``features.TREE_TYPES`` (the modelling PFT range 0-6) are
# distinct by design; access them via their submodule to avoid ambiguity.
__all__ = [
    "__version__",
    # submodules
    "baseline",
    "data",
    "drivers",
    "features",
    "metrics",
    "train",
    "transforms",
    # baseline
    "DirectEmulator",
    "ResidualRegressor",
    "add_competition",
    # data
    "IND_COLUMNS",
    "validate_ind_schema",
    "ind_columns",
    "load_ind",
    "build_patch_summaries",
    # features
    "FEATURES",
    "AXES",
    "build_cell_year_feats",
    # metrics
    "PUBLISHED_NOISE_FLOOR",
    "noise_floor",
    "per_cell_relative_error",
    # transforms
    "MonotoneLink",
    "VarTransformer",
    "log1p_signed",
    "expm1_clip",
]
