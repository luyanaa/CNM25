#!/bin/sh
# Usage: run_pex.sh <layout.gds> <topcell> [out.spice]
# Magic PEX: node capacitances plus the distributed resistance of every
# net that has at least one port.  GDS text labels are not ports, so the
# script declares every label it finds before extraction.
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
select top cell
expand
# extresist only keeps a net it can tie to a port, and drops anything
# else after extracting it.  Magic has no command that lists labels, so
# try every name this PDK puts on a GDS text layer and keep the ones that
# resolve.  findlabel selects the label; port make turns it into a port.
set n 1
foreach name {
    IN OUT VDD VSS GND VCC A B C D E F G H I J K L M N O P Q R S T U V W X Y Z
    M1A M1B M2A M2B PA PB P0A P0B NA NB DA DB CA CB VA VB PCA PCB S0 S1 SM
    CLK RST BIAS VINN VINP VOUT IBIAS VCOMM VLOAD VINTER
} {
    if {![catch {findlabel \$name}]} {
        port make \$n
        incr n
    }
}
extract all
extresist threshold 0
extresist minresist 0
extresist mindelay 0
extresist simplify on
extresist all
ext2spice format ngspice
ext2spice scale off
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist on
ext2spice subcircuit top on
ext2spice -o $TMPD/raw.spice
quit -noprompt
EOF

magic -dnull -noconsole -rcfile /dev/null -T "$HERE/cnm25.tech" "$TMPD/pex.tcl"

# extresist records each resistor once in each direction and ext2spice
# writes both, so every resistor would appear twice in parallel.  Keep
# one of each pair.
awk '
    /^R/ {
        key = ($2 < $3 ? $2 " " $3 : $3 " " $2) " " $4
        if (seen[key]++) next
    }
    { print }
' "$TMPD/raw.spice" > "$OUT"
