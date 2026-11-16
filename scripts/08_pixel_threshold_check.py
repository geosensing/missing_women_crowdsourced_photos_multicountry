"""Generate Appendix Table A1: empirical pixel-area threshold and regional bias check.

Joins outputs/muse_counts_round1.csv and outputs/selected_images.csv with
Mask2Former Person+Rider pixel counts from data/parquet/segmentation.parquet,
and writes tabs/tableA1_pixel_threshold.tex (Panel A: global threshold curve;
Panel B: regional pedestrian female share at pix >= 0 vs. pix >= 5,000).
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

HF_REPO = "NUS-UAL/global-streetscapes"
HF_SEG = "data/parquet/segmentation.parquet"
THRESHOLDS = [0, 1000, 2000, 5000, 10000, 20000]


def load_person_pixels(target_uuids: set[str]) -> dict[str, float]:
    """Load total Person+Rider pixel counts for target_uuids from segmentation.parquet."""
    try:
        path = hf_hub_download(
            repo_id=HF_REPO, filename=HF_SEG, repo_type="dataset", local_files_only=True
        )
    except Exception:
        path = hf_hub_download(repo_id=HF_REPO, filename=HF_SEG, repo_type="dataset")

    pf = pq.ParquetFile(path)
    pix: dict[str, float] = {}
    cols = ["uuid", "Person", "Bicyclist", "Motorcyclist", "Other-Rider"]
    for rg_idx in range(pf.num_row_groups):
        table = pf.read_row_group(rg_idx, columns=cols)
        uuids = table["uuid"].to_pylist()
        hits = [i for i, u in enumerate(uuids) if u in target_uuids]
        if hits:
            sub = table.take(hits).to_pydict()
            for idx, u in enumerate(sub["uuid"]):
                pix[u] = (
                    (sub["Person"][idx] or 0.0)
                    + (sub["Bicyclist"][idx] or 0.0)
                    + (sub["Motorcyclist"][idx] or 0.0)
                    + (sub["Other-Rider"][idx] or 0.0)
                )
    return pix


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts-csv", type=Path, default=Path("outputs/muse_counts_round1.csv"))
    parser.add_argument("--images-csv", type=Path, default=Path("outputs/selected_images.csv"))
    parser.add_argument(
        "--out", type=Path, default=Path("tabs/tableA1_pixel_threshold.tex")
    )
    args = parser.parse_args()

    with args.images_csv.open(newline="", encoding="utf-8") as handle:
        meta = {r["uuid"]: r for r in csv.DictReader(handle)}
    with args.counts_csv.open(newline="", encoding="utf-8") as handle:
        muse = {r["image"].rsplit(".", 1)[0]: r for r in csv.DictReader(handle)}

    pix = load_person_pixels(set(muse.keys()))
    total_imgs = len(muse)
    total_ped_all = sum(int(r["women_count"]) + int(r["men_count"]) for r in muse.values())

    panel_a_rows: list[str] = []
    for thresh in THRESHOLDS:
        sub = [r for u, r in muse.items() if pix.get(u, 0.0) >= thresh]
        w = sum(int(r["women_count"]) for r in sub)
        m = sum(int(r["men_count"]) for r in sub)
        unc = sum(int(r["unclear_count"]) for r in sub)
        ped = w + m
        share = (w / ped * 100) if ped > 0 else 0.0
        panel_a_rows.append(
            f"$\\ge {thresh:,}$ & {len(sub):,} ({len(sub)/total_imgs*100:.1f}\\%) & "
            f"{ped:,} ({ped/total_ped_all*100:.1f}\\%) & {unc:,} & {share:.2f}\\% \\\\"
        )

    reg_all: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    reg_5k: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for u, r in muse.items():
        reg = meta[u]["region"]
        w, m = int(r["women_count"]), int(r["men_count"])
        reg_all[reg][0] += w
        reg_all[reg][1] += m
        if pix.get(u, 0.0) >= 5000:
            reg_5k[reg][0] += w
            reg_5k[reg][1] += m

    short_reg = {
        "Middle East, North Africa, Afghanistan & Pakistan": "MENA, Afg. & Pak.",
    }
    panel_b_rows: list[str] = []
    for reg in sorted(reg_all):
        w0, m0 = reg_all[reg]
        w5, m5 = reg_5k[reg]
        s0 = w0 / (w0 + m0) * 100
        s5 = w5 / (w5 + m5) * 100
        reg_tex = short_reg.get(reg, reg).replace("&", "\\&")
        panel_b_rows.append(
            f"{reg_tex} & {s0:.2f}\\% ($n={w0+m0:,}$) & {s5:.2f}\\% ($n={w5+m5:,}$) & {s5-s0:+.2f} pp & \\\\"
        )

    lines = [
        "\\begin{table}[ht]",
        "\\centering",
        "\\caption{Sensitivity of Round 1 counts and pedestrian female share to Mask2Former person-pixel thresholds.}",
        "\\label{tab:pixel_threshold}",
        "\\begin{threeparttable}",
        "\\footnotesize",
        "\\begin{tabular}{@{}lrrrr@{}}",
        "\\toprule",
        "\\multicolumn{5}{@{}l}{\\textit{Panel A: Global yield and female share across pixel thresholds}} \\\\",
        "\\midrule",
        "Threshold (pixels) & Images kept & Classified ped. & Unclear & Ped. female share \\\\",
        "\\midrule",
        *panel_a_rows,
        "\\midrule",
        "\\multicolumn{5}{@{}l}{\\textit{Panel B: Regional invariance at $\\ge 5{,}000$ person/rider pixels}} \\\\",
        "\\midrule",
        "Region & All ($\\ge 0$ px) & Filtered ($\\ge 5{,}000$ px) & Difference & \\\\",
        "\\midrule",
        *panel_b_rows,
        "\\bottomrule",
        "\\end{tabular}",
        "\\begin{tablenotes}[flushleft]\\footnotesize",
        "\\item \\textit{Notes:} Pixel counts sum Mask2Former \\texttt{Person}, \\texttt{Bicyclist}, "
        "\\texttt{Motorcyclist}, and \\texttt{Other-Rider} pixels from \\texttt{segmentation.parquet} "
        "across the 9,721 Round 1 images.",
        "\\end{tablenotes}",
        "\\end{threeparttable}",
        "\\end{table}",
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
