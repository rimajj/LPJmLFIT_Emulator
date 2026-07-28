# JOURNAL — LINE E (Component E vs observations (P2))

> **Append-only, newest at the bottom.** Narrative for THIS LINE only: what you did, the commands, the
> results, dead ends. Durable state goes to `lines/E/STATE.md` (and its `## NEXT` block — refresh it before
> your session ends); cross-cutting durable facts go to `MEMORY.md`; the story of one change goes to a
> `changelog.d/E-<slug>.md` fragment. Pre-split history for the whole project: the root `JOURNAL.md`.
>
> Entry template:
> ```
> ## YYYY-MM-DD — <short title>  [milestone E<n>]
> - **Goal:**
> - **Did:**
> - **Result / evidence:** (numbers, job ids, gate outcomes)
> - **Decisions:** (ADR NNNN if any)
> - **Next:** (mirror into STATE.md's NEXT block)
> ```

## 2026-07-28 — line created (ADR 0028/0029)
- **Goal:** stand up line E as an independent work line so it can run concurrently with the other lines.
- **Did:** created by the Phase-0 setup session on `main`: branch `line/E` + worktree `wt-E`,
  `lines/E/{STATE.md,JOURNAL.md}`, ADR block assigned, ownership recorded in ADR 0029.
- **Result / evidence:** see the root `JOURNAL.md` Phase-0 entry for the setup evidence.
- **Decisions:** ADR 0028 (branch+worktree per line, supersedes 0013), ADR 0029 (the split + ownership).
- **Next:** the `## NEXT — start here` block in `lines/E/STATE.md`.
