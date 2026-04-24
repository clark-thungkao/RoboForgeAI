from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Callable
from uuid import uuid4

from mmcad.cli import build
from mmcad.project_io import load_project

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


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class BuildService:
    """Backend contract for UI IPC integration."""

    def __init__(self, build_fn: BuildFn | None = None) -> None:
        self._build_fn = build_fn or build
        self._jobs: dict[str, JobRecord] = {}
        self._lock = Lock()

    def start_generation(self, spec_path: str, outdir: str) -> str:
        job_id = str(uuid4())
        record = JobRecord(
            job_id=job_id,
            spec_path=spec_path,
            outdir=outdir,
            status="queued",
            created_at=_utc_now(),
        )
        with self._lock:
            self._jobs[job_id] = record

        worker = Thread(target=self._run_job, args=(job_id,), daemon=True)
        worker.start()
        return job_id

    def start_generation_from_project(self, project_path: str) -> str:
        project = load_project(project_path)
        spec_path = str(project["inputs"]["spec_path"])
        outdir = str(project["generation_profile"]["outdir"])
        return self.start_generation(spec_path, outdir)

    def get_job_status(self, job_id: str) -> dict:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise KeyError(f"Unknown job_id: {job_id}")
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

    def _run_job(self, job_id: str) -> None:
        with self._lock:
            record = self._jobs[job_id]
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
            done.status = "succeeded"
            done.finished_at = _utc_now()
            done.project_outdir = output_dir
