#!/bin/sh
# Usage: run_pex.sh <layout.gds> <topcell> [out.spice]
# Magic PEX: extraction with parasitic node capacitances.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
GDS=$1
TOP=$2
OUT=${3:-$(basename "$GDS" .gds)_pex.spice}
TMPD=$(mktemp -d)
trap 'rm -rf "$TMPD"' EXIT

cat > "$TMPD/pex.tcl" <<EOF
drc off
gds readonly true
gds read $GDS
load $TOP
expand
extract all
ext2spice -o $OUT
quit -noprompt
EOF

exec magic -dnull -noconsole -rcfile /dev/null -T "$HERE/cnm25.tech" "$TMPD/pex.tcl"
