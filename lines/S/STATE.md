# LINE S — Component-S science (branch `line/S`, worktree `wt-S`)

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/S/JOURNAL.md` (append-only). Decisions: tier-1 block
> **0030–0049 is EXHAUSTED**; use the **tier-2 block 0100–0119** (opened by ADR 0100).
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here

### ⚠ ACTION 0, BEFORE ANY SCIENCE: MERGE THE PUSHED WORK. IT IS NOT ON `main` YET.

ADR 0100 is committed and pushed but **not merged** — the previous session ran out of wall-clock while branch
CI was still running. Do this first:

1. The verdict to check is on **`1b44cebb`** (`feat(S): the response arm …`) — that is the commit carrying the
   `test/**` change, so its expected gate set is **`test (lts)`, `test (1)`, `format`** (`format` was already
   **green**; `python` and `docs` correctly never run — ADR 0090's path filter). `test (pre)` /
   `test (macOS, lts)` are not required.
2. ⚠ **This STATE.md-only commit on top of it triggers NO gates at all** (ADR 0090), so the branch **tip**
   will report no check-runs. That is correct and expected, not a missing verdict — read the verdict off
   `1b44cebb` and merge the tip.
3. Then the normal ritual (`repo-commit` skill): `flock` the integration worktree, merge **`origin/line/S`**,
   push `main`, and check `main`'s own latest run (the merge touches `src/**`? **no** — so `main` runs
   `CI`/`format` only from the `test/**`+`.jl` paths, and `docs` still does not run).
4. If a required gate is **red**, do not merge: the suite was green on SLURM (job 1700642, **107 821 pass /
   0 fail / 4 broken**) and Runic was clean locally, so a red gate means a CI-only difference — a dep bump
   (diff the `Enzyme vX.Y.Z` line against a last-green log, CLAUDE.md §2) or a JET-0.11.6-only finding on
   `test (1)`, which reproduces only on Julia 1.12.

**Then: Phase 3A is COMPLETE as a mechanism (Stages 1/1b/2/3 all landed). Read ADR 0100 first, then 0049 §5,
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
  - **Stage 4 OPEN** — §NEXT item A (the pooled-artifact re-run, pre-registered prediction) then item B
    (co-occurring gross turnover, now DEMOTED).

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
