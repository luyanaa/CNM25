#!/bin/sh
# Usage: run_lvs.sh <layout.gds> <topcell> <schematic.spice> [extracted.cir] [report.lvsdb]
# Runs the CNM25 KLayout LVS deck and prints "LVS MATCH"/"LVS MISMATCH".
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
GDS=$1
TOP=$2
SCH=$3
EXT=${4:-$(basename "$GDS" .gds)_ext.cir}
REPORT=${5:-$(basename "$GDS" .gds).lvsdb}
exec klayout -b -z -r "$HERE/cnm25.lvs" \
    -rd input="$GDS" -rd top="$TOP" \
    -rd schematic="$SCH" -rd target="$EXT" -rd report="$REPORT"
