# CNM25 magic startup file.
# Usage:
#   magic -dnull -noconsole -rcfile cnm25.tcl [script.tcl]
# or interactively:
#   magic -T CNM25 -rcfile cnm25.tcl
#
# The tech file sits next to this script; %T% is expanded by magic to the
# technology name on the command line (-T option).

tech load [file join [file dirname [info script]] cnm25.tech]

# Common batch settings for GDS-driven verification
drc off
gds readonly true
gds flatten true
