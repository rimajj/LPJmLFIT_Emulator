#!/usr/bin/env python3
"""Append ONE response seed-ensemble to the committed cross-cell reference, identity columns and all.

WHY THIS EXISTS (line S, 2026-08-12)
------------------------------------
`scripts/summarize_response_seed_ensemble.py` writes the per-seed rows (`CSV=`), but its column set is the
single-ensemble one — it has no idea which cell, which artifact pair, or which ssp-boundary basis produced
the logs, because none of that is in its own scope. The committed cross-cell reference
`test/testitems/references/S_recruit_multicell_seed_ensembles.csv` therefore carries FIVE extra identity
columns in front, which ADR 0171 added BY HAND. Doing that a second time (the Sahel and Iberia ensembles) is
the CLAUDE.md §8 "same multi-step thing twice" trigger, and getting it wrong is silent: a row whose `site`
says one cell while its `log` column points at another is unfalsifiable after the logs age out.

So: this reads the logs through the summarizer's OWN parser (imported, never re-implemented — ADR 0031's
one-definition rule), prefixes the identity, and appends. It is idempotent — a `tag` already present is
refused rather than duplicated, because a duplicated ensemble silently halves every SEM computed off the file.

It also CROSS-CHECKS the identity it is told against what the logs themselves report: `n_init`/`age0` must
match the site's own committed `M_cells.csv` row, and the `drf` basename must match ARTIFACT. That is what
makes a mislabelled ensemble a hard error instead of a footnote.

Env: GLOB (required, e.g. 'logs/S-rbSAH*.out') · TAG (required, the run tag, e.g. rbSAH) · SITE (a name in
     M_cells.csv) · ARTIFACT (e.g. pooled_w20_t8) · SSP_BASIS (trained|untrained; ADR 0171 §2) ·
     REF (the committed csv) · FORCE=1 (allow re-appending an existing tag — it DELETES the old rows first)
Run:
  GLOB='logs/S-rbSAH*.out' TAG=rbSAH SITE=semiarid_sahel ARTIFACT=pooled_w20_t8 SSP_BASIS=trained \
    python3 scripts/append_response_ensemble_reference.py
"""

from __future__ import annotations

import glob as globmod
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFDIR = os.path.join(REPO, "test", "testitems", "references")
sys.path.insert(0, os.path.join(REPO, "scripts"))
from summarize_response_seed_ensemble import parse  # noqa: E402 — the ONE parser (ADR 0031)

ID_COLS = ["tag", "site", "cell", "artifact", "ssp_boundary_basis"]
SUM_COLS = ["log", "arm", "drf", "seed", "n_init", "age0", "score_window", "wd_ctl_hist",
            "wd_arm_hist", "d_hist", "wd_ctl_ssp", "wd_arm_ssp", "d_ssp", "R_ctl",
            "R_arm", "interaction", "hard_kills", "shortfall_years", "n_merge",
            "bnd_live", "estab_draws", "inherit_pct", "sb_weight", "d_drawn_wd"]
COLS = ID_COLS + SUM_COLS


def site_row(site: str) -> dict:
    with open(os.path.join(REFDIR, "M_cells.csv")) as fh:
        lines = [ln.rstrip("\n") for ln in fh if not ln.startswith("#") and ln.strip()]
    cols = lines[0].split(",")
    for ln in lines[1:]:
        f = ln.split(",")
        if f[cols.index("name")] == site:
            return dict(zip(cols, f, strict=False))
    raise SystemExit(f"FATAL: SITE {site!r} is not a name in M_cells.csv")


def main() -> int:
    g = os.environ.get("GLOB", "").strip()
    tag = os.environ.get("TAG", "").strip()
    site = os.environ.get("SITE", "").strip()
    artifact = os.environ.get("ARTIFACT", "pooled_w20_t8").strip()
    ssp_basis = os.environ.get("SSP_BASIS", "trained").strip()
    ref = os.environ.get("REF", os.path.join(REFDIR, "S_recruit_multicell_seed_ensembles.csv"))
    force = os.environ.get("FORCE", "0") == "1"
    if not g or not tag or not site:
        raise SystemExit("FATAL: set GLOB, TAG and SITE")

    sr = site_row(site)
    cell = int(sr["cell"])
    rows = [r for r in (parse(f) for f in sorted(globmod.glob(g))) if r]
    if not rows:
        raise SystemExit(f"FATAL: no complete logs matched {g!r} (a running/failed job has no 'exit=0' tail)")
    rows.sort(key=lambda r: (r["seed"] or 0))
    print(f"== {len(rows)} parsed logs for tag {tag} (site {site}, cell {cell})")

    # ── the cross-checks that make a mislabelled ensemble a hard error ────────────────────────────────
    ni = {r.get("n_init") for r in rows}
    a0 = {r.get("age0") for r in rows}
    if len(ni) != 1 or len(a0) != 1:
        raise SystemExit(f"FATAL: the logs disagree on n_init/age0 ({ni} / {a0}) — this is not ONE ensemble")
    got_ni, got_a0 = float(next(iter(ni))), float(next(iter(a0)))
    want_ni, want_a0 = float(sr["n_init"]), float(sr["age0"])
    if abs(got_ni - want_ni) > 1e-9 or abs(got_a0 - want_a0) > 1e-3:
        raise SystemExit(
            f"FATAL: the logs ran at n_init/age0 = {got_ni}/{got_a0} but {site}'s committed M_cells.csv row "
            f"says {want_ni}/{want_a0}. Either SITE is wrong or the run did not read the per-cell values "
            "(the probe must take them from M_cells.csv at a non-default SITE, never from the artifact meta)."
        )
    drfs = {os.path.basename(str(r.get("drf") or "")) for r in rows}
    if len(drfs) != 1:
        raise SystemExit(f"FATAL: the logs used more than one artifact: {drfs}")
    drf = next(iter(drfs))
    if artifact not in drf:
        raise SystemExit(f"FATAL: ARTIFACT={artifact!r} does not appear in the logs' own artifact {drf!r}")
    bad = [r for r in rows if any(float(r.get(c) or 0) > 0
                                 for c in ("hard_kills", "shortfall_years", "n_merge"))]
    print(f"   n_init/age0 {got_ni}/{got_a0} match M_cells.csv · artifact {drf} · "
          f"{len(bad)} row(s) fail the ADR-0048/0101 usability preconditions")

    with open(ref) as fh:
        text = fh.readlines()
    head = [ln for ln in text if ln.startswith("#")]
    hdr = next(ln for ln in text if ln.startswith("tag,")).rstrip("\n")
    if hdr.split(",") != COLS:
        raise SystemExit(f"FATAL: {os.path.basename(ref)}'s header is not the expected column set:\n{hdr}")
    body = [ln.rstrip("\n") for ln in text if not ln.startswith("#") and not ln.startswith("tag,") and ln.strip()]
    existing = {ln.split(",")[0] for ln in body}
    if tag in existing:
        if not force:
            raise SystemExit(
                f"FATAL: tag {tag!r} is already in {os.path.basename(ref)} "
                f"({sum(1 for ln in body if ln.split(',')[0] == tag)} rows). Appending would duplicate an "
                "ensemble and silently halve every SEM computed off this file. Re-run with FORCE=1 to "
                "REPLACE those rows."
            )
        body = [ln for ln in body if ln.split(",")[0] != tag]
        print(f"   FORCE=1: replaced the existing {tag} rows")

    new = []
    for r in rows:
        ident = [tag, site, str(cell), artifact, ssp_basis]
        new.append(",".join(ident + ["" if r.get(c) is None else str(r[c]) for c in SUM_COLS]))
    with open(ref, "w") as fh:
        fh.writelines(head)
        fh.write(hdr + "\n")
        for ln in body + new:
            fh.write(ln + "\n")
    tags = sorted({ln.split(",")[0] for ln in body + new})
    print(f"== {os.path.relpath(ref, REPO)}: +{len(new)} rows, {len(body) + len(new)} total, "
          f"{len(tags)} ensembles ({', '.join(tags)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
