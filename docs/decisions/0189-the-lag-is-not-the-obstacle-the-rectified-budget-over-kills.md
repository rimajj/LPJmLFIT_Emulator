# 0189 — A lagged recruit count carries the gross budget exactly and cheaply: last year's recruits ARE countable at the rendezvous (100.000 % of 29 700 patch-years), so no interface change is needed — but the budget must NOT be rectified per patch-year, because that turns an unbiased budget into a 17–66 % over-kill that would collapse the roster to 0.62×/0.11× over the ssp370 leg

* **Status:** accepted
* **Date:** 2026-08-13
* **Line:** S · ADR block 0170–0189 (tier 3) — **this ADR EXHAUSTS line S's tier-3 block; §9 allocates tier 4**
* **Answers:** **ADR 0188 §7's one required derivation** — *"R̂ for the current year is not available at
  decision time … derive whether a lagged R̂ still moves the blessed statistic before writing the arm"*.
  The answer is YES, and the derivation also found a second, larger problem in the same instrument.
* **Does NOT disturb:** ADR 0188 §§2–5 (H1 refuted, the ρ≥1 gate, the net-vs-gross mechanism) — every number
  reproduced here where they overlap. ADR 0187 (the rate shortfall, the kill set's composition). ADR 0186
  §8.8's closure of count-side instruments — §7 states why the accounting formulation is not one. ADR 0183
  (the hazard as a function).
* **Amends:** **ADR 0188 §7's pre-registered instrument.** The budget `(n_now − target) + R̂` is right in its
  mean and wrong in the way it is spent. The arm to build is the ACCOUNTING form (§5), and its capacity on
  the arm's own stand is **marginal, not comfortable** — pre-registered here in advance (§7).
* **Evidence:** `scripts/diagnose_rung2_gross_budget_lag.py`, SLURM job **1788149** (log
  `logs/S-grossbudget4.1788149.out`; the earlier 1788141/1788143/1788148 are the same scorer before the two
  corrections in §8). **No model run.** 12 cells × 2 legs of `REC` `predict` dumps joined to
  `map_on_rec_stand_predict.csv`, plus `S1`'s own dumps + arm logs (seed 1) for §6, behind ADR 0185 §5's
  imported completion+coverage gate — 30 300 patch-years, 0 unmatched, 0 roster-count mismatches.

## 1. The question, and why it had to be answered before writing the arm

ADR 0188 sized the lever: the operator's budget is the NET count change (0.78–1.02 %/yr) while the mortality
flux that moves biomass is the GROSS (FIT 5.65–5.96 %/yr), the difference being recruitment (4.6–6.5 %/yr)
which the C supplies regardless because establishment is deferred (`ESTAB_C`). Its §7 pre-registered the fix
— budget `(n_now − target) + R̂` — and named the one thing that could kill it: **the rendezvous is at the
`grow` phase and establishment happens after `post`, so this year's R̂ does not exist yet.**

Three things were derived and written down before the run (the scorer's header carries them verbatim).

## 2. D1 — last year's recruit cohort is EXACTLY countable at the rendezvous

`age` at `grow` is post-increment and establishment sets age 0, so a stem with `age == 1` at the rendezvous
of year y established at the `post` phase of y−1:

> `#{age == 1 at grow, year y}` == `R(y−1)` == `n_post(y−1) − n_grow(y−1)`

**Measured: 29 700 of 29 700 patch-years, 100.000 %.** The harness already receives the whole roster, so it
can count the previous year's recruits itself with no new column, no index tracking (hence no exposure to the
`ERROR043` duplicate-key fault) and **no integration point with line M's `rung2_apply.c`**. ADR 0188 §7's
escalation branch does not fire.

## 3. D2 — the lag does not put the count at risk, and the argument is algebraic

With `K = (n_now − target) + R̂` the realized count is `n_next = n_now − K + R = target + (R − R̂)`, so with
`R̂ = R(y−1)` the cumulative departure over a leg **telescopes** to `R_last − R_first` — bounded by ONE
year's recruitment however long the leg, where the current operator's (`R̂ = 0`) is `Σ_y R_y` and grows with
the horizon.

| leg | R̂ | ‖Σ(R−R̂)‖ stems | as % of roster | derived bound |
|---|---|---|---|---|
| historic | none (current) | 35.72 | 131.6 % | — |
| historic | **lag1** | **1.73** | **6.4 %** | 4.89 |
| ssp370 | none (current) | 145.96 | 667.0 % | — |
| ssp370 | **lag1** | **1.72** | **7.8 %** | 7.21 |

Both lagged values sit below their derived bound. A running mean is *worse* on this axis (22.6/24.7 % for a
5-yr mean, 38.0/106.7 % expanding) because only the one-year lag telescopes.

## 4. What recruitment actually looks like — and it carries the warming signal itself

12 cells, per patch-year (a patch holds ~4–11 emitted stems, 2–3× that in roster):

| leg | R %/yr | R per patch-yr | sd | zero share | lag-1 r (pooled) | lag-1 r (within-patch) |
|---|---|---|---|---|---|---|
| historic | **4.619** | 1.786 | 2.233 | 35.5 % | 0.618 | **0.230** |
| ssp370 | **6.456** | 1.802 | 2.295 | 35.0 % | 0.636 | **0.343** |

The two rate columns reproduce ADR 0188 §4's 4.619/6.456 exactly — a free cross-check, since this scorer
reaches them through a different code path.

⚠ **The pooled lag-1 correlation is mostly NOT temporal.** Demeaning by patch drops it from 0.62 to 0.23 and
0.64 to 0.34: what a lagged R̂ recovers is chiefly each patch's own persistent recruitment LEVEL, not next
year's value. That is fine — a budget needs the right level — but the pooled number must never be quoted as
year-to-year skill. Both are printed side by side.

**And FIT's own recruitment rises +39.8 % between the legs** (4.619 → 6.456 %/yr). So the recruit term is
itself climate-responsive: handing it to the operator hands over a budget that RISES under warming, one year
late. That is a response channel the current net budget does not have at all.

## 5. D3 — the capacity, its two anchors, and the finding that changes the instrument

The capacity statistic is, per patch-year on FIT's OWN stand,

```
b     = max(0, (1−ρ)·n_tree + R̂)      the budget the operator may spend
D     = max(0, b − n_cert)             what is left for the discretionary channel
total = 0 if b ≤ 0 else max(b, n_cert) what is removed (the ρ≥1 gate spares even certain deaths, §8)
net   = R − total                      the implied roster count change
```

with ρ = `clamp(target/n_prev, 0.7, 1.3)` from the count model's own replay on that roster.

ssp370 leg, 12 cells, medians over cells (seeds averaged), all as % of roster per year:

| R̂ | budget | **D** | SE | empty | total | net | ×over leg | FIT K_all | FIT K_disc |
|---|---|---|---|---|---|---|---|---|---|
| none (current) | 1.056 | **0.590** | 0.100 | 46.7 % | 2.687 | +3.814 | 21.97 | 5.961 | 2.049 |
| **lag1** | 6.378 | **3.525** | 0.566 | 21.8 % | 6.999 | −0.583 | **0.62** | 5.961 | 2.049 |
| mean5 | 6.188 | 3.898 | 0.515 | 8.4 % | 7.443 | −0.897 | 0.48 | 5.961 | 2.049 |
| oracle (unavailable) | 6.371 | 4.509 | 0.582 | 22.3 % | 7.609 | −1.056 | 0.42 | 5.961 | 2.049 |
| **perfect** (derivable arm) | 5.961 | **2.049** | 0.598 | 35.6 % | 5.961 | +0.254 | 1.23 | 5.961 | 2.049 |
| **lag1_acct** (§5.3) | 5.037 | **2.702** | 0.446 | 40.9 % | **5.817** | **+0.657** | **1.70** | 5.961 | 2.049 |

**5.1 Both usable anchors pass.** `none` returns **0.590 %/yr** inside its pre-registered [0.3, 0.9] band,
reproducing ADR 0187's measured 0.5–0.6 % discretionary rate through a completely different route. `perfect`
returns **2.049 %/yr against FIT's own K_disc of 2.049 %, |diff| 0.0000** — an exact identity, as derived.

**5.2 The lag is not the obstacle.** `lag1` delivers **3.525 %/yr** of discretionary capacity against the
1.5 %/yr criterion — 2.4× the threshold, and 6.0× the current operator's 0.590 %. ADR 0188 §7's verdict
branch **(i)** fires: the instrument survives the lag.

**5.3 But the budget as pre-registered OVER-kills, and the horizon column is what shows it.** `lag1`'s
implied total mortality is **6.999 %/yr against FIT's own 5.961** (+17 %), giving net −0.583 %/yr ⇒ the
roster would fall to **0.62×** over the 81-year leg. The cause is **not** the gross-budget idea: `perfect`
reproduces FIT's gross kills and FIT's own net exactly. It is **rectification** — `max(0, b − n_cert)` and
`max(b, n_cert)` are convex, so a budget that is unbiased but noisy per patch-year over-spends, and the count
model's per-patch-year error is large (±24 %, ADR 0185's separability figure). The `perfect`-to-`oracle` gap
(2.049 → 4.509) IS that error, measured.

Smoothing does not fix it (`mean5` is worse: net −0.897). **What fixes it is not rectifying at all:** accrue
the signed budget increment into a running account and spend what the account holds, so a year the count
model says "grow" REPAYS an earlier overspend instead of being clipped to zero. `lag1_acct` lands total
mortality at **5.817 %/yr vs FIT's 5.961 (−2.4 %)**, net **+0.657 %/yr**, roster **1.70×** — bounded — while
still delivering **2.702 %/yr** of discretionary capacity.

## 6. The same statistic on the arm's OWN stand — where it is much tighter

The arms' stands have diverged (+90 % agb), so a FIT-stand-only conclusion could be an artifact. Repeating it
on `S1`'s own dumps with ρ from its own arm log (seed 1, ssp370):

| R̂ | budget | **D** | SE | empty | total | net | ×over leg | S1 K_all | S1 K_disc |
|---|---|---|---|---|---|---|---|---|---|
| none (current) | 0.929 | 0.452 | 0.088 | 45.3 % | 4.344 | +0.594 | 1.62 | 5.001 | 0.494 |
| lag1 | 5.014 | 2.197 | 0.258 | 26.3 % | 8.292 | −2.767 | **0.11** | 5.001 | 0.494 |
| **lag1_acct** | 2.971 | **1.493** | 0.180 | 60.7 % | 4.160 | +0.777 | 1.88 | 5.001 | 0.494 |

Three things to carry forward. **(a) The panel is corroborated by an independent number:** `none`'s modelled
total mortality is **4.344 %/yr against the arm's realized 5.001** and its implied roster change is
+0.594 %/yr — i.e. near-stationary, which is exactly ADR 0186's measured "count on target (−2.9 %)". The
residual is the C's own hard kills on gated years, which this model sets to 0 by construction (§8).
**(b) The over-kill is far worse on the arm's own stand** — 8.292 vs 5.001 %/yr, roster to **0.11×** — because
that stand carries a heavier certain-death load (K_cert 4.441 vs FIT's 3.976) for the budget to overdraw.
**(c) The accounting form's capacity there is 1.493 ± 0.180 %/yr — AT the 1.5 % criterion, 0.04 σ below it**,
though 3.0× the arm's current 0.494 %. So the criterion will be a close call, and that is being said before
the arm is run rather than after.

## 7. The decision

**Record the derivation; change no default, no flag and no `src/**` file in this ADR.** The next action, with
its lever sized and its risks named:

**Build the accounting form of the gross budget, not the per-year rectified form.** Per patch: accrue
`(n_now − target) + R̂` with `R̂ = #{age == 1}` (exact, §2), spend what the account holds, charge a forced
overshoot against it. ADR 0188 §7's criterion is unchanged — ssp370, FIT-gain cells: discretionary kill rate
**≥ 1.5 %/yr**, annual mass removal **≥ 0.025**, agb departure **< +40 %** — and three clauses are added here:

1. **The roster-horizon check is part of the gate, not a diagnostic.** Report implied `net` and the
   compounded roster factor beside every rate. A rate that clears 1.5 % while the roster runs to 0.1× is not
   a pass; it has traded a biomass excess for a stand collapse.
2. **Capacity is NECESSARY, NOT SUFFICIENT.** This ADR measures what the operator could afford to spend, not
   what it realizes — the draw is stochastic and `_hazard_tilt` can still return θ = 0. Say "capacity".
3. **Expect the criterion to be marginal on the arm's own stand** (§6c). If it lands just under, that is the
   pre-registered expectation, not a new mystery — and the next lever is the count model's per-patch-year
   error, not the budget.

**Why this is not a count-side instrument** (ADR 0186 §8.8): it does not change the count target, the
`n_prev` basis, or add an anchor. `n_next = target + (R − R̂)` still holds, so the count the arm lands on is
the one it already lands on correctly; the account only changes *when* the same total is spent. The
`empty`-budget share stays high (40–61 %) under the account, i.e. mortality becomes LUMPIER than FIT's — a
real caveat to measure on the arm, and the honest reason not to oversell the accounting form.

## 8. Gotchas paid for here

* ⚠ **A DERIVED ANCHOR MUST BE DERIVED THROUGH THE SAME NONLINEARITY AS THE STATISTIC, OR IT IS NOT THAT
  STATISTIC'S ANCHOR.** A second band was pre-registered for the oracle arm ([1.5, 2.6] %/yr, "near FIT's own
  K_disc") from `n_now − target ≈ K_all − R` ⇒ `b ≈ K_all` ⇒ `D ≈ K_all − K_cert = K_disc`. Every step is a
  statement about MEANS while the statistic contains `max(0, b − n_cert)`, which is convex — so it "failed"
  at 4.509 for a reason that is a property of the instrument, not a defect of the panel, and the budget mean
  it was derived from landed on FIT's gross kills to 0.6 %. Under ADR 0187's clause the tolerance was **not**
  moved: the band is retained in the code as `ANCHOR_ORACLE_MISDERIVED`, printed every run, and replaced —
  before any verdict was read — by an arm whose answer is an exact identity rather than a band (`perfect`,
  which returned |diff| 0.0000). **The generalisation: when a statistic is convex, derive the anchor by
  removing the noise (a perfect-input arm), not by pushing means through the identity.**
* ⚠ **MODEL THE GATE, NOT JUST THE BUDGET — AND CHECK THE MODEL AGAINST A NUMBER THAT IS ALREADY PUBLISHED.**
  A first version took `total = max(b, n_cert)` unconditionally, i.e. assumed certain deaths are always
  honoured. They are not: the kill list IS the whole answer, so on a gated year (`b ≤ 0`, 42–46 % of
  patch-years) the arm spares the certain deaths too. That single omission put the CURRENT operator's implied
  roster at 0.45× on the arm's own stand — contradicting ADR 0186's measured on-target count. Fixing it moved
  the same row to +0.594 %/yr and 1.62×, agreeing with the published number. **A counterfactual panel that
  contains the status quo as one of its arms has a free validation in it; use it.**
* ⚠ **A POOLED LAG-1 AUTOCORRELATION OVER MANY UNITS IS MOSTLY CROSS-SECTIONAL.** 0.618/0.636 pooled vs
  0.230/0.343 demeaned by patch (a 2-cell smoke test read 0.28–0.32 and the 12-cell pooled value read 0.62,
  which is the tell: adding UNITS should not raise a temporal correlation). Print both.
* **The recruit observable needed no dump-format change and no C change** — `age == 1` at the rendezvous.
  Fourth time in this investigation that a question answered itself out of state already on disk (ADR 0184,
  0186, 0188 were the arm log; this one is one extra column in the same scan).
* **`scan_rec_dump` was extended additively** (indices 0–5 unchanged, `n_cert`/`n_age1` appended at 6–7), so
  ADR 0188's panels return the same numbers from the same function — which is why §4's 4.619/6.456 is a
  cross-check rather than a re-derivation.
