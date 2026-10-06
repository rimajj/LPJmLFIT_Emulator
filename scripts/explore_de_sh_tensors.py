#!/usr/bin/env python3
"""explore_de_sh_tensors.py — LINE X, Germany data-driven emulator, shared item SH11: PADDED PATCH
TENSORS and the
PAIRED-FORK INDEX for the neural tracks (C-RECUR, D-NSET).

Pre-registration + results: /p/tmp/jamirp/X_de/_status/SH11.md ; report _reports/r2_SH11.json.

LAYOUT  shared/tensors/<cellset>/<member>/   (member = SH3/SH4 member-window, e.g.
MPI-ESM1-2-HR_Historical_s1_h1985)
  idx.npy        int32  [P, T, S]   row index into tok/keys (-1 = empty slot). P = cells (sorted) x
  npatch, patch
                                    index p = cell_idx * npatch + Patch; T = the member's transition
                                    years y (pairs
                                    y -> y+1, from SH3); S = slots (40). Slots are filled tallest
                                    first (height_rank,
                                    then ID) with no holes, so mask = idx >= 0 and the padded token
                                    tensor is tok[idx].
  tok.npy        float32 [N, F]     every numeric SH3 column except the key/cell columns (state at
  y, targets at y+1);
                                    integer and boolean columns are stored exactly as float32, nulls
                                    as NaN
  keys.npy       int64  [N, 7]      Year, Cell, Patch, Type, ID, sla_i, wd_i ;  uhash.npy float64
  [N] (u_hash)
  cellf.npy      float32 [C, T, 8]  cell_stems_per_patch, cell_share_t0..6 (cell-level SH3 columns)
  patch.npy      float32 [P, T, Fp] every numeric SH4 patch-year column (state at y + outcomes at
  y+1)
  rec_f.npy      float32 [R, Fr]    SH4 recruit rows (numeric non-key columns); rec_keys.npy int64
  [R, 8]
                                    (Year, Year_entry, Cell, Patch, Type, ID, sla_i, wd_i);
                                    rec_p.npy int32 [R] patch
                                    index; rec_t.npy int16 [R] year index
  clim.npy       float32 [C, T+21, Fc]  climate of years Y0-20 .. Y_last+1 (Historical up to 2014,
  the member's
                                    scenario after), columns CLIM_COLS; clim_frozen.npy float32 [C,
                                    Fc] (own-GCM
                                    1985-2014 mean, anomalies 0); static.npy float32 [C, Fs]
                                    (soil_code, c85_*)
  meta.json      column lists, years, cells, npatch, S, gates
  shared/tensors/<cellset>/_fork_index.parquet   paired-fork index (gcm, seed, Cell, leg_a, leg_b,
  same_2014,
                                    first_diff_year)

STAGES  build --member M [--member M2 ...] | gates --member M | fork | submit --member ... (SLURM
array, standard/short)
No lat/lon, cell id is a KEY only (never a model input), no CO2, no wind. Years > 2044 refused by
the SH2 guard.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_sh_trans as tr  # noqa: E402

XDE = tr.XDE
OUT = os.environ.get("SH11_OUT", os.path.join(XDE, "shared", "tensors"))
PATCHT = os.path.join(XDE, "shared", "patch")
RECT = os.path.join(XDE, "shared", "recruits")
C8514 = os.path.join(XDE, "shared", "climate", "clim8514.parquet")
STATIC = os.path.join(XDE, "climate", "cell_static.parquet")
STATUS = os.path.join(XDE, "_status", "SH11.md")
REPORT = os.path.join(XDE, "_reports", "r2_SH11.json")
PY = tr.PY
S_SLOTS = 40
HIST_YEARS = 20
KEYCOLS = ["Year", "Cell", "Patch", "Type", "ID", "sla_i", "wd_i"]
STRCOLS = ["member", "gcm", "traj", "seed"]
CELLCOLS = ["cell_stems_per_patch"] + [f"cell_share_t{k}" for k in range(tr.MAX_TREE_TYPE + 1)]
REC_KEYS = ["Year", "Year_entry", "Cell", "Patch", "Type", "ID", "sla_i", "wd_i"]
CLIM_F = [
    "tmean_ann",
    "twarm_month",
    "tcold_month",
    "gdd5",
    "frost_days",
    "days_gt30",
    "prec_ann",
    "prec_jja",
    "prec_amjjas",
    "cwb_jja",
    "cwb_amjjas",
    "cwb_min3",
    "dry_spell_max",
    "vpd_jja",
    "vpd_win10_sum",
    "swdown_ann",
    "rh_jja",
]
TR20 = ["tcold_month_tr20", "twarm_month_tr20", "gdd5_tr20"]
TSTRESS = [f"tstress_pft{k}" for k in range(tr.MAX_TREE_TYPE + 1)]
ABS_COLS = CLIM_F + TR20 + TSTRESS
CLIM_COLS = ABS_COLS + [f"anom_{c}" for c in ABS_COLS]
C85_F = [
    "tmean_ann",
    "tcold_month",
    "twarm_month",
    "gdd5",
    "frost_days",
    "prec_ann",
    "prec_jja",
    "cwb_jja",
    "cwb_amjjas",
    "cwb_min3",
    "dry_spell_max",
    "vpd_jja",
    "vpd_win10_sum",
    "swdown_ann",
    "rh_jja",
]
STATIC_COLS = ["soil_code"] + [f"c85_{f}" for f in C85_F]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def status(line: str):
    with open(STATUS, "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {line}\n")


def member_dir(member: str, cellset: str = "dev") -> str:
    return os.path.join(OUT, cellset, member)


def year_files(root: str, member: str, cellset: str = "dev") -> dict[int, str]:
    fs = sorted(glob.glob(os.path.join(root, cellset, member, "cb=*", "y*.parquet")))
    return {int(os.path.basename(f)[1:5]): f for f in fs}


def parse_member(member: str) -> dict:
    gcm, scen, s, win = member.rsplit("_", 3)
    return {"gcm": gcm, "scen": scen, "seed": int(s[1:]), "win": win}


def to_f64(df: pl.DataFrame, cols: list[str]) -> np.ndarray:
    """[n, len(cols)] float64, nulls -> NaN, booleans -> 0/1 (the round-trip comparison basis)."""
    out = np.empty((df.height, len(cols)), dtype=np.float64)
    for j, c in enumerate(cols):
        s = df[c]
        if s.dtype == pl.Boolean:
            s = s.cast(pl.Int8)
        out[:, j] = s.cast(pl.Float64).fill_null(np.nan).to_numpy()
    return out


# ================================================================================================
# climate
def climate_tensor(gcm: str, scen: str, cells: np.ndarray, y_from: int, y_to: int) -> np.ndarray:
    """[C, y_to - y_from + 1, len(CLIM_COLS)] float32: Historical for years <= 2014, `scen` after
    (clim_year == Year
    for every usable year, SH1 README; asserted against SH0 segments for the member's own years)."""
    assert y_to <= 2045, (
        "owner decision 2026-10-01: only the 1985-2044 window (+ its y+1 climate) is used"
    )
    cy = pl.scan_parquet(tr.CLIM).filter(
        (pl.col("gcm") == gcm)
        & pl.col("Cell").is_in(cells.tolist())
        & pl.col("Year").is_between(y_from, y_to)
    )
    ex = pl.scan_parquet(tr.EXT).filter(
        (pl.col("gcm") == gcm)
        & pl.col("Cell").is_in(cells.tolist())
        & pl.col("Year").is_between(y_from, y_to)
    )
    exn = ["gcm", "scen", "Cell", "Year"] + [
        c for c in CLIM_COLS if c not in cy.collect_schema().names()
    ]
    df = (
        cy.join(ex.select(exn), on=["gcm", "scen", "Cell", "Year"], how="left")
        .select("scen", "Cell", "Year", *CLIM_COLS)
        .collect()
    )
    want = "Historical"
    df = df.filter(
        ((pl.col("Year") <= 2014) & (pl.col("scen") == want))
        | ((pl.col("Year") > 2014) & (pl.col("scen") == (scen if scen != "Historical" else "none")))
    )
    years = np.arange(y_from, y_to + 1)
    full = pl.DataFrame(
        {
            "Cell": np.repeat(cells, len(years)).astype(np.int32),
            "Year": np.tile(years, len(cells)).astype(np.int32),
        }
    )
    df = full.join(
        df.with_columns(pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32)),
        on=["Cell", "Year"],
        how="left",
        maintain_order="left",
    )
    X = to_f64(df, CLIM_COLS).astype(np.float32).reshape(len(cells), len(years), len(CLIM_COLS))
    return X


def climate_frozen(gcm: str, cells: np.ndarray) -> np.ndarray:
    c8 = pl.read_parquet(C8514).filter(pl.col("gcm") == gcm)
    fr = pl.DataFrame({"Cell": cells.astype(np.int64)}).join(
        c8.with_columns(pl.col("Cell").cast(pl.Int64)), on="Cell", how="left", maintain_order="left"
    )
    out = np.zeros((len(cells), len(CLIM_COLS)), np.float32)
    for j, c in enumerate(CLIM_COLS):
        if c.startswith("anom_"):
            continue
        out[:, j] = fr[c].cast(pl.Float64).fill_null(np.nan).to_numpy()
    return out


def static_tensor(gcm: str, cells: np.ndarray) -> np.ndarray:
    st = pl.read_parquet(STATIC)
    c8 = pl.read_parquet(C8514).filter(pl.col("gcm") == gcm)
    fr = (
        pl.DataFrame({"Cell": cells.astype(np.int64)})
        .join(
            st.select(pl.col("Cell").cast(pl.Int64), "soil_code"),
            on="Cell",
            how="left",
            maintain_order="left",
        )
        .join(
            c8.select(pl.col("Cell").cast(pl.Int64), *[pl.col(f).alias(f"c85_{f}") for f in C85_F]),
            on="Cell",
            how="left",
            maintain_order="left",
        )
    )
    return to_f64(fr, STATIC_COLS).astype(np.float32)


# ================================================================================================
# build
def build(member: str, cellset: str = "dev", S: int = S_SLOTS) -> dict:
    rl.assert_usable(member)
    t0 = time.time()
    _, _, folds = tr.registry()
    cells = tr.cell_list(folds, cellset).astype(np.int64)
    mem, _, _ = tr.registry()
    npatch = int(tr.member_row(mem, member)["npatch"]) if "npatch" in mem.columns else 250
    tf = year_files(tr.TRANS, member, cellset)
    pf = year_files(PATCHT, member, cellset)
    rf = year_files(RECT, member, cellset)
    years = sorted(tf)
    assert years == sorted(pf), (years, sorted(pf))
    assert max(years) + 1 <= 2044 + 1
    T, C = len(years), len(cells)
    P = C * npatch
    od = member_dir(member, cellset)
    os.makedirs(od, exist_ok=True)
    schema = pl.read_parquet_schema(tf[years[0]])
    tok_cols = [c for c in schema if c not in STRCOLS + KEYCOLS + CELLCOLS + ["u_hash"]]
    nrows = {
        y: pl.scan_parquet(tf[y])
        .filter(pl.col("Cell").is_in(cells.tolist()))
        .select(pl.len())
        .collect()
        .item()
        for y in years
    }
    N = sum(nrows.values())
    log(f"{member}: {C} cells x {npatch} patches, {T} years, {N} tree rows, F = {len(tok_cols)}")
    tok = np.lib.format.open_memmap(
        os.path.join(od, "tok.npy"), "w+", np.float32, (N, len(tok_cols))
    )
    keys = np.lib.format.open_memmap(
        os.path.join(od, "keys.npy"), "w+", np.int64, (N, len(KEYCOLS))
    )
    uh = np.lib.format.open_memmap(os.path.join(od, "uhash.npy"), "w+", np.float64, (N,))
    idx = np.full((P, T, S), -1, np.int32)
    cellf = np.full((C, T, len(CELLCOLS)), np.nan, np.float32)
    max_live = 0
    off = 0
    for t, y in enumerate(years):
        df = (
            pl.read_parquet(tf[y])
            .filter(pl.col("Cell").is_in(cells.tolist()))
            .sort(["Cell", "Patch", "height_rank", "ID"])
        )
        n = df.height
        assert n == nrows[y], (y, n, nrows[y])
        ci = np.searchsorted(cells, df["Cell"].to_numpy())
        assert np.all(cells[ci] == df["Cell"].to_numpy())
        p = ci * npatch + df["Patch"].to_numpy().astype(np.int64)
        first = np.r_[True, p[1:] != p[:-1]]
        start = np.flatnonzero(first)
        grp = np.cumsum(first) - 1
        slot = np.arange(n) - start[grp]
        mx = int(slot.max()) + 1 if n else 0
        max_live = max(max_live, mx)
        if mx > S:
            raise RuntimeError(
                f"{member} y{y}: {mx} living stems in one patch > S = {S} slots (gate G1)"
            )
        idx[p, t, slot] = (off + np.arange(n)).astype(np.int32)
        tok[off : off + n] = to_f64(df, tok_cols).astype(np.float32)
        keys[off : off + n] = to_f64(df, KEYCOLS).astype(np.int64)
        uh[off : off + n] = df["u_hash"].to_numpy()
        cf = df.group_by("Cell").agg([pl.col(c).first() for c in CELLCOLS]).sort("Cell")
        cellf[np.searchsorted(cells, cf["Cell"].to_numpy()), t] = to_f64(cf, CELLCOLS).astype(
            np.float32
        )
        off += n
        if t % 10 == 0:
            log(f"  y{y}: {n} rows, max slots so far {max_live}")
    tok.flush()
    keys.flush()
    uh.flush()
    np.save(os.path.join(od, "idx.npy"), idx)
    np.save(os.path.join(od, "cellf.npy"), cellf)
    # patch tensor
    pschema = pl.read_parquet_schema(pf[years[0]])
    pcols = [c for c in pschema if c not in STRCOLS + ["Year", "Cell", "Patch"]]
    patch = np.full((P, T, len(pcols)), np.nan, np.float32)
    for t, y in enumerate(years):
        d = pl.read_parquet(pf[y]).filter(pl.col("Cell").is_in(cells.tolist()))
        p = np.searchsorted(cells, d["Cell"].to_numpy()) * npatch + d["Patch"].to_numpy().astype(
            np.int64
        )
        patch[p, t] = to_f64(d, pcols).astype(np.float32)
    np.save(os.path.join(od, "patch.npy"), patch)
    # recruit rows
    rschema = pl.read_parquet_schema(rf[years[0]])
    rcols = [c for c in rschema if c not in STRCOLS + REC_KEYS]
    RF, RK, RP, RT = [], [], [], []
    for t, y in enumerate(years):
        if y not in rf:
            continue
        d = tr.with_key(pl.read_parquet(rf[y]).filter(pl.col("Cell").is_in(cells.tolist())))
        RF.append(to_f64(d, rcols).astype(np.float32))
        RK.append(to_f64(d, REC_KEYS).astype(np.int64))
        RP.append(
            (np.searchsorted(cells, d["Cell"].to_numpy()) * npatch + d["Patch"].to_numpy()).astype(
                np.int32
            )
        )
        RT.append(np.full(d.height, t, np.int16))
    np.save(os.path.join(od, "rec_f.npy"), np.concatenate(RF))
    np.save(os.path.join(od, "rec_keys.npy"), np.concatenate(RK))
    np.save(os.path.join(od, "rec_p.npy"), np.concatenate(RP))
    np.save(os.path.join(od, "rec_t.npy"), np.concatenate(RT))
    # climate + static
    mp = parse_member(member)
    clim = climate_tensor(mp["gcm"], mp["scen"], cells, years[0] - HIST_YEARS, years[-1] + 1)
    np.save(os.path.join(od, "clim.npy"), clim)
    np.save(os.path.join(od, "clim_frozen.npy"), climate_frozen(mp["gcm"], cells))
    np.save(os.path.join(od, "static.npy"), static_tensor(mp["gcm"], cells))
    meta = {
        "member": member,
        **mp,
        "cellset": cellset,
        "cells": cells.tolist(),
        "npatch": npatch,
        "years": years,
        "S": S,
        "N": int(N),
        "tok_cols": tok_cols,
        "key_cols": KEYCOLS,
        "cell_cols": CELLCOLS,
        "patch_cols": pcols,
        "rec_cols": rcols,
        "rec_keys": REC_KEYS,
        "clim_cols": CLIM_COLS,
        "clim_year0": years[0] - HIST_YEARS,
        "static_cols": STATIC_COLS,
        "max_live": int(max_live),
        "build_s": round(time.time() - t0, 1),
    }
    json.dump(meta, open(os.path.join(od, "meta.json"), "w"), indent=1)
    log(f"{member}: built in {time.time() - t0:.0f} s, max living stems {max_live}")
    return meta


# ================================================================================================
# load helpers
def load(member: str, cellset: str = "dev", mmap: bool = True) -> dict:
    od = member_dir(member, cellset)
    meta = json.load(open(os.path.join(od, "meta.json")))
    mm = "r" if mmap else None
    d = {"meta": meta}
    for k in (
        "idx",
        "tok",
        "keys",
        "uhash",
        "cellf",
        "patch",
        "rec_f",
        "rec_keys",
        "rec_p",
        "rec_t",
        "clim",
        "clim_frozen",
        "static",
    ):
        d[k] = np.load(os.path.join(od, f"{k}.npy"), mmap_mode=mm)
    return d


def rows_of_year(D: dict, t: int) -> pl.DataFrame:
    """Tensor -> SH3 rows of year index t (the round-trip direction; also for consumers)."""
    m = D["meta"]
    idx = np.asarray(D["idx"][:, t, :])
    p, s = np.nonzero(idx >= 0)
    r = idx[p, s]
    cols = {c: D["keys"][r, j] for j, c in enumerate(KEYCOLS)}
    cols["u_hash"] = D["uhash"][r]
    tok = np.asarray(D["tok"][r]).astype(np.float64)
    for j, c in enumerate(m["tok_cols"]):
        cols[c] = tok[:, j]
    ci = p // m["npatch"]
    cf = np.asarray(D["cellf"][ci, t]).astype(np.float64)
    for j, c in enumerate(CELLCOLS):
        cols[c] = cf[:, j]
    return pl.DataFrame(cols)


# ================================================================================================
# gates
def gates(member: str, cellset: str = "dev") -> dict:
    D = load(member, cellset)
    m = D["meta"]
    tf = year_files(tr.TRANS, member, cellset)
    pf = year_files(PATCHT, member, cellset)
    rf = year_files(RECT, member, cellset)
    cells = np.asarray(m["cells"])
    npatch = m["npatch"]
    allcols = KEYCOLS + ["u_hash"] + m["tok_cols"] + CELLCOLS
    g = {"G1_slots": {"S": m["S"], "max_live": m["max_live"], "pass": m["max_live"] <= m["S"]}}
    bad_rt, bad_mask, bad_patch, bad_rec, n_rows, seen_once = [], [], [], [], 0, True
    nl_j = m["patch_cols"].index("n_live_y")
    for t, y in enumerate(m["years"]):
        src = pl.read_parquet(tf[y]).filter(pl.col("Cell").is_in(cells.tolist()))
        rec = rows_of_year(D, t)
        a = to_f64(src.sort(KEYCOLS), allcols)
        b = to_f64(rec.sort(KEYCOLS), allcols)
        if a.shape != b.shape or not np.array_equal(a, b, equal_nan=True):
            diff = [
                c
                for j, c in enumerate(allcols)
                if a.shape != b.shape or not np.array_equal(a[:, j], b[:, j], equal_nan=True)
            ]
            bad_rt.append({"year": y, "cols": diff[:10], "shape": [list(a.shape), list(b.shape)]})
        n_rows += src.height
        idx = np.asarray(D["idx"][:, t, :])
        msk = idx >= 0
        cnt = msk.sum(1)
        prefix = np.all(msk == (np.arange(m["S"])[None, :] < cnt[:, None]))
        r = idx[msk]
        once = len(np.unique(r)) == len(r) == src.height
        seen_once &= bool(once)
        nl_patch = np.nan_to_num(np.asarray(D["patch"][:, t, nl_j]), nan=-1).astype(np.int64)
        # SH3's own per-row n_live column at the row's patch
        nlj = m["tok_cols"].index("n_live")
        tokn = np.asarray(D["tok"][r, nlj]).astype(np.int64)
        prow = np.nonzero(msk)[0]
        if not (prefix and np.array_equal(cnt, nl_patch) and np.array_equal(tokn, cnt[prow])):
            bad_mask.append(
                {
                    "year": y,
                    "prefix": bool(prefix),
                    "eq_sh4_n_live": bool(np.array_equal(cnt, nl_patch)),
                    "eq_sh3_n_live": bool(np.array_equal(tokn, cnt[prow])),
                }
            )
        # patch table
        ps = (
            pl.read_parquet(pf[y])
            .filter(pl.col("Cell").is_in(cells.tolist()))
            .sort("Cell", "Patch")
        )
        pp = np.searchsorted(cells, ps["Cell"].to_numpy()) * npatch + ps["Patch"].to_numpy().astype(
            np.int64
        )
        if not (
            ps.height == len(cells) * npatch
            and np.array_equal(
                to_f64(ps, m["patch_cols"]),
                np.asarray(D["patch"][pp, t]).astype(np.float64),
                equal_nan=True,
            )
        ):
            bad_patch.append(y)
        if y in rf:
            rs = tr.with_key(pl.read_parquet(rf[y]).filter(pl.col("Cell").is_in(cells.tolist())))
            sel = np.asarray(D["rec_t"]) == t
            kk = np.asarray(D["rec_keys"])[sel]
            rr = pl.DataFrame(
                {c: kk[:, j] for j, c in enumerate(REC_KEYS)}
                | {
                    c: np.asarray(D["rec_f"])[sel][:, j].astype(np.float64)
                    for j, c in enumerate(m["rec_cols"])
                }
            )
            ok_p = np.array_equal(
                np.asarray(D["rec_p"])[sel],
                (np.searchsorted(cells, kk[:, 2]) * npatch + kk[:, 3]).astype(np.int32),
            )
            a2 = to_f64(rs.sort(REC_KEYS), REC_KEYS + m["rec_cols"])
            b2 = to_f64(rr.sort(REC_KEYS), REC_KEYS + m["rec_cols"])
            if not (ok_p and a2.shape == b2.shape and np.array_equal(a2, b2, equal_nan=True)):
                bad_rec.append(y)
    g["G2_round_trip_sh3"] = {
        "years": len(m["years"]),
        "rows": n_rows,
        "cols": len(allcols),
        "bad": bad_rt,
        "pass": not bad_rt,
    }
    g["G2_round_trip_sh4_patch"] = {"bad_years": bad_patch, "pass": not bad_patch}
    g["G2_round_trip_sh4_recruits"] = {"bad_years": bad_rec, "pass": not bad_rec}
    g["G3_masks"] = {
        "bad": bad_mask,
        "every_row_once": seen_once,
        "pass": (not bad_mask) and seen_once,
    }
    clim = np.asarray(D["clim"])
    g["climate_finite"] = {
        "share_finite": float(np.isfinite(clim).mean()),
        "pass": bool(np.isfinite(clim).all()),
    }
    g["pass"] = all(v["pass"] for v in g.values() if isinstance(v, dict))
    json.dump(g, open(os.path.join(member_dir(member, cellset), "_gates.json"), "w"), indent=1)
    log(
        f"{member}: gates pass={g['pass']} "
        + json.dumps({k: v["pass"] for k, v in g.items() if isinstance(v, dict)})
    )
    status(
        f"{member}: gates pass={g['pass']} "
        + json.dumps({k: v["pass"] for k, v in g.items() if isinstance(v, dict)})
        + f" (rows {n_rows}, max living stems {m['max_live']}, S {m['S']})"
    )
    return g


# ================================================================================================
# paired-fork index
def fork_index(cellset: str = "dev") -> pl.DataFrame:
    """For every (gcm, seed) and every pair of ssp legs: is the 2014 roster identical (keys + every
    state column at
    y = 2014), and the first year y whose living roster differs (keys + Height + agb), per Cell."""
    mem, _, folds = tr.registry()
    cells = tr.cell_list(folds, cellset).tolist()
    ms = [m for m in tr.usable_members(mem) if "_w2015" in m and "_ssp" in m]
    by = {}
    for m in ms:
        p = parse_member(m)
        by.setdefault((p["gcm"], p["seed"]), []).append(m)
    state = (
        ["Type", "ID", "sla_i", "wd_i"]
        + tr.TRAITS
        + tr.STATE
        + tr.FLUX
        + ["c_y", "G_y", "W_y", "d_agb_prev"]
    )
    out = []
    for (gcm, seed), legs in sorted(by.items()):
        H = {}
        for m in legs:
            fs = year_files(tr.TRANS, m, cellset)
            per = []
            for y in sorted(fs):
                d = pl.read_parquet(fs[y], columns=["Cell", "Patch"] + state).filter(
                    pl.col("Cell").is_in(cells)
                )
                cols = state if y == 2014 else ["Type", "ID", "sla_i", "wd_i", "Height", "agb"]
                h = (
                    d.select("Cell", pl.struct(["Patch"] + cols).hash(seed=7).alias("h"))
                    .group_by("Cell")
                    .agg(pl.col("h").sum().alias("hs"), pl.len().alias("n"))
                )
                per.append(h.with_columns(Year=pl.lit(y, pl.Int16)))
            H[m] = pl.concat(per)
            log(f"fork: hashed {m}")
        for i in range(len(legs)):
            for j in range(i + 1, len(legs)):
                a, b = legs[i], legs[j]
                J = H[a].join(H[b], on=["Cell", "Year"], how="full", suffix="_b", coalesce=True)
                J = J.with_columns(
                    same=(pl.col("hs") == pl.col("hs_b")) & (pl.col("n") == pl.col("n_b"))
                )
                same14 = J.filter(pl.col("Year") == 2014).select(
                    "Cell", pl.col("same").alias("same_2014")
                )
                fd = (
                    J.filter(~pl.col("same").fill_null(False))
                    .group_by("Cell")
                    .agg(pl.col("Year").min().alias("first_diff_year"))
                )
                r = same14.join(fd, on="Cell", how="left").with_columns(
                    gcm=pl.lit(gcm),
                    seed=pl.lit(seed, pl.Int8),
                    leg_a=pl.lit(parse_member(a)["scen"]),
                    leg_b=pl.lit(parse_member(b)["scen"]),
                )
                out.append(r)
    F = (
        pl.concat(out)
        .select("gcm", "seed", "Cell", "leg_a", "leg_b", "same_2014", "first_diff_year")
        .sort("gcm", "seed", "leg_a", "leg_b", "Cell")
    )
    od = os.path.join(OUT, cellset)
    os.makedirs(od, exist_ok=True)
    F.write_parquet(os.path.join(od, "_fork_index.parquet"))
    summ = (
        F.group_by("gcm", "seed", "leg_a", "leg_b")
        .agg(
            n=pl.len(),
            share_same_2014=pl.col("same_2014").mean(),
            share_diff_by_2015=(pl.col("first_diff_year") <= 2015).mean(),
            median_first_diff=pl.col("first_diff_year").median(),
        )
        .sort("gcm", "seed", "leg_a", "leg_b")
    )
    log(summ)
    ok = bool((F["same_2014"].fill_null(False)).all())
    status(
        f"fork index: {F.height} (gcm, seed, Cell, leg pair) rows; 2014 roster identical in "
        f"{F['same_2014'].fill_null(False).mean():.4f} -> G4 pass={ok}; "
        "median first differing year "
        f"{F['first_diff_year'].median()}"
    )
    json.dump(
        {"pass": ok, "rows": F.height, "summary": summ.to_dicts()},
        open(os.path.join(od, "_fork_gates.json"), "w"),
        indent=1,
        default=str,
    )
    return F


# ================================================================================================
# submit
def submit(members: list[str], cellset: str, fork: bool):
    jobs = os.path.join(XDE, "_jobs")
    logs = os.path.join(REPO, "logs")
    me = os.path.abspath(__file__)
    lines = "\n".join(f'  {i}) M="{m}" ;;' for i, m in enumerate(members))
    jcf = os.path.join(jobs, "sh11_tensors.jcf")
    with open(jcf, "w") as f:
        f.write(f"""#!/bin/bash
#SBATCH --job-name=X-sh11
#SBATCH --account=waldspektrum
#SBATCH --partition=standard
#SBATCH --qos=short
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=01:00:00
#SBATCH --array=0-{len(members) - 1}
#SBATCH --output={logs}/X-sh11.%A_%a.out
case $SLURM_ARRAY_TASK_ID in
{lines}
esac
export POLARS_MAX_THREADS=4
{PY} {me} build --member "$M" --cellset {cellset} && \\
  {PY} {me} gates --member "$M" --cellset {cellset}
echo "=== JOB DONE exit=$? ==="
""")
    jid = subprocess.check_output(["sbatch", "--parsable", jcf], text=True).strip()
    log(f"submitted {jid}")
    status(f"submitted build+gates array {jid} for {members}")
    if fork:
        jf = os.path.join(jobs, "sh11_fork.jcf")
        with open(jf, "w") as f:
            f.write(f"""#!/bin/bash
#SBATCH --job-name=X-sh11fork
#SBATCH --account=waldspektrum
#SBATCH --partition=standard
#SBATCH --qos=short
#SBATCH --cpus-per-task=16
#SBATCH --mem=60G
#SBATCH --time=01:00:00
#SBATCH --output={logs}/X-sh11fork.%j.out
export POLARS_MAX_THREADS=16
{PY} {me} fork --cellset {cellset}
echo "=== JOB DONE exit=$? ==="
""")
        j2 = subprocess.check_output(["sbatch", "--parsable", jf], text=True).strip()
        log(f"submitted fork {j2}")
        status(f"submitted fork-index job {j2}")


def report(members: list[str], cellset: str = "dev"):
    gs = {}
    for m in members:
        f = os.path.join(member_dir(m, cellset), "_gates.json")
        gs[m] = json.load(open(f)) if os.path.exists(f) else {"pass": False, "missing": True}
        mf = os.path.join(member_dir(m, cellset), "meta.json")
        if os.path.exists(mf):
            mt = json.load(open(mf))
            gs[m]["size"] = {
                "rows": mt["N"],
                "years": mt["years"],
                "S": mt["S"],
                "max_live": mt["max_live"],
                "build_s": mt["build_s"],
            }
    fk = json.load(open(os.path.join(OUT, cellset, "_fork_gates.json")))
    du = subprocess.check_output(["du", "-sh", os.path.join(OUT, cellset)], text=True).split()[0]
    rep = {
        "id": "SH11",
        "status": "ok" if all(g["pass"] for g in gs.values()) and fk["pass"] else "fail",
        "deliverables": [os.path.abspath(__file__), os.path.join(OUT, cellset), STATUS],
        "members": gs,
        "fork_index": fk,
        "disk": du,
        "notes": "padded INDEX tensor idx[P,T,S] into a row store tok[N,F] (tok[idx] is the padded "
        "token tensor); round trip exact against SH3/SH4; paired-fork index over all 12 usable "
        "ssp members",
    }
    json.dump(rep, open(REPORT, "w"), indent=1, default=str)
    log(f"report: {rep['status']} disk {du}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["build", "gates", "fork", "submit", "report"])
    ap.add_argument("--member", action="append")
    ap.add_argument("--cellset", default="dev")
    ap.add_argument("--fork", action="store_true")
    a = ap.parse_args(argv)
    if a.stage == "build":
        for m in a.member:
            build(m, a.cellset)
    elif a.stage == "gates":
        for m in a.member:
            gates(m, a.cellset)
    elif a.stage == "report":
        report(a.member, a.cellset)
    elif a.stage == "fork":
        fork_index(a.cellset)
    else:
        submit(a.member, a.cellset, a.fork)


if __name__ == "__main__":
    main()
