#!/bin/bash
# Install armoor-viewer data files (Blue Marble basemap) into the active conda env.
#
# Usage:
#   ./tools/install_viewer_data.sh [SOURCE_IMAGE]
#
# SOURCE_IMAGE defaults to the ZOE copy if found, otherwise aborts.

set -euo pipefail

DEST_DIR="${CONDA_PREFIX:-}/share/armoor-viewer/img"
IMG_NAME="earth-blue-marble.jpg"

SRC="${1:-}"

if [[ -z "$SRC" || ! -f "$SRC" ]]; then
    echo "ERROR: Blue Marble image not found. Pass the path as argument:" >&2
    echo "  $0 /path/to/earth-blue-marble.jpg" >&2
    exit 1
fi

if [[ -z "${CONDA_PREFIX:-}" ]]; then
    echo "ERROR: no active conda environment (CONDA_PREFIX not set)." >&2
    exit 1
fi

mkdir -p "$DEST_DIR"
cp "$SRC" "$DEST_DIR/$IMG_NAME"
echo "Installed: $DEST_DIR/$IMG_NAME"
