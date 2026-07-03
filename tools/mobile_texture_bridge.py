import base64
import json
import os
import re
import struct
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
UNALTERED = Path(os.environ.get(
    "MINIMALUS_UNALTERED_DIR",
    r"C:\Users\Administrator\Documents\Minimalus UI 3.0 Pipeline\working\Minimalus UI 3.0\UnalteredMobile",
))
BRIDGE_OUT = ROOT / "outputs" / "mobile_texture_bridge"
HOST = "127.0.0.1"
PORT = 8787

state = {
    "seq": 0,
    "command": "",
    "records": [],
    "dumps": [],
    "status": {},
    "preview": {},
    "commandExpiresAt": 0,
    "startedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
}
lock = threading.Lock()


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        return


def safe_part(value):
    text = str(value or "unknown")
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    return text[:80] or "unknown"


def rgba_to_dds_bytes(width, height, rgba):
    if len(rgba) != width * height * 4:
        raise ValueError(f"RGBA length mismatch: {len(rgba)} != {width}x{height}x4")
    bgra = bytearray(len(rgba))
    for i in range(0, len(rgba), 4):
        bgra[i] = rgba[i + 2]
        bgra[i + 1] = rgba[i + 1]
        bgra[i + 2] = rgba[i]
        bgra[i + 3] = rgba[i + 3]

    DDSD_CAPS = 0x1
    DDSD_HEIGHT = 0x2
    DDSD_WIDTH = 0x4
    DDSD_PITCH = 0x8
    DDSD_PIXELFORMAT = 0x1000
    DDPF_ALPHAPIXELS = 0x1
    DDPF_RGB = 0x40
    DDSCAPS_TEXTURE = 0x1000

    pitch = width * 4
    header = bytearray()
    header += b"DDS "
    header += struct.pack("<I", 124)
    header += struct.pack("<I", DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PITCH | DDSD_PIXELFORMAT)
    header += struct.pack("<I", height)
    header += struct.pack("<I", width)
    header += struct.pack("<I", pitch)
    header += struct.pack("<I", 0)
    header += struct.pack("<I", 1)
    header += bytes(44)
    header += struct.pack("<I", 32)
    header += struct.pack("<I", DDPF_RGB | DDPF_ALPHAPIXELS)
    header += struct.pack("<I", 0)
    header += struct.pack("<I", 32)
    header += struct.pack("<I", 0x00FF0000)
    header += struct.pack("<I", 0x0000FF00)
    header += struct.pack("<I", 0x000000FF)
    header += struct.pack("<I", 0xFF000000)
    header += struct.pack("<I", DDSCAPS_TEXTURE)
    header += struct.pack("<I", 0)
    header += struct.pack("<I", 0)
    header += struct.pack("<I", 0)
    header += struct.pack("<I", 0)
    if len(header) != 128:
        raise AssertionError(len(header))
    return bytes(header) + bytes(bgra)


def save_dump(record):
    width = int(record.get("width") or 0)
    height = int(record.get("height") or 0)
    rgba_b64 = record.get("rgbaBase64") or ""
    if not width or not height or not rgba_b64:
        return None
    rgba = base64.b64decode(rgba_b64)
    tex = safe_part(record.get("textureName") or record.get("textureId"))
    hsh = safe_part(record.get("hash") or record.get("originalHash"))
    stamp = time.strftime("%Y%m%d_%H%M%S")
    stem = f"AndroidMobile_{width}x{height}_{hsh}_tex{tex}_{stamp}"
    dds = rgba_to_dds_bytes(width, height, rgba)

    UNALTERED.mkdir(parents=True, exist_ok=True)
    BRIDGE_OUT.mkdir(parents=True, exist_ok=True)
    dds_path = UNALTERED / f"{stem}.dds"
    json_path = UNALTERED / f"{stem}.json"
    mirror_json = BRIDGE_OUT / f"{stem}.json"
    dds_path.write_bytes(dds)
    clean = dict(record)
    clean.pop("rgbaBase64", None)
    clean.update({
        "savedDds": str(dds_path),
        "savedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    json_text = json.dumps(clean, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    mirror_json.write_text(json_text, encoding="utf-8")
    return clean


def rgba_to_png_bytes(width, height, rgba):
    if len(rgba) != width * height * 4:
        raise ValueError(f"RGBA length mismatch: {len(rgba)} != {width}x{height}x4")

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    rows = bytearray()
    stride = width * 4
    for y in range(height):
        rows.append(0)
        start = y * stride
        rows.extend(rgba[start:start + stride])
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + chunk(b"IEND", b"")
    )


def save_preview(record):
    width = int(record.get("width") or 0)
    height = int(record.get("height") or 0)
    rgba_b64 = record.get("rgbaBase64") or ""
    if not width or not height or not rgba_b64:
        return None
    rgba = base64.b64decode(rgba_b64)
    tex = safe_part(record.get("textureName") or record.get("textureId"))
    hsh = safe_part(record.get("hash") or record.get("originalHash"))
    stem = f"preview_{width}x{height}_{hsh}_tex{tex}.png"
    BRIDGE_OUT.mkdir(parents=True, exist_ok=True)
    png_path = BRIDGE_OUT / stem
    png_path.write_bytes(rgba_to_png_bytes(width, height, rgba))
    clean = dict(record)
    clean.pop("rgbaBase64", None)
    clean.update({
        "previewPng": f"/preview/{stem}",
        "previewPath": str(png_path),
        "savedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    return clean


def html():
    with lock:
        status = dict(state["status"])
        dumps = list(state["dumps"][-30:])
        records = list(state["records"][-20:])
        preview = dict(state["preview"])
        seq = state["seq"]
    dump_rows = "\n".join(
        f"<tr><td>{d.get('savedAt','')}</td><td>{d.get('width')}x{d.get('height')}</td>"
        f"<td>{d.get('hash') or d.get('originalHash')}</td><td>{d.get('textureName') or d.get('textureId')}</td>"
        f"<td><code>{d.get('savedDds','')}</code></td></tr>"
        for d in reversed(dumps)
    )
    record_rows = "\n".join(
        f"<tr><td>{r.get('kind','')}</td><td>{r.get('width','')}x{r.get('height','')}</td>"
        f"<td>{r.get('hash') or r.get('originalHash') or ''}</td><td>{r.get('textureName') or r.get('textureId') or ''}</td></tr>"
        for r in reversed(records)
    )
    status_json = json.dumps(status, indent=2)
    preview_html = "<p>No preview yet.</p>"
    if preview.get("previewPng"):
        preview_html = (
            f"<p>{preview.get('browserIndex','?')}/{preview.get('browserTotal','?')} "
            f"{preview.get('width')}x{preview.get('height')} "
            f"hash {preview.get('hash') or preview.get('originalHash') or ''} "
            f"tex {preview.get('textureName') or preview.get('textureId') or ''}</p>"
            f"<img src=\"{preview.get('previewPng')}?t={int(time.time())}\" "
            f"style=\"image-rendering:pixelated;max-width:512px;max-height:512px;background:#333;border:1px solid #666\">"
        )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>Minimalus Mobile Texture Bridge</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:20px;background:#111;color:#eee}}
button{{font-size:16px;margin:4px;padding:8px 12px}}
code,pre{{background:#222;color:#9f9;padding:3px 5px}}
table{{border-collapse:collapse;width:100%;margin-top:12px}}
td,th{{border:1px solid #444;padding:6px;text-align:left;font-size:13px}}
.bar{{position:sticky;top:0;background:#111;padding-bottom:10px}}
</style>
<div class="bar">
<h1>Minimalus Mobile Texture Bridge</h1>
<p>Command seq: {seq}. ADB route: <code>adb reverse tcp:8787 tcp:8787</code></p>
<form method="post" action="/cmd">
<button name="command" value="capture_on">Capture On</button>
<button name="command" value="capture_off">Capture Off</button>
<button name="command" value="reset_capture_on">Fresh Capture</button>
<button name="command" value="reset">Reset Android</button>
<button name="command" value="pc_reset">Reset PC</button>
<button name="command" value="filter_ui">UI Filter</button>
<button name="command" value="filter_minimalus">Minimalus Sizes</button>
<button name="command" value="filter_all">Broad Sizes</button>
<button name="command" value="prev">Prev</button>
<button name="command" value="prev10">Prev 10</button>
<button name="command" value="next">Next</button>
<button name="command" value="next10">Next 10</button>
<button name="command" value="show">Preview Selected</button>
<button name="command" value="restore">Restore</button>
<button name="command" value="dump">Dump Selected</button>
<button name="command" value="status">Status</button>
</form>
</div>
<h2>Status</h2>
<pre>{status_json}</pre>
<h2>Saved Dumps</h2>
<table><tr><th>Saved</th><th>Size</th><th>Hash</th><th>Texture</th><th>DDS</th></tr>{dump_rows}</table>
<h2>Preview</h2>
{preview_html}
<h2>Recent Records</h2>
<table><tr><th>Kind</th><th>Size</th><th>Hash</th><th>Texture</th></tr>{record_rows}</table>
<script>setTimeout(()=>location.reload(),1500)</script>
"""


class Handler(BaseHTTPRequestHandler):
    def cors(self, content_type="application/json"):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", content_type)

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            body = html().encode("utf-8")
            self.send_response(200)
            self.cors("text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/gw-command":
            with lock:
                command = state["command"] if time.time() < state.get("commandExpiresAt", 0) else ""
                payload = {"seq": state["seq"], "command": command}
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.cors()
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path.startswith("/preview/"):
            file_path = BRIDGE_OUT / Path(parsed.path).name
            if file_path.exists() and file_path.is_file():
                body = file_path.read_bytes()
                self.send_response(200)
                self.cors("image/png")
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_error(404)
            return
        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length)
        if parsed.path == "/cmd":
            params = parse_qs(raw.decode("utf-8", errors="replace"))
            command = (params.get("command") or [""])[0]
            with lock:
                if command == "pc_reset":
                    state["records"] = []
                    state["dumps"] = []
                    state["status"] = {}
                    state["preview"] = {}
                else:
                    state["seq"] += 1
                    state["command"] = command
                    state["commandExpiresAt"] = time.time() + 6
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return
        if parsed.path == "/gw-texture":
            try:
                record = json.loads(raw.decode("utf-8", errors="replace"))
            except Exception as exc:
                record = {"kind": "bridge.parse_error", "error": str(exc), "raw": raw[:200].decode("utf-8", errors="replace")}
            saved = None
            preview = None
            if record.get("kind") == "bridge.dump":
                try:
                    saved = save_dump(record)
                except Exception as exc:
                    saved = {"kind": "bridge.save_error", "error": str(exc)}
            elif record.get("kind") == "bridge.preview":
                try:
                    preview = save_preview(record)
                except Exception as exc:
                    preview = {"kind": "bridge.preview_error", "error": str(exc)}
            with lock:
                if record.get("kind") == "bridge.status":
                    state["status"] = record
                elif record.get("kind") == "bridge.preview":
                    state["preview"] = preview or {}
                else:
                    small = dict(record)
                    if "rgbaBase64" in small:
                        small["rgbaBase64"] = f"<{len(small['rgbaBase64'])} chars>"
                    state["records"].append(small)
                    state["records"] = state["records"][-200:]
                if saved:
                    state["dumps"].append(saved)
            self.send_response(204)
            self.cors()
            self.end_headers()
            return
        self.send_error(404)

    def log_message(self, fmt, *args):
        return


def main():
    BRIDGE_OUT.mkdir(parents=True, exist_ok=True)
    print(f"Minimalus Mobile Texture Bridge")
    print(f"Open http://{HOST}:{PORT}/")
    print(f"Dumps write to: {UNALTERED}")
    QuietThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
