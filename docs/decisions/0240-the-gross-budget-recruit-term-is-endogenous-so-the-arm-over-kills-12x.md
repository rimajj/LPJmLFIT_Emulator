# 0240 — The accounting gross-budget arm is built and spends exactly what its definition says, but its recruit term is ENDOGENOUS: the arm kills at 12.5× FIT's discretionary rate, and the +90 % biomass excess only falls to +2.9 % because the >5 m count collapses by 72 % — the per-stem mass error, which ADR 0186 identified as the real defect, gets WORSE (+96 % → +269 %)

* **Status:** accepted
* **Date:** 2026-08-13
* **Line:** S · ADR block 0240–0259 (tier 4) — the first number of the block CLAUDE.md §9 allocated
* **Builds:** **ADR 0189 §7's pre-registered arm**, verbatim: budget `(1−ρ)·n_tree + R̂` with
  `R̂ = #{stems of age == 1}`, spent from a per-patch RUNNING ACCOUNT, charged with what is actually
  removed. Three arms, `G0`/`G0h`/`G1` = `S0`/`S0h`/`S1` asked for a different MAGNITUDE and nothing else.
* **Answers:** ADR 0188 §7's criterion, on its own pre-registered basis and with its thresholds unmoved.
* **Amends:** **ADR 0189 §7's capacity estimate, and the reason it was wrong.** Its 1.493 ± 0.180 %/yr
  "capacity on the arm's own stand" under-predicted the arm's realized nomination rate (27.6 %/yr) by
  **18×**, because `R̂` is not an exogenous property of the stand — it is a RESPONSE to the killing.
  ADR 0189 said its numbers were counterfactual; it did not identify which term made them so. §6 does.
* **Does NOT disturb:** ADR 0188 §§2–5 and ADR 0187 (both reproduced here — FIT's gross K 5.961 %/yr,
  R 6.456, K_cert 3.976, discretionary 2.1 %/yr, mass removal 0.03063, `S1` 0.6 %/yr and 0.01781, all
  to the printed digit). ADR 0186's finding, which this **strengthens**: the defect is per-stem mass.
  ADR 0187's panel-6 verdict, whose arm pair stays pinned (§9).
* **Evidence:** a 360-leg campaign, 12 cells × 2 legs × 3 arms × 5 seeds, `predict` mode,
  `scripts/run_rung2_response_matrix.sh` with `ARMS="G0 G0h G1"`; **357 legs complete** (§5).
  Scorers: `diagnose_rung2_gross_account_identity.py` (new, the derivable gate),
  `diagnose_rung2_kill_budget.py` panel F (new), `diagnose_rung2_kill_selectivity.py`
  (job **1788641**, `logs/S-killselG2.1788641.out`), `diagnose_rung2_anchor_preflight.py` panel 4.

## 1. What was built

`scripts/rung2_s_demography_harness.jl`, one new block before the decision:

```
acct  += (1 − ρ)·n_tree + R̂          R̂ = #{age == 1}, EXACT at the rendezvous (ADR 0189 §2)
b      = clamp(acct, 0, n_tree)       what may be spent THIS year
ρ_dec  = 1 − b/n_tree                 the fraction the SAME three operators then use
acct  -= n_kill                       charge what was actually removed
```

The clamp is on what may be **spent**, not on the account, which is what lets a "grow" year repay an
earlier overspend instead of being clipped to zero — the whole point of the accounting form (ADR 0189 §6:
per-year rectification is convex, so an unbiased-but-noisy budget over-kills). The charge is the REALIZED
`n_kill` rather than the feasibility panel's modelled `max(b, n_cert)`, because that is what the C removes.

**Guardrail 4, measured rather than asserted.** The `S*`/`NP` arms read `ρ_dec`, which *is* `ρ` for them.
Re-running `S1` historic/`predict` at Hainich under the new code leaves the arm log **byte-identical over
all 27 pre-existing columns, 500 patch-years**, and the dump **identical in every initialised column,
40 569 tree records**. ⚠ A file-level `cmp` on the dump reports 28 322 differing lines for those same
byte-identical decisions — `Pfttree.sapwood_old` is a dead struct field `new_tree` never zeroes, so it is
garbage in every phase. `scripts/diagnose_rung2_dump_equality.py` knows the uninitialised set; use it.

## 2. The derivable gate: the arm spends exactly what its definition says

Two answers are known in advance (skill traps 5d/5f — a derivable arm is the cheapest real gate, and it
has caught two basis errors in this investigation already). `scripts/diagnose_rung2_gross_account_identity.py`:

1. **The account identity, row by row**, chained on the LOGGED account so an error cannot hide behind its
   own propagation: **451 161 patch-years over 360 legs, max |logged − derived| = 0.000e+00** on `budget`,
   `rho_eff` and `acct` alike.
2. **`G0`'s spend ratio.** `G0` draws uniformly at `ρ_dec`, so `E[n_kill] = b` exactly:
   **0.9998 (historic) / 0.9995 (ssp370)** against a pre-registered ±0.02.

⚠ `G0h`/`G1` sit at **1.05–1.14**, and that is CORRECT, not a defect: their certain deaths have `f = 0`
and cannot be un-killed, so a short budget still costs `n_cert` and the account repays it afterwards.

⇒ **Nothing below is an implementation artifact.** The arm does what ADR 0189 §7 specified.

## 3. THE CRITERION, on ADR 0188 §7's own basis, thresholds unmoved

ssp370 leg, FIT-gain cells, median over cells with seeds averaged, behind ADR 0185 §5's coverage gate:

| | criterion | FIT | `S1` (status quo) | **`G1`** | `G0h` | `G0` |
|---|---|---|---|---|---|---|
| discretionary kill rate %/yr | **≥ 1.5** | 2.1 | 0.6 | **26.2** | 29.0 | 63.4 |
| annual mass removal | **≥ 0.025** | 0.03063 | 0.01781 | **0.03203** | 0.02901 | 0.43870 |
| agb departure | **< +40 %** | — | +90.6 % | **+2.9 %** | −20.2 % | −100.0 % |
| count departure, `n_emit` | ADR 0186 §8.8 | — | −2.9 % | **−72.1 %** | −74.3 % | −100.0 % |
| **per-stem mass departure** | — | — | +96 % | **+269 %** | +210 % | — |
| roster horizon, own stand | not → 0.1× | ~1 | 0.944× | 0.612× | 0.596× | 0.476× |
| nomination rate %/yr | FIT gross 5.96 | 5.961 | 4.28 | 27.6 | 33.3 | 71.4 |
| `R̂` on its own stand %/yr | FIT 6.456 | 6.456 | not logged | 27.6 | 32.7 | 70.6 |
| empty-budget share | — | — | 0.462 | 0.395 | 0.330 | 0.061 |
| top-decile kill concentration | — | — | 0.575 | 0.347 | 0.304 | 0.199 |

**By the letter, `G1` passes all three clauses.** The rate clears 1.5 %/yr by 17×, the mass removal lands
within 4.6 % of FIT's own, the agb departure falls from +90.6 % to +2.9 %, and the roster runs to 0.612×,
nowhere near clause (a)'s 0.1× FAIL line.

**In substance it fails, and the reason is in the two rows the criterion did not name.**

## 4. Why it is a fail: the biomass lands on FIT's by CANCELLING two large errors

`dAGB = +2.9 %` with `dN = −72.1 %` forces per-stem mass to **+269 %** — arithmetically, `1.029/0.279`.
The stand holds a **quarter** of FIT's trees above the 5 m emission cut, each **3.7×** too heavy.

ADR 0186 established that the emulator's defect is per-stem mass, not count. **Under the gross budget that
error gets WORSE**: `S1`'s per-stem mass departure is +96 % (from its own −2.9 %/+90.6 % pair), `G1`'s is
+269 %. The total biomass improves only because the count collapses underneath it.

So the honest one-line verdict is the mirror of ADR 0186's: **the status quo has the right number of trees
and far too much mass in them; the gross-budget arm has the right total mass and far too few trees.** Both
are the same underlying error — per-stem mass — read through two different constraints, and neither is a
faithful demography. Reporting "+2.9 % agb, criterion met" without the count row beside it would be exactly
the failure mode ADR 0184's "report the level beside every shift" was written against.

## 5. Coverage — and one latent harness bug the arm surfaced

357 of 360 legs complete. The three that are not are the **known, open, C-side** `ERROR043: duplicate
roster key` fault in line M's `rung2_apply.c:118` (`c52059` `G0` s2/s5, `c44048` `G0h` s5) — unchanged,
still to raise with M. One further leg (`c42490` `G0` s2) is excluded by the dump-based coverage gate as
"24 patches at terminal", which is §6's empty patch seen from the scoring side: an empty patch emits no
`T` record, so the gate cannot tell it from a missing one.

Getting there cost **53 of the first 360 legs** to a bug that had been latent for the entire investigation.

## 6. ⚠ THE BUG THE `G*` ARMS SURFACED: an EMPTY patch deadlocked the harness

`read_request` initialised `year`/`patch` to a sentinel **−1** and set them only inside the `T`-record
branch — but **a patch with no living trees emits no `T` record at all**. The response FILENAME is built
from those two numbers, so the harness answered under `rsp_…_y-0001_p-01` while the C waited for
`rsp_…_y02066_p005`, marked the request served, never retried, and 600 s later the run died on
`ERROR043: rung2 apply: no answer for year 2066 patch 5`.

The dump-analysis skill's trap 7 has said "empty patches emit no `T` record" since ADR 0175; nobody applied
it to the *request* parser. It stayed invisible because **no `S*` arm ever empties a patch and the `G*` arms
do** (worst cell: 0.1 % of patch-years). Fixed by taking the identity off the `P grow` record,
cross-checking the tree rows against it, and refusing a request whose identity is still negative — a loud
failure instead of a ten-minute deadlock.

Two consequences beyond this ADR. **(a)** The "no answer after 600 s" variant of `ERROR043` is not
necessarily a slow harness, so ADR 0185's 6 late-ssp370 losses may be this bug rather than the idle
timeout they were attributed to; `--max-idle` was nevertheless raised 300 → **900 s** (it must exceed the
C's own 600 s wait, which it never did). **(b)** The reusable rule: **whenever a filename is derived from
parsed input, a parse that yields a sentinel is a silent hang, not an error — assert the identity before
you build the name.**

## 7. WHY the arm over-spends by 12×: the recruit term is ENDOGENOUS

The mechanism is visible in one trace (Hainich, ssp370, `G1`, patch-means):

| year | n_tree | `R̂` | target | ρ | ρ_eff | budget | n_kill | agb |
|---|---|---|---|---|---|---|---|---|
| 2020 | 16.0 | 1.36 | 8.62 | 0.985 | 0.887 | 1.70 | 1.52 | 5016 |
| 2050 | 13.2 | 4.80 | 5.50 | 0.988 | 0.546 | 4.73 | 4.76 | 3291 |
| 2100 | 9.3 | 5.36 | 3.33 | 0.999 | 0.401 | 5.27 | 5.28 | 4092 |

**ρ ≈ 0.99 throughout, so `(1−ρ)·n_tree ≈ 0.1 and the budget IS `R̂`.** That is the gross identity working
as designed — with a near-stationary count, `K = R`. The problem is whose `R` it is:

* FIT's own recruitment is **6.456 %/yr** of its roster (ADR 0188 §4, reproduced).
* The `G*` arms' own recruitment is **27.6 / 32.7 / 70.6 %/yr** — **4.3× to 10.9× FIT's**.

Establishment in LPJmL-FIT is light/FPC-driven and is left to the C in every arm (`ESTAB_C`). So killing
opens space, the C establishes into it, and **next year's budget grows with the killing it caused**. The
loop is self-limiting rather than explosive — it settles into a young, thin, churning stand (roster 0.6×,
`R̂` ≈ `n_kill` exactly, see the table) — but it settles at the wrong equilibrium.

This is why ADR 0189 §7's capacity number was 18× low: it measured `R̂` on stands where the operator was
**not** spending gross (FIT's own, and `S1`'s own). **The generalisable trap:** a counterfactual capacity
panel cannot bound a quantity that responds to the change being costed. The tell was available a priori —
`R̂` is a *stand* statistic, and skill trap 5 already says the C grows the stand in every arm; the flip
side, unstated until now, is that **a stand-derived statistic used as an INPUT to the operator closes a
feedback loop**, and its value under the change is not its value today.

## 8. What follows — and what does NOT

**Settled, do not re-investigate.**

1. **The gross budget is not a magnitude-calibration problem.** Its mean is right (ADR 0189 §3) and the
   account spends it exactly (§2). Do not propose a coefficient on `R̂` or a tuned account.
2. **`G0` is dead as a candidate, and it is still the useful self-test.** Uniform thinning at a gross
   budget removes 44 % of stand mass per year and annihilates the >5 m population (−100 % on both count
   and agb, 14× FIT's mass removal). Keep it as the derivable arm; never quote it as a contender.
3. **The kill-set composition is still not the defect.** `G1`'s mass selectivity is 0.97 against FIT's
   0.90 — mass-neutral, as `S1`'s was. ADR 0187's closure stands.
4. **The count channel remains closed in the direction ADR 0186 named.** Nothing here re-opens a
   count-side instrument: the gross budget is a MORTALITY-FLUX instrument, and the count is now the thing
   it breaks rather than the thing it fixes.

**The next question, and it is now sharply posed.** Both formulations put the same error in different
places, so the binding constraint is neither the budget nor the selection: **per-stem mass**. A mortality
operator cannot fix it — it decides who dies, and the trees that survive are too heavy whether there are
many or few. The candidates are therefore outside the demography interface:

* the C's own growth on the arms' stands (F is not in this loop at all — skill trap 5), i.e. whether the
  thinned stand's per-stem growth is FIT's growth on a genuinely different stand or an artifact of the
  substitution; and
* whether an operator that also constrains RECRUITMENT (`ESTAB_C` is deferred in every arm here, so
  `n_recruit ≡ 0` by construction and no arm has ever expressed a recruitment decision) can hold the
  count and the mass at once. That is the `S2` arm the harness header has always listed as unwired.

**Pre-registered, before either is opened:** the blessed statistic stays the pair `(dN, dAGB)` read
TOGETHER with per-stem mass beside them, on ADR 0185 §5's basis, at the FIT-gain cells on the ssp370 leg.
A candidate passes only if **both** |dN| and |dAGB| are under 40 % — not one of them. `G1`'s +2.9 % agb is
the worked example of why a single-clause criterion is not enough, and this ADR is the reason the clause
is now written as a pair rather than moved (ADR 0187's "do not move a threshold after the fact" applies:
ADR 0188 §7's three clauses are NOT amended, a fourth is added and its addition is recorded here).

## 9. Method notes paid for here

* **A widened arm set must not widen a pre-registered verdict.** `ARMS` now widens four scorers at once
  (comma or space), defaults unchanged, but `LEARNED` (ADR 0185) and `OPERATOR_ARMS` (ADR 0187) do NOT
  follow it — panel 6 returns the same REFUTED verdict on the same two arms with `G*` in the table.
  `kill_selectivity` additionally forces `REC` back in, because it is both the reference and the
  height-quintile basis; dropping it empties the report rather than narrowing it.
* **A missing measurement must not print as a measured zero.** `R̂` reads `nan` for every `S*` leg: their
  logs predate the column. Their stands do recruit; it is simply not logged. Printing 0.00 % there would
  have asserted a false fact in the same table that makes the endogeneity argument.
* **For a rare-but-fatal event, print the maximum, not the median.** The empty-roster share is 0.000 as a
  per-cell median and 0.001 as a maximum — and 0.001 was enough to kill 53 legs.
* **A campaign's failures are silent in every obvious place.** The job exits on the C's code, a truncated
  dump looks like a short one, and the harness's `served <N> patch-years` line is written by the FAILURE
  path (the job file kills a healthy harness before it prints), so reading its absence as failure inverts
  the test. `scripts/check_rung2_campaign_coverage.py` gates on the C's own completion line plus the arm
  log's patch-year count, and prints the re-run lines.
