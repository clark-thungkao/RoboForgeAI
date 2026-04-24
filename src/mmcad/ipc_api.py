from __future__ import annotations

from typing import Any

from mmcad.app_service import BuildService
from mmcad.project_io import (
    ProjectError,
    create_project_data,
    load_project,
    save_project,
    validate_project_data,
)


def _error_payload(category: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"category": category, "message": message}}


def api_start_generation(service: BuildService, spec_path: str, outdir: str) -> dict[str, Any]:
    try:
        job_id = service.start_generation(spec_path, outdir)
    except ProjectError as err:
        return _error_payload("input_validation_error", str(err))
    except ValueError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": {"job_id": job_id}}


def api_create_project(
    *,
    name: str,
    spec_path: str,
    outdir: str = "build",
    generation_profile: dict | None = None,
    outputs: dict | None = None,
    metadata: dict | None = None,
) -> dict[str, Any]:
    try:
        project = create_project_data(
            name=name,
            spec_path=spec_path,
            outdir=outdir,
            generation_profile=generation_profile,
            outputs=outputs,
            metadata=metadata,
        )
    except ProjectError as err:
        return _error_payload("input_validation_error", str(err))
    except ValueError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": {"project": project}}


def api_save_project(project_path: str, project_data: dict[str, Any]) -> dict[str, Any]:
    try:
        save_project(project_path, project_data)
    except ProjectError as err:
        return _error_payload("input_validation_error", str(err))
    except ValueError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": {"project_path": project_path}}


def api_load_project(project_path: str) -> dict[str, Any]:
    try:
        project = load_project(project_path)
    except ProjectError as err:
        return _error_payload("input_validation_error", str(err))
    except ValueError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": {"project": project}}


def api_validate_project_data(project_data: dict[str, Any]) -> dict[str, Any]:
    try:
        project = validate_project_data(project_data)
    except ProjectError as err:
        return _error_payload("input_validation_error", str(err))
    except ValueError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": {"project": project}}


def api_start_generation_from_project(service: BuildService, project_path: str) -> dict[str, Any]:
    try:
        job_id = service.start_generation_from_project(project_path)
    except ProjectError as err:
        return _error_payload("input_validation_error", str(err))
    except ValueError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": {"job_id": job_id}}


def api_start_generation_from_project_data(
    service: BuildService, project_data: dict[str, Any]
) -> dict[str, Any]:
    try:
        job_id = service.start_generation_from_project_data(project_data)
    except ProjectError as err:
        return _error_payload("input_validation_error", str(err))
    except ValueError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": {"job_id": job_id}}


def api_get_job_status(service: BuildService, job_id: str) -> dict[str, Any]:
    try:
        status = service.get_job_status(job_id)
    except KeyError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": status}


def api_list_jobs(
    service: BuildService, *, status: str | None = None, limit: int | None = None
) -> dict[str, Any]:
    try:
        jobs = service.list_jobs(status=status, limit=limit)
    except ValueError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": {"jobs": jobs}}


def api_cancel_generation(service: BuildService, job_id: str) -> dict[str, Any]:
    try:
        status = service.cancel_generation(job_id)
    except KeyError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": status}


def api_get_artifacts(service: BuildService, job_id: str) -> dict[str, Any]:
    try:
        artifacts = service.get_artifacts(job_id)
    except KeyError as err:
        return _error_payload("input_validation_error", str(err))
    except RuntimeError as err:
        msg = str(err)
        if "succeeded jobs" in msg:
            return _error_payload("generation_failure", msg)
        return _error_payload("export_failure", msg)
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": artifacts}


def api_get_run_metadata(service: BuildService, job_id: str) -> dict[str, Any]:
    try:
        metadata = service.get_run_metadata(job_id)
    except KeyError as err:
        return _error_payload("input_validation_error", str(err))
    except RuntimeError as err:
        return _error_payload("generation_failure", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": metadata}


def api_get_latest_job_summary(service: BuildService) -> dict[str, Any]:
    try:
        summary = service.get_latest_job_summary()
    except RuntimeError as err:
        return _error_payload("generation_failure", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": summary}


def api_get_job_stats(service: BuildService) -> dict[str, Any]:
    try:
        stats = service.get_job_stats()
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": stats}


def api_get_dashboard_snapshot(service: BuildService) -> dict[str, Any]:
    try:
        snapshot = service.get_dashboard_snapshot()
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": snapshot}


def api_get_recent_failures(service: BuildService, *, limit: int = 5) -> dict[str, Any]:
    try:
        failures = service.get_recent_failures(limit=limit)
    except ValueError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": {"failures": failures}}


def api_get_home_snapshot(
    service: BuildService, *, recent_failure_limit: int = 5
) -> dict[str, Any]:
    try:
        snapshot = service.get_home_snapshot(recent_failure_limit=recent_failure_limit)
    except ValueError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": snapshot}


def api_get_job_timeline(service: BuildService, *, limit: int = 20) -> dict[str, Any]:
    try:
        timeline = service.get_job_timeline(limit=limit)
    except ValueError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": {"timeline": timeline}}


def api_get_ui_bootstrap(
    service: BuildService, *, recent_failure_limit: int = 5, timeline_limit: int = 20
) -> dict[str, Any]:
    try:
        data = service.get_ui_bootstrap(
            recent_failure_limit=recent_failure_limit,
            timeline_limit=timeline_limit,
        )
    except ValueError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": data}


def api_get_job_details(service: BuildService, job_id: str) -> dict[str, Any]:
    try:
        details = service.get_job_details(job_id)
    except KeyError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": details}


def api_retry_job(service: BuildService, job_id: str) -> dict[str, Any]:
    try:
        new_job_id = service.retry_job(job_id)
    except KeyError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": {"job_id": new_job_id}}


def api_prune_jobs(service: BuildService, *, keep_recent: int = 100) -> dict[str, Any]:
    try:
        result = service.prune_jobs(keep_recent=keep_recent)
    except ValueError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": result}


def api_delete_job(service: BuildService, job_id: str) -> dict[str, Any]:
    try:
        result = service.delete_job(job_id)
    except KeyError as err:
        return _error_payload("input_validation_error", str(err))
    except RuntimeError as err:
        return _error_payload("generation_failure", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": result}


def api_get_active_jobs(service: BuildService, *, limit: int | None = None) -> dict[str, Any]:
    try:
        jobs = service.get_active_jobs(limit=limit)
    except ValueError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": {"jobs": jobs}}


def api_clear_finished_jobs(service: BuildService) -> dict[str, Any]:
    try:
        result = service.clear_finished_jobs()
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": result}


def api_delete_jobs(service: BuildService, job_ids: list[str]) -> dict[str, Any]:
    try:
        result = service.delete_jobs(job_ids)
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": result}


def api_get_backend_capabilities(service: BuildService) -> dict[str, Any]:
    try:
        data = service.get_backend_capabilities()
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": data}


def api_get_backend_health(service: BuildService) -> dict[str, Any]:
    try:
        data = service.get_backend_health()
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": data}


def api_get_contract_summary(service: BuildService) -> dict[str, Any]:
    try:
        data = service.get_contract_summary()
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": data}


def api_cancel_all_active_jobs(service: BuildService) -> dict[str, Any]:
    try:
        data = service.cancel_all_active_jobs()
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": data}
