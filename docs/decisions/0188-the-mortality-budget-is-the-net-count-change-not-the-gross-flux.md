# 0188 — The mortality budget is the NET count change, not the GROSS flux: FIT replaces 4.6–6.5 %/yr of its roster by recruitment, so a count target hands the operator ~1 %/yr where the flux is ~6 %/yr — and the non-negotiable deaths alone overdraw that budget 4–5×

* **Status:** accepted
* **Date:** 2026-08-13
* **Line:** S · ADR block 0170–0189 (tier 3)
* **Answers:** **ADR 0187 §B** — the promoted next action ("the discretionary mortality RATE, starting with
  ρ's population mismatch"). The mechanism is identified, sized, and sufficient.
* **Refutes:** **ADR 0187 §B's FIRST HYPOTHESIS** — that a ρ derived on the emitted population
  "under-kills the whole roster by exactly that ratio". It does not, and the refutation is derivable from
  the harness's own algebra rather than measured. See §2.
* **Does NOT disturb:** ADR 0187 §§1–3 (the kill set is not size-biased; the shortfall is the rate) — this
  ADR supplies the *cause* of that rate shortfall. ADR 0183 (the hazard is exact as a function; this is
  about its BUDGET, not the function). ADR 0186 §8.8's closure of the emitted stand *count* — §6 states
  precisely why this is not a re-opening of it. ADR 0181 §§4–5's "do not start a target redesign" — §7.
* **Evidence:** `scripts/diagnose_rung2_kill_budget.py`, SLURM job **1788038** (panels A–D from the arm
  logs, ~170 kB per leg; panel E a 1.9 GB scan of the 24 `REC` `predict` dumps). Log
  `logs/S-killbudget3.1788038.out`. **No model run.** 12 cells × 2 legs behind ADR 0185 §5's own
  completion+coverage gate, imported rather than re-implemented.

## 1. The question

ADR 0187 established that the emulator kills the right *kinds* of trees and far too few of them: on the
discretionary population FIT kills **2.1 %** of stems per year against `S1` **0.6 %** and `S0h` **0.5 %**,
uniformly across every height quintile, removing **58 %** of the annual biomass FIT removes. It promoted
the question *why*, and named a first suspect: ρ is `clamp(target/n_prev, 0.7, 1.3)` with `target`/`n_prev`
on the **>5 m emitted** population while the thinning `rand(rng) > f[i]` is applied to **every tree in the
roster**.

Three candidate mechanisms were pre-registered in the scorer's header before any number was read, each
with what it must return. All three are answerable from state already on disk.

## 2. H1 — the population mismatch: REFUTED, by algebra and by a derivable self-test

**The roster/emitted ratio is large** — median `n_tree/n_emit` = **2.08–2.92** across arms and legs, well
above the 1.9× line M's ADR 0130 measured at Hainich. So the suspicion was well aimed at a real disparity.

**But ρ is a FRACTION, not a count quota, and a fraction is scale-free.** The harness applies it against
the whole-roster density `n_now = sum(nind)` over ALL trees
(`rung2_s_demography_harness.jl:521-527`; for `S1`, `_hazard_tilt(haz, tp, ρ*n_now, n_now)`). The absolute
budget `(1−ρ)·n_now` therefore already scales WITH the roster; nothing carries the emitted count over into
an absolute quota.

**The derived a-priori gate that settles it.** For the uniform arm `S0`, `f[i] = ρ` for every tree, so
`E[n_kill] = Σ_i (1 − f_i) = (1−ρ)·n_tree` **exactly**. If H1 held, the realized rate would sit a factor
`n_tree/n_emit` BELOW its own implied quota:

| leg | H1 requires | measured realized/implied | SE | σ | verdict |
|---|---|---|---|---|---|
| historic | 0.425 | **1.004** | 0.009 | 0.51 | H1 **refuted** |
| ssp370 | 0.400 | **1.006** | 0.007 | 0.84 | H1 **refuted** |

The quota is spent in full. The same gate validates the column reading, and the null is free: `NP` sets
ρ = 1.0 unconditionally, so its ρ≥1 incidence must be **100.0 %** and its kill rate exactly **0.000 %** —
both returned. Pass band (3 σ) and the SE were fixed before the run and not moved (ADR 0187's clause).

**The clamp is also not binding**, as ADR 0187 §B assumed but had not checked: the ρ ≤ 0.7 bound fires in
**0.00–0.25 %** of patch-years, the ρ ≥ 1.3 bound in 0.00–0.81 %. One grep, assumption discharged.

## 3. H2 — in 42–46 % of patch-years the operator nominates NOBODY

The entire decision is wrapped in `if ρ < 1.0 && !isempty(trees)` (harness :521). When the count model
predicts the stand grows, the arm's answer is an **empty kill list** — not a small one.

| arm | leg | ρ ≥ 1 share | SE | nominated %/yr | θ == 0 |
|---|---|---|---|---|---|
| `NP` | both | 100.0 % | 0.000 | 0.000 | — |
| `S0` | ssp370 | 42.4 % | 0.019 | 0.809 | 0.0 % |
| `S0h` | ssp370 | 45.8 % | 0.018 | 4.270 | 0.0 % |
| `S1` | ssp370 | **46.2 %** | 0.018 | 4.283 | **27.9 %** |

And in **27.9 %** of `S1`'s patch-years the tilt solver returns **θ = 0** — `_hazard_tilt`'s own reported
give-up (`slow.jl:929-933`): the certain kills alone have already reached the count target, so every
non-condemned tree is spared. Nearly half the years have no discretionary mortality by construction, and a
quarter of the rest have it explicitly switched off.

⚠ **`S0h` reaches the same state unlogged.** Its `c = clamp(ρ*n_now/n_free, 0, 1)` hits 1.0 under exactly
the same condition, but its `shortfall` column tests a *different* one (`ρ*n_now < n_cert`) and so reports
**0.0 %**. `S0h`'s starvation is real and invisible in its own log. Do not read that 0 % as "no override".

## 4. H3 — the budget is the NET count change; the flux it must produce is the GROSS

ρ ≈ `n_next/n_now`, so `(1−ρ)·n_now` approximates **K − R** (kills minus recruits) — the *net* count
change. The flux that moves biomass is the *gross* **K**. Establishment is deferred to the C
(`ESTAB_C`; `n_recruit = 0` by construction, harness :573), so R arrives regardless of what the operator
answers.

FIT's own side, from the `REC` dumps, as % of roster per year (12 cells):

| leg | gross K | of which certain | of which discretionary | recruits R | net = R − K |
|---|---|---|---|---|---|
| historic | **5.651** | 3.523 | 1.884 | **4.619** | −0.537 |
| ssp370 | **5.961** | 3.976 | 2.049 | **6.456** | +0.254 |

FIT's roster is near-stationary in count (−0.54 / +0.25 %/yr) while turning over **~6 %/yr** — it kills
5.7–6.0 % and replaces 4.6–6.5 %. `K_disc` here (1.88 / 2.05 %) independently reproduces ADR 0187's 2.1 %
by a completely different route (a count identity over `grow`/`mort`/`post` rather than a stratified
selectivity statistic), which is the corroboration that the two scorers agree on FIT.

Against the operator's spendable budget `Σ max(0, 1−ρ)·n_tree / Σ n_tree`:

| arm | leg | FIT gross K | budget+ | FIT certain deaths | overdraw | gross/budget |
|---|---|---|---|---|---|---|
| `S1` | historic | 5.651 | 0.980 | 3.523 | **5.23×** | **7.57×** |
| `S1` | ssp370 | 5.961 | 0.891 | 3.976 | **4.32×** | **6.38×** |
| `S0h` | ssp370 | 5.961 | 0.900 | 3.976 | 4.54× | 6.77× |
| `S0` | ssp370 | 5.961 | 0.783 | 3.976 | 4.94× | 7.48× |

**H3 is confirmed, and the arithmetic closes.** The count-implied budget is **0.78–1.02 %/yr**, which is
FIT's *net* (~0.3–0.5 %/yr) to within the same order — and **6.4–7.6× smaller than FIT's gross mortality**.
The gap is FIT's recruitment, 4.6–6.5 %/yr, which the operator never sees. Worse, **FIT's non-negotiable
deaths alone are 4.1–5.3× the entire budget**, so the discretionary channel — the one carrying biomass — is
overdrawn before it is ever reached. That is what θ = 0 reports, and it is why the measured discretionary
rate lands at 0.5–0.6 % against FIT's 2.0 %.

## 5. Why this is a structural limit, not a tuning error

A mortality-only operator driven by a next-year **count** target cannot express gross mortality flux. The
target already has recruitment netted out of it, and recruitment is 78–108 % of mortality here. Two stands
with identical counts and wildly different turnover are indistinguishable to it — and FIT is the
high-turnover one.

This is the same shape as ADR 0132's trap in a different place: **a quantity defined as a year-over-year
difference of state cannot carry a gross flux.** The count target is such a difference.

## 6. What this does NOT re-open

**ADR 0186 §8.8 closed the emitted stand COUNT as an instrument, and that stands.** This ADR does not
propose a count-side instrument: not the level anchor, not a retrained count target, not a different
`n_prev` basis. The count is on FIT's number (ADR 0186: `S1` −2.9 %) and this ADR explains *why that is
compatible with a 4× mortality-flux shortfall* — because the certain deaths, which every arm honours by
construction, carry the count while the discretionary channel carries the mass.

**ADR 0181 §§4–5's "do not start a target redesign" also stands, and is about a different quantity.** It
established that the training target is not where the *warming response* is lost. This ADR is about the
*biomass level*, and its finding is not that the target predicts the wrong count — the count is right —
but that a count is **the wrong kind of question** to derive a mortality budget from. The fix that follows
is therefore not a retrained count target: it is giving the operator a second number.

## 7. The decision

**Record the mechanism; change no default, no flag and no `src/**` file in this ADR.** The next action is
pre-registered here with its lever stated and that lever's current size measured, per ADR 0186's clause:

**Give the operator the gross budget instead of the net.** The recruits are knowable at the rendezvous —
the C delivers them and the harness already sees the roster before and after — so the budget can become
`(n_now − target) + R̂` rather than `(n_now − target)`. **The lever's size is measured in §4: it is a
4.6–6.5 %/yr addition to a 0.78–1.02 %/yr budget, i.e. the budget grows 5.5–8.3×**, which is the right
order to close a 3.5–4.2× rate shortfall and a 58 % mass-flux shortfall.

⚠ **The one derivation to do BEFORE building it, because it can kill the idea:** R̂ for the *current* year
is not available at decision time — the rendezvous is at `grow`, establishment happens after `post`. So the
instrument must use a lagged or predicted R̂, and the pre-registration must state what happens when that
prediction is wrong. Derive whether a lagged R̂ still moves the blessed statistic before writing the arm.

**Pre-registered criterion (to be read once, thresholds not to be moved):** on the ssp370 leg at the
FIT-gain cells, the discretionary kill rate must reach **≥ 1.5 %/yr** (against FIT's 2.05 % and the current
0.6 %) AND the annual mass-removal fraction **≥ 0.025** (against FIT's 0.0306 and the current 0.0178), with
the agb departure falling below **+40 %** (ADR 0185 §7.5's number, unchanged). A rate that rises while agb
does not falls refutes §4's reachability reading. `S0` remains the derivable self-test arm.

## 8. Gotchas paid for here

* ⚠ **A GATE STRICTER THAN ITS OWN IDENTITY MANUFACTURES DOUBT ABOUT A SOUND NUMBER.** The recruit
  identity needs only *no stem removed* between `mort` and `post`, which holds at **30 300 of 30 300**
  patch-years. A first version also required `dead@post == dead@mort` and reported a **13.2 %** violation
  rate that was not a violation: **fire** flags further stems dead between the phases (ADR 0121),
  one-directional (`dead@post ≥ dead@mort` at 8100 of 8100, never below) and **14.1 %** on top of the
  demographic kills. Fire is not the demography interface's to own, so `K_all` is read at `mort`. State the
  identity, gate exactly it, and report the extra as information.
* ⚠ **IMPLAUSIBILITY OF A LEVEL IS THE TELL THAT CATCHES A BASIS ERROR A RATIO HIDES.** The naive
  `R = n_post − (n_grow − K)` assumes the killed stems are gone from `post`. Under ADR 0123's deferred
  kills they are still there, so it inflates R by exactly `K_all` — it returned FIT recruitment of
  10.5–12.6 %/yr and **sustained +4.6 to +6.5 %/yr roster growth over 81 years**, which would explode the
  roster by orders of magnitude. Every arm-to-arm *ratio* looked perfectly sane. The same discipline as ADR
  0184's "report the level beside every shift", used in the opposite direction: **sanity-check a level
  against what the system must do over its own horizon.**
* **`n_tree` and `n_emit` are BOTH in `s_arm_log.txt`**, so the whole population-ratio question needed no
  dump scan — 170 kB per leg, seconds. Third time the arm log has retired a planned scan (ADR 0184, 0186).
* ⚠ **`scripts/sbatch_python.sh` prints an empty `env:` line even when the knob DID propagate.** `NPREV`
  is not in the wrapper's forward list, but `export NPREV=predict` reaches the job through
  `--export=ALL`. The proof is the scorer's own header line (`mode NPREV=predict`), which is why every
  scorer in this family prints its mode — do not infer the mode from the wrapper's echo.
