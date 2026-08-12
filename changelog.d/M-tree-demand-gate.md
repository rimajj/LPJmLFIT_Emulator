### Added

- **`WaterParams.tree_demand_gate` — the C's photosynthesis demand-gate for TREES** (opt-in, default off ⇒
  byte-identical; ADR 0131). `water_stressed.c:196` runs photosynthesis only when the canopy's own demand
  `gpd > 1e-5`, and `:83` has already zeroed leaf respiration `*rd`, so on a gated day the C's PFT makes
  neither gross assimilation nor leaf respiration. That gate is per-`Pft`, and this configuration runs
  `individual:true`, so it applies to every tree — but F_diff's existing `grass_demand_gate` is
  `ind.is_grass`-gated, leaving the tree path ungated since it was written. Measured on all five biome
  cells: it flips `semiarid_sahel`'s annual tree carbon balance from **−83.8 to +34.6 gC/m²/yr** on its own,
  and reduces mean `|bmi_F/bmi_C − 1|` over the four readable cells by **17.5 %** on the shipping parameter
  configuration. The default flip is pre-registered behind the `sapwood_bg` growth port (the two act on the
  same carbon-use-efficiency channel and partially cancel).
- `test/testitems/tree_demand_gate_tests.jl` — pins the mechanism: default off, the off-path reproduces a
  bare `tebs_params()` rollout bit-for-bit, a grass individual is byte-identical when only the tree flag
  flips, the trees are not, and stand GPP is monotone under the gate.
- `scripts/biome_sapwood_bg_probe.jl` — arms `Ag` / `Ags` / `Pg` and PART 6, with the prediction the arm
  tests written down before it ran (it was refuted, which is the result). `arm`/`run_one_year!` gained
  `params` / `grass_gate` keywords; the pre-existing arms A/Abg/P/Pbg are byte-identical.

### Changed

- `test/testitems/references/M_growth_channel_decomposition.csv` — three arm rows appended per cell; every
  pre-existing data row is byte-identical (only the arms legend gained three comment lines).

### Fixed

- `docs/notes/sapwood_bg_design.md` §1/§6 and `docs/notes/phase3_fdiff_cbinary_validation.md` §13 predicted
  the **wrong sign** for this fix, because both assumed every demand-gated day is carbon-negative. With
  `A = gpp − rd`, gating scales `A` by a factor in `(0,1]`, so a gated day raises NPP only where its ungated
  `A` was negative — which is true at `mediterranean_iberia` and false at `temperate_hainich`. Amended in
  place with a pointer to ADR 0131.
