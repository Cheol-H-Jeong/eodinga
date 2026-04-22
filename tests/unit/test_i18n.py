from __future__ import annotations

from eodinga.i18n import load_catalog, t


def test_catalogs_have_same_keys() -> None:
    assert set(load_catalog("en")) == set(load_catalog("ko"))


def test_missing_key_falls_back_to_key() -> None:
    assert t("missing.key", language="ko") == "missing.key"

