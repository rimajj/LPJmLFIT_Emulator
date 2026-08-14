# 0241 — A next-year per-patch COUNT target can never be precise enough to drive a GROSS mortality budget: the budget is a difference of counts, so the count model's error is amplified by the level-to-flux ratio (measured 2.1–2.6×, i.e. 209–259 % relative budget error), and the ±1.2 %-per-patch-year precision a ±20 % budget would need sits 2.7–3.9× inside the irreducible demographic realisation floor, 35× inside the cell-year conditioning floor, and 4.1–4.9× inside the integer atom of a stem count. This is an ARCHITECTURAL result, not a tuning one — retire the learned count model from the mortality path and apply FIT's own per-tree hazard as a RATE

* **Status:** accepted
* **Date:** 2026-08-14
* **Line:** S · ADR block 0240–0259 (tier 4)
* **Answers:** the integrator's question after ADR 0240 — *"can a next-year per-patch count target ever
  be precise enough to drive a gross mortality budget?"* — posed as a hypothesis to be REFUTED, with
  the reading pre-registered in the scorer's header before it ran (§1).
* **Builds on:** ADR 0188 (the budget is the NET count change, argued from the identity), ADR 0189
  (the lag is not the obstacle; per-year rectification is convex), ADR 0240 (the arm was built and
  its recruit term is endogenous). This ADR supplies the **quantitative** version of ADR 0188's
  operative sentence, which until now was an identity argument with no precision attached to it.
* **Does NOT disturb:** ADR 0186 (the defect is per-stem mass), ADR 0187 (the kill set is not
  size-biased), ADR 0183 (the ported hazard is exact). §6 below is the second half of this session's
  work and *strengthens* ADR 0186.
* **Evidence:** `scripts/diagnose_rung2_count_precision_budget.py`, SLURM job **1793142**
  (`logs/S-countprec2.1793142.out`; job 1792783 is the same scorer before §5's quantisation panel
  was appended). **No model run** — 24 `REC` `predict` dumps (12 cells × 2 legs) joined to
  `map_on_rec_stand_predict.csv`, behind ADR 0185 §5's imported completion + coverage gate.

## 1. What was pre-registered, and where

The scorer's header carries, **before the run**: the hypothesis in the integrator's own words; the
algebra of §2 in full; the reference basis; the three refutation panels; and the verdict branches

* `A ≤ 1` → the required precision is INSIDE the realisation floor ⇒ a budget-driven operator is
  FEASIBLE and `S2` stays the plan;
* `A > 3` → OUTSIDE by more than 3× ⇒ **architectural**, retire the count model from the mortality
  path;
* `1 < A ≤ 3` → in between, say so and name the tie-breaker;

with `A ≡ FLOOR-2 / e_req`. It was not re-read after the numbers appeared (ADR 0104's error).

**Two additions are disclosed rather than hidden, both made after a read.** §4's mode-exact
companion (`P2b`) was written after the two-cell smoke test of the level-basis panel, for an
algebraic reason — the pre-registered algebra assumes `n_prev ≈ M`, which is true in `roster` mode
and false in the `predict` mode these runs used. §5's quantisation floor was derived after the
12-cell run. Neither changes the pre-registered verdict expression; both are reported beside it, and
§5 is *stronger* than what was pre-registered rather than weaker.

## 2. The algebra, in full

One patch, one year. `N` = roster stem count at the rendezvous (`n_tree`); `M` = its EMITTED (> 5 m)
count — the population the count model is trained and scored on, because its training target
`n_living` (`build_slow_runtime_table.py:545`) is the `ind`-table count and the `ind` writer cuts at
`param.height_min` = 5 m. `T` = the model's target, `M*` = FIT's own realized `n_living`, so the
count-target error is `ε = T − M*` in emitted stems.

The harness forms `ρ = T / n_prev` on the emitted basis (`:574`) and applies it to the roster
(`:521-527`), so ADR 0189 §7's gross budget and its sensitivity to the target are

```
B      = (1 − T/n_prev)·N + R̂                        ∂B/∂T = −N/n_prev
δB     = −ε·(N/M)                                     [roster stems]
```

The truth the budget is trying to be is FIT's own gross kills `K` (roster stems), so

```
|δB| / K  =  (|ε|/M) · (N/K)  =  (|ε|/M) / (K/N)  ≡  e / k

   e ≡ |ε|/M    the count-target error as a fraction of the LEVEL   (emitted basis)
   k ≡ K/N      FIT's gross kill rate as a fraction of the LEVEL    (roster basis)
```

⚠ **The `N/M` cancels exactly.** The emitted-vs-roster population ratio (2.08–2.92, ADR 0188 §6)
does not enter the amplification — which is why this is not a second copy of the hypothesis ADR 0188
already refuted.

Requiring the budget within a relative tolerance `τ`:

```
e_req = τ · k                                         τ = 0.20, pre-registered
```

## 3. The four measured numbers

Basis: FIT's OWN stand, `predict` mode, 12 cells, the emitted population, per patch-year, median
over cells. **The reproduction gate passes exactly first** — FIT's own gross kills and recruitment
through this scorer's own scan land on ADR 0188 §4 at `K_all` 5.651 / 5.891 %/yr (anchors
5.651 / 5.961) and `R` 4.619 / 6.456 %/yr (anchors 4.619 / 6.456), i.e. three of four to the printed
digit.

| | historic | ssp370 |
|---|---|---|
| **(1a) count-target error, fraction of the LEVEL** | **0.1179** (11.8 %) | **0.1525** (15.2 %) |
| **(1b) the same, fraction of the GROSS FLUX** `e/k` | **2.09×** (209 %) | **2.59×** (259 %) |
| FIT's gross flux `k` | 5.651 %/yr | 5.891 %/yr |
| **(2) FLOOR-2, irreducible realisation (lower bound)** | **0.0414** | **0.0458** |
| FLOOR-1, cell-and-year conditioning | 0.3926 | 0.4159 |
| **(3) required precision** `e_req = 0.20·k` | **0.01130** (1.13 %) | **0.01178** (1.18 %) |
| **(4) ratio (3)/(2)** | **0.273** | **0.257** |
| ⇒ `A` = (2)/(3), the amplification over the floor | **3.66×** | **3.89×** |
| ⇒ `A₁` against FLOOR-1 | 34.7× | 35.3× |

**What each floor is conditioned on, stated explicitly because the two are floors for different
model classes.**

* **FLOOR-1** is the between-patch CV of `n_living` **within (cell, year, scenario, seed)** — i.e.
  conditioned on the cell, the year, the scenario and the seed, and on **nothing about the patch**.
  It is the floor for a predictor with cell-and-year information only. The shipped model also reads
  per-patch stand features (`hmean`/`hmax`/`agb`/`lai`/`fpc`/`age_mean`/`n_prev`) and does beat it,
  so it is context, **not** the verdict's bar. Its value, ~0.40, is the number the integrator's
  hypothesis quoted.
* **FLOOR-2** is conditioned on the **full per-stem state** and is a strict LOWER BOUND on the
  irreducible error of **any** learner. Survival is an independent Bernoulli draw per stem at FIT's
  own hazard (`erand48`, `mortality_tree_ind.c:120-146`), and the dump's `mort_prob` **is** that
  probability (the port reproduces it to 5e-18, ADR 0183), so
  `sd(M* | state) ≥ sqrt(Σᵢ pᵢ(1−pᵢ))` exactly, per patch-year. It is a lower bound because
  ingrowth across the 5 m cut and establishment add variance it cannot see. Certain kills
  (`mort_prob ≥ 1`) contribute 0, correctly — they carry no randomness.

**The pre-registered verdict fires on both legs: `A` = 3.66× and 3.89×, i.e. OUTSIDE by more than
3×.**

## 4. Three attempts to refute the hypothesis, and what each returned

The scorer was written to break H, not to confirm it. All three attempts fail, and the *way* they
fail is the mechanism.

**R1 — is `e` really ~24 %?** No: measured honestly on FIT's own stand it is **11.8 / 15.2 %**, not
24. The integrator's figure was ADR 0185's *separability* statistic `|target/n_emit − 1|`, which is
measured on an ARM's own diverged stand and conflates the model's error with the trajectory
divergence and with the mortality the target is meant to express. So H's premise number is ~1.6×
too pessimistic — **and the conclusion survives it**: the amplification is 2.1–2.6× rather than 4×,
against a tolerance of 0.20, so the budget error is 209–259 % instead of 400 %.

**R2 — do the errors cancel in a running ACCOUNT?** This is the strongest available refutation,
because the shipped `G*` arms *do* spend from a per-patch running account (ADR 0240 §1), and a
zero-mean, uncorrelated error would fall as `1/√n_yr` — a factor of 4.5 over the historic leg and
9.0 over ssp370. Measured as `e_acct = |Σ_y ε_y| / Σ_y K_y` per patch over the whole leg:

| leg | `e_acct` | per-year `e/k` | realised gain | gain if i.i.d. |
|---|---|---|---|---|
| historic | **1.734** | 1.280 | **0.74** | 4.5 |
| ssp370 | **1.494** | 1.578 | **1.06** | 9.0 |

**The account absorbs essentially nothing** (gain 0.74–1.06 against 4.5–9.0), and it lands 7–9×
outside `τ = 0.20`.

**R3 — why not?** Because the error is not noise. Its systematic part alone is `bias/k` = **+1.568 /
+2.476** — the *bias* is already 157–248 % of the gross flux — and within a patch it is strongly
autocorrelated, lag-1 `ac1` = **+0.624 / +0.852**. An account absorbs zero-mean noise and cannot
absorb either. The sign is informative and independently corroborating: the target is systematically
**too high**, so the budget is systematically **too small**, which is ADR 0187/0188's measured
under-kill (0.5–0.6 %/yr against FIT's 2.05) arriving from a completely different direction.

**The mode-exact companion, and the one place the picture is less extreme.** §2's algebra assumes
`n_prev ≈ M`; in `predict` mode `n_prev = T(y−1)`, so `ρ = T(y)/T(y−1)` is a ratio of two model
outputs and a common LEVEL bias partly cancels in it. The companion statistic makes no such
assumption: with `ρ_true ≡ 1 − (K−R)/N` (and `R̂ = R`, so the recruit term contributes nothing and
the count model's error is isolated), `|B − K|/K = |Δρ|/k` — the same form and the **same** required
precision, because `e` and `Δρ` are both dimensionless fractions of a level.

| leg | `\|Δρ\|` | `\|Δρ\|/k` | account | FLOOR-2r | `A_ρ` |
|---|---|---|---|---|---|
| historic | 0.0539 | 0.90× | 0.30 | 0.0304 | **2.69×** |
| ssp370 | 0.0604 | 0.87× | 0.12 | 0.0321 | **2.72×** |

**Reported rather than buried: the two instruments straddle the pre-registered 3× line** — the
level basis gives 3.66/3.89× (ARCHITECTURAL), the ratio basis 2.69/2.72× (IN BETWEEN) — and the
ratio basis's leg-account error on ssp370, 0.12, is **inside** `τ = 0.20`. §7 names the tie-breaker
and §5 settles it on a third instrument that neither of them can escape.

## 5. ⚠ THE FLOOR THAT NEEDS NO STATISTICS: a stem count is an INTEGER

The smallest change either a count target or a kill budget can express is **one stem**, and FIT's
gross mortality is of order **one stem per patch-year**. Pure arithmetic off the measured levels
(scorer panel P5, added after the run and disclosed as such):

| leg | emitted level `M` | FIT's `K` per patch-year | `1/M` vs `e_req` | `1/K` vs `τ` |
|---|---|---|---|---|
| historic | 10.52 stems | **1.221 stems** | 0.0951 vs 0.0113 ⇒ **8.41×** | 0.819 vs 0.20 ⇒ **4.09×** |
| ssp370 | 8.13 stems | **1.026 stems** | 0.1230 vs 0.0118 ⇒ **10.44×** | 0.975 vs 0.20 ⇒ **4.88×** |

A ±20 % budget on a flux of about one stem means being right to about **±0.2 of a stem** in a
quantity whose atom is 1. **No learner, no architecture and no amount of training data changes
this**, because the quantity being predicted cannot take a fractional value — and it binds the
level basis and the ratio basis identically, so it is the instrument neither §4 arm can escape.

## 6. THE SECOND HALF OF THE SESSION: the matched-age / matched-height decomposition of the per-stem mass excess (line S STATE §B step 1)

Pre-registered thresholds, unmoved: `share = dPER_matched / dPER` **< 0.25** ⇒ a structure
consequence; **> 0.60** ⇒ the trees really are heavier at the same age and it is a disclosure, not a
defect. Scorer `scripts/diagnose_rung2_perstem_mass_decomp.py`, job **1793003**
(`logs/S-permass.1793003.out`); `grow`-phase terminal-year (2100) roster, `height > 5 m`, per-stem
mass `w = leaf_c + sapwood_c + heartwood_c − debt_c`, bins are FIT's own terminal-stand quintiles at
each cell, FIT-gain cells, ssp370, seeds pooled.

**The basis gate is honest about a partial miss.** `S1`'s dump-derived `dPER` is **+99.0 %** against
ADR 0240 §3's published **+96 %** (|d| = 0.03) — which validates the per-stem mass definition, since
`w` omits the C's `excess` and `turn_litt.leaf`, neither of which the hook emits. `G1` comes out
**+160.5 %** against the published **+269 %** and **FAILS** the ±0.60 gate. The reason is known and
is an aggregation-plus-coverage difference, not a defect in `w`: the published figure is
`(1+dAGB)/(1+dN) − 1` formed from **two medians** (1.029/0.279), while this scan takes a **median of
per-cell ratios**, and `G1` **has no emitted stems at all at 2 of 12 cells at 2100** (`c18371`,
`c22990` — and `c22990` is a FIT-gain cell), so its gain set is 4 cells, not 5. The *shares* below
are intra-cell quantities and are unaffected by that choice; the absolute `dPER` column is on the
dump basis and must not be quoted against ADR 0240's.

**⚠ And that coverage note is itself a finding: `G1` annihilates the > 5 m population at two cells.**
ADR 0240 §8 item 19 recorded this for the uniform arm `G0` (−100 % count and agb). It is now
measured for the trait arm `G1` as well, at 2 of 12 cells including one that carries FIT's gain.

**The scalar shares land IN BETWEEN on three of four, and that is why the profile was demanded.**

| arm | matched-AGE share | matched-HEIGHT share | bin coverage |
|---|---|---|---|
| `S1` | **0.423** (in between) | **0.666** (> 0.60) | 100 % |
| `G1` | **0.287** (in between) | **0.379** (in between) | 100 % |

**The height-quintile profile resolves it, and it is unambiguous.** `ratio` = the arm's mean
per-stem mass in that quintile of FIT's own stand, over FIT's:

| quintile of FIT's own stand | REC share | `S1` share | `S1` ratio | `G1` share | `G1` ratio |
|---|---|---|---|---|---|
| 1 (shortest) | 0.202 | 0.184 | **1.02** | 0.156 | **0.97** |
| 2 | 0.198 | 0.192 | **0.92** | 0.161 | **1.05** |
| 3 | 0.202 | 0.185 | **1.05** | 0.152 | **1.05** |
| 4 | 0.198 | 0.184 | **0.94** | 0.130 | **1.00** |
| 5 (tallest, OPEN-ENDED) | 0.202 | **0.254** | **1.89** | **0.370** | **1.63** |

**In four of five height bins the arms' trees carry FIT's own per-stem mass to within 8 %.** The
entire excess sits in the top quintile, and it arrives there two ways at once: the arms hold a much
larger *share* of their stems in it (`S1` 1.26×, `G1` **1.83×** FIT's), and within it their stems
are 1.63–1.89× heavier. ⚠ **The top quintile is open-ended**, so its within-bin ratio is *itself*
partly composition — the arms' tallest trees are taller than FIT's tallest, which a quintile
standardisation cannot remove. That is also why matching on HEIGHT removes *less* of the excess than
matching on AGE (0.666 vs 0.423 for `S1`): the standardisation has no bin to move the runaway tail
into.

⇒ **Read on ADR 0187's shape-versus-level rule, the answer is STRUCTURE.** A generic per-stem growth
excess would lift every bin; this lifts one. The arms are not growing uniformly heavier trees — they
are accumulating a big-tree tail that FIT's stand does not have, which is exactly what less
competition on a thinned stand produces, and it is the C's own growth doing it (dump-skill trap 5:
in a rung-2 arm the C grows the stand, so this can be neither an F defect nor a growth-code error).
The scalar "in between" verdicts are the pre-registration's own summary statistic failing to see a
one-bin effect; the profile clause it carried is what made the answer readable.

## 7. The decision

**Retire the learned count model from the MORTALITY path.** The count target cannot carry a gross
mortality budget at patch granularity, and no learner or architecture changes that:

* the required precision is **1.1–1.2 % per patch-year**, against an irreducible realisation floor
  of 4.1–4.6 % (`A` = 3.66–3.89×), a cell-year conditioning floor of 39–42 % (`A₁` ≈ 35×), and an
  integer atom that is larger still (§5);
* the amplification is a *property of the arithmetic* — a budget is a DIFFERENCE of counts, so a
  level-to-flux ratio of ~17 multiplies whatever error the count model has;
* the error that gets amplified is a **bias**, not noise, so no account and no smoothing removes it.

**What replaces it is already exact and already measured.** FIT's per-tree hazard as a **rate**:
ADR 0183 measured the port at `|Δhazard|` **5e-18** with certain-set recall = precision = 1.0000,
and ADR 0189's `perfect` arm reproduces FIT's gross kills **and** FIT's own net exactly
(`|diff| 0.0000`). A rate operator has no difference-of-counts amplification in it at all, because
it never forms a budget.

**What is NOT decided here, and must not be read into it.**

1. **This does not say the count model is wrong.** ADR 0186 measured the count as ON TARGET
   (−2.9 %). A count is the wrong KIND of question to derive a mortality *flux* from — ADR 0188's
   item 14, now with a precision attached. The count model's other consumers are untouched.
2. **`S2` — an operator that also owns ESTABLISHMENT — is NOT retired by this**, but its motivation
   changes. ADR 0240 §7's endogeneity argument stands on its own, and §6 above says the surviving
   defect is a big-tree tail, which is a structure question. `S2` should be re-specified around a
   rate operator, not around a count budget, before it is built.
3. **No threshold was moved.** §4's straddle is reported as a straddle; §5 is an addition, not a
   replacement; ADR 0188 §7's three clauses and ADR 0240's fourth are untouched.

**The tie-breaker §4 owes, named:** whether the operator's budget is charged the count target's
LEVEL error or only its year-on-year RATIO error. Two things settle it against the ratio reading.
(a) §5 binds both identically. (b) The ratio basis is measured on **FIT's own stand, where the
operator does not act** — precisely the counterfactual construction ADR 0240 §7 established cannot
bound a quantity that responds to the change being costed; ADR 0240's realised `G1` nominated at
**27.6 %/yr against FIT's 5.96**, a +363 % budget error, worse than either instrument's
counterfactual estimate.

## 8. Method notes paid for here

* **An amplification factor is a reference-basis question in disguise.** H's premise number (±24 %)
  was a real measured quantity from ADR 0185 — on a different population, for a different purpose.
  Re-measuring it on the count model's own basis moved it to 11.8–15.2 % and left the conclusion
  intact. **When a hypothesis quotes a number from another ADR, re-derive it on the basis the new
  statistic needs before building on it** (residual-diagnosis §14).
* ⚠ **DERIVE THE FLOOR FROM THE REFERENCE'S OWN COIN FLIPS WHEN IT HAS THEM.** A between-unit spread
  (FLOOR-1) is the floor for a predictor that cannot see the unit; it is not the irreducible floor,
  and using it would have flattered this verdict by 9×. Where the reference model's stochasticity is
  an explicit per-item probability that the dump already carries, `sqrt(Σ p(1−p))` is an **exact**
  lower bound on any predictor's error, needs no replicates, and binds every architecture. Look for
  it before reaching for a between-unit CV.
* ⚠ **CHECK WHETHER THE QUANTITY YOU ARE ASKING A MODEL TO PREDICT IS AN INTEGER.** §5 is four
  numbers of arithmetic and it is the strongest result in this ADR. Any time a required tolerance is
  expressed as a *fraction of a small count*, compare it against `1/count` first — that comparison
  costs nothing and cannot be argued with. It generalises well beyond this operator.
* ⚠ **A PRE-REGISTERED SUMMARY STATISTIC CAN MISS A ONE-BIN EFFECT; THE PROFILE CLAUSE IS WHAT SAVES
  IT.** §6's scalar shares returned "in between" on three of four arm × axis combinations, and the
  profile it also demanded showed four of five bins at ratio 0.92–1.05 with the whole excess in one
  open-ended bin. **Write the profile requirement INTO the pre-registration**, as STATE §B did here
  — it is the difference between a tie and a diagnosis (ADR 0187's shape-versus-level rule, second
  time it has been decisive).
* ⚠ **AN OPEN-ENDED TOP BIN CANNOT BE STANDARDISED AWAY.** A quantile-matched decomposition removes
  composition *within* the reference's range and is blind to a tail beyond it — which is why the
  height-matched share came out HIGHER than the age-matched one for the same arm. State the
  open-endedness with any matched number that leans on the extreme bin.
* **A basis gate that fails for a knowable reason is still a gate.** §6's `G1` row missed by 1.08.
  Diagnosing it (ratio-of-medians vs median-of-ratios, plus a cell whose emitted stand is empty)
  turned the failure into two findings and kept the *shares* readable, because they are intra-cell.
  Report which columns the miss invalidates and which it does not, rather than suppressing the gate
  or the panel.
* **Fifth time this investigation answered itself out of state already on disk** (ADR 0184, 0186,
  0188, 0189 and now this) — 24 dumps, one map replay CSV, two scorers, no model run.
