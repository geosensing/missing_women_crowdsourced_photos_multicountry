"""Count women, men, two-wheeler riders, and unclear pedestrians via museclient.

Supports both single images (default) and packed contact-sheet grids (e.g. 2x2),
concurrent workers via ProcessPoolExecutor, hard USD spend caps, and incremental
resumable CSV output.
"""

from __future__ import annotations

import argparse
import base64
import csv
import io
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Allow running directly without installing museclient into the global Python env.
MUSECLIENT_SRC = Path("/Users/soodoku/Documents/GitHub/gojiplus/museclient/src")
if MUSECLIENT_SRC.exists() and str(MUSECLIENT_SRC) not in sys.path:
    sys.path.insert(0, str(MUSECLIENT_SRC))

from museclient import Client  # noqa: E402

PROMPT = (
    "You are coding street-level photographs for a demographic study of public space.\n"
    "The attached image is a {cols}x{rows} contact sheet containing {n} numbered panels "
    "([1]..[{n}] in reading order, left-to-right, top-to-bottom).\n"
    "For EACH numbered panel, count visible people in public space (exclude people inside "
    "enclosed cars/buses/trucks, and exclude posters, billboards, mannequins, or statues):\n"
    "- women_count: adult or adolescent women/girls walking or standing "
    "(pedestrians, not on vehicles)\n"
    "- men_count: adult or adolescent men/boys walking or standing "
    "(pedestrians, not on vehicles)\n"
    "- women_twowheeler: women/girls riding bicycles, motorcycles, or scooters\n"
    "- men_twowheeler: men/boys riding bicycles, motorcycles, or scooters\n"
    "- unclear_count: pedestrians or riders too small, blurred, or occluded to classify by sex\n"
    "Return JSON with one entry per panel slot 1..{n}. Do not skip any panel."
)

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slot": {"type": "integer", "minimum": 1},
                    "women_count": {"type": "integer", "minimum": 0},
                    "men_count": {"type": "integer", "minimum": 0},
                    "women_twowheeler": {"type": "integer", "minimum": 0},
                    "men_twowheeler": {"type": "integer", "minimum": 0},
                    "unclear_count": {"type": "integer", "minimum": 0},
                },
                "required": [
                    "slot",
                    "women_count",
                    "men_count",
                    "women_twowheeler",
                    "men_twowheeler",
                    "unclear_count",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}


def pack_grid(
    image_paths: list[Path], cols: int, rows: int, tile_w: int = 1600, tile_h: int = 1200
) -> bytes:
    """Pack up to cols*rows images into a numbered JPEG contact sheet."""
    pad = 8 if cols * rows > 1 else 0
    canvas = Image.new(
        "RGB",
        (cols * tile_w + (cols + 1) * pad, rows * tile_h + (rows + 1) * pad),
        color=(255, 255, 255),
    )
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    for idx, path in enumerate(image_paths):
        r, c = divmod(idx, cols)
        x0 = pad + c * (tile_w + pad)
        y0 = pad + r * (tile_h + pad)
        with Image.open(path) as im:
            rgb = im.convert("RGB")
            rgb.thumbnail((tile_w, tile_h), Image.Resampling.LANCZOS)
            if cols * rows == 1:
                canvas = rgb
                break
            ox = x0 + (tile_w - rgb.width) // 2
            oy = y0 + (tile_h - rgb.height) // 2
            canvas.paste(rgb, (ox, oy))

        badge = f"[{idx + 1}]"
        draw.rectangle([x0, y0, x0 + 38, y0 + 22], fill=(0, 0, 0))
        draw.text((x0 + 6, y0 + 5), badge, fill=(255, 255, 255), font=font)

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


_WORKER_CLIENT: Client | None = None
_WORKER_CFG: dict = {}


def _init_worker(cap_usd: float, workdir: str, cfg: dict) -> None:
    global _WORKER_CLIENT, _WORKER_CFG
    _WORKER_CLIENT = Client(cap_usd=cap_usd, workdir=workdir)
    _WORKER_CFG = cfg


def _process_batch(batch_strs: list[str]) -> list[dict]:
    assert _WORKER_CLIENT is not None
    batch = [Path(p) for p in batch_strs]
    cols = _WORKER_CFG["cols"]
    rows = _WORKER_CFG["rows"]
    jpeg_bytes = pack_grid(batch, cols, rows, _WORKER_CFG["tile_width"], _WORKER_CFG["tile_height"])
    b64 = base64.b64encode(jpeg_bytes).decode("ascii")
    prompt_text = PROMPT.format(cols=cols, rows=rows, n=len(batch))

    answer = _WORKER_CLIENT.complete(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                ],
            }
        ],
        schema=RESPONSE_SCHEMA,
        max_completion_tokens=_WORKER_CFG["max_tokens"],
        reasoning_effort=_WORKER_CFG["reasoning_effort"],
    )
    items = answer["items"]
    by_slot = {item["slot"]: item for item in items}
    if len(items) != len(batch) or set(by_slot) != set(range(1, len(batch) + 1)):
        raise ValueError("Model response must contain each requested slot exactly once")

    out_rows: list[dict] = []
    for slot_idx, path in enumerate(batch, start=1):
        item = by_slot[slot_idx]
        wc = item["women_count"]
        mc = item["men_count"]
        wt = item["women_twowheeler"]
        mt = item["men_twowheeler"]
        uc = item["unclear_count"]
        ped_known = wc + mc
        out_rows.append(
            {
                "image": path.name,
                "path": str(path),
                "grid": _WORKER_CFG["grid"],
                "slot": slot_idx,
                "women_count": wc,
                "men_count": mc,
                "women_twowheeler": wt,
                "men_twowheeler": mt,
                "unclear_count": uc,
                "pedestrian_female_share": f"{(wc / ped_known):.4f}" if ped_known > 0 else "",
            }
        )
    return out_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=8, help="Max images (0 = all)")
    parser.add_argument("--grid", default="1x1", help="Grid layout COLSxROWS (e.g. 1x1, 2x2)")
    parser.add_argument("--tile-width", type=int, default=1600)
    parser.add_argument("--tile-height", type=int, default=1200)
    parser.add_argument("--cap-usd", type=float, default=1.0)
    parser.add_argument("--workdir", type=Path, default=Path("data/muse_cache"))
    parser.add_argument("--out", type=Path, default=Path("outputs/muse_counts.csv"))
    parser.add_argument("--reasoning-effort", default="low")
    parser.add_argument("--max-tokens", type=int, default=4000)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    cols, rows = (int(x) for x in args.grid.lower().split("x"))
    batch_size = cols * rows

    exts = {".jpg", ".jpeg", ".png", ".webp"}
    paths = sorted(p for p in args.images_dir.iterdir() if p.suffix.lower() in exts)
    if args.limit > 0:
        paths = paths[: args.limit]
    if not paths:
        raise SystemExit(f"No images found in {args.images_dir}")

    fieldnames = [
        "image",
        "path",
        "grid",
        "slot",
        "women_count",
        "men_count",
        "women_twowheeler",
        "men_twowheeler",
        "unclear_count",
        "pedestrian_female_share",
    ]
    done_images: set[str] = set()
    if args.out.exists():
        with args.out.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                done_images.add(row["image"])
    todo = [p for p in paths if p.name not in done_images]
    print(
        f"Total images: {len(paths):,}, already in {args.out}: {len(done_images):,}, "
        f"todo: {len(todo):,}"
    )
    if not todo:
        return

    batches = []
    for start in range(0, len(todo), batch_size):
        end = start + batch_size
        batches.append([str(path) for path in todo[start:end]])
    cfg = {
        "cols": cols,
        "rows": rows,
        "grid": args.grid,
        "tile_width": args.tile_width,
        "tile_height": args.tile_height,
        "max_tokens": args.max_tokens,
        "reasoning_effort": args.reasoning_effort,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_header = not args.out.exists() or args.out.stat().st_size == 0
    written = 0
    with args.out.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        with ProcessPoolExecutor(
            max_workers=args.workers,
            initializer=_init_worker,
            initargs=(args.cap_usd, str(args.workdir), cfg),
        ) as ex:
            futures = {ex.submit(_process_batch, b): b for b in batches}
            for idx, fut in enumerate(as_completed(futures), start=1):
                try:
                    batch_rows = fut.result()
                except Exception as exc:
                    print(f"Batch {idx} failed ({futures[fut]}): {exc}", flush=True)
                    continue
                if batch_rows:
                    writer.writerows(batch_rows)
                    handle.flush()
                    written += len(batch_rows)
                if idx % 50 == 0 or idx == len(batches):
                    spend = Client(cap_usd=args.cap_usd, workdir=str(args.workdir)).spend()
                    print(f"Batch {idx}/{len(batches)} (+{written:,} rows) -> spend={spend}")

    if written != len(todo):
        raise SystemExit(
            f"Saved {written:,} of {len(todo):,} pending images. Rerun to retry the rest."
        )
    print(f"Done: wrote {written:,} new rows to {args.out}")


if __name__ == "__main__":
    main()
