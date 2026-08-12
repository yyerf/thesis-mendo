#!/usr/bin/env python3
"""Verify — and optionally repair — the print-ready STLs.

A mesh that is not watertight may slice differently on different slicers, or
silently lose a wall. Before committing 9 h to a rotor it is worth knowing.

    ./.venv/bin/python hardware/3d-print/source/stl_qa.py           # report
    ./.venv/bin/python hardware/3d-print/source/stl_qa.py --repair  # + fix

Repair only removes **degenerate (zero-area) triangles**. Those carry no
geometry but each one duplicates an edge, which is what makes an otherwise sound
mesh read as non-manifold. Nothing else is touched: no re-meshing, no hole
filling, no vertex merging. If a file is broken for any other reason this tool
reports it and leaves it alone.
"""

from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path

import numpy as np

PRINT_READY = Path(__file__).resolve().parents[1] / "PRINT-READY"
PETG_DENSITY = 1.27          # g/cm3
EFFECTIVE_FILL = 0.45        # walls + infill, empirical for these settings


def read_stl(path: Path):
    b = path.read_bytes()
    count = struct.unpack("<I", b[80:84])[0]
    tris, off = [], 84
    for _ in range(count):
        v = struct.unpack("<12fH", b[off:off + 50])
        off += 50
        tris.append(tuple(tuple(v[3 + i * 3:6 + i * 3]) for i in range(3)))
    return tris


def write_stl(path: Path, tris) -> None:
    data = bytearray(b"\0" * 80) + struct.pack("<I", len(tris))
    for a, b, c in tris:
        n = np.cross(np.subtract(b, a), np.subtract(c, a))
        ln = np.linalg.norm(n)
        n = n / ln if ln > 1e-12 else np.array([0.0, 0.0, 1.0])
        data += struct.pack("<3f", *n)
        for p in (a, b, c):
            data += struct.pack("<3f", *p)
        data += struct.pack("<H", 0)
    path.write_bytes(bytes(data))


QUANT = 4  # decimal places; 0.1 micron. Must match analyse()'s edge keys, or a
           # sliver reads as non-degenerate here while still duplicating an edge.


def degenerate(t) -> bool:
    q = [tuple(round(c, QUANT) for c in v) for v in t]
    if len({q[0], q[1], q[2]}) < 3:
        return True
    n = np.cross(np.subtract(q[1], q[0]), np.subtract(q[2], q[0]))
    return float(np.linalg.norm(n)) < 1e-9


def analyse(tris):
    q = [tuple(tuple(round(c, QUANT) for c in v) for v in t) for t in tris]
    edges = Counter()
    for t in q:
        for i in range(3):
            edges[frozenset((t[i], t[(i + 1) % 3]))] += 1
    bad = sum(1 for v in edges.values() if v != 2)
    pts = np.array([v for t in tris for v in t])
    vol = sum(np.dot(np.array(t[0]), np.cross(np.array(t[1]), np.array(t[2]))) / 6.0
              for t in tris) / 1000.0
    bbox = [float(pts[:, i].max() - pts[:, i].min()) for i in range(3)]
    return bad, vol, bbox, sum(1 for t in tris if degenerate(t))


def main() -> int:
    repair = "--repair" in sys.argv
    files = sorted(PRINT_READY.glob("*.stl"))
    if not files:
        print(f"no STLs in {PRINT_READY}")
        return 1

    print(f"{'file':<34} {'tri':>6} {'seal':>6} {'vol cm3':>8} {'~g':>5}  bbox mm")
    print("-" * 104)
    failures = 0
    for p in files:
        tris = read_stl(p)
        bad, vol, bbox, degen = analyse(tris)

        repaired = 0
        if bad and degen and repair:
            repaired = degen
            tris = [t for t in tris if not degenerate(t)]
            write_stl(p, tris)
            bad, vol, bbox, degen = analyse(tris)

        seal = "OK" if bad == 0 else f"{bad} BAD"
        grams = vol * PETG_DENSITY * EFFECTIVE_FILL
        bb = f"{bbox[0]:.1f} x {bbox[1]:.1f} x {bbox[2]:.1f}"
        if bad:
            flag = f"   <-- {degen} degenerate tri" if degen else "   <-- inspect"
        else:
            flag = f"   repaired: dropped {repaired} degenerate tri" if repaired else ""
        print(f"{p.name:<34} {len(tris):>6} {seal:>6} {vol:>8.2f} {grams:>5.0f}  {bb}{flag}")
        if bad:
            failures += 1

    print()
    if failures:
        print(f"{failures} file(s) not watertight."
              + ("" if repair else "  Re-run with --repair to drop degenerate triangles."))
        return 1
    print("All print-ready STLs are watertight.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
