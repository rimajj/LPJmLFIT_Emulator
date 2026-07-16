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

---

## 8. Update — multi-layer soil water (scale-up step 2)

The single soil bucket was replaced with a **differentiable 23-layer soil column** (`FDiff.SoilColumn`,
`FDiffStateML`, `daily_step_ml`/`rollout_daily_ml`): fill-to-field-capacity infiltration cascade,
Jackson-1996 β root distribution (from D95 ≈ 115 cm → ~93 % of roots in the top 1 m), per-layer
root-weighted transpiration withdrawal, and top-300 mm quadratic soil evaporation. Per-layer capacities
come from the C run's own `whc_nat` output (× layer depth), so no pedotransfer port is needed; the code
stays dependency-free and water closes exactly. Validated on Hainich with the same FAPAR-driven harness.

| metric (Hainich 2000–2019, growing season) | single bucket | **multi-layer** | C binary |
|---|---|---|---|
| water closure | exact | **exact (~1e-10)** | — |
| **GPP daily correlation** | 0.76 | **0.93** | — |
| **transpiration daily correlation** | 0.91 | **0.96** | — |
| root-zone water (top-1 m) | 1 bucket | **23 layers, r = 0.87** | `d_rootmoist` |
| GPP level (GS ratio) | 0.59 | 0.61 | 1.0 |
| transpiration level (GS ratio) | 1.41 | 1.45 | 1.0 |

**Outcome:** the multi-layer column substantially improves the daily **dynamics** (GPP correlation
0.76 → 0.93; transpiration 0.91 → 0.96) and makes soil water physically representable per layer, at
**essentially unchanged levels**. This is the decisive finding: the transpiration/GPP **level** gaps are
**NOT soil-supply-limited** — with realistic per-layer drying the root-zone water tracks the C binary
(r = 0.87) yet transpiration stays ~45 % high and demand-limited. The levels are therefore **demand-side
/ single-representative-individual** effects (one well-watered tree transpires at full atmospheric demand
and concentrates all light through the SLA-Vcmax cap), which **definitively localizes the next step to
the multi-PFT / representative-individual work** (item 1 above). One documented v1 simplification: a bug
where saturation-excess at field capacity bounced rain into spurious surface runoff (→ over-drained the
root zone) was fixed by letting infiltration always refill toward field capacity and route the excess as
drainage; surface/infiltration-excess runoff, the free-water percolation timescale, and permafrost ice
are v2 items. Differentiability: **ForwardDiff** flows through the layered rollout (matches finite
differences); **Enzyme reverse-mode** through the layered Vector-mutation is a follow-up (the single-
bucket already establishes Enzyme-reverse through the full physics). Gate:
`test/testitems/multilayer_soil_tests.jl` + committed `hainich_soilcolumn.txt` /
`hainich_ml_baseline_2010.txt`.

## 9. Update — multi-individual / multi-PFT canopy (scale-up step 3): the GPP level gap closes

The single representative tree was replaced with the Hainich cell's **real set of individuals** — 25
patches × 297 reconstructed trees + grass — each patch a canopy that shares one 23-layer soil column
and distributes light by LPJmL-FIT's **vertical layered Beer–Lambert competition**. New code:
`FDiff.Individual`, `daily_step_canopy`, `rollout_daily_canopy` (`src/fdiff.jl`); the individual set is
reconstructed from the `ind` output by `scripts/extract_fdiff_individuals.py` and committed as
`test/testitems/references/hainich_individuals_2010.csv`.

**Same-physics port (verified against the C source, adversarially).** Each individual's photosynthesis
sees `apar_i = par·(1−albedo_i)·alphaa_i·fpar_i·phen` (`water_stressed.c:204`), where `fpar_i` is the
individual's LAYERED absorbed-PAR fraction from the FIT canopy light model (`getfpar.c`: 2 m layers,
tallest-first, `k_lambert=0.5`; the tall dominants absorb first, the suppressed ones get the transmitted
light). Transpiration demand is stand-level — `gp_sum.c` returns the fpc-normalized MEAN potential
conductance `gp_stand = Σ_i gp_i·phen / Σ_i fpc_i` (each `gp_i` from FPC-based light) — and each
individual transpires `min(supply_i, demand_stand)·fpc_i`, summed and withdrawn from the shared soil
(per-layer capped at available water). GPP is `Σ_i` gross assimilation per m² (`daily_natural.c:200`).

**Reconstruction, self-validated.** From the `ind` CSV (`Height, LAI, SLA, Wooddens, fpc_ind`) each
individual's crown area (Jucker), leaf & sapwood carbon (pipe model), and layered leaf-area profile are
reconstructed. The reconstructed density comes out to `nind = 1/225` for **every** tree — i.e. exactly
one individual per the FIT 225 m² patch — which independently confirms the Jucker crown-area
reconstruction reproduces the C's stored crown area (via `fpc = crownarea·nind·(1−e^{−k·LAI})`). The
layered light is provably independent of the (uncertain) crown-area reconstruction: the per-layer leaf
area `atoh·nind` reduces to CSV-only quantities (`LAI, fpc_ind, H, SLA`).

**A load-bearing correction to the earlier drive.** The cell `d_fapar` OUTPUT is an **albedo-based**
quantity (`albedo_tree.c:75`, ≈0.49 leaf-on) — NOT the **layered** `fpar` that actually feeds
photosynthesis (Σ ≈ 0.83 leaf-on). The single-individual validations (§2, §8) drove the canopy with the
albedo `d_fapar` and so under-fed it by ~1.7×; the multi-individual core drives each individual with its
reconstructed layered `fpar` (using the C's daily `d_fapar` only for its phenology *shape*).

**A latent Vcmax-cap bug, fixed.** The SLA-Vcmax cap `smoothmin(vm, vm_n, βvm)` used `βvm = 0.05`, whose
`log(2)/β ≈ 14 gC/m²/day` softmin floor biased **every** individual's Vcmax downward — negligible for the
single lumped tree (its Vcmax sits far above the cap) but catastrophic once light is distributed: the
light-starved understory individuals were driven to **negative** assimilation. Corrected to `βvm = 1.0`
(near-cap deviation `≤ 0.69`, uncapped individuals unbiased). This alone lifts even the single-individual
GPP 626 → 721 (−42% → −35%) and raises transpiration in step (correct carbon ⇒ conductance ⇒ demand);
the committed single-individual drift baselines (`hainich_fdiff_baseline_2010.txt`,
`hainich_ml_baseline_2010.txt`) were regenerated accordingly.

| metric (Hainich 2010, cell mean over 25 patches) | single individual | **multi-individual** | C binary |
|---|---|---|---|
| **GPP annual ratio** (model/C) | 0.57 → 0.65* | **1.06** | 1.0 |
| GPP full-year daily r | 0.96 | **0.95** | — |
| **transpiration annual ratio** | 1.47 → 1.60* | **1.32** | 1.0 |
| transpiration full-year daily r | 0.97 | **0.96** | — |
| root-zone water (GS) daily r | 0.87 | **0.97** | — |

*single-individual values after the `βvm` fix.

**Outcome — the GPP level gap is CLOSED** (annual ratio 0.57 → **1.06**), the primary lever the multi-PFT
step targeted (§7 item 1). Three effects combine: the correct (layered, ~1.7× larger) canopy light, the
de-saturation of the SLA-Vcmax cap once light is spread across individuals, and the `βvm` fix.
**Transpiration improves** (single-individual multilayer 1.60 → **1.32**) and is now cleanly
demand-limited: the residual +32 % is demand-side — no interception/wet-canopy `(1−wet)` term, `eeq` ~7 %
high from the fixed forest albedo, and the stand conductance→demand coupling — i.e. exactly the
documented **coupled conductance↔carbon (§7 item 3)** + **full `petpar` radiation (§7 item 4)** items,
not the multi-PFT structure. Differentiability: **ForwardDiff** flows through the per-individual loop
(matches finite differences). Documented v1 simplifications: fixed (year-end) canopy structure with a
daily phenology factor, sub-5 m saplings absent from the `ind` output, the shared cell root profile for
all individuals, and interception omitted. Gate: `test/testitems/multi_individual_tests.jl` + committed
`hainich_individuals_2010.csv` / `hainich_canopy_baseline_2010.txt`.
