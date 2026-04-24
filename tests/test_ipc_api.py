from __future__ import annotations

import time
from pathlib import Path

from mmcad.app_service import BuildService
from mmcad.ipc_api import (
    api_cancel_generation,
    api_create_project,
    api_get_artifacts,
    api_get_job_status,
    api_get_run_metadata,
    api_list_jobs,
    api_load_project,
    api_save_project,
    api_start_generation,
    api_start_generation_from_project_data,
    api_start_generation_from_project,
    api_validate_project_data,
)
from mmcad.project_io import create_project_data, save_project


def _await_terminal(service: BuildService, job_id: str, timeout_s: float = 2.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = service.get_job_status(job_id)
        if status["status"] in {"succeeded", "failed", "cancelled"}:
            return
        time.sleep(0.01)
    raise TimeoutError("job did not complete in time")


def test_api_start_generation_success() -> None:
    service = BuildService(build_fn=lambda *_: "build/demo")
    result = api_start_generation(service, "spec.yaml", "build")

    assert result["ok"] is True
    assert "job_id" in result["data"]


def test_api_get_job_status_bad_id_returns_input_error() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_get_job_status(service, "missing")

    assert result["ok"] is False
    assert result["error"]["category"] == "input_validation_error"


def test_api_get_artifacts_running_job_returns_generation_failure(tmp_path: Path) -> None:
    def slow_build(_: str, __: str) -> str:
        time.sleep(0.15)
        project_dir = tmp_path / "demo"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "a.step").write_text("x", encoding="utf-8")
        return str(project_dir)

    service = BuildService(build_fn=slow_build)
    started = api_start_generation(service, "spec.yaml", str(tmp_path))
    result = api_get_artifacts(service, started["data"]["job_id"])

    assert result["ok"] is False
    assert result["error"]["category"] == "generation_failure"


def test_api_get_artifacts_succeeded_job_returns_files(tmp_path: Path) -> None:
    def fake_build(_: str, outdir: str) -> str:
        project_dir = Path(outdir) / "demo"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "assembly.csv").write_text("a,b\n", encoding="utf-8")
        return str(project_dir)

    service = BuildService(build_fn=fake_build)
    started = api_start_generation(service, "spec.yaml", str(tmp_path))
    job_id = started["data"]["job_id"]
    _await_terminal(service, job_id)
    result = api_get_artifacts(service, job_id)

    assert result["ok"] is True
    assert any(path.endswith("assembly.csv") for path in result["data"]["files"])


def test_api_start_generation_from_project_success(tmp_path: Path) -> None:
    project_path = tmp_path / "sample.rfa.json"
    save_project(
        str(project_path),
        create_project_data(
            name="sample",
            spec_path="examples/bracket_demo.yaml",
            outdir=str(tmp_path / "out"),
        ),
    )
    service = BuildService(build_fn=lambda *_: str(tmp_path / "out" / "sample"))

    result = api_start_generation_from_project(service, str(project_path))
    assert result["ok"] is True
    assert "job_id" in result["data"]


def test_api_start_generation_from_project_invalid_file_returns_input_error() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_start_generation_from_project(service, "missing.rfa.json")

    assert result["ok"] is False
    assert result["error"]["category"] == "input_validation_error"


def test_api_start_generation_from_project_data_success(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "out" / "sample"))
    project_data = create_project_data(
        name="sample",
        spec_path="examples/bracket_demo.yaml",
        outdir=str(tmp_path / "out"),
    )
    result = api_start_generation_from_project_data(service, project_data)
    assert result["ok"] is True
    assert "job_id" in result["data"]


def test_api_start_generation_from_project_data_invalid_payload_returns_input_error() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_start_generation_from_project_data(service, {"schema_version": 1})
    assert result["ok"] is False
    assert result["error"]["category"] == "input_validation_error"


def test_api_list_jobs_returns_jobs_array(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "demo"))
    job_id = api_start_generation(service, "spec.yaml", str(tmp_path))["data"]["job_id"]
    _await_terminal(service, job_id)

    result = api_list_jobs(service)
    assert result["ok"] is True
    assert isinstance(result["data"]["jobs"], list)
    assert any(job["job_id"] == job_id for job in result["data"]["jobs"])


def test_api_list_jobs_supports_status_and_limit_filters(tmp_path: Path) -> None:
    def fake_build(spec_path: str, outdir: str) -> str:
        if "fail" in spec_path:
            raise ValueError("boom")
        return str(Path(outdir) / "ok")

    service = BuildService(build_fn=fake_build)
    api_start_generation(service, "ok.yaml", str(tmp_path))
    failed_job = api_start_generation(service, "fail.yaml", str(tmp_path))["data"]["job_id"]
    _await_terminal(service, failed_job)

    result = api_list_jobs(service, status="failed", limit=1)
    assert result["ok"] is True
    assert len(result["data"]["jobs"]) == 1
    assert result["data"]["jobs"][0]["status"] == "failed"


def test_api_list_jobs_invalid_limit_returns_input_error(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "demo"))
    result = api_list_jobs(service, limit=0)
    assert result["ok"] is False
    assert result["error"]["category"] == "input_validation_error"


def test_api_cancel_generation_unknown_job_returns_input_error() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_cancel_generation(service, "missing")

    assert result["ok"] is False
    assert result["error"]["category"] == "input_validation_error"


def test_api_cancel_generation_running_job(tmp_path: Path) -> None:
    def slow_build(_: str, outdir: str) -> str:
        time.sleep(0.2)
        project_dir = Path(outdir) / "demo"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "assembly.csv").write_text("a,b\n", encoding="utf-8")
        return str(project_dir)

    service = BuildService(build_fn=slow_build)
    started = api_start_generation(service, "spec.yaml", str(tmp_path))
    job_id = started["data"]["job_id"]
    time.sleep(0.05)
    cancelled = api_cancel_generation(service, job_id)
    assert cancelled["ok"] is True
    _await_terminal(service, job_id)
    status = api_get_job_status(service, job_id)
    assert status["data"]["status"] == "cancelled"


def test_api_get_run_metadata_success(tmp_path: Path) -> None:
    def fake_build(_: str, outdir: str) -> str:
        project_dir = Path(outdir) / "demo"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "assembly.csv").write_text("a,b\n", encoding="utf-8")
        (project_dir / "design_report.json").write_text(
            '{"report_version": 1, "project": "demo"}',
            encoding="utf-8",
        )
        return str(project_dir)

    service = BuildService(build_fn=fake_build)
    started = api_start_generation(service, "spec.yaml", str(tmp_path))
    job_id = started["data"]["job_id"]
    _await_terminal(service, job_id)

    result = api_get_run_metadata(service, job_id)
    assert result["ok"] is True
    assert result["data"]["status"] == "succeeded"
    assert result["data"]["design_report"]["report_version"] == 1


def test_api_get_run_metadata_non_terminal_returns_generation_failure(tmp_path: Path) -> None:
    def slow_build(_: str, outdir: str) -> str:
        time.sleep(0.2)
        return str(Path(outdir) / "demo")

    service = BuildService(build_fn=slow_build)
    started = api_start_generation(service, "spec.yaml", str(tmp_path))
    result = api_get_run_metadata(service, started["data"]["job_id"])

    assert result["ok"] is False
    assert result["error"]["category"] == "generation_failure"


def test_api_create_project_builds_project_payload() -> None:
    result = api_create_project(name="demo", spec_path="examples/bracket_demo.yaml", outdir="build")

    assert result["ok"] is True
    project = result["data"]["project"]
    assert project["project"]["name"] == "demo"
    assert project["inputs"]["spec_path"] == "examples/bracket_demo.yaml"


def test_api_save_and_load_project_round_trip(tmp_path: Path) -> None:
    project_path = tmp_path / "demo.rfa.json"
    created = api_create_project(name="demo", spec_path="examples/bracket_demo.yaml")
    saved = api_save_project(str(project_path), created["data"]["project"])
    loaded = api_load_project(str(project_path))

    assert saved["ok"] is True
    assert loaded["ok"] is True
    assert loaded["data"]["project"]["project"]["name"] == "demo"


def test_api_load_project_bad_path_returns_input_error() -> None:
    result = api_load_project("missing.rfa.json")
    assert result["ok"] is False
    assert result["error"]["category"] == "input_validation_error"


def test_api_save_project_invalid_payload_returns_input_error(tmp_path: Path) -> None:
    project_path = tmp_path / "bad.rfa.json"
    result = api_save_project(str(project_path), {"schema_version": 1})
    assert result["ok"] is False
    assert result["error"]["category"] == "input_validation_error"


def test_api_validate_project_data_success() -> None:
    project = create_project_data(name="demo", spec_path="examples/bracket_demo.yaml")
    result = api_validate_project_data(project)
    assert result["ok"] is True
    assert result["data"]["project"]["project"]["name"] == "demo"


def test_api_validate_project_data_invalid_payload_returns_input_error() -> None:
    result = api_validate_project_data({"schema_version": 1})
    assert result["ok"] is False
    assert result["error"]["category"] == "input_validation_error"
