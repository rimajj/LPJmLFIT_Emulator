### Fixed

- **Line M / ADR 0051 — F_diff's daily `wscal` was the REALIZED supply/demand ratio; the C's is a
  POTENTIAL leaf-on index.** This closes the last of ADR 0034 §1's three runtime↔training conditioning
  shifts (the other two were line S's, ADR 0035), and it was the stated blocker on M3.

  Both sides carry the column name `water_stress` and both form it as `1 − wscal_mean`, which is why the
  gap was recorded as "same definition on both sides". Reading the expressions
  (`water_stressed.c:130-140`, `gp_sum.c:57-67`) shows they are different physical variables: the C asks
  *if this canopy were at FULL leaf cover, could the soil meet the evaporative demand?* — no `phen` in the
  numerator, the leaf-on conductance `gp_stand_leafon` (normalized by the **plain** `Σfpc`) and no
  `(1−wet)` in the denominator, and `wscal = 1` (**unstressed**) on a no-demand day. F_diff's
  `min(1, Σsupply·fpc / Σdemand·fpc)` carried `phen` **squared** in the numerator and degenerated to **0**
  (maximally stressed) as leaf display vanished.

  Available as **`WaterParams.wscal_leafon`, default `false`** — every committed baseline and the AD trainer
  are byte-identical (guardrail 4). Enabling it moves Hainich's annual `water_stress` from 6–7 trained-band
  widths above the C's `[0, 0.04315]` to **inside** it (0.3050 → 0.0034 against a C truth of 0.0014, a
  **152×** error reduction), and puts `tropical_amazon` **inside the seed1-vs-seed2 noise floor** (0.4×);
  `semiarid_sahel` improves 6.7×, `mediterranean_iberia` 2.1×. `boreal_siberia` is **not** closed — the C
  says it *is* stressed (0.3146) and the C-faithful expression under-stresses it to 0.000, with F_diff's
  absent soil-ice/permafrost representation the leading (explicitly unverified) hypothesis.

  Why it gated M3: coupled on the pinned `_t8` forest, end-of-run tree N moves **−36.4 % in
  `semiarid_sahel`** (19 → 12) — the cell whose conditioning shift was largest — so a per-cell demography
  score taken before this fix was reading a badly displaced Sahel.

  Evidence: `scripts/wscal_leafon_probe.jl` (the coupled A/B, 5 cells × 10 yr) and
  `scripts/wscal_c_truth_diagnosis.py` (the reference, derived per cell/year exactly as the training table
  forms the column, scored against the seed1-vs-seed2 noise floor). Gate:
  `test/testitems/wscal_leafon_tests.jl` — the C's semantics (phenology-independence, the no-demand
  branch, the cap) plus the end-to-end in-band result, all on committed fixtures.

- **Line M — `FToS.soilmoist` now uses the ADR-0035 root-zone basis.** `components/fast.jl` built it as
  `sum(state.w)/length(state.w)`, an unweighted mean over all 23 layers, while `interface.jl:37` documents
  the field as the root-zone fraction of WHC and Component S computes exactly that
  (`root_zone_soilmoist` — the top 1 m, `whcs`-weighted, what the C's `rootmoist` measures). Two
  definitions of one named quantity is the hazard ADR 0035 exists to remove. Nothing consumed the field
  numerically, so this is a definition alignment, not a physics change.
