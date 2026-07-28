---
name: plumber2-reference
description: Stage and load the PLUMBER2 / FLUXNET observational reference that Component E (the surface-energy-balance + skin-temperature closure) is validated against — anonymous NCI THREDDS download, the 9-site biome-matched set, the model-facing half-hourly/daily/diurnal tables, and the unit/coverage/closure sanity report. Use whenever working with observed LE / H / Rn / T_skin / Ustar or tower forcing (wind, psurf, SWdown, LWdown, Tair, Qair, precip), adding a site, validating Component E against observations (line E, milestones E1/E4), or hitting the PLUMBER2 `_FillValue = -9999` masked-array trap. Names scripts/fetch_plumber2_sites.py, scripts/validate_e_plumber2_load.py, data.energy_reference, ADR 0070.
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
