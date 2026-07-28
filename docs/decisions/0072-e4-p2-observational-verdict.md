---
status: "accepted"
date: 2026-07-28
deciders: "line E (session 1), autonomous per STEERING_PROMPT.md"
consulted: "DEVELOPMENT_PLAN.md §Phase 4 + §7 (H is the residual, validate it hardest), ADR 0017 (self-contained SEB), ADR 0070 (the reference), ADR 0071 (wind/psurf)"
informed: "line M (runs the closure in the coupled loop), MEMORY.md, lines/E/STATE.md"
---

# The P2 verdict: E's Rn and T_skin are observationally verified; H is verified in the MEAN but not in nocturnal variability

## Context and Problem Statement

Component E's outputs have carried an `[ASSUMPTION]` tag since they were written: *physically plausible but
invented quantities validated only out-of-model*. `DEVELOPMENT_PLAN` §Phase 4 sets the gate as "energy closes;
LE/H/T_skin plausible vs flux towers", and §7 sharpens it: **H is the residual and PLUMBER2 flags it as the
hardest flux to get right — validate it hardest.** With the reference staged (ADR 0070) and wind/psurf sourced
(ADR 0071), what does the closure actually score against towers, and what may now be claimed?

## Decision Drivers

- **Attribution.** `FToE` hands E `le` **already formed** as λ·ET (`src/components/fast.jl:236`:
  `le = et/86400 · LAMBDA_VAPORIZATION`, `et = transp + evap + interc`). LE is therefore **F's** number; E's own
  predictions are **T_skin, H (the residual) and G**. A comparison that scores "E's LE" would be scoring F.
- **The claim must survive being quoted.** Any `[VERIFIED]` must name the sites, the sample size, the flux
  basis, the acceptance band and the failure modes — not a single flattering statistic.
- **Guardrail 4** — no default may change as a side effect of a validation, and flipping one is an integration
  point with line M.

## Considered Options

- **Experiment A — the closure alone:** drive `solve_seb` with a tower's own forcing **and the tower's measured
  LE**; score H, T_skin, Rn.
- **Experiment B — coupled:** F's ET → LE → E, scored the same way.
- **Score LE against the towers** as the headline P2 number.

## Decision Outcome

Chosen: **Experiment A is the P2 gate for Component E**, with Experiment B deferred as the *coupled* test (its
difference from A is exactly F's ET error, which belongs to F/M, not to E). Scoring LE as E's result is
rejected outright — it would credit or blame E for F's water balance.

Everything the closure needs is taken from the observations where one exists: driving `swdown/lwdown/tair/
psurf/wind`, the LE (`le_cor`), the **albedo from the tower's own Σ SWup/Σ SWdown**, canopy height, and —
load-bearing — `SEBParams.z_ref` overridden with each site's **measurement height** (43.5 m at DE-Hai, not the
10 m default; `g_a` is evaluated at that level). `t_soil` reproduces `solve!`'s τ = 30 d EWMA on **daily-mean**
Tair (applying the per-step recursion at 30 min would decay ~48× too fast).

Pipeline: `scripts/build_e_seb_validation_table.py` → `scripts/validate_e_seb_vs_plumber2.jl`
(SLURM `E-sebtable2` 1622120, `E-e4a3` 1622127). **497 936 tower steps at 4 sites.**

**A data trap found while freezing the regression fixture, and corrected before these numbers were accepted:**
at DE-Hai the *uncorrected* `le` is all-NaN for **2010–2012** (that is where the site's 23.1 % missing LE sits)
and PLUMBER2's energy-balance correction emitted **≈0 instead of a fill value** there (annual mean `le_cor`
0.39 / −0.09 / 0.04 W/m² against 30–40 W/m² in 2000–2009), while `h_cor_uc` disappears. A finiteness filter
happily kept 36 550 such rows, and feeding the closure LE ≈ 0 pushes all the available energy into H — it
inflated DE-Hai's apparent H bias to +39.8 W/m². The builder now **also requires the uncorrected `le` to be
finite**, which reduces DE-Hai to its 175 344 jointly-valid steps (2000–2009) and matches ADR 0070's coverage
figure exactly. The other three sites are unaffected.

### What the data says [VERIFIED 2026-07-28]

| site | steps | H bias | H RMSE | H R² (all / day / **night**) | T_skin RMSE / R² | Rn R² |
|---|---|---|---|---|---|---|
| DE-Hai (DBF, temperate) | 175 344 (2000–2009) | **+6.4** | 54.8 | 0.647 / 0.535 / **−1.02** | — (no LWup) | **0.986** |
| AU-Tum (EBF, temperate) | 134 898 | −19.2 | 80.3 | 0.569 / 0.390 / **−1.70** | 3.21 K / 0.773 | 0.989 |
| AU-ASM (ENF, arid) | 122 736 | −6.8 | 59.2 | 0.898 / 0.780 / **−1.01** | 2.59 K / 0.941 | **0.996** |
| AU-Rob (EBF, tropical) | 64 958 | −7.8 | 110.7 | −0.01 / −0.22 / **−5.62** | 3.34 K / 0.385 | 0.995 |

Daily means (**the model's native step**): H bias/RMSE/R² = +6.4 / 33.4 / 0.257 (DE-Hai), −19.2 / 37.8 / 0.125
(AU-Tum), −6.8 / 18.3 / **0.778** (AU-ASM), −7.8 / 34.5 / 0.256 (AU-Rob). Daily **T_skin RMSE 1.41–1.97 K,
R² 0.76–0.95**. At DE-Hai — the only site with an uncertainty band — **76.4 % of 3 653 daily means and 57.2 %
of 175 344 half-hours fall inside PLUMBER2's own `|h_cor_uc|`** (mean band ±40.94 W/m²).

**Therefore:**

1. **Rn is VERIFIED.** R² 0.986–0.996 with a bias of +1.95…+10.2 W/m² across four sites, under the towers' own
   albedo. The radiation path (`swnet + ε·LWdown − ε·σT⁴`) is right.
2. **T_skin is VERIFIED at the three sites where it is observable at all** (OzFlux `LWup`; ADR 0070): daily
   RMSE 1.4–2.0 K, R² 0.76–0.95; half-hourly RMSE 2.6–3.3 K. **Not** verified at Hainich — PLUMBER2 cannot
   observe it there.
3. **H is VERIFIED IN THE MEAN, NOT IN VARIABILITY.** Every site's mean bias (+6.4 to −19.2 W/m²) sits inside
   the dataset's own uncertainty, and **76.4 %** of DE-Hai daily means land inside the band. But the
   **day-to-day** daily R² is poor at the forest sites (0.257 DE-Hai, 0.125 AU-Tum), and **nocturnal H is wrong
   at every site** (R² −1.0 to −5.6, i.e. worse than predicting the nocturnal mean).
4. **The failure mode is named and one-directional: the closure runs too COLD at night.** Modelled
   `T_skin − Tair` at night is −3.38 / −2.62 / −1.82 K (AU-Tum / AU-ASM / AU-Rob) against observed −1.39 /
   −1.67 / −0.74 K — a 1–2 K over-cooling, i.e. too little nocturnal turbulent + ground coupling.
5. **The half-hourly R² is inflated by the diurnal cycle.** DE-Hai H R² is 0.647 half-hourly but 0.257 on daily
   means: most half-hourly variance *is* the day/night swing, which any closure driven by observed SWdown gets
   right. Quote the daily number when claiming skill.
6. **The stability correction earns its keep, and its default is too weak.** Night H RMSE with the
   bounded-Richardson factor ON vs OFF: 37.0 vs 41.7 (DE-Hai), 29.7 vs 46.4 (AU-ASM) W/m² — so ON is right.
   A (`stab_amp`, `stab_k`) sweep is **monotone in amp** at both sites: `amp = 0.9` gives night RMSE 36.1
   (DE-Hai) and 24.2 (AU-ASM) vs 37.0 / 29.7 at the 0.75 default. This confirms `SEBParams`' own comment that
   the 0.25 floor under-suppresses stable turbulence. **No default was changed** (guardrail 4) — see below.
7. **AU-Rob is a suspect site, not an E failure.** Its own tower energy budget is the worst of the nine staged
   (closure slope 0.599) and its H is unpredictable even in daylight (R² −0.22) while its T_skin still scores
   R² 0.762 daily. Treat its H as a data problem pending diagnosis.

### Consequences

- Good, because `MEMORY.md`'s `[ASSUMPTION]` can be replaced by a **quantified** statement with sites, n, basis,
  band and named failure modes — which is what the P2 gate was for.
- Good, because the evidence is now a **CI-enforced regression gate**, not a one-off report: two committed
  extracts sampled **every 12th day of year at every 3rd hour across the whole record**
  (`test/testitems/references/e4_seb_drive_{DE-Hai,AU-ASM}.csv`; H bias +4.5 / −6.4 W/m², H R² 0.667 / 0.910,
  Rn R² 0.988 / 0.996, T_skin R² 0.935, 59.8 % inside the band) re-run the same Experiment-A comparison inside
  `test/testitems/energy_closure_tests.jl` with bounds set loosely around those values. **That gate paid for
  itself immediately** — a first attempt at a single-year fixture landed inside DE-Hai's broken 2010–2012
  window and reported +39.8 W/m², which is how the `le_cor ≈ 0` trap above was found. The night-cold-bias is pinned as a **sign** assertion, so a future fix trips the test and
  forces this ADR to be superseded rather than silently drifting.
- Bad, because **nocturnal H is not fit for purpose yet.** Anything that depends on night-time H or on the
  night skin temperature (a coupled ESM's stable boundary layer, dew/frost formation) inherits an R² < 0 flux.
  The next E step is the nocturnal diagnosis, not more sites.
- Bad, because `stab_amp = 0.75` is now known to be sub-optimal against observations while remaining the
  default. Raising it changes every coupled/biome baseline ⇒ **integration point with line M** (raised in
  `lines/M/STATE.md`), and the sweep is monotone to the parameter's bound, which suggests the *functional form*
  (a bounded tanh surrogate) is the real limitation, not the coefficient. Do the diagnosis before the retune.
- Neutral: Experiment B (F's LE → E) is not run here. It is the **coupled** number and belongs with M's
  multi-cell work; A is what isolates E.

## Pros and Cons of the Options

### Experiment A (chosen)

- Good, because it removes F's ET error from the comparison entirely — a miss is unambiguously E's.
- Good, because every boundary condition can be taken from the tower (albedo, heights), so the only unobserved
  input is `z0m = 0.1·h_can`.
- Bad, because it does not test the coupled system a user actually runs.

### Experiment B (coupled)

- Good, because it is the configuration that ships.
- Bad, because F's ET bias and E's closure error are then inseparable — exactly the attribution failure that
  makes "our LE is off by X" an unactionable statement.

### Scoring LE as the headline

- Good, because LE is the flux with the best observational constraint.
- Bad, because **E does not compute LE** — it receives λ·ET from F. Reporting it as E's skill would be false
  attribution, and would hide that E's own hardest output (nocturnal H) is the one that fails.

## More Information

- Report: `<energy_reference>/derived/seb_validation/e4_experimentA_report.txt` (per-site skill, the mean
  diurnal cycle, the stability sweep). Driving tables + `.meta` in the same directory; regenerate with the two
  scripts above (procedure in the `plumber2-reference` skill).
- Test: `test/testitems/energy_closure_tests.jl` — *"Component E — P2 observational gate vs PLUMBER2 towers
  (E4 Experiment A)"*.
- Supersede this ADR when the nocturnal diagnosis lands (a stability-form change, a `lambda_g` calibration, or
  a G-model change) — the numbers above are the pre-fix baseline.
