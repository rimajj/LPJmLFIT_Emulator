#!/usr/bin/env python3
"""fetch_plumber2_sites.py — download the PLUMBER2 (v1-0) site set that Component E is validated against.

WHY (line E, milestone E1):
  Component E's LE / H / T_skin are currently `[ASSUMPTION]` — "physically plausible but invented
  quantities validated only out-of-model". The whole line exists to turn that into `[VERIFIED]` against
  observations. PLUMBER2 (Ukkola et al. 2022, ESSD 14, 449) is the ~170-site quality-controlled,
  gap-filled, energy-flux-complete FLUXNET/OzFlux/LaThuile subset built exactly for land-model
  benchmarking, so it is preferred over raw FLUXNET2015 (see ADR 0070).

ACCESS [VERIFIED 2026-07-28]: the NCI THREDDS `ks32` collection serves PLUMBER2 v1-0 **anonymously** over
  plain HTTPS — no registration, no token, and it is reachable from the PIK login node (unlike GitHub
  HTTPS). Per-site payload ~11 MB (Flux) + ~4.5 MB (Met), half-hourly.
    catalog:    https://thredds.nci.org.au/thredds/catalog/ks32/CLEX_Data/PLUMBER2/v1-0/Flux/catalog.html
    fileServer: https://thredds.nci.org.au/thredds/fileServer/ks32/CLEX_Data/PLUMBER2/v1-0/{Flux,Met}/<stem>_{Flux,Met}.nc

SITE SET: DE-Hai (the prototype cell Hainich) + one site per remaining biome of the 5-biome coupled test
  (`test/testitems/biome_coupled_tests.jl`: boreal / temperate / mediterranean / semi-arid / tropical).
  The mapping is an INTENT label, not a claim that the tower sits in the model cell — site coordinates are
  read from the NetCDF by the loader (`validate_e_plumber2_load.py`), never hard-coded here.

Idempotent: an existing file whose size matches the server's Content-Length is kept (re-hashed only if the
  manifest lacks it). Writes `manifest.json` next to the data so the loader is self-describing.

Env:
  OUT     destination dir            (default: resolved from config/paths.yaml `data.energy_reference`)
  SITES   comma-separated site ids    (default: all of SITES below; e.g. SITES=DE-Hai)
  FORCE   1 = re-download everything  (default 0)
Usage:
  /home/jamirp/.conda/envs/py311_new/bin/python3 scripts/fetch_plumber2_sites.py
  SITES=DE-Hai python3 scripts/fetch_plumber2_sites.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://thredds.nci.org.au/thredds/fileServer/ks32/CLEX_Data/PLUMBER2/v1-0"

# site id -> (PLUMBER2 file stem, biome slot in biome_coupled_tests.jl, short note)
SITES: dict[str, tuple[str, str, str]] = {
    "DE-Hai": (
        "DE-Hai_2000-2012_FLUXNET2015",
        "temperate_hainich",
        "Hainich, temperate deciduous broadleaf — THE prototype cell (orderA 42490)",
    ),
    "FI-Hyy": (
        "FI-Hyy_1996-2014_FLUXNET2015",
        "boreal_siberia",
        "Hyytiala, boreal evergreen needleleaf",
    ),
    "FR-Pue": (
        "FR-Pue_2000-2014_FLUXNET2015",
        "mediterranean_iberia",
        "Puechabon, Mediterranean evergreen broadleaf (Quercus ilex)",
    ),
    "US-SRM": (
        "US-SRM_2004-2014_FLUXNET2015",
        "semiarid_sahel",
        "Santa Rita Mesquite, semi-arid woody savanna",
    ),
    "AU-How": (
        "AU-How_2003-2017_OzFlux",
        "semiarid_sahel",
        "Howard Springs, wet-dry tropical savanna (the closer Sahel seasonality analogue)",
    ),
    "GF-Guy": (
        "GF-Guy_2004-2014_FLUXNET2015",
        "tropical_amazon",
        "Guyaflux, tropical evergreen rainforest",
    ),
    # --- the T_skin-capable subset -------------------------------------------------------------
    # [VERIFIED 2026-07-28] PLUMBER2's FLUXNET2015-sourced files carry NO upwelling longwave, so
    # T_skin is NOT derivable at DE-Hai. The OzFlux-sourced files DO carry `LWup` => T_skin via an
    # inverted Stefan-Boltzmann. These three add an LWup site in the temperate-forest, tropical-forest
    # and arid slots (there is no boreal OzFlux site — boreal T_skin stays unsourced; see ADR 0070).
    "AU-Tum": (
        "AU-Tum_2002-2017_OzFlux",
        "temperate_hainich",
        "Tumbarumba, temperate wet evergreen eucalypt forest — LWup present (T_skin)",
    ),
    "AU-Rob": (
        "AU-Rob_2014-2017_OzFlux",
        "tropical_amazon",
        "Robson Creek, tropical rainforest — LWup present (T_skin)",
    ),
    "AU-ASM": (
        "AU-ASM_2011-2017_OzFlux",
        "semiarid_sahel",
        "Alice Springs Mulga, arid woodland — LWup present (T_skin)",
    ),
}

REPO_ROOT = Path(__file__).resolve().parents[1]


def resolve_paths_yaml(key: str) -> str:
    """Return config/paths.yaml value for a dotted key, expanding ${a.b} references.

    Deliberately a 20-line reader instead of a PyYAML dependency: this script must run under any
    interpreter on the cluster (paths.yaml is plain nested mappings of scalars).
    """
    text = (REPO_ROOT / "config" / "paths.yaml").read_text()
    flat: dict[str, str] = {}
    stack: list[tuple[int, str]] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        m = re.match(r"^\s*([A-Za-z0-9_]+):\s*(.*)$", line)
        if not m:
            continue
        name, value = m.group(1), m.group(2).strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        dotted = ".".join([p for _, p in stack] + [name])
        if value:
            flat[dotted] = value
        else:
            stack.append((indent, name))
    if key not in flat:
        raise KeyError(f"{key} not found in config/paths.yaml")

    def expand(v: str, depth: int = 0) -> str:
        if depth > 8:
            raise RuntimeError(f"cyclic ${{}} reference while expanding {v!r}")
        return re.sub(
            r"\$\{([A-Za-z0-9_.]+)\}", lambda m: expand(flat[m.group(1)], depth + 1), v
        )

    return expand(flat[key])


def sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def remote_size(url: str) -> int | None:
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            n = resp.headers.get("Content-Length")
            return int(n) if n else None
    except urllib.error.URLError as exc:  # network hiccup -> fall back to unconditional download
        print(f"  ! HEAD failed ({exc}); will download unconditionally", flush=True)
        return None


def download(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=600) as resp, tmp.open("wb") as out:
        while True:
            block = resp.read(1 << 20)
            if not block:
                break
            out.write(block)
    tmp.replace(dest)


def main() -> int:
    out_root = Path(os.environ.get("OUT") or resolve_paths_yaml("data.energy_reference"))
    force = os.environ.get("FORCE", "0") == "1"
    wanted = [s.strip() for s in os.environ.get("SITES", "").split(",") if s.strip()] or list(SITES)
    unknown = [s for s in wanted if s not in SITES]
    if unknown:
        print(f"unknown site id(s): {unknown}; known: {list(SITES)}", file=sys.stderr)
        return 2

    print(f"PLUMBER2 v1-0 -> {out_root}")
    manifest_path = out_root / "manifest.json"
    manifest: dict = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    entries: dict[str, dict] = manifest.get("sites", {})

    for site in wanted:
        stem, biome, note = SITES[site]
        print(f"\n[{site}] {note}  (biome slot: {biome})")
        files: dict[str, dict] = {}
        for kind in ("Flux", "Met"):
            rel = f"{kind}/{stem}_{kind}.nc"
            dest = out_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            url = f"{BASE_URL}/{rel}"
            want = remote_size(url)
            have = dest.stat().st_size if dest.exists() else -1
            if force or have < 0 or (want is not None and have != want):
                print(f"  fetch {rel}  ({want if want else '?'} B)")
                download(url, dest)
            else:
                print(f"  keep  {rel}  ({have} B, matches server)")
            files[kind] = {
                "path": str(dest),
                "url": url,
                "bytes": dest.stat().st_size,
                "sha256": sha256(dest),
            }
        entries[site] = {"stem": stem, "biome_slot": biome, "note": note, "files": files}

    out_root.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "dataset": "PLUMBER2 v1-0 (Ukkola et al. 2022, ESSD 14, 449; doi:10.25914/5fdb0902607e1)",
                "source": BASE_URL,
                "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "root": str(out_root),
                "sites": entries,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    total = sum(f["bytes"] for e in entries.values() for f in e["files"].values())
    print(f"\nmanifest: {manifest_path}  ({len(entries)} site(s), {total / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
