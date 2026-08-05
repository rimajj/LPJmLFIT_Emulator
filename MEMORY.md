# MEMORY.md — SHARED durable state for the LPJmL-FIT hybrid land-component emulator

> **Shared, cross-cutting durable state only** (ADR 0029) — the facts and status every work line needs: what
> this is, the `[VERIFIED]` facts, the load-bearing ADR constraints, and the cross-line frontier.
> **Any line may APPEND a cross-cutting `[VERIFIED]` fact here**; *restructuring* this file (the
> `consolidate-memory` reshape) is **integrator-only**, because it is a destructive in-place rewrite that can
> silently auto-merge away another line's edit.
> **Per-line state lives in `lines/<X>/STATE.md`** — see the router below. Environment/runbook facts live in
> `CLAUDE.md` (+ §9 for the parallel-line protocol); per-line narrative in `lines/<X>/JOURNAL.md`; the story
> of one change in a `changelog.d/<X>-*.md` fragment.
> Reshaped 2026-07-22 (consolidation P0), 2026-07-27 (collapsed the Tier-0/Tier-1 narrative), and 2026-07-28
> (split per-line state out; ADR 0028/0029). Pre-consolidation copies:
> `docs/archive/MEMORY_2026-07-{22,27}_pre-consolidation.md` (and in git).
> Cap: ≤ 400 lines / ≤ 15k tokens — keep it that way; narrative goes to a line JOURNAL, not here.
>
> Tags: **[VERIFIED]** confirmed against source/data · **[DECISION]** frozen unless reopened via ADR ·
> **[TODO]** must be resolved · **[ASSUMPTION]** believed, not confirmed.

---

## 0. Router — which line am I, and where do I continue?

Work runs as **4 parallel lines**, one long-lived branch + git worktree each (ADR 0028/0029). A session's line
is the branch in the worktree it was launched from; the `SessionStart` hook prints it plus that line's
`## NEXT` action. **Continue from your line's STATE.md, not from this file.**

| Line | Branch · worktree | Scope | State (start here) |
|---|---|---|---|
| **S** | `line/S` · `/p/projects/open/Jamir/wt-S` | Component-S science — close the trait per-cell headroom, grass ownership, in-loop OOD | [`lines/S/STATE.md`](lines/S/STATE.md) |
| **M** | `line/M` · `/p/projects/open/Jamir/wt-M` | Multi-cell coupled S+F+E (P3) — per-cell inputs, S multi-cell, C-truth validation, resilience | [`lines/M/STATE.md`](lines/M/STATE.md) |
| **E** | `line/E` · `/p/projects/open/Jamir/wt-E` | Component E vs observations (P2) — PLUMBER2/FLUXNET, wind/psurf remap, sublimation-λ | [`lines/E/STATE.md`](lines/E/STATE.md) |
| **O** | `line/O` · `/p/projects/open/Jamir/wt-O` | Online coupling (P4/P5) — licensing basis, P4 design, Terrarium `Abstract*`, SpeedyWeather | [`lines/O/STATE.md`](lines/O/STATE.md) |

`main` (this directory) is the **integration** worktree: merges, `changelog.d` collation, shared-file
reconciliation, `Project.toml` deps, and cross-cutting ADRs (0001–0029). Ownership map + the frozen cross-line
contracts: **ADR 0029**. Protocol/mechanics: **`CLAUDE.md` §9** + the `repo-commit` skill.

---

## 1. What this is

Hybrid ESM-ready land component from **LPJmL-FIT** (LPJmL 5.6.004 + FIT; carbon-only, `individual=true`,
`with_nitrogen="no"`). Three components:

- **S** — slow ML emulator of the per-cell **trait/size distribution** + count N (annual). *The novelty.*
- **F / F_diff** — the fast, differentiable, conserving daily biophysical core kept from LPJmL-FIT
  (photosynthesis, water, soil thermal), reimplemented AD-friendly.
- **E** — surface-energy-balance + skin-temperature closure the ESM needs and LPJmL-FIT lacks.

Goal: run **offline** emulating LPJmL-FIT faithfully **and** run **online** coupled to SpeedyWeather.
Orders + reasoning: `STEERING_PROMPT.md`, `PROJECT_REVIEW_2026-07-22.md`. Runbook: `CLAUDE.md`.

---

## 2. Phase status (as of 2026-07-28; per-line detail in `lines/<X>/STATE.md`)

| Phase | State | Evidence / gate |
|---|---|---|
| **0 DESIGN** | ✅ done | schemas + interface contract frozen (`DESIGN.md`); both load-bearing findings re-verified |
| **1 Carbon+water closure** | ✅ PASSED | carbon flux identity 7.3e-5 PgC/yr, 0.6% cumulative drift; water proven by `-DSAFE` per-cell abort over all 67,420 cells × 20 yr (global cumulative \|Σprec−Σ(ET+runoff)\|/Σprec median 0.87%); 186 GB daily dataset generated |
| **2 S offline** | ✅ done — **GLOBAL flux-driven** (ADR 0020-0027) | native-Julia count DRF + recruit copula, K-fold-BY-CELL OOS over **45009 cells**. Counts **AT the seed1-vs-seed2 noise floor** (per-cell-mean r²=0.9994); pooled+transient held-out-BY-SCENARIO R²=0.9847 (unseen regime). Traits: pooled marginal KS 0.004-0.015; **per-cell median has model HEADROOM** (r SLA 0.87 / Wd 0.52 / D95max 0.74 / minwscal 0.78 — the floor is 0.90-0.97 ⇒ learnable, not noise). The climate-only `DirectEmulator` is retained ONLY as the OOD benchmark it beats **2.35×** (ADR 0020) |
| **3 F_diff** | ✅ scale-up steps 1–11 done; C-validated **Hainich only** | multi-layer soil, multi-PFT canopy, prognostic structure, self-computed calibrated NPP, NN λ/Vcmax hooks (Enzyme/Zygote gradients verified), grass faithful to ±10–15%, `sapwood_bg` pool added. Decadal (2009–2019) mean GPP ratio 1.066, interannual r=0.86, no drift |
| **4 E energy** | ✅ landed (ADR 0017) + **P2 tower-validated** (ADR 0072); **nocturnal H DIAGNOSED (ADR 0073)** — `λ_g`, not `g_a` | `SEBEnergyClosure` closes `Rn=LE+H+G` to **1.4e-14 W/m²**; H the residual; MO g_a stability correction ON. Coupled Hainich decade reproduces the **2018 drought** (summer Bowen 0.89 vs ~0.2). **vs 4 PLUMBER2 towers (498k steps): Rn R² 0.986–0.996, T_skin daily RMSE 1.4–2.0 K / R² 0.76–0.95, H bias inside the observational band (76.4 % of DE-Hai days) but daily R² 0.125–0.778 and nocturnal R² −1.0…−5.6**. **ADR 0073:** that night failure is the GROUND-HEAT term's timescale, not `g_a` (modelled nocturnal `g_a` within 0.7 % of the measured `u*` value) ⇒ **`λ_g ≈ 1.0`, not 7.0**, at the daily step (daily H R² 0.03→0.64 DE-Hai); `lambda_g` is the live E→M integration point, `stab_amp` is withdrawn |
| **5 Multi-cell** | 🟡 offline S done; COUPLED still 5-biome F+E | OFFLINE S generalizes globally (K-fold-BY-CELL, 45009 cells — Phase 2). COUPLED S+F+E runs across 5 biomes but `slow=nothing` (F+E only; energy ≤3e-14, climate-correct partitioning); **not yet** the coupled flux-driven S across cells vs C-truth demography, nor the resilience battery |
| **6 Online / SpeedyWeather** | ⬜ not started | |
| **7 ESM packaging** | ⬜ not started | |

**Remaining project (not done):** the flux-driven Component-S is IN the coupled loop and validated GLOBALLY
**offline** (counts at the noise floor; the OOD win is `[VERIFIED]` 2.35×) — but the **coupled** S+F+E run
beyond Hainich is F+E-only so far (S not yet driven across cells vs C-truth demography); the **trait per-cell
median has model headroom** (esp. Wooddens — richer conditioning, P3); E's **nocturnal H is still unfit but now
DIAGNOSED** (P2 ran: Rn + T_skin verified, H only in the mean — ADR 0072; the cause is the ground-heat
timescale, `λ_g ≈ 1.0` not 7.0 — ADR 0073); nothing runs online with SpeedyWeather. F_diff and the
coupled loop remain **Hainich-C-validated only** — single-cell fidelity is scaffolding, the global evidence
is the offline S.

---

## 3. Verified facts — the load-bearing, durable ones

### Model / data structure
- [VERIFIED] Integration is **daily**; no sub-daily physics except the soil-heat numerical substep. Daily
  output is a **runtime config flag** (`"timestep":"daily"`), never a recompile.
- [VERIFIED] LPJmL-FIT has **no surface energy balance**: ET = Priestley–Taylor equilibrium/demand–supply;
  soil temp uses **air temp** as the top Dirichlet BC; no H, G-as-flux, T_skin, or Rn closure. All of that
  is component E (new physics), validated **out-of-model** against PLUMBER2 towers — sourced and scored,
  ADR 0070/0072.
- [VERIFIED] Forcing consumed: tas, precip, swdown, **net** longwave (`lwnet`, downward-positive), `huss`
  (→VPD, hard dependency), CO₂. **Wind is read but unused**; **surface pressure is hard-coded** `p=1e5` in
  `photosynthesis.c`. E needs **wind + psurf** as genuinely new inputs.
- [VERIFIED] **Fire is ON (GlobFIRM)** ⇒ carbon closes only with fire + establishment:
  `ΔC = NPP − Rh − firec + flux_estabc`; `NBP_atm = Rh + firec − NPP − flux_estabc`. A fire-free
  `NEE = Rh − NPP` will NOT close. Mortality drivers: water stress, temp stress, growth efficiency, age.
- [VERIFIED] **Constant-CO₂ regime** (`with_nitrogen="no"` ⇒ unbounded CO₂ fertilization ⇒ future CO₂ held
  constant). OOD test = **warming/precip at constant CO₂**, not rising CO₂. NEE is diagnostic-only, so
  SpeedyWeather's missing carbon cycle is a non-issue. **Not** valid for CO₂-fertilization projections.
- [VERIFIED] Allometry is **re-derived, not co-predicted**: height = k_latosa·Csap/(Cleaf·SLA·wooddens);
  crownarea (Jucker 2022); LAI = Cleaf·SLA/crownarea; FPC = crownarea·nind·(1−e^(−k·LAI)); AGB = leaf+heart+sap.
- [VERIFIED] **`individual=true` config skips many C paths.** `light()`/`light_grass()` (cover/light
  competition) are **never called** (`annual_natural.c:117` gates on `!individual`); active grass reduction
  is `reduce_grass` (fpc-only, no carbon killed, fires 0/25 at Hainich). Per-PFT `gp_pft`/`gc_pft` are
  diagnostic-only; GPP uses the stand mean `gp_stand`. **Always confirm a C routine actually runs here
  before porting it** (the sessions-16/17/19 waste). Active param file = `par/pft_lpjmlfit.js` (beech =
  ANGIO allometry), **not** `par/pft.js`. `-DPERMUTE` randomizes daily PFT-depletion order ⇒ the C is
  non-deterministic / order-averaged.

### Prototype cell (critical)
- [VERIFIED] **Hainich (DE-Hai) = global orderA grid 0-based index `42490`** (lat 51.25/lon 10.25; 98% beech,
  PFT type 3). **Index `28008` in the global grid is Sonoran desert** — it is Hainich only in the repo
  `-DSINGLESITE` grid. Single-cell daily re-run: `STARTGRID=ENDGRID=42490`. Byte-verified against grid.nc.

### Per-cell soil + rooting inputs (cross-cutting; ADR 0050, skill `provision-coupled-cell`)
- [VERIFIED] **Soil layer thicknesses are a C GLOBAL, not per-cell** (`fscansoilpar.c:36-39` ← `par/soil_20m.js`
  = `200,300,500,1000×19,3000` mm). The per-cell Pelletier `soildepth` input is read and then **discarded** —
  `newgrid.c:282` sets `grid[i].soildepth=20` unconditionally. Plant-available mm = `whc_nat[l] × soildepth[l]`
  (the C's own `whcs`, `soil.h:222`), where `whc_nat` is the patch-ensemble-mean **fraction**
  (`soilpar_output.c:42`) — read it, don't port the pedotransfer. It is **monthly, time-varying** (soil-carbon
  driven) and **`-DPERMUTE`-nondeterministic between runs** (1.6e-4 relative in layer 0, global vs single-cell).
- [VERIFIED] **`beta_root` / `D95max` / `D95` are three different `ind` columns, all in cm.** `beta_root` is the
  C's real root-profile parameter (`new_tree.c:230` → `getrootdist.c`); `D95max` the sampled trait; emitted
  `D95` the rootdepth-limited realized depth, recoverable as `R_cm = ln(1−(1−β^D95)/0.95)/ln β`. Tree test is
  **`D95max > 0`**, never a `Type` number (ids differ by biome: Hainich {1,2,3,4,5,8}, Sahel/Amazon {0,7}).

### F_diff (fast core) — what's validated vs the C oracle (Hainich)
- [VERIFIED] Gradient gate: Enzyme reverse **and** ForwardDiff match FiniteDifferences to ~1e-11 for
  d(annual NPP)/dx through the full 365-day rollout incl. the λ ci:ca Newton solve; water closes ~1e-12.
- [VERIFIED] Level gaps closed step-by-step to the C binary: multi-individual canopy closed the GPP level
  (annual ratio → ~1.06); coupled conductance↔carbon closed transpiration (→~1.02); self-computed NPP
  calibrated via two faithful `npp_tree.c` fixes (growth-resp floor `βgrowth=50`; phen-gated fine-root
  maintenance) → annual NPP +663 (C 507 in-model; CUE 0.512, C ~0.46). Residual ~+7–17% is an inherited
  GPP-phenology **level** offset, not a respiration bug; daily correlations r ≈ 0.98–0.998.
- [VERIFIED] NN-hook training (Vcmax `:vm` + λ) via the extension: Zygote (single-rep) and **Enzyme reverse
  (canopy/cell/multi-year)** gradients match FiniteDifferences (max rel err 1e-8…1e-10); recovery losses
  >96–99%. Cell GPP annual ratio 1.093 → 1.010 with `:vm,:λ`. The single-representative Vcmax lever only
  partially closes the level and degrades daily shape — the residual is **light/structure-limited**.
- [VERIFIED] Prognostic canopy: pipe-model invariant to 3e-16 over 272 trees; carbon conservation exact;
  multi-year rollout tracks C tree height (9.34 m yr-1 vs C 9.344) with no blow-up.
- [VERIFIED] **Grass thread CLOSED as faithful** (§20→§26.2 in the archive): the apparent ~2–3× grass-NPP
  overshoot was a **reference-basis artifact** — against the C's own newly-built daily grass GPP/NPP,
  aggregate ΣF/ΣC=0.95, mean per-year 0.98, CUE 0.55–0.60 matches. The fix that mattered was per-PFT grass
  **phenology** (grass was getting beech GSI), plus a photosynthesis **demand-gate** + grass
  **establishment**; these are the coupled-rollout **default** now (tree-only paths byte-identical). One
  residual remains — see §5 water-supply.

### Scoring a RECURSIVE emulator (cross-cutting method; ADR 0054, line M)
- [VERIFIED 2026-08-05] **Never score a free-running rollout without also running the TEACHER-FORCED arm.**
  Component S's count DRF takes `n_prev` as a feature, and in the **training table** `n_prev` is the C's OWN
  previous `n_living` (`build_slow_runtime_table.py:572`) — never a prediction. A free rollout feeds its own
  output back, so it is off that basis by construction and **integrates** any one-step bias. Measured across
  the five coupled biome cells: overwriting `s.n_prev` with the C truth each year (a driver-level write to a
  public mutable field — no library change) removes **59–72 %** of the total coupled count error in *every*
  cell and flattens a monotone drift (boreal 1.12→1.74 becomes a flat 1.12–1.17); the per-year model then sits
  at **0.2–3.9 seed1-vs-seed2 noise floors**. Free-running error alone would have indicted the count model
  for what is a one-step bias compounded by an unanchored recursion (worth ×1.26–1.53 over nine steps =
  2.6–4.9 %/yr; the rest of the total excess is the year-1 level offset) — a completely different fix.
  The arm generalizes to any AR-conditioned emulator here (S's rollouts, O's online runs), and it also
  confounds resilience metrics: an unanchored recursion manufactures autocorrelation and slow recovery, so
  run both arms in the M4 shuffle test. Ready-made: `scripts/biome_slow_oracle_probe.jl::run_cell(k; teacher=true)`.
- [VERIFIED 2026-08-05] **The noise floor is the only honest scale, and watch its denominator.** Report the
  absolute error next to the ratio: Sahel SLA reads **7.9 floors** but is a 4.6 % error (floor 0.0002), while
  the Amazon count floor is **29 % of the mean** because the cell carries only 4.7 trees per patch.

### E (energy) — Hainich + 5-biome + the P2 tower validation (ADR 0072)
- [VERIFIED] Closure to machine precision (13,824 cases; ForwardDiff-vs-FD; Float32); demo daily 1.4e-14,
  biome ≤3e-14 W/m²; Monin–Obukhov aerodynamic identity ~3e-11. Emergent climate-correct Bowen ordering
  (tropical LE-dominated ~0.10; semi-arid/mediterranean H-dominated; boreal low-flux; 2018 drought 0.89).
- **[VERIFIED 2026-07-28, line E, ADR 0072 — this REPLACES the former `[ASSUMPTION]`; the P2 gate has run.]**
  Experiment A (the closure alone: tower forcing **and the tower's own LE**, so F's ET error is excluded —
  `FToE` hands E `le` already formed as λ·ET, hence **E's own outputs are T_skin / H / G, not LE**), 497 936
  half-hours at 4 PLUMBER2 sites: **Rn VERIFIED** (R² 0.986–0.996, bias +1.95…+10.2 W/m² under the towers' own
  albedo) · **T_skin VERIFIED where observable** (daily RMSE 1.41–1.97 K, R² 0.76–0.95 at AU-Tum/AU-ASM/AU-Rob;
  **not at Hainich** — no `LWup`) · **H verified in the MEAN only** (bias +6.4…−19.2 W/m², **76.4 % of DE-Hai
  daily means inside PLUMBER2's own ±40.9 W/m² band**, but daily R² 0.125–0.778 and **nocturnal R² −1.0…−5.6**).
  Named failure mode: the closure runs **1–2 K too cold at night**. Method note: half-hourly H R² (0.647) is
  **inflated by the diurnal cycle** — quote the daily number. `stab_amp = 0.75` is **too weak** (sweep monotone
  to 0.9; ON still beats OFF at night, 37.0 vs 41.7 W/m² RMSE) — retune is an integration point with M, and the
  monotonicity points at the bounded-tanh *form*. Frozen as a CI gate in `energy_closure_tests.jl`.
  **Data trap this exposed:** PLUMBER2's `Qle_cor`/`Qh_cor` can be **≈0 garbage rather than a fill value**
  (DE-Hai 2010–2012, where the uncorrected `le` is all-NaN) — always require the UNCORRECTED `le` to be finite
  too, or the closure gets fed LE ≈ 0 and its H bias inflates (+39.8 vs +6.4 W/m² at DE-Hai).
- **[VERIFIED 2026-07-28, line E, ADR 0073 — SUPERSEDES ADR 0072's *diagnosis* (items 4 + 6); its measured
  verdict above still stands.] The nocturnal-H failure is a ground-heat TIMESCALE error, not an aerodynamic
  one.** `H` is the **exact residual** `Rn_m − LE − G_m`, so its error obeys *identically*
  `ΔH = ΔRn − ΔG + ε_obs` (`ε_obs = Rn_o − LE − H_o − G_o` = the tower's own non-closure) — and **`g_a` is in
  none of those three terms.** Measured: the closure's nocturnal `g_a` is within **0.7 %** of DE-Hai's
  measured-`u*` value; substituting the measurement makes night H **worse at all 4 sites**; a **100× `g_a`
  bracket** never reaches positive nocturnal R². ⇒ **Do NOT retune `stab_amp`** — its monotone sweep was bias
  cancellation, and it is **withdrawn as an E→M integration point**. The mechanism is
  `G = λ_g(T_skin − t_soil)` with a τ=30 d EWMA reference: sd(`G_m`) is **5–7×** sd(`G_o`) at the forest sites
  and **88 %** of DE-Hai's night H bias is `ΔG`. **`run.jl:93` calls `solve!` ONCE PER DAY**, and at that
  native step three independent lines give **`λ_g ≈ 1.0`, not the 7.0 default** (implied fit 0.83–1.10 at all
  4 sites; it reproduces the observed daily sd(`G_o`) 4.3–6.3 W/m²; daily H R² **0.03 → 0.64** DE-Hai,
  **0.33 → 0.74** AU-ASM). **`lambda_g` is now the live E→M integration point** (no default changed;
  `SEBEnergyClosure(params = SEBParams(lambda_g = 1.0))` works today). **Reference-basis limit:** mean
  nocturnal `ε_obs` is **−62.3 / −47.5** W/m² at AU-Tum / AU-Rob ⇒ **those towers cannot score a closing
  model's nocturnal H at all** (they stay valid for `T_skin`); DE-Hai closes (−0.32) and is the site to tune
  against. Nocturnal R² > 0 is **not** reachable by any `λ_g` in this form — that needs a force-restore /
  two-layer soil scheme + canopy heat storage, which **bounds line O's sub-daily online coupling**.
- [VERIFIED 2026-07-28, line E, ADR 0070] The **observational reference now exists on disk**: PLUMBER2 v1-0,
  9 sites (DE-Hai + one tower per biome slot + 4 OzFlux), `config/paths.yaml` `data.energy_reference*`;
  re-stage with `scripts/fetch_plumber2_sites.py` → `scripts/validate_e_plumber2_load.py` (skill
  `plumber2-reference`). The NCI THREDDS `ks32` collection is **anonymously readable from the PIK login node**
  (general HTTPS egress works — zenodo / ICOS / fluxnet.org / NCI all reachable; only GitHub-HTTPS-for-git is
  the blocked case). Observed daytime Bowen reproduces the 5-biome ordering (tropical 0.30 → semi-arid 4.57).
- [VERIFIED 2026-07-28, line E, ADR 0071] **The two forcings E needs are sourced and mapped**: daily `sfcwind`
  [m/s] + `ps` [Pa] from ISIMIP3a obsclim **GSWP3-W5E5** (the same family as the run's own tas/pr/rsds/lwnet/
  huss; the raw SSP370 GCM set has `sfcwind` but **no `ps`** ⇒ future psurf still open). Remapped onto orderA
  cells by `scripts/remap_wind_psurf_cells.py`; committed fixtures `test/testitems/references/wind_psurf_
  <biome>.csv`. **The lat/lon ↔ orderA mapping is now PROVEN**: obsclim `tas` at the cell's lat/lon vs the
  model-grid `temperature_test.clm` agrees to `max|Δ| = 0.000 °C` over 365 days at all 5 biome cells — reuse
  that route (`grid.nc cellid → (lat,lon) → source axis`, exactness-asserted) for ANY new per-cell input
  (skill `obsclim-cell-remap`). Hainich 0.5° cell vs the DE-Hai tower: wind **−10.1 %**, psurf **+1649 Pa**
  (cell mean ≈143 m below the tower) ⇒ score tower fluxes with TOWER forcing, not grid forcing. Feeding the
  coupled driver is an **open integration point with line M** (`src/run.jl`).
- [VERIFIED 2026-07-28] **T_skin is NOT observable at Hainich**: PLUMBER2's FLUXNET2015/LaThuile files carry no
  `LWup` (only `SWup`); the OzFlux files do ⇒ T_skin validation is biome-analogous (AU-Tum/AU-ASM/AU-Rob;
  AU-How suspect, no boreal source). Two loader traps: PLUMBER2 `_FillValue = -9999` **leaks through
  `np.asarray()`** (masked array → use `np.ma.filled(x, np.nan)`), and a `*_qc == 5` flag in the *Flux* files
  marks data left **MISSING**, not gap-filled.

### S (slow) — offline only
- **[VERIFIED 2026-07-31] The ssp370 `random_seed2` GROUND TRUTH IS A BIT-IDENTICAL COPY OF SEED1 — there is
  no independent second realization of ssp370 (ADR 0038).** `ssp370/.../transient_2020_2100_npatch25_random_seed{1,2}/output/ind_2020_2100.csv`
  are both **193 097 583 638 B** with equal md5 on 1 MB blocks at MB 0 / 30000 / 120000. Cause: the seed2
  config sets `"random_seed": 2` but its `restart_filename` points at the **historic seed1**
  `restart_2019.lpj`, and under `-DFROM_RESTART` the per-cell RAND48 state is restored from the restart, so
  the seed setting is **inert**. The historic pair IS genuinely independent — each config reads its own
  *relative* `restart/restart_1999.lpj`, and those files differ in size and at every block sampled.
  **Why this is cross-cutting:** any noise floor / ceiling / `%GAP` built from it is FABRICATED (`floor_r ≡ 1`
  ⇒ ceiling ~0.998) and raises **no error**; the `seed1-basis ≥ 0.99` check compares a table to the parquet of
  the *same* seed and reads 1.000, so it is structurally blind. `scripts/noise_floor_vs_emulator.py` now
  ABORTS on bit-identical per-cell medians (self-tested both ways, job 1648005). A real ssp370 seed2 needs its
  own restart lineage, not a re-run of the existing config. Only `historic` has a usable seed2 —
  so **criterion 1's `%GAP` and criterion 4's `r_center` are NOT computable for the pooled/ssp370 artifacts.**
- [VERIFIED] Sibling offline S emulator at `/p/projects/open/Jamir/emulator`. Published noise floor
  {Height 0.020, agb 0.113, npp 0.062, LAI 0.025} — ~11% cell-mean agb noise floor is the yardstick.
  PFT types 0–6 = trees, 7–9 = grass. S is **not differentiable** and stays out of the gradient loop (ADR 0014).
- **[VERIFIED 2026-07-28] The Component-S training population WAS truncated; fixed — ADR 0031.** Every
  `build_slow_*.py` selected `TREE_TYPES=[1,2,3,4,5]`, but `Type` is the 0-based `pftpar` index and **ids 0–6
  are all seven tree PFTs** — so id 0 (tropical broadleaved evergreen) and id 6 (boreal larch) were dropped:
  **32.5 % of 197.7 M survivor tree stems, and 9 011 of 54 020 tree-bearing cells (16.7 %) invisible** (the
  tropical belt + Siberian larch). Provenance = a stale sibling `configs/config.yaml`, never an ADR. **Now ONE
  imported constant** (`lpjmlfit_emulator.data.TREE_TYPES`; `features.py`, `config.yaml` and every builder
  import it — never re-declare it). Hainich has only ids 1–5, which is why all single-cell gates stayed green.
  **Every "global" S number published before 2026-07-28 is on the ids-1..5 population** and is superseded by
  the `t7` artifact generation, not restated. Measured: the historic copula table goes 133.5 M → **197.8 M
  stems** / 45 072 → **54 058 cells**, and counts survive intact (every count-DRF metric within ≈0.003 R²).
- **[VERIFIED 2026-07-28] A degenerate-denominator feature must copy the RUNTIME's guard, not floor the
  divisor** (ADR 0031/0032; the general lesson). The S table computed `growth_eff = applied_npp/max(lai,EPS)`
  with `EPS=1e-6`, so a joined `LAI_STAND == 0` became `applied_npp × 1e6` (max 1.19e9). Both the Julia runtime
  (`fast.jl:369` `leaf_area > 0 ? applied/leaf_area : 0`) and the C oracle (`mortality_tree_ind.c:95`) return a
  *guarded* value instead of dividing — so matching them is the fix, and there is no policy choice to make.
  Two durable corollaries: (1) **coverage guards structurally cannot catch this class** — the feature tables are
  complete, so a degenerate zero is *present*, not missing (assert the feature's MAX instead); (2) **there is
  exactly ONE `cell_year_{soilmoist,lai}` table per scenario and it is seed1-derived**, so joining it onto a
  **seed2** `ind` parquet is a cross-seed join (0 affected groups in seed1 vs 21 501 in seed2 — that was the
  "unexplained" asymmetry). A seed2 table's `Xc` can never be fully runtime-consistent; fine for the ADR-0030
  floor, which reads `Y` only.
- **[VERIFIED 2026-07-28] Before arguing about AGGREGATION, check the two sides are the same QUANTITY
  (ADR 0035, S1d — the general lesson, and it cost a milestone's worth of mis-scoping).** ADR 0034 diagnosed
  the S `soilmoist` train/inference shift as annual-mean-vs-year-end. It was not: the training column reduced
  the C `swc` output = **total water over SATURATION capacity** (`update_daily.c:411`) while the runtime fed
  `state.w` = **plant-available water over WHC**. Two different variables that happen to overlap numerically
  (Hainich 0.84–0.87 vs 0.79–1.00), which is exactly why an aggregation story looked like it explained the
  gap — and no time re-reduction of `swc` could ever have closed it. `swc` is **not invertible** back to `w`
  (needs `wsats`/`wpwps`, never emitted); the one C output carrying `w` is `rootmoist` (top 1 m). Second
  corollary from the same milestone: **"quantity X is not reconstructable from the output" is a claim to
  re-derive, not to inherit** — the per-patch stand LAI *was* recoverable from the 29-col `ind` all along
  (`LAI` + `fpc_ind` carry the crown area), despite a skill and a builder docstring both asserting otherwise.
  Mechanics + the exact formulas: CLAUDE.md §3.
- **[VERIFIED 2026-07-28] How to score a stochastic-truth emulator (ADR 0030).** A seed1-vs-seed2 per-cell
  correlation is a *realization-vs-realization* r, NOT a predictor ceiling: with `m = μ(env)+δ(RNG)` and a
  prediction of reliability `rel_P`, the reachable ceiling is `√(rel_P·rel_Y)` where `rel_Y` = the two-seed r,
  and `r_center = emu_r/ceiling`. Always also report `sd(pred)/sd(truth)` (a correlation is scale-blind — the
  copula reproduces only 0.55 of the true between-cell Wooddens spread), and gate the comparison with a
  same-population cross-check (`seed1-basis ≥ 0.99`). Split-half (Spearman-Brown) separates finite-sample
  noise from trajectory divergence: here 0.978–0.999 vs a floor of 0.694–0.964 ⇒ **trajectory divergence**.
- **[VERIFIED 2026-08-05] A parameter adopted from an upstream model is tuned for THAT model's timestep —
  check the relaxation number before trusting it (ADR 0074, line E).** For any prognostic reservoir, compute
  `dt·(Σ conductances)/(thickness · heat capacity)` at *our* step. MITgcm/SpeedyWeather's soil top-layer
  `z1 = 0.2 m` is for a minute-scale model; at the daily step `run.jl:93` actually runs it is **1.125**, so the
  layer equilibrates within one step and the flux it drives degenerates into a day-to-day *difference* of the
  driving temperature (measured: daily G R² −2.8, sd 2.2× observed). The scheme looked mediocre for that reason
  alone until the thickness was swept. Applies to any reservoir F/E/O adopt from an upstream LSM or GCM, and it
  is separate from numerical *stability*: this scheme is stable at all these values, just unresolved.
  Corollary, same ADR: **a flux diagnosed at the start of a step must be compared against the pre-step state** —
  reading the reservoir after the update is off by exactly `conductance × Δstate`.

---

## 4. Frozen decisions — pointer + the load-bearing constraints

**Single source of truth: [`docs/decisions/README.md`](docs/decisions/README.md)** (29 ADRs, with per-line
number blocks). This file no longer duplicates the index — that duplication was a merge-conflict source and
drifted out of order (ADR 0029). ADRs are **immutable once accepted**; supersede, don't edit.

The subset that constrains *any* line's work — violating one of these silently breaks the model or the repo:

| ADR | Constraint you must respect |
|---|---|
| 0003 | **Flux-then-integrate** carbon conservation — fire + establishment are IN the budget (`ΔC = NPP − Rh − firec + flux_estabc`) |
| 0004 | **Constant-CO₂ regime** — CO₂ is not a feature and not a projection axis; OOD means warming/precip at fixed CO₂ |
| 0014 | **Runtime `[deps]` stays EMPTY** — AD/ML/coupling deps are `[weakdeps]` + extensions; Aqua enforces it |
| 0018 | **Growth-ownership split** — F_diff owns representative-individual carbon growth; S owns distribution + demography |
| 0020 | **Component S is FLUX-DRIVEN**, not climate-equilibrium — condition on F's delivered fluxes + AR state + slow boundary; this-year raw climate is dropped |
| 0023 | **Train/inference consistency is load-bearing** — the runtime feature vector and the training table must match exactly (a silent mismatch is the worst failure mode here) |
| 0028 | **Branch + worktree per line**, self-merge on green branch CI (supersedes 0013's main-only) |
| 0029 | **Per-path line ownership + frozen cross-line contracts** — don't edit another line's exclusive paths |
| 0090 | **CI is PATH-FILTERED — most commits trigger NO gate** (owner decision): a gate that does not trigger reports **no check-run**, so polling for `test (lts)` hangs forever; derive the expected set from `git diff --name-only origin/main...HEAD`. Opens the 0090–0099 integrator block (0001–0029 exhausted) |
| guardrail 4 | **Opt-in, default byte-identical** — new physics leaves every committed baseline and the AD trainer unchanged until deliberately enabled |


**Reuse posture (steering reversal):** reuse is now the **default**; reimplementation must be justified in
an ADR. Targets: Terrarium (coupling substrate for P4, SEB cross-check), LPJmL-hybrid-photosynthesis
(differentiable-λ, MIT, done), NeuralCrop (methodology; **CC-BY-NC — code is a blocker**, method-only or
cite it — CC-BY-NC allows the research use we do), LPJ_resilience (reimplement from the paper; no licence). **Reuse of the TUM-PIK-ESM + LPJmL-FIT
models is AUTHORIZED — ADR 0081; cite, don't analyse.**

**Licensing — CLOSED, do not reopen (ADR 0081, owner decision 2026-07-28).** The owner is a member of
**both** the LPJmL-FIT group and **TUM-PIK-ESM** (which hosts SpeedyWeather.jl / Terrarium.jl /
LPJmL-hybrid-photosynthesis) ⇒ **reuse those models freely; raise no licence question and do not re-audit
upstream licences.** ADR 0080 (the good-faith basis + the verified upstream register) and ADR 0081 (the
owner's decision) are the complete and final record. **The one standing obligation is TRANSPARENT
CITATION** across four surfaces kept in agreement: `docs/third_party_licensing.md`, `CITATION.cff`,
`docs/src/refs.bib`, and source-file headers (skill `reuse-citation`). **NeuralCrop.jl is usable as well** —
CC-BY-NC permits non-commercial use and this is research; cite it and move on.

---

## 5. Frontier — what remains, and which line owns it

**Per-line detail (milestones, gates, NEXT) lives in `lines/<X>/STATE.md`** — see the §0 router. This section
is only the cross-line map, so it stays true no matter which line reads it.

| Order | State | Line | One-line status |
|---|---|---|---|
| **P1** S in the coupled loop (the novelty) | ✅ **DONE** | — | flux-driven S runs coupled, carbon-conserving ~1e-12 gC; ADR 0018→0027 |
| **P2** E vs observations | ⬜ open | **E** | data-bounded: no PLUMBER2/FLUXNET on disk; `sfcwind`/`ps` not model-ready (cross-grid remap) |
| **P3** multi-cell generalization | 🟡 half | **M** (+**S**) | OFFLINE S generalizes globally; the **coupled** run beyond Hainich is F+E-only (`slow=nothing`); resilience battery is 4 stubs |
| **P4** online / SpeedyWeather | ⬜ open | **O** | zero code; Terrarium + `speedy_*_land.jl` templates on disk; **licensing basis now in place (ADR 0080)**; O5 needs M1/M2 |
| **P5** reuse + licensing | ✅ **DONE + CLOSED** | **O** | ADR 0080 (basis) + **ADR 0081 (owner closes it — reuse authorized, he is in both groups)**. No residual. Obligation = transparent citation only |
| **P6** nitrogen limitation | ⛔ gated | — | **do not start before the owner's "(c)" discussion** |

**The two `[VERIFIED]` global results that anchor everything** (don't re-derive these):
- **ADR-0020's falsifiable test PASSED:** flux-conditioning beats climate-only **2.35×** on the warm+dry OOD
  holdout (ood R² 0.76 vs −0.16, `scripts/flux_ood_experiment.jl`). The climate-only `DirectEmulator` is
  retained ONLY as this benchmark.
- **The global offline S generalizes across cells** (K-fold-BY-CELL, 45009 cells, real features): counts
  per-cell-mean **r²=0.9994 — AT the seed1-vs-seed2 noise floor**; pooled+transient held-out-BY-SCENARIO
  **R²=0.9847** (an unseen climate regime); trait pooled marginals KS **0.004–0.015**.
  Artifacts `*_pooled_w20.{drf,rcop}` on `/p/tmp` (DVC); the committed `.drf`/`.rcop` are the Hainich demo.

**The one open scientific gap worth naming here** (line S owns it): trait **per-cell medians** have model
headroom — per-cell-median r SLA 0.87 / minwscal 0.78 / D95max 0.74 / **Wooddens 0.52**, against a
seed1-vs-seed2 floor of **0.90–0.97** ⇒ the signal is **learnable, not RNG-limited**. Cause (not a bug): the
copula conditions on flux+boundary and deliberately excludes stand-state (ADR 0025).

**Still true across all lines:** F_diff and the coupled loop are **C-validated on Hainich only** — say
"Hainich only" wherever a result is single-cell; the global evidence is the *offline* S.

### Deferred / known issues (fidelity refinements of an already-in-band core — not blockers)
- **[TODO, DEFERRED] Per-PFT competitive grass water-supply** (§26.4): the 2018 grass drought-amplitude
  residual is a genuine water-supply gap — `daily_step_canopy` runs one stand-level FPC-weighted `wscal`
  (tree-dominated, saturates near 1) with no competitive per-layer depletion, vs C's per-PFT `wscal` +
  sequential `aet_cor` cap. **Deferred behind the `FluxHooks` learned lever** because `-DPERMUTE` makes a
  faithful port non-differentiable/non-deterministic and per-PFT `wscal` is half-degenerate
  (`EMAX_ANGIO=EMAX_GRASS=10`, shared `beta_root=0.8`). Design: `docs/water_supply_perpft_design.md`.
- **[TODO] `sapwood_bg` prognostic growth**: the below-ground root-sapwood pool is added but **static-seeded**
  (opt-in, default byte-identical; in-model CUE 0.512→0.497). Finishing it (C_LATERAL pool growth +
  carbon-debt loan in `grow_individual`, the Enzyme SoA thread, flip the seed on + regenerate the CUE ~0.497
  and coupled/decadal baselines) closes only ~40–50% of the 0.51→0.46 CUE gap. Design: `docs/sapwood_bg_design.md`.
- **[TODO] Lift the Enzyme pin / 1.11 canopy guard** when a fixed Enzyme ships (still blocked upstream on
  0.13.187 / Julia 1.11.7; a 0.14 migration is higher-risk).
- **[TODO] Lift the `JET` pin** (`JET = "0.9, 0.11"`, `test/Project.toml`) by migrating `test/jet_tests.jl` to
  JET 0.12's replacement scoping API. `[VERIFIED 2026-07-28]` JET **0.12.0** removed the
  `target_defined_modules` configuration that `jet_tests.jl:6` passes ⇒ `JETConfigError` ⇒ `test (1)`
  (Julia 1.12) errored **repo-wide** on a fresh resolve — reproduced on line/M `693322fa` (job 90278705919,
  docs+tests-only diff) and line/O `11ef8d89` (job 90275445875), while `test (lts)` stayed green because JET
  0.11+ needs ≥1.12 so 1.10 resolves 0.9.20. Second instance of the CLAUDE.md §5 "CI resolves deps fresh ⇒ a
  missing `[compat]` absorbs a breaking bump" class, after Enzyme 0.13.189. **Two lines pinned it
  independently and concurrently** (`47c6407a` from M, `51529464` from E) — identical text, so it merged to a
  single `[compat]` entry, but that is the clearest sign yet that a repo-wide dep break wants ONE integrator
  action, not four parallel ones.
- **[TODO] Owner actions**: ratify ADR 0018; the "(c)" N-track discussion; close stray Dependabot PRs;
  the `eval`-filename allow decision. (`LICENSE` is NO LONGER tracked here — ADR 0081 closed it.)

---

## 6. Pointers (don't duplicate here)

- **Environment / build / test / C-binary / CI runbook** → `CLAUDE.md` (+ `config/paths.yaml` for paths,
  `config/hpc_slurm.yaml` for SLURM). Skills in `.claude/skills/` automate the mechanical loops.
- **Source map** (`src/` + `ext/`) → `CLAUDE.md` §7. In brief: `fdiff.jl` = the differentiable daily core
  + canopy rollout + allocation/growth (`grow_individual`, `rollout_canopy_years`; `annual_step!` lives in
  `components/fast.jl`); `conservation.jl` = softmax/flux-then-integrate/budget residuals; `interface.jl` =
  the S↔F↔E I/O contract; `run.jl` = the coupled loop (+ opt-in `climbuf=`); `components/slow.jl` = S
  (`DemographicSlowEmulator` Tier-0 + `FluxDrivenSlowEmulator` Tier-1 + `RecruitCopula`); `climbuf.jl` = the
  online transient boundary; `components/energy.jl` = `SEBEnergyClosure`; `ext/FDiffTrainingExt.jl` = the NN-hook trainers.
- **Deep dives**: `docs/phase1_p3b_water_closure.md`, `docs/phase2_slow_emulator.md`,
  `docs/phase3_fdiff_cbinary_validation.md`, `docs/sapwood_bg_design.md`, `docs/water_supply_perpft_design.md`.
- **Session narrative** → **`lines/<X>/JOURNAL.md`** (per line, append-only). The root `JOURNAL.md` holds the
  **pre-2026-07-28 history** and is now the **INTEGRATION journal** — appended only from the `main` worktree
  (single-writer ⇒ conflict-free). Never append line narrative there.
- **Change log** → write a **`changelog.d/<X>-<slug>.md` fragment**; the integrator collates into
  `CHANGELOG.md` (newest on top). **Never edit `CHANGELOG.md` from a line branch.**
- **Parallel-line protocol** → `CLAUDE.md` §9 + ADR 0028/0029; ownership map in ADR 0029; mechanics in the
  `repo-commit` skill. **Per-line state** → `lines/<X>/STATE.md` (§0 router).
- **Archived pre-consolidation docs** → `docs/archive/` (also in git history).
