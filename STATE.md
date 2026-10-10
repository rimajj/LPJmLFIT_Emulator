# STATE — the single current state and handoff (one development stream, ADR 0319)

> The `## NEXT — start here` block is what the SessionStart hook replays. **Refresh it before a session ends.**
> Narrative → `JOURNAL.md` (append). Durable cross-cutting facts → `MEMORY.md`. Decisions → next free ADR number
> (**0320**). History of the retired parallel lines: `lines/{S,M,E,O,X}/STATE.md` + `JOURNAL.md` (read-only).

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
| daily carbon/water exchange, learned | **nothing exists.** Plan arm F2 (EXECUTION_PLAN §6). Data: 186 GB global daily output 2000–2019 (`/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output`), plus daily outputs of the panel members (Track D) |
| re-implemented daily physics (F_diff) | C-validated at 5 biome cells with known residuals (ADR 0125–0139); 4.62× slower than the original. Parked as the fidelity oracle/reference, not the runtime path |
| energy closure, online coupling | built for Hainich / harness level (ADR 0073–0085); not on the critical path until both halves above exist |

## NEXT — start here

1. **Learned daily water–carbon model, phase A (offline learnability).** Pre-register first (inputs: daily forcing +
   the annual stand state; soil water as an explicit state with the bucket closed by construction; split by spatial
   blocks and held-out scenario; bar from EXECUTION_PLAN §6: annual GPP, ET, NPP within ±5 %, SSP370 GPP change inside
   the original's two-member band, ≤ 0.01 core-s per cell-year; nulls: climatology per cell, persistence). Start by
   inventorying exactly which daily variables and stand-state inputs exist on disk.
2. **Structure: remove the dense-cell low bias** (anchor vs learned shift vs warming; measure first, then one
   pre-registered treatment). Score with `explore_relaxed_standard.py` + `explore_panel_abs_err.py`.
3. **Year-by-year drift test of the structure map** on the panel (trailing-window climate each year vs the original's
   yearly 2020–2100 output in `…/xpanel/yearly/`); define the no-drift number before running.
4. **Speed:** time each half per cell-year; never quote a speed-up without the end-to-end number and the original's
   cost at its patch count.
5. Open owner questions: removal of the retired `wt-*` worktrees; whether the relaxed numbers of ADR 0318 §2 are right.
