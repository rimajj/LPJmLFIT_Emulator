# 0176 — rung-2 arm S at Hainich: the learned demography inside FIT's own physics beats the shipped uniform thinning decisively, but ~85 % of that advantage is the INTERFACE (not overriding deaths FIT had already settled), not trait ordering

* Status: accepted
* Date: 2026-08-12
* Line: S (tier-3 block 0170–0189)
* Supersedes: nothing. **Delivers the falsifiable measurement ADR 0175 §3 promised** and answers the first
  item of that ADR's handoff (run the arms, check the null first). **Narrows the reading of ADR 0124**: arm
  C's `trait_mortality`-vs-uniform contrast is reproduced here with the LEARNED count target, and is here
  decomposed into two effects arm C could not separate.
* Scope, mandatory with every number below: **ONE cell of 54 020** (Hainich, 42490), **historic 2000–2019
  only**, 25 patches, 500 patch-years per run, establishment deferred to the C in every arm. **Nothing here
  is a warming-response result** — see §6.

---

## 1. What was run

`scripts/rung2_s_demography_harness.jl` serves the production count DRF's decision into LPJmL-FIT's own
daily physics at each patch-year rendezvous, with `ρ` taken from a feature row built off the C's live roster
(`--n-prev=roster`, the ADR-0175 fix). Four arms, each 1 task, ~12 s, `lpjml rc=0` in all 17 runs:

| arm | count target | who dies |
|---|---|---|
| `NP` | ρ = 1 (persistence null) | nobody |
| `S0` | learned | uniform: `f_i = ρ` for every tree — **the shipped operator** |
| `S0h` | learned | uniform **among the non-certain**, `f_i = 0` where FIT's own `mort ≥ 1` — **the decomposition control, new here** |
| `S1` | learned | `f_i = (1 − mort_i)^θ` — the trait-hazard ordering (`trait_mortality`'s shape) |

`S0h` exists because `S1` differs from `S0` in **two** ways at once and no statistic in ADR 0124 separated
them: the tilted survival function is zero wherever FIT's hazard is already certain, *and* it orders the
remaining stems by trait. `S0h` takes only the first and hits the same count target, so `S0h − S0` prices
the interface behaviour and `S1 − S0h` prices trait ordering.

Seeds: 5 for `S0`/`S0h`/`S1`, 2 for `NP`. **`NP` is seed-independent by construction** (`rand` is reached
only inside `if ρ < 1.0`, which `NP` never enters) and this was verified, not assumed: its two runs give
**identical** terminal counts and bit-identical `mort`-phase rosters.

## 2. THE PRE-REGISTERED CHECK PASSES — the persistence null does NOT tie the arms

This had to be read before anything else (ADR 0112 showed a persistence null matching the production model
on *every* response statistic OFFLINE; had it tied here too, no number from this harness would mean
anything).

    terminal stems 2019, the C itself = 365
      NP   658.0 ± 0.0     1.803 × the C
      S0   544.0 ± 12.5    1.490 ×
      S0h  397.4 ± 16.4    1.089 ×
      S1   375.2 ± 24.3    1.028 ×

`NP` is 21 % above the worst learned arm with **zero** seed spread. ⇒ **the harness has power the offline
basis did not**, and the arms below are measurements rather than restatements of their input.

## 3. The result, and the decomposition that is the actual finding

|  | terminal stems (ratio to C) | realized selection differential (ratio to C) | terminal age structure `<20 / 20–40 / ≥40` |
|---|---|---|---|
| **the C itself** | 1.000 | 1.000 (+35 376 gC/m³) | 118 / 120 / 127 |
| `NP` | 1.803 | 2.201 | 174 / 241 / 243 |
| `S0` **(shipped)** | 1.490 ± 0.034 | 0.390 ± 0.081 | 224 / 166 / 154 |
| `S0h` | 1.089 ± 0.045 | 1.126 ± 0.041 | 158 / 118 / 122 |
| `S1` | **1.028 ± 0.067** | **0.965 ± 0.093** | 142 / 114 / 119 |

**a. The shipped uniform thinning is the worst non-null arm on every statistic.** It ends 49 % over the C's
stem count, its realized selection differential is 0.39 × the C's (it kills *too little* of the dense-wood
tail), and it hands back a stand skewed young — 224 stems under 20 years against the C's 118, while holding
154 of the C's 127 mature ones.

**b. The mechanism is visible in the C's own audit, and it is not subtle.** Summed over 500 patch-years,
`S0` **spares 1 952 trees the C's own hazard was certain of** (`mort_prob ≥ 1`); `S0h` spares 370 and `S1`
358. A uniform `f_i = ρ ≈ 0.9` gives a tree FIT had already condemned a 90 % survival chance. That is what
inflates the stand, and it is a property of the *operator's shape*, not of the count target — which is
identical in all three arms.

**c. The decomposition. Most of what looks like "trait selection works" is the interface:**

| error against the C | `S0` | `S0h` | `S1` | removed by the interface | removed by trait ordering |
|---|---|---|---|---|---|
| terminal-count \|ratio − 1\| | 0.490 | 0.089 | 0.028 | **0.401 (87 %)** | 0.061 (13 %) |
| selection-differential \|ratio − 1\| | 0.610 | 0.126 | 0.035 | **0.484 (84 %)** | 0.091 (16 %) |

Welch on the arm pairs (5 seeds each): `S0 → S0h` is **t = 15.9** on counts and **t = −18.2** on the
selection differential — decisive. `S0h → S1` is **t = 1.69, df 7.0 on counts (NOT resolved at 5 seeds)**
and **t = 3.54, df 5.5 on the selection differential (resolved, and in `S1`'s favour** — `S0h` overshoots to
+1.126, `S1` lands at 0.965).

**d. Trait ordering contributes nothing measurable to the age–wood-density gradient at this cell.** The
per-PFT Spearman against the recorded baseline is **identical between `S0h` and `S1`** — 0.400 / 1.000 /
0.943 / 0.600 / 0.500 for PFT ids 1–5 — and both reproduce the C's own age-bin *extent* (4 bins for id 4,
3 for id 5) where `S0` and `NP` retain stems in older bins the C does not have. The one place `S1` is alone
is composition: it matches the C's PFT set exactly, while `NP`, `S0` and `S0h` all carry a sixth PFT
(larch) the C does not.

## 4. What this does and does not say about flipping `trait_mortality`

**Supports the operator's shape.** On both headline statistics `S1` is the closest arm to the C, and it is
better than the shipped operator by a margin no seed ensemble confuses (t ≈ 14–18). ADR 0049's flip
criterion is an OFFLINE improvement the operator cannot demonstrate — offline it has neither of FIT's stress
integrals (ADR 0174 §4) — and this is the second independent measurement *inside real physics* pointing the
same way as arm C's (ADR 0124: terminal 1.050 vs 1.209, selection 0.952 vs 0.241).

**But it does not establish the coupled flip, and the reason is specific.** ~85 % of the advantage measured
here comes from zeroing survival on stems whose hazard is **FIT's own `mort ≥ 1`**, read off the C's roster.
In the coupled emulator there is no C hazard — `trait_mortality` uses the **ported** one, which ADR 0174 §4
records as lacking FIT's running water-stress and growth-failure integrals, i.e. exactly the inputs three of
the four death rates depend on. **Whether the port reproduces FIT's certain-kill SET is therefore the thing
the flip actually rests on, and it has not been measured.**

⇒ **`trait_mortality` stays off for now, on a NEW and much narrower blocker than ADR 0049's** — not "it
cannot be shown to help", but "the part of it that demonstrably helps is not yet shown to survive the port".
**Pre-registered flip criterion, replacing ADR 0049's:** on ≥ 12 named cells, the ported hazard's certain
set (`mort ≥ 1`) against FIT's own on the **same** rosters must reach recall ≥ 0.8 with precision ≥ 0.8; the
harness already sees both, so this costs one comparison pass and no new run. If it passes, flip; if it
fails, the finding is that the port's hazard needs the stress integrals before its ordering is worth
anything, and that is a rung-2 work item, not a flag decision.

## 5. The `NP` determinism check, and a process note against myself

The two `NP` runs are **identical in every initialised column** over 55 546 tree records —
`scripts/diagnose_rung2_dump_equality.py`, exit 0. That is the rigorous form of §1's seed-independence
claim, and it is what licenses reporting `NP` on 2 seeds beside the others' 5.

The columns it excludes are **already-known** uninitialised memory, not a finding of this ADR: `sapwood_old`
(a dead struct field, garbage in every phase and year) and the five `mort_*` columns for any tree not yet
through `mortality_tree_ind` — every tree at the first `pre` after a restart, and every recruit at the
`post` of its own establishment year. Recorded in ADR 0061/0121 and the `lpjmlfit-cbinary` skill, with that
script written for exactly this comparison. The measured pattern here reproduces it precisely (`sapwood_old`
in all four phases; `mort_*` in `pre` and a handful in `post`; **zero** in `grow` and `mort`).

**Process note, worth more than the numbers:** I hand-rolled this column comparison before checking the
skill, which already named both column groups *and* the script. The skill was right and the hand-rolled
version had to be thrown away. The standing rule — consult the matching skill before doing a mechanical
task by hand — earned its place again here.

Why it does not touch any arm above: `diagnose_rung2_armc.py::read_dump` scores the **`mort`** phase, and
the rendezvous request the harness answers is written from the **`grow`** phase records
(`lpjmlfit_rung2_hook_v6.patch`: "the same point as its `grow` phase"). Both are clean. But any future arm
that scores a hazard off the `pre` phase would be reading noise.

## 6. What is NOT measured here

* **The warming response — the actual deliverable.** Every number above is historic-only and is a LEVEL
  statistic. ADR 0174's rung-1 verdict (level passes, response fails on sign) is untouched by this ADR.
  The response needs the scenario PAIR per cell with a `MODE=record` baseline for each, per ADR 0041.
* **Anything beyond one cell.** ADR 0172 §5's bar is ≥ 12 cells with a reported Cochran's Q; this is 1.
* **Recruits.** Establishment defers to the C in every arm, so `nrec ≡ 0` by construction.
* **θ is small and the target often binds.** `S1`'s median θ is 0.19–0.35 with **shortfall > 0 in 132–148
  of 500 patch-years** — in ~28 % of patch-years the certain kills alone overshoot the learned target, so
  the ordering had no room. ADR 0117 item 6.i requires this be quoted beside the result.
* The C binary defers its demographic kills under either rung-2 env var (ADR 0123): mathematically inert,
  worth 0.05 % of stem-years over 20 yr, and a departure from stock LPJmL-FIT.

## 7. Changes

* `scripts/rung2_s_demography_harness.jl` — the `S0h` arm.
* `scripts/diagnose_rung2_armc.py` — auto-discovery of the S-arm dump family (`--glob`), and the harness-log
  reader is now **header-driven**. It was positional, and the two harnesses do **not** share a column order
  (arm C's field 4 is `rho`, the S arm's is `n_emit`), so scoring an S arm with it would silently have read
  another arm's columns — the same class of basis bug as the three ADR 0175 §B records.
* No `src/**` change, no default moved, no committed baseline regenerated.
