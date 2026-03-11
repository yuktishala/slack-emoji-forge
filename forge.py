#!/usr/bin/env python3
"""
slack-emoji-forge: Generate per-species, per-role Slack custom emoji.

Downloads Noto Emoji SVGs from Google, composites a role badge in the
bottom-right corner, and outputs 128x128 PNGs named for Slack upload:
  {species}-hand.png, {species}-buddy.png

Usage:
  python forge.py                    # Generate all species x all roles
  python forge.py --species fox,ant  # Generate specific species only
  python forge.py --roles hand       # Generate only hand badges
  python forge.py --download-only    # Just download sources, no compositing
"""

import argparse
import json
import os
import sys
from io import BytesIO
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
BADGES_DIR = REPO_ROOT / "badges"
OUTPUT_DIR = REPO_ROOT / "output"
SPECIES_FILE = REPO_ROOT / "species.json"

# Google Noto Emoji CDN (pre-rendered 128px PNGs)
NOTO_PNG_URL = "https://raw.githubusercontent.com/googlefonts/noto-emoji/main/png/128/emoji_u{codepoint}.png"
# Fallback: SVG source
NOTO_SVG_URL = "https://raw.githubusercontent.com/googlefonts/noto-emoji/main/svg/emoji_u{codepoint}.svg"

ICON_SIZE = 128
BADGE_SIZE = 48
BADGE_OFFSET = ICON_SIZE - BADGE_SIZE  # bottom-right corner

# Role definitions: name -> badge filename
ROLES = {
    "hand": "hand.png",
    "buddy": "buddy.png",
}


def load_species() -> dict:
    with open(SPECIES_FILE) as f:
        return json.load(f)


def download_source(species: str, codepoint: str) -> Path:
    """Download Noto emoji PNG for a species. Falls back to SVG + rasterize."""
    png_path = SOURCES_DIR / f"{species}.png"
    if png_path.exists():
        return png_path

    # Try pre-rendered PNG first
    url = NOTO_PNG_URL.format(codepoint=codepoint)
    resp = requests.get(url, timeout=15)
    if resp.status_code == 200:
        png_path.write_bytes(resp.content)
        return png_path

    # Fallback: SVG → rasterize
    if not HAS_CAIRO:
        print(f"  SKIP {species}: PNG not found and cairosvg not installed", file=sys.stderr)
        return None

    svg_url = NOTO_SVG_URL.format(codepoint=codepoint)
    resp = requests.get(svg_url, timeout=15)
    if resp.status_code != 200:
        print(f"  SKIP {species}: neither PNG nor SVG found (codepoint {codepoint})", file=sys.stderr)
        return None

    png_data = cairosvg.svg2png(bytestring=resp.content, output_width=ICON_SIZE, output_height=ICON_SIZE)
    png_path.write_bytes(png_data)
    return png_path


def load_badge(role: str) -> Image.Image | None:
    """Load and resize a role badge."""
    badge_file = BADGES_DIR / ROLES[role]
    if not badge_file.exists():
        return None
    badge = Image.open(badge_file).convert("RGBA")
    return badge.resize((BADGE_SIZE, BADGE_SIZE), Image.LANCZOS)


def composite(base_path: Path, badge: Image.Image | None, output_path: Path):
    """Composite base icon with optional badge overlay."""
    base = Image.open(base_path).convert("RGBA").resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)

    if badge is not None:
        base.alpha_composite(badge, dest=(BADGE_OFFSET, BADGE_OFFSET))

    base.save(output_path, "PNG", optimize=True)


def generate_placeholder_badges():
    """Generate simple colored circle badges if none exist."""
    colors = {
        "hand": (66, 133, 244, 220),    # blue
        "buddy": (251, 188, 4, 220),     # yellow
    }
    for role, color in colors.items():
        path = BADGES_DIR / f"{role}.png"
        if path.exists():
            continue
        img = Image.new("RGBA", (BADGE_SIZE, BADGE_SIZE), (0, 0, 0, 0))
        # Draw a filled circle
        for y in range(BADGE_SIZE):
            for x in range(BADGE_SIZE):
                cx, cy = BADGE_SIZE / 2, BADGE_SIZE / 2
                if (x - cx) ** 2 + (y - cy) ** 2 <= (cx - 2) ** 2:
                    img.putpixel((x, y), color)
        img.save(path, "PNG")
        print(f"  Generated placeholder badge: {path.name}")


def main():
    parser = argparse.ArgumentParser(description="Forge Slack custom emoji from Noto + role badges")
    parser.add_argument("--species", help="Comma-separated species to generate (default: all)")
    parser.add_argument("--roles", help="Comma-separated roles (default: all)", default=",".join(ROLES.keys()))
    parser.add_argument("--download-only", action="store_true", help="Only download source icons")
    parser.add_argument("--no-badge", action="store_true", help="Generate plain icons without badge overlay")
    args = parser.parse_args()

    SOURCES_DIR.mkdir(exist_ok=True)
    BADGES_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    all_species = load_species()
    selected = args.species.split(",") if args.species else list(all_species.keys())
    roles = args.roles.split(",")

    # Download sources
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

    # Generate placeholder badges if needed
    generate_placeholder_badges()

    # Load badges
    badges = {}
    for role in roles:
        if role not in ROLES:
            print(f"  SKIP role '{role}': not defined", file=sys.stderr)
            continue
        badges[role] = load_badge(role) if not args.no_badge else None

    # Composite
    count = 0
    for species, source_path in downloaded.items():
        for role, badge in badges.items():
            out = OUTPUT_DIR / f"{species}-{role}.png"
            composite(source_path, badge, out)
            count += 1

    print(f"\nForged {count} emoji in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
