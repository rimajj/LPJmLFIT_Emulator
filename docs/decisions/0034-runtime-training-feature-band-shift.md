---
status: "accepted"
date: 2026-07-28
deciders: "engineering agent on line S (full autonomy per STEERING_PROMPT.md). The four out-of-band columns and the before/after threshold table are MEASURED facts (job 1622724 after, job 1622727 before, both on compute nodes with identical fixtures); the decisions recorded here are (a) to close S1c as scoped rather than widen it into the three newly-exposed causes, (b) to route those three causes separately by owner, and (c) to make the shift permanently observable and CI-gated instead of documenting it in prose."
consulted: "scripts/measure_hainich_gate_bands_probe.jl (the re-measurement harness; validated by reproducing the pre-S1c documented numbers 0.39/1.25/0.67 exactly), the regenerated test/testitems/references/drf_forest_hainich_meta.txt trained bands, src/components/slow.jl::flux_feature_vector (the runtime rows) + reconcile_demography!, scripts/build_swc_soilmoist_feature.py (the training soilmoist = mean over days x 23 layers), scripts/build_laistand_lai_feature.py (the training lai = C LAI_STAND cell-mean), src/components/fast.jl:353-369 (growth_eff / water_stress), ADR 0023 (train/inference consistency), ADR 0032 (the artifact-basis split this closes), ADR 0029 (the F core belongs to line M)"
informed: "line M (the F-core water_stress finding is an integration point; the committed demo .drf moved, which M's planned M2 CI gate reads), lines/S/STATE.md milestones S1c (CLOSED) + S1d (NEW), the slow-drf-pipeline + residual-diagnosis skills, MEMORY.md"
---

# Regenerating the demo artifact closed the artifact-basis SPLIT but not the runtime↔training SHIFT — three separate causes remain, and they are now measured and gated

> **Status.** `accepted`. Milestone S1c is complete and closed: the committed Hainich count `.drf` and recruit
> `.rcop` are on one feature basis, every affected drift threshold is re-measured, and one is tightened. This
> ADR records what that did **not** fix, why it must not be fixed inside S1c, and how the remainder is now
> visible to CI rather than to prose.

## What was measured

S1c regenerated all four committed Hainich demo artifacts from one table build
(`scripts/verify_hainich_demo_artifacts.sh`, job 1622718). Result, exactly as ADR 0032 predicted: the
`.rcop` + its meta and both `hainich_slow_oracle_*.csv` came back **byte-identical**; only
`drf_forest_hainich.drf` + `_meta.txt` moved, and the control re-confirmed the working tree is a no-op for
this cell (`STALE-FIXTURE`, exit 2 — the expected verdict, not a failure).

**The artifact-basis split is closed.** The `.rcop`'s fallback conditioning row now lies inside the `.drf`'s
trained per-feature band on all eight shared columns, and their boundary tails are equal — **0 violations**
(was: `soilmoist` 0.854 against a constant-0.7 basis, `growth_eff` 150.5 against ~19).

**Every re-measured drift threshold improved** (`scripts/measure_hainich_gate_bands_probe.jl`; the BEFORE
column is the same harness pointed at the artifact extracted from git, which reproduced the three documented
pre-S1c numbers exactly — that is what validates the harness):

| gate quantity | assertion | proxy-basis `.drf` | real-basis `.drf` |
|---|---|---|---|
| Gate-3 Height `nqrmse` | ≤ 0.45 → **0.40** | 0.3895 | **0.2998** |
| median Height ratio | 0.6 … 1.6 | 1.2463 | **1.1316** |
| settled count ratio | 0.25 … 4.0 | 0.6734 | **1.2808** |
| `target_history` band | 0.5 … 40 → meta `y`-band | 6.62 … 9.72 | 12.28 … 13.64 |
| DIRECT copula draws (SLA / Wooddens) | ≤ 0.22 / ≤ 0.12 | 0.1274 / 0.0346 | **unchanged** |
| coupled community (SLA / Wooddens) | ≤ 0.45 | 0.2558 / 0.2203 | 0.2634 / 0.2203 |
| carbon residual | < 1e-6 | 2.5e-12 | 1.7e-12 |

The three Height/count numbers move together and the mechanism is coherent: in-domain `bm_inc_cell` /
`growth_eff` raise the settled count from ~6.8 to ~12.9 stems per patch, and more stems sharing the same
carbon are smaller trees, so the size distribution moves **down** toward the C truth. This is deterministic,
not a seed wobble — the same fixtures and seed differ only in which artifact is loaded.

**And the finding S1c was built to surface.** With the runtime rows now recorded
(`FluxDrivenSlowEmulator.feature_history`) and the trained band now in the meta (`feat_min`/`feat_max`),
**4 of 15 feature columns are still outside the band the forest was trained on**, identically in all three
coupled harnesses (12-yr, 20-yr, 20-yr + copula):

| column | runtime range | trained band | excursion | cause |
|---|---|---|---|---|
| `water_stress` | 0.323 … 0.331 | [0, 0.0432] | **6.6× band width** | F_diff vs the C oracle |
| `soilmoist` | 0.792 … 0.999 | [0.8416, 0.8674] | **5.1×** | TEMPORAL aggregation |
| `lai` | 3.63 … 5.17 | [2.758, 3.369] | **2.9×** | SPATIAL aggregation |
| `fpc` | … 0.784 | [0.155, 0.741] | 0.03× | SPATIAL aggregation (marginal) |

Every other column is inside, including the two the regeneration moved in. On the **retired** proxy basis the
shift was worse and pointed the other way — the runtime `lai` (3.3–5.1) sat *below* all five committed golden
rows' `lai` values (21.2, 59.6, 37.2, 29.1, 56.3) and the runtime `growth_eff` (124–179) sat *above* all five
(19.0, 6.6, 12.3, 20.0, 7.6). That is directly checkable in the pre-S1c artifact and needs no reconstruction.

### Why the old gate could not see any of this — a proof, not an inference

ADR 0032 attributed the green gates to the DRF leaf-clamping out-of-domain inputs, flagged as inferred. The
real reason is structural and stronger: **a DRF prediction is a convex combination of training leaf means, so
it can never leave `[y_min, y_max]` no matter what it is fed.** The assertion "predicted targets are inside
the training band" is therefore *incapable* of failing, and it is not a conditioning check at all — it is an
artifact-integrity check. Detecting a conditioning shift requires looking at the **input** side. That is why
this ADR ships a mechanism, not just a measurement.

## The three causes are distinct, and only one of them is S's to fix

1. **`water_stress` — an F-core-vs-C difference, not an aggregation artifact.** Both sides use the same
   definition (`1 − wscal_mean`, `fast.jl`). The training rows carry ~0.001 (Hainich is essentially
   unstressed in the C); F_diff reports ~0.33 in the coupled loop, two orders of magnitude larger, while its
   own soil column is near saturation for part of the year — internally odd enough to need its own
   diagnosis. `src/fdiff.jl` / `src/components/fast.jl` belong to **line M** (ADR 0029, CLAUDE.md §9), so S
   must not "fix" this; it is raised as an integration point.
2. **`soilmoist` — a TEMPORAL aggregation mismatch, and a textbook ADR-0023 shift.** Training is
   `build_swc_soilmoist_feature.py`'s mean of the C `swc` over **365 days × 23 layers** (an annual mean);
   the runtime is `sum(state.w)/length(state.w)` (`slow.jl`) evaluated at the **instant**
   `reconcile_demography!` runs, i.e. one year-end layer mean. An annual mean's range cannot contain an
   instantaneous value's range even with identical physics, so part of this excursion is *expected* and is a
   training-basis choice that was never decided. Fixing it means choosing one side: train on year-end `swc`,
   or feed the runtime an accumulated annual mean (the `ClimBuf` pattern of ADR 0027 already shows how).
3. **`lai` / `fpc` — a SPATIAL aggregation mismatch, already known but never quantified.** Training joins the
   C's patch-ensemble **cell-mean** `LAI_STAND`; the runtime forms a **single-patch** stand LAI on the
   most-populous patch. The `slow-drf-pipeline` skill already flagged this as an open Phase-5 decision ("do
   not overclaim per-patch consistency"); it is now measured at ~1.4× for `lai`, and `fpc` follows because
   the coupled single patch is denser than any training patch-year.

## Decision

1. **S1c is CLOSED as scoped**, and deliberately not widened. It promised one basis for the two committed
   artifacts, a re-measurement of the four gates, and a documented threshold move; all three are delivered.
   Folding the three causes above into it would repeat exactly the entanglement ADR 0031 §3 forbids — and
   two of them are not even S-owned.
2. **The Hainich demo emulator is NOT to be described as runtime-consistent.** The accurate label is:
   *conditioned consistently on 11 of 15 columns; `water_stress`, `soilmoist` and `lai` remain shifted*.
   The Gate-3 improvement above is real and measured, but it is **not** evidence of a clean conditioning
   basis and must not be re-cited as such.
3. **Make the shift observable and CI-gated, permanently.** Three additive pieces, no numerical change:
   `FluxDrivenSlowEmulator.feature_history` records the exact row fed to the forest each year (diagnostic
   only); `train_slow_drf.jl` writes `y_min`/`y_max`/`feat_min`/`feat_max` into every artifact meta; and
   `slow_production_drf_tests.jl` asserts the out-of-band set is **exactly** `{water_stress, soilmoist, lai}`
   with a bounded worst excursion, plus `bm_inc_cell`/`growth_eff` strictly inside. A new column drifting
   out, or these growing, now fails CI. The set is asserted at a 0.5-band-width cut so the marginal `fpc`
   excursion cannot flap across CPU microarchitectures.
4. **Route the causes by owner; do not bundle them.** `soilmoist` (temporal) and `lai`/`fpc` (spatial) become
   **milestone S1d** — an S-side training-basis decision needing its own ADR, because either fix changes what
   the features MEAN and is therefore a both-sides change with M (ADR 0023). `water_stress` is raised to
   **line M** as an integration point against the F core.
5. **S1d comes before S2.** S2 expands the copula conditioning; starting it while three conditioning columns
   are on the wrong basis would let S2 take credit for a basis fix — the exact failure mode ADR 0033
   recorded, where the population fix silently delivered 30 % of S2's gate.
6. **Rejected: retrain on runtime-produced features** (i.e. drive the coupled loop and fit the DRF to what F
   emits). It would make every band assertion pass by construction while teaching the emulator F's own bias
   instead of the C's demography. The C binary is the oracle (guardrail 3); the training basis must stay the
   C's, and the *runtime* must be brought to it.
7. **This is not demo-only.** The global `_t7` artifacts come from the same builder, so causes 2 and 3 apply
   to them too. Their published OOS numbers are unaffected because they are measured offline, table against
   table, never through the coupled loop — but a coupled global run inherits the shift, which line M needs
   before M3.

## Consequences

- **ADR 0032's expectation is corrected, not overturned.** Its diagnosis (two artifacts, two bases) was right
  and its fix was necessary; its implicit reading — that regenerating the artifact would restore
  train/inference consistency — is falsified, and its "two of eleven head features" undercounts: after the
  fix the shifted set is `water_stress` (which 0032 did not flag at all), `soilmoist` and `lai`.
- **One threshold tightened, none widened:** the Gate-3 Height alarm 0.45 → **0.40**, a 0.10 absolute cushion
  over the 0.2998 measurement — relatively *wider* than the 0.45/0.39 it replaces, which matters because this
  20-year Float64 trajectory's tails are CPU-microarch-sensitive. All other bounds are unchanged and their
  re-measured values are written into the test comments.
- **The `.rcop` gates are untouched** because the artifact is byte-identical; the trait-side single-cell
  evidence stands exactly as measured.
- **Cost carried forward:** the demo `.drf` is regenerated whenever the feature basis changes, and S1d will
  move it again. That is the intended behaviour of a golden fixture that is only a gate on change if it is
  itself current (the generalization ADR 0032 recorded).
- **`feature_history` grows with simulated years** (15 `Float64`s per year). Negligible for a cell-decade;
  worth a bound if a coupled run ever spans millennia at global scale.

## Alternatives considered

- **Assert zero out-of-band columns now.** Rejected: it would red the suite immediately and force either a
  rushed fix inside S1c or a silently-widened gate. Pinning the *known* set keeps the alarm live for anything
  new while naming the debt.
- **Document the four columns in prose only** (an ADR + a STATE.md note, no assertion). Rejected: that is
  precisely the mechanism by which the proxy basis survived five days of green gates and a whole milestone.
  A documented shift with no gate is a shift that comes back.
- **Widen the trained band to admit the runtime values.** Rejected: the band is a *measurement* of the
  training data, not a tunable. Widening it would destroy the only signal that can detect the next shift.
- **Fix `water_stress` from line S** (it is the largest excursion). Rejected: `src/fdiff.jl` /
  `components/fast.jl` are line M's under ADR 0029, and the finding needs an F-vs-C oracle diagnosis
  (`fdiff-validate`), not an S-side feature change.
