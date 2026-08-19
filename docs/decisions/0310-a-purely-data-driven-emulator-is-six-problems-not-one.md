# 0310 — A purely data-driven emulator is SIX problems, not one: fluxes and speed yes, the warming response UNPROVEN, and the per-individual roster may be non-negotiable

* **Status:** **exploratory — a recorded exploration, NOT a decision.** ⚠ **Two owner instructions bound it,
  both 2026-08-19, verbatim: (1) *"no! stop! dont write anythign of this to other lines!!! we are jsut
  discussion a new direction of this project here, nothing to do wiht other lines!!!"* and (2) *"you are also
  nto the correct person to discuss this with. relocate our whole discussion to a new line that is
  responisble for these project lever decisions and exploring new ideas."*** ⇒ **nothing here has been raised
  with line S, M, E or the integrator; nothing was written to `MEMORY.md`, `EXECUTION_PLAN.md` or any other
  line's `STATE.md`; nothing here binds anyone or schedules any work.** This is **line X's** open exploration,
  and only line X may carry it forward. Do not propagate it without the owner reopening the topic.
* **Date:** 2026-08-19
* **Line:** **X — project direction & exploration** (tier-1 block 0310–0329; this is the block's FIRST record,
  and the record that opens the line). ⚠ **Originally drafted as ADR 0088 on line O and RELOCATED here, in
  the same session, before ever being committed** — on instruction (2) above. Line O was the wrong owner:
  it owns online coupling, not project direction.
* **Supersedes:** nothing. **Narrows** ADR 0086 §5d's "the learned annual operator is 1.3–1.5×" (that costing
  assumed the daily soil/grass loop stays — false once a daily flux head is learned too, §4). **Does NOT
  supersede** ADR 0093 §4.4/§4.5, which it instead makes *testable* (§5).
* **Basis:** 14-agent workflow `wf_1392bef9-337` — 6 independent investigations, each adversarially reviewed
  (**all 6 refuted**), 1 synthesis, 1 completeness critic. Full transcript:
  `~/.claude/projects/-p-projects-open-Jamir-wt-O/d1fedf05-84e7-49aa-8351-cc3c0206c27b/subagents/workflows/wf_1392bef9-337/journal.jsonl`
  (one `{"type":"result"}` line per agent). 2.66 M subagent tokens, 574 tool uses.

---

## 1. The question, and why it is not the question this repo has been answering

Owner, 2026-08-19, verbatim (lightly de-typo'd):

> *"You were way too narrow on what we did so far. You did not explore directions that deviate from the
> hybrid modelling idea. I want you to explore also other ways. For example: a PURELY DATA-DRIVEN emulator,
> not a hybrid. Isn't it possible to learn which state of the forest follows a given state with a given
> climate? In a first step this would be purely offline of course, but would not only predict the stable
> state but also the WARMING RESPONSE hopefully. For running in an ESM we would then of course need also
> the DAILY FLUXES, not only the yearly state of the forest. Do you think this is learnable / achievable?"*

The project's entire architecture (ADR 0001) is a **hybrid** by decision, and every subsequent record
reasons inside it. This ADR is the first to price the non-hybrid alternative on its own terms.

⚠ **The framing correction that matters most: it is six problems with six different answers**, and the
single yes/no the question invites is what makes it look either obviously right or obviously refuted.

---

## 2. The six verdicts

| # | part | verdict | confidence |
|---|---|---|---|
| (i) | daily **water + carbon** flux head | **data exist; learnability UNTESTED** | medium (downgraded from the synthesis's "high" by the critic, §6.6) |
| (i′) | daily **energy** flux head | **IMPOSSIBLE from this oracle, permanently** | high |
| (ii) | one-year-ahead annual operator, teacher-forced | **already achieved, and near-worthless as measured** | high |
| (iii) | free-running multi-century rollout | **stability probably fine; UNPROVEN, and the mandated remedy is untried** | medium |
| (iv) | the warming response within tolerance | **NOT demonstrated; no positive evidence exists** | high on the diagnosis, low on the prognosis |
| (v) | conservation inside a coupled ESM | **not achievable by a loss penalty; only by construction** | high |
| (vi) | speed | **achievable, 1–4× margin** | medium-high |

### (i)/(i′) The daily head splits in half, and the halves are not comparable

Water and carbon targets exist for **both** legs [MEASURED]:
`/p/tmp/jamirp/esm_land_daily/daily_2000_2019_global_c0_67419_seed1/output` = 198 716 168 736 B and
`daily_2020_2100_ssp370_global_c0_67419_seed1/output` = 805 580 866 802 B, all 67 420 cells, carrying
`d_gpp d_npp d_transp d_evap d_interc d_pet d_prec d_runoff d_swc d_swe d_rootmoist` + `whc_nat lai_stand
fpc_stand`. **Two investigations claimed the ssp370 daily set does not exist; both were refuted** — it does.

**Energy has no target and never will.** Of 421 output slots in `par/outputvars.js` only monthly `ALBEDO`
and `SOILTEMP1-6` are energy-adjacent [MEASURED]. Sensible heat, net radiation and skin temperature have no
training target **at any data volume**, and no LPJmL configuration creates one. This is not a new obstacle —
CLAUDE.md §0 defines Component E as *"a surface-energy-balance + skin-temperature closure LPJmL-FIT lacks"*,
validated against PLUMBER2 towers (ADR 0072/0073). It is recorded here because it **bounds the owner's
question**: "purely data-driven, trained on LPJmL-FIT" is structurally impossible for the atmosphere-facing
energy, independent of method.

Two further constraints on the achievable half:
* latent heat and skin temperature must be solved **implicitly together** or the atmosphere sees a surface
  it disagrees with (ADR 0082; `src/interface.jl:64` makes sensible heat the residual);
* **there is no two-run spread for any daily flux** (seed1 only, both legs) ⇒ ADR 0106's
  `max(10 %, the C's own spread)` **has no denominator on the daily side** [MEASURED].

⚠ Critic's downgrade, accepted: the daily head must be conditioned on the **learned** annual state, so its
error compounds with the annual head's, and that compounding **has never been estimated anywhere**.

### (ii) The one-step operator is already built, and its headline number is 96 % null

Out-of-sample R² **0.9824** on 121 495 658 rows / 51 767 cells, both scenarios — against a **persistence
null of 0.9622** [SOURCE, ADR 0113/0115, re-read verbatim by two reviewers]. Per-band one-step response
ratios are right (0.90–1.08).

**STANDING RULE:** report the persistence null beside every one-step number, or the number is meaningless.

### (iii) Stability is probably fine, and every reason given for it was wrong

Measured: recursed R² 0.9182, level bias ≤ +0.155 stems/patch on a mean of 8.28 (< 2 %), RMSE saturating at
1.717, `sd(pred)/sd(truth)` 0.983 → 0.904, corr 0.994 → 0.940 at lead 80 ⇒ **no variance collapse, no
runaway** [SOURCE, ADR 0113/0114].

Three reviewer narrowings, all accepted:

1. ⚠ **"Stability is free, do not buy stabilisers" is REFUTED and was the most dangerous sentence in the
   pile.** ADR 0115 §1 attributes the boundedness to *tree-ensemble leaf values being confined to the
   training range [1, 42]* — a **hypothesis-class artifact of a piecewise-constant forest**, which does not
   transfer to a neural operator. The same machinery on a multiplicative target produced **799.5 stems where
   the observed maximum anywhere is 42**.
2. **The measured arm recurses 1 of 15 features.** The other 14 are FIT's own roster state
   (`agb/lai/fpc/hmean/hmax/age_mean`), FIT's own four flux columns — **through which the entire transient
   climate signal enters** — and four static columns. ⇒ **it is not an instance of the owner's
   (state, climate) → state map at all.**
3. **It was trained one-step and merely INFERRED recursively.** No multi-step loss, no pushforward, no noise
   injection has ever been run in this repo. That is precisely the configuration every weather emulator cited
   (NeuralGCM, GraphCast, ACE2, Samudra) exists to avoid.

### (iv) The response: the diagnosis is solid, the prognosis is empty

| fact | value | basis |
|---|---|---|
| recursing ONE variable flips the aggregate response ratio | **+0.707 → −0.226** (target 1.0) while R² drops only 0.982 → 0.918 | ADR 0113/0114 |
| validity horizon | 1.03 at 2 yr, 1.06 at 3 yr, **−0.82 at 40 yr** | ADR 0114 |
| the mechanism is **rectification**, not noise | reproduces **86.7 %** of a large stem decline vs **96.2 %** of a large increase | ADR 0116 §4 |
| the leg-bias difference at lead 18 | **+0.126** stems/patch against a true global response of **−0.122** — same size, opposite sign | ADR 0115 §3 |
| the previous attempt's target was pre-determined | persistence null **0.9623** vs de-leaked **0.9620** ⇒ **3.77 %** of variance left for climate | ADR 0180 |
| the response it had was **inherited from the stand** | through-origin slope STAND **0.994**, CLIM **0.016**, FLUX **0.037** | ADR 0181 |
| the climate channel is structurally wide open and FLAT | 77 440 climate splits = **10.20 %** of all splits; prediction moves **0.227** stems over the entire global range, **0.0568** over each cell's own warming = 4.4 % of the live lagged channel | ADR 0179 |

**KILLED by review — do not quote these:**
* *"93 % of the leg bias cancels at lead 1"* — the ADR's own printed row gives 86 %, and the cancellation is
  **negative** at leads 5 and 12.
* *"you need cross-leg error correlation ≥ 0.99985"* — it applies a 10 %-of-response bar to an **area-weighted
  global aggregate that appears in no acceptance criterion**. On the correct per-cell basis a typical
  |count response| is **1.854 stems/patch on a level of 7.053 ⇒ r = 0.263**, needing 1.86 % level accuracy at
  uncorrelated leg errors, or ρ ≥ 0.965 at a 10 % level error.
* *`rho_within_chain = 0.088` as a cross-leg error correlation* — `crn_headroom.py:40-59` computes it between
  historic-2019 and ssp370-2099 seed noise, and **ssp370 CONTINUES the historical chain from
  `restart_2019`**, so it is an 80-year **within-chain memory decay** of the C's own noise. It bounds nothing
  about a learned map, and its effect on the acceptance test is **sign-inverted** from how it was used (a
  noisy reference *widens* `max(10 %, own spread)`).
* *"R² = 0.74 of FIT's per-cell response is recoverable from climate alone"* — **refuted by the missing
  null.** A pure geographic address (unit-sphere x/y/z, **no climate whatsoever**) scores **0.654** on the
  identical target under identical folds; the warming increment buys **+0.019 of 95.2 achievable points**;
  under spatially blocked 15°×5° folds everything collapses (full 0.549, geo 0.353, warming-only 0.093); and
  the target is the **drift-contaminated** 20-vs-81-year window difference ADR 0178 §1 was written to reject.
  ⇒ **THERE IS NO POSITIVE LEARNABILITY EVIDENCE FOR THE RESPONSE.**

⚠ **A decision request, NOT a premise (critic §6.4, accepted).** "Score the response as a map and an
aggregate, never per cell" and "the per-cell response tolerance is 40–100 % of the response" are **proposals
to amend ADR 0106** (owner-set: all 54 020 cells, both scenarios, and the response between them). They are
raised here, not adopted. And the loosening is derived at **npatch = 25**; the 500-patch reference resolves
its own response to 8.5–12 %, so **the loose tolerance is an artifact of the cheap reference and largely
evaporates at acceptance grade.** State both patch counts whenever this is discussed.

Where the response *is* well posed: the **aggregate** (S/N 29.26, two-seed noise 3.42 % of the response) and
the **spatial pattern** (cross-cell response reliability **0.909**) [MEASURED].

### (v) Conservation is structural, and the current gate would not catch its absence

`test/testitems/conservation_closure_tests.jl` asserts the budget **formulas** are consistent on synthetic
fluxes at 1e-9; the real closure is structural — `src/conservation.jl` routes every carbon movement through
an accounted flux in a mutable ledger, residual identically zero [SOURCE]. ⇒ **a purely learned model has
none of that structure and would fail nothing in the current gate, because the gate tests formulas, not the
model.** That is a gap in the gate, not only in the proposal.

Timescales (reviewer's versions; the investigator's two headline figures were killed):
* **energy is the fast clock** — 1 W/m² = **3.04 K/yr** of unopposed column heating (cp·ps/g = 1.0369e7
  J/m²/K, verified), ≈0.24 K global-mean feedback-limited at 1.2 W/m²/K over 29 % land. ⚠ *"a 10 W/m² learned
  bias → 2.4 K"* has **no basis**; line E's measured tower errors are where a real number lives.
* **KILLED:** *"a 1 %-of-NPP leak burns the 10 % biomass tolerance in 101 years"* — stock/NPP = 10.1 yr, so in
  a turnover system a persistent 1 % flux bias **equilibrates at ~1 % stock error in ~10 yr**. Also KILLED:
  *"a 10 % ET bias drains a 200 mm root zone in 3.9 yr"* — bounded bucket, and ET is a function of moisture.
* ⚠ **fp32 cannot meet guardrail 2.** Water closure ~1e-12 and energy ~1e-14 are CI gates; fp32 eps is
  1.2e-7. **This removes the 2.1× fp32 saving the speed case had banked.**

---

## 3. Speed — measured, and the strategic reading is NOT the raw ratio

All single-core, Zen-4 (`csp14c01`, AMD EPYC 9554), measured on a compute node.
⚠ The investigation's headline **0.001364 is KILLED — it was timed on arrays that had overflowed to
`inf`/`nan`** (`RuntimeWarning: overflow encountered in matmul` on the reviewer's re-run). Replaced by the
reviewer's reproduction with finite weights.

| configuration | core-s / cell-year | basis |
|---|---|---|
| daily head, w256/L3/din96, **fp32**, batch ≥ 256, 365 calls | 0.00149 | MEASURED |
| same, **fp64** (required by guardrail 2) | 0.00314 | MEASURED |
| annual head, shared-trunk NN (w512/L4) | 0.00004 | MEASURED |
| annual head, **the repo's single-output regression forests**, 500 output scalars | 0.0095 | MEASURED (63.2 ns/tree/row — 3.5× the investigator's 18.3) |
| **realistic purely-learned total** (fp64 batched daily + NN annual) | **≈0.0032** | REASONED from two MEASURED |
| pessimistic corner (fp64, w512/L4, tanh, **batch-1**, forest annual head) | **≈0.055** | MEASURED components |

Against the reference points: **7.06** (C @ 500 patches) → 2200× cheaper; **0.290–0.383** (C @ 25) → 92–120×;
**1.2329** (the current basis, vs the C's 0.2666 = 4.62×, ADR 0084 — *not* the retired 1.096) → ~350×;
**0.030** (T63 convention) → fits with 9× margin; **0.0135** (T31 convention) → fits with **4×** margin.
⚠ **The pessimistic corner FAILS BOTH.** Three engineering choices are load-bearing, not optional: batching
over land columns (batch-1 costs 4.5–12.7× more per FLOP), fp64 (2.1×), and tiling at ~1024 cells.

**Three corrections that change the strategy:**

1. ⚠ **"210× faster than the C" is KILLED as a rigged comparison.** Cost = `0.014112·J` ⇒ J=1 → 0.0136,
   J=2 → 0.0282, and the **atmosphere-facing fluxes converge within 1.7–6.6 % at 1–3 patches**, with a
   further 1.5–2.0× of bit-identical optimisation available (ADR 0086 §2/§3c/§4a). ⇒ **for exactly the daily
   fluxes being priced, the unlearned C already meets the conventions.** Comparing against 25 patches picks a
   pure variance setting the same ADR says nobody needs for fluxes.
2. **But the acceptance criterion is not a flux criterion — and this is the real speed case, which no
   investigation made.** Certifying 54 020 cells individually needs ~125–192 patches ⇒ **the C at acceptance
   grade is ~1.8–2.7 core-s/cell-year.** A learned operator predicting the **ensemble expectation** pays no
   patch tax at all, and the determinism dividend is worth **+2.9 to +14.4 pp** of cells inside the 10 % band
   (ADR 0093), free.
3. **A sub-daily head does not fit:** 385 cycles per cell per 300-s Terrarium land step. Daily
   piecewise-constant buffering is mandatory ⇒ **the head cannot represent a diurnal cycle**, which is what
   the boundary layer is most sensitive to.

⇒ **all three routes (learned, C at 1–3 patches, hybrid with the 51× per-tree gap closed) fit the
conventions. Speed is NOT the discriminator it looked like.** What speed *does* buy uniquely is escape from
the patch tax at acceptance grade.

---

## 4. What is genuinely new vs. already tried and failed

**Already tried, measured, failed — do not re-propose without refuting these:**
* the one-year count map trained one-step and recursed (aggregate response **−0.226**) and its
  ratio/anomaly variant (**−1.099**, R² 0.678, 799.5 stems) — ADR 0113/0115;
* feeding climate directly: channel structurally open (10.20 % of splits) and **flat** — ADR 0179;
* **hold-out-by-scenario as an evaluation mode** (counts R² 0.9847, *"a wash"*; ADR 0026 §5/0027/0036) ⇒
  *"the first genuine held-out-forcing test this project could run"* is **FALSE**;
* a learned recruit marginal (superseded by porting FIT's own establishment rule, ADR 0119); a count target
  driving a gross mortality budget (refuted architecturally, ADR 0241, e/k = 2.09–2.59×).

**Genuinely new / untried:**
* **a third forcing leg** — §7;
* **a 1000-step global state trajectory** — §7;
* **`bm_inc_counter` is observable after all** — §7;
* **the entire rollout-training family** (multi-step loss, pushforward, noise injection), a paired/difference
  loss, common random numbers as a *training device*, a two-leg shared trunk: none tried;
* **a permutation-equivariant set/graph network over the per-stem roster** — §5, the critic's #1 finding;
* **a stochastic transition operator** with a binomial-survival + Poisson-birth head — §5;
* **a direct, NON-autoregressive climatology → 20-year-mean-state map** — never considered, its estimand
  **equals** the acceptance criterion (ADR 0106/0111 are stated on 20-year windows), and it eliminates
  rollout drift by construction.

**Is the recorded near-zero response evidence against the proposal?** ⚠ **Reviewer-corrected answer, and the
synthesis's "predominantly an artifact" was OVER-CONFIDENT (critic §6.7):** the failure has *identified,
mundane causes* (the pre-determined target; the response inherited from the stand not read from climate; the
rollout arm recursing 1 of 15 features and trained one-step; the trait head containing no roster state at
all, so a state recursion **cannot reach the trait axes**); **the standard remedies are untried; and the one
remedy actually tested — de-leaking the lagged column — recovered 13.5 % of FIT's response, still ~7×
short.** Also relevant: after deattenuation only **two of four** trait axes are broken (SLA 1.08 and minwscal
0.99 are already right; Wooddens 0.63, D95max 0.51), and one has a written, wired, **default-OFF** fix
(`src/trait_mortality.jl`, ADR 0093 §5.2 — guardrail 4's corollary applies).

---

## 5. The strongest objection, and the architecture that survives it

**ADR 0093 §4.4/§4.5, verified verbatim by two agents.** A learned operator whose state is a coarse-grained
summary of the forest destroys, and **sign-reverses**, the covariance carrying the trait response:

* `bm_inc_counter` (the per-individual negative-growth run-length; multiplies `mort_npp` and `mort_water`,
  hard-kills at 5) is **strongly trait-correlated** — PFT 3 `E[Wooddens|c]` rises 236 883 → 281 936 across
  c = 0…5 (**+19 %**). **11.69 % of stems have c ≥ 1 and carry 44.8 % of all mortality mass and 37.8 % of all
  deaths.** Factorising trait ⊥ c drops a covariance worth **39–329 % of the total selection covariance and
  reverses its sign in PFTs 1, 2, 3 and 5.** Quadrature on a step converges O(1/M).
* collapsing `mort_water` to a patch mean **flips the sign of the minwscal selection differential in PFTs 0,
  1 and 2** (4.28 M of 10.59 M stems).

**Decisive against the CHEAP version of the proposal; NOT against the direction.** Four reasons, the last two
of which are new here:

1. decisive against any low-order-summary state (moments + copula — **which is what ships**) and against a
   patch-mean hazard;
2. **not** decisive against an operator carrying a joint state over (trait × size × growth-failure class)
   with a per-stem hazard input;
3. **ADR 0093 scopes its own refutation to QUADRATURE COST** (*"1 260 nodes instead of 90 ⇒ 3.7× not
   31.8×"*). That kills the density family as a **speed lever**. For a *learned* head the marginal cost of
   state width is measured to be nearly flat — widening a daily head's input from 96 to 1 200 numbers costs
   **2.7×** — so a 14× node blow-up does **not** become a 14× cost blow-up, and §3 shows the wide version
   still fits. ⇒ **the refutation transfers as a STATE-CONTENT REQUIREMENT, not an impossibility.**
4. ⚠ **THE ARCHITECTURE NOBODY PRICED (critic #1) — a permutation-equivariant set/graph network over the
   tree list.** Learn the *per-stem* annual update (grow / die / recruit) from the stem's own state plus
   permutation-invariant pooled summaries of its patch. **No ported equations, no C source ⇒ still purely
   data-driven, but it keeps the roster.** Three facts make this the strongest omission:
   (a) `(Cell, Patch, ID)` is a stable cross-year identity (ADR 0125) ⇒ the corpus is **2.55e9 PAIRED
   per-stem labels**, ~20× larger and far better-posed than the 1.2e8 cell-year rows every other option uses;
   (b) it is the **only** candidate that survives ADR 0093 §4.4/§4.5 (it can carry `bm_inc_counter` and
   per-stem water stress as state axes — now known to be dumped, §7) **and** pays no patch tax;
   (c) its cost is annual-per-stem ≈ **1/365 of the C's per-tree cost**, and ADR 0086 §5d's "1.3–1.5× only"
   does **not** apply, because that costing assumed the daily soil/grass loop stays — false once the daily
   flux head is learned too.

**And the target should be a STOCHASTIC operator, not a conditional mean (critic #2).** Rectification is the
*definitional* failure mode of a self-fed conditional-mean regressor; the only remedy the synthesis offered
was a multi-step *deterministic* loss. Two cheap arms are absent from every experiment proposed so far:
* a **stochastic rollout** — sample, roll an ensemble, compare **distributions**, which is literally what
  `max(10 %, the C's own two-run spread)` asks for;
* a **binomial-survival + Poisson-birth head**, conservative by construction (`n_{y+1} ≤ n_y + births`),
  which **structurally forbids** both the 799.5-stem blow-up and one-sided under-tracking of losses.
Precedent: deterministic autoregressive weather models blur and lose extremes/trends; diffusion-ensemble
successors recover them (GraphCast → GenCast) [LITERATURE].

**A measurement that reframes the count problem (critic #3, run this session).** On
`tables/direct_count_global.parquet` (4 969 168 rows; 10 000 cells × 25 patches × 2000–2019), linear least
squares for next-year per-patch stem count over 4 220 878 lag-3-complete rows:
`lag1 alone 0.97597 · +climate 0.97600 · +lag2 0.97613 · +lag3 0.97621` [MEASURED].
⇒ (a) **deeper history buys 0.00024 of variance** — the non-Markov worry is worth ≲0.02 % of the
conditional-mean variance of the count LEVEL, so "the observed state is not Markov" must be **narrowed to
the trait-axis selection covariance** (ADR 0093's actual claim), not asserted of count predictability;
(b) ~2.4 % of variance survives lag-1 and **essentially none of it is explainable from history or climate**
⇒ it is the C's own per-patch Bernoulli realisation noise. **Therefore the ceiling on any count operator is a
VARIANCE ceiling, the correct target is the ensemble expectation, and single-draw R² scores are
near-saturated and CANNOT DISCRIMINATE ARMS** — which invalidates an R²-floor guard in any experiment design.

---

## 6. Literature that was missing (critic #8) — three families, none previously cited

* **Integral Projection Models / Usher size-class transition matrices** — the canonical *purely statistical*
  published form of exactly the owner's question (a learned kernel over size × trait plus a recruitment
  boundary term). And the IPM literature **already answers §5's objection** with a latent frailty /
  hidden-developmental-state axis (IPLM) — fittable now that `bm_inc_counter` is known to be dumped.
* **The published LPJ-GUESS ML emulator, GMD 18, 4317 (2025)** — the closest precedent: **97 % runtime
  saving, and a neural net extrapolating BETTER than a random forest to 2100**. But on **grid-cell carbon**,
  i.e. positive evidence for the aggregate and **silent on counts and traits**. An honest calibration of
  expectations, and it should be read before designing anything.
* **The ABM-surrogate literature** (permutation-invariant surrogates; interventionally-consistent
  surrogates) whose central lesson is that *a surrogate fit to observed trajectories can be accurate yet
  wrong under a CHANGED FORCING* — the owner's warming question stated in that field's own language.

Sources: <https://gmd.copernicus.org/articles/18/4317/2025/> ·
<https://harvardforest1.fas.harvard.edu/publications/pdfs/Merow_MEE_2014.pdf> ·
<https://agritrop.cirad.fr/586544/1/CASTANO_manuscript_avril%202017.pdf> ·
<https://link.springer.com/article/10.1007/s00285-025-02318-6> · <https://arxiv.org/pdf/2312.11158> ·
<https://arxiv.org/abs/2403.17410>. The one real precedent for a century-scale autoregressive *vegetation
state* operator is **Rammer & Seidl's SVD emulating iLand over 500 years**, which bought stability by
discretising to **1 418 categorical classes** (4 m height bins, most-abundant species, 3-class LAI) and
**sampling from predicted probabilities** — 0.565–0.602 cell-wise accuracy on that coarse state.
**No published DGVM emulator reproduces trait or size distributions at all.**

---

## 7. NEW cross-cutting facts discovered this session (all `[MEASURED]`, all previously unrecorded)

1. ⛳ **A THIRD forcing leg exists: ssp126, BOTH seeds, complete, finished 2026-08-18 — and it is recorded
   nowhere in this repo.**
   `/p/projects/waldspektrum/priesner/clustering/global/ssp126/ground_truth/model_output/transient_2020_2100_npatch25_random_seed{1,2}/`;
   both logs end `lpjml successfully terminated, 67420 grid cells processed.` (~74 min each);
   `ind_2020_2100.csv` = 186 299 086 970 B vs 186 123 571 505 B ⇒ **different, so not the byte-identical-clone
   failure**; seed protocol is ADR-0041-correct (each restarts from its **own** Historical
   `random_seed{1,2}/restart/restart_2019.lpj`, i.e. a second spin-up carried forward); forest state on disk
   in raw form = **591 GB**, needing only the shipped CSV→parquet conversion. Same constant-CO2 file ⇒ **no
   ADR 0107 violation.**
   ⚠ **Amplitude — I resolved a 3× disagreement between two reviewers: BOTH measured correctly, and the
   difference is entirely the baseline convention.** 2020s→2090s gives ssp126 **+0.190 K** vs ssp370
   **+3.188 K** (ratio 0.060); on a **common pre-2020 baseline** (2016/17→2094/95) it is **+0.783 K** vs
   **+3.440 K** (ratio **0.227**), because ssp126 front-loads its warming. The acceptance criterion's
   response is historic→future ⇒ **the criterion-relevant convention is the common baseline, 0.227.**
   ⚠ Pattern correlation with ssp370 is only **0.19–0.22** and **15–26 % of scored cells COOL** ⇒ ssp126 is
   **useless per cell** (its per-cell response is ~11× below the reference's own noise) but an **excellent
   held-out test: a model that memorised the ssp370 pattern MUST fail it.**
   ⚠ **Build-provenance confound:** ssp126 both seeds report `lpjml C Version 5.6.004 (Aug 12 2026)` while
   the historic spin-up + transient and ssp370 seed1 report `(Feb 5 2026)`. A historic→ssp126 response is
   confounded with **two intervening rebuilds** — gate against `bin/lpjml.pre_dgrass.bak` before use.
2. ⛳ **A 1000-step global state trajectory exists, for both seeds, cited in no document:**
   `vegc_spinup_1999.nc` = `VegC(time=1000, lat=280, lon=720)` gC/m², noleap, 806 449 620 B. ⇒ **refutes the
   claimed "80-step hard cap on rollout depth"** for the aggregate carbon state.
3. ⛳ **`bm_inc_counter` IS EMITTED PER STEM — in the rung-2 roster dumps.** The `#H T` header carries
   `… water_stress temp_stress bm_inc_counter gddtw … isdead mort_prob mort_npp mort_age mort_water
   mort_temp bm_delta leafarea_real`, all per-stem pools including `sapwood_bg_c`/`heartwood_bg_c`; the
   `#H P` line carries the seedbank (`sb_agb sb_trait sb_year sb_id`, `treelen`) plus `rootzone_w
   rootzone_whcs` and `fpar_leafon_grass`. Example:
   `/p/tmp/jamirp/S_rung2/S_r2s_historic_c12045_G0h_predict_s1_dump/roster_rank0000.txt`.
   ⇒ **narrows "these channels are unobservable" to the 29-column GLOBAL `ind` table only, and makes ADR 0093
   §4.4's refutation TESTABLE rather than assumed.**
4. ⚠ **A geographic address is the null that was never run, and it passes.** Unit-sphere x/y/z, no climate,
   scores **0.654** on the per-cell response target under 5-fold-by-cell; under blocked 15°×5° folds the full
   model falls to 0.549 and the warming-only arm to 0.093. **Any per-cell response score under hash/random
   folds is a spatial-interpolation score until this null is reported beside it** (ADR 0040 measured the same
   trap: r 0.923 hash → 0.579 blocked).
5. **The effective independent spatial sample is ~161 populated 15°×15° tiles**, not 54 020 cells (312 at
   10°, 957 at 5°) — consistent with the repo's own 166-tile cluster bootstrap. Row counts overstate
   independent spatial evidence by ~4 orders of magnitude.
6. **Space-for-time is viable in interpolation, not extrapolation:** spatial sd of mean annual T = 12.73 K
   (range 49.51 K) against mean warming +3.23 K ⇒ ratio **3.94**; **95.1 %** of cells' 2090s temperature
   falls inside today's tree-cell range, but **4.9 % (~2 600 cells) exceed the hottest tree-bearing cell that
   exists today.** Gated against `cell_year_feats.parquet` to max|diff| 1.4e-14.

---

## 8. Decisions

1. **The purely data-driven direction is NOT refuted and is worth one properly-nulled experiment.** It is
   also **not** demonstrated: there is currently **zero** positive evidence that the warming response is
   learnable, because the only claim of one died to a geographic-address null.
2. **Every speed claim in this record is superseded if quoted without its patch count and its precision.**
   The purely-learned total is **≈0.0032 core-s/cell-year at fp64**, not 0.0014, and the honest comparison is
   against the C **at acceptance grade (~1.8–2.7)**, not at 25 patches.
3. **`max(10 %, own spread)` has no denominator on the daily flux side.** Either a second daily member gets
   run, or the daily head is scored against the C directly with the tolerance stated as 10 % flat and that
   choice disclosed.
4. **A reporting rule worth PROPOSING if the topic reopens — not imposed on anyone here:** a one-step
   operator number means little without its **persistence null** beside it (0.9622 of 0.9824), and a per-cell
   response number means little without a **geographic-address null under spatially blocked folds** beside it
   (0.654 of 0.748). Both nulls were missing from work this session reviewed. ⚠ **Not raised with line S** per
   the Status note; recorded here as an observation about method, not a directive.
5. **The critic's architecture (§5.4) and stochastic-head recommendation (§5) supersede the synthesis's
   experiment design**, which was four flavours of one deterministic regressor and guarded on an R² floor
   that §5's variance measurement shows cannot discriminate arms.
6. **Nothing in this ADR is implemented.** No `src/**` change, no flag, no artifact. Guardrail 4's form for
   this work, when it happens, is a **parallel opt-in component**, not a change to F.

---

## 9. NOTHING HERE HAS BEEN RAISED WITH ANYONE — and that is deliberate

⚠ **The owner stopped the propagation explicitly (see Status).** This section records *who would have to be
asked* **if and only if** the owner reopens the direction. **It is not a queue, not an integration point, and
no line has been notified.**

| what it would touch | whose scope | status |
|---|---|---|
| a per-stem rate operator; the pooled count tables; the rung-2 dumps; `src/components/slow.jl`, `src/drf.jl` | line S (exclusive) | **NOT raised.** Do not write to `lines/S/STATE.md`. |
| a daily flux head's interaction with `src/fdiff.jl` / `components/fast.jl` | line M (exclusive) | **NOT raised.** |
| adding a purely-data-driven arm to the error-attribution ladder | integrator (`EXECUTION_PLAN.md`) | **NOT raised.** |
| the ssp126 leg, the 1000-step spin-up trajectory, `bm_inc_counter` being dumped (§7) | would normally go to `MEMORY.md` as cross-cutting facts | ⚠ **DELIBERATELY NOT WRITTEN THERE.** They live in §7 of this file only. They are real and measured, and they will matter to other lines *eventually* — but propagating them is the owner's call, not this session's. |

⚠ **AND A NOTE ON WHAT LINE X IS FOR, since this record opens it.** A direction/exploration line is exactly
the place a finding like this can sit *unpropagated* without rotting — which the four component lines cannot
do, because each of them is mid-ladder and would either have to act on it or drop it. The failure mode to
guard against is the mirror image of ADR 0095's (an integrator-owned chore with no trigger silently rots):
**a strategy line with no owner conversation attached to it silently accumulates unactioned proposals.** So
line X's `STATE.md` records, for every open exploration, *what the owner last said about it* and *what would
have to be true to promote it* — and promotion is always an owner decision, never line X's.

## 10. Open disagreements — do NOT quote either side as fact

1. **Lower or upper bound?** Whether −0.226 bounds a closed rollout **from below** (four investigations) or
   **from above** (one reviewer, via the missing density-dependent `exp(−LAI)` recruitment feedback that
   would correct a too-high count; the measured drift channel is exactly `n_prev` at r = −0.336 and
   `age_mean` at +0.330, with every climate/flux feature at |r| ≤ 0.084). **Material to the prior on any
   rollout experiment.**
2. **Unexplained mortality fraction:** **32.4 %** (605-cell sample) vs **11.0 %** (independent 199-cell
   sample) — regionally variable by ~3×. Hazard-decile-1 miscalibration 12× vs 1.8×.
3. **Patch exchangeability for `Height`:** 1.596 vs **1.110** — **does not replicate**, so the "traits at
   cell level, size at patch level" factorisation is **not established**.
4. **Recruitment convexity magnitude:** median ratio 1.221 vs **1.082** (the q95 tail ≈8.4–8.5 does
   replicate). Both rest on a patch LAI reconstructed from the 5 m-censored `ind` table (which reproduces the
   C's own `LAI_STAND` at only 0.87–0.98, and **0.574** at Amazon) and both condition on all 25 patches
   occupied — which **excludes the bright patches carrying 64.8 % of recruitment.** Bias direction
   unquantified.
5. **Stratification vs quadrature on the light axis:** one agent measured equal-count classes at M = 8 giving
   median 0.60 % error but **q95 = 45.7 %**; ADR 0093 §5.4 already measured **4 Gauss nodes recovering
   99.1 %** and stratification **49.5 %**. ⇒ prefer quadrature or the closed-form two-moment correction; do
   not re-derive stratification as new.

## 11. Still unverified
* whether a fixed-size state summary is **information-sufficient** for the daily fluxes. The "photosynthesis
  is degree-1 homogeneous so the per-stem sum collapses" argument is **REASONED, not SOURCE**: three per-stem
  nonlinearities survive (the SLA cap on Vcmax, the net-assimilation rectifier, and the per-stem λ whose
  supply is clipped against a running cross-stem accumulator under `-DPERMUTE`).
* the compounding of the daily head's error with the annual head's — never estimated.
* whether the spin-up's shuffled forcing sequence is recoverable (decides whether a 1000-step test is paired
  or only distributional).
* ssp126's forest state row counts / tree-bearing cell count / per-cell counts (raw CSV only, no parquet).
* GPU throughput; hand-written Julia kernel vs BLAS; the diurnal-cycle cost of daily buffering.
* **the 2019/2020 forcing splice was checked for TEMPERATURE only — precipitation is unchecked**, and GCM
  precipitation biases are typically much larger.
* ADR 0181's flux/stand channel slopes (0.037 / 0.994) were read out of the record, not re-run.
