from __future__ import annotations

import ast
from pathlib import Path

from eodinga.content.base import ParsedContent, ParserSpec, make_parsed_content
from eodinga.content.text import _decode_bytes
from eodinga.core.fs import read_bytes

CODE_EXTENSIONS = frozenset(
    {
        "py",
        "js",
        "ts",
        "tsx",
        "jsx",
        "go",
        "rs",
        "java",
        "kt",
        "swift",
        "c",
        "cc",
        "cpp",
        "h",
        "hpp",
        "cs",
        "rb",
        "php",
        "scala",
        "sh",
        "bash",
        "zsh",
        "sql",
        "lua",
        "r",
    }
)
COMMENT_PREFIXES = ("#", "//", "/*", "*", "--", ";", "%", "'")


def _python_docstring(source: str) -> str:
    module = ast.parse(source)
    return ast.get_docstring(module, clean=True) or ""


def _leading_comment_block(source: str) -> str:
    comments: list[str] = []
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped and not comments:
            continue
        if stripped.startswith(COMMENT_PREFIXES):
            comment = stripped.lstrip("#/*-;%' ").rstrip("*/ ").strip()
            if comment:
                comments.append(comment)
            continue
        break
    return "\n".join(comments)


def parse_code(path: Path, max_body_chars: int) -> ParsedContent:
    source = _decode_bytes(read_bytes(path))
    head_text = (
        _python_docstring(source)
        if path.suffix.lower() == ".py"
        else _leading_comment_block(source)
    )
    title = head_text.splitlines()[0][:200] if head_text else path.stem
    return make_parsed_content(
        title=title,
        head_text=head_text,
        body_text=source,
        max_body_chars=max_body_chars,
    )


def get_parser_spec() -> ParserSpec:
    return ParserSpec(name="code", extensions=CODE_EXTENSIONS, parse=parse_code)
