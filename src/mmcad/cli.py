import argparse
import json
import os
import sys

import cadquery as cq
import yaml

from mmcad.parts.basic import link_rect, plate, shaft


class SpecError(ValueError):
    """Raised when a build spec is invalid."""


def _require_fields(data: dict, fields: tuple[str, ...], where: str) -> None:
    missing = [name for name in fields if name not in data]
    if missing:
        raise SpecError(f"Missing required field(s) {missing} in {where}.")


def _normalize_holes(holes: list[dict], where: str) -> list[dict]:
    normalized = []
    for idx, hole in enumerate(holes):
        if not isinstance(hole, dict):
            raise SpecError(f"Hole entry {idx} in {where} must be a mapping.")
        if "diameter" not in hole and "d" not in hole:
            raise SpecError(f"Hole entry {idx} in {where} must include 'diameter'.")
        normalized.append(
            {
                "x": float(hole.get("x", 0.0)),
                "y": float(hole.get("y", 0.0)),
                "diameter": float(hole.get("diameter", hole.get("d"))),
            }
        )
    return normalized


def _make_part(part: dict) -> tuple[str, cq.Workplane]:
    _require_fields(part, ("type", "name"), "part definition")
    part_type = part["type"]
    name = part["name"]

    if part_type == "plate":
        _require_fields(part, ("width", "height", "thickness"), f"plate part '{name}'")
        holes = _normalize_holes(part.get("holes", []), f"plate part '{name}'")
        model = plate(part["width"], part["height"], part["thickness"], holes)
        return name, model
    if part_type == "shaft":
        _require_fields(part, ("diameter", "length"), f"shaft part '{name}'")
        return name, shaft(part["diameter"], part["length"])
    if part_type == "link":
        _require_fields(part, ("length", "width", "thickness"), f"link part '{name}'")
        return name, link_rect(part["length"], part["width"], part["thickness"], part.get("end_hole_d", 8))
    raise SpecError(f"Unknown part type '{part_type}' for part '{name}'.")


def _load_spec(spec_path: str) -> dict:
    if not os.path.exists(spec_path):
        raise SpecError(f"Spec file not found: {spec_path}")
    try:
        with open(spec_path, "r", encoding="utf-8") as handle:
            spec = yaml.safe_load(handle)
    except yaml.YAMLError as err:
        raise SpecError(f"Failed to parse YAML in '{spec_path}': {err}") from err

    if not isinstance(spec, dict):
        raise SpecError("Top-level YAML must be a mapping/object.")
    if not isinstance(spec.get("parts"), list) or not spec["parts"]:
        raise SpecError("Spec must include a non-empty 'parts' list.")
    return spec


def _write_assembly_csv(spec: dict, output_path: str, part_names: set[str]) -> None:
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("assembly,part,tx,ty,tz,rx,ry,rz\n")
        assemblies = spec.get("assemblies", [])
        if not assemblies:
            for part_name in sorted(part_names):
                handle.write(f"default,{part_name},0,0,0,0,0,0\n")
            return

        for assembly in assemblies:
            _require_fields(assembly, ("name", "items"), "assembly definition")
            if not isinstance(assembly["items"], list):
                raise SpecError(f"Assembly '{assembly['name']}' items must be a list.")
            for item in assembly["items"]:
                _require_fields(item, ("part", "transform"), f"assembly '{assembly['name']}' item")
                if item["part"] not in part_names:
                    raise SpecError(
                        f"Assembly '{assembly['name']}' references unknown part '{item['part']}'."
                    )
                transform = item["transform"]
                if not isinstance(transform, list) or len(transform) != 6:
                    raise SpecError(
                        f"Assembly '{assembly['name']}' part '{item['part']}' requires transform of 6 numbers."
                    )
                tx, ty, tz, rx, ry, rz = [float(v) for v in transform]
                handle.write(f"{assembly['name']},{item['part']},{tx},{ty},{tz},{rx},{ry},{rz}\n")


def _write_design_report(spec: dict, output_path: str, part_names: list[str], outputs: list[str]) -> None:
    report = {
        "report_version": 1,
        "project": spec.get("project"),
        "parts": part_names,
        "assumptions": [
            "Geometry is generated from deterministic parametric rules.",
            "Output must be reviewed and verified before manufacturing use.",
        ],
        "warnings": [],
        "outputs": outputs,
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")


def build(spec_path: str, outdir: str = "build") -> str:
    spec = _load_spec(spec_path)
    project_name = spec.get("project") or os.path.splitext(os.path.basename(spec_path))[0]
    project_outdir = os.path.join(outdir, project_name)
    os.makedirs(project_outdir, exist_ok=True)

    part_names: set[str] = set()
    for part in spec["parts"]:
        name, model = _make_part(part)
        if name in part_names:
            raise SpecError(f"Duplicate part name '{name}' in spec.")
        part_names.add(name)
        cq.exporters.export(model, os.path.join(project_outdir, f"{name}.step"))
        cq.exporters.export(model, os.path.join(project_outdir, f"{name}.stl"))

    asm_path = os.path.join(project_outdir, "assembly.csv")
    _write_assembly_csv(spec, asm_path, part_names)
    output_files = sorted(file for file in os.listdir(project_outdir) if os.path.isfile(os.path.join(project_outdir, file)))
    report_path = os.path.join(project_outdir, "design_report.json")
    _write_design_report(spec, report_path, sorted(part_names), output_files + ["design_report.json"])
    return project_outdir


def main() -> int:
    parser = argparse.ArgumentParser(description="MECHA CLI")
    parser.add_argument("spec", help="Path to YAML spec")
    parser.add_argument("--outdir", default="build", help="Output directory (default: build)")
    args = parser.parse_args()

    try:
        project_outdir = build(args.spec, args.outdir)
    except SpecError as err:
        print(f"Spec error: {err}", file=sys.stderr)
        return 2
    except Exception as err:  # pragma: no cover - guard for unexpected runtime errors
        print(f"Build failed: {err}", file=sys.stderr)
        return 1

    print(f"Done. Files in {project_outdir}/ (STEP, STL, assembly.csv, and design_report.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
