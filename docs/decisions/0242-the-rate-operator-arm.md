# ADR 0242 — The RATE operator: FIT's own per-tree hazard with no count target at all

* **Status:** accepted
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
  tolerance. Smoke: |z| ≤ 0.33 on five legs. ⚠ **This bullet is part of the pre-registration
  and its central claim is WRONG at campaign scale — `z` is exact per patch-year but its
  POOLED form is not a standard normal, because the denominator is correlated with its own
  numerator through the trajectory. §7 has the diagnosis, the frozen-roster experiment that
  settles it, and the clause that carries the gate instead. Do not quote `z` from here.**
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

**Coverage first (skill trap 2).** 360 legs submitted, **351 OK, 0 SHORT, 9 DEAD**. All nine are
the **known, open C-side `ERROR043: duplicate roster key`** fault (§D of line S's state file), at
cells 42973 (5 legs), 52059 (3) and 32628 (1), all ssp370 — not the empty-patch deadlock ADR 0240
fixed, and not a new fault. The selectivity scan excludes 6 of them by its own gate and names them.
Its audit cross-check passes on **210 of 210** audit-bearing legs.

**The derivable gate passes** (`diagnose_rung2_rate_flux_identity.py`, 441 346 patch-years):
panel A **max |kill_exp − haz_exp| 1.5e-16, 0 rows above 1e-12**; panel B1 max |ratio − 1| **0.0058**
against a 2 % tolerance; panel C **0 no-draw rows and `rho_eff` NaN on every row**. §7 records what
happened to panel B's pre-registered |z| clause and why it is not the gate.

### 5.1 THE CRITERION — `H1` PASSES BOTH CLAUSES OF THE PAIR, BY ROUGHLY 9×

ssp370 leg, FIT-gain cells, median over cells with seeds averaged, on ADR 0185 §5's imported basis:

| | clause | FIT | `S1` (status quo) | `G1` (ADR 0240) | `H0` | `H0h` | **`H1`** |
|---|---|---|---|---|---|---|---|
| discretionary kill rate %/yr | **≥ 1.5** | 2.1 | 0.6 | 26.2 | 24.8 | 2.5 | **2.2** |
| annual mass removal | **≥ 0.025** | 0.03063 | 0.01781 | 0.03203 | 0.34785 | 0.03579 | **0.03406** |
| **agb departure `dAGB`** | **\|·\| < 40 %** | — | +90.6 % | +2.9 % | −99.6 % | −13.3 % | **+4.1 %** |
| **count departure `dN`** | **\|·\| < 40 %** | — | −2.9 % | −72.1 % | −98.5 % | +0.3 % | **+4.4 %** |
| per-stem mass departure | printed beside | — | +96 % | +269 % | −73 % | −13.6 % | **−0.3 %** |
| roster horizon, own stand | not → 0.1× | ~1 | 0.944× | 0.612× | 0.971× | 1.008× | **1.000×** |
| nomination rate %/yr | FIT gross **5.961** | 5.961 | 4.28 | 27.6 | 23.2 | 6.50 | **5.961** |
| `R̂` on its own stand %/yr | FIT **6.456** | 6.456 | not logged | 27.6 | 23.0 | 6.97 | **6.43** |
| mass selectivity Λ (stratified) | FIT **0.90** | 0.90 | 0.926 | — | 1.00 | 1.01 | **0.94** |
| `hmean` / `age_mean` departure | — | — | +12.5 / +57.2 % | −41.4 / −21.6 % | −91.8 / −97.2 % | −3.2 / −9.4 % | **+1.5 / +4.2 %** |

`H1` also holds on the **FIT-thin** cells (7): `dN` **−0.2 %**, `dAGB` **−5.3 %** (`S1`: −1.7 % /
+55.9 %), and on the historic leg's FIT-gain cells: **+1.5 % / +8.9 %**.

**The per-stem mass excess that five ADRs chased is gone.** It was +90.6 % agb on −2.9 % stems for
`S1` (ADR 0186) and +269 % for `G1` (ADR 0240); under a rate operator it is **−0.3 %**. And the
size-conditional rate profile — the statistic ADR 0187 used to show `S1` had *FIT's shape at 2.9–4.6×
lower level* — now has FIT's shape **at FIT's level**, quintile by quintile of FIT's own stand:

| P(die \| height quintile of FIT's stand), ssp370 | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---|---|---|---|---|
| FIT (`REC`) | 0.0231 | 0.0221 | 0.0175 | 0.0188 | 0.0198 |
| **`H1`** | **0.0250** | **0.0232** | **0.0173** | **0.0177** | **0.0218** |
| `H0h` | 0.0245 | 0.0221 | 0.0215 | 0.0236 | 0.0232 |
| `H0` | 0.3109 | 0.2191 | 0.1781 | 0.1558 | 0.1326 |

and the standardized selection differentials reproduce FIT's own weak size selection (height: FIT
−0.066, `H1` −0.078, `H0h` −0.020, `H0` −0.120).

### 5.2 THE WARMING RESPONSE — the deliverable, and the null derived before it was read

Per-cell count response (terminal ssp370 minus terminal historic), 12 cells, against FIT's own:

| arm | slope vs FIT | r | RMSE (stems) | \|mean bias\| | sign, FIT-gain |
|---|---|---|---|---|---|
| `NP` (do-nothing null) | 2.320 | 0.917 | 5.448 | 3.490 | 1/5 |
| `S1` (status quo) | 1.797 | 0.775 | 4.997 | 2.700 | 2/5 |
| `H0h` | 1.303 | 0.807 | 2.670 | 0.878 | **4/5** |
| **`H1`** | **1.150** | **0.946** | **1.116** | **0.330** | **3/5** |

⚠ **`r` DOES NOT DISCRIMINATE AND MUST NOT BE QUOTED AS SKILL — the do-nothing null scores 0.917.**
That is skill trap 5 exactly (in a rung-2 arm the C grows the stand, so a stand-derived statistic is
inherited by every arm), and the null's value was computed before the arms' were read. What
discriminates is the **slope** (1.15 against the null's 2.32) and the **error magnitude**: `H1`'s
RMSE is **4.9× smaller than the null's and 4.5× smaller than the status quo's**, and its mean bias
falls from 3.49 stems to 0.33.

**Where the sign misses are.** All four of `H1`'s misses over the 12 cells sit at
**|FIT response| < 0.9 stems**; at the four cells where FIT's own response exceeds 1 stem `H1` gets
sign and magnitude (FIT −5.24/`H1` −6.06 · +5.24/+6.07 · −3.56/−3.31 · −3.00/−5.36). Whether those
small-response cells are inside FIT's own two-run spread is **UNMEASURED** — this campaign has one
`REC` member per cell, so the honest statement is that the misses are small in magnitude, not that
they are inside the reference's noise.

### 5.3 THE DECOMPOSITION — and it inverts what the rate alone is worth

`H0` → `H0h` → `H1` on ssp370 `dAGB`: **−99.6 % → −13.3 % → +4.1 %**.

**`H0` annihilates the stand**: it spends FIT's own expected flux and spends it on the wrong stems,
so the >5 m population falls **−98.5 %** in count and **−99.6 %** in biomass, at a discretionary
kill rate of 24.8 %/yr against FIT's 2.1. Its whole-roster horizon is nevertheless **0.971×** — it
does not empty the patch, it converts the stand to saplings, which is why a roster-count check alone
would have called it healthy. ⚠ **Its nomination rate, 23.2 %/yr against FIT's 5.96, is ENDOGENOUS
in exactly ADR 0240's sense**: the expected flux is right on each roster (panel A, to 1.5e-16), but
sparing the certain deaths leaves stems that linger at `mort ≈ 1` and lift the mean hazard every year
after. Same shape as `G1`'s recruit feedback, a different input.

⇒ **at FIT's full gross flux, WHICH trees die is decisive, and that refines rather than contradicts
ADR 0187.** ADR 0187 measured the `S*` arms as picking the right kinds of trees and found the
shortfall to be the rate; that was measured at a discretionary rate of 0.5–0.6 %/yr, where
mis-ordering has little to work with. At 2.1 %/yr the same mis-ordering is the difference between
+4.1 % and −99.6 % biomass. **The two findings are a scale-dependence, not a disagreement, and
neither is quotable without the other.**

Honouring the certain deaths (`H0h`) recovers almost all of it and leaves a systematic **−13.3 %**
biomass and a flat rate profile; per-stem ordering among the rest (`H1`) closes that residual.

### 5.4 WHAT THIS IS AND IS NOT — the ceiling caveat, restated because it is easy to over-read

`H1` reads FIT's own stress integrals through the rendezvous, so it is close to *replaying FIT's own
mortality inside FIT's own physics*. Its agreement is therefore **expected**, and it is a CEILING,
not a fidelity result for the standalone emulator (pre-registered in §1; ADR 0049 item 4). What it
does establish, none of which was known before:

1. **The count-budget architecture was the whole of the mortality defect.** Nothing else in the loop
   — the C's growth, its establishment, the rendezvous, the >5 m emission cut, the free-running
   81-year recursion — prevents a mortality operator from holding FIT's stand to within ~5 % on both
   count and biomass. ADR 0186's `S1` climbed monotonically to +91 % for 81 years; `H1` does not
   drift at all (roster 1.000×).
2. **ADR 0241's replacement claim is now measured in the closed loop, not only offline.** Its
   evidence was ADR 0189's offline `perfect` arm and ADR 0183's `|Δhazard|` 5e-18; the nomination
   rate landing on **5.961 %/yr against FIT's own 5.961** and `R̂` on **6.43 against 6.456** is the
   live version.
3. **The remaining gap in the deliverable is the HAZARD'S INPUTS, not the operator.** That is where
   ADR 0049 item 4 has always pointed, and it is now the only thing between this ceiling and the
   standalone emulator.
4. **ADR 0241 §6's big-tree tail is not a separate defect.** It was a property of stands built by a
   starved mortality operator; at FIT's rate the tail does not form (`hmean` +1.5 %, `age_mean`
   +4.2 %, and four of five height quintiles already matched). No allometry or growth work is
   implied — item 25 stands and is now also unnecessary.

## 6. Decision

**Adopt the rate operator as the mortality path.** `H1` — every stem faces FIT's own per-tree hazard,
no target, no budget, no account, no gate — meets ADR 0240's pair (**+4.4 % / +4.1 %** against 40 %)
and all three of ADR 0188 §7's clauses, holds the stand stationary over 81 years, reproduces FIT's
gross mortality rate to the printed digit and its size-conditional rate profile quintile by
quintile, and cuts the warming response's error 4.5× below the status quo and 4.9× below the
do-nothing null. **Keep `H0h` as the shipped decomposition control and `H0` as the demonstration
that the rate alone is not the answer.**

**What is NOT decided here.**

1. **This does not close the deliverable**, and the ADR must not be cited as if it did. It is a
   ceiling on FIT's own stress integrals (§5.4). The acceptance criterion is unchanged.
2. **No `src/**` change and no flag flip.** The operator lives in the rung-2 harness; wiring an
   equivalent into `src/components/slow.jl` is a separate, later step with its own guardrail-4
   obligation, and it needs §5.4 item 3 answered first — a rate operator in the coupled path has to
   get its stress integrals from somewhere.
3. **`S2` is still not specified.** ADR 0241 §7 said re-specify it around a rate operator; that is
   now possible, and the establishment half is untouched by anything here (`ESTAB_C` in every arm,
   `n_recruit ≡ 0` by construction, structural replay floor 0.907 per ADR 0121).
4. **The count model is not further indicted.** ADR 0241 retired it from the mortality path; its
   other consumers are untouched, and `H1`'s log still carries its `target` for exactly that reason.

## 7. What happened to panel B's pre-registered clause, and the method notes

⚠ **A SELF-NORMALIZED MARTINGALE POOLED OVER A FEEDBACK TRAJECTORY IS NOT A STANDARD NORMAL — ITS
MEAN IS POSITIVE.** Panel B's pre-registered clause was |z| < 4 on
`z = (Σ kill_nind − Σ kill_exp)/sqrt(Σ kill_var)`. It came out at **4.47** for `H1` on ssp370, with
the realized total 0.58 % above the implied one and the per-leg z at mean **+0.50**, sd **0.992**. A
unit sd said the variance formula was right, so the mean shift had to be explained. Two hypotheses
were written down — the draw is biased, or the statistic is — and the second was diagnosed from the
shape first: the effect **grows down the leg** (z +1.02 in the first decade of an ssp370 leg, +3.95
in the seventh), the signature of feedback. The numerator is a martingale
(`E[kill_nind | history] = kill_exp` row by row, exactly), but the DENOMINATOR is random and
negatively correlated with it: a leg that kills more than implied carries a smaller stand afterwards,
hence smaller later `kill_var`, hence a smaller denominator — positive residuals amplified, negative
ones damped.

**The experiment that settles it freezes the feedback** (`scripts/diagnose_rung2_rate_draw_replay.jl`):
take one leg's rosters exactly as the C published them and re-run only the draw.

* Replaying with the harness's own per-patch-year seed reproduces the logged `n_kill` at **2025 of
  2025 patch-years, 0 differing**, and `kill_exp` to **6.9e-18**. That single check identifies the
  dump's `grow` roster with the roster the harness was served AND re-proves the ported hazard against
  FIT's own `mort_prob` at the level of realized kills — the replay draws on the dump's column and
  lands on the count the harness produced from `TraitMortality.mortality_hazard`.
* **400 Monte-Carlo redraws of those same fixed rosters land at −0.0585 % of the implied total,
  z = −0.83.** The draw is unbiased. `H-draw` refuted.

**The clause was not moved** (ADR 0187's rule): it is still computed, still printed, and still
reported as FAILING, with the diagnosis beside it. The gate is carried by **B1, the pooled ratio**
(|ratio − 1| < 2 %), which no normalizer distorts. ⚠ **And a second addition failed for the same
reason as the first, which is worth recording**: a first attempt gated on `sd(z_leg)` being within
0.25 of 1, reasoning that a mean shift leaves the variance alone. Measured, it runs **0.74–1.27**
across arms, lowest for the arm whose stand collapses — under feedback the self-normalized
statistic's *second* moment is not derivable either. That clause is reported, not gated. Both
additions are disclosed as post-hoc rather than presented as the original design.

Other method notes paid for here:

* ⚠ **DERIVE THE NULL'S VALUE FOR EVERY STATISTIC YOU QUOTE, NOT JUST THE BLESSED ONE.** The
  response correlation `r` looks like strong skill at 0.946 — and the do-nothing null scores
  **0.917**. It was only safe to publish the slope and the RMSE because the null was computed in the
  same pass (residual-diagnosis; ADR 0184's rule, third time decisive).
* ⚠ **A WHOLE-ROSTER COUNT CANNOT SEE THE `H0` COLLAPSE.** Its roster horizon is 0.971× while the
  >5 m population it is judged on falls 98.5 % — the stand converts to saplings. **State which
  population a horizon column is on**, every time.
* ⚠ **A LOG READER THAT DROPS THE ROW TAG FROM ONE SIDE AND NOT THE OTHER RETURNS SILENTLY EMPTY.**
  The `#H` line is `#H L year patch …`, so the header keeps the `L`; splitting the data row as
  `[2:end]` made every row fail the width check and the reader reported *"the log has 0 rows"* —
  indistinguishable from a leg that never ran. Same family as the dump's header-to-field offset, one
  level up.
* ⚠ **A NEW ARM MUST BE ADDED TO EACH SCORER'S OWN SEED MAP, AND A MISS IS A `KeyError` ONLY IF YOU
  ARE LUCKY.** `diagnose_rung2_kill_selectivity.py` carries a per-arm `SEEDS` dict pinned to three
  seeds for comparability; an unlisted arm raised `KeyError` after the header had already printed.
  Its pre-registered panel-6 verdict deliberately does NOT follow `ARMS` (skill trap 5n), so it
  correctly returned `nan`/NO VERDICT for arms that did not exist when its thresholds were written —
  **that is the design working, not a defect to fix**, and the rate arms are judged by ADR 0240's
  criterion in §5.1 instead.
