"""Build the hybrid launcher STLs from the pristine originals.

Kocyns print-in-place stages keep their housing, carrier, bores and 45-degree
retention cones; only the 15T straight-spur teeth are replaced with 18T
herringbone teeth (Lukas Hannert style). The propeller adapter joins the
Kocyns hex shank/collar to the Lukas splined, coned nose. The handle gets a
closed bottom face with the B3D Labs logo engraved into it.

    python build.py                    # stages at CLEARANCE, adapter, coupons
    python build.py --clearance 0.25   # rebuild stages with another clearance
"""
import argparse
import math
import re
import shutil
from pathlib import Path

import manifold3d as m3
import numpy as np
import trimesh
from shapely import affinity
from shapely.geometry import Point, Polygon

from herringbone import (cylinder, gear_outline, herringbone, revolve,
                         to_cross_section, twist_for)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Custom_HybridLauncher"
KOC = ROOT / "Original_Kocyns"
LUK = ROOT / "Original_LukasHannert"
LOGO = ROOT / "B3D_Labs.svg"

# --- gear parameters -------------------------------------------------------
TEETH = 18                 # sun and planets
RING_TEETH = 54
CENTRE = 17.96             # Kocyns carrier pin radius (measured)
MODULE = 2 * CENTRE / (2 * TEETH)
HA, HF = 0.85, 1.05        # short addendum for print-in-place
HELIX = 35.0               # Lukas helix angle, degrees
CLEARANCE = 0.15           # gap between mating flanks, mm
FACE = 12.0                # gear face width = Kocyns stage gear height
N_DIV = 14                 # extrusion slices per herringbone half

# --- Kocyns retention geometry (45-degree cones) ----------------------------
ENV_R0 = 7.0               # planet barrel radius at both faces
CONE_GAP = 0.5             # radial gap between facing 45-degree cones
SUN_FLANGE_R = 9.85        # Kocyns sun end-flange radius
RING_CUT_R = 28.1          # just outside the Kocyns ring root (28.07)
BORE_KEEP_R = 6.95         # inside this radius the original bores are kept

STAGES = {
    "Stage1_PropEnd_PIP": "obj_6_toro_monoV3_rovne_test5_ruco_vrch_rucoV5.stl",
    "Stage2_Middle_PIP": "obj_5_ruco_V5_mezikus.stl",
    "Stage3_HandleEnd_PIP": "obj_7_ruco_V5.stl",
}


# --- mesh conversion ---------------------------------------------------------
def to_manifold(tm):
    mesh = m3.Mesh(vert_properties=np.asarray(tm.vertices, np.float32),
                   tri_verts=np.asarray(tm.faces, np.uint32))
    man = m3.Manifold(mesh)
    if man.status() != m3.Error.NoError:
        raise RuntimeError(f"not a manifold: {man.status()}")
    return man


def to_trimesh(man):
    mesh = man.to_mesh()
    tm = trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3],
                         np.asarray(mesh.tri_verts), process=True)
    # manifold keeps zero-area triangles on coplanar seams; once vertices are
    # merged they float free as empty "bodies", so drop them
    tm.update_faces(tm.nondegenerate_faces(height=1e-9))
    tm.remove_unreferenced_vertices()
    return tm


def section_centroids(tm, z, holes=False):
    sec = tm.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    polys, _ = sec.to_2D(to_2D=np.eye(4))
    polys = polys.polygons_full
    if holes:
        from shapely.geometry import Polygon
        return [np.array(Polygon(r).centroid.coords[0])
                for p in polys for r in p.interiors]
    return [np.array(p.centroid.coords[0]) for p in polys]


def box_above(z0, z1=1e3, r=1e3):
    return m3.Manifold.cube((2 * r, 2 * r, z1 - z0)).translate((-r, -r, z0))


# --- shared geometry -----------------------------------------------------------
def gear_set(clearance):
    """Herringbone sun, planet (about own axis) and ring band, plus retention."""
    rp_s = MODULE * TEETH / 2
    rp_r = MODULE * RING_TEETH / 2
    tw_s = twist_for(rp_s, FACE, HELIX)
    tw_r = twist_for(rp_r, FACE, HELIX)
    c2 = clearance / 2

    sun2d = gear_outline(TEETH, MODULE, HA, HF).buffer(-c2)
    # even tooth count: planet shows a gap towards the sun -> half-tooth phase
    planet2d = gear_outline(TEETH, MODULE, HA, HF,
                            phase_deg=180 / TEETH).buffer(-c2)
    # ring tooth spaces = external 54T outline with swapped addendum/dedendum,
    # phased so a ring tooth faces each planet's outward gap
    hole2d = gear_outline(RING_TEETH, MODULE, HF, HA,
                          phase_deg=180 / RING_TEETH).buffer(c2)
    ring2d = Point(0, 0).buffer(RING_CUT_R + 0.06, quad_segs=128).difference(hole2d)

    # helical hands: sun +, planet - (external mesh), ring - (internal mesh)
    sun = herringbone(sun2d, FACE, tw_s, N_DIV)
    planet = herringbone(planet2d, FACE, -tw_s, N_DIV)
    ring = herringbone(ring2d, FACE, -tw_r, N_DIV)

    F, r0 = FACE, ENV_R0
    big = 12.0
    planet_env = revolve([(0, 0), (r0, 0), (big, big - r0),
                          (big, F - (big - r0)), (r0, F), (0, F)])
    a = CENTRE - r0 - CONE_GAP          # sun flange cone: r = a - z
    rf = SUN_FLANGE_R
    r_in = 6.5
    sun_fill = revolve([(0, 0), (rf, 0), (rf, a - rf), (r_in, a - r_in),
                        (r_in, F - (a - r_in)), (rf, F - (a - rf)), (rf, F),
                        (0, F)])
    b = CENTRE + r0 + CONE_GAP          # ring lip cones: r = b + z, b + F - z
    # outer edge sits inside the solid band (hole tips < ro < ring2d outer):
    # coincident cylinders here leave zero-area slivers in the union
    ro = RING_CUT_R + 0.03
    ring_fill = (revolve([(b, 0), (ro, 0), (ro, ro - b)]) +
                 revolve([(b, F), (ro, F - (ro - b)), (ro, F)]))
    return dict(sun=sun + sun_fill,
                planet=planet ^ planet_env,
                ring=ring + ring_fill)


def planet_positions():
    return [np.array([CENTRE * math.cos(math.radians(a)),
                      CENTRE * math.sin(math.radians(a)), 0.0])
            for a in (0, 120, 240)]


# --- stages ---------------------------------------------------------------------
def build_stage(src, gears):
    tm = trimesh.load(src, force="mesh")
    bodies = sorted(tm.split(only_watertight=False), key=lambda b: -b.volume)
    ring, carrier, sun, planets = bodies[0], bodies[1], bodies[2], bodies[3:]
    assert len(planets) == 3

    pins = section_centroids(carrier, 6.0)
    assert len(pins) == 3, "expected three carrier pins"
    axis = np.mean(pins, axis=0)
    radii = [np.linalg.norm(p - axis) for p in pins]
    assert max(abs(r - CENTRE) for r in radii) < 0.02, radii
    sun_bore = section_centroids(sun, 6.0, holes=True)[0]
    assert np.linalg.norm(sun_bore - axis) < 0.05, "sun bore off-axis"

    shift = np.array([-axis[0], -axis[1], 0.0])
    for b in bodies:
        b.apply_translation(shift)
    old = {k: to_manifold(v) for k, v in
           dict(ring=ring, carrier=carrier, sun=sun).items()}

    keep = cylinder(BORE_KEEP_R, -1, FACE + 1)
    # sun: herringbone + flanges, minus the original hex bore and its chamfer
    sun_void = (keep + cylinder(8.3, -1, 0.3)) - old["sun"]
    new_sun = gears["sun"] - sun_void

    new_planets = []
    for pc in planet_positions():
        old_p = min(planets, key=lambda p: np.linalg.norm(
            (p.bounds.mean(0) - pc)[:2]))
        bore = section_centroids(old_p, 6.0, holes=True)[0]
        assert np.linalg.norm(bore - pc[:2]) < 0.05, "planet bore off its pin"
        void = keep.translate(tuple(pc)) - to_manifold(old_p)
        new_planets.append(gears["planet"].translate(tuple(pc)) - void)

    new_ring = (old["ring"] - cylinder(RING_CUT_R, -1, FACE)) + gears["ring"]
    return [new_ring, old["carrier"], new_sun, *new_planets]


# --- propeller adapter -------------------------------------------------------------
def build_adapter():
    """Hex-down / nose-up: Kocyns hex + cone + collar, Lukas spline + nose."""
    k = trimesh.load(KOC / "obj_8_cep.stl", force="mesh")
    hex_c = section_centroids(k, 18.0)[0]
    k.apply_translation([-hex_c[0], -hex_c[1], 0])
    # collar starts at z 11 (tri-lobe below is dropped); flip so hex tip is z 0
    base = (to_manifold(k) ^ box_above(11.0)).rotate((180, 0, 0)).translate((0, 0, 22.0))

    lk = trimesh.load(LUK / "Adapter.stl", force="mesh")
    lk.apply_translation([-7.0, -7.0, 0])
    nose = (to_manifold(lk) ^ box_above(-1, 15.5)) + cylinder(5.3, 2.6, 15.5)
    # flip so the cone nose points up; bottom (z_L 15.5) sinks 0.05 into collar
    nose = nose.rotate((180, 0, 0)).translate((0, 0, 15.5 + 10.95))
    return base + nose


# --- handle with engraved logo --------------------------------------------------
LOGO_HEIGHT = 34.0         # mm, fits inside the 59 mm bottom face
LOGO_DEPTH = 0.6           # 3 layers at 0.2 mm



def logo_outline(height):
    """B3D Labs SVG (absolute M/L/Z path, even-odd) -> shapely, centred.

    Laid out to read correctly when the face is viewed from below (-Z).
    """
    d = re.search(r'\sd="([^"]+)"', LOGO.read_text()).group(1)
    rings = []
    for sub in d.split("Z"):
        nums = [float(v) for v in re.findall(r"-?\d+\.?\d*", sub)]
        if len(nums) >= 6:
            rings.append(Polygon(np.reshape(nums, (-1, 2))).buffer(0))
    shape = rings[0]
    for r in rings[1:]:
        shape = shape.symmetric_difference(r)  # even-odd fill rule
    x0, y0, x1, y1 = shape.bounds
    shape = affinity.translate(shape, -(x0 + x1) / 2, -(y0 + y1) / 2)
    k = height / (y1 - y0)
    # SVG y points down; viewed from -Z the model x axis appears mirrored
    return affinity.scale(shape, -k, -k, origin=(0, 0))


def build_handle():
    tm = trimesh.load(KOC / "obj_1_ruco_rukojet_V5.stl", force="mesh")
    tm.apply_translation(-np.r_[tm.bounds.mean(0)[:2], 0])
    # fill the blind bottom recess (r 18.0 at z 0 tapering to closed at z 16)
    # so the bottom is one flat face; the profile stays >= 0.5 mm inside the
    # surrounding hub wall and never reaches the cup cavity
    fill = revolve([(0, 0), (18.5, 0), (18.5, 5.5), (14.5, 8.0), (14.2, 12.0),
                    (13.0, 14.0), (11.6, 15.2), (11.2, 16.3), (0, 16.3)])
    logo = m3.Manifold.extrude(to_cross_section(logo_outline(LOGO_HEIGHT)),
                               LOGO_DEPTH + 1).translate((0, 0, -1))
    return (to_manifold(tm) + fill) - logo


# --- clearance coupon ------------------------------------------------------------
def build_coupon(clearance, notches):
    g = gear_set(clearance)
    shell = cylinder(30.5, 0, FACE) - cylinder(RING_CUT_R, -1, FACE + 1)
    for i in range(notches):
        a = 15.0 * i
        cut = (m3.Manifold.cube((1.2, 1.2, FACE + 2), center=True)
               .rotate((0, 0, 45)).translate((30.5, 0, FACE / 2))
               .rotate((0, 0, a)))
        shell = shell - cut
    ring = g["ring"] + shell
    hex_r = 6.5 / math.sqrt(3)  # 6.5 mm across flats: fits a 1/4" hex bit
    hex_hole = m3.Manifold.cylinder(FACE + 2, hex_r, hex_r, 6).translate((0, 0, -1))
    sun = g["sun"] - hex_hole
    planets = [g["planet"].translate(tuple(p)) for p in planet_positions()]
    return [ring, sun, *planets]


def export(parts, name):
    mesh = trimesh.util.concatenate([to_trimesh(p) for p in parts])
    path = OUT / f"{name}.stl"
    mesh.export(path)
    print(f"  {path.name:34s} {len(mesh.faces):8d} faces  "
          f"ext={np.round(mesh.extents, 2)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clearance", type=float, default=CLEARANCE)
    ap.add_argument("--stages-only", action="store_true")
    args = ap.parse_args()

    print(f"module {MODULE:.4f}, clearance {args.clearance}")
    gears = gear_set(args.clearance)
    for name, src in STAGES.items():
        export(build_stage(KOC / src, gears), name)
    if args.stages_only:
        return
    export([build_adapter()], "Propeller_Adapter")
    for n, c in enumerate((0.15, 0.20, 0.25), start=1):
        export(build_coupon(c, n), f"Coupon_Clearance_{c:.2f}")
    export([build_handle()], "Handle_B3D")
    src = LUK / "100mm Propeller.stl"
    shutil.copyfile(src, OUT / "Propeller_100mm.stl")
    print(f"  {'Propeller_100mm.stl':34s} (unchanged copy of {src.name})")


if __name__ == "__main__":
    main()
