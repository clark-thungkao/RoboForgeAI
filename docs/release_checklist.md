# Release Checklist

Use this checklist before creating a new release tag.

1. Ensure branch is up to date with `main`.
2. Run local quality gates:
  - `ruff check src tests`
  - `pytest`
  - `mmcad examples/bracket_demo.yaml --outdir build`
3. Confirm CI is green on the release commit.
4. Update version in `pyproject.toml` if needed.
5. Update release notes/changelog summary.
6. Create and push release tag.