# IPC Flow Diagram

This diagram shows how UI/IPC calls move through API wrappers, job orchestration, and CAD generation.

```mermaid
sequenceDiagram
    autonumber
    participant UI as UI / IPC Caller
    participant API as ipc_api.py
    participant SVC as BuildService (app_service.py)
    participant TH as Worker Thread
    participant CLI as build() (cli.py)
    participant IO as project_io.py

    alt Start from spec path
        UI->>API: api_start_generation(service, spec_path, outdir)
        API->>SVC: start_generation(spec_path, outdir)
    else Start from project file
        UI->>API: api_start_generation_from_project(service, project_path)
        API->>SVC: start_generation_from_project(project_path)
        SVC->>IO: load_project(project_path)
        IO-->>SVC: validated project dict
        SVC->>SVC: start_generation(spec_path, outdir)
    end

    SVC->>SVC: create JobRecord(status="queued")
    SVC->>TH: spawn _run_job(job_id)
    SVC-->>API: job_id
    API-->>UI: {ok: true, data: {job_id}}

    TH->>SVC: mark running + started_at
    TH->>CLI: build(spec_path, outdir)
    CLI-->>TH: project_outdir or exception

    alt build success
        TH->>SVC: mark succeeded + project_outdir + finished_at
    else build failure
        TH->>SVC: mark failed + error + finished_at
    end

    loop Poll status
        UI->>API: api_get_job_status(service, job_id)
        API->>SVC: get_job_status(job_id)
        SVC-->>API: JobRecord as dict
        API-->>UI: {ok: true, data: status}
    end

    UI->>API: api_get_artifacts(service, job_id)
    API->>SVC: get_artifacts(job_id)
    SVC-->>API: files list (if succeeded)
    API-->>UI: {ok: true, data: artifacts}
```

## Keep This Updated

When adding new behavior, update this diagram in the same PR if any of these change:

- New IPC entry points in `ipc_api.py`
- New service methods or job state transitions in `app_service.py`
- New project-loading paths in `project_io.py`
- New generation/export stages in `cli.py` (or modules called by it)
- New error categories returned to IPC clients
