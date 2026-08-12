#!/usr/bin/env python3
"""Split a MULTI-CELL `build_estab_eligibility.py` CSV into the per-site fixtures the response arm reads.

WHY THIS EXISTS (line S, 2026-08-12, ADR 0171's handoff item 1)
--------------------------------------------------------------
`scripts/build_estab_eligibility.py`'s `CSV_OUT` **appends every selected cell into ONE file**, because
building several sites out of one 12 GB `.clm` read is the right economy — but the result interleaves cells
and both scenarios, while `scripts/trait_mortality_arm_probe.jl` reads exactly one committed file per site
(`test/testitems/references/S_estab_eligibility_<site>.csv`, historic rows first, then ssp370).

The split was done BY HAND for the first two extra cells (ADR 0171, jobs 1761401/1761402), which is precisely
the "did the same multi-step thing twice" trigger in CLAUDE.md §8. It is a header-preserving filter with three
places to get it wrong, so it is a script now:

  1. the comment block must be carried over VERBATIM — it is the file's own regeneration recipe and the
     `temp_min20` != `tas_cold_month` warning (ADR 0170 §3), and a hand-split that drops it leaves a
     generated fixture with no provenance;
  2. the row order is load-bearing — the probe indexes the series as `ser[clamp(s.year + 1, ...)]` over a
     single concatenated 81 + 81 sequence, so historic MUST precede ssp370 and each block MUST be
     year-ascending (a multi-cell build emits cells interleaved WITHIN a year);
  3. the cell filter must be on the `cell` COLUMN, not on a row stride — the number of cells per year is a
     property of the build, not of the file.

Env:
  HIST      the historic multi-cell CSV      (required)
  SSP       the ssp370 multi-cell CSV        (required)
  SITES     comma-separated names in M_cells.csv (default: every name whose cell appears in BOTH inputs)
  PROV      a provenance sentence appended to the header (e.g. "split out of a two-cell build (jobs A/B).")
  OUTDIR    default test/testitems/references
  DRYRUN    1 = report what would be written and exit

Run:
  HIST=/p/tmp/jamirp/emulator_global/S_elig_sah_ibe_hist.csv \
  SSP=/p/tmp/jamirp/emulator_global/S_elig_sah_ibe_ssp.csv \
  SITES=semiarid_sahel,mediterranean_iberia \
  PROV="split out of a two-cell build (jobs 1761997/1761998)." \
    python3 scripts/split_estab_eligibility_percell.py
"""

from __future__ import annotations

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFDIR = os.path.join(REPO, "test", "testitems", "references")
CELLS_CSV = os.path.join(REFDIR, "M_cells.csv")


def read_block(path: str) -> tuple[list[str], str, list[str]]:
    """Return (comment_lines, header_line, data_lines) — the file's own three parts, unparsed."""
    comments: list[str] = []
    header = ""
    data: list[str] = []
    with open(path) as fh:
        for ln in fh:
            ln = ln.rstrip("\n")
            if not ln:
                continue
            if ln.startswith("#"):
                (comments if not header else data).append(ln)
            elif not header:
                header = ln
            else:
                data.append(ln)
    if not header:
        raise SystemExit(f"FATAL: no header row found in {path}")
    return comments, header, data


def site_cells() -> dict[str, int]:
    with open(CELLS_CSV) as fh:
        lines = [ln.rstrip("\n") for ln in fh if not ln.startswith("#") and ln.strip()]
    cols = lines[0].split(",")
    iname, icell = cols.index("name"), cols.index("cell")
    return {r.split(",")[iname]: int(r.split(",")[icell]) for r in lines[1:]}


def main() -> int:
    hist_p = os.environ.get("HIST", "").strip()
    ssp_p = os.environ.get("SSP", "").strip()
    if not hist_p or not ssp_p:
        raise SystemExit("FATAL: set HIST and SSP to the two multi-cell CSVs")
    outdir = os.environ.get("OUTDIR", REFDIR)
    prov = os.environ.get("PROV", "").strip()
    dry = os.environ.get("DRYRUN", "0") == "1"

    hc, hh, hd = read_block(hist_p)
    sc, sh, sd = read_block(ssp_p)
    if hh != sh:
        raise SystemExit(f"FATAL: the two inputs have different headers:\n  {hh}\n  {sh}")
    cols = hh.split(",")
    i_scen, i_cell, i_year = cols.index("scenario"), cols.index("cell"), cols.index("year")

    def by_cell(rows: list[str], want_scen: str) -> dict[int, list[tuple[int, str]]]:
        out: dict[int, list[tuple[int, str]]] = {}
        for r in rows:
            f = r.split(",")
            if f[i_scen] != want_scen:
                raise SystemExit(
                    f"FATAL: expected only scenario {want_scen!r} rows but found {f[i_scen]!r}. "
                    "Pass the historic and ssp370 builds as SEPARATE files."
                )
            out.setdefault(int(f[i_cell]), []).append((int(f[i_year]), r))
        return out

    H, S = by_cell(hd, "historic"), by_cell(sd, "ssp370")
    reg = site_cells()
    both = sorted(set(H) & set(S))
    if os.environ.get("SITES", "").strip():
        sites = [s.strip() for s in os.environ["SITES"].split(",") if s.strip()]
    else:
        sites = [n for n, c in reg.items() if c in both]
    if not sites:
        raise SystemExit(f"FATAL: no site resolved. cells in both inputs: {both}")

    print(f"== header  : {len(cols)} columns")
    print(f"== historic: {len(hd)} rows over cells {sorted(H)}")
    print(f"== ssp370  : {len(sd)} rows over cells {sorted(S)}")
    print(f"== sites   : {', '.join(sites)}")

    for site in sites:
        if site not in reg:
            raise SystemExit(f"FATAL: SITE {site!r} is not a name in {os.path.relpath(CELLS_CSV, REPO)}")
        cell = reg[site]
        if cell not in H or cell not in S:
            raise SystemExit(
                f"FATAL: {site} is cell {cell}, which is not in BOTH inputs "
                f"(historic {cell in H}, ssp370 {cell in S})"
            )
        hrows = [r for _, r in sorted(H[cell])]
        srows = [r for _, r in sorted(S[cell])]
        # The probe holds the LAST value past the end of the series, so a short block silently
        # mis-aligns the gate against every later simulation year (skill: slow-drf-pipeline, item 1).
        for scen, rows in (("historic", hrows), ("ssp370", srows)):
            yrs = [int(r.split(",")[i_year]) for r in rows]
            if yrs != list(range(min(yrs), max(yrs) + 1)):
                raise SystemExit(f"FATAL: {site} {scen} years are not a dense ascending run: {yrs[:5]}...")
            print(f"   {site:24s} {scen:8s} {len(rows):3d} yr  {min(yrs)}-{max(yrs)}")
        out = os.path.join(outdir, f"S_estab_eligibility_{site}.csv")
        body = hc[:]
        line = f"# THIS FILE: cell {cell} ({site}) only"
        body.append(f"{line}, {prov}" if prov else f"{line}.")
        text = "\n".join(body + [hh] + hrows + srows) + "\n"
        if dry:
            print(f"   DRYRUN would write {out}  ({len(hrows) + len(srows)} data rows)")
            continue
        with open(out, "w") as fh:
            fh.write(text)
        print(f"== wrote {os.path.relpath(out, REPO)}  ({len(hrows) + len(srows)} data rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
