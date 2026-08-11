### Changed

- **Line M — the rung-2 demography rendezvous moved behind the growth loop, and the one-year lag is gone
  exactly (ADR 0123).** The C used to ask the external demography for its answer at the *top* of the
  annual block, while its own hazard runs after turnover and allocation, so the roster it published
  carried last year's growth state. Measured, that inverted the sign of the wood-density selection
  signal (ratio −0.825 against the C). The hazard and its random draw now run unchanged but no tree is
  removed inside the loop: each verdict is recorded, the rendezvous opens afterwards on a new `grow`
  dump phase holding the complete current-year roster, and a kill pass applies the verdicts.
  On the new basis the interface reproduces the C's own per-tree ordering exactly — Spearman ρ = 1.000
  at p05, median *and* minimum over all 500 patch-years — and the selection differential ratio is
  +1.000. The 942-of-9 951 record skip disappears with it, so the youngest cohort is no longer
  invisible. `patches/lpjmlfit_rung2_hook_v5.patch` supersedes v4.

### Fixed

- **Line M — the roster key table no longer silently caps at 1024 entries** (it stopped recording
  duplicates past the cap, which would have made a kill instruction ambiguous in a dense cell).

### Notes

- The deferral is shared by *both* rung-2 hooks, so the recorded baseline and every replayed arm sit on
  the same code path and the null control is exact by construction (identical in every initialised
  column over 40 161 tree records; no divergence in all 2 000 patch-years of cell state). With both
  environment variables unset the stock model is untouched — 139 decoded quantities identical, 0 differ.
  The deferred path does move the C's *own* trajectory relative to stock by 0.05 % of stem-years over
  20 years at one cell (identical terminal stem count); that is disclosed with every rung-2 number.
- Any roster dump recorded before this change is unusable as a replay basis; the harness now fails
  loudly on one instead of replaying a stale roster.
