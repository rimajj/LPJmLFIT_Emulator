#!/usr/bin/env python3
"""explore_de_convert.py -- LINE X, Germany data-driven emulator, stage "convert".

Convert every LPJmL-FIT `ind` tree table of the Germany production runs (40 CSV files, ~4.7 TB)
to parquet ONCE, so that no later stage ever reads the CSV again.  PREP, NOT A FINDING: this
produces tables plus gate results, never a skill number.

Source (READ-ONLY):  /p/projects/waldspektrum/data/LPJmLFIT/productionruns_jamir/
    <gcm>/<scen>/random_seed_<seed>/output/{ind_.csv | ind_2044.csv | ind_2100.csv | ind_3100.csv}
Output:
    /p/tmp/jamirp/X_de/ind/<gcm>/<scen>/s<seed>/<window>/cb=NN/part-0.parquet
        cb = Cell // 500 (00..18), one file per cell block, rows sorted (Year, Cell, Patch) with
        the writer's own within-patch PFT-list order kept (stable), ONE ROW GROUP PER YEAR, so a
        cell subset prunes by directory and a year subset prunes by row-group statistics.
    /p/tmp/jamirp/X_de/ind_dev/<gcm>_<scen>_s<seed>_<window>.parquet
        the Cell % 10 == 0 dev subset (907 cells), same row order, one row group per year,
        written in the SAME pass (the CSV is read exactly once).
    /p/tmp/jamirp/X_de/ind/_gates/<member>.json   full gate record of one member-window
    /p/tmp/jamirp/X_de/ind/_gates.csv             one flat row per member-window (rebuilt under
                                                  flock by every task from the JSONs)
    /p/tmp/jamirp/X_de/ind/_census/<member>.parquet  per (Year, Cell) row counts -- GATE EVIDENCE
                                                  (recomputable from the tables; kept because it is
                                                  what the census gate was scored on)

Dtypes (pinned, never inferred): Year Int16, ID Int32, Type Int8, Patch Int16, Cell Int16,
isdead Int8, everything else Float32 (the C writer prints %g = 6 significant digits, which a
float32 round-trips exactly; FLT_DIG = 6). ALL rows are kept, grass (Type 7-9) included.
Nothing derived is added.  A value that does not parse as its pinned integer type ABORTS the task
(polars is strict), so a stray header line / garbage token cannot slip in silently.

How the single pass works: the file is read in 256 MiB byte chunks by background `os.pread`
threads; each chunk is cut at its last newline (the remainder carries into the next), the NEWLINES
ARE COUNTED ON THE RAW BYTES (an independent line count, not the parser's own row count), the block
is parsed with pl.read_csv(schema=...), rows are buffered until their Year is complete, and then the
whole year is processed EAGERLY (no streaming engine anywhere -- the ADR-0036 key-set trap):
order check, census, key uniqueness, value sanity, and one row group appended to each of the 19
block files and to the dev file.  After the writers close, every file is READ BACK (non-streamed,
per block) and the census, the row count, the key uniqueness and the sort order are recomputed from
disk and compared with the in-pass values.  Only then is the staging directory renamed to its final
name.  A task whose final output already exists and whose gate JSON says `conversion_ok` (and whose
source size/mtime is unchanged) is SKIPPED, so the array is restartable/idempotent.

Usage
  python scripts/explore_de_convert.py list                   # manifest with task indices
  python scripts/explore_de_convert.py run <idx>              # convert one member-window
  python scripts/explore_de_convert.py collect                # rebuild _gates.csv from the JSONs
  python scripts/explore_de_convert.py submit <array-spec> [partition qos ncpus time exclude]
      e.g. submit 0-39%8 standard short 16 03:00:00
  Env knobs (EXPORT them; the names avoid the sbatch wrappers' own variables):
      DECONV_FORCE=1     reconvert even if a passing output exists
      DECONV_CHUNK_MB    read chunk size in MiB (default 256)
      DECONV_PREFETCH    outstanding background reads (default 4)
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

SRC_ROOT = "/p/projects/waldspektrum/data/LPJmLFIT/productionruns_jamir"
OUT_ROOT = "/p/tmp/jamirp/X_de/ind"
DEV_ROOT = "/p/tmp/jamirp/X_de/ind_dev"
GATE_DIR = f"{OUT_ROOT}/_gates"
CENSUS_DIR = f"{OUT_ROOT}/_census"
DUPKEY_DIR = f"{OUT_ROOT}/_dupkeys"
GATES_CSV = f"{OUT_ROOT}/_gates.csv"
LOGDIR = os.path.join(_ROOT, "logs")
PY = "/home/jamirp/.conda/envs/py311_new/bin/python"

GCMS = ("MPI-ESM1-2-HR", "ACCESS-CM2")
SCENS = ("Historical", "ssp126", "ssp245", "ssp370")
SEEDS = (1, 2)
# file name -> window label (first year of the file)
HIST_FILES = (("ind_.csv", "h1985"),)
SSP_FILES = (("ind_2044.csv", "w2015"), ("ind_2100.csv", "w2071"), ("ind_3100.csv", "w3071"))

SOIL_FILE = "/p/projects/biodiversity/billing/input/FirEUrisk/LPJ/soil_germany_9km_new.clm"
NCELL = 9067
NPATCH = 250
CELL_BLOCK = 500
DEV_MOD = 10

COLS = [
    "Year", "ID", "Type", "Height", "Age", "agb", "vegc", "transp", "npp", "gpp", "wscal_mean",
    "SLA", "Longevity", "Wooddens", "LAI", "fpc_ind", "minwscal", "D95", "D95max", "beta_root",
    "k_root", "mort_npp", "mort_age", "mort_water", "mort_temp", "mort", "isdead", "Patch", "Cell",
]
INT_DT = {"Year": pl.Int16, "ID": pl.Int32, "Type": pl.Int8, "Patch": pl.Int16,
          "Cell": pl.Int16, "isdead": pl.Int8}
SCHEMA = {c: INT_DT.get(c, pl.Float32) for c in COLS}
FLOATS = [c for c in COLS if SCHEMA[c] == pl.Float32]
MORT = ["mort_npp", "mort_age", "mort_water", "mort_temp", "mort"]
# parquet encoding: dictionary for the low-cardinality integer columns, BYTE_STREAM_SPLIT for the
# floats (measured on a 400k-row sample: 63.7 B/row vs 78.0 B/row for pyarrow's default).
PQ_KW = dict(
    compression="zstd",
    compression_level=3,
    use_dictionary=["Year", "Type", "Patch", "Cell", "isdead"],
    column_encoding={c: "BYTE_STREAM_SPLIT" for c in FLOATS},
    write_statistics=True,
)
ROWGROUP_MAX = 64_000_000  # large enough that one (block, year) is always ONE row group


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ------------------------------------------------------------------------------------------------
# manifest
# ------------------------------------------------------------------------------------------------
def manifest() -> list[dict]:
    out = []
    for gcm in GCMS:
        for scen in SCENS:
            for seed in SEEDS:
                files = HIST_FILES if scen == "Historical" else SSP_FILES
                for fname, win in files:
                    src = f"{SRC_ROOT}/{gcm}/{scen}/random_seed_{seed}/output/{fname}"
                    member = f"{gcm}_{scen}_s{seed}_{win}"
                    out.append(dict(
                        idx=len(out), gcm=gcm, scen=scen, seed=seed, window=win, src=src,
                        member=member,
                        out_dir=f"{OUT_ROOT}/{gcm}/{scen}/s{seed}/{win}",
                        dev_file=f"{DEV_ROOT}/{member}.parquet",
                        gate_json=f"{GATE_DIR}/{member}.json",
                        census_file=f"{CENSUS_DIR}/{member}.parquet",
                    ))
    return out


# ------------------------------------------------------------------------------------------------
# reading: background pread chunks, stitched at newlines, newline-counted on the raw bytes
# ------------------------------------------------------------------------------------------------
def _pread_full(fd: int, n: int, off: int) -> bytes:
    parts = []
    got = 0
    while got < n:
        b = os.pread(fd, n - got, off + got)
        if not b:
            break
        parts.append(b)
        got += len(b)
    return b"".join(parts) if len(parts) != 1 else parts[0]


def iter_blocks(path: str, chunk: int, prefetch: int, stats: dict):
    """Yield complete-line byte blocks of the data section, in file order.

    Sets stats: header (bytes), data_offset, newlines (count of b'\\n' in the data section),
    tail (bytes after the last newline; b'' for a newline-terminated file), read_wait_s."""
    fd = os.open(path, os.O_RDONLY)
    try:
        size = os.fstat(fd).st_size
        head = _pread_full(fd, 65536, 0)
        nl = head.find(b"\n")
        if nl < 0:
            raise RuntimeError("no newline in the first 64 KiB -- not an ind CSV")
        stats["header"] = head[:nl].decode()
        off0 = nl + 1
        stats["data_offset"] = off0
        offsets = list(range(off0, size, chunk))
        stats["n_chunks"] = len(offsets)
        stats["newlines"] = 0
        stats["read_wait_s"] = 0.0
        carry = b""
        with ThreadPoolExecutor(max_workers=prefetch) as ex:
            futs = {}
            nxt = 0
            for i in range(len(offsets)):
                while nxt < len(offsets) and nxt < i + prefetch:
                    futs[nxt] = ex.submit(_pread_full, fd, min(chunk, size - offsets[nxt]),
                                          offsets[nxt])
                    nxt += 1
                t0 = time.time()
                buf = futs.pop(i).result()
                stats["read_wait_s"] += time.time() - t0
                data = carry + buf if carry else buf
                cut = data.rfind(b"\n")
                if cut < 0:
                    carry = data
                    continue
                block = data[: cut + 1]
                carry = data[cut + 1:]
                stats["newlines"] += block.count(b"\n")
                yield block
        stats["tail"] = carry
    finally:
        os.close(fd)


def parse_block(block: bytes) -> pl.DataFrame:
    return pl.read_csv(block, has_header=False, new_columns=COLS, schema=SCHEMA, rechunk=True)


# ------------------------------------------------------------------------------------------------
# per-year eager processing
# ------------------------------------------------------------------------------------------------
class YearProcessor:
    def __init__(self, stage_dir: str, stage_dev: str, y0: int, y1: int, nthreads: int):
        self.stage_dir = stage_dir
        self.stage_dev = stage_dev
        self.y0, self.y1 = y0, y1
        self.writers: dict[int, pq.ParquetWriter] = {}
        self.dev_writer: pq.ParquetWriter | None = None
        self.schema: pa.Schema | None = None
        self.pool = ThreadPoolExecutor(max_workers=max(4, min(24, nthreads)))
        self.census: list[pl.DataFrame] = []
        self.per_year: list[dict] = []
        self.rows_written = 0
        self.dev_rows_written = 0
        self.dup_examples: list[dict] = []
        self.dup_keys: list[pl.DataFrame] = []
        self.nonfinite_all: dict[str, int] = {c: 0 for c in FLOATS}
        self.flushes: dict[int, int] = {}

    def _writer(self, cb: int) -> pq.ParquetWriter:
        w = self.writers.get(cb)
        if w is None:
            d = f"{self.stage_dir}/cb={cb:02d}"
            os.makedirs(d, exist_ok=True)
            w = pq.ParquetWriter(f"{d}/part-0.parquet", self.schema, **PQ_KW)
            self.writers[cb] = w
        return w

    def flush(self, year: int, parts: list[pl.DataFrame], late: bool = False) -> None:
        t0 = time.time()
        df = pl.concat(parts, rechunk=True) if len(parts) > 1 else parts[0]
        n = df.height
        self.flushes[year] = self.flushes.get(year, 0) + 1
        # --- order within the year: (Cell, Patch) must be non-decreasing (writer loop order)
        ck = df["Cell"].cast(pl.Int32) * 256 + df["Patch"].cast(pl.Int32)
        order_viol = int((ck.diff() < 0).sum())
        if order_viol:
            df = df.sort(["Cell", "Patch"], maintain_order=True)
        # --- census (eager group_by)
        cen = (
            df.group_by("Cell")
            .agg(
                n_rows=pl.len(),
                n_tree=(pl.col("Type") <= 6).sum(),
                n_tree_live=((pl.col("Type") <= 6) & (pl.col("isdead") == 0)).sum(),
                n_grass=(pl.col("Type") >= 7).sum(),
            )
            .with_columns(pl.lit(year, dtype=pl.Int16).alias("Year"))
        )
        self.census.append(cen)
        # --- ranges
        rng = df.select(
            cell_bad=((pl.col("Cell") < 0) | (pl.col("Cell") >= NCELL)).sum(),
            patch_bad=((pl.col("Patch") < 0) | (pl.col("Patch") >= NPATCH)).sum(),
            type_bad=((pl.col("Type") < 0) | (pl.col("Type") > 9)).sum(),
            isdead_bad=(~pl.col("isdead").is_in([0, 1])).sum(),
            id_neg=(pl.col("ID") < 0).sum(),
            year_bad=((pl.col("Year") < self.y0) | (pl.col("Year") > self.y1)).sum(),
            null_total=pl.sum_horizontal([pl.col(c).null_count() for c in COLS]),
            isdead_grass=((pl.col("Type") >= 7) & (pl.col("isdead") != 0)).sum(),
        ).row(0, named=True)
        nonfin = df.select([(~pl.col(c).is_finite()).sum().alias(c) for c in FLOATS]).row(
            0, named=True)
        for c, v in nonfin.items():
            self.nonfinite_all[c] += int(v or 0)
        # --- tree rows: uniqueness of (Cell, Patch, Type, ID) + value sanity
        tr = df.filter(pl.col("Type") <= 6)
        packable = rng["cell_bad"] == 0 and rng["patch_bad"] == 0 and rng["id_neg"] == 0
        if packable:
            key = (((tr["Cell"].cast(pl.Int64) * 256 + tr["Patch"].cast(pl.Int64)) * 8
                    + tr["Type"].cast(pl.Int64)) * (1 << 31)) + tr["ID"].cast(pl.Int64)
            n_unique = key.n_unique()
        else:
            n_unique = tr.select(["Cell", "Patch", "Type", "ID"]).n_unique()
        dup_excess = tr.height - n_unique
        n_dup_keys = 0
        dup_excess_traitkey = 0
        if dup_excess:
            # how many distinct keys collide, and do the immutable traits separate them?
            kcols = ["Cell", "Patch", "Type", "ID"]
            dd = tr.filter(pl.struct(kcols).is_duplicated())
            n_dup_keys = dd.select(kcols).n_unique()
            self.dup_keys.append(
                dd.group_by(kcols).agg(n=pl.len(), n_trait_distinct=pl.struct(
                    ["SLA", "Wooddens"]).n_unique(), height_min=pl.col("Height").min(),
                    height_max=pl.col("Height").max())
                .with_columns(pl.lit(year, dtype=pl.Int16).alias("Year")))
            dup_excess_traitkey = dd.height - dd.select(kcols + ["SLA", "Wooddens"]).n_unique()
        if dup_excess and len(self.dup_examples) < 50:
            d = (tr.group_by(["Cell", "Patch", "Type", "ID"]).agg(n=pl.len())
                 .filter(pl.col("n") > 1).sort(["Cell", "Patch", "Type", "ID"]).head(20))
            for r in d.iter_rows(named=True):
                self.dup_examples.append(dict(Year=year, **r))
        tsan = tr.select(
            height_nonfinite=(~pl.col("Height").is_finite()).sum(),
            agb_nonfinite=(~pl.col("agb").is_finite()).sum(),
            height_lt5=(pl.col("Height") < 5.0).sum(),
            height_eq5=(pl.col("Height") == 5.0).sum(),
            mort_bad=pl.any_horizontal(
                [(~pl.col(c).is_finite()) | (pl.col(c) < 0) | (pl.col(c) > 1) for c in MORT]
            ).sum(),
            mort_absmax=pl.max_horizontal([pl.col(c).abs().max() for c in MORT]),
            n_dead=(pl.col("isdead") == 1).sum(),
        ).row(0, named=True)
        # --- write: one row group per block + one to the dev file
        df = df.with_columns((pl.col("Cell") // CELL_BLOCK).alias("_cb"))
        blocks = df.partition_by("_cb", as_dict=True, maintain_order=True)
        tables = {}
        for k, part in blocks.items():
            cb = int(k[0] if isinstance(k, tuple) else k)
            tables[cb] = part.drop("_cb").to_arrow()
        dev = df.filter(pl.col("Cell") % DEV_MOD == 0).drop("_cb").to_arrow()
        if self.schema is None:
            first = next(iter(tables.values()))
            self.schema = first.schema
        for t in list(tables.values()) + [dev]:
            if not t.schema.equals(self.schema):
                raise RuntimeError(f"arrow schema drift in year {year}: {t.schema}")
        writers = {cb: self._writer(cb) for cb in tables}
        if self.dev_writer is None:
            os.makedirs(os.path.dirname(self.stage_dev), exist_ok=True)
            self.dev_writer = pq.ParquetWriter(self.stage_dev, self.schema, **PQ_KW)
        futs = [self.pool.submit(writers[cb].write_table, t, row_group_size=ROWGROUP_MAX)
                for cb, t in tables.items()]
        futs.append(self.pool.submit(self.dev_writer.write_table, dev,
                                     row_group_size=ROWGROUP_MAX))
        for f in futs:
            f.result()
        self.rows_written += n
        self.dev_rows_written += dev.num_rows
        rec = dict(Year=year, rows=n, tree_rows=tr.height, dev_rows=dev.num_rows,
                   cells=cen.height, order_viol=order_viol, dup_excess=dup_excess,
                   n_dup_keys=n_dup_keys, dup_excess_traitkey=dup_excess_traitkey,
                   late=late, **rng, **tsan,
                   nonfinite_any=int(sum(int(v or 0) for v in nonfin.values())))
        self.per_year.append(rec)
        log(f"  year {year}: rows={n:,} tree={tr.height:,} cells={cen.height} "
            f"dup={dup_excess} order_viol={order_viol} nulls={rng['null_total']} "
            f"mort_bad={tsan['mort_bad']} ({time.time() - t0:.1f}s)")

    def close(self) -> None:
        for w in self.writers.values():
            w.close()
        if self.dev_writer is not None:
            self.dev_writer.close()
        self.pool.shutdown(wait=True)


# ------------------------------------------------------------------------------------------------
# read-back verification (non-streamed, per block file)
# ------------------------------------------------------------------------------------------------
def read_back(stage_dir: str, stage_dev: str, census: pl.DataFrame, nthreads: int) -> dict:
    t0 = time.time()
    res = dict(ok=True, problems=[])
    files = sorted(
        (int(d.split("=")[1]), f"{stage_dir}/{d}/part-0.parquet")
        for d in os.listdir(stage_dir) if d.startswith("cb=")
    )
    res["n_block_files"] = len(files)

    def one(item):
        cb, f = item
        md = pq.ParquetFile(f).metadata
        df = pl.read_parquet(f, columns=["Year", "Cell", "Patch", "Type", "ID"],
                             use_statistics=False, parallel="columns")
        out = dict(cb=cb, meta_rows=md.num_rows, rows=df.height, row_groups=md.num_row_groups)
        out["cell_block_bad"] = int((df["Cell"] // CELL_BLOCK != cb).sum())
        sk = (df["Year"].cast(pl.Int64) * 1_000_000_000 + df["Cell"].cast(pl.Int64) * 256
              + df["Patch"].cast(pl.Int64))
        out["sort_viol"] = int((sk.diff() < 0).sum())
        out["census"] = df.group_by(["Year", "Cell"]).agg(n_rows_disk=pl.len())
        tr = df.filter(pl.col("Type") <= 6)
        out["tree_rows"] = tr.height
        out["tree_unique_year_keys"] = tr.select(["Year", "Cell", "Patch", "Type", "ID"]).n_unique()
        # per-row-group year purity (a year subset must prune on statistics)
        impure = 0
        for i in range(md.num_row_groups):
            st = md.row_group(i).column(0).statistics
            if st is None or not st.has_min_max or st.min != st.max:
                impure += 1
        out["rowgroup_year_impure"] = impure
        return out

    with ThreadPoolExecutor(max_workers=4) as ex:
        outs = list(ex.map(one, files))
    disk_cen = pl.concat([o.pop("census") for o in outs])
    res["blocks"] = outs
    res["rows_disk"] = int(sum(o["rows"] for o in outs))
    res["rows_meta"] = int(sum(o["meta_rows"] for o in outs))
    if res["rows_disk"] != res["rows_meta"]:
        res["ok"] = False
        res["problems"].append("row count != metadata row count")
    for k in ("cell_block_bad", "sort_viol", "rowgroup_year_impure"):
        s = int(sum(o[k] for o in outs))
        res[k] = s
        if s:
            res["ok"] = False
            res["problems"].append(f"{k}={s}")
    res["tree_rows_disk"] = int(sum(o["tree_rows"] for o in outs))
    res["tree_dup_excess_disk"] = int(
        sum(o["tree_rows"] - o["tree_unique_year_keys"] for o in outs))
    # census equality: in-pass (from the CSV parse) vs on-disk
    j = census.select(["Year", "Cell", "n_rows"]).join(
        disk_cen, on=["Year", "Cell"], how="full", coalesce=True)
    mism = j.filter(pl.col("n_rows").fill_null(-1) != pl.col("n_rows_disk").fill_null(-1)).height
    res["census_mismatch_blocks"] = mism
    if mism:
        res["ok"] = False
        res["problems"].append(f"census mismatch in {mism} (Year, Cell) blocks")
    # dev file
    ddf = pl.read_parquet(stage_dev, columns=["Year", "Cell", "Patch"])
    res["dev_rows_disk"] = ddf.height
    exp_dev = int(census.filter(pl.col("Cell") % DEV_MOD == 0)["n_rows"].sum())
    res["dev_rows_expected"] = exp_dev
    res["dev_cells"] = int(ddf["Cell"].n_unique())
    res["dev_cell_bad"] = int((ddf["Cell"] % DEV_MOD != 0).sum())
    dk = (ddf["Year"].cast(pl.Int64) * 1_000_000_000 + ddf["Cell"].cast(pl.Int64) * 256
          + ddf["Patch"].cast(pl.Int64))
    res["dev_sort_viol"] = int((dk.diff() < 0).sum())
    res["dev_row_groups"] = pq.ParquetFile(stage_dev).metadata.num_row_groups
    if exp_dev != ddf.height or res["dev_cell_bad"] or res["dev_sort_viol"]:
        res["ok"] = False
        res["problems"].append("dev subset mismatch")
    res["out_bytes"] = int(sum(os.path.getsize(f) for _, f in files))
    res["dev_bytes"] = os.path.getsize(stage_dev)
    res["readback_s"] = round(time.time() - t0, 1)
    return res


# ------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------
def ranges(xs: list[int]) -> str:
    """Compress a sorted int list to '0-4,7,9-12'."""
    if not xs:
        return ""
    out, a, b = [], xs[0], xs[0]
    for x in xs[1:]:
        if x == b + 1:
            b = x
        else:
            out.append(f"{a}-{b}" if b > a else f"{a}")
            a = b = x
    out.append(f"{a}-{b}" if b > a else f"{a}")
    return ",".join(out)


def parse_tail(tail: bytes) -> tuple[pl.DataFrame | None, str]:
    """A non-empty tail = bytes after the last newline. Complete 29-field record -> keep."""
    if not tail:
        return None, "none"
    try:
        s = tail.decode(errors="replace")
    except Exception:  # noqa: BLE001
        s = repr(tail[:200])
    if s.count(",") == len(COLS) - 1:
        try:
            df = parse_block(tail + b"\n")
            if df.null_count().sum_horizontal().item() == 0:
                return df, "complete-unterminated"
        except Exception:  # noqa: BLE001
            pass
    return None, "partial"


def rock_cells() -> list[int]:
    """Cells whose soil code is 13 (= the 13th soilpar entry, "rock and ice", par/soil_20m.js);
    LPJmL skips them. Read from the soil file the run used (LPJSOIL v3, header parsed)."""
    b = open(SOIL_FILE, "rb").read()
    if b[:7] != b"LPJSOIL" or struct.unpack("<i", b[7:11])[0] != 3:
        raise RuntimeError("unexpected soil header")
    nc = struct.unpack("<i", b[27:31])[0]
    dt = struct.unpack("<i", b[47:51])[0]
    v = np.frombuffer(b[51:], dtype={0: np.uint8, 1: np.int16, 2: np.int32}[dt])[:nc]
    return [int(i) for i in np.nonzero(v == 13)[0]]


def src_sig(src: str) -> dict:
    st = os.stat(src)
    return dict(src_bytes=st.st_size, src_mtime=int(st.st_mtime))


def already_done(m: dict) -> bool:
    if os.environ.get("DECONV_FORCE", "0") not in ("", "0"):
        return False
    try:
        with open(m["gate_json"]) as f:
            g = json.load(f)
    except (OSError, ValueError):
        return False
    if not g.get("conversion_ok"):
        return False
    if g.get("src_bytes") != os.stat(m["src"]).st_size or \
            g.get("src_mtime") != int(os.stat(m["src"]).st_mtime):
        return False
    if not (os.path.isdir(m["out_dir"]) and os.path.isfile(m["dev_file"])):
        return False
    try:
        rows = sum(
            pq.ParquetFile(f"{m['out_dir']}/{d}/part-0.parquet").metadata.num_rows
            for d in os.listdir(m["out_dir"]) if d.startswith("cb=")
        )
        dev_rows = pq.ParquetFile(m["dev_file"]).metadata.num_rows
    except Exception:  # noqa: BLE001
        return False
    return rows == g.get("parquet_rows") and dev_rows == g.get("dev_rows")


# ------------------------------------------------------------------------------------------------
# one member-window
# ------------------------------------------------------------------------------------------------
def run(idx: int) -> int:
    m = manifest()[idx]
    nthreads = int(os.environ.get("POLARS_MAX_THREADS", os.cpu_count() or 8))
    log(f"task {idx}: {m['member']}  host={socket.gethostname()} threads={nthreads} "
        f"polars={pl.__version__} pyarrow={pa.__version__}")
    log(f"  src {m['src']}")
    if already_done(m):
        log("  SKIP: final output exists, gate JSON says conversion_ok, source unchanged")
        collect()
        return 0
    meta = json.load(open(m["src"] + ".json"))
    y0, y1 = int(meta["firstyear"]), int(meta["lastyear"])
    sig = src_sig(m["src"])
    log(f"  json window {y0}..{y1}, ncell={meta['ncell']}, {sig['src_bytes'] / 1e9:.1f} GB")
    job = os.environ.get("SLURM_JOB_ID", "local")
    stage_dir = f"{m['out_dir']}.staging-{job}"
    stage_dev = f"{DEV_ROOT}/.staging-{job}/{m['member']}.parquet"
    for p in (stage_dir, os.path.dirname(stage_dev)):
        if os.path.exists(p):
            shutil.rmtree(p)
    os.makedirs(stage_dir)
    chunk = int(os.environ.get("DECONV_CHUNK_MB", "256")) * (1 << 20)
    prefetch = int(os.environ.get("DECONV_PREFETCH", "4"))

    t_start = time.time()
    stats: dict = {}
    yp = YearProcessor(stage_dir, stage_dev, y0, y1, nthreads)
    cur, parts = None, []
    year_order_viol = 0
    late_parts: dict[int, list] = {}
    flushed: set[int] = set()
    parse_s = 0.0
    nparsed = 0
    nbytes = 0
    t_last = time.time()
    for bi, block in enumerate(iter_blocks(m["src"], chunk, prefetch, stats)):
        if bi == 0 and stats["header"].split(",") != COLS:
            raise RuntimeError(f"header drift: {stats['header']}")
        t0 = time.time()
        df = parse_block(block)
        parse_s += time.time() - t0
        nparsed += df.height
        nbytes += len(block)
        del block
        yr = df["Year"]
        ymin, ymax = yr.min(), yr.max()
        if ymin == ymax and (cur is None or ymin == cur):
            cur = ymin
            parts.append(df)
        else:
            year_order_viol += int((yr.diff() < 0).sum())
            for part in df.partition_by("Year", maintain_order=True):
                y = int(part["Year"][0])
                if cur is None:
                    cur = y
                if y == cur:
                    parts.append(part)
                elif y > cur and y not in flushed:
                    yp.flush(cur, parts)
                    flushed.add(cur)
                    cur, parts = y, [part]
                else:  # a year that was already flushed (or older): keep rows, flag
                    year_order_viol += part.height
                    late_parts.setdefault(y, []).append(part)
        if time.time() - t_last > 60:
            el = time.time() - t_start
            log(f"  progress: {nbytes / 1e9:.1f} GB parsed, {nparsed:,} rows, "
                f"{nbytes / 1e9 / el:.2f} GB/s, read-wait {stats['read_wait_s']:.0f}s "
                f"parse {parse_s:.0f}s")
            t_last = time.time()
    if parts:
        yp.flush(cur, parts)
        flushed.add(cur)
    tail_df, tail_kind = parse_tail(stats.get("tail", b""))
    if tail_df is not None:
        # a complete record without a trailing newline: it belongs to the data; flush as late
        late_parts.setdefault(int(tail_df["Year"][0]), []).append(tail_df)
    for y, ps in sorted(late_parts.items()):
        yp.flush(y, ps, late=True)
    yp.close()
    t_pass = time.time() - t_start
    csv_lines = stats["newlines"] + (1 if tail_kind == "complete-unterminated" else 0)
    log(f"  pass done in {t_pass:.0f}s: csv complete data lines={csv_lines:,} "
        f"rows written={yp.rows_written:,} tail={tail_kind} "
        f"(read-wait {stats['read_wait_s']:.0f}s, parse {parse_s:.0f}s)")

    census = pl.concat(yp.census).group_by(["Year", "Cell"]).agg(
        pl.col("n_rows").sum(), pl.col("n_tree").sum(), pl.col("n_tree_live").sum(),
        pl.col("n_grass").sum()).sort(["Year", "Cell"])
    rb = read_back(stage_dir, stage_dev, census, nthreads)
    log(f"  read-back ({rb['readback_s']}s): ok={rb['ok']} rows_disk={rb['rows_disk']:,} "
        f"problems={rb['problems']}")

    # ---------------- gates ----------------
    py = pl.DataFrame(yp.per_year)
    years_present = sorted(int(y) for y in census["Year"].unique().to_list())
    years_expected = list(range(y0, y1 + 1))
    missing_years = [y for y in years_expected if y not in years_present]
    extra_years = [y for y in years_present if y not in years_expected]
    # (Year, Cell) census over the EXPECTED grid
    full = pl.DataFrame({"Year": np.repeat(years_expected, NCELL).astype(np.int16),
                         "Cell": np.tile(np.arange(NCELL), len(years_expected))},
                        schema_overrides={"Cell": SCHEMA["Cell"]})
    cj = full.join(census, on=["Year", "Cell"], how="left")
    miss = cj.filter(pl.col("n_rows").is_null())
    miss_by_year = {}
    for (y,), g in miss.group_by(["Year"], maintain_order=True):
        miss_by_year[int(y)] = g["Cell"].sort().to_list()
    # cells never present in ANY year of this file (LPJmL skips them: soil code 13 = "rock and ice"
    # in par/soil_20m.js -> grid[cell].skip -> the ind writer emits nothing for them)
    present_cells = set(census["Cell"].unique().to_list())
    absent_all = sorted(set(range(NCELL)) - present_cells)
    rock = rock_cells()
    # HOLES = a (Year, Cell) block missing in a present year for a cell that exists in some other
    # year: the dangerous kind, which a year-pairing would misread as mass death
    holes = miss.filter(pl.col("Year").is_in(years_present)
                        & ~pl.col("Cell").is_in(absent_all))
    holes_by_year = {}
    for (y,), gg in holes.group_by(["Year"], maintain_order=True):
        holes_by_year[str(int(y))] = ranges(gg["Cell"].sort().to_list())
    # missing blocks inside the years that ARE present (the dangerous kind: looks like mass death)
    miss_in_present = {y: c for y, c in miss_by_year.items() if y in years_present}
    n_miss_in_present = int(sum(len(c) for c in miss_in_present.values()))
    cells_missing_in_present = sorted({c for cs in miss_in_present.values() for c in cs})
    # partial-year: in a present year, cells missing
    tree_cells = census.filter(pl.col("n_tree") > 0).group_by("Year").agg(
        n=pl.len()).sort("Year")

    dup_total = int(py["dup_excess"].sum())
    if yp.dup_keys:
        dupk = pl.concat(yp.dup_keys).select(
            ["Year", "Cell", "Patch", "Type", "ID", "n", "n_trait_distinct", "height_min",
             "height_max"]).sort(["Cell", "Patch", "Type", "ID", "Year"])
    else:
        dupk = pl.DataFrame(schema={"Year": pl.Int16, "Cell": SCHEMA["Cell"], "Patch": pl.Int16,
                                    "Type": pl.Int8, "ID": pl.Int32, "n": pl.UInt32,
                                    "n_trait_distinct": pl.UInt32, "height_min": pl.Float32,
                                    "height_max": pl.Float32})
    n_dup_distinct = dupk.select(["Cell", "Patch", "Type", "ID"]).n_unique() if dupk.height else 0
    null_total = int(py["null_total"].sum())
    g = dict(
        member=m["member"], idx=idx, gcm=m["gcm"], scen=m["scen"], seed=m["seed"],
        window=m["window"], src=m["src"], **sig,
        json_firstyear=y0, json_lastyear=y1,
        csv_data_lines=int(csv_lines), csv_tail=tail_kind,
        csv_tail_text=(stats.get("tail", b"")[:300].decode(errors="replace")
                       if tail_kind == "partial" else ""),
        parquet_rows=rb["rows_disk"], rows_written=yp.rows_written,
        dev_rows=rb["dev_rows_disk"], dev_cells=rb["dev_cells"],
        years_present_n=len(years_present),
        years_present=f"{years_present[0]}..{years_present[-1]}" if years_present else "",
        missing_years=ranges(missing_years), extra_years=ranges(extra_years),
        n_missing_blocks_expected_grid=int(miss.height),
        n_missing_blocks_in_present_years=n_miss_in_present,
        missing_blocks_in_present_years={str(y): ranges(c) for y, c in miss_in_present.items()},
        cells_missing_in_present_years=ranges(cells_missing_in_present),
        cells_absent_all_years=ranges(absent_all), n_cells_absent_all_years=len(absent_all),
        absent_equals_rock_cells=absent_all == rock, rock_cells=ranges(rock),
        n_census_holes=int(holes.height), census_holes_by_year=holes_by_year,
        cells_per_present_year_min=int(census.group_by("Year").agg(n=pl.len())["n"].min()),
        cells_with_trees_per_year_min=int(tree_cells["n"].min()) if tree_cells.height else 0,
        cells_with_trees_per_year_max=int(tree_cells["n"].max()) if tree_cells.height else 0,
        tree_rows=int(py["tree_rows"].sum()),
        tree_live_rows=int(census["n_tree_live"].sum()),
        tree_dup_excess=dup_total, tree_dup_excess_disk=rb["tree_dup_excess_disk"],
        tree_dup_keys=int(py["n_dup_keys"].sum()),
        tree_dup_keys_distinct=int(n_dup_distinct),
        tree_dup_types=dupk.group_by("Type").agg(n=pl.len()).sort("Type").rows() if dupk.height
        else [],
        tree_dup_excess_traitkey=int(py["dup_excess_traitkey"].sum()),
        tree_dup_examples=yp.dup_examples[:20],
        null_total=null_total,
        tree_height_nonfinite=int(py["height_nonfinite"].sum()),
        tree_agb_nonfinite=int(py["agb_nonfinite"].sum()),
        tree_height_lt5=int(py["height_lt5"].sum()),
        tree_height_eq5=int(py["height_eq5"].sum()),
        isdead_bad=int(py["isdead_bad"].sum()),
        isdead_grass=int(py["isdead_grass"].sum()),
        cell_bad=int(py["cell_bad"].sum()), patch_bad=int(py["patch_bad"].sum()),
        type_bad=int(py["type_bad"].sum()), year_bad=int(py["year_bad"].sum()),
        id_neg=int(py["id_neg"].sum()),
        nonfinite_by_col={c: v for c, v in yp.nonfinite_all.items() if v},
        mort_bad_first_year=int(py.filter(pl.col("Year") == y0)["mort_bad"].sum()),
        mort_bad_other_years=int(py.filter(pl.col("Year") != y0)["mort_bad"].sum()),
        mort_absmax_first_year=float(py.filter(pl.col("Year") == y0)["mort_absmax"].max() or 0),
        year_order_viol=year_order_viol,
        within_year_order_viol=int(py["order_viol"].sum()),
        readback=rb,
        per_year=yp.per_year,
        wall_pass_s=round(t_pass, 1), wall_total_s=round(time.time() - t_start, 1),
        read_wait_s=round(stats["read_wait_s"], 1), parse_s=round(parse_s, 1),
        gb_per_s=round(sig["src_bytes"] / 1e9 / t_pass, 3),
        host=socket.gethostname(), job=job, threads=nthreads,
        finished=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
    # the conversion is faithful iff every complete CSV line is on disk, read back identically
    g["conversion_ok"] = bool(
        rb["ok"] and g["parquet_rows"] == csv_lines == yp.rows_written and null_total == 0
        and rb["tree_dup_excess_disk"] == dup_total)
    checks = dict(
        rows=g["parquet_rows"] == csv_lines,
        tail=tail_kind in ("none", "complete-unterminated"),
        years=not missing_years and not extra_years,
        census=holes.height == 0 and absent_all == rock,
        unique=dup_total == 0 and rb["tree_dup_excess_disk"] == 0,
        sanity=(null_total == 0 and g["tree_height_nonfinite"] == 0
                and g["tree_agb_nonfinite"] == 0 and g["isdead_bad"] == 0
                and g["cell_bad"] == 0 and g["patch_bad"] == 0 and g["type_bad"] == 0
                and g["year_bad"] == 0),
        order=year_order_viol == 0,
        readback=rb["ok"],
    )
    g["checks"] = checks
    g["gate_pass"] = bool(all(checks.values()))
    # same gate with the individual key extended by the two immutable traits (SLA, Wooddens):
    # the raw (Cell, Patch, Type, ID) key is NOT unique in this output (see README), this is the
    # key that is
    ck2 = dict(checks, unique=int(py["dup_excess_traitkey"].sum()) == 0)
    g["gate_pass_traitkey"] = bool(all(ck2.values()))
    g["failed_checks"] = [k for k, v in checks.items() if not v]
    log(f"  GATES: pass={g['gate_pass']} conversion_ok={g['conversion_ok']} "
        f"failed={g['failed_checks']}")

    if not g["conversion_ok"]:
        os.makedirs(GATE_DIR, exist_ok=True)
        with open(m["gate_json"] + ".failed", "w") as f:
            json.dump(g, f, indent=1, default=str)
        log("  conversion NOT ok: staging kept for inspection, final not replaced")
        return 3
    # finalize: census, then atomically swap staging -> final
    os.makedirs(CENSUS_DIR, exist_ok=True)
    census.write_parquet(m["census_file"] + ".tmp")
    os.replace(m["census_file"] + ".tmp", m["census_file"])
    os.makedirs(DUPKEY_DIR, exist_ok=True)
    dupk.write_parquet(f"{DUPKEY_DIR}/{m['member']}.parquet")
    if os.path.exists(m["out_dir"]):
        shutil.rmtree(m["out_dir"])
    os.replace(stage_dir, m["out_dir"])
    os.makedirs(DEV_ROOT, exist_ok=True)
    os.replace(stage_dev, m["dev_file"])
    shutil.rmtree(os.path.dirname(stage_dev), ignore_errors=True)
    os.makedirs(GATE_DIR, exist_ok=True)
    with open(m["gate_json"] + ".tmp", "w") as f:
        json.dump(g, f, indent=1, default=str)
    os.replace(m["gate_json"] + ".tmp", m["gate_json"])
    try:
        os.remove(m["gate_json"] + ".failed")
    except OSError:
        pass
    collect()
    log(f"  DONE {m['member']}: {g['parquet_rows']:,} rows, "
        f"{rb['out_bytes'] / 1e9:.1f} GB + dev {rb['dev_bytes'] / 1e9:.2f} GB, "
        f"wall {g['wall_total_s']:.0f}s")
    return 0


# ------------------------------------------------------------------------------------------------
# collect / list / submit
# ------------------------------------------------------------------------------------------------
FLAT = [
    "idx", "member", "gcm", "scen", "seed", "window", "gate_pass", "conversion_ok",
    "failed_checks", "json_firstyear", "json_lastyear", "years_present", "years_present_n",
    "missing_years", "csv_data_lines", "parquet_rows", "dev_rows", "dev_cells", "csv_tail",
    "n_missing_blocks_expected_grid", "n_missing_blocks_in_present_years",
    "cells_missing_in_present_years", "n_census_holes", "n_cells_absent_all_years",
    "cells_absent_all_years", "absent_equals_rock_cells", "cells_per_present_year_min",
    "cells_with_trees_per_year_min", "cells_with_trees_per_year_max", "tree_rows",
    "tree_live_rows", "tree_dup_excess", "tree_dup_excess_disk", "tree_dup_keys",
    "tree_dup_excess_traitkey", "null_total",
    "tree_height_nonfinite", "tree_agb_nonfinite", "tree_height_lt5", "tree_height_eq5",
    "isdead_bad", "gate_pass_traitkey", "tree_dup_keys_distinct",
    "nonfinite_by_col", "mort_bad_first_year", "mort_bad_other_years", "year_order_viol",
    "within_year_order_viol", "src_bytes", "out_bytes", "dev_bytes", "wall_pass_s",
    "wall_total_s", "read_wait_s", "parse_s", "gb_per_s", "host", "job", "finished",
]


def collect() -> None:
    os.makedirs(OUT_ROOT, exist_ok=True)
    lock = open(f"{OUT_ROOT}/.gates.lock", "w")
    fcntl.flock(lock, fcntl.LOCK_EX)
    try:
        rows = []
        for m in manifest():
            for path, status in ((m["gate_json"], "done"), (m["gate_json"] + ".failed",
                                                            "conversion_failed")):
                if os.path.isfile(path):
                    g = json.load(open(path))
                    g["out_bytes"] = g.get("readback", {}).get("out_bytes")
                    g["dev_bytes"] = g.get("readback", {}).get("dev_bytes")
                    r = {k: g.get(k) for k in FLAT}
                    r["status"] = status
                    for k in ("failed_checks", "nonfinite_by_col"):
                        r[k] = json.dumps(r[k])
                    rows.append(r)
                    break
            else:
                rows.append({"idx": m["idx"], "member": m["member"], "gcm": m["gcm"],
                             "scen": m["scen"], "seed": m["seed"], "window": m["window"],
                             "status": "not_done"})
        df = pl.DataFrame(rows, infer_schema_length=None)
        df.write_csv(GATES_CSV + ".tmp")
        os.replace(GATES_CSV + ".tmp", GATES_CSV)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def submit(args: list[str]) -> int:
    array = args[0]
    part = args[1] if len(args) > 1 else "standard"
    qos = args[2] if len(args) > 2 else "short"
    ncpus = int(args[3]) if len(args) > 3 else 16
    tlim = args[4] if len(args) > 4 else "03:00:00"
    exclude = args[5] if len(args) > 5 else ""
    os.makedirs(LOGDIR, exist_ok=True)
    jdir = "/p/tmp/jamirp/X_de/_jobs"
    os.makedirs(jdir, exist_ok=True)
    jcf = f"{jdir}/deconv_{time.strftime('%Y%m%d_%H%M%S')}.jcf"
    exc = f"#SBATCH --exclude={exclude}\n" if exclude else ""
    body = f"""#!/usr/bin/env bash
#SBATCH --job-name=X-de-conv
#SBATCH --account=waldspektrum
#SBATCH --partition={part}
#SBATCH --qos={qos}
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task={ncpus}
#SBATCH --time={tlim}
#SBATCH --array={array}
#SBATCH --output={LOGDIR}/X-de-conv.%A_%a.out
#SBATCH --error={LOGDIR}/X-de-conv.%A_%a.out
{exc}set -uo pipefail
export POLARS_MAX_THREADS={ncpus}
export OMP_NUM_THREADS={ncpus}
echo "=== X-de-conv task $SLURM_ARRAY_TASK_ID on $(hostname) at $(date) ==="
{PY} {os.path.abspath(__file__)} run $SLURM_ARRAY_TASK_ID
code=$?
echo "=== JOB DONE tag=X-de-conv task=$SLURM_ARRAY_TASK_ID exit=$code ==="
exit $code
"""
    with open(jcf, "w") as f:
        f.write(body)
    out = subprocess.run(["sbatch", jcf], capture_output=True, text=True)
    print(out.stdout.strip(), out.stderr.strip())
    print(f"jcf: {jcf}")
    return out.returncode


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "list":
        for m in manifest():
            print(m["idx"], m["member"], m["src"])
        return 0
    if cmd == "run":
        return run(int(sys.argv[2]))
    if cmd == "collect":
        collect()
        print(GATES_CSV)
        return 0
    if cmd == "submit":
        return submit(sys.argv[2:])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
