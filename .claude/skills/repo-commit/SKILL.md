---
name: repo-commit
description: Commit/push/merge discipline for the LPJmL-FIT emulator under PARALLEL WORK LINES (ADR 0028/0029) — the branch-per-line + git-worktree model, the rebase→push→green-branch-CI→merge-to-main ritual, the mandatory STATE.md NEXT handoff before a session ends, where each artifact is written (per-line JOURNAL/STATE + changelog.d fragments, never CHANGELOG.md from a line), per-line SLURM tags and ADR number blocks, the pre-push checklist against the 5 CI gates, the commit trailer, and how to check CI via the GitHub REST API (gh not on PATH). Use whenever committing, pushing, merging a line, or checking CI for this repo.
---

# repo-commit — commit, push & merge under parallel work lines

**Commit and push as you go** — full autonomy (`STEERING_PROMPT.md`); no owner sign-off is needed or expected.
CI is a smoke alarm, not a human gate: run the equivalent checks locally first.

**Since 2026-07-28 work runs on 4 parallel lines** (ADR 0028, which supersedes ADR 0013's main-only rule):
one long-lived branch `line/{S,M,E,O}` per line, each checked out in its own worktree
`/p/projects/open/Jamir/wt-{S,M,E,O}`; `main` stays in `esm_land_emulator/` as the integration worktree.
Your line = the branch in the worktree you launched from (the `SessionStart` hook tells you). Full protocol:
`CLAUDE.md` §9; ownership map + frozen contracts: ADR 0029.

## The ritual

```bash
git pull --rebase origin main          # at session START, and again before merging
# ... work; commit (Conventional Commits, one logical change per commit) ...
git push origin line/<X>               # branch CI: test (lts), test (1), format, python
# `docs` does NOT run on branches by design (gh-pages deploy race) → build it locally instead
# green? integrate:
git switch main && git pull && git merge --no-ff line/<X> && git push origin main
git switch line/<X>                    # back to your line
```

**Merge at every milestone, never hoard** — a stale branch is the only real conflict source left. `test (pre)`
is `continue-on-error` and currently red for unrelated Julia-prerelease churn; don't chase it.

## Where each artifact goes (this is what keeps merges conflict-free)

| Kind | Destination |
|---|---|
| Narrative / what happened | `lines/<X>/JOURNAL.md` (append) |
| Durable line state + the **NEXT handoff** | `lines/<X>/STATE.md` |
| Changelog entry | a **NEW** `changelog.d/<X>-<slug>.md` fragment — **never edit `CHANGELOG.md` from a line** |
| A decision | an ADR from **your block** (S 0030–0049 · M 0050–0069 · E 0070–0079 · O 0080–0089) + a row in **your** subsection of `docs/decisions/README.md` |
| Cross-cutting `[VERIFIED]` fact | `MEMORY.md` (shared, additive only) |

`CHANGELOG.md`, the shared `MEMORY.md`, `Project.toml`, the root `JOURNAL.md` (= the integration journal) and
cross-cutting ADRs are **integrator-owned** (the `main` worktree). Never edit another line's exclusive path —
raise an **integration point** instead (note it in both lines' STATE.md and land both sides together).

## ⚠️ The handoff — do this BEFORE the session ends or context runs low

**Refresh the `## NEXT — start here` block in `lines/<X>/STATE.md` and commit it.** The `SessionStart` hook
replays that block verbatim into the next session, so it *is* the handoff. Make it a concrete next action
(command + gate), not "continue where I left off". A session that ends without refreshing it has silently
broken the chain — this is the single most important line in this skill.

## SLURM + scratch under parallel lines

- **Tag every job with your line prefix**: `scripts/run_tests_slurm.sh S-suite`,
  `scripts/sbatch_python.sh M-soil scripts/foo.py` — keeps `squeue` and `logs/<tag>.<jobid>.out` attributable
  (each worktree has its own gitignored `logs/`).
- Write only to `/p/tmp` paths your line created; other lines' artifacts are **read-only**. Version artifacts
  instead of overwriting them in place (the S→M contract depends on this).

## Pre-push checklist (mirror the 5 CI gates locally)

1. **Julia tests** — `julia-test` skill: `rm -f test/Manifest.toml`, then the CI-faithful suite **on SLURM**
   (`scripts/run_tests_slurm.sh <X>-suite`) — never a login-node `Pkg.test()` (hook-blocked; it also dies with
   the session). Green = 0 fail (broken are OK). Separate worktrees mean lines can run this concurrently.
2. **format** — Runic 1.7 `--check` clean over `src test ext scripts` (see `julia-test`; never pipe the check
   to `tail`/`grep` — that masks the exit code).
3. **docs** — build it **locally**, since `docs` CI does not run on line branches:
   `DOCS_LINKCHECK=false julia --project=docs docs/make.jl`; `gen_diagrams.jl --check` clean. New exports need
   docstrings (`checkdocs=:exports`).
4. **python** (only if `python/` changed) — inside `python/`: `uv run ruff check .` + `uv run ruff format
   --check .` + `uv run pytest`.
5. **Baselines/opt-in** — no committed ReferenceTests baseline moved unless the change is a deliberate
   physics change (and you noted which baseline moved and why). New physics defaults byte-identical.

## Commit

- End every commit message with the trailer in `CLAUDE.md` §5 — currently:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```
  (Match what the existing history uses — `git log -1 --format=%b | tail -1` — so the trailer stays consistent;
  `CLAUDE.md` §5 is the source of truth if they disagree.)
- Follow the repo's message style: `type(scope): summary` (e.g. `feat(fdiff): …`, `docs: …`), then a body
  explaining *why*, and reference the ADR / phase where relevant.
- Push: `git push origin line/<X>` from a line worktree (remote
  `git@github-esm:rimajj/LPJmLFIT_Emulator.git`, SSH alias, deploy key — no manual auth). GitHub HTTPS is
  blocked on the cluster; SSH works.
- Commits show **"Unverified"** on GitHub by design (locally `G`-signed; owner declined enforcement).
  Don't chase it.

## Check CI status — `gh` is NOT reliably on PATH; use the REST API

```bash
TOKEN=$(python3 -c "import yaml;print(yaml.safe_load(open('/home/jamirp/.config/gh/hosts.yml'))['github.com']['oauth_token'])")
R=rimajj/LPJmLFIT_Emulator
curl -s -H "Authorization: token $TOKEN" https://api.github.com/repos/$R/commits/<sha>/check-runs
# also: /commits/<sha>/status  /actions/runs?head_sha=<sha>  /actions/runs/<id>/jobs  /actions/jobs/<id>/logs
```

**Required checks:** `test (lts)` and `test (1)` only. `test (pre)` is `continue-on-error` (allowed to
fail on Julia-prerelease churn); `test (macOS, lts)` is a non-required extra. **Never merge on a red
required check.**

## End-of-session retrospective (do before wrapping, not just before a commit)

Ask: **"what did this session learn that a future session would otherwise re-derive, and where does it
go?"** Route each item (CLAUDE.md §8): procedure→skill (prefer updating one), env gotcha→CLAUDE.md,
decision→ADR **from your block**, durable line state→`lines/<X>/STATE.md`, cross-cutting fact→`MEMORY.md`,
narrative→`lines/<X>/JOURNAL.md`. Capture minimally in the moment.
**Then do the handoff** (refresh `## NEXT`, above) — that is not optional.
Run `consolidate-memory` every ~5 sessions: on your `lines/<X>/STATE.md` as line housekeeping, and on the
shared `MEMORY.md` only as an **integrator** action from the `main` worktree.

## When CI is red with the test tree unchanged

Suspect a **dependency bump** — manifests are git-ignored so every CI run re-resolves to newest-allowed
deps. Diff the `Enzyme vX.Y.Z` (etc.) line in the last-green vs first-red job logs and tighten `[compat]`
(this is exactly how the Enzyme 0.13.189 regression turned CI red with no code change).
