#!/usr/bin/env bash
# Upload forged emoji to Slack using emojinator.
#
# Prerequisites:
#   pip install -r upstream/requirements.txt
#   export SLACK_TEAM=your-team-name
#   export SLACK_COOKIE='d=xoxd-...'
#
# Usage:
#   ./upload.sh                    # Upload all from output/
#   ./upload.sh output/fox-*.png   # Upload specific files

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UPLOAD_SCRIPT="${SCRIPT_DIR}/upstream/upload.py"

if [[ ! -f "$UPLOAD_SCRIPT" ]]; then
    echo "ERROR: emojinator not found. Run: git submodule update --init" >&2
    exit 1
fi

if [[ -z "${SLACK_TEAM:-}" ]] || [[ -z "${SLACK_COOKIE:-}" ]]; then
    echo "ERROR: Set SLACK_TEAM and SLACK_COOKIE env vars" >&2
    echo "  export SLACK_TEAM=your-team-name" >&2
    echo "  export SLACK_COOKIE='d=xoxd-...'" >&2
    exit 1
fi

if [[ $# -gt 0 ]]; then
    files=("$@")
else
    files=("${SCRIPT_DIR}/output/"*.png)
fi

if [[ ${#files[@]} -eq 0 ]]; then
    echo "No emoji files found. Run forge.py first." >&2
    exit 1
fi

echo "Uploading ${#files[@]} emoji to Slack team '${SLACK_TEAM}'..."
python3 "$UPLOAD_SCRIPT" "${files[@]}"
echo "Done."
