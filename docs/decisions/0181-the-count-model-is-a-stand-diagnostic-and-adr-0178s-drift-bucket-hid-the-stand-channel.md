# 0181 — the count model is a STAND DIAGNOSTIC: handed FIT's own stand it delivers 0.29 of the aggregate warming response, essentially all of it through the stand columns, and ADR 0178's "drift" bucket contained that channel all along

* Status: accepted
* Date: 2026-08-13
* Line: S (tier-3 block 0170–0189)
* **Answers the question ADR 0180 §4 left open and the line handoff named as "the one question that could
  redirect this whole effort".** Withdraws nothing from ADR 0177/0178/0179/0180. **Narrows ADR 0178** on one
  point (§6) — a reading that ADR 0180's text and the handoff both inherited — in the same way ADR 0178
  narrowed ADR 0177.
* Scope: 4 forests + 1 reference arm, **51 767 of the 54 020 tree-bearing cells**, both scenarios, one-step
  C-forced. No LPJmL run. Probe `scripts/slow_stand_forced_response_probe.jl` (job 1772586, 37 min) +
  `scripts/diagnose_truth_yardstick.py` (job 1772872). Output
  `/p/tmp/jamirp/emulator_global/S_stand_forced_response/{summary.csv,yardstick_summary.csv,ctrl/,abl/}`.

---

## 1. The question

ADR 0180 §4 established that the count target is **near-determined by the contemporaneous stand**: with
`n_prev` neutralised the remaining 13 features still reach R² 0.9620 against the persistence null's 0.9623.
It drew the consequence that at runtime those six stand features come from the fast core's own pools, so the
coupled warming response must arrive **through the stand** — and left as a falsifiable [ASSUMPTION] that no
reweighting of the existing feature set can produce FIT's response magnitude.

The measurement that separates the two candidate defects is a table scan, not a run: **drive the count model
with LPJmL-FIT's OWN stand under both scenarios, with no free-running loop, and see whether the response
appears.** If it does, the stand→count map is fine and the coupled failure is that the fast core does not
move the stand. If it does not, the map cannot express the response whatever it is handed.

## 2. Design, and the control that makes it readable

Every feature in `slow_count_pooled_w20_t8` is built from FIT's own roster and fluxes for that very
`(Cell, Patch, Year)`, so every arm here is **one-step, C-forced** (ADR 0112's first label). Two forests,
**K-fold by cell** (5 folds, a cell's rows predicted only by a forest that never saw that cell), production
hyperparameters, on a 30 373 914-row systematic random sample:

* **CTRL** — the table as it is.
* **ABL** — column 11 (`n_prev`) neutralised **in place** to a constant, so `p`, the column indices and
  `mtry` are identical between arms (ADR 0180 §2, ADR 0126 §5).

**ABL is the headline and CTRL cannot be.** The full feature set contains FIT's own previous-year answer,
and the persistence null already scores an aggregate response ratio of 0.685 against the shipped model's
0.707 — so on this axis CTRL has no power *by construction*. It is a basis check, not evidence.

**Four basis checks passed before any arm was read** (`residual-diagnosis` §3):

| check | this run | published | |
|---|---|---|---|
| persistence-null R² on the sample | **0.9623** | 0.9622 (ADR 0112) | OK |
| CTRL out-of-sample R² | **0.9823** | 0.9824 (shipped) | OK |
| CTRL climate split share | **10.13 %** | 10.20 % (ADR 0179) | OK |
| **CTRL area-weighted aggregate response ratio** | **0.707** | **0.707** (shipped) | exact |

The last one is the important one: the retrained control reproduces the shipped artifact's response
*statistic*, not merely its skill, so the contrast is attributable to the ablation.

## 3. PANEL 1 — FIT's own stand does move, and its climate moves ~8× harder

Median per-cell historic→ssp370 leg shift, in units of that cell's own within-leg sd:

| group | features | med \|Δ\|/sd | frac > 0.5 sd |
|---|---|---|---|
| **CLIM** | `eco_diag_gdd_5` 2.643 · `tas_cold_month` 2.587 | **~2.6** | 0.99 |
| **FLUX** | `bm_inc_cell` 0.405 · `soilmoist` 0.351 · `water_stress` 0.325 · `growth_eff` 0.186 | ~0.32 | 0.14–0.40 |
| **STAND** | `lai` 0.359 · `agb` 0.339 · `fpc` 0.325 · `hmean` 0.307 · `hmax` 0.297 · `age_mean` 0.287 | ~0.32 | 0.28–0.37 |
| AR | `n_prev` 0.290 | 0.290 | 0.29 |
| const | `soil_depth`, `co2` | 0.000 | 0.000 |

So the premise holds: FIT's stand carries a real warming displacement (~0.3 sd), and the climate inputs
carry a very large one (~2.6 sd). Neither channel is empty on the **input** side. `co2` at exactly 0 is the
designed-out input confirming itself (ADR 0004/0107 — faithfulness, not a gap).

## 4. PANEL 2 — the response, on the one blessed statistic

`diagnose_truth_yardstick.py` scores all four arms in the same process, on the same 51 767 paired cells,
through the same code path (ADR 0112). Basis cross-check `r` = 0.9935–0.9948 on every arm.

| arm | per-cell slope | deattenuated (2-seed) | **area-weighted aggregate** | tropical | subtropical | temperate | boreal |
|---|---|---|---|---|---|---|---|
| shipped artifact | 0.958 | 1.006 | **0.707** | −0.51 | +3.41 | +0.93 | +1.07 |
| persistence null | 0.980 | 1.029 | **0.685** | −0.43 | +2.83 | +0.95 | +0.95 |
| CTRL (retrained) | 0.959 | 1.007 | **0.707** | −0.47 | +3.46 | +0.93 | +1.07 |
| **ABL (de-leaked)** | 0.923 | **0.970** | **0.292** | **−2.48** | +4.56 | +0.74 | +1.04 |

**Pre-registered verdict: `H_map` PARTIAL** (thresholds fixed in the probe before the run: SUPPORTED needs
aggregate ≥ 0.50 *and* per-cell slope ≥ 0.70; REFUTED at aggregate ≤ 0.20 *or* slope ≤ 0.30). Handed FIT's
own perfect stand and fluxes, and with the lagged-truth shortcut removed, the map delivers **29 % of FIT's
area-weighted warming response**.

⚠ **The per-cell slope column is reported and is worth nothing.** All four arms sit at 0.97–1.03
deattenuated, including the null. This is ADR 0112's finding reconfirmed at global scale, and it bit here:
**the first version of the probe keyed its printed verdict on that slope and printed `H_map SUPPORTED` for
an arm the binding statistic scores as PARTIAL.** The pre-registered aggregate thresholds were already in
the file; the verdict expression simply did not use them. The script now refuses to print a verdict at all
and names the statistic that decides it (§7.3).

## 5. PANEL 3 — which channel carries what, and this is the deliverable

Per cell, one feature **group** moved from that cell's historic leg mean to its ssp370 leg mean, everything
else held on that cell's own historic rows. At runtime each group is computed by a different part of the
system, so this says which part must carry the response. Mean \|FIT's own response\| over these cells:
1.4145 stems/patch.

| arm | group | computed at runtime by | mean \|Δ\| / truth | through-origin slope vs FIT |
|---|---|---|---|---|
| ABL | **STAND** (`hmean hmax agb lai fpc age_mean`) | **the fast core's own pools** | **1.186** | **0.9944** |
| ABL | FLUX (`bm_inc_cell growth_eff water_stress soilmoist`) | the fast core's daily physics | 0.075 | 0.0370 |
| ABL | **CLIM** (`eco_diag_gdd_5 tas_cold_month`) | **the boundary series** | **0.058** | **0.0162** |
| ABL | AR (`n_prev`) | the emulator's own state | 0.000 | 0.0000 |
| ABL | ALL | — | 1.197 | 1.0150 |
| CTRL | STAND | | 0.486 | 0.4145 |
| CTRL | AR | | 0.698 | 0.4729 |
| CTRL | FLUX | | 0.027 | 0.0140 |
| CTRL | CLIM | | 0.022 | 0.0040 |

Three things follow, and they are the point of this record.

1. **The count model is a stand diagnostic.** In ABL, the stand columns alone carry a through-origin slope
   of **0.994** against FIT's own per-cell response — the whole of it. This is not learned climate skill; it
   is the allometric consequence ADR 0180 §4 identified, now measured. The response the map has is
   **inherited from the stand**, not read off the climate.
2. **The direct climate channel is dead at global scale.** 0.0162 of slope, 5.8 % of magnitude, on 51 432
   cells — an independent global confirmation of ADR 0179's 4.4 % measured on 12 cells with a completely
   different instrument. **And the flux channel is dead too** (0.0370 / 7.5 %), which ADR 0179 never tested;
   those four features are what the fast core's daily physics delivers each year.
3. **In CTRL, `n_prev` absorbs roughly half of the stand's channel** (STAND 0.4145 + AR 0.4729 ≈ ABL's
   STAND 0.9944). That is the mechanism of ADR 0180's 2.85×, seen from the other side.

**Internal check:** ABL's AR corner is **exactly 0.000e+00**, as it must be when `n_prev` is a constant —
i.e. the neutralisation really is in force at prediction time, not only at fit time (ADR 0132 §3: an exact
zero is a red flag unless it is the one you predicted).

## 6. ⚠ THE CORRECTION — ADR 0178's "drift" bucket contains the stand-mediated response

ADR 0180 §4 and the line's `## NEXT` handoff both say *"the coupled response has to arrive through F moving
the stand — ADR 0178 measured that pathway as ~0."* **ADR 0178 measured something narrower**, and the
difference matters because it is what sent the next action toward redesigning the training target.

Read at the source rather than from the prose: `build_rung2_boundary_series.py --freeze` writes a CSV whose
columns are `Year,eco_diag_gdd_5,tas_cold_month,soil_depth,co2` — **the 4 boundary columns and nothing
else**. The other 11 features stay live on the C-grown roster, and the C itself still runs under transient
ssp370 forcing in both arms. So ADR 0178's decomposition is

```
climate  = terminal(transient) − terminal(FROZEN)   -> the DIRECT boundary-feature channel  (its ~0)
drift    = terminal(FROZEN)    − terminal(historic) -> free-running drift PLUS the stand-mediated response
```

The stand-mediated channel was never isolated; it is inside "drift" **by construction**. So ADR 0178's
result reads exactly as *"the direct climate channel is dead"* — which §5 above now confirms globally and
independently — and **not** as *"no warming response reaches the count model"*. Its own §5.2 says as much
("this experiment holds the other 13 on the live roster"); the summary sentence that propagated did not.

Nothing in ADR 0178 is withdrawn: its numbers, its by-construction null (`NP` climate = 0.000 at all 12
cells) and its conclusion about the direct channel all stand. What is corrected is a claim built on it.

This is `residual-diagnosis`'s "read what the arm DOES, not what it is called" and ADR 0105's "an
attribution arm inherits every basis error of its harness", landing on this line's own chain.

## 7. Decision

1. **`H_map` is PARTIAL and is recorded as such.** Given FIT's own stand, the de-leaked map delivers
   **0.292** of FIT's area-weighted warming response — better than nothing and 2.4× short. **Neither
   candidate defect is exonerated**, and the earlier plan to redesign the count target as the next step is
   **not** supported by this measurement: the target is not where the response is lost.

2. **The response that the map does carry is carried by the STAND, so the fast core is on the critical
   path.** A count model fed a stand that does not warm cannot produce a warming response, whatever its
   target. Conversely §5 shows the direct climate and flux channels cannot be reweighted into one: they are
   ≤ 4 % of the per-cell slope with 10 % of the splits (ADR 0179's open-and-empty channel, global).

3. **THE PRE-REGISTERED NEXT ACTION — measure whether the emulator's own stand warms, and it needs no new
   run.** The rung-2 dumps for every arm, cell, scenario and seed are on disk under `/p/tmp/jamirp/S_rung2/`
   and carry full per-tree state (`height crownarea nind fpc leaf_c sapwood_c heartwood_c …`), so each arm's
   own `hmean/hmax/agb/lai/fpc/age_mean` is reconstructable per year. **Score each arm's historic→ssp370
   stand shift against FIT's own (PANEL 1's ~0.3 sd) on the same cells.** Pre-registered reading:
   * arm stand shift ≈ FIT's ⇒ the stand warms and the map still loses the response ⇒ the defect is inside
     S after all, and §4's 0.292 is its size;
   * arm stand shift ≪ FIT's ⇒ the emulator's stand does not warm ⇒ the defect is upstream in the fast core,
     and no S-side retrain can recover it.
   Run the **liveness panel first** (ADR 0179): confirm each arm's stand features actually vary before
   reading any shift.

4. **The `n_prev` de-leak is now priced on the blessed statistic, and the price is negative.** ADR 0180
   measured +2.85× on the direct climate channel; here the same ablation takes the **aggregate response**
   from 0.707 to 0.292 and the **tropical band** from −0.47 to **−2.48**. Both are true — the direct channel
   triples while the total falls — because the shipped model's aggregate is mostly persistence. ⇒ **do not
   flip `roster_n_prev` opportunistically**; ADR 0180's "flip it if a retrain touches the conditioning
   anyway" is superseded by a measured cost on the deliverable's own axis.

5. **No flag flipped, no artifact regenerated, nothing shipped moved.** Both jobs write only to `/p/tmp`.

## 8. Two things captured because they cost something here

* **`diagnose_truth_yardstick.py` writes its summary to a COMMITTED shared fixture by default**
  (`test/testitems/references/S_truth_yardstick_summary.csv`), and a `COUNT_DIR`-only invocation **drops
  every trait row from it** — 66 deletions, 24 insertions. Running it from a line worktree therefore
  silently regenerates a shared baseline, which is an integration point (CLAUDE.md §9), not a side effect.
  **Always `export OUT_SUMMARY=` to scratch.** Reverted here before anything was committed; the same class
  as CLAUDE.md §9 item 6 (a hard-coded absolute path writing into the integrator's worktree).
* **A pre-registered threshold is not a pre-registered verdict.** The correct thresholds were in the file
  and the verdict expression used a different, powerless statistic — see §4 and `residual-diagnosis`.
