from __future__ import annotations

import re
from pathlib import Path

from charset_normalizer import from_bytes

from eodinga.content.base import ParsedContent, ParserSpec, make_parsed_content
from eodinga.core.fs import read_bytes

TEXT_EXTENSIONS = frozenset(
    {"txt", "md", "log", "csv", "json", "yaml", "yml", "toml", "ini", "cfg", "rtf"}
)
_RTF_CONTROL_RE = re.compile(r"\\[a-zA-Z]+-?\d* ?|[{}]")


def _decode_bytes(data: bytes) -> str:
    if not data:
        return ""
    match = from_bytes(data).best()
    if match is not None:
        return str(match)
    return data.decode("utf-8", errors="ignore")


def _extract_title(text: str, path: Path) -> str:
    for line in text.splitlines():
        candidate = line.strip()
        if candidate:
            return candidate[:200]
    return path.stem


def _normalize_rtf(text: str) -> str:
    without_controls = _RTF_CONTROL_RE.sub(" ", text)
    return re.sub(r"\s+", " ", without_controls).strip()


def parse_text(path: Path, max_body_chars: int) -> ParsedContent:
    raw = read_bytes(path)
    decoded = _decode_bytes(raw)
    normalized = _normalize_rtf(decoded) if path.suffix.lower() == ".rtf" else decoded
    title = _extract_title(normalized, path)
    head_text = "\n".join(normalized.splitlines()[:5]).strip()
    return make_parsed_content(
        title=title,
        head_text=head_text,
        body_text=normalized,
        max_body_chars=max_body_chars,
    )


def get_parser_spec() -> ParserSpec:
    return ParserSpec(name="text", extensions=TEXT_EXTENSIONS, parse=parse_text)
