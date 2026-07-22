# Design — tree below-ground sapwood (`sapwood_bg`) + carbon-debt (frontier scoping)

**Status: SCOPED, NOT IMPLEMENTED (a 2–3 session frontier).** This is the verified design for closing the
small remaining tree CUE (NPP/GPP) bias documented in §13 of
`phase3_fdiff_cbinary_validation.md`. Produced by an adversarial-workflow investigation (deep-read of the
LPJmL-FIT C + F_diff, then an independent verify pass); the verify surfaced load-bearing corrections and
open questions, folded in below. **Read the "Crux / decision-first" section before touching code — one
open question (seeding) determines whether the whole change does anything at all.**

## 1. Goal

The C's tree maintenance respiration multiplies the `(root + sapwood_bg)` block by `pft->phen` on the
soil-temperature response (`npp_tree.c:47-51`); above-ground sapwood is un-gated on the air-temperature
response. F_diff carries only 4 carbon pools (`leaf, sapwood, heartwood, root`) and **omits the
below-ground root-sapwood pool `sapwood_bg` entirely**, so it never pays that maintenance term. Net: the
F_diff tree CUE sits at ~**0.51–0.52** vs the C's ~**0.46** (§13; `multi_individual_tests.jl` CUE gate
`[0.42, 0.56]`). Adding `sapwood_bg` + its phen-gated maintenance (and the allocation demand that grows
it, + the carbon-debt loan) moves CUE **down toward the C**. A partially-cancelling simplification exists —
the rare-day leaf respiration `rd` is not conductance-gated in F_diff (the C zeroes it when `gpd ≤ 1e-5`,
`water_stressed.c:196`) — so the two must not both be "fixed" naively (they cancel; see §6).

## 2. Current F_diff state (what's missing) — code-verified

- **`TreePools{T}`** (`src/fdiff.jl:1819-1830`): 10 positional fields `leaf_c, sapwood_c, heartwood_c,
  root_c, height, crownarea, nind, sla, wooddens, is_grass`. NO `sapwood_bg` / `heartwood_bg` / `debt`.
  `vegc_ind` sums leaf+sapwood+heartwood+root; `agb_ind` sums leaf+sapwood+heartwood. (`state.jl:18`
  documents the C's full 7-pool `Treephys2`: `leaf, sapwood, heartwood, root, sapwood_bg, heartwood_bg,
  debt` — F_diff carries only 4.)
- **`autotrophic_respiration`** (`src/fdiff.jl:543-557`): `rmaint = respcoeff·k·gtemp·(c_sapwood/cn_sapwood
  + phen·c_root/cn_root)` — above-ground sapwood un-gated, fine-root phen-gated. NO `sapwood_bg` term.
  Call sites: `daily_step_canopy:1569-1573` (passes `c_sap = ind.c_sapwood·nind`, `c_root =
  ind.c_root·nind`, `phen = phi`), `daily_step:681`, `daily_step_ml:938`.
- **`Individual{T}`** (`src/fdiff.jl:1352-1369`, 16 positional fields): carries `c_sapwood, c_root` for
  maintenance but no `c_sapwood_bg`; built in `individual_from_pools` (`:2184-2193`).
- **`grow_individual`** (`src/fdiff.jl:1898-1974`): ports turnover→allocation→allometry but has NO soil
  geometry in its signature `(alloc, allom, tree, bm_inc_ind, wscal_mean)`, so it cannot compute the C's
  below-ground lateral sapwood demand; `debt` is never formed (carbon-debt off, documented `:1764`).
- **Enzyme SoA path** `rollout_canopy_years_gpp` (`src/fdiff.jl:2387-2457`): carries the evolving pools as
  struct-of-arrays field vectors (`leafcs/sapcs/heartcs/rootcs/heights/crowns`) precisely because Enzyme
  cannot type-analyze a `Vector{TreePools}`. No `sapbgcs` array.

## 3. C reference equations (LPJmL-FIT v5.6, `with_nitrogen=no`, individual mode, PFT 3 beech)

1. **Maintenance** (`npp_tree.c:47-51`): the below-ground sapwood respires WITH the fine root, phen-gated
   on the soil-temperature response, at the (N-poor) sapwood C:N:
   `mresp = nind·( sapwood·respcoeff·k·nc_sapwood·gtemp_air + (root·nc_root + sapwood_bg·nc_sapwood)·
   respcoeff·k·gtemp_soil·phen )`. In F_diff's C:N form: add `phen·c_sapwood_bg/cn_sapwood` to `rmaint`
   (sapwood C:N ≈ 330 — ~11× lower per-gram respiration than fine root; but the pool can be large).
2. **Below-ground lateral demand** (`allocation_tree.c:113 C_LATERAL=0.900, :163, :173-189`):
   `sap_xs_area = sapwood_c / wooddens / height`; per layer accumulate a vertical + lateral demand
   `root_sapwood_layer += (soildepth[l]/1000)·sap_xs_area·root_sum·wooddens
    + (soildepth[l]/1000)·sap_xs_area·rootdist_n[l]·wooddens·2π/C_LATERAL²` (with `root_sum` = cumulative
   root fraction below layer l, decremented by `rootdist_n[l]` each layer; the lateral factor
   `2π/0.81 ≈ 7.76`). Demand `sapwood_bg_inc = max(0, root_sapwood_layer − sapwood_bg_c)`, taken only when
   the pool is already `> 0` (`:206-209`), subtracted from `bm_inc_ind` BEFORE the above-ground pipe-model
   (`:268-280`, carbon-limited: if `bm_inc < leaf_min+root_min+demand`, take only the surplus).
3. **Carbon-debt** (`allocation_tree.c:288-297`): when `deficit = leaf_min+root_min − bm_inc > 0`,
   `loan = max( min(deficit·0.8, sapwood_c − debt_c)·0.2, 0 )`; `bm_inc += loan`; `debt_c += loan`. Fires
   only for carbon-starved trees; ~zero for a healthy growing beech.

## 4. Crux / decision-first (the verify's load-bearing findings)

1. **★ SEEDING IS MANDATORY, not optional.** The C grows the `sapwood_bg` demand ONLY when the pool is
   already `> 0` (`allocation_tree.c:206`). In real LPJmL the pool is seeded at establishment; the
   emulator's demography is FIXED (no establishment for trees), so **a 0-seeded pool never bootstraps → a
   permanently-0 `sapwood_bg` → a permanently-0 maintenance term → NO CUE movement (the whole change is
   inert).** The pool MUST be reconstructed at init from the demand equation (`sapwood_bg_0 =
   root_sapwood_layer` at the initial `sap_xs_area`). This is step 0, and it also sets the CUE magnitude.
2. **★ CUE MAGNITUDE is unquantified and drives a test-break risk.** The committed
   `hainich_individuals_*.csv` have NO `sapwood_bg` column (verified), so the pool size — hence the CUE
   decrement — is unknown. The lateral factor `2π/0.81 ≈ 7.76` makes the pool potentially large, but it
   respires at the N-poor sapwood C:N (330). **Before the invasive struct change, quantify it** (re-extract
   the C `ind` output with `sapwood_bg`, or compute the demand from the committed `sapwood_c/height/
   wooddens` + a rootdist profile) and confirm CUE lands ~0.46, INSIDE the gate band `[0.42, 0.56]` — an
   over-large seed pushes CUE below the 0.42 floor and breaks `multi_individual_tests.jl:153`.
3. **★ GPP is byte-identical only for the single-year annual-totals.** In the coupled/decadal rollouts the
   new maintenance term (lowers NPP → lowers accumulated `bm_inc`) AND the pre-allocation demand (shrinks
   `bm_net` into the pipe-model) shrink each tree's height/leaf/crownarea, changing next year's light
   competition and therefore GPP in years 2+. So `fdiff_annual_totals` GPP stays byte-identical (fixed
   within-year structure) but **decadal/coupled-canopy GPP baselines WILL drift** — plan to regenerate them.
4. **Dynamic per-tree rootdist.** The C recomputes `rootdist_n` per tree per year
   (`allocation_tree.c:152 getrootdepth(tree->height,...)`, `:159 getrootdist`). Threading the emulator's
   single fixed column `soil.rootdist` as `rootdist_n` is an **added simplification** (ignores the
   height→rooting-depth feedback and the vertical/lateral split) — call it out, or port `getrootdepth`.
5. **`sap_xs_area` from POST-turnover sapwood.** The C's `allocation_tree.c:163` uses sapwood AFTER
   `turnover_tree` (annual_tree.c runs turnover before allocation). `grow_individual` already computes the
   post-turnover sapwood as `sm` (`fdiff.jl:1917`) — use `sm`, NOT the pre-turnover `tree.sapwood_c` (that
   overstates the demand by the sapwood turnover rate ~4%).
6. **`sapwood_bg` turnover / `heartwood_bg`.** Decide the turnover policy (does `turnover_tree` move
   `sapwood_bg → heartwood_bg` annually?) and rework the `dynamic_structure_tests.jl:69-77` conservation
   assertion consistently. `heartwood_bg` matters only for below-ground turnover, not maintenance/CUE — can
   be deferred if `sapwood_bg` turnover is handled.

## 5. Implementation steps (once §4.1/§4.2 are resolved)

0. **Quantify + seed** (do FIRST, §4.1/§4.2): reconstruct `sapwood_bg_0` from the demand equation; confirm
   the CUE lands ~0.46 inside `[0.42, 0.56]`.
1. **Add `sapwood_bg_c` (and optionally `debt_c`) to `TreePools`** + update EVERY positional constructor
   (~6 `TreePools` sites in src + `grass_treepools`, the grass-estab rebuild, the SoA rebuilds, and
   `dynamic_structure_tests.jl:104`) and `vegc_ind` (carbon accounting). `agb_ind` unchanged (bg is
   below-ground).
2. **Add `c_sapwood_bg` to `Individual`** (16→17 fields) + `individual_from_pools`.
3. **Add the phen-gated `sapwood_bg` maintenance term to `autotrophic_respiration`** (new arg, default 0 so
   grass + the single-column `daily_step`/`daily_step_ml` paths stay byte-identical); pass it from the 3
   call sites (canopy multiplies by `nind`, passes `phen`).
4. **Add the C_LATERAL demand + carbon-debt to `grow_individual`** — thread soil geometry (per-layer
   `rootdist` + `soildepth` thicknesses) into the signature; use the POST-turnover `sm` (§4.5); grow the
   pool; apply the `cmass_loan` debt. Keep `max`/`min` as plain branch-selects (AD selects the live branch,
   as `_solve_leaf_inc` does).
5. **Extend the Enzyme SoA path** (`rollout_canopy_years_gpp`) with a `sapbgcs` (+ debt) plain `Vector{T}`
   threaded like `sapcs/rootcs` — NEVER a `Vector{TreePools}` scatter (Enzyme type-analysis, documented
   `:2097-2105`).
6. **Regenerate baselines + update gates**: `fdiff_annual_totals.txt` `npp` (single-year GPP/water stay
   byte-identical); the coupled/decadal NPP-derived baselines (GPP drifts, §4.3); the `multi_individual`
   CUE gate (verify it lands ~0.46, still inside `[0.42,0.56]`); the `dynamic_structure` conservation test
   (§4.6). Add a targeted test: a positive-bm beech grows a positive `sapwood_bg` and the maintenance
   lowers NPP.

## 6. AD-safety, risk, effort

- **AD path: YES.** `grow_individual` + `autotrophic_respiration` are BOTH on the Enzyme/ForwardDiff path
  (`rollout_canopy_years_gpp` is the multi-year Enzyme trainer; `gradient_correctness_tests` +
  `nn_canopy_training_tests`). The new `sapbgcs` SoA array must stay a plain `Vector{T}`. The C_LATERAL
  demand is arithmetic + `max`/`min` branch-selects (AD-safe, same pattern as the existing
  `_solve_leaf_inc` clamp). Type-stability: adding a field to `TreePools` (10→11) and `Individual` (16→17)
  breaks every positional constructor — a missed site is a compile/`type_stability_tests`/`determinism`
  failure. Do the struct plumbing + `@assert`-compile pass first.
- **Regression risk: MEDIUM-HIGH** (struct-field churn across ~8 sites; the AD path; the CUE-overshoot
  break tied to the seed magnitude). Mitigants: the change is tree-only + monotone toward the C target;
  grass + single-column paths default-off.
- **Interaction with the ungated `rd` (§13):** fixing `rd` ALONE pushes CUE further from the C; adding
  `sapwood_bg` alone lowers CUE toward 0.46. They partially cancel today — so land `sapwood_bg` FIRST and
  keep the `rd` gate deferred, confirming CUE stays inside `[0.42, 0.56]`.
- **Effort:** ~150–250 lines in `src/fdiff.jl` (3 structs/signatures + 2 rollout callers + the SoA path) +
  baseline regeneration + ~4 test-gate updates. 2–3 focused sessions: (1) quantify+seed + struct plumbing +
  maintenance term (get the suite compiling); (2) the C_LATERAL demand + debt + soil-geometry threading +
  SoA array; (3) baseline regeneration + CUE quantification + Enzyme re-verification.

## 7. Recommended first action

Do NOT start with the struct change. First run a **quantification probe** (a `scripts/` Julia script, no
`src/` change): reconstruct the `sapwood_bg` demand from the committed `sapwood_c/height/wooddens` + the
Hainich rootdist, compute the resulting phen-gated maintenance, and predict the CUE decrement. Only if it
lands CUE ~0.46 inside `[0.42, 0.56]` (§4.2) does the invasive, AD-path struct change (§5) pay off; if it
overshoots below 0.42, the seed/gate strategy must be revisited before any `src/` edit. This mirrors the
diagnosis-first discipline that caught the §26.4 grass mis-attribution.
