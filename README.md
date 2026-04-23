# RoboForgeAI (MECHA)

From spec to CAD in minutes. Define parts and simple assembly placement in YAML, then generate STEP/STL parts plus an assembly transform CSV.

## Compatibility

- Supported runtime: **Python 3.11**
- CAD stack is pinned for reliability on Python 3.11.
- Python 3.13 is not yet supported by the current dependency set.

## Quickstart

```bash
# Windows
py -3.11 -m venv .venv
.\.venv\Scripts\activate
python -m pip install -e .

# Build the example project
mmcad examples/bracket_demo.yaml --outdir build
```

Outputs are written to `build/<project>/`:
- `<part>.step`
- `<part>.stl`
- `assembly.csv`

## Spec Schema (Current)

Top-level fields:
- `project` (optional): output folder name; defaults to spec file name
- `parts` (required): list of part objects
- `assemblies` (optional): assembly placement list

Supported part types:

1) `plate`
- Required: `type`, `name`, `width`, `height`, `thickness`
- Optional: `holes`
- `holes` items:
  - `x` (default `0`)
  - `y` (default `0`)
  - `diameter` (required; legacy `d` is accepted for compatibility)
  - Coordinates are relative to plate center.

2) `shaft`
- Required: `type`, `name`, `diameter`, `length`

3) `link`
- Required: `type`, `name`, `length`, `width`, `thickness`
- Optional: `end_hole_d` (default `8`)

Assembly items:
- `assemblies` is a list of objects with:
  - `name`
  - `items` (list)
- `items` entries:
  - `part`: must reference a defined part name
  - `transform`: `[tx, ty, tz, rx, ry, rz]` (exactly 6 numbers)

## Example Spec

```yaml
project: bracket_demo
parts:
  - type: plate
    name: base
    width: 100
    height: 60
    thickness: 6
    holes:
      - {x: -30, y: -10, diameter: 5}
      - {x: 30, y: -10, diameter: 5}
  - type: shaft
    name: pin
    diameter: 8
    length: 40
assemblies:
  - name: assy
    items:
      - {part: base, transform: [0, 0, 0, 0, 0, 0]}
      - {part: pin, transform: [0, 0, 6, 0, 0, 0]}
```

## FreeCAD Export

To produce a FreeCAD assembly and STEP assembly export, run from a FreeCAD Python environment:

```bash
python -c "from mmcad.export.freecad_export import export_assembly; export_assembly('build/bracket_demo/assembly.csv', 'build/bracket_demo', 'build/bracket_demo')"
```

This creates:
- `assembly.FCStd`
- `assembly.step`

## Project Layout

```bash
src/mmcad/cli.py
src/mmcad/parts/basic.py
src/mmcad/export/freecad_export.py
examples/bracket_demo.yaml
tests/
```

## Contributing

See `CONTRIBUTING.md` and `docs/dev_setup.md`.
