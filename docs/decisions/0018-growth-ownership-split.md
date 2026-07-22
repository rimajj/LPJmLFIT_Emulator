---
status: "proposed"
date: 2026-07-22
deciders: "Jamir Priesner (owner)"
consulted: "PROJECT_REVIEW_2026-07-22.md §4; ADR 0002 (emulate distributions), ADR 0003 (flux-then-integrate), ADR 0014 (F_diff-first); src/fdiff.jl (grow_individual, rollout_canopy_years), src/components/fast.jl (annual_step!), src/components/slow.jl, src/interface.jl"
informed: "P1 (put S in the coupled loop); the conservation @testitem gates; MEMORY.md; JOURNAL.md"
---

# Growth-ownership split: F_diff owns representative-individual carbon growth; S owns the distribution + demography

> **Status note.** `proposed`. This ADR formalises the owner's own recommendation in
> `PROJECT_REVIEW_2026-07-22.md` §4, and the owner delegated engineering direction ("you call the
> shots", 2026-07-22) — so **P1 engineering proceeds on this contract now**, while the formal
> `accepted` stamp is left to the owner (ADRs are the owner's audit/control surface). There is no
> divergence from the owner's recommendation to escalate.

## Context and Problem Statement

Two overlapping investments now exist for advancing the vegetation state each year, and the boundary
between them was left implicit:

- **ADR 0002/0003** assign "advance the existing population by conserved increments" to component **S**:
  S predicts per-individual/class growth increments summing to the delivered `bm_inc`
  (flux-then-integrate), plus establishment, mortality, and the trait×size distribution.
- **ADR 0014** then built the fast core **F_diff** *differentiable-first* and, in doing so,
  reimplemented the conserving carbon allocation/growth of representative individuals in Julia —
  [`grow_individual`](../../src/fdiff.jl), [`rollout_canopy_years`](../../src/fdiff.jl), driven at the
  year boundary by [`annual_step!`](../../src/components/fast.jl) (`src/components/fast.jl:257`), a port
  of the LPJmL-FIT `turnover_tree.c → allocation_tree.c → allometry_tree.c` sequence. ADR 0014 kept S
  non-differentiable and *outside* the gradient loop.

So F_diff already performs the differentiable carbon growth that ADR 0003's wording placed inside S,
while `src/components/slow.jl`'s `step!` still `error(...)`s ("not implemented yet") and the coupled
driver [`run_coupled_cell`](../../src/run.jl) grows structure from **F_diff's own** prognostic canopy
with `nind` (individual density) held fixed. `src/fdiff.jl:1794` states the current stopgap plainly:
*"establishment + whole-tree mortality are S's demography, held fixed (fixed-N prototype)."*

**When S is wired into the loop (P1), who owns tree growth — F_diff or S?** Until this is decided the
"hybrid" is a slogan, not an architecture, and P1 cannot be built without double-counting or
double-implementing the year-end carbon advance.

## Decision Drivers

- **Do not discard either code investment.** F_diff's differentiable growth is what makes gradient-based
  online training (P4) possible (ADR 0014); S's distributional emulation is the project's scientific
  novelty (ADR 0002). A split that keeps both is strictly preferable to one that retires either.
- **Conservation must survive the handoff.** Carbon cannot be invented or destroyed where S and F_diff
  meet (ADR 0003, flux-then-integrate). Whoever owns which quantity, `Σ ΔC = f_alloc·bm_inc` must still
  hold to machine precision.
- **Keep the gradient path intact.** The quantity carried on the differentiable channel (`bm_inc` and
  the pools it grows) must stay inside F_diff so Enzyme/Zygote can differentiate the coupled rollout.
- **Match what the code already assumes.** `nind` fixed + "establishment/mortality = S's demography" is
  already the F_diff stopgap; the cleanest resolution is the one that turns that stopgap into the
  ratified contract rather than contradicting it.
- **Well-posedness.** S's target is a *distribution over a variable count N* (ADR 0002). A distribution
  is the right object for demography (who is in the population, with what traits); a conserving ODE-like
  integrator is the right object for advancing each member's carbon. Assigning each to the tool suited
  to it is the well-posed decomposition.

## Considered Options

- **Option A — S owns everything (regenerate-then-conserve).** S regenerates the full trait×size
  distribution each year and F_diff's `grow_individual`/allocation is retired; carbon is reconciled by
  rescaling onto the conserved total.
- **Option B — Split (chosen/proposed).** **F_diff owns the conserving, differentiable *carbon* growth
  of the representative individuals**; **S owns the *distribution + demography*** — count `N`,
  establishment, mortality, and the trait×size *spread* across the population — conditioned on climate,
  state, and the delivered `bm_inc`.
- **Option C — F_diff owns everything (deterministic demography).** Keep the fixed-N prognostic canopy
  permanently; never wire S in. (This is the current running model — it is the thing P1 exists to
  replace, and it forecloses the novelty.)

## Decision Outcome

Chosen: **Option B — the split.**

**The annual contract (each year, at `annual_step!`):**

1. **S sets population membership + trait distribution.** Given the annual climate summary, CO₂, soil,
   the previous-year distribution summary, the 20-yr `Climbuf` memory, stand age, the four mortality
   drivers, and the delivered `bm_inc` ([`FToS`](../../src/interface.jl)), S produces: the new count
   `N` (establishment adds saplings; mortality removes individuals) and the trait×size *spread* — i.e.
   which representative individuals exist and their non-carbon traits/weights.
2. **F_diff advances each representative individual's carbon**, differentiably, by partitioning the
   conserved `bm_inc` into that individual's pools ([`grow_individual`](../../src/fdiff.jl) via
   [`softmax_partition`](../../src/conservation.jl) + [`flux_then_integrate`](../../src/conservation.jl)),
   exactly as it does today.
3. **The flux-then-integrate reconciliation conserves carbon at the handoff.** Establishment carbon is
   debited from `flux_estabc`, mortality moves carbon to litter/soil, fire removes `firec`; every
   movement is an accounted flux, so `ΔC = NPP − Rh − firec + flux_estabc` closes by construction
   (ADR 0003, [`carbon_budget_residual`](../../src/conservation.jl)). The P1 gate re-asserts closure to
   ~1e-6.

**Boundary, stated crisply:** S changes *who is in the population and with what traits* (a
non-differentiable, stochastic, distributional operation); F_diff changes *how much carbon each member
holds* (a differentiable, conserving operation). Neither touches the other's quantity.

**Relationship to prior ADRs.** This clarifies — does not overturn — ADR 0003 and ADR 0014. ADR 0003's
"S predicts per-individual growth increments" is refined: **the differentiable carbon allocation is
F_diff's** (as built under ADR 0014); **S predicts the demographic/distributional envelope** those
increments are applied within. ADR 0014's "S stays non-differentiable, outside the gradient loop"
stands: the `bm_inc`→pools path that must stay differentiable lives entirely in F_diff.

### Consequences

- Good: both investments are preserved; the gradient path (P4) is untouched; the novelty (S) is put at
  the centre of the demography where it is well-posed.
- Good: it ratifies what the code already assumes (`fixed-N prototype` comment, `nind` held fixed), so
  P1 is "hand N + trait spread from S to the existing F_diff growth," not a rewrite.
- Good: conservation is unchanged — the same tested primitives (`softmax_partition`,
  `flux_then_integrate`, `carbon_budget_residual`) carry it.
- Bad/risk: the handoff has a subtlety — when S changes `N` mid-rollout, `bm_inc` (a per-m² quantity)
  must be re-mapped onto the new per-individual basis (`bm_inc/nind`, `allocation_tree.c:236`) without
  leaking carbon. This is the one place the P1 conservation gate must bite hardest.
- Bad/risk: representative-individual identity across a year when membership changes (establishment/
  mortality) needs a defined matching rule so `grow_individual` grows the right pools. To be specified
  in the P1 implementation, tested against the C oracle.
- Neutral: `run_coupled_cell` keeps its structure; the change is that `SToF`/`N` come from S's `step!`
  instead of F_diff's self-computed canopy.

## Pros and Cons of the Options

### Option A — S owns everything (regenerate-then-conserve)
- Good: conceptually simple; one owner for the annual state.
- Bad: throws away F_diff's differentiable growth → forecloses gradient-based online training (P4), the
  capability ADR 0014 exists to enable. Regenerate-then-rescale is exactly the "regenerate-then-hope"
  pattern ADR 0003 rejected. **Rejected** unless S-only proves strictly better on the distributional
  panel.

### Option B — Split (chosen)
- Good: preserves both investments; keeps gradients; well-posed decomposition; matches the code.
- Bad: the N-change carbon re-mapping and individual-identity matching are real implementation care
  points (mitigated by the P1 conservation + C-oracle gates).

### Option C — F_diff owns everything (fixed-N deterministic demography)
- Good: it already runs and conserves.
- Bad: it *is* the deterministic demography S was built to replace; no distribution, no novelty, no
  measured speed-up. This is the status quo P1 supersedes. **Rejected as an end state** (it remains the
  baseline the P1 speed-up is measured against).

## More Information

- Reasoning: `PROJECT_REVIEW_2026-07-22.md` §4. Directive: `STEERING_PROMPT.md` prime directive 2 + P1.
- Superseded/clarified: ADR 0003 (increment ownership wording), ADR 0014 (gradient-loop boundary).
- Validated by (P1 gate): S+F+E runs on Hainich; carbon conserved to ~1e-6 at the S↔F handoff; the
  coupled trait/size distribution matches the offline-S panel; speed-up measured vs the fixed-N
  deterministic-F baseline (Option C).
- Revisit if: the P1 distributional panel shows S-only (Option A) strictly dominates the split on
  fidelity *and* a differentiable surrogate for S's demography becomes available (removing Option A's
  gradient-path cost).
- ADRs are immutable once accepted — supersede rather than edit. This one is still `proposed`; edits are
  permitted until it is ratified to `accepted`.
