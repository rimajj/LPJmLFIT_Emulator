"""explore_de_struct_sd.py — LINE X, Germany emulator, STRUCT track: diagnostic subclass of the
STRUCT stepper for the stem-loss diagnosis (pre-registration /p/tmp/jamirp/X_de/_status/SD.md).

class StructSD(explore_de_struct_stepper.Struct), kwargs (JSON) on top of Struct's:
  hmode     "allom" (default; identical to Struct: Height_{y+1} = fitted allometry of the new
            agb)
            "carry"      Height_{y+1} = Height_y * Hhat(agb_{y+1}) / Hhat(agb_y): the allometric
                         relative increment applied to the tree's OWN height (residual kept)
            "carry_mono" the same, never decreasing: Height_y * max(1, Hhat(agb_{y+1}) /
                         Hhat(agb_y))
  glat      "ar1" (default; the B1 AR(1) latent) | "two": the growth-efficiency latent zG becomes
            sd * (sqrt(w) * slow + sqrt(1 - w) * white), slow an AR(1) with coefficient phi, per
            size class from struct/stepper/<split>/g_twocomp.json (fitted to the lag-1..10
            autocorrelation of B1's out-of-fold zG; SD.md H8). The white part is the base AR's own
            G innovation; the six other latents are unchanged. Start / recruits: slow = z_G / sd.
  ident     "kernel" (default; B3 inheritance kernel, no acceptance) | "oracle": DIAGNOSTIC ONLY —
            each recruit's Type + six traits drawn uniformly (the kernel's per-cell generator) from
            the ORIGINAL's own first-appearing printed trees of the same cell, 1986-2044, Historical
            + --oracle_leg (reads the test member's truth: an upper bound for an acceptance filter)
            | "oracle_full": the same rows ALSO give the entry state (Height, agb, vegc, LAI,
            fpc_ind, D95, Age, counter c) — from the SH3 transition table of the member
  xdump_dir if set: per chunk and year the sign head's FULL input row (StructHeads.X) of printed
            trees with Height < 6 m and Age <= 15 (+ keys, p_gneg, G) -> <xdump_dir>/c<a>-<b>/y<y+1>
  diag_tag  sub-directory for the per-chunk diag JSON (so diagnostic arms never overwrite the
            stored run's diag files)
  dump_dir  if set: per chunk and year one parquet of every tree's step internals
            (<dump_dir>/c<first>-<last>/y<y+1>.parquet: keys, hidden at y, Height y / y+1, agb
            y / y+1, G, latent z of G and dlagb, the three death channels, hidden at y+1, hazard,
            counter)
Run the arm under the STORED run's arm name (--arm struct_noacc) so the random streams are the
stored run's (Rand is keyed on arm, rep, gcm, stream, year, keys — not on chunk or leg);
hmode=allom then reproduces the stored rosters exactly (the gate), and any other hmode differs
ONLY through height.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import explore_de_struct_heads as hd  # noqa: E402
import explore_de_struct_stepper as st  # noqa: E402

rl = st.rl
TRAITS4 = ["D95max", "minwscal", "Longevity", "beta_root"]


class _RandProxy:
    """Passes everything to the engine Rand; records the cell of each per-cell generator."""

    def __init__(self, r, owner):
        self._r, self._owner = r, owner

    def generator(self, stream, year, cell):
        self._owner._cur_cell = int(cell)
        return self._r.generator(stream, year, cell)

    def __getattr__(self, k):
        return getattr(self._r, k)


class _OracleKernel:
    """Kernel stand-in: real eligibility, identities from the original model recruits."""

    def __init__(self, K, owner):
        self._K, self._o = K, owner

    def eligible(self, *a, **kw):
        return self._K.eligible(*a, **kw)

    def propose(self, bank, n, elig, build, rng, force_type=None):
        b = self._o.obank.get(self._o._cur_cell)
        if b is None or not len(b["Type"]):
            raise RuntimeError(f"oracle bank empty for cell {self._o._cur_cell}")
        i = rng.integers(0, len(b["Type"]), n)
        out = {k: v[i] for k, v in b.items()}
        self._o._picks.append(out)
        return out


class StructSD(st.Struct):
    def __init__(
        self,
        hmode: str = "allom",
        diag_tag: str = "sd",
        dump_dir: str | None = None,
        glat: str = "ar1",
        ident: str = "kernel",
        xdump_dir: str | None = None,
        oracle_leg: str = "ssp370",
        **kw,
    ):
        super().__init__(**kw)
        assert hmode in ("allom", "carry", "carry_mono"), hmode
        self.hmode, self.diag_tag, self.dump_dir = hmode, diag_tag, dump_dir
        assert glat in ("ar1", "two"), glat
        self.glat = glat
        assert ident in ("kernel", "oracle", "oracle_full"), ident
        self.ident, self.oracle_leg = ident, oracle_leg
        self._cur_cell = None
        self.xdump_dir = xdump_dir
        self._X_last = None
        self._s_cur = self._s_next = None

    def init(self, state, ctx):
        super().init(state, ctx)
        d, f = os.path.split(self.diag_path)
        dd = os.path.join(os.path.dirname(d), f"_{self.diag_tag}", os.path.basename(d))
        os.makedirs(dd, exist_ok=True)
        self.diag_path = os.path.join(dd, f)
        self.diag["hmode"] = self.hmode
        cells = state.cell["cells"]
        if self.dump_dir:
            self.dump_path = os.path.join(self.dump_dir, f"c{int(cells[0])}-{int(cells[-1])}")
            os.makedirs(self.dump_path, exist_ok=True)
        self.diag["glat"] = self.glat
        self.diag["ident"] = self.ident
        if self.xdump_dir:
            X0 = self.H.X

            def _xrec(feat, g=None, _f=X0):
                X = _f(feat, g)
                if g is None:
                    self._X_last = X
                return X

            self.H.X = _xrec
            self.xdump_path = os.path.join(
                self.xdump_dir, f"c{int(state.cell['cells'][0])}-{int(state.cell['cells'][-1])}"
            )
            os.makedirs(self.xdump_path, exist_ok=True)
        if self.ident != "kernel":
            self._oracle_bank(state.cell["cells"])
        if self.glat == "two":
            import json

            par = json.load(open(os.path.join(st.OUT, self.split, "g_twocomp.json")))
            ns = len(hd.SIZE_EDGES) + 2
            self.g_phi = np.array([par.get(str(k - 1), par["-1"])["phi"] for k in range(ns)])
            self.g_w = np.array([par.get(str(k - 1), par["-1"])["w"] for k in range(ns)])
            t = state.tree
            state.aux_tree["zs"] = self._slow_from_z(
                state.aux_tree["z"], t["Type"], hd.size_class(t["Height"])
            )

    def _oracle_bank(self, cells):
        """First-appearing printed trees of the member's original run (SH3 transition table, which
        carries the counter c_y), 1986-2044, Historical + oracle_leg, these cells."""
        mem = pl.read_parquet(os.path.join(st.XDE, "shared", "registry", "members.parquet")).filter(
            (pl.col("gcm") == self.gcm)
            & (pl.col("seed") == self.seed)
            & ~pl.col("excluded")
            & pl.col("scen").is_in(["Historical", self.oracle_leg])
        )
        k = ["Cell", "Patch", "Type", "ID", "SLA", "Wooddens"]
        cols = TRAITS4 + ["Height", "agb", "vegc", "LAI", "fpc_ind", "D95", "Age", "c_y"]
        parts = []
        for m in mem["member"].to_list():
            lf = pl.concat(
                [pl.scan_parquet(f).select(k + ["Year"] + cols) for f in hd.member_files(m)],
                how="vertical_relaxed",
            )
            lf = lf.filter(
                (pl.col("Year") <= 2014) if "Historical" in m else (pl.col("Year") > 2014)
            )
            parts.append(lf)
        D = (
            pl.concat(parts, how="vertical_relaxed")
            .filter(
                pl.col("Cell").is_in([int(c) for c in cells])
                & (pl.col("Type") <= 6)
                & (pl.col("Year") <= 2044)
            )
            .sort(k + ["Year"])
            .group_by(k, maintain_order=True)
            .agg(pl.all().first())
            .filter(pl.col("Year") > 1985)
            .sort(k)
            .collect()
        )
        keep = ["Type", "SLA", "Wooddens"] + cols
        self.obank = {
            int(c): {kk: g[kk].to_numpy() for kk in keep}
            for (c,), g in D.group_by(["Cell"], maintain_order=True)
        }
        self._picks = []
        self.diag["oracle_bank_n"] = int(D.height)

    def _recruits(self, state, ctx, y1, clim_y1, flags_y1, rand, Xp1, nrec, pcell, ppat):
        if self.ident == "kernel":
            return super()._recruits(
                state, ctx, y1, clim_y1, flags_y1, rand, Xp1, nrec, pcell, ppat
            )
        K0 = self.K
        self.K = _OracleKernel(K0, self)
        self._picks = []
        try:
            R, zr = super()._recruits(
                state, ctx, y1, clim_y1, flags_y1, _RandProxy(rand, self), Xp1, nrec, pcell, ppat
            )
        finally:
            self.K = K0
        if R is not None and self.ident == "oracle_full":
            P = {kk: np.concatenate([p[kk] for p in self._picks]) for kk in self._picks[0]}
            assert len(P["Type"]) == len(R["Type"]) and np.array_equal(P["Type"], R["Type"])
            for kk in ("Height", "agb", "vegc", "LAI", "fpc_ind", "D95", "Age"):
                R[kk] = P[kk].astype(np.float64)
            R["c"] = np.clip(np.nan_to_num(P["c_y"]), 0, 4).astype(np.int8)
        return R, zr

    def _sdG(self, typ, scls):
        ti, si = np.asarray(typ, np.int64) + 1, np.asarray(scls, np.int64) + 1
        return self.ar["sd"][ti, si, 0]

    def _slow_from_z(self, z, typ, scls):
        return np.asarray(z, np.float64)[:, 0] / self._sdG(typ, scls)

    def step(self, state, ctx, year, clim_y1, flags_y1, rand):
        if self.glat != "two":
            return super().step(state, ctx, year, clim_y1, flags_y1, rand)
        t = state.tree
        self._s_cur = state.aux_tree["zs"]
        self._eta = rand.normal(
            "struct_gslow", int(year), t["Cell"], t["Patch"], t["Type"], t["ID"]
        )
        out = super().step(state, ctx, year, clim_y1, flags_y1, rand)
        aux = dict(out.aux_tree)
        aux["zs"] = self._s_next
        out.aux_tree = aux
        if out.recruits is not None and out.aux_recruits is not None:
            R = out.recruits
            ar = dict(out.aux_recruits)
            ar["zs"] = self._slow_from_z(ar["z"], R["Type"], hd.size_class(R["Height"]))
            out.aux_recruits = ar
        return out

    def _ar_step(self, z, typ, scls, e):
        z1 = super()._ar_step(z, typ, scls, e)
        if self.glat != "two":
            return z1
        si = np.asarray(scls, np.int64) + 1
        phi, w = self.g_phi[si], self.g_w[si]
        s1 = phi * self._s_cur + np.sqrt(1 - phi**2) * self._eta
        z1 = z1.copy()
        z1[:, 0] = self._sdG(typ, scls) * (np.sqrt(w) * s1 + np.sqrt(1 - w) * e[:, 0])
        self._s_next = s1
        return z1

    def _height_next(self, t, agb, agb1, typ):
        hh1 = rl.predict_height(agb1, t["Wooddens"], t["SLA"], typ, self.allom)
        if self.hmode == "allom":
            return hh1
        hh0 = rl.predict_height(agb, t["Wooddens"], t["SLA"], typ, self.allom)
        r = hh1 / hh0
        if self.hmode == "carry_mono":
            r = np.maximum(r, 1.0)
        return t["Height"].astype(np.float64) * r

    def _hook(self, y, t, keys, hidden0, z, d, agb1, h1, dead_h, dead_s, dead_f, hidden1, mo, R):
        if self.xdump_dir and self._X_last is not None:
            m = (
                ~np.asarray(hidden0, bool)
                & (np.asarray(t["Height"]) < 6.0)
                & (np.asarray(t["Age"]) <= 15)
            )
            Xm = self._X_last[m]
            cols = {n: Xm[:, j] for j, n in enumerate(self.H.names)}
            cols.update(
                Year=np.full(int(m.sum()), y + 1, np.int16),
                Cell_k=np.asarray(t["Cell"], np.int16)[m],
                Patch_k=np.asarray(t["Patch"], np.int16)[m],
                ID_k=np.asarray(t["ID"], np.int32)[m],
                p_gneg=np.asarray(d["p_gneg"], np.float32)[m],
                G1=np.asarray(d["G"], np.float32)[m],
            )
            pl.DataFrame(cols).write_parquet(os.path.join(self.xdump_path, f"y{y + 1}.parquet"))
        if not self.dump_dir:
            return
        n = len(t["Cell"])
        df = pl.DataFrame(
            {
                "Year": np.full(n, y + 1, np.int16),
                "Cell": np.asarray(t["Cell"], np.int16),
                "Patch": np.asarray(t["Patch"], np.int16),
                "Type": np.asarray(t["Type"], np.int8),
                "ID": np.asarray(t["ID"], np.int32),
                "SLA": np.asarray(t["SLA"], np.float32),
                "Wooddens": np.asarray(t["Wooddens"], np.float32),
                "Age": np.asarray(t["Age"], np.float32),
                "hidden0": np.asarray(hidden0, bool),
                "H0": np.asarray(t["Height"], np.float32),
                "H1": np.asarray(h1, np.float32),
                "agb0": np.asarray(t["agb"], np.float32),
                "agb1": np.asarray(agb1, np.float32),
                "G1": np.asarray(d["G"], np.float32),
                "p_gneg": np.asarray(d["p_gneg"], np.float32),
                "zG": np.asarray(z[:, 0], np.float32),
                "zdlagb": np.asarray(z[:, 2], np.float32),
                "dead_h": np.asarray(dead_h, bool),
                "dead_s": np.asarray(dead_s, bool),
                "dead_f": np.asarray(dead_f, bool),
                "hidden1": np.asarray(hidden1, bool),
                "mort": np.asarray(mo["mort"], np.float32),
                "c1": np.asarray(np.minimum(mo["c"], 5), np.int8),
            }
        )
        df.write_parquet(os.path.join(self.dump_path, f"y{y + 1}.parquet"))
