### Added

- **The response-arm harness now runs at any of the five provisioned biome cells, not only Hainich**
  (`SITE=<name from M_cells.csv>` on `scripts/trait_mortality_arm_probe.jl` and
  `scripts/build_hainich_response_forcing.py`). A non-default site takes its trees, soil column, forcing,
  latitude, per-cell stem/age seeds and static boundary from the committed per-cell fixtures — never from the
  Hainich-trained artifact meta. `SITE` unset is byte-identical to every earlier run, verified two ways: a
  matched-seed pre/post-refactor pair differing only in the scope label, and a 40-seed ensemble reproducing
  ADR 0170's published arm to every digit (ADR 0171 §1).
- **New committed fixtures:** the two-scenario transient boundary and the per-cell(-year) eligible-PFT set for
  `tropical_amazon` and `boreal_siberia`, plus `S_recruit_multicell_seed_ensembles.csv` — the 200-row per-seed
  record behind ADR 0171's cross-cell table.
- **`BND_FIXTURE`** on the probe: run the arm against another transient-boundary file, so a conditioning-basis
  comparison never needs the committed fixture hand-edited.

### Fixed

- **A train/inference inconsistency in the response arm's SSP370 conditioning basis (ADR 0171 §2).** The
  builder gave only the historic scenario a 20-year monthly lead-in, so the ssp370 side's first years were
  averaged over 1, 2, 3 … years instead of 20 — making **19 of 81 conditioning years a different quantity from
  the one the learned models were trained on**, by up to **+210 growing-degree-days (+10.7 %)** and
  **+1.94 °C**. A code comment asserted the omission was deliberate and consistent with the training basis;
  measured against that basis, it was not. Both scenarios now take the lead-in, and a new hard gate compares
  the result to the trained table for the run's own cell (it now reproduces it exactly, at all three cells).
  **No published number moves:** every number measured on this arm used an artifact whose two boundary axes are
  constant in training, so its boundary channel is provably inert (the probe's own liveness check reads exactly
  0.0), and the 40-seed reproduction confirms it. Where the channel *is* live, the fix moves the arm by
  **0.03 ×** the reference warming shift against a sampling error of **0.32 ×** — real, correct, and an order
  of magnitude below the ensemble's own precision.

### Changed

- `test/testitems/references/S_hainich_response_boundary.csv` regenerated on the corrected basis (the
  historic half is unchanged; the ssp370 half changes only for 2020–2038 and is exact from 2039). The
  pre-fix basis stays reproducible bit-for-bit via `SSP_LEAD=2020 ALLOW_UNTRAINED_SSP_BASIS=1`, and is
  retained as ADR 0171's own control arm.
- The response-boundary testitem gains a CI-safe tell for a truncated averaging window (the largest
  year-on-year jump against the series' own median jump — 13.1 before the fix, 4.0 after; the gate allows 8),
  because the trained reference table lives on scratch and CI cannot read it.

### Measured (ADR 0171 — the recruit arm at three cells)

- **The ported establishment rule raises the standing community's mean wood density at all three cells
  measured** — +2.20 % (temperate), +4.93 % (tropical), +5.00 % (boreal), each at t ≥ 5.1, i.e. 2.1–4.4× the
  entire observed warming shift as a static offset. This is the robust finding and it is why the rule **stays
  switched off** by default; the one-cell +8.5 % of ADR 0170 is the same conclusion on a different artifact.
- **Its contribution to the warming response is not even sign-stable**: −0.89 ± 0.32, +1.98 ± 0.93 and
  −1.91 ± 0.53 × the reference shift at the three cells, and it *also* reverses (+3.41 → −0.89) when the
  learned artifact is swapped at a fixed cell. ⇒ ADR 0170 §2's "the port removes a wrong-signed response" is a
  statement about one cell on one artifact and must not be generalised; a **third** condition is added to the
  pre-registered flip criterion (at least one cell per eligibility regime, artifact held fixed and named, sign
  must agree).
- **The baseline being scored against is itself strongly cell-dependent** (+0.27, +0.30, **+1.94** × the
  reference shift) — at the boreal cell the *shipped* configuration already overshoots the observed warming
  shift by 94 %, and the ported rule removes that response rather than adding one.
- **The bioclimatic recruit gate moves in opposite directions with warming**, and the earlier reading
  generalised the wrong way: at the temperate cell it CLOSES (the three boreal tree types are expelled once
  the 20-year cold-month mean passes 0 °C, so more recruits come from the cell's own seed bank), at the boreal
  cell it OPENS (temperate types are admitted, so fewer do). The tropical cell's is static.
- **The low-diversity regime is not where it was thought to be**: the Amazon and Sahel admit four tree types
  (not one). Only **124 of 52 451** tree-bearing cells admit exactly one; the modal cell admits four (49 %),
  and the genuinely inheritance-dominated regime is the **11.2 %** that admit none — untested, and the class
  with the worst noise floor (median 29 stems).
