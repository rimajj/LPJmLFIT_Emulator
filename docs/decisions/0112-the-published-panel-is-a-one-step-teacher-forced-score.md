# ADR 0112 — every published global Component-S number is a ONE-STEP TEACHER-FORCED score, and the count response it reports is matched by a predictor that copies LPJmL-FIT's own previous-year answer

- **Status:** accepted (line S, 2026-08-10)
- **Rung:** `EXECUTION_PLAN.md` **rung 1** ("S alone, on the C's own fluxes"), line S — the *entry* finding.
  It changes what the four arms A/B/C/D mean, so it is recorded before any arm is run.
- **Supersedes / corrects:** no number in ADR 0111 is wrong; every one of them gains a **basis label** it did
  not carry. Specifically it retires the unqualified sentence *"the count response is faithful per cell
  (deattenuated 1.006)"* from ADR 0111 §4b and from `lines/S/STATE.md`, and it retires the reading of
  ADR 0111 §5b's four wrong-signed band responses as *the emulator's own* localised defect (§4c).
- **Related:** 0111 (the yardstick this is measured on; unchanged), 0023 (runtime consistency — the reason the
  training features are C-derived in the first place), 0020 (S is flux-driven), 0102/0054 (the count recursion
  and its level drift, measured single-cell/coupled — this is the global, offline statement of the same
  hazard), 0105 (offline ≠ coupled: the offline bias does not predict the coupled error), 0106 (the acceptance
  criterion), 0030 (the discipline: name the basis, then measure a null).
- **Artefacts:** `scripts/build_count_persistence_null.py` (job **1747638**),
  `scripts/diagnose_truth_yardstick.py` (now takes a comma-separated `COUNT_DIR`, so an arm and its null are
  scored in one process on one cell set; job **1747639**), summary
  `/p/tmp/jamirp/emulator_global/rung1_yardstick_with_null.csv` (273 rows),
  `scripts/attach_count_table_keys.py` (job **1747642**, the enabler for the recursion arm in §5).
- **Coverage:** the whole frozen production count table — **121 495 658 rows**, 58 588 cells, both scenarios —
  scored on ADR 0111's paired set of **51 767 cells**. Not a five-cell result.

---

## 1. What was verified

Three facts, each read from the code and the shipped manifests rather than inferred.

**(a) All 15 features the production count model is conditioned on are built from LPJmL-FIT's own output for
that very `(Cell, Patch, Year)`.** `scripts/build_slow_runtime_table.py` computes them in one `group_by` over
the `ind` parquet: `bm_inc_cell` = Σ `npp`, `water_stress` = 1 − mean `wscal_mean`, `growth_eff` = applied
`npp` / reconstructed patch LAI, `hmean`/`hmax`/`agb`/`lai`/`fpc`/`age_mean` from the same roster, `soilmoist`
from the C's own daily root-zone moisture, and — decisively — **`n_prev` = the C's own `n_living` for the same
patch in the previous year** (`shift(1).over(["Cell","Patch"])`). The remaining four are static or constant
(`eco_diag_gdd_5`, `tas_cold_month`, `soil_depth`, `co2`).

**(b) The published out-of-sample predictions are per-row, not a rollout.** `scripts/eval_slow_drf.jl:61` is
`preds[te] = DRF.predict(f, X[te, :])` — K-fold **by cell**, so no cell's own rows train its forest, but every
row is predicted from its own X. Held-out *cells*, not held-out *time*, and nothing the model predicts is ever
fed back into a later prediction.

**(c) The trait side is teacher-forced on fluxes, but carries no lagged trait.** The copula's conditioning
(`manifest_copula.txt`, `cond_cols`) is `bm_inc_cell growth_eff water_stress soilmoist` + `eco_diag_gdd_5
tas_cold_month soil_depth co2` — the first four C-derived, the last four static/constant. So the trait panel is
a *"given FIT's own carbon uptake, growth efficiency, water stress and soil moisture"* score. There is no
previous-year trait input, so the null in §3 does not apply to it.

⇒ **`EXECUTION_PLAN.md` rung 1's arm B — "fed the C's own per-tree fluxes each year" — is not work to be done.
It is what every published global Component-S number already is.** The arm that has never been measured
globally is arm **A**, "free-running", which the plan calls "today's behaviour".

## 2. Why this matters more for counts than for traits

The count model is handed the answer it is being scored on, lagged by one year, as one of its 15 inputs. Stem
counts are strongly persistent, so that input alone is most of the target. This is not a suspicion; §3 measures
it.

## 3. The measurement — the persistence null

Define the null model, which learns nothing:

    n̂(Cell, Patch, Year) := n_prev = LPJmL-FIT's own n_living(Cell, Patch, Year − 1)

It is written into a `COUNT_DIR`-shaped directory by `scripts/build_count_persistence_null.py` (the shared
provenance arrays are **symlinked**, so the null cannot drift from the table it is a null for) and scored by
the **same** yardstick code, on the **same** 51 767-cell paired set, in the **same** process as the production
model. Basis `capped400`, as ADR 0111.

| | production count model | **persistence null** |
|---|---|---|
| out-of-sample R² on `n_living` | **0.9824** | **0.9622** |
| unexplained variance | 0.0176 | 0.0378 |
| per-cell response slope vs seed 1 | 0.958 | **0.980** |
| per-cell response slope vs the 2-seed mean | 0.958 | 0.979 |
| **deattenuated (1 seed / 2 seed)** | **1.056 / 1.006** | **1.080 / 1.029** |
| aggregate area-weighted response ratio | **0.691** | 0.536 |
| band ratio: tropical | −0.51 | −0.43 |
| band ratio: subtropical | +3.41 | +2.83 |
| band ratio: temperate | +0.93 | +0.95 |
| band ratio: boreal | +1.07 | +0.95 |

**(a) 96.2 % of the count variance the emulator "explains" is explained by copying last year's truth.** The
learned model removes **53.3 %** of the null's residual variance — a real gain, and the honest way to state its
skill. "98.2 % of count variance" is not.

**(b) The per-cell response slope has essentially no power against persistence.** The null's deattenuated slope
is **1.029**; the production model's is **1.006**. Both are "faithful" by any reading of that number, so the
statement *"counts already respond faithfully per cell"* does not distinguish the emulator from a model with no
warming response of its own at all. It is a property of being handed FIT's lagged count.

**(c) The four wrong-signed band responses are in the null too.** Tropical −0.43 and subtropical +2.83 in the
null against −0.51 and +3.41 in the model. So ADR 0111 §5b's "four wrong-signed band responses no earlier
statistic could see" are **not**, on the count axis, a localised defect of the emulator to go and fix: a
predictor with no model in it reproduces them. They are a property of the response statistic on this basis.

**(d) The one statistic that does discriminate is the aggregate area-weighted response ratio** — 0.536 (null)
vs 0.691 (model) vs 1.0 (target). The learned model recovers about a third of the null's shortfall. ⚠ And the
null's 0.536 is **not** a clean zero-skill baseline: a one-year lag under a trend shifts the mean of an
N-year window by (first − last)/N, so the null's response is the truth's response minus a boundary term, which
is why it lands below 1.0 rather than at it. **The null is a control, not a floor** — do not quote 0.536 as
"the skill of no model".

## 4. Decision

**(a) Every Component-S fidelity number is quoted with its forcing basis from now on.** Three labels, and one
of them is mandatory on every number:

| label | what the model is handed | who does this today |
|---|---|---|
| **one-step, C-forced** | FIT's own roster state *and* fluxes for the same patch-year, incl. its previous-year count | every published global number, incl. all of ADR 0111 |
| **flux-forced, state-recursed** | FIT's own fluxes; the model's *own* previous-year state | nobody yet — §5 |
| **free-running** | climate only; state and fluxes both the model's own | the coupled 5-cell driver (line M) |

**(b) The rung-1 arm ladder is redefined**, because the plan's A/B collapse into one arm that is already done:

* **A0 — one-step, C-forced.** Delivered; it is ADR 0111's panel. Nothing to run.
* **A0-null — the persistence null.** Delivered here. **Every future count-response claim is reported next to
  it**; a claim the null also satisfies is not evidence about the emulator.
* **A1 — flux-forced, state-recursed.** The missing control, and the acceptance-critical one, because error
  accumulation is what the coupled model does. See §5.
* **C — A1 + `trait_mortality` ON.** Unchanged, and the pre-registered flip criterion (ADR 0109 / rung 1)
  still stands, but it is now decided against **A1**, not against the one-step arm — an operator that acts on
  who dies cannot be scored in an arm that is handed next year's count.
* **D — C + the bounded-Beta trait family.** Unchanged. It is a trait-marginal change, so it is scored on the
  trait axes, where the persistence null does not apply (§1c).

**(c) What to stop writing, effective immediately:**
- "the count response is faithful per cell (deattenuated 1.006)" ⇒ *"handed FIT's own previous-year count, the
  count response is faithful per cell (1.006) — but so is a predictor that copies it (1.029), so this says
  nothing yet about the emulator's own response."*
- "the emulator explains 98.2 % of count variance" ⇒ *"0.9824 against a persistence null's 0.9622 — it removes
  53 % of that null's residual error."*
- "the tropics respond the wrong way — a concrete, localised target" **on counts** ⇒ the null does that too;
  the concrete localised targets on counts are gone until A1 is measured.

**(d) ADR 0111 is not retracted.** Its noise floor, its λ table, its aggregate-vs-per-cell argument and the
trait-axis panel all stand; the count-response section gains the label above. The two extra reference seeds
the integrator is scheduling are still worth their compute — λ is a property of the truth, not of the arm.

## 5. What A1 is, and why it needs a key attachment first

A1 marches the count prediction forward per `(Cell, Patch)`: year *t*'s prediction is fed in as year *t+1*'s
`n_prev`, while the four flux features and the six other roster-state features stay at FIT's values. That makes
A1 a **strict lower bound** on free-running error — `agb`/`lai`/`fpc`/`hmean`/`hmax`/`age_mean` would also come
from the emulator's own roster in a real rollout, and that needs individuals and allometry (rung 2/4 territory,
line M's harness). Say "lower bound" every time.

The frozen production table predates ADR 0108, so it ships `cells.i64` + `scenario.i64` and **no year or
patch** — and the chain a recursion needs is *not* recoverable by inference. Both shortcuts fail, measured:
equal-length blocking is wrong for **24.8 %** of historic and **49.9 %** of ssp370 cells (a patch that loses
every tree for one year breaks its own run through the builder's `_prev_year + 1 == Year` filter), and
segmenting on `n_prev[i+1] == y[i]` silently **merges** adjacent patches whose runs join on the same small
integer count — concentrated in exactly the sparse cells whose noise floor is worst. So
`scripts/attach_count_table_keys.py` replays the builder's key pipeline from the `ind` parquet and **proves**
the alignment (recomputed `n_living` == `y.f64`, recomputed `n_prev` == `X[:, n_prev]`, recomputed `Cell` ==
`cells.i64`, row for row) before writing `years.i64`/`patches.i64`. Rows it cannot key carry −1 and must be
dropped, never guessed.

## 6. Falsifiable predictions (so this can be refuted rather than believed)

1. **A1's per-cell count response slope will fall materially below A0's 0.958** — if it does not, the AR
   recursion is not the channel, and the single-cell drift of ADR 0102/0054 does not generalise.
2. **A1's R² will fall well below the null's 0.9622**, because the null *is* the recursion's initial condition
   held constant and A1 must accumulate error away from it.
3. **The trait-axis panel will move much less than the count panel between A0 and A1**, because the trait
   conditioning has no lagged trait input (§1c) — only its four flux columns are C-forced, and A1 keeps those.

If (1) and (2) both fail, this ADR's framing is wrong and the one-step basis is a fair proxy for the offline
emulator after all.

## 7. Consequences

- `scripts/diagnose_truth_yardstick.py` takes a comma-separated `COUNT_DIR` so an arm and its null share one
  process, one cell set and one basis. Scoring two arms in two invocations is how bases drift apart.
- `EXECUTION_PLAN.md` rung 1's arm list (A/B/C/D) no longer matches the work. That file is integrator-owned ⇒
  **integration point raised**, replacement text is §4b here.
- The committed `test/testitems/references/S_truth_yardstick_summary.csv` is unchanged by this ADR; the
  null-bearing summary is scratch until A1 exists, at which point one committed table carries all arms.
