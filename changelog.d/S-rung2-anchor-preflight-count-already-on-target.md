### Added

- **The rung-2 level-anchor pre-flight, which retired a 264-job matrix in ~7 s ([ADR 0186](docs/decisions/0186-the-count-is-already-on-target-the-excess-is-per-stem-mass-so-the-level-anchor-has-no-lever.md)).**
  New `scripts/diagnose_rung2_anchor_preflight.py` derives what ADR 0103's `anchor` reduces to inside the
  rung-2 harness and pre-flights it against the `predict`-matrix arm logs already on disk — no model run,
  no SLURM job. **The algebra does not carry over from `slow.jl`:** the harness's feature row and count
  target are the >5 m emitted population while the coupled path uses the whole roster, so `patch_area`
  cancels and `ρ_eff = (target/n_prev)^(1−a)·(target/n_emit)^a`. Two measured consequences: the anchor is
  **identically inert in `roster` mode** (916 484 rows, `n_prev` bit-identical to `n_emit`, max |diff| 0),
  so no published `roster` number is at stake; and `a` moves only the ρ conversion, never the feature row,
  so ADR 0184's tether stays off. **Headline: the count is already on target and the excess is per-stem
  mass.** On the ssp370 leg at the FIT-gain cells `S1` holds **−2.9 %** stems and **+90.6 %** biomass
  (`S0h` −13.6 % / +89.0 %), with per-stem mass **+63…+246 %** corroborated by height +12…+45 % and
  `age_mean` +53…+160 % — and the per-year trajectory kills the rescue hypothesis, `S1`'s count staying
  within a few per cent of FIT's for **all 81 years** while biomass climbs monotonically to +91 %.
  ⇒ **ADR 0185 §7.5's pre-registered criterion (agb departure < +40 %) is unreachable by wiring the
  anchor**: granted a perfect anchor and proportional biomass — the most generous bound available — the
  surviving departure is **+75.6 % to +415.1 %**, and for `S1` it is *worse* than unanchored because the
  target sits below FIT's count while the mass sits far above it. ADR 0185 §7.2's named next action is
  withdrawn on measured grounds; its §7.1 conditioning-limited verdict **stands and is sharpened** (the
  displaced coordinate is size and age, not count). **Nothing here is a finding against ADR 0103's anchor
  in the coupled path**, where the measured departure genuinely is a count-level one (1.409× over-density,
  ADR 0103 §2). Panels (4)–(6) **import** `diagnose_rung2_map_target_response.py`'s `Leg`/readers/coverage
  gate rather than re-deriving them, and reproduce ADR 0185 §5's table exactly — a first version that
  re-implemented the basis put `S1`'s count departure at +37 % instead of −2.9 %, a sign flip on the
  quantity the decision turns on. No flag flipped, no artifact regenerated, no `src/**` change.
