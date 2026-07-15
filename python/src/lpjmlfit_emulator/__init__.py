"""lpjmlfit-emulator (prototype): the slow distributional emulator, component S.

Python-first PROTOTYPE of the LPJmL-FIT slow trait/size *distribution* emulator:
the per-cell object ``p(traits, size | drivers, state)`` over trees plus the tree
count ``N`` (DESIGN.md §"S's target object"). Per ``ECOSYSTEM_AND_COUPLING.md`` the
target ESM stack is Julia + Enzyme AD; this package is the Python prototype
(LightGBM + Gaussian copula baseline, no NN/diffusion unless the metric panel
demands it) to be ported to Julia/Lux.jl for the coupled, online-trainable system.

Evaluation reuses the PRIOR sibling emulator's noise-floor discipline
(``/p/projects/open/Jamir/emulator/src/metrics.py``): report per-cell error
magnitude against the seed1-vs-seed2 noise floor first (see
``lpjmlfit_emulator.metrics``). Fixed seed 42 for all stochastic work.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
