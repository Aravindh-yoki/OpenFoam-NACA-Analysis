#!/usr/bin/env python3
"""Average Cd / Cl / Cm of the last N iterations from the forceCoeffs output.
Usage: python3 average_coeffs.py run2D [N=300] [U=1] [span=1.0] [rho=998.2] [chord=0.16923]"""
import glob, os, sys

case = sys.argv[1] if len(sys.argv) > 1 else "run2D"
N    = int(sys.argv[2]) if len(sys.argv) > 2 else 300
U    = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
span = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
rho  = float(sys.argv[5]) if len(sys.argv) > 5 else 998.2
c    = float(sys.argv[6]) if len(sys.argv) > 6 else 0.16923

files = sorted(glob.glob(os.path.join(case, "postProcessing", "forceCoeffs*", "*", "*.dat")))
if not files:
    sys.exit("No forceCoeffs output found in %s/postProcessing" % case)
f = files[-1]
header, rows = None, []
for line in open(f):
    if line.startswith("#"):
        t = line[1:].split()
        if t and t[0] == "Time":
            header = t
        continue
    p = line.split()
    if p:
        rows.append([float(v) for v in p])
if header is None:
    sys.exit("Could not read column names in " + f)
col = {n: i for i, n in enumerate(header)}
last = rows[-N:]
mean = lambda name: sum(r[col[name]] for r in last) / len(last)
Cd, Cl = mean("Cd"), mean("Cl")
q = 0.5 * rho * U * U * c * span          # dynamic pressure x reference area
print("File            :", f)
print("Iterations used : %d (up to iteration %g)" % (len(last), last[-1][0]))
print("Cd = %.5f   Cl = %.5f   Cl/Cd = %.2f" % (Cd, Cl, Cl / Cd if Cd else float('nan')))
for k in ("CmPitch", "Cm"):
    if k in col:
        print("%s = %.5f" % (k, mean(k))); break
print("Drag = %.4f N   Lift = %.4f N   (U=%g m/s, rho=%g, chord=%g m, span=%g m)"
      % (Cd * q, Cl * q, U, rho, c, span))
