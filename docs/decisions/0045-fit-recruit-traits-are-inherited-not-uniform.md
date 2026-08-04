# ADR 0045 — LPJmL-FIT's recruit traits are INHERITED from the live community, not uniform draws

* **Status:** Accepted
* **Date:** 2026-08-04
* **Line:** S (Component-S science) · ADR block 0030–0049
* **Supersedes:** the `CLAUDE.md` §3 claim that "traits are drawn **uniformly** from per-PFT
  `[low,high]` intervals (`new_tree.c:195-206` / `getrndinterval`; the par `median` field is unused
  there), so any per-cell trait statistic is a *composition* statistic" — **true only of the
  background channel, which is the minority one.** Also supersedes ADR 0042 §9's framing, which
  corrected the composition reading by adding within-PFT *selection* but still treated the recruit
  **prior** as uniform.
* **Corrects a load-bearing docstring:** `scripts/build_slow_runtime_table.py:293-294` and `:370-371`
  both assert "mortality is trait-blind ⇒ community dist == establishment dist" as the justification
  for (a) training the copula on the **survivor** marginal and (b) `STEM_CAP` being harmless.
* **Related:** ADR 0025 (the recruit-trait copula and its conditioning contract), ADR 0044 (the
  response instruments), ADR 0046 (the measured decomposition of the shift)

## Context

The recruit-trait copula (ADR 0025) models establishment as a function of environment. Its design
rested on FIT drawing recruit traits uniformly from per-PFT intervals, independent of the standing
stand — which is why ADR 0025 §4 could argue that conditioning recruits on the stand's own state
"would be a feedback loop" and exclude all seven stand-state features from `live_flux_cond`.

## Decision — record the mechanism as it actually is

`[VERIFIED 2026-08-04]` against `/home/jamirp/lpjml56fit`, every claim at the file:line given.

### 1. Inheritance is ON, and it is on in EVERY transient year, under BOTH config branches

`lpjmlfit.js:35` `"inheritance": true`. The gate that selects the uniform ("everything is
everywhere") branch is `establishmentpft_ind.c:99`:

```c
if(!config->inheritance || year < config->firstyear - config->nspinup + config->inherit_startyear
   || patch->stand->cell->treelen == 0)   /* everything is everywhere */
```

`lpjmlfit.js` carries two branches and **the conclusion is the same in both**, which is stronger than
depending on which is compiled:

| branch | `nspinup` | `firstyear` | `inherit_startyear` | threshold year | transient years ≥ 2000 |
|---|---|---|---|---|---|
| spinup (`:256,258,37`) | 1000 | 1901 | 200 | **1101** | past it ⇒ inheritance |
| from-restart (`:268,270,39`) | 0 | 1901 | 0 | **1901** | past it ⇒ inheritance |

`treelen > 0` is restored from the restart file, so the third clause does not fire either.

### 2. Establishment is a two-channel mixture with a CLOSED-FORM weight

* **Inheritance** (`establishmentpft_ind.c:124`): rate `param.k_est_inherit` = **0.02**
  (`par/lpjparam_fit.js:18`), one Poisson draw for the whole cell, `addpft(..., inherit=TRUE)`.
* **Background** (`:102`): rate `param.k_est_inherit_bg` = **0.005** (`:19`), **per eligible PFT** —
  this is the uniform `getrndinterval` channel `CLAUDE.md` described.

Both are `poidev(rate · param.patcharea · f_sap(patch->fpar_leafon_grass, α))`. `f_sap` (`:24-32`)
returns `pow(fpar, α)` and depends on **nothing else**; the inheritance branch passes
`param.alpha_r` = 2.0 (`par/lpjparam_fit.js:20`) and the background branch passes `treepar->alpha_r`
= `ALPHA_R` = 2.0 for **all seven** tree PFTs (`par/pft_lpjmlfit.js:111,231,363,491,621,751,881,1013`).
`patcharea` is shared. **So `f_sap` and `patcharea` cancel exactly** and the mixture weight is exact,
not approximate:

> **`w_inherit = 0.02 / (0.02 + 0.005·n_elig) = 4 / (4 + n_elig)`**

with `n_elig` = the number of tree PFTs passing `establish()` in that cell-year. **≈ 44 % inherited at
Hainich (~5 eligible), ≈ 80 % at Amazon/Sahel (a single eligible tree id).** Inheritance is the
MAJORITY channel wherever diversity is low.

### 3. The inheritance kernel is a reflected multiplicative random walk on the parent's trait

`new_tree.c:38-61` `draw_new_trait`:

```c
s = gasdev(seed);  if(s > 5.0) s = 5.0;  if(s < -5.0) s = -5.0;
if(trait_min == trait_max) return trait_old;
trait_new = trait_old * (1 + corridor*s);
if     (trait_new < trait_min) trait_new = trait_min + (trait_old - trait_min)*erand48(seed);
else if(trait_new > trait_max) trait_new = trait_old + (trait_max - trait_old)*erand48(seed);
```

`corridor` = `INHERIT_CORRIDOR` = **0.1** (`par/pft_lpjmlfit.js:101`), applied to every axis. The
recruit's **PFT id is the parent's** (`new_tree.c:131`). The parent is drawn from `cell->treelist`, a
rolling **seedbank** of the top-AGB trees, `param.max_age` = **50** yr (`par/lpjparam_fit.js:21`),
refreshed **every year** (`update_annual.c:75-77` — `getsapling.c`'s "called every five years" header
comment is stale), threshold `getmaxagb(stand, n_max·npatch·patcharea/100)`.

**Therefore the establishment marginal is a functional of the live community, and FIT's establishment
IS the feedback loop ADR 0025 §4 excluded on principle.** No stationary environment-conditioned
artifact can represent it exactly.

### 4. `[MEASURED]` But this is a LEVEL/structure defect, NOT the warming-response lever

This is the part that decides priority, and it goes against the reading the mechanism invites. From
ADR 0046's global census (job `1694062`/`1693988`), the youngest emitted age class (`Age < 10 yr`,
the closest observable proxy for the entry marginal) **barely moves between the historic and ssp370
blocks**:

| PFT | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|---|
| Δ mean `Wooddens`, `Age<10` | **−9227** | +854 | +278 | +981 | +4599 | −684 | +528 |

Five of seven move by under +1000 against a within-PFT shift of +1951.7 per cell, and the largest PFT
by stem count moves **downward**. Meanwhile the `Age≥10`/`Age≥20` classes move up several times more
(Type 3 +7035/+10035, Type 5 +4515/+9559). **So the entry marginal is close to static under warming
and the shift is generated after establishment.** Consequences:

* **Porting the inheritance operator is DEPRIORITISED as a response fix** (the plan's "Rung B"). It
  remains the correct model of establishment and is the right long-run structure, but it cannot be
  credited with closing the damping and must not be justified on that basis.
* The trait-blind premise in `build_slow_runtime_table.py:293-294` is **false as stated**, and
  separately its *conclusion* (train on survivors) is now known to be load-bearing for a different
  reason: the survivor marginal already contains the age–trait gradient that the emulator cannot
  generate. Fixing the premise text without fixing the mechanism would make the pipeline worse.
* `:370-371`'s use of the same premise to argue `STEM_CAP` is harmless ("patch-years within a cell are
  exchangeable") is **not supported** — patch-years differ in age structure, which is exactly the axis
  the shift rides. This is an additional, independent reason to land `CAP_HASH_SEED`.
* Any statement of the form "the per-cell trait statistic is a composition statistic" is wrong in
  **two** ways now: within-PFT selection (ADR 0042 §9) **and** the inherited, community-dependent
  prior recorded here.

## Consequences

* `CLAUDE.md` §3's uniform-recruit-draw bullet is corrected in the same commit as this ADR.
* ADR 0025 §4's "feedback loop" argument is **factually inverted** — the loop is in the C. It is not
  reopened here: excluding stand state from `live_flux_cond` may still be the right *engineering*
  choice (teacher-forcing fragility, and `n_prev`'s exposure-bias precedent), but it can no longer be
  defended as fidelity to FIT. Any future revisit cites this ADR, not the original reasoning.
* The `.rcop` `training_target` guard proposed for a survivor→entry retrain is **not** made obsolete by
  §4; it is simply no longer urgent, because the retrain it protects is deprioritised.

## Alternatives rejected

* **Treating the two channels as one effective uniform draw.** The weight is 44–80 % inheritance, and
  the kernel is a reflected multiplicative walk whose stationary distribution is not the uniform prior
  — so "effectively uniform" is quantitatively wrong wherever it matters most (low-diversity cells).
* **Leaving `CLAUDE.md` as-is with a footnote.** The claim is used to justify calling per-cell trait
  statistics composition statistics, which propagated into two ADRs and a pipeline docstring. It needs
  replacing, not annotating.
