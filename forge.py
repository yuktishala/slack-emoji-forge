#!/usr/bin/env python3
"""
slack-emoji-forge: Generate totem identity icons for Fiat agents.

Design:
  - 128x128 canvas with #1a1d21 background (Slack dark mode)
  - Emoji centered at 100% canvas fill
  - One PNG per species — no role overlays

Output naming: {species}.png (e.g., fox.png, nova.png)
Icon URL: https://raw.githubusercontent.com/yuktishala/slack-emoji-forge/main/output/{species}.png

Usage:
  python forge.py                    # Generate all species
  python forge.py --species fox,ant  # Generate specific species only
  python forge.py --download-only    # Just download Noto sources
  python forge.py --catalog          # Generate catalog.html and exit
"""

import argparse
import json
import sys
from pathlib import Path

import requests
from PIL import Image

try:
    import cairosvg
    HAS_CAIRO = True
except ImportError:
    HAS_CAIRO = False

REPO_ROOT = Path(__file__).parent
SOURCES_DIR = REPO_ROOT / "sources"
OUTPUT_DIR = REPO_ROOT / "output"
SPECIES_FILE = REPO_ROOT / "species.json"

# Google Noto Emoji CDN (pre-rendered 128px PNGs)
NOTO_PNG_URL = "https://raw.githubusercontent.com/googlefonts/noto-emoji/main/png/128/emoji_u{codepoint}.png"
NOTO_SVG_URL = "https://raw.githubusercontent.com/googlefonts/noto-emoji/main/svg/emoji_u{codepoint}.svg"

ICON_SIZE = 128
BG_COLOR = (26, 29, 33, 255)  # #1a1d21 — Slack dark mode


def load_species() -> dict:
    with open(SPECIES_FILE) as f:
        return json.load(f)


def download_source(species: str, codepoint: str) -> Path:
    """Download Noto emoji PNG for a species. Falls back to SVG + rasterize."""
    png_path = SOURCES_DIR / f"{species}.png"
    if png_path.exists():
        return png_path

    url = NOTO_PNG_URL.format(codepoint=codepoint)
    resp = requests.get(url, timeout=15)
    if resp.status_code == 200:
        png_path.write_bytes(resp.content)
        return png_path

    if not HAS_CAIRO:
        print(f"  SKIP {species}: PNG not found and cairosvg not available", file=sys.stderr)
        return None

    svg_url = NOTO_SVG_URL.format(codepoint=codepoint)
    resp = requests.get(svg_url, timeout=15)
    if resp.status_code != 200:
        print(f"  SKIP {species}: not found (codepoint {codepoint})", file=sys.stderr)
        return None

    png_data = cairosvg.svg2png(bytestring=resp.content, output_width=ICON_SIZE, output_height=ICON_SIZE)
    png_path.write_bytes(png_data)
    return png_path


def composite(base_path: Path, output_path: Path):
    """Composite: dark background + full-size emoji."""
    canvas = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), BG_COLOR)
    emoji = Image.open(base_path).convert("RGBA").resize(
        (ICON_SIZE, ICON_SIZE), Image.LANCZOS
    )
    canvas.alpha_composite(emoji)
    canvas.save(output_path, "PNG", optimize=True)


def generate_catalog(species: dict, catalog_path: Path):
    """Generate catalog.html listing all totem species."""
    rows = []
    for slug in sorted(species.keys()):
        cp = species[slug]
        rows.append(
            f"<tr>"
            f"<td><img src=\"output/{slug}.png\" width=\"64\" height=\"64\" title=\"{slug}\"></td>"
            f"<td><code>{slug}</code></td>"
            f"<td><code>U+{cp.upper()}</code></td>"
            f"</tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>slack-emoji-forge — {len(species)} totems</title>
<style>
  body {{ font-family: monospace; background: #1a1d21; color: #d1d2d3; padding: 16px; }}
  h1 {{ color: #fff; }}
  table {{ border-collapse: collapse; }}
  th, td {{ padding: 6px 10px; border: 1px solid #333; text-align: center; vertical-align: middle; }}
  th {{ background: #222529; }}
  tr:hover {{ background: #222529; }}
  img {{ display: block; margin: auto; }}
</style>
</head>
<body>
<h1>slack-emoji-forge &mdash; {len(species)} totems</h1>
<table>
<tr><th>icon</th><th>slug</th><th>codepoint</th></tr>
{"".join(rows)}
</table>
</body>
</html>
"""
    catalog_path.write_text(html, encoding="utf-8")
    print(f"Catalog written: {catalog_path} ({len(species)} totems)")


def main():
    parser = argparse.ArgumentParser(description="Forge Fiat totem identity icons")
    parser.add_argument("--species", help="Comma-separated species to generate (default: all)")
    parser.add_argument("--download-only", action="store_true", help="Only download source icons")
    parser.add_argument("--catalog", action="store_true", help="Generate catalog.html and exit")
    args = parser.parse_args()

    SOURCES_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    all_species = load_species()

    if args.catalog:
        generate_catalog(all_species, REPO_ROOT / "catalog.html")
        return

    selected = args.species.split(",") if args.species else list(all_species.keys())

    print(f"Downloading {len(selected)} species icons...")
    downloaded = {}
    for species in selected:
        codepoint = all_species.get(species)
        if not codepoint:
            print(f"  SKIP {species}: not in species.json", file=sys.stderr)
            continue
        path = download_source(species, codepoint)
        if path:
            downloaded[species] = path
            print(f"  OK {species}")

    print(f"\nDownloaded {len(downloaded)}/{len(selected)} species")

    if args.download_only:
        return

    count = 0
    for species, source_path in downloaded.items():
        out = OUTPUT_DIR / f"{species}.png"
        composite(source_path, out)
        count += 1
        print(f"  {species}.png")

    print(f"\nForged {count} icons in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
