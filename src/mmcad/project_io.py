from __future__ import annotations

import json
from pathlib import Path


PROJECT_SCHEMA_VERSION = 1


class ProjectError(ValueError):
    """Raised when a .rfa.json project is invalid."""


def _require_fields(data: dict, fields: tuple[str, ...], where: str) -> None:
    missing = [field for field in fields if field not in data]
    if missing:
        raise ProjectError(f"Missing required field(s) {missing} in {where}.")


def create_project_data(
    *,
    name: str,
    spec_path: str,
    outdir: str = "build",
    generation_profile: dict | None = None,
    outputs: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "project": {"name": name},
        "inputs": {"spec_path": spec_path},
        "generation_profile": generation_profile or {"outdir": outdir},
        "outputs": outputs or {},
        "metadata": metadata or {},
    }


def validate_project_data(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ProjectError("Project content must be a JSON object.")
    _require_fields(
        data,
        ("schema_version", "project", "inputs", "generation_profile", "outputs", "metadata"),
        "project root",
    )
    if data["schema_version"] != PROJECT_SCHEMA_VERSION:
        raise ProjectError(
            f"Unsupported schema_version {data['schema_version']}; expected {PROJECT_SCHEMA_VERSION}."
        )
    if not isinstance(data["project"], dict):
        raise ProjectError("'project' must be an object.")
    _require_fields(data["project"], ("name",), "'project'")
    if not isinstance(data["inputs"], dict):
        raise ProjectError("'inputs' must be an object.")
    _require_fields(data["inputs"], ("spec_path",), "'inputs'")
    if not isinstance(data["generation_profile"], dict):
        raise ProjectError("'generation_profile' must be an object.")
    _require_fields(data["generation_profile"], ("outdir",), "'generation_profile'")
    if not isinstance(data["outputs"], dict):
        raise ProjectError("'outputs' must be an object.")
    if not isinstance(data["metadata"], dict):
        raise ProjectError("'metadata' must be an object.")
    return data


def save_project(path: str, data: dict) -> None:
    project_path = Path(path)
    validate_project_data(data)
    project_path.parent.mkdir(parents=True, exist_ok=True)
    project_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_project(path: str) -> dict:
    project_path = Path(path)
    if not project_path.exists():
        raise ProjectError(f"Project file not found: {path}")
    try:
        data = json.loads(project_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as err:
        raise ProjectError(f"Project file is not valid JSON: {path}") from err
    return validate_project_data(data)
