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

- **Port, don't call Python.** Empty runtime `[deps]` (ADR 0014) + offline compute nodes rule out
  PythonCall/CondaPkg and `LightGBM.jl`/`Distributions`. Port *inference* to pure-Base Julia; training stays
  Python. Stdlib (`Random`) is offline-safe.
- **Wrap the machinery, don't port the `DirectEmulator` wholesale.** It is climate-only, non-recursive, and
  emits the carbon fan-outs F now owns — porting it as-is is the ADR-0018-rejected "regenerate each year"
  and re-introduces the double-count. Reuse only ResidualRegressor + Gaussian copula + Poisson/NB count +
  GBDT tree-walk, driven by a new recursive demography-only adapter.

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
`(1−Σfpc)` gate establishment. P1 ships climate-only trained weights (documented gap: the interface is
`bm_inc`-aware, the weights are not yet — an FToS-conditioned retrain is post-P1); `FToS` drives only the
rate channel for now.

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
   establish(+)/kill(−)/merge with a seeded `sapwood_bg_c>0` cohort ⇒ `|residual| ≤ 1e-6`.
3. **`grow_annual_accounted!`** (`src/components/fast.jl`) — grows at fixed `nind`, returns `FToS` + grown
   pools + litterfall; keep `annual_step!` as the byte-identical `slow=nothing` path. Test: existing
   coupled/biome tests re-run UNCHANGED (byte-identical guard) + fixed-N litter closure with grass present.
4. **`src/slow_infer.jl`** (pure-Base): GBDT text-walk, `ResidualRegressor.sample_u`, 5×5 Cholesky +
   Acklam `Φ⁻¹` + rational `Φ`, Poisson/NB (Gamma-Poisson) on `Random.Xoshiro`, artifact loader. Test
   `slow_infer_tests.jl`: parity vs committed Python predictions ~1e-6 + a deps-guard (no
   Statistics/LinearAlgebra/Distributions/SpecialFunctions in runtime `[deps]`).
5. **`scripts/export_slow_hainich.py`** — export the slim PFT-3 artifact (Tier-0 scalar bundle + Tier-1
   boosters/pools/copula/ECO row) to committed `references/slow_hainich_pft3.bin` + `slow_infer_parity.csv`.
6. **`DemographicSlowEmulator` + `PopulationState` + `reconcile_demography!`** (`src/components/slow.jl`),
   Tier-0 first (constant count + fixed copula); replace the erroring stub. Test: Gate-2 handoff residual
   `≤1e-6` on forced N-up / N-down / merge years (incl. `sapwood_bg>0`) + a C-oracle veg-C-delta cross-check.
7. **`run.jl`**: `stand_structure_tof`; `slow=` kwarg (default `nothing` byte-identical); daily
   climate-accumulation hook; year-end sequence `grow_annual_accounted!`→`S.step!`→`reconcile_demography!`→
   `stand_structure_tof`. Test: byte-identical guard + Gate-1 (`slow=DemographicSlowEmulator` runs ≥20 yr,
   all finite, total N changes year-to-year proving S is in the loop; energy closure preserved).
8. **Tier-1 wire-up**: ported GBDT count + copula recruit-trait sampler; ML channel from the rolling
   buffer; `FToS` drives the rate channel. Test: Gate-3 panel + oracle testitems (run residual-diagnosis first).
9. **`scripts/bench_slow_speedup.jl` + Gate-4 testitem**: assert `S.step!` per-year work below threshold +
   K≪N; the script records the two wall-time ratios off the login node.
10. **Docs**: ADR 0019 (done), this doc, MEMORY/CHANGELOG/JOURNAL. Docs build + Runic gate.

## 8. Open risks (carry until closed)

1. Pure-Julia GBDT text-walk fidelity (categorical splits, missing-value default direction, float32 vs 64
   thresholds) must match LightGBM to ~1e-6 — gated by the Step-4 parity fixture + a version string in the
   artifact header.
2. Climate-only trained weights vs the `bm_inc`-aware interface — a documented fidelity gap under novel
   climate/state until an FToS-conditioned retrain (needs `bm_inc`/stress labels on the ground-truth table).
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
