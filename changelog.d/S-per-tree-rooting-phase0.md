### Added

- `scripts/diagnose_per_tree_water_access.py` — the Phase-0 kill/proceed check for the rooting-depth gap.
  Measures, on the LPJmL-FIT C model's own per-individual `ind` output rather than by simulation, how
  differently real trees in the same cell and year experience water: the across-tree spread of `wscal_mean`,
  its amplification in dry years, the within-(PFT × age-band) correlation with each stem's own `beta_root` /
  `D95max`, and the share of total mortality hazard carried by `mort_water` / `mort_temp` together with the
  selection differential those hazards impose on rooting depth. Pre-registered pass criterion; both
  scenarios; 5 biome cells.

### Documented

- ADR 0110 — the "structurally impossible" per-individual water-supply verdict was reached on **grass** and
  does not apply to **trees**. `beta_root` is set per individual from that individual's own `D95max`
  (`new_tree.c:229-230`), the trait spans 51–1800 cm within a single PFT, and the C's per-individual `wr`,
  `supply`, `wscal` and the routinely-firing "own FPC share" cap are all **order-independent** — the
  `-DPERMUTE` randomness touches only the residue cap and realized GPP. Measured: across-tree water-scalar
  spread of 0.16–0.19 in the water-limited cells (our fast core carries one number), a 0.83 within-band
  correlation between a stem's root profile and its own water status in the Sahel, and drought-killed stems
  rooting 57 % shallower than the population mean at Hainich. Verdict PASS; per-tree roots + per-tree water
  + un-zeroing the two hazards ADR 0049 left at zero is the decided path, in three separately-gated
  default-byte-identical steps.
