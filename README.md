# slack-emoji-forge

Generate per-species, per-role custom Slack emoji for Fiat agents.

Takes Google Noto Emoji animal icons, composites a role badge (Hand = blue dot, Buddy = yellow dot), and outputs Slack-ready 128x128 PNGs.

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

## Upload to Slack

```bash
export SLACK_TEAM=your-team
export SLACK_COOKIE='d=xoxd-...'
./upload.sh                            # Upload all
./upload.sh output/fox-*.png           # Upload specific
```

## Structure

```
sources/         Downloaded Noto Emoji PNGs (gitignored)
badges/          Role badge overlays (hand.png, buddy.png)
output/          Generated emoji (gitignored)
species.json     Species name → Unicode codepoint mapping
forge.py         Compositing script
upload.sh        Bulk upload wrapper around emojinator
upstream/        git submodule → smashwilson/slack-emojinator
```

## Custom Badges

Replace `badges/hand.png` and `badges/buddy.png` with your own 48x48 RGBA PNGs. The badge is composited in the bottom-right corner of each species icon.

## Adding Species

Edit `species.json` — keys are species names (used in filenames and Slack emoji names), values are Unicode codepoints for Google Noto Emoji.
