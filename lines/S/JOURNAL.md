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

## 2026-08-04 — Track A closed, the cross-build question answered, and the first ssp370 noise floor

Picked up a handoff that said "check SLURM first, don't trust the state here" — correctly, because the
state had moved. The C member (`1684567`) had finished cleanly, but its chained independence gate
(`1684568`) had **failed in 1 second** and left the 92 GB parquet child stranded on
`DependencyNeverSatisfied`.

**The gate failure was spurious.** Three of its four checks passed (sizes differ 0.1255 %, all 6 sampled
windows differ, final year 2100); only the completion check failed, with `no completion line at all`. The
run's actual log says `lpjml successfully terminated, 67420 grid cells processed.` The cause: when the
previous session resubmitted the hung member with `--exclude=cso14c74`, it re-chained the children onto the
new job id but left `--log …lpjml_2020_2100.1678574.out` — the **cancelled** attempt's 0-byte log — pinned in
the child jcf. The gate was reading the corpse of the run it was meant to judge. Re-run against the real
log: **PASSES all four checks.** Fixed at the root rather than by hand: `--log-dir <run_dir>` resolves the
newest non-empty `lpjml_*.out`, and a 0-byte log is now a distinct FATAL (exit 2) instead of a gate failure —
because "empty" and "unfinished" were indistinguishable, which is what made a passing member look failed.

**`ind_ssp370_seed2_all.parquet` ships**: 91.88 GB, 1 028 945 462 rows, 63 398 cells, 10 distinct `Type`
(the complete ADR-0031 basis). Against its seed1 sibling's 1 030 175 289 rows that is −0.1194 % — non-zero,
so not a clone, and small, so a real seed pair. Track A is complete.

**The cross-build gate (`1678607`) PASSES, and by more than it was asked to.** ADR 0041 specified comparing
`globalflux` + `vegc` against the seed1 truth. `globalflux` is `cmp`-identical. `vegc` differs by 124 B at
byte 172 — which turned out to be **only the `history` attribute** (a wall-clock timestamp and the config
path); all seven variables including the full 81×280×720 `VegC` field hash identically. So a file-level `cmp`
on a NetCDF output is the wrong test, and that is now in CLAUDE.md. The decisive one was unplanned: the
**193 GB per-individual `ind` roster is `cmp`-identical over all 81 years.** That is the finest grain the
model emits and precisely the quantity ADR 0041 showed amplifies any perturbation into a permanently
different row count — so the two builds don't merely agree in the mean, they produce the same individuals.
**ADR 0043.** Deleted the gate's redundant 193 GB CSV afterwards (−181 GB), but only after proving its
bit-identity to the retained original.

**Then the first ssp370 noise floor.** The obvious next step per the handoff was the pooled seed2 copula
tables, but the floor script's *definitive* basis 1 needs "static boundary, **no STEM_CAP**", and the
arithmetic says that path is not simply submittable: there is no ssp370 seed2 copula table at all, the
existing seed1 `slow_copula_ssp370_t8` is **capped** (22.3M ≈ 400×58 683) where historic is not, and an
uncapped ssp370 build is ~870 M stems ⇒ 91 GiB in numpy alone before the polars frame — several hundred GB
peak, twice. The cap can't just be left on either: `build_slow_runtime_table.py:380` hashes with the **data**
SEED and subsamples whole patch-years, so two capped tables keep *different* clusters and the extra noise
lowers `floor_r`, flattering the emulator. So I did not launch a six-hour job on hope; §E1 records the
option space (including a `CAP_HASH_SEED` decoupling that would cost 1/40th the size) for a deliberate ADR.

What *was* reachable: the `tree7` parquet basis, which needs only the two `ind` parquets. Parameterizing it
took three careful changes — `IND_SEED1`/`IND_SEED2` overrides (defaults unchanged so every published number
stays byte-identical), a `SKIP_COPULA` floor-only path, and two guards that the parameterization made
load-bearing: the streamed `group_by` had **no key-set assertion** (ADR 0036 §5b — a duplicated `Cell` fans
out every join in the script and silently re-weights the floor, invisible to a `before − after` check), and
the bit-identical-seeds FATAL lived only in the copula path, so `SKIP_COPULA` would have routed straight
around the fabricated-floor guard.

Result (57 295 cells, both guards silent): SLA **0.975** · Wooddens **0.944** · D95max **0.837** ·
minwscal **0.978**; COUNT 0.9895. Against the historic `tree7` floor (0.965 / 0.923 / 0.895 / 0.973) three
axes rise and **D95max falls 0.058**. That matters because ssp370 pools 81 years per cell against historic's
20, so ~4× more averaging should raise `floor_r` mechanically on every axis — D95max falls *despite* the
tailwind, so rooting-depth trait medians are genuinely less reproducible between realizations under warming
and the true effect exceeds −0.058. It was already the weakest axis; it is now the clearly RNG-limited one.

## 2026-08-04 (late) — Phase 3A Stage 1: the hazard is ported offline, and the confound pre-flight found a different confound  [ADR 0047 / 0048]
- **Goal:** handoff items A (port the hazard offline and gate it) and D (measure the k-cap merge trait
  confound before touching the runtime).
- **Did:** `src/trait_mortality.jl` (`module TraitMortality`, no call site) ·
  `scripts/build_mort_params_reference.py` → `test/testitems/references/S_pft_mortality_params.csv` ·
  `test/testitems/slow_trait_mortality_tests.jl` · `python/tests/test_mort_params_reference.py` ·
  a `gate_pft_params_against_reference()` called at import in `build_slow_flux_table.py` ·
  `scripts/kcap_merge_confound_probe.jl`.

**The parameter table is generated, not transcribed, and that is what paid off.** LPJmL parses its own
`.js` parameter files by piping them through `cpp` (`openconfig.c:28` `#define cpp_cmd "cpp"`, `popen` at
`:467`), so `cpp -P` + a trailing-comma strip + `json.loads` reproduces the authoritative macro expansion
exactly. The self-check against CLAUDE.md §3's hand-read table passed on all seven rows — and then the
parse turned up **two facts nobody had recorded**. Larch (id 6) declares `aphen_min`/`aphen_max` **twice**:
the macro defaults at `:1001-1002` (60/245) and an override pair at `:1003-1004` (10/200). LPJmL reads
parameters through json-c's `json_object_object_get_ex`, and json-c's tokener inserts each pair with
`json_object_object_add`, which *replaces* — so the last occurrence wins and larch's effective `aphen_min`
is **10**, six times earlier water-stress accumulation than every other tree PFT. `json.loads` agrees,
which is the only reason the parse is faithful, so the builder now **enumerates** duplicate keys and
asserts the set is unchanged: a future silent override has to be read deliberately. Second: `sla_median`
(0.01986) is a single global default and lies **outside** `[low, high]` for ids 1/2/3/5 — so it is not a
central value of the interval recruits are drawn on (ADR 0045).

The Julia and Python tables both gate against the one CSV. The pytest exists because `scripts/*.py` is
watched by **no** CI gate (ADR 0090), so the builder's import-time assert would only fire when somebody ran
the builder; and it carries a **mutation test** (perturb one `wdmort_1`, require the assert to fire),
because ADR 0032 is the record of a check that could never fail hiding a two-order-of-magnitude basis shift
for five days.

**One test I had to throw away and rewrite, which is the more useful note.** My first version of the
non-sign-definiteness test invented a `greff ∝ 1/wooddens` relation and asserted the total hazard rises
with density. It fails: `0.01·greff` is tiny at greff ≈ 20, so `mort_max` dominates and the dense tree is
strictly safer. I was asserting my own toy growth model, not the C. The honest form is that the logistic
**factorizes** (`mort_npp = mort_max(wd)·f(greff)`), so the density advantage is exactly the `mort_max`
ratio 1.765 and the crossover is the greff where `f(g_light)/f(g_dense) = 1.765` — solved by bisection in
the test at **≈172**, which sits inside FIT's measured `growth_eff` distribution (global mean 146.7, max
31 183, CLAUDE.md §3). So the flip is reachable in the real model, and the test now fails if anyone
"simplifies" the logistic away — without asserting anything I made up.

**Then item D, which returned a null and then a different answer (`1694397`, exit 0).** The literal
instruction — default `k_cap` vs `typemax(Int)`, diff the community wood-density trajectory — gives
Δ = **exactly 0.0 in every year of a 150-yr rollout, in both copula arms**. Not because the merge is
harmless: because **it never fires**. `k_cap = max(2·K_initial, 40)` needs the roster to double, the roster
grows by ≤1 cohort per establishment year, and establishment fires in only 12–14 of 149 years (roster
17 → 29/31, then frozen). Publishing that null would have retired a live defect on a vacuous measurement.
Adding a TIGHT arm (`k_cap = 20`, just above the initial roster) forces it: the merge then moves the
community mean by up to **12 375 = 5.09×** the FIT warming shift (copula off) / **7 627 = 3.13×**
(production copula on). So `_merge_pair!`'s dominant-parent trait inheritance is **dormant, not harmless** —
Stage 2 is unblocked without fixing it, with an explicit re-check trigger. (The +6.0 % Σnind gap between
arms is *not* non-conservation: the merge conserves Σnind within the call, but the merged roster changes the
`lai`/`fpc`/`age_mean`/`n_living` the DRF is conditioned on, so the count target diverges. Carbon closes at
~1.3e-11 in every arm.)

**And the measurement I did not go looking for is the one that matters most.** The merge-disabled reference
arm is a rollout under **constant forcing** — the same year repeated, no climate signal of any kind. Its
community wood density still moves **−3 267 = 1.34× the FIT warming shift, in the OPPOSITE direction,
settling at year 52** (production config; +9 273 = 3.81× with the copula off). That is a relaxation from
the C-derived initial state to the emulator's own fixed point, and it is larger than the signal and on the
same timescale as the 80-yr historic→ssp370 window. ⇒ **every Stage-2 response arm must be differenced
against a matched constant-forcing control re-run in the same generation, and measured past the
transient** — handoff item F's discipline, now with a number attached to why. Recruitment dilution gives
`e` = 0.0106 (firing years) / 0.0010 (run mean) ⇒ **τ = 94 / 1 003 yr**, only ~14 % of the population
replaced in 150 years: an upper bound on how fast any recruit-mediated fix can act, and a second,
independent reason to prefer the mortality lever over the entry marginal.
- **Result / evidence:** probe jobs `1694111` (script error, soft-scope `worst_share`), `1694359` /
  `1694373` (same numbers, pre-reporting-fix), **`1694397` exit 0** (the reported run). Suite
  `1694467`. `python`: ruff + ruff-format clean, 56 pass / 6 skip locally. Runic clean over all tracked
  `.jl`. The reference CSV round-trips (`CHECK=1` is byte-identical).
- **Decisions:** ADR 0047 (the offline port + the ONE generated parameter table), ADR 0048 (the merge is
  dormant not harmless; the constant-forcing drift is the real confound).
- **Next:** Stage 2 — wire the hazard in behind an opt-in flag, with the ADR-0046 §3 per-PFT age–wooddens
  gradient as the acceptance target and an ADR-0048 constant-forcing control as the baseline. Mirrored into
  STATE.md's NEXT block.

## 2026-08-05 — Phase 3A Stage 2: the hazard is wired in and it selects; the COUNT CHANNEL is what bounds it  [ADR 0049 / milestone S7]

- **Goal:** the handoff's items A–C in order — build the ADR-0046 §3 acceptance target as a fixture, wire
  ADR 0047's ported hazard into `reconcile_demography!` behind an opt-in flag, and measure it the ADR-0048
  way (matched constant-forcing control, same generation, scored past yr 52).

**B first, and building the fixture refined the ADR it came from.**
`scripts/build_age_wooddens_gradient_reference.py` → `test/testitems/references/S_age_wooddens_gradient.csv`
(93 rows: scenario × PFT × age bin, mean/median `Wooddens` and `SLA`, on byte-for-byte the basis that
produced ADR 0046 §3 — survivors only, no stem filter, fixed edges 10/20/40/80/160/320). It **asserts** the
five rows ADR 0046 published reproduce to 1 gC/m³ and they do exactly (id 1: 184 869.3 → 331 234.4 vs the
ADR's 184 869 → 331 234), so the fixture is provably the ADR's target rather than a second measurement of
it. Two facts fell out that ADR 0046 did not state and that change how an operator must be scored: **id 2
is non-monotone too** (rises to 273 634 at bin 2, dips to 264 692 at bin 3, recovers to 287 639) *despite*
a positive one-year selection differential — so "the sign of `S` predicts the gradient's shape" has a
measured exception; and **the age axis is PFT-dependent** — id 5 has **no stems above 160 yr at all**
(longevity 125, the row a beech default used to get wrong) and id 2 none above 320. A gradient test that
assumes seven bins per PFT is testing the wrong thing for two of the seven. Job `1698771`.

**A — the call site, and the one design question that actually mattered.** The constraint pair was fixed in
advance (the hazard picks *which* cohorts die; the DRF keeps *how many*), and the obvious implementation is
a linear rescale `f_i = λ·(1 − mort_i)`. I rejected it: it needs a clamp against `f_i > 1` (mortality that
*creates* individuals) and it distorts the ratio between two cohorts' survival by a different amount for
every pair, so it is not a hazard at all. What went in is FIT's own object scaled — a **proportional-hazards
tilt** `f_i = (1 − mort_i)^θ = exp(−θ·H_i)`, θ bisected so `Σ nind·f_i = ρ·Σ nind`. Bounded in [0,1] by
construction, order-preserving, deterministic and order-independent, and it **recovers FIT exactly at
θ = 1** — which is a test, not an intention. A hard kill is never resurrected to reach the count target; the
miss is reported as a `shortfall`, and the test suite's first run caught that the *mirror* unreachable case
(a hazard that is zero everywhere, so there is nothing to tilt) was returning shortfall `0` — i.e. reading
as "the count target was honoured" in the one year it could not be. Fixed in the operator, not in the test.

`mort_water`/`mort_temp` are **zero by decision**: the emulator has neither stress integral on FIT's basis,
and `grow.water_stress` = `1 − wscal_mean` is a different quantity on a different scale (ADR 0051 is the
precedent for what mapping those two costs). The cost is bounded and stated — `mort_temp` is not
trait-dependent at all and `mort_water`'s only per-cohort variation is a per-PFT factor, i.e. composition
rather than the within-PFT channel ADR 0046 named as the lever, and both hazards' level is absorbed by θ.

**C — the measurement, and the finding I did not expect.** 150 yr, production copula, default `k_cap`, arm
and control differing in *exactly* the flag and both re-run in the same process: controlled Δ community
`wooddens` = **+7 899 = 3.25× the FIT shift, same sign**, carbon at 3.0e-11 (control 1.9e-11), count target
honoured every year (Σnind matches the control to 1.4e-13), 0 hard kills, 0 k-cap merges in either arm, and
the age–wooddens gradient rises with age as required — **+6 565** in the 80–160 yr bin, **+9 642** in
160–320. That is the ADR-0046 §3 signature: selection accumulating over a lifetime, not a level offset.

**But the tilt distribution is the real result.** θ is bimodal at ~0 — median **8.5e-12**, θ > 0.5 in only
**18 of 132** thinning years (13.6 %). A forest prediction is piecewise constant, so the DRF's demanded
`|ρ−1|` has **median 0.0 %/yr** against the ported hazard's own 1.688 %/yr (mean ratio 2.8×). FIT's deaths
and recruits **CO-OCCUR** every year — a near-stationary count with large gross turnover — while the
emulator's `ρ<1` XOR `ρ>1` branches make gross turnover *equal* net change, so a zero-net year is a
zero-selection year. Selection scales with GROSS deaths, so a faithful hazard in a net-only demography is
throttled by its duty cycle. That is a structural limit of ADR 0024's roster, not a fidelity gap in ADR
0047's port, and it re-derives ADR 0048 §4's τ = 94/1 003 yr from the other end. **Co-occurring gross
turnover is the named next lever** — and it is exactly what item E forbids bundling into this arm.

I also wrote down what this is NOT: a constant-forcing **LEVEL** change on ONE cell is not a warming
response (FIT's +2432.9 is between-scenario), and none of it may be quoted against the ADR-0044 gate.

- **Result / evidence:** gradient fixture `1698771`; arm probe `1698789` (5 yr validation) / `1698791` /
  `1698795` (150 yr, with the duty-cycle diagnostic). Suite `1698797` **red — 2 fails + 1 error, all in the
  new testitem** (a `NaN != NaN` θ comparison, three wrong `Individual` field names in a Float32 block, and
  the real shortfall gap above), then `1698873` **green: 107 749 pass / 0 fail / 4 broken**. Runic clean over
  `src test ext scripts`. Docs built locally (`1698958`) because `docs` never runs on a branch.
- **Decisions:** ADR 0049 — trait-dependent mortality is wired in and selects; the DRF count channel, not
  the hazard, bounds what it can express. **This exhausts the S ADR block 0030–0049.**
- **Next:** the response arm (does Δ differ between historic and warmed forcing? needs the ADR-0026/0027
  transient boundary on both arms), and then co-occurring gross turnover as its own arm. Both need a new ADR
  range — raise it as an integration point before writing. Mirrored into STATE.md's NEXT block.

## 2026-08-05 — the RESPONSE arm: the operator is right, the recruit channel is not  [milestone S7 / Phase 3A Stage 3]

- **Goal:** the measurement ADR 0049 declined to make — does the trait-mortality operator change the emulator's
  wood-density response to *warming*, not just its level under constant forcing? (Handoff item B.) Plus item A:
  the S ADR block was exhausted at 0049.
- **Did:**
  - **Item A first, as the handoff demanded.** Allocated a **tier-2 ADR block per line** in
    `docs/decisions/README.md` + `CLAUDE.md` §9 (S 0100–0119 · M 0120–0139 · E 0140–0149 · O 0150–0159 ·
    integrator 0160–0169), rather than only claiming S's. A pre-allocated tier means no line has to negotiate a
    range mid-milestone again, and two lines exhausting in the same week cannot collide. Flagged to the
    integrator in this entry + STATE.md rather than blocking on it.
  - **New extractor `scripts/build_hainich_response_forcing.py`** (7 s): real daily forcing for BOTH scenarios
    at one cell from the same orderA `.clm` files the two ground-truth runs read — historic 1939–2019 and
    ssp370 2020–2100, 81 yr each so the arms difference at matched year indices. It **imports**
    `build_transient_boundary.py`'s `open_clm`/`gdd5_tcm` rather than re-deriving them. Three gates, all green:
    it reproduces `climbuf_hainich_boundary_w20.csv` (4.9e-06 on a gdd5 of 1800 = a float32 print artefact) and
    **`hainich_forcing_2010.csv` — the fixture Stage 2 itself was measured on** (≤1.8e-05 on all five
    variables, which is what proves the cell index, the YEARCELL decode, the v2-int16-×0.1 vs v3-float32 branch
    and the units), and it asserts ADR 0004's flat 409.63 ssp370 CO2. Contrast at Hainich: **+2.45 K,
    +709 gdd5, +2.53 K coldest month**. Daily forcing → `/p/tmp` (1.7 MB/scenario); only the 16 kB per-year
    summary + boundary is committed (`S_hainich_response_boundary.csv`), with a new testitem guarding it.
  - **`MODE=response` on the existing probe** (the handoff said add a knob, not a fourth harness): the 2×2, all
    four rollouts in one process, double difference. `rollout(...)` gained `forcing`/`boundary_series`/
    `t_soil0`/`k_cap`, all defaulted to the Stage-2 construction.
- **Result — the operator's response contribution is +3 400.6 gC/m³ = +1.40× the FIT shift, right sign**
  (job 1700471/1700508/1700629, merge dormant, carbon 0.8–1.6e-11). Phase 3A's mechanism claim is complete.
- **THE FINDING, and it reframes the line: the emulator's BASELINE warming response has the WRONG SIGN.**
  `R_ctl` = −5 945.8 = **−2.44× FIT** where FIT *rises* +2432.9. The hazard shrinks that wrong-signed response 57.2 % in
  magnitude — 40.6 % of the gap to FIT — and cannot flip the sign. Attribution is near-forced — ρ-thinning is composition-preserving and the merge is dormant, so
  `R_ctl` IS the recruit channel — and the band diagnostic localises it: **`soilmoist` runs 0.658 band widths
  below anything the historic-only copula saw, a 16× larger excursion than the historic arm**, and an
  out-of-band forest **saturates** rather than extrapolating. It also **excludes** `water_stress` (worse under
  historic, ratio 0.49×), so line M's known defect is not the driver.
- **Two protocol decisions each moved the answer by more than a FIT shift, and both are the interesting part:**
  1. **The k-cap merge, dormant for 150 constant-forcing years, WAKES under real forcing** — 8–9 merges/arm at
     the default cap, and it **destroys 54 % of the response contribution** (+0.638× vs +1.398×). ADR 0048's
     "the merge is dormant" is a property of a *forcing configuration*, never of the cap. Raised `K_CAP` to 400
     for the primary and demoted the default-cap run to a sensitivity check.
  2. **A terminal-year read would have reported +2.21× instead of +1.40×.** With real interannual forcing the
     year-to-year interaction swings −1 070 → +5 388; FIT's +2432.9 is a run mean. Headline is now a 20-yr
     window mean with the terminal read printed beside it.
- **Two more measured facts worth carrying:** ADR 0049 §5's **13.6 % duty cycle is a constant-forcing
  artefact** — real forcing gives 54.2 % (historic) / **62.5 %** (ssp370), i.e. **warming loosens** the
  count-channel throttle (|ρ−1| 1.87 → 2.18 %/yr), so the gross-vs-net mechanism stands but its cost was ~4×
  overstated; and the transient boundary is **exactly inert** (max |Δwd| = 0.0) for this cell's demo artifacts
  because both boundary axes are constant in training — the same fact the band table reports as `Inf`, which is
  why an excursion ranking must special-case a zero-width band or it ranks the one harmless channel top.
- **Dead end avoided:** a synthetic ΔT ramp. The real files cost 7 s and remove every "that isn't ssp370"
  objection. Also resisted fixing `R_ctl` in this arm (handoff item F) — it is a recruit-channel defect with its
  own ADR and its own control.
- **Verification:** `MODE=stage2` regression job **1700483** reproduces **every** ADR-0049 headline number
  (132/150 thinning yr, θ median 8.453e-12, 0 merges, worst 11 256.4 at yr 46, +7 899.35 = 3.2469×) — guardrail
  4 by measurement, not intention. Suite 1700639 with the new testitem; Runic clean; ADR 0100 written.
- **Next:** re-run this 2×2 against the existing global `pooled_w20` `.rcop`/`.drf` (no new training) — the
  falsifiable prediction is that `|R_ctl|` shrinks or flips, which would also lift the boundary-inertness null.
  Mirrored into STATE.md's NEXT block.
- **One red test, and it was the ASSERTION that was wrong (the ADR-0049 §G reflex, applied):** the new
  fixture testitem asserted `s.boundary == series[1]` while also passing an explicit `boundary = bnd`. ADR 0026's
  documented rule is that an **explicit** `boundary` is kept as given and only an **omitted** one is seeded from
  the series' first row — so the code was right. Fixed by pinning **both** directions (explicit ⇒ kept; omitted
  ⇒ seeded), which is a better test than the one I meant to write: a silent year-0 offset here would put the
  first simulated year on the wrong bioclimate, and nothing else in the suite would notice.
- **Second self-caught defect, in the FIXTURE this time — the trailing window had no lead-in.** The committed
  boundary's first 19 historic years were computed on a **truncated** window (1939 got a 1-year "climatology",
  reading `tas_cold_month` = −3.11 °C instead of **−0.54**), because the monthly means were built from the same
  1939–2019 slice as the daily output. The historic `.clm` starts **1901**, so a full W=20 window is available
  for every target year ≥ 1920 and there was no reason to accept the truncation. Fixed with a W−1 year lead-in
  read (19 rows moved; gates 1–3 still green; the last-20-yr contrast unchanged at +709.3 gdd5 / +2.526 K).
  ⚠ The ssp370 side **deliberately keeps** the short window for 2020–2034 — that is `build_transient_boundary.py`'s
  documented edge and therefore the basis the artifacts were TRAINED against (ADR 0023), so "fixing" it there
  would break train/inference consistency. *Gate 1 did not catch this*: it checks 2000–2019, where the window is
  already full. A gate that only samples the easy end of a range does not cover the range.
- **The fixture fix became a free second test of the inertness claim:** re-running the primary on the corrected
  boundary (job 1700644) returned **every headline number identical to the digit** (`R_ctl` −5 945.79, `R_arm`
  −2 545.21, interaction +3 400.58) — 19 changed boundary rows moved nothing, exactly as ADR 0100 §4 predicts.

## 2026-08-05 (later) — the response arm was one draw: replication withdraws Stage 3, and the baseline defect was CELL SCOPE  [ADR 0101 / Phase 3A Stage 3, corrected]

Picked up ADR 0100's handoff ACTION A — re-run its 2×2 against the global `pooled_w20` artifacts, with the
pre-registered prediction that `|R_ctl|` shrinks or flips. The previous session had already made the enabling
edit (the `DRF_ART`/`RCOP_ART` knob) and left job **1701183** in the queue; its result was sitting unread.

- **The prediction confirmed, and then dissolved.** Pooled seed 1: `R_ctl` −1.94 (−0.0008× FIT, from the
  demo's −2.44×), `R_arm` +1 836 (+0.755×), interaction +1 838 (+0.756×), every runtime feature **0.0
  excursion** including `soilmoist` down to 0.587. That looked like a clean win for "the training scenario was
  the defect" — so I built the ladder that tests it instead of assuming it.
- **The ladder falsified the attribution.** A **global HISTORIC-ONLY** artifact — same scenario as the demo,
  different cell scope — already gives a *correctly signed* `R_ctl` (+0.619× at seed 1). Ensembled, the two
  contrasts separate cleanly: cell scope **ΔR_ctl = +1.651 ± 0.386, t = +4.28**; scenario coverage
  **−0.417 ± 0.403, t = −1.03**. The mechanism is in the metadata — cross-**cell** pooling widens the
  `soilmoist` trained band **4.79×**, adding the whole ssp370 scenario widens it **−0.04 %**. ADR 0100 §5's
  *measurement* was right and its *causal reading* was wrong; the fix it predicted does nothing, and the fix
  that works (use a global artifact) was already in the production pipeline.
- **Then the control that changed the whole conclusion.** Re-running the pooled arm on the *other* legitimate
  per-cell seed (`n_init` 7.0 / `age0` 46.0 — the ssp370 sub-table's own values for this cell) returned
  **−4.08× FIT**. Decomposing it: `n_init` is the fragile one (6–7 hard kills + a count-override year), but
  `age0` 43.556 → 46.0 fires **nothing** and *still* moves the contribution from +0.756× to +0.017×. A 2.4-year
  change in a stand-age seed, every diagnostic clean, 44× change in the answer. At that point the honest
  reading is that the estimator, not the operator, was under measurement.
- **So I exposed `SEED` (hard-coded to 1 through ADR 0100) and replicated.** 32 jobs, three artifacts. The
  double difference has a **seed sd of 0.67–1.74× FIT — the size of the effect**. Consequences:
  - **the operator's contribution to the warming response is indistinguishable from zero on BOTH global
    artifacts** (+0.048 [−0.380, +0.476] and +0.263 [−0.377, +0.903]), and **both CIs exclude ADR 0100's
    +1.40×**. Even on ADR 0100's own artifact the 8-seed CI [−0.100, +2.812] straddles zero. **Stage 3's
    response claim is withdrawn.**
  - **ADR 0049's LEVEL claim is confirmed and strengthened** (+6 718 ± 286 / +7 041 ± 334 / +8 959 ± 862
    gC/m³, t = 10.4–23.5). Replication makes exactly one of the two claims stronger, and it is not the new one.
  - **ADR 0100's headline finding is a single-cell FIXTURE artefact and the sign REVERSES on a global
    artifact**: `R_ctl` −1.234 [−2.058, −0.411] (demo, significant) vs **+0.417 [+0.050, +0.784]** (global
    historic, FIT's own sign) vs −0.000 ± 0.367 (pooled). The deployment defect is milder and different — *no*
    warming response where FIT has +1× — and it is a conditioning-set question, i.e. S2.
- **Fair to ADR 0100:** its +1.398 is 0.03 from its artifact's 8-seed mean, so it was a *fair draw*, not an
  outlier or a bug — and `SEED=1` reproduces it to the digit (−5 945.79 / −2 545.21 / +3 400.58), which is how
  I know the ensemble is a superset of that measurement rather than a different harness. The error was
  treating one draw as a measurement, and reading an excursion diagnostic as a causal attribution.
- **A provisioning defect fell out of the seed control.** The `pooled_w20` artifact **ships no
  `cell_meta.parquet`** — its meta names one that does not exist — and its two training sub-tables disagree on
  this cell's seed, a **4.5× FIT** swing. `M_slow_init_meta.json` silently resolves it to the well-behaved
  branch (nothing is broken in M's pin today) and takes its **boundary row** from `slow_runtime_historic_t8`,
  a table the pinned artifact was never trained on (gdd5 1 863.7 vs the training basis's 1 698.0) — while that
  artifact's boundary channel is worth **3 165 gC/m³ = 1.30× FIT** on ensemble average. **S→M integration
  point #2**, raised, not landed.
- **Two hard-coded messages in the probe asserted the DEMO artifact's properties as if they were the
  harness's** and had to go: "not inert ⇒ out-of-band extrapolation" *mis-reported the correctly-trained
  global artifact as the broken one*, and "the boundary rows read `Inf`" is true only of a zero-width band.
  Worth remembering as a class: a diagnostic message that hard-codes one configuration's answer will
  confidently mislabel the configuration you introduce to test it.
- **Also measured, so it cannot be re-litigated:** ADR 0100 §4's boundary inertness is **exact** — 0.0 in all
  8 demo seeds — and a *fixture* property; the globals run 1 105 / 3 165 gC/m³.
- **Captured** (§8 gate): `scripts/run_response_seed_ensemble.sh` + `scripts/summarize_response_seed_ensemble.py`
  (the summarizer derives the three response numbers from the four 2×2 corners and **self-checks** them
  against the log's printed ×FIT values — it caught my own unit bug of re-scaling an already-scaled ratio —
  enforces both preconditions by *exclusion*, and refuses to mix artifacts or initial conditions in one
  ensemble); committed fixture `S_response_seed_ensemble.csv` (32 rows) gated by
  `test/testitems/slow_response_ensemble_tests.jl`, which asserts the 2×2 identity per row, both
  preconditions, and the withdrawn claim itself (both global CIs straddle 0 *and* exclude 1.40×).
- **Next:** S2 (the conditioning set) is now the only lever Phase 3A's finding points at, and the ADR-0044
  global gate is the only instrument that can carry a response claim — with the replication cost now measured
  (~115 seeds for the effect size seen at one cell).

## 2026-08-05 (later still) — line M's "unanchored" is three defects, my hypothesis was the empty one, and the real one is that the stand has no LEVEL  [ADR 0102 / milestone S8]

- **Started by reading the handoff against the repo rather than trusting it, and the handoff was stale in one
  important way.** `lines/S/STATE.md` listed `fc.pft_ids` as "still unraised with M" — it was raised on
  2026-08-04 and is sitting in `lines/M/STATE.md`. More importantly, **line M had raised an INBOUND
  integration point at S that S's own NEXT block never recorded**: ADR 0054's *"the count recursion is
  unanchored … raise it with S rather than editing"*, with M's note that it "matters more than any remaining
  F-side item". S's queue said the next lever was S2. M's said the next lever was S's file. M was right.
- **My leading hypothesis was wrong, and measuring it first is the only reason it did not ship.** Reading
  `slow.jl` I found what looked like the defect: `:1026` clamps `ρ = clamp(target/n_prev, …)` and applies the
  CLAMPED ρ to the roster, while `:1110` assigns the **unclamped** `target` to `n_prev`. A clamp-binding year
  desynchronises the AR state from the stand permanently, nothing re-syncs them, and the fix would have been
  byte-identical exactly where the current behaviour is already coherent — the ideal guardrail-4 shape. It is
  also **empty**: the clamp binds **0 of 150 years** and the roster tracks ρ to **1.5e-13**. One 4-minute job.
  Generalised into ADR 0102 §2 and into the method rules: **a code-level inconsistency is a hypothesis about
  the trajectory, not a defect, until the branch is shown to execute** — CLAUDE.md §3's `individual=true`
  dead-path discipline, turned on our own code instead of the C's.
- **The clue was in M's own number.** Teacher forcing recovers **59–72 %**, not ~100 %. If the whole defect
  were the AR state compounding its own error, putting the truth back into the AR state every year would
  remove essentially all of it. Something teacher forcing does not touch carries the rest. **M got there
  independently the same afternoon** — `9ad8721b` (13:07, while my probe was queued) splits the +36–81 % into
  a recursion factor ×1.26–1.53 and a **year-1 level offset ×1.05–1.12**. I nearly published "M did not
  attribute the residual", which would have been false by four hours; caught it by diffing `origin/main`
  before rebasing rather than after. **Read a sibling line's latest commits, not only the ADR you were
  handed.** What S actually adds is the level term's *fate*, which M had no reason to test: it never decays.
  And it is sitting in M's own published numbers — the forced boreal arm flattens to **1.12–1.17**, flat but
  still displaced by the 1.12 it started with. That flat-but-offset trace *is* the missing anchor.
- **It does: the stand has no level anchor.** ρ is unit-free and the roster is advanced multiplicatively,
  `D_T = D_0·Πρ_t` — which `slow.jl:779` documents as a *feature*, since it is what lets a per-patch count
  target drive a cohort-density roster without knowing the patch area. The cost had never been measured. It
  is: scale the initial density by **4×**, hold forcing/seed/artifact/`n_init` fixed, and the terminal
  densities still differ by **4.21×** after **300** years. Retention **1.036**, and the horizon sweep is what
  makes it conclusive — it *rises* to **1.40 at year 25** (transient amplification), relaxes to 1.036 by
  year 150, and then **stops**, flat to year 300. It converges to a non-zero asymptote, not to zero.
- **The dissociation is the actual finding, and a probe that measured one variable would have missed it.**
  The `n_init` sweep converges the **AR state** almost completely (retention **0.092**, four of five seeds
  landing on an identical 6.7529) while the **physical stand** those same runs carry retains **60.2 %** of its
  spread. So the constructor docstring's "`n_init` … is self-corrected by the `max_*` clamp thereafter" is
  **true of the AR state and false of the stand** — and had I only instrumented `target`, I would have
  confirmed the docstring and closed the investigation. Method rule (3).
- **What this re-orders.** S2 has been "the only lever the finding points at" since ADR 0101. That was true of
  the *response* defect and is false of the coupled configuration: an unanchored level compounds without bound
  and no conditioning skill corrects it, because the channel that would carry the correction is discarded
  upstream. ADR 0102 demotes S2 to second. It also re-reads ADR 0101 §5's 4.5×-FIT `n_init` swing as this
  recursion property rather than an artifact quirk, which promotes integration point #2 to a correctness issue.
- **Deliberately NOT fixed, and that is the decision.** Anchoring needs the count↔density conversion at the
  S↔F seam — the very quantity the ratio formulation exists to avoid needing — so it is an `interface.jl`
  addition (M's) plus a `slow.jl` change (S's), and it moves every coupled baseline. The tempting one-liner
  (anchor `D` using `n_prev` as the scale) is recorded as rejected: their ratio *is* the unknown patch area,
  so it silently sets that constant to 1 and converts a drift into a bias that looks anchored.
- **Cleared two cross-line blockers instead of adding a third.** M's `wscal_leafon` flip had sat as "S's to
  schedule" purely because S asserted the out-of-band set is *exactly* `{water_stress}`; that assertion now
  admits exactly the two admissible states and still fails on any third, so M lands it alone — and on M's own
  ADR-0051 measurement (0.3050 → **0.0034** against a band of [0, 0.04315]) the flip **closes S's last
  out-of-band column**. Integration point #2 is now written into `lines/M/STATE.md`, where it had only ever
  existed on S's side.
- **Corrected the public report, which had drifted on more than the two known numbers.** The damping is
  39.9 % / −971.5 / +1461 (the 37 % / −892 pair was arm B, the *refused* env arm); the ceiling is patch-year
  (Wooddens 0.9543), not the superseded stem-parity 0.9201; **placement-not-shrinkage** (dispersion 1.034 at
  39 % of ceiling) is stated for the first time; "recursive stability — not yet tested, no evidence either
  way" is now "not established (measured, negative)"; the roadmap is re-ordered with the level anchor as
  item 1; and a new `sec:traitmort` reports Phase 3A as it came out — level robust, response null.
- **Captured** (§8 gate): `scripts/diagnose_count_recursion_anchor.jl`, three sections (coherence / anchoring
  / level anchor) with an explicit printed verdict for the "(B) is empty" outcome, because a null there is a
  reportable result and not a failed probe.
- **Next:** the level anchor, and it cannot start from this line alone — agree the seam with M first.

## 2026-08-05 (later still) — the owner caught the error that had just blocked a one-file fix  [ADR 0103 / milestone S8]

- **ADR 0102, merged an hour earlier, said the level anchor was blocked on line M. The owner read it and
  said: the patch is 15×15 m, you should be able to see that in the LPJmL-FIT source.** They were right.
  `par/lpjparam_fit.js:17` `"patcharea" : 225.0`, and `new_tree.c:209` `pft->nind = 1/param.patcharea`.
  Verified rather than conceded — `cpp -P` on the live config gives exactly one occurrence at 225.0 with no
  duplicate-key override, and the committed fixture agrees end-to-end (`sum(nind)×225 = 17.000`, every
  individual at `1/225`). The conversion I had called "the very quantity the ratio formulation exists to
  avoid needing" was a constant sitting three files away.
- **How I got there is worth more than the fix.** CLAUDE.md contains the sentence *"with `nind = 1/patcharea`
  (`new_tree.c:209`) the patcharea cancels"* — written about the ADR-0035 per-patch LAI reconstruction, where
  it genuinely does. I read it as a property of the *quantity*. The question I never asked was **cancels
  against what**. Generalised into `residual-diagnosis`: *"X cancels" is a statement about an expression, not
  about X* — and, before concluding a quantity is unavailable, grep the upstream source, which is right here.
- **The second-order error was procedural and it is the one to watch.** I invoked ADR 0029 (the ownership
  map) to route the fix through line M's `interface.jl`. ADR 0029 stops lines editing each other's *files*;
  it does not make a constant from a third repository into another line's property. A wrongly-raised
  integration point is not harmless caution — it parks finished work behind someone else's schedule, which
  is precisely how the `wscal_leafon` flip sat unscheduled for weeks with each line recording it as the
  other's to move. Rule added to `repo-commit`: ask whether you need a FILE EDIT or a VALUE.
- **Built it, and it works.** Geometric blend `ρ_eff = (target/n_prev)^(1−a)·(D_want/D)^a`, opt-in, the
  branch not evaluated at `a = 0`. Measured on the ADR-0102 sweep (job 1707102): retention **1.036 → 0.051**,
  terminal spread **4.207× → 1.074×**, and the stand's ratio to its own count-model target **1.409 → 1.000**.
  `a = 1` is *worse* than `a = 0.1` (retention 0.076 vs 0.051), which is the shape the design predicted — a
  hard anchor overwrites the stand's dynamics so the perturbation is re-imposed through the clamp and the
  recruit branch rather than relaxed away. **Recommend `a = 0.1`: the gentlest setting that fully works.**
- **THE FINDING BEHIND THE FINDING, and it indicts the whole validation panel.** Unanchored, the stand sits
  **1.41× denser than its own count model's absolute prediction** — a 41 % over-density, permanent, and
  **invisible to every gate this project has**: the ADR-0030 per-cell trait gate, the count R² of 0.982, the
  pooled KS checks, the trained-band diagnostic. All of them read ratios, distributions or correlations.
  **A panel of scale-invariant metrics cannot see a scale error.** That is now a rule in
  `residual-diagnosis`, and it is the most transferable thing this line has produced in weeks.
- **Owner decisions recorded, standing:** M's coupled baseline regeneration is **pre-authorised** (written to
  `lines/M/STATE.md`, mirrored here, and into `MEMORY.md` §4 beside the ADR-0081 licensing closure so it
  survives a STATE consolidation), and **HPC compute is not a reason to defer** — do not park a measurement
  or a global re-fit solely because it costs cluster time.
- **A concurrent session was live on `line/S` in this same worktree** (CLAUDE.md §9 forbids it), auditing the
  public report. No damage: it staged by explicit path, touched neither level-anchor file, and left the push
  to avoid a branch race. It found 7 report errors, **one of them mine from earlier today** — I had written
  that the `ind` table's `mort_*` fields "are the basis of the optional operator"; the operator re-derives
  the hazard from the C source and zeroes `mort_water`/`mort_temp`, so those columns are unconsumed.
  Ported-from-the-source ≠ built-from-the-table.
- **Next:** the two remaining levers are now both retrains, and both are unblocked — kill the exposure bias
  at the root (retrain the count DRF without feeding its own prediction back; the anchor currently makes the
  stand follow a biased prediction *faithfully*), and S2's conditioning in the only form that can carry a
  warming signal. Then line M's five coupled cells with `anchor = 0.1`, which is where ADR 0054's 59–72 %
  residual either goes away or does not.

---

## 2026-08-06 — the flip criterion failed, and the criterion was wrong (ADR 0104)

- **The decisive arm ADR 0103 §6 pre-registered was run — by BOTH lines, independently, within two minutes
  of each other and without coordinating** (S job 1716500, M job 1716489). Same numbers to the digit.
  Verbatim, the criterion **FAILS**: the three drifting cells flatten (15 / 30 / 64 % of the log-drift
  removed) but none reaches 1.00, and `semiarid_sahel` goes from 1.4 noise floors to **3.7**. A sweep over
  `a` = 0.1 / 0.25 / 0.5 was run to characterise the failure, not to escape it, and it made the picture
  worse: Sahel degrades **monotonically** in `a` (1.9 / 2.3 / 3.7).
- **Then the yardstick turned out to be wrong.** The criterion scores `s.target_history` — the count model's
  PREDICTION. `slow.jl:1066-1070` multiplies the ROSTER; `target` appears only as the thing aimed at. The
  anchor never writes the quantity the criterion measures, so the criterion was reading a second-order
  feature feedback with its own per-cell sign. **That argument is readable off seven lines of code and does
  not depend on the results** — which is the only reason it is legitimate to change the yardstick after
  seeing them, and it is stated that way in the ADR rather than glossed.
- **M's own run contained the tell and neither of us had read it that way.** Their last table asks "did the
  anchor fire?" and reports the stand landing on its own count model's target at **1.001 in all five cells**
  — while the criterion two tables up scores FAIL in four of five. Two tables disagreeing that completely
  are not measuring one thing.
- **On the corrected yardstick — the stand's density against the C's per-patch mean ÷ patch area,
  `mean_y |ln(density/truth)|`, symmetric so an overshoot is penalised exactly as hard as the over-density
  it replaced — the anchor improves ALL FIVE CELLS AT ALL THREE SETTINGS.** Mean 0.679 → 0.478 / 0.361 /
  0.329. ⇒ the recommendation moves from `a` = 0.1 to **0.25**: the best mean whose worst cell is still an
  improvement. 0.5 wins the mean only by pushing Sahel from 55 % over- to 67 % **under**-density.
- **Sahel earned its own section rather than being absorbed into a mean.** Free-running its prediction is
  nearly right (0.95× the C) while its stand is 1.55× too dense. The anchor makes them **agree at 0.33× of
  truth** — it converted a disagreement into a *consistent wrong answer*, which is the more dangerous
  failure, because self-consistency reads as correctness. Mechanism: the count model's feature sensitivity
  exceeds the anchor's restoring strength in the driest cell, i.e. ADR 0102's training-side exposure bias,
  **surfaced by the anchor rather than caused by it**. Unanchored, that cell looked fine on the gate metric
  while carrying a 55 % level error nothing could see.
- **The memory arm was built, and building it correctly mattered more than running it.** M4's caveat named
  `biome_resilience_probe.jl`'s `anchor0` arm — but `anchor0` is **teacher forcing**, which overwrites the
  AR feature with an externally measured series and therefore *injects* that series' memory. That is exactly
  why M measured it destroying Amazon `n` (0.066 against a C of 0.501). Running it would have answered a
  question about a different intervention. New `lvl0`/`lvl1` arms instead: Amazon `n` stays at **0.549**,
  and mean |AC − C's AC| over 10 cell-variable pairs goes **0.0439 free → 0.0405 anchored** (`pin1` 0.0973).
  The anchor does not buy its level fix with dead dynamics.
- **And the memory arm nearly repeated the same error an hour later.** The obvious read is `lvl − free`,
  which shows a degradation in 8 of 10 pairs. But the free arm sits ABOVE the C's autocorrelation in 9 of 10
  pairs, so lowering the AC moves *toward* the oracle. **When a control arm and a truth disagree, score
  against the truth.** Same mistake, different costume, same session.
- **The default is still off, and the remaining blocker is now exactly one measurable thing:** the driver
  starts from the MODAL patch, 1.12–1.72× denser than the ensemble the count model was trained on, so every
  free arm starts 1.56–1.95× above its truth and the measured benefit is an **upper bound**. Re-run on the
  patch-ensemble driver decides it. Named as item A in the handoff so it cannot quietly become permanent —
  `wscal_leafon` sat correct-but-off for weeks on precisely this failure mode.
- **One clause of the re-registered criterion was deleted after measuring it, and that is recorded too.**
  The 100-year cycled biomass drift is 2 better / 1 flat / 2 worse. It was in the first draft of the new
  criterion; it is dropped because that drift lives in F's carbon pools, which the anchor does not touch —
  gating a count-level fix on a biomass metric would be the same category error a second time. It stays
  reported in every anchored run as a fact about the coupled model.
- **Top-level, all lines:** `CLAUDE.md` §0a — reports to the owner go in plain language, no decision-record
  numbers, no phase or milestone codes, no jargon standing in for an explanation. Owner instruction. A
  translation table is in the section; it binds user-facing text only, not ADRs, STATE or code comments.
- **Next:** re-run the corrected criterion on the patch-ensemble driver (the one blocker), then the exposure
  bias — for which Sahel is now the sharpest test case this line has.

## 2026-08-06 (later) — the ensemble closed both open questions, and both answers were "no"

The one blocker named at the end of the previous entry got run, and it reversed the conclusion it was
supposed to confirm. Line M had landed the patch-ensemble driver (ADR 0057) on `main` that morning, so the
basis was available without waiting on anything.

- **The criterion FAILS on the ensemble at all three settings, and the effect it was measuring was mostly
  the confound.** Free-running terminal density/truth goes from 2.55 / 2.03 / 3.01 / 1.55 / 1.90× on the
  modal patch to **1.35 / 1.15 / 1.38 / 0.52 / 1.04×** on the 25-patch ensemble — mean score 0.679 →
  **0.159**. The anchor now improves 3 of 5 cells and **worsens the mean** (0.159 → 0.166 / 0.181 / 0.194).
  Jobs 1717190 / 1717247. The harness check that makes it a measurement: the ensemble's own year-2010 stem
  count reproduces the C's per-patch mean exactly in all five cells.
- **`semiarid_sahel` was never over-dense.** On the modal patch it read 1.55× too dense; on the ensemble it
  is **0.52× — 48 % UNDER-dense**, the largest error in the set, and the anchor drives it to 0.33×. ADR 0104
  §4's whole reading of that cell inverts.
- **The mechanism is now unified and it is not a defect in the anchor.** The anchor lands the stand on the
  count model's absolute target exactly as ADR 0103 built it to. Given **F's own** canopy features that
  target sits below the C's truth — so it helps where the free stand is above truth and hurts where it is
  already right.
- **Teacher forcing is WORSE in all five cells** (score 0.149 → 0.277, 0.086 → 0.153, 0.180 → 0.259,
  0.349 → 0.460, 0.029 → 0.069), inverting ADR 0054's 59–72 %. That number was modal-patch AND scored on the
  prediction; it does not survive either correction. Which yields the thing worth keeping: **the
  multiplicative ratio update is not simply a defect that discards the level** — free-running, it cancels a
  biased target, and both interventions built to re-introduce that level therefore hurt.
- **The exposure bias — the #1 remaining item, and the retrain that was queued behind it — is EMPTY.**
  Measured offline from the tables that already existed (`scripts/exposure_bias_probe.jl`, job 1717208,
  22.5 M rows, four minutes): one-step bias **−0.0014** stems/patch/yr held-out-cell OOS on counts of ~10,
  AR gain **g = 0.562** ⇒ a **bounded** 2.28× amplification to −0.038 stems. Per-cell it predicts
  +4.2 / −5.9 / +10.5 / −0.0 / +0.2 % against a coupled +35 / +15 / +38 / −48 / +4 % — wrong size in every
  cell, wrong sign in two. The gap is F's canopy diverging from the C's (F's `fpc` moves 1.56× where the
  C's moves 0.90× at boreal). **Cancelled, not deferred.**
- **The method rule this cost.** ADR 0104 applied the rule it had just earned to the *metric* axis and got
  it right, then named the *canopy* axis as an open confound, called its own benefit an upper bound — and
  published a recommended `a` from that arm anyway. **Naming a confound is not closing it.** Never publish a
  default or a tuned value from an arm you have labelled an upper bound. Corollary, of which the teacher
  forcing above is the instance: an attribution arm inherits every basis error of its harness.
- **And the cheap one that paid for itself twice over:** price a retrain offline before buying it. Two
  hundred lines of Julia and one four-minute job stood in for a global two-artifact retrain and a
  cross-line re-pin.
- **Next:** the residual is a coupling / F-fidelity item and belongs to line M — raised with the
  measurement attached. S2 (the conditioning set) returns to the top of S's own queue by elimination.

## 2026-08-06 (later still) — the acceptance criterion, and the moisture actually varies now

The owner set the acceptance criterion and was right to be angry at the framing of the previous entry:
nothing was near finished, because the emulator has no climate-change response at all. Recorded as ADR 0106
and delivered to all four lines' start-here blocks, to `MEMORY.md`, and to `~/.claude/CLAUDE.md`.

- **Done = everything (counts, trait distributions AND medians) within 10 %, on ALL cells, under climate
  change too.** Supersedes every noise-floor stopping condition. One clause needed a stated default rather
  than the owner's words: the original model's own two runs differ by 29 % of the mean for the per-patch
  count in a low-density cell, so a literal 10 % is unmeetable there by any emulator ⇒ tolerance =
  `max(10 %, the original's own two-run spread)`. Flagged, not absorbed.
- **The binding constraint is the climate-change clause, not the fidelity numbers.** Trait medians are
  already 9 of 10 within 10 % at the test cells. But the warming response is indistinguishable from zero,
  and CO2 is a constant in every deployed training row so there is no CO2 response at all — which has no
  owner and may need a new run of the original model.
- **The moisture conditioning now exists.** All six descriptors built per cell-year for both scenarios, all
  67 420 cells. Global mean humidity deficit +20.4 % and evaporative demand +4.9 % 2019 → 2100; per cell the
  values now take 20 (historic) / 81 (ssp370) distinct values where they took **1**.
- **The gate earned its keep twice, and both were the same trap in different sizes.** (1) I averaged 12
  monthly means where the original averages DAYS; months are 28–31 days long, so four of six columns were
  off by ~0.3 % — small enough to look like rounding, far too large to be zero. Fixed in the formula, which
  is where a real failure belongs. (2) The last column then failed only in **3 cells of 67 420**, all with a
  humidity deficit of ~1e-4 against a median of 0.446; the max ABSOLUTE error over all cells was 9.5e-07.
  A pure relative test is undefined for a column that legitimately reaches zero, so the metric was widened
  to a combined absolute+relative form — argued from the three cells' actual magnitudes, and only after the
  real bug had been fixed rather than tolerated.
- **Method rule:** an acceptance criterion is a deliverable and its absence is a defect. Months of
  per-milestone gates with no project-level stopping condition is exactly how "the open questions are
  closed" got reported as near-finished.
- **Next:** wire the transient tail into the training-table builder, retrain both artifacts, re-pin with M,
  then score globally against the 10 % criterion.

## 2026-08-06 (correction) — the CO2 "gap" was not a gap, and I had cited the decision that says so

The owner corrected this sharply and was right. **The emulator must not see CO2 and must not respond to it.**
It responds to **climate**, and the SSP scenarios already carry the CO2-driven climate signal. LPJmL-FIT runs
**constant CO2** for future runs **on purpose**: with nitrogen limitation off, its CO2 fertilization is
unbounded and a rising-CO2 run blows vegetation carbon up — its own CO2 response is wrong. So an emulator with
no CO2 response **matches the reference**, which is the entire criterion. Written up as ADR 0107.

- **What I published that was wrong:** ADR 0106 §4 listed CO2 as "FAILS COMPLETELY … the largest single gap
  and it is structural", and §5 item 2 escalated it to an unowned item that "may require a new run of the
  original model, which is an owner-level cost decision". Both withdrawn. Adding a CO2 response would be a
  fidelity *regression* and would reintroduce the exact carbon runaway ADR 0004 exists to prevent.
- **This was not a knowledge gap — ADR 0004 is in ADR 0106's own `Related` line.** I retrieved the decision
  and then contradicted it in the same document. Citing a decision is not reading it.
- **And I broadcast it** into `MEMORY.md`, all four lines' `## NEXT` banners and `~/.claude/CLAUDE.md` — so
  four lines' next sessions were pointed at a non-existent defect. All corrected in the same commit, and the
  rule is now recorded as **standing, do-not-re-litigate** beside the reuse/licensing entry, because the owner
  reports having had to correct it repeatedly.
- **Method rule:** **an absent behaviour is not automatically a missing one — check whether it was designed
  out before calling it a gap.** A gap list built by asking "what does the emulator not do?" will promote
  every deliberate simplification to a defect. One question per row: *is there an accepted decision that this
  should not be there?* Corollary: under a match-the-reference criterion, every candidate gap must be phrased
  as a comparison against the reference, never as an absolute capability. "The emulator has no CO2 response"
  is not a finding; "its CO2 response differs from the source model's" would be, and is false.
- **What this does NOT change:** the acceptance criterion itself (ADR 0106 §1–§3), the other five gap rows,
  and the moisture work — which remains the critical path, and is now the *only* climate-response channel
  rather than one of two.

---

## Session 2026-08-06 (line S) — the moisture conditioning is WIRED: transient tail, per-row Year, and the isolated arm (ADR 0108)

**Item A from the previous handoff was already done** — the F-canopy attribution is in `lines/M/STATE.md`
(the `▶ NEW INTEGRATION POINT RAISED BY LINE S, 2026-08-06` block, with the offline-vs-coupled table and the
`fpc` drift ratios). Nothing was owed. Do not re-raise it.

**Item B (S2) is what this session did.** The data layer existed; the wiring, the runtime policy, the gate and
the arm did not.

### What was built

1. **`ENV_WINDOW` in `build_slow_runtime_table.py::_env_source`** — the env tail becomes a per-`(Cell,Year)`
   join against `cell_year_env_<scenario>_w20.parquet` instead of a per-`Cell` mean. Default unset ⇒
   byte-identical.
2. **`live_flux_cond_env_series` in `src/components/slow.jl`** — the runtime half, indexing `s.year + 1`
   clamped, i.e. the *same* index `boundary_series` uses, evaluated in the *same* year (`reconcile_demography!`
   advances the boundary and calls `rc.cond` before `s.year += 1`). A constant series reproduces
   `live_flux_cond_env` exactly. Exported; the ADR-0038 construction probe stub gained `year = 0`.
3. **`years.i64` on every table** (count + copula) + manifest `years_tag`, pooled all-or-nothing.
4. **`env_basis` in every copula manifest** — the ONLY thing distinguishing a static-tail from a
   transient-tail artifact, since the two have identical `ncond` AND identical `cond_cols`. `pool_slow_tables.py`
   now refuses to pool two scenarios whose bases differ.
5. **`scripts/diagnose_env_window_gate.py`** (job **1718598**, 5 biome cells) and
   **`scripts/run_moisture_conditioning_arm.sh`** (job **1718904**).

### Why `years.i64` rather than inverting the year from `Xc`

Measured, because it decided the design: `(Cell, gdd5, tas_cold_month)` is ambiguous for **174 of 1 348 400**
historic and **202 of 5 461 020** ssp370 cell-years; adding `soilmoist` to the key only cuts it to
**134 / 141**. ~1e-4 of the rows — invisible in every aggregate, wrong exactly where the climate is flattest.
So the Year is stored, not inferred, and a pre-0108 table cannot be augmented transiently at all.

### The gate result (job 1718598)

`ENV_WINDOW` unset reproduces the pre-change builder's `Xc.f64` **byte-for-byte** (diffed against
`git show <parent>:`, not a re-run of the new code, so the check is not circular), with
`n`/`ncond`/`cond_cols`/`axes`/`x` unchanged. Under `ENV_WINDOW=20`: columns 0-7 **identical**, only the six
tail columns move, same row universe; 20 000/20 000 probed rows carry their own `(Cell,Year)` values
re-derived from the parquet; **20 distinct tail values per cell where the static tail has 1**.

### Why the arm is one base table plus two appended tails

Two independent 14-column builds would land on two row universes (ADR 0036 §5b: streaming `group_by` is
non-deterministic in its **key set**), so the comparison would not isolate the tail — the ADR-0033 attribution
error this line has made twice. Instead: build the 8-column base once, append each tail to that frozen base
(`build_slow_copula_env_augment.py`, which verifies the base columns survive **bitwise** and symlinks
`Y_*`/`cells.i64`/`years.i64`), and score both on identical `Cell`-hash folds ⇒ **paired per cell**. The
pooled base came out at **42 227 077** rows, the same as `_t8`'s, and the transient augment resolved **all**
42 227 077 rows to their own `(scenario, Cell, Year)` moisture values.

### ⚠ THE CORRECTION THIS SESSION MADE TO ITSELF — measure the baseline before arguing from structure

The first draft of ADR 0108 said the frozen tail meant the trait response to climate was "structurally zero,
by construction". **That is false, and it was caught by measuring rather than by review.** The frozen tail is
**6 of 14** conditioning columns; `water_stress` and `soilmoist` are per-`(Cell,Year)` flux drivers and the
boundary pair is transient under `BOUNDARY_WINDOW`. So a new diagnostic
(`scripts/diagnose_moisture_arm_response.py`, job **1718922**) was run on the **shipped `_t8` generation**
first — 52 074 cells with >=30 stems in both scenarios, K-fold-by-cell OOS, per-cell response
`D = median(ssp370) - median(historic)`, `D_pred` regressed on `D_truth` through the origin:

| axis | response slope | corr | sign agreement | per-cell median within 10 % (hist / ssp) |
|---|---|---|---|---|
| SLA | **+0.85** | +0.45 | 71.9 % | 70.7 % / 67.5 % |
| Wooddens | **+0.35** | +0.38 | 61.5 % | 71.4 % / 72.2 % |
| D95max | **+0.16** | +0.20 | 57.5 % | **28.0 % / 30.0 %** |
| minwscal | **+0.69** | +0.58 | 62.7 % | 62.1 % / 63.8 % |

⇒ **the offline recruit-trait response channel is PARTIALLY OPEN, not closed.** The arm's job is to *beat*
these slopes, not to move a response off zero, and every doc/comment claiming otherwise was corrected in the
same commit. It also gives this line its first **global** (52 074-cell, both-scenario) level-and-response
score, replacing five-cell statements: `D95max` is the outlier at 28 % of cells within 10 %.

**METHOD RULE (this is the third time this line has paid for a version of it):** *measure the baseline before
arguing from code structure that a channel is closed.* "Column X is frozen" bounds what X can carry; it says
nothing about what the model can do, and the difference cost one 3-minute job. Same shape as ADR 0107's rule
(an absent behaviour is not automatically a missing one) — applied this time to our own reasoning.

### What is NOT claimed

Whether the transient tail improves trait skill or the response is what the arm measures. A null is a
legitimate outcome. Nothing here is a *coupled* claim: it is all offline with the conditioning fed the C's own
features, and ADR 0105 §5 shows the coupled residual is dominated by F's canopy.

### THE ARM REPORTED — and the answer is a trade, not a win (ADR 0109; jobs 1718904 build+eval, 1719206 score)

**The pairing is total**, which makes the three-way comparison unusually strong: the `_t9` 8-column base
`Xc.f64` is **SHA-256 bit-identical** to the shipped `_t8` base (`fc8d619edd6cd06e…`), and
`cells.i64`/`scenario.i64`/every `Y_*` match. So `_t8` (8 columns, **what line M pins**), `_t9env` (14 columns,
frozen tail) and `_t9envT` (14 columns, transient tail) are all on the **same 42 227 077 rows**. ADR 0036 §5b's
streaming key-set nondeterminism did not fire this time — which is luck, not a property; keep building arms as
one base plus appended tails.

| axis | | 8-col `_t8` | 14-col FROZEN | 14-col TRANSIENT |
|---|---|---|---|---|
| SLA | slope / within 10 % | +0.851 / 70.7 % | +0.396 / **74.2 %** | **+0.752** / 73.6 % |
| Wooddens | | +0.346 / 71.4 % | +0.254 / **74.0 %** | **+0.332** / 73.8 % |
| D95max | | +0.163 / 28.0 % | +0.145 / **33.1 %** | **+0.172** / 32.4 % |
| minwscal | | +0.689 / 62.1 % | +0.609 / **66.1 %** | **+0.706** / 65.3 % |

**1. The env tail is a LEVEL-vs-RESPONSE TRADE.** Adding it frozen buys **+2.6…+5.1 pp** of cells within 10 %
and costs response slope on **all four** axes. Six per-cell constants are a near-unique **spatial address**:
they help locate a cell and thereby make the fit *less* dependent on the columns that move with time.
⚠ **ADR 0037/0038 recommended that tail on level evidence and every number in it stands — there was no
response statistic then.** The tail was not wrong; the metric panel was incomplete. That is the generalizable
part: *a metric panel missing the binding quantity will confidently recommend a change that degrades it.*

**2. Transient buys the response back** on all four axes (+0.356/+0.079/+0.028/+0.097) and sign agreement on
all four, for **0.2–0.8 pp** of level. Sharpest number: the truth's mean `Wooddens` response is **+2406**;
frozen predicts **+1529**, transient **+2402**. On `D95max` the transient tail is the **best of all three**.
Recovery is not complete (0.752 vs 0.851 on SLA) ⇒ the address effect is reduced, not removed.

**3. NO FLIP, and the criterion was NOT re-read.** ADR 0108 §8 clause (a) fails as written (`D95max` pooled
`nqrmse` 0.0120 vs 0.0090; level worse by 0.2–0.8 pp on all four). The margins are small and I think the
response gain outweighs them — **which is precisely what a pre-registered criterion exists to overrule.**
Clause (b), the coupled screen, was never run, so the flip is blocked regardless and nothing needed
adjudicating. `_t9envT.rcop` exists, is **not pinned**, and M's `_t8` pin is untouched.

**4. The criterion itself was mis-specified — recorded, not retro-fixed.** It gated on trait *level* while
ADR 0106 makes the *response* binding, so it can reject a change that improves the binding quantity to protect
0.4 pp of the non-binding one. Editing it now would be the ADR-0104 error in a new costume; instead ADR 0109 §5
registers a correct three-clause criterion (response-primary, level as a stated-band guardrail, `agb` named as
reported-not-gating out loud) for a **new** arm.

---

## Session — 2026-08-10 · rung 0: fix the yardstick (ADR 0111)

`EXECUTION_PLAN.md` landed on `main` after the last handoff was written, and it puts line S on **rung 0**
(re-score existing artefacts on a corrected yardstick; no new model runs). That supersedes the ordering in my
own `## NEXT` block, which was written a day earlier. So I did rung 0 rather than item 0★★.

**I set out to reproduce a published correction and found the correction was broken three ways.** The plan's
rung-0 text says the deattenuated response slopes are "SLA 1.08, minwscal 0.99 — already correct; only
Wooddens (0.63) and D95max (0.51) are broken", sourced from ADR 0093 §3e.

1. **The λ column and the deattenuated column are swapped in exactly two rows.** ADR 0093's λ came from
   `crn_headroom.json`; its `lambda_1seed` is SLA 0.788, minwscal 0.697, Wooddens 0.628, D95max 0.510. The SLA
   and minwscal rows of §3e are internally consistent with that. The Wooddens/D95max rows are not: 0.63 and
   0.51 **are the λs**, and 0.55 = 0.346/0.628 and 0.32 = 0.163/0.510 are the quotients. Two lines of
   arithmetic; I nearly wrote the ADR around the wrong pair before checking.
2. **λ and the slope were never on the same basis.** λ: log-space, single year 2019→2099, ≥50 stems, 43 257
   cells, uncapped, cell-mean-of-per-patch. Slope: linear, all years pooled, ≥30 stems, 52 074 cells,
   `STEM_CAP=400`. A reliability belongs to a *statistic*. This is ADR 0030's rule — it had been applied to
   the level and never to the response.
3. **My own first version was wrong too**, and it is the most reusable lesson: I divided a cell's stem count
   by the number of patches that *held a tree* instead of the configured 25. That makes the denominator
   correlate with the numerator across seeds and cancels part of the sampling noise — the sparse stratum's
   floor came out 10.5 % where the honest number is 27.0 %. I only caught it because my "reproduction" of
   ADR 0093's 31.6 % was 3× too small and I refused to write that off as a basis difference. **A reproduction
   that misses by 3× is a bug, not a nuance.** `cell_npatch.parquet` would not have saved me: it is itself
   built from occupied patches.

**What the corrected panel says** (2-seed deattenuated, shipped pin, 51 767 of 54 020 cells, both scenarios):
SLA **1.28 — over-responds by ~30 %**, minwscal 1.06 correct, Wooddens **0.66 — the worst axis**, D95max
**0.73 — not the worst**. D95max looked broken because its regressor is nearly noise (λ = 0.198; it is the
only quantity whose per-cell response signal-to-noise is below 1, at 0.50). Its raw slope of 0.163 is mostly
attenuation.

**The result I trust most is a robustness check I almost did not run.** Between the capped and uncapped bases
the raw slope moves up to 21 % and λ up to 25 %, but the quotient moves ≤3 % on all four axes. That is what an
errors-in-variables correction should do, and it is the only reason I am willing to publish the deattenuated
numbers as steering quantities. `Height` fails it (1.05 vs 0.85) and is therefore quoted as a range only.

**The aggregate metric was the easy win.** Area-weighted response signal-to-noise is 25–489; per-cell is
0.5–3.1. And the latitude bands matter more than the global mean: above-ground carbon responds −1.5 % in the
tropics and **+19.4 % in the boreal** against a global −0.5 %, so a global-mean-only report would describe a
model that gains a fifth of its boreal stand carbon as having almost no carbon response.

**One correction lands on my own line's previous work.** ADR 0109 read "the transient tail raises the slope on
all four axes" as unambiguously good. Deattenuated, SLA and minwscal sit *above* 1.0, so raising them is
movement away from faithful. The arm's verdict survives (it is closer to 1.0 on the two axes with the biggest
margins) but the reading "higher is better" does not. I did **not** re-read the flip criterion — that is
ADR 0104's error — only recorded that its statistic must be `|deattenuated slope − 1|` against a multi-seed
mean.

Cost: 6 SLURM jobs, ~15 min of compute total. The expensive-looking part (2.55 × 10⁹ stem-year rows) ran in
3.5 min because `Cell` predicate pushdown works on those parquets.

### Postscript, same session — the merge, and a storage fault worth knowing about

The merge took longer than the science. `/p/projects` began returning `Input/output error` on individual files:
**21 of 90** pack files in the shared repository became unreadable, so `git` and `curl` died with
`Bus error (core dumped)` and littered 53 core files in this worktree (and 24 in `wt-M` — a second line was hit
at the same moment). Three things I would do faster next time, all now in the `repo-commit` skill:

1. **`dd`, not git, decides whether a repository is corrupt.** I wasted a cycle concluding "the object store is
   fine" from `git verify-pack -s`, which is **stat-only** and returned `rc=0` on all 45 packs while 21 of them
   could not be read at all. A one-line `dd` loop over the packs answered it definitively, and reproducing on
   `login02` ruled out a bad machine in another ten seconds.
2. **`fatal: Unable to write index.` means a stale `index.lock`.** The fault killed a git process and left the
   lock behind; three merge attempts then failed with a message that mentions neither locks nor storage. I found
   it only after checking `ls -la $INT/.git/*.lock`.
3. **My own retry loop lied to me.** It printed `MERGE+PUSH SUCCEEDED` while the merge was still failing,
   because the `if` tested the exit status of the `tail` at the end of a pipe. I caught it only because I print
   the tip of `main` after every merge — that habit is the sole reason I did not report a merge that never
   happened.

Two judgement calls worth recording. I did **not** attempt any in-place repair — no `gc`, no `repack`, no
deleting packs — on a filesystem returning EIO, and instead verified through the GitHub API that every locally
unreadable file was intact on the remote, which turned the incident into a delay rather than a data question.
And while local `git commit` was impossible I landed the handoff through the GitHub API, so the next session
would not inherit a "merge pending" note with no explanation of why.

The rebase then hit one conflict, in the shared `residual-diagnosis` skill, where line M had appended a section
of its own. Both appends were kept: that file is append-only by convention, and taking either side would have
silently deleted another line's work.

---

## 2026-08-10 (line S) — rung 1 opened, and the first thing it found was that rung 1's arm B was already done

Rung 0 merged green, so I started rung 1: "S alone, on the C's own fluxes", four arms A/B/C/D. Before building
arm B — "fed the C's own per-tree fluxes each year" — I went to check what the production emulator is
conditioned on, so that arm B would differ from the control by exactly one thing.

It differs by nothing. Every one of the 15 features the production count model reads is built from LPJmL-FIT's
own output for that very (Cell, Patch, Year): `build_slow_runtime_table.py` computes the carbon uptake, growth
efficiency and water stress from the `ind` roster, the soil moisture from the C's own daily root-zone water,
the six size/structure features from the same roster — and `n_prev` is FIT's own stem count for that patch in
the previous year. `eval_slow_drf.jl:61` then predicts each row from that row's own features. Held-out *cells*,
never held-out *time*, and nothing the model predicts is ever fed back. The copula's four flux conditioning
columns are C-derived too (it has no lagged trait, which matters later). So the published panel — all of
ADR 0111 — **is** arm B. The arm that has never been measured globally is A, free-running.

The sharpest consequence is on counts, because one of the 15 inputs is the answer, lagged a year. I built the
null that follows from that: predict `n_prev`, learn nothing. It reaches R² **0.9622** where the production
model reaches 0.9824, per-cell response slope **0.980** where the model gets 0.958, deattenuated **1.029**
where the model gets 1.006 — and it reproduces the regional pattern ADR 0111 called "a concrete, localised
target", tropics wrong-signed included (−0.43 vs the model's −0.51). So "the count response is faithful per
cell (1.006)" is a statement a model with no warming response of its own also satisfies. It is retired as
evidence. What survives as a discriminating statistic is the aggregate area-weighted ratio: 0.536 for the null,
0.691 for the model, 1.0 for the target — the learned model does add response amplitude, about a third of the
way. And the null is a control, not a floor: a one-year lag under a trend shifts an N-year window mean by
(first − last)/N, which is exactly why it lands below 1.0 rather than at it, so nobody should quote 0.536 as
"the skill of no model".

Then the missing arm. A1 feeds each year's own prediction in as next year's previous-year count and changes
nothing else — same folds, same forests, same seed — so A1 minus A0 is the recursion and nothing else. It needed
the (Cell, Patch, Year) key, which the frozen table does not carry (it predates ADR 0108). Both ways of guessing
it fail on the real data, and I measured both before rejecting them: equal-length blocking is wrong for 24.8 %
of historic and 49.9 % of ssp370 cells, because a patch that loses every tree for one year breaks its own run;
and segmenting on "last year's count equals this row's `n_prev`" silently merges adjacent patches that happen to
join on the same small integer, worst in exactly the sparse cells whose noise floor is already worst. So the
keys are recomputed from the `ind` parquet by replaying the builder's own pipeline and then *proved* — the
recomputed count, previous count and cell must equal `y.f64`, `X[:, n_prev]` and `cells.i64` row for row. They
did, on all 121 495 658 rows of both scenarios, with no fallback needed.

Written up as decision record 0112, with three falsifiable predictions for A1 so the framing can be refuted
rather than believed.

Then arm A1 itself, the same afternoon. Four minutes on 48 cores over all 121 495 658 rows, and the answer is
clean and not what I expected. Making the count feed itself barely touches the **level**: error against FIT
grows from 0.60 to 1.41 stems per patch over a dozen years, reaches 1.72 by year 80 and then stops growing, and
the mean bias never exceeds +0.16 on a mean of 8.28 — under 2 %, flat after year 20. There is no runaway. That
contradicts the natural reading of the earlier single-cell drift result ("the recursion is unanchored, it needs
a level anchor") at global scale, and agrees with ADR 0105, which had already found the anchor harmful on the
patch ensemble. So: no anchor, and if a future arm claims a runaway it has to show it on this lead-time table.

What the recursion destroys is the **response**. The area-weighted global count response ratio goes from +0.707
to **−0.226** — wrong sign — and every latitude band degrades: temperate 0.93 → 0.45, boreal 1.07 → 0.70,
tropical −0.51 → −3.62. Meanwhile the per-cell deattenuated slope moves 1.006 → 0.976. Across three arms whose
accuracy spans R² 0.982 → 0.962 → 0.918 and whose global response spans +0.707 → +0.685 → −0.226, that slope
never leaves 0.976–1.029. It is dead as a discriminator and I have retired it for counts: this morning it
couldn't tell the model from a null, this afternoon it couldn't tell +0.707 from −0.226.

Two corrections fell out. First, the count path of the yardstick still carried a **second** definition of the
aggregate ratio — the unweighted mean-ratio ADR 0111 had removed on the trait side. It agrees with the
area-weighted one on the production arm (0.691 vs 0.707) and disagrees fourfold on the recursed arm (−0.93 vs
−0.226), because an unweighted mean-ratio is dominated by cells whose own denominator is near zero. Fixed, and
the two records that quote the unweighted number are corrected in ADR 0113 §5 rather than edited. Second, that
correction makes this morning's null result stronger, not weaker: area-weighted, the null is 0.685 against the
model's 0.707. So on *every* count response statistic the null matches the production model, and the only place
the learned model clearly wins is accuracy.

And one scoping finding worth carrying forward: an offline S-only arm **cannot** measure recursion damage to the
trait axes. The trait sampler is conditioned on four flux columns plus static climate and constant CO₂ — no
roster state, no lagged trait — so nothing a state recursion does can reach it. The trait axes' free-running
error is inherited from the fast core's fluxes, which makes it rung 3/4 work on line M's harness, not rung 1's.
Arms C and D can still be scored on the trait axes, but only on the one-step basis, and every such verdict has
to say so — including `trait_mortality`'s pre-registered flip criterion, whose text I did not touch.

The follow-up diagnostic ran the same evening, because everything it needed was already on disk — the arm's own
predictions plus the proven keys, two minutes on 24 cores, no retraining. It answered the question ADR 0113 left
open and killed the obvious fix. The recursion is **not** collapsing onto an average: after 80 years of feeding
on itself the prediction still carries 90 % of the truth's between-patch spread and correlates with it at 0.94
(the one-step arm sits at 0.975). So a variance-preserving or distribution-sampling count predictor would not
help, and I have recorded that as a decision so it does not get proposed again without refuting the measurement.

What actually breaks is smaller and more awkward. The recursion's own level drift reaches +0.155 stems per patch
and then flattens — and FIT's entire global count response is about −0.14 stems per patch. The drift is the size
of the signal, and it is not the same size in the two scenarios, because the ssp370 chains run 80 years and the
historic ones 19. A difference of two biases at different depths is what the response statistic then reports.

The useful number that falls out is a **validity horizon**. Restricting to rows within k years of the last time
the chain was handed the truth: at one step the count response is right in *every* latitude band, 0.90 to 1.07 —
the best evidence yet that the count model does have a warming response. Temperate then decays 1.07 → 1.03 (3 yr)
→ 0.95 (5) → 0.77 (10) → 0.59 (20) → 0.45 (80); the tropics decay faster and go wrong-signed; boreal holds and
overshoots to 1.36 before collapsing, which fits its being the band with the large real response. Controlled
against the one-step arm on identical rows — necessary, because restricting the lead also shortens the climate
window — the recursion is indistinguishable from truth-fed up to about 3 years and inverted by 40.

Two honesty notes I put in the record rather than smoothing over. This diagnostic scores against the count
table's own seed-1 truth on 53 607 cells, because two-seed deattenuation and the ≥30-stem paired set are not
defined on a lead-restricted subset; the same quantity reads +0.835/−0.635 here against +0.707/−0.226 on the
yardstick's basis. Every sign and ordering agrees, the magnitudes differ up to 2.8×, so a decay ratio must never
be quoted against the yardstick's number. And the control column is undetermined at k = 5–20 and its per-band
values are not printed at all, so the per-band decay curve is arm-only — the contrast the control actually
establishes is k ≤ 3 versus k ≥ 40. Fixing that print is item 4 of the decision.

## 2026-08-11 — the drift is scenario-asymmetric; the ratio target is refuted; matched depth refutes the chain-length story (ADR 0115)

Ran both experiments ADR 0114 pre-registered, plus the print it left open. Four jobs, about ten minutes of
compute, all on artefacts already on disk: 1753653 (the ratio arms), 1753655 (five arms through one yardstick
process), 1753666/1753667 (the extended decay diagnostic on A1 and R1).

The ratio target went in as the more promising of the two. The idea is clean — if the drift comes from
predicting a level from a lagged level, cancel the level in the target and recurse `n̂_t = r̂_t · n̂_{t-1}`. I
built it as two arms so the target change separates from the recursion, with the free gate that R1 must equal
R0 exactly on the first-year rows, where the recursion is handed the truth. The gate passed at exactly zero
over 2 669 860 rows. Everything else failed: one-step R² 0.9742 against the production 0.9824, recursed 0.678
against A1's 0.918, drift 0.408 against 0.155 stems/patch at lead 20, aggregate response −1.099 against
−0.226, and a top prediction of 799.5 stems in a patch whose observed maximum anywhere in the table is 42.
Nothing was clamped, deliberately, because a clamp would have hidden precisely the failure the arm existed to
find. The explanation is the useful part: a forest that predicts the level has leaf values inside the training
range, so a self-fed level prediction cannot leave `[1, 42]` — the level target was quietly doing the job of
the anchor ADR 0102/0103 went looking for, and the ratio target deletes it. That is worth remembering as a
general rule about autoregressive reformulations.

The matched-lead-depth arm was supposed to be the bookkeeping control and turned into a correction. ADR 0114
§2 had attributed the scenario-dependent drift to the ssp370 chains running 80 years against the historic 19.
Building each cell's two scenario means lead by lead over only the leads present in both, with equal weight,
removes that difference by construction — and the inversion survives: −1.52 globally, against a one-step
control's +0.52 on identical rows. So the explanation that felt structural was wrong, and I would not have
known without building the arm in which the bookkeeping difference is gone.

What replaced it is better than either hypothesis. Resolving the arm's bias by scenario at a fixed lead shows
the drift is not symmetric: in the historic chains it dips to −0.070 and comes back to +0.024 by lead 18,
while in ssp370 it climbs monotonically to +0.150. The part that does not cancel reaches +0.126 against a
one-step control's +0.051 on the same rows. LPJmL-FIT's own global count response is about −0.14 stems/patch,
so at lead 18 the recursion is manufacturing ninety per cent of the true signal's magnitude with the opposite
sign. The failure is not that the self-fed count is inaccurate — its level bias stays under two per cent and
it keeps ninety per cent of its spread — it is that its error depends on the climate it is run under, which is
exactly the difference the acceptance criterion is about. That reframing is what the next experiment should
target: which conditioning feature carries the scenario signal into the error.

Two smaller things. The control's per-band columns are now printed at every horizon, which closes ADR 0114
§5.4 and confirms its per-band decay curve — the control is flat (temperate 1.07 → 0.95, global +0.90 → +0.83)
while the arm decays under it, so the curve is the recursion's and not the row subset's; and at lead 1 the arm
and the control agree band for band, which independently confirms the arm scripts' refit reproduces the
production forest. And I found that the decay script divided the already-per-patch stem count by the ensemble
size a second time. Every ratio it has ever produced is unaffected because the factor cancels top and bottom,
which is exactly why it survived a whole ADR unnoticed; only the level panels carried a label 25× too large. I
fixed the script and flagged ADR 0114's mean row as being on the old scaling rather than silently re-scaling
an immutable record.

## 2026-08-11 — the drift has a mechanism now: the recursion follows gains and not losses (ADR 0116)

The one experiment ADR 0115 pre-registered was cheap and it worked, but not in the way it was specified, and
the gap is worth recording because it is a design lesson rather than a bug.

As specified: at a fixed lead, take each cell's excess drift — the self-feeding arm's historic-to-ssp370 bias
difference minus the one-step control's on the same rows — and regress it on that cell's scenario change in
each of the fifteen conditioning features. Run at leads 5, 12 and 18 over all 121 495 658 rows, the answer is
unambiguous and it is not the answer I expected. The channel is the **stand state**, not the climate. The
previous year's stem count correlates −0.34 with the excess drift and the mean cohort age +0.33, while every
climate and flux feature — growing degree days, cold-month temperature, water stress, soil moisture, growth
efficiency — sits at 0.084 or below. Greedy forward selection picks the previous count first and mean age
second at both deep leads. The control is what turns this from a description of the rows into a finding: on
identical cells the one-step predictor's own scenario asymmetry is far weaker (R² 0.096 against 0.250), it
selects a *flux* first, and its correlation with the previous count is essentially zero. So the one-step error
runs through the fluxes and the recursion's extra error runs through the stand state. The pattern is also
uniform across all four latitude bands, which says the wrong-signed tropics are not a separate problem needing
a separate fix.

Then the gap. The regression explains a quarter of the drift's spatial spread — and, because it is fitted on
centred columns, *nothing at all* about its mean. The mean is the whole reason the aggregate response inverts.
The diagnostic as pre-registered could name a channel and could not touch the quantity it was built to explain.
I added the panel that can: bin cells by LPJmL-FIT's own count response and read the drift in each bin.

That panel is the real result. The error is one-sided. Where FIT loses the most trees the arm drifts +0.575
stems/patch; where it gains the most, at the same magnitude of response, only −0.157. Read as the fraction of
FIT's own response reproduced, the arm follows 86.7 % of a large decline but 96.2 % of a large increase. Since
FIT's global count response is a net loss, the rectified error lands almost entirely on the loss side and comes
out as a spurious *positive* drift — which is exactly the wrong-signed aggregate response measured two ADRs
ago, now with a mechanism instead of a description.

I made myself refute the two ways this could be an artefact before writing it down. The drift contains minus
the truth's response by construction, so binning on the truth's response correlates mechanically; the excess
column cancels that term exactly, and the asymmetry is 2.6× on it. And "the declining cells are simply the
dense ones" dies on its own numbers: the extreme deciles differ by 1.3× in stem count while the drift differs
by 3.7×, and normalising by density still leaves 3.0×.

Two process notes. Reconciling against ADR 0115 §3 before doing anything else took ten lines, reproduced its
arm row exactly, and caught a transcription slip in its control row at lead 5 — the value printed is lead 4's,
copied one row off from a CSV whose intermediate rows the table skips. Nothing depends on it, and it is
recorded rather than edited. And the height and crown-cover coefficients came out as a beautiful ±0.9 pair
that means nothing at all: variance inflation 16.5 and 15.3, an artefact of four collinear canopy columns. The
forward-selection path is the reading that survives.

## 2026-08-11 (second) — answering the rung-2 interface, and finding that arm C was never blocked on science

Line M's ADR 0120 landed on main while I was writing up the drift attribution, and it contains a sentence
addressed to me: the demography interface was raised on 10 August and "S has not yet replied". It had also
built the half that matters — the C now *accepts* a replacement kill set and recruit set, gated to be
numerically identical to the current binary when switched off. So the question was live and blocking.

The choice M offered was between returning a kill set, returning a count plus a victim rule borrowed from
the C's own hazard, or returning a per-individual survival probability. I picked the third, and the argument
is not a preference. FIT's warming trait shift decomposes as about a fifth composition and half within-PFT,
and the within-PFT part is entirely within age class. Traits never change after a tree is created, so a
trait mean that moves at fixed species and fixed age can only be differential survival. Who dies *is* the
trait response. A demography that returns only a count cannot reach the trait half of the acceptance
criterion through that interface no matter how good the count is. The middle option borrows the C's ordering,
which makes any trait result the C's selection wearing the emulator's count — a good upper-bound control and
not an answer. And returning a probability rather than a finished kill set mirrors what FIT itself does, and
keeps the random draw on M's side, where the seed ensemble is run.

The part I did not expect: this needs no new model. The opt-in trait-dependent mortality operator built back
in Phase 3A already produces exactly this — a per-individual survival factor with a tilt tuned so the learned
count target is still hit. So the null arm and the selection arm are the same wire format with the tilt off
and on, and their difference is a direct measurement of how much of the trait response is selection. Which
also means my own arm C was never blocked on science. It was blocked because it needs a roster and the only
rollout I have is one cell. M's harness is the roster. The option my last handoff floated — build a global
offline demography rollout — is now the wrong thing to build, and I said so in the handoff explicitly.

Better still, the harness removes a limitation I recorded as permanent: two of the four death rates are
zeroed in the ported hazard because the emulator has neither of FIT's stress integrals, and the C's roster
dump carries exactly those accumulators. Inside rung 2 the operator can run complete for the first time. I
also offered M a free gate: with the tilt forced to one, the operator provably reduces to FIT's own hazard,
so it must reproduce the C's per-tree mortality — no new code, and it catches a port error before any science
number is quoted.

I answered M's other question with data rather than opinion, and it nearly went wrong. Of the three recruit
traits the hook leaves on the C's own draw, only one is emitted anywhere, so I measured whether it correlates
with the four the emulator predicts. The first run came back with correlations of exactly zero and a
selection differential of minus two hundred and eighty-four standard deviations — a number that cannot exist.
That was the tell: a column with no variance produces both. It turns out that trait is a scalar 0.02 for all
seven tree types in the live parameter file, with the sampled-interval version commented out at every entry,
and it carries exactly one distinct value across all 206 million tree rows. So leaving it to the C is an
identity, not an approximation, and the four-axis recruit interface is complete. I restructured the script to
audit variability first and to print "const" instead of a ratio, because the next person to run it on a
different axis deserves to hit the audit rather than the impossible number. The two remaining axes are
emitted nowhere, so the honest answer there is that it is not measurable from the current output, and the
cheap route if it ever matters is to add them to the roster dump.

One more thing worth recording: the four axes the copula does predict are genuinely correlated with each
other within species and age class — leaf economics against rooting depth at −0.29, against drought tolerance
at +0.25. That is the joint the copula exists to carry, so the recruit rows have to be consumed as a set.

## 2026-08-11 — arm C's target was invalidated by the ADR that created it (ADR 0118)

Session opened with the handoff's instruction: agree the arm-C run with M, and meanwhile scope arm D.
Scoping arm D meant reading ADR 0025 (the recruit copula) properly, and §3 turned out to contain its own
expiry condition in the decision text — *"Trait-dependent mortality is a much larger, separate change; if
ever added, this training target must change."* Arm C is exactly that change. `grep -rln 0025
docs/decisions/` returned nothing from the 0047→0049→0117 chain, including last session's own reply to M.
So the condition had been sitting unevaluated for two weeks with the arm one session from running.

Rather than argue the point, sized it: `scripts/diagnose_copula_selection_confound.py`, 197.7 M historic +
828.8 M ssp370 surviving stems, both seeds, both scenarios, all four live axes, no refit and no new model
run. Two jobs of ~7 min on the `priority` partition (1754705; 1754709 after adding the young-mean column
the per-cell panel was printing as `nan`). Pre-registered the hypothesis and the two decision numbers in
the script docstring before submitting, per the residual-diagnosis discipline.

The composition control earned its place. Pooled, D95max (−49.6 %) and minwscal (−35.9 %) looked
catastrophic; within (Cell, Type) they collapse to −2.4 % / +0.4 %. Had only the pooled panel been run this
would have been written up as a four-axis crisis of which exactly one is real. And the control is not a
"pooled overstates" rule — Wooddens moved the other way, +5.4 % → +12.2 %, i.e. composition had been masking
the one displacement that matters. Wooddens is the axis ADR 0049's flip criterion is written on.

Also had to be careful not to blend the two panels: the per-cell floor (`n_young ≥ 30`) selects a
young-stem-rich subsample whose own Wooddens response is −3698 against the pooled +1848 — opposite in sign.
One ratio definition per panel (ADR 0111 §5b), stated in the script's own docstring so a future reader
cannot mix them by accident.

Seed agreement was ≲ 2 % on every entry, which is unusual for this line and worth noting: the variability
audit passed cleanly for once, so nothing here needs a multi-seed caveat.

Written up as ADR 0118, amended into `lines/M/STATE.md` (M runs the arm, so they needed it before starting),
and captured as two skill sections — the composition-control trap and the "check whether the ADR you are
extending wrote its own expiry condition" check, both in `residual-diagnosis`, plus a survivor-marginal
section in `slow-drf-pipeline`.

Arm D was scoped in the same pass and came back with its own problem: ADR 0093 §5.3's motivating 2–3× KS
win has no committed reproducer anywhere in the repo, and its "two-moment fit, no fitting procedure"
phrasing reads as oracle moments against the copula's out-of-sample number. Not resolved here — handed to
the next session as the one cheap offline task remaining.

⚠ ADR block 0100–0119 is now down to **0119**, the last number. Raised (again) as an integration point.

### Same day — the owner overturned the fix, and was right

Presented ADR 0118 and the owner objected to decision 4 immediately: *"which trees are born is — apart from
the inheritance functionality — randomly drawn from uniform distributions. why should we train on that??
what matters and what we have to learn is who survives the environmental filtering — and for that looking at
trees above 5 m should be enough."*

Correct on both counts, and it is a better answer than the one in the ADR. FIT's establishment rule is fully
specified — a uniform draw on each PFT's own interval from the parameter file, plus the top-AGB seedbank
inheritance channel with its 10 % Gaussian jitter, mixed at the closed-form `4/(4 + n_elig)` — and every
input is either in `par/pft_lpjmlfit.js` or computable from the emulator's own roster. So it is a PORT, not
a learning problem: no recruit-marginal retrain, no new artifact version, and nothing needed from line M's
rung-2 dump, which is what decision 4 had asked for. And >5 m is sufficient, because the emulator grows its
own saplings and applies the ported hazard through the sub-5 m phase itself — the "lower bound" caveat only
ever constrained *fitting* an entry distribution, which is exactly what we are no longer doing.

Two things the owner's framing understates, both design-relevant rather than verdict-relevant, and both
recorded rather than argued: inheritance is the MAJORITY channel (44 % mixed / ~80 % low-diversity,
ADR 0045), so a pure-uniform recruit model would be wrong; and the seedbank is the cell's own biggest trees,
so the recruit marginal moves as the forest moves. That second one is the real cost of the port — it makes
recruits a functional of the emulator's own community, i.e. the feedback loop ADR 0025 §4 excluded on
principle, and ADR 0112–0116 already measured what this model does when it feeds its own state back in.
That risk replaces the one decision 4 was worried about; it must be measured, not assumed.

What survives ADR 0118 unchanged: the double count itself and its size (+12.18 % on wood density within a
cell-PFT group, 0.56 of it not cancelling), the asymmetry that puts the bias on the arm and not its null,
the two added conditions on ADR 0049's flip criterion, and the composition-control lesson.

Recorded as a correction in `lines/S/STATE.md`, the M inbound (item 4 withdrawn, original text retained
beneath it so the change is visible) and the `slow-drf-pipeline` skill. **ADR 0118 itself was NOT edited** —
guardrail 1, immutable once accepted. ADR block still has exactly one number left (0119); deliberately not
spent on this correction.

---

## 2026-08-11 (later) — the ported establishment rule is BUILT, and reading the C corrected three things we thought we knew

The owner's steer from earlier today is implemented rather than planned. ADR 0119 (the last number in line
S's tier-2 block, spent deliberately on the thing the owner asked for): a `module Establishment` in
`src/establishment.jl` that computes FIT's recruit marginal from the C's parameter files, plus an opt-in
`recruit_establishment` hook on the flux-driven emulator, plus a generated per-PFT parameter reference on the
same one-artifact-two-consumers discipline as the ported mortality hazard.

**Reading the C rather than the summary of it changed three statements, one of which was this line's own.**

1. **The inheritance jitter does NOT reflect at the interval edges.** `new_tree.c:55-59` redraws *uniformly
   between the parent and the bound that was crossed* — inward, biased toward the parent, with a point mass
   exactly ON the bound when the parent sits there. ADR 0045 and the `slow-drf-pipeline` skill both said
   "reflected", and this session's own journal entry above repeats it. A reflection puts mass on the far side
   of the parent, which is a different stationary shape precisely at the narrow boreal intervals
   (`minwscal` `[0.05, 0.15]`, id 6 `d95max` `[51, 300]`). Corrected in the skill (in place, with the error
   named) and pinned by a test that separates the two rules by their point mass — not by their mean, which
   is nearly the same.
2. **The seedbank is an accumulation of individual-YEARS, not a set of distinct trees.** `getsapling.c`
   appends every qualifying tree every year with no de-duplication, so 30 years of dominance is 30 draws.
   That makes inheritance a stronger selection channel than "sample the current top trees" would be, and it
   is now what the ported `Seedbank` does.
3. **`getsapling` runs before the year's mortality**, so a recruit can inherit from a parent that dies later
   the same year. The hook keeps that order — the seedbank refresh sits at the top of
   `reconcile_demography!`, ahead of ρ.

Two invariants FIT gets for free had to be enforced explicitly, and finding them was the useful part of
writing the tests. `draw_new_trait`'s inward redraw keeps a child inside `[low, high]` **only if the parent
is inside it** — true in FIT by construction, false in the emulator, where a roster rebuilt from the `ind`
output carries `d95max`/`minwscal` at the ADR-0110 UNSET sentinel 0. Diffusing from 0 would have put every
inherited rooting depth *below* its own PFT's floor, silently and in range-looking numbers. So an UNSET axis
now falls back to the uniform channel for that one axis, and a finite out-of-range parent is clamped on
insertion with a comment saying the clamp is a guard and not physics.

The other thing the tests caught: a `set_pft_id` contrast written the obvious way proves nothing. With the
channel mix live, the Hainich arm drew beech five times out of five at one seed — because beech dominates
its own seedbank — so "the drawn id reached the roster" and "the drawn id equals the donor's id" were
indistinguishable. Made deterministic by switching the inheritance channel off entirely
(`Seedbank(; n_top = 0)` ⇒ the bank never fills ⇒ background channel only), which also exercises that path
end to end. Recorded in the skill, because the same trap applies to any channel-mixture arm.

Also learned that the drawn PFT identity cannot simply be written into the roster: `_commit_membership!`
refuses an id absent from `fc.pft_slot`, and the recruit's canopy template would still carry the donor
cohort's physiology. So identity ships behind a second flag, default off, with an up-front constructor check
instead of a mid-run failure — and the per-PFT template registry is named as the line-M integration point.

**No science number is claimed.** The flip criterion is pre-registered in ADR 0119 §6 with an explicit kill
condition — if the recruit channel makes the error climate-dependent the way the count recursion did
(ADR 0112–0116), the flip is refused and *that* becomes the result. The arm runs on M's roster harness,
which is where the criterion is written as an action.

Captured on the way: the fast single-test-item loop (a 10-line shim that runs one `@testitem` file in ~10 s
instead of the 6-minute suite) is now in the shared `julia-test` skill. It is the difference between four
iterations and one, and every future test-writing session needs it.

---

## 2026-08-11 (session 2) — the recruit port's kill condition, pre-tested at one cell, and the eligibility table that unblocks running it anywhere

Both items the last handoff left were the work: pre-test ADR 0119 §6's kill condition offline before line M
spends harness time on it, and derive the per-cell eligible-PFT set that the ported rule needs to run
outside a hand-configured cell. They turned out to be the same task — the probe cannot be honest without
the table, because the eligible set is what sets the inherited share, and at Hainich the *fixture roster*
carries only two PFT ids while FIT's own gate admits six. Configuring the arm from the roster would have
run it at `w_inherit = 0.667` instead of 0.400 and called that the ported rule.

The probe change is a third dimension rather than a new script: `ARM=recruit` swaps the contrast axis of
the existing response 2×2 from `trait_mortality` to the recruit channel, holding the count model, forcing
pair, seed, year indices, `k_cap` and the mortality setting identical on both sides. That reuse is the
whole reason the run was cheap — the four-corner protocol, the merge/hard-kill preconditions, the
trained-band excursion panel and the seed-ensemble summarizer all came for free, and the one genuinely new
panel is the drawn recruit marginal per scenario, which needed four fields added to `EstabDiag`.

**The result is a two-sided answer and it is worth stating in that shape.** The kill condition as written
is about a specific failure — the count recursion made the error climate-dependent and manufactured ~90 %
of the true signal with the wrong sign. The recruit port does the *opposite*: the shipped copula channel's
own warming response at this cell is significantly wrong-signed (−0.75 ± 0.24 ×FIT), and the port turns it
positive. So the condition does not fire. But it does not clear either, and what blocks it is not the
response at all — it is the **level**: the community wood density moves +8.5 % (t = 15) while the response
contribution needed forty seeds to reach t = 3.4. An arm whose level effect is eight times its response
quantity cannot be judged on the response, and I nearly did exactly that, because the harness was built
for a response question and prints the response first.

The natural rescue — pair the port with the selection operator, since ADR 0118 showed the copula's
marginals already carry survivor selection — was measured and **fails at this cell**: with
`trait_mortality` on, the level effect is *larger*, not smaller. The reason was already on the record
(ADR 0049 item 5: the count channel throttles the hazard to θ ≈ 0 here), which is what makes it a
prediction for rung 2 rather than a refutation: the operator has nothing to redistribute offline. Two
conditions went into the flip criterion as a result, pre-registered before M runs anything.

A method finding I did not expect: **ADR 0101's seed guidance does not transfer between arms.** Twelve
seeds — the number that resolves the `trait_mortality` arm — left every response CI straddling zero here,
because this arm's double-difference sd is 6.4–7.8 ×FIT against that arm's 0.67–1.74. The first ensemble
therefore looked like "indistinguishable from inert", which would have been a wrong conclusion reported in
the right format. Forty seeds resolved it. The rule now in the skill: size the ensemble from the arm's own
spread, and check the sd before reading a null.

**The eligibility table cost more thought than the probe, and the gate is where the thinking went.** The
first version failed at 2.75 % of (cell, PFT, establishment-year) triples and told me the derivation was
wrong. It was not — the *gate* was. Two things had to be modelled: the emitted `Age` is post-increment and
the two per-year inputs (`gdd5`, `aprec`) swing across their thresholds year to year, so the establishment
year is only known to ±1; and, far more important, reading `establishmentpft_ind.c` properly shows the
**inheritance channel is not bioclimatically gated at all** — it sits outside the per-PFT loop and tests
only that the cell has trees. A cell whose gate has closed keeps recruiting its own residents forever, and
22 % of cell-years are in that state. With both modelled the residual is 0.076 %, and it is arid-skewed on
exactly the clause the exemption cannot reach (a desert population living below `ind`'s 5 m threshold).

That finding is a correction to how the table must be *read*, not to the port: `w_inherit = 4/(4+n_elig)`
is 1 at `n_elig = 0`, and `draw_recruit!` already forces inheritance on an empty eligible set. I checked
that before writing it down, because the alternative reading — "the port is wrong in 22 % of cells" —
would have been a much more exciting and completely false journal entry.

The other basis correction is the kind this repo keeps having to make: FIT's gate reads
`mean_y(min_m T)` and the boundary table carries `min_m(mean_y T)`. They differ by 0.73 °C on average, the
three boreal PFTs have `temp_high` exactly 0.0, and at Hainich the wrong basis deletes all three. Both
columns are emitted side by side now, which is ADR 0060's lesson applied before rather than after.

Next session: the arm belongs to M's rung-2 harness (with the two added conditions, and noting M's own
ADR 0122 — the rendezvous lag makes a wood-density result unreadable there until M moves it behind the
growth loop). Arm D's bounded-Beta comparison is still the cheapest undone offline task. And if more
offline recruit measurement is wanted, it should buy **more cells**, not more seeds: the eligibility table
is exactly what makes a low-diversity cell (`n_elig` 1, `w_inherit` 0.8, inheritance dominant) runnable,
and that is a different regime from Hainich's throttled six-PFT one.

---

## Session 2026-08-12 — the recruit arm at three cells; and the ssp370 conditioning basis was not the trained basis (ADR 0171)

Started with the previous handoff's three items in order. Item 1 (raise the rung-2 recruit arm with M) was
written into `lines/M/STATE.md` first, since it was owed and cheap; the raise carries ADR 0170's numbers, the
four pre-registered conditions, and the eligibility table M can consume as-is, and it retires my own stale
caveat about the rendezvous lag — M's ADR 0123 had already removed it, which the previous handoff did not know.

Then item 3, "more cells, not more seeds." Two things happened that I did not plan.

**The `n_elig = 1` regime the handoff sent me to look for does not exist where it said.** The Amazon and Sahel
admit four tree types, not one, `w_inherit` 0.5 rather than 0.8. The belief traced to a comment in my own probe
that conflated the ids FIT *established* at those cells with the ids the gate *admits*. Checking the table
properly: `n_elig = 1` is 124 of 52 451 tree-bearing cells (0.24 %), the modal cell admits four (49 %), and the
regime where inheritance genuinely dominates is `n_elig = 0` — 11.2 %, and a median of 29 stems, so it is also
where the C's own noise is worst. That regime is still untested and is now the next handoff's item 2. Lesson I
should have applied without prompting: the handoff asserted a number I could have checked in one query before
building anything on it.

**The second thing was a defect, and I found it by writing a gate rather than by looking for it.** Making the
forcing builder per-cell meant replacing its two Hainich-fixture gates with per-cell equivalents, and the
natural reference for the boundary gate is the global trailing-W table the artifacts were actually trained on.
Gating against it exposed that the **ssp370** side had never had a monthly lead-in while the historic side
always had: 19 of 81 conditioning years were a different quantity from the training basis, by up to +210 gdd5
and +1.94 °C. A comment in the file asserted that omission was deliberate *and* consistent with the trained
table. Reading the global builder took two minutes and showed the opposite — it averages from the `.clm`'s own
first year. That comment is the most useful thing in the file: a confident justification for an absence is a
test nobody ran.

What kept the fallout small was instrumentation that was already there. The probe prints a boundary-channel
liveness line, and on the committed demo artifact it reads exactly 0.0 — that artifact's boundary axes are
constant in training, so it cannot express a boundary-mediated response at all. Every number in ADR
0100/0101/0170 was measured on that pair, so the defect provably could not have reached them, and the 40-seed
reproduction confirmed it to every digit. On the production pooled artifact the same line reads 2022–2406, so
the defect was caught exactly one step before the first measurement it could have corrupted — the cross-cell
arms, which all use that pair. I kept the off-basis arm runnable (`BND_FIXTURE=`, `SSP_LEAD=2020`,
`ALLOW_UNTRAINED_SSP_BASIS=1`) and ran it as a 40-seed control: where the channel is live the fix is worth
0.03 ×FIT against a 0.32 ×FIT SEM. Real, correct, an order of magnitude below the noise — which is the honest
way to state a defect's size, and impossible to state at all if you delete the old basis when you fix it.

The science: the level effect survived the move to three cells (+2.20 / +4.93 / +5.00 %, t ≥ 5.1) and is now
the three-cell reason the flip stays refused. The response-sign headline did not survive — the contribution is
−0.89, +1.98, −1.91 ×FIT at the three cells, and it also reverses at a *fixed* cell when the artifact pair is
swapped (+3.41 → −0.89). So ADR 0170 §2 needed narrowing, and the pre-registered flip criterion needed a third
condition: one cell per gate regime, artifact fixed and named, sign must agree. The finding I did not expect
was R0's own behaviour: at Siberia the *shipped* configuration already overshoots FIT's warming shift by 94 %,
and the port removes that response instead of adding one. A contribution's sign is meaningless without its
baseline printed next to it.

One process note for whoever reads this next. I reformatted the probe (Runic) while some ensemble jobs were
still pending, so a few runs read a file whose indentation differed from the earlier ones. The change was
indentation of one continuation line inside a printed string, so no output moved — but the general shape is a
real hazard: editing a script that queued jobs will later read is a silent way to make an ensemble
inhomogeneous. Either submit after the last edit, or copy the script to a run-specific path.

---

## Session 2026-08-12 (b) — closing out line S's own rungs: five cells, arm D refuted, and the exit verdict nobody had written

The instruction was "finish line S". That is not the same as finishing the emulator, and the first useful
thing was to work out which of the two was on the table. Line S owns rungs 0 and 1 of the attribution ladder;
rung 0 was closed by ADR 0111; rung 1 had four arms, three of which were done, and an exit gate with two
clauses of which only the first had ever been answered. So "finish line S" = run the last arm, close the gate,
and hand the rest up. That is what this session did, and the honest headline is that **rung 1 closes with one
pass and one failure, not with a pass.**

**The cross-cell table (handoff item 1) went exactly as scoped and then said something better than expected.**
Two more cells, two commands each, 80 jobs, all 80 usable. The level effect held at all five cells — that part
was predicted. What was not predicted is that the three cells sharing the *same* eligibility regime disagree on
the response contribution beyond seed noise (Q = 8.03, p = 0.018, I² = 75 %) while the *shipped* channel's own
response over those same three cells is homogeneous (Q = 0.51, p = 0.77, I² = 0 %). I nearly did not compute
that. My first draft of the changelog fragment asserted "the three cells split +1.98 / −1.67 / +3.56", which
reads as two established signs — but one of those three is not significant, and with the point estimates alone
you can tell two opposite stories ("the sign is cell-idiosyncratic" and "the sign is set by the regime") and
both look supported. The regime story was actually the *better*-looking one on a glance: the two significant
negatives sit at n_elig 6 and 3, both significant positives at n_elig 4. Only Cochran's Q separates them.
Lesson I want the next session to inherit: with five cells the eye is not a statistic, and a flip condition
written from the eye gets grouped on the wrong variable — which is what happened to ADR 0171 §5, by me,
yesterday.

**Arm D was the one I expected to be a modelling task and it turned out to be an archaeology task.** ADR 0118
suspected the "bounded Beta beats the copula 2–3×" number compared an oracle-moment Beta against an
out-of-sample copula. It does — and worse. The reproducer existed, uncommitted, on scratch, and reading it
showed the two sides of the ratio are not the same statistic at all: one-sample KS with parameters estimated
from the very sample being tested, per (Cell, PFT), on the top-400 densest cells per PFT, with the script's own
comment saying "to give the Beta its best case". Three confounds in one number. I priced each, and the thing
I am gladdest about is the arm that was not asked for: simulating data that genuinely *is* Beta and
re-estimating its moments gives a median KS of 0.043–0.048 at n = 150, and two of the four published Beta
numbers are 0.0437 and 0.0476. The number was at its own noise floor. It never had the power to measure what
it was quoted as measuring. Then the like-for-like: with each test cell's own observed moments, the Beta ties
the out-of-sample copula on two axes and is 7–12 % worse on the other two. There is no advantage to recover,
so arm D is descoped rather than run — and ADR 0093 §5.3's `[MEASURED]` tag comes off.

**Two gates I wrote caught real things, and in both cases the gate mattered more than the measurement.**
(1) I built the regime-table reproducer to gate against ADR 0171 §4's published numbers, expecting to confirm
them. It failed by a factor of three, and the cause was that the ADR's table is classified by a 20-year
*minimum* while its header says "(2010)". Same cell universe to the unit (52 451), different partition. The
"11.2 % pure-inheritance regime" the handoff sent me to measure is really "dips into it at least once"; the
persistent class is 1.4 %, at one stem per patch, which is inside the stratum where the C's own two runs differ
by 31.6 %. So that arm is descoped too, on arithmetic rather than on preference. (2) The arm-D part-2 gate
comparing my re-derived copula column against the table's *stored* one failed — and so did the **stock,
unmodified** evaluator re-run on a copy of the same table. The stored OOS predictions on the scratch tables no
longer correspond to today's code, while `drf.jl`'s default numerics are unchanged. That is the exact trap the
obvious arm-D implementation walks into: stored column as one arm, fresh column as the other, and a code change
sitting silently inside the family comparison. I restructured it as two gates with different severities — fatal
on the invariant the comparison rests on, reported on the anchor to the stored artifact — because a rotting
artifact discovered *inside* a comparison is indistinguishable from a scientific result.

**The exit verdict was the most valuable thing here and cost no compute at all.** Rung 1's gate asks for the
compensating-errors verdict; no document stated one. Ten ADRs each had a piece. Written out, the verdict is
yes, with three named channels, and the middle one is the sentence I would keep if I could keep only one: the
recursion follows 86.7 % of a large decline but 96.2 % of a large increase, FIT's global response is a net
loss, so the one-sided error *rectifies* into +0.155 stems/patch — which is the same size as FIT's entire
global count response. **The component passes its level gate because of the error that fails its response
gate.** That reframes every "the level is fine" statement in this line's history as a warning rather than a
reassurance.

One process note. I reformatted the arm script (Runic) after submitting two jobs that would read it. The
changes were provably semantics-preserving (`1e-300` → `1.0e-300` and line reflow), but I cancelled and
resubmitted both anyway, because last session's journal entry flagged exactly this hazard and "provably
harmless this time" is not a habit worth building. It cost ten minutes of compute and bought a clean
provenance claim. Then I did it *again* — cancelled two more running jobs to fold the determinism-dividend arm
into the same pass, so all three arms come off one set of forests instead of two. That one was worth it on the
science: identical forests across arms is a stronger claim than matched hyperparameters.

What line S still owes after this is small and named in STATE. What the *project* still owes is not small, and
rung 1 closing does not touch it: the response clause of the acceptance criterion is failed, offline, with a
measured horizon of about three years, and everything that could fix it is upward on the ladder.

## 2026-08-12 — rung 2 arm S RUN and SCORED: the trait operator's advantage is 85 % interface (ADR 0176)

Picked up the handoff's item D1 (run `S0`/`S1`, score against `NP` and the record baseline) and finished the
housekeeping it left open.

**Housekeeping first, since branch CI is ~10 min of wall clock and the arms are 12 s.** Rebased, pushed
`cf872a36`, launched the arms while `CI`/`format` ran, then merged `line/S` → `main` at `91581373` with the
changelog collated inside the lock. Required gates green (`test (pre)` red as always). Recorded rung-2
ownership in `EXECUTION_PLAN.md` itself at `aa5b2dc1` — the owner steer was the trigger, and the plan file is
where a line looks up what it owns; the S → M integration point is marked dormant rather than deleted.

**The pre-registered check passed, which is the only reason anything below counts.** `NP` (persistence null)
does NOT tie the learned arms: 1.803× the C's terminal stems with *zero* seed spread, against `S0` 1.490 /
`S1` 1.028. Offline (ADR 0112) the same null matched the production model on every response statistic — so
the harness has power the offline basis did not.

**Then the thing I nearly published wrong.** The naive reading of `S1` 1.028 vs `S0` 1.490 is "trait
selection works". But `S1` differs from `S0` in *two* ways at once — `f_i = (1−mort)^θ` is zero wherever
FIT's hazard is already certain, *and* it orders survivors by trait — and the C's own audit showed `S0`
sparing **1 952 trees the C was certain of** against `S1`'s 358. So I added `ARM=S0h` (uniform among the
non-certain, same count target, 12 s × 5 seeds) to price the two separately. The interface removes **87 %**
of the count error and **84 %** of the selection error; trait ordering 13 % / 16 %, and contributes nothing
measurable to the age–wooddens gradient (`S0h` and `S1` have *identical* per-PFT Spearman). `S0h → S1` is
not even resolved at 5 seeds on counts (t = 1.69).

That re-attribution is the ADR's point, and it changes the `trait_mortality` flip argument rather than
settling it: the part that demonstrably helps rests on **FIT's own** `mort ≥ 1` set, and the coupled
emulator uses the **ported** hazard, which lacks FIT's stress integrals (ADR 0174 §4). So ADR 0049's
unmeetable offline criterion is retired and replaced with a narrow, run-free one (certain-set recall and
precision ≥ 0.8 on ≥ 12 cells).

**Two process notes.** (1) The arm-C scorer's harness-log reader was *positional*, and the two harnesses do
not share a column order (field 4 is `rho` in one, `n_emit` in the other) — it would have scored the S arm
on arm C's columns without a word. Made it header-driven. (2) I hand-rolled a column-by-column dump
comparison to test `NP`'s seed-independence, then found `scripts/diagnose_rung2_dump_equality.py` already
does exactly that, excludes the known-uninitialised `sapwood_old`/`pre`-phase `mort_*` columns, and returns
a clean *"identical in every initialised column"*. Threw mine away. The skill was right and I should have
read it first.

**Not done, and it is still the deliverable:** the warming response. Everything here is historic-only and a
LEVEL statistic; ADR 0174's rung-1 response verdict is untouched. The scenario-pair run at ≥ 12 cells is
item 1 of the handoff.

## 2026-08-12 — rung 2 over the scenario pair: the warming response, measured at 12 cells (ADR 0177)

Built and ran the scenario-pair experiment the standing steer asks for. 510 runs: 15 pre-registered cells
(gdd5 519–9043), both legs, per-cell **and per-scenario** `REC` baselines, arms `NP`/`S0`/`S0h`/`S1` × 5 seeds.

**Result is negative and clean.** FIT's own response is not one-signed (thins at 7 of 12 cells, gains at 5).
Every arm thins almost everywhere ⇒ sign correct 7/7 where FIT thins, 1/5 where FIT gains — and the
persistence null reproduces that pattern exactly (8/12 for NP, S0, S0h alike). So on DIRECTION the count
model buys nothing. It buys magnitude (slope 1.33–1.48 vs the null's 2.56), but I² = 93–99 % kills the
pooled slope as a summary.

**Three defects fixed on the way in, two of them fatal to the measurement.** (1) The harness read its
bioclimatic tail ONCE from the 5-cell registry, whose value is the 2000–2019 climatology — an ssp370 leg saw
present-day climate for all 81 years, so any response was ~0 by construction. The shipped runtime never had
this (ADR 0026) and the forest was trained per-(Cell,Year), so it was also a train/inference split.
(2) `run_daily_subset.sh` could not generate a runnable ssp370 config at all (dead CO2 path).
(3) The baseline and the arms had drifted onto different binaries after M's ADR-0130 rebuild.

**Caveat I could not close this session:** the legs differ in length (20 vs 81 yr), so the raw pair mixes the
climate response with 61 years of drift. The frozen-climate control that separates them is written and
tested (`BOUNDARY=frozen`) — it is the next action.

**Discovered two limits of the C hook** (M's `rung2_apply.c`): the `duplicate roster key` guard killed 82 of
510 runs, fires in the observation path too, is cell-specific, and cost 3 cells their baseline — mechanism
still open, `fread_tree.c:64-66` rules out the two obvious explanations. And cell 22732's ssp370 `S0h`/`S1`
arms hang at the rendezvous reproducibly.

**Process mistakes worth not repeating:** edited a bash script while a 510-job submission loop was reading it
(bash resumes mid-token → `syntax error near unexpected token '('`); ran the campaign on `priority`, whose QOS
caps a user at 10 concurrent jobs; and `pkill -f` on a pattern that also matched my own waiter loops. All
captured in the `lpjmlfit-cbinary` skill.

## 2026-08-13 — the frozen-climate control: there is no climate response (ADR 0178)

Ran the control ADR 0177 §5 pre-registered (240 runs, 187 complete). It validates itself — the persistence
null's climate term is exactly 0.000 at all 12 cells, as it must be, since ρ=1 never consults the model.

Against that: drift is 94.4 / 97.2 / 99.8 % of the magnitude for S0 / S0h / S1, and the surviving climate
term's slope against FIT's own change is −0.031 / +0.044 / +0.003. **Essentially the entire apparent
response in ADR 0177 was drift.** The count model does not respond to climate in a measurable way when it
runs free inside FIT's physics. That also gives ADR 0177's "matches the null on direction" its mechanism:
on the climate channel the arms ARE the null.

Resolves ADR 0175's roster_n_prev falsifier negatively — n_prev is the stand's own count throughout and the
response is still ~0, so that defect is not the mechanism.

Next is cheap and needs no LPJmL run: a partial-dependence sweep of the trained forest over its two
transient climate features, to separate "never learned a climate dependence" from "learned one the loop
cannot express".

## 2026-08-13 — the sweep: the climate channel is open and empty; de-leaking buys 2.8× (ADR 0179, 0180)

Ran the pre-registered next action (job 1771609, 4 min, no LPJmL run). Added a third hypothesis before the
run, which turned out to matter: a forest pooled over 58 588 cells is *certain* to split hard on gdd5 as a
CELL IDENTIFIER, so a naive full-range sweep would have shown a big dependence and read as "the loop is the
defect". Emitted the pooled and within-cell panels side by side (ADR 0118) plus a live-channel anchor.

**The liveness panel is what stopped me writing the wrong thing.** The forest splits on the two climate
features 77 440 times — 10.20 % of all splits, thresholds across the whole global range. So "it never
learned climate" in the sense of "there are no splits" is flatly false, and that is the sentence I would
have written. `co2` is the feature with 0 splits, exactly as designed.

And yet: 0.227 / 0.066 / 0.281 stems of partial dependence over the ENTIRE global range; 0.0568 stems over
the operative per-cell warming excursion = 4.4 % of the `n_prev` anchor, under 10 % of FIT's own response at
9 of 12 cells, over 50 % at 0 of 12. The local full-range sweep per cell gives 0.345 — no steep surface
anywhere, so H3 dies too. Verdict H1: the training target/feature set is the defect.

Two cells returned exactly 0.0000 on the anchor. That is quantization, not a bug — `n_prev` splits sit at
half-integers because per-patch counts are integers, and those cells' observed shifts stay inside one bin.
It biases the anchor DOWN, i.e. conservative for the conclusion.

Then priced the mechanism rather than asserting it (job 1771616). One-variable arm, `n_prev` neutralised in
place so p/mtry/indices are identical. Two basis checks first: the sample reproduces ADR 0112's null R²
(0.9623 vs 0.9622) and CTRL reproduces the shipped artifact (10.10 % vs 10.20 % climate splits, R² 0.9801 vs
0.9824). Result: climate response ×2.85 (0.0836 → 0.2381 stems, 4.7 % → 13.5 % of FIT's), larger at 13 of 15
cells (median 2.44), for 0.018 of R². Sign agreement 7/12 → 8/12 — magnitude, not direction. Verdict
PARTIAL, and explicitly NOT a licence to buy the global retrain.

**The finding I did not expect, and it is the important one.** With `n_prev` gone entirely, R² is 0.9620 —
indistinguishable from the persistence null's 0.9623. The other 13 features reconstruct the count as well as
FIT's own lagged answer, because six of them describe the SAME year's stand and a stand of given
agb/cover/height/age holds a nearly determined number of stems above the 5 m cut. So dropping `n_prev` does
not de-leak the target; the count is close to an allometric consequence of the stand. At runtime those six
come from F's own pools (ADR 0023), so that is not a runtime leak — but it does mean the count model's
climate inputs are a small correction on a stand-to-count map, and the coupled warming response has to
arrive through F moving the stand. Which is the pathway ADR 0178 measured as ~0.

Also worth noting the split share barely moved under the ablation (10.10 % → 9.87 %) while the effect nearly
tripled: the climate splits were always there, `n_prev` was muting them, not crowding them out.

## 2026-08-13 — ADR 0181: the count model is a stand diagnostic, and ADR 0178's "drift" bucket hid the stand channel

Took the handoff's flagged action ("drive the count model with FIT's OWN stand under both scenarios — a
table scan, not a run") rather than the target redesign it listed first, because the redesign was
conditional on the stand pathway being dead and that had never actually been measured.

Wrote `scripts/slow_stand_forced_response_probe.jl`. K-fold BY CELL over 51 767 of 54 020 cells, CTRL vs
the ADR-0180 in-place `n_prev` ablation, plus a four-group corner decomposition (FLUX / STAND / AR / CLIM)
that maps each feature group to the part of the system that computes it at runtime. Smoke first
(PSTRIDE=512 → the guard fired: 4 rows/cell, no scorable leg; a config error, not a result), then
PSTRIDE=16, then production. Jobs 1772580/1772581/1772586 + scorers 1772587/1772872.

Four basis checks passed before any arm was read; the strongest is that the retrained control reproduces the
shipped artifact's **response statistic** exactly (area-weighted 0.707 vs 0.707), not merely its skill.

Result: the de-leaked map delivers **0.292** of FIT's area-weighted warming response given a perfect stand
(shipped 0.707, persistence null 0.685) ⇒ pre-registered verdict PARTIAL. The channel decomposition is the
deliverable: **STAND slope 0.994, CLIM 0.016, FLUX 0.037**. So the count is an allometric consequence of the
stand and its response is inherited, not learned — and the target redesign the handoff pre-registered is
aimed at the wrong lever.

Two things went wrong and are recorded rather than tidied away.

1. **The probe's verdict expression keyed on the per-cell slope** — the statistic ADR 0112 already proved has
   no power (all four arms including the null score 0.97–1.03) — and printed `H_map SUPPORTED` for an arm the
   binding statistic calls PARTIAL. Both threshold pairs were pre-registered in the file; the expression just
   used the wrong one. Fixed: the script now prints no verdict and names the job that decides it.
2. **The scorer silently rewrote a committed shared fixture** (`S_truth_yardstick_summary.csv`, 66 deletions)
   because `OUT_SUMMARY` defaults there and a COUNT_DIR-only run drops the trait rows. Reverted before
   anything was committed; re-ran with the redirect (job 1772872) and reproduced every digit.

And the finding I did not expect to make: **ADR 0178's frozen arm freezes only the 4 boundary columns**
(read the writer, not the prose), so the stand-mediated response is inside its `drift` term by construction.
"ADR 0178 measured that pathway as ~0" — in ADR 0180's text and in the handoff — is false. Nothing of
ADR 0178 is withdrawn; the sentence built on it is.

Next action pre-registered in ADR 0181 §7.3 and the STATE handoff: reconstruct each rung-2 arm's OWN
`hmean/hmax/agb/lai/fpc/age_mean` from the dumps already on disk and compare its historic→ssp370 shift
against FIT's ~0.30 sd. That decides whether the remaining defect is in S or upstream in the fast core.
Liveness panel first.

---

## Session, 2026-08-13 — the arms' stand DOES warm; the ported hazard is exact; `trait_mortality` flipped ON

Two measurements, both on dumps already on disk, no LPJmL run. Both were pre-registered by earlier
sessions and both had a decisive answer waiting in data we already had.

**1. Does the emulator's own stand warm? (ADR 0182, the action ADR 0181 §7.3 pre-registered.)** New
scorer `scripts/diagnose_rung2_stand_warming.py` reconstructs the six `flux_feature_vector` stand
features per (year, patch) from the `grow`-phase roster records of all 510 rung-2 dumps (~38 GB of text,
16 workers, one `.npz` cache per dump) and scores each arm's historic→ssp370 leg shift in per-cell sd
units against FIT's own at the SAME cells — the `REC` observation-path dumps, through the same parser,
rather than ADR 0181 PANEL 1's 51 432-cell global median.

Basis check first: `REC`'s median per-feature |z| is 0.21–0.37 (median ‖z‖ 0.809), reproducing PANEL 1's
~0.30 on 12 cells. Liveness clean. 92 of 510 legs excluded and named — all the two known interface
faults, nothing new.

The pre-registered PASS branch fired for all three real arms: `S0` RATIO 1.426 / COSINE 0.876, `S0h`
1.652 / 0.758, `S1` 1.634 / 0.907. **The "the stand does not warm" hypothesis is closed.** Splitting the
cells by how much FIT's own stand moves sharpens it a lot: where FIT's shift is large the arms track its
direction at **cosine 0.97–0.99**; where FIT barely moves they move anyway (RATIO 1.8–3.1) in unrelated
directions.

Two things stop this being a credit to the emulator, and I wrote both into the ADR rather than leading
with the PASS. The persistence null `NP` — which learns nothing — tracks FIT's stand direction at 0.910
in those same cells, because in a rung-2 arm the **C grows the stand** and every arm inherits its shift.
And the declared drift control (the same statistic between the two halves of the historic leg, same
forcing, no excursion) puts the arms at 3.0–3.6× and **`REC` itself at 5.39×**, with the arms' absolute
decadal mobility in the same ~1.5× proportion as their leg shift ⇒ RATIO > 1 is stand MOBILITY, not a
stronger warming response. I nearly had a table that read "the arms warm 1.6× more than FIT". They do
not.

Also corrected the handoff's branch B.3: a rung-2 arm cannot indict "the fast core", which never runs
there.

**2. Does the ported hazard reproduce FIT's own? (ADR 0183 — and the flip.)** While writing the first
scorer I checked what `S0h`/`S1` actually feed their certain-kill test, because ADR 0176 §4 rests on it.
`rung2_s_demography_harness.jl:539` reads `Tree.mort`, and that field's own comment (:206) says
`TraitMortality.mortality_hazard`. **The arms were already using the port**; only an inline comment at
:533 calls it "FIT's own hazard". So ADR 0176 §4's premise was wrong and its blocker was pointed at the
wrong thing.

Measured the criterion anyway with `scripts/diagnose_rung2_ported_certain_set.jl` (reaching the hazard as
the shipped name — no second copy). Over **1 568 744 stem-years at 15 cells**, both scenarios, 0 stems
dropped: recall = precision = **1.0000**, mean |Δhazard| = **5e-18**. Handed the C's own per-tree inputs
the port simply *is* `mortality_tree_ind`.

Then the number that actually decides the flip: the same hazard with `water_stress`/`temp_stress`
**zeroed**, which is what `slow.jl::_trait_hazards!` feeds it unless M's `trait_drought_mortality` is on.
Recall **0.9087–0.9718** at precision 1.0000 — passes ≥0.8/≥0.8 with the coupled loop's own degraded
inputs. The structure is the interesting part: those two hazards carry **29–37 % of the graded hazard
mass but only 3–9 % of the certain kills**. And precision is 1.0000 for structural reasons (zeroing two
non-negative additive terms can only lower the total), so recall is the only informative half — worth
noticing before quoting a precision/recall pair.

⇒ **flipped `trait_mortality` default `false` → `true`**, per ADR 0176 §4's own pre-registration and the
owner's standing steer that "it is opt-in" is not a sufficient answer. Guardrail 4 is re-served by the
opt-out. Ran the full CI-faithful suite with only the default changed so the failure list is the measured
blast radius. Did NOT flip `trait_drought_mortality` — line M's file, and the certain set does not need
it; the unmeasured residual is trait ORDERING among non-certain stems, with its own criterion
pre-registered in ADR 0183 §5.4.

Blast radius came in at **5 assertions of 275 605**, all in one testitem and all one cause — that file's
CONTROL arm was constructed with no kwarg, i.e. it *meant* "the old default", so at the flip it became a
second copy of the arm. Every assertion whose meaning depended on the two arms differing moved; nothing
else did (no conservation gate, no AD gate, no committed baseline). Fixed by passing `trait_mortality =
false` explicitly with a comment saying it must stay explicit, plus a new assertion that reads the flag off
the CONSTRUCTOR so a silent flip back cannot pass the file. Re-run green: **275 606 pass / 0 fail**.

Also audited the other 75 construction sites (`julia-test` step 5/6). The test files are proven insensitive
by the green suite; six PROBE scripts take the default by omission and I deliberately did NOT edit them —
guessing which meant "whatever ships" versus "the uniform thinning" would be inventing intent. Recorded the
labelling rule instead: every number those six have already published is a pre-0183 uniform-thinning number.

One caveat I went looking for rather than waiting to be bitten by: `_trait_hazards!` looks up per-PFT
mortality parameters from `fc.pft_ids`, which DEFAULTS to beech for every tree. Nothing errors, but an
unwired coupled caller now runs the ported hazard on beech's mortality parameters — and those are strongly
per-PFT. The measurement used the C's own ids, so it does not license the flip for an unwired caller; ADR
0183 §5b says so.

---

## Session — 2026-08-13 · the map-on-arm-stand loop closure (ADR 0184)

The handoff's pre-registered action was to run the count model on each arm's own stand and reconcile ADR
0181's 0.292 with ADR 0177's null. It turned out to need almost no work: the harness already writes its own
`target` — `DRF.predict` on that arm's own stand — at every rendezvous, into `<apply>/s_arm_log.txt`. Four
of the five arms were therefore already measured, sitting in a 170 kB text file beside dumps that two
previous sessions had scanned 38 GB of for stand features the same file already carried. That is now the
first line of the `rung2-dump-analysis` skill.

Only `REC` lacked a log, because pure observation never starts a harness. I supplied it by replaying FIT's
own dumps through the shipped `flux_feature_vector` + `DRF.predict` rather than a copy (ADR 0023), which
needed one small change: the harness's `exit(main(ARGS))` now sits behind the repo's standard
`PROGRAM_FILE` guard so its `Tree`/`pools_of`/`flux_drivers` can be reused. The gate for that reader is the
part I am happiest with — in year 2000 no arm has killed anything yet, so the offline row must equal the
live rendezvous row, and it does to the last printed digit (`target = 6.819800183403388`). Cheap, and it
made the reference trustworthy without argument.

Then the result, which is not the one the handoff expected. `ASK ≈ GOT` at every cell for every arm, which
reads as "the operator transmits the map's ask faithfully, so the loss is upstream" — and the pre-registered
verdict duly fired `CONDITIONING-LIMITED`. I did not believe it, because the basis check had passed *too*
well: the map on FIT's own stand agreed with FIT's own count direction at 12/12 cells with a slope of 1.058.
Numbers that clean, on an axis where ADR 0177 measured I² of 93–99 %, are usually a null in disguise. They
were. Every rung-2 run used `--n-prev=roster`, which hands the model the live stem count; measured,
`target/n_emit` = 1.00 ± 2.3 %, within ±5 % in 84–87 % of patch-years. The model's target *is* the count it
was handed, so ASK and GOT are the same quantity and the null `target = n_prev` scores 12/12 by
construction. I overrode my own pre-registered branch and recorded NO VERDICT.

The lesson I want to keep is sharper than "score the null too" — ADR 0181 already did that, and this probe's
header already named the trap. What was missing was one line of algebra: *derive what the null must return
for the blessed statistic, and write that number beside the threshold.* It would have voided the basis check
before a single job ran.

Two things came out of it that are worth more than the original question. First, it collapses ADR 0180 and
ADR 0181 §7.4 into one mechanism — with the live count the model is accurate but mute, without it expressive
but mis-levelled — and it narrows ADR 0177 from a statement about what the model learned to a statement
about the configuration it ran in. Second, and independent of all the count arithmetic: nothing anchors the
stand's size/age structure. By 2100 the arms hold ~15 % fewer stems but +99–106 % above-ground biomass and
+47–84 % mean age than FIT, growing monotonically from ~+38 % at the historic leg, and the do-nothing null
departs worst of all at +312 %. ADR 0182's cosine of 0.97–0.99 is still true; a correctly-directed z-scored
shift on a 2× displaced level is simply not the same conditioning, and no count statistic on this line can
see it. That is the first defect here that provably needs a size-resolved measurement of *who dies*.

I also checked whether the recommended fix is real before recommending it. `predict` mode — the shipped
coupled path — had never been run in this harness. A 12-job smoke succeeded, and it caught my own
pre-registration being on the wrong statistic: |ρ−1| barely moves (0.024 → 0.037, under my 0.10 threshold)
because ρ is a ratio of two smooth tree-ensemble outputs in *both* modes. The right metric is the level
decoupling, `target/n_emit`, which goes from ±2.3 % to ±24 % (±28 % late century). So the question is
answerable there, and the full 264-job matrix is submitted with its reading pre-registered on the corrected
metric. Next session scores it; ρ first, then the gain-cell signs, and `REC`'s 12/12 labelled as the null's
every time it appears.

## 2026-08-13 — the `predict` matrix is scored: the limit is the stand, not the operator (ADR 0185)

Executed ADR 0184 §10.4's pre-registered reading on the 264-job `--n-prev=predict` matrix (258 completed,
6 lost to the known `--max-idle` harness timeout). No new model run, no flag flipped, no artifact
regenerated.

Two S-owned scorers gained an `NPREV` knob, default `roster` so every published number reproduces:
`diagnose_rung2_map_target_response.py` (regex + completion gate) and `diagnose_rung2_map_on_rec_stand.jl`,
which also gained the shipped `n_prev[patch] = target` recursion mirroring the harness. The second one
mattered more than it looks: `REC` has no runtime log, so its column is replayed offline, and had it been
left in `roster` the reference would have sat on a tethered axis while the arms ran free — invisible.
Gated it on the year the recursion cannot touch: 600/600 first-year rows bit-identical to the `roster`
replay, 78.3 % of 29 700 later rows differing.

Added the pre-registered separability gate to the scorer, printed before any response statistic. It
refuses the `roster` matrix (0.018–0.031, NO VERDICT — reproducing 0184) and admits `predict` (ssp370 leg
0.13–0.35). The awkward part, recorded rather than buried: the `predict` *historic* leg reaches only
0.079–0.099, and keying the verdict on ssp370 was decided after seeing that. It is defended by algebra —
the blessed statistic is a difference of leg means, so a tethered baseline leg deletes a term from the
ASK-vs-GOT contrast instead of collapsing it — and the scorer now prints the strict per-leg alternative
(NO VERDICT) on every run.

Result: `ASK_gain(REC)` = 4/5 with the do-nothing null at 1/5, learned arms 1–2/5 ⇒ CONDITIONING-LIMITED.
The derivation that makes it readable, and the thing 0184 was voided for missing: in `roster` mode `REC`
and the null are both 5/5 *by construction*; in `predict` mode they separate, and since `REC` and the arms
run the same map with the same free-running recursion and differ only in the stand they read, the gap is
attributable to the stand. Mechanism is 0184 §7's departure, now operative: +89–312 % agb, +54–160 %
`age_mean` vs FIT.

Explicitly NOT concluded: the operator is not refuted, only untested — with the map not asking for the
gain it never got the chance to fail. Said so in the ADR and in settled item 7 of the handoff, because
"the operator is fine" is the reading this result invites and does not support.

Next action handed on: wire ADR 0103's `anchor` into the rung-2 path (a harness change — the harness never
builds a `FluxDrivenSlowEmulator`), with the conjunction criterion pre-registered in 0185 §7.5.

---

## 2026-08-13 — the anchor was never the lever: the count is on target, the mass is not (ADR 0186)

Picked up the handed-on action — wire ADR 0103's level anchor into the rung-2 path and run the 12-cell
`predict` matrix against 0185 §7.5's pre-registered conjunction. Did not run it. Two derivations that
0185 had not done, both answerable from logs already on disk, said it could not pass.

**First, what the anchor even is here.** It does not carry over from `slow.jl` unchanged. The coupled path
feeds the whole roster to `flux_feature_vector` and anchors on the whole roster's density; this harness
deliberately splits them (`pools_of`: feature row and count target on the >5 m emitted population, thinning
on every tree). So the anchor's `D` must be the emitted density, and then `patch_area` **cancels**:
`ρ_eff = (target/n_prev)^(1−a)·(target/n_emit)^a`. Two consequences fell straight out. It is **identically
inert in `roster` mode**, because there `n_prev := n_emit` — verified, 916 484 rows bit-identical, max
|diff| exactly 0, which also means no published `roster` number was ever at stake. And `a` moves only the ρ
conversion, never the feature row, so `a = 1` is not a return to `roster` mode and 0184's tether stays off.
Worth noting for its own sake: the anchor was *unmeasurable* in rung 2 until 0185 opened the `predict`
axis. It sat unreachable for a mechanical reason, not because three sessions overlooked it.

**Second, and the actual finding: the anchor's lever is the count, and the count is already right.** On the
ssp370 leg at the FIT-gain cells `S1` holds **−2.9 %** the stems FIT holds and **+90.6 %** the biomass;
`S0h` −13.6 % and +89.0 %. Per-stem mass +63…+246 %, corroborated in the same direction by `hmean`
+12…+38 %, `hmax` +14…+45 % and `age_mean` +53…+160 %, so the decomposition is physical rather than an
artefact of dividing two medians. The stand is not over-numerous. It is over-massive.

I went looking for the one alternative that would have rescued the anchor — that the count departure was
large mid-leg and had merely closed by 2100, in which case an anchor acting throughout would have stopped
the mass accumulating. It is not there: `S1`'s count sits within a few per cent of FIT's in **every decade
of the 81-year leg** (+4/+1/−0/+0/−7/+5/−2/−3 %) while biomass climbs monotonically +18 → +91 %. `S0` and
`NP` do open a +26…+39 % mid-leg gap, and they are exactly the two arms without the trait operator.

So the criterion is unreachable, and generously so. Granting a perfect anchor and letting biomass follow
the count proportionally — the anchor cannot touch per-stem mass at all, so this is the most favourable
bound available — the surviving agb departure is +75.6 % (`S0h`), +117.2 % (`S1`), +194.5 % (`S0`),
+415.1 % (`NP`), against the +40 % that had been fixed in advance. For `S1` the bound is *worse* than doing
nothing, because the target sits below FIT's count while the mass sits far above it. A second reason
surfaced on its own: the anchor DOES clear +40 % on the historic leg, and an instrument that corrects the
baseline leg but not the future leg manufactures a response, the blessed statistic being a difference of
leg means. That is 0185's own gotcha arriving from the other side.

**The basis error I made, because it is the instructive part.** My first reachability panel re-implemented
the departure statistic — 20-year window, mean over cells, mean of per-patch ratios — and reported `S1`'s
ssp370 count departure as **+37 %**. The criterion's own basis gives **−2.9 %**. A sign flip, on the same
data, on the single quantity the decision turns on; per-patch counts are 4–11 stems, so patches where FIT
holds one or two stems dominate an unweighted mean of ratios. Caught it by noticing my table disagreed with
0185 §5's published one, rewrote the panel to `import` the scorer and reuse its `Leg`, readers, `median`
and coverage gate, and it now reproduces that table exactly. Reproducing the published table is the gate,
and it belongs before adding a column to it, not after.

**What this does and does not settle.** 0185's conditioning-limited verdict stands and is sharpened — the
limit is still the stand the map reads, and now we know the displaced coordinate is size and age rather
than count. It is explicitly *not* a finding against ADR 0103 in the coupled path, where the measured
departure genuinely is a count-level one (1.409× over-density with no restoring force) and the anchor is
still the right instrument; that flip criterion is untouched and still unrun. And it is still not an
operator verdict: hitting the right count while holding the wrong size distribution is consistent with a
mis-ordered kill rule *and* with a kill rule never given enough deaths to allocate.

Next action handed on: the size-resolved "who dies" comparison, promoted from secondary to primary on
measurement rather than preference. The count statistic is *satisfied* while the stand is wrong — that is
the proof a count statistic cannot see this failure. The kill lists are already on disk in the apply dirs
and the `grow` dumps carry every stem's size and age, so it needs no model run either. The defensible
statistic on diverged stands is a size-conditional mortality rate, not a comparison of who was killed.

Cost of the whole session's measurement: about seven seconds of login-node compute, against the 264 jobs
the plan called for.

## 2026-08-13 — ADR 0187: the kill set is NOT size-biased; the shortfall is the mortality RATE

Executed ADR 0186 §B's promoted primary action (the size-resolved "who dies" comparison) and it came
back **negative on the hypothesis** — a clean refutation, not an inconclusive.

**Data.** ADR 0186 §B planned to read the harness's `rsp_r*_y*_p*.txt` kill lists and flagged "check
they still exist". They are **gone** (the `_apply` dirs hold only `audit_r0000.txt`, `s_arm_log.txt`,
`harness.ready`). Not needed: under ADR 0123 the binary defers its kills, so the `mort`-phase roster
carries every killed stem flagged `isdead` on a roster identical in length to `grow`. Gated the
extraction against the harness's own audit log before using it — 2025/2025 patch-years, 940 = 940 on
the development leg, then 234/234 audit-bearing legs in the full run.

**Result** (`scripts/diagnose_rung2_kill_selectivity.py`, job 1779616, ~9 min, 24 GB, 12 cells × 2
legs, no model run). Mass selectivity `LAMBDA = kill_frac_m/kill_frac_n`, ssp370, FIT-gain median:
FIT **0.900**, `S0h` **0.996**, `S1` **0.926** — both inside the pre-registered refute band, sign
opposite to the hypothesis. Corroborated by near-zero selection differentials (FIT itself is only
weakly size-selecting: −0.066 height) and by the size-conditional rate profile having **FIT's shape at
2.9–4.6× lower level in every quintile** — a selectivity defect tilts the profile; this shifts it.

**What is actually wrong:** the discretionary kill rate (FIT 2.1 %/yr vs `S1` 0.6 %) and hence the
annual mass flux (FIT 0.0306 vs `S1` 0.0178 ⇒ **58 % of FIT's**), which compounds to **2.90×** over 81
years — more than the observed +90 % agb. It reconciles with ADR 0186's "count on target" because FIT's
kills are dominated by CERTAIN deaths (starving suppressed stems) that the arms honour by construction
and that carry almost no mass. So: right number, right kinds, **far too few of the ones carrying
biomass**.

**Two basis errors, both caught by the pre-registered derived-a-priori self-test on the uniform arm** —
this is the part worth carrying forward. (1) `isdead` is the arm's nomination UNION the C's own
non-negotiable kills, and that contamination is **8 %→100 % arm-dependent**, so it cannot rank arms ⇒
restrict to `mort_prob < 1`, checked by `NP`'s discretionary count coming out 14 of 12 393. (2) The
POOLED ratio-of-fractions is not 1.00 for a uniform operator (it is `<(1−ρ)>_mass/<(1−ρ)>_count` over
patch-years, and the hardest-thinned patches are the heaviest) ⇒ stratify by patch-year. Self-test then
lands at 0.994 = **0.14 σ**. Also learned: the tolerance had been pre-registered without deriving the
statistic's SE (≈0.09 at one cell vs a 0.15 tolerance), so a single-cell 1.19 read as a defect when it
was noise — the scorer now prints the SE and σ-departure, and the tolerance was **not** moved. All four
lessons went into the `rung2-dump-analysis` skill as traps 5d–5f.

Nothing flipped, no default moved, no baseline regenerated, no `src/**` change.

---

## 2026-08-13 — ADR 0188: the mortality budget is the NET count change, not the GROSS flux

Took ADR 0187 §B's promoted next action (the discretionary mortality RATE, starting from ρ's suspected
emitted-vs-roster population mismatch). Answered it entirely from state already on disk — the arm logs
(~170 kB/leg) plus a 1.9 GB scan of the 24 `REC` `predict` dumps, one SLURM job (1788038), no model run.
New scorer `scripts/diagnose_rung2_kill_budget.py`, five panels, ADR 0185 §5's coverage gate imported
rather than re-implemented.

**Read the harness before measuring anything, and the leading hypothesis died there.** ADR 0187 §B's
first suspect — a quota formed on the >5 m emitted population "under-killing the whole roster by exactly
that ratio" — is wrong, and wrong *derivably*: ρ is applied as a per-tree survival FRACTION against the
whole-roster density `n_now = sum(nind)` (harness :521-527), and a fraction is scale-free. The population
ratio is genuinely large (**2.08–2.92**, above line M's 1.9× at Hainich), so the suspicion was aimed at a
real disparity — it just cannot have that consequence. The derived a-priori gate settles it in one line:
for the uniform arm `E[n_kill] = (1−ρ)·n_tree` exactly, so H1 needs realized/implied ≈ 0.40–0.43 where the
measurement gives **1.004 ± 0.009 (0.51 σ)** and **1.006 ± 0.007 (0.84 σ)**. The free null (`NP` has ρ ≡ 1)
returned its derived 100.0 % and 0.000 %. The ρ clamp is not binding either (0.00–0.25 % at the low bound)
— ADR 0187 §B flagged that as an assumption and it cost one grep to discharge.

**What is actually wrong, in two layers.** The whole decision is gated `if ρ < 1.0`, so in **42–46 %** of
patch-years the arm's answer is an *empty* kill list, and in a further **27.9 %** of `S1`'s years
`_hazard_tilt` returns **θ = 0** — its own reported give-up, the certain kills having already reached the
target. Underneath that, the budget is the wrong quantity: ρ ≈ `n_next/n_now`, so `(1−ρ)·n_now` ≈ **K − R**,
the NET count change, while the flux that moves biomass is the GROSS **K** — and establishment is deferred
to the C (`ESTAB_C`, `n_recruit ≡ 0` by construction), so R arrives regardless.

**FIT's own numbers close the arithmetic.** Gross kills **5.65 / 5.96 %/yr**, recruits **4.62 / 6.46 %/yr**,
net **−0.54 / +0.25 %/yr**: near-stationary in count while turning over ~6 %/yr. Against the operator's
spendable budget of **0.78–1.02 %/yr** that is **6.4–7.6×** short, and FIT's non-negotiable deaths ALONE
overdraw the whole budget **4.1–5.3×** — so the discretionary channel is starved before it is reached,
which is exactly what θ = 0 reports and why the rate lands at 0.5–0.6 % against 2.0 %. A useful
corroboration fell out for free: the discretionary rate measured here by a count identity (1.88 / 2.05 %)
independently reproduces ADR 0187's 2.1 %, which was a stratified selectivity statistic over different
records.

⇒ **a mortality-only operator driven by a next-year COUNT target structurally cannot express gross
mortality flux**, because recruitment is 78–108 % of mortality: two stands with identical counts and wildly
different turnover look the same to it. Same shape as ADR 0132's trap — a quantity defined as a
year-over-year difference of state cannot carry a gross flux. Carefully NOT a re-opening of ADR 0186 §8.8
(no count-side instrument proposed; this explains why the count can be right while the mass flux is 4×
short) nor of ADR 0181 §§4–5 (that is the warming response, and it is about the target predicting the wrong
count — here the count is right and a count is the wrong kind of question to derive a budget from).

**Two basis errors again, both found inside the scorer before its numbers were published.** (1) The recruit
identity: the killed stems are **still in the `post` roster** under ADR 0123's deferred kills, so
`R = n_post − n_grow`, and the naive `n_post − (n_grow − K)` inflates R by exactly `K_all`. What caught it
was not a ratio — every arm-to-arm ratio looked sane — but the **implausibility of a LEVEL**: it implied
sustained +4.6 to +6.5 %/yr roster growth over an 81-year leg. Sanity-check a level against what the system
must do over its own horizon. (2) My first gate was **stricter than its own identity** — it also demanded
`dead@post == dead@mort` and duly reported a 13.2 % "violation" rate that was just **fire** (ADR 0121,
one-directional at 8100 of 8100, +14.1 % on top of the demographic kills, and not the demography
interface's to own). An over-strict gate manufactures doubt about a correct number. Both are now skill
traps 5g/5h, with 5i recording that `n_tree`/`n_emit` are both in the arm log — the third time that file
has retired a planned dump scan.

Next action pre-registered in ADR 0188 §7 **with its lever's current size measured** (ADR 0186's clause):
give the operator `(n_now − target) + R̂`, a 5.5–8.3× budget increase, against a criterion of discretionary
rate ≥ 1.5 %/yr AND mass removal ≥ 0.025 AND agb departure < +40 %. The one derivation that could kill it
is named first: R̂ for the current year is not available at the `grow` rendezvous, so it must be lagged or
predicted, and whether a lagged R̂ still moves the blessed statistic has to be derived before the arm is
written.

Nothing flipped, no default moved, no baseline regenerated, no `src/**` change.
