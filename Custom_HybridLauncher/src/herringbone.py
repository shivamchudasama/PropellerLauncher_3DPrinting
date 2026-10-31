"""Herringbone gear geometry for print-in-place planetary stages.

2D tooth outlines are generated with shapely by sweeping a straight-flanked
rack cutter past the blank (true generated involute + trochoid root), then
extruded into herringbone solids with manifold3d.

Units: mm, degrees at the API boundary.
"""
import math

import numpy as np
import manifold3d as m3
import shapely
from shapely import affinity
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

PRESSURE_ANGLE = 20.0


def _rack_tooth(rp, m, ha, hf, pa_deg):
    """Cutter tooth centred on x=0, pitch line at y=rp, tip pointing to -y."""
    t = math.tan(math.radians(pa_deg))
    y_tip = rp - hf * m          # cutter tip forms the gear root
    y_top = rp + ha * m + 2 * m  # well beyond the gear tip
    w = lambda y: math.pi * m / 4 - (rp - y) * t
    return Polygon([(-w(y_tip), y_tip), (w(y_tip), y_tip),
                    (w(y_top), y_top), (-w(y_top), y_top)])


def gear_outline(z, m, ha, hf, pa_deg=PRESSURE_ANGLE, phase_deg=0.0,
                 steps=161, tol=0.004):
    """Solid outline of an external gear, teeth centred at phase + k*360/z.

    ha/hf are addendum/dedendum in multiples of the module.
    """
    rp = m * z / 2
    ra = rp + ha * m
    cutter = _rack_tooth(rp, m, ha, hf, pa_deg)
    reach = (ha + hf + 3) * m
    cuts = []
    for s in np.linspace(-reach, reach, steps):
        phi = s / rp  # rack shift s <-> gear rotation phi (rolling on pitch)
        c = affinity.translate(cutter, xoff=s)
        cuts.append(affinity.rotate(c, phi, origin=(0, 0), use_radians=True))
    space = unary_union(cuts)            # one tooth space, centred at 90 deg
    pitch = 360.0 / z
    # 90 deg is a space centre when teeth sit at 0 + k*pitch only if 90/pitch
    # is a half-integer; rotate so the space lands at pitch/2 explicitly.
    space = affinity.rotate(space, pitch / 2 - 90.0, origin=(0, 0))
    spaces = unary_union([affinity.rotate(space, k * pitch, origin=(0, 0))
                          for k in range(z)])
    blank = Point(0, 0).buffer(ra, quad_segs=max(64, 4 * z))
    g = blank.difference(spaces)
    g = affinity.rotate(g, phase_deg, origin=(0, 0))
    return shapely.simplify(g, tol)


def _contours(geom):
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    out = []
    for p in polys:
        p = shapely.geometry.polygon.orient(p, 1.0)  # exterior CCW, holes CW
        out.append(np.asarray(p.exterior.coords)[:-1])
        out.extend(np.asarray(r.coords)[:-1] for r in p.interiors)
    return out


def to_cross_section(geom):
    return m3.CrossSection(_contours(geom), m3.FillRule.Positive)


def herringbone(geom, height, twist_half_deg, n_div=14):
    """Extrude geom to `height`, twisting +twist_half_deg up to mid-height and
    back to 0 at the top (apex at height/2)."""
    cs = to_cross_section(geom)
    h2 = height / 2
    lower = m3.Manifold.extrude(cs, h2, n_div, twist_half_deg)
    upper = m3.Manifold.extrude(cs.rotate(twist_half_deg), h2, n_div,
                                -twist_half_deg).translate((0, 0, h2))
    return lower + upper


def twist_for(rp, height, helix_deg):
    """Half-height twist (deg) giving helix angle `helix_deg` at radius rp."""
    arc = (height / 2) * math.tan(math.radians(helix_deg))
    return math.degrees(arc / rp)


def revolve(rz_points, segments=256):
    """Solid of revolution about Z from a closed (r, z) polygon (r >= 0)."""
    cs = m3.CrossSection([np.asarray(rz_points, float)], m3.FillRule.Positive)
    return m3.Manifold.revolve(cs, segments)


def cylinder(r, z0, z1, segments=256):
    return m3.Manifold.cylinder(z1 - z0, r, r, segments).translate((0, 0, z0))
