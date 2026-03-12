#!/usr/bin/env python3
"""
slack-emoji-forge: Generate per-species, per-role Slack avatar icons.

Design (v12 frozen):
  - 128x128 canvas with #1a1d21 background (Slack dark mode)
  - 80% animal emoji, positioned top-left
  - ~30% area role badge, bottom-right, with moderate drop shadow
  - Hand badge: medium-light skin tone hand (Noto Emoji)
  - Buddy badge: eye emoji (Noto Emoji)

Output naming: {species}-{role}.png (e.g., fox-hand.png, fox-buddy.png)
Startup.sh resolves icon_url as:
  https://raw.githubusercontent.com/yuktishala/slack-emoji-forge/main/output/{species}-{role}.png

Usage:
  python forge.py                    # Generate all species x all roles
  python forge.py --species fox,ant  # Generate specific species only
  python forge.py --roles hand       # Generate only hand badges
  python forge.py --download-only    # Just download sources, no compositing
"""

import argparse
import json
import math
import sys
from pathlib import Path

import requests
from PIL import Image, ImageFilter

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

# === v12 Design Constants ===
ICON_SIZE = 128
BG_COLOR = (26, 29, 33, 255)  # #1a1d21 — Slack dark mode chat background

# Animal: 80% of canvas, top-left aligned
ANIMAL_SIZE = int(ICON_SIZE * 0.80)  # 102px
ANIMAL_OFFSET = (0, 0)

# Badge: ~30% of canvas area → sqrt(0.30) * 128 ≈ 70px
BADGE_SIZE = 70
BADGE_OFFSET = (ICON_SIZE - BADGE_SIZE, ICON_SIZE - BADGE_SIZE)  # bottom-right

# Drop shadow for badge
SHADOW_SPREAD = 6
SHADOW_BLUR = 5
SHADOW_ALPHA_MULT = 1.5  # boost shadow opacity

# Role definitions: name -> badge filename
ROLES = {
    "hand": "hand-medium-light.png",
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
    """Load badge image for a role."""
    badge_file = BADGES_DIR / ROLES[role]
    if not badge_file.exists():
        print(f"  WARNING: badge not found: {badge_file}", file=sys.stderr)
        return None
    return Image.open(badge_file).convert("RGBA")


def make_shadow(badge: Image.Image) -> Image.Image:
    """Create a drop shadow from the badge's alpha channel."""
    # Extract alpha as grayscale shadow
    alpha = badge.split()[3]

    # Create shadow layer (black with badge's alpha, boosted)
    shadow = Image.new("RGBA", badge.size, (0, 0, 0, 0))
    for y in range(badge.height):
        for x in range(badge.width):
            a = alpha.getpixel((x, y))
            boosted = min(255, int(a * SHADOW_ALPHA_MULT))
            shadow.putpixel((x, y), (0, 0, 0, boosted))

    # Expand shadow by spread amount
    expanded_size = (badge.width + SHADOW_SPREAD * 2, badge.height + SHADOW_SPREAD * 2)
    shadow_expanded = Image.new("RGBA", expanded_size, (0, 0, 0, 0))
    shadow_expanded.paste(shadow, (SHADOW_SPREAD, SHADOW_SPREAD))

    # Blur
    shadow_expanded = shadow_expanded.filter(ImageFilter.GaussianBlur(radius=SHADOW_BLUR))

    return shadow_expanded


def composite(base_path: Path, badge: Image.Image | None, output_path: Path):
    """Composite: dark bg + 80% animal top-left + badge bottom-right with drop shadow."""
    # Dark background
    canvas = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), BG_COLOR)

    # Animal at 80%, top-left
    animal = Image.open(base_path).convert("RGBA").resize(
        (ANIMAL_SIZE, ANIMAL_SIZE), Image.LANCZOS
    )
    canvas.alpha_composite(animal, dest=ANIMAL_OFFSET)

    if badge is not None:
        # Resize badge
        sized_badge = badge.resize((BADGE_SIZE, BADGE_SIZE), Image.LANCZOS)

        # Drop shadow
        shadow = make_shadow(sized_badge)
        # Shadow offset: centered on badge position, accounting for spread expansion
        shadow_x = BADGE_OFFSET[0] - SHADOW_SPREAD
        shadow_y = BADGE_OFFSET[1] - SHADOW_SPREAD
        canvas.alpha_composite(shadow, dest=(shadow_x, shadow_y))

        # Badge on top
        canvas.alpha_composite(sized_badge, dest=BADGE_OFFSET)

    canvas.save(output_path, "PNG", optimize=True)


def main():
    parser = argparse.ArgumentParser(description="Forge Slack avatar icons (v12 design)")
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
            print(f"  {species}-{role}.png")

    print(f"\nForged {count} icons in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
