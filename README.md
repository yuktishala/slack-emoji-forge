# slack-emoji-forge

Generate per-species, per-role avatar icons for Fiat agents.

Takes Google Noto Emoji animal icons, composites a role badge, adds a background for Slack dark mode compatibility, and outputs 128x128 PNGs hosted via raw GitHub URLs for use as `icon_url` in Slack's `chat.postMessage`.

## Quick Start

```bash
pip install -r requirements.txt
python forge.py
# Output in output/: fox-hand.png, fox-buddy.png, ant-hand.png, ...
```

## Usage

```bash
python forge.py                        # All species x all roles
python forge.py --species fox,ant,owl  # Specific species only
python forge.py --roles hand           # Only hand variants
python forge.py --no-badge             # Plain icons, no role badge
python forge.py --download-only        # Just fetch Noto sources
```

## Hosting

Generated PNGs are committed to `samples/` and served via raw GitHub URLs:

```
https://raw.githubusercontent.com/yuktishala/slack-emoji-forge/main/samples/{species}-{variant}.png
```

Used as `icon_url` in Slack `chat.postMessage` with `chat:write.customize` scope.

## Structure

```
sources/         Downloaded Noto Emoji PNGs (gitignored)
badges/          Role badge overlays (hand.png, buddy.png)
samples/         Committed output for hosting via GitHub raw URLs
output/          Working output (gitignored)
species.json     Species name → Unicode codepoint mapping
forge.py         Compositing script
```

## Custom Badges

Replace `badges/hand.png` and `badges/buddy.png` with your own 48x48 RGBA PNGs. The badge is composited in the bottom-right corner of each species icon.

## Adding Species

Edit `species.json` — keys are species names (used in filenames), values are Unicode codepoints for Google Noto Emoji.
