# 0318 — Relaxed pass standard (dense cells first, sparse cells must not run away) and the full-emulator goal restated

* **Status:** **Accepted — the direction (owner, 2026-10-10). Proposed — the numbers in §2** (line X's; the owner may
  move them). Line X, tier-1 block 0310–0329. **Next free number: 0319.**
* **Amends:** ADR 0317 (the threshold: "10 % worse than a second run on all cells" → §2) and, through it, ADR 0106 §3.
  ADR 0106 §1 (fully emulate the original, especially under climate change) is restated, not weakened (§1).
* **Not propagated.** Nothing written to `MEMORY.md`, `EXECUTION_PLAN.md`, another line's STATE, or
  `~/.claude/CLAUDE.md` (which still carries ADR 0106 §3's 10 % rule). Propagation is the owner's call.
* Scripts: `scripts/explore_relaxed_standard.py` (the scorer, thresholds pre-registered in commit ed54a98d),
  `scripts/explore_panel_abs_err.py` (plain units).

## 1. The owner's words (2026-10-10)

> "we should definetely focus on getting the dense cell as goos as possible. the sparse cells are not as important."

> "I think we have to relax the passing standarts a bit. as long as the dense ells are fine and the sparse cells dont
> drift away completely we should go on.
> AS before the goal is to have a full LPJmL_FIT emulator that emulates everything happening in the mode orders of
> magnitude faster thatn lpjmlfit and does not drift away in transient runs"

And, correcting line X's reply that the daily carbon/water exchange "would still come from the fast daily physics
code":

> "which fast dayly physics structure?!?!?! we established long a gao that the so called "fast physics strucutre" was
> not fast at all. We also want to simulate teh fast physcs structure!!!"

**The correction is right and line X's sentence was wrong.** The re-implemented daily physics is measured **4.62×
slower per cell-year than the original** (ADR 0084), because its per-tree daily step costs 51× the C code's. It is not a
fast path. The goal is an emulator of **everything**: the slow forest structure **and** the daily carbon/water
exchange, both learned, the whole thing orders of magnitude faster than the original, and drift-free over transient
runs. The window-level structure map of ADR 0315–0317 is **one half** of that, not the whole.

## 2. The relaxed standard (proposed numbers)

Per test case (held-out climate model × scenario; truth = an unseen run; "second run" = other runs of the original),
every panel quantity:

| | criterion | limit |
|---|---|---|
| **dense cells** (truth ≥ 5 trees per patch, ~80 % of tree-bearing cells) | D1 typical-cell error | ≤ 1.2 × a second run's |
| | D2 worst-10 % error | ≤ 1.5 × a second run's |
| | D3 area totals of stems and biomass | within 5 % |
| **sparse cells** ("must not run away") | S1 typical-cell error | ≤ 3 × a second run's |
| | S2 area totals of stems and biomass | within 25 % |
| **transient runs** | T1 no drift: the error of a year-by-year run does not grow over 2020–2100 | not yet defined numerically — needs the year-by-year test (§4) |

A criterion passes at the median over cases **and** in ≥ 12 of 15 cases.

## 3. The current best arm against it (panel, A7rH, seed 1, 15 cases; expectations committed before scoring)

| | tree count | biomass per tree | 4 trait medians | totals |
|---|---|---|---|---|
| D1 dense typical | 1.23 (6 of 15 cases) ✗ | 1.18 (9 of 15) ✗ | 0.58–0.87 ✓ | |
| D2 dense worst 10 % | 1.35 ✓ | 1.16 ✓ | 0.48–0.90 ✓ | |
| D3 dense totals | | | | stems 1.6 % ✓, biomass 2.5 % ✓ (second run 0.4 % / 0.7 %) |
| S1 sparse typical | 3.15 ✗ | 1.60 ✓ | 0.83–1.03 ✓ | |
| S2 sparse totals | | | | biomass 9.0 % ✓, **stems 19.5 % (10 of 15) ✗** |

As expected except S2. The dense-cell stem total is **low in 14 of 15 cases** (−0.5 to −5.1 %) — a systematic
shortfall, the first dense-cell target. **The panel is 1 050 cells, not the 54 020-cell global set.**

## 4. What the restated goal implies (line X's reading, not a decision)

1. **Daily exchange must be emulated too.** The plan already has the arm (`EXECUTION_PLAN.md` F2: a learned daily
   water–carbon model, soil water as an explicit state, bucket closed by construction; bar: annual GPP/ET/NPP within
   ±5 %, ≤ 0.01 core-s per cell-year). It is assigned to line O, and **no line O or line M session has run since
   2026-10-08**, so nothing of it exists yet. Starting it is the owner's call (line O session, or a line-X
   learnability probe on the existing daily dataset).
2. **Drift.** The structure map is not recursive: each year's state is a function of climate and the cell's anchor
   only, so errors cannot accumulate by construction. That property has to be **shown** on a year-by-year run
   (trailing-window climate each year vs the original's yearly 2020–2100 output, which already exists on the panel).
3. **Speed** must be measured end to end on the whole emulator, against the original at the patch count it is run at.
   Nothing here is timed yet.
