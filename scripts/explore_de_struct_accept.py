"""explore_de_struct_accept.py — LINE X, Germany emulator, STRUCT track: a minimal B4 acceptance
filter (pre-registration /p/tmp/jamirp/X_de/_status/SD.md, arm `acc`).

The B3 kernel proposes recruit identities (type + traits) the original model would mostly never
carry to the 5 m print height. This learns that filter: LightGBM binary classifier, label 1 =
observed printed recruits, label 0 = the kernel's own proposals for the same cell-years (the stored
B3 proposal sample, struct/kernel/<member>/proposals_sample.parquet, cells % 50 == 0, establishment
2015-2034). Inputs: Type (categorical), SLA, Wooddens, D95max, minwscal, Longevity, beta_root and
the cell's 1985-2014 climatology of the run's GCM (annual temperature, precipitation, gdd5,
summer water balance). Training member(s) only; folds 1-4 train, fold 5 validation.

STAGES  fit [--member M]  -> struct/accept/<split>/model.txt + meta.json (validation log-loss vs
        the base rate, per-Type acceptance shares)
CLASS   Accept.load(split, gcm=...) ; weights(props, ctx) -> p / (1 - p)   (the stepper's hook:
        kwargs {"accept": "explore_de_struct_accept:Accept", "accept_kwargs": {"gcm": G}})
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_struct_heads as hd  # noqa: E402
import explore_de_struct_kernel as kn  # noqa: E402

XDE = os.environ.get("XDE_ROOT", "/p/tmp/jamirp/X_de")
OUT = os.path.join(XDE, "struct", "accept")
TRAITS = ["SLA", "Wooddens", "D95max", "minwscal", "Longevity", "beta_root"]
CLIM = ["c8_tann", "c8_pann", "c8_gdd5", "c8_cwb_jja"]
FEATS = ["Type"] + TRAITS + CLIM


def cell_clim(gcm: str) -> pl.DataFrame:
    c = hd.clim8514().filter(pl.col("gcm") == gcm)
    t = [f"c8_temp_m{m:02d}" for m in range(1, 13)]
    p = [f"c8_prec_m{m:02d}" for m in range(1, 13)]
    return c.select(
        pl.col("Cell").cast(pl.Int32),
        c8_tann=pl.mean_horizontal(t),
        c8_pann=pl.sum_horizontal(p),
        c8_gdd5=pl.col("c8_gdd5"),
        c8_cwb_jja=pl.col("c8_cwb_jja"),
    )


def stage_fit(a):
    import lightgbm as lgb

    gcm = a.member.split("_")[0]
    P = pl.read_parquet(os.path.join(kn.OUT, a.member, "proposals_sample.parquet")).select(
        pl.col("Cell").cast(pl.Int32), pl.col("Type").cast(pl.Int32), *TRAITS
    )
    R = (
        pl.scan_parquet(os.path.join(kn.RECR, a.member, "cb=dev", "*.parquet"))
        .filter(
            (pl.col("Cell") % 50 == 0)
            & pl.col("Year_entry").is_between(2015, 2034)
            & (pl.col("Type") <= 6)
        )
        .select(pl.col("Cell").cast(pl.Int32), pl.col("Type").cast(pl.Int32), *TRAITS)
        .collect()
    )
    D = pl.concat(
        [P.with_columns(y=pl.lit(0)), R.with_columns(y=pl.lit(1))], how="vertical_relaxed"
    ).join(cell_clim(gcm), on="Cell", how="left")
    fo = hd.folds().select(pl.col("Cell").cast(pl.Int32), "fold")
    D = D.join(fo, on="Cell", how="inner")
    X = D.select([pl.col(c).cast(pl.Float64) for c in FEATS]).to_numpy()
    y = D["y"].to_numpy()
    tr = D["fold"].to_numpy() != 5
    print(f"proposals {P.height}, recruits {R.height}, train {tr.sum()}, valid {(~tr).sum()}")
    prm = dict(
        objective="binary",
        learning_rate=0.05,
        num_leaves=63,
        min_data_in_leaf=200,
        feature_fraction=0.9,
        bagging_fraction=0.8,
        bagging_freq=1,
        lambda_l2=1.0,
        verbose=-1,
        seed=20261006,
        deterministic=True,
        num_threads=a.threads,
    )
    dtr = lgb.Dataset(X[tr], y[tr], feature_name=FEATS, categorical_feature=["Type"])
    dva = lgb.Dataset(X[~tr], y[~tr], reference=dtr)
    bst = lgb.train(
        prm, dtr, 2000, valid_sets=[dva], callbacks=[lgb.early_stopping(50, verbose=False)]
    )
    p = bst.predict(X[~tr], num_iteration=bst.best_iteration)
    base = y[tr].mean()
    ll = float(-np.mean(y[~tr] * np.log(p + 1e-12) + (1 - y[~tr]) * np.log(1 - p + 1e-12)))
    ll0 = float(-np.mean(y[~tr] * np.log(base) + (1 - y[~tr]) * np.log(1 - base)))
    # per-Type: observed recruit share vs reweighted proposal share on the validation fold
    pv = bst.predict(X, num_iteration=bst.best_iteration)
    w = pv / (1 - pv)
    Dv = D.with_columns(w=pl.Series(w)).filter(pl.col("fold") == 5)
    obs = (
        Dv.filter(pl.col("y") == 1)
        .group_by("Type")
        .len()
        .with_columns(obs=pl.col("len") / pl.col("len").sum())
    )
    prop = Dv.filter(pl.col("y") == 0).group_by("Type").agg(n=pl.len(), w=pl.col("w").sum())
    prop = prop.with_columns(
        raw=pl.col("n") / pl.col("n").sum(), rew=pl.col("w") / pl.col("w").sum()
    )
    tab = (
        obs.select("Type", "obs")
        .join(prop.select("Type", "raw", "rew"), on="Type", how="full", coalesce=True)
        .fill_null(0)
        .sort("Type")
    )
    print(tab)
    od = os.path.join(OUT, a.split)
    os.makedirs(od, exist_ok=True)
    bst.save_model(os.path.join(od, "model.txt"), num_iteration=bst.best_iteration)
    meta = {
        "member": a.member,
        "features": FEATS,
        "best_iteration": bst.best_iteration,
        "valid_logloss": ll,
        "valid_logloss_base_rate": ll0,
        "train_base_rate": float(base),
        "type_shares_valid": tab.to_dicts(),
    }
    json.dump(meta, open(os.path.join(od, "meta.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in meta.items() if k != "type_shares_valid"}, indent=1))


class Accept:
    def __init__(self, split: str = "DEV-A", gcm: str = "ACCESS-CM2"):
        import lightgbm as lgb

        self.b = lgb.Booster(model_file=os.path.join(OUT, split, "model.txt"))
        cc = cell_clim(gcm)
        self.clim = {int(r["Cell"]): [r[c] for c in CLIM] for r in cc.iter_rows(named=True)}

    @classmethod
    def load(cls, split: str = "DEV-A", **kw):
        return cls(split, **kw)

    def weights(self, props: dict, ctx: dict) -> np.ndarray:
        n = len(props["Type"])
        cl = np.tile(np.asarray(self.clim[int(ctx["Cell"])], np.float64), (n, 1))
        X = np.column_stack(
            [np.asarray(props["Type"], np.float64)]
            + [np.asarray(props[k], np.float64) for k in TRAITS]
            + [cl]
        )
        p = np.clip(self.b.predict(X), 1e-6, 1 - 1e-6)
        return p / (1 - p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["fit"])
    ap.add_argument("--split", default="DEV-A")
    ap.add_argument("--member", default="MPI-ESM1-2-HR_ssp370_s1_w2015")
    ap.add_argument("--threads", type=int, default=8)
    a = ap.parse_args()
    stage_fit(a)


if __name__ == "__main__":
    main()
