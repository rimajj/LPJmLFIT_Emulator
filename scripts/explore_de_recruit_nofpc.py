#!/usr/bin/env python3
"""explore_de_recruit_nofpc.py — LINE X, Germany emulator: refit the SH13 recruit head WITHOUT the grass-cover input
and score it against the shipped head.

Why (sixth session, _status/RG.md): in the original model the grass cover of a patch is capped after establishment so
that grass + ALL tree cover <= 1 (establishmentpft_ind.c:197-204; reduce_grass.c divides fpc only, LAI/agb untouched).
Where the cap binds (35 % of patch-years) grass cover therefore carries the patch's own cover of the unprinted < 5 m
trees, i.e. next year's recruits, and the recruit head learned to read it. Any grass model with a cover closure (grass2)
removes that signal and biases the head (-7..-11 % one step ahead in 1985-2004, +6..+10 % after 2025). This item tests
the simplest fix — the head stops reading grass cover (it keeps grass LAI and biomass) — before anyone builds an
explicit hidden-sapling state. Pre-registration + decision rule: _status/HR.md (written before the run).

Stages
  fit   --tag T [--drop COL ...]  refit rec_B0/rec_B1 exactly as explore_de_sh_patchheads.stage_fit does (same members,
        folds, hyperparameters, seed) with the dropped state features removed; writes shared/patchheads/<split>_<T>/
        (rec_* + meta.json; every other head file is a symlink to the base split, so load_heads("<split>_<T>") works).
  score --heads H1 H2 ...         Poisson deviance + pred/obs by 5-yr window for each head on the training members'
        held-out fold 5 and on every test member (all dev cells) -> shared/eval/recruit_nofpc_scores.csv
  submit                          SLURM chain: fit r0 (reproducibility gate) | fit nofpc -> score

Read-only with respect to everything outside line X's own /p/tmp/jamirp/X_de tree.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_sh_patchheads as ph  # noqa: E402

XDE = ph.XDE
EVAL = os.path.join(XDE, "shared", "eval")
STATUS = os.path.join(XDE, "_status", "HR.md")
PY = ph.PY
LOGS = os.path.join(REPO, "logs")
KEEP_FILES = ("rec_B0.txt", "rec_B1.txt", "meta.json")
GF, GL = "grass8_fpc_y", "grass8_LAI_y"
EXTRA = {"hlag": ["h_lag1", "capped_lag1", "u_lag1"],  # TRUTH-ONLY: upper bound of a carried hidden-cover state
         "hist": ["n_recruit_y", "rec_lag1", "rec_lag2_5"]}  # emulator-visible: its own recruit history


def grass_K(split="DEV-A") -> float:
    import explore_de_grass2 as g2
    return float(g2.Grass2(split).C["K"])


def with_extra(members, folds_keep=None, cols=None, K=None) -> pl.DataFrame:
    """Feature rows of `members` plus the EXTRA columns. Lags are taken within (Cell, Patch) along Year; a w2015 leg
    gets its 2014 lag rows from the Historical member of the same GCM and seed (the leg forks from that state).
    h = 1 - grass fpc - printed tree fpc is the hidden (< 5 m) tree cover, exact only where the post-establishment
    cover cap binds (grass fpc below its own Beer-Lambert cover by > 1e-3); u is the same expression everywhere (an
    upper bound on h where the cap does not bind)."""
    K = grass_K() if K is None else K
    base = ["Year", "Cell", "Patch", GF, GL, "sum_fpc_y", "n_recruit_y"]
    out = []
    for m in members:
        F = ph.load_feats([m], folds_keep=folds_keep, cols=None if cols is None else sorted(set(cols) | set(base)
                                                                                          | {"fold"}))
        F = F.with_columns(_keep=pl.lit(True))
        if m.endswith("_w2015"):
            g, rest = m.split("_", 1)
            hist = f"{g}_Historical_{rest.split('_')[1]}_h1985"
            P = (ph.load_feats([hist], cols=base).filter(pl.col("Year") >= 2010)
                 .filter(pl.col("Cell").is_in(F["Cell"].unique().implode())))
            F = pl.concat([P.with_columns(_keep=pl.lit(False)), F], how="diagonal_relaxed")
        L = pl.col(GL).cast(pl.Float64)
        g = pl.col(GF).cast(pl.Float64)
        t = pl.col("sum_fpc_y").cast(pl.Float64)
        cap = ((1 - (-K * L).exp()) - g) > 1e-3
        F = F.sort("Cell", "Patch", "Year").with_columns(
            _u=1 - g - t, _cap=cap.cast(pl.Float64), _r=pl.col("n_recruit_y").cast(pl.Float64))
        F = F.with_columns(_h=pl.when(pl.col("_cap") > 0).then(pl.col("_u")).otherwise(None))
        ov = ["Cell", "Patch"]
        F = F.with_columns(
            h_lag1=pl.col("_h").shift(1).over(ov), capped_lag1=pl.col("_cap").shift(1).over(ov),
            u_lag1=pl.col("_u").shift(1).over(ov), rec_lag1=pl.col("_r").shift(1).over(ov),
            rec_lag2_5=pl.sum_horizontal([pl.col("_r").shift(k).over(ov) for k in range(2, 6)]))
        # a lag reaching before the first available year must be missing, not zero
        F = F.with_columns(rec_lag2_5=pl.when(pl.col("_r").shift(5).over(ov).is_null()).then(None)
                           .otherwise(pl.col("rec_lag2_5")))
        out.append(F.filter(pl.col("_keep")).drop("_keep", "_u", "_cap", "_r", "_h").sort("Year", "Cell", "Patch"))
    return pl.concat(out, how="diagonal_relaxed")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def status(msg):
    with open(STATUS, "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {msg}\n")


def stage_fit(a):
    split, vf = a.split, int(a.val_fold)
    base_dir = os.path.join(ph.OUT, split)
    od = os.path.join(ph.OUT, f"{split}_{a.tag}")
    os.makedirs(od, exist_ok=True)
    meta = json.load(open(os.path.join(base_dir, "meta.json")))
    ms = ph.split_members(split)
    assert ms["train"] == meta["train_members"], "registry train members changed since the base fit"
    trf = [1, 2, 3, 4]
    F = with_extra(ms["train"], folds_keep=trf)
    _, rec_s, _ = ph.state_feats([c for c in F.columns if not any(c in v for v in EXTRA.values())])
    assert rec_s == meta["recruit"]["state_feats"], "base feature list differs from the shipped head's"
    for c in a.drop:
        assert c in rec_s, f"{c} is not a recruit state feature"
    rec_s = [c for c in rec_s if c not in a.drop] + [c for e in a.extra for c in EXTRA[e]]
    tr_m = (F["fold"] != vf).to_numpy()
    log(f"fit {split}_{a.tag}: drop {a.drop}; {F.height} patch-years, train {tr_m.sum()} val {(~tr_m).sum()}")
    y = F["n_recruit_y1"].cast(pl.Float64).to_numpy()
    mbar = y[tr_m].mean()
    rbase = float(np.log(mbar))
    Xs = ph._np(F, rec_s)
    Xc = ph._np(F, ph.REC_CLIM)
    rp = dict(objective="poisson", metric="poisson", learning_rate=0.08, num_leaves=63, min_data_in_leaf=2000,
              lambda_l2=1.0, feature_fraction=0.9, bagging_fraction=0.7, bagging_freq=1, max_bin=255)
    trm, vam = tr_m, ~tr_m
    r0 = ph._train(rp, Xs[trm], y[trm], None, np.full(trm.sum(), rbase), Xs[vam], y[vam], None,
                   np.full(vam.sum(), rbase), a.rounds, 50, rec_s, label="recruit B0")
    q0 = rbase + r0.predict(Xs, num_threads=ph.NTHREADS, raw_score=True)
    rp1 = dict(rp, learning_rate=0.05, num_leaves=15, min_data_in_leaf=20000, linear_lambda=10.0)
    r1 = ph._train(rp1, Xc[trm], y[trm], None, q0[trm], Xc[vam], y[vam], None, q0[vam], a.rounds, 50, ph.REC_CLIM,
                   linear=True, label="recruit B1")
    q1 = r1.predict(Xc, num_threads=ph.NTHREADS, raw_score=True)
    kl = {k: ph.pois_dev(np.exp(q0[vam] + k * q1[vam]), y[vam]) for k in ph.KAPPAS}
    kr = min(kl, key=kl.get)
    r0.save_model(os.path.join(od, "rec_B0.txt"))
    r1.save_model(os.path.join(od, "rec_B1.txt"))
    mu = np.exp(q0[vam] + kr * q1[vam])
    yv = y[vam]
    edges = np.quantile(mu, np.linspace(0, 1, 11)[1:-1])
    dec = np.searchsorted(edges, mu)
    alpha = [max(float(np.sum((yv[dec == d] - mu[dec == d]) ** 2 - yv[dec == d]) / np.sum(mu[dec == d] ** 2)), 0.0)
             for d in range(10)]
    meta["recruit"] = {"base": rbase, "mean_train": mbar, "state_feats": rec_s, "clim_feats": ph.REC_CLIM,
                       "kappa": kr, "val_dev_by_kappa": kl, "val_dev_const": ph.pois_dev(np.full(vam.sum(), mbar), yv),
                       "B0_iter": r0.best_iteration, "B1_iter": r1.best_iteration, "nb_edges": edges.tolist(),
                       "nb_alpha": alpha, "dropped": list(a.drop), "extra": list(a.extra),
                       "derived_from": base_dir}
    json.dump(meta, open(os.path.join(od, "meta.json"), "w"), indent=1)
    for fn in os.listdir(base_dir):
        if fn in KEEP_FILES or fn.startswith("_"):
            continue
        dst = os.path.join(od, fn)
        if not os.path.lexists(dst):
            os.symlink(os.path.join(base_dir, fn), dst)
    msg = (f"fit {split}_{a.tag} (drop {a.drop}, extra {a.extra}): val dev {kl[kr]:.5f} at kappa {kr} (const "
           f"{meta['recruit']['val_dev_const']:.5f}); B0 {r0.best_iteration} B1 {r1.best_iteration} iters")
    log(msg)
    status(msg)


def eval_sets(split):
    ms = ph.split_members(split)
    sets = [(m, [5]) for m in ms["train"]]
    sets += [(m, None) for m in ms["test"] if m.startswith("ACCESS-CM2") and "_s1_" in m]
    return sets


def stage_score(a):
    heads = {h: ph.load_heads(h) for h in a.heads}
    need = set()
    for H in heads.values():
        need |= set(H.meta["recruit"]["state_feats"]) | set(H.meta["recruit"]["clim_feats"])
    cols = sorted(need | {"member", "Year", "Cell", "fold", "n_recruit_y1"})
    rows, gate = [], {}
    for m, fk in eval_sets(a.split):
        S = with_extra([m], folds_keep=fk, cols=[c for c in cols if c != "member" and c not in
                                                 sum(EXTRA.values(), [])])
        y = S["n_recruit_y1"].cast(pl.Float64).to_numpy()
        win = (S["Year"].to_numpy() // 5) * 5
        mus = {h: H.recruit_mean(S) for h, H in heads.items()}
        if "DEV-A" in mus and "DEV-A_r0" in mus:
            gate[m] = float(np.mean(np.abs(np.log(mus["DEV-A_r0"]) - np.log(mus["DEV-A"]))))
        mbar = float(heads[a.heads[0]].meta["recruit"]["mean_train"])
        for h, mu in list(mus.items()) + [("const", np.full(y.size, mbar))]:
            for w in [None] + sorted(set(win.tolist())):
                k = np.ones(y.size, bool) if w is None else win == w
                rows.append(dict(member=m, fold5_only=fk is not None, head=h, win=-1 if w is None else int(w),
                                 n=int(k.sum()), dev=ph.pois_dev(mu[k], y[k]), mu_pp=float(mu[k].mean()),
                                 obs_pp=float(y[k].mean())))
        log(f"{m}: {S.height} patch-years scored")
    R = pl.DataFrame(rows).with_columns(ratio=pl.col("mu_pp") / pl.col("obs_pp"))
    os.makedirs(EVAL, exist_ok=True)
    out = os.path.join(EVAL, f"recruit_nofpc_scores{a.out_suffix}.csv")
    R.write_csv(out)
    pl.Config.set_tbl_rows(300)
    pl.Config.set_tbl_width_chars(250)
    print("GATE refit r0 vs shipped, mean |d log mu| per member:", json.dumps(gate))
    A = R.filter(pl.col("win") == -1)
    print(A.pivot(on="head", index="member", values="dev").with_columns(pl.selectors.float().round(5)))
    W = R.filter(pl.col("win") >= 0)
    print(W.pivot(on="head", index=["member", "win"], values="ratio").sort("member", "win")
          .with_columns(pl.selectors.float().round(4)))
    status(f"score {a.heads}: gate {json.dumps(gate)}; wrote {out}")
    log("wrote", out)


def stage_submit(a):
    me = os.path.abspath(__file__)
    jobs = os.path.join(XDE, "_jobs")
    os.makedirs(LOGS, exist_ok=True)

    def jcf(name, body, dep=None):
        f = os.path.join(jobs, f"HR_{name}.jcf")
        L = ["#!/bin/bash", f"#SBATCH --job-name=X-de-HR-{name}", "#SBATCH --account=waldspektrum",
             "#SBATCH --partition=priority", "#SBATCH --qos=priority", "#SBATCH --cpus-per-task=16",
             "#SBATCH --time=03:00:00", f"#SBATCH --output={LOGS}/X-de-HR-{name}.%j.out"]
        if dep:
            L.append(f"#SBATCH --dependency=afterok:{dep}")
        L += ["set -eu", "export POLARS_MAX_THREADS=16", body, 'echo "=== JOB DONE exit=$? ==="']
        open(f, "w").write("\n".join(L) + "\n")
        return subprocess.run(["sbatch", "--parsable", f], capture_output=True, text=True,
                              check=True).stdout.strip().split(";")[0]

    if a.stage2:
        arms = {"nofpc_hlag": "--extra hlag", "nofpc_hist": "--extra hist", "nofpc_hist_hlag": "--extra hist hlag"}
        ids = [jcf(f"fit_{t}", f"{PY} {me} fit --split {a.split} --tag {t} --drop grass8_fpc_y {x}")
               for t, x in arms.items()]
        hs = " ".join(f"{a.split}_{t}" for t in ["r0", "nofpc", *arms])
        js = jcf("score2", f"{PY} {me} score --split {a.split} --heads {hs} --out-suffix _stage2", dep=":".join(ids))
        status(f"submitted stage 2 fits {ids}, score {js}")
        print(ids, js)
        return
    j0 = jcf("fit_r0", f"{PY} {me} fit --split {a.split} --tag r0")
    j1 = jcf("fit_nofpc", f"{PY} {me} fit --split {a.split} --tag nofpc --drop grass8_fpc_y")
    js = jcf("score", f"{PY} {me} score --split {a.split} --heads {a.split} {a.split}_r0 {a.split}_nofpc",
             dep=f"{j0}:{j1}")
    gm = os.path.join(REPO, "scripts", "explore_de_recruit_grass.py")
    jg = jcf("grass_nofpc", f"{PY} {gm} --split {a.split} --heads {a.split}_nofpc --tag-suffix _nofpc", dep=j1)
    status(f"submitted fit r0 {j0}, fit nofpc {j1}, score {js}, grass-swap with nofpc {jg}")
    print(j0, j1, js, jg)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="stage", required=True)
    for s in ("fit", "score", "submit"):
        p = sub.add_parser(s)
        p.add_argument("--split", default="DEV-A")
        p.add_argument("--tag", default="nofpc")
        p.add_argument("--drop", nargs="*", default=[])
        p.add_argument("--extra", nargs="*", default=[], choices=sorted(EXTRA))
        p.add_argument("--stage2", action="store_true", help="submit: the history arms instead of step 1")
        p.add_argument("--val-fold", type=int, default=4)
        p.add_argument("--rounds", type=int, default=1500)
        p.add_argument("--heads", nargs="*", default=["DEV-A", "DEV-A_nofpc"])
        p.add_argument("--out-suffix", default="")
    a = ap.parse_args()
    {"fit": stage_fit, "score": stage_score, "submit": stage_submit}[a.stage](a)


if __name__ == "__main__":
    main()
