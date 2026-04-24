# RoboForgeAI 24-Month Roadmap

## Strategy

- Product-first direction: desktop app for non-technical users
- Technical core: deterministic CAD generation + engineering rule checks
- AI role: intent-to-spec assistant, not uncontrolled geometry generator

## Milestone 0 (Weeks 1-4): Foundation Decisions

Lock architecture decisions before feature expansion.

- UI stack decision
- Local vs cloud AI boundary
- Project file schema/versioning
- Preview/rendering approach
- Telemetry/privacy defaults

Decision record:

- `docs/adr_001_m1_architecture.md`
- `docs/adr_002_component_library.md`
- `docs/adr_003_rule_engine_policy.md`
- `docs/adr_004_ai_governance.md`
- `docs/adr_005_pilot_gtm_validation.md`

### Exit Criteria

- Architecture Decision Record (ADR) approved
- One reference flow implemented from input to generated output
- Team can run local dev and CI from docs alone

## Milestone 1 (Months 0-3): No-Terminal MVP

- Guided project creation workflow
- Form-based replacement for direct YAML authoring
- One-click generation and export (STEP/STL/report)
- Session save/load

### Exit Criteria

- 10 pilot users run flow without terminal help
- > = 80% complete design-to-export flow
- Median time-to-first-export < 10 minutes

## Milestone 2 (Months 3-6): Reliability + UX

- Expand templates (enclosure, mount, adapter)
- Add validation UX and corrective suggestions
- Add export center and lightweight preview
- Add opt-in error telemetry

### Exit Criteria

- Support requests for setup/generation reduced release-over-release
- > = 85% successful exports in pilot cohort

## Milestone 3 (Months 6-9): AI Intent Assistant

- Prompt-to-parameter assistant
- Confidence and rationale display
- User approval before generation
- Rule checks for fastener fit/clearance/min thickness

### Exit Criteria

- > = 70% of AI-generated drafts accepted with <= 2 edits
- No increase in rule-check failure rate

## Milestone 4 (Months 9-12): Assembly Intelligence

- Multi-part constraints in UX
- Interference/clearance checks
- Design history and compare mode

### Exit Criteria

- Users can complete multi-part assemblies with validated transforms
- Regression suite covers assembly scenarios

## Milestone 5 (Months 12-18): Manufacturability Layer

- Process profiles (FDM, CNC, sheet-metal baseline)
- Material-aware rule suggestions
- Design review report for engineering handoff

### Exit Criteria

- Pilot users report reduced rework before fabrication
- Reports are used in design review meetings

## Milestone 6 (Months 18-24): Ecosystem Expansion

- CAD adapter strategy (start with one target CAD platform)
- Requirement decomposition to subsystem generation
- Shared libraries/permissions/auditability

### Exit Criteria

- First external CAD adapter in production pilot
- End-to-end traceability for generated designs

## What We Will Not Do Early

- Promise broad "any version" Python compatibility without CI proof
- Build all CAD plugins in parallel
- Claim full autonomous engineering design capability

