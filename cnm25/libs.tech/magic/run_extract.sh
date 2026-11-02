#!/bin/sh
# Usage: run_extract.sh <layout.gds> <topcell> [out.spice]
# Runs magic extraction (LVS-style netlist, no parasitics) for a GDS cell.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
GDS=$1
TOP=$2
OUT=${3:-$(basename "$GDS" .gds)_ext.spice}
TMPD=$(mktemp -d)
trap 'rm -rf "$TMPD"' EXIT

cat > "$TMPD/extract.tcl" <<EOF
drc off
gds readonly true
gds read $GDS
load $TOP
expand
extract all
ext2spice lvs
ext2spice -o $TMPD/raw.spice
quit -noprompt
EOF

magic -dnull -noconsole -rcfile /dev/null -T "$HERE/cnm25.tech" "$TMPD/extract.tcl"

# Magic does not emit a .subckt pin list from GDS labels; add it so that
# netgen can do pin matching.  Pin order is taken from the reference
# schematic at LVS time; we just need the names present.
PINS=$(grep -o '^\.subckt [^ ]*' "$TMPD/raw.spice" | head -1 | cut -d' ' -f2)
{
    # keep .global line if present
    grep '^\.global' "$TMPD/raw.spice" || true
    # rewrite the .subckt line to include all named nets that look like ports
    # (nets appearing in device terminals but not purely internal '#'-names)
    awk '
        /^\.subckt/ {
            cell=$2
            # collect nets used by devices
            print $0
            next
        }
        { print }
    ' "$TMPD/raw.spice" | grep -v '^\.global'
} > "$TMPD/pins.spice"

# Simpler: rewrite .subckt line with ports derived from top-level labels.
python3 - "$TMPD/raw.spice" "$OUT" <<'PYEOF'
import re, sys
src, dst = sys.argv[1], sys.argv[2]
txt = open(src).read()
m = re.search(r'\.subckt\s+(\w+)\s*\n', txt)
cell = m.group(1)
# port names = nets on device terminals that have no '#'
devs = re.findall(r'^M\S+\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', txt, re.M)
ports = []
for d,g,s,b in devs:
    for n in (d,g,s,b):
        if '#' not in n and n not in ports:
            ports.append(n)
newsub = '.subckt %s %s\n' % (cell, ' '.join(ports))
txt = re.sub(r'\.subckt\s+\w+\s*\n', newsub, txt, count=1)
open(dst,'w').write(txt)
PYEOF
echo "Wrote $OUT"
