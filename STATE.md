# STATE — the single current state and handoff (one development stream, ADR 0319)

> The `## NEXT — start here` block is what the SessionStart hook replays. **Refresh it before a session ends.**
> Narrative → `JOURNAL.md` (append). Durable cross-cutting facts → `MEMORY.md`. Decisions → next free ADR number
> (**0327**). History of the retired parallel lines: `lines/{S,M,E,O,X}/STATE.md` + `JOURNAL.md` (read-only).

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

## Where things stand (2026-10-10)

| part | state |
|---|---|
| forest structure, 30-year windows | best setup = per-cell anchor + gradient-boosted climate shift, log target on biomass per tree (ADR 0316 §11–13). On the 1 050-cell panel, held-out climate model: passes the relaxed standard except dense typical-cell tree count (1.23× a second run) / biomass per tree (1.18×) on the case count and the sparse stem total (19.5 %). Dense stem total low in 14/15 cases. Not yet run on the global venue with these changes, not yet year-by-year, not timed |
| daily carbon/water exchange, learned | **exists (phase A, offline).** One small network + closed snow / top-metre / deep water stores, trained on the panel runs of the original (ADR 0320–0324; skill `daily-model`). Best arm, a five-seed ensemble with NPP = GPP − respiration: **on the second-run yardstick (ADR 0325):** GPP / ET typical error 2–3× a second run ✓, NPP 2.9–3.6× (3× proposed) ✗, runoff 11–14× ✗; area totals ≤ 1.7 % ✓ (runoff 5.1 %); no drift on the MPI climates ✓; **under the unseen climate model the GPP / NPP gap to the original grows 1.3× / 1.4× over the century ✗** (per-day carbon response outside the training climates — the one-step run grows identically, so not the stores); deep store walks away (2.0–2.8 m vs 0.22 m) ✗. Cost 6.4e-3 core-s per cell-year ✓. The stand still comes from the original (flatters the score) |
| re-implemented daily physics (F_diff) | C-validated at 5 biome cells with known residuals (ADR 0125–0139); 4.62× slower than the original. Parked as the fidelity oracle/reference, not the runtime path |
| energy closure, online coupling | built for Hainich / harness level (ADR 0073–0085); not on the critical path until both halves above exist |

## NEXT — start here

1. **Daily model, water split** — the deep store walks away from the original (2.0–2.8 m over 81 yr vs 0.22 m) and runoff is
   11–14× a second run (ADR 0325). Fix the deep/runoff partition (e.g. make deep drainage a function of the stores
   with the original's near-zero annual net, or learn runoff+deep jointly against the original's runoff); score with
   `scripts/f2_relative_score.py`. Prerequisite for phase B anyway.
2. **Daily model, carbon outside the training climates** — the GPP/NPP gap grows 1.3–1.4× over the century under the unseen
   climate model, and NPP typical is 2.9–3.6× a second run on trained climates (3× proposed). Probably one problem;
   pre-register one arm against both (candidates: more climate diversity in training — other legs/members of the
   panel, spatial regularisation — or physically constrained carbon heads). Then, before phase B, build the map from the
   structure emulator's outputs to the stand inputs (`lai_stand`, `vegc`, `fpc_stand` per PFT).
3. **Structure: remove the dense-cell low bias** (anchor vs learned shift vs warming; measure first, then one
   pre-registered treatment). Score with `explore_relaxed_standard.py` + `explore_panel_abs_err.py`.
4. **Year-by-year drift test of the structure map** on the panel (trailing-window climate each year vs the original's
   yearly 2020–2100 output in `…/xpanel/yearly/`); define the no-drift number before running.
5. **Speed:** the daily half is measured (above); time the structure half and the whole per cell-year; never quote a
   speed-up without the end-to-end number and the original's cost at its patch count.
6. Open owner questions: removal of the retired `wt-*` worktrees; whether the relaxed numbers of ADR 0318 §2 are right;
   whether the daily-model numbers proposed in ADR 0325 §3 are right (3× a second run on trained climates, no drift
   = gap grows ≤ 1.2× over the century; both chosen after the scores were seen).
