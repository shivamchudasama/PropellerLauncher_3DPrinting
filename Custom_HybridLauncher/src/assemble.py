"""Stack the built STLs into the in-use assembly and write Assembly.glb.

Parts are seated by collision search (lower each part until it touches the
one below) rather than hard-coded offsets. Built in print orientation
(Stage1 at the bottom), then turned over: handle down, propeller up.
Housings are semi-transparent so the gear train shows.

The GLB carries a looping animation: the housings stay still while the
handle makes one turn, and every gear, carrier and the propeller follow the
planetary kinematics (ring fixed: sun = 4 x carrier, planet spin relative to
its carrier = -3 x carrier).

    python assemble.py
"""
import json
import struct

import numpy as np
import manifold3d as m3
import trimesh
from shapely import affinity

from build import OUT, stage_file, to_manifold
from check import best_fit, classify, hole_at, outline_at

TOUCH = 1e-3  # mm3 of overlap that counts as contact
LOOP_S = 20.0  # one handle turn
FPS = 30
# Turning sense about +Z (handle -> propeller). The handle's chevron grip ribs
# point clockwise seen from the propeller end, i.e. counter-clockwise seen from
# the handle's logo face; the handle turns the way they point.
DIRECTION = -1

# turns per handle turn: (carrier, sun) of each stage; handle drives Stage3
STAGE_SPEED = {"Stage1_PropEnd_PIP": (16, 64),
               "Stage2_Middle_PIP": (4, 16),
               "Stage3_HandleEnd_PIP": (1, 4)}

COLOURS = {  # RGBA 0-255
    "housing": (150, 170, 190, 90),
    "carrier": (235, 140, 40, 255),
    "sun": (210, 50, 50, 255),
    "planet": (245, 200, 40, 255),
    "handle": (60, 60, 70, 255),
    "adapter": (60, 170, 90, 255),
    "propeller": (40, 110, 220, 255),
}


def seat(moving, fixed, z_hi, z_lo, down=True):
    """Largest travel along -Z (down=True) or +Z before `moving` touches."""
    def hits(dz):
        m = moving.translate((0, 0, -dz if down else dz))
        return any((m ^ f).volume() > TOUCH for f in fixed)
    lo, hi = z_lo, z_hi            # lo: no contact, hi: contact
    assert not hits(lo) and hits(hi), "seating search range is wrong"
    while hi - lo > 0.01:
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if not hits(mid) else (lo, mid)
    return lo


def stage_parts(name):
    """-> [(kind, speed, manifold)]; a planet's speed is its carrier's."""
    tm = trimesh.load(stage_file(name), force="mesh")
    p = classify(tm.split(only_watertight=False))
    c, s = STAGE_SPEED[name]
    return [("housing", 0, to_manifold(p["ring"])),
            ("carrier", c, to_manifold(p["carrier"])),
            ("sun", s, to_manifold(p["sun"])),
            *[("planet", c, to_manifold(b)) for b in p["planets"]]]


def main():
    flip = (180, 0, 0)  # proper rotation, keeps handedness
    placed = []          # (kind, speed, manifold) in print-orientation frame

    s1 = stage_parts("Stage1_PropEnd_PIP")
    placed += s1
    below = s1
    for name in ("Stage2_Middle_PIP", "Stage3_HandleEnd_PIP"):
        parts = stage_parts(name)
        top = max(m.bounding_box()[5] for *_, m in below)
        ring = parts[0][2].translate((0, 0, top))
        dz = seat(ring, [below[0][2]], top, 0.0)
        z = top - dz
        parts = [(k, v, m.translate((0, 0, z))) for k, v, m in parts]
        print(f"  {name} seated at z={z:.2f}")
        placed += parts
        below = parts

    # handle: cup down over Stage3; its rim lands on the Stage3 ring shoulder
    s3_ring = below[0][2]
    s3_z0 = s3_ring.bounding_box()[2]
    shoulder = s3_ring ^ m3.Manifold.cube((80, 80, 12.5)).translate((-40, -40, s3_z0))
    handle = to_manifold(trimesh.load(OUT / "Handle_B3D.stl")).rotate(flip)
    hb = handle.bounding_box()
    top = s3_ring.bounding_box()[5]
    handle = handle.translate((0, 0, top + 1 - hb[2]))
    dz = seat(handle, [shoulder], top - s3_z0, 0.0)
    placed.append(("handle", 1, handle.translate((0, 0, -dz))))
    print(f"  handle seated, travel {dz:.2f}")

    # adapter: hex up into the Stage1 sun bore from below; turn hex to fit
    sun1 = next(m for k, _, m in s1 if k == "sun")
    sun_tm = trimesh.load(stage_file("Stage1_PropEnd_PIP"), force="mesh")
    sun_tm = classify(sun_tm.split(only_watertight=False))["sun"]
    bore = hole_at(sun_tm, 6.0, np.zeros(2))
    ad_tm = trimesh.load(OUT / "Propeller_Adapter.stl")
    hexs = outline_at(ad_tm, 4.0, np.zeros(2))
    ang = max(np.linspace(0, 60, 121), key=lambda a: (
        bore.contains(affinity.rotate(hexs, a, origin=(0, 0))),
        bore.exterior.distance(affinity.rotate(hexs, a, origin=(0, 0)))))
    adapter = to_manifold(ad_tm).rotate((0, 0, ang)).rotate(flip)
    ab = adapter.bounding_box()
    adapter = adapter.translate((0, 0, -ab[5] - 1))        # just below Stage1
    rise = seat(adapter, [sun1, s1[0][2]], 20.0, 0.0, down=False)
    adapter = adapter.translate((0, 0, rise))
    placed.append(("adapter", 64, adapter))
    print(f"  adapter hex turned {ang:.1f} deg, inserted {rise - 1:.2f} mm")

    # propeller: on the collar seat, hub turned to fit the spline
    prop_tm = trimesh.load(OUT / "Propeller_100mm.stl", force="mesh")
    hub_c = prop_tm.bounds.mean(0)[:2]
    hub = hole_at(prop_tm, 5.0, hub_c)
    off = np.array(hub.centroid.coords[0])
    hub = affinity.translate(hub, *(-off))
    spline = outline_at(ad_tm, 18.0, np.zeros(2))
    spline = affinity.rotate(spline, ang, origin=(0, 0))
    pa = max(np.linspace(0, 40, 161), key=lambda a: (
        hub.contains(affinity.rotate(spline, a, origin=(0, 0))),
        hub.exterior.distance(affinity.rotate(spline, a, origin=(0, 0)))))
    prop = to_manifold(prop_tm).translate((-(hub_c[0] + off[0]),
                                           -(hub_c[1] + off[1]), 0))
    prop = prop.rotate((0, 0, -pa)).rotate(flip)
    seat_z = adapter.bounding_box()[5] - 11.0  # collar face: 11 mm from hex tip
    prop = prop.translate((0, 0, seat_z - 0.05 - prop.bounding_box()[5]))
    placed.append(("propeller", 64, prop))

    parts = []
    for kind, speed, man in placed:
        mesh = man.rotate(flip).scale((1e-3, 1e-3, 1e-3)).to_mesh()  # metres
        parts.append((kind, speed, np.asarray(mesh.vert_properties)[:, :3],
                      np.asarray(mesh.tri_verts)))
    path = OUT / "Assembly.glb"
    write_glb(path, parts)
    faces = sum(len(f) for *_, f in parts)
    height = (max(v[:, 2].max() for _, _, v, _ in parts) -
              min(v[:, 2].min() for _, _, v, _ in parts)) * 1e3
    print(f"  {path.name}: {faces} faces, {path.stat().st_size / 1e6:.1f} MB, "
          f"height {height:.1f} mm, {LOOP_S:.0f} s loop")


def _z_quats(turns, t):
    """Quaternions (x, y, z, w) for `turns` revolutions about +Z over t/LOOP_S."""
    half = np.pi * DIRECTION * turns * t / LOOP_S
    q = np.zeros((len(t), 4), np.float32)
    q[:, 2], q[:, 3] = np.sin(half), np.cos(half)
    return q


def write_glb(path, parts):
    """Minimal glTF 2.0 binary: one mesh per part, flat shaded (no normals),
    rotation keyframes about the shared Z axis. Planets hang under a pivot
    node that turns with their carrier and spin about their own axis."""
    blob, views, accessors = bytearray(), [], []

    def add(arr, target=None, **acc):
        while len(blob) % 4:
            blob.append(0)
        views.append(dict(buffer=0, byteOffset=len(blob), byteLength=arr.nbytes,
                          **({"target": target} if target else {})))
        blob.extend(arr.tobytes())
        accessors.append(dict(bufferView=len(views) - 1, count=len(arr), **acc))
        return len(accessors) - 1

    materials, mat_index = [], {}
    for kind, rgba in COLOURS.items():
        a = rgba[3] < 255
        mat_index[kind] = len(materials)
        materials.append(dict(
            name=kind, doubleSided=a, alphaMode="BLEND" if a else "OPAQUE",
            pbrMetallicRoughness=dict(
                baseColorFactor=[c / 255 for c in rgba],
                metallicFactor=0.1, roughnessFactor=0.6)))

    t = np.linspace(0, LOOP_S, int(LOOP_S * FPS) + 1).astype(np.float32)
    t_acc = add(t, componentType=5126, type="SCALAR",
                min=[float(t[0])], max=[float(t[-1])])
    meshes, nodes, roots, samplers, channels = [], [], [], [], []

    def animate(node, turns):
        samplers.append(dict(input=t_acc, interpolation="LINEAR",
                             output=add(_z_quats(turns, t), componentType=5126,
                                        type="VEC4")))
        channels.append(dict(sampler=len(samplers) - 1,
                             target=dict(node=node, path="rotation")))

    for i, (kind, speed, v, f) in enumerate(parts):
        centre = np.zeros(3)
        if kind == "planet":   # spin about its own axis, inside a pivot node
            centre[:2] = (v[:, :2].min(0) + v[:, :2].max(0)) / 2
        v = (v - centre).astype(np.float32)
        pos = add(v, 34962, componentType=5126, type="VEC3",
                  min=v.min(0).tolist(), max=v.max(0).tolist())
        idx = add(f.astype(np.uint32).ravel(), 34963, componentType=5125,
                  type="SCALAR")
        meshes.append(dict(name=f"{kind}_{i:02d}", primitives=[dict(
            attributes=dict(POSITION=pos), indices=idx,
            material=mat_index[kind])]))
        nodes.append(dict(name=f"{kind}_{i:02d}", mesh=len(meshes) - 1))
        me = len(nodes) - 1
        if kind == "planet":
            nodes[me]["translation"] = centre.tolist()
            nodes.append(dict(name=f"pivot_{i:02d}", children=[me]))
            roots.append(len(nodes) - 1)
            animate(len(nodes) - 1, speed)      # orbit with the carrier
            animate(me, -3 * speed)             # spin relative to the carrier
        else:
            roots.append(me)
            if speed:
                animate(me, speed)

    gltf = dict(
        asset=dict(version="2.0", generator="PropellerLauncher assemble.py"),
        scene=0, scenes=[dict(nodes=roots)], nodes=nodes, meshes=meshes,
        materials=materials, accessors=accessors, bufferViews=views,
        buffers=[dict(byteLength=len(blob))],
        animations=[dict(name="turn_handle", samplers=samplers,
                         channels=channels)])
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    blob += bytes(-len(blob) % 4)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2,
                             12 + 8 + len(js) + 8 + len(blob)))
        fh.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        fh.write(struct.pack("<II", len(blob), 0x004E4942) + bytes(blob))


if __name__ == "__main__":
    main()
