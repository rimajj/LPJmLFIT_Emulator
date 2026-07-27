# Online transient boundary — the coupled-run Climbuf

**Status: BUILT** (2026-07-27). Implemented as `ClimBuf` in **`src/climbuf.jl`** and wired into the coupled
driver via the opt-in `run_coupled_cell(...; climbuf=)` kwarg (`src/run.jl`); gated by
**`test/testitems/climbuf_tests.jl`** (offline parity + coupled wiring) against the committed Hainich fixture
`test/testitems/references/climbuf_hainich_{monthly,boundary_w20,daily_2010}.csv`
(`scripts/build_climbuf_parity_fixture.py`). It does not require SpeedyWeather — it runs inside the existing
multi-year `run_coupled_cell`; the SpeedyWeather driver (P4) will use the same object. The sections below are
the design of record; the "when built" notes are now satisfied (see §Verification outcome at the end).

The offline transient boundary (ADR 0026/0027) ships as a pre-baked per-(cell,year) `boundary_series`; this
is its **online-coupling** counterpart — a per-cell trailing climate buffer ("Climbuf", mirroring LPJmL-FIT's
own ~20-yr `Climbuf`) that computes the boundary live from the climate F sees. Reviewed and built against
`src/run.jl`, `src/components/slow.jl`, `src/interface.jl`, and `scripts/build_transient_boundary.py`.

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

## Test plan (satisfied — see the outcome below)

1. **Offline-parity unit test:** drive the Climbuf with a cell's daily `.clm` stream and assert
   `s.boundary` per year == `build_transient_boundary.py`'s per-(cell,year) row.
2. **Conservation + determinism** in the coupled loop (as the ADR-0026 testitem: default off ⇒ `s.boundary`
   constant; a warming stream shifts the gate).
3. **Spin-up:** short-window years match the offline shrinking-window values.

## Verification outcome (2026-07-27)

Gated by `test/testitems/climbuf_tests.jl` against the committed Hainich (cell 42490) fixture:

- **Offline parity — the load-bearing train/inference contract.** Feeding the buffer the historic Hainich
  climate reproduces `build_transient_boundary.py` to **float32-summation-order** precision (NOT claimed
  bitwise: numpy's pairwise reductions vs the buffer's sequential ones): daily→monthly max\|Δ\| **1.9e-6 °C**;
  per-year trailing-window boundary (2000–2019) max\|Δgdd5\| **3.7e-4** (of ~1800, rel ~2e-7) and max\|Δtcm\|
  **1.8e-7 °C**. The W=20 window ending 2019 reproduces the committed production DRF meta boundary
  (**gdd5=1863.695, tas_cold=0.2184**) — so the online buffer and the offline `boundary_series` are the same
  boundary. These residuals are orders of magnitude below any DRF split resolution.
- **Coupled wiring.** `run_coupled_cell(...; climbuf=)` folds F's daily air temperature (K→°C), refreshes
  `s.boundary` each year end BEFORE `reconcile_demography!`, and: drives `s.boundary` to the
  offline-consistent trailing value (≠ the initial static one), preserves the static `soil_depth`/`co2` tail,
  conserves carbon at the S↔F handoff (resid ≤ 1e-6·C_scale) and energy closure (< 1e-6 W/m²), is
  deterministic (identical `s.boundary` + demography trajectory across runs), and a **+2 K/yr warming stream
  raises the recomputed gate** (higher gdd5, milder coldest month). Default `climbuf=nothing` leaves
  `s.boundary` untouched (byte-identical — ADR 0027's static fallback).
- **Guards:** a Climbuf is rejected with a baked `boundary_series` (mutually exclusive), with a non-flux
  emulator, or a non-365-day year (the noleap month binning).

**Follow-up (not blocking):** populate the `SharedState` Climbuf-mirror fields (`climbuf_mtemp20` …) from the
same buffer so E's soil-temp initialization can consume the live 20-yr climatology; source the spin-up
climatology for the SpeedyWeather cold start (P4).
