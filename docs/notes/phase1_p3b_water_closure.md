# Phase 1 / P3b — Daily-output re-run + WATER-CLOSURE gate (RESULT: PASSED)

_Date: 2026-07-16 (session 3). Run: `daily_2000_2002_boreal_val_c45000_45999_seed1`._

## What was done

Enabled **daily output** (no recompile) and re-ran the Historical transient restarting from the
**spinup-end `restart_1999.lpj`** (not `restart_2019`) over a **contiguous cell subset** of the global
67,420-cell grid, then verified water closure. This is the Phase-1 gate that the existing (annual-only)
ground truth could not test.

- **Cells:** `startgrid=45000 … endgrid=45999` — 1,000 contiguous boreal-forest cells (lat ≈ 54–56 °N,
  forest_frac = 1.00). Chosen as the *most demanding* single test: it exercises transpiration,
  interception, soil evaporation, runoff **and** deep seasonal snow (ΔSWE) — plus permafrost.
- **Years:** 2000–2002 (3 full seasonal cycles), `nspinup:0` (spinup skipped via the existing restart).
- **Daily outputs (mm/day):** prec, transp, evap, interc, runoff; plus swe (mm), swc (23-layer fractional
  saturation), rootmoist (mm), whc_nat, pet, npp, gpp.
- **Cost:** 1,000 cells × 3 yr on 16 tasks → **83 s wall**, ~376 MB output. (Option **(b)** of the owner's
  P3b guidance — a cheap subset "box", not the full-global run.)
- Reproduce: `scripts/run_daily_subset.sh` (generates + `lpjcheck`-validates + submits);
  `scripts/water_closure_check.py` (the analysis below).

## Evidence

### (1) DEFINITIVE — LPJmL's own per-cell/year water balance passed
The binary is built with `-DSAFE` (Makefile.inc:22), so `check_fluxes.c` enforces the per-cell water
balance every year — `|balanceW| ≤ 1.5 mm/yr` — and **aborts the run** (`INVALID_WATER_BALANCE_ERR`)
otherwise. The run **terminated cleanly** ("lpjml successfully terminated, 1000 grid cells processed"),
with **no water-balance error** in the logs (only 3 benign optional-key warnings). A clean run over
1,000 cells × 3 yr therefore *is* the closure proof. For this configuration the enforced identity is:

```
prec == transp + evap + interc + runoff + excess_water + Δ(soil water + snow + litter moisture)
```

(river_routing:false, landuse:no ⇒ no lake / reservoir / irrigation / discharge terms — all verified
zero in code, not just config).

### (2) OUTPUT reconstruction — daily fluxes integrate exactly to the annual budget
Per-cell daily fluxes summed over each year reproduce LPJmL's own annual `globalflux` aggregate to 5
significant figures (units + area handling validated):

| var | daily-sum reconstruction (2000) | globalflux (2000) |
|---|---|---|
| transp | 372.41 km³ | 372.41 km³ |
| evap   | 174.26 km³ | 174.26 km³ |
| interc |  48.03 km³ |  48.03 km³ |
| prec   | 1328.97 km³ | 1328.97 km³ |
| **NPP** (carbon) | 0.7339 ×10¹⁵ gC/yr | 0.7339 ×10¹⁵ gC/yr |

Cumulative water balance over the 3 years, per cell — `|Σprec − Σ(transp+evap+interc+runoff)| / Σprec`:

| percentile | fractional imbalance |
|---|---|
| median | **2.7 %** |
| p90 | 7.0 % |
| p99 | 12.2 % |
| max | 21.0 % |

The residual is the **net multi-year storage drift + `excess_water`** (permafrost thaw), *not* an
unclosed budget — LPJmL's SAFE check independently guarantees closure to ≤1.5 mm/yr. Mean annual
partition: prec 737, ET 326, runoff 401, residual (storage change) ≈ 10 mm/yr.

### (3) SELF-CONSISTENCY
- `swc` fractional saturation ∈ [0.08, 0.99] (dimensionless, in range).
- `swe` snowpack builds to ~1140 mm and returns to within 6 mm of its start over 3 full years (Δ≈0).
- All daily fluxes ≥ 0 (runoff min = −7×10⁻¹⁵, numerical zero).
- Daily NPP integrates to annual NPP (ratio 1.000, all 3 years) — carbon self-consistent sub-annually
  too (the annual carbon-closure gate passed in session 2).

## Load-bearing facts verified against LPJmL source (`/home/jamirp/lpjml56fit`)

1. **Restart a contiguous cell subset from a full-grid restart works.** `startgrid`/`endgrid` are
   **0-based positional row indices** into the grid/soil files (not lat/lon, not 1-based). The restart
   read seeks per-cell via an index vector, so any contiguous sub-range works and is
   MPI-decomposition-independent. Requires the **byte-identical** grid/soil/input files and matching
   physics config as the run that wrote the restart. (openrestart.c:193-203, fwriterestart.c:96-119,
   fscanconfig.c:1055-1112.) — *adversarially verified.*
2. **Daily output = runtime only**, `"timestep":"daily"` placed **inside** each output entry's `"file"`
   object. transp/evap/interc/runoff/prec/pet/swc/npp/gpp are all daily-capable (default monthly).
   (fscanoutput.c:390, readfilename.c:240-250.)
3. **Water balance is enforced ANNUALLY, not daily** (check_fluxes.c, once per year). `swc` is
   **fractional saturation** = water/`wsats`; absolute soil water in mm needs the per-layer `wsats`,
   which LPJmL does **not** expose as an output. `swe` (snow) and `rootmoist` are in mm. `excess_water`
   (permafrost thaw) has no gridded output — the only unobservable residual term.
4. **Correct module set** for this binary: `intel/oneAPI/2024.0.0 udunits/2.2.28 json-c/0.13.1
   openssl/3.6.0 netcdf-c(4.9.2) curl/8.4.0 expat/2.5.0`. **json-c/0.13.1** (→ `libjson-c.so.4`) — the
   older historical `.sh` script's `json-c/0.17` (→ `.so.5`) fails to load. `module purge` first.

## Implication for the hybrid (F-core) water budget
A fully-closed **daily** water storage term needs the per-layer saturated capacity `wsats` (to convert
`swc` → mm) or an added absolute-soil-water output; LPJmL's conservation itself is only checked/closed
**annually**. Carry this into the F-core data spec: either reconstruct `wsats` from soil params, add a
`wsat`/absolute-soil-water output, or define the F-core water conservation at the annual cadence LPJmL
guarantees.

## Full-global daily dataset (2026-07-16, session 3) — generated + closure re-confirmed at scale

After the subset gate passed, the **full-global daily F/E training dataset** was generated:
`daily_2000_2019_global_c0_67419_seed1` — **all 67,420 cells × 2000–2019**, restarted from the seed1
spinup-end `restart_1999.lpj` (so it reproduces the existing seed1 Historical trajectory at daily
resolution). SLURM job 1448860: 512 tasks / 4 exclusive nodes, **COMPLETED in 31m48s**, **186 GB**
daily output (prec/transp/evap/interc/runoff/swe/swc/rootmoist/whc_nat/pet/npp/gpp). Same generator
(`scripts/run_daily_subset.sh` with `STARTGRID=0 ENDGRID=67419 … TIME=03:00:00 EXCLUSIVE=yes`).

**Water closure confirmed at global scale:**
- **DEFINITIVE:** run terminated cleanly ("67420 grid cells processed"), **no water-balance error** —
  LPJmL's `-DSAFE` per-cell/year balance (≤1.5 mm/yr) held for **all 67,420 cells across all 20 years**.
- **Output reconstruction** (`artifacts/metrics/p3b_water_closure_global_c0_67419.json`): daily fluxes
  integrate to the run's own annual `globalflux` to ~5 sig figs (2000: transp 50050.6 vs 50050.7 km³,
  evap 14587.6 vs 14587.7, interc 8830.3 vs 8830.3, prec 131649.6 vs 131650.0). Cumulative per-cell
  `|Σprec − Σ(ET+runoff)|/Σprec`: **median 0.87 %**, p90 3.7 %, p99 10.7 % — *tighter* than the boreal
  subset (the global set is dominated by cells without deep snow/permafrost). Mean annual: prec 773,
  ET 420, runoff 348, residual (storage change) 4.6 mm/yr.
- **Sanity:** swc ∈ [0.017, 0.997] (fractional ✓); fluxes ≥ 0; snow builds/melts.
- **Caveat:** the per-cell fractional-imbalance *max* is ~112 % on a few cells — arid cells where
  Σprec≈0 (ratio ill-conditioned) and high-latitude permanent-ice cells (large snow accumulation +
  `excess_water`); the *absolute* balance there is still ≤1.5 mm/yr by the SAFE check. The fractional
  metric is only meaningful where prec is non-trivial.

Reproduce the analysis (memory-safe / dask-lazy): `python scripts/water_closure_check.py <run_dir>`.

## Next
Both Phase-1 gates (carbon + water) pass, and the **full-global daily dataset now exists** on
`/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output` (186 GB) — the daily
forcing→flux+storage+carbon data the F-core / E-layer will train on. Next: Phase 2+
(`DEVELOPMENT_PLAN.md` §6). For the F-core water budget, remember closure is enforced **annually** and
`swc` is fractional (no `wsats` output) — see the "Implication" note above.
