# 0357 — Which hard kill drives the original's drought die-offs? (diagnostic, pre-registration)

* **Status:** pre-registered 2026-10-21, while the diagnostic job runs and before its output was read. **Result (§5): the leaf-carbon threshold; nearness to it does not predict the year (AUC ~0.5); the original's own NPP crash 0.90 vs the bucket's 0.88.**
* **Owner instruction (2026-10-21):** "continue as recommended" = STATE NEXT (b5): first confirm which hard kill
  removes the trees, from the existing tree tables, then — if it is the leaf-carbon threshold — give the departure
  model the share of trees close to it.
* **Follows:** ADR 0356 §7 (post-hoc): in the 3 291 shared die-off years of the unseen run, deaths equal the trees' own
  death probability (not fire); 23.3 % of trees die by a hard kill with the hazards below 1, against 11.1 % in other
  years.
* **Code:** `scripts/diagnose_hardkill_cause.py` (job 2653076).

## 1. The two hard kills and how they are told apart

`mortality_tree_ind.c:135-140`: (a) `bm_inc_counter >= 5`, five years in a row of negative growth after turnover;
(b) the "ghost tree fix", leaf carbon below the sapling's (`:63-65`, from the tree's own SLA and its PFT's `lai_sapl`,
`allom1`, `wood_sapl`, `kpr`, `k_latosa`). Leaf carbon per tree is exact from the `ind` columns `LAI`, `fpc_ind`, `SLA`
(crown area = 225 · fpc_ind / (1 − e^(−k·LAI)), leaf carbon = LAI · crown area / SLA). Per tree
`r = leaf carbon / sapling leaf carbon`.

## 2. Pre-registered reading

* **(b) the leaf threshold** if ≥ 80 % of the hard-killed trees have r < 1 and ≤ 5 % of the surviving trees do.
* **(a) the five-year counter** if ≤ 20 % of the hard-killed trees have r < 1.
* In between: both act; report the split.
* Harness: no surviving tree can have r < 1 at the mortality call, so the surviving trees' share below 1 measures the
  reconstruction's own error (a share above 5 % means the reconstruction, not the model, sets the number; then the
  `ind` row's leaf area is not the one the mortality call saw).
* Step 2 preview (reported, no verdict here): how well LAST year's share of living trees with r below 1.25 / 1.5 / 2
  singles out the die-off years (AUC), beside the bucket weather's 0.87 (ADR 0355 C2). If it is the leaf threshold and
  that share separates the years well, the next arm is to emulate it (a new quantity of the forest map) and feed it to
  the departure model — its own pre-registration.

## 3. Expectations (written before reading)

* (b): the run-length result of ADR 0356 (no deepening with consecutive bad years) argues against (a). I expect 85–95 %
  of hard-killed trees below r = 1 and the surviving trees' share below 1 %.
* AUC of last year's near-threshold share: 0.6–0.75 — the stand's vulnerability matters, but the drought decides the
  year.

## 4. Added before reading (2026-10-21): does the year's carbon crash single out the die-off years?

`scripts/diagnose_dieoff_flux_oracle.py` (job 2653081): AUC of the original's own yearly NPP, GPP, transpiration and
mean top-metre soil water (run m4, f2 daily arrays; z against the cell's centred 21-year mean) for the shared
tree-count events, beside the bucket's actual/potential evaporation on the same events (0.87 on all 15 cases, ADR
0355). Exact panel runs (mpi-esm1-2-hr × 3, ukesm1-0-ll ssp370) read first; the `_daily` re-runs of the other three
models are reported separately. Expectation: NPP ≥ 0.92 and above the bucket's — the leaf-carbon kill is the year's
carbon balance. If NPP is not above the bucket's, the emulated NPP is not the input to try next.

## 5. Results (2026-10-21; jobs 2653076, 2653079, 2653081)

**Which hard kill: the leaf-carbon threshold ("ghost tree fix").** Trees with leaf carbon below the sapling's, by death
class (15 held-out cases, unseen run, event cells, 2025–2090):

| class | other years: trees / share r < 1 / median r | die-off years |
|---|---|---|
| hard kill (`mort` = 1, hazards < 1) | 9 411 399 / **0.977** / 0.64 | 436 815 / **0.945** / 0.58 |
| died by chance (`mort` < 1) | 8 208 720 / 0.000 / 2.60 | 356 847 / 0.000 / 3.56 |
| hazards ≥ 1 | 1 606 729 / 0.50 / 1.02 | 110 071 / 0.25 / 4.31 |
| survived | 138 008 096 / 0.104 / 3.08 | 1 490 998 / 0.143 / 2.44 |

* Verdict (§2): **(b), the leaf threshold** — 94.5–97.7 % of hard-killed trees below r = 1 (≥ 80 %), against 0 % of
  trees that died by chance. The five-year counter plays at most a minor part.
* **The harness failed as written and is explained:** 10–14 % of SURVIVING trees reconstruct below 1 (limit 5 %). All
  of them are the year's recruits (age 0: 71.7 % "below 1", every one at r ≥ 0.95, median 1.0 — established AFTER the
  mortality call at exactly the sapling leaf carbon, under 1 by the writer's 6 digits); trees of age ≥ 1: 2 of 33.6 M
  below 1 (three legs, job 2653079). So the reconstruction is exact and the verdict stands.
* **The kill is a one-year drop, not a slow approach:** hard-killed trees sit at a median 0.58 of the threshold in the
  die-off year.

**Step 2 preview: nearness to the threshold barely predicts the year.** Last year's share of living trees with
r < 1.25 / 1.5 / 2: AUC 0.490 / 0.487 / 0.483 with recruits included (all 15 cases), 0.565 / 0.547 / 0.522 for trees
older than a year (three legs, 712 events). Expectation 0.6–0.75 ✗. ⇒ the planned arm (feed the departure model the
share of trees near the threshold) has no signal to carry and is not run.

**§4: the year's carbon crash.** AUC for the shared events (exact panel runs, 917 event years / 59 605 other years;
the `_daily` re-runs of the other three models in brackets, 1 923 / 124 995): the original's own yearly NPP **0.903**
(0.900), GPP 0.891 (0.885), transpiration 0.865 (0.863), top-metre soil water 0.862 (0.855); the bucket's
actual/potential evaporation on the same events 0.884 (0.873). Expectation (NPP ≥ 0.92) ✗; NPP is above the bucket
but by only 0.02.

## 6. Reading

* A drought die-off in the original is many trees whose leaf carbon falls below a sapling's in one year — a per-tree
  threshold crossed by a one-year carbon crash. Neither how close the trees were to it the year before (AUC ~0.5) nor
  any single yearly total (best: the original's own NPP, 0.90) singles out the die-off years sharply; the bucket the
  emulator can already compute gets 0.88 of that.
* So feeding the departure model the emulated NPP would add at most what 0.90 vs 0.88 buys, and it needs the daily
  networks run on all 27 training legs first. The departure model already captures a quarter of a die-off
  (ADR 0355/0356). Reproducing more would need the emulator to carry how the year's carbon balance moves each tree's
  leaf carbon against its threshold — a per-tree (or per-cohort) quantity the stand-level maps do not represent.
