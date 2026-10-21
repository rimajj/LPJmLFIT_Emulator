# 0352 — Yearly forest map: the forest's own last-year state as an input (recursive map), with a drift test (pre-registration)

* **Status:** pre-registered 2026-10-21, before any fit of this record. Results §6.
* **Owner decision (2026-10-21):** asked whether to feed the forest map its own previous state so it knows what a
  drought hit — knowing that this makes the map year-to-year dependent and that its no-drift property came from not
  doing so — with a drift test pre-registered alongside: *"yes try it"*.
* **Follows:** ADR 0350 (the map misses the original's drought die-offs: 3 % of the drop captured, 10-year aftermath
  gap 4.4× a second run's), ADR 0351 (climate-only inputs lift the capture to ~0.14 and leave the gap at 3.8–4.4×;
  §5.2: the second runs follow a die-off because they carry their own forest through it).
* **Code:** `scripts/explore_panel_yearly_drift.py fit --state {none,lag,lagd}`, `retention` stage (new).

## 0. A defect found while preparing this arm: run m5 on the held-out climate model was in the training rows

`stage_fit` builds `rows` = (training runs × training legs × training years) ∪ (runs m4, m5 × the held-out model's 3
legs × every year), then takes `tr = rows.filter(member ∈ TRAIN_M)`. m5 is both a training run (`TRAIN_M` =
1, 2, 3, 5, 6) and the test-side harness run, so `tr` also held **m5 × the 3 held-out legs × all 81 years** —
255 150 rows, 7.9 % of the 3 231 900 training rows (the logs show 3 231 900 where the design is
5 × 27 × 21 × 1 050 = 2 976 750). m5 shares the held-out model's weather with the unseen run m4 and is one of its
"second runs", so the map trained on a sibling of its truth under the very climate it was scored on. The same line
is in `explore_panel_stand_map.build_rows` (used by the validated fold release, ADR 0340).
**Every held-out-climate-model number from the year-by-year structure and stand maps since ADR 0330 carries this**
(ADR 0330 drift, ADR 0340's structure verdict, ADR 0349–0351 arms, the stand-map arms). The deployment release
`release/v1` is NOT affected (all runs and legs train; there are no test legs).
Fix: `tr = rows.filter(member ∈ TRAIN_M AND leg ∈ train legs)` in both scripts. New prediction files carry the
suffix `_fx`, so no stored prediction is overwritten. Arm `fix` (§1) measures the defect's size on the structure map;
the stand map and the fold release are re-scored in a later step (not here).

## 1. Arms

All arms are leak-free (`_fx`). One change per step, read as a chain:

| arm | = | measures |
|---|---|---|
| `fix` | the deployed map (ADR 0330 form), leak fixed | the defect's size: against the stored `_rerun` (ADR 0349) |
| `fx10` | ADR 0351's `x10` (recent-year + 10-year-extreme climate inputs), leak fixed | base for the state arms |
| `lag` | `fx10` + **last year's state**: tree count per patch and biomass per tree of the same run in y−1, raw and as deviation from this year's anchor (n − anc; ln((a+1)/(anc+1))) — 4 columns, fed to all six quantity models. Trained on the original's own y−1 state (teacher forcing). | does the state carry the aftermath? |
| `lagd` | `lag`, but trained on the lags the map itself produces: 3 folds by training climate model (3 models each); a teacher-forced tree-count / biomass-per-tree model fitted on the other two folds free-runs each fold's legs 2020–2100 from the run's own 2019 state; those free-run values replace the true lags in the training rows; then the six models are refitted. | the standard remedy for errors piling up when a map trained on true lags is fed its own |

**Run time (all state arms):** the map runs forward year by year — 2020's lag is the run's own 2019 state (as the
deployed map already knows the run's 2000–2019 levels), every later year's lag is the map's own prediction for the
year before. Only tree count and biomass per tree are fed back; the traits do not feed back.

## 2. Measures

* **Die-off (ADR 0350's diagnostic, shared tree-count events, `SUFFIX=<arm>`):** drop capture and aftermath gap
  (|L_X − L_T| / second runs').
* **Must not get worse (`compare_structure_variants.py`, relaxed standard, dense by the anchor):** median ratio arm /
  `fix` ≤ 1.02 on every quantity and group; no criterion passing in `fix` lost.
* **Drift (ADR 0330 measure, `score` stage):** median over the 15 cases of late (2081–2100) / early (2021–2040)
  error ratio, dense cells, tree count and biomass per tree: ≤ `fix` + 0.05. And the late level itself: median
  `rho50_late` ≤ 1.05 × `fix`'s (a recursive map could keep the ratio flat by being bad early).
* **Start-error test (new, `retention` stage):** the map is run a second time from a start in which every cell's 2019
  tree count is cut by 30 % (a die-off of the median shared size, ADR 0350: 0.31). Retained fraction
  `r(y)` = median over dense cells of (X(y) − X_cut(y)) / X(y), divided by 0.30. A start error must never grow and
  must fade: **max over years of r ≤ 1.1, and mean r over 2081–2100 ≤ 0.5.** Reported beside it, for scale: the
  original's own memory of a die-off (ADR 0350: a 0.31 drop is still a −0.25 deficit over the next 10 years, i.e.
  ~0.8 retained over a decade). Not computed for `fix` / `fx10` (no state input: r ≡ 0 after 2020 by construction —
  the harness check: `retention` on `fix` must return r = 0 exactly).

## 3. Pre-registered verdict

* **Adopt** `lagd` (preferred) or `lag` if: aftermath gap ≤ 2.0× a second run's, AND must-not-worsen, AND both drift
  conditions, AND the start-error test.
* The drop capture (≥ 0.30 in ADR 0351) is reported but is **not** an adoption condition here: last year's state
  cannot announce this year's drought — that is the climate inputs' job, and ADR 0351 measured them at ~0.14. The
  state input's job is the aftermath. (Changed from ADR 0351's primary, stated before the run.)
* If the aftermath improves but drift or the start-error test fails: report "the state input carries the aftermath
  but errors pile up" and do not adopt; the trade-off goes back to the owner.
* If `fix` moves the relaxed-standard ratios by more than 2 % against `_rerun`, the earlier held-out-model numbers
  (ADR 0330, 0340 structure) are restated from the leak-free fits in a follow-up.

## 4. Expectations (written before running)

* `fix` vs `_rerun`: errors on held-out legs up by 0–5 % (dense tree count ×1.00–1.05); drift ±0.03; capture ≈ 0.03.
* `fx10`: capture 0.06–0.14 (part of ADR 0351's 0.14 may have come from m5's held-out drought years); gap 3.8–4.5×.
* `lag`: capture 0.10–0.25, aftermath gap 1.5–3×; risk of piling up: tree-count drift 1.2–1.6, start-error retained
  late 0.5–0.9.
* `lagd`: gap 2–3.5×, drift within ±0.05 of `fix`, retained late 0.2–0.5.
* My best guess: `lag` improves the aftermath and fails a drift condition; `lagd` passes drift and does not reach
  2.0×. I do not have a confident expectation.

## 5. If adopted

The package (`landemu`) would carry the forest's tree count and biomass per tree from year to year (it already
carries a 30-year climate window); the map's year step becomes y−1 → y; the release gates (numpy == pipeline)
gain the year-by-year replay. The stand map (leaf area, cover) is a separate follow-up.

## 6. Results

(pending)
