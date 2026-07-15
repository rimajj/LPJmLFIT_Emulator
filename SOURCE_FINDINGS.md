# LPJmL-FIT Source-Code Findings (feasibility investigation)

**Model:** LPJmL 5.6.004 + FIT ("flexible individual traits") extensions + project "waldspektrum" parameterizations.
**Repo root:** `/home/jamirp/waldspektrum` (this is a working copy of the PIK LPJmL git tree).
**Active run config:** `lpjmlfit.js` → includes `input_GSWP3-W5E5.js`, `param_lpjmlfit.js`, `par/pft_lpjmlfit.js`, `par/lpjparam_fit.js`.
**Key switches (as configured):** `"individual": true` (FIT mode on), `"npatch": 25`, `"radiation": "radiation"` (net-radiation input mode), `"landuse": "no"` (natural vegetation only), `"with_nitrogen": "no"`, `"permafrost": true`, `"new_phenology": true`, `"fire": "fire"` (GlobFIRM, *not* SPITFIRE).

All line numbers below were read from the working tree and, for the load-bearing facts (daily output, absence of an energy balance), verified directly. Treat the specific line numbers as accurate-at-time-of-writing pointers; the *facts* are verified.

---

## Executive summary (the five feasibility questions)

| # | Question | Answer |
|---|----------|--------|
| Q1 | Internal temporal resolution & enable-able daily outputs | **Daily** physics (no sub-daily loop). Daily output of essentially all flux/pool variables is a **runtime config flag** (`"timestep":"daily"`), **no recompile**. |
| Q2 | Compute cost of daily-output re-runs | Adds only I/O volume (≈365× the annual write frequency for chosen variables); CPU cost of the *simulation* is unchanged (the model already integrates daily). Cheap for the prototype ensemble; scales linearly with cells×years for larger sets. |
| Q3 | Forcing consumed & ET/energy scheme | Uses tas, precip, shortwave-down, **net** longwave, specific humidity (→VPD, required), CO₂. **Does not use wind or surface pressure** (pressure hard-coded). ET = **Priestley–Taylor equilibrium / demand–supply**; **no surface energy balance, no sensible heat, no skin temperature.** |
| Q4 | State vector, carbon pools, allometry/diagnostics | Fully enumerated below. 7 C(+N) pools per tree individual; soil SOM fast/slow × 22 layers; litter per PFT; 23-layer soil water + ice + enthalpy thermal state; single snow store. Allometry: pipe/latosa + Reinicke; LAI = leafC·SLA/crownarea; FPC = Beer–Lambert. |
| Q5 | Persistent patch/stand ID across years | **No explicit ID field**, but in the active `landuse="no"` config the tuple **`(cell, patch-index)` is a stable positional key every year** (the `ind` output already emits it), and each tree carries a persistent unique `tree->index`. Autoregressive lagged-state design is feasible. |

**Two findings dominate the design decision:**

1. **Daily flux/pool output is trivially available** (config-only). This removes the constraint in the handover §4 that originally motivated the hybrid route.
2. **LPJmL-FIT has no surface energy balance.** It produces latent heat (via ET), ground-heat storage (soil enthalpy), water fluxes, and carbon fluxes — but **never** sensible heat `H`, net radiation closure, or a skin/surface temperature `T_skin`. These *cannot be emulated from the model* and must be **added** by a new energy-balance closure module. This is true for both the emulator and hybrid routes and is the single most important architectural consequence.

A third, quieter constraint: **the model timestep is one day.** There is no sub-daily physics anywhere (the only sub-daily loop is a numerical substepping inside the soil heat-conduction solver, driven for stability, not by sub-daily forcing). A genuinely sub-daily coupled land component therefore cannot be *trained* purely from LPJmL-FIT; the realistic target is **daily coupling** with an added, physically-based diurnal-downscaling layer.

---

## Q1 — Internal temporal resolution & which daily outputs can be enabled

### Q1a. Integration timestep is one day

The main loop is `year → month → day → (cell → update_daily)`:

- `src/lpj/iterate.c` — outer year loop.
- `src/lpj/iterateyear.c`: `foreachmonth(month)` → `foreachdayofmonth(dayofmonth,month)` → `for(cell...) update_daily(...)`. River routing (`drain`) runs after each day.

Within one day, **all balances are computed exactly once**:
- Radiation / equilibrium-evaporation demand (`petpar*` via `radiation.c`).
- Snow, soil temperature, heterotrophic respiration (`update_daily.c` → `littersom`).
- Photosynthesis → GPP → NPP, once per PFT (`daily_natural.c`).
- Water balance, once (`daily_natural.c` → `waterbalance`).

**No sub-daily loop exists for photosynthesis, water, or PET.** The *only* sub-daily stepping is an adaptive substep inside `src/soil/apply_heatconduction_of_a_day.c` (explicit enthalpy scheme; chosen for numerical stability when layers straddle 0 °C). It does not read sub-daily climate and produces no sub-daily output. **Consequence: the finest physically meaningful output resolution is daily.**

### Q1b. Daily output is a per-variable runtime option (no recompile) — VERIFIED

Mechanism (verified directly):

- Every output variable carries an `int timestep` field (`include/output.h`).
- `src/lpj/fscanoutput.c:391` sets `config->withdailyoutput = TRUE` automatically whenever *any* requested output has `timestep == DAILY`.
- `src/lpj/iterateyear.c:207` gates the daily write on that runtime boolean; `fwriteoutput` is called three times per year (DAILY, MONTHLY, ANNUAL), and `iswrite2` (`fwriteoutput.c`) emits each variable only on the call matching its configured timestep.
- `src/lpj/getmintimestep.c` caps **only** `VEGC, VEGN, GLOBALFLUX, CFTFRAC, CFTFRAC2, SDATE, SDATE2` at ANNUAL; the `default` for every other index is `DAILY`. (`isannual_output.c` additionally forces `CFTFRAC/SDATE/HDATE/SYEAR/IND` annual.)
- The min-timestep check is **soft** (`fscanoutput.c` prints a warning under verbosity but assigns the requested timestep anyway), so requesting daily on a capped variable warns rather than aborting — but avoid it; use the daily-capable equivalents.

The `#define DAILY_OUTPUT` seen (commented out) in `lpj.js`/`lpjmlfit.js` is only a JSON-preprocessor convenience that pulls in the legacy per-CFT `d_*` diagnostic block; it is **not** referenced by any C source and is **not** required for daily output of the normal variables.

### Q1c. How to declare a daily output (config)

Output is a JSON array `"output"` of `{ "id", "file" }` records. `par/outputvars.js` provides each id's default `timestep`/`unit`/`scale`/NetCDF `var`; the run config's `"file"` object overrides them. To emit at daily resolution, add an explicit daily timestep and a per-day unit:

```jsonc
{ "id":"npp",     "file":{ "fmt":"cdf", "timestep":"daily", "unit":"gC/m2/day", "name":"output/npp_daily.nc" }},
{ "id":"transp",  "file":{ "fmt":"cdf", "timestep":"daily", "unit":"mm/day",   "name":"output/transp_daily.nc" }},
{ "id":"evap",    "file":{ "fmt":"cdf", "timestep":"daily", "unit":"mm/day",   "name":"output/evap_daily.nc" }},
{ "id":"interc",  "file":{ "fmt":"cdf", "timestep":"daily", "unit":"mm/day",   "name":"output/interc_daily.nc" }},
{ "id":"runoff",  "file":{ "fmt":"cdf", "timestep":"daily", "unit":"mm/day",   "name":"output/runoff_daily.nc" }},
{ "id":"swc",     "file":{ "fmt":"cdf", "timestep":"daily", "name":"output/swc_daily.nc" }},   // per-layer array
{ "id":"soiltemp","file":{ "fmt":"cdf", "timestep":"daily", "name":"output/soiltemp_daily.nc" }},
{ "id":"swe",     "file":{ "fmt":"cdf", "timestep":"daily", "unit":"mm", "name":"output/swe_daily.nc" }},
{ "id":"pet",     "file":{ "fmt":"cdf", "timestep":"daily", "unit":"mm/day", "name":"output/pet_daily.nc" }}
```

### Q1d. Flux/pool wishlist → availability & daily-capability

"Daily-capable = yes" means `getmintimestep` allows DAILY and the value genuinely varies sub-annually.

| Flux / pool | Available? | Daily? | Variable key(s) |
|---|---|---|---|
| Evapotranspiration (total) | Yes (sum) | Yes | `evap` + `transp` + `interc` (and blue-water variants); `pet` |
| Transpiration | Yes | Yes | `transp` |
| Soil/interception evaporation | Yes | Yes | `evap`, `interc` |
| Runoff (total/surface/lateral/snow) | Yes | Yes | `runoff`, `runoff_surf`, `runoff_lat`, `snowrunoff` |
| Drainage / percolation / seepage | Yes | Yes | `perc` (per-layer), `seepage` |
| GPP | Yes | Yes | `gpp` |
| NPP | Yes | Yes | `npp` |
| **Autotrophic respiration Ra** | **No direct output** | — | derive **Ra = GPP − NPP** (both available); leaf resp only in per-CFT `d_rd` |
| Heterotrophic/soil resp Rh | Yes | Yes | `rh`, `rh_litter` |
| **Latent heat LE** | **No** | — | derive **LE = λ·ET** externally (λ = latent heat of vaporization) |
| **Sensible heat H** | **No** | — | **not computed by the model** (see Q3) |
| **Net radiation Rn** | **No** | — | only `albedo`, `cft_srad` (SW-down, W/m²), `daylength` exist; derive Rn from forcing |
| Soil moisture (per layer) | Yes | Yes | `swc` (array), `swc1..5`; absolute `rootmoist` |
| Snow water equivalent | Yes | Yes | `swe` |
| Soil temperature (per layer) | Yes | Yes | `soiltemp` (array), `soiltemp1..6` |
| Soil carbon | Yes | Yes* | `soilc`, `soilc_layer`, `soilc_slow` |
| Litter carbon | Yes | Yes* | `litc`, `litc_ag`, `litc_all` |
| LAI | Yes | Yes* | `lai_stand`, `pft_lai`, `nv_lai` |
| FPC | Yes | annual-updated | `fpc`, `fpc_stand`, `fpc_pft` |
| Vegetation carbon | Yes | `vegc`=annual-only → use `vegc_avg`/`agb` | `vegc`, `vegc_avg`, `agb` |
| FIT individual-tree table | Yes | annual | `ind` output (see Q5) — one row per tree with traits/pools/structure |

\* Mechanically daily-capable, but these pools/structure update mainly at annual allocation/turnover, so intra-year daily snapshots are near-constant. Output them annually unless a specific need arises.

**Take-away:** the full **water** budget (P, ET-components, runoff, drainage, ΔsoilmoistureΔsnow) and the full **carbon** budget are available at daily resolution — but the carbon budget must include the **disturbance and establishment fluxes**: **fire is ON (GlobFIRM)**, so `firec` (fire carbon emission) and `flux_estabc` (establishment influx) are real fluxes (`par/outputvars.js`) and must be enabled and carried. Correct closure: ecosystem `ΔC = NPP − Rh − firec + flux_estabc`; atmosphere-facing `NBP_atm = Rh + firec − NPP − flux_estabc` (Ra = GPP − NPP). A fire-free `NEE = Rh − NPP` will *not* close. The **energy** budget is *not* closable from model output — LE is derivable (λ·ET), but H, Rn, and G-as-a-flux are not model outputs (G is implicit in the soil enthalpy state).

---

## Q2 — Compute cost of daily-output re-runs

- **Simulation CPU cost is unchanged by enabling daily output.** The model already integrates daily; daily output only changes *how often results are written*, not the compute. The marginal cost is disk I/O and storage.
- **Storage scaling:** for a chosen daily variable, output volume ≈ (cells) × (days) × (bands, e.g. soil layers) × 4 bytes. For the prototype single-cell ensemble (10,000 replicate "cells" × 5 patches over 10 years, ~3,650 days) this is modest — order of tens of MB to a few GB per variable depending on how the ensemble is represented as cells vs patches (patch-level `ind`/daily output is per-patch).
- **The FIT individual-tree table is the real cost driver**, not daily flux output: it scales with the number of living trees × patches × cells × years. This is already the dominant output in FIT runs.
- **Practical guidance for the agent:** (i) generate daily output only for the variables the fast layer needs; (ii) keep the tree table at annual resolution; (iii) profile one representative run before scaling to many cells. Provide SLURM settings via config (see `config/hpc_slurm.yaml`), do not probe the cluster interactively.

**One-off training-data generation cost** (running LPJmL-FIT across the training design after spin-up) is the dominant compute item in the whole project and must be budgeted explicitly; it is excluded from any "emulator speed-up" claim, exactly as in Natel et al. (2025).

---

## Q3 — Forcing consumed, ET/energy scheme, and the ESM-interface implication

### Q3a. Forcing variables actually consumed (active FIT config)

| Field | Consumed? | Role |
|---|---|---|
| `temp` (tas) | Yes | Photosynthesis, phenology, respiration, PET, **soil-temperature top boundary** |
| `prec` | Yes | Water balance, snow, interception |
| `swdown` (rsds) | Yes | Net shortwave + PAR + equilibrium-evap demand |
| `lwnet` (net longwave) | Yes | Longwave term of equilibrium-evap demand |
| `humid` (huss, specific humidity) | **Yes** | Converted to **VPD** (`getvpd.c`), drives **FIT tree water stress** (`waterstress_tree.c`) — a genuine hard dependency in FIT mode |
| `co2` | Yes | Photosynthesis (partial pressure) |
| `tamp` (diurnal T range) | Yes (aux) | Derives daily tmin/tmax when not supplied |
| `cloud`/`sun`, `wetdays` | No (this config) | Only used in alternative radiation/weather-generator modes |
| **`wind` (sfcwind)** | **No (effective)** | Read into the data path, but its only consumers (SPITFIRE fire spread; N volatilization) are **inactive** in this config. Never enters ET/energy/water/carbon. |
| **surface pressure / psurf** | **Not a forcing field** | Atmospheric pressure is a hard-coded constant (`photosynthesis.c`: `#define p 1.0e5` Pa; `getvpd.c` uses fixed 1013.25 hPa). |

### Q3b. ET / energy scheme — VERIFIED: equilibrium ET, no energy balance

- **Evapotranspiration** uses the **Priestley–Taylor equilibrium-evaporation / demand–supply** formulation (Haxeltine & Prentice 1996; Gerten et al. 2004), *not* Penman–Monteith:
  - Equilibrium evaporation `eeq` computed in `src/numeric/petpar2.c` from net shortwave and net longwave with the `s/(s+γ)` slope factor — **no aerodynamic (wind) term**.
  - Actual transpiration in `src/lpj/water_stressed.c` = min(**supply** = `emax·w_r·phen`, **demand** = `(1−wet)·eeq·ALPHAM / (1 + GM·ALPHAM/gp)`), where `gp` is a canopy conductance (Monteith-like) but **there is no aerodynamic resistance**.
- **Soil temperature** is solved by an enthalpy-based heat-conduction scheme whose **upper boundary is the imposed air temperature (Dirichlet BC)** (`update_soil_thermal_state.c`; `apply_heatconduction_of_a_day.c`). Snow and litter add series thermal resistance only; **no skin temperature is solved.** Outgoing longwave, where used, is computed from **air** temperature.
- **VERIFIED absence:** no `sensible`, `skin_temp`, `bowen`, `netrad`, or `energy_balance` symbols in core `src/`. The only hits for "sensible" (a roughness-height comment) and "latent_heat" (soil freeze–thaw **latent heat of fusion**, water↔ice) are unrelated to a surface energy flux. `outputvars.js` contains no latent-heat, sensible-heat, or net-radiation output.

### Q3c. Implications for the ESM coupling interface

An atmospheric model expects the land surface to return, per coupling step: net radiation partitioned into **latent heat (LE)**, **sensible heat (H)**, and **ground heat (G)**; a **skin/surface temperature** (which sets the upward longwave and the near-surface gradients); a **CO₂ flux (NEE)**; and momentum roughness. From LPJmL-FIT we can obtain:

- **LE** — yes, as `λ·ET` (ET = transp + soil evap + interception + snow sublimation).
- **CO₂ flux** — yes, but use the full net flux the atmosphere sees: `NBP_atm = Rh + firec − NPP − flux_estabc` (biological NEE = Rh − NPP = Ra + Rh − GPP; fire is ON, so include `firec` and establishment).
- **G** — implicitly, as the change in soil enthalpy; extractable but not a native flux output.
- **H, Rn-closure, T_skin** — **NOT available.** They do not exist in the model.
- **Roughness length** — `src/lpj/roughnesslength.c` exists (built for CLIMBER/GCM coupling) and gives an aerodynamic roughness from canopy structure, but it is not on the standard output path and is only compiled for coupled builds.

**Therefore, to serve as an ESM land component, the system must ADD a surface-energy-balance closure** that: takes available energy `A = Rn − G` (Rn assembled from the atmosphere's shortwave/longwave down + surface albedo + upward longwave from `T_skin`); takes the vegetation/soil **latent heat** the LPJmL-FIT core computes; and **solves for `T_skin` and partitions `A` into `LE, H, G`** using an aerodynamic conductance that **requires wind and surface pressure** (the two forcings LPJmL-FIT ignores). This module is new physics/ML, not emulation of LPJmL-FIT, and is required regardless of the emulator-vs-hybrid choice. See `DEVELOPMENT_PLAN.md` for its conservation-constrained design.

---

## Q4 — Prognostic state vector, carbon pools, allometry

`Stocks = {Real carbon; Real nitrogen;}` (N carried but inert here: `with_nitrogen="no"`).

### Q4a. Vegetation (per tree individual — FIT)

Each established tree is a node in `patch->pftlist` with a unique `tree->index`. Carbon(+N) pools (`Treephys2`): **`leaf, sapwood, heartwood, root, sapwood_bg, heartwood_bg, debt`** — 7 pools. (FIT adds belowground sapwood/heartwood and a `debt` pool vs classic LPJmL's 4.) Structure/traits (`Pfttree` + generic `Pft`): `height, boleht, crownarea, barkthickness, wooddens, sla, D95, D95max, age, k_root, emax, longevity, nind, fpc, phen/aphen, phen_gsi{tmin,tmax,light,wscal}, wscal, bm_inc, fapar, rootdepth, mort_prob, excess_carbon, fruit, water_stress, temp_stress`.

### Q4b. Soil & litter

- **SOM:** `pool[LASTLAYER=22]`, each `{fast, slow}` Stocks → 2 pools × 22 layers = 44 SOM C(+N) stores (vertically resolved).
- **Litter:** `Litter.item[pft]`, each with above-ground `ag` (leaf + wood[4 fuel classes]), `agsub`, and below-ground `bg`.
- **Mineral N:** `NO3[22]`, `NH4[22]` (inert here).

### Q4c. Soil water / ice / thermal (23 layers) & snow

- **Water:** `w[23]` (fraction of water-holding capacity), `w_fw[23]` (free/gravitational water, mm), `w_evap` (mm), `rw_buffer` (mm), litter surface water `agtop_moist`.
- **Ice/permafrost:** `ice_depth[23]`, `ice_fw[23]`, `freeze_depth[23]`, `ice_pwp[23]`.
- **Thermal:** `enth[NHEATGRIDP]` (J/m³, the fundamental thermal state), `temp[]` (derived; last slot = snow), `state[]`, plus enthalpy-adjustment bookkeeping fields. `NHEATGRIDP = NSOILLAYER·GPLHEAT`; here it equals 23 only because `GPLHEAT=1` (`include/soil.h`) — key the emulator's thermal dimension to `NHEATGRIDP`, not a literal 23, since a build with `GPLHEAT>1` changes it.
- **Snow:** single store `snowpack` (mm water-equivalent) → `snowheight`, `snowfraction` derived.
- **Interception:** diagnostic (recomputed from current LAI each day; no persistent store).

Layer thicknesses (from `par/soil_20m.js`): `[200, 300, 500, 1000×19, 3000]` mm → 23 m total (top 3 = classic 1 m hydrology; deep column for permafrost). `NSOILLAYER = 23`.

### Q4d. Cell-level running state (source of multi-year memory)

`Climbuf` (per cell): 20-year running climate memory — `atemp_mean20, mtemp20[12], mprec20[12], mpet20[12], mtemp_min20, aetp_mean, gdd5`, plus daily buffers. **This is the principal source of multi-year autocorrelation** and must be part of the slow emulator's conditioning. Also per cell: per-PFT `gdd`, RNG `seed` (drives stochastic establishment/mortality — the source of ensemble spread), and the FIT `treelist`/`Sapling` inheritance pool (each Sapling carries `sla, k_root, emax, wooddens, beta_root, beta_2, D95max, agb, fpc, year, id`).

### Q4e. Allometry & diagnostics (to re-derive closure)

- **Height (pipe/latosa):** `height = k_latosa · C_sapwood / (C_leaf · SLA · wooddens)`, capped at `height_max`.
- **Stem diameter:** from height via `allom2/allom3`, or from wood mass `stemdiam = sqrt((C_wood/wooddens)/(height·π/4))`.
- **Crown area (Reinicke):** `crownarea = min(allom1·(height/allom2)^(kpr/allom3), crownarea_max)` (FIT uses an individual exponent `kpr`).
- **Pipe model:** `sapwood_xs_area = C_sapwood/(wooddens·height)`.
- **LAI:** `LAI = C_leaf·SLA / crownarea`; actual LAI = `LAI · phen`.
- **FPC (Beer–Lambert):** `FPC = crownarea · nind · (1 − exp(−k·LAI))`.
- **SLA↔longevity (Reich):** `SLA = f(longevity)`; FIT draws SLA per individual and back-computes longevity.
- **AGB:** `leaf + heartwood + sapwood` (above-ground).

These relations let the emulator carry only a minimal state and **re-derive diagnostics** (LAI, FPC, canopy height, AGB) rather than co-predict them — essential for consistency and conservation.

---

## Q5 — Persistent patch/stand identifier

- **No explicit `id` field** on `struct stand` or `struct patch`. FIT replicate patches are an **array inside one natural stand** (`stand->patch[0..npatch-1]`, here 25), addressed positionally.
- **In the active `landuse="no"` config the natural stand is never deleted or reordered**, and the patch array is fixed for the run. Therefore **`(cell, patch-index)` is a stable positional key across all years** — and this is exactly what the FIT `ind` output already records (`output->patch = np`). Each tree also carries a persistent unique `tree->index` (restored across restarts), though it disappears when the tree dies.
- **Caveat (LIVE, not hypothetical):** the guarantee holds only while land-use change, patch-merging, and reservoir-stand creation stay inactive. `landuse="no"`, **but `reservoir:true` is set in the transient (data-generating) branch of `lpjmlfit.js`.** Reservoir-stand creation could perturb the `(cell, patch-index)` key in affected cells. For a pure natural single-cell prototype this should not trigger, but **verify explicitly in DESIGN** (read `src/reservoir/` and callers of `mergepatch`/`landusechange`), and restrict the training set to cells where the key is provably stable. For the emulator, the safe, self-consistent unit is **the patch, keyed by `(cell, patch-index)`**, with per-tree `index` available for within-patch tracking if needed.

**Consequence:** the autoregressive lagged-state design (condition year *t* on year *t−1* patch state) is feasible at the patch level. Because ensemble spread across patches is driven by the RNG seed and stochastic establishment/mortality, the natural modelling target is the **distribution over patches within a cell**, conditioned on cell drivers + cell climate memory + previous-year patch/cell state — not the identity of individual trees.

---

## Open items to confirm before/at data generation (low-risk, flagged)

1. **`.clm` climate files are daily** and the `lwnet` sign convention matches `petpar2`'s downward-positive usage — verify against the actual GSWP3-W5E5 input headers used for the prototype.
2. **`reservoir=true` with `river_routing=false`:** confirm no reservoir stand is ever created (which would perturb positional patch identity in affected cells). In a pure natural single-cell prototype this does not arise.
3. **Exact `pet` output semantics** and the numeric values of `ALPHAM`, `GM` (`par/lpjparam*.js`) if the precise PET is needed as a fast-layer input.
4. **huss is a hard dependency** of FIT tree water stress — confirm no alternative branch exists for `individual=true` (it does not appear to). Any ESM forcing must therefore supply specific humidity.
5. **Soil-layer band counts** in per-layer array outputs (`swc`, `soiltemp`, `perc`) — confirm `NSOILLAYER`/output banding in `outputsize.c` so the emulator's layer dimension matches.

These are verification steps for the Claude Code agent's DESIGN phase; none blocks the plan.
