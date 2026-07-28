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
