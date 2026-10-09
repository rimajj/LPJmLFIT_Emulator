#!/usr/bin/env python3
"""explore_panel_lstm.py -- LINE X: the cell-level recurrent arm (A2g, ADR 0315 sec. 12/15) on the PANEL VENUE
(explore_panel_prep.py). Same model, state encoding, causal input fill and window aggregator as the global arm (imported
from explore_glob_lstm.py); what changes is the data: per-tree truth EVERY year 2000-2100 (no gap to bridge), 5
climate models x 3 scenarios, and a constant-climate control whose drawn weather years are known exactly.

SEQUENCES: (member, leg) = observed 2000-2019 (the `hist` leg) + that leg 2020-2100, T = 101. Legs: the 15 model x
scenario legs and ctl_obs (its 2020-2100 weather = observed years drawn with replacement from 1990-2019; the draw
sequence is recovered per member from the run's own daily precipitation, exact to 0.0 mm on every day, identical
across the 105 blocks of a member). ctl_mpi370 has no daily output, its draws are unknown -> not used here.
Climate per year = the explore_panel_prep feature set (CLIM of explore_glob_lstm; *_tr20 recomputed along the actual
sequence) + its anomaly to the cell's 2000-2019 mean. lstmCB (climate-blind twin): every year's climate = that mean.

TRAINING: members 1-3 on the split's training legs; folds by 10-cell block (5), 15 % of the training blocks held out for
model selection; phase S = K-step free runs at random starts (K = 1, 3, 5, 10, 20), phase F = free run from a random
year <= 2019 to 2100, loss on every free year. TEST: member 4 on the held-out fold's cells, free from 2020 with its own
2000-2019 truth fed in (S19), and free from 2001 with only its 2000 state (S00: the within-training check, scored at
2019 on stems and biomass per tree).

SPLITS: HG:<g> (held-out climate model; train = other 4 models x 3 scenarios + ctl_obs) ; H585G:<g> (also ssp585 never
seen: train = other 4 x {126, 370} + ctl_obs). Arms: lstm, lstmCB (HG only).

WRITTEN BEFORE THE RUN (ADR 0184):
  replay   m4's own yearly statistics through the window aggregator against m4's levels: stems and biomass per stem
           identical (rel < 1e-6), pass >= 0.95 -- else the aggregator sets the score (harness failure).
  val      every fold model beats carrying the 2019 state forward on its validation blocks (`converged`).
  lstmCB   its response relative to ctl_obs (scenario - control) is ~0 on the aggregate (|agg| < 0.25): with the climate
           frozen, the ssp and control sequences differ only in ... nothing (same frozen climate, same start) => EXACTLY
           0 is required for the scenario-minus-control contrast; any non-zero value is a harness bug.
  E1  (calendar removed): the real arm's scenario - control tree-count response, deattenuated slope, >= 0.5 on HG
           ssp370 for >= 4 of 5 held-out models (global venue: scenario contrast slope 0.47 with no control to learn).
  E2  (level): on HG the real arm passes the bar (0.5 x ceiling_mean AND above the best null of explore_panel_a7) on
           ssp370 for >= 3 of 5 models, area totals within +-10 %.
  E3  (coverage): on ssp585, H585G is worse than HG by >= 0.02 in pass or >= 3 points in biomass-per-tree error.
  FALSIFIER: if lstm on HG does not beat A7s (same split, explore_panel_a7) in pass on >= 3 of 5 models AND its
           scenario-minus-control slope is not above A7s's, the recurrent arm has no advantage even with full-coverage data.
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
import explore_glob_lstm as GL  # noqa: E402
import explore_panel_a7 as PA  # noqa: E402
import explore_panel_prep as PP  # noqa: E402
from build_transient_boundary import open_clm  # noqa: E402

YEARLY = os.path.join(PP.OUT, "yearly")
OUT = os.path.join(PP.OUT, "arms", "lstm")
NPATCH = PP.NPATCH
Y0, Y1, YS, W0 = 2000, 2100, 2019, 2071
YEARS = np.arange(Y0, Y1 + 1)
T = len(YEARS)  # 101
I19, I71 = YS - Y0, W0 - Y0  # 19, 71
CLIM = GL.CLIM
TRAITS, PN, PS, PFTS = GL.TRAITS, GL.PN, GL.PS, GL.PFTS
TRAIN_M, TRUTH, REPLICA = (1, 2, 3), 4, 3
SEQ_LEGS = [*PP.SLEGS, *PP.NEW_SLEGS, "ctl_obs"]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ------------------------------------------------------------------------------------------------ yearly statistics
def stage_yearly(a) -> None:
    os.makedirs(YEARLY, exist_ok=True)
    cells = PP.cells()["Cell"].to_list()
    jobs = [(m, lg) for m in PP.MEMBERS for lg in ["hist", *SEQ_LEGS]]
    for i, (m, lg) in enumerate(jobs):
        if i % a.nparts != a.part:
            continue
        out = os.path.join(YEARLY, f"m{m}_{lg}.parquet")
        td = PP.table_dir(m, lg)
        if os.path.exists(out) or td is None:
            continue
        path = os.path.join(td, "ind.parquet")
        t0 = time.time()
        y0, y1 = (2000, 2019) if lg == "hist" else (2020, 2100)
        blocks = list(range(105)) if lg == "hist" else PP.complete_blocks(m, lg)
        cl = PP.cells().filter(pl.col("block").is_in(blocks))["Cell"].to_list()
        lf = (pl.scan_parquet(path).filter(pl.col("Year").is_between(y0, y1) & pl.col("Cell").is_in(cl))
              .select(pl.col("Year").cast(pl.Int32), pl.col("Cell").cast(pl.Int32), pl.col("Type").cast(pl.Int8),
                      pl.col("isdead").cast(pl.Int8), *[pl.col(v).cast(pl.Float64) for v in TRAITS]))
        aggs = [pl.len().alias("n_living"), pl.col("agb").sum().alias("agb_sum")]
        aggs += [(pl.col("Type") == t).sum().alias(f"n_t{t}") for t in PFTS]
        aggs += [pl.col(v).quantile(p, interpolation="linear").alias(f"{v}_{pn}")
                 for v in TRAITS for p, pn in zip(PS, PN, strict=True)]
        g = R.living(lf).group_by(["Cell", "Year"]).agg(aggs).collect()
        assert g.select("Cell", "Year").n_unique() == g.height, "duplicate (Cell, Year)"
        census = pl.DataFrame({"Cell": np.repeat(cl, y1 - y0 + 1).astype(np.int32),
                               "Year": np.tile(np.arange(y0, y1 + 1), len(cl)).astype(np.int32)})
        assert g.join(census, on=["Cell", "Year"], how="anti").height == 0, "rows outside the census"
        d = census.join(g, on=["Cell", "Year"], how="left").with_columns(
            pl.col("n_living").fill_null(0), pl.col("agb_sum").fill_null(0.0),
            *[pl.col(f"n_t{t}").fill_null(0) for t in PFTS])
        d = d.with_columns((pl.col("n_living") / NPATCH).alias("n_per_patch"),
                           (pl.col("agb_sum") / NPATCH).alias("agb_stand"),
                           *[pl.when(pl.col("n_living") > 0).then(pl.col(f"n_t{t}") / pl.col("n_living"))
                             .otherwise(None).alias(f"share_{t}") for t in PFTS])
        d.sort("Cell", "Year").write_parquet(out)
        log(f"m{m} {lg}: {d.height} rows, {len(cl)} cells ({time.time() - t0:.0f}s)")
    _ = cells


# ------------------------------------------------------------------------------------------------ control draws
def ctl_sequence(m: int) -> list[int]:
    """Observed year drawn for each of 2020-2100 in member m's ctl_obs run, from its daily precipitation (exact)."""
    f = os.path.join(PP.OUT, "ctl_obs_draws.json")
    have = json.load(open(f)) if os.path.exists(f) else {}
    if str(m) in have:
        return have[str(m)]
    mm, fy, *_ = open_clm(PP.OBS["prec"])
    c = PP.cells()
    probe = c.group_by("block").agg(pl.col("Cell").min()).sort("block")["Cell"].to_list()[::15]  # 7 blocks
    d = (pl.scan_parquet(os.path.join(PP.table_dir(m, "ctl_obs"), "daily.parquet"))
         .filter(pl.col("Cell").is_in(probe)).select("Cell", "Year", "Day", "prec").collect().sort("Cell", "Year", "Day"))
    pool = np.array([[np.asarray(mm[y - fy][cell], dtype=np.float64) for cell in probe] for y in range(1990, 2020)])
    seq = []
    for y in range(2020, 2101):
        v = np.stack([d.filter((pl.col("Cell") == cell) & (pl.col("Year") == y))["prec"].to_numpy() for cell in probe])
        err = np.abs(pool - v[None]).max(axis=(1, 2))
        k = int(err.argmin())
        assert err[k] < 1e-4 and np.sort(err)[1] > 1e-2, (m, y, float(err[k]), float(np.sort(err)[1]))
        seq.append(1990 + k)
    have[str(m)] = seq
    json.dump(have, open(f, "w"))
    return seq


# ------------------------------------------------------------------------------------------------ tensors
def full_state(m: int, leg: str, cells: list[int], start_only: bool = False):
    """start_only: the leg's own table may be missing (prediction needs only the 2000-2019 start)."""
    parts = [os.path.join(YEARLY, f"m{m}_hist.parquet"), os.path.join(YEARLY, f"m{m}_{leg}.parquet")]
    if start_only:
        parts = [p for p in parts if os.path.exists(p)]
    if not all(os.path.exists(p) for p in parts):
        return None, None
    d = pl.concat([pl.read_parquet(p) for p in parts], how="vertical_relaxed")
    census = pl.DataFrame({"Cell": np.repeat(cells, T).astype(np.int32), "Year": np.tile(YEARS, len(cells)).astype(np.int32)})
    d = census.join(d, on=["Cell", "Year"], how="left").sort("Cell", "Year")
    X, W = GL.to_z(d.with_columns(pl.col("n_living").fill_null(0)))
    X, W = X.reshape(len(cells), T, -1), W.reshape(len(cells), T, -1)
    W[~np.isfinite(X)] = 0.0  # a leg missing for some blocks: no loss there
    return X, W


_CLIM: dict = {}


def climate(m: int, leg: str, cells: list[int], mode: str) -> np.ndarray:
    key = (m if leg == "ctl_obs" else 0, leg, mode)
    if key in _CLIM:
        return _CLIM[key]
    base = [c.replace("_tr20", "") for c in CLIM if c.endswith("_tr20")]
    raw = [c for c in CLIM if not c.endswith("_tr20")]
    h = pl.read_parquet(os.path.join(PP.CLIM_DIR, "hist.parquet")).select("Cell", "Year", *raw)
    if leg == "ctl_obs":
        pool = pl.read_parquet(os.path.join(PP.CLIM_DIR, "ctl_obs_pool.parquet")).select("Cell", "Year", *raw)
        seq = pl.DataFrame({"Year": np.arange(2020, 2101, dtype=np.int32), "src": np.array(ctl_sequence(m), np.int32)})
        s = seq.join(pool.rename({"Year": "src"}), on="src").drop("src")
    else:
        s = pl.read_parquet(os.path.join(PP.CLIM_DIR, f"{leg}.parquet")).select("Cell", "Year", *raw)
    c = pl.concat([h, s.select(h.columns)]).sort("Cell", "Year")
    # trailing 20-yr means along the actual sequence (hist 2000-2019 has its own stored values from 1981 on)
    htr = pl.read_parquet(os.path.join(PP.CLIM_DIR, "hist.parquet")).select("Cell", "Year", *[f"{b}_tr20" for b in base])
    c = c.with_columns([pl.col(b).cast(pl.Float64).rolling_mean(20).over("Cell").alias(f"{b}_tr20") for b in base])
    c = c.join(htr, on=["Cell", "Year"], how="left", suffix="_h").with_columns(
        [pl.coalesce(pl.col(f"{b}_tr20_h"), pl.col(f"{b}_tr20")).alias(f"{b}_tr20") for b in base]
    ).drop([f"{b}_tr20_h" for b in base])
    census = pl.DataFrame({"Cell": np.repeat(cells, T).astype(np.int32), "Year": np.tile(YEARS, len(cells)).astype(np.int32)})
    lev = census.join(c, on=["Cell", "Year"], how="left").sort("Cell", "Year").select(CLIM).to_numpy().astype(np.float64)
    lev = lev.reshape(len(cells), T, len(CLIM))
    assert np.all(np.isfinite(lev)), f"missing climate {leg}"
    cm = lev[:, : I19 + 1].mean(axis=1, keepdims=True)
    if mode == "frozen":
        lev = np.repeat(cm, T, axis=1)
    _CLIM[key] = np.concatenate([lev, lev - cm], axis=2).astype(np.float32)
    return _CLIM[key]


def static(cells: list[int]) -> np.ndarray:
    s = PP.cells()
    codes = sorted(s["soil_code"].unique().to_list())
    s = pl.DataFrame({"Cell": np.asarray(cells, dtype=np.int32)}).join(s, on="Cell", how="left")
    code, lat, lon = (s[c].to_numpy().astype(float) for c in ("soil_code", "lat", "lon"))
    cols = [(code == k).astype(float) for k in codes] + [lat / 90.0, np.sin(np.deg2rad(lon)), np.cos(np.deg2rad(lon))]
    return np.stack(cols, axis=1).astype(np.float32)


def split_legs(split: str) -> tuple[list[str], list[str]]:
    kind, g = split.split(":")
    other = [lg for lg in PP.SLEGS if lg.rsplit("_", 1)[0] != g]
    if kind == "HG":
        return other + ["ctl_obs"], [f"{g}_{s}" for s in PP.SCENS] + ["ctl_obs"]
    if kind == "H585G":
        return [lg for lg in other if not lg.endswith("ssp585")] + ["ctl_obs"], [f"{g}_ssp585", "ctl_obs"]
    raise SystemExit(split)


# ------------------------------------------------------------------------------------------------ train + predict
def stage_train(a) -> None:
    import torch

    torch.set_num_threads(int(os.environ.get("SLURM_CPUS_PER_TASK", "8")))
    torch.manual_seed(1000 + a.fold)
    rng = np.random.default_rng(1000 + a.fold)
    mode = "frozen" if a.arm == "lstmCB" else "real"
    train_legs, test_legs = split_legs(a.split)
    cdf = PP.cells()
    cells = cdf["Cell"].to_list()
    tr_c = cdf.filter(pl.col("fold") != a.fold)
    blocks = sorted(tr_c["block"].unique().to_list())
    vblocks = set(rng.choice(blocks, size=max(1, round(0.15 * len(blocks))), replace=False).tolist())
    is_va = tr_c["block"].is_in(list(vblocks)).to_numpy()
    idx_all = {c: i for i, c in enumerate(cells)}
    i_tr = np.array([idx_all[c] for c in tr_c["Cell"].to_numpy()[~is_va]])
    i_va = np.array([idx_all[c] for c in tr_c["Cell"].to_numpy()[is_va]])
    S_all = static(cells)
    Xs, Ws, Cs = [], [], []
    for m in TRAIN_M:
        for leg in train_legs:
            X, W = full_state(m, leg, cells)
            if X is None:
                log(f"no table m{m} {leg} -- skipped")
                continue
            Xs.append(X)
            Ws.append(W)
            Cs.append(climate(m, leg, cells, mode))
    X, W, C = (np.stack(v) for v in (Xs, Ws, Cs))  # (M, cells, T, .)
    Sx = np.repeat(S_all[None], X.shape[0], axis=0)
    flat = lambda A, ii: A[:, ii].reshape(-1, *A.shape[2:])  # noqa: E731
    Xtr = flat(X, i_tr)
    mu, sd = np.nanmean(Xtr.reshape(-1, X.shape[-1]), axis=0), np.nanstd(Xtr.reshape(-1, X.shape[-1]), axis=0)
    sd = np.where(sd > 1e-6, sd, 1.0)
    Ctr = flat(C, i_tr).reshape(-1, C.shape[-1])
    cmu, csd = Ctr.mean(axis=0), Ctr.std(axis=0)
    csd = np.where(csd > 1e-9, csd, 1.0)
    del Ctr

    def tens(ii):
        Xf = GL.fill_causal(flat(X, ii))
        Xf = np.where(np.isfinite(Xf), Xf, mu)
        return (torch.tensor((Xf - mu) / sd, dtype=torch.float32),
                torch.tensor((flat(C, ii) - cmu) / csd, dtype=torch.float32),
                torch.tensor(flat(Sx, ii), dtype=torch.float32), torch.tensor(flat(W, ii), dtype=torch.float32))

    Ztr, Ctr_, Str, Wtr = tens(i_tr)
    Zva, Cva, Sva, Wva = tens(i_va)
    D, F = Ztr.shape[2], Ctr_.shape[2]
    log(f"{a.split} fold {a.fold} arm {a.arm}: {len(Xs)} sequences x cells; train {Ztr.shape[0]}, val {Zva.shape[0]}")
    model = GL.make_model(D, D + F + Str.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=a.lr, weight_decay=1e-5)

    def val():
        with torch.no_grad():
            n = Zva.shape[0]
            tf = torch.full((n,), I19 + 1, dtype=torch.long)
            mask = torch.zeros(n, T - 1)
            mask[:, I19:] = 1.0  # every free year 2020-2100
            lv = float(GL.wloss(GL.rollout(model, Zva, Cva, Sva, tf, T - 1), Zva, Wva, mask))
            Pp = Zva[:, I19 : I19 + 1].expand(-1, T - 1, -1)
            lp = float(GL.wloss(Pp, Zva, Wva, mask))
        return lv, lp

    hist, best, it, t0 = [], (np.inf, None, None), 0, time.time()
    for K in (1, 3, 5, 10, 20):
        for _ in range(a.iters):
            b = torch.randint(0, Ztr.shape[0], (a.batch,))
            tf = torch.randint(1, T - K, (a.batch,))
            nst = int(tf.max()) - 1 + K
            tg = torch.arange(nst)[None, :]
            mask = ((tg >= (tf - 1)[:, None]) & (tg < (tf - 1 + K)[:, None])).float()
            loss = GL.wloss(GL.rollout(model, Ztr[b], Ctr_[b], Str[b], tf, nst), Ztr[b], Wtr[b], mask)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            it += 1
        lv, lp = val()
        hist.append({"phase": f"S{K}", "it": it, "train": float(loss), "val": lv, "val_persist": lp,
                     "sec": round(time.time() - t0)})
        log(json.dumps(hist[-1]))
    for g in opt.param_groups:
        g["lr"] = a.lr * 0.3
    for _ in range(a.iters_full):
        b = torch.randint(0, Ztr.shape[0], (a.batch_full,))
        tf = torch.randint(1, I19 + 2, (a.batch_full,))
        mask = (torch.arange(T - 1)[None, :] >= (tf - 1)[:, None]).float()
        loss = GL.wloss(GL.rollout(model, Ztr[b], Ctr_[b], Str[b], tf, T - 1), Ztr[b], Wtr[b], mask)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        it += 1
        if it % 100 == 0:
            lv, lp = val()
            hist.append({"phase": "F", "it": it, "train": float(loss), "val": lv, "val_persist": lp,
                         "sec": round(time.time() - t0)})
            log(json.dumps(hist[-1]))
            if lv < best[0]:
                best = (lv, it, {k: v.detach().clone() for k, v in model.state_dict().items()})
    if best[2] is not None:
        model.load_state_dict(best[2])
    lv, lp = val()
    d = os.path.join(OUT, a.split.replace(":", "_"), a.arm)
    os.makedirs(d, exist_ok=True)
    torch.save({"state": model.state_dict(), "mu": mu, "sd": sd, "cmu": cmu, "csd": csd}, f"{d}/f{a.fold}.pt")
    info = {"split": a.split, "arm": a.arm, "fold": a.fold, "clim_mode": mode, "best_it": best[1], "val_best": lv,
            "val_persist": lp, "converged": bool(lv < lp), "train_seconds": round(time.time() - t0),
            "train_legs": train_legs, "history": hist, "args": dict(vars(a))}
    log(f"trained: val {lv:.4f} vs persistence {lp:.4f} (best it {best[1]})")

    i_te = np.array([idx_all[c] for c in cdf.filter(pl.col("fold") == a.fold)["Cell"].to_list()])
    te_cells = [cells[i] for i in i_te]
    model.eval()
    out, timing = [], {}
    for leg in test_legs:
        X4, _ = full_state(TRUTH, leg, cells, start_only=True)
        if X4 is None:
            log(f"no truth table m{TRUTH} {leg} -- not predicted")
            continue
        X4[:, I19 + 1 :] = np.nan  # the test member's own 2020-2100 truth is never an input
        Xf = GL.fill_causal(X4[i_te])
        Xf = np.where(np.isfinite(Xf), Xf, mu)
        Z = torch.tensor((Xf - mu) / sd, dtype=torch.float32)
        Cc = torch.tensor((climate(TRUTH, leg, cells, mode)[i_te] - cmu) / csd, dtype=torch.float32)
        Sc = torch.tensor(S_all[i_te])
        for start, tfree in (("S19", I19 + 1), ("S00", 1)):
            nthr = torch.get_num_threads()
            torch.set_num_threads(1)
            t1 = time.time()
            with torch.no_grad():
                P = GL.rollout(model, Z, Cc, Sc, torch.full((len(i_te),), tfree, dtype=torch.long), T - 1).numpy()
            timing[f"{leg}_{start}"] = (time.time() - t1) / (len(i_te) * (T - 1))
            torch.set_num_threads(nthr)
            phys = GL.from_z(P * sd + mu)  # years 2001..2100
            out.append(pl.DataFrame({"Cell": np.repeat(te_cells, T - 1).astype(np.int32),
                                     "Year": np.tile(YEARS[1:], len(te_cells)).astype(np.int32),
                                     **{k: v.reshape(-1) for k, v in phys.items()}})
                       .with_columns(pl.lit(leg).alias("leg"), pl.lit(start).alias("start")))
    pl.concat(out).write_parquet(f"{d}/f{a.fold}_pred.parquet")
    info["core_s_per_cell_year"] = timing
    json.dump(info, open(f"{d}/f{a.fold}.json", "w"), indent=1)
    log(f"predicted {len(te_cells)} cells")


# ------------------------------------------------------------------------------------------------ score
def window_stats(Y, y0, y1):
    GL.NPATCH = NPATCH
    return GL.window_stats(Y, y0, y1)


def stage_score(a) -> None:
    cells = PP.cells().select("Cell", "lat")
    rows = []
    # harness: m4's own yearly statistics through the aggregator vs its levels (one leg)
    leg0 = "gfdl-esm4_ssp370"
    y4 = pl.read_parquet(os.path.join(YEARLY, f"m{TRUTH}_{leg0}.parquet"))
    h4 = pl.read_parquet(os.path.join(YEARLY, f"m{TRUTH}_hist.parquet"))
    rw, rh = window_stats(y4, W0, Y1), window_stats(h4, Y0, YS)
    cand = {"replay_truth": (rw, rh, None)}
    for r in PA.score_leg(leg0, cand, cells):
        rows.append(dict(split="harness", **r))
        log("HARNESS replay pass", round(r["pass_rate"], 4), "stems", r["stems_ratio"], "bpt", r["agb_per_stem_ratio"])
    T_h = PA.lev(TRUTH, "hist", "h2000")
    for split in a.splits:
        sd = split.replace(":", "_")
        for arm in ("lstm", "lstmCB"):
            d = os.path.join(OUT, sd, arm)
            if not os.path.exists(os.path.join(d, "f5_pred.parquet")):
                continue
            P = pl.concat([pl.read_parquet(f"{d}/f{k}_pred.parquet") for k in range(1, 6)])
            infos = [json.load(open(f"{d}/f{k}.json")) for k in range(1, 6)]
            meta = dict(converged_folds=sum(i["converged"] for i in infos),
                        core_s_per_cell_year=float(np.median([np.median(list(i["core_s_per_cell_year"].values()))
                                                              for i in infos])))
            pc = window_stats(P.filter((pl.col("leg") == "ctl_obs") & (pl.col("start") == "S19")), W0, Y1)
            for leg in [x for x in P["leg"].unique().to_list() if x != "ctl_obs"] + ["ctl_obs"]:
                p = P.filter((pl.col("leg") == leg) & (pl.col("start") == "S19"))
                pw = window_stats(p, W0, Y1)
                for r in PA.score_leg(leg, {f"{arm}": (pw, T_h, pc if leg != "ctl_obs" else None)}, cells):
                    rows.append(dict(split=split, **meta, **r))
                # within-training check: S00 at 2019 (stems, biomass per tree only)
                p0 = P.filter((pl.col("leg") == leg) & (pl.col("start") == "S00"))
                s19 = window_stats(p0, YS, YS)
                t19 = PA.lev(TRUTH, "hist", "y2019")
                j = s19.join(t19, on="Cell", suffix="_T").join(cells, on="Cell")
                w = np.cos(np.deg2rad(j["lat"].to_numpy()))
                nP, nT = j["n_per_patch"].fill_null(0).to_numpy(), j["n_per_patch_T"].fill_null(0).to_numpy()
                bP = (j["agb_per_stem"].fill_null(0) * j["n_per_patch"].fill_null(0)).to_numpy()
                bT = (j["agb_per_stem_T"].fill_null(0) * j["n_per_patch_T"].fill_null(0)).to_numpy()
                rows.append(dict(split=split, arm=f"{arm}_S00_y2019", test_leg=leg,
                                 stems_ratio=float((w * nP).sum() / (w * nT).sum()),
                                 agb_per_stem_ratio=float(((w * bP).sum() / (w * nP).sum()) / ((w * bT).sum() / (w * nT).sum()))))
            log(split, arm, "scored")
    out = pl.DataFrame(rows, infer_schema_length=None)
    f = os.path.join(PP.OUT, "eval", "lstm_scores.csv")
    out.write_csv(f)
    keep = ["split", "test_leg", "arm", "pass_rate", "stems_ratio", "agb_per_stem_ratio",
            "resp_n_per_patch_slope_deatt", "ctl_resp_n_per_patch_slope_deatt", "ctl_resp_n_per_patch_agg_ratio",
            "converged_folds"]
    with pl.Config(tbl_rows=300, tbl_cols=12, fmt_str_lengths=30):
        print(out.select([c for c in keep if c in out.columns]))
    log(f"wrote {f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["yearly", "draws", "train", "score"])
    ap.add_argument("--split", default="HG:gfdl-esm4")
    ap.add_argument("--splits", type=lambda x: x.split(","), default=[f"{k}:{g}" for k in ("HG", "H585G")
                                                                      for g in PP.GCMS])
    ap.add_argument("--fold", type=int, default=1)
    ap.add_argument("--arm", default="lstm", choices=["lstm", "lstmCB"])
    ap.add_argument("--iters", type=int, default=800)
    ap.add_argument("--iters-full", dest="iters_full", type=int, default=4000)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--batch", type=int, default=512)
    ap.add_argument("--batch-full", dest="batch_full", type=int, default=256)
    ap.add_argument("--part", type=int, default=int(os.environ.get("SLURM_ARRAY_TASK_ID", "0")))
    ap.add_argument("--nparts", type=int, default=1)
    a = ap.parse_args()
    if a.stage == "draws":
        for m in PP.MEMBERS:
            log(f"m{m} ctl_obs draws (first 10):", ctl_sequence(m)[:10])
    else:
        {"yearly": stage_yearly, "train": stage_train, "score": stage_score}[a.stage](a)
    log("=== DONE")


if __name__ == "__main__":
    main()
