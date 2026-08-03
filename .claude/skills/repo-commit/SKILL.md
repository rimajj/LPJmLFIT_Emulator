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

**A STALE `index.lock` in the integration worktree blocks EVERY line — clear it, but prove it is stale first
(line S, 2026-07-30).** The merge died with `Unable to create '<INT>/.git/index.lock': File exists`, and git's
own advice ("a git process may have crashed earlier: remove the file manually") is right here but must be
earned, because removing a LIVE lock can corrupt the shared index. Check all four, then clear it INSIDE the
`flock` so a protocol-following sibling cannot race you:
```bash
INT=/p/projects/open/Jamir/esm_land_emulator
[ ! -s "$INT/.git/index.lock" ]                     # 1. zero bytes (a live git writes its pid//content)
find "$INT/.git/index.lock" -mmin +30               # 2. older than any plausible in-flight operation
pgrep -a -u "$USER" git                             # 3. no git process at all (beware: `ps|grep git` matches
                                                    #    your OWN grep — use pgrep, or a [g]it bracket class)
git -C "$INT" diff --stat HEAD; git -C "$INT" ls-files --others --exclude-standard   # 4. tree is clean
```
Observed: 0 bytes, 3 h old, no process, clean tree — an interrupted `pull`, and `main` was left behind
`origin/main`. Leaving it costs every line its merge path, so this is worth fixing rather than waiting out.

**Two more, learned in anger on 2026-07-28 (line S, S1c):**
6. **NEVER chain the push behind the rebase in one shell command.** `git pull --rebase … ; git push …` looks
   convenient and is a trap: if the rebase stops on a conflict, the branch ref still points at the ORIGINAL tip,
   so the push fires anyway and ships the **un-rebased** commits — reporting success while leaving you mid-rebase.
   Recoverable (resolve, `--continue`, re-push with `--force-with-lease`), but you have then triggered a CI run on
   a sha you are about to replace. Run the rebase, CHECK it finished (`git status` must not say
   "rebase in progress"), then push.
7. **"Shared files are append-only" does NOT prevent a conflict when two lines append to the same SECTION.**
   Line E and line S both appended to the `## Docs` block of `.claude/skills/julia-test/SKILL.md` hours apart and
   the rebase conflicted. The fix is never to drop one side: read both hunks and **keep both contributions** (they
   were complementary — "warm `--project=docs` before submitting to SLURM" and "the diagram alarm needs
   `--project=.`"). Taking `--ours`/`--theirs` on a shared skill silently deletes another line's captured
   knowledge, which is the one thing the capture gate exists to prevent.

**Two more, learned in anger on 2026-07-30 (line S, a documentation session):**
8. **Check `git log origin/line/<X>..HEAD` before assuming the only unpushed commit is yours.** A prior
   session can leave a fully legitimate, already-committed piece of work sitting locally unpushed — nothing
   wrong with the commit itself, just not yet pushed. The routine "N ahead of / M behind `origin/main`" the
   `SessionStart` hook reports does **not** surface this, because it compares against `origin/main`, not
   `origin/line/<X>`. Pushing ships BOTH commits together, which is fine mechanically (same branch, sequential
   sessions, ADR 0028's "one session at a time" model expects exactly this) — but you must recognize whose
   work is whose before reporting "done," not silently take credit for or bury a foreign commit. Observed: a
   full "S2 copula-gap-is-estimator-capacity" diagnosis commit (`Co-Authored-By: Claude Opus 5`) was sitting
   unpushed when an unrelated Sonnet-5 documentation session went to commit — caught only because `git log`
   was checked before push, not assumed clean.
9. **A Workflow/Agent subagent's RETURNED value is not the only thing it did.** A subagent with Bash/Write
   tool access can write side-effect files directly into the shared repo that never pass through the task's
   own review pipeline — a fact-check stage that only inspects the returned string never sees a file the
   agent wrote to disk on the side. Always `git status` after a Workflow run that touched this worktree,
   before trusting "the returned text is the deliverable." Such a file can look like a bonus (real embedded
   figures, in one case) while still failing the task's own hard constraints (it had formulas the
   fact-checked returned text did not, and was missing whole sections) — verify it against the source before
   reusing any part of it, don't just delete it unread and don't just trust it either.

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

**Refreshing is also not REPLACING someone else's handoff — and git will not warn you (`[VERIFIED 2026-08-03]`).**
ADR 0028 says one session per line, but if a second session *is* running in your worktree, the `## NEXT` block
is the single place your edits collide, and a wholesale rewrite of it is a silent data loss:
- Hit for real: two line-S sessions ran on 2026-08-03. Session 2 rewrote `## NEXT` for the ssp370-second-seed
  work (ADR 0041); session 1 then replaced the whole block with its own handoff, **deleting 225 lines** that
  were the only record of how to collect a 2048-task C run and its two chained `afterok` children.
- **Git cannot catch this.** The other session had already *committed*, so the rewrite was a clean
  fast-forward with nothing to merge and no conflict to resolve. `git status` was clean afterwards.
- **Before rewriting `## NEXT`, run `git log --oneline -5 -- lines/<X>/STATE.md`.** If a commit you did not
  write touched it this session, keep both as labelled `### TRACK A/B` subsections under the one `## NEXT`
  header (the hook prints the whole block, so it stays coherent), and put the time-critical track FIRST —
  chained `afterok` children are cancelled silently when their parent dies.
- Two concurrent sessions also race on **ADR numbers**. Both sessions here drafted `0039`; each detected the
  other and moved (to `0040` / `0041`), leaving `0039` unused. That is the correct outcome — `ls
  docs/decisions/` immediately before you name the file, not when you start writing it.
- Same rule for commits: **stage by explicit path, never `git add -A`**, or you sweep the other session's
  in-progress files into your commit.

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

**Confirm it is repo-wide before you touch `main`, then land the pin THERE, not on your branch.** Pull the
same failing job log for a *sibling* line's latest sha: an identical failure on a completely unrelated diff is
the proof. `[VERIFIED 2026-07-28]` JET 0.12.0 failed identically on line/M `693322fa` (docs+tests only) and
line/O `11ef8d89`. Because the file is integrator-owned, the fix belongs on `main` (drive the integration
worktree with `git -C "$INT"` under the `flock`, never `git switch main`); putting it on your branch instead
leaves the other three lines broken and duplicates the change at merge time.

**⚠️ Then expect a CONCURRENT DUPLICATE FIX, and check the merge for a duplicate TOML key.** A repo-wide break
is visible to all four lines at once, so two sessions independently pinned JET the same afternoon
(`47c6407a` from M, `51529464` from E). Git merges two *identical* `[compat]` lines cleanly, but two lines
that differ only in bound or comment merge into **two `JET = …` entries in one `[compat]` table**, which is a
duplicate-key TOML error that reds every job — a worse break than the one being fixed. After any merge that
touched `Project.toml`/`test/Project.toml`, run `grep -n '^<Pkg> = ' test/Project.toml` and confirm exactly one
entry. The narrative conflict shows up in `MEMORY.md` instead (both sides append a TODO in the same list) —
resolve by keeping ONE entry and the newer sibling bullets, not by taking a whole side.
