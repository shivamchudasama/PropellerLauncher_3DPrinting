"""Verify the built STLs: mesh sanity, no fused bodies, gear mesh sweep,
and interface fits. Exit code 1 on any failure.

    python check.py
"""
import itertools
import math
import sys

import manifold3d as m3
import numpy as np
import shapely
import trimesh
from shapely.geometry import MultiPolygon, Polygon
from shapely import affinity

from build import (CENTRE, KOC, LUK, OUT, RING_TEETH, STAGES, TEETH,
                   stage_file, to_manifold)

FAILS = []


def report(ok, msg):
    print(("  ok   " if ok else "  FAIL ") + msg)
    if not ok:
        FAILS.append(msg)


def load_bodies(name):
    tm = trimesh.load(OUT / f"{name}.stl", force="mesh")
    return tm, tm.split(only_watertight=False)


def classify(bodies):
    """-> dict(ring, carrier?, sun, planets[3]) by position and size."""
    out = dict(planets=[], carrier=None)
    ring = max(bodies, key=lambda b: b.extents[0])
    out["ring"] = ring
    for b in bodies:
        if b is ring:
            continue
        c = b.bounds.mean(0)[:2]
        r = np.hypot(*c)
        if b.extents[0] < 21 and r < 0.3:
            out["sun"] = b
        elif b.extents[0] < 21 and abs(r - CENTRE) < 0.5:
            out["planets"].append(b)
        else:
            out["carrier"] = b
    assert "sun" in out and len(out["planets"]) == 3, "cannot classify bodies"
    return out


def slice_poly(man, z):
    polys = man.slice(z).to_polygons()
    shapes = [Polygon(p) for p in polys if len(p) >= 3]
    return shapely.make_valid(shapely.unary_union(
        [s for s in shapes if s.exterior.is_ccw]).difference(
        shapely.unary_union([Polygon(s.exterior.coords[::-1])
                             for s in shapes if not s.exterior.is_ccw])))


def rotz(man, deg, about=(0.0, 0.0)):
    x, y = about
    return man.translate((-x, -y, 0)).rotate((0, 0, deg)).translate((x, y, 0))


def check_assembly(name, clearance, expect_bodies):
    tm, bodies = load_bodies(name)
    print(f"\n{name}")
    report(all(b.is_watertight for b in bodies), "all bodies watertight")
    report(len(bodies) == expect_bodies,
           f"{len(bodies)} bodies (expected {expect_bodies})")
    parts = classify(bodies)
    man = {k: to_manifold(v) for k, v in
           (("ring", parts["ring"]), ("sun", parts["sun"]))}
    if parts["carrier"] is not None:
        man["carrier"] = to_manifold(parts["carrier"])
    pcs = []
    for i, p in enumerate(parts["planets"]):
        man[f"planet{i}"] = to_manifold(p)
        c = p.bounds.mean(0)[:2]
        pcs.append(CENTRE * c / np.hypot(*c))

    # static: no overlaps, smallest gap between any pair of bodies
    worst = (9.0, "")
    for a, b in itertools.combinations(man, 2):
        v = (man[a] ^ man[b]).volume()
        if v > 1e-6:
            report(False, f"{a} overlaps {b} ({v:.4f} mm3)")
        g = man[a].min_gap(man[b], 2.0)
        worst = min(worst, (g, f"{a}/{b}"))
    report(worst[0] >= 0.9 * min(clearance, 0.2) * math.cos(math.radians(35)),
           f"no overlaps; smallest 3D gap {worst[0]:.3f} mm ({worst[1]})")

    # kinematic sweep, carrier fixed: sun +a, planets -a, ring -a*Zs/Zr
    min3d, min2d = 9.0, 9.0
    zs = [1.5, 3.5, 6.0, 8.5, 10.5]
    for a in np.linspace(0, 360 / TEETH, 13):
        sun = rotz(man["sun"], a)
        ring = rotz(man["ring"], -a * TEETH / RING_TEETH)
        ring_s = {z: slice_poly(ring, z) for z in zs}
        sun_s = {z: slice_poly(sun, z) for z in zs}
        for i, pc in enumerate(pcs):
            pl = rotz(man[f"planet{i}"], -a, tuple(pc))
            for other in (sun, ring):
                v = (pl ^ other).volume()
                if v > 1e-6:
                    report(False, f"planet{i} collides at sun angle {a:.1f}")
                min3d = min(min3d, pl.min_gap(other, 2.0))
            for z in zs:
                ps = slice_poly(pl, z)
                min2d = min(min2d, ps.distance(sun_s[z]), ps.distance(ring_s[z]))
    report(min2d >= 0.9 * clearance,
           f"mesh sweep: min per-layer (XY) gap {min2d:.3f} mm "
           f"(target {clearance}), min 3D gap {min3d:.3f} mm")
    return man


def best_fit(inner, outer, sym):
    """Max over rotations of the min gap of `inner` inside hole `outer`."""
    best = -9.0
    for a in np.linspace(0, 360 / sym, 91):
        r = affinity.rotate(inner, a, origin=(0, 0))
        if outer.contains(r):
            best = max(best, outer.exterior.distance(r) if outer.area else 0)
    return best


def hole_at(tm, z, centre):
    sec = tm.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    polys, _ = sec.to_2D(to_2D=np.eye(4))
    holes = [Polygon(np.asarray(r.coords) - centre)
             for p in polys.polygons_full for r in p.interiors]
    return min(holes, key=lambda h: np.hypot(*h.centroid.coords[0]))


def outline_at(tm, z, centre):
    sec = tm.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    polys, _ = sec.to_2D(to_2D=np.eye(4))
    p = max(polys.polygons_full, key=lambda q: q.area)
    return Polygon(np.asarray(p.exterior.coords) - centre)


def check_interfaces():
    print("\nInterfaces")
    stage1 = trimesh.load(stage_file("Stage1_PropEnd_PIP"), force="mesh")
    sun = classify(stage1.split(only_watertight=False))["sun"]
    adapter = trimesh.load(OUT / "Propeller_Adapter.stl", force="mesh")
    report(adapter.is_watertight and len(adapter.split()) == 1,
           "adapter watertight, single body")
    # both hexes taper (Kocyns wedge fit): compare at matching depths for the
    # 7.4 mm insertion found by assemble.py
    insert = 7.4
    for za in (1.5, 3.5, 5.5):
        bore = hole_at(sun, insert - za, np.zeros(2))
        hexs = outline_at(adapter, za, np.zeros(2))
        g = best_fit(hexs, Polygon(bore.exterior), 6)
        report(g >= 0, f"adapter hex fits Stage1 sun bore at depth "
                       f"{insert - za:.1f} mm, gap {g:.3f} mm")
    bore = hole_at(sun, 6.0, np.zeros(2))

    prop = trimesh.load(LUK / "100mm Propeller.stl", force="mesh")
    hub_c = np.array([50.0, 49.14])
    hub = hole_at(prop, 5.0, hub_c)
    hub = affinity.translate(hub, *(-np.array(hub.centroid.coords[0])))
    spline = outline_at(adapter, 18.0, np.zeros(2))
    g = best_fit(spline, Polygon(hub.exterior), 9)
    report(g >= 0, f"adapter spline fits 100mm propeller hub, gap {g:.3f} mm")

    handle = trimesh.load(OUT / "Handle_B3D.stl", force="mesh")
    face, _ = handle.section(plane_origin=[0, 0, 0.3],
                             plane_normal=[0, 0, 1]).to_2D(to_2D=np.eye(4))
    disc = max(face.polygons_full, key=lambda p: p.area)
    engraved = Polygon(disc.exterior).area - face.area
    report(handle.is_watertight and len(handle.split()) == 1 and engraved > 100,
           f"handle watertight, single body, logo engraved ({engraved:.0f} mm2)")

    old_sun = sorted(trimesh.load(KOC / STAGES["Stage1_PropEnd_PIP"],
                                  force="mesh").split(), key=lambda b: -b.volume)[2]
    old_bore = hole_at(old_sun, 6.0, old_sun.bounds.mean(0)[:2])
    report(abs(old_bore.area - bore.area) < 0.5,
           f"sun hex bore preserved ({bore.area:.2f} vs {old_bore.area:.2f} mm2)")


def main():
    for path in sorted(OUT.glob("Stage*_PIP_*.stl")):  # every clearance set
        check_assembly(path.stem, float(path.stem.rsplit("_", 1)[1]), 6)
    for c in (0.15, 0.20, 0.25):
        check_assembly(f"Coupon_Clearance_{c:.2f}", c, 5)
    check_interfaces()
    print(f"\n{len(FAILS)} failure(s)")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
