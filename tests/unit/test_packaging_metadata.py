from __future__ import annotations

import importlib.util
from pathlib import Path

from eodinga import __version__


def _load_metadata_module():
    spec = importlib.util.spec_from_file_location("packaging_metadata", Path("packaging/metadata.py"))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_packaging_metadata_reports_synced_version() -> None:
    module = _load_metadata_module()

    assert module.read_project_version() == __version__
    assert module.read_package_version() == __version__
    assert module.require_synced_versions() == __version__


def test_packaging_metadata_renders_debian_control_from_template() -> None:
    module = _load_metadata_module()

    rendered = module.render_debian_control(version=__version__, arch="amd64")

    assert "Package: eodinga\n" in rendered
    assert f"Version: {__version__}\n" in rendered
    assert "Section: utils\n" in rendered
    assert "Priority: optional\n" in rendered
    assert "Architecture: amd64\n" in rendered
    assert "Maintainer: Cheol-H-Jeong\n" in rendered
    assert "Depends: python3 (>= 3.11)\n" in rendered
    assert "Description: Instant lexical file search for Windows and Linux\n" in rendered
