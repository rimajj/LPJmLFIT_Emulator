# ADR 0133 — The tree demand-gate default is FLIPPED ON: it meets its own pre-registered criterion, removes 21 % of the assimilate error on the most faithful arms, and is paid for in the photosynthesis channel and in one cell's GPP deficit

* **Status:** accepted
* **Date:** 2026-08-13
* **Line:** M (multi-cell coupled S+F+E; rung 3 of `EXECUTION_PLAN.md`) · ADR block 0120–0139
* **Consumes:** ADR 0131 (built the gate, measured it, and **pre-registered this flip's three conditions**
  in its §8), ADR 0132 (the `sapwood_bg` growth port — condition (a), the blocking one), ADR 0129/0130
  (the photosynthesis/respiration split this moves in opposite directions), ADR 0059 and ADR 0075 (the two
  previous default flips, whose procedure this follows — now the `julia-test` skill's "Landing a DEFAULT
  FLIP" section)
* **Supersedes:** nothing. **Discharges ADR 0131 §8** (its criterion is met and its ACTION in
  `lines/M/STATE.md` is closed). **Amends the arm definitions of four probes** (§5) so that the arms which
  MEAN "gate off" say so instead of inheriting a default that has moved.
* **Basis:** the flip is scored on the committed
  `test/testitems/references/M_growth_channel_decomposition.csv` (rung 3, five biome cells, historic
  2010–2019, 25-patch ensemble, year-matched, `slow = nothing`) and on the coupled 2-year 5-cell driver.
  Logs of record: **`logs/M-treegate-flip.1771606.out`** (the blast-radius suite, default flipped and NO
  baseline touched), **`logs/M-regenbase.1771763.out`** (the canopy baseline, two arms in one run),
  **`logs/M-enspin-off.1771770.out`** / **`logs/M-enspin-def.1771772.out`** (the coupled pins, opt-out
  control and new default), **`logs/M-treegate-flip2.1771985.out`** (the green suite after the two
  deliberate baseline moves).

---

## 1. Context — a default known to be unfaithful, with the flip condition written down in advance

ADR 0131 established that `water_stressed.c:196` runs a tree's photosynthesis only when that tree's own
canopy demand clears `gpd > 1e-5`, that the gated branch zeroes **both** gross assimilation and leaf
respiration, and that F_diff had run the tree path ungated since it was written. It shipped the fix
**opt-in** because guardrail 4 requires the measurement to happen without moving a committed baseline —
and, per guardrail 4's corollary, it **pre-registered the flip criterion in the same document** rather than
leaving a future session to decide. That is the whole reason this ADR is short: nothing here is a judgement
call about whether the gate is a good idea. The three conditions were:

1. the `sapwood_bg` **growth** port has landed (the two act on the same CUE channel and partially cancel,
   so flipping first would silently re-price that port's own pass criterion);
2. on arm `Pg`, mean `|bmi_F/bmi_C − 1|` over the four readable cells (excluding `mediterranean_iberia`)
   does not increase against the then-current arm `P`;
3. the full suite's failure list is enumerated and every moved assertion is a deliberate baseline move.

Condition (a) was satisfied by ADR 0132 on 2026-08-13.

## 2. Condition (b) — met, and met on the arms that now exist rather than the arms that existed when it was written

Computed from the committed decomposition table over `boreal_siberia`, `temperate_hainich`,
`semiarid_sahel`, `tropical_amazon`:

| comparison | mean `\|bmi_F/bmi_C − 1\|` | verdict |
|---|---|---|
| `P` → `Pg` (the criterion exactly as pre-registered) | 0.1914 → **0.1581** (−0.0333) | **PASS** |
| `Pbgg` → `Pgbgg` (the same test on the ADR-0132 growth arms) | 0.1599 → **0.1266** (−0.0333) | **PASS** |

Per cell (`Pbgg` → `Pgbgg`): boreal 0.2524 → 0.1772 · Hainich 0.1986 → 0.1767 · Sahel 0.1199 → 0.0836 ·
Amazon 0.0687 → 0.0688. The improvement is −0.0333 in **both** comparisons to four decimals, i.e. the
gate's effect on the assimilate is additively separable from the below-ground port's at these cells — the
partial cancellation ADR 0131 §8 condition (a) was protecting against does not appear in this channel.
Including the excluded fifth cell the mean still falls (0.5029 → 0.4859), so the exclusion is not doing the
work.

**The verdict does not depend on which of the two comparisons is used, which is the only reason it is
reported this way.** The pre-registered form named arm `P`, which is no longer the most faithful
configuration that exists; had the two disagreed, the pre-registered form would have been the one that
counts and the disagreement would have been the finding.

## 3. Condition (c) — the blast radius, measured: 4 assertions of 275 597

Following the `julia-test` default-flip procedure, the default was flipped **alone**, with no baseline
touched, and the CI-faithful suite run (`logs/M-treegate-flip.1771606.out`): **275 593 pass / 4 fail**,
135 test items. The complete failure list:

| # | site | what moved |
|---|---|---|
| 1–2 | `tree_demand_gate_tests.jl:50,51` | the "default is OFF" assertions themselves |
| 3 | `multi_individual_tests.jl:190` | `hainich_canopy_baseline_2010.txt` `gpp_annual`: 1250.124 → 1237.437 (**−1.02 %**) |
| 4 | `biome_coupled_tests.jl:326` | the coupled `boreal_siberia` GPP pin: 1.01916 → 0.96798 (**−5.02 %**) |

Third flip in a row whose measured blast radius is 3–4 assertions (`wscal_leafon` 3, `enable_two_layer` 3).
The suite is green again after the two deliberate baseline moves below: **275 605 pass / 0 fail**
(`logs/M-treegate-flip2.1771985.out`).

## 4. The two baseline moves, each regenerated by a harness that reproduces the OLD numbers in the same run

Step 3 of the procedure: a re-record of whatever the new code prints cannot prove the harness ran the
gate's own configuration. Both regenerators were given an explicit opt-out arm.

**(a) The coupled 5-cell pins** — `scripts/biome_ensemble_pin_probe.jl` gains a `TREE_GATE=0|1` env knob
following the same convention as its existing `TWO_LAYER` (unset = the package default, which is what the CI
gate runs). The `TREE_GATE=0` arm reproduced all ten previously committed pins **to every printed digit**.
Deltas, default vs opt-out:

| cell | LE | GPP | coupled stand cover `fpc` |
|---|---|---|---|
| `boreal_siberia` | 23.9726 → 23.9437 (−0.12 %) | 1.01916 → **0.967978 (−5.02 %)** | 0.3037 → 0.2942 |
| `temperate_hainich` | 40.4677 → 40.4456 (−0.05 %) | 3.44906 → 3.40306 (−1.33 %) | 0.5689 → 0.5633 |
| `mediterranean_iberia` | 46.6253 → 46.6246 (−0.002 %) | 5.05669 → 5.05285 (−0.08 %) | 0.4404 → 0.4402 |
| `semiarid_sahel` | 35.2051 → 35.255 (+0.14 %) | 1.36655 → **1.38778 (+1.55 %)** | — |
| `tropical_amazon` | 116.062 → 116.063 (+0.001 %) | 6.94035 → 6.94069 (+0.005 %) | — |

**The Sahel's sign is the informative one and it is not a contradiction.** Within a day the gate can only
LOWER GPP (`gate ∈ (0,1]`, asserted in the gate's own test). Over two coupled years it RAISES that cell's
mean GPP, because the gate stops F paying leaf respiration against a collapsed assimilation on drought
days, so the tree carbon balance improves (ADR 0131: −83.8 → +34.6 gC/m²/yr there), the canopy grows
instead of shrinking, and a larger canopy assimilates more. Minimum pairwise separation stays 0.128 LE /
0.272 GPP against gate tolerances of 0.02 / 0.03, so the pins remain a fallback detector.

**(b) The Hainich canopy annual totals** — `scripts/regen_fdiff_baselines.jl` now runs the canopy block as
two arms and prints both plus their ratios. **Only `gpp_annual` moves**; `transp`/`evap`/`interc`/
`rootmoist` come out at ratio **exactly 1.0**, which is the mechanism's own prediction (the gate multiplies
tree GPP and tree `rd`, both formed *after* `gp_stand`, transpiration and the per-layer soil withdrawal) and
is therefore a check, not a coincidence. So exactly one of the five committed rows was re-recorded.

⚠ **An honest limit of that control, recorded in the fixture's own header rather than smoothed over:** the
gate-OFF arm reproduces the committed file to **1.3e-4, not to its printed digits**. The four water rows
carry ≤ 1.6e-4 of accumulated **sub-tolerance drift** from earlier physics changes — the drift alarm's
tolerance is 1e-3, so it never fired. That drift predates this flip and is **left in place**: absorbing it
into this re-record would have hidden a pre-existing fact behind an unrelated change, and re-recording all
five rows would have made the diff stop being this flip's blast radius.

## 5. The control-arm audit (step 5) — four probes whose arms would have been silently relabelled

The failure mode is ADR 0075 §4's, which cost line E a sub-daily verdict: an arm written to take the
default **by omission** stops being a control the moment the default moves, and prints numbers under a label
that is no longer true. Audited every construction of the F parameter bundle:

* **`scripts/biome_sapwood_bg_probe.jl`** — the worst case, and it would have been silent. Its arms
  `A`/`Abg`/`P`/`Pbg`/`Abgg`/`Pbgg` are DEFINED as the gate-off ADR 0125/0126/0132 basis, and its
  `PARAMS_TG` is built by copying `PARAMS` and setting the flag: with the default flipped, `PARAMS_TG` would
  have become **field-for-field equal to `PARAMS`**, collapsing `Ag ≡ A` and `Pg ≡ P`, and 30 committed rows
  of the decomposition table would have been reproducible only under labels that no longer described them.
  `mkparams()` now passes `tree_demand_gate = false` explicitly.
* **`scripts/biome_canopy_growth_probe.jl`** (whose published panel the probe above gates PART 1 against),
  **`scripts/biome_slow_oracle_probe.jl`**, **`scripts/biome_resilience_probe.jl`** — same one-line fix, for
  the same reason: their published panels are on the gate-off basis. Re-measuring them on the new default is
  a deliberate new arm, not a substitution.

The rule this leaves behind: **an arm that means a specific value passes that value; only an arm that means
"whatever ships" takes the default by omission.** The coupled pin probe is deliberately the latter — that is
why it needed an explicit opt-out knob instead of an explicit value.

## 6. Guardrail 4, re-served through the opt-out (step 4)

`test/testitems/tree_demand_gate_tests.jl` now pins the **new** default explicitly
(`WaterParams{Float64}().tree_demand_gate == true`) so the next flip cannot be silent, and asserts that a
bare `tebs_params()` rollout reproduces the explicit `tree_demand_gate = true` arm bit-for-bit — guardrail 4
on the path that ships, not on the struct default. The opt-out is still exercised and still builds a
physical stand.

⚠ **One assertion in that file was a hole after the flip and is now closed with its reason asserted rather
than assumed.** The pre-flip test proved "the default reproduces a bare rollout bit-for-bit". After the flip
that pair *still passed* — not because the flag is inert, but because at the soft default `βgpd_gate = 2e4`
the sigmoid saturates to exactly 1.0 on every day of that fixture's forcing, so opt-out and gated default
are byte-identical **on that fixture**. Left alone, a green assertion would have carried a comment that was
now false. The equality is kept, relabelled as a property of the fixture, and the wiring is proven where the
gate actually fires (the fixed-structure daily arm at the C's hard `1e8` step, where `d_on != d_off` on the
trees). This is the `julia-test` skill's "a gate that looks green while proving nothing" check catching a
gate written **one week earlier by this same line**.

## 7. The cost, in the same breath as the gain (step 6)

The gain is in the carbon budget. The cost is in the photosynthesis channel — and the two are the opposite
halves of ADR 0129/0130's split, exactly as ADR 0131 §1 warned:

| channel, mean over the four readable cells | `Pbgg` → `Pgbgg` |
|---|---|
| assimilate `\|bmi_F/bmi_C − 1\|` (the criterion) | 0.1599 → **0.1266** (−21 % of the error) |
| respiration `\|cue_F/cue_C − 1\|` | 0.1420 → **0.1363** |
| photosynthesis `\|gpp_F/gpp_C − 1\|` | 0.0570 → **0.0611 (WORSE)** |

Per-cell GPP ratio: boreal 1.0273 → **1.0022** (better), Hainich 1.0851 → 1.0744 (better), Amazon 1.0223
(unmoved), **Sahel 0.9065 → 0.8545 (worse)** — the whole photosynthesis regression is that one cell, whose
GPP was already the second-lowest against the C and whose deficit this deepens. (That ratio is itself biased
DOWN by the sub-5 m stems the `ind` writer drops, `gt5m_frac` 0.783 there — ADR 0130 — so its LEVEL is not
quotable, only its movement.) In the coupled driver the cost also shows as slightly less canopy: `fpc`
−3.1 % at boreal, −1.0 % at Hainich.

**Why flip anyway:** the criterion was pre-registered on the assimilate channel because that is the quantity
that drives growth, and the gate is not a tuning knob — it is what the C does. A faithfulness fix that
worsens one diagnostic at one cell is still faithfulness; the alternative on offer is a default that is
known to be a mis-port. What is NOT claimed: that this improves GPP, that the Sahel's photosynthesis is
better, or that the flip helps at `mediterranean_iberia` (excluded from the criterion, and the one cell
where the gate makes the assimilate error worse — ADR 0131 §5).

## 8. What this does NOT change

* **The differentiated path.** `rollout_canopy_years_gpp` reads `p.water` directly with no reconstruction,
  so the trainer now runs with the gate ON at the **soft** `2e4` — AD-usable, and licensed by ADR 0131 §6,
  which measured that sharpness reproducing the C's hard step to the printed digit at three of five cells.
  All four `nn_canopy_training_tests` Enzyme items pass unchanged. But note it: any trainer arm that meant
  "the pre-0133 path" must now say so.
* **The single-individual kernels.** `daily_step` / `daily_step_ml` honour neither gate (ADR 0131 §SCOPE);
  the `hainich_fdiff_baseline_2010`/`_ml_` fixtures are untouched, verified in the same regen run.
* **The head of the F queue.** At Hainich F still over-grows by 57 % and 77 % of that is the assimilate
  error (ADR 0127 §4). This flip is a default change, not a new mechanism — the ~24 % Hainich assimilate
  excess with every parameter faithful is unmoved as the next target.

## 9. Files

* `src/fdiff.jl` — `WaterParams.tree_demand_gate` default `false` → `true` (one character; the surrounding
  ADR-0131 commentary is unchanged and still describes the mechanism).
* `test/testitems/tree_demand_gate_tests.jl` — the new default pinned, guardrail 4 re-served through the
  opt-out, the fixture-saturation caveat asserted.
* `test/testitems/biome_coupled_tests.jl` — the five coupled pins re-measured, with the control-arm
  provenance and the Sahel sign explained in place.
* `test/testitems/references/hainich_canopy_baseline_2010.txt` — `gpp_annual` only.
* `scripts/biome_ensemble_pin_probe.jl` — the `TREE_GATE` opt-out knob.
* `scripts/regen_fdiff_baselines.jl` — the canopy block as two arms with ratios.
* `scripts/biome_sapwood_bg_probe.jl`, `scripts/biome_canopy_growth_probe.jl`,
  `scripts/biome_slow_oracle_probe.jl`, `scripts/biome_resilience_probe.jl` — gate-off made explicit.
