# ADR 0052 — F_diff has no soil ice: the confirmed cause of the boreal water-stress residual

- **Status:** accepted (2026-07-30)
- **Line:** M (multi-cell coupled S+F+E, P3) — ADR block 0050–0069
- **Resolves:** the `[ASSUMPTION]` ADR 0051 left open (its own recorded falsifiable test, now run).
  **Does not supersede** ADR 0051 — the leaf-on `wscal` fix stands unchanged.
- **Code change:** none. This is a measurement + a scoping decision for M3.

## Context

ADR 0051 fixed the `water_stress` conditioning shift in 4 of 5 biome cells but not `boreal_siberia`
(52059): the C says it *is* water stressed (0.3146) while the C-faithful leaf-on index gives exactly
**0.000**, the `min(…,1)` cap binding on 100 % of days. The leading hypothesis was tagged `[ASSUMPTION]`
— the C's `wr` is over **plant-available** water and the C's soil carries ice, while F_diff has no
soil-ice or permafrost state — together with the exact test to run.

## Decision / evidence

Ran that test. `scripts/boreal_soilice_diagnosis.py` recovers the C's own root-zone plant-available
fraction (`rootmoist / Σ_{l<3} whc_nat[l]·soildepth[l]` — per ADR 0035 `rootmoist` is the **only** C output
carrying the model's `w`; `swc` is not invertible), and `scripts/boreal_soilice_probe.jl` prints the
emulator's `root_zone_soilmoist` for the identical quantity. Monthly climatology, 2010–2019:

| cell | source | Jan | Feb | Mar | Apr | Jul | Sep | Dec |
|---|---|---|---|---|---|---|---|---|
| **boreal_siberia** | **C** | **0.000** | **0.000** | **0.000** | **0.001** | 0.437 | 0.525 | **0.004** |
| **boreal_siberia** | **F_diff** | **0.761** | **0.748** | **0.730** | **0.762** | 0.688 | 0.764 | **0.789** |
| temperate_hainich | C | 0.967 | 0.916 | 0.955 | 0.962 | 0.877 | 0.877 | 0.981 |
| temperate_hainich | F_diff | 0.970 | 0.977 | 0.949 | 0.865 | 0.700 | 0.703 | 0.969 |
| mediterranean_iberia | C | 0.864 | 0.912 | 0.843 | 0.744 | 0.369 | 0.260 | 0.702 |
| mediterranean_iberia | F_diff | 0.764 | 0.790 | 0.744 | 0.678 | 0.239 | 0.168 | 0.658 |
| semiarid_sahel | C | 0.533 | 0.527 | 0.525 | 0.535 | 0.770 | 0.821 | 0.544 |
| semiarid_sahel | F_diff | 0.361 | 0.322 | 0.312 | 0.317 | 0.564 | 0.747 | 0.375 |

**CONFIRMED.** The C's boreal root-zone plant-available water is **exactly zero for Nov–Apr** — every drop
in the top metre is ice, which is precisely what `rootmoist = Σ w[l]·whcs[l]` reports when `w` excludes
ice — while F_diff's sits flat at **0.67–0.91 all year**. So F_diff's `wr` never collapses, `emax·wr`
exceeds the leaf-on demand on every day, and the leaf-on `wscal` is pinned at **1.000 in all twelve
months** (measured). It is not a bad `wscal`; it is the right `wscal` of a soil column that cannot freeze.

**A SECOND, DISTINCT residual, newly identified by the same measurement.** In the two dry cells F_diff's
root-zone `w` is systematically **drier than the C's** — Sahel Jan 0.361 vs 0.533, Jul 0.564 vs 0.770;
mediterranean Jul 0.239 vs 0.369 — with the *same seasonal shape*. That, not the `wscal` definition, is
what remains of their ADR-0051 gap (Sahel still 36.5× the noise floor, mediterranean 7.5×), and it points
the opposite way from boreal: F_diff **over**-stresses where it runs too dry. Hainich and Amazon agree
well (both ≥0.86 in winter), which is why the ADR-0051 fix landed cleanly there.

So the five-cell `water_stress` picture is now fully attributed: **ADR 0051** (the `wscal` *definition*)
explains Hainich and Amazon completely; **missing soil ice** explains boreal; **an F_diff root-zone water
balance that runs too dry in dry climates** explains mediterranean and Sahel. Three separate causes, one
of them fixed.

## Consequences

- **M3 must report the boreal cell's `water_stress` as a known, quantified bias, not as fidelity.** A
  cold-cell coupled demography score is conditioned on `water_stress ≡ 0` where the C's is 0.31. Do not
  average it into a headline per-cell number without saying so; the same caveat applies to any cell with a
  seasonally frozen root zone, i.e. much of the boreal/permafrost belt in a global run.
- **Soil ice is a real F-core feature, deliberately NOT started here.** It needs a frozen-water state per
  layer, a freeze/thaw energy path, and `w` excluding ice everywhere `wr` is formed — and it must be
  opt-in and default byte-identical (guardrail 4). Scoping it inside M3 is exactly the entanglement ADR
  0051's milestone discipline exists to prevent. The C's own machinery to port when it is staffed:
  `ice_depth`/`ice_fw` in `soil.h`, and `getrootdist(…, config->permafrost)`.
- **The dry-cell root-zone bias is a separate, independently actionable finding** with its own reference
  basis already established (the table above). It is the higher-value of the two for a *global* run, since
  semi-arid cells are far more numerous than permafrost ones. Diagnose it on its own with
  `residual-diagnosis`; the candidate terms are the `_infiltrate` cascade (no surface/infiltration-excess
  runoff — a documented v2 item), `_soil_evap`, and the absence of the C's free-water/`w_fw` reservoir.
- **Reusable method:** the C's `rootmoist` + `whc_nat` give a per-cell, per-day reference for the
  emulator's root-zone water **anywhere on the global grid**, with no new HPC run. That is the cheapest
  available check on F_diff's soil water balance and should be the first thing any future soil-water
  residual is measured against.
