---
status: "accepted"
date: 2026-07-15
deciders: "Jamir Priesner (owner)"
consulted: "ENGINEERING_STANDARDS.md §1/§8"
informed: "CI/CD, docs deploy"
---

# Authenticate to GitHub from the HPC via a repository SSH deploy key

## Context and Problem Statement

The agent works on a shared PIK HPC and must push to the owner's **private** GitHub repo and deploy
docs, without leaking credentials into reflogs, CI logs, or shared storage. What auth mechanism? See
ENGINEERING_STANDARDS §8.

## Decision Drivers

- **Least privilege** — bound to exactly one repo.
- No secret ever embedded in a `git remote` URL (leaks to reflogs/CI logs).
- Works non-interactively in scheduler jobs; supports signed commits and docs deploy.

## Considered Options

- **Repository SSH deploy key** with write access (bound to one repo), via an `ssh-agent` /
  `~/.ssh/config` host alias.
- **Fine-grained PAT** scoped to the single repo (Contents: read/write, short expiry), injected via a
  credential helper.
- **Org-wide / classic PAT** (rejected outright).

## Decision Outcome

Chosen: **repository SSH deploy key** as the primary mechanism (a fine-grained single-repo PAT is the
acceptable alternative). The private key is stored `chmod 600` and used through an `ssh-agent` /
`~/.ssh/config` host alias — the working tree already uses the alias
`git@github-esm:rimajj/LPJmLFIT_Emulator.git`. Docs deploy uses a `DOCUMENTER_KEY` SSH deploy key
(from `DocumenterTools.genkeys`); `GITHUB_TOKEN` with `contents: write` also works for same-repo
deploys in Actions. Never put a token in a remote URL.

### Consequences

- Good: least privilege (one repo); no token in URLs/logs; non-interactive; supports SSH commit
  signing for the "Verified" badge.
- Good: `DOCUMENTER_KEY` cleanly separates docs-deploy auth from push auth.
- Bad: key management overhead (rotation, `chmod 600`, host-alias config) on shared HPC storage.
- Bad: keys/tokens must be `.gitignore`-excluded (they are) and never committed.

## More Information

Branch protection assumed on `main` (require PR + green `test`/`format`/`docs`/coverage, signed
commits, no force-push; ENGINEERING_STANDARDS §1). Secret files are blocked by the repo `.gitignore`
(`*.pem`, `*.key`, `id_ed25519*`, `*token*`, …).
