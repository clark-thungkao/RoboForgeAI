# UI Flow (Desktop Scaffold)

This document explains the current desktop UI behavior in simple terms.

## Goal

Let a non-technical user run the core design pipeline without using terminal commands.

## Current Screen

The current `mmcad-gui` window has:

- **Spec input**: choose a YAML file
- **Output input**: choose where generated files go
- **Generate button**: start a build job
- **Status line**: shows current job state
- **Summary line**: backend health and job counters
- **Artifacts list**: output files from succeeded jobs
- **Job history**: recent jobs
- **Job details**: details of selected job
- **Job action buttons**:
  - `Refresh`
  - `Retry`
  - `Cancel`
  - `Delete`
  - `Clear Finished`

## User Flow

1. User selects spec file.
2. User confirms output directory.
3. User clicks `Generate`.
4. UI starts job and polls status.
5. On success, UI lists artifacts.
6. User can inspect history and details.
7. User can run cleanup or control actions from history panel.

## Backend Calls Used by UI

- Start generation: `api_start_generation`
- Poll one job: `api_get_job_status`
- Read artifacts: `api_get_artifacts`
- List recent jobs: `api_list_jobs`
- Read selected job details: `api_get_job_details`
- Retry selected job: `api_retry_job`
- Cancel selected job: `api_cancel_generation`
- Delete selected job: `api_delete_job`
- Clear finished jobs: `api_clear_finished_jobs`
- Dashboard counts: `api_get_backend_health`, `api_get_job_stats`

## Known Gaps (Next)

- Better visual status cues (colors/icons)
- Disable conflicting buttons during active operations
- Cleaner error panel (instead of message-only popups)
- Form mode for non-YAML users (guided template input)
- Optional 3D preview panel

