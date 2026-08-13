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

> **LAST MERGE — 2026-08-13, ADR 0182 + 0183 are ON `main`.** Merge commit `af95bc55` (+ changelog
> collation `83718446`). Branch gates green on `7a922716` (`test (lts)`, `test (1)`, `format`,
> `test (macOS, lts)`); **`main`'s own gates green incl. `docs`** — which never runs on a branch, so it was
> also built locally first. The only red anywhere is `test (pre)`, which is `continue-on-error` and dies on
> **Julia 1.13.0-rc2** with `MethodError: no method matching setindex!(::Base.ScopedValues.ScopedValue{Bool},
> ::Bool)` — a prerelease API change in a dependency, unrelated to anything in this diff. Don't chase it.
> The suite on the flip is **275 606 pass / 0 fail** (job 1773556).

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
> | 0177 | the arms match FIT's sign where FIT thins, get it wrong where FIT gains, indistinguishable from a do-nothing null on DIRECTION. |
> | 0178 | 94–100 % of the apparent response was drift — but what it isolated is the DIRECT boundary channel only (ADR 0181 §6). |
> | 0179 | the climate channel is structurally WIDE OPEN (77 440 splits, 10.20 %) and carries almost nothing (4.4 % of a live channel over the operative excursion), at 12 cells. |
> | 0180 | de-leaking `n_prev` buys 2.85× on that channel; and the count is near-determined by the contemporaneous STAND (R² 0.9620 without `n_prev` ≈ the persistence null's 0.9623). |
> | 0181 | **the decisive table scan. Handed FIT's OWN stand, K-fold by cell over 51 767 of 54 020 cells, the de-leaked map delivers 0.292 of FIT's area-weighted response — and the STAND columns carry ALL of it (slope 0.994) while the direct climate channel gives 0.016 and the FLUX channel 0.037.** |
> | **0182** | **the arms' OWN stand DOES warm** — `S0`/`S0h`/`S1` RATIO 1.43/1.65/1.63 against FIT's own at the same 12 cells, cosine 0.88/0.76/0.91, and **cosine 0.97–0.99 where FIT's own stand moves substantially**. The "the stand does not warm" branch is CLOSED. |
> | **0183** | **the ported hazard IS `mortality_tree_ind`** — recall = precision = 1.0000, mean \|Δhazard\| 5e-18, over 1 568 744 stem-years at 15 cells; **recall 0.909–0.972 with the stress integrals zeroed** as the coupled loop feeds it ⇒ **`trait_mortality` FLIPPED ON**. |
>
> **Five things are now settled. Do not re-investigate them.**
>
> 1. **The training TARGET is not where the response is lost, so DO NOT start a target redesign.** ADR 0181 §4
>    measures the de-leaked map at 0.292 of FIT's response given a *perfect* stand — real skill, 2.4× short —
>    and §5 shows the map's response tracks the stand at slope 0.994.
> 2. **The count is an allometric consequence of the stand, not a learned climate response.** Its climate and
>    flux inputs together are ≤ 4 % of the per-cell response slope while holding ~14 % of the splits. No
>    reweighting of them can work.
> 3. **`roster_n_prev` must NOT be flipped opportunistically.** ADR 0181 §7.4 prices the flip as NEGATIVE on
>    the deliverable's axis (aggregate 0.707 → 0.292, tropical −0.47 → −2.48). ADR 0180's conditional is
>    superseded.
> 4. **The stand handed to the map DOES carry FIT's warming direction (ADR 0182).** Do not re-measure it — and
>    do not quote it as evidence for any arm either: the persistence null `NP`, which learns nothing, tracks
>    FIT's stand direction at 0.910 in the same cells, because **in a rung-2 arm the C grows the stand** and
>    every arm inherits its shift. And the arms' RATIO > 1 is stand MOBILITY, not a stronger response — the
>    declared drift control puts the arms at 3.0–3.6× and FIT itself at 5.39×.
> 5. **The ported hazard needs no further validation as a function (ADR 0183).** It reproduces the C to
>    floating-point noise when handed the C's inputs. Any remaining hazard question is about its INPUTS.
>
> ### B. THE NEXT ACTION — reconcile ADR 0181's 0.292 with ADR 0177's null, on the arms' OWN stand (NO NEW RUN)
>
> Two measured numbers do not yet fit together, and the gap between them is where the response is actually
> being lost:
>
> * ADR 0181: handed **FIT's own** stand, the map delivers **0.292** of FIT's area-weighted response, and it
>   converts stand shift → count response at slope **0.994**.
> * ADR 0177: the arms' **actual** count response is indistinguishable from a do-nothing null on direction.
> * ADR 0182: the arms' own stand shift is **≥ FIT's in magnitude and aligned in direction** (cosine 0.97–0.99
>   where FIT moves).
>
> If the map converts a warming stand faithfully and the arm's stand warms, the arm's count should carry
> ~0.292, not nothing. **Close the loop: run the map on each arm's OWN stand and score the resulting count
> response.** Everything needed is on disk — the dumps carry every one of the six stand features (that is what
> ADR 0182's `scripts/diagnose_rung2_stand_warming.py` already extracts and caches as `.npz` under
> `/p/tmp/jamirp/S_rung2_standwarm/cache/`), the four flux drivers are in the same `grow` records plus the
> `P` record's `rootzone_w`, and `rung2_s_demography_harness.jl` already assembles the row through the
> shipped `flux_feature_vector` (never copy it — ADR 0023).
>
> **Pre-registered reading, fixed before the run:**
> * map-on-arm-stand response ≈ 0.292 (say within a factor 1.5) ⇒ the loss is the map's own ATTENUATION and
>   the remaining work is calibration / the stand→count link, not the demography;
> * map-on-arm-stand response ≪ 0.292 ⇒ the arm's extra stand MOBILITY (ADR 0182 §4) is diluting the signal
>   and the demography operator is the work.
>
> Blessed statistic: the area-weighted aggregate response ratio via `diagnose_truth_yardstick.py`, on the same
> axis as ADR 0181's 0.707 / 0.292 / 0.685 — **and export `OUT_SUMMARY=` to /p/tmp first** (see §E).
>
> ### C. FLAG STATE
>
> | flag | state | what blocks it |
> |---|---|---|
> | `wscal_leafon` | **ON** | — |
> | `trait_mortality` | **ON since ADR 0183** | — flipped on the pre-registered criterion. **Guardrail 4 is now served by the OPT-OUT** `trait_mortality = false`: any control arm that wants the pre-0183 composition-preserving thinning must pass it EXPLICITLY, or it is measuring the new operator. Measured blast radius: **5 assertions of 275 605**, all in `slow_trait_mortality_operator_tests.jl`, all from that file's control relying on the old default (now fixed, plus a constructor assertion on the new default). Suite green after the fix: **275 606 pass / 0 fail** (job 1773556). No conservation gate, AD gate or committed baseline moved. ⚠ **Six probe scripts take the default by omission** (`kcap_merge_confound`, `biome_slow_oracle`, `wscal_leafon`, `biome_resilience`, `measure_hainich_gate_bands`, `diagnose_count_recursion_anchor`) and were deliberately left alone — so **every number they have already published is a PRE-0183 uniform-thinning number**; do not compare a fresh run against an old printed value without accounting for the flip (ADR 0183 §6). |
> | `roster_n_prev` | off | **keep it off** — measured NEGATIVE on the deliverable's axis (ADR 0181 §7.4). |
> | `recruit_establishment` | off | off for a GOOD measured reason (ADR 0172): a +2–8 % standing wood-density LEVEL offset at 5 cells, 2–10× the whole warming signal. Do NOT flip it to satisfy the steer. |
> | `trait_drought_mortality` (M's, in `fast.jl`) | off | **an integration point to RAISE, not a flag to flip** (ADR 0183 §5.3). It supplies the two stress integrals `slow.jl::_trait_hazards!` currently zeroes. Measured: they carry **29–37 % of FIT's graded hazard mass but only 3–9 % of its certain kills**, so the certain set does not need them. What is unmeasured is trait ORDERING among non-certain stems — criterion pre-registered in ADR 0183 §5.4 (Spearman rank ≥ 0.9 between zeroed and full hazard over non-certain stems, plus a same-sign wood-density selection differential). |
> | `per_pft_params` (M's) | off | M's call |
>
> ### D. OPEN INTERFACE LIMITS — both in the C hook (line M's `rung2_apply.c`), not in S's code
>
> * **`ERROR043: rung2 apply: duplicate roster key (pft P, tree N)`** killed 82 of 510 runs. The guard is gated
>   on **either** env var (`rung2_apply.c:118`), so it fires in the pure OBSERVATION path too. Cells **23318
>   and 33335 lose their baseline in both scenarios**, 46336 its ssp370 baseline. `fread_tree.c:64-66` rules
>   out the naive explanations; mechanism OPEN. **Raise with M: the key `(pft_id, treeidx)` is not unique.**
>   ADR 0182's coverage gate quantifies the cost: **92 of 510 legs unscoreable**, which is what caps rung 2 at
>   12 cells instead of 15.
> * **Cell 22732's `S0h`/`S1` ssp370 arms HANG at the rendezvous**, reproducibly, at low concurrency, and in
>   the frozen variant too ⇒ cell-specific. Excluded, not scored early.
>
> ### E. GOTCHAS PAID FOR IN THIS INVESTIGATION
>
> * ⚠ **A PRE-REGISTERED THRESHOLD IS NOT A PRE-REGISTERED VERDICT.** ADR 0181's probe defined both threshold
>   pairs before the run, warned in its own header which statistic binds — and then branched on the *other*
>   one, printing SUPPORTED for a PARTIAL arm. **Grep your verdict expression for the blessed statistic's
>   variable name before submitting**; if the blessed number comes from a different job, print no verdict.
> * ⚠ **A DIFFERENCE OF LEG MEANS IS NOT A RESPONSE UNTIL A DRIFT CONTROL SAYS SO** (ADR 0182). Declare the
>   control with the thresholds, before the run, and **read the reference's own drift rate too** — FIT's was
>   the largest of all five arms and would have been very easy to present as an arm defect.
> * ⚠ **A PER-FEATURE RATIO EXPLODES WHEREVER THE REFERENCE SHIFT IS NEAR ZERO** (ADR 0182 §7 — `age_mean`
>   read 26.5 at the first smoke cell). Report the arm's own signed shift beside the reference's; keep ratios
>   for a vector norm, whose denominator is bounded away from 0.
> * ⚠ **PRECISION CAN BE 1.0 BY CONSTRUCTION** (ADR 0183 §7). Before quoting a precision/recall pair, ask
>   whether the perturbation under test can only move the statistic one way — zeroing two non-negative
>   additive hazard terms cannot create a false certain kill, so precision carried no information at all.
> * ⚠ **A HAZARD-MASS SHARE AND A DECISION-SET SHARE ARE DIFFERENT QUESTIONS** — they disagreed by 4–10× here.
> * ⚠ **CHECK WHICH QUANTITY A HARNESS ACTUALLY FEEDS ITS TEST BEFORE BUILDING AN ADR ON IT** (ADR 0183 §2).
>   ADR 0176 §4's whole blocker rested on the arms using FIT's own hazard; `Tree.mort` is the PORTED one and
>   its own field comment says so. Read the field, not the surrounding prose.
> * ⚠ **DUMP HEADER OFFSET:** the header is `#H T phase lon lat …` while the record is `T grow <lon> …`, so
>   name *n* is field *n+1*. It fails loudly on a string column and SILENTLY between two float columns.
> * **`diagnose_truth_yardstick.py` writes to a COMMITTED shared fixture by default** and a `COUNT_DIR`-only
>   run DROPS every trait row from it. **Always `export OUT_SUMMARY=`** to /p/tmp, and read `git status` after
>   any analysis job.
> * **A tree-ensemble sensitivity read as a derivative returns 0 for almost every row** — piecewise constant
>   (ADR 0105). Use an observed secant and check the shift clears the quantization step.
> * **Run the liveness panel FIRST.** In ADR 0179 it prevented the wrong write-up; in ADR 0182 it cleared all
>   six features in every leg before any shift was read.
> * **`priority` caps a USER at 10 concurrent jobs** (`sacctmgr show qos`, `MaxJobsPU`); `short` on `standard`
>   has no per-user cap and identical hardware.
> * ⚠ **NEVER EDIT A BASH SCRIPT WHILE IT IS RUNNING** — bash reads it incrementally from a byte offset.
> * ⚠ **`pkill -f <pattern>` also kills your own waiter loops** whose command text contains the pattern.
> * **The sbatch wrappers forward a FIXED list of env names** — and `NCPUS`, not `CPUS`, is the thread knob
>   for `sbatch_julia.sh` (it sets `JULIA_NUM_THREADS=$NCPUS`). `export` any knob of your own.
> * **Never put a `#` comment inside a generated LPJmL config heredoc** — LPJmL pipes its config through `cpp`.
