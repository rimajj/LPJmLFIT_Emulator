# 0357 — Which hard kill drives the original's drought die-offs? (diagnostic, pre-registration)

* **Status:** pre-registered 2026-10-21, while the diagnostic job runs and before its output was read.
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
