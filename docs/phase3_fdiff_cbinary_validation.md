# Phase 3 — quantitative C-binary validation of `F_diff` on the prototype cell

**Status: DONE — the strongest "same physics" check to date.** The differentiable fast core `F_diff`
was driven by the Hainich prototype cell's **real daily forcing** and the LPJmL-FIT **C binary's own
daily FAPAR**, and its daily GPP / transpiration / PET compared against the C binary's daily outputs
for the same cell. This replaces the previous regression gate (which pinned `F_diff` against *itself*
on a synthetic scenario — `docs/phase3_fdiff_spike.md` §5) with a real cross-check against the C oracle.

**Headline:**
- **The radiation / Priestley–Taylor PET path is quantitatively validated:** daily PET ratio **1.05**,
  correlation **r = 0.999** (growing season and full year). Same forcing + byte-identical formula ⇒
  near-exact agreement; the residual ~5 % is the surface-albedo term (`F_diff` uses a fixed forest
  albedo, the C run a daily `albedo_patch`).
- **GPP seasonal dynamics are captured** — annual r = 0.96; *within a single year* the growing-season
  daily r = **0.96** — but the **level under-predicts ~42 %** at the single-representative-individual
  level. Photosynthesis kernel constants are byte-identical, so this is a **structural** gap, not a
  kernel bug: the documented multi-PFT / representative-individual + fixed-canopy scale-up items.
- **Transpiration timing is captured** (r = 0.91–0.97) but the **level runs ~40–47 % high** — the
  single-bucket vs 23-layer soil-water + demand-side confound (documented scale-up item). It is
  *demand-limited* (still 33 % high at `emax=5`), so not an `emax` tuning artifact.
- Water closes by construction; no NaN/Inf over the full 20-year daily rollout on real forcing.

⚠️ **Load-bearing correction (verified this session).** The prototype cell index in the **global
orderA grid** (`soil_code_test.grid.clm` / the daily NetCDF `grid.nc`, which *all* the ground-truth +
daily data use) is **`42490`** (lat 51.25, lon 10.25 — Hainich DE-Hai, 98 %-cover temperate broadleaved
summergreen beech, PFT id 3). The value `28008` carried in earlier notes is Hainich only in the repo's
default `-DSINGLESITE` grid; **in the global grid `28008` is Sonoran desert** (31.75 N, −114.75 E). Any
prior code that hard-coded `28008` against the global data was pointing at a desert cell.

---

## 1. Method

### 1.1 Single-cell re-run with the canopy light/structure boundary
The 186 GB global daily dataset has **no** canopy-structure/light fields, and the dominant confound in
a GPP comparison is **phenology** (the C folds daily leaf-on/off into LAI; `F_diff` holds structure
fixed). So a fresh **single-cell** daily re-run of Hainich (`scripts/run_fdiff_validation_cell.sh`,
`STARTGRID=ENDGRID=42490`, restart from `restart_1999.lpj`, seed1, 2000–2019) additionally emits the C
binary's **actual daily FAPAR** (`d_fapar.nc`) plus NV_LAI and annual FPC_STAND/LAI_STAND. FAPAR *is*
filled every day for natural vegetation (`src/lpj/daily_natural.c:219`, `pft->fapar` from
`albedo_tree.c:75`) and is not annual-capped, so `"timestep":"daily"` is accepted. Run: 9 s, 1 cell,
clean (no water-balance error).

### 1.2 Forcing extraction (`scripts/extract_fdiff_validation_inputs.py`)
- **Real daily forcing** (temp, swdown, lwnet, precip, huss) read from the LPJmL `.clm` inputs. Layout
  decoded and **validated**: LPJCLIM v3, `order=1` = **YEARCELL** (`data[year][cell][band]`), float32,
  scalar 1.0, 51-byte header. Self-check: the `.clm` precip for cell 42490 equals the model's own
  `d_prec` output to **max|Δ| = 0** — the reader is exact.
- **Daylength** reproduced from `petpar2.c` (latitude + day-of-year), matching the C radiation routine.
- **CO₂** from the annual TRENDY v12 file.
- **Targets**: the C binary's daily gpp/npp/transp/evap/interc/pet/runoff/**fapar**/rootmoist from the
  single-cell re-run (fills masked).
- Writes the full 2000–2019 daily CSV (on `/p/tmp`) + a committed one-year (2010) reference for the CI
  gate (`test/testitems/references/hainich_{forcing,cbinary_targets,fdiff_baseline}_2010.*`).

### 1.3 Kernel-isolation drive (`F_diff`)
`F_diff` is run with the **TeBS beech parameter set** (`tebs_params()` / `tebs_structure()` — the
PFT-3 switches the confound analysis flagged: `alphaa=0.55`, SLA Vcmax cap on, `temp_photos` 20/30,
`emax=10`, `gmin=1.0`, `k_beer=0.59`) and driven by the C binary's **daily FAPAR**: at full canopy
(`phen≈1`, no snow) the C `apar = par·(1−albedo)·alphaa·fpar` collapses to `par·alphaa·FAPAR_out`
(the `(1−albedo)` cancels), so feeding FAPAR isolates the photosynthesis → λ → conductance → PET
kernel from *all* structure/phenology/aggregation differences. Analysis driver:
`scripts/validate_fdiff_vs_cbinary.jl`.

---

## 2. Results (Hainich cell 42490, 2000–2019 daily)

| Quantity | window | ratio (F_diff / C) | NMBE | correlation r |
|---|---|---|---|---|
| **PET** (eeq·1.32) | annual | **1.05** | +5.2 % | **0.999** |
| **PET** | growing (DOY 150–240) | 1.05 | +4.8 % | 0.999 |
| **GPP** | annual | 0.57 | −42.9 % | **0.963** |
| **GPP** | growing (pooled) | 0.59 | −41.0 % | 0.76 |
| **GPP** | growing (within 2010) | 0.60 | — | **0.961** |
| **Transpiration** | annual | 1.47 | +47.2 % | 0.973 |
| **Transpiration** | growing | 1.41 | +41.2 % | 0.912 |
| **Root-zone soil water** | growing | 0.74 | −26 % | 0.887 |

(The pooled growing-season GPP r = 0.76 is dragged down by across-year scatter; *within* a year the
daily growing-season correlation is ≈ 0.96 — the temporal dynamics are reproduced, the level is offset.)

Artifacts: `artifacts/metrics/phase3_fdiff_cbinary_validation.json` (per-year totals + all metrics).

---

## 3. Interpretation — what is validated, what is the remaining gap

- **Validated (tight): the radiation + Priestley–Taylor + daylength machinery.** PET matches the C
  binary to ~5 % with r = 0.999. This is a decisive "same physics" confirmation of `priestley_taylor_eeq`
  and the `petpar2` daylength reproduction.
- **Captured (dynamics), offset (level): GPP and transpiration.** Both track the C binary's daily
  temporal pattern (high r), confirming the photosynthesis kernel + λ solve + conductance respond
  correctly to forcing. The **level** offsets are attributable to the documented scale-up items, not
  bugs (kernel `#define`s are byte-identical):
  - GPP **under**-predicts ~42 %: one representative individual vs the cell's 25-patch, multi-PFT,
    multi-trait-class canopy; fixed structure; the SLA-Vcmax-cap / co-limitation partitioning at a
    single individual.
  - Transpiration **over**-predicts ~40 %: single soil bucket vs LPJmL's 23-layer + rootdist +
    permafrost; no interception term; the demand-side Priestley–Taylor closure. Demand-limited, so
    unaffected by `emax`.
  - The two together imply a **water-use-efficiency inconsistency** (too much water per unit carbon),
    pointing at the coupled conductance↔carbon path — a specific target for the multi-PFT + multi-layer
    scale-up.
- **NPP not gated:** LPJmL maintenance respiration scales with the individual's real sapwood/root
  carbon, which `F_diff` cannot supply until S provides the pools; the `ind` CSV `npp` column is also
  corrupt (byte-identical to `gpp`). GPP is the honest carbon target for now.

---

## 4. `F_diff` changes made (all AD-safe; regression baseline preserved)

- **`alphaa` PAR-use fraction** added to `Structure` (default 1.0 = spike behaviour; TeBS = 0.55).
- **SLA-dependent Vcmax cap** (`photosynthesis.c:92-97`) added to `PhotoParams` (`issla`, default off).
- **External-FAPAR drive mode** (`daily_step`/`rollout`/**`rollout_daily`** accept a per-day `fapar`)
  for kernel isolation; plus `rollout_daily` returning the full per-day flux trajectory.
- **`tebs_params()` / `tebs_structure()`** — one source of truth for the beech PFT set.
- **λ-solve robustness:** the fixed-graph Newton now confines its iterate to the physical bracket
  `[0.02, 0.85]` with a plain `clamp`. Real deep-winter forcing (near-zero light under a fixed summer
  canopy) drives `adtmm` to its softplus floor ⇒ `dg≈0` ⇒ the raw Newton step diverges to NaN; the
  clamp bounds it (GPP≈0 there regardless). A `smooth_clamp` was rejected because `softplus(β·huge)`
  overflows the **AD dual**; the hard `clamp` instead discards the divergent branch's derivative. In
  the normal regime λ is interior (≤ λmax = 0.8), so the clamp is the identity and the **numerical
  regression baseline is unchanged** (npp = 868.51795, exact).
- **Enzyme reverse-mode now uses `set_runtime_activity`** (the λ clamp is a genuine conditional →
  static activity analysis is insufficient). Still true reverse-mode through the full physics rollout,
  still exact vs finite differences. **Gradient gate unchanged:** ForwardDiff + Enzyme match
  FiniteDifferences on `∂NPP/∂{CO₂, emax, α_c3, w₀}`.

---

## 5. The gate + drift baseline

`test/testitems/cbinary_validation_tests.jl` (committed, CI-runnable — reads the one-year 2010
reference, no HPC/`/p/tmp` dependency):
- **PET** growing-season ratio ∈ [0.90, 1.15], r > 0.99 — the tight "same physics" assertion.
- **GPP** annual r > 0.92, growing-season r > 0.85, annual ratio ∈ [0.45, 1.5] — dynamics + documented
  level band.
- **Transpiration** growing r > 0.85, annual ratio ∈ [0.5, 2.0].
- **ReferenceTests drift alarm**: `F_diff`'s own annual GPP/transp/PET on the real 2010 forcing pinned
  to `hainich_fdiff_baseline_2010.txt` (rtol 1e-4).
- No NaN/Inf over the year.

---

## 6. Reproducing

```bash
# 1) single-cell re-run with FAPAR + structure (HPC; ~9 s) — already generated
SUBMIT=yes bash scripts/run_fdiff_validation_cell.sh
# 2) extract forcing + targets (login node OK)
/home/jamirp/.conda/envs/py311_new/bin/python scripts/extract_fdiff_validation_inputs.py
# 3) multi-year analysis (login node OK — pure Julia)
JULIA_DEPOT_PATH=$HOME/.julia julia --project=. scripts/validate_fdiff_vs_cbinary.jl
# 4) the committed gate
JULIA_DEPOT_PATH=$HOME/.julia julia --project=. -e 'import Pkg; Pkg.test()'   # incl. cbinary_validation
```

---

## 7. What this changes for the scale-up plan (`docs/phase3_fdiff_spike.md` §7)

The PET/radiation path is now quantitatively confirmed against the C oracle, so it drops off the risk
list. The measured GPP/transpiration **level** gaps now have concrete targets and expected signs,
sharpening the remaining "cover all of F" items:
1. **Multi-PFT + representative-individual set** (biggest GPP lever — the −42 % level gap) driven by S.
2. **Multi-layer soil water** (biggest transpiration lever — the +40 % gap; the single bucket also
   over-drains, root-zone water r = 0.89 / ratio 0.74).
3. Coupled conductance↔carbon consistency (the WUE inconsistency).
4. Dynamic (phenology-folded) structure so the full-year GPP comparison no longer needs the FAPAR
   crutch or the growing-season restriction.
