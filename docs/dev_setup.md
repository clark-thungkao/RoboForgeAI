# Developer Setup

## Prerequisites

- Python 3.11
- Git

## Local Setup

```bash
py -3.11 -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Common Commands

```bash
# Build demo outputs
mmcad examples/bracket_demo.yaml --outdir build

# Run checks
ruff check src tests
pytest
```

## FreeCAD Export Check (Optional)

Run this from a FreeCAD Python environment:

```bash
python -c "from mmcad.export.freecad_export import export_assembly; export_assembly('build/bracket_demo/assembly.csv', 'build/bracket_demo', 'build/bracket_demo')"
```
