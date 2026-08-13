---
name: rung2-dump-analysis
description: Read and score the rung-2 roster dumps — the per-tree state LPJmL-FIT writes at the demography rendezvous when the emulator substitutes its mortality (line S, ADR 0175). Use whenever a question about the rung-2 arms can be answered from state already on disk instead of a new LPJmL run: an arm's own stand features (hmean/hmax/agb/lai/fpc/age_mean), its per-stem hazards or certain-kill set, its trait/age distributions, a historic-vs-ssp370 leg comparison, or FIT's own values as the like-for-like reference. Names the dump layout `/p/tmp/jamirp/S_rung2/S_r2s_<scen>_c<cell>_<arm>_roster_s<seed>_dump/roster_rank0000.txt`, the arms REC/NP/S0/S0h/S1, the four phases pre/grow/mort/post and why `grow` is almost always the right one, the `#H`-header-to-field OFFSET that silently mis-reads two same-typed columns, the coverage gate that 92 of 510 legs fail, and the existing scorers scripts/diagnose_rung2_stand_warming.py, scripts/diagnose_rung2_ported_certain_set.jl, scripts/diagnose_rung2_response.py, scripts/diagnose_rung2_armc.py. ALSO the rule that in a rung-2 arm the C GROWS THE STAND, so any stand-derived statistic is inherited by every arm including the do-nothing null and cannot rank arms. ALSO — CHECK `<apply>/s_arm_log.txt` FIRST: beside every arm's dump the harness logged its own count `target`, `rho`, `n_kill`, the four flux drivers and BOTH stand feature bases per patch-year in ~170 kB, so most stand questions need no dump scan at all (only REC lacks one; supply it with scripts/diagnose_rung2_map_on_rec_stand.jl). ALSO the `--n-prev` mode check that decides whether a response statistic exists: all 767 dumps are `roster`, where the model is handed the LIVE stem count and returns one within ±5 % of it in ~85 % of patch-years, so `target` and the stand's own count are the SAME quantity, any ASK-vs-GOT comparison is degenerate, and a persistence null passes a sign-agreement basis check at 12/12 cells by construction (ADR 0184) — test it with median |target/n_emit − 1| > 0.10, never with |rho − 1|, which is near 1 in both modes. ALSO the `predict` matrix now on disk (264 jobs, 258 done, tags `_predict_s<seed>`, ADR 0185) and the three rules it paid for: the mode knob must reach the OFFLINE REC replay too or the reference sits on a tethered axis while the arms run free; gate an added recursion on the first year it cannot change (600/600 rows bit-identical) rather than on an aggregate; and run the python scorers with the conda py311 interpreter, because /usr/bin/python3 dies on zip(strict=True) two thirds down the output and a partial run looks complete. ALSO the FIT-side TURNOVER reference and the kill-BUDGET side of the rate question (ADR 0188, scripts/diagnose_rung2_kill_budget.py): FIT kills 5.65-5.96 %/yr of its roster and replaces 4.62-6.46 %/yr by recruitment, so it is near-stationary in count while turning over ~6 %/yr, while the operator's count-implied budget is only 0.78-1.02 %/yr — the budget is the NET change and the flux is the GROSS, and FIT's non-negotiable deaths alone overdraw it 4-5x. Includes the recruit count identity R = n_post - n_grow (the killed stems are STILL in the post roster under ADR 0123's deferred kills, so the naive n_post-(n_grow-K) inflates recruitment by exactly K and implies a roster that explodes over 81 years), why a gate must not be stricter than the identity it gates (a dead@post == dead@mort clause reported a 13.2 % violation rate that was just fire), and why the roster-vs-emitted population ratio of 2.08-2.92 does NOT under-spend the kill quota. ALSO how to test a PROPOSED change to the kill budget before writing the arm (ADR 0189, scripts/diagnose_rung2_gross_budget_lag.py): last year's recruit count is sitting in the roster as `age == 1` (exact at 29 700 of 29 700 patch-years, since age at grow is post-increment and establishment sets age 0), so a lagged recruit term needs no dump-format change, no index tracking and no integration point with line M's rung2_apply.c; a one-year lag's count departure telescopes and stays bounded; but a budget rectified per patch-year is CONVEX, so an unbiased-but-noisy budget OVER-kills (+17 % on FIT's stand, +66 % on the arm's own, roster to 0.62x/0.11x over the ssp370 leg) and spending from a running account instead fixes it. Carries the two anchoring rules that fell out: derive a convex statistic's anchor by removing the noise (a perfect-input arm whose answer is an exact identity), never by pushing means through the identity; and model the rho>=1 gate, because a counterfactual panel containing the status quo as one arm can be validated against what the status quo is already known to do.
---

# rung2-dump-analysis — answer a rung-2 question from the dumps instead of a new run

The rung-2 harness leaves **full per-tree state on disk for every arm × cell × scenario × seed**. Two
sessions in a row have found a decisive answer in it with a parser and no model run (ADR 0182, ADR 0183).
**Before scheduling any LPJmL run for a rung-2 question, check whether the dumps already carry it.**

## What is on disk

```
/p/tmp/jamirp/S_rung2/S_r2s_<scenario>_c<cell>_<arm>_roster_s<seed>_dump/roster_rank0000.txt
        scenario : historic (2000-2019) | ssp370 (2020-2100) | ssp370frz
        arm      : REC | NP | S0 | S0h | S1          seed : 1-5 (S0/S0h/S1), 1 (NP/REC)
```
~71 GB total, ~38 GB for the non-`frz` arms. One cell per dump, 25 patches, plain text.

Three record types, each with its own `#H` header line: **`P`** = per patch-year (incl. `rootzone_w`, the
`soilmoist` driver — v6 hook only), **`T`** = per TREE (52 columns: full pools, traits, all five `mort_*`,
`bm_delta`, `leafarea_real`, `bm_inc_counter`, `isdead`), **`G`** = per grass PFT. `T` is trees only
(`istree(pft)` in the writer), so no grass filter is needed.

**The arms:** `REC` = pure observation, i.e. **LPJmL-FIT's own roster** and the like-for-like reference for
anything; `NP` = persistence null (ρ = 1, learns nothing); `S0` = shipped uniform thinning; `S0h` = S0 +
honouring certain kills (the decomposition control); `S1` = + the trait hazard's ordering. `ssp370frz`
freezes only the 4 boundary columns fed to the emulator — it is **not** a frozen-climate control for the
stand, because the C still runs transient forcing.

## ⚠ CHECK `<apply>/s_arm_log.txt` BEFORE YOU SCAN A SINGLE DUMP

Beside every emulator arm's `_dump` there is an `_apply` directory, and in it the harness's own runtime log:

```
/p/tmp/jamirp/S_rung2/S_r2s_<scen>_c<cell>_<arm>_roster_s<seed>_apply/s_arm_log.txt
#H L year patch n_tree n_emit n_prev target rho theta shortfall n_kill n_recruit
       bm_inc growth_eff water_stress soilmoist  hmean_rt hmax_rt agb_rt lai_rt fpc_rt age_rt
       hmean_c hmax_c agb_c lai_c fpc_c age_c
```

One line per patch-year, ~170 kB per leg instead of 11–47 MB, and it carries **the map's own prediction
(`target`), the thinning ratio it implied (`rho`), the kills it made, all four flux drivers and BOTH stand
feature bases** (`_rt` = the RUNTIME row the DRF was actually fed; `_c` = the C's `ind`-aggregate training
basis — the gap between them is a real train/inference shift, ADR 0060). Two sessions read 38 GB of dumps
for stand features this file already had. **Only `REC` has no log** (pure observation ⇒ no harness starts);
supply it offline with `scripts/diagnose_rung2_map_on_rec_stand.jl`.

⚠ **AND CHECK WHICH `--n-prev` MODE THE RUNS USED — it decides whether your statistic exists at all.**
All 767 dumps written before 2026-08-13 are `roster`, where `n_prev` is the LIVE stand count; measured, `target` then lies within
±5 % of it in 84–87 % of patch-years and `target/n_emit` = 1.00 ± 2.3 % (ADR 0184). So in `roster` mode
**the map's target and the stand's own count are the same quantity**, any comparison between them is
degenerate, and a persistence null (`target = n_prev`) reproduces FIT's count direction at 12/12 cells *by
construction* — it will pass a sign-agreement basis check that looks like skill. `predict` mode (the shipped
coupled path, `n_prev[patch] = target`) decouples them to ±24 %. **Do not use |ρ−1| to test for this**: ρ is
a year-on-year ratio of two smooth tree-ensemble outputs and sits near 1 in *both* modes. Use
median |`target`/`n_emit` − 1|, and require > 0.10 before reading any response statistic.

**Both scorers now take `NPREV` (default `roster`) and there is a `predict` matrix on disk** — 264 jobs,
258 completed, tags `S_r2s_<scen>_c<cell>_<arm>_predict_s<seed>` (ADR 0185). Measured separability on the
ssp370 leg: `REC` 0.132 · `NP` 0.347 · `S0` 0.244 · `S0h`/`S1` 0.18, against 0.018–0.031 for every `roster`
arm and leg. Three things to carry over:

* ⚠ **THE MODE KNOB MUST REACH EVERY SCRIPT IN THE CHAIN, INCLUDING THE REFERENCE ARM'S.** `REC` has no
  runtime log, so its `target` column is replayed offline by `diagnose_rung2_map_on_rec_stand.jl`. Leaving
  that replay in `roster` while the arms are in `predict` puts **the reference on a tethered axis and the
  arms on a free one** — invisible in every output, and it would have inflated `REC`'s score back toward
  the null's. Set `NPREV` on both, and check each script names its mode in its own header line.
* **Gate an added recursion on the year it CANNOT change, not on an aggregate.** In `predict` mode a
  patch's first year seeds `n_prev` from `n_emit`, so it must reproduce the `roster` replay bit-for-bit
  while later years must not: measured **600/600 first-year rows identical, 78.3 % of 29 700 later rows
  differing**. One aggregate agreement number cannot tell "wired in" from "the seed moved too".
* ⚠ **A gate met on one leg and missed on another is a DERIVATION problem.** The `predict` historic leg
  reaches only 0.079–0.099. Keying on ssp370 is defensible because the blessed statistic is a *difference
  of leg means*, so a tethered BASELINE leg deletes the term `ASK_hist − GOT_hist` from the ASK-vs-GOT
  contrast rather than collapsing it (degeneracy needs BOTH legs tethered) — but that reading was chosen
  after seeing the numbers, so the scorer prints the strict per-leg alternative (NO VERDICT) every run.
  Do the algebra of what your statistic needs from each leg *before* picking.

⚠ **RUN THE PYTHON SCORERS WITH `/home/jamirp/.conda/envs/py311_new/bin/python`, NOT `/usr/bin/python3`.**
The system python is too old for `zip(..., strict=True)` and dies `TypeError: zip() takes no keyword
arguments` **two thirds of the way down the output** — after the separability gate and the per-cell table
have already printed convincingly. A partial run that dies below the fold looks like a complete one.

## The four phases, and which one you want

`patches/lpjmlfit_rung2_hook_v5.patch` writes at four points in `annual_natural`:

| phase | state | use it for |
|---|---|---|
| `pre` | before turnover/allocation/mortality | almost never — `mort_*`/`bm_delta`/`leafarea_real` are **uninitialised garbage** here and at a recruit's establishment year |
| **`grow`** | after this year's turnover/allocation/**hazard**, before anyone is removed — the rendezvous | **the default choice.** It is the exact analogue of the runtime feature point (`slow.jl` builds `flux_feature_vector` from the GROWN pools, before `reconcile_demography!` removes anybody), AND it carries this year's hazard: verified that for a stem present at both, all five `mort_*` are bit-identical at `grow` and at `mort` |
| `mort` | after the demographic hazards, before fire | when you need the post-hazard roster specifically. Note it is missing the stems this year's hazard killed — which is why a certain-set comparison uses `grow` |
| `post` | after mortality AND establishment | recruits |

## The traps

1. **⚠ THE HEADER-TO-FIELD OFFSET.** The header is `#H T phase lon lat …` while a record is
   `T grow <lon> …`, so **name *n* lives at field *n+1*** (field 0 is the `T` tag). Getting it wrong fails
   loudly on a string column (`int('51.25')`) and **silently between two columns of the same type**. Parse
   the `#H` line for positions — never hardcode offsets; the writer's column set has grown across hook
   versions (v3 → v5 → v6).
2. **⚠ THE COVERAGE GATE IS NOT OPTIONAL — 92 of 510 legs are incomplete.** Two known interface faults
   (`ERROR043 duplicate roster key` killed 82 runs; cell 22732 hangs) truncate dumps *mid-leg*, and a
   truncated dump looks exactly like a short one. Require every year of the leg present with all 25 patches,
   **exclude and NAME the failures**, and expect ~12 scoreable cells, not 15. A statistic that needs only
   per-stem rows (a hazard comparison) can still use a truncated dump — say which kind yours is.
3. **⚠ `ERROR043` IS TWO DIFFERENT FAULTS — READ THE MESSAGE, NOT THE CODE.**
   * `rung2 apply: duplicate roster key (pft P, tree N)` — the C-side interface fault (line M's
     `rung2_apply.c:118`, gated on *either* env var so it fires in the pure OBSERVATION path too). Killed 82
     of 510 `roster` runs; cells 23318/33335 lose both baselines, 46336 its ssp370 one. Mechanism OPEN.
   * `rung2 apply: no answer for year <Y> patch <P> after 600 s` — a **harness-side idle timeout**, not an
     interface fault. The harness exits *cleanly* on its `--max-idle` (default 300 s) while the C is still
     running — its log ends `harness: served <N> patch-years` with N short of the leg — and the C then waits
     600 s and dies. Cost 6 of 264 `predict` runs, all late ssp370 (2071–2094). Fix by raising `--max-idle`
     in `scripts/run_rung2_s_arm.sh` above the C's own 600 s wait.
4. **⚠ THE RUN LOG GLOB IS `lpjml.*.out`, NOT `lpjml_*.out`.** The wrong one matches nothing, so a
   completion-line count over a healthy matrix reports **0** and looks like total failure. Same family as
   CLAUDE.md §3's "a 0-byte log is a provenance FATAL, never a physics verdict" — confirm the glob matches
   *something* before reading a zero as a result.
5. **⚠ IN A RUNG-2 ARM THE C GROWS THE STAND.** The emulator only decides who dies. So any stand-derived
   statistic is **inherited by every arm, including `NP`** — ADR 0182 measured the do-nothing null tracking
   FIT's stand-shift direction at 0.910, as well as `S1`. Such a statistic can clear or convict a
   hypothesis; it cannot rank arms. Score `NP` on the same statistic and print its number in the same table.
   For the same reason a rung-2 result can never indict the Julia **fast core**, which never runs here.
5b. **⚠ THE COUNT IS ON TARGET WHILE THE STAND IS WRONG — A COUNT STATISTIC CANNOT SEE THIS FAILURE
   (ADR 0186).** On the ssp370 leg at the FIT-gain cells the trait arms hold **−2.9 % / −13.6 %** the stems
   FIT holds and **+90.6 % / +89.0 %** the biomass, with per-stem mass +63…+246 %, `hmean` +12…+38 % and
   `age_mean` +53…+160 %; `S1`'s count stays within a few per cent of FIT's for **all 81 years** while its
   biomass climbs monotonically. So the emulator kills the right NUMBER of trees and the WRONG trees. Two
   standing consequences: **never read "the count matches" as "the demography matches"**, and **a
   count-side instrument (the level anchor, a retrained count target) has no lever on this** — check the
   count departure BEFORE proposing one, it costs seconds
   (`scripts/diagnose_rung2_anchor_preflight.py`).

5c. **⚠ A CRITERION IS WRITTEN AGAINST A DEFINITION — IMPORT THAT DEFINITION, DO NOT RE-IMPLEMENT IT
   (ADR 0186).** ADR 0185 §5's departure table is a patch-mean at the SINGLE terminal year, seeds averaged,
   then the MEDIAN over cells, behind the scorer's coverage gate. A re-implementation using a 20-yr window,
   a mean over cells and a **mean of per-patch ratios** put `S1`'s ssp370 count departure at **+37 %**
   where the real basis gives **−2.9 %** — a sign flip, on the same data, on the quantity the decision
   turned on. Per-patch counts are 4–11 stems, so patches where FIT holds one or two dominate an unweighted
   mean of ratios. **Reproducing the published table is the gate: do it before adding a column to it.**

5d. **⚠ `isdead` AT THE `mort` PHASE IS *NOT* THE ARM'S KILL SET — IT IS THE ARM'S NOMINATION UNION THE
   C's OWN NON-NEGOTIABLE KILLS, AND THAT CONTAMINATION IS 8 % TO 100 % ARM-DEPENDENT (ADR 0187).** The C
   always applies its own hard kills whatever the arm answers (negative pools / `isneg_tree`, bioclimatic
   `survive()`, `cut_year`). Measured share of forced over total kills, 12 cells' ssp370 legs:
   **NP 100.0 % · S0 45.8 % · S0h 7.9 % · S1 8.7 %.** Those stems are dying and carry almost no mass, so
   any mass- or size-weighted statistic on the raw `isdead` set is dragged down by a different amount in
   every arm — **it cannot rank arms.** Restrict to the stems the operator had discretion over,
   **`mort_prob < 1`**, applied identically to every arm INCLUDING `REC`. The check that the restriction
   works is free: **`NP` nominates nothing, so its discretionary kill count must be ~0** (measured 14 of
   12 393). ⚠ Also: the kill set IS recoverable without the `rsp_r*_y*_p*.txt` files (**they are gone from
   the `_apply` dirs**) — under ADR 0123 the binary defers its kills, so the `mort` roster carries every
   killed stem flagged, on a roster identical in length to `grow`. And gate it: the flagged-dead count per
   patch-year must equal `n_kill_applied + n_forced_dead` in `<apply>/audit_r0000.txt` (234 of 234
   audit-bearing legs pass; `REC` has no audit log — say so rather than hiding the asymmetry).

5e. **⚠ A RATIO-OF-FRACTIONS STATISTIC POOLED OVER A LEG IS NOT ITS OWN NULL — STRATIFY BY PATCH-YEAR
   (ADR 0187).** The operator draws **once per patch-year**, so that is the only level at which a
   uniform-draw null is exact. Pooled over a leg, `kill_frac_m / kill_frac_n` equals
   `<(1−ρ)>_mass-weighted / <(1−ρ)>_count-weighted` over patch-years, which is 1 **only** if the thinning
   ratio is uncorrelated with per-stem mass across patch-years — and it is not, because the patches
   thinned hardest are the dense old heavy ones. Measured, the between-stratum term moved `S1` from 0.93
   (stratified) to 1.08 (pooled) and put the uniform arm at 1.19 against a derived 1.00. Use the
   kill-weighted mean of the per-patch-year ratio, and print the pooled value beside it.

5f. **⚠ DERIVE THE BLESSED STATISTIC'S SAMPLING SE BEFORE CHOOSING ITS TOLERANCE (ADR 0187).** A
   derived-a-priori self-test is the best gate available — the uniform-thinning arm `S0` MUST return mass
   selectivity 1.00, and it caught BOTH basis errors above. But its tolerance was pre-registered without
   deriving the SE, which is ≈ **0.09 at one cell** (most strata hold ONE kill and per-stem mass inside a
   patch is strongly right-skewed) against a 0.15 tolerance ⇒ ~1.7 σ, too tight to be a clean gate, and a
   single-cell 1.19 read as a defect when it was ~2 σ of noise. Pooled over 15 legs the SE is 0.045 and
   the same test lands at 0.14 σ. **Print the SE and the σ-departure beside every pass/fail** — and do
   not move the tolerance after the fact; report both.

5g. **⚠ THE KILLED STEMS ARE STILL IN THE `post` ROSTER — SO THE RECRUIT COUNT IS `n_post − n_grow`, NOT
   `n_post − (n_grow − K)` (ADR 0188).** ADR 0123 makes the binary DEFER its demographic kills, so a stem
   flagged `isdead` at `mort` is still a record at `post`: measured, **no stem is removed between the two
   phases at 30 300 of 30 300 patch-years**. The roster only GAINS, and recruits therefore need no index
   tracking at all — which also makes the count immune to the `ERROR043` duplicate-key fault. The naive
   form inflates recruitment by exactly `K_all`; it returned FIT recruitment of 10.5–12.6 %/yr and a
   **sustained +4.6 to +6.5 %/yr roster growth over an 81-year leg**, which would explode the roster by
   orders of magnitude, while **every arm-to-arm ratio still looked perfectly sane**. ⇒ **SANITY-CHECK A
   LEVEL AGAINST WHAT THE SYSTEM MUST DO OVER ITS OWN HORIZON** — that is the tell a ratio cannot give you
   (the mirror of ADR 0184's "report the level beside every shift"). FIT's own reference values, `predict`,
   12 cells: gross kills **5.65 / 5.96 %/yr** (certain 3.52/3.98, discretionary 1.88/2.05), recruits
   **4.62 / 6.46 %/yr**, net **−0.54 / +0.25 %/yr** — near-stationary in count while turning over ~6 %/yr.

5h. **⚠ A GATE STRICTER THAN ITS OWN IDENTITY MANUFACTURES DOUBT ABOUT A SOUND NUMBER (ADR 0188).** The
   identity in 5g needs only *no stem removed*. A first version also required `dead@post == dead@mort` and
   reported a **13.2 % violation rate that was not a violation**: **FIRE** flags further stems dead between
   the phases (ADR 0121) — one-directional (`dead@post ≥ dead@mort` at 8100 of 8100, never below) and
   **+14.1 %** on top of the demographic kills. Fire is not the demography interface's to own, so read
   `K_all` at `mort` and report the fire excess separately. **Write down the identity, gate exactly it, and
   report anything else as information** — an over-strict gate costs a session re-deriving whether a correct
   result is trustworthy.

5i. **⚠ `n_tree` AND `n_emit` ARE BOTH IN `s_arm_log.txt`, SO THE ROSTER-vs-EMITTED QUESTION NEEDS NO DUMP
   SCAN (ADR 0188).** Third time the arm log retired a planned scan (with 0184 and 0186). The ratio is
   **2.08–2.92** — above line M's 1.9× at Hainich — but it does NOT under-spend the kill quota: ρ is applied
   as a per-tree survival FRACTION against the whole-roster `n_now = sum(nind)` (harness :521-527), and a
   fraction is scale-free. The derivable check: the uniform arm's `E[n_kill] = (1−ρ)·n_tree` **exactly**
   (measured realized/implied **1.004 ± 0.009**). And two gates on the operator that are one grep each: the
   ρ clamp is **not** binding (0.00–0.25 % at the low bound) while `if ρ < 1.0` leaves **42–46 %** of
   patch-years with an EMPTY kill list, plus **27.9 %** of `S1`'s years at `_hazard_tilt`'s reported
   `θ = 0` give-up. ⚠ `S0h` reaches that same starved state through `c = clamp(ρ*n_now/n_free, 0, 1)` → 1.0
   but its `shortfall` column tests a DIFFERENT condition and reports 0 % — **its override is real and
   unlogged**; never read that 0 % as "no override".

5j. **⚠ LAST YEAR'S RECRUIT COUNT IS SITTING IN THE ROSTER AS `age == 1` — EXACTLY, AT 29 700 OF 29 700
   PATCH-YEARS (ADR 0189).** `age` at `grow` is post-increment (trap 6) and establishment sets age 0, so
   `#{age == 1 at grow, year y}` **is** `R(y−1)` = `n_post(y−1) − n_grow(y−1)`, per patch. Two consequences.
   (a) Any instrument needing lagged recruitment needs **no** dump-format change, **no** index tracking
   (hence no `ERROR043` exposure) and **no** integration point with line M's `rung2_apply.c` — the harness
   already holds the whole roster. (b) It is a free consistency check on any recruit statistic you compute
   the other way. FIT's own recruitment is **4.619 → 6.456 %/yr historic → ssp370 (+39.8 %)**, and about
   two thirds of a pooled lag-1 correlation in it is CROSS-SECTIONAL: 0.618/0.636 pooled vs **0.230/0.343**
   demeaned by patch. ⚠ The tell that a pooled autocorrelation is cross-sectional: **adding UNITS raises it**
   (2 cells 0.30 → 12 cells 0.62). Print both, and never quote the pooled one as temporal skill.

5k. **⚠ WHEN A STATISTIC IS CONVEX, DERIVE ITS ANCHOR BY REMOVING THE NOISE — NOT BY PUSHING MEANS THROUGH
   THE IDENTITY (ADR 0189).** A rung-2 budget statistic contains `max(0, budget − n_cert)` and
   `max(budget, n_cert)`. An anchor derived as `mean(budget) − mean(n_cert)` therefore CANNOT be that
   statistic's expected value: the leg mean exceeds it by a Jensen gap that grows with the count model's
   per-patch-year error, so a correctly-computed panel "fails" a correctly-motivated band (measured 4.509
   against a derived [1.5, 2.6]) — and the budget mean it came from was right to 0.6 %. The fix that works is
   an arm with a **perfect input** (`budget = K_all` per patch-year), whose answer is then an exact identity
   (`max(0, K_all − n_cert) ≡ K_disc`, measured |diff| **0.0000**). Under ADR 0187's clause do **not** move
   the band — keep it in the code, print it, and add the identity arm. **And the same convexity is a physical
   finding, not just a scoring nuisance:** it means an unbiased-but-noisy kill budget OVER-kills (total
   mortality +17 % on FIT's stand, +66 % on the arm's own, roster to 0.62×/0.11× over the ssp370 leg), which
   is why the accounting formulation exists.

5l. **⚠ MODEL THE ρ≥1 GATE, NOT JUST THE BUDGET — AND USE THE STATUS QUO AS A FREE VALIDATION (ADR 0189).**
   On a gated patch-year the kill list is EMPTY, and because the list IS the whole answer the arm spares the
   **certain** deaths too. A counterfactual panel that assumed certain deaths are always honoured put the
   CURRENT operator's implied roster at 0.45× over the leg — contradicting ADR 0186's measured on-target
   count — and modelling the gate moved that same row to +0.594 %/yr / 1.62×, agreeing with the published
   number. **Any panel that contains the status quo as one of its arms can be checked against what the status
   quo is already known to do; do that before reading the other arms.** (The C's own hard kills on a gated
   year are still unmodelled — state such a residual rather than hiding it.)

6. **`age` at `grow` is POST-increment** (the C's hazard used `age − 1`; ADR 0031's off-by-one). Subtract 1
   when feeding a ported equation; a constant offset cancels in a difference-of-means-over-sd statistic but
   not in a level. **And it is what makes trap 5j's recruit identity exact.**
7. **Empty patches emit no `T` record** but are a real all-zero stand row at runtime — enumerate patch-years
   from the `P grow` records, not from the trees.
8. `leaf_c`/`sapwood_c`/`heartwood_c` are `tree->ind.*.carbon`, i.e. **per individual** — multiply by `nind`
   exactly where the runtime does.

## Existing scorers — extend one before writing a new one

| script | what it does |
|---|---|
| `scripts/diagnose_rung2_stand_warming.py` | the six stand features per (year, patch) from `grow`, leg shifts in per-cell sd units vs `REC`, liveness panel, drift control. **Caches one `.npz` per dump under `/p/tmp/jamirp/S_rung2_standwarm/cache/`, keyed by size+mtime — reuse that cache rather than re-reading 38 GB.** |
| `scripts/diagnose_rung2_ported_certain_set.jl` | per-stem ported hazard vs FIT's own `mort_prob`, certain-set recall/precision, and a zeroed-stress arm that evaluates the hazard as the COUPLED loop runs it |
| `scripts/diagnose_rung2_response.py` | the per-cell count response by arm/scenario/seed |
| `scripts/diagnose_rung2_map_on_rec_stand.jl` | the count model run over **FIT's OWN** roster, i.e. the `target` column `REC` has no log for. `include`s the harness for `Tree`/`pools_of`/`flux_drivers` so the row reaches the SHIPPED `flux_feature_vector` + `DRF.predict` (ADR 0023); ~15 s for all 30 REC dumps. **Its gate is the pattern to copy: at year 2000 no arm has killed anything yet, so its row must equal the live `s_arm_log.txt` to the last digit — verified bit-identical.** |
| `scripts/diagnose_rung2_map_target_response.py` | ASK (the count the map asked for) vs GOT (the count the stand reached) vs FIT, per cell and arm, off the arm logs; the ρ/tether panel, the stand-LEVEL departure table, the drift and frozen-boundary controls (ADR 0184). Takes `NPREV`; prints the pre-registered SEPARABILITY GATE before any response statistic and suppresses the verdict for a tethered arm (ADR 0185). |
| `scripts/diagnose_rung2_anchor_preflight.py` | **six panels, ~7 s, no model run** — what a proposed count-side change would do, off the arm logs alone (ADR 0186). Panel 1 the `roster`-mode inertness proof, 2 the `target/n_emit` level gap, 3 per-year push + clamp incidence + time constant, **4 the count-vs-mass departure decomposition, 5 its per-year trajectory, 6 the per-stem split** — 4–6 **import** `diagnose_rung2_map_target_response.py`'s `Leg`/readers/coverage gate, so they are on the criterion's own basis by construction. Copy this shape before proposing any rung-2 experiment. |
| `scripts/diagnose_rung2_kill_selectivity.py` | **WHICH trees each arm kills, vs FIT's own kills** (ADR 0187) — mass selectivity `kill_frac_m/kill_frac_n` on the discretionary population stratified by patch-year, the size-conditional rate profile P(die \| height quintile of the REFERENCE arm's stand), standardized selection differentials, the ADR-0186 §8 reachability clause, and a verdict gated by the derived-a-priori `S0` self-test. ~9 min for 12 cells × 2 legs (24 GB). **Copy its self-test shape**: a uniform arm with a derivable answer is the cheapest real gate on a new scorer, and it caught two independent basis errors here. |
| `scripts/diagnose_rung2_kill_budget.py` | **WHY the operator's kill RATE is short** (ADR 0188) — the budget side of ADR 0187's rate finding. Five panels: the derived-a-priori `S0` self-test that refutes the emitted-vs-roster population hypothesis, the ρ-clamp incidence, the `ρ ≥ 1` empty-kill-list gate plus `θ = 0` give-ups, the budget-vs-nominations decomposition, and **FIT's own gross kills / certain kills / discretionary kills / recruits / net** by the 5g count identity. Panels A–D are the arm logs alone (seconds, `SKIP_REC=1`); panel E is a 1.9 GB `REC` scan (~2 min). Imports ADR 0185 §5's coverage gate. **Use it for any FIT-side turnover reference** — gross mortality and recruitment per year are here.
| `scripts/diagnose_rung2_gross_budget_lag.py` | **WOULD A PROPOSED BUDGET CHANGE ACTUALLY WORK, before the arm is written** (ADR 0189) — the feasibility half of ADR 0188's next action. Five panels off the `REC` dumps joined to `map_on_rec_stand_predict.csv` (so ρ and the roster are the same patch-years, gated on `n_tree`), plus the same statistic on `S1`'s own stand from its own dumps + arm log: the exact `age == 1` recruit-observability gate (trap 5j), recruitment's own statistics with the pooled AND within-patch lag-1 correlation, the telescoping count-departure check, and **the capacity table** — discretionary capacity, empty-budget share, implied total mortality, implied net and the compounded roster factor over the leg, for each of `none`/`lag1`/`mean5`/`expand`/`oracle`/`perfect` and the `_sm5`/`_acct` design probes. **Reuse it for ANY proposed change to what the operator is asked to kill**: it costs ~4 min and no model run, it carries the two derivable anchors (traps 5k/5l), and its `ROSTER-HORIZON` columns are the check that catches trading a biomass excess for a stand collapse. Extends `scan_rec_dump` additively (`n_cert`, `n_age1` at indices 6–7). |
| `scripts/diagnose_rung2_armc.py` | age–wooddens gradients and selection differentials (shared with line M's arm C; **each arm family has its own recorded baseline and they are NOT interchangeable**) |
| `scripts/rung2_s_demography_harness.jl` | **the row assembly.** It reaches `flux_feature_vector` and `DRF.predict` as private names off the package rather than copying them — do the same, or the copy becomes the thing being measured (ADR 0023). |

**Reach ported physics as the shipped name** (`LPJmLFITEmulator.TraitMortality.mortality_hazard`,
`flux_feature_vector`) and feed it only dumped columns. That is what makes an agreement result meaningful:
ADR 0183's 5e-18 match over 1 568 744 stem-years would have proved nothing had the scorer re-derived any
input. And **check what a harness actually feeds its own test before building on it** — ADR 0176 §4's whole
blocker rested on `Tree.mort` being FIT's hazard when its own declaration comment says it is the port.

## Mechanics

Both scorers run off the login node only for a smoke test on a symlink dir of 2-4 dumps; the full scan goes
to SLURM (`scripts/sbatch_python.sh S-<tag>` / `scripts/sbatch_julia.sh S-<tag> --project=.`). **`export`
every env knob** — the wrappers forward only a fixed list of names. Python: lint with the repo's real rule
set, `ruff check --select E,F,I,UP,B --line-length 100` (CI does not lint `scripts/*.py`, so nobody else
will). Julia: the repo-wide Runic `format` gate DOES cover `scripts/**` — run the check from the
`julia-test` skill before pushing.
