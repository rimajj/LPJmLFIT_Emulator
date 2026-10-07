"""explore_de_gmargin.py — LINE X, Germany emulator: can the per-tree MARGIN model carry the year-to-year swings of the
growth-efficiency MAGNITUDE? One step, no stepper. (pre-registration: /p/tmp/jamirp/X_de/_status/TS.md, "GM")

Identity (explore_de_bmdelta.side): L_y1 = gain_y1 - G_y1 la_y1, m = log(gain_y1 / L_y1)  =>  G_y1 = r_y1 (1 - e^-m)
with r = gain / la (NPP per leaf area). Arms on the I9/I11 test rows (explore_de_nppmodel2), one margin draw per tree:
  T   truth;  RM  true r_y1 x drawn m;  PM  last year's r_y x drawn m (stepper-feasible: r_y = G_y / (1 - e^thr))
Usage: python explore_de_gmargin.py [ARM ...]   (margin arms, default MS) -> shared/eval/gmargin_yearly.csv
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_bmdelta as bd  # noqa: E402
import explore_de_gsign_info as gi  # noqa: E402
import explore_de_nppmodel as nm  # noqa: E402
import explore_de_nppmodel2 as n2  # noqa: E402

M_CLIP = 10.0


def leaf_area(s: str) -> pl.Expr:
    k = pl.when(pl.col("Type").is_in(bd.NEEDLE)).then(bd.K_NL).otherwise(bd.K_BL)
    lai, fpc = pl.col(f"LAI{s}").cast(pl.Float64), pl.col(f"fpc_ind{s}").cast(pl.Float64)
    return lai * fpc * bd.PATCHAREA / (1 - (-k * lai).exp())


def main(arms: list[str]):
    t0 = time.time()
    W, wcols = n2.weather()
    A = {a: n2.Arm(a) for a in arms}
    c2 = gi.cells200()
    rng = np.random.default_rng(23)
    rows = []
    for mem in nm.TEST:
        D = n2.y1_side(nm.load(mem, cells=c2, frac=n2.TEST_FRAC).join(W, on=n2.JOIN, how="left"))
        assert D[wcols[0]].null_count() == 0
        D = D.with_columns(thr=pl.when(pl.col("is_new_y").fill_null(False)).then(None).otherwise(pl.col("thr")),
                           la=leaf_area(""), la_y1=leaf_area("_y1"))
        D = D.with_columns(r=pl.col("gain") / pl.col("la"), r_y1=pl.col("gain_y1") / pl.col("la_y1"))
        G = D["G_y1"].to_numpy().astype(np.float64)
        r1, r0, m = D["r_y1"].to_numpy(), D["r"].to_numpy(), D["m"].to_numpy()
        ident = r1 * (1 - np.exp(-m))
        ok = np.abs(m) < M_CLIP - 1e-9  # m is clipped at gain >= GAIN_EPS in y1_side; the identity holds elsewhere
        err = np.abs(ident[ok] - G[ok]) / np.maximum(np.abs(G[ok]), 1e-3)
        print(f"{mem}: {D.height} trees; identity max rel err {err.max():.2e} (99.9 % {np.quantile(err, 0.999):.2e})",
              flush=True)
        out = D.select("Year", "Height", G_true=pl.col("G_y1").cast(pl.Float64))
        z = rng.standard_normal(D.height)
        for a, M in A.items():
            mu, s = M.pred(D.select(M.cols).to_numpy().astype(np.float32))
            md = np.clip(mu + s * z, -M_CLIP, M_CLIP)
            out = out.with_columns(pl.Series(f"RM_{a}", r1 * (1 - np.exp(-md))),
                                   pl.Series(f"PM_{a}", r0 * (1 - np.exp(-md))))
        out = out.with_columns(hcls=pl.when(pl.col("Height") < 10).then(pl.lit("lt10"))
                               .when(pl.col("Height") < 15).then(pl.lit("10-15"))
                               .when(pl.col("Height") < 25).then(pl.lit("15-25")).otherwise(pl.lit("ge25")))
        vals = [c for c in out.columns if c.startswith(("G_", "RM_", "PM_"))]
        for cls, flt in (("15-25", pl.col("hcls") == "15-25"), ("lt10", pl.col("hcls") == "lt10"),
                         ("all", pl.lit(True))):
            Y = (out.filter(flt).group_by("Year").agg(pl.col(vals).mean(), n=pl.len()).sort("Year")
                 .with_columns(member=pl.lit(mem), cls=pl.lit(cls)))
            rows.append(Y)
            t = Y["G_true"].to_numpy()
            for c in vals[1:]:
                e = Y[c].to_numpy()
                print(f"   {cls:6s} {c:10s} corr {np.corrcoef(t, e)[0, 1]:.3f}  slope "
                      f"{np.cov(t, e)[0, 1] / t.var(ddof=1):.3f}  mean {e.mean():.2f} (true {t.mean():.2f})",
                      flush=True)
        print(f"   ({time.time() - t0:.0f}s)", flush=True)
    path = os.path.join(gi.EVAL, "gmargin_yearly.csv")
    pl.concat(rows, how="diagonal_relaxed").write_csv(path)
    print("wrote", path)


if __name__ == "__main__":
    main(sys.argv[1:] or ["MS"])
