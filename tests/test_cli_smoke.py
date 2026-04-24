from __future__ import annotations

from pathlib import Path

from mmcad.cli import build


def test_build_bracket_demo_writes_outputs(tmp_path: Path) -> None:
    project_dir = Path(build("examples/bracket_demo.yaml", str(tmp_path)))
    assert (project_dir / "base.step").exists()
    assert (project_dir / "base.stl").exists()
    assert (project_dir / "pin.step").exists()
    assert (project_dir / "pin.stl").exists()
    assert (project_dir / "assembly.csv").exists()
