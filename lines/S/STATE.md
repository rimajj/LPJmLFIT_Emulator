# LINE S — Component-S science (branch `line/S`, worktree `wt-S`)

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/S/JOURNAL.md` (append-only). Decisions: ADR block **0030–0049**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here

**The wood-density damping investigation has a MECHANISM VERDICT. Read ADR 0046 first, then 0044, then 0045.**
Phase 0 (instruments) and the Phase-1 kill switch are DONE; the mechanism is identified and the gate is frozen.

### THE STATE IN SIX LINES

1. **ADR 0046 — trait-dependent mortality is CONFIRMED as the lever, by three independent measurements.**
   FIT's per-cell MEAN wood-density shift decomposes **22.2 % composition / 51.3 % within-PFT / 26.6 %
   interaction** (closure 4.6e-13), and the within-PFT part is **+112 % WITHIN-AGE-CLASS** with the
   age-structure term at **−11.8 %** (stands get *younger* under warming, opposing the shift). Traits are
   immutable after `new_tree`, so a trait rise at fixed age can only be differential survival ⇒ **the
   selection intensity itself responds to warming.** Composition (S3) is capped at 22.2 %; age structure and
   the entry marginal are excluded.
2. **ADR 0044 — the gate is frozen and the residual is a PLACEMENT error, not shrinkage.** On the corrected
   reliability basis the deployed arm's amplitude is `Ra` = **1.034** (`|Ra−1|` = 0.0344) while `Rr` = 0.3751
   against a **0.9543** ceiling. **So any lever justified by "reducing attenuation" / "raising `sd_ratio`" is
   aimed at a defect this emulator does not have** — including ADR 0030's criterion 2.
3. **`Rb` is DEMOTED to veto-only.** `sd_paired(ΔRb)` blocked = **533** (above the 450 demotion trigger), and
   the **permutation null buys `Rb` resolvably: +291.3 ± 88.1, 3.30σ, P(Δ≤0)=0.000.** The sentence form
   *"X reduced the damping from A % to B %"* is now forbidden in every variant (ADR 0044 §5).
   **P1 threshold = `ΔRr` ≥ +0.036** (measured 2σ; `sd_paired(ΔRr)` = 0.0178 hash / 0.0162 blocked).
4. **ADR 0045 — recruit traits are INHERITED, not uniform.** `w_inherit = 4/(4+n_elig)` ⇒ ≈44 % at Hainich,
   ≈80 % in low-diversity cells. **But the entry marginal is near-STATIC under warming** (5 of 7 PFTs move
   <+1000; the largest moves *down* 9227) ⇒ **the inheritance operator (old "Rung B") is DEPRIORITISED as a
   response fix.** It is still the correct establishment model and still corrects `CLAUDE.md` §3.
5. **Two numbers in the public report are wrong.** "37 % damping / `Rb` = −892" is arm **B `p14env-hash`, the
   REFUSED env arm**; the deployed ncond-8 arm is **−971.5 = 39.9 %**. And the `Rr` ceiling 0.9201 (and every
   `Ra` against it) is superseded by the patch-year basis (Wooddens **0.9543**). Not yet fixed in the .tex.
6. **New instruments, both gated and reusable.** `scripts/diagnose_slow_response_power.py` (paired
   `Rr`/`Ra`/`Rb` bootstrap; reproduces all 7 ADR-0042 arms to ≤5e-5) and
   `scripts/diagnose_wooddens_shift_decomposition.py` (the decomposition; per-cell terms at
   `/p/tmp/jamirp/emulator_global/tables/wd_shift_d2/`). Jobs `1693482`, `1693988`, `1694062`, all exit 0.

### DO THIS NEXT, IN THIS ORDER

**A. Port the hazard offline and gate it (Phase 3A Stage 1) — no call site, nothing in CI moves.**
The exact expression, `[VERIFIED]` against `/home/jamirp/lpjml56fit/src/tree/mortality_tree_ind.c`:
`mort_npp = min(1, mort_max/(1 + 0.2·exp(0.01·greff))·(1 + bm_inc_counter))` with
`mort_max = 10^(wdmort_1 + wdmort_2/(wooddens/1e6))` (`:92`; the `pft->par->mort_max` read at `:87` is DEAD
code, overwritten), `greff = bm_delta/leafarea`, then
`mort = min(1, mort_npp + mort_age + mort_water + mort_temp)` (**additive**, `:120-146`), hard kills at
`bm_inc_counter ≥ 5` and `leaf_c < leaf_carbon_sapl(sla)`, then a per-individual `erand48` Bernoulli draw.
⚠ **Do NOT port `mort_max` alone as "denser wood survives better"** — net selection is **not sign-definite**
(the one-year differential is *negative* for ids 0 and 3), because denser wood also lowers `greff` and so
*raises* `mort_npp`. Generate the per-PFT parameter table into ONE committed CSV
(`scripts/build_mort_params_reference.py` → `test/testitems/references/S_pft_mortality_params.csv`) and have
`slow.jl` **and** `build_slow_flux_table.py::PFT_PARAMS` both gate against it — never a third copy (ADR 0031).
`longevity` is the JSON key `"age"` (id 5 = 125, not 400); `temp_low/high` is `"temp_stressed"`.

**B. The validation target is the AGE–WOODDENS GRADIENT (ADR 0046 §3), not the damping.** Per PFT, including
the **non-monotone** shape for ids 0 and 3. A ported operator that produces a monotone gradient everywhere is
wrong even if `Rb` improves.

**C. `fc.pft_ids` already exists — no M struct change needed** (`fast.jl:94`, maintained by `slow.jl` at
`:445,453,457,513,793`). But **M's drivers never pass it**, so `FDiffFastCore`'s default
`pft_ids = is_grass ? 8 : 3` makes Amazon/Sahel (`Type 0`) run **beech `wdmort`**. M integration point #1;
until it lands the S-side harness passes `pft_ids` itself and the operator must **error**, not default, on an
id with no parameter row.

**D. Before touching the runtime, measure the k-cap merge confound (D4, zero compute).** `_merge_pair!`
(`slow.jl:441-445`) inherits the **dominant** parent's `wooddens` while conserving carbon by `nind` weight —
a trait-non-conservative operator sitting directly in the path of the fix. Run `k_cap = typemax(Int)` vs
default on the existing Hainich harness and diff the community wood-density trajectory. **If it moves, fix it
FIRST, separately, with its own ADR.** Same pass: read `s.target_history`/`s.total_n_history` (already
recorded at `slow.jl:810,812`) for the establishment fraction `e` ⇒ `τ = −1/ln(1−e)`, the analytic bound on
the rollout's second (relaxation) damping.

**E. Still open from Phase 0/1:** `CAP_HASH_SEED` (~10 lines at `build_slow_runtime_table.py:378-384`, default
`= seed` so every artifact stays byte-identical) — now has a SECOND justification beyond the floor: ADR 0045 §4
shows `:370-371`'s "patch-years are exchangeable" premise is false, since patch-years differ in age structure.
D1 (space-for-time surrogate) and D3 (calibration curve) are unrun but are **no longer on the critical path** —
ADR 0046 identified the mechanism without them; run them only to characterise the residual.

**F. Do not bundle.** Every arm/change lands separately with its own matched baseline **re-run in the same
generation, never inherited from a log** — that is the one move that caught all five prior wrong turns on this
line.

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
