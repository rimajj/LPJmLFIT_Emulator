# Data spec — extended Phase-1 outputs for the flux-driven Component S

Buildable **design of record** for the extended Phase-1 data task in
[ADR 0020](decisions/0020-component-s-flux-driven.md) (S is flux-driven, not climate-equilibrium) and
DEVELOPMENT_PLAN §3. It defines, per cell/year and **aligned to the annual `ind` distribution**, the F and
mortality-driver variables the flux-driven S is trained on. Every definition is `[VERIFIED]` against the
LPJmL-FIT C source (`/home/jamirp/lpjml56fit`), commit-pinned per the reproducibility rule (§3 of the plan).

> **Headline finding (audit this before assuming a big C-source job):** the **four mortality drivers are
> ALREADY emitted** in the annual `ind` output (`src/lpj/fwriteoutput_ind.c` `printind`, TXT columns 22–26:
> `mort_npp, mort_age, mort_water, mort_temp, mort_prob`). The genuine data *gap* is narrow — per-individual
> `bm_inc`/`turnover`/`nind` (the conservation budget) and the **raw** `water_stress`/`temp_stress`
> accumulators (needed only for within-year *statistics* beyond the derived drivers, and largely
> reconstructable from the existing daily set). Do not over-scope this as "add all mortality outputs."

## 1. Alignment key

Each `ind` row is one representative individual of a (cell, year, patch, PFT). The join key for the slow
table is **`(cell, year, patch, index, id)`** — `index = tree->index` identifies the individual, `id` the
PFT, `patch` the patch (npatch samples of the within-cell distribution), `cell` the grid cell (Hainich =
global-grid `42490`). Trees appear/disappear across years (establishment/mortality), so the AR "year-(t−1)
summary" is a *distribution* summary keyed by (cell, patch), not a per-individual carry-over.

## 2. What is already available (no recompile)

**Annual `ind` output — TXT columns** (`printind`, `Output_ind` in `include/output.h`), already written when
the `ind` output is enabled. `[VERIFIED 2026-07-22 against the real 46 GB `ind_2000_2019.csv` + the writer]`:
the emitted TXT has **exactly 29 columns** (header row present) — `Year, ID(=tree->index), Type(=PFT id),
Height, Age, agb, vegc, transp, npp, gpp, wscal_mean, SLA, Longevity, Wooddens, LAI, fpc_ind, minwscal, D95,
D95max, beta_root, k_root, mort_npp, mort_age, mort_water, mort_temp, mort(=mort_prob), isdead, Patch, Cell`.
This ground truth is also pre-converted to parquet at
`/p/tmp/jamirp/emulator_global/ind_hist_seed{1,2}_all.parquet` (frozen 29-col schema,
`python/src/lpjmlfit_emulator/data.py::IND_COLUMNS`) — scan/filter it, do **not** parse the 46 GB CSV.

| Group | Fields **actually in the annual TXT `ind` output** |
|---|---|
| Distribution axes (S-owned + F-derived) | `Height, LAI, SLA, Wooddens, leaf_longevity(Longevity), D95, D95max, beta_root, k_root, fpc_ind, minwscal, agb, vegc, Age` |
| **Mortality drivers (the four + sum)** | **`mort_npp, mort_age, mort_water, mort_temp, mort(=mort_prob)`** |
| Per-PFT annual fluxes / state | `npp` (=`pft->anpp`), `gpp` (=`pft->agpp`), `transp` (=`pft->atransp`), `wscal_mean`, `minwscal` |
| Keys | `Year, ID(=tree->index), Type(=PFT id), Patch, Cell, isdead` |

> **[CORRECTION 2026-07-22]** An earlier draft of this table listed `stemdiam, crownarea, leafarea, fpc` as
> present in the annual `ind` output. They are **NOT** in the TXT writer — they are commented out of
> `printind` and appear only in RAW `ind` output (see the RAW paragraph below). Only `fpc_ind` (not the
> whole-individual `fpc`) is emitted in TXT. A naive `nind` reconstruction from the FPC relation therefore
> needs `crownarea`, which is RAW-only.

**Daily set** (the 186 GB `daily_2000_2019_global_...` DVC dataset): `transp, swc(-layer), gpp, npp, rh` and
the water-balance terms are present. These carry the within-year *timing* the annual `ind` row averages away.

**In the RAW `Output_ind` struct but commented out of the TXT writer** (uncomment in `printind` **or** write
`ind` in `RAW` format, which dumps the whole struct): `bm_inc_counter, stemdiam, crownarea, leafarea,
rootmass, sapwood, heartwood, alphaa, boleh`. `bm_inc_counter` is needed to invert `mort_water`/`mort_npp`
(see §4) — prefer RAW `ind` output, which already contains it.

## 3. The gap and how to close it

Three tiers, cheapest first. Pick per how faithful the flux feature must be.

1. **No recompile — use what is emitted. `[DONE — the Hainich prototype ships on this tier]`** The four
   derived drivers (`mort_*`) + `npp`/`gpp`/`transp`/`wscal_mean` + the distribution axes already give a first
   flux-driven S. `bm_inc` is taken as the emitted per-individual `npp` (=`pft->anpp`) — this is
   **runtime-consistent** with `FToS.bm_inc` (the coupled `bm_inc_cell = sum(npp_ind)`), not the raw
   `pft->bm_inc.carbon` (which is the post-allocation residual at output time; see the tier-3 caveat).
   `growth_eff` is **inverted from the emitted `mort_npp`** (monotone in `bm_delta/leafarea_real`; ~86 % of
   Hainich living-tree rows are invertible, the rest have `mort_npp ≥ mort_max` ⇒ `bm_inc_counter>0` or a
   cap, needing tier 3). Stress accumulators are inverted from `mort_water`/`mort_temp` (§4) + within-year
   *statistics* from the daily set (§5). **Builder: `scripts/build_slow_flux_table.py` (validated §7).**
   Sufficient to stand up the retrain and run the OOD benchmark.
2. **RAW `ind` output (config-only, no source change).** Set the `ind` output format to `RAW` (`"fmt":"raw"`)
   so `fwrite(output,sizeof(Output_ind),1,file)` dumps the whole struct — every field commented out of the
   TXT writer (`bm_inc_counter, stemdiam, crownarea, leafarea, rootmass, sapwood, heartwood, alphaa, fpc,
   boleh`) then appears with no recompile. Enables exact `water_stress` inversion (needs `bm_inc_counter`)
   and `nind` reconstruction (needs `crownarea`). **`[VERIFIED — LIMIT]` RAW canNOT yield `bm_inc`, `nind`,
   or `turnover`: those fields do not exist in `Output_ind`.** RAW is also a flat per-run binary stream with
   **no header/metafile** and alignment-sensitive layout (no Python reader exists) — so for the three target
   quantities RAW is *not* enough, and its bespoke binary parser is a real cost. Prefer tier 3.
3. **Small C-source addition + rebuild** (for exact per-individual `nind`/`turnover` + the clean-CSV path).
   `[VERIFIED plumbing]` The `ind` output uses the `Output_ind` **struct stream** (`fwriteoutput_ind.c`), NOT
   the `outputmap`/`NOUT` machinery — so, unlike `patches/lpjmlfit_daily_grass_gpp.patch`, a tier-3 patch does
   **not** touch `conf.h`/`outputvars.js`/`daily_natural.c` (the `IND` id already exists). Minimal patch
   (3 files): add `nind` (`= pft->nind`, a durable `Pft` field) and `turnover_ind`
   (`= Σ pool_c·turnover_rate`, computed in `getind`) to the struct + `getind` + `printind` TXT + the
   `fopenoutput.c` header; and **uncomment `crownarea`/`leafarea`/`bm_inc_counter`** in the TXT writer (they
   are already filled by `getind`). **Do NOT copy `pft->bm_inc.carbon` at `getind` time — it is the
   post-allocation residual (0 for grass); use the emitted `npp`/`anpp` for the budget instead.** Rebuild per
   the `lpjmlfit-cbinary` skill (json-c **0.13.1**, exact module set); keep it a committed patch. Physics is
   unchanged ⇒ the rebuilt binary reproduces the same trajectory (guardrail 4).

`nind` (individual density, indiv/m²) is **reconstructable** from `fpc_ind`, `crownarea` and the individual
`lai` via `fpc_ind = crownarea·nind·(1 − exp(−0.5·lai_ind))`, but `crownarea` is **RAW-only** — so exact
`nind` needs tier 2 (RAW) or tier 3 (the direct field). Add it in tier 3 if reconstruction precision is
inadequate for the carbon-budget check (§7.3).

## 4. Exact C-source definitions (`[VERIFIED]`)

> **`[VERIFIED 2026-07-22]` Parameter values + hazards (adversarial re-derivation; recompute passes on real
> data, §7).** Every formula below matches the C source verbatim. The load-bearing traps a porter MUST heed:
>
> - **`longevity` for `mort_age` = the JSON key `"age"` = `TREE_LONGEVITY = 400`** for beech (mapping
>   `fscanpft_tree.c:271`), **NOT** the JSON field literally named `"longevity"` (`= 2.0`, which is *leaf*
>   longevity). Using 2.0 is off by ~200×.
> - **`k_mort = 0.01`** (active `par/lpjparam_fit.js`), NOT the `0.2`/`0.5` in unloaded `lpjparam*.js` or the
>   commented `#define` in `mortality_tree_ind.c`.
> - **`mort_max` is the wood-density formula** (`mortality_tree_ind.c:92`); the pft `mort_max`:0.025 and the
>   `0.005` biomass value on lines 84–87 are **dead assignments** (overwritten). Ignore them.
> - **`mort_prob` (col `mort`) is saved AFTER** the cap-at-1 + the immediate-death (`bm_inc_counter≥5⇒1`) +
>   ghost-tree (`leaf<sapling⇒1`) overrides. On override rows the four components do **not** sum to `mort`;
>   the §7.1 parity check must exclude them (flag `emitted==1 & Σcomponents<1`).
> - **AGE ALIGNMENT (`[VERIFIED]` this session).** The emitted `Age` is the **post-increment** year-end age
>   (`getind`, `annual_tree.c:46`), but the same row's `mort_*` were computed with the **pre-increment** age
>   (`mortality_tree_ind` at `annual_tree.c:31-38`). So the age feeding a row's mortality is **`Age − 1`**.
>   Recomputing `mort_age` from `Age − 1` matches the emitted column to **~5e-8** (the `%g` rounding floor);
>   from `Age` it is off by up to ~1.4e-4. Carry `age_mort = Age − 1` in the table.
>
> **Beech (PFT id 3) values** (`par/pft_lpjmlfit.js` + `par/lpjparam_fit.js`): `wdmort_1=-2.465`,
> `wdmort_2=0.148`, `mort_water_factor=5`, `mort_temp_factor=5.0`, `mort_water_res=0.75`, `aphen_min=60`,
> `temp_stressed=[-20.0, 54.0]`. C constants: `KMORT_2=0.2`, `KMORTBG_LNF=-ln(0.001)`, `KMORTBG_Q=2.0`,
> `BM_INC_COUNTER_MAX=5`. (The other temperate tree types 1/2/4/5 at Hainich are <6 % of rows and reuse these
> temperate values with a flag; the scale-up must read each PFT's own params.)

From `src/tree/mortality_tree_ind.c`, `waterstress_tree.c`, `tempstress_tree.c` (`NDAYYEAR = 365`):

- **`bm_delta = pft->bm_inc.carbon / pft->nind − turnover_ind`** — per-individual net biomass increment.
- **`leafarea_real = tree->ind.leaf.carbon · pft->sla`** (= `leafarea` in the `ind` output).
- **growth efficiency** (the greff argument) **`= bm_delta / leafarea_real`**.
- **`mort_npp`** `= mort_max / (1 + 0.2·exp(param.k_mort · bm_delta/leafarea_real)) · (1 + bm_inc_counter)`,
  capped at 1; if `leafarea_real ≤ 1e-6` then `mort_npp = 1`. **`mort_max = 10^(wdmort_1 + wdmort_2/(wooddens/1e6))`**
  (wood-density dependent; `wdmort_1`, `wdmort_2` from `par/pft_lpjmlfit.js`).
- **`bm_inc_counter`**: `+1` each year `bm_delta < 0`, reset to 0 on `bm_delta ≥ 0` (and at `age==1`);
  `counter ≥ 5` ⇒ immediate death (`mort=1`).
- **`mort_age`** `= min(1, −log(0.001)·(2+1)/longevity · (age/longevity)^2)` (`KMORTBG_LNF = −log(0.001)`,
  `KMORTBG_Q = 2`, `longevity` from `par/pft_lpjmlfit.js`).
- **`mort_water`** `= (treepar->mort_water_factor · tree->water_stress / 365) · (1 + bm_inc_counter)`, cap 1.
  **`water_stress`** accumulates daily (reset at the coldest day, `waterstress_tree.c:35`):
  `water_stress += pft->phen · (getvpd(...)/1000 [kPa]) · ((mort_water_res − minwscal) − wscal)`, only when
  `aphen > aphen_min`, `soil->temp[0] > 10 °C`, and `wscal < mort_water_res − minwscal`.
- **`mort_temp`** `= treepar->mort_temp_factor · tree->temp_stress / 365`, cap 1. **`temp_stress`** is the
  annual **count of stress days**: `+1` each day `temp < temp_stressed.low` or `temp > temp_stressed.high`
  (`tempstress_tree.c:30`, reset at the coldest day).
- **total** `mort = mort_npp + mort_age + mort_water + mort_temp`, capped at 1 (then the immediate-death and
  ghost-tree overrides). `mort_prob` = this sum (pre-logging).

**Inversion (when not capped), for reconstructing the raw accumulators from tier-1/2 outputs:**
`water_stress = mort_water · 365 / (mort_water_factor · (1 + bm_inc_counter))`;
`temp_stress = mort_temp · 365 / mort_temp_factor`. Both fail at the `=1` cap — flag capped rows and prefer
reconstruction from the daily set for those.

## 5. Within-year stress statistics from the daily set (extremes, timing, counts)

ADR 0020 requires *statistics*, not just annual means. Build these per (cell, year) from the daily data,
**not** from the annual `ind` row:

- **Heat/cold-stress-day count** = number of days with daily `temp` outside `[temp_stressed.low,
  temp_stressed.high]` — this **is** `temp_stress` by definition (`tempstress_tree.c`), recoverable directly
  from the daily temperature forcing and the PFT thresholds.
- **Water-stress peak / timing / stress-day count** — apply the `waterstress_tree.c` daily formula to daily
  `swc`/`wscal`, VPD (from daily T + humidity), and phenology: peak daily increment, day-of-year of peak,
  count of days the threshold `wscal < mort_water_res − minwscal` is crossed while `soil.temp[0] > 10 °C`.
- **End-of-year vs growing-season soil moisture** = daily `swc` sampled at year-end and averaged over the
  growing season (phenology-gated), **not** the annual mean.

## 6. Output → `FToS` feature mapping (train/runtime consistency)

The offline training table columns map onto the runtime F→S interface (`src/interface.jl` `FToS`), so S is
trained on the same channel it is conditioned on at runtime (ADR 0020 §5):

| `FToS` field (runtime) | Training-table source (offline, LPJmL true flux) |
|---|---|
| `bm_inc` | per-individual `bm_inc.carbon` (tier 3) or cell/patch `npp` (tier 1); the conservation budget |
| `water_stress` | raw `water_stress` (tier 2/3 or inversion) + within-year stats from the daily set (§5) |
| `temp_stress` | `temp_stress` day-count (daily set, §5) + timing |
| `growth_eff` | `bm_delta / leafarea_real` (from `bm_inc`, `nind`, `turnover`, `leafarea`) |
| `soilmoist` | root-zone `swc` — EOY + growing-season (daily set, §5), not the annual mean |

**Note the interface extension ADR 0020 requires:** `FToS` currently carries 5 scalars; the *statistics*
(peaks, timings, stress-day counts) need additional fields. That is an interface change — keep it
**opt-in, default byte-identical** (guardrail 4) behind `run_coupled_cell(...; slow=)` until the
flux-conditioned weights exist.

## 7. Validation before training (guardrail 5 — adversarially re-derive)

1. **Definition parity:** recompute `mort_npp`/`mort_age`/`mort_water`/`mort_temp` from their inputs (§4) on
   a sample of `ind` rows and match the emitted `mort_*` columns to ~1e-6 (catches a wrong factor / cap /
   `bm_inc_counter` handling).
2. **`temp_stress` cross-check:** the daily-reconstructed stress-day count (§5) must equal the inverted
   `temp_stress` (§4) on non-capped rows.
3. **Budget tie-out:** per-cell `Σ_individuals bm_inc` (or `npp`) must reconcile with the cell-level annual
   NPP and the carbon-closure `ΔC = NPP − Rh − firec + flux_estabc` (the Phase-1 closure gate) — this is what
   makes `bm_inc` usable as *both* feature and conservation budget.

## 8. Build / run

- Enable/adjust the `ind` output (RAW for tier 2) in the production config; regenerate for the prototype cell
  and the biome-stratified set via `scripts/run_daily_subset.sh` (positional args in CLAUDE.md §3) — the
  daily-set variables are already produced; add the `ind`-format change and, for tier 3, apply the C-source
  patch and rebuild (`lpjmlfit-cbinary` skill).
- Prototype cell: Hainich, global-grid `42490` (`STARTGRID=ENDGRID=42490`), restart from
  `restart_1999.lpj` for the Historical 2000–2019 re-run.
- Materialise the slow table (join annual `ind` + daily-derived stats + Climbuf/soil/CO₂ boundary) with the
  Python loaders under `python/`; keep it out of git (DVC/`/p`), only the schema + a small fixture committed.
</content>
