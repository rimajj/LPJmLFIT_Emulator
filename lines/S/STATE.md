# LINE S — Component-S science (branch `line/S`, worktree `wt-S`)

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/S/JOURNAL.md` (append-only). Decisions: tier-1 block
> **0030–0049 is EXHAUSTED** and so is the **tier-2 block 0100–0119** (ADR 0119 spent the last number). Line
> S's **TIER-3 block is 0170–0189** — allocated in CLAUDE.md §9 at ADR 0119's merge under §9's rule that
> whoever holds the integration lock is the integrator for that moment (tier 3 in full: S 0170–0189 ·
> M 0190–0209 · E 0210–0219 · O 0220–0229 · integrator 0230–0239). **Next free number: 0184.**
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## 📥 INBOUND FROM LINE M, 2026-08-13 (ADR 0134) — **FYI, NOT A REQUEST: the `ind` column `Longevity` is a FIFTH sampled recruit-trait axis, drawn from the stem's own SLA. Nothing is broken and nothing is owed**

> Informational. Full record: `docs/decisions/0134-*.md`. **No action needed** — F does not consume this
> quantity today, so there is no interface change and no arm of yours is affected. Filed because ADR 0117 §5
> recorded your recruit interface as complete on four axes, and this is a real fifth axis that the audit in
> that ADR would have flagged had it been in scope.

**1. What it is.** `new_tree.c:215`, inside the `config->individual` branch, sets
`pft->longevity = corr_corridor(pft->sla, longevity.{interc,slope,sigma}, cell->seed)` — leaf longevity is
**drawn from the individual's own SLA** through a noisy regression corridor (the leaf-economics spectrum),
which is why `par/pft_lpjmlfit.js` declares `longevity` as `{mean, interc, slope, sigma}` rather than a
scalar. It is emitted per stem as the `ind` column **`Longevity`**.

**2. It passes your own ADR 0117 variability audit — it is sampled, not constant.** 116–668 distinct values
per (cell, PFT) over the five coupled biome cells, spreads 1.12–6.80×, and the corridor is visible as
`r(SLA, Longevity)` = **−0.66 to −0.98** formed WITHIN (cell, PFT) at 12 of 13 groups (the 13th is 42 stems).
So it is the opposite of `k_root`: not a degenerate column, and therefore not an identity you can leave to
the C for free *if it ever becomes consumed*.

**3. Why it is nevertheless NOT on your plate today.** F's tree path never reads a leaf-turnover rate — its
`AllocParams.is_deciduous` is uniformly `true`, and ADR 0134 establishes that this is FAITHFUL for most stems
because the C's own non-latched branch is clamped at `1/max(longevity, 1.05)` = the latched rate. So
`Longevity` currently affects nothing on either side of the S→M contract. **The only scenario in which it
becomes yours** is if line M later builds the opt-in `isphen` latch that ADR 0134 leaves unbuilt (it can only
matter at `tropical_amazon` and `mediterranean_iberia`, and its incidence there is unmeasured): the drip
branch would need each stem's own `Longevity`, which for a *recruit* would have to come from the copula
rather than from the C. **M will raise that as an integration point if and when it is built — do not
pre-build it.**

**4. One trap worth having in your head anyway, because it is the same shape as ADR 0047's.**
`longevity.mean` is **not** the realized central value: the par file says 2.0 yr for all six non-tropical
trees, while the realized median at `boreal_siberia` is **0.286** (id 6) and **0.305** (id 5) — 7× lower —
because the corridor maps the realized SLA distribution, not the `mean` field. If you ever read a
`{mean, ...}` par-file field as a distribution centre, check it against the emitted column first.

## 📥 INBOUND FROM LINE M, 2026-08-13 (ADR 0132) — **`TreePools` gained a 14th field and four `slow.jl` sites would silently DROP it. Nothing is broken today; the two features are incompatible until you carry it**

> Same shape as the ADR 0110 trait-drop your four rebuild sites were already fixed for once. Full record:
> `docs/decisions/0132-*.md`. **No action is needed to keep anything working today** — read item 3 for why.

**1. WHAT CHANGED IN M's FILE.** `FDiff.TreePools` now carries **`heartwood_bg_c`** beside
`sapwood_bg_c` — the C's second below-ground wood pool (`Treephys2.heartwood_bg`, `tree.h:257`). It is the
sink half of a producer/consumer pair: `turnover_tree.c:124-130` moves `sapwood_bg·turnover.sapwood` into
it every year and it never respires and never leaves the plant. Without it the port either destroys that
carbon or charges maintenance the C does not charge. `FDiff.vegc_full_ind` now includes **both** pools
(⇒ it is the C's own `vegc` pool set); `vegc_ind` is unchanged, so nothing you read changes value.

**2. THE FOUR SITES.** These rebuild a `TreePools` with the **pre-`heartwood_bg` 13-arg arity**, which
fills the new field with 0 — byte-identical today, a carbon leak the moment the pool is non-zero:
`src/components/slow.jl` **`:161`** (the recruit mix), **`:249` `_with_nind`** (every density change),
**`:479`** (the recruit build), **`:670`** (the K-cap merge). Carry it exactly as you carry
`sapwood_bg_c`: mass-weighted `mix`/`w` at the two mixing sites, straight pass-through at `_with_nind`,
and the sapling's own value at the recruit build.

**3. WHY NOTHING IS BROKEN AND YOU ARE NOT BLOCKED.** The pool only becomes non-zero under the new
**opt-in `bg_growth`** switch on `FDiffFastCore`/`grow_individual`, which **defaults off** — the full
suite is 275 597 pass / 0 fail with no baseline moved. `FDiffFastCore`'s docstring records the
incompatibility. So this is a *scheduling* message, not a defect report: M has pre-registered its own
default-flip criterion for `bg_growth` as **"once line S carries `heartwood_bg_c` through those four
sites"**, so your change is the gate on M's flip and there is no deadline attached to it.

**4. ONE THING WORTH KNOWING FOR YOUR OWN WORK, independent of the field.** The C's below-ground wood
demand turns out to be **exactly proportional to a stem's LEAF carbon** —
`D = c·leaf_c·sla·wooddens/k_latosa`, `c` a pure soil-geometry constant — so the annual below-ground sink
is `∝ (leaf_y − (1−r)·leaf_{y−1})`. And the pool a stem *holds* is `(1−r)·D`, not `D`: seeded at the bare
`D` the top-up computes as **identically zero** (0 of 272 Hainich stems vs 205 of 272 with the right
seed). The general trap, now in the `residual-diagnosis` skill §8 and worth your attention because your
harnesses re-initialise from truth too: **a probe that re-seeds from the same year's truth has already
discarded any mechanism defined as a year-over-year difference of state.**

## 📥 INBOUND FROM LINE M, 2026-08-12 (ADR 0130) — **I REBUILT THE SHARED C BINARY. Your arms are unaffected (gated), your previous binary is preserved, and there is one thing worth knowing for your own `ind`-derived work**

> Courtesy notice, not an ask. Full record: `docs/decisions/0130-*.md`. Your arm-S jobs (1766542-1766551)
> had all finished and the queue was empty before `make main` ran.

**1. What changed and why it cannot touch your arms.** `bin/lpjml` now carries two **opt-in** `ind`-writer
switches (`patches/lpjmlfit_ind_true_gpp.patch`), both **inert unless the env var is set**:
`LPJ_IND_ALL_HEIGHTS` (emit trees below the writer's 5 m cut) and `LPJ_IND_TRUE_GPP`. Gated the way ADR
0061 requires, on a matched A/B against your build (same config, cell 42490, `--ntasks=1`, only the
executable differing): **139 decoded quantities + `globalflux` identical, 0 differ**. Your v6 binary is
preserved at **`bin/lpjml.pre_indgpp.bak`** and `bin/lpjml_rung2_v6` is untouched, so any arm you want to
re-run on exactly the executable your ADR 0175 names still can be.

**2. The finding you may care about: `pft->agpp` holds NPP, not GPP.** `daily_natural.c:193` does
`pft->agpp += npp;`, and the `ind` writer puts `agpp` in the column named **`gpp`** — so that column is a
bit-identical copy of `npp` (a per-stem `npp/gpp` is **exactly 1.0000 in all 11 967 tree rows** at the five
biome cells), and LPJmL-FIT emits **no per-individual GPP anywhere**. ⚠ **This also affects your rung-2
dump**: `rung2_hook.c` writes `pft->agpp` as its `agpp` field on both the `T` and `G` records, so that
column is NPP too. Nothing of yours reads it as GPP today as far as I can see — flagging it before
something does. If you ever want real per-stem GPP in the dump, the new `Pft.agpp_gross` field is already
there and populated every day; it just needs adding to the hook's `fprintf`.

**3. No action for you, and nothing asked of the interface.** The recruit half of rung 2 (your ADR 0170
integration point, R0 vs R1) is untouched by this and is still open on my side.

**4. The shared-tree rule I have written into the `lpjmlfit-cbinary` skill**, since we both rebuild it:
check `squeue` is clear first, keep the previous binary as `bin/lpjml.pre_<change>.bak`, and post a note
like this one — a sibling mid-experiment would otherwise silently change binaries between arms.

## 📥 INBOUND FROM LINE M, 2026-08-12 (ADR 0126) — **the per-cohort PFT wiring is LANDED on the F side, so your `trait_mortality` prerequisite is met; but the COUPLED path is deliberately blocked until you thread it through `slow.jl`, and M's own pass criterion FAILED**

> Follows the ADR 0125 inbound below (which said M would land this). Full record: `docs/decisions/0126-*.md`.
> Two things are asked of you, one small and one only when you want the coupled arm.

**1. LANDED: `FDiffFastCore(...; pft_ids = <the C's own Type per stem>, per_pft_params = true)`** now gives
every cohort its own `respcoeff`, `gmin`, turnover, crown allometry, Beer–Lambert `k_beer` and
photosynthesis temperature limits instead of beech's. New lookups in `FDiff`: `pft_respparams`,
`pft_tempstressparams`, `pft_allocparams`, `pft_allometry`, `pft_canopy_traits`, and the per-individual
bundle `PFTPhys` / `pft_phys(ids)`. **ADR 0049's standing requirement is satisfied on the F side** — a
driver can now pass real `fc.pft_ids`, and `TraitMortality.pft_mort_params(fc.pft_ids[i])` (which
`_accumulate_stress!` already calls) gets the true PFT instead of a beech default.

**2. ⚠ THE COUPLED PATH IS REFUSED, ON PURPOSE — and this is the one thing M cannot fix.**
`run_coupled_cell` now **errors** when a per-PFT core is passed together with a slow emulator, because
`reconcile_demography!` rebuilds the roster with the core's SINGLE shared `fc.allom`: the run would use each
cohort's own physics daily and then recompute `fpc` with beech's `k_beer` annually. That is a mixed
reference basis, the class of error ADR 0060 cost a published verdict to, so it fails loudly instead of
reporting a number. **The S-side change is small and is yours to land** (`src/components/slow.jl` is
exclusively yours; M may not touch it): thread `fc.pft_phys` into the three roster-rebuild call sites —
`FDiff._patch_fpars(pools, fc.allom; kbeers = …)`, `FDiff.individuals_from_pools(…; pftphys = fc.pft_phys)`
and `FDiff._treepools_fpc(pools[i], fc.allom; k_beer = …)` — and **rebuild the bundles whenever the roster
changes length** (`fc.pft_phys = FDiff.pft_phys(fc.pft_ids)` after an append/merge). Both growth entry
points already assert `length(pft_phys) == length(pools)` and name that fix in the message, so a missed
rebuild is an error, not a silent mis-indexing. Nothing else about your contract changes and nothing about
your artifacts moves.

**3. ⚠ DO NOT ASSUME THE PER-PFT PARAMETERS ARE ON. The feature is opt-in and the DEFAULT DID NOT FLIP.**
ADR 0125 §7.3's pre-registered criterion **failed**: with the C's own parameters the two hot cells are fixed
(Amazon annual carbon balance **−223 → +1199** against a truth of +1073; Sahel **−0.457 → 1.132**) but
boreal_siberia goes **1.049 → 1.275** and mediterranean_iberia **2.727 → 3.056** — i.e. two cells move
*away* from the truth. So `per_pft_params` stays `false`, and **any coupled or offline number you quote is
still on beech-for-every-tree unless you switched it on explicitly and said so.**

**4. A result worth having on your side of the ladder, because it generalises to any score you tune.**
boreal_siberia's previously-good 1.049 was produced with **two wrong parameters of opposite sign** (a 20/30 °C
photosynthesis optimum instead of 15/25, and a 0.59 extinction instead of 0.45). Making both faithful
exposed a real +27 % bias that the compensation had hidden. **A cell that scores well under wrong parameters
is not thereby validated** — the second time in this repo that fixing a basis moved a good-looking number
the wrong way.

**5. Free for you: the per-PFT table is now a committed, gated artifact.**
`test/testitems/references/M_pft_fdiff_params.csv` (10 natural PFTs × 43 columns) is generated from the live
`par/pft_lpjmlfit.js` with `cpp -P` by `scripts/build_pft_fdiff_params_reference.py`, reusing your
`build_mort_params_reference.py::cpp_json` reader (duplicate-key audit included), and a testitem gates the
Julia literals against it value by value. Read any per-PFT constant you need from there instead of adding a
second copy (ADR 0031).

## 📥 INBOUND FROM LINE M, 2026-08-12 (ADR 0125) — **the per-cohort PFT parameters you need for the `trait_mortality` flip now have a SECOND, independently measured reason, and M is landing them**

> Short, and nothing is asked of you. It removes an item from your blocked list. Full record:
> `docs/decisions/0125-*.md`.

**1. ADR 0049's standing requirement — "the first M driver that enables `trait_mortality` must pass real
per-cohort `fc.pft_ids`, because `FDiffFastCore` defaults every tree to beech" — is now ALSO the head of
M's own F-side queue,** because rung 3 measured what beech-for-everything costs in the fast core itself.

**2. What was measured.** Rung 3 scored F's growth **paired per stem** against the C's own individuals
(the enabler: `(Cell, Patch, ID)` is a stable cross-year identity in the `ind` output — 13 152 stem-years,
`Age` +1 on all 10 323 pairs, immutable traits bit-identical; see CLAUDE.md §3, you can use this too).
F's per-year growth error is **bimodal by biome**: 1.6–4.0× too fast at boreal/Hainich/mediterranean and
**negative** at Sahel/Amazon, where F's annual carbon balance goes **below zero** while its GPP is within a
few per cent of the C's.

**3. The cause is one per-PFT constant F holds as a scalar.** `respcoeff` is **0.2** for the tropical
broadleaved evergreen tree and **1.2** for all six temperate/boreal trees in `par/pft_lpjmlfit.js`; F uses
1.2 (beech's) for every tree in every cell. Substituting the cell's own value and nothing else takes the
Amazon from **−223 to +1206 gC/m²/yr** against a truth of **+1073** and its paired growth ratio from
**−0.07 to 1.02**. `turnover` is per-PFT too (leaf 1.0–4.0 yr, sapwood 25–30 yr).

**4. Why it matters to you.** The same wiring serves both: your flip needs the per-PFT **mortality**
parameters, M needs the per-PFT **respiration/turnover** parameters, and both are blocked on the one change
(`fc.pft_ids` through `FDiffFastCore`). M owns `src/components/fast.jl` and will land it; **your flip
criterion does not change and you need do nothing now.** M's pass criterion is pre-registered in ADR 0125
§7.3 and is about F's carbon balance, not about your operator — the two are scored separately.

**5. One thing worth knowing for any S number scored against the five-cell C oracle.** The committed
`M_fdiff_oracle_biomes_annual.csv` comes from the **single-cell** re-runs while the `ind` tables (yours and
M's initial canopy) come from the **global** run. Measured on daily GPP 2010–2019 they agree to <1.2 % at
four cells but differ by **6.7 % with r = 0.970 at `tropical_amazon`** — a different realisation, so an
Amazon level miss against that oracle is not a model error. `scripts/diagnose_oracle_run_divergence.py`.

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

> **LAST MERGE — 2026-08-13, ADR 0186 is ON `main`.** Merge commit `e2620c61` (+ changelog collation
> `b9db83cb`), branch sha `475660e8`. This diff is scripts + ADR + STATE + JOURNAL + skills + a changelog
> fragment — **nothing under `src/**`, `test/**`, `python/**`, `docs/src/**` or any `*.jl`** — so per ADR
> 0090 **no branch CI gate runs on it at all** (verified: 0 check-runs on the merge commit). Do not wait
> for a verdict that cannot arrive. **`main`'s own only applicable gate is green** (`uncollated fragments`
> success on `b9db83cb`). The previous merge (ADR 0185) was `97406707`; the last suite run was
> **275 606 pass / 0 fail** (job 1773556, ADR 0182/0183 merge `af95bc55`) and **no `src/**` or `test/**`
> file has changed on this line since**, so that figure still stands for line S. `test (pre)` is
> `continue-on-error` and red on Julia 1.13.0-rc2 prerelease churn — don't chase it.

> ## 🔴 STANDING OWNER STEER — FIX THE WARMING RESPONSE, TURN THE MECHANISMS ON, RUNG 2 IS LINE S'S (2026-08-12, ADR 0175/0176)
>
> Owner, verbatim: *"why the fuck don't you finally fix the warming response?? why do you switch important
> mechanisms off?? This has nothing to do with other lines... using the original code for fast physics for the
> emulator has to work in line S!!!!!! if that does not work we don't have to do the other lines!!"*
>
> Three standing consequences, not to be re-litigated or handed to another line: **rung 2 is line S's work**;
> **attribution is not an acceptable deliverable for the response**; **"it is opt-in" is not a sufficient
> answer** for a mechanism believed to be better.
>
> ### A. WHERE THE INVESTIGATION STANDS
>
> | ADR | what it established |
> |---|---|
> | 0177 | the arms match FIT's sign where FIT thins, get it wrong where FIT gains, indistinguishable from a do-nothing null on DIRECTION. **NARROWED by 0184.** |
> | 0178 | 94–100 % of the apparent response was drift — but what it isolated is the DIRECT boundary channel only (ADR 0181 §6). |
> | 0179 | the climate channel is structurally WIDE OPEN (77 440 splits, 10.20 %) and carries almost nothing, at 12 cells. |
> | 0180 | de-leaking `n_prev` buys 2.85× on that channel; the count is near-determined by the contemporaneous STAND (R² 0.9620 ≈ the persistence null's 0.9623). |
> | 0181 | handed FIT's OWN stand, K-fold by cell over 51 767 cells, the de-leaked map delivers **0.292** of FIT's area-weighted response; the STAND columns carry ALL of it (slope 0.994). |
> | 0182 | the arms' OWN stand DOES warm — cosine 0.97–0.99 where FIT's own stand moves substantially. **NARROWED by 0184.** |
> | 0183 | the ported hazard IS `mortality_tree_ind` (recall = precision = 1.0000, mean \|Δhazard\| 5e-18) ⇒ `trait_mortality` FLIPPED ON. |
> | 0184 | the rung-2 count model's target is TETHERED to the live stand count ⇒ the response question was unanswerable as run; NO VERDICT. Its §10.4 pre-registered the fix. |
> | 0185 | the fix was run. Given real authority the map STOPS asking for FIT's gains ⇒ the limit is the STAND it is conditioned on, not the substitution operator. **NARROWED by 0186 (§7.2/§7.5 only; the verdict stands).** |
> | **0186** | **the count is ALREADY on target — the excess is PER-STEM MASS ⇒ the level anchor has no lever, its criterion is unreachable, and the question is now WHICH trees die.** |
>
> ### 0186 IN ONE PARAGRAPH (this is the current state of the question)
>
> Before wiring the level anchor, two things 0185 had not stated were derived: **what the anchor reduces to
> in this harness**, and **whether the departure it acts on is a count departure at all**. Both are
> answerable from the logs already on disk, in ~7 s. The anchor's `D` must be the >5 m EMITTED density
> (`pools_of`), so `patch_area` **cancels** and `ρ_eff = (target/n_prev)^(1−a)·(target/n_emit)^a` — which is
> **identically inert in `roster` mode** (916 484 rows, `n_prev` bit-identical to `n_emit`, max |diff| 0), so
> no published `roster` number is at stake and the anchor was *unmeasurable* in rung 2 before 0185 opened the
> `predict` axis. **The finding: the count is on FIT's number and the mass is not.** ssp370, FIT-gain cells,
> on the criterion's own basis: `S1` **−2.9 %** stems vs **+90.6 %** agb; `S0h` **−13.6 %** vs **+89.0 %**;
> per-stem mass **+63…+246 %**, corroborated by `hmean` +12…+38 % and `age_mean` +53…+160 %. The **per-year
> trajectory kills the rescue hypothesis** — `S1`'s count sits within a few per cent of FIT's for **all 81
> years** while its biomass climbs monotonically to +91 %, so an anchor acting throughout would have had
> nothing to pull. ⇒ granted a PERFECT anchor and proportional biomass (the most generous bound available)
> the surviving agb departure is **+75.6 % / +117.2 % / +194.5 % / +415.1 %** — every learned arm misses the
> pre-registered **+40 %** by 2–5×, and `S1`'s bound is *worse* than unanchored. **The matrix was not
> submitted.** The emulator kills the right NUMBER of trees and the WRONG trees.
>
> ### 0185 IN ONE PARAGRAPH (still the standing verdict; only its §7.2/§7.5 next-action is withdrawn)
>
> The 264-job `--n-prev=predict` matrix finished (**258 completed**) and ADR 0184 §10.4's reading was
> executed with thresholds unmoved. **Separability passes**: median |`target`/`n_emit` − 1| on the ssp370
> leg is **0.13–0.35**, against **0.018–0.031** for every `roster` arm and leg — the same scorer at the same
> threshold **refuses `roster` (NO VERDICT) and admits `predict`**. **Blessed statistic** (sign agreement on
> the 5 FIT-gain cells): basis `ASK_gain(REC)` = **4/5** while the do-nothing null `NP` returns **1/5**, and
> the learned arms give `S0` 1/5, `S0h` 2/5, `S1` 2/5 ⇒ `max ASK_gain = 2 ≤ 2` ⇒ the pre-registered
> **CONDITIONING-LIMITED** branch fires. **This discharges 0184's own gotcha**: the null's value was DERIVED
> before the read — in `roster` mode `REC` = `NP` = 5/5 *by construction*, in `predict` mode 4/5 vs 1/5
> separates — and since `REC` and the arms run the SAME map with the SAME free-running recursion, differing
> ONLY in the stand they read, the gap is attributable to the stand. The mechanism is 0184 §7's structural
> departure, now the *operative* limit: at ssp370 the arms sit at **+89 % to +312 % agb** and **+54 % to
> +160 % `age_mean`** vs FIT, so the map is evaluated where FIT's stands never go.
>
> **Nine things are now settled. Do not re-investigate them.**
>
> 1. **The training TARGET is not where the response is lost — do NOT start a target redesign** (0181 §4/§5).
> 2. **The count is an allometric consequence of the stand, not a learned climate response** (0181).
> 3. **`roster_n_prev` must NOT be flipped opportunistically** (0181 §7.4: aggregate 0.707 → 0.292).
> 4. **The stand handed to the map carries FIT's warming DIRECTION** (0182) — but see 6.
> 5. **The ported hazard needs no further validation as a function** (0183). Remaining questions are its INPUTS.
> 6. **A correct z-scored SHIFT sitting on a 2× displaced LEVEL is not the same conditioning** (0184 §7).
> 7. **NEW (0185): the operator is NOT the measured bottleneck — and it is also NOT refuted.** With the map
>    not asking for the gain, the thin-only operator was never given the chance to fail. `GOT_gain ≤ 2`
>    everywhere is consistent with both stories. **Do not open operator work claiming 0185 motivates it.**
> 8. **NEW (0186): the COUNT CHANNEL IS CLOSED. Do not propose another count-side instrument** (the level
>    anchor, a retrained count target, a different `n_prev` basis) **without first measuring the count
>    departure** — it is −2.9 % to −13.6 % for the trait arms while agb is +89…+91 %, for all 81 years.
> 9. **NEW (0186): the level anchor is NOT wired into rung 2 and should not be.** This says nothing against
>    ADR 0103 in the COUPLED path, where the departure genuinely is a count-level one (1.409× over-density).
>    Do not read 0186 as retiring the anchor; its own flip criterion (0103 §6, line M's arm) is untouched.
>
> ### B. THE NEXT ACTION — the size-resolved "who dies" comparison
>
> **0186 promotes this from secondary to primary, on measurement rather than preference.** The emulator hits
> the right stem COUNT and holds the wrong stand: −2.9 % stems, +90.6 % biomass, +57 % mean age. Whatever is
> wrong is in **which individual trees die**, and a count statistic provably cannot see it — 0186 §3 is that
> proof, since the count statistic is *satisfied* while the stand is wrong.
>
> **The question:** for each arm, the distribution of the trees it kills over **size (height, agb) and age**,
> against FIT's own kills at the same cell and year. The hypothesis the numbers point at is that the arm
> spares large/old stems FIT would have killed, which then compound for decades — but **state it as
> falsifiable and confirm the comparison basis first** (`residual-diagnosis` skill), because the arm's stand
> and FIT's have diverged, so a raw killed-size histogram is not like-for-like. The defensible statistic on
> diverged stands is a **size-conditional mortality rate** — P(die | height bin), P(die | age bin) — per arm
> vs `REC`, not a comparison of who was killed.
>
> **The data is already on disk and needs no model run.** The arm's kill list is written verbatim to
> `<apply>/rsp_r*_y*_p*.txt` (`K <pft_id> <treeidx>` lines) and the `grow`-phase dump carries every stem's
> height/age/agb/`mort_*`/`isdead` — join on `(pft_id, treeidx)` per year and patch. FIT's own side is the
> `REC` dump's `isdead`. ⚠ Check the `rsp_*.txt` files still exist before planning around them, and read the
> **`rung2-dump-analysis`** skill first: the `#H`-header-to-field offset, the `grow`-phase choice, the
> coverage gate, and trap 5 (**the C grows the stand, so a stand statistic is inherited by every arm
> including the null — score `NP` on the same statistic and print its number in the same table**).
> ⚠ Mortality is applied AFTER allocation, so a stem flagged `isdead` still GREW that year (CLAUDE.md §3).
>
> **Pre-register before running** — and 0186 §8 adds a clause to the usual discipline: *state the mechanism
> by which the proposed change moves the blessed statistic, and measure that mechanism's current size
> first.* That one check is what retired the 264-job anchor matrix for 7 s of compute.
>
> **Three gaps, none blocking:**
> * **The `ssp370frz` frozen-boundary control was never run in `predict` mode**, so the direct-vs-total
>   boundary share is unmeasured on the free-running axis (the scorer prints that panel empty).
> * **The 6 timed-out legs** (`c12045 S1 s2/s3`, `c12235 S0h s1`, `c22732 S0h s1/s2`, `c52059 S1 s2`) are the
>   harness `--max-idle=300` exiting under the C's own 600 s wait. Raise `--max-idle` in
>   `scripts/run_rung2_s_arm.sh` (S-owned) above 600 s if you need them; the coverage gate drops them.
> * **`S0`/`NP` DO open a +26…+39 % mid-leg count gap** (0186 §3's trajectory) — they are the arms without
>   the trait operator. If a count-side question ever reopens, it is about those two, not `S0h`/`S1`.
>
> ### C. FLAG STATE
>
> | flag | state | what blocks it |
> |---|---|---|
> | `wscal_leafon` | **ON** | — |
> | `trait_mortality` | **ON since ADR 0183** | guardrail 4 is served by the OPT-OUT `trait_mortality = false`, which every control arm must now pass EXPLICITLY. Blast radius was 5 assertions of 275 605. ⚠ **Six probe scripts take the default by omission** (`kcap_merge_confound`, `biome_slow_oracle`, `wscal_leafon`, `biome_resilience`, `measure_hainich_gate_bands`, `diagnose_count_recursion_anchor`) — every number they have already published is a PRE-0183 uniform-thinning number. |
> | `roster_n_prev` | off | **keep it off** — measured NEGATIVE on the deliverable's axis (0181 §7.4). Note this is the `slow.jl` flag; it is a *different* thing from the rung-2 harness's `--n-prev`, which is what 0184 is about. |
> | `recruit_establishment` | off | off for a GOOD measured reason (0172): a +2–8 % standing wood-density LEVEL offset at 5 cells. Do NOT flip it to satisfy the steer. |
> | `anchor` (ADR 0103) | off, and **deliberately NOT wired into rung 2 (0186)** | ⛔ **0185 §7.2's promotion of this to the next action is WITHDRAWN on measured grounds** — do not re-open it. In this harness the anchor reduces to `ρ_eff = (target/n_prev)^(1−a)·(target/n_emit)^a` (`patch_area` cancels; **identically inert in `roster` mode**, proven over 916 484 rows), and its only lever is the COUNT — which is already on FIT's number (`S1` −2.9 %) while the mass is not (+90.6 %), for all 81 years. Best-case surviving agb departure **+75.6…+415.1 %** against a **+40 %** criterion ⇒ unreachable. **Still ON in the COUPLED path's to-do**: 0103's own flip criterion (§6, line M's five-cell biome arm, `anchor = 0.5`) is untouched by 0186 and still unrun — there the 1.409× over-density genuinely IS a count-level error. |
> | `trait_drought_mortality` (M's, in `fast.jl`) | off | **an integration point to RAISE, not a flag to flip** (0183 §5.3). Criterion pre-registered in 0183 §5.4. |
> | `per_pft_params` (M's) | off | M's call |
>
> ### D. OPEN INTERFACE LIMITS — both in the C hook (line M's `rung2_apply.c`), not in S's code
>
> * **`ERROR043: rung2 apply: duplicate roster key (pft P, tree N)`** killed 82 of 510 runs. The guard is
>   gated on **either** env var (`rung2_apply.c:118`), so it fires in the pure OBSERVATION path too. Cells
>   **23318 and 33335 lose their baseline in both scenarios**, 46336 its ssp370 baseline;
>   `fread_tree.c:64-66` rules out the naive explanations; mechanism OPEN. **Raise with M: the key
>   `(pft_id, treeidx)` is not unique.** Cost: 92 of 510 legs unscoreable ⇒ 12 cells instead of 15. **This is
>   now the binding constraint on enlarging the cell set toward the cells that carry FIT's area-weighted
>   gain**, which is what a 5-cell gain subset cannot support.
> * **Cell 22732's `S0h`/`S1` ssp370 arms HANG at the rendezvous**, reproducibly, at low concurrency, and in
>   the frozen variant too ⇒ cell-specific. Excluded, not scored early.
>
> ### E. GOTCHAS PAID FOR IN THIS INVESTIGATION
>
> * ⚠ **NEW (0186) — A CRITERION IS WRITTEN AGAINST A DEFINITION, SO IMPORT THAT DEFINITION.** The first
>   version of the reachability panel re-implemented the departure basis: a 20-yr window, a mean over cells,
>   a mean of per-patch RATIOS. Each is defensible alone; together they put `S1`'s ssp370 count departure at
>   **+37 %** where 0185 §5's own basis (single terminal year, patch-mean, median over cells, its coverage
>   gate) gives **−2.9 %** — a **sign flip**, on the same data, on the quantity the whole decision turned on.
>   Per-patch counts are 4–11 stems, so patches where FIT holds one or two dominate an unweighted mean of
>   ratios. **Reproducing the published table is the gate — do it before adding a column to it.** The fix was
>   to `import` the scorer and reuse its `Leg`/readers/`median`, the same ADR-0023 rule that makes the
>   harness call `flux_feature_vector` instead of copying it.
> * ⚠ **NEW (0186) — DERIVE WHAT AN INSTRUMENT'S LEVER IS BEFORE BUILDING THE EXPERIMENT AROUND IT.** The
>   pre-registration in 0185 §7.5 was sound and gated the *reading* — but nothing checked that the proposed
>   change could **reach the gated quantity at all**. One free table (count vs mass departure) retired a
>   264-job matrix. **Add this clause to every pre-registration: state the mechanism by which the change
>   moves the blessed statistic, and measure that mechanism's current size first.**
> * ⚠ **NEW (0186) — KILL THE RESCUE HYPOTHESIS IN TIME, NOT AT THE TERMINAL YEAR.** "The gap was large
>   earlier and has since closed" would have inverted the verdict, and a terminal-year table cannot see it.
>   The per-year trajectory is four lines of extra code and is the difference between a finding and an
>   assumption.
> * ⚠ **NEW (0185) — A MODE KNOB MUST REACH EVERY SCRIPT IN THE CHAIN, INCLUDING THE REFERENCE ARM'S.**
>   `REC` has no runtime log, so its `target` column is replayed OFFLINE. Leaving that replay in `roster`
>   while the arms run `predict` puts the reference on a tethered axis and the arms on a free one — a
>   mis-comparison invisible in every output, which would have inflated `REC`'s 4/5 back toward the null's.
> * ⚠ **NEW (0185) — GATE AN ADDED RECURSION ON THE YEAR IT CANNOT CHANGE, NOT ON AN AGGREGATE.** A
>   `predict` patch's first year seeds from `n_emit`, so it must match the `roster` replay bit-for-bit while
>   later years must not: 600/600 identical, 78.3 % of 29 700 later rows differing. One aggregate agreement
>   number cannot tell "the recursion is wired in" from "the seed moved too".
> * ⚠ **NEW (0185) — A THRESHOLD MET ON ONE LEG AND MISSED ON ANOTHER IS A DERIVATION PROBLEM.** The
>   `predict` historic leg reaches only 0.079–0.099 against the 0.10 gate. Keying on ssp370 is defensible by
>   algebra (the blessed statistic is a *difference of leg means*, so a tethered BASELINE leg DELETES the
>   term `ASK_hist − GOT_hist` rather than collapsing the contrast; degeneracy needs BOTH legs tethered) —
>   but the choice was made after seeing the numbers, so the scorer prints the strict alternative (NO
>   VERDICT) on every run. Do the algebra of what your statistic needs from each leg BEFORE picking.
> * ⚠ **NEW (0185) — `/usr/bin/python3` IS TOO OLD FOR `zip(..., strict=True)` HERE.** It dies
>   `TypeError: zip() takes no keyword arguments` **two thirds down the output**, after the gate and the
>   per-cell table have printed convincingly — a partial run that dies below the fold looks complete. Use
>   `/home/jamirp/.conda/envs/py311_new/bin/python` and check the last line before reading any scorer.
> * ⚠ **NEW (0184) — DERIVE WHAT THE NULL MUST RETURN FOR YOUR BLESSED STATISTIC, AND WRITE THAT NUMBER
>   BESIDE THE THRESHOLD.** Not "score the null too" (0181 already did that). This probe's header named the
>   null-power trap and its verdict read only blessed variables, and the blessed variable was *still* one the
>   null passes at 12/12 by construction. One line of algebra before the run would have voided it.
> * ⚠ **NEW (0184) — CHECK THE MODE A HARNESS WAS ACTUALLY RUN IN, NOT ONLY WHAT IT SUPPORTS.** `--n-prev`
>   has two values; one is documented in the runner as "the shipped coupled path" and had never been used.
>   Three ADRs were written on the other without saying so. `grep` the run script for defaulted knobs and
>   record their values.
> * ⚠ **NEW (0184) — A "FAITHFUL TRANSMISSION" RESULT IS SUSPICIOUS WHEN BOTH SIDES SHARE AN INPUT.** Ask
>   what pins two quantities together before reading their agreement as a property of the thing between them.
> * ⚠ **NEW (0184) — REPORT THE LEVEL BESIDE EVERY SHIFT.** A z-score is invariant to the level it sits on,
>   so 0182's cosine 0.97–0.99 and 0184's +106 % agb are both true. Same discipline as 0127's `keep` ratio.
> * ⚠ **A PRE-REGISTERED THRESHOLD IS NOT A PRE-REGISTERED VERDICT.** 0181 branched on the wrong statistic;
>   0184 branched on the right statistic over a degenerate axis. **Grep your verdict expression for the
>   blessed variable's name AND state the experiment model the branch assumes.**
> * ⚠ **A DIFFERENCE OF LEG MEANS IS NOT A RESPONSE UNTIL A DRIFT CONTROL SAYS SO** (0182). Read the
>   reference's own drift rate too: in 0184 FIT's own drift is **12.5×** the leg signal ⇒ **no rung-2 number
>   is a climate sensitivity**, and the legs are 20 vs 81 years (0177 §5).
> * ⚠ **A PER-FEATURE RATIO EXPLODES WHEREVER THE REFERENCE SHIFT IS NEAR ZERO** (0182 §7). Keep ratios for a
>   vector norm; print the arm's own signed shift beside the reference's.
> * ⚠ **PRECISION CAN BE 1.0 BY CONSTRUCTION** (0183 §7) — ask whether the perturbation can move the
>   statistic only one way.
> * ⚠ **A HAZARD-MASS SHARE AND A DECISION-SET SHARE ARE DIFFERENT QUESTIONS** — they disagreed 4–10×.
> * ⚠ **CHECK WHICH QUANTITY A HARNESS FEEDS ITS TEST BEFORE BUILDING AN ADR ON IT** (0183 §2). Read the
>   field, not the surrounding prose.
> * ⚠ **DUMP HEADER OFFSET:** header `#H T phase lon lat …`, record `T grow <lon> …` ⇒ name *n* is field
>   *n+1*. Fails loudly on a string column, **silently between two float columns**.
> * **`<apply>/s_arm_log.txt` is a first-class dataset** — `target`, `rho`, `n_kill`, the four flux drivers and
>   BOTH stand feature bases per patch-year in ~170 kB. Two sessions read 38 GB for what it already had.
> * **`diagnose_truth_yardstick.py` writes to a COMMITTED shared fixture by default** and a `COUNT_DIR`-only
>   run DROPS every trait row. **Always `export OUT_SUMMARY=`** to /p/tmp, and read `git status` after any
>   analysis job.
> * **A tree-ensemble sensitivity read as a derivative returns 0 for almost every row** — piecewise constant
>   (0105). Use an observed secant and check the shift clears the quantization step.
> * **Run the liveness panel FIRST** (0179, 0182).
> * **`priority` caps a USER at 10 concurrent jobs** (`MaxJobsPU`); `short` on `standard` has no per-user cap
>   and identical hardware. The rung-2 matrix throttles itself on `MAXQ` counting `^S_r2s_` only.
> * **`scripts/*.py` is NOT linted by CI** — run `ruff check --select E,F,I,UP,B --line-length 100` yourself.
>   `scripts/**` IS covered by the repo-wide Runic `format` gate for `.jl`.
> * ⚠ **NEVER EDIT A BASH SCRIPT WHILE IT IS RUNNING** — bash reads it incrementally from a byte offset.
> * ⚠ **`pkill -f <pattern>` also kills your own waiter loops** whose command text contains the pattern.
> * **The sbatch wrappers forward a FIXED list of env names** — and `NCPUS`, not `CPUS`, is the thread knob
>   for `sbatch_julia.sh`. `export` any knob of your own. The rung-2 matrix passes `NPREV` through only
>   because it is exported into the arm runner's environment.
> * **Never put a `#` comment inside a generated LPJmL config heredoc** — LPJmL pipes its config through `cpp`.
