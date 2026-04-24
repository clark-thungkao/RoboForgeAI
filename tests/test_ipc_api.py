from __future__ import annotations

import time
from pathlib import Path

from mmcad.app_service import BuildService
from mmcad.ipc_api import (
    api_get_artifacts,
    api_get_job_status,
    api_start_generation,
    api_start_generation_from_project,
)
from mmcad.project_io import create_project_data, save_project


def _await_terminal(service: BuildService, job_id: str, timeout_s: float = 2.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = service.get_job_status(job_id)
        if status["status"] in {"succeeded", "failed"}:
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
