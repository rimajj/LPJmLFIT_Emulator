#!/usr/bin/env python3
"""explore_de_engine.py — LINE X, Germany data-driven emulator, shared item SH6: THE ROLLOUT ENGINE.

Every arm (LOOKUP, ORACLE-1, TAB, STRUCT, RECUR, NSET, the nulls) runs through THIS loop, so the comparison is fair:
same initial states (SH5), same climate provider, same segment flags, same random-number streams, same emission and
the same writer the scorer (explore_de_score.py, roster contract) reads.

STATE  RosterState — numpy arrays for one chunk of cells:
  tree   per tree: Cell, Patch, Type, ID, the 6 traits, Height, agb, vegc, LAI, fpc_ind, D95, Age, c, G, W,
         d_agb_prev, the printed fluxes/hazards (npp, transp, wscal_mean, mort_npp, mort_age, mort_water, mort_temp,
         mort), isdead (flagged this year), hidden (alive but below the 5 m print cut), hidden_years
  patch  per (cell, patch), index cell_idx * npatch + patch: grass<t>_{fpc,LAI,agb}, loss_ring[:, 0..19] (frac loss
         of years y, y-1, ...; NaN = no history), hist_years
  cell   cells (sorted), seedbank (polars frame: Cell, KEY, Type, traits, first_year, last_year, n_years),
         idmax[cell_idx, patch, Type]
  aux_tree / aux_patch / aux_cell: arm-owned dicts of arrays (AR residuals, GRU states, ...). The engine keeps
         aux_tree aligned with the tree arrays (compaction, recruits get the stepper's aux rows).

STEPPER PROTOCOL (an arm is a class with these two methods; see Replay / Frozen below)
  init(state, ctx)                                   -> None   (may fill state.aux_*)
  step(state, ctx, year, clim_y1, flags_y1, rand)    -> StepOut for the transition year -> year + 1
    clim_y1   polars frame (Cell + climate columns of year+1, cell order = state.cell["cells"]) from the provider
    flags_y1  {"rh_on": int, "bin_feb2026": int} of year+1 (segment flags stay live in every climate mode)
    rand      Rand: counter-based random numbers keyed by (arm, rep, gcm, stream, year, keys...) — NOT by chunk and
              NOT by scenario, so a chunk boundary changes nothing and scenario legs share their random numbers
              (common random numbers, the way the original model's legs do)
  StepOut(tree=..., isdead=..., hidden=..., remove=None, recruits=None, grass=None, aux_tree=None,
          aux_recruits=None, aux_patch=None, aux_cell=None)
    tree      dict of updated per-tree arrays for EVERY tree of the state (same order), at least the dynamic
              fields the arm changes; missing fields keep their year-y value
    isdead    bool: flagged dead at year+1 (emitted with isdead = 1 at year+1 if not hidden, then removed)
    hidden    bool: alive at year+1 but not printed (below 5 m); hidden trees are kept up to HIDDEN_MAX years
    recruits  dict of arrays for NEW trees at year+1 (Cell, Patch, Type, traits, state, isdead, hidden; ID = -1 ->
              the engine assigns idmax + 1 per (Cell, Patch, Type))

ENGINE-OWNED BOOKKEEPING (identical for every arm): emission of every non-hidden tree at year+1 incl. the flagged
dead; compaction; recruit insertion + ID assignment; the patch cover-loss ring (frac fpc lost by printed living
trees of year y that are dead or hidden at year+1); the seedbank refresh (printed trees of year+1 enter; entries
whose last year is >= max_age ago leave; n_years capped at the window = exact for continuously printed trees);
hidden_years.

CLIMATE PROVIDER  Climate(mode): actual (SH0 segments -> cell_year + cell_year_ext) | frozen_mean (SH1 clim8514;
anom_* = 0) | resampled:<rep> (SH0 blind_yearmap: the same Historical year for every cell). Years > 2070 refused.

RUN  explore_de_engine.py run --arm A --stepper module:Class [--kwargs JSON] --gcm G --seed 1 --start 1985|2014|2044
     --end 2044 --legs ssp126,ssp370 [--rep 1] [--clim actual] [--cellset dev] [--chunk-size 100] [--chunks i,j]
     [--cells FILE] [--timing]
     -> runs/<arm>/<gcm>_s<seed>_<start>-<end>_<legs>_<clim>_r<rep>/chunk_<k>/y<Y>_<scen>.parquet + meta_<k>.json
     The START year's roster (= the truth, living trees) is written too, so a REPLAY scores exactly; score every
     other arm with the scorer's --start-year <start> so the truth's own start roster is not counted as skill.
     The seedbank is refreshed only for an arm with `needs_bank = True` (it costs a group-by per year).
     A start before 2015 with ssp legs runs ONE Historical part to 2014 (emitted as scen = Historical) and forks the
     state into every leg (the legs branch from the arm's own 2014 state with common random numbers ->
     score with --legs-branched yes).
     submit ... -> the same as a SLURM array over chunks (+ optional scorer job)
TESTS  explore_de_engine.py conform -> the four conformance tests (REPLAY == truth exactly through the scorer; FROZEN
     2014 == the 2014 truth year's statistics; same seed byte-identical / other rep different; chunk boundary inert)
CO2 and wind are never inputs. Nothing Germany-specific is hard-coded.
"""
from __future__ import annotations

import argparse
import copy
import glob
import hashlib
import importlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import explore_de_sh_init as si  # noqa: E402
import explore_de_sh_patch as sp  # noqa: E402
import explore_de_sh_rules as rl  # noqa: E402
import explore_de_sh_trans as tr  # noqa: E402

XDE = tr.XDE
RUNS = os.environ.get("XDE_RUNS", os.path.join(XDE, "runs"))
STATUS = os.path.join(XDE, "_status", "SH6.md")
REG = tr.REG
KEY = tr.KEY
HIDDEN_MAX = 30
LAST_SIM_YEAR = 2070  # owner decision 2026-10-01: nothing after 2070 is simulated (2071+ truth unusable)
NLAG = sp.NLAG
TREE_F32 = ["SLA", "Wooddens", "D95max", "minwscal", "Longevity", "beta_root", "Height", "agb", "vegc", "LAI",
            "fpc_ind", "D95", "Age", "G", "W", "d_agb_prev", "npp", "transp", "wscal_mean", "mort_npp", "mort_age",
            "mort_water", "mort_temp", "mort"]
TREE_INT = {"Cell": np.int16, "Patch": np.int16, "Type": np.int8, "ID": np.int32, "c": np.int8,
            "hidden_years": np.int16}
TREE_BOOL = ["isdead", "hidden"]
EMIT = ["Year", "Cell", "Patch", "Type", "ID", "isdead", "Height", "SLA", "Wooddens", "D95max", "minwscal",
        "Longevity", "beta_root", "agb", "vegc", "LAI", "fpc_ind", "D95", "Age", "c"]
log = tr.log


def status(line: str):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    with open(STATUS, "a") as f:
        f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} {line}\n")


# ================================================================================================ random numbers
def _h64(s: str) -> int:
    return int.from_bytes(hashlib.sha256(s.encode()).digest()[:8], "big")


class Rand:
    """Counter-based random numbers: u = hash(arm, rep, gcm, stream, year, keys...) -> [0, 1). Deterministic per tree
    / patch / cell whatever the chunking, identical across scenario legs (scenario is NOT in the hash)."""

    def __init__(self, arm: str, rep: int, gcm: str):
        self.base = (arm, int(rep), gcm)

    def _seed(self, stream: str, year: int) -> np.uint64:
        return np.uint64(_h64(f"{self.base}|{stream}|{int(year)}"))

    def uniform(self, stream: str, year: int, *keys) -> np.ndarray:
        n = len(keys[0])
        h = np.full(n, self._seed(stream, year), dtype=np.uint64)
        for k in keys:
            h = tr._splitmix(h ^ np.asarray(k).astype(np.int64).view(np.uint64))
        h = tr._splitmix(h)
        return ((h >> np.uint64(11)).astype(np.float64) + 0.5) * (1.0 / 9007199254740992.0)

    def normal(self, stream: str, year: int, *keys) -> np.ndarray:
        u1 = self.uniform(stream + "#n1", year, *keys)
        u2 = self.uniform(stream + "#n2", year, *keys)
        return np.sqrt(-2.0 * np.log(u1)) * np.cos(2.0 * np.pi * u2)

    def poisson(self, lam, stream: str, year: int, *keys) -> np.ndarray:
        """Inversion; exact for any lam (loop length ~ max lam + a few sd)."""
        u = self.uniform(stream, year, *keys)
        lam = np.asarray(lam, dtype=np.float64)
        k = np.zeros(u.shape, dtype=np.int64)
        p = np.exp(-lam)
        cdf = p.copy()
        active = u > cdf
        while active.any():
            k[active] += 1
            p = np.where(active, p * lam / np.maximum(k, 1), p)
            cdf = np.where(active, cdf + p, cdf)
            active = active & (u > cdf) & (k < 10000)
        return k

    def generator(self, stream: str, year: int, cell: int) -> np.random.Generator:
        """A numpy Generator for draws that are awkward to key (e.g. a sampler): one per (stream, year, cell)."""
        return np.random.Generator(np.random.PCG64(_h64(f"{self.base}|{stream}|{int(year)}|cell{int(cell)}")))


# ================================================================================================ climate provider
class Climate:
    def __init__(self, gcm: str, traj: str, seed: int, cells: np.ndarray, mode: str = "actual", cols=None):
        self.gcm, self.traj, self.seed, self.mode = gcm, traj, int(seed), mode
        self.cells = np.asarray(cells, dtype=np.int32)
        seg = pl.read_parquet(os.path.join(REG, "segments.parquet")).filter(
            (pl.col("gcm") == gcm) & (pl.col("scen") == traj) & (pl.col("seed") == seed))
        self.seg = {int(r["Year"]): r for r in seg.iter_rows(named=True)}
        cy = pl.scan_parquet(tr.CLIM)
        ex = pl.scan_parquet(tr.EXT)
        exn = [c for c in ex.collect_schema().names() if c not in ("excluded", "exclusion_reason", "truth_usable")]
        self.base = (cy.filter((pl.col("gcm") == gcm) & pl.col("Cell").is_in(self.cells.tolist()))
                     .join(ex.select(exn), on=["gcm", "scen", "Cell", "Year"], how="left"))
        names = [c for c in self.base.collect_schema().names() if c not in ("gcm", "scen", "Cell", "Year")]
        self.cols = names if cols is None else list(cols)
        if mode.startswith("resampled"):
            self.rep = int(mode.split(":")[1])
            ym = pl.read_parquet(os.path.join(REG, "blind_yearmap.parquet")).filter(
                (pl.col("gcm") == gcm) & (pl.col("rep") == self.rep))
            self.ymap = {int(a): (b, int(c)) for a, c, b in ym.select("Year", "src_year", "src_scen").rows()}
        if mode == "frozen_mean":
            c8 = pl.read_parquet(os.path.join(XDE, "shared", "climate", "clim8514.parquet")).filter(
                (pl.col("gcm") == gcm) & pl.col("Cell").is_in(self.cells.tolist()))
            fr = pl.DataFrame({"Cell": self.cells}).join(c8, on="Cell", how="left")
            out = [pl.col("Cell")]
            for c in self.cols:
                if c in fr.columns:
                    out.append(pl.col(c).cast(pl.Float32))
                elif c.startswith("anom_"):
                    out.append(pl.lit(0.0, pl.Float32).alias(c))
                else:
                    out.append(pl.lit(None, pl.Float32).alias(c))
            self.frozen = fr.select(out)
        self._cache: dict = {}

    def flags(self, year: int) -> dict:
        r = self.seg[int(year)]
        return {"rh_on": int(r["rh_on"]), "bin_feb2026": int(r["bin_feb2026"])}

    def year(self, year: int) -> pl.DataFrame:
        year = int(year)
        if year > LAST_SIM_YEAR:
            raise ValueError(f"year {year} > {LAST_SIM_YEAR}: owner decision 2026-10-01, nothing after 2070")
        if year in self._cache:
            return self._cache[year]
        if self.mode == "frozen_mean":
            out = self.frozen
        else:
            if self.mode == "actual":
                r = self.seg[year]
                scen, cyear = r["clim_scen"], int(r["clim_year"])
            else:
                scen, cyear = self.ymap[year]
            df = self.base.filter((pl.col("scen") == scen) & (pl.col("Year") == cyear)).select(
                ["Cell"] + self.cols).collect()
            out = pl.DataFrame({"Cell": self.cells}).join(df.with_columns(pl.col("Cell").cast(pl.Int32)), on="Cell",
                                                         how="left")
            assert out.height == len(self.cells)
        if len(self._cache) > 4:
            self._cache.pop(next(iter(self._cache)))
        self._cache[year] = out
        return out


# ================================================================================================ state
@dataclass
class RosterState:
    year: int
    npatch: int
    tree: dict
    patch: dict
    cell: dict
    aux_tree: dict = field(default_factory=dict)
    aux_patch: dict = field(default_factory=dict)
    aux_cell: dict = field(default_factory=dict)

    @property
    def n(self) -> int:
        return len(self.tree["Cell"])

    def cell_index(self, cells: np.ndarray) -> np.ndarray:
        return np.searchsorted(self.cell["cells"], cells)

    def patch_index(self) -> np.ndarray:
        return self.cell_index(self.tree["Cell"]) * self.npatch + self.tree["Patch"].astype(np.int64)

    def take(self, idx: np.ndarray):
        self.tree = {k: v[idx] for k, v in self.tree.items()}
        self.aux_tree = {k: v[idx] for k, v in self.aux_tree.items()}

    def frame(self) -> pl.DataFrame:
        return pl.DataFrame(self.tree)


@dataclass
class StepOut:
    tree: dict
    isdead: np.ndarray
    hidden: np.ndarray
    remove: np.ndarray | None = None
    recruits: dict | None = None
    grass: dict | None = None
    aux_tree: dict | None = None
    aux_recruits: dict | None = None
    aux_patch: dict | None = None
    aux_cell: dict | None = None


def _typed(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        v = np.asarray(v)
        if k in TREE_INT:
            out[k] = v.astype(TREE_INT[k])
        elif k in TREE_BOOL:
            out[k] = v.astype(bool)
        elif k in TREE_F32 or v.dtype.kind == "f":
            out[k] = v.astype(np.float32)
        else:
            out[k] = v
    return out


def load_init(name: str, cellset: str, cells: np.ndarray) -> RosterState:
    base = os.path.join(si.INIT, cellset, name)
    dirs = sorted(glob.glob(os.path.join(base, "cb=*")))
    assert dirs, f"no initial state {base} (build SH5 first)"
    metas = [json.load(open(os.path.join(d, "meta.json"))) for d in dirs]
    npatch = int(metas[0]["npatch"])
    Y = int(metas[0]["Y"])
    cl = cells.tolist()

    def rd(f):
        return pl.concat([pl.scan_parquet(os.path.join(d, f)).filter(pl.col("Cell").is_in(cl)) for d in dirs]
                         ).collect()

    T = rd("trees.parquet").sort(["Cell", "Patch", "Type", "ID"])
    have = np.unique(T["Cell"].to_numpy())
    missing = np.setdiff1d(cells, have)
    tree = {c: T[c].to_numpy() for c in ["Cell", "Patch", "Type", "ID"] + tr.TRAITS
            + ["Height", "agb", "vegc", "LAI", "fpc_ind", "D95", "Age", "c", "G", "W", "d_agb_prev", "npp",
               "transp", "wscal_mean", "mort_npp", "mort_age", "mort_water", "mort_temp", "mort"]}
    tree["isdead"] = np.zeros(T.height, bool)
    tree["hidden"] = np.zeros(T.height, bool)
    tree["hidden_years"] = np.zeros(T.height, np.int16)
    tree = _typed(tree)
    Pt = rd("patches.parquet").sort("Cell", "Patch")
    cells_sorted = np.sort(cells)
    assert Pt.height == len(cells_sorted) * npatch, (Pt.height, len(cells_sorted), npatch)
    patch = {c: Pt[c].cast(pl.Float32).to_numpy() for c in Pt.columns if c.startswith("grass")}
    ring = np.full((Pt.height, NLAG), np.nan, dtype=np.float32)
    for k in range(NLAG):
        ring[:, k] = Pt[f"frac_loss_lag{k}"].cast(pl.Float32).fill_null(np.nan).to_numpy()
    patch["loss_ring"] = ring
    patch["hist_years"] = Pt["hist_years"].to_numpy().astype(np.int8)
    bank = rd("bank.parquet")
    im = rd("idmax.parquet")
    idmax = np.zeros((len(cells_sorted), npatch, tr.MAX_TREE_TYPE + 1), dtype=np.int64)
    if im.height:
        ci = np.searchsorted(cells_sorted, im["Cell"].to_numpy())
        idmax[ci, im["Patch"].to_numpy(), im["Type"].to_numpy()] = im["id_max"].to_numpy()
    cell = {"cells": cells_sorted, "bank": bank, "idmax": idmax, "cells_without_trees": missing}
    return RosterState(year=Y, npatch=npatch, tree=tree, patch=patch, cell=cell)


def init_name(gcm: str, seed: int, start: int, leg: str) -> str:
    return f"{gcm}_Historical_s{seed}_{start}" if start <= 2014 else f"{gcm}_{leg}_s{seed}_{start}"


# ================================================================================================ one step
def apply_step(state: RosterState, out: StepOut, year: int, P, needs_bank: bool = True) -> pl.DataFrame:
    """Engine-owned bookkeeping for year -> year + 1. Returns the emission frame of year + 1."""
    n = state.n
    y1 = year + 1
    t = state.tree
    printed_living = ~t["hidden"] & ~t["isdead"]
    fpc_y = np.where(printed_living, t["fpc_ind"].astype(np.float64), 0.0)
    for k, v in out.tree.items():
        assert len(v) == n, f"StepOut.tree[{k}] has {len(v)} rows, state has {n}"
        t[k] = _typed({k: v})[k]
    if out.aux_tree is not None:
        state.aux_tree = out.aux_tree
    isdead = np.asarray(out.isdead, bool)
    hidden = np.asarray(out.hidden, bool) & ~isdead
    t["isdead"] = isdead
    t["hidden"] = hidden
    t["hidden_years"] = np.where(hidden, t["hidden_years"] + 1, 0).astype(np.int16)
    # cover-loss ring (frac of year-y printed living fpc lost to death or the 5 m cut at y+1)
    pidx = state.patch_index()
    npatches = len(state.cell["cells"]) * state.npatch
    tot = np.bincount(pidx, weights=fpc_y, minlength=npatches)
    lost = np.bincount(pidx, weights=np.where(isdead | hidden, fpc_y, 0.0), minlength=npatches)
    frac = np.where(tot > 0, lost / np.where(tot > 0, tot, 1.0), 0.0).astype(np.float32)
    ring = state.patch["loss_ring"]
    state.patch["loss_ring"] = np.concatenate([frac[:, None], ring[:, :-1]], axis=1)
    state.patch["hist_years"] = np.minimum(state.patch["hist_years"] + 1, NLAG).astype(np.int8)
    if out.grass is not None:
        state.patch.update({k: np.asarray(v, np.float32) for k, v in out.grass.items()})
    if out.aux_patch is not None:
        state.aux_patch = out.aux_patch
    if out.aux_cell is not None:
        state.aux_cell = out.aux_cell
    # recruits
    if out.recruits is not None and len(out.recruits.get("Cell", [])):
        R = dict(out.recruits)
        m = len(R["Cell"])
        for k, v in t.items():
            if k not in R:
                if k in ("isdead", "hidden"):
                    R[k] = np.zeros(m, bool)
                elif k == "hidden_years":
                    R[k] = np.zeros(m, np.int16)
                elif k == "ID":
                    R[k] = np.full(m, -1, np.int64)
                elif v.dtype.kind == "f":
                    R[k] = np.full(m, np.nan, np.float32)
                else:
                    raise ValueError(f"recruits lack required field {k}")
        R = _typed(R)
        need = R["ID"] < 0
        if need.any():
            ci = state.cell_index(R["Cell"][need])
            pa = R["Patch"][need].astype(np.int64)
            ty = R["Type"][need].astype(np.int64)
            key = (ci * state.npatch + pa) * (tr.MAX_TREE_TYPE + 1) + ty
            order = np.argsort(key, kind="stable")
            ks = key[order]
            first = np.r_[True, ks[1:] != ks[:-1]]
            grp = np.cumsum(first) - 1
            start_idx = np.flatnonzero(first)
            rank = np.arange(len(ks)) - start_idx[grp]
            im = state.cell["idmax"]
            new = np.empty(len(ks), np.int64)
            new[order] = im[ci[order], pa[order], ty[order]] + 1 + rank
            ids = R["ID"].astype(np.int64)
            ids[need] = new
            R["ID"] = ids.astype(np.int32)
        ci = state.cell_index(R["Cell"])
        np.maximum.at(state.cell["idmax"], (ci, R["Patch"].astype(np.int64), R["Type"].astype(np.int64)),
                      R["ID"].astype(np.int64))
        for k in t:
            t[k] = np.concatenate([t[k], R[k].astype(t[k].dtype)])
        if state.aux_tree:
            ar = out.aux_recruits or {}
            for k, v in state.aux_tree.items():
                add = ar.get(k)
                if add is None:
                    add = np.zeros((m,) + v.shape[1:], v.dtype)
                state.aux_tree[k] = np.concatenate([v, np.asarray(add, v.dtype)])
    # emission (non-hidden, incl. flagged dead) of year + 1
    em = ~t["hidden"]
    E = pl.DataFrame({k: t[k][em] for k in EMIT if k != "Year"}).with_columns(
        Year=pl.lit(y1, pl.Int16), isdead=pl.col("isdead").cast(pl.Int8))
    # seedbank refresh with the printed trees of y+1 (only for arms that read it: needs_bank = True)
    if needs_bank:
        bank_update(state, E, y1, P)
    # compaction: the flagged dead leave; hidden too long leave; arm-requested removals leave
    keep = ~t["isdead"] & (t["hidden_years"] <= HIDDEN_MAX)
    if out.remove is not None:
        rm = np.asarray(out.remove, bool)
        keep &= ~np.r_[rm, np.zeros(state.n - len(rm), bool)]
    state.take(np.flatnonzero(keep))
    state.year = y1
    return E.select(EMIT)


def bank_update(state: RosterState, E: pl.DataFrame, y1: int, P):
    max_age = int(P.g["max_age"])
    B = state.cell["bank"]
    new = tr.with_key(E.select("Cell", "Patch", "Type", "ID", *tr.TRAITS)).with_columns(
        first_year=pl.lit(y1, pl.Int16), last_year=pl.lit(y1, pl.Int16), n_years=pl.lit(1, pl.Int16))
    new = new.select(B.columns)
    B = pl.concat([B, new.cast(B.schema)]).group_by(KEY).agg(
        first_year=pl.col("first_year").min(), last_year=pl.col("last_year").max(),
        n_years=pl.col("n_years").sum(), **{t: pl.col(t).first() for t in tr.TRAITS})
    B = B.filter((y1 - pl.col("last_year").cast(pl.Int32)) < max_age)
    lo = y1 - max_age + 1
    B = B.with_columns(n_years=pl.min_horizontal(
        pl.col("n_years"), (pl.col("last_year").cast(pl.Int32) - pl.max_horizontal(pl.col("first_year").cast(pl.Int32),
                                                                                    pl.lit(lo)) + 1)).cast(pl.Int16))
    state.cell["bank"] = B.select(state.cell["bank"].columns)


# ================================================================================================ built-in steppers
class Replay:
    """REPLAY: the truth through the engine. Every tree's year+1 state, death flag and visibility are read from the
    truth table of the trajectory; truth stems with no match in the state are recruits (with their truth IDs).
    Through the scorer this must reproduce the reference statistics EXACTLY (conformance test i)."""

    def __init__(self, cellset: str = "dev"):
        self.cellset = cellset

    def init(self, state, ctx):
        mem, _, _ = tr.registry()
        hist = tr.historical_of(mem, ctx["gcm"], ctx["seed"])
        self.src = {}
        for y in hist["years_complete"]:
            self.src[int(y)] = list(tr.sources(hist, self.cellset).values())
        self._mem = mem

    def _src(self, ctx, year):
        if year in self.src:
            return self.src[year]
        r = self._mem.filter((pl.col("gcm") == ctx["gcm"]) & (pl.col("scen") == ctx["traj"])
                             & (pl.col("seed") == ctx["seed"]) & ~pl.col("excluded"))
        r = [x for x in r.iter_rows(named=True) if year in [int(v) for v in x["years_complete"]]]
        assert r, f"no truth table for {ctx['traj']} {year}"
        return list(tr.sources(r[0], self.cellset).values())

    def step(self, state, ctx, year, clim_y1, flags_y1, rand):
        y1 = year + 1
        cells = state.cell["cells"].tolist()
        tru = pl.concat([tr.read_year(s, y1, None).filter(pl.col("Cell").is_in(cells)) for s in self._src(ctx, y1)])
        tru = tr.with_key(tru.filter(pl.col("Type") <= tr.MAX_TREE_TYPE))
        st = tr.with_key(pl.DataFrame({k: state.tree[k] for k in ["Cell", "Patch", "Type", "ID", "SLA", "Wooddens"]})
                         ).with_row_index("_i")
        J = st.join(tru, on=KEY, how="left", suffix="_t")
        J = J.sort("_i")
        hit = J["Year"].is_not_null().to_numpy()
        fields = ["Height", "agb", "vegc", "LAI", "fpc_ind", "D95", "Age", "npp", "transp", "wscal_mean",
                  "mort_npp", "mort_age", "mort_water", "mort_temp", "mort"]
        upd = {}
        for f in fields:
            v = J[f].to_numpy().astype(np.float32)
            upd[f] = np.where(hit, v, state.tree[f])
        isdead = np.where(hit, J["isdead"].fill_null(0).to_numpy() == 1, False)
        hidden = ~hit
        new = tru.join(st.select(KEY), on=KEY, how="anti")
        rec = {c: new[c].to_numpy() for c in ["Cell", "Patch", "Type", "ID"] + tr.TRAITS + fields}
        rec["isdead"] = new["isdead"].to_numpy() == 1
        rec["c"] = np.zeros(new.height, np.int8)
        rec["G"] = np.zeros(new.height, np.float32)
        rec["W"] = np.zeros(new.height, np.float32)
        rec["d_agb_prev"] = np.zeros(new.height, np.float32)
        return StepOut(tree=upd, isdead=isdead, hidden=hidden, recruits=rec)


class Frozen:
    """FROZEN: nothing changes; the start roster is emitted unchanged every year (no growth, no death, no aging)."""

    def init(self, state, ctx):
        pass

    def step(self, state, ctx, year, clim_y1, flags_y1, rand):
        n = state.n
        return StepOut(tree={}, isdead=np.zeros(n, bool), hidden=state.tree["hidden"].copy())


def load_stepper(spec: str, kwargs: dict):
    if spec in ("replay", "Replay"):
        return Replay(**kwargs)
    if spec in ("frozen", "Frozen"):
        return Frozen(**kwargs)
    mod, cls = spec.split(":")
    return getattr(importlib.import_module(mod), cls)(**kwargs)


# ================================================================================================ the run
def run_chunk(a, k: int, cells: np.ndarray, out_dir: str) -> dict:
    P = rl.load_params()
    legs = a.legs.split(",")
    stepper = load_stepper(a.stepper, json.loads(a.kwargs or "{}"))
    timing = {"init": 0.0, "climate": 0.0, "step": 0.0, "engine": 0.0, "write": 0.0}
    t0 = time.process_time()
    name = init_name(a.gcm, a.seed, a.start, legs[0])
    state = load_init(name, a.cellset, cells)
    assert state.year == a.start, (state.year, a.start)
    ctx = {"gcm": a.gcm, "seed": a.seed, "rep": a.rep, "arm": a.arm, "cellset": a.cellset, "npatch": state.npatch,
           "P": P, "start": a.start, "clim_mode": a.clim, "traj": "Historical" if a.start <= 2014 else legs[0]}
    rand = Rand(a.arm, a.rep, a.gcm)
    stepper.init(state, ctx)
    timing["init"] += time.process_time() - t0
    cd = os.path.join(out_dir, f"chunk_{k:03d}")
    if os.path.isdir(cd):
        shutil.rmtree(cd)
    os.makedirs(cd)
    rows = {}
    label0 = "Historical" if (a.start <= 2014 and legs[0] != "Historical") else legs[0]
    em = ~state.tree["hidden"]
    E0 = pl.DataFrame({k: state.tree[k][em] for k in EMIT if k != "Year"}).with_columns(
        Year=pl.lit(a.start, pl.Int16), isdead=pl.col("isdead").cast(pl.Int8)).select(EMIT)
    E0 = E0.with_columns(gcm=pl.lit(a.gcm), scen=pl.lit(label0), rep=pl.lit(a.rep, pl.Int8), arm=pl.lit(a.arm))
    E0.write_parquet(os.path.join(cd, f"y{a.start}_{label0}.parquet"), compression="zstd")
    rows[f"{label0}_{a.start}"] = E0.height
    needs_bank = bool(getattr(stepper, "needs_bank", False))

    def run_seg(state, traj, label, y_from, y_to):
        ctx["traj"] = traj
        clim = Climate(a.gcm, traj, a.seed, state.cell["cells"], a.clim)
        for y in range(y_from, y_to):
            t1 = time.process_time()
            cy = clim.year(y + 1)
            fl = clim.flags(y + 1)
            t2 = time.process_time()
            out = stepper.step(state, ctx, y, cy, fl, rand)
            t3 = time.process_time()
            E = apply_step(state, out, y, P, needs_bank)
            t4 = time.process_time()
            E.with_columns(gcm=pl.lit(a.gcm), scen=pl.lit(label), rep=pl.lit(a.rep, pl.Int8),
                           arm=pl.lit(a.arm)).write_parquet(os.path.join(cd, f"y{y + 1}_{label}.parquet"),
                                                            compression="zstd")
            t5 = time.process_time()
            timing["climate"] += t2 - t1
            timing["step"] += t3 - t2
            timing["engine"] += t4 - t3
            timing["write"] += t5 - t4
            rows[f"{label}_{y + 1}"] = E.height

    if a.start <= 2014 and legs[0] != "Historical":
        fork = 2014
        run_seg(state, legs[0], "Historical", a.start, min(fork, a.end))
        if a.end > fork:
            base = state
            for leg in legs:
                st = copy.deepcopy(base)
                run_seg(st, leg, leg, fork, a.end)
    else:
        assert len(legs) == 1
        run_seg(state, legs[0], legs[0], a.start, a.end)
    n_cy = len(cells) * (a.end - a.start) * (len(legs) if a.start > 2014 or a.end <= 2014 else 1)
    if a.start <= 2014 < a.end and legs[0] != "Historical":
        n_cy = len(cells) * ((2014 - a.start) + len(legs) * (a.end - 2014))
    meta = {"chunk": k, "cells": [int(c) for c in cells], "rows": rows, "timing_core_s": timing,
            "cell_years": n_cy, "core_s_per_cell_year": sum(timing.values()) / max(n_cy, 1),
            "core_s_per_cell_year_step": timing["step"] / max(n_cy, 1)}
    json.dump(meta, open(os.path.join(out_dir, f"meta_{k:03d}.json"), "w"), indent=1)
    return meta


def run_dir(a) -> str:
    legs = a.legs.replace(",", "+")
    return os.path.join(RUNS, a.arm, f"{a.gcm}_s{a.seed}_{a.start}-{a.end}_{legs}_{a.clim.replace(':', '')}_r{a.rep}")


def chunks_of(a) -> list[np.ndarray]:
    _, _, folds = tr.registry()
    if a.cells:
        cells = np.array(sorted(int(x) for x in open(a.cells).read().split()), dtype=np.int64)
    else:
        cells = tr.cell_list(folds, a.cellset).astype(np.int64)
    return [cells[i:i + a.chunk_size] for i in range(0, len(cells), a.chunk_size)]


def stage_run(a):
    assert a.end <= LAST_SIM_YEAR
    od = run_dir(a)
    os.makedirs(od, exist_ok=True)
    ch = chunks_of(a)
    sel = range(len(ch)) if not a.chunks else [int(x) for x in a.chunks.split(",")]
    spec = {k: v for k, v in vars(a).items() if k not in ("stage", "chunks")}
    json.dump({**spec, "n_chunks": len(ch)}, open(os.path.join(od, "run.json"), "w"), indent=1)
    for k in sel:
        t = time.time()
        m = run_chunk(a, k, ch[k], od)
        log(f"chunk {k}: {len(ch[k])} cells, {m['core_s_per_cell_year']:.4f} core-s/cell-year "
            f"(step {m['core_s_per_cell_year_step']:.4f}), wall {time.time() - t:.0f} s")


def stage_submit(a):
    od = run_dir(a)
    os.makedirs(od, exist_ok=True)
    n = len(chunks_of(a))
    logs = os.path.join(REPO, "logs")
    args = " ".join(f"--{k.replace('_', '-')} '{v}'" for k, v in vars(a).items()
                    if k not in ("stage", "chunks", "parallel", "ncpu", "timing") and v is not None and v is not False)
    jcf = os.path.join(od, "submit.jcf")
    with open(jcf, "w") as f:
        f.write(f"""#!/bin/bash
#SBATCH --job-name=X-de-run-{a.arm}
#SBATCH --account=waldspektrum
#SBATCH --partition=priority
#SBATCH --qos=priority
#SBATCH --cpus-per-task={a.ncpu}
#SBATCH --time=04:00:00
#SBATCH --array=0-{n - 1}%{a.parallel}
#SBATCH --output={logs}/X-de-run-{a.arm}.%A_%a.out
set -eu
export POLARS_MAX_THREADS={a.ncpu} OMP_NUM_THREADS={a.ncpu}
{tr.PY} {os.path.abspath(__file__)} run {args} --chunks "$SLURM_ARRAY_TASK_ID"
echo "=== JOB DONE chunk=$SLURM_ARRAY_TASK_ID exit=$? ==="
""")
    jid = subprocess.run(["sbatch", "--parsable", jcf], capture_output=True, text=True, check=True).stdout.strip()
    log(f"submitted {jid}: {n} chunks -> {od}")
    status(f"run {a.arm} {os.path.basename(od)}: array {jid} ({n} chunks)")
    return jid


# ================================================================================================ conformance tests
def _ns(**kw):
    d = dict(arm="conform", stepper="replay", kwargs=None, gcm="MPI-ESM1-2-HR", seed=1, start=1985, end=2044,
             legs="ssp370", rep=1, clim="actual", cellset="dev", chunk_size=100, chunks=None, cells=None)
    d.update(kw)
    return argparse.Namespace(**d)


def _score(pred, label, extra):
    cmd = [tr.PY, os.path.join(REPO, "scripts", "explore_de_score.py"), "score", "--pred", pred, "--format", "roster",
           "--label", label, "--scope", "covered", "--out", os.path.join(XDE, "runs", "_conform_scores")] + extra
    log(" ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    open(os.path.join(XDE, "runs", "_conform_scores", f"{label}.log"), "w").write(r.stdout + r.stderr)
    return r


def stage_conform(a):
    out = {}
    os.makedirs(os.path.join(XDE, "runs", "_conform_scores"), exist_ok=True)
    tests = a.tests.split(",")
    if "iv" in tests or "iii" in tests:
        cells = chunks_of(_ns())[0][:20]
        cf = os.path.join(XDE, "runs", "_conform_scores", "cells20.txt")
        open(cf, "w").write("\n".join(str(c) for c in cells))
    if "i" in tests:
        ns = _ns(arm="conform_replay", end=2044, legs="ssp126,ssp370")
        nch = len(chunks_of(ns))
        if not all(os.path.exists(os.path.join(run_dir(ns), f"meta_{k:03d}.json")) for k in range(nch)):
            stage_run(ns)
        r = _score(run_dir(ns), "conform_replay", ["--split", "DEV-B",
                                                    "--cells", os.path.join(XDE, "shared", "scorer", "cells_dev.txt")])
        lab = os.path.join(XDE, "runs", "_conform_scores", "conform_replay")
        cel = pl.read_parquet(os.path.join(lab, "cells.parquet")) if os.path.exists(
            os.path.join(lab, "cells.parquet")) else None
        res = {"scorer_rc": r.returncode}
        if cel is not None:
            both = cel.filter(pl.col("E").is_not_null() & pl.col("C").is_not_null())
            d = (both["E"].cast(pl.Float64) - both["C"].cast(pl.Float64)).abs()
            res["rows_compared"] = both.height
            res["rows_E_missing"] = cel.filter(pl.col("E").is_null() & pl.col("C").is_not_null()).height
            res["by_kind"] = {k: float(v) for k, v in both.with_columns(_d=d).group_by("target_kind").agg(
                pl.col("_d").max()).rows()}
            res["max_abs_E_minus_C"] = float(d.max())
            res["pass"] = float(d.max()) == 0.0 and res["rows_E_missing"] == 0
        out["i_replay_exact"] = res
    if "ii" in tests:
        ns = _ns(arm="conform_frozen", stepper="frozen", start=2014, end=2044, legs="ssp370")
        stage_run(ns)
        out["ii_frozen"] = frozen_check(run_dir(ns))
    if "iii" in tests:
        cf = os.path.join(XDE, "runs", "_conform_scores", "cells20.txt")
        h = {}
        for tag, rep in (("a", 1), ("b", 1), ("c", 2)):
            ns = _ns(arm="conform_det", stepper="explore_de_engine_testarm:Noisy", start=2014, end=2020, cells=cf,
                     rep=rep)
            od = os.path.join(RUNS, "_conform", f"det_{tag}")
            os.makedirs(od, exist_ok=True)
            run_chunk(ns, 0, chunks_of(ns)[0], od)
            h[tag] = _dir_hash(os.path.join(od, "chunk_000"))
        out["iii_determinism"] = {"same_seed_identical": h["a"] == h["b"], "other_rep_differs": h["a"] != h["c"],
                                  "hashes": h}
        out["iii_determinism"]["pass"] = (out["iii_determinism"]["same_seed_identical"]
                                          and out["iii_determinism"]["other_rep_differs"])
    if "iv" in tests:
        cf = os.path.join(XDE, "runs", "_conform_scores", "cells20.txt")
        res = {}
        for cs in (20, 7):
            ns = _ns(arm="conform_chunk", stepper="explore_de_engine_testarm:Noisy", start=2014, end=2020, cells=cf,
                     chunk_size=cs)
            od = os.path.join(RUNS, "_conform", f"chunk{cs}")
            os.makedirs(od, exist_ok=True)
            for k, c in enumerate(chunks_of(ns)):
                run_chunk(ns, k, c, od)
            res[cs] = pl.read_parquet(os.path.join(od, "chunk_*", "*.parquet")).sort(
                "Year", "scen", "Cell", "Patch", "Type", "ID")
        same = res[20].equals(res[7])
        out["iv_chunk_inert"] = {"rows": res[20].height, "identical": same, "pass": same}
    out["pass"] = all(v.get("pass", False) for v in out.values() if isinstance(v, dict))
    json.dump(out, open(os.path.join(XDE, "runs", "_conform_scores", f"conform_{'_'.join(tests)}.json"), "w"),
              indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))
    status(f"conformance {tests}: pass={out['pass']}")


def _dir_hash(d):
    h = hashlib.sha256()
    for f in sorted(glob.glob(os.path.join(d, "*.parquet"))):
        df = pl.read_parquet(f).sort("Cell", "Patch", "Type", "ID")
        h.update(os.path.basename(f).encode())
        h.update(df.write_csv().encode())
    return h.hexdigest()


def frozen_check(od) -> dict:
    """FROZEN from 2014: every 2015-2044 year's emitted roster == the 2014 truth roster (living, printed), so the
    w2015 window statistics equal the 2014 truth year's statistics. Checked by reducing both through the scorer's
    own reduce_window (explore_de_reference), float tolerance 1e-6."""
    import explore_de_reference as R
    E = pl.read_parquet(os.path.join(od, "chunk_*", "*.parquet"))
    cells = np.unique(E["Cell"].to_numpy())
    mem, _, _ = tr.registry()
    hist = tr.historical_of(mem, "MPI-ESM1-2-HR", 1)
    T = tr.read_year(hist["ind_dev_path"], 2014, None).filter(
        (pl.col("Type") <= 6) & (pl.col("isdead") == 0) & pl.col("Cell").is_in(cells.tolist()))
    cy_e = pl.DataFrame({"Cell": cells.astype(np.int32)}).join(pl.DataFrame({"Year": list(range(2015, 2045))}),
                                                                how="cross")
    cy_t = pl.DataFrame({"Cell": cells.astype(np.int32), "Year": [2014] * len(cells)})
    e = R.reduce_window(E.filter(pl.col("Year").is_between(2015, 2044)).with_columns(pl.col("Cell").cast(pl.Int32)),
                        cy_e)
    t = R.reduce_window(T.with_columns(pl.col("Cell").cast(pl.Int32)), cy_t)
    keys = [c for c in e.columns if c in ("Cell", "quantity")]
    num = [c for c in e.columns if c not in keys and e.schema[c].is_numeric()]
    j = e.join(t, on=keys, suffix="_t")
    worst = 0.0
    for c in num:
        if f"{c}_t" in j.columns:
            a_, b_ = j[c].cast(pl.Float64).to_numpy(), j[f"{c}_t"].cast(pl.Float64).to_numpy()
            ok = np.isfinite(a_) & np.isfinite(b_)
            if ok.any():
                rel = np.abs(a_[ok] - b_[ok]) / np.maximum(np.abs(b_[ok]), 1e-12)
                worst = max(worst, float(rel.max()))
    return {"cells": len(cells), "quantities": num, "max_rel_diff": worst, "pass": worst <= 1e-6}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["run", "submit", "conform"])
    ap.add_argument("--arm", default="arm")
    ap.add_argument("--stepper", default="replay")
    ap.add_argument("--kwargs")
    ap.add_argument("--gcm", default="MPI-ESM1-2-HR")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--start", type=int, default=1985)
    ap.add_argument("--end", type=int, default=2044)
    ap.add_argument("--legs", default="ssp370")
    ap.add_argument("--rep", type=int, default=1)
    ap.add_argument("--clim", default="actual")
    ap.add_argument("--cellset", default="dev")
    ap.add_argument("--chunk-size", type=int, default=100)
    ap.add_argument("--chunks")
    ap.add_argument("--cells")
    ap.add_argument("--parallel", type=int, default=8)
    ap.add_argument("--ncpu", type=int, default=8)
    ap.add_argument("--timing", action="store_true")
    ap.add_argument("--tests", default="i,ii,iii,iv")
    a = ap.parse_args(argv)
    {"run": stage_run, "submit": stage_submit, "conform": stage_conform}[a.stage](a)


if __name__ == "__main__":
    main()
