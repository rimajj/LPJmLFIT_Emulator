---
status: "accepted"
date: 2026-07-28
deciders: "line E (session 1), autonomous per STEERING_PROMPT.md"
consulted: "lines/E/STATE.md (E2/E5), config/paths.yaml lpjml.energy_extra_inputs, ADR 0017 (self-contained SEB), ADR 0029 (E→M contract)"
informed: "line M (consumes the coupled driver's forcing), MEMORY.md"
---

# Component E's wind and surface pressure come from ISIMIP3a obsclim GSWP3-W5E5, remapped onto orderA cells

## Context and Problem Statement

Component E is the only part of the model that needs **wind** and **surface pressure**: `g_a` is a
Monin–Obukhov function of wind, and ρ/γ depend on psurf. LPJmL-FIT needs neither — it reads wind but never
uses it, and `photosynthesis.c` hard-codes `p = 1e5`. So the coupled runs have been driven with a **constant**
wind and a fixed psurf, which is recorded honest scope but blocks milestone E4: a model forced with a constant
cannot be scored against a tower that was not. Where do the two forcings come from, on the model's grid, and
how is the mapping proven rather than assumed?

## Decision Drivers

- **Physical consistency with the forcing the model already sees.** The run's `*_test.clm` (tas, pr, rsds,
  lwnet, huss) were built from GSWP3-W5E5 obsclim; mixing in a reanalysis from a different family would put
  wind/psurf out of step with the temperature and humidity in the same time step.
- **Two hard traps.** (1) orderA cell indices are not lat/lon-ordered — Hainich is 42490 in the global orderA
  grid, 28008 in the repo-default SINGLESITE grid, and *raw-GCM* cell 42490 is a different place entirely.
  (2) The model forcing is **noleap-365** while every candidate source uses a real calendar.
- **The gate must be falsifiable**, not "looks plausible": a round-trip against a file the LPJmL-FIT run
  actually read.
- E must not acquire a runtime dependency or a new global `.clm` before anything consumes one (ADR 0014,
  guardrail 4).

## Considered Options

- **ISIMIP3a obsclim GSWP3-W5E5 raw daily NetCDF** for both `sfcwind` and `ps`.
- **The raw SSP370 MPI-ESM1-2-HR NetCDFs** (`config/paths.yaml` `lpjml.inputs.ssp370_raw_gcm`) — the source
  the E2 milestone originally named.
- **The LPJmL-prepared obsclim `.clm`/`.nc`** (`sfcwind_gswp3-w5e5_obsclim_1901-2019.{clm,nc}`).
- **WFDE5_CRU `PSurf`** (`/p/projects/lpjml/input/historical/WFDE5_CRU/rawdata/PSurf_*`) for pressure.
- **Derive psurf from elevation** with a barometric formula.

## Decision Outcome

Chosen: **ISIMIP3a obsclim GSWP3-W5E5 daily NetCDF for both variables**, remapped onto orderA cells by
`scripts/remap_wind_psurf_cells.py`, with 29 February dropped and the mapping proven by a round-trip.

```
/p/projects/isimip/isimip/ISIMIP3a/InputData/climate/atmosphere/obsclim/global/daily/historical/GSWP3-W5E5/
    gswp3-w5e5_obsclim_{ps,sfcwind}_global_daily_<y0>_<y1>.nc
0.5°, lon 720 ascending (−179.75…), lat 360 DESCENDING (89.75…), proleptic_gregorian, ps [Pa], sfcwind [m s-1]
```

It is the only option that is **both** obsclim-consistent **and** complete: the raw SSP370 GCM set has no `ps`
at all (`hurs huss lwnet pr rsds sfcwind tas tasmax tasmin`), and there is no LPJmL-prepared `ps` anywhere on
the cluster. Cell → (lat, lon) comes from the run's `grid.nc` `cellid[lat, lon]`; the source axes are then
matched **by value with an exactness assertion**, never by arithmetic on an assumed ordering.

### The gate — all four checks PASS at all five orderA biome cells [VERIFIED 2026-07-28]

| check | what it proves | result |
|---|---|---|
| (a) index arithmetic vs an `xarray` label `.sel` | the lookup is not an indexing accident | `max|Δ| = 0` for `sfcwind` and `ps`, every cell |
| (b) obsclim `tas` NetCDF at (lat, lon) vs the model-grid `temperature_test.clm` cell-year | the lat/lon ↔ **orderA cell** mapping, against a file the C run actually read | `max|Δ| = 0.000 °C` over 365 days at all 5 cells (means −9.552 / 7.381 / 14.926 / 28.303 / 30.231 °C) |
| (c) this script's leap-dropped wind vs the LPJmL-prepared **noleap** `sfcwind…nc` | the 29-Feb handling | agrees to `3e-7 m/s` once matched to the prepared file's **0.01 m/s quantization** (raw `max|Δ| ≤ ½` step) |
| (d) Hainich grid cell vs the DE-Hai tower (PLUMBER2, ADR 0070) | physical plausibility, not equality | wind 3.246 vs 3.609 m/s (**−10.1 %**); psurf 97 522 vs 95 873 Pa (**+1649 Pa ⇒ the 0.5° cell mean sits ≈143 m below the tower's 430 m**) |

Deliverable: committed per-cell daily fixtures `test/testitems/references/wind_psurf_<biome>.csv`
(`year,doy,wind,psurf`; 2010–2019 × 365 d), the same cells and decade as the existing
`biome_forcing_<biome>.csv` — a **new** fixture family, so no committed baseline moves (guardrail 4).

### Consequences

- Good, because E4 can now force the closure with the real wind/psurf at the five biome cells, and (d) gives an
  independent, physically interpretable check of the remap against a tower.
- Good, because the round-trip (b) settles the orderA-mapping question **exactly** (0.000 °C), so any later
  per-cell input pipeline — including line M's multi-cell work — can reuse the same
  `grid.nc cellid → (lat, lon) → source axis` route with a proven test.
- Bad, because **SSP370 wind exists but SSP370 psurf does not**: the future-scenario branch of E stays on a
  fixed pressure until a GCM `ps` is sourced (or psurf is derived from elevation + a standard atmosphere, which
  would break the obsclim consistency this ADR buys). Historical E4 is unaffected.
- Bad, because the tower comparison (d) shows the grid-cell forcing is **not** the tower forcing: −10 % wind and
  +1.6 kPa pressure at Hainich. E4 must therefore drive the model with the **tower's** measured wind/psurf when
  scoring against tower fluxes, and use these remapped fields for the model-grid runs — conflating the two
  would attribute a forcing difference to the closure.
- Neutral: no global `.clm` is generated. Five cells × 10 years is what anything consumes today; writing a
  1.9 GB global daily wind `.clm` before a consumer exists would be speculative work (ADR 0014's discipline).
- **Integration point with line M (E5):** feeding these fields into the coupled driver touches `src/run.jl` /
  the `AtmForcing` construction, which **line M owns**. E supplies the fixtures + this ADR; the driver change
  lands on M's side, both together.

## Pros and Cons of the Options

### ISIMIP3a obsclim GSWP3-W5E5 (chosen)

- Good, because same product family as the model's existing forcing, has **both** variables, daily 1901–2019,
  and is a documented ISIMIP input with a published provenance.
- Bad, because it is a leap calendar on a lat-descending grid — handled, but it is the code's main risk surface.

### Raw SSP370 MPI-ESM1-2-HR NetCDFs

- Good, because it is the only source for the future scenario, and it does carry `sfcwind`.
- Bad, because it has **no `ps`**, and it is a GCM realization rather than an observational reanalysis — wrong
  basis for a historical validation against towers (it would only be right for the OOD branch).

### LPJmL-prepared obsclim `.clm`/`.nc`

- Good, because already noleap and already on an LPJmL grid — zero calendar work.
- Bad, because there is **no prepared `ps`**, and the prepared wind is **quantized to 0.01 m/s**; keeping it as
  the *independent check* (c) rather than the source preserves full precision and exercises the calendar code
  that `ps` needs anyway.

### WFDE5_CRU `PSurf`

- Good, because it is 0.5° daily surface pressure in Pa and is on the cluster.
- Bad, because it ends in 2018 (the model window runs to 2019) and belongs to a different forcing family than
  the run's own climate.

### Derive psurf from elevation

- Good, because it always works and needs no data.
- Bad, because it has no weather — no synoptic pressure variability at all, which is precisely the signal E's
  ρ/γ terms would sample; acceptable only as the documented fallback it already is.

## More Information

- Script: `scripts/remap_wind_psurf_cells.py` (env `CELLS` / `YEARS` / `CHECK` / `NO_WRITE`; ≈3 min for
  5 cells × 10 yr — submit with `scripts/sbatch_python.sh E-windps`). Procedure captured in the
  `obsclim-cell-remap` skill. Paths recorded in `config/paths.yaml` `lpjml.energy_extra_inputs`.
- Trap worth its own line: LPJmL `.clm` **datatype codes are 0-based** (`0=byte 1=short 2=int 3=float
  4=double`, `build_transient_boundary.py::_DT`). An off-by-one here reads `temperature_test.clm`'s float32 as
  int32 and reports ~5.9e8 "°C" — which is how check (b) first failed.
- Validated by: the four-part gate above (re-runnable), and later by **E4** using these fields.
- Revisit if: an SSP370 (or any GCM) `ps` is sourced, or a global `.clm` becomes necessary — then supersede.
