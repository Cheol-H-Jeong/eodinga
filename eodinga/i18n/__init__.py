from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ("en", "ko")


@lru_cache(maxsize=len(SUPPORTED_LANGUAGES))
def load_catalog(language: str) -> dict[str, str]:
    selected = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    catalog_path = files("eodinga.i18n").joinpath(f"{selected}.json")
    return json.loads(catalog_path.read_text(encoding="utf-8"))


def t(key: str, language: str = DEFAULT_LANGUAGE, **kwargs: Any) -> str:
    catalog = load_catalog(language)
    fallback = load_catalog(DEFAULT_LANGUAGE)
    template = catalog.get(key, fallback.get(key, key))
    return template.format(**kwargs)

