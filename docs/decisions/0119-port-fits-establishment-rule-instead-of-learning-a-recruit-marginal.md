---
status: "accepted"
date: 2026-08-11
deciders: "the OWNER (steer of 2026-08-11, quoted verbatim below) on the question of what to do; engineering agent, line S (standing autonomous delegation, STEERING_PROMPT) on how"
consulted: "ADR 0025 (the recruit copula and its §3 expiry condition + §4 exclusion of a community feedback loop), ADR 0045 (recruit traits are INHERITED, not uniform draws; the closed-form inherited share 4/(4+n_elig)), ADR 0046 (the warming trait shift is within-PFT, within-age-class selection with a per-PFT age-Wooddens fingerprint), ADR 0047/0049 (the ported mortality hazard, its parameter-reference discipline and its pre-registered flip criterion), ADR 0110 (the per-tree D95max/minwscal consumers and the Enzyme heap-field hazard), ADR 0112-0116 (what happens when this model feeds its own state back in: the error becomes CLIMATE-DEPENDENT), ADR 0117 (the four-axis recruit interface is complete; k_root is a scalar), ADR 0118 (the survivor-training double count, and the composition control that makes it readable), ADR 0120/0121 (line M's rung-2 hook: the seedbank checksums, and that the cross-cell merge branch is dead)"
informed: "line M (the flip criterion is an ACTION in lines/M/STATE.md INBOUND; M owns the roster harness the arm runs on and the artifact pin), lines/S/STATE.md, scripts/build_estab_params_reference.py, test/testitems/references/S_pft_estab_params.csv, src/establishment.jl, src/components/slow.jl, EXECUTION_PLAN.md rung-1/rung-2 arm list (integrator-owned -- raised, not edited)"
supersedes: "ADR 0118 decision 4 (retrain the recruit marginals on entering individuals from M's rung-2 roster dump) -- withdrawn on the owner's steer, see Context"
---

# Port FIT's establishment rule instead of learning a recruit marginal — which trees are BORN is a parameter-file fact, and only which trees SURVIVE has to be learned

> **Status note.** `accepted` 2026-08-11 under the standing autonomous delegation, implementing an explicit
> owner steer. Ships **code**: a new `Establishment` submodule, an opt-in `RecruitEstablishment` hook on
> `FluxDrivenSlowEmulator`, and a generated per-PFT parameter reference. **Default OFF ⇒ every committed
> baseline, the AD gate and every pinned artifact are byte-identical** (guardrail 4). No science result is
> claimed here: §6 pre-registers the arm and the flip criterion that would earn one.

## Context

ADR 0118 measured that the shipped recruit sampler (`RecruitCopula`, ADR 0025) learns its marginals from
FIT's `ind` output — which contains only stems above 5 m, i.e. **survivors** — so it already carries the
trait selection that ADR 0049's mortality operator adds, double-counting it by **+12.18 % on `Wooddens`**
within a cell-PFT group. ADR 0118 §4 proposed fixing that by **retraining** the marginals on *entering*
individuals, which only exist inside line M's rung-2 roster dump.

The owner rejected that route the same day, verbatim:

> "which trees are born is — apart from the inheritance functionality — randomly drawn from uniform
> distributions. why should we train on that?? what matters and what we have to learn is who survives the
> environmental filtering — and for that looking at trees above 5 m should be enough."

Both halves are correct, and checking them against the C is what this ADR does.

**Half one — the entry distribution needs no training data.** `establishmentpft_ind.c:97-140` builds recruits
from two channels, and every input to both is in the parameter files or computable from the emulator's own
roster: uniform draws on each PFT's own interval, plus inheritance from the cell's rolling top-AGB seedbank
with the diffusion of `new_tree.c:38-61`. There is nothing to fit.

**Half two — above 5 m is enough.** The 5 m truncation only ever limited *fitting* an entry distribution
from `ind`. A ported rule generates its own recruits and grows them through the sub-5 m phase under the
emulator's own hazard, so `>5 m` suffices both to drive and to validate — and it is the basis ADR 0106's
10 % acceptance criterion is defined on anyway.

**What the owner's framing understates, and it changes the port's design rather than its verdict.**
Inheritance is not a side feature: with `k_est_inherit`/`k_est_inherit_bg` = 4 and both channels carrying
the same `f_sap`, the inherited share is `4/(4 + n_elig)` — **≈44 % in a five-PFT cell and ≈80 % in a
single-PFT one** (ADR 0045). A pure-uniform recruit model would be wrong in exactly the low-diversity cells
(Amazon, Sahel) where the emulator is weakest. And because the seedbank is the cell's own biggest trees,
**the recruit marginal moves as the forest moves** — which is the risk this ADR pre-registers a measurement
for, not a reason to avoid the port.

## Decision

**Port FIT's establishment rule into the recruit channel, opt-in and default-off, with the flip criterion
pre-registered in §6.** ADR 0118 decision 4 (retrain on entering individuals) is **withdrawn**; item 4 of
the ADR-0117 inbound to line M is withdrawn there too. Nothing in the port depends on M's roster dump.

### 1. What was ported, and what the C actually says

| Piece | C source | Ported as |
|---|---|---|
| eligibility gate | `establish.c:29-33` + `establishmentpft_ind.c:88` | `Establishment.eligible_pfts` |
| the two channels' mixture weight | `establishmentpft_ind.c:99-124` | `Establishment.w_inherit` (closed form) |
| background trait draw | `new_tree.c:196-203`, `numeric.h:59` | `Establishment.rnd_interval` |
| inheritance diffusion | `new_tree.c:38-61` | `Establishment.draw_new_trait` |
| the rolling seedbank | `getsapling.c`, `getmaxagb.c` | `Establishment.Seedbank` + `seedbank_update!` |
| the whole rule, one recruit | `establishmentpft_ind.c` + `new_tree.c` | `Establishment.draw_recruit!` |
| the parameters | `par/pft_lpjmlfit.js`, `par/lpjparam_fit.js` | `S_pft_estab_params.csv` (generated) → `PFT_ESTAB_PARAMS` (gated) |

Five things the C says that a summary of it would get wrong — each verified by reading the source, and each
load-bearing (guardrail 5):

* **The interval-violation rule is NOT a reflection.** ADR 0045 described the diffusion as "reflected at
  the interval edges". `new_tree.c:55-59` instead redraws **uniformly between the parent and the bound that
  was crossed** — a strictly inward move that biases the offspring toward the parent and puts a point mass
  exactly ON the bound when the parent sits there. A reflection would place mass on the far side. This
  matters precisely at the edges where the boreal `minwscal` (`[0.05, 0.15]`) and `d95max` (`[51, 300]`)
  intervals live. Corrected here, in the module docstring, and pinned by a test that separates the two
  rules by their point mass.
* **The seedbank is an accumulation of individual-YEARS, not a set of distinct trees.** `getsapling.c`
  appends every qualifying tree every year with no de-duplication, so a tree that dominates for 30 years
  contributes 30 draws. Inheritance is therefore weighted toward *persistently* dominant genotypes, which
  is a stronger selection channel than "sample the current top trees" would be.
* **It is a per-cell bank.** `getsapling.c:54,105` gate a cross-cell MPI merge on `config->isequal`, which
  `isequalcoord` sets TRUE only when every cell in the run shares identical coordinates — dead in every
  real run (line M established the same thing in ADR 0120's hook notes; `mergesapling()` has no live
  caller).
* **`getsapling` runs BEFORE the year's mortality and establishment** (`update_annual.c:77`, ahead of
  `annual_stand`), so a recruit can inherit from a parent that dies later the same year. The port keeps that
  order.
* **The eligible set is genuinely cell-dependent**, so `n_elig` — and hence the channel mix — is not a
  constant: `gdd5min` spans 0/350/900/1200 across the seven PFTs, and the three boreal PFTs have
  `temp_high = 0`, i.e. they are eligible only where the 20-year mean coldest month is below freezing.
  `establish()` also refuses **every** tree where the 20-year mean warmest month is ≤ 10 °C.

Parameters follow ADR 0047's discipline exactly: one generated artifact
(`test/testitems/references/S_pft_estab_params.csv`, from `scripts/build_estab_params_reference.py`, which
reuses `build_mort_params_reference.cpp_json` rather than copying a second parser), literals in Julia gated
row-by-row against it, and the run globals repeated on every row so a global cannot drift unnoticed. The
builder asserts the two facts the closed-form weight rests on — `k_est_inherit / k_est_inherit_bg == 4` and
per-PFT `alpha_r == param.alpha_r` — so a future parameter edit that turns the closed form into an
approximation stops the build instead of silently biasing the mixture.

### 2. Three departures from the C, stated rather than hidden

1. **The port is DISTRIBUTIONAL, not bit-identical, and cannot be otherwise.** FIT draws from its own
   per-cell RAND48 stream and a process-global `gasdev` pair cache; the emulator has neither. Any result
   from this operator is a claim about the recruit marginal and its PFT composition, never about a year's
   trajectory matching.
2. **FIT draws a Poisson COUNT per channel; the emulator appends ONE cohort per year** whose density the
   count model chose. The port maps this to a Bernoulli on `w_inherit`, which is exact for the recruit
   population's channel mix in expectation and ignores the within-year joint counts.
3. **Two invariants FIT gets for free are enforced explicitly.** A parent trait outside its own PFT's
   interval is clamped on insertion (the inward-redraw rule keeps a child in range only if the parent is in
   range), and an UNSET axis — `TreePools` uses 0 as the ADR-0110 sentinel, and every roster reconstructed
   from `ind` before that ADR has `d95max`/`minwscal` unset — falls back to the uniform channel **for that
   one axis** instead of diffusing a value that does not exist. If the clamp ever fires on
   `sla`/`wooddens` in a real arm, something upstream put a tree outside its own parameter range; that is
   worth investigating, not absorbing.

### 3. What is deliberately NOT wired

The drawn **PFT identity** reaches the roster only behind a second flag (`set_pft_id`, default `false`),
because `fc.tmpls` still carries the donor cohort's per-PFT physiology (`alphaa`, `emax`, `intc`, albedos,
`photo`, `tstress`) — so `true` produces a knowingly inconsistent individual: drawn id, donor physiology.
It is also bounded by the fast core, since `_commit_membership!` refuses an id absent from `fc.pft_slot`;
the `FluxDrivenSlowEmulator` constructor now checks that up front for a fixed eligible set rather than
failing in whichever later year the background channel first draws the missing id. **A per-PFT template
registry is the integration point with line M** (M's drivers build `fc.tmpls`), and until it lands the
honest configuration is `set_pft_id = false` with the drawn id recorded in the diagnostics.

The two samplers are **mutually exclusive** at construction: both set the recruit marginal, from bases that
differ by ADR 0118's measured +12.18 %, so an undocumented precedence rule would be exactly the silent
ADR-0023 shift.

### 4. Why this is safe to ship now

`recruit_establishment = nothing` is the default; nothing in `slow.jl` evaluates the rule, updates a
seedbank or records a diagnostic when it is unset, and no pinned artifact references it. The refactor that
gave both samplers one pool-construction path (`_recruit_pools`) is behaviour-preserving — the copula's
`to_pools` now calls it with the identical clamps and the identical UNSET handling, so the committed copula
gates and golden draw pairs are unchanged.

## Consequences

* **Arm D's question changes shape.** ADR 0118 §5 left "re-establish the bounded-Beta comparison
  like-for-like" as the cheapest remaining offline task. If establishment is *ported* rather than learned,
  the marginal-family question (Beta vs empirical-copula) no longer applies to the recruit channel at all —
  it applies only to whatever remains learned. Arm D is therefore **descoped to the learned path** and is no
  longer a prerequisite for anything on the recruit side.
* **The feedback loop ADR 0025 §4 excluded on principle is now reachable** — deliberately, behind the flag.
  ADR 0112-0116 measured what this model does when it feeds its own state back in: the count recursion's
  level stayed within 2 % while its **error became climate-dependent** and manufactured ~90 % of FIT's true
  global response with the opposite sign. The recruit channel is a different channel and may behave
  differently; §6 makes measuring it the gate rather than an afterthought.
* **The emulator now carries FIT's establishment gate**, so a warming cell's eligible PFT set can open and
  close during a run (via a callable eligibility policy fed by `ClimBuf`'s 20-year window). That is a
  response channel the copula's frozen environmental tail did not have (ADR 0108) — and an untested one.
* **`k_root`, `emax`, `beta_2` are untouched**, consistent with ADR 0117 §6: `k_root` is a scalar 0.02 in
  this configuration, and the other two are emitted nowhere.
* Line S's tier-2 ADR block (0100-0119) is **exhausted by this record**. A tier-3 map is allocated in
  CLAUDE.md §9 at merge time (S 0170-0189, M 0190-0209, E 0210-0219, O 0220-0229, integrator 0230-0239),
  under the §9 rule that whoever holds the integration lock is the integrator for that moment.

## The pre-registered flip criterion (guardrail-4 corollary — §6)

Three opt-in flags in this repo have already rotted in the off position because no ADR said what would flip
them. This one states the arm, the line, the pass condition and the value to flip to, and the same block is
written into `lines/M/STATE.md` as an ACTION.

* **Arm.** Rung 2, on line M's roster harness (the only roster that exists; ADR 0117 §2). Two recruit
  channels under an otherwise identical configuration, both with the trait-mortality arm **C1** on, since
  the double count only bites when selection is active:
  **R0** = today's pinned `.rcop` copula artifact · **R1** = `RecruitEstablishment` with the cell's eligible
  set and the seedbank fed by the emulator's own roster, `set_pft_id = false`.
* **Necessary condition, checked FIRST (an operator that never fired produces a null, not a verdict).** In
  ≥90 % of recruiting years: `sb_weight > 0`, and the realised inherited fraction within ±0.05 of
  `4/(4 + n_elig)`. Report the mix. If it fails, the arm measured the uniform background channel only and
  says nothing about inheritance.
* **Primary pass condition — the per-PFT age–`Wooddens` GRADIENT SHAPE** against
  `test/testitems/references/S_age_wooddens_gradient.csv` (ADR 0118 §4's discriminator, chosen because a
  roughly uniform double count cannot fake it): R1+C1 must reproduce the gradient's sign in ≥5 of 7 PFTs
  **including the non-monotone ids 0 and 3**, and must not do worse than R0+C1 on that count.
* **Secondary — the trait RESPONSE must not be paid for.** On ADR 0108's basis (per-cell
  `median(ssp370) − median(historic)` regressed on the C truth's own response; the shipped copula scores
  +0.85 SLA / +0.35 Wooddens / +0.16 D95max / +0.69 minwscal), R1 must **gain ≥ 0.10 on Wooddens** — the
  axis carrying the double count — and **lose ≤ 0.05 on every other axis**.
* **Kill condition (this is the one that refuses the flip).** The recruit channel must not reproduce the
  count recursion's failure mode. Measured as in ADR 0116: the scenario-differential bias of the community
  trait mean at lead 18 must stay **below 10 % of FIT's own response on that axis** (ADR 0106's tolerance
  applied to the response, not the level). If it exceeds it, the ported rule stays opt-in and the finding
  is recorded as the second measurement of a climate-dependent self-feeding error — which would itself be a
  result worth having.
* **Value to flip to** if the conditions hold: M's coupled driver pins
  `recruit_establishment = RecruitEstablishment(; eligible = <per-cell set from ClimBuf>, set_pft_id = false)`
  and drops `recruit_copula` for that arm; S bumps the artifact generation rather than mutating one in place
  (the frozen S→M contract).
* **Not a valid basis for the flip:** the one-step copula table (ADR 0104's error, restated in ADR 0117 §5),
  a per-cell deattenuated slope (retired three times over, ADR 0113/0115 §5), or a five-cell result
  presented as fidelity evidence (guardrail 6; the acceptance criterion is all 54 020 cells).
