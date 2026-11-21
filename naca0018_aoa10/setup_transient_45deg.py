#!/usr/bin/env python3
"""
Prepare a COPY of the working NACA 0012 case for a high angle of attack (e.g. 45 deg).

Run it from the case root (the folder that contains mesh3D/ and run2D/):
    python3 setup_transient_45deg.py            # default 8 s of simulated time
    python3 setup_transient_45deg.py 10         # 10 s

What it changes
  mesh3D/system/snappyHexMeshDict
      * bigger refinement boxes (the stalled foil and its wake sit lower / wider)
      * coarser mesh, no prism layers (wall functions, y+ ~ 40 at U = 1 m/s)
        -> a transient run is then ~1 h instead of ~1 day
  run2D/system/controlDict   steady -> transient, adjustable time step (maxCo 1)
  run2D/system/fvSchemes     steadyState -> Euler, no 'bounded'
  run2D/system/fvSolution    SIMPLE -> PIMPLE (2 outer correctors)
Originals are saved with the ending .steady
Works with both the old (levels ((1E15 n))) and the new (level n) region syntax.
"""
import re
import shutil
import sys

END_TIME = sys.argv[1] if len(sys.argv) > 1 else "8"


def backup(path):
    try:
        shutil.copy(path, path + ".steady")
    except FileNotFoundError:
        sys.exit("Cannot find %s - run this from the case root folder." % path)


# ------------------------------------------------------------------ mesh
f = "mesh3D/system/snappyHexMeshDict"
backup(f)
s = open(f).read()

s, n1 = re.subn(r"^addLayers\s+true;", "addLayers       false;", s, flags=re.M)
s, n2 = re.subn(r"level\s*\(\s*6\s+6\s*\)", "level (5 5)", s)


def set_box(s, name, lo, hi):
    pat = r"(%s[^{}]*\{[^{}]*?type\s+\w+;\s*)min\s*\([^)]*\);\s*max\s*\([^)]*\);" % name
    rep = r"\1min     (%s);\n        max     (%s);" % (lo, hi)
    return re.subn(pat, rep, s)


def set_level(s, name, lvl):
    pat = r"(%s\s*\{\s*mode\s+inside;\s*)(levels\s*\(\(1E15\s+\d+\)\)|level\s+\d+);" % name

    def f_(m):
        if m.group(2).startswith("levels"):
            return "%slevels ((1E15 %d));" % (m.group(1), lvl)
        return "%slevel %d;" % (m.group(1), lvl)
    return re.subn(pat, f_, s)


s, n3 = set_box(s, "nearBox", "-0.05 -0.15 -1", " 0.25  0.09  1")
s, n4 = set_box(s, "wakeBox", "-0.10 -0.40 -1", " 1.20  0.20  1")
s, n5 = set_level(s, "nearBox", 4)
s, n6 = set_level(s, "wakeBox", 3)
if min(n1, n2, n3, n4, n5, n6) == 0:
    sys.exit("snappyHexMeshDict has an unexpected layout (changes made: %s) - nothing written."
             % [n1, n2, n3, n4, n5, n6])
open(f, "w").write(s)

# ------------------------------------------------------------ controlDict
f = "run2D/system/controlDict"
backup(f)
s = open(f).read()
for pat, rep in (
    (r"^endTime\s+.*$", "endTime         %s;" % END_TIME),
    (r"^deltaT\s+.*$", "deltaT          0.0005;\nadjustTimeStep  yes;\nmaxCo           1;\nmaxDeltaT       0.005;"),
    (r"^writeControl\s+.*$", "writeControl    adjustableRunTime;"),
    (r"^writeInterval\s+.*$", "writeInterval   1;"),
):
    s, n = re.subn(pat, rep, s, count=1, flags=re.M)
    if n == 0:
        sys.exit("controlDict: could not find '%s'" % pat)
open(f, "w").write(s)

# --------------------------------------------------------------- fvSchemes
f = "run2D/system/fvSchemes"
backup(f)
open(f, "w").write("""FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      fvSchemes;
}

ddtSchemes      { default Euler; }

gradSchemes
{
    default         Gauss linear;
    grad(U)         cellLimited Gauss linear 1;
}

divSchemes
{
    default         none;
    div(phi,U)      Gauss linearUpwind grad(U);
    div(phi,k)      Gauss limitedLinear 1;
    div(phi,omega)  Gauss limitedLinear 1;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}

laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }
wallDist        { method meshWave; }
""")

# -------------------------------------------------------------- fvSolution
f = "run2D/system/fvSolution"
backup(f)
open(f, "w").write("""FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      fvSolution;
}

solvers
{
    "p|pFinal"
    {
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-8;
        relTol          0.01;
    }
    "(U|k|omega)(Final)?"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-8;
        relTol          0.01;
    }
}

PIMPLE
{
    nOuterCorrectors          2;
    nCorrectors               2;
    nNonOrthogonalCorrectors  1;
    momentumPredictor         yes;
}
""")

print("Done. Transient set-up written (end time %s s). Originals kept as *.steady" % END_TIME)
print("Next:  python3 stl_to_openfoam.py nacaprof.stl mesh3D/constant/triSurface/airfoil.stl --aoa 45")
print("       ./Allmesh   &&   ./Allrun")
