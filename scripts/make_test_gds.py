#!/usr/bin/env python3
"""Generate CNM25 test/primitive GDS cells using klayout pya.

Usage:
  klayout -b -r make_test_gds.py            # writes into ../cnm25/libs.ref
  klayout -b -r make_test_gds.py -- -o DIR  # custom output dir
"""
import pya
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "cnm25", "libs.ref")
argv = sys.argv
if "-o" in argv:
    OUT = argv[argv.index("-o") + 1]

DBU = 0.001  # 1 nm database unit

# CNM25 layers (gds layer, datatype)
L_NWELL   = (1, 0)
L_ACTIVE  = (2, 0)   # GASAD
L_POLY0   = (3, 0)
L_POLY1   = (4, 0)
L_NPLUS   = (5, 0)
L_CONT    = (6, 0)   # WINDOW contact
L_METAL1  = (7, 0)
L_CAPS    = (8, 0)
L_METAL2  = (9, 0)
L_VIA     = (10, 0)
L_POLY1_PIN = (20, 0)
L_METAL1_PIN = (21, 0)
L_METAL2_PIN = (22, 0)
L_POLY1_NET = (23, 0)
L_METAL1_NET = (24, 0)
L_METAL2_NET = (25, 0)
L_PWELL = (26, 0)

ALL_LAYERS = [L_NWELL, L_ACTIVE, L_POLY0, L_POLY1, L_NPLUS, L_CONT,
              L_METAL1, L_METAL2, L_VIA, L_CAPS, L_PWELL,
              L_POLY1_PIN, L_METAL1_PIN, L_METAL2_PIN,
              L_POLY1_NET, L_METAL1_NET, L_METAL2_NET]


def um(v):
    return int(round(v / DBU))


class Lib(object):
    def __init__(self, name):
        self.layout = pya.Layout()
        self.layout.dbu = DBU
        self.top = self.layout.create_cell(name)
        self._li = {}
        for lp in ALL_LAYERS:
            self._li[lp] = self.layout.layer(lp[0], lp[1])

    def box(self, cell, lpair, x1, y1, x2, y2):
        cell.shapes(self._li[lpair]).insert(
            pya.Box(um(x1), um(y1), um(x2), um(y2)))

    def text(self, cell, lpair, s, x, y):
        t = pya.Text(s, pya.Trans(pya.Point(um(x), um(y))))
        cell.shapes(self._li[lpair]).insert(t)

    def write(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.layout.write(path)
        print("wrote", path)


# ---------------------------------------------------------------------------
# Design-rule constants (um) used by the generators
# ---------------------------------------------------------------------------
CP  = 2.0    # contact edge to poly gate
CS  = 2.5    # contact size
AOV = 1.0    # gasad enclosure of cont
POV = 2.5    # poly1 extension over gasad
POVC = 1.25  # poly1 enclosure of cont
MOV = 1.25   # metal enclosure of cont
NOV = 2.5    # nplus enclosure of gasad
WOV = 5.0    # nwell enclosure of gasad / spacing to ndiff


def fet_cell(lib, name, w, l, pmos):
    """Single-finger transistor, gate along x (length l), width along y."""
    c = lib.layout.cell(name) or lib.layout.create_cell(name)
    n = max(1, int((w - 2 * AOV + 3.0) / (CS + 3.0)))
    step = 0.0
    if n > 1:
        step = (w - 2 * AOV - CS) / (n - 1)
    for i in range(n):
        y = AOV + i * step
        lib.box(c, L_CONT, -CP - CS, y, -CP, y + CS)
        lib.box(c, L_CONT, l + CP, y, l + CP + CS, y + CS)
    lib.box(c, L_METAL1, -CP - CS - MOV, -MOV, -CP + MOV, w + MOV)
    lib.box(c, L_METAL1, l + CP - MOV, -MOV, l + CP + CS + MOV, w + MOV)
    lib.box(c, L_POLY1, 0, -POV, l, w + POV)
    lib.box(c, L_ACTIVE, -CP - CS - AOV, 0, l + CP + CS + AOV, w)
    if pmos:
        lib.box(c, L_NWELL, -CP - CS - AOV - WOV, -WOV,
                l + CP + CS + AOV + WOV, w + WOV)
        # (no NPLUS in the pmos cell: pgate = gate & ~nplus)
    else:
        lib.box(c, L_NPLUS, -CP - CS - AOV - NOV, -NOV,
                l + CP + CS + AOV + NOV, w + NOV)
        # p-substrate marker under NMOS (PWELL drawing layer 26/0)
        lib.box(c, L_PWELL, -CP - CS - AOV - NOV - 2, -NOV - 2,
                l + CP + CS + AOV + NOV + 2, w + NOV + 2)
    # pin labels
    lib.text(c, L_METAL1_PIN, "S", -CP - CS - MOV + 1, w / 2)
    lib.text(c, L_METAL1_PIN, "D", l + CP + CS + MOV + 1, w / 2)
    lib.text(c, L_POLY1_PIN, "G", l / 2, w / 2)
    return c


def tap_cell(lib, name, n_tap):
    """Well/substrate tap: active + contact + metal1. n_tap -> n+ in nwell."""
    c = lib.layout.cell(name) or lib.layout.create_cell(name)
    W = 4.5
    lib.box(c, L_ACTIVE, 0, 0, W, W)
    lib.box(c, L_CONT, AOV, AOV, AOV + CS, AOV + CS)
    lib.box(c, L_METAL1, AOV - MOV, AOV - MOV, AOV + CS + MOV, AOV + CS + MOV)
    if n_tap:
        lib.box(c, L_NPLUS, -NOV, -NOV, W + NOV, W + NOV)
        lib.box(c, L_NWELL, -WOV, -WOV, W + WOV, W + WOV)
        lib.text(c, L_METAL1_PIN, "B", W / 2, W + WOV + 1)
    else:
        # p+ tap = active NOT covered by nplus
        lib.text(c, L_METAL1_PIN, "B", W / 2, W + 1)
    return c


def pip_cell(lib, name, w, l):
    """PiP cap: poly1 plate w x l over poly0 plate (3um enc), 4 contact stubs."""
    c = lib.layout.cell(name) or lib.layout.create_cell(name)
    P0OV = 3.0   # poly0 enclosure of poly1
    CSP = 4.0    # cont spacing to cpoly
    lib.box(c, L_POLY0, -P0OV, -P0OV, l + P0OV, w + P0OV)
    lib.box(c, L_POLY1, 0, 0, l, w)
    stub_len = P0OV + CSP + CS + POVC
    stub_w = CS + 2 * POVC
    lib.box(c, L_POLY1, -stub_len, 0, 0, stub_w)
    lib.box(c, L_POLY1, l, w - stub_w, l + stub_len, w)
    lib.box(c, L_POLY1, l - stub_w, -stub_len, l, 0)
    lib.box(c, L_POLY1, 0, w, stub_w, w + stub_len)
    lib.box(c, L_CONT, -P0OV - CSP - CS, POVC, -P0OV - CSP, POVC + CS)
    lib.box(c, L_CONT, l + P0OV + CSP, w - POVC - CS, l + P0OV + CSP + CS, w - POVC)
    lib.box(c, L_CONT, l - POVC - CS, -P0OV - CSP - CS, l - POVC, -P0OV - CSP)
    lib.box(c, L_CONT, POVC, w + P0OV + CSP, POVC + CS, w + P0OV + CSP + CS)
    lib.box(c, L_METAL1, -P0OV - CSP - CS - MOV, POVC - MOV,
            -P0OV - CSP + MOV, POVC + CS + MOV)
    lib.box(c, L_METAL1, l + P0OV + CSP - MOV, w - POVC - CS - MOV,
            l + P0OV + CSP + CS + MOV, w - POVC + MOV)
    lib.box(c, L_METAL1, l - POVC - CS - MOV, -P0OV - CSP - CS - MOV,
            l - POVC + MOV, -P0OV - CSP + MOV)
    lib.box(c, L_METAL1, POVC - MOV, w + P0OV + CSP - MOV,
            POVC + CS + MOV, w + P0OV + CSP + CS + MOV)
    lib.text(c, L_METAL1_PIN, "T", l + P0OV + CSP, w - POVC - CS / 2)
    # B plate pin: poly0 text (magic labels poly0; klayout reads text on 3/0)
    lib.text(c, (3, 0), "B", l / 2, -P0OV / 2 - 0.5)
    return c


def drc_violator(lib):
    c = lib.top
    lib.box(c, L_NWELL, 0, 0, 20, 4)          # nwell width 4 < 8
    lib.box(c, L_NWELL, 0, 8, 20, 20)         # nwell spacing 4 < 8
    lib.box(c, L_ACTIVE, 40, 0, 60, 1)        # active width 1 < 2
    lib.box(c, L_POLY1, 40, 10, 60, 11)       # poly1 width 1 < 2.5
    lib.box(c, L_CONT, 40, 20, 42, 22)        # bad cont size 2x2
    lib.box(c, L_METAL1, 38, 18, 44, 24)
    lib.box(c, L_ACTIVE, 38, 18, 44, 24)
    lib.box(c, L_METAL1, 0, 40, 30, 44)       # metal1 spacing 2 < 3
    lib.box(c, L_METAL1, 0, 46, 30, 50)
    lib.box(c, L_VIA, 40, 40, 43, 43)         # via without metal2
    lib.box(c, L_METAL1, 38, 38, 45, 45)
    lib.box(c, L_METAL2, 60, 40, 90, 42)      # metal2 width 2 < 3.5


def _inst_geom(lib, src_cell, dx, dy, skip_texts=True):
    """Copy shapes of src_cell into lib.top at offset (flat).
    skip_texts drops per-terminal labels (S/D/G/B) of the child device
    cells so the flattened top only carries its own pin names."""
    top = lib.top
    tr = pya.Trans(pya.Point(um(dx), um(dy)))
    for li in src_cell.layout().layer_indices():
        for s in src_cell.shapes(li).each():
            if s.is_text():
                if skip_texts:
                    continue
                t = s.text
                nt = pya.Text(t.string, tr * t.trans)
                nt.size = t.size
                top.shapes(li).insert(nt)
            else:
                top.shapes(li).insert(s.polygon.transformed(tr))


def inverter(lib):
    """IN/OUT/VDD/VSS inverter: nmos 9/3 + pmos 18/3 + well/sub taps.
    Geometry is placed FLAT in the top cell so extraction works in either
    flat or deep mode."""
    top = lib.top
    nmos = fet_cell(lib, "nmos_9x3", 9.0, 3.0, False)
    pmos = fet_cell(lib, "pmos_18x3", 18.0, 3.0, True)
    ntap = tap_cell(lib, "ntap", True)
    ptap = tap_cell(lib, "ptap", False)
    py = 40.0
    _inst_geom(lib, nmos, 0, 0)
    _inst_geom(lib, pmos, 0, py)
    _inst_geom(lib, ntap, -3.0, py + 27.0)   # nwell overlaps pmos nwell
    _inst_geom(lib, ptap, -4.5, 17.0)        # left of OUT bus, 3.5um gap
    # drawn PWELL under the p-tap, merged with the nmos pwell so the
    # substrate node is a single well region tying ptap->VSS->bulk
    lib.box(top, L_PWELL, -7.0, 9.0, 3.0, 23.0)
    # remove the now-empty child cells so the file is truly flat
    for cc in (nmos, pmos, ntap, ptap):
        lib.layout.delete_cell(cc.cell_index())
    # gates: route IN on metal1 at x ~ -17; poly1 stubs extend each gate
    # left to a contact pad, far enough that cont-gate spacing (2.0) and
    # poly1-cont enclosure (1.25) are met and stubs avoid active by 1.25.
    # stub poly1: x -17.25..3, y 2..7 (nmos), y py+2..py+7 (pmos);
    # width 5 >= 2*1.25+2.5 so contacts are enclosed on all sides.
    # gate stubs: bulb (x -17.25..-11) for the contact pad + 3um neck
    # (y 5.5..8.5: clears S-cont top 3.5 by 2.0, inside active 0..9)
    # nmos: gate-poly contact on the bottom poly extension (outside active):
    # vertical field-poly leg x 0..3 from y -POV(-2.5) down to the pad row,
    # horizontal leg to a bulb, keeping 1.25 clear of active.
    # stub path: (0..3, -8.5..0) then (-17.25..3, -8.5..-3.5)? widths>=2.5
    lib.box(top, L_POLY1, 0.0, -8.5, 3.0, 0.0)
    lib.box(top, L_POLY1, -17.25, -8.5, 3.0, -3.5)
    # pmos: stub continues the gate finger at full 3um channel width:
    # vertical leg x 0..3 from gate top (58) up to the pad row, then
    # a horizontal field-poly leg to the bulb at x -17.25..-11.
    lib.box(top, L_POLY1, 0.0, py + 18.0, 3.0, py + 23.0)
    lib.box(top, L_POLY1, -14.0, py + 20.5, 3.0, py + 23.0)
    lib.box(top, L_POLY1, -17.25, py + 18.0, -11.0, py + 23.0)
    # contacts in the bulbs (poly1 encl 1.25 every side)
    lib.box(top, L_CONT, -16.0, -7.25, -13.5, -4.75)
    lib.box(top, L_CONT, -16.0, py + 19.25, -13.5, py + 21.75)
    # IN rail metal1 covering both contacts (enc 1.25 on every side)
    lib.box(top, L_METAL1, -17.5, -8.5, -12.25, py + 23.0)
    lib.text(top, L_METAL1_PIN, "IN", -14.75, py / 2)
    # OUT: join drain metals (right side) of both fets
    dx1 = 3.0 + CP - MOV            # 3.75
    dx2 = 3.0 + CP + CS + MOV       # 8.75
    lib.box(top, L_METAL1, dx1, -MOV, dx2, py + 18.0 + MOV)
    # VSS rail: source (left) of nmos + ptap metal.
    # The strip must NOT cross the OUT bus (x 3.75..8.75): stop at x 0.75.
    sx1 = -CP - CS - MOV            # -5.75
    sx2 = -CP + MOV                 # -0.75
    lib.box(top, L_METAL1, sx1, -MOV, sx2, 9.0 + MOV)
    lib.box(top, L_METAL1, sx1, 9.0 + MOV, 0.75, 14.0)
    lib.box(top, L_METAL1, -4.75, 12.0, 0.25, 17.75)  # drop to ptap metal
    # VDD rail: source (left) of pmos + ntap metal (same constraint).
    lib.box(top, L_METAL1, sx1, py - MOV, sx2, py + 18.0 + MOV)
    lib.box(top, L_METAL1, sx1, py + 18.0 + MOV, sx2, py + 28.5)
    lib.box(top, L_METAL1, sx1, py + 23.5, 0.75, py + 28.5)
    # labels (IN placed with rail above)
    lib.text(top, L_METAL1_PIN, "OUT", (dx1 + dx2) / 2, py / 2)
    lib.text(top, L_METAL1_PIN, "VSS", -2.5, 12.0)
    lib.text(top, L_METAL1_PIN, "VDD", -2.5, py + 25.0)


def main():
    tdir = os.path.join(OUT, "cnm25_test", "gds")
    ddir = os.path.join(OUT, "cnm25", "gds")

    lib = Lib("drc_test")
    drc_violator(lib)
    lib.write(os.path.join(tdir, "drc_test.gds"))

    lib = Lib("inverter")
    inverter(lib)
    lib.write(os.path.join(tdir, "inverter.gds"))

    lib = Lib("cnm25cpoly_30x30")
    pip_cell(lib, "cnm25cpoly_30x30", 30.0, 30.0)
    lib.write(os.path.join(tdir, "cnm25cpoly_30x30.gds"))

    for w, l, pmos, nm in [(4.5, 3.0, False, "cnm25modn"),
                           (4.5, 3.0, True, "cnm25modp")]:
        lib = Lib(nm)
        fet_cell(lib, nm, w, l, pmos)
        lib.write(os.path.join(ddir, nm + ".gds"))


main()
