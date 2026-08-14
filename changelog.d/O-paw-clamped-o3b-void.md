### Added

- **`scripts/online_coupling/diagnose_paw_clamping.py`** — post-hoc scorer that decides whether an
  online Terrarium `plant_available_water` field is *informative* or *clamped at its own limits*.
  Reads the candidate CSVs an existing coupled diagnosis run already wrote (no simulation, ~1 s),
  reports the binary-front ladder fraction, the level histogram, the front-depth distribution and
  the cross-run bit-identity, and **exits non-zero on `CLAMPED`** so it gates a comparison rather
  than merely informing it (ADR 0085).

### Fixed

- **The online soil-moisture comparison (O3b) is void in the vegetation-free configuration, and is
  no longer reported as a fidelity gap** (ADR 0085). The 90-day coupled run reproduced the 30-day
  root-zone quantiles to four significant figures; the pre-registered rule read that as *converged,
  so the 2.4–4.6× dry bias is real* and would have raised a training/inference mismatch with the
  slow-emulator line — meaning a retrain of the learned demography model and the trait sampler on a
  new soil-moisture basis. The rule's disjunction was incomplete: a static distribution can equally
  mean the *diagnostic* is saturated. It is — the plant-available-water fraction is clipped at both
  ends, and **94.0 % of land columns have every root-zone layer sitting at one of the two clips**,
  so the field is a 10-level step function of wetting-front depth (90 % of columns on just four
  front positions, 47.9 % bone dry, 90.8 % bit-identical over 60 extra simulated days). The
  "2.4–4.6× too dry" figure is retired as a fidelity statement and nothing was reported onward.
  Cause: the run carries no vegetation — forced by an upstream assertion that rejects zero vapour
  pressure deficit — and transpiration is the process that populates the range of the quantity being
  measured, not merely a feedback.

### Changed

- **Line O reorders its own work:** the vegetation spike and water-limited evapotranspiration now
  come *before* the soil-moisture comparison, because a transpiration sink is a precondition for
  that comparison being measurable at all rather than an independent milestone (ADR 0085). The
  re-entry gate is pre-registered in the same decision record, before the arm exists.
