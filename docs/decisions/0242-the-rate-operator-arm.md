# ADR 0242 — The RATE operator: FIT's own per-tree hazard with no count target at all

* **Status:** proposed (pre-registration; the campaign is running)
* **Date:** 2026-08-14
* **Line:** S (Component-S science)
* **Supersedes / amends:** nothing. Builds ADR 0241 §7's named replacement.
* **Answers:** line S STATE §B step 1 as rewritten by ADR 0241 — "re-specify the operator
  around a RATE, not a budget".

## 1. What is pre-registered here, and why this section exists

ADR 0241 retired the learned count model from the mortality path on an architectural
argument and named its replacement in the same breath: **FIT's own per-tree hazard applied
as a rate**. This ADR builds that operator and reads it. Everything in this section is
written **before any campaign number is looked at**, because the last four ADRs on this
question each turned on a pre-registered reading, and twice (ADR 0187 §5f, ADR 0241 §6) the
clause that saved the diagnosis was one written down in advance.

**The arms.** Three, in `scripts/rung2_s_demography_harness.jl`, mirroring the
`S0`/`S0h`/`S1` shape exactly so the decomposition is the same shape as every previous one:

| arm | survival fraction handed to the draw | what it isolates |
|---|---|---|
| `H0` | `1 − h̄`, `h̄ = Σ nind·mort / Σ nind` | the RATE alone, no per-stem information |
| `H0h` | `0` for a certain stem (`mort ≥ 1`), else `1 − h̄_disc` over the rest | + honouring the deaths FIT had already settled |
| `H1` | `1 − mort_i`, stem by stem | + per-stem ordering ⇒ FIT's own Bernoulli |

No target, no budget, no account, and **no `ρ < 1` gate** — that gate belongs to the
count-budget architecture, and it is what left 42–46 % of `S*` patch-years with an empty
kill list, sparing the certain deaths too (ADR 0188 §3).

**The criterion is ADR 0240's PAIR, unmoved.** On ADR 0185 §5's basis (patch-mean at the
single terminal year, seeds averaged, median over cells, behind that scorer's coverage
gate), at the FIT-gain cells on the ssp370 leg: **both |dN| and |dAGB| under 40 %**, with
per-stem mass printed beside them. ADR 0188 §7's three clauses (discretionary kill rate
≥ 1.5 %/yr, annual mass removal ≥ 0.025, agb departure < +40 %) are also reported, unmoved.

**What the answer will and will not be.** In rung 2 the hazard reads FIT's own stress
integrals through the rendezvous, so **these arms measure a CEILING**: what an exact hazard
buys, given inputs the standalone emulator does not have offline (ADR 0049 item 4). A pass
here does not close the standalone emulator, and any number quoted from this ADR must say
which of the two it is on.

**Derived in advance, so that a surprise is legible as one.**

1. **`H1` should deliver FIT's own gross mortality flux on the stand it is standing on** —
   that is ADR 0189's `perfect` arm identity (`|diff| 0.0000`) and ADR 0183's port
   (`|Δhazard|` 5e-18) restated inside the closed loop. If the delivered-flux column is not
   1.00 the gate has failed, not the physics.
2. **The three arms are NOT expected to agree.** They have identical expected removal *on a
   given roster* and their stands diverge, so their leg totals must differ; measured in the
   Hainich smoke, `H0`'s leg `haz_exp` is 1.9× `H1`'s, because `H0` spares certain-death
   stems that then linger at `mort ≈ 1` and inflate `h̄` every year after. **A leg-summed
   flux difference between these arms is a RESULT, never an operator difference.**
3. **The rate clause should clear easily and the pair is the real test.** ADR 0187 measured
   FIT's own discretionary rate at 2.05 %/yr against `S1`'s 0.6; an exact hazard reproduces
   FIT's, so clause (a) is not informative here. ADR 0241 §6 measured the surviving defect
   as a big-tree TAIL, and nothing in a mortality-rate fix is guaranteed to remove a tail
   the C's own growth builds — so **|dAGB| is the clause at risk, and `dN` is the one this
   operator has the most direct claim on.** That is stated now, not after the fact.

## 2. Guardrail 4 — measured, not asserted

The pre-existing arms must decide identically under the new code. `S1`, historic,
cell 42490, `predict`, seed 1, re-run under the new harness:

* **arm log: the 27 pre-existing columns are byte-identical over 500 patch-years** (a
  `cut`-then-`cmp`; the five appended columns are new and carry the additions).
* **dump: identical in every initialised column, 40 569 tree records**
  (`scripts/diagnose_rung2_dump_equality.py`; a file-level `cmp` calls 28 322 lines
  different for those same decisions, because `sapwood_old` is a dead struct field —
  ADR 0240, skill trap 5m).

## 3. The derivable a-priori gate, and the five new log columns

`scripts/diagnose_rung2_rate_flux_identity.py` — arm logs only, seconds, no dump scan.
Three panels are the gate and one is information:

* **(A) the expected-flux identity.** On one roster all three arms remove `Σ nind·mort` in
  expectation, so the new `kill_exp` column must equal the new `haz_exp` column row by row.
  Smoke: **max |diff| 2.4e-17 over 3 525 patch-years, 0 rows above 1e-12.**
* **(B) the realization, with an EXACT sampling SE.** The harness now accumulates both the
  mean `Σ nind·(1−f)` and the variance `Σ nind²·f(1−f)` from the `f` it actually used, so
  `z = (realized − implied)/sd` is exact **for every arm**, `S*` and `G*` included. ADR
  0188's `1.004 ± 0.009` had to hand-roll an SE from a uniform-draw assumption that only
  `S0` meets; ADR 0187 §5f is the standing instruction to derive the SE before choosing a
  tolerance. Smoke: |z| ≤ 0.33 on five legs.
* **(C) the gate incidence.** A rate arm decides on every non-empty patch-year, and
  `rho_eff` is **NaN** rather than 1.0 to say that no thinning ratio was formed — a missing
  measurement must not print as a measured value (ADR 0240). Smoke: 0 no-draw rows,
  NaN on every row; the `S1` control shows 140 of 500 gated rows.
* **(D) delivered flux, NOT a gate.** `Σ kill_nind / Σ haz_exp` — the arm's realized
  removal against FIT's own expected mortality **on the arm's own roster**. 1.00 by
  construction for a rate arm; for `S*`/`G*` it is ADR 0187's rate shortfall available from
  the log for the first time. Smoke: `S1` **0.6803** at Hainich historic, i.e. it delivers
  68 % of the mortality its own stand was asking for — reproducing ADR 0187's shortfall by
  a fourth independent route. ⚠ Not a ranking: every row is a different, diverged stand.

New columns, appended (readers take positions off the `#H L` header, so an additive column
cannot move an existing one): `haz_exp` `kill_nind` `kill_exp` `kill_var`, on top of
ADR 0240's four. All are written for **every** arm, because they are properties of the
roster and the draw, not of the operator.

## 4. The campaign

12 cells × 2 legs × 3 arms × 5 seeds = **360 legs**, `predict` mode, same cell set and same
per-cell `REC` baselines as ADR 0240's campaign. Wall time is 17 s (historic) / 40 s
(ssp370) per leg — the whole campaign is cheaper than one of the offline scorers.

## 5. Results

*To be filled in when the campaign completes. Nothing above this line changes.*

## 6. Decision

*Pending §5.*
