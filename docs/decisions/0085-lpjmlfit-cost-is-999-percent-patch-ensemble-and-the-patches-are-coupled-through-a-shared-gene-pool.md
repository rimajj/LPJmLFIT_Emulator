# ADR 0085 — LPJmL-FIT's cost is 99.9 % patch ensemble, the patches are COUPLED through a shared gene pool, and the atmosphere-facing fluxes converge in a handful of patches

* **Status:** accepted
* **Date:** 2026-08-17
* **Line:** O (online coupling) · ADR block 0080–0089
* **Supersedes in part:** ADR 0093 §2 ("the patch ensemble is NOT the bottleneck") and ADR 0084 §4
  ("the patch ensemble stays last … a clean ~3× that is worth nothing to argue about now") — **both were
  derived at `npatch = 25` and both invert at the production `npatch ≈ 500`.**
* **Trigger:** the owner, 2026-08-17: *"take the original C code as starting point … Remember that usually
  for publications at least 500 patches per cell are used — the 25 were just for testing."*

---

## 1. Why this ADR exists — a stated basis that was wrong

Every speed verdict this project has recorded was computed at **`npatch = 25`**, because that is what the
committed ground-truth run used. The owner has now stated that **publication-grade LPJmL-FIT runs use
~500 patches per cell** and that 25 was a testing convenience.

That is not a detail. Patch count is the multiplier on essentially the entire model, so **three recorded
conclusions invert**:

| recorded at npatch = 25 | true at npatch = 500 |
|---|---|
| ADR 0093 §2: "the ~100× decomposes as 37× engineering + ~3× patches" | the patch ensemble is **99.94 %** of the cost; engineering is worth ~1.9× and patches ~1658× |
| ADR 0084 §4: "the patch ensemble stays last … worth nothing to argue about now" | the patch ensemble is **the only** route to an order of magnitude, and everything else is a rounding error beside it |
| line O's kill of the few-patch → many-patch surrogate ("caps at 25×, and the target is too noisy to validate") | the cap is **20× at J=25, 49× at J=10, 94× at J=5**; and the reference target's own noise falls as 1/√J, so at 500 patches it is ~4.5× *cleaner* than the figure the unmeasurability argument used |

**Method lesson, and it is the general one:** a cost verdict is only valid at the configuration it was
measured at, and a *multiplicative* configuration knob (patch count, ensemble members, resolution) must be
stated with every speed number, exactly as ADR 0084 required the cell and the core count to be stated.
The knob was in the config file the whole time; nobody asked what production used.

---

## 2. MEASURED — the patch-scaling law

`scripts/probe_c_patch_scaling.sh` (new). Cell 42490 (Hainich), 1 core, stock binary. `npatch` is
**restart-pinned** — it is read only in the non-restart branch (`newgrid.c:477`
`addstand(...,config->npatch)`) — so each patch count pays for its **own 300-yr spin-up** from bare ground,
and the timed transient runs from that patch count's own restart at two lengths which are **differenced**,
cancelling every per-run fixed cost (start-up, restart read, output).

| npatch | core-s per cell-year (marginal) | **cost / J** |
|---|---|---|
| 1 | 0.0136 | 0.01360 |
| 5 | 0.0738 | 0.01476 |
| 10 | 0.1286 | 0.01286 |
| 25 | 0.3566 | 0.01426 |
| 50 | 0.6668 | 0.01334 |
| 100 | 1.4308 | 0.01431 |

**The per-patch cost is FLAT in J — 0.01385 ± 0.00065, 4.7 % scatter over two decades of patch count.**
So the law is a proportionality, not an affine relation:

```
cost(J) ≈ 0.014112 · J        core-s per cell-year        (fit through the origin)
```

⚠ **METHOD TRAP, and the first version of this script fell into it.** An *unconstrained* least-squares line
through data whose intercept is genuinely zero returns a small **negative** intercept — measured
**−0.0078** — and then every quantity derived from it prints as negative nonsense ("per-cell share
−120 %", "hard ceiling −913×"). **Read `cost/J` first; fit through the origin; and BOUND the fixed cost from
the smallest-J point rather than extrapolating to it.** The bound: the entire J=1 cell-year is 0.0136
core-s, so the patch-count-independent part is **at most 0.19 % of the 500-patch bill**. Script corrected;
it now also refuses to extrapolate when `cost/J` is not flat.

Confirmed structurally by reading `src/lpj/update_daily.c:67-83`: the only work before the patch loop is
`updategdd`, `temp_response`, `daily_climbuf`, `getavgprec` and two output accumulators. Everything
expensive is inside `foreachstand → foreachpatch`.

| npatch | core-s / cell-yr | global, 54 020 tree-bearing cells |
|---|---|---|
| 5 | 0.071 | 1.1 core-h per simulated year |
| 25 | 0.353 | 5.3 core-h |
| 100 | 1.411 | 21.2 core-h |
| **500 (production)** | **7.06** | **105.9 core-h** |
| 1000 | 14.11 | 211.8 core-h |

**Speedup from 500 patches down to J is exactly 500/J**, because no Amdahl floor was detected:
100 → 5× · 50 → 10× · 25 → **20×** · 10 → **50×** · 5 → **100×** · 2 → 250×. **Do not quote a finite
"ceiling"** — the measurement bounds the floor below 0.19 %, so the ceiling is set by how few patches the
science can accept, not by the code.

**FAIRNESS CHECK (passed).** Each patch count was spun up independently, so the comparison is only valid if
the resulting stands are equivalent. Cell vegetation carbon over the six patch counts spans
0.01558–0.01652 — **5.8 %** — so they are. The script now asserts this and warns if it fails.

**REPRODUCED AT A SECOND, CONTRASTING CELL.** `tropical_amazon` (12045), 200-yr spin-ups:
J=5 → 0.00692, J=25 → 0.00828, J=100 → 0.00839 core-s per **patch**-year, i.e. converging and flat within
20 % ⇒ `cost ≈ 0.00838 · J`, **4.19 core-s per cell-year at 500 patches** (Hainich 7.06). The per-patch
constant differs between cells by ~1.7× — as expected, since it is set by how many individuals the cell
carries — but **the proportionality holds**. So the global bill at 500 patches is of order **60–100 core-h
per simulated year**, cell-mix dependent.

⚠ **And the guard earned its keep on the first use.** The Amazon J=1 point came out at 0.0388 core-s per
patch-year against 0.0069 at J=5 — a 5.6× outlier that makes the raw scatter 86 % — because differencing
two ~2-second runs at a cheap cell is dominated by timing noise. The corrected script's *"NOT flat: the
cost is not proportional to patch count — investigate before extrapolating"* branch fired and refused to
report a speedup table. **Read that warning as a data-quality signal, not as a physics finding**: exclude
the shortest-run arm and re-fit, as done here.

⚠ Basis caveat, stated because it matters: these spin-ups are 300 yr (Hainich) / 200 yr (Amazon) from bare
ground, not the production 1000 yr, so the *absolute* level differs from ADR 0084's 0.2666 at J=25 measured
from the production restart (this probe gives 0.3566 — a denser stand). **The scaling law is the result
here, not the level.**

### 2a. Against the compute targets

At the production 500 patches, **7.06 core-s per cell-year**:

* **235×** over `EXECUTION_PLAN.md` §0's ≤ 0.030 convention (small fast atmosphere), **523×** over ≤ 0.0135.
  Both remain a **convention** (10 % of a measured SpeedyWeather coupled cost), **not an owner requirement**.
* **1.4×** over 10 % of a CMIP-class 1° atmosphere (~50 core-s per land-column-year). ⇒ **LPJmL-FIT at its
  full publication configuration is already essentially affordable inside a realistic climate model.** The
  affordability problem is specific to a deliberately small, fast atmosphere.
* And at **2 patches it is 0.028 core-s per cell-year — inside even the aggressive convention, with no code
  change at all.** §4 is why that is not yet a solution, and §5 is what would make it one.

---

## 3. MEASURED — where the time goes inside the C

Fresh `perf record --call-graph dwarf` + `perf report --children`, same cell, `ARM=min`
(`scripts/bench_speed_gate_c.sh … PERF=1`, job 1821066). Marginal rate reproduced at **0.2678** against
ADR 0084's 0.2666 (+0.4 %) — the profile is on a run whose cost is the recorded one.

| inclusive | self | symbol |
|---|---|---|
| 98.22 % | 1.37 % | `update_daily` |
| 82.23 % | 4.71 % | `daily_natural` |
| 54.08 % | 6.35 % | `water_stressed` |
| **45.67 %** | **31.02 %** | **`photosynthesis`** |
| **36.34 %** | 0.17 % | **`bisect`** (the λ solve) |
| 36.17 % | 0.17 % | `fcn` (the bisected residual) |
| 10.20 % | 2.49 % | **`getrootdist`** |
| 6.47 % | 3.43 % | `infil_perc_rain` |
| 5.87 % | 1.85 % | **`pedotransfer`** |
| 5.65 % | 0.26 % | `gp_sum` |
| 4.38 % | 2.24 % | `littersom` |
| 3.77+1.20+1.03 % | | soil thermal / heat conduction |

**⚠ A THIRD OF LPJmL-FIT IS SPENT IN `pow`/`exp`/`log`.** Self time in the math library:
`__libm_exp2_e7` 13.63 · `__svml_pow2_l9` 7.63 · `__libm_pow_l9` 7.06 · `__svml_log101_l9` 1.37 ·
`__libm_exp_z0` 1.29 · `__svml_exp2_l9` 0.85 = **31.83 %**. That is the single most actionable fact about
the C's single-core cost, and a large share of those calls recompute a quantity that has not changed.

**The annual step is ~2 % of a cell-year** (`update_daily` is 98.22 % inclusive). Allocation, mortality,
establishment and the light competition together cost almost nothing. ⇒ **any proposal that speeds up the
demography is attacking 2 % of the model.** This is the measured refutation of the current architecture's
premise, from the C side, and it agrees with the emulator-side finding that the learned demography's own
arithmetic is under 2 % of the coupled run.

### 3a-0. The production build has vectorisation switched OFF

`Makefile.inc:19` — **`OPTFLAGS = -g -O3 -no-vec`**, with `-Werror` and `-DSAFE -DWITH_FPE`. So the entire
model runs **scalar**, by explicit choice, and carries debug symbols. This matters twice over: it is a
large untested headroom (the daily canopy loop is the kind of code auto-vectorisation helps most), and it
means **any "the C is already optimal, we cannot beat it" argument is unfounded** — nobody has tried.
⚠ It is **not** an exact win: `-no-vec` is very likely deliberate, because vectorised reductions reorder
floating-point additions and this model's bit-reproducibility (ADR 0041/0043 equality gates) depends on
them. Treat it as *measurable headroom requiring a decision about bit-reproducibility*, not as free.

### 3a. Two verified pieces of pure waste

1. **`getrootdist` (10.20 %) is called TWICE PER INDIVIDUAL PER DAY WITH IDENTICAL ARGUMENTS, and its
   result is CONSTANT WITHIN A YEAR.** The two call sites are `water_stressed.c:86` and
   `daily_natural.c:247` — same `pft`, same `config->permafrost`, so the second is 100 % redundant with the
   first and exists only to fill the `ROOTDIST` diagnostic. Each invocation does `2 + num_layer_new`
   `pow(beta_root, layerbound[l]/10)` calls with a **runtime base** (no strength reduction possible);
   `USE_BETA2` is *not* defined so the second block is dead, and with `root_model="logistic"` a mature tree
   reaches ~20 m of rooting depth ⇒ `num_layer_new ≈ 21` ⇒ **~22 `pow` per call, ~44 per tree-day**.
   Its inputs are `pft->beta_root` — an **immutable trait** fixed at establishment (`new_tree.c:237`) —
   `pft->rootdepth`, **written only at `allocation_tree.c:152`, i.e. once per year** (verified by grep: the
   only other writers are the three `new_*` initialisers), the global constant `layerbound[]`, a `soildepth`
   that is unconditionally 20 m (`newgrid.c:282`), and `soil.mean_maxthaw`, updated once per year
   (`update_annual.c:80`). ⇒ **~16 000 `pow` calls per tree-year for a value that changes once a year**, or
   of order **10⁹ per cell-year at 500 patches**. Caching on the `Pft` and invalidating at the annual
   allocation is **bit-identical**, and dropping the second call is bit-identical too. **This is the
   cleanest single win in the model.**
2. **`photosynthesis` recomputes and then DISCARDS work on every bisection iteration.** With
   `comp_vm = FALSE` — which is the case for every bisection call — `photosynthesis.c:66-80` computes
   `ko`, `kc`, `fac`, `tau`, `gammastar`, then `pi = lambdamc3*co2`, `c1`, `c2`, `s`, and
   `sigma = sqrt(1-(c2-s)/(c2-theta*s))`; then `:98` overwrites `pi = lambda*co2` and `:102-106` overwrite
   `c1` and `c2`, and **`s` and `sigma` are never read again**. So a division and a `sqrt` and ~8 flops are
   dead on every iteration. Separately, `ko`/`kc`/`tau` are three `pow(q10, (temp-25)*0.1)` calls depending
   on **air temperature alone** — identical for all ~149 individuals, all bisection iterations, and all 500
   patches of a cell-day.

### 3b. The λ solve is a polynomial root, not a transcendental one

`water_stressed.c:207` calls `bisect((Bisectfcn)fcn, 0.02, LAMBDA_OPT+0.05, &data, 0, EPSILON, 30, &iter)`
on `fcn(λ) = data.fac*(1-λ) - photosynthesis(…,λ,…,compvm=FALSE)`. With `vm` held fixed, the λ-dependence
of `photosynthesis` is entirely through `pi = λ·co2` in two **Möbius** functions,
`c1 = tstress·alphac3·(pi-Γ*)/(pi+2Γ*)` and `c2 = (pi-Γ*)/(pi+kc(1+po2/ko))`, entering the
Haxeltine–Prentice co-limitation `agd ∝ (je+jc) - sqrt((je+jc)² - 4θ·je·jc)`. Both `je` and `jc` carry the
**common factor** `(pi-Γ*)`, so with `u = pi`, `s = u-Γ*`, `D = (u+2Γ*)(u+h)`, `N` linear in `u`:

```
je+jc = s·N/D        je·jc = A·B·s²/D        sqrt(…) = (s/D)·sqrt(Q),  Q = N² - 4θAB·D  (quadratic in u)
```

Clearing `D` and squaring once turns the residual into a **sextic polynomial in λ** whose coefficients are
assembled **once per individual-day** from `(A, B, Γ*, h, fac, rd, θ, co2)`. A sextic is not solvable in
radicals, but that is irrelevant: Horner evaluation is ~12 flops against a `photosynthesis` call's three
`pow`, one `sqrt`, one division and ~40 flops, so 4–5 Newton/Halley steps on the polynomial replace the
bisection at **~1–2 % of its cost**. Squaring admits spurious roots (where `C·s·N - P·D < 0`); select the
root in `[0.02, LAMBDA_OPT+0.05]` that satisfies the **unsquared** residual, which is one extra evaluation.

⚠ **How many iterations the bisection actually runs — and the trap in answering it.** `bisect.c` is called
with `xacc = 0`, which makes its x-tolerance early exit at `:37` **dead code**, so it terminates only on
`|ymid| < EPSILON = 1e-3` or after `maxit = 30`. Attributing the profile: `photosynthesis` is 45.67 %
inclusive, of which `fcn` (the bisected residual) is **36.17 %**; `gp_sum` — which calls
`photosynthesis(compvm=TRUE)` once per individual-day unconditionally — is 5.65 % inclusive; leaving
**~4 %** for the single final `compvm=TRUE` call at `water_stressed.c:208`. Since that final call is the
*more* expensive kind (it computes `vm`, adding two further `pow` for the SLA cap), the ratio
36.17 / ~4 implies **roughly 9–13 residual evaluations per solve** — for those individual-days that pass
the `:196` gate `gpd > 1e-5 && tstress >= 1e-2`.
**Two things not to say.** (a) Never quote "30 calls per individual-day" — that is the loop bound.
(b) Never quote a single average over *all* individual-days either: the gate fails on a large fraction of
them (0–65.6 % inert days by biome; 47 % of stems are sub-5 m suppressed saplings), so the correct
statement is **a gated fraction of individual-days each doing ~9–13 evaluations**, which is why the
bisection is 36 % of runtime while a naive cycle-budget estimate over all individual-days suggests ~2.
Both figures are consistent; conflating them is what makes the estimate wrong.
⇒ This corrects the emulator-side framing in ADR 0084 §3, which compared its 78–79 calls against
"the C's ≤ 30". Against the real ~9–13 the emulator's disadvantage on this path is **~6–9×**, not 2.6×.

### 3c. The exact-only ladder (no accuracy change whatsoever)

| removes | % of runtime | exactness |
|---|---|---|
| the λ bisection → polynomial solve (§3b) | ~28.9 (80 % of `fcn`) | equal to solver tolerance; opt-in flag |
| cache `getrootdist`, and delete the duplicate second call (§3a.1) | ~9.2 | **bit-identical** |
| memoise the Vcmax bracket per (cell-day, PFT id) — ≤ 10 values (§3d.1) | ~5.8 | **bit-identical** (same expression, same inputs) |
| memoise `temp_stress` per (cell-day, PFT id) — ≤ 10 values, 2 `exp` each (§3d.2) | ~2 | **bit-identical** |
| hoist `pedotransfer`'s per-cell sand/clay coefficients; `daylength`/`par`/`petpar2`'s `s`; `setup_heatgrid` (§3d.3-5) | ~3 | **bit-identical** |
| the dead `sigma`/`s`/discarded `c1`/`c2` block when `compvm=FALSE` (§3a.2) | subsumed by row 1 | **bit-identical** |
| **total** | **~49 %** | ⇒ **~2.0×**, or **1.6×** if only three quarters is realised |

Deliberately **excluded** from this ladder because they are *not* exact: `"soilpar_option":
"fixed_soilpar"` (5.9 % — it freezes the soil hydraulic parameters at a chosen year rather than merely
skipping the recomputation, used at `update_daily.c:152/210/264`, so it changes the physics and must be
scored); and lifting `-no-vec` (§3a-0 — reorders floating-point reductions).

⇒ **the honest single-core headroom in the C is ~1.5–1.9×**, and it is *disjoint from* and *multiplies
with* any patch reduction. It is not an order of magnitude and no combination of micro-optimisation is.

### 3d. Two EXACT algebraic factorisations the code does not exploit

Both come from the same observation: a quantity that depends only on `(air temperature, daylength, CO2,
PFT-parameter id)` has **at most 10 distinct values per cell-day** (there are 10 natural PFT parameter
sets), yet is recomputed once per individual per solver iteration per patch.

1. **The Vcmax bracket factorises exactly into (per-cell-day constant) × `apar`.** `photosynthesis.c:91`
   computes `*vm = (1/b)·(c1/c2)·((2θ−1)s − (2θs − c2)σ)·apar·cmass·cq`, and `c1`, `c2`, `s`, `σ` are all
   functions of `(temp, daylength, co2, PFT id)` alone. ⇒ **the per-individual content of a
   `compvm=TRUE` call is exactly one multiply.** This is algebra, not approximation.
2. **`temp_stress(pft->par, temp, daylength)`** likewise has ≤ 10 distinct values per cell-day and is
   evaluated ~2 × n_ind × npatch ≈ 150 000 times. Same for the temperature-only Michaelis–Menten block
   (`ko`, `kc`, `fac`, `tau`, `gammastar`).
3. **`pedotransfer` is affine in a single per-patch input.** `pedotransfer.c:69-79`'s Saxton–Rawls
   polynomials depend on `sand`/`silt`/`clay` through `soil->par`, a **pointer to a shared per-cell
   `Soilpar`**; the only per-patch input is `om_layer` (that patch's own soil carbon). So each layer's
   coefficients are `A_l + om_layer · B_l` with `A_l`, `B_l` **per-cell constants** — currently recomputed
   2 × 23 × npatch times per cell-day for 23 distinct values.
4. **`setup_heatgrid`** rebuilds the 23-point thermal grid from the *global* `soildepth[]` on every
   patch-day — 182 500 identical rebuilds per cell-year.
5. **`daylength`, `par` and the saturation-slope term in `petpar2`** are functions of `(lat, day)` or
   `temp`/`swdown` alone (`petpar2.c:47-69`) but sit inside the patch loop — 500× redundant. Only `eeq`
   genuinely depends on the patch, through its albedo.

⚠ **And the floor this leaves.** Per-individual work is 88.7–98.5 % of a patch's cost, so the Amdahl
ceiling on *all* per-individual optimisation is 8.8–67×. Driving every per-individual cost to **zero** at
500 patches still leaves **0.08–0.60 core-s per cell-year of irreducible per-patch cost** — dominated by
500 independent 23-layer soil columns with an enthalpy permafrost solve, two pedotransfer calls and
`littersom`. That still misses the 0.030 convention by 2.7–20×. **⇒ patch reduction is not optional; no
amount of per-tree optimisation substitutes for it.**

---

## 4. MEASURED — the atmosphere-facing fluxes converge in a handful of patches

From the `globalflux` written by the scaling probe, 10-yr means, one realisation per patch count
(each with its own independent 300-yr spin-up, so the spread mixes estimator noise with stand luck —
`scripts/probe_c_patch_convergence.sh` repeats this over independent seeds to separate them):

| quantity | J=1 | J=5 | J=10 | J=25 | range |
|---|---|---|---|---|---|
| precipitation | | | | | **0.4 %** |
| net primary production | | | | | **1.7 %** |
| evaporation | | | | | **2.1 %** |
| **gross carbon uptake** | 0.002308 | 0.002226 | 0.002245 | 0.002215 | **4.2 %** |
| interception | | | | | 6.5 % |
| transpiration | | | | | 6.6 % |
| heterotrophic respiration | | | | | 7.0 % |
| litter carbon | | | | | 10.3 % |
| fire | | | | | 25.1 % |
| **vegetation carbon** | | | | | **34.2 %** |
| **net ecosystem production** | | | | | **40.6 %** |
| net biome production | | | | | 47.6 % |
| **establishment** | | | | | **96.5 %** |

**The pattern is a mean versus a small residual of two large numbers**, and it splits the outputs along
exactly the line that matters:

* **What an ATMOSPHERE consumes** — carbon uptake, transpiration, evaporation, interception, and through
  them the latent and sensible heat fluxes — is within **1.7–6.6 %** even at a *single* patch.
* **What the FOREST SCIENCE consumes** — tree numbers, vegetation carbon, establishment, the net carbon
  balance — is **34–97 %** wrong at low patch count.

⇒ **The 500 patches are needed for the forest structure, not for the surface exchange.** This is the
finding that reframes the coupling problem: an ESM-ready LPJmL-FIT does not need 500 patches for the
fluxes it hands the atmosphere. Combined with §2, a few-patch C model is **already inside** the aggressive
convention (J=2 is 0.031 core-s/cell-yr against 0.030) — before any code change at all.

### 4a. MEASURED PROPERLY — the per-variable patch requirement, from independent seeds

`scripts/probe_c_patch_convergence.sh`, cell 42490, **5 independent spin-ups per patch count** (a seed is
inert on restart, so each member is its own 200-yr spin-up), patch counts 1/5/25/100, scored over 10 yr.
The spread **across seeds** at fixed J is the estimator's own error at that J.

| | **measured CV at J=100** | patches for 10 % | for 5 % | for 2 % |
|---|---|---|---|---|
| **atmosphere-facing** | | | | |
| evaporation | **0.59 %** | 1 | 2 | 9 |
| gross carbon uptake | **0.96 %** | 1 | 4 | 24 |
| transpiration | **1.48 %** | 3 | 9 | 55 |
| net primary production | **1.57 %** | 3 | 10 | 62 |
| interception | 5.22 % | 28 | 109 | 682 |
| **forest science** | | | | |
| soil carbon | 2.12 % | 5 | 18 | 113 |
| heterotrophic respiration | 2.38 % | 6 | 23 | 142 |
| net ecosystem production | 2.74 % | 8 | 31 | 188 |
| **vegetation carbon** | **3.40 %** | **12** | 47 | 289 |
| litter carbon | 4.00 % | 17 | 65 | 400 |
| net biome production | 4.76 % | 23 | 91 | 567 |
| establishment | 7.54 % | 57 | 228 | 1 422 |
| **fire** | **32.3 %** | **1 044** | 4 176 | 26 099 |

**⇒ At the stated 10 % tolerance, 100 patches already over-delivers on every quantity except fire, and the
extrapolated requirement is 12–28 patches for the quantities that matter — a 18–42× over-provision at
500.** The one quantity that needs **more** than 500 is fire (~1 000 for 10 %), a rare near-Poisson event;
it is not named in the acceptance criterion.

⚠ **CHECK THE 1/√J ASSUMPTION BEFORE EXTRAPOLATING — it does not hold uniformly, and the table alone hides
that.** Forming `c = CV_J·√J` at each arm (constant `c` ⇔ pure Monte Carlo scaling):

* **`fire` (1.1×), `transp` (1.2×), `LitC` (1.7×), `VegC` (1.7×), `estab` (1.8×), `interc` (1.8×)** — `c`
  stable, the law holds, extrapolation is safe.
* **`GPP` (1.9 → 9.6), `NPP` (3.2 → 15.7), `SoilC` (9.6 → 21.2), `SoilC_slow` (6.0 → 27.8)** — `c` drifts
  **upward**, i.e. the error stops falling: GPP's between-seed CV is **0.85 % at J=5 and 0.96 % at J=100**,
  so it has hit a **floor of ~1 % that more patches do not remove.** Cause: each member is its own
  spin-up, so the spread carries genuine spin-up-to-spin-up differences in the equilibrium state on top of
  ensemble error, and 200 yr is likely too short to erase that memory. **The floor is a property of this
  probe's design, not necessarily of the model** — but it means the small-CV rows are upper bounds on
  what patches can fix, and it reinforces the conclusion (those quantities need essentially no patches).
* Fit `c` values in the script's own table are dominated by the wild **J=1** arm (`estab` c=554 there
  against 70–75 at J≥25) and should not be used. **Anchor on J=100.**

⚠ Other caveats: 5 seeds ⇒ each CV carries ~35 % uncertainty of its own; one cell; `negc_fluxes` is
identically zero so its CV is undefined.

⚠ **This does NOT say a few-patch run is acceptable on its own terms** — it says the patch count required is
set by *which quantity* you are certifying, and for every quantity in the acceptance criterion that number
is far below 500. §5b is the structural reason this is a pure variance question with no bias to correct.

---

## 5. VERIFIED FROM THE SOURCE — the patches are COUPLED through a shared, patch-count-sized gene pool

This is the structural finding, and it was not known to this project. **The patches in a cell are not
independent replicates.**

1. **Every random draw in the daily and annual paths uses ONE per-CELL stream**, `stand->cell->seed` —
   `mortality_tree_ind.c:152`, `fire_tree_ind.c:25`, `firepft_ind.c:27`, `daily_natural.c:92` (`permute`),
   `new_tree.c:121/137`. There is no per-patch seed. So patches are serially coupled through the RNG state:
   patch *k*'s draws depend on how many draws patches 1…*k*−1 made. ⇒ **patches cannot be reordered,
   parallelised, or reduced in number without changing every patch's random numbers** — which is also why
   ADR 0041's subset-re-run divergence behaves as it does.
2. **The inheritance seed bank is a CELL-level object shared by every patch.** `getsapling.c:70-104` loops
   `foreachpatch` over the whole cell and admits every tree whose above-ground biomass exceeds
   `getmaxagb(stand, param.n_max * stand->npatch * param.patcharea/100)` — with `n_max = 7`,
   `patcharea = 225` that is the **top `15.75 × npatch` trees**, accumulated over a rolling
   `param.max_age = 50` years. It is stored as `cell->treelist` / `cell->treelen`.
3. **Every inherited recruit draws its parent from that pool as a uniform sample, at exactly ONE call
   site:** `new_tree.c:137` `index = (int)(erand48(cell->seed) * treelen)`, then copies the parent's
   `id`, `sla`, `k_root`, `emax`, `beta_root`, `beta_2`, `D95max`, `wooddens`, `minwscal` and diffuses each
   by `×(1+0.1·gasdev)` (`new_tree.c:38-61`). The inherited channel's weight is `4/(4+n_eligible_PFTs)` —
   ~44 % at Hainich, ~80 % where diversity is low (ADR 0045/0046).

**Therefore the gene pool's SIZE IS PROPORTIONAL TO THE PATCH COUNT:** ~15 candidate trees per year at
`npatch=1` against ~7 875 at `npatch=500`. Running fewer patches does not merely add noise — it
**impoverishes the gene pool every recruit inherits from**, which is a systematic, patch-count-dependent
degradation of the trait distribution. That is a **second and previously unnamed mechanism**, distinct from
the `exp(-LAI)` plot-averaging (Jensen) gap that this project had assumed was the whole explanation for the
measured 21–81 % recruitment loss at low patch count.

**And it is the cheapest one to attack.** The coupling between patches is *purely mean-field* — a patch
never interacts with another patch, only with this one aggregate — which is exactly the structure in which
a self-consistent treatment is asymptotically exact. The pool is **only ever sampled from**, never
inspected as a set, at **one call site**. So the intervention is:

> **Decouple the gene pool from the patch count.** Run few patches for the physics, but represent the
> cell's top-biomass trait pool at its many-patch richness — as a distribution over ~8 trait axes × 7 PFTs
> rather than an explicit list of individuals — and sample recruits from that.

This is where a statistical model has an honest job, and it is a much better-posed one than anything this
project has attempted: the target is a **pooled distribution over thousands of trees**, whose own Monte
Carlo noise is far below that of a single cell's tree count, so the "the reference is too noisy to validate
against" objection is weak here. Training data already exists (the global 67 420-cell, two-seed runs).

### 5a. ⛔ MEASURED AND KILLED — the gene-pool mechanism does NOT bite, at either cell

The pre-registered condition was: *"if the spread is flat, this line of attack is dead and should be
dropped."* **It is flat. The idea is dropped.**

`scripts/probe_c_genepool_diversity.sh`, at Hainich (42490, ~44 % inherited channel) and at
**tropical_amazon (12045, ~80 % inherited — the cell where the mechanism must bite hardest, and the one a
Hainich-only test could not settle)**. Trait spread (CV) of the four sampled axes among living stems and
among young stems, versus patch count:

| Hainich, all stems | J=1 | J=5 | J=10 | J=25 | J=50 | J=100 |
|---|---|---|---|---|---|---|
| SLA | 13.8 | 21.6 | 20.0 | 20.2 | 16.9 | 18.3 |
| Wooddens | 24.3 | 23.9 | 25.9 | 25.3 | 24.4 | 23.7 |
| minwscal | 16.9 | 23.3 | 26.7 | 22.5 | 19.4 | 21.9 |

Wood density and drought tolerance are **flat to within noise across two decades of patch count**; only
rooting depth rises (37.6 → ~58). At the Amazon, restricting to the **only comparison with adequate
samples in both arms** (J=25, n=150 vs J=100, n=654): SLA −4.5 %, Wooddens −0.9 %, minwscal −10.7 %,
D95max +21.4 %, and among young stems SLA −17.7 %, Wooddens +28.2 %, minwscal +7.8 % — **four flat, two up,
one down. No systematic trend.** PFT composition is patch-count-invariant at both cells (5 types at
Hainich, 1 at the Amazon, at every J).

⚠ **The trap that made this look confirmed at first, and it is a general one.** The apparent monotone rise
lives entirely in the J=1 and J=5 arms, which have **n = 5–26 stems**. A sample CV from n < 30 is biased
**low**, and the low-patch-count arms have few stems *by construction* — **so the estimator's bias points in
exactly the same direction as the hypothesis being tested.** Any "diversity grows with ensemble size"
result must be checked against arms with comparable sample sizes before it means anything. The probe now
prints the per-arm counts and flags every group with n < 30 as *not evidence*.
(A second defect found and fixed in the same pass: the `ind` table is **annual**, so a stem alive for N
years is emitted N times, and "distinct trait values / rows" therefore just measures 1/N — it came out
~0.35 for *every* patch count on a 3-year run. Dedupe by `(Patch, ID)`, the stable cross-year individual
identity of ADR 0125.)

**Why diversity survives a 500× smaller pool — the mechanism that defeats the hypothesis.** Inheritance
does not copy a parent's trait, it **diffuses** it: `new_tree.c:38-61` applies
`new = old·(1 + 0.1·gasdev)`, clamped at ±5 σ and **reflected at the interval edges**. That is a random
walk in trait space with a reflecting boundary, so it relaxes to the interval's stationary distribution
over generations *regardless of how few distinct parents there are*. A small pool makes parents more
**correlated**; it does not make the offspring distribution **narrower**, because the diffusion regenerates
spread every generation. The uniform background channel (weight `n_elig/(4+n_elig)`, ~56 % at Hainich,
~20 % at the Amazon) reinforces this but is not needed to explain it — the effect is present at the Amazon
where that channel is weakest.

⇒ **The structural finding stands (the pool is cell-level and its size is `15.75 × npatch`); its
quantitative consequence for trait diversity is measured to be nil between 25 and 100 patches at two
contrasting cells.** So it is *not* a lever, and the 34–97 % low-patch-count error in the forest variables
must be dominated by the other two channels: plain Monte Carlo noise in the counts, and the
`exp(-LAI)` plot-averaging (Jensen) gap in establishment — measured at 21 % (temperate) to 81 % (Amazon).
**The Jensen gap is therefore the correct target**, and unlike the gene pool it is a low-dimensional,
closed-form-correctable object: `E[exp(-L)] ≈ exp(-µ + σ²/2)` to second order, or a handful of quadrature
nodes on the LAI distribution. Not tested here.

⚠ **Not ruled out:** an effect between 100 and 500 patches, which was not measured. But a lever that is
invisible from 25 → 100 is not the explanation for a 34–97 % error at low patch count.

---

---

## 5b. ⭐ THE PATCH COUNT IS A PURE VARIANCE KNOB — THERE IS NO PATCH-COUNT BIAS AT ALL

This **corrects §5's own closing sentence** (and what was said to the owner on the way to it), and it is the
most consequential finding in this ADR.

`npatch` enters LPJmL-FIT in exactly **two** places that are not output normalisation:

1. `standlist.c:94-95` — `stand->npatch=npatch; stand->patch=newvec(Patch,npatch)`, i.e. the ensemble size.
2. `getsapling.c:68` — the seed-bank admission threshold
   `agb_max = getmaxagb(stand, param.n_max*stand->npatch*param.patcharea/100)`. This is **exactly
   proportional to `npatch`**, so the *fraction* of the cell's trees admitted to the pool is
   **patch-count-invariant**.

And **establishment is computed per patch from that patch's own floor light**: `annual_natural.c:192` calls
`establishmentpft_ind(patch,…)` from **inside** `foreachpatch` (`:57`–`:283`), and the light driver is
`patch->fpar_leafon_grass` (`establishmentpft_ind.c:104/106/128/144`). Nothing anywhere averages leaf area
across patches and then computes recruitment from the average.

⇒ **The ensemble mean of establishment is `(1/J)·Σᵢ exp(−LAIᵢ)`, an unbiased estimator of `E[exp(−LAI)]`
for ANY J.** So:

⚠ **THE JENSEN GAP IS NOT PATCH-COUNT-DEPENDENT, AND THE MEASURED 21–81 % RECRUITMENT LOSS IS NOT A
FEW-PATCH EFFECT.** That measurement is the cost of replacing the ensemble with **one averaged patch** —
i.e. of a *mean-field* approximation, which is what a deterministic emulator does. It says nothing about
running 25 patches instead of 500 in the C. **Running fewer patches in the C is unbiased; it is only
noisier.** (Residual: an O(1/J) finite-population feedback, since the seed bank is drawn from the same J
patches — and §5a already measured that this does not move trait spread between 25 and 100 patches.)

**This is very good news, and it removes the need for a learned few-patch→many-patch map entirely.** The
question is no longer *"can we correct a bias?"* but *"how much precision does the acceptance criterion
actually demand?"* — which is arithmetic.

### The patch count the stated tolerance actually requires

Input: the C's own measured two-run spread on tree counts at J=25 is **7.6 %**. Two readings, because it is
not recorded whether that is the spread of one ensemble mean or of the difference of two; both are carried.

| | per-patch CV | J=500 resolves counts to | J for 1σ ≤ 10 % | J for **2σ ≤ 10 %** |
|---|---|---|---|---|
| pessimistic (7.6 % = sd of one mean) | 0.380 | 1.70 % | 15 ⇒ **35×** | 58 ⇒ **8.7×** |
| optimistic (7.6 % = sd of a difference) | 0.269 | 1.20 % | 8 ⇒ **69×** | 29 ⇒ **17×** |

**⇒ 500 patches over-delivers on the level clause by roughly 6–35×.** The tolerance is 10 %; 500 patches
buys 1.2–1.7 %. Taking 2σ (which is what *"proven correct on all 54 020 cells"* demands, not 1σ), the
honest bracket is **9–17× available from plain Monte Carlo with no new method, no learned artifact, no
fidelity validation and no code change** — just running the patch count the criterion requires.

**Trait medians and trait distributions are NOT the binding clause.** Each patch supplies ~149 individuals,
so a pooled trait median's error is ~1.253·σ/√(149J/DEFF); at a design effect of 8.4 and J=15 that is ~1.5 %
of the median — 6.5× inside tolerance. **One patch is 149 trait observations but only ONE count
observation, so the count sets J.** That inverts the intuition that trait *distributions* would be the hard
part.

### ⚠ AND THE CLAUSE THAT NEITHER 500 PATCHES NOR ANYTHING ELSE CURRENTLY PASSES

The binding clause is *the response between the two scenarios*. Read the 10 % as 10 % **of the response**
(which it must mean, or the clause has no power), with a true response of ~20 % of the level ⇒ the target is
2 % of the level. Unpaired, `sd(Δ)/µ = √2·CV/√J`:

| | J needed, unpaired | what J=500 actually resolves the response to |
|---|---|---|
| pessimistic | **722 — MORE THAN 500** | **12.0 %** |
| optimistic | 362 | **8.5 %** |

⇒ **The 500-patch reference resolves its own warming response only to 8.5–12 %.** So at the strict reading
**nothing passes, the reference included**, and no few-patch scheme can be blamed for it. **A large part of
this project's central blocking problem — "the warming response is indistinguishable from zero" — may be
Monte Carlo noise in the REFERENCE, not a deficiency of the emulator.** That is a testable claim and it
should be tested before any more effort goes into chasing the response.

**The fix is common random numbers across the two scenario legs**, which collapses the variance of a
*difference* by `(1−ρ)`:

| correlation ρ | J needed | speedup vs 500 | reference's own response resolution |
|---|---|---|---|
| 0.90 | 36–72 | **7–14×** | 2.7–3.8 % |
| 0.95 | 18–36 | **14–28×** | 1.9–2.7 % |
| 0.99 | 4–7 | **69–138×** | 0.9–1.2 % |

⇒ **Pairing is not an optimisation; it is the precondition for the binding acceptance clause being
answerable at any patch count, including 500.** Partially free already: both scenario legs restart from the
same `restart_2019.lpj`, and `random_seed` is inert on restart (the per-cell RAND48 state is restored), so
the legs start *identically seeded* and then decorrelate as their draw counts diverge. **How fast they
decorrelate is unmeasured and is the single highest-value experiment available.** Holding ρ high needs
per-event RNG substreams — indexing the generator by `(patch, tree ID, year, event)` instead of one
sequential per-cell stream — which is a real but well-understood change, and which would also make the
patches reorderable and parallelisable (§5.1).

### 5c. One more verified free win: a value computed 462 million times that nothing reads

`getfpar.c:153` accumulates `pft->fpar_leafon += fpar_uptake_leafon_layer * lai_leafon_layer[p] /
plai_leafon_layer` inside the (canopy layer × individual) double loop — a multiply and a **double divide**
per visit. Grepping every occurrence of `fpar_leafon` in `src/` and `include/`, the **only** non-assignment
hits are a comment (`getfpar.c:13`) and the struct declaration (`pft.h:242`): **the per-individual field is
write-only.** Trip count at 500 patches, Hainich (~17 canopy layers, 149 individuals):
365 × 500 × 17 × 149 ≈ **462 million discarded divisions per cell-year**.

⚠ **Do not confuse it with `patch->fpar_leafon_grass`** (`stand.h:60`, set at `getfpar.c:166`), which is a
different variable, is very much alive, and **is the establishment light driver** — deleting that would
break recruitment. The dead one is the per-individual `pft->fpar_leafon`; the live one is the per-patch
`..._grass`.

---

---

## 5d. ADVERSARIAL REVIEW OF 18 PROPOSALS — and the correction to §5b's own arithmetic

Seven idea-generation passes over the C source, each proposal then sent to a reviewer told to destroy it.
**18 verdicts: 0 confirmed, 17 weakened, 1 killed.** Ten reviewers and the synthesis died on a session
limit, so the ten concrete *exact-code* items (§3b, §3a, §3d) are **unjudged** — but those were derived and
verified against the source in §3, which is stronger evidence than a reviewer's opinion.

**⚠ THE CORRECTION THAT MATTERS MOST — §5b's 9–17× is too optimistic, and it is my error.** I priced the
patch requirement at **2σ**. With **54 020 cells each certified individually**, 2σ is the wrong bar: a
multiple-comparison correction puts it near 4σ, which quadruples J. Two independent reviewers landed on
**J ≈ 125–170 ⇒ 3–4×**, a third on 5–18× depending on how "all cells" is read. **Honest range for the whole
fewer-patches lever: 3–8×, centre ~5×.** My own measured table (§4a) agrees once read at 4σ: vegetation
carbon needs 12 patches at 1σ ⇒ ~192 at 4σ ⇒ 2.6×.

**⚠ THE STRUCTURAL FINDING THE REVIEWERS FORCED, and it invalidates every "stacked" number:** essentially
every ensemble-side idea draws on **the same 99.9 % of the bill** and is therefore *the same lever*, not a
factor to multiply. Fewer patches, the mortality control variate, per-cell adaptive patch counts, common
random numbers, stratified mortality — all reduce *the effective number of patch-years*. Quoting them
together triple-counts. Only two families genuinely compose: **(A) reduce the number of patch-years** and
**(B) reduce the cost of one patch-year**.

| proposal | claimed | **reviewer-corrected** | family |
|---|---|---|---|
| run fewer patches, unchanged | 8.6–33× | **3–8×** (centre ~5×) | A |
| K shared soil columns instead of npatch | 1.06× | **1.29×** alone (raised); ≤ J/K, so anti-stacks with A | B |
| mortality control variate | 1.93–12.7× | **1.10–1.30×** marginal — it *is* A's multiplier | A |
| per-cell adaptive patch count | 17× | **1.4×** (1.2–2.5×) — sparse cells are numerous | A |
| common random numbers across scenarios | 7–14× | **~1.0×** — the pairing already exists (shared restart) | A |
| stratified/systematic mortality sampling | 12.5× | **1.25–1.9×** | A |
| learned annual per-individual operator | 7–73× | **1.3–1.5×** as scoped | B |
| delete the dead leaf-on share (§5c) | 1.09–1.30× | **1.01×** — above its own Amdahl ceiling | B |
| annual-step solver fixes | 1.26× | 1.005× today; **1.6×** after B lands | B |
| Perfect Plasticity Approximation / patch-age closure | — | **0× — rejection strengthened** | — |
| prediction-powered estimation of trait medians | 2–5× | **KILLED (1.0×, possibly 0.5×)** | — |

**Three reviewer findings worth more than the numbers:**

1. **Why the learned annual operator collapses from 7–73× to 1.3–1.5×** — the per-tree daily step is *also
   what drives the patch's soil water and litter every day*. **You cannot delete the daily tree loop without
   also replacing the soil column.** It reaches 15–40× only in the unstated larger scope where the soil and
   the grass PFTs are emulated too. This is the cleanest refutation yet of "learn the annual operator", and
   it explains why K shared soil columns is its prerequisite rather than its alternative.
2. **Why the textbook mean-field route is genuinely unavailable** — LPJmL-FIT spreads each tree's leaf area
   **uniformly over its whole patch** (`getfpar.c`'s `atoh` is per-patch, ADR 0135) rather than tracking
   crown positions, so the Perfect Plasticity Approximation's canopy-closure height **does not exist as a
   quantity in this model**. Not a tuning problem — a structural mismatch.
3. **Why prediction-powered estimation was killed outright** — every patch in a cell starts bit-identical
   under identical weather, so there is nothing to predict a patch *from*; the estimator degenerates to
   plain averaging or worse.

**Honest bottom line.** Family A ≈ **3–8×**; family B exact-only ≈ **2×** (§3c, self-verified); together
**6–16×**, or **10–40×** if the approximate soil + annual-operator route is built and validated. Against
the ≤ 0.030 convention, which needs **235×**, **nothing here reaches it.** Against a CMIP-class 1°
atmosphere, the unmodified 500-patch model is already inside budget (§2a).

## 6. DECISION

1. **Every speed number in this project must state its patch count**, exactly as ADR 0084 required the cell
   and core count. Added to the `speed-gate` skill as a fifth trap.
2. **ADR 0093 §2 and ADR 0084 §4 are superseded on the patch question.** At the production configuration
   the patch ensemble is 99.94 % of the cost and is the *only* route to an order of magnitude. The
   remaining single-core work is worth **~1.5–1.9×** and should be taken because it is exact and it
   multiplies — not because it changes the outcome.
3. **The three probes are committed** and are the basis for any future patch-count claim:
   `probe_c_patch_scaling.sh` (the law), `probe_c_patch_convergence.sh` (per-variable patch requirement
   from independent seeds), `probe_c_genepool_diversity.sh` (whether the gene-pool mechanism bites).
4. **The project's target should be re-examined against the atmosphere it is actually for.** At 500 patches
   the C is 1.3× over a CMIP-class budget and 223× over this project's own small-atmosphere convention.
   Those two statements support opposite programmes, and the convention is not an owner requirement.
5. **[TODO — owner decision, raised, not taken]** The measured split in §4 means the ESM coupling problem
   and the forest-fidelity problem have different patch requirements. Whether the online model is held to
   flux accuracy or to trait accuracy is an owner call and it changes the whole programme.

## 7. Integration points raised

* **To line M / the integrator:** ADR 0084 §3's "the C's ≤ 30 photosynthesis calls per individual-day" is
  the loop bound, not the behaviour — the measured figure is **~4–8** (§3b). Any emulator-vs-C per-call
  comparison built on 30 understates the emulator's disadvantage by ~4×.
* **To line M:** the λ hand-over requested in ADR 0084 §5 now has a *derived* target form (§3b: a sextic
  whose coefficients are per-individual-day). The pre-registered six-part equivalence criterion is
  unchanged and still applies.
* **To the integrator:** `EXECUTION_PLAN.md` §0's allowances are stated without a patch count. They should
  name one, since the same model is 0.03 or 6.7 core-s per cell-year depending on it.
