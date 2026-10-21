"""The yearly forest-structure map and stand map (gradient-boosted trees, one per quantity).

Port of the inference half of ``scripts/explore_panel_yearly_drift.py`` (structure: tree count per
patch, biomass per
tree, the median of four traits) and ``scripts/explore_panel_stand_map.py`` (stand: leaf area,
vegetation carbon,
cover of 10 plant types). Each quantity is predicted as a departure from a per-cell, per-year
ANCHOR (the mean of
the original's training runs for that cell and year), from the trailing 30-year climate, its offset
from the
anchor runs' climate, the run's own 2000-2019 levels and their offset from the training runs', and
lat/lon/soil.

Optional (annual.json ``departure``, ADR 0354/0358): a DEPARTURE model on top of the structure
map for tree count and biomass per tree -- ln((X + 1) / (M + 1)) from last year's departures, the
map's own value M, the 30-year climate and this and last year's weather anomaly (z-score of the 25
yearly statistics against the 30 years before). It is the only part carried from year to year (two
numbers per cell); see ``LandEmulator``.
"""

from __future__ import annotations

import json
import os

import numpy as np

STRUCT_Q = ["n_per_patch", "agb_per_stem", "SLA_p50", "Wooddens_p50", "D95max_p50", "minwscal_p50"]
STAND_Q = ["lai_stand", "vegc"] + [f"fpc{p}" for p in range(1, 11)]


class AnnualMaps:
    def __init__(self, cfg, boosters):
        self.cfg = cfg
        self.b = boosters
        self.f_struct = cfg["features_structure"]
        self.f_stand = cfg["features_stand"]
        self.log_eps = cfg["log_eps"]  # quantity -> e: target log((v + e) / (anchor + e))
        self.cover_mode = cfg.get("cover_mode", "additive")
        self.totals = cfg.get("cover_totals", {})  # sumconstrained: name -> member quantities
        self.dep = cfg.get("departure")  # None = no departure model (releases before ADR 0358)

    @classmethod
    def load(cls, d):
        import lightgbm as lgb

        with open(os.path.join(d, "annual.json")) as fh:
            cfg = json.load(fh)
        names = STRUCT_Q + STAND_Q + list(cfg.get("cover_totals", {}))
        names += [f"dep_{q}" for q in (cfg.get("departure") or {}).get("quantities", [])]
        return cls(cfg, {q: lgb.Booster(model_file=os.path.join(d, f"lgb_{q}.txt")) for q in names})

    def _pred(self, q, X, anc, mode):
        p = self.b[q].predict(X, num_threads=1)
        if mode == "log":
            e = self.log_eps[q]
            return (anc + e) * np.exp(p) - e
        if mode == "relative":
            return np.maximum(anc, 1e-3) * np.exp(p)
        return p + anc

    def predict(self, feat):
        """feat: dict name -> (N,) for every feature the models read (incl. anc_<q>). Returns dict
        q -> (N,)."""
        Xs = np.column_stack([feat[c] for c in self.f_struct])
        Xx = np.column_stack([feat[c] for c in self.f_stand])
        out = {}
        for q in STRUCT_Q:
            v = self._pred(q, Xs, feat[f"anc_{q}"], "log" if q in self.log_eps else "add")
            out[q] = np.maximum(v, 0.0) if q == "n_per_patch" else v
        for q in STAND_Q:
            mode = (
                self.cover_mode if q.startswith("fpc") and self.cover_mode == "relative" else "add"
            )
            out[q] = np.maximum(self._pred(q, Xx, feat[f"anc_{q}"], mode), 0.0)
        for (
            name,
            members,
        ) in self.totals.items():  # sumconstrained: rescale the members to a separately fit total
            tot = np.maximum(
                self._pred(name, Xx, sum(feat[f"anc_{c}"] for c in members), "add"), 0.0
            )
            cur = sum(out[c] for c in members)
            scale = np.where(cur > 1e-3, tot / np.maximum(cur, 1e-3), 1.0)
            for c in members:
                out[c] = out[c] * scale
        return out

    def departure(self, feat):
        """feat: dict name -> (N,) for every departure-model input (``dlag_<q>``, ``lvl_<q>``, the
        30-year climate, ``z0_<c>`` / ``z1_<c>``). Returns q -> (N,) this year's departure (log)."""
        X = np.column_stack([feat[c] for c in self.dep["features"]])
        return {q: self.b[f"dep_{q}"].predict(X, num_threads=1) for q in self.dep["quantities"]}
