"""Micro-benchmark for the per-tree tabular-heads design (architect panel, 2026-10-01).

Measures single-thread LightGBM batch-predict cost per row per model on synthetic data shaped like the
transition table (60 features), to ground the core-seconds-per-cell-year estimate. Synthetic data: the
cost of a GBDT prediction depends on tree count/depth/feature count, not on the data values.
Writes JSON to /p/tmp/jamirp/X_de/arch_tabular/bench_lgb.json.
"""
import json, os, sys, time
import numpy as np
import lightgbm as lgb

out = "/p/tmp/jamirp/X_de/arch_tabular/bench_lgb.json"
rng = np.random.default_rng(0)
nfeat = 60
Xtr = rng.normal(size=(200_000, nfeat)).astype(np.float32)
y = (Xtr[:, :8] @ rng.normal(size=8) + np.sin(Xtr[:, 8] * 3) + 0.3 * rng.normal(size=len(Xtr))).astype(np.float32)
yb = (y > np.quantile(y, 0.9)).astype(np.int32)
res = {"nfeat": nfeat, "rows_per_cell_year_assumed": 2100, "runs": []}
batch = rng.normal(size=(2100 * 50, nfeat)).astype(np.float32)  # 50 cell-years at ~2100 stems
for obj, target in (("regression", y), ("binary", yb)):
    for ntree, leaves in ((300, 63), (600, 63), (300, 31)):
        t0 = time.time()
        m = lgb.train({"objective": obj, "num_leaves": leaves, "learning_rate": 0.05, "verbose": -1,
                       "num_threads": 16, "min_data_in_leaf": 50}, lgb.Dataset(Xtr, target), num_boost_round=ntree)
        ttrain = time.time() - t0
        # single-thread predict, best of 3
        best = 1e9
        for _ in range(3):
            c0 = time.process_time(); w0 = time.time()
            m.predict(batch, num_threads=1)
            best = min(best, time.process_time() - c0)
        us = best / len(batch) * 1e6
        r = {"objective": obj, "ntree": ntree, "leaves": leaves, "train_s_16thr": round(ttrain, 1),
             "predict_us_per_row_1thr": round(us, 3),
             "core_s_per_cell_year_per_model": round(us * 2100 / 1e6, 5)}
        res["runs"].append(r); print(r, flush=True)
json.dump(res, open(out, "w"), indent=1)
print("JOB OUTPUT", out, flush=True)
