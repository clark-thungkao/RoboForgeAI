"""Small CadQuery primitives used by the YAML-driven CLI."""

from __future__ import annotations

import cadquery as cq


def _hole_diameter(hole: dict) -> float:
    """Read hole diameter while supporting old `d` field."""
    if "diameter" in hole:
        return float(hole["diameter"])
    if "d" in hole:
        return float(hole["d"])
    raise KeyError("Hole entry must include 'diameter'.")


def plate(
    width: float,
    height: float,
    thickness: float,
    holes: list[dict] | None = None,
) -> cq.Workplane:
    """Create a centered rectangular plate with optional through-holes."""
    model = cq.Workplane("XY").box(float(width), float(height), float(thickness), centered=(True, True, False))
    if not holes:
        return model

    top = model.faces(">Z").workplane()
    for hole in holes:
        dia = _hole_diameter(hole)
        x = float(hole.get("x", 0.0))
        y = float(hole.get("y", 0.0))
        top = top.pushPoints([(x, y)]).hole(dia)
    return top


def shaft(diameter: float, length: float) -> cq.Workplane:
    """Create a straight cylindrical shaft."""
    radius = float(diameter) / 2.0
    return cq.Workplane("XY").circle(radius).extrude(float(length))


def link_rect(
    length: float,
    width: float,
    thickness: float,
    end_hole_d: float = 8.0,
) -> cq.Workplane:
    """Create a rectangular link with one hole near each end."""
    model = cq.Workplane("XY").box(float(length), float(width), float(thickness), centered=(True, True, False))
    hole_radius = float(end_hole_d) / 2.0
    half_span = float(length) / 2.0
    hole_x = max(half_span - float(width) / 2.0, 0.0)

    return (
        model.faces(">Z")
        .workplane()
        .pushPoints([(-hole_x, 0.0), (hole_x, 0.0)])
        .circle(hole_radius)
        .cutThruAll()
    )
