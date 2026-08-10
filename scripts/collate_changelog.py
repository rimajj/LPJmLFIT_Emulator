#!/usr/bin/env python3
"""Collate `changelog.d/<LINE>-<slug>.md` fragments into `CHANGELOG.md` (ADR 0095).

Why this exists: `CHANGELOG.md` is integrator-owned and written by inserting at the top, so two
concurrent work lines editing it produce overlapping hunks in long prose blocks — the worst merge
conflict in this repo (ADR 0029). Fragments removed the *authoring* conflict; this script removes the
*collation* bottleneck, which is what actually rotted (56 fragments accumulated over 13 days because
"the integrator collates at an integration point" named no event that reliably happens).

Usage
-----
    python3 scripts/collate_changelog.py --check      # exit 1 if any fragment is uncollated
    python3 scripts/collate_changelog.py --dry-run    # print the block that would be inserted
    python3 scripts/collate_changelog.py              # collate + delete the fragments

What it does, exactly (deterministic, no network, no git calls):

1. Reads every `changelog.d/*.md` except `README.md`.
2. Splits each fragment on its `### <Category>` headings — most fragments are multi-category, so a
   fragment contributes several chunks.
3. Groups all chunks by category, in CANONICAL_ORDER, and inserts ONE new group of `### <Category>`
   sections immediately after the `## [Unreleased]` heading. That matches the file's existing shape
   (repeated category blocks, newest group at top) and keeps the diff minimal — it deliberately does
   NOT reorganise the existing 1200+ lines.
4. Deletes the collated fragments. Staging/committing is the caller's job.

A heading may carry a parenthetical qualifier, e.g.
`### Verdict (497 936 tower steps, 4 sites — full numbers in ADR 0072)`. The qualifier is preserved as
an italic lead-in line above that chunk's bullets, so grouping never discards it.

Ordering within a category is by fragment filename: deterministic and reviewable. Running with no
fragments present is a no-op, so the script is idempotent.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Derive the repo root from THIS file — never hard-code an absolute path, or running from a line
# worktree silently writes into the integrator worktree (CLAUDE.md §9 trap 6).
REPO = Path(__file__).resolve().parent.parent
FRAGMENT_DIR = REPO / "changelog.d"
CHANGELOG = REPO / "CHANGELOG.md"
UNRELEASED = "## [Unreleased]"

# The six Keep-a-Changelog categories, then the extra ones this project already uses in CHANGELOG.md
# (`### Validation`, `### Notes`) and in fragments. Extending this list is a deliberate act: an
# unknown category is an error, not a silent passthrough, so a typo cannot invent a section.
CANONICAL_ORDER = [
    "Added",
    "Changed",
    "Fixed",
    "Deprecated",
    "Removed",
    "Security",
    "Documentation",
    "Validation",
    "Verified",
    "Measured",
    "Verdict",
    "Gates",
    "Notes",
]
ALIASES = {"Documented": "Documentation"}

HEADING_RE = re.compile(r"^###\s+(.+?)\s*$")
# Split a heading into its base category and an optional trailing parenthetical qualifier.
QUALIFIED_RE = re.compile(r"^(?P<base>[A-Za-z]+)\s*\((?P<qual>.+)\)$")


class CollationError(RuntimeError):
    pass


def fragment_paths() -> list[Path]:
    if not FRAGMENT_DIR.is_dir():
        return []
    return sorted(p for p in FRAGMENT_DIR.glob("*.md") if p.name != "README.md")


def normalise(heading: str, source: Path) -> tuple[str, str | None]:
    """('Verdict (4 sites)', path) -> ('Verdict', '4 sites'); validates against CANONICAL_ORDER."""
    qualifier = None
    base = heading.strip()
    m = QUALIFIED_RE.match(base)
    if m:
        base, qualifier = m.group("base"), m.group("qual").strip()
    base = ALIASES.get(base, base)
    if base not in CANONICAL_ORDER:
        raise CollationError(
            f"{source.name}: unknown changelog category '{heading}'.\n"
            f"  Allowed: {', '.join(CANONICAL_ORDER)}\n"
            f"  Fix the fragment, or add the category to CANONICAL_ORDER deliberately."
        )
    return base, qualifier


def parse_fragment(path: Path) -> list[tuple[str, str | None, list[str]]]:
    """-> [(category, qualifier, body_lines)] in the order they appear in the fragment."""
    chunks: list[tuple[str, str | None, list[str]]] = []
    current: tuple[str, str | None, list[str]] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = HEADING_RE.match(raw)
        if m:
            if current is not None:
                chunks.append(current)
            base, qual = normalise(m.group(1), path)
            current = (base, qual, [])
        elif current is not None:
            current[2].append(raw)
    if current is not None:
        chunks.append(current)
    if not chunks:
        raise CollationError(
            f"{path.name}: no '### <Category>' heading — see changelog.d/README.md for the format."
        )
    return chunks


def strip_blanks(lines: list[str]) -> list[str]:
    out = list(lines)
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


def build_block(paths: list[Path]) -> tuple[str, dict[str, int]]:
    """Group every fragment's chunks by category and render the markdown block to insert."""
    grouped: dict[str, list[str]] = {c: [] for c in CANONICAL_ORDER}
    counts: dict[str, int] = {}
    for path in paths:
        for category, qualifier, body in parse_fragment(path):
            body = strip_blanks(body)
            if not body:
                continue
            piece: list[str] = []
            if qualifier:
                piece.append(f"*{qualifier}:*")
                piece.append("")
            piece.extend(body)
            grouped[category].append("\n".join(piece))
            counts[category] = counts.get(category, 0) + 1

    parts: list[str] = []
    for category in CANONICAL_ORDER:
        if not grouped[category]:
            continue
        parts.append(f"### {category}")
        parts.append("")
        parts.append("\n\n".join(grouped[category]))
        parts.append("")
    return "\n".join(parts).rstrip() + "\n", counts


def insert_into_changelog(block: str) -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.rstrip() == UNRELEASED:
            break
    else:
        raise CollationError(f"{CHANGELOG.name}: no '{UNRELEASED}' heading found.")
    # Insert after the heading and the blank line that follows it.
    at = i + 1
    while at < len(lines) and not lines[at].strip():
        at += 1
    new = lines[:at] + [block, "\n"] + lines[at:]
    CHANGELOG.write_text("".join(new), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if fragments are uncollated")
    ap.add_argument("--dry-run", action="store_true", help="print the block, change nothing")
    args = ap.parse_args(argv)

    paths = fragment_paths()

    if args.check:
        if not paths:
            print("changelog.d: clean — no uncollated fragments.")
            return 0
        by_line: dict[str, int] = {}
        for p in paths:
            by_line[p.name.split("-", 1)[0]] = by_line.get(p.name.split("-", 1)[0], 0) + 1
        print(f"changelog.d: {len(paths)} uncollated fragment(s).")
        print("  by line: " + ", ".join(f"{k}={v}" for k, v in sorted(by_line.items())))
        for p in paths:
            print(f"    {p.name}")
        print("\nCollate them with:  python3 scripts/collate_changelog.py")
        print("This runs on `main` after a line merge — see CLAUDE.md §9 and the repo-commit skill.")
        return 1

    if not paths:
        print("changelog.d: nothing to collate.")
        return 0

    block, counts = build_block(paths)

    if args.dry_run:
        print(block)
        print(f"--- would collate {len(paths)} fragment(s) into {sum(counts.values())} chunk(s) ---")
        for c in CANONICAL_ORDER:
            if counts.get(c):
                print(f"  {c}: {counts[c]}")
        return 0

    insert_into_changelog(block)
    for p in paths:
        p.unlink()
    print(f"Collated {len(paths)} fragment(s) -> {CHANGELOG.name} ({sum(counts.values())} chunks).")
    for c in CANONICAL_ORDER:
        if counts.get(c):
            print(f"  {c}: {counts[c]}")
    print("Fragments deleted. Review `git diff` and commit both changes together.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CollationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
