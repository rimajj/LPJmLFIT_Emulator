### Added

- **Line S, rung 2 — the learned demography can now be run inside LPJmL-FIT's own physics.**
  `scripts/rung2_s_demography_harness.jl` serves the C's demography substitution hook from the **production
  count model**: ρ comes from the shipped count DRF evaluated on a feature row built off the C's own live
  roster, with arms `S0` (uniform thinning, the shipped default), `S1` (the trait hazard's ordering) and `NP`
  (the persistence null, ρ = 1). Establishment stays with the C in all three, so every number is a mortality
  result. Unlike arm C (ADR 0124), which took its count target from the ported hazard or the recorded
  baseline, this asks the learned model. (ADR 0175)
- **`patches/lpjmlfit_rung2_hook_v6.patch`** adds `rootzone_w` / `rootzone_whcs` to the hook's per-patch
  record — the one Component-S conditioning feature (`soilmoist`) that no other dumped record could supply.
  Rebuilt binary `bin/lpjml_rung2_v6`; the rebuild-equality gate passes (110 decoded quantities identical,
  `ind` byte-for-byte), and `scripts/diagnose_rung2_rootzone_column.py` proves the new column reproduces the
  run's own `d_rootmoist.nc` to **5.3e-08** relative — the float32 precision of the output. (ADR 0175)
- **`FluxDrivenSlowEmulator(...; roster_n_prev = true)`** re-synchronises the count model's `n_prev` feature
  and the denominator of ρ to the **live roster's own stem count** instead of the emulator's previous
  prediction. Default `false` ⇒ byte-identical. (ADR 0175)

### Fixed

- **Diagnosed a train/inference shift in the shipped coupled emulator (ADR 0175).** The count DRF's `n_prev`
  column was trained as FIT's own previous-year stem count for that patch, but at runtime
  `reconcile_demography!` sets `s.n_prev = target` every year and nothing ever re-synchronises it with the
  roster the other ten feature columns are read from — so the feature row describes two different stands, and
  they diverge without limit. This gives a mechanism for ADR 0113–0116's measurements (free-running destroys
  the response and leaves the level alone; variance and correlation preserved at lead 80, so not a
  regression to the mean; declines under-followed more than increases). **No fidelity number has been
  measured with the flag on yet** — the default stays off until an arm measures it, and the falsifier is
  pre-registered in the ADR.

### Changed

- `flux_feature_vector` is split so its body takes `(boundary, ages, n_prev, …)` with the
  `FluxDrivenSlowEmulator` method as a one-line wrapper, letting an external harness whose stand belongs to
  the C build the feature row through the same implementation instead of copying it.
