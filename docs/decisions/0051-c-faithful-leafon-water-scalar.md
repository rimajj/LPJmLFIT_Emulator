# ADR 0051 — F_diff's `wscal` was the REALIZED supply/demand ratio; the C's is a POTENTIAL leaf-on index

- **Status:** accepted (2026-07-30)
- **Line:** M (multi-cell coupled S+F+E, P3) — ADR block 0050–0069
- **Supersedes:** nothing. **Closes:** the last of ADR 0034 §1's three runtime↔training conditioning
  shifts (the other two were line S's, closed by ADR 0035).
- **Touches:** `src/fdiff.jl` (line M, ADR 0029). Opt-in; every committed baseline byte-identical.

## Context

ADR 0034 §1 recorded that the coupled loop feeds Component S's count DRF a `water_stress` of
**0.323–0.331** at Hainich while the C-derived training rows for the same cell and years span
**[0, 0.04315]** — 6.5 band widths, and after ADR 0035 the **only** remaining out-of-band feature (pinned
as exactly `Set(["water_stress"])` in `slow_production_drf_tests.jl:168`). It was routed to line M because
`src/fdiff.jl` and `src/components/fast.jl` are M's, and it blocked M3: a coupled per-cell demography score
is meaningless while the conditioning is wrong.

Both sides were believed to be "the same definition, `1 − wscal_mean`" (ADR 0034 §1 says so explicitly).
They are not. This is exactly the trap `residual-diagnosis` §3f describes — **same name, same aggregation
formula, different underlying daily variable** — and the plausible aggregation stories (annual mean vs
instant, stand vs per-PFT) would each have "explained" the gap.

## Decision

Read the expression on both sides. The C (`src/lpj/water_stressed.c:130-140`):

```c
if(eeq>0 && gp_stand_leafon>0 && pft->fpc>0)
  pft->wscal = (pft->emax*wr) / (eeq*param.ALPHAM/(1+(param.GM*param.ALPHAM)/gp_stand_leafon));
  if(pft->wscal>1) pft->wscal=1;
else
  pft->wscal = 1;
pft->wscal_mean += pft->wscal;          /* ÷ NDAYYEAR at output — fwriteoutput_ind.c:119 */
```

and `gp_stand_leafon` (`src/lpj/gp_sum.c:57-67`) is built from a per-PFT `gp` computed at **full leaf
cover** — `apar ∝ pft->fpc` with **no `phen`** — accumulated **without** `phen` (`gp_stand` gets
`gp·phen`; `gp_stand_leafon` gets `gp`), both normalized by the **plain** `Σ pft->fpc`.

So **the C's `wscal` is a POTENTIAL, phenology-independent soil-water-supply index**: *if this canopy were
fully leafed out, could the soil meet the evaporative demand?* F_diff instead computed the **realized**
ratio (`fdiff.jl:1609` before this change):

```julia
sup_acc += supply_i * fpc_i          # supply_i = ind.emax·wr·φ ; fpc_i = ind.fpc·φ
dem_acc += demand   * fpc_i          # demand   = (1−wet)·eeq·ALPHAM/(1+GM·ALPHAM/gp_stand)
wscal = smoothmin(1, sup_acc/(dem_acc + 1e-9), βwscal)
```

Three differences, **all** biasing the annual mean the same way:

1. **`phen` in the numerator — SQUARED.** `sup_acc = emax·wr·Σ fpc_i·φ_i²` against a denominator carrying
   `φ` once. The C's numerator `emax·wr` has no `phen` at all.
2. **The denominator uses the actual phen-weighted `gp_stand` and the `(1−wet)` wet-canopy reduction.**
   The C's uses `gp_stand_leafon` and omits `(1−wet)`.
3. **The no-demand day.** The C sets `wscal = 1` (**unstressed**). `sup_acc/(dem_acc+1e-9)` degenerates to
   **0** (**maximally stressed**), because supply vanishes faster than demand as `φ→0`.

**Decision: implement the C expression as `WaterParams.wscal_leafon`, default `false`.** When on,
`daily_step_canopy` additionally accumulates the leaf-on conductance (the same `photosynthesis` call at
`φ ≡ 1`) and the plain `Σfpc`, and `_wscal_leafon` evaluates the C expression per individual — the only
PFT-dependent term is `emax` once F_diff's shared community root profile (ADR 0050) makes `wr` and
`gp_stand_leafon` stand-level — returning the fpc-weighted mean of the capped values. `smoothmin` keeps the
path AD-safe. Default off, so every committed baseline and the AD trainer are byte-identical (guardrail 4).

## Evidence

`scripts/wscal_leafon_probe.jl` (job 1644166), 10 yr of committed GSWP3-W5E5 forcing, per-cell soil +
canopy, all five biome cells; the reference is derived per cell and per year by
`scripts/wscal_c_truth_diagnosis.py` (job 1644171) **exactly as the training table forms the column**
(`1 − mean_over_living_tree_stems(ind.wscal_mean)`, `build_slow_runtime_table.py:424,436`), scored against
the **seed1-vs-seed2 noise floor** of the same statistic. `water_stress`, mean over 2010–2019:

| cell | C truth | floor | F default | F `wscal_leafon` | \|d\| default | \|d\| leafon | ×floor |
|---|---|---|---|---|---|---|---|
| boreal_siberia | 0.3146 | 0.0023 | 0.6640 | 0.0000 | 0.3494 | **0.3146** | **138.6** |
| temperate_hainich | 0.0014 | 0.0003 | 0.3050 | **0.0034** | 0.3036 | **0.0020** | 6.8 |
| mediterranean_iberia | 0.0984 | 0.0102 | 0.2579 | 0.1748 | 0.1595 | 0.0764 | 7.5 |
| semiarid_sahel | 0.3425 | 0.0026 | 0.9830 | 0.4379 | 0.6405 | 0.0954 | 36.5 |
| tropical_amazon | 0.0011 | 0.0032 | 0.0054 | **0.0000** | 0.0043 | **0.0011** | **0.4** |

**The decisive result:** Hainich's annual `water_stress` moves from 6–7 band widths above the C-trained
`[0, 0.04315]` to **entirely inside** it (mean 0.0034, max 0.0336) — a **152× error reduction** against the
C's own value — and `tropical_amazon` lands **inside the noise floor** (0.4×). `semiarid_sahel` improves
6.7×, `mediterranean_iberia` 2.1×. The pinned out-of-band conditioning column at Hainich is closed.

**What the fix does NOT close, stated plainly: `boreal_siberia`.** The C says boreal Siberia *is* water
stressed (0.3146); the realized ratio over-stressed it (0.664, error +0.35) and the C-faithful expression
**under**-stresses it to exactly 0.000 (error −0.31). The error barely shrinks — it changes sign. In the
probe the boreal cap binds on **100 %** of days (`wscal ≡ 1.0000`, growing season included), so F_diff's
`emax·wr` exceeds the leaf-on demand every single day there.

**[ASSUMPTION] — the leading hypothesis for the boreal residual, NOT verified here.** The C's `wr` is
`Σ rootdist_n[l]·soil.w[l]` over **plant-available** water, and the C's soil carries **ice**
(`ice_depth`/`ice_fw`, and `getrootdist(…, config->permafrost)`), so a frozen boreal profile has little
plant-available water even when total water is high. **F_diff has no soil-ice or permafrost
representation at all** (verified by inspection of `src/fdiff.jl`/`src/state.jl`), so its `wr` stays high
year-round, inflating `emax·wr` until the cap binds. This is consistent with every number above but is
**not measured** — the C emits neither `wr` nor absolute layer water (`swc` is not invertible to `w`,
ADR 0035). Falsifiable next step: compare F_diff's root-zone `w` against the C's `rootmoist` for cell
52059 (that single-cell run exists) over the winter/spring months; if F_diff's stays high while the C's
collapses, the mechanism is confirmed. **Deliberately not chased inside this milestone** — soil ice is a
separate F-core physics feature, and the old definition was wrong for this cell by a comparable magnitude,
so nothing regresses.

**Which prediction FAILED, and what that corrects.** The pre-probe hypothesis was that difference (3) —
leaf-off days scored as maximally stressed — dominated, predicting a leaf-off day fraction ≈ 0.33 at
Hainich. **Refuted there:** Hainich has **zero** days with GPP ≤ 0.05 (its evergreen PFTs assimilate
year-round), so no day takes the no-demand branch; the shift is entirely differences (1)+(2), with the
growing-season daily `wscal` moving 0.695 → 0.997. Difference (3) *is* dominant at **boreal_siberia**,
where 31.3 % of days score **exactly 0** under the realized ratio and **exactly 1** under the C's. Both
mechanisms are real, they dominate in different climates, and a single-cell probe would have
mis-attributed Hainich's.

**A bug in the first implementation, caught by the test, not by the probe.** The no-demand gate was first
wired to F_diff's own `gp_stand_acc`, which sums conductances built from a **phen-scaled** `apar` — and
`photosynthesis(apar=0)` does not return exactly 0, so at `phen ≡ 0` it stayed above the `1e-20` threshold
and the C's `else wscal = 1` branch **never fired**. The gate must use the C's own numerator
`Σ gp_leafon·phen` (`gp_sum.c:65`). Every coupled number in the table above is **identical** before and
after the fix (jobs 1644166 / 1644228), because on those days the `min(…,1)` cap already returned 1 —
which is exactly why a probe could not see it and an exact-zero-`phen` unit assertion could.

**Why this gated M3 (the demographic consequence).** Coupled, on the pinned `_t8` forest, end-of-run tree N:
`semiarid_sahel` **19 → 12 (−36.4 %)`, boreal −1.7 %, mediterranean −1.2 %, Hainich −0.2 %, tropical
+0.3 %. The largest count change is in the cell whose conditioning shift was largest — a per-cell demography
score taken before this fix would have been reading a 36 %-displaced Sahel.

**A distinction ADR 0034 did not draw.** Against the **global pooled `_t8`** band the runtime values are
*inside* range (`water_stress ∈ [0, 0.9618]`); only against the **Hainich demo artifact's** band are they
out of band. So for a global coupled run this is a **conditioning shift, not extrapolation**: the DRF was
being evaluated at a valid point in feature space belonging to a *much drier cell*. That is not benign —
it is why the Sahel count moved 36 % — but it is a different failure mode from out-of-range extrapolation,
and `residual-diagnosis` §3e's warning applies: a band-membership assertion could never have caught it.

## Consequences

- **`wscal_mean` is consumed TWICE**, so this is not only a feature-basis fix: it also drives the F core's
  leaf:root allocation `lmtorm` (`fast.jl:267` → `grow_individual`), exactly as the C's own
  `allocation_tree.c:233` uses the same accumulator. The realized-ratio version was therefore biasing
  allocation toward roots in every seasonal canopy. **This is a genuine F-core physics gap** (category (a)
  in `residual-diagnosis`), not a reference-basis artifact.
- **INTEGRATION POINT with line S — do not flip the default without S.** `slow_production_drf_tests.jl:168`
  asserts the out-of-band set is exactly `Set(["water_stress"])`; turning `wscal_leafon` on by default
  makes that set **empty** and reds S's gate. Flipping the default is a both-sides change: M flips it, S
  tightens the pinned set to `Set(String[])` in the same integration.
- **Scope.** Implemented in `daily_step_canopy` (the coupled path, and the one that produces S's feature).
  `daily_step` / `daily_step_ml` (`fdiff.jl:662,850`, the single-`Structure` validation paths) still use the
  realized ratio; their `wscal` feeds no conditioning feature. Unifying them is deliberate follow-on work,
  not silent scope creep.
- **Not addressed here** (pre-existing, documented): F_diff's `gp_stand` normalizes by the phen-weighted
  `Σ fpc_i` where the C uses plain `Σ fpc`, and F_diff's pass-1 `gp` uses a phen-scaled `apar` where the C
  computes `gp` at full leaf cover then multiplies by `phen`. Both affect `demand`, hence GPP and every
  committed baseline; they are a separate opt-in change with their own re-measure.
- `wscal` also feeds next day's GSI water phenology (`fast.jl:210`), so enabling the flag changes leaf
  display — visible in the probe as the Sahel's leaf-off fraction moving 3.6 % → 18.9 %. Faithful (the C's
  `phenology_gsi.c` also reads `pft->wscal`), and a reason the default flip needs its own baseline re-measure.

## Alternatives rejected

- **Widen the trained band to admit 0.33.** `residual-diagnosis` §3e: a band is a measurement, not a
  tunable. It would have destroyed the only signal that catches the next shift.
- **Treat it as an aggregation mismatch** (annual-mean vs instantaneous, stand vs per-PFT). This is what
  ADR 0034 §1's framing invited, and §3f is explicit that "fixing" the aggregation over a *quantity*
  mismatch is worse than the documented residual, because it spends the alarm.
- **Refactor to per-PFT `wscal` trajectories** (the C's true granularity). Larger change, and unnecessary
  here: the only PFT-dependent term in the C's expression is `emax`, and the `min(...,1)` cap binds on
  almost every Hainich day, so the per-individual evaluation already recovers it.
