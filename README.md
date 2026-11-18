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
    ngspice/
      cnm25mod_ngspice.lib  ngspice port of the BSIM3 model library
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
  exp_devices.py          ngspice device characterization experiment
  exp_inverter.py         ngspice inverter corner experiment
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

### ngspice
`libs.ref/cnm25/models/cnm25mod.lib` is the original SpiceOpus library and
does not load in ngspice (its `param:` subcircuit syntax, `LEVEL=53` and
`rndgauss()` are SpiceOpus-specific). Use the port instead:

```
.func rndgauss(sig) {agauss(0, sig, 1)}   ; {0} is enough outside ttt_mc
.lib libs.tech/ngspice/cnm25mod_ngspice.lib ttt   ; sss / fff / ttt_mc
xn d g s b cnm25modn w=10u l=3u
```

`scripts/exp_devices.py` and `scripts/exp_inverter.py` exercise that
library: threshold and drive current across the ttt/sss/fff corners,
gm/Id, PiP capacitor density against `cj`, Pelgrom Vth mismatch on
`ttt_mc`, and the voltage transfer and delay of the golden inverter
(NMOS 9u/3u, PMOS 18u/3u) at 5 V. Both exit non-zero on a failed check.

## Regenerating fixtures
```
klayout -b -r scripts/make_test_gds.py
```

## Known limitations

- DRC rules 6.7/6.8 of the original deck were never implemented in Glade
  either; they are skipped here as well.
- The PiP capacitor has no dedicated pin text layer in the source kit;
  the B plate is labeled with a text directly on POLY0 (3/0).
- The reference SPICE library is unchanged and remains SpiceOpus-only.
  `libs.tech/ngspice/cnm25mod_ngspice.lib` is the ngspice port
  (`param:` removed, BSIM3 level 49, `rndgauss` mapped to `agauss`). The
  PMOS parameter set realizes a Vth about 0.15 V below |VTH0|; that shift
  comes from the model card (large negative K3), not from the port.
