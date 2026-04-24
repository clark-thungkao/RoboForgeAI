from __future__ import annotations

import time
from pathlib import Path

import pytest

from mmcad.app_service import BuildService
from mmcad.project_io import create_project_data, save_project


def _wait_for_terminal_state(service: BuildService, job_id: str, timeout_s: float = 2.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = service.get_job_status(job_id)
        if status["status"] in {"succeeded", "failed", "cancelled"}:
            return status
        time.sleep(0.01)
    raise TimeoutError(f"Job {job_id} did not finish within {timeout_s} seconds.")


def test_start_generation_success_and_artifacts(tmp_path: Path) -> None:
    def fake_build(spec_path: str, outdir: str) -> str:
        project_dir = Path(outdir) / "demo"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "assembly.csv").write_text("assembly,part,tx,ty,tz,rx,ry,rz\n", encoding="utf-8")
        (project_dir / "part.step").write_text("step", encoding="utf-8")
        return str(project_dir)

    service = BuildService(build_fn=fake_build)
    job_id = service.start_generation("spec.yaml", str(tmp_path))
    status = _wait_for_terminal_state(service, job_id)

    assert status["status"] == "succeeded"
    artifacts = service.get_artifacts(job_id)
    assert artifacts["project_outdir"].endswith("demo")
    assert any(path.endswith("assembly.csv") for path in artifacts["files"])
    assert any(path.endswith("part.step") for path in artifacts["files"])


def test_start_generation_failure_exposes_error(tmp_path: Path) -> None:
    def fake_build(_: str, __: str) -> str:
        raise ValueError("build blew up")

    service = BuildService(build_fn=fake_build)
    job_id = service.start_generation("spec.yaml", str(tmp_path))
    status = _wait_for_terminal_state(service, job_id)

    assert status["status"] == "failed"
    assert "build blew up" in status["error"]
    with pytest.raises(RuntimeError, match="only available for succeeded jobs"):
        service.get_artifacts(job_id)


def test_unknown_job_id_raises_key_error() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    with pytest.raises(KeyError, match="Unknown job_id"):
        service.get_job_status("missing")


def test_list_jobs_returns_newest_first(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "a"))
    first = service.start_generation("one.yaml", str(tmp_path))
    second = service.start_generation("two.yaml", str(tmp_path))
    _wait_for_terminal_state(service, first)
    _wait_for_terminal_state(service, second)

    jobs = service.list_jobs()
    assert len(jobs) >= 2
    assert jobs[0]["job_id"] == second
    assert jobs[1]["job_id"] == first


def test_list_jobs_supports_status_filter(tmp_path: Path) -> None:
    def fake_build(spec_path: str, outdir: str) -> str:
        if "fail" in spec_path:
            raise ValueError("boom")
        return str(Path(outdir) / "ok")

    service = BuildService(build_fn=fake_build)
    success_job = service.start_generation("ok.yaml", str(tmp_path))
    failed_job = service.start_generation("fail.yaml", str(tmp_path))
    _wait_for_terminal_state(service, success_job)
    _wait_for_terminal_state(service, failed_job)

    failed_jobs = service.list_jobs(status="failed")
    assert len(failed_jobs) == 1
    assert failed_jobs[0]["job_id"] == failed_job


def test_list_jobs_supports_limit(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "a"))
    first = service.start_generation("one.yaml", str(tmp_path))
    second = service.start_generation("two.yaml", str(tmp_path))
    _wait_for_terminal_state(service, first)
    _wait_for_terminal_state(service, second)

    jobs = service.list_jobs(limit=1)
    assert len(jobs) == 1
    assert jobs[0]["job_id"] == second


def test_list_jobs_rejects_non_positive_limit(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "a"))
    with pytest.raises(ValueError, match="positive integer"):
        service.list_jobs(limit=0)


def test_cancel_generation_unknown_job_raises_key_error() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    with pytest.raises(KeyError, match="Unknown job_id"):
        service.cancel_generation("missing")


def test_start_generation_from_project_uses_project_spec_and_outdir(tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    def fake_build(spec_path: str, outdir: str) -> str:
        captured["spec_path"] = spec_path
        captured["outdir"] = outdir
        project_dir = Path(outdir) / "demo"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "artifact.step").write_text("ok", encoding="utf-8")
        return str(project_dir)

    project_file = tmp_path / "sample.rfa.json"
    project_data = create_project_data(
        name="sample",
        spec_path="examples/bracket_demo.yaml",
        outdir=str(tmp_path / "out"),
    )
    save_project(str(project_file), project_data)

    service = BuildService(build_fn=fake_build)
    job_id = service.start_generation_from_project(str(project_file))
    status = _wait_for_terminal_state(service, job_id)

    assert status["status"] == "succeeded"
    assert captured["spec_path"] == "examples/bracket_demo.yaml"
    assert captured["outdir"] == str(tmp_path / "out")


def test_start_generation_from_project_data_uses_project_spec_and_outdir(tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    def fake_build(spec_path: str, outdir: str) -> str:
        captured["spec_path"] = spec_path
        captured["outdir"] = outdir
        project_dir = Path(outdir) / "demo"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "artifact.step").write_text("ok", encoding="utf-8")
        return str(project_dir)

    project_data = create_project_data(
        name="sample",
        spec_path="examples/bracket_demo.yaml",
        outdir=str(tmp_path / "out"),
    )

    service = BuildService(build_fn=fake_build)
    job_id = service.start_generation_from_project_data(project_data)
    status = _wait_for_terminal_state(service, job_id)

    assert status["status"] == "succeeded"
    assert captured["spec_path"] == "examples/bracket_demo.yaml"
    assert captured["outdir"] == str(tmp_path / "out")


def test_cancel_generation_while_running_marks_cancelled(tmp_path: Path) -> None:
    def slow_build(_: str, outdir: str) -> str:
        time.sleep(0.2)
        project_dir = Path(outdir) / "demo"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "artifact.step").write_text("ok", encoding="utf-8")
        return str(project_dir)

    service = BuildService(build_fn=slow_build)
    job_id = service.start_generation("spec.yaml", str(tmp_path))
    time.sleep(0.05)
    service.cancel_generation(job_id)
    status = _wait_for_terminal_state(service, job_id)
    assert status["status"] == "cancelled"
    assert "Cancelled by user" in status["error"]


def test_get_run_metadata_returns_report_and_artifact_list(tmp_path: Path) -> None:
    def fake_build(_: str, outdir: str) -> str:
        project_dir = Path(outdir) / "demo"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "a.step").write_text("step", encoding="utf-8")
        (project_dir / "design_report.json").write_text(
            '{"report_version": 1, "project": "demo"}',
            encoding="utf-8",
        )
        return str(project_dir)

    service = BuildService(build_fn=fake_build)
    job_id = service.start_generation("spec.yaml", str(tmp_path))
    _wait_for_terminal_state(service, job_id)

    metadata = service.get_run_metadata(job_id)
    assert metadata["job_id"] == job_id
    assert metadata["status"] == "succeeded"
    assert any(path.endswith("a.step") for path in metadata["artifacts"])
    assert metadata["design_report"]["report_version"] == 1


def test_get_run_metadata_requires_success(tmp_path: Path) -> None:
    def slow_build(_: str, __: str) -> str:
        time.sleep(0.2)
        return str(tmp_path / "demo")

    service = BuildService(build_fn=slow_build)
    job_id = service.start_generation("spec.yaml", str(tmp_path))
    with pytest.raises(RuntimeError, match="succeeded jobs"):
        service.get_run_metadata(job_id)


def test_get_latest_job_summary_requires_existing_jobs() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    with pytest.raises(RuntimeError, match="No jobs available"):
        service.get_latest_job_summary()


def test_get_latest_job_summary_includes_run_metadata_for_success(tmp_path: Path) -> None:
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
    job_id = service.start_generation("spec.yaml", str(tmp_path))
    _wait_for_terminal_state(service, job_id)
    summary = service.get_latest_job_summary()
    assert summary["latest_job"]["job_id"] == job_id
    assert summary["run_metadata"] is not None
    assert summary["run_metadata"]["status"] == "succeeded"


def test_get_latest_job_summary_omits_metadata_for_failed_job(tmp_path: Path) -> None:
    def fake_build(_: str, __: str) -> str:
        raise ValueError("boom")

    service = BuildService(build_fn=fake_build)
    job_id = service.start_generation("spec.yaml", str(tmp_path))
    _wait_for_terminal_state(service, job_id)
    summary = service.get_latest_job_summary()
    assert summary["latest_job"]["job_id"] == job_id
    assert summary["latest_job"]["status"] == "failed"
    assert summary["run_metadata"] is None


def test_get_job_stats_returns_zeroed_counts_when_empty() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    stats = service.get_job_stats()
    assert stats["total"] == 0
    assert stats["latest_job_id"] is None
    assert stats["by_status"]["queued"] == 0
    assert stats["by_status"]["succeeded"] == 0


def test_get_job_stats_counts_statuses_and_tracks_latest_job(tmp_path: Path) -> None:
    def fake_build(spec_path: str, outdir: str) -> str:
        if "fail" in spec_path:
            raise ValueError("boom")
        return str(Path(outdir) / "ok")

    service = BuildService(build_fn=fake_build)
    first = service.start_generation("ok.yaml", str(tmp_path))
    second = service.start_generation("fail.yaml", str(tmp_path))
    third = service.start_generation("ok-2.yaml", str(tmp_path))
    _wait_for_terminal_state(service, first)
    _wait_for_terminal_state(service, second)
    _wait_for_terminal_state(service, third)

    stats = service.get_job_stats()
    assert stats["total"] == 3
    assert stats["by_status"]["succeeded"] == 2
    assert stats["by_status"]["failed"] == 1
    assert stats["latest_job_id"] == third


def test_get_dashboard_snapshot_empty_service_has_no_latest_summary() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    snapshot = service.get_dashboard_snapshot()
    assert snapshot["stats"]["total"] == 0
    assert snapshot["latest_summary"] is None


def test_get_dashboard_snapshot_includes_latest_summary_when_jobs_exist(tmp_path: Path) -> None:
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
    job_id = service.start_generation("spec.yaml", str(tmp_path))
    _wait_for_terminal_state(service, job_id)
    snapshot = service.get_dashboard_snapshot()
    assert snapshot["stats"]["total"] == 1
    assert snapshot["latest_summary"] is not None
    assert snapshot["latest_summary"]["latest_job"]["job_id"] == job_id
