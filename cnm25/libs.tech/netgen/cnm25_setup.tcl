# CNM25 netgen LVS setup file
# Usage: netgen -batch lvs "extracted.spice CELL" "reference.spice CELL" \
#            cnm25_setup.tcl [comp.out]

permute default

# Magic extraction emits generic device classes nfet/pfet; the CNM25
# reference netlists use cnm25modn/cnm25modp.  Allow either naming.
equate classes "-circuit2 cnm25modn" "-circuit1 nfet"
equate classes "-circuit2 cnm25modp" "-circuit1 pfet"

# Magic writes per-device diffusion parasitics ad/as/pd/ps that the
# schematic-level reference does not carry; ignore them in comparison.
property {-circuit1 nfet} remove ad pd as ps
property {-circuit1 pfet} remove ad pd as ps
property {-circuit2 cnm25modn} remove ad pd as ps
property {-circuit2 cnm25modp} remove ad pd as ps
