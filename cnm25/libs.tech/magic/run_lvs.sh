#!/bin/sh
# Usage: run_lvs.sh <layout.gds> <topcell> <schematic.spice> [comp.out]
# Magic extraction + netgen LVS compare.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
GDS=$1
TOP=$2
SCH=$3
RPT=${4:-$(basename "$GDS" .gds)_lvs.out}
TMPD=$(mktemp -d)
trap 'rm -rf "$TMPD"' EXIT

"$HERE/run_extract.sh" "$GDS" "$TOP" "$TMPD/layout.spice" >/dev/null

netgen -batch lvs "$TMPD/layout.spice $TOP" "$SCH $TOP" \
    "$HERE/../netgen/cnm25_setup.tcl" "$RPT" || true

if grep -q "Circuits match uniquely" "$RPT" 2>/dev/null; then
    echo "LVS MATCH: $TOP"
else
    echo "LVS MISMATCH: $TOP (see $RPT)"
    exit 1
fi
