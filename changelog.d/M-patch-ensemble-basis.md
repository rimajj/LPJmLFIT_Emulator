### Changed

- **Line M / ADR 0057 — the production 5-biome coupled driver runs the PATCH ENSEMBLE, not the modal
  patch, and the CI signatures were regenerated for it.** LPJmL-FIT simulates each cell as 25 replicate
  patches and every gridded output it writes is the patch-ensemble mean; ADR 0053 made that the M-line
  comparison basis and moved the oracle probes to it, but `scripts/run_coupled_biomes.jl` and the CI gate
  pinning its per-cell signatures (`biome_coupled_tests.jl` item 2) were left driving the single **modal**
  (= densest) patch. Both now run every patch independently — its own core, soil water and energy closure —
  and average the outputs. This is a deliberate baseline move under guardrail 4, in its own commit.

  **The artifact is small in energy and large in carbon** (`scripts/biome_ensemble_pin_probe.jl`, job
  1716587, both bases measured in one run, 2 yr): `mod/ens` is **1.009–1.057 on LE** but up to **1.331 on
  GPP** (boreal). LE is water- or energy-limited in all five climates and therefore buffered against canopy
  density; GPP is not. The density artifact does **not** predict the flux one — `semiarid_sahel` has the
  largest FPC artifact (1.588×) and the smallest flux artifact in the set (GPP **0.990**: extra leaf area
  buys nothing when water is the constraint) — and the ratio is horizon-dependent, flipping sign at the
  driver's 10-year horizon for the Sahel (0.821) and mediterranean (0.961). It can never be carried as a
  per-cell correction factor; re-run on the ensemble instead.

  The same job reproduced the OLD committed pins to every printed digit on the modal basis, which is what
  makes this a measured basis change rather than a re-record of whatever the new code prints. The new pins
  stay a driver-level fallback detector: minimum pairwise separation 13.2 % on LE (gate rtol 2 %) and 27.0 %
  on GPP (rtol 3 %). The ensemble costs **10.6 s** for the whole five-cell CI set, and the gate now asserts
  the Phase-4 energy closure **per patch** — 25× more closure evidence than before.

  Five gates/probes stay single-member **on purpose**, each carrying the reason at the reader (ADR 0057 §4):
  the M2 conservation/determinism gate, the rollout-stability and resilience-battery gates (member-invariant
  structural claims), `scripts/wscal_leafon_probe.jl` (so it still reproduces ADR 0051's published numbers)
  and `scripts/boreal_soilice_probe.jl` (a seasonal shape, not a level).

  Rule recorded: **a canopy basis is part of a result's reference basis (guardrail 7) — state it where the
  number is produced**, because a modal-patch number and an ensemble number are not comparable and nothing
  in the code makes the difference visible.
