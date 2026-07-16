---
status: "accepted"
date: 2026-07-16
deciders: "Jamir Priesner (owner)"
consulted: "ENGINEERING_STANDARDS.md §0/§1; ADR 0009 (deploy-key auth); the session-2 CI-repair experience"
informed: "ENGINEERING_STANDARDS.md §1 (softened), MEMORY.md §6, HANDOFF_NEXT_SESSION.md, JOURNAL.md"
---

# Work on `main` directly — no feature branches, no PRs, no branch protection

## Context and Problem Statement

`ENGINEERING_STANDARDS.md` §0/§1 mandated a trunk-based, short-lived-branches **+ Pull-Request**
workflow with **branch protection** on `main` (required status checks, direct pushes disabled) as the
"hard gate the AI agent cannot bypass." After Phase 0 and the session-2 CI repair + component-S port,
the owner reassessed the cost/benefit of that gate for a **solo, single-agent, pre-release** project
and decided to relax it. Which Git workflow do we actually use going forward?

## Decision Drivers

- **Solo, single-operator repo.** There is no second reviewer; a PR the same operator opens and merges
  is ceremony, not review. The value a PR gate adds in a team (independent human approval) is absent.
- **CI feedback is still wanted** — the test/format/docs/python signal must keep running on every
  change, just not as a *merge blocker*.
- **Friction from branch protection.** Protection mutations, force-pushes for rebases, and the
  PR-open/merge dance were repeatedly flagged by the Claude Code auto-mode permission classifier,
  interrupting otherwise-authorized work (see JOURNAL session 2).
- **The repo is still private and pre-release.** No external consumers depend on `main` being
  green at every instant; a transient red is recoverable by fixing forward.
- Signing (the "Verified" badge) was **declined** by the owner (repo going public later) — a separate
  simplification, recorded here so the docs match reality.

## Considered Options

- **Keep §1 as written:** trunk-based + short-lived branches + PR-per-change + branch protection
  (required checks, no direct push, signed commits).
- **Main-only:** commit and push straight to `main`; CI runs on `push: main` as a *smoke alarm*, not a
  gate; fix-forward if a push turns `main` red.
- **Middle ground:** branches + PRs but **without** branch protection (PRs optional, self-merge).

## Decision Outcome

Chosen: **main-only.** Commit and push directly to `main`. **No feature branches, no PRs, no branch
protection** (owner declined branch protection explicitly). CI workflows still trigger on `push: main`,
so the test/format/docs/python signal is preserved — it is now a **smoke alarm** (tells you *after* a
push) rather than a **gate** (blocks *before* a merge). If a push turns `main` red, **fix forward**.

This is a deliberate, owner-authorized relaxation of `ENGINEERING_STANDARDS.md` §0/§1. §1's wording is
softened to point at this ADR (§1 is not deleted — it records the *original* stricter posture and the
conditions under which it would be reinstated).

**Reinstatement condition:** if a second contributor (human or otherwise) joins, or the repo goes
public with external consumers, **revert to the §1 PR + branch-protection regime** by writing a new ADR
that supersedes this one. The exact `gh api -X PUT …/branches/main/protection` command (required checks
`test (lts)`, `test (1)`, `format`, `docs`, `python`; **no** `required_signatures`, since signing was
declined) is preserved in `JOURNAL.md` (session 2) for that day.

### Consequences

- Good: no PR ceremony, no branch-protection mutations, no force-pushes/rebases → fewer auto-mode
  permission interruptions; faster iteration for a solo operator.
- Good: CI still runs on every push, so regressions are still surfaced loudly (just after the fact).
- Bad / carried forward: `main` can be transiently red between a breaking push and its fix — the
  "green at all times" invariant is dropped. Mitigation: run the relevant suite **locally before
  pushing** (the session-2 practice of reproducing CI locally), and fix-forward promptly.
- Bad / carried forward: commits show **"Unverified"** on GitHub (signing declined) — cosmetic; do not
  chase it while the repo is private.

## Pros and Cons of the Options

### Keep §1 as written (PR + branch protection)

- Good: `main` is provably green at every instant; the AI agent cannot merge red code.
- Bad: for a solo operator the PR is self-approved (no real review); protection mutations, rebase
  force-pushes, and the PR dance generate constant permission friction for zero review value.

### Main-only (chosen)

- Good: minimal friction; CI signal retained as a smoke alarm; matches the solo, pre-release reality.
- Bad: drops the "always-green `main`" guarantee; relies on local pre-push checks + fix-forward
  discipline instead of a hard gate.

### Branches + PRs without protection

- Good: keeps a PR paper-trail per change.
- Bad: still self-merged (no review value), still needs rebases/force-pushes; the paper-trail
  duplicates what `JOURNAL.md` + Conventional-Commit messages already provide. Not worth the friction.

## More Information

Retained from §1 even under main-only: **Conventional Commits** (drives SemVer + a readable history),
**Keep-a-Changelog** `CHANGELOG.md`, one-logical-change-per-commit, never commit data/weights/secrets,
and **run CI-equivalent checks locally before pushing**. Superseded specifically: the PR requirement,
branch protection, "direct pushes to `main` disabled", and (separately) signed-commit enforcement.
Revisit when the repo gains a second contributor or goes public — write a superseding ADR then.
