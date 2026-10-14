# STATE — the single current state and handoff (one development stream, ADR 0319)

> The `## NEXT — start here` block is what the SessionStart hook replays. **Refresh it before a session ends.**
> Narrative → `JOURNAL.md` (append). Durable cross-cutting facts → `MEMORY.md`. Decisions → next free ADR number
> (**0339**). History of the retired parallel lines: `lines/{S,M,E,O,X}/STATE.md` + `JOURNAL.md` (read-only).

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
| daily carbon/water exchange, learned | **exists (phase A, offline; phase B — fed the emulated stand — measured, ADR 0331: +10–40 % error; with the deployment model arm D on all 13 climate-model legs, ADR 0337: the full learned emulator's daily fluxes are GPP 2.0–2.9×, ET 2.1–3.9×, NPP 3.3–4.6×, runoff 3.9–7.7× a second run, totals ≤ 2.5 %, the stand adds a median 13 % (GPP) to 35 % (ET); falsifier fired on two IPSL legs ⇒ the stand map is now the lever).** **End-to-end timing (ADR 0337 §5): 6.55e-3 core-s per cell-year on one core for structure + stand + daily model in one loop (daily model 97 %), 41× less than the original at 25 patches, ≈ 1 000× at 500 (the original measured at one cell).** One small network + closed snow / top-metre / deep water stores, trained on the panel runs of the original (ADR 0320–0328; skill `daily-model`). Best setup: five-seed ensemble, NPP = GPP − respiration, no humidity input (the original's daily exchange never reads it, ADR 0327), deep store draining into runoff (ADR 0326). **On the second-run yardstick:** GPP / ET typical error 2–3× a second run ✓, NPP 2.7–3.5× (3× proposed) ✗, runoff 3.9–5.5× ✗ (the ET error carried through — runoff is a small residual of rain minus ET); area totals ≤ 1.8 % ✓; deep store stable ✓; no drift on the MPI climates ✓; **under the unseen climate model the GPP / NPP gap still grows 1.29× / 1.35× over the century ✗** (removing humidity was a null). Cost 6.4e-3 core-s per cell-year. The stand still comes from the original (flatters the score). **More climate models in training (ADR 0328, 2026-10-12): fails, falsifier fired** — levels improve 10–20 %, the gap still grows on UKESM / IPSL, NPP totals now 3–5 % off (plant respiration 1.5–3 % too high everywhere). A structured carbon head (ADR 0332) was much worse (daily GPP fit 2.3× worse) — closed. **Warm-climate coverage (ADR 0333, corrected by ADR 0336):** the effect is small — with IPSL in training UKESM's GPP/NPP gap growth 1.19/1.27 → 1.15/1.25 (the first reading, 1.30/1.41, came from early-stopped members); swapped roles IPSL ssp585 1.13/1.20 → 1.06/1.14. Run-to-run noise (ADR 0336 §6): the UKESM effect is within it, the IPSL GPP effect beyond it. ⇒ still train on every climate model (no measured cost on GPP). **The "constant respiration excess" is four places (ADR 0334):** none on training cells (≤ 0.8 %) or on 200 of 240 held-out cells; ~80 % of it is four held-out blocks at 33–47° S (NPP −7 … −11 %), two at the edge of what training covers. Arms L (hemisphere-aware season input) and V (80 M samples) **both null** (ADR 0334 §4) ⇒ it is coverage of places. Deployment candidate (all 14 legs, arm D, ADR 0335): not passed — UKESM drift 1.25 → 1.17 but early ET 16–28 % worse on three legs; **11 members in 7 ensembles had stopped mid-schedule (ADR 0336); repaired:** the L/V nulls stand, **arm D is the deployment model** (UKESM drift 1.25 → 1.17, early ET ×1.16–1.28 on three legs). **Run-to-run noise of one ensemble: ±9–20 % per leg in typical error, 0.05–0.08 in drift** (ADR 0336 §6) — most earlier arm margins are inside it |
| re-implemented daily physics (F_diff) | C-validated at 5 biome cells with known residuals (ADR 0125–0139); 4.62× slower than the original. Parked as the fidelity oracle/reference, not the runtime path |
| energy closure, online coupling | built for Hainich / harness level (ADR 0073–0085); not on the critical path until both halves above exist |

## NEXT — start here

1. **Daily model — decided (ADR 0335/0336): the deployment model is arm D** (`D_3x256_seed0..4`, ensemble
   `DE_5seed`: all 14 legs, 40 M samples, five members, calendar season input, deep store draining). Out of sample by
   place only. Its scores and the run-to-run noise they carry: ADR 0336 §6 (one ensemble's typical error moves
   ±9–20 % per leg between seeds). **Owner question (ADR 0336 §6):** more members would cut that noise but multiply
   the daily model's cost (6.4e-3 core-s per cell-year at five members), against the speed goal.
2. **Done 2026-10-14 (ADR 0338): cover carries most of the emulated stand's added error — on every flux, not only
   ET.** Jobs 2483470–72 (`PD_L`/`PD_V`/`PD_C`) scored with `scripts/f2_stand_attribution.py`: median share `s_C` =
   0.70 (GPP) / 0.89 (NPP) / 0.87 (ET) / 0.57 (runoff); leaf area secondary (0.10–0.45); vegetation carbon minor
   everywhere (0.08–0.16, under the pre-registered 0.2 ceiling); additivity holds (pooled median sum 1.19); the
   `s_V ≥ 0.3` falsifier did not fire. The pre-registered guess that leaf area would dominate GPP/NPP was wrong — cover
   dominates those too. **Next:** improve the per-type cover component of the stand map (e.g. learn it as its own
   target with a relative error measure, or constrain the ten covers to sum to the stand total), then re-run phase B
   (ADR 0337's harness) to see whether it narrows the FAIL from item 1's deployment check.
   **Also done 2026-10-14:** phase B with arm D (ADR 0337 §4, FAIL as pre-registered, falsifier fired on IPSL ssp370/585
   late GPP ×1.58/×1.74) and the end-to-end timing (§5, `scripts/bench_coupled_speed.py`, 6.55e-3).
3. **Closed 2026-10-13 (ADR 0334 §4): arms L and V both null.** The hemisphere-aware season input did not move the
   southern respiration excess or the June–September GPP swing (it grew 7–9 %) and worsened test-climate GPP by
   10–19 %; 80 M samples moved NPP < 5 %. The excess is generalisation to places unlike the training cells
   (likely winter-rain grassland at 33–47° S — not tested). Only more / differently placed training cells can address it — a candidate
   next data step if the excess matters for coupling.
3b. **Closed 2026-10-12/13:** more climate models in training (ADR 0328, falsifier fired; levels 10–20 % better but NPP
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
6. **Speed: measured end to end (ADR 0337 §5)** — 6.55e-3 core-s per cell-year, one core, all parts in one loop; inside
   the T31 / T63 allowances of EXECUTION_PLAN §0 (a convention, 0.0135 / 0.030) by 2.1× / 4.6×. The five-network
   ensemble is 97 % (≈ 1.3e-3 per network), so the owner question in item 1 is linear in members. Speed work belongs in
   the daily network (fewer / smaller members, batching on a GPU), not in the structure or stand maps (2 %).
7. Open owner questions: removal of the retired `wt-*` worktrees; whether the relaxed numbers of ADR 0318 §2 are right;
   whether the daily-model numbers proposed in ADR 0325 §3 are right — and, new (ADR 0326 §4), whether runoff should
   carry the same 3× limit as ET when runoff is a small residual of rain minus ET (an ET error of 2–3× a second run is
   necessarily 4–5× in runoff terms). New (ADR 0330 §1): whether the structure map's drift should be judged after
   the start state has faded (2081–2100 vs 2051–2070) rather than against 2021–2040, where it is better than a second run.
