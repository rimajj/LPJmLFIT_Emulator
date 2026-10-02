#!/usr/bin/env python3
"""explore_de_struct_apicheck.py — LINE X, B-STRUCT: check of the StructHeads predict API a stepper calls.
(1) round trip: residual_z(sample(z)) == z for continuous latents; (2) single-core cost per tree of features + predict +
sample; (3) a sampled one-year draw vs truth: mean G, share G<0, share W>0.
Writes struct/heads/<split>/apicheck.json."""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_struct_heads as hd  # noqa: E402

split = sys.argv[1] if len(sys.argv) > 1 else "DEV-A"
H = hd.StructHeads.load(split)
df = hd.read_member_rows("ACCESS-CM2_ssp370_s1_w2015", pl.lit(True), pl.col("u_hash") < 0.002).filter(pl.col("g_ok"))
n = df.height
typ = df["Type"].to_numpy()
scl = hd.size_class(df["Height"].to_numpy())
t0 = time.process_time()
feat = H.features(df.drop([c for c in df.columns if c.startswith("a_") or c.startswith("c8_")
                           or c in ("tstress_y", "tstress_y1", "soil_code")]))
X = H.X(feat)
t1 = time.process_time()
rng = np.random.default_rng(1)
z = H.stationary(typ, scl, rng.standard_normal((n, len(hd.LATENT))))
d = H.sample(X, z, typ, scl)
t2 = time.process_time()
z_back = H.residual_z(X, typ, scl, d["G"], d["W"], {h: d[h] for h in hd.SIZE_HEADS})
z1 = H.ar_step(z, typ, scl, rng.standard_normal((n, len(hd.LATENT))))
cont = [0] + list(range(2, len(hd.LATENT)))
inner = (np.abs(z[:, cont]) < 2.5) & np.isfinite(z_back[:, cont])
err = np.abs(z_back[:, cont] - z[:, cont])[inner]
G1 = df["G_y1"].to_numpy().astype(float)
out = {"rows": n, "member": "ACCESS-CM2_ssp370_s1_w2015 (u_hash < 0.002, all dev cells)",
       "roundtrip_abs_err_median": float(np.median(err)), "roundtrip_abs_err_p99": float(np.quantile(err, 0.99)),
       "cpu_s_per_tree_features": (t1 - t0) / n, "cpu_s_per_tree_predict_sample": (t2 - t1) / n,
       "threads_note": "process_time over all threads (LightGBM is multi-threaded): an upper bound of single-core cost",
       "sampled_vs_truth": {"mean_G": [float(d["G"].mean()), float(G1.mean())],
                            "share_G_neg": [float((d["G"] < 0).mean()), float((G1 < 0).mean())],
                            "share_W_pos": [float((d["W"] > 0).mean()), float((df["W_y1"].to_numpy() > 0).mean())],
                            "dlagb_mean": [float(d["dlagb"].mean()), float(df["dlagb_t"].mean())]},
       "ar_step_sd": [float(v) for v in z1.std(0)], "stationary_sd": [float(v) for v in z.std(0)]}
json.dump(out, open(os.path.join(hd.OUT, split, "apicheck.json"), "w"), indent=1)
print(json.dumps(out, indent=1), flush=True)
