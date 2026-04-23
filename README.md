## RoboForgeAI
> **From spec to robot CAD in minutes.** Define mechanisms in YAML/JSON and generate parametric parts & assemblies with exports for FreeCAD (`.FCStd`) and neutral STEP (Fusion 360, SolidWorks, Inventor).
To be updated with AI
> # 23.04.2026 - Rethinking the approach for more modular design -
[![CI]
[![License]
![Python]
![Status]

## TL;DR (Quickstart)
```bash
# Clone & setup
git clone https://github.com/USER/roboforgeai
cd roboforgeai
python -m venv .venv && source .venv/bin/activate  # (Windows: .venv\Scripts\activate)
pip install -e .

# Generate the demo assembly from a spec
mmcad examples/bracket_demo.yaml --outdir build

# Open outputs
TBA

```
First Idea of RoboForgeAI
Spec → CAD: go from a structured spec to editable CAD in one command.

Parametric: parts & assemblies are generated with parameters you can tweak.

Repeatable: deterministic builds—great for design reviews & CI.

Multi-CAD friendly: FreeCAD for native parametrics; STEP for everything else.

#Features

YAML/JSON → parts, subassemblies, constraints, BOM.

Exports: FreeCAD (.FCStd) and STEP; BOM as CSV/XLSX.

Pluggable builders (e.g., brackets, plates, linkages, gear trains).

Rule-based/AI helpers for quick mechanism variants (WIP).

Headless mode for CI runners.

# Example (minimal spec)
```bash
name: "demo_bracket_assembly"
units: mm
parts:
  - type: bracket
    name: L_bracket
    params: { w: 40, h: 40, t: 3, r: 4, hole_d: 5, pitch: 20 }
  - type: plate
    name: base_plate
    params: { w: 60, h: 60, t: 4, hole_d: 5, pattern: "2x2", pitch: 30 }
assembly:
  - mate: { type: planar, a: base_plate.top, b: L_bracket.bottom }
  - mate: { type: concentric, a: base_plate.hole_1, b: L_bracket.hole_1 }
outputs:
  - format: fcstd
    path: build/assembly.FCStd
  - format: step
    path: build/assembly.step
  - format: bom
    path: build/BOM.xlsx
```

# Installation
tba

## Python Version (Important)
Use **Python 3.11** for now.

- The current CAD dependency stack is reliable on Python 3.11.
- Python 3.13 may fail to install/run some pinned CAD packages in this project.

Windows example:
```bash
py -3.11 -m venv .venv
.\.venv\Scripts\activate
python -m pip install -e .
```

## How to Use MECHA
1. Create or edit a spec file (see `examples/bracket_demo.yaml`).
2. Run the CLI:

```bash
mmcad examples/bracket_demo.yaml --outdir build
```

3. Check generated files in `build/<project_name>/`:
   - part `.step`
   - part `.stl`
   - `assembly.csv`

### Export to FreeCAD / STEP Assembly
After generating parts and `assembly.csv`, run the FreeCAD export helper from a FreeCAD Python environment:

```bash
python -c "from mmcad.export.freecad_export import export_assembly; export_assembly('build/bracket_demo/assembly.csv', 'build/bracket_demo', 'build/bracket_demo')"
```

This creates:
- `assembly.FCStd` (FreeCAD native)
- `assembly.step` (neutral STEP)

#Multi-CAD Export

FreeCAD: native .FCStd keeps parametrics and constraints.

STEP: neutral .step for broad compatibility (no parametrics).

#Project Structure
```bash
roboforgeai/
  roboforge/
    cli.py              # CLI entry points
    core/               # schema, validators, units
    builders/           # parametric parts (bracket, plate, shaft, gears, etc.)
    assembly/           # mates/constraints → scene graph
    exporters/          # freecad.py, step.py, bom.py
examples/
  bracket_demo.yaml
media/
  demo.gif
```
#Windows/macOS/Linux notes (FreeCAD CLI)
```bash
Windows: ensure FreeCADCmd.exe is on PATH, e.g.

set "PATH=C:\Program Files\FreeCAD 0.21\bin;%PATH%"
FreeCADCmd --version
```
#Linux:

freecadcmd --version


#If RoboForgeAI can’t find FreeCAD automatically, set an env var before building:
```bash
# Point to your FreeCAD command
# Windows (PowerShell):
$env:ROBOFORGE_FREECAD_CMD="C:\Program Files\FreeCAD 0.21\bin\FreeCADCmd.exe"
# macOS/Linux (bash/zsh):
export ROBOFORGE_FREECAD_CMD="/Applications/FreeCAD.app/Contents/MacOS/FreeCADCmd"
```
#Troubleshooting
Tba

#First Roadmap (will be updated)

# 23.04.2026 - Rethinking the approach for more modular design -

Constraint graph visualizer (roboforge viz)
Direct Fusion 360 API export (parametric timeline)
Mechanism templates (linkages, belt drives, gear trains)
Tolerancing & fastener libraries
AI-assisted design suggestions from requirements text

#Contributing

PRs welcome! Please:
See CONTRIBUTING.md and docs/dev_setup.md. *tba

#Citation

If this project helps your research, please cite it. Add a CITATION.cff at repo root for GitHub to generate citation metadata.
