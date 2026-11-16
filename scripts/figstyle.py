"""House figure style adapted from streetscope so plots match across papers."""

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

ACCENT = "#800000"
BAR_GRAY = "0.45"
BAND_GRAY = "0.88"
TEXT_GRAY = "0.25"

ACCENT_CMAP = LinearSegmentedColormap.from_list("accent_seq", ["#f7f0f0", ACCENT])

RC = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 8,
    "axes.linewidth": 0.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.08,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
}


def apply_style() -> None:
    plt.rcParams.update(RC)
