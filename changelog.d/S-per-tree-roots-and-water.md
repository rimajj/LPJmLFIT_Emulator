### Added

- **Per-tree root profiles and per-tree water status** in the differentiable fast core (ADR 0110, opt-in via
  `WaterParams.per_tree_roots`, default off ⇒ every committed baseline byte-identical). Each individual with a
  rooting-depth trait now gets its own root-weighted soil moisture, its own water supply, its own water
  scalar, and withdraws down its own profile — instead of every tree sharing one cell-average profile
  collapsed to a single scalar. Two trees differing only in rooting depth are no longer identical in the
  water balance.
  - `FDiff.betaroot_from_d95max` / `FDiff.jackson_rootdist` / `FDiff.per_tree_rootdists` — ports of the C's
    `soil/getbetaroot.c` and `lpj/getrootdist.c`, **validated to 5e-7 against the C's own emitted
    `beta_root`** across the full trait range (an oracle test, not self-consistency).
  - `FDiff.getvpd` — port of `spitfire/getvpd.c` on the `relative_humidity = false` branch this configuration
    takes; `DailyForcing` gains `humid` (specific humidity, already column 7 of every committed forcing
    fixture).
  - `TreePools` gains `d95max` and `minwscal`; `Individual` unchanged (see below); `daily_step_canopy` takes a
    `rootdists` keyword and returns `wscal_ind` / `wr_ind`.
  - The C's **order-free** first cap — no individual may draw more from a layer than its own FPC share
    (`water_stressed.c:159-161`) — via `WaterParams.per_tree_fpc_cap`. The order-*dependent* residue cap
    stays out of scope.
- **The drought and heat mortality hazards can be switched on** (ADR 0110, `WaterParams.trait_drought_mortality`,
  default off). ADR 0049 §3 set `mort_water` and `mort_temp` to zero because the emulator had neither the C's
  per-individual daily water scalar nor a per-tree drought threshold; both now exist.
  `TraitMortality.water_stress_increment` / `temp_stress_increment` port `tree/waterstress_tree.c` and
  `tree/tempstress_tree.c` one day at a time, and `FDiffFastCore` accumulates them per individual over the
  year.

### Changed

- `make_recruit_to_pools` writes the sampled `D95max` and `minwscal` into each recruit's `TreePools` (located
  by axis name; an artifact lacking those axes still loads and leaves both unset ⇒ unchanged behaviour).
  `_merge_pair!`, `_with_nind` and `grow_individual` carry both traits — without that, every cohort merge,
  density change or growth step would silently reset them.

### Fixed

- A `Vector` field on `FDiff.Individual` aborts the Enzyme reverse pass with SIGABRT (a bare LLVM abort with
  no Julia error, surfacing right after the grass Enzyme training test item). The per-tree root profiles now
  travel as a separate argument that Enzyme sees as constant data. Recorded on the struct so it is not
  reintroduced.

### Documented

- ADR 0110 — the "structurally impossible" per-individual water-supply verdict was reached on **grass** and
  does not apply to **trees**, and the `-DPERMUTE` randomness behind it does not touch the per-individual
  quantities the drought channel needs (they read a soil column frozen for the whole permuted loop). Narrows
  `docs/water_supply_perpft_design.md`'s DEFER to the order-dependent residue cap alone; reopens the channel
  ADR 0049 §3 closed. Flip criteria pre-registered.
