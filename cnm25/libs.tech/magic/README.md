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
| PiP capacitor | (no device; see below) | `POLY1` over `POLY0` |
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
otherwise-clean layouts.  The KLayout deck is authoritative for signoff.

`drc count` is also unreliable in batch mode here: it reports 0 while
`drc listall why` lists the errors.  Count errors from `drc listall why`.
Rule 2.3 and the 5.x implant rules are not in this deck at all (see
below), so magic will never flag the `drc_test` violations of those
rules.

## Parasitics (PEX)

Capacitance follows the manual, section 3.10: the parallel-plate model of
Fig. 44 with the fringe term left at 0, exactly as `cnm25pex_2d.py` does.
Magic shields a plate by whatever overlaps it, so no separate perimeter
term is needed. Densities in aF/um2:

| coupling | oxide | density |
|----------|-------|---------|
| poly1, poly0 to substrate | 1060 nm | 32.58 |
| poly1 over poly0 (PiP) | foundry Cj | 422.7 |
| metal1 to poly or diffusion | 1300 nm | 26.56 |
| metal1 to substrate | 2360 nm | 14.63 |
| metal2 to metal1 | 1300 nm | 26.56 |
| metal2 to poly | 2600 nm | 13.28 |
| metal2 to diffusion or substrate | 3660 nm | 9.44 |

`areacap` needs the layer's own plane (`metal1/m1`, `metal2/m2`). Written
as `metal1/a` the metal is looked up on the active plane and the parasitic
is zero. Diffusion and well junction caps are not extracted: the BSIM
models carry `CJ`/`CJSW` and magic already emits `AD`/`PD`/`AS`/`PS`.

Resistance is not in the manual. Sheet values are milliohms per square
(metal1 50, metal2 30, poly and poly0 20000, ndiff 25000, pdiff 80000),
and each contact cut is 2 ohms, each via 1 ohm, counted with `contact`
rather than as sheet resistance. `run_pex.sh` turns every GDS label into
a port and runs `extresist`; magic only emits the resistors of a net that
has a port, and it warns about (but still extracts) the substrate tie of a
MOSFET, which has no routing of its own.

The PiP capacitor is **not** a magic device. A `device capacitor` line
would double-count it, because the 422.7 aF/um2 overlap cap above is the
same capacitance, and magic keeps both. It therefore appears in the PEX
netlist as an overlap capacitor between the poly1 and poly0 nets
(`cnm25cpoly_30x30`: C(T,B) = 0.8116 pF) rather than as a `cnm25cpoly`
element. The KLayout deck extracts it as a named device.

## Validated

- `cnm25_test/inverter.gds` — magic DRC clean, extraction gives
  `nfet w=9u l=3u` + `pfet w=18u l=3u` with `IN OUT VDD VSS` pins;
  **netgen LVS "Circuits match uniquely"** vs `inverter.spice`.
- `cnm25cpoly_30x30.gds` — PEX gives C(T,B) = 0.8116 pF, the 422.7
  aF/um2 overlap over the poly1/poly0 plate, plus the plate-to-substrate
  fringe. No `cnm25cpoly` device (see above).
- `drc_test.gds` — flags nwell/active/poly/contact/metal violations
  (9 rules; implant + 2.3 handled by KLayout).
