from __future__ import annotations

from typing import Any

from mmcad.app_service import BuildService
from mmcad.project_io import (
    ProjectError,
    create_project_data,
    load_project,
    save_project,
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


def api_get_job_status(service: BuildService, job_id: str) -> dict[str, Any]:
    try:
        status = service.get_job_status(job_id)
    except KeyError as err:
        return _error_payload("input_validation_error", str(err))
    except Exception as err:  # pragma: no cover - defensive boundary
        return _error_payload("unknown_error", str(err))
    return {"ok": True, "data": status}


def api_list_jobs(service: BuildService) -> dict[str, Any]:
    try:
        jobs = service.list_jobs()
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
