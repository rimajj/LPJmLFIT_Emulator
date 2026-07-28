---
status: "accepted"
date: 2026-07-28
deciders: "Jamir Priesner (owner)"
consulted: "ADR 0013 (main-only, superseded here — its own reinstatement clause §More Information); ENGINEERING_STANDARDS.md §1; STEERING_PROMPT.md §Orders (the `P1 ∥ P2 ∥ P5` dependency line); the 2026-07-28 contention audit"
informed: "ADR 0029 (the line split + ownership map), CLAUDE.md §9, 00_START_HERE.md, MEMORY.md, .github/workflows/{CI,format,python}.yml"
---

# Parallel session lines: one long-lived branch + git worktree per line (supersedes ADR 0013)

## Context and Problem Statement

All work has so far run through **one serial agent session**, and the owner judged the resulting rate of
progress too slow. The remaining work is genuinely parallel — `STEERING_PROMPT.md` §Orders already states
`Dependencies: P0 → then P1 ∥ P2 ∥ P5 → P3 (after P1) → P4 (after P3 + P5)`, and P2's own heading says "run
in parallel with P1" — but the workspace has **no protocol for two concurrent writers**: no branch strategy
beyond ADR 0013's "main only", no worktree convention, no lock/lease rule, no ADR-number allocator.

[ADR 0013](0013-main-only-workflow.md) chose main-only explicitly for a **single-writer** repo
("**Solo, single-operator repo.** There is no second reviewer") and named this exact situation as its own
reinstatement trigger: *"if a second contributor (**human or otherwise**) joins … revert to the §1 PR +
branch-protection regime by writing a new ADR that supersedes this one."* Running several agent sessions
concurrently **is** that trigger. How do concurrent lines of work share this repo?

## Decision Drivers

- **A shared working directory is unworkable, independent of branching.** The mandated test procedure
  (`CLAUDE.md` §2 / the `julia-test` skill) is `rm -f test/Manifest.toml` before `Pkg.test()` — two sessions
  in one checkout delete each other's test environment mid-run, and neither `test/Manifest.toml`,
  `Manifest.toml` nor `*.jl.*.cov` is tracked, so git gives **no warning**. They would also contend on
  `.git/index.lock`.
- **A shared branch tip serializes and de-attributes.** With one `main` tip, the second `git push` is
  rejected non-fast-forward → a rebase loop (which ADR 0013 §Consequences counted avoiding as a *benefit*).
  Worse, CI attaches to a **sha**, not a session: if line B pushes while line A's run is queued, A's sha may
  never get a completed run, so "is my change green?" becomes unanswerable — and ADR 0013's own mitigation
  ("run the relevant suite locally before pushing") tests a tree that is not what lands.
- **The code is already cleanly partitionable; the contention is elsewhere.** `src/components/slow.jl` +
  `drf.jl` (S) vs `components/energy.jl` (E) vs `run.jl` + `interface.jl` (M) are near-disjoint, and
  `test/testitems/` partitions by subsystem. The real collisions are the coordination documents — see
  [ADR 0029](0029-line-split-and-ownership.md), which handles them.
- **Worktrees are effectively free here.** Tracked content is **6.9 MB**, so each additional working copy
  costs ~7 MB and shares the 31 MB object store.
- **ADR 0013's rejection of branches no longer applies.** It dismissed branches+PRs because they are "still
  self-merged (no review value)". A merge between two *independent* agent lines is not a self-merge; it is a
  real integration boundary with real conflict potential.
- **The owner still declines ceremony.** The speed complaint that motivated this forbids adding a review gate
  or branch protection; the fix must remove friction, not add it.

## Considered Options

- **A. Branch + worktree per line; self-merge to `main` on green branch CI** (no PRs, no protection).
- **B. Branch + long-lived draft PR per line** (PR as the CI vehicle and review surface).
- **C. Keep main-only; separate worktrees all tracking `main`, frequent `pull --rebase`.**
- **D. Full ADR-0013-reinstatement: PRs + branch protection + required checks.**

## Decision Outcome

Chosen option: **A — one long-lived branch per line, each checked out in its own git worktree, self-merged to
`main` when that branch's CI is green.**

It is the only option that removes both failure modes (shared checkout, shared tip) without reintroducing the
ceremony ADR 0013 deliberately removed. Concretely:

- **Branches** `line/S`, `line/M`, `line/E`, `line/O` (scope per ADR 0029), each permanently checked out in
  its own worktree under `/p/projects/open/Jamir/wt-<X>`; `main` stays checked out in the original
  `esm_land_emulator/` directory, which is also the integration worktree.
- **A line's identity is its worktree's branch.** A `SessionStart` hook resolves
  `git rev-parse --abbrev-ref HEAD` → the line, and prints that line's ownership block and its
  `## NEXT — start here` action from `lines/<X>/STATE.md` into the new session's context. A session is never
  told its line by hand, and the ending session's duty is to refresh that `NEXT` block — that is the handoff.
- **CI runs on branches.** `line/**` is added to the `push` triggers of `CI.yml`, `format.yml` and
  `python.yml`. Deliberately **not** `docs.yml`: it holds `permissions: contents: write` and deploys
  `gh-pages`, so running it on four branches would race that branch. Lines build docs locally
  (`DOCS_LINKCHECK=false julia --project=docs docs/make.jl`, already the documented check).
  `CI.yml`'s existing `cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}` now works *for* us: a
  branch push cancels its own superseded run, while `main` runs are never cancelled.
- **Merge ritual** (no PR, no review, no protection — ADR 0013's spirit retained):
  `git pull --rebase origin main` → push the branch → branch CI green (`test (lts)`, `test (1)`, `format`,
  `python`; `test (pre)` is `continue-on-error` and currently red for unrelated prerelease churn) →
  `git switch main && git merge --no-ff line/<X>` → push `main`. Merge at every milestone, never hoard.
- **`main` remains the single integration trunk** and the only branch anything is released or documented from.

### Consequences

- Good, because two-to-four sessions can run **simultaneously** without touching each other's test
  environment, working tree, or branch tip — the actual goal.
- Good, because each line's CI result is **attributable** (its own branch, its own run) instead of being
  superseded by a sibling's push.
- Good, because `main` stays green: a line integrates only after its own suite passes, so ADR 0013's dropped
  "green at all times" invariant is partially **restored** rather than further eroded.
- Good, because a line can iterate fast — `cancel-in-progress` on branches means a rapid push sequence does
  not queue four full suites.
- Bad, because long-lived branches can diverge. Mitigation: rebase on `main` at every session start and merge
  at every milestone; the per-line file ownership (ADR 0029) makes conflicts rare in practice.
- Bad, because it adds a merge step that main-only did not have, and four worktrees to keep straight. The
  `SessionStart` hook and the `repo-commit` skill absorb that cost.
- Bad, because CI minutes and the SLURM queue now carry up to 4× the load. Mitigation: stagger heavy
  submissions; per-line SLURM tag prefixes keep `squeue` and `logs/` attributable.
- Neutral: no branch protection and no required-review gate are added, so the agent is still not
  hard-blocked — the safety net remains CI + the conservation gates + the C-binary oracle + ADRs.

## Pros and Cons of the Options

### A. Branch + worktree per line, self-merge on green

- Good, because it fixes the shared-checkout and shared-tip failures at once.
- Good, because zero ceremony: no PR to open, no reviewer to wait for.
- Good, because green-before-merge protects `main` without blocking anyone.
- Bad, because merge conflicts become possible (mitigated by ADR 0029's per-line files).

### B. Branch + long-lived draft PR per line

- Good, because it gives the owner a per-line diff and comment thread to skim asynchronously, and needs no
  workflow-trigger change (PRs already trigger CI).
- Bad, because it reintroduces exactly the PR bookkeeping ADR 0013 removed, for a gate nobody will enforce.
- Bad, because a long-lived PR accumulates an unreadable diff, which defeats the review benefit that is its
  only advantage.

### C. Main-only + separate worktrees on `main`

- Good, because ADR 0013 stands unchanged and there is nothing new to learn.
- Bad, because it keeps the shared tip: non-fast-forward rejections, rebase loops, and unattributable CI.
- Bad, because one line's red push blocks every other line's ability to verify its own work.

### D. Full PR + branch protection reinstatement

- Good, because it is literally what ADR 0013's reinstatement clause names, and it makes `main` unbreakable.
- Bad, because required checks + protection on a repo whose owner wants **more speed** is the wrong trade;
  the reviewer that would justify it still does not exist.
- Bad, because self-approving a protected-branch PR needs admin overrides — friction with no safety gain.

## More Information

- **Supersedes** [ADR 0013](0013-main-only-workflow.md) (whose `status:` is updated to
  `superseded by ADR-0028`), invoking its own §More Information reinstatement clause. The retained
  obligations from ADR 0013 §Consequences carry over unchanged: Conventional Commits, Keep-a-Changelog, one
  logical change per commit, never commit data/weights/secrets, and run CI-equivalent checks locally
  (CI-faithfully on SLURM) before pushing.
- **Companion:** [ADR 0029](0029-line-split-and-ownership.md) defines *which* lines exist, the per-path
  ownership map, the frozen cross-line contracts, the ADR-number blocks, and the per-line coordination files
  that make merges conflict-free. This ADR is the *mechanism*; 0029 is the *scope*.
- **Operational runbook:** `CLAUDE.md` §9. Mechanics of the ritual: the `repo-commit` skill.
- **Validated by** the Phase-0 acceptance checks: 5 entries in `git worktree list`; the hook printing the
  correct line per worktree; a branch push running `test (lts)`/`test (1)`/`format`/`python` but **not**
  `docs`; two concurrent `run_tests_slurm.sh` submissions from different worktrees both reaching
  `=== JOB DONE … exit=0 ===`; and a conflict-free merge of two lines into `main`.
## Errata (2026-07-28, same day — recorded rather than editing the decision text above)

An adversarial review of this ADR's rollout found the **merge-ritual snippet in §Decision Outcome is not
executable as written**. The decision (branch + worktree per line, self-merge on green branch CI) stands; the
mechanics are corrected in **`CLAUDE.md` §9**, which is authoritative:

1. `git switch main` **fails in a line worktree** — `main` is permanently checked out in the integration
   worktree, so git refuses with `fatal: 'main' is already used by worktree at …` (exit 128). Drive the
   integration worktree with `git -C "$INT"`; there is no "switch back" step.
2. The mandated `git pull --rebase origin main` **rewrites already-pushed commits**, so the snippet's plain
   `git push origin line/<X>` is rejected non-fast-forward — and git's own hint leads to a `--no-rebase` merge
   that duplicates every rebased commit. Use `git push --force-with-lease` (safe: one session per line).
3. Merge **`origin/line/<X>`**, not the local branch, so the sha that lands on `main` is the sha branch CI
   actually verified (a pre-rebase verdict does not transfer).
4. **`flock`** the integration worktree: it is the one remaining shared checkout, and four lines merging into
   it unserialised reintroduces the contention this ADR adopted worktrees to remove.
5. A green branch does **not** imply a green `main` (`format`/`docs`/`python`/Aqua/JET are whole-package gates
   and `docs` never runs on a branch), and GitHub keeps only one *pending* run per branch, so a rapid
   follow-up push can cancel an intermediate `main` verdict — check `main`'s **newest** run after merging.

None of these had run before the review: both acceptance merges were performed from the integration worktree,
where step 1 happens to work.

- **Revisit when** the number of lines changes materially, a line needs a dependency added to `Project.toml`
  (integrator-gated), or the repo goes public with external consumers — at which point option D becomes the
  right answer and should supersede this ADR.
