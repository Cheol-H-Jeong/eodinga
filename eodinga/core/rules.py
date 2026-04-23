from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pathspec import PathSpec

from eodinga.common import PathRules
from eodinga.core.fs import DENYLIST, absolute_safe, resolve_safe


def _normalize(path: Path) -> str:
    return str(path).replace("\\", "/")


@lru_cache(maxsize=128)
def _compile(patterns: tuple[str, ...]) -> PathSpec:
    normalized = [pattern.replace("\\", "/") for pattern in patterns]
    return PathSpec.from_lines("gitignore", normalized)


@lru_cache(maxsize=1)
def _expanded_denylist() -> tuple[str, ...]:
    home = Path.home()
    system_root = Path.home().drive + "/Windows" if Path.home().drive else "C:/Windows"
    expanded: list[str] = []
    for raw in DENYLIST:
        if raw == "%SystemRoot%":
            expanded.append(system_root)
        elif raw.startswith("~/"):
            expanded.append(_normalize(home / raw[2:]))
        else:
            expanded.append(raw)
    return tuple(expanded)


def _matches_default_denylist(path: Path) -> bool:
    normalized = _normalize(resolve_safe(path))
    for pattern in _expanded_denylist():
        prefix = pattern.replace("\\", "/").rstrip("/")
        if normalized == prefix or normalized.startswith(f"{prefix}/"):
            return True
    return False


def _matches(spec: PathSpec, path: Path, root: Path | None) -> bool:
    normalized = _normalize(absolute_safe(path))
    candidates = [normalized]
    if root is not None:
        try:
            candidates.append(_normalize(absolute_safe(path).relative_to(absolute_safe(root))))
        except ValueError:
            pass
    return any(spec.match_file(candidate) for candidate in candidates)


def _is_within_root(path: Path, root: Path | None) -> bool:
    if root is None:
        return False
    try:
        absolute_safe(path).relative_to(absolute_safe(root))
    except ValueError:
        return False
    return True


def should_index(path: Path, rules: PathRules) -> bool:
    include_spec = _compile(rules.include)
    exclude_spec = _compile(rules.exclude)
    explicitly_included = rules.include != ("**/*",) and _matches(include_spec, path, rules.root)
    if _matches(exclude_spec, path, rules.root):
        return False
    if _matches_default_denylist(path) and not explicitly_included and not _is_within_root(path, rules.root):
        return False
    return True
