"""Prepare a stratified 300-image validation sample and config for Label Studio.

Draws 300 coded Round 1 images proportionally across the 12 region x income strata,
symlinks them into data/label_studio/images/, and writes:
  - data/label_studio/label_config.xml (5-class KeyPointLabels with hotkeys 1-5)
  - data/label_studio/tasks.json (local-files URLs + city/region metadata)
  - outputs/label_studio_sample.csv (manifest with Muse counts for post-hoc eval)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

HF_REPO = "NUS-UAL/global-streetscapes"
HF_SEG = "data/parquet/segmentation.parquet"

LABEL_CONFIG_XML = """<View>
  <Header value="$city ($iso3) — $region"/>
  <KeyPointLabels name="people" toName="image" strokeWidth="2">
    <Label value="Woman pedestrian" background="#E11D48" hotkey="1"/>
    <Label value="Man pedestrian" background="#2563EB" hotkey="2"/>
    <Label value="Woman two-wheeler" background="#F59E0B" hotkey="3"/>
    <Label value="Man two-wheeler" background="#10B981" hotkey="4"/>
    <Label value="Unclear person" background="#6B7280" hotkey="5"/>
  </KeyPointLabels>
  <Image name="image" value="$image" zoom="true" zoomControl="true"/>
  <Choices name="quality" toName="image" choice="multiple" showInLine="true">
    <Choice value="Bad / unusable image" hotkey="b"/>
  </Choices>
</View>
"""


def allocate_quotas(sizes: dict[str, int], total: int) -> dict[str, int]:
    """Proportional largest-remainder allocation across strata."""
    grand = sum(sizes.values())
    exact = {k: (v / grand) * total for k, v in sizes.items()}
    quotas = {k: min(sizes[k], math.floor(exact[k])) for k in sizes}
    leftover = total - sum(quotas.values())
    for k in sorted(sizes, key=lambda x: (-(exact[x] - quotas[x]), x)):
        if leftover == 0:
            break
        if quotas[k] < sizes[k]:
            quotas[k] += 1
            leftover -= 1
    return quotas


def load_person_pixels(target_uuids: set[str]) -> dict[str, float]:
    """Load Person+Rider pixel counts for target_uuids from segmentation.parquet."""
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
    parser.add_argument("--n", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20261115)
    parser.add_argument("--min-pixels", type=int, default=5000)
    parser.add_argument("--counts-csv", type=Path, default=Path("outputs/muse_counts_round1.csv"))
    parser.add_argument("--images-csv", type=Path, default=Path("outputs/selected_images.csv"))
    parser.add_argument("--cities-csv", type=Path, default=Path("outputs/selected_cities.csv"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/label_studio"))
    parser.add_argument(
        "--manifest-out", type=Path, default=Path("outputs/label_studio_sample.csv")
    )
    args = parser.parse_args()

    with args.cities_csv.open(newline="", encoding="utf-8") as handle:
        city_stratum = {r["city_id"]: r["stratum"] for r in csv.DictReader(handle)}
    with args.images_csv.open(newline="", encoding="utf-8") as handle:
        img_meta = {r["uuid"]: r for r in csv.DictReader(handle)}
    with args.counts_csv.open(newline="", encoding="utf-8") as handle:
        muse_rows = list(csv.DictReader(handle))

    pix: dict[str, float] = {}
    if args.min_pixels > 0:
        uuids = {r["image"].rsplit(".", 1)[0] for r in muse_rows}
        pix = load_person_pixels(uuids)

    by_stratum: dict[str, list[dict]] = defaultdict(list)
    for row in muse_rows:
        uuid = row["image"].rsplit(".", 1)[0]
        meta = img_meta.get(uuid)
        if not meta or not Path(row["path"]).exists():
            continue
        if args.min_pixels > 0 and pix.get(uuid, 0.0) < args.min_pixels:
            continue
        stratum = city_stratum[meta["city_id"]]
        by_stratum[stratum].append({**row, **meta, "uuid": uuid, "stratum": stratum})

    quotas = allocate_quotas({k: len(v) for k, v in by_stratum.items()}, args.n)

    img_dir = args.out_dir / "images"
    if img_dir.exists():
        for old in img_dir.iterdir():
            if old.is_file() or old.is_symlink():
                old.unlink()
    img_dir.mkdir(parents=True, exist_ok=True)
    tasks: list[dict] = []
    manifest_rows: list[dict] = []

    for stratum in sorted(by_stratum):
        pool = sorted(
            by_stratum[stratum],
            key=lambda r: hashlib.sha256(f"{args.seed}:ls:{r['uuid']}".encode()).hexdigest(),
        )
        for rec in pool[: quotas[stratum]]:
            src = Path(rec["path"]).resolve()
            dst = img_dir / src.name
            if not dst.exists():
                try:
                    os.link(src, dst)
                except OSError:
                    shutil.copy2(src, dst)
            tasks.append(
                {
                    "data": {
                        "image": f"/data/local-files/?d=images/{src.name}",
                        "uuid": rec["uuid"],
                        "city": rec["city_ascii"],
                        "iso3": rec["iso3"],
                        "region": rec["region"],
                        "stratum": stratum,
                    }
                }
            )
            manifest_rows.append(
                {
                    "uuid": rec["uuid"],
                    "image": src.name,
                    "city_ascii": rec["city_ascii"],
                    "iso3": rec["iso3"],
                    "region": rec["region"],
                    "stratum": stratum,
                    "muse_women_count": rec["women_count"],
                    "muse_men_count": rec["men_count"],
                    "muse_women_twowheeler": rec["women_twowheeler"],
                    "muse_men_twowheeler": rec["men_twowheeler"],
                    "muse_unclear_count": rec["unclear_count"],
                }
            )

    (args.out_dir / "label_config.xml").write_text(LABEL_CONFIG_XML, encoding="utf-8")
    (args.out_dir / "tasks.json").write_text(json.dumps(tasks, indent=2) + "\n", encoding="utf-8")
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest_out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0].keys()))
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"Prepared {len(tasks)} Label Studio tasks in {args.out_dir}/")


if __name__ == "__main__":
    main()
