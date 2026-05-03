#!/usr/bin/env python3
"""
slack-emoji-forge: Generate totem identity icons for Fiat agents.

Design:
  - 128x128 canvas with #1a1d21 background (Slack dark mode)
  - Bare totem: emoji fills full canvas
  - Role variants ({species}-eye.png, {species}-hand.png):
      80% emoji top-left + ~30% area role badge bottom-right with drop shadow

Output naming:
  - {species}.png       — bare totem (e.g., fox.png)
  - {species}-eye.png   — eye-overlay variant
  - {species}-hand.png  — hand-overlay variant

Icon URL: https://raw.githubusercontent.com/yuktishala/slack-emoji-forge/main/output/{species}[-{role}].png

Usage:
  python forge.py                       # All species, bare + all role variants
  python forge.py --species fox,ant     # Specific species only
  python forge.py --roles eye           # Only eye-badge variant (skips bare + hand)
  python forge.py --no-roles            # Only bare totems, no overlays
  python forge.py --download-only       # Just download Noto sources
  python forge.py --catalog             # Generate catalog.html and exit
"""

import argparse
import json
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

NOTO_PNG_URL = "https://raw.githubusercontent.com/googlefonts/noto-emoji/main/png/128/emoji_u{codepoint}.png"
NOTO_SVG_URL = "https://raw.githubusercontent.com/googlefonts/noto-emoji/main/svg/emoji_u{codepoint}.svg"

ICON_SIZE = 128
BG_COLOR = (26, 29, 33, 255)  # #1a1d21 — Slack dark mode

# Role-variant compositing (v12 design, restored)
ANIMAL_SIZE = int(ICON_SIZE * 0.80)  # 102px, top-left
ANIMAL_OFFSET = (0, 0)
BADGE_SIZE = 70                                           # ~30% area
BADGE_OFFSET = (ICON_SIZE - BADGE_SIZE, ICON_SIZE - BADGE_SIZE)  # bottom-right
SHADOW_SPREAD = 6
SHADOW_BLUR = 5
SHADOW_ALPHA_MULT = 1.5

ROLES = {
    "eye": "eye.png",
    "hand": "hand-medium-light.png",
}


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


def load_role_badge(role: str) -> Image.Image:
    """Load + resize a role badge to BADGE_SIZE."""
    badge_file = BADGES_DIR / ROLES[role]
    if not badge_file.exists():
        raise FileNotFoundError(f"badge not found: {badge_file}")
    badge = Image.open(badge_file).convert("RGBA")
    return badge.resize((BADGE_SIZE, BADGE_SIZE), Image.LANCZOS)


def make_shadow(badge: Image.Image) -> Image.Image:
    """Drop shadow from badge alpha — vectorized via point()/Gaussian blur."""
    alpha = badge.split()[3]
    boosted = alpha.point(lambda v: min(255, int(v * SHADOW_ALPHA_MULT)))
    shadow = Image.merge("RGBA", (
        Image.new("L", badge.size, 0),
        Image.new("L", badge.size, 0),
        Image.new("L", badge.size, 0),
        boosted,
    ))
    expanded_size = (badge.width + SHADOW_SPREAD * 2, badge.height + SHADOW_SPREAD * 2)
    expanded = Image.new("RGBA", expanded_size, (0, 0, 0, 0))
    expanded.paste(shadow, (SHADOW_SPREAD, SHADOW_SPREAD))
    return expanded.filter(ImageFilter.GaussianBlur(radius=SHADOW_BLUR))


def composite_bare(source_path: Path, output_path: Path):
    """Bare totem: dark bg + full-size emoji."""
    canvas = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), BG_COLOR)
    emoji = Image.open(source_path).convert("RGBA").resize(
        (ICON_SIZE, ICON_SIZE), Image.LANCZOS
    )
    canvas.alpha_composite(emoji)
    canvas.save(output_path, "PNG", optimize=True)


def composite_with_badge(source_path: Path, badge: Image.Image, shadow: Image.Image, output_path: Path):
    """Role variant: dark bg + 80% emoji top-left + badge bottom-right w/ drop shadow."""
    canvas = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), BG_COLOR)
    emoji = Image.open(source_path).convert("RGBA").resize(
        (ANIMAL_SIZE, ANIMAL_SIZE), Image.LANCZOS
    )
    canvas.alpha_composite(emoji, dest=ANIMAL_OFFSET)
    shadow_x = BADGE_OFFSET[0] - SHADOW_SPREAD
    shadow_y = BADGE_OFFSET[1] - SHADOW_SPREAD
    canvas.alpha_composite(shadow, dest=(shadow_x, shadow_y))
    canvas.alpha_composite(badge, dest=BADGE_OFFSET)
    canvas.save(output_path, "PNG", optimize=True)


def generate_catalog(species: dict, catalog_path: Path):
    """Catalog grid: per-species card with bare + role variants."""
    cards = []
    role_keys = list(ROLES.keys())
    for slug in sorted(species.keys()):
        cp = species[slug]
        variants = "".join(
            f'<img src="output/{slug}-{role}.png" width="48" height="48" alt="{slug}-{role}">'
            for role in role_keys
        )
        cards.append(
            f'<div class="card" title="U+{cp.upper()}">'
            f'<img src="output/{slug}.png" width="64" height="64" alt="{slug}">'
            f'<div class="variants">{variants}</div>'
            f'<div class="name">{slug}</div>'
            f'</div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>slack-emoji-forge — {len(species)} totems</title>
<style>
  body {{ font-family: monospace; background: #1a1d21; color: #d1d2d3; padding: 16px; }}
  h1 {{ color: #fff; margin-bottom: 4px; }}
  p.count {{ color: #888; margin: 0 0 16px; }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 8px;
  }}
  .card {{
    background: #222529;
    border-radius: 6px;
    padding: 10px 6px 8px;
    text-align: center;
    cursor: default;
    transition: background 0.15s;
  }}
  .card:hover {{ background: #2c3036; }}
  .card > img {{ display: block; margin: 0 auto 4px; }}
  .variants {{ display: flex; justify-content: center; gap: 4px; margin-bottom: 6px; }}
  .variants img {{ display: block; }}
  .name {{ font-size: 11px; color: #aaa; word-break: break-all; }}
</style>
</head>
<body>
<h1>slack-emoji-forge</h1>
<p class="count">{len(species)} totems × (bare + {len(role_keys)} role variants)</p>
<div class="grid">
{"".join(cards)}
</div>
</body>
</html>
"""
    catalog_path.write_text(html, encoding="utf-8")
    print(f"Catalog written: {catalog_path} ({len(species)} totems)")


def main():
    parser = argparse.ArgumentParser(description="Forge Fiat totem identity icons")
    parser.add_argument("--species", help="Comma-separated species (default: all)")
    parser.add_argument("--roles", help=f"Comma-separated roles (default: {','.join(ROLES.keys())})",
                        default=",".join(ROLES.keys()))
    parser.add_argument("--no-roles", action="store_true", help="Only generate bare {species}.png, skip role variants")
    parser.add_argument("--download-only", action="store_true", help="Only download source icons")
    parser.add_argument("--catalog", action="store_true", help="Generate catalog.html and exit")
    args = parser.parse_args()

    SOURCES_DIR.mkdir(exist_ok=True)
    BADGES_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    all_species = load_species()

    if args.catalog:
        generate_catalog(all_species, REPO_ROOT / "catalog.html")
        return

    selected = args.species.split(",") if args.species else list(all_species.keys())
    roles = [] if args.no_roles else [r for r in args.roles.split(",") if r]

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

    # Pre-load + pre-build shadows per role (badges are species-agnostic)
    badges = {}
    shadows = {}
    for role in roles:
        if role not in ROLES:
            print(f"  SKIP role '{role}': not defined", file=sys.stderr)
            continue
        badges[role] = load_role_badge(role)
        shadows[role] = make_shadow(badges[role])

    count = 0
    for species, source_path in downloaded.items():
        # Bare totem
        bare_out = OUTPUT_DIR / f"{species}.png"
        composite_bare(source_path, bare_out)
        count += 1
        print(f"  {species}.png")

        # Role variants
        for role, badge in badges.items():
            out = OUTPUT_DIR / f"{species}-{role}.png"
            composite_with_badge(source_path, badge, shadows[role], out)
            count += 1
            print(f"  {species}-{role}.png")

    print(f"\nForged {count} icons in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
