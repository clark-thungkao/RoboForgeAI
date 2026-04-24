# Contributing

Thanks for contributing to RoboForgeAI.

## Development Setup

Use Python 3.11 and follow `docs/dev_setup.md`.

## Pull Request Guidelines

- Keep changes focused and small.
- Add or update tests for behavior changes.
- Run locally before opening a PR:
  - `ruff check src tests`
  - `pytest`
  - `mmcad examples/bracket_demo.yaml --outdir build`

## Commit Style

Use concise, imperative commit subjects (e.g., `Fix CLI spec validation`).

## Reporting Bugs

Open an issue with:
- expected behavior
- actual behavior
- reproduction steps
- OS and Python version
