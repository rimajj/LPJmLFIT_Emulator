# ADR 0136 — The two remaining `gp_sum` basis differences, measured one at a time: the leaf-on conductance basis is a real GPP excess at every seasonal cell, and the λ-solve Vcmax basis is faithful and makes the target statistic WORSE

* **Status:** accepted
* **Date:** 2026-08-13
* **Line:** M (multi-cell coupled S+F+E; rung 3 of `EXECUTION_PLAN.md`)
* **Discharges:** ADR 0051's "Consequences" item *"Not addressed here (pre-existing, documented) … a separate opt-in change with their own re-measure"* — unmeasured for two weeks. **Executes** ADR 0135 §"what to do next" item (a) and widens it from one difference to two.
* **Basis:** the LIVE lines of `/home/jamirp/lpjml56fit/src/lpj/gp_sum.c:36-68` and `water_stressed.c:190-210`; the five biome cells' committed fixtures, 2010–2019, alignment A (roster(y−1) + year-y forcing → roster(y)), 25-patch ensemble, `slow = nothing`. Reference statistic `GPP F/C` on the CLOSED population basis of ADR 0130 (both sides on F's own >5 m roster). Job `logs/M-gpsum3.1775096.out`; basis gate PASS.
* **Related:** ADR 0135 (which scoped the excess to the kernel and named this item); ADR 0051 (which registered both); ADR 0130 (the +7.4 %/+10.1 % Hainich GPP excess this is aimed at); ADR 0131/0133 (the demand gate — the same "faithful ≠ better" shape); ADR 0126 §5 (the one-variable-arm rule this obeys).

---

## 1. Context

ADR 0135 closed the light INPUT as a suspect for F_diff's tree-GPP excess and left a three-item shortlist,
first of which was:

> **the λ solve's Vcmax basis** — the C's bisection residual uses `pft->vmax` **as left by `gp_sum`**,
> computed at a **crown-cover, no-phen** `apar`, while F recomputes `vm` at the **actual layered,
> phen-scaled** `apar` before its solve.

Reading `gp_sum.c` end to end to confirm that turned up a **second** difference in the same 30-line
function, and both were already on record as unmeasured: ADR 0051's "Consequences" section names them
together and defers them. This ADR measures both, one variable at a time.

## 2. What the C actually does (both lines are LIVE — no comment block, no `!individual` gate)

`gp_sum.c:53-67`, once per day per `Pft` (⇒ per TREE, `individual:true`):

```c
adtmm = photosynthesis(pft,&agd,&rd,&pft->vmax, LAMBDA_OPT, tstress, ppm2Pa(co2), temp,
                       par*pft->fpc*alphaa(pft,…)*(1-albedo_leaf)*(1-pft->snowcover),   /* NO phen */
                       daylength, config->individual, TRUE);                            /* comp_vm=TRUE  */
gp = 1.6*adtmm/(ppm2bar(co2)*(1.0-LAMBDA_OPT)*hour2sec(daylength)) + pft->par->gmin*pft->fpc*(1-snowcover);
gp_stand        += gp*pft->phen;          /* phen applied to the WHOLE gp, afterwards */
*fpc_total      += pft->fpc;              /* the PLAIN sum, not phen-weighted         */
…
return gp_stand / *fpc_total;
```

and `water_stressed.c:198-206`:

```c
data.apar  = par*(1-albedo_leaf)*alphaa(pft,…)*fpar(pft);   /* the LAYERED, phen-carrying absorption */
data.vmax  = pft->vmax;                                     /* ← as left by gp_sum, above            */
data.compvm = FALSE;                                        /* the bisection does NOT recompute it   */
lambda = bisect((Bisectfcn)fcn, 0.02, LAMBDA_OPT+0.05, &data, …);
adtmm  = photosynthesis(pft,&agd,rd,&pft->vmax, lambda, …, data.apar, …, TRUE);  /* compvm=TRUE */
```

So the two differences from F_diff are:

| tag | flag | the C | F_diff (before this ADR) |
|---|---|---|---|
| **gpS** | `WaterParams.gp_stand_leafon_basis` | `gp` at FULL leaf cover, then `Σ gp·φ / Σ fpc` | `φ` folded into the pass-1 `apar` **and** `gmin`, then `Σ gp(φ) / Σ fpc·φ` |
| **vmG** | `WaterParams.lambda_vm_gp` | the λ residual carries the **crown-cover, no-phen** Vcmax | the λ residual carries the Vcmax at the **layered, phen-scaled** `apar` |

**Two properties settle what these are and are not.** (a) Vcmax is computed at `pi = lambdamc3·co2`
(`photosynthesis.c:78-91`) — **it does not depend on the λ argument at all** — and the C's FINAL call is
`compvm=TRUE` at `data.apar`, exactly what F_diff already does. ⇒ **vmG changes only the solved λ, never
the Vcmax the reported `agd`/`rd` are built from.** (b) At `φ ≡ 1` both are exact identities, so both are
**partial-leaf-day** effects; that is what the unit test pins, bitwise.

## 3. Decision

**Ship both as opt-in `WaterParams` flags, default OFF and byte-identical, and flip NEITHER today.**
Publish the per-cell measurement and pre-register a flip criterion for gpS only (§7). The measurement is
the deliverable; the flip is not, and §5 says why for each.

## 4. What was measured (5 cells × 10 years, one variable per arm)

Arm `A` is the published gate-off basis of ADR 0125/0127/0130 (beech parameters everywhere,
`sapwood_bg = 0`), so the columns are differenced against exactly the arm every prior number is on. The
C side is arm-independent.

**Per-cell effect on F's own annual tree GPP** (gC/m²/yr, ensemble mean; `d%` vs arm `A`):

| cell | gpS `d%` | vmG `d%` | both `d%` |
|---|---|---|---|
| `boreal_siberia` | **−10.41** | +9.12 | −0.39 |
| `temperate_hainich` | **−5.10** | +1.07 | −3.93 |
| `mediterranean_iberia` | −3.21 | +7.56 | +4.65 |
| `semiarid_sahel` | −0.10 | +7.06 | +6.97 |
| `tropical_amazon` | −0.23 | +0.72 | +0.49 |

**The kernel error itself** — `GPP F/C` on ADR 0130's closed population, i.e. the statistic ADR 0135
established IS the kernel error:

| cell | A | +gpS | +vmG | +both |
|---|---|---|---|---|
| `boreal_siberia` | 1.044 | **0.935** | 1.139 | 1.040 |
| `temperate_hainich` | 1.101 | **1.045** | 1.113 | 1.058 |
| `mediterranean_iberia` | 1.473 | 1.425 | 1.584 | 1.541 |
| `semiarid_sahel` | 1.121 | 1.120 | 1.201 | 1.200 |
| `tropical_amazon` | 1.030 | 1.028 | 1.037 | 1.035 |

Aggregates are computed by the script, not read off the table (ADR 0104). Mean over cells of
`|GPP F/C − 1|` / `|bmi F/C − 1|`, with `mediterranean_iberia` excluded from the 4-cell column for the
reason ADR 0127/0133 already exclude it (its own 1.5–1.7× growth error dominates any mean it enters), and
with every cell whose `bmi` ratio is negative dropped and counted rather than folded in:

| arm | GPP 5-cell | GPP 4-cell | bmi 5-cell (n) | bmi 4-cell (n) |
|---|---|---|---|---|
| `A` | 0.1538 | 0.0741 | 0.6717 (3) | 0.1441 (2) |
| `A` + gpS | **0.1365** | **0.0643** | 0.6035 (3) | 0.1223 (2) |
| `A` + vmG | 0.2148 | 0.1225 | 0.8446 (3) | 0.2220 (2) |
| `A` + both | 0.1747 | 0.0830 | 0.7115 (3) | **0.0956** (2) |
| `Pgbgg` (the shipping configuration) | 0.1898 | 0.0824 | 0.4859 (5) | 0.1266 (4) |
| `Pgbgg` + gpS (**`Pgbggs`**) | **0.1480** | **0.0328** | **0.4205** (5) | **0.0535** (4) |
| `Pgbgg` + vmG (`Pgbggv`) | 0.2439 | 0.1179 | 0.6183 (5) | 0.1872 (4) |
| `Pgbgg` + both (`Pgbgg2`) | 0.2059 | 0.0723 | 0.5550 (5) | 0.1147 (4) |

`Pgbgg` = per-PFT parameters + the C's tree demand gate + the prognostic below-ground wood pool — the most
faithful configuration that exists, and the one a default flip would ship into. Its `bmi` columns admit all
five cells (`n = 5`) where arm `A`'s admit two, because the per-PFT parameters fix the two hot cells'
carbon-balance sign; **compare a `bmi` column only where the two `n`s agree.**

**`GPP F/C` on that shipping configuration, per cell:**

| cell | `Pgbgg` | +gpS | +vmG | +both |
|---|---|---|---|---|
| `boreal_siberia` | 1.183 | **1.053** | 1.237 | 1.122 |
| `temperate_hainich` | 1.091 | **1.030** | 1.103 | 1.042 |
| `mediterranean_iberia` | 1.619 | **1.609** | 1.748 | 1.740 |
| `semiarid_sahel` | 1.029 | **1.025** | 1.097 | 1.093 |
| `tropical_amazon` | 1.027 | **1.023** | 1.034 | 1.031 |

## 5. The findings

**1. gpS is real, C-faithful, and lowers F's GPP at every one of the five cells — the direction was
predicted before the arm ran and is structural.** With `adtmm` near-linear in `apar` the two numerators
agree and the ratio of the two `gp_stand`s is `≈ 1/φ̄ ≥ 1`, so F's `demand`, `gc`, `gpd`, `fac` and hence
its solved λ are all biased HIGH on any partial-leaf day. Measured: 5 of 5 negative. **It improves the
kernel error on every aggregate** (5-cell 0.1538 → 0.1365; 4-cell 0.0741 → 0.0643) and takes Hainich's
excess from **+10.1 % to +4.5 %** — a little over half of ADR 0130's headline target, from a basis fix
with no new physics and no parameter.

**2. Its magnitude ranking was predicted too, and it is the mechanism's own fingerprint.** `|d%|`
smallest first: `semiarid_sahel` < `tropical_amazon` < `mediterranean_iberia` < `temperate_hainich` <
`boreal_siberia`. `gp_stand` can only reach GPP where `gc` is **conductance**-limited; at the driest cell
`gc` is set by supply and the flag moves only `demand`, which is why the Sahel is −0.10 %. The Amazon is
next because its canopy is nearest full leaf all year, where the flag is an exact identity.

**3. ⚠ gpS OVERSHOOTS at `boreal_siberia` — 1.044 → 0.935 — but ONLY on arm `A`, and that is a property of
arm `A`, not of the flag.** On the shipping configuration the same flag alone takes boreal **1.183 →
1.053**: a large improvement that never crosses 1. The reason is on record: ADR 0126 §"the parameters do
NOT all improve fidelity" measured that **boreal's agreement under beech parameters came from two wrong
parameters of opposite sign**, so arm `A`'s boreal 1.044 is a compensating-error baseline and any faithful
fix scored against it will look like an overshoot. **Score a faithfulness fix on the most faithful
configuration available, not on the historical control arm** — this is the same trap as ADR 0126 §5, one
level up: not a confounded arm, but a confounded *reference*.

**3b. On the shipping configuration gpS improves EVERY cell and every aggregate**, by a lot: 4-cell mean
`|GPP F/C − 1|` **0.0824 → 0.0328** (−60 %) and 4-cell mean `|bmi F/C − 1|` **0.1266 → 0.0535** (−58 %),
with per-cell GPP ratios 1.183→1.053, 1.091→1.030, 1.619→1.609, 1.029→1.025, 1.027→1.023. It is the best
arm in the table on all four aggregate columns. On this basis Hainich's GPP excess goes **+9.1 % → +3.0 %**.

**4. ★ vmG is C-faithful and moves the target statistic AWAY from the C at all five cells (+0.7 % to
+9.1 % on GPP).** No sign was predicted — deliberately, because the sign is conditional twice over — and
the measured sign is the opposite of the one the "the C bisects against a larger Vcmax" reading suggests.
The reason is measurable and not subtle: **the layered absorbed fraction `fpar` EXCEEDS the crown-cover
`fpc` in a real stand** (0.282 vs 0.151 for the dominant stem of the unit-test roster), because the
layered integration shares ALL the light the stand absorbs among the stems by leaf area while `fpc`
saturates per crown. So the C's `gp_sum` Vcmax is the SMALLER one, `adtmm(λ)` in the residual is smaller,
and the root of `fac·(1−λ) − adtmm(λ)` moves UP. The pre-registered sub-prediction `|vmG| < |gpS|` is
**REFUTED at 3 of 5 cells**.

**5. What (4) means, and it is the scientifically load-bearing part.** The C is the oracle. A change that
makes F's code MORE faithful and its agreement WORSE is evidence of a **compensating error elsewhere in
the kernel** — i.e. **F's true tree-photosynthesis error is LARGER than the measured `GPP F/C`**. This is
now the third independent term to say so: ADR 0135 §3 found the same for the `phen`-inside-the-extinction
placement and the missing `(1−snowcover)` factor, both of which make F absorb LESS PAR while its GPP is
measured above the C's. Four terms, all pointing the same way, and each of them individually faithful.
**Stop reading `GPP_F/GPP_C` as the size of the kernel error; read it as a lower bound.**

**6. The two flags are NOT additive and must be read jointly.** Both act on the same λ solve. At Hainich
`−5.10 + 1.07 = −4.03` against a joint `−3.93`; at `mediterranean_iberia` `−3.21 + 7.56 = +4.35` against a
joint `+4.65`. Close, but neither exact nor guaranteed — the joint arm is the one to quote.

**7. ⚠ On arm `A` the JOINT arm looks best on the published assimilate statistic** (`|bmi F/C − 1|`
0.1441 → **0.0956** over the two readable cells) **and that is a cancellation, not a fix** — gpS's arm-`A`
boreal overshoot and vmG's upward push offset each other there. On the shipping configuration, where
neither error is present, the joint arm is **worse than gpS alone on all four aggregates** (4-cell bmi
0.0535 → 0.1147). An arm that wins by cancelling two errors of opposite sign is exactly what ADR 0174 §3b
warns a symmetric diagnostic cannot see; here the two bases disagree about which arm is best, and the
faithful one is the tiebreak.

## 6. What this does NOT establish

* **The incidence is not measured.** These are the incidence-weighted products of a per-day effect and the
  number of partial-leaf tree-days each cell has, and the latter needs an accumulator inside
  `daily_step_canopy` (a struct on the Enzyme path — ADR 0110's SIGABRT trap). So a small number at a cell
  does not separate "the mechanism is small there" from "that cell is evergreen" (ADR 0134's `CAN BIND`
  distinction). Both flags are exact identities at `φ ≡ 1`.
* **Nothing coupled.** Every number here is rung 3 (F alone, restarted from the C's own roster each year).
  The coupled consequence is unmeasured, which is half of why neither default is flipped.
* **`mediterranean_iberia` remains uninterpretable at the level** — its 1.47–1.74 GPP ratio is dominated by
  that cell's own growth error, which is why it is excluded from the 4-cell aggregate rather than averaged.

## 7. Pre-registered flip criteria (guardrail 4's corollary — an opt-in whose default is known wrong is a defect on a timer)

**gpS (`gp_stand_leafon_basis`) — a live flip candidate, and conditions 1–2 are ALREADY MET.** The
criterion below was written into this ADR **before** the `Pgbggs` arm finished, and its justification
(score a faithfulness fix on the configuration a flip would ship into, one variable at a time) does not
depend on the result — ADR 0104's test for a legitimate yardstick. Flip the default to `true` when:

1. measured on the **shipping configuration** (`Pgbgg`: per-PFT parameters + the tree demand gate + the
   prognostic below-ground pool) with **gpS alone** — arm `Pgbggs`, which exists for this purpose — the
   4-cell mean `|GPP F/C − 1|` **and** the 4-cell mean `|bmi F/C − 1|` both fall.
   **→ MET: 0.0824 → 0.0328 and 0.1266 → 0.0535** (and both 5-cell means fall too).
2. `boreal_siberia`'s own `|GPP F/C − 1|` does not exceed its arm-`A` value of 0.044 by more than the
   cell's own noise floor (ADR 0093 §5(a): `vegc` bootstrap CV **11.3 %** at `npatch=25`) — i.e. finding
   3's overshoot must not be a per-cell regression outside the target's own scatter.
   **→ MET on both readings**: as literally written (cross-basis) 0.053 against a bar of 0.044 + 0.113 =
   0.157; on the like-for-like same-basis reading it is an improvement, 0.183 → 0.053. Finding 3 shows the
   arm-`A` overshoot does not exist on the shipping basis at all.
3. **STILL OPEN** — the default must be flipped **ALONE**, with the full suite's failure list enumerated
   as the measured blast radius (the `julia-test` skill's default-flip procedure; the last four flips moved
   3–5 assertions), every moved baseline regenerated by a harness that reproduces the OLD numbers in the
   same run, and every control arm that means the OLD basis passing it explicitly rather than by omission
   (ADR 0133 §4). Guardrail 4 is then re-served through the opt-out.

⚠ **Condition 3 is the whole remaining cost and it is not a formality** — ADR 0133 found four probes whose
control arms the tree-gate flip would have silently relabelled. This flip is line M's own next action, named
in `lines/M/STATE.md`; it is deliberately NOT bundled into this ADR, whose deliverable is the measurement.

**vmG (`lambda_vm_gp`) — NOT a flip candidate, and this is a real block, not a deferral.** It is
C-faithful and it makes agreement worse at 5 of 5 cells. Flipping it is correct only once finding 5's
compensating error is found, because until then the flip trades a known faithfulness gain for a measured
fidelity loss with no account of what pays for it. The flag exists so that the compensating-error search
has the faithful arm available as a control.

## 8. Consequences

* Two new `WaterParams` fields, both `false`; scope is `daily_step_canopy` only, like the two demand
  gates. The single-individual `daily_step`/`daily_step_ml` kernels are byte-identical either way.
* Suite **275 621 pass / 0 fail** with no committed baseline moved (guardrail 4 discharged by the
  defaults, verified rather than asserted).
* `test/testitems/gpsum_basis_tests.jl` pins the mechanism: the two exact-boundary identities (`φ ≡ 1` for
  gpS; `φ ≡ 1` **and** `fpar ≡ fpc` for vmG) **bitwise**, each with a matched "the flag actually fires"
  partner so a green identity can never be an inert code path (ADR 0048 §3), plus the signed direction for
  gpS at three `φ` values. **No sign is asserted for vmG** — the test says so and why.
* `test/testitems/references/M_growth_channel_decomposition.csv` gains six arms
  (`Agps`/`Avmg`/`Agv`/`Pgbggs`/`Pgbggv`/`Pgbgg2`) as **new rows only**: 30 lines added, **0 pre-existing
  lines changed or removed**, checked by diff against the pre-edit file (ADR 0060's additive rule).
* ADR 0135's photosynthesis shortlist loses item (a) as an open question and keeps items (b) the
  `tstress < 1e-2` hard zeroing and (c) the phenology trajectory. Finding 5 raises the priority of both,
  since the kernel error they are aimed at is now known to be larger than the ratio that measures it.
