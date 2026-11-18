"""Download sampled Global Streetscapes images for a wave without the 6 TB corpus.

- KartaView: fetches direct HTTPS URLs from data/parquet/metadata_kv.parquet.
- Mapillary: queries Graph API (requires MAPILLARY_ACCESS_TOKEN in env or .env).

Resumable: skips existing non-empty files under data/images/<wave>/<uuid>.jpg.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

HF_REPO = "NUS-UAL/global-streetscapes"
HF_KV_META = "data/parquet/metadata_kv.parquet"


def load_dotenv(path: Path = Path(".env")) -> None:
    """Populate os.environ from .env if present (without overwriting existing vars)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def get_mapillary_token() -> str | None:
    """Read Mapillary token from env/.env or ~/.config/mapillary/auth.json."""
    load_dotenv()
    token = os.environ.get("MAPILLARY_ACCESS_TOKEN")
    if token:
        return token
    auth_path = Path.home() / ".config/mapillary/auth.json"
    if auth_path.exists():
        return json.loads(auth_path.read_text(encoding="utf-8")).get("access_token")
    return None


def load_kv_urls(target_uuids: set[str]) -> dict[str, list[str]]:
    """Load KartaView fallback URLs for target_uuids from metadata_kv.parquet."""
    if not target_uuids:
        return {}
    path = hf_hub_download(repo_id=HF_REPO, filename=HF_KV_META, repo_type="dataset")
    pf = pq.ParquetFile(path)
    urls: dict[str, list[str]] = {}
    for rg_idx in range(pf.num_row_groups):
        table = pf.read_row_group(rg_idx, columns=["uuid", "kv_fileurlLTh", "kv_fileurlProc"])
        uuids = table["uuid"].to_pylist()
        hits = [i for i, u in enumerate(uuids) if u in target_uuids]
        if hits:
            sub = table.take(hits).to_pydict()
            for u, lth, proc in zip(sub["uuid"], sub["kv_fileurlLTh"], sub["kv_fileurlProc"]):
                urls[u] = [x for x in (lth, proc) if x]
    return urls


def _fetch_to_file(url: str, dest: Path, timeout: int = 20) -> None:
    """Download URL to dest with an explicit socket timeout."""
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = resp.read()
    tmp = dest.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(dest)


def download_one(
    row: dict[str, str],
    out_dir: Path,
    kv_urls: dict[str, list[str]],
    mly_token: str | None,
) -> dict[str, str]:
    """Download a single image and return status metadata."""
    uuid = row["uuid"]
    dest = out_dir / f"{uuid}.jpg"
    if dest.exists() and dest.stat().st_size > 0:
        return {**row, "status": "cached", "local_path": str(dest)}

    if row["source"] == "KartaView":
        last_err = "no_url"
        for url in kv_urls.get(uuid, []):
            try:
                _fetch_to_file(url, dest)
                if dest.exists() and dest.stat().st_size > 0:
                    return {**row, "status": "ok", "local_path": str(dest)}
            except Exception as exc:
                last_err = str(exc)
        return {**row, "status": f"error:{last_err}", "local_path": ""}

    if row["source"] == "Mapillary":
        if not mly_token:
            return {**row, "status": "skipped:no_mapillary_token", "local_path": ""}
        api_url = (
            f"https://graph.mapillary.com/{row['orig_id']}"
            f"?fields=thumb_2048_url,thumb_1024_url&access_token={mly_token}"
        )
        try:
            with urllib.request.urlopen(api_url, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            img_url = payload.get("thumb_2048_url") or payload.get("thumb_1024_url")
            if not img_url:
                return {**row, "status": "error:no_thumb_url", "local_path": ""}
            _fetch_to_file(img_url, dest)
            return {**row, "status": "ok", "local_path": str(dest)}
        except Exception as exc:
            return {**row, "status": f"error:{exc}", "local_path": ""}

    return {**row, "status": f"error:unknown_source:{row['source']}", "local_path": ""}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-csv", type=Path, default=Path("outputs/selected_images.csv"))
    parser.add_argument("--wave", default="round1", help="Wave to download (round1, round2, all)")
    parser.add_argument("--source", default="all", help="Filter source (all, KartaView, Mapillary)")
    parser.add_argument("--max-rank", type=int, default=0, help="Max rank_in_city (0 = no limit)")
    parser.add_argument("--out-dir", type=Path, default=Path("data/images"))
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()

    mly_token = get_mapillary_token()

    with args.images_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    if args.wave != "all":
        rows = [r for r in rows if r["wave"] == args.wave]
    if args.source != "all":
        rows = [r for r in rows if r["source"] == args.source]
    if args.max_rank > 0:
        rows = [r for r in rows if int(r["rank_in_city"]) <= args.max_rank]

    wave_dir = args.out_dir / args.wave
    wave_dir.mkdir(parents=True, exist_ok=True)

    kv_uuids = {r["uuid"] for r in rows if r["source"] == "KartaView"}
    kv_urls = load_kv_urls(kv_uuids)

    print(f"Downloading {len(rows)} images (wave={args.wave}, source={args.source})...")
    results: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(download_one, r, wave_dir, kv_urls, mly_token) for r in rows]
        for idx, fut in enumerate(as_completed(futures), start=1):
            results.append(fut.result())
            if idx % 200 == 0 or idx == len(rows):
                ok = sum(1 for x in results if x["status"] in {"ok", "cached"})
                print(f"  {idx}/{len(rows)} processed ({ok} ok/cached)")

    manifest_path = Path(f"outputs/download_manifest_{args.wave}.csv")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(results[0].keys()) if results else []
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"Wrote {manifest_path}")


if __name__ == "__main__":
    main()
