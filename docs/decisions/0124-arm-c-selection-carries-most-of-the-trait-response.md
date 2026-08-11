# ADR 0124 — Arm C: selection carries 71 % of FIT's wood-density differential, the no-selection null restructures the stand, and the option-(c) interface reaches the ceiling exactly

* **Status:** accepted
* **Date:** 2026-08-11
* **Line:** M (multi-cell coupled S+F+E) — rung 2 of `EXECUTION_PLAN.md`
* **Supersedes / amends:** nothing. Consumes ADR 0117 (line S's option-(c) reply), ADR 0121 (the exact
  replay floor for the mortality half), ADR 0122 (the θ=1 identity gate), ADR 0123 (the rendezvous behind
  the growth loop). **Lifts nothing** — ADR 0122 §4's ban on scoring arm C on traits was already lifted by
  ADR 0123; this is the arm it unblocked.
* **Artifacts:** `scripts/rung2_armc_harness.jl` · `scripts/run_rung2_armc.sh` ·
  `scripts/diagnose_rung2_armc.py` · report `/p/tmp/jamirp/M_rung2/armc_report/{armc_score.txt,armc_gradient.csv}`
  · 16 arm runs `/p/tmp/jamirp/M_rung2/M_r2armc_{C0,C1}_{expected,recorded}_s*_{dump,apply}`
  (jobs 1759477–1759492, every one `rc=0` with the mandatory
  `lpjml successfully terminated, 1 grid cells processed.` line)

---

## 1. What was run

Line S returned **option (c)** for the rung-2 demography interface (ADR 0117): S hands back a
per-individual survival factor `f_i ∈ [0,1]` keyed by the `(pft_id, treeidx)` pair of the roster M
publishes, and M draws the Bernoulli. S specified two arms in one wire format:

| arm | `f_i` | what it is |
|---|---|---|
| **C0** | `ρ` for every tree | the shipped uniform ρ-thinning = the **no-selection null** |
| **C1** | `(1 − mort_i)^θ`, θ bisected so `Σ nind·f_i = ρ·Σ nind` | the count target pinned; the ported hazard decides only **who** dies |

`C1 − C0` is the measurement. Both arms defer **establishment** to the C (`ESTAB_C`), because the recruits
half has a structural replay floor of 0.907 (ADR 0121) and substituting it would spend the exactness that
makes a mortality difference attributable. Arm C is a **mortality** arm.

**Nothing was reimplemented.** The hazard is `TraitMortality.mortality_hazard` and the tilt is
`LPJmLFITEmulator._hazard_tilt` — the same code the coupled `FluxDrivenSlowEmulator` calls when
`trait_mortality = true`. A second copy of either would have made the arm measure the harness instead of
the shipped operator (the ADR-0023 train/inference-shift trap in a new place).

**The count target ρ has two sources, and which one an arm ran on must be stated with any number:**

* **`expected`** — ρ = the operator's own mean survival on the live roster,
  `Σ nind(1 − mort_i)/Σ nind`. This reads **no decision of the C's**, only the state the rendezvous
  publishes, which is rung 2's premise. It pins θ to 1 *analytically*, so this arm is simultaneously the
  **ceiling** an option-(c) interface can reach and a **live end-to-end identity check**.
* **`recorded`** — ρ = the recorded baseline's **realized** survival at that patch-year. The target then
  comes from outside the live state, exactly as a learned count model's would, so θ is genuinely solved and
  the count target's own failure modes appear.

Cell 42490 (Hainich), 25 patches, 2000–2019, 500 patch-years per run; 5 seeds per arm on `expected`,
3 on `recorded`.

## 2. The interface is exact, live, and the port holds outside the state distribution it was gated on

Three independent identity results, all new (ADR 0122's gate was offline and only ever saw the recorded
run's states):

1. **ρ from the ported hazard vs ρ from the C's own `mort_prob`, on the live roster:
   max |Δ| = 4.4e-16 over 5 000 patch-years** (the `expected` arms, where the two are the same quantity).
2. **θ = 1 to 4.5e-14 over 2 500 patch-years** — hazard, tilt solver, rendezvous and draw compose exactly.
3. **The port re-gated on an arm's OWN state distribution.** Running
   `scripts/diagnose_rung2_hazard_identity.jl` against the `C0/expected/s1` dump — a stand the recording
   never had, because the null keeps condemned trees alive for years — gives
   `mortality_hazard.total` **max rel Δ 1.7e-15, 0 exceedances over 10 600 records**, with
   **105 `bm_inc_counter` and 769 ghost-tree hard kills** classified correctly.
   ⚠ **This is the generalisable bit: an identity gate is only as wide as the state distribution it ran
   on.** ADR 0122 gated 9 951 records of the *recorded* trajectory; the null arm's trajectory visits a
   region with 7× the ghost-tree rate, and the gate had never been asked about it. Re-run a port's identity
   gate on each new arm's dump — it costs one command and it is the difference between "the port is exact"
   and "the port is exact where we looked".

The C's own audit corroborates it at the decision level: on `C1/expected`, `n_kill_applied / n_kill_c`
(what the arm killed ÷ what the C's own `mortality_tree_ind` chose on the *same* roster) is
**0.980–1.014** across five seeds, and **`n_spared_certain` = 0** — the arm never keeps alive a tree the C
was certain of.

## 3. THE RESULT — three statistics, and the null fails all three

Recorded C truth at this cell: **365 terminal stems**, selection differential **+35 376 gC/m³**.

| statistic | **C1** (selection, 5 seeds) | **C0** (no-selection null, 5 seeds) | the C |
|---|---|---|---|
| terminal stems 2019 | **383.2 ± 18.7 → 1.050×** | 441.2 ± 21.8 → **1.209×** | 365 |
| wood-density selection differential | **+33 684 ± 2 841 → 0.952×** | +8 541 ± 2 455 → **0.241×** | +35 376 |
| per-PFT age–wooddens gradient, Spearman ρ vs the C at this cell | **1.000 / 1.000 / 0.943 / 1.000 / 1.000** (ids 1–5) | 0.800 / 0.500 / 0.943 / 0.600 / **−0.500** | 1 |

⇒ **`C1 − C0` = +25 142 gC/m³ = 71.1 % of the C's own differential is differential survival.** ADR 0117's
argument for option (c) over a count-only interface — *"who dies IS the trait response"* — is now a
measurement, not an argument: a count-only interface leaves 71 % of the wood-density response on the table,
and the null gets one PFT's gradient **backwards**.

### 3a. The largest departure is one no count statistic sees: the age structure

Terminal (2019) survivors by age, and how many of the C's **own** survivors the arm still holds by identity
`(patch, pft_id, treeidx)`:

| age bin | the C | **C1/expected** (5 seeds) | **C0/expected** (5 seeds) |
|---|---|---|---|
| `<20` — built by the arm | 118 | **117–147** | **336–404** |
| `20–40` — carried through | 120 | **111–145** | 25–47 |
| `≥40` — from the shared restart | 127 | **103–126** | 26–47 |
| identity overlap with the C at `≥40` | — | **63–80 of 127 (50–63 %)** | 13–20 of 127 (**10–16 %**) |

**The null does not merely mis-rank traits — it converts a mature stand into a young one.** Uniform hazard
applies to old trees at the same rate as young ones, so it thins the canopy, and the C's own establishment
answers with a flush of recruits: 80 % of C0's terminal stand is under 20 years old where the C's is evenly
spread across the three bins. ADR 0106 measured FIT's *own* age-structure term at −11.8 %; this is not a
−11.8 % perturbation, it is a different stand. C1 reproduces all three bins and keeps half to two-thirds of
the C's actual individuals.

**Read the three bins separately, always.** 20 years is exactly the run length, so `<20` is what the arm
built, `≥40` is what the shared spin-up restart handed it. The old bins are **not** pure inheritance —
C1 has already turned over 37–50 % of them and C0 84–90 % — but a "span" statistic across the whole
gradient is dominated by the youngest bin and must not be read as an equilibrium result at 20 years.

### 3b. Matching the count target every year does NOT reproduce the count

C0 and C1 are given **identical count targets in expectation in every patch-year** (`Σ(1 − f_i)` is equal
by construction of ρ), and both draws are unbiased (C1 killed 579 against 581.6 expected; C0 1 096 against
1 105.9). They still end **1.05× vs 1.21×**. The mechanism is a feedback the count model cannot represent:
the null spares trees FIT condemns (669–817 `n_spared_certain` per run, and 874 vs 369 hazard-hard-kill
records), those trees keep a high hazard, so the *next* year's ρ falls and the arm kills **1 096 vs 579**
trees in total — nearly twice as many — while ending denser.

⇒ **A count target is not a count.** Who dies feeds back into how many, so a Stage-2 arm that reports
only a density ratio cannot tell a right answer from a compensating pair of wrong ones.

## 4. What the `recorded` variant adds — the count target's own failure mode

`recorded` is where the tilt is actually solved, and it is the honest proxy for the production
configuration (a target from outside the live state):

| arm | terminal ratio | selection ratio | θ median / p95 | θ > 0.5 | patch-years with an unreachable target |
|---|---|---|---|---|---|
| `C1/recorded` (3 seeds) | 1.087× | 0.669× | **0.000 / 12–14** | 207–215 / 500 | **124–134 / 500 (25–27 %)** |
| `C0/recorded` (3 seeds) | **1.536×** | 0.180× | n/a | — | 0 |

Two things this measures, both of which S's ADR 0117 item 6.i anticipated:

* **θ is bimodal, not small.** The median of 0 is not the tilt collapsing — **the C kills nobody in 198 of
  500 patch-years (39.6 %) at this cell** (558 deaths in 9 951 tree-years), so a realized-count target is
  exactly 1.0 and there is nothing for selection to do. In the other half θ runs to 12–14: the target
  demands far more death than the hazard produces.
* **In 25–27 % of patch-years no θ reaches the target at all** (`shortfall > 0`) — the hazard's hard kills
  alone already overshoot it. `_hazard_tilt` reports this rather than absorbing it, which is the only reason
  it is visible. And `C0/recorded` applies just **38–48 %** of the kills the C wanted, ending **1.54×**.

⇒ **A count model that sets ρ without seeing the hazard will fight it.** Quote θ's *distribution* and the
shortfall rate beside any production arm; a null `C1 − C0` under such a target says nothing about selection.

## 5. Decision

1. **Adopt option (c) as the rung-2 mortality interface.** It is exact end-to-end (§2) and it reaches
   1.05× on counts, 0.95× on the selection differential and the gradient ordering in 5 of 5 PFTs (§3).
   Those numbers are the **ceiling** for this interface, not an emulator score — see §6.
2. **Report the four statistics of §3 and §3a together, never singly.** Counts, selection differential,
   per-PFT gradient ρ against *this cell's own recording*, and the three-bin age structure. The null passes
   none of them and would pass a density-only report at 1.21× in some cells.
3. **The global gradient fixture cannot be a per-cell acceptance target.** Scored against
   `references/S_age_wooddens_gradient.csv` (all 54 020 cells), **the C's own recording at this cell** gets
   Spearman ρ of −0.500 (id 2), −0.314 (id 3), +0.400 (id 4), −0.500 (id 5), +0.800 (id 1). The fixture is
   a different population; a naive reading of ADR 0118 §3 as "score the arm against the fixture" would have
   failed FIT itself. `diagnose_rung2_armc.py` prints the C's own row against the fixture for exactly this
   reason — the reference's inapplicability is measured, not asserted.
4. **Pre-registered flip criterion for line S's `trait_mortality` default** (guardrail 4's corollary: an
   opt-in whose default is known worse is a defect on a timer). Raised to S as an INBOUND block in
   `lines/S/STATE.md`, not left as a note here. **Arm:** the coupled `FluxDrivenSlowEmulator` at cell 42490,
   25 patches, 2000–2019, 5 seeds, `trait_mortality` `false` → `true`, everything else fixed.
   **Pass condition:** the terminal three-bin age structure of §3a within the C's own seed spread on all
   three bins, AND the per-PFT gradient Spearman ρ against this cell's recording ≥ 0.9 on ids 1–5.
   **Value to flip to:** `true`. **What blocks it today:** ADR 0049 item 4 — offline the operator has
   neither of FIT's stress integrals, and the harness result does **not** transfer, because inside the
   harness both are the C's own exact accumulators (§6).

## 6. What this does NOT show — read this before quoting §3

* **C1/expected is not a count model.** With ρ from the operator's own hazard, θ = 1 identically, so C1 *is*
  FIT's mortality with an independent Bernoulli stream. Its agreement with the C is a **ceiling
  measurement** and an end-to-end identity — not evidence that any learned count model reproduces FIT.
  Every real ρ can only do worse, and `recorded` (§4) shows by how much a mismatched target costs.
* **The hazard ran on the C's own state.** `water_stress`, `temp_stress`, `bm_delta`, `leafarea_real` and
  `bm_inc_counter` come from the C's accumulators through the rendezvous. That is rung 2's premise (borrow
  the C's *state*, not its *decision*), but it means **§3 does not license flipping `trait_mortality` in the
  standalone emulator**, where S must compute those itself — hence the conditional criterion in §5.4.
* **One cell of 54 020**, one scenario, no climate-change response measured. The acceptance criterion
  (ADR 0106) is unaffected by anything here.
* **4 of 7 trait axes** are what the wire format carries; `k_root` is a scalar identity in this config
  (ADR 0117), `emax`/`beta_2` are emitted nowhere.
* **The C binary defers its demographic kills** under either rung-2 env var — mathematically inert, not
  bit-identical, worth **0.05 % of stem-years** over 20 years at this cell (ADR 0123). Two orders of
  magnitude below this model's smallest noise floor (11.3 % bootstrap CV on `vegc` at `npatch=25`), but a
  departure from stock LPJmL-FIT, and it is shared by both arms **by construction** so it cannot bias the
  comparison.
* **A single seed is not an observable** (ADR 0106: the C's own two runs disagree on the sign of a per-cell
  trait response in 33–37 % of cells). Every number above is a seed mean with its across-seed spread.
