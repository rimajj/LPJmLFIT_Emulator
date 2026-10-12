# STATE — the single current state and handoff (one development stream, ADR 0319)

> The `## NEXT — start here` block is what the SessionStart hook replays. **Refresh it before a session ends.**
> Narrative → `JOURNAL.md` (append). Durable cross-cutting facts → `MEMORY.md`. Decisions → next free ADR number
> (**0331**). History of the retired parallel lines: `lines/{S,M,E,O,X}/STATE.md` + `JOURNAL.md` (read-only).

## The goal (owner, 2026-10-10, ADR 0318)

> "AS before the goal is to have a full LPJmL_FIT emulator that emulates everything happening in the mode orders of
> magnitude faster thatn lpjmlfit and does not drift away in transient runs"

* **Everything** = forest structure (tree counts, biomass, trait distributions) **and** the daily carbon/water exchange.
  ⚠ The re-implemented daily physics in `src/fdiff.jl` is **4.62× slower** than the original (ADR 0084) — it is not a
  fast path; the daily exchange must be **learned** too (owner: *"We also want to simulate teh fast physcs
  structure!!!"*).
* **Yardstick everywhere = error relative to a second run of the original** (ADR 0317), never a flat ±X %; the daily
  fluxes need not be as close as a second run (owner 2026-10-11, ADR 0325). **Drift = the gap to the original growing
  over time**, not the values changing (owner: *"as long as we are no in equilibirum of course teh values drift"*).
* **Pass standard (relaxed, owner 2026-10-10):** *"as long as the dense ells are fine and the sparse cells dont drift
  away completely we should go on."* Proposed numbers: ADR 0318 §2, scorer `scripts/explore_relaxed_standard.py`.
* **Orders of magnitude faster** than the original, measured end to end at the patch count the original is run at.
* **No drift** in transient (year-by-year) runs.
* Standing closures: no CO2 response (ADR 0004/0107); reuse is authorised, cite (ADR 0081).

## Where things stand (2026-10-11)

| part | state |
|---|---|
| forest structure, 30-year windows | best setup = per-cell anchor + gradient-boosted climate shift, log target on biomass per tree (ADR 0316 §11–13). On the 1 050-cell panel, held-out climate model: passes the relaxed standard except dense typical-cell tree count (1.23× a second run) / biomass per tree (1.18×) on the case count and the sparse stem total (19.5 %). Dense stem total "low in 14–15/15 cases" is a selection effect, not a bias (ADR 0329: with dense cells defined before the run the total is −3.7 … +1.5 %, median 0.0 %); the real limit is that the learned shift explains only 27–49 % of how cells differ in their response to an unseen climate model. **Year by year (ADR 0330):** run each year from the trailing 30-yr climate, its error starts below a second run's (it knows the run's 2000–2019 state) and settles at about a second run's by the 2050s (biomass per tree ~1.0×, tree count ~1.1×), with a slow tree-count creep after that grows with warming; the pre-registered late/early drift rule fails as written (tree count 8/15, biomass per tree 2/15). **Cost 7.8e-5 core-s per cell-year** (the daily half is 6.4e-3, so the whole is ~6.5e-3 ≈ 41× less than the original at 25 patches, ~1 000× at 500; a sum of parts). Not yet on the global venue |
| daily carbon/water exchange, learned | **exists (phase A, offline).** One small network + closed snow / top-metre / deep water stores, trained on the panel runs of the original (ADR 0320–0328; skill `daily-model`). Best setup: five-seed ensemble, NPP = GPP − respiration, no humidity input (the original's daily exchange never reads it, ADR 0327), deep store draining into runoff (ADR 0326). **On the second-run yardstick:** GPP / ET typical error 2–3× a second run ✓, NPP 2.7–3.5× (3× proposed) ✗, runoff 3.9–5.5× ✗ (the ET error carried through — runoff is a small residual of rain minus ET); area totals ≤ 1.8 % ✓; deep store stable ✓; no drift on the MPI climates ✓; **under the unseen climate model the GPP / NPP gap still grows 1.29× / 1.35× over the century ✗** (removing humidity was a null). Cost 6.4e-3 core-s per cell-year. The stand still comes from the original (flatters the score). **Running:** training on two more climate models (ADR 0328) |
| re-implemented daily physics (F_diff) | C-validated at 5 biome cells with known residuals (ADR 0125–0139); 4.62× slower than the original. Parked as the fidelity oracle/reference, not the runtime path |
| energy closure, online coupli
## NEXT — start here

1. **Collect the more-climate-models test (ADR 0328), all chained on SLURM — nothing to submit.** 36 new runs of the
   original with daily output (`S-D-m*-*_daily`; **moved 2026-10-12 09:40 from the standard queue (estimated start
   next day) to the priority queue at 64 cores**, same job ids so the chain holds; each run is 105 independent
   single-process blocks, so fewer cores changes only the time: ~11 min each, one at a time, ~6–7 h for all; ids in
   `/p/tmp/jamirp/trackD/panel/jobs_gfdl-esm4_ssp126_daily.json`) → 36 collectors (`logs/f2col-*`) → array builder
   (`logs/f2-build-new.2463904.out`) → members `f2-C-s0..4` → ensemble **`f2-CE.2463910`** (`runs/CE_5seed`) and the
   control **`f2-HEdr-x.2463911`** (`runs/HEdr_x`). Check with `squeue -u $USER`; if anything sits in
   `DependencyNeverSatisfied`, the step before it failed — read its log, fix, and resubmit the rest with
   `scripts/f2_chain_new_legs.py` (edit it to skip done steps). Then
   `python scripts/f2_relative_score.py HEdr_x CE_5seed` and judge **only** by ADR 0328 §3 (primary: GPP/NPP drift
   ≤ 1.2 on UKESM ssp370 and each IPSL leg, and below the control). Append the result to ADR 0328, update its README
   row, STATE, JOURNAL.
2. If the drift does not fall (falsifier in ADR 0328 §3): pre-register a physically constrained carbon head
   (e.g. GPP as light-use × learned non-negative limiters in temperature / water / stand, so it cannot extrapolate
   into nonsense). Runoff (3.9–5.5×) only improves with ET — no separate water work needed.
3. Before phase B: build the map from the structure emulator's outputs to the stand inputs (`lai_stand`, `vegc`,
   `fpc_stand` per PFT). Every panel run carries them yearly (`annual.parquet`, `fpc_stand.parquet` in each leg dir),
   so the natural form is extra targets of the year-by-year arm (`explore_panel_yearly_drift.py`), then feed them to
   the daily model on its held-out legs and score with `f2_relative_score.py`. Pre-register first.
4. ~~Structure: dense-cell low bias~~ — **done 2026-10-12, ADR 0329: no bias to treat** (a selection effect of
   defining dense cells by the held-out run's own outcome). Report the anchor-defined dense total beside ADR 0318's D3
   (`scripts/explore_panel_dense_bias.py`). The open structure question is how to explain more of each cell's response
   to an unseen climate (27–49 % now; a per-cell linear temperature/water response explains less — not that).
5. ~~Year-by-year drift test~~ — **done, ADR 0330** (`scripts/explore_panel_yearly_drift.py`). Open from it: the
   slow tree-count creep after 2050 that grows with warming (+0.01 / +0.07 / +0.12 for ssp126 / 370 / 585) — the
   only candidate for real drift; a run without the start state would separate memory from climate.
6. **Speed:** structure half measured (7.8e-5 core-s per cell-year, ADR 0330); the daily half (6.4e-3) is 99 % of the
   bill. Still missing: one coupled end-to-end timing once the stand map (item 3) exists — never quote the sum of
   parts as an end-to-end number without saying so.
7. Open owner questions: removal of the retired `wt-*` worktrees; whether the relaxed numbers of ADR 0318 §2 are right;
   whether the daily-model numbers proposed in ADR 0325 §3 are right — and, new (ADR 0326 §4), whether runoff should
   carry the same 3× limit as ET when runoff is a small residual of rain minus ET (an ET error of 2–3× a second run is
   necessarily 4–5× in runoff terms). New (ADR 0330 §1): whether the structure map's drift should be judged after
   the start state has faded (2081–2100 vs 2051–2070) rather than against 2021–2040, where it is better than a second run.
