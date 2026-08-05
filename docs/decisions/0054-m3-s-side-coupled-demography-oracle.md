# ADR 0054 — M3 S-side: the coupled demography/trait oracle, and the AR recursion behind the count drift

- **Status:** accepted
- **Date:** 2026-08-05
- **Line:** M (multi-cell coupled S+F+E, P3)
- **Supersedes / relates to:** ADR 0053 (the M3 F side, same five cells, same window), ADR 0051
  (`wscal_leafon`), ADR 0052 (the two F soil-water residuals), ADR 0023 (artifact pinning), ADR 0031
  (the complete seven tree PFTs)

## Context

ADR 0053 closed M3's **F side**: with demography held out (`slow = nothing`), F_diff's tree GPP / ET / FPC /
stand LAI were scored against the C oracle for all five biome cells, on bases fixed by construction rather
than caveated. Its verdict — seasonal phase excellent everywhere, level decomposing per cell into one genuine
flux bias, two drifts, one volatility case and one clean pass — is unchanged by anything here.

What remained was the **S side**: with Component S back in the loop, does the coupled emulator reproduce the
C's per-cell tree numbers and the standing community's trait distribution? That question cannot be answered by
line S's offline evaluation, which scores table against table. A coupled rollout is a *recursion*: the count
DRF's own prediction becomes next year's `n_prev` feature, and its demographic ratio reshapes the canopy that
produces next year's flux features. Only a closed-loop run can see what that does.

## The reference basis

`scripts/extract_biome_slow_oracle.py` builds the C truth from the annual `ind` parquet (historic, seeds 1 and
2, 2010–2019, the five biome cells) and commits it as `test/testitems/references/M_slow_oracle_counts.csv`,
`M_slow_oracle_traits.csv` and `M_slow_oracle_meta.json`. ADR 0053's four basis checks were applied to the S
side, as its handoff required:

1. **Tree-only.** `Type <= 6` via the imported `TREE_TYPES` (ADR 0031), `isdead == 0`. Grass is emitted with
   every tree field **zeroed**, so a grass row does not add noise to a trait marginal — it adds a spike at 0.
2. **Per-patch, not per-cell.** Component S's count target is `n_living` per **(Cell, Patch, Year)** and the
   coupled driver runs **one** patch, while the C emits **25 independent patches** per cell-year. The
   like-for-like reference is therefore the per-patch ensemble **mean**; the per-cell total is ~25× larger.
3. **Year-matched.** Per-year rows only. On the F side three of five 10-yr-mean ratios were actively
   misleading; the same is true here, and more sharply.
4. **The >5 m population.** The `ind` writer emits only stems `height > height_min = 5 m`
   (`fwriteoutput_ind.c:84`), so every count here — and every count S was trained on — is that population.
   Self-consistent, but stated rather than assumed.

**Independent cross-check of the population.** The 2010 per-cell totals this extractor produces equal
`M_cells.csv`'s `n_trees` **exactly** for all five cells (122 / 282 / 214 / 272 / 276), and that column was
derived from the same `ind` table by a different script (`extract_cell_individuals.py`) months earlier. Two
extractors, one population — this is evidence the tree filter agrees end to end, and it is now a CI assertion.

**Noise floor.** LPJmL-FIT is stochastic (RAND48 + `-DPERMUTE`), so seed1 and seed2 are two equally valid
realizations of the same cell and climate; their disagreement on a statistic is the irreducible error. Every
statistic is emitted for both seeds. The count floor is 0.20–1.36 stems (2.6 % boreal → 29.0 % Amazon, which
has only 4.7 trees per patch).

**Configuration, because every number is conditional on it.** `wscal_leafon = true` passed explicitly
(ADR 0051; the default stays `false` until line S schedules the two-sided flip). The pinned `_t8` pair, with
`nfeat`, `colnames` and `cond_cols` re-checked against `flux_feature_vector`/`live_flux_cond` at load. A `t9`
`.rcop` exists on `/p/tmp` but has **no matching `.drf`** — a half-published pair, deliberately not adopted
(ADR 0023). **These five cells are in the `_t8` training population, so every number here is in-sample for the
count DRF.** Line S's held-out-cell OOS (R² 0.9824) is the out-of-sample statement; this measures the closed
loop, which offline scoring cannot see. A miss here is therefore a real miss, not an extrapolation artifact.

## Measurement

`scripts/biome_slow_oracle_probe.jl`, 10 coupled years per cell, one `run_coupled_cell` call per year so the
community can be snapshotted annually (the call is re-entrant — it rebuilds `bc_f` from `stand_structure_tof`
and all state lives in the mutable structs).

### Counts — the free-running rollout drifts, and the shape is the verdict

| cell | floor | C 2010 → 2019 | E 2010 → 2019 | E/C 2010 → 2019 | mean \|E−C\| in floors |
|---|---|---|---|---|---|
| `boreal_siberia` | 0.440 | 11.04 → 9.76 | 12.33 → 17.02 | 1.12 → **1.74** | **11.1** |
| `temperate_hainich` | 0.520 | 10.88 → 8.68 | 11.44 → 11.85 | 1.05 → **1.36** | **4.5** |
| `mediterranean_iberia` | 0.204 | 8.56 → 7.40 | 8.41 → 13.39 | 0.98 → **1.81** | **13.9** |
| `semiarid_sahel` | 1.220 | 11.28 → 13.48 | 13.46 → 12.79 | 1.19 → 0.95 | **1.4** |
| `tropical_amazon` | 1.364 | 4.88 → 4.56 | 4.06 → 3.91 | 0.83 → 0.86 | **0.5** |

Two cells are **at or inside the noise floor free-running** (Amazon 0.5×, Sahel 1.4×). The other three are
4.5–13.9 floors out, and in all three the per-year ratio series is **monotone**, not noisy: boreal
1.12→1.74, Hainich 1.05→1.36, mediterranean 0.98→1.81. A 10-year mean of those series would read 1.4, 1.2,
1.3 and hide the mechanism completely — which is precisely check 3.

### Attribution — it is the AR recursion, not the per-year count model

In the training table `n_prev` is the C's **own** previous `n_living` (`build_slow_runtime_table.py:572`),
never a prediction; a free-running rollout is off that basis by construction. Arm B overwrites `s.n_prev` with
the C's per-patch ensemble mean after each year — a driver-level intervention on a public mutable field,
nothing in `slow.jl` touched — putting that one feature back on its trained basis while leaving F's canopy
features exactly as they are.

| cell | free/floor | forced/floor | error removed |
|---|---|---|---|
| `boreal_siberia` | 11.1 | **3.2** | 72 % |
| `temperate_hainich` | 4.5 | **1.6** | 65 % |
| `mediterranean_iberia` | 13.9 | **3.9** | 72 % |
| `semiarid_sahel` | 1.4 | **0.6** | 59 % |
| `tropical_amazon` | 0.5 | **0.2** | 67 % |

And the drift **flattens**: boreal 1.12–1.17 across the decade instead of 1.12→1.74, mediterranean 0.98–1.18
instead of 0.98→1.81, Hainich 1.05–1.08 instead of 1.05→1.36.

**So 59–72 % of the free-running error is the recursion compounding a small persistent one-step bias.** The
per-year count model, given F's own (drifting) canopy features, sits at **0.2–3.9 floors**.

Decomposing the 2019 level, so the two effects are not conflated: in the three drifting cells the recursion's
own multiplicative contribution over the nine steps is `free₂₀₁₉ / forced₂₀₁₉` = **×1.49 boreal, ×1.26
Hainich, ×1.53 mediterranean** — i.e. a compounding **2.6–4.9 %/yr** — while the remainder of the +36–81 %
total excess is the **year-1 level offset** the run starts with (×1.05–1.12, itself partly the modal-patch
initialization below). The recursion is the larger of the two in boreal and mediterranean and roughly equal
in Hainich; neither is the whole number, and quoting the total as "the recursion" would overstate it.

This does not exonerate the count channel — a persistent one-step bias is a real bias, and the recursion is
part of the deployed system, not an artifact of the measurement. What it does is **relocate** the defect: the
lever is the systematic sign of the one-step error and the absence of any anchor on the count recursion, not
the DRF's conditional accuracy.

### Is the drift inherited from the F-side canopy drift?

Partly, and the honest answer is "directionally, not quantitatively". 2019/2010 ratios:

| cell | F fpc | C fpc | F lai | F agb | count ratio drift |
|---|---|---|---|---|---|
| `boreal_siberia` | 1.56 | 0.90 | 1.86 | 2.17 | 1.56 |
| `temperate_hainich` | 1.27 | 1.00 | 1.47 | 1.73 | 1.30 |
| `mediterranean_iberia` | 0.98 | 0.67 | 0.60 | 1.52 | 1.84 |
| `semiarid_sahel` | 0.71 | 1.23 | 0.71 | 0.95 | 0.80 |
| `tropical_amazon` | 0.81 | 0.99 | 0.86 | 0.96 | 1.03 |

The sign of the F-vs-C canopy divergence matches the sign of the count drift in **4 of 5** cells, and at
boreal and Hainich the count drift equals F's FPC drift almost exactly (1.56 vs 1.56; 1.30 vs 1.27). But
mediterranean and Amazon do not follow quantitatively, and the teacher-forced arm above shows the recursion
alone accounts for ~70 % regardless. Inheritance from ADR 0053's canopy drift is a **contributing** cause,
not the dominant one. Recorded as measured; not promoted to a mechanism claim.

### Traits — at or near the noise floor in 9 of 10 cell-axis pairs

Only `SLA` and `Wooddens` reach `TreePools` (`make_recruit_to_pools`); `D95max`/`minwscal` are drawn and
validated but have no per-tree consumer, so a coupled community cannot be scored on them. Scored
nind-weighted, because the roster is merged cohorts carrying density, not individual stems.

| cell | SLA \|d\|/floor (nqrmse) | Wooddens \|d\|/floor (nqrmse) |
|---|---|---|
| `boreal_siberia` | 0.9 (**1.31**) | 0.7 (0.21) |
| `temperate_hainich` | 2.0 (0.43) | 1.8 (0.24) |
| `mediterranean_iberia` | 1.1 (0.22) | 0.6 (0.19) |
| `semiarid_sahel` | **7.9** (0.25) | 0.5 (0.14) |
| `tropical_amazon` | 0.7 (0.24) | 0.2 (0.25) |

Nine of ten medians are within 2.0 floors. Two exceptions, both worth naming rather than averaging away:
`semiarid_sahel` SLA is 7.9 floors out — but on an extraordinarily tight floor (0.0002), so in absolute terms
it is 0.0374 vs 0.0392, a 4.6 % error. And `boreal_siberia` SLA has a correct **median** (0.9 floors) with a
wrong distribution **width** (nqrmse 1.31, the only value above 0.43): the coupled community's SLA spread is
off even though its centre is right. Distribution shape and centre are separate claims and are reported so.

### Invariants

Carbon closes at the S↔F handoff to 4.3e-13 – 3.4e-12 in every cell; the coupled `water_stress` reads 0.0000
(boreal, Amazon), 0.0033 (Hainich), 0.1745 (mediterranean), 0.4392 (Sahel) — i.e. exactly ADR 0051/0052's
picture, with the boreal 0.0000 being the missing soil ice and the Sahel 0.4392 the too-dry root zone.

## Decision

1. **M3 is closed on both sides.** The S-side verdict: **counts sit at the seed-to-seed noise floor in 2 of 5
   cells free-running (Amazon 0.5×, Sahel 1.4×) and at 0.2–3.9 floors in all five once the count recursion is
   anchored; the standing community's trait medians are within 2.0 floors in 9 of 10 cell-axis pairs.** The
   dominant remaining error in a free-running coupled rollout is **AR-recursion compounding of a persistent
   one-step count bias (59–72 % of the total)**, not the count model's conditional skill.
2. **Commit the reference, not the score.** `M_slow_oracle_{counts,traits}.csv` + `M_slow_oracle_meta.json`
   are committed fixtures; the skill measurement stays a cluster-only probe, because the pinned `_t8` pair is
   180 MB on `/p/tmp` and CI has no cluster. CI guards the fixture's **basis** instead (a new `@testitem` in
   `biome_coupled_tests.jl`): coverage, the per-patch identity `n_mean · npatch == n_cell_total` with
   `npatch == 25`, the two-extractor population cross-check against `M_cells.csv`'s `n_trees`, quantile
   monotonicity, a strictly positive q05 on every axis (the zeroed-grass-row tell), and `Height` q05 ≥ 5 m.
   These are the exact places the F side's two verdict-flipping errors lived.
3. **Stay pinned to `_t8`.** The `t9` `.rcop` is not adopted: no matching `.drf` exists, so it is a
   half-published pair (ADR 0023).
4. **Do not "fix" the recursion inside this ADR.** The candidate levers (anchoring the count recursion, or
   re-basing `n_prev` on an observable) touch `src/components/slow.jl`, which is line S's exclusive path
   (ADR 0029). This is raised as an **integration point with line S**, with the measurement attached.

## Consequences

- The P3 gate has a number and a mechanism, on a stated basis, for both components.
- **New integration point → line S:** the count recursion is unanchored, and a free rollout integrates a
  compounding 2.6–4.9 %/yr one-step bias into a ×1.26–1.53 recursion contribution over nine steps (the
  rest of the +36–81 % total 2019 excess is the year-1 level offset). Measured at 59–72 % of the total
  coupled count error.
  Any fix is S's file; M supplies `scripts/biome_slow_oracle_probe.jl`'s teacher-forced arm as the
  ready-made before/after test. This is the S-side counterpart of the F-side drifts in ADR 0053 and it
  matters more than either for a multi-decadal or online run, because it compounds without bound.
- The measurement is reusable and parameterized by cell, not forked per cell; the procedure (including the
  teacher-forced arm, which is the S-side of the `fdiff-validate` kernel-isolation drive) is captured in the
  `fdiff-validate` skill.
- **A general trap, now recorded:** never score a recursive emulator's free-running rollout without also
  running the teacher-forced arm. Free-running error attributes a compounding recursion to the model's
  conditional accuracy, and the two call for completely different fixes. Here it would have indicted a count
  DRF that is actually within 0.2–3.9 floors.
- Deliberately still open, unchanged by this ADR: moving the production driver from the modal patch to the
  25-patch ensemble (`lines/M/STATE.md` NEXT item 4 — the modal patch is 1.6–2.0× the ensemble mean stem count here:
  18 vs 11.04 boreal, 17 vs 10.88 Hainich, 22 vs 11.28 Sahel), which will move `biome_coupled_tests.jl`'s
  pinned per-cell LE and GPP and is its own deliberate baseline regeneration under guardrail 4.
