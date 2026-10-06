# Auto-Casing — BASIRA well-engineering tools

Single-file HTML applications; open them in a browser, no install needed.

| File | What it is |
|---|---|
| `BASIRA-EDM.html` | **BASIRA EDM v4.0** — well path (COMPASS-style), casing seat selection (CasingSeat-style) and casing stress design (StressCheck-style), metric, API TR 5C3 / 5CT / ISO 10400 / NACE MR0175 |
| `basira.html` | BASIRA autonomous casing architecture generator |
| `CBL_VDL_Tool_v2_with_Fracture_Pressure.html` | CBL/VDL cement-bond analysis with fracture-pressure module |

## BASIRA EDM v4.0 — changes from v3.26

**Calculation fixes**
- Hydrostatic gradient is now the exact 0.4335275 psi/ft per sg (was 0.433, −0.12 % on every pressure).
- Seat selection uses the pore pressure of the open hole only and also requires the next-hole mud to stay
  below frac − kick margin over the whole open hole, not just at the shoe.
- Shoes are rounded to whole metres on the safe side (a rounded shoe could fall just outside its criterion).
- Triaxial plot: collapse load points now use the same installed axial force as the triaxial check.
- Conductor and surface strings created from the seats are cemented to surface.

**New — well path (COMPASS-style)**: targets with hit/miss, build-and-hold plan to target, vertical
section azimuth, closure, build / turn rates, toolface, interpolation at any MD or TVD, plan view.

**New — CasingSeat-style**: differential-sticking limit enforced in seat selection, *Governed by* column,
volumetric kick tolerance (bbl) per hole section, optional kick-volume criterion.

**New — StressCheck-style**: API TR 5C3 / ISO 10400 collapse with internal pressure (option), buckling of the
free pipe above TOC (Lubinski / Paslay–Dawson), API coupling-OD clearance checks.

## Verification

`npm test` (or `node test/run-tests.js`) runs 129 checks against published API casing ratings, API 5C3
Table 1, exact directional geometry and independent hand calculations. Latest results:
[`test/TEST-REPORT.md`](test/TEST-REPORT.md).
