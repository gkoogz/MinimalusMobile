import base64
import json
import os
import re
import shutil
import subprocess
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIPELINE = Path(os.environ.get(
    "MINIMALUS_PIPELINE_DIR",
    r"C:\Users\Administrator\Documents\Minimalus UI 3.0 Pipeline\working\Minimalus UI 3.0",
))
ALTERED = PIPELINE / "Altered"
UNALTERED = PIPELINE / "Unaltered"
ALTERED_MOBILE = PIPELINE / "AlteredMobile"
UNALTERED_MOBILE = PIPELINE / "UnalteredMobile"
TEXCONV = Path(r"C:\Program Files (x86)\Microsoft DirectX SDK (June 2010)\Utilities\bin\x64\texconv.exe")
CLIENT_JS = ROOT / "app" / "src" / "main" / "assets" / "public" / "astro" / "client-main.js"
OUT_DIR = ROOT / "outputs"
OUT_JSON = OUT_DIR / "minimalus_mobile_replacements_full.json"
OUT_MD = OUT_DIR / "minimalus_mobile_replacements_full.md"
OUT_SKIPPED = OUT_DIR / "minimalus_mobile_replacements_skipped.md"
ALIAS_JSON = ROOT / "tools" / "mobile_texture_aliases.json"
TMP = ROOT / "build" / "dds_to_tga_tmp"


def texture_id(name: str) -> str:
    match = re.search(r"0x([0-9a-fA-F]{8})", name, re.I)
    if match:
        return "0x" + match.group(1).upper()
    match = re.search(r"AndroidMobile_[^_]+_([0-9a-fA-F]{8})_tex([0-9]+)_", name)
    if match:
        return "AndroidMobile:" + match.group(1).lower() + ":tex" + match.group(2)
    return Path(name).stem


def convert_to_tga(dds: Path) -> Path:
    TMP.mkdir(parents=True, exist_ok=True)
    for child in TMP.glob("*"):
        child.unlink()
    command = [str(TEXCONV), "-nologo", "-ft", "tga", "-m", "1", "-o", str(TMP), str(dds)]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"texconv failed for {dds}\n{result.stdout}\n{result.stderr}")
    files = list(TMP.glob("*.tga"))
    if len(files) != 1:
        raise RuntimeError(f"Expected one TGA for {dds}, found {files}")
    return files[0]


def read_tga_rgba(tga: Path) -> tuple[int, int, bytes]:
    data = tga.read_bytes()
    if len(data) < 18:
        raise ValueError(f"Short TGA: {tga}")
    image_id_len = data[0]
    color_map_type = data[1]
    image_type = data[2]
    width = data[12] | (data[13] << 8)
    height = data[14] | (data[15] << 8)
    bpp = data[16]
    descriptor = data[17]
    if color_map_type != 0 or image_type != 2 or bpp not in (24, 32):
        raise ValueError(f"Unsupported TGA {tga}: type={image_type} colorMap={color_map_type} bpp={bpp}")
    pixel_size = bpp // 8
    offset = 18 + image_id_len
    raw = data[offset:offset + width * height * pixel_size]
    if len(raw) != width * height * pixel_size:
        raise ValueError(f"Unexpected TGA pixel length for {tga}")
    rgba = bytearray(width * height * 4)
    for i in range(width * height):
        src = i * pixel_size
        dst = i * 4
        rgba[dst] = raw[src + 2]
        rgba[dst + 1] = raw[src + 1]
        rgba[dst + 2] = raw[src]
        rgba[dst + 3] = raw[src + 3] if pixel_size == 4 else 255
    top_origin = bool(descriptor & 0x20)
    if not top_origin:
        row = width * 4
        rows = [bytes(rgba[i * row:(i + 1) * row]) for i in range(height)]
        rgba = bytearray().join(reversed(rows))
    return width, height, bytes(rgba)


def dds_to_rgba(dds: Path) -> tuple[int, int, bytes]:
    return read_tga_rgba(convert_to_tga(dds))


def read_png_rgba(png: Path) -> tuple[int, int, bytes]:
    data = png.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"Not a PNG: {png}")

    pos = 8
    width = height = color_type = bit_depth = None
    compressed = bytearray()
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(">IIBBBBB", chunk)
            if bit_depth != 8 or color_type not in (2, 6) or compression != 0 or filter_method != 0 or interlace != 0:
                raise ValueError(f"Unsupported PNG format for {png}")
        elif kind == b"IDAT":
            compressed.extend(chunk)
        elif kind == b"IEND":
            break

    if width is None or height is None:
        raise ValueError(f"PNG missing IHDR: {png}")

    channels = 4 if color_type == 6 else 3
    stride = width * channels
    raw = zlib.decompress(bytes(compressed))
    rows = []
    src = 0
    previous = bytearray(stride)
    for _ in range(height):
        filter_type = raw[src]
        src += 1
        row = bytearray(raw[src:src + stride])
        src += stride
        for i in range(stride):
            left = row[i - channels] if i >= channels else 0
            up = previous[i]
            up_left = previous[i - channels] if i >= channels else 0
            if filter_type == 1:
                row[i] = (row[i] + left) & 0xFF
            elif filter_type == 2:
                row[i] = (row[i] + up) & 0xFF
            elif filter_type == 3:
                row[i] = (row[i] + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                p = left + up - up_left
                pa = abs(p - left)
                pb = abs(p - up)
                pc = abs(p - up_left)
                predictor = left if pa <= pb and pa <= pc else up if pb <= pc else up_left
                row[i] = (row[i] + predictor) & 0xFF
            elif filter_type != 0:
                raise ValueError(f"Unsupported PNG filter {filter_type} in {png}")
        previous = row
        rows.append(row)

    rgba = bytearray(width * height * 4)
    for y, row in enumerate(rows):
        for x in range(width):
            src_i = x * channels
            dst_i = (y * width + x) * 4
            rgba[dst_i] = row[src_i]
            rgba[dst_i + 1] = row[src_i + 1]
            rgba[dst_i + 2] = row[src_i + 2]
            rgba[dst_i + 3] = row[src_i + 3] if channels == 4 else 255
    return width, height, bytes(rgba)


def image_to_rgba(path: Path) -> tuple[int, int, bytes]:
    if path.suffix.lower() == ".png":
        return read_png_rgba(path)
    return dds_to_rgba(path)


def fnv1a(data: bytes) -> str:
    value = 0x811C9DC5
    for byte in data:
        value ^= byte
        value = (value * 0x01000193) & 0xFFFFFFFF
    return f"{value:08x}"


def patch_client_js(replacements: dict) -> None:
    source = CLIENT_JS.read_text(encoding="utf-8", errors="replace")
    replacement_json = json.dumps(replacements, separators=(",", ":"))
    sizes = sorted({f"{entry['width']}x{entry['height']}" for entry in replacements.values()})
    sizes_json = json.dumps({size: True for size in sizes}, separators=(",", ":"))
    pattern = re.compile(
        r"window\.__gwMinimalusReplacements=\{.*?\};"
        r"window\.__gwMinimalusReplacementSizes=\{.*?\};"
        r"console\.log\('\[gw-minimalus\] replacements loaded',Object\.keys\(window\.__gwMinimalusReplacements\)\.length\);",
        re.S,
    )
    replacement = (
        "window.__gwMinimalusReplacements=" + replacement_json + ";"
        "window.__gwMinimalusReplacementSizes=" + sizes_json + ";"
        "console.log('[gw-minimalus] replacements loaded',Object.keys(window.__gwMinimalusReplacements).length);"
    )
    patched, count = pattern.subn(replacement, source, count=1)
    if count != 1:
        raise RuntimeError("Could not patch embedded Minimalus replacement table")
    CLIENT_JS.write_text(patched, encoding="utf-8")


def add_layer(replacements: dict, rows: list[dict], skipped: list[dict], label: str, altered_dir: Path, unaltered_dir: Path) -> None:
    all_altered_files = [
        p for p in altered_dir.iterdir()
        if p.is_file() and p.suffix.lower() in (".dds", ".png")
    ]
    dds_stems = {p.stem.lower() for p in all_altered_files if p.suffix.lower() == ".dds"}
    altered_files = [
        p for p in all_altered_files
        if p.suffix.lower() == ".dds" or p.stem.lower() not in dds_stems
    ]
    for altered in sorted(altered_files, key=lambda p: p.name.lower()):
        if label == "pc" and altered.name.startswith("AndroidMobile_"):
            continue
        unaltered = unaltered_dir / altered.name
        if not unaltered.exists() and altered.suffix.lower() == ".png":
            unaltered = unaltered_dir / (altered.stem + ".dds")
        if not unaltered.exists():
            skipped.append({
                "layer": label,
                "file": altered.name,
                "reason": "missing unaltered fingerprint source",
            })
            continue
        ow, oh, original_rgba = dds_to_rgba(unaltered)
        aw, ah, altered_rgba = image_to_rgba(altered)
        if (ow, oh) != (aw, ah):
            raise ValueError(f"Dimension mismatch for {altered.name}: original {ow}x{oh}, altered {aw}x{ah}")
        if len(original_rgba) != len(altered_rgba):
            raise ValueError(f"Byte length mismatch for {altered.name}")
        key = f"{ow}x{oh}:{fnv1a(original_rgba)}"
        existing = replacements.get(key)
        replacements[key] = {
            "texmodHash": texture_id(altered.name),
            "source": label,
            "file": altered.name,
            "width": ow,
            "height": oh,
            "rgbaBase64": base64.b64encode(altered_rgba).decode("ascii"),
        }
        rows.append({
            "layer": label,
            "file": altered.name,
            "key": key,
            "size": f"{ow}x{oh}",
            "status": "overrode-existing-key" if existing else "added",
            "previousSource": existing.get("source", "") if isinstance(existing, dict) else "",
        })


def pipeline_path(relative_path: str) -> Path:
    normalized = relative_path.replace("/", os.sep).replace("\\", os.sep)
    return PIPELINE / normalized


def add_aliases(replacements: dict, rows: list[dict], skipped: list[dict]) -> set[str]:
    if not ALIAS_JSON.exists():
        return set()
    aliases = json.loads(ALIAS_JSON.read_text(encoding="utf-8"))
    aliased_files: set[str] = set()
    for alias in aliases:
        label = alias.get("layer", "mobile-alias")
        altered = pipeline_path(alias["altered"])
        unaltered = pipeline_path(alias["unaltered"])
        aliased_files.add(altered.name)
        if not altered.exists():
            skipped.append({
                "layer": label,
                "file": alias["altered"],
                "reason": "missing aliased altered texture",
            })
            continue
        if not unaltered.exists():
            skipped.append({
                "layer": label,
                "file": alias["altered"],
                "reason": "missing aliased mobile fingerprint source",
            })
            continue
        ow, oh, original_rgba = dds_to_rgba(unaltered)
        aw, ah, altered_rgba = image_to_rgba(altered)
        if (ow, oh) != (aw, ah):
            raise ValueError(f"Dimension mismatch for alias {altered.name}: original {ow}x{oh}, altered {aw}x{ah}")
        key = f"{ow}x{oh}:{fnv1a(original_rgba)}"
        existing = replacements.get(key)
        replacements[key] = {
            "texmodHash": texture_id(altered.name),
            "source": label,
            "file": altered.name,
            "width": ow,
            "height": oh,
            "rgbaBase64": base64.b64encode(altered_rgba).decode("ascii"),
        }
        rows.append({
            "layer": label,
            "file": f"{altered.name} -> {unaltered.name}",
            "key": key,
            "size": f"{ow}x{oh}",
            "status": "overrode-existing-key" if existing else "added",
            "previousSource": existing.get("source", "") if isinstance(existing, dict) else "",
        })
    return aliased_files


def main() -> None:
    if not TEXCONV.exists():
        raise SystemExit(f"texconv not found: {TEXCONV}")
    for folder in [ALTERED, UNALTERED, ALTERED_MOBILE, UNALTERED_MOBILE]:
        if not folder.exists():
            raise SystemExit(f"missing folder: {folder}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    replacements: dict = {}
    rows: list[dict] = []
    skipped: list[dict] = []
    add_layer(replacements, rows, skipped, "pc", ALTERED, UNALTERED)
    add_layer(replacements, rows, skipped, "mobile", ALTERED_MOBILE, UNALTERED_MOBILE)
    aliased_files = add_aliases(replacements, rows, skipped)
    skipped = [
        row for row in skipped
        if not (row["layer"] == "pc" and row["file"] in aliased_files)
    ]

    OUT_JSON.write_text(json.dumps(replacements, indent=2), encoding="utf-8")
    patch_client_js(replacements)

    lines = [
        "# Minimalus Mobile Replacement Table",
        "",
        f"Total entries: {len(replacements)}",
        f"PC altered textures: {sum(1 for row in rows if row['layer'] == 'pc')}",
        f"Mobile altered textures: {sum(1 for row in rows if row['layer'] == 'mobile')}",
        "",
        "Priority order:",
        "",
        "1. PC `Altered` textures",
        "2. Mobile `AlteredMobile` textures",
        "3. Explicit mobile aliases in `tools/mobile_texture_aliases.json`",
        "",
        "| Layer | Texture | Runtime key | Size | Status |",
        "|---|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(f"| {row['layer']} | `{row['file']}` | `{row['key']}` | {row['size']} | {row['status']} |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    skipped_lines = [
        "# Minimalus Mobile Skipped Texture Inputs",
        "",
        "These altered files were present but could not be converted into runtime replacements.",
        "",
        "| Layer | Texture | Reason |",
        "|---|---|---|",
    ]
    for row in skipped:
        skipped_lines.append(f"| {row['layer']} | `{row['file']}` | {row['reason']} |")
    OUT_SKIPPED.write_text("\n".join(skipped_lines) + "\n", encoding="utf-8")
    shutil.rmtree(TMP, ignore_errors=True)
    print(f"entries={len(replacements)} pc={sum(1 for r in rows if r['layer']=='pc')} mobile={sum(1 for r in rows if r['layer']=='mobile')} skipped={len(skipped)}")
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_MD}")
    print(f"wrote {OUT_SKIPPED}")
    print(f"patched {CLIENT_JS}")


if __name__ == "__main__":
    main()
