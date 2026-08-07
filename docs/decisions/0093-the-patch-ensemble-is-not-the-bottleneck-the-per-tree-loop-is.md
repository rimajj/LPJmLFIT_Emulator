# ADR 0093 — the patch ensemble is not the bottleneck; the per-tree daily loop is. And the plan is to attribute error before removing cost

* **Status:** **PROPOSED — evidence is measured and settled; the SEQUENCING half is under discussion with
  the owner (2026-08-07) and is not yet accepted.** Do not treat §6 as frozen.
* **Date:** 2026-08-07
* **Line:** cross-cutting / integrator (block 0090–0099)
* **Answers:** **ADR 0092** (OPEN — "the patch ensemble is THE central production problem, and the compute
  case is unmeasured"). This record supplies the missing measurement and proposes the strategy 0092 declined
  to pick. ADR 0092 stays OPEN until the owner accepts §6.
* **Related:** 0053 (modal-patch artifact), 0057 (the driver moved to the patch ensemble), 0025 (the
  emulator's mortality is trait-blind by construction), 0045/0046 (inheritance; the warming shift is
  within-PFT within-age selection), 0049 (age–trait gradient), 0101/0105/0108/0109 (the response arm),
  0106 (the acceptance criterion), 0110 (per-tree rooting)
* **Provenance:** a 17-agent workflow (`wf_8bb33a36-ce2`); six evidence probes, four candidate
  architectures, seven adversarial critiques. Scripts and intermediate tables:
  `/p/tmp/jamirp/npatch_analysis/` (5.7 GB, scratch — not DVC-tracked). Five critiques and the automated
  synthesis died on a session limit; the synthesis in §5–§6 is the integrator's, not an agent's.
* **Owner input this session, verbatim:** *"are we doing too many steps at the same time? should we maybe
  first get the emulator working in this setting: using the original c code for the fast part … then we know
  that the problem is not in the fast part."*

---

## 1. Context

ADR 0092 framed the patch ensemble as the central production problem and explicitly refused to pick a
strategy without measurement. This record supplies the measurement. **The headline result inverts 0092's
implicit premise.**

---

## 2. The cost anatomy — MEASURED, and it changes the priority

All figures are single-core core-seconds per cell-year. C figures from `perf` on a 21-cell temperate
20-yr run plus single-task timings; Julia figures from `bench_emulator.jl` (job 1722379).

| configuration | core-s / cell-yr | vs the C |
|---|---|---|
| C, 25 patches (boreal, 131.5 ind/patch) | 0.383 | 1× |
| C, 25 patches (temperate, 145 ind/patch) | 0.290 | 1× |
| C, 1 patch | 0.0153 | 25× |
| **shipped Julia emulator, 25 patches** | **1.096** | **0.26× — 3.8× SLOWER** |
| shipped Julia emulator, 1 patch | 0.0438 | 8.7× |
| derived SpeedyWeather T31 land allowance | 0.0135 | — |

**[VERIFIED] `72–86 %` of the C's runtime is per-individual per-day photosynthesis** — `update_daily` 98.6 %
of children, `water_stressed` 49.4 %, `photosynthesis` 41.3 %, and the λ bisection alone **33.3 %** (up to 30
photosynthesis calls per tree per day, `water_stressed.c:207`). Cost is **exactly linear in npatch**
(0.0176–0.0185 core-s per patch-year at npatch=1 and npatch=50).

**[VERIFIED] the C carries 108–150 individuals per patch in memory** (restart byte accounting; global mean
108, Hainich 149) while the `ind` writer emits only the **7.3** stems above 5 m. Cost scales as
`npatch × n_ind × 365`, and `n_ind` is the larger multiplier.

**[VERIFIED] the Julia core's per-individual daily step costs 51× the C's**
(`cost_patch(10yr) = 0.0033 + 0.03998·ntree` ⇒ 3.998e-3 core-s/ind-yr vs the C's 7.84e-5), while its
**per-patch fixed cost is 0.066× the C's** (3.3e-4 vs 5.0e-3).

### The consequence, stated as arithmetic

Closing the per-individual gap alone takes the 25-patch emulator from **1.096 → 0.0296** core-s/cell-yr
(**37×**), with the patch ensemble fully intact and **zero fidelity risk** — it is the same computation done
faster. Eight patches then costs **0.0093**, inside the T31 allowance with 45 % margin.

So: **the ~100× the project needs is 37× of unclaimed single-core engineering and ~3× of patch reduction.**
All four candidate architectures were priced against the *C*; re-priced against the shipping artefact, every
one is **slower than running the existing code at 8 patches**. That is the decisive finding.

Two scope notes. (a) Because the Julia per-patch fixed cost is 0.066× the C's, **patch reduction in the
emulator scales as an almost perfect 1/J with no Amdahl floor** — the C's 33 % floor does not exist in the
thing being built. (b) **Offline production is not cost-constrained at all**: the entire 2-seed × 2-scenario
ground truth cost 35 000 core-hours (17 h on 2048 cores). The compute case exists **only** for online
coupling.

---

## 3. What the patch ensemble is worth — MEASURED

Source: the owner's replicate-cell convergence experiment in `/home/jamirp/scripts/test_npatch/`
(one climate cell replicated 10 000× at npatch=5 ⇒ 50 000 realisations of the SAME cell; Amazon and
temperate), plus the two production seeds.

### 3a. npatch is NUMERICAL, not physical

npatch=50 vs npatch=25 (same seed1, same spin-up, 8 553 cells, 2000–2019): stems/patch **−0.06 %**,
Wooddens **+0.10 %**, SLA −0.03 %, minwscal +0.01 %, D95max +0.03 %, Height −0.07 %, Age +0.15 %.
The seedbank threshold `n_max·npatch·patcharea/100` scales with npatch by construction, so the selection
density (15.75 stems/patch) is npatch-invariant. **Cutting patches costs noise, not biology.**

### 3b. The 25 patches are worth far fewer than 25 samples — and the coupling is the seedbank

Production, npatch=25, both seeds, 45 093 cells. `deff = Var(between runs)/Var(resampling one cell's patches)`:

| quantity | ICC | n_eff of 25 |
|---|---|---|
| n_trees | 0.039 | 12.9 |
| Wooddens median | 0.085 | 8.2 |
| minwscal median | 0.148 | 5.5 |
| SLA median | 0.157 | 5.2 |
| D95max median | 0.177 | 4.8 |
| **Height median (the control — same stems, NOT inherited)** | **~0** | **~25** |

The Height-median row is the decisive control: measured on the identical stems in the identical patches,
it shows **no coupling at all**. Everything heritable is coupled; nothing else is. **The coupling is the
cell-level seedbank (`getsapling.c`, `cell->treelist`, filled `foreachpatch`), and nothing else.**

Cost of running P patches instead of 25, `sd(P)/sd(25)`:

| P | 12 | 8 | 5 | 1 |
|---|---|---|---|---|
| n_trees | 1.24 | 1.43 | 1.73 | 3.59 |
| Wooddens | 1.15 | 1.28 | 1.48 | 2.86 |
| D95max | 1.08 | 1.15 | 1.28 | 2.18 |

### 3c. At npatch=25 the C's own answer is already outside the 10 % band

Bootstrap CV of the cell estimator, Amazon, 50 000 patches, year 2010:

| quantity | n=5 | **n=25** | n=100 | n for CV<10 % |
|---|---|---|---|---|
| n_trees | 19.8 | 8.9 | 4.4 | 19 |
| vegc | 24.7 | **11.3** | 5.6 | 32 |
| Height median | 23.2 | **11.3** | 5.4 | 15 |
| Wooddens median | 7.4 | 3.3 | 1.7 | 3 |
| **D95max median** | 45.3 | **22.7** | 11.6 | **53** |
| minwscal median | 23.5 | **11.0** | 5.6 | 20 |

Confirmed on production: median |seed1−seed2|/mean at npatch=25 is n_trees 7.57 %, Wooddens 3.30 %,
**D95max 11.60 %**, minwscal 4.20 %. In the <2 stems/patch stratum (7 964 cells): tree count **31.6 %**,
carbon **42.7 %**. **For several acceptance quantities the target is noisier than the tolerance.** ADR 0106's
`max(10 %, the model's own two-run spread)` clause is therefore load-bearing, not decorative.

### 3d. The warming response is below the per-cell noise floor and enormous in aggregate

hist 2019 → ssp370 2099, paired per chain, 52 989 cells:

| quantity | median response | median 2-run noise | S/N | runs disagree on SIGN | AREA-MEAN resp / noise |
|---|---|---|---|---|---|
| n_trees | −2.31 % | 8.79 % | 2.08 | 24.7 % | −0.62 % / 0.033 % |
| vegc | −4.12 % | 12.09 % | 2.94 | 16.3 % | −11.28 % / 0.055 % |
| Wooddens median | — | — | 1.25 | **33.2 %** | — |
| D95max median | — | — | **0.92** | **36.7 %** | — |
| minwscal median | — | — | 1.68 | **34.4 %** | — |

**[DECISION IMPLICATION] the trait response is not a per-cell observable in the reference data.** Scoring
per-cell trait response against a single seed is scoring against noise. It must be scored on a
multi-seed mean and/or in aggregate.

### 3e. Deattenuation: it is TWO broken axes, not four

Treating the single-seed truth as a noisy regressor and estimating reliability λ from the two seeds:

| axis | response slope as scored | λ | deattenuated |
|---|---|---|---|
| SLA | 0.851 | 0.79 | **1.08 — already correct** |
| minwscal | 0.689 | 0.70 | **0.99 — already correct** |
| Wooddens | 0.346 | 0.55 | 0.63 — broken |
| D95max | 0.163 | 0.32 | 0.51 — broken |

The two broken axes are exactly the two ADR 0046/0049 attribute to **within-PFT differential survival** —
the mechanism ADR 0025 removed by construction. Every arrow points the same way.

---

## 4. What is REFUTED (record these so they are not re-proposed)

1. **One big patch instead of 25 small ones.** Recruitment ∝ `f_sap = exp(−LAI)`
   (`establishmentpft_ind.c:24-32,:124`, α_r=2.0, k=0.5). Merging 25×225 m² into 1×5625 m² replaces
   `mean(exp(−L))` by `exp(−mean L)`: **recruitment falls 81.3 % (Amazon) / 21.4 % (temperate)**. The
   brightest 5 % of patches carry 64.8 % of all recruitment. **Dead.**
2. **Structural stratification / quadrature over patches.** Measured variance-reduction factor at k=5 for
   trait medians: **1.00–1.13**. The trait axes are orthogonal to stand structure (each its own PCA
   eigenvalue ≈1.0; |corr| ≤0.27). Works only for carbon (VRF 6.7), and the *implementable* version
   (stratify on last year's agb) drops even that to 2.11. **Dead for the acceptance quantities.**
3. **Time-averaging as a substitute for ensemble-averaging.** Patch-anomaly e-folding time **32–41 yr**
   (n_trees, vegc). Eleven years of output buys ×1.11–1.18. **Dead.**
4. **A smooth trait density with no individuals (the ED/PPA/moment-closure family).** Fails for a specific
   measured reason: `bm_inc_counter` (the per-individual negative-growth run-length, which multiplies
   `mort_npp` and `mort_water` and hard-kills at 5) is **strongly trait-correlated** — PFT 3
   `E[Wooddens|c] = 236 883 … 281 936` across c=0…5, a **+19 %** gradient. 11.69 % of stems have c≥1 and
   they carry **44.8 % of all mortality mass and 37.8 % of all deaths**. Factorising trait ⊥ c drops
   `Cov_c(E[mort|c], E[trait|c])`, which is **39–329 %** of the total selection covariance and **reverses
   its sign in PFTs 1, 2, 3 and 5**. Repairing it needs 1 260 quadrature nodes instead of 90 ⇒ 3.7× not
   31.8×. Also: the deterministic bankruptcy kill (`mort:=1` at c≥5 or `leaf_c < leaf_carbon_sapl(SLA)`) is
   **0.77 % of stems**, trait-selective (killed/population ratio 1.09–1.29 on Wooddens), contributing
   ~0.12 %/yr of the trait mean — the same order as the entire annual within-PFT signal — and Gauss
   quadrature on a step converges O(1/M). **This is the load-bearing reason to keep a per-individual roster.**
5. **A cheap "shadow ensemble" of rosters without daily physics.** Three of the four hazards are not
   computable without the daily loop: `mort_water` needs `tree->water_stress`, accumulated daily per
   individual from that individual's own `wscal` against **that patch's** soil water and gated on
   `soil->temp[0] > 10` (`waterstress_tree.c:31-38`); `mort_npp` needs per-individual `bm_delta` and
   `leafarea_real`; `lmtorm` needs `wscal_mean`. Collapsing `mort_water` to a patch mean **flips the sign of
   the minwscal selection differential in PFTs 0, 1 and 2** (4.28 M of 10.59 M stems). It would **close** a
   response channel. **Dead.**

---

## 5. What SURVIVED, and it is mostly cheap

1. **[MEASURED] Asymmetric mean field — share the soil column, never the canopy.** Between-patch CV of
   patch-mean `wscal` within a cell: **median 0.0126, p90 0.0667** across 41 587 cells. One soil column per
   cell is defensible *on measurement*. Light is not: mean-field transmitted light at fixed height is
   **−31 % at 5 m and −47 % at 20 m** (Amazon), and the dominant tree holds 69 % (p90 92 %) of patch biomass.
   This matters because the 23-layer water + permafrost column is the Amdahl floor that caps every
   cohort-only scheme at 3.1× (boreal) / 7.2× (temperate).
2. **[MEASURED] Trait-dependent mortality recovers the wood-density selection almost for free.** Keeping
   `mort_max = 10^(wdmort_1 + wdmort_2/(wooddens/1e6))` **per-individual** preserves the one-year Wooddens
   selection differential at a ratio of **0.98–1.06 across all seven PFTs** even when the growth-efficiency
   logistic is collapsed to its patch mean. Collapse `mort_max` too and it drops 47–100 % and **flips sign in
   PFTs 3, 5, 6**. `src/trait_mortality.jl` is already written, already wired, **default OFF**, level effect
   already measured at t=23.5. This is the guardrail-4 corollary case exactly.
3. **[MEASURED] A bounded Beta on each PFT's own trait interval beats the shipped copula 2–3×.**
   Two-moment fit, no fitting procedure, median per-cell KS **0.042–0.073** vs the copula's **0.129–0.173**
   (400 cells/PFT with ≥150 stems, historic 2019). The reflect-into-interval rule in `new_tree.c:38-61`
   is why a bounded family is the right one.
4. **[MEASURED] Light-axis quadrature for the recruitment kernel.** Gauss nodes on the LAI axis recover
   **99.1 %** of the true recruitment kernel at J=4 (Amazon; 99.997 % temperate) vs **49.5 %** for
   stratification. And the closed-form two-moment correction `E[exp(−L)] = exp(−L̄ + σ_L²/2)` fixes a
   **median −12.7 %** global recruitment bias to a median **+0.04 %**. ⚠ Caveats: measured on >5 m stems
   only (~7 % of the canopy) and the correction factor has p90 4.57 / p99 12.51, so it is **not** validated
   in dense tropical canopies; and σ_L² is not stationary — between-patch CV of stand LAI rises 0.259→0.304
   hist→ssp370.
5. **[FREE] The determinism dividend.** Predicting the ensemble *expectation* rather than drawing a
   realisation halves the error variance against a stochastic target: **+2.9 to +14.4 percentage points of
   cells inside the 10 % band**, at zero compute cost. This accrues to any deterministic emulator and was
   not being counted.
6. **[FREE] Score the response on a multi-seed mean and report the deattenuated slope** (§3e). Two more
   reference seeds cost **35 000 core-hours ≈ 17 h on 2048 cores** — the highest-value compute purchase
   identified anywhere in this analysis.

---

## 6. PROPOSED strategy — attribute the error before removing the cost

**This section is under discussion and is NOT accepted.**

The owner's diagnosis is correct: too many things are being changed at once, and the record shows the
symptom. Offline Component S looks excellent (count OOS R² 0.982, per-cell-mean R² 0.9989) while the coupled
driver is 1.35×/1.15×/1.38×/**0.52×**/1.04× on terminal density across five biome cells — and ADR 0105
records that *"offline bias predicts the coupled error with the wrong size in every cell and the wrong sign
in two."* That is the signature of **confounded error sources**: S's demography, F's physics, and the
feedback between them are currently measured only in combination.

### The ladder. Each rung isolates exactly one thing. Do not climb two at once.

| rung | what runs | what it isolates | decides |
|---|---|---|---|
| **0** | re-score existing artefacts | the **yardstick** | multi-seed target + deattenuated slope (§3e); noise floor per cell per quantity |
| **1** | S alone, fed the C's own per-tree fluxes from the `ind` parquet | **S's demography** | does S reproduce FIT's roster given perfect physics? Trait-dependent death, Beta traits, selection channel all get tested here |
| **2** | S + the **real C** fast part in a closed annual loop | **the feedback**, with physics exact | if 1 passes and 2 fails, the defect is the loop, not either component |
| **3** | F alone, fed the C's own canopy | **F's physics** | the decadal canopy drift (F's fpc moves 1.56× where the C's moves 0.90×) |
| **4** | S + F coupled | the residual | now attributable, because 1–3 are clean |
| **5** | speed | — | per-tree loop (37×) → shared soil column → 8–12 patches (3×) → threads/GPU |
| **6** | ESM coupling | — | — |

Rung 1 needs **no C/Julia mixing at all**: the `ind` parquet already *is* the C's fast-part output at
per-(Cell, Patch, Year) resolution. ⚠ But note the standing warning in the `fdiff-validate` skill — a
teacher-forced arm was measured **worse in all five cells** (0.149→0.277, 0.086→0.153, …). That inversion
is itself a rung-1 finding to explain, not a reason to skip the rung.

### Rung 2 is feasible. Three routes, ranked.

* **(a) Annual external-demography hook in the C — RECOMMENDED.** The entire demography is one
  `foreachpatch` block, `src/lpj/annual_natural.c:55-232`: `annualpft` (turnover/allocation/mortality,
  :73), `light` (:118, dead in `individual=true`), fire (:121-135), `establishmentpft_ind` (:145). A config
  flag that dumps the roster + accumulated per-tree fluxes at the top of that block and reads a replacement
  roster at the bottom is a bounded C patch. The project already has the patch-and-rebuild workflow
  (`patches/lpjmlfit_daily_grass_gpp.patch`). Per-year file I/O is free at a handful of cells.
* **(b) Restart-file year-stepping.** Run the C one year with `-DFROM_RESTART`, have Julia rewrite the
  restart, run the next year. No linking, no MPI surgery — but needs a writer for the binary restart
  format (`fwritecell.c` → `fwritestandlist` → `fwritestand` → `fwritepftlist`).
* **(c) `ccall` into a shared-library LPJmL.** Global state + MPI + its own I/O. Not worth it.

**Rung 2 is a throwaway test harness, not a deliverable.** Build it as cheaply as possible. Its only job is
to answer "is the defect in S, or in F, or in the loop?" — and the owner is right that a C-fast-part
emulator is not itself a product. It *is*, however, a scientific result: it isolates whether the learned
demography reproduces FIT, which is the project's novel claim.

### Why speed comes AFTER, and in this order

Rung 5's ordering is forced by the measurement, not by taste: the per-tree loop is 37× and fidelity-free;
the shared soil column removes the Amdahl floor; the patch cut is the last ~3×. **GPU is deliberately last**
— 54 020 independent cells are already embarrassingly parallel on CPU, the 51× gap is single-core
inefficiency, and the workload (variable roster length, data-dependent branching, the λ bisection) is
warp-divergent. A GPU port of slow code is still slow code.

---

## 7. Consequences

* ADR 0092 gets its measurement; it stays OPEN until §6 is accepted.
* The `trait_mortality` default-off flag acquires a concrete, pre-registered flip criterion (rung 1).
* The project needs an **end-to-end emulator-vs-C timing** as a standing gate. None exists today
  (`grep` for speedup/faster across MEMORY + all four STATE files returns nothing), which is how a 3.8×
  regression went unnoticed.
* Any future patch-reduction proposal must be priced against the **Julia** cost model, not the C's.
* Nothing here proposes a CO2 feature; every hazard input is VPD, `wscal`, air temperature and growth
  efficiency (ADR 0107 respected).

## 8. Data-quality notes found in passing

* `single_n10000_latm3p25_lonm60p25` actually holds the cell at **lon −60.25, lat +0.25**, not −3.25.
* `single_n2048_lat50p2_lon10p7` and `single_n64_lat13p06_lon52p38` have **no model output on disk**.
* `analyze_patch_sampling.py` averages over **rows**, including grass (1 row/patch, ~0 carbon, 8.9–14.6 % of
  rows) and dead stems (1.7–3.6 %); its per-patch CV is 71–77 % against 46–56 % for the correct stand
  density, and its level is 3 677 vs 20 873 gC/m² (Amazon). The experiment design is sound; the statistic
  is not the one the acceptance criterion names.
