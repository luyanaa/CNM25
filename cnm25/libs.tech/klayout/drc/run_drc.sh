#!/bin/sh
# Usage: run_drc.sh <layout.gds> <topcell> [report.lyrdb]
# Runs the CNM25 KLayout DRC deck.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
GDS=$1
TOP=$2
REPORT=${3:-$(basename "$GDS" .gds).lyrdb}
exec klayout -b -z -r "$HERE/cnm25.drc" \
    -rd input="$GDS" -rd top="$TOP" -rd report="$REPORT"
