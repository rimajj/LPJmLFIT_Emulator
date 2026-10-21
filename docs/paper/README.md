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
* Gotchas: the `ind` biomass per tree is density-weighted gC m⁻² (nind = 1/patcharea, patcharea 225 m²), so
  kgC per tree = value × 0.225; the second-run yardstick of the structure scores is runs m1–m3 under the held-out
  climate model (m5 is the harness check), not m5.
