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
