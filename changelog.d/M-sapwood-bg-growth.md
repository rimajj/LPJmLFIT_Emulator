### Added

- **F_diff: the C's below-ground wood sink is now prognostic (opt-in, ADR 0132).** `TreePools` gains
  `heartwood_bg_c` beside `sapwood_bg_c`, and `grow_individual` / `FDiffFastCore` / `rollout_canopy_years`
  gain `bg_growth`: the below-ground `sapwood_bg → heartwood_bg` turnover (`turnover_tree.c:124-130`) plus
  the C_LATERAL demand top-up deducted from the assimilate *before* the leaf/root/sapwood split
  (`allocation_tree.c:163-209, :268-277`). The port is a pure redistribution — `vegc_full_ind` is
  unchanged between the on and off arms on all 272 committed Hainich stems — which is why the second pool
  is not optional. Default off ⇒ byte-identical (275 597 pass / 0 fail, no baseline moved).
  New gate `test/testitems/sapwood_bg_growth_tests.jl`.
- **`FDiff.sapwood_bg_seed`** — the below-ground pool a stem in the C actually *holds*, `(1−turnover_sapwood)`
  times the C_LATERAL demand. Seeding at the bare demand (the previous convention) makes the pool and the
  demand shrink in lockstep so the annual top-up computes as **exactly zero**: the top-up fires on 0 of 272
  Hainich stems with the old seed and 205 of 272 with this one.

### Changed

- `FDiff.vegc_full_ind` now includes **both** below-ground wood pools, i.e. the C's own `vegc` pool set
  (`veg_sum_tree.c:25`). `vegc_ind` is unchanged. Byte-identical while the pools are 0.
- `scripts/biome_sapwood_bg_probe.jl` gains arms `Abgg`/`Pbgg`/`Pgbgg` and a PART 7 scoring ADR 0127 §6's
  pre-registered criterion: the paired surplus drops **51.3** gC/m²/yr at `temperate_hainich` (bar 30.9,
  **PASS**) and **19.2** at `boreal_siberia` (bar 19.9, **FAIL** — the outcome ADR 0127 §5's own
  `dD/bel_C = 0.11` predicted for that cell). All 35 pre-existing rows of
  `test/testitems/references/M_growth_channel_decomposition.csv` are byte-identical; 15 rows added.
