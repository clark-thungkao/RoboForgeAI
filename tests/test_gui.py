from __future__ import annotations

from mmcad.gui import (
    _TEMPLATES,
    _action_enabled_states,
    _artifact_folder,
    _default_outdir,
    _default_project_path,
    _filter_jobs,
    _job_details_text,
    _job_line,
    _path_exists,
    _summary_text,
)


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


def test_job_details_text_includes_error_and_artifact_count() -> None:
    text = _job_details_text(
        {
            "job_id": "job-123",
            "status": "failed",
            "spec_path": "examples/bracket_demo.yaml",
            "outdir": "build",
            "created_at": "2026-01-01T00:00:00+00:00",
            "error": "bad input",
        },
        {"files": ["a.step", "a.stl"]},
    )
    assert "Job ID: job-123" in text
    assert "Error: bad input" in text
    assert "Artifacts: 2 file(s)" in text


def test_summary_text_formats_dashboard_counts() -> None:
    text = _summary_text(
        {"status": "ok", "active_jobs": 2},
        {
            "total": 7,
            "by_status": {
                "queued": 1,
                "running": 1,
                "succeeded": 4,
                "failed": 1,
                "cancelled": 1,
            },
        },
    )
    assert "Backend: ok" in text
    assert "Total: 7" in text
    assert "Active: 2" in text


def test_action_enabled_states_for_statuses() -> None:
    none_state = _action_enabled_states(None)
    assert none_state == {"retry": False, "cancel": False, "delete": False}
    running_state = _action_enabled_states("running")
    assert running_state["cancel"] is True
    assert running_state["retry"] is False
    finished_state = _action_enabled_states("failed")
    assert finished_state["retry"] is True
    assert finished_state["delete"] is True


def test_default_project_path_uses_rfa_json_suffix() -> None:
    project_path = _default_project_path("examples/bracket_demo.yaml")
    normalized = project_path.replace("\\", "/")
    assert normalized.endswith("examples/bracket_demo.rfa.json")


def test_templates_include_bracket_demo() -> None:
    assert "Bracket Demo" in _TEMPLATES
    assert _TEMPLATES["Bracket Demo"].endswith("bracket_demo.yaml")


def test_artifact_folder_returns_parent_directory() -> None:
    folder = _artifact_folder("build/bracket_demo/base.step")
    normalized = folder.replace("\\", "/")
    assert normalized.endswith("build/bracket_demo")


def test_path_exists_detects_existing_and_missing_paths() -> None:
    assert _path_exists("README.md") is True
    assert _path_exists("definitely_missing_file_123.txt") is False


def test_filter_jobs_applies_status_and_search_query() -> None:
    jobs = [
        {"job_id": "a1", "status": "succeeded", "spec_path": "examples/bracket_demo.yaml"},
        {"job_id": "b2", "status": "failed", "spec_path": "examples/other.yaml"},
        {"job_id": "c3", "status": "running", "spec_path": "examples/bracket_demo.yaml"},
    ]
    filtered = _filter_jobs(jobs, "failed", "other")
    assert len(filtered) == 1
    assert filtered[0]["job_id"] == "b2"

