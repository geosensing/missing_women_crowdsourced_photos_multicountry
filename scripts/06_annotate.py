"""Mobile-first swipe-to-agree & tap-to-edit street-view annotation server.

Zero external dependencies (stdlib http.server + embedded touch-friendly HTML/JS).
- Swipe RIGHT (or tap Agree): accepts pre-filled LLM counts and advances.
- Swipe LEFT (or tap Flag): marks bad/unusable image and advances.
- Tap +/- thumb steppers: quick-edit counts, then Save & Next.
- Supports --blind (hides LLM counts) and --sample-csv (e.g. stratified 300-image subset).

Open on your phone over local Wi-Fi (--host 0.0.0.0), Tailscale, or cloudflared tunnel.
Saves incrementally to outputs/human_annotations.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport"
  content="width=device-width, initial-scale=1, maximum-scale=5, user-scalable=yes">
<title>Street Annotation</title>
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  body {
    margin: 0; font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    background: #0d0d0f; color: #f5f5f7; display: flex; flex-direction: column;
    height: 100dvh; overflow: hidden;
  }
  header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 8px 12px; background: #1c1c1e; border-bottom: 1px solid #2c2c2e;
    font-size: 13px;
  }
  .pill { background: #2c2c2e; padding: 3px 8px; border-radius: 999px; font-weight: 600; }
  #stage {
    position: relative; flex: 1; display: flex; align-items: center; justify-content: center;
    background: #000; overflow: hidden; touch-action: pan-y pinch-zoom;
  }
  #stage img {
    max-width: 100%; max-height: 100%; object-fit: contain;
    transition: transform 0.15s ease-out;
  }
  #swipe-badge {
    position: absolute; top: 16px; left: 50%; transform: translateX(-50%);
    padding: 6px 14px; border-radius: 999px; font-weight: 700; font-size: 14px;
    opacity: 0; pointer-events: none; transition: opacity 0.1s;
  }
  #controls {
    background: #1c1c1e; border-top: 1px solid #2c2c2e;
    padding: 10px 12px max(10px, env(safe-area-inset-bottom));
    display: flex; flex-direction: column; gap: 8px;
  }
  .grid {
    display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px;
  }
  .counter {
    background: #2c2c2e; border-radius: 10px; padding: 6px 8px;
    display: flex; align-items: center; justify-content: space-between;
  }
  .counter.wide { grid-column: span 2; }
  .counter span.lbl { font-size: 12px; color: #d1d1d6; font-weight: 600; }
  .stepper { display: flex; align-items: center; gap: 8px; }
  .stepper button {
    width: 34px; height: 34px; border-radius: 8px; border: 0;
    background: #3a3a3c; color: #fff; font-size: 18px; font-weight: 700; cursor: pointer;
  }
  .stepper .val { min-width: 20px; text-align: center; font-size: 16px; font-weight: 700; }
  .actions { display: flex; gap: 8px; }
  .btn {
    flex: 1; padding: 12px 10px; border: 0; border-radius: 10px;
    font-size: 15px; font-weight: 700; cursor: pointer; color: #fff;
  }
  .btn-flag { background: #ff453a; flex: 0.7; }
  .btn-prev { background: #3a3a3c; flex: 0.5; }
  .btn-agree { background: #30d158; color: #000; flex: 1.4; }
  .btn-save { background: #0a84ff; flex: 1.4; }
  .hint { font-size: 11px; color: #8e8e93; text-align: center; }
</style>
</head>
<body>
  <header>
    <span class="pill" id="progress">0 / 0</span>
    <span id="city" style="color:#d1d1d6; font-weight:600; truncate"></span>
    <span class="pill" id="done-count">0 done</span>
  </header>

  <div id="stage">
    <img id="img" src="" alt="street image">
    <div id="swipe-badge"></div>
  </div>

  <div id="controls">
    <div class="grid">
      <div class="counter">
        <span class="lbl">Women ped.</span>
        <div class="stepper">
          <button onclick="adj('wc', -1)">-</button>
          <span class="val" id="wc">0</span>
          <button onclick="adj('wc', 1)">+</button>
        </div>
      </div>
      <div class="counter">
        <span class="lbl">Men ped.</span>
        <div class="stepper">
          <button onclick="adj('mc', -1)">-</button>
          <span class="val" id="mc">0</span>
          <button onclick="adj('mc', 1)">+</button>
        </div>
      </div>
      <div class="counter">
        <span class="lbl">Women 2W</span>
        <div class="stepper">
          <button onclick="adj('wt', -1)">-</button>
          <span class="val" id="wt">0</span>
          <button onclick="adj('wt', 1)">+</button>
        </div>
      </div>
      <div class="counter">
        <span class="lbl">Men 2W</span>
        <div class="stepper">
          <button onclick="adj('mt', -1)">-</button>
          <span class="val" id="mt">0</span>
          <button onclick="adj('mt', 1)">+</button>
        </div>
      </div>
      <div class="counter wide">
        <span class="lbl">Unclear / distant</span>
        <div class="stepper">
          <button onclick="adj('uc', -1)">-</button>
          <span class="val" id="uc">0</span>
          <button onclick="adj('uc', 1)">+</button>
        </div>
      </div>
    </div>

    <div class="actions">
      <button class="btn btn-prev" onclick="go(-1)">&#8592;</button>
      <button class="btn btn-flag" onclick="submit(1, false)">Bad</button>
      <button class="btn btn-agree" id="primary-btn"
        onclick="submit(0, true)">Agree &#8594;</button>
    </div>
    <div class="hint" id="hint">Swipe right = Agree &amp; Next &middot; Swipe left = Bad image
      &middot; Pinch to zoom</div>
  </div>

<script>
let items = [];
let idx = 0;
let cur = {wc: 0, mc: 0, wt: 0, mt: 0, uc: 0};
let edited = false;

async function init() {
  const res = await fetch('/api/items');
  items = await res.json();
  const firstTodo = items.findIndex(x => !x.human);
  idx = firstTodo >= 0 ? firstTodo : 0;
  render();
}

function render() {
  if (!items.length) return;
  const it = items[idx];
  const done = items.filter(x => x.human).length;
  document.getElementById('progress').textContent = `${idx + 1} / ${items.length}`;
  document.getElementById('done-count').textContent = `${done} done`;
  document.getElementById('city').textContent = it.city
    ? `${it.city} (${it.iso3})` : it.image.slice(0, 14);
  document.getElementById('img').src = `/image/${idx}`;

  const src = it.human || (!it.blind && it.llm) || {};
  cur = {
    wc: src.women_count || 0,
    mc: src.men_count || 0,
    wt: src.women_twowheeler || 0,
    mt: src.men_twowheeler || 0,
    uc: src.unclear_count || 0,
  };
  edited = false;
  syncVals();
}

function syncVals() {
  for (const k of ['wc','mc','wt','mt','uc']) {
    document.getElementById(k).textContent = cur[k];
  }
  const btn = document.getElementById('primary-btn');
  if (edited || items[idx]?.blind) {
    btn.className = 'btn btn-save';
    btn.innerHTML = 'Save &amp; Next &#8594;';
  } else {
    btn.className = 'btn btn-agree';
    btn.innerHTML = 'Agree &#8594;';
  }
}

function adj(k, delta) {
  cur[k] = Math.max(0, cur[k] + delta);
  edited = true;
  syncVals();
}

async function submit(badFlag, agreedLlm) {
  const it = items[idx];
  const payload = {
    image: it.image,
    path: it.path,
    women_count: cur.wc,
    men_count: cur.mc,
    women_twowheeler: cur.wt,
    men_twowheeler: cur.mt,
    unclear_count: cur.uc,
    bad_image: badFlag,
    agreed_llm: (!it.blind && it.llm && !edited && !badFlag && agreedLlm) ? 1 : 0,
  };
  await fetch('/api/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
  });
  it.human = payload;
  if (idx + 1 < items.length) idx++;
  render();
}

function go(delta) {
  idx = Math.max(0, Math.min(items.length - 1, idx + delta));
  render();
}

// Touch swipe support on image stage (single-finger horizontal swipe).
let startX = null, startY = null;
const stage = document.getElementById('stage');
const imgEl = document.getElementById('img');
const badge = document.getElementById('swipe-badge');

stage.addEventListener('touchstart', (e) => {
  if (e.touches.length === 1) {
    startX = e.touches[0].clientX;
    startY = e.touches[0].clientY;
  } else {
    startX = null;
  }
}, {passive: true});

stage.addEventListener('touchmove', (e) => {
  if (startX === null || e.touches.length !== 1) return;
  const dx = e.touches[0].clientX - startX;
  const dy = e.touches[0].clientY - startY;
  if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 20) {
    imgEl.style.transform = `translateX(${dx * 0.35}px)`;
    badge.style.opacity = '1';
    if (dx > 0) {
      badge.textContent = edited ? 'SAVE' : 'AGREE';
      badge.style.background = '#30d158';
      badge.style.color = '#000';
    } else {
      badge.textContent = 'BAD IMAGE';
      badge.style.background = '#ff453a';
      badge.style.color = '#fff';
    }
  }
}, {passive: true});

stage.addEventListener('touchend', (e) => {
  if (startX === null) return;
  const dx = e.changedTouches[0].clientX - startX;
  const dy = e.changedTouches[0].clientY - startY;
  imgEl.style.transform = '';
  badge.style.opacity = '0';
  startX = null;
  if (Math.abs(dx) > 85 && Math.abs(dx) > Math.abs(dy) * 1.4) {
    if (dx > 0) submit(0, true);
    else submit(1, false);
  }
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === 'ArrowRight') { e.preventDefault(); submit(0, true); }
  else if (e.key === 'ArrowLeft') { e.preventDefault(); go(-1); }
  else if (e.key.toLowerCase() === 'b') { e.preventDefault(); submit(1, false); }
});

init();
</script>
</body>
</html>
"""


def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images-dir", type=Path, default=Path("data/images/round1"))
    parser.add_argument("--llm-csv", type=Path, default=Path("outputs/muse_counts_round1.csv"))
    parser.add_argument("--meta-csv", type=Path, default=Path("outputs/selected_images.csv"))
    parser.add_argument("--out", type=Path, default=Path("outputs/human_annotations.csv"))
    parser.add_argument("--limit", type=int, default=200, help="Max images to queue (0 = all)")
    parser.add_argument("--blind", action="store_true", help="Hide LLM counts (blind coding)")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (0.0.0.0 for phone on LAN)")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    exts = {".jpg", ".jpeg", ".png", ".webp"}
    paths = sorted(p for p in args.images_dir.iterdir() if p.suffix.lower() in exts)
    if args.limit > 0:
        paths = paths[: args.limit]

    meta_by_uuid: dict[str, dict] = {}
    if args.meta_csv.exists():
        with args.meta_csv.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                meta_by_uuid[row["uuid"]] = row

    llm_by_name: dict[str, dict] = {}
    if args.llm_csv.exists():
        with args.llm_csv.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                llm_by_name[row["image"]] = {
                    "women_count": int(row["women_count"]),
                    "men_count": int(row["men_count"]),
                    "women_twowheeler": int(row["women_twowheeler"]),
                    "men_twowheeler": int(row["men_twowheeler"]),
                    "unclear_count": int(row["unclear_count"]),
                }

    human_by_name: dict[str, dict] = {}
    if args.out.exists():
        with args.out.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                human_by_name[row["image"]] = {
                    "image": row["image"],
                    "path": row["path"],
                    "women_count": int(row["women_count"]),
                    "men_count": int(row["men_count"]),
                    "women_twowheeler": int(row["women_twowheeler"]),
                    "men_twowheeler": int(row["men_twowheeler"]),
                    "unclear_count": int(row["unclear_count"]),
                    "bad_image": int(row["bad_image"]),
                    "agreed_llm": int(row.get("agreed_llm", 0)),
                }

    items = []
    for p in paths:
        u = p.stem
        m = meta_by_uuid.get(u, {})
        items.append(
            {
                "image": p.name,
                "path": str(p),
                "city": m.get("city_ascii", ""),
                "iso3": m.get("iso3", ""),
                "llm": llm_by_name.get(p.name),
                "human": human_by_name.get(p.name),
                "blind": args.blind,
            }
        )

    def flush_csv() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "image",
                    "path",
                    "women_count",
                    "men_count",
                    "women_twowheeler",
                    "men_twowheeler",
                    "unclear_count",
                    "bad_image",
                    "agreed_llm",
                ],
            )
            writer.writeheader()
            for name in sorted(human_by_name):
                writer.writerow(human_by_name[name])

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path).path
            if parsed == "/":
                body = HTML_PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parsed == "/api/items":
                body = json.dumps(items).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parsed.startswith("/image/"):
                idx = int(parsed.split("/")[-1])
                img_path = Path(items[idx]["path"])
                mime, _ = mimetypes.guess_type(img_path)
                data = img_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mime or "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            if urlparse(self.path).path == "/api/save":
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                human_by_name[payload["image"]] = payload
                flush_csv()
                self.send_response(200)
                self.end_headers()
            else:
                self.send_error(404)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer((args.host, args.port), Handler)
    ip = lan_ip()
    print(f"Serving {len(items)} images:")
    print(f"  Local : http://127.0.0.1:{args.port}/")
    if args.host == "0.0.0.0":
        print(f"  Phone : http://{ip}:{args.port}/  (same Wi-Fi or Tailscale)")
    print(f"Writing annotations to {args.out}")
    server.serve_forever()


if __name__ == "__main__":
    main()
