### Added

- **The two remaining `gp_sum` basis differences between the fast core and the LPJmL-FIT C, measured one
  variable at a time — one helps a lot, one is faithful and makes agreement worse
  ([ADR 0136](docs/decisions/0136-the-two-gp-sum-basis-differences-measured-one-helps-one-hurts.md)).**
  Discharges ADR 0051's registered-but-unmeasured item and executes ADR 0135's shortlist item (a). Both
  differences live in `gp_sum.c:53-67`, both are **exact identities at `phen = 1`** (i.e. partial-leaf-day
  effects), and both ship as opt-in `WaterParams` flags, **default off and byte-identical**.
  **`gp_stand_leafon_basis`** — the C builds each PFT's potential canopy conductance at FULL leaf cover and
  forms `Sum gp*phen / Sum fpc` with a PLAIN denominator; F_diff folded `phen` into the pass-1 absorbed PAR
  and into `gmin` and divided by the phen-weighted denominator, biasing its stand conductance high by
  `~1/mean(phen)` on any partial-leaf day and thereby raising its solved ci:ca ratio and its GPP. Switching
  to the C's basis LOWERS F's tree GPP at **5 of 5** biome cells (direction predicted before the arm ran;
  magnitude ranking predicted too, and smallest at the driest cell because conductance is supply-limited
  there). **On the shipping configuration** (per-PFT parameters + the tree demand gate + the prognostic
  below-ground wood pool) it improves **every cell and every aggregate**: mean `|GPP_F/GPP_C - 1|` over the
  four readable cells **0.0824 -> 0.0328** and mean `|bmi_F/bmi_C - 1|` **0.1266 -> 0.0535**, with Hainich's
  GPP excess going **+9.1 % -> +3.0 %** — from a basis fix with no new physics and no parameter. Its
  apparent overshoot on the historical control arm (boreal 1.044 -> 0.935) is a property of **that arm's
  reference**, not of the flag: ADR 0126 measured that boreal's agreement under beech parameters came from
  two wrong parameters of opposite sign, so a faithfulness fix scored against it necessarily looks like an
  overshoot. The default flip is pre-registered in ADR 0136 §7 with conditions 1-2 already met.
  **`lambda_vm_gp`** — the C's stomatal-optimisation bisection carries the Vcmax left by `gp_sum` (computed
  at a crown-cover, no-phen absorption) while its light-limited term uses the layered phen-scaled
  absorption; only the solved ci:ca ratio differs, because Vcmax does not depend on it and the C's final
  call recomputes at the layered absorption exactly as F_diff does. **No sign was predicted, deliberately,
  and the measured one is positive at all five cells:** the layered absorbed fraction EXCEEDS crown cover in
  a real stand (0.282 vs 0.151 for the unit roster's dominant stem), so the C's Vcmax is the smaller one.
  **A more faithful arm therefore scores WORSE — making this the third independent term to say the fast
  core's true tree-photosynthesis error is LARGER than the GPP ratio that measures it** (ADR 0135 found two
  more, both making F absorb less light while its GPP sits above the C's). Read that ratio as a lower bound.
  `lambda_vm_gp` is explicitly NOT a flip candidate until the compensating error is found; it ships as the
  faithful control for that search. Gated by `test/testitems/gpsum_basis_tests.jl`, which pins both
  exact-boundary identities **bitwise**, each with a matched "the flag actually fires" partner so a green
  identity cannot be an inert code path, and asserts **no sign** for `lambda_vm_gp`. Suite 275 621 pass /
  0 fail with no committed baseline moved; `M_growth_channel_decomposition.csv` gains six arms as **30 added
  lines with 0 pre-existing lines changed**.
