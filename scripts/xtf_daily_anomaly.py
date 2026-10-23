"""ADR 0368 section 7.1, POST-HOC (not pre-registered): do the daily-memory arms track the original's
year-to-year departures? Per cell, departure = annual value minus that cell's 2021-2100 linear trend; the
correlation of emulated with original departures, pooled over cells and years, per leg and member; the
original's own second run scored the same way. Median over legs, mean over seeds.
Reads esm_land_emulator_data/xtf/daily/runs/<arm>_s<seed>/annual.npz; writes anomaly.csv beside score.csv."""

import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xtf_daily as X  # noqa: E402

YRS = slice(1, 81)


def departures(a):
    t = np.arange(a.shape[1], dtype=np.float64)
    tc = t - t.mean()
    slope = ((a - a.mean(1, keepdims=True)) * tc).sum(1, keepdims=True) / (tc**2).sum()
    return a - a.mean(1, keepdims=True) - slope * tc


def corr(x, y):
    x, y = x.ravel(), y.ravel()
    ok = np.isfinite(x) & np.isfinite(y)
    return float(np.corrcoef(x[ok], y[ok])[0, 1])


def main():
    cells = pl.read_parquet(f"{X.F2N}/cells.parquet")
    ho = cells["heldout"].to_numpy()
    rows = []
    for r in sorted(r for r in os.listdir(f"{X.OUT}/runs") if os.path.exists(f"{X.OUT}/runs/{r}/annual.npz")):
        z = np.load(f"{X.OUT}/runs/{r}/annual.npz")
        arm, seed = r.rsplit("_s", 1)
        legs = sorted({k.split("__")[2] for k in z.files if k.startswith("free__m3__") and "co2fix" not in k})
        for grp, gl, cm in (("heldout x heldout-GCM", X.TEST_GCMS, ho), ("heldout x train-GCM", X.TRAIN_GCMS, ho),
                            ("train cells x all", X.TRAIN_GCMS + X.TEST_GCMS, ~ho)):  # fmt: skip
            for v in ("gpp", "npp", "et", "runoff"):
                rE, rR = [], []
                for lg in [lg for lg in legs if lg.rsplit("_", 1)[0] in gl]:
                    gpp = (z[f"truth__m2__{lg}__gpp"][:, YRS].mean(1) + z[f"truth__m3__{lg}__gpp"][:, YRS].mean(1)) / 2
                    m = cm & (gpp >= 50)
                    for k, j in X.PAIRS:
                        T = departures(z[f"truth__m{k}__{lg}__{v}"][m, YRS].astype(np.float64))
                        E = departures(z[f"free__m{k}__{lg}__{v}"][m, YRS].astype(np.float64))
                        R = departures(z[f"truth__m{j}__{lg}__{v}"][m, YRS].astype(np.float64))
                        rE.append(corr(E, T))
                        rR.append(corr(R, T))
                rows.append({"arm": arm, "seed": int(seed), "group": grp, "flux": v,
                             "r_emulator": float(np.median(rE)), "r_second_run": float(np.median(rR))})  # fmt: skip
    df = pl.DataFrame(rows)
    df.write_csv(f"{X.OUT}/anomaly.csv")
    s = df.group_by("group", "flux", "arm").agg(
        pl.col("r_emulator").mean(), (pl.col("r_emulator").max() - pl.col("r_emulator").min()).alias("spread"),
        pl.col("r_second_run").mean()).sort("group", "flux", "arm")  # fmt: skip
    with pl.Config(tbl_rows=60, float_precision=3):
        print(s)


if __name__ == "__main__":
    main()
