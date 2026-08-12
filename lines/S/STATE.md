# LINE S — Component-S science (branch `line/S`, worktree `wt-S`)

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/S/JOURNAL.md` (append-only). Decisions: tier-1 block
> **0030–0049 is EXHAUSTED** and so is the **tier-2 block 0100–0119** (ADR 0119 spent the last number). Line
> S's **TIER-3 block is 0170–0189** — allocated in CLAUDE.md §9 at ADR 0119's merge under §9's rule that
> whoever holds the integration lock is the integrator for that moment (tier 3 in full: S 0170–0189 ·
> M 0190–0209 · E 0210–0219 · O 0220–0229 · integrator 0230–0239). **Next free number: 0170.**
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

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
> ### A. WHAT LANDED THIS SESSION — the scenario-pair machinery exists and runs; see ADR 0177
>
> The warming-response experiment now RUNS end to end: 15 cells spanning the global climate range
> (growing-degree-days 519 → 9043), both legs of the scenario pair (historic 2000–2019 from `restart_1999`,
> ssp370 2020–2100 from `restart_2019`), a per-cell **and per-scenario** `ARM=REC` baseline (ADR 0041 forbids
> scoring a single-cell re-run against the global truth), and arms `NP`/`S0`/`S0h`/`S1` at 5 seeds. 510 runs.
>
> **Three defects were found and fixed on the way in; two of them would each have invalidated the whole
> measurement, so read these before touching the harness:**
>
> 1. **The harness conditioned every year on a FROZEN PRESENT-DAY CLIMATE.** It read its 4-column bioclimatic
>    tail ONCE from the 5-cell registry `M_cells.csv`, whose value is the per-cell 2000–2019 climatology. On an
>    ssp370 leg that shows the count model present-day climate for all 81 future years, so the two legs differ
>    only through the roster and **any measured warming response is driven to ~0 by construction** — an
>    unfalsifiable experiment, not a null result. Fixed: `--boundary-csv` advances the tail per year, the same
>    ADR-0026 treatment the shipped runtime already applies and the pooled forest was trained under. Unset, the
>    old static behaviour is kept, so ADR 0176's arms still reproduce byte-for-byte.
> 2. **`scripts/run_daily_subset.sh` could not generate a runnable ssp370 config at all** — its CO2 path named
>    a file deleted when `climclusterpy_package/` was reorganised on 2026-07-27/28. Repointed to the recovered
>    copy (md5 `ed5699b9c92d4d25857889f644b153db`, verified).
> 3. **The baseline and the arms had drifted onto DIFFERENT BINARIES.** `run_rung2_replay_arm.sh`'s
>    `MODE=record` hardcodes `bin/lpjml`, which line M rebuilt on 2026-08-12 21:12 for the ADR-0130 `ind`
>    switches, while the arms run `bin/lpjml_rung2_v6`. `ARM=REC` now lives in `run_rung2_s_arm.sh`, pinned to
>    the same `$BIN` as the arms by construction.
>
> ### B. THE RESULT (ADR 0177) — and it is a NEGATIVE one, stated plainly
>
> `response = terminal(ssp370) − terminal(historic)`, scored against each cell's own `REC` baseline.
> **FIT's own response is NOT one-signed**: it thins at 7 of the 12 scored cells and GAINS stems at 5.
>
> | | where FIT THINS (7) | where FIT GAINS (5) |
> |---|---|---|
> | `NP` (persistence null) | 7 / 7 sign correct | **1 / 5** |
> | `S0` (shipped uniform) | 7 / 7 | **1 / 5** |
> | `S0h` (interface control) | 7 / 7 | **1 / 5** |
> | `S1` (trait ordering) | 6 / 6 | **2 / 5** |
>
> **The learned demography thins almost everywhere.** It matches FIT's sign wherever FIT thins and gets it
> wrong where FIT gains — and **the persistence null reproduces that pattern exactly (8/12 for NP, S0 and
> S0h alike)**, so on the DIRECTION of the warming response the count model is indistinguishable from doing
> nothing. It does buy magnitude: through-origin slope `NP` 2.559 vs `S0` 1.481 ± 0.093, `S0h` 1.333, `S1`
> 1.441 ± 0.050. **But I² is 93–99 % for every arm** (per-cell ratios −7.5 … +15.5), so there is no common
> effect and **the pooled slope may NOT be quoted as "1.4× too strong"**. The per-cell table is the result.
>
> ### B2. ⚠ IT IS NOT YET A CLEAN CLIMATE RESPONSE — item 1 fixes that, and the code is written
>
> **The two legs have different LENGTHS (20 vs 81 years).** So the raw pair is the climate response **plus 61
> extra years of free-running drift**, and `NP` is the direct evidence: it kills nobody yet posts the largest
> slope of all. **No number above is a climate sensitivity.**
>
> 1. **RUN THE FROZEN-CLIMATE CONTROL. Written, tested, one command.**
>    `BOUNDARY=frozen SCEN=ssp370 bash scripts/run_rung2_response_matrix.sh` (240 jobs, ~15 min) reruns the
>    ssp370 leg with the climate held at present day — same restart, same seeds, same leg length, only the
>    climate channel frozen. Then **`transient − frozen` is the climate response with drift differenced out**
>    and `frozen − historic` is the drift. `build_rung2_boundary_series.py --freeze` builds it;
>    `frozen_series()` documents why. **This is the number the owner actually asked for.**
> 2. **Score with `scripts/diagnose_rung2_response.py`** (per-cell response, through-origin slope, Cochran's
>    Q + I²; `--stat wooddens|age_mean` for the other two). It now runs in **~40 s of CPU** — it was 40+ min
>    until the reader was changed to reject non-terminal-year lines with a substring test before splitting
>    51 fields. Wall time is I/O-bound on ~40 GB, and it buffers, so a 0-byte log is normal, not a hang.
>    ⚠ **Never pool the per-cell ratios without Q** — heterogeneous cells cancel.
>
> ### C. TWO INTERFACE LIMITS DISCOVERED — both are in the C hook (line M's `rung2_apply.c`), not in S's code
>
> * **`ERROR043: rung2 apply: duplicate roster key (pft P, tree N)` killed 82 of 510 runs.** The guard is
>   `rung2_apply_note` → `find_verdict`, gated on `rung2_defer_mortality()` = **either** env var
>   (`rung2_apply.c:118`), so **it fires in the pure OBSERVATION path too** — several `ARM=REC` baselines died
>   of it. It is **cell-specific, not leg-length-specific** (it hits 20-year historic runs as well): cells
>   **23318 and 33335 lose their baseline in both scenarios** and are unusable, 46336 loses its ssp370
>   baseline. ADR 0176 never saw it because it ran the one cell (42490) that does not collide.
>   `fread_tree.c:64-66` DOES restore `index` and advance the per-PFT counter past it, so the naive
>   "uninitialised memory" and "counter restarts at 0" explanations are both **ruled out** — the mechanism is
>   still open. **Raise with M: the key `(pft_id, treeidx)` is not unique in all cells.**
> * **Cell 22732's `S0h`/`S1` ssp370 arms HANG at the rendezvous, reproducibly, at low concurrency as well as
>   high.** The harness serves ~755 of 2025 patch-years, logs one malformed request (`year -1`, survived only
>   because the boundary lookup clamps), then idles out while the C waits on its 600 s apply timeout. Excluded.
> * **Nothing contaminated survived**: the scorer gates every dump on the run's OWN
>   `lpjml successfully terminated` line AND on the expected terminal year (2019 / 2100), and prints every
>   exclusion with its reason. A hung or crashed run is dropped, never scored at an early year.
>
> ### D. FLAG STATE — unchanged this session
>
> | flag | state | what blocks it |
> |---|---|---|
> | `wscal_leafon` | **ON** | — |
> | `roster_n_prev` | off | ADR 0175 §3's falsifier — item 1 (the frozen control) is what finally tests it |
> | `trait_mortality` | off | ADR 0176 §4's certain-set criterion (≥12 cells, recall AND precision ≥ 0.8 of the ported hazard's certain set vs FIT's own on the SAME rosters). **Needs no new run** — the dumps are on disk. ADR 0049's offline criterion is retired. |
> | `recruit_establishment` | off | off for a GOOD measured reason (ADR 0172): a +2–8 % standing wood-density LEVEL offset at 5 cells, 2–10× the whole warming signal. Do NOT flip it to satisfy the steer. |
> | `per_pft_params` (M's) | off | M's call |
>
> ### E. OPERATIONAL GOTCHAS THIS SESSION PAID FOR — all captured in the `lpjmlfit-cbinary` skill
>
> * **`priority` caps a USER at 10 concurrent jobs** (`sacctmgr show qos`, `MaxJobsPU`), which serialises a
>   500-job campaign to ~9 finished runs a minute and starves the other three lines. `short` on `standard` has
>   NO per-user job cap and the hardware is identical. The runner now defaults to `standard`/`short`.
> * ⚠ **NEVER EDIT A BASH SCRIPT WHILE IT IS RUNNING.** bash reads a script incrementally from a byte offset,
>   so rewriting it under a live loop makes it resume mid-token — it died with
>   `syntax error near unexpected token '('` two thirds through the first 510-job campaign. Edit a copy, or
>   write the new file atomically (temp + `mv`), or wait.
> * **A copied script that derives `REPO` from its own path breaks** — `$(dirname $0)/..` resolved to
>   `/p/tmp/jamirp` and every submission failed instantly. Run it from the repo.
> * ⚠ **`pkill -f <pattern>` also kills your own waiter loops** whose command text contains the pattern.
>   Three background waits were killed this way; use a job id or a narrower pattern.
> * **Never put a `#` comment inside a generated LPJmL config heredoc** — LPJmL pipes its config through
>   `cpp`, which reads `#` as a preprocessor directive and errors on every line.
>
