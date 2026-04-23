from __future__ import annotations


def root_variants(root_text: str) -> tuple[str, ...]:
    normalized = _strip_windows_extended_prefix(root_text)
    candidates = dict.fromkeys(
        candidate
        for candidate in (
            root_text,
            normalized,
            normalized.replace("\\", "/"),
            normalized.replace("/", "\\"),
        )
        if candidate
    )
    variants: dict[str, None] = {}
    for candidate in candidates:
        variants[candidate] = None
        if len(candidate) >= 2 and candidate[1] == ":" and candidate[0].isalpha():
            variants[f"{candidate[0].lower()}{candidate[1:]}"] = None
            variants[f"{candidate[0].upper()}{candidate[1:]}"] = None
    return tuple(variants)


def _strip_windows_extended_prefix(root_text: str) -> str:
    if root_text.startswith("\\\\?\\UNC\\"):
        return f"\\\\{root_text[8:]}"
    if root_text.startswith("//?/UNC/"):
        return f"//{root_text[8:]}"
    if root_text.startswith("\\\\?\\") or root_text.startswith("//?/"):
        return root_text[4:]
    return root_text
