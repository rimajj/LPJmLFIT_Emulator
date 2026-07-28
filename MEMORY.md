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
| **4 E energy** | ✅ landed, self-contained (ADR 0017) | `SEBEnergyClosure` closes `Rn=LE+H+G` to **1.4e-14 W/m²**; H the residual; Monin–Obukhov g_a stability correction ON by default; coupled Hainich decade emergently reproduces the **2018 drought** (summer Bowen 0.89 vs ~0.2) |
| **5 Multi-cell** | 🟡 offline S done; COUPLED still 5-biome F+E | OFFLINE S generalizes globally (K-fold-BY-CELL, 45009 cells — Phase 2). COUPLED S+F+E runs across 5 biomes but `slow=nothing` (F+E only; energy ≤3e-14, climate-correct partitioning); **not yet** the coupled flux-driven S across cells vs C-truth demography, nor the resilience battery |
| **6 Online / SpeedyWeather** | ⬜ not started | |
| **7 ESM packaging** | ⬜ not started | |

**Remaining project (not done):** the flux-driven Component-S is IN the coupled loop and validated GLOBALLY
**offline** (counts at the noise floor; the OOD win is `[VERIFIED]` 2.35×) — but the **coupled** S+F+E run
beyond Hainich is F+E-only so far (S not yet driven across cells vs C-truth demography); the **trait per-cell
median has model headroom** (esp. Wooddens — richer conditioning, P3); E is **not validated against
FLUXNET/PLUMBER2**; nothing runs online with SpeedyWeather; wind/psurf forcing not sourced. F_diff and the
coupled loop remain **Hainich-C-validated only** — single-cell fidelity is scaffolding, the global evidence
is the offline S.

---

## 3. Verified facts — the load-bearing, durable ones

### Model / data structure
- [VERIFIED] Integration is **daily**; no sub-daily physics except the soil-heat numerical substep. Daily
  output is a **runtime config flag** (`"timestep":"daily"`), never a recompile.
- [VERIFIED] LPJmL-FIT has **no surface energy balance**: ET = Priestley–Taylor equilibrium/demand–supply;
  soil temp uses **air temp** as the top Dirichlet BC; no H, G-as-flux, T_skin, or Rn closure. All of that
  is component E (new physics), validated **out-of-model** (FLUXNET/PLUMBER2 — still to source).
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

### E (energy) — Hainich + 5-biome, no observational validation yet
- [VERIFIED] Closure to machine precision (13,824 cases; ForwardDiff-vs-FD; Float32); demo daily 1.4e-14,
  biome ≤3e-14 W/m²; Monin–Obukhov aerodynamic identity ~3e-11. Emergent climate-correct Bowen ordering
  (tropical LE-dominated ~0.10; semi-arid/mediterranean H-dominated; boreal low-flux; 2018 drought 0.89).
- [ASSUMPTION] LE/H/T_skin are physically plausible but **invented quantities validated only out-of-model**;
  the FLUXNET/PLUMBER2 validation (P2) has **not** happened. `g_a` had been neutral-only until the stability
  correction landed.

### S (slow) — offline only
- [VERIFIED] Sibling offline S emulator at `/p/projects/open/Jamir/emulator`. Published noise floor
  {Height 0.020, agb 0.113, npp 0.062, LAI 0.025} — ~11% cell-mean agb noise floor is the yardstick.
  PFT types 0–6 = trees, 7–9 = grass. S is **not differentiable** and stays out of the gradient loop (ADR 0014).
- **[VERIFIED 2026-07-28] The Component-S training population is TRUNCATED — ADR 0031.** Every
  `build_slow_*.py` selects `TREE_TYPES=[1,2,3,4,5]`, but `Type` is the 0-based `pftpar` index and **ids 0–6
  are all seven tree PFTs** — so id 0 (tropical broadleaved evergreen) and id 6 (boreal larch) are dropped:
  **32.5 % of 197.7 M survivor tree stems, and 9 011 of 54 020 tree-bearing cells (16.7 %) are invisible**
  (the tropical belt + Siberian larch). Provenance = a stale sibling `configs/config.yaml`, never an ADR; the
  correct constant already exists at `python/.../features.py:50`. Every "global" S number so far is on the
  ids-1..5 population / 45 009 cells. Fix = re-derive → retrain → re-validate (integration point with M,
  versioned artifacts). Hainich has only ids 1–5, which is why all single-cell gates stayed green.
- **[VERIFIED 2026-07-28] How to score a stochastic-truth emulator (ADR 0030).** A seed1-vs-seed2 per-cell
  correlation is a *realization-vs-realization* r, NOT a predictor ceiling: with `m = μ(env)+δ(RNG)` and a
  prediction of reliability `rel_P`, the reachable ceiling is `√(rel_P·rel_Y)` where `rel_Y` = the two-seed r,
  and `r_center = emu_r/ceiling`. Always also report `sd(pred)/sd(truth)` (a correlation is scale-blind — the
  copula reproduces only 0.55 of the true between-cell Wooddens spread), and gate the comparison with a
  same-population cross-check (`seed1-basis ≥ 0.99`). Split-half (Spearman-Brown) separates finite-sample
  noise from trajectory divergence: here 0.978–0.999 vs a floor of 0.694–0.964 ⇒ **trajectory divergence**.

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
| guardrail 4 | **Opt-in, default byte-identical** — new physics leaves every committed baseline and the AD trainer unchanged until deliberately enabled |


**Reuse posture (steering reversal):** reuse is now the **default**; reimplementation must be justified in
an ADR. Targets: Terrarium (coupling substrate for P4, SEB cross-check), LPJmL-hybrid-photosynthesis
(differentiable-λ, MIT, done), NeuralCrop (methodology; **CC-BY-NC — code is a blocker**, method-only or
get permission), LPJ_resilience (no license — reimplement from the paper).

**Licensing — RESOLVED by [ADR 0080](docs/decisions/0080-licensing-basis.md) (P5); register + the
before-you-take-a-dependency gate = `docs/third_party_licensing.md`.** `[VERIFIED 2026-07-28]`
**Outbound = AGPL-3.0-or-later**, and it is *forced*, not chosen: it is both what LPJmL-FIT's AGPL-3.0
copyleft requires of a derivative **and** an EUPL-1.2 Appendix "Compatible Licence", so EUPL Art. 5 sanctions
combining with Terrarium/SpeedyWeather (**both EUPL-1.2**, not MIT) — valid whether or not a dependency
counts as a derivative work. **Terrarium's `NOTICE` extends Art. 5 to *any* licence for "normal use of the
Work as a library"** ⇒ taking it as `[weakdeps]` + an extension is clean, so **P4 is unblocked**.
Three tiers, never conflated: **READ** (methods are unprotectable — permitted for all references) ·
**DEPEND** (the P4 mechanism; runtime `[deps]` stays empty, ADR 0014) · **VENDOR** (**not permitted by
default — needs its own ADR**; this is the only tier ADR 0017's "hard blocker" ever applied to, so 0017 is
*annotated, not superseded*, and stands on its zero-deps + v0.1.x drivers). CC-BY-NC ↔ AGPL §7 is
**undistributable**, so NeuralCrop.jl is method-only, permanently.
**[TODO] Owner action — the licence *act* is all that's left:** the repo is **public with no `LICENSE`**
(`license: null` via API; never existed in git history), which grants nobody rights *and* ships an
AGPL-derived patch without AGPL's notices. File `LICENSE` (AGPL-3.0-or-later) + `Project.toml` `license` +
`CITATION.cff` `license:` + README §License (ADR 0080 §4); or make the repo private again as the interim
mitigation. A formal legal review is explicitly **not** a blocker (P5).

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
| **P5** reuse + licensing | ✅ **DONE** | **O** | ADR 0080: AGPL-3.0-or-later outbound, EUPL works as library deps only, never vendored. Residual = the owner *files* `LICENSE` (§4) |
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
- **[TODO] Owner actions**: ratify ADR 0018; **file `LICENSE` = AGPL-3.0-or-later** (ADR 0080 §4 — the
  licensing *read* is done, only the act remains); the "(c)" N-track discussion; close stray Dependabot PRs;
  the `eval`-filename allow decision.

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
