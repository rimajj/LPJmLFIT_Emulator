# DESIGN.md — ESM-Ready LPJmL-FIT Hybrid Land Component (Phase 0)

**Status:** Phase-0 DESIGN. Investigation complete; schemas frozen; load-bearing findings
re-verified against the live source tree. No heavy compute spent. Gate to Phase 1 = this document
reviewed + findings reproduced.

**Verified against:** LPJmL-FIT source `/home/jamirp/lpjml56fit`, git `b2e5ca9`
(2026-01-28, "fixed inheritance routine in new_tree.c"), `VERSION` 5.6.004; PIK cluster login03.
Every file:line below was read directly this phase.

> **Terminology.** S = slow ML trait/size **distribution** emulator (annual). F = fast physical
> biophysical core kept from LPJmL-FIT (daily). E = new surface-energy-balance + skin-temperature
> closure (the ESM interface LPJmL-FIT lacks). Decision to build a **phased hybrid** is frozen
> (`DEVELOPMENT_PLAN.md` §1); this document is execution scaffolding, not a re-litigation.

---

## 0. Executive summary of what Phase 0 established

1. **Both load-bearing findings reproduce** (§1): daily output is a runtime config flag (no
   recompile); LPJmL-FIT has **no** surface energy balance (no H, no skin temperature, no Rn closure).
2. **The environment differs from the handover's assumptions** and is now resolved (§4): the LPJmL
   tree is `/home/jamirp/lpjml56fit` (not `/home/jamirp/waldspektrum`); the binary is already built;
   input data is the **priesner/clustering** pipeline, not the repo-default `input_GSWP3-W5E5.js`.
3. **The prototype-mechanism blocker is resolved** (§5): the real design is **global multi-cell**
   (67,420 cells × 25 patches), and the annual **ground-truth data already exists on disk** (Historical
   obsclim 2000–2019 seed1+seed2; SSP370 MPI-ESM1-2-HR 2020–2100). The existing `ind` CSV suffices for
   S at **agb/vegc/trait** granularity, so no new run is needed to train the *aggregate* S; **but** the
   disaggregated **woody-C (sapwood+heartwood) memory state** the resilience mechanism needs (§6, §9)
   is NOT in the CSV — it requires either a **RAW `ind` re-generation** or **allometric reconstruction**
   (pipe model: `sapwood_xs_area=C_sapwood/(wooddens·height)`), so "no new run needed" holds for
   aggregate S only, not for the pool-resolved variant (§3.1 decision).
4. **A sibling offline emulator already built component S** (`/p/projects/open/Jamir/emulator`) and
   **documented its in-principle failure** (§6): a pure equilibrium climate→distribution mapping
   cannot represent the SSP transient / no-analog future. That failure is precisely what this
   project's hybrid (physical core F + flux-then-integrate S + energy layer E) is designed to fix.
5. **The concrete Phase-1 gap is narrow** (§7): existing output is **annual only**; components F and E
   need **daily** flux/pool output (a config-only re-run) and, for per-tree carbon pools, a **RAW**
   `ind` output. Component E additionally needs **wind + surface pressure** and external FLUXNET/PLUMBER2.
6. **The reservoir/patch-identity caveat does NOT bite** (§1.3): under `landuse="no"` the
   `(cell,patch-index)` key is provably stable even with `reservoir:true`.
7. **The binary is runtime-validated** (this phase): with the §4.3 modules loaded (incl.
   `netcdf-c/4.9.2`), `bin/lpjml -h` runs and reports "C Version 5.6.004 (Feb 5 2026)". The help also
   exposes a `-couple host[:port]` interface — relevant for the eventual ESM coupling (§8).

---

## 1. Re-verification of the two load-bearing findings (done this phase, cited)

### 1.1 Daily flux/pool output is a runtime config flag — REPRODUCED

- Each output carries an `int timestep`; the daily-write path is switched on automatically when any
  requested output has `timestep==DAILY`:
  `src/lpj/fscanoutput.c:390-391` → `if(config->outnames[flag].timestep==DAILY) config->withdailyoutput=TRUE;`
  (initialized FALSE at `fscanoutput.c:131`).
- The daily write is gated on that runtime boolean:
  `src/lpj/iterateyear.c:207-208` → `if(config->withdailyoutput && year>=config->outputyear) fwriteoutput(output,grid,year,day-1,DAILY,...)`.
- Only 7 output ids are capped at annual; everything else defaults to daily:
  `src/lpj/getmintimestep.c:24-27` → `case VEGC: case VEGN: case GLOBALFLUX: case CFTFRAC: case CFTFRAC2: case SDATE: case SDATE2: return ANNUAL; default: return DAILY;`
  → for sub-annual vegetation carbon use `vegc_avg`/`agb`, not `vegc`.
- `#define DAILY_OUTPUT` (commented out in `lpjmlfit.js`) is a JSON-preprocessor convenience for the
  legacy per-CFT `d_*` block only; **not** referenced by any C source and **not** required.

**Verdict:** to emit daily, set `"timestep":"daily"` + a per-day `"unit"` on the chosen `"file"`
objects. Simulation CPU is unchanged (model already integrates daily); only I/O grows.

### 1.2 No surface energy balance — REPRODUCED

- Symbol search over `src/` and `include/`: `skin_temp` 0 hits, `netrad` 0, `energy_balance` 0,
  `bowen` 0. The single `sensible` hit is a comment in `src/lpj/roughnesslength.c:19` (unrelated).
- `par/outputvars.js` (476 lines) has **no** latent-heat, sensible-heat, or net-radiation output.
- **ET = Priestley–Taylor equilibrium / demand–supply, no aerodynamic term:**
  `src/numeric/petpar2.c:72` → `*eeq = dayseconds*(s/(s+gamma_t(temp))/lambda(temp))*(swnet + lw*(*daylength)/24)`;
  `swnet=(1-albedo)*swdown` (`petpar2.c:61`). Transpiration = `min(supply,demand)` with a Monteith
  canopy conductance but **no aerodynamic resistance**: `src/lpj/water_stressed.c:108` (supply),
  `:118` (`demand=(1-wet)*eeq*ALPHAM/(1+GM*ALPHAM/gp_stand)`), `:153` (min).
- **Soil temperature top BC = imposed air temperature (Dirichlet), no skin temperature:**
  `src/soil/update_soil_thermal_state.c:125` (`top_dirichlet_BC = airtemp`), fed to
  `apply_heatconduction_of_a_day.c` (`temp[0]=temp_top` at `:64,:80,:172`); the caller passes the
  daily air temperature `update_daily.c:187` (`update_soil_thermal_state(&patch->soil,climate.temp,...)`).

**Verdict:** LE is derivable (λ·ET); **H, Rn-closure, G-as-flux, and T_skin do not exist** and must be
**added** (component E), validated out-of-model. This is the single most important architectural fact.

### 1.3 Open items from SOURCE_FINDINGS — all closed

| Open item | Verdict (this phase) |
|---|---|
| `.clm` are daily | **YES** for Historical: `temperature_test.nc` header = "GSWP3-W5E5 obsclim ISIMIP3a", 1901–2019 **daily**, noleap (43,435 steps). SSP370 regridded from MPI-ESM1-2-HR daily; confirm the `.clm` header in Phase 1. |
| `lwnet` sign | **Net longwave, downward-positive.** `petpar2.c:39` doc "longwave net/downward"; in `radiation` mode `islwdown=FALSE` so `lw` is used as-is and **added** to `swnet` (`petpar2.c:72`). Typically negative (a loss). |
| PET semantics + `ALPHAM`,`GM` | `pet` output = `eeq * PRIESTLEY_TAYLOR`, daily→monthly (`update_daily.c:159`). `PRIESTLEY_TAYLOR=1.32` (`include/soil.h:71`); `ALPHAM=1.391` (`par/lpjparam_fit.js:38`), `GM=3.26` (`par/lpjparam_fit.js:37`) drive transpiration **demand**, not the PET diagnostic. |
| Soil-layer band counts | `swc`,`soiltemp`,`perc` = **23** bands (`NSOILLAYER`); `soilc_layer`,`aet_layer` = **22** (`LASTLAYER`). `swc1..5`,`soiltemp1..6` are separate single-band scalars. `src/lpj/outputsize.c:63-68`. |
| No reservoir-stand creation | **CONFIRMED stable** — see below. |

**Patch-identity / reservoir (the LIVE caveat) — RESOLVED, key is stable.** Under `landuse="no"`
(`conf.h:25` `NO_LANDUSE==0`), `initinput.c:41-47` sets `input.landuse=NULL`, so:
`allocate_reservoir` (the only runtime setter of `ml.dam=TRUE`, `allocate_reservoir.c:39`) is behind
`if(input.landuse!=NULL)` at `iterate.c:217` → never runs → `ml.dam` stays FALSE; and the stand
mutators `landusechange`/`landusechange_for_reservoir`/`mergepatch`/`deforest` are all inside
`if(config->withlanduse)` (`iterateyear.c:73`) → never run. `initreservoir` still runs (allocates
irrigation data only, leaves `ml.dam=FALSE`); with `river_routing=false` the network is degenerate.
There are **no `addpatch`/`delpatch`** functions; the natural stand's patch array is allocated once
(`standlist.c:95`, size `config->npatch`) and never resized/reordered; the natural stand is never
deleted (`annual_natural.c:251` always returns FALSE). → **`(cell, patch-index)` is a stable
positional key for all years** in this config; per-tree `index` is persistent while the tree lives.

---

## 2. Frozen shared-state vector (single source of truth)

One authoritative copy of each state (START_HERE rule 1). F owns/integrates soil water, snow, soil
thermal, and SOM/litter pools; S owns the vegetation distribution and allocates into veg-C. Exact
struct provenance (all verified this phase):

### 2.1 Soil water / ice / thermal / snow (`include/soil.h`; constants `soil.h:30-41`)
- `NSOILLAYER=23`, `LASTLAYER=22`, `GPLHEAT=1`, `NHEATGRIDP=NSOILLAYER*GPLHEAT=23`.
  **Key the emulator's thermal dimension to `NHEATGRIDP`, not literal 23** (a `GPLHEAT>1` build changes it).
- Water: `Real w[23]` (frac of WHC, `soil.h:202`), `Real w_fw[23]` (free water mm, `:203`),
  `Real w_evap` (`:204`), `Real rw_buffer` (`:240`).
- Ice: `ice_depth[23]` (`:224`), `ice_fw[23]` (`:225`), `freeze_depth[23]` (`:226`), `ice_pwp[23]` (`:227`).
- Thermal: **`Real enth[NHEATGRIDP]`** (volumetric enthalpy J/m³, the fundamental state, `:215`);
  `Real temp[NSOILLAYER+1]` (derived; last slot = snow, `:214`); `short state[23]` (`:232`).
- Snow: `Real snowpack` (mm w.e., `:211`) → `snowheight` (`:212`), `snowfraction` (`:213`) derived.
- Layer thicknesses (`par/soil_20m.js:19-41`): `[200, 300, 500, 1000×19, 3000]` mm = 23 m total (23 layers).

### 2.2 Soil / litter carbon (`include/soil.h`)
- SOM: `Pool pool[LASTLAYER]` (`soil.h:196`), `Pool = {Stocks fast; Stocks slow;}` (`:119-123`) →
  2 C(+N) pools × 22 layers.
- Litter: `Litter litter` (`:239`); `Litteritem = {const Pftpar *pft; Trait ag; Trait agsub; Stocks bg;}`
  (`:138-144`); `Trait = {Stocks leaf; Stocks wood[NFUELCLASS=4];}` (`:132-136`).

### 2.3 Vegetation — per tree individual (`include/tree.h`, `include/pft.h`)
- **7 carbon(+N) pools** `Treephys2 = {Stocks leaf, sapwood, heartwood, root, sapwood_bg, heartwood_bg, debt;}`
  (`tree.h:48-51`); stored per individual as `Treephys2 ind` (`tree.h:115`). `Stocks={carbon,nitrogen}` (`types.h:104-108`).
- Structure/traits: `Pfttree` (`tree.h:96-135`): `height` (`:99`), `crownarea` (`:101`),
  `barkthickness` (`:102`), `wooddens` (`:105`), `D95`/`D95max` (`:111,:98`), `age` (`:125`),
  `index` (`:126`), `isdead` (`:127`), `mort_prob` (`:128`), `k_root` (`:129`), `emax` (`:130`),
  `mort_{age,npp,water,temp}` (`:131-134`). **Correction to SOURCE_FINDINGS:** `sla` is **not** a
  `Pfttree` field — it is in generic `Pft` (`pft.h:239`) and in `struct sapling` (`tree.h:139`).
- Generic `Pft`: `nind` (`pft.h:224`), `fpc` (`:219`), `phen`/`aphen` (`:229`), `wscal` (`:227`),
  `Stocks bm_inc` (annual increment, `:226`), `fapar` (`:223`), `rootdepth` (`:251`),
  per-individual trait copies `sla,longevity,emax,beta_root,beta_2,minwscal` (`:235-240`).

### 2.4 Cell-level memory (`include/climbuf.h`, `include/cell.h`) — the multi-year autocorrelation source
- `Climbuf` (`climbuf.h`, `CLIMBUFSIZE=20`): `gdd5` (`:28`), `atemp_mean20` (`:36`),
  `mtemp20[12]` (`:44`), `mprec20[12]` (`:42`), `mpet20[12]` (`:43`), `mtemp_min20` (`:45`),
  `aetp_mean` (`:46`), plus daily buffers. Embedded per cell (`cell.h:112`).
- RNG: `Seed seed` per cell (`cell.h:145`; `NSEED=3` for rand48) — drives stochastic
  establishment/mortality → **the source of the patch ensemble spread**.
- FIT inheritance: `Sapling` (`tree.h:137-152`): `sla,k_root,emax,wooddens,minwscal,beta_root,beta_2,
  D95max,agb,fpc,year,id`; per-cell `treelist`/`treelist_old` + `Trait_tree` (`cell.h:146-150,53-59`).

**S's target object** = the per-cell **distribution** over trees (traits × size × pools) + count `N`,
conditioned on cell drivers + `Climbuf` + previous-year distribution summary + stand age + the NPP F
delivered (`bm_inc`) + the four mortality drivers (water, temp, growth-efficiency/npp, age;
`src/tree/mortality_tree_ind.c`).

---

## 3. Data schema (frozen)

### 3.1 The `ind` (FIT individual-tree) table — writer `src/lpj/fwriteoutput_ind.c`

**CSV/TXT format (existing ground-truth data), 29 columns** (`fwriteoutput_ind.c:28-57`), in order:
```
Year, index(ID), id(Type), height, age, agb, vegc, transp, npp, gpp, wscal_mean,
sla(SLA), leaf_longevity(Longevity), wooddens(Wooddens), lai(LAI), fpc_ind, minwscal,
D95, D95max, beta_root, k_root, mort_npp, mort_age, mort_water, mort_temp, mort_prob(mort),
isdead, patch(Patch), cell(Cell)
```
(Header names as written by the model in parentheses where they differ.) One row per living
individual per year, natural stands only; grass PFTs (`Type 8`) written with tree fields zeroed.

**⚠ Design-critical:** the CSV **omits the disaggregated per-tree carbon pools**. The block commented
out at `fwriteoutput_ind.c:58-67` is exactly `bm_inc_counter, stemdiam, crownarea, leafarea, rootmass,
sapwood, heartwood, alphaa, fpc, boleh`; `leafmass` (computed at `:112`) is simply never emitted to
the CSV at all. So the CSV exposes only `agb` and `vegc` for carbon. The **RAW** format
(`fwriteoutput_ind.c:69-71`) writes the whole `Output_ind` struct (`include/output.h:119-165`: 36
Real + 7 int + 1 Bool) which **does** expose 4 tree C pools (`leafmass, rootmass, sapwood,
heartwood`) + geometry (`stemdiam, crownarea, leafarea, boleh`).

**Decision (carbon granularity for S) — two-tier, and honest about the consequence:**
- **Tier 1 (aggregate S):** S conserves carbon at the **`vegc`/`agb`** granularity the CSV provides
  (the quantity F delivers as `bm_inc` integrates into `vegc`). Finer S→F structure (crownarea → LAI,
  z0, FPC) is **re-derived by the model's own allometry** (§2.3, SOURCE_FINDINGS Q4e), not co-predicted.
  Trainable on the **existing** annual `ind` CSV — no re-run.
- **Tier 2 (pool-resolved S):** the LPJ_resilience memory mechanism (§6, §9) requires the **explicit
  slow woody-C = sapwood + heartwood** state, which is **not** in the CSV. Two routes, and this is a
  real cost decision, not an afterthought: **(a) allometric reconstruction** of the sapwood/heartwood
  split from the CSV's `height`+`wooddens`+`agb` via the pipe model (`sapwood_xs_area =
  C_sapwood/(wooddens·height)`) — cheap, no re-run, but approximate; or **(b) RAW `ind` re-generation
  of the full slow-emulator ground truth** (not just the daily prototype) — exact (gives
  leaf/root/sapwood/heartwood; `*_bg`/`debt` stay internal, diagnostic), but a **global re-run** of the
  Historical + SSP370 ground truth. **Therefore "the data already exists" (§0.3) is true for Tier-1
  aggregate S only; Tier-2 requires route (a) or (b).** Default: attempt **(a)** first (validate the
  reconstruction against a small RAW-output check cell), fall back to (b) only if the split is
  inadequate. Do not present "explicit woody-C memory" and "no new run needed" as both unconditionally
  true.

### 3.2 The `globalflux` CSV — writer `src/lpj/fprintcsvflux.c` (budget-closure reference)

Columns (natural-veg config; `fprintcsvflux.c:29-87`):
`Year, NEP(=NPP−RH), GPP, NPP, RH, estab(=flux_estabc), negc_fluxes, fire(=firec), NBP, transp,
evap, interc, prec, SoilC, SoilC_slow, LitC, VegC`. Carbon in gC/yr (scaled), water in dm³/yr.
→ **All CARBON-closure fluxes are already present** (`estab`, `fire`, `NBP`), so the carbon closure
`ΔC = NPP − Rh − firec + flux_estabc` and `NBP_atm = Rh + firec − NPP − flux_estabc` can be validated
**now, on the existing annual data, with no re-run**. **The WATER budget cannot:** `globalflux` gives
only annual global-total `transp/evap/interc/prec` — the full balance `P = ET + runoff + drainage +
Δ(soil+snow+interception)` needs the per-cell **runoff/drainage/storage** variables from the daily
re-run (§3.3), defined to match LPJmL's own internal `balanceW` term set. So the Phase-1 gate is
**split** (§7).

### 3.3 Daily fast-layer output to ADD in Phase 1 (config-only)

Enable `"timestep":"daily"` + per-day units for the fast-core variables F/E need:
`transp, evap, interc, runoff, runoff_surf, runoff_lat, perc, seepage, swc(23-band), soiltemp(23-band),
swe, gpp, npp, rh, pet, albedo` (+ `firec`, `flux_estabc` annual for closure). Keep the `ind` table
annual (cost driver). Derive offline: `Ra=GPP−NPP`, `LE=λ·ET` (λ vaporization for liquid, sublimation
for snow/ice), `ET=transp+evap+interc+snow-sublimation`.

### 3.4 The three datasets

1. **Slow-emulator table** (`(cell,year)`): conditioning features (annual climate summary of the year
   simulated, CO₂, soil props, `Climbuf` 20-yr memory, previous-year distribution summary, stand age,
   `bm_inc`, mortality drivers, soil-moisture state) + year-*t* trait×size distribution (all trees) +
   `N`. **Source = existing annual `ind` CSV** (44 GB Historical/seed × 20 yr; 180 GB SSP370) + climate +
   Climbuf. **Largely already materialized** by the sibling project (§6) — reuse its parquet tables.
2. **Fast-core validation set** (daily forcing → daily fluxes + pool states): **NEW**, from a
   daily-output re-run (§3.3). For validating F1 reproduces LPJmL daily, and for training F2.
3. **Energy-closure reference** (external — no in-model ground truth for E). **Schema stub** (resolve
   the path/site list in Phase 4, but freeze the shape now): source **PLUMBER2** (preferred; the
   ~170-site quality-controlled FLUXNET subset) or **FLUXNET2015 Tier-1**. Variables + units:
   `LE [W/m²], H [W/m²], Ts/T_skin [K], Rn [W/m²]`, plus the forcing E needs: `SWdown, LWdown [W/m²],
   Tair [K], qair [kg/kg], wind [m/s], psurf [Pa], precip`. Temporal resolution **half-hourly**
   (aggregate to daily-mean + retain the sub-daily cycle for the diurnal-downscaling test). Site
   selection: forest/woody PFTs spanning the prototype biomes; format NetCDF (PLUMBER2 `*_Flux.nc` +
   `*_Met.nc`). `config/paths.yaml:data.energy_reference` (currently a TODO placeholder — acquisition
   is a Phase-4 step). **Note (build-vs-reuse for E):** "greenfield" means *absent from LPJmL-FIT*, not
   built-from-scratch — per `ECOSYSTEM_AND_COUPLING.md`/plan §1 the intended implementation **reuses
   Terrarium.jl's `SurfaceEnergyBalance` + `ImplicitSkinTemperature`** (which already provide T_skin
   and a consistent G). **Open blocker carried forward:** the LPJmL **AGPL-3.0** ↔ Terrarium/
   SpeedyWeather **EUPL-1.2** ↔ NeuralCrop **CC-BY-NC** licensing needs a written legal read before any
   cross-repo code embedding (§9).

---

## 4. LPJmL-FIT build + run recipe (validated) & resolved inputs

### 4.1 Build — already done
- Source `/home/jamirp/lpjml56fit`; `Makefile.inc:38 LPJROOT=/home/jamirp/lpjml56fit` (correct).
- Binary `/home/jamirp/lpjml56fit/bin/lpjml` already built (2026-02-05, 11.8 MB), v5.6.004, git `b2e5ca9`.
- Build recipe (if a rebuild is needed): load modules (§4.3), `./configure.sh` (selects the PIK
  include), `make`. Verify with `bin/lpjml -h`.
- **Runtime-validated this phase:** with the §4.3 modules loaded (`netcdf-c/4.9.2` is the compatible
  version — bare `netcdf-c` resolves to it), `bin/lpjml -h` runs. The full spinup→transient *chain*
  is not executed in Phase 0 (it is Phase-1 data generation) — "validated" here means binary + source
  + config verified, not a completed run.

### 4.2 Resolved input data (production "global" domain) — all present on disk
See `config/paths.yaml:lpjml.inputs` for exact paths+sizes. Grid: 0.5°, **67,420 cells** (verified 3
ways: `soil_code_test.soil.bin`=67,420 bytes; every metafile `"ncell":67420`; `lpjcheck`), **63,119
carry tree data**. The **production** input config reads only **soil, coord, soildepth, tas(temp),
pr(prec), lwnet, rsds(swdown), huss(humid), CO₂** — note it does **NOT** read `sfcwind`/`wind` at all
(unlike the repo-default `input_GSWP3-W5E5.js:80`, which does). So SOURCE_FINDINGS' "wind is read but
unused" is true for the repo default only; in the production runs wind is **absent**, and component E
must **source wind (and `ps`) separately** (§7.3). The many landuse/N/fire inputs in the repo default
are inactive under `landuse="no"`. huss is a **hard dependency** (`getvpd.c:38` → `waterstress_tree.c:35`
→ `daily_natural.c:130`). Two climate regimes exist on the same grid:
- **Historical** (obsclim GSWP3-W5E5, daily, run 2000–2019) — training baseline. CO₂ = TRENDY v12.
- **SSP370** (MPI-ESM1-2-HR; forcing spans 2015–2100, the transient is **run 2020–2100** continuing
  from the Historical restart; "orderA") — **the realistic OOD/warming trajectory** (a real GCM
  scenario, not a synthetic delta), **CO₂ held constant after 2019** (`..._const_2100.txt`) — exactly
  the constant-CO₂ regime the plan requires. Regridded from daily GCM output; confirm the `.clm` header
  is 365-band daily in Phase 1 (the residual concern is daily-weather *realism*, not resolution).

### 4.3 Run recipe (authoritative = production scripts, NOT the stale repo `.jcf`)
- Modules ([VERIFIED]): `intel/oneAPI/2024.0.0, udunits/2.2.28, json-c/0.13.1, openssl/3.6.0,
  netcdf-c, curl/8.4.0, expat/2.5.0`. `export LPJROOT=/home/jamirp/lpjml56fit`.
- Orchestration (`config/paths.yaml:lpjml.run_scripts_dir`): a script writes `input_*.js` + `lpjml_*.js`
  + `slurm_*.jcf` into `<outpath>/scripts_for_running_the_model/` and submits a **spinup→transient**
  SLURM chain (`--dependency=afterany`). Spinup: `nspinup=1000, nspinyear=30, shuffle_climate:true`,
  writes `restart_1999.lpj`. Transient: `-DFROM_RESTART`, reads restart, writes `ind`+`globalflux`+…
- SLURM: `--qos=short`, `--exclusive`, `--ntasks` 46 (historical) / 2048 (ssp370). Account
  `waldspektrum`. **Do not probe partitions interactively.** SSP370 continuation restarts from the
  Historical seed1 `restart_2019.lpj` (120 GB) — a working, documented pattern.
- Single-site (tiny tests): `-DSINGLESITE` selects `startgrid:28008` (Hainich ≈51.1 N/10.4 E),
  `--ntasks=1`. `mpirun bin/lpjml -DSPINUP -DSINGLESITE lpjmlfit.js` then `-DTRANSIENT -DSINGLESITE`.

### 4.4 Reproducibility ledger (log per dataset)
LPJmL commit `b2e5ca9` / v5.6.004; config JS (`lpjmlfit.js` + generated `lpjml_*.js`); input `.clm`
files + CO₂ file; RNG `random_seed` (1 and 2 for the noise-floor pair); `npatch=25`; spinup
`nspinup=1000/nspinyear=30`; module versions (§4.3). Fixed seed 42 for all Python/ML.

---

## 5. Data-generation mechanism — RECONCILED (the Phase-0 blocker)

The handover's "single-cell / ~50,000 realizations" framing is **superseded** by the real pipeline:

- **The real design is global multi-cell**: 67,420 cells × `npatch=25` patches × years, with a
  **climate-clustering** surrogate branch (cells grouped into N clusters; representative cells run).
  Filenames encode it, e.g. `..._100_clusters_..._ncells_2000_npatch_100_npatchresult_5.nc` and
  `cluster_cell_mapping_{10,25,50,75,100}.csv`. The **within-cell trait/size distribution** that S
  targets is sampled by the **25 patches/cell** (RNG-seed-driven ensemble); the **across-cell**
  distribution provides the conditioning coverage.
- **The ground truth already exists** (no new run needed to train S): Historical 2000–2019 seed1+seed2
  (44 GB `ind` each — the seed pair is the **noise floor**) and SSP370 2020–2100 seed1 (180 GB; seed2
  in progress). See `config/paths.yaml:lpjml.ground_truth`.

**Prototype definition (this project):**
- **F1 integration and E** are proven on **one** cell first (candidate **Hainich `startgrid:28008`**,
  or a S-German cell) — a single cell is sufficient to prove the daily biophysics + energy closure.
- **S is prototyped on a small BIOME-STRATIFIED multi-cell set from the start (≈10–50 cells), NOT one
  cell.** Rationale: S's whole purpose — and the exact thing the sibling emulator failed at (§6) — is
  the **climate/state-conditional** distribution; a single cell has no across-cell climate gradient to
  fit or test, so a single-cell Phase-2 gate would be near-vacuous for the conditional response and the
  25-patch single-cell noise floor is statistically weak. **Scope the Phase-2 single-cell check to
  marginal reproduction + allocation conservation only**, and evaluate the conditional response on the
  multi-cell set. Drawn from the existing global ground-truth; no `npatch` change or single-site re-run
  is required for S. The daily-output re-run (§7) is what the prototype needs for F/E.

---

## 6. Positioning vs the sibling offline emulator (evidence-based justification for the hybrid)

`/p/projects/open/Jamir/emulator` already built **component S offline** (a LightGBM + Gaussian-copula
distribution emulator; no NN/diffusion) on this exact data, and its own `PROJECT_REVIEW.md` records
the honest outcome:

- ✅ **Present-day interpolation works** near the seed noise floor; per-cell spatial pattern r 0.94–0.97
  across 63,119 cells; universal ecological links reproduced (SLA↔longevity −0.95, β_root↔D95max 1.00,
  height↔agb 0.92).
- ❌ **SSP370 projection fails** — "the SSP forest is in **transient disequilibrium** … which an
  *equilibrium* climate→distribution mapping cannot represent even in principle"; models draw 73–86 %
  of signal from **static historical normals**, so warming leaves the prediction unmoved.
- ⚠ **Per-cell biomass at a ceiling** (~1.8–2.4× the 25-patch noise floor; +21 % bias) — proven
  irreducible (sampling noise + non-climate variance: stand age / disturbance history).
- The review's own unbuilt recommendation: *"direct model as the climate attractor + a bounded
  dynamical layer for the transient."*

**This is the hybrid's mandate, with evidence.** This project supplies exactly the missing dynamical
layer: **F** (the kept physical core) computes the true, transient-aware daily biophysics and delivers
the actual `bm_inc`; **S advances the existing population by flux-then-integrate** (increments summing
to the delivered NPP) rather than regenerating an equilibrium snapshot; the slow woody-C
(sapwood+heartwood) and population states are carried explicitly and conditioned on climate/state
(the LPJ_resilience lesson). The sibling's failure is therefore not a discouragement but the
**strongest single piece of evidence** that the equilibrium-ML route is a dead end and the hybrid is
necessary.

**Reuse (do not redo):** the seed1-vs-seed2 **noise-floor** yardstick and per-cell error maps
(`emulator/src/metrics.py`); the derived parquet feature/target tables (63,119 cells) on
`/p/tmp/jamirp/emulator_global`; the conda env `/home/jamirp/.conda/envs/py311_new` (Python 3.11.9,
LightGBM/copulas). **Report per-cell magnitude vs the per-cell floor first**, never lead with pooled
KS/r (the sibling's hard-won lesson).

---

## 7. Concrete Phase-1 work (the narrow gap) & checkpoint

Because the annual carbon/vegetation ground truth already exists, Phase 1 is narrower than the plan
implies. Phase-1 tasks, in order:

1. **Enable daily output** (config-only, §3.3) and re-run the **prototype set** (a small
   **biome-stratified multi-cell** set — see §5; not a single cell) to materialize the **fast-core
   validation set** (daily fluxes + pool states). **Restart from `restart_1999.lpj`** (the spinup end,
   `config/paths.yaml:restart_historical_spinup_end`) with the **same `random_seed`, `startgrid`/domain,
   `npatch=25`, and binary** as the annual ground truth, so the daily set reproduces the exact 2000–2019
   trajectory the annual `ind`/S-table are built on. (`restart_2019.lpj` is only for the SSP370
   continuation.) Add a **RAW `ind`** output if the pool-resolved (Tier-2) S is pursued (§3.1).
   Simulation CPU unchanged; only I/O grows.
2. **Verify budgets close — split gate.** (2a) **Carbon closure NOW** on the existing annual
   `globalflux`, no re-run: `Ra=GPP−NPP`, `ΔC = NPP − Rh − firec + flux_estabc`,
   `NBP_atm = Rh + firec − NPP − flux_estabc` (fire ON — `firec`/`flux_estabc` mandatory; §3.2). (2b)
   **Water closure** on the daily re-run: `P = ET + runoff + drainage + Δ(soil+snow+interc)`, using the
   added runoff/drainage/storage outputs and matched to LPJmL's own `balanceW` terms. **The Phase-1
   gate = both close.**
3. **Source component-E inputs** (deferred to Phase 4 but locate now): **wind (`sfcwind`)** and
   **surface pressure (`ps`)** from the raw GCM NetCDFs / obsclim; external **FLUXNET/PLUMBER2**.
4. **Build the slow-emulator table** for the prototype cell from the existing annual `ind` + climate +
   Climbuf (reuse the sibling's extraction where possible).

**Optional tiny daily-output demonstration (this phase / early Phase 1):** a single-site
(`-DSINGLESITE`, Hainich) run with a **shortened spinup** and daily output on 2–3 variables, submitted
via `sbatch` (`--ntasks=1 --qos=short`), to confirm daily `.nc` files with 365 steps/year appear. The
mechanism is already source-verified (§1.1); this is a smoke test, not a gate. **Not run on the login
node.**

---

## 8. Fast↔slow↔energy interface contract (I/O signatures) — frozen

| Direction | Payload | Type | Conservation role |
|---|---|---|---|
| **S → F** (annual) | LAI, canopy height, z0, rooting-depth profile, Vcmax proxy, FPC, albedo, representative individuals | boundary conditions (structure) | none (structure, not flux) — all **re-derived from the distribution via model allometry**, not co-predicted |
| **S → E** (annual) | albedo, z0, canopy structure (for Rn and g_a) | boundary conditions | none |
| **F → S** (annual) | NPP increment `bm_inc`, water/temp stress, growth efficiency, soil-moisture state | conserved carbon + state | S allocates **exactly** `bm_inc` (flux-then-integrate); carbon can't be invented |
| **F → E** (daily; +annual) | `LE = λ·ET` (λ vaporization/sublimation); GPP, NPP (Ra=GPP−NPP), Rh, firec (daily); **flux_estabc (annual channel)** | fluxes + state | LE **derived** from ET; **all four carbon terms Rh, firec, NPP, flux_estabc must reach E** so it can form NBP_atm (estab arrives annually, the rest daily) |
| **E → F** (daily) | **T_skin (mandatory top thermal BC), G(T_skin), g_a** | boundary + flux | replaces F's air-temp Dirichlet BC (`update_soil_thermal_state.c:125`) so Rn/H/G share one surface temperature |
| **E → ATM** (sub-daily) | LE, H, G, T_skin, NBP_atm(=Rh+firec−NPP−flux_estabc), z0 | fluxes + state | `Rn(T_skin)=LE+H+G` closed by construction; **H is the residual** |
| **ATM → F/E** | SWdown, LWdown, Tair, qair, **wind (sfcwind), psurf (ps)**, precip, CO₂ | forcing | wind + ps are NEW (LPJmL-FIT ignores both) |

**Cross-domain identities enforced:** `LE=λ·ET` (predict ET, derive LE; vaporization vs sublimation λ;
demand-cap water returned to F's soil reservoir when it binds); carbon handoff via flux-then-integrate
allocation of delivered `bm_inc` (softmax pool partition of a conserved input); soil-moisture reservoir
shared (F draws it down, S reads it for establishment/mortality); one skin temperature shared by
Rn, H, G. **H is a documented residual exception** (LE is water-limited, not free) — validate hardest
against FLUXNET.

**Signatures (units / dtype / source):** each payload maps to a §2 struct field or a §3 output id —
LAI (`m²/m²`, from `lai_stand`/allometry), height (`m`, `Pfttree.height`), z0 (`m`, `roughnesslength.c`),
FPC (`-`, Beer–Lambert), Vcmax proxy (from SLA/trait relations, `pft.h:230 vmax`), albedo (`-`),
`bm_inc` (`gC/m²/yr`, `Pft.bm_inc`), soil-moisture `w[23]` (`frac WHC`, `Soil.w`), LE (`W/m²` = λ·ET),
H/G (`W/m²`), T_skin (`K`), NBP_atm (`gC/m²/day`). Full field provenance is §2; this table is the
data-flow, the codeable signature is (§2 field × unit above).

---

## 9. Limitations carried forward (state in every report)

- **Daily source model** — no sub-daily physics to learn; sub-daily fluxes come only from re-solving
  E per sub-daily step at fixed daily structure/soil (not from linearly distributing daily means).
- **Energy balance is new physics with no in-model ground truth** — validate out-of-model
  (FLUXNET/PLUMBER2); accuracy bounded by that external data. **H is the least-controlled flux.**
- **LE=λ·ET bridge** is pragmatic (water-limited equilibrium ET, not energy-balance ET); needs a
  demand-limited cap with water returned to F.
- **Target is a distribution** (RNG-driven patch ensemble), not a single realization — evaluate
  distributionally, against the seed1-vs-seed2 noise floor (~11 % on cell-mean agb), never per-tree.
- **Constant-CO₂ regime** (`with_nitrogen="no"` → unbounded CO₂ fertilization → CO₂ held constant for
  the future). OOD test = warming/precip at constant CO₂, **not** rising CO₂; **not valid for
  CO₂-fertilization projections**. Upside: SpeedyWeather's lack of a carbon cycle is a non-issue
  (NEE diagnostic-only).
- **Pure-ML does not extrapolate** (the sibling's no-analog trait-syndrome failure); OOD robustness
  relies on the physical core F, conservation-by-construction, and climate-invariant input features.
- **CSV `ind` lacks disaggregated pools** — per-pool carbon needs a RAW re-run or allometric derivation.
- **Autoregressive stiff carbon+population system is failure-prone** (oscillations / "AC-gap" / blow-up;
  the sibling's IBM-AR drifted). Mitigate: flux-then-integrate, bounded outputs, multi-step rollout,
  explicit slow woody-C + population states, climate-conditioned memory, re-anchoring; verify with the
  LPJ_resilience battery incl. the shuffle test.
- **Prototype scope** — F1/E proven on one cell; **S on a small biome-stratified multi-cell set** (§5);
  full multi-cell generalization is a separate gated phase (Phase 5).
- **Noise-floor scope** — the seed1-vs-seed2 floor bounds only **annual distributional** error. Daily
  flux error is bounded against LPJmL's own daily output (no seed floor); energy (LE/H/T_skin) error
  only against FLUXNET/PLUMBER2 (no seed floor). The **SSP370** seed2 pair (needed for the OOD floor) is
  still generating — gate the OOD-distribution evaluation on its completion.
- **F1 callable-interface feasibility (Phase-3 risk)** — "keep the LPJmL-FIT C core, drive it with
  emulated structure via a library/thin interface" understates surgery on an MPI batch program with
  global state. Add a **Phase-3 spike** to prove a callable per-cell daily-biophysics entry point
  exists (or must be built) before committing to F1's "fast to stand up" schedule; the binary's
  `-couple host[:port]` socket interface (§0.7) is a candidate path worth evaluating first.
- **New forcings** (wind, surface pressure) are exercised only in the added energy layer E; both are
  **absent** from the production input config (§4.2) and must be sourced (§7.3).

---

## 10. Provenance appendix — every file:line cited this phase

Daily output: `fscanoutput.c:131,390-391`, `iterateyear.c:207-208`, `getmintimestep.c:24-27`.
No energy balance: `roughnesslength.c:19`, `petpar2.c:39,61,66,72`, `water_stressed.c:108,118,153`,
`update_soil_thermal_state.c:125,135`, `apply_heatconduction_of_a_day.c:31,64,80,172`, `update_daily.c:187`.
State vector: `soil.h:30-41,119-123,132-158,196,202-240`, `soil_20m.js:19-41`, `tree.h:48-51,96-135,137-152`,
`pft.h:219-256`, `types.h:104-108`, `climbuf.h:20-49`, `cell.h:53-59,108-162`.
Output schema: `fwriteoutput_ind.c:23-71`, `output.h:119-165`, `outputsize.c:63-68`,
`outputvars.js:80,87`, `fprintcsvflux.c:29-87`, `update_daily.c:159,452`, `soil.h:71`, `lpjparam_fit.js:37-38`,
`param.h:36-37`, `fscanparam.c:126-127`.
Patch identity/reservoir: `conf.h:25`, `initinput.c:41-47`, `iterate.c:217,256-257`,
`allocate_reservoir.c:39`, `iterateyear.c:73,81-83`, `mergepatch.c:17`, `setaside.c:362`,
`landusechange.c:872,936`, `landusechange_for_reservoir.c:36,44,62,296,312`, `standlist.c:95`,
`newgrid.c:360,477,628-632`, `annual_natural.c:251`, `initreservoir.c:114-131`.
huss dependency: `getvpd.c:27,34,38,41`, `waterstress_tree.c:35-37`, `daily_natural.c:130-132`,
`fscanconfig.c:255-256`, `dailyclimate.c:57`.
