#!/usr/bin/env python3
"""Generate the rotor deck plate STL.

The rotor's pockets are through-cuts (`medicine_rotor_parametric.scad` extrudes
them over `rotor_thickness + 1.0` from z = -0.5), so nothing holds a container
up. This plate is the floor the loaded rotor slides on, with a single aperture
at the drop station.

Geometry is expressed as an annulus minus a list of angular-sector cutouts, so
every face lands exactly on a cutout boundary and the mesh stays watertight.

Edit the constants, re-run, reprint:

    ./.venv/bin/python hardware/3d-print/source/deck_plate_generator.py
"""

from __future__ import annotations

import math
import struct
from pathlib import Path

import numpy as np

# --- Geometry, mm -----------------------------------------------------------
# Rotor is OD 172 with pockets on a 57 mm centre circle, 35.8 radial x 20.8
# tangential. The deck must cover the whole pocket circle and overhang the rotor
# rim so the disc cannot drop off its own support.
R_OUTER = 90.0     # 180 mm OD vs the 172 mm rotor -> 4 mm of rim support
R_BORE = 6.0       # 12 mm centre clearance for the drive shaft / hub
THICKNESS = 5.0    # stiff enough not to bow under nine loaded pockets

POCKET_RADIUS = 57.0
POCKET_RADIAL = 35.8
POCKET_TANGENTIAL = 20.8

# Drop aperture. Deliberately larger than the pocket in both directions so a
# container that is cocked inside its pocket still falls clean instead of
# catching the deck edge. The pocket only permits +/-1.49 deg of yaw, and a
# cocked container stands 16.98 mm, so the exit must not be the tight feature.
APERTURE_RADIAL_CLEARANCE = 4.0     # 2 mm per side
APERTURE_TANGENTIAL = 26.0          # vs 20.8 pocket -> 2.6 mm per side

# Mounting: 4x M4 clearance, clear of both the pocket circle and the aperture.
BOLT_CIRCLE_R = 83.0
BOLT_CLEARANCE_D = 4.5
BOLT_ANGLES_DEG = (45.0, 135.0, 225.0, 315.0)

ANGULAR_STEP_DEG = 2.0  # arc refinement between critical angles

OUT = Path(__file__).resolve().parents[1] / "PRINT-READY" / "MAIN - rotor deck plate.stl"


def sector(theta_c_deg: float, half_width_deg: float, r_in: float, r_out: float):
    return (
        math.radians(theta_c_deg - half_width_deg),
        math.radians(theta_c_deg + half_width_deg),
        r_in,
        r_out,
    )


def build_cutouts():
    cuts = []

    # Drop aperture, centred at 0 deg on the pocket circle.
    r_in = POCKET_RADIUS - (POCKET_RADIAL + APERTURE_RADIAL_CLEARANCE) / 2.0
    r_out = POCKET_RADIUS + (POCKET_RADIAL + APERTURE_RADIAL_CLEARANCE) / 2.0
    half = math.degrees(APERTURE_TANGENTIAL / 2.0 / POCKET_RADIUS)
    cuts.append(sector(0.0, half, r_in, r_out))

    # Bolt holes as narrow sectors. For an M4 clearance hole the barrel shape is
    # dimensionally irrelevant and keeps the mesh exact on its boundaries.
    bolt_half = math.degrees(BOLT_CLEARANCE_D / 2.0 / BOLT_CIRCLE_R)
    for a in BOLT_ANGLES_DEG:
        cuts.append(
            sector(a, bolt_half,
                   BOLT_CIRCLE_R - BOLT_CLEARANCE_D / 2.0,
                   BOLT_CIRCLE_R + BOLT_CLEARANCE_D / 2.0)
        )
    return cuts


def solid_intervals(theta: float, cuts):
    """Radial spans of material at this angle, after subtracting the cutouts."""
    spans = [(R_BORE, R_OUTER)]
    for t0, t1, r0, r1 in cuts:
        inside = t0 <= theta <= t1 or t0 <= theta - 2 * math.pi <= t1 or t0 <= theta + 2 * math.pi <= t1
        if not inside:
            continue
        nxt = []
        for a, b in spans:
            if r1 <= a or r0 >= b:
                nxt.append((a, b))
                continue
            if a < r0:
                nxt.append((a, r0))
            if r1 < b:
                nxt.append((r1, b))
        spans = nxt
    return spans


def main() -> int:
    cuts = build_cutouts()

    # Sample angles: every cutout edge exactly, plus refinement between them.
    critical = set()
    for t0, t1, _, _ in cuts:
        for t in (t0, t1):
            critical.add(t % (2 * math.pi))
    step = math.radians(ANGULAR_STEP_DEG)
    angles = sorted(critical | {i * step for i in range(int(2 * math.pi / step) + 1)})
    angles = [a for a in angles if a < 2 * math.pi] + [2 * math.pi]

    tris: list[tuple] = []

    def quad(p1, p2, p3, p4):
        tris.append((p1, p2, p3))
        tris.append((p1, p3, p4))

    def pt(r, t, z):
        return (r * math.cos(t), r * math.sin(t), z)

    # Every face must share a radial vertex set, or a long edge on one side of a
    # critical angle meets several short ones on the other and the mesh is
    # non-manifold by T-junction. Subdivide every span at the same breakpoints.
    breaks = sorted({R_BORE, R_OUTER} | {r for _, _, r0, r1 in cuts for r in (r0, r1)})

    def split(r0, r1):
        pts = [r0] + [b for b in breaks if r0 + 1e-9 < b < r1 - 1e-9] + [r1]
        return list(zip(pts, pts[1:]))

    for i in range(len(angles) - 1):
        ta, tb = angles[i], angles[i + 1]
        if tb - ta < 1e-9:
            continue
        mid = (ta + tb) / 2.0
        for r0, r1 in solid_intervals(mid, cuts):
            for c0, c1 in split(r0, r1):
                # top (+Z) and bottom (-Z)
                quad(pt(c0, ta, THICKNESS), pt(c1, ta, THICKNESS),
                     pt(c1, tb, THICKNESS), pt(c0, tb, THICKNESS))
                quad(pt(c0, tb, 0), pt(c1, tb, 0), pt(c1, ta, 0), pt(c0, ta, 0))
            # arc walls only at the true material boundaries, not the splits
            quad(pt(r0, ta, 0), pt(r0, ta, THICKNESS),
                 pt(r0, tb, THICKNESS), pt(r0, tb, 0))
            quad(pt(r1, tb, 0), pt(r1, tb, THICKNESS),
                 pt(r1, ta, THICKNESS), pt(r1, ta, 0))

    # Radial end caps wherever the solid spans change across a critical angle.
    # This needs real interval subtraction: when a cutout splits [6, 90] into
    # [6, 37.1] + [76.9, 90], the face to cap is the missing [37.1, 76.9], not
    # the three spans a naive set difference would report.
    def subtract(a_list, b_list):
        out = []
        for a0, a1 in a_list:
            pieces = [(a0, a1)]
            for b0, b1 in b_list:
                nxt = []
                for p0, p1 in pieces:
                    if b1 <= p0 or b0 >= p1:
                        nxt.append((p0, p1))
                        continue
                    if p0 < b0 - 1e-9:
                        nxt.append((p0, b0))
                    if b1 + 1e-9 < p1:
                        nxt.append((b1, p1))
                pieces = nxt
            out.extend(pieces)
        return [(a, b) for a, b in out if b - a > 1e-9]

    eps = 1e-6
    for t in sorted(critical):
        before = solid_intervals(t - eps, cuts)
        after = solid_intervals(t + eps, cuts)
        # Material ends here: the cap faces the +theta side.
        for r0, r1 in subtract(before, after):
            for c0, c1 in split(r0, r1):
                quad(pt(c0, t, THICKNESS), pt(c1, t, THICKNESS), pt(c1, t, 0), pt(c0, t, 0))
        # Material starts here: the cap faces the -theta side.
        for r0, r1 in subtract(after, before):
            for c0, c1 in split(r0, r1):
                quad(pt(c0, t, 0), pt(c1, t, 0), pt(c1, t, THICKNESS), pt(c0, t, THICKNESS))

    data = bytearray(b"\0" * 80)
    data += struct.pack("<I", len(tris))
    for a, b, c in tris:
        n = np.cross(np.subtract(b, a), np.subtract(c, a))
        ln = np.linalg.norm(n)
        n = n / ln if ln > 1e-12 else np.array([0.0, 0.0, 1.0])
        data += struct.pack("<3f", *n)
        for p in (a, b, c):
            data += struct.pack("<3f", *p)
        data += struct.pack("<H", 0)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(bytes(data))

    ap = cuts[0]
    print(f"wrote {OUT.name}")
    print(f"  triangles     : {len(tris)}")
    print(f"  OD            : {R_OUTER * 2:.1f} mm   thickness {THICKNESS:.1f} mm")
    print(f"  centre bore   : {R_BORE * 2:.1f} mm")
    print(f"  aperture      : R{ap[2]:.1f}-{ap[3]:.1f} "
          f"({ap[3] - ap[2]:.1f} mm radial) x {APERTURE_TANGENTIAL:.1f} mm tangential")
    print(f"  vs pocket     : {POCKET_RADIAL:.1f} x {POCKET_TANGENTIAL:.1f} mm")
    print(f"  bolts         : {len(BOLT_ANGLES_DEG)}x M4 clearance @ R{BOLT_CIRCLE_R:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
