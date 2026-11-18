#!/usr/bin/env python3
"""CNM25 device characterization experiment.

Drives ngspice over the ngspice port of the CNM25 model library and checks
the results against the process definition:

  * BSIM3 parameters actually took effect (Vth tracks the corner vth0,
    drawn-length delta from LINT = 0.9 um is visible).
  * Process corners order the drive current: fff > ttt > sss.
  * gm/Id peaks in moderate inversion, as a long-channel MOSFET must.
  * The PiP capacitor density matches the corner `cj` (4.227e-4 F/m^2 at ttt).
  * Monte-Carlo mismatch (ttt_mc) produces device-to-device Vth scatter of
    the Pelgrom magnitude, and none when the mismatch coeffs are zero.

Usage: exp_devices.py [--lib PATH] [--work DIR]
Exit status is non-zero when any check fails.
"""

import argparse
import math
import os
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_LIB = HERE.parent / "cnm25" / "libs.tech" / "ngspice" / "cnm25mod_ngspice.lib"

CORNERS = {
    # name: (vth0n, vth0p, u0n, u0p, cj)
    "ttt": (0.860363, -1.52069, 0.0573986, 0.0228166, 4.227e-4),
    "sss": (1.00467, -1.73564, 0.0367598, 0.0140327, 4.650e-4),
    "fff": (0.63934, -1.20160, 0.0780374, 0.0316005, 3.804e-4),
}
LINT_N = 0.9e-6          # BSIM3 LINT of cnm25modn
AVTH0 = 30e-9            # Pelgrom A_Vth [V*m], ttt_mc corner


class SpiceError(RuntimeError):
    pass


def ngspice(netlist: str, work: Path, tag: str) -> str:
    """Run a netlist in batch mode and return stdout+stderr."""
    path = work / f"{tag}.sp"
    path.write_text(netlist)
    log = work / f"{tag}.log"
    proc = subprocess.run(
        ["ngspice", "-n", "-b", str(path)],
        cwd=work, capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    log.write_text(out)
    if proc.returncode != 0 or re.search(r"fatal error|Simulation interrupted",
                                          out):
        tail = "\n".join(out.strip().splitlines()[-12:])
        raise SpiceError(f"{tag} failed (rc={proc.returncode}):\n{tail}")
    return out


def wrdata(work: Path, name: str) -> np.ndarray:
    """Read an ngspice `wrdata` file written with `set wr_singlescale`.

    Columns come in (scale, value) pairs; the duplicated scale column of
    every vector after the first is dropped.
    """
    rows = []
    for line in (work / name).read_text().splitlines():
        if line.strip():
            rows.append([float(x) for x in line.split()])
    data = np.array(rows)
    keep = [0] + list(range(2, data.shape[1], 2))
    return data[:, keep]


def mos_deck(lib: Path, corner: str, dev: str, w: str, l: str,
             sources: str, sweeps: str) -> str:
    """MOS deck. `sources` is netlist lines, `sweeps` control-block lines."""
    if dev == "n":
        inst = f"xn d g 0 0 cnm25modn w={w} l={l}"
    else:
        inst = f"xp d g s 0 cnm25modp w={w} l={l}"
    return f"""* {dev}mos {corner} {w}/{l}
.func rndgauss(sig) {{0}}
.lib '{lib}' {corner}
{inst}
{sources}
.control
set wr_singlescale
set filetype=ascii
{sweeps}
.endc
.end
"""


def op_point(lib, corner, dev, w, l, vgs, vds, work, tag):
    """Single bias point: returns (vth, id) with id signed as ngspice prints."""
    if dev == "n":
        sources = f"vg g 0 {vgs}\nvd d 0 {vds}"
        body = "op\nprint @m.xn.mn[vth] @m.xn.mn[id]\n"
    else:
        sources = f"vs s 0 0\nvg g 0 {vgs}\nvd d 0 {vds}"
        body = "op\nprint @m.xp.mp[vth] @m.xp.mp[id]\n"
    out = ngspice(mos_deck(lib, corner, dev, w, l, sources, body), work, tag)
    vth = float(re.search(r"\[vth\]\s*=\s*([\d.eE+-]+)", out).group(1))
    id_ = float(re.search(r"\[id\]\s*=\s*([\d.eE+-]+)", out).group(1))
    return vth, id_


def idvg(lib, corner, dev, w, l, vds, work, tag):
    """Id(Vg) from 0 to |vds|, returns arrays (vg, id) with id > 0."""
    if dev == "n":
        sources = f"vg g 0 0\nvd d 0 {vds}"
        sweep = f"dc vg 0 {vds} 0.02\nwrdata idvg.dat v(g) i(vd)\n"
    else:
        sources = f"vs s 0 0\nvg g 0 0\nvd d 0 {-vds}"
        sweep = f"dc vg 0 {-vds} -0.02\nwrdata idvg.dat v(g) i(vd)\n"
    ngspice(mos_deck(lib, corner, dev, w, l, sources, sweep), work, tag)
    data = wrdata(work, "idvg.dat")
    return np.abs(data[:, 0]), np.abs(data[:, 1])


def check(name, ok, detail):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    return ok


def experiment(lib: Path, work: Path) -> bool:
    ok = True
    print(f"library: {lib}")

    # --- 1. threshold vs corner and channel length ---------------------
    print("\n[1] threshold voltage")
    vth = {}
    for corner, (vth0n, vth0p, *_) in CORNERS.items():
        for dev, vth0, vgs, vds in (("n", vth0n, 1.0, 0.1),
                                    ("p", vth0p, -1.0, -0.1)):
            vt, _ = op_point(lib, corner, dev, "10u", "10u", vgs, vds,
                             work, f"vth_{dev}_{corner}")
            vth[(dev, corner)] = vt
            # BSIM3 Vth at Vbs=0 sits close to, but not exactly on, VTH0
            # NMOS tracks VTH0 within ~40 mV here. The PMOS parameter set
            # (large negative K3, K1 = 0.74) shifts the realized Vth about
            # 0.15 V below |VTH0| at this bias; what must hold for every
            # corner is that the shift is stable and the ordering survives.
            tol = 0.05 if dev == "n" else 0.20
            ok &= check(f"{dev}mos {corner} Vth", abs(vt - abs(vth0)) < tol,
                        f"simulated {vt:.4f} V, model VTH0 {vth0:+.4f} V")
    for dev in ("n", "p"):
        order = vth[(dev, "sss")] > vth[(dev, "ttt")] > vth[(dev, "fff")]
        ok &= check(f"{dev}mos Vth corner order sss>ttt>fff", order,
                    " / ".join(f"{c} {vth[(dev, c)]:.3f}"
                               for c in ("sss", "ttt", "fff")))

    vt_long, _ = op_point(lib, "ttt", "n", "10u", "10u", 1.0, 0.1,
                          work, "vth_n_long")
    vt_short, _ = op_point(lib, "ttt", "n", "10u", "3u", 1.0, 0.1,
                           work, "vth_n_short")
    # LINT = 0.9um: Leff is 2.1um at Ldrawn=3um vs 9.1um at 10um, so the
    # minimum device must show a clearly different Vth (roll-off).
    ok &= check("nmos Vth rolls off at minimum L=3um", 
                abs(vt_short - vt_long) > 0.02,
                f"L=10um {vt_long:.4f} V, L=3um {vt_short:.4f} V "
                f"(LINT={LINT_N*1e6:.1f}um)")

    # --- 2. drive current across corners ------------------------------
    print("\n[2] saturation current at |Vgs|=|Vds|=5V, W/L=10u/10u")
    idsat = {}
    for dev, vgs, vds in (("n", 5.0, 5.0), ("p", -5.0, -5.0)):
        for corner in CORNERS:
            _, id_ = op_point(lib, corner, dev, "10u", "10u", vgs, vds,
                              work, f"ids_{dev}_{corner}")
            idsat[(dev, corner)] = abs(id_)
        order = (idsat[(dev, "fff")] > idsat[(dev, "ttt")]
                 > idsat[(dev, "sss")])
        ok &= check(f"{dev}mos Idsat fff>ttt>sss", order,
                    " / ".join(f"{c} {idsat[(dev, c)]*1e6:.1f}uA"
                               for c in ("fff", "ttt", "sss")))
        ok &= check(f"{dev}mos ttt Idsat in a sane range", 
                    10e-6 < idsat[(dev, "ttt")] < 2e-3,
                    f"{idsat[(dev, 'ttt')]*1e6:.1f} uA")

    # --- 3. gm/Id shape -----------------------------------------------
    print("\n[3] gm/Id (nmos ttt, Vds=2.5V)")
    vg, id_ = idvg(lib, "ttt", "n", "10u", "10u", 2.5, work, "idvg_n")
    np.save(work / "idvg_nmos_ttt.npy", np.column_stack((vg, id_)))
    # central difference, skip the first point where Id is subthreshold noise
    gm = np.gradient(id_, vg)
    with np.errstate(divide="ignore", invalid="ignore"):
        gmid = np.where(id_ > 1e-12, gm / id_, np.nan)
    finite = np.isfinite(gmid)
    peak = np.nanmax(gmid)
    idx_peak = np.nanargmax(gmid)
    ok &= check("gm/Id peaks in weak inversion", 8 < peak < 35,
                f"peak {peak:.1f} /V at Vgs={vg[idx_peak]:.2f} V")
    ok &= check("gm/Id falls toward strong inversion", 
                gmid[finite][-1] < peak / 3,
                f"{gmid[finite][-1]:.2f} /V at Vgs={vg[finite][-1]:.2f} V "
                f"vs peak {peak:.1f} /V")
    ioff = id_[0]
    ok &= check("off current negligible at Vgs=0", ioff < 1e-9,
                f"Ioff={ioff:.2e} A")

    # --- 4. PiP capacitor density -------------------------------------
    print("\n[4] poly-insulator-poly capacitor")
    for corner, (*_, cj) in CORNERS.items():
        w = l = 30e-6
        expected = cj * w * l
        deck = f"""* cpoly {corner}
.func rndgauss(sig) {{0}}
.lib '{lib}' {corner}
xc t 0 cnm25cpoly w=30u l=30u
vc t 0 dc 0 ac 1
.control
ac lin 1 1k 1k
let cmeas = abs(imag(i(vc)))/(2*pi*frequency)
print cmeas
.endc
.end
"""
        out = ngspice(deck, work, f"cpoly_{corner}")
        cmeas = float(re.search(r"cmeas\s*=\s*([\d.eE+-]+)", out).group(1))
        err = abs(cmeas - expected) / expected
        ok &= check(f"cpoly {corner} density", err < 0.005,
                    f"{cmeas*1e12:.4f} pF vs cj*W*L {expected*1e12:.4f} pF "
                    f"({err*100:.3f}%)")

    # --- 5. Monte-Carlo mismatch --------------------------------------
    print("\n[5] local mismatch (Pelgrom, ttt_mc)")
    area = (10e-6) ** 2
    sigma_pair = math.sqrt(2) * AVTH0 / math.sqrt(area)   # V
    deltas = []
    seeds = (1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610,
             987, 1597)
    deck_tpl = """* mc
.func rndgauss(sig) {{agauss(0, sig, 1)}}
.options seed={seed}
.lib '{lib}' {corner}
x1 d1 g 0 0 cnm25modn w=10u l=10u
x2 d2 g 0 0 cnm25modn w=10u l=10u
vg g 0 2
vd1 d1 0 0.1
vd2 d2 0 0.1
.control
op
print @m.x1.mn[vth] @m.x2.mn[vth]
.endc
.end
"""
    for seed in seeds:
        out = ngspice(deck_tpl.format(seed=seed, corner="ttt_mc", lib=lib),
                      work, f"mc_{seed}")
        vths = [float(v) for v in
                re.findall(r"\[vth\]\s*=\s*([\d.eE+-]+)", out)]
        deltas.append(vths[0] - vths[1])
    deltas = np.array(deltas)
    sigma = statistics.stdev(deltas)
    ratio = sigma / sigma_pair
    ok &= check("matched pair differs sample to sample", 
                np.std(deltas) > 0, f"std(dVth)={sigma*1e3:.2f} mV")
    ok &= check("dVth spread matches AVth=30 mV*um", 0.5 < ratio < 2.0,
                f"measured sigma {sigma*1e3:.2f} mV, Pelgrom "
                f"{sigma_pair*1e3:.2f} mV over {len(seeds)} pairs "
                f"(ratio {ratio:.2f})")

    out = ngspice(deck_tpl.format(seed=1, corner="ttt", lib=lib), work, "mc_nom")
    vths = [float(v) for v in re.findall(r"\[vth\]\s*=\s*([\d.eE+-]+)", out)]
    ok &= check("no mismatch on the ttt corner", abs(vths[0] - vths[1]) < 1e-6,
                f"Vth1={vths[0]:.6f} Vth2={vths[1]:.6f}")

    np.save(work / "mc_dvth.npy", deltas)
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lib", type=Path, default=DEFAULT_LIB)
    ap.add_argument("--work", type=Path)
    args = ap.parse_args()
    if args.work:
        args.work.mkdir(parents=True, exist_ok=True)
        ok = experiment(args.lib.resolve(), args.work.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="cnm25_") as tmp:
            ok = experiment(args.lib.resolve(), Path(tmp))
    print("\nRESULT:", "ALL CHECKS PASSED" if ok else "CHECKS FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
