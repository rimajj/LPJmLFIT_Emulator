# LINE S — Component-S science (branch `line/S`, worktree `wt-S`)

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/S/JOURNAL.md` (append-only). Decisions: tier-1 block
> **0030–0049 is EXHAUSTED** and so is the **tier-2 block 0100–0119** (ADR 0119 spent the last number). Line
> S's **TIER-3 block is 0170–0189** — allocated in CLAUDE.md §9 at ADR 0119's merge under §9's rule that
> whoever holds the integration lock is the integrator for that moment (tier 3 in full: S 0170–0189 ·
> M 0190–0209 · E 0210–0219 · O 0220–0229 · integrator 0230–0239). **Next free number: 0170.**
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## 📥 INBOUND FROM LINE M, 2026-08-11 (ADR 0124) — **arm C is run. Your operator is exact, your option-(c) choice is now a MEASUREMENT, and one pre-registered flip criterion is owed back to you**

> This is the reply to ADR 0117. Nothing here asks you to change `src/trait_mortality.jl` — it is exact.
> Full record: `docs/decisions/0124-*.md`; the numbers below are cell 42490, 25 patches, 2000-2019, 500
> patch-years per run, 5 seeds per arm.

**1. Your ported hazard is an identity, live, and it holds OUTSIDE the state distribution it was gated on.**
ADR 0122's gate ran offline on the recorded trajectory only. Three new results: the count target built from
your hazard and the one built from the C's own `mort_prob` agree to **max |Δ| 4.4e-16 over 5 000 live
patch-years**; `_hazard_tilt` returns **θ = 1 to 4.5e-14 over 2 500 patch-years**; and re-running the identity
gate on the *null* arm's dump — a stand the recording never had, with 7× the ghost-tree rate — still gives
**0 exceedances, max rel Δ 1.7e-15 over 10 600 records**, 105 `bm_inc_counter` + 769 ghost-tree hard kills
classified correctly. The C's own audit adds the decision-level check: `n_kill_applied / n_kill_c` = 0.980-1.014
and **`n_spared_certain` = 0**.

**2. Your reason for choosing (c) over a count-only interface is now measured, not argued.** With the count
target pinned identically in both arms, C1 (your tilt) vs C0 (`f_i = ρ`, the shipped uniform thinning):

| statistic | C1 | C0 (the shipped default) | the C |
|---|---|---|---|
| terminal stems | **1.050×** | 1.209× | 365 |
| wood-density selection differential | **0.952×** | 0.241× | +35 376 gC/m3 |
| per-PFT gradient Spearman ρ vs this cell's own recording, ids 1-5 | **1.000/1.000/0.943/1.000/1.000** | 0.800/0.500/0.943/0.600/**−0.500** | 1 |

**`C1 − C0` = +25 142 = 71.1 % of the differential is differential survival.**

**3. THE FINDING THAT MATTERS MOST FOR YOUR DEFAULT, and no count statistic sees it.** Terminal age structure,
stems `<20` / `20-40` / `≥40` yr: the C **118/120/127**, C1 **117-147 / 111-145 / 103-126**, C0
**336-404 / 25-47 / 26-47**. The uniform-thinning default converts a mature stand into a young one — 80 % of
its terminal stand is under 20 years old — and keeps only **10-16 %** of the C's own `≥40` yr individuals by
identity against C1's **50-63 %**. Related: both arms get the **same count target in expectation every
patch-year** and both draws are unbiased, yet end 1.05× vs 1.21×, because the null spares trees FIT condemns
(669-817 of them), their hazard stays high, and it then kills **twice as many** trees in total while ending
denser. **A count target is not a count.**

**4. Your θ warning was right, and here is its actual shape.** With the target taken from outside the live
state (`RHO=recorded`, the honest proxy for a learned ρ), θ is **bimodal**: median 0, p95 12-14, θ > 0.5 in
207-215 of 500. The median of 0 is not the tilt collapsing — **the C kills nobody in 198 of 500 patch-years
(39.6 %) at this cell**, so a realized-count target is 1.0 and selection has nothing to do. In **25-27 % of
patch-years no θ reaches the target at all** (`_hazard_tilt`'s `shortfall > 0`; the hard kills alone overshoot).
Your decision to REPORT the shortfall rather than absorb it is what made this visible — keep it.

**5. ⚠ WHAT THIS DOES NOT LICENSE, so you are not handed a false green.** C1's count target came from your own
hazard, which pins θ = 1 analytically ⇒ that arm **is** FIT's mortality with an independent draw. It is a
**ceiling** and an end-to-end identity, not evidence about a learned count model. And the hazard ran on the
**C's own** `water_stress` / `temp_stress` / `bm_delta` / `bm_inc_counter` through the rendezvous, so
**ADR 0049 item 4 still bites in the standalone emulator** and §2's exactness does not transfer there.

**▶ 6. ACTION — the pre-registered flip criterion for `trait_mortality`, per guardrail 4's corollary (an
opt-in whose default is known worse is a defect on a timer).** Item 3 is the evidence that the `false` default
is worse; it is not evidence that `true` is better *in the coupled driver*, which is why this is conditional
rather than a request to flip now.

* **arm** — the coupled `FluxDrivenSlowEmulator` at cell 42490, 25 patches, 2000-2019, 5 seeds,
  `trait_mortality` `false` → `true`, everything else fixed.
* **pass condition** — the terminal three-bin age structure of item 3 within the C's own seed spread on **all
  three** bins, AND per-PFT gradient Spearman ρ against **this cell's own recording** ≥ 0.9 on ids 1-5.
* **value to flip to** — `true`.
* **blocked by** — ADR 0049 item 4: offline the operator has neither of FIT's stress integrals. Closing that
  is the work the criterion is waiting on, and M cannot do it (it is inside `src/components/slow.jl`).
* **do NOT score it against `references/S_age_wooddens_gradient.csv`.** That fixture is all 54 020 cells;
  **the C's own recording at cell 42490 scores ρ −0.500 / −0.314 / +0.400 / −0.500 / +0.800 against it**, so a
  naive reading of ADR 0118 §3 as "match the fixture" would fail FIT itself. Use the cell's own recording for
  a per-cell test and the fixture only for a global one. `scripts/diagnose_rung2_armc.py` prints the C's own
  row against the fixture for exactly this reason.

## NEXT — start here

> ## ✅ THE PORTED ESTABLISHMENT RULE IS BUILT AND SHIPPED OPT-IN (2026-08-11, ADR 0119)
>
> The owner's steer of the same day is **implemented**, not planned. `src/establishment.jl`
> (`module Establishment`, pure Base) computes FIT's recruit marginal from the C's parameter files; the
> opt-in hook is `FluxDrivenSlowEmulator(...; recruit_establishment = RecruitEstablishment(...))`, default
> `nothing` ⇒ every committed baseline, the AD gate and every pinned artifact byte-identical. Parameters live
> in one generated artifact (`test/testitems/references/S_pft_estab_params.csv` via
> `scripts/build_estab_params_reference.py`), gated row-by-row by `test/testitems/slow_establishment_tests.jl`
> (160 186 + 69 assertions, both items green). Full suite: job 1758701.
>
> **1. Reading the C corrected three things this repo thought it knew** — details in ADR 0119 §1 and the
> `slow-drf-pipeline` skill, but the first one matters for any future edit of the sampler:
> * the inheritance jitter **does not reflect at the interval edges**; it redraws *uniformly between the
>   parent and the crossed bound* (inward, with a point mass ON the bound). ADR 0045, the skill and this
>   line's own last journal entry all said "reflected". A reflection is a different stationary shape exactly
>   at the narrow boreal intervals.
> * the seedbank accumulates **individual-YEARS with no de-duplication** — 30 years of dominance is 30 draws
>   — so inheritance favours *persistently* dominant genotypes.
> * `getsapling` runs **before** the year's mortality, so a recruit can inherit from a parent that dies the
>   same year. The hook keeps that order.
>
> **2. Two invariants FIT gets for free had to be enforced explicitly, and one of them would have failed
> silently.** `draw_new_trait`'s inward redraw keeps a child in range **only if the parent is in range**. A
> roster rebuilt from the `ind` output carries `d95max`/`minwscal` at the ADR-0110 UNSET sentinel 0, so
> diffusing from it would have put every inherited rooting depth *below* its own PFT's floor — in
> range-looking numbers. An UNSET axis now falls back to the uniform channel **for that one axis**; a finite
> out-of-range parent is clamped on insertion (a guard, not physics — if it ever fires on `sla`/`wooddens`,
> investigate upstream).
>
> **3. What is deliberately NOT wired: the drawn PFT IDENTITY.** `set_pft_id` defaults to `false` because
> `fc.tmpls` still carries the donor cohort's physiology, and because `_commit_membership!` refuses an id
> absent from `fc.pft_slot`. The constructor now checks a fixed eligible set up front instead of failing in
> whichever later year the background channel first draws the missing id. **A per-PFT template registry is
> the line-M integration point** (M builds `fc.tmpls`) — raise it when the arm needs identity.
>
> **4. NO SCIENCE NUMBER IS CLAIMED, and the flip criterion is pre-registered (ADR 0119 §6)** with an
> explicit **kill condition**: if the recruit channel makes the error climate-dependent the way the count
> recursion did (ADR 0112–0116), the flip is REFUSED and that becomes the result. The arm is rung 2 on M's
> roster harness (R0 = pinned copula vs R1 = ported rule, both under the C1 mortality arm); it is written as
> an ACTION in `lines/M/STATE.md`.
>
> **⏩ WHAT TO DO NEXT, in order:**
>
> 1. **PRE-TEST THE KILL CONDITION AT HAINICH, OFFLINE, BEFORE M's HARNESS EXISTS.** Two facts make this
>    cheap, both already checked: `scripts/trait_mortality_arm_probe.jl` **already has a `MODE=response` 2×2**
>    ({operator on, off} × {historic, ssp370}, all arms advanced in ONE process at matched year indices, the
>    double difference read as the response) — which is structurally the design the kill condition needs — and
>    the R0 side needs no new artifact, because `test/testitems/references/recruit_copula_hainich.rcop` is
>    committed next to `drf_forest_hainich.drf`. So the change is a third dimension on that probe: recruit
>    channel R0 (pinned copula) vs R1 (`recruit_establishment`), both under the same count model and the same
>    mortality arm, with ADR 0101's seed ensemble (**one run is not a measurement** — mean ± SEM over ~8
>    seeds), reading whether the community trait mean's bias DIVERGES between the two forcings. It either
>    finds the feedback problem early or buys confidence before M spends harness time. ⚠ **Label it
>    "1 of 54 020"** (guardrail 6) — a smoke test of the kill condition, never fidelity evidence. And keep
>    ADR 0048's protocol: difference against a matched control re-run in the SAME process, read past year 52
>    (the constant-forcing drift settles there), and report the merge count and θ before reading any Δ.
> 2. **DERIVE THE PER-CELL ELIGIBLE-PFT SET** — the concrete blocker to running the port anywhere but a
>    hand-configured cell. `Establishment.eligible_pfts` needs `temp_min20`, `temp_max20` (20-yr running
>    means of the year's coldest/warmest MONTHLY mean, `climbuf.c:134-137,153-154`) and `gdd5`; the monthly
>    inputs already exist in the transient-boundary builder's pipeline. Emit it as a per-cell(-year) table so
>    a warming cell's gate can open and close during a run, and gate it against a cell whose FIT-observed PFT
>    set is known (Hainich has ids 1–5, the Sahel/Amazon 0 and 7).
> 3. **Arm D is DESCOPED, not pending.** ADR 0119's consequence: if establishment is ported rather than
>    learned, the marginal-family question (bounded Beta vs empirical copula) applies only to whatever
>    remains learned, so re-establishing ADR 0093 §5.3's 2–3× KS claim like-for-like is no longer a
>    prerequisite for anything on the recruit side. Do it only if the learned path needs it.
>
> **Two things NOT to do:** do not build a global offline demography rollout (ADR 0117 §2 — M's harness is
> the roster), and do not flip `recruit_establishment` on by default on anything other than ADR 0119 §6's
> criterion (three flags have already rotted in the off position; this one has a named arm, line, pass
> condition and kill condition).

> ## ✅ ARM C IS SCOPED, AND IT TURNS OUT TO REST ON AN INVALIDATED TRAINING TARGET (2026-08-11, ADR 0118)
>
> **Read ADR 0118 first.** No new model run, no refit, ~14 min in 2 jobs (1754705, 1754709). It changes what
> arm C is allowed to claim, and it is already written into `lines/M/STATE.md` as an amendment to the ADR-0117
> inbound (M runs the arm, so they had to have it before they start).
>
> **1. THE FINDING — the recruit copula is trained on FIT's SURVIVORS, so it already carries the selection
> arm C proposes to add.** ADR 0025 §3 chose that target and wrote its own expiry condition into the decision
> text: *"if trait-dependent mortality is ever added, this training target must change."* Arm C **is** that
> change, and **no ADR in the 0047→0049→0117 chain cites ADR 0025** — including this line's own reply to M
> last session. The asymmetry is what makes it bite: **C0 (uniform thinning) is unaffected**, because that is
> exactly the trait-blind design the survivor marginal was matched to, so the bias lands on the arm and not on
> its null — i.e. straight onto the headline `C1 − C0`.
>
> **2. Sized: +12.18 % on Wooddens within a cell-PFT group, and 0.56 of it does NOT cancel in a response.**
> 197.7 M historic + 828.8 M ssp370 surviving stems, both seeds (agreement ≲ 2 % everywhere — an unusually
> clean variability audit for this line). Other axes: SLA +0.80 %, D95max −2.35 %, minwscal +0.44 %.
> **Wooddens is precisely the axis ADR 0049's flip criterion is written on** and the one ADR 0046
> fingerprinted as within-PFT selection. ⚠ **All four are LOWER BOUNDS** — the `ind` writer drops stems below
> 5 m, so selection before that height is invisible.
>
> **3. ⚠ THE COMPOSITION CONTROL IS WHAT MAKES THE PANEL READABLE — do not quote the pooled numbers.** Pooled,
> D95max (**−49.6 %**) and minwscal (**−35.9 %**) look catastrophic; formed *within* (Cell, Type) they collapse
> to −2.4 % / +0.4 %, so ~95 % of that was *where young stems live*, which the per-cell conditioning already
> handles. The pooled panel alone would have reported a four-axis crisis of which exactly one is real. And it
> is not a "pooled overstates" rule — Wooddens went the OTHER way, +5.4 % → +12.2 % under the control.
> **Never blend the two panels' ratios:** the per-cell panel's `n_young ≥ 30` floor makes it a biased
> subsample (34 256 of 54 020 cells) whose own Wooddens response is **−3698**, opposite in sign to the pooled
> **+1848**.
>
> **4. What arm C may now claim, pre-registered so it cannot be reinterpreted afterwards.** `C1 − C0` is
> **not** "how much of the trait response is selection". ADR 0049's flip criterion is not re-scoped but gains
> two conditions: **read θ first** (the confound and the arm's power scale together — near-zero θ means the
> operator never fired, ADR 0117 §6.i), and **discriminate on the per-PFT gradient SHAPE**
> (`S_age_wooddens_gradient.csv`, non-monotone ids 0 and 3), which a roughly uniform double count cannot fake.
>
> **5. ⚠ THE FIX IS A PORT, NOT A RETRAIN — ADR 0118 decision 4 IS SUPERSEDED BY AN OWNER STEER (2026-08-11,
> same day; correction recorded here, the ADR is not edited).** ADR 0118 §4 proposed retraining the marginals
> on entering individuals from M's rung-2 roster dump. **Withdraw that.** The owner's objection: *"which trees
> are born is — apart from the inheritance functionality — randomly drawn from uniform distributions. why
> should we train on that?? what matters and what we have to learn is who survives the environmental
> filtering — and for that looking at trees above 5 m should be enough."* Correct on both counts.
> * **FIT's establishment rule needs no training data.** Uniform on each PFT's `[low, high]` from
>   `par/pft_lpjmlfit.js`, plus inheritance from the cell's 50-yr rolling top-AGB seedbank with
>   `new = old·(1 + 0.1·gasdev)` reflected at the edges, mixed at the closed-form `w_inherit = 4/(4 + n_elig)`
>   (ADR 0045). Every input is in the parameter file or computable from the emulator's OWN roster ⇒ **port it.
>   No new artifact version, no dependency on M's dump.** Item 4 of the M inbound is withdrawn there too.
> * **>5 m IS enough, and item 2's "lower bound" caveat does not constrain this route.** It only ever limited
>   *fitting* an entry distribution from `ind`. The emulator grows its own saplings and applies the ported
>   hazard through the sub-5 m phase itself, so >5 m suffices to drive AND to validate — which is also the
>   basis ADR 0106's 10 % is defined on. (The caveat still applies to any number in ADR 0118's own table.)
> * ⚠ **Two things the owner's framing understates, and they change the port's design, not its verdict:**
>   inheritance is **44 % of recruits in a mixed cell and ~80 % in a low-diversity one** (ADR 0045), so it is
>   the MAJORITY channel, not a side feature — a pure-uniform recruit model is wrong; and the seedbank is the
>   cell's own biggest trees, so the recruit marginal **moves as the forest moves**.
> * **THE RISK THAT REPLACES THE OLD ONE, and it must be measured rather than assumed:** the port makes
>   recruits a functional of the emulator's own community — the **feedback loop** ADR 0025 §4 excluded on
>   principle. ADR 0112–0116 measured what this model does when it feeds its own state back in: the error
>   becomes **climate-dependent** and manufactures ~90 % of the true signal with the WRONG SIGN. Rung 2 (where
>   the roster returns from the C each year) is the cleanest place to measure it on this channel.
>
> **6. ARM D IS SCOPED, AND ITS MOTIVATING NUMBER IS NOT CURRENTLY DEFENSIBLE.** Arm D inherits the double
> count unchanged (it is "C + Beta"). Separately: ADR 0093 §5.3's "bounded Beta beats the copula 2–3× on
> per-cell KS (0.042–0.073 vs 0.129–0.173)" has **no committed reproducer in this repo** — no script, no
> fixture — and its phrase *"two-moment fit, no fitting procedure"* indicates the Beta used each cell's
> **observed** moments while the copula's figure is **K-fold-by-cell out-of-sample**
> (`score_slow_copula_ks.py`). If so it compares oracle-conditioned against out-of-sample and the 2–3× is an
> **upper bound**, not a realizable gain — a deployed Beta still needs a learned map from features to
> (mean, variance), the cost the copula's forests already pay. **Re-establish that like-for-like before arm D
> runs**, or it repeats ADR 0112's lesson in a new place. This is the cheapest remaining offline S task.
>
> **7. ⚠ ADR BLOCK NEARLY EXHAUSTED — 0119 IS THE LAST NUMBER LINE S HAS.** Raised again below; the block map
> is CLAUDE.md §9, integrator-owned. Allocate the next block BEFORE it is needed mid-session.

> ## ✅ RUNG 1 IS OPEN, AND ITS FIRST TWO FINDINGS CHANGE HOW YOU READ EVERY S NUMBER (2026-08-10, ADR 0112 + 0113)
>
> **Read ADR 0112 and 0113 before anything else in this file — several statements further down are superseded
> by them and are flagged in the ⚠ block below.** Both are on this branch; no new model runs were needed; total
> compute ~25 min in 5 jobs (1747638, 1747642, 1747655, 1747656, 1747662).
>
> **1. Every published global Component-S number is a ONE-STEP TEACHER-FORCED score** (ADR 0112). All 15
> features of the production count model are built from LPJmL-FIT's own output for that very
> `(Cell, Patch, Year)` — including `n_prev`, FIT's own previous-year stem count — and the evaluation predicts
> each row from that row's own features. **K-fold BY CELL holds out space, not time.** So rung 1's arm B ("fed
> the C's own per-tree fluxes") was never work to be done: it is what the published panel already is. The
> missing control was arm A.
> **The null that follows:** predict `n_prev`, learn nothing ⇒ R² **0.9622** against the production model's
> 0.9824, per-cell response slope **0.980** vs 0.958, deattenuated **1.029** vs 1.006, area-weighted aggregate
> ratio **0.685** vs 0.707, and it reproduces the regional band pattern including the wrong-signed tropics.
> ⇒ **on every count RESPONSE statistic the null matches the production model; the only place the learned model
> clearly wins is accuracy.**
>
> **2. Arm A1 — making the count feed itself — destroys the RESPONSE and leaves the LEVEL alone** (ADR 0113).
> Error against FIT grows 0.60 → 1.41 stems/patch over 12 years, **1.72 by year 80 and then stops**, bias never
> above **+0.16 on a mean of 8.28 (< 2 %)** and flat after year 20 — **no runaway.** But the area-weighted global
> count response ratio goes **+0.707 → −0.226 (WRONG SIGN)**, temperate 0.93 → 0.45, boreal 1.07 → 0.70,
> tropical −0.51 → −3.62. ⇒ **for counts the LEVEL is not what fails ADR 0106 — the RESPONSE is**, and A1 is a
> **strict lower bound** (six other roster-state features still come from FIT), so free-running can only be
> worse.
>
> **3. THE PER-CELL DEATTENUATED COUNT SLOPE IS RETIRED AS A DISCRIMINATOR.** Three arms spanning R²
> 0.982 → 0.962 → 0.918 and a global response ratio spanning **+0.707 → +0.685 → −0.226** all score it between
> **0.976 and 1.029**. Do not use it to support any claim about the emulator's response. For counts the primary
> statistic is the **area-weighted aggregate ratio + its latitude bands**; per-cell is a secondary quoted only
> with the null beside it.
>
> **4. DO NOT build a level anchor for the global count recursion.** ADR 0113 §2d measures no runaway, and
> ADR 0105 already measured the anchor harmful on the patch ensemble. A future arm claiming a runaway must show
> it on ADR 0113's lead-time table first.
>
> **5. An offline S-only arm CANNOT measure recursion damage to the TRAIT axes** (ADR 0113 §2e). The trait
> sampler is conditioned on four flux columns + static climate + constant CO₂ — no roster state, no lagged
> trait — so nothing a state recursion does can reach it. Trait free-running error is inherited from the fast
> core's fluxes ⇒ rung 3/4, line M. Arms C/D are still scoreable on the trait axes, but **only on the one-step
> basis, and every such verdict must say so** — including `trait_mortality`'s flip criterion, whose text is
> unchanged.
>
> **⚠ SUPERSEDED BY THE ABOVE — sentences still present further down this file:** (a) item 3's / §5b's
> "**counts already respond faithfully per cell (deattenuated 1.01)**" and "**do NOT write 'the warming response
> is indistinguishable from zero' any more**" — a null scores 1.029, so the per-cell number is not evidence, and
> free-running counts respond with the WRONG SIGN; (b) "**the tropics respond the wrong way — a concrete,
> localised target**" on COUNTS — the null does that too, so it is a property of the statistic, not a defect to
> go and fix; (c) every "aggregate ratio" quoted as **0.691** (and the null's 0.536) is the **unweighted**
> definition, mislabelled — area-weighted they are **0.707** and **0.685** (ADR 0113 §5 corrects ADR 0111 §4b
> and ADR 0112 §3; the conclusions they supported are unchanged). The rest of item 1/2/3 — the noise floor, the
> λ table, aggregate-over-per-cell, the TRAIT panel — **stands unchanged**.

> **✅ THAT DIAGNOSTIC IS ALSO DONE — ADR 0114** (job 1747677, `scripts/rung1_response_decay.py`, 2 min, no
> refit). Two results, both decision-bearing:
> * **the recursion is NOT regressing to a conditional mean** — at lead 80 it still carries `sd(pred)/sd(truth)`
>   **0.904** and **corr 0.940** ⇒ **DO NOT build a variance-preserving or distribution-sampling count predictor
>   to fix this.** Any such proposal must refute ADR 0114 §1 first. What breaks is a **lead-dependent level
>   drift** (+0.155 stems/patch, saturating) that is **the same size as FIT's entire global count response
>   (≈ −0.14 stems/patch)** and differs between scenarios because ssp370 chains run 80 yr and historic 19.
> * **the validity horizon:** at ONE step the count response is right in **every band (0.90–1.07)** — the best
>   evidence yet that the count model does respond — then temperate decays 1.07 → 0.95 (5 yr) → 0.77 (10) →
>   0.59 (20) → 0.45 (80), the tropics go wrong-signed, boreal holds/overshoots to 1.36 first. Controlled
>   against the one-step arm on identical rows: **indistinguishable up to ~3 yr, inverted by 40.**
> * ⚠ **ADR 0114's ratios are on ITS OWN basis** (the table's own seed-1 truth, 53 607 cells): one-step +0.835 /
>   A1 −0.635 there vs **+0.707 / −0.226** on the yardstick. Signs and ordering agree, magnitudes differ up to
>   2.8× — **never quote a decay ratio against the yardstick's number.**

> ## ✅ BOTH DRIFT ARMS ARE DONE, AND THE DRIFT HAS A NAME NOW (2026-08-11, ADR 0115)
>
> The two experiments ADR 0114 pre-registered are run, on all 121 495 658 rows and both scenarios; total
> compute ~10 min in 4 jobs (1753653, 1753655, 1753666, 1753667). Both hypotheses are **refuted**, and the
> refutations point somewhere better:
>
> **1. Training the count model on the year-on-year RATIO instead of the level is worse on every axis**
> (arms R0 teacher-forced / R1 recursed, `scripts/rung1_count_ratio_arm.jl`). Five arms in one yardstick
> process: R² **0.9824 / 0.9622 / 0.9742 / 0.9182 / 0.6778** and aggregate area-weighted response
> **+0.707 / +0.685 / +0.766 / −0.226 / −1.099** for A0 / null / **R0** / A1 / **R1**. One-step the ratio target
> is a small real gain (+0.766, tropics −0.15 vs −0.51); recursed it collapses — drift +0.408 vs A1's +0.155 at
> lead 20, and a top prediction of **799.5 stems in a patch whose observed maximum is 42**.
> ⇒ **THE LEVEL TARGET IS ITSELF THE LEVEL ANCHOR** — a forest predicting `n_t` cannot leave the training range
> `[1, 42]`; a product of 80 biased multipliers can. **Do not propose another target form without beating
> ADR 0115 §1's table**, and note this retro-explains ADR 0113's "no runaway to anchor".
>
> **2. The sign inversion is NOT an unequal-chain-length artefact — ADR 0114 §2's stated cause is wrong.**
> Scored at MATCHED LEAD DEPTH (each cell's two scenario means built lead by lead over only the leads present
> in both, equal weight; mean 18.2 shared leads): GLOBAL **A1 −1.52, R1 −4.91, one-step control +0.52 on the
> same rows**. ⚠ Matched-lead scoring saturates at 19 yr (where the historic chains stop), so k = 20/40/80 are
> the same rows — never present them as three horizons.
>
> **3. WHAT THE DRIFT ACTUALLY IS, and this is the finding: the recursion's bias depends on the climate it is
> run under.** Bias at exactly lead s, by scenario (stems/patch): historic −0.014 → −0.070 (5) → +0.024 (18)
> while ssp370 −0.013 → +0.001 → **+0.150**, so the part that does NOT cancel grows monotonically
> **+0.002 → +0.071 → +0.126** against a one-step control's +0.002 → +0.024 → +0.051. FIT's own global count
> response is **≈ −0.14 stems/patch** ⇒ at lead 18 the recursion manufactures **90 % of the true signal with the
> opposite sign**. The failure is **not** inaccuracy (level bias < 2 %, 90 % of the spread survives) — it is that
> the error is **climate-dependent**, which eats exactly the difference ADR 0106 is about.
>
> **4. ADR 0114 §5.4 is closed:** the control's per-band columns print at every horizon and are flat
> (temperate 1.07 → 0.95, GLOBAL +0.90 → +0.83) against the arm's 1.07 → 0.45 / +0.93 → −0.64 ⇒ ADR 0114 §3's
> per-band decay curve is the recursion's, not the row subset's. At lead 1 A1 and the control agree in every
> band, which also confirms the arm scripts' refit reproduces the production forest exactly.
>
> **5. The retired per-cell deattenuated slope stays retired** — five arms spanning +0.766 → −1.099 all score
> between **0.976 and 1.044**. Third demonstration.
>
> **6. ⚠ A UNITS CORRECTION you may see referenced:** `rung1_response_decay.py` divided the already-per-patch
> `n_living` by the ensemble size a second time. Every **ratio** it ever produced is unaffected (the factor
> cancels), so ADR 0114's ratios/sd-ratios/correlations stand; only its **level** panels were 25× too small for
> their label. ADR 0114 §1's mean row is on the old scaling and is flagged there rather than re-scaled.

> ## ✅ THE CHANNEL IS NAMED, AND THE DRIFT HAS A MECHANISM (2026-08-11, ADR 0116)
>
> ADR 0115 §6.3's diagnostic is run — `scripts/rung1_drift_attribution.py`, no refit, 3 jobs of ~4 min
> (1753852, 1753855, **1753886**), all 121 495 658 rows, 49 282–52 613 cells at leads 5/12/18, area-weighted.
>
> **1. The channel is the STAND STATE, not the climate.** Univariate r with the excess drift at lead 18:
> `n_prev` **−0.336**, `age_mean` **+0.330**, `hmean` +0.269 — and **every climate and flux feature at
> |r| ≤ 0.084** (`gdd_5` −0.084, `tas_cold_month` −0.043, `water_stress` −0.042, `growth_eff` +0.001).
> Forward selection picks `n_prev` → `age_mean` first at both deep leads. **The control discriminates:** on
> identical cells the one-step predictor's own asymmetry is R² **0.096** vs **0.250**, selects `growth_eff`
> first, and its `n_prev` correlation is ≈ 0 ⇒ the one-step error runs through the FLUXES, the recursion's
> extra error through the STAND STATE. **Uniform in all four latitude bands** ⇒ the wrong-signed tropics are
> not a separate defect needing a separate fix.
> ⇒ **DO NOT propose adding or re-weighting a climate/flux conditioning feature to fix the drift** without
> refuting ADR 0116 §2 first.
>
> **2. THE FINDING — the recursion's error is ONE-SIDED: it follows FIT's stem GAINS but not its LOSSES.**
> At lead 18, where FIT loses most (−4.32 stems/patch) the arm drifts **+0.575**; where it gains most (+4.17)
> only **−0.157**. As the fraction of FIT's own response reproduced: **86.7 % of a large decline vs 96.2 % of a
> large increase** (89.9/98.1 at lead 5; 87.1/94.6 at 12). FIT's global response is a net LOSS, so the
> rectified error lands on the loss side as a spurious POSITIVE drift — **ADR 0113's wrong-signed aggregate
> response, explained.** Confound-controlled twice: the **excess** column cancels the `−Δtruth` term by
> construction (2.6× asymmetry on it), and it is **not density** — the extreme deciles differ only **1.3×** in
> stem count while the drift differs 3.7×, and 3.0× survives normalising by it.
>
> **3. Pre-registered criterion for the NEXT count arm: score it ON THE LOSS SIDE.** A fix works if
> decile-1 excess drift falls from **+0.377** (lead 18) **without decile 10's magnitude rising** — the
> aggregate response ratio alone cannot separate a real fix from a compensating positive bias. Regenerate the
> table with `scripts/rung1_drift_attribution.py` (same `FIT_LEADS`, same imported `lead_index`).
>
> **4. Two method rules this bought** (both in the `slow-drf-pipeline` skill): a regression on
> weighted-**centred** columns explains a SPREAD and is **blind to the MEAN**, so any drift attribution needs a
> mean-bearing panel (a binned table) beside it — the pre-registered form reached R² 0.14–0.25 and could say
> nothing about the mean that inverts the response; and **open every extension with a reconciliation panel**
> against the ADR it extends (ten lines here, reproduced ADR 0115 §3's arm row exactly).
>
> **5. ⚠ Correction recorded, not edited: ADR 0115 §3's control row at lead 5 reads +0.024; it should read
> +0.031** (its own CSV's lead-4 value, copied one row off). No conclusion of ADR 0115 changes.

> ## ✅ THE S→M INTERFACE IS ANSWERED, AND IT UNBLOCKS ARM C (2026-08-11, ADR 0117)
>
> M raised the rung-2 demography interface on 2026-08-10 and re-raised it in ADR 0120 §1 (*"S has not yet
> replied"*). **Replied** — ADR 0117, and an ▶ INBOUND block at the head of `lines/M/STATE.md`
> (mirrored here; if a rebase conflicts on that file, **keep BOTH sides**).
>
> **1. S returns option (c)** — a per-individual survival factor `f_i ∈ [0,1]` per tree of the C's `pre`
> roster, keyed by `(pft_id, treeidx)`; **M does the Bernoulli draw**. Decided by ADR 0046: FIT's warming
> trait shift is **51.3 % within-PFT + 26.6 % interaction**, and +112 % *within age class* — with traits
> immutable after `new_tree`, that can only be differential survival, so **a count-only interface cannot
> reach the trait half of ADR 0106 in principle.** (b) borrows the C's hazard *ordering* ⇒ upper-bound
> control only. (c) over (a) because FIT is itself probability-then-draw, and ADR 0101's seed ensemble is
> then a re-run of M's harness rather than of S.
>
> **2. THIS IS ARM C, AND IT NEEDS NO NEW MODEL.** `trait_mortality` (ADR 0047→0049) already emits exactly
> this shape: `f_i = (1 − mort_i)^θ`, θ bisected so `Σ nind·f_i = ρ·Σ nind`. **C0** = `f_i = ρ` everywhere
> (the shipped uniform thinning = the no-selection null); **C1** = the tilted factors. **C1 − C0 measures
> how much of the trait response is selection.** The blocker on arm C was never the operator — it was that
> S has only a single-cell Hainich rollout and the arm needs a ROSTER. **M's harness is that roster**, so
> the option in the old handoff ("build a global offline demography rollout") is superseded: **do not build
> one.** Arm C runs inside rung 2, on M's harness, as an integration point already accepted on both sides.
>
> **3. The harness also retires ADR 0049 item 4's limitation** — `mort_water`/`mort_temp` are zeroed offline
> because S has neither of FIT's stress integrals, but the C's `pre` record carries `water_stress`,
> `temp_stress`, `bm_inc_counter` and `bm_inc`, so **all four hazards run faithfully for the first time**.
> That borrows the C's *state*, not its *decision* — rung 2's premise, not (b)'s problem — and any result
> must say so.
>
> **4. ⚠ THE RISK TO MEASURE FIRST: the count channel may bound the selection.** At Hainich θ median was
> **8.5e-12**, θ > 0.5 in only **18 of 132** thinning years, because the count model's demanded `|ρ−1|` has
> median 0 %/yr against the hazard's 1.688 %/yr (ADR 0049 item 5). **Read θ before interpreting any
> C1 − C0 difference** — a null may mean the count gave the selection no room, not that selection is absent.
>
> **5. Arm D (the bounded-Beta recruit marginals) is NOT unblocked by this** and is still unscoped. Same
> rule as before: it needs a roster, so it belongs in the same harness — **do not quietly score it on the
> one-step copula table and call it the flip test** (that would repeat ADR 0104's error).
>
> **6. Verified while answering, and it closes M's open question:** `k_root` — one of the three recruit axes
> the hook leaves on the C's own draw — is a **scalar 0.02 for all seven tree PFTs** in the live parameter
> file (the sampled-interval form is commented out at every entry) and carries **exactly one distinct value
> over all 206 561 574 tree rows**. Leaving it to the C is an **identity**, so the four-axis recruit
> interface is complete. `emax`/`beta_2` are emitted nowhere ⇒ not measurable from `ind`; say that rather
> than assuming either way. The four axes ARE mutually correlated within (PFT, age bin) — `SLA~D95max`
> −0.292, `SLA~minwscal` +0.251 — so they must be consumed as a **set**.

> **⏩ ONE-LINE ANSWER TO "WHAT DO I DO?" (refreshed 2026-08-11 after ADR 0118): arms C and D are now BOTH
> scoped, and each came back with a defect that had to be fixed before the arm could mean anything —
> C rests on a training target its own ADR had already invalidated (0118 §1–4, amended into M's STATE), and
> D's motivating number has no reproducer (0118 §5). **The OWNER then steered the fix (item 5 above): port
> FIT's establishment rule instead of learning a recruit marginal.** So, in order:
>
> 1. **PORT FIT's ESTABLISHMENT RULE into the recruit channel** (owner steer, item 5). Uniform on each PFT's
>    own interval + the top-AGB seedbank inheritance channel + the closed-form mix `4/(4 + n_elig)`. No
>    training data, no new artifact version, nothing needed from M. **Ship it opt-in and default-off**
>    (guardrail 4) and **pre-register the flip criterion in the same ADR** (guardrail-4 corollary — three
>    flags have already rotted in the off position). The measurement that decides it is the feedback-loop
>    risk: does the recruit channel, once fed by the emulator's own community, go climate-dependent the way
>    the count recursion did (ADR 0112–0116)?
> 2. **RE-ESTABLISH ARM D's BOUNDED-BETA COMPARISON LIKE-FOR-LIKE** — a bounded Beta fitted per cell and
>    scored K-fold-by-cell out-of-sample on `score_slow_copula_ks.py`'s own basis, not against oracle
>    moments. Cheap, offline, on tables that already exist, and it decides whether arm D is worth running.
>    ⚠ Note (1) may make (2) moot: if establishment is ported rather than learned, the marginal family
>    question changes shape. **Do (1) first.**
>
> Everything else on the count side is finished; arm C itself belongs to M's harness.**
>
> Two things NOT to do, both now on the record: do not start a global offline demography rollout (ADR 0117 §2
> — M's harness is the roster), and do not "fix" the copula by re-fitting it to young stems (ADR 0118 §5 —
> the `ind` parquet contains no recruits at all; the target only exists inside M's rung-2 dump).
>
> **(i) Arms C and D, with their scope stated honestly.** ⚠ **Neither is an offline-table arm.**
> `trait_mortality` selects *which individuals* die by trait, and the bounded-Beta family replaces the recruit
> marginals — both need a ROSTER, so both are demography-rollout arms. Today the only rollout harness is
> single-cell Hainich (`scripts/trait_mortality_arm_probe.jl`, and ADR 0101: **one run of it is not a
> measurement** — quote mean ± SEM over ~8 seeds). Options, pick deliberately and record the choice: build a
> global offline demography rollout (real work, and it overlaps line M's rung-2 harness — raise it as an
> integration point before starting), or run C and D at the biome-cell set with the seed ensemble and label the
> result "5 of 54 020" (guardrail 6). **Do not quietly score C or D on the one-step copula table and call it
> the flip test** — that would repeat ADR 0104's error in a new place.
>
> **Score everything with `scripts/diagnose_truth_yardstick.py`** — `COUNT_DIR` takes a comma-separated list so
> an arm, its null and the control are scored in ONE process on ONE cell set (jobs 1747662 and 1753655 both did
> five-way). Always pass `OUT_SUMMARY` to a scratch path for an arm run; the committed
> `S_truth_yardstick_summary.csv` is rung 0's table and no arm has earned a place in it yet. **Do not invent a
> new metric and do not re-derive a noise floor.**
>
> **Integration point you own one side of:** S → M, the demography entry point the C hook will call in rung 2.
> M owns the harness; you own the shape of what it calls. ⚠ ADR 0113 §2e makes this *more* urgent: the trait
> axes' free-running error is only measurable on M's harness, so the rung-2 interface is now on the critical
> path for the trait side of the acceptance criterion, not just for counts.
>
> **Four integration points raised.** Three on the integrator-owned `EXECUTION_PLAN.md`: rung 0's superseded
> numbers (replacement text = ADR 0111 §3/§4/§7); rung 1's arm list, whose A/B collapse into one already-done
> arm (replacement ladder = ADR 0112 §4b); and rung 1's exit criterion, which should now name the
> **one-sided loss drift** it has a mechanism for (ADR 0116 §5.1) rather than the response ratio alone.
> Fourth, on CLAUDE.md §9: **line S's ADR block 0100–0119 has three numbers left** — the next block needs
> allocating before it runs out mid-session.


### 0☆ ⛳ THE PROGRAM CHANGED — `EXECUTION_PLAN.md` IS NOW THE ORDER OF WORK (owner-approved 2026-08-07; ADR 0093 + 0094)

**Read `EXECUTION_PLAN.md` before planning anything.** The project now runs as a strict **error-attribution
ladder**, because offline Component S (98.2 % of count variance) and the coupled driver (terminal density
0.52–1.38×) were being measured together and ADR 0105 proved they cannot be one error — *"offline bias predicts
the coupled error with the wrong size in every cell and the wrong sign in two."* **Do not climb two rungs at
once. Do not report a coupled score without the isolated ones beside it.**

Two owner decisions re-rank everything:

* **ADR 0094 — per-year ESM speed is now goal #2, ahead of everything except fidelity.** The spin-up saving is
  explicitly *not* the goal (*"boring and not my main goal"*). ⚠ And the measurement that forced it: **the
  shipped Julia emulator is 3.8× SLOWER per cell-year than the C model it replaces** (1.096 vs 0.290–0.383
  core-s), because its per-individual daily step costs **51×** the C's. **Never claim "faster than LPJmL-FIT"
  without a measured end-to-end number that names the atmosphere it is against.**
* **ADR 0093 — the patch ensemble is NOT the bottleneck.** The ~100× decomposes as **37× single-core
  engineering + ~3× patches**. Price every speed proposal against the **Julia** cost model, never the C's:
  four candidate architectures looked good against the C and are all slower than the existing code at 8 patches.

Three things that change how you score anything (skill `residual-diagnosis` §5):

1. **At the production `npatch=25` the C's own answer is already outside the 10 % band** — and **ALWAYS SAY
   WHICH BASIS** (ADR 0111 §3; the two differ by 2–3× and both are correct for their own question).
   **Per-cell-YEAR** (a single year's full roster): counts 8.59 %, carbon 11.93 %, and in the <2 stems/patch
   stratum **27.0 % / 37.2 %** — the basis ADR 0093's 31.6 %/42.7 % lives on, though ⚠ **those two are NOT
   exactly reproducible (~14 % gap, unresolved): the year, dead stems and grass inclusion were each tested and
   ruled out (job 1743684), leaving an undocumented difference in that record's per-cell estimator.** Use a
   floor you can regenerate with one command and whose population is stated (here: survivors, `Type<=6`, ÷ the
   configured `NPATCH=25`). **Per-cell 20-yr
   climatology**: counts 6.77 %, carbon 10.16 %, sparse stratum 16.6 % / 25.3 %. **`D95max` exceeds 10 % in
   EVERY density stratum** (10.1–15.4 %, still 13.7 % in the densest) — its per-cell median is simply not a
   10 %-resolvable quantity here. Carbon at 10.2 % globally ⇒ ADR 0106's `max(10 %, …)` branch binds for
   carbon almost everywhere. **Quote a noise floor with every fidelity number, and name its basis.**
   Committed table: `test/testitems/references/S_truth_yardstick_summary.csv`.
2. **The 25 patches are worth `n_eff` 4.8–12.9**, not 25, because the cell-level seedbank couples the
   *inherited* trait pool. The control that proves it: median **Height** — same stems, not inherited — is
   `n_eff ≈ 25`.
3. **The per-cell trait response is not an observable in single-seed truth** (the two seeds disagree on the
   response's *sign* in 18.7–42.2 % of cells; per-cell S/N 0.50–3.14). Score responses on a multi-seed mean
   and **deattenuate**. ⚠ **THE PANEL THAT USED TO BE HERE WAS WRONG THREE WAYS AND IS CORRECTED BY
   ADR 0111** (λ and the deattenuated slope were swapped in two rows of ADR 0093 §3e; the two factors were on
   different bases; and a per-patch density had been divided by *occupied* patches). On one self-consistent
   basis, 51 767 of 54 020 cells, both scenarios, 2-seed deattenuated: **SLA 1.28 — OVER-responds by ~30 %**
   (it was read as "already correct at 1.08"), **minwscal 1.06 — correct**, **Wooddens 0.66 — the WORST
   axis**, **D95max 0.73 — NOT the worst** (its raw 0.163 is mostly attenuation: λ = 0.198, the only
   quantity with per-cell S/N below 1). **The target is 1.0, not as-high-as-possible** — above 1.0 a bigger
   slope is worse, which is the one reading of ADR 0109 that does not survive. **Stop writing "four broken
   axes" AND "two broken axes at 0.63/0.51".**

**Refuted, do not re-propose** (ADR 0093 §4, with numbers): one big patch · structural stratification/quadrature ·
time-averaging instead of ensemble-averaging · a smooth trait density with no individuals · a roster ensemble
without daily physics.

#### YOUR ASSIGNMENT — **rung 0 is DELIVERED (ADR 0111). START RUNG 1.**

**✅ Rung 0 — fix the yardstick — DONE, 2026-08-10, ADR 0111.** All three deliverables, on **51 767 of the
54 020 tree-bearing cells** (≥30 stems in all four runs), **both scenarios and the response between them**, no
new model runs, ~15 min of compute in 6 jobs. Do **not** redo it; **use it**:

```bash
# stage 1 (already run; rerun only if the ground-truth tables change) — jobs 1743333 / 1743334
export SCENARIOS=historic SEEDS=1,2 CAP=400 OUT=/p/tmp/jamirp/emulator_global/yardstick_v1
scripts/sbatch_python.sh S-yardhist scripts/build_truth_yardstick_tables.py
# stage 2 — score ANY copula table's OOS predictions on the ONE canonical basis
export YARD=/p/tmp/jamirp/emulator_global/yardstick_v1 BASIS=capped400 PRED_DIR=<dir1>,<dir2>
export COUNT_DIR=/p/tmp/jamirp/emulator_global/slow_count_pooled_w20_t8    # optional: scores the COUNT side too
scripts/sbatch_python.sh S-yardscore scripts/diagnose_truth_yardstick.py   # jobs 1743409/1743410/1743515
# ⚠ every knob above must be EXPORTed — sbatch_python.sh forwards only a fixed list (CLAUDE.md §9)
```

- **The floor** is item 1 above; the machine-readable table is
  `test/testitems/references/S_truth_yardstick_summary.csv` (272 rows: floor × 2 bases × 2 scenarios × 6
  density strata · reliability · aggregate response × 5 latitude bands · re-scored slopes).
- **The deattenuated panel** is item 3 above. **λ for 1/2/4 seeds** (capped basis): counts .908/.952/.975 ·
  carbon .616/.762/.865 · SLA .645/.784/.879 · Wooddens .510/.676/.807 · **D95max .198/.330/.497** ·
  minwscal .640/.780/.877 · Height .315/.480/.648 · Age .604/.753/.859. ⇒ **the two extra seeds are worth
  more than they looked**: they roughly halve the attenuation on exactly the two axes that matter.
- **The aggregate response is now the PRIMARY response statistic**, per-cell a reported secondary:
  area-weighted S/N **25–489** vs per-cell 0.5–3.1. Global: stems/patch −1.74 %, above-ground C −0.54 %,
  SLA −1.58 %, Wooddens +0.74 %, D95max +1.19 %, minwscal +1.27 %, Age −4.43 %. **Report the latitude bands
  too** — above-ground C is −1.5 % tropical / −3.9 % temperate / **+19.4 % boreal**, so the global mean alone
  calls a model that gains a fifth of its boreal stand carbon "almost no carbon response".
- **★ THE COUNT RESPONSE IS FAITHFUL, and it is the first quantity ADR 0106 names** (ADR 0111 §4b, from the
  pooled count table's own OOS predictions, `COUNT_DIR=…/slow_count_pooled_w20_t8`): raw slope 0.958, λ
  0.908/0.952, **deattenuated 1.056 (1-seed) / 1.006 (2-seed)**, with a **r = 0.9948** cross-check between the
  count table's own seed1 response and this reduction's (two independent code paths — the ADR-0030 check).
  ⇒ **do NOT write "the warming response is indistinguishable from zero" any more; that is not true of
  counts.** The response error lives in the trait axes.
- **★ SCORE THE BAND, NOT THE GLOBE — a positive global response ratio HIDES WRONG-SIGNED REGIONAL
  RESPONSES** (ADR 0111 §5b). Area-weighted prediction ÷ truth by band (`n/d` = the truth's band response is
  undetermined, S/N < 3):

  | quantity | GLOBAL | tropical | subtropical | temperate | boreal |
  |---|---|---|---|---|---|
  | stems per patch | +0.71 | **−0.51** | +3.41 | +0.93 | +1.07 |
  | SLA | +1.94 | +0.69 | **−3.91** | **−0.29** | +3.19 |
  | Wooddens | +1.06 | +0.86 | +1.23 | +0.43 | +1.40 |
  | D95max | +1.75 | **n/d** (S/N 1) | +1.09 | +3.08 | +1.75 |
  | minwscal | +2.95 | +3.62 | +1.80 | +1.22 | **−4.45** |
  | Height *(diag)* | +2.88 (S/N 4) | +1.51 | +1.00 | +1.42 | +0.92 |

  **Four wrong-signed band responses no earlier statistic could see.** The count story is NOT "31 % too weak":
  temperate (0.93) and boreal (1.07) are right and **the tropics respond the wrong way (−0.51)** — a concrete,
  localised target. **Wooddens is the best-behaved axis in aggregate (0.43–1.40) while having the WORST
  per-cell slope (0.66)** — the right total in the wrong places. Per-cell pattern and regional total are
  different questions; publish both.
- ⚠ **A RATIO WITH AN UNDETERMINED DENOMINATOR IS NOT A NUMBER — this bit THIS session.** A draft of ADR 0111
  reported "the emulator delivers 14 % of the truth's height response" from an *unweighted* mean-ratio;
  area-weighted the same quantity is **2.88**, Height's global S/N is **4** (weakest of any quantity), and the
  band ratios say Height is roughly RIGHT (0.92–1.51). **Neither 0.14 nor 2.88 is a result.** The script now
  keeps exactly ONE definition (area-weighted) and prints `n/d` below S/N 3. Do not reintroduce a second one.
- ⚠ **`Height` fails the basis-robustness check** (deatt 1.05 capped vs 0.85 uncapped) — quote it as a range,
  never a number. The four production axes move ≤3 % between bases, which is what licenses steering by them.
- ⚠ Everything here is **OFFLINE** ⇒ an upper bound on the coupled model (ADR 0105 §5).

**▶ INTEGRATION POINT RAISED BY LINE S (2026-08-10) — `EXECUTION_PLAN.md` rung 0 quotes superseded numbers**
(the swapped λ/deattenuated pair, and the `<2` stratum tolerances with no basis named). That file is
**integrator-owned**, so this line does not edit it. The replacement text is ADR 0111 §3, §4 and §7.

*(The integrator is separately scheduling two more reference seeds, ~35 000 core-h ≈ 17 h on 2048 cores — the
λ table above is the quantitative case for them.)*

**Rung 1 — S alone, on the C's OWN fluxes.** No C/Julia mixing needed: **the `ind` parquet already IS the C's
fast part** — per (Cell, Patch, Year) it carries each tree's growth, water stress and four death rates. Run
four arms and report all: **A** free-running (control) · **B** fed the C's own per-tree fluxes · **C** = B +
`trait_mortality` ON · **D** = C + the bounded-Beta trait family replacing the copula marginals.

⚠ **PRE-REGISTERED, so it cannot be reinterpreted later: if rung 1 scores WORSE than the coupled result, that
is THE FINDING, not a failed test.** The owner has agreed the compensating-errors hypothesis is plausible —
S may have been tuned while F was biased, two errors that cancel today and stop cancelling under warming.
Teacher-forcing already made the score worse in **all five** cells (0.149→0.277, 0.086→0.153, 0.180→0.259,
0.349→0.460, 0.029→0.069), which is backwards. That would also explain the flat warming response directly.

Three cheap wins to fold in and measure **separately** (ADR 0093 §5): the **determinism dividend** is free —
predicting the ensemble expectation rather than a draw is worth **+2.9 to +14.4 pp** of cells inside the 10 %
band; a **bounded Beta on each PFT's own trait interval** beats the shipped copula 2–3× on per-cell KS
(**0.042–0.073** vs 0.129–0.173), two moments, no fitting; and `trait_mortality` holds the wood-density
selection differential at **0.98–1.06 across all seven PFTs** provided `mort_max(wooddens)` stays
**per-individual** (collapse it too and it flips sign in PFTs 3, 5, 6).

**FLIP CRITERION for `trait_mortality`** (pre-registered, guardrail-4 corollary — decide from arm C vs arm B
only, and do not re-read it after the fact): flip the default ON if C improves the **deattenuated Wooddens
response slope** by ≥ +0.10 over B **and** loses ≤ 1.0 pp of cells inside the 10 % band on every trait axis
and on counts. **This is now measurable exactly as written, and the number to beat is on the record:
Wooddens deattenuated is 0.66 (2-seed) / 0.69 (1-seed).** Score every arm with
`scripts/diagnose_truth_yardstick.py PRED_DIR=<arm>` so all arms share the one basis, and read the level
guardrail against item 1's stratified tolerances rather than a literal 10 %.

**Integration point you own one side of:** S → M, the demography entry point the C hook will call in rung 2.
M owns the harness; you own the shape of what it calls. Record it in both STATE files.

---


### 0★ 🎯 THE ACCEPTANCE CRITERION — READ THIS BEFORE PLANNING ANYTHING (owner, 2026-08-06; ADR 0106)

The owner has stated what **finished** means, and it **supersedes every per-milestone stopping condition on
every line**, including "at the seed1-vs-seed2 noise floor" and any five-cell verdict read as sufficient:

> the emulator must **fully emulate the original model**, "of course also and **especially under climate
> change**"; done = **everything, including trait distributions AND medians, within 10 % error**; and it is
> "**only finished when it's proven to be correct on ALL cells, not only a handful of test sites**".

**All cells = the 54 020 tree-bearing cells.** **Both scenarios AND the response between them.** A noise-floor
statement is a *diagnostic*, not the acceptance test, and **no line may call a milestone done on a five-cell
result** — nor present one as fidelity evidence without saying it is 5 of 54 020.

⚠ One clause carries a stated default, not the owner's words: the original model is stochastic and its own two
runs differ by **29 % of the mean** for the per-patch count in a low-density cell, so a literal 10 % is
unmeetable there by ANY emulator. Default in use: tolerance = **max(10 %, the original's own two-run spread
for that quantity in that cell)**. Full record: ADR 0106.

⚠ **CO2 — STANDING RULE, DO NOT RE-LITIGATE (ADR 0107).** The emulator **does not see CO2 and must not respond
to it**. It responds to **climate**; the SSP scenarios already carry the CO2-driven climate signal, and the
source model runs constant CO2 **on purpose** (no nitrogen limitation ⇒ unbounded fertilization, ADR 0004). An
emulator with no CO2 response **matches the reference**. Never raise a CO2 feature, varying-CO2 training rows,
or a new model run for CO2, and never list it as a defect.

### 📥 INBOUND FROM LINE M, 2026-08-11 (ADR 0122) — **your ported hazard reproduces the C EXACTLY (the free
### identity gate you offered is run and green). One correction to ADR 0117 item 3, and arm C is not yet
### scorable on the trait question — the reason is M's harness, not your operator.**

> Reply to ADR 0117. Nothing is asked of line S. Full record: `docs/decisions/0122-*.md`.

**1. `src/trait_mortality.jl` is verified against the C binary, as an IDENTITY.** ADR 0117 item 4 offered
θ = 1 as a free gate; M ran it against the C's own `mortality_tree_ind` on **all 9 951 tree-patch-years** of
the recorded rung-2 dump (cell 42490, 25 patches, 2000–2019, PFT ids 1/2/3/4/5/6 = 631/275/7 370/1 231/401/43).
Max relative error: `mort_age` 5.0e-16 · `mort_temp` 1.7e-16 · `mort_water` 2.2e-16 · `mort_npp` 1.6e-15 ·
**`mortality_hazard.total` 1.6e-15, zero exceedances** — plus both hard kills classified correctly (175
growth-failure, 195 ghost-tree, 3.7 % of records). So **ADR 0049 item 2's "θ = 1 recovers FIT exactly" is now
measured rather than asserted**, and the operator is safe to build on. It is also locked into CI
(`test/testitems/m_rung2_hazard_identity_tests.jl` + a 333-record C-truth fixture), so a future edit to your
file cannot regress against the C silently. **ADR 0049 item 4 is retired inside the harness** — both stress
integrals are exact there, so the complete four-hazard operator ran for the first time.

**2. ⚠ ONE CORRECTION — ADR 0117 item 3 is wrong on the fourth hazard, and it was worth two rebuilds to
find.** Item 3 states that the `pre` record carrying `water_stress`, `temp_stress`, `bm_inc_counter` and
`bm_inc` means *"inside the harness all four hazards are computable faithfully"*. Three of four: yes,
exactly (`water_stress`/`temp_stress` are byte-identical between the `pre` and `mort` phases in **0 of
9 951** records). But `mort_npp` consumes `bm_delta = bm_inc.carbon/nind − turnover_ind.carbon` with
`bm_inc` taken **post-turnover and post-allocation**, whereas the `pre` record's `bm_inc` is the year's
**gross** NPP — and `turnover_ind` is not reconstructable from the dumped pools (only its two sapwood terms
are; `turn.leaf`/`turn.root` are daily accumulators and `turnover_tree` mutates `bm_inc.carbon` itself). M
therefore added `bm_delta`/`leafarea_real` as dump columns (`patches/lpjmlfit_rung2_hook_v4.patch`), which
is what made item 1 possible. **Nothing about the interface or the wire format changes.**

**3. ARM C IS NOT YET SCORABLE ON THE TRAIT QUESTION — pre-registered, so it cannot be reinterpreted after
a run.** The rendezvous where the C asks for `f_i` sits at the *top* of the annual block, so live it carries
**last year's** `bm_delta`/`leafarea_real`/`bm_inc_counter`. Per-tree **ordering** survives that
(per-patch-year Spearman ρ against the C's own `mort_prob`: median **0.900**). The trait statistic does not:
the one-year wood-density selection differential is the C's **+17 729** gC/m³ against the lagged basis's
**−14 528** — **ratio −0.819, opposite sign**. Attributed one term at a time: hard kills suppressed −0.819
(not them), only `bm_delta`/`leafarea` lagged **+1.001** (the growth lag is harmless), only
`bm_inc_counter` lagged **−0.562** ⇒ **the culprit is the consecutive-growth-failure counter**, which
multiplies `mort_npp` and `mort_water` by `(1+counter)` and whose update needs *this* year's `bm_delta`
sign (`pre` holds the previous value in 21.8 % of records).

**This is M's rendezvous POINT, not your operator and not the emulator** — standalone, the fast core grows
the trees before the demography runs, so the counter is current. M's next C change moves the rendezvous
behind the growth loop, which removes the lag entirely. **Until then a rung-2 arm is readable on counts and
ordering only** — so if you were planning to read a `C1 − C0` wood-density result (and ADR 0118 §3's two
pre-registered conditions are written on exactly that axis), it is worth knowing that the arm cannot carry
it yet. ADR 0118 §3's other condition stands unchanged and is the right one to keep: test the per-PFT
**gradient shape** against `references/S_age_wooddens_gradient.csv`, including the non-monotone ids 0 and 3.

### 📥 INBOUND FROM LINE M, 2026-08-10 (ADR 0061) — **rung 2's observation half is built; the entry point's
### SHAPE is yours, and here is a concrete proposal so you can accept or amend rather than design.**

> **▶ UPDATE FROM LINE M, 2026-08-11 (ADR 0120) — the C side is now COMPLETE, and three facts change the
> menu below. Still nothing owed from you on a deadline, but the answer is now on the critical path for
> the trait side (your own ADR 0113 §2e says trait free-running error is only measurable on M's harness).**
>
> 1. **The read-back exists and is gated.** The C accepts a kill set + a complete recruit set per
>    patch-year and applies them; with the environment variables unset it is numerically identical to
>    the binary you are using (139 decoded quantities, 0 differ). A null control — rendezvous active,
>    every decision handed straight back to the C — reproduces the recorded run exactly over 20 years.
> 2. **All three of your options are supported, so pick on scientific grounds, not feasibility.** The
>    harness normalises whatever you return into a kill set before the C sees it. **But option (b) got
>    worse:** "rank or draw on the C's own `mort_prob`" is awkward, because at the rendezvous the
>    *current* year's hazards have not been computed yet — the C computes them after the roster is
>    handed over. Such a rule would rank on a **one-year-stale** hazard, or need the kill decision
>    deferred until after `mortality_tree_ind`, which is intrusive (`litter_update` fires inline). That
>    is an argument for **(a)** or **(c)**.
> 3. **Your copula covers 4 of the 7 trait axes a recruit actually carries.** `new_tree` samples `sla`,
>    `wooddens`, `D95max`, `minwscal`, `emax`, `k_root` and `beta_2`, and derives leaf `longevity` from
>    `sla`. The hook substitutes your four, re-derives `beta_root` and `longevity` from them as the C
>    does, and leaves `emax`/`k_root`/`beta_2` on the C's own uniform draw. Nothing for you to do — but
>    any rung-2 trait result has to say "4 of 7 axes", and if you think one of the other three matters
>    for the axes you do predict, say so and it can be added to the wire format.

Nothing here blocks your rung 0/1 work. Read it when you next touch rung 1's arms, because the interface
below is the same demography call, driven by the C instead of by the emulator's own physics.

**What now exists.** An opt-in hook in the LPJmL-FIT C binary (`LPJ_RUNG2_DIR`,
`patches/lpjmlfit_rung2_demography_hook.patch`) dumps each patch's tree roster at the **top** of the annual
demography block (`pre`) and again **after** establishment (`post`). It is inert with the variable unset —
138 decoded NetCDF variables + `globalflux` identical to the previous build, so `bin/lpjml` is still the
oracle for your work too. Mechanics + gotchas: skill `lpjmlfit-cbinary`; the record schemas are in the dump
file's own `#H` header lines.

**Why it matters to you specifically: the C holds three per-tree accumulators the emulator does not
produce, and they are NOT in the `ind` parquet** — `water_stress`, `temp_stress` and `bm_inc_counter`.
Three of the four death rates read them (`mortality_tree_ind.c:66-96`). If rung 1's arm B ("fed the C's own
per-tree fluxes") is scored without them, it is fed less than the C's fast part actually provides. The
`pre` record also carries `bm_inc`, `nind` and all seven carbon pools, likewise absent from `ind`.

**The proposal — the narrow interface, `EXECUTION_PLAN.md`'s "replace only who dies and who establishes".**
Per (cell, patch, year) the C hands over the `pre` roster and expects back exactly two lists:

1. **who dies** — the set of `treeidx` values (the C's own `tree->index`, stable across years) to kill;
2. **who establishes** — one row per recruit: `pft_id` plus the four trait axes
   (`SLA`, `Wooddens`, `D95max`, `minwscal`), i.e. your copula's axes. The C builds the pools from the
   traits via its own `establishment_tree_ind`, so nothing else is needed.

**The one thing that is genuinely yours to decide, and the reason this is an integration point rather than
a request.** The shipped demography predicts a per-patch **count** and a recruit-trait distribution — not
which individual dies. Turning a count into a kill set is itself a demographic operator, and M must not
invent it. Three options, all implementable on this side; say which:

* **(a)** you return the kill set directly (the emulator gains a per-individual survival rule);
* **(b)** you return a target surviving count and a *stated* victim rule (e.g. rank by the C's own
  `mort_prob`, or a Bernoulli draw on it renormalised to hit the target) — the C's four hazard components
  are in the `pre`/`post` records, so any such rule is computable;
* **(c)** you return a per-individual survival probability and M does the draw.

(b) is the cheapest and keeps the emulator unchanged, but it borrows the C's hazard *ordering*, which makes
the arm partly a C arm — worth saying out loud in whatever the rung-2 result claims. Your call.

**The control is free.** The `post` records are the C's own answer for the same year, so every arm is
scored against the exact trajectory it replaced, on the same run. Verified: the dump reproduces the run's
own `ind` table on identical tree sets (5 465 trees) across all 21 shared columns to ≤5.0e-6.

**Two facts to design against:** recruits enter the roster at **`age == 0`** (the `age++` is in
`annual_tree`), and the `mort_*` fields are meaningful only in the `post` phase.

⚠ **Also: check whether you have seen M's EARLIER inbound (ADR 0060, the two FPC outputs).** It was written
into this file on 2026-08-06, and it did not reach `main` before you rewrote the head of this file on the
7th; it was re-placed by hand during a rebase on 2026-08-10. If the block above the "MERGED AND GREEN"
section is new to you, that is why — and its content changes two numbers in ADR 0105.

### 📥 INBOUND FROM LINE M, 2026-08-06 (ADR 0060) — **your canopy attribution SURVIVES; two of the FPC
### numbers supporting it were read off the wrong one of the C's TWO FPC outputs. Nothing is owed from you.**

M worked ADR 0105 §5's hand-over. **The attribution is confirmed** — F's canopy does diverge from the C's,
it is M's paths, and M is keeping it. One correction you may be carrying, and one caveat that changes how the
supporting numbers may be quoted:

1. **`annual_natural.c` writes two different FPCs from the same individuals.** `a_fpc` (`FPC`, `:209`) is the
   patch-mean **sum of individual crown covers** (`fpc_tree.c:28`) — the quantity F's `fpc` feature *is*.
   `a_fpc_stand` (`FPC_STAND`, `:218,248`) accumulates per-PFT **leaf area** and applies one Beer–Lambert
   saturation over the whole patch. They differ **1.5–2.3×** in the same cell-year. ADR 0105's `C_fpc`
   column, and ADR 0053 finding 4, are both `a_fpc_stand`.
2. **Your DRIFT ratios barely move** (a same-basis ratio over time mostly cancels the form difference), which
   is why the attribution stands. On the crown basis the C's own 2010→2019 change is **−10.9 %** (boreal),
   −2.6 % (Hainich), −22.9 % (mediterranean), **+25.4 %** (Sahel), −11.0 % (Amazon) against F's +64.5 / +28.6
   / −7.0 / −13.5 / +4.7. Same conclusion, slightly different numbers. `biome_slow_oracle_probe.jl` REPORT 5
   now prints **both** bases (`C_fpc` = crown, `C_fpcBL` = the old one) so neither can be quoted by accident.
3. **The LEVEL claim inside it does not survive.** ADR 0053 finding 4 is **withdrawn**: F does not
   under-predict crown cover in all five cells — it **over**-predicts in four (boreal 1.32, Hainich 1.18,
   mediterranean 1.47, Amazon 1.05) and under-predicts only at `semiarid_sahel` (0.54). So "the count model
   is fed a systematically sparser canopy than the C's" is wrong as stated; the canopy is too *dense* in
   three cells and too sparse in one, which is a different input error per cell.
4. **Two eliminations, so you do not re-derive them.** F's canopy *reconstruction* is faithful (crown cover
   at t=0 over the stems it was handed = **1.00–1.04 in all five cells**) ⇒ not an initialisation defect. And
   **no F-vs-C FPC ratio may be scored against 1.0**: the `ind` writer emits only stems above 5 m, so F's
   stand structurally lacks **29 %** of boreal's and the Sahel's crown cover (0.95–1.02 elsewhere).
5. ⚠ **A `slow = nothing` arm has no mortality and no tree establishment**, so its monotone FPC rise is
   partly expected by construction — a growth-divergence number must come from the **coupled** arm. Yours
   does; M's kernel-isolation one does not.

No committed baseline, artifact or default moved; the new oracle columns are appended with every
pre-existing value byte-identical.

### ✅ MERGED AND GREEN — nothing about this line's work is outstanding

**LATEST (ADR 0110, the per-tree rooting + drought work):** merged to `main` as **`f5c614db`**, and
**`main`'s OWN post-merge run is green** — `test (lts)` ✅ `test (1)` ✅ `test (macOS, lts)` ✅ **`docs` ✅**
(the whole-package gate that never runs on a branch) `format` ✅.
⚠ **It came back RED first, on `test (lts)` AND `docs`, and it was a GITHUB OUTAGE, not the merge:** both jobs
died at `Failed to resolve action download info. Error: Service Unavailable` — before any Julia ran — while
`test (1)`, `test (macOS, lts)` and `format` passed on the same sha and `test (lts)` had passed on the branch
sha minutes earlier. `rerun-failed-jobs` on both runs went green with **zero code changes**. The 30-second
triage (read the failure STEP, check the siblings, check the branch) is now in the **`repo-commit`** skill. Branch CI on
the code-bearing sha `b739cb14`: `test (lts)` ✅ `test (1)` ✅ `test (macOS, lts)` ✅ `format` ✅; `test (pre)`
❌ = the same documented `ScopedValues` prerelease `MethodError` on Julia 1.13.0-rc1, confirmed from the job
log, `continue-on-error`, not ours. Local CI-faithful suite (job **1719485**): **111 775 pass / 0 fail /
0 error**, and **no pre-existing assertion moved** — that is the guardrail-4 byte-identity evidence, since all
three flags default off. ⚠ The FIRST suite attempt (job 1719462) died with **SIGABRT** — see the
`julia-test` skill and CLAUDE.md §2; it was a `Vector` field on `FDiff.Individual`, not the physics.

**Earlier (ADR 0109, the moisture arm):** work merged to `main` as **`362d115d`**, and **`main`'s OWN post-merge run is green**: `test (lts)` ✅
`test (1)` ✅ `test (macOS, lts)` ✅ `format` ✅ **`docs` ✅** (the whole-package gate that never runs on a
branch — §9 note 5's one case that always deserves the look, and it passed). Branch CI on the code-bearing sha
**`c68ee134`**: `test (lts)` ✅ `test (1)` ✅ `test (macOS, lts)` ✅ `format` ✅. `test (pre)` ❌ = the documented
`ScopedValues` prerelease `MethodError` at LOAD time — confirmed from the job log, `continue-on-error`, not
ours. Every commit after `c68ee134` touched only `docs/`, `changelog.d/`, `.claude/skills/`, `MEMORY.md` and
`lines/S/`, i.e. **no gate-watched path**, so the tree CI verified is the tree that landed.

⚠ **The merge was BLOCKED for a while and that is worth knowing about:** the integration worktree had **91
uncommitted files** from an ACTIVE integrator session (a docs reorganization), which makes `git merge` there
fail outright. It was left alone, the branch was left pushed and green, and the merge went through once the
worktree came back clean — no conflicts. The detection procedure (mtime check) and why routing around it via a
detached worktree is *wrong* rather than clever are now in the **`repo-commit`** skill.

### ⚠ A CONCURRENT SESSION RAN ON LINE S IN THIS SAME WORKTREE — the history is interleaved, and `git add -A` is a hazard here

ADR 0110 (`f75b5907`) is a **line-S commit this session did not make**, and it sits *between* two of this
session's commits on the branch. Files in `wt-S` (`MEMORY.md`, `src/LPJmLFITEmulator.jl`) were also modified
externally mid-session. ADR 0028's "one session per line at a time" was therefore **not** holding today.

**Nothing was corrupted** — every commit of this session was audited with `git show --stat` afterwards and each
contains exactly its intended files, and ADR 0110's own files came in cleanly via the rebase. But that was
luck, not care: **`git add -A` in a shared worktree can commit another session's in-progress work under your
message.** If you find yourself sharing a worktree, stage explicitly (`git add <paths>`) and audit with
`git show --stat` before pushing.

**The two lines of work CONVERGED rather than collided** (see item D): ADR 0110 read ADR 0109's numbers
correctly and drew the next conclusion from them. No reconciliation is needed.

### THE STATE IN SEVEN LINES

1. **S2 (the moisture conditioning) is WIRED, GATED, TESTED and PUSHED GREEN — ADR 0108, commit `c68ee134`**
   (merge pending, see the block above).
   `ENV_WINDOW=W` (builder) + `live_flux_cond_env_series` (runtime) + `years.i64` on every table +
   `env_basis` in every copula manifest. All opt-in; default byte-identical, verified against
   `git show <parent>:` rather than a re-run of the new code (job **1718598**). Julia suite **111 289 pass /
   0 fail** (job 1718905).
2. ⚠ **THE FRAMING S2 STARTED FROM WAS FALSE, AND THIS LINE CORRECTED IT ITSELF.** "A frozen moisture tail
   ⇒ the trait response is structurally zero by construction" is **wrong**: that tail is **6 of 14** columns,
   and `water_stress`/`soilmoist` are per-(Cell,Year) while the boundary pair is transient under
   `BOUNDARY_WINDOW`. **Do not repeat the old claim** — every copy of it was corrected in `c68ee134`.
3. **THE BASELINE, MEASURED, GLOBAL, BOTH SCENARIOS** (`scripts/diagnose_moisture_arm_response.py`, job
   **1718922**, shipped `_t8`, 52 074 cells with ≥30 stems in both scenarios, K-fold-by-cell OOS). Per-cell
   response `D = median(ssp370) − median(historic)`, `D_pred` regressed on `D_truth` through the origin:

   | axis | response slope | corr | sign agreement | per-cell median within 10 % (hist / ssp) |
   |---|---|---|---|---|
   | SLA | **+0.85** | +0.45 | 71.9 % | 70.7 % / 67.5 % |
   | Wooddens | **+0.35** | +0.38 | 61.5 % | 71.4 % / 72.2 % |
   | D95max | **+0.16** | +0.20 | 57.5 % | **28.0 % / 30.0 %** |
   | minwscal | **+0.69** | +0.58 | 62.7 % | 62.1 % / 63.8 % |

   ⇒ the **offline** recruit-trait response channel is **partially open, not closed**, and worst on the
   rooting-depth trait. **This is the arm's reference basis: success is BEATING these slopes.** It is also this
   line's first global both-scenario level score — `D95max` at 28 % of cells within 10 % is the largest
   trait-side gap against ADR 0106, and it is now a measured global number, not a five-cell one.
4. **THE ARM REPORTED — the answer is a TRADE, and there is NO FLIP (ADR 0109; jobs 1718904, 1719206).**
   The pairing is **total**: the `_t9` 8-col base `Xc.f64` is **SHA-256 bit-identical** to the shipped `_t8`
   base, and cells/scenario/every `Y_*` match, so all three arms are on the SAME 42 227 077 rows.

   | axis | 8-col `_t8` (M's pin) | 14-col FROZEN | 14-col TRANSIENT |
   |---|---|---|---|
   | SLA — slope / within 10 % | +0.851 / 70.7 % | +0.396 / **74.2 %** | **+0.752** / 73.6 % |
   | Wooddens | +0.346 / 71.4 % | +0.254 / **74.0 %** | **+0.332** / 73.8 % |
   | D95max | +0.163 / 28.0 % | +0.145 / **33.1 %** | **+0.172** / 32.4 % |
   | minwscal | +0.689 / 62.1 % | +0.609 / **66.1 %** | **+0.706** / 65.3 % |

   **The env tail buys LEVEL (+2.6…+5.1 pp of cells) and costs RESPONSE (all four axes)** — six per-cell
   constants are a near-unique spatial ADDRESS. **Transient buys the response back** on all four
   (+0.356/+0.079/+0.028/+0.097) for 0.2–0.8 pp of level; the truth's mean `Wooddens` response is +2406, frozen
   predicts +1529, transient **+2402**. ⚠ **ADR 0037/0038 recommended the tail on level evidence and every
   number in it stands — no response statistic existed then.** The tail was not wrong; the metric panel was
   incomplete.
   **NO FLIP:** ADR 0108 §8 clause (a) fails as written (`D95max` pooled `nqrmse` 0.0120 vs 0.0090; level worse
   by 0.2–0.8 pp on all four) and clause (b) — the coupled screen — was never run. The criterion was **not
   re-read after seeing the numbers**, even though the response gain arguably outweighs the level cost; that is
   what a pre-registered criterion is for. `recruit_copula_global_pooled_w20_t9envT.rcop` exists and is **NOT
   pinned**; M's `_t8` pin is untouched.
   **The criterion was ALSO mis-specified** — it gated on trait *level* while ADR 0106 makes the *response*
   binding. Not edited (that would be ADR 0104's error again); a correct three-clause replacement is registered
   in **ADR 0109 §5** for a NEW arm, and its clause 3 (the coupled ensemble screen vs a matched
   constant-forcing control) is the whole remaining blocker.
4b. ⚠ **TWO CAVEATS ON THE ARM, FOUND AFTER ADR 0109 WAS ACCEPTED (so they live here, not in that
   immutable ADR — neither changes a conclusion, and both must be quoted alongside its numbers).**
   * **The scored estimator is NOT the shipped one, and that is the pre-existing documented split.**
     `run_moisture_conditioning_arm.sh` inherited `NTREES=60` (train) / `EVAL_NTREES=40` (eval) from
     `run_pooled_slow_copula.sh`, so **every number in ADR 0109 describes a 40-tree estimator while
     `_t9envT.rcop` is 60-tree** (verified from the artifact: `ntrees=60`, 3 000 000 stored leaf values on
     axis 1, `ncond=14`, `qrf=false`). **No conclusion moves:** all three arms were scored at 40 trees so the
     comparison is paired and like-for-like, `_t8`'s published numbers are 40-tree too, and `_t8.rcop` is
     *also* 60-tree — so artifact-vs-artifact is like-for-like as well. But never write "the artifact achieves
     slope 0.752" without this sentence. The skill's standing instruction is **set `NTREES == EVAL_NTREES`
     when shipping a generation**; this arm did not, and a future arm should.
   * **The label `t9` is OVERLOADED in this line's vocabulary.** It already named a 2026-07-31 artifact
     (`recruit_copula_global_historic_t9.rcop`, untouched, and the capacity rungs live under
     `capacity/b6x2M` etc.), and it now also names this generation's `slow_copula_*_w20_t9*` tables +
     `recruit_copula_global_pooled_w20_t9envT.rcop`. **Nothing was overwritten** (verified by mtime), but pick
     a fresh, unused tag for the next generation and say which namespace you mean.

5. **Item A of the previous handoff was ALREADY DONE — do not redo it.** The F-canopy attribution is in
   `lines/M/STATE.md` (the `▶ NEW INTEGRATION POINT RAISED BY LINE S, 2026-08-06` block) with the
   offline-vs-coupled table and the `fpc` drift ratios. Nothing is owed by S there.
6. **Nothing about ADR 0105 is outstanding.** The anchor does not get the default (criterion FAILS at all three
   settings on the 25-patch ensemble); teacher forcing is WORSE in all five cells; the exposure-bias retrain is
   **cancelled, measured empty** (−0.0014 stems/patch/yr, AR gain 0.562 ⇒ bounded 2.28× ⇒ −0.4 %). Read ADR
   0105 §6 before throwing out any of that family.
7. **The count DRF is untouched by ADR 0108** — its features are the 11 head columns + the 4-column boundary
   tail. Whether it should also see moisture is a separate question and must be **priced offline first**.

### DO THIS NEXT, IN THIS ORDER

**0★★ THE ROOTING-DEPTH TRAIT NOW HAS A PHYSICAL CONSUMER — finish landing it (ADR 0110). THIS IS THE
DROUGHT-RESPONSE WORK AND IT SUPERSEDES A★/A2 IN PRIORITY.**

The owner's instruction that opened it: *"drought response is one of the most important features our
emulator has to capture."* ADR 0109 finished the *statistical* search on `D95max` — worst of four axes on
all three arms, no flip. What was left is that **the trait had no consumer**: `make_recruit_to_pools` wrote
only SLA + Wooddens, and `daily_step_canopy` collapsed the 23-layer profile to ONE scalar `wr` before the
individual loop opened. Two trees differing only in rooting depth were identical in the water balance.

**The standing DEFER (`docs/water_supply_perpft_design.md`) does NOT cover trees.** Its "rooting depth is
not the mechanism" rests on grass sharing beech's `beta_root=0.8` — grass vs the AVERAGE tree. Tree-vs-tree:
`beta_root` is per individual from that individual's own `D95max` (`new_tree.c:229-230`), the trait spans
**51-1800 cm within one PFT**, top-20 cm root share **69 % vs 4 %**. And the `-DPERMUTE` randomness that
blocks a faithful `aet_cor` port **does not touch** per-individual `wr`, `supply`, `pft->wscal` or the
routinely-firing "own FPC share" cap — all four are order-INDEPENDENT (`soil.w[]` is frozen for the whole
loop, written once per patch-day afterwards). ADR 0110 §3 has the table. **Cap (ii) is out of scope,
deliberately, and is NOT "impossible" — it is "reproduce the average over orders", over only 6-12 individuals.**

**Measured first, on the C's own per-stem output** (`scripts/diagnose_per_tree_water_access.py`,
pre-registered criterion, 5 biome cells, both scenarios): across-tree p5-p95 water-scalar span **0.19**
Iberia / **0.16** Sahel where F carries one number; within-(PFT x age) corr(`beta_root`,`wscal`) **0.83**
Sahel; dry/wet spread amplification **112x** Hainich; drought share of hazard **0.147** boreal / 0.069
Iberia / 0.039 Hainich; drought-killed stems root **57 % shallower** than the mean at Hainich. Warming:
drought share **x3.95** Amazon / x1.47 Iberia / x1.32 Hainich. Verdict PASS — honestly, the spread-RATIO
sub-test is marginal (median 1.11) and fails at Hainich and boreal; the other two carry it.

**WHAT IS BUILT** (all opt-in, default byte-identical; F-side files are M's — integration point recorded in
`lines/M/STATE.md`, the ADR-0029 "hand over for one milestone" route):
- ports of `getbetaroot.c` + `getrootdist.c`, validated to **5e-7** against the C's OWN emitted `beta_root`;
  `getvpd` (`spitfire/getvpd.c`); `TreePools` gains `d95max`/`minwscal`; `DailyForcing` gains `humid`
- `daily_step_canopy` takes `rootdists=`, computes per-tree `wr_i`, withdraws down each tree's own profile
  with the order-free cap (i), and returns `wscal_ind`/`wr_ind`
- `_accumulate_stress!` builds the two per-individual annual integrals ADR 0049 §3 could not supply, and
  `_trait_hazards!` feeds them to `mort_water`/`mort_temp` instead of zeros
- flags `per_tree_roots`, `per_tree_fpc_cap`, `trait_drought_mortality` (all default off);
  `test/testitems/per_tree_roots_tests.jl`

**WHAT IS LEFT — in order:**
1. **Confirm the suite is green** (`logs/S-pertree-roots2.1719476.out`). ⚠ The FIRST attempt (job 1719462)
   died with **SIGABRT** — a bare LLVM abort, no Julia error — right after the grass Enzyme reverse item,
   because the per-tree profile was a `Vector{T}` field on `Individual`, a struct Enzyme differentiates
   through. It now travels as a separate `rootdists` argument. **Never put a heap-allocated field on
   `Individual`.** If the suite is red again, suspect the AD path first, not the physics.
2. **Score the per-tree `wscal` against the C's own per-stem `wscal_mean`** — the truth table emits it, so
   this is a direct oracle test, not self-consistency. That is ADR 0110 §6's flip criterion (a).
3. **Then the flip criteria in ADR 0110 §6** — (a)-(c) for `per_tree_roots`, (d)+(e) for
   `trait_drought_mortality`. Criterion (e) is the historic->ssp370 response and needs the coupled screen,
   i.e. the SAME blocker as A below. Do not flip on the level result alone (ADR 0104's error).
4. **`k_root` is not per-individual in the port** (the C draws it per tree; `per_tree_rootdists` uses one
   default), so the size-driven half of the rooting channel is coarser than the C's. Stated, not hidden.
5. **`trait_drought_mortality` needs a REAL humidity in the forcing.** `AtmForcing.qair` carries it on the
   coupled path and `huss` is already column 7 of every committed forcing fixture, but `DailyForcing.humid`
   defaults to 0, which `getvpd` reads as bone-dry air => maximal VPD. Never enable it on unset humidity.

**A★ RUN THE COUPLED SCREEN — it is clause 3 of ADR 0109 §5 and the ONLY remaining blocker on the moisture
tail, and it is the same blocker every response claim on this line has had.** The offline work is DONE
(ADR 0109); do not re-run the arm. What is needed: a coupled run with `_t9envT` wired via
`live_flux_cond_env_series`, on the patch **ENSEMBLE** (not the modal patch — ADR 0105 §2 showed the modal
patch inverted three published conclusions), differenced against a **matched constant-forcing control re-run in
the same generation** and measured **past the transient** (ADR 0048: constant-forcing drift alone moves
community wood density by 1.34× the real shift and settles only at year ~52, inside the 80-yr window). That
harness is line **M**'s (`biome_slow_oracle_probe.jl`), so this is an **integration point**, not S-only work —
and it needs the `env_series` provisioning of item B anyway. ⚠ An offline slope is an **UPPER BOUND** on the
coupled one (ADR 0105 §5: the coupled residual is dominated by F's canopy), so a coupled null does not
contradict ADR 0109.

**A2. The cheaper, S-only follow-up if the coupled screen cannot be scheduled: kill the ADDRESS effect
directly.** ADR 0109 §2's mechanism says per-cell constants act as a spatial address. ADR 0040 already built
the controls for exactly this question (`p14geo` = a pure-position tail, `p14perm` = the true env tuples
permuted across cells, both via `ENV_PARQUET=` on `build_slow_copula_env_augment.py`). Score those two with
`diagnose_moisture_arm_response.py` on the `_t9` base: if the **geo** tail reproduces the frozen tail's
level gain AND its response loss, the address reading is confirmed and the design question becomes whether to
carry the tail at all rather than how to time-base it. Cheap (two augments + two evals, ~1 h each) and it is a
falsifiable test of §2 rather than another lever.

**B. RE-PIN WITH LINE M — needed to run A at all, and it is an ADR-0023 BOTH-SIDES change.** M currently passes a
constant `env`; it must pass a per-cell `env_series`, which is a `cell_year_env_<scenario>_w20.parquet` slice
(a read, not a new derivation). Version the artifact, never mutate in place. Note in BOTH lines' STATE.md and
land both sides together. Until M re-pins, nothing M runs changes.
⚠ **Read `env_basis` before wiring ANY 14-column artifact.** A static-tail and a transient-tail `.rcop` have
identical `ncond` and identical `cond_cols`, so the ADR-0038 width probe and `load_copula` pass for **either**
pairing and a mis-paired coupled run completes, conserves carbon and returns in-range traits.

**C. SCORE GLOBALLY AGAINST ADR 0106 — the machinery now exists and item 3 above is the first instalment.**
`diagnose_moisture_arm_response.py` gives per-cell medians + the response for the four trait axes over 52 074
cells. Still missing for a full verdict: the **count** side at global scale (needs `eval_slow_drf.jl` preds for
this generation — note `run_slow_validation_figures.sh` SKIPS a scenario entirely when `preds_oos.f64` is
absent), the two **struct** axes (`agb`/`Height`, already in the tables), and the **max(10 %, two-run spread)**
tolerance, which needs the seed2 companion per cell (ADR 0030) — the script currently reports the literal 10 %
and says so.

**D. ~~`D95max` needs a soil axis~~ — ANSWERED, and better, by ADR 0110 (a CONCURRENT line-S session, same
day). Do not re-open it as a conditioning question.** ADR 0109 established that `D95max` is the worst axis on
BOTH level (28–33 % of cells within 10 %) and response (best arm +0.172) on **all three** arms; ADR 0110 reads
that as the completion of a search on the *statistical* side and identifies the cause as **the trait having no
physical consumer** — Component S samples `D95max` and `minwscal`, but nothing in F reads them (ADR 0025 shipped
them "sampled + validated only, until F_diff gains per-tree consumers"), so no conditioning change can make a
predicted quantity matter when nothing downstream uses it. ADR 0110 also narrows the standing "per-individual
water supply is structurally impossible" DEFER to the *order-dependent residue cap alone*, having found that
verdict was reached on GRASS. **That is the live thread for this trait, and it needs F — an integration point
with line M, not S-only work.** My earlier guess here (a missing soil axis in the tail) is withdrawn as
speculation that the measurement did not support.

**E. Still open, unchanged, off the critical path:** `CAP_HASH_SEED` (~10 lines at
`build_slow_runtime_table.py`, default `= seed` so every artifact stays byte-identical); D1 (space-for-time
surrogate); D3 (calibration curve). S3 stays de-prioritized (ADR 0033); S4 (grass) is unstaffed and needs F;
S6 (in-loop OOD) needs M's harness.

**F. THE METHOD RULES — the newest one cost an ADR draft, a changelog entry, three comment blocks and a test
header before one 3-minute job killed it.**
1. **MEASURE THE BASELINE BEFORE ARGUING FROM CODE STRUCTURE THAT A CHANNEL IS CLOSED.** "Conditioning column
   X is a frozen constant" bounds what **X** can carry and says **nothing** about what the model does, because
   the other columns are not frozen. A structural argument reads as *stronger* than a measurement ("by
   construction" sounds like proof), every sentence in it is true, and a reviewer re-reading the same code
   agrees — so it survives review and dies to one measurement. Name a **response** statistic (not a level one:
   a model can match in two regimes separately and still have zero response between them), measure it on the
   **shipped** artifact first, and treat that as the reference basis. Written up in the `residual-diagnosis`
   skill. Same shape as ADR 0107's rule, turned on our own reasoning.
2. **Never publish a default, a recommendation or a tuned value from an arm you have labelled an upper bound**
   (ADR 0104 did, and ADR 0105 had to withdraw it). Close the confound, or publish the finding without the
   recommendation and say what would close it.
3. **An attribution arm inherits every basis error of the harness it runs in.** ADR 0054's teacher forcing was
   modal-patch AND scored on the prediction, and reversed under *either* correction. A diagnostic arm is not
   more robust than a skill measurement just because it is diagnostic.
4. **Price a retrain offline before buying it** (ADR 0105 item 6: 200 lines of Julia and one 4-minute job
   against a global two-artifact retrain).
5. **Isolate what you attribute.** Two independent builds of these tables land on two row universes (ADR 0036
   §5b: streaming `group_by` is non-deterministic in its KEY SET), so an arm and its control must be appended
   to ONE frozen base — that is why ADR 0108's arm is built the way it is.
6. **Read the diff, name the variable the change writes, confirm the metric is a function of it**; and **when a
   control arm and a truth disagree, score against the truth.**

**G. TOP-LEVEL, ALL LINES — `CLAUDE.md` §0a (owner instruction, 2026-08-06).** Reports to the owner go in
**plain language**: no decision-record numbers, no milestone or phase codes, no repo jargon standing in for an
explanation. User-facing text only; ADRs, STATE and code comments keep the precise shorthand. Translation table
in §0a.

## Superseded NEXT — ADR 0105 as it left the line (S2 was then unbuilt); audit trail

That block's item A (raise the F-canopy attribution with line M) was **done** — it is in `lines/M/STATE.md`
— and its item B (wire the moisture conditioning, retrain, re-pin, score) is what ADR 0108 built. Its framing
of B, "the only channel through which a warming signal can reach the recruit model", was **measured false**
in the same session that acted on it (the channel was already partially open: slopes +0.85/+0.35/+0.16/+0.69,
job 1718922) — see the method rule in **F1** above. Every number in the old block is preserved immutably in
**ADR 0105**, which is where to read it. The full text is in git at `c68ee134~1:lines/S/STATE.md`.

## Superseded NEXT — ADR 0104 as it left the line (ADR 0105 reversed its recommendation); audit trail

ADR 0104's handoff block ended with **item A: "re-run the corrected criterion on the patch-ensemble driver
— this is the whole remaining blocker"**, a revised recommendation of `anchor = 0.25`, and the exposure-bias
retrain as item C. Item A was run (jobs 1717190 / 1717247 / 1717189) and the criterion **failed**, which
superseded the recommendation; item C was priced offline (job 1717208) and measured **empty**, which
cancelled it. The full block is in git at `b9ca54a4:lines/S/STATE.md`, and every number in it is preserved
immutably in **ADR 0104** itself — which is where to read it, since an ADR is immutable and a STATE block
is not. ADR 0105 records exactly which of its claims survive (§6) and which do not (§2–§5). Line M's reply
and this line's reconciliation with it, both quoted verbatim in that block, are in ADR 0056 and ADR 0104
respectively.

## Superseded NEXT — ADR 0103 as it left the line (ADR 0104 corrected its flip criterion); audit trail

**THE LEVEL ANCHOR IS BUILT, MEASURED AND SHIPPED (ADR 0103). Read ADR 0103 first, then 0102, then 0101.**
⚠ **ADR 0102 §4 was WRONG and 0103 supersedes it.** 0102 said the fix needed the count↔density conversion at
the S↔F seam and deferred it to line M as an integration point. **The conversion is a documented CONSTANT** —
`param.patcharea = 225.0` m² (15×15) in `par/lpjparam_fit.js`, with `new_tree.c:209` giving every individual
`nind = 1/patcharea`; verified by `cpp -P` on the live config (single occurrence, no duplicate override) and
end-to-end against the fixture (`sum(nind)×225 = 17.000` exactly). **The owner caught the error.** Nothing was
missing, no interface change was needed, and the fix is one file: `src/components/slow.jl`.

**It works.** `anchor` blends the AR ratio with the ratio that lands the stand on the DRF's absolute target,
`ρ_eff = (target/n_prev)^(1−a)·(D_want/D)^a`. Measured (job 1707102, Hainich, 150 yr, the ADR-0102 sweep):
retention **1.036 → 0.051**, terminal spread **4.21× → 1.07×**, and the stand goes from **1.409×** its own
count model's absolute prediction to **1.000×** — a 41 % over-density nothing in this project could see,
because every existing gate reads ratios, distributions or correlations, never the absolute level.
`anchor = 0` reproduces the unanchored trajectory to the last bit (pinned in
`test/testitems/slow_level_anchor_tests.jl`). **Recommendation: `anchor = 0.1`** — the gentlest setting that
fully works; `a = 1` is measurably *worse* (retention 0.076), so relax, don't force.

**⚠ THE ANCHOR IS OFF BY DEFAULT, AND THAT IS TEMPORARY — do not let it become permanent (ADR 0103 §6).**
`anchor = 0` is a KNOWN-WRONG default (41 % level error, invisible to every gate). It is off for exactly one
measurement cycle, because the evidence is one cell and flipping a global default on single-cell evidence is
the ADR-0031 defect class. **The flip criterion is pre-registered** in ADR 0103 §6 and the decisive arm is
line M's 5-cell oracle at `anchor = 0.5` (their 10-yr horizon needs the stronger setting — §3b). Raised as an
ACTION in `lines/M/STATE.md`. **If that arm has not been run when the next S session opens, running it is
that session's FIRST action, ahead of the retrains** — `wscal_leafon` sat correct-but-off for weeks on
exactly this failure mode, with each line recording it as the other's to schedule.

**What is left is genuinely two things, and both are now unblocked** (the owner has confirmed HPC compute is
not a reason to defer): the **exposure bias** (retrain the count DRF without feeding its own prediction back
— the anchor makes the stand follow a biased prediction *faithfully* rather than compounding it, which is
better and still not right), and **S2's conditioning** in the only form that can carry a warming signal
(per-cell-per-year moisture descriptors, not present-day means).

✅ **MERGED AND VERIFIED ON BOTH SIDES — nothing about ADR 0102 is outstanding.** Work sha `0a230ece`
merged to `main` as **`07c0029f`**. Branch CI green on every required gate (`format`, `test (1)`,
`test (lts)`, + non-required `test (macOS, lts)`), and **`main`'s OWN post-merge run on `07c0029f` is green
on the same set**. `python` and `docs` correctly never ran (ADR 0090: no `python/**`, and
`docs/report/component_s_public_report.*` + `docs/decisions/**` are outside the Documenter page tree; the merge
added no `src/**`). Local CI-faithful suite job **1705738**: **110 102 pass / 0 fail / 4 broken**. Runic
1.7.0 clean on all 121 tracked `.jl`. `test (pre)` is red and was **diagnosed, not waved away**: it dies at
`ReTestItems.jl:510` in `_runtests_in_current_env`, immediately after `Scheduling 107 tests` and **before
any testitem body runs**, with `MethodError: no method matching setindex!(::Base.ScopedValues.ScopedValue{Bool},
::Bool)` — a Julia-prerelease API removal inside ReTestItems itself, the documented allowed-to-fail churn
(CLAUDE.md §5), with `test (1)` passing on 1.12 as the evidence it is not ours.

⚠ **One protocol refinement worth carrying (it nearly cost the verdict).** A docs-only follow-up commit
(`f56dffce`) was pushed *while branch CI was in flight*, which CLAUDE.md §9(5) warns can cancel the pending
run. It did **not**, and the reason generalises: **a push that triggers NO workflow cannot displace the
pending one** — `docs/decisions/**` is in no gate's path filter, so `f56dffce` has 0 check-runs and
`0a230ece`'s run continued untouched. Both shas were checked rather than assumed. That also made merging
`origin/line/S` (= `f56dffce`) rather than the CI-verified `0a230ece` sound: `git diff --name-only` between
them is exactly one `.md` under `docs/decisions/`, i.e. no gate-watched path.

🔓 **OWNER PRE-AUTHORISATION, 2026-08-05 — M's coupled BASELINE REGENERATION is pre-authorised**, for the
two enablements that need it: `wscal_leafon = true` (ADR 0051) and the Component-S level anchor (ADR 0103,
once S publishes a measured `anchor`). Recorded verbatim in `lines/M/STATE.md` (where M reads it) and in
`MEMORY.md` (so it survives a STATE consolidation). **Do not re-raise it as an open question** — it existed
only because §9 makes a baseline regeneration a two-line integration point, so each line waited for the
other. The record-the-before/after-numbers discipline is unchanged; only the waiting is removed.

📄 **THE PUBLIC REPORT IS CURRENT — a CONCURRENT SESSION audited and rewrote it (commits `f34c5f91` +
`2c3e4c1e`), and it did NOT refresh this block, deliberately, because this line owned the handoff.**
Recording it here at that session's request. It is a per-dimension audit of every table, caption and claim
against the ADRs: **7 corrections + 5 additions**, PDF rebuilt (34 pp, was 28). The corrections worth
knowing because they are traps this line can repeat:
- **`co2` is `CO2_CONST = 369.0` in every training row of every deployed artifact** ⇒ the emulator has **no
  CO2 response at all**, and ADR 0004 obliges every write-up to say so. It was being presented as live
  boundary context.
- The "29 recorded fields are the complete input universe" claim was false — only 10 of the count model's 15
  predictors are aggregates of them.
- `soil_depth` is **static spatial context, not a rooting-volume limit** (the C discards its soil-depth
  input; `newgrid.c:282` sets 20 m unconditionally).
- The blocked-hold-out "73 % retained" was the env6 1-NN surrogate over the **REFUSED** moisture tail, and
  ADR 0042 §8(3) forbids quoting that retention percentage as a finding at all.
- ⚠ **It also corrected an error THIS session introduced into the report earlier the same day:** I wrote that
  the `ind` table's `mort_*` fields "are the basis of the optional operator". They are not — the operator
  **re-derives** the hazard from the C source and its parameter files and sets `mort_water`/`mort_temp` to
  zero (ADR 0047/0049), so those columns remain **unconsumed**. Ported-from-the-source ≠ built-from-the-table.
- New `§sec:coupled` and `§sec:anchor` carry ADR 0054's coupled measurement and this line's retention table.

⚠ **Two sessions were live on `line/S` in ONE worktree** (CLAUDE.md §9 forbids this). No damage: that session
staged by explicit path, touched neither of the level-anchor files, and left the push to avoid a branch race.
But we shared one git index, one `test/Manifest.toml` and one `logs/`. If it happens again, the second
session belongs in its own worktree.

### THE STATE IN SEVEN LINES

1. **THE DOMINANT DEFECT IS A MISSING LEVEL ANCHOR IN THE COUPLED RECURSION, newly measured (ADR 0102).**
   ρ is a unit-free ratio and the roster is advanced multiplicatively, `D_T = D_0·Πρ_t`, so the count DRF's
   **absolute** skill (OOS R² 0.982) never reaches the stand — only its year-on-year ratios do. A **4.00×**
   perturbation of initial stand density is still **4.21×** after **300** identical-forcing years:
   retention **1.036**, converging to a NON-ZERO asymptote (peak **1.40** at yr 25, then flat yr 150→300).
   There is no restoring force — not a weak one, none.
2. **Line M's ADR-0054 is ANSWERED and decomposed into three defects with three owners.** (A) **exposure
   bias** — training `n_prev` is the C's own previous `n_living`, runtime feeds the DRF its own output;
   real, **training-side**, needs a global retrain. (B) **state incoherence** (the clamp/`n_prev`
   mismatch) — S's leading hypothesis, **MEASURED EMPTY**: the clamp binds **0 of 150 years**, roster
   tracks ρ to 1.5e-13. **Closed — do not spend time here.** (C) the level anchor, item 1.
   **(C) is why M's teacher forcing recovers 59–72 % and not 100 %:** it repairs the RATIO each year and
   nothing repairs the LEVEL. This **completes M's same-day refinement `9ad8721b`** rather than correcting
   it — M had already split the total into a recursion factor ×1.26–1.53 and a **year-1 level offset
   ×1.05–1.12**; what S adds is that the level term never decays. Visible in M's own numbers: their forced
   boreal arm flattens to **1.12–1.17** — flat, but still displaced by the 1.12 it started with.
3. **The dissociation is the finding, and it falsifies a docstring.** The `n_init` sweep converges the **AR
   state** (terminal spread 6.7 %, retention **0.092**, 4 of 5 seeds identical at 6.7529) while the
   **physical stand** those same runs carry retains **60.2 %** of its spread. So `slow.jl:844-846`'s
   "`n_init` … is self-corrected by the `max_*` clamp thereafter" is **true of the AR state and false of
   the stand**. It also re-reads ADR 0101 §5's 4.5×-FIT `n_init` swing as a *recursion property*, not an
   artifact quirk — which promotes S→M integration point #2 from provenance to correctness.
4. **S2 (recruit conditioning) IS DEMOTED FROM TOP PRIORITY** — the first time this line has re-ordered its
   own queue on a measurement rather than a plan. An unanchored level compounds without bound and no
   conditioning skill corrects it, because the channel that would carry the correction is discarded
   upstream of the conditioning. S2 remains real and remains specified (ADR 0038/0040/0042: the env tail
   is a genuine RESPONSE, not a spatial address, but it buys +0.031 of level skill while COSTING 0.031 of
   transient pattern correlation — the two gates dissociate, which is why it was never promoted).
5. **Two cross-line blockers are cleared from S's side, both landed here.** (i) M's **`wscal_leafon`
   default flip** is **pre-authorised and unblocked in code** — `slow_production_drf_tests.jl` now admits
   exactly the two admissible out-of-band states (`{water_stress}` off / EMPTY on) and still fails on any
   third, so M lands it alone; on M's own ADR-0051 measurement (0.3050 → **0.0034** vs a trained band of
   [0, 0.04315]) it **closes S's last out-of-band conditioning column**. (ii) **S→M integration point #2**
   (the pooled artifact's missing `cell_meta.parquet`, the undocumented `n_init`/`age0` substitution, the
   boundary-basis mismatch) is now **raised in `lines/M/STATE.md`**, where it had only ever been recorded
   on S's side.
6. **The public report is corrected and re-ordered** (`docs/report/component_s_public_report.tex`). The damping is
   **39.9 % / −971.5 / +1461**, not 37 % / −892 / +1541 (that pair was arm B, the *refused* env arm); the
   ceiling is on the **patch-year** basis (Wooddens **0.9543**, axes 0.94–0.97), not the superseded
   stem-parity 0.9201/0.87–0.96; **the defect is placement, not shrinkage** (dispersion **1.034** while the
   pattern captures 39 % of ceiling) is stated for the first time; recursive stability moves from *"not yet
   tested — no evidence either way"* to **"not established (measured, negative)"**; the roadmap is
   **re-ordered** with the level anchor as item 1; and a new `sec:traitmort` reports Phase 3A honestly
   (level `+7 041 ± 334`, t = 21, response `+0.26 [−0.38, +0.90]` ×FIT = not distinguishable from zero).
7. **Nothing in the shipped emulator moved.** No committed baseline, artifact, fixture or default changed;
   the only code change is the widened assertion in item 5(i), which passes identically under today's
   default. Runtime `[deps]` still empty. Suite green (job 1705738); Runic clean.

### DO THIS NEXT, IN THIS ORDER

**A. THE LEVEL ANCHOR — the highest-value remaining item, and it is a TWO-SIDED change (ADR 0102 §4).**
It is not startable from this line alone. It needs the count↔density conversion (per-cell patch area) at
the S↔F seam: an addition to `src/interface.jl` (**line M's exclusive path**) or a new column in
`cell_meta.parquet`, plus a `reconcile_demography!` change (**S's**) that blends the multiplicative update
toward the absolute target with a **stated relaxation time** — a *hard* anchor is wrong, it would discard
F's own stand dynamics and convert a level drift into a level bias. **It moves every committed coupled
baseline** ⇒ deliberate regeneration under guardrail 4, its own commit, its own matched control. Score it
on the **teacher-forced arm as well as the free arm** or the ratio and level effects re-confound. Raised in
`lines/M/STATE.md`; agree the seam with M before writing code.

**B. Do NOT re-open (B), and do not "just anchor to `n_prev`".** Both are recorded as rejected in ADR 0102
with the measurement behind them. `n_prev` is per-patch COUNT space and `D` is DENSITY space; their ratio
is exactly the unknown patch area, so using one as the other silently sets that constant to 1 and turns a
drift into a bias that *looks* anchored. That is the trap this ADR exists to prevent.

**C. S2 is now the SECOND lever, and its honest remaining target is small.** Do not restate ADR 0033's
warning by crediting a basis or population fix to conditioning. Read ADR 0030 §4's criteria, then ADR 0042
§4 (the `Rr`/`Ra` dissociation) — the specified resolution is a **scenario- and time-resolved** version of
the six moisture descriptors, recomputed per cell-year rather than frozen at present-day means, which is
the only form that can carry a warming signal. Unbuilt.

**D. Exposure bias (A) needs a global retrain** — scheduled sampling, or dropping `n_prev` from the count
feature set. Both are an ADR-0023 both-sides change with M. Worth measuring the one-step bias offline from
the existing `t8` tables *before* buying any retrain.

**E. Still open, unchanged, off the critical path:** `CAP_HASH_SEED` (~10 lines at
`build_slow_runtime_table.py:378-384`, default `= seed` so every artifact stays byte-identical); D1
(space-for-time surrogate); D3 (calibration curve — note it is the natural instrument for D above).
S3 stays de-prioritized (ADR 0033), S4 (grass) is unstaffed and needs F, S6 (in-loop OOD) needs M's harness.

**F. METHOD RULES EARNED HERE — they each cost or saved a wrong turn.** (1) **A code-level inconsistency is
a HYPOTHESIS about the trajectory, not a defect, until the branch is shown to execute.** Defect (B) was
real in the source, attractive, S-owned and cheap — and fires 0 times in 150 years. One 4-minute job before
implementing saved shipping a fix for something that does not happen. This is CLAUDE.md §3's
`individual=true` dead-path rule turned on our own code. (2) **Read the part of another line's result that
does NOT fit.** M's teacher forcing recovering 59–72 % rather than ~100 % was in ADR 0054 all along and
was the whole clue; the level component is exactly the residual — and M reached the same split
independently the same afternoon (`9ad8721b`), so read a sibling line's LATEST commits, not only the ADR
you were handed. (3) **Separate the state variable from
its diagnostic.** Sections (b) and (c) disagree — the AR state converges, the stand does not — and a probe
that had measured only the AR state would have confirmed the docstring and closed the investigation.
(4) Before believing a null, check the operator FIRED (`TraitMortDiag` prints first) — unchanged.

## Superseded NEXT — ADR 0101 as it left the line (ADR 0102 re-ordered the queue); audit trail

**ADR 0101 is written and Phase 3A Stage 3's response claim is WITHDRAWN. Read ADR 0101 first — it corrects
ADR 0100 §1/§2/§5 — then ADR 0049 (whose LEVEL claim it CONFIRMS), then ADR 0046 §3.** ADR 0100's protocol
(the 2×2 on real forcing, window mean, raised `k_cap`, byte-identical `MODE=stage2`) is intact and reused.

### THE STATE IN SEVEN LINES

1. **ADR 0100's `+1.40× FIT` MUST NOT BE QUOTED.** `SEED` was hard-coded to 1; exposed and replicated, the
   2×2 double difference has a **seed sd of 0.67–1.74× FIT — the size of the effect.** On both GLOBAL
   artifacts the operator's contribution to the warming response is **indistinguishable from zero**:
   `+0.048 [−0.380, +0.476]` (global historic-only, n=12) and `+0.263 [−0.377, +0.903]`
   (`pooled_w20_t8` = **the pair line M pins**, n=12). Both CIs **exclude +1.40×**.
2. **ADR 0049's LEVEL claim is CONFIRMED and STRENGTHENED** — `+6 718 ± 286` / `+7 041 ± 334` /
   `+8 959 ± 862` gC/m³, `t` = 10.4–23.5. Replication made exactly one of the two claims stronger, and it is
   the older one. **This is the quotable Phase-3A result**, with ADR 0049 §4's age structure.
3. **ADR 0100's headline FINDING was a single-cell FIXTURE artefact, and the sign REVERSES on a global
   artifact.** `R_ctl` = `−1.234 [−2.058, −0.411]` on the committed demo pair (significant — so ADR 0100 §2
   was real *for its artifact*) but **`+0.417 [+0.050, +0.784]`, FIT's own sign, on the global historic-only
   pair**, and `−0.000 ± 0.367` on the pooled one. The deployment defect is milder and different: **no**
   warming response where FIT has +1×.
4. **The attribution was wrong — CELL SCOPE, not scenario coverage.** demo → global-historic (scenario fixed)
   `ΔR_ctl = +1.651 ± 0.386`, `t = +4.28`; global-historic → pooled (scope fixed) `−0.417 ± 0.403`, `t = −1.03`.
   Cross-**cell** pooling widens the `soilmoist` trained band **4.79×**; adding the whole ssp370 scenario
   widens it **−0.04 %**. **An excursion diagnostic localises a channel; it does NOT identify which axis of
   the training design to change** — test candidate levers separately, holding the others fixed.
5. **NEW PRECONDITION, alongside ADR 0048's merge dormancy: hard kills = 0 AND count-override (shortfall)
   years = 0.** `n_init` 11.0 → 7.0 fires 6 hard kills + one override year and swings the contribution to
   **−3.71×**. And `age0` 43.556 → 46.0 fires **nothing** yet still moves it +0.756× → +0.017× — a 2.4-year
   seed change, all diagnostics clean, 44× answer change. `summarize_response_seed_ensemble.py` EXCLUDES
   violating runs rather than averaging them.
6. **S→M INTEGRATION POINT #2 (raised here, NOT landed, not yet raised WITH M):** the `pooled_w20` artifact
   **ships no `cell_meta.parquet`** (its meta names one that does not exist), and its two training sub-tables
   disagree on Hainich's seed (`n_init`/`age0` 11.0/43.556 vs 7.0/46.0) — a **4.5× FIT** swing.
   `M_slow_init_meta.json` silently reads the well-behaved branch (**nothing is broken in M's pin today**) and
   takes its **boundary row** from `slow_runtime_historic_t8`, a table the pinned artifact was never trained
   on (gdd5 1 863.7 vs the training basis's 1 698.0 = 23 % of the warming signal) — while that artifact's
   boundary channel is worth **3 165 gC/m³ = 1.30× FIT** on ensemble average.
7. **ADR 0100 §4's boundary inertness is EXACT and is a fixture property** — 0.0 in all 8 demo seeds; the
   globals run 1 105 / 3 165 gC/m³ mean.

### DO THIS NEXT, IN THIS ORDER

**A. ✅ NOTHING IS OUTSTANDING ON ADR 0101 — it is MERGED and verified on both sides. Start at B.**
Work sha `09ae6156`, merged to `main` as **`3e11284d`**. Branch CI green on every required gate (`format`,
`test (lts)`, `test (1)`, + non-required `test (macOS, lts)`), and **`main`'s OWN post-merge run on
`3e11284d` is green on the same set**. `python` and `docs` correctly never ran (`scripts/*.py` is unlinted;
`docs/decisions/**` is outside the Documenter tree; the merge added no `src/**` — ADR 0090). `test (pre)` is
red and was **diagnosed, not waved away**: it dies at LOAD time with `MethodError: no method matching
setindex!(::Base.ScopedValues.ScopedValue{Bool}, ::Bool)` — a Julia-prerelease API removal breaking the
`ScopedValues` dep, before any testitem runs — the documented allowed-to-fail churn (CLAUDE.md §5), with
`test (1)` passing on 1.12 as the evidence it is not ours. Local CI-faithful suite on the **rebased** tree:
job **1701366**, `110 102 pass / 0 fail / 4 broken`. Runic clean on all tracked `.jl`.
⚠ Worth repeating because it nearly cost a verdict: `main` moved (line/M merged `src/components/slow.jl`)
*between* the pre-push suite and the push, so the pre-rebase suite no longer covered the tree — re-run it
after a rebase that pulls in another line's `src/**`, and let branch CI on the pushed sha be the authority.

**B. MILESTONE S2 — THE CONDITIONING SET — is now the only lever the finding points at.** Every trained-band
excursion is **0.0** on both global artifacts and the training scenario is excluded, so the deployment
artifact's recruit channel producing *no* warming response is a conditioning-set question, not a coverage or
extrapolation one. Read ADR 0030's S2 targets. ⚠ Do **not** re-open "retrain on the pooled table" — ADR 0101
§4 measured that as inert (`t = −1.03`).

**C. ANY response claim goes to the ADR-0044 GLOBAL GATE, not this harness — and the cost is now known.**
~8 seeds resolve a 1×-FIT effect at one cell; **~115** resolve the +0.26× actually measured. FIT's own
+2432.9 is a 25-patch ensemble mean over 67 420 cells. The single-cell 81-yr harness is a **mechanism** check
and nothing more. Entry points if you do run one: `scripts/run_response_seed_ensemble.sh <TAGPREFIX> [N]`
then `scripts/summarize_response_seed_ensemble.py 'logs/<TAGPREFIX>*.out'`. Always name the artifact pair,
the `n_init`/`age0` and the boundary row with the number (ADR 0101 §3).

**D. Report numbers to fix in `docs/report/component_s_public_report.tex`** — now three items, one new:
(i) "37 % damping / `Rb` = −892" is arm **B `p14env-hash`, the REFUSED env arm** (the deployed ncond-8 arm is
**−971.5 = 39.9 %**); (ii) the `Rr` ceiling 0.9201 is superseded by the patch-year basis (**0.9543**);
(iii) **anything inherited from ADR 0100's response headline** must be replaced by ADR 0101's ensemble
statement (level effect quotable, response withdrawn).

**E. `fc.pft_ids` is STILL M integration point #1, still unraised with M.** The operator errors on a non-tree
id but a wrong-but-*valid* id passes silently, and `FDiffFastCore` defaults every tree to beech
(`fast.jl:147`), which would run the tropical and boreal PFTs on temperate wood-density mortality (the
ADR-0031 defect class). **Any M driver that enables `trait_mortality` must pass `pft_ids`.**

**F. Still open, unchanged, off the critical path:** `CAP_HASH_SEED` (~10 lines at
`build_slow_runtime_table.py:378-384`, default `= seed` so every artifact stays byte-identical); D1
(space-for-time surrogate — note ADR 0101 §4 makes this sharper: the global artifacts learn the boundary
response *cross-sectionally*); D3 (calibration curve). ADR 0049's "co-occurring gross turnover" stays
DEMOTED — ADR 0100 demoted it and ADR 0101 removes the reason to promote it, since the mechanism it would
enlarge has no measurable response contribution to enlarge.

**G. METHOD RULES EARNED HERE — apply them, they each cost a wrong turn.** (1) **One run is not a
measurement** when the estimator is a difference of small-sample stochastic rollouts; replicate before
writing a number down, and note that a common seed across corners does **not** pair them (the rosters diverge
after yr 1, so `sd(Δ_ssp)` ≡ `sd(interaction)`). (2) **A diagnostic message that hard-codes one
configuration's answer will confidently mislabel the configuration you introduce to test it** — two such
messages in the probe called the correctly-trained global artifact "an out-of-band extrapolation". (3) **A
correct measurement can carry a wrong causal reading**: ADR 0100 §5's excursion numbers were right and its
attribution was not. (4) **Re-verify confounds per CONFIGURATION, not per protocol** (ADR 0100's own lesson,
which is how the hard-kill precondition was found). (5) Before believing a null, check the operator FIRED
(`TraitMortDiag` prints first).

## Superseded NEXT — Stage 3 as ADR 0100 left it (ADR 0101 withdrew its response claim); audit trail


**ADR 0100 IS MERGED to `main` (`d4b849b6`).** Branch CI on the work sha `1b44cebb` was green on every
required gate — `format` ✅, `test (1)` ✅, `test (lts)` ✅ (+ `test (macOS, lts)` ✅). `python` and `docs`
correctly never ran (ADR 0090's path filter). **`test (pre)` failed and was diagnosed, not waved away:** it
dies at LOAD time with `MethodError: no method matching setindex!(::Base.ScopedValues.ScopedValue{Bool},
::Bool)` — a Julia-prerelease API removal breaking a dependency, before any testitem runs — which is the
documented allowed-to-fail churn (CLAUDE.md §5), and `test (1)` passing on 1.12 is the evidence it is not ours.

✅ **`main`'s OWN post-merge run on `d4b849b6` is GREEN on every required gate** — `format`, `test (1)`,
`test (lts)` (+ non-required `test (macOS, lts)`); `test (pre)` red with the same unrelated prerelease load
error. So the merge is fully verified on both sides and **nothing about ADR 0100 is outstanding**. (`main`
was still at `a18d1599` when the merge landed and the branch was rebased onto it, so `main`'s tree was
byte-identical to the branch tree — `git diff d4b849b6 origin/line/S` empty outside this file — which is why
the whole-package gates could not have diverged short of a dep bump between the two runs.)

**Phase 3A is COMPLETE as a mechanism (Stages 1/1b/2/3 all landed). Read ADR 0100 first, then 0049 §5,
then 0046 §3.** Stage 3 made the response measurement and it **reframed the line**: the operator is right, and the
binding constraint has moved to the **recruit channel**. The ADR-range blocker is gone.

### THE STATE IN SIX LINES

1. **ADR 0100 — the operator's contribution TO THE WARMING RESPONSE is +3 400.6 gC/m³ = +1.40× the FIT
   shift, right sign.** Measured as a 2×2 double difference, {`trait_mortality` on/off} × {historic, ssp370},
   all four rollouts in one process at matched year indices, on **real** forcing from the same orderA `.clm`
   files the two ground-truth runs read (+2.45 K / +709 gdd5 at Hainich). Phase 3A's mechanism claim is now
   complete: right level (ADR 0049, 3.25×), right age structure (ADR 0049 §4), right response sign (this).
2. **THE FINDING — the emulator's BASELINE warming response has the WRONG SIGN and is LARGER.** `R_ctl` =
   −5 945.8 = **−2.44× FIT** where FIT *rises* +2432.9. The hazard shrinks that wrong-signed response by **57.2 % in
   magnitude** and closes **40.6 % of the gap to FIT** — but cannot flip the sign. Attribution is near-forced: ρ-thinning is composition-preserving and the merge is dormant, so `R_ctl`
   **is** the recruit channel's warming response.
3. **It is localised, and the fix is testable without new training.** The trained-band diagnostic (probe
   section (e)) shows **`soilmoist` running 0.658 band widths BELOW anything the historic-only copula saw — a
   16× larger excursion than the historic arm** — and an out-of-band forest **saturates** rather than
   extrapolating, so the recruit conditional is clamped to the driest historic leaf. It **excludes**
   `water_stress` (excursion worse under *historic*, ratio 0.49×), so line M's known defect is not the driver.
4. **`k_cap` IS A CONFOUND ON ANY TRANSIENT RUN — this is the trap to remember.** The k-cap merge, which
   ADR 0048 measured as dormant over 150 constant-forcing years, **wakes under real forcing** (8–9 merges/arm
   at the default `max(2K,40)`) and **destroys 54 % of the response contribution** (+0.638× vs +1.398×).
   "The merge is dormant" is a property of a forcing configuration, never of the cap. Always report the merge
   count per corner and raise `K_CAP` until it is 0.
5. **ADR 0049 §5's 13.6 % duty cycle is a CONSTANT-FORCING ARTEFACT — quote it with its basis.** Under real
   forcing the operator selects in **54.2 %** of thinning years (historic) and **62.5 %** (ssp370), and
   warming *loosens* the throttle (|ρ−1| 1.868 → 2.176 %/yr). The gross-vs-net mechanism still stands; its
   measured cost was ~4× overstated.
6. **The transient boundary is EXACTLY inert for this cell's committed artifacts** (max |Δwd| = 0.0), because
   both boundary axes are constant in training — the same fact the band table shows as `Inf`. Good for
   ADR 0100 (nothing in it is a boundary extrapolation) but it means the demo artifact **cannot** express a
   boundary-mediated response; the global `pooled_w20` artifacts can.

### DO THIS NEXT, IN THIS ORDER

**A. THE CHEAPEST DECISIVE ARM — re-run the ADR-0100 2×2 against the global `pooled_w20` `.rcop` + `.drf`.**
No new training: those artifacts already exist on `/p/tmp` (`slow_copula_pooled_w20_*`, `*_pooled_w20.drf`),
are fit on historic **and** ssp370 so `soilmoist` down to 0.65 is in band, and train on a **live** transient
boundary so §6's null lifts too. **The pre-registered prediction is that `|R_ctl|` shrinks substantially or
flips sign.** If it does, the cause was the training scenario and the fix is an artifact version bump (S→M
integration point, ADR 0023 lockstep). If it does not, the cause is the **conditioning set** and it is
milestone S2, which Phase 3A cannot deliver. Either outcome is a publishable answer; write it as ADR 0101.
⚠ The pooled artifacts have a wider boundary/feature width than the demo — check `nfeat`/`colnames`/`cond_cols`
against `flux_feature_vector`/`live_flux_cond` before wiring, and pass `K_CAP` (item 4) and real `pft_ids`.

**B. Co-occurring gross turnover is DEMOTED, not cancelled.** ADR 0049 named it as the next lever; ADR 0100
demotes it because it would enlarge a mechanism that already has the right sign while a larger opposite-signed
error sits upstream, and because item 5 shows the duty cycle it targets is already 54–62 % under real forcing,
not 13.6 %. Revisit after A.

**C. Still open, unchanged:** `CAP_HASH_SEED` (~10 lines at `build_slow_runtime_table.py:378-384`, default
`= seed` so every artifact stays byte-identical). D1 (space-for-time surrogate) and D3 (calibration curve)
remain unrun and off the critical path. Two report numbers are still wrong in the `.tex`: "37 % damping /
`Rb` = −892" is arm **B `p14env-hash`, the REFUSED env arm** (the deployed ncond-8 arm is **−971.5 = 39.9 %**),
and the `Rr` ceiling 0.9201 is superseded by the patch-year basis (**0.9543**).

**D. `fc.pft_ids` is a CORRECTNESS requirement — M integration point #1, unchanged and still unraised with M.**
The operator errors on a non-tree id but a wrong-but-*valid* id passes silently, and `FDiffFastCore` defaults
every tree to beech (`fast.jl:147`), which would run the tropical and boreal PFTs on temperate wood-density
mortality (the ADR-0031 defect class). **Any M driver that enables `trait_mortality` must pass `pft_ids`.**

**E. Integrator notification (do not re-do):** the ADR tier-2 blocks are allocated for ALL FOUR lines in
`docs/decisions/README.md` + `CLAUDE.md` §9 (S 0100–0119 · M 0120–0139 · E 0140–0149 · O 0150–0159 ·
integrator 0160–0169). S's is opened; the other three are unopened and theirs to use.

**F. Do not bundle, and re-run the control in the same generation.** Every arm lands separately with its own
matched baseline re-run in the same process — the move that has now caught seven wrong turns on this line.
Corollary from ADR 0100: also **re-verify the confounds per configuration**, not per protocol — the merge was
"proven dormant" and was not.

**G. Method notes worth keeping.** (1) Before believing a null, check the operator FIRED (`TraitMortDiag`
prints first). (2) An excursion ranking **must special-case a zero-width trained band**, or it ranks the one
channel that provably cannot act (a constant training column) above the one that does. (3) Score a transient
arm on a **window mean**; a terminal-year read of ADR 0100 would have said 2.21× where the honest number is
1.40×.

> **📥 INTEGRATION POINT RAISED BY LINE M, 2026-08-05 (ADR 0054) — the count recursion is unanchored.**
> Also: your item **D** (`fc.pft_ids`) is **acknowledged** by M and recorded in `lines/M/STATE.md`; no M
> driver enables `trait_mortality` today, and the requirement is now written into M's contract list so the
> first one that does will pass real ids. Nothing needed from you on D.
>
> **The finding.** M3's S side scored the coupled loop's per-cell demography against the C's `ind` truth in
> seed1-vs-seed2 noise floors, five biome cells, historic 2010–2019, pinned `_t8`. Free-running, two cells
> are AT the floor (Amazon 0.5×, Sahel 1.4×) and three **drift monotonely** — boreal 1.12→1.74, mediterranean
> 0.98→1.81, Hainich 1.05→1.36 — at 4.5–13.9 floors.
>
> **The attribution, and why it is yours.** In the training table `n_prev` is the C's **own** previous
> `n_living` (`build_slow_runtime_table.py:572`), never a prediction. A coupled rollout feeds the DRF's own
> output back, so it is off that basis by construction and **integrates** the one-step bias. Overwriting
> `s.n_prev` with the C truth after each year **removes 59–72 % of the total count error in every one of the
> five cells** and flattens the drift (boreal becomes a flat 1.12–1.17); what remains is **0.2–3.9 floors**.
> So the per-year count model, given F's own drifting canopy features, is near the floor, and the deployed
> error is a one-step bias compounded by an **unanchored AR recursion** — worth ×1.26–1.53 over the nine
> steps (2.6–4.9 %/yr) in the three drifting cells; the rest of the +36–81 % total excess is the year-1
> level offset, so the total is not all recursion. Only the recursion term grows without bound. Any fix lives in
> `src/components/slow.jl` = your exclusive path (ADR 0029), which is why M measured it and stopped.
>
> **Ready-made before/after test, no setup:** `scripts/biome_slow_oracle_probe.jl::run_cell(k; teacher = true)`
> — a driver-level write to the public mutable `s.n_prev`, so it needs nothing from your side to run. The
> C-truth reference it scores against is committed (`test/testitems/references/M_slow_oracle_counts.csv`).
>
> **Why it may matter to Phase 3A specifically.** ADR 0100 found the emulator's baseline warming response has
> the wrong sign and is 2.44× FIT's, measured on **free-running** 81-year rollouts. An unanchored recursion
> integrating a one-step bias over 81 years is a candidate contributor to exactly that, and it is separable
> from the recruit-channel hypothesis at zero training cost: re-run the ADR-0100 2×2 with the teacher-forced
> arm alongside the free one. If `R_ctl` moves, some of the wrong-signed response is recursion, not recruits.
> M is not claiming it is — only that the arm is cheap, and ADR 0100's attribution was "near-forced" by
> elimination, which this adds a term to.
>
> **⚠ UPDATE FROM LINE M, 2026-08-05 (ADR 0055) — a CAVEAT on the fix, from the M4 resilience battery. The
> ask above is unchanged; this changes how the fix must be SCORED.** M4 measured the coupled loop's lag-1
> autocorrelation against the C's, five cells × {count, AGB}, C's between-patch SD as the yardstick. Two
> results bear directly on the anchor:
>
> 1. **The unanchored recursion is a LEVEL failure, not a memory failure.** Replacing `n_prev` with a
>    CONSTANT each year (so the DRF's explicit count-space AR feature carries nothing) moves the lag-1 AC by
>    **≤ 0.135**; `slow = nothing` alone already carries AC 0.454–0.691. The memory lives in **F's carbon
>    pools**. So expect an anchor to fix the drift and to leave the dynamics essentially where they are —
>    and do not credit it with a dynamics improvement it did not cause.
> 2. **⚠ The teacher-forced arm itself makes the AC WORSE in two cells** — `tropical_amazon` count
>    **0.066** vs a C of 0.501 (**2.3 between-patch SDs**, the worst single number in the battery) and
>    `mediterranean_iberia` **1.2 SDs**, against 0.1–0.6 SDs for the free-running arm everywhere. Forcing
>    the state onto an externally measured series removes the emulator's own memory without substituting
>    equivalent memory. **The teacher-forced arm is a DIAGNOSTIC of the level error; it is not itself the
>    design to ship.** Whatever anchoring you land should be scored on the **AC as well as the level**.
>
> **Ready-made, again nothing needed from your side:** `scripts/biome_resilience_probe.jl` already runs
> `free0` / `pin0` / `anchor0` arms and writes `test/testitems/references/M_resilience_battery.csv` with a
> `d_over_psd` column (the miss in C between-patch SDs). Reference: `M_resilience_reference_cells.csv`.
>
> **What M is NOT claiming:** not that the anchor is wrong (it removes 59–72 % of the count error, which
> still stands), and not that the AC regression is intrinsic to anchoring rather than to *this* anchor's
> particular form. Only that a fix scored on the level alone would have missed it.

## Superseded NEXT — Phase 3A Stage 2 (ADR 0049), kept for the audit trail

**Phase 3A Stage 2 is DONE and MERGED. Read ADR 0049 first, then 0048 (the measurement protocol), then
0046 §3 (the target).** The hazard is wired in, opt-in, and it selects correctly — and the measurement found
that the bottleneck is no longer the hazard but the DRF's **count channel**. That reframes what comes next.

### ⚠ FIRST, A BLOCKER THAT IS NOT SCIENTIFIC: THE S ADR BLOCK IS EXHAUSTED

ADR 0049 was the **last number in the S block 0030–0049**. Do not borrow 0090–0099 (integrator/cross-cutting)
and do not reuse a number. **Raise a new range as an integration point** (note it in `lines/S/STATE.md` +
ask the integrator to record it in CLAUDE.md §9's table) *before* writing the next S decision. Everything
below needs an ADR, so this is the first action of the next session.

### THE STATE IN SEVEN LINES

1. **ADR 0049 — the ported hazard is WIRED IN, opt-in, and it works.**
   `FluxDrivenSlowEmulator(fc, forest; …, trait_mortality = true)` replaces the uniform ρ-thinning with
   ADR 0047's per-individual hazard. `trait_mortality = false` (the default) does not evaluate the hazard at
   all ⇒ every committed baseline, ReferenceTest and AD path byte-identical; runtime `[deps]` still empty.
   Suite **107 749 pass / 0 fail / 4 broken** (job 1698873); docs green (1698958); Runic clean.
2. **The count target is imposed as a PROPORTIONAL-HAZARDS TILT, and this is the design decision to know.**
   `f_i = (1 − mort_i)^θ = exp(−θ·H_i)`, θ bisected so `Σ nind·f_i = ρ·Σ nind` exactly. Bounded in [0,1],
   order-preserving, deterministic, and **it recovers FIT exactly at θ = 1** (asserted in the testitem).
   A linear `λ·(1 − mort_i)` renormalization was REJECTED — it needs a clamp against mortality that
   *creates* individuals, and it distorts pairwise survival ratios, so it is not a hazard. Don't reopen it.
3. **`mort_water` and `mort_temp` are ZERO by decision, not by omission.** The emulator has neither stress
   integral on FIT's basis; `grow.water_stress` = `1 − wscal_mean` is a different quantity on a different
   scale (ADR 0051's precedent). Cost is bounded: `mort_temp` is not trait-dependent, `mort_water`'s only
   per-cohort variation is a per-PFT factor (composition, not the within-PFT channel), and both levels are
   absorbed by θ. Recovering them needs a per-PFT daily accumulator in F — **line M's file**.
4. **THE FINDING: the DRF's count channel, not the hazard, bounds the selection.** θ is bimodal at ~0 —
   median **8.5e-12**, θ > 0.5 in only **18 of 132** thinning years (13.6 %) — because a forest prediction
   is piecewise constant, so the demanded `|ρ−1|` has **median 0.0 %/yr** against the hazard's own
   1.688 %/yr. FIT's deaths and recruits **CO-OCCUR** (near-stationary count, large gross turnover); the
   emulator's `ρ<1` XOR `ρ>1` branches make gross turnover *equal* net change, so a zero-net year is a
   zero-selection year. Selection scales with GROSS deaths. This also re-derives ADR 0048 §4's τ = 94/1003 yr.
5. **What the arm measured, and what it is NOT.** Hainich only, 150 yr, matched constant-forcing control
   re-run in-process, 0 k-cap merges: controlled Δ community `wooddens` **+7 899 = 3.25× the FIT shift, same
   sign**; carbon 3.0e-11; count honoured every year (Σnind matches the control to 1.4e-13); 0 hard kills;
   **age–wooddens gradient rises with age** (+6 565 in the 80–160 yr bin, **+9 642** in 160–320). ⚠ This is
   a constant-forcing **LEVEL** change on ONE cell. FIT's +2432.9 is a **between-scenario** difference, so
   this is NOT a response, and none of it may be quoted against the ADR-0044 gate.
6. **The acceptance target is now an ARTIFACT, and it refined the ADR twice.**
   `test/testitems/references/S_age_wooddens_gradient.csv` (+ its builder, which **asserts** ADR 0046 §3's
   five published rows reproduce to 1 gC/m³). New: **id 2 is non-monotone too** (dips at bin 3 despite a
   positive `S`, so "the sign of `S` predicts the shape" has a measured exception), and **id 5 has no stems
   above 160 yr at all** (longevity 125) while id 2 has none above 320 — never assume 7 bins per PFT.
7. **The frozen gate is unchanged (ADR 0044).** `Rr` = 0.3751 against a 0.9543 ceiling, `Ra` = 1.034 ⇒ the
   residual is a **PLACEMENT** error, not shrinkage. **P1 threshold = `ΔRr` ≥ +0.036.** `Rb` is veto-only;
   *"X reduced the damping from A % to B %"* stays forbidden, and ADR 0030 criterion 2 stays off the table.

### DO THIS NEXT, IN THIS ORDER

**A. Allocate the new ADR range (above). Then pick ONE of B or C — not both (item F).**

**B. The RESPONSE arm — the measurement Stage 2 deliberately did not make.** Everything in §5 is a level
change under constant forcing. The question Phase 3A exists to answer is whether Δ *differs* between
historic and warmed forcing. Needs the ADR-0026/0027 transient boundary (`boundary_series`) on **both** arms
and a 2×2: {`trait_mortality` on/off} × {constant, transient forcing}, all four re-run in one process at
matched year indices. `scripts/trait_mortality_arm_probe.jl`'s `rollout(...)` already takes the flag — add a
`boundary_series` knob rather than writing a fourth harness. Expect the answer to be *small*, because §4
says the operator only selects in 13.6 % of years.

**C. CO-OCCURRING GROSS TURNOVER — the lever §4 names.** Let a year apply the hazard's *gross* deaths AND an
establishment influx that restores the DRF's *net* target, instead of the current mutually-exclusive
branches. That would take the operator's duty cycle from 13.6 % of thinning years to every year. ⚠ It
changes the count identity's meaning AND the recruit channel at once, so it needs its own ADR, its own
matched control, and a carbon-closure re-check — and it must NOT be bundled with B.

**D. Still open, unchanged:** `CAP_HASH_SEED` (~10 lines at `build_slow_runtime_table.py:378-384`, default
`= seed` so every artifact stays byte-identical) — two justifications: the ssp370 noise-floor basis, and
ADR 0045 §4 falsifying `:370-371`'s "patch-years are exchangeable" premise. D1 (space-for-time surrogate)
and D3 (calibration curve) remain unrun and off the critical path. Two report numbers are still wrong in the
`.tex`: "37 % damping / `Rb` = −892" is arm **B `p14env-hash`, the REFUSED env arm** (the deployed ncond-8
arm is **−971.5 = 39.9 %**), and the `Rr` ceiling 0.9201 is superseded by the patch-year basis (**0.9543**).

**E. `fc.pft_ids` is now a CORRECTNESS requirement, not a nicety — M integration point #1.** The operator
errors on a non-tree id but a wrong-but-*valid* id passes silently, and `FDiffFastCore` defaults every tree
to beech (`fast.jl:147`), which would run the tropical and boreal PFTs on temperate wood-density mortality
(the ADR-0031 defect class). The S-side probes and testitems pass real ids from the fixture's `type` column;
**any M driver that enables `trait_mortality` must pass `pft_ids` first.** Raise it before M adopts the flag.

**F. Do not bundle.** Every arm lands separately with its own matched baseline **re-run in the same
generation, never inherited from a log** — the move that has now caught six wrong turns on this line.

**G. Two method notes worth keeping.** (1) Before believing a null, check the operator FIRED — the probe
prints `TraitMortDiag` (mean hazard, θ, hard kills, thinning years) first, for exactly this reason. (2) The
first suite run went red in the new testitem and one of the three failures was a **real gap in the
operator**: the mirror unreachable case (a hazard that is zero everywhere, so there is nothing to tilt) was
returning `shortfall = 0`, i.e. reading as "the count target was honoured" in the one year it could not be.
Fixed in the operator, not in the test — the reflex to check when a new assertion fails.

## Scope + ownership (ADR 0029)

**You own (exclusive):**
- `src/components/slow.jl`, `src/drf.jl`, `src/climbuf.jl`
- `scripts/*slow*`, `scripts/flux_ood_experiment.jl`, `scripts/diagnose_*`, `scripts/noise_floor_vs_emulator.py`
- `test/testitems/{slow_*,drf_*,recruit_copula_*,climbuf_*,carbon_ledger_*}`
- `lines/S/*`, `changelog.d/S-*.md`, ADRs 0030–0049

**Do NOT touch:** `src/run.jl`, `src/interface.jl` (line M owns the coupling seam) ·
`src/components/energy.jl` (line E) · `ext/` (line O) · `Project.toml` (integrator).
Shared, additive-only: `src/LPJmLFITEmulator.jl` (inside the `# ── line S ──` region), `CLAUDE.md`, `MEMORY.md`.

**SLURM tag prefix:** `S-` · **scratch:** write under `/p/tmp/jamirp/...` paths you created; other lines'
artifacts are **read-only**.

## The contract you must not silently break (S → M)

Line M runs your emulator inside the coupled loop. **Frozen:** `FluxDrivenSlowEmulator(fc, forest; …)` kwargs ·
the `flux_feature_vector` column order · the `live_flux_cond` subset (ADR 0025) · the `.drf`/`.rcop` format
(ADR 0023) · the `cell_meta.parquet` schema.
Train/inference consistency is load-bearing (ADR 0023), so **a conditioning change is by definition a
both-sides change**: write the ADR, bump a version in the artifact meta (never mutate an artifact in place),
and coordinate an integration point with M. Never re-point M's pinned artifact path from this line.

## Status (2026-07-28)

- **P1 is DONE**: the flux-driven S runs in the coupled loop, carbon-conserving to ~1e-12 gC (ADR 0018→0027).
- **The tree-PFT truncation is FIXED in code (ADR 0031, S1b).** `TREE_TYPES` now lives in ONE place
  (`lpjmlfit_emulator.data`) and `features.py` / `config.yaml` / all four `build_slow_*.py` /
  `noise_floor_vs_emulator.py` **import** it. The `growth_eff` `÷max(lai,EPS)` shift is fixed to the runtime
  rule (`fast.jl:369`) with a `GROWTH_EFF_MAX` assertion. Per-PFT mortality params are all seven `[VERIFIED]`.
  The **global re-derivation on the `t7` generation is IN FLIGHT** — see §NEXT for the job table.
- **⚠ EVERY global S number below with a "tree5" label is on the TRUNCATED population** (ids 1–5) and is
  superseded by its `t7` counterpart, not silently restated (ADR 0031 §5).
- *S1b `t7` job provenance (logs are in this worktree's `logs/`):* `1622131` historic copula + its chained
  ADR-0030 gate `1622436` · `1622337` pooled copula at `NCPUS=96` after `1622330` OOM-killed at 32 (exit 137) ·
  `1622134` pooled count DRF · `1622242` historic count + `1622305` its K-fold · `1622132` seed2 floor table.
  *S1c:* `1622718` regeneration + byte-identity gate · `1622724` after / `1622727` before re-measurement ·
  `1622741` + `1622792` (post-rebase) suite · `1622811` the gate re-run that returned **`PASS` (exit 0)** on the
  committed fixtures — S1c's binary success signal, so a `STALE-FIXTURE` exit 2 is now a NEW finding, not the
  expected state.
  *S1d cross-line:* line O's ADR 0082 §4 reached the SAME porosity-vs-WHC insight independently, online —
  and was calibrating against the RETIRED `swc` table (its quoted `mean 0.5075 / q50 0.4635` is exactly
  `cell_year_soilmoist_hist.parquet`). Notified in `lines/O/STATE.md` O3b. The two distributions have
  near-equal means (0.5075 vs **0.4780**) and completely different SHAPE — new: q10 **0.0000**, q25 0.0000,
  q50 0.4980, q75 0.8770, q90 0.9999. **A quarter of global cell-years have a fully dry root zone at year
  end**, which also answers whether a year-end reading is degenerate: it is not, globally (it saturates
  only at wet-winter cells like Hainich).
  *S1d:* `1622917` the root-zone soilmoist deriver (global, 1 348 400 rows) · `1622921` regeneration +
  drift control (`FAIL`/exit 1 = the CORRECT verdict — the edit is SUPPOSED to move the table here) ·
  `1622923` the gate-band re-measurement · `1622924` suite **107 076 pass / 0 fail / 4 broken**.
- **The committed Hainich demo artifacts are on ONE feature basis (S1c DONE, ADR 0032 closed → ADR 0034).**
  The `.rcop` + meta and both `hainich_slow_oracle_*.csv` regenerated **byte-identical**; only the count `.drf`
  + `_meta.txt` moved. The `.rcop`'s conditioning row is now inside the `.drf`'s trained band on **8/8** shared
  columns (0 violations), boundary tails equal. Suite **107 065 pass / 0 fail / 4 broken** (job 1622741).

  | Hainich gate quantity | assertion | proxy-basis `.drf` | **real-basis `.drf`** |
  |---|---|---|---|
  | Gate-3 Height `nqrmse` | ≤ 0.45 → **0.40** | 0.3895 | **0.2998** |
  | median Height ratio | 0.6 … 1.6 | 1.2463 | **1.1316** |
  | settled count ratio | 0.25 … 4.0 | 0.6734 | **1.2808** |
  | `target_history` band | 0.5…40 → meta `y`-band | 6.62 … 9.72 | 12.28 … 13.64 |
  | DIRECT draws SLA / Wooddens | ≤ 0.22 / ≤ 0.12 | 0.1274 / 0.0346 | **unchanged** (`.rcop` identical) |
  | coupled community SLA / Wooddens | ≤ 0.45 | 0.2558 / 0.2203 | 0.2634 / 0.2203 |

  Mechanism, one cause for all three headline moves: in-domain `bm_inc_cell`/`growth_eff` raise the settled
  count 6.8 → 12.9 stems/patch, and more stems on the same carbon are smaller trees ⇒ Height moves *down*
  toward the C truth. Re-measure with `scripts/measure_hainich_gate_bands_probe.jl` (`DRF_ART=` for a BEFORE
  column; it reproduced the documented 0.39/1.25/0.67 exactly, which is what validated the harness).
- **The demo emulator is runtime-consistent on 14 of 15 columns (S1d DONE, ADR 0035). The one remaining
  out-of-band column, `water_stress`, is LINE M's.** ADR 0034's four-column shift is closed on both S-owned
  causes — and neither was the cause ADR 0034 named (§S1d below). Measured job 1622923:

  | column | runtime | trained band | S1c excursion | **S1d** | cause / owner |
  |---|---|---|---|---|---|
  | `water_stress` | 0.323 … 0.331 | [0, 0.0432] | 6.6× | **6.60×** (unchanged) | F_diff vs the C — **line M** |
  | `soilmoist` | 0.9962 … 0.9968 | [0.7908, 1.0000] | 5.1× | **IN** | was the wrong VARIABLE — CLOSED |
  | `lai` | 3.63 … 5.12 | [0.7766, 4.7809] | 2.9× | **0.021×** (12-yr) / 0.086× (20-yr) | per-patch basis — CLOSED |
  | `fpc` | 0.607 … 0.791 | [0.1548, 0.7414] | 0.03× | 0.084× | never a basis error — DYNAMICS, see below |

  The pinned set in `slow_production_drf_tests.jl` is now **`Set(["water_stress"])`** alone, plus new bounds
  asserting `soilmoist` exactly inside and `lai`/`fpc` ≤ 0.2 band widths. **`fpc` is not S1d debt:** it was
  already `min(Σ fpc_ind, 1)` per-patch on both sides, so its residual is the coupled patch settling denser
  than the training upper tail — a dynamics outcome no basis fix can close. **Why the old gate never saw any
  of this is a proof, not a caveat:** a DRF prediction is a convex combination of training leaf means, so
  "predicted targets are inside the training band" can never fail — it is artifact integrity, not
  conditioning. Check the INPUT side.
- **S1d re-measurement (`[VERIFIED 2026-07-28]`, jobs 1622921 regeneration / 1622923 bands / 1622924 suite).**
  Both committed demo artifacts moved, regenerated TOGETHER from one table build; both oracle CSVs unchanged.
  The regeneration control confirms **only** `soilmoist`, `lai` and `growth_eff` (via its `lai` divisor)
  moved — every other column and the target `n_living` are byte-identical.

  | Hainich gate quantity | assertion | S1c | **S1d** |
  |---|---|---|---|
  | Gate-3 Height `nqrmse` | ≤ 0.40 | 0.2998 | **0.2990** |
  | median Height ratio | 0.6 … 1.6 | 1.1316 | 1.1547 |
  | settled count ratio | 0.25 … 4.0 | 1.2808 | **1.1597** |
  | `target_history` band | meta `y`-band [3, 19] | 12.28 … 13.64 | 11.66 … 12.52 |
  | DIRECT draws SLA / Wooddens | ≤ 0.22→**0.10** / ≤ 0.12→**0.06** | 0.1274 / 0.0346 | **0.0391 / 0.0273** |
  | coupled community SLA / Wooddens | ≤ 0.45 | 0.2634 / 0.2203 | unchanged |
  | carbon residual | < 1e-6 | 1.7e-12 | 1.9e-12 |
  | basis-agreement violations | 0 | 0 | **0** |

  **The Height drift did NOT move (0.2998 → 0.2990), and that is a finding:** the remaining Gate-3 residual
  is not a conditioning-basis artifact, so S5 must not budget a basis fix to pay for it. Two thresholds were
  **tightened**, none widened.

### Population widening — measured effect (historic copula table, seed2, `[VERIFIED]` job 1622132)

| | tree5 (pre-0031) | **tree7 (t7)** |
|---|---|---|
| survivor tree stems | 133 562 549 | **197 802 377** (+48 %) |
| cells | 45 072 | **54 058** (+8 986) |
| `minwscal` span | [0.025, **0.30**] | [0.025, **0.75**] — FIT's true range (id 0's interval) |
| `growth_eff` max / mean | 1.19e9 / 264 495 | **43 138 / 146.7** (the guard; seed1 reads 31 183 / 120.6) |

Seed1 equivalents `[VERIFIED]`: historic w20 = **197 721 867 stems / 54 020 cells** (exactly ADR 0031's census),
`growth_eff` max 31 183 with **0** `lai<=0` rows — the cross-seed-join diagnosis confirmed in production.
ssp370 w20 = **828 818 873 stems / 58 683 cells** (this is what OOM-kills a 32-cpu build; use `NCPUS=96`).

### Count DRF — before/after (like-for-like, same script + hyperparameters)

| metric | tree5 | **t7** | Δ | source |
|---|---|---|---|---|
| pooled table rows (historic+ssp370, w20) | 77 636 574 | **121 495 487** | +56 % | |
| pooled cells | 53 993 | **58 587** | +4 594 | |
| pooled held-out-BY-CELL TEST R² | 0.9852 | **0.9818** | −0.0034 | 1597387 → 1622134 |
| pooled in-sample R² | 0.9852 | **0.9819** | −0.0033 | |
| pooled by-cell OOS R² / RMSE | 0.9852 / 0.702 | **0.9819 / 0.707** | −0.0033 | |
| HOLD-OUT-BY-SCENARIO R², held out historic | 0.9847 (RMSE 0.714) | **0.9816** (0.709) | −0.0031 | 1600416 → 1622134 |
| HOLD-OUT-BY-SCENARIO R², held out ssp370 | 0.9847 (RMSE 0.714) | **0.9814** (0.716) | −0.0033 | |
| historic K-fold-by-cell per-row R² / RMSE | 0.9852 / 0.702 | **0.9821 / 0.699** | −0.0031 | 1581897 → 1622305 |
| historic **per-cell-mean R²** / bias | **0.9994** / 0.005 | **0.9987** / **0.001** | −0.0007 | |
| historic cells scored | 44 328 | **53 699** | **+9 371** | the previously-invisible tropical + larch cells |

### Trait POOLED-MARGINAL fidelity — before/after (K-fold-by-cell OOS, historic, `[VERIFIED 2026-07-28]`)

Jobs 1597648 (tree5) → 1622131 (tree7), same script + hyperparameters. `nqrmse = RMSE(q05..q95) / IQR(obs)`,
so it is **spread-normalized** — and the observed IQRs moved, which the headline ratio hides. Both are shown:

| axis | nqrmse tree5 | **nqrmse tree7** | headline | IQR ×  | raw RMSE tree5 → tree7 | **real gain** |
|---|---|---|---|---|---|---|
| SLA | 0.016 | **0.006** | 2.67× | 0.89× | 3.14e-4 → 1.05e-4 | **2.99×** |
| Wooddens | 0.022 | **0.008** | 2.75× | 1.13× | 1771 → 726 | **2.44×** |
| D95max | 0.028 | **0.008** | 3.50× | 1.20× | 7.29 → 2.50 | **2.92×** |
| minwscal | 0.038 | **0.008** | 4.75× | **2.47×** | 2.73e-3 → 1.42e-3 | **1.92×** |

**The improvement is real on every axis (1.9–3.0× in absolute quantile error), but do NOT quote the headline
ratios.** For `minwscal` the 4.75× is mostly its IQR growing 2.47× (the tropical PFT's `[0.05,0.75]` interval
entering the population); the honest number is 1.9×. `SLA` is the opposite case — its IQR *shrank*, so its
headline 2.67× **understates** a real 2.99×.

**This does NOT refute or confirm ADR 0031's degradation prediction.** ADR 0031 predicted that a single pooled
marginal per axis would be a *worse structural fit* once id 0's very different trait intervals were included —
that is a statement about **between-cell composition**, which is what ADR 0030's **per-cell-median** gate
measures. The table above is the **pooled global marginal**, a strictly weaker test that is blind to whether the
right cells got the right traits. The chained job **1622436** is the test of the actual prediction; until it
reports, the trait verdict is OPEN. Plausible reason the marginal improved anyway: 48 % more stems and 20 % more
cells is more training data per marginal DRF, and the truncated set was itself an awkward mixture to fit.

**Counts survive the widening essentially intact:** every count metric moves by ≈ −0.003 R² on a 56 %-larger,
markedly more heterogeneous population (the tropical belt + Siberian larch added), and the unseen-regime
generalization gap stays flat (holdout-by-scenario is within 0.0005 of the by-cell baseline, as before). So the
truncation was **not** materially inflating the count skill — the count DRF's headline claim is robust. The
trait side is where the population change was predicted to bite (ADR 0031), and that is what the in-flight
copula + 0030 re-measurement will show.
- **Trait per-cell medians — RE-MEASURED on `tree7` (`[VERIFIED 2026-07-28]`, ADR 0030 gate, job 1622436).**
  **Gate PASSED: `seed1-basis` = 1.000 on all four axes** (requirement ≥0.99), 52 165 cells scored (was
  36 228). Each population measured against its OWN floor and ceiling, which is what makes the columns
  comparable across a population change (ADR 0030 §4):

  | axis | emu_r | floor (rel_Y) | ceiling | **GAP** | r_center | sd(pred)/sd(Y1) |
  |---|---|---|---|---|---|---|
  | SLA | 0.866 → **0.885** | 0.964 → 0.973 | 0.981 → 0.986 | +0.115 → **+0.101** | 0.883 → **0.898** | 0.946 → 0.911 |
  | Wooddens | **0.567 → 0.807** | 0.694 → 0.937 | 0.794 → 0.965 | +0.226 → **+0.157** | 0.715 → **0.837** | **0.546 → 0.718** |
  | D95max | 0.771 → **0.812** | 0.791 → 0.833 | 0.873 → 0.909 | +0.102 → **+0.098** | 0.883 → **0.893** | 0.732 → 0.742 |
  | minwscal | **0.793 → 0.947** | 0.909 → 0.973 | 0.947 → 0.986 | +0.153 → **+0.039** | 0.838 → **0.960** | **0.736 → 0.970** |

  **ADR 0031's degradation prediction is FALSIFIED — see ADR 0033.** It expected a single pooled marginal to fit
  *worse* once id 0's very different trait intervals entered. Instead per-cell skill improved on **every** axis,
  and **most on the two that were worst**: Wooddens `emu_r` 0.567 → 0.807 and minwscal +0.153 → **+0.039 (near
  ceiling)**. The mechanism: the truncation was *destroying* composition signal, not hiding a need for per-PFT
  structure — the tropical belt is environmentally distinct (hot, wet, frost-free) AND carries id 0's distinct
  intervals, so with it present the environment↔composition link the copula conditions on is much *stronger*.
  So the "missing between-cell composition signal" diagnosis was largely an artifact of the truncated basis.
- Split-half 0.992–0.999 vs a floor of 0.833–0.973 ⇒ the floor remains **trajectory divergence**, not
  finite-stem noise. `rel_P` (0.993–0.999) still exceeds `rel_Y`, so the raw floor−emu gaps stay lower bounds.
- **The cross-population `tree5` row is the truncation's size, not a gap** — its `seed1-basis` reads
  0.976 / 0.556 / 0.814 / **0.174**, i.e. the script's own ≥0.99 guard correctly refuses it. That is the
  mechanism that made the pre-S1 numbers unreadable, now reproduced deliberately as a control.
- Seed2 floor artifact: `/p/tmp/jamirp/emulator_global/slow_copula_historic_seed2` (133 562 549 stems / 45 072
  cells; rebuild in ~70 s).
- Artifacts: `*_pooled_w20.{drf,rcop}` on `/p/tmp` (DVC); the committed `.drf`/`.rcop` are the Hainich demo.
- The online transient boundary (`src/climbuf.jl`, ADR 0027) is BUILT and offline-parity verified.

### `t8` — the GLOBAL generation on the ADR-0035 bases (`[VERIFIED 2026-07-30]`, ADR 0036)

Jobs: `1633248` ssp370 root-zone soilmoist deriver · `1633254`/`1633255` per-scenario count DRFs ·
`1633273` pooled count + scenario holdout · `1633275`/`1633276` count K-fold · `1641319` the STRUCT-axes
byte-identity gate · `1641321`/`1641322`/`1641323` the three copulas · `1641324` pooled count K-fold ·
`1641325` the seed2 companion · `1641372` the ADR-0030 gate · `1642638` the AR-rewrite gate ·
`1642642` the ssp370 rebuild · `1641863` the suite (**107 076 pass / 0 fail / 4 broken**).

**COUNT** — the population is intact and the basis move did not cost skill:

| | historic | ssp370 | pooled (w20 transient) |
|---|---|---|---|
| rows / cells | 22 467 348 / 53 699 | 99 028 310 / 58 496 | 121 495 658 / 58 588 |
| in-sample R² | 0.9827 | 0.9823 | 0.9824 |
| **K-fold-by-cell OOS R² / RMSE** | **0.9826 / 0.689** | **0.9823 / 0.698** | **0.9824 / 0.697** |
| held-out-CELL test R² | — | — | 0.9824 (5 744 cells) |
| hold-out-by-SCENARIO R² | 0.982 (held out historic) | 0.9818 (held out ssp370) | — |
| per-cell-mean R² / bias | 0.9988 / 0.0027 | — | — |

The pooled row count is exactly `22 467 348 + 99 028 310`, i.e. the pooled table always had the CORRECT
ssp370 row set — the streaming defect hit only the per-scenario static build (§NEXT).

**COPULA** — pooled OOS `nqrmse` (4 production traits) and the two diagnostic struct axes:

| scenario | SLA | Wooddens | D95max | minwscal | `agb` [diag] | `Height` [diag] |
|---|---|---|---|---|---|---|
| historic (uncapped, 197 721 867 stems / 54 020 cells) | 0.004 | 0.013 | 0.006 | 0.007 | 0.643 | 0.032 |
| ssp370 (`STEM_CAP=400`, 22 283 459 / 58 683) | 0.006 | 0.018 | 0.006 | 0.005 | 0.752 | 0.028 |
| pooled (`STEM_CAP=400`, 42 227 077 / 58 683) | 0.004 | 0.021 | 0.008 | 0.004 | 0.618 | 0.027 |

**`agb`'s `nqrmse` ≈ 0.6-0.75 is a METRIC ARTEFACT, not a miss** — read its quantiles: historic
`pred [10.15, 22.02, 47.53, 163.0, 2656]` vs `obs [10.30, 22.61, 49.51, 176.3, 2876]`, i.e. every quantile
within **1.5-7.6 %**, and pooled `KS ≈ 0.011`. `nqrmse` divides every quantile error by ONE IQR and per-stem
`agb` has `q95/IQR ≈ 10`. New `median_rel_q_err` reports it directly (**0.025**). Height matches to 0.2-1.2 %.

**ADR-0030 per-cell gate on `t8`** (historic, 52 165 cells, **`seed1-basis` = 1.000 on all six axes ⇒ PASS**):

| axis | emu_r | floor (rel_Y) | ceiling | GAP | r_center | sd(pred)/sd(Y1) |
|---|---|---|---|---|---|---|
| SLA | 0.881 | 0.973 | 0.986 | +0.104 | 0.894 | 0.907 |
| Wooddens | 0.814 | 0.937 | 0.964 | **+0.150** | 0.844 | **0.678** |
| D95max | 0.791 | 0.833 | 0.909 | +0.118 | 0.870 | 0.714 |
| minwscal | 0.945 | 0.973 | 0.986 | +0.041 | 0.958 | 0.970 |
| **`agb` [diag]** | 0.864 | 0.776 | 0.875 | **+0.011** | **0.987** | 0.822 |
| **`Height` [diag]** | 0.954 | 0.939 | 0.967 | **+0.013** | **0.986** | 0.967 |

**The VALIDATION FIGURE SET** (job 1641373 → `figures/emulator_validation/{historic,ssp370,pooled}_t8/`
+ `report_t8.html`; figures are git-ignored, the report inlines them all). Per-cell OOS skill, 6 axes:

| | count per-cell-mean R² | SLA | Wooddens | D95max | minwscal | **`agb`** | **`Height`** |
|---|---|---|---|---|---|---|---|
| historic — per-cell `r` | **0.9988** | 0.880 | 0.812 | 0.789 | 0.944 | **0.864** | **0.954** |
| ssp370 — per-cell `r` | **0.9989** | 0.903 | 0.814 | 0.770 | 0.962 | **0.869** | **0.954** |
| **pooled** — per-cell `r` | **0.9989** | 0.899 | 0.826 | 0.776 | 0.967 | **0.906** | **0.966** |
| pooled — median per-cell KS | — | 0.173 | 0.129 | 0.158 | 0.149 | **0.091** | **0.065** |
| pooled — pooled KS | — | 0.0039 | 0.0065 | 0.0020 | 0.0040 | 0.0099 | 0.0062 |
| pooled — median rel. quantile err | — | 0.0019 | 0.0059 | 0.0029 | 0.0050 | 0.0348 | 0.0048 |

**The two STRUCT axes have the LOWEST per-cell KS of all six** — the emulator reproduces a cell's biomass and
size distribution *better* than its trait distributions, which makes sense: `agb`/`Height` are dynamical
outcomes the flux conditioning speaks to directly, while a trait median is a PFT-composition statistic.

**STAND BIOMASS** (composite: OOS count × OOS per-stem `agb`, vs the C's own per-patch `sum(agb)`):

| | per-cell R² | log₁₀ R² | median pred:obs | basis_ratio | p10 / p90 | cells >10 % off | cells |
|---|---|---|---|---|---|---|---|
| historic | **0.931** | 0.945 | 1.020 | 0.995 | 0.961 / 1.004 | **3.0 %** | 53 699 |
| ssp370 | **0.920** | 0.963 | 1.013 | 0.982 | 0.868 / 1.124 | **30.7 %** | 58 496 |
| pooled | — REFUSED — | | | | | | |

**ssp370's 10× looser basis spread (30.7 % vs 3.0 %) is the `STEM_CAP` CLUSTER subsample showing up, exactly
as predicted** — historic is uncapped, ssp370 caps at 400 stems/cell and the cap keeps whole patch-years, so
its copula factor is over a different row subset than its count factor. The medians still agree (0.982), which
is why `basis_ok` passes; but quote ssp370's biomass number with that spread attached. **Pooled is REFUSED
outright** (its two tables weight the scenarios 81 % vs 53 % ssp370 — ADR 0036 §6).

**The trait axes are within ±0.02 of their `t7` values** (SLA 0.885→0.881, Wooddens 0.807→**0.814**,
D95max 0.812→0.791, minwscal 0.947→0.945) — expected, since `t8` changes the conditioning BASIS, not the
population. **Biomass and size are AT CEILING**: their per-cell medians are as reproducible as the model's own
seed-to-seed irreducibility allows. `agb`'s NEGATIVE raw gap (−0.088) is not a paradox — the emulator carries
no trajectory divergence, so it is *more* stable than one seed; the attenuation-corrected ceiling (0.875) is
the fair comparison and `emu_r` 0.864 sits just under it.

## Milestones

- **S1** Basis-clean noise floor → exact per-axis headroom. **DONE 2026-07-28 (ADR 0030)** — gate met
  (`seed1-basis` 1.000 ×4), headroom table in §Status, and it is what uncovered S1b.
- **S1b** **Widen the training population to FIT's complete tree set (ADR 0031).** Code + gates + docs **DONE
  2026-07-28**; the global re-derivation / re-validation / 0030 re-measurement is **IN FLIGHT** (§NEXT).
  Blocks S2. Side outcomes: the `lai==0` seed asymmetry is diagnosed (cross-seed feature join), all seven PFTs'
  mortality params are `[VERIFIED]` (ids 1/2/4/5 were also wrong, not just the two new ones), and the byte-identity
  gate exists as `scripts/verify_hainich_demo_artifacts.sh` + `scripts/diagnose_slow_table_drift.py`.
- **S1c** **Regenerate the committed Hainich demo `.drf` + `.rcop` onto ONE feature basis (ADR 0032).**
  **DONE 2026-07-28 (→ ADR 0034).** Both rebuilt from one table build; the `.rcop` + meta and both oracle CSVs
  came back byte-identical, only the count `.drf` moved. Basis agreement **8/8 shared columns, 0 violations**.
  Every drift threshold improved and the Gate-3 alarm was **tightened** 0.45 → 0.40 (numbers in §Status). Side
  outcome that became S1d: regenerating the artifact does NOT close the runtime↔training shift — 4 of 15
  columns are still out of band, from three causes, one of which is line M's.
- **S1d** **Put `soilmoist` and `lai` on ONE basis, runtime and training. DONE 2026-07-28 (ADR 0035).**
  Both of ADR 0034's S-owned diagnoses were **wrong**, and re-deriving them against the C source before
  writing the fix is what saved the milestone (`residual-diagnosis` §3):
  - **`soilmoist` was the wrong VARIABLE, not the wrong clock.** Training reduced the C `swc` = total water
    over **saturation** capacity; the runtime fed `state.w` = plant-available water over **WHC**. The
    handoff's "cheap side" (re-reduce `swc` to year-end) would have turned the alarm green over a mismatch.
    Both sides are now `ROOTMOIST / Σ_{l<3} whcs[l]` — root-zone, `whcs`-weighted, YEAR-END (a state, like
    the other seven state columns; the annual water integral is already `water_stress`). New deriver
    `scripts/build_rootmoist_soilmoist_feature.py`; new `root_zone_soilmoist` used at all three `slow.jl`
    sites. **Rejected** the ADR-0034 "clean" runtime annual-mean accumulator: it needs a daily hook in
    `run.jl`, which is line M's, so it would have parked this gate on another line's schedule.
  - **`lai` IS reconstructable per-patch** — the skill and the builder docstring both said it was not.
    `Σ LAI·fpc_ind/(1−exp(−k_pft·LAI))`, patcharea cancels; validated against the C's own crown allometry at
    median rel err **1.8e-8** (`scripts/diagnose_patch_lai_reconstruction.py`). Fixes the `growth_eff`
    divisor with it. **`fpc` needed no change** (already per-patch both sides — ADR 0034 mis-grouped it).
  *Gate met:* `soilmoist` IN band, `lai` 2.9× → 0.021×/0.086×, pinned set = `{water_stress}` alone, two
  thresholds tightened and none widened, suite green. Numbers in §Status; M notified in `lines/M/STATE.md`.
- **S2** **Close the trait headroom.** Expand the copula conditioning — `COPULA_COND_COLS` in
  `scripts/build_slow_runtime_table.py` **and** `live_flux_cond` in `src/components/slow.jl` **in lockstep** —
  with environment / PFT-composition covariates; global K-fold re-fit (`run_pooled_slow_copula.sh`); measure
  against the **re-measured** ADR-0030 gate. **Needs an ADR (0032) + an integration point with M** (artifact
  version bump). *Gate (ADR 0030 §4, replacing "r ≥ 0.75"):* close ≥50 % of the Wooddens GAP to the ceiling
  **and** lift `sd(pred)/sd(Y1)` to ≥0.75 on that axis, with pooled KS not degraded (≤0.02) and no other axis
  losing >0.01 of `r_center`. Report honestly if the conditioning does not deliver.
  **⚠ S1b already delivered a large share of this gate WITHOUT touching the conditioning (ADR 0033):** the
  Wooddens GAP closed 0.226 → 0.157 (**30 % of the way**, target 50 %) and `sd(pred)/sd(Y1)` went 0.546 →
  **0.718** (target ≥0.75 — nearly met), pooled nqrmse improved rather than degraded, and no axis lost
  `r_center`. So **re-baseline the S2 gate against the `tree7` numbers before starting**, or S2 will take credit
  for the population fix. The honest remaining target is the last ~20 % of the Wooddens GAP; minwscal (+0.039)
  and D95max/SLA (+0.098/+0.101, both `r_center` ≈ 0.89) have little left to win.
  **⚠ AND S1d comes first (ADR 0034 §5):** three of the columns S2 would condition on are still on the wrong
  aggregation basis, so an S2 run started now would again be crediting a basis fix — the same trap ADR 0033
  recorded when S1b silently delivered 30 % of this gate.
- **S3** Per-PFT / mixture copula. **DE-PRIORITIZED back to a fallback (ADR 0033 — reverses ADR 0031).** The
  argument for promoting it was that the copula predicted only 0.55 of the true between-cell Wooddens spread and
  had no composition covariate. On the complete population that dispersion ratio is **0.718** and `r_center`
  0.837 without any structural change, and minwscal went to near-ceiling — so the pooled marginal *does* capture
  composition once it can see the whole forest. Revisit only if S2's conditioning stalls above ~0.75 dispersion.
- **S4** **Grass ownership** (open risk #8): S owns grass demography; today grass stays F-side and S is
  TREE-only. Needs an ADR + a carbon-conservation gate for grass at the handoff.
- **S5** Whole-cohort **DROP** + the Gate-3 recursive drift (nqrmse 0.39 vs the documented 0.45 alarm).
- **S6** The **in-loop** OOD win — the offline 2.35× is `[VERIFIED]` (`flux_ood_experiment.jl`); the in-loop
  (recursive, coupled) OOD advantage is not yet demonstrated. Coordinate with M for the coupled harness.
- **S7 / Phase 3A** **Trait-dependent mortality** — the mechanism ADR 0046 confirmed as the lever for FIT's
  within-PFT wood-density warming shift.
  - **Stage 1 DONE 2026-08-04 (ADR 0047).** The hazard is ported in full (`src/trait_mortality.jl`), with
    its per-PFT parameters GENERATED from the C into one committed CSV that all three consumers gate
    against, and **no call site** — so nothing in CI moved. Suite **107 682 pass / 0 fail / 4 broken**
    (job 1694467, up from 107 076: the four new testitems). Docs verified locally (1694728 red → 1694742
    green after adding `TraitMortality` to `checkdocs_ignored_modules`; `docs` never runs on a branch).
  - **Stage 1b DONE (ADR 0048)** — the pre-flight. The k-cap merge is dormant at the default `k_cap`
    (0 merges / 150 yr) so it need not be fixed first, but it is trait-destructive at 3.1–5.1× the signal
    when forced; and the rollout's constant-forcing relaxation is 1.34× the signal, opposite in sign,
    settling at yr 52 ⇒ every response arm needs a matched constant-forcing control. Job 1694397.
  - **Stage 2 DONE 2026-08-05 (ADR 0049).** The hazard is wired into `reconcile_demography!` behind
    `trait_mortality = false` (default ⇒ inert), reconciled with the DRF's count target by a
    **proportional-hazards tilt** `f_i = (1 − mort_i)^θ` that recovers FIT exactly at θ = 1.
    `mort_water`/`mort_temp` are zero by decision (the emulator has neither integral on FIT's basis).
    Measured on the ADR-0048 protocol (Hainich only, matched constant-forcing control re-run in-process,
    0 k-cap merges): controlled Δ community `wooddens` **+7 899 = 3.25× the FIT shift, same sign**, carbon
    3.0e-11, count honoured every year, and the **age–wooddens gradient rises with age** (+6 565 in the
    80–160 yr bin, +9 642 in 160–320) — the ADR-0046 §3 signature. Suite **107 749 pass / 0 fail /
    4 broken** (job 1698873), docs green (1698958). The acceptance target is now the committed fixture
    `S_age_wooddens_gradient.csv` (job 1698771), which refined ADR 0046 twice (id 2 non-monotone too; id 5
    has no stems > 160 yr).
    **⚠ THE FINDING: the DRF's count channel, not the hazard, bounds the selection** — θ median 8.5e-12,
    θ > 0.5 in only 18 of 132 thinning years, because the demanded `|ρ−1|` has median 0.0 %/yr against the
    hazard's 1.688 %/yr. FIT's deaths and recruits CO-OCCUR; the emulator's mutually-exclusive `ρ<1`/`ρ>1`
    branches make gross turnover equal net change. **Co-occurring gross turnover is the named next lever.**
    ⚠ The arm is a constant-forcing **LEVEL** change on one cell — **not a response**, and not the ADR-0044
    gate. **This ADR exhausted the S block 0030–0049** (see §NEXT).
  - **Stage 3 DONE 2026-08-05 (ADR 0100) — Phase 3A is COMPLETE as a mechanism.** The RESPONSE arm: a 2×2
    of {`trait_mortality` on/off} × {historic, ssp370}, all four rollouts in one process at matched year
    indices, on REAL forcing from the same orderA `.clm` files the two ground-truth runs read (new extractor
    `scripts/build_hainich_response_forcing.py`, 3 gates green, Hainich contrast +2.45 K / +709 gdd5 /
    +2.53 K coldest month; 81 yr per corner; merge held dormant at `K_CAP=400`; carbon 0.8–1.6e-11).
    **The operator's contribution to the warming response = +3 400.6 gC/m³ = +1.40× the FIT shift, right
    sign.** ⚠ **THE FINDING: the emulator's BASELINE warming response has the WRONG SIGN and is larger** —
    `R_ctl` = −5 945.8 = **−2.44× FIT** where FIT rises +2432.9; the hazard shrinks it 57.2 % in magnitude
    (40.6 % of the gap to FIT) and cannot flip the sign. `R_ctl` **is** the recruit channel (ρ-thinning is composition-preserving, merge dormant),
    and the band diagnostic localises it to **`soilmoist` 0.658 band widths below a historic-only copula's
    training range (16× the historic arm)** while *excluding* `water_stress` (ratio 0.49×). Also measured:
    ADR 0049 §5's 13.6 % duty cycle is a **constant-forcing artefact** (real forcing: 54.2 % historic /
    **62.5 %** ssp370 — warming *loosens* the throttle), the k-cap merge **wakes under real forcing** and
    costs 54 % of the response contribution, and the transient boundary is **exactly inert** (0.0) for this
    cell's demo artifacts. `MODE=stage2` regression (job 1700483) reproduces every ADR-0049 headline number.
    New fixture `S_hainich_response_boundary.csv` + its testitem. **⇒ the next lever is the RECRUIT channel:
    re-run the 2×2 on the global `pooled_w20` artifacts (no new training) — §NEXT item A.**
  - **Stage 4 DONE 2026-08-05 (ADR 0101) — and it WITHDREW Stage 3's response claim.** Ran ADR 0100's own
    pre-registered prediction on the global artifacts, then asked the two questions it could not answer
    alone. `SEED` was hard-coded to 1; replicated, the double difference has a **seed sd of 0.67–1.74× FIT
    — the size of the effect**, and the operator's contribution to the warming response is
    **indistinguishable from zero on both global artifacts** (+0.048 [−0.380, +0.476] and
    +0.263 [−0.377, +0.903], n = 12 each; both CIs exclude ADR 0100's +1.40×). ADR 0049's **LEVEL** claim is
    confirmed and strengthened (+6 718 ± 286 / +7 041 ± 334 / +8 959 ± 862, t = 10.4–23.5) and is the
    quotable Phase-3A result. ADR 0100's headline finding was a single-cell **fixture** artefact whose sign
    reverses on a global artifact, and its attribution was wrong: **cell scope, not scenario coverage**.
    **⇒ Phase 3A is CLOSED.** The mechanism is right and its response contribution is unmeasurable at one
    cell; any response claim belongs to the ADR-0044 global gate (~115 seeds would be needed here).
- **S8 — THE COUPLED COUNT RECURSION. NEW, and the top of the queue (ADR 0102, 2026-08-05).** Answers line
  M's inbound ADR-0054. Decomposed into (A) exposure bias [training-side], (B) state incoherence
  [**measured EMPTY** — the clamp binds 0 of 150 yr], (C) **no level anchor** [the dominant one: retention
  **1.036** on a 4× initial-density perturbation after **300** yr, converging to a non-zero asymptote].
  (C) explains M's 59–72 % and completes M's own `9ad8721b` split (recursion ×1.26–1.53 vs a year-1 level
  offset ×1.05–1.12) by showing the level term never decays. **Specified, deliberately NOT landed** — it needs the count↔density conversion
  at the S↔F seam, so it is a two-sided change with M that moves every coupled baseline. **This DEMOTES S2
  from top priority.** Side outcomes landed here: M's `wscal_leafon` flip is unblocked from S's side, S→M
  integration point #2 is raised in M's STATE, and the public report is corrected + re-ordered.

## Line-local gotchas

- **Before arguing about AGGREGATION, check the two sides are the same QUANTITY (ADR 0035).** `soilmoist`
  spent a milestone mis-scoped as annual-mean-vs-year-end when the training column was the C `swc` (total
  water over SATURATION) and the runtime was `state.w` (plant-available over WHC). They overlap numerically
  (0.84–0.87 vs 0.79–1.00), which is exactly why the aggregation story looked right. See CLAUDE.md §3 for
  the `swc`/`rootmoist` formulas and why `swc` is not invertible.
- **"Quantity X is not reconstructable from the `ind` output" is a claim to RE-DERIVE, not to inherit
  (ADR 0035).** Both this skill and the builder docstring asserted per-patch LAI was unrecoverable; it was
  recoverable exactly, from two columns already emitted. Validate any such reconstruction against an
  INDEPENDENT C expression (crown area from `fpc_ind` vs from the height allometry), not against a quantity
  that differs from it for a *second* reason.
- **Anything inverted from the TXT `ind` table has a ~1e-5 precision floor** — `printind` uses `%g` = six
  significant digits (`fwriteoutput_ind.c:27`), and an inversion amplifies that. Don't set a tolerance below
  it; a genuinely wrong constant shows as a percent-level bias in the MEDIAN, not as a large max.
- **The `ind` writer emits only stems `height > height_min` = 5 m** (`fwriteoutput_ind.c:84`). Every training
  column is on that >5 m population, so it is self-consistent — but any comparison against an all-trees C
  grid output (`LAI_STAND`, `fpc_stand`) will show a biome-dependent deficit (0.77–1.01) that is NOT an error.
- **`age_mean` is the classic train/inference-shift trap** — train it as the nind-weighted mean cohort age
  (`mean(Age−1)`, start-of-year), NOT the elapsed-year counter (ADR 0024 supersedes 0023 §3).
- Never rename/clobber `test/testitems/references/drf_forest_hainich.drf` (+ `_meta.txt`) or
  `recruit_copula_hainich.rcop` — they are committed golden fixtures with bitwise round-trip tests.
- `*.drf`/`*.rcop` are **text** artifacts; `*.bin` is gitignored (writing one silently loses it).
- Diagnostic scripts must be `*_probe.jl` / `*_diagnosis.jl` / `*_decomp.jl` — a stray `*_test.jl` in
  `scripts/` fails the WHOLE suite at ReTestItems collection (and would red every other line).
- Read `.claude/skills/slow-drf-pipeline/SKILL.md` before touching the pipeline; it names every artifact.
