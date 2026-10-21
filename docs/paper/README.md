# The emulator paper (manuscript draft)

`main.tex` + `refs.bib` → `main.pdf`: a model-description paper of the learned LPJmL-FIT emulator (release v1,
package `python/src/lpjmlfit_emulator/landemu`), written for an external scientific audience (GMD-style). It is
about the emulator itself — design reasoning, how it works, how good and how fast it is; the Earth-system-model
coupling experiments are deliberately left out (owner, 2026-10-20).

* Figures: `figs/` (PDF for the paper, PNG previews). Data figures come from `scripts/paper/fig_*.py`
  (shared style `scripts/paper/style.py`), schematics from `schematics/*.tex` (TikZ).
* The only new computation: `scripts/paper/run_daily_example.py` (validated fold release, daily output at the
  biome cells → `esm_land_emulator_data/paper/daily_example.npz`; SLURM, ~15 min).
* Rebuild everything: `scripts/paper/make_all.sh` (needs `module load texlive/2026`; `pdflatex` is not on PATH).
* Every number is from the decision records (mainly ADR 0312, 0316–0318, 0320–0343) or the scored tables named
  in each figure script's docstring. Bibliography: the review corpus entries (`~/dgvm-review-corpus/manuscript/corpus.bib`,
  keys = record ids) plus standard model references.
* Status (2026-10-21): complete draft, 25 pages, ready for the owner's read. An independent fact-check of every
  number (`FACTCHECK.md`) was applied in full: the abstract, the requirements table and the conclusions now say that
  the daily networks were tested on new places only (climate models seen), that the warming-response test did not pass
  as pre-registered and that one training step of it was added after seeing results, that the dense-cell definition
  and the forest-structure drift baseline were chosen after first results (with the pre-registered outcomes beside
  them), and the 500-patch cost is the measured 7.06 core-s (not the extrapolated 6.7). Open before submission: the
  owner's own read, author list / affiliations, a Zenodo DOI for code and release, target-journal formatting.
* **Restated 2026-10-21 (ADR 0353): every held-out-model number now comes from leak-free fits** (ADR 0352 §0 found the
  structure and stand maps had trained on a sibling of the test run under the held-out climate model). Changed in the
  text: abstract, Sect. structure (21 → 18 of 22 criteria; dense tree density 1.16 → 1.26, biomass per tree 1.07 → 1.18),
  drift, daily fluxes (ET 5 → 4 of 13 legs, totals ≤ 2.9 %, stand adds 12 % / 37 %), limitations, requirements table,
  conclusions. Figure scripts read the `_fx` / `PD_B_fx` / `fold_gfdl-esm4_v2` inputs (`daily_example_v2.npz`).
  `FACTCHECK.md` checked the pre-restatement numbers and is kept as it was.
* **Owner's questions, 2026-10-21 → text to-dos (none done yet).** Answers were checked against the code and ADRs.
  1. *Daily inputs, the capacity sentence* ("read from the original each year in the evaluation runs"): say that
     "original" = LPJmL-FIT; in the tests the capacity came each year from the held-out run itself (a small leak,
     harmless: 0.1–0.2 % median change); the release uses a fixed per-cell 2019 value (`build_emulator_release.py`).
  2. *What a deployment needs*: state plainly that every emulated cell needs a historical LPJmL-FIT run (anchors,
     2000–2019 state, start stores and stand, capacity), and that the panel anchor uses the training runs' FUTURE
     output at that cell (other runs and climate models, not the predicted run); the global and nitrogen-on versions
     use only the historical state.
  3. *Forest maps, Sect. 4.3*: say where year-to-year development comes from — the panel anchor is the original's
     own year-by-year trajectory, and the 30-yr window moves slowly; consequence: a one-year extreme event leaves no
     legacy beyond 1/30 of the window. In the global version the anchor is constant, so only the climate carries time.
  4. *Limitations, "cells seen in training"*: rewrite. "Clearly worse" came from an earlier map WITHOUT an anchor
     (agreed with the unseen run on 5–9 % of cells vs a ~13 % target, below a lookup; ADR 0316 §3). With the anchor,
     unseen cells give 1.8–2.2× a second run for leaf area / cover; dropping lat/lon/soil code or blocking memorisation
     changed < 5 %; the error falls 6–12 % per doubling of training cells (ADR 0343). Say "seen" = "the original was
     run there", and that coordinates are not what the map relies on.
  5. *Soil*: state that the daily networks get no soil texture, only the top-metre capacity (how fast water moves is
     not represented — relevant to runoff), and that the soil code enters the maps as a number (or fix it first —
     STATE.md NEXT item 2). Candidate limitation/outlook line.
  6. *Ensemble, Sect. 4.1*: give the reason — a single network's NPP level shifts by several % with the random seed
     (ADR 0322); five is set by cost, not tuned; the member spread is not used as uncertainty.
  7. *Gradient-boosted trees*: one sentence that tree models cannot extrapolate (outputs stay within values seen in
     training), linking it to the damped response beyond the training scenarios (Sect. 6.5/6.6, Discussion).
* Gotchas: the `ind` biomass per tree is density-weighted gC m⁻² (nind = 1/patcharea, patcharea 225 m²), so
  kgC per tree = value × 0.225; the second-run yardstick of the structure scores is runs m1–m3 under the held-out
  climate model (m5 is the harness check), not m5.
