from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import blake2b
from pathlib import Path


@dataclass(frozen=True)
class ParsedContent:
    title: str
    head_text: str
    body_text: str
    content_sha: bytes


@dataclass(frozen=True)
class ParserSpec:
    name: str
    extensions: frozenset[str]
    parse: Callable[[Path, int], ParsedContent]
    max_bytes: int = 50 * 1024 * 1024


def truncate_body(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    return text[:max_chars]


def make_parsed_content(
    title: str,
    head_text: str,
    body_text: str,
    max_body_chars: int,
) -> ParsedContent:
    truncated_body = truncate_body(body_text, max_body_chars)
    return ParsedContent(
        title=title,
        head_text=head_text.strip(),
        body_text=truncated_body,
        content_sha=blake2b(truncated_body.encode("utf-8"), digest_size=16).digest(),
    )


def empty_content(path: Path) -> ParsedContent:
    return ParsedContent(title=path.stem, head_text="", body_text="", content_sha=b"")
