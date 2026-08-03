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

---

## Session 2026-07-29 — the `t8` global generation, and biomass/size become measurable (ADR 0036)

The task was the `t8` re-derivation the S1d handoff left. An earlier session today had already landed the
COUNT half (jobs 1633248 the ssp370 root-zone soilmoist deriver, 1633254/1633255 the two scenario DRFs,
1633273 the pooled DRF + scenario-holdout, 1633275/1633276 the K-fold OOS preds) but had not updated
`STATE.md`, so the handoff understated the state — **check the artifact directory's mtimes and `logs/`, not
only the handoff.** It had also left uncommitted work in the tree: the STRUCT-axes plumbing in the builder,
the pooler, `eval_slow_copula.jl` and `run_global_slow_copula.sh`, plus a new report script — and, in two
files, a **docstring describing behaviour that was not implemented** (`noise_floor_vs_emulator.py` promised
`[diag]` struct rows; `plot_slow_emulator_validation.py` had no biomass block at all). Reading the diff
before extending it is what caught that.

**Why biomass needed a decision rather than a metric.** Neither model predicts stand biomass: the count DRF
predicts `n_living`, the copula predicts four *recruit traits*. The obvious move — add `agb`/`Height` as
production copula axes — is wrong three ways: `make_recruit_to_pools` maps exactly four axes onto carbon
pools (ADR 0025, frozen; line M pins the artifact), and `agb`/`Height` are *outcomes* of the dynamics, so
sampling them at recruitment would double-count F's allocation. They are therefore APPENDED diagnostic axes,
excluded from the `.rcop` structurally (the trainer reads the manifest's `axes` line; the struct set is a
separate `nstruct`/`struct_axes` pair) — and the "production predictions stay bit-identical" claim was
**measured, not asserted**: job 1641319 builds the same 50-cell table with the option off and on and `cmp`s
every shared file and every production `pred_<axis>.f64`. All four identical.

**The 5-cell smoke that failed for the right reason.** My first gate used 5 cells and died on
`AssertionError: axis SLA: some rows never in a test fold`. That is not a coverage bug: folds are
`hash(cell) mod K`, all 5 cells hashed into fold 0, the other fold fitted a forest on **0 rows**, and its
predictions came back `NaN`. Captured in the skill — never smoke `eval_slow_copula.jl` on a handful of cells.

**Stand biomass is a composite, and the cross-check is what makes it quotable.**
`pred = mean_OOS(n_living) × mean_OOS(per-stem agb)` per cell, against the C's own per-patch `sum(agb)`.
`mean(N)·mean(A) ≠ mean(N·A)` — they differ by a negative within-cell covariance (denser patches, smaller
trees) *and* by a year-set mismatch (the count table drops each scenario's first year for `n_prev`; the
copula table keeps it). Rather than argue either away, `basis_ratio` measures both: **0.992**, so the
identity holds to 0.8 % across three decades and the composite is a fidelity claim, not a diagnostic. The
right-hand panel of fig 12 IS that cross-check, and it sits on the 1:1 line.

**Two metrics that would have misled, fixed in the same change.**
- `nqrmse` on a heavy-tailed axis is meaningless: per-stem `agb` reads **0.75** while every one of its five
  quantiles is within 3–8 % (`pred [8.8, 19.5, 43.1, 160, 3047]` vs `obs [9.0, 20.0, 44.5, 171, 3301]`) and
  its KS is **0.011**. `nqrmse` divides every quantile error by ONE IQR, and here `q95/IQR ≈ 10`. Added
  `median_rel_q_err` (agb: **0.025**) and made the panel title say which number to read. Same family as the
  ADR-0031 lesson that a scale-free metric can move because its scale moved.
- Figure 06 was captioned "the distributional check the count DRF exists to pass". It is not: the count eval
  scores `DRF.predict`, a **conditional mean**, so the predicted histogram is narrower than observed BY
  CONSTRUCTION. Both the panel and the report now say so — and this is why I did **not** add the per-cell
  count-KS figure that would have been symmetric with the trait figure 11: a conditional mean cannot be
  scored against an observed within-cell spread.

Also: figures 09-11 sized their panel grid from a hard-coded 2×2, which would have silently dropped any axis
past the fourth; heavy-tailed axes now auto-switch to log scaling (on a linear axis both curves collapse into
one spike, which hides a mismatch instead of showing it); and the biomass R² is reported linear AND log10,
because stand AGB spans 3+ decades and a linear R² is nearly blind to the semi-arid/boreal tail that is most
of the land area.

Captured as reusable procedure: `scripts/run_slow_validation_figures.sh` (the whole figure set + report for a
generation, one submission — its real content is the input-dir mapping, which does not follow one pattern),
the two skills' new sections, and `DEPENDENCY=` on `run_pooled_slow_copula.sh` so it matches its three
siblings.

**Outcome.** `t8` merged to `main` as `bf84a219`, all required gates green (`test (lts)`, `test (1)`,
`format`, `python`; `test (pre)` is the allowed-to-fail prerelease job and I touched no Julia source). The
headline: counts OOS R² 0.9826/0.9823/0.9824 with per-cell-mean R² 0.9989; traits pooled `nqrmse` 0.004-0.021
and the ADR-0030 gate PASSING at `seed1-basis` 1.000 ×4 over 52 165 cells; **biomass per-cell R² 0.931
(log₁₀ 0.945), median pred:obs 1.020** and both structure axes AT CEILING (`r_center` 0.987 / 0.986) with the
lowest per-cell KS of all six axes.

**Two process notes for whoever is next.** (1) The handoff understated the state — an earlier session the
same day had already landed the whole COUNT half and not updated `STATE.md`. Check artifact mtimes and
`logs/` before re-running anything expensive. (2) The shared integration worktree had a **stale 0-byte
`index.lock` from 21:40** with no git process behind it, which blocks every line from merging; I cleared it
inside the `flock` after checking size, age, process table and tree cleanliness. If a merge fails that way,
verify those four things rather than either forcing it blindly or giving up.

## 2026-07-31 — S2's gate is met, and the win is a spatial address

Collected the four in-flight rungs (1646346/47/54/55) plus the self-polling KS sweep (1646487). Both
env-conditioned rungs clear the ADR-0030 §4 criteria for the first time; `env-qrf-b6x2M` (6x2M, d22, QRF=1,
ncond 14) is the config, `b6x8M` rejected for 4x the bytes and worse pooled KS on all four axes.

Ran an 11-agent adversarial verification (7 audits + 3 refutations + synthesis, ~1.9 M subagent tokens). It
changed the conclusion twice, which is the point of running it:

1. **ADR 0037's thesis inverts.** The estimator lever is larger on `emu_r` but SATURATES at 0.867 (asymptote
   0.870; the gate needs ~1000x the whole table by capacity alone), while conditioning is the larger lever on
   criterion 2 — the axis that was failing — and carries both criteria across. S2's premise is vindicated,
   not refuted. I had initially written this up as "capacity saturates at ncond=8"; the audit correctly
   pointed out that (a) the b12/24/40x500k trio is the tree-count experiment and is NOT evidence of subsample
   saturation, and (b) the plateau is a property of the subsample lever at BOTH widths, with the conditioning
   setting the level. Also: ADR 0037's extrapolation was defensible on the QRF=0 ladder it had (dead
   straight, +0.00903/+0.00900 per doubling) — the 8M rung is new information, not an avoidable error. Said
   so in the ADR rather than framing it as a mistake.
2. **The six env columns are a per-cell spatial ADDRESS, not a climate response.** Verified myself: median
   within-cell sd is EXACTLY 0 for 100 % of cells on all six. 1-NN on them reaches r=0.800 with the nearest
   neighbour 1.00° away, and by-cell folds cannot separate interpolation from transfer. So the gain is real
   offline and its generalization is unestablished ⇒ shipped as the historic-static artifact, NOT promoted to
   M's pinned production copula. Spatially blocked CV is now the named gate on production.

Independently verified the audit's biggest claim before believing it: the **ssp370 `random_seed2` ground
truth is a bit-identical copy of seed1** (same 193 GB size, equal md5 at three separate 1 MB blocks) because
its config restarts from the *historic seed1* `restart_2019.lpj`, making `"random_seed": 2` inert under
`-DFROM_RESTART`. My first control read the empty-string md5 (wrong path) and proved nothing; redid it
against the real historic pair, which DIFFERS at every block and reads its own relative restart. A floor from
that duplicate would report `floor_r ≡ 1` and fabricated headroom with no error, and the `seed1-basis ≥ 0.99`
check is structurally blind to it. Guarded, and self-tested in BOTH directions — the negative control aborts,
the positive control passes and reproduces the published baseline exactly, which also proves the gate's
arithmetic is untouched.

Three silent-failure paths closed in code: `.rcop` format v2 carries `qrf` (v1 still loads, so guardrail 4
holds and nothing M pinned needs regenerating); the emulator rejects a conditioning-width mismatch at
CONSTRUCTION rather than at a first recruit that may never happen; and the duplicate-seed guard above. Plus
two new tools — an acceptance probe that loads an artifact in a FRESH process (t9: 6.77 s / 71.6 MiB/s
measured, replacing an unmeasured "~12 s at 42 MB/s") and a seed1-only dispersion scorer so criterion 2 is
measurable for pooled, which has no seed2.

Closed a gap the audit named: no 2M/8M rung had ever reported its leaf geometry. The t9 artifact IS a
6x2M/d22 forest, so probing it measured the missing slack directly — 52.3-67.0 % of stored values are still
depth-capped, so depth is not exhausted at the production config and is free in bytes. The same probe
explained why QRF's payoff collapsed with capacity: the max-leaf weight share is 6.7x `1/T` at 60 trees but
only 2.9x at 6.

Suite green end to end: 107 394 pass / 0 fail / 4 broken (job 1647687), Runic clean 111/111.

### Post-merge: the config transfers to the pooled basis

Job 1647661 finished after the merge. The same config on `slow_copula_pooled_w20_t8env` (the transient
`pooled_w20` basis line M pins) lifts Wooddens `emu_r` 0.8261 → 0.9095 and `sd_ratio` 0.6119 → 0.8493, so
criterion 2 goes FAIL → PASS there too, with criterion 3 improving on all four axes against the pooled
baseline. Recorded in STATE.md + a changelog fragment rather than by editing ADR 0038, which is accepted and
immutable — nothing in it is falsified: it explicitly declined to claim pooled numbers and listed this as
pending, and its §7 statement that criteria 1 and 4 are uncomputable for pooled still stands.

Care taken with the arithmetic: the pooled A/B is baseline→final, i.e. the FULL three-lever delta against a
60-tree/50k/d14/ncond-8/QRF=0 baseline, whereas the historic +0.037 I quote for conditioning is a matched
pair off `qrf-b6x2M`. Comparing those two directly would overstate the conditioning lever by ~2x. The
like-for-like figures are the full-stack ones: historic +0.087/+0.1766 vs pooled +0.0834/+0.2374.

This removes one of the two objections to promoting the artifact but NOT the important one: the pooled folds
are still `mod(hash(cell), k)`, and the env columns are bit-identical for a cell across the two scenarios, so
the interpolation-vs-transfer confound is untouched. Spatially blocked CV remains the gate.

## 2026-08-03 — the ssp370 second seed, finally: a second seed is a second SPIN-UP  [ADR 0041]

The task was narrow — "finally get the random seed 2 data, with the correct random seed and the correct
spinup" — and the reason earlier attempts kept failing turned out to be a single fact worth more than the
data: **`random_seed` is inert in any `-DFROM_RESTART` run.**

Established from primary source, not assumed. With `"new_seed": false` the per-cell RAND48 seeds are
restored from the restart file (`newgrid.c:507-513` -> `freadcell.c:37` `freadseed`) and the `setseed` that
would apply `config->seed_start` is gated off (`newgrid.c:520-521`). `seed_start` *is* applied once at parse
time (`fscanconfig.c:231`) but is then unconditionally overwritten from the restart header
(`openrestart.c:139-140`) with no consumer in between; its only trajectory-relevant consumers
(`iterate.c:108/148/181`) are unreachable at `nspinup:0`/`fix_climate:false`. The historic pair is
independent only because its 1000-yr spin-ups ran WITHOUT `-DFROM_RESTART`, taking `newgrid.c:460` whose
`setseed(grid[i].seed, seed_start+(i+startgrid)*36363)` is UNGATED — and that is literally readable in the
restart bytes (cell 156: `(13070,36533,86)` vs `(13070,36534,86)`).

So the broken member, which set `random_seed: 2` while restarting from the historic **seed1**
`restart_2019.lpj`, inherited seed1's exact state. Both `ind_2020_2100.csv` are 193 097 583 638 B and
md5-identical over six sampled MB windows; the historic pair, by contrast, differs in size and in all six.
The trap that let it live three weeks: with `new_seed:false` the log prints `Reading random seeds from
restart file.`, never `Random seed: 2` (`fprintconfig.c:748-751`). Nothing warned, and a floor built from it
returns `floor_r == 1` — fabricated headroom.

Fix: repoint `restart_filename` at the historic **seed2** restart. Kept `new_seed:false` deliberately —
flipping it would discard 1020 years of evolved RNG state at the 2019/2020 boundary, a discontinuity seed1
does not have, and would make the members differ in protocol as well as seed.

`lpjcheck` then caught something I had not looked for: **`ERROR100` on the co2 input.** The seed1 config
reads `~/scripts/clustering/climclusterpy_package/global_co2_ann_1700_2019_const_2100.txt`, and that
directory was repurposed for an unrelated project on 2026-07-28 — so the committed seed1 ssp370 config has
been unrunnable since, and nobody noticed. Recovered the file and proved its identity four independent ways
before using it: the git blob (its only version in that repo's history, added 07-13, deleted 07-28, so it
spans the 07-15 seed1 run unchanged); `/home/jamirp/.snapshot/weekly.2026-07-26_0015/` with **mtime
2026-07-07**, predating the run; byte-exact reconstruction from TRENDY v12 (1700-2019 verbatim, then 2019's
409.63 held flat); and agreement with ADR 0004. Installed at
`.../clustering/global/global_co2_ann_1700_2019_const_2100.txt`, md5 `ed5699b9c92d4d25857889f644b153db`. So
the provenance is FOUR edits off seed1, not three, and the forcing is content-identical.

An adversarial verification pass over the plan (7 agents) found three defects in the stock ground-truth job
file that I had copied without reading: `rc=0` + a bare `exit` (it **always** exits 0, so a run dying
mid-century leaves a plausible truncated 193 GB CSV behind a green `sacct` row), no module pinning (a purged
env leaves `libnetcdf.so.19`/`libudunits2.so.0` unresolved), and no `-D`. All three fixed. It also corrected
me on the binary: `bin/lpjml` is not "Feb-5 source + the daily-grass-GPP patch" but additionally a
**RHEL8->RHEL9 toolchain rebuild** (GCC 8.5.0 -> 11.5.0, GLIBC_2.14 -> 2.33/2.34). Two things I could
settle by reading — the patch is inert here (unopened outputs map to a dedicated trash slot,
`initoutput.c:50-67`) and no physics par file drifted (`find -newermt 2026-07-15` returns exactly the
patch's four files) — but neither proves trajectory equality.

**The gate I built to settle it came back VOID, and that is the most useful result of the session.** I ran
cell 42490 twice with the same binary, restart and forcing, varying only the cell set, with the 21-cell
block as a decomposition control:

| run | cell set | `ind` rows @42490 | first year != global truth | years matching |
|---|---|---|---|---|
| A | 42490 alone | 18 530 | **2021** (first step) | 2 / 81 |
| B | 42480-42500 | 19 366 | **2035** | 16 / 81 (contiguous 2020-2034) |
| truth | 67 420 @ 2048 tasks | 18 790 | - | - |

B is bit-identical for 15 consecutive years then diverges; A diverges immediately; at 2020 A and B already
differ in exactly `fpc_ind` and `isdead`. So **a subset re-run is not a per-cell replica of the global run**
— the *seek* is decomposition-independent, the *evolution* is not. Checked and ruled out the obvious
mechanism: the RNG is fully per-cell (`permute` takes `stand->cell->seed`, there is no `drand48()`/
`lrand48()` anywhere in `src/`, `config->seed` is read only in the unreachable spinup branches). I am NOT
claiming a mechanism; the pattern is what a stochastic gap model does to any perturbation once one
individual dies or establishes differently. This retires CLAUDE.md §3's implied per-cell reproducibility and
explains the previously recorded ~1.6e-4 `whc_nat` discrepancy as the same effect through a smoother
variable. It also means the decomposition confound is larger than the binary signal, so the subset gate can
never answer the cross-build question — replaced by a matched-decomposition full-grid 2048-task re-run of
the seed1 member (job 1678607), scored on `globalflux` (10 KB, 81-year global aggregate) and `vegc` (65 MB,
per-cell annual).

Consequence worth carrying: **a seed pair is valid only at the same binary AND the same `--ntasks`.** seed2
satisfies the second by construction. And this bears on line M, whose per-cell oracle work uses single-cell
re-runs — raised in STATE.md; the fact went to CLAUDE.md §3 (shared) rather than the M-owned
`fdiff-validate` skill.

Jobs left running unattended, fully chained so nothing needs a session present: `1678574` the corrected
member (2048 tasks / 16 nodes) -> `1678595` the independence gate -> `1678596` the parquet, plus `1678607`
the cross-build gate. `afterok` throughout, so a missing parquet means the parent died rather than that
nothing was scheduled.

Three reusable scripts captured rather than left as one-off commands: `build_slow_ind_parquet.py` (the
`ind`->parquet step had NO in-repo builder at all — the only one was the frozen sibling's
`global_extract.py`, whose `--which` is argparse-locked to three hard-coded names and so literally cannot
name a new scenario/seed), `diagnose_ind_seed_independence.py` (equal file size to the sibling is the copy
signature), and `diagnose_ind_binary_equality.py` (carries the decomposition control and exits 3 = VOID
rather than reporting a false verdict).

## 2026-08-03 — the address null was on the wrong basis, and the gate metric is nearly blind to warming (ADR 0040)

Picked up the handoff's item 3 (*"the decisive experiment and the gate on production: spatially BLOCKED CV"*)
and found, before spending any compute, that the decision rule it carried was wrong. ADR 0038 said *"decays
toward the 1-NN level (r≈0.80) ⇒ it is an address"*. That 0.80 is a pure address's skill under **hash** folds;
the fold-mode-matched null under `block(15°,5°)` is **0.140/0.210**. The rule was off by ~0.63 in r, in the
direction that would have declared a strong response an address — guardrail 7's reference-basis error, which
ADR 0033 already records this line making twice. Corrected and pre-registered in ADR 0040 *before* any forest
log was opened, which is the only thing that stops a decision rule being written after the outcome is known.

Two results came out of the zero-compute pre-registration and both changed the milestone's framing.

**The env tuple is not merely an address.** A 1-NN surrogate under the exact fold designs the forests run
(read from the Julia code, since `mod(hash(tile),k)` is not reproducible in Python) shows `env6` retaining
73 % of its hash-fold Wooddens skill under blocking (0.811 → 0.594) where a pure geographic address retains
21 % (0.837 → 0.140), and the conditioning DELTA staying ~invariant (+0.078 → +0.076/+0.058). So the screen
predicts, in advance, that the blocked forests will find the gain survives.

**But the gate metric was the wrong instrument all along.** `sd(Δobs)/sd(level)` is only 0.20–0.31, so
`emu_r` — a level statistic — is 3–5× more sensitive to spatial interpolation than to the warming response a
coupled run actually turns on. Measured from predictions that already existed: the shipped artifact **damps
the mean Wooddens warming shift by 37 %** (Rb −892 [−1022,−756] against +2433 observed) and captures only
24–62 % of the transient pattern against a 0.87–0.96 split-half ceiling. The available comparison arm is
4-lever confounded, so causation waits on the matched `p8` rung — but the spatial question turns out to have
been a proxy for a temporal one that is directly measurable and largely unmeasured.

Six adversarial reviewers ran on the design before it was built. Their most useful catches, all acted on:
`BUFFER_DEG=0` does not remove the mechanism under test (the block perimeter keeps 24.2 % of test cells within
1° of training data), `mtry` is a hidden fourth lever (`sqrt(p)` is 3 at ncond 8 and 4 at ncond 14, so every
published ncond-8-vs-14 comparison varied it too), the pooled baseline everyone assumed existed is a 4-lever
gap from the shipped rung and was mislabelled "60-tree" when the eval ran at 40, and `capacity/*env-qrf-b6x2M`
— the only prediction sets behind ADR 0038's numbers — were one `CAPTAG` reuse away from deletion. Also caught
a defect in my own control: the first `p14geo` basis had `geo_abs_lat` and `geo_cos_lat` at Spearman
−1.000000, so the address control was silently 5-dimensional while declaring `ncond=14`, biasing the
experiment toward its own hypothesis. Cancelled those two rungs, fixed the basis, and made the builder gate it.

One protocol note worth recording: a **concurrent line-S session** was running in this same worktree (it took
ADR 0039 for the ssp370 seed2 work and submitted the `S-FIT_ssp370_seed2` chain). Committed only my own files
by explicit path throughout.

## 2026-08-03 — the blocked-CV verdict lands: RESPONSE, and the gate that asked for it was mis-specified  [milestone S2]

- **Goal:** collect the six in-flight ADR-0040 forest rungs and apply the **pre-registered** rule without
  rewriting it now that results exist — the one thing the pre-registration was built to prevent.
- **Did:**
  - Collected all six rungs (all exit 0) plus the pre-existing hash-fold treatment arm
    (`pooled-env-qrf-b6x2M`, `1647661`), and verified the basis before adjudicating anything: the four tables'
    `cells.i64`/`scenario.i64`/`Y_*.f64` are **md5-identical**, blocked fold sizes are character-identical
    across arms C/D/F, hash fold sizes reproduce ADR 0040's published set, and effective `mtry` is 4 in all
    seven arms (`MTRY=0` at ncond 14 resolves to `round(sqrt(14)) = 4`, which is why the p8 arms pass
    `MTRY=4` explicitly). Ran the rule through three independent lenses plus three adversarial refutations.
  - **Fixed an inert `BLOCK_SALT` before spending compute on the replicate.** `eval_slow_copula.jl` reads it
    from `ENV` but the driver listed every *other* fold knob on the Julia command line and not that one, so a
    salt-1 rung rode on `sbatch --export=ALL` inheritance with nothing echoed. Had it stayed inert the
    replicate would have agreed with its sibling *exactly*, which does not weaken ADR 0040 §5's
    "NOT RESOLVABLE if the two salts disagree" clause — it **inverts** it into a false RESOLVED. Verified via
    `SUBMIT=no`, then proven at runtime: arm C′'s fold sizes `[14066, 8302, 13575, 11241, 11582]` genuinely
    differ from salt 0's `[15285, 10995, 11199, 8014, 13273]`.
  - Ran the §4 warming-response gate on the matched arms — the comparison ADR 0040 explicitly deferred — at
    **both** fold modes, then found and fixed a bootstrap defect and re-ran it (below).
  - Shipped `cell_env.parquet`, the per-cell env sidecar both handoffs listed as a standing blocker.
  - Submitted the salt-1 pair, the `mtry` 7/8 dilution rungs, and a chained `afterok` response gate.
- **Result / evidence:**
  - **VERDICT: RESPONSE — the six env columns are not merely a spatial address.** `[PROVISIONAL]` pending arm
    D′. Wooddens `Δ_blocked = +0.0315` [+0.0011, +0.0633], `P(≤0) = 0.021`, clearing the pre-registered bar
    `0.5·Δ_hash = +0.0201`; the blocked pure-position control sits **0.1868 below the treatment and 0.1553
    below no tail at all**, `P(fail) = 0.0000` in all five folds. The frozen 1-NN screen predicted ~86 %
    retention; the forests delivered 78/119/137 % on the three axes with a resolvable delta. Screen and
    forests were frozen in that order, which is the strongest evidence in the set.
  - **`p14geo-hash` 0.9231 > `p14env-hash` 0.9095 on all four axes** — under the *published* hash folds six
    pure-geometry columns reproduce and exceed the entire ADR-0038 gain. ADR 0038's doubt was well founded;
    the defensible conditioning figure is the blocked +0.0315, not +0.0402.
  - **ADR 0040 §4's attribution is refuted.** The matched ncond-8 arm damps the Wooddens warming shift
    **39.9 % on its own** (`Rb` −971.5 vs the tail's −892.0), so §5's promotion gate is simultaneously *met*
    and *mis-specified* — passable by a change that degrades the transient. Re-specified on `Rb`+`Rr`+`|Ra−1|`
    at both fold modes, under which the tail **fails**: `Rr` flips sign, +0.0395 hash → **−0.0305** blocked.
    **The two gates dissociate** — level delta survives blocking, transient-pattern delta does not.
  - **A bootstrap defect changed what could be claimed.** `diagnose_slow_address_prereg.py` built tile-cluster
    labels through a join returning rows in the latlon frame's order while `dp`/`dy` are in `group_by` order,
    with `tl[:min(len(tl), len(dy))]` hiding the mismatch — permuted labels degenerate a tile bootstrap toward
    an independent-cell one and **understate** the sd. Point estimates never touch the labels, so only the CIs
    were wrong; the detector was that a **fixed** seed gave two different intervals (jobs 1681338 vs 1681925 —
    I initially mis-read that as an RNG draw). Fixed and verified by running each gate twice and diffing
    (byte-identical, job 1683182). Intervals came back **3–5× wider**, so I weakened the ADR: blocked-fold
    damping is no longer significant, and **no inter-arm difference is resolvable from marginal CIs**.
  - **Measured the noise scale the whole rule rests on**, which ADR 0040 §7 asserted but never computed:
    **0.004–0.006 (hash) / 0.012–0.016 (blocked)** — the single "order 0.01" understates blocking ~1.6×. And
    `Δ_blocked` is **one-fold-dominated**: fold 0 carries ~84 % of it from 26 % of the cells, and it is the
    fold with the fewest training cells. Under hash folds the same quantity is stable to 0.0011 across folds.
  - **Width costs skill at matched `mtry`**: `p14perm-hash` is below `p8-hash-mtry4` on every axis (Wooddens
    −0.0201, z ≈ 9). Fourteen zero-information columns are worse than eight.
  - `cell_env.parquet`: 67 420 cells (superset of the pinned 58 766), **gated on exact float64 equality against
    the shipped `Xc` tail over 200 000 real rows**. The gate fired first time and caught a real train/inference
    shift — four of the six columns are `Float32` and polars' `group_by().mean()` accumulates in `Float32`,
    putting the naive aggregation 3.35e-07 relative off the trained values on 199 093/200 000 rows.
- **Decisions:** **ADR 0042**. Corrects two ADR-0040 statements (`eco_diag_gdd_5`/`tas_cold_month` *are*
  transient on `pooled_w20`; the noise scale) and forbids quoting the retention ratio (0.783 ± 0.411) or
  blocked `sd_ratio` against criterion 2. **0039 is permanently vacant.**
- **Dead ends / mis-steps worth recording:** I attributed the two response-gate runs' differing CIs to an RNG
  draw before checking that the seed was fixed — the refutation pass caught it. And the handoff's claim that
  the augment script's `ENV_PARQUET` seam "already accepts" a per-(Cell,Year) join is **wrong**: it is keyed on
  `Cell` alone (`group_by("Cell").mean()`, broadcast by cell index), and the copula tables carry no per-row
  `Year` to join on. A *scenario*-resolved tail is the tractable middle path, since `scenario.i64` already
  exists per row.
- **Next:** see `lines/S/STATE.md` `## NEXT`.

## 2026-08-03 (late) — Track A's member was HUNG, not slow; caught it in a close-out check  [milestone S2 / ADR 0041]

- **Goal:** final state check before ending the session.
- **Did:** looked at Track A's progress rather than just its SLURM state, and found job `1678574`
  (`S-FIT_ssp370_seed2`, 2048 tasks) had produced **nothing** in 67 minutes — 0 output files, 0-byte stdout,
  0-byte stderr, and an output-dir mtime still 6 h older than the run's own start. `sstat` reported no CPU/RSS
  for its step. The decisive evidence was a **matched control** that happened to be running concurrently: the
  crossbuild gate `1678607` — same binary, `mpirun`, `--ntasks=2048`, `--exclusive`, same `-DFROM_RESTART` —
  had written **30 GB in 12 minutes**. And `cso14c74`, the node that killed jobs `1680828`/`1681087` earlier
  today with the documented `0:53`/no-log signature, was in its allocation. Cancelled it, resubmitted the
  member with `--exclude=cso14c74` **on the sbatch command line** (leaving the jcf byte-identical, because ADR
  0041 records this member's provenance as exactly four edits), re-chained both `afterok` children onto the new
  id, and cancelled the two orphans left `DependencyNeverSatisfied`.
- **Result / evidence:** the resubmission `1684567` started immediately into the freed allocation and was
  **verified healthy: 7 output files, 833 MB, within 15 seconds** — including a preallocated 784 MB
  `mnpp_2020_2100.nc`. Against that 15-second baseline the original's 67 minutes of silence is a **268×**
  discrepancy, so the hang diagnosis is not a judgement call. New chain: `1684567 → 1684568 → 1684569`.
- **Decisions:** none new; this is ADR 0041's member being re-run on a different node set.
- **Why it mattered:** left alone it would have burned ~2 h 20 m × 2048 CPUs and then cancelled both chained
  children, and the next session would have found a dead chain with no explanation — the jcf itself is correct.
- **The generalisable lesson, now in CLAUDE.md §3:** "judge a C run from its log, not SLURM state" is
  insufficient when the log is *empty*, because empty is indistinguishable from starting-up. The **output
  directory** is the absolute progress signal — a healthy run populates it in ~15 s — and a concurrently
  running same-config job is the ideal control. Also corrected my own earlier report in this session, which
  said Track A "needs nothing from this session".
- **Next:** `lines/S/STATE.md` §F, which now carries the new ids and tells the reader to query SLURM rather
  than trust any state written down.
