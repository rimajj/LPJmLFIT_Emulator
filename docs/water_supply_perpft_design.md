# Design — per-PFT competitive water supply (`water_supply_perpft`) (frontier scoping)

**Status: SCOPED, RECOMMENDATION = DEFER (behind the learned-correction lever).** This is the verified
design for closing the 2018 warm/dry-year grass-NPP amplitude residual diagnosed in §26.4 of
`phase3_fdiff_cbinary_validation.md`. Produced by a code-verified deep-read of the LPJmL-FIT C
(`water_stressed.c` + `daily_natural.c`) against F_diff's `daily_step_canopy`. **The read surfaced two
load-bearing corrections to the §26.4 framing — one that SHARPENS the mechanism and one that makes a
faithful port structurally impossible on the AD path (`PERMUTE`).** Read the "Crux / decision-first"
section before touching code: one finding (PERMUTE non-determinism) determines whether an exact port is
even possible, and it is not.

## 1. Goal

§26.2 established that the matched-structure grass flux is faithful in aggregate (ΣF/ΣC 1.10, season
faithful) but overshoots in warm/dry years, most starkly **2018** (C grass NPP 31.5 gC/m²/yr, F_diff 58.9
→ **F/C 1.87, ampR 1.69**). §26.4 diagnosed this as a genuine grass **water-supply** gap: F_diff's
`daily_step_canopy` runs ONE stand-level water balance in which each individual's `supply` is the
**uncapped** potential from a single shared root-zone moisture, so the dominant trees never deplete the
shared soil column ahead of grass. Quantified (§26.4 probes):

| | 2018 | wet-year mean (2010/13/17) |
|---|---|---|
| F_diff per-leaf grass NPP `F/leaf` | **2.591** | 1.578 |
| C per-leaf grass NPP `C/leaf` | **1.386** | (C strongly suppresses in drought) |
| F_diff growing-season stand `wscal` | **0.939** | 0.976 |

`corr(F/C, −wscal) = 0.66`; Probe 3 (rooting lever) closes the overshoot ~6× when the root weight is
concentrated on the top layers (F/C 1.87 → 1.13). "Done" would mean: at matched per-year structure the
2018 grass F/C moves from 1.87 toward ~1.0, the wet-year years stay ~1.0, and **no tree baseline moves**
(the tree GPP/NPP validation of §13–§21 must stay byte-identical). This design concludes that "done" is
**not cheaply reachable faithfully** (§4) and recommends closing the residual with the learned-correction
lever instead (§4.4, §6, §7).

## 2. Current F_diff state (code-verified) — what the stand-aggregate balance computes

`daily_step_canopy` (`src/fdiff.jl:1427-1597`) runs a single shared water balance. The water-supply-
relevant chain:

- **One shared root-zone moisture** (`:1467-1473`): `wr = Σ_l soil.rootdist[l]·rel1[l]` from the SINGLE
  cell `soil.rootdist` — identical for every individual (documented "cell rootdist for all individuals,
  v1", `:1467`).
- **Pass 2, per-individual UNCAPPED supply** (`:1520-1574`): `supply_i = ind.emax·wr·phi` (`:1528`) is the
  potential supply — it is **never reduced by what other individuals already withdrew**. It feeds
  `canopy_conductance(w, eeq, gp_stand, supply_i; wet)` (`:1532`) → `(gc, demand)`; `gc` then drives
  `gpd_raw = hour2sec(dl)·(gc·fpc_i − gmin·fpar_i)` (`:1542`) → the λ-solve (`:1553`) → `agd` = grass GPP
  (`:1558-1559`). So **`supply_i` directly gates grass GPP through `gc`**, and it is the uncapped
  potential.
- **`demand` is faithful** (`canopy_conductance`, `:519-527`): built from the STAND-mean `gp_stand`
  (`:1514`, `:1532`), exactly matching the C's `demand = (1−wet)·eeq·ALPHAM/(1+GM·ALPHAM/gp_stand)`
  (`water_stressed.c:118`) and the final GPP-solve regime (`water_stressed.c:180-194`). The gap is on the
  SUPPLY side only, not demand and not conductance.
- **Aggregate layer cap is MASS-BALANCE only** (`:1576-1577`): `_transpire_total(w1, whcs, rootdist, wr,
  transp_demand_tot, βw)` (`:1390-1403`) caps the TOTAL withdrawal at each layer's water so soil water
  cannot go negative. It runs AFTER every individual's GPP is already fixed (`:1558-1573`) and **does not
  feed back into any individual's `supply_i`/`gc`** — so it never suppresses GPP. This is the precise
  difference from the C's `aet_cor`, which recomputes each PFT's realized supply BEFORE its GPP solve.
- **Stand `wscal` is one FPC-weighted scalar** (`:1586-1587`): `wscal = smoothmin(1, sup_acc/(dem_acc+ε))`
  with `sup_acc = Σ supply_i·fpc_i`, `dem_acc = Σ demand·fpc_i` (`:1533-1534`). Tree-dominated (high FPC),
  saturates at its cap of 1, and feeds ONLY next-day GSI water phenology (`rollout_daily_canopy:1714`
  `water_avail = fl.wscal`, shared across all PFTs). It does not gate GPP within the day.
- **Top-layer over-recharge** (`_infiltrate`, `:812-832`): each rain event refills the top layers to field
  capacity with no competitive depletion, so `wr` recovers between events — a proximate reason the shared
  `wr`/`wscal` barely register the 2018 drought.

Net: F_diff has **no per-individual realized-supply state and no competitive per-layer depletion**. Every
individual sees the same uncapped `wr`-driven supply; the only shared-column feedback is a post-hoc
mass-balance cap that never touches GPP.

## 3. C reference equations (LPJmL-FIT v5.6, individual mode; `water_stressed.c`, `daily_natural.c`)

`daily_natural.c` calls `water_stressed(pft, aet_stand, ...)` **once per PFT** in a loop (`:170-181`),
passing the SAME `aet_stand[LASTLAYER]` array (initialized to 0 at `:109-110`) into every call. Inside
`water_stressed` this array is the `aet_layer[]` accumulator. The per-PFT state:

1. **Per-PFT `wr`** (`water_stressed.c:86-100`): `getrootdist(rootdist_n, pft, ...)`; `wr = Σ_l
   rootdist_n[l]·trf[l]` with `trf[l]` the per-layer transpiration reduction factor (`:90-98`).
2. **Per-PFT supply / demand** (`:106-119`): `supply = pft->emax·wr·pft->phen`; `supply_pft =
   supply·pft->fpc`; `demand = (1−wet)·eeq·ALPHAM/(1+GM·ALPHAM/gp_stand)`.
3. **Per-PFT `pft->wscal`** (`:130-140`): `wscal = (emax·wr)/(eeq·ALPHAM/(1+GM·ALPHAM/gp_stand_leafon))`,
   capped at 1; accumulated into `wscal_mean` (`:140`) → feeds GSI phenology + allocation `lmtorm`. It is
   NOT used to gate the within-day GPP solve.
4. **★ The sequential competitive per-layer availability cap `aet_cor`** (`:153-177`) — the load-bearing
   piece. First `aet = min(supply,demand)/wr·fpc` (`:153`). Then per layer (`:156-170`):
   - `aet_frac` caps this PFT's own per-layer want at the layer capacity (`:158-160`);
   - `aet_tmp[l] = aet_layer[l] + aet·rootdist_n[l]·trf[l]·aet_frac` — the CUMULATIVE withdrawal INCLUDING
     water already taken by earlier PFTs in the loop (`:161`);
   - if `aet_tmp[l]` exceeds the layer's water `w[l]·whcs[l]`, this PFT can take only the RESIDUAL
     `w[l]·whcs[l] − aet_layer[l]` (`:162-167`); else it takes its full want (`:169`);
   - accumulate into `aet_cor`.
   Then the realized supply is RECOMPUTED (`:175-179`): `aet = aet_cor/wr`; `supply = aet·wr/fpc =
   aet_cor/fpc`. This recomputed `supply` drives `gc` (`:180-189`) → `gpd` (`:194`) → the photosynthesis
   solve → `agd` = GPP (`:196-260`). **So a PFT that runs after high-FPC trees in a drought sees the
   shared layers already drawn down (`aet_layer[l] ≈ w[l]·whcs[l]`), its residual → 0, its realized supply
   collapses, its `gc` collapses, its GPP collapses.**
5. **Write-back for the next PFT** (`:263-275`): at the end of the call, `aet_layer[l] +=
   aet·rootdist_n[l]·trf[l]`, then capped at `w[l]·whcs[l]`. This is how the depletion is carried to later
   PFTs in the loop.

**★ PFT ORDERING — this is the crux (§4.1).** The FIT build compiles with **`-DPERMUTE`** (verified: the
active build config `/home/jamirp/lpjml56fit/Makefile.inc:22` `LPJFLAGS`, and every platform template
`config/Makefile.{gcc,intel,icx,mpich,cluster2015,hpc2024}` carries `-DPERMUTE`). Under `PERMUTE`,
`daily_natural.c:89-92` builds `pvec = permute(npft, cell->seed)` and `:168, :179` iterate
`pft = getpft(pvec[p])` — a **Fisher-Yates shuffle** (`src/numeric/permute.c`) on the cell's RAND48 seed,
**re-drawn EVERY day**. So the competition order is randomized daily; there is no fixed "trees-first."
The C's grass suppression is the **order-AVERAGED** (stochastic) outcome over the growing season, not a
deterministic "trees deplete first."

## 4. Crux / decision-first

**★ 4.1 — PERMUTE makes an EXACT port impossible on the AD/deterministic path (the decisive finding).**
The C's competitive result depends on the daily-randomized PFT order (§3). Two consequences, both bad for
a faithful port:
- A **deterministic** F_diff order (e.g. "trees first, grass last") suppresses grass on EVERY day, whereas
  the PERMUTE-averaged C suppresses it only on the (random) days grass draws after the trees — so a
  deterministic port would **systematically OVER-suppress** grass and likely overshoot the correction the
  other way (F/C 1.87 → below 1). The magnitude of this bias is unquantified (§7 probes it).
- Replicating PERMUTE faithfully (daily random order from the RAND48 stream) is **non-differentiable and
  non-deterministic** → it would break the Enzyme/ForwardDiff path AND the `determinism_tests`. So the
  faithful mechanism is structurally incompatible with F_diff's AD + reproducibility contract. Only a
  deterministic APPROXIMATION is feasible, and its fidelity to the PERMUTE-averaged C is unproven.

**★ 4.2 — The mechanism SHARPENS: it is the `aet_cor` cap ALONE, not "per-PFT wscal + aet_cor."** §26.4
bundled the fix as "per-PFT `wscal` + the sequential competitive cap." The source shows the `wscal` half
is **degenerate in this FIT config**: `EMAX_ANGIO = EMAX_GRASS = 10.0`
(`par/pft_lpjmlfit.js:116-118`), grass and mature beech share `beta_root=0.8` (§26.4 CORRECTION), so the
per-PFT `wr` and hence `pft->wscal = emax·wr/demand_leafon` are **≈identical** between grass and trees.
The per-PFT `wscal` therefore does NOT differentiate grass from trees — and it feeds only phenology +
allocation `lmtorm` (§3.3), not the within-day GPP solve. The entire 2018 grass GPP overshoot rides on the **`aet_cor` competitive
supply cap** (§3.4), which recomputes the realized supply feeding `gc`. This is good news for scoping
(one mechanism, not two) but it also confirms the load-bearing piece is exactly the sequential,
order-dependent, AD-hostile one (§4.1, §4.3).

**★ 4.3 — The `aet_cor` cap is squarely ON the Enzyme reverse path AND adds a loop-carried dependency.**
`daily_step_canopy` is folded by `rollout_canopy_years_gpp` (`:2436`), the multi-year GPP trainer whose
per-year GPP is the trained loss (docs §17; `gradient_correctness_tests`, `nn_canopy_training_tests`).
The recomputed realized supply feeds `gc` → `agd`, i.e. it modifies the **differentiated GPP output
directly** — this is not a peripheral pool. And it changes the pass-2 loop structure: today each
individual's supply is INDEPENDENT (pass 2, `:1520-1574`, carries only scalar reductions `sup_acc`,
`dem_acc`, `gpp_tot`). The `aet_cor` cap requires a per-layer `aet_layer` accumulator that each
individual READS (its residual) and WRITES (its withdrawal) for the next individual — a **loop-carried
read-modify-write array with conditional (`min`/branch) updates**. Array mutation per se is tolerated on
the AD path (`_infiltrate`/`_transpire_total`/`_soil_evap` already mutate `Vector{T}` and differentiate
cleanly at 1e-12, docs §17), and `min`/branch caps are AD-safe as branch-selects (as `_solve_leaf_inc`
does). But the sequential aliasing (iteration i's write is iteration i+1's read, inside the
differentiated fold) is a **materially more complex reverse-pass pattern than anything currently on the
canopy AD path**, and an unproven Enzyme risk (the repo's history — `EnzymeNoTypeError` on the kwarg
constructor `:1549`, the `Vector{TreePools}` scatter ENZYME NOTE `:2097-2105` — shows Enzyme is brittle
to exactly this class of change). Every competitive cap also needs an AD-smooth `smoothmin`/`smoothmax`,
which perturbs the trained gradient.

**★ 4.4 — Magnitude: modest, extreme-year-only, and there is a cheaper lever.** §26.4: aggregate
matched-structure grass fidelity is already 0.95–1.10; only warm/dry years overshoot; the stand `wscal`
gap is 0.939 vs 0.976 (Δ0.037). This is a small, extreme-year-concentrated residual on grass, which is
the SUBDOMINANT PFT (the tree GPP/NPP — the validated headline — is untouched by this gap and must stay
byte-identical). Meanwhile F_diff already carries a learned per-individual correction hook (`FluxHooks`,
`daily_step_canopy:1480-1498`) whose feature vector is `[temp, swdown, daylength, apar_i, wr, co2]`
(`:1494`) — it already sees the shared `wr` and per-individual absorbed PAR. A learned Vcmax/λ correction
can absorb a warm/dry-year grass amplitude residual **without** the structural competition port, exactly
as the §26/§26.1 grass level gap was deferred behind the learned lever. Given §4.1 (no faithful port
exists), §4.3 (AD risk on the trained output), and this modest magnitude, the cost/risk does not justify
the structural change.

**★ 4.5 — F_diff's individual ordering does not match the C anyway.** `daily_step_canopy` iterates `inds`
in vector order (`enumerate(inds)`, `:1503`, `:1520`), and that order is whatever the caller's
`tmpls`/`trees0` supplies (`rollout_canopy_years:2295`) — not dominance-sorted and, per §4.1, not
matchable to the C's per-day random order. Even sorting F_diff by descending FPC would be a *choice*, not
a match to the PERMUTE-averaged C.

## 5. Implementation steps (IF, contrary to the recommendation, a deterministic approximation is pursued)

This is the minimum faithful-ish path; it is documented for completeness, NOT recommended (§4).

0. **Quantify FIRST (§7).** Do not touch `src/` until the scripts-only probe confirms a deterministic cap
   lands 2018 grass F/C near 1.0 without over-suppressing, AND is close to a PERMUTE Monte-Carlo mean.
1. **Fix the ordering policy.** Choose a deterministic per-individual order for pass 2 (e.g. descending
   `fpc_i`). Document it as an APPROXIMATION of the C's PERMUTE average (§4.1) — not a match. This is a
   pure ordering of the existing `inds` loop; no struct change.
2. **Add the competitive per-layer accumulator to pass 2** of `daily_step_canopy` (`:1520-1574`): a
   per-layer `aet_layer::Vector{T}` (length `N`, zero-initialized before the loop). For each individual,
   BEFORE its `canopy_conductance` call, compute the C's `aet = min(supply_i, demand)/wr·fpc_i`, the
   per-layer wants `aet·rootdist[l]·rel[l]`, the residual cap against `whcs[l]·rel[l] − aet_layer[l]` via
   `smoothmin`, accumulate `aet_cor`, recompute the realized `supply_i = aet_cor/fpc_i`, THEN call
   `canopy_conductance` with the realized supply. After the call, write the actual withdrawal back into
   `aet_layer` (capped by `smoothmin`). This is a self-contained rewrite of pass 2 — no new struct, no new
   `WaterParams` field except two new smoothing sharpnesses (`βaet`, `βresid`).
3. **Reconcile with `_transpire_total`** (`:1577`): the aggregate mass-balance withdrawal must now be
   consistent with the per-individual `aet_layer` already computed (avoid double-withdrawing). Simplest:
   drive `_transpire_total`'s per-layer withdrawal from the accumulated `aet_layer` directly, or replace
   it with the final `aet_layer` state. Water closure (`precip = transp + evap + interc + runoff + Δstore`,
   asserted by `waterbalance_tests`) must still hold exactly — this is a real regression surface.
4. **Extend `rollout_canopy_years_gpp`** — nothing to add to the SoA arrays (the change is INSIDE
   `daily_step_canopy`, which the SoA path already calls, `:2436`); but re-verify Enzyme reverse vs
   ForwardDiff to 1e-12 through the multi-year rollout (§6). If Enzyme fails on the loop-carried
   accumulator, the whole approach is blocked on the AD path (§4.3).
5. **Grass-gate it (default off).** Wrap the competitive cap behind a `WaterParams` flag (default off ⇒
   byte-identical), mirroring the §26 `grass_demand_gate` discipline (`:215-217`), so the tree path and
   every committed baseline stay byte-identical until the cap is explicitly enabled.
6. **Regenerate baselines + gates.** With the cap ON: the coupled/decadal canopy GPP/NPP baselines drift
   (grass changes → light competition changes → years 2+ drift), so `fdiff_annual_totals` and the
   canopy/decadal baselines need regeneration; the grass drought probes (`scripts/grass_drought_*`) are
   re-run to confirm 2018 F/C → ~1.0; `waterbalance_tests` closure re-verified; a targeted test that a
   drought-year understory grass is suppressed relative to gate-off.

## 6. AD-safety, risk, effort

- **AD path: YES, and on the trained output.** The cap modifies `supply_i → gc → agd` (GPP), the exact
  quantity `rollout_canopy_years_gpp` returns and the trainer descends (§4.3). The loop-carried
  read-modify-write `aet_layer` accumulator is the risky part — a reverse-pass pattern not currently on
  the canopy AD path. Plausible it works (plain `Vector{T}`, `smoothmin` caps), plausible it raises an
  `EnzymeNoTypeError`/activity-analysis failure like the repo's prior struct-in-memory cases
  (`:1549`, `:2097-2105`). **Unproven — must be de-risked before any commitment (§7).**
- **Faithfulness ceiling: capped by PERMUTE (§4.1).** Even a perfectly-implemented deterministic cap
  cannot match the C, because the C's answer is a daily-random-order average. Best case is a plausible
  APPROXIMATION whose bias (deterministic-order vs PERMUTE-mean) is itself unquantified.
- **Regression risk: MEDIUM-HIGH.** Rewrites the core of pass 2 (the GPP-driving supply), touches water
  closure (`_transpire_total` reconciliation, §5.3), drifts every coupled canopy baseline, and carries the
  Enzyme risk. Mitigant: grass-gated + default-off keeps the tree path and baselines byte-identical until
  enabled.
- **Effort:** ~80–150 lines in `src/fdiff.jl` (pass-2 rewrite + `_transpire_total` reconciliation + a
  `WaterParams` flag + 2 sharpnesses) + baseline regeneration + probe re-runs + a full Enzyme
  re-verification. Realistically **2–3 sessions**, with a real chance session 1 (the AD probe, §7) kills
  it. Contrast: the learned-correction lever (§4.4) is ~0 lines of physics.

## 7. Recommended first action

Do NOT start with a `src/` change. Run a **scripts-only quantification + AD-feasibility probe** (no
`src/` edit; `[deps]` stays empty), in this order:

1. **Competitive-cap magnitude probe** (`scripts/`): reimplement the C's `aet_cor` sequential cap OUTSIDE
   `daily_step_canopy`, post-processing (or standalone-recomputing) the per-individual supplies over the
   committed Hainich patch for 2018 and the wet-year mean, under BOTH (a) deterministic trees-first order
   and (b) a Monte-Carlo ensemble of PERMUTE orders (the same Fisher-Yates over random orders). Report:
   (i) does the competitive cap move 2018 grass F/C from 1.87 toward ~1.0? (ii) how far does the
   deterministic-order result overshoot the PERMUTE-mean (§4.1)? If the deterministic approximation
   overshoots badly, or the effect is small, **STOP — the port cannot faithfully close the residual.**
2. **Enzyme-feasibility spike** (`scripts/`): prototype the loop-carried `aet_layer` accumulator as a
   standalone differentiable function (a toy reduction over N individuals × N_layers, with `smoothmin`
   caps and the loop-carried read-modify-write) and run Enzyme reverse vs ForwardDiff. If Enzyme cannot
   type it, the mechanism is blocked on the AD path (§4.3) and only the learned lever remains.

Only if BOTH probes pass — the deterministic cap lands 2018 near the C AND near the PERMUTE-mean, AND
Enzyme differentiates the accumulator — does the invasive pass-2 rewrite (§5) pay off. Given §4.1
(no faithful port exists under PERMUTE), §4.2–§4.3 (the one load-bearing mechanism is the AD-hostile
sequential cap), and §4.4 (a modest, extreme-year, subdominant-PFT residual with a cheaper learned lever
already in place), **the standing recommendation is DEFER: close the 2018 grass amplitude residual behind
the `FluxHooks` learned per-individual water/Vcmax correction, exactly as the grass level gap was
deferred, and revisit the structural port only if the learned lever proves insufficient.** This mirrors
the diagnosis-first discipline that caught the §26.4 mis-attribution and the quantify-first discipline of
`sapwood_bg_design.md` §7.
