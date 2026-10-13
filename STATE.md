# STATE — the single current state and handoff (one development stream, ADR 0319)

> The `## NEXT — start here` block is what the SessionStart hook replays. **Refresh it before a session ends.**
> Narrative → `JOURNAL.md` (append). Durable cross-cutting facts → `MEMORY.md`. Decisions → next free ADR number
> (**0335**). History of the retired parallel lines: `lines/{S,M,E,O,X}/STATE.md` + `JOURNAL.md` (read-only).

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
| daily carbon/water exchange, learned | **exists (phase A, offline; phase B — fed the emulated stand — measured, ADR 0331: +10–40 % error).** One small network + closed snow / top-metre / deep water stores, trained on the panel runs of the original (ADR 0320–0328; skill `daily-model`). Best setup: five-seed ensemble, NPP = GPP − respiration, no humidity input (the original's daily exchange never reads it, ADR 0327), deep store draining into runoff (ADR 0326). **On the second-run yardstick:** GPP / ET typical error 2–3× a second run ✓, NPP 2.7–3.5× (3× proposed) ✗, runoff 3.9–5.5× ✗ (the ET error carried through — runoff is a small residual of rain minus ET); area totals ≤ 1.8 % ✓; deep store stable ✓; no drift on the MPI climates ✓; **under the unseen climate model the GPP / NPP gap still grows 1.29× / 1.35× over the century ✗** (removing humidity was a null). Cost 6.4e-3 core-s per cell-year. The stand still comes from the original (flatters the score). **More climate models in training (ADR 0328, 2026-10-12): fails, falsifier fired** — levels improve 10–20 %, the gap still grows on UKESM / IPSL, NPP totals now 3–5 % off (plant respiration 1.5–3 % too high everywhere). A structured carbon head (ADR 0332) was much worse (daily GPP fit 2.3× worse) — closed. **Warm-climate coverage (ADR 0333):** with IPSL in training, UKESM's GPP gap growth 1.30 → 1.15 (passes), NPP 1.41 → 1.25 (just over 1.2), NPP totals 4.7 → 2.4 %; nothing worse. **Confirmed with the roles swapped** (train on UKESM, test IPSL: ssp585 GPP/NPP drift 1.22/1.27 → 1.12/1.13). ⇒ train on every climate model. **The "constant respiration excess" is four places (ADR 0334):** none on training cells (≤ 0.8 %) or on 200 of 240 held-out cells; ~80 % of it is four held-out blocks at 33–47° S (NPP −7 … −11 %), two at the edge of what training covers. Arms L (hemisphere-aware season input) and V (80 M samples) running |
| re-implemented daily physics (F_diff) | C-validated at 5 biome cells with known residuals (ADR 0125–0139); 4.62× slower than the original. Parked as the fidelity oracle/reference, not the runtime path |
| energy closure, online coupli
## NEXT — start here

1. **Daily model — collect arms L and V (ADR 0334, pre-registered; jobs 2476675–86, GPU, chained).** The
   respiration excess of ADR 0333 turned out to be four southern held-out blocks, not a training bias (the planned
   annual-NPP loss term is dropped). Arm L = arm W + `--season-phase local` (hemisphere-aware day-of-year input);
   arm V = arm W + 80 M samples. When `runs/LE_5seed/summary.md` and `runs/VE_5seed/summary.md` exist, score:
   `python scripts/f2_relative_score.py WE_5seed LE_5seed VE_5seed`,
   `python scripts/f2_carbon_split.py WE_5seed LE_5seed VE_5seed --blocks=0,1,2,4` (and `--blocks=-0,1,2,4`),
   and `scripts/sbatch_python.sh f2-season-L scripts/f2_season_residual.py LE_5seed` (July − September GPP swing
   of blocks 2 / 4; arm W 40.9 / 46.4). Append the verdicts to ADR 0334 §4 against its §3 numbers. If the excess
   stays (coverage), go straight to item 2. A missing ensemble result = a member job died (afterok).
2. **Deployment model:** once arms L / V settle (adopt whichever passes), train on all five climate models (no climate model held out) — then the
   only out-of-sample check left is by cell; say so when quoting it.
3. **Closed 2026-10-12/13:** more climate models in training (ADR 0328, falsifier fired; levels 10–20 % better but NPP
   totals 3–5 % off from a 1.5–3 % plant-respiration excess on every leg); a structured carbon head (ADR 0332, much
   worse); phase B on the IPSL legs (ADR 0331 §5, fails like MPI/UKESM: the emulated stand adds 2–36 %, ET most).
   The respiration excess is still open (`f2_carbon_split.py` shows it).
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
