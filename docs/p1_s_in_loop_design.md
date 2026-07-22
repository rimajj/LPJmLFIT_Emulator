# P1 design — putting Component S in the coupled loop

Design of record for P1 (the project's novelty: the slow ML trait/size **distribution + demography**
emulator S, run inside the coupled S+F+E loop). Synthesised 2026-07-22 from a 4-architecture design
workflow (minimal-coupled / faithful-machinery / conservation-identity / ESM-forward), each adversarially
critiqued, then merged. Decisions are frozen in **ADR 0018** (growth-ownership split) and **ADR 0019**
(port-not-call, wrap-not-port-wholesale). This doc is the buildable plan; update it as steps land.

## 1. The contract (ADR 0018)

Each year: **S sets population membership + trait distribution** (count N, establishment, mortality, the
trait×size spread); **F_diff advances each representative individual's carbon** (`grow_individual` /
`grow_grass_individual`, unchanged); **flux-then-integrate reconciles and conserves** at the handoff. S is
recursive, demography-only, non-differentiable, outside the AD loop. The whole path is **opt-in** behind
`run_coupled_cell(...; slow=nothing)` — default `nothing` is byte-identical to today.

## 2. Why not the obvious things (ADR 0019)

- **[SUPERSEDED by ADR 0021] Port, don't call Python.** *Original 0019 reasoning: port Python-LightGBM
  inference to pure-Base Julia; training stays Python.* **ADR 0021 replaces this:** S is **trained AND run in
  native Julia** (EvoTrees.jl/DRF + Lux + hand-rolled Julia copula on `Random`), so there is **no port and no
  Python at runtime** — the model that is validated is the model that runs. Python is confined to building
  the training table + running the DirectEmulator OOD benchmark. The learned S ships via a package extension
  (weakdeps), keeping the core's runtime `[deps]` empty (ADR 0014). **Do not build `src/slow_infer.jl`.**
- **Wrap the machinery, don't port the `DirectEmulator` wholesale.** It is climate-only, non-recursive, and
  emits the carbon fan-outs F now owns — using it as-is is the ADR-0018-rejected "regenerate each year" and
  re-introduces the double-count. The native-Julia S reuses only the *design pattern* (a distributional/count
  model + Gaussian copula + Poisson/NB), driven by a recursive, flux-conditioned, demography-only adapter.

## 3. Architecture

**`DemographicSlowEmulator{T} <: AbstractSlowEmulator`** holds: (a) frozen ported models (count booster +
NB `r`, per-PFT 5-axis `ResidualRegressor`s, per-PFT 5×5 copula Cholesky `L`, baked per-cell ECO/STATIC
feature vector); (b) a `PopulationState` = **K persistent cohorts**, each `(id, age, traits{sla, wooddens,
beta_root})` — the demography + non-carbon traits S owns; the carbon **pools stay in
`fc.pools::Vector{FDiff.TreePools}`** keyed positionally to the cohort id (F owns them, single source of
truth); (c) a mutable **`CarbonLedger`** (litter accumulator + per-year flux tallies — the writable sink
`SharedState` scalars cannot provide, since they are immutable in v1); (d) S's own 10-yr rolling
annual-climate ring buffer (5 vars) + N_prev + stand_age + a prev-year distribution summary + a seeded
`Random.Xoshiro`. `Statistics`/`LinearAlgebra` are NOT runtime deps: `mean`/`std` and the 5×5 Cholesky are
hand-rolled.

**Two conditioning channels.** *ML channel*: build the 48-feature vector from S's rolling buffer +
current-year climate aggregate (accumulated daily from `AtmForcing`) + baked ECO/STATIC constants → the
ported boosters/copula predict the target envelope. *Physical-rate channel*: `FToS.growth_eff` drives the
greff mortality rate `mort = mort_max/(1+k_mort·growth_eff)`; `FToS.water_stress`/`soilmoist` + patch
`(1−Σfpc)` gate establishment. **[UPDATED — ADR 0020]** S is now governed as **flux-driven, not
climate-equilibrium**: the Tier-1 ML weights must be **retrained flux-conditioned** (on F's delivered fluxes
+ AR state + slow bioclimatic boundary; this-year raw climate dropped), and the climate-only `DirectEmulator`
is demoted to the **OOD benchmark**. The FToS-conditioned retrain that this design doc had deferred as
"post-P1" is **in scope** — its data task is `docs/slow_flux_conditioning_data_spec.md`, and the flux-driven
S beating the climate-only baseline on the warm+dry OOD holdout is the falsifiable P1/P2 success test.
(Tier-0's physical-rate channel — `FToS.growth_eff`/`water_stress`/`soilmoist` — is already flux-driven; the
change is that the ML channel is retrained on fluxes rather than climate.)

**Count / establishment / mortality.** Ported count model → per-patch mean μ, NB draw (Gamma-Poisson;
Poisson when `r≥1e5`), clip `[0,80]`, ×npatch → target N. Reconcile against realised N as a *difference*:
N-up → establishment (append age-0 cohorts; sapling **carbon** taken from F's/LPJmL's FIXED sapling pools
so S sets only count/traits, not carbon magnitude — ADR-0018-clean; total sapling C debited to
`flux_estabc`, wired onto `FToE.flux_estabc`); N-down → mortality (reduce `nind`, biased to low
`growth_eff`; removed carbon `vegc_full_ind(grown)·Δnind` → `CarbonLedger.litter`). K-cap **merge**: sum
`nind`, mass-weight pools per component, then **re-derive height from the merged pools via allometry**
(never mass-average height — it breaks the pipe model).

**Trait spread.** Per-PFT 5×5 Gaussian copula `{logHeight, Age, SLA, Wooddens, beta_root}`: `z~N(0,I)⁵ →
L·z → u=Φ(z) →` per-axis `ResidualRegressor.sample_u` marginal. Applied ONLY to **recruit** traits at
establishment; survivors keep frozen traits (keeps carbon identity clean); continuing-cohort height stays
F-grown from carbon. `logHeight` seeds recruit initial size and is the reference for the gate-3 comparison.

**Structure derivation.** New `stand_structure_tof(fc)::SToF` (generalises the existing
`stand_structure_toe`): `height` = fpc-weighted mean pool height; `lai` = cover-weighted `Σ nind·leaf_c·sla`;
`fpc` = `Σ FDiff._treepools_fpc`; `z0 = max(0.1·height, 0.01)`; `rootdepth` (D95) from cohort `beta_root`;
`albedo = fc.last_albedo`; `vcmax` a beech `PhotoParams` proxy (no live consumer in F v1, documented).
`SToE` stays the existing 4-field `stand_structure_toe`. These become `bc_f` each year (replacing the
static default at `run.jl:78`).

**Year-end ordering (the crux):** PHASE F (unchanged `grow_individual` per cohort at **OLD** `nind`,
returns `FToS`) → PHASE S (`S.step!` sets target → `reconcile_demography!` applies metered mortality /
establishment / merge fluxes) → atomic membership rebuild → `stand_structure_tof`.

## 4. Carbon conservation strategy (the 1e-6 gate)

The gate is a **veg + litter + establishment mass balance**, NOT an ecosystem NPP−Rh budget (F has no Rh;
`SharedState` is immutable). Order-locked per year:

- **Re-map safety:** `nind` never changes between the `bm/nind` divide and the grown-pool weighting, so
  `Σ_i nind_i(old)·Δvegc_full_ind_i == applied_bm_cell − L_turnover` to machine precision — the ADR-0018
  re-map cannot leak (same `nind_old` divides `bm_inc` out and weights growth back in).
- **Litter routed as the exact residual** `bm_applied − Δvegc_full` per cohort (branch-agnostic: captures
  the abnormal-branch extra leaf shed that the `_turnover_litter` formula omits — verified on real Hainich
  cohorts, `scripts`/probe). Mortality carbon `vegc_full_ind·Δnind` → litter (uses **`vegc_full_ind`**
  incl. `sapwood_bg_c`, closing the leak `vegc_ind` would open on a seeded pool). Establishment sapling C =
  `flux_estabc` (external influx). Merge conserves `Σ vegc_full·nind` exactly (height re-derived).
- **Two assertions to `1e-6·C_scale`:** (A) fixed-N growth reconciliation `|Δ(Σ vegc_full·nind_old) −
  (applied_bm_cell − L_turnover)| ≤ 1e-6` with `L_turnover` measured independently by `_turnover_litter`
  (non-tautological — witnesses that growth conserves into known channels on the normal path); (B)
  total-carbon closure `carbon_budget_residual(npp=applied_bm_cell, rh=0, firec=0, flux_estabc,
  dC=Δ(C_veg+C_litter)) ≈ 0`. Cross-witnessed by the C-oracle veg-C delta at cell 42490.
- **Stagnating cohorts** (`grow_individual` returns unchanged for `bm_net≤0`) contribute
  `applied_bm=0`, `litter=0`; their negative `bm_inc_acc` is reported as a bounded **unapplied-NPP
  diagnostic** (a pre-existing fixed-N F approximation — must not be over-claimed as closed).

## 5. Speed-up (gate 4) — two baselines, both named so the metric can't move silently

The ADR-0018 Option-C fixed-N baseline is **not** the speed target (S *adds* cost there). (a) **Overhead
baseline** (CI-robust): `slow=nothing` vs `slow=DemographicSlowEmulator` over a Hainich decade — assert
`S.step!`+reconcile per-year wall-time below a fixed threshold and a machine-independent work-count proxy
(per-individual `grow_individual` evaluations with K persistent cohorts ≪ the explicit-N ensemble). (b)
**Scientific / horizon-collapse baseline** (recorded off the login node, not asserted in CI): what S
actually replaces is the C-IBM `individual=true` stochastic demography (dozens–hundreds of explicit
individuals × npatch, `-DPERMUTE` competition, per-tree allocation) integrated over a **multi-century
spin-up**; S collapses that to K cohorts + a one-shot climate→distribution map with no spin-up. Report at
**matched gate-3 panel error** (a speed-up that broke fidelity does not count).

## 6. Distribution match (gate 3) — three fixtures, scoped to S-owned axes

Interpret "matches the panel" strictly on the axes S owns (N + traits {SLA, Wooddens, beta_root} + the
size-class weight distribution); Height/agb/npp/LAI are F-derived structure. (1) **Parity** testitem:
pure-Julia `SlowInfer` reproduces the Python `DirectEmulator` count μ, PFT fraction, and a seeded 5-axis
copula draw on a committed fixed feature row to ~1e-6 (isolates port correctness). (2) **Panel** testitem:
coupled S-owned marginals vs committed `references/slow_panel_hainich.csv` by normalised per-axis
quantile-RMSE within `{Height 0.020}` (wider, documented tolerance for continuing-cohort Height, since the
coupled S is recursive while the panel is not). (3) **Oracle** testitem (the load-bearing one): coupled
S+F distribution on S-owned axes vs the LPJmL-FIT C ground-truth Hainich distribution (cell 42490), with
the noise-floor yardstick re-derived for that basis. Discipline: invoke the **residual-diagnosis** skill
BEFORE chasing any miss.

## 7. Implementation plan (each step names the test that proves it)

1. **`_turnover_litter` + `vegc_full_ind`** (`src/fdiff.jl`; do NOT modify `grow_individual`). Test
   `fdiff_litter_closure_tests.jl`: `Δvegc_full == bm_net − (leaf_shed+root_shed)` on the normal branch +
   grass; ledger-residual identity + no carbon creation, branch-agnostic. **[DONE — verified]**
2. **`CarbonLedger` + `handoff_carbon_residual`** (`src/conservation.jl`). Test: synthetic
   establish(+)/kill(−)/merge with a seeded `sapwood_bg_c>0` cohort ⇒ `|residual| ≤ 1e-6`. **[DONE — `carbon_ledger_tests.jl`]**
3. **`grow_annual_accounted!`** (`src/components/fast.jl`) — grows at fixed `nind`, returns `FToS` + grown
   pools + litterfall; keep `annual_step!` as the byte-identical `slow=nothing` path. Test: existing
   coupled/biome tests re-run UNCHANGED (byte-identical guard) + fixed-N litter closure with grass present.
   **[DONE — `grow_accounted_tests.jl`]**
4. **[SUPERSEDED by ADR 0021 — do NOT build `src/slow_infer.jl`.]** The original plan (port a Python
   LightGBM model's inference to a pure-Base Julia GBDT text-walk with a ~1e-6 parity fixture) is dropped:
   S is now **trained AND run in native Julia** (no Python at runtime, no double build). The Julia
   distributional/count model is **EvoTrees.jl** (or a Julia DRF); NN parts (if any) **Lux**; the
   Gaussian-copula Cholesky + inverse-CDF + Poisson/NB sampler stay **hand-rolled Julia on `Random.Xoshiro`**.
   It ships via a **package extension** (weakdeps EvoTrees/Lux) so the core keeps empty runtime `[deps]`
   (ADR 0014). Test: the native model's Gate-3 accuracy (below), a deps-guard (core `[deps]` stays empty),
   and reproducibility under a seeded `Xoshiro`.
5. **`scripts/build_slow_training_table.py` (rescoped from `export_slow_hainich.py`, ADR 0021):** Python's
   ONLY S roles — (a) build + align the training table (the F-flux + mortality-driver features, ADR 0020,
   against the `ind` trait/size distribution) and (b) run the climate-only `DirectEmulator` to produce the
   OOD-benchmark predictions. Commit the aligned table + benchmark predictions to `references/`. No model
   artifact to port; the Julia S trains directly off the table.
6. **`DemographicSlowEmulator` + `reconcile_demography!`** (`src/components/slow.jl`),
   Tier-0 first (constant/physical-rate demography; no ML, empty runtime `[deps]`); replace the erroring stub.
   Test: Gate-2 handoff residual `≤1e-6` on forced N-up / N-down / seeded-`sapwood_bg` + stagnating-cohort
   years. **[DONE — Tier-0; `slow_demography_tests.jl`.** Fixed roster (no append/merge yet); TREE-only
   demography — grass stays F-side (open-risk #8). Residual closes to machine precision (~3e-12 gC ≪ the
   1e-6·C_scale gate). Membership append/merge + the C-oracle veg-C cross-check move to Tier-1.]
7. **`run.jl`**: `stand_structure_tof`; `slow=` kwarg (default `nothing` byte-identical); year-end sequence
   `grow_annual_accounted!`→`reconcile_demography!`→`stand_structure_tof`. Test: byte-identical guard + Gate-1
   (`slow=DemographicSlowEmulator` runs ≥20 yr, all finite, total N changes proving S is in the loop; energy
   closure preserved). **[DONE — Tier-0.** Byte-identical guard is now DIFFERENTIAL: fixed-N F holds tree N
   constant, so the N change is causally S. Needed a fix: `SoilColumn` gained a `soildepth` field for the D95
   rooting-depth in `stand_structure_tof`. Daily climate-accumulation hook deferred to Tier-1 (ADR-0020 ML
   channel).]
8. **Tier-1 wire-up (ADR 0020 + 0021 + 0022 — now in P1 scope). [DONE — v1, 2026-07-22.]** The flux-driven S
   is **trained + run natively in Julia** on the zero-dependency hand-rolled **DRF** (`src/drf.jl`, ADR 0022 —
   *not* EvoTrees; EvoTrees verified as a fallback), conditioned on F's delivered fluxes + this-year patch state
   + the recursive AR count + the baked slow bioclimatic boundary. `FluxDrivenSlowEmulator`
   (`src/components/slow.jl`, in `src/` not an extension since it has no external dep) plugs into the existing
   `reconcile_demography!` interface: the DRF predicts a demographic **target**, and the coupled tree density
   moves toward `target/n_prev` — a UNIT-FREE ratio, so the training-table count ↔ coupled-cohort density gap
   cancels — through the SAME carbon-conserving mortality/establishment machinery Tier-0 uses (conservation by
   construction). **The ADR-0020 falsifiable success test is `[VERIFIED] SUPPORTED` OFFLINE**
   (`scripts/flux_ood_experiment.jl`: on the warm+dry OOD holdout the flux channel beats the climate-only channel
   2.35×, ood R² 0.76 vs −0.16). The in-loop test (`test/testitems/slow_flux_driven_tests.jl`) verifies the DRF
   target drives the demography + carbon conserves (~1e-12) + determinism + Float32. **Still open (v2):** train the
   PRODUCTION DRF on a runtime-consistent feature table + serialize it (the in-loop test uses an in-test DRF); the
   Gate-3 **oracle** testitem (coupled S-owned marginals vs the LPJmL-FIT C ground truth at Hainich) + the in-loop
   OOD win; the annual-statistics `FToS` extension (`docs/slow_flux_conditioning_data_spec.md` §5); the copula
   recruit-trait sampler (traits are still fixed-cohort). Prereq for those: the extended flux-statistics data.
9. **`scripts/bench_slow_speedup.jl` + Gate-4 testitem**: overhead + K≪N structural invariant; the script
   records the wall-time ratios off the login node. **[DONE — structural invariant (fixed K-cohort roster) is
   asserted in `slow_demography_tests.jl`; the overhead/scientific ratios are reported by the script (run via
   `scripts/sbatch_julia.sh`), not asserted in CI.]**
10. **Docs**: ADR 0019 (done), ADR 0020 (done), this doc, MEMORY/CHANGELOG/JOURNAL. Docs build + Runic gate.

## 8. Open risks (carry until closed)

1. Pure-Julia GBDT text-walk fidelity (categorical splits, missing-value default direction, float32 vs 64
   thresholds) must match LightGBM to ~1e-6 — gated by the Step-4 parity fixture + a version string in the
   artifact header.
2. ~~Climate-only trained weights vs the `bm_inc`-aware interface — a documented fidelity gap under novel
   climate/state until an FToS-conditioned retrain.~~ **CLOSED by [ADR 0020](decisions/0020-component-s-flux-driven.md):**
   the flux-conditioned retrain is now the governing spec, not a deferred gap. The residual risk is that the
   flux-driven S must actually *close* the warm+dry OOD gap (else ADR 0020 is falsified) — and that the
   extended Phase-1 data (`docs/slow_flux_conditioning_data_spec.md`) must be materialised first.
3. Gate-3 recursive-vs-non-recursive basis mismatch: the coupled Height marginal may miss the offline
   panel's 0.020 floor with no bug — the oracle testitem (vs LPJmL truth) is the real test; re-derive its
   yardstick; use residual-diagnosis + honest tolerance framing.
4. `SharedState` scalar `litc`/`vegc` are immutable; P1 holds litter in a mutable `CarbonLedger` on S. A
   future need to persist litter in `SharedState` makes the Phase-4 mutable-state refactor a prerequisite
   (flagged, off the P1 critical path).
5. Membership-change plumbing (`fc.pools`/`tmpls`/`inds`/`pft_ids`/`pft_slot`/`pft_states`/`bm_inc_acc`)
   must be rebuilt ATOMICALLY on establish/drop/merge or daily `npp_ind` indexing bounds-errors — dedicated test.
6. Stagnating-cohort unapplied-NPP gap — reported as a bounded diagnostic, not closed (pre-existing fixed-N
   F approximation); the ecosystem–atmosphere budget is not fully closed in v1 — must not be over-claimed.
7. Stochastic NB/copula draws need the seeded `Xoshiro` threaded through S for reproducible coupled runs /
   non-flaky gate-3 assertions.
8. Hainich-only, single-PFT (beech id 3): the S↔F split is asserted only for trees; grass establishment
   stays F-side for P1 (decide grass demography ownership before generalising). Global 7-PFT artifact → DVC/`/p`.
