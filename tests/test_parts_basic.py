from __future__ import annotations

import pytest

cq = pytest.importorskip("cadquery")
mm_parts = pytest.importorskip("mmcad.parts.basic")


def test_plate_returns_workplane() -> None:
    model = mm_parts.plate(20, 10, 2, holes=[{"x": 0, "y": 0, "diameter": 2}])
    assert isinstance(model, cq.Workplane)


def test_shaft_returns_workplane() -> None:
    model = mm_parts.shaft(8, 40)
    assert isinstance(model, cq.Workplane)


def test_link_returns_workplane() -> None:
    model = mm_parts.link_rect(60, 20, 4, end_hole_d=6)
    assert isinstance(model, cq.Workplane)
