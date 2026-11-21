# NACA 0012 – 2D lift & drag in OpenFOAM (water, steady RANS k-ω SST)

Chord c = 0.16923 m · fresh water 20 °C (ν = 1.004e-6 m²/s, ρ = 998.2 kg/m³) · default U = 1 m/s (Re ≈ 1.7e5)

```
naca0012_openfoam_case/
├── stl_to_openfoam.py   flat FreeCAD STL  ->  extruded, metre-scaled STL (+ optional angle of attack)
├── Allmesh              blockMesh + snappyHexMesh (3-D slab)  ->  extrudeMesh (true 2-D mesh)
├── Allrun               simpleFoam + y+ + lift/drag summary
├── average_coeffs.py    mean Cd, Cl, Cm and forces in newtons from the forceCoeffs output
├── mesh3D/              background mesh + snappyHexMeshDict
└── run2D/               final 2-D case: 0/, constant/, system/
```

## Why the STL has to be converted
Your FreeCAD STL is a *flat surface* (zero thickness, no volume). snappyHexMesh needs a wall that
cuts through the whole slab, so `stl_to_openfoam.py` extrudes the outline in Z (±0.1 m), converts
mm → m, puts the leading edge at the origin and (optionally) rotates it by the angle of attack.
Flow is always along +X; lift is +Y.

## Run (Linux or Windows WSL2 with OpenFOAM sourced)
```bash
# 0) copy the case to the Linux file system (faster, no spaces in the path)
cp -r "/mnt/y/Krishna Defence/Savior/NACA 0012/naca0012_openfoam_case" ~/naca0012
cd ~/naca0012
cp "/mnt/y/Krishna Defence/Savior/NACA 0012/NACA0012 final.stl" .

# 1) STL -> OpenFOAM geometry   (--aoa = angle of attack in degrees, nose up positive)
python3 stl_to_openfoam.py "NACA0012 final.stl" mesh3D/constant/triSurface/airfoil.stl --aoa 0

# 2) mesh (about 3 min):  3-D slab -> 2-D mesh in run2D/
./Allmesh                         # must end with "Mesh OK."  (see run2D/log.checkMesh2D)

# 3) solve + results
./Allrun
python3 average_coeffs.py run2D 300 1.0 0.30   # last 300 its, U = 1 m/s, span = 0.30 m
```
If a script complains about `\r`, run `dos2unix Allmesh Allrun` first.
If the `Y:` drive is not visible in WSL: `sudo mkdir -p /mnt/y && sudo mount -t drvfs Y: /mnt/y`.
View the result: `touch run2D/case.foam` and open it in ParaView.

## What to change for your test condition
| Item | Where | Rule |
|---|---|---|
| Speed U | `run2D/0/U` (2×), `magUInf` in `run2D/system/controlDict` | Re = U·c/ν |
| Water properties | `constant/transportProperties` (ν), `rhoInf` in controlDict (2×) | 20 °C: ν = 1.004e-6, ρ = 998.2 |
| Turbulence at inlet | `0/k`, `0/omega` | k = 1.5 (I·U)², ω ≈ 10·U/c (I = 0.5–1 % for a tank/tunnel) |
| First cell height | `firstLayerThickness` in `mesh3D/system/snappyHexMeshDict` | y₁ ≈ 2·y⁺·ν/u_τ, u_τ = U·√(Cf/2), Cf ≈ 0.026·Re^(−1/7); target y⁺ ≈ 1 |
| Angle of attack | `--aoa` in step 1 | drag/lift directions stay (1 0 0)/(0 1 0) |
| Span / thickness | `thickness` in `extrudeMeshDict`, `Aref = c · thickness` in controlDict | only used to normalise Cl/Cd, results scale with span |

## Results
* `run2D/postProcessing/forceCoeffs1/0/…dat` : Cd, Cl, Cm for every iteration
* `run2D/postProcessing/forces1/0/force.dat` : pressure + viscous force (N, for the 0.01 m model thickness – multiply by span/0.01)
* **Drag** D = Cd · ½ρU²·c·b  **Lift** L = Cl · ½ρU²·c·b  (b = real span), done for you by `average_coeffs.py`.

## Quality checklist
1. `Mesh OK.` in `log.checkMesh2D`; airfoil patch has 8 prism layers (see `mesh3D/log.snappyHexMesh`).
2. Residuals below ~1e-5 and Cd/Cl flat over the last few hundred iterations.
3. y⁺ (`log.yPlus`) ideally ≈ 1 (works up to ≈ 5; if 30–300 the wall functions take over – also fine).
4. Mesh sensitivity: change `level (6 6)` to `(5 5)` and `(7 7)`; Cd/Cl should change by < 2 %.
5. Domain size: ±5c / 10c downstream is adequate for a first estimate (blockage ≈ 10 %).

## Notes
* Single-phase, fully submerged hydrofoil. No free surface, no cavitation (use interFoam / cavitatingFoam for that).
* Steady k-ω SST treats the boundary layer as turbulent. Near Re ≈ 1e5 a laminar separation bubble can matter –
  compare with a transition model (kOmegaSSTLM) or experiment if accuracy is critical.
* Tested with OpenFOAM v1912 (openfoam.com). Newer versions: `constant/geometry` is picked up automatically
  (Allmesh copies the STL there). OpenFOAM Foundation v11+: rename `transportProperties` → `physicalProperties`
  (`viscosityModel constant; nu 1.004e-06;`), `turbulenceProperties` → `momentumTransport`
  (`simulationType RAS; RAS { model kOmegaSST; }`) and run `foamRun -solver incompressibleFluid`.
