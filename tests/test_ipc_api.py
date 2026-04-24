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
    api_get_latest_job_summary,
    api_get_job_stats,
    api_get_dashboard_snapshot,
    api_get_recent_failures,
    api_get_home_snapshot,
    api_get_job_timeline,
    api_get_ui_bootstrap,
    api_get_job_details,
    api_retry_job,
    api_prune_jobs,
    api_delete_job,
    api_get_active_jobs,
    api_clear_finished_jobs,
    api_delete_jobs,
    api_get_backend_capabilities,
    api_get_backend_health,
    api_get_contract_summary,
    api_cancel_all_active_jobs,
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


def test_api_get_latest_job_summary_returns_generation_failure_when_empty() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_get_latest_job_summary(service)
    assert result["ok"] is False
    assert result["error"]["category"] == "generation_failure"


def test_api_get_latest_job_summary_success(tmp_path: Path) -> None:
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
    job_id = api_start_generation(service, "spec.yaml", str(tmp_path))["data"]["job_id"]
    _await_terminal(service, job_id)
    result = api_get_latest_job_summary(service)
    assert result["ok"] is True
    assert result["data"]["latest_job"]["job_id"] == job_id
    assert result["data"]["run_metadata"]["status"] == "succeeded"


def test_api_get_job_stats_empty_service() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_get_job_stats(service)
    assert result["ok"] is True
    assert result["data"]["total"] == 0
    assert result["data"]["latest_job_id"] is None


def test_api_get_job_stats_counts_jobs(tmp_path: Path) -> None:
    def fake_build(spec_path: str, outdir: str) -> str:
        if "fail" in spec_path:
            raise ValueError("boom")
        return str(Path(outdir) / "ok")

    service = BuildService(build_fn=fake_build)
    api_start_generation(service, "ok.yaml", str(tmp_path))
    failed_id = api_start_generation(service, "fail.yaml", str(tmp_path))["data"]["job_id"]
    _await_terminal(service, failed_id)
    result = api_get_job_stats(service)
    assert result["ok"] is True
    assert result["data"]["total"] >= 2
    assert result["data"]["by_status"]["failed"] >= 1


def test_api_get_dashboard_snapshot_empty_service() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_get_dashboard_snapshot(service)
    assert result["ok"] is True
    assert result["data"]["stats"]["total"] == 0
    assert result["data"]["latest_summary"] is None


def test_api_get_dashboard_snapshot_with_succeeded_latest_job(tmp_path: Path) -> None:
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
    job_id = api_start_generation(service, "spec.yaml", str(tmp_path))["data"]["job_id"]
    _await_terminal(service, job_id)
    result = api_get_dashboard_snapshot(service)
    assert result["ok"] is True
    assert result["data"]["stats"]["total"] == 1
    assert result["data"]["latest_summary"]["latest_job"]["job_id"] == job_id


def test_api_get_recent_failures_returns_failed_jobs(tmp_path: Path) -> None:
    def fake_build(spec_path: str, outdir: str) -> str:
        if "fail" in spec_path:
            raise ValueError("boom")
        return str(Path(outdir) / "ok")

    service = BuildService(build_fn=fake_build)
    failed_id = api_start_generation(service, "fail.yaml", str(tmp_path))["data"]["job_id"]
    _await_terminal(service, failed_id)
    result = api_get_recent_failures(service, limit=1)
    assert result["ok"] is True
    assert len(result["data"]["failures"]) == 1
    assert result["data"]["failures"][0]["job_id"] == failed_id


def test_api_get_recent_failures_invalid_limit_returns_input_error() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_get_recent_failures(service, limit=0)
    assert result["ok"] is False
    assert result["error"]["category"] == "input_validation_error"


def test_api_get_home_snapshot_success(tmp_path: Path) -> None:
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
    failed_id = api_start_generation(service, "fail.yaml", str(tmp_path))["data"]["job_id"]
    succeeded_id = api_start_generation(service, "ok.yaml", str(tmp_path))["data"]["job_id"]
    _await_terminal(service, failed_id)
    _await_terminal(service, succeeded_id)
    result = api_get_home_snapshot(service, recent_failure_limit=1)
    assert result["ok"] is True
    assert result["data"]["dashboard"]["latest_summary"]["latest_job"]["job_id"] == succeeded_id
    assert result["data"]["recent_failures"][0]["job_id"] == failed_id


def test_api_get_home_snapshot_invalid_limit_returns_input_error() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_get_home_snapshot(service, recent_failure_limit=0)
    assert result["ok"] is False
    assert result["error"]["category"] == "input_validation_error"


def test_api_get_job_timeline_success(tmp_path: Path) -> None:
    def fake_build(spec_path: str, outdir: str) -> str:
        if "fail" in spec_path:
            raise ValueError("boom")
        project_dir = Path(outdir) / "demo"
        project_dir.mkdir(parents=True, exist_ok=True)
        return str(project_dir)

    service = BuildService(build_fn=fake_build)
    failed_id = api_start_generation(service, "fail.yaml", str(tmp_path))["data"]["job_id"]
    _await_terminal(service, failed_id)
    result = api_get_job_timeline(service, limit=5)
    assert result["ok"] is True
    assert len(result["data"]["timeline"]) > 0
    assert any(item["job_id"] == failed_id for item in result["data"]["timeline"])


def test_api_get_job_timeline_invalid_limit_returns_input_error() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_get_job_timeline(service, limit=0)
    assert result["ok"] is False
    assert result["error"]["category"] == "input_validation_error"


def test_api_get_ui_bootstrap_success(tmp_path: Path) -> None:
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
    failed_id = api_start_generation(service, "fail.yaml", str(tmp_path))["data"]["job_id"]
    succeeded_id = api_start_generation(service, "ok.yaml", str(tmp_path))["data"]["job_id"]
    _await_terminal(service, failed_id)
    _await_terminal(service, succeeded_id)

    result = api_get_ui_bootstrap(service, recent_failure_limit=1, timeline_limit=4)
    assert result["ok"] is True
    assert result["data"]["home"]["dashboard"]["stats"]["total"] == 2
    assert result["data"]["home"]["recent_failures"][0]["job_id"] == failed_id
    assert any(event["job_id"] == succeeded_id for event in result["data"]["timeline"])


def test_api_get_ui_bootstrap_invalid_limit_returns_input_error() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_get_ui_bootstrap(service, recent_failure_limit=0, timeline_limit=1)
    assert result["ok"] is False
    assert result["error"]["category"] == "input_validation_error"


def test_api_get_job_details_success_for_succeeded_job(tmp_path: Path) -> None:
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
    job_id = api_start_generation(service, "ok.yaml", str(tmp_path))["data"]["job_id"]
    _await_terminal(service, job_id)
    result = api_get_job_details(service, job_id)
    assert result["ok"] is True
    assert result["data"]["status"]["job_id"] == job_id
    assert result["data"]["artifacts"] is not None
    assert result["data"]["run_metadata"] is not None


def test_api_get_job_details_unknown_job_returns_input_error() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_get_job_details(service, "missing")
    assert result["ok"] is False
    assert result["error"]["category"] == "input_validation_error"


def test_api_retry_job_success(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "demo"))
    original_id = api_start_generation(service, "spec.yaml", str(tmp_path))["data"]["job_id"]
    _await_terminal(service, original_id)

    retried = api_retry_job(service, original_id)
    assert retried["ok"] is True
    assert retried["data"]["job_id"] != original_id


def test_api_retry_job_unknown_job_returns_input_error() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_retry_job(service, "missing")
    assert result["ok"] is False
    assert result["error"]["category"] == "input_validation_error"


def test_api_prune_jobs_success(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "ok"))
    first = api_start_generation(service, "a.yaml", str(tmp_path))["data"]["job_id"]
    second = api_start_generation(service, "b.yaml", str(tmp_path))["data"]["job_id"]
    _await_terminal(service, first)
    _await_terminal(service, second)

    result = api_prune_jobs(service, keep_recent=1)
    assert result["ok"] is True
    assert result["data"]["removed_count"] == 1
    jobs = api_list_jobs(service)
    assert len(jobs["data"]["jobs"]) == 1


def test_api_prune_jobs_invalid_keep_recent_returns_input_error() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_prune_jobs(service, keep_recent=-1)
    assert result["ok"] is False
    assert result["error"]["category"] == "input_validation_error"


def test_api_delete_job_success(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "ok"))
    job_id = api_start_generation(service, "a.yaml", str(tmp_path))["data"]["job_id"]
    _await_terminal(service, job_id)
    result = api_delete_job(service, job_id)
    assert result["ok"] is True
    assert result["data"]["deleted_job_id"] == job_id


def test_api_delete_job_running_returns_generation_failure(tmp_path: Path) -> None:
    def slow_build(_: str, outdir: str) -> str:
        time.sleep(0.2)
        return str(Path(outdir) / "ok")

    service = BuildService(build_fn=slow_build)
    job_id = api_start_generation(service, "a.yaml", str(tmp_path))["data"]["job_id"]
    time.sleep(0.05)
    result = api_delete_job(service, job_id)
    assert result["ok"] is False
    assert result["error"]["category"] == "generation_failure"


def test_api_delete_job_unknown_returns_input_error() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_delete_job(service, "missing")
    assert result["ok"] is False
    assert result["error"]["category"] == "input_validation_error"


def test_api_get_active_jobs_success(tmp_path: Path) -> None:
    def slow_build(_: str, outdir: str) -> str:
        time.sleep(0.2)
        return str(Path(outdir) / "ok")

    service = BuildService(build_fn=slow_build)
    active_id = api_start_generation(service, "slow.yaml", str(tmp_path))["data"]["job_id"]
    time.sleep(0.05)
    result = api_get_active_jobs(service, limit=1)
    assert result["ok"] is True
    assert len(result["data"]["jobs"]) <= 1
    assert any(job["job_id"] == active_id for job in result["data"]["jobs"])


def test_api_get_active_jobs_invalid_limit_returns_input_error() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_get_active_jobs(service, limit=0)
    assert result["ok"] is False
    assert result["error"]["category"] == "input_validation_error"


def test_api_clear_finished_jobs_success(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "ok"))
    one = api_start_generation(service, "a.yaml", str(tmp_path))["data"]["job_id"]
    two = api_start_generation(service, "b.yaml", str(tmp_path))["data"]["job_id"]
    _await_terminal(service, one)
    _await_terminal(service, two)
    result = api_clear_finished_jobs(service)
    assert result["ok"] is True
    assert result["data"]["removed_count"] == 2


def test_api_clear_finished_jobs_keeps_active_jobs(tmp_path: Path) -> None:
    def slow_build(_: str, outdir: str) -> str:
        time.sleep(0.2)
        return str(Path(outdir) / "ok")

    service = BuildService(build_fn=slow_build)
    active = api_start_generation(service, "slow.yaml", str(tmp_path))["data"]["job_id"]
    time.sleep(0.05)
    result = api_clear_finished_jobs(service)
    assert result["ok"] is True
    assert result["data"]["removed_count"] == 0
    status = api_get_job_status(service, active)
    assert status["ok"] is True


def test_api_delete_jobs_bulk_success_with_partial_errors(tmp_path: Path) -> None:
    def slow_build(_: str, outdir: str) -> str:
        time.sleep(0.2)
        return str(Path(outdir) / "ok")

    service = BuildService(build_fn=slow_build)
    finished_id = api_start_generation(service, "done.yaml", str(tmp_path))["data"]["job_id"]
    _await_terminal(service, finished_id)
    running_id = api_start_generation(service, "slow.yaml", str(tmp_path))["data"]["job_id"]
    time.sleep(0.05)

    result = api_delete_jobs(service, [finished_id, running_id, "missing"])
    assert result["ok"] is True
    assert result["data"]["deleted_count"] == 1
    assert result["data"]["deleted_job_ids"] == [finished_id]
    assert len(result["data"]["errors"]) == 2


def test_api_get_backend_capabilities_success() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_get_backend_capabilities(service)
    assert result["ok"] is True
    assert result["data"]["api_version"] == 1
    assert "job_status" in result["data"]["features"]


def test_api_get_backend_health_success(tmp_path: Path) -> None:
    service = BuildService(build_fn=lambda *_: str(tmp_path / "ok"))
    job_id = api_start_generation(service, "a.yaml", str(tmp_path))["data"]["job_id"]
    _await_terminal(service, job_id)
    result = api_get_backend_health(service)
    assert result["ok"] is True
    assert result["data"]["status"] == "ok"
    assert result["data"]["api_version"] == 1


def test_api_get_contract_summary_success() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_get_contract_summary(service)
    assert result["ok"] is True
    assert result["data"]["api_version"] == 1
    assert "unknown_error" in result["data"]["error_categories"]


def test_api_cancel_all_active_jobs_success(tmp_path: Path) -> None:
    def slow_build(_: str, outdir: str) -> str:
        time.sleep(0.2)
        return str(Path(outdir) / "ok")

    service = BuildService(build_fn=slow_build)
    api_start_generation(service, "a.yaml", str(tmp_path))
    api_start_generation(service, "b.yaml", str(tmp_path))
    time.sleep(0.05)
    result = api_cancel_all_active_jobs(service)
    assert result["ok"] is True
    assert result["data"]["requested_count"] >= 1
    assert result["data"]["cancelled_count"] >= 1


def test_api_cancel_all_active_jobs_when_none_active() -> None:
    service = BuildService(build_fn=lambda *_: "unused")
    result = api_cancel_all_active_jobs(service)
    assert result["ok"] is True
    assert result["data"]["requested_count"] == 0
    assert result["data"]["cancelled_count"] == 0
