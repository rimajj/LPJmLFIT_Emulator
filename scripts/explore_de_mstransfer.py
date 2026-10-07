"""explore_de_mstransfer.py — LINE X, Germany emulator: is the margin model's tall-tree bias on the other climate model
carried by its CLIMATE-LEVEL inputs? (pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "Pre-registration T")

MS (explore_de_nppmodel2.py) is trained on MPI-ESM1-2-HR members only. Its weather anomalies are GCM-common by
construction (each member's own gcm 1985-2014 cell mean subtracted), so the only GCM-specific inputs are the 15 c85_*
climatology LEVELS and the two absolute y1 temperatures. On the KZ test rows (no refit) this swaps those for MPI's
values of the same cell and re-reads the residual statistics:
  base    as fitted
  swapC   c85_* <- MPI's c85 of the same cell
  swapA   tmean_ann_y1 / twarm_month_y1 re-levelled by (MPI c85 - own c85), the anomaly kept
  swapCA  both
Also (T1) the ACCESS - MPI level difference per feature and the share of >= 15 m rows outside the MPI training range.
Usage:  python explore_de_mstransfer.py        -> shared/eval/mstransfer_{zstats,levels,yearly}.csv
        python explore_de_mstransfer.py anom   -> T3: >= 15 m r/s by warming-anomaly bin + the share of rows with an
                                                  anomaly input outside the MPI training range -> mstransfer_anom.csv
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
import polars as pl
from scipy.stats import norm

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_gsign_info as gi  # noqa: E402
import explore_de_nppmodel as nm  # noqa: E402
import explore_de_nppmodel2 as n2  # noqa: E402
import explore_de_tab_features as F  # noqa: E402

REF = "MPI-ESM1-2-HR"
ABS = {"tmean_ann_y1": "tmean_ann", "twarm_month_y1": "twarm_month"}
VARIANTS = ("base", "swapC", "swapA", "swapCA")


def ref_levels() -> pl.DataFrame:
    c85 = pl.read_parquet(os.path.join(gi.XDE, "shared", "climate", "clim8514.parquet"))
    return c85.filter(pl.col("gcm") == REF).select(pl.col("Cell").cast(pl.Int16),
                                                   *[pl.col(f).alias(f"ref_{f}") for f in F.C85_F])


def swapped(D: pl.DataFrame, var: str) -> pl.DataFrame:
    ex = []
    if var in ("swapC", "swapCA"):
        ex += [pl.col(f"ref_{f}").alias(f"c85_{f}") for f in F.C85_F]
    if var in ("swapA", "swapCA"):
        ex += [(pl.col(a) - pl.col(f"c85_{f}") + pl.col(f"ref_{f}")).alias(a) for a, f in ABS.items()]
    return D.with_columns(ex) if ex else D


def stats(T: pl.DataFrame) -> pl.DataFrame:
    T = T.with_columns(r=pl.col("m") - pl.col("mu"), h5=pl.Series(n2.hclass(T["Height"].to_numpy())),
                       p=pl.Series(norm.cdf((-T["mu"] / T["s"]).to_numpy())), neg=(pl.col("m") < 0).cast(pl.Float64))
    return (T.group_by("h5").agg(pl.col("r").mean().alias("r_mean"), pl.col("s").mean().alias("s_mean"),
                                 (pl.col("r") / pl.col("s")).std().alias("z_sd"),
                                 (pl.col("p") - pl.col("neg")).mean().alias("excess"), n=pl.len())
            .with_columns(r_over_s=pl.col("r_mean") / pl.col("s_mean")).sort("h5"))


def main():
    t0 = time.time()
    W, wcols = n2.weather()
    R = ref_levels()
    A = n2.Arm("MS")
    lvl = [c for c in A.cols if c.startswith("c85_")] + list(ABS)
    # T1: training range of each level input = MPI training members' cell-years (all dev cells)
    WT = W.filter((pl.col("gcm") == REF) & (pl.col("seed") == 1) & pl.col("traj").is_in(["Historical", "ssp126",
                                                                                         "ssp370"]))
    lo = {c: float(WT[c].min()) for c in lvl}
    hi = {c: float(WT[c].max()) for c in lvl}
    c2 = gi.cells200()
    c85 = pl.read_parquet(os.path.join(gi.XDE, "shared", "climate", "clim8514.parquet")).filter(
        pl.col("Cell").cast(pl.Int16).is_in(c2))
    lrows = []
    for f in F.C85_F:
        a = c85.filter(pl.col("gcm") == "ACCESS-CM2").sort("Cell")[f].to_numpy().astype(float)
        b = c85.filter(pl.col("gcm") == REF).sort("Cell")[f].to_numpy().astype(float)
        lrows.append(dict(feature=f, mean_diff=float((a - b).mean()), sd_ref=float(b.std()),
                          diff_in_sd=float((a - b).mean() / max(b.std(), 1e-12)),
                          corr_cells=float(np.corrcoef(a, b)[0, 1])))
    L = pl.DataFrame(lrows)
    print("T1 ACCESS - MPI 1985-2014 level difference over the 200 test cells:")
    print(L.with_columns(pl.col(pl.Float64).round(3)), flush=True)
    rows, yrows = [], []
    for mem in nm.TEST:
        D = n2.y1_side(nm.load(mem, cells=c2, frac=n2.TEST_FRAC).join(W, on=n2.JOIN, how="left"))
        assert D[wcols[0]].null_count() == 0
        D = D.with_columns(thr=pl.when(pl.col("is_new_y").fill_null(False)).then(None).otherwise(pl.col("thr")))
        D = D.join(R, on="Cell", how="left")
        assert D["ref_tmean_ann"].null_count() == 0
        big = D.filter(pl.col("Height") >= 15)
        out = pl.any_horizontal([(pl.col(c) < lo[c]) | (pl.col(c) > hi[c]) for c in lvl])
        share = float(big.select(out.cast(pl.Float64).mean()).item())
        per = {c: float(big.select(((pl.col(c) < lo[c]) | (pl.col(c) > hi[c])).cast(pl.Float64).mean()).item())
               for c in lvl}
        top = sorted(per.items(), key=lambda kv: -kv[1])[:4]
        print(f"{mem}: >= 15 m rows {big.height}, any level input out of MPI training range {share:.3f}; top "
              + ", ".join(f"{k} {v:.3f}" for k, v in top), flush=True)
        base_mu = None
        Y = D.select("Year", true=(pl.col("m") < 0).cast(pl.Float64))
        for var in VARIANTS:
            Dv = swapped(D, var)
            mu, s = A.pred(Dv.select(A.cols).to_numpy().astype(np.float32))
            if var == "base":
                base_mu = mu
            elif mem.startswith(REF):
                assert np.array_equal(mu, base_mu), f"T0: {var} changed MPI's mu"
            G = stats(D.select("Height", "m").with_columns(mu=pl.Series(mu), s=pl.Series(s))).with_columns(
                member=pl.lit(mem), variant=pl.lit(var), out_share_ge15=pl.lit(share))
            rows.append(G)
            Y = Y.with_columns(pl.Series(f"p_{var}", norm.cdf(-mu / s)))
        Yy = Y.group_by("Year").agg(pl.all().mean()).sort("Year").with_columns(member=pl.lit(mem))
        yrows.append(Yy)
        t = Yy["true"].to_numpy()
        S = pl.concat([r for r in rows if r["member"][0] == mem])
        print(S.filter(pl.col("h5") >= 1).select("variant", "h5", "r_over_s", "z_sd", "excess")
              .with_columns(pl.col(pl.Float64).round(4)).pivot(on="h5", index="variant", values="r_over_s"), flush=True)
        for var in VARIANTS:
            e = Yy[f"p_{var}"].to_numpy()
            ge10 = S.filter((pl.col("variant") == var) & (pl.col("h5") >= 1))
            ex10 = float((ge10["excess"] * ge10["n"]).sum() / ge10["n"].sum())
            print(f"   {var:7s} yearly corr {np.corrcoef(t, e)[0, 1]:.3f}  mean {e.mean():.4f} (true {t.mean():.4f})"
                  f"  >= 10 m excess {ex10:+.4f}  ({time.time() - t0:.0f}s)", flush=True)
    Z = pl.concat(rows)
    Z.write_csv(os.path.join(gi.EVAL, "mstransfer_zstats.csv"))
    L.write_csv(os.path.join(gi.EVAL, "mstransfer_levels.csv"))
    pl.concat(yrows).write_csv(os.path.join(gi.EVAL, "mstransfer_yearly.csv"))
    print("wrote mstransfer_{zstats,levels,yearly}.csv")


ABINS = (-0.5, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5)


def stage_anom():
    t0 = time.time()
    W, wcols = n2.weather()
    A = n2.Arm("MS")
    anom = [c for c in A.cols if c.startswith(("anom_", "ma_"))]
    WT = W.filter((pl.col("gcm") == REF) & (pl.col("seed") == 1) & pl.col("traj").is_in(["Historical", "ssp126",
                                                                                         "ssp370"]))
    lo = {c: float(WT[c].min()) for c in anom}
    hi = {c: float(WT[c].max()) for c in anom}
    print(f"MPI training range anom_tmean_ann_y1 {lo['anom_tmean_ann_y1']:.2f}..{hi['anom_tmean_ann_y1']:.2f}",
          flush=True)
    c2 = gi.cells200()
    rows = []
    for mem in nm.TEST:
        D = n2.y1_side(nm.load(mem, cells=c2, frac=n2.TEST_FRAC).join(W, on=n2.JOIN, how="left"))
        D = D.with_columns(thr=pl.when(pl.col("is_new_y").fill_null(False)).then(None).otherwise(pl.col("thr")))
        mu, s = A.pred(D.select(A.cols).to_numpy().astype(np.float32))
        D = D.with_columns(mu=pl.Series(mu), s=pl.Series(s)).filter(pl.col("Height") >= 15)
        outx = pl.any_horizontal([(pl.col(c) < lo[c]) | (pl.col(c) > hi[c]) for c in anom])
        D = D.with_columns(out=outx, ab=pl.Series(np.searchsorted(ABINS, D["anom_tmean_ann_y1"].to_numpy())),
                           neg=(pl.col("m") < 0).cast(pl.Float64),
                           p=pl.Series(norm.cdf((-D["mu"] / D["s"]).to_numpy())))
        per = sorted(((c, float(D.select(((pl.col(c) < lo[c]) | (pl.col(c) > hi[c])).mean()).item())) for c in anom),
                     key=lambda kv: -kv[1])[:4]
        G = (D.group_by("ab").agg(r_over_s=(pl.col("m") - pl.col("mu")).mean() / pl.col("s").mean(),
                                  excess=(pl.col("p") - pl.col("neg")).mean(), out_share=pl.col("out").mean(),
                                  a_mean=pl.col("anom_tmean_ann_y1").mean(), n=pl.len())
             .sort("ab").with_columns(member=pl.lit(mem)))
        Gi = (D.filter(~pl.col("out")).select(r_over_s=(pl.col("m") - pl.col("mu")).mean() / pl.col("s").mean(),
                                              n=pl.len()))
        rows.append(G)
        print(f"{mem}: >= 15 m rows {D.height}, any anomaly input out of range {float(D['out'].mean()):.3f} (top "
              + ", ".join(f"{k} {v:.3f}" for k, v in per) + f"); r/s on in-range rows {Gi['r_over_s'][0]:+.3f} "
              f"(n {Gi['n'][0]})  ({time.time() - t0:.0f}s)", flush=True)
        print(G.drop("member").with_columns(pl.col(pl.Float64).round(3)), flush=True)
    pl.concat(rows).write_csv(os.path.join(gi.EVAL, "mstransfer_anom.csv"))
    print("wrote mstransfer_anom.csv")


if __name__ == "__main__":
    if sys.argv[1:] == ["anom"]:
        stage_anom()
    else:
        main()
