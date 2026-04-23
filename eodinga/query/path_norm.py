from __future__ import annotations


def strip_windows_extended_prefix(value: str) -> str:
    if value.startswith("\\\\?\\UNC\\"):
        return f"\\\\{value[8:]}"
    if value.startswith("\\\\?\\"):
        return value[4:]
    return value


def windows_path_variants(value: str) -> tuple[str, ...]:
    canonical = strip_windows_extended_prefix(value.rstrip("/\\") or value)
    ordered_variants = [
        canonical,
        canonical.replace("\\", "/"),
        canonical.replace("/", "\\"),
    ]
    if len(canonical) >= 2 and canonical[1] == ":" and canonical[0].isalpha():
        drive_variants: list[str] = []
        for variant in ordered_variants:
            drive_variants.append(f"{variant[0].lower()}{variant[1:]}")
            drive_variants.append(f"{variant[0].upper()}{variant[1:]}")
        ordered_variants.extend(drive_variants)
    return tuple(dict.fromkeys(ordered_variants))


__all__ = ["strip_windows_extended_prefix", "windows_path_variants"]
