# 0370 — The cheaper-memory and the transformer daily models in the complete emulator, and a daily NPP aimed at the extreme years (pre-registration, SEPARATE EXPERIMENT)

* **Status:** pre-registered 2026-10-23, before any fit of this record. Results: §6, added after the runs. **No candidate passes the complete-emulator rule (all improve the typical error 11–19 % but exceed the per-leg drift limit) ⇒ no package change, no release copy, no end-to-end timing. No NPP version aimed at the extreme years helps the die-offs (best +0.025 capture, bar +0.03).**
* **SEPARATE EXPERIMENT — nothing of it enters the paper** (continues ADR 0368/0369). A release copy is built only if
  §2 passes, and it does not replace the current releases without the owner's word.
* **Owner instruction (2026-10-23):** *"continue with 1-4"*, on the options offered after ADR 0369: (1) make the
  running-average + place daily network (MEP) a release candidate, tested in the complete emulator first; (2) aim the
  daily NPP at the extreme years, judged by die-off capture; (3) the transformer + place (TP) as the daily model —
  9× the deployed network's cost, still far below the original's, not yet timed end to end; (4) stop afterwards.
* **Data, cells, models:** as ADR 0368/0369 (clustered nitrogen-on runs, held-out cells, held-out climate models
  IPSL + MPI). The nitrogen-on fold release `non_fold_v1` (ADR 0344) has exactly this split, the deployed daily
  ensemble NC_s0–4 (= arm B) and the structure maps `main2`; its measured end-to-end cost is 7.29e-3 core-s per
  cell-year (one core, forcing read excluded), the original's 0.95 (allocation basis), daily model ~97 % of the
  emulator's cost.

## 1. New networks

* **MEP s3, s4** and **TP s3, s4** (as ADR 0369) so every candidate is a 5-member ensemble like the release.
* **MEPx s0–4** (option 2): MEP whose training loss weights the days of extreme NPP years 5× — the cell-years whose
  true annual NPP departure (minus the mean of the 5 previous years, over the cell's mean |NPP|, as the tree-death
  inputs) is in that cell's top 10 % by absolute value (per training leg, member 2). Everything else as MEP.

## 2. Options 1 and 3 — the complete-emulator test

**Venue:** the daily ENSEMBLE (mean of 5 networks' daily outputs, one closed bucket, as the release) run 2020–2100 on
member 2 with the EMULATED stand (`f2_non/stand_emul_main2`: the release's structure maps; held-out cells
out of sample for both) — `xtf_daily.py runens`; 30 rising-CO2 legs decide, CO2-fixed legs reported. Scored on
held-out cells (mean GPP ≥ 50) against member 2; member 3 is the second run. REF = B (NC_s0–4, the release's
networks); CAND = MEP, TP, MEPx (each s0–4). Per leg × window (2021–2050, 2071–2100) × flux: typical error = median
over cells of |E/T − 1| of the 30-year means; q = CAND / REF; drift = (late ÷ second run's late) / (early ÷ second
run's early) (`xtf_daily.py scoreens`).

**Accuracy rule** (ADR 0367's, on this venue): median q over legs × windows ≤ 0.95 for NPP and ≤ 1.05 for GPP, ET,
runoff; no flux's worst leg-window q > 1.25; no leg's drift more than 0.08 above REF's.

**Cost:** one-core cost of one network's daily step (ADR 0369 bench, set-up excluded): MEP must stay ≤ 1.35× B
(measured 1.18×); TP has no cost bar (owner's choice of option 3): its end-to-end cost is reported against the
original's and the release's.

**If a candidate passes:** (a) the package `landemu` gets its daily inputs (MEP: the running-mean bank as a daily
state + the place description; TP: a numpy transformer), opt-in per release file, existing releases unchanged
(gated: an unchanged release reproduces its old outputs bit for bit); (b) a fold release copy `non_fold_v2<arm>` with
only the daily networks replaced (`build_release_daily_swap.py`-style), gated numpy == PyTorch on the daily step
(max relative difference ≤ 1e-5); (c) its end-to-end one-core cost per cell-year (`run_emulator_non.py`, as ADR 0344).
If no candidate passes, no package change.

## 3. Option 2 — NPP aimed at the extreme years

* **MEPx** (§1): its 5 seeds also free-run on the original's stand, both members, every leg (as ADR 0369), mean →
  cell carbon `mepx`.
* **Yearly correction** (`xtf_npp_corrector.py`): LightGBM predicts (true − emulated) annual NPP and GPP from the
  emulated NPP, GPP, their departures, last year's emulated NPP, the 25 yearly climate statistics of the year / the
  year before / the trailing 30 years, latitude, CO2. Fitted on the held-out cells under the 8 training climate
  models (where the networks are out of sample), both members; validation every 5th of those cells; applied
  everywhere. Only the decision group (held-out cells × held-out models) is out of sample for it. Two versions:
  **corb** (on the deployed networks' NPP) and **cormep** (on MEP's).
* **Scores** (held-out cells × held-out models): the NPP departure correlation with the original, over all cell-years
  and over the extreme ones (each cell's top 10 % |true departure|); die-off capture through the deployable
  carbon-state route of ADR 0369 (**STK&lt;tag&gt;** = carbon-state model + set transformer fed that cell carbon, 2
  seeds; STKe = 0.283) and **STC&lt;tag&gt;** (STCe with it; 0.265).
* **Decision:** a version **helps the die-offs** if STK&lt;tag&gt; ≥ STKe + 0.03 (0.313); it is **worth a free-running
  test** (new record) if STK&lt;tag&gt; ≥ STCe + 0.05 = 0.315 with skill ≥ STCe's (0.539) and a 30-yr death-rate ratio
  ≤ 1.1 × STCe's (0.90). The bound with the original's cell NPP is 0.385 (STKc).

## 4. What this record does not do

No change to any existing release; no full-grid run; no paper text. The tree-death tests remain teacher-forced.

## 5. Amendments

* The ensemble runner and scorer were smoke-tested on one leg with 2 seeds (job 2696967); those outputs were deleted
  before the real runs.
* `STKmepx` seed 1's predictions were not written by the chained job (it ended right after the seed's training);
  the prediction and the tree score were re-run (job 2701283). No other change.

## 6. Results (2026-10-23)

### 6.1 Options 1 and 3 — complete emulator (5-member ensembles on the emulated stand; jobs 2696966, 2696982, 2696983)

`xtf/daily/ens/score_stand_emul_main2.csv`, `ratios_stand_emul_main2.csv`; 30 rising-CO2 legs, held-out cells.
q = typical error ÷ the deployed ensemble's (B); median over legs × windows; worst = largest leg-window q; drift
excess = the largest leg's drift minus B's on that leg.

| ensemble | NPP q (worst) | GPP q (worst) | ET q (worst) | runoff q (worst) | worst drift excess NPP / GPP / ET / runoff | rule |
|---|---|---|---|---|---|---|
| MEP running means + place | 0.849 (1.11) | 0.882 (1.16) | 0.902 (1.24) | 0.875 (1.25) | 0.53 / 0.51 / 0.34 / 0.36 | fails (drift) |
| MEPx MEP + extreme-year weights | 0.851 (1.07) | 0.892 (1.16) | 0.895 (1.09) | 0.889 (1.24) | 0.16 / 0.43 / 0.38 / 0.24 | fails (drift) |
| TP transformer + place | **0.813** (1.03) | 0.871 (1.10) | 0.865 (1.17) | 0.853 (**1.52**) | 0.26 / 0.20 / 0.42 / 0.86 | fails (drift, runoff worst leg) |

The deployed ensemble itself, late window, vs a second run of the original: GPP 2.04, ET 3.49, NPP 2.50, runoff 5.53
(on the original's stand ADR 0368 measured 1.30–1.35 for GPP: the emulated stand dominates the daily error here).

**Verdict by the rule: no candidate passes** ⇒ no package change, no fold release copy, no end-to-end timing (§2).
All three cut the median error 11–19 % (TP most: NPP −19 %, ET −14 %, runoff −15 %); every one fails the "no leg's
drift more than 0.08 above the deployed networks'" clause, on many legs (MEP 7–16 of 30 per flux, TP 4–21), and TP
also has one runoff leg-window at 1.52. Their gain is larger early than late (median q 2021–2050 vs 2071–2100: MEP
NPP 0.87 → 0.82 but runoff 0.86 → 0.91, ET 0.88 → 0.94; TP ET 0.80 → 0.93, runoff 0.80 → 0.94).

**TP's cost (not measured end to end):** one network's daily step 1.15e-2 core-s per cell-year (ADR 0369 bench);
with 5 members and the rest of the emulator unchanged that sums to ≈ 5.8e-2 vs 7.3e-3 for the release and 0.95 for
the original ⇒ ≈ 16× fewer core-seconds than the original instead of ≈ 130×. This is a sum of measured parts, not an
end-to-end measurement.

**Post-hoc (not pre-registered): is the fixed place description why the gain fades?** 3-member ensembles B3, ME3
(running means, no place), MEP3 (job 2701284, `ratios_stand_emul_main2_ph3.csv`, vs B3): median q early / late — ME3
NPP 0.92 / 0.86, ET 0.91 / 0.92, runoff 0.96 / 0.96; MEP3 NPP 0.87 / 0.82, ET 0.94 / 0.95, runoff 0.87 / 0.92. Legs over
the drift limit: ME3 3–10 per flux, MEP3 5–11. ⇒ the network WITHOUT the place description breaks the drift clause as
often, so the stale 2020–2049 place description is not the cause. Untested: how often two ensembles of the SAME
network break that clause (its noise level on this venue) — a B-vs-B check would say whether the clause can be
passed by any network here.

### 6.2 Option 2 — NPP aimed at the extreme years (jobs 2696968, 2696979, 2696983, 2701283)

| version | NPP departure r, held-out × held-out models: all / extreme years | die-off capture via the carbon-state route (STK) | STC route |
|---|---|---|---|
| deployed networks (STKe / STCe) | 0.55 / 0.56 | 0.283 | 0.265 |
| corb: yearly correction of the deployed networks' NPP | 0.69 / 0.72 | 0.288 | 0.266 |
| MEP (ADR 0369) | 0.69 / 0.73 | 0.291 | 0.265 |
| cormep: yearly correction of MEP's | 0.69 / 0.74 | 0.287 | — |
| MEPx: MEP trained with 5× weight on extreme years | (all cells 0.742 vs MEP 0.740) | **0.308** | — |
| original's cell NPP (bound, STKc) | 1 | 0.385 | 0.350 |

(skill 0.624–0.626 for every STK version; 30-yr death-rate ratio 0.82–0.85; seed spread ≤ 0.010 capture.)

**Verdict: no version helps the die-offs** (bar STKe + 0.03 = 0.313; best MEPx +0.025) and none is worth a
free-running test (bar 0.315). The yearly correction lifts the year-to-year NPP agreement of the deployed networks
from 0.55 to 0.69 (0.72 in the extreme years) and moves die-off capture by +0.005: the cell's yearly NPP departure is
not what limits the deployable route. Weighting the extreme years in training does a little more (+0.025) without
changing the departure correlation, i.e. it changes the size of the extreme-year NPP drops rather than their timing.
The gap to the bound (0.308 vs 0.385 with the original's own cell NPP) remains.

