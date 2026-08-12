# LINE M — multi-cell coupled S+F+E (branch `line/M`, worktree `wt-M`) — P3

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/M/JOURNAL.md` (append-only). Decisions: ADR block **0050–0069**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## 📥 INBOUND FROM LINE S, 2026-08-11 (ADR 0117) — **the reply you are waiting for: option (c), and your recruit interface is already complete**

> ADR 0120 §1 records that the S→M demography interface was raised and *"S has not yet replied"*. This is the
> reply. Full record: `docs/decisions/0117-*.md`. Nothing here asks you to change the hook.

**1. S returns option (c): a per-individual survival factor `f_i ∈ [0,1]` per tree of the `pre` roster,
keyed by your `(pft_id, treeidx)` pair — you do the Bernoulli draw.** Plus the recruit set exactly as you
proposed. Why (c) and not the cheaper (b): ADR 0046 decomposed FIT's warming trait shift as 22.2 %
composition / **51.3 % within-PFT** / 26.6 % interaction, with the within-PFT part **+112 % within-age-class**
— traits are immutable after `new_tree`, so a shift at fixed PFT and fixed age can only be differential
survival. **Who dies IS the trait response**, so a count-only interface cannot reach the trait half of
ADR 0106 in principle. (b) borrows *your* hazard ordering, which makes any trait result the C's selection
wearing the emulator's count — run it as an upper-bound control, not as the answer. (c) over (a) because
FIT's own structure is probability-then-draw (`mortality_tree_ind.c:95-146`) and because ADR 0101 needs a
**seed ensemble**: with the draw on your side a seed ensemble is a re-run of the harness, not of S.

**2. Nothing new has to be built to start.** S's existing opt-in `trait_mortality` operator (ADR 0047→0049)
already computes exactly this: `f_i = (1 − mort_i)^θ` with θ bisected so `Σ nind·f_i = ρ·Σ nind` — the count
model pins the expectation, the ported hazard sets the ordering. Two arms in one wire format: **C0** returns
`f_i = ρ` for every tree (the shipped uniform thinning — the *no-selection null*) and **C1** returns the
tilted factors. **C1 − C0 is the measurement of how much of the trait response is selection.**

**3. Your harness retires a limitation S could not fix offline — worth knowing before you scope arms.**
ADR 0049 item 4 zeroes `mort_water` and `mort_temp` in the ported hazard because the emulator has neither of
FIT's stress integrals. Your `pre` record carries `water_stress`, `temp_stress`, `bm_inc_counter` and
`bm_inc` ⇒ **inside the harness all four hazards are computable faithfully and the operator can run complete
for the first time.** That borrows the C's *state*, not its *decision*, which is rung 2's premise rather than
(b)'s problem — but a rung-2 trait result has to say which.

**4. A FREE identity gate, offered:** run one arm with **θ forced to 1** and the hazards on the C's own
accumulators — ADR 0049 item 2 records that **θ = 1 recovers FIT exactly**, so S's operator must reproduce
your per-tree `mort`. No new code; any mismatch is a port error in `src/trait_mortality.jl`, caught before a
science number is quoted.

**5. Your recruit interface is COMPLETE — `k_root` costs nothing, verified, so there is nothing to add to the
wire format.** All seven tree PFTs declare `"k_root": 0.02` as a **scalar** in the live
`par/pft_lpjmlfit.js` (the sampled-interval form is commented out at every one of the seven entries), and the
emitted column carries **exactly one distinct value over all 206 561 574 tree rows, 0 differing**. Leaving it
on the C's own draw is an **identity**, not an approximation. `emax` and `beta_2` are emitted nowhere, so
their coupling is not measurable from `ind`; if it ever matters the cheap route is adding them to the `pre`
dump. ⚠ But **consume the four axes as a SET**: they are genuinely correlated within (PFT, age bin) among
survivors (`SLA~D95max` −0.292, `SLA~minwscal` +0.251, `D95max~minwscal` −0.124, `Wooddens~minwscal` +0.102),
which is the joint the copula exists to carry.

**6. Two things to design against.** (i) **The count channel may bound the selection**: at Hainich the tilt
was θ median **8.5e-12** with θ > 0.5 in only **18 of 132** thinning years, because the learned count model's
demanded `|ρ−1|` has median 0 %/yr against the hazard's 1.688 %/yr (ADR 0049 item 5). The rung-2 count target
is the same model ⇒ **measure θ before interpreting any C1 − C0 difference**; a null there may mean the count
gave the selection no room. (ii) **ADR 0116's offline count drift does not transfer unchanged** — in rung 2
the roster returns from the C each year, so the count is read off the *true* roster instead of being
self-fed. Rung 2 is where that can be tested; don't assume it in either direction.

### ▶ AMENDMENT FROM LINE S, 2026-08-11 (ADR 0118) — **read this BEFORE running arm C: its headline claim is narrower than the block above says, and the reason is measured**

> Same integration point, one day later. **Nothing about the interface or the wire format changes** —
> option (c), the four recruit axes, and the θ=1 identity gate all stand exactly as written above. What
> changes is **what `C1 − C0` is allowed to claim**. Full record: `docs/decisions/0118-*.md`.

**1. The copula's recruit marginals are trained on FIT's SURVIVORS, so they already carry the selection
arm C adds on top.** ADR 0025 §3 chose that target and wrote its own expiry condition into the decision —
*"Trait-dependent mortality is a much larger, separate change; **if ever added, this training target must
change**."* Arm C is that change, and no decision record in the 0047→0049→0117 chain (including S's own
reply above) had cited it. **The asymmetry is the problem: C0 is unaffected** — uniform thinning is exactly
the trait-blind design the survivor marginal was matched to — so the bias lands entirely on the arm and not
on its null, i.e. straight onto the headline difference.

**2. Measured, so you can price it rather than argue about it** (197.7 M historic + 828.8 M ssp370 surviving
stems, both ground-truth members, no refit, ~7 min; `scripts/diagnose_copula_selection_confound.py`). Within
a cell-PFT group, FIT's standing marginal sits this far above its own youngest-stem marginal:

| axis | displacement | of it, the part that does NOT cancel in a warming response |
|---|---|---|
| **Wooddens** | **+12.18 %** | **0.56 of FIT's own response** |
| SLA | +0.80 % | 0.06 |
| D95max | −2.35 % | 0.31 |
| minwscal | +0.44 % | 0.12 |

Seed agreement ≲ 2 % on every entry. **Wooddens is the one that matters** — it is the axis ADR 0049's flip
criterion is written on, and the axis ADR 0046 fingerprinted as within-PFT selection. ⚠ All four are
**LOWER BOUNDS**: the `ind` writer drops stems below 5 m, so selection before that height is invisible.

**3. What this changes for your arms — two conditions, pre-registered so they cannot be reinterpreted after
the run.** A Wooddens improvement in `C1 − C0` is **no longer sufficient evidence on its own**, because a
double count pushes the same way:
* **read θ first** (already your item 6.i): the confound and the arm's power **scale together**. Near-zero θ
  ⇒ `C1 ≈ C0` and the arm measured nothing; large θ ⇒ the double count is live. Neither reading is available
  without θ printed beside the result.
* **test the per-PFT gradient SHAPE**, not just the level: a genuine selection channel must reproduce
  `test/testitems/references/S_age_wooddens_gradient.csv` including the **non-monotone** ids 0 and 3,
  whereas a double count inflates the level roughly uniformly. That is the ID-free discriminator; the slope
  alone cannot separate them.

**4. ⚠ SUPERSEDED SAME DAY BY AN OWNER STEER — THE FIX IS A PORT, NOT A RETRAIN. NOTHING IS ASKED OF YOUR
HARNESS.** *(Original text kept below so the change is visible; the owner's objection, 2026-08-11, was:
"which trees are born is — apart from the inheritance functionality — randomly drawn from uniform
distributions. why should we train on that?? what matters and what we have to learn is who survives the
environmental filtering — and for that looking at trees above 5 m should be enough". Correct on both
counts.)*

**The corrected fix.** FIT's establishment rule is **fully specified and needs no training data at all**:
a uniform draw on each PFT's own `[low, high]` interval from `par/pft_lpjmlfit.js`, plus an inheritance
channel that copies a random member of the cell's 50-yr rolling top-AGB seedbank and jitters each axis by
`new = old·(1 + 0.1·gasdev)` reflected at the interval edges, mixed in the **closed-form** ratio
`w_inherit = 4/(4 + n_elig)` (ADR 0045). Every input is either in the parameter file or computable from the
emulator's **own** roster. So S ports the rule; **no recruit-marginal retrain, no new artifact version, and
nothing is needed from your `pre`/`post` dump.** Item 4's original ask is **withdrawn** — do not carry it
into your rung-2 scoping.

**Also withdrawn: the "lower bound" caveat is not a constraint on this route.** It only ever limited
*fitting* an entry distribution from `ind`. The emulator grows its own saplings and applies the ported
hazard through the sub-5 m phase itself, so >5 m data is sufficient both to drive and to validate — which
is also the basis ADR 0106's 10 % is defined on.

**The one risk that replaces it, and it is a real one:** a ported establishment rule makes recruits a
functional of the emulator's own community (the seedbank is its own biggest trees) — i.e. a **feedback
loop**, exactly what ADR 0025 §4 excluded on principle. ADR 0112–0116 measured what this model does when it
feeds its own state back in: the error becomes **climate-dependent** and manufactures ~90 % of the true
signal with the wrong sign. That must be measured on this channel, not assumed either way — and rung 2,
where the roster returns from the C each year, is the cleanest place to measure it.

> *(original item 4, superseded — retained for the record)* Something that could be fixed cheaply, and only
> your harness can do it. The clean repair is to train the marginals on **entering** individuals instead of
> survivors — and that is impossible from the `ind` parquet, which never emits a recruit (nothing below
> 5 m). Your `pre`/`post` roster dump does see recruits at `age == 0`. So a recruit-marginal copula is a
> rung-2 by-product that costs no new model run. It would change the S→M contract (a new artifact version,
> not a patch) … S owns the retrain; you own whether the dump keeps what it needs.

**4b. ⬆ UPDATE, later the same day (2026-08-11, ADR 0119): the ported rule is BUILT, and its flip criterion
is an ACTION FOR YOUR HARNESS.** Item 4's corrected fix above is no longer a plan — `src/establishment.jl`
(`module Establishment`) plus an opt-in
`FluxDrivenSlowEmulator(...; recruit_establishment = RecruitEstablishment(...))` hook are on `main`, default
off, byte-identical when unset, and **mutually exclusive with `recruit_copula`** (the constructor errors —
both set the recruit marginal, from bases differing by ADR 0118's measured +12.18 % on `Wooddens`). Nothing
is asked of your `pre`/`post` dump; the seedbank is fed by the emulator's own roster.

**What you would run, when rung 2 has a roster.** Two recruit channels under an otherwise identical
configuration, both with the trait-mortality arm **C1** on (the double count only bites when selection is
active): **R0** = today's pinned `.rcop` copula · **R1** = the ported rule with the cell's eligible PFT set,
`set_pft_id = false`. The pass/kill conditions are pre-registered in ADR 0119 §6 — read them there rather
than re-deriving; the two that will shape your harness are:

* **check the channel mix FIRST** — `establishment_diag(s)` must show `sb_weight > 0` and an inherited
  fraction within ±0.05 of `4/(4 + n_elig)` in ≥90 % of recruiting years, else the arm measured the uniform
  background channel only and says nothing about inheritance (an operator that never fired produces a null,
  not a verdict — the ADR-0048 lesson);
* **the KILL condition** — if the recruit channel makes the error climate-dependent the way the count
  recursion did (ADR 0112–0116: level within 2 %, but ~90 % of FIT's global response manufactured with the
  wrong sign), the flip is REFUSED and that becomes the result.

**One thing S needs from you eventually, raised now rather than at the arm: a PER-PFT CANOPY TEMPLATE
REGISTRY.** The ported rule draws a recruit's **PFT identity** as well as its traits, but writing that id
into the roster is currently unsafe — `fc.tmpls` still carries the donor cohort's per-PFT physiology
(`alphaa`, `emax`, `intc`, albedos, `photo`, `tstress`), and `_commit_membership!` refuses any id absent from
`fc.pft_slot`. So identity ships behind a second flag (`set_pft_id`, default `false`) and the drawn id is
recorded in the diagnostics only. You build `fc.tmpls`; a `pft_id -> FDiff.Individual` template map from your
per-cell provisioning would let the recruit channel carry composition as well as traits. **Not urgent, not a
blocker for R0-vs-R1** — noted so it is scoped before an arm needs it.

**5. Arm D, if it comes up: it inherits all of the above unchanged**, and separately its motivating number
should not be relied on yet. ADR 0093 §5.3's "bounded Beta beats the copula 2–3× on per-cell KS" has **no
committed reproducer** in this repo, and its "two-moment fit, no fitting procedure" wording indicates the
Beta was matched to each cell's **observed** moments while the copula's number is **out-of-sample** — if so
it is an upper bound, not a realizable gain. S owns re-establishing that like-for-like before arm D runs.

## ✅ RESOLVED — the JET 0.12.0 blocker (pinned on `main` in `47c6407a`, 2026-07-28)

JET **0.12.0** removed the `target_defined_modules` configuration that `test/jet_tests.jl:6` passes, so
`JET.test_package` died with `JETConfigError` and `test (1)` (Julia 1.12) errored **repo-wide** on a fresh
resolve — `test/Project.toml` had no `JET` `[compat]` entry. Confirmed repo-wide, not line-M: identical
failure on line/M `693322fa` (job 90278705919, a docs+tests-only diff) **and** line/O `11ef8d89`
(job 90275445875); `test (lts)` stayed green because JET 0.11+ needs Julia ≥1.12 so 1.10 resolves 0.9.20.

Fixed with `JET = "0.9, 0.11"` in `test/Project.toml` `[compat]`. **Landed directly on `main`** rather than on
this branch, because that file is integrator-owned (ADR 0029) and the breakage blocked all four lines from
merging; both pinned versions were already in the shared depot, so the compute-node warm needs no new tarball.
**[TODO, not this line]** lift the pin by migrating `jet_tests.jl` to JET 0.12's replacement scoping API.

## 📌 The PINNED Component-S artifact — **`_t8`**, adopted 2026-07-30 (frozen S→M contract, ADR 0023)

**Pinned pair** (`/p/tmp/jamirp/emulator_global/`, line S's, read-only to this line):

| Artifact | sha256 | bytes | mtime |
|---|---|---|---|
| `drf_forest_global_pooled_w20_t8.drf` | `b8e59a4ab1d59f2fab5c31757947e870a960c85f22d71a2f31ca292778e5b483` | 51554735 | 2026-07-29 15:14 |
| `recruit_copula_global_pooled_w20_t8.rcop` | `016f51117c6af79fe2de5e1c25e4714584f8bf319212225b9af3ffb0ea7dc444` | 129031922 | 2026-07-29 22:49 |

Per-cell seed + boundary taken from **`slow_runtime_historic_t8/cell_meta.parquet`**
(sha256 `d208ca0797161b86130e8d1d9693a3dcc1c7408946887031e0374db96b88012e`, 53,699 cells) — provenance
recorded in `references/M_slow_init_meta.json`.

**Why `_t8` and not `_t7`/`pooled_w20`:** `_t8` re-derives the same population (ADR 0031's complete seven
tree PFTs) on the **ADR-0035 feature bases** (`soilmoist` = root-zone year-end plant-available fraction,
`lai` = the per-patch reconstruction). `_t7`'s OOS numbers stay valid as *offline* measurements, but a
COUPLED run on `_t7` inherits the retired bases — exactly what M3 must avoid. The original `pooled_w20`
pin was never trained on `semiarid_sahel` at all.

**VERIFIED INDEPENDENTLY (2026-07-30), not taken from S's handoff note:**
- `DRF.load_forest` → 1.46 s, `nfeat = 15`, 150 trees. Meta `colnames` = the 11 head features + boundary
  tail `eco_diag_gdd_5 tas_cold_month soil_depth co2` — **identical** to `slow.jl::flux_feature_vector`.
- `DRF.load_copula` → 3.0 s, `axis_names = [SLA, Wooddens, D95max, minwscal]`, and **`nfeat = 8` on every
  axis forest**. That last number is the one that actually proves ADR 0036's new diagnostic axes
  (`agb`, `Height`) are **absent** from the `.rcop` — the meta only *claims* 4 axes. `cond_cols` is
  **identical** to `live_flux_cond` = `vcat(feats[1:4], s.boundary)`.
- Coverage read out of the parquet directly: both `_t8` tables cover **5/5** biome cells
  (historic 53,699 · ssp370 58,496).
- **Bit-identity cross-check:** `M_cells.csv`'s `temperate_hainich` row (`n_init` 11.0, `age0`
  43.55555555555556, boundary `1863.695068359375 0.21838709712028503 1.5173755884170532 369.0`) is
  **exactly** the committed `drf_forest_hainich_meta.txt`'s own baked values. Same quantity, same
  upstream, independently derived ⇒ the extractor pulls the right columns in the right ORDER. Asserted
  as an equality in `biome_coupled_tests.jl` (which is why the fixture is emitted at `repr`/`%.17g` —
  `%.6f` truncated that gdd5 to 1863.695068, and these values feed DRF split thresholds).

So the per-cell boundary vector this line builds is exactly
`[eco_diag_gdd_5, tas_cold_month, soil_depth, co2]` — the columns `cell_meta.parquet` carries.

**Nothing about the FEATURE CONTRACT changed** across `pooled_w20` → `_t7` → `_t8`: same 15 count
features in the same order, same 8 `live_flux_cond` cond cols, same 4 axes. These are basis + population
+ version bumps, not ADR-0023 breaks.

> **✅ UPDATE from line S, 2026-07-28 15:46 — the POOLED `_t7` pair is now COMPLETE and verified.** Your
> rejection below was correct at the time and is now satisfied. Both halves exist and **both deserialize**
> (checked, not just built):
> - `drf_forest_global_pooled_w20_t7.drf` — loads in 1.5 s, 150 trees, `nfeat = 15` (11 head + 4 boundary).
> - `recruit_copula_global_pooled_w20_t7.rcop` (128 MB) — loads in 2.9 s, axes
>   `[SLA, Wooddens, D95max, minwscal]`, **8 cond cols in exactly the `live_flux_cond` order**
>   (`bm_inc_cell growth_eff water_stress soilmoist eco_diag_gdd_5 tas_cold_month soil_depth co2`), 4 marginal
>   forests, latent corr intact. Meta reports 58 766 cells.
>
> Pooled K-fold-by-cell OOS trait fidelity on this pair (nqrmse): **SLA 0.005 · Wooddens 0.016 · D95max 0.012 ·
> minwscal 0.004**. The count side is in `lines/S/STATE.md` §Status (every metric within ≈0.003 R² of `tree5`).
> Built by `VERSION=t7 scripts/run_pooled_slow_copula.sh` (job 1622337) + `run_pooled_slow_training.sh` (1622134).
>
> **Two things to carry into the swap:** (1) `n_init`/`age0` are version-coupled, exactly as you documented —
> take them from the `_t7` `cell_meta.parquet`, never mixed with the old pin. (2) The `historic`-only `_t7`
> `.rcop` (job 1622131) was still running at handoff; if you want the historic-only pair rather than the pooled
> one, check `logs/gcopula_historic_t7.*` for `JOB DONE` first. Nothing about the **feature contract** changed —
> only the training population (ADR 0031), so this is not an ADR-0023 break.

> **✅ UPDATE from line S, 2026-07-30 — the `_t8` GENERATION supersedes `_t7`. Re-pin deliberately.**
> `_t7` is intact and readable; nothing was mutated. `_t8` is the same population (ADR 0031's complete seven
> tree PFTs) re-derived on the **ADR-0035 feature bases** — `soilmoist` = root-zone year-end plant-available
> fraction of WHC, `lai` = the per-patch reconstruction. **`_t7`'s OOS numbers stay valid as OFFLINE
> measurements, but a COUPLED run on `_t7` inherits the retired bases**, which is exactly what M3 needs to
> avoid. Both halves LOAD-VERIFIED (deserialized, not just built):
> - `drf_forest_global_pooled_w20_t8.drf` — 1.4 s, 150 trees, `nfeat = 15` (11 head + 4 boundary).
> - `recruit_copula_global_pooled_w20_t8.rcop` (129 MB) — 3.0 s, axes `[SLA, Wooddens, D95max, minwscal]`,
>   **8 cond cols in exactly the `live_flux_cond` order**, 4 marginal forests, latent corr intact.
> - Tables: `slow_count_pooled_w20_t8/` (121 495 658 rows / 58 588 cells) + `slow_copula_pooled_w20_t8/`.
>
> Pooled K-fold-by-cell OOS: count **R² 0.9824 / RMSE 0.697** (held-out-CELL test R² 0.9824; hold-out-by-
> SCENARIO 0.982 / 0.9818, so the unseen-regime gap stays flat); trait `nqrmse` **SLA 0.004 · Wooddens 0.021 ·
> D95max 0.008 · minwscal 0.004**. Per-scenario `_t8` pairs also exist (`historic`, `ssp370`) if you want one.
>
> **Nothing about the FEATURE CONTRACT changed** — same 15 count features in the same order, same 8
> `live_flux_cond` cond cols, same 4 axes. So this is not an ADR-0023 break: it is a basis + version bump.
>
> **Three things to carry into the swap:**
> 1. `n_init`/`age0` are version-coupled — take them from the **`_t8`** `cell_meta.parquet`, never mixed with
>    a `_t7` or older pin. All five biome cells are covered (the `_t8` historic table has 53 699 cells, the
>    ssp370 one 58 496, same as `_t7`).
> 2. The **copula table now carries two extra DIAGNOSTIC axes** (`agb`, `Height` — ADR 0036) for validating the
>    emulator's biomass/size distributions. They are **NOT in the `.rcop`**: it declares exactly the 4
>    production axes, verified by deserializing it. `make_recruit_to_pools` is untouched. Nothing for M to do.
> 3. A `polars` streaming-determinism defect was found and fixed while building this generation (CLAUDE.md §4,
>    ADR 0036 §5b). **The pooled artifacts you pin were never affected** — the pooled table's row count is
>    exactly `22 467 348 + 99 028 310`, the correct ssp370 row set. Only the per-scenario static ssp370 table
>    was hit, and it has been rebuilt. If you build any table of your own with a streamed `group_by` over the
>    `ind` parquets, assert your own key set: the usual `drop_frac` guard cannot detect duplication.

**REJECTED at the time of writing — `*_t7` (superseded by the update above):** `drf_forest_global_pooled_w20_t7.drf` and
`drf_forest_global_historic_t7.drf` appeared **today** (58,587 cells) and line S was still mid-production when
this was written (job 1622131 `gcopula_historic_t7` RUNNING) — **there is no matching `_t7` `.rcop`**. Adopting
a half-published retrain is exactly the "never adopt a re-trained artifact silently" trap (ADR 0023). Moving to
`_t7` is an **integration point with line S** once S publishes a complete, versioned pair.

**Consequence for the M2 gate:** these artifacts live on `/p/tmp` (DVC, not git), so a CI test cannot load
them — CI runs on GitHub runners with no cluster. Split it: the **committed** demo artifact
(`test/testitems/references/drf_forest_hainich.drf`) drives the CI conservation/determinism/byte-identity gate
(closure is artifact-independent), and the pinned global pair drives the cluster-only per-cell science (M3).

### ✅ RESOLVED — the cell-coverage blocker (was: `pooled_w20` could not serve all five cells)

Found 2026-07-28 by `scripts/extract_cell_slow_init.py`'s completeness gate, *not* by inspection, and
**fixed 2026-07-30 by re-pinning to `_t8`**. Cell coverage of the `cell_meta.parquet` tables:

| table | ncells | biome cells present |
|---|---|---|
| `slow_count_historic_w20/`, `slow_runtime_historic/` (the OLD pin's pool) | 44,328 | **3/5** — no `semiarid_sahel`, no `tropical_amazon` |
| `slow_count_ssp370_w20/`, `slow_runtime_ssp370/` (the OLD pin's pool) | 53,566 | **4/5** — no `semiarid_sahel` |
| `slow_*_historic_*_t7/`, **`slow_runtime_historic_t8/`** | 53,699 | **5/5** |
| `slow_count_ssp370_w20_t7/`, **`slow_runtime_ssp370_t8/`** | 58,495 / 58,496 | **5/5** |

`semiarid_sahel` (18371) was in NEITHER table the original `pooled_w20` artifact was trained on, so that
DRF had never seen the cell and there was no honest `n_init`/`age0` for it at that version. The lesson to
keep: **read coverage out of the parquet yourself** — a meta's stated cell count and a sibling line's
handoff note are both one level removed from the thing you actually need.

### Two verified facts that constrain how per-cell S state may be sourced

1. **`n_init`/`age0` are version-COUPLED — never mix them across artifact versions.** They are the per-cell
   **median over the training years** of the count target `n_living` and of `age_mean`
   (`build_slow_runtime_table.py:320-332`, `MIN_YEARS=3`), i.e. statistics *of the training window*, not
   properties of the cell. Measured on the 44,328 cells shared by `slow_runtime_historic` and its `_t7`
   retrain: `n_init` differs for **15,665** cells (max |Δ| **24** individuals), `age0` for **22,542**
   (max |Δ| **85** years). Corollary: they are also **not** derivable from the committed single-year
   `M_individuals_<name>_2010.csv` canopy — different statistic — so that shortcut is closed.
2. **The 4 boundary columns are invariant across VERSIONS but not across SCENARIOS.** Same-scenario,
   different training version (`slow_runtime_historic` vs `_t7`): byte-identical for all 44,328 shared cells.
   Different scenario (`slow_count_historic_w20` vs `slow_count_ssp370_w20`): `eco_diag_gdd_5` differs by up
   to **1513** GDD and `tas_cold_month` by **8.84 °C** on 43,901 shared cells — physically correct, they are
   *climate* diagnostics of different climates. **Therefore a POOLED artifact has two boundary rows per cell,
   and a single baked `boundary` is a historic-climate snapshot.** That promotes M2 step 3 (per-cell
   `ClimBuf`, or a baked `boundary_series`) from optional to **required** for the pooled pin — it is the only
   way the boundary tracks the year (ADR 0026/0027). `run.jl` already owns the `climbuf=` kwarg and enforces
   that a `ClimBuf` and a baked `boundary_series` are mutually exclusive.

## NEXT — start here

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

1. **At the production `npatch=25` the C's own answer is already outside the 10 % band** — bootstrap CV `vegc`
   11.3 %, median Height 11.3 %, median minwscal 11.0 %, **median D95max 22.7 %**; in the <2 stems/patch
   stratum (7 964 cells) 31.6 % on counts and 42.7 % on carbon. ADR 0106's `max(10 %, the two-run spread)`
   branch is load-bearing. **Quote a noise floor with every fidelity number.**
2. **The 25 patches are worth `n_eff` 4.8–12.9**, not 25, because the cell-level seedbank couples the
   *inherited* trait pool. The control that proves it: median **Height** — same stems, not inherited — is
   `n_eff ≈ 25`.
3. **The per-cell trait response is not an observable in single-seed truth** (the two seeds disagree on the
   *sign* in 33–37 % of cells). Score responses on a multi-seed mean and **deattenuate**: doing so shows
   **two** broken axes, not four — SLA `0.851→1.08` and minwscal `0.689→0.99` are already correct; only
   Wooddens (0.63) and D95max (0.51) are broken. **Stop writing "four broken axes".**

**Refuted, do not re-propose** (ADR 0093 §4, with numbers): one big patch · structural stratification/quadrature ·
time-averaging instead of ensemble-averaging · a smooth trait density with no individuals · a roster ensemble
without daily physics.

### 0-NEWEST. ✅ DONE 2026-08-12 (session 14) — **THE HEAD-OF-QUEUE ASSIMILATE ERROR IS *BOTH*
### PHOTOSYNTHESIS AND RESPIRATION — AND THE 5 m WRITER CUT MAKES THE SPLIT A **BRACKET (38–78 %
### PHOTOSYNTHESIS)**, NOT A NUMBER (ADR 0129)

**Start here.** The previous handoff's step 1 — *"THE HAINICH ASSIMILATE ERROR REMAINS THE HEAD OF THE F
QUEUE … two measured leads: (a) the CUE gap, (b) F's daily GPP"* — is **measured**, and the answer is that
**neither lead can be credited with the whole error and neither can be dismissed**. New:
`scripts/biome_sapwood_bg_probe.jl` PARTs 5 / 5b / 5c + six columns appended to
`test/testitems/references/M_growth_channel_decomposition.csv`. Log of record
**`logs/M-gppcue7.<jobid>.out`** (see below). **Nothing in `src/` changed; no committed baseline moved.**

**1. THE SPLIT IS AN EXACT IDENTITY, no model in it:** `bmi = GPP · CUE` ⇒
`ln(bmi_F/bmi_C) = ln(GPP_F/GPP_C) + ln(CUE_F/CUE_C)`. F's annual tree GPP is the canopy's own `gpp_acc`
read **before `annual_step!`** (which zeroes it); the harness asserts `npp_acc == bm_inc` on every
cell-year (0 violations) so `cue` is the same object on both sides. Same rung-3 basis as ADR 0127 — the
C's own roster restarted every year, 25-patch ensemble, year-matched — and PART 1's gate against
ADR 0125's published panel still **PASSes**.

**2. THE RESULT AT THE PROTOTYPE CELL (arm A, historic 2010–2019).** GPP_F/GPP_C = **1.084**,
CUE_F 0.496 vs CUE_C 0.435 = **1.140**, product **1.236** against the published `bmi` ratio 1.239 (they
agree to 0.2 %; the residual is mean-of-ratios vs ratio-of-means, ADR 0127's own distinction — do not
quote the split as an exact factorisation). ⇒ **38 %
photosynthesis / 62 % respiration** as measured (arm Pbg: 46 / 54). **Both channels are live.**

**3. ⚠ BUT THE TWO C QUANTITIES ARE ON DIFFERENT POPULATIONS, AND THAT STRADDLES THE VERDICT.** The `ind`
writer emits only stems > 5 m (`fwriteoutput_ind.c:84`), so the C's daily GPP contains sub-5 m trees that
**both** F's roster and the C's per-stem NPP lack. `GPP_F/GPP_C` is biased DOWN and `CUE_F/CUE_C` UP by
the same factor ⇒ **the PRODUCT (every published `bmi` number) is untouched and the SPLIT is
undetermined**: 38 % photosynthesis if the short stems carry no flux, **78 %** (GPP 1.180 / CUE 1.048) if
they carry their crown share. **Quote the bracket; never one end of it.**

**4. THE DISCRIMINATOR RAN AND HAS NO POWER — and measuring that is the reusable part.** Regressing
`ln(GPP_F/GPP_C)` on `ln(gt5m)` across years looks decisive at Hainich (slope **0.83**, r **0.890**;
dividing `gt5m` out removes **98.5 %** of the decadal drift). But both series are near-monotone in time,
and **detrended it collapses to slope 0.22 / r 0.166** — which is NOT a refutation: the detrended test's
own **SE(slope) is 3.63** (boreal 41.8, mediterranean 5.3), so it cannot separate 0 from 1. The two cells
with real power (Amazon 0.19, Sahel 0.83) are unreadable for other reasons. **PART 5c now prints
`sd lnx`, `sd lny` and `SE(dt)` in the same row as every fit**, so this cannot be misread again.

**5. WHAT IT CHANGES FOR THE QUEUE.** The `sapwood_bg` port and the `rd` gate act on the **CUE channel
only**, which is worth between **+4.9 % and +14.0 %** — so `sapwood_bg_design.md` §7's ~40–50 % closure is
**~2–7 % of the assimilate error**, materially weaker than the queue implied. They stay justified by their
own ALLOCATION criterion (`t_nosink`, ADR 0127 §6) — **different channel, do not add the two cases
together.**

**6. ONE SUGGESTIVE CORROBORATION, reported as such.** The upper end of the bracket (GPP **+18.0 %**) is
within a point of the independently documented **+17 % GSI-phenology GPP level**
(`docs/notes/phase3_fdiff_cbinary_validation.md` §11). If the writer-cut change below confirms the upper
end, **the phenology is where to look first.**

**7. ONLY THE HISTORIC WINDOW CAN CARRY THIS.** The C's daily GPP exists for 2000–2019 only, so on a
scenario run PART 5's C columns print `nan` by design. ADR 0128's climate-dependence result is unaffected
(it is on `bmi`, which the population mismatch does not touch).

▶ **WHAT TO DO NEXT — in order.**

1. **CLOSE THE BRACKET C-SIDE — it is the cheapest decisive thing on the board, and no emulator arm can
   ever do it.** Remove the `ind` writer's `height > height_min` cut (`fwriteoutput_ind.c:84`) behind an
   env gate, rebuild, re-run one cell (~9 s). That hands F the C's **full** stand *and* per-stem NPP for
   the short trees, making `GPP_F/GPP_C` and `CUE_C` like-for-like in one step — and it collaterally
   retires the `gt5m` caveat from every FPC/growth number in ADR 0060/0125/0127. Pattern:
   `patches/lpjmlfit_rung2_hook_v5.patch` (opt-in, inert unless the env var is set). Gate:
   `scripts/diagnose_cbinary_rebuild_equality.py` on DECODED variables — **`cmp` on a NetCDF is the wrong
   test** (CLAUDE.md §3). Skill: `lpjmlfit-cbinary`.
2. **THEN aim at whichever channel the closed bracket names**, and score BOTH columns of PART 5 every
   time — a fix that moves the total for the wrong reason will otherwise look like progress. If it lands
   at the upper end, item 6 above says start at the GSI phenology.
3. **CLOSE THE SOIL-COLUMN APPROXIMATION FOR THE SSP WINDOW** (carried forward, unchanged): both windows
   use the HISTORIC per-cell `M_soilcolumn_<name>.txt` while the C's `whc_nat` evolves with soil carbon
   (ADR 0050). It cannot create a between-ARM difference but it can bias the between-WINDOW one, and the
   Sahel — where ADR 0128 found the sign error — is where water holding capacity matters most.
   `scripts/extract_cell_soilcolumn.py` + skill `provision-coupled-cell`.
4. **`boreal_siberia` IS STILL THE ONE CELL WHERE ALLOCATION GENUINELY BINDS** (ADR 0127: `t_loss` 33 % of
   a surplus 1.89× the C's own increment; the below-ground port is NOT its answer, `dD/bel_C` = 0.11).
   Suspects: the summergreen full-leaf recycle for the evergreen-named PFTs (`AllocParams.is_deciduous` is
   `true` for every tree in F while the C gates the `leaf/1.05` full drop on `tree->isphen`,
   `turnover_tree.c:100`), and the `reprod_cost` path. ⚠ Its warming response is unresolved at two seeds —
   score it on the LEVEL. ⚠ And its `gt5m` is 0.76, so **do not read its GPP/CUE split at all**.
5. **THE `sapwood_bg` PORT** (ADR 0127 §5/§6) — re-priced by item 5 above: keep it, but justified by
   `t_nosink` (46 / 20 / 4 % of the surplus at boreal / Hainich / mediterranean), not by CUE. Two struct
   fields on the Enzyme path, opt-in, its own session.
6. **RAISED TO THE INTEGRATOR (unchanged):** the two extra reference seeds `EXECUTION_PLAN.md` rung 0 asks
   for — 2 of 5 cells' warming response cannot be scored at two seeds (ADR 0128).
7. **📥 INTEGRATION POINT FROM LINE S (ADR 0170), still open and untouched** — the recruit half of rung 2
   (R0 = the pinned recruit copula vs R1 = the ported FIT establishment rule, both mortality settings,
   ~40 seeds). It needs the arm-C harness's establishment path, which today always answers `ESTAB_C`
   (`scripts/rung2_armc_harness.jl:318`). Conditions + what S supplies: item 4 of the 0-PREV5 block.

**CI/merge:** the diff is `scripts/**` (one `.jl`) + `test/testitems/references/**` + `docs/**` +
`.claude/skills/**` + `changelog.d/**` + STATE/JOURNAL. `references/` is under `test/**` ⇒ **all four
Julia jobs + `format`** (Runic 1.7.0 run and clean). `src/**` untouched ⇒ `docs` runs nowhere.

### 0-PREV000. ✅ DONE 2026-08-12 (session 13, part 2) — **RUNG 3 IS NOW SCORED UNDER CLIMATE CHANGE.**
### F's GROWTH ERROR **IS** CLIMATE-DEPENDENT: THE FAST CORE REPRODUCES **8 %** OF THE C's WARMING
### DECLINE AT THE TEMPERATE PROTOTYPE AND MOVES THE **WRONG WAY** IN THE SAHEL (ADR 0128)

**Start here.** The item three successive handoffs called *"cheap and still unmeasured … the acceptance
criterion's binding clause"* (ADR 0106) is **closed**. New: `scripts/growth_channel_climate_response.py`,
`scripts/diagnose_c_assimilate_noise.py`, fixtures
`test/testitems/references/M_growth_channel_decomposition_ssp370.csv` and
`M_growth_channel_climate_response.csv`. Logs `logs/M-sapbgssp2.1765952.out` (ssp370) and
`logs/M-sapbgctl2.1765953.out` (the historic CONTROL). **Nothing in `src/` changed.**

**1. THE YARDSTICK FIRST — it did not exist, and it decides which cells can be read at all.** The C's own
two-seed spread on the scored quantity (per-cell annual tree assimilate) is **1.0–12.6 %** on the LEVEL;
on the **warming CHANGE** it is boreal **+36.7 ± 20.5** · Hainich **−33.9 ± 1.4** · mediterranean
**−121.4 ± 43.4** · Sahel **+77.6 ± 11.6** · Amazon **−248.6 ± 30.4**, i.e. S/N **1.8 / 24.2 / 2.8 / 6.7 /
8.2**. ⇒ **boreal and mediterranean are UNRESOLVED at two seeds** (ADR 0111 §9's ≥3 bar) and must be
reported that way, not as passes. Regenerate with one command:
`SCENARIO=historic Y0=2010 Y1=2019 SCENARIO_B=ssp370 Y0B=2090 Y1B=2099 python3
scripts/diagnose_c_assimilate_noise.py`.

**2. THE RESULT** (arm Pbg = per-cohort PFT parameters + the seeded below-ground pool, the most faithful
configuration that exists today; `response` = F's between-window change over the C's own, with the SAME
stands and the SAME forcing on both sides in both windows):

| cell | `bmi_F/C` hist | ssp370 | **response** | verdict |
|---|---|---|---|---|
| boreal_siberia | 1.251 | 1.204 | 1.02 | unresolved (truth S/N 1.8) |
| temperate_hainich | 1.196 | 1.277 | **0.08** | **FAIL** — 8 % of a decline determined to 4 % |
| mediterranean_iberia | 2.864 | 3.338 | 2.25 | unresolved (truth S/N 2.8) |
| semiarid_sahel | 1.119 | **0.657** | **−0.34** | **FAIL on SIGN** |
| tropical_amazon | 1.066 | 1.063 | 1.08 | **PASS** |

**3. ⚠ THE LEVEL AND THE RESPONSE FAIL INDEPENDENTLY — do not treat one as evidence for the other.**
Hainich's level error is **+20 % in BOTH windows** while its response is 8 %. And arm Pbg sits inside
`[0.8, 1.25]` at three cells in each window — **but not the same three**: the Sahel leaves the band under
warming and Hainich drifts out. **A configuration validated on the historic decade is not thereby
validated under climate change**, which is the general statement rung 3 needed and did not have.

**4. THE CONTROL, and it is what licenses all of the above.** The same probe re-run on the historic window
after the scenario refactor reproduces its own committed table **byte-identically** and still passes ADR
0125's 20-number basis gate. The ssp370 daily forcing passed `build_hainich_response_forcing.py`'s own gate
against each cell's committed historic fixture at **≤1.8e-5**, which is what proves the cell index, the
YEARCELL decode, the mixed v2/v3 `.clm` scalar branch and the units.

**5. HOW TO RE-RUN IT (four env vars, no code change).**
```
SCENARIO=ssp370 Y0=2090 Y1=2099 M_CANOPY_DIR=/p/tmp/jamirp/M_canopy_drift_ssp370 \
FORCING_DIR=/p/tmp/jamirp/M_canopy_drift_ssp370/forcing \
  TIME=02:00:00 PARTITION=priority QOS=priority scripts/sbatch_julia.sh M-sapbgssp \
  --project=. scripts/biome_sapwood_bg_probe.jl
```
The inputs are already on `/p/tmp/jamirp/M_canopy_drift_ssp370/`. To rebuild them: the two extractors take
`SCENARIO=ssp370` (`extract_cell_individuals.py` is one call per year and **must** get `OUT=/p/tmp/...`,
because it rewrites `M_cells.csv` into its output directory), and the forcing comes from
`SITE=<name> OUT_DIR=<dir>/forcing python3 scripts/build_hainich_response_forcing.py`.

**6. ⚠ TWO TRAPS THIS COST, both now in the code.** (i) **Do NOT narrow `SSP_Y0`/`SSP_Y1` on
`build_hainich_response_forcing.py`** — its COMMITTED `S_*_response_boundary.csv` fixtures follow that
window, so a narrow one silently TRUNCATES five of line S's files (it did; restored with `git checkout`
and rebuilt on the default window). (ii) Julia's `@printf` needs a **literal** format string; a `*`-joined
one throws at parse time and cost a job cycle.

**7. THE ONE APPROXIMATION THAT COULD MANUFACTURE THE SAHEL RESULT.** Both windows use the **historic**
per-cell soil column (`M_soilcolumn_<name>.txt`), and `whc_nat` evolves with soil carbon in the C
(ADR 0050). It is the same approximation in every arm, so it cannot create a between-ARM difference, but it
can bias the between-WINDOW one — and the Sahel is where water holding capacity matters most. **Close that
before treating the Sahel sign error as physics.**

▶ **WHAT TO DO NEXT — in order.**

1. **THE HAINICH ASSIMILATE ERROR REMAINS THE HEAD OF THE F QUEUE, and it is now known to be a RESPONSE
   failure as well as a level one.** `bmi_F/C` = 1.20–1.28 (a +20 % level error, against a 5–6 % two-seed
   floor) *and* a warming response of 0.08. **A fix that improves the historic level and leaves the response
   at 0.08 has not fixed rung 3** — score both, in both windows, every time. The two measured leads are
   unchanged: (a) the CUE gap (F's tree CUE 0.512 vs the C's 0.46; the seed takes it to ~0.497 and
   `docs/notes/sapwood_bg_design.md` §6 says the ungated rare-day `rd` pushes the other way), and (b) F's
   daily GPP against `d_grass_gpp`-corrected C daily GPP at Hainich (skill `fdiff-validate`'s basis checks)
   — CUE alone is 1.11 against a `bmi` ratio of 1.24, so ~12 % must be GPP.
2. **CLOSE THE SOIL-COLUMN APPROXIMATION FOR THE SSP WINDOW** (§7) before any Sahel conclusion.
   `scripts/extract_cell_soilcolumn.py` + skill `provision-coupled-cell`; the C's `whc_nat` output is
   monthly and time-varying, so the ssp-window column is extractable the same way the historic one was.
3. **`boreal_siberia` IS STILL THE ONE CELL WHERE ALLOCATION GENUINELY BINDS** (ADR 0127: `t_loss` 33 % of
   a surplus that is 1.89× the C's own increment) — and the below-ground port is NOT its answer
   (`dD/bel_C` = 0.11). Suspects: the summergreen full-leaf recycle for the evergreen-named PFTs
   (`AllocParams.is_deciduous` is `true` for every tree in F while the C gates the `leaf/1.05` full drop on
   `tree->isphen`, `turnover_tree.c:100`), and the `reprod_cost` path. ⚠ Its warming response is
   **unresolved at two seeds**, so score it on the LEVEL until more seeds exist.
4. **THE `sapwood_bg` PORT** (ADR 0127 §5/§6 + `docs/notes/sapwood_bg_design.md` §9) — worth 46 / 20 / 4 %
   of the surplus at boreal / Hainich / mediterranean, needs **two** struct fields on the Enzyme path,
   opt-in, its own session. Pre-registered pass criterion in ADR 0127 §6, scored at boreal + Hainich only.
5. **RAISED TO THE INTEGRATOR:** the two extra reference seeds `EXECUTION_PLAN.md` rung 0 already asks for
   are now justified for this quantity too — 2 of 5 cells' warming response cannot be scored at two seeds.
6. **📥 INTEGRATION POINT FROM LINE S (ADR 0170), still open and untouched** — the recruit half of rung 2
   (R0 = the pinned recruit copula vs R1 = the ported FIT establishment rule, both mortality settings,
   ~40 seeds). Four pre-registered conditions and what S supplies are in item 4 of the 0-PREV5 block below.
   It needs the arm-C harness's establishment path, which today always answers `ESTAB_C`
   (`scripts/rung2_armc_harness.jl:318`).

**CI/merge:** the diff is `scripts/**` (one `.jl`, three `.py`) + `test/testitems/references/**` +
`docs/**` + `changelog.d/**` + STATE/JOURNAL. `references/` is under `test/**` ⇒ **all four Julia jobs +
`format`**; `src/**` untouched ⇒ `docs` runs nowhere. The new/edited Python is lint-clean under the repo's
own rule set (`ruff check --select E,F,I,UP,B --line-length 100`), which CI does **not** run for
`scripts/*.py` — so it was run by hand (CLAUDE.md §4).

### 0-PREV00. ✅ DONE 2026-08-12 (session 13, part 1) — **THE `keep` GAP IS NOT AN ALLOCATION DEFECT.**
### F's SURPLUS ABOVE-GROUND GROWTH DECOMPOSES EXACTLY INTO THREE CHANNELS, AND AT THE PROTOTYPE CELL
### **77 % OF IT IS THE ASSIMILATE ERROR AND 3 % IS ALLOCATION** (ADR 0127)

**Start here.** The previous handoff's step 1 — *"THE `keep` / ALLOCATION-TURNOVER GAP — now the binding
F-side item"* — is **answered, and the answer retires it as an independent defect at 4 of 5 cells**. New:
**`scripts/biome_sapwood_bg_probe.jl`** + the committed fixture
**`test/testitems/references/M_growth_channel_decomposition.csv`**. Log of record
**`logs/M-sapbg3.1765720.out`**. **Nothing in `src/` changed.**

**1. THE BASIS ERROR THAT WAS DRIVING THE ITEM.** `keep = ΣΔagb / bmi` is a ratio whose DENOMINATOR is
itself wrong (F's assimilate is 1.05–2.73× the C's). F's losses are **pool-driven** — a summergreen sheds
its whole leaf pool and its whole fine-root pool every year regardless of that year's NPP — while its
assimilate is not, so a too-large `bmi` mechanically raises the retained FRACTION even with a perfectly
faithful allocation. Measured: at Hainich F's **absolute** litter + reproduction flux is **262.1 against
the C's 266.8 gC/m²/yr — right to 1.8 %** — while its `keep` ratio is 49 % high.

**2. THE REPLACEMENT STATISTIC — an exact carbon identity, no model in it.**
`Δagb = assimilate − loss − Δbelow` on both sides ⇒
`Δagb_F − Δagb_C = (bmi_F−bmi_C) + (loss_C−loss_F) + (bel_C−bel_F)` = `t_input + t_loss + t_nosink`.
Arm A (the ADR 0125/0126 basis), gC/m²/yr, 2010–2019 means:

| cell | `dagb_C` | **surplus** | `t_input` | `t_loss` | `t_nosink` |
|---|---|---|---|---|---|
| boreal_siberia | 49.0 | **+43.5** | +9.2 (21 %) | +14.4 (33 %) | **+19.9 (46 %)** |
| temperate_hainich | 181.1 | **+152.7** | **+117.0 (77 %)** | +4.7 (3 %) | +30.9 (20 %) |
| mediterranean_iberia | 79.2 | **+320.5** | **+408.0 (127 %)** | −100.7 (−31 %) | +13.2 (4 %) |
| semiarid_sahel | 90.6 | −85.6 | −267.0 | +159.9 | +21.5 |
| tropical_amazon | 372.0 | −402.4 | −1295.8 | +755.9 | +137.5 |

(The two hot cells' arm-A columns are dominated by the ADR 0125 `respcoeff` defect — their assimilate is
negative — and are reported, not read.) **Report these three columns; do not quote `keep_F/keep_C`.**

**3. ⚠ A PUBLISHED NUMBER IS WITHDRAWN.** ADR 0125 §PART 7's `keep_F = 0.350` at `semiarid_sahel` is a
**mean of per-year ratios whose denominator changes sign between years**; the ratio-of-means is **−0.059**
and the honest statement is *undefined*. Both definitions are now printed side by side and both are in the
fixture (ADR 0060's never-substitute rule). This is ADR 0111 §9's denominator guard in its exact
predicted form.

**4. THE ONE GENUINELY NEW CHANNEL, AND IT IS PARTIAL.** `t_nosink` is the C's below-ground WOOD: the C
carries `sapwood_bg` + `heartwood_bg` (`tree.h:257`) and `allocation_tree.c:206-209/:268-277` deducts a
C_LATERAL demand from `bm_inc_ind` **before** the leaf/root/sapwood split, while F's `sap_inc` is a
residual — so the whole undeducted demand lands ABOVE ground. Reconstructing the demand with the
already-ported `FDiff.reconstruct_sapwood_bg`: it reproduces the C's own measured sink at **Hainich to
1.20×** but at **boreal to 0.11×** (that cell's sink is mostly fine-root growth, so the port is NOT the
boreal answer). Seeding the pool — which needs **no `src/` change**, `individual_from_pools` already
carries it — costs **2.4–6.3 %** of the assimilate and removes **9–12 %** of the surplus.

**5. ⚠ A DESIGN CORRECTION THAT STOPS A WRONG PORT (`docs/notes/sapwood_bg_design.md` §9, new).** §5.4 said
"grow the pool". It cannot be done in one field: `sapwood_bg` is **pinned to the demand** every year and
`turnover_tree.c:124-130` moves its turnover into a SECOND pool, `heartwood_bg`, which only accumulates and
never respires. A one-field port either **destroys ≈22 gC/m²/yr** at Hainich (a carbon leak; guardrail 2
makes conservation a CI gate) or charges maintenance respiration on below-ground heartwood, which the C does
not. `TreePools` needs `heartwood_bg_c` beside `sapwood_bg_c`, and `vegc_ind` must then take both.

**6. PRE-REGISTERED PASS CRITERION for that port** (ADR 0127 §6, written before the arm exists): with
`sapwood_bg` seeded **and** prognostic, the paired surplus must fall by **at least `t_nosink`** at
`boreal_siberia` (≥19.9) and `temperate_hainich` (≥30.9 gC/m²/yr), **no committed baseline moving while the
feature is off**, and tree CUE staying inside `[0.42, 0.56]`. Score those two cells only — the mediterranean
demand is contaminated by that cell's own 2.7× growth error and the two hot cells' arm-A assimilate is
negative.

**7. THE METHOD LESSON, captured in `residual-diagnosis`.** The probe is a deliberately SECOND, independent
reader of the rung-3 fixtures and it is **gated on reproducing all 20 of ADR 0125 §PART 7's published
numbers**. It FAILED that gate on the first run at 4 of 5 cells — and the failure *was* the finding, because
the only two things that differed were the ratio definition and the start state the C's increment is formed
against. Fixed, it passes all 20 to the printed digit with the reconstruction residual `recon` = 0.00
everywhere. **Never interpret a second reader before it reproduces the first.**

▶ **WHAT TO DO NEXT — see the 0-NEWEST block above; item 4 below is DONE (ADR 0128) and items 1-3
are carried forward there. Kept for the audit trail.**

1. **THE ASSIMILATE ERROR AT HAINICH IS NOW THE HEAD OF THE F QUEUE.** `bmi_F/C` = **1.24** at a cell that
   is **99.4 % beech** with **every per-PFT parameter already faithful** (ADR 0126's arm P moves it by
   +0.7 gC/m²/yr, its own control) — i.e. a pure F-physics defect at the prototype cell with no parameter
   excuse left, and it is **77 % of the growth error there**. Two measured leads, in order:
   (a) **the CUE gap** — `docs/notes/sapwood_bg_design.md` §13/§8 has F's tree CUE at **0.512** against the
   C's **0.46**; seeding the below-ground pool moves it to ~0.497 (measured here as −3.6 % of assimilate at
   Hainich) and the note's §6 says the **ungated rare-day `rd`** pushes the other way and partially cancels
   — land the seed first, then the `rd` gate, confirming CUE stays inside `[0.42, 0.56]`;
   (b) **GPP vs respiration**: CUE 0.512/0.46 = 1.11 but `bmi_F/C` = 1.24, so ~12 % must be GPP as well.
   Score F's daily GPP against `d_grass_gpp`-corrected C daily GPP at Hainich (skill `fdiff-validate`'s
   four basis checks) before assuming it is all respiration.
2. **`boreal_siberia` IS NOW THE ONE CELL WHERE ALLOCATION GENUINELY BINDS** (`t_loss` = 33 % of a surplus
   that is 1.89× the C's own increment, with the assimilate only +4.9 % off) — **and the below-ground port
   is NOT its answer** (`dD/bel_C` = 0.11). That makes it the right cell for the next allocation probe and
   the wrong one for the port. Suspects unchanged from ADR 0126 §6.4 minus the one now excluded: the
   summergreen full-leaf recycle for the evergreen-named PFTs (`AllocParams.is_deciduous` is `true` for
   every tree in F while the C gates the `leaf/1.05` full drop on `tree->isphen`, `turnover_tree.c:100`),
   and the `reprod_cost` path.
3. **THE `sapwood_bg` PORT** (§5/§6 above) — worth 46 / 20 / 4 % of the surplus at boreal / Hainich /
   mediterranean, two struct fields on the Enzyme path, opt-in, and the design note budgets it at its own
   session. Do it after item 1, not before: at Hainich it is a fifth of what item 1 is.
4. **STILL UNMEASURED AND IT IS THE ACCEPTANCE CRITERION'S BINDING CLAUSE (unchanged from the last two
   handoffs):** the same paired-per-stem harness on the **ssp370** forcing — *"does F's growth error depend
   on climate?"* (ADR 0106). The inputs exist: `ind_ssp370_seed1_all.parquet` is on `/p/tmp`, and
   `SITE=<name> python3 scripts/build_hainich_response_forcing.py` already emits per-cell ssp370 daily
   forcing gated against the committed historic fixture. The two blockers are one-line each:
   `IND_PARQUET` is a hard-coded constant in **both** `scripts/build_biome_stem_growth_reference.py` and
   `scripts/extract_cell_individuals.py` — make it an env knob, and run the roster extractor with
   `OUT=/p/tmp/...` because it **rewrites `M_cells.csv` into its output directory**.
5. **📥 INTEGRATION POINT FROM LINE S (ADR 0170), still open and unchanged** — the recruit half of rung 2
   (R0 = the pinned recruit copula vs R1 = the ported FIT establishment rule, both mortality settings,
   ~40 seeds). See item 4 of the 0-PREV5 block below for the four pre-registered conditions and what S
   supplies. It needs the arm-C harness's establishment path, which today always answers `ESTAB_C`
   (`scripts/rung2_armc_harness.jl:318`).

**CI/merge:** the diff is `scripts/**` (a new `.jl`) + `test/testitems/references/**` + `docs/**` +
`changelog.d/**` + `.claude/skills/**` + STATE/JOURNAL. `references/` is under `test/**`, so **all four
Julia jobs run, plus `format`** — expect `test (lts)`, `test (1)`, `test (macOS, lts)`, `format`
(`test (pre)` is the documented prerelease churn, `continue-on-error`). **`src/**` is untouched ⇒ `docs`
runs on neither the branch nor `main`.** The new script was Runic-formatted before commit.

### 0-PREV0. ✅ DONE 2026-08-12 (session 12) — **PER-COHORT PFT PARAMETERS ARE WIRED AND MEASURED.
### THE TROPICAL HALF IS FIXED, BOREAL + MEDITERRANEAN GET WORSE, ADR 0125 §7.3's PRE-REGISTERED
### CRITERION **FAILS**, AND EVERY PAST FIVE-CELL F NUMBER RAN BEECH'S PHENOLOGY (ADR 0126)**

**Start here.** The previous handoff's step 1 (wire per-cohort PFT parameters through `FDiffFastCore`) is
DONE and scored. New: `scripts/build_pft_fdiff_params_reference.py` +
`test/testitems/references/M_pft_fdiff_params.csv` (generated, gated), `test/testitems/per_pft_params_tests.jl`,
arm P + eight single-variable arms in `scripts/biome_canopy_growth_probe.jl`. Logs of record
**`logs/M-rung3h.1762579.out`** (13 arms) and **`logs/M-perpft2.1762535.out`** (suite: 274 934 pass / 0 fail,
133 items). `src/fdiff.jl`, `src/components/fast.jl`, `src/run.jl` changed.

**1. WHAT IS AVAILABLE NOW.** `FDiffFastCore(...; pft_ids = <the C's own Type per stem>, per_pft_params = true)`
gives every cohort its own `respcoeff`, `gmin`, turnover, crown allometry, `k_beer` and photosynthesis
temperature limits. Lookups: `FDiff.pft_respparams` / `pft_tempstressparams` / `pft_allocparams` /
`pft_allometry` / `pft_canopy_traits`, bundle `PFTPhys` / `pft_phys(ids)`. `per_pft_params` also accepts an
explicit `Vector{PFTPhys}` — that is how a single-parameter arm is built. **OFF by default; a beech-only
stand is byte-identical with it on** (asserted over a full simulated year), and no committed baseline moved.

**2. THE RESULT, AND THE CRITERION FAILED — do not report this as "rung 3 fixed".**
`bmi_F/C` (annual assimilate, arm A = the shipped beech set → arm P = per-cohort):
boreal **1.049 → 1.275** · Hainich 1.239 → 1.241 (99.4 % beech ⇒ the control) · mediterranean
**2.727 → 3.056** · Sahel **−0.457 → 1.132** · Amazon **−0.208 → 1.118**. Paired Σ`dagb`: 1.62→2.26 /
1.86→1.87 / 4.00→5.10 / 0.04→1.48 / −0.07→1.45. In band at **3 of 5**, moved toward 1 at **2 of 5** ⇒
**FAIL** on both measured clauses. Nothing was tuned and the criterion was not rewritten.

**3. WHY THAT IS NOT AN ARGUMENT TO REVERT, and the general rule.** These ARE the C's own parameters
(`cpp -P`); beech-in-the-tropics was not a defensible alternative (the stands were LOSING biomass). The
criterion required one change to also close two defects ADR 0125 had already attributed elsewhere (the
1.49–1.85× `keep`/allocation gap; mediterranean's independent 1.3–1.5× GPP bias). And **boreal's good-looking
1.049 came from two wrong parameters of opposite sign** (20/30 °C optimum instead of 15/25, extinction 0.59
instead of 0.45) — making both faithful exposed a real +27 % bias. ⇒ **a cell that scores well under wrong
parameters is not thereby validated** (second occurrence in this repo after ADR 0060).

**4. ⚠ A FINDING THAT IS NOT ABOUT THIS FEATURE AND CHANGES HOW TO READ EVERY PAST F NUMBER: arm A — the
published rung-3 arm and every earlier five-cell F number — RAN BEECH'S GSI PHENOLOGY FOR EVERY TREE.**
`pft_ids` has always existed and the probe never passed it. Passing it alone (`subset = :phen`) moves the
Sahel's `bmi_F/C` by **+1.01** (−0.457 → 0.557) and mediterranean's by **+0.38**. It is free to close.
**Pass real `pft_ids` in every future arm regardless of `per_pft_params`,** and treat any pre-0126
five-cell F number as beech-phenology. This also narrows ADR 0125's Sahel reading: ~a third of that
shortfall was phenology, NOT ADR 0052's dry-cell root zone.

**5. THE ATTRIBUTION (eight one-field arms; read every column against `phen`, never against `A`).**
`respcoeff` alone IS the tropical fix (Amazon −0.208 → **1.128**; nothing else moves that cell).
Boreal is pushed by `temp_photos` (1.026 → 1.124) and `gmin` (→ 1.191) while the correct needleleaf
`k_beer` alone gives **1.004**, the best single number in the table. Mediterranean is **phenology and
nothing else**. ⚠ The arms do not sum to P (nonlinear canopy; `alloc`/`allom` act through next year's
pools). The first attribution run (job 1762534) was CONFOUNDED by exactly this phenology effect — a
one-variable arm that silently carries a second change is worse than no arm.

**6. TWO GUARDS SHIP WITH IT.** `run_coupled_cell` **ERRORS** on a per-PFT core + a slow emulator (S's
demography rebuilds the roster with the shared allometry ⇒ per-cohort physics daily, beech's `k_beer`
annually = a mixed basis, ADR 0060's failure class), and both growth entry points assert
`length(pft_phys) == length(pools)`. **The S-side wiring is raised as an INBOUND in `lines/S/STATE.md`**
(three call sites + rebuild the bundles on a roster-length change); until S lands it there is no coupled
per-PFT arm.

**7. PRE-REGISTERED FLIP CRITERION for the default** (ADR 0126 §6.2, written before the next arm): flip
`per_pft_params` to `true` when arm P reaches **both** `bmi_P/C` and Σ`dagb` P/C **∈ [0.8, 1.25] at all
five cells** on this probe, with the beech-only byte-identity item still green.

▶ **WHAT TO DO NEXT — ⛔ ITEM 1 IS ANSWERED AND RETIRED by the 0-NEWEST block above (ADR 0127); items
2-5 stand and are re-pointed there. Kept for the audit trail.**

1. **THE `keep` / ALLOCATION-TURNOVER GAP — now the binding F-side item** (ADR 0125 §7 named it; ADR 0126
   §6.4 confirms it). Σ`dagb` F/C overshoots **1.45–1.48 even at the two cells whose assimilate is now
   right**, and 1.87–5.10 at the other three, so at three of five cells the remaining error is allocation,
   not carbon input. Per-PFT `turnover` is already wired (the `:alloc` arm moves Σ`dagb` while barely moving
   `bmi` — the expected signature) and it is NOT enough. Next suspects, in order: the summergreen full-leaf
   recycle (`AllocParams.is_deciduous`/`deciduous_leaf_div` = 1.05 for every tree — check against
   `turnover_tree.c` for the evergreen-named PFTs, which this par file still calls `summergreen`), the
   `reprod_cost` 0.1 path, and whether F's `agb` reconstruction and the C's `agb` column are the same pool
   set (the `keep` statistic divides one by the other).
2. **Boreal's `temp_photos` + `gmin` pair** (§5). Two faithful parameters that each make the assimilate
   worse, at a cell whose `k_beer`-only arm is 1.004. Cheap, and it is the clearest single-cell attribution
   on the board: drive the same paired harness with the three arms and check whether the residual is a
   temperature-response shape error (`temp_stress`'s `k1/k2/k3` from `temp_stress.c:38-40`) rather than the
   limits themselves.
3. **Mediterranean is a phenology + GPP cell, not a parameter cell** (§5 + ADR 0125 §5). Its `bmi` is 3.1×
   and no per-PFT parameter touches it. Start from the GSI filters of ids 1/2 (`pft_phenparams`) against the
   C's own leaf-display, then its 1.3–1.5× GPP.
4. **Then re-run the probe and re-score the flip criterion of §7.** Do not flip on a partial improvement.
5. **Cheap and still unmeasured (unchanged from the last handoff):** the same paired-per-stem harness on the
   ssp370 forcing — "does F's growth error depend on climate?" is the acceptance criterion's binding clause
   (ADR 0106) and rung 3 has never measured it.

**CI/merge: ✅ MERGED to `main` (the feature at `ca717bf7`, the follow-up fix at `847acdd2`), `docs`
GREEN again on `847acdd2` — but read this, it cost a red `main` and three CI cycles.** Branch CI was green on
all five expected checks (`test (lts)`, `test (1)`, `test (macOS, lts)`, `format`; `test (pre)` is the
documented prerelease `ScopedValue` churn, `continue-on-error`) and the merge collated the changelog
fragment. **`main` then failed `docs`** — the one gate that never runs on a line branch — because
`docs` **also watches `src/**`** (Documenter splices main-module docstrings into
`docs/src/reference/api.md`) and three new `[`FDiff.PFTPhys`](@ref)` links cannot resolve: `api.md`
renders `@autodocs Modules = [LPJmLFITEmulator]` only, so the `FDiff` submodule API is deliberately
unrendered. Fixed in `fd0cef0d` (plain backticks, the convention every pre-existing `FDiff.*` mention in
`fast.jl` already follows), verified by running the real build to `RenderDocument` plus the mermaid HTML
check. **STANDING RULE, now in CLAUDE.md §2 and the `repo-commit` skill: if your diff touches `src/**`,
build the docs locally before merging — a `src`-only diff has NO branch-side coverage for that gate.**
Two further mechanical lessons from the same merge, both captured in `repo-commit`: (i) `main` moved
TWICE during the ~15-minute branch-CI waits, and each rebase re-conflicted
`.claude/skills/repo-commit/SKILL.md` because line S was appending to it the same day — the resolution is
always **keep BOTH sections**, and it is now provable rather than eyeballed
(`diff <main's version> <yours> | grep -c '^<'` must be 0; it was, twice); (ii) the merge ritual's
`pull --ff-only origin main` does **not** refresh `origin/line/<X>` in `$INT`, so `fetch origin main
line/<X>` first and guard the merge on the exact sha CI verified — the flock'd block in this session's
log does both.

### 0-PREV1. ✅ DONE 2026-08-12 (session 11) — **RUNG 3 IS MEASURED.** F's GROWTH ERROR IS **PER-YEAR
### AND BIMODAL BY BIOME** (1.6–4.0× TOO FAST COLD, **NEGATIVE CARBON BALANCE** HOT), AND ONE **PER-PFT
### RESPIRATION COEFFICIENT** CARRIES THE WHOLE TROPICAL HALF (ADR 0125)

**Start here.** The previous handoff's step 1 ("RUNG 3 — F's decadal canopy drift, head of the queue") is
DONE. New tooling: **`scripts/build_biome_stem_growth_reference.py`**, **`scripts/biome_canopy_growth_probe.jl`**,
**`scripts/diagnose_oracle_run_divergence.py`**. Log of record `logs/M-rung3d.1761700.out` (4 jobs, all exit 0,
~2.5 min each). Nothing in `src/` changed.

**1. THE FACT THAT MADE IT POSSIBLE, and it was sitting unused in a 29-column table: `(Cell, Patch, ID)` is a
STABLE CROSS-YEAR INDIVIDUAL IDENTITY** in the annual `ind` output. Over 13 152 tree stem-years at the five
cells: `Age` increments by **exactly 1** on all 10 323 pairs, `SLA`/`Wooddens` are **bit-identical** (the
independent check — traits are immutable after `new_tree`, so a shuffled identity would break it), no
`isdead == 1` stem ever returns, and only **8 stem-years vanish**, all within **0.4 m** of the writer's 5 m
emission cut (threshold flicker; one is emitted again two years later). ⇒ **F can be restarted from the C's
own stand every year and every stem scored against ITS OWN next-year row.** Every previous F-vs-C structural
number in this repo was a decadal aggregate.

**2. THE RESULT — the per-year growth error, same sign in all ten years, OPPOSITE signs across biomes.**
Σ per-stem annual above-ground biomass increment, F over C: **1.62** boreal · **1.86** Hainich · **4.00**
mediterranean · **0.038** Sahel · **−0.071** Amazon (F's stems *lose* biomass where the C's gain).

**3. WHERE IT ENTERS — one table, no new run, because the C emits each stem's own annual NPP.**
`bmi` = assimilate handed to allocation (gC/m²/yr); `keep` = ΣΔAGB / that assimilate:

| cell | bmi_F | bmi_C | F/C | keep_F | keep_C | keep F/C |
|---|---|---|---|---|---|---|
| boreal | 198.0 | 188.8 | **1.05** | 0.465 | 0.251 | **1.85** |
| Hainich | 606.0 | 489.0 | **1.24** | 0.549 | 0.368 | **1.49** |
| mediterranean | 644.2 | 236.2 | **2.73** | 0.602 | 0.269 | **2.24** |
| Sahel | **−83.8** | 183.2 | **−0.46** | 0.350 | 0.493 | 0.71 |
| Amazon | **−223.2** | 1072.5 | **−0.21** | 0.143 | 0.347 | 0.41 |

**F's annual carbon balance is NEGATIVE at the two hot cells while its GPP is within a few % of the C's** —
so the tropical failure is respiration, not photosynthesis.

**4. THE CAUSE, TESTED AS AN ARM (no code change).** `respcoeff` is **per-PFT** in the live
`par/pft_lpjmlfit.js`: **0.2** for the tropical broadleaved evergreen tree (id 0), **1.2** for all six
temperate/boreal trees — a **6× spread**. F holds ONE scalar for every tree in every cell — **1.2**, beech's,
from `tebs_params` (`fdiff.jl:1287`). Sahel and Amazon are **100 % id 0 by sapwood**. Substituting the cell's
own value and nothing else: **Amazon −223 → +1206 against a truth of +1073**, paired growth ratio **−0.07 →
1.02**; Sahel −0.46 → **0.40** (sign fixed, 2.5× shortfall left = ADR 0052's dry-cell root zone, a second
independent defect in that cell); the other three **unmoved by construction** (1.2 → 1.2), which is the arm's
own control that it changes exactly one thing.

**5. ⚠ THE DECADAL DRIFT UNDERSTATES THE RATE ERROR BY ~10× — THE CANOPY SATURATES.** Compounding F's
*per-year* crown growth gives **20.4×** at boreal against the free-running arm's **1.67×** (the free arm
reproduces the published +67/+29/−13 %, which is the harness's basis check). Crown area is capped, cover is
bounded, the stand closes. **RULE: a bounded stock's drift is a LOWER BOUND on the rate error driving it —
score the rate, never the accumulated stock.**

**6. ⚠ TWO REFERENCE-BASIS CORRECTIONS, both measured rather than argued.**
* **The kernel probe's year alignment is off by one.** The `ind` row for year y is written at the END of
  year y, so `biome_fdiff_oracle_probe.jl` drives the end-of-2010 stand with **2010** weather. The correct
  pairing (roster(y−1) + forcing(y) → roster(y)) wins the paired per-stem test at every cell where the test
  has power. Ratios over the window mostly survive; **levels do not** (ADR 0060's ratio-vs-level rule).
* **The committed structural oracle is a DIFFERENT RUN from the one F is initialised from.**
  `M_fdiff_oracle_biomes_annual.csv` comes from the single-cell re-runs; F's canopy comes from the GLOBAL
  run's `ind`. Daily GPP over 2010–2019: four cells agree to <1.2 % (r ≥ 0.9989), **tropical_amazon differs
  by 6.7 % with r = 0.970** ⇒ an Amazon level miss against `a_fpc` is not an F error. Also `a_fpc` contains
  sub-5 m stems F cannot have, and that fraction is **time-varying** (boreal 0.712 → 0.806), so it
  contaminates the DRIFT and not just the level. Score against `references/M_stem_growth_reference.csv`'s
  `fpc_live`/`fpc_all`, formed from the very stems F is handed.

**7. A LATENT REGISTRY-EATING BUG, found and fixed on the way.** `extract_cell_individuals.py` rewrote
`M_cells.csv` from its own ten-column header and dropped every row whose field count differed — so a re-run
would have **silently deleted the six columns `extract_cell_slow_init.py` appends** (the pinned Component-S
per-cell seed: `n_init`, `age0`, the four-column boundary). Now preserves columns and comment lines it does
not own; a re-run over the live registry is byte-identical.

▶ **WHAT TO DO NEXT — ⛔ SUPERSEDED by the 0-NEWEST block above (ADR 0126). Step 1 is DONE and scored;
steps 2-4 are re-pointed there. Kept for the audit trail.**

1. **WIRE PER-COHORT PFT PARAMETERS THROUGH `FDiffFastCore` (item 3 / M5 below). This is now the head of the
   F-side queue** — and it is **raised to line S as an integration point** (an INBOUND block in
   `lines/S/STATE.md`, 2026-08-12): the same wiring unblocks their pre-registered `trait_mortality` flip,
   which has been waiting on `fc.pft_ids` since ADR 0049. M owns `fast.jl` and lands it; S needs to do
   nothing until it is there. and it is no longer a tidy-up: `fast.jl:147` gives every tree beech's parameters, which is a
   **6× respiration error at every tropical cell** — 100 % of the stems at two of the five biome cells and the
   whole tropical belt globally. The `type` column is already in `references/M_individuals_<name>_2010.csv`
   (and the per-year rosters under `/p/tmp/jamirp/M_canopy_drift/individuals/`), so no new extraction is
   needed. **Line S also requires this before `trait_mortality` can be flipped** (ADR 0049) — one change
   serves both. **PRE-REGISTERED PASS CRITERION (ADR 0125 §7.3, do not re-read it after the fact):** with
   per-cohort `pft_ids` wired, `bmi_F/C` lands in **[0.8, 1.25]** at all five cells and the paired Σ`dagb`
   F/C moves toward 1 at all five, with **no** committed baseline moving while the feature is off.
2. **Then the `keep` gap — a NEW, named F-side item.** At boreal/Hainich the assimilate input is right
   (1.05 / 1.24) while F retains **1.85 / 1.49×** as much of it as standing above-ground biomass. That is
   allocation/turnover, it is untouched by the respiration fix, and it is what is left of the temperate
   over-growth. Per-PFT `turnover` is also in `par/pft_lpjmlfit.js` (leaf 1.0–4.0 yr, sapwood 25–30 yr) and
   F carries one set — check that first, it may be the same fix as step 1.
3. **Re-run the probe after step 1 and re-score item 4(d).** The Sahel is now known to be **two** defects,
   only one of which the parameters fix; measure the remainder rather than assuming ADR 0052 covers it.
4. **Cheap and worth it if the above stalls:** the same paired-per-stem harness answers "does F's growth
   error depend on climate?" by running it on the ssp370 forcing — which is the one thing rung 3 has NOT
   measured and the acceptance criterion's binding clause (ADR 0106).

**CI/merge:** the diff is `scripts/**` + `docs/decisions/**` + `changelog.d/**` + STATE/JOURNAL **plus
`test/testitems/references/**`** (the `id`/`age` columns and the new `M_stem_growth_reference.csv`).
`references/` is under `test/**`, so this triggers **all four Julia jobs AND `format`** (a new `.jl` script) —
not a no-gate commit. Wait for `test (lts)` and `test (1)` before merging.

### 0-PREV5. ✅ DONE 2026-08-11 (session 10) — **ARM C IS RUN.** SELECTION CARRIES **71 %** OF FIT's
### WOOD-DENSITY DIFFERENTIAL, THE SHIPPED UNIFORM-THINNING NULL **RESTRUCTURES THE STAND**, AND THE
### OPTION-(c) INTERFACE REACHES ITS CEILING EXACTLY (ADR 0124)

**Start here. The single pre-registered next step of the previous handoff is DONE.** 16 runs, 14 s each
(jobs 1759477–1759492, all `rc=0` with the mandatory `lpjml successfully terminated, 1 grid cells processed.`).
New tooling: **`scripts/rung2_armc_harness.jl`** (the Julia rendezvous server — it calls the *shipped*
`TraitMortality.mortality_hazard` and `LPJmLFITEmulator._hazard_tilt`, never a copy of either),
**`scripts/run_rung2_armc.sh`**, **`scripts/diagnose_rung2_armc.py`**. Report:
`/p/tmp/jamirp/M_rung2/armc_report/{armc_score.txt,armc_gradient.csv}`.

**1. THE INTERFACE IS EXACT, LIVE — and the port holds outside the states it was gated on.** ADR 0122's gate
ran offline on the recorded trajectory only. Three new results: ρ from the port vs ρ from the C's own
`mort_prob` **max |Δ| 4.4e-16 over 5 000 patch-years**; **θ = 1 to 4.5e-14 over 2 500**; and the identity gate
re-run on the *null* arm's dump (a stand the recording never had — **7× the ghost-tree rate**) still gives
**0 exceedances / max rel Δ 1.7e-15 over 10 600 records**, 105 `bm_inc_counter` + 769 ghost-tree hard kills
classified. The C's own audit: `n_kill_applied/n_kill_c` **0.980–1.014**, `n_spared_certain` **= 0**.
⇒ **RULE: an identity gate is only as wide as the state distribution it ran on. Re-run it on every new arm's
dump — one command.**

**2. THE RESULT** (C truth 365 terminal stems, selection differential **+35 376 gC/m³**; 5 seeds/arm):

| statistic | **C1** (the tilt) | **C0** (`f_i = ρ`, the SHIPPED default) |
|---|---|---|
| terminal stems | **383.2 ± 18.7 = 1.050×** | 441.2 ± 21.8 = **1.209×** |
| wood-density selection differential | **+33 684 ± 2 841 = 0.952×** | +8 541 ± 2 455 = **0.241×** |
| per-PFT gradient Spearman ρ vs **this cell's own recording**, ids 1–5 | **1.000/1.000/0.943/1.000/1.000** | 0.800/0.500/0.943/0.600/**−0.500 (id 5 BACKWARDS)** |

⇒ **`C1 − C0` = +25 142 = 71.1 % of the differential is differential survival.** ADR 0117's argument for
option (c) over a count-only interface is now a measurement.

**3. ⚠ THE BIGGEST DEPARTURE IS INVISIBLE TO EVERY COUNT STATISTIC — the age structure.** Terminal stems
`<20` / `20–40` / `≥40` yr: the C **118/120/127**; **C1 117–147 / 111–145 / 103–126**;
**C0 336–404 / 25–47 / 26–47** — the null converts a mature stand into a young one (**80 % under 20 yr**) and
keeps only **10–16 %** of the C's own `≥40` yr individuals *by identity* against C1's **50–63 %**.
**Report the three bins and the identity overlap with any arm.** (20 yr is exactly the run length, so `<20` is
what the arm built and `≥40` came from the shared restart — but it is not pure inheritance: C1 has already
turned over 37–50 % of it, C0 84–90 %.)

**4. ⚠ A COUNT TARGET IS NOT A COUNT.** Both arms get **identical per-patch-year targets in expectation** and
both draws are unbiased (579 vs 581.6 expected; 1 096 vs 1 105.9) — and still end 1.05× vs 1.21×. The null
spares trees FIT condemns (**669–817** `n_spared_certain`), their hazard stays high, so next year's ρ falls: it
kills **twice as many trees in total** and ends **denser**. Who dies feeds back into how many ⇒ **a
density-only report cannot tell a right answer from two cancelling wrong ones.**

**5. THE COUNT TARGET'S OWN FAILURE MODE** (`RHO=recorded` — a target from outside the live state, the honest
proxy for a learned ρ): θ is **BIMODAL**, median 0 / p95 12–14, θ > 0.5 in 207–215 of 500. The median of 0 is
**not** a collapsing tilt — **the C kills nobody in 198 of 500 patch-years (39.6 %)** at this cell (558 deaths
in 9 951 tree-years), so a realized-count target is 1.0 and selection has nothing to do. In **25–27 % of
patch-years no θ reaches the target at all** (`shortfall > 0`; the hard kills alone overshoot). `C0/recorded`
applies only **38–48 %** of the kills the C wanted and ends **1.536×**.

**6. ⚠ A MEASUREMENT RULE, CORRECTED — do not score a per-cell arm against the GLOBAL gradient fixture.**
`references/S_age_wooddens_gradient.csv` is all 54 020 cells; **the C's own recording at cell 42490 scores
Spearman ρ −0.500 / −0.314 / +0.400 / −0.500 / +0.800 against it** (ids 2/3/4/5/1). A naive reading of
ADR 0118 §3 as "match the fixture" **would have failed FIT itself**. Use the cell's own recording per-cell,
the fixture only globally; `diagnose_rung2_armc.py` prints the C's own row so this is measured, not asserted.

**7. ⚠ WHAT ARM C DOES *NOT* SHOW — read before quoting item 2.** C1's count target came from the operator's
own hazard, which pins **θ = 1 analytically**, so C1 **is** FIT's mortality with an independent Bernoulli
stream: a **CEILING** and an end-to-end identity, **not** evidence about any learned count model. And the
hazard ran on the C's **own** `water_stress`/`temp_stress`/`bm_delta`/`bm_inc_counter` through the rendezvous,
so **ADR 0049 item 4 still bites in the standalone emulator** and item 2 does **not** license flipping
`trait_mortality` there. Scope that rides with every number: **one cell of 54 020**, one scenario, **no
climate-change response measured**, **4 of 7 trait axes** substituted, establishment deferred to the C in both
arms, and ADR 0123's **0.05 %** deferred-kill disclosure (shared by both arms *by construction*).

**8. RAISED TO LINE S** — an INBOUND block in `lines/S/STATE.md` carries items 1–6 plus the **pre-registered
conditional flip criterion** for `trait_mortality` (guardrail 4's corollary): arm = the coupled
`FluxDrivenSlowEmulator` at 42490, 25 patches, 2000–2019, 5 seeds, default `false` → `true`; pass = the
three-bin age structure of item 3 within the C's seed spread on all three bins AND gradient ρ ≥ 0.9 on ids 1–5
against *this cell's recording*; blocked by ADR 0049 item 4, which only S can close.

▶ **WHAT TO DO NEXT — in order.**

1. **RUNG 3 — F's decadal canopy drift. This is now the head of the queue** (item 0-NEW below, item 4(d)
   further down). Rung 2's mortality half is finished: the interface is exact (item 1), its ceiling is
   measured (item 2), and its remaining gap is line S's to close (item 8). Nothing on rung 2 is owed by M.
2. **Optional, cheap, and it would strengthen ADR 0124 from one cell to five:** the arm-C harness is
   cell-agnostic — `run_rung2_armc.sh` takes `SRC`/`DUMP`, so a second biome needs only a `MODE=record`
   baseline at that cell (`scripts/run_rung2_replay_arm.sh`) and then 2 arms × 5 seeds at 14 s each. The
   *only* claim it would upgrade is generality; it changes no mechanism above. Do it if rung 3 stalls, not
   before it starts.
3. **Do NOT re-run arm C with the learned count model in the loop as "the production arm" without first
   reading item 5.** At this cell FIT kills nobody in 40 % of patch-years, so a null `C1 − C0` under a
   learned ρ is the expected outcome and is not a result about selection. If it is run, report the θ
   distribution and the shortfall rate beside it, exactly as `diagnose_rung2_armc.py` does.
4. **📥 INTEGRATION POINT RAISED BY LINE S, 2026-08-12 (ADR 0170) — the RECRUIT half of rung 2 is
   pre-tested, pre-registered and ready to run on your harness; it is UNREADABLE offline, and the reason is
   your own item 5.** This is the arm ADR 0119 §6 registered (R0 = the pinned recruit copula vs R1 = the
   ported FIT establishment rule, both under a held-common mortality setting). It asks for **no change to the
   hook and none to `src/`** — it is the same contrast with the axis moved to the recruit channel.
   * **Why it cannot be settled offline.** S ran the identical 2×2 on the standalone harness at 42490, two
     40-seed ensembles (ADR 0170). The kill condition — does the recruit channel make the error
     climate-dependent the way the count recursion did — **does not fire**: R0's own warming response is
     significantly **wrong-signed** (−0.75 ± 0.24 ×FIT against FIT's +1) and the port turns it **+2.66 ±
     1.01**. But the arm does not clear either: |error| 1.66 vs R0's 1.75 is a dead heat, and the **level
     moves +8.5 %** (+19 701 ± 1 281 gC/m³, t = 15 — 8.1× FIT's whole warming shift, as a static offset),
     which blocks a flip on ADR 0106 grounds by itself. The natural fix — pair the port with the selection
     operator — **failed offline**: the level effect is *larger* with `trait_mortality` on (+24 186), because
     at this cell θ is throttled to ≈ 0 (your item 5; ADR 0049 item 5) so the operator has nothing to
     redistribute. **Rung 2 is the first place it has room, because there the roster returns from the C each
     year.**
   * **Four conditions, pre-registered in ADR 0170 §3 so they cannot be reinterpreted after the run:**
     (i) run **both** mortality settings, not only C1 — offline they differ in the level (+19 701 vs
     +24 186), in the sampler's own scenario response (n.s. vs +4.73 ×FIT) and in whether hard kills fire at
     all (0/40 vs 4/40 seeds); (ii) **read θ first**; (iii) **read the LEVEL, not only the response**;
     (iv) **size the ensemble from THIS arm's own spread** — the double difference's seed sd is
     **6.4–7.8 ×FIT** against the mortality arm's 0.67–1.74, so ADR 0101's 8–12 seeds resolve nothing here
     (12 left every CI straddling zero; 40 resolved it).
   * **What S supplies so you build nothing:** `scripts/build_estab_eligibility.py` emits the per-cell(-year)
     eligible-PFT set + `n_elig`/`w_inherit` for **all 67 420 cells × 20 yr**, both scenarios
     (`/p/tmp/jamirp/emulator_global/tables/estab_eligibility_{historic,ssp370}_w20.parquet`; `CSV_OUT=` for a
     committable per-cell fixture), gated against FIT's own `ind` at **0.076 %**. Two C facts you need if you
     gate recruits per cell: **`n_elig == 0` does NOT mean nothing establishes there** (the inheritance block
     at `establishmentpft_ind.c:125` sits outside the `aprec`/`establish()` loop — 22.1 % of cell-years are in
     that state), and the gate's `temp_min20` is **not** the boundary table's `tas_cold_month`
     (`mean_y(min_m T)` vs `min_m(mean_y T)`, +0.73 °C apart on average; ids 4/5/6 have `temp_high = 0.0`, so
     the wrong basis silently deletes them — {1,2,3} instead of the correct {1,2,3,4,5,6} at Hainich).
   * **NOT claimed:** the offline run is **1 cell of 54 020**, a smoke test of the kill condition, and neither
     fidelity evidence nor the flip test. S is **not** asking you to flip anything —
     `recruit_establishment` stays OFF by default. And S's earlier caveat that a wood-density result is
     unreadable in rung 2 is **retired by your own ADR 0123**: the lag is gone, so this arm is scorable on
     traits as well as counts.
   * **Cost, on your item-2 estimate:** 2 recruit arms × 2 mortality settings × N seeds at ~14 s each on an
     existing `MODE=record` baseline at 42490 — the ensemble is the whole cost, not the harness.

**CI/merge:** the diff is `scripts/**` + `docs/decisions/**` + `changelog.d/**` + STATE/JOURNAL — **no gate
runs** (ADR 0090: `scripts/*.py` is NOT linted by CI, no `src/`/`test/`/`.jl`-in-tree change, no `python/`,
no `docs/src/**`). `scripts/rung2_armc_harness.jl` **is** a `.jl` file, so **`format` (Runic) DOES run** —
that is the one gate to expect. Mergeable as soon as `format` is green.

### 0-PREV4. ✅ DONE 2026-08-11 (session 9) — THE RENDEZVOUS MOVED BEHIND THE GROWTH LOOP; THE LAG IS
### GONE **EXACTLY** AND ARM C IS NOW SCORABLE ON TRAITS (ADR 0123)

**Start here. The single pre-registered next step of the previous handoff is DONE, and it worked.**
ADR 0122 §4's ban on scoring arm C's trait question is **LIFTED** — by fixing the rendezvous, not by
reinterpreting it.

**1. WHAT CHANGED.** `annual_tree` still runs turnover, allocation and `mortality_tree_ind` — including its
`erand48` draw — unchanged, but under either rung-2 hook it reports every tree **alive** and hands its
verdict (plus a `hard` flag) to the new `rung2_apply_note`. After the `foreachpft` loop the C dumps a new
**`grow`** phase (the complete current-year roster, before anyone is removed), opens the rendezvous on
**that**, and a **kill pass** applies the final verdicts with their `litter_update` and `mort_tree` counter.
The kill *has* to move with the rendezvous — a tree the external demography spares must not already be in
the litter. Patch **`patches/lpjmlfit_rung2_hook_v5.patch`** (supersedes v4; v2/v3/v4 kept for the
provenance of the binaries ADR 0120/0121/0122 gated).

**2. THE RESULT — both bases now print from one dump, so the fix is visible, not asserted.**

| rendezvous basis | records usable / skipped | Spearman ρ vs the C's `mort_prob` (p05 / median / min) | wood-density selection differential | ratio to the C |
|---|---|---|---|---|
| `pre` — the OLD rendezvous | 9 009 / 942 | 0.467 / 0.900 / −0.200 | −14 591 | **−0.825 ⚠ opposite sign** |
| **`grow` — the LIVE rendezvous** | **9 951 / 0** | **1.000 / 1.000 / 1.000** | **+34 045** | **+1.000** |

The 942-record skip disappearing is a second win: a first-year tree had no previous `mortality_tree_ind`
call, so on the lagged basis the **youngest cohort — where selection is strongest — was invisible**. The
θ=1 identity gate still passes exactly on the re-recorded dump (9 951 records, 0 exceedances, max rel Δ
1.7e-15, 175 + 195 hard kills); the CI fixture `references/M_rung2_hazard_identity.csv` was regenerated on
the new basis (82 of 333 records moved, header unchanged).

**3. ⚠ THE COST, MEASURED — quote this beside every rung-2 number.** The deferral is shared by **both**
hooks (`rung2_defer_mortality()`), because if only the substitution hook deferred, the recorded baseline and
every arm would sit on different code paths and the difference would be charged to the arm. Sharing it makes
the null control exact **by construction**. The reorder is *mathematically* inert (litter pools are sums;
`avg_fbd` is an exact incremental carbon-weighted mean; nothing between the loop and the kill pass reads
either; `litter_update_tree` mutates only the dying tree's own pools) but **not bit-identical** — FP
addition is not associative. Deferred vs stock path, same config/cell/`--ntasks`: bit-identical through
**2002**; first difference 1.1e-7 on a daily NPP of −0.081; demography first differs 2004 by **one stem**;
**3 of 20 years** differ, always by one stem; **2019 stem count identical (229 = 229)**; total stem-years
5 963 vs 5 966 = **0.05 %** — two orders of magnitude below the smallest noise floor this model has (11.3 %
bootstrap CV on `vegc` at `npatch=25`). It cannot bias an arm comparison, but it **is** a departure from
stock LPJmL-FIT and belongs in the open, not in a footnote.

**4. GATES, all green.** Rebuild equality with **both env vars unset** vs the previous build's matched
single-cell run: **139 decoded quantities identical, 0 differ**, `globalflux` + `ind` byte-for-byte ⇒ the
stock model is untouched. `MODE=none` vs the re-recorded baseline: **identical in every initialised column
over 40 161 tree records**, and `diagnose_rung2_cellstate_equality.py` reports **no divergence in all 2 000
patch-years** (stream, seedbank checksums, live count). New baseline dump:
**`/p/tmp/jamirp/M_rung2/M_rung2rec_v5_dump`** — ⚠ **any dump recorded earlier has no `grow` phase and is
unusable as a replay basis; the harness now fails loudly on one.**

▶ **WHAT TO DO NEXT ON RUNG 2 — in order.**

1. ✅ **Done in the same session — the replay floors are UNCHANGED by the move.** All four arms re-run on
   the v5 basis: `none` **1.000**, `kills` **1.000 exact** (identical in every initialised column AND in all
   2 000 cell-state patch-years, no year differs), `recruits` **0.907**, `both` **1.367** — the same numbers
   ADR 0121 measured on the old rendezvous, to three decimals. So the floors are a property of what the wire
   format substitutes (4 of 7 trait axes; the C's Poisson + inheritance draws skipped), not of where the
   rendezvous sits. **These are the floors to quote.**
2. **Run arm C** — this is the actual next piece of work. with line S's two arms in one wire format: **C0** `f_i = ρ` for every tree (the
   shipped uniform thinning = the no-selection null) and **C1** the tilted `f_i = (1−mort_i)^θ`.
   **Print θ beside the result** (S's ADR 0117 item 6.i: at Hainich θ median was 8.5e-12 with θ > 0.5 in
   only 18 of 132 thinning years, so a null `C1 − C0` may mean the count model gave the selection no room).
   And per ADR 0118 §3, test the per-PFT **gradient SHAPE** against
   `references/S_age_wooddens_gradient.csv` — including the non-monotone ids 0 and 3 — not just the level.
   Nothing is owed from S: the interface, the wire format and the operator are all in place, and the θ=1
   identity is a CI gate.
3. **Quote the floors and the scope beside any arm**: the floors in step 1, the 0.05 %
   deferred-path disclosure from item 3 above, **one cell of 54 020**, and **4 of 7 trait axes
   substituted**.
4. **Rung 3 (F's decadal canopy drift) is still untouched** — item 0-NEW below and item 4(d) further down.

**CI/merge: nothing outstanding.** Work sha **`c74b6ec9`**, merged to `main` as **`21bfa162`** (+ the
changelog collation `913c87f1`). Branch CI green on the required jobs — `test (lts)` success, `test (1)`
success, `format` success, `test (macOS, lts)` success; `test (pre)` red for the usual unrelated
Julia-prerelease churn (`continue-on-error`, do not chase it). The `changelog` gate on `main` is green (the
fragment was collated inside the merge `flock`). `python`/`docs` did not run and could not (no `python/`,
no `docs/src/**`).

### 0-PREV3. ✅ DONE 2026-08-11 (session 8) — S's PORTED HAZARD REPRODUCES THE C **EXACTLY**, AND THE
### RENDEZVOUS'S ONE-YEAR LAG INVERTS THE TRAIT SELECTION ⇒ ARM C IS NOT YET SCORABLE ON TRAITS (ADR 0122)

> ⚠ **PARTLY SUPERSEDED BY ADR 0123 (session 9, the block above).** Item 3's pre-registration — *"arm C
> must not be scored on the trait question from the current rendezvous"* — is **LIFTED**: the rendezvous
> moved behind the growth loop and the lag is gone (ρ = 1.000, differential ratio +1.000). Its step 1
> ("move the rendezvous behind the growth loop") is **done**. Everything else here stands: the θ=1 identity
> is still exact and still a CI gate, and the mechanism in item 3 is why the move was necessary. The
> baseline dump named in item 4 (`M_rung2rec_v4b_dump`) is **superseded by `M_rung2rec_v5_dump`**.

**Start here. S has replied (the INBOUND blocks at the top of this file: ADR 0117 + the 0118 amendment +
the owner steer). Step 1 of the previous handoff — "check whether line S has replied" — is done, and its
free identity gate has been run.**

**1. THE PORT IS AN IDENTITY, NOT AN AGREEMENT — this was the one thing owed before any arm-C number.**
`src/trait_mortality.jl` has **no call site anywhere** (guardrail 4 ships it inert) and had never been
scored against the C on real per-individual state; the existing S test gates its *parameter table*, not
its arithmetic. New `scripts/diagnose_rung2_hazard_identity.jl` scores it against the C's own
`mortality_tree_ind` on **all 9 951 tree-patch-years** of the recorded dump (cell 42490, 25 patches,
2000–2019, PFT ids 1/2/3/4/5/6 = 631/275/7 370/1 231/401/43):

| gated | records | exceedances | max rel Δ |
|---|---|---|---|
| `mort_age` | 9 951 | 0 | 5.0e-16 |
| `mort_temp` | 9 951 | 0 | 1.7e-16 |
| `mort_water` | 9 951 | 0 | 2.2e-16 |
| `mort_npp` | 9 951 | 0 | 1.6e-15 |
| **`mortality_hazard.total`** | **9 951** | **0** | **1.6e-15** |

Both hard kills classified correctly (175 `bm_inc_counter ≥ 5`, 195 ghost-tree = 3.7 %). ⇒ **ADR 0049's
θ = 1 claim is measured, not asserted**, and **ADR 0049 item 4 is retired** — inside the harness both
stress integrals are exact, so the operator ran complete for the first time. **Now a CI gate:**
`test/testitems/m_rung2_hazard_identity_tests.jl` + `references/M_rung2_hazard_identity.csv` (333 records,
61 hard kills, 6 PFT ids), so the port cannot regress against C truth without a red check.

**2. It needed a schema change, and the reason is the generalisable bit.** `patches/lpjmlfit_rung2_hook_v4.patch`
(supersedes v3) publishes two write-only `Pfttree` fields, `bm_delta` + `leafarea_real`. The rendezvous is
the `pre` phase at the **top** of the annual block, but the C's hazard runs **after** `turnover_tree` and
`allocation_tree` — which splits the four: `mort_age`/`mort_water`/`mort_temp` have every input present
unchanged at the rendezvous (`water_stress`/`temp_stress` differ in **0 of 9 951** records `pre` vs `mort`),
while `mort_npp` needs post-allocation `bm_delta`/`leafarea_real`. **Do not try to reconstruct `bm_delta`:**
only the two sapwood turnover terms are recoverable (= Δ`heartwood_c`, exact, which also pins
`turnover.sapwood = 0.04`); `turn.leaf`/`turn.root` are daily accumulators, `isphen` is not dumped, and
`turnover_tree` *mutates* `bm_inc.carbon` before allocation mutates it again. **`mort_npp` is not an
arbitrary fourth — `mort_max(wooddens)` enters ONLY through it, so it is the entire trait channel.**
Both fields are initialised in `new_tree.c` **and** `fread_tree.c` (unlike the `mort_*` siblings) because
the external demography **reads** them; the restart format is unchanged (field-by-field serialization).

**3. ⚠ THE FINDING THAT DECIDES ARM C — the rendezvous is one year stale, and for the trait question that
inverts the answer.** Live, the `pre` roster carries **last year's** `bm_delta`/`leafarea_real`/
`bm_inc_counter`. Per-tree **ordering** survives it (per-patch-year Spearman ρ vs the C's own `mort_prob`:
median **0.900**, p05 0.467). The trait statistic does not — one-year wood-density selection differential
(hazard-weighted mean minus the stand mean; positive = denser wood dies more, sign agrees with ADR 0046 §3):

| hazard basis | differential | ratio to the C |
|---|---|---|
| the C itself | **+17 729** | 1.000 |
| **the lagged rendezvous = arm C as it would run today** | **−14 528** | **−0.819 ⚠ OPPOSITE SIGN** |
| … hard kills suppressed | −14 528 | −0.819 ⚠ (not the hard kills) |
| … **only** `bm_delta`/`leafarea` lagged | **+17 750** | **+1.001 (harmless)** |
| … **only** `bm_inc_counter` lagged | −9 967 | −0.562 ⚠ **← the culprit** |

Mechanism: the counter **multiplies** `mort_npp` and `mort_water` by `(1+counter)`
(`mortality_tree_ind.c:71-81` updates it from **this** year's `bm_delta` sign, so `pre` holds the previous
value in **21.8 %** of records), so misdating it re-weights exactly the trees the differential measures.
**This is the harness's rendezvous POINT — not S's operator, and not the emulator** (standalone, the fast
core grows the trees before the demography runs, so the counter is current).
⇒ **PRE-REGISTERED: arm C must not be scored on the trait question from the current rendezvous.** Counts
and ordering remain readable.

**4. Gates run, all green.** Rebuild equality after **each of two** rebuilds against the v3 build's matched
single-cell run (cell 42490, `--ntasks=1`, same config ⇒ the ADR-0041 control holds): **110 decoded
quantities identical, 0 differ**, `ind` + `globalflux` byte-for-byte. Baseline re-recorded (mandatory on a
schema change) → **`/p/tmp/jamirp/M_rung2/M_rung2rec_v4b_dump`**. **ADR 0121's replay floor survives:**
`none` **1.000**, `kills` **1.000 exact, no year differs**, both arms *identical in every initialised
column* and agreeing in all 1 500 cell-state patch-years. ⚠ Before the initialisers of item 2 were added,
`diagnose_rung2_dump_equality.py` returned a **false FAIL** on those exact arms (695–705 `pre` + 259–317
`post` records of "DIFFERENT model state") — a new dump column the harness feeds to an operator must be
initialised on both creation paths.

▶ **WHAT TO DO NEXT ON RUNG 2 — in order.**

1. **Move the rendezvous behind the growth loop.** This is the scoped C change that removes the lag and
   makes item 1's identity the *live* basis instead of an offline one. In `annual_tree`, with the apply
   hook on, return "alive" for every non-forced tree and record its current-year state; after the
   `foreachpft` loop and **before** the `mort` dump, do the rendezvous with the complete current-year
   roster and apply the kill set there — `litter_update` and the `mort_tree` counter move with it. Gate it
   behind the apply hook so the stock binary is untouched, and **prove it with `MODE=none` still
   reproducing exactly**. Re-record afterwards (schema/timing change ⇒ new reference basis).
2. **Then run arm C** with S's two arms in one wire format: **C0** `f_i = ρ` for every tree (the shipped
   uniform thinning = the no-selection null) and **C1** the tilted `f_i = (1−mort_i)^θ`. **Print θ beside
   the result** — S's item 6.i: at Hainich θ median was 8.5e-12 with θ > 0.5 in only 18 of 132 thinning
   years, so a null C1 − C0 may mean the count model gave the selection no room. And per ADR 0118 §3,
   test the per-PFT **gradient SHAPE** against `references/S_age_wooddens_gradient.csv` (including the
   non-monotone ids 0 and 3), not just the level.
3. **Quote the floor beside any arm**: `kills` 1.000, `recruits` 0.907, `both` 1.367 — **one cell of
   54 020**, **4 of 7 trait axes substituted**.
4. **Rung 3 (F's decadal canopy drift) is still untouched** — item 0-NEW below and item 4(d) further down.

**CI/merge:** the diff touches `test/**` and `.jl`, so **`CI` (4 Julia jobs) and `format` DO run** — unlike
the last three sessions' prose-only commits. `python`/`docs` do not (no `python/`, no `docs/src/**`).

### 0-PREV2. ✅ DONE 2026-08-11 (session 7) — ADR 0120's OPEN QUESTION IS CLOSED, AND THE ANSWER RETIRES
### THE REPLAY FLOOR: THE MORTALITY HALF OF THE INTERFACE NOW REPLAYS **EXACTLY** (ADR 0121)

**Start here. Read this before quoting ANY rung-2 replay number — ADR 0120 §5's `kills` 1.37× and `both`
1.30× are superseded and must not be quoted.** Everything else in ADR 0120 (the four gates, the interface
design, the uninitialised-memory findings) stands.

**The experiment the previous handoff pre-registered was run, and it refuted BOTH branches it offered.**
The `P` record now dumps the three channels of cell-level state no per-tree record can carry — the per-cell
RAND48 `seed`, `gasdev_iset` (the parity of `gasdev()`'s **process-global** spare-deviate cache; normals
are drawn in pairs and the spare comes from a file-local static, so this is not even per-cell), and
seedbank content checksums `sb_*`. At the divergence onset (**2002, patch 2**) the `pre` phase is
**identical in every one of them plus the 25-tree roster**, and the `post` phase of that same patch-year
differs in the stream and has one fewer tree alive. ⇒ **the divergence is created INSIDE the patch-year:
not an inherited stream offset, not a drifted seedbank.** The C's audit localised it: `n_kill_c = 2` (the
hazards wanted two deaths) vs `n_kill_applied = 3` (the list held three), `n_forced_dead = 0`.

▶ **THE CAUSE — `isdead` has more than one author, and one of them is DOWNSTREAM of the hook.** The
harness derived kills as *"any `post` row with `isdead == 1`"*, but `fire_tree_ind.c:33` also sets it, from
`firepft` at `annual_natural.c:129-135`, **after** the decision point. Replaying fire's victims is wrong
twice over: it claims a death the narrow interface does not own, **and it moves the per-cell random
stream**, because `if(!tree->isdead && erand48(cell->seed) < ...)` draws **only for trees not already
dead** — pre-killing fire's victim changes how many draws fire consumes, and fire then kills a different
tree. One short-circuited `&&` produces both symptoms.

▶ **THE FIX — a third dump phase, `mort`**, written after the demographic hazards and **before fire**;
kills are read there, recruits still from `post`. **Corrected replay floor** (cell 42490, 25 patches,
2000–2019, terminal stems replay ÷ recorded):

| arm | ADR 0120 (kills off `post`) | **corrected (kills off `mort`)** | first differing year |
|---|---|---|---|
| `none` (null control) | 1.000 | **1.000** | none |
| `kills` | 1.37 | **1.000 — 376 vs 376, EXACT** | **none** |
| `recruits` | 0.91 | **0.907** | 2000 |
| `both` | 1.30 | **1.367** | 2000 |

The `kills` arm is identical to the recorded run in every initialised per-tree column **and** every
cell-state column across all 1 500 patch-year records (20 yr × 25 patches × 3 phases). **So a substituted
mortality operator can now be credited with any difference it makes — the transport contributes none.** A
substituted establishment operator still cannot be credited below **0.907**, and that floor is structural,
not a defect (the C's Poisson + inheritance draws are skipped, 4 of 7 trait axes substituted).

⚠ **ADR 0120's "naive ID replay is upward-biased by construction" is much NARROWER than stated.** It bites
only once the *other* half has already parted the trajectory: `recruits` alone is 0.907, and adding the
exactly-faithful kills half gives 1.367, because recorded kill IDs stop matching live trees and go
unserved, so the stand under-thins. With only kills substituted the replay is exact.

⚠ **THE TRANSFERABLE LESSON, and it is about the control: a NULL CONTROL VALIDATES THE TRANSPORT, NOT THE
PAYLOAD.** `MODE=none` defers both halves, so it never serves the kill list — it stayed green throughout
and was cited as the thing "that makes the replay numbers readable". It did make them readable; they were
just measuring the wrong kill list. **Green null control + diverging arm ⇒ suspect what you are FEEDING
the interface before you suspect the interface.**

⚠ **A THIRD uninitialised field found: `cell->treelen_old` / `treelist_old`.** Sole writer is
`getsapling.c:57-58` behind `if(config->isequal)`, and `isequalcoord` is TRUE only when every cell in the
run shares identical coordinates (hardwired FALSE for `nall == 1`) ⇒ dead branch, **`mergesapling()` has no
caller anywhere in `src/`**, field is garbage (read 29 458 000 against a `treelen` of 19 650). Deliberately
NOT dumped. Generalisable: before dumping any C field, find its writer and confirm the writer's guard is
live under `individual=true`.

**Mechanics, all three rebuilds gated** (139 decoded quantities + `globalflux` identical, 0 differ, every
time): patch **`patches/lpjmlfit_rung2_hook_v3.patch`** (supersedes v2, kept for provenance); new scorer
`scripts/diagnose_rung2_cellstate_equality.py`; **`MODE=record`** added to
`scripts/run_rung2_replay_arm.sh` — **a rebuild that changes the dump schema invalidates the recorded
baseline every arm is scored against, so re-record before re-running an arm.** Baseline dump now
`/p/tmp/jamirp/M_rung2/M_rung2rec_v3_dump`. Full record: ADR 0121. Skill `lpjmlfit-cbinary` carries the
fire trap, the three phases and the corrected floor.

**CI/merge: nothing outstanding.** Work sha `fde5d660`, merged to `main` as **`414f283a`**. The diff touches
no `.jl`, no `python/`, no `docs/src/**` and no `src/**`, so per ADR 0090's path filters **no Julia, format,
docs or python gate runs on it at all** — the only check that fires is `changelog` on `main`, and it is
**green** (the fragment was collated inside the merge `flock`). Do not wait for a verdict that cannot arrive.

▶ **WHAT TO DO NEXT ON RUNG 2 — in order.**

1. **Check whether line S has replied** (`lines/S/STATE.md`, the ▶ INBOUND block from 2026-08-10 with the
   2026-08-11 update). **Still unanswered as of this session.** Nothing is owed from M — the C side is
   complete and accepts all three shapes, because the harness normalises whatever S returns into a kill
   set before the C sees it. One thing to carry back when next touching that block: **the mortality half
   of the interface is now exact**, so whatever S returns for "who dies" will be measured with zero
   transport error, which makes option (a) (S returns the kill set) or (c) (S returns per-individual
   survival probabilities, M draws) cleanly scorable. Option (b) remains awkward for the reason already
   recorded (the current year's hazards do not exist at the rendezvous).
2. **When an emulator arm does run, quote the floor beside it** — kills 1.000, recruits 0.907, both 1.367,
   **one cell of 54 020** — and say "4 of 7 trait axes substituted".
3. **The `recruits` floor of 0.907 is worth one bounded look, but only if the recruit half is on the
   critical path.** It is structural (skipped Poisson + inheritance draws), so it cannot be removed the way
   the kills defect was; it could only be *reduced* by widening the wire format to carry the three
   unsubstituted axes. Do not start this before S answers, because S's answer decides whether it matters.
4. **Rung 3 (F's decadal canopy drift) is untouched by this session** and remains the other open M item —
   item 0-NEW below and item 4(d) further down.

### 0-PREV. ✅ DONE 2026-08-11 (session 6) — RUNG 2's SUBSTITUTION HALF IS BUILT AND GATED (ADR 0120)

**Start here. The C now ACCEPTS a replacement demography, and the harness has been measured against the
C's own answer. Both steps of the previous handoff's "what to do next on rung 2" are done: step 1 (raise
the entry point with line S) was done last session and S has NOT yet replied; step 2 (write the C
read-back) is this session's work and did not need S's answer.**

`export LPJ_RUNG2_APPLY_DIR=<dir>` turns on a second opt-in hook (`include/rung2apply.h` +
`src/lpj/rung2_apply.c`, call sites in `annual_natural.c` / `annual_tree.c` / `establishmentpft_ind.c`).
Per patch-year the C writes the `pre` roster as a request, blocks, and reads back
`K <pft_id> <treeidx>` kills plus `R <pft_id> <sla> <wooddens> <D95max> <minwscal>` recruits, with
`MORT_C` / `ESTAB_C` to defer either half. Full mechanics + the five traps: the **`lpjmlfit-cbinary`**
skill. Patch: **`patches/lpjmlfit_rung2_hook_v2.patch`** (supersedes the ADR-0061 one, which is kept for
provenance).

**Four gates, all passed** (cell 42490, 25 patches, 2000–2019, `--ntasks=1`):

- **A — the rebuild did not move the physics.** Both env vars unset ⇒ **139 decoded quantities +
  `globalflux` identical, 0 differ**, against the ADR-0061 binary. Run after **each** of the two
  rebuilds this session made. `bin/lpjml` was rebuilt again; `bin/lpjml_rung2` is the ADR-0061 build.
- **B — the observation dump is unchanged** by the shared-writer refactor: identical in every
  initialised column over 20 259 records, from **two independent runs**.
- **C — the null control.** Rendezvous active for all 500 patch-years with both halves deferred:
  **identical in every initialised column over 20 years.** This is what proves the machinery itself
  perturbs nothing, and it is why the replay numbers below can be read at all. **Always run
  `MODE=none` first.**
- **D — replay identity** (below). Cost of the whole rendezvous: 10 s vs 7 s.

▶ **THE RESULT — ⚠ SUPERSEDED BY ADR 0121, DO NOT QUOTE THE RATIOS BELOW.** The kill set fed to these arms
included fire's victims, which both mis-attributed deaths to the interface and moved the random stream; on
the corrected `mort`-phase basis `kills` is **exact (1.000)**, `recruits` 0.907, `both` 1.367. The table is
kept for the record of what was measured. One cell of 54 020 either way (guardrail 6):

| arm | 2000 roster | first differing year | 2019 stems, replay ÷ recorded |
|---|---|---|---|
| `none` | identical | — | **1.000** |
| `kills` | **identical** (583 = 583, all 31 + all 20 recorded kills applied) | 2002 | **1.37** |
| `recruits` | differs (583 vs 586) | 2000 | **0.91** |
| `both` | 583 = 583, keys differ (benign, see ADR) | 2000 | **1.30** |

**Do NOT read 1.30–1.37 as a property of the interface** — naive replay of *identifiers* is
upward-biased by construction: once trajectories part, some recorded kills name trees that no longer
exist and cannot be applied, while the recruit list replays in full. No real emulator arm replays IDs.

⚠ **TWO THINGS ANY RUNG-2 RESULT MUST SAY.** (1) A recruit has **seven** sampled trait axes
(`sla`, `wooddens`, `D95max`, `minwscal`, `emax`, `k_root`, `beta_2`, plus leaf `longevity` derived from
`sla`); Component S supplies four, so the arm substitutes **4 of 7** and `emax`/`k_root`/`beta_2` stay on
the C's own draw. (2) Quote the replay floor beside any fidelity number.

⚠ **TWO COLUMNS OF THE ROSTER DUMP ARE UNINITIALISED MEMORY — this corrects ADR 0061.** `sapwood_old` is
a **dead field** (declared in `include/tree.h`, never written or read anywhere in LPJmL-FIT, not zeroed
by `new_tree`) — garbage at both phases in every year. And `mort_*` are garbage for any tree not yet
through `mortality_tree_ind`, **including every recruit at the `post` of its own establishment year** —
so ADR 0061's "valid only at `post`" holds only for trees already alive that year. **Neither was
findable by ADR 0061's gate**, because the dump and `ind` read the *same struct memory* and agree on the
garbage too: a consistency check between two readers of one buffer cannot detect uninitialised memory,
only two independent **runs** can. Use `scripts/diagnose_rung2_dump_equality.py`.

▶ **WHAT TO DO NEXT ON RUNG 2 — in order.**

1. ✅ **CLOSED 2026-08-11 by ADR 0121 — see item 0-NEWEST at the top. It was neither of the two suspects
   named below: the kill set was including fire's victims.** Original text kept for the record.
   In the `kills` arm the state at
   the end of 2001 is identical to the recorded run in every dumped column, yet in 2002 the C's own
   hazard draw wants **33** kills where the record has **29**. Gate C rules out the rendezvous, so
   either the per-cell RAND48 stream or cell-level state *outside* the dump — most likely the top-AGB
   **seedbank** (`cell->treelist`), which is rebuilt yearly and appears in no roster record — has moved.
   **Decisive and cheap: add the cell's RAND48 seed and `treelen` to the `P` record and re-run
   `MODE=kills`.** If the seeds agree at the 2002 `pre` and the answer still differs, it is state, not
   randomness; if they disagree, walk back to the first year they do. ADR 0120 §5. Do not guess.
2. **Then check whether line S has replied** (`lines/S/STATE.md`; the ▶ INBOUND block from 2026-08-10 is
   still there, unanswered as of this session). One thing this session learned changes the menu and is
   being carried back to S: **option (b) — "rank or draw on the C's own `mort_prob`" — is now known to
   be awkward**, because at the rendezvous the *current* year's hazards have not been computed yet, so
   such a rule would rank on a one-year-stale hazard, or need the kill decision deferred until after
   `mortality_tree_ind`, which `litter_update`'s inline call makes intrusive. That is an argument for
   option (a) or (c). **Nothing is owed from M until S replies** — the C side is complete and accepts
   all three shapes, because the harness normalises whatever S returns into a kill set before the C
   ever sees it.
3. **Rung 3 (F's decadal canopy drift) is untouched by this session** and remains the other open M item
   — the narrowed version is item 0-NEW below and item 4(d) further down.

### 0-NEW. ✅ DONE 2026-08-10 (session 5) — RUNG 2's OBSERVATION HALF IS BUILT AND GATED (ADR 0061)

**Rung 2's first half. Its second half is now done too — see the block immediately above.**

An **opt-in demography hook** now exists in the C, activated by the environment variable
`LPJ_RUNG2_DIR`. It dumps each patch's tree roster at the **top** of the annual demography block (`pre`)
and again **after establishment** (`post`). Patch: `patches/lpjmlfit_rung2_demography_hook.patch`
(`include/rung2hook.h` + `src/lpj/rung2_hook.c` + two call sites in `annual_natural.c`). Full mechanics
and the five gotchas are in the **`lpjmlfit-cbinary`** skill — read it before touching this.

- **The feasibility question the substitution half depends on is ANSWERED: yes.** Everything the narrow
  interface needs is live at the hook point — `water_stress`, `temp_stress`, `bm_inc_counter` (the
  accumulators three of the four death rates read), plus `bm_inc`, `nind` and all seven carbon pools.
  **None of those is in the `ind` output**, so this is not a re-derivation of an existing table.
- **Gate A — the rebuild did not move the physics.** `bin/lpjml` was rebuilt (in place; the Jul-21 build
  is gone) and with `LPJ_RUNG2_DIR` unset it is **numerically identical**: 138 decoded NetCDF variables +
  `globalflux` unchanged on a matched cell-42490 / 2000–2019 / `--ntasks=1` run. `cmp` calls 20 of 21
  outputs different (ADR 0043's `history` timestamp) — use
  `scripts/diagnose_cbinary_rebuild_equality.py`, **after every future rebuild**.
- **Gate B — the dump says what the C says.** Same run emitting both: identical tree sets (**5 465 trees,
  0 rows on either side alone**), **all 21 shared columns to ≤5.0e-6** (the `%g` floor), hazard components
  included. `scripts/diagnose_rung2_roster_vs_ind.py`. Accounting closes: `post`-alive of year *N* ==
  `pre` of year *N+1* in all 19 transitions; **recruits enter at `age == 0`**.
- ⚠ **`mort_prob`/`mort_npp`/`mort_age`/`mort_water`/`mort_temp` are valid ONLY at `post`** — at `pre` in
  the first year after a restart they are uninitialised memory (a `6.9e-310` denormal was observed).
- **Cost is nil** — 7 s vs 6–7 s, 13.4 MB for 20 yr × 25 patches. The plan's "per-year file I/O is free at
  a handful of cells" is now measured, not assumed.
- **The generalisable mistake, already in `MEMORY.md`:** the first run of gate B printed `0.000e+00` for
  **nine** columns because the join kept one column per colliding name and nine checks compared a column
  **against itself**. Caught only because a tenth colliding column had a unit conversion. **An exact zero
  on a float comparison of two independently written representations is an aliasing bug, not agreement.**

▶ **WHAT TO DO NEXT ON RUNG 2 — the substitution half.** The C now *offers* the roster; it does not yet
*accept* a replacement. Two steps:

1. ✅ **DONE 2026-08-10 — the S → M integration point is RAISED** as an ▶ INBOUND block at the head of
   `lines/S/STATE.md` (ADR 0056's lesson: an ADR alone is not a channel), with a concrete proposal rather
   than an open question: *given the `pre` roster, return the `treeidx` set that dies and the recruits
   (`pft_id` + `SLA`/`Wooddens`/`D95max`/`minwscal`) that appear.* It names the ONE thing that is genuinely
   S's to decide — the shipped demography predicts a per-patch **count**, not which individual dies, and
   turning a count into a kill set is itself a demographic operator M must not invent — and offers three
   options: (a) S returns the kill set, (b) S returns a target count plus a *stated* victim rule (e.g. rank
   or draw on the C's own `mort_prob`, which the dump carries), (c) S returns per-individual survival
   probabilities and M draws. (b) is cheapest but borrows the C's hazard *ordering*, which makes the arm
   partly a C arm — that must be said in whatever the rung-2 result claims. **Nothing is owed from M until
   S replies; check `lines/S/STATE.md`.** The ADR-0060 inbound is re-placed in the same file, above this one.
   ⚠ Do not start the read-back's *field list* on option (b) before S answers — options (a) and (c) change it.
2. **Write the C read-back while waiting** — it does not depend on S's answer, only its field list does.
   Where: kills go where `annual_tree` sets `isdead` (`src/tree/annual_tree.c:31-38`), recruits where
   `establishmentpft_ind` calls `addpft` + `establishment_tree_ind` (`:100-115`, `:124-140`); overriding a
   recruit's traits after `addpft` is the cheap route, since `establishment_tree_ind` builds the pools from
   them. Keep the same env-var opt-in so the stock path stays inert. Rendezvous: the harness runs few
   cells, so a file-per-year with a spin-wait beats FIFOs on debuggability.

**Rung 3 (F's decadal canopy drift) is untouched by this session** and remains the other open M item — the
previous handoff's narrowed version of it is item 4(d) further down.

#### YOUR ASSIGNMENT — **rungs 2, 3, 4** (then 5b and 5c). **You may start rung 2 NOW, in parallel with S's rung 1.**

**Rung 2 — S + the REAL C fast part, closed annual loop.** The harness build does not depend on rung 1's
answer, only its interpretation does, so it is not blocked.

* **NARROW INTERFACE FIRST — this is the owner-delegated recommendation (ADR 0093 §Owner answers).** Replace
  **only who dies and who establishes.** Leave turnover, allocation and growth to the C. Reason: it keeps the
  C's internal per-tree accumulators intact — the running water stress and the growth-failure counter — which
  **three of the four death rates read** (`waterstress_tree.c:31-38`, `mortality_tree_ind.c:66-96`) and which
  the emulator does not currently produce. It also halves the interface surface, so a failure is attributable.
  Widen later, one function at a time, each its own experiment.
* **The hook point.** The whole demography is one loop, `src/lpj/annual_natural.c:55-232` in
  `/home/jamirp/lpjml56fit`: `annualpft` at :73, `light` at :118 (**dead** under `individual=true`), fire at
  :121-135, `establishmentpft_ind` at :145. Add an **opt-in config flag** that dumps the patch roster +
  accumulated per-tree fluxes at the top and reads a replacement roster at the bottom. Mechanics precedent:
  `patches/lpjmlfit_daily_grass_gpp.patch` + rebuild (skill `lpjmlfit-cbinary`). Keep the stock binary
  byte-identical. Per-year file I/O is free at a handful of cells.
* **This is a THROWAWAY test harness, not a deliverable.** Build it cheap. Its only job: is the defect in S,
  in F, or in the loop? Fallbacks if it stalls — restart-file year-stepping (needs a writer for
  `fwritecell.c` → `fwritestandlist` → `fwritestand` → `fwritepftlist`), or `ccall` into a shared-library
  LPJmL (**not worth it**: global state, MPI, its own I/O).

**Rung 3 — F alone, on the C's own canopy.** Partly exists (`fdiff-validate`). The open item is the **decadal
canopy drift**: over 2010–2019 F's leaf cover moves **1.56×** where the C's moves 0.90× (boreal), 1.27 vs 1.00
(Hainich), **0.71 vs 1.23** (Sahel). Score **year-matched over the decade** and read the ratio's SHAPE — a
10-year-mean ratio hides drift. Run `fdiff-validate`'s four mandatory basis checks first.

**Rung 4 — coupled.** Only after 1–3 are clean, and report the decomposition explicitly:
residual = (rung 1) ⊕ (rung 3) ⊕ (the loop). **If the three do not add up, the loop is amplifying** — that is
a result and deserves its own ADR from your block (0120–0139, unopened).

**Later, yours:** rung **5b** one shared soil column per cell — licensed by measurement (between-patch CV of
patch-mean `wscal` is median **0.0126** / p90 0.0667 over 41 587 cells) but **share the soil column, NEVER the
canopy** (mean-field light is wrong by −31 % at 5 m, −47 % at 20 m). This is the step that removes the fixed
cost capping everything else at ~3×. **E must review it** — it touches E's ground-heat column. And rung **5c**
25 → 8–12 patches in `scripts/run_coupled_biomes.jl` (sd cost ×1.15–1.43; `npatch` is numerical, <0.15 % on
every cell-mean at 50 vs 25).

**Integration points you own one side of:** S → M (the demography entry point) · **M → O: the hand-over of
`src/fdiff.jl` for performance work after rung 4** — O must not edit it before then (CLAUDE.md §9 Gap 1) ·
M → E (the shared soil column).

---

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
zero where the original rises, and — separately — the source model itself is deliberately run at
**constant CO2** (ADR 0004/0107), which the emulator correctly inherits. **Work that improves present-day agreement is not progress
toward this criterion unless it also opens a response channel.** Plan accordingly.

⚠ **CO2 — STANDING RULE, DO NOT RE-LITIGATE (ADR 0107; the owner has had to correct this repeatedly).** The
emulator **does not see CO2 and must not respond to it**. It responds to **climate**, and the SSP scenarios
already carry the CO2-driven climate signal. The source model runs constant CO2 **on purpose** because its
own CO2 response is wrong (no nitrogen limitation ⇒ unbounded fertilization, ADR 0004). So the emulator
having no CO2 response is **faithfulness, not a gap** — never raise a CO2 feature, varying-CO2 training
rows, or a new model run for CO2, and never list it as a defect or a missing capability.

⚠ One clause needed a decision and carries a stated default, not the owner's words: the original model is
stochastic and its own two runs differ by **29 % of the mean** for the per-patch count in a low-density cell,
so a literal 10 % is unmeetable there by ANY emulator. Default in use: tolerance =
**max(10 %, the original's own two-run spread for that quantity in that cell)**. Full record: ADR 0106.

### 0a. 📥 TWO INBOUND ITEMS FROM LINE S, 2026-08-06 (ADR 0105) — full blocks further down this file

1. ⚠ **PLAIN LANGUAGE TO THE OWNER — your checkout is MISSING the rule (`CLAUDE.md` §0a).** The owner
   said on 2026-08-06 that line M is still writing to them in acronyms and code names. It is not a
   choice you made: `line/M` had not rebased onto the commit that added §0a, so **your working copy of
   `CLAUDE.md` does not contain it**. It is now also in `~/.claude/CLAUDE.md` (outside git, loads in
   every worktree regardless of branch), so you have it either way. **No ADR numbers, no phase or
   milestone codes, no line letters, no internal names as explanations in anything the owner reads.**
   Findings, numbers and caveats stay; the labels go. ADRs/STATE/code comments keep the shorthand.
2. **The anchor ACTION you were asked to run is CLOSED — do not run it, do not flip anything.** It was
   run on your patch ensemble and the criterion failed at every setting. **And a NEW integration point
   is raised for you:** the coupled tree-count residual is F's canopy diverging from the C's, which is
   your paths, with the measurements attached. Both blocks are further down under "▶ NEW INTEGRATION
   POINT RAISED BY LINE S". ⚠ Two of your published numbers invert there (ADR 0054's teacher-forcing
   59–72 %, and `semiarid_sahel` being too dense) — worth reading before you quote either.
   **↳ ✅ THE CANOPY HALF OF THIS IS WORKED — see item 0-NEW immediately below (ADR 0060).** S's attribution
   survives, but the FPC numbers on both sides came from the wrong one of the C's two FPC outputs, and a
   third published claim (ADR 0053 finding 4) is withdrawn as a result. Read 0-NEW before quoting any FPC.

### 0-NEW. ✅ DONE 2026-08-06 (session 4) — the canopy attribution S handed over is ANSWERED, and it was a
### reference-basis error: the oracle scored the wrong one of the C's TWO FPC outputs (ADR 0060)

Item 2b below is **worked, not open**. Nothing in `src/` changed; no baseline moved.

- **The C writes two FPCs from the same individuals.** `a_fpc` (`FPC`, `annual_natural.c:209`) is the
  patch-mean **sum of individual crown covers** (`fpc_tree.c:28`). `a_fpc_stand` (`FPC_STAND`, `:218,248`)
  accumulates per-PFT **leaf area** and applies ONE Beer–Lambert saturation over the whole patch. Different
  functional forms; **1.5–2.3× apart** in the same cell-year. `src/allometry.jl::fpc` implements the crown
  form ⇒ `a_fpc` is comparable. The extractor used `a_fpc_stand` and the probe header called it "CLEAN",
  citing `fpc_tree.c:28` — the right C line for the wrong file. `a_fpc.nc` was in all five run dirs, unread.
- **ADR 0053 finding 4 is WITHDRAWN and item 4(d) below with it.** Not "F under-predicts FPC in all five
  cells (0.31–0.72×)" but: boreal **1.32**, Hainich **1.18**, mediterranean **1.47**, Amazon **1.05**,
  `semiarid_sahel` **0.54**. Sign flips in four of five.
- **F's canopy RECONSTRUCTION is faithful and is eliminated** — new PART 6 column: F's crown cover at
  **t = 0** over the crown cover of the stems it was handed = **1.00–1.04 in all five cells**.
- **Never read an FPC ratio against 1.0** — the `ind` writer emits only stems > 5 m, so F's stand lacks
  **29 %** of boreal's and the Sahel's crown cover (`>5m_frac` 0.71; 0.95–1.02 elsewhere). Printed per cell.
- ⚠ **This arm cannot convict F's growth by itself:** under `slow = nothing` the fast core has **no
  mortality and no tree establishment** (only grass, `fast.jl:272`, `n_est = 0` here), so a monotone FPC rise
  is partly expected. Two things survive: the **Sahel shrinks 0.71 → 0.47** with nothing able to remove
  cover but F's own allocation (fourth independent symptom of ADR 0052's dry-cell bias, same cell), and S's
  **coupled** arm drifts 1.56× vs the C's 0.90× where this arm gives 1.65× ⇒ mortality is a small part.
  **Quote a growth-divergence number from the coupled arm, never from this one.**
- **S's ADR 0105 attribution SURVIVES** — a same-basis ratio over time mostly cancels the form difference
  (the C's own crown drift is −10.9 / −2.6 / −22.9 / **+25.4** / −11.0 %). The *level* claim inside it does
  not. Both bases now print side by side in `biome_slow_oracle_probe.jl` REPORT 5.
- Committed tables gain `fpc_tree_crown` (+ `fpc_grass_crown` monthly), **appended last, every pre-existing
  value byte-identical, verified row-by-row** ⇒ guardrail 4 untouched. Jobs 1718928 / 1718932 / **1718979**.
- **CI:** the diff touches `test/testitems/references/**` (which is under `test/**`) and two `.jl` scripts,
  so it triggers **`format` + all four Julia jobs** — not `format` alone. `docs` and `python` do not run
  (`docs/decisions/**` and `scripts/*.py` are outside their path filters).

▶ **WHAT TO DO NEXT ON THIS ITEM (the narrowed F-side item, and it is the highest-value one left).** The
remaining defect is F's **growth**, not its canopy reconstruction and not a uniform sparseness. Two steps,
in order, and neither needs anything from another line:

1. **Score the growth divergence on the COUPLED arm, not the kernel-isolation arm.** `slow = nothing` has no
   mortality, so it cannot separate "F grows too fast" from "nothing is killing trees". The coupled arm
   already exists (`biome_slow_oracle_probe.jl`, now printing both FPC bases) — read F's `fpc` trajectory
   against `fpc_tree_crown` there and quote *that*.
2. **Then take `semiarid_sahel` first.** It is the only cell the kernel arm convicts on its own (crown cover
   falls 0.71 → 0.47 with nothing able to remove cover but F's own allocation) and it is now the **fourth**
   independent symptom of the same dry-cell root-zone bias in the same cell — with items 4(a) (ET 11–35 %
   high while F carries no grass transpiration) and 4(c) already pointing at the demand side. Fixing the
   demand side may close all four; measure before assuming. Run `residual-diagnosis` first.

### 0. ✅ DONE 2026-08-06 (session 3) — the water-stress DEFAULT is flipped (ADR 0059)

Line S's explicit GO ("yours to land, unilaterally, S's side is already in") is **acted on**. The flag
CLAUDE.md's own guardrail-4 corollary names as "a defect on a timer" is off the timer.

- **It is a ONE-CELL change.** A full suite with *only* the default flipped failed **3 assertions out of
  111 237** — the opt-in guarantee itself and `semiarid_sahel`'s two pinned signatures. Four of five cells
  move ≤ 1.2 %. The Sahel's GPP goes **0.386 → 1.367 gC/m²/day (+254 %)** = **0.26× → 0.90×** the C's own
  tree GPP (1.513). Mechanism: the pre-flip expression scored every leaf-off day as fully water-stressed,
  and that number drives the leaf:root allocation — so the cell with the most leaf-off days starved its own
  leaf pool.
- **The cost is in the same cell:** its ET goes 1.19× → **1.26×** the C's. Large carbon gain, ~6 % more of
  ADR 0053's ET overshoot. Quote both halves or neither.
- **What the fix exposed matters more than the fix.** Until now this gate pinned a configuration *no
  published F-vs-C comparison ever ran* — every oracle probe passes the flag explicitly. A default that
  disagrees with the measurement basis is the train/inference-shift hazard in its cheapest form, and it
  survived for weeks because **both halves were individually documented**.
- **Also swept up E's default flip (ADR 0075):** the pin probe hardcoded `enable_two_layer = false` as its
  "default" arm, which stopped being the default the moment E flipped it — ADR 0075 §4's own trap. It now
  takes the package default by omission; stale "the default is off" comments are corrected.
- Suites 1718279 (flip only, the 3 expected failures) and **1718316 (111 238 pass / 0 fail)**; pins
  regenerated by job 1718307; driver on the final configuration 1718317.
- **CI/merge: nothing outstanding.** Work sha `bbdef097` — `format`, `test (lts)`, `test (1)`,
  `test (macOS, lts)` all success. Merged to `main` as **`406d0eb7`**, whose own post-merge run is green on
  `format`, `test (lts)`, `test (1)`, `test (macOS, lts)` **and `docs`** (the gate that never runs on a
  branch — this merge touched `src/**`, so it ran there for the first time). `test (pre)` red for the
  diagnosed prerelease reason (`setindex!(::ScopedValue{Bool}, ::Bool)` at LOAD time); do not chase it.

**⚠ THE CURRENT COUPLED CONFIGURATION, all three by default now:** C-faithful `wscal` (ADR 0059) +
two-layer ground heat (ADR 0075) + the 25-patch ensemble (ADR 0057). `run_coupled_biomes.jl` prints all
three at the top of its output. Nothing needs to be passed explicitly any more; the probes that still pass
flags do so deliberately, so their labels stay true if a default moves again.

**Three items in a row now where the assumed blast radius exceeded the measured one** (ADR 0057's CI cost,
ADR 0058's "moves every baseline", ADR 0059's "physics-wide" flag). The procedure that settles it in one
job is captured in the `julia-test` skill: flip only the default, run the full suite, read the failure list.

### 1. The `n_prev` integration point with line S — ⚠ SUPERSEDED IN PART, do not quote the 59–72 %

> **⚠ CORRECTION, line S / ADR 0105, 2026-08-06.** ADR 0054's headline — teacher-forcing `n_prev` removes
> **59–72 %** of the coupled count error — **INVERTS on the patch-ensemble basis** when scored on the stand
> against the C rather than on `target_history`: forcing is **worse in all five cells** (0.149→0.277,
> 0.086→0.153, 0.180→0.259, 0.349→0.460, 0.029→0.069). It survives neither correction. It was a correct
> measurement on its basis (modal patch, `target_history`) and both parts of that basis were wrong. The
> generalisable half: the free-running ratio update **cancels** the count model's absolute level, and on the
> correct basis that is *protective* — so an intervention that re-introduces the level (the anchor, or
> teacher forcing) makes things worse until the target itself is right. **Run the arm; do not quote the
> number.** The text below is kept for the AC caveat, which is unaffected.

ADR 0054 raised it (item **H** in `lines/S/STATE.md`): the coupled count is an unanchored AR recursion, and
teacher-forcing `s.n_prev` onto the C truth removes **59–72 %** of the count error in all five cells.
**Still true, still S's** (`src/components/slow.jl` is S's exclusive path — do not edit it here). ADR 0056
answered S's anchor criterion: the anchor fires perfectly but does not get the default, and `a` must not be
tuned. What M4 adds, and what must be said when S replies:

- **The recursion is a LEVEL failure, not a memory failure.** Pinning the count-space AR feature changes the
  lag-1 autocorrelation by ≤ **0.135**; the memory lives in F's carbon pools (`slow=nothing` alone carries
  AC 0.454–0.691). So an anchor fixes the drift and should not be expected to change the dynamics.
- **⚠ The anchor arm makes the AC WORSE in two cells** — `tropical_amazon` `n` **0.066** vs a C of 0.501
  (**2.3 between-patch SDs**, the worst number in the whole battery) and `mediterranean_iberia` 1.2 SDs.
  Teacher-forcing removes the emulator's own memory without substituting equivalent memory. **Whatever S
  lands must be scored on the AC as well as the level**, using `scripts/biome_resilience_probe.jl`'s
  `anchor0` arm, which already exists and needs nothing from S to run.
- Nothing is owed from this line until S replies. If S declines, the honest framing for any coupled
  multi-decadal result is unchanged: quote the teacher-forced number alongside the free one.

### 2. ✅ CLOSED BY LINE E — the two-ground-heat-scheme state is gone (ADR 0075)

Read E's reply block below before quoting anything about the ground-heat scheme: it corrects three things
M asserted, including that the flip would move E's own P2 tower gate (it cannot — `solve_seb` never reads
the flag) and that ADR 0074 §6's sub-daily `T_skin` cost applied at the shipped `z1`. **Item (b) — my
"regenerate ADR 0055's fixtures when the default flips" — is NOT required:** E measured the full suite with
only the default flipped and nothing outside `energy_closure_tests.jl` moved, ADR 0055's fixtures included.
What remains is an optional **re-measurement of ADR 0055's published autocorrelation gaps** on the new
scheme, at M's discretion and with its own verdict — not a repair.

### 2b. ✅ WORKED 2026-08-06 by ADR 0060 — read item 0-NEW at the top FIRST. The attribution survives; its
### FPC level numbers do not, because they were read off the wrong one of the C's two FPC outputs.
### (original block kept below for the record)

Full block below under "▶ NEW INTEGRATION POINT RAISED BY LINE S" — read it before quoting any coupled
demography number, because **two of this line's published numbers invert there**: ADR 0054's "teacher
forcing removes 59–72 %" (on the ensemble basis, forcing is *worse* in all five cells) and
`semiarid_sahel` being over-dense (it is **48 % UNDER**-dense). S eliminated its own two candidate causes
by measurement (the exposure bias is empty at −0.0014 stems/patch/yr; the level anchor is net-harmful),
leaving F's canopy drift — `fpc` 1.56× where the C's is 0.90× at boreal, 0.71× vs 1.23× at the Sahel —
which is `src/fdiff.jl` / `src/components/fast.jl`, i.e. this line's. Nothing is blocked on it, and it is
the same defect item 4(d) already names. **ADR 0059 has just changed one input to it** (the Sahel's carbon
is no longer starved), so re-measure that cell before building on S's numbers.

### 2c. The old ground-heat block, kept for its answered-integration-point record

> **📤 ANSWERED BY LINE E, 2026-08-06 — ADR 0075: option 1. `SEBParams.enable_two_layer` now defaults to
> `true`, and item (a) below is CLOSED. The repo runs ONE ground-heat scheme again.**
>
> E flipped it in its own files (`src/components/energy.jl` + `test/testitems/energy_closure_tests.jl`), so no
> hand-over was needed. Guardrail 4 is re-served by the **opt-out**: `enable_two_layer = false` reproduces the
> pre-E7 closure exactly. **`lambda_g` and `tau_soil` are now inert under the default.**
>
> **Three things in the ask turned out to be wrong, and two of them change what M should do next:**
>
> 1. **The pre-registered criterion FAILED — at AU-Rob only** (daily H R² 0.069 → −0.176; the other three
>    improve, DE-Hai 0.035 → 0.645, AU-ASM 0.329 → 0.775, AU-Tum −0.478 → −0.362). E flipped anyway on four
>    grounds published *before* the measurement: ADR 0073 had already excluded that tower from scoring H
>    (`ε_obs` −47.5 W/m²), its two `λ_g` fit targets disagree 13.6×, the fitted `λ_g = 1.0` arm fails there too
>    (−0.172 ⇒ the site does not discriminate the schemes), and its pre-E7 "skill" coexists with a G R² of
>    **−4.02** at 2.4× the observed sd(G). Daily `G` R² improves at **all four** sites, AU-Rob included, and
>    `Rn` moves ≤ 0.005 everywhere. Full reasoning: ADR 0075 §1 — read it before quoting the flip anywhere.
> 2. **▶ ITEM (b) IS NOT REQUIRED FOR A GREEN `main` — measured, not assumed.** The full CI-faithful suite with
>    only the default flipped is **111 227 pass / 3 fail**, and all three failures are E's own re-pinned
>    assertions. **Nothing outside `energy_closure_tests.jl` moves — ADR 0055's fixtures included.** So
>    `resilience_battery_tests.jl` and `rollout_stability_tests.jl` now run the **column** against pre-E7
>    fixtures and still pass, which proves those fixtures do not discriminate the two schemes. What is left for
>    M is therefore a **re-measurement of ADR 0055's *published* AC gaps**, at M's discretion and with its own
>    verdict — not a repair. Those files are M's exclusive path; E did not touch them.
> 3. **The flip does NOT move E's P2 tower gate, and could not have.** `solve_seb` never reads
>    `enable_two_layer` — the scheme lives entirely in `solve!` — so every **stateless** caller is
>    scheme-independent *by construction*, including ADR 0072's committed night-cold assertion (its fixture is
>    a stratified sub-sample no prognostic column can be integrated along). ADR 0058 §5 expected this gate to
>    move; it does not. The night-cold sign is instead restated as a **measurement** in a new stateful gate,
>    where it **deepens** rather than disappearing (−0.95 → −3.17 K at AU-ASM).
>
> **One correction M may be carrying:** ADR 0074 §6's sub-daily `T_skin` cost was measured at `z1 = 0.2 m`,
> which is **not** the shipped default. At the shipped 0.75 m it is larger (AU-Tum 0.773 → 0.547, AU-Rob
> 0.385 → **−0.116**). The **daily** cost — M's operational step — is small and is now pinned per site for the
> first time (0.981 → 0.979, 0.900 → 0.851, 0.858 → 0.793). ADR 0075 §4; cause was a control arm that omitted
> `z_soil1` and silently tracked the package default.
>
> **Nothing is owed from E.** The two remaining E→M asks are unchanged and untouched by this: `theta_soil`
> needs soil moisture through the frozen `FToE`, and the E3 sublimation-λ split needs `fast.jl`.

Declared, not hidden: ADR 0058 §4 lists every site and why. M's driver + `biome_coupled_tests.jl` items 2/3
are on the **two-layer** column; `resilience_battery_tests.jl`, `rollout_stability_tests.jl`'s AC-gap check
and every E-owned gate are on the **default**, because they score against fixtures measured under it
(ADR 0055). Two follow-ups, in order:

a. **E owes a decision on the package default** (ADR 0058 §5, pre-registered pass condition, with M's
   evidence attached: the scheme is free in the coupled loop, removes the 6.4 W/m² sink, does not drift,
   and its measured cost is *sub-daily* `T_skin` while M's step is daily). ✅ **Written into
   `lines/E/STATE.md` as an ▶ INBOUND block** (ADR 0056's lesson applied: an ADR alone is not a channel),
   with three explicit options — E flips it, E hands `energy.jl` + `energy_closure_tests.jl` over for one
   commit, or E declines in an E-block ADR. ⚠ Note E's own STATE said "M lands it" while ADR 0029 makes
   that file E's; the inbound names that conflict rather than assuming either reading. **Nothing further is
   owed from M until E replies** — check `lines/E/STATE.md` and `lines/M/STATE.md` for the answer.
b. **When (and only when) the default flips, regenerate ADR 0055's resilience/rollout fixtures on the new
   scheme** — `scripts/biome_resilience_probe.jl`, ~22 min. That re-pins ADR 0055's *published* AC gaps, so
   it is its own measurement with its own verdict, never a side effect. Q1 says the level effect will be
   ~zero and the effect on H/G real; measure, do not assume.

### 3. M5 — biome-calibrated PFT params + spin-up (the next MILESTONE proper)

**✅ THE PARAMETER HALF IS DONE (ADR 0126, session 12) — see the 0-NEWEST block.** `FDiffFastCore` now takes
per-cohort PFT parameters (`per_pft_params=true` + real `pft_ids`), opt-in and default byte-identical, and
line S's `trait_mortality` prerequisite is satisfied on the F side. What remains under M5 is the **spin-up**
half, plus the two cells ADR 0126 §5 leaves open (boreal's `temp_photos`/`gmin`, mediterranean's phenology).
The paragraph below is the original statement of the problem, kept because its C-side facts are still the
reference.

Today every biome runs **beech ANGIO params** from `par/pft_lpjmlfit.js`. Two things now make this both
more urgent and better-specified:
- **Line S's standing requirement (ADR 0049):** the first M driver that enables `trait_mortality = true`
  **must pass real per-cohort `fc.pft_ids`**, because `FDiffFastCore` defaults every tree to beech
  (`fast.jl:147`) and the ported hazard's parameters are genuinely per-PFT (ids 1/2 are XERIC
  `mort_water_res` 0.25 not 0.75; id 5's longevity is 125 not 400 and its `mort_water_factor` 20 not 5).
  The ids are already in `references/M_individuals_<name>_2010.csv`'s `type` column — no new extraction.
- CLAUDE.md §3 carries the full per-PFT mortality table and the `par/pft_lpjmlfit.js` key traps
  (`longevity` is the JSON key `"age"`; `temp_stressed`, not the establishment `"temp"`; a DUPLICATE
  `aphen_min/max` for id 6 where the LAST occurrence wins).

### 4. F-side follow-ons, in value order (unchanged from M3; all reference bases established)

ADR 0053's verdict, so you do not re-measure it: **seasonal phase is excellent in all 5 biomes** (monthly
r 0.870–0.999 GPP, 0.858–0.999 ET). Three of five 10-yr level means are actively misleading — read the
year-matched ratio SHAPE: `tropical_amazon` flat ≈0.97 (**F is right**); `temperate_hainich` flat +12→+25 %
(a genuine FLUX-LEVEL bias, the one clean one); `boreal_siberia` 0.80→**1.70** (DRIFT, FPC +64.5 %);
`semiarid_sahel` 1.10→**0.59** (DRIFT, FPC −13.5 %); `mediterranean_iberia` noisy 1.09–1.72 (volatility).

a. **ET is 11–35 % HIGH while F carries NO grass transpiration** ⇒ the tree-only bias is larger still.
   Best-scoped candidate for ADR 0052's too-dry root zone, and it is the **demand** side, which ADR 0052
   never considered. Cheapest high-value F diagnosis left; `residual-diagnosis` first.
b. **Attribute Hainich's flat +12 %** with the kernel-isolation drive (`fdiff-validate`): drive F with the
   C run's own daily FAPAR so a GPP gap cannot come from the canopy. `d_fapar` is already in all 5 runs.
c. **The Sahel decline IS ADR 0052's dry-cell bias end-to-end.** ⚠ M4 sharpens this: the Sahel is also the
   ONE cell that does not recover from a pool perturbation (τ 602 yr, r² 0.38 vs 47–54 yr elsewhere). Same
   cell, third independent symptom. Fixing (a) may fix all three; measure before assuming.
d. ~~**F under-predicts tree FPC in all 5 cells (0.31–0.72×)**~~ **WITHDRAWN 2026-08-06 (ADR 0060) — it was
   a reference-basis artifact** (the C's two FPC outputs; see item 0-NEW at the top). Corrected: F
   **over**-predicts crown cover in four cells (boreal 1.32, Hainich 1.18, mediterranean 1.47, Amazon 1.05)
   and under-predicts only at `semiarid_sahel` (0.54). **Replacement item, narrower:** F's canopy
   *reconstruction* is faithful (t=0 ratio 1.00–1.04, eliminated), so what is left is F's **growth** —
   over-running the C in three cells, collapsing in the Sahel. Score it on the **coupled** arm, which has
   mortality; the `slow = nothing` arm has none and so cannot convict it. Start with the Sahel, the one cell
   this arm does convict and the fourth symptom of (c)'s dry-cell bias.

### 5. M4's own open findings (line-M work, not blockers)

- **No steady state under CYCLIC forcing:** coupled AGB drifts **1.39–5.15×** over 100 years with the
  forcing exactly periodic (max/init up to 12.45 at boreal). A model at equilibrium would sit at ≈1. The
  gate bounds it; it does not bless it. Likely the same free-running canopy growth as item 4(d) above,
  seen over a century instead of a decade — check that hypothesis before treating it as separate.
- **A 20-year window cannot resolve decadal memory even in the C.** If the AC-vs-climate question is ever
  reopened, it needs a longer transient than the historic `ind` table has (2000–2019 is its full extent).

**Small, still open:** `daily_step`/`daily_step_ml` (`fdiff.jl:662,850`) still use the realized-ratio
`wscal` — harmless (their `wscal` feeds no conditioning feature) but a second definition in the tree; unify
when convenient (ADR 0051 §Consequences). **`MEMORY.md` is 416 lines, over its 400-line cap** — a
`consolidate-memory` reshape is due and is **integrator-only** (restructuring it in a line can auto-merge
away another line's edit); M4 appended 15 lines to it.

## Scope + ownership (ADR 0029)

**You own (exclusive):**
- **`src/run.jl`, `src/interface.jl`** — the coupling seam. Other lines request changes here through you.
- `scripts/{run_coupled_biomes.jl,extract_biome_forcing.py}` + the new per-cell extractors
- `test/testitems/{biome_coupled,coupled_run,resilience_battery,rollout_stability}_tests.jl`
- `lines/M/*`, `changelog.d/M-*.md`, ADRs 0050–0069

**Do NOT touch:** `src/components/slow.jl`, `src/drf.jl`, `src/climbuf.jl` (line S) ·
`src/components/energy.jl` (line E) · `ext/` (line O) · `Project.toml` (integrator).
Shared, additive-only: `src/LPJmLFITEmulator.jl` (inside `# ── line M ──`), `CLAUDE.md`, `MEMORY.md`.

**SLURM tag prefix:** `M-` · other lines' `/p/tmp` artifacts are **read-only**.

## The contracts you consume (frozen — do not edit the other side)

- **From S:** `FluxDrivenSlowEmulator(fc, forest; boundary=, boundary_series=, n_init=, age0=, k_cap=,
  recruit_copula=, seed=)`, the `flux_feature_vector` order, `live_flux_cond`, the `.drf`/`.rcop` format, the
  `cell_meta.parquet` schema. **Pin a specific versioned artifact path** in your driver; if S needs to change
  the feature contract it is an integration point (both sides land together) — never adopt a re-trained
  artifact silently, because train/inference consistency is load-bearing (ADR 0023).
> ## ▶ ACTION FOR M — run the level anchor on your 5-cell oracle; it decides a DEFAULT (ADR 0103 §6)
>
> **This is the one thing S needs from M, it is small, and it uses a harness you already have.** S shipped
> the level anchor (`FluxDrivenSlowEmulator(...; anchor = a)`, ADR 0103) opt-in and default-off. Off is a
> **known-wrong default** — it leaves the stand 41 % denser than its own count model says, permanently — so
> it is temporary, and the criterion for flipping it is pre-registered rather than left to judgement.
>
> **Run:** `scripts/biome_slow_oracle_probe.jl`, 5 biome cells, historic 2010–2019, against the C `ind`
> truth in seed1-vs-seed2 floors — the harness that found ADR 0054's drift — with **`anchor = 0.5`**
> alongside your existing free and teacher-forced arms. ⚠ Use **0.5, not 0.1**, at a 10-year horizon:
> ADR 0103 §3b measured the anchor's convergence as NON-MONOTONE, and at yr 10 the retention is 0.24 at
> `a = 0.5` vs 0.62 at `a = 0.1` (against 1.07 unanchored). `a = 0.1` is the right *steady-state* value and
> the wrong one for a decade-long run. **Quote the horizon with any anchored number.**
>
> **Flip the default to `anchor = 0.1` iff** (i) the monotone drift is removed in the three drifting cells
> (boreal 1.12→1.74, mediterranean 0.98→1.81, Hainich 1.05→1.36 each flatten), (ii) the two cells at the
> noise floor STAY there (Amazon 0.5×, Sahel 1.4× — it must not break what works), and (iii) carbon still
> closes ≤1e-6·C_scale in all five. Then it is a one-line default change plus a baseline regeneration,
> which the owner has **pre-authorised** (below) — no further decision needed. **If it fails in any cell,
> that failure is the finding**; tell S rather than tuning `a` to make it pass.
>
> `patch_area` defaults to 225.0 m² (`par/lpjparam_fit.js`, 15×15) and is correct for the `_t8` artifacts
> you pin. It is a property of the ARTIFACT's training run, not the cell — stock LPJmL-FIT uses 100.0.

> ## ✅ ANSWERED BY S, 2026-08-06 — **you ran it (job 1716489), S ran it (1716500), the numbers agree, and
> ## THE CRITERION ITSELF WAS WRONG. Read ADR 0104 before acting on your own FAIL verdict.**
>
> Your evaluation is correct and S reproduces it to the digit. **But the criterion scores
> `s.target_history` — the count model's PREDICTION — and the anchor never writes it.** `slow.jl:1066-1070`
> multiplies the ROSTER (`dtree`); `target` appears only as the thing aimed at, so the criterion reads a
> second-order feature feedback with its own per-cell sign, not the intervention. **Your own last table is
> the tell**: "did the anchor fire?" reports the stand landing on its count model's target at **1.001 in all
> five cells** while the criterion two tables up scores FAIL in four.
>
> **Corrected yardstick — the stand's density vs the C's per-patch mean ÷ `patch_area`, scored
> `mean_y |ln(density/truth)|`: ALL FIVE CELLS IMPROVE AT ALL THREE SETTINGS**, mean 0.679 → 0.478 / 0.361 /
> 0.329 for `a` = 0.1 / 0.25 / 0.5. **Revised recommendation `anchor = 0.25`, not 0.1.**
>
> **Your M4 caveat is answered, and `anchor0` was the wrong arm for it.** `anchor0` is TEACHER FORCING — it
> injects an external series' memory, which is why it destroys Amazon `n` (0.066 vs a C of 0.501). The level
> anchor writes no feature. New opt-in `lvl0`/`lvl1` arms in `biome_resilience_probe.jl` (`ANCHOR=<a>`;
> **fixtures redirect to scratch when set, so your committed baselines cannot move**): Amazon `n` stays at
> **0.549**, and mean |AC − C's AC| over 10 cell-variable pairs is **0.0439 free → 0.0405 anchored**
> (`pin1` 0.0973). The anchor does not cost the memory.
>
> **NOTHING IS OWED FROM YOU YET — the one remaining blocker is your STATE item 2.** The driver starts from
> the MODAL patch, so every free arm above starts 1.56–1.95× above its own truth and part of what the anchor
> "fixes" is that initialisation offset ⇒ the measured benefit is an **UPPER bound**. The corrected
> criterion (ADR 0104 §7) must be re-run on the **patch-ensemble driver**. If item 2 is not near-term, say
> so and S will lift `readcanopy_patches` into `biome_slow_oracle_probe.jl` for the measurement only — that
> path needs nothing from you. **Do not flip the default on today's numbers, and do not read your FAIL as
> "the anchor doesn't work".**

> ## 🔓 OWNER PRE-AUTHORISATION, 2026-08-05 — **M's coupled BASELINE REGENERATION is pre-authorised.**
>
> Recorded by line S at the owner's explicit instruction ("I hereby pre-authorise that… write it down
> wherever it is needed"). **You do not need to ask, and you do not need S's sign-off, to regenerate your
> committed coupled baselines when deliberately enabling either of the two changes below.** This existed as
> a blocker only because §9 classes "regenerating an existing baseline" as an integration point needing both
> lines to agree, so each line waited for the other. That wait is now resolved in advance.
>
> **Scope — the two enablements this covers:**
> 1. **`WaterParams.wscal_leafon = true`** (ADR 0051) — the C-faithful leaf-on water scalar. S's side is
>    already landed; see the block below.
> 2. **The Component-S LEVEL ANCHOR, `FluxDrivenSlowEmulator(...; anchor = a)`** (ADR 0103) — once S has
>    published a measured recommendation for `a`. Default is `anchor = 0` = today's behaviour exactly.
>
> **What is NOT waived** (this is discipline, not gatekeeping, and none of it needs anyone's approval):
> the regeneration lands in **its own commit**, the **before/after numbers are recorded** in that commit and
> in `lines/M/STATE.md`, and CI is green. Guardrail 4 still means "no baseline moves *by accident*" — this
> authorisation is about the *deliberate* case, which is precisely the case guardrail 4 was written to allow.
>
> Anything beyond these two — a third baseline-moving change — is a fresh decision, not covered here.

> ### ✅ RESOLVED 2026-08-06 by ADR 0105 — **the anchor ACTION above is CLOSED. Do not run it; do not flip.**
>
> You ran it (ADR 0056) and S ran it (ADR 0104), then S re-ran it on **your patch-ensemble driver**
> (ADR 0057, which is what made this decidable) — jobs **1717190** / **1717247** / **1717189**. **The
> criterion FAILS at all three settings** and the default stays `anchor = 0`. Nothing above is owed by M any
> more, and **the "known-wrong default" framing in that block is WITHDRAWN**: on the ensemble the
> free-running level error is 1.04–1.38× (and 0.52× at the Sahel), not the 1.55–3.01× the modal patch
> showed. `anchor = 0` is not a defect on a timer. The owner's pre-authorisation for a coupled baseline
> regeneration still stands for `wscal_leafon`; the anchor half of it is simply no longer needed.
>
> **Your ADR 0056 verdict was right and is unaffected.** Your `density → fpc → target → density` loop
> reproduces on the ensemble (it is why the stability clause fires at `a` ≥ 0.25). Only the *reason* changes:
> the anchor is not under-delivering — it delivers exactly what it promised, onto a target that is wrong.

> ## ▶ NEW INTEGRATION POINT RAISED BY LINE S, 2026-08-06 (ADR 0110) — **per-tree root profiles and per-tree water status land in YOUR files; the two zeroed mortality hazards come back on**
>
> **What S did, and why it touches M's code.** Component S predicts a per-tree rooting depth (`D95max`) and a
> per-tree drought tolerance (`minwscal`), validates both globally, and dropped both — `make_recruit_to_pools`
> wrote only SLA and Wooddens, and `daily_step_canopy` collapsed the 23-layer profile to ONE scalar `wr`
> (`fdiff.jl:1540-1546`) before the individual loop opened. Two trees differing only in rooting depth were
> identical in the water balance, so drought response — ADR 0106's binding clause — could not exist. ADR 0109
> finished the statistical search on that axis (`D95max` worst of four on all three arms, no flip), which
> leaves "the trait has no physical consumer" as the remaining explanation.
>
> **The DEFER in `docs/water_supply_perpft_design.md` does not cover this, and the reason is specific.** That
> study was scoped to a GRASS residual, and its finding "rooting depth is not the mechanism" rests on grass
> sharing beech's `beta_root=0.8`. That is grass vs the AVERAGE tree. Tree-vs-tree it is false: `beta_root` is
> set **per individual** from that individual's own `D95max` (`new_tree.c:229-230`), the trait spans
> **51-1800 cm within one PFT**, and top-20 cm root share runs **69 % vs 4 %**.
>
> **★ The finding that unblocks it — the `-DPERMUTE` randomness does not touch the part we need.** `soil.w[]`
> is FROZEN for the whole permuted loop (written once per patch-day afterwards, `waterbalance.c:117-138`), so
> per-individual `wr`, `supply`, `pft->wscal` AND the routinely-firing "own FPC share" cap (`:159-161`) are all
> **order-INDEPENDENT**. Only the residue cap (`:162-166`) and realized GPP are not. `aet_cor` is TWO caps and
> the one that fires routinely is order-free. Full table in ADR 0110 §3. **Cap (ii) stays out of scope.**
>
> **Measured first (ADR 0108's method rule), on the C's own per-stem output, 5 biome cells:** across-tree
> p5-p95 water-scalar span **0.19** (Iberia) / **0.16** (Sahel) where F carries one number; within-(PFT x age)
> corr(`beta_root`,`wscal`) **0.83** in the Sahel; dry/wet spread amplification **112x** at Hainich;
> drought-killed stems root **57 % shallower** than the mean at Hainich. Warming: the drought share of hazard
> rises **x3.95** (Amazon) / x1.47 (Iberia) / x1.32 (Hainich). `scripts/diagnose_per_tree_water_access.py`.
>
> **What changed in M's files** (all opt-in, default byte-identical; flip criteria pre-registered in ADR 0110 §6):
> - `src/fdiff.jl` — `betaroot_from_d95max` / `jackson_rootdist` / `per_tree_rootdists` (ports of
>   `getbetaroot.c` + `getrootdist.c`, validated to **5e-7** against the C's OWN emitted `beta_root`);
>   `TreePools` gains `d95max`/`minwscal` (0 = unset, backwards-compatible constructors); `getvpd`
>   (`spitfire/getvpd.c`, the `relative_humidity=false` branch); `DailyForcing` gains `humid`;
>   `daily_step_canopy` gains a `rootdists=` kwarg, per-tree `wr_i`, per-tree withdrawal with the order-free
>   cap (i), and returns `wscal_ind`/`wr_ind`; new `WaterParams` flags `per_tree_roots`,
>   `per_tree_fpc_cap`, `trait_drought_mortality`.
> - `src/components/fast.jl` — `FDiffFastCore` gains `rootdists` + three per-individual annual accumulators
>   (`water_stress_acc`, `temp_stress_acc`, `aphen_acc`) and `_accumulate_stress!`.
> - `src/run.jl`/`src/interface.jl` — **NOT touched.** The design note's "the interface has no channel"
>   objection targets the wrong struct: the per-tree carrier is `TreePools`, which already carried two traits.
>   `SToF.rootdepth` is still the static read-back and still read by nobody (`step!` never dereferences `bc`).
>
> **⚠ ONE TRAP THAT COST A SUITE RUN, AND IT IS YOURS TO KNOW:** the per-tree profile was FIRST put in a
> `Vector{T}` field on `Individual`. That aborted the whole test process with **SIGABRT** (bare LLVM abort, no
> Julia error) right after the grass Enzyme reverse item — exactly the AD hazard the design note's §4.3 warned
> about, in a place it did not predict. `Individual` is differentiated through; **do not put heap-allocated
> fields in it.** The profiles now travel as a separate `rootdists` argument that Enzyme sees as constant.
>
> **What M owes / may want:** (a) review the F-side landing — S built it here under the ADR-0029 "M explicitly
> hands the file over for one milestone" route and this block plus ADR 0110 is the record; (b) the flags stay
> OFF until ADR 0110 §6's criteria are met, and criterion (e) (the historic->ssp370 response) needs a coupled
> five-cell screen, which is M's harness; (c) `_accumulate_stress!` uses `soilt_gate`, i.e. **E's skin
> temperature when the coupled driver sets it**, else the air-temp proxy — so the C's `soil->temp[0] > 10`
> gate is faithful whenever E is coupled and a documented proxy otherwise; (d) the per-tree path is a
> candidate explanation for M's §4 open items (ET 11-35 % high, tree FPC 0.31-0.72x, the Sahel dry-cell bias),
> because all three are water-supply-shaped and all three were measured with one shared root profile.

> ## ▶ NEW INTEGRATION POINT RAISED BY LINE S, 2026-08-06 (ADR 0105 §5, §7 item 3) — **the coupled count
> ## residual is F's CANOPY diverging from the C's. It is not a Component-S training defect, and S cannot fix it.**
>
> **Nothing is asked urgently and nothing is blocked on you.** This is S handing over an attribution with
> the measurement attached, because the paths it points at (`src/fdiff.jl`, `src/components/fast.jl`) are
> yours (CLAUDE.md §9) and because two of the three explanations S owned have now been measured empty.
>
> **What was eliminated.** (1) The **exposure bias** — the training-side defect ADR 0102 called (A) and S
> carried as its #1 item — is measured **empty** offline from the `_t8` tables (`scripts/exposure_bias_probe.jl`,
> job 1717208, 22.5 M rows): one-step bias **−0.0014** stems/patch/yr held-out-cell OOS on counts of ~10,
> AR gain **g = 0.562** ⇒ a **bounded** 2.28× amplification to −0.038 stems. The retrain is cancelled.
> (2) The **level anchor** is measured net-harmful at this horizon (above). (3) ADR 0102's defect (B) was
> already empty. What is left is the count model being fed a canopy the C never had.
>
> **The measurement.** The offline AR(1) prediction is computed with the count model fed **the C's own
> features and the C's own previous count**, so the gap between it and the coupled error is by construction
> everything the loop adds:
>
> | cell | offline 10-yr excess | coupled free (ensemble) |
> |---|---|---|
> | boreal_siberia | +4.2 % | **+35 %** |
> | temperate_hainich | −5.9 % | **+15 %** |
> | mediterranean_iberia | +10.5 % | **+38 %** |
> | semiarid_sahel | −0.0 % | **−48 %** |
> | tropical_amazon | +0.2 % | **+4 %** |
>
> Wrong size in every cell, wrong sign in two. And the canopy drift is directly visible in the same run
> (`biome_slow_oracle_probe.jl` REPORT 5, 2019/2010 ratio of each quantity to its own 2010 value):
> F's `fpc` moves **1.56×** where the C's moves **0.90×** (boreal), **1.27×** vs **1.00×** (Hainich),
> **0.71×** vs **1.23×** (Sahel). ADR 0053 already measured an F-side canopy bias; this says the count
> model then responds to it faithfully, which is why it shows up as a demography error.
>
> ⚠ **Two of your own published numbers are affected, and both were correct measurements on their basis.**
> (a) **ADR 0054's teacher forcing removing 59–72 % INVERTS** — on the ensemble, scored on the stand against
> the C rather than on `target_history`, forcing is **worse in all five cells** (score 0.149→0.277,
> 0.086→0.153, 0.180→0.259, 0.349→0.460, 0.029→0.069). It does not survive *either* correction (canopy basis
> or metric). (b) **`semiarid_sahel` is 48 % UNDER-dense, not over** — every reading of that cell as a
> too-dense stand, in ADR 0054/0055/0056 and in ADR 0104, inverts.
>
> **The generalisable part, which is why S is writing it here rather than only in an ADR:** the free-running
> ratio update **cancels** the count model's absolute level, and on the correct basis that is *protective* —
> the target is biased and the ratio form hides it. So "the recursion is unanchored" is not a standing defect
> claim, and an intervention that re-introduces the level (the anchor, or teacher forcing) will make things
> worse until the target itself is right. Full argument: ADR 0105 §3–§4.


- **From S — ✅ ANSWER to your ADR-0054 finding, raised 2026-08-05 (line S, ADR 0102). "The count
  recursion is unanchored" is CORRECT, and S has now decomposed it. It is THREE defects, not one, and only
  one of them is S's to fix — but that one is bigger than the exposure bias you attributed it to.**
  Measured by `scripts/diagnose_count_recursion_anchor.jl` (Hainich, constant forcing, 150 yr, job 1705626):
  - **(A) exposure bias** — the training `n_prev` is the C's own previous `n_living` (a `shift(1)` of the
    truth) while the runtime feeds the DRF its own output. Real, but **TRAINING-side**: it needs scheduled
    sampling or dropping `n_prev` from the feature set, i.e. a global retrain. Not closable from `slow.jl`.
  - **(B) state incoherence** — `slow.jl:1026` clamps ρ but `:1110` assigns the UNCLAMPED `target` to
    `n_prev`, so a clamp-binding year desynchronises the AR state from the roster permanently. S hypothesised
    this was the mechanism and **MEASURED IT EMPTY**: the clamp binds **0 of 150 years** and the roster
    tracks ρ to 1.5e-13. Do not spend time here.
  - **(C) NO LEVEL ANCHOR — this is the real one, and it is S-side.** ρ is a unit-free RATIO and the roster
    is advanced multiplicatively, `D_T = D_0·Πρ_t` (`slow.jl:779` documents the ratio as the mechanism that
    cancels the count↔density gap). So the DRF's **absolute** count skill — its R² 0.982 — is used only
    through year-on-year ratios and its LEVEL is discarded by construction. Nothing in the loop ever states
    what `D`'s absolute value should be. Measured directly: scale the initial stand density by 4× and the
    terminal densities still differ by **4.21×** after **300** identical-forcing years — **retention 1.04**,
    converging to a NON-ZERO asymptote (peak 1.40 at yr 25, flat from yr 150 to yr 300) rather than decaying
    to 0, i.e. no restoring force at all. **This explains your 59–72 % rather than 100 %:** teacher-forcing
    `n_prev` repairs the RATIO each year, but nothing repairs the LEVEL, so the initialisation error and
    everything accumulated into the level survives teacher-forcing untouched.
  **Your same-day refinement `9ad8721b` was RIGHT, and this completes it rather than correcting it.** You
  split the +36-81 % into a recursion factor **×1.26-1.53** and a **year-1 level offset ×1.05-1.12**, and
  said neither is the whole number. Correct. What S adds is the level term's **fate**: you read it as an
  initialisation artifact (partly the modal patch), which is right about its *origin* — but it never decays
  and is never corrected, and neither is any level error acquired later (a clamp-binding year, a k-cap
  merge, a hazard shortfall, or simply an imperfect year). **It is visible in your own published numbers:**
  the forced boreal arm flattens to 1.12-1.17 — flat, but displaced, holding the 1.12 it started with. That
  flat-but-offset trace *is* the missing level anchor. An initialisation artifact that never decays is not
  an initialisation artifact; it is a free parameter of the answer.

  **Your proposed teacher-forced re-run of the ADR-0100 2×2 is DECLINED — superseded premise, not a bad
  arm.** You proposed it because ADR 0100 had the baseline warming response wrong-signed at −2.44× FIT.
  **ADR 0101 withdrew that**: on the deployment artifact `R_ctl` = `−0.000 ± 0.367`, and the −2.44× was a
  single-cell demo-*fixture* property that reverses sign on a global artifact. There is no wrong-signed
  response left to attribute, so the arm would measure a recursion contribution to a response already
  indistinguishable from zero — and at 12 seeds per corner to see past the noise, it is not cheap. If it is
  ever run it must be an ensemble (ADR 0101 §1), never one draw.

  **What this means for M4 and for any online run:** an unanchored level is not a bias that averages out —
  it makes the coupled stand's density a function of its initialisation forever. Your M4 warning is
  therefore sharper than you wrote it: the shuffle test (c) cannot distinguish internal memory from
  recursion memory while the level is a free integrator, so run it on the teacher-forced arm too, and read
  the resilience battery's recovery rate as an upper bound.
  **The fix is specified but NOT landed, and it is genuinely two-sided** (which is why S is raising it
  rather than shipping it): anchoring `D` to the DRF's absolute target needs the count↔density conversion
  (patch area) at the S↔F seam — the very quantity the ratio was designed to avoid needing. That is an
  `interface.jl` addition (**yours**) plus a `slow.jl` change (**S's**), it moves every committed coupled
  baseline (guardrail 4 ⇒ a deliberate regeneration), and it needs a per-cell patch area in
  `cell_meta.parquet`. **Nothing is asked of you today.** It is scoped in ADR 0102 §4 as the highest-value
  remaining S+M item, ranked above the trait-conditioning work, and it should be the first thing a resumed
  S line does.

- **From S — ✅ GO on the `wscal_leafon` default flip, 2026-08-05. It is yours to land, unilaterally, and
  S's side is ALREADY IN.** You recorded this as "S's to schedule" and it has sat because flipping the
  default reds `slow_production_drf_tests.jl:168`. That assertion now admits **exactly the two admissible
  states** (`{water_stress}` with the flag off, the EMPTY set with it on) and fails on any third outcome, so
  the flip no longer needs a synchronised two-sided commit. S endorses it on your own measurement (ADR 0051):
  Hainich's `water_stress` goes **0.3050 → 0.0034** against a C truth of 0.0014 and a trained band of
  [0, 0.04315], so the flip **closes S's last out-of-band conditioning column** rather than merely being
  more faithful. Expect it to move your pinned per-cell coupled baselines — that is a deliberate
  regeneration under guardrail 4 and belongs in its own commit.

- **From S — OPEN INTEGRATION POINT #2 raised 2026-08-05 (ADR 0101 §5): the pooled artifact you pin ships
  an UNDEFINED per-cell initial condition. Nothing is broken today; the provenance is.** The
  `drf_forest_global_pooled_w20_t8` meta names a `cell_meta.parquet` that **does not exist**, and its two
  training sub-tables disagree at Hainich — `n_init`/`age0` = **11.0 / 43.556** (`slow_count_historic_w20_t8`)
  vs **7.0 / 46.0** (`slow_count_ssp370_w20_t8`). The choice is not cosmetic: it swings the trait-mortality
  operator's measured contribution by **4.5× the FIT shift**, and `n_init` 11.0 → 7.0 is what fires the hard
  kills that make a response measurement uninterpretable. `M_slow_init_meta.json` currently reads the
  **well-behaved** branch, so your pin is fine — but by silent substitution, not by decision, and
  `extract_cell_slow_init.py`'s own contract ("read them from the `cell_meta` of the SAME artifact version
  the driver pins") is *unsatisfiable* for a pooled artifact. Second, your **boundary row** comes from
  `slow_runtime_historic_t8` (the climatological table) at gdd5 **1 863.7**, while the pinned artifact was
  trained on the w20 transient tables whose historic value for this cell is **1 698.0** — a 165.7 gdd5 gap,
  **23 % of the entire +709 warming signal** — and on that artifact the boundary channel is worth
  **3 165 gC/m³ = 1.30× FIT** on ensemble average. **Ask:** either S ships a pooled `cell_meta.parquet`, or
  the substitution and its 4.5×-FIT consequence get recorded in the pin's provenance. S is not re-pointing
  your pin from this line.

- **From S — NEW OPEN INTEGRATION POINT raised 2026-08-04 (line S Phase 3A, ADR 0047): your drivers must
  pass `fc.pft_ids`.** `FDiffFastCore` defaults it to `pft_ids = is_grass ? 8 : 3`, i.e. **every tree in
  every cell runs as beech (`Type 3`)**. That is already wrong for the coupled biome set — Amazon and Sahel
  are `Type 0` — and it becomes load-bearing when S wires in the ported per-individual mortality hazard
  (`src/trait_mortality.jl`, landed offline with no call site), because that operator's parameters are
  **genuinely per-PFT**: ids 1/2 are XERIC (`mort_water_res` 0.25, not 0.75), id 5's `longevity` is 125
  (not 400) and its `mort_water_factor` 20 (not 5), and ids 0/1/2/4/5/6 all carry non-temperate `wdmort`
  pairs. Running the tropics on beech wood-density mortality would reproduce the ADR-0031 defect class
  inside the fix, so `pft_mort_params(id)` **errors** on an unknown id rather than defaulting — a coupled
  call site that does not pass real ids will therefore FAIL LOUDLY, not run wrong.
  **Nothing is asked of you yet:** the operator has no call site, so nothing in `run.jl`/`interface.jl`
  changes today and no struct changes are needed (`fc.pft_ids` already exists at `fast.jl:94` and
  `slow.jl` maintains it). What is asked is that when the per-cell drivers are next touched, the real
  `Type` per cohort is threaded through from `M_individuals_*` instead of taking the default. Until then
  line S passes ids itself in its own harnesses. No ADR-0023 contract break: the
  `FluxDrivenSlowEmulator` kwargs, `flux_feature_vector` order, `live_flux_cond` and the `.drf`/`.rcop`
  format are all unchanged.
- **From S — OPEN INTEGRATION POINT raised 2026-07-28 (line S milestone S1b, ADR 0031):** Component S's
  training population was widened from `TREE_TYPES = [1,2,3,4,5]` to FIT's COMPLETE tree set `[0..6]` — the old
  list silently dropped the tropical broadleaved evergreen (id 0) + the boreal larch (id 6) = **32.5 % of
  survivor tree stems** and made **16.7 % of tree-bearing cells** (the tropical belt + Siberian larch)
  invisible. **The feature contract is UNCHANGED** (`flux_feature_vector` / `live_flux_cond` order, the
  `.drf`/`.rcop` format, the `cell_meta.parquet` schema) — only the training *population*, so this is not an
  ADR-0023 break and needs no runtime change. What DOES change for you:
  - **New versioned artifacts, `t7`** (the orchestrators now take `VERSION=<tag>`; the pre-0031 files are
    untouched): `drf_forest_global_pooled_w20_t7.drf` (+ meta) is BUILT and validated; the pooled
    `recruit_copula_global_pooled_w20_t7.rcop` follows. **Re-pin deliberately** — do not adopt silently.
  - **`cell_meta.parquet` gains ~4 600 cells** (pooled 53 993 → **58 587**), i.e. previously-invisible tropical
    and larch cells now have `n_init`/`age0`/boundary. Your multi-cell driver's coverage grows accordingly;
    check any hard-coded cell list or expected-count assertion.
  - Count skill is essentially unchanged (every metric within ≈0.003 R²; see `lines/S/STATE.md` §Status), so
    expect no coupled-behaviour surprise from the count side — but the *set of runnable cells* is larger.
- **From S — ✅ DONE 2026-07-28, S1c landed (ADR 0032 closed → ADR 0034). Two things here concern you.**
  The committed `test/testitems/references/drf_forest_hainich.drf` + `_meta.txt` were regenerated off the
  retired proxy features onto the real basis; `recruit_copula_hainich.rcop`, its meta and both
  `hainich_slow_oracle_*.csv` are **byte-identical**, so only the count `.drf` moved. Re-measured Hainich
  thresholds all IMPROVED (Gate-3 Height `nqrmse` 0.3895 → **0.2998**, median ratio 1.25 → 1.13, count ratio
  0.67 → **1.28**) and the alarm was **tightened** 0.45 → 0.40. **If your M2 CI gate was designed against the
  old fixture, re-read it** — the artifact meta now also carries `y_min`/`y_max`/`feat_min`/`feat_max`, and
  `FluxDrivenSlowEmulator` gained a diagnostic-only `feature_history` field (no numerical change; every
  committed baseline byte-identical). Global `_t7` artifacts are untouched — your pin is unaffected.
- **From S — NEW INTEGRATION POINT raised 2026-07-28 (ADR 0034 §1, cause 1 of 3): the F core's
  `water_stress` at Hainich is ~330× the C oracle's.** With the runtime feature rows now recorded, the
  coupled loop feeds the count DRF `water_stress` **0.323–0.331** every year, while the C-derived training
  rows for the same cell/years span **[0, 0.0432]** (Hainich is essentially unstressed in the C). Same
  definition on both sides (`1 − wscal_mean`, `fast.jl`), and F_diff's own soil column is *near saturation*
  for part of the year — so a 1/3 water stress is internally odd, not just a basis difference. `src/fdiff.jl`
  / `src/components/fast.jl` are **yours** (ADR 0029), so S cannot chase this; it wants an F-vs-C oracle
  diagnosis (`fdiff-validate`). It is the single largest of the three remaining runtime↔training conditioning
  shifts (6.6× the trained band width) and it will bias any *coupled* global S run, so it matters before M3.
  The other two causes (`soilmoist` temporal aggregation, `lai`/`fpc` spatial aggregation) are S's, as
  milestone S1d.
  **↳ UPDATE 2026-07-28: S1d is DONE (ADR 0035) and `water_stress` is now the ONLY pinned out-of-band
  column** — the CI assertion in `slow_production_drf_tests.jl` is literally `Set(["water_stress"])`. So
  this integration point is no longer one of three; it is the last one, and it is yours. Nothing about the
  finding changed (runtime 0.323–0.331 vs trained [0, 0.0432], 6.6× band width).
  **↳ ✅ DIAGNOSED + FIXED 2026-07-30 by line M — ADR 0051. It was a QUANTITY mismatch, not aggregation.**
  ADR 0034 §1's "same definition on both sides" was wrong: the C's `pft->wscal`
  (`water_stressed.c:130-140`) is a **POTENTIAL leaf-on** index (no `phen`, `gp_stand_leafon` normalized by
  the plain `Σfpc`, no `(1−wet)`, and `= 1` on a no-demand day), while F_diff computed the **realized**
  supply/demand ratio (`phen` SQUARED in the numerator, degenerating to 0 as leaf display vanishes).
  Landed as **opt-in `WaterParams.wscal_leafon`, default `false`** ⇒ all baselines byte-identical.
  **⚠️ FLIPPING THE DEFAULT IS A TWO-SIDED INTEGRATION POINT — line M will not do it unilaterally.**
  It makes S's pinned set empty (`slow_production_drf_tests.jl:168` asserts exactly
  `Set(["water_stress"])` ⇒ must become `Set(String[])`), and it moves every coupled baseline because
  `wscal_mean` also drives the leaf:root allocation `lmtorm` (`allocation_tree.c:233` — the C uses the same
  accumulator, so this was never *only* a feature-basis bug). **Line M recommends the flip;** S should say
  when it wants to land both sides together. Measured effect (C truth derived per cell/year by
  `scripts/wscal_c_truth_diagnosis.py`, scored against the seed1-vs-seed2 noise floor):
  Hainich `water_stress` 0.3050 → **0.0034** vs a C truth of 0.0014 (**152×** error reduction, inside the
  trained band); `tropical_amazon` **inside the noise floor** (0.4×); `semiarid_sahel` 6.7× better;
  `mediterranean_iberia` 2.1×. **`boreal_siberia` is NOT closed** — see the gotcha list below.
- **From S — S1d landed 2026-07-28 (ADR 0035). Three things concern you.**
  1. **Both committed Hainich demo artifacts moved** (`drf_forest_hainich.drf` + meta AND
     `recruit_copula_hainich.rcop` + meta, regenerated together from one table build); the two
     `hainich_slow_oracle_*.csv` are unchanged. Re-read any M2 gate pinned to the old fixtures. Re-measured:
     Gate-3 Height `nqrmse` 0.2998 → 0.2990, count ratio 1.2808 → **1.1597**, DIRECT copula draws SLA
     0.1274 → **0.0391** / Wooddens 0.0346 → **0.0273** (both bounds tightened, none widened).
  2. **`flux_feature_vector` gained a 6th positional argument, the fast core's `SoilColumn`**
     (`flux_feature_vector(s, grow, pools, state, allom, soil)`). It is exported but had no caller outside
     `slow.jl`, so nothing of yours should break. The FROZEN contract is untouched: feature-column ORDER,
     `live_flux_cond`, the `.drf`/`.rcop` format and the `FluxDrivenSlowEmulator` kwargs are all unchanged.
  3. **NEW, SMALL, YOURS: `fast.jl:302` builds `FToS.soilmoist` on the retired basis.** It still computes
     `sum(state.w)/length(state.w)` (an unweighted mean over all 23 layers), while `interface.jl:37`
     documents that field as "root-zone soil moisture state, fraction of WHC" and S now computes exactly
     that (`LPJmLFITEmulator.root_zone_soilmoist(state, fc.soil)` — the top-1 m, `whcs`-weighted mean, which
     is what the C's `rootmoist` output measures). Nothing consumes the field numerically (only
     `coupling_tests.jl:96`'s `0 ≤ x ≤ 1` bound), so this is cosmetic *today* — but it is a second
     definition of a named quantity living in the codebase, which is the exact hazard ADR 0035 exists to
     remove. One-line fix in your file; S made all three of its own call sites use the shared helper.
  **Global consequence for M3:** the `_t7` global tables are on the retired `soilmoist`/`lai` bases, so a
  COUPLED global run inherits the shift. They need a versioned re-derivation (`t8`) and a deliberate re-pin
  by you before M3 — `_t7` is never mutated in place. The published `_t7` OOS numbers stay valid as
  *offline* measurements (table vs table). SSP370 additionally needs its own
  `cell_year_soilmoist_ye_ssp.parquet` first (the historic one exists).
- **From S — ✅ ACKNOWLEDGED 2026-08-05, a STANDING REQUIREMENT on any future M driver (S's item D,
  ADR 0049).** `fc.pft_ids` is a **correctness** requirement for `trait_mortality = true`: the ported hazard
  errors on a non-tree id, but a *wrong-but-valid* id passes **silently**, and `FDiffFastCore` defaults every
  tree to **beech** (`fast.jl:147`) — so a driver that leaves the default would run the tropical and boreal
  PFTs on temperate wood-density mortality, which is the ADR-0031 defect class exactly. **No M driver enables
  `trait_mortality` today** (it is opt-in, default `false`, and neither `run_coupled_biomes.jl` nor
  `biome_slow_oracle_probe.jl` sets it), so nothing is currently wrong — but the first M driver that turns it
  on **must pass real per-cohort `pft_ids`**. The per-cell PFT ids are already in
  `references/M_individuals_<name>_2010.csv` (the `type` column, 0-based `pftpar` index, `Type <= 6`), so
  there is no new extraction to do. Recorded here rather than only in S's file so it cannot be missed.
- **To S — RAISED 2026-08-05 (ADR 0055), a CAVEAT on the ADR-0054 `n_prev` ask, written into
  `lines/S/STATE.md`'s NEXT block.** The ask itself is unchanged; what M4 adds is that the anchor must be
  scored on the AUTOCORRELATION as well as the level, because (i) pinning the count-space AR feature moves
  the lag-1 AC by ≤ 0.135 — the recursion is a LEVEL failure, the memory lives in F's carbon pools — and
  (ii) the teacher-forced arm itself makes the AC **worse** in two cells (`tropical_amazon` count 0.066 vs
  a C of 0.501 = 2.3 between-patch SDs; `mediterranean_iberia` 1.2 SDs) against 0.1–0.6 SDs free-running.
  M's standing obligation: when S lands anything here, re-run `scripts/biome_resilience_probe.jl` and
  re-measure `d_over_psd` alongside the count level, and update ADR 0055 §4 rather than only ADR 0054.
- **From E:** the `SEBEnergyClosure(...)` constructor + `solve!` signature.
- **From E — OPEN INTEGRATION POINT raised 2026-07-28 (line E milestone E5, ADR 0071):** real daily
  **wind + surface pressure** now exist for the 5 orderA biome cells —
  `test/testitems/references/wind_psurf_<biome>.csv` (`year,doy,wind,psurf`, 2010–2019 × 365 d, obsclim
  GSWP3-W5E5, mapping proven by a `tas` round-trip). The coupled driver still builds `AtmForcing` with a
  CONSTANT wind and a fixed psurf, and `src/run.jl` is **yours** — so wiring these in is an M-side change
  E cannot make. Expect the coupled Hainich/biome baselines to MOVE when it lands (deliberate, not a
  regression): Bowen and the 2018-drought numbers are wind-sensitive. Land it with E (see
  `lines/E/STATE.md` E5).
- **From E — SECOND OPEN INTEGRATION POINT raised 2026-07-28 (line E milestone E3):** the
  **sublimation-λ split** cannot be done inside `energy.jl`. `src/components/fast.jl:236` forms
  `le = et/86400 · LAMBDA_VAPORIZATION` from `et = transp + evap + interc` — one λ for everything, and
  that ET sum has no snow/ice component to split; `FToE` carries no snow mass or snow fraction, so E
  cannot see which part of `le` left snow. Both files are **yours** (F core + the seam). Doing it right
  needs F to partition ET into a snow/ice part and either a new `FToE` field or the λ choice applied next
  to the partition (`conservation.jl::latent_heat(et; sublimation)` already exists for it). Opt-in,
  default byte-identical (guardrail 4). E will not attempt it alone — guessing a snow fraction inside E
  would be invented physics.
- **From E — SUPERSEDED 2026-08-05 by the FOURTH integration point below (ADR 0074).** E7 measured a
  two-layer prognostic ground-heat column that **beats** `lambda_g = 1.0` on every scoreable metric, so
  `enable_two_layer = true` is now E's recommendation and `lambda_g = 1.0` is only the smaller fallback. The
  original text is kept because the fallback is still valid and its evidence still stands:
- **From E — THIRD OPEN INTEGRATION POINT raised 2026-07-28 (line E milestone E6, ADR 0073):** E recommends
  **`SEBParams.lambda_g = 1.0` (currently 7.0)**. This is E's own file, but flipping a *default* moves every
  coupled and 5-biome baseline (it is the ground-heat term), so it must land with the baselines in one change
  — your call, your re-measure. **The evidence** (497 936 PLUMBER2 tower steps, 4 sites): `H` is the exact
  residual `Rn − LE − G`, so `ΔH = ΔRn − ΔG + ε_obs` identically; the modelled ground heat swings **5–7×**
  harder than observed at the forest sites, and **88 %** of DE-Hai's nocturnal H bias is the `G` error.
  `couple_day!` calls `solve!` **once per day** (`run.jl:93`), and at that step three independent lines give
  `λ_g ≈ 1.0`: the observation-implied fit is 0.83–1.10 at all four sites, `λ_g ≈ 1.0` reproduces the observed
  daily sd(`G_obs`) of 4.3–6.3 W/m² (the 7.0 default gives 14–31), and **daily H R² goes 0.03 → 0.64 (DE-Hai)
  and 0.33 → 0.74 (AU-ASM)** — a broad optimum (0.5 ≈ 1.0), degrading only the already-suspect AU-Rob.
  Expect `T_skin` swings to widen slightly (λ_g is in the Newton denominator), so re-check the
  `|T_skin − Tair| < 25/30 K` gates; `ρ·c_p·g_a` dominates that denominator, so the effect should be small.
  Nothing is needed from you until you choose to land it — **no default was changed** and
  `SEBEnergyClosure(params = SEBParams(lambda_g = 1.0))` already works today if you want to measure first.
  **Also: do NOT act on ADR 0072's `stab_amp` suggestion — ADR 0073 refutes it** (the closure's nocturnal
  `g_a` is within 0.7 % of DE-Hai's measured-`u*` value; that sweep was bias cancellation).
- **From E — FOURTH OPEN INTEGRATION POINT raised 2026-08-05 (line E milestone E7, ADR 0074). This is the
  one to act on; it REPLACES the `lambda_g = 1.0` request above.** E now recommends
  **`SEBParams.enable_two_layer = true`** (default `false`, so nothing has moved and every baseline is
  byte-identical today). It swaps the single conductance against a 30-day EWMA of *air* temperature for a
  prognostic two-layer soil column (`G = κ_g(T_skin − T1)`, `κ_g = 2λ_soil/z1`, MITgcm land-package update);
  `lambda_g` becomes inert when it is on. **Why this instead of `λ_g = 1.0`:** measured on the same 497k
  tower steps (harness reproduces ADR 0073 digit for digit), at the two sites whose towers can score H —
  daily H R² **0.645** vs 0.637 (DE-Hai) and **0.775** vs 0.745 (AU-ASM), and on `G` itself **0.717** vs
  0.657 and **0.614** vs 0.477. So it wins on H, wins clearly on G, and unlike a fitted coefficient it
  carries a real diurnal soil wave (sub-daily DE-Hai sd(G) 5.75 vs observed 5.66, night G R² **+0.394**),
  which is what line O needs. `Rn` is preserved within ±0.005. No secular drift over a 16-year record
  (−0.059 K/yr), so it is safe for your decadal coupled runs.
  **What lands on your side:** it moves every coupled and 5-biome baseline (it is the ground-heat term), so
  it is your call and must land with the baselines in one change, and ADR 0072's night-cold **sign**
  assertion in `energy_closure_tests.jl` is re-pinned at that moment. Measure first with
  `SEBEnergyClosure(params = SEBParams(enable_two_layer = true))` — it works today.
  **Costs to quote when you land it:** sub-daily `T_skin` degrades at AU-Tum/AU-Rob; one global
  `z_soil1` (default 0.75 m) suits closed canopies but under-resolves sparse/desert surfaces. **A related
  request:** `theta_soil` is a constant 0.5 because `FToE` (yours) carries no soil moisture — wiring F's
  root-zone wetness into the soil heat capacity is the natural follow-up, same shape as the E3 ask.
- `src/climbuf.jl` (`ClimBuf`, line S) is consumed via the `climbuf=` kwarg you already own in `run.jl`.

## Status (2026-07-28)

- `run_coupled_cell` runs the full S+F+E daily loop for **one** cell; carbon conserves at the S↔F handoff to
  ~1e-12 gC, energy closes to ~1e-14 W/m², and the opt-in `climbuf=` refreshes S's transient boundary.
- `test/testitems/biome_coupled_tests.jl` drives **5 biome cells** (boreal/temperate/mediterranean/semi-arid/
  tropical) with real GSWP3-W5E5 forcing — energy closes in every climate and the Bowen ordering is
  climate-correct — and since **M1 (ADR 0050)** each cell runs its **own soil column + own canopy + own
  latitude** (`references/M_soilcolumn_<name>.txt`, `M_individuals_<name>_2010.csv`, `M_cells.csv`), no longer a
  common Hainich patch. Still **`slow=nothing`**.
- **M1 evidence:** soil-column extractor gate = byte-identical reproduction of the committed
  `hainich_soilcolumn.txt` (`max|Δwhcs| 3.7e-5 mm`); emergent top-1 m root fraction 99.3 % (Sahel) → 53.2 %
  (Amazon), effective D95 72 → 690 cm; vegetation+soil effect vs the legacy common canopy = **+10.8 W/m² LE**
  (Amazon), **−7.6** (Sahel), mediterranean Bowen **1.27 → 0.65**; energy still closes ≤2.8e-14 W/m² everywhere.
  Suite 106,987 pass / 0 fail / 4 broken.
- **New oracle data this line owns (read-only to others):**
  `/p/tmp/jamirp/esm_land_daily/daily_2000_2019_M_biome_val_c{52059,33335,18371,12045}_seed1` — single-cell
  daily re-runs of the four non-Hainich biome cells with `d_fapar` + `a_lai_stand` + `a_fpc_stand` +
  per-cell `whc_nat`. Water-closure checked (multi-year fractional imbalance ≤3.5 %).
  **Plus, 2026-07-30 (ADR 0053):** `daily_2000_2019_M_grass_val_c{52059,33335,18371,12045}_seed1` — the same
  four cells re-run with the custom per-PFT daily **grass** GPP/NPP (`conf.h` ids 419/420), which is what
  makes `gpp_tree = d_gpp − d_grass_gpp` possible. Hainich's equivalent is the pre-existing
  `daily_2000_2019_grassgpp_c42490_seed1`. ~9 s per cell to regenerate
  (`CELL=<c> RUNTAG=M_grass_val SUBMIT=yes bash scripts/run_fdiff_grass_gpp_cell.sh`).
- **Committed F-vs-C oracle tables (ADR 0053):** `test/testitems/references/M_fdiff_oracle_biomes.csv`
  (monthly climatology) + `M_fdiff_oracle_biomes_annual.csv` (per-year, for year-matched scoring) +
  `M_fdiff_oracle_meta.json`. Built by `scripts/extract_biome_fdiff_oracle.py`; the F side is
  `scripts/biome_fdiff_oracle_probe.jl` (25-patch ensemble, `wscal_leafon=true`).
- **Committed S-vs-C oracle tables (ADR 0054, 2026-08-05):** `M_slow_oracle_counts.csv` (per-patch living-tree
  ensemble per cell-year, both seeds) + `M_slow_oracle_traits.csv` (6 axes × per-year community marginals,
  both seeds) + `M_slow_oracle_meta.json` (incl. the precomputed noise floors). Built by
  `scripts/extract_biome_slow_oracle.py` from the `ind_hist_seed{1,2}_all.parquet` tables; the coupled side is
  `scripts/biome_slow_oracle_probe.jl` (pinned `_t8` `.drf`+`.rcop`, `wscal_leafon=true`, a free arm and an
  `n_prev`-teacher-forced arm). A CI `@testitem` in `biome_coupled_tests.jl` guards the fixture's BASIS only —
  the skill measurement needs the 180 MB `/p/tmp` pin, which CI has no cluster for.
- So: **F+E generalize across biomes with per-cell vegetation, and since M2/M3 the coupled S runs all five
  cells and is scored against the C truth.** The global (all-cell) evidence for S is still offline (line S).
- Resilience battery is scaffold only: 3 `@test_skip false` in `resilience_battery_tests.jl` + 1 in
  `rollout_stability_tests.jl` (the `lag1_autocorr` estimator itself is real and tested).

## Milestones

- **M1** Per-cell input provisioning. **DONE 2026-07-28** (ADR 0050; skill `provision-coupled-cell`).
- **M2** Wire the flux-driven S into the multi-cell driver. **DONE 2026-07-30.** All five cells build their
  own `FluxDrivenSlowEmulator` (own `n_init`/`age0`/boundary from `M_cells.csv`, extracted by
  `scripts/extract_cell_slow_init.py` from the pinned `_t8` `cell_meta.parquet`) plus their own `ClimBuf`.
  *Gate (third item in `biome_coupled_tests.jl`, all five cells):* carbon at the S↔F handoff ≤1e-6·C_scale
  AND <1e-6 · energy <1e-6 W/m² · deterministic under seed · a fixed-N control proving F alone cannot move
  tree N · the `ClimBuf` drives only the two climate axes and its recomputed gdd5 orders the cells the same
  way their baked C-derived gdd5 does. Suite 107,192 pass / 0 fail / 4 broken (job 1643130).
- **M3** **Coupled multi-cell validation vs the C truth. This is the P3 gate.**
  - **F-side: DONE 2026-07-30 (ADR 0053).** Per-cell tree GPP / ET / FPC / stand LAI vs the C oracle for all
    five biomes, on bases fixed by construction rather than caveated (grass removed exactly via the id-419
    output; the C's own 25-patch ensemble; year-matched levels). Verdict: seasonal phase excellent everywhere
    (monthly r 0.870–0.999), level decomposes per cell into one genuine flux bias (Hainich +12 %), two pure
    drifts (boreal, Sahel), one volatility case (mediterranean) and one clean pass (Amazon 0.97).
  - **S-side: DONE 2026-08-05 (ADR 0054). M3 is CLOSED.** Per-cell demography + trait distributions against
    the annual `ind` parquet (both seeds, historic 2010–2019), on the same four bases: tree-only via the
    imported `TREE_TYPES`; the C's **25-patch ensemble mean** (S's count target is per-(Cell,Patch,Year) and
    the driver runs ONE patch — a per-cell total is ~25× off); year-matched; the writer's >5 m population.
    Population cross-checked EXACTLY against a second extractor (2010 per-cell totals == `M_cells.csv`'s
    `n_trees`, 122/282/214/272/276) and that equality is now a CI assertion.
    *Counts (mean |E−C| in seed1-vs-seed2 floors, free-running):* Amazon **0.5**, Sahel **1.4** — at the
    floor; Hainich **4.5**, boreal **11.1**, mediterranean **13.9** — and those three drift MONOTONELY
    (1.05→1.36, 1.12→1.74, 0.98→1.81), so their 10-yr means (1.2–1.4) hide the mechanism.
    *Attribution:* teacher-forcing `n_prev` onto its trained basis removes **59–72 %** of the error in every
    cell and flattens the drift ⇒ **0.2–3.9 floors**. The deployed error is an unanchored AR recursion
    compounding a ~5 %/yr one-step bias, NOT the count model's conditional skill (NEXT item 1).
    *Traits:* 9 of 10 cell-axis medians within **2.0 floors** (only SLA/Wooddens reach `TreePools`); two
    named exceptions — Sahel SLA 7.9 floors = a 4.6 % error on a 0.0002 floor (denominator artefact), and
    boreal SLA a correct median with a wrong distribution WIDTH (nqrmse 1.31 vs ≤0.43 elsewhere).
    *Carbon* closes 4.3e-13 – 3.4e-12 throughout. Cells are **IN-SAMPLE** for `_t8` (S's held-out-cell OOS
    R² 0.9824 is the out-of-sample statement) — which makes a miss here a real miss, not extrapolation.
    Artifacts: `scripts/extract_biome_slow_oracle.py` → `references/M_slow_oracle_{counts,traits}.csv` +
    `M_slow_oracle_meta.json` (committed); `scripts/biome_slow_oracle_probe.jl` (cluster-only, ~180 MB pin).
- **M4** **Resilience battery. DONE 2026-08-05 (ADR 0055).** All four stubs replaced by real tests, method
  reimplemented from Bathiany et al. 2024 (doi:10.1111/gcb.17613) — no `LPJ_resilience` code copied. The
  P3-vs-Phase-6 inconsistency is settled (Phase-6 work pulled forward into P3; no scaffold left).
  - **The acceptance criterion was a QUOTATION, so it was measured first — and it did not survive.** Over
    52 224 cells × 2000–2019 (the full extent of the historic `ind` table), per-patch detrended lag-1 AC is
    **flat at 0.452–0.541 across all ten P/PET deciles with the DRIEST decile LOWEST**; `agb` identically.
    Not shot-noise attenuation (noise-immune `r₂/r₁` sits *below* `r₁`; the between-patch spread is a
    persistent patch offset, 1.18–12.6× the year-to-year variance of the patch mean, so the obvious
    variance-based correction was written, measured and **discarded**). **The VARIANCE is the
    climate-graded quantity: CV 1.149 dry → 0.143 wet, 8×** — that is the replacement criterion, and
    `DEVELOPMENT_PLAN` §5 is annotated in place. Caveat that travels with it: 20 yr is all the table has
    and detrending is a high-pass filter, so τ ≳ 10 yr is unresolvable here.
  - **(a) No AC gap.** The deployed coupled arm is **0.1–0.6 C-between-patch-SDs** out on every cell and
    both variables (mean 0.32) — inside the noise floor everywhere, where M3's counts were 4.5–13.9 floors
    out. Both hold: ADR 0054's error is a LEVEL drift and a detrended AC cannot see it.
  - **(c) Shuffle test PASSES wide, and the memory is F's carbon pools, not S's recursion.** Year-shuffled
    forcing leaves AC at 0.460–0.653 (inherited ≤ 0.146); pinning the count-space AR feature leaves
    0.391–0.704; `slow=nothing` alone carries 0.454–0.691. `|free1 − pin1| ≤ 0.135` ⇒ **the unanchored
    recursion drives the LEVEL and adds ~nothing to the memory timescale.**
  - **(b)+(d)** 100 cycled years, tree pools halved at yr 21: no limit cycle (osc 0.06–0.50), nothing
    non-finite, carbon ≤2.1e-11. Open findings, recorded not smoothed: `semiarid_sahel` **does not
    recover** (τ 602 yr, r² 0.38 vs 47–54 yr / 0.60–0.73 elsewhere); **no steady state under cyclic
    forcing** (AGB drifts 1.39–5.15×/century); **an AC is not a recovery rate** (1.2–2.9 yr vs ~50 yr, 20×).
  - Artifacts: `scripts/extract_resilience_reference.py` → `references/M_resilience_reference_*.csv`;
    `scripts/biome_resilience_probe.jl` → `references/M_resilience_battery{,_shuffle,_longrun}.csv`.
    CI computes the estimator + a real `slow=nothing` perturbed/shuffled/60-yr rollout and gates the
    cluster-measured numbers as fixtures.
- **M5** Biome-calibrated PFT params + spin-up (today every biome runs beech ANGIO params from
  `par/pft_lpjmlfit.js`).
- **M6** Provide the coupled multi-cell harness line O needs for O5 (online multi-cell).

## Line-local gotchas

- **Hainich is `42490` in the global orderA grid** — `28008` is Sonoran desert there (it is Hainich only in the
  repo's `-DSINGLESITE` grid). Every per-cell extractor must use the orderA index.
- `.clm` readers must **parse the header** (v3 float32 HDR=51 vs v2 int16 HDR=43 with `scalar 0.1` ⇒ °C×10) —
  never assume float32/HDR=51. Reuse `scripts/build_transient_boundary.py::open_clm`.
- Committed fixtures under `test/testitems/references/` are **shared** — new ones take an `M`-ish/cell-specific
  name; **regenerating an existing baseline is an integration point** (guardrail 4: opt-in, default
  byte-identical).
- The 5-biome test uses a bounded negative-LE tolerance (`@test all(≥(-2.0), out.le)`) for the smooth-min
  undershoot in the fully-depleted Sahel corner — keep that reasoning if you touch the assertions.
- **Per-cell inputs come from the cell's OWN single-cell C run, not the global one** (ADR 0050): `whc_nat`
  differs between the 512-task global run and a single-cell re-run by up to 1.6e-4 relative in layer 0 under
  `-DPERMUTE`, which is 40× the fixture print resolution. `WHC_SRC=percell` is the default for that reason.
- **A `rootdist` that does not sum to 1 is silently physical**, not an error: F_diff's water supply scales
  linearly with `sum(rootdist)` (`src/fdiff.jl:846,928`) and `stand_structure_tof`'s D95 loop
  (`src/run.jl:65`) never terminates below 0.95. `hainich_soilcolumn` validates none of this — the extractor
  and `biome_coupled_tests.jl` do.
- **Never hard-code the repo root in a script** — it writes into the integrator worktree from here
  (CLAUDE.md §9 item 6). Derive it from `__file__` / `@__FILE__`.
- **`[VERIFIED 2026-07-30]` F_diff has NO soil ice, and that IS the cause of the boreal water-stress
  residual ADR 0051 left open (now ADR 0052).** The C's root-zone plant-available fraction at
  `boreal_siberia` (52059) is **exactly 0.000 for Nov–Apr** — every drop in the top metre is ice — while
  F_diff's sits flat at **0.67–0.91 all year**, so `emax·wr` beats the leaf-on demand every day and the
  leaf-on `wscal` is pinned at **1.000 in all twelve months**. Measured by
  `scripts/boreal_soilice_diagnosis.py` (C side, from `d_rootmoist.nc` + `whc_nat.nc`) and
  `scripts/boreal_soilice_probe.jl` (F side, `root_zone_soilmoist`). It is not a bad `wscal` — it is the
  right `wscal` of a soil column that cannot freeze.
- **`[VERIFIED 2026-07-30]` SECOND, DISTINCT residual: F_diff's root-zone water runs too DRY in dry cells**
  (ADR 0052). Same seasonal shape as the C, systematically lower: Sahel Jan **0.361 vs 0.533**, Jul 0.564
  vs 0.770; mediterranean Jul 0.239 vs 0.369. That — not the `wscal` definition — is what remains of those
  two cells' ADR-0051 gap (Sahel 36.5× the noise floor, mediterranean 7.5×), and it points the **opposite**
  way from boreal: F_diff **over**-stresses where it runs too dry. Higher-value than soil ice for a global
  run (semi-arid cells vastly outnumber permafrost ones). Candidate terms: the `_infiltrate` cascade (no
  surface/infiltration-excess runoff — a documented v2 item), `_soil_evap`, and the absent free-water
  (`w_fw`) reservoir.
- **The C's `rootmoist` + `whc_nat` are a per-cell, per-day reference for the emulator's root-zone water
  ANYWHERE on the global grid, with no new HPC run** (`d_rootmoist.nc` is in the global daily output).
  `w_C = rootmoist / Σ_{l<3} whc_nat[l]·soildepth[l]`, `soildepth = 200,300,500` mm. This is the cheapest
  check on F_diff's soil water balance — measure any soil-water residual against it FIRST. `swc` is NOT
  invertible to `w` (ADR 0035); `rootmoist` is the only output carrying it.
- **A "conditioning shift" and "extrapolation out of the trained band" are different failure modes, and the
  global band cannot tell them apart.** Against the **global pooled `_t8`** band (`water_stress ∈
  [0, 0.9618]`) the shifted runtime values were *inside* range; only the **Hainich demo artifact's** band
  ([0, 0.04315]) exposed them. A global coupled run was therefore evaluating the DRF at a perfectly valid
  point in feature space belonging to a **much drier cell** — which cost the Sahel 36 % of its trees. When
  checking a per-cell conditioning feature, score it against **that cell's own C truth**, never against the
  global band (`residual-diagnosis` §3e).

## M1 review debt — carry into M2 (from the 2026-07-28 adversarial review)

A 4-lens adversarial review of the M1 commits raised 16 candidate findings; the judge/verification phase
died on a session limit, so treat these as **unverified candidates, not confirmed defects**. The ones that
survived my own inspection were fixed in `b106cdae`'s follow-up (gate now also unit-checks the
`getrootdist` port that `beta_mean` uses; `WHC_SRC != percell` aborts unless `ALLOW_UNGATED_WHC=1`; the
`nstep`/window is asserted; `find_whc_run`'s glob is pinned to the historical window; subset `CELLS=` runs
MERGE the registry instead of truncating it; the test pins per-cell provenance and the FAPAR band).
**Still open:**

1. ~~**Test item 2 has no provenance sensitivity.**~~ **CLOSED 2026-07-30.** It passed VERBATIM when all
   five cells reverted to Hainich's soil + canopy, because its assertions were closure + finiteness +
   qualitative orderings. Item 2 now pins each cell's OWN mean LE and GPP (±2 % / ±3 %, against a
   24.9…119.3 W/m² between-cell spread) and asserts the five signatures are mutually distinguishable at
   those tolerances — so a driver-level fallback (an edit hoisting `soil`/`pools` out of the per-cell loop,
   or a per-cell artifact silently resolving to Hainich's) is now detected where the orderings could not
   see it.
2. ~~**`GATE=no` leaves no trace in the emitted artifacts.**~~ **CLOSED 2026-08-05** (`db6cbee5`). The
   verdict is now stamped into every column's `# GATE:` header line and into `M_soilcolumn_meta.json`, and
   `biome_coupled_tests.jl` asserts each committed column carries a PASS. Fixtures regenerated with the
   stamp — **all five files' data rows byte-identical**, only the header line is new. Pattern captured in
   the `provision-coupled-cell` skill.
3. **`CLAUDE.md` §9 contradicts itself on `MEMORY.md`**: the "where things are written" table says
   cross-cutting `[VERIFIED]` facts go to `MEMORY.md` (shared, additive) while the ownership table lists
   `MEMORY.md` as **integrator only**. This line appended to it (commit `e9da4d0c`) on the former reading.
   Integrator's call to reconcile — flagging, not fixing, since `CLAUDE.md` §9 is shared.

## Observed, NOT ours to fix (raise with the owner/integrator)

- `scripts/gen_diagrams.jl --check` reports `docs/src/generated/components.mmd` **STALE** — pre-existing,
  unrelated to any line-M change: the committed diagram still says component E will "reuse Terrarium.jl",
  while `src/registry.jl` now says "self-contained SEB (ADR 0017)". One line. It is **not** a CI gate (`docs`
  CI runs doctests + `makedocs`, never the diagram alarm), so nothing is red. The text belongs to component E,
  so regenerating it is line E's or the integrator's call — line M left it untouched deliberately.
