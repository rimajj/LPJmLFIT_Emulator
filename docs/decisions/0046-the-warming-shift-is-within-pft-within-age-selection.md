# ADR 0046 — the wood-density warming shift is WITHIN-PFT, WITHIN-AGE-CLASS selection: trait-dependent mortality is the lever

* **Status:** Accepted
* **Date:** 2026-08-04
* **Line:** S (Component-S science) · ADR block 0030–0049
* **Decides:** the pre-registered Phase-1 kill switch for trait-dependent mortality (the plan's
  Phase 3A). **Verdict: BUILD IT.** Three independent measurements agree, and two competing
  explanations — PFT-composition turnover and age-structure shift — are quantitatively excluded.
* **Related:** ADR 0044 (the response instruments and frozen thresholds), ADR 0045 (recruit traits are
  inherited; the entry marginal is near-static), ADR 0025 (the copula's trait-blind-mortality
  compensation), ADR 0033 (the composition diagnosis that was previously falsified for the *level*),
  ADR 0042 §9 (within-PFT selection exists in the C source)
* **Evidence:** `scripts/diagnose_wooddens_shift_decomposition.py`, jobs `1693988` + `1694062`
  (exit 0), per-cell terms at `/p/tmp/jamirp/emulator_global/tables/wd_shift_d2/`

## Context

Component S damps FIT's per-cell wood-density warming shift by **39.9 %** (deployed ncond-8 arm,
`Rb` = −971.5 against `meanDobs` = +2432.9; ADR 0042 §5.1 — note ADR 0040's "−892 / 37 %" is the
**refused env arm**, not the deployed one). ADR 0044 established that the residual is a **placement**
error, not shrinkage: on the corrected reliability basis the deployed arm's shift amplitude is
`Ra` = **1.034** (`|Ra−1|` = 0.0344) while its pattern correlation is `Rr` = 0.3751 against a
**0.9543** ceiling — right-sized shifts in the wrong cells.

The candidate mechanisms implied different fixes, so the plan pre-registered a decision rule
(within-PFT share <15 % ⇒ the mechanism is dead; >40 % ⇒ it is the lever) **before** any measurement.

## Decision — the measured decomposition, and what it excludes

Basis: committed seed1 parquets, `Type ∈ TREE_TYPES` (imported, ADR 0031), `isdead == 0` for survivor
statistics (matching the copula's own `stem_filt`), **52 450 cells** with ≥20 survivor stems in both
blocks — the same universe as the response gate. Every streamed aggregate carries the ADR-0036 §5b
key-set assert (`n_unique(keys) == height`); none fired.

Reported on the per-cell **MEAN** basis, because only a mean decomposes additively. The per-cell
**MEDIAN** shift is **+2422.3**, reproducing ADR 0042's +2432.9 basis to 0.4 %; the mean shift is
**+3808.0**. Quote shares, not absolutes, across the two.

### 1. Not composition. Within-PFT dominates.

```
composition   SUM dw_p * Wbar_p^hist  =  +844.4    22.2 %
within-PFT    SUM w_p^hist * dWbar_p  = +1951.7    51.3 %
interaction   SUM dw_p * dWbar_p      = +1011.9    26.6 %
SUM                                   = +3808.0            closure residual -4.55e-13
```

**Within-PFT = 51.3 % > 40 % ⇒ the pre-registered rule returns "trait-dependent mortality is the right
lever."** The interaction term (26.6 %) contains within-PFT change too, so 51.3 % is a *lower* bound on
the non-compositional share. PFT turnover explains at most 22.2 %.

### 2. Not age structure either — and the age term has the WRONG SIGN

The age–wooddens gradient is steep and universal (§3), so a within-PFT mean can move with **zero**
change in selection, purely by the age distribution sliding along it. That alternative is separable and
was tested:

```
              dWbar_p    age-struct      %    within-age      %   interact      %
ALL         +19030.7      -2244.6    -11.8     +21322.4  +112.0      -47.2   -0.2
Type 3       +7399.9         +43.7     +0.6      +7298.5   +98.6      +57.7   +0.8
Type 5       +9232.7         -10.7     -0.1      +9342.3  +101.2      -98.9   -1.1
Type 2       +2586.7        +334.5    +12.9      +2163.7   +83.6      +88.5   +3.4
```
(stem-weighted, global — **not** commensurable with §1's per-cell +1951.7; read the shares.)

**The within-age-class term is 112 % of the total; the age-structure term is −11.8 %, i.e. it OPPOSES
the shift.** Stands get *younger* under warming — mean age falls in all seven PFTs (Type 1 49.5→46.7,
Type 3 42.4→38.9, Type 2 27.3→25.6) — which along a positive gradient pushes wood density *down*. The
observed increase happens **despite** the age structure, not because of it.

**Traits are immutable after `new_tree`, so a trait-mean increase at FIXED age can only be produced by
differential survival.** Therefore: **the selection intensity itself responds to warming.**

### 3. Corroboration — the age–wooddens gradient, and why the annual differential looks small

Mean survivor `Wooddens` by Age bin (historic; `<10 … ≥320` yr) rises steeply in every PFT:

| PFT | `<10` | `≥320` | Δ |
|---|---|---|---|
| 1 temperate NE | 184 869 | 331 234 | **+146 365** |
| 4 boreal NE | 146 894 | 288 121 | **+141 227** |
| 6 boreal NS | 138 072 | 268 630 | **+130 558** |
| 3 temperate BS (beech) | 217 954 | 262 019 | +44 065 |
| 0 tropical BE | 240 708 | 263 347 | +22 640 (non-monotone: peaks at `≥20`) |

This is the direct fingerprint of cumulative wood-density selection, and it is the **ID-free validation
target** for a ported mortality operator.

The one-year selection differential `S = mean(Wooddens | live) − mean(Wooddens | all emitted)` is by
contrast **small and mixed in sign** (−461.6 … +337.5 across PFTs). The two are consistent, not
contradictory: only **2.8–6.2 %** of stems die per year (`dead_frac`), so a ~0.1 %-per-year differential
compounds over centuries into the gradient above. Two things follow, and both matter:

* **`S`'s sign predicts the gradient's SHAPE per PFT.** `S` > 0 PFTs (1: +305, 4: +127, 6: +161) have
  steeply monotone gradients; `S` < 0 PFTs (0: −462, 3: −394) have non-monotone gradients that rise
  then fall. The measurements corroborate each other.
* **`S` < 0 for two PFTs means the `mort_max` advantage can be OUTWEIGHED.** Denser wood halves
  `mort_max` (`mortality_tree_ind.c:92`, ratio 1.765 between `wooddens` 2e5 and 3e5) but also grows
  more slowly, lowering `greff` and *raising* `mort_npp` through the logistic
  `mort_max/(1+0.2·exp(0.01·greff))`. **Net selection is a competition between the two and is not
  sign-definite.** A port must therefore reproduce the *whole* hazard, not the `mort_max` factor alone;
  a "denser wood survives better" shortcut would get Types 0 and 3 backwards.

`ΔS` (ssp − historic) is positive for 4 of 7 PFTs, largest for Type 0 (+450.3). `mort_*` are C outputs
and can **never** be emulator features — diagnosis only.

### 4. The emulator has exactly zero channel for this

`slow.jl:763-773` scales every tree cohort's `nind` by one `ρ`, which is **exactly
composition-preserving** — the community wood-density mean is invariant under it to floating point. The
only channels that move it are appended copula recruits (which carry no age–trait covariance) and the
k-cap merge (`slow.jl:441-445`, which inherits the *dominant* parent's trait). So the emulator cannot
produce the §3 gradient at all, and cannot respond to a change in selection intensity.

**That is the mechanism gap, and it explains the placement error of ADR 0044 §2**: the emulator gets the
shift's size roughly right by fitting an environment→trait conditional, but it cannot place the shift
because placement is set by where selection intensifies.

## Consequences

* **Phase 3A (trait-dependent mortality) is CONFIRMED and unblocked.** Its validation target is the
  §3 age–wooddens gradient, per PFT, including the non-monotone shape for Types 0 and 3.
* **Phase 3B (the inheritance operator) is DEPRIORITISED as a response fix** — ADR 0045 §4 measures the
  entry marginal as near-static under warming (five of seven PFTs move <+1000; the largest PFT moves
  *down* 9227). It remains the correct model of establishment; it is not the damping fix.
* **The pre-registered upper bound to quote is 51.3 %+ of the mean shift**, not "the 37 %/39.9 %
  damping". A mechanism that closes the within-PFT channel perfectly cannot address the 22.2 %
  compositional part.
* **`build_slow_runtime_table.py:293-294`'s "mortality is trait-blind" is false** (ADR 0045), and the
  survivor-marginal training it justifies is now understood to be load-bearing for a *different*
  reason: the survivor marginal already contains the age–trait gradient the emulator cannot generate.
  Fixing the docstring without the mechanism would make the pipeline worse, not better.
* **ADR 0025's compensation is confirmed as an equilibrium-only device.** Training on survivors makes
  the community converge to FIT's survivor distribution in a *stationary* regime; §2 shows the warming
  signal is a change in the selection operator, which no stationary target can carry.
* ADR 0030 criterion 2 (`sd_ratio ≥ 0.75`) and any lever justified by "reducing attenuation" remain
  aimed at a defect this emulator does not have (ADR 0044 §2).

## Alternatives rejected (on this evidence, not on argument)

* **PFT-composition / mixture copula (S3).** 22.2 % ceiling. Already de-prioritised for the *level* by
  ADR 0033; now excluded for the *response* too.
* **Age-structure shift along the existing gradient.** −11.8 %, wrong sign (§2).
* **Entry-marginal / inheritance shift.** Near-static (ADR 0045 §4).
* **Reading the pre-registered "lever confirmed" verdict off the 51.3 % share alone.** The automated
  rule fired on §1, but §1 cannot distinguish selection from age structure or entry — the corroborating
  measurements in §2 and §3 are what make the verdict sound, and the first-pass selection differential
  in §3 initially appeared to *contradict* it. The share alone would have been an unsafe basis.
