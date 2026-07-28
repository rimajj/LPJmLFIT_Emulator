---
status: "accepted"
date: 2026-07-28
deciders: "engineering agent on line S (full autonomy per STEERING_PROMPT.md). The variable-identity finding, the per-patch LAI reconstruction and its validation are MEASURED/derived facts (scripts/diagnose_patch_lai_reconstruction.py; the C sources named below); the decisions recorded here are (a) which side of each basis mismatch moves, (b) that `soilmoist` is a YEAR-END STATE rather than an annual mean, and (c) to correct ADR 0034's TEMPORAL diagnosis rather than build on it."
consulted: "the LPJmL-FIT C source at /home/jamirp/lpjml56fit — update_daily.c:411 (SWC) + :414 (ROOTMOIST), fpc_tree.c:28, lai_tree.c:18, new_tree.c:209, allometry_tree.c:53-57, fwriteoutput.c:714 (LAI_STAND) + fwriteoutput_ind.c:27,84,106,111 (the ind writer, its %g format and its height_min gate), include/soil.h:353 (forrootmoist), par/pft_lpjmlfit.js (K_LAMBERT_BEER_*, ALLOM*, KPR_*, CA_MAX), par/lpjparam_fit.js:17,22; src/state.jl:38, src/interface.jl:37, src/components/slow.jl, src/components/fast.jl:176-207,302, src/fdiff.jl:796 (SoilColumn); ADR 0034 (the diagnosis this corrects), ADR 0023 (train/inference consistency), ADR 0031 (one definition, never two copies), ADR 0029 (the F core and run.jl belong to line M), the residual-diagnosis + slow-drf-pipeline skills"
informed: "line O (ADR 0082 §4 reached the SAME porosity-vs-WHC insight independently on the online side and is calibrating Terrarium's plant_available_water against what turns out to be the RETIRED swc-based table — notified in lines/O/STATE.md O3b, with the new reference distribution and the changed runtime definition), line M (the runtime feature definition changed, so the committed demo .drf/.rcop move and any pinned global artifact must be re-derived before a coupled global run; `fast.jl:302` still builds FToS.soilmoist on the retired basis — an integration point), lines/S/STATE.md milestones S1d + S2, MEMORY.md, the slow-drf-pipeline skill"
---

# `soilmoist` was not a time-aggregation mismatch — it was the wrong VARIABLE; and per-patch stand LAI *is* reconstructable from `ind`

> **Status.** `accepted`. Milestone S1d. Both S-owned columns of ADR 0034's four-column runtime↔training
> shift are put on ONE basis, in the training table and in the runtime, and the change that closes each is
> not the one ADR 0034 predicted.

## 1. What ADR 0034 said, and what re-deriving it against the C found

ADR 0034 measured four feature columns outside the band the forest was trained on, and routed two of them
to this milestone with a stated cause each:

| column | ADR 0034's cause | actual cause (this ADR) |
|---|---|---|
| `soilmoist` | TEMPORAL: annual mean vs year-end instant | **the two sides are different physical QUANTITIES** — time aggregation is the smaller, second-order part |
| `lai` / `fpc` | SPATIAL: cell-mean vs single patch, "per-patch LAI is not reconstructable" | SPATIAL confirmed, but **per-patch LAI IS reconstructable** — exactly, from the columns already emitted |

Both corrections were found by doing what guardrail 5 and the `residual-diagnosis` skill require and ADR
0034 did not do for these two columns: read the C for what each side actually computes, before choosing a
fix. Had S1d been executed as ADR 0034 scoped it, the `soilmoist` "fix" (re-reduce `swc` to year-end) would
have aligned the *time* basis of two quantities that are still not the same thing — a green gate on a
mismatch, which is worse than the documented shift it replaced.

### 1a. `soilmoist`: fraction-of-saturation vs fraction-of-WHC

The training column came from the C's `swc` output (`build_swc_soilmoist_feature.py`), which is
(`update_daily.c:411`)

```
SWC[l] = (w[l]·whcs[l] + w_fw[l] + wpwps[l] + ice_depth[l] + ice_fw[l]) / wsats[l]
```

— **total** water (plant-available **plus** the wilting-point reservoir, free/gravitational water and ice)
as a fraction of **saturation** capacity. The runtime fed `sum(state.w)/length(state.w)`, and `state.w` is
(`state.jl:38`) **plant-available** water as a fraction of **WHC** — the C's own `soil.w[l]`, i.e. only the
first term of that numerator, normalised by a different capacity.

These are not the same variable on two clocks. `swc` lives on roughly `[wpwp/wsat, 1]` and never approaches
0 on a real soil; `w` lives on `[0, 1]`. No temporal re-reduction of `swc` can make them agree, and `swc`
**cannot be inverted** back to `w`: that needs `wsats`, `wpwps`, `w_fw` and `ice`, and LPJmL-FIT emits none
of them (CLAUDE.md §3 already recorded "no `wsats` output ⇒ absolute mm not reconstructable").

The interface contract had said which one is meant all along: `FToS.soilmoist` is documented "root-zone
soil moisture **state, fraction of WHC**" (`interface.jl:37`). The one C output carrying `w` itself is
`rootmoist` (`update_daily.c:414`), summed over `forrootmoist` = the top 1 m (`soil.h:353`):

```
ROOTMOIST = Σ_{l<3} w[l]·whcs[l]     (mm, patch-ensemble mean)
```

and the per-layer capacity is recoverable as `whcs[l] = whc_nat[l]·soildepth[l]` — the C's own `whcs`
(CLAUDE.md §3 / ADR 0050). So `ROOTMOIST / Σ_{l<3} whcs[l]` is a `whcs`-weighted mean of `w` over a named
layer set, in `[0,1]`, on both sides.

### 1b. `lai`: the reconstruction the skill said did not exist

`build_slow_runtime_table.py` joined the C's `LAI_STAND`, a patch-ensemble **cell-mean**
(`fwriteoutput.c:714`), onto per-**patch** training rows — while `hmean`, `hmax`, `agb`, `fpc`, `age_mean`
and the target `n_living` in the same row are all per-patch sums over that patch's emitted stems. `lai` was
the only column on a different spatial basis, and it is also the **`growth_eff` divisor**, whose numerator
(applied npp) is per-patch. The `slow-drf-pipeline` skill recorded this as unavoidable: "per-patch LAI is
NOT reconstructable from ind (no `leaf_c`/`nind`)".

Literally true, and false in effect. The emitted `LAI` (the individual's within-crown LAI) and `fpc_ind`
between them carry the missing crown area:

```
fpc_ind = crownarea·nind·(1 − exp(−k_pft·LAI))        fpc_tree.c:28
nind    = 1 / param.patcharea                          new_tree.c:209   (individual = true)
LAI     = leaf_c·sla / crownarea                       lai_tree.c:18
⇒  leaf_c·sla/patcharea = LAI · fpc_ind / (1 − exp(−k_pft·LAI))
⇒  stand_lai(patch) = Σ_stems LAI_i · fpc_ind_i / (1 − exp(−k_i·LAI_i))            (*)
```

`patcharea` cancels — it is never needed. `k_pft` is **per-PFT** (`getpftpar(pft, lightextcoeff)`: 0.59
broadleaf / 0.45 needleleaf), not one global constant; using a single k would bias every needleleaf stem.

**(*) is validated, not asserted.** `scripts/diagnose_patch_lai_reconstruction.py` inverts `fpc_ind` for the
crown area and compares it against the C's own **height** allometry (`allometry_tree.c:53,57`,
`min(allom1·(H/allom2)^(kpr/allom3), CA_MAX)`) — two expressions sharing no algebra. Over 22 498 stems in
five biome-spread cells: **median relative error 1.8e-8, p99 9.2e-6, max 1.2e-5**. That residual is the TXT
`ind` writer's `%g` six-significant-digit rounding (`fwriteoutput_ind.c:27`) amplified by the `^≈2.3` power
in the allometry — a real formula or per-PFT-constant error would be a percent-level bias in the *median*.

## 2. Why (*) does not equal `LAI_STAND`, and why that is correct

The `ind` writer emits a stem only `if(tree->height > param.height_min)` = 5 m
(`fwriteoutput_ind.c:84`), while `LAI_STAND` sums **all** living trees. So (*) is the **>5 m** per-patch
stand LAI, measured at 0.77–1.01 of the all-trees cell mean depending on biome (Amazon 1.007, Hainich
0.974, Iberia 0.964, Sahel 0.788, boreal Siberia 0.772 — the deficit is the sapling share).

This is not a new approximation: **every** column in the training row is already on that >5 m population,
including the target. Adopting (*) therefore *removes* an inconsistency rather than adding one, and the
Gate-3 oracle already compares on the C `ind`-output basis (≥5 m) for the same reason. A naive
"reconstruction == LAI_STAND" test fails, and must be read as the height truncation it is — the diagnostic
reports the share explicitly rather than tuning it away.

The measured payoff is the point of S1d: at Hainich the trained `lai` band goes from the cell-mean
`[2.707, 3.369]` (width 0.663) to the per-patch `[0.777, 4.781]` (width 4.004) — **6.0× wider**, 2.5–7.9×
across the five cells. The runtime's single patch was never a draw from the cell-mean distribution; it is a
draw from the per-patch one.

## 3. Decision

1. **`soilmoist` is the root-zone, `whcs`-weighted mean of plant-available water, both sides.**
   Training: `ROOTMOIST / Σ_{l<3} whcs[l]` — `scripts/build_rootmoist_soilmoist_feature.py`, a new deriver
   on `d_rootmoist.nc` + `whc_nat.nc`. Runtime: `root_zone_soilmoist(state, fc.soil)` in `slow.jl`, the
   same weighted mean over the same layers of `state.w`. `build_swc_soilmoist_feature.py` is marked
   SUPERSEDED (retained so the superseded tables/artifacts stay reproducible) and the `_ye` tables are
   written to **new** paths — the pre-0035 `cell_year_soilmoist_*.parquet` are never overwritten.
2. **`lai` is the per-patch stand LAI reconstructed in-row by (*)**, replacing the `LAI_STAND` join.
   The definition lives in exactly ONE place, `build_slow_runtime_table.py::patch_stand_lai_expr`, which
   the diagnostic **imports** (ADR 0031's lesson: two independent copies of one definition is what caused
   the tree-PFT truncation). `build_laistand_lai_feature.py` is marked SUPERSEDED but retained — its table
   is the all-trees reference the diagnostic's CHECK 2 scores the >5 m share against.
3. **`fpc` needs no change.** It was already `min(Σ fpc_ind, 1)` over the same patch's stems — a per-patch
   quantity on both sides. ADR 0034 grouped it with `lai` as "SPATIAL"; that was wrong. Its marginal
   excursion (0.03× band width, already below the test's 0.5 cut) is a *dynamics* outcome — the coupled
   patch settles denser than any training patch-year — not an aggregation basis error. It is therefore not
   something a basis fix can close, and this ADR does not claim to close it.
4. **`soilmoist` is a YEAR-END STATE, deliberately — not an annual mean.** The feature row splits cleanly
   into three annual integrals F delivers (`bm_inc_cell`, `growth_eff`, `water_stress`) and eight year-end
   states (`soilmoist`, `hmean`, `hmax`, `agb`, `lai`, `fpc`, `age_mean`, `n_prev`). The `ind` table is
   written at year end, so every other state column is already a year-end quantity, and the annual water
   *integral* is separately represented by `water_stress` = 1 − mean(wscal). Reading `soilmoist` at the
   instant `reconcile_demography!` runs is what makes the row internally consistent — and it needs no
   runtime accumulator. ADR 0034 framed the annual mean as the "cleaner side"; on the corrected variable
   the state reading is both cleaner and cheaper.
5. **This supersedes ADR 0034 §3.2 and §3.3 (the two causes), not ADR 0034 as a whole.** Its measurement of
   the four-column shift, its `water_stress` routing to line M, and its mechanism decision (record
   `feature_history`, write `feat_min`/`feat_max` into every meta, pin the out-of-band set in CI) all
   stand — and are what made this correction findable at all.
6. **Rejected: an annual-mean `soilmoist` accumulated in the runtime.** It is the better *predictor* in the
   abstract, and ADR 0034 named it the clean fix. It requires a DAILY hook in the coupled driver
   (`run_coupled_cell`'s day loop, the `climbuf_accumulate!` pattern of ADR 0027) — and `src/run.jl` is
   **line M's** file (ADR 0029). So it cannot be landed from line S, it would leave S1d's gate open on
   another line's schedule, and per §4 it is not even clearly right. Recorded as available if a later
   milestone shows the state reading is limiting.
7. **Rejected: emitting a per-patch `LAI_STAND` from the C.** A source patch + rebuild + a re-run of the
   historic scenario, to obtain a quantity (*) already recovers exactly from data on disk.
8. **Rejected: widening the trained band, or dropping `soilmoist` from the feature set.** The band is a
   measurement of the training data, not a tunable (ADR 0034); dropping a column would change the frozen
   `flux_feature_vector` order that line M pins.

## 4. Consequences

- **Both committed Hainich demo artifacts are regenerated TOGETHER from one table build** (ADR 0032 §5's
  standing rule): they share four conditioning columns, two of which move here, so regenerating them apart
  would silently re-split the basis S1c just unified. `scripts/verify_hainich_demo_artifacts.sh` reports
  `FAIL`/exit 1 for this change — the correct verdict, because the control confirms the edit itself moved
  the table. **That is the deliverable, not a regression: do not `git checkout --` it.** The exit-2
  `STALE-FIXTURE` tier remains reserved for a fixture that was already out of date.
- **`flux_feature_vector` gained a positional `soil` argument.** It is exported, but had no caller outside
  `slow.jl`. Adding a parameter was preferred over keeping a 5-argument method that would silently compute
  the retired feature — the exact hazard this milestone exists to remove. The frozen S→M contract (column
  ORDER, `live_flux_cond` subset, the `.drf`/`.rcop` format, `FluxDrivenSlowEmulator` kwargs) is unchanged.
- **`fast.jl:302` still builds `FToS.soilmoist` as the unweighted 23-layer mean.** `src/components/fast.jl`
  is line M's (ADR 0029) and nothing consumes that field numerically, so it is raised as an integration
  point rather than edited: after it is aligned, `FToS.soilmoist` will finally match its own docstring.
  All three constructions inside `slow.jl` were moved to `root_zone_soilmoist` so S is self-consistent now.
- **The global `_t7` tables are on the retired bases and must be re-derived, versioned** (`t8`), before any
  coupled global run; line M re-pins deliberately, and `_t7` is never mutated in place (ADR 0029/0031).
  The published `_t7` OOS numbers remain valid *as offline measurements* (table against table) exactly as
  ADR 0034 §7 recorded — only a coupled run inherits the shift. SSP370 additionally needs its own
  `cell_year_soilmoist_ye_ssp.parquet` before it can be rebuilt.
- **One whole failure class is now structurally impossible.** The `lai == 0 → growth_eff` blow-up that ADR
  0031 chased was a CROSS-SEED join artifact: one seed1-derived `lai` table joined onto a seed2 `ind`.
  With `lai` reconstructed from the same rows being aggregated it cannot come from another trajectory, and
  a group with positive npp cannot have `lai == 0`. The `GROWTH_EFF_MAX` assertion stays as a standing
  alarm, no longer as a guard against a known live path.
- **The generalizable lesson, stated so the next session can apply it without this ADR:** when a training
  feature and a runtime feature disagree, check that they are the same QUANTITY before choosing between
  aggregation bases. Two columns with the same NAME, the same units-of-a-sort and overlapping numeric
  ranges (`swc` 0.84–0.87 against `w` 0.79–1.00) can still be different variables, and an aggregation
  argument will look like it explains the gap.
