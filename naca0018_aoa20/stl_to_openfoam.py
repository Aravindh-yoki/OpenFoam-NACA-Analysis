#!/usr/bin/env python3
"""
Flat 2D face STL (from FreeCAD)  ->  extruded airfoil STL for OpenFOAM snappyHexMesh

* finds the outline of the flat face (edges used by only one triangle)
* converts units (default mm -> m)
* puts the leading edge at the origin, optionally pitches the foil about the
  quarter-chord point (angle of attack, flow is always along +X)
* extrudes the outline along Z (+/- ZHALF) -> a 'tube' wall (open ends are intentional,
  the ends lie outside the CFD slab)

Usage:
  python3 stl_to_openfoam.py "NACA0012 final.stl" mesh3D/constant/triSurface/airfoil.stl
  python3 stl_to_openfoam.py "NACA0012 final.stl" out.stl --aoa 5
Options:
  --scale 0.001   unit factor (0.001 = STL is in mm, output in m)
  --aoa   0       angle of attack in degrees (positive = nose up)
  --zhalf 0.1     half length of the extrusion in Z (m)
"""
import argparse
import math
import os
import struct
import sys


def read_stl_triangles(path):
    """Return list of triangles [(x,y,z)*3]; handles ASCII and binary STL."""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        data = f.read()
    is_binary = False
    if len(data) >= 84:
        n = struct.unpack("<I", data[80:84])[0]
        is_binary = (84 + 50 * n == size)
    tris = []
    if is_binary:
        n = struct.unpack("<I", data[80:84])[0]
        off = 84
        for _ in range(n):
            v = struct.unpack("<12fH", data[off:off + 50])
            tris.append([(v[3], v[4], v[5]), (v[6], v[7], v[8]), (v[9], v[10], v[11])])
            off += 50
    else:
        verts = []
        for line in data.decode("utf-8", errors="ignore").splitlines():
            p = line.split()
            if len(p) == 4 and p[0].lower() == "vertex":
                verts.append((float(p[1]), float(p[2]), float(p[3])))
        tris = [verts[i:i + 3] for i in range(0, len(verts) - 2, 3)]
    if not tris:
        raise RuntimeError("No triangles found in %s" % path)
    return tris


def outline_loop(tris):
    """Ordered outline (list of (x,y)) of a flat triangulated face."""
    key = lambda p: (round(p[0], 5), round(p[1], 5))     # merge duplicate vertices
    edge_count, xy = {}, {}
    for t in tris:
        ids = []
        for p in t:
            k = key(p)
            xy.setdefault(k, (p[0], p[1]))
            ids.append(k)
        for a, b in ((0, 1), (1, 2), (2, 0)):
            e = (ids[a], ids[b]) if ids[a] < ids[b] else (ids[b], ids[a])
            edge_count[e] = edge_count.get(e, 0) + 1
    adj = {}
    for (a, b), c in edge_count.items():
        if c == 1:                                        # boundary edge
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
    if not adj:
        raise RuntimeError("No boundary edges found - is this a flat face STL?")
    # chain boundary edges into loops, keep the longest loop
    seen, loops = set(), []
    for start in adj:
        if start in seen:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = [n for n in adj[cur] if n != prev and n not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            loop.append(cur)
        loops.append(loop)
    loop = max(loops, key=len)
    return [xy[k] for k in loop]


def signed_area(pts):
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % len(pts)][1] -
                     pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("infile")
    ap.add_argument("outfile")
    ap.add_argument("--scale", type=float, default=0.001)
    ap.add_argument("--aoa", type=float, default=0.0)
    ap.add_argument("--zhalf", type=float, default=0.1)
    a = ap.parse_args()

    pts = [(x * a.scale, y * a.scale) for x, y in outline_loop(read_stl_triangles(a.infile))]

    # leading edge -> origin, mid-thickness -> y = 0
    xmin = min(p[0] for p in pts)
    xmax = max(p[0] for p in pts)
    ymid = 0.5 * (min(p[1] for p in pts) + max(p[1] for p in pts))
    chord = xmax - xmin
    pts = [(x - xmin, y - ymid) for x, y in pts]

    # angle of attack: rotate about quarter chord (nose up = clockwise for flow along +x)
    if abs(a.aoa) > 1e-12:
        th = -math.radians(a.aoa)
        c, s = math.cos(th), math.sin(th)
        px = 0.25 * chord
        pts = [(px + (x - px) * c - y * s, (x - px) * s + y * c) for x, y in pts]

    if signed_area(pts) < 0:                              # make counter-clockwise
        pts.reverse()

    n, z0, z1 = len(pts), -a.zhalf, a.zhalf
    with open(a.outfile, "w") as f:
        f.write("solid airfoil\n")
        for i in range(n):
            (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
            dx, dy = x1 - x0, y1 - y0
            L = math.hypot(dx, dy)
            if L == 0.0:
                continue
            nx, ny = dy / L, -dx / L                       # outward normal (CCW outline)
            for tri in (((x0, y0, z0), (x1, y1, z0), (x1, y1, z1)),
                        ((x0, y0, z0), (x1, y1, z1), (x0, y0, z1))):
                f.write(" facet normal %.6e %.6e 0\n  outer loop\n" % (nx, ny))
                for v in tri:
                    f.write("   vertex %.9e %.9e %.9e\n" % v)
                f.write("  endloop\n endfacet\n")
        f.write("endsolid airfoil\n")

    area = abs(signed_area(pts))
    print("Outline points : %d" % n)
    print("Chord          : %.5f m   (area %.6f m^2 = %.4f c^2)" % (chord, area, area / chord ** 2))
    print("Angle of attack: %.2f deg" % a.aoa)
    print("Written        : %s" % a.outfile)


if __name__ == "__main__":
    main()
