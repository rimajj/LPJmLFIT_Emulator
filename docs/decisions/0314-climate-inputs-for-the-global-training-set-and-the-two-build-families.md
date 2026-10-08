# 0314 — Climate inputs for the global training set, verified end to end; the two model-build families differ in table layout and in parameters

* **Status:** **accepted — line X data preparation** (2026-10-08). Executes step 2 of ADR 0313's consequences.
* **Date:** 2026-10-08.
* **Line:** X. Tier-1 block 0310–0329. **Next free number: 0316** (0315 is the round-1 venue pre-registration).

## 1. What was built

`scripts/explore_glob_climate.py` → `/p/projects/open/Jamir/esm_land_emulator_data/billing_global/climate/`:
`cell_year/<gcm>_<scen>.parquet` for GFDL-ESM4 historical (1951–2014), ssp126/245/370 (2015–2100) and GSWP3-W5E5
obsclim (1951–2019), 67 420 cells each, `grid.bin` order (joins the converted tree tables on `Cell` directly), 158
columns: the Germany arms' feature names (monthly means, the annual set, `*_tr20`, `anom_*` against the same forcing's
1985–2014 cell mean, `tstress_pft0..6`, `vpd_*_eff`) plus `huss_mean` and hemisphere-summer `prec_hs`/`cwb_hs`/`vpd_hs`.
`*_tr20` is computed from real forcing years (1932 on) — no padding assumption, unlike Germany. `cell_static.parquet`
carries lon/lat/soil/rock.

## 2. Model formulas the features use, as these runs are configured `[VERIFIED from the run configs + Feb-build source]`

* **Net longwave** (`"radiation": "radiation"`): PET uses `lwnet` as given, with no σT⁴ term (`petpar2.c`, `islwdown`
  false). Germany read downward longwave — a different formula, same feature name family (`lwnet_ann` here, never
  `lwdown_ann`).
* **Specific humidity** (`"relative_humidity": false`, `huss` kg/kg): `getvpd.c` converts with
  `rh = 0.263 · 1013.25 · q / exp(17.67 T / (T + 273.16 − 29.65))`, clipped at 1. ⚠ **This looks like an hPa/Pa slip and
  is not one:** with the pressure in Pa the textbook formula returns *percent*; in hPa it returns a *fraction*.
  Measured: mean relative humidity 0.69 in every leg, 4.3–4.5 % of days clipped at saturation. (A session briefly
  claimed the opposite from mental arithmetic; the script's own check refuted it before anything was published.)
  ADR 0313's statement that these runs carry no humidity defect stands.
* **Stress accumulators reset on day 14 north / day 195 south** (CLAUDE.md, ADR 0244), so `tstress_*` and
  `vpd_win10_sum` count days 15–365 / 196–365 per cell. Air temperature stands in for top-soil temperature in the
  >10 °C gate `[ASSUMPTION]`. Wind is built for layout parity only — the runs never read it (GlobFIRM, no nitrogen).

## 3. The end-to-end check

The printed per-tree `mort_temp` must equal `min(1, factor · tstress_pft<Type> / 365)` computed from these tables.
That fails if the forcing file, the cell order, the year alignment or the reset day is wrong. Result over the
`ind_dev` tables (every 10th cell, all years but the first): **38 of 38 tables, 1 147 183 867 tree-year rows, 100 %
within print precision** (max error 5 × 10⁻⁷ on the GFDL-ESM4 tables). Also passing: every forcing value in range,
no NaN, header kinds as expected (tas/pr/rsds/lwnet/sfcwind v2 int16 with scalar; huss v3 float32).

## 4. Finding: the two build families are different models, visibly

The 32 GFDL-ESM4 tables (Feb-5 and May-26-2026 builds) matched with the repo's parameter table at first try. The six
reanalysis tables (Oct-1/6/7/8 builds) first matched on only 94.6–94.9 %, and the failure was informative:

* **Mortality parameters differ.** The printed value implies exactly **0.8 × the stress-day count** — Billing's live
  `par/pft_lpjmlfit.js` (edited 2026-10-08 10:40) sets `MORT_TEMP_FACTOR` **4.0** where the earlier builds used
  **5.0**, and the tropical tree's cold-stress limit **14 °C** where they used **12.5 °C**. With factor 4.0 the six
  tables match 100 % for tree types 1–6; type 0 is reported ungated because the tables count days below 12.5 °C. The
  mortality source also changed (`BM_INC_COUNTER_MAX` 5 → 10, a `MORT_MIN_NPP` term, a stem-diameter state).
* **The per-tree table layout differs.** The Oct builds write 30 columns: + `Height_max` (a trait in that build),
  `stemdiam`, `barkthickness`, `mort_fire`; − `wscal_mean`, `beta_root`, `k_root`. The converter refused it
  (`header drift`) rather than mislabel columns; it now converts that layout natively (`use_layout`), and the
  registry records `ind_layout` per member.
* ⚠ **Parameters are read from a directory edited in place, at run start.** The build date identifies the binary,
  not the parameters; what a run actually used is recoverable only from its own output, as done here.

So the model-version transfer split of ADR 0315 (GV) is a real test: the Oct-build members differ in mortality
parameters, in mortality code, and in which per-tree quantities exist. An arm that conditions on `wscal_mean` cannot
even be evaluated on them without a substitute.

## 5. Consequences

* Climate inputs exist for every converted member-window; the arms can be re-targeted (ADR 0315).
* `tstress_pft<k>` embeds the Feb-build thresholds. For the Oct family, type 0's count is at the wrong threshold;
  add a 14 °C variant if an arm uses it there.
* A run of the Oct family cannot be pooled with the others on columns either family lacks.
