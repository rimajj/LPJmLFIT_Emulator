# ADR 0095 — An integrator-owned chore needs an EVENT, not a role; changelog collation attaches to the merge

* **Status:** Accepted
* **Date:** 2026-08-10
* **Line:** cross-cutting / integrator
* **Owner decision:** yes — raised by the repo owner (2026-08-10), on being told 56 changelog fragments were
  uncollated: *"yes do the integrator work, but find a sustainable mechanism for the integration — what is the
  protocol here? who orchestrates integration and who does it?"*
* **Amends:** ADR 0029 §`changelog.d/` (the collation clause), ADR 0028 §the merge ritual, ADR 0090 §the gate
  list (adds a sixth gate, `changelog`)
* **Related:** ADR 0013 (Keep-a-Changelog), ADR 0090 (path-filtered CI)

## Context

`CHANGELOG.md` is written by inserting at the top, in 20–40-line prose blocks. With four concurrent work
lines (ADR 0028) that made it the worst merge conflict in the repo — roughly 54 of the first 128 commits
touched it. ADR 0029 fixed the *authoring* half: each line writes its own `changelog.d/<LINE>-<slug>.md`
file, filenames are disjoint by construction, and the conflict disappeared. **That half worked and is not
in question.**

The *collation* half was specified as one sentence: *"the integrator collates them into `CHANGELOG.md`"*,
"at an integration point". On 2026-08-10 that was measured:

* **56 fragments** were uncollated, the oldest from **2026-07-28** — 13 days, 129 category chunks, 245
  bullets, from all four lines (S 31, M 13, E 6, O 5) **and the integrator itself** (1).
* In that same window `CHANGELOG.md` **was edited three times** (2026-08-06, -07, -10) — by the integrator,
  each time adding its own entry directly and never running the collation.
* Nothing failed. No gate watched `changelog.d/`, no conflict arose (that was the point of fragments), and
  no session was told it was behind. The debt was **invisible by construction**.

The root cause is not laziness and not a missing script. It is that **"the integrator" names a role with no
holder and no schedule, and "at an integration point" names no observable event.** This repo has **no
orchestrator**: ADR 0028 made every line merge its *own* branch to `main` behind a `flock`. That is a good
design and it works — all four lines were merged on 2026-08-10. But it means nothing ever *convenes* an
integration point for a nominated integrator to attend. The integrator is simply whichever session happens
to be launched in the `main` worktree, which is an accident, not a trigger.

The same shape has bitten this repo before under a different name: guardrail 4's corollary (`CLAUDE.md` §6)
records three opt-in flags whose defaults were known-wrong and sat unflipped for weeks because each line
recorded the flip as *the other's* to schedule. An obligation that belongs to "whoever gets to it" belongs
to nobody.

## Decision

**1. Attach the chore to the one event that provably happens: the merge to `main`.**
The session that merges its line runs the collation **inside the same `flock`**, immediately after the merge,
and pushes the collation with it. Holding the lock *is* holding the integrator role for that moment. This
does not violate "never edit `CHANGELOG.md` from a line branch" — the edit happens on `main`, in the
integration worktree.

**2. Make the mechanical part a script, not a procedure.** `scripts/collate_changelog.py`:

* splits each fragment on its `### <Category>` headings — **most fragments are multi-category** (129 chunks
  from 56 files; one has six), which is why hand-collation is error-prone;
* groups by category in a fixed `CANONICAL_ORDER` and inserts **one new group of `### <Category>` sections**
  after `## [Unreleased]`, matching the file's existing shape (repeated category groups, newest at top) and
  deliberately **not** reorganising what is already there — so the diff is provably **purely additive**
  (measured on the first run: 1832 insertions, **0 deletions**, all 245 bullets present);
* **validates categories against a fixed list, erroring on an unknown one** rather than silently inventing a
  section. The list is the six Keep-a-Changelog categories plus the seven this project already uses in
  practice — `Documentation`, `Validation`, `Verified`, `Measured`, `Verdict`, `Gates`, `Notes` (`Documented`
  aliases `Documentation`). Two of these were already live in `CHANGELOG.md` before this ADR;
* preserves a heading's parenthetical qualifier (`### Verdict (497 936 tower steps, 4 sites)`) as an italic
  lead-in, so grouping never discards it;
* derives the repo root from `__file__` (`CLAUDE.md` §9 trap 6 — a hard-coded path writes into the
  integrator worktree from a line worktree);
* is **idempotent** (no fragments ⇒ no-op) and offers `--dry-run` and `--check`.

**3. Make the residue visible: a sixth CI gate, `changelog`.** It runs `--check` on **`main` only**, path
filtered to `changelog.d/**` · `CHANGELOG.md` · the script · its own workflow. A fragment on a `line/**`
branch is *correct* — that is where fragments are authored — so the gate asks exactly one question: **does
`main` carry a fragment nobody folded in?** If a merge skips collation, `main` goes red with the exact list
and the one command that fixes it. Cheap: pure-stdlib Python, seconds, no dependencies.

**4. Generalise the rule, because collation is not the only triggerless chore.** `CLAUDE.md` §9 now states
that *"integrator-owned" names a role, not a person or a schedule*, and carries a table binding each
integrator chore to a triggering event **and** a visibility mechanism (collation → every merge → the
`changelog` gate; shared `MEMORY.md` → every ~5 sessions → the line/token cap; a `[compat]` pin → a red gate
whose diff cannot explain it → `CI`; a cross-cutting ADR or `EXECUTION_PLAN.md` change → an owner steer or a
raised integration point → both lines' `STATE.md`). **A new integrator-owned chore must name both, or it will
rot the same way.**

## Consequences

* Collation happens ~daily as a side effect of ordinary merges, in one command, by whoever merges. No
  session needs to volunteer, and no schedule needs to be kept.
* `CHANGELOG.md` is still only ever written on `main` — the authoring conflict ADR 0029 removed does not
  return. Lines never touch it, so a line rebasing onto a collated `main` sees no conflict; only fragments
  **already merged to `main`** are ever collated, so an unmerged fragment on a branch is untouched.
* The gate can red `main`. That is intended and is the point: this debt was invisible for 13 days precisely
  because nothing could go red. The fix is one command and requires no judgement.
* This ADR does **not** introduce a bot that commits to `main`. Automatic commits from CI were rejected
  (below) — the human/agent doing the merge is already there, holding the lock.
* First collation landed 56 fragments / 129 chunks / 245 bullets into `## [Unreleased]`, growing
  `CHANGELOG.md` from 1247 to 3079 lines with zero deletions.

## Alternatives considered

* **Let lines write `CHANGELOG.md` directly again** — rejected: reintroduces exactly the conflict ADR 0029
  removed, which was the worst in the repo.
* **A scheduled/cron integrator session** — rejected: a schedule is another thing to maintain, it does no
  work when no merge happened, and it fails silently when it stops running (the same failure class again).
* **A CI job that collates and commits to `main` itself** — rejected for now: needs write permissions from a
  workflow, risks push loops with the path filters, and there is no bot-commit precedent in this repo. The
  merging session is already present and holding the lock, which is strictly simpler.
* **Fail the gate on a fragment *count* or *age* threshold** — rejected: a threshold is a knob that drifts,
  and "zero uncollated fragments on `main`" is both simpler and exactly the invariant wanted.
* **Run the gate on `line/**` too** — rejected: it would fire on every correctly-authored fragment, training
  every line to ignore it.
