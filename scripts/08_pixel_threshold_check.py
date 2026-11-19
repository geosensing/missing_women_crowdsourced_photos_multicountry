"""Generate Appendix Table A1: empirical pixel-area threshold and regional bias check.

Joins outputs/muse_counts_all.csv and outputs/selected_images.csv with
Mask2Former Person+Rider pixel counts from data/parquet/segmentation.parquet,
and writes tabs/tableA1_pixel_threshold.tex (Panel A: global threshold curve;
Panel B: regional pedestrian female share at pix >= 0 vs. pix >= 5,000).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download
from paper_tables import region_label, write_table

HF_REPO = "NUS-UAL/global-streetscapes"
HF_SEG = "data/parquet/segmentation.parquet"
THRESHOLDS = [0, 1000, 2000, 5000, 10000, 20000]


def load_person_pixels(target_uuids: set[str], revision: str) -> dict[str, float]:
    """Load total Person+Rider pixel counts for target_uuids from segmentation.parquet."""
    try:
        path = hf_hub_download(
            repo_id=HF_REPO,
            filename=HF_SEG,
            repo_type="dataset",
            revision=revision,
            local_files_only=True,
        )
    except Exception:
        path = hf_hub_download(
            repo_id=HF_REPO, filename=HF_SEG, repo_type="dataset", revision=revision
        )

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
                if u in pix:
                    raise ValueError(f"Duplicate segmentation record for {u}")
                pixels = [sub[col][idx] for col in cols[1:]]
                if any(p is None or not math.isfinite(p) or p < 0 for p in pixels):
                    raise ValueError(f"Missing or invalid segmentation pixels for {u}")
                pix[u] = sum(pixels)
    if missing := target_uuids - pix.keys():
        raise ValueError(f"Missing segmentation for {len(missing)} coded images")
    return pix


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/sampling.json"))
    parser.add_argument("--counts-csv", type=Path, default=Path("outputs/muse_counts_all.csv"))
    parser.add_argument("--images-csv", type=Path, default=Path("outputs/selected_images.csv"))
    parser.add_argument("--out", type=Path, default=Path("tabs/tableA1_pixel_threshold.tex"))
    args = parser.parse_args()

    with args.images_csv.open(newline="", encoding="utf-8") as handle:
        metadata = list(csv.DictReader(handle))
        meta = {r["uuid"]: r for r in metadata}
    with args.counts_csv.open(newline="", encoding="utf-8") as handle:
        counts = list(csv.DictReader(handle))
        muse = {r["image"].rsplit(".", 1)[0]: r for r in counts}
    if len(meta) != len(metadata) or len(muse) != len(counts):
        raise ValueError("Repeated image IDs in metadata or count records")
    if missing := muse.keys() - meta.keys():
        raise ValueError(f"{len(missing)} coded images are absent from the selection file")

    revision = json.loads(args.config.read_text(encoding="utf-8"))["corpus_revision"]
    pix = load_person_pixels(set(muse), revision)
    total_imgs = len(muse)
    total_ped_all = sum(int(r["women_count"]) + int(r["men_count"]) for r in muse.values())

    panel_a_rows = []
    for thresh in THRESHOLDS:
        sub = [r for u, r in muse.items() if pix[u] >= thresh]
        w = sum(int(r["women_count"]) for r in sub)
        m = sum(int(r["men_count"]) for r in sub)
        unc = sum(int(r["unclear_count"]) for r in sub)
        ped = w + m
        share = f"{w/ped:.2%}" if ped else "—"
        panel_a_rows.append(
            (
                f"{thresh:,}",
                f"{len(sub):,} ({len(sub)/total_imgs:.1%})",
                f"{ped:,} ({ped/total_ped_all:.1%})",
                f"{unc:,}",
                share,
            )
        )

    reg_all: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    reg_5k: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for u, r in muse.items():
        reg = meta[u]["region"]
        w, m = int(r["women_count"]), int(r["men_count"])
        reg_all[reg][0] += w
        reg_all[reg][1] += m
        if pix[u] >= 5000:
            reg_5k[reg][0] += w
            reg_5k[reg][1] += m

    panel_b_rows = []
    for reg in sorted(reg_all):
        w0, m0 = reg_all[reg]
        w5, m5 = reg_5k[reg]
        s0 = w0 / (w0 + m0) * 100
        s5 = w5 / (w5 + m5) * 100
        panel_b_rows.append(
            (
                region_label(reg),
                f"{s0:.2f}% (n={w0+m0:,})",
                f"{s5:.2f}% (n={w5+m5:,})",
                f"{s5-s0:+.2f} pp",
            )
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    counts_table = pd.DataFrame(
        panel_a_rows,
        columns=["Minimum pixels", "Images kept", "Pedestrians kept", "Unclear", "Women (ped.)"],
    )
    region_table = pd.DataFrame(
        panel_b_rows, columns=["Region", "All images", "At least 5,000 pixels", "Difference"]
    )
    write_table(counts_table, args.out, "lrrrr")
    write_table(region_table, args.out.with_name("tableA1_pixel_regions.tex"), "lrrr")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
