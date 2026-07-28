# JOURNAL — LINE S (Component-S science)

> **Append-only, newest at the bottom.** Narrative for THIS LINE only: what you did, the commands, the
> results, dead ends. Durable state goes to `lines/S/STATE.md` (and its `## NEXT` block — refresh it before
> your session ends); cross-cutting durable facts go to `MEMORY.md`; the story of one change goes to a
> `changelog.d/S-<slug>.md` fragment. Pre-split history for the whole project: the root `JOURNAL.md`.
>
> Entry template:
> ```
> ## YYYY-MM-DD — <short title>  [milestone S<n>]
> - **Goal:**
> - **Did:**
> - **Result / evidence:** (numbers, job ids, gate outcomes)
> - **Decisions:** (ADR NNNN if any)
> - **Next:** (mirror into STATE.md's NEXT block)
> ```

## 2026-07-28 — line created (ADR 0028/0029)
- **Goal:** stand up line S as an independent work line so it can run concurrently with the other lines.
- **Did:** created by the Phase-0 setup session on `main`: branch `line/S` + worktree `wt-S`,
  `lines/S/{STATE.md,JOURNAL.md}`, ADR block assigned, ownership recorded in ADR 0029.
- **Result / evidence:** see the root `JOURNAL.md` Phase-0 entry for the setup evidence.
- **Decisions:** ADR 0028 (branch+worktree per line, supersedes 0013), ADR 0029 (the split + ownership).
- **Next:** the `## NEXT — start here` block in `lines/S/STATE.md`.

## 2026-07-28 — S1: the basis-clean noise floor — and the truncated-tree-set defect it uncovered  [milestone S1 → S1b]

- **Goal:** S1 as handed off — make the per-axis trait headroom an EXACT number by putting the
  seed1-vs-seed2 floor on the same basis as the emulator, so S2's success metric becomes measurable.
- **Did:**
  - Built the missing **seed2** copula table byte-for-byte like seed1 (only `SEED` differs; static boundary,
    **no `STEM_CAP`** — capping would subsample `Y` and inject noise into the floor). Job 1613731, **68 s**:
    `/p/tmp/jamirp/emulator_global/slow_copula_historic_seed2`, 133 562 549 stems / 45 072 cells.
    Note the handoff's literal command would have built a **count** table: `sbatch_python.sh` forwarded only
    `NCELLS/SEED/NO_DAILY/OUT/CELLS`, so `MODE`/`SCENARIO`/`STEM_CAP`/`BOUNDARY_WINDOW` silently defaulted.
    Fixed the forwarding list (shared infra, additive).
  - Rewrote `scripts/noise_floor_vs_emulator.py`: three bases (`copula` / `tree5` / `tree7`), a
    `seed1-basis ≥ 0.99` hard gate, a split-half (Spearman-Brown) decomposition of the floor, the
    attenuation-corrected ceiling, and a between-cell dispersion table. Smoke-tested on synthetic fixtures
    before every SLURM submit.
  - Ran a 4-agent read + 4-agent adversarial-verify workflow over the PFT semantics, every stem-selection
    predicate in the repo, the `pred_<axis>.f64` semantics, and the fix design. That is what caught the
    polarity error below — my first framing had it exactly backwards.
  - Wrote `scripts/diagnose_ind_type_composition.py` to settle it by global measurement (job 1616777).
- **Result / evidence:**
  - **S1 gate MET.** `seed1-basis` = **1.000 on all four axes** (was 0.973/0.488/0.761/0.092), and the
    independent parquet re-derivation reproduces the copula-table floor to three decimals — two code paths,
    one answer. Job 1616690.
  - **Exact per-axis headroom** (ids-1..5 population): GAP to the reachable ceiling **Wooddens +0.226 ·
    minwscal +0.153 · SLA +0.115 · D95max +0.102**; `r_center` 0.715/0.838/0.883/0.883.
  - Two corrections to published numbers: Wooddens' floor is **0.694, not 0.923** (the old basis inflated it
    ~3×, so the "+0.40 headroom" was wrong), and **D95max is NOT "at floor"** — `floor_r` is a
    realization-vs-realization r, not a predictor ceiling, so its raw +0.021 gap is a lower bound (+0.102).
  - Split-half 0.978–0.999 vs a floor of 0.694–0.964 ⇒ the floor is **trajectory divergence**, not
    finite-stem noise. `sd(pred)/sd(Y1)` = 0.55 for Wooddens (a second seed gives 1.00) ⇒ the copula
    regresses cells toward the global mean: missing between-cell *composition* signal.
  - **THE BIG FINDING — the emulator's training population is truncated.** `Type` is the 0-based `pftpar`
    index and ids **0–6 are all seven tree PFTs**, so `TREE_TYPES=[1,2,3,4,5]` drops id 0 (tropical
    broadleaved evergreen) and id 6 (larch): **64 179 572 of 197 721 867 survivor tree stems = 32.5 %**, and
    **9 011 of 54 020 tree-bearing cells (16.7 %) are invisible** — the tropical belt and Siberian larch.
    41.8 % of cells lose >half their stems. Provenance: a stale sibling `configs/config.yaml`, never an ADR;
    the correct constant already sits in `python/.../features.py:50`. It survived because Hainich has only
    ids 1–5, so every single-cell gate stayed green. The pre-S1 cross-checks (0.494 Wooddens / 0.093
    minwscal) are reproduced exactly by re-medianing the two populations ⇒ the committed "per-cell-median
    instability" diagnosis was wrong: traits are drawn from PER-PFT intervals, so a per-cell trait median is
    a composition statistic.
  - Latent defect recorded, not fixed: `growth_eff = applied_npp/max(lai,EPS)` divides by `EPS=1e-6` where
    `LAI_STAND == 0` (202 106 of 1 348 400 historic cell-years) → `growth_eff` max **1.19e9** in the seed2
    table vs 3.1e4 in seed1. The coverage guards cannot fire: the feature tables are complete, so a zero is
    *present*, not missing.
  - Process note: one SLURM job (1616644) failed with exit 1:0 and **no log at all** on `csm14c186`; a plain
    resubmit to another node succeeded — the known flaky-node signature, not a code fault.
- **Decisions:** **ADR 0030** (the gate: same-population floor, `seed1-basis ≥ 0.99`, the
  `√(rel_P·rel_Y)` ceiling, `(GAP, r_center)` + dispersion as the headline, S2 targets restated and blocked)
  and **ADR 0031** (Component S must train on ids 0–6; one imported constant; re-derive → retrain →
  re-validate → re-measure; versioned artifacts; **integration point with line M**).
- **Next:** S1b — execute ADR 0031 (constant → `lai>0` guard → re-derive/retrain/re-validate → re-measure the
  0030 gate). S2 is blocked until then, and ADR 0031's census makes **S3 (per-PFT/mixture copula) the leading
  hypothesis** for Wooddens rather than more covariates. Mirrored into `lines/S/STATE.md`.

## Session 2026-07-28 (line S) — S1b: the population widening lands, and the Hainich gate finds a second defect

- **Task:** execute ADR 0031 — one imported `TREE_TYPES`, the `lai == 0` guard, then re-derive → retrain →
  re-validate → re-measure the ADR-0030 gate.
- **The `lai == 0` guard: the answer was in the runtime, not in a policy choice.** ADR 0031 framed it as
  "drop or floor the row". Reading `fast.jl:369` settles it — the coupled loop computes
  `growth_eff = leaf_area > 0 ? applied_cell/leaf_area : zero(T)`, i.e. it returns **0** and never divides by a
  small number; the C oracle guards it identically (`mortality_tree_ind.c:95`: `if(leafarea_real > 1e-6) … else
  mort_npp = 1`). So the table must match the runtime: `lai > 0 ? applied_npp/lai : 0.0`, plus a
  `GROWTH_EFF_MAX` assertion, because the coverage guards structurally cannot catch this class (the feature
  tables are complete — a zero is *present*, not missing).
- **The "UNEXPLAINED" seed asymmetry is diagnosed** (`scripts/diagnose_lai0_growth_eff.py`, job 1621973). Stated
  as a falsifiable hypothesis first (H_seed) and confirmed on all three predictions: there is exactly **one**
  `cell_year_lai_hist.parquet` and it is **seed1-derived** (`RUN_DIR=…_c0_67419_seed1`). Joined onto seed1 `ind`
  it is self-consistent — **0 of 23.9 M** tree groups have `lai == 0`, because a cell-year with living leafy
  stems in *that* trajectory never has `LAI_STAND == 0`. Joined onto **seed2** `ind` (a different
  RAND48/`-DPERMUTE` trajectory) it hits **21 501 groups / 204 867 stems** with positive npp → max 1.19e9. Under
  the runtime rule that same seed2 build maxes at **4.3e4**, right at seed1's 3.1e4, and its mean falls from
  264 495 to 121.7 (seed1: 120.6). Consequence worth remembering: a seed2 table's `Xc` can never be fully
  runtime-consistent without seed2-derived `soilmoist`/`lai` — harmless for the 0030 floor (it reads `Y` only).
- **Widening the tree set, measured on the seed2 historic copula table:** 133.5 M → **197.8 M stems**,
  45 072 → **54 058 cells**, and `minwscal` from the truncated `[0.025, 0.30]` span to FIT's true
  `[0.025, 0.75]` — exactly the tropical-interval effect ADR 0031 predicted, now visible in the data.
- **The per-PFT parameter gap was bigger than ADR 0031 expected.** It asked for ids 0/6 to be added to
  `PFT_PARAMS`. Extracting them (brace-depth parse of the active `par/pft_lpjmlfit.js`, cross-checked by
  reproducing the previously-`[VERIFIED]` beech row) showed the old dict applied temperate/ANGIO values to
  *every* id, so it was also wrong for **ids 1, 2, 4 and 5** — most sharply id 5, whose longevity is **125**,
  not `TREE_LONGEVITY` 400 (a 3.2× age-mortality error), and whose `mort_water_factor` is 20, not 5. All seven
  rows are now `[VERIFIED]`, an unknown `Type` RAISES instead of silently taking temperate defaults, and the
  table is in CLAUDE.md §3.
- **ADR 0031 §3's byte-identity gate fired — and it was right to.** Built it as
  `scripts/verify_hainich_demo_artifacts.sh`; job 1622105 reported `drf_forest_hainich.drf` + meta modified
  (the oracle CSVs and the `.rcop` were byte-identical). I did NOT assume jitter and did NOT widen the gate:
  - The DRF meta's golden rows name the cause — `soilmoist` 0.7 → 0.860, `lai` 21.22 → 2.77, `growth_eff`
    18.97 → 145.26, **every other column bit-identical**. That is the retired **proxy → real** `soilmoist`/`lai`
    migration, not the population.
  - **Proved it is not my edit** (`scripts/diagnose_slow_table_drift.py`, job 1622128): the Hainich table built
    with the builder at `git HEAD` vs the working tree agrees to **max|abs diff| = 0 on all 15 columns**, same
    475 rows, same `n_init`/`age0`. The widening is a no-op here (ids 1–5) and so is the `lai` guard (no
    `lai == 0` row exists in seed1 at all).
  - **The sharp finding is disagreement, not staleness.** The `.rcop`'s own fallback conditioning row is
    `growth_eff = 150.53, soilmoist = 0.8539` — the REAL basis (committed 2026-07-27, ADR 0025), while the
    `.drf` is on the PROXY basis (committed 2026-07-23, ADR 0024). The coupled emulator loads both at once and
    they share four conditioning columns, so **one emulator has two conditioning bases**. → **ADR 0032**, and
    milestone **S1c**: regenerate both fixtures together with re-measured drift thresholds, as its own
    integration point with M — deliberately NOT folded into this milestone, since entangling it would make both
    before/after tables unreadable (ADR 0031 §3).
- **Process lesson captured in the gate itself:** a one-tier byte-identity gate **conflates** "my edit moved the
  table" with "the fixture was already stale". The gate now has a third verdict (`STALE-FIXTURE`, exit 2) driven
  by the control build, so the next session gets the diagnosis instead of the ambiguity.
- **Versioning:** all four `run_*_slow_*.sh` orchestrators took a `VERSION=<tag>` knob (suffixes every table
  dir, artifact and log). Line M pins `*_pooled_w20.{drf,rcop}`, so the re-derivation writes the **`t7`**
  generation and M re-pins deliberately — never an in-place overwrite.
- **Global re-derivation launched** on the `t7` basis: `gcopula_historic_t7` (1622131), `gpool_slow_t7`
  (1622134, pooled 22.5 M historic + 99.0 M ssp370 = 121.5 M rows), seed2 floor table t7 (1622132, DONE).
- **The pooled `t7` pair shipped and unblocked line M the same afternoon.** `recruit_copula_global_pooled_w20_t7.rcop`
  (job 1622337, after the 32-cpu OOM) completed at 15:46, so the COMPLETE pair now exists and **both halves were
  load-verified, not just declared built**: the `.drf` loads in 1.5 s with `nfeat=15`, the `.rcop` in 2.9 s with
  4 axes and 8 cond cols in exactly `live_flux_cond` order. Pooled K-fold-by-cell OOS trait nqrmse **SLA 0.005 ·
  Wooddens 0.016 · D95max 0.012 · minwscal 0.004**. Line M had, independently and on the same day, run a cell-
  coverage gate that found `semiarid_sahel` (18371) is in **neither** table the pre-0031 `pooled_w20` pin was
  trained on — only the `_t7` family covers all five biome cells (5/5 vs 3/5) — and had correctly REFUSED to
  adopt a half-published retrain with no `.rcop` (ADR 0023). That is external confirmation that the truncation
  was not a cosmetic scope issue: it was blocking another line's milestone outright.
- **Two bugs in my OWN new gate, found by running it rather than trusting it** (worth remembering as a habit):
  the extracted control builder resolved its repo root from `__file__`, so it broke the moment `TREE_TYPES`
  became an import (`ModuleNotFoundError`) — fixed by extracting into a mirrored repo root; and a control that
  *failed to run* was reported as "your edit moved the table", the loudest possible wrong conclusion from a gate
  whose entire purpose is telling those two apart — now a distinct `INCONCLUSIVE` (exit 3). Re-run confirms
  control exit 0 / NO-OP → `VERDICT: STALE-FIXTURE` (job 1622370), which is the ADR-0032 diagnosis.
- **S1b CLOSED — and the trait result reverses ADR 0031's central prediction (→ ADR 0033).** The chained gate
  (job 1622436, `afterok` on the copula) fired by itself and **passed**: `seed1-basis` = **1.000** on all four
  axes, 52 165 cells scored (was 36 228). ADR 0031 predicted a pooled single marginal would fit *worse* once id
  0's very different trait intervals entered. Measured, per-cell skill improved on **every** axis and most on the
  two that were worst: Wooddens `emu_r` **0.567 → 0.807** (dispersion 0.546 → 0.718, `r_center` 0.715 → 0.837),
  minwscal GAP **+0.153 → +0.039 (near ceiling)**, SLA +0.115 → +0.101, D95max +0.102 → +0.098.
  - **Mechanism (the actual defect):** the truncation removed the two PFTs whose composition is *most* predictable
    from environment — the tropical evergreen (climatically distinctive, the only tree PFT whose establishment
    gate is unconditionally open in the wet tropics) and the Siberian larch — leaving ids 1–5 competing in
    overlapping temperate/boreal envelopes where per-cell composition genuinely *is* weakly determined by the
    boundary features. So it selected the sub-population where the conditioning has least to say, and the low
    skill there was misread as "a pooled copula cannot represent composition". Two conclusions drawn from that
    basis are withdrawn: ADR 0030's "regresses cells toward the global mean" and ADR 0031's promotion of S3.
  - **Consequence for planning:** S1b closed **30 %** of the Wooddens GAP and lifted its dispersion 0.546 → 0.718
    (S2's gate targets 50 % and ≥0.75) **without touching the conditioning** — so the S2 gate must be re-baselined
    against `tree7` or S2 will take credit for the population fix. Wooddens is the only axis left with material
    headroom; the other three are at `r_center` 0.89–0.96.
- **Nearly mis-reported the pooled-marginal gain as 2.7–4.8×.** `nqrmse` divides by the observed IQR, and the
  widening moved that denominator (minwscal's IQR grew **2.47×** as id 0's `[0.05,0.75]` interval entered). The
  real gain is 1.9–3.0× in raw quantile RMSE; minwscal's headline 4.75× is really 1.92×, while SLA's IQR *shrank*
  so its 2.67× understates a real 2.99×. Recovered with `raw = nqrmse × IQR_obs` from the `obs_q` already in the
  log — no re-run. Captured in the `emulator-validation-figures` skill: a scale-free metric can move because its
  scale moved (the same family as ADR 0030's scale-blind-correlation lesson).
- **Also mis-read my own gate log once:** grepped for verdict patterns that silently dropped the SLA/Wooddens
  rows and briefly concluded the run was incomplete. It was complete. Read the raw section, not a filtered view,
  before calling a result missing.

## Session 2026-07-28 (line S) — S1c: one feature basis at last, and the gate that can finally see a shift  [S1c CLOSED → S1d]

**Task from the handoff:** regenerate the committed Hainich demo `.drf` + `.rcop` from ONE table build (ADR
0032), assert the two metas now agree, re-measure the four gates, document every moved threshold.
All of that is done, plus a finding the milestone was designed to surface.

**Reference basis + hypotheses, written down BEFORE probing (residual-diagnosis §1/§2):**
- *Basis:* LPJmL-FIT v5.6.004, historic obsclim 2000–2019, seed1, cell 42490, `individual=true`, carbon-only.
  Truth = `hainich_slow_oracle_{traits,counts}.csv` (the C `ind` per-stem marginals, ≥5 m = the C writer's own
  floor, nind-weighted). Training features = `soilmoist` from daily `swc` (23-layer × 365-day mean) and `lai`
  from annual `LAI_STAND` (cell-mean). Comparison = recursive coupled S (20 yr, repeated 2010 forcing) vs the
  non-recursive 25-patch C truth ⇒ a DRIFT ALARM, never parity.
- *H1:* regenerating the `.drf` on the real basis closes the ADR-0023 shift ⇒ the runtime feature rows land
  inside the retrained band. **Pre-registered risk:** `soilmoist` is the one at risk, because the runtime uses
  `mean(state.w)` while the trained band is a narrow annual-mean [0.8416, 0.8674].
- *H2:* the Gate-3 Height nqrmse moves, direction genuinely unpredictable. *H3:* the `.rcop` is byte-identical.

**H3 CONFIRMED, H2 resolved favourably, H1 PARTIALLY FALSIFIED — and that is the session's real result.**
- Regeneration (job 1622718): `.rcop` + meta and both oracle CSVs **byte-identical**; only `drf_forest_hainich.drf`
  + `_meta.txt` moved; control re-confirms NO-OP ⇒ `STALE-FIXTURE` exit 2, the expected verdict.
- Basis agreement now **8/8 shared conditioning columns inside the trained band, 0 violations**, boundary tails
  equal. ADR 0032's defect is closed and *measured* closed, not assumed.
- Every drift threshold improved: Height `nqrmse` **0.3895 → 0.2998**, median ratio 1.2463 → 1.1316, count ratio
  0.6734 → **1.2808**. Coherent single mechanism: in-domain `bm_inc_cell`/`growth_eff` raise the settled count
  6.8 → 12.9 stems/patch, and more stems on the same carbon are smaller trees, so Height moves *down* toward the
  C truth. Alarm **tightened 0.45 → 0.40**; nothing widened.
- **But 4 of 15 runtime columns are STILL outside the trained band** — `water_stress` (6.6× band width),
  `soilmoist` (5.1×), `lai` (2.9×), `fpc` (0.03×, marginal) — identically in all three coupled harnesses. So
  regenerating the artifact fixed the artifact-vs-artifact *split*, not the runtime↔training *shift*. Three
  distinct causes, routed by owner instead of bundled (→ **ADR 0034**): `water_stress` is an F_diff-vs-C
  difference (line M's file; ~330× the C's value while F's own soil is near saturation — internally odd);
  `soilmoist` is a TEMPORAL aggregation mismatch (year-end instant vs annual mean); `lai`/`fpc` are a SPATIAL
  one (one patch vs the C's cell-mean `LAI_STAND`, the known-open Phase-5 choice, now quantified at ~1.4×).

**The mechanism that made this visible is the durable deliverable.** ADR 0032 blamed the green gates on the
DRF's OOD leaf-clamping, flagged as inferred. The real reason is a *proof*: a DRF prediction is a convex
combination of training leaf means, so it can never leave `[y_min, y_max]` whatever it is fed — "targets inside
the training band" is therefore incapable of failing and is an artifact-integrity check, not a conditioning
check. So: `FluxDrivenSlowEmulator.feature_history` now records the exact row fed to the forest each year
(diagnostic only, numerically inert), `train_slow_drf.jl` writes `y_min`/`y_max`/`feat_min`/`feat_max` into
every meta, and `slow_production_drf_tests.jl` asserts the runtime rows against that band with the out-of-band
set **pinned** to the known three. A new column drifting out now reds CI. Chose pinning over asserting zero:
asserting zero would have forced either a rushed fix inside S1c or a silently widened gate.

**Harness validated before it was trusted (residual-diagnosis §3).** `measure_hainich_gate_bands_probe.jl`
pointed at the pre-S1c artifact (`DRF_ART=`, job 1622727) reproduced the three documented numbers exactly —
0.3895 vs "≈0.39", 1.2463 vs "≈1.25", 0.6734 vs "≈0.67". Only after that did I read the after-column as real.
It also let me state the *old* shift from the committed artifact itself with no reconstruction: the runtime
`lai` (3.3–5.1) sat below **all five** golden rows' `lai` (21.2, 59.6, 37.2, 29.1, 56.3) and the runtime
`growth_eff` (124–179) above all five (19.0, 6.6, 12.3, 20.0, 7.6).

**Planning consequence:** S1d (the two S-side aggregation bases) goes BEFORE S2. Starting S2's conditioning
expansion while three conditioning columns are on the wrong basis would let S2 take credit for a basis fix —
exactly the failure ADR 0033 recorded, where S1b silently delivered 30 % of S2's gate. Rejected outright:
retraining on runtime-produced features, which would make every band assertion pass by construction while
teaching the emulator F's bias instead of the C's demography (the C is the oracle, guardrail 3).
- **Closed the loop on S1c's own gate:** `scripts/verify_hainich_demo_artifacts.sh` re-run against the committed
  regenerated fixtures returned **`VERDICT: PASS` — exit 0** (job 1622811, all four artifacts byte-identical,
  working tree clean, no `git checkout --` needed). So the milestone's stated binary signal is verified, not
  asserted, and the `slow-drf-pipeline` skill's long-standing "expect exit 2 here" note is retired.
- **Merge friction worth remembering:** the mandated `git pull --rebase origin main` conflicted with line E's
  `ca1e78c6`, which had edited the SAME docs section of the shared `julia-test` skill hours earlier — the
  append-only rule for shared skills does not prevent a conflict when two lines append to the *same* section.
  Resolved by keeping BOTH contributions (E's "warm `--project=docs` before submitting to SLURM", mine "the
  diagram alarm needs `--project=.` and no CI job runs it"). Also: I ran the rebase and the push in one chained
  command, so the push fired while the rebase was still conflicted and shipped the UN-rebased tip; harmless here
  (the forced re-push after `--continue` corrected it) but the lesson is to never chain a push behind a rebase in
  one command. Branch CI was re-verified on the post-rebase sha `e3fa102a` (the pre-rebase verdict does not carry
  over), and `main` at `78fec71e` is green on all five required gates including `docs`.

---

## S1d — one basis for `soilmoist` and `lai` (2026-07-28, ADR 0035)

**Both of ADR 0034's S-owned diagnoses were wrong, and finding that out was most of the milestone.** The
handoff scoped S1d as two aggregation choices — a TEMPORAL one for `soilmoist` (annual mean vs year-end)
and a SPATIAL one for `lai`/`fpc` (cell-mean vs single patch). Following the `residual-diagnosis` rule
("confirm the comparison basis is correct" *before* writing the fix) against the C source changed both.

**`soilmoist` was the wrong VARIABLE, not the wrong clock.** `build_swc_soilmoist_feature.py` reduced the C
`swc` output, which `update_daily.c:411` writes as `(w·whcs + w_fw + wpwps + ice)/wsats` — **total** water
over **saturation** capacity. The runtime fed `state.w`: **plant-available** water over **WHC**. Different
quantities; `swc` lives on ~[wpwp/wsat, 1] and `w` on [0,1]. Had I implemented the handoff's "cheap side"
(re-reduce `swc` to year-end) the band assertion would have gone green over a mismatch — strictly worse
than the documented shift, because the alarm would have been spent. The tell that this is easy to miss:
the two overlap numerically (Hainich `swc` 0.84–0.87 vs `w` 0.79–1.00), so an aggregation story *looks*
like it explains the gap. `swc` is not invertible back to `w` (needs `wsats`/`wpwps`, never emitted); the
only C output carrying `w` is `rootmoist` = `Σ_{l<3} w·whcs` over the top 1 m (`soil.h:353`).

**`lai` was reconstructable all along, contrary to the skill AND the builder docstring.** Both asserted
"per-patch LAI is NOT reconstructable from ind (no `leaf_c`/`nind`)". True literally, false in effect —
`LAI` (within-crown) and `fpc_ind` between them carry the crown area, and `nind = 1/patcharea` makes
patcharea cancel: `stand_lai(patch) = Σ LAI·fpc_ind/(1−exp(−k_pft·LAI))`. I did **not** take that on faith:
`scripts/diagnose_patch_lai_reconstruction.py` inverts `fpc_ind` for crown area and compares against the
C's own *height* allometry — two expressions sharing no algebra — over 22 498 stems in five biomes.
Median rel err **1.8e-8**, p99 9.2e-6.

Two false starts worth recording, both from validating against the wrong thing:
- I first gated the reconstruction on matching the gridded `LAI_STAND` and got errors up to 38 %. The cause
  is that the `ind` writer emits only stems `height > height_min = 5 m` (`fwriteoutput_ind.c:84`) while
  `LAI_STAND` sums all trees — so the reconstruction is the **>5 m** stand LAI (0.77–1.01 of the cell mean,
  by biome). That is not an error: every other column in the training row is on that same >5 m population.
- My first tolerance (1e-6) failed at max 1.2e-5. The TXT writer is `%g` = **six significant digits**, and
  the inversion amplifies that through a `^≈2.3` power. Any inversion from `ind` has a ~1e-5 precision
  floor; the honest signal for a wrong constant is a percent-level bias in the MEDIAN, not the max.

**`fpc` needed no change at all.** ADR 0034 grouped it with `lai` as "SPATIAL", but the training `fpc` was
already `min(Σ fpc_ind, 1)` over the same patch's stems — per-patch on both sides. Its residual excursion is
a *dynamics* outcome (the coupled patch settles denser than the training upper tail), which no basis fix can
close, so ADR 0035 does not claim to close it.

**Decisions.** `soilmoist` = root-zone (top 1 m) `whcs`-weighted mean of `w` at YEAR END, both sides —
because the feature row splits into three annual integrals F delivers and eight year-end states, `soilmoist`
is a state, and the annual water integral is already `water_stress`. I rejected the runtime annual-mean
accumulator that ADR 0034 called the clean fix: it needs a daily hook in `run_coupled_cell`, and `run.jl` is
line M's — it would have parked S1d's gate on another line's schedule for a change that §4 argues is not
even clearly better. `lai` = the per-patch reconstruction, defined in ONE place
(`build_slow_runtime_table.py::patch_stand_lai_expr`) which the diagnostic imports (ADR 0031's lesson).

**Measured (job 1622923; regeneration 1622921, control confirms only `soilmoist`/`lai`/`growth_eff` moved,
targets byte-identical):** `soilmoist` **IN** band (was 5.1× band width); `lai` 2.9× → **0.021×** (12-yr) /
0.086× (20-yr); pinned out-of-band set down to **`{water_stress}`** alone. Gate-3 Height `nqrmse`
0.2998 → 0.2990, count ratio 1.2808 → **1.1597**, carbon 1.9e-12, basis-agreement violations 0. DIRECT
copula draws improved sharply (SLA 0.1274 → **0.0391**, Wooddens 0.0346 → **0.0273**) because two of the
copula's four conditioning columns moved onto real bases — so those two bounds were **tightened**
(0.22 → 0.10, 0.12 → 0.06). Nothing was widened.

That the Height drift did **not** move (0.2998 → 0.2990) is itself a result: the remaining Gate-3 residual
is not a conditioning-basis artifact, so S5's recursive-drift work cannot expect a basis fix to pay for it.

**Side effect:** the `lai == 0 → growth_eff` blow-up class (ADR 0031) is now structurally impossible rather
than guarded — `lai` comes from the same `ind` rows being aggregated, so it can no longer arrive from a
different seed's trajectory via a cross-seed join. The `GROWTH_EFF_MAX` assertion stays as a standing alarm.
