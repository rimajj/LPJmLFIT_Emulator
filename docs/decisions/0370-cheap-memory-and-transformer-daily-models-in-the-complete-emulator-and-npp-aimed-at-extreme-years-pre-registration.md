# 0370 — The cheaper-memory and the transformer daily models in the complete emulator, and a daily NPP aimed at the extreme years (pre-registration, SEPARATE EXPERIMENT)

* **Status:** pre-registered 2026-10-23, before any fit of this record. Results: §6, added after the runs.
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

(none yet)

## 6. Results

(to be added after the runs)
