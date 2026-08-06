# ADR 0108 — the recruit-trait moisture conditioning becomes TRANSIENT (per cell-year), and the table carries its own year

- **Status:** accepted (line S, 2026-08-06)
- **Supersedes:** nothing. **Refines** ADR 0037 (which introduced the six-column environmental tail as a
  per-cell time mean) the way ADR 0026 refined ADR 0020's time-constant boundary.
- **Context:** ADR 0106 (the owner's acceptance criterion — all 54 020 tree-bearing cells, both scenarios,
  *and the response between them*, "especially under climate change"), ADR 0107 (the emulator must not see
  CO2 at all; the climate signal is the channel), ADR 0105 §5 (the count-side residual is F's canopy, not S's
  training), ADR 0033 (do not credit a basis or population fix to conditioning), ADR 0023 (train/inference
  consistency is load-bearing and fails silently), ADR 0036 §5b (streaming `group_by` is non-deterministic in
  its emitted key set).

## 1. The defect — stated correctly, after measuring the baseline

`live_flux_cond_env(env)` (ADR 0037) closes over **one constant vector per cell**, and
`build_slow_runtime_table.py`'s `COPULA_ENV_COLS` tail was a per-`Cell` time MEAN over
`tables/cell_year_feats.parquet` — a 2000-2019 historic climatology read whole for **both** scenarios. So a
stem establishing in **2100 under ssp370** is conditioned on the **2000-2019** moisture climatology of its own
cell, and **that** channel is frozen: none of the slow, 20-year-window moisture *climate* FIT's establishment
gates key on can reach the sampled marginal.

⚠ **AND THAT IS AS FAR AS THE ARGUMENT GOES. An earlier draft of this ADR said the establishment marginal
therefore "cannot shift with a drying climate *by construction*" and the trait response is "structurally
zero". That is FALSE, and it was a structural argument made without measuring the baseline** — precisely the
error ADR 0107 turned into a method rule (an absent behaviour is not automatically a missing one) and the
`residual-diagnosis` discipline exists to prevent. The frozen tail is **6 of 14** conditioning columns. The
other eight are **not** moisture-blind and **not** static: `water_stress` and `soilmoist` are per-`(Cell,Year)`
flux drivers, `bm_inc_cell` and `growth_eff` carry the year's carbon budget, and under `BOUNDARY_WINDOW=20`
`eco_diag_gdd_5` and `tas_cold_month` are transient too.

**Measured** (`scripts/diagnose_moisture_arm_response.py`, job **1718922**, the SHIPPED `_t8` pooled
generation, 52 074 cells with ≥30 stems in both scenarios, K-fold-by-cell OOS). Per-cell response
`D = median(ssp370) − median(historic)`, `D_pred` regressed on `D_truth` through the origin:

| axis | response slope | corr | sign agreement | per-cell median within 10 % (hist / ssp) |
|---|---|---|---|---|
| SLA | **+0.85** | +0.45 | 71.9 % | 70.7 % / 67.5 % |
| Wooddens | **+0.35** | +0.38 | 61.5 % | 71.4 % / 72.2 % |
| D95max | **+0.16** | +0.20 | 57.5 % | **28.0 % / 30.0 %** |
| minwscal | **+0.69** | +0.58 | 62.7 % | 62.1 % / 63.8 % |

So the **offline recruit-trait response channel is already partially open** — it is not closed, and this ADR
must not be read as opening it from zero. What is true is narrower and still worth fixing: one of the two
moisture channels is frozen; the response it could carry is missing; the response that exists is **partial and
axis-dependent**, worst exactly where a moisture climatology should matter most (`D95max` = the rooting-depth
trait, slope 0.16 and only 28 % of cells within 10 % on the level).

**This table is the arm's reference basis.** Success is *beating* these slopes, not moving off zero.

**What this is NOT.** Not a CO2 item (ADR 0107: the emulator must not see CO2, and the SSP scenarios already
carry the CO2-driven *climate* signal). Not a claim that the frozen tail explains any measured present-day
residual — ADR 0033's warning stands. Not a coupled-run statement: every number above is **offline**, with the
conditioning fed the C's own features (ADR 0105 §5 shows the coupled residual is dominated by F's canopy).

## 2. The decision

Three changes, each opt-in and default-preserving:

1. **`scripts/build_slow_runtime_table.py` gains `ENV_WINDOW`** (`_env_source`). Unset ⇒ the pre-0108
   per-cell mean, byte-identical. `ENV_WINDOW=W` ⇒ the per-`(Cell, Year)` trailing-W-year moisture
   descriptors from `tables/cell_year_env_<scenario>_wW.parquet`, joined on `["Cell","Year"]` — exactly the
   ADR-0026 treatment the boundary pair already gets. Column names and order are unchanged; only the values
   become year- and scenario-specific.
2. **`src/components/slow.jl` gains `live_flux_cond_env_series(env_series)`** — the runtime half. It indexes
   `s.year + 1`, clamped, which is the *same* indexing `boundary_series` uses and is evaluated in the *same*
   year (`reconcile_demography!` advances the boundary and calls `rc.cond(s, feats)` in one invocation, before
   `s.year += 1`). A constant series reproduces `live_flux_cond_env` exactly.
3. **Every table now emits `years.i64`** — a per-row `Year` aligned to `Xc`/`X` exactly like `cells.i64`,
   declared in the manifest as `years_tag`, and pooled all-or-nothing by `pool_slow_tables.py`.

## 3. Why `years.i64` is a decision and not a convenience

Attaching a per-`(Cell, Year)` quantity to an **already-built** table is the cheap, perfectly-isolated way to
answer "what is the transient tail worth?" (§4). It requires each row's year, and the obvious shortcut —
inverting the year from `Xc`'s own per-cell-year columns — **does not work**:

| key | rows | ambiguous |
|---|---|---|
| `(Cell, gdd5, tas_cold_month)`, historic w20 | 1 348 400 | **174** |
| `(Cell, gdd5, tas_cold_month)`, ssp370 w20 | 5 461 020 | **202** |
| `(Cell, soilmoist, gdd5, tas_cold_month)`, historic | 1 348 400 | **134** |
| `(Cell, soilmoist, gdd5, tas_cold_month)`, ssp370 | 5 461 020 | **141** |

Adding `soilmoist` to the key *reduces* the collisions but does not remove them: a residue of cell-years is
genuinely indistinguishable in every per-cell-year column the table carries. That residue is ~1e-4 of the
rows — small enough that an inversion would look correct in every aggregate and be wrong for a few hundred
cell-years, in the cells where the climate is flattest. So the Year is **stored**, not inferred. The sidecar
also makes any future per-year analysis of a frozen table possible at all.

## 4. Why the arm is built as ONE base table plus TWO appended tails

`scripts/run_moisture_conditioning_arm.sh` builds the 8-column base **once**, then appends the static tail and
the transient tail to that same frozen base (`build_slow_copula_env_augment.py`, which verifies the base
columns survive **bitwise** and symlinks `Y_*`/`cells.i64`/`years.i64` so they cannot drift).

Two independent 14-column builds would **not** answer the question: ADR 0036 §5b established that the copula
build's `collect(engine="streaming")` is non-deterministic in its emitted **key set** at this scale (two
ssp370 builds differed by 4 913 rows, with 12 cells duplicated), so two builds land on two row universes and
any measured difference is confounded with that. The two arms here differ in the six tail columns and in
**nothing else**, and the K-fold-by-cell fold map is a hash of `Cell` over identical `cells.i64` bytes, so the
two out-of-sample scores are **paired per cell**.

This is the rule this line earned the hard way in ADR 0105 §D1-D2 and ADR 0033: isolate the change you are
attributing, and never credit a conditioning change with a basis or population effect.

## 5. What is measured, and what is NOT claimed yet

**Verified now** (`scripts/diagnose_env_window_gate.py`, job **1718598**, the 5 biome cells, historic w20):

- `ENV_WINDOW` unset reproduces the pre-0108 builder's `Xc.f64` **byte-for-byte**, with `n`, `ncond`,
  `cond_cols`, `axes` and the fallback row `x` unchanged (guardrail 4). Checked against
  `git show <parent>:scripts/build_slow_runtime_table.py`, not against a re-run of the new code.
- Under `ENV_WINDOW=20` the head + boundary columns 0-7 are **identical** to the static run's and only the
  six tail columns move, over an identical row universe (same `cells.i64`, same `years.i64`).
- 20 000 of 20 000 probed rows carry their **own** `(Cell, Year)` moisture values, re-derived from the parquet
  independently of the builder's join.
- The tail takes **20 distinct values per cell over 20 years** where the static tail takes **1**.
- `years.i64` is emitted, aligned, and declared in both manifests.

**The signal the tables carry** (built 2026-08-06, jobs 1718339/1718347, all 67 420 cells, both scenarios;
formulas ported verbatim from `climclusterpy/features/diagnostics.py` and gated at 1e-7 against the frozen
per-cell basis): global mean VPD **+20.4 %**, PET **+4.9 %**, humidity **+19.9 %** from 2019 to 2100.

**The baseline the arm must beat** is §1's table (job 1718922) — response slopes +0.85 / +0.35 / +0.16 / +0.69
and per-cell level agreement 70.7 / 71.4 / **28.0** / 62.1 % of cells within 10 %, measured on the shipped `_t8`
generation with the frozen tail. `scripts/diagnose_moisture_arm_response.py` computes exactly this for both
arms at once and **checks the pairing** (identical `cells.i64`, `scenario.i64` and `Y_*` bytes) instead of
assuming it.

**NOT claimed.** Whether the transient tail improves trait skill or the response is what the arm measures — it
is not asserted here, and a null result is a legitimate outcome to be reported as one. Nor is any *coupled*
claim made: these are offline, conditioning fed the C's own features, and ADR 0105 §5 shows the coupled
residual is dominated by F's canopy. What this ADR does on its own terms is remove a frozen column from a
conditioning row that is otherwise transient, and make the two bases distinguishable and comparable.

## 6. The trap this creates, and the only thing that guards it

A static-tail artifact and a transient-tail artifact have the **same `ncond`** and the **same `cond_cols`**.
Therefore:

- `FluxDrivenSlowEmulator`'s ADR-0038 conditioning-width probe **passes for either policy paired with either
  artifact**;
- `DRF.load_copula`'s `ncond`/`nfeat` consistency check passes;
- a coupled run completes, conserves carbon, and returns in-range traits.

Pairing them wrong reads the marginal forests at systematically wrong coordinates — the ADR-0023 silent shift,
with no width anywhere to catch it. **The manifest's new `env_basis` line is the only discriminator**:
`static_cell_mean` requires `live_flux_cond_env(env)`, `transient_w<W>` requires
`live_flux_cond_env_series(series)`. It is propagated by the augmenter and by the pooler, and
`pool_slow_tables.py` now **refuses** to pool two scenarios whose `env_basis` differs — that combination would
put the historic half on a frozen basis and the ssp370 half on a year-varying one and fabricate part of the
scenario contrast it is supposed to measure.

## 7. Consequences

- **Adopting the resulting artifact is an ADR-0023 BOTH-SIDES change with line M.** The `.rcop` is versioned
  (`recruit_copula_global_pooled_w20_t9envT.rcop`), never mutated in place, and M must pass a per-cell,
  per-year `env_series` where it currently passes a constant `env` — a per-cell series is a
  `cell_year_env_<scenario>_w20.parquet` slice, so the provisioning is a read, not a new derivation.
  Until M re-pins, nothing M runs changes.
- The count DRF is **untouched**: its features are the 11 head columns + the 4-column boundary tail, and this
  change adds nothing to them. Whether the count model should also see moisture (it currently sees temperature
  transiently and moisture not at all) is a **separate** question, and by this line's own rule it must be
  **priced offline** against the existing tables before a retrain is bought.
- `docs/decisions/README.md` gets the row; the procedure lives in the `slow-drf-pipeline` skill.

## 8. Alternatives rejected

- **Invert the Year from `Xc`.** Rejected on measurement: ~140 ambiguous cell-years per scenario remain even
  with `soilmoist` in the key (§3), and the failure would be invisible in every aggregate.
- **Rebuild both 14-column tables independently.** Rejected: two row universes, so the comparison would not
  isolate the tail (§4).
- **Append the six columns to `BOUNDARY_COLS` instead.** That would widen the count DRF's
  `flux_feature_vector` — a frozen S→M contract — for a change whose value is unmeasured. Rejected as
  premature; the copula tail is where the moisture columns already live.
- **Make the transient tail the default.** Rejected for now (guardrail 4). But note guardrail 4's corollary:
  an opt-in whose default is known worse is a defect on a timer. **Pre-registered flip criterion:** flip
  `ENV_WINDOW=20` to the default for every production copula build, and `live_flux_cond_env_series` to the
  policy the coupled driver uses, once (a) the paired K-fold-by-cell OOS trait scores of `_t9envT` are not
  worse than `_t9env` on any of the four production axes, and (b) the coupled five-cell screen shows a
  non-zero historic→ssp370 trait-median response where the C model has one. If (a) holds and (b) does not,
  say so and keep it opt-in — the structural closure still stands, and the remaining gap is then somewhere
  else (ADR 0105 §5 points at F's canopy).
