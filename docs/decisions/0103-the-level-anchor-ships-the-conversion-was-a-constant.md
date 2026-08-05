# ADR 0103 — the level anchor ships: the count↔density conversion was never missing, it is a documented constant (`patcharea = 225 m²`)

* **Status:** Accepted
* **Date:** 2026-08-05
* **Line:** S (Component-S science) · ADR block 0100–0119 (tier 2)
* **Supersedes, in part:** **ADR 0102 §4** ("the fix is specified and deliberately not landed") and the
  clause in its `Decides` (4) that the fix "requires the count↔density conversion at the S↔F seam — an
  `interface.jl` addition, which is line M's". **That is factually wrong**, and it is the load-bearing claim
  of that section: it routed a one-file change through a cross-line contract negotiation and deferred it.
  **ADR 0102 §1, §2, §3 and §5 stand unchanged** — the three-way decomposition, the empty (B), the
  retention measurement and the `wscal_leafon` pre-authorisation are all unaffected.
* **Decides:** **(1)** the count↔density conversion is a **documented constant**, not missing data, so the
  level anchor is implementable entirely inside `src/components/slow.jl`; **(2)** it ships **now**, as an
  opt-in `anchor` kwarg, default `0` ⇒ every committed baseline byte-identical; **(3)** the mechanism is a
  **geometric** blend `ρ_eff = (target/n_prev)^(1−a)·(D_want/D)^a`, chosen so `a` is a relaxation-rate dial
  rather than an on/off switch; **(4)** the measured recommendation for line M is **`anchor = 0.1`** — the
  gentlest setting that fully works, which is the value the owner's standing pre-authorisation was waiting
  on; **(5)** `patch_area` is a property of the **artifact's training run** and travels with the artifact,
  not with the cell.
* **Related:** ADR 0102 (the defect this fixes; §4 corrected here), ADR 0054 (line M's original finding),
  ADR 0049 (the opt-in/default-off pattern this reuses verbatim), ADR 0023 (train/inference consistency —
  `patch_area` is a training-run property for exactly that reason), ADR 0029 (the ownership map, which this
  ADR shows was invoked unnecessarily), CLAUDE.md §3 (the `cpp -P` rule used to verify the constant) and §6
  guardrails 4 and 6
* **Evidence:** `scripts/diagnose_count_recursion_anchor.jl` section (d), job **1707102**. Hainich cell
  42490 only, constant repeated-2010 forcing, committed demo artifact pair, `n_init` 11.0 / `age0` 43.5556,
  seed 1, 150 yr, `DENS_SWEEP = 0.5,0.75,1.0,1.5,2.0`.

## Context — the error, and how it was caught

ADR 0102 established that the coupled stand has no level anchor (retention 1.036 over 300 years) and then
concluded the fix was blocked: the roster is advanced by a ratio precisely so it never needs the patch area,
and supplying that area would be an addition to `src/interface.jl`, which line M owns. On that basis the fix
was scoped, raised as an integration point, and **deferred**.

**The project owner rejected the premise immediately: the patch is 15×15 m, and that is in the LPJmL-FIT
source.** It is:

| where | what |
|---|---|
| `par/lpjparam_fit.js:17` | `"patcharea" : 225.0, //100.0,  /* patch area (m2), 100.0 in std FIT */` |
| `src/tree/new_tree.c:209` | `pft->nind = 1/param.patcharea;` — every individual's density |
| `include/param.h:43` | `Real patcharea;  /**< patch area (m2) */` |

Verified rather than eyeballed, per CLAUDE.md §3's rule: `cpp -P -I. param_lpjmlfit.js` over the **live**
config yields exactly **one** `"patcharea"` occurrence, value **225.0** — no duplicate key silently
overriding it (the trap that makes larch's `aphen_min` 10 instead of 60, ADR 0047). And confirmed against
the committed fixture end-to-end: in `hainich_individuals_2010.csv` the modal patch's 17 tree stems have
`sum(nind) × 225 = 17.000` exactly, with every individual at `nind = 1/225 = 0.00444444`.

So the training target (stems **per patch**) maps to the roster (stems **per m²**) by an exact division by
225. **Nothing was missing.**

**How the error survived a whole ADR.** CLAUDE.md itself carries the sentence *"with `nind = 1/patcharea`
(`new_tree.c:209`) the patcharea cancels"* — written about reconstructing per-patch LAI (ADR 0035), where it
genuinely does cancel. That sentence was read as a general property of the quantity rather than a property
of one particular derivation, and the follow-up question — *cancels against **what**?* — was never asked.
The transferable lesson is narrow and worth stating: **"X cancels" is a statement about an expression, not
about X.** In a different expression X is just a number you have to know, and here it was written down three
files away.

## Decision

### 1. The mechanism

In `reconcile_demography!`, the demographic ratio becomes a **geometric blend** of the AR ratio and the
ratio that would place the stand on the DRF's absolute target:

```
D_want = target / patch_area                      # stems per m², the DRF's absolute prediction
ρ_eff  = (target/n_prev)^(1−a) · (D_want/D)^a      # a = `anchor` ∈ [0,1]
```
then clamped by `max_mort`/`max_estab` exactly as before.

* `a = 0` — the branch is **not evaluated**; the code path, and every committed baseline, ReferenceTest and
  AD gate, is byte-identical to pre-0103. This is the ADR-0049 pattern reused unchanged.
* `a = 1` — the stand is placed on `D_want` outright (subject to the clamp).
* `0 < a < 1` — exponential relaxation toward the target with time constant ≈ `1/a` years.

**Geometric, not arithmetic, and that is a decision.** The update stays multiplicative and strictly
positive, so the carbon routing below it is untouched, the clamp still bounds the year's demographic change,
and `a` is a *rate* rather than a mixing weight. An arithmetic blend would need a positivity clamp and would
make `a` interact with the magnitude of `D`.

### 2. What it measures (Hainich, 150 yr, same 4× perturbation sweep as ADR 0102 §3)

| `anchor` | retention | terminal spread | `D_end` | `target/patch_area` | ratio |
|---|---|---|---|---|---|
| **0.00** | **1.0364** | 4.207× | 0.042281 | 0.030013 | **1.409** |
| 0.10 | **0.0513** | 1.074× | 0.028036 | 0.028036 | **1.000** |
| 0.25 | 0.0491 | 1.071× | 0.028036 | 0.028036 | 1.000 |
| 0.50 | 0.0513 | 1.074× | 0.028036 | 0.028036 | 1.000 |
| 1.00 | 0.0762 | 1.111× | 0.027952 | 0.027952 | 1.000 |

Three things, all of which had to hold:

* **`anchor = 0` reproduces ADR 0102 §3 exactly** (retention 1.0364, spread 4.207×) — the default is
  verified untouched by measurement, not by inspection.
* **The initialisation is forgotten.** Retention **1.036 → 0.051**, terminal spread **4.21× → 1.07×**. A
  20-fold reduction, at the *weakest* non-zero setting.
* **A previously invisible LEVEL ERROR is closed.** Unanchored, the stand settles **1.409×** denser than its
  own count model's absolute prediction — a **41 % over-density that no diagnostic in this project could
  see**, because every existing check is on ratios, distributions or per-cell correlations, none of which
  reads the absolute level. Anchored, the ratio is **1.000**.

### 3. `anchor = 0.1` is the recommendation

Everything in 0.1–0.5 is equivalent within noise, and **`a = 1` is slightly *worse*** (retention 0.076 vs
0.049–0.051). That is the expected shape and it is why the dial exists: a hard anchor overwrites the stand's
own dynamics every year, so a perturbation is re-imposed through the clamp and the recruit branch rather
than relaxed away. **Take the gentlest setting that works** — it retains the most of what F computes, which
is the whole reason for not simply assigning `D = D_want`.

### 4. `patch_area` belongs to the ARTIFACT, not the cell

225 m² is `param.patcharea` of the runs that produced the training tables. It is a **global constant in this
configuration** (`fscanparam.c:49` reads it once), so it needs no `cell_meta.parquet` column and no per-cell
plumbing — but it is **not** a law of nature: stock LPJmL-FIT uses **100.0**, and `par/lpjparam.js` in this
very tree still does. An artifact trained on a run with a different `patcharea` needs that value passed, or
the anchor pulls the stand to a level that is wrong by the ratio of the two areas. It is a kwarg with a
documented default for that reason, and it is inert when `anchor == 0`.

## Consequences

* **The level anchor is no longer blocked, and never was.** ADR 0102's integration point is withdrawn as an
  integration point and replaced by an ordinary opt-in feature. What remains for line M is only to *enable*
  it and regenerate their coupled baselines — which the owner **pre-authorised on 2026-08-05**
  (`lines/M/STATE.md`, `MEMORY.md`), with `anchor = 0.1` as the measured value that authorisation was
  waiting for.
* **An ownership rule was invoked where none applied, and that has a cost.** ADR 0029 exists to stop lines
  editing each other's files; it does not make a constant from a third repository into another line's
  property. Deferring a one-file change to a cross-line negotiation is a *real* cost, and the check against
  it is cheap: **before routing work to another line, confirm the thing you need is actually theirs.**
* **41 % is the size of what was not being measured.** No existing gate — not the ADR-0030 per-cell trait
  gate, not the count R², not the trained-band check — reads the stand's absolute level. A validation suite
  built entirely on ratios and correlations is blind to a level error by construction.
* **This does not close ADR 0102's mechanism (A).** The exposure bias is untouched: the anchor makes the
  stand track the DRF's prediction, so a biased prediction is now followed *faithfully* rather than
  compounded. That is strictly better and still not right, and it is a training-side fix (retrain without
  the fed-back count). The owner has confirmed compute is available for it.
* **One cell, constant forcing, one artifact pair** (guardrail 6). The next measurement is line M's five
  coupled biome cells against the C truth, where ADR 0054's drift was found — that is where `anchor = 0.1`
  either removes the 59–72 % residual or does not.
* **Nothing shipped changes by default.** `anchor = 0`, no committed baseline, artifact or fixture moved,
  runtime `[deps]` still empty.

## Alternatives rejected

* **Assign `D = D_want` outright (`a = 1` as the default).** Measured *worse* on retention, and it discards
  what the fast core computes about the stand in favour of a statistical prediction — inverting the
  hybrid-model design.
* **Anchor using `n_prev` as the density scale, to avoid naming a constant.** Rejected in ADR 0102 and still
  rejected: `n_prev` is per-patch and `D` is per-m², so their ratio *is* the patch area; using one as the
  other silently sets it to 1 and converts a drift into a bias that looks anchored. The point of this ADR is
  that the constant did not need avoiding.
* **Keep deferring until line M can co-land it.** That was ADR 0102's decision and it rested on the error.
  With the conversion in hand there is no second side to land.
* **Put `patch_area` in `cell_meta.parquet`.** It is not per-cell in this configuration. A per-cell column
  would imply a variation that does not exist and would have to be regenerated for every artifact.
