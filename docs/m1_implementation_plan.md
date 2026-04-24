# Milestone 1 Implementation Plan (0-3 Months)

## Goal

Deliver a no-terminal MVP where a non-technical user can create a simple project and export manufacturable CAD files.

## Scope

- Guided UI for V1 templates (enclosure, mount, adapter baseline)
- Deterministic generation using existing backend primitives
- Export pipeline for STEP/STL/report
- Local project save/load

## Proposed Technical Shape

## 1) App Shell

- Desktop app UI (final framework selection to be decided in ADR)
- Backend service layer wraps `mmcad` generation logic
- Async job model for generate/export operations

## 2) Domain Model

- Keep current canonical spec model from `src/mmcad/cli.py`
- Add stable app-facing project schema (versioned)
- Add migration strategy between schema versions

## 3) Rule Engine Baseline

- Build pre-export rule checks:
  - geometric sanity
  - wall thickness minimums
  - hole/fastener compatibility
  - transform validity

## 4) Output Contract

Each run must produce:

- STEP/STL outputs
- structured run metadata
- human-readable design report

## Workstreams

## Workstream A: Product and UX

- Define V1 user flow
- Define forms and defaults
- Define error/warning presentation

## Workstream B: Core Engine Integration

- Build app-to-engine adapter
- Add job state model (queued/running/failed/success)
- Harden error mapping to user-readable messages

## Workstream C: Validation and Reporting

- Implement rule-check pipeline hooks
- Generate report from checks and assumptions
- Add deterministic regression fixtures

## Workstream D: QA and Release Readiness

- Extend CI for app/API smoke checks
- Add end-to-end test for first-run flow
- Add installer/build artifact pipeline

## Acceptance Criteria

- New user can generate and export without terminal use.
- Median first-run completion under 10 minutes in pilot tests.
- Generation failures return actionable messages.
- CI passes on all required checks.

## Risks and Mitigations

- Risk: UI development slows engine progress.
  - Mitigation: Keep backend contract-first and UI thin.
- Risk: Early AI features destabilize MVP.
  - Mitigation: defer AI assistant to Milestone 3.
- Risk: quality drift in generated outputs.
  - Mitigation: add golden fixture tests for deterministic outputs.
