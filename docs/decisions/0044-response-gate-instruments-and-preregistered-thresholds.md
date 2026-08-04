# ADR 0044 — the response gate's instruments: a paired bootstrap, a corrected reliability ceiling, and pre-registered thresholds

* **Status:** Accepted
* **Date:** 2026-08-04
* **Line:** S (Component-S science) · ADR block 0030–0049
* **Closes:** **ADR 0042** §10 caveat 7b (the missing paired bootstrap, costed at "~15 lines, zero new
  forest compute" and left unbuilt) and its §5.1 verdict that the inter-arm `Rb` gaps are "not
  resolvable" — that expectation is now **measured**, not inferred.
* **Related:** ADR 0030 (the four S2 acceptance criteria and the floor/ceiling machinery), ADR 0037
  (pooled-marginal metrics are blind to a badly under-resolved conditional), ADR 0038 (the env arm met
  all four criteria and was refused), ADR 0040 (the response statistics `Rr`/`Ra`/`Rb`), ADR 0042 (the
  forbidden-statement list, the noise scales, the `Rr` sign flip between fold modes)
* **Supersedes on one point:** ADR 0040 §4's split-half **ceiling of 0.9201** and every `Ra` computed
  against it. The corrected values are in §2. No prediction, no artifact and no arm changes.

## Context

The owner approved closing Component S's damped wood-density warming response (deployed ncond-8 arm:
`Rb` = −971.5 against `meanDobs` = +2432.9, i.e. **39.9 %**). Before any treatment arm runs, two
instruments the gate depends on had to be built or fixed, because **without them no acceptance
threshold can be written and any threshold chosen later is retro-fittable to whatever improved**:

1. **No paired bootstrap existed for any response statistic.**
   `scripts/diagnose_slow_address_prereg.py:245-246` calls `cluster_boot` on **marginal** `Rr` and `Rb`
   only, one arm at a time. That is the wrong instrument for an inter-arm difference, which is why
   ADR 0042 §5.1 had to record every response gap as sitting "far inside the marginal intervals".
2. **The split-half reliability halves shared their patch-years.**
   `diagnose_slow_address_prereg.py:191` builds them as
   `pl.int_range(pl.len()).over(["Cell","scen"]) % 2` on a table sorted by `(Cell, Patch, Year)`
   (`build_slow_runtime_table.py:352`), so consecutive rows are the **same** patch-year and the two
   halves interleave within every retained patch-year.

New instrument: **`scripts/diagnose_slow_response_power.py`** (job `1693482`, exit 0).

## Decision

### 1. The paired instrument ships, and it is GATED on reproducing the published table

One tile resample is applied to **every arm at once**, so the "which cells are in the sample"
component cancels and the difference is isolated. Before any bootstrap is reported the script must
reproduce ADR 0042 §5's logged Wooddens table from each arm's stored `pred_*.f64`. `[VERIFIED]`: all
seven arms reproduced, `Rr`/`Ra` to **≤ 5e-5** and `Rb` to **≤ 0.05**, with `meanDobs` = +2432.9
(logged +2432.9) and the stem-parity ceiling = **0.9201** (logged 0.9201), on **52 450** cells — the
same universe. A gate failure is a hard exit, not a warning: the noise must attach to the same numbers
the ADRs quote.

### 2. `[VERIFIED]` The reliability ceiling was UNDERstated, not overstated — the prediction was refuted

The patch-year grouping needed no `Year` column and no gated reconstruction. The copula table
**broadcasts** the per-`(Cell,Patch,Year)` conditioning aggregates onto every stem row of that
patch-year (`build_slow_runtime_table.py:352` inner join), so rows of one patch-year carry
**bit-identical** `Xc` head values, and **runs of identical `Xc[:, :4]` ARE the patch-year groups** —
an exact reconstruction. Measured: **8 292 458** patch-year groups over 42 227 077 rows (5.1
stems/patch-year; median 54 patch-years per `(Cell, scen)` segment; only 362 segments have <2, where
the split is degenerate). This retires `lines/S/STATE.md`'s carried debt "emit `Year` in the
`MODE=copula` table (schema change ⇒ ride a new generation)" **for this purpose**.

The working hypothesis was that the stem-parity halves omit the between-patch-year variance component,
making `rel` too high, the ceiling an **upper** bound and `Ra` **understated**. **That is wrong, in
direction, on all four axes.** `rh_py > rh_stem` everywhere:

| axis | `rh` stem | ceil stem | `rh` patch-year | **ceil patch-year** | Δceil | `sd_true` ratio |
|---|---|---|---|---|---|---|
| SLA | 0.8494 | 0.9584 | 0.8839 | **0.9687** | +0.0103 | 1.0107 |
| **Wooddens** | **0.7340** | **0.9201** | **0.8360** | **0.9543** | **+0.0342** | **1.0372** |
| D95max | 0.6115 | 0.8712 | 0.7940 | **0.9408** | +0.0697 | 1.0800 |
| minwscal | 0.8119 | 0.9467 | 0.9011 | **0.9737** | +0.0270 | 1.0285 |

So the between-patch-year term is **not** dominant; the stem-parity split was too **pessimistic**.
Two consequences, in opposite directions, and both must be reported:

* **The pattern deficit is WORSE than published.** Wooddens `Rr` = 0.3751 against **0.9543**, i.e.
  **39.3 %** of ceiling, not 40.8 %.
* **`Ra` was OVERstated.** `sd_true` rises 3.72 %, so the deployed arm's dispersion ratio is
  **1.034**, not 1.0728, and `|Ra − 1|` = **0.0344**, not 0.0728.

**This strengthens the placement-not-shrinkage reading decisively.** The deployed emulator's shift
**amplitude is nearly perfect** (1.034) while its **pattern captures 39 % of ceiling**. It produces
right-sized shifts in the wrong cells, which cancel in the mean. Pure shrinkage would damp mean and
dispersion together. **Therefore any lever justified by "fixing attenuation/dispersion" is aimed at a
problem this emulator does not have**, and the ADR-0038 dispersion criterion (C2, `sd_ratio ≥ 0.75`)
is measuring a level-space quantity that does not transfer to the response.

### 3. `[VERIFIED]` `ΔRb` is NOT resolvable, and the pre-registered `Ra` fallback FIRES

Wooddens, patch-year basis, paired 15° tile-cluster bootstrap, NBOOT = 2000, 161 tiles:

| paired delta | `ΔRr` [sd] | `Δ\|Ra−1\|` [sd] | `ΔRb` [sd] | `\|pt\|/sd` on `Rb` |
|---|---|---|---|---|
| B `p14env-hash` − A `p8-hash` | **+0.0395** [0.0178] | +0.1274 [0.0838] | **+79.5** [353.1] | **0.23** |
| G `p14perm-hash` − A `p8-hash` | −0.0153 [0.0043] | −0.0171 [0.0464] | **+291.3** [88.1] | **3.30** |
| E `p14geo-hash` − A `p8-hash` | **+0.0610** [0.0155] | +0.0902 [0.0875] | −341.7 [322.3] | 1.06 |
| D `p14env-blk` − C `p8-blk` | **−0.0304** [0.0162] | +0.0893 [0.0949] | +163.2 [533.4] | 0.31 |
| F `p14geo-blk` − C `p8-blk` | −0.0779 [0.0136] | +0.1021 [0.0914] | −611.0 [528.3] | 1.16 |

* **`sd_paired(ΔRb)` blocked = 533**, above the 450 trigger (`0.5·|Rb_baseline|`) pre-registered for
  demoting `Rb`. **The fallback fires: `Rb` is a VETO ONLY and can never be a primary criterion.**
* **The permutation null buys `Rb` RESOLVABLY: +291.3 ± 88.1, 3.30σ, P(Δ≤0) = 0.000.** A
  zero-information column change moves the damping toward zero with high confidence. ADR 0042 §5.3
  argued "less damping can be bought with noise" from a point estimate; it is now **quantified**. This
  retires the sentence form *"X reduced the damping from 37 % to Y %"* permanently, in every variant.
* `ΔRr` env−p8 = **−0.0304** blocked, reproducing ADR 0042 §4's −0.0305 to four decimals **from an
  independent implementation** — but its paired sd is 0.0162, so each single draw is only ~1.9σ. **The
  credibility of that penalty rests on its replication across colourings, not on either measurement.**
* The pure-**position** arm has the **largest** hash-fold `ΔRr` of any arm (+0.0610, 3.93σ) and
  collapses under blocking (−0.0779, 5.74σ). Textbook address signature; consistent with ADR 0042.

### 4. The pre-registered acceptance thresholds (frozen HERE, before any treatment arm runs)

Criterion axis is **Wooddens**. Tier P decides; Tier S may only veto (ADR 0038's arm met all four
Tier-S criteria and was correctly refused).

* **P1 — pattern, NECESSARY.** `ΔRr ≥ max(+0.030, 2·sd_paired) = **+0.036**` (the measured 2σ binds,
  slightly above the proposed floor), with the **same sign at both `BLOCK_SALT`s and at hash**, and
  `|ΔRr(s0) − ΔRr(s1)| ≤ 0.010`. Rationale for the floor: the refused env tail's penalty was −0.0305
  replicated on both colourings, so a fix must clear that magnitude in the opposite direction.
* **P2 — amplitude (the promoted primary, per §3).** `Δ|Ra − 1| ≤ −0.03` on the **patch-year** basis,
  both colourings, CI excluding 0. Baseline `|Ra − 1|` = **0.0344** (arm A). Note this baseline is
  *already small*, so P2 has little room and is expected to act mainly as a guard.
* **P3 — `Rb`, VETO ONLY.** `|Rb|` must not increase. An `Rb` improvement may be **claimed** only if
  P1 has already passed **and** its paired CI excludes 0 at **both** colourings. Not otherwise.
* **Tier S** (ADR 0030 C1–C4): C3 scored on **pooled KS numerically, never `nqrmse`** (ADR 0038 §4);
  `TRAIT_ONLY=0` mandatory. C1/C4 remain **not computable** on the future basis until `CAP_HASH_SEED`
  lands — write "not computed", never "passed" (absence is not a pass, ADR 0042 §6).
* **Admissibility:** paired deltas only, never a blocked level alone; leave-one-tile-group-out on every
  accepted blocked delta; realized leaf sizes reported. Measured noise: `sd_paired(ΔRr)` **0.0178 hash
  / 0.0162 blocked**; `sd_paired(Δ|Ra−1|)` **0.084–0.095**; `sd_paired(ΔRb)` **322–533**.

### 5. Additions to the forbidden-statement list (extending ADR 0042 §8)

1. **Any "the damping fell from A % to B %" claim** unless P1 passed first with a paired CI at both
   colourings. §3 shows a zero-information change buys +291 at 3.3σ.
2. **Do not quote 0.9201 as "the `Rr` ceiling", or any `Ra` computed against it.** Use the patch-year
   values in §2 (Wooddens ceiling **0.9543**), and state the basis.
3. **Do not describe `Rb` = −892 / "37 %" as the deployed model's damping.** −892 is arm **B**
   `p14env-hash`, the **refused** env arm. The deployed ncond-8 arm is **−971.5 = 39.9 %**
   (ADR 0042 §5.1). `docs/component_s_public_report.tex` currently quotes the wrong arm.
4. **Do not justify a lever by "reducing attenuation" or "raising the dispersion ratio".** On the
   corrected basis the deployed arm's response amplitude is 1.034; the defect is placement (§2).
5. **Do not present the −0.0305 `Rr` penalty as individually significant.** It is ~1.9σ per draw; its
   force comes from replicating across two colourings.

## Consequences

* Phase-2 conditioning arms may now be run against a frozen, measured gate. Nothing about them is
  decided here.
* `diagnose_slow_address_prereg.py:191`'s stem-parity split is left **in place and unchanged** so
  every published number stays reproducible; the corrected basis is computed alongside it by the new
  script. This is deliberate: no committed baseline moves (guardrail 4).
* `docs/component_s_public_report.tex` needs three corrections — the ceiling (§2), the arm attribution
  (§5.3), and the amplitude reading (§2). Not made in this ADR.
* **Not measured, so every sd above is a strict LOWER bound on replication noise:** forest-seed noise
  (`seed = a` hard-wired at `ntrees = 6`), fold-colouring noise, and the `STEM_CAP` cluster-subsampling
  draw — the bootstrap resamples tiles, not the cap, which is why the published `Rb` CI understates its
  own interval. `CAP_HASH_SEED` is the separate fix and is not in this ADR.

## Alternatives rejected

* **Emit `Year` in the copula table and ride a new generation** (the route `STATE.md` carried as debt)
  — unnecessary: the `Xc` broadcast already fingerprints the patch-year exactly, at zero cost and with
  no schema change.
* **Re-estimating `sd_true` inside each bootstrap draw** — it is a property of the target's
  reliability, not of the resample, and re-estimating it injects the split-half's own noise into every
  arm's `Ra` identically, destroying the pairing.
* **Keeping `Rb` as the headline** — §3 measures it as unresolvable *and* buyable with noise. Retaining
  it as primary would have made the plan's most quotable number its least trustworthy one.
