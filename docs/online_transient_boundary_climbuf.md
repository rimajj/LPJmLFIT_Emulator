# Online transient boundary — the coupled-run Climbuf (design sketch)

**Status:** design only (not built). The offline transient boundary (ADR 0026/0027) ships as a pre-baked
per-(cell,year) `boundary_series`; this note specifies its **online-coupling** counterpart — a per-cell
trailing climate buffer ("Climbuf", mirroring LPJmL-FIT's own ~20-yr `Climbuf`) that computes the boundary
live from the climate F sees, for when the online coupled driver (SpeedyWeather ↔ S/F/E) exists. Reviewed
against `src/run.jl`, `src/components/slow.jl`, `src/interface.jl`, and `scripts/build_transient_boundary.py`.

## Why it's needed (and why it's cheap)

Offline, S reads a fixed vector (`boundary`) or an indexed per-year vector (`boundary_series`) baked from the
`.clm` forcing. Online, climate evolves as the run proceeds, so the boundary (`gdd5`, `tas_cold_month`) must
be recomputed each year from the climate F actually consumed — otherwise it is frozen at the initial
climatology (the static case, which ADR 0027 keeps only as the fallback). Cost is negligible: the daily
temperature is already in hand (F uses it for photosynthesis); the Climbuf adds ~a few thousand FLOPs per
cell per year against F's millions/cell/year daily core (≈ 0 % slower). The cost is the code below, and it is
the *faithful* implementation.

## The contract: it MUST reproduce the offline builder

`scripts/build_transient_boundary.py` defines the offline boundary bit-for-bit (verified: a W=20 window
ending 2019 reproduces the static Hainich `gdd5=1863.695` / `tas_cold=0.2184`). The online Climbuf must
compute the SAME quantities so train (offline table) and inference (online) stay consistent (ADR 0023):

- **Monthly climatology** over the trailing window: `T_m` = mean daily temperature in calendar month `m`
  (noleap 365-day, `DAYS_PER_MONTH = [31,28,31,30,31,30,31,31,30,31,30,31]`), averaged over the last `W`
  years. (Per-year-monthly-then-average-over-years == daily-average-over-window, since every noleap year has
  identical days per month — the identity the offline builder relies on.)
- **`gdd5 = Σ_m max(T_m − 5, 0) · DAYS_PER_MONTH[m]`** (Thom 1966 monthly method — identical to
  `climclusterpy` / the offline `gdd5_tcm`).
- **`tas_cold_month = min_m T_m`.**
- `soil_depth` static per cell; `co2 = 369` constant (ADR 0004).
- `W ≈ 20` (matches FIT's Climbuf; the offline default). `W→∞` is the static boundary.

## Data structure

```julia
mutable struct ClimBuf{T}                       # one per cell (lives beside FluxDrivenSlowEmulator)
    monthly_ring::Matrix{T}       # (W, 12) ring of past years' monthly-mean temperature (°C)
    filled::Int                   # years accumulated so far (< W during spin-up)
    head::Int                     # ring write cursor
    # current-year accumulators, updated during the daily loop:
    month_sum::Vector{T}          # (12,) running sum of daily T in each calendar month
    month_cnt::Vector{Int}        # (12,) day count per month (→ DAYS_PER_MONTH at year end)
    doy::Int                      # day-of-year cursor (1..365), maps to the calendar month
end
```

## Integration into the coupled loop (`run.jl`)

The coupled driver already holds the daily `AtmForcing` (with `tair`) and calls `annual_step!` /
`reconcile_demography!` once per model year (`run.jl:155/160`). The Climbuf slots in with **no change to the
`FToS` interface** — the driver owns it and writes `s.boundary`, exactly mirroring how the offline path
advances `boundary_series`:

1. **Daily** (inside the `couple_day!` / daily loop): `climbuf_accumulate!(cb, forcing.tair, doy)` — add
   `tair` (converted to °C) to `month_sum[month_of(doy)]`, bump `month_cnt`. One add per day. (Or: read F's
   own monthly temperature aggregation if F exposes it — avoids a second pass.)
2. **Year end, BEFORE `reconcile_demography!`** (so the DRF row and the copula's `live_flux_cond` see this
   year's boundary — the same ordering the offline `boundary_series` update uses at `slow.jl`'s top of
   `reconcile_demography!`):
   ```julia
   Tm = climbuf_finalize_year!(cb)          # (12,) this year's monthly means; push to ring; reset accumulators
   gdd5 = sum(max(Tm[m] - 5, 0) * DAYS_PER_MONTH[m] for m in 1:12)
   tcm  = minimum(view(climbuf_window_climatology(cb), :))   # trailing-window monthly clim → min
   s.boundary = T[gdd5_W, tcm_W, soil_depth, 369.0]          # gdd5_W/tcm_W from the WINDOW clim, not just this year
   ```
   (Precisely: recompute the window monthly climatology `mean over the filled ring rows`, then gdd5/tcm from
   THAT — the trailing-W-yr boundary, not the single current year.)

`FluxDrivenSlowEmulator` needs **no new field** if the driver sets `s.boundary` each year (as the offline
driver would from `boundary_series`). Alternatively, give the emulator an optional `climbuf::Union{Nothing,
ClimBuf}` and a `boundary_fn` hook so it self-updates — but keeping it driver-side matches the offline
mechanism and keeps S's dependency surface minimal (it already only reads `s.boundary`).

## Spin-up / edge cases

- **First `< W` years:** the ring is partially filled (`filled < W`); use the mean over the filled rows (a
  shrinking window) — identical to the offline builder's short-window handling for the earliest target years.
  Optionally seed the ring from an initial climatology so year 1 already has a full window.
- **Coupled cold start:** the initial `s.boundary` (year 0) should be the initial-climatology boundary (the
  static value), then the Climbuf takes over — consistent with `age0`/`n_init` seeding.

## Guarantees

- **Conservation:** the boundary is a conditioning feature only (no carbon/water/energy) — `vegc_full_ind`
  and every closure are boundary-independent, so the Climbuf cannot affect conservation (ADR 0026 §Consequences).
- **Determinism:** pure function of the climate stream + `W`; no RNG.
- **Train/inference consistency:** by construction identical to `build_transient_boundary.py` (same Thom
  monthly gdd5 + coldest-month + trailing-W window) — the load-bearing requirement.
- **Fallback:** if the Climbuf is absent, `s.boundary` stays at its initial value = the static boundary
  (ADR 0027's documented fallback), and the run is still valid (flux-driven generalization, ADR 0020).

## Test plan (when built)

1. **Offline-parity unit test:** drive the Climbuf with a cell's daily `.clm` stream and assert
   `s.boundary` per year == `build_transient_boundary.py`'s per-(cell,year) row (bitwise, openlibm).
2. **Conservation + determinism** in the coupled loop (as the ADR-0026 testitem: constant series == static
   byte-identical; a warming stream shifts the gate).
3. **Spin-up:** short-window years match the offline shrinking-window values.
