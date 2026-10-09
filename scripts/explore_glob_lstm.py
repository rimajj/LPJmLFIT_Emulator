#!/usr/bin/env python3
"""explore_glob_lstm.py -- LINE X, arm A2g on the global venue (ADR 0315): the cell-level LSTM over YEARLY CELL
STATISTICS (the Germany C0 design, scripts/explore_de_rec_lstmstats.py), re-targeted to Billing's global runs.

What is new for the global venue: per-tree truth exists only in 1985-2014 and 2071-2100, never 2015-2070. So training
has two phases: (S) K-step free runs inside each 30-year segment (curriculum 1,3,5,10,20), then (F) the GAP-CROSSING
rollout -- teacher-forced from 1985 up to a random year <= 2014, free-running through 2015-2070 on that leg's GFDL-ESM4
climate, with the loss on every free-run year that has truth (the rest of 1985-2014 and all of 2071-2100). That is the
scored task itself (ADR 0315 sec. 3), learned on the TRAINING members only; it emits no tree roster.

SPLIT GS370 (ADR 0315 sec. 2): train = members 2,3,4,6 x {historical + ssp126, historical + ssp245}; model selection on
held-out 5x5-degree blocks of the training cells (15 %), never on member 7 (the ceiling) or 8 (the truth); test = member
8, cross-fitted over the 5 spatial folds (fold-k model predicts fold-k cells). ssp126/ssp245 predictions for member 8
are reported too (an unseen member on a training scenario, GM-like), ungated.

ARMS (one variable): lstm (real climate) and lstmCB (its climate-blind twin: every year's climate = the cell's
1985-2014 mean, anomalies 0, in training AND prediction).
STARTS: S14 = member 8's own 1985-2014 truth fed in, free from 2015 (the scored free run); S85 = member 8's 1985 truth
only, free from 1986 (the within-training free run, DP-G1 (d)).

STAGES
  yearly           per-member yearly statistics over the dev cells of every GFDL-ESM4 member-window
                   -> <DATA>/yearly/<member>.parquet
  train --fold k --arm A     fit, then predict member 8 (all starts, all three scenarios) -> <OUT>/<A>/f<k>.*
  score            window statistics -> the ADR 0315 panel -> eval/scores_A2g.csv (+ the replay harness check)

WHAT EACH MUST RETURN, written before the run (ADR 0184):
  replay   member 8's own yearly statistics pushed through the window aggregator and scored against member 8's
           levels: stems and biomass per stem identical (|rel| < 1e-6); pass rate >= 0.95 (the trait medians come
           from a mixture of yearly quantile functions, not the pooled stem-years, so not exactly 1). Below 0.95 the
           aggregator, not the arm, would set the score -- a harness failure.
  lstmCB   no climate signal: its 2071-2100 minus 1985-2014 change is pure free-run drift. Expected response slope
           ~0; a slope far from 0 measures drift, and is subtracted in reading (c).
  val      the best validation loss must beat carrying the 2014 state forward (`converged`); if not, the arm has
           learned nothing beyond persistence and its scores are not read as a method result.
  gates    DP-G1 as amended in ADR 0315 sec. 9 (a deterministic arm predicts the expectation): (a) pass >= 0.5 x
           ceiling_mean = 0.140 AND above the best null 0.100; (b) area-weighted stems and biomass per stem within
           +-10 %; (c) deattenuated tree-count response slope above lstmCB's by more than the member spread;
           (d) S85 at 2014 within +-10 % on both totals. Benchmark to beat: A7s (0.131, slope 0.63).

INPUT FILL (ADR 0315 sec. 14.1, 2026-10-09). The sec. 12/13 runs filled missing inputs forward AND backward over the
whole leg, so a cell treeless in 1985-2014 got its trait/share inputs from the test member's own 2071-2100 truth
(303 dev cells). Default is now --fill causal (forward only, in training AND prediction); --fill leaky reproduces the
published runs. The clean RETRAIN (--tag _causal) must return, written before the run: lstm pass ~0.125 (+-0.01) and a
deattenuated tree-count response slope near sec. 14.1's clean RE-PREDICTION of the leaky model, 0.65; lstmCB ~0.53.
Retraining is a new draw (A7's draw spread in pass is 0.003; the LSTM's is unmeasured), so read +-0.1 of slope as
"the same". A slope well BELOW 0.55 would mean the leaky model had learned something from the fill that the clean one
cannot recover; well ABOVE 0.75 would mean the backward fill had also been hurting it. The S85 free run (d) is now
leak-free for the first time; its 2014 totals may move either way.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_reference as R  # noqa: E402
import explore_glob_eval as ev  # noqa: E402
from explore_de_rec_lstmstats import _mixture_quantiles  # noqa: E402

YEARLY = os.path.join(ev.DATA, "yearly")
OUT = os.path.join(ev.EVAL, "arms", "A2g")
CLIMD = os.path.join(ev.DATA, "climate", "cell_year")
NPATCH = ev.NPATCH
NMIN_STEMYEARS = 30
TRAITS = ["SLA", "Wooddens", "D95max", "minwscal", "Height", "agb"]
LOGT = {"Height", "agb"}
PS = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
PN = ["p01", "p05", "p10", "p25", "p50", "p75", "p90", "p95", "p99"]
PFTS = list(range(7))
CLIM = [
    "tmean_ann",
    "tcold_month",
    "twarm_month",
    "gdd5",
    "frost_days",
    "days_gt30",
    "prec_ann",
    "prec_hs",
    "pet_ann",
    "cwb_ann",
    "cwb_hs",
    "cwb_min3",
    "dry_spell_max",
    "rh_mean",
    "vpd_hs",
    "vpd_win10_sum",
    "swdown_ann",
    "lwnet_ann",
    "tcold_month_tr20",
    "twarm_month_tr20",
    "gdd5_tr20",
] + [f"tstress_pft{k}" for k in PFTS]
Y0, Y1, YS, W0 = 1985, 2100, 2014, 2071
YEARS = np.arange(Y0, Y1 + 1)
T = len(YEARS)  # 116
I14, I71 = YS - Y0, W0 - Y0  # 29, 86
TRAIN_SCENS, TEST_SCENS = ("ssp126", "ssp245"), ("ssp126", "ssp245", "ssp370")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ------------------------------------------------------------------------------------------------ yearly statistics
def stage_yearly(_a) -> None:
    os.makedirs(YEARLY, exist_ok=True)
    m = pl.read_parquet(os.path.join(ev.REG, "members.parquet")).filter(pl.col("gcm") == "GFDL-ESM4")
    cells = ev.dev_cells()["Cell"].to_list()
    for i, r in enumerate(m.iter_rows(named=True)):
        if i % _a.nparts != _a.part:
            continue
        out = os.path.join(YEARLY, f"{r['member']}.parquet")
        if os.path.exists(out):
            continue
        t0 = time.time()
        y0, y1 = ev.WIN[r["window"]]
        lf = (
            pl.scan_parquet(r["ind_dev_path"])
            .filter(pl.col("Year").is_between(y0, y1) & pl.col("Cell").is_in(cells))
            .select(
                pl.col("Year").cast(pl.Int32),
                pl.col("Cell").cast(pl.Int32),
                pl.col("Type").cast(pl.Int8),
                pl.col("isdead").cast(pl.Int8),
                *[pl.col(v).cast(pl.Float64) for v in TRAITS],
            )
        )
        aggs = [pl.len().alias("n_living"), pl.col("agb").sum().alias("agb_sum")]
        aggs += [(pl.col("Type") == t).sum().alias(f"n_t{t}") for t in PFTS]
        aggs += [
            pl.col(v).quantile(p, interpolation="linear").alias(f"{v}_{pn}")
            for v in TRAITS
            for p, pn in zip(PS, PN, strict=True)
        ]
        g = R.living(lf).group_by(["Cell", "Year"]).agg(aggs).collect()
        assert g.select("Cell", "Year").n_unique() == g.height, "duplicate (Cell, Year)"
        census = pl.DataFrame(
            {
                "Cell": np.repeat(cells, y1 - y0 + 1).astype(np.int32),
                "Year": np.tile(np.arange(y0, y1 + 1), len(cells)).astype(np.int32),
            }
        )
        assert g.join(census, on=["Cell", "Year"], how="anti").height == 0, "rows outside the dev census"
        d = census.join(g, on=["Cell", "Year"], how="left").with_columns(
            pl.col("n_living").fill_null(0),
            pl.col("agb_sum").fill_null(0.0),
            *[pl.col(f"n_t{t}").fill_null(0) for t in PFTS],
        )
        d = d.with_columns(
            (pl.col("n_living") / NPATCH).alias("n_per_patch"),
            (pl.col("agb_sum") / NPATCH).alias("agb_stand"),
            *[
                pl.when(pl.col("n_living") > 0)
                .then(pl.col(f"n_t{t}") / pl.col("n_living"))
                .otherwise(None)
                .alias(f"share_{t}")
                for t in PFTS
            ],
        )
        d.sort("Cell", "Year").write_parquet(out)
        log(f"{r['member']}: {d.height} rows ({time.time() - t0:.0f}s)")


# ------------------------------------------------------------------------------------------------ window aggregation
def window_stats(Y: pl.DataFrame, y0: int, y1: int) -> pl.DataFrame:
    """Yearly statistics (Cell, Year, n_per_patch, agb_stand, {v}_{pn}) -> the ADR 0315 panel over [y0, y1]."""
    Y = Y.filter(pl.col("Year").is_between(y0, y1)).sort("Cell", "Year")
    rows = []
    for (cell,), g in Y.group_by(["Cell"], maintain_order=True):
        n = np.clip(g["n_per_patch"].to_numpy().astype(float), 0, None)
        sy = n * NPATCH
        r = {"Cell": cell, "n_per_patch": float(n.mean())}
        agb = float(np.clip(g["agb_stand"].to_numpy().astype(float), 0, None).mean())
        r["agb_per_stem"] = agb / r["n_per_patch"] if r["n_per_patch"] > 0 else None
        for v in ("SLA", "Wooddens", "D95max", "minwscal"):
            qv = np.stack([g[f"{v}_{pn}"].to_numpy().astype(float) for pn in PN], axis=1)
            ok = np.all(np.isfinite(qv), axis=1) & (sy > 0)
            r[f"{v}_q50"] = (
                float(_mixture_quantiles(qv[ok], sy[ok], probs=[0.5])[0])
                if sy.sum() >= NMIN_STEMYEARS and ok.any()
                else None
            )
        rows.append(r)
    return pl.DataFrame(rows, schema={"Cell": pl.Int32, **{q: pl.Float64 for q in ev.PANEL}})


# ------------------------------------------------------------------------------------------------ tensors
def to_z(Y: pl.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    n = Y["n_per_patch"].to_numpy().astype(float)
    cols = [np.log(n + 0.05), np.log(Y["agb_stand"].to_numpy().astype(float) + 1.0)]
    cols += [Y[f"share_{t}"].to_numpy().astype(float) for t in PFTS]
    for v in TRAITS:
        for pn in PN:
            x = Y[f"{v}_{pn}"].to_numpy().astype(float)
            cols.append(np.log(np.maximum(x, 1e-3)) if v in LOGT else x)
    X = np.stack(cols, axis=1)
    W = np.ones_like(X)
    W[:, :2] = 3.0
    W[:, 2:] = np.clip(Y["n_living"].to_numpy().astype(float) / 20.0, 0, 1)[:, None]
    W[~np.isfinite(X)] = 0.0
    return X, np.nan_to_num(W)


def from_z(X: np.ndarray) -> dict[str, np.ndarray]:
    out = {
        "n_per_patch": np.clip(np.exp(X[..., 0]) - 0.05, 0, None),
        "agb_stand": np.clip(np.exp(X[..., 1]) - 1.0, 0, None),
    }
    k = 9
    for v in TRAITS:
        q = X[..., k : k + len(PN)]
        q = np.sort(np.exp(q) if v in LOGT else q, axis=-1)
        for j, pn in enumerate(PN):
            out[f"{v}_{pn}"] = q[..., j]
        k += len(PN)
    return out


def ffill(X: np.ndarray) -> np.ndarray:
    """The ADR 0315 sec. 12/13 input fill: forward, then BACKWARD over the whole leg. LEAKS (sec. 14.1): a value missing
    in all of 1985-2014 (a treeless cell has no trait quantiles or shares) is back-filled from that leg's 2071-2100
    truth, and the S85 start's 1985 input from any later year. Kept only to reproduce the published runs (--fill leaky,
    scripts/explore_glob_clock.py)."""
    X = X.copy()
    for t in range(1, X.shape[1]):
        m = ~np.isfinite(X[:, t])
        X[:, t][m] = X[:, t - 1][m]
    for t in range(X.shape[1] - 2, -1, -1):
        m = ~np.isfinite(X[:, t])
        X[:, t][m] = X[:, t + 1][m]
    return X


def fill_causal(X: np.ndarray) -> np.ndarray:
    """Forward fill only, along T: the input of year t carries a value from a year <= t or stays NaN (the caller then
    puts the training mean there). Same in training and prediction, so no input can see a later year's truth."""
    X = X.copy()
    for t in range(1, X.shape[1]):
        m = ~np.isfinite(X[:, t])
        X[:, t][m] = X[:, t - 1][m]
    return X


FILL = {"causal": fill_causal, "leaky": ffill}


def full_state(seed: int, scen: str, cells: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """(cells, T, D) state for historical 1985-2014 + scen 2071-2100, NaN (weight 0) in 2015-2070."""
    d = pl.concat(
        [pl.read_parquet(os.path.join(YEARLY, f"{ev.mname(s, seed)}.parquet")) for s in ("historical", scen)],
        how="vertical_relaxed",
    )
    census = pl.DataFrame(
        {"Cell": np.repeat(cells, T).astype(np.int32), "Year": np.tile(YEARS, len(cells)).astype(np.int32)}
    )
    d = census.join(d, on=["Cell", "Year"], how="left").sort("Cell", "Year")
    X, W = to_z(d)
    return X.reshape(len(cells), T, -1), W.reshape(len(cells), T, -1)


_CLIM: dict = {}


def climate(scen: str, cells: list[int], mode: str) -> np.ndarray:
    key = (scen, mode)
    if key not in _CLIM:

        def tab(s, y0, y1):
            return (
                pl.scan_parquet(os.path.join(CLIMD, f"GFDL-ESM4_{s}.parquet"))
                .filter(pl.col("Cell").is_in(cells) & pl.col("Year").is_between(y0, y1))
                .select(
                    pl.col("Cell").cast(pl.Int32),
                    pl.col("Year").cast(pl.Int32),
                    *[pl.col(c).cast(pl.Float64) for c in CLIM],
                )
                .collect()
            )

        c = pl.concat([tab("historical", Y0, YS), tab(scen, YS + 1, Y1)])
        census = pl.DataFrame(
            {"Cell": np.repeat(cells, T).astype(np.int32), "Year": np.tile(YEARS, len(cells)).astype(np.int32)}
        )
        lev = census.join(c, on=["Cell", "Year"], how="left").sort("Cell", "Year").select(CLIM).to_numpy()
        lev = lev.reshape(len(cells), T, len(CLIM))
        assert np.all(np.isfinite(lev)), f"missing climate {scen}"
        cm = lev[:, : I14 + 1].mean(axis=1, keepdims=True)
        if mode == "frozen":
            lev = np.repeat(cm, T, axis=1)
        _CLIM[key] = np.concatenate([lev, lev - cm], axis=2).astype(np.float32)
    return _CLIM[key]


def static(cells: list[int]) -> np.ndarray:
    s = pl.read_parquet(os.path.join(ev.DATA, "climate", "cell_static.parquet"))
    codes = sorted(s.filter(~pl.col("rock"))["soil_code"].unique().to_list())
    s = pl.DataFrame({"Cell": np.asarray(cells, dtype=np.int32)}).join(
        s.with_columns(pl.col("Cell").cast(pl.Int32)), on="Cell", how="left"
    )
    code, lat, lon = (s[c].to_numpy().astype(float) for c in ("soil_code", "lat", "lon"))
    cols = [(code == k).astype(float) for k in codes] + [lat / 90.0, np.sin(np.deg2rad(lon)), np.cos(np.deg2rad(lon))]
    return np.stack(cols, axis=1).astype(np.float32)


# ------------------------------------------------------------------------------------------------ model
def make_model(d_state: int, d_in: int, hidden: int = 128, layers: int = 2):
    import torch

    nn = torch.nn

    class LSTMStats(nn.Module):
        def __init__(self):
            super().__init__()
            self.lstm = nn.LSTM(d_in, hidden, num_layers=layers, batch_first=True)
            self.head = nn.Linear(hidden, d_state)
            nn.init.zeros_(self.head.weight)
            nn.init.zeros_(self.head.bias)

        def step(self, inp, hc):
            o, hc = self.lstm(inp[:, None, :], hc)
            return self.head(o[:, 0]), hc

    return LSTMStats()


def rollout(model, Z, C, S, t_free, n_steps):
    """Inputs at step t: state t (truth if t < t_free, else own), climate t+1, static; P[:, t] = state t+1."""
    import torch

    hc, z, preds = None, Z[:, 0], []
    for t in range(n_steps):
        zin = torch.where((t < t_free)[:, None], Z[:, t], z) if t > 0 else Z[:, 0]
        dz, hc = model.step(torch.cat([zin, C[:, t + 1], S], dim=1), hc)
        z = zin + dz
        preds.append(z)
    return torch.stack(preds, dim=1)


def wloss(P, Z, W, mask):
    """Weighted squared error of P[:, t] against Z[:, t+1] over the (S, n_steps) mask."""
    n = P.shape[1]
    w = W[:, 1 : n + 1] * mask[:, :, None]
    return (((P - Z[:, 1 : n + 1]) ** 2) * w).sum() / w.sum().clamp_min(1e-9)


# ------------------------------------------------------------------------------------------------ train + predict
def stage_train(a) -> None:
    import torch

    torch.set_num_threads(int(os.environ.get("SLURM_CPUS_PER_TASK", "8")))
    torch.manual_seed(1000 + a.fold)
    rng = np.random.default_rng(1000 + a.fold)
    mode = "frozen" if a.arm == "lstmCB" else "real"
    folds = ev.dev_cells().join(
        pl.read_parquet(os.path.join(ev.REG, "folds.parquet")).select("Cell", "block"), on="Cell"
    )
    cells = folds["Cell"].to_list()
    tr_c = folds.filter(pl.col("fold") != a.fold)
    blocks = sorted(tr_c["block"].unique().to_list())
    vblocks = set(rng.choice(blocks, size=max(1, round(0.15 * len(blocks))), replace=False).tolist())
    is_va = tr_c["block"].is_in(list(vblocks)).to_numpy()
    idx_all = {c: i for i, c in enumerate(cells)}
    i_tr = np.array([idx_all[c] for c in tr_c["Cell"].to_numpy()[~is_va]])
    i_va = np.array([idx_all[c] for c in tr_c["Cell"].to_numpy()[is_va]])
    S_all = static(cells)

    Xs, Ws, Cs, Ss, tags = [], [], [], [], []
    for seed in a.train_seeds:
        for scen in TRAIN_SCENS:
            X, W = full_state(seed, scen, cells)
            Xs.append(X)
            Ws.append(W)
            Cs.append(climate(scen, cells, mode))
            Ss.append(S_all)
            tags.append((seed, scen))
    X, W, C, Sx = (np.stack(v) for v in (Xs, Ws, Cs, Ss))  # (M, cells, T, .)
    flat = lambda A, ii: A[:, ii].reshape(-1, *A.shape[2:])  # noqa: E731
    Xtr = flat(X, i_tr)
    mu, sd = np.nanmean(Xtr.reshape(-1, X.shape[-1]), axis=0), np.nanstd(Xtr.reshape(-1, X.shape[-1]), axis=0)
    sd = np.where(sd > 1e-6, sd, 1.0)
    Ctr = flat(C, i_tr).reshape(-1, C.shape[-1])
    cmu, csd = Ctr.mean(axis=0), Ctr.std(axis=0)
    csd = np.where(csd > 1e-9, csd, 1.0)
    del Ctr

    def tens(ii):
        Xf = FILL[a.fill](flat(X, ii))
        Xf = np.where(np.isfinite(Xf), Xf, mu)
        return (
            torch.tensor((Xf - mu) / sd, dtype=torch.float32),
            torch.tensor((flat(C, ii) - cmu) / csd, dtype=torch.float32),
            torch.tensor(flat(Sx, ii), dtype=torch.float32),
            torch.tensor(flat(W, ii), dtype=torch.float32),
        )

    Ztr, Ctr_, Str, Wtr = tens(i_tr)
    Zva, Cva, Sva, Wva = tens(i_va)
    # segment views for phase S: the historical segment once per (member, cell), each scenario's 2071-2100 segment
    hist_once = (
        torch.arange(0, Ztr.shape[0])
        .reshape(len(tags), -1)[[i for i, t in enumerate(tags) if t[1] == TRAIN_SCENS[0]]]
        .ravel()
    )
    segs = [
        (Ztr[hist_once, : I14 + 1], Ctr_[hist_once, : I14 + 1], Str[hist_once], Wtr[hist_once, : I14 + 1]),
        (Ztr[:, I71:], Ctr_[:, I71:], Str, Wtr[:, I71:]),
    ]
    Zs_, Cs_, Ss_, Ws_ = (torch.cat([s[k] for s in segs]) for k in range(4))
    D, F = Ztr.shape[2], Ctr_.shape[2]
    log(
        f"fold {a.fold} arm {a.arm}: train seq {Ztr.shape[0]}, val seq {Zva.shape[0]}, segments {Zs_.shape[0]}"
    )
    model = make_model(D, D + F + Str.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=a.lr, weight_decay=1e-5)

    def val():
        with torch.no_grad():
            n = Zva.shape[0]
            tf = torch.full((n,), I14 + 1, dtype=torch.long)
            mask = torch.zeros(n, T - 1)
            mask[:, I71 - 1 :] = 1.0  # targets 2071-2100
            lv = float(wloss(rollout(model, Zva, Cva, Sva, tf, T - 1), Zva, Wva, mask))
            Pp = Zva[:, I14 : I14 + 1].expand(-1, T - 1, -1)
            lp = float(wloss(Pp, Zva, Wva, mask))
        return lv, lp

    hist, best, it, t0 = [], (np.inf, None, None), 0, time.time()
    for K in (1, 3, 5, 10, 20):
        for _ in range(a.iters):
            b = torch.randint(0, Zs_.shape[0], (a.batch,))
            tf = torch.randint(1, I14 + 2 - K, (a.batch,))
            nst = int(tf.max()) - 1 + K
            tg = torch.arange(nst)[None, :]
            mask = ((tg >= (tf - 1)[:, None]) & (tg < (tf - 1 + K)[:, None])).float()
            loss = wloss(rollout(model, Zs_[b], Cs_[b], Ss_[b], tf, nst), Zs_[b], Ws_[b], mask)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            it += 1
        lv, lp = val()
        hist.append(
            {
                "phase": f"S{K}",
                "it": it,
                "train": float(loss),
                "val": lv,
                "val_persist": lp,
                "sec": round(time.time() - t0),
            }
        )
        log(json.dumps(hist[-1]))
    for g in opt.param_groups:
        g["lr"] = a.lr * 0.3
    for _ in range(a.iters_full):
        b = torch.randint(0, Ztr.shape[0], (a.batch_full,))
        tf = torch.randint(1, I14 + 2, (a.batch_full,))
        mask = (torch.arange(T - 1)[None, :] >= (tf - 1)[:, None]).float()
        loss = wloss(rollout(model, Ztr[b], Ctr_[b], Str[b], tf, T - 1), Ztr[b], Wtr[b], mask)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        it += 1
        if it % 100 == 0:
            lv, lp = val()
            hist.append(
                {
                    "phase": "F",
                    "it": it,
                    "train": float(loss),
                    "val": lv,
                    "val_persist": lp,
                    "sec": round(time.time() - t0),
                }
            )
            log(json.dumps(hist[-1]))
            if lv < best[0]:
                best = (lv, it, {k: v.detach().clone() for k, v in model.state_dict().items()})
    if best[2] is not None:
        model.load_state_dict(best[2])
    lv, lp = val()
    d = os.path.join(OUT, a.arm + a.tag)
    os.makedirs(d, exist_ok=True)
    torch.save({"state": model.state_dict(), "mu": mu, "sd": sd, "cmu": cmu, "csd": csd}, f"{d}/f{a.fold}.pt")
    info = {
        "arm": a.arm,
        "fold": a.fold,
        "clim_mode": mode,
        "fill": a.fill,
        "best_it": best[1],
        "val_best": lv,
        "val_persist": lp,
        "converged": bool(lv < lp),
        "train_seconds": round(time.time() - t0),
        "history": hist,
        "args": dict(vars(a)),
    }
    json.dump(info, open(f"{d}/f{a.fold}.json", "w"), indent=1)
    log(f"trained: val {lv:.4f} vs persistence {lp:.4f} (best it {best[1]})")

    # ---- predict member 8 on this fold's cells
    i_te = np.array([idx_all[c] for c in folds.filter(pl.col("fold") == a.fold)["Cell"].to_list()])
    te_cells = [cells[i] for i in i_te]
    model.eval()
    out, timing = [], {}
    for scen in TEST_SCENS:
        X8, _ = full_state(a.test_seed, scen, cells)
        X8 = X8[i_te]
        Xf = FILL[a.fill](X8)
        Xf = np.where(np.isfinite(Xf), Xf, mu)
        Z = torch.tensor((Xf - mu) / sd, dtype=torch.float32)
        Cc = torch.tensor((climate(scen, cells, mode)[i_te] - cmu) / csd, dtype=torch.float32)
        Sc = torch.tensor(S_all[i_te])
        for start, tfree in (("S14", I14 + 1), ("S85", 1)):
            nthr = torch.get_num_threads()
            torch.set_num_threads(1)
            t1 = time.time()
            with torch.no_grad():
                P = rollout(model, Z, Cc, Sc, torch.full((len(i_te),), tfree, dtype=torch.long), T - 1).numpy()
            timing[f"{scen}_{start}"] = (time.time() - t1) / (len(i_te) * (T - 1))
            torch.set_num_threads(nthr)
            phys = from_z(P * sd + mu)  # years 1986..2100
            df = pl.DataFrame(
                {
                    "Cell": np.repeat(te_cells, T - 1).astype(np.int32),
                    "Year": np.tile(YEARS[1:], len(te_cells)).astype(np.int32),
                    **{k: v.reshape(-1) for k, v in phys.items()},
                }
            )
            out.append(df.with_columns(pl.lit(scen).alias("scen"), pl.lit(start).alias("start")))
    pl.concat(out).write_parquet(f"{d}/f{a.fold}_pred.parquet")
    info["core_s_per_cell_year"] = timing
    json.dump(info, open(f"{d}/f{a.fold}.json", "w"), indent=1)
    log(f"predicted {len(te_cells)} cells; core-s per cell-year {timing}")


# ------------------------------------------------------------------------------------------------ score
def stage_score(a) -> None:
    TR, RP = a.test_seed, a.replica
    cells = ev.dev_cells()
    T_h, R_h = ev.lev(ev.mname("historical", TR)), ev.lev(ev.mname("historical", RP))
    T14, R14 = ev.lev(ev.mname("historical", TR), "_y2014"), ev.lev(ev.mname("historical", RP), "_y2014")
    first = (
        pl.read_parquet(os.path.join(YEARLY, f"{ev.mname('historical', TR)}.parquet"))
        .filter(pl.col("Year") == Y0)
        .select("Cell", "Year", "n_per_patch", "agb_stand", *[f"{v}_{pn}" for v in TRAITS for pn in PN])
    )
    rows = []

    def emit(name, scen, s, **kw):
        rows.append(dict(split="GM-like" if scen in TRAIN_SCENS else "GS370", test_scen=scen, baseline=name, **kw, **s))
        log(
            name,
            scen,
            {
                k: round(v, 4)
                for k, v in s.items()
                if isinstance(v, float)
                and k
                in (
                    "pass_rate",
                    "pass_rate_flat10",
                    "stems_ratio",
                    "agb_per_stem_ratio",
                    "resp_n_per_patch_slope_deatt",
                    "resp_Wooddens_q50_slope_deatt",
                )
            },
        )

    # harness check: the truth's own yearly statistics through this aggregator
    yr8 = {s: pl.read_parquet(os.path.join(YEARLY, f"{ev.mname(s, TR)}.parquet")) for s in ("historical", "ssp370")}
    rep_w, rep_h = window_stats(yr8["ssp370"], W0, Y1), window_stats(yr8["historical"], Y0, YS)
    T_w, R_w = ev.lev(ev.mname("ssp370", TR)), ev.lev(ev.mname("ssp370", RP))
    sc = cells.join(
        pl.concat([d.filter(pl.col("n_per_patch") > 0).select("Cell") for d in (T_w, T_h)]).unique(), on="Cell"
    )
    emit("replay_truth", "ssp370", ev.score(rep_w, rep_h, T_w, T_h, R_w, R_h, sc))
    j = rep_w.join(T_w, on="Cell", suffix="_T").filter(pl.col("n_per_patch_T") > 0)
    rel = {q: float(((j[q] - j[f"{q}_T"]).abs() / j[f"{q}_T"].abs()).max()) for q in ("n_per_patch", "agb_per_stem")}
    log(f"HARNESS replay max rel diff {rel}")

    for arm in a.arms:
        d = os.path.join(OUT, arm + a.tag)
        P = pl.concat([pl.read_parquet(f"{d}/f{k}_pred.parquet") for k in range(1, 6)])
        infos = [json.load(open(f"{d}/f{k}.json")) for k in range(1, 6)]
        meta = dict(
            converged_folds=sum(i["converged"] for i in infos),
            core_s_per_cell_year=float(np.median([i["core_s_per_cell_year"]["ssp370_S14"] for i in infos])),
        )
        for scen in TEST_SCENS:
            T_w, R_w = ev.lev(ev.mname(scen, TR)), ev.lev(ev.mname(scen, RP))
            sc = cells.join(
                pl.concat([x.filter(pl.col("n_per_patch") > 0).select("Cell") for x in (T_w, T_h)]).unique(), on="Cell"
            )
            for start in ("S14", "S85"):
                p = P.filter((pl.col("scen") == scen) & (pl.col("start") == start))
                pw = window_stats(p, W0, Y1)
                ph = (
                    T_h
                    if start == "S14"
                    else window_stats(pl.concat([first, p.drop("scen", "start")], how="diagonal_relaxed"), Y0, YS)
                )
                emit(f"{arm}_{start}", scen, ev.score(pw, ph, T_w, T_h, R_w, R_h, sc), **meta)
                if start == "S85" and scen == "ssp370":
                    sch = cells.join(T_h.filter(pl.col("n_per_patch") > 0).select("Cell"), on="Cell")
                    s = ev.score(ph, ph, T_h, T_h, R_h, R_h, sch)
                    emit(f"{arm}_S85_h1985", "historical", {k: v for k, v in s.items() if not k.startswith("resp_")})
                    p14 = window_stats(p, YS, YS)
                    s = ev.score(p14, p14, T14, T14, R14, R14, sch)
                    emit(f"{arm}_S85_y2014", "historical", {k: v for k, v in s.items() if not k.startswith("resp_")})
    out = os.path.join(ev.EVAL, f"scores_A2g{a.tag}.csv")
    pl.DataFrame(rows, infer_schema_length=None).write_csv(out)
    log(f"wrote {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["yearly", "train", "score"])
    ap.add_argument("--fold", type=int, default=1)
    ap.add_argument("--arm", default="lstm", choices=["lstm", "lstmCB"])
    ap.add_argument("--arms", type=lambda x: x.split(","), default=["lstm", "lstmCB"])
    ap.add_argument(
        "--train-seeds", dest="train_seeds", type=lambda x: [int(v) for v in x.split(",")], default=list(ev.TRAIN)
    )
    ap.add_argument("--test-seed", dest="test_seed", type=int, default=ev.TRUTH)
    ap.add_argument("--replica", type=int, default=ev.REPLICA)
    ap.add_argument("--tag", default="", help="suffix of the arm directory and score file (per-version runs)")
    ap.add_argument("--fill", default="causal", choices=list(FILL), help="input fill (ADR 0315 sec. 14.1)")
    ap.add_argument("--iters", type=int, default=400)
    ap.add_argument("--iters-full", dest="iters_full", type=int, default=2000)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--batch", type=int, default=512)
    ap.add_argument("--batch-full", dest="batch_full", type=int, default=256)
    ap.add_argument("--part", type=int, default=0)
    ap.add_argument("--nparts", type=int, default=1)
    a = ap.parse_args()
    {"yearly": stage_yearly, "train": stage_train, "score": stage_score}[a.stage](a)
    log("=== DONE")


if __name__ == "__main__":
    main()
