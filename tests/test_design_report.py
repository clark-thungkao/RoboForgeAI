from __future__ import annotations

import json
from pathlib import Path

from mmcad.cli import build


def test_design_report_contains_expected_fields(tmp_path: Path) -> None:
    project_dir = Path(build("examples/bracket_demo.yaml", str(tmp_path)))
    report = json.loads((project_dir / "design_report.json").read_text(encoding="utf-8"))

    assert report["report_version"] == 1
    assert report["project"] == "bracket_demo"
    assert sorted(report["parts"]) == ["base", "pin"]
    assert isinstance(report["assumptions"], list)
    assert isinstance(report["warnings"], list)
    assert "assembly.csv" in report["outputs"]
    assert "design_report.json" in report["outputs"]
