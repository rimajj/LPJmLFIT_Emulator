---
status: "accepted"
date: 2026-07-28
deciders: "Jamir Priesner (owner) — direct instruction"
consulted: "ADR 0080 (the good-faith basis), ADR 0015 (reuse map), STEERING_PROMPT.md P5"
informed: "all lines; ADR 0080 §4 (its open owner action is closed here)"
supersedes: "0080 §4 only (the owner-action checklist and the 'file LICENSE first' framing) — 0080's factual register and its depend-not-vendor mechanism stand"
---

# Owner closes the licensing question: reuse of LPJmL-FIT / Terrarium / SpeedyWeather is authorized; the only standing obligation is transparent citation

## Context and Problem Statement

[ADR 0080](0080-licensing-basis.md) delivered the good-faith licensing basis `STEERING_PROMPT.md` P5 asked
for, and left one open owner action (file `LICENSE`). On **2026-07-28** the owner closed the matter directly,
supplying the fact that had been missing from every prior analysis: **he is a member of both upstream groups
— the LPJmL-FIT group and TUM-PIK-ESM**, which hosts SpeedyWeather.jl, Terrarium.jl and
LPJmL-hybrid-photosynthesis.

His instruction: **use these models, stop discussing licences, and make sure they are transparently cited
wherever they are used.**

## Decision Outcome

**The licensing question is CLOSED. Reuse is authorized. Citation is the requirement.**

1. **Reuse freely** — LPJmL-FIT, Terrarium.jl, SpeedyWeather.jl, LPJmL-hybrid-photosynthesis. No licence
   analysis, no licence decision, and no upstream licence re-audit is needed before using them, including
   for P4 online coupling.
2. **Do not raise licensing again.** ADR 0080 (the basis) plus this ADR (the owner's decision) are the
   complete and final record. Reopening it is a waste of a session; the owner has said so explicitly.
   Anything genuinely new belongs in a *new* ADR, not a re-derivation of the old one.
3. **Transparent citation is the one standing obligation.** Every reused model is cited in **all four**
   surfaces, kept in agreement: [`docs/third_party_licensing.md`](../third_party_licensing.md) (the
   provenance register), `CITATION.cff`, `docs/src/refs.bib` (cited inline as `[key](@cite)`), and the
   **header of any source file with derived content**. Provenance must be stated *accurately* — neither
   overstated (ADR 0080 §3) nor omitted.
4. **`LICENSE` is no longer a blocker or a tracked TODO.** ADR 0080 §4 stands only as a recommendation the
   owner may action whenever he chooses (`AGPL-3.0-or-later`, justified there). Nothing waits on it.

### Two things that are NOT reopened by this, and are not licensing caveats

- **NeuralCrop.jl stays method-only.** It is CC-BY-NC and belongs to a different author outside these two
  groups, so the owner's memberships do not cover it. Cite the paper (arXiv:2512.20177); do not copy code.
  Likewise LPJ_resilience — reimplement its published metrics from Bathiany et al. (2024).
- **Runtime `[deps]` still stays empty (ADR 0014), so Terrarium/SpeedyWeather still enter as `[weakdeps]` +
  a package extension.** This survives for a purely **technical** reason that has nothing to do with
  licences: the HPC compute nodes have no GitHub egress, and the physics core is deliberately
  dependency-free. Same for ADR 0017 — component E stays self-contained on its zero-deps and v0.1.x-churn
  drivers.

### Consequences

- Good: P4 proceeds with no legal question in front of it, and the next session spends its time on the
  coupling instead of on this.
- Good: the requirement that remains — accurate, four-surface citation — is the one that matters for
  scientific credit, and it also happens to be all the attribution the upstream licences ask for, so
  nothing further is outstanding.
- Bad: the four citation surfaces must be kept in sync by hand; drift between them is the failure mode to
  watch, and the `reuse-citation` skill exists to prevent it.

## More Information

The factual content of ADR 0080 remains useful and is retained: the verified upstream register (what each
package actually is, and how that was verified) is now the **citation** register, and its READ/DEPEND/VENDOR
distinction remains good engineering hygiene — vendoring a copy of someone's source still deserves an ADR
because of maintenance drift, independent of any licence. Revisit only if a *new* upstream from outside these
two groups is proposed.
