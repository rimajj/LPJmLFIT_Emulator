### Fixed

- **Corrected two claims about why F's uniform tree leaf-recycle is faithful** (ADR 0134). The
  `pft_allocparams` docstring in `src/fdiff.jl` justified `AllocParams.is_deciduous = true` by "every
  tree PFT in this configuration is `summergreen` under `new_phenology`". That is true of the parameter
  file and irrelevant to the code: under `new_phenology:true` the `phenology` key is never read for
  leaf turnover, because `daily_natural.c:123` dispatches to `phenology_gsi` and
  `phenology_tree.c`'s phenology switch is dead. The load-bearing reason is the clamp in the C's own
  non-latched branch, `1/max(pft->longevity, 1.05)` (`turnover_daily_tree.c:38`), which caps the drip
  rate at the latched branch's own 0.9524/yr.
- **Replaced an assertion in `scripts/build_pft_fdiff_params_reference.py` that could not fail.** It
  checked `phenology == "summergreen"` for tree ids 0–6 — an inert key, so it would only trip on an
  edit that changes nothing while staying green through the edit that matters. It now asserts the
  `1.05` clamp constant and that each tree's `longevity` is still the `{mean, interc, slope, sigma}`
  corridor form positioned above the clamp, i.e. the quantities a real change would move. The
  committed 43-column `M_pft_fdiff_params.csv` is unchanged and still reproduces byte-for-byte under
  `CHECK=1`.

### Added

- `scripts/diagnose_leaf_turnover_regime.py` — audits the C's per-individual leaf-turnover basis at the
  five coupled biome cells from its own `ind` table (variability audit, retained-leaf fraction per
  branch with a per-cell CANNOT BIND / CAN BIND verdict, and the SLA–longevity corridor). Runs in
  seconds.

### Changed

- **Retired `AllocParams.is_deciduous` as the `boreal_siberia` allocation suspect** (ADR 0134). The
  C's leaf-recycle gate is a runtime latch (`tree->isphen`), not a per-PFT flag, and its two branches
  evaluate to the *same number* for any stem whose leaf longevity is at or below 1.05 yr — which
  measured is 100.0 % of the larch and BoBS stems that are 99 % of that cell. Stem-weighted, F over-
  sheds 0.3 % of the leaf pool there, so no latch-incidence measurement can revive the item. The gap
  is relocated to `tropical_amazon` (12.4 %) and `mediterranean_iberia` (24.8 %), both upper bounds
  until the latch incidence is measured; no default, parameter or recommendation is proposed on that
  basis.
- **Recorded that leaf longevity is a per-individual, SLA-derived trait** (`new_tree.c:215`, emitted
  as the `ind` column `Longevity`), distinct from the per-PFT `turnover.leaf` residence time F stores
  in `AllocParams.turnover_leaf`. No active defect — F's tree path never reads `turnover_leaf` — but
  wiring it into a non-latched branch would retain 0.75 of the leaf pool where the truth is 0.44.
