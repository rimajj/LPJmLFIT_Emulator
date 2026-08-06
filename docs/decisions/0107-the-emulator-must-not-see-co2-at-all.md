# ADR 0107 — the emulator must NOT see CO2 at all: constant CO2 is FAITHFULNESS, not a gap

* **Status:** Accepted
* **Date:** 2026-08-06
* **Line:** S · ADR block 0100–0119 (tier 2)
* **Supersedes, in part:** **ADR 0106 §4**'s table row "under climate change — CO2 · FAILS COMPLETELY ·
  the largest single gap" and **ADR 0106 §5 item 2** ("CO2 needs its own item, and it does not exist yet …
  may need a new run of the original model, which is an owner-level cost decision"). **Both are WITHDRAWN
  as factually wrong.** ADR 0106 §1–§3 (the owner's criterion itself), its other five gap rows, and §5
  items 1/3/4 all stand unchanged.
* **Decides:** **(1)** the emulator must **not respond to CO2 and must not even see it as an input**;
  **(2)** its lack of a CO2 response is therefore **correct behaviour and evidence of faithfulness**, not a
  defect, not a gap, and not an item on any queue; **(3)** the emulator responds to **climate**, and the SSP
  scenarios already carry the CO2-driven climate signal — that is the channel, and it is the only one;
  **(4)** **nothing is owed by the owner here** — the "new run of the original model" raised in ADR 0106 §5
  is cancelled and must not be re-raised.
* **Related:** **ADR 0004** (the decision this ADR merely restates — 2026-07-15, owner), DESIGN.md §4.2/§9,
  the docs Limitations page, ADR 0106 (the criterion, whose CO2 row this corrects).
* **Evidence:** none required — this is a correction to a claim that contradicted an existing accepted
  decision that the correcting ADR itself cited.

## 1. The science, which ADR 0004 already recorded

This configuration runs LPJmL-FIT with `with_nitrogen="no"`. **Without nitrogen limitation, CO2
fertilization is unbounded**, so a rising-CO2 future run makes vegetation carbon blow up. The source model
is therefore deliberately run at **constant CO2** for all future runs (`global_co2_ann_1700_2019_const_2100.txt`,
flat from 2020), because **its CO2 response is not correct** — the limitations that would bound it are absent.

Two consequences follow, and the second is the one ADR 0106 got backwards:

1. The emulator's regime is **warming + precipitation change at constant CO2**. That is not an impoverished
   test — it is the real SSP370 GCM trajectory, and it is the regime the ground truth exists in.
2. **The CO2-driven signal is already inside the climate forcing.** The SSP scenarios' warming and
   precipitation changes *are* the effect of rising CO2, transmitted through the atmosphere. An emulator that
   responds to that climate is responding to CO2's consequences by the only route that is physically
   defensible here. Giving it CO2 as a *direct* input would let it learn a fertilization response that the
   source model is known to get wrong.

⇒ `CO2_CONST = 369.0` in every training row is the design working as intended. The correct statement about it
is a **validity-envelope disclosure** — "this emulator must not be used to project CO2-fertilization
responses" (ADR 0004's own wording) — **not a fidelity failure**.

## 2. What ADR 0106 said, and why it was wrong

ADR 0106 §4 listed the CO2 row as "**FAILS COMPLETELY** … the largest single gap and it is structural", and
§5 item 2 escalated it to an unowned item that "may require a new run of the original model, which is an
owner-level cost decision". Read against the acceptance criterion — *fully emulate the original model* — this
is precisely inverted: **the original model has no CO2 response in its future runs, so an emulator with no
CO2 response matches it.** Adding one would be a fidelity *regression*, and would also reintroduce the carbon
runaway ADR 0004 exists to avoid.

**The failure mode is worth naming because it is not a knowledge gap.** ADR 0004 is listed in ADR 0106's own
`Related` line. The information was retrieved and then contradicted — a wrong claim was generated *next to*
its own refutation. Citing a decision is not the same as reading it, and a "gap list" is exactly where an
absent behaviour gets mislabelled as a missing one.

**And it was broadcast.** ADR 0106's CO2 row went into `MEMORY.md`, into all four lines' `## NEXT` banners,
and into `~/.claude/CLAUDE.md`. All of those are corrected in the same commit as this ADR. A false claim
placed in four session-start banners is not a documentation error; it is four lines' next sessions
misdirected.

## 3. The standing rule — do not re-litigate this

Recorded in `MEMORY.md` §owner decisions alongside the reuse/licensing entry, in the same "standing, do not
re-open" form, because the owner reports having had to correct it repeatedly:

> **The emulator does not see CO2 and does not respond to CO2. It responds to climate. The SSP scenarios
> already carry the CO2-driven climate signal. The source model runs constant CO2 on purpose because its own
> CO2 response is wrong (no nitrogen limitation). Never raise a CO2 response, a CO2 feature, varying-CO2
> training rows, or a new model run for CO2, and never list the absence of a CO2 response as a gap, a
> defect, or a limitation of the *emulator* — it is a documented limitation of the *source model*, carried
> forward deliberately.**

## 4. The method rule

**An absent behaviour is not automatically a missing one — check whether it was designed out before calling
it a gap.** A gap list built by asking "what does the emulator not do?" will confidently promote every
deliberate simplification to a defect. The check is one question per row: *is there an accepted decision
that this should not be there?* For CO2 the answer had been written down thirteen months earlier and was
sitting in the same ADR's own reference list.

Corollary: **when a fidelity criterion is "match the reference", every candidate gap must be stated as a
comparison against the reference, never as an absolute capability.** "The emulator has no CO2 response" is
not a finding. "The emulator's CO2 response differs from the source model's" would be one — and it is false.
