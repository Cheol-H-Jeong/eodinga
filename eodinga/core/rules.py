from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

from pathspec import PathSpec

from eodinga.common import PathRules
from eodinga.core.fs import DENYLIST, absolute_safe, resolve_safe


class CompiledRules(NamedTuple):
    include_spec: PathSpec
    exclude_spec: PathSpec
    root_absolute: Path | None
    explicitly_scoped: bool


def _normalize(path: Path) -> str:
    return str(path).replace("\\", "/")


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


@lru_cache(maxsize=256)
def _compile_rules(
    include: tuple[str, ...],
    exclude: tuple[str, ...],
    root_text: str | None,
) -> CompiledRules:
    root = Path(root_text) if root_text is not None else None
    return CompiledRules(
        include_spec=_compile(include),
        exclude_spec=_compile(exclude),
        root_absolute=absolute_safe(root) if root is not None else None,
        explicitly_scoped=include != ("**/*",),
    )


def _matches_default_denylist(path: Path) -> bool:
    normalized = _normalize(resolve_safe(path))
    for pattern in _expanded_denylist():
        prefix = pattern.replace("\\", "/").rstrip("/")
        if normalized == prefix or normalized.startswith(f"{prefix}/"):
            return True
    return False


def _matches(spec: PathSpec, absolute_path: Path, root_absolute: Path | None) -> bool:
    normalized = _normalize(absolute_path)
    candidates = [normalized]
    if root_absolute is not None:
        try:
            candidates.append(_normalize(absolute_path.relative_to(root_absolute)))
        except ValueError:
            pass
    return any(spec.match_file(candidate) for candidate in candidates)


def _is_within_root(absolute_path: Path, root_absolute: Path | None) -> bool:
    if root_absolute is None:
        return False
    try:
        absolute_path.relative_to(root_absolute)
    except ValueError:
        return False
    return True


def should_index(path: Path, rules: PathRules) -> bool:
    compiled = _compile_rules(
        rules.include,
        rules.exclude,
        str(rules.root) if rules.root is not None else None,
    )
    absolute_path = absolute_safe(path)
    explicitly_included = compiled.explicitly_scoped and _matches(
        compiled.include_spec, absolute_path, compiled.root_absolute
    )
    if _matches(compiled.exclude_spec, absolute_path, compiled.root_absolute):
        return False
    if _matches_default_denylist(path) and not explicitly_included and not _is_within_root(
        absolute_path, compiled.root_absolute
    ):
        return False
    return True
