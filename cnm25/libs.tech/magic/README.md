# CNM25 Magic verification

Magic technology file and batch wrappers for DRC, netlist extraction, LVS
(via netgen) and PEX on the CNM25 2-poly 2-metal n-well CMOS process.

## Contents

| Path | Purpose |
|------|---------|
| `cnm25.tech` | Magic technology file (planes, DRC, CIF/GDS I/O, extract) |
| `cnm25.tcl`  | Magic startup script (`-rcfile`) |
| `run_extract.sh` | GDS -> SPICE (LVS-style, no parasitics) |
| `run_pex.sh` | GDS -> SPICE with parasitic node capacitances |
| `run_lvs.sh` | extraction + `netgen` LVS compare |
| `../netgen/cnm25_setup.tcl` | netgen device-class equate/property rules |

## Usage

```sh
# DRC (interactive)
magic -T CNM25 -rcfile cnm25.tcl

# batch extraction for LVS
./run_extract.sh foo.gds TOPCELL [out.spice]

# PEX (netlist + node caps from cnm25pex_2d.py densities)
./run_pex.sh foo.gds TOPCELL [out.spice]

# LVS against a reference schematic
./run_lvs.sh foo.gds TOPCELL ref.spice [report]
```

## Devices recognized

| Magic type | Model | Recognition |
|-----------|-------|-------------|
| `nfet` | nfet / `cnm25modn` | `POLY1 & GASAD & NPLUS` gate in pwell |
| `pfet` | pfet / `cnm25modp` | `POLY1 & GASAD` (no nplus) inside NTUB |
| `nsc`/`psc` | well/sub taps | `WINDOW` over `nsd`/`psd` residues |
| `pc`,`p0c`,`ndc`,`pdc`,`m2c` | contacts | `WINDOW`/`VIA` classified by context |

Substrate taps: `nsd = GASAD & NPLUS & NTUB`, `psd = GASAD & ~NPLUS & PWELL`.
A drawn `PWELL` under the p-tap ties substrate to VSS in extraction.

## Layer map (GDS)

`1 NTUB, 2 GASAD, 3 POLY0, 4 POLY1, 5 NPLUS, 6 WINDOW, 7 METAL,
8 CAPS(pad), 9 METAL2, 10 VIA, 26 PWELL`; texts `20–25` map to
poly/metal pin & net labels.

## DRC coverage

Lambda = 0.5um.  Magic expresses CNM25 width/spacing/enclosure/exact-size
rules 1.x–4.x, 6.x–9.x.  Rule 2.3 (nwell enclosure of pdiff) and all 5.x
implant rules are not expressible without false positives and are left to
the KLayout deck (`../klayout/drc/cnm25.drc`).

**Caveat:** magic rescales the lambda grid on GDS read (GDS dbu=1nm vs
cifinput `scalefactor 100`), so the built-in checker reports geometric
rule distances on a distorted grid and can produce spurious errors on
otherwise-clean layouts.  Treat `drc count` as advisory — the KLayout
deck is authoritative for signoff; extraction/LVS/PEX are unaffected and
validated below.

## Parasitics (PEX)

Extract section carries the `cnm25pex_2d.py` plate/overlap caps in aF/um2:
poly→sub 32.58, PiP `poly1-poly0` 422.7, m1→poly/diff 26.56, m1→sub 14.63,
m2→m1 26.56, m2→poly 13.28, m2→diff/sub 9.44.

## Validated

- `cnm25_test/inverter.gds` — magic DRC clean, extraction gives
  `nfet w=9u l=3u` + `pfet w=18u l=3u` with `IN OUT VDD VSS` pins;
  **netgen LVS "Circuits match uniquely"** vs `inverter.spice`.
- `cnm25cpoly_30x30.gds` — DRC clean.
- `drc_test.gds` — flags nwell/active/poly/contact/metal violations
  (9 rules; implant + 2.3 handled by KLayout).
