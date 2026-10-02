#!/usr/bin/env python
"""Germany (FirEUrisk 9 km grid) — the ANATOMY of one LPJmL-FIT forest year in the `ind` table.

Line X exploration probe (read-only on the production runs; writes only under
/p/tmp/jamirp/X_de/anatomy/).  It measures exactly what a one-year transition y -> y+1 of the
emitted tree table looks like, so a data-driven emulator's transition table and rollout are
defined on the right population:

  1 identity          (Cell, Patch, Type, ID) uniqueness, Age +1, trait immutability, ID reuse
  2 fate              every living tree stem at y: alive / flagged dead / absent at y+1
  3 death channels    isdead vs the printed hazard `mort`, hard kills, fire, bioclimatic kills,
                      first-year-of-restart garbage in mort_*
  4 recruitment       entries into the > 5 m population: counts, height/age at entry, PFT mix,
                      inheritance signature, relation to patch gaps (lags)
  5 hidden state      the bm_inc_counter recovered algebraically from mort_npp (route 2b of
                      explore_hidden_counter.py), with truth-free gates
  6 patch structure   stems per patch, grass rows, growth persistence baseline
  7 state vs flux     which columns are carried state and which are annual fluxes

Stages (argv[1]):
  extract_full <label>    byte-range read of whole-Germany years -> full/<label>_<year>.parquet
  extract_sub  <label>    streaming read of a whole file, cells with Cell % SUBMOD == 0
  analyze_full            all whole-Germany analyses (needs extract_full of every window)
  analyze_sub  <label>    long-series analyses on the cell subsample (lags, inheritance, fire share)

Data basis: /p/projects/waldspektrum/data/LPJmLFIT/productionruns_jamir (READ-ONLY).
"""

from __future__ import annotations

import io
import json
import math
import os
import re
import subprocess
import sys
import time

import numpy as np
import polars as pl

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = "/p/projects/waldspektrum/data/LPJmLFIT/productionruns_jamir"
OUT = "/p/tmp/jamirp/X_de/anatomy"
LPJROOT = "/home/jamirp/lpjml56fit"
PARAMS = os.path.join(REPO, "test/testitems/references/S_pft_mortality_params.csv")
DEVDIR = "/p/tmp/jamirp/X_de/ind_dev"  # explore_de_convert.py dev subset (Cell % 10 == 0)
SUBMOD = 10  # cell subsample for the 30-year series: Cell % 10 == 0 -> 907 of 9067 cells

COLS = ["Year", "ID", "Type", "Height", "Age", "agb", "vegc", "transp", "npp", "gpp",
        "wscal_mean", "SLA", "Longevity", "Wooddens", "LAI", "fpc_ind", "minwscal", "D95",
        "D95max", "beta_root", "k_root", "mort_npp", "mort_age", "mort_water", "mort_temp",
        "mort", "isdead", "Patch", "Cell"]
INTS = {"Year": pl.Int16, "ID": pl.Int64, "Type": pl.Int8, "Age": pl.Int32, "isdead": pl.Int8,
        "Patch": pl.Int16, "Cell": pl.Int16}
# Float32 is LOSSLESS with respect to the writer's %g = 6 significant digits (two distinct
# 6-digit decimals never share a float32), and an identical printed string always parses to the
# same float32, so bit-identity checks on traits stay exact.
SCHEMA = {c: INTS.get(c, pl.Float32) for c in COLS}
FLOATS = [c for c in COLS if c not in INTS]

# windows read for whole Germany (label -> file, years)
MPI = f"{ROOT}/MPI-ESM1-2-HR"
FILES = {
    "H1": f"{MPI}/Historical/random_seed_1/output/ind_.csv",       # 1985-2014 (run 1950-2014)
    "S44": f"{MPI}/ssp370/random_seed_1/output/ind_2044.csv",      # 2015-2044 (restart 2014)
    "S100": f"{MPI}/ssp370/random_seed_1/output/ind_2100.csv",     # 2071-2100 (restart 2070)
}
FULL_YEARS = {"H1": [1985, 1986, 1987, 1988, 1989, 2014], "S44": [2015, 2016, 2017],
              "S100": [2071, 2072, 2073, 2074, 2075]}
# the first simulated year of each restarted SEGMENT (from the run configs):
#   Historical: restart_1950 -> sim 1950-2014, output from 1985  => 1985 is NOT a restart year
#   ssp370 2044 segment: restart_2014 -> 2015-2044               => 2015 IS
#   ssp370 2070 segment: restart_2044 -> 2045-2070 (no ind)
#   ssp370 2100 segment: restart_2070 -> 2071-2100               => 2071 IS
RESTART_FIRST = {2015, 2071}

RESIST = {0: 0.12, 1: 0.12, 2: 0.5, 3: 0.3, 4: 0.12, 5: 0.3, 6: 0.12}  # par/pft_lpjmlfit.js "resist"
K_BEER = {0: 0.59, 1: 0.45, 2: 0.59, 3: 0.59, 4: 0.45, 5: 0.59, 6: 0.45}
PATCHAREA = 225.0  # par/lpjparam_fit.js; nind = 1/patcharea
NPATCH = 250
TRAITS = ["SLA", "Wooddens", "D95max", "minwscal", "Longevity", "beta_root", "k_root"]
FORBIDDEN = [(1.0, 5.0 / 3.0), (2.0, 2.5), (3.0, 10.0 / 3.0), (4.0, 25.0 / 6.0), (5.0, 5.0)]


def log(*a):
    print(*a, flush=True)


def res_path(name: str) -> str:
    d = os.path.join(OUT, "results", os.environ.get("ANAT_RESSUB", ""))
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, name)


# ============================================================ extraction
def _year_at(f, off: int) -> int | None:
    f.seek(off)
    if off:
        f.readline()
    ln = f.readline()
    if not ln:
        return None
    return int(ln.split(b",", 1)[0])


def first_offset(path: str, year: int) -> int:
    """Byte offset of the first line whose Year >= year (rows are year-major)."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        h = len(f.readline())
        lo, hi = h, size
        while hi - lo > 1 << 16:
            mid = (lo + hi) // 2
            y = _year_at(f, mid)
            if y is None or y >= year:
                hi = mid
            else:
                lo = mid
        f.seek(lo)
        if lo != h:
            f.readline()
        while True:
            pos = f.tell()
            ln = f.readline()
            if not ln:
                return size
            if int(ln.split(b",", 1)[0]) >= year:
                return pos


def parse_block(buf: bytes) -> tuple[pl.DataFrame, dict]:
    """Parse a header-less block with the pinned schema; fall back to a lenient parse (and COUNT
    what failed) if a garbage value does not parse as a float."""
    try:
        df = pl.read_csv(io.BytesIO(buf), has_header=False, new_columns=COLS, schema=SCHEMA)
        return df, {}
    except Exception as e:  # noqa: BLE001
        log(f"    strict parse failed ({type(e).__name__}: {str(e)[:200]}); lenient re-parse")
    raw = pl.read_csv(io.BytesIO(buf), has_header=False, new_columns=COLS,
                      schema={c: pl.Utf8 for c in COLS})
    bad = {}
    exprs = []
    for c in COLS:
        exprs.append(pl.col(c).cast(SCHEMA[c], strict=False).alias(c))
    df = raw.select(exprs)
    for c in COLS:
        n = int(df[c].null_count() - raw[c].null_count())
        if n:
            bad[c] = n
            ex = raw.filter(df[c].is_null() & raw[c].is_not_null())[c].head(5).to_list()
            log(f"    column {c}: {n} unparseable values, e.g. {ex}")
    return df, bad


def stage_extract_full(label: str):
    path = FILES[label]
    d = os.path.join(OUT, "full")
    os.makedirs(d, exist_ok=True)
    size = os.path.getsize(path)
    for y in FULL_YEARS[label]:
        t0 = time.time()
        a, b = first_offset(path, y), first_offset(path, y + 1)
        with open(path, "rb") as f:
            f.seek(a)
            buf = f.read(b - a)
        df, bad = parse_block(buf)
        del buf
        yrs = df["Year"].unique().to_list()
        assert yrs == [y], f"{label} block {a}-{b} holds years {yrs}, expected [{y}]"
        df.write_parquet(os.path.join(d, f"{label}_{y}.parquet"), compression="zstd")
        log(f"  {label} {y}: bytes [{a/1e9:.3f},{b/1e9:.3f}) GB of {size/1e9:.1f}; rows {df.height}; "
            f"unparseable {bad}; {time.time()-t0:.0f}s")


def stage_extract_sub(label: str):
    path = FILES[label]
    d = os.path.join(OUT, "sub")
    os.makedirs(d, exist_ok=True)
    out = os.path.join(d, f"{label}_mod{SUBMOD}.parquet")
    t0 = time.time()
    # ignore_errors: a garbage value becomes null instead of killing a 2-hour stream; the nulls are
    # COUNTED below and reported, never silently dropped.
    lf = (pl.scan_csv(path, has_header=True, schema=SCHEMA, ignore_errors=True)
          .filter((pl.col("Cell") % SUBMOD) == 0))
    lf.sink_parquet(out, compression="zstd")
    df = pl.read_parquet(out)
    log(f"  {label}: {df.height} rows, cells {df['Cell'].n_unique()}, years "
        f"{df['Year'].min()}-{df['Year'].max()} ({df['Year'].n_unique()}), {time.time()-t0:.0f}s")
    nulls = {c: int(df[c].null_count()) for c in COLS if df[c].null_count()}
    log(f"  null (unparseable) counts: {nulls}")


# ============================================================ parameters
def cpp_json(path: str) -> dict:
    """Expand a LPJmL .js parameter file with `cpp -P` exactly as LPJmL does (openconfig.c) and
    parse it; logic copied from scripts/build_mort_params_reference.py::cpp_json (last key wins)."""
    proc = subprocess.run(["cpp", "-P", path], capture_output=True, text=True, check=True,
                          stdin=subprocess.DEVNULL)
    body = proc.stdout.strip().rstrip(",")
    body = re.sub(r",(\s*[}\]])", r"\1", body)
    return json.loads("{" + body + "}")


def trait_intervals() -> dict[int, dict[str, tuple[float, float]]]:
    pft = cpp_json(os.path.join(LPJROOT, "par", "pft_lpjmlfit.js"))["pftpar"]
    out = {}
    for i in range(7):
        p = pft[i]
        out[i] = {"SLA": (p["sla"]["low"], p["sla"]["high"]),
                  "Wooddens": (p["wooddens"]["low"], p["wooddens"]["high"]),
                  "D95max": (p["D95max"]["low"], p["D95max"]["high"]),
                  "minwscal": (p["minwscal"]["low"], p["minwscal"]["high"])}
    return out


def load_params() -> dict[int, dict[str, float]]:
    rows = pl.read_csv(PARAMS, comment_prefix="#")
    out = {}
    for r in rows.iter_rows(named=True):
        if int(r["pft_id"]) <= 6:
            out[int(r["pft_id"])] = {k: v for k, v in r.items() if k != "name"}
    return out


def leaf_carbon_sapl(p: dict, sla: np.ndarray) -> np.ndarray:
    kpr = p["kpr"]
    return (p["lai_sapl"] * p["allom1"] * p["wood_sapl"] ** (kpr * 0.5)
            * (4.0 * sla / math.pi / p["k_latosa"]) ** (kpr * 0.5) / sla) ** (2.0 / (2.0 - kpr))


def pmap(P: dict, key: str, types: np.ndarray) -> np.ndarray:
    lut = np.full(16, np.nan)
    for k, v in P.items():
        lut[k] = v[key]
    return lut[types.astype(np.int64)]


def dmap(d: dict, types: np.ndarray) -> np.ndarray:
    lut = np.full(16, np.nan)
    for k, v in d.items():
        lut[k] = v
    return lut[types.astype(np.int64)]


# ============================================================ helpers
def key4(df: pl.DataFrame | pl.LazyFrame):
    """(Cell, Patch, Type, ID) packed into one Int64: Cell<2^14, Patch<2^8, Type<2^4, ID<2^32."""
    return ((((pl.col("Cell").cast(pl.Int64) * 256 + pl.col("Patch").cast(pl.Int64)) * 16
              + pl.col("Type").cast(pl.Int64)) * (1 << 32)) + pl.col("ID").cast(pl.Int64))


def key3():
    return (((pl.col("Cell").cast(pl.Int64) * 256 + pl.col("Patch").cast(pl.Int64)) * (1 << 32))
            + pl.col("ID").cast(pl.Int64))


def load_full(label: str, years: list[int]) -> pl.DataFrame:
    fs = [os.path.join(OUT, "full", f"{label}_{y}.parquet") for y in years]
    df = pl.concat([pl.read_parquet(f) for f in fs])
    return df.with_columns(k4=key4(df), is_tree=(pl.col("Type") <= 6))


def q(x, qs=(0.0, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 1.0)) -> str:
    x = np.asarray(x, dtype=np.float64)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return "(empty)"
    v = np.quantile(x, qs)
    return " ".join(f"q{int(a*100):02d}={b:.4g}" for a, b in zip(qs, v, strict=True))


def r2(a: np.ndarray, b: np.ndarray) -> float:
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 3:
        return float("nan")
    c = np.corrcoef(a[m], b[m])[0, 1]
    return float(c * c)


def ols_r2(X: np.ndarray, y: np.ndarray) -> float:
    m = np.all(np.isfinite(X), axis=1) & np.isfinite(y)
    X, y = X[m], y[m]
    A = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    res = y - A @ beta
    return float(1 - res.var() / y.var())


def pois_sf(k: np.ndarray, lam: np.ndarray) -> np.ndarray:
    from scipy.stats import poisson
    return poisson.sf(k - 1, np.maximum(lam, 1e-12))


def route_2b(D: pl.DataFrame, P: dict) -> pl.DataFrame:
    """Recover bm_inc_counter c = ceil(mort_npp/mort_max) - 1 (explore_hidden_counter.py route 2b)."""
    t = D["Type"].to_numpy()
    wd = D["Wooddens"].to_numpy().astype(np.float64)
    mmax = 10.0 ** (pmap(P, "wdmort_1", t) + pmap(P, "wdmort_2", t) / (wd / 1e6))
    mn = D["mort_npp"].to_numpy().astype(np.float64)
    r = mn / mmax
    c = np.maximum(0, np.ceil(r - 1e-9).astype(np.int64) - 1)
    info = mn < 1.0 - 1e-6
    forb = np.zeros(r.size, dtype=bool)
    for lo, hi in FORBIDDEN[:4]:
        # a small margin for the 6-significant-digit print of mort_npp and Wooddens
        forb |= (r >= lo * (1 + 2e-5)) & (r <= hi * (1 - 2e-5))
    return D.with_columns(mort_max=pl.Series(mmax), r=pl.Series(r), c2b=pl.Series(c),
                          info=pl.Series(info), forb=pl.Series(forb))




# ============================================================ analysis
TCOLS = ["Cell", "Patch", "Type", "ID", "Year", "Height", "Age", "agb", "vegc", "transp", "npp",
         "wscal_mean", "SLA", "Longevity", "Wooddens", "LAI", "fpc_ind", "minwscal", "D95",
         "D95max", "beta_root", "k_root", "mort_npp", "mort_age", "mort_water", "mort_temp",
         "mort", "isdead"]
STATE_COLS = ["Height", "agb", "vegc", "LAI", "fpc_ind", "D95", "npp", "transp", "wscal_mean",
              "mort_npp", "mort_age", "mort_water", "mort_temp", "mort"]
TRAITS6 = ["SLA", "Wooddens", "D95max", "minwscal", "Longevity", "beta_root"]


def pft_json() -> list:
    return cpp_json(os.path.join(LPJROOT, "par", "pft_lpjmlfit.js"))["pftpar"]


def resist_map() -> dict[int, float]:
    pft = pft_json()
    return {i: float(pft[i]["resist"]) for i in range(7)}


def interval_table() -> pl.DataFrame:
    pft = pft_json()
    rows = []
    for i in range(7):
        p = pft[i]
        rows.append({"Type": i,
                     "sla_lo": p["sla"]["low"], "sla_hi": p["sla"]["high"],
                     "wd_lo": p["wooddens"]["low"], "wd_hi": p["wooddens"]["high"],
                     "d95_lo": p["D95max"]["low"], "d95_hi": p["D95max"]["high"],
                     "mw_lo": p["minwscal"]["low"], "mw_hi": p["minwscal"]["high"]})
    return pl.DataFrame(rows).with_columns(pl.col("Type").cast(pl.Int8),
                                           pl.exclude("Type").cast(pl.Float64))


def trees(df: pl.DataFrame) -> pl.DataFrame:
    return df.filter(pl.col("Type") <= 6)


def dup_info(T: pl.DataFrame) -> dict:
    """key uniqueness within one year's tree rows."""
    n = T.height
    k4u = T["k4"].n_unique()
    k3 = T.select(key3().alias("k3"))["k3"]
    k3u = k3.n_unique()
    # (Cell, Patch, Type, ID) + traits
    kt = T.select(pl.struct(["k4", "SLA", "Wooddens"]).alias("s"))["s"].n_unique()
    return dict(rows=n, excess_k4=n - k4u, excess_k3_dropType=n - k3u, excess_k4_SLA_WD=n - kt)


def dup_keys(T: pl.DataFrame) -> pl.Series:
    return (T.group_by("k4").len().filter(pl.col("len") > 1)["k4"])


def out_of_interval(T: pl.DataFrame, IV: pl.DataFrame) -> dict:
    """inheritance-bug signature: traits outside their OWN Type's [low, high]."""
    J = T.select(["Type", "SLA", "Wooddens", "D95max", "minwscal"]).join(IV, on="Type", how="left")
    tol = 1e-5
    res = {}
    for c, lo, hi in [("SLA", "sla_lo", "sla_hi"), ("Wooddens", "wd_lo", "wd_hi"),
                      ("D95max", "d95_lo", "d95_hi"), ("minwscal", "mw_lo", "mw_hi")]:
        v = pl.col(c).cast(pl.Float64)
        m = J.select(((v < pl.col(lo) * (1 - tol)) | (v > pl.col(hi) * (1 + tol))).alias("o"),
                     pl.col("Type"))
        res[c] = float(m["o"].mean())
        res[c + "_by_type"] = {int(t): round(float(x), 6) for t, x in
                               m.group_by("Type").agg(pl.col("o").mean()).sort("Type").iter_rows()}
    return res


def mort_garbage(T: pl.DataFrame, P: dict) -> dict:
    """first-year-of-restart garbage detector: range, sum-consistency, mort_age recomputation."""
    t = T["Type"].to_numpy()
    mcols = ["mort_npp", "mort_age", "mort_water", "mort_temp", "mort"]
    arr = {c: T[c].to_numpy().astype(np.float64) for c in mcols}
    bad_range = np.zeros(T.height, bool)
    for c in mcols:
        bad_range |= ~np.isfinite(arr[c]) | (arr[c] < 0) | (arr[c] > 1 + 1e-6)
    s = np.minimum(1.0, arr["mort_npp"] + arr["mort_age"] + arr["mort_water"] + arr["mort_temp"])
    tolv = 2e-5 * np.maximum(1.0, np.abs(s)) + 2e-6
    bad_sum = (np.abs(arr["mort"] - s) > tolv) & (np.abs(arr["mort"] - 1.0) > 1e-6)
    age_pre = T["Age"].to_numpy().astype(np.float64) - 1.0
    longv = pmap(P, "longevity", t)
    lnf, qq = P[0]["kmortbg_lnf"], P[0]["kmortbg_q"]
    mage = np.minimum(1.0, lnf * (qq + 1.0) / longv * (np.maximum(age_pre, 0) / longv) ** qq)
    bad_age = np.abs(arr["mort_age"] - mage) > (2e-5 * mage + 1e-9)
    return dict(n=int(T.height), bad_range=float(bad_range.mean()),
                bad_sum_consistency=float(bad_sum.mean()), bad_mort_age=float(bad_age.mean()),
                hard_mort1=float((arr["mort"] >= 1 - 1e-6).mean()))


def death_channels(T: pl.DataFrame, R: dict) -> dict:
    """T = all tree rows of year y (isdead 0 and 1).  Decompose isdead against the printed hazard."""
    D = T.with_columns(res=pl.col("Type").cast(pl.Int64).replace_strict(R, return_dtype=pl.Float64),
                       m=pl.col("mort").cast(pl.Float64).clip(0, 1),
                       d=pl.col("isdead").cast(pl.Float64))
    n = D.height
    nd = float(D["d"].sum())
    nm = float(D["m"].sum())
    hard = D.filter(pl.col("m") >= 1 - 1e-6)
    out = dict(n=n, deaths=int(nd), mean_isdead=nd / n, mean_mort=nm / n,
               hazard_share_of_deaths=nm / nd if nd else float("nan"),
               hard_mort1_n=hard.height, hard_mort1_isdead=float(hard["d"].mean()) if hard.height else float("nan"),
               hard_share_of_deaths=float(hard["d"].sum()) / nd if nd else float("nan"),
               fire_floor_expected=float(((1 - D["res"]) * 0.001 * (1 - D["m"])).sum()) / nd if nd else float("nan"))
    # --- bioclimatic signature: a whole (Cell, Type) dies at low hazard
    G = (D.group_by(["Cell", "Type"]).agg(pl.len().alias("n"), pl.col("d").sum().alias("D"),
                                           pl.col("m").sum().alias("M")))
    bio = G.filter((pl.col("n") >= 5) & (pl.col("D") >= 0.95 * pl.col("n")) & (pl.col("M") < 0.5 * pl.col("n")))
    out["bioclim_groups"] = bio.height
    out["bioclim_deaths_share"] = float(bio["D"].sum()) / nd if nd else float("nan")
    out["bioclim_excess_share"] = float((bio["D"] - bio["M"]).sum()) / (nd - nm) if nd > nm else float("nan")
    D2 = D.join(bio.select(["Cell", "Type"]).with_columns(bio=pl.lit(True)), on=["Cell", "Type"], how="left")
    D2 = D2.filter(pl.col("bio").is_null())
    # --- patch clustering (fire: one fire_frac per patch-year, kill prob (1-resist)*f per tree)
    PP = (D2.group_by(["Cell", "Patch"]).agg(
        pl.len().alias("n"), pl.col("d").sum().alias("D"), pl.col("m").sum().alias("M"),
        (pl.col("m") * (1 - pl.col("m"))).sum().alias("V"),
        ((1 - pl.col("res")) * (1 - pl.col("m"))).sum().alias("W")))
    PP = PP.with_columns(z=(pl.col("D") - pl.col("M") - 0.001 * pl.col("W"))
                         / (pl.col("V") + 0.001 * pl.col("W") + 1e-12).sqrt(),
                         f_hat=((pl.col("D") - pl.col("M")) / pl.col("W").clip(1e-9)).clip(0, 1))
    exc_tot = float((PP["D"] - PP["M"]).sum())
    out["excess_nonbio"] = exc_tot
    out["excess_total"] = nd - nm
    for zt in (3, 5):
        S = PP.filter(pl.col("z") > zt)
        out[f"patchyears_z>{zt}"] = S.height
        out[f"patchyears_z>{zt}_frac"] = S.height / PP.height
        out[f"excess_in_z>{zt}_share_of_all_excess"] = float((S["D"] - S["M"]).sum()) / (nd - nm) if nd > nm else float("nan")
        out[f"deaths_in_z>{zt}_share_of_deaths"] = float(S["D"].sum()) / nd if nd else float("nan")
    ev = PP.filter((pl.col("n") >= 3) & (pl.col("D") >= 0.5 * pl.col("n")) & (pl.col("M") < 0.2 * pl.col("n")))
    out["stand_kill_patchyears"] = ev.height
    out["stand_kill_deaths_share"] = float(ev["D"].sum()) / nd if nd else float("nan")
    # f_hat binned excess
    bins = [-0.01, 0.01, 0.05, 0.2, 0.5, 1.01]
    fb = []
    for a, b in zip(bins[:-1], bins[1:], strict=True):
        S = PP.filter((pl.col("f_hat") > a) & (pl.col("f_hat") <= b))
        fb.append(dict(f_lo=a, f_hi=b, patchyears=S.height, deaths=int(S["D"].sum()),
                       excess=round(float((S["D"] - S["M"]).sum()), 1)))
    out["excess_by_fhat"] = fb
    # by type
    bt = (D.group_by("Type").agg(pl.len().alias("n"), pl.col("d").mean().alias("isdead"),
                                  pl.col("m").mean().alias("mort")).sort("Type"))
    out["by_type"] = [dict(Type=int(a), n=int(b), isdead=round(c, 5), mort=round(d, 5))
                      for a, b, c, d in bt.iter_rows()]
    return out


def census(df: pl.DataFrame) -> dict:
    c = df.group_by("Year").agg(pl.col("Cell").n_unique().alias("cells"),
                                pl.col("Cell").filter(pl.col("Type") <= 6).n_unique().alias("tree_cells"))
    return {int(y): (int(a), int(b)) for y, a, b in c.sort("Year").iter_rows()}


def transition(A: pl.DataFrame, B: pl.DataFrame, P: dict, R: dict, IV: pl.DataFrame,
               ncell_universe: int | None = None, prev: pl.DataFrame | None = None) -> dict:
    """one transition y -> y+1 on TREE rows. A, B: all rows (with k4) of years y and y+1."""
    y = int(A["Year"][0])
    TA, TB = trees(A), trees(B)
    out = {"year": y}
    out["identity_A"] = dup_info(TA)
    dA, dB = dup_keys(TA), dup_keys(TB)
    bad = pl.concat([dA, dB]).unique()
    out["dup_keys_excluded"] = int(bad.len())
    TA_ = TA.filter(~pl.col("k4").is_in(bad.implode()))
    TB_ = TB.filter(~pl.col("k4").is_in(bad.implode()))
    # ---- census
    cA = set(A["Cell"].unique().to_list())
    cB = set(B["Cell"].unique().to_list())
    out["cells_A"], out["cells_B"] = len(cA), len(cB)
    out["cells_A_not_B"] = sorted(cA - cB)[:20]
    out["n_cells_A_not_B"] = len(cA - cB)
    tcA = set(TA["Cell"].unique().to_list())
    tcB = set(TB["Cell"].unique().to_list())
    out["tree_cells_A_not_B"] = len(tcA - tcB)
    out["tree_cells_B_not_A"] = len(tcB - tcA)
    # ---- fate of living stems
    Bk = TB_.select(["k4", pl.col("isdead").alias("isdead_B"), pl.col("Age").alias("Age_B"),
                     pl.col("Height").alias("Height_B"), pl.col("agb").alias("agb_B")]
                    + [pl.col(c).alias(c + "_B") for c in TRAITS6])
    L = TA_.filter(pl.col("isdead") == 0).join(Bk, on="k4", how="left")
    nL = L.height
    present = L.filter(pl.col("isdead_B").is_not_null())
    absent = L.filter(pl.col("isdead_B").is_null())
    out["live_A"] = nL
    out["fate_alive_B"] = present.filter(pl.col("isdead_B") == 0).height / nL
    out["fate_flagged_dead_B"] = present.filter(pl.col("isdead_B") == 1).height / nL
    out["fate_absent_B"] = absent.height / nL
    out["absent_n"] = absent.height
    hA = absent["Height"].to_numpy()
    out["absent_height_q"] = q(hA)
    out["absent_frac_H_lt_5.5"] = float((hA < 5.5).mean()) if hA.size else float("nan")
    out["absent_frac_H_lt_6"] = float((hA < 6.0).mean()) if hA.size else float("nan")
    out["absent_frac_H_ge_10"] = float((hA >= 10).mean()) if hA.size else float("nan")
    out["absent_mort_q"] = q(absent["mort"].to_numpy())
    out["absent_n_cells"] = absent["Cell"].n_unique() if absent.height else 0
    # absent in a cell that vanished entirely?
    out["absent_in_missing_cells"] = absent.filter(pl.col("Cell").is_in(list(cA - cB))).height
    # ---- identity across years (matched)
    age_d = (present["Age_B"] - present["Age"]).to_numpy()
    out["matched"] = present.height
    out["age_plus1_frac"] = float((age_d == 1).mean())
    out["age_diff_values"] = {int(k): int(v) for k, v in zip(*np.unique(age_d, return_counts=True), strict=True)} if age_d.size < 1e9 else {}
    trait_eq = {}
    for c in TRAITS6:
        eq = (present[c] == present[c + "_B"]).to_numpy()
        trait_eq[c] = float(eq.mean())
    out["trait_bit_identical"] = trait_eq
    dh = (present["Height_B"] - present["Height"]).to_numpy()
    out["height_decrease_frac"] = float((dh < 0).mean())
    out["height_decrease_q"] = q(dh[dh < 0]) if (dh < 0).any() else "(none)"
    dagb = (present["agb_B"] - present["agb"]).to_numpy()
    out["agb_decrease_frac"] = float((dagb < 0).mean())
    # ---- flagged-dead stems reappear?
    Dd = TA_.filter(pl.col("isdead") == 1).join(Bk.select("k4"), on="k4", how="semi")
    out["dead_A"] = TA_.filter(pl.col("isdead") == 1).height
    out["dead_A_reappear_B"] = Dd.height
    # ---- recruits into the > 5 m population
    Rn = TB_.join(TA.select("k4"), on="k4", how="anti")
    if prev is not None:
        re = Rn.join(trees(prev).select("k4"), on="k4", how="semi").height
        out["recruits_seen_at_y-1"] = re
    out["recruits"] = Rn.height
    out["recruits_isdead"] = float(Rn["isdead"].cast(pl.Float64).mean()) if Rn.height else float("nan")
    out["recruit_height_q"] = q(Rn["Height"].to_numpy())
    out["recruit_age_q"] = q(Rn["Age"].to_numpy())
    out["recruit_type_mix"] = {int(t): int(n) for t, n in Rn.group_by("Type").len().sort("Type").iter_rows()}
    out["live_type_mix_A"] = {int(t): int(n) for t, n in
                              TA.filter(pl.col("isdead") == 0).group_by("Type").len().sort("Type").iter_rows()}
    rp = Rn.group_by(["Cell", "Patch"]).len()
    counts = rp["len"].to_numpy()
    npatch_univ = len(cB) * NPATCH
    zero = npatch_univ - counts.size
    allc = np.concatenate([counts, np.zeros(max(zero, 0), dtype=counts.dtype)])
    out["recruits_per_patchyear_mean"] = float(allc.mean())
    out["recruits_per_patchyear_var"] = float(allc.var())
    out["recruits_per_patchyear_dist"] = {int(k): int(v) for k, v in zip(*np.unique(allc, return_counts=True), strict=True)}
    rc = Rn.group_by("Cell").len()["len"].to_numpy()
    rc = np.concatenate([rc, np.zeros(max(len(cB) - rc.size, 0), dtype=rc.dtype)])
    out["recruits_per_cellyear_q"] = q(rc)
    out["recruits_per_cellyear_zero_frac"] = float((rc == 0).mean())
    # ---- inheritance-bug signature among recruits vs all
    out["out_of_interval_all_trees_A"] = out_of_interval(TA, IV)
    out["out_of_interval_recruits"] = out_of_interval(Rn, IV) if Rn.height else {}
    # ---- death channels + hazard at year y (all tree rows of A)
    out["death_channels_A"] = death_channels(TA, R)
    out["mort_garbage_A"] = mort_garbage(TA, P)
    out["mort_garbage_B"] = mort_garbage(TB, P)
    # ---- hidden counter: recursion gate on matched live stems
    HA = route_2b(TA_.filter(pl.col("isdead") == 0).select(["k4", "Type", "Wooddens", "mort_npp"]), P)
    HB = route_2b(TB_.select(["k4", "Type", "Wooddens", "mort_npp", "isdead"]), P)
    out["counter_A"] = counter_stats(HA)
    H = HA.select(["k4", "c2b", "info"]).join(HB.select(["k4", pl.col("c2b").alias("cB"), pl.col("info").alias("iB")]),
                                             on="k4", how="inner")
    Hi = H.filter(pl.col("info") & pl.col("iB"))
    ok = ((Hi["cB"] == 0) | (Hi["cB"] == Hi["c2b"] + 1)).to_numpy()
    out["counter_recursion_n"] = Hi.height
    out["counter_recursion_ok"] = float(ok.mean()) if ok.size else float("nan")
    bad_ex = Hi.filter(~pl.Series(ok)).head(0)
    del bad_ex
    # c = 5 must be a hard kill in B
    HB5 = HB.filter(pl.col("info") & (pl.col("c2b") >= 5))
    out["counter5_B_n"] = HB5.height
    return out, present, absent, Rn


def counter_stats(H: pl.DataFrame) -> dict:
    n = H.height
    info = H["info"].to_numpy()
    forb = H["forb"].to_numpy()
    c = H["c2b"].to_numpy()
    d = {int(k): int(v) for k, v in zip(*np.unique(c[info], return_counts=True), strict=True)}
    return dict(n=n, informative=float(info.mean()), forbidden_band_rate=float(forb[info].mean()) if info.any() else float("nan"),
                counter_dist_informative=d, counter_ge1=float((c[info] >= 1).mean()) if info.any() else float("nan"))


def growth_persistence(Y0: pl.DataFrame, Y1: pl.DataFrame, Y2: pl.DataFrame) -> dict:
    """surviving stems in 3 consecutive years: R^2 of this year's Delta from last year's."""
    s = ["k4", "Height", "agb", "vegc", "LAI", "fpc_ind"]
    a = trees(Y0).filter(pl.col("isdead") == 0).select(s)
    b = trees(Y1).filter(pl.col("isdead") == 0).select(s)
    c = trees(Y2).select(s + ["isdead"])
    J = a.join(b, on="k4", suffix="_1").join(c, on="k4", suffix="_2")
    out = {"n": J.height}
    for v in ["Height", "agb", "vegc"]:
        d1 = (J[v + "_1"] - J[v]).to_numpy().astype(np.float64)
        d2 = (J[v + "_2"] - J[v + "_1"]).to_numpy().astype(np.float64)
        out[f"R2_d{v}_persist"] = r2(d1, d2)
        # R2 of the copy-null  d2_hat = d1  (not re-fitted)
        out[f"R2_d{v}_copy_null"] = float(1 - np.mean((d2 - d1) ** 2) / np.var(d2))
    # log-log fit dagb2 ~ dagb1 + agb
    return out


def state_vs_flux(present: pl.DataFrame, B: pl.DataFrame) -> dict:
    """lag-1 R^2 of each column on matched living stems."""
    TB = trees(B).select(["k4"] + STATE_COLS)
    J = present.select(["k4"] + STATE_COLS).join(TB, on="k4", suffix="_B")
    out = {}
    for c in STATE_COLS:
        a = J[c].to_numpy().astype(np.float64)
        b = J[c + "_B"].to_numpy().astype(np.float64)
        out[c] = dict(R2_lag1=round(r2(a, b), 5),
                      nondecreasing=round(float((b >= a).mean()), 5),
                      rel_change_median=round(float(np.nanmedian(np.abs(b - a) / np.maximum(np.abs(a), 1e-9))), 5))
    return out


def allometry_determinacy(T: pl.DataFrame) -> dict:
    """is Height a function of (agb, Wooddens, Type)?  OLS in logs per type."""
    out = {}
    L = trees(T).filter((pl.col("isdead") == 0) & (pl.col("agb") > 0) & (pl.col("Height") > 0))
    for t in range(7):
        S = L.filter(pl.col("Type") == t)
        if S.height < 100:
            continue
        S = S.sample(min(S.height, 400000), seed=1)
        y_ = np.log(S["Height"].to_numpy().astype(np.float64))
        X = np.column_stack([np.log(S["agb"].to_numpy().astype(np.float64)),
                             np.log(S["Wooddens"].to_numpy().astype(np.float64)),
                             np.log(S["SLA"].to_numpy().astype(np.float64))])
        X2 = np.column_stack([X, np.log(np.maximum(S["LAI"].to_numpy().astype(np.float64), 1e-6)),
                              np.log(np.maximum(S["fpc_ind"].to_numpy().astype(np.float64), 1e-9))])
        out[t] = dict(n=S.height, R2_logH_on_logagb_wd_sla=round(ols_r2(X, y_), 5),
                      R2_plus_LAI_fpc=round(ols_r2(X2, y_), 5))
    return out


def patch_structure(T: pl.DataFrame, ncells: int) -> dict:
    Tr = trees(T).filter(pl.col("isdead") == 0)
    sp = Tr.group_by(["Cell", "Patch"]).len()["len"].to_numpy()
    zero = ncells * NPATCH - sp.size
    allp = np.concatenate([sp, np.zeros(max(zero, 0), dtype=sp.dtype)])
    G = T.filter(pl.col("Type") > 6)
    out = dict(live_stems_per_patch_q=q(allp), patches_without_live_tree_frac=float((allp == 0).mean()),
               live_stems_per_patch_mean=float(allp.mean()),
               patch_min=int(T["Patch"].min()), patch_max=int(T["Patch"].max()))
    if G.height:
        gp = G.group_by(["Cell", "Patch", "Type"]).len()["len"]
        out["grass_rows"] = G.height
        out["grass_rows_per_cell_patch_type_max"] = int(gp.max())
        out["grass_cell_patch_pairs"] = G.select(["Cell", "Patch"]).unique().height
        out["grass_types"] = {int(t): int(n) for t, n in G.group_by("Type").len().sort("Type").iter_rows()}
        nz = {}
        for c in COLS:
            if c in ("Year", "Type", "Patch", "Cell"):
                continue
            v = G[c].cast(pl.Float64)
            nz[c] = round(float((v != 0).mean()), 4)
        out["grass_nonzero_frac"] = nz
        out["grass_ID_values"] = G["ID"].unique().head(5).to_list()
        # does a patch with trees also carry grass rows?
        tp = Tr.select(["Cell", "Patch"]).unique()
        gpp = G.select(["Cell", "Patch"]).unique()
        out["tree_patches_with_grass_row_frac"] = float(tp.join(gpp, on=["Cell", "Patch"], how="semi").height / max(tp.height, 1))
    return out


def jdump(obj, name):
    def conv(o):
        if isinstance(o, dict):
            return {str(k): conv(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [conv(v) for v in o]
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        return o
    with open(res_path(name), "w") as f:
        json.dump(conv(obj), f, indent=1)
    log(f"  wrote {res_path(name)}")


def stage_analyze_full(labels: list[str]):
    P = load_params()
    R = resist_map()
    IV = interval_table()
    log(f"  resist {R}")
    pairs = [("H1", 1985, "H1", 1986), ("H1", 1986, "H1", 1987), ("H1", 1987, "H1", 1988),
             ("H1", 1988, "H1", 1989), ("H1", 2014, "S44", 2015), ("S44", 2015, "S44", 2016),
             ("S44", 2016, "S44", 2017), ("S100", 2071, "S100", 2072), ("S100", 2072, "S100", 2073),
             ("S100", 2073, "S100", 2074), ("S100", 2074, "S100", 2075)]
    if labels:
        pairs = [p for p in pairs if p[0] in labels]
    cache = {}

    def get(lab, y):
        k = (lab, y)
        if k not in cache:
            cache[k] = load_full(lab, [y])
            for kk in list(cache):
                if kk[1] < y - 2 or kk[0] != lab and kk != k and kk[1] < y - 1:
                    del cache[kk]
        return cache[k]

    res = {}
    for la, ya, lb, yb in pairs:
        t0 = time.time()
        A, B = get(la, ya), get(lb, yb)
        prev = cache.get((la, ya - 1))
        out, present, absent, Rn = transition(A, B, P, R, IV, prev=prev)
        out["state_vs_flux"] = state_vs_flux(present, B)
        if prev is not None:
            out["growth_persistence"] = growth_persistence(prev, A, B)
        if ya in (1985, 2015, 2071):
            out["patch_structure_A"] = patch_structure(A, A["Cell"].n_unique())
            out["allometry_A"] = allometry_determinacy(A)
        res[f"{la}{ya}->{lb}{yb}"] = out
        log(f"  {la} {ya}->{lb} {yb}: live {out['live_A']} alive {out['fate_alive_B']:.4f} "
            f"flag {out['fate_flagged_dead_B']:.4f} absent {out['fate_absent_B']:.6f} "
            f"recruits {out['recruits']} dupA {out['identity_A']} hazard_share "
            f"{out['death_channels_A']['hazard_share_of_deaths']:.4f} recursion {out['counter_recursion_ok']:.6f} "
            f"{time.time()-t0:.0f}s")
        jdump(res, f"full_transitions_{'_'.join(labels) or 'all'}.json")


# ---------------------------------------------------------------- sub-series analyses
def inheritance_signature(TA: pl.DataFrame, Rn: pl.DataFrame, IV: pl.DataFrame, rng) -> dict:
    """recruits' nearest-neighbour trait distance to the cell's same-type standing trees at y,
    vs (a) a uniform draw from the type's interval, (b) a random standing tree of the same type
    from ANOTHER cell (a same-PFT, wrong-community draw)."""
    from scipy.spatial import cKDTree
    cols = ["SLA", "Wooddens", "D95max", "minwscal"]
    IVd = {int(r["Type"]): r for r in IV.iter_rows(named=True)}
    lohi = {"SLA": ("sla_lo", "sla_hi"), "Wooddens": ("wd_lo", "wd_hi"), "D95max": ("d95_lo", "d95_hi"),
            "minwscal": ("mw_lo", "mw_hi")}
    St = TA.filter((pl.col("isdead") == 0))
    res_rows = []
    for (cell, t), g in Rn.group_by(["Cell", "Type"]):
        t = int(t)
        s = St.filter((pl.col("Cell") == cell) & (pl.col("Type") == t))
        if s.height < 20 or g.height < 1:
            continue
        iv = IVd[t]
        w = np.array([iv[lohi[c][1]] - iv[lohi[c][0]] for c in cols])
        lo = np.array([iv[lohi[c][0]] for c in cols])
        Xs = s.select(cols).to_numpy().astype(np.float64) / w
        Xr = g.select(cols).to_numpy().astype(np.float64) / w
        tree = cKDTree(Xs)
        dr, _ = tree.query(Xr, k=1)
        U = (lo + rng.random((g.height, 4)) * w) / w
        du, _ = tree.query(U, k=1)
        other = St.filter((pl.col("Cell") != cell) & (pl.col("Type") == t))
        if other.height > 0:
            idx = rng.integers(0, other.height, g.height)
            Xo = other[idx].select(cols).to_numpy().astype(np.float64) / w
            do, _ = tree.query(Xo, k=1)
        else:
            do = np.full(g.height, np.nan)
        for a, b, c_ in zip(dr, du, do, strict=True):
            res_rows.append((int(cell), t, s.height, a, b, c_))
    if not res_rows:
        return {}
    arr = np.array([r[3:] for r in res_rows])
    typ = np.array([r[1] for r in res_rows])
    out = dict(n_recruits=len(res_rows), n_groups=len({(r[0], r[1]) for r in res_rows}),
               median_nn_recruit=float(np.nanmedian(arr[:, 0])),
               median_nn_uniform=float(np.nanmedian(arr[:, 1])),
               median_nn_othercell=float(np.nanmedian(arr[:, 2])),
               frac_recruit_closer_than_uniform=float(np.mean(arr[:, 0] < arr[:, 1])),
               frac_recruit_closer_than_othercell=float(np.nanmean(arr[:, 0] < arr[:, 2])))
    bt = {}
    for t in np.unique(typ):
        m = typ == t
        bt[int(t)] = dict(n=int(m.sum()), nn_rec=round(float(np.median(arr[m, 0])), 5),
                          nn_unif=round(float(np.median(arr[m, 1])), 5),
                          nn_other=round(float(np.nanmedian(arr[m, 2])), 5))
    out["by_type"] = bt
    return out


def stage_analyze_sub(label: str):
    P = load_params()
    R = resist_map()
    IV = interval_table()
    rng = np.random.default_rng(20260930)
    dev = os.environ.get("ANAT_DEV")  # members stage: a converted ind_dev parquet (same Cell%10 subset)
    if dev:
        path = os.path.join(DEVDIR, f"{label}.parquet")
        lf = pl.scan_parquet(path).with_columns(pl.col("ID").cast(pl.Int64),
                                                pl.col("Age").round(0).cast(pl.Int32))
    else:
        path = os.path.join(OUT, "sub", f"{label.split('_')[0]}_mod{SUBMOD}.parquet")
        lf = pl.scan_parquet(path)
    smoke = int(os.environ.get("ANAT_SMOKE", "0"))
    if smoke:
        lf = lf.filter((pl.col("Cell") % smoke) == 0, pl.col("Year") < 2015 + 6 if label == "S44" else pl.lit(True))
        label = label + f"_smoke{smoke}"
    years = sorted(lf.select(pl.col("Year").unique()).collect()["Year"].to_list())
    log(f"  {label}: years {years[0]}-{years[-1]} ({len(years)})")
    cen = lf.group_by(["Year"]).agg(pl.col("Cell").n_unique().alias("cells"),
                                    pl.len().alias("rows")).collect().sort("Year")
    exp_cells = sorted(c for c in range(0, 9067, SUBMOD) if not smoke or c % smoke == 0)
    cy = lf.select(["Year", "Cell"]).unique().collect()
    holes = []
    for y in years:
        have = set(cy.filter(pl.col("Year") == y)["Cell"].to_list())
        holes.append((y, sorted(set(exp_cells) - have)))
    out = {"label": label, "years": years, "census": {int(a): (int(b), int(c)) for a, b, c in cen.iter_rows()},
           "expected_cells": len(exp_cells),
           "census_holes": {int(y): h for y, h in holes if h}}
    log(f"  census holes (cell ids missing per year; rock cells 31/32 are not in Cell%10): "
        f"{ {y: len(h) for y, h in holes if h} } of {len(exp_cells)} expected")
    # ---- patch-level series for lag analysis
    T = (lf.filter(pl.col("Type") <= 6)
         .with_columns(k4=key4(None))
         .collect())
    log(f"  tree rows {T.height}")
    trans = []
    per_patch = []
    prev = None
    byY = {y: T.filter(pl.col("Year") == y) for y in years}
    for i, y in enumerate(years[:-1]):
        A, B = byY[y], byY[years[i + 1]]
        o, present, absent, Rn = transition(A, B, P, R, IV, prev=prev)
        o["state_vs_flux"] = state_vs_flux(present, B)
        if prev is not None:
            o["growth_persistence"] = growth_persistence(prev, A, B)
        if i in (0, len(years) // 2):
            o["inheritance"] = inheritance_signature(A, Rn, IV, rng)
            log(f"    inheritance {y}: {json.dumps({k: v for k, v in o['inheritance'].items() if k != 'by_type'})}")
        trans.append(o)
        # per-patch series: recruits at y+1, deaths at y, live fpc sum and n at y
        pa = A.group_by(["Cell", "Patch"]).agg(
            (pl.col("fpc_ind") * (pl.col("isdead") == 0)).sum().alias("fpc_live"),
            (pl.col("isdead") == 0).sum().alias("n_live"),
            pl.col("isdead").cast(pl.Int32).sum().alias("deaths"),
            (pl.col("fpc_ind") * (pl.col("isdead") == 1)).sum().alias("fpc_dead"))
        rp = Rn.group_by(["Cell", "Patch"]).len().rename({"len": "recruits_next"})
        pa = pa.join(rp, on=["Cell", "Patch"], how="full", coalesce=True).with_columns(Year=pl.lit(y).cast(pl.Int16))
        per_patch.append(pa)
        log(f"    {y}: live {o['live_A']} alive {o['fate_alive_B']:.4f} flag {o['fate_flagged_dead_B']:.4f} "
            f"absent {o['fate_absent_B']:.6f} rec {o['recruits']} hz {o['death_channels_A']['hazard_share_of_deaths']:.4f} "
            f"garbA {o['mort_garbage_A']['bad_sum_consistency']:.4g}/{o['mort_garbage_A']['bad_mort_age']:.4g} "
            f"rec_ok {o['counter_recursion_ok']:.6f}")
        prev = A
        jdump({**out, "transitions": trans}, f"sub_{label}.json")
    # ---- lag analysis on the patch series
    PS = pl.concat(per_patch, how="diagonal_relaxed").fill_null(0)
    # complete (cell, patch, year) universe
    cells = sorted(T["Cell"].unique().to_list())
    U = (pl.DataFrame({"Cell": cells}).cast({"Cell": pl.Int16})
         .join(pl.DataFrame({"Patch": list(range(NPATCH))}).cast({"Patch": pl.Int16}), how="cross")
         .join(pl.DataFrame({"Year": years[:-1]}).cast({"Year": pl.Int16}), how="cross"))
    PS = U.join(PS, on=["Cell", "Patch", "Year"], how="left").fill_null(0).sort(["Cell", "Patch", "Year"])
    PS.write_parquet(res_path(f"patch_series_{label}.parquet"))
    lag = {}
    for k in [0, 1, 2, 3, 5, 8, 10, 12, 15, 20]:
        S = PS.with_columns(d_lag=pl.col("deaths").shift(k).over(["Cell", "Patch"]),
                            fd_lag=pl.col("fpc_dead").shift(k).over(["Cell", "Patch"])).drop_nulls("d_lag")
        if S.height < 1000:
            continue
        rr = S["recruits_next"].to_numpy().astype(np.float64)
        lag[k] = dict(n=S.height, corr_recruits_deaths=float(np.corrcoef(rr, S["d_lag"].to_numpy().astype(np.float64))[0, 1]),
                      corr_recruits_fpcdead=float(np.corrcoef(rr, S["fd_lag"].to_numpy().astype(np.float64))[0, 1]))
    rr = PS["recruits_next"].to_numpy().astype(np.float64)
    fpc = PS["fpc_live"].to_numpy().astype(np.float64)
    nl = PS["n_live"].to_numpy().astype(np.float64)
    fb = []
    edges = [-1e-9, 0.0, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 100]
    for a, b in zip(edges[:-1], edges[1:], strict=True):
        m = (fpc > a) & (fpc <= b)
        if m.sum():
            fb.append(dict(fpc_lo=a, fpc_hi=b, patchyears=int(m.sum()), recruits_mean=float(rr[m].mean())))
    # within-cell (demeaned) correlation, to remove the cell-level productivity confound
    D = PS.with_columns(rd=pl.col("recruits_next") - pl.col("recruits_next").mean().over(["Cell", "Year"]),
                        fd=pl.col("fpc_live") - pl.col("fpc_live").mean().over(["Cell", "Year"]))
    within = float(np.corrcoef(D["rd"].to_numpy(), D["fd"].to_numpy())[0, 1])
    # event study: patches losing >= 50 % of live fpc in one year (fpc_dead >= 0.5*(fpc_live+fpc_dead)) with fpc>0.3
    ev = PS.with_columns(tot=pl.col("fpc_live") + pl.col("fpc_dead"))
    ev = ev.with_columns(event=((pl.col("fpc_dead") >= 0.5 * pl.col("tot")) & (pl.col("tot") > 0.3)))
    E = ev.filter(pl.col("event")).select(["Cell", "Patch", pl.col("Year").alias("y0")])
    es = {}
    if E.height:
        EJ = E.join(PS.select(["Cell", "Patch", "Year", "recruits_next"]), on=["Cell", "Patch"])
        EJ = EJ.with_columns(dt=(pl.col("Year").cast(pl.Int32) - pl.col("y0").cast(pl.Int32)))
        g = EJ.group_by("dt").agg(pl.col("recruits_next").mean(), pl.len()).sort("dt")
        es = {int(a): (round(float(b), 4), int(c)) for a, b, c in g.iter_rows()}
    base = float(rr.mean())
    out["patch_lag"] = dict(lag_corr=lag, recruits_by_fpc_live=fb, within_cellyear_corr_recruits_fpc=within,
                            corr_recruits_nlive=float(np.corrcoef(rr, nl)[0, 1]),
                            corr_recruits_fpc=float(np.corrcoef(rr, fpc)[0, 1]),
                            event_n=E.height, event_study_recruits_next_by_dt=es, base_recruits_next=base)
    log(f"  lag corr {lag}")
    log(f"  event study (dt: mean recruits in next year, n) {es}; base {base:.4f}")
    # ---- whole-series key histories: ID reuse, dead-then-seen, gaps
    K = T.group_by("k4").agg(pl.len().alias("n"), pl.col("Year").n_unique().alias("ny"),
                             pl.col("Year").min().alias("ymin"), pl.col("Year").max().alias("ymax"),
                             pl.col("Year").filter(pl.col("isdead") == 1).min().alias("ydead"),
                             pl.col("isdead").cast(pl.Int32).sum().alias("ndead"),
                             pl.col("SLA").n_unique().alias("nsla"))
    assert K["k4"].n_unique() == K.height
    kh = dict(keys=K.height, keys_rows_gt_years=int((K["n"] > K["ny"]).sum()),
              keys_multi_dead=int((K["ndead"] > 1).sum()),
              keys_seen_after_dead=int(K.filter(pl.col("ydead").is_not_null() & (pl.col("ymax") > pl.col("ydead"))).height),
              keys_with_gap=int(K.filter((pl.col("ymax") - pl.col("ymin") + 1) > pl.col("ny")).height),
              keys_multi_SLA=int((K["nsla"] > 1).sum()))
    G = K.filter((pl.col("ymax") - pl.col("ymin") + 1) > pl.col("ny"))
    if G.height:
        GJ = T.join(G.select("k4"), on="k4", how="semi").sort(["k4", "Year"])
        GJ = GJ.with_columns(gap=(pl.col("Year").diff().over("k4")),
                             hprev=pl.col("Height").shift(1).over("k4"),
                             slaprev=pl.col("SLA").shift(1).over("k4"))
        GG = GJ.filter(pl.col("gap") > 1)
        kh["gap_len_dist"] = {int(a): int(b) for a, b in GG.group_by("gap").len().sort("gap").iter_rows()}
        kh["gap_height_before_q"] = q(GG["hprev"].to_numpy())
        kh["gap_same_SLA_frac"] = float((GG["SLA"] == GG["slaprev"]).mean())
    out["key_histories"] = kh
    log(f"  key histories {kh}")
    jdump({**out, "transitions": trans}, f"sub_{label}.json")


# ---------------------------------------------------------------- extras (round 2)
def fire_null(TA: pl.DataFrame, R: dict, rng, nsim: int = 5) -> dict:
    """Patch-level death clustering: observed vs a simulated null in which every tree dies
    independently with its printed hazard plus the fire-probability FLOOR 0.001*(1-resist)
    (fire_prob.c returns >= 0.001; fire_tree_ind.c kills with prob (1-resist)*fire_frac)."""
    D = TA.select(["Cell", "Patch", "Type", "isdead", "mort"]).with_columns(
        res=pl.col("Type").cast(pl.Int64).replace_strict(R, return_dtype=pl.Float64),
        m=pl.col("mort").cast(pl.Float64).clip(0, 1))
    m = D["m"].to_numpy()
    p = m + (1 - m) * (1 - D["res"].to_numpy()) * 0.001
    grp = D.select((pl.col("Cell").cast(pl.Int64) * 256 + pl.col("Patch").cast(pl.Int64)).alias("g"))["g"].to_numpy()
    ug, inv = np.unique(grp, return_inverse=True)
    n = np.bincount(inv)
    dobs = np.bincount(inv, weights=D["isdead"].to_numpy().astype(np.float64))
    out = {"patchyears": int(ug.size), "deaths_obs": int(dobs.sum()), "deaths_null_expected": float(p.sum())}
    ks = [1, 2, 3, 4, 5, 6, 8, 10]
    tail_obs = {k: int((dobs >= k).sum()) for k in ks}
    half_obs = int(((dobs >= 0.5 * n) & (n >= 3)).sum())
    half_dobs = float(dobs[(dobs >= 0.5 * n) & (n >= 3)].sum())
    sims = []
    for _ in range(nsim):
        ds = np.bincount(inv, weights=(rng.random(p.size) < p).astype(np.float64))
        sims.append(({k: int((ds >= k).sum()) for k in ks}, int(((ds >= 0.5 * n) & (n >= 3)).sum()),
                     float(ds[(ds >= 0.5 * n) & (n >= 3)].sum()), float(ds.var()), float(ds.sum())))
    out["tail_obs"] = tail_obs
    out["tail_null_mean"] = {k: float(np.mean([s[0][k] for s in sims])) for k in ks}
    out["halfpatch_obs"] = half_obs
    out["halfpatch_null_mean"] = float(np.mean([s[1] for s in sims]))
    out["halfpatch_deaths_obs"] = half_dobs
    out["halfpatch_deaths_null_mean"] = float(np.mean([s[2] for s in sims]))
    out["var_patch_deaths_obs"] = float(dobs.var())
    out["var_patch_deaths_null_mean"] = float(np.mean([s[3] for s in sims]))
    out["deaths_null_sim_mean"] = float(np.mean([s[4] for s in sims]))
    return out


def trait_locality(Tsub: pl.DataFrame, years: list[int], IV: pl.DataFrame, rng) -> dict:
    """Do recruits' trait MEANS track their own cell's standing trees (local inheritance) or only
    the PFT-wide distribution?  Per (Cell, Type): standing means at the first year, recruit means
    pooled over the following transitions.  Slope of recruit mean on standing mean across cells
    within a type, vs a null that shuffles the cell labels of the recruit groups within type."""
    y0 = years[0]
    cols = ["SLA", "Wooddens", "D95max", "minwscal", "Longevity"]
    S0 = Tsub.filter((pl.col("Year") == y0) & (pl.col("isdead") == 0))
    # recruits: key first seen after y0 (and not in y0)
    first = Tsub.group_by("k4").agg(pl.col("Year").min().alias("y1"))
    rec_keys = first.filter(pl.col("y1") > y0)
    Rr = Tsub.join(rec_keys, on="k4").filter(pl.col("Year") == pl.col("y1"))
    top = S0.with_columns(rk=pl.col("agb").rank(descending=True).over(["Cell", "Type"]),
                          nn=pl.len().over(["Cell", "Type"])).filter(pl.col("rk") <= (0.1 * pl.col("nn")).ceil())
    agg = lambda df, nm: df.group_by(["Cell", "Type"]).agg([pl.len().alias("n_" + nm)] + [pl.col(c).cast(pl.Float64).mean().alias(c + "_" + nm) for c in cols])  # noqa: E731
    G = agg(S0, "st").join(agg(Rr, "rec"), on=["Cell", "Type"]).join(agg(top, "top"), on=["Cell", "Type"])
    G = G.filter((pl.col("n_st") >= 30) & (pl.col("n_rec") >= 10))
    out = {"groups": G.height, "recruits": int(G["n_rec"].sum())}
    res = {}
    for c in cols:
        per = {}
        for t in sorted(G["Type"].unique().to_list()):
            g = G.filter(pl.col("Type") == t)
            if g.height < 20:
                continue
            x = g[c + "_st"].to_numpy()
            xt = g[c + "_top"].to_numpy()
            y = g[c + "_rec"].to_numpy()
            xc, yc, xtc = x - x.mean(), y - y.mean(), xt - xt.mean()
            b = float((xc * yc).sum() / (xc * xc).sum())
            bt = float((xtc * yc).sum() / (xtc * xtc).sum())
            nulls = []
            for _ in range(200):
                yp = rng.permutation(yc)
                nulls.append(float((xc * yp).sum() / (xc * xc).sum()))
            per[int(t)] = dict(groups=g.height, slope=round(b, 4), slope_on_top10pct=round(bt, 4),
                               null_slope_sd=round(float(np.std(nulls)), 4),
                               r=round(float(np.corrcoef(x, y)[0, 1]), 4),
                               sd_between_cells_standing=float(x.std()), sd_between_cells_recruit=float(y.std()))
        res[c] = per
    out["by_trait_type"] = res
    return out


def growth_signflip(Tsub: pl.DataFrame, years: list[int]) -> list:
    """per year: fraction of surviving stems whose Delta-agb changes sign between consecutive years,
    median |Delta agb|/agb, fraction Delta agb < 0, and agreement of (counter>=1) with printed Delta-agb<0."""
    # keys carried by >1 row in some year (ID reuse, see key_histories) would pair two different
    # trees; they are dropped whole.  (The first growth_persistence numbers of analyze_sub/full were
    # corrupted exactly this way in the late windows, where such keys become frequent.)
    dupk = Tsub.group_by(["k4", "Year"]).len().filter(pl.col("len") > 1)["k4"].unique()
    Tsub = Tsub.filter(~pl.col("k4").is_in(dupk.implode()))
    X = (Tsub.filter(pl.col("isdead") == 0).select(["k4", "Year", "agb", "vegc", "Height"]).sort(["k4", "Year"])
         .with_columns(d=pl.col("agb").cast(pl.Float64).diff().over("k4"),
                       dy=pl.col("Year").cast(pl.Int32).diff().over("k4"),
                       dv=pl.col("vegc").cast(pl.Float64).diff().over("k4"),
                       dh=pl.col("Height").cast(pl.Float64).diff().over("k4"))
         .with_columns(dprev=pl.col("d").shift(1).over("k4"), dyprev=pl.col("dy").shift(1).over("k4"),
                       dhprev=pl.col("dh").shift(1).over("k4")))
    rows = []
    for y in years[2:]:
        s = X.filter((pl.col("Year") == y) & (pl.col("dy") == 1) & (pl.col("dyprev") == 1))
        d, dp = s["d"].to_numpy(), s["dprev"].to_numpy()
        a = s["agb"].to_numpy().astype(np.float64)
        rows.append(dict(year=int(y), n=s.height, signflip=round(float((np.sign(d) != np.sign(dp)).mean()), 4),
                         neg=round(float((d < 0).mean()), 4),
                         med_rel=round(float(np.median(np.abs(d) / np.maximum(a, 1e-9))), 5),
                         corr=round(float(np.corrcoef(d, dp)[0, 1]), 4),
                         sd_ratio=round(float(d.std() / dp.std()), 4),
                         R2_dagb_persist=round(r2(dp, d), 4),
                         R2_dagb_copy_null=round(float(1 - np.mean((d - dp) ** 2) / np.var(d)), 4),
                         R2_dH_persist=round(r2(s["dhprev"].to_numpy(), s["dh"].to_numpy()), 4),
                         n_dup_keys_dropped=int(dupk.len())))
    return rows


def stage_extras(label: str):
    R = resist_map()
    IV = interval_table()
    rng = np.random.default_rng(7)
    path = os.path.join(OUT, "sub", f"{label}_mod{SUBMOD}.parquet")
    T = pl.scan_parquet(path).filter(pl.col("Type") <= 6).with_columns(k4=key4(None)).collect()
    years = sorted(T["Year"].unique().to_list())
    out = {"label": label}
    if os.environ.get("ANAT_ONLY") == "growth":
        out["growth_signflip"] = growth_signflip(T, years)
        for r in out["growth_signflip"]:
            log(f"  growth {r}")
        jdump(out, f"extras_growth_{label}.json")
        return
    fn = []
    for y in years:
        o = fire_null(T.filter(pl.col("Year") == y), R, rng)
        o["year"] = int(y)
        fn.append(o)
        log(f"  fire-null {y}: deaths {o['deaths_obs']} vs null {o['deaths_null_sim_mean']:.0f}; "
            f"var obs/null {o['var_patch_deaths_obs']:.4f}/{o['var_patch_deaths_null_mean']:.4f}; "
            f"half-patch obs/null {o['halfpatch_obs']}/{o['halfpatch_null_mean']:.1f}; "
            f"tail>=5 obs/null {o['tail_obs'][5]}/{o['tail_null_mean'][5]:.1f}")
    out["fire_null"] = fn
    jdump(out, f"extras_{label}.json")
    out["trait_locality"] = trait_locality(T.filter(pl.col("Year") <= years[0] + 10), years[:11], IV, rng)
    log(f"  trait locality: {json.dumps(out['trait_locality'])[:3000]}")
    jdump(out, f"extras_{label}.json")
    out["growth_signflip"] = growth_signflip(T, years)
    for r in out["growth_signflip"]:
        log(f"  growth {r}")
    jdump(out, f"extras_{label}.json")


# ============================================================ cross-member summary
def stage_summarize_members():
    """flatten results/members/sub_<member>.json into one row per member-window (30-yr aggregates)."""
    d = os.path.join(OUT, "results", "members")
    rows = []
    for fn in sorted(os.listdir(d)):
        if not (fn.startswith("sub_") and fn.endswith(".json")):
            continue
        J = json.load(open(os.path.join(d, fn)))
        tr = J.get("transitions", [])
        if not tr:
            continue
        mem = fn[4:-5]
        def g(k, tr=tr):
            return np.array([t[k] for t in tr], dtype=float)
        live = g("live_A")
        dc = [t["death_channels_A"] for t in tr]
        deaths = np.array([x["deaths"] for x in dc], float)
        mortsum = np.array([x["mean_mort"] * x["n"] for x in dc], float)
        hard = np.array([x["hard_share_of_deaths"] * x["deaths"] for x in dc], float)
        fire = np.array([x["fire_floor_expected"] * x["deaths"] for x in dc], float)
        cn = g("counter_recursion_n")
        cok = g("counter_recursion_ok")
        idA = [t["identity_A"] for t in tr]
        ab_n = g("absent_n")
        ab_h = np.array([t["absent_frac_H_lt_5.5"] if t["absent_n"] else np.nan for t in tr], float)
        mg = [t["mort_garbage_A"] for t in tr]
        PL = J.get("patch_lag", {})
        es = PL.get("event_study_recruits_next_by_dt", {})
        rows.append(dict(
            member=mem, years=f"{J['years'][0]}-{J['years'][-1]}", n_years=len(J["years"]),
            census_hole_years=len(J.get("census_holes", {})),
            live_stem_years=int(live.sum()),
            fate_alive=float((g("fate_alive_B") * live).sum() / live.sum()),
            fate_flagged=float((g("fate_flagged_dead_B") * live).sum() / live.sum()),
            fate_absent=float(ab_n.sum() / live.sum()),
            absent_H_lt_5p5=float(np.nansum(ab_h * ab_n) / ab_n[~np.isnan(ab_h)].sum()) if ab_n.sum() else float("nan"),
            absent_H_ge_10_n=int(sum(round(t["absent_frac_H_ge_10"] * t["absent_n"]) for t in tr if t["absent_n"])),
            dead_reappear=int(g("dead_A_reappear_B").sum()),
            age_plus1_min=float(g("age_plus1_frac").min()),
            trait_identical_min=float(min(min(t["trait_bit_identical"].values()) for t in tr)),
            excess_k4_per_yr=float(np.mean([x["excess_k4"] for x in idA])),
            excess_k4_max=int(max(x["excess_k4"] for x in idA)),
            excess_k4_SLA_WD_max=int(max(x["excess_k4_SLA_WD"] for x in idA)),
            excess_dropType_per_yr=float(np.mean([x["excess_k3_dropType"] for x in idA])),
            mean_isdead=float(deaths.sum() / sum(x["n"] for x in dc)),
            hazard_share=float(mortsum.sum() / deaths.sum()),
            hazard_share_yr_min=float(min(x["hazard_share_of_deaths"] for x in dc)),
            hazard_share_yr_max=float(max(x["hazard_share_of_deaths"] for x in dc)),
            hard_kill_share=float(hard.sum() / deaths.sum()),
            fire_floor_share=float(fire.sum() / deaths.sum()),
            residual_share=float(1 - mortsum.sum() / deaths.sum() - fire.sum() / deaths.sum()),
            bioclim_groups=int(sum(x["bioclim_groups"] for x in dc)),
            mort_garbage_first_year=float(max(mg[0]["bad_range"], mg[0]["bad_sum_consistency"], mg[0]["bad_mort_age"])),
            mort_garbage_any_year=float(max(max(x["bad_range"], x["bad_sum_consistency"], x["bad_mort_age"]) for x in mg)),
            counter_recursion_viol=int(round(((1 - cok) * cn).sum())), counter_recursion_n=int(cn.sum()),
            counter_forbidden_max=float(max(t["counter_A"]["forbidden_band_rate"] for t in tr)),
            counter_informative_min=float(min(t["counter_A"]["informative"] for t in tr)),
            counter_ge1_mean=float(np.mean([t["counter_A"]["counter_ge1"] for t in tr])),
            recruits_per_yr_frac_live=float(g("recruits").sum() / live.sum()),
            recruits_patchyear_mean=float(g("recruits_per_patchyear_mean").mean()),
            recruits_patchyear_vm=float(np.mean(g("recruits_per_patchyear_var") / g("recruits_per_patchyear_mean"))),
            recruits_cellyear_zero_frac_max=float(g("recruits_per_cellyear_zero_frac").max()),
            recruits_isdead=float(np.nanmean(g("recruits_isdead"))),
            within_cellyear_corr_recruits_fpc=PL.get("within_cellyear_corr_recruits_fpc", float("nan")),
            event_n=PL.get("event_n", 0),
            event_rec_dtm1=(es.get("-1") or [np.nan])[0], event_rec_dt0=(es.get("0") or [np.nan])[0],
            event_rec_dt10=(es.get("10") or [np.nan])[0], event_rec_dt20=(es.get("20") or [np.nan])[0],
            keys_seen_after_dead=J.get("key_histories", {}).get("keys_seen_after_dead"),
            keys_multi_SLA=J.get("key_histories", {}).get("keys_multi_SLA"),
            wd_out_of_interval=float(np.mean([t["out_of_interval_all_trees_A"]["Wooddens"] for t in tr])),
            d95_out_of_interval=float(np.mean([t["out_of_interval_all_trees_A"]["D95max"] for t in tr])),
            sla_out_of_interval=float(np.mean([t["out_of_interval_all_trees_A"]["SLA"] for t in tr])),
        ))
    S = pl.DataFrame(rows)
    S.write_csv(os.path.join(d, "members_summary.csv"))
    with pl.Config(tbl_rows=60, tbl_cols=60, tbl_width_chars=400):
        log(S)
    log(f"  wrote {os.path.join(d, 'members_summary.csv')} ({S.height} member-windows)")


# ============================================================ fire vs residual deaths (year to year)
GF_FILE = {"h1985": "globalflux_.csv", "w2015": "globalflux_2044.csv", "w2071": "globalflux_2100.csv",
           "w3071": "globalflux_3100.csv"}


def stage_fire_check():
    """Does the cell-total fire carbon flux (globalflux `fire`, whole Germany) explain the per-year
    death residual the printed hazard + the 0.001 fire floor leave (subsample Cell%10==0)?
    proxy burnt fraction f_eff = fire / (LitC + VegC); at the floor everywhere it is ~0.001 x a pool share."""
    d = os.path.join(OUT, "results", "members")
    rows = []
    for fn in sorted(os.listdir(d)):
        if not (fn.startswith("sub_") and fn.endswith(".json")):
            continue
        mem = fn[4:-5]
        gcm, scen, seed, win = mem.rsplit("_", 3)
        gf = os.path.join(ROOT, gcm, scen, f"random_seed_{seed[1:]}", "output", GF_FILE[win])
        G = pl.read_csv(gf, skip_rows_after_header=1)
        G = G.with_columns(pl.col("Year").cast(pl.Int64)).select(["Year", "fire", "LitC", "VegC", "NPP"])
        J = json.load(open(os.path.join(d, fn)))
        for t in J.get("transitions", []):
            x = t["death_channels_A"]
            n = x["n"]
            rows.append(dict(member=mem, gcm=gcm, scen=scen, seed=seed, win=win, Year=int(t["year"]),
                             n=n, death_rate=x["deaths"] / n, hazard_rate=x["mean_mort"],
                             floor_rate=x["fire_floor_expected"] * x["deaths"] / n,
                             resid_rate=(x["deaths"] - x["mean_mort"] * n - x["fire_floor_expected"] * x["deaths"]) / n,
                             hard_rate=x["hard_share_of_deaths"] * x["deaths"] / n))
        del J
        if rows and rows[-1]["member"] == mem:
            pass
        GJ = G
        for r in rows:
            if r["member"] == mem:
                g = GJ.filter(pl.col("Year") == r["Year"])
                if g.height:
                    r["fire"], r["LitC"], r["VegC"], r["NPP"] = (float(g[c][0]) for c in ["fire", "LitC", "VegC", "NPP"])
    F = pl.DataFrame(rows).with_columns(f_eff=pl.col("fire") / (pl.col("LitC") + pl.col("VegC")))
    F.write_csv(os.path.join(d, "fire_vs_residual_by_year.csv"))
    out = {}
    for grp, S in [("all", F)] + [(m, F.filter(pl.col("member") == m)) for m in F["member"].unique().sort().to_list()]:
        S = S.drop_nulls("fire")
        if S.height < 3:
            continue
        a, b = S["f_eff"].to_numpy(), S["resid_rate"].to_numpy()
        h = S["hazard_rate"].to_numpy()
        slope, icpt = np.polyfit(a, b, 1)
        out[grp] = dict(n_years=S.height, corr_resid_feff=float(np.corrcoef(a, b)[0, 1]),
                        slope=float(slope), intercept=float(icpt),
                        corr_hazard_feff=float(np.corrcoef(a, h)[0, 1]),
                        feff_min=float(a.min()), feff_med=float(np.median(a)), feff_max=float(a.max()),
                        resid_rate_mean=float(b.mean()), resid_rate_at_min_feff=float(b[np.argmin(a)]))
    jdump(out, "fire_vs_residual.json")
    log(json.dumps(out.get("all"), indent=1))
    for k, v in out.items():
        log(f"  {k:40s} n={v['n_years']:3d} corr(resid,f_eff)={v['corr_resid_feff']:+.3f} slope={v['slope']:.3f} "
            f"icpt={v['intercept']:+.5f} f_eff {v['feff_min']:.5f}/{v['feff_med']:.5f}/{v['feff_max']:.5f} "
            f"resid {v['resid_rate_mean']:.5f}")


# ============================================================ per-cell-year death decomposition (fire driver)
def stage_cellyear_deaths():
    """per (member, Cell, Year) on the dev subsample: tree rows, deaths, sum of printed hazard, the
    fire-floor expectation; residual = deaths - hazard - floor (= fire above the floor, see fire_check).
    Then: where is the residual (cell concentration) and which climate drives it."""
    R = resist_map()
    parts = []
    for f in sorted(os.listdir(DEVDIR)):
        if not f.endswith(".parquet"):
            continue
        mem = f[:-8]
        gcm, scen, seed, win = mem.rsplit("_", 3)
        A = (pl.scan_parquet(os.path.join(DEVDIR, f)).filter(pl.col("Type") <= 6)
             .with_columns(res=pl.col("Type").cast(pl.Int64).replace_strict(R, return_dtype=pl.Float64),
                           m=pl.col("mort").cast(pl.Float64).clip(0, 1))
             .group_by(["Cell", "Year"]).agg(pl.len().alias("n"), pl.col("isdead").cast(pl.Int64).sum().alias("deaths"),
                                             pl.col("m").sum().alias("hazard"),
                                             ((1 - pl.col("res")) * 0.001 * (1 - pl.col("m"))).sum().alias("floor"),
                                             (pl.col("m") >= 1 - 1e-6).sum().alias("hard"))
             .collect())
        assert A.select(["Cell", "Year"]).n_unique() == A.height
        parts.append(A.with_columns(gcm=pl.lit(gcm), scen=pl.lit(scen), seed=pl.lit(int(seed[1:])), win=pl.lit(win)))
        log(f"  {mem}: {A.height} cell-years")
    D = pl.concat(parts).with_columns(resid=pl.col("deaths") - pl.col("hazard") - pl.col("floor"))
    D.write_parquet(res_path("cellyear_deaths.parquet"))
    out = {}
    # concentration of the residual across cells (30-yr totals per member, cell)
    C = D.group_by(["gcm", "scen", "seed", "win", "Cell"]).agg(pl.col("resid").sum(), pl.col("n").sum(),
                                                               pl.col("deaths").sum())
    C = C.with_columns(rr=pl.col("resid") / pl.col("n"))
    rr = C["rr"].to_numpy()
    out["cell_resid_rate_q"] = q(rr)
    srt = np.sort(np.clip(C["resid"].to_numpy(), 0, None))[::-1]
    out["share_of_positive_resid_in_top10pct_cells"] = float(srt[: max(1, srt.size // 10)].sum() / srt.sum())
    # climate join: summer (JJA) temperature and precipitation of the same year
    clim = os.path.join(os.path.dirname(OUT), "climate", "cell_year.parquet")
    if os.path.exists(clim):
        K = (pl.scan_parquet(clim).select(["gcm", "scen", "Cell", "Year", "temp_m06", "temp_m07", "temp_m08",
                                           "prec_m06", "prec_m07", "prec_m08", "tmean_ann"])
             .with_columns(tJJA=(pl.col("temp_m06") + pl.col("temp_m07") + pl.col("temp_m08")) / 3,
                           pJJA=pl.col("prec_m06") + pl.col("prec_m07") + pl.col("prec_m08"))
             .select(["gcm", "scen", "Cell", "Year", "tJJA", "pJJA", "tmean_ann"]).collect())
        # Historical climate rows are labelled scen=Historical; 3071-3100 uses recycled years -> skip w3071
        DJ = (D.filter(pl.col("win") != "w3071")
              .with_columns(pl.col("Cell").cast(pl.Int32), pl.col("Year").cast(pl.Int32))
              .join(K, on=["gcm", "scen", "Cell", "Year"], how="inner")
              .with_columns(rrate=pl.col("resid") / pl.col("n"), hrate=pl.col("hazard") / pl.col("n")))
        out["climate_joined_cellyears"] = DJ.height
        cc = {}
        for v in ["tJJA", "pJJA", "tmean_ann"]:
            x = DJ[v].to_numpy().astype(np.float64)
            cc[v] = dict(resid=float(np.corrcoef(x, DJ["rrate"].to_numpy())[0, 1]),
                         hazard=float(np.corrcoef(x, DJ["hrate"].to_numpy())[0, 1]))
        out["corr_with_climate_cellyear"] = cc
        # binned by summer precipitation
        edges = np.quantile(DJ["pJJA"].to_numpy(), [0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0])
        bins = []
        for a, b in zip(edges[:-1], edges[1:], strict=True):
            S = DJ.filter((pl.col("pJJA") >= a) & (pl.col("pJJA") <= b))
            bins.append(dict(pJJA_lo=float(a), pJJA_hi=float(b), cellyears=S.height,
                             resid_rate=float(S["resid"].sum() / S["n"].sum()),
                             hazard_rate=float(S["hazard"].sum() / S["n"].sum()),
                             death_rate=float(S["deaths"].sum() / S["n"].sum())))
        out["by_pJJA_decile_bins"] = bins
    jdump(out, "cellyear_deaths_summary.json")
    log(json.dumps(out, indent=1))


# ============================================================ main
def main():
    st = sys.argv[1]
    log(f"=== explore_de_anatomy {st} {sys.argv[2:]} (polars {pl.__version__}) ===")
    t0 = time.time()
    if st == "extract_full":
        for lab in sys.argv[2:]:
            stage_extract_full(lab)
    elif st == "extract_sub":
        for lab in sys.argv[2:]:
            stage_extract_sub(lab)
    elif st == "analyze_full":
        stage_analyze_full(sys.argv[2:])
    elif st == "extras":
        for lab in sys.argv[2:]:
            stage_extras(lab)
    elif st == "analyze_sub":
        for lab in sys.argv[2:]:
            stage_analyze_sub(lab)
    elif st == "members":
        # cross-member robustness: the analyze_sub battery on each converted ind_dev member-window
        os.environ["ANAT_DEV"] = "1"
        os.environ["ANAT_RESSUB"] = "members"
        for lab in sys.argv[2:]:
            try:
                stage_analyze_sub(lab)
            except Exception as e:  # one broken member must not lose the others
                log(f"  !! {lab} FAILED: {type(e).__name__}: {e}")
    elif st == "summarize_members":
        stage_summarize_members()
    elif st == "cellyear_deaths":
        os.environ["ANAT_RESSUB"] = "members"
        stage_cellyear_deaths()
    elif st == "fire_check":
        os.environ["ANAT_RESSUB"] = "members"
        stage_fire_check()
    else:
        raise SystemExit(f"unknown stage {st}")
    log(f"=== done {st} in {time.time()-t0:.0f}s ===")


if __name__ == "__main__":
    main()
