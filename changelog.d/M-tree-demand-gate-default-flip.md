### Changed

- **The C's per-tree photosynthesis demand-gate is now ON by default** (`WaterParams.tree_demand_gate`,
  ADR 0133), discharging the flip criterion ADR 0131 §8 pre-registered before the gate existed. All three
  conditions met: the below-ground wood growth port landed (ADR 0132); the assimilate error
  `mean |bmi_F/bmi_C − 1|` over the four readable biome cells FALLS 0.1914 → 0.1581 on the pre-registered
  arm pair and 0.1599 → 0.1266 on the current most-faithful growth arms (−21 % of the error, same −0.0333
  in both); and the blast radius was measured before any baseline was touched — **4 assertions of 275 597**,
  two of them the "default is off" assertions themselves.
- **Two committed baselines deliberately re-measured**, each by a harness that reproduces the pre-flip
  numbers in the same run: the Hainich canopy annual totals (`gpp_annual` only, 1250.124 → 1237.437; the
  four water rows at ratio exactly 1.0, which is the mechanism's own prediction) and the coupled 5-cell
  LE/GPP pins (the new `TREE_GATE=0` opt-out arm reproduced all ten previous pins to every printed digit).
- **The cost is stated with the gain:** the photosynthesis channel gets slightly WORSE
  (`mean |gpp_F/gpp_C − 1|` 0.0570 → 0.0611), entirely at `semiarid_sahel` (0.906 → 0.855), while boreal
  and Hainich improve; coupled stand cover falls 3.1 % at boreal and 1.0 % at Hainich. `semiarid_sahel`'s
  2-year coupled GPP nevertheless RISES 1.6 %, because the gate stops F paying leaf respiration against a
  collapsed assimilation on drought days, so that cell's canopy grows instead of shrinking.

### Fixed

- **Four probes had control arms that would have been silently relabelled by the flip** — the arms in
  `biome_sapwood_bg_probe.jl` / `biome_canopy_growth_probe.jl` / `biome_slow_oracle_probe.jl` /
  `biome_resilience_probe.jl` that MEAN "gate off" now say so instead of inheriting a default that moved.
  Worst case, and it would have been silent: the first probe builds its gated arm by copying its ungated
  one and setting the flag, so `Ag ≡ A` and `Pg ≡ P` would have collapsed and 30 committed rows of the
  growth-channel decomposition would have been reproducible only under labels that no longer described them.
- **A guardrail-4 assertion written one week earlier became a green test that proved nothing**, and is now
  closed with its reason asserted rather than assumed: at the soft default sharpness the gate's sigmoid
  saturates to exactly 1.0 on every day of that fixture's forcing, so "the default reproduces the opt-out
  bit-for-bit" kept passing after the flip for a reason that had nothing to do with the flag.
