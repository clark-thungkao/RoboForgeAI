# Release Checklist

Use this checklist before creating a new release tag.

1. Ensure branch is up to date with `main`.
2. Run local quality gates:
  - `ruff check src tests`
  - `pytest`
  - `mmcad examples/bracket_demo.yaml --outdir build`
3. Confirm CI is green on the release commit.
4. Update version in `pyproject.toml` if needed.
5. Update IPC flow diagram in `docs/ipc_flow.md` when flow/API behavior changed.
6. Update release notes/changelog summary.
7. Create and push release tag.