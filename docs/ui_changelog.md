# UI Changelog

Track UI-facing progress in plain language.

## 2026-04-24

- Added first desktop scaffold (`mmcad-gui`) with:
  - spec selection
  - output directory input
  - generation start
  - status polling
  - artifact listing

- Expanded UI with job history and selected job details:
  - history refresh
  - details panel bound to selected job

- Added history action controls:
  - retry selected job
  - cancel selected job
  - delete selected job
  - clear finished jobs

- Added live summary strip:
  - backend status
  - total jobs
  - active jobs
  - succeeded/failed/cancelled counters

- Added template quick start panel:
  - one-click prefill for example spec(s)
  - auto-fills output directory

- Added artifact quick actions:
  - open selected artifact file directly
  - open selected artifact's folder

- Added path usability and safety actions:
  - open spec folder directly from spec row
  - open output folder directly from action row
  - validate spec file exists before starting generation

- UI polish pass for checkpoint prep:
  - clearer labels for first-time users
  - better empty states in artifacts/history panels
  - quick-help strip with 4-step usage guidance
  - cleaner success/failure inline status messaging

- Added job history filtering tools:
  - status dropdown filter
  - text search by job id/spec path

