"""Shared figure style for the emulator paper (docs/paper). One palette, one type size, one export path.

Colour roles (validated reference palette of the dataviz method, light mode):
  ORIG   the original model LPJmL-FIT (the truth run)        near-black
  EMU    the learned emulator                                blue
  SECOND a second run of the original (the yardstick)        orange
  NULL1  first null / reference arm                          aqua
  NULL2  second null / reference arm                         violet
  MUTED  grid, thresholds, annotations                       grey
"""

import os

import matplotlib as mpl
import matplotlib.pyplot as plt

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIGDIR = os.path.join(REPO, "docs", "paper", "figs")
DATA = "/p/projects/open/Jamir/esm_land_emulator_data"

ORIG = "#222220"
EMU = "#2a78d6"
SECOND = "#eb6834"
NULL1 = "#1baf7a"
NULL2 = "#6250d6"
YELLOW = "#eda100"
RED = "#e34948"
MUTED = "#8a8984"
GRID = "#e4e3df"
INK2 = "#52514e"
BLUES = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]
DIV_NEG, DIV_MID, DIV_POS = "#2a78d6", "#f0efec", "#e34948"

FULL = 6.6   # in, full text width
HALF = 3.2


def setup():
    mpl.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 7.5,
        "axes.titlesize": 8,
        "axes.labelsize": 7.5,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "axes.linewidth": 0.6,
        "axes.edgecolor": INK2,
        "axes.labelcolor": ORIG,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.5,
        "axes.axisbelow": True,
        "legend.frameon": False,
        "lines.linewidth": 1.4,
        "savefig.dpi": 300,
        "figure.dpi": 150,
        "pdf.fonttype": 42,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
    })


def panel(ax, letter, title=None):
    """Bold panel letter + optional title, left-aligned above the axes."""
    t = f"({letter})" if title is None else f"({letter}) {title}"
    ax.set_title(t, loc="left", fontsize=8, fontweight="bold", color=ORIG, pad=4)


def save(fig, name):
    os.makedirs(FIGDIR, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(FIGDIR, f"{name}.{ext}"), bbox_inches="tight", pad_inches=0.03)
    plt.close(fig)
    print("wrote", os.path.join(FIGDIR, name + ".pdf"), flush=True)
