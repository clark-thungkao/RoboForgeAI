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


def test_get_recent_failures_returns_latest_failed_jobs(tmp_path: Path) -> None:
    def fake_build(spec_path: str, outdir: str) -> str:
        if "fail" in spec_path:
            raise ValueError(f"failed for {spec_path}")
        return str(Path(outdir) / "ok")

    service = BuildService(build_fn=fake_build)
    first_failed = service.start_generation("fail-one.yaml", str(tmp_path))
    second_failed = service.start_generation("fail-two.yaml", str(tmp_path))
    ok_job = service.start_generation("ok.yaml", str(tmp_path))
    _wait_for_terminal_state(service, first_failed)
    _wait_for_terminal_state(service, second_failed)
    _wait_for_terminal_state(service, ok_job)

    failures = service.get_recent_failures(limit=2)
    assert len(failures) == 2
    assert failures[0]["job_id"] == second_failed
    assert failures[1]["job_id"] == first_failed
    assert "failed for" in failures[0]["error"]


def test_get_recent_failures_rejects_invalid_limit(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "ok"))
    with pytest.raises(ValueError, match="positive integer"):
        service.get_recent_failures(limit=0)


def test_get_home_snapshot_includes_dashboard_and_recent_failures(tmp_path: Path) -> None:
    def fake_build(spec_path: str, outdir: str) -> str:
        if "fail" in spec_path:
            raise ValueError("boom")
        project_dir = Path(outdir) / "demo"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "assembly.csv").write_text("a,b\n", encoding="utf-8")
        (project_dir / "design_report.json").write_text(
            '{"report_version": 1, "project": "demo"}',
            encoding="utf-8",
        )
        return str(project_dir)

    service = BuildService(build_fn=fake_build)
    failed_id = service.start_generation("fail.yaml", str(tmp_path))
    succeeded_id = service.start_generation("ok.yaml", str(tmp_path))
    _wait_for_terminal_state(service, failed_id)
    _wait_for_terminal_state(service, succeeded_id)

    snapshot = service.get_home_snapshot(recent_failure_limit=1)
    assert snapshot["dashboard"]["stats"]["total"] == 2
    assert snapshot["dashboard"]["latest_summary"]["latest_job"]["job_id"] == succeeded_id
    assert len(snapshot["recent_failures"]) == 1
    assert snapshot["recent_failures"][0]["job_id"] == failed_id


def test_get_home_snapshot_rejects_invalid_limit(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "ok"))
    with pytest.raises(ValueError, match="positive integer"):
        service.get_home_snapshot(recent_failure_limit=0)


def test_get_job_timeline_returns_recent_events(tmp_path: Path) -> None:
    def fake_build(spec_path: str, outdir: str) -> str:
        if "fail" in spec_path:
            raise ValueError("boom")
        project_dir = Path(outdir) / "demo"
        project_dir.mkdir(parents=True, exist_ok=True)
        return str(project_dir)

    service = BuildService(build_fn=fake_build)
    failed_id = service.start_generation("fail.yaml", str(tmp_path))
    succeeded_id = service.start_generation("ok.yaml", str(tmp_path))
    _wait_for_terminal_state(service, failed_id)
    _wait_for_terminal_state(service, succeeded_id)

    timeline = service.get_job_timeline(limit=6)
    assert len(timeline) > 0
    assert all(item["type"] in {"created", "started", "finished"} for item in timeline)
    assert any(item["job_id"] == failed_id and item["type"] == "finished" for item in timeline)
    assert any(item["job_id"] == succeeded_id for item in timeline)


def test_get_job_timeline_rejects_invalid_limit(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "ok"))
    with pytest.raises(ValueError, match="positive integer"):
        service.get_job_timeline(limit=0)


def test_get_ui_bootstrap_combines_home_and_timeline(tmp_path: Path) -> None:
    def fake_build(spec_path: str, outdir: str) -> str:
        if "fail" in spec_path:
            raise ValueError("boom")
        project_dir = Path(outdir) / "demo"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "assembly.csv").write_text("a,b\n", encoding="utf-8")
        (project_dir / "design_report.json").write_text(
            '{"report_version": 1, "project": "demo"}',
            encoding="utf-8",
        )
        return str(project_dir)

    service = BuildService(build_fn=fake_build)
    failed_id = service.start_generation("fail.yaml", str(tmp_path))
    succeeded_id = service.start_generation("ok.yaml", str(tmp_path))
    _wait_for_terminal_state(service, failed_id)
    _wait_for_terminal_state(service, succeeded_id)

    payload = service.get_ui_bootstrap(recent_failure_limit=1, timeline_limit=3)
    assert payload["home"]["dashboard"]["stats"]["total"] == 2
    assert payload["home"]["recent_failures"][0]["job_id"] == failed_id
    assert len(payload["timeline"]) <= 3
    assert any(event["job_id"] == succeeded_id for event in payload["timeline"])


def test_get_ui_bootstrap_rejects_invalid_limits(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "ok"))
    with pytest.raises(ValueError, match="positive integer"):
        service.get_ui_bootstrap(recent_failure_limit=0, timeline_limit=1)
    with pytest.raises(ValueError, match="positive integer"):
        service.get_ui_bootstrap(recent_failure_limit=1, timeline_limit=0)


def test_get_job_details_for_succeeded_job_includes_artifacts_and_metadata(tmp_path: Path) -> None:
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
    job_id = service.start_generation("ok.yaml", str(tmp_path))
    _wait_for_terminal_state(service, job_id)

    details = service.get_job_details(job_id)
    assert details["status"]["job_id"] == job_id
    assert details["artifacts"] is not None
    assert details["run_metadata"] is not None
    assert details["run_metadata"]["status"] == "succeeded"


def test_get_job_details_for_failed_job_omits_artifacts_and_metadata(tmp_path: Path) -> None:
    def fake_build(_: str, __: str) -> str:
        raise ValueError("boom")

    service = BuildService(build_fn=fake_build)
    job_id = service.start_generation("fail.yaml", str(tmp_path))
    _wait_for_terminal_state(service, job_id)

    details = service.get_job_details(job_id)
    assert details["status"]["status"] == "failed"
    assert details["artifacts"] is None
    assert details["run_metadata"] is None


def test_retry_job_starts_new_job_with_same_inputs(tmp_path: Path) -> None:
    captured: list[tuple[str, str]] = []

    def fake_build(spec_path: str, outdir: str) -> str:
        captured.append((spec_path, outdir))
        return str(Path(outdir) / "demo")

    service = BuildService(build_fn=fake_build)
    original_id = service.start_generation("spec.yaml", str(tmp_path))
    _wait_for_terminal_state(service, original_id)

    retry_id = service.retry_job(original_id)
    _wait_for_terminal_state(service, retry_id)

    assert retry_id != original_id
    assert len(captured) == 2
    assert captured[0] == captured[1]


def test_retry_job_unknown_id_raises_key_error() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    with pytest.raises(KeyError, match="Unknown job_id"):
        service.retry_job("missing")


def test_prune_jobs_removes_older_finished_jobs(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "ok"))
    first = service.start_generation("a.yaml", str(tmp_path))
    second = service.start_generation("b.yaml", str(tmp_path))
    third = service.start_generation("c.yaml", str(tmp_path))
    _wait_for_terminal_state(service, first)
    _wait_for_terminal_state(service, second)
    _wait_for_terminal_state(service, third)

    result = service.prune_jobs(keep_recent=1)
    assert result["removed_count"] == 2
    assert third not in result["removed_job_ids"]
    jobs = service.list_jobs()
    assert len(jobs) == 1
    assert jobs[0]["job_id"] == third


def test_prune_jobs_rejects_negative_keep_recent(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "ok"))
    with pytest.raises(ValueError, match="positive integer"):
        service.prune_jobs(keep_recent=-1)


def test_delete_job_removes_finished_job(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "ok"))
    job_id = service.start_generation("a.yaml", str(tmp_path))
    _wait_for_terminal_state(service, job_id)
    result = service.delete_job(job_id)
    assert result["deleted_job_id"] == job_id
    with pytest.raises(KeyError, match="Unknown job_id"):
        service.get_job_status(job_id)


def test_delete_job_rejects_running_job(tmp_path: Path) -> None:
    def slow_build(_: str, outdir: str) -> str:
        time.sleep(0.2)
        return str(Path(outdir) / "ok")

    service = BuildService(build_fn=slow_build)
    job_id = service.start_generation("a.yaml", str(tmp_path))
    time.sleep(0.05)
    with pytest.raises(RuntimeError, match="queued or running"):
        service.delete_job(job_id)


def test_delete_job_unknown_id_raises_key_error() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    with pytest.raises(KeyError, match="Unknown job_id"):
        service.delete_job("missing")


def test_get_active_jobs_returns_only_queued_or_running(tmp_path: Path) -> None:
    def slow_build(_: str, outdir: str) -> str:
        time.sleep(0.2)
        return str(Path(outdir) / "ok")

    service = BuildService(build_fn=slow_build)
    active_id = service.start_generation("slow.yaml", str(tmp_path))
    time.sleep(0.05)
    active = service.get_active_jobs()
    assert any(job["job_id"] == active_id for job in active)
    _wait_for_terminal_state(service, active_id)
    active_after = service.get_active_jobs()
    assert all(job["job_id"] != active_id for job in active_after)


def test_get_active_jobs_supports_limit_and_validation(tmp_path: Path) -> None:
    def slow_build(_: str, outdir: str) -> str:
        time.sleep(0.2)
        return str(Path(outdir) / "ok")

    service = BuildService(build_fn=slow_build)
    first = service.start_generation("a.yaml", str(tmp_path))
    second = service.start_generation("b.yaml", str(tmp_path))
    time.sleep(0.05)
    active = service.get_active_jobs(limit=1)
    assert len(active) == 1
    assert active[0]["job_id"] in {first, second}
    with pytest.raises(ValueError, match="positive integer"):
        service.get_active_jobs(limit=0)


def test_clear_finished_jobs_removes_all_finished_jobs(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "ok"))
    one = service.start_generation("a.yaml", str(tmp_path))
    two = service.start_generation("b.yaml", str(tmp_path))
    _wait_for_terminal_state(service, one)
    _wait_for_terminal_state(service, two)

    result = service.clear_finished_jobs()
    assert result["removed_count"] == 2
    assert len(service.list_jobs()) == 0


def test_clear_finished_jobs_keeps_active_jobs(tmp_path: Path) -> None:
    def slow_build(_: str, outdir: str) -> str:
        time.sleep(0.2)
        return str(Path(outdir) / "ok")

    service = BuildService(build_fn=slow_build)
    active = service.start_generation("slow.yaml", str(tmp_path))
    time.sleep(0.05)
    result = service.clear_finished_jobs()
    assert result["removed_count"] == 0
    assert service.get_job_status(active)["status"] in {"queued", "running"}


def test_delete_jobs_bulk_reports_deleted_and_errors(tmp_path: Path) -> None:
    def slow_build(_: str, outdir: str) -> str:
        time.sleep(0.2)
        return str(Path(outdir) / "ok")

    service = BuildService(build_fn=slow_build)
    finished_id = service.start_generation("done.yaml", str(tmp_path))
    _wait_for_terminal_state(service, finished_id)
    running_id = service.start_generation("slow.yaml", str(tmp_path))
    time.sleep(0.05)

    result = service.delete_jobs([finished_id, running_id, "missing"])
    assert result["requested_count"] == 3
    assert result["deleted_count"] == 1
    assert result["deleted_job_ids"] == [finished_id]
    assert len(result["errors"]) == 2
    assert any(item["job_id"] == running_id for item in result["errors"])
    assert any(item["job_id"] == "missing" for item in result["errors"])


def test_get_backend_capabilities_includes_version_and_features() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    capabilities = service.get_backend_capabilities()
    assert capabilities["api_version"] == 1
    assert "job_start" in capabilities["features"]
    assert "job_cleanup" in capabilities["features"]


def test_get_backend_health_reports_status_and_counts(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "ok"))
    job_id = service.start_generation("a.yaml", str(tmp_path))
    _wait_for_terminal_state(service, job_id)
    health = service.get_backend_health()
    assert health["status"] == "ok"
    assert health["api_version"] == 1
    assert health["total_jobs"] >= 1
    assert health["active_jobs"] >= 0


def test_get_contract_summary_includes_envelope_and_error_categories() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    summary = service.get_contract_summary()
    assert summary["api_version"] == 1
    assert summary["response_envelope"]["success"]["ok"] is True
    assert "input_validation_error" in summary["error_categories"]
    assert "job_cleanup" in summary["endpoint_groups"]


def test_cancel_all_active_jobs_requests_cancellation_for_running_jobs(tmp_path: Path) -> None:
    def slow_build(_: str, outdir: str) -> str:
        time.sleep(0.2)
        return str(Path(outdir) / "ok")

    service = BuildService(build_fn=slow_build)
    first = service.start_generation("a.yaml", str(tmp_path))
    second = service.start_generation("b.yaml", str(tmp_path))
    time.sleep(0.05)

    result = service.cancel_all_active_jobs()
    assert result["requested_count"] >= 1
    assert result["cancelled_count"] >= 1
    assert len(result["cancelled_job_ids"]) >= 1
    _wait_for_terminal_state(service, first)
    _wait_for_terminal_state(service, second)


def test_cancel_all_active_jobs_when_none_active_returns_zero() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = service.cancel_all_active_jobs()
    assert result["requested_count"] == 0
    assert result["cancelled_count"] == 0
