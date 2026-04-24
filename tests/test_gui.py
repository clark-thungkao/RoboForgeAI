from __future__ import annotations

from mmcad.gui import _default_outdir


def test_default_outdir_uses_spec_parent_build_folder() -> None:
    result = _default_outdir("examples/bracket_demo.yaml")
    normalized = result.replace("\\", "/")
    assert normalized.endswith("examples/build")

