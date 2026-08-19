# LINE X — JOURNAL (append-only)

Narrative for line X only. Durable state: `lines/X/STATE.md`. Decisions: ADR block 0310–0329.
Newest entry at the bottom.

---

## 2026-08-19 — the line is created, and its first exploration is relocated into it

**Why the line exists.** The owner asked whether a *purely data-driven* emulator could replace the hybrid —
learn `(forest state, climate) → next forest state`, roll it out, plus a daily flux head for an ESM. The
question was put to **line O** (online coupling), which explored it, and the owner then corrected the venue
twice in quick succession:

1. *"no! stop! dont write anythign of this to other lines!!! we are jsut discussion a new direction of this
   project here, nothing to do wiht other lines!!!"* — issued while line O was mid-write of an INBOUND block
   into `lines/S/STATE.md` and about to append cross-cutting facts to `MEMORY.md`. **Both were abandoned; the
   `lines/O/STATE.md` edit was reverted with `git checkout --`.** Nothing reached another line.
2. *"you are also nto the correct person to discuss this with. relocate our whole discussion to a new line
   that is responisble for these project lever decisions and exploring new ideas."*

**What that diagnosed, and it is a real structural gap, not a preference.** The four component lines are each
mid-ladder on one subsystem. A question of the form *"should the architecture be different?"* therefore has no
owner: whichever line is asked must either act on it (wrong — not their call) or drop it. Line O's own
exploration illustrates the failure mode exactly — it produced a defensible finding and then, following the
capture discipline in CLAUDE.md §8 faithfully, immediately began pushing it into two other lines' state. **The
discipline was right and the venue was wrong.** Line X can hold an open question without pushing it at anyone.

**What was done.**

* **Line X bootstrapped complete**, so its first working session starts on content rather than plumbing:
  `lines/X/STATE.md` (charter — scope, the "does NOT do" list, owned paths, the four traps), this journal,
  branch `line/X`, worktree `/p/projects/open/Jamir/wt-X`, ADR block **0310–0329** allocated in CLAUDE.md §9
  (tier-2 reserved at 0330–0349), the row in `docs/decisions/README.md`, and `wt-X` added to the
  SessionStart hook's integrator hint list. The hook needed **no** code change — it is generic over `line/*`
  and resolves `lines/<letter>/STATE.md`.
* **ADR 0088 → ADR 0310, relocated before it was ever committed**, with a Status box quoting both owner
  instructions and stating plainly that nothing was raised with any line and nothing binds anyone.

**The finding itself** (full record in ADR 0310): the proposal is **six problems with six answers**. Daily
water/carbon = data exist, learnability untested. Daily **energy = impossible from this model, permanently**
(of 421 outputs, only monthly albedo + soil temperature are energy-adjacent). One-step operator = already
built, **96 % of its skill is the persistence null** (0.9622 of 0.9824). Century rollout = stable, but every
reason given for the stability was a piecewise-constant-forest artifact, and rollout training has never been
run here. **The warming response = not demonstrated, and zero positive evidence exists** — the one claim died
to a null nobody had run (a pure lat/lon address scores 0.654 of the 0.748 attributed to climate). Speed =
**≈0.0032 core-s/cell-year at fp64**, inside the strict convention with 4× margin.

**Method note worth keeping.** 6 investigations → 6 adversarial reviewers → synthesis → completeness critic
(14 agents, 2.66 M tokens). **All six investigations were refuted.** The reviewers killed five numbers that
would otherwise have been reported to the owner as measurements: a speed figure timed on arrays that had
overflowed to `inf`; a "210× faster than the C" comparison rigged against a configuration nobody runs; a
"needs 0.12 % level accuracy" bar computed on a global aggregate that appears in no acceptance criterion; a
cross-leg error correlation that was actually an 80-year within-chain memory decay; and the response-recovery
headline that fell to the geographic null. **The critic then found the single most important omission — an
architecture that is purely learned yet keeps the per-individual roster — which no investigator and no
reviewer had considered.** ⇒ the adversarial layer earned its cost, and the *completeness* layer earned it
twice; neither is optional on a direction question.

**Also corrected during the session, to the owner, unprompted:** my own earlier hypothesis that the flat
warming response was caused by conditioning on per-cell constants. **Refuted by measurement** — 13 of 15
inputs do vary between scenarios. The real cause is a target defect (the next-year count is 96 % determined
before climate is consulted), which survived review.

**Left open on purpose:** five investigator-vs-reviewer disagreements (ADR 0310 §10), the largest being
whether the measured −0.226 response inversion bounds a closed rollout from below or from above. Recording
them as disagreements rather than picking a side is the point of the line.
