from __future__ import annotations

from pathlib import Path


def _load_spec_module():
    namespace = {"__file__": str(Path("packaging/pyinstaller.spec").resolve())}
    exec(Path("packaging/pyinstaller.spec").read_text(encoding="utf-8"), namespace)
    return namespace


def test_pyinstaller_datas_cover_current_i18n_assets() -> None:
    module = _load_spec_module()

    datas = {tuple(item) for item in module["DATAS"]}
    expected_assets = {
        (str(path.resolve()), path.parent.as_posix())
        for path in sorted(Path("eodinga/i18n").glob("*.json"))
    }

    assert expected_assets <= datas
    assert (str(Path("LICENSE").resolve()), ".") in datas
