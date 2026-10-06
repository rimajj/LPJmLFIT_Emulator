"""explore_de_struct_youngswap.py — LINE X, Germany emulator, STRUCT track: which inputs make
STRUCT's young small trees look "bad" to the growth-sign head? (SD.md, H13)

STRUCT side: the sign head's full input rows dumped by explore_de_struct_sd (xdump_dir) for printed
trees < 6 m and <= 15 yr. Original side: the SH3 transition rows of the same member, cells,
< 6 m and <= 15 yr, through the SAME feature builder (StructHeads.features / X). Each STRUCT row is
matched to
a random original row of the same (Cell, state year, Type) — climate inputs are then identical by
construction (checked). The sign head's P(negative growth) is evaluated on
  S        STRUCT rows as they are          T   the matched original rows
  S[g<-T]  STRUCT rows with input group g taken from the matched original row (and T[g<-S])
groups: size (Height, agb, vegc, LAI, fpc_ind, D95), agec (Age, c_y), traits (6), ctx (n_live,
sum_fpc, sum_agb, height_rank, fpc_above), grass (3). Share of the gap closed by g =
(P(S) - P(S[g<-T])) / (P(S) - P(T)).
Usage:  python explore_de_struct_youngswap.py --xdump <dir> [--ncells 200]
Writes /p/tmp/jamirp/X_de/shared/eval/struct_youngswap.csv
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_struct_heads as hd  # noqa: E402

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
GROUPS = {
    "size": ["Height", "agb", "vegc", "LAI", "fpc_ind", "D95"],
    "agec": ["Age", "c_y"],
    "traits": ["SLA", "Wooddens", "D95max", "minwscal", "Longevity", "beta_root"],
    "ctx": ["n_live", "sum_fpc", "sum_agb", "height_rank", "fpc_above"],
    "grass": ["grass8_fpc", "grass8_LAI", "grass8_agb"],
}
MED = ["LAI", "fpc_ind", "vegc", "agb", "D95", "c_y", "Age", "n_live", "sum_fpc", "fpc_above"]


def tgroup(t):
    return np.where(t == 3, "beech", np.where(np.isin(t, [1, 2, 5]), "t125", "t046"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xdump", required=True)
    ap.add_argument("--ncells", type=int, default=200)
    ap.add_argument("--gcm", default="ACCESS-CM2")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    H = hd.StructHeads.load("DEV-A")
    names = H.names
    fs = sorted(glob.glob(os.path.join(a.xdump, "c*", "y*.parquet")))
    S = pl.concat([pl.read_parquet(f) for f in fs]).with_columns(
        y=pl.col("Year").cast(pl.Int32) - 1,
        Cell=pl.col("Cell_k").cast(pl.Int32),
        Type_i=pl.col("Type").cast(pl.Int32),
    )
    print("STRUCT rows", S.height, flush=True)
    cells = sorted(hd.folds()["Cell"].to_list())[: a.ncells]
    mem = pl.read_parquet(os.path.join(XDE, "shared", "registry", "members.parquet")).filter(
        (pl.col("gcm") == a.gcm)
        & (pl.col("seed") == a.seed)
        & ~pl.col("excluded")
        & pl.col("scen").is_in(["Historical", "ssp370"])
    )
    parts = []
    for m in mem["member"].to_list():
        df = hd.read_member_rows(
            m,
            pl.col("Cell").is_in(cells),
            (pl.col("Height") < 6.0) & (pl.col("Age") <= 15) & (pl.col("Type") <= 6),
        )
        df = df.filter(pl.col("Year") <= (2013 if "Historical" in m else 2043))
        X = H.X(df)
        parts.append(
            pl.DataFrame({n: X[:, j] for j, n in enumerate(names)}).with_columns(
                y=df["Year"].cast(pl.Int32),
                Cell=df["Cell"].cast(pl.Int32),
                Type_i=df["Type"].cast(pl.Int32),
            )
        )
    T = pl.concat(parts).sort("Cell", "y", "Type_i").with_row_index("ti")
    print("original rows", T.height, flush=True)
    grp = T.group_by("Cell", "y", "Type_i").agg(t0=pl.col("ti").min(), tn=pl.len())
    S = S.join(grp, on=["Cell", "y", "Type_i"], how="inner")
    rng = np.random.default_rng(20261006)
    pick = (S["t0"].to_numpy() + np.floor(rng.random(S.height) * S["tn"].to_numpy())).astype(int)
    XS = S.select([pl.col(n).cast(pl.Float32) for n in names]).to_numpy()
    XT = T.select([pl.col(n).cast(pl.Float32) for n in names]).to_numpy()[pick]
    print("matched STRUCT rows", S.height, flush=True)
    clim = [j for j, n in enumerate(names) if n.endswith("_y") or n.endswith("_y1")]
    dmax = float(np.nanmax(np.abs(XS[:, clim] - XT[:, clim])))
    print("max |climate input difference| on matched pairs:", dmax, flush=True)
    res = {"S": H._pred("gclf", XS), "T": H._pred("gclf", XT)}
    for g, cols in GROUPS.items():
        idx = [names.index(c) for c in cols]
        A = XS.copy()
        A[:, idx] = XT[:, idx]
        res[f"S[{g}<-T]"] = H._pred("gclf", A)
        B = XT.copy()
        B[:, idx] = XS[:, idx]
        res[f"T[{g}<-S]"] = H._pred("gclf", B)
    tg = tgroup(S["Type_i"].to_numpy())
    yy = S["y"].to_numpy()
    win = np.where(yy < 1995, "1985-94", np.where(yy < 2015, "1995-2014", "2015-43"))
    rows = []
    for w in ("1985-94", "1995-2014", "2015-43", "all"):
        for t in ("beech", "t125", "t046", "all"):
            m = np.ones(len(tg), bool)
            if w != "all":
                m &= win == w
            if t != "all":
                m &= tg == t
            if m.sum() < 50:
                continue
            r = {"win": w, "tg": t, "n": int(m.sum()), "clim_maxdiff": dmax}
            for k, v in res.items():
                r[k] = float(v[m].mean())
            gap = r["S"] - r["T"]
            for g in GROUPS:
                r[f"share_{g}"] = (r["S"] - r[f"S[{g}<-T]"]) / gap if abs(gap) > 1e-9 else None
            for c in MED:
                j = names.index(c)
                r[f"S_{c}_med"] = float(np.median(XS[m, j]))
                r[f"T_{c}_med"] = float(np.median(XT[m, j]))
            rows.append(r)
    out = pl.DataFrame(rows)
    p = os.path.join(XDE, "shared", "eval", "struct_youngswap.csv")
    out.write_csv(p)
    pl.Config.set_tbl_cols(40)
    pl.Config.set_tbl_width_chars(300)
    pl.Config.set_tbl_rows(40)
    show = ["win", "tg", "n", "S", "T"] + [f"share_{g}" for g in GROUPS]
    print(out.select(show).with_columns(pl.selectors.float().round(3)))
    meds = ["win", "tg"] + [c for c in out.columns if c.endswith("_med")]
    print(out.select(meds).with_columns(pl.selectors.float().round(4)))
    print("wrote", p)


if __name__ == "__main__":
    main()
