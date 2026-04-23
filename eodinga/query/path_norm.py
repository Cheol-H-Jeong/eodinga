from __future__ import annotations


def strip_windows_extended_prefix(value: str) -> str:
    if value.startswith("\\\\?\\UNC\\"):
        return f"\\\\{value[8:]}"
    if value.startswith("\\\\?\\"):
        return value[4:]
    return value


def windows_path_variants(value: str) -> tuple[str, ...]:
    canonical = strip_windows_extended_prefix(value.rstrip("/\\") or value)
    variants = {
        canonical,
        canonical.replace("\\", "/"),
        canonical.replace("/", "\\"),
    }
    if len(canonical) >= 2 and canonical[1] == ":" and canonical[0].isalpha():
        drive_variants = set()
        for variant in variants:
            drive_variants.add(f"{variant[0].lower()}{variant[1:]}")
            drive_variants.add(f"{variant[0].upper()}{variant[1:]}")
        variants |= drive_variants
    return tuple(dict.fromkeys(variants))


__all__ = ["strip_windows_extended_prefix", "windows_path_variants"]
