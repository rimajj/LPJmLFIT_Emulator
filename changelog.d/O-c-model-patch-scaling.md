### Measured

- **LPJmL-FIT's cost is proportional to patch count with no measurable fixed floor** — `cost ≈ 0.0141 · npatch`
  core-s per cell-year (Hainich; reproduced at the Amazon cell at `0.0084 · npatch`). At the production
  ~500 patches that is **7.06 core-s per cell-year** and the patch-count-independent work is **at most
  0.19 %** of the bill. Speedup from 500 patches to J is exactly 500/J.
- **The patch count each OUTPUT requires**, from 5 independent spin-ups per patch count: at 100 patches the
  measured error is 0.59 % (evaporation), 0.96 % (gross carbon uptake), 1.48 % (transpiration), 3.40 %
  (vegetation carbon), 7.54 % (establishment), 32.3 % (fire). The atmosphere-facing fluxes need a handful of
  patches; fire needs more than 500.
- **A third of the C model is spent in `pow`/`exp`/`log`** (31.8 % self time), and an exact-only optimisation
  ladder worth **~2×** exists: the root-profile routine is called twice per tree-day with identical arguments
  for a value that changes once a year (10.2 %); the peak-photosynthetic-capacity bracket and the
  temperature-stress factor each have at most 10 distinct values per cell-day but are evaluated ~150 000
  times; the stomatal-optimality residual is a polynomial in the solved variable.

### Fixed

- `scripts/probe_c_patch_scaling.sh` no longer reports a negative per-cell share or a negative "ceiling" when
  the true intercept is zero — it reads `cost/J` first, fits through the origin, bounds the fixed cost from
  the smallest-J arm, and refuses to extrapolate when `cost/J` is not flat.
- `scripts/probe_c_genepool_diversity.sh` dedupes stems by `(Patch, ID)` (the annual `ind` table emits a
  surviving stem once per year, so "distinct values / rows" measured 1/years) and flags any group with fewer
  than 30 stems as not evidence.

### Notes

- Corrects three earlier conclusions of this project, all of which had been computed at 25 patches rather
  than the production 500: that the patch ensemble is not the bottleneck; that patch reduction is worth ~3×;
  and that a few-patch → many-patch surrogate is capped at 25×.
- **The patch count is a pure variance knob — there is no patch-count bias.** `npatch` enters in exactly two
  non-cosmetic places, and establishment is computed per patch from that patch's own floor light, so the
  ensemble mean is unbiased at any patch count. The measured 21–81 % recruitment loss is the cost of
  averaging the stand into ONE patch, not of running fewer patches.
- A hypothesis that the shared cell-level seed bank (sized `15.75 × npatch`) impoverishes trait diversity at
  low patch count was **measured and rejected** at two contrasting cells.
