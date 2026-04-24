# RoboForgeAI Requirements v2

## Purpose

Define the product requirements for a practical, market-valid first product direction:
an AI-assisted mechanical design tool focused on enclosures, mounts, and adapters.

## Product Direction

RoboForgeAI starts as an **AI Enclosure and Mount Specialist** for non-expert users.

It does not start as a fully autonomous "design anything" CAD AI.

## Problem Statement

Teams repeatedly need custom mechanical parts (enclosures, mounting brackets, adapter plates, simple fixtures), but current workflows are:

- slow for non-CAD users
- expensive in engineering hours
- error-prone for manufacturability and fit

## Target Users (Initial)

- Hardware startup engineers with limited ME bandwidth
- University/research lab builders
- Automation/integration technicians

## Jobs To Be Done

1. "Given these components, generate an enclosure that fits and is printable."
2. "Generate a mount/adapter with valid fastener holes and tolerances."
3. "Export manufacturing-ready CAD quickly with clear assumptions/warnings."

## In Scope (V1)

- No-terminal workflow (guided app UI)
- Component-aware design inputs
- Rule-based generation for:
  - enclosures
  - mounting brackets/plates
  - simple adapters
- Rule checks:
  - minimum wall thickness
  - basic clearances
  - hole/fastener compatibility
  - printability heuristics (FDM-first)
- Export outputs:
  - STEP
  - STL
  - design report (assumptions + warnings)

## Out of Scope (V1)

- Full robot/system architecture generation
- Fully autonomous "design anything" generation
- Full multiphysics simulation
- Multi-CAD plugin suite (Fusion/SolidWorks/Inventor) in the first release

## Functional Requirements

- User can create/open/save a project.
- User can select components from a library and enter constraints.
- User can generate at least one valid design candidate.
- User can edit key generated parameters before export.
- System blocks invalid configurations with actionable error messages.
- User can export STEP/STL and a design report.

## Non-Functional Requirements

- Deterministic outputs for equivalent inputs.
- Typical generation latency under 60 seconds for V1 templates.
- Errors readable by non-technical users.
- Rule and output traceability through versioned reporting.

## Trust and Safety Requirements

Every exported design report must include:

- input assumptions
- applied rule checks
- pass/fail results
- warnings and unresolved risks
- "requires human verification" disclaimer

RoboForgeAI must not claim certified engineering approval in V1.

## Initial KPI Targets (0-6 months)

- Time-to-first-valid-design: under 10 minutes (new user)
- First-pass fit success (pilot reported): >= 70%
- Manual CAD time reduction: >= 50%
- Export completion rate: >= 85%
- Active pilot teams: >= 10

## Validation Requirements Before Full Build

Run 15-20 user interviews across target segments and confirm:

- problem frequency is high
- current process is costly enough
- proposed output format is usable
- willingness to trial/pay exists

Proceed only if these assumptions are validated.