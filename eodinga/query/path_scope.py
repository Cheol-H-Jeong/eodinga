from __future__ import annotations


def is_windows_path_text(path_text: str) -> bool:
    return (
        len(path_text) >= 3
        and path_text[1] == ":"
        and path_text[0].isalpha()
        and path_text[2] in {"\\", "/"}
    ) or path_text.startswith(("\\\\", "//"))


def normalize_windows_scope_text(path_text: str) -> str:
    normalized = path_text.rstrip("/\\") or path_text
    if normalized.startswith("\\\\?\\UNC\\"):
        return "\\\\" + normalized[8:]
    if normalized.startswith("//?/UNC/"):
        return "//" + normalized[8:]
    if normalized.startswith("\\\\?\\") or normalized.startswith("//?/"):
        return normalized[4:]
    return normalized


def scope_path_variants(path_text: str) -> tuple[str, ...]:
    normalized = normalize_windows_scope_text(path_text)
    variants: list[str] = []

    def add_variant(value: str) -> None:
        if value and value not in variants:
            variants.append(value)

    add_variant(normalized)
    add_variant(normalized.replace("\\", "/"))
    add_variant(normalized.replace("/", "\\"))

    if len(normalized) >= 2 and normalized[1] == ":" and normalized[0].isalpha():
        for variant in tuple(variants):
            add_variant(normalized[0].upper() + variant[1:])
            add_variant(normalized[0].lower() + variant[1:])

    return tuple(variants)


__all__ = ["is_windows_path_text", "normalize_windows_scope_text", "scope_path_variants"]
