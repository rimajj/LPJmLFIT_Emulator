# 0365 — Release v4 / fold v5: the tree-population outputs (distributions, type shares, virtual trees, diversity indices)

* **Status:** accepted 2026-10-22 (owner: "do a-c, all of it" — (a) = package the parts of ADR 0363 that pass).
* **Follows:** ADR 0363 §9 and §12 (what passed), ADR 0364 §6 (mortality did not), ADR 0340/0358 (the release and its
  current version v2 / fold v3), ADR 0362 (v3 / fold v4 recorded, not current).
* **Code:** `python/src/lpjmlfit_emulator/landemu/population.py` (new), `emulator.py` (`start(setup, popsetup)`,
  `virtual_trees`, `diversity`), `scripts/build_population_release.py` (new), `scripts/run_emulator.py --population`,
  tests in `python/tests/test_landemu.py`; user guide `docs/emulator_release.md` § Tree population.

## 1. Decision

Ship, as **additive and opt-in** outputs of the release:

* the within-cell distributions (nine levels, 1–99 %) of eight variables of the living trees ≥ 5 m — height, biomass
  per tree, SLA, wood density, maximum rooting depth (`D95max`, a trait), drought threshold (`minwscal`), the ACTUAL
  95 % rooting depth (`D95`), age — with ADR 0363's arm `AQ` (one model per level, sorted), and the seven tree-type
  shares: 79 LightGBM models;
* **learned**, not computed, actual rooting depth and biomass per tree (ADR 0363 §9, §12: learned 0.78 vs 1.07 and 0.86
  vs 0.95 of a second run's error);
* virtual trees (N = round(25 × tree count per patch), Schaake shuffle from the run's own 2019 trees, **no-repeat
  donor draw**) and the functional-diversity indices of ADR 0363 §5, computed on request.

Not shipped: any mortality output (ADR 0363 §9, ADR 0364 §6 — no arm passed its bars).

**Additive:** a release with population maps runs exactly as its base unless a population setup is passed; with one,
every existing output is unchanged and the new ones carry a `pop_` prefix. (The first build named them without the
prefix; the four trait medians, which are also structure-map outputs, were then overwritten by the population map's —
caught by the on/off comparison below and fixed before release.)

## 2. Releases (`/p/projects/open/Jamir/esm_land_emulator_data/release/`)

| directory | = | for |
|---|---|---|
| `v4/` | `v2` + population (deployment: every run and leg trains) | use |
| `fold_gfdl-esm4_v5/` | `fold_gfdl-esm4_v3` + population (GFDL-ESM4 held out) | proving the package equals the scored pipeline |

`v2` / `fold_gfdl-esm4_v3` stay valid and unchanged; `v4` without a population setup is `v2`.

## 3. Gates and checks (all measured 2026-10-22)

* **Copied files:** all 26 model and setup files of v2 byte-identical in v4 (`cmp`).
* **Fold anchors** (P1a): the population setups' anchors equal the training table's test-row anchors exactly
  (255 150 rows, max |diff| 0).
* **Fold models** (P1b) vs the scored ADR 0363 predictions, fed the training table's test rows: height, biomass per
  tree, SLA, wood density, `D95max`, `minwscal`, `D95` — median |relative difference| 0, 99.5th percentile ≤ 1e-8.
  **Age: 4.2e-3** — and two refits of the scored Age model with the same code, data and settings differ from each other
  by 3.7e-3 (median 0.18 years at the median level): **the Age fit is not reproducible run to run** (LightGBM; every
  other variable is). Its gate is therefore "within 2× the measured refit-to-refit spread" (passed: 1.1×).
* **On/off** (v4, run m1, UKESM1 ssp370, 81 years): all 20 existing output arrays identical with the population on.
* **v2 with the new code** equals v4 without population: see §5.
* **End-to-end fold check** (`run_emulator.py --population --check`, every input from the daily weather): see §5.

## 4. Cost (one core, 1 050 cells × 81 years, `run_emulator.py`)

| | core-seconds per cell-year |
|---|---|
| v4 without population (= v2) | 7.14e-3 |
| v4 with the distributions and shares | 7.67–7.69e-3 (+7 %) |
| virtual trees + all indices, each time requested | 6.7e-3 |

## 5. Results of the remaining checks

* **v2 run with the new package code == v4 without population:** all 20 output arrays identical (run m1, UKESM1
  ssp370, 81 years; 7.10e-3 vs 7.14e-3 core-s per cell-year, timing noise).
* **End-to-end fold check** (`fold_gfdl-esm4_v5`, run m4, GFDL-ESM4 ssp370, every input computed from the daily
  weather, job 2670790): structure, stand and daily fluxes as for fold v3 — all OK except the cover of plant types 7
  and 8 (the known hot-day threshold artefact of the training table, ADR 0340 §3). Population: 64 of 72 distribution
  levels and 6 of 7 type shares OK (median |diff| ≤ 1e-9 of the size); **Age DIFFERS at 8 of 9 levels** (median 0.14–0.27 %
  of the size — the refit noise of §3, mean 34.38 vs 34.39 yr at the median level); **the larch share (type 6) DIFFERS
  in its tail** (median 1e-12, 99th percentile 0.12) — larch is plant type 7 of the stand map, which flags too, so most
  likely the same hot-day artefact (not traced row by row). Indices of the virtual trees (every 10th year) against the scored no-repeat virtual trees: 16 of 17 OK
  (medians ≤ 2.5e-4); **functional richness 99th percentile 0.058** (limit 0.05) — the convex-hull volume reacts to any
  upstream difference (a tree count that rounds to a different number of virtual trees changes the hull).
* Reading: the package reproduces the scored population pipeline from daily weather; every difference has a known or
  likely cause (Age refit noise; the hot-day artefact; propagation into a hull volume).

## 6. Known limits (stated with the outputs)

* Population ≥ 5 m only (the population of every other structure output). Smaller trees exist in the original
  (`LPJ_IND_ALL_HEIGHTS`) but are not emulated.
* Learned biomass per tree is a median 5 % below the allometry applied to the same virtual trees (ADR 0363 §12).
* Functional evenness 1.82× a second run's error (no bias; scatter).
* 3 % of panel cells have no living tree ≥ 5 m in the run's 2019 roster ⇒ no virtual trees there (the distributions
  are still emitted).
* The ratios of ADR 0363 §9 for distributions sit below 1 partly because the bar compares a smooth prediction with a
  noisy second run (the anchor alone scores 0.83–1.01); read them as "within the original's own spread".
* Age's fit is not reproducible run to run (§3); a rebuild gives a different, equally good Age model.
