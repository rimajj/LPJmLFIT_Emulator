# 0175 — the count model's runtime `n_prev` is its own previous PREDICTION while the training column was FIT's own previous stem count, nothing re-synchronises the two, and that is a train/inference shift in the shipped coupled emulator — not a property of the demography

* Status: accepted
* Date: 2026-08-12
* Line: S (tier-3 block 0170–0189)
* Supersedes: nothing. **Narrows ADR 0113/0114/0116's interpretation** — their measurements stand, their
  attribution ("the recursion loses the response") is here traced to a specific defect in how the recursion
  is *constructed*, rather than to the learned mapping. **Does not touch ADR 0103/0105's level anchor** and is
  not covered by ADR 0174 §4's prohibition on one (§4 below explains why they are opposite operations).
* Owner steer this responds to (2026-08-12): *"why the fuck don't you finally fix the warming response?? …
  using the original code for fast physics for the emulator has to work in line S."* Both clauses are
  actioned here — this ADR is the first, and it is what makes the second measurable (§5).

---

## 1. What the code does

`src/components/slow.jl::reconcile_demography!` ends every year with

```julia
s.n_prev = convert(T, target)          # recursive count-space AR update
```

and begins the next year by putting that same `s.n_prev` into the feature row
(`flux_feature_vector`, position 11 of 15) **and** into the denominator of the demographic ratio
`ρ = target / n_prev`. The ten other feature columns are read from the live roster: four flux drivers from
the fast core's annual integrals, and six state aggregates (`hmean`, `hmax`, `agb`, `lai`, `fpc`,
`age_mean`) formed by looping over `pools` — the actual stand.

**So the feature row describes two different stands.** Ten columns describe the roster; one column describes
a scalar that has evolved on its own since year 0. Nothing in the loop compares them, and
`dtree = Σ nind` — the roster's own count, in the same units up to the exact constant `patch_area` — is
computed four lines below and used for the thinning, but never fed back into `n_prev`.

## 2. Why that is a train/inference shift, and not a modelling choice

The count DRF's `n_prev` column was built as **FIT's own previous-year stem count for that
`(Cell, Patch)`** (ADR 0112 §1; `scripts/build_slow_runtime_table.py` aggregates `n_living` off the `ind`
table). At training time it is therefore a *measurement of the stand*. At runtime it is *the model's own
previous output*. The two coincide only while the model is exactly right, and they have no mechanism pulling
them back together when it is not.

This is precisely the failure class ADR 0023 named and that this repo has now paid for four times
(`age_mean` as an elapsed-year counter; `growth_eff`'s `max(lai, EPS)`; `swc`-for-`w`; the `Float32`
group-mean). The distinguishing mark is the same every time: **the runtime value is a plausible proxy for
the training column rather than the same quantity**, and no coverage, finiteness or conservation check can
see the difference.

## 3. What this predicts about the measurements already on the record

The prediction is not new evidence; it is a mechanism for evidence that already exists, and it is
falsifiable:

| observation | ADR | what the shift explains |
|---|---|---|
| free-running **destroys the response, leaves the level alone** | 0113 | the response lives in the year-to-year *change*, which is exactly what `ρ = target/n_prev` computes — and its denominator is the drifting quantity. The level is set by the roster, which is never touched by `n_prev`. |
| response decays over ~5 yr, inverted by 40, **validity horizon ~3 yr** | 0114 | the two bases separate gradually, so the ratio is right while they still agree |
| **not** a regression to the mean (`sd(pred)/sd(truth)` still 0.904, `corr` 0.940 at lead 80) | 0114 §1 | a drifting *offset* preserves variance and correlation. A conditional-mean collapse would not. |
| large declines under-followed (86.7 %) more than large increases (96.2 %), rectifying to **+0.155 stems/patch** | 0116 | when the stand declines and `n_prev` does not follow it down, `ρ` is computed against a too-high base every year, which under-thins. The asymmetry is the asymmetry of the base error. |
| the memoryless null matches the model on every response statistic | 0112 | the null is handed the *truth's* `n_prev`; the model is handed its own. The comparison was never between two mappings — it was between two bases. |

**The falsifier is stated so this cannot be quietly re-read later:** if `n_prev` is taken from the roster and
the free-running response ratio does **not** move materially toward the one-step value (+0.707), then the
defect is real but is not the mechanism of ADR 0113's sign failure, and the attribution in this table is
withdrawn. Being a genuine train/inference shift is not by itself evidence that it is the dominant one.

## 4. Why this is NOT the level anchor ADR 0174 §4 forbids

ADR 0174 §4 forbids "a level anchor for the global count recursion", on the basis that ADR 0105 measured the
anchor harmful and ADR 0113 §2d measured no runaway. That prohibition is intact and this is a different
operation, in the opposite direction:

* **The anchor (ADR 0103, `anchor > 0`)** moves the **STAND** toward the model's absolute prediction:
  `ρ_eff = r^(1−a)·(D_want/D)^a`. It overrides physics with a learned level.
* **This (`roster_n_prev = true`)** moves the model's **INPUT** to the stand's own measured count. It
  overrides a stale scalar with an observation, and leaves ρ and the thinning untouched.

The stand's count is not a free parameter that has to be inferred — it is the physical state, and it is
available at every runtime the emulator has: from the roster in the coupled loop, and from the C's own roster
in a rung-2 substitution arm. Reading it is what makes the runtime feature *equal* the training column. The
anchor was an attempt to inject the count model's level skill into the stand; this removes the need to,
because the stand stops being unobserved.

## 5. What is shipped

1. **`FluxDrivenSlowEmulator(...; roster_n_prev = true)`** re-synchronises `s.n_prev` to `Σ nind · patch_area`
   immediately before the feature row is built. Default `false` ⇒ **byte-identical**; verified by the full
   CI-faithful suite at **274 934 pass / 0 fail** over 133 items (job 1766421).
2. **`flux_feature_vector` is split** so its body takes `(boundary, ages, n_prev, …)` and the
   `FluxDrivenSlowEmulator` method is a one-line wrapper. This is what lets an external harness — one whose
   stand belongs to the C — build the row through the *same* implementation instead of copying it.
3. **The C hook gains the one feature the roster could not supply.**
   `patches/lpjmlfit_rung2_hook_v6.patch` adds `rootzone_w` / `rootzone_whcs` to the `P` record
   (`Σ_{l<3} w[l]·whcs[l]` and its divisor), because `soilmoist` is one of the four flux drivers and
   proxying it is the ADR-0035 trap. Rebuilt binary `bin/lpjml_rung2_v6`; `bin/lpjml.pre_v6.bak` is the
   previous one.
   * **Rebuild-equality gate: PASSED** — 110 decoded quantities identical, including the full `ind` table
     byte-for-byte, same cell (42490), same `--ntasks` (1)
     (`scripts/diagnose_cbinary_rebuild_equality.py`).
   * **The column IS the training quantity, proven against an independent reader**:
     `scripts/diagnose_rung2_rootzone_column.py` compares the patch-ensemble mean of
     `rootzone_w · rootzone_whcs` against the run's own `d_rootmoist.nc` at the year-end day — **max
     relative difference 5.29e-08 over 20 years**, i.e. the float32 precision of the NetCDF output. The
     capacity comes out at 176.6–177.3 mm and `w` at 0.789–1.000, both matching ADR 0035's independently
     recorded Hainich values.
4. **`scripts/rung2_s_demography_harness.jl`** — the rung-2 arm this ADR exists to enable: the shipped count
   DRF setting ρ from a feature row built off the C's own live roster, with arms S0 (uniform thinning, the
   shipped default), S1 (the trait hazard's ordering) and NP (the persistence null, ρ = 1). Establishment
   stays with the C in all three, so every number it produces is a mortality result.

## 6. What is NOT claimed

* **No fidelity number has been measured with the flag on.** This ADR reports a defect and a mechanism; the
  default stays `false` until an arm measures it. Quoting the reasoning in §3 as if it were a result would be
  the exact error ADR 0174 §3 was written to stop.
* **The `>5 m` basis question is open and is separate.** The count target and `n_prev` are trained on the
  `ind` table, whose writer emits only stems above 5 m, while the coupled roster carries whatever cohorts the
  emulator holds. The harness applies the cut explicitly; the shipped coupled path does not, and whether that
  matters has not been measured.
* **The runtime state columns are on a different basis from the training ones** — the runtime recomputes
  `hmean`/`hmax`/`agb`/`fpc` from its own allometry, the training table used the C's own `ind` aggregates.
  The harness logs both rows side by side (ADR 0060) rather than picking one. That gap is *another* candidate
  shift of the same family and is not addressed here.
* Nothing here re-opens CO₂ (ADR 0004 + 0107).
