# LINE S — Component-S science (branch `line/S`, worktree `wt-S`)

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/S/JOURNAL.md` (append-only). Decisions: tier-1 block
> **0030–0049 is EXHAUSTED**; use the **tier-2 block 0100–0119** (opened by ADR 0100).
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here


### 0★ 🎯 THE ACCEPTANCE CRITERION CHANGED — READ THIS BEFORE PLANNING ANYTHING (owner, 2026-08-06; ADR 0106)

The owner has stated what **finished** means, and it **supersedes every per-milestone stopping condition on
every line**, including "at the seed1-vs-seed2 noise floor" and any five-cell verdict read as sufficient:

> the emulator must **fully emulate the original model**, "of course also and **especially under climate
> change**"; done = **everything, including trait distributions AND medians, within 10 % error**; and it is
> "**only finished when it's proven to be correct on ALL cells, not only a handful of test sites**".

**All cells = the 54 020 tree-bearing cells**, not 5 biome cells. **Both scenarios AND the response between
them.** A noise-floor statement is still the right *diagnostic*; it is no longer the *acceptance test*, and
**no line may call a milestone done on a five-cell result again** — nor present one as fidelity evidence
without saying it is 5 of 54 020.

⚠ **The binding constraint is the climate-change clause, not the fidelity numbers.** Trait medians are
already 9 of 10 within 10 % at the test cells, but the emulator's warming response is indistinguishable from
zero where the original rises, and **CO2 is a constant in every training row of every deployed artifact, so
there is NO CO2 response at all** (ADR 0004). **Work that improves present-day agreement is not progress
toward this criterion unless it also opens a response channel.** Plan accordingly.

⚠ One clause needed a decision and carries a stated default, not the owner's words: the original model is
stochastic and its own two runs differ by **29 % of the mean** for the per-patch count in a low-density cell,
so a literal 10 % is unmeetable there by ANY emulator. Default in use: tolerance =
**max(10 %, the original's own two-run spread for that quantity in that cell)**. Full record: ADR 0106.

**BOTH OF THIS LINE'S OPEN QUESTIONS ARE CLOSED, AND BOTH ANSWERS WERE "NO" (ADR 0105). Read ADR 0105
first, then 0104, then 0103.** Nothing is outstanding on the level anchor and nothing is owed by any line.
The next session should start at **item A** below, which is a genuinely new item, not a continuation.

**1. THE ANCHOR DOES NOT GET THE DEFAULT. The question is CLOSED, not deferred.** ADR 0104 §7's
re-registered criterion was run on the **25-patch ensemble** (line M's ADR 0057 made the basis available)
and **FAILS at all three settings** — clause 1 everywhere, clause 3b (stability) at `a` ≥ 0.25, clause 2
(memory) at the recommended 0.25. Jobs **1717190** / **1717247** (criterion + forced arm) and **1717189**
(memory). `anchor` stays shipped, opt-in, default `0`, unchanged in code.

**2. ADR 0104 §3 WAS A MODAL-PATCH ARTIFACT, and ADR 0104 §5 named the confound and published a
recommendation from it anyway.** Free-running terminal density/truth: **2.55 / 2.03 / 3.01 / 1.55 / 1.90×**
on the modal patch → **1.35 / 1.15 / 1.38 / 0.52 / 1.04×** on the ensemble; mean score **0.679 → 0.159**.
The anchor improves 3 of 5 and **worsens the mean** (0.159 → 0.166 / 0.181 / 0.194). Harness check: the
ensemble's own 2010 stem count reproduces the C's per-patch mean exactly in all five cells.

**3. `semiarid_sahel` IS 48 % UNDER-DENSE, NOT 55 % OVER.** Its whole ADR-0104 §4 reading inverts. It is
still the largest single error in the set (0.52× of the C) and still a real defect — just the other way up,
and not the anchor's.

**4. THE MECHANISM IS UNIFIED AND THE ANCHOR IS NOT AT FAULT.** It lands the stand on the count model's
absolute target exactly as ADR 0103 built it to. Given **F's own** canopy features that target is BELOW the
C's truth ⇒ it helps where the free stand is above truth, hurts where the stand was already right.

**5. TEACHER FORCING IS WORSE IN ALL FIVE CELLS** (score 0.149→0.277, 0.086→0.153, 0.180→0.259,
0.349→0.460, 0.029→0.069), **inverting ADR 0054's 59–72 %** — which was modal-patch AND scored on the
prediction, and survives neither fix. ⇒ **the multiplicative ratio update is NOT simply a defect that
discards the level (ADR 0102 §1): free-running it CANCELS a biased target.** Re-introducing that level is
exactly why both interventions hurt. Do not treat "the recursion is unanchored" as a standing defect claim.

**6. THE EXPOSURE BIAS IS EMPTY AND THE RETRAIN IS CANCELLED, NOT DEFERRED.** Priced offline from the
existing `_t8` tables before buying anything (`scripts/exposure_bias_probe.jl`, job **1717208**, 22.5 M
rows, 4 minutes): one-step bias **−0.0014** stems/patch/yr held-out-cell OOS on counts of ~10, AR gain
**g = 0.562** ⇒ a **bounded** 2.28× amplification to −0.038 stems (−0.4 %). Per-cell it predicts
+4.2 / −5.9 / +10.5 / −0.0 / +0.2 % against a coupled +35 / +15 / +38 / −48 / +4 % — wrong size in every
cell, wrong sign in two. This was the #1 remaining item; it is measured empty on its own terms.

**6b. THE VERDICT SURVIVES LINE E's ENERGY DEFAULT FLIP (ADR 0075), which landed on `main` between the
runs.** Re-run on the rebased tree (job **1717307**): REPORTS 8/9 identical **to every printed digit**,
`mean water_stress` to 4 dp. The null is meaningful because the new path demonstrably fired — the carbon
handoff residuals DO move at the 1e-12 level (boreal 1.080e-12 → 5.684e-13). Per-CONFIGURATION
re-verification, not per-protocol (ADR 0100's lesson).

**7. WHAT IS NOT WITHDRAWN** (ADR 0105 §6 — read it before throwing out the family): ADR 0103 §2's 300-year
retention measurement (a perturbation *ratio*, so the canopy basis cancels out of it — there IS no
restoring force, and `anchor` still removes it); the shipped opt-in anchor and its testitem; Sahel as a real
defect; ADR 0056's verdict (M said do not flip, and this says do not flip).

✅ **MERGED AND GREEN — nothing about ADR 0105 is outstanding.** Work sha `1a2ec7e2` merged to `main` as
**`803c62e2`**; `format` green on the branch sha AND on main's own post-merge run. The full Julia matrix
(`test (lts)` ✅, `test (1)` ✅, `test (macOS, lts)` ✅) ran and passed on the earlier branch sha `2a3b6fe2`,
and `git diff 2a3b6fe2 HEAD -- src/ test/ ext/ Project.toml` is **empty**, so the Julia tree that went green
is the one that landed. `test (pre)` is red with the documented `ScopedValues` prerelease `MethodError` at
LOAD time — confirmed from the job log, not waved away.
⚠ **CI fired the whole Julia matrix on a diff of `scripts/*.jl` + Markdown.** Not a surprise and not a bug:
GitHub filters on the **push span**, which after the mandated rebase contained line E's `src/components/energy.jl`
default flip. The `repo-commit` skill already documents this (line M hit it the same day) — predict the gate
set from `git diff --name-only <old-remote-tip>..HEAD`, not from `origin/main...HEAD`.

### DO THIS NEXT, IN THIS ORDER

**A. THE RESIDUAL IS A COUPLING / F-FIDELITY ITEM AND IT BELONGS TO LINE M — raise it with the measurement
attached, do not chase it from here.** ADR 0105 §5's last paragraph is the argument: the offline number is
computed with the count model fed the C's OWN features and the C's OWN previous count, so the gap between
it and the coupled error is, by construction, everything the loop adds — and that is F's canopy diverging
from the C's. The same run measures it directly (REPORT 5): over 2010–2019 F's `fpc` moves **1.56×** where
the C's moves **0.90×** (boreal), 1.27× vs 1.00× (Hainich), 0.71× vs 1.23× (Sahel). `src/fdiff.jl` /
`components/fast.jl` are **M's** paths (CLAUDE.md §9) and ADR 0053 already measured an F-side canopy bias.
**S cannot and should not fix this.** Write it into `lines/M/STATE.md` as an integration point with the
numbers, then stop.

**B. S2 CONDITIONING is once again the top S-OWNED item — by ELIMINATION, not by promotion.** ADR 0102
demoted it because an unanchored level "compounds without bound"; item 6 measures the compounding as
bounded and small, so that reason is withdrawn. The specified form is unchanged and its honest target is
still modest: the six moisture descriptors recomputed **per cell-year** rather than frozen at present-day
means — the only form that can carry a warming signal (ADR 0038/0040/0042; ADR 0042 §4's `Rr`/`Ra`
dissociation is the thing to read first). Unbuilt. Do NOT credit a basis or population fix to conditioning
(ADR 0033's warning).

**C. Still open, unchanged, off the critical path:** `CAP_HASH_SEED` (~10 lines at
`build_slow_runtime_table.py:378-384`, default `= seed` so every artifact stays byte-identical); D1
(space-for-time surrogate); D3 (calibration curve). S3 stays de-prioritized (ADR 0033); S4 (grass) is
unstaffed and needs F; S6 (in-loop OOD) needs M's harness.

**D. THE METHOD RULES EARNED HERE — the first one cost a published recommendation.**
1. **A reference basis has more than one axis, and NAMING a confound is not CLOSING it.** ADR 0104 applied
   the rule it had just earned to the *metric* axis and got it right, then named the *canopy* axis as an
   open confound, called its own measured benefit an upper bound — and published a recommended `a` from
   that arm anyway. **Never publish a default, a recommendation or a tuned value from an arm you have
   labelled an upper bound.** Either close the confound first, or publish the finding without the
   recommendation and say what would close it.
2. **An attribution arm inherits every basis error of the harness it runs in.** ADR 0054's teacher forcing
   was measured on the modal patch and scored on the prediction, and it reversed under *either* correction.
   A diagnostic arm is not more robust than a skill measurement just because it is diagnostic.
3. **Price a retrain offline before buying it.** Item 6 is 200 lines of Julia and one 4-minute job against
   a global two-artifact retrain and an ADR-0023 both-sides re-pin with line M. The tables already existed.
4. Both surviving rules from the previous cycle still hold: **read the diff, name the variable the change
   writes, confirm the metric is a function of it**; and **when a control arm and a truth disagree, score
   against the truth.**

**E. TOP-LEVEL, ALL LINES — `CLAUDE.md` §0a (owner instruction, 2026-08-06).** Reports to the owner go in
**plain language**: no decision-record numbers, no milestone or phase codes, no repo jargon standing in for
an explanation. User-facing text only; ADRs, STATE and code comments keep the precise shorthand. Translation
table in §0a.

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
`docs/component_s_public_report.*` + `docs/decisions/**` are outside the Documenter page tree; the merge
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
6. **The public report is corrected and re-ordered** (`docs/component_s_public_report.tex`). The damping is
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

**D. Report numbers to fix in `docs/component_s_public_report.tex`** — now three items, one new:
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
