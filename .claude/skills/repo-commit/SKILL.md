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
INT=/p/projects/open/Jamir/esm_land_emulator   # integration worktree; `main` is checked out HERE

git pull --rebase origin main          # at session START, and again before merging
# ... work; commit (Conventional Commits, one logical change per commit) ...
git push --force-with-lease origin line/<X>    # NOT a plain push (the rebase rewrote pushed commits)
# branch CI on that sha: test (lts), test (1), format, python.
# `docs` does NOT run on branches by design (gh-pages deploy race) → build it locally instead.
# green? integrate — WITHOUT switching branches in your worktree:
flock "$INT/.git/esm-integrate.lock" bash -eu -c '
  git -C "$0" pull --ff-only origin main
  git -C "$0" merge --no-ff --no-edit "origin/line/$1"
  git -C "$0" push origin main
' "$INT" <X>
# finally: check main's OWN latest CI run.
```

**The five traps (all were wrong in the first draft of this protocol; fixed 2026-07-28 after an adversarial review):**
1. **`git switch main` FAILS in a line worktree** — `fatal: 'main' is already used by worktree at …` (exit 128),
   because `main` is permanently checked out in `$INT`. Use `git -C "$INT"`. There is no "switch back" step.
   Never reach for `git switch --ignore-other-worktrees` or `git checkout -B main` to get around it.
2. **Plain `git push` is rejected after the mandated rebase** (non-fast-forward), and git's hint leads to
   `git pull --no-rebase`, which **duplicates every rebased commit** into a self-merge. Use
   `--force-with-lease` (safe: one session per line, ADR 0028).
3. **Merge `origin/line/<X>`** so the sha that lands is the sha CI verified — a pre-rebase green verdict does
   not transfer, and branch CI takes ~10 min, plenty of time for a sibling `main` push to force another rebase.
4. **`flock`** the integration worktree: it is the last shared checkout, and unserialised
   `pull`/`merge`/`push` from four lines reintroduces the contention worktrees exist to prevent.
5. **Green branch ≠ green main.** `format`, `docs`, `python`, Aqua and JET are whole-package gates and `docs`
   never ran on your branch. Check **main's newest** run after merging — GitHub keeps only one *pending* run per
   branch, so a quick follow-up push can cancel an intermediate `main` verdict (observed twice on 2026-07-27/28).

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

**Refreshing is not appending — DELETE the superseded predictions.** When a milestone closes, the handoff still
contains the *expectations* you wrote before measuring, and the next session reads them as current guidance. Hit
for real on 2026-07-28: after the ADR-0030 re-measurement, line S's own `## NEXT` still said "ADR 0031 expects
pooled KS to WORSEN", "evidence FOR S3", "expect Wooddens 0.694 → ~0.923" and "S3 the leading hypothesis" —
every one falsified by the run that had just finished. So, before committing the handoff:
- **Strike any "expect / should / this will probably" sentence whose measurement has landed**, and replace it
  with the outcome. Predictions and results must never sit side by side undated.
- **Collapse completed steps into a short audit trail** (job ids, artifact paths, gotchas) and put the numbers in
  `## Status`. Keep provenance, drop the instructions.
- **Say why the next action was NOT started**, if it wasn't — "not started because a half-executed X leaves
  regenerated golden fixtures in the worktree" is actionable; silence reads as an oversight.
- `grep` the block for your own hedges before committing; that is how the above were caught.

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
- **`slurm-guard` can false-positive on the COMMIT MESSAGE (bit on 2026-07-28).** The `PreToolUse` guard
  pattern-matches the whole Bash command, so **any heredoc text** that merely *mentions* the suite runner or
  "test suite" is blocked as if you were running the suite on the login node — this hits commit messages AND
  journal entries you append with a heredoc. Fix: put the text in a file
  and `git commit -F <file>` (write the file with the Write tool, so the text never appears in the command),
  or prefix `ALLOW_LOGIN_HEAVY=1` if you are certain. Don't reword the message to appease the matcher.
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
(this is exactly how the Enzyme 0.13.189 regression turned CI red with no code change, and how **JET 0.12.0**
broke `test (1)` on 2026-07-28 by removing `target_defined_modules`).

Getting from "which check is red" to the failing line — `curl` must follow the log redirect (`-sL`):
```bash
ID=$(curl -s -H "Authorization: token $TOKEN" \
  "https://api.github.com/repos/$R/commits/<sha>/check-runs" \
  | python3 -c "import sys,json;print([r['id'] for r in json.load(sys.stdin)['check_runs'] if r['name']=='test (1)'][0])")
curl -sL -H "Authorization: token $TOKEN" "https://api.github.com/repos/$R/actions/jobs/$ID/logs" -o /tmp/ci.log
grep -nE "Test Failed|Error During Test|errored|Some tests did not pass" /tmp/ci.log | tail
grep -oE "<Pkg> v[0-9.]+" /tmp/ci.log | sort -u      # the resolved version, to compare against last-green
```
**A red check on a diff that cannot explain it is a dep bump until proven otherwise** — check whether `main`'s
own latest run is still green (it often is, simply because it predates the release), which tells you the break
will hit every branch on its next push and is not yours. `[compat]` is **integrator-only** (ADR 0029), so a
line records the one-line pin as a blocker rather than applying it.
