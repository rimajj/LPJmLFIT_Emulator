# 0325 — The learned daily model is judged relative to a second run of the original; a climate model held out entirely is judged on stability, not on the same level bar

* **Status:** **Accepted — the direction (owner, 2026-10-11). Proposed — the numbers in §3** (chosen *after* the
  scores in §4 were seen; the owner may move them). Next free number: **0326**.
* **Amends:** ADR 0320 §5 (the ±5 % bar of the learned daily model) and the F2 row of `EXECUTION_PLAN.md` §6.
  ADR 0321–0324's results stand as measured; only the yardstick they are read against changes.
* Script: `scripts/f2_relative_score.py` (reads `runs/<tag>/annual.npz`, seconds, no model). Output for the two
  ensemble arms: `…/esm_land_emulator_data/f2/runs/relative_score_RE_A2E.md`.

## 1. The owner's words (2026-10-11)

Asked whether a climate model held out entirely must meet the same ±5 % as the training climates:

> "no, it does not need to meet the same +-5% but is also has to be stable and not drift. what do you mean by 5%
> anymway? did we say we use relative emasures to the second run spread?"

Asked whether the daily fluxes should meet the plan's ±5 % or "as close as a second run":

> "again? did't we already establish to use measures relative to the second run? what was teh updated measures after
> our last talk? Of course it does not need to be as close as a second run."

And, on what "drift" means:

> "by drifting i meanof course drifting relative to the original model. as long as we are no in equilibirum of course
> teh values drift."

So **drift = the gap between the emulator and the original growing over time**, never the values themselves changing
(they must change: a transient climate is not an equilibrium).

## 2. What went wrong

ADR 0317 (2026-10-09) made "error relative to a second run of the original" the yardstick, and ADR 0318 (2026-10-10)
relaxed its thresholds. `EXECUTION_PLAN.md` revision 3 updated the pass test in its §1 but **left the F2 row's old
absolute bar** ("annual GPP, ET, NPP within ±5 %"), and ADR 0320 pre-registered the daily model from that row the
same day. So the daily model was scored on a yardstick the owner had already replaced. The ±5 % meant: the median,
over held-out cells, of the absolute relative error of the 2021–2100 mean annual total (ADR 0320 L2), plus the same
at the biome cells (L1) and on area totals (L3).

## 3. The measure and the proposed numbers

**Measure (ADR 0317 §3, applied to the daily fluxes).** Per held-out cell with mean GPP ≥ 50 gC m⁻² yr⁻¹ (238
cells): emulator error `|E_k − T_k|/|T_k|` (member k's emulator, run on member k's stand, against member k of the
original), second-run error `|T_j − T_k|/|T_k|` over every pair j ≠ k; ratio of the typical (50th centile) and the
bad-cell (90th centile) errors. On 30-year means (2021–2050, 2071–2100, the structure standard's window), on the
climate response (late minus early), on single years per decade (drift), and on cos-lat area totals.
Harness, derived before running: a second run scored as the emulator must give ≈ 1.0 (measured 0.95–1.01), the mean
of the three other runs ≈ 0.82 (measured 0.77–0.85).

**Proposed numbers** (the owner said *not* as close as a second run; the ratio reuses ADR 0318's "must not run away"
value, 3×, which was fixed before these scores; the totals reuse ADR 0318's 5 % / 25 %):

| | criterion | limit |
|---|---|---|
| climates of a model the network trained on (the MPI legs, ssp585 included) | typical-cell error, 30-yr means, GPP / ET / NPP / runoff | ≤ 3 × a second run |
| | worst-10 % cells | ≤ 3 × |
| | climate response, typical cell | ≤ 1.5 × |
| | area totals | within 5 % |
| every leg, and the only level-free test for a climate model held out entirely (owner: stable, not the same level) | **no drift relative to the original:** the typical single-year error ratio (emulator vs a second run, same decades) in 2081–2100 ≤ 1.2 × that in 2021–2040, per flux | |
| | **water stores do not walk away from the original's:** the emulator's deep-store 81-year change within 2 × the original's | |
| | area totals | within 25 % |

In plain units: two runs of the original agree on a cell's 30-year GPP / ET / NPP to **1.0–1.6 %**, so 3× is ≈ 3–5 %
— close to the old ±5 %. The ratio measure does not loosen the daily bar much; it ties it to the original's noise
and makes it comparable with the structure standard.

## 4. The two best arms on it (RE = respiration head, A2E = direct NPP head; both five-seed ensembles)

| | GPP | ET | NPP | runoff |
|---|---|---|---|---|
| typical cell, MPI ssp126 / 370 / 585, early–late window, **RE** | 2.2–2.4 ✓ | 2.0–2.9 ✓ | **2.9–3.6 ✗** | **10.8–13.8 ✗** |
| same, **A2E** | 1.8–2.2 ✓ | 1.9–2.4 ✓ | **2.7–3.3 ✗** | not scored |
| worst-10 % cells, RE | ≤ 2.4 ✓ | ≤ 1.8 ✓ | ≤ 2.8 ✓ | |
| response typical, RE | 1.0–1.6 (ssp585 1.56 ✗) | ≤ 1.0 ✓ | 1.3 / 1.3 / **1.9 ✗** | |
| area totals, RE (second run) | ≤ 1.7 % (0.5 %) ✓ | ≤ 0.4 % ✓ | ≤ 1.0 % ✓ | **5.1 % ✗** (ssp126) |
| drift: error ratio 2081–2100 ÷ 2021–2040, MPI legs, RE (A2E) | 0.94–0.97 ✓ (0.94–1.01) | 0.87–0.92 ✓ | 0.86–1.05 ✓ (0.89–1.08) | 0.85–0.97 ✓ |
| **drift, unseen climate model**, RE (A2E) | **1.32 ✗** (1.31) | 1.04 ✓ (1.05) | **1.42 ✗** (1.44) | 1.02 ✓ |
| deep water store, 81-year change, every leg (original 0.22 m) | **2.0–2.8 m ✗** | | | |
| unseen climate model, RE: area totals | 0.2 % ✓ | 1.1 % ✓ | 2.4 % ✓ | 7.6 % ✓ |

**Readings.**
1. **On the climates it trained on, GPP and ET pass; NPP misses narrowly (≤ 3.6× vs 3×); runoff fails badly.**
2. **On the unseen climate model the emulator drifts away from the original on GPP and NPP** (the gap grows 1.3× /
   1.4× from the first to the last 20 years, relative to a second run in the same years); ET and runoff do not. On
   the MPI legs nothing drifts — the gap is flat or shrinks. **Cause, measured:** the one-step run (water stores reset
   from the original every day) grows identically (NPP 2.6 → 3.7 per decade vs 2.5 → 3.7 free), so it is not the
   carried water walking away; it is the per-day carbon response degrading as that model's climate moves further
   from the training climates. The fix is therefore in what the network learns about carbon under far-out climate
   (more climate diversity in training, or physically constrained carbon heads), not in the stores.
   The deep water store also walks away from the original — 2.0–2.8 m over 81 years against 0.22 m, on every leg. It
   feeds back into nothing (never an input), but it is a constant runoff deficit, and it is why runoff is 11–14× a
   second run.
3. **Basis caveat (flatters the emulator).** In this offline test the emulator is handed the original's own stand
   for the run it is scored against; a second run has its own stand. On `ctl_obs` the emulator's single-year error
   is 0.4× a second run's for that reason and because the four members' `ctl_obs` legs shuffle the observed years in
   different orders (so that leg's "second run" is not a clean one). Once the stand comes from the structure
   emulator its error adds.
4. On this yardstick A2E is slightly better cell by cell and RE better on totals (A2E's NPP total on the unseen
   model is 5.4 %, inside the 25 % held-out limit). Neither is preferred yet; both fail the same flux.

## 5. Consequence for the order of work

The binding problems are now (a) the **deep/runoff split** — a stability failure and an 11–14× runoff error — and
(b) **GPP/NPP drift away from the original under an unseen climate model** (gap grows 1.3–1.4× over the century),
and (c) **NPP cell-by-cell**, ≈ 3–3.6× where 3× is asked. The earlier next step "push the unseen-model NPP level
below 5 %" is replaced by (b): the owner does not require that level for a model held out entirely, only that it
does not drift away. (b) and (c) are probably one problem — the carbon response outside the training climates — and
the next arm should be pre-registered against both.
