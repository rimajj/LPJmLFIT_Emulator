#!/usr/bin/env python3
"""explore_glob_a7r.py -- LINE X, the direct window map on the GLOBAL venue (ADR 0315, split GS370) in the DEPLOYMENT
setting: cells seen in training, only the RUN (member 8) and the SCENARIO (ssp370) held out.

Why (explore_panel_a7.py `core`): every score on this venue so far held out the cells as well (5 spatial folds), while
the lookup null (0.100) reads the same test cells from the training runs. An emulator inside an ESM is trained on the
original's runs of every cell and then runs those cells under a new climate and a new random draw, so holding out the
cell tests a requirement the goal does not have. Both settings stay reported; the thresholds do not change.

One variable per step, all on GS370 (train members 2,3,4,6 x {historical, ssp126, ssp245}; test member 8, ssp370 and its
own 1985-2014 baseline; 5 809 dev cells, scored by explore_glob_eval.score):
  A7s       the published arm (spatially cross-fitted; re-run here so all rows share one process) -- must reproduce
            ADR 0315 sec. 8: pass 0.131, biomass per tree 1.124 (harness check, |diff| < 0.003).
  A7s-seen  same features, trained on all dev cells.
  A7r       + per-cell anchor: per quantity, the mean over the training runs x training legs {h1985, ssp126, ssp245}
            of the same cell (leave-one-leg-out in training rows); dclim = the leg's 30-yr climate minus the anchor
            legs' climate; memoff = the run's own 1985-2014 value minus the training runs' 1985-2014 mean. Target =
            value minus anchor. A7rcb: its climate-blind twin (the leg's climate replaced by the cell's 1985-2014 one).

WRITTEN BEFORE THE RUN (ADR 0184):
  harness   A7s reproduces sec. 8 (above).
  E1  A7s-seen pass >= 0.131 + 0.01.
  E2  A7r passes DP-G1 (a) as amended (>= 0.140 AND > 0.100) and (b) (stems and biomass per tree within +-10 %), and
      (c) its deattenuated tree-count response slope exceeds A7rcb's by > 0.2.
  Falsifier: A7r pass <= 0.110 (no better than the lookup + 0.01) -- per-cell memory plus climate adds nothing usable.
Output: billing_global/eval/scores_A7r_GS370.csv

RESULT OF THE FIRST RUN (job 2451596): harness FAILED as written (A7s 0.1267 vs 0.131); A7s-seen 0.1355 (E1 failed by
0.005); A7r 0.1386 (E2 (a) missed by 0.0014) with biomass per tree NaN (a cell with no anchor -> fixed: such cells use
the arm's own direct model). Diagnosed (job 2451605): two fits in one process are bit-identical, but a re-run of the
published A7s in a new process gives 0.1241 vs the stored 0.1307 with the same inputs and code -- polars group_by order
changes the row order, and LightGBM's row bagging then draws different rows. ADR 0315's numbers carry a draw noise of
at least +-0.004 in pass rate that was never measured.

SECOND RUN (pre-registered before it, 2026-10-09): rows sorted (deterministic), every variant fitted with LightGBM seeds
1-5; the verdict uses the MEAN over the five seeds, the spread is reported beside it. Expectations unchanged (E1, E2,
falsifier). The harness check becomes: the A7s seed mean within 2 seed-sd of the stored 0.1307.

THIRD RUN, `--train 2,3,4,6,7` (pre-registered before it, 2026-10-09): the data lever on THIS venue with data on disk.
Member 7 (the replica that sets the tolerance) becomes a fifth training run of the same build; it carries no
information about member 8. Expected from the panel runs curve (ADR 0316 sec. 6): A7r +0.005 to +0.01 over the
4-run 0.1401 (5-seed means). Falsifier: < +0.003 (the global venue does not respond to more runs).
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_glob_a7 as A7  # noqa: E402
import explore_glob_eval as ev  # noqa: E402

PANEL, CLIM_COLS = ev.PANEL, A7.CLIM_COLS
ANCHOR_LEGS = ("historical", "ssp126", "ssp245")


TRAIN = tuple(int(x) for x in os.environ.get("A7R_TRAIN", ",".join(map(str, ev.TRAIN))).split(","))


def anchored(df: pl.DataFrame) -> pl.DataFrame:
    base = df.filter(pl.col("seed").is_in(list(TRAIN)) & pl.col("scen").is_in(list(ANCHOR_LEGS)))
    vals = PANEL + CLIM_COLS
    tot = base.group_by("Cell").agg([pl.col(v).sum().alias(f"S_{v}") for v in vals]
                                    + [pl.col(v).count().alias(f"N_{v}") for v in vals])
    per = base.group_by(["Cell", "scen"]).agg([pl.col(v).sum().alias(f"s_{v}") for v in vals]
                                              + [pl.col(v).count().alias(f"n_{v}") for v in vals])
    out = df.join(tot, on="Cell", how="left").join(per, on=["Cell", "scen"], how="left")
    out = out.with_columns([pl.col(f"s_{v}").fill_null(0.0) for v in vals] + [pl.col(f"n_{v}").fill_null(0) for v in vals])
    ex = []
    for v in vals:
        den = pl.col(f"N_{v}") - pl.col(f"n_{v}")
        ex.append(pl.when(den > 0).then((pl.col(f"S_{v}") - pl.col(f"s_{v}")) / den).otherwise(None).alias(f"anc_{v}"))
    out = out.with_columns(ex).with_columns(
        [(pl.col(c) - pl.col(f"anc_{c}")).alias(f"dclim_{c}") for c in CLIM_COLS]
        + [(pl.col(f"{c}_cb") - pl.col(f"anc_{c}")).alias(f"dclim_{c}_cb") for c in CLIM_COLS])
    hm = (df.filter(pl.col("seed").is_in(list(TRAIN)) & (pl.col("scen") == "historical"))
          .group_by("Cell").agg([pl.col(q).mean().alias(f"hm_{q}") for q in PANEL]))
    out = out.join(hm, on="Cell", how="left").with_columns(
        [(pl.col(f"s0_{q}") - pl.col(f"hm_{q}")).alias(f"memoff_{q}") for q in PANEL])
    return out.drop([c for c in out.columns if c[:2] in ("S_", "N_", "s_", "n_") and c[2:] in vals])


def feats(variant):
    blind = variant.endswith("cb")
    clim = [f"{x}_cb" for x in CLIM_COLS] if blind else CLIM_COLS
    base = clim + ["lat", "lon", "soil_code"] + [f"s0_{q}" for q in PANEL]
    if not variant.startswith("A7r"):
        return base
    dcl = [f"dclim_{x}_cb" for x in CLIM_COLS] if blind else [f"dclim_{x}" for x in CLIM_COLS]
    return base + dcl + [f"anc_{q}" for q in PANEL] + [f"memoff_{q}" for q in PANEL]


def fit_seen(tr: pl.DataFrame, te: pl.DataFrame, variant: str) -> pl.DataFrame:
    import lightgbm as lgb

    resid, f = variant.startswith("A7r"), feats(variant)
    out = te.select("Cell", "scen")
    for q in PANEL:
        t = tr.filter(pl.col(q).is_not_null() & (pl.col(f"anc_{q}").is_not_null() if resid else pl.lit(True)))
        y = (t[q] - t[f"anc_{q}"]).to_numpy() if resid else t[q].to_numpy()
        m = lgb.train(A7.PARAMS, lgb.Dataset(t.select(f).to_numpy(), y), A7.ROUNDS)
        p = m.predict(te.select(f).to_numpy())
        if resid:  # where a cell has no anchor (no trees in any training run): the direct model of the same arm
            anc = te[f"anc_{q}"].to_numpy().astype(float)
            p = p + anc
            miss = ~np.isfinite(anc)
            if miss.any():
                f0 = feats("A7s-seen" if not variant.endswith("cb") else "A7scb")
                t0 = tr.filter(pl.col(q).is_not_null())
                m0 = lgb.train(A7.PARAMS, lgb.Dataset(t0.select(f0).to_numpy(), t0[q].to_numpy()), A7.ROUNDS)
                p[miss] = m0.predict(te.filter(pl.Series(miss)).select(f0).to_numpy())
        if q == "n_per_patch":
            p = np.maximum(p, 0.0)
        out = out.with_columns(pl.Series(q, p))
    return out


def main():
    t0 = time.time()
    cells = ev.dev_cells()
    rows0 = A7.build_rows(cells)
    extra = [m for m in TRAIN if m not in ev.TRAIN]
    for m in extra:  # a further training run of the same build (historical + the training scenarios)
        h = ev.lev(ev.mname("historical", m)).rename({q: f"s0_{q}" for q in PANEL})
        cw = A7.climate_windows(cells["Cell"].to_list())
        add = []
        for scen in ("historical", "ssp126", "ssp245"):
            y = ev.lev(ev.mname(scen, m))
            add.append(y.with_columns(pl.lit(m).alias("seed"), pl.lit(scen).alias("scen")).join(h, on="Cell")
                       .join(cw.filter(pl.col("scen") == scen).drop("scen"), on="Cell"))
        hist_clim = cw.filter(pl.col("scen") == "historical").drop("scen").rename({c: f"{c}_cb" for c in CLIM_COLS})
        st = pl.read_parquet(os.path.join(A7.CLIM, "cell_static.parquet")).select("Cell", "lon", "soil_code")
        rows0 = pl.concat([rows0, pl.concat(add).join(hist_clim, on="Cell").join(cells, on="Cell").join(st, on="Cell")
                           .select(rows0.columns)])
    df = anchored(rows0)
    T_w, T_h = ev.lev(ev.mname("ssp370", ev.TRUTH)), ev.lev(ev.mname("historical", ev.TRUTH))
    R_w, R_h = ev.lev(ev.mname("ssp370", ev.REPLICA)), ev.lev(ev.mname("historical", ev.REPLICA))
    tb = (T_w.filter(pl.col("n_per_patch") > 0).select("Cell")
          .vstack(T_h.filter(pl.col("n_per_patch") > 0).select("Cell")).unique())
    scored = cells.join(tb, on="Cell")
    df = df.sort(["seed", "scen", "Cell"])
    tr = df.filter(pl.col("seed").is_in(list(TRAIN)))
    te = df.filter(pl.col("seed") == ev.TRUTH)
    rows = []
    for sd in range(1, 6):
        A7.PARAMS["seed"] = sd
        preds = {"A7s": A7.fit_predict(df, "A7s")}
        for v in ("A7s-seen", "A7r", "A7rcb"):
            preds[v] = fit_seen(tr, te, v)
        for v, p in preds.items():
            pw = p.filter(pl.col("scen") == "ssp370").drop("scen")
            ph = p.filter(pl.col("scen") == "historical").drop("scen") if v == "A7s" else T_h
            s = ev.score(pw, ph, T_w, T_h, R_w, R_h, scored)
            rows.append(dict(split="GS370", arm=v, lgb_seed=sd, **s))
            ev.log(sd, v, {k: round(x, 4) for k, x in s.items() if isinstance(x, float) and k in (
                "pass_rate", "stems_ratio", "agb_per_stem_ratio", "resp_n_per_patch_slope_deatt")})
    d = pl.DataFrame(rows)
    tag = "" if TRAIN == tuple(ev.TRAIN) else "_train" + "".join(map(str, TRAIN))
    out = os.path.join(ev.EVAL, f"scores_A7r_GS370{tag}.csv")
    d.write_csv(out)
    num = [c for c, t in d.schema.items() if t.is_numeric() and c != "lgb_seed"]
    summ = d.group_by("arm").agg([pl.col(c).mean() for c in num] + [pl.col("pass_rate").std().alias("pass_sd")])
    summ.write_csv(os.path.join(ev.EVAL, f"scores_A7r_GS370{tag}_mean.csv"))
    with pl.Config(tbl_cols=10, float_precision=4):
        print(summ.select("arm", "pass_rate", "pass_sd", "pass_rate_flat10", "stems_ratio", "agb_per_stem_ratio",
                          "resp_n_per_patch_slope_deatt", "resp_Wooddens_q50_slope_deatt"))
    h = summ.filter(pl.col("arm") == "A7s")
    ok = abs(h["pass_rate"][0] - 0.1307) <= 2 * max(h["pass_sd"][0], 1e-9)
    ev.log(f"HARNESS A7s seed mean {h['pass_rate'][0]:.4f} +- {h['pass_sd'][0]:.4f} vs stored 0.1307: "
           f"{'PASS' if ok else 'FAIL'}; wrote {out} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
