---
status: "accepted"
date: 2026-07-28
deciders: "engineering agent on line S (full autonomy per STEERING_PROMPT.md). The DEFECT is a measured fact, not a judgement call; the decision recorded here is to fix it by widening the training population rather than by documenting the restriction as intended scope."
consulted: "the ACTIVE parameter file /home/jamirp/lpjml56fit/par/pft_lpjmlfit.js + src/lpj/fscanpftpar.c:177 + src/lpj/fwriteoutput_ind.c:82,140 (Type == 0-based pftpar index; ids 0-6 are trees, 7-9 grass, 10-21 crops), src/tree/new_tree.c (per-PFT trait intervals), the global census scripts/diagnose_ind_type_composition.py (job 1616777), the sibling frozen emulator /p/projects/open/Jamir/emulator/src/direct_features.py:43 (uses the full [0..6]), ADR 0030 (the measurement that exposed this), ADR 0025/0023/0024 (the artifacts affected)"
informed: "line M (INTEGRATION POINT — the pinned .drf/.rcop artifacts and cell_meta.parquet coverage change; M must re-pin a bumped version), lines/S/STATE.md, MEMORY.md, CLAUDE.md §3, python/src/lpjmlfit_emulator/data.py + config/config.yaml (the root constants), scripts/build_slow_{runtime_table,count_table,flux_table,oracle_reference}.py, the emulator-validation-figures + slow-drf-pipeline skills, every published global Component-S fidelity number"
---

# Component S must be trained on LPJmL-FIT's COMPLETE tree PFT set (ids 0–6): the `TREE_TYPES = [1,2,3,4,5]` basis silently drops a third of the forest

> **Status.** `accepted` as a decision + a measured defect report. The *execution* (rebuild tables → retrain →
> re-validate → re-measure ADR 0030's gate) is the next line-S work item and an **integration point with line
> M**; nothing is rebuilt by this ADR. Committed baselines and the runtime are untouched, so the repo stays
> green in the meantime — the defect is in the *training population*, not in the code that consumes it.

## The defect

`Type` in the annual `ind` output is the **0-based index into the active `pftpar` array**
(`src/lpj/fscanpftpar.c:177`; written as `pft->par->id` by `src/lpj/fwriteoutput_ind.c:82` for trees and `:140`
for grass). In the active `par/pft_lpjmlfit.js` that array is:

| id | PFT | class |
|---|---|---|
| **0** | tropical broadleaved evergreen tree | **tree** |
| 1 | temperate needleleaved evergreen tree | tree |
| 2 | temperate broadleaved evergreen tree | tree |
| 3 | temperate broadleaved summergreen tree (the Hainich beech) | tree |
| 4 | boreal needleleaved evergreen tree | tree |
| 5 | boreal broadleaved summergreen tree | tree |
| **6** | boreal needleleaved summergreen tree (larch) | **tree** |
| 7 / 8 / 9 | Tropical C4 / Temperate C3 / Polar C3 grass | grass |
| 10–21 | cereals, rice, maize, pulses, roots, oil crops, sugarcane | crop (never emitted: `landuse:"no"`) |

Every Component-S **DRF/copula** data builder selects `TREE_TYPES = [1, 2, 3, 4, 5]`
(`scripts/build_slow_runtime_table.py:74`, `build_slow_count_table.py:55`, `build_slow_flux_table.py`,
`build_slow_oracle_reference.py:27`, rooted in `python/src/lpjmlfit_emulator/data.py:68` and
`python/config/config.yaml:32`). That omits **id 0 and id 6 — both trees**. The python LightGBM
`DirectEmulator` path is NOT affected — `train.py:29` and `baseline.py:47` import the correct `[0..6]` from
`features.py` — so the blast radius is exactly the production DRF + copula pipeline.

**Measured global cost** (`scripts/diagnose_ind_type_composition.py`, seed1 historic `ind`, 246 M rows, job
1616777):

- **64 179 572 of 197 721 867 survivor tree stems dropped = 32.5 %** (id 0: 51.2 M = 25.9 %, in 21 957 cells;
  id 6: 12.9 M = 6.6 %, in 14 530 cells).
- **9 011 of 54 020 tree-bearing cells (16.7 %) contain no id-1..5 stem at all ⇒ they are INVISIBLE to
  Component S.** They sit in the tropical-forest belt and the extreme-continental Siberian larch zone: id 0's
  stems have a stem-weighted mean latitude of **+2.4** (p5/p95 −20/+23) and id 6's **+64.0** (p5/p95 +54/+72);
  id 0 is the only tree PFT whose establishment gate is unconditionally open in the wet tropics
  (`temp.low=2.5`, `gdd5min=0`, `twmax=1000`), while ids 4/5/6 are locked out there by `temp.high=0`
  (`establish.c:30-31`). *(Why ids 1–3, which are not gate-excluded, leave no surviving stems in those
  particular cells is NOT diagnosed here — the 9 011 count is measured, that mechanism is not.)* This is
  exactly the "45 009 cells" the global validation reports against the parquet's 54 020.
- **22 552 cells (41.8 %) lose more than half their tree stems**; 14 507 cells pass a ≥20-stem filter on all
  trees but fail it on the truncated subset.
- Because FIT draws traits **uniformly from PER-PFT `[low, high]` intervals** (`src/tree/new_tree.c:195-206`
  via `getrndinterval`; the par file's `median` field is unused there), the truncation also biases the cells it
  does retain: on the 38 009 cells both populations retain, per-cell medians
  correlate only **0.973 (SLA) / 0.494 (Wooddens) / 0.762 (D95max) / 0.093 (minwscal)** between the two
  populations, and the complete set carries **1.3–2.7× more between-cell spread** on Wooddens/D95max/minwscal.
  Id 0's minwscal interval is `[0.05, 0.75]` (measured per-stem median 0.497), reaching far outside the
  `[0.025, 0.30]` span the truncated tables cover at all.

So the production `drf_forest_global_*` / `recruit_copula_global_*` artifacts emulate **a temperate-and-boreal
subset of LPJmL-FIT's forest**, and every global Component-S fidelity number is scored on that subset.

## Why it is a defect and not intended scope

- The **same repo already carries the correct constant**: `python/src/lpjmlfit_emulator/features.py:50` has
  `TREE_TYPES = [0, 1, 2, 3, 4, 5, 6]`, and `python/src/lpjmlfit_emulator/train.py` /
  `scripts/train_slow_emulator.py` use *that* one with `GRASS_TYPES = [7, 8, 9]`. `MEMORY.md` states "PFT
  types 0–6 = trees, 7–9 = grass".
- **Provenance is a stale config, not a decision**: the port source
  `/p/projects/open/Jamir/emulator/src/direct_features.py:43` (which built the sibling's production tables)
  uses `[0..6]`; only that project's `configs/config.yaml:45` still said `[1,2,3,4,5]`, and it is that yaml
  value which was copied into `python/config/config.yaml` and `data.py`. The clash was noticed and
  rationalized as "distinct by design" (`python/src/lpjmlfit_emulator/__init__.py:44-45`, `JOURNAL.md:131`)
  instead of resolved — which is how it survived.
- **No ADR ever scoped Component S to temperate/boreal trees.** ADR 0025 says the copula is trained on "FIT's
  survivor marginal"; ADR 0020/0023 say S emulates FIT's tree demography. A 32.5 %-of-stems restriction would
  have needed its own decision, and there is none.
- It survived because the prototype cell **Hainich only contains ids 1–5 + grass 8**
  (`test/testitems/references/hainich_individuals_2010_meta.json`), so every single-cell gate — the Gate-3
  oracle, the coupled decade, the golden fixtures — is *unaffected* and stayed green.

## Decision

1. **Component S's tree population is `Type ∈ {0,1,2,3,4,5,6}`** — FIT's complete tree set. `isdead == 0`
   (survivor) and the grass/crop exclusion are unchanged. Grass ids 7/8/9 stay out of S until the separate
   grass-ownership decision (milestone S4); note grass rows are emitted with the tree fields **zeroed**
   (`fwriteoutput_ind.c:139-189` — verified: median Wooddens/D95max/minwscal = 0 for ids 7/8/9), so including
   them would inject structural zeros, not information.
2. **One shared constant, imported — never re-declared.** `python/src/lpjmlfit_emulator/data.py:68` and
   `python/config/config.yaml:32` are corrected to `[0..6]`, `features.py:50` keeps its value, and the
   `scripts/build_slow_*.py` hard-coded copies are replaced by an import so the two cannot drift again. Until
   that lands, each declaration site carries a pointer to this ADR (added now).
3. **Re-derive and re-validate, in this order** (nothing may be published from a mixed-basis state):
   count + copula tables (historic, ssp370, pooled) → retrain DRF + copula → K-fold-by-cell OOS + the
   hold-out-by-scenario evals → the ADR 0030 gate re-run (its floor moves to the `tree7` numbers: Wooddens
   0.694 → 0.923) → the figure set. The Hainich demo artifacts and their golden fixtures are expected
   byte-identical (Hainich has no id-0/6 stems); **if they move, stop** — that would mean something other than
   the population changed.
4. **Version, never overwrite** (the S→M contract, ADR 0029): the widened artifacts are new versioned files
   (`…_t7.drf` / `…_t7.rcop` or an explicit version bump in the meta), and line M re-pins deliberately. The
   `cell_meta.parquet` gains ~9 000 previously invisible cells, which changes coverage for M's multi-cell
   driver — hence this is an **integration point**, to be noted in both lines' STATE.md and landed together.
5. **Every global Component-S fidelity number published before this fix is labelled with its population**
   ("temperate+boreal trees, ids 1–5, 45 009 cells") rather than silently restated. They are not wrong as
   measurements; they answer a narrower question than they appear to.
6. **The feature contract is unchanged.** `flux_feature_vector` / `live_flux_cond` column order, the
   `.drf`/`.rcop` format, and the runtime code are all PFT-agnostic — only the training *population* changes.
   So this is not an ADR-0023 train/inference-consistency break, and no runtime change is required.

## Consequences

- **Expect the fidelity numbers to move in both directions.** The complete population has 1.3–2.7× more
  between-cell trait spread — more signal for the conditioning to explain (the `tree7` floor is higher on every
  axis), but the tropical PFT's very different trait intervals make the pooled single-marginal copula a worse
  structural fit. This sharpens the S2-vs-S3 question rather than settling it: a per-PFT/mixture marginal (S3)
  is now the *leading* hypothesis for Wooddens, since a per-cell trait median is a composition statistic and
  `COPULA_COND_COLS` contains no composition term.
- Compute is modest and known: a copula table is ~70 s, a count table minutes, a global retrain ≈ 1–4 h on 32
  cpus (the `run_global_slow_*.sh` orchestrators already do build→eval→train in one job). The 186 GB daily
  F/E data and the C runs are **not** re-run — this is a re-derivation from the existing `ind` parquets.
- **A related latent defect is recorded here, not fixed:** `growth_eff = applied_npp / max(lai, EPS)` divides
  by `EPS = 1e-6` where the joined `LAI_STAND` is exactly 0 (202 106 of 1 348 400 historic cell-years have
  `lai == 0`), which produced a `growth_eff` maximum of **1.19e9** in the seed2 copula table against 3.1e4 in
  seed1. The soilmoist/lai tables are *complete* (all 67 420 cells × 20 yr), so the `drop_frac`/`cells_lost`
  coverage guards cannot fire on a zero — a zero is present, not missing. The re-derivation must add an
  explicit `lai > 0` guard (drop or floor the row) and assert a sane `growth_eff` maximum; conditioning on a
  1e9 outlier is a live train/inference hazard.
- Until the re-derivation lands, **S2 is blocked** (ADR 0030 §5): tuning conditioning against a truncated
  population would optimise the wrong target.

## Alternatives considered

- **Document the restriction as intended scope** ("Component S emulates temperate+boreal trees"). Rejected:
  it silently excludes the tropical forest belt — the largest live-biomass pool on Earth and the region an
  ESM land component most needs — and it contradicts the project's stated goal of emulating LPJmL-FIT
  faithfully. It would also require retracting "global" from every existing result.
- **Add ids 0/6 but keep one pooled marginal per axis.** Not rejected, but not assumed sufficient: it is the
  cheapest next step and the honest first measurement, and the composition mechanism predicts a per-PFT
  mixture (S3) will be needed. Sequence: widen first, measure, then decide S3 on evidence.
- **Train a separate tropical emulator.** Rejected for now: it re-fragments what ADR 0026 deliberately pooled
  (one environment-conditioned model across regimes) and would need its own regime-holdout validation. Revisit
  only if the widened pooled model fails on tropical cells specifically.
