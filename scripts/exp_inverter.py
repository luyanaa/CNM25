#!/usr/bin/env python3
"""CNM25 inverter experiment.

Simulates the golden LVS cell (NMOS 9u/3u, PMOS 18u/3u) at the three
process corners and checks that it behaves like a logic inverter:

  * output swings rail to rail,
  * the transfer curve crosses Vin exactly once (one trip point),
  * the trip point moves with the corner in the direction the measured
    PMOS/NMOS strength ratio predicts,
  * small-signal gain at the trip point is large,
  * a 5 V pulse into 1 pF gives finite, positive propagation delays.

Gain and delay are measured in Python from saved waveforms: vectors
created inside an ngspice control block do not survive the `alter`
re-expansion of the subcircuits, so the deck only sweeps and writes data.

Usage: exp_inverter.py [--lib PATH] [--work DIR]
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_LIB = (HERE.parent / "cnm25" / "libs.tech" / "ngspice"
               / "cnm25mod_ngspice.lib")

DECK = """* inverter {corner}
.func rndgauss(sig) {{0}}
.lib '{lib}' {corner}
* golden LVS cell: libs.ref/cnm25_test/spice/inverter.spice
xmn out in 0   0   cnm25modn w=9u  l=3u
xmp out in vdd vdd cnm25modp w=18u l=3u
vdd vdd 0 5
vin in 0 dc 0 pulse(0 5 20n 0.5n 0.5n 200n 400n)
cl out 0 1p
.control
set wr_singlescale
set filetype=ascii
dc vin 0 5 0.01
wrdata vtc.dat v(in) v(out)
tran 0.2n 420n
wrdata tran.dat v(in) v(out)
.endc
.end
"""

# Diode-connected strength at |Vgs| = 2.5 V, same sizes as the inverter.
RATIO_DECK = """* strength {corner}
.func rndgauss(sig) {{0}}
.lib '{lib}' {corner}
xn dn dn 0  0  cnm25modn w=9u  l=3u
xp dp gp 0  0  cnm25modp w=18u l=3u
vn dn 0 2.5
vg gp 0 -2.5
vp dp 0 -2.5
.control
op
print i(vn) i(vp)
.endc
.end
"""


class SpiceError(RuntimeError):
    pass


def run(netlist: str, work: Path, tag: str) -> str:
    (work / f"{tag}.sp").write_text(netlist)
    proc = subprocess.run(["ngspice", "-n", "-b", f"{tag}.sp"],
                          cwd=work, capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    (work / f"{tag}.log").write_text(out)
    if proc.returncode != 0 or re.search(r"fatal error|Simulation interrupted",
                                          out):
        tail = "\n".join(out.strip().splitlines()[-12:])
        raise SpiceError(f"{tag} failed (rc={proc.returncode}):\n{tail}")
    return out


def load_dat(path: Path) -> np.ndarray:
    """Read a `wrdata` file.

    With `wr_singlescale` the file is `scale value value ...` — three
    columns for two traces. Without it every trace repeats the scale, so
    the even columns are dropped.
    """
    rows = [[float(x) for x in line.split()]
            for line in path.read_text().splitlines() if line.strip()]
    data = np.array(rows)
    if data.shape[1] % 2 == 0:
        keep = [0] + list(range(2, data.shape[1], 2))
        data = data[:, keep]
    return data


def crossing(x, y, level):
    """First time `y` crosses `level`, linearly interpolated on `x`."""
    above = y >= level
    idx = np.where(np.diff(above.astype(int)))[0]
    if len(idx) == 0:
        return None
    i = idx[0]
    frac = (level - y[i]) / (y[i + 1] - y[i])
    return x[i] + frac * (x[i + 1] - x[i])


def check(name, cond, detail):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}: {detail}")
    return cond


def experiment(lib: Path, work: Path) -> bool:
    ok = True
    print(f"library: {lib}")

    print("\n[1] device strength at the golden sizes, |Vgs|=2.5V")
    ratio = {}
    for corner in ("ttt", "sss", "fff"):
        out = run(RATIO_DECK.format(lib=lib, corner=corner),
                  work, f"ratio_{corner}")
        vals = [abs(float(v)) for v in
                re.findall(r"i\(v[np]\)\s*=\s*([\d.eE+-]+)", out)]
        ratio[corner] = vals[1] / vals[0]
        ok &= check(f"{corner} both devices conduct",
                    1e-6 < vals[0] < 5e-3 and 1e-6 < vals[1] < 5e-3,
                    f"In={vals[0]*1e6:.1f}uA Ip={vals[1]*1e6:.1f}uA "
                    f"Ip/In={ratio[corner]:.3f}")

    print("\n[2] voltage transfer and timing, VDD=5V, CL=1pF")
    trip = {}
    for corner in ("ttt", "sss", "fff"):
        sub = work / corner
        sub.mkdir(exist_ok=True)
        run(DECK.format(lib=lib, corner=corner), sub, "inv")

        cols = load_dat(sub / "vtc.dat").T
        vin, vout = cols[0], cols[-1]
        voh, vol = vout[0], vout[-1]
        crossings = np.where(np.diff(np.sign(vout - vin)))[0]
        trip[corner] = crossing(vin, vout - vin, 0.0)

        # small-signal gain from the slope through the trip point
        span = (vin > trip[corner] - 0.05) & (vin < trip[corner] + 0.05)
        gain = np.polyfit(vin[span], vout[span], 1)[0]

        t, waves = load_dat(sub / "tran.dat")[:, 0], None
        data = load_dat(sub / "tran.dat")
        t, vin_t, vout_t = data.T[:3]
        tphl = crossing(t, vout_t, 2.5)          # output falls first
        rise = np.where(np.diff((vin_t >= 2.5).astype(int)) == -1)[0]
        tplh = None
        if len(rise):
            j = rise[0]
            tplh = crossing(t[j:], vout_t[j:], 2.5)
            tplh = None if tplh is None else tplh - t[j]
            # tphl above is measured from t=0; the input edge is at 20 ns
        tphl = None if tphl is None else tphl - 20e-9

        np.save(work / f"vtc_{corner}.npy", np.column_stack((vin, vout)))

        ok &= check(f"{corner} rail-to-rail", vol < 0.05 and voh > 4.95,
                    f"VOH={voh:.4f} V VOL={vol:.4g} V")
        ok &= check(f"{corner} single trip point",
                    len(crossings) == 1 and 1.0 < trip[corner] < 4.0,
                    f"Vtrip={trip[corner]:.3f} V, "
                    f"{len(crossings)} crossing(s)")
        ok &= check(f"{corner} gain", gain < -5, f"Av={gain:.1f}")
        ok &= check(f"{corner} delay",
                    tphl is not None and tplh is not None
                    and 0 < tphl < 100e-9 and 0 < tplh < 100e-9,
                    "unmeasurable" if tphl is None or tplh is None else
                    f"tPHL={tphl*1e9:.2f} ns tPLH={tplh*1e9:.2f} ns")

    print("\n[3] trip point tracks the PMOS/NMOS strength ratio")
    strongest = max(ratio, key=ratio.get)
    weakest = min(ratio, key=ratio.get)
    ok &= check(f"Vtrip highest at {strongest}, lowest at {weakest}",
                trip[strongest] > trip[weakest],
                " / ".join(f"{c}: Ip/In {ratio[c]:.2f}, "
                           f"Vtrip {trip[c]:.3f} V"
                           for c in ("fff", "ttt", "sss")))
    spread = max(trip.values()) - min(trip.values())
    ok &= check("corners actually move the trip point", spread > 0.1,
                f"spread {spread*1e3:.0f} mV")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lib", type=Path, default=DEFAULT_LIB)
    ap.add_argument("--work", type=Path)
    args = ap.parse_args()
    if args.work:
        args.work.mkdir(parents=True, exist_ok=True)
        good = experiment(args.lib.resolve(), args.work.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="cnm25inv_") as tmp:
            good = experiment(args.lib.resolve(), Path(tmp))
    print("\nRESULT:", "ALL CHECKS PASSED" if good else "CHECKS FAILED")
    sys.exit(0 if good else 1)


if __name__ == "__main__":
    main()
