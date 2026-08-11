# 0170 — The ported establishment rule's kill condition, pre-tested offline: it does NOT fire, but it does NOT clear either, and the level says the recruit port must be flipped TOGETHER with a mortality operator that has room to act

* Status: accepted
* Date: 2026-08-11
* Line: S (tier-3 block 0170–0189, opened here; the tier-2 block 0100–0119 was closed by ADR 0119)
* Supersedes: nothing. Extends ADR 0119 §6 (the pre-registered arm and its kill condition), ADR 0118
  (the survivor-marginal double count), ADR 0045 (the two establishment channels), ADR 0101 (one run is
  not a measurement).
* Reproduce: `ARM=recruit MODE=response K_CAP=400 TRAIT_MORT=0 scripts/run_response_seed_ensemble.sh S-recA 40`
  (and `TRAIT_MORT=1 … S-recB 40`) → `scripts/summarize_response_seed_ensemble.py 'logs/S-recA*.out'`.
  Jobs 1759211–1759428, ~2 min each. Eligibility table: `scripts/build_estab_eligibility.py`, jobs
  1759338 / 1759339 / 1759435.

---

## 0. Reconciliation with the ADR this extends (the panel every extension opens with, ADR 0116 §4)

ADR 0119 §6 pre-registered: arm = rung 2 on line M's roster harness, R0 = pinned copula vs R1 = ported
rule, both under the C1 mortality arm; **kill condition** = if the recruit channel makes the error
climate-dependent the way the count recursion did (ADR 0112–0116), the flip is REFUSED and that is the
result. Nothing in that registration is changed here. This ADR reports a **cheap offline pre-test of the
same contrast at one cell**, run before M's harness exists, plus the per-cell eligibility table that the
rule needs to run anywhere but a hand-configured cell.

**Scope, stated before any number: Hainich, cell 42490, 1 of 54 020 (guardrail 6). This is a smoke test
of the kill condition. It is not fidelity evidence and it is not the flip test.**

---

## 1. The measurement

The 2×2 of `scripts/trait_mortality_arm_probe.jl` gains a third dimension, `ARM=recruit`: the contrast
axis becomes the recruit channel (R0 = the pinned `recruit_copula_hainich.rcop`, R1 =
`recruit_establishment`), with the count DRF, the forcing pair, the seed, the year indices, `k_cap = 400`
and the `trait_mortality` setting held identical on both sides. Two ensembles, because ADR 0119 §6 writes
the rung-2 arm under the C1 mortality arm while the shipped configuration has it off:

* **A** — `trait_mortality = false` on both sides (the emulator as it ships), 40 of 40 seeds usable;
* **B** — `trait_mortality = true` on both sides (ADR 0119 §6's C1), 36 of 40 usable — **4 seeds violated
  the ADR-0101 preconditions (1–4 hard kills, 2 of them also a count-override year) and are excluded, not
  averaged in.** Arm A produced zero such violations, so the combination of the ported recruit rule with
  the hazard is what wakes them; that is itself a result for rung 2.

Community `nind`-weighted wood density, mean over the last 20 years, mean ± SEM over seeds, in units of
FIT's own per-cell historic→ssp370 shift (+2432.9 gC/m³, ADR 0046 §1):

| quantity | A (`trait_mortality` off) | B (on) |
|---|---|---|
| level effect R1 − R0, historic | **+19 701 ± 1 281** gC/m³ (t 15.4) | **+24 186 ± 1 616** (t 15.0) |
| level effect R1 − R0, ssp370 | **+27 990 ± 2 284** (t 12.3) | **+33 774 ± 2 810** (t 12.0) |
| R0's own warming response | **−0.747 ± 0.236 ×FIT** (t −3.2) | −0.269 ± 0.292 (t −0.9, n.s.) |
| R1's warming response | **+2.660 ± 1.010 ×FIT** (t 2.6) | **+3.671 ± 1.294** (t 2.8) |
| R1 − R0 contribution to the response | **+3.407 ± 1.009 ×FIT** (t 3.4) | **+3.941 ± 1.288** (t 3.1) |
| the SAMPLER's own scenario response (mean drawn `wooddens`) | +0.109 ± 1.706 (n.s.) | **+4.725 ± 1.555** (t 3.0) |
| realised inherited share, historic | 40.8 % | 42.0 % |

The realised inherited share matches the closed form (`w_inherit = 4/(4+6) = 0.400` at this cell's
six-PFT eligible set) to within a percentage point, and the seedbank reaches ~500 individual-years, so
**both channels ran and the feedback channel was live** — the two preconditions ADR 0119 wrote into
`EstabDiag` before any arm existed. The k-cap merge was dormant in every run.

## 2. What it says about the kill condition — it does NOT fire, and it does NOT clear either

**The kill condition as written is about a specific failure**: the count recursion's error became
climate-dependent and manufactured ~90 % of FIT's true signal **with the wrong sign** (ADR 0115 §3). The
recruit channel does the opposite at this cell: **R0's own warming response is significantly WRONG-SIGNED
(−0.75 ×FIT against FIT's +1), and R1 turns it positive (+2.66).** So the port does not introduce a
wrong-signed climate dependence — it removes one.

It does not clear the criterion either, and the reason is the magnitude and the level:

1. **The response overshoots.** |R1 − truth| = 1.66 ×FIT against |R0 − truth| = 1.75 (arm A) — a
   statistical dead heat, sign notwithstanding. Under the C1 mortality arm it is **worse**: 2.67 vs 1.27.
   Crossing zero from −0.75 to +2.66 is not an improvement in error, and the target is 1.0, not
   as-high-as-possible (the one reading of ADR 0109 that did not survive, `EXECUTION_PLAN` item 3).
2. **The LEVEL moves, hugely and certainly.** The community mean goes from 230 571 ± 580 (R0, historic)
   to 250 272 ± 1 279 (R1) — **+8.5 %**, i.e. **8.1× FIT's entire warming shift as a static offset**,
   at t = 15. Against the fixture's own FIT-derived starting value of 235 470, R0 ends 2.1 % below and R1
   4.8 % above. **A recruit channel that shifts the standing community by 8.5 % cannot be flipped on
   fidelity grounds**, whatever it does to the response, and ADR 0106's criterion is a 10 % band on
   levels as well as responses.
3. **The mortality arm does not absorb it.** This was the natural hypothesis — ADR 0118 §1 showed the
   copula's marginals already carry survivor selection, so removing that (the port) should be paired with
   adding the selection operator (`trait_mortality`). Measured, arm B's level effect is **larger**
   (+24 186), not smaller. The mechanism is already on the record: at this cell the hazard is throttled by
   the count channel — θ median 8.5e-12, the DRF's demanded |ρ−1| is a median 0 %/yr against the hazard's
   1.688 %/yr (ADR 0049 item 5, ADR 0117 item 4). **The operator has nothing to redistribute, so it cannot
   remove the over-dense recruits the ported rule supplies.**

## 3. Decision

1. **`recruit_establishment` stays OFF by default.** ADR 0119 §6's flip criterion is unchanged and
   unmet; this pre-test adds two conditions to it rather than replacing it.
2. **Two conditions added to the flip criterion, pre-registered here so they cannot be reinterpreted
   after M's run:**
   * **read the LEVEL, not only the response** — the flip requires the community trait means to stay
     inside ADR 0106's band against FIT's own, and at this cell R1 is 8.5 % away from R0 before any
     response is discussed;
   * **read θ first** (already ADR 0118 §3's condition) — this pre-test is consistent with the
     hypothesis that the port is only flippable where the mortality operator has room to act, and rung 2
     is the first place that can be true, because there the roster comes back from the C each year.
3. **The rung-2 arm should run BOTH mortality settings**, not only C1. The two differ here in the level
   effect (+19 701 vs +24 186), in the sampler's own scenario response (n.s. vs +4.73 ×FIT) and in
   whether hard kills fire at all (0/40 vs 4/40).
4. **ADR 0101's seed guidance does not transfer to this arm.** The double difference's seed sd is
   **6.4–7.8 ×FIT** here against 0.67–1.74 for the `trait_mortality` arm — 4–10× wider — so the 8–12 seeds
   that resolve that arm resolve nothing here. 40 seeds give SEM ≈ 1.0 ×FIT, which is what made the
   contribution resolvable at all. Size the ensemble from the arm's own spread, not from ADR 0101's
   number.

## 4. The per-cell eligible-PFT table, and the C fact that changes how it must be read

`scripts/build_estab_eligibility.py` emits `Cell, Year, temp_min20, temp_max20, gdd5_annual, aprec,
elig_mask, n_elig, w_inherit` (+ the two boundary-basis comparison columns and an `aprec`-free variant)
for all 67 420 cells × 20 historic years, gated against FIT's own `ind` output.

**a. The gate's temperature input is NOT the boundary table's `tas_cold_month`, and the difference
decides the boreal PFTs.** FIT's `temp_min20` is `mean_y (min_m T_{y,m})` (`climbuf.c:134-137,153-154`);
the boundary table's column is `min_m (mean_y T_{y,m})`. The second is larger by Jensen — measured, mean
**+0.73 °C**, max +4.14 — and ids 4/5/6 have `temp_high = 0.0`, so at Hainich the boundary basis gives
{1,2,3} while the C's own basis gives **{1,2,3,4,5,6}**, which is the set FIT actually has there.

**b. ⚠ `n_elig == 0` DOES NOT MEAN "nothing establishes here", and this is a correction to how ADR 0119
§1's port is described, not to the port.** FIT's two channels are gated differently:
`establishmentpft_ind.c:91` wraps the **background** per-PFT loop in `aprec >= aprec_min &&
establish(...)`, but the **inheritance** block at `:125` sits OUTSIDE that loop and tests only
`config->inheritance && cell->treelen > 0` — **no `establish()`, no `aprec`**. A cell whose bioclimatic
gate has closed keeps recruiting its own resident genotypes indefinitely. 22.1 % of historic cell-years
are in that state. The closed-form weight already encodes it (`4/(4+n_elig) = 1` at `n_elig = 0`) and
`Establishment.draw_recruit!` implements it (an empty eligible set forces inheritance) — **so the ported
code is right and only the reading of the table needed fixing.** It also means the gate is a statement
about **introductions** only.

**c. The gate passes: 0.076 %** (503 of 660 025 (cell, PFT, establishment-year) triples), with a ±1 yr
establishment-year tolerance and the inheritance exemption of (b). Without the exemption it is 2.75 %.
94 % of the residual is the `aprec` clause in hyper-arid cells, which is what (b) predicts and `ind`
cannot exempt: the parent population there lives below the 5 m emission threshold, so its recruits look
like introductions. **A residual that shifted onto the temperature clauses would not be explained and
must be investigated, not absorbed.**

**d. The gate MOVES: 16 709 of 67 420 cells change their eligible set within 2000–2019 alone**, and at
Hainich under ssp370 it closes from {1,2,3,4,5,6} to {1,2,3} for 48 of 81 years as `temp_min20` crosses
0 °C — which raises the inherited share from 0.400 to 0.571. A fixed per-cell set is therefore wrong for
a quarter of cells, and wrong in exactly the direction the kill condition cares about: **warming hands
MORE of the recruit population to the cell's own seedbank.** The probe consumes the per-year series from
the committed fixture `S_hainich_estab_eligibility.csv`.

**e. `aprec` is the one input whose reconstruction is not independently confirmed** (it is the only
clause the gate ever fails on). Its blast radius is measured rather than assumed: it changes the eligible
set in **7.82 %** of cell-years, and the table ships `elig_mask_noaprec` / `n_elig_noaprec` so any
consumer can bound its own exposure.

## 5. What did NOT change

No committed baseline, no artifact version, no default. `EstabDiag` gained the four drawn trait values
(additive; the diagnostics are only recorded when the opt-in hook is on), and the establishment testitems
gained assertions for them plus a **cross-implementation gate**: a new testitem reproduces every row of
the committed eligibility fixture with the Julia `Establishment.eligible_pfts`, against the Python
derivation that built it (the ADR-0030 two-code-path check), and pins that the set is constant over the
historic years at this cell and moves under ssp370 — so rebuilding the fixture on the wrong temperature
basis fails the suite instead of silently deleting three PFTs. Full suite green: **274 546 pass / 0 fail**
over 129 test items (job 1759461).
