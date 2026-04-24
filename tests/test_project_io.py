from __future__ import annotations

from pathlib import Path

import pytest

from mmcad.project_io import (
    PROJECT_SCHEMA_VERSION,
    ProjectError,
    create_project_data,
    load_project,
    save_project,
)


def test_save_and_load_project_round_trip(tmp_path: Path) -> None:
    project_data = create_project_data(name="demo", spec_path="examples/bracket_demo.yaml", outdir="build")
    project_path = tmp_path / "demo.rfa.json"
    save_project(str(project_path), project_data)

    loaded = load_project(str(project_path))
    assert loaded["schema_version"] == PROJECT_SCHEMA_VERSION
    assert loaded["project"]["name"] == "demo"
    assert loaded["inputs"]["spec_path"] == "examples/bracket_demo.yaml"


def test_load_project_rejects_unsupported_schema(tmp_path: Path) -> None:
    project_path = tmp_path / "bad.rfa.json"
    project_path.write_text(
        """
{
  "schema_version": 999,
  "project": {"name": "bad"},
  "inputs": {"spec_path": "spec.yaml"},
  "generation_profile": {"outdir": "build"},
  "outputs": {},
  "metadata": {}
}
""".strip(),
        encoding="utf-8",
    )
    with pytest.raises(ProjectError, match="Unsupported schema_version"):
        load_project(str(project_path))


def test_load_project_rejects_missing_required_fields(tmp_path: Path) -> None:
    project_path = tmp_path / "bad.rfa.json"
    project_path.write_text('{"schema_version": 1}', encoding="utf-8")

    with pytest.raises(ProjectError, match="Missing required field"):
        load_project(str(project_path))
