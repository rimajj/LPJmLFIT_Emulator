# Fact-check of the manuscript draft (2026-10-20) — all items applied 2026-10-21

Independent number-by-number check of `main.tex` against the decision records and scored tables, made by a
read-only review agent on 2026-10-20. Every item below was re-verified against its source and applied on 2026-10-21
(one correction to the report itself: item 25's yearly differences come from threshold-counted climate statistics,
ADR 0340 §3, not from tree-model splits). Kept as the provenance of the corrections.

**Fact-check of docs/paper/main.tex (LandEmu v1). No files were edited.**

Ordered from most to least serious. Sources are under /p/projects/open/Jamir/esm_land_emulator/ unless a full path is given. Where a check needed computing, I recomputed from the data tables with scripts/final_daily_score.py, the PD_A/PD_B sections of relative_score_PD_ADR0337.md, final_structure_anchor.csv, drift_score.txt and paper/daily_example.npz.

### A. Serious

**1. ERROR – what the daily evaluation held out is misdescribed** (abstract, contribution 3, Table 2 out-of-distribution row, Conclusions).
- Quotes:
  - "Trained on six independent runs of LPJmL-FIT under ten climate models and tested on a climate model and a run never seen…"
  - "every test holds out a climate model and an independent run"
  - Conclusions: "Under a held-out climate model and run, … daily GPP and evapotranspiration to a few per cent per cell"
- What the sources say:
  - The daily networks were trained on runs 1–4 only (`f2_train.py` MEMBERS=[1,2,3,4]). They saw 14 legs: the control plus five climate models, not ten.
  - The deployed daily model saw every climate model it is scored on. ADR 0335 §1: "the only out-of-sample check left is by cell (place) … A number from this arm must never be quoted as skill on an unseen climate model."
  - The structure folds trained on 5 runs and 9 climate models. Six runs and ten models is the deployment release (ADR 0340 §2).
- Section 5.4 states this correctly ("only the cells are new"). The abstract, Table 2 and Conclusions contradict it.
- Fix:
  - Abstract: "forest maps tested on a held-out climate model and run (trained on five runs, nine climate models); daily networks tested on held-out cells under climate models they were trained on."
  - Correct Table 2 and the Conclusions the same way.

**2. ERROR – "Training on more climate models reduced this growth to 1.17."**
- The 1.17 is the drift of net production for the deployment daily model with UKESM1-0-LL *added to training* (ADR 0335 §3: 1.25→1.17). It is no longer an unseen-model test.
- ADR 0336 §6: "No coverage effect is measurable on UKESM" (within run-to-run noise).
- STATE.md: more climate models "fails, falsifier fired … the gap still grows on UKESM / IPSL".
- In the final emulator, UKESM GPP drift is 1.26 (PD_B).
- Fix: "Adding further climate models did not measurably reduce this growth for UKESM1-0-LL; it is reduced only when the model itself is in training (1.17 for NPP), and the full emulator's GPP gap still grows 1.26× on that leg."

**3. OVERSTATEMENT – the warming-response test omits its pre-registered verdict and that a key arm was added after seeing results** (abstract, Sect. 5.5, Conclusions).
- ADR 0342 §7.1 and §7.2: "Verdict as pre-registered: NOT PASSED" for rising CO2 and for fixed CO2.
- The quoted 79–98 % and the "72 % of this largest loss" come from the arm with CO2-fixed copies of every scenario in training. ADR 0342 §6b: "this step was chosen after seeing held-out results". Before that step the largest warming-only loss was reproduced at 57 %.
- The abstract does not say this is the nitrogen-on model with rising CO2, where CO2 fertilisation dominates the +32–45 % change. Warming-only losses stay damped by about 30 %.
- Fix: state the nitrogen-on/rising-CO2 setting in the abstract, report the not-passed verdict, disclose the post-hoc arm, and give the warming-only result (0.72; 0.57 before the post-hoc arm).

**4. OVERSTATEMENT – how "dense" is defined, and the 21 of 22 count** (Sect. 3.3, 5.2).
- Quotes: "defined by the anchor before the run"; "moves three criteria across their limits".
- The accepted pass standard defines dense cells by the truth run (ADR 0318 §2). ADR 0329 §4 says D3 "keeps its definition (truth ≥ 5) … report the anchor-defined total beside it". The anchor-based definition was adopted as primary afterwards (ADR 0340).
- Under the truth-based definition 19 of 22 criteria pass, so two criteria move, not three. Failing under truth: tree density dense-typical, sparse-typical and sparse stem totals; under anchor: tree density dense-typical only.
- Fix: "the standard as written defines dense cells by the held-out run (19 of 22 pass); defined by the anchor, 21 of 22; two criteria change."

**5. OVERSTATEMENT – the drift claims** (abstract "Nothing drifts away…", Sect. 3.3, Table 2).
- The structure drift baseline (2051–2070) was proposed after the pre-registered rule failed and was "Proposed to the owner (not adopted)" (ADR 0330 §1). Sect. 3.3 presents it as the standard.
- The daily no-drift result holds only on climate models the networks were trained on. With a model held out, the GPP/NPP gap grew 1.29/1.35× (ADR 0327; STATE.md).
- There is a tree-density creep of +0.12 under SSP5-8.5 that increases with warming.
- Fix: put these caveats in the abstract and in Sect. 3.3.

### B. Moderate

**6. ERROR – area totals of the daily fluxes.**
- Quotes: abstract "with area totals within 2 %"; Sect. 5.4 "within 1 % for GPP, NPP and evapotranspiration and within 2 % for runoff".
- These are medians over legs. The worst legs are GPP 2.1 %, NPP 2.1 %, ET 0.9 %, runoff 2.5 %. ADR 0337 §4: "≤ 2.5 % on every leg and flux".
- Fix: "median 1–2 %, all legs within 2.5 %."

**7. ERROR (inconsistent statistic) – the cost of the emulated stand.**
- Quote: "reach 2.2 … 2.6 … the emulated stand adds a median 13 % to the GPP error and 35 % to the evapotranspiration error".
- 2.2/2.6/3.4/4.5 are medians of the larger of the two 30-year windows; these match my recomputation (2.15/2.55/3.41/4.51).
- 13 %/35 % are medians of per-leg, per-window ratios (ADR 0337).
- On the same statistic as 2.4/3.1 the increase is 9 % (GPP) and 27 % (ET), so a reader computing 2.4/2.2 ≈ 1.10 finds a contradiction. Fix: say which statistic is used, or quote 9 %/27 %.

**8. ERROR – "the mean of other runs, an upper bound on what a deterministic emulator can reach".**
- A perfect expectation predictor scores about 0.71. The mean of three to five runs scores about 0.79–0.82 (ADR 0317 §5).
- Fix: call it "a reference for a near-ideal expectation predictor".

**9. OVERSTATEMENT – literature: "Tree ensembles trained to predict one step ahead drift when run freely over long periods, while networks trained on their own multi-step rollouts do not".**
- The ecLand study evaluated lead times "up to about one year"; aiLand ran four years (review results.tex).
- Fix: "at long lead times (up to about one year)".

**10. OVERSTATEMENT – structure area totals.**
- Quote: "within −0.1 % for stems and −1.5 % for biomass".
- These are signed medians over cases. Individual cases reach −2.0 % and −5.0 % (one case past the 5 % limit). Sparse cases range from −13 % to +12 % for stems and down to −18.5 % for biomass.
- Fix: say "median" and give the ranges.

**11. OVERSTATEMENT – ILAMB "within 0.03 of the original's on all 27 data-set comparisons".**
- Biomass, leaf area and cover are anchored over the historical period (in sample). ADR 0341 §6: these "test the original, not the emulator".
- Fix: add that caveat to the ILAMB sentence.

**12. OVERSTATEMENT – "On an earlier set of eight independent runs … the forest maps pass…"**
- That score is from the earlier 30-year-window map, not the v1 year-by-year map (ADR 0340 §4.1). It used runs from mixed model builds.
- Fix: say "an earlier window form of the forest maps".

**13. OVERSTATEMENT – the cost comparison.**
- Quote: "0.267 … about 6.7 at 500 patches on the same hardware".
- 6.7 is a linear extrapolation; the measured value at 500 patches is 7.06 (ADR 0086). The original was timed at one cell; across five biomes it costs 0.20–0.33 (ADR 0312), giving 24–44×.
- I found no source that the original and the emulator were timed on the same hardware.
- Fix: "extrapolated; one cell; 24–44× across biomes".

**14. OVERSTATEMENT – "its per-tree daily step cost 51 times the original's".**
- The later re-measurement is 58×. The hybrid also carried about 14× fewer individuals than the original (ADR 0084 §2a).
- Fix: "51–58×" plus that caveat.

### C. Minor

15. **ERROR** – "seven most expensive processes … 30-fold": the cumulative list has eight processes (phenology and the solver are combined in one row), and it is for the temperate cell only (ADR 0312 §3a).
16. **ERROR** – abstract "systematic review of 115 land-model emulators": the 115 are emulator *and hybrid* studies; 19 are hybrids (review numbers.tex).
17. **ERROR** – "every fourth year of five runs under the nine training climate models (about four million cell-years in the deployment release)": five runs × nine models ≈ 3.0 M rows (the validation fold). The 3.97 M is the deployment release, six runs × ten models.
18. **ERROR** – CO2 "held at its 2019 level": the global (full-grid) runs hold it at the 2014 level (ADR 0341 §1).
19. **ERROR (conservative direction)** – "agree … within 10 % in only 17–21 % of cells": the tolerance was max(10 %, the median two-run spread of the density stratum) (ADR 0316 §8). A plain 10 % gives fewer cells still.
20. **UNSUPPORTED** – the daily-flux limits are justified as what "an atmosphere needs less precisely". The source reason is the owner's "not as close as a second run" and reusing the 3× limit from the sparse-cell standard; the numbers were chosen after the scores (ADR 0325).
21. **Missing caveat** – "No input is taken from the fluxes of the run being emulated": in the scored runs the daily model reads the original run's own yearly top-metre water capacity (ADR 0337 §5; median change 0.1–0.2 %, up to 4–6 %).
22. **Minor** – the deep-store equation drains (D_{t-1}+Q_t)/τ in the code (daily.py), not D_{t-1}/τ. Total runoff goes slightly negative on a few days (−2.5 to −10 mm, ADR 0326).
23. **OVERSTATEMENT** – "a few per cent per cell" (abstract) for 2.4–5.2×: runoff at 5.2× is about 8–10 %, NPP 5–6 %.
24. **OVERSTATEMENT** – "Year-to-year variations of annual GPP follow the original's closely": at the boreal cell the correlation is 0.66 (temperate 0.93, semi-arid 0.94).
25. **OVERSTATEMENT** – the validation release reproduces "to rounding": true for fluxes; for structure/stand the 99th percentile difference is 0.1–7 % (a float32 threshold artefact; ADR 0340 §3).
26. **OVERSTATEMENT** – "A learning curve … reduced this error": the learning curve measured error on unseen cells, not the all-cell per-cell slope. ADR 0343 §8 extrapolates that about 12 000 training regions would be needed.
27. **Wording** – "bracket the range of climate sensitivity": MPI-ESM1-2-HR and IPSL-CM6A-LR lie *inside* the training range; CanESM5 and UKESM1-0-LL warm more (ADR 0342 §2).
28. **Wording** – "Five measurements ruled this design out": item (v) is a literature result, not a measurement (the caption says so).
29. **Possible OVERSTATEMENT** – hybrid mortality "ported exactly": on the hybrid's own inputs the ported hazard delivered only 0.78 of the mortality flux (review_comparison §1.8).

**Internal shorthand:** No decision-record numbers, arm codes (A7rH, arm D, PD_B) or phase names appear in the text. P1–P5 are defined in place, which is fine. "Leg" ("13 climate-model legs", "the two warmest legs") is project jargon and is never defined; replace it with "climate-model–scenario combination", or define it once. The abstract's "two warmest scenarios" really means two climate-model–scenario combinations (UKESM1-0-LL SSP3-7.0, IPSL-CM6A-LR SSP5-8.5).

**Verified correct:**
- Run-time profile: 36–46 %, 15–27 %, 0.4–1.1 %, 97–98 %, 21–27 %, 0.20–0.33.
- Hybrid lessons: 4.6×, 1.23, 83 %, 0.982/0.962, +0.71→−0.23, 96/87 %, 76 %.
- Panel design: 1 050 cells, 105 blocks, 20 strata, 24 held-out blocks / 238 cells.
- Network and training settings.
- Structure numbers: 1.16 (11/15), 1.07, 0.60–0.83, 1.29, 1.01, 2.74, 1.34, −2.3 %, −5.7 %, 21/22.
- Drift values, and the daily scores 2.37/3.14/3.85/5.21 with their legs-passing counts.
- Response percentages.
- Global-run values: +0.04 %, −8.5 %, 151→162, 6.0–6.4 %, −2.8 vs −9.2 %.
- Costs: 7.6e-3, 1.8×/4×, 7.3e-3, 115–130×.
- Daily-example cell values: +0.8, −0.6, +12, 3 %, 20 mm, about 50 mm.
- Review counts: 115, 89, 7, 12, 25, 204 gC, 0.96–0.98 → 0.59–0.70.

**Overall judgement.** Almost every number in the manuscript traces to the records, and the body text is mostly careful. The main problem is framing in the abstract, Table 2 and the Conclusions, which claim more than the evidence supports in four places. First, the daily evaluation is described as holding out a climate model and a run when only the place is held out. Second, the warming-response test is presented without its not-passed verdict or the post-hoc training arm, and the abstract hides that it is the nitrogen-on, rising-CO2 model. Third, the headline 21 of 22 uses a definition of dense cells that replaced the pre-registered one after the fact. Fourth, the drift claim rests on a baseline chosen after the pre-registered rule failed and on climate models the daily networks had seen. One claim is plainly wrong: that more climate models reduced the unseen-model drift to 1.17. Fixing items 1–8 would make the paper defensible; the rest are wording and precision.
