from __future__ import annotations

from mmcad.gui import _default_outdir, _job_line


def test_default_outdir_uses_spec_parent_build_folder() -> None:
    result = _default_outdir("examples/bracket_demo.yaml")
    normalized = result.replace("\\", "/")
    assert normalized.endswith("examples/build")


def test_job_line_formats_expected_columns() -> None:
    line = _job_line(
        {
            "job_id": "job-123",
            "status": "succeeded",
            "spec_path": "examples/bracket_demo.yaml",
        }
    )
    assert "job-123" in line
    assert "succeeded" in line

