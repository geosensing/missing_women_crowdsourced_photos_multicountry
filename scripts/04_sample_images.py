"""Sample up to 2,000 person-containing images per selected city from Global Streetscapes.

Streams only the required columns from Hugging Face Parquet files
(simplemaps.parquet and instances.parquet) for the 100 cities in
outputs/selected_cities.csv without downloading the 6 TB image corpus.
Filters to images with Mask2Former Person/Bicyclist/Motorcyclist/Other-Rider >= 1,
draws deterministically via SHA-256, and writes selected_images.csv,
city_image_summary.csv, and image_sampling_manifest.json.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

HF_REPO = "NUS-UAL/global-streetscapes"
HF_SIMPLEMAPS = "data/parquet/simplemaps.parquet"
HF_INSTANCES = "data/parquet/instances.parquet"

DEFAULT_CONFIG = Path("config/sampling.json")
DEFAULT_SELECTED_CITIES = Path("outputs/selected_cities.csv")
DEFAULT_IMAGES_OUT = Path("outputs/selected_images.csv")
DEFAULT_SUMMARY_OUT = Path("outputs/city_image_summary.csv")
DEFAULT_MANIFEST_OUT = Path("outputs/image_sampling_manifest.json")


def file_digest(path: Path) -> dict[str, int | str]:
    """Return byte size and SHA-256 hex digest for a file."""
    data = path.read_bytes()
    return {
        "path": str(path),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def deterministic_img_key(seed: int, city_id: str, uuid: str) -> str:
    """Compute a deterministic SHA-256 sort key for within-city image sampling."""
    return hashlib.sha256(f"{seed}:img:{city_id}:{uuid}".encode("utf-8")).hexdigest()


def load_selected_cities(path: Path) -> dict[str, dict[str, str]]:
    """Load selected_cities.csv keyed by city_id."""
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["city_id"]: row for row in csv.DictReader(handle)}


def stream_city_images(cities_by_id: dict[str, dict[str, str]]) -> tuple[dict[str, dict], dict[str, int]]:
    """Download/cache the two Parquet tables (0.7 GB total) and filter to selected city_ids."""
    target_id_strs = list(cities_by_id.keys())
    target_id_ints = [int(cid) for cid in target_id_strs]
    value_set = None

    city_total_counts: dict[str, int] = defaultdict(int)
    images_by_uuid: dict[str, dict] = {}

    print(f"Fetching {HF_SIMPLEMAPS} (cached via huggingface_hub)...")
    simplemaps_path = hf_hub_download(repo_id=HF_REPO, filename=HF_SIMPLEMAPS, repo_type="dataset")
    pf = pq.ParquetFile(simplemaps_path)
    for rg_idx in range(pf.num_row_groups):
        table = pf.read_row_group(rg_idx, columns=["uuid", "city_id", "source", "orig_id"])
        if value_set is None:
            col_type = table["city_id"].type
            if pa.types.is_string(col_type) or pa.types.is_large_string(col_type):
                value_set = pa.array(target_id_strs, type=col_type)
            else:
                value_set = pa.array(target_id_ints, type=col_type)
        mask = pc.is_in(table["city_id"], value_set=value_set)
        filtered = table.filter(mask)
        if filtered.num_rows > 0:
            cols = filtered.to_pydict()
            for uuid, cid, source, orig_id in zip(
                cols["uuid"], cols["city_id"], cols["source"], cols["orig_id"]
            ):
                cid_str = str(cid)
                city_total_counts[cid_str] += 1
                images_by_uuid[uuid] = {
                    "uuid": uuid,
                    "city_id": cid_str,
                    "source": source,
                    "orig_id": str(orig_id),
                }
    print(f"  matched {len(images_by_uuid):,} images across {len(target_id_strs)} cities")

    target_uuids = set(images_by_uuid.keys())
    person_cols = ["Person", "Bicyclist", "Motorcyclist", "Other-Rider"]
    print(f"Fetching {HF_INSTANCES} (cached via huggingface_hub)...")
    instances_path = hf_hub_download(repo_id=HF_REPO, filename=HF_INSTANCES, repo_type="dataset")
    pf = pq.ParquetFile(instances_path)
    for rg_idx in range(pf.num_row_groups):
        table = pf.read_row_group(rg_idx, columns=["uuid", *person_cols])
        uuids = table["uuid"].to_pylist()
        hit_indices = [i for i, u in enumerate(uuids) if u in target_uuids]
        if hit_indices:
            sub = table.take(hit_indices).to_pydict()
            for idx, uuid in enumerate(sub["uuid"]):
                p_cnt = int(round(sub["Person"][idx] or 0.0))
                r_cnt = int(
                    round(
                        (sub["Bicyclist"][idx] or 0.0)
                        + (sub["Motorcyclist"][idx] or 0.0)
                        + (sub["Other-Rider"][idx] or 0.0)
                    )
                )
                images_by_uuid[uuid]["person_count"] = p_cnt
                images_by_uuid[uuid]["rider_count"] = r_cnt

    return images_by_uuid, city_total_counts


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    """Write rows to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--selected-cities", type=Path, default=DEFAULT_SELECTED_CITIES)
    parser.add_argument("--images-out", type=Path, default=DEFAULT_IMAGES_OUT)
    parser.add_argument("--summary-out", type=Path, default=DEFAULT_SUMMARY_OUT)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST_OUT)
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    seed = int(config["seed"])
    alloc_cfg = config["within_city_allocation"]
    target_inf = int(alloc_cfg["target_images_per_city"])
    round1_inf = int(alloc_cfg.get("round1_images_per_city", 100))
    target_cal = int(alloc_cfg["calibration_images_per_city"])

    cities_by_id = load_selected_cities(args.selected_cities)
    images_by_uuid, city_total_counts = stream_city_images(cities_by_id)

    people_by_city: dict[str, list[dict]] = defaultdict(list)
    for rec in images_by_uuid.values():
        p_cnt = rec.get("person_count", 0)
        r_cnt = rec.get("rider_count", 0)
        if p_cnt + r_cnt >= 1:
            people_by_city[rec["city_id"]].append(rec)

    selected_rows: list[dict] = []
    summary_rows: list[dict] = []

    for cid in sorted(cities_by_id.keys()):
        city_meta = cities_by_id[cid]
        total_imgs = city_total_counts.get(cid, 0)
        pool = sorted(
            people_by_city.get(cid, []),
            key=lambda r: deterministic_img_key(seed, cid, r["uuid"]),
        )
        n_people = len(pool)
        inf_slice = pool[:target_inf]
        inf_rank = {r["uuid"]: i + 1 for i, r in enumerate(inf_slice)}

        # Prefer disjoint calibration images from the tail if pool > target_inf;
        # otherwise sample calibration from the top of the inference draw.
        if n_people > target_inf:
            cal_slice = pool[target_inf : target_inf + target_cal]
        else:
            cal_slice = pool[:target_cal]
        cal_uuids = {r["uuid"] for r in cal_slice}

        seen_uuids: set[str] = set()
        for rec in inf_slice + cal_slice:
            uuid = rec["uuid"]
            if uuid in seen_uuids:
                continue
            seen_uuids.add(uuid)
            rank = inf_rank.get(uuid)
            in_cal = uuid in cal_uuids
            if rank is not None and in_cal:
                role = "both"
            elif rank is not None:
                role = "inference"
            else:
                role = "calibration"
            wave = "round1" if (rank is not None and rank <= round1_inf) else (
                "round2" if rank is not None else "calibration"
            )
            selected_rows.append(
                {
                    "uuid": uuid,
                    "city_id": cid,
                    "city_ascii": city_meta["city_ascii"],
                    "iso3": city_meta["iso3"],
                    "region": city_meta["region"],
                    "source": rec["source"],
                    "orig_id": rec["orig_id"],
                    "person_count": rec["person_count"],
                    "rider_count": rec["rider_count"],
                    "rank_in_city": rank if rank is not None else "",
                    "wave": wave,
                    "sample_role": role,
                }
            )

        summary_rows.append(
            {
                "city_id": cid,
                "city_ascii": city_meta["city_ascii"],
                "iso3": city_meta["iso3"],
                "region": city_meta["region"],
                "total_corpus_images": total_imgs,
                "images_with_people": n_people,
                "person_mask_rate": f"{(n_people / total_imgs) if total_imgs else 0.0:.4f}",
                "sampled_inference_images": len(inf_slice),
                "sampled_calibration_images": len(cal_slice),
            }
        )

    write_csv(
        args.images_out,
        selected_rows,
        [
            "uuid",
            "city_id",
            "city_ascii",
            "iso3",
            "region",
            "source",
            "orig_id",
            "person_count",
            "rider_count",
            "rank_in_city",
            "wave",
            "sample_role",
        ],
    )
    write_csv(
        args.summary_out,
        summary_rows,
        [
            "city_id",
            "city_ascii",
            "iso3",
            "region",
            "total_corpus_images",
            "images_with_people",
            "person_mask_rate",
            "sampled_inference_images",
            "sampled_calibration_images",
        ],
    )

    manifest = {
        "seed": seed,
        "config_version": config["version"],
        "sources": {
            "simplemaps": HF_SIMPLEMAPS,
            "instances": HF_INSTANCES,
            "selected_cities": file_digest(args.selected_cities),
        },
        "counts": {
            "cities": len(summary_rows),
            "total_corpus_images": sum(r["total_corpus_images"] for r in summary_rows),
            "total_images_with_people": sum(r["images_with_people"] for r in summary_rows),
            "sampled_inference_images": sum(r["sampled_inference_images"] for r in summary_rows),
            "sampled_calibration_images": sum(r["sampled_calibration_images"] for r in summary_rows),
            "unique_sampled_images": len(selected_rows),
        },
        "outputs": {
            "selected_images": file_digest(args.images_out),
            "city_image_summary": file_digest(args.summary_out),
        },
    }
    args.manifest_out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"Done: {manifest['counts']['sampled_inference_images']:,} inference + "
        f"{manifest['counts']['sampled_calibration_images']:,} calibration "
        f"({manifest['counts']['unique_sampled_images']:,} unique) across "
        f"{manifest['counts']['cities']} cities."
    )


if __name__ == "__main__":
    main()
