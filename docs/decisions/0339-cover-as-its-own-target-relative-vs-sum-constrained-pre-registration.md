# 0339 — Cover as its own target: relative error vs sum-constrained to a total (pre-registration)

* **Status:** pre-registered 2026-10-14, before the runs. **Result recorded 2026-10-15 (§4): both methods null — the additive cover fit stays.**
* **Depends on:** ADR 0338 (cover of the 10 plant types carries the largest median share of the stand map's added
  error on every flux — GPP 0.70, NPP 0.89, ET 0.87, runoff 0.57 — not only ET; the decision there was to improve
  cover next). ADR 0331 (the stand map; cover's own error on dense cells: tree 1.55×, grass 1.27× a second run).
* **Owner instruction (2026-10-14):** try both proposed fixes rather than picking one up front.
* **Scripts:** `scripts/explore_panel_stand_map.py` (new `--cover-mode {additive,relative,sumconstrained}` on `fit`,
  `arrays` and `score`), `scripts/f2_train.py --stand-dir`, `scripts/f2_relative_score.py`,
  `scripts/f2_relscore_compare.py`.

## 1. Why

The stand map fits each of the 10 per-type covers independently with LightGBM, target = value − anchor (an absolute
difference). Two concrete changes were proposed at the end of ADR 0338 and neither is obviously better without
measuring:

* **Relative:** fit the per-type target as a log-ratio to its anchor (`log(value) − log(anchor)`, floored at 1e-3
  before the log) instead of an absolute difference, so a small cover's error is weighted the same as a large one's in
  the loss — the current additive loss is dominated by the largest covers.
* **Sum-constrained:** fit a separate total (tree cover = sum of types 1–7, grass cover = sum of types 8–10) and
  rescale the 10 additively fit per-type predictions so they sum to it. The total is itself a learned quantity (there
  is no oracle total at inference time for a future run), chosen because a sum is a smoother target than any one
  type and may be easier to fit; the per-type predictions keep whatever shape the additive fit gave them.

Implemented as two arms, isolating the cover-fitting method as the one variable (lai_stand and vegc are fit
identically — additive — in every arm, matching ADR 0338's attribution which reads cover from the map and leaf
area/vegetation carbon from the original). `--cover-mode additive` (the default) reproduces the pre-existing
`preds_<g>.parquet` files byte for byte — checked on the smoke test (`pc-smoke-rel`/`pc-smoke-sum`, g=gfdl-esm4,
hold=1): both new modes ran cleanly and give visibly different cover levels (tree-cover mean on that fold: additive
0.556, relative 0.468, sumconstrained 0.562 — the rescale is small because the per-type sum was already close to a
sensible total on this fold).

## 2. Design

Two arms, each changing only the cover-fitting method; everything else as ADR 0337/0338 (arm D, the 13 held-out
climate-model legs, free runs, held-out cells, the stand of run k from the map fitted with run k and the leg's
climate model unseen):

| arm | cover fit | leaf area, vegetation carbon |
|---|---|---|
| `PC_R` | `--cover-mode relative` | from the original (as `PD_C`) |
| `PC_S` | `--cover-mode sumconstrained` | from the original (as `PD_C`) |

References: `PD_A` (everything from the original), `PD_C` (cover additive, the current stand map — ADR 0338).

**Two readings, cheapest first:**

1. **Stand-map level (CPU only, ~15 min):** `stage score --cover-mode <mode>` on dense cells, the same statistic
   ADR 0331 used for `PD_C`'s cover (typical-cell error vs a second run, `tree`/`grass` cover only). This is a fast
   filter before spending GPU time: if a mode does not improve cover's own accuracy here, it is unlikely to improve
   phase B.
2. **Phase-B flux level (GPU, the decisive one, as ADR 0338):** `f2_train.py --ensemble D_3x256_seed0..4 --stand-dir
   stand_cover_<mode>` (score-only, same five networks as `PD_A`/`PD_C`, no retraining), scored with
   `f2_relative_score.py` against `PD_A` and `PD_C`.

## 3. Pass / decision rule (written before the runs)

* **Stand-map level:** a mode is worth carrying to phase B if its dense-cell typical-cell cover error (tree or
  grass) is below `PD_C`'s (the current additive fit) on at least half of the 13 legs. Neither passing this is not a
  reason to skip phase B — the stand-level metric and the flux-level one could disagree (ADR 0338's own surprise,
  that cover beat leaf area on GPP/NPP, came from exactly this kind of indirect effect) — but it orders which arm to
  read first.
* **Phase-B level (the decisive test):** compare each arm's typical-cell flux error (GPP/NPP/ET/runoff, both
  windows) against `PD_C`'s (cover additive) and `PD_A`'s (no cover from the map at all, the floor this group of
  arms cannot beat). A mode **improves cover** if its typical error is below `PD_C`'s on at least 3 of 4 fluxes
  (median across legs); it **closes the cover gap** if it comes within 1.1× of `PD_A`'s on a flux. Report both arms
  side by side regardless of which (if either) passes — "try both" was the instruction, and a numeric comparison is
  the point even if neither clears the bar.
* **Falsifier:** either arm making a flux worse than `PD_C`'s by more than 1.1× (median) on half the legs ⇒ that
  cover-fitting method is actively harmful and should not be adopted, independent of the other arm's result.

## 4. Result (recorded 2026-10-15)

**Provenance.** All runs were made on 2026-10-14 by the session that wrote this record, but the result was never
written down: stand fits `pc-<model>-h<k>-{rel,sum}` (40 jobs), arrays `PC_rel-arrays.2487182` /
`PC_sum-arrays.2487183` into `f2/stand_cover_rel` / `f2/stand_cover_sum`, stand-level scores
`logs/PC_{rel,sum}-standscore.out`, phase B `f2-PC_R.2487185` / `f2-PC_S.2487186` (`f2/runs/PC_R`, `PC_S`). ⚠ On
2026-10-15 a later session, not knowing this, re-ran the 20 `relative` fits (jobs 2502421–40), which **overwrote
`xpanel/eval/stand/preds_<g>[_h<k>]_relative.parquet` with refits** (multithreaded LightGBM is not bit-reproducible,
so they are replicates, not the files phase B read; `stand_cover_rel/` still holds the arrays phase B read). The
`sumconstrained` prediction files are the originals. Scored 2026-10-15 with `f2_relative_score.py PD_A PD_C PC_R
PC_S` + `f2_relscore_compare.py` (13 climate-model legs, the observed-climate control leg excluded — it is
identical in every arm).

**Reading 1, stand map, dense cells, typical-cell cover error vs a second run (2071–2100, median of 15 cases):**

| cover fit | tree cover | grass cover | tree drift mid→late | grass drift |
|---|---|---|---|---|
| additive (`PD_C`, ADR 0331) | **1.55** | **1.27** | 1.07 | 1.05 |
| relative (`PC_R`) | 1.85 | 1.49 | 1.12 | 1.06 |
| sum-constrained (`PC_S`) | 1.58 | 1.29 | 1.12 | 1.06 |

Neither mode is below the additive fit on the stand-level filter (the log-ratio target is clearly worse: weighting
small covers equally costs the large covers that carry the fluxes).

**Reading 2, phase B (the decisive one), median over the 13 legs × 2 windows of the typical-cell flux error ratio:**

| | GPP | NPP | ET | runoff |
|---|---|---|---|---|
| `PC_R` / `PD_C` | 1.026 | 1.015 | 1.060 | 1.048 |
| `PC_S` / `PD_C` | 1.017 | 0.990 | 1.000 | 1.000 |
| `PD_A` / `PD_C` (the floor: cover from the original) | 0.925 | 0.902 | 0.774 | 0.898 |
| `PC_S` / `PD_A` | 1.109 | 1.139 | 1.295 | **1.093** |
| `PD_C` / `PD_A` | 1.081 | 1.109 | 1.292 | 1.114 |

Against the rule of §3:
* **Improves cover** (below `PD_C` on ≥ 3 of 4 fluxes): `PC_R` 0 of 4, `PC_S` 1 of 4 (NPP 0.990) → **neither**.
* **Closes the cover gap** (within 1.1× of `PD_A` on a flux): `PC_S` on runoff (1.093) — but `PD_C` itself is at
  1.114 there and at 1.081 on GPP, so this is the existing fit's margin moved by 0.02, far inside the run-to-run
  noise of ADR 0336 §6 (±9–20 % per leg). Not read as a closure.
* **Falsifier** (worse than `PD_C` by > 1.1× on half the legs): `PC_R` exceeds 1.1 in ET on 7 of 26 (leg, window)
  values and runoff on 6 of 26 — under half → **did not fire**; `PC_S` never.

**Decision.** Keep the additive cover fit. The cover error remains the main share of what the emulated stand adds
(ADR 0338), and neither changing the loss weighting nor constraining the type covers to a fitted total moves it.
Both levers were cheap re-weightings of the same features; what the cover model lacks is information, not loss
shape — the same limit as the structure map's (27–49 % of the per-cell response to an unseen climate explained,
ADR 0329). Not pursued further in this round.
