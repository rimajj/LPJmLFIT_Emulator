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
