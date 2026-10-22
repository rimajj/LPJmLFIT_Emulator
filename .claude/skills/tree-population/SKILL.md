---
name: tree-population
description: The whole-tree-POPULATION and per-tree MORTALITY pipelines of the learned emulator (ADR 0363, 0364, 0365) — within-cell distributions (9 quantile levels) of height, biomass per tree, SLA, wood density, D95max, minwscal, the ACTUAL rooting depth D95 and age; tree-type shares; virtual trees (Schaake shuffle from the run's 2019 trees, no-repeat donor draw); functional-diversity indices (richness, evenness, divergence, dispersion, Rao's Q, CWM/CWV); and death rates (cell-level maps and the per-tree leaf-carbon / counter / hazard model). Use whenever refitting or re-scoring any of these, adding a population variable or index, building the per-tree year-to-year tables, asking "how good are the trait distributions / biodiversity indices / mortality", or touching xpanel/yearly2, yearly3, tree_pairs, eval/popmap, eval/treemort. Carries the traps: the ind `mort` column already holds the hard kills; tree identity needs Type + SLA; repeated donor trees bias evenness; Age LightGBM fits are not reproducible.
---

# Tree population + per-tree mortality

Data (`/p/projects/open/Jamir/esm_land_emulator_data/xpanel/`):
* `yearly2/` per (Cell, Year) quantiles/means/deaths — `scripts/build_panel_yearly_v2.py yearly|rosters|npp`
  (rosters every 5 yr: `/p/projects/reformit/.../xpanel_rosters/`).
* `yearly3/` + `tree_pairs/` — `scripts/build_panel_tree_pairs.py build --part I --nparts N` (186 run-legs, ~10 s each):
  at-risk = alive ≥ 5 m at end of y−1; `n_hard` counted directly; 0.5 % per-tree sample with y−1 state and y outcome.

Fits and scores (all on SLURM, `scripts/sbatch_python.sh`; `EXCLUDE=cso14c65` — that node fails jobs in 0 s):
```bash
python scripts/explore_panel_popmap.py fit --g <gcm> --group <Height|agb|SLA|Wooddens|D95max|minwscal|D95|Age|shares|mort|mortn|mort3|mort3n>
VDRAW=unique python scripts/explore_panel_popjoint.py truth|virtual --g <gcm>; VDRAW=unique ... score
python scripts/diagnose_popjoint_agb_evenness.py run --g <gcm>; ... score       # computed-vs-learned biomass, evenness
python scripts/explore_panel_treemort.py fit|pred --g <gcm> --arm BC|BCN; ... score   # VDRAW=unique for pred
```
`export` knobs (VDRAW, POPMAP_SFX) — the wrapper forwards only a fixed list. `POPMAP_SFX=_x` writes
`preds_<g>_<group>_x.parquet` so a refit never overwrites a scored file. Scores are ratios to the pooled second runs
m1–m3 against the truth m4 (dense = anchor ≥ 5 trees per patch); the harness (run m5) must read 0.98–1.02.

Traps:
* The `ind` `mort` = probability AFTER hard kills (= 1 for them): `Σ mort` includes hard kills; deaths beyond it are
  fire / isneg / luck. yearly2's "chance"/"excess" split is mislabelled; use yearly3.
* Identity `(Cell, Patch, Type, ID)` + `SLA`; assert unique before a year-to-year join.
* For trees ≥ 5 m most hard kills outside die-offs are the bad-years counter; in die-offs the leaf threshold (92 %).
* Virtual trees: a repeated donor gives near-identical trees and biases evenness (−0.04) — use `draw_unique`.
* The second-run bar has little power for distributions (the anchor alone scores 0.83–1.01).
* Results: ADR 0363 §9–12 (distributions/indices pass; learned > computed for biomass and rooting depth), ADR 0364 §6
  (per-tree mortality not adopted: capture 0.36, 30-yr rate 1.51; with the run's own NPP 0.74).
