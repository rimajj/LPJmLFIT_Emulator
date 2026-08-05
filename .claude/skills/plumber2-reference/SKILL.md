---
name: plumber2-reference
description: Stage and load the PLUMBER2 / FLUXNET observational reference that Component E (the surface-energy-balance + skin-temperature closure) is validated against — anonymous NCI THREDDS download, the 9-site biome-matched set, the model-facing half-hourly/daily/diurnal tables, and the unit/coverage/closure sanity report. Use whenever working with observed LE / H / Rn / T_skin / Ustar or tower forcing (wind, psurf, SWdown, LWdown, Tair, Qair, precip), adding a site, validating Component E against observations (line E, milestones E1/E4), or hitting the PLUMBER2 `_FillValue = -9999` masked-array trap. ALSO the P2 validation itself — scoring the SEB closure against the towers (Experiment A: tower forcing + the tower's own LE ⇒ H / T_skin / Rn skill, the |h_cor_uc| acceptance band, the diurnal cycle, the stability sweep). ALSO diagnosing a MISS in H / T_skin / G against the towers — the exact decomposition `ΔH = ΔRn − ΔG + ε_obs` (H is the residual, so `g_a` is in NONE of those terms), injecting an arbitrary or measured-`u*` `g_a` through the real solver, the tower-non-closure `ε_obs` trap that makes AU-Tum/AU-Rob unable to score nocturnal H, fitting `lambda_g`, and the check-the-native-DAILY-step rule. Use before ANY `stab_amp`/`lambda_g` sweep or retune. ALSO scoring a NEW E scheme against the towers (ADR 0074, the opt-in two-layer prognostic ground-heat column): the three-arm probe (default / previously-fitted / new) driven through the real `solve!`, the mandatory harness check that arms A+B reproduce ADR 0073's published R² digit for digit, drift measured as annual means with a second-half trend, and the two traps — a published layer thickness is tuned for the PUBLISHER's timestep (check `dt·rate` before adopting it; MITgcm's z1=0.2 m gives 1.125 at a daily step and makes G a day-to-day difference of T_skin), and a diagnosed flux belongs to the START of the step (asserting G against the post-step T1 is off by κ_g·ΔT1). Names scripts/fetch_plumber2_sites.py, scripts/validate_e_plumber2_load.py, scripts/build_e_seb_validation_table.py, scripts/validate_e_seb_vs_plumber2.jl, scripts/e_nocturnal_h_decomp.jl, scripts/e_two_layer_probe.jl, scripts/e_seb_drive_common.jl (the shared drive-table readers/metrics — reuse, do not copy a fourth time), data.energy_reference, ADR 0070/0072/0073/0074.
---

# plumber2-reference — the observational reference for Component E

Component E's LE / H / T_skin were `[ASSUMPTION]` ("invented quantities validated only out-of-model") until a
reference existed. This is how that reference is staged, loaded, and re-checked. Decision + site rationale:
**ADR 0070**. Line-E specifics and the E4 recipe: `lines/E/STATE.md`.

## The two commands

```bash
# 1. stage (idempotent; skips files whose size already matches the server)
/home/jamirp/.conda/envs/py311_new/bin/python3 scripts/fetch_plumber2_sites.py
#    SITES=DE-Hai,AU-Tum   only these       FORCE=1  re-download      OUT=<dir>  elsewhere

# 2. load + sanity report + derived tables
/home/jamirp/.conda/envs/py311_new/bin/python3 scripts/validate_e_plumber2_load.py
#    SITES=DE-Hai  NO_WRITE=1 (report only)  ROOT=<dir>  OUT=<derived dir>
```

Destination is read from `config/paths.yaml` → `data.energy_reference`
(`/p/tmp/jamirp/esm_land_emulator_data/fluxnet_plumber2`; 300 MB, git-untracked scratch by design):
`{Flux,Met}/<stem>_{Flux,Met}.nc` · `manifest.json` (URL + bytes + `sha256` per file) ·
`derived/{halfhourly,daily,diurnal}_<site>.parquet` + `plumber2_sanity_report.txt` + `site_summary.csv`.
A committed copy of the summary lives at `lines/E/data/plumber2_site_summary.csv`.

Both scripts run in seconds-to-a-minute on the login node (a ~120 MB download); no SLURM needed. Use
`scripts/sbatch_python.sh E-<tag>` if you ever pull the full 170-site set.

## Access (the fact that unblocked the line)

**[VERIFIED 2026-07-28]** PLUMBER2 v1-0 is served **anonymously over plain HTTPS** by the NCI THREDDS `ks32`
collection, reachable from the PIK login node — no registration, no token:

```
catalog:    https://thredds.nci.org.au/thredds/catalog/ks32/CLEX_Data/PLUMBER2/v1-0/Flux/catalog.html
fileServer: https://thredds.nci.org.au/thredds/fileServer/ks32/CLEX_Data/PLUMBER2/v1-0/{Flux,Met}/<stem>_{Flux,Met}.nc
```

170 sites: 102 `FLUXNET2015`, 45 `LaThuile`, 23 `OzFlux` (the origin is part of the file stem, e.g.
`DE-Hai_2000-2012_FLUXNET2015`). General HTTPS egress from the login node works (zenodo, ICOS, fluxnet.org,
NCI) — the blocked case is GitHub-over-HTTPS for git, not the whole internet. **Don't assume a dataset needs a
human download until you have curl'd the host.**

## Adding a site

Append to `SITES` in `scripts/fetch_plumber2_sites.py`: `id -> (PLUMBER2 stem, biome slot, note)`. The biome
slot must be one of the five in `test/testitems/biome_coupled_tests.jl` (`boreal_siberia`,
`temperate_hainich`, `mediterranean_iberia`, `semiarid_sahel`, `tropical_amazon`) so observations line up with
the coupled test. Get the exact stem from the catalog listing (the years are part of it). Never hard-code
lat/lon — the loader reads it from the NetCDF. Then re-run both commands; the manifest merges.

## The traps (each one cost a debugging round; don't re-derive them)

- **`_FillValue = -9999` leaks through `np.asarray()`.** netCDF4 hands back a *masked* array; `np.asarray`
  drops the mask, so the fill enters as data — DE-Hai's mean LE read **−2283 W/m²** instead of +32.2, Bowen
  −0.04 instead of 0.96. Use `np.ma.filled(np.ma.asarray(v[:]).astype("f8"), np.nan)`
  (`validate_e_plumber2_load.py::_series`).
- **A `*_qc == 5` flag in the *Flux* files means MISSING, not gap-filled.** Verified at DE-Hai: all 52 608
  flag-5 rows are fill rows and match the variable's own `Missing_%: 23.1` attribute. Compute QC composition
  over the *present* samples and report the missing fraction separately.
- **No `LWup` outside the OzFlux subset ⇒ no observable T_skin at DE-Hai.** Where `LWup` exists, invert E's own
  longwave term at E's own emissivity (`SEBParams.emissivity = 0.97`):
  `T_skin = [(LWup − (1−ε)·LWdown)/(ε·σ)]^(1/4)`, so `Rn_lw = ε·LWdown − ε·σ·T_skin⁴` matches the measured
  `LWdown − LWup` by construction. The ε = 1 brightness temperature differs by only +0.2…+0.5 K.
- **The towers do not close energy.** Uncorrected `(LE+H)` vs `(Rn−G)` slopes are 0.60–0.88; the EB-corrected
  `Qle_cor`/`Qh_cor` give 0.87–1.02. Score a closing model against the corrected fluxes and quote both.
- **`*_cor_uc` (the acceptance band) exists only on FLUXNET2015-sourced sites** — the OzFlux (T_skin) sites
  have none.
- **Calendar + time zone.** PLUMBER2 is a real **leap** calendar (drop 29 Feb before pairing with the model's
  noleap-365) and the time axis is **local standard time** — the loader proves this per site via the
  mean-diurnal `SWdown` peak hour (11.0–12.5 h at all 9). AU-Tum is **hourly**; the rest half-hourly.
- **Not every site has every variable.** GF-Guy has no `Qg`/`Qle_cor`/`Qh_cor`; OzFlux uses `GPP_LL`/`GPP_SOLO`
  instead of `GPP_DT`. Check presence, don't index blindly.
- **Range-check philosophy:** bands catch *unit* errors (K vs °C, Pa vs hPa, kg/m²/s vs mm/h), and a documented
  dataset artifact is admitted with a comment saying why — negative nighttime `SWup` (radiometer offset),
  negative `Ustar` at AU-ASM (drop u* ≤ 0 for any `g_a` check), in-canopy `CO2air` to 1250 ppm, half-hourly
  `GPP` to −48 µmol/m²/s. FAIL vs WARN splits at 0.1 % of the finite record. **Inspect the offending values
  before widening a band** — the whole point is that a real unit slip still FAILs.

## Sanity-report contents (what you get per site, so you don't re-write it)

metadata (lat/lon/elev/canopy + reference height/IGBP) · coverage % + QC composition + missing % ·
unit/range verdicts · observed `Rn/LE/H/G` means, the residual under **both** `Qg` sign conventions (it is
`positive INTO ground` at 7 of 8 sites that have `Qg`), the closure slope raw and corrected, and the daytime
`*_cor_uc` band · daytime Bowen (all-record + warm season) · the time-axis check · `T_skin` mean and
`T_skin − Tair` day/night. Plus the parquet triple: half-hourly (model-facing names + `*_qc`), daily (means,
`precip_mm`, `tair_{mean,min,max}`, valid counts, gap-filled fractions, `daily_ok` = ≥5/6 of the day present
for both LE and H), and the **mean diurnal cycle per month** — the sub-daily signal E4's diurnal test needs.

## Scoring the closure against the towers (the P2 gate — Experiment A; ADR 0072)

```bash
/home/jamirp/.conda/envs/py311_new/bin/python3 scripts/build_e_seb_validation_table.py   # tower-forced tables
STAB_SWEEP=1 scripts/sbatch_julia.sh E-e4a --project=. scripts/validate_e_seb_vs_plumber2.jl
# -> <energy_reference>/derived/seb_validation/{seb_drive_<site>.csv,.meta,e4_experimentA_report.txt}
```

**Experiment A vs B — get this right or the result means nothing.** `FToE` hands E `le` **already formed** as
λ·ET (`src/components/fast.jl:236`), so **LE is F's number**; E's own outputs are **T_skin, H (the residual)
and G**. Experiment **A** drives `solve_seb` with a tower's own forcing *and the tower's own `le_cor`*, which
excludes F's ET error by construction — a miss is E's. Experiment **B** feeds F's LE (the coupled case); the
**A − B difference is F's ET error**. Never present LE skill as E's.

**Conventions that make it honest** (all already implemented — don't re-derive):

- **albedo** = the tower's own daytime Σ SWup / Σ SWdown per day (nighttime albedo is undefined; instantaneous
  low-sun ratios are noise). Site median as the gap fallback.
- **`z_ref` = the site's MEASUREMENT height**, read from the NetCDF (43.5 m at DE-Hai, 70 m at AU-Tum), not
  `SEBParams`' 10 m default — `g_a` is evaluated at that level.
- **`z0m` = 0.1 · canopy height** — the only unobserved boundary value in the whole comparison.
- **`t_soil` = τ=30 d EWMA of DAILY-MEAN Tair.** `solve!` advances `t_soil` once per coupled step with
  `a = 1/tau_soil`; running that recursion at 30 min decays ~48× too fast. Same trap applies to any sub-daily
  use of the closure.
- **Score against `Qle_cor`/`Qh_cor`** (towers don't close energy: raw slopes 0.60–0.88, corrected 0.87–1.02),
  and use `|*_cor_uc|` as the acceptance band — it exists **only on FLUXNET2015-sourced sites**.
- **Report daily as well as half-hourly.** Half-hourly H R² is **inflated by the diurnal cycle** (DE-Hai 0.647
  half-hourly vs 0.257 daily): any closure driven by observed SWdown reproduces the day/night swing.

**Two traps this pipeline exists to remember:**

1. **`Qle_cor` can be ≈0 GARBAGE rather than a fill value.** At DE-Hai the uncorrected `le` is all-NaN for
   **2010–2012** and the EB correction emitted ≈0 there (annual mean 0.39 / −0.09 / 0.04 W/m² vs 30–40 in
   2000–2009) while `h_cor_uc` vanishes. A finiteness filter keeps 36 550 rows of it, and feeding the closure
   LE ≈ 0 pushes all available energy into H — it inflated DE-Hai's H bias to **+39.8** instead of **+6.4**
   W/m². **Always require the UNCORRECTED `le` to be finite too.**
2. **A committed fixture must be stratified ACROSS the record**, not taken from one year — sample every 12th
   day of year × every 3rd hour. The single-year attempt landed inside DE-Hai's broken window (that is how
   trap 1 was found), and subsampling every Nth *surviving* row drifts across the diurnal cycle.

**Current verdict to compare against** (ADR 0072, 497 936 steps, 4 sites): `Rn` R² 0.986–0.996 · `T_skin` daily
RMSE 1.41–1.97 K / R² 0.76–0.95 · `H` bias +6.4…−19.2 W/m² with 76.4 % of DE-Hai daily means inside the band,
daily R² 0.125–0.778, **nocturnal R² −1.0…−5.6**. The CI regression gate lives in
`test/testitems/energy_closure_tests.jl`. ADR 0072's *diagnosis* of that failure (items 4 + 6) is **superseded
by ADR 0073** — see the next section before touching `stab_amp`.

## Diagnosing a residual in H — do this BEFORE any sweep (ADR 0073)

```bash
scripts/sbatch_julia.sh E-e6decomp --project=. scripts/e_nocturnal_h_decomp.jl
# -> <energy_reference>/derived/seb_validation/e6_nocturnal_h_decomp.txt
```

**`H` is not predicted — it is the EXACT residual `Rn_m − LE − G_m`.** So writing the tower's own non-closure
as `ε_obs ≡ Rn_o − LE − H_o − G_o`, the H error obeys *identically* (algebra, not a hypothesis):

    ΔH = ΔRn − ΔG + ε_obs  =  ΔRn − (G_m − G_res),   G_res ≡ Rn_o − LE − H_o

**`g_a` is in none of those terms** — it acts only by moving the solved `T_skin`. Decompose first; a
parameter sweep on `H` cannot tell you which term it is moving. The drive tables already carry `g_obs` and
`rn_obs`, so the decomposition costs nothing.

- **A `stab_amp`/`g_a` sweep that looks monotone is usually BIAS CANCELLATION.** Measured (ADR 0073): the
  closure's nocturnal `g_a` is within **0.7 %** of DE-Hai's measured-`u*` value, substituting the measurement
  makes night H **worse at all 4 sites**, and a **100× `g_a` bracket** never reaches positive nocturnal R².
  Suppressing `g_a` merely shifts the skin in the direction that offsets the ground-heat error.
- **Inject an arbitrary `g_a` through the REAL solver — never re-implement it.** With
  `enable_stability=false`, `g_a = k²U/(lm·lh)` is exactly proportional to wind, so scaling `wind` is an exact
  `g_a` multiplier, and `U_eq = g_a_target·lm·lh/k²` reproduces any target (e.g. the tower's
  `g_a* = 1/(U/u*² + ln(z0m/z0h)/(k·u*))` from the `ustar` column). Report how often `U_eq` hits the 0.1 m/s
  `min_wind` floor — it binds on 1–9 % of steps.
- **`ε_obs` is a first-class term, not noise.** Mean nocturnal `ε_obs`: DE-Hai **−0.32** (the tower closes),
  AU-ASM −12.0, AU-Rob −47.5, AU-Tum **−62.3** W/m². A model that closes exactly *cannot* match `H_o` where
  `ε_obs` is large ⇒ **AU-Tum and AU-Rob cannot score nocturnal H at all** (they stay valid for `T_skin`).
  Score H at DE-Hai and AU-ASM.
- **Fit `λ_g` against BOTH targets and compare** — the measured plate `G_o` and the budget-implied `G_res`.
  They agree only where `ε_obs ≈ 0` (DE-Hai 0.94 vs 1.27) and diverge 10× where it is not (AU-Tum 0.90 vs 9.67,
  AU-Rob 1.46 vs 19.92). That divergence is the `residual-diagnosis` §3b population signal, and it is how you
  decide which sites can constrain a parameter at all.
- **CHECK THE MODEL'S NATIVE STEP BEFORE CALLING A SUB-DAILY MISS A BUG.** `run.jl::couple_day!` calls
  `solve!` **once per day** (`src/run.jl:93`), so a half-hourly diagnosis is of a regime the coupled model
  never runs in. Aggregate the drive table to daily means and solve once per day — that is the operational
  number. Doing this is what turned "nocturnal H is broken" into "`λ_g = 7.0` is a *diurnal-amplitude*
  conductance applied to a *daily-mean* gradient".
- **The standing finding:** `λ_g ≈ 1.0`, not the 7.0 default, at the daily step — implied `λ_g` 0.83–1.10 at
  all four sites, it reproduces the observed daily sd(`G_o`) 4.3–6.3 W/m² (the default gives 14–31), and daily
  H R² goes 0.03 → **0.64** (DE-Hai) / 0.33 → **0.74** (AU-ASM). **No default was changed** — `lambda_g` is an
  E→M integration point; `SEBEnergyClosure(params = SEBParams(lambda_g = 1.0))` already works today.
- **Nocturnal R² > 0 is NOT reachable by any `λ_g`** in the present form (`ε_obs` scatter alone is the size of
  the night H RMSE). That needs a force-restore / two-layer soil scheme + canopy heat storage — a design
  change, and the blocker for line O's sub-daily online coupling.

## Scoring a NEW ground-heat scheme (E7 / ADR 0074) — and the two traps that cost a run each

```bash
scripts/sbatch_julia.sh E-e7probe --project=. scripts/e_two_layer_probe.jl
# OUT=<path> to keep several runs side by side; SITES= to subset
# -> <energy_reference>/derived/seb_validation/e7_two_layer_probe.txt
```

`scripts/e_two_layer_probe.jl` is the template for comparing ANY new E scheme against the towers. Reuse it
rather than writing a fresh driver, and reuse **`scripts/e_seb_drive_common.jl`** for the readers/metrics/daily
aggregation (`read_drive_csv`, `read_meta`, `skill`/`fmt`, `nanmean`/`nanstd`, `loglaw`, `run_site`,
`aggregate_daily`) — those were copied three times before being extracted; do not make a fourth copy.

What that probe gets right and a hand-rolled one usually does not:

- **Three arms on the same rows** — default, the previously-fitted parameter, and the new scheme — so the new
  scheme is judged against the *best existing option*, not against the untuned default (which flatters it).
- **A harness check before any verdict** (`residual-diagnosis` §3): arms A/B must reproduce ADR 0073's
  published per-site daily H R² **digit for digit** (DE-Hai 0.03/0.64 · AU-ASM 0.33/0.74 · AU-Tum −0.48/−0.35 ·
  AU-Rob 0.07/−0.17) and the observed daily sd(`G_o`) 4.3/6.3/4.3/6.0. If those drift, the harness is wrong,
  not the physics.
- **A stateful arm driven through the real `solve!`**, not a re-implementation, so what is scored is what
  `run.jl` runs. Guard non-finite forcing rows by **skipping without advancing** any prognostic state — one
  NaN poisons a reservoir for the rest of the record.
- **Both steps.** Daily = the operational number (`run.jl:93`); sub-daily = where a diurnal wave shows up.
- **Drift as ANNUAL MEANS with a second-half trend**, never `(last − first)/years`: the seed is an annual mean,
  so the first step jumps several K and a raw endpoint difference reports spin-up as drift. Short records look
  like drift and are interannual variability — the 16-year AU-Tum record is the one that settles it.

**TRAP 1 — a published layer thickness is tuned for the publisher's TIMESTEP.** Before adopting any
reservoir/relaxation parameter from an upstream model, compute the relaxation number
`dt·(sum of conductances)/(thickness · heat capacity)` at **our** step. MITgcm/SpeedyWeather's `z1 = 0.2 m` is
for a minute-scale model; at `dt = 1 d` it gives **1.125**, so the top layer equilibrates within one step and
`G` degenerates into a day-to-day *difference* of `T_skin` (daily G R² −2.8, sd(G) 2.2× observed). The scheme
looked mediocre for this reason alone. `z1 = 0.75 m` gives 0.093. Sweep the thickness and report the number.

**TRAP 2 — a diagnosed flux belongs to the START of the step.** `G` is computed from the pre-step `T1`, and
`solve!` then advances the column, so asserting `G == κ_g(T_skin − clo.t_soil1)` *after* the call is off by
exactly `κ_g·ΔT1`. Capture the pre-step state first. (This produced 54 identical CI failures.)

**The standing E7 finding:** `enable_two_layer = true` beats the fitted `λ_g = 1.0` at both sites whose towers
can score H — daily H R² 0.645 vs 0.637 (DE-Hai), 0.775 vs 0.745 (AU-ASM); daily G R² 0.717 vs 0.657 and
0.614 vs 0.477 — and unlike a coefficient it carries a diurnal soil wave (sub-daily DE-Hai sd(G) 5.75 vs
observed 5.66; night G R² **+0.394**). **Nocturnal H R² is still negative** (−0.324) and always will be while
`ε_obs` scatter is the size of the night H RMSE — canopy heat storage is the remaining term, not a tune.
