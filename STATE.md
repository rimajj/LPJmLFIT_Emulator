# STATE — the single current state and handoff (one development stream, ADR 0319)

> The `## NEXT — start here` block is what the SessionStart hook replays. **Refresh it before a session ends.**
> Narrative → `JOURNAL.md` (append). Durable cross-cutting facts → `MEMORY.md`. Decisions → next free ADR number
> (**0325**). History of the retired parallel lines: `lines/{S,M,E,O,X}/STATE.md` + `JOURNAL.md` (read-only).

## The goal (owner, 2026-10-10, ADR 0318)

> "AS before the goal is to have a full LPJmL_FIT emulator that emulates everything happening in the mode orders of
> magnitude faster thatn lpjmlfit and does not drift away in transient runs"

* **Everything** = forest structure (tree counts, biomass, trait distributions) **and** the daily carbon/water exchange.
  ⚠ The re-implemented daily physics in `src/fdiff.jl` is **4.62× slower** than the original (ADR 0084) — it is not a
  fast path; the daily exchange must be **learned** too (owner: *"We also want to simulate teh fast physcs
  structure!!!"*).
* **Pass standard (relaxed, owner 2026-10-10):** *"as long as the dense ells are fine and the sparse cells dont drift
  away completely we should go on."* Proposed numbers: ADR 0318 §2, scorer `scripts/explore_relaxed_standard.py`.
* **Orders of magnitude faster** than the original, measured end to end at the patch count the original is run at.
* **No drift** in transient (year-by-year) runs.
* Standing closures: no CO2 response (ADR 0004/0107); reuse is authorised, cite (ADR 0081).

## Where things stand (2026-10-10)

| part | state |
|---|---|
| forest structure, 30-year windows | best setup = per-cell anchor + gradient-boosted climate shift, log target on biomass per tree (ADR 0316 §11–13). On the 1 050-cell panel, held-out climate model: passes the relaxed standard except dense typical-cell tree count (1.23× a second run) / biomass per tree (1.18×) on the case count and the sparse stem total (19.5 %). Dense stem total low in 14/15 cases. Not yet run on the global venue with these changes, not yet year-by-year, not timed |
| daily carbon/water exchange, learned | **exists (phase A, offline).** One small network + closed snow / top-metre / deep water stores, trained on the panel runs of the original (ADR 0320–0324; skill `daily-model`). Best arm, a five-seed ensemble with NPP = GPP − respiration: passes the pre-registered bar on biome cells, area totals (worst 2.3 %), warming response and cost (6.4e-3 core-s per cell-year, one core); **fails one statistic: typical-cell NPP under the unseen climate model, 5.7 % vs 5 %**. GPP/ET typical errors ≤ 3.6 % / 2.8 %. Per-cell response r 0.92–0.98, slope 0.88–0.98. Errors are 2–9× the original's run-to-run noise. The stand still comes from the original; deep/runoff split biased |
| re-implemented daily physics (F_diff) | C-validated at 5 biome cells with known residuals (ADR 0125–0139); 4.62× slower than the original. Parked as the fidelity oracle/reference, not the runtime path |
| energy closure, online coupling | built for Hainich / harness level (ADR 0073–0085); not on the critical path until both halves above exist |

## NEXT — start here

1. **Daily model, NPP under an unseen climate model** — the one statistic still failing (ADR 0324: 5.7 % vs 5 %; one-step
   already 5.1 %). Not moved by capacity, more rows, seed averaging or the respiration constraint. Next candidate: spatial
   regularisation (the limit is the 730 training cells; ADR 0322 §2) — pre-register first, five seeds, ensemble is the arm
   (ADR 0322/0323 protocol), compare on `scripts/f2_compare.py`. Ask the owner whether the held-out climate model must meet
   the same ±5 % (item 6).
2. **Before phase B (coupling the daily model):** fix the deep/runoff split (deep store 1.8 m over 81 yr vs 0.22 m in the
   original), and build the map from the structure emulator's outputs to the stand inputs the daily model needs
   (`lai_stand`, `vegc`, `fpc_stand` per PFT) — the structure emulator does not produce them today.
3. **Structure: remove the dense-cell low bias** (anchor vs learned shift vs warming; measure first, then one
   pre-registered treatment). Score with `explore_relaxed_standard.py` + `explore_panel_abs_err.py`.
4. **Year-by-year drift test of the structure map** on the panel (trailing-window climate each year vs the original's
   yearly 2020–2100 output in `…/xpanel/yearly/`); define the no-drift number before running.
5. **Speed:** the daily half is measured (above); time the structure half and the whole per cell-year; never quote a
   speed-up without the end-to-end number and the original's cost at its patch count.
6. Open owner questions: removal of the retired `wt-*` worktrees; whether the relaxed numbers of ADR 0318 §2 are right;
   whether ±5 % (the plan's bar for the daily model) or "as close as a second run" (ADR 0318) governs the daily
   fluxes — today they pass the first for GPP/ET and fail the second everywhere; and whether a climate model held out
   entirely must meet the same ±5 % (it is the only statistic the best arm fails).
