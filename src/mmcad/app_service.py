from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock, Thread
from typing import Callable
from uuid import uuid4

from mmcad.cli import build
from mmcad.project_io import load_project, validate_project_data

BuildFn = Callable[[str, str], str]
BACKEND_API_VERSION = 1


@dataclass
class JobRecord:
    job_id: str
    spec_path: str
    outdir: str
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    project_outdir: str | None = None
    error: str | None = None
    cancel_requested: bool = False
    sequence: int = 0


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _ts_key(value: str | None) -> tuple[int, str]:
    if value is None:
        return (0, "")
    return (1, value)


class BuildService:
    """Backend contract for UI IPC integration."""

    def __init__(self, build_fn: BuildFn | None = None) -> None:
        self._build_fn = build_fn or build
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()
        self._sequence = 0

    def start_generation(self, spec_path: str, outdir: str) -> str:
        job_id = str(uuid4())
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
        record = JobRecord(
            job_id=job_id,
            spec_path=spec_path,
            outdir=outdir,
            status="queued",
            created_at=_utc_now(),
            sequence=sequence,
        )
        with self._lock:
            self._jobs[job_id] = record

        worker = Thread(target=self._run_job, args=(job_id,), daemon=True)
        worker.start()
        return job_id

    def start_generation_from_project(self, project_path: str) -> str:
        project = load_project(project_path)
        return self.start_generation_from_project_data(project)

    def start_generation_from_project_data(self, project_data: dict) -> str:
        project = validate_project_data(project_data)
        spec_path = str(project["inputs"]["spec_path"])
        outdir = str(project["generation_profile"]["outdir"])
        return self.start_generation(spec_path, outdir)

    def get_job_status(self, job_id: str) -> dict:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise KeyError(f"Unknown job_id: {job_id}")
            return asdict(record)

    def list_jobs(self, *, status: str | None = None, limit: int | None = None) -> list[dict]:
        if limit is not None and limit <= 0:
            raise ValueError("limit must be a positive integer.")
        with self._lock:
            jobs = [asdict(record) for record in self._jobs.values()]
        if status is not None:
            jobs = [item for item in jobs if item["status"] == status]
        jobs.sort(key=lambda item: item["sequence"], reverse=True)
        if limit is not None:
            jobs = jobs[:limit]
        return jobs

    def cancel_generation(self, job_id: str) -> dict:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise KeyError(f"Unknown job_id: {job_id}")
            if record.status in {"succeeded", "failed", "cancelled"}:
                return asdict(record)
            record.cancel_requested = True
            if record.status == "queued":
                record.status = "cancelled"
                record.finished_at = _utc_now()
                record.error = "Cancelled by user before start."
            return asdict(record)

    def get_artifacts(self, job_id: str) -> dict:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise KeyError(f"Unknown job_id: {job_id}")
            if record.status != "succeeded" or record.project_outdir is None:
                raise RuntimeError("Artifacts are only available for succeeded jobs.")
            project_outdir = record.project_outdir

        files = sorted(str(path) for path in Path(project_outdir).glob("*") if path.is_file())
        return {"job_id": job_id, "project_outdir": project_outdir, "files": files}

    def get_run_metadata(self, job_id: str) -> dict:
        status = self.get_job_status(job_id)
        if status["status"] != "succeeded":
            raise RuntimeError("Run metadata is only available for succeeded jobs.")
        artifacts = self.get_artifacts(job_id)
        project_outdir = Path(artifacts["project_outdir"])
        report_path = project_outdir / "design_report.json"
        report: dict | None = None
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))

        return {
            "job_id": job_id,
            "status": status["status"],
            "created_at": status["created_at"],
            "started_at": status["started_at"],
            "finished_at": status["finished_at"],
            "project_outdir": artifacts["project_outdir"],
            "artifacts": artifacts["files"],
            "design_report": report,
        }

    def get_latest_job_summary(self) -> dict:
        jobs = self.list_jobs(limit=1)
        if not jobs:
            raise RuntimeError("No jobs available.")
        latest = jobs[0]
        if latest["status"] == "succeeded":
            metadata = self.get_run_metadata(str(latest["job_id"]))
            return {"latest_job": latest, "run_metadata": metadata}
        return {"latest_job": latest, "run_metadata": None}

    def get_job_stats(self) -> dict:
        with self._lock:
            jobs = [asdict(record) for record in self._jobs.values()]
        if not jobs:
            return {
                "total": 0,
                "by_status": {
                    "queued": 0,
                    "running": 0,
                    "succeeded": 0,
                    "failed": 0,
                    "cancelled": 0,
                },
                "latest_job_id": None,
            }
        by_status = {"queued": 0, "running": 0, "succeeded": 0, "failed": 0, "cancelled": 0}
        latest = max(jobs, key=lambda item: item["sequence"])
        for job in jobs:
            status = str(job["status"])
            if status in by_status:
                by_status[status] += 1
        return {"total": len(jobs), "by_status": by_status, "latest_job_id": latest["job_id"]}

    def get_dashboard_snapshot(self) -> dict:
        stats = self.get_job_stats()
        latest_summary: dict | None = None
        if stats["total"] > 0:
            latest_summary = self.get_latest_job_summary()
        return {"stats": stats, "latest_summary": latest_summary}

    def get_recent_failures(self, *, limit: int = 5) -> list[dict]:
        if limit <= 0:
            raise ValueError("limit must be a positive integer.")
        failed_jobs = self.list_jobs(status="failed", limit=limit)
        return [
            {
                "job_id": job["job_id"],
                "created_at": job["created_at"],
                "finished_at": job["finished_at"],
                "spec_path": job["spec_path"],
                "error": job["error"],
            }
            for job in failed_jobs
        ]

    def get_home_snapshot(self, *, recent_failure_limit: int = 5) -> dict:
        if recent_failure_limit <= 0:
            raise ValueError("recent_failure_limit must be a positive integer.")
        return {
            "dashboard": self.get_dashboard_snapshot(),
            "recent_failures": self.get_recent_failures(limit=recent_failure_limit),
        }

    def get_job_timeline(self, *, limit: int = 20) -> list[dict]:
        if limit <= 0:
            raise ValueError("limit must be a positive integer.")
        jobs = self.list_jobs()
        events: list[dict] = []
        for job in jobs:
            events.append(
                {
                    "job_id": job["job_id"],
                    "type": "created",
                    "timestamp": job["created_at"],
                    "status": job["status"],
                    "spec_path": job["spec_path"],
                }
            )
            if job["started_at"] is not None:
                events.append(
                    {
                        "job_id": job["job_id"],
                        "type": "started",
                        "timestamp": job["started_at"],
                        "status": job["status"],
                        "spec_path": job["spec_path"],
                    }
                )
            if job["finished_at"] is not None:
                events.append(
                    {
                        "job_id": job["job_id"],
                        "type": "finished",
                        "timestamp": job["finished_at"],
                        "status": job["status"],
                        "spec_path": job["spec_path"],
                        "error": job["error"],
                    }
                )
        events.sort(key=lambda item: _ts_key(item["timestamp"]), reverse=True)
        return events[:limit]

    def get_ui_bootstrap(
        self, *, recent_failure_limit: int = 5, timeline_limit: int = 20
    ) -> dict:
        if recent_failure_limit <= 0:
            raise ValueError("recent_failure_limit must be a positive integer.")
        if timeline_limit <= 0:
            raise ValueError("timeline_limit must be a positive integer.")
        return {
            "home": self.get_home_snapshot(recent_failure_limit=recent_failure_limit),
            "timeline": self.get_job_timeline(limit=timeline_limit),
        }

    def get_job_details(self, job_id: str) -> dict:
        status = self.get_job_status(job_id)
        details = {"status": status, "artifacts": None, "run_metadata": None}
        if status["status"] == "succeeded":
            artifacts = self.get_artifacts(job_id)
            details["artifacts"] = artifacts
            details["run_metadata"] = self.get_run_metadata(job_id)
        return details

    def retry_job(self, job_id: str) -> str:
        status = self.get_job_status(job_id)
        spec_path = str(status["spec_path"])
        outdir = str(status["outdir"])
        return self.start_generation(spec_path, outdir)

    def prune_jobs(self, *, keep_recent: int = 100) -> dict:
        if keep_recent < 0:
            raise ValueError("keep_recent must be zero or a positive integer.")
        with self._lock:
            finished = [
                record
                for record in self._jobs.values()
                if record.status in {"succeeded", "failed", "cancelled"}
            ]
            finished.sort(key=lambda item: item.sequence, reverse=True)
            keep_ids = {record.job_id for record in finished[:keep_recent]}
            removed_ids: list[str] = []
            for record in finished[keep_recent:]:
                if record.job_id in keep_ids:
                    continue
                removed_ids.append(record.job_id)
                del self._jobs[record.job_id]
        return {"removed_count": len(removed_ids), "removed_job_ids": removed_ids}

    def delete_job(self, job_id: str) -> dict:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise KeyError(f"Unknown job_id: {job_id}")
            if record.status in {"queued", "running"}:
                raise RuntimeError("Cannot delete a queued or running job.")
            del self._jobs[job_id]
        return {"deleted_job_id": job_id}

    def get_active_jobs(self, *, limit: int | None = None) -> list[dict]:
        if limit is not None and limit <= 0:
            raise ValueError("limit must be a positive integer.")
        jobs = self.list_jobs()
        active = [job for job in jobs if job["status"] in {"queued", "running"}]
        if limit is not None:
            active = active[:limit]
        return active

    def clear_finished_jobs(self) -> dict:
        return self.prune_jobs(keep_recent=0)

    def get_backend_capabilities(self) -> dict:
        return {
            "api_version": BACKEND_API_VERSION,
            "features": [
                "project_lifecycle",
                "job_start",
                "job_status",
                "job_artifacts",
                "job_run_metadata",
                "job_summary",
                "job_stats",
                "job_timeline",
                "job_retry",
                "job_cleanup",
            ],
        }

    def get_backend_health(self) -> dict:
        stats = self.get_job_stats()
        return {
            "status": "ok",
            "api_version": BACKEND_API_VERSION,
            "active_jobs": stats["by_status"]["queued"] + stats["by_status"]["running"],
            "total_jobs": stats["total"],
        }

    def get_contract_summary(self) -> dict:
        return {
            "api_version": BACKEND_API_VERSION,
            "response_envelope": {"success": {"ok": True, "data": "..."}, "error": {"ok": False, "error": {"category": "...", "message": "..."}}},
            "error_categories": [
                "input_validation_error",
                "generation_failure",
                "export_failure",
                "unknown_error",
            ],
            "endpoint_groups": [
                "project_lifecycle",
                "generation_control",
                "job_introspection",
                "job_cleanup",
                "startup_bootstrap",
            ],
        }

    def delete_jobs(self, job_ids: list[str]) -> dict:
        deleted_job_ids: list[str] = []
        errors: list[dict] = []
        for job_id in job_ids:
            try:
                self.delete_job(job_id)
                deleted_job_ids.append(job_id)
            except (KeyError, RuntimeError) as err:
                errors.append({"job_id": job_id, "error": str(err)})
        return {
            "requested_count": len(job_ids),
            "deleted_count": len(deleted_job_ids),
            "deleted_job_ids": deleted_job_ids,
            "errors": errors,
        }

    def cancel_all_active_jobs(self) -> dict:
        active_jobs = self.get_active_jobs()
        cancelled_ids: list[str] = []
        for job in active_jobs:
            status = self.cancel_generation(str(job["job_id"]))
            if status["status"] == "cancelled" or status["cancel_requested"] is True:
                cancelled_ids.append(str(job["job_id"]))
        return {
            "requested_count": len(active_jobs),
            "cancelled_count": len(cancelled_ids),
            "cancelled_job_ids": cancelled_ids,
        }

    def _run_job(self, job_id: str) -> None:
        with self._lock:
            record = self._jobs[job_id]
            if record.cancel_requested:
                record.status = "cancelled"
                record.finished_at = _utc_now()
                record.error = "Cancelled by user before start."
                return
            record.status = "running"
            record.started_at = _utc_now()

        try:
            output_dir = self._build_fn(record.spec_path, record.outdir)
        except Exception as err:
            with self._lock:
                failed = self._jobs[job_id]
                failed.status = "failed"
                failed.finished_at = _utc_now()
                failed.error = str(err)
            return

        with self._lock:
            done = self._jobs[job_id]
            done.finished_at = _utc_now()
            if done.cancel_requested:
                done.status = "cancelled"
                done.error = "Cancelled by user during execution."
                done.project_outdir = None
                return
            done.status = "succeeded"
            done.project_outdir = output_dir
