---
name: repo-commit
description: Commit/push discipline for the LPJmL-FIT emulator — main-only workflow (ADR 0013), the pre-push checklist against the 5 CI gates, the commit trailer, how to check CI via the GitHub REST API (gh not on PATH), and the "Unverified" note. Use whenever committing, pushing, or checking CI for this repo.
---

# repo-commit — main-only commit & push

**Commit and push to main as you go** — full autonomy (`STEERING_PROMPT.md`); no owner sign-off is needed
or expected. Work on `main` directly (ADR 0013 — no branches, PRs, or branch protection; owner declined).
CI on `push:main` is a smoke alarm: run the equivalent checks locally first, fix-forward if red — that
automated discipline is the safety net, not a human gate.

## Pre-push checklist (mirror the 5 CI gates locally)

1. **Julia tests** — `julia-test` skill: `rm -f test/Manifest.toml` then `Pkg.test()` on the **login
   node**. Green = 0 fail (broken are OK).
2. **format** — Runic 1.7 `--check` clean over `src test ext scripts` (see `julia-test`).
3. **docs** — `DOCS_LINKCHECK=false julia --project=docs docs/make.jl` builds; `gen_diagrams.jl --check` clean.
4. **python** (only if `python/` changed) — inside `python/`: `uv run ruff check .` + `uv run ruff format
   --check .` + `uv run pytest`.
5. **Baselines/opt-in** — no committed ReferenceTests baseline moved unless the change is a deliberate
   physics change (and you noted which baseline moved and why). New physics defaults byte-identical.

## Commit

- End every commit message with:
  ```
  Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
  ```
- Follow the repo's message style: `type(scope): summary` (e.g. `feat(fdiff): …`, `docs: …`), then a body
  explaining *why*, and reference the ADR / phase where relevant.
- Push: `git push` (remote `git@github-esm:rimajj/LPJmLFIT_Emulator.git`, SSH alias, deploy key — no
  manual auth). GitHub HTTPS is blocked on the cluster; SSH works.
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
decision→ADR, durable state→MEMORY.md, narrative→JOURNAL.md. Capture minimally in the moment. Run
`consolidate-memory` (reshape MEMORY.md to durable-state-only under its cap; archive what you remove)
every ~5 sessions.

## When CI is red with the test tree unchanged

Suspect a **dependency bump** — manifests are git-ignored so every CI run re-resolves to newest-allowed
deps. Diff the `Enzyme vX.Y.Z` (etc.) line in the last-green vs first-red job logs and tighten `[compat]`
(this is exactly how the Enzyme 0.13.189 regression turned CI red with no code change).
