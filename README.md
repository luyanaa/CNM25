# open_pdk / CNM25

Open-PDK style packaging of the CNM25 analog process design kit, converted
from the original Glade `apdk_cnm25` distribution (v2024-04-09).

Layout follows the open_pdks convention:

```
cnm25/
  libs.tech/
    klayout/
      tech/cnm25.lyp      layer display properties
      drc/cnm25.drc       KLayout DRC deck
      lvs/cnm25.lvs       KLayout LVS deck
      run_drc.sh run_lvs.sh
    magic/
      cnm25.tech          magic technology file
      cnm25.tcl           magic startup script
    netgen/
      cnm25_setup.tcl     netgen LVS setup
    doc/                  original APDK documentation
  libs.ref/
    cnm25/
      gds/                device layout (cnm25modn, cnm25modp)
      spice/              extracted-view subcircuits
      models/cnm25mod.lib original BSIM3 model library
    cnm25_test/
      gds/                test fixtures (inverter, drc_test, cpoly)
      spice/              golden schematic netlists
scripts/
  make_test_gds.py        regenerates the .gds fixtures (klayout pya)
```

## Process summary

- ~2.5 µm single-poly-gate + capacitor-poly (POLY0/POLY1), 2 metal layers
- Devices: `cnm25modn` (NMOS), `cnm25modp` (PMOS), `cnm25cpoly` (PiP capacitor)
- Manufacturing grid: 0.25 µm
- Bulk = p-substrate (implicit pwell); NTUB = nwell; NPLUS selects n+
  implants; GASAD&~NPLUS = p+ diffusion.
- Pin text layers 20/21/22 (poly1/m1/m2 pins), net text layers 23/24/25.

## Usage

### KLayout
```
klayout -b -r libs.tech/klayout/drc/cnm25.drc -rd input=foo.gds -rd report=drc.lyrdb
klayout -b -r libs.tech/klayout/lvs/cnm25.lvs -rd input=foo.gds ...
```

### Magic
```
magic -dnull -noconsole -T libs.tech/magic/cnm25.tech
# then: gds read foo.gds / load cell / drc check / extract all / ext2spice
```

### Netgen LVS
```
netgen -batch lvs "extracted.spice cell" "schematic.spice cell" \
    libs.tech/netgen/cnm25_setup.tcl comp.out
```

## Regenerating fixtures
```
klayout -b -r scripts/make_test_gds.py
```

## Known limitations

- DRC rules 6.7/6.8 of the original deck were never implemented in Glade
  either; they are skipped here as well.
- The PiP capacitor has no dedicated pin text layer in the source kit;
  the B plate is labeled with a text directly on POLY0 (3/0).
- SPICE model distribution is unchanged: `libs.ref/cnm25/models/cnm25mod.lib`
  is the original SpiceOpus file (BSIM3 level 53 with `rndgauss` mismatch
  parameters — ngspice-compatible syntax may need minor edits).
