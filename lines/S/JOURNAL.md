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
