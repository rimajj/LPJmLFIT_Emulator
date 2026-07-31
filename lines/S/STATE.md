# LINE S — Component-S science (branch `line/S`, worktree `wt-S`)

> Durable state for THIS LINE only. Shared/cross-cutting facts: `MEMORY.md`. Runbook: `CLAUDE.md` (+ §9 for
> the parallel-line protocol). Narrative: `lines/S/JOURNAL.md` (append-only). Decisions: ADR block **0030–0049**.
> **The `## NEXT` block below is what the SessionStart hook prints — the ending session MUST refresh it.**

## NEXT — start here

**S2's gate is MET — and the win is smaller than it looks, for a reason worth reading before you act on it.**
`env-qrf-b6x2M` (6 trees x 2M subsample, `max_depth` 22, `min_leaf` 20, `QRF=1`, **`ncond` 14**) clears all
four ADR-0030 §4 criteria for the first time. **ADR 0038** is the record; it SUPERSEDES ADR 0037's central
thesis. **Merged to `main`? NOT YET — 9 commits sit on `line/S` awaiting the push/CI/merge ritual.**

### The result, in one table (all verified against the raw logs, twice)

| | Wooddens `emu_r` | %GAP | `sd_ratio` | pooled KS SLA/W/D95/minw |
|---|---|---|---|---|
| baseline `t8` (40x50k, d14, ncond 8) | 0.814 | — | 0.6775 ✗ | .0051/.0052/.0069/.0115 |
| best at **ncond 8** (`qrf-b6x8M`) | **0.867** | 35.3 % ✗ | 0.7633 | not KS-scored |
| **`env-qrf-b6x2M` (ncond 14) — SHIPPED** | **0.901** | **58.0 % ✓** | **0.8541 ✓** | **.0032/.0024/.0019/.0013 ✓** |

Threshold is `emu_r` 0.889. Criterion 1 passes under all five defensible %GAP conventions (min 56.7 %).
`b6x8M` rejected: +0.002 for 4x the bytes and worse KS on all four axes.

### The three levers, isolated (matched pairs — do NOT collapse these)

| lever | Δ `emu_r` | Δ `sd_ratio` | crosses the gate? |
|---|---|---|---|
| capacity, ncond 8, QRF=1 (50k→2M→8M) | +0.037 then **+0.003** | +0.0884 | **no — saturates at 0.867** |
| QRF alone (at 50k / at 2M) | +0.013 / +0.002 | **−0.003 / −0.013** | no |
| **conditioning, at fixed 6x2M+QRF** | **+0.037** | **+0.0966** | **yes** |

Capacity *provably* cannot reach the gate at ncond 8: fitted asymptote **0.870**; the last marginal rate
implies ~15 more doublings = ~1000x the whole 197.7M-row table. **Subsample is exhausted past ~2M at BOTH
widths** (+0.003 / +0.002); the *level* it plateaus at is set by the conditioning. QRF's payoff shrinks
with capacity because the max-leaf weight share is 6.7x `1/T` at 60 trees but only **2.9x at 6 trees** —
what QRF fixes is largely absent there, so `qrf-b6x2M` was chosen for consistency with the scored rung, not
for skill.

### ⚠ THE CAVEAT THAT GATES PRODUCTION — read before promoting anything

**The six env columns are a per-cell spatial ADDRESS, not a climate response.** Verified directly:
median within-cell sd is **EXACTLY 0, for 100 % of cells**, on all six (`prec_mean`,
`eco_diag_p_pet_ratio`, `eco_diag_pet_mean`, `eco_diag_vpd_mean`, `pr_cv_monthly`, `humid_mean`) —
`cell_year_feats` broadcasts a per-cell climatology to every year. So they cannot encode a warming
response; in the pooled table a cell's historic and ssp370 rows are **bit-identical** on them. A 1-NN
lookup on those columns reaches Wooddens r = **0.800** with the nearest training neighbour **1.00°** away
(q25 = 0.50° = the adjacent cell). **`mod(hash(cell), k)` folds cannot detect this** — by-cell CV leaves
the neighbours in the training fold, so it scores spatial interpolation, not transfer.

⇒ `recruit_copula_global_historic_t9.rcop` is the **historic-STATIC** artifact and the S2 evidence. It is
**NOT** line M's production copula (M pins the **transient** `pooled_w20` basis, ADR 0027). Do not re-pin M
onto it.

### DO THIS FIRST

1. **Push + merge the 9 commits.** `git push --force-with-lease origin line/S`, wait for branch CI
   (`test (lts)`, `test (1)`, `format`, `python`; `test (pre)` is allowed-to-fail), then the `flock` merge of
   `origin/line/S`, then check **main's own** latest run. Local evidence is already green: full CI-faithful
   suite **107 394 pass / 0 fail / 4 broken** (job 1647687), Runic 1.7.0 clean 111/111.
2. **Collect job `1647661` `S-cap-pooled-env`** (started 11:04, 8 h wall) — the SAME config on the
   **pooled_w20** table M actually pins. It scores criterion 3 (KS, auto-read against the *pooled* baseline)
   and criterion 2 via `score_slow_copula_dispersion.py`, A/B against pooled t8. **Criteria 1 and 4 are NOT
   computable for pooled — there is no pooled seed2** (see below). Pooled t8 baseline to compare against:
   Wooddens `emu_r` **0.8261**, `sd_ratio` **0.6119** (57 719 cells), pooled KS .0039/.0065/.0020/.0040.
3. **THE decisive experiment, and the gate on production: spatially BLOCKED CV.** Re-score
   `env-qrf-b6x2M` with contiguous lat/lon block folds instead of `mod(hash(cell), k)`
   (`eval_slow_copula.jl:143`), plus a lat/lon-only conditioning control. Survives blocking ⇒ a real
   environmental response, promote it. Decays toward the 1-NN level (r≈0.80) ⇒ it is an address, and S2's
   framing changes a third time. **Do not promote to M before this runs.**

### Then, in priority order

4. **A per-cell env sidecar** — there is NO runtime plumbing supplying the six values per cell; a caller
   hand-builds them from `cell_year_feats.parquet`, which is unreachable from CI and basis-sensitive. S emits
   `cell_env.parquet` (same no-year-filter basis); M folds it into `M_cells.csv`. **Until this exists the
   14-column artifact is not coupled-runnable outside a bespoke script.**
5. **Depth is NOT exhausted at the production config** — measured on t9 (job 1648259): 33 449–46 036
   leaves/tree but **52.3–67.0 % of stored values still depth-capped**, and only 84–86 % of large leaves at
   `max_depth` (vs 99.9–100 % at 50k/d14). Depth is free in bytes. **One `6 x 2M, d32` rung** settles whether
   the 0.870 asymptote moves.
6. **Re-run the shipped rung with `TRAIT_ONLY=0`** — `agb`/`Height` were trimmed out of 11 of 12 rungs
   including the shipped one, and they carry the tightest baseline margins (agb pooled KS 0.0116 vs the 0.02
   bound; `r_center` headroom 0.011/0.013). "S2 met" must not be read as "biomass and size unchanged".
7. **The composed coupled path is still unexercised**: emulator + 14-col copula + `qrf=true` + establishment
   + carbon closure over a multi-year run. Construction is now gated; the run is not.
8. **Cheap and still open (carried, ADR 0036 §6):** emit **`Year`** in the `MODE=copula` table so the
   stand-biomass composite is computable on matched rows — it blocks figures 12/13 for the POOLED pair. It is
   a table SCHEMA change, so it costs a rebuild, and ADR 0036 §5b's streaming key-set nondeterminism means a
   rebuild lands on a different row universe ⇒ do it when a new generation is being built anyway, never as a
   standalone rebuild of a validated table. (Related gotcha, don't re-derive: `STEM_CAP` is a patch-year
   **CLUSTER** subsample, not per-stem — ADR 0036 §178, and it is why ssp370's basis spread is ~10x looser.)

### OPEN INTEGRATION POINT with line M (raise it before any re-pin)

`scripts/extract_cell_slow_init.py:142-146` checks `cond_cols[-4:] == BOUNDARY_COLS`. A 14-column artifact
fails that **by construction** — its last four are the env tail — so M's re-pin step `sys.exit`s. The correct
check is **positional**, `cond_cols[4:8]`. **That file is M-owned; S requests, M lands.**

### What shipped in code this session (all opt-in, default byte-identical)

- **`.rcop` format v2 carries `qrf`.** It selects a different conditional from the same forests and used to
  live ONLY in the sidecar, while M's contract pins a `.rcop` *path* ⇒ a consumer that missed the sidecar
  silently sampled the estimator that was never scored. Flipping it changes all three of t9's golden draws.
  v1 still loads and means `qrf=false`; `qrf` is the 6th tuple element so all five 5-way `load_copula` call
  sites are untouched. **This is a VERSION BUMP of the frozen S→M contract — nothing M pinned needs
  regenerating.**
- **`FluxDrivenSlowEmulator` rejects a conditioning-width mismatch at CONSTRUCTION.** `_check_nfeat` fires
  only inside `sample_copula!`, reached only when a patch recruits — so a thinning cell or all-grass patch
  never draws and a mis-wired run completes "successfully", conserving carbon, silently.
- **The ADR-0030 gate refuses a floor from two seeds that are the same seed** — see below.
- `rcop_acceptance_probe.jl` (accept an artifact in a FRESH process; t9 = load **6.77 s / 71.6 MiB/s
  measured**, all width guards fire) · `score_slow_copula_dispersion.py` (criterion 2 without a seed2).

### Traps found this session (do not re-derive)

- **THE ssp370 `random_seed2` GROUND TRUTH IS A BIT-IDENTICAL COPY OF SEED1.** Both `ind_2020_2100.csv` are
  193 097 583 638 B with equal md5 at MB 0/30000/120000, because the seed2 config sets `"random_seed": 2` but
  its `restart_filename` points at the **historic seed1** `restart_2019.lpj` — under `-DFROM_RESTART` the
  RAND48 state is restored, so the seed is inert. (Historic IS independent: each reads its own *relative*
  `restart/restart_1999.lpj`.) A floor built from it reports `floor_r ≡ 1` ⇒ fabricated headroom, with **no
  error**; the `seed1-basis ≥ 0.99` check is structurally blind to it. Now guarded + self-tested both ways
  (job 1648005). **Only `historic` has a usable seed2 ⇒ criteria 1 and 4 are not computable for
  pooled/ssp370.**
- **`median_percell_r` in `metrics_traits.txt` IS `emu_r`** (between-cell r of per-cell medians, despite the
  name) — reproduced to 4 dp. So every scenario's baseline is already published; you do not need a seed2 for
  it. Basis offset to the gate's own number ~0.002.
- **Criterion 3 = pooled KS, the NUMERIC ≤0.02 bound** (pinned in ADR 0038). Decisive: `pooled_t8`'s own
  Wooddens `pooled_nqrmse` is **0.0208**, so applying the bound to `nqrmse` fails the pooled *baseline*.
  But KS hides a coherent **−0.4 % SLA quantile shift** (SLA KS improves 0.0051→0.0032 while `nqrmse` gets
  1.8x worse) — score KS, **report both**.
- **`co2` is a DEAD conditioning column** — a literal constant 369.0 (`CO2_CONST`, ADR 0004) ⇒ effective
  width is `ncond − 1`, and the pooled table has no static scenario discriminator at all.
- **The env-augment dropped every manifest-named sidecar but `cells.i64`** — pooled tables declare
  `scenario_tag scenario.i64`; it trained fine and would have died much later in the scenario-holdout eval.
  Fixed by resolving sidecars from the manifest.
- **The `.rcop` is byte-reproducible** from `(table, config, seeds)` — so regenerating it for a metadata fix
  is safe (md5 verified, job 1647662).
- **Julia soft scope**: `ndiff += 1` inside a top-level `for` binds a NEW local ⇒ `UndefVarError` at the
  outer read. Use a single assignment / comprehension.
- **The `format` CI gate is REPO-WIDE** (the runic-action takes no `paths`), so a new `scripts/*.jl` is
  checked exactly like `src/`. The per-file loop that NAMES offenders is in the `julia-test` skill.

**Not S's to chase:** `water_stress` (6.6x band) is line M's F core, ADR 0029. `fpc`'s residual is dynamics
(ADR 0035 §3.3).

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
