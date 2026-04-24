from __future__ import annotations

from pathlib import Path

import pytest

from mmcad.cli import SpecError, build


def test_build_rejects_missing_parts(tmp_path: Path) -> None:
    spec = tmp_path / "bad.yaml"
    spec.write_text("project: bad\n", encoding="utf-8")

    with pytest.raises(SpecError, match="non-empty 'parts' list"):
        build(str(spec), str(tmp_path / "out"))


def test_build_rejects_invalid_assembly_reference(tmp_path: Path) -> None:
    spec = tmp_path / "bad_assembly.yaml"
    spec.write_text(
        """
project: bad_assembly
parts:
  - type: shaft
    name: pin
    diameter: 8
    length: 20
assemblies:
  - name: assy
    items:
      - part: missing_part
        transform: [0, 0, 0, 0, 0, 0]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(SpecError, match="unknown part"):
        build(str(spec), str(tmp_path / "out"))
