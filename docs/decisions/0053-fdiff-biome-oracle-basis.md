# ADR 0053 — the M3 F-side oracle: two reference-basis artifacts that outweigh the physics they hide

- **Status:** accepted (2026-07-30)
- **Line:** M (multi-cell coupled S+F+E, P3) — ADR block 0050–0069
- **Builds on:** ADR 0050 (per-cell inputs), ADR 0051 (the C-faithful leaf-on `wscal`), ADR 0052 (no soil
  ice; the too-dry dry cells). **Supersedes nothing.**
- **Code change:** none in `src/` — every committed baseline is byte-identical. Two new scripts and two new
  committed reference tables; `wscal_leafon` stays `false` by default.

## Context

M3's F-side task was recorded as "the cheap win, still unclaimed": four single-cell C runs already carried
`a_lai_stand` / `a_fpc_stand` / `d_gpp` / `d_transp`, so a per-cell F_diff-vs-C oracle for five biomes
needed no new HPC run. ADR 0052 had already done the water side (`rootmoist`); this extends the same
pattern to carbon, water flux and structure.

The `residual-diagnosis` step came first, and it is the whole story of this ADR: **before measuring
anything, state the reference basis.** Two of the bases were wrong in ways that would have produced
confident, publishable, false fidelity numbers.

## Artifact 1 — the C's daily fluxes are ALL-PFT; F_diff's canopy is tree-only

`d_gpp` / `d_transp` are grid-cell totals over every PFT. The coupled driver builds its core from
`M_individuals_<name>_2010.csv`, which keeps only `type <= 6` — so F_diff has **no grass at all** (verified
in the probe: `count(is_grass) == 0` in all five cores). The grass share is not a rounding term:

| cell | grass share of the C's cell-total GPP | grass share of FPC |
|---|---|---|
| `boreal_siberia` | **42.4 %** | 55.6 % |
| `mediterranean_iberia` | 28.4 % | 52.9 % |
| `semiarid_sahel` | 19.3 % | 40.1 % |
| `temperate_hainich` | 5.8 % | 17.3 % |
| `tropical_amazon` | 0.2 % | 1.1 % |

Rather than caveat it, it was **removed exactly**. The binary already has the custom per-PFT daily grass
GPP output (`conf.h` id 419, `patches/lpjmlfit_daily_grass_gpp.patch`), and a single-cell re-run costs ~9 s,
so four re-runs (`CELL=<c> RUNTAG=M_grass_val bash scripts/run_fdiff_grass_gpp_cell.sh`) give
`gpp_tree = d_gpp − d_grass_gpp` for every cell.

Note the second column: **the FPC share over-states the flux share in every cell** — by 1.31× (boreal),
1.86× (mediterranean), 2.08× (Sahel), 2.98× (Hainich) and 5.6× (Amazon, where both numbers are near zero so
the ratio is noise-dominated). Grass under a closed canopy is light-limited, so an FPC-based grass
correction — the obvious shortcut when no per-PFT flux output exists — would itself have been wrong, and
wrong in the same direction everywhere.

## Artifact 2 — the driver runs ONE patch; the C reports the 25-patch ensemble mean

`run_coupled_biomes.jl` and `wscal_leafon_probe.jl` pick the **modal** patch (most stems) out of the 25 in
the `ind` fixture. But `d_gpp` / `d_transp` / `a_fpc_stand` are **patch-ensemble means**, and the modal patch
is systematically denser than that ensemble — measured directly on the committed fixtures:

| cell | modal-patch FPC / ensemble-mean FPC | modal / ensemble stand LAI |
|---|---|---|
| `semiarid_sahel` | **1.72×** | 1.50× |
| `boreal_siberia` | 1.48× | 1.44× |
| `mediterranean_iberia` | 1.19× | 1.02× |
| `tropical_amazon` | 1.14× | 1.26× |
| `temperate_hainich` | 1.12× | 1.05× |

That is **the same magnitude as the flux biases being measured**, so a modal-patch comparison cannot
separate F's physics from the patch choice. Patches do not share light in the C either (`getfpar.c` is
per-patch), so the correct emulator-side ensemble is *run each patch independently and average the outputs*
— never one core holding all 25 patches' stems, which would make them compete inside a single canopy.

**This is load-bearing, not pedantic.** Correcting it flips a verdict:

| cell | tree-GPP ratio, MODAL patch | tree-GPP ratio, 25-patch ENSEMBLE |
|---|---|---|
| `semiarid_sahel` | **1.03** ("essentially exact") | **0.75** (a 25 % under-prediction) |
| `boreal_siberia` | 1.47 | 1.18 |
| `temperate_hainich` | 1.27 | 1.21 |
| `mediterranean_iberia` | 1.34 | 1.39 |
| `tropical_amazon` | 1.01 | 0.98 |

The Sahel number is the cautionary one: on the wrong basis it was the best cell in the set, and it is
actually the worst. It also flips the *sign*, so it would have contradicted ADR 0052's finding that F_diff
over-stresses dry cells, when in fact it confirms it.

## What IS established

1. **Seasonal phase is excellent in every biome** — monthly-climatology correlation between F_diff and the
   C, 2010–2019: tree GPP **r = 0.870–0.999**, ET **r = 0.858–0.999**. Correlation is insensitive to level,
   so this result survives both basis artifacts above and is the solid F-side claim: F's phenology, light
   response and temperature response track the C across boreal→tropical.
2. **The GPP level verdict, and it DECOMPOSES.** A 10-yr-mean ratio is useless on its own here, because
   under `slow = nothing` F's canopy is free-running and drifts **−13.5 % to +64.5 %** in FPC. Scoring F's
   year *k* against the C's year *k* and reading the **shape** of the ratio series separates the two failure
   modes — a ratio walking monotonically away from 1 is structural drift; a flat but offset ratio is a
   genuine flux-level bias:

   | cell | 2010 → 2019 year-matched GPP ratio | shape | diagnosis |
   |---|---|---|---|
   | `tropical_amazon` | 0.97 0.89 0.92 0.93 0.97 1.01 1.02 1.00 1.01 1.03 | **flat ≈ 0.97** | F is right, within 3 % |
   | `temperate_hainich` | 1.12 1.16 1.16 1.21 1.20 1.24 1.22 1.25 1.23 1.25 | **flat, offset** | genuine +12 % flux-level over-prediction, creeping to +25 % |
   | `boreal_siberia` | 0.80 0.93 0.95 1.07 1.09 1.11 1.29 1.53 1.40 **1.70** | **monotone up** | DRIFT — unbounded canopy growth (FPC +64.5 %), not a flux bias |
   | `semiarid_sahel` | 1.10 0.89 0.80 0.76 0.73 0.68 0.66 0.67 0.65 **0.59** | **monotone down** | DRIFT — canopy dieback (FPC −13.5 %) |
   | `mediterranean_iberia` | 1.42 1.72 1.31 1.70 1.54 1.34 1.12 1.09 1.25 1.17 | **noisy, 1.09–1.72** | excessive interannual volatility |

   So the 10-yr means (boreal 1.18, Hainich 1.21, mediterranean 1.39, Sahel 0.75, Amazon 0.98) are
   **misleading in three of five cells**: boreal's 1.18 is the midpoint of a run from 0.80 to 1.70, and
   Sahel's 0.75 is the midpoint of a collapse from 1.10 to 0.59. Neither is a flux-level bias.
   Least-drifted (year-1) ratios: Amazon 0.97 · Sahel 1.10 · Hainich 1.12 · mediterranean 1.42 · boreal 0.80.
3. **The Sahel decline is ADR 0052's dry-cell bias, observed end-to-end.** ADR 0052 measured that F_diff's
   root-zone water runs too dry in dry cells and therefore over-stresses them. Here that shows up as its
   consequence: the Sahel canopy starts correct (1.10 in 2010) and then dies back monotonically to 0.59.
   The two findings are one mechanism, seen at two points in the chain.
4. **F under-predicts tree FPC in all five cells** (0.31–0.72×) while stand LAI is 0.57–1.32× — fewer/less
   extensive crowns carrying comparable or greater leaf area. The FPC deficit is robust to artifact 2,
   because it is measured *despite* F starting from a patch 1.12–1.72× denser than the ensemble.
5. **ET is biased high by 11–35 % even though F carries no grass transpiration**, so the tree-only ET bias
   is *larger* than the table shows. This is a new, concrete candidate mechanism for ADR 0052's too-dry
   root zone: over-transpiration would drain the column. ADR 0052 guessed at the `_infiltrate` cascade and
   the absent `w_fw` reservoir; this points at the demand side first, and it is cheaper to test.

## What is NOT established

- **Whether Hainich's flat +12 % is photosynthesis or canopy reconstruction.** It is the one clean
  flux-level bias in the set and it is unattributed. The kernel-isolation drive (`fdiff-validate`: drive F
  with the C run's own daily FAPAR so a GPP gap cannot come from the canopy) is the next measurement, and
  `d_fapar` is already in all five runs.
- **Why boreal grows without bound and Sahel dies back.** Both are `annual_step!` allocation/growth
  behaviour, not daily flux behaviour, and neither has been traced to a term. The boreal case is additionally
  contaminated by ADR 0052's missing soil ice.
- **Any statement about a coupled run.** These are `slow = nothing` numbers by construction.

## Consequences

- Two reusable scripts + two committed tables (`test/testitems/references/M_fdiff_oracle_biomes.csv`,
  `..._annual.csv`, `M_fdiff_oracle_meta.json`), each recording its own basis and stating which quantities
  are splittable. `transp` and `a_lai_stand` are **not** splittable (no per-PFT daily transpiration output
  exists; `d_nv_lai` is the *within-crown* LAI, `lai_tree.c:29`, not a stand LAI) and are labelled as such.
- **`biome_coupled_tests.jl` item 2 pins per-cell mean LE and GPP on the MODAL-patch basis** (±2 %/±3 %).
  Moving the production driver to the patch ensemble is the right fix, and it **will** move those baselines
  — a deliberate regeneration under guardrail 4, not an incidental one. Not done here: this ADR establishes
  the basis and the measurement; the driver change is its own change with its own baseline move.
- Every number here is a **`wscal_leafon = true`** number, passed explicitly. The package default stays
  `false` and flipping it remains the open two-sided integration point with line S (ADR 0051) — line S is
  mid-S2 and has not answered, so M3 takes option (b) from its own handoff: run explicitly, and say so.
- ADR 0052's two caveats stand and are carried in the probe header: `boreal_siberia` has no soil ice, so
  its water-stress-like terms are unreliable and must not be averaged into a headline; F_diff runs too dry
  in dry cells.
