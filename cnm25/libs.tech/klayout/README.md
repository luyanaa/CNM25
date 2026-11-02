# CNM25 KLayout verification decks

DRC, LVS and layer-display files ported from the Glade APDK
(`apdk_cnm25_v2024_04_09/glade/verification/`).

## Contents

| Path | Purpose |
|------|---------|
| `tech/cnm25.lyp` | Layer properties (names/colors) for the KLayout viewer |
| `drc/cnm25.drc`  | DRC deck — full port of `cnm25drc.py` |
| `drc/run_drc.sh` | Convenience wrapper for batch DRC |
| `lvs/cnm25.lvs`  | LVS deck — port of `cnm25lvs.py` (nmos/pmos/PiP-cap extraction) |
| `lvs/run_lvs.sh` | Convenience wrapper for batch LVS |

## Usage

```sh
# DRC: produces a .lyrdb viewable in klayout via Tools > Marker Browser
./drc/run_drc.sh mylayout.gds MYTOP [report.lyrdb]

# LVS: compare layout against a reference spice netlist
./lvs/run_lvs.sh mylayout.gds MYTOP reference.spice [extracted.cir] [report.lvsdb]
```

Direct invocation (all variables optional unless noted):

```sh
klayout -b -z -r lvs/cnm25.lvs \
    -rd input=foo.gds -rd top=FOOTOP \
    -rd schematic=ref.spice \
    -rd target=extracted.cir -rd report=foo.lvsdb
```

`schematic` is optional: without it the deck performs extraction only.
`target` is optional: without it no extracted netlist file is written.
`report` defaults to `<input>.lvsdb` next to the input GDS.

## Devices recognized

| Device | Model | Recognition |
|--------|-------|-------------|
| nMOS (4-terminal) | `cnm25modn` | `poly1 & active & nplus` gate over PWELL |
| pMOS (4-terminal) | `cnm25modp` | `poly1 & active` gate (no nplus) inside NTUB |
| PiP capacitor     | `cnm25cpoly` | `poly1 & poly0` overlap, C = 4.227e-16 F/µm² |

B S/G/D terminal order follows SPICE `M` device convention
(drain, gate, source, bulk).

## Conventions

- Substrate bulk defaults to global net `VSS`; override with
  `-rd subnet=NAME`.
- Labels: pin texts on layers 20 (poly1), 21 (metal1), 22 (metal2);
  net labels on 23/24/25. Top-level labels become pins.
- Derived tap layers (`ntap = ndiff & nwell`, `ptap = pdiff & pwell`)
  carry well/substrate connections.

## Validated

- `cnm25_test/inverter.gds`: DRC clean, **LVS MATCH** vs
  `cnm25_test/spice/inverter.spice`.
- `cnm25_test/cnm25cpoly_30x30.gds`: DRC clean, cap extraction.
- `cnm25_test/drc_test.gds`: flags all 8 intentionally planted
  violations (rules 1.1, 1.2, 2.1, 4.1b, 6.1, 7.2, 8.0, 9.1).
