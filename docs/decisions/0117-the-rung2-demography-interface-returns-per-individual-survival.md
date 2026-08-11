# ADR 0117 — S's answer to the rung-2 demography interface: **per-individual survival probabilities**, and the four recruit axes are COMPLETE (verified, not assumed)

- **Status:** accepted (line S, 2026-08-11)
- **Rung:** `EXECUTION_PLAN.md` **rung 2** — the S→M integration point line M raised on 2026-08-10 (ADR 0061)
  and re-raised on 2026-08-11 (ADR 0120 §1: *"S has not yet replied"*). This is the reply. It decides only
  S's half — the shape of what the C's hook calls; M owns the harness.
- **Related:** 0120 + 0061 (M's observation and substitution halves — the question), 0049 + 0047 (the
  `trait_mortality` operator, which turns out to BE this interface), 0046 (the measurement that decides the
  choice), 0101 (one run is not a measurement — why the draw belongs on M's side), 0116 (why the roster loop
  is structurally better than the offline count recursion), 0106 (the acceptance criterion), 0031 (the
  complete seven-PFT tree set).
- **Artefacts:** `scripts/diagnose_recruit_trait_axis_coupling.py` → `recruit_trait_axis_coupling.csv`
  (109 rows), job **1754601** (`logs/S-axiscoup3.1754601.out`); the live parameter file
  `/home/jamirp/lpjml56fit/par/pft_lpjmlfit.js`.
- **Coverage of the verification in §4:** all **206 561 574** tree rows (`Type <= 6`) of
  `ind_hist_seed1_all.parquet`, all seven PFTs. Not a five-cell result.

---

## 1. Decision: option **(c)** — S returns a per-individual survival probability; M draws

Per (cell, patch, year), against the `pre` roster the C hands over, S returns:

* **one survival factor `f_i ∈ [0, 1]` per tree**, keyed by ADR 0120's `(pft_id, treeidx)` pair;
* **the recruit set** — one row per recruit: `pft_id` plus `SLA`, `Wooddens`, `D95max`, `minwscal`
  (unchanged from M's proposal; see §4).

M performs the Bernoulli draw and normalises to the `K` lines the hook already accepts. Three reasons, in
the order that decided it:

1. **A count-only interface cannot carry the trait response, even in principle.** ADR 0046 decomposed FIT's
   per-cell wood-density shift historic→ssp370 as **22.2 % composition / 51.3 % within-PFT / 26.6 %
   interaction**, and the within-PFT part is **+112 % within-age-class** — with traits immutable after
   `new_tree`, a trait-mean shift at fixed PFT and fixed age can *only* be differential survival. So **who
   dies is the mechanism of the trait response**, and the interface has to be per-individual or the trait
   half of ADR 0106 is unreachable through it. This is the argument that rules out returning a bare count.
2. **(b) is a control, not an endpoint.** Ranking on the C's own `mort_prob` borrows the C's hazard
   *ordering*, so any trait result it produces is the C's selection wearing the emulator's count — worth
   running as an upper bound, never as the answer. M's ADR 0120 adds an independent implementation
   objection (the current year's hazards are not computed at the rendezvous, so such a rule would rank on a
   one-year-stale hazard).
3. **(c) over (a), because it mirrors the C and puts the randomness where the ensemble is run.** FIT itself
   computes a per-individual probability and then draws: `mort = min(1, mort_npp + mort_age + mort_water +
   mort_temp)` followed by a per-individual `erand48` Bernoulli (`mortality_tree_ind.c:95-146`). Returning
   the probability reproduces that structure exactly. Returning a finished kill set (option (a)) would move
   the RNG into S, where M cannot re-draw it — and ADR 0101 requires a **seed ensemble** (~8 seeds,
   mean ± SEM) for any single-cell rollout claim. With the draw on M's side, a seed ensemble is a re-run of
   the harness, not a re-run of S.

## 2. This needs no new S science to start — `trait_mortality` already computes exactly this

ADR 0049's opt-in operator is, in its own terms, option (c): it produces a per-individual survival factor
**`f_i = (1 − mort_i)^θ`**, with θ bisected so that `Σ nind·f_i = ρ·Σ nind` — the learned count model pins
the *expectation* and the ported hazard sets the *ordering*, bounded in [0,1] and order-preserving. Two arms
therefore fall out of one wire format with no new model:

| arm | what S returns | what it measures |
|---|---|---|
| **C0 (null, ships today)** | `f_i = ρ` for every tree — the shipped composition-preserving uniform thinning | the trait response obtainable from **composition + recruit sampling alone**, zero within-PFT selection |
| **C1** | `f_i = (1 − mort_i)^θ` (`trait_mortality = true`) | the same plus **differential survival** |

**C1 − C0 is the measurement of how much of FIT's trait response is selection** — which ADR 0046 predicts
is most of it. That comparison is the pre-registered flip test `trait_mortality` has been waiting for, and
it is the reason this reply also unblocks line S's own arm C: the arm needs a roster, S has only a
single-cell Hainich rollout, and M's harness is the roster.

## 3. What M's harness gives S that no offline arm can — it retires ADR 0049's stated limitation

ADR 0049 item 4 records that **`mort_water` and `mort_temp` are zeroed on purpose** in the ported hazard,
because the emulator has neither of FIT's stress integrals (and `1 − wscal_mean` is a different quantity on
a different scale, ADR 0051). ADR 0061's `pre` record carries **`water_stress`, `temp_stress`,
`bm_inc_counter` and `bm_inc`** — exactly the accumulators those two hazards and `mort_npp` read. So inside
the rung-2 harness **all four hazards are computable faithfully, and the operator can run complete for the
first time.**

Stated honestly: those inputs are then the C's, not the emulator's. That is **not** the objection that
rules out (b) — (b) borrows the C's *decision*, this borrows the C's *state*, and borrowing the C's state is
precisely what rung 2 is ("S plus the real C fast part, closed annual loop"). Any rung-2 trait result must
still say which of the two it is.

**A free identity gate for the harness, offered to M:** with **θ forced to 1** and the hazards evaluated on
the C's own accumulators, S's operator must reproduce the C's own per-tree `mort` — ADR 0049 item 2 records
that **θ = 1 recovers FIT exactly**. It costs one arm with no new code and any mismatch is a port error in
`src/trait_mortality.jl`, caught before a single science number is quoted.

## 4. The four recruit axes are COMPLETE for this configuration — `k_root` is a constant, verified two ways

M asked (ADR 0120 §3 / the inbound update) whether any of the three axes left on the C's own draw —
`emax`, `k_root`, `beta_2` — matters for the four S predicts. Only `k_root` is emitted anywhere, and for it
the answer is decisive:

* **In the live parameter file it is a scalar.** All seven tree PFTs declare `"k_root": 0.02`, with the
  sampled-interval form `{"low":0.02,"median":0.04,"high":0.06}` **commented out at every one of the seven
  entries** (`par/pft_lpjmlfit.js:134, 264, 394, 524, 654, 784, 914`). It is not a sampled trait in this
  configuration.
* **The emitted column agrees, at full scale.** Over all **206 561 574** tree rows it carries **exactly one
  distinct value (0.02)**, with **0 rows differing** — and 0 for grass.

⇒ **Leaving `k_root` on "the C's own uniform draw" is an identity, not an approximation.** Nothing to add
to the wire format. `emax` and `beta_2` are emitted nowhere, so their coupling to the four is **not
measurable from `ind`** — the honest statement, and the cheap route if it ever matters is to add them to the
rung-2 `pre` dump rather than to reason about them.

**What the same audit does establish, and it matters for the recruit half:** the four substituted axes are
genuinely **mutually correlated within (PFT, age bin)** among survivors — `SLA~D95max` **−0.292**,
`SLA~minwscal` **+0.251**, `D95max~minwscal` −0.124, `Wooddens~minwscal` +0.102, `SLA~Wooddens` −0.036,
`Wooddens~D95max` −0.030. That joint structure is exactly what the copula exists to carry, so the recruit
rows must be consumed **as a set**; sampling the four marginals independently would discard a real
dependence. (Correlations are computed within stratum precisely because `Type` and age otherwise dominate
them — ADR 0049's age–trait gradient.)

⚠ **A degenerate correlation is the signature of a constant column, not of an uncoupled trait.** The first
run of this diagnostic reported `r = ±0.0000` for `k_root` against all four axes and a selection
differential of **−284 sd units** for PFT 3 — the second is arithmetically impossible and was a
near-zero-variance denominator. The variability audit now runs **first** and the selection panel prints
`const` instead of a ratio. Any future axis question must clear that audit before its correlations are read.

## 5. What this does not settle

* **The count channel may bound the selection, and that is the main scientific risk of the plan.** ADR 0049
  item 5 measured at Hainich a tilt median **θ = 8.5e-12**, with **θ > 0.5 in only 18 of 132 thinning
  years**, because the learned count model's demanded `|ρ − 1|` has median **0 %/yr** (a forest prediction
  is piecewise constant) against the hazard's 1.688 %/yr — so the operator often has nothing to
  redistribute. The rung-2 count target comes from the same model, so the same risk transfers. **Measure θ
  before interpreting any C1 − C0 difference**; a null result there may mean the count channel gave the
  selection no room, not that selection does not matter.
* **The count target is still the shipped count model's**, with the conditioning ADR 0116 characterised.
* **ADR 0116's drift does not transfer unchanged.** In rung 2 the roster comes back from the C every year,
  so the count feature is read off the *true* roster rather than self-fed — the one-sided loss drift is a
  property of the offline scalar recursion. Rung 2 is where that can be tested, and it should be, rather
  than assumed in either direction.
* Nothing here is measured on the harness yet. This ADR decides an interface; it reports no rung-2 result.
