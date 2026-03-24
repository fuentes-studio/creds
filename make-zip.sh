#!/usr/bin/env bash
# make-zip.sh — package creds for sharing
# Usage: bash make-zip.sh [output-path]
# Default output: ~/Desktop/creds.zip

set -e

CREDS_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="${1:-$HOME/Desktop/creds.zip}"

echo "Packaging creds → $OUTPUT"

cd "$(dirname "$CREDS_DIR")"

zip -r "$OUTPUT" "$(basename "$CREDS_DIR")" \
    --exclude "*/\.venv/*" \
    --exclude "*/__pycache__/*" \
    --exclude "*/.pytest_cache/*" \
    --exclude "*/\.git/*" \
    --exclude "*/meta.db" \
    --exclude "*/\.env" \
    --exclude "*/creds.egg-info/*" \
    --exclude "*/*.pyc" \
    --exclude "*DS_Store" \
    --exclude "*/.omc/*" \
    --exclude "*/.env" \
    --exclude "*/.env.*"

SIZE=$(du -sh "$OUTPUT" | cut -f1)
echo "Done — $OUTPUT ($SIZE)"
echo ""
echo "Share it, then recipient runs:"
echo "  unzip creds.zip && cd creds && bash install.sh"
