#!/usr/bin/env python
"""Does the rung-2 demography hook's roster dump agree with the C's OWN ``ind`` output?

The correctness gate for the observation half of the rung-2 harness (the opt-in
``LPJ_RUNG2_DIR`` hook in ``patches/lpjmlfit_rung2_demography_hook.patch``).  Both the dump
and the ``ind`` table are written by the same run, so they describe the same trees in the
same trajectory — any disagreement is the hook reading the wrong field, not stochasticity.

What is compared
----------------
Only the ``post`` phase (state after mortality and establishment), because that is when
``ind`` is written.  Only trees with ``height > 5 m``: ``fwriteoutput_ind.c:84`` drops
everything shorter, so the dump is a strict superset by construction and a raw row-count
comparison would fail for the right reason.

``ind`` is written with ``%g`` = **6 significant digits** (``fwriteoutput_ind.c:27``), so the
tightest meaningful tolerance is ~1e-5 relative; the dump is ``%.17g``.

Usage::

    python scripts/diagnose_rung2_roster_vs_ind.py \
        --roster /p/tmp/jamirp/M_rung2/dump_ind_c42490/roster_rank0000.txt \
        --ind    /p/tmp/jamirp/esm_land_daily/daily_2000_2019_historic_M_rung2ind_c42490_42490_seed1/output/ind_2000_2019.csv

Exit status: 0 = the dump reproduces every compared ``ind`` column; 1 = a mismatch.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

HEIGHT_MIN = 5.0  # param.height_min — the ind writer's own cut (fwriteoutput_ind.c:84)
RTOL = 2e-5  # ind carries 6 significant digits

# dump column -> (ind column, transform applied to the DUMP value)
COMPARE: dict[str, tuple[str, str]] = {
    "height": ("Height", "id"),
    "age": ("Age", "id"),
    "sla": ("SLA", "id"),
    "wooddens": ("Wooddens", "id"),
    "minwscal": ("minwscal", "id"),
    "D95max": ("D95max", "id"),
    "beta_root": ("beta_root", "id"),
    "k_root": ("k_root", "id"),
    "leaf_longevity": ("Longevity", "id"),
    "anpp": ("npp", "id"),
    "agpp": ("gpp", "id"),
    "atransp": ("transp", "id"),
    "fpc": ("fpc_ind", "id"),
    "wscal_mean": ("wscal_mean", "per365"),  # the writer divides by NDAYYEAR
    "mort_npp": ("mort_npp", "id"),
    "mort_age": ("mort_age", "id"),
    "mort_water": ("mort_water", "id"),
    "mort_temp": ("mort_temp", "id"),
    "mort_prob": ("mort", "id"),
    "isdead": ("isdead", "id"),
    "pft_id": ("Type", "id"),
}


def read_roster(path: Path) -> pl.DataFrame:
    """Parse the ``T`` records, taking the column names from the file's own ``#H T`` line."""
    cols: list[str] | None = None
    rows: list[list[str]] = []
    with path.open() as fh:
        for line in fh:
            if line.startswith("#H T "):
                cols = line.split()[2:]
            elif line.startswith("T "):
                rows.append(line.split()[1:])
    if cols is None:
        raise SystemExit(f"{path}: no '#H T' header line")
    df = pl.DataFrame({c: [r[i] for r in rows] for i, c in enumerate(cols)})
    ints = {"year", "patch", "treeidx", "pft_id", "age", "temp_stress", "bm_inc_counter", "isdead"}
    return df.with_columns(
        [pl.col(c).cast(pl.Int64) if c in ints else pl.col(c).cast(pl.Float64) for c in cols if c != "phase"]
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--roster", required=True, type=Path)
    ap.add_argument("--ind", required=True, type=Path)
    args = ap.parse_args()

    dump = read_roster(args.roster)
    post = dump.filter((pl.col("phase") == "post") & (pl.col("height") > HEIGHT_MIN))
    ind = pl.read_csv(args.ind, infer_schema_length=None).filter(pl.col("Type") <= 6)  # ids 0-6 are the seven tree PFTs

    print(f"roster: {dump.height} tree records ({post.height} post & >{HEIGHT_MIN} m)")
    print(f"ind   : {ind.height} tree rows")

    key_d, key_i = ["year", "patch", "treeidx"], ["Year", "Patch", "ID"]
    for df, keys, name in ((post, key_d, "roster post"), (ind, key_i, "ind")):
        if df.select(keys).n_unique() != df.height:
            print(f"FAIL: {name} keys are not unique")
            return 1

    # Nine ind columns share a name with a roster column (mort_*, isdead, minwscal, k_root,
    # beta_root, D95max).  Without an explicit prefix the join silently keeps ONE of each and
    # every such check compares a column against itself and passes — a green gate that tested
    # nothing.  Rename the ind side first.
    ind = ind.rename({c: ("I_" + c) for c in ind.columns})
    key_i = ["I_" + c for c in key_i]

    j = post.join(ind, left_on=key_d, right_on=key_i, how="full", coalesce=True)
    only_dump = j.filter(pl.col("I_Height").is_null()).height
    only_ind = j.filter(pl.col("height").is_null()).height
    print(f"rows only in roster: {only_dump}   only in ind: {only_ind}")
    if only_dump or only_ind:
        print("FAIL: the two rosters are not the same set of trees")
        return 1

    bad = 0
    for dcol, (icol, tf) in COMPARE.items():
        d = j[dcol].cast(pl.Float64)
        if tf == "per365":
            d = d / 365.0
        i = j["I_" + icol].cast(pl.Float64)
        denom = i.abs().clip(lower_bound=1e-30)
        rel = ((d - i).abs() / denom).max()
        ok = rel is not None and rel <= RTOL
        print(f"  [{'OK ' if ok else 'BAD'}] {dcol:<16} vs ind.{icol:<12} max rel diff {rel:.3e}")
        if not ok:
            bad += 1

    if bad:
        print(f"\nFAIL: {bad} column(s) disagree")
        return 1
    print(f"\nVERDICT: the hook's post-demography roster reproduces all {len(COMPARE)} shared "
          f"ind columns on {post.height} trees.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
