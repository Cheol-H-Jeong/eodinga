from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_stage_runtime_module():
    spec = importlib.util.spec_from_file_location("stage_runtime", Path("packaging/linux/stage_runtime.py"))
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stage_runtime_copies_package_tree_without_bytecode(tmp_path: Path) -> None:
    module = _load_stage_runtime_module()
    package_root = Path("eodinga")
    pycache_dir = package_root / "__pycache__"
    pycache_dir.mkdir(exist_ok=True)
    pyc_path = pycache_dir / "staging-test.pyc"
    pyc_path.write_bytes(b"bytecode")
    runtime_root = tmp_path / "runtime"
    try:
        assert module.main([str(runtime_root)]) == 0
    finally:
        pyc_path.unlink(missing_ok=True)
        try:
            pycache_dir.rmdir()
        except OSError:
            pass

    staged_package = runtime_root / "eodinga"
    assert staged_package.exists()
    assert (staged_package / "__init__.py").exists()
    assert (staged_package / "__main__.py").exists()
    assert (staged_package / "i18n" / "en.json").exists()
    assert not (staged_package / "__pycache__").exists()
