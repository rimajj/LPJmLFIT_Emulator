#!/usr/bin/env python3
"""build_slow_validation_report.py — assemble the Component-S global validation figure set into ONE
self-contained HTML report (every image inlined as a data URI, no external requests).

WHY: `plot_slow_emulator_validation.py` writes per-scenario figure dirs under
`figures/emulator_validation/<scen>/` which are git-ignored (regenerable, avoids binary churn), so the
figures live only on the cluster filesystem. This script turns a set of those dirs into ONE page that can
be read anywhere — and, because every asset is inlined, it is also directly publishable as an Artifact
(hence the deliberate `<title>` + `<style>` fragment form: no `<html>`/`<body>` wrapper, which the
Artifact publisher supplies; browsers render the fragment fine on its own).

It is a REPORTER, not a metric: every number it shows is read verbatim from the `metrics*.txt` files the
plot script wrote. It adds no analysis of its own, so it can never disagree with the figures.

Env:
  SCENARIOS  comma-list of figure-dir names under FIGROOT, `label=dirname` accepted
             (default: historic_t8,ssp370_t8,pooled_t8)
  FIGROOT    default figures/emulator_validation
  OUT        default <FIGROOT>/report.html
  MAXWIDTH   px; images wider than this are downscaled with PIL before inlining (default 1500)
  TITLE      page title
  GENERATION the artifact generation tag quoted in the header prose (default t8)

Run:  SCENARIOS=historic_t8,ssp370_t8 OUT=/p/tmp/jamirp/report_t8.html \
        /home/jamirp/.conda/envs/py311_new/bin/python scripts/build_slow_validation_report.py
"""

from __future__ import annotations

import base64
import html
import io
import os
from pathlib import Path

from PIL import Image

FIG_ORDER = [
    "01_map_observed",
    "02_map_predicted",
    "03_map_bias",
    "04_scatter_density",
    "05_scatter_percell",
    "06_distribution",
    "07_error_by_latitude",
    "08_error_by_gdd5",
    "09_trait_marginals",
    "10_trait_percell_median",
    "11_trait_ks_map",
    "12_biomass_percell",
    "13_map_biomass",
]

#: Every caption states WHAT is plotted and HOW to read it — the figures are quoted in reviews, and an
#: unlabelled panel invites the "it looks totally off" misread that fig 10 already caused once
#: (emulator-validation-figures skill).
CAPTIONS = {
    "01_map_observed": ("Observed tree density — LPJmL-FIT truth", "Cell-mean n_living (stems per patch, "
                        "stems >5 m only — the population the C `ind` writer emits), averaged over patches and years."),
    "02_map_predicted": ("Predicted tree density — out-of-sample", "Same colour scale as fig 01. Every cell is "
                         "predicted by forests that never trained on it (K-fold BY CELL), so this is generalization, "
                         "not fit."),
    "03_map_bias": ("Bias (predicted − observed)", "Symmetric diverging scale, robust (98th-percentile) limits."),
    "04_scatter_density": ("Per-row prediction density", "One point per (cell, patch, year) row, log-density hexbin, "
                           "1:1 dashed. R²/RMSE are the OOS per-row numbers."),
    "05_scatter_percell": ("Per-cell means", "One point per cell. The per-cell-mean R² is the number to quote for "
                           "a map-scale claim."),
    "06_distribution": ("Count distribution", "Observed vs predicted n_living histogram (log density). "
                        "Read this one carefully: the count DRF is scored with <code>DRF.predict</code>, a "
                        "CONDITIONAL MEAN (a convex combination of training leaf means), not a random draw — "
                        "so the predicted histogram is narrower than the observed one <em>by construction</em> "
                        "and that narrowing is not a distributional failure. The distributional claims in this "
                        "report are the copula ones (figs 09–11), which do draw per stem."),
    "07_error_by_latitude": ("Skill by latitude", "Where the count emulator works and where it does not."),
    "08_error_by_gdd5": ("Skill by growing-degree-days", "The ecological gradient version of fig 07."),
    "09_trait_marginals": ("Trait + structure marginals, pooled", "Per axis: the LPJmL-FIT survivor marginal vs the "
                           "OOS copula draws. `nqrmse` is IQR-normalised, so never compare it across populations "
                           "without checking the IQR moved. Axes marked [diagnostic] are the structure axes "
                           "(biomass, height) — validated, but never written into the production artifact."),
    "10_trait_percell_median": ("Per-cell median, observed vs predicted", "The between-cell COMPOSITION test — a "
                                "good pooled marginal (fig 09) can coexist with per-cell medians regressed to the "
                                "global mean. Density-coloured on purpose: tens of thousands of cells saturate a "
                                "plain scatter and hide the diagonal."),
    "11_trait_ks_map": ("Per-cell KS statistic", "Where each cell's whole distribution is reproduced (dark = good). "
                        "Cells with <20 stems are blank."),
    "12_biomass_percell": ("Stand biomass, observed vs predicted (+ basis cross-check)", "Left: per-cell mean stand "
                           "AGB, predicted as (count-DRF OOS stems) × (copula OOS per-stem biomass) — a COMPOSITE of "
                           "the emulator's two halves, each out-of-sample. Right: the basis cross-check. That "
                           "product is an <em>exact identity</em> on matched rows (the per-stem mean is "
                           "stem-weighted), so the right panel is a ROW-UNIVERSE check — do the two tables cover "
                           "the same (cell, patch, year) rows? — not a statistical correction. It departs from 1 "
                           "because the count table drops each scenario's first year (it needs the AR state) and, "
                           "where stems were capped, because the cap keeps whole patch-year clusters."),
    "13_map_biomass": ("Stand biomass maps", "Observed / predicted / bias, gC m⁻² per patch."),
}

HEADLINE = [
    ("count", "oos_r2_perrow", "count OOS R² (per row)"),
    ("count", "percell_mean_r2", "count R² (per-cell mean)"),
    ("count", "mean_bias_percell", "count bias (stems/patch)"),
    ("count", "n_cells", "cells scored"),
    ("count", "n_rows", "rows scored"),
    ("biomass", "percell_r2", "biomass R² (per-cell, linear)"),
    ("biomass", "percell_r2_log10", "biomass R² (per-cell, log₁₀)"),
    ("biomass", "median_ratio", "biomass median pred:obs"),
    ("biomass", "basis_ratio", "biomass basis cross-check"),
]

CSS = """
:root { --fg:#1a1a1a; --mut:#5b6672; --bg:#ffffff; --card:#f6f7f9; --line:#dfe3e8; --acc:#2f6f9f; }
@media (prefers-color-scheme: dark) {
  :root { --fg:#e8e9eb; --mut:#a3adb8; --bg:#14161a; --card:#1c1f25; --line:#2c313a; --acc:#7fb2dc; }
}
:root[data-theme="dark"] { --fg:#e8e9eb; --mut:#a3adb8; --bg:#14161a; --card:#1c1f25; --line:#2c313a; --acc:#7fb2dc; }
:root[data-theme="light"] { --fg:#1a1a1a; --mut:#5b6672; --bg:#ffffff; --card:#f6f7f9; --line:#dfe3e8; --acc:#2f6f9f; }
* { box-sizing:border-box; }
body { margin:0; padding:2rem 1.25rem 4rem; background:var(--bg); color:var(--fg);
  font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; }
.wrap { max-width:1120px; margin:0 auto; }
h1 { font-size:1.7rem; line-height:1.25; margin:0 0 .4rem; letter-spacing:-.01em; }
h2 { font-size:1.25rem; margin:2.6rem 0 .6rem; padding-bottom:.35rem; border-bottom:1px solid var(--line); }
h3 { font-size:1.02rem; margin:1.8rem 0 .3rem; }
p, li { color:var(--fg); }
.sub { color:var(--mut); margin:0 0 1.6rem; }
.note { background:var(--card); border-left:3px solid var(--acc); padding:.8rem 1rem; border-radius:0 6px 6px 0;
  margin:1.2rem 0; font-size:.94rem; }
.cap { color:var(--mut); font-size:.9rem; margin:.15rem 0 1.4rem; }
figure { margin:0 0 .2rem; }
img { max-width:100%; height:auto; display:block; border:1px solid var(--line); border-radius:6px; background:#fff; }
.tablewrap { overflow-x:auto; margin:1rem 0 1.6rem; }
table { border-collapse:collapse; font-size:.9rem; min-width:100%; }
th, td { text-align:right; padding:.42rem .7rem; border-bottom:1px solid var(--line); white-space:nowrap; }
th:first-child, td:first-child { text-align:left; }
thead th { color:var(--mut); font-weight:600; }
tbody tr:hover { background:var(--card); }
code { background:var(--card); padding:.1rem .3rem; border-radius:3px; font-size:.88em; }
.miss { color:var(--mut); font-style:italic; }
footer { margin-top:3rem; color:var(--mut); font-size:.85rem; border-top:1px solid var(--line); padding-top:1rem; }
"""


def read_kv(path: Path) -> dict[str, str]:
    """Parse a `key\\tvalue` metrics file (metrics.txt / metrics_biomass.txt)."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text().splitlines():
        parts = line.rstrip("\n").split("\t")
        if len(parts) >= 2:
            out[parts[0]] = parts[1]
    return out


def read_traits(path: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Parse metrics_traits.txt: `scenario`/`axes` header lines then one multi-field line per axis."""
    per_axis: dict[str, dict[str, str]] = {}
    order: list[str] = []
    if not path.is_file():
        return per_axis, order
    for line in path.read_text().splitlines():
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 3 or parts[0] in ("scenario", "axes", "struct_axes"):
            continue
        axis = parts[0]
        # strict=False on purpose: a reporter must not crash on a metrics line that grew an unpaired trailing
        # field — it drops that field and still shows every complete one.
        fields = dict(zip(parts[1::2], parts[2::2], strict=False))
        per_axis[axis] = fields
        order.append(axis)
    return per_axis, order


def inline_png(path: Path, maxwidth: int) -> str:
    """Return a data URI for `path`, downscaled to `maxwidth` px if wider (keeps the page a few MB)."""
    with Image.open(path) as im:
        im.load()
        if im.width > maxwidth:
            h = round(im.height * maxwidth / im.width)
            im = im.resize((maxwidth, h), Image.LANCZOS)
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def fmt(v: str) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return html.escape(str(v))
    if f == int(f) and abs(f) >= 1000:
        return f"{int(f):,}"
    return f"{f:.4g}"


def main() -> int:
    figroot = Path(os.environ.get("FIGROOT", os.path.join("figures", "emulator_validation")))
    spec = os.environ.get("SCENARIOS", "historic_t8,ssp370_t8,pooled_t8")
    gen = os.environ.get("GENERATION", "t8")
    title = os.environ.get("TITLE", f"Component-S global validation — {gen}")
    out = Path(os.environ.get("OUT", figroot / "report.html"))
    maxwidth = int(os.environ.get("MAXWIDTH", "1500"))

    scens: list[tuple[str, Path]] = []
    for tok in [t.strip() for t in spec.split(",") if t.strip()]:
        label, _, dirname = tok.partition("=")
        d = figroot / (dirname or label)
        if not d.is_dir():
            print(f"== SKIP {label}: {d} does not exist")
            continue
        scens.append((label, d))
    if not scens:
        raise SystemExit(f"FATAL: none of the requested figure dirs exist under {figroot} ({spec})")

    parsed = []
    for label, d in scens:
        m_count = read_kv(d / "metrics.txt")
        m_bio = read_kv(d / "metrics_biomass.txt")
        traits, axorder = read_traits(d / "metrics_traits.txt")
        parsed.append((label, d, {"count": m_count, "biomass": m_bio}, traits, axorder))
        print(f"== {label}: {d} — count keys {len(m_count)}, biomass keys {len(m_bio)}, axes {len(axorder)}")

    h: list[str] = [f"<title>{html.escape(title)}</title>", f"<style>{CSS}</style>", '<div class="wrap">']
    h.append(f"<h1>{html.escape(title)}</h1>")
    h.append(
        '<p class="sub">How closely the global Component-S slow emulator reproduces LPJmL-FIT — tree '
        "counts, per-cell trait distributions and stand biomass — from <strong>out-of-sample</strong> "
        "predictions (K-fold <em>by cell</em>: every cell is predicted by forests that never trained on "
        "it).</p>"
    )
    h.append(
        '<div class="note"><strong>What is being compared.</strong> These are <em>offline</em> '
        "table-vs-table measurements: the emulator is fed LPJmL-FIT's own annual drivers and its "
        "prediction is scored against LPJmL-FIT's own stems. That is the right test of the learned "
        "mapping, and it is <em>not</em> a coupled-run test — a recursive S+F+E trajectory can drift for "
        "reasons no offline number here would show. Population: all seven of LPJmL-FIT's tree PFTs "
        "(<code>Type ≤ 6</code>), stems above the C writer's 5 m emission threshold.</div>"
    )

    # ---------------- headline table ----------------
    h.append("<h2>Headline numbers</h2>")
    h.append('<div class="tablewrap"><table><thead><tr><th>quantity</th>')
    for label, *_ in parsed:
        h.append(f"<th>{html.escape(label)}</th>")
    h.append("</tr></thead><tbody>")
    for group, key, pretty in HEADLINE:
        h.append(f"<tr><td>{html.escape(pretty)}</td>")
        for _, _, mets, _, _ in parsed:
            v = mets[group].get(key)
            h.append(f"<td>{fmt(v) if v is not None else '<span class=miss>—</span>'}</td>")
        h.append("</tr>")
    h.append("</tbody></table></div>")

    # ---------------- per-axis distribution table ----------------
    if any(ax for *_, ax in parsed):
        h.append("<h2>Per-axis distribution fidelity</h2>")
        h.append(
            '<p class="cap">Per axis: the pooled marginal error (<code>nqrmse</code>, IQR-normalised), the '
            "pooled and median-per-cell KS statistics, and the per-cell-median correlation — the "
            "between-cell <em>composition</em> skill, which a pooled marginal is blind to. "
            "<strong>On a heavy-tailed axis read <code>median_rel_q_err</code> and <code>pooled_KS</code>, not "
            "<code>nqrmse</code></strong>: <code>nqrmse</code> divides every quantile error by one IQR, so for "
            "per-stem biomass (IQR ≈ 25, q95 ≈ 3300 gC m⁻²) the q95 term alone contributes ≈10 and the metric "
            "reads ≈0.75 while every quantile is in fact within a few percent.</p>"
        )
        for label, _, _, traits, axorder in parsed:
            if not axorder:
                continue
            h.append(f"<h3>{html.escape(label)}</h3>")
            cols = ["pooled_nqrmse", "median_rel_q_err", "pooled_KS", "median_percell_KS", "median_percell_r",
                    "median_percell_spearman", "n_cells"]
            h.append('<div class="tablewrap"><table><thead><tr><th>axis</th>')
            for c in cols:
                h.append(f"<th>{html.escape(c)}</th>")
            h.append("</tr></thead><tbody>")
            for ax in axorder:
                kind = traits[ax].get("kind", "")
                tag = " [diagnostic]" if kind.startswith("struct") else ""
                h.append(f"<tr><td>{html.escape(ax)}{tag}</td>")
                for c in cols:
                    v = traits[ax].get(c)
                    h.append(f"<td>{fmt(v) if v is not None else '<span class=miss>—</span>'}</td>")
                h.append("</tr>")
            h.append("</tbody></table></div>")

    # ---------------- figures ----------------
    for label, d, mets, _, _ in parsed:
        h.append(f"<h2>{html.escape(label)}</h2>")
        bio = mets["biomass"]
        if bio.get("basis_ok") == "no":
            h.append(
                '<div class="note"><strong>Basis cross-check did not pass for this scenario</strong> '
                f"(<code>basis_ratio = {html.escape(bio.get('basis_ratio', '?'))}</code>). The composite "
                "biomass number below is therefore a diagnostic, not a fidelity claim — read fig 12's "
                "right-hand panel before quoting it.</div>"
            )
        shown = 0
        for stem in FIG_ORDER:
            p = d / f"{stem}.png"
            if not p.is_file():
                continue
            head, cap = CAPTIONS.get(stem, (stem, ""))
            h.append(f"<h3>{html.escape(head)}</h3>")
            h.append(f'<figure><img alt="{html.escape(head)}" src="{inline_png(p, maxwidth)}"></figure>')
            h.append(f'<p class="cap">{cap}</p>')
            shown += 1
        if not shown:
            h.append('<p class="miss">no figures found in this directory</p>')
        print(f"== {label}: inlined {shown} figures")

    h.append(
        "<footer>Generated by <code>scripts/build_slow_validation_report.py</code> from the figure dirs "
        f"written by <code>scripts/plot_slow_emulator_validation.py</code> (generation <code>{html.escape(gen)}</code>). "
        "Every number is read verbatim from the <code>metrics*.txt</code> files; this page computes none of "
        "its own.</footer></div>"
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(h))
    print(f"== wrote {out} ({out.stat().st_size / 1e6:.2f} MB, {len(parsed)} scenarios)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
