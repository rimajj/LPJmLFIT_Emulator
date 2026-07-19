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

**Status (as of step 5):** items 1–4 are DONE (§8 multi-layer soil, §9 multi-PFT canopy — GPP level
closed, §10 coupled conductance — transpiration level closed), and the two C-output crutches (FAPAR
phenology + PET/albedo `eeq`) are now REMOVED (§11 — F_diff self-computes the GSI phenology and the
dynamic-albedo `eeq`, matching the dropped C outputs at r 0.99 / 0.999). Remaining: prognostic
(within-year dynamic) canopy structure, then the `SharedState` adapter → S↔F coupling.

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

## 10. Update — coupled conductance ↔ carbon consistency (scale-up step 4): the transpiration level closes

Step 3 closed the GPP level and localized the remaining transpiration residual (+32 %) to the **demand
side**. This step closes that residual — the multi-individual canopy transpiration annual ratio goes
**1.32 → 1.02** vs the C binary — by porting the three demand-side pieces and, in the process, finding a
load-bearing conductance bug.

**(a) Wet-canopy interception (`interception.c`).** Each individual now carries its leaf-on crown LAI
(`lai = leaf_c·sla/crownarea`) and PFT interception coefficient (`intc`; trees 0.02 / boreal 0.06 /
grass 0.01). The relative canopy wetness `wet = min(intc·lai·phen·rain/(eeq·1.32), 0.9999)` (a) reduces
each individual's transpirative demand by `(1 − wet)` (`water_stressed.c:118`) and (b) evaporates
`eeq·1.32·wet·fpc` off the wet canopy, which is removed from infiltration (`daily_natural.c:151`) so
water still closes exactly. The interception flux tracks the C binary at **r = 0.99** (17.4 vs 23.1
mm/yr; the ~25 % magnitude shortfall is a v1 point — the C sums over its full pft list including
sub-5 m saplings absent from the reconstruction).

**(b) The `eeq` albedo (kernel isolation).** F_diff's fixed forest albedo (0.15) makes its
Priestley–Taylor `eeq` **6.8 %** high (annual PET 807 vs the C's 755.6). Exactly as the FAPAR path is
driven by the C's daily output, `eeq` is now optionally driven by the C binary's own daily PET
(`eeq = pet_C/1.32`), which embeds the daily `albedo_patch` (`update_daily.c:157`). Porting the full
`albedo_patch` (tree/grass/soil/snow albedos) so standalone F_diff needs no PET crutch is a documented
follow-up, parallel to the dynamic-phenology-structure item.

**(c) The load-bearing bug: a coarse net-assimilation floor inflated stand conductance ~8×.** The
`adtmm` conductance driver (`photosynthesis.c:166`, the C's `(adt≤0)?0`) was smoothed with a hardcoded
`softplus(adt, 0.5)`, whose floor `log(2)/0.5 = 1.386 gC` injected spurious net assimilation into every
**light-starved** individual. Because `gp_i ∝ adtmm` while an understory individual's `fpc` is tiny,
its `gp_i/fpc` exploded (≈190 for a suppressed sapling), and the fpc-normalized stand conductance
`gp_stand = Σgp_i/Σfpc_i` was lifted to **24.5 mm/s** — vs the ~2.9 the C's transpiration implies —
which through the saturating demand function `eeq·ALPHAM/(1 + GM·ALPHAM/gp_stand)` inflated demand ~2×.
This affected **only** `adtmm` (the 4th `photosynthesis` return + the conductance/λ-solve path), **not**
`agd` (GPP) — which is exactly why GPP matched while transpiration ran high, and why the earlier
sessions' correlations were capped at ≈0.95. Sharpening the floor (`PhotoParams.βadt`, 0.5 → 20; floor
≤ 0.035 gC) drops `gp_stand` to a physically sensible ~10.7 and leaves the well-lit dominant
individuals (and the GPP baseline) unchanged.

| metric (Hainich 2010, cell mean over 25 patches) | step 3 | + interception | + interception + C-eeq | C binary |
|---|---|---|---|---|
| **transpiration annual ratio** (model/C) | 1.32 | 1.05 | **1.02** | 1.0 |
| transpiration full-year daily r | 0.955 | — | **0.988** | — |
| GPP annual ratio | 1.06 | — | **1.09** | 1.0 |
| GPP full-year daily r | 0.953 | — | **0.998** | — |
| root-zone water (GS) daily r | 0.97 | — | **0.98** | — |
| root-zone water (GS) ratio | 0.73 | — | **0.84** | 1.0 |
| interception flux (mm/yr) | — (0) | 17.4 | **17.4** | 23.1 (r 0.99) |

**Outcome — the transpiration level gap is CLOSED** (annual ratio 1.32 → **1.02**), and the fix lifts
every daily correlation (GPP 0.953 → **0.998**, transpiration 0.955 → **0.988**, root-zone water ratio
0.73 → **0.84**) because the inflated conductance had been distorting demand for the whole canopy, not
just the understory. The single-representative-individual paths inherit the same `βadt` fix (their
committed drift baselines were regenerated: single-bucket transpiration 383 → 350, multi-layer 382 →
350 — the floor had been over-transpiring their shoulder seasons too). Differentiability is preserved:
**ForwardDiff** flows through the interception + per-individual loop (matches finite differences).
Remaining demand-side residual is now small and in the GS (+8 %), attributable to the residual
`gp_stand` over-estimate (10.7 vs ~2.9 implied) and the interception magnitude shortfall — plus the
still-fixed (phenology-folded) canopy structure. Next: the full `albedo_patch`/`petpar` port (remove
the PET crutch) and **dynamic phenology-folded structure**, then the `SharedState`/`AbstractFastCore`
adapter → S↔F coupling. Gate: `test/testitems/multi_individual_tests.jl` (transpiration ratio now
0.9–1.15, interception r > 0.9) + regenerated `hainich_canopy_baseline_2010.txt`.

## 11. Update — self-computed radiation + phenology (scale-up step 5): the C-output crutches are removed

Steps 1–4 leaned on two daily C-binary outputs to isolate the physics under test: the leaf phenology
was driven by the C's daily **FAPAR** (`phens = fapar_C/peak`) and the Priestley–Taylor `eeq` by the
C's daily **PET** (`eeqs = pet_C/1.32`, which embeds the dynamic `albedo_patch`). This step ports both
so the canopy runs **standalone** — from the atmospheric forcing and the S-supplied structure alone —
and the self-computed quantities reproduce the C outputs they replaced.

**(a) GSI leaf phenology (`phenology_gsi.c`).** LPJmL-FIT's "new phenology" is the Growing-Season-Index
model: four low-passed logistic limiting functions — cold-temperature `tmin`, heat `tmax`, `light`,
water `wscal` — whose product is the daily leaf-display factor `phen ∈ [0,1]`. Each is
`f ← f + (sigmoid(±sl·(x−base)) − f)·τ`; `phen = tmin·tmax·light·wscal`. The beech (TeBS, PFT id 3,
`par/pft.js:527-550`) parameters are `tmin`(sl 2, base 8 °C, τ 0.2), `tmax`(1.74, 41.51 °C, 0.2),
`light`(58, 40 W/m², 0.2), `wscal`(5.24, base = `minwscal`·100 = 20.96 %, 0.1). Drivers: daily-mean air
temperature, shortwave-down, and the previous day's stand water scalar; the C's `soil→temp[0] < 10 °C ⇒
water factor forced open` rule (`phenology_gsi.c:67`) is driven here by air temperature (LPJmL uses air
temp as the soil top boundary). The steep-slope `exp` overflow the C guards with its `<200` branch is
handled by a clamped sigmoid ([`stable_sigmoid`](@ref); the clamp only bites in a saturated tail with a
`< 1e-13` true derivative). The self-computed `phen` tracks the C's daily FAPAR at **r = 0.99**
(`FDiff.phenology_gsi_step`, `FDiff.PhenState`, `FDiff.tebs_phenparams`).

**(b) Dynamic surface albedo → self-computed `eeq` (`albedo_stand.c`).** The daily patch albedo `beta`
LPJmL feeds to `petpar2`'s `eeq` (`swnet = (1−beta)·swdown`) is
`Σᵢ fpcᵢ·(frsᵢ·c_albsnow + (1−frsᵢ)·albvegᵢ) + max(1−Σfpc, 0)·(sfr·c_albsnow + (1−sfr)·c_albsoil)`, where
the leaf-on/off vegetation albedo is `phen·albedo_leaf + (1−phen)·(c_fstem·albedo_stem +
(1−c_fstem)·albedo_litter)` for a tree (no stem term for grass), and the snow fraction `sfr` comes from
the snowpack (`snow.c`). Constants are the LPJmL `#define`s (`c_albsnow = 0.65`, `c_albsoil = 0.30`,
`c_fstem = 0.70`, `c_watertosnow = 6.70`) and the PFT albedos (`par/pft.js`; beech leaf 0.15 / stem
0.04 / litter 0.10 / snowcanopyfrac 0.40). For a leaf-on beech patch (`Σfpc ≈ 0.56`) this gives
`beta ≈ 0.22`, vs the fixed `0.15` the earlier canopy runs used — exactly the ~7 % PET overshoot the
C-`eeq` drive had been correcting. The canopy-snow-burial term `frs2` (snow deeper than the crown base;
`albedo_tree.c:44-52`) is neglected — a v1 simplification (needs per-individual height) that is
negligible at temperate Hainich, where the dominant snow effect (ground snow through the exposed
fraction) is exact. The self-computed `eeq` matches the C's daily PET at **r = 0.999**, annual ratio
**0.98** (740 vs 756 mm; the fixed-0.15 `eeq` was 807, ratio 1.07). ([`FDiff.patch_albedo`](@ref).)

**(c) Daylength from latitude (`petpar2.c`).** `petpar_daylength(lat, doy)` reproduces the C's
declination/hour-angle daylength (the polar-day/night three-way branch is the branch-free clamp of the
`acos` argument to `[−1,1]`), so F_diff no longer needs daylength as a forcing. It reproduces the
supplied Hainich daylength to `max|Δ| = 5e-5 h`. ([`FDiff.petpar_daylength`](@ref).)

| metric (Hainich 2010, cell mean over 25 patches) | step 4 (both crutches) | **standalone (self+self)** | C binary |
|---|---|---|---|
| **GPP annual ratio** (model/C) | 1.09 | **1.17** | 1.0 |
| GPP full-year daily r | 0.998 | **0.993** | — |
| **transpiration annual ratio** | 1.02 | **1.08** | 1.0 |
| transpiration full-year daily r | 0.988 | **0.978** | — |
| interception flux (mm/yr) | 17.4 | **20.4** | 23.1 |
| root-zone water (GS) daily r | 0.98 | **0.984** | — |
| self `phen` ↔ C `d_fapar` (daily r) | — | **0.99** | — |
| self `eeq` ↔ C `d_pet` (daily r) | — | **0.999** | — |

**Outcome — both crutches are removed** with the daily dynamics essentially intact (GPP r 0.993,
transpiration r 0.978). The annual levels edge up (GPP 1.09 → 1.17, transpiration 1.02 → 1.08) because
the faithful GSI phenology integrates ~11 % more leaf-display than the FAPAR-normalized proxy the
earlier steps used (self-`phen` annual mean 0.479 vs proxy 0.432; the C's `d_fapar` output folds
`(1−albedo_leaf)` and the leaf-off stem term, so `fapar/peak` under-reads the true `phen`), which
surfaces slightly more of the reconstruction's pre-existing GPP over-estimate. Both remain in the gate
bands, the interception flux improves toward the C (20.4 vs 23.1 mm, from the longer effective leaf-on
season), and the self-computed `eeq` matches the C's PET essentially exactly (r 0.999). Differentiability
is preserved: **ForwardDiff** flows through the GSI phenology + dynamic-albedo + water-scalar-feedback
path (`d(annual canopy GPP)/d(α_c3)` matches finite differences to ~1e-11). Documented v1
simplifications: one beech-GSI `phen` applied patch-wide (as the FAPAR-proxy crutch was — the stand is
87 % beech; per-PFT phenology for the evergreen/grass minority is a follow-up), the canopy-snow-burial
`frs2` term neglected, and the soil-temp water gate driven by air temperature. Next: **dynamic
(prognostic) canopy structure** so the year-end reconstructed individuals are no longer fixed within the
year, then the `SharedState`/`AbstractFastCore` adapter → S↔F coupling. Gate:
`test/testitems/multi_individual_tests.jl` (standalone config: GPP ratio 0.9–1.30, transpiration
0.9–1.2, + crutch-removal asserts phen↔FAPAR r > 0.95 / eeq↔PET r > 0.98 / daylength Δ < 0.01 h) +
regenerated `hainich_canopy_baseline_2010.txt`.

## 12. Update — dynamic (prognostic) canopy structure + the S↔F coupling adapter (scale-up step 6)

Steps 3–5 fixed each individual's structure at its year-END value for the whole year (a daily phenology
factor scaled leaf display, but crown/leaf/sapwood were static). Step 6 makes the per-individual carbon
pools **prognostic**: they accumulate the daily `bm_inc` (= Σ daily NPP) and, at the annual boundary,
**GROW** via a faithful **differentiable** port of the LPJmL-FIT year-end sequence `turnover_tree.c` →
`allocation_tree.c` → `allometry_tree.c` (`annual_tree.c:29-30`). This is the flux-then-integrate carbon
handoff of DESIGN §8, and it is also the mechanism the `SharedState`/`AbstractFastCore` adapter needs to
close the S↔F coupling surface.

**The port (verified line-by-line against `/home/jamirp/lpjml56fit` v5.6.004; `with_nitrogen=no`, FIT
individual mode, PFT 3 beech).** The annual allocation partitions the accumulated `bm_inc_ind =
bm_inc/nind` into leaf/sapwood/heartwood/root subject to (A) the pipe-model leaf-area:sapwood-area
constraint (`k_latosa`), (B) the leaf:root ratio `lmtorm = 0.5 + 0.5·min(1, wscal)`, and (C,D) the
Jucker-2022 crown/height allometry, by solving the residual `f(leaf_inc) = k1·(b − x·lm + heart) −
((b − x·lm)/(leaf + x)·k3)^(1+2/allom3) = 0` (`allocation_tree.c:120-125`; `b = sapwood + bm_inc −
leaf/lmtorm + root`, `k1 = allom2^(2/allom3)·4/π/wooddens`, `k3 = k_latosa/wooddens/sla`). The C's
`leftmostzero` bracket-scan + bisection is replaced by a **fixed-graph damped-Newton** with a segment
seed and a plain `clamp` to the physical bracket — the same AD-safe pattern the λ solve uses
(`FDiff._solve_leaf_inc`): the total derivative equals the implicit-function result at convergence, so
ForwardDiff flows through cleanly. Turnover (reproduction reserve `bm_inc·0.1`, sapwood→heartwood at the
0.04/yr rate, summergreen leaf recycle `leaf/1.05`, fine-root turnover) precedes allocation; the height
cap does the sapwood→heartwood transfer; height/crownarea/LAI/FPC are re-derived. New API:
`FDiff.AllocParams` / `FDiff.TreePools` / `FDiff.grow_individual` / `FDiff.individual_from_pools` /
`FDiff._patch_fpars` (getfpar layered-light recompute as heights change) / `FDiff.rollout_canopy_years`
(the multi-year coupled loop) / `FDiff.tebs_allocparams`.

**Validation (decisive, all on the committed 2010 reference).** For every reconstructed beech, growing it
by its per-individual `bm_inc` reproduces the C's allometric constraint to **machine precision**:

| check | result |
|---|---|
| pipe-model invariant `leaf ≈ k_latosa·sapwood/(wooddens·H·sla)` after allocation | **max rel. error 2.9e-16** (272 trees) |
| carbon conservation `Δ(pools) = bm_net − turnover-to-litter` | **exact** (max abs 0, to fp) |
| growth direction (`bm_inc>0 ⇒ agb↑`) | **258/272** (the rest are in the abnormal/deficit regime) |
| AD `d(height)/d(bm_inc)`, `d(sapwood)/d(bm_inc)` vs finite differences | **match** (rtol 1e-4) |
| coupled gradient `d(grown height)/d(α_c3)` (daily flux → bm_inc → allocation) | **matches** finite differences |
| multi-year coupled rollout (2009 start + 2010 forcing + C `bm_inc`) | **year-1 mean tree height 9.34 m = the C's 2010 value** (from 2009's 9.21); AGB 4625 → 4864 (C 2010: 4784); an 8-year trajectory grows smoothly (AGB 4864→6314, H 9.34→10.02) with all pools finite and heights bounded — no blow-up |

**The `SharedState` adapter (`FDiffFastCore <: AbstractFastCore`).** `AbstractFastCore.step!` previously
threw; it is now wired: the daily `step!(fc, state::SharedState, bc::SToF, forcing::AtmForcing) -> FToE`
maps the shared per-layer soil water (`SharedState.w`, fraction of WHC) to the `SoilColumn`
plant-available mm, self-computes daylength (from latitude) / GSI phenology / dynamic-albedo `eeq`, runs
one `daily_step_canopy`, **writes the updated soil water back into `state.w` in place**, accumulates the
conserved per-individual `bm_inc`, and returns the daily `FToE` (`LE = λ·ET` derived; `gpp`/`npp` from
the canopy). The year-end `annual_step!(fc, state) -> FToS` grows the prognostic structure
(`grow_individual`) from the accumulated `bm_inc` and returns the conserved `FToS` increment for S — the
deterministic carbon allocation F owns, leaving demography (distribution/count/mortality) to S.

**A load-bearing correction surfaced by this work — the per-m² maintenance respiration.** The
multi-individual `daily_step_canopy` had fed **per-individual** carbon pools into the maintenance-
respiration term while `gpp`/`rd` are **per-m²** (patch basis) — harmless for the existing gates (NPP is
not gated; GPP/transpiration do not depend on it) but wrong for `bm_inc`. The C forms maintenance as
`nind·(sapwood·… + root·…)` (`npp_tree.c:51`), i.e. per-m². Adding `nind` to `FDiff.Individual` and the
`×nind` factor makes NPP per-m² consistent (the committed water/light baselines are unchanged — they do
not involve NPP).

**Known residual (documented; the immediate follow-up).** F_diff's SELF-computed canopy NPP still
over-respires (the `×nind` fix moved the cell NPP from wildly negative to ≈ −25 gC/m²/yr, vs the C's
≈ +512): the maintenance constants match the C exactly (`param.k=0.0548`, `nc_ratio=1/cn`, `CTON_SAP=330`,
`CTON_ROOT=30`), so the excess is a leaf-respiration aggregation issue over the multi-individual canopy
that was never gated (the C-binary validation explicitly did not gate NPP). Until it is calibrated, the
coupled multi-year rollout and the adapter use a `bm_inc` **crutch** — the C's own per-individual annual
NPP — exactly the kernel-isolation methodology steps 5–7 used for the FAPAR/PET C-outputs (and later
removed). This isolates the allocation/structure growth (validated above to machine precision) from the
flux calibration. A carbon-deficit individual (`bm_inc ≤ 0`) **stagnates** (structure held; whole-tree
mortality is S's demography) rather than stripping its leaves and blowing up the pipe-model height — a
robustness guard.

**v1 simplifications (carried forward):** below-ground root-sapwood (`sapwood_bg`) and the carbon-debt
loan are neglected (second-order under `with_nitrogen=no`); grasses hold structure fixed (the grass
allocation is a separate model); GSI phenology cold-starts each year; the full-year multi-year gradient
through the layered-light feedback is a follow-up (the within-year gradient and the `d(structure)/d(bm)`
gradient are proven). Gates: `test/testitems/dynamic_structure_tests.jl` (allocation invariant,
conservation, growth, AD) + `test/testitems/coupling_tests.jl` (the `FDiffFastCore` adapter + the coupled
loop). Reconstruction of the before/after individual sets: `scripts/extract_fdiff_individuals_multiyear.py`
(+ committed cell-aggregate targets `references/hainich_structure_growth.txt`); driver
`scripts/validate_fdiff_structure.jl`.

**Next:** calibrate the self-computed canopy NPP (remove the `bm_inc` crutch) so the coupled loop runs
fully self-driven; per-PFT phenology for the evergreen/grass minority; then gradient-based online rollout
training (finish NeuralCrop's TBPTT scaffold; add Lux NN λ/Vcmax hooks — the AD-through-the-rollout
prerequisite is proven).

## 13. Update — self-computed canopy NPP CALIBRATED; the `bm_inc` crutch removed (scale-up step 7a)

Step 6 left the self-computed canopy NPP over-respiring (≈ −25 gC/m²/yr vs the C's ≈ +507), so the
coupled loop leaned on the `bm_inc` crutch. Decomposing the standalone canopy respiration `Ra = R_leaf +
R_maint + R_growth` against the C target isolated the cause to **two faithful-to-`npp_tree.c` fixes**, not
a constants error (the maintenance constants match the C exactly):

1. **Growth-respiration floor was far too soft.** The C is a hard branch — `npp = (assim < mresp) ?
   assim−mresp : (assim−mresp)·(1−r_growth)` (`npp_tree.c:52`), i.e. `R_growth = r_growth·max(0, assim −
   mresp)` with `assim = gpp − rd` — **zero whenever a tissue is carbon-negative**. F_diff smoothed that
   `max(0,·)` with `softplus(·, β=1)`, whose `log(2)/β ≈ 0.69 gC` offset (and slow sub-zero decay)
   injected a spurious growth respiration into **every carbon-negative individual on every day**;
   aggregated over ~12 individuals × 365 days this alone was ≈ **+730 gC/m²/yr** of phantom Ra (on
   deep-winter days with GPP ≈ 0 the model booked R_growth ≈ 2 gC/m²/day). Fix: a dedicated sharpness
   `RespParams.βgrowth = 50` (matching the other flux floors' `βflux`), reducing the offset to
   `log(2)/50 ≈ 0.014 gC`.
2. **Fine-root maintenance was not phen-gated.** The C multiplies the root (+`sapwood_bg`) maintenance
   block by `pft->phen` (`npp_tree.c:51`) — a deciduous canopy stops respiring roots when the leaves are
   off — while the above-ground sapwood term runs year-round (no phen). F_diff respired the root pool
   year-round. Fix: `R_maint = respcoeff·k·gtemp·(C_sap/CN_sap + phen·C_root/CN_root)` (the sapwood term
   still un-gated). (`gtemp_soil` for the root term is proxied by `gtemp_air` — F_diff has no soil-thermal
   model yet; a small, documented residual.)

Both are in `FDiff.autotrophic_respiration`; the three call sites (`daily_step`, `daily_step_ml`,
`daily_step_canopy`) pass the current day's `phen`.

**Result — standalone canopy (self-GSI-phen + self-albedo-`eeq`, 25 patches, 2010):**

| quantity | before | after | C binary |
|---|---:|---:|---:|
| annual NPP (gC/m²/yr) | **−25** | **+663** | 507 |
| winter (leaf-off, 117 d) NPP | −250 | **−6.7** | −13 |
| daily NPP correlation vs C | — | **0.987** | — |
| carbon-use efficiency NPP/GPP | (neg.) | **0.52** | 0.46 |

The respiration is now **physically calibrated**: in the kernel-isolation config (C's FAPAR + PET drives,
so GPP ≈ C), F_diff's **total Ra = 592.8 vs the C's 595.6 — a 0.5 % match**. The remaining standalone NPP
overshoot (663 vs 507, ×1.31) is therefore **inherited from the standalone GPP** (the documented +17 %
GSI-phenology level of §11), *not* a respiration miscalibration — CUE 0.52 sits just above the C's 0.46
(a physical temperate-forest value). Two second-order respiration residuals, both **pre-existing v1
simplifications**, partially cancel and account for the CUE sitting slightly high: `sapwood_bg`
below-ground maintenance is omitted (biases NPP high, growing-season) and `rd` is not conductance-gated on
rare water-stress-collapse days (the C zeroes it when `gpd ≤ 1e-5`, `water_stressed.c:196`; biases NPP low
on those days). Both stay on the item-7c list — fixing the `rd` gate *alone* would push CUE further from
the C, and `sapwood_bg` needs a below-ground pool.

**The crutch is removed.** `rollout_canopy_years` now defaults to fully self-driven (`bm_inc_ext=nothing`
uses `Σ npp_ind`); `FDiffFastCore` always self-accumulated `fl.npp_ind` (never the crutch), so the adapter
was self-driven the moment the flux went positive. The self-driven coupled loop (2009 start + 2010
forcing) delivers self-NPP ≈ 594 gC/m²/yr and **grows structure smoothly** — year-1 mean tree height 9.41 m
(C 2010: 9.344), an 8-year trajectory H 9.41 → 10.28 (≈ 0.11 m/yr vs the C's ≈ 0.13), AGB 4927 → 6736, all
finite, no blow-up — essentially tracking the crutch-driven trajectory.

**Baselines / gates.** Only the numerical-regression anchor `references/fdiff_annual_totals.txt` moves —
`npp` 871.81 → **893.28** (the sharpened growth-resp floor removes the phantom Ra on this synthetic
scenario too); `gpp/transp/evap/runoff/precip` are **byte-identical** (the fix is downstream of GPP and the
water balance). The water/light canopy baselines (`hainich_{fdiff,ml,canopy}_baseline`) are unchanged for
the same reason. New self-NPP gate in `multi_individual_tests.jl` (positive NPP, ratio ≤ 1.6, CUE ∈
[0.42,0.56], daily r > 0.95, winter deficit bounded); `dynamic_structure_tests.jl` and `coupling_tests.jl`
now run the coupled loop **self-driven** (asserting positive annual self-NPP + structure growth).
Diagnostic decomposition driver behaviour is reproduced by `scripts/validate_fdiff_canopy.jl` (extended to
report NPP). Full suite green; ForwardDiff/Enzyme through the new respiration path match finite differences
(the fixes add no new conditionals — a sharper `softplus` and a `phen` multiply).

**Next:** per-PFT phenology for the evergreen/grass minority; grass structure prognostic; the below-ground
`sapwood_bg` + carbon-debt in the allocation; then gradient-based online rollout training (finish
NeuralCrop's TBPTT scaffold; add Lux NN λ/Vcmax hooks — the AD-through-the-rollout prerequisite is proven).

## 14. Update — gradient-based online rollout training: NN λ/Vcmax hooks + finished TBPTT loop (scale-up step 7b)

The milestone the differentiable-first core exists to enable (ADR 0014): **train a learned closure
end-to-end through the differentiable rollout.** Two pieces landed (ADR 0016).

**(a) Dependency-free NN hooks in the physics (`FDiff.FluxHooks`).** The two photosynthesis levers a
hybrid trains — Vcmax (`vm`) and the ci:ca ratio `λ` — each gain an OPTIONAL learned multiplicative
correction `feat -> scale` (`scale ≈ 1`; `feat = [temp, swdown, daylength, apar, w_soil, co2]`). `vm`
scales Vcmax (propagating consistently into potential conductance and leaf respiration); `λ` scales the
solved ci:ca ratio, re-clamped to the physical bracket. The default is `nothing` — the identity fast
path — so **every regression baseline is byte-identical when the hook is off**; the runtime stays
dependency-free (the physics only ever *calls* the hook). The learned model (a Lux MLP) has a
**zero-initialized final layer**, so the *untrained* network is exactly the identity correction:
training departs from the calibrated physics rather than replacing it.

**(b) The finished TBPTT online-rollout training loop** (`train_fdiff_rollout!`, a working port of
NeuralCrop.jl's broken `train_loop_rollout!` scaffold), shipped as the `FDiffTrainingExt` **package
extension** (activated by `using Lux, Zygote, Optimisers`; runtime deps stay empty). It sweeps the daily
rollout in chunks, takes a **Zygote** gradient of the segment GPP loss w.r.t. the network parameters,
`Optimisers.update`s, and carries the detached soil-water state across chunk boundaries (the truncation
in TBPTT). Reverse-mode is the right tool: F_diff computes its working type from its declared inputs and
`convert(T,·)`s its state, so a ForwardDiff dual injected *only* via the NN params would hit that
convert; Zygote (and Enzyme) keep the forward values `Float64` and trace the adjoint.

**Verification (gate `test/testitems/nn_training_tests.jl`):**
- **Identity** — the `nothing` hook reproduces the committed baseline; the zero-init network reproduces
  the pure-physics rollout to ~1e-10.
- **Gradient correctness** — the Zygote gradient of the real-forcing (Hainich C-FAPAR) rollout GPP loss
  w.r.t. the network parameters matches **FiniteDifferences to rtol 1e-4** (the AD-vs-FD discipline of
  the physics gradient gate, now w.r.t. NN parameters).
- **Recovery of a known correction** — on a well-posed light-sufficient scenario the TBPTT loop drives
  the loss **0.67 → ~1e-3 (> 99 % down)**, the trained GPP matches the target to **< 0.5 %**, and the
  recovered Vcmax correction **≈ 1.31 vs the known 1.30** — an identifiability proof of the machinery,
  independent of the physics being right.

**Physical finding — which lever, which path.** Fitting the learned Vcmax correction to the LPJmL-FIT C
daily GPP on the **single-representative** path only PARTIALLY closes the level gap (annual ratio ≈ 0.64
→ ≈ 0.79) and actually *degrades* the growing-season daily shape (r 0.96 → 0.81 — the net trades shape
for level). The reason is physical, not a training failure: that gap is **light/structure-limited** — the
Haxeltine–Prentice co-limitation saturates at the light-limited rate `je`, so once a single individual's
absorbed PAR is fixed, scaling Vcmax (the Rubisco-limited rate `jc`) gives diminishing returns and cannot
recover the *shape*. This is exactly why the **multi-individual canopy** step (§9) closed GPP by spreading
light across individuals, not by changing Vcmax. So the learned Vcmax/λ correction belongs on the
**coupled canopy path**, where the residual is Vcmax/phenology-shaped — and that path mutates arrays, so
it trains with **Enzyme reverse** (the documented next step; the AD-through-mutation follow-up flagged
since step 2). This session lands and gate-verifies the *machinery* on the proven representative path;
wiring the hooks into `daily_step_canopy` + Enzyme-reverse training is item 7b-canopy.

**Reproduce:** `julia --project=test scripts/train_fdiff_nn.jl` (identity + recovery + the C-fit partial
closure with the light-limitation explanation). Gate + ADR 0016.

## 15. Update — NN training on the coupled CANOPY path: Enzyme reverse through the mutating rollout (scale-up step 7b-canopy)

§14 landed the online-rollout-training *machinery* on the single-representative path and found that path's
GPP gap is light-limited, so Vcmax is the wrong lever there. This step applies the learned correction
where the residual **is** Vcmax/phenology-shaped — the coupled multi-individual canopy — and, in doing so,
closes the AD-through-array-mutation follow-up flagged since step 2.

**(a) Per-individual NN hooks in `daily_step_canopy`.** Each individual gets a learned Vcmax/λ correction
from its own feature vector `[temp, swdown, daylength, apar_i, wr, co2]` (`apar_i` = its layered absorbed
PAR — the physically relevant lever; `wr` = the shared root-zone relative moisture), applied consistently
to both the potential-conductance Vcmax (pass 1) and the GPP/λ Vcmax (pass 2), exactly as `daily_step`
propagates `vm_scale`. The identity fast path (no hook) skips feature construction entirely, so **every
committed canopy baseline (`multi_individual`/`dynamic_structure`/`coupling`) is byte-identical** — the
gate confirms Δ = 0. Threaded through `rollout_daily_canopy` and `rollout_canopy_years`.

**(b) Enzyme-reverse training** (`fdiff_canopy_gpp_loss` / `train_fdiff_canopy_rollout!`, in the
extension). `daily_step_canopy` MUTATES the per-layer soil-water arrays (`_infiltrate` / `_transpire_total`
/ `_soil_evap`) and its per-individual buffers, which **Zygote cannot cross** — so this path trains with
**Enzyme reverse**: the network params are the sole `Duplicated` argument (a fresh `make_zero` shadow per
call — never reused, which would silently accumulate across chunks), everything else `Const`, the scalar
loss `Active`, and `set_runtime_activity` covers the λ-solve's data-dependent `clamp` (the same conditional
`gradient_correctness_tests.jl` documents). The returned gradient is a NamedTuple in the params' tree
shape, so it drops straight into `Optimisers.update`; the TBPTT chunk loop is otherwise identical to the
Zygote trainer.

**Verification (gate `test/testitems/nn_canopy_training_tests.jl`, self-contained: 4 individuals, a
5-layer soil column, a 40-day forcing):**
- **Identity** — the zero-init network reproduces the pure-physics canopy rollout exactly (**Δ = 0**).
- **Enzyme gradient correctness** — the Enzyme-reverse gradient of the canopy GPP loss w.r.t. the network
  parameters matches **FiniteDifferences to max rel err 1.2e-8** (through the array-mutating
  multi-individual path — the decisive proof the AD-through-mutation path is not just running but
  *correct*). The Enzyme primal equals the direct loss.
- **Recovery of a known correction** — the Enzyme TBPTT loop drives the loss **0.205 → 1.1e-3 (> 99 %
  down)**, the trained canopy GPP matches the target to **< 3 %**, and the recovered Vcmax correction is
  **≈ 1.18 vs the known 1.20** (the small low-bias is the understory individuals, whose `je`-limited
  photosynthesis weakens their Vcmax gradient — the top, light-sufficient individual recovers it tightest).

This is the AD-through-mutation milestone: F_diff is now end-to-end differentiable **and trainable** on
the coupled multi-individual canopy — the path the hybrid actually couples through — with Enzyme reverse
verified against finite differences to 1e-8. Applying it against the real C-binary daily GPP (rather than a
synthetic recovery target) on the full 25-patch Hainich canopy, and adding the λ lever + a multi-year
objective through the structure/allocation feedback, is the next step. Driver
`scripts/train_fdiff_nn.jl`; ADR 0016.

**Julia-version note (CI-surfaced).** The Enzyme-reverse canopy path is verified on **Julia 1.10** (the
`lts` CI job + `Project.toml` compat `julia = "1.10"` — the project's supported version) to 1e-8. On
**Julia ≥ 1.11**, Enzyme 0.13 raises an internal LLVM compiler error compiling the reverse pass through
this complex array-mutating path (the simpler single-bucket Enzyme gate,
`gradient_correctness_tests.jl`, compiles fine on 1.11 — it is specific to the multi-individual canopy).
Two responses: (i) the pre-existing per-individual `FDiffParams{T}(; …)` **keyword** constructor in
`daily_step_canopy` — which Enzyme on 1.11 could not even type-analyze (`EnzymeNoTypeError`) — was
switched to the equivalent **positional** constructor (Enzyme-transparent, behaviour-identical); (ii) the
Enzyme-dependent parts of the canopy gate are guarded to `VERSION < v"1.11"` (identity still runs on all
versions), so CI's forward-compat `test (1)` job stays green. Lifting the guard is an upstream-Enzyme
follow-up (EnzymeAD/Enzyme.jl on Julia ≥ 1.11).

## 16. Update — NN training against the REAL C-binary daily GPP on the full 25-patch cell + the λ lever (scale-up step 7b-cell)

§15 proved the Enzyme-reverse canopy trainer recovers a *known synthetic* correction on one patch. This
step trains the learned correction against the **honest objective** — the LPJmL-FIT C binary's own daily
GPP — on the full Hainich cell (25 patches / 297 reconstructed individuals), and turns on the λ lever.

**The cell objective + an exact per-patch gradient decomposition.** The C daily GPP is a CELL quantity:
the mean over the cell's patches. A single shared learned correction (one MLP, feature-driven per
individual) is trained so the cell-mean GPP `ḡ_i = (1/P)·Σ_p g_{p,i}` matches the C. The cell MSE
`L = (1/D)·Σ_i (ḡ_i − t_i)²` is a sum of squares, so its EXACT gradient factors into one reverse pass
PER PATCH with detached Gauss–Newton residual weights:

  `∂L/∂ps = Σ_p ∂/∂ps [ Σ_i c_i·g_{p,i}(ps) ]`,  `c_i = (2/(D·P))·(ḡ_i − t_i)`   (detached, at the current `ps`).

The identity `Σ_p ∂g_{p,i}/∂ps = P·∂ḡ_i/∂ps` makes this exact (not an approximation) — the weights are
the true residuals. Each per-patch pass is exactly the proven single-patch `daily_step_canopy` Enzyme
path (§15), so the cell gradient inherits its Enzyme-vs-FiniteDifferences correctness and its Julia-1.10
compilation — there is **no** new monolithic multi-patch Enzyme entry point. The per-patch gradients are
summed by REUSING one `Duplicated` shadow across the patch loop (Enzyme accumulates `∂/∂ps` into the
shadow — verified independently), fresh per cell-gradient call. `fdiff_cell_gpp_loss` /
`train_fdiff_cell_rollout!` in the extension; driver `scripts/train_fdiff_canopy_cell.jl`.

**Verification (gate `nn_canopy_training_tests.jl`, cell testitem — 3 ragged patches, self-contained):**
- **Identity** — the zero-init network (BOTH vm + λ hooks) reproduces the pure-physics cell rollout, **Δ = 0**.
- **Cell gradient vs FiniteDifferences** — the per-patch-decomposed cell-MSE gradient matches FD on the
  FULL multi-patch cell loss to **max rel err 6.1e-10** (through the array-mutating canopy, both levers).
- **Recovery** — the cell TBPTT loop drives the loss **0.330 → 0.011 (> 96 %)**; trained cell GPP within
  **0.04 %** of a known vm = 1.15 / λ = 1.05 target.

**Result — the learned canopy Vcmax/λ lever closes the GPP LEVEL against the real C daily GPP.** On the
full 25-patch Hainich cell (C annual GPP 1102.5 gC/m²/yr; kernel-isolation phenology = the C binary's own
daily FAPAR, `phens = fapar_C / max`), fitting the cell-mean daily GPP over the growing-season window
(DOY 105–285):

| lever | annual GPP ratio (model/C) | daily r (full-year) | daily r (GS) | mean GS Vcmax scale |
|---|---:|---:|---:|---:|
| baseline (identity) | 1.093 | 0.9978 | 0.9973 | 1.000 |
| `:vm` | **1.023** | 0.9982 | 0.9984 | 0.798 |
| `:vm, :λ` | **1.010** | 0.9983 | 0.9990 | 0.724 |

Unlike the single-representative path (§14, where the residual is light-limited so Vcmax is the wrong
lever and the fit *degraded* the daily shape — r 0.96 → 0.81), the canopy residual IS Vcmax-shaped: the
learned correction closes the level from +9.3 % toward the C (ratio 1.093 → 1.023 with Vcmax alone,
→ 1.010 adding λ) while the (already excellent) daily correlation **improves** (full-year 0.9978 → 0.9983,
growing-season 0.9973 → 0.9990). This is exactly the lever docs §14/§15 predicted for the coupled canopy
path — light is spread across individuals, so photosynthesis is Vcmax-limited and a modest effective-Vcmax
reduction (mean growing-season scale ≈ 0.80 for `:vm`, ≈ 0.72 with the λ head sharing the load) removes
the inherited over-estimate without touching the seasonal shape. The learned correction is a **safe
residual** on the calibrated physics (identity-at-init, bounded `1 + corr_max·tanh`, `corr_max = 0.6`).

**Multi-year objective through the structure/allocation feedback — the next frontier, not yet reached.**
Training the correction so MULTI-YEAR GPP matches the C — with the canopy structure growing between years
via the allocation — needs Enzyme reverse through `rollout_canopy_years`'s composed path (`_patch_fpars`
layered-light recompute + `grow_individual`'s pipe-model allocation Newton + `individual_from_pools`),
chained onto the daily rollout. A direct probe (a lean 2-year GPP loss folding `daily_step_canopy`
per year and growing between years) raises **`EnzymeNoTypeError`** on Julia 1.10 — Enzyme cannot statically
type the reverse pass through this composed structure path (the likely culprits are untyped temporaries:
the `BitVector` leaf-layer mask in `_patch_fpars` and the allocation-solve primal scan in
`_solve_leaf_inc`). This is an Enzyme *type-analysis* blocker on the composed path, **not** a
differentiability problem: the structure/allocation feedback itself is differentiable and verified —
§12 already shows ForwardDiff `d(grown height)/d(bm_inc)` and the coupled `d(grown height)/d(α_c3)` (daily
flux → bm_inc → allocation) match finite differences. Making that path Enzyme-typeable (typed temporaries
in `_patch_fpars`/`_solve_leaf_inc`, or an `Enzyme.API.maxtypeoffset!` bump) is the documented follow-up;
the single-year cell training above is the landed milestone.

## 17. Update — NN training THROUGH the multi-year structure/allocation feedback (scale-up step 7b-multiyear)

§16 trained the learned Vcmax/λ correction against the real C daily GPP on the full 25-patch cell for a
SINGLE year (structure held fixed), and flagged the multi-year objective — training GPP to match the C
**while the canopy structure grows between years via the allocation** — as the next frontier, blocked
because Enzyme reverse through `rollout_canopy_years`'s composed structure path raised `EnzymeNoTypeError`.
This step RESOLVES that blocker and lands the Enzyme-differentiable multi-year rollout.

**Root-cause diagnosis (corrects §16's hypothesis).** §16 guessed the blocker was an untyped temporary —
the `BitVector` leaf-layer mask in `_patch_fpars` and/or the `_solve_leaf_inc` allocation-solve primal
scan. **That was wrong.** Both differentiate cleanly in isolation: Enzyme reverse through `_patch_fpars`
alone matches FiniteDifferences to **1e-9** on the leaf_c derivative, and `grow_individual` alone (the
`_solve_leaf_inc` Newton) differentiates fine. Isolated by bisection, the real cause is a **struct-in-memory
type-analysis failure**: Enzyme cannot type-analyze a reverse pass that stores `grow_individual`'s BRANCHY
struct output into a `Vector{TreePools}` and then FIELD-SCATTERS it (e.g. `trees[i].height → scratch[i]`
inside `_patch_fpars`). The `TreePools` struct's trailing `is_grass::Bool` + 7 bytes of padding read as
`Anything` in the copied 80-byte `memcpy`, so the reverse pass raises `EnzymeNoTypeError` ("Cannot deduce
type of copy"). Three pieces of evidence pin it: (i) a trivial branch-free growth fed to the identical
`Vector{TreePools}`-scatter consumer differentiates fine — only the real `grow_individual` output through
the struct-Vector scatter fails; (ii) `Enzyme.API.maxtypeoffset!` / `maxtypedepth!` did NOT help, so it is
not a type-analysis size/depth limit; (iii) `looseTypeAnalysis!(true)` cleared the error but returned a
**wrong** gradient — proving a genuine untyped value, not a spurious over-strict check. A second, smaller
instance of the same class: a `Union{Nothing,Vector}` `phens` local carried into the daily loop is an
untypeable `{Pointer,Float64}` phi. Both are structural, not differentiability, problems — §12 already
verifies the structure/allocation feedback with ForwardDiff (`d(grown height)/d(bm_inc)` and the coupled
`d(grown height)/d(α_c3)` match finite differences).

**The fix — struct-of-arrays (SoA).** Keep the differentiated multi-year canopy state as plain
`Vector{Float64}` field arrays (`heights`, `leaf_c`, `sapwood_c`, `heartwood_c`, `root_c`, `crownarea`,
plus the per-tree `Const` constants `sla`/`nind`/`wooddens`/`is_grass`) — **never** a `Vector{TreePools}`
inside the differentiated region. A `TreePools` is built only transiently (a single struct, consumed
immediately) where the physics needs one; it is never the carried, field-scattered container. Two pieces
landed:

- **(a) `_patch_fpars` refactored into an SoA core + a thin unpacking wrapper.** The layered
  Beer–Lambert light is now computed by `_patch_fpars_soa(heights, leafcs, slas, ninds, crownareas,
  isgrass, allom; nlayers, vstep, k_lambert)` — plain `Vector{T}` field arrays + a `Vector{Bool}` grass
  mask, Enzyme-typeable. The original `_patch_fpars(trees::Vector{TreePools}, allom; …)` is a thin
  wrapper that unpacks the struct-Vector into arrays and calls the SoA core — the diagnostic / non-AD
  path, and NOT on the Enzyme multi-year path. The two are **byte-identical** (max|Δ| = 0.0); every
  §9/§12/§16 canopy baseline that goes through `_patch_fpars` is unmoved.
- **(b) `rollout_canopy_years_gpp` — the Enzyme-differentiable multi-year coupled rollout.** A new,
  dependency-free function that runs the same physics as `rollout_canopy_years` (§12) but in SoA form and
  returns only the per-year annual stand GPP `gpp_by_year[yr]` (gC/m²/yr) — the object a multi-year
  training loss descends through. Per year: extract the initial SoA from the `Const` `trees0` by
  iteration → `_patch_fpars_soa` recomputes the layered `fpar` from the current heights → build the daily
  `Individual`s from the SoA (a single transient `TreePools` per tree, consumed at once) → a
  scalar-accumulating `daily_step_canopy` fold accumulating each individual's per-m² `bm_inc = Σ npp_ind`
  + the stand GPP + the annual-mean water scalar (no per-day flux vector — the Enzyme-friendly fold of
  §15) → `grow_individual` rebuilds a single `TreePools` per tree and SCATTERS the grown fields into
  FRESH arrays (next year's structure). The soil water carries across years as its FIELDS (`wcol::Vector`,
  `snow::scalar`), not the `FDiffStateML` struct; `hooks` supplies the learned Vcmax/λ correction
  (identity when off); `phens_by_year` is the kernel-isolation daily leaf-display crutch (e.g.
  `fapar_C/peak`, as §9/§16). Exported.

**Enzyme note (for future readers — two distinct `EnzymeNoTypeError` mechanisms).** Both are the same
underlying limitation: Enzyme's reverse pass must statically deduce the type of every value it stores into
its shadow/tape, and a heap value whose bytes are copied through a `memcpy` (a struct field-scatter, or a
`Union`/`Nothing` phi across a loop back-edge) defeats that deduction.
1. **Branchy struct field-scatter (`Vector{TreePools}`).** `grow_individual` returns a `TreePools` built
   through data-dependent branches (grass skip, abnormal-allocation branch, height-cap transfer). When
   such a struct is stored into a `Vector{TreePools}` and later field-scattered (`trees[i].height →
   scratch[i]`), Enzyme copies the whole 80-byte struct; the trailing `is_grass::Bool` + 7 bytes of
   padding are `undef`-typed to the analysis and read as `Anything` → "Cannot deduce type of copy". The
   fix is to never carry a `Vector{TreePools}` in the differentiated region: SoA `Vector{Float64}` field
   arrays have no padding and no struct memcpy, so every carried value is concretely typed.
2. **`Union{Nothing,Vector}` phi.** A `phens = phens_by_year === nothing ? … : …` local reaching the
   daily loop is a `Union{Nothing,Vector}`; carried across a loop back-edge it becomes an untypeable
   `{Pointer,Float64}` phi. The fix is to MATERIALIZE it up front to a concrete `Vector{Vector{T}}`
   (full display `ones(T, …)` when not supplied), so the loop sees a single concrete type. The same
   discipline applies to the soil state (carried as `wcol`/`snow` fields, not the two-field
   `FDiffStateML` struct, which is itself a `{Vector,Float64}` phi around the outer year loop).
Neither `Enzyme.API.maxtypeoffset!`/`maxtypedepth!` (size limits) nor `looseTypeAnalysis!` (which silently
returns a WRONG gradient here) is a correct workaround — the only correct fix is to remove the untypeable
value.

**Verification (Enzyme reverse through the full multi-year chain).** Enzyme reverse through the composed
multi-year path — SoA structure → `_patch_fpars_soa` layered light → build `Individual`s →
`daily_step_canopy` daily fold → `grow_individual` → next year's SoA — matches FiniteDifferences to
**~1e-11 (scalar `vm_scale` hook derivative)** and **<1e-9 (network-parameter gradient, 8-coordinate FD
subset)**; ForwardDiff through the same rollout w.r.t. a physics input agrees with FD to ~1e-13. This is
the decisive proof that the multi-year structure/allocation feedback is not just differentiable (§12,
ForwardDiff) but **trainable by reverse-mode Enzyme** — the composed path the hybrid actually integrates
through across years.

**Verification (gate `test/testitems/nn_canopy_training_tests.jl`, multi-year testitem — self-contained).**
- **Identity** — the zero-init network reproduces the pure-physics multi-year rollout exactly (**Δ = 0**);
  `_patch_fpars_soa` vs the `Vector{TreePools}` wrapper is byte-identical (max|Δ| = 0.0).
- **Enzyme gradient correctness** — the Enzyme-reverse gradient of the multi-year GPP loss w.r.t. the
  network parameters (through the SoA structure → daily rollout → grow → next-year chain) matches
  **FiniteDifferences to max rel err 8.2e-10** over a random 8-coordinate subset; the Enzyme primal equals
  the direct loss exactly.
- **Recovery** — the multi-year Enzyme online-rollout loop recovers a known correction: the loss falls
  **16.2 → 0.12 (99.3 %)** in 25 epochs, and the trained multi-year GPP lands within **0.28 %** of a known
  `vm=1.15 / λ=1.05` target.

The trainer is a new extension pair `fdiff_multiyear_gpp_loss` / `train_fdiff_multiyear_rollout!` (in
`ext/FDiffTrainingExt.jl`), the multi-year counterpart of the §15/§16 Enzyme trainers — one Enzyme reverse
gradient of the FULL multi-year loss per epoch (no per-chunk TBPTT: the annual structure feedback must stay
inside the differentiated unit). Runtime `[deps]` stays EMPTY. The entry point is **single-patch
multi-year**; the cell-multi-year objective (the per-patch Gauss–Newton decomposition of §16, now with each
patch grown across years) is the next extension.

**What this milestone is — and is not.** The landed deliverable is the *machinery*: the multi-year
structure/allocation feedback is now Enzyme-typeable and gate-verified (identity, Enzyme-vs-FD gradient,
and a 99.3 % recovery of a known correction *through* the between-year allocation). A *real* multi-year
C-binary GPP fit is NOT yet done — it needs (i) real multi-year daily forcing and (ii) per-year C annual
GPP targets, neither committed yet (the driver `scripts/train_fdiff_multiyear.jl` runs the full end-to-end
pipeline on the reconstructed Hainich patch but against a demo target — the 2010 annual GPP repeated — with
its data sources flagged as TODOs). Producing that multi-year reference (via
`scripts/extract_fdiff_individuals_multiyear.py`) and running the cell-multi-year objective against it is
the documented next step. As in §16 the learned correction is a **safe residual** on the calibrated physics
(identity-at-init, bounded `1 + corr_max·tanh`), and — because the canopy residual is Vcmax-shaped (§16) —
it closes the GPP level without touching the seasonal shape, now with the effective-Vcmax reduction carried
consistently through the between-year allocation. ADR 0016 (addendum). The remaining open items are the
cell-multi-year objective, per-PFT phenology for the evergreen/grass minority, and the
upstream-Enzyme-on-Julia-≥1.11 guard-lift (§15).

## 18. Update — NN training on the CELL × MULTI-YEAR objective against a real multi-year reference (scale-up step 7b-cell-multiyear)

§16 fit the learned Vcmax/λ correction to the real C daily GPP on the full 25-patch cell for a SINGLE year
(structure frozen). §17 fit ONE patch's per-year annual GPP THROUGH the between-year allocation, but against
a *demo* target (2010 repeated) — flagging both the **cell-multi-year objective** and a **real multi-year
reference** as the next steps. This step lands both: the cell-mean per-year annual GPP over several years,
fit to the C binary's OWN per-year annual GPP, with every one of the 25 patches grown across years.

**The composition — §16's cell decomposition through §17's multi-year rollout.** The objective is
`Ḡ_y = (1/P)·Σ_p G_{p,y}(ps)`, the cell-mean over patches of each patch's year-`y` stand GPP `G_{p,y}` (from
the SoA multi-year rollout `rollout_canopy_years_gpp`, §17), against the C's per-year annual GPP `T_y`. The
cell MSE over years

  `L(ps) = (1/NY)·Σ_y (Ḡ_y − T_y)²`

is a sum of squares, so — exactly as in §16, but with the year index in place of the day index — its
gradient factors into ONE reverse pass PER PATCH with detached Gauss–Newton residual weights:

  `∂L/∂ps = Σ_p ∂/∂ps [ Σ_y c_y·G_{p,y}(ps) ]`,  `c_y = (2/(NY·P))·(Ḡ_y − T_y)`   (detached, at the current `ps`).

The identity `Σ_p ∂G_{p,y}/∂ps = P·∂Ḡ_y/∂ps` makes this exact. Each per-patch pass `Σ_y c_y·G_{p,y}` is a
linear functional of exactly the PROVEN single-patch multi-year rollout (§17), so the cell-multi-year
gradient inherits its Enzyme-vs-FiniteDifferences correctness AND its Julia-1.10 compilation — there is
**no** new monolithic multi-patch AD entry point. The per-patch gradients are summed by REUSING one
`Duplicated` shadow across the patch loop (Enzyme accumulates `∂/∂ps` into the shadow), fresh per gradient
call; each patch pass is ONE Enzyme reverse over the FULL multi-year rollout (no per-chunk TBPTT — the
annual structure feedback stays inside the differentiated unit, as in §17). `fdiff_cell_multiyear_gpp_loss`
/ `train_fdiff_cell_multiyear_rollout!` in the extension; driver `scripts/train_fdiff_cell_multiyear.jl`.

**A real, committed multi-year reference (`scripts/extract_fdiff_cell_multiyear.py`).** The prerequisite
§17 flagged — real multi-year forcing + per-year C annual-GPP targets — is produced by slicing data already
on disk (no C re-run): the single-cell C re-run (`run_fdiff_validation_cell.sh`) already wrote the full
2000–2019 daily forcing + daily C GPP/FAPAR, and the multi-year structure reconstruction
(`extract_fdiff_individuals_multiyear.py`) already wrote the per-year per-patch individuals. The script
commits a CI-runnable slice: the **2008** start-year 25-patch reconstructed structure
(`hainich_individuals_2008.csv`), the per-year daily forcing for sim years **2009/2010/2011**
(`hainich_multiyear_forcing.csv`), and those years' daily C GPP + FAPAR (`hainich_multiyear_targets.csv`).
Start-of-year convention (matching the dynamic-structure validation §12): the rollout starts from 2008's
reconstructed structure and simulates the subsequent years, so the structure entering each sim year is
F_diff's OWN grown structure; the C annual-GPP trajectory is the target for that self-driven growth. Kernel
isolation: the per-year daily leaf display is driven by that year's C FAPAR (`phens = fapar_C / peak`),
isolating the Vcmax/λ level lever from phenology mismatch (the §16 discipline, across years).

**Verification (gate `nn_canopy_training_tests.jl`, cell × multi-year testitem — 3 ragged patches × NY = 2,
self-contained):**
- **Identity** — the zero-init network (BOTH vm + λ hooks) reproduces the pure-physics cell multi-year
  rollout, per-year **Δ = 0**.
- **Cell-multi-year gradient vs FiniteDifferences** — the per-patch-decomposed cell-multi-year MSE gradient
  matches FD on the FULL multi-patch multi-year loss to **max rel err 1.5e-10** (through the SoA structure →
  daily rollout → grow → next-year chain, both levers); the decomposed primal equals the direct cell MSE.
- **Recovery** — the cell-multi-year loop drives the loss down **98.8 %** in 25 epochs; trained cell GPP
  within **0.07 %** of a known vm = 1.15 / λ = 1.05 target.

**Result — the learned canopy Vcmax/λ lever closes the ANNUAL GPP LEVEL against the real C per-year annual
GPP, over the full 25-patch cell, through the multi-year structure feedback.** Start structure 2008; sim
years 2009/2010/2011; C per-year annual GPP (cell-mean) [1177.4, 1102.5, 1233.1] gC/m²/yr; kernel-isolation
phenology = that year's C FAPAR:

| lever | 2009 | 2010 | 2011 | mean ratio |
|---|---:|---:|---:|---:|
| baseline (identity) | 1.026 | 1.014 | 1.063 | 1.034 |
| `:vm` | 0.992 | 0.981 | 1.022 | **0.998** |
| `:vm, :λ` | 0.991 | 0.979 | 1.020 | **0.996** |

(per-year model/C annual-GPP ratio; C targets [1177.4, 1102.5, 1233.1] gC/m²/yr.)

The learned canopy Vcmax/λ correction closes the cell-mean annual-GPP LEVEL against the real C per-year
annual GPP THROUGH the multi-year structure feedback — mean ratio **1.034 → 0.998** (`:vm`) → **0.996**
(`:vm, :λ`) — with the level residual carried consistently across years by F_diff's OWN self-driven grown
structure (the rollout starts from 2008 and grows; the C FAPAR drives only the leaf display). ONE shared
correction is fit to all three years' cell-mean at once, so it trims the year-to-year SPREAD rather than
zeroing each year independently: 2011 (the high outlier — a high-GPP year, baseline 1.063) lands at 1.02
while 2009/2010 settle at ~0.98–0.99, and the mean sits at ≈1.0. This is the §16 within-year cell result
(the Vcmax-shaped canopy residual closes the level while the daily/seasonal shape is preserved) now extended
across years through the between-year allocation — the honest multi-year analogue. The λ head adds little
over `:vm` alone here (0.998 → 0.996), consistent with §16 (the canopy level is Vcmax-shaped). Loss
(mean-squared per-year annual-GPP error, gC²·m⁻⁴·yr⁻²) 2390 (identity) → ~434 (`:vm`) → ~419 (`:vm, :λ`).
Cost: baseline forward over all 25 patches ~5 s; first cell-multi-year gradient ~413 s (one-time Enzyme
compile of the multi-year reverse pass); ~34 s/epoch post-compile (25 per-patch reverses); the two-fit
driver ≈ 30 min. Heavy runs like this belong on a compute node — `scripts/sbatch_train.sh
scripts/train_fdiff_cell_multiyear.jl` submits it as a durable SLURM batch job.

**What this milestone is — and is not.** This is the first honest cell fit *through* the structure feedback:
the §16 cell-mean objective (the quantity the C actually reports) trained against the C's real per-year
annual GPP trajectory (§17's demo target replaced by a committed real reference), with every patch grown by
its own allocation across years. As in §16/§17 the correction is a **safe residual** on the calibrated
physics (identity-at-init, bounded `1 + corr_max·tanh`). What it is NOT: a full multi-decade fit (the span
is 3 years, bounded by the committed reconstruction 2008–2011) or a demography-coupled run (fixed-N canopy;
whole-tree mortality/establishment is S's job). Remaining open items: **per-PFT phenology** for the
evergreen/grass minority (one beech-GSI `phen` patch-wide today), **grass structure prognostic**
(`grass_allocation.c`), and the **upstream-Enzyme-on-Julia-≥1.11 guard-lift** (§15). Runtime `[deps]` stays
EMPTY. ADR 0016 (addendum).

## 19. Update — per-PFT GSI leaf phenology + the beech-tmin correction (scale-up step 8)

§11 removed the daily C-FAPAR "crutch" by self-computing the GSI leaf phenology (`phenology_gsi.c`), but
with a **single beech GSI applied patch-wide** — every individual, including the evergreen/grass minority,
got the beech (TeBS, summergreen) leaf-display curve. The LPJmL-FIT config runs `phenology_gsi` **per PFT**
(`lpjmlfit.js` sets `"new_phenology":true` + `"individual":true`, so the four-limiter GSI runs for *every*
natural PFT with its own parameters — the "evergreen"-named PFTs are **not** static `phen≡1`). This step
generalizes the self-computed phenology from one beech GSI to per-PFT, and corrects a parameter-sourcing
bug found along the way.

**The beech-tmin correction (a real fidelity fix).** The committed `PhenParams` defaults (beech) had
`tmin_slope = 2.0`, `tmin_base = 8.0` — these are the **standard** `par/pft.js` values, but the active FIT
run (verified session 8) uses **`par/pft_lpjmlfit.js`**, which sets beech `tmin_slope = 4.0`,
`tmin_base = 8.5` (all other beech GSI params — `tmax` 1.74/41.51, `light` 58/40, `wscal` 5.24/20.96 —
already matched). So the self-computed phenology had been using cold-limiter params the C binary it
validates against never used. Correcting them to the active file (`tmin` 2/8 → 4/8.5) brings the
self-phenology into consistency with the C: the standalone 25-patch canopy GPP annual ratio tightens
**1.17 → 1.13** (closer to the C), transpiration **1.08 → 1.05**, with the daily GPP correlation essentially
unchanged (≈ 0.99). Only one committed baseline moved — `hainich_canopy_baseline_2010.txt` (the standalone
self-phen canopy: `gpp` 1286 → 1250, `transp` 258 → 251 gC·m⁻²·yr⁻¹ / mm·yr⁻¹). The single-representative
and multilayer baselines and `fdiff_annual_totals.txt` are **unmoved** — they drive phenology from the C
FAPAR (kernel isolation), not the self-computed GSI.

**Per-PFT parameters, verbatim from the active file.** `pft_phenparams(id, T)` returns the twelve GSI
numbers (`tmin/tmax/light` slope·base·tau + `wscal` slope·base·tau) for each 0-based natural PFT id 0–9,
read directly from `par/pft_lpjmlfit.js`. The individual-mode subtlety: under `config->individual` the
water-limiter inflection is **`minwscal·100`, NOT the par-file `wscal.base`** (`phenology_gsi.c:64-66`), so
`wscal_base = minwscal_median·100` (beech `0.2096·100 = 20.96`, which is why the previous beech value
happened to be right). `tebs_phenparams()` == `pft_phenparams(3)` == the `PhenParams` defaults (single
source of truth for beech). Crops (id ≥ 10, `cropgreen`) use a different routine and are out of scope.

**The per-individual phen path (AD-safe by construction).** `daily_step_canopy` and `patch_albedo` now
accept `phen` as **either a scalar (patch-wide) or a per-individual vector**, via a compile-time-dispatched
accessor `_phen_at`. In the scalar specialization `_phen_at(phen, i)` constant-folds to the plain value, so
the scalar path — **every committed baseline and the Enzyme trainer** — compiles to the identical IR it had
before and is **byte-identical** (gate: scalar vs a uniform vector Δ = 0 across every flux + state field).
The Enzyme multi-year training path (`rollout_canopy_years_gpp`, `ext/FDiffTrainingExt.jl`) keeps passing a
**scalar** C-FAPAR phen per day (kernel isolation), so it is structurally untouched. `per_pft_phenology`
(the standalone driver) advances one `PhenState` per distinct PFT and returns the per-day × per-individual
leaf-display; `rollout_daily_canopy` gains a `pft_ids` kwarg that co-solves per-PFT phenology with the stand
water feedback and a **lag-1 forest-floor light attenuation for grass** (`grass_lf = 1 − Σ_trees fpar_i·phen_i`,
the C's `fpar_grass·light` for the understory light limiter, `phenology_gsi.c:30-35`).

**Result (full 25-patch Hainich cell, 2010, standalone self-driven).** Cell composition: beech (id 3) 259
individuals, temperate C3 grass (id 8) 25, temperate/boreal evergreen + boreal summergreen minority (ids
1/2/4/5) 13. Per-PFT phenology gives each PFT its physically-correct leaf display — annual-mean `phen`
evergreens **0.77 (TeNE) / 0.89 (TeBE) / 0.96 (BoNE)** vs summergreens **0.46 (beech/BoBS)** and grass
**0.47** — and, wired through the canopy, **moves the cell GPP annual ratio vs the C `1.134 → 1.097`
(closer to the C) while the daily GPP correlation improves `0.988 → 0.993`** (cell-mean |ΔGPP| ≈ 40
gC·m⁻²·yr⁻¹, 3.2 %). The improvement is driven entirely by the minority the beech-patch-wide phen got
wrong: the evergreens now hold winter leaf display, and the grass understory is light-shaded rather than
given the full beech curve. Beech (the dominant PFT) self-phenology still tracks the C's daily FAPAR at
**r ≈ 0.99**.

**Verification (gate `per_pft_phenology_tests.jl`, self-contained):**
- **Param fidelity** — `pft_phenparams(id)` for every id 0–9 matches `par/pft_lpjmlfit.js` exactly (all
  twelve numbers, `wscal_base = minwscal_median·100`); beech is the corrected `tmin` 4.0/8.5; crops throw.
- **Trajectories** — per-PFT `phen ∈ [0,1]`, distinct and physically ordered (summergreen beech swings
  near-off → near-full; the "evergreen"-named TeNE runs full GSI but holds far more winter display; grass
  forest-floor shading lowers its light limiter).
- **Scalar byte-identity** — `daily_step_canopy`/`patch_albedo` with a scalar phen == with a uniform
  per-individual vector, **Δ = 0** across every flux + state field (self-eeq and kernel-isolation `eeq_ext`
  paths); a per-individual vector correctly changes only the individuals whose display changed.
- **Self-driven rollout** — the per-PFT `rollout_daily_canopy` runs, closes water exactly (`|Σprecip −
  (Σout + ΔS)| < 1e-6`), and reduces to the beech-patch-wide default identically on an all-beech patch
  (rtol 1e-12).

**What this is — and is not.** A faithful per-PFT generalization of the self-computed GSI phenology, plus a
beech-tmin sourcing correction — essential for the ESM goal of running F_diff on non-beech vegetation
(grasslands, evergreen forests), where the single beech GSI would be badly wrong. It is **AD-safe**
(per-individual phen is Const forcing-derived data on the standalone path; the Enzyme trainer keeps scalar
phen, byte-identical). Documented v1 simplifications: the per-individual `minwscal` corridor sampling of the
C's individual mode is collapsed to the PFT **median**; the grass forest-floor light is a **lag-1**
attenuation from the previous day's tree leaf display; and the `aphen` COLDEST_DAY reset (`newpft.c`) is
omitted (as in the §11 beech port). Runtime `[deps]` stays EMPTY.

## 20. Update — prognostic GRASS structure: the `allocation_grass.c` port (scale-up step 9)

Through §19 the multi-year structure rollout grew only **trees**: `grow_individual` returns grass
unchanged, and — more fundamentally — grass was structurally *dropped* from the multi-year path. The
committed `ind`-output reconstruction gives grass rows `leaf_c = root_c = crownarea = nind = 0` (grass is a
per-**area** cohort, carried in the daily canopy via `lai`/`fpc`/`fpar`, not per-individual-count), so a
round-trip through `individual_from_pools`/`_patch_fpars_soa` (which derive structure from
`crownarea`/`leaf_c`/`nind`) zeroed grass to a dead cohort. Every multi-year test/script therefore filtered
grass out (`type ≤ 6`). This step makes grass leaf/root carbon **prognostic** — a faithful differentiable
port of the LPJmL-FIT NATURAL-veg annual grass sequence `turnover_grass.c` → `allocation_grass.c`
(`annual_grass.c:29-30`, `landusetype == NATURAL`) — essential for the ESM goal of running F_diff on
grasslands (where trees are absent entirely).

**The per-area grass convention.** `grass_treepools(agb, vegc, sla)` reconstructs a grass `TreePools` from
the two grass columns the `ind` output *does* carry: leaf carbon = `agb` (`agb_grass.c:25` `= leaf·nind`,
i.e. `lai/sla`, per-m²) and root carbon = `vegc − agb` (grass has no woody pools, so `vegc = leaf + root`).
It sets `crownarea = nind = 1` (the per-area convention: `lai = leaf_c·sla` and `fpc = 1 − e^{−k·lai}`,
both of which the existing recompute needs `> 0`) and `height = sapwood_c = heartwood_c = 0`. With this
convention **no change to `individual_from_pools`/`_patch_fpars_soa` was needed** — the grass `fpar`
recompute already reproduces the C: at the committed Hainich structure the recomputed grass `fpar = 0.03042`
matches the C's `fpar_leafon = 0.0304233` to 5 s.f.

**The allocation port (`grow_grass_individual`).** Closed-form carbon math (no allometry solve): leaf turns
over **daily** (`turnover_daily_grass.c`) and root **monthly** (`turnover_monthly_grass.c`), each
accumulating against the within-year-constant pool ⇒ the annual pool is reduced by `pool·rate`
(`leaf → leaf·(1 − r_leaf)`, `root → root·(1 − r_root)`); the reproduction reserve (`turnover_grass.c:45`)
removes `bm·reprod_cost` before allocation (growing-days fraction ≈ 1, v1, as for the tree path); and the
natural-veg full-reallocation (`allocation_grass.c:87-118`, `with_nitrogen = no` ⇒ `vscal = 1`) partitions
`bm_net` between leaf and root at `lmtorm = lmro_ratio·(lmro_offset + (1 − lmro_offset)·min(1, wscal))`,
including the no-reallocation caps and the negative-leaf reduction branch (`:97-110`). (The reproduction
growing-days fraction is *exactly* 1 on the NATURAL path — `patch->growing_days` increments unconditionally,
`daily_natural.c:82` — so this is not an approximation.) `grass_allocparams`
holds the temperate C3 grass (id 8) numbers **verbatim from the active `par/pft_lpjmlfit.js`**:
`lmro_ratio 0.8`, `lmro_offset 0.5`, leaf turnover rate `1.0` (full annual renewal), root turnover rate
`0.5` (`turnover.root 2.0 → 1/2` after the `fscanpft_grass.c:124` reciprocal), `reprod_cost 0.1`.

**Allocation faithfulness (the deliverable, gate-verified).**
- **Golden** — `grow_grass_individual` reproduces a direct hand-port of the `allocation_grass.c` natural-veg
  formula across **every** branch (positive / zero / negative `bm`; the negative-leaf reallocation) to
  **< 1e-5** (the residual = the AD-safe `smoothmin(1, wscal)` vs the C's hard `min`).
- **Conservation** — Δ(leaf + root) = `bm_net − (leaf_turnover + root_turnover)` to **4.4e-16** (the
  allocation invents no carbon, net of turnover).
- **Equilibrium fed the C's grass NPP** (the `bm_inc_ext` crutch, exactly as the *tree* allocation was
  validated in §12 before the self-NPP was calibrated in §13): fed the C's Hainich grass NPP (patch-15
  grass `npp = 10.73`), from a cold start the grass equilibrates to leaf:root = **0.791** vs the C's
  `6.406/8.023 = 0.799` (within 3 %), with leaf/root magnitudes within ~8 % — the allocation reproduces the
  C's grass structure when given the C's carbon.

**The honest finding — the self-computed grass NPP is uncalibrated (~3×).** With the grass carbon pools now
live, the daily canopy gives the grass its physically-correct per-m² respiration (`nind = 1`), but the grass
still uses the **beech** `PhotoParams`/`RespParams`/temp-stress. F_diff's self-computed grass NPP at the C's
structure is **31.8 vs the C's 10.7** (~3×), so a **self-driven** grass overshoots (leaf 6.4 → ~48, lai
0.27 → 2.0 over 8 years). This is *precisely* the tree story — §6 shipped the tree allocation with the
self-NPP still a crutch (`bm_inc_ext`), and §13 later calibrated it (the `βgrowth` growth-resp floor +
fine-root phen-gating). The grass allocation is the deliverable here; the **grass NPP calibration**
(grass-specific Vcmax / `respcoeff` / temperature optimum, and the `fpc_grass.c` cover competition) is the
documented next step. Until then, grass-inclusive multi-year runs should drive the grass with the
`bm_inc_ext` crutch (the C's grass NPP), as the gate does.

**AD-safe, additive by construction.** `grow_grass_individual` is scalar carbon math (no arrays, no struct
field-scatter), so it is Enzyme-typeable on the multi-year SoA path by the same argument as
`grow_individual`. The grass branch (`isgrass[i] ? grow_grass_individual(galloc, …) : grow_individual(…)`)
fires **only** for `is_grass` individuals, and every existing caller passes trees only — so all committed
tree baselines and the Enzyme trainer are **untouched** (byte-identical). Gate `grass_structure_tests.jl`
(five self-contained testitems): param fidelity + reconstruction; golden-vs-C + conservation + bounds;
equilibrium-fed-C-NPP → C structure; **ForwardDiff** d(grown pools)/d(bm, wscal) and d(ΣGPP)/d(α_c3)
*through the coupled multi-year grass-inclusive rollout* vs finite differences; and **Enzyme reverse**
through the grass-inclusive multi-year training path (grad vs FD `rtol 1e-4`, guarded `VERSION < 1.11` as
the other Enzyme canopy gates). Runtime `[deps]` stays EMPTY.

**v1 simplifications (documented).** The grass pool→structure light recompute shares the beech `k_beer`
(0.59 vs the grass 0.5); grass maintenance respiration reuses the beech `RespParams`; the reproduction
growing-days fraction is taken as 1 (as for trees); and — the load-bearing one — the self-computed grass NPP
is uncalibrated (grass shares the beech photosynthesis parameters), so the faithful validation uses the C's
grass NPP as the carbon input.

## 21. Update — decadal (11-year) fidelity of the coupled multi-year rollout (scale-up step 10)

§18 validated the cell × multi-year objective over a **3-year** span (2009–2011). The open question it left
is the **fidelity horizon**: F_diff's coupled rollout starts from a reconstructed structure and self-drives
(each patch grown across years by the pipe-model allocation) — over a decade, does the self-driven structure
stay faithful to the C, or drift / blow up? This step extends the committed real reference to a full DECADE
(2009–2019, 11 sim years) and measures it.

**The decadal reference (committed, no C re-run).** `scripts/extract_fdiff_decadal.py` slices the full-period
single-cell daily CSV already on disk (`hainich_c42490_daily_2000_2019.csv`) into
`hainich_decadal_forcing.csv` (per-year daily forcing) + `hainich_decadal_targets.csv` (per-year daily C
GPP + FAPAR), reusing the already-committed 2008 start structure. The C's own per-year annual GPP over the
decade is `[1177, 1102, 1233, 1181, 1085, 1241, 1146, 1150, 1147, 1373, 1286]` gC·m⁻²·yr⁻¹ (2009→2019) — a
rich decadal target driven mostly by interannual weather, no trend.

**★ Result — the coupled rollout stays faithful over the decade.** Starting from the 2008 reconstructed
25-patch structure and self-driving 11 years (kernel-isolation C-FAPAR phenology, each patch grown by its own
allocation), F_diff's cell-mean per-year annual GPP tracks the C's own per-year annual GPP with:
- **mean annual-GPP ratio 1.066** over 2009–2019 (F_diff's inherited ~+7 % GPP-phenology level, §13/§19), each
  year **bounded in 1.01–1.11** — a mild mid-decade drift (peaks ~1.11 at 2015–2017) that recovers by 2019,
  and **no runaway** (cell GPP stays in 1118–1401 gC·m⁻²·yr⁻¹, no blow-up of the self-driven structure);
- **interannual correlation r = 0.86** with the C's year-to-year variability — the coupled rollout responds to
  the real forcing, mirroring the C's high years (2011/2014/2018/2019) and low years (2010/2013), not just a
  flat mean.

So the coupled multi-year rollout is fidelity-stable over a decade: the level bias is the documented,
bounded GPP-phenology offset (it does not compound into a drift), and the self-driven structure neither
collapses nor blows up over 11 years. This is the first validation of the coupled rollout beyond 3 years.

**Gate `decadal_validation_tests.jl`** (self-contained on the committed decadal reference): the 25-patch
rollout runs the full 11 years and stays physical (finite, positive, bounded per-year GPP); the mean ratio is
near 1 (≤ 1.12) with each year bounded (0.9–1.2); and the per-year correlation with the C exceeds 0.7
(measured 0.86). Runtime `[deps]` stays EMPTY.

**Two investigation findings recorded this step (sharpen the roadmap; no code change).**
- **Grass-NPP calibration is *structural*, not a parameter fix.** Decomposing the §20 self-driven grass
  overshoot (~3×): the run is carbon-only (`with_nitrogen:"no"` — N-limitation ruled out); the grass fPAR the
  recompute produces matches the C exactly (0.03042 vs 0.0304233 — open-field light ruled out); grass is
  light-limited, insensitive to soil water (shared-water ruled out); grass root C:N (30) and `respcoeff` (1.2)
  equal the beech values F_diff reuses (respiration ruled out). The residual overshoot is the **shared
  stand-mean conductance** (`gp_stand`, `daily_step_canopy`): F_diff gives the understory grass the
  tree-dominated stand conductance, so it is not demand-limited the way the C's *per-PFT* grass is. Fixing it
  faithfully needs per-PFT/per-individual conductance — a structural change to the two-pass conductance model
  (which would move the validated tree transpiration/GPP), not a clean grass-only parameter port. So grass-NPP
  calibration is deferred to a per-PFT-conductance step, not attempted as a quick fix.
- **The Enzyme-on-Julia-≥1.11 guard-lift is blocked upstream.** Probed on Julia 1.11.7 with the latest
  Enzyme 0.13.187 (newer than the 0.13 the guards were written against): the canopy forward pass is fine
  (loss finite), but the Enzyme *reverse* through the array-mutating canopy path still raises
  `Enzyme.Compiler.EnzymeInternalError` — the same class of failure §15 documented. So the `VERSION < 1.11`
  guards cannot be lifted by a 0.13.x bump; it remains an upstream-Enzyme (or 0.14-migration) follow-up.
