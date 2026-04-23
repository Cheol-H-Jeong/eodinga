from __future__ import annotations

from functools import lru_cache
from importlib.metadata import entry_points
from pathlib import Path
from time import perf_counter

from eodinga.content.base import ParsedContent, ParserSpec, empty_content
from eodinga.content.code import get_parser_spec as get_code_parser_spec
from eodinga.content.epub import get_parser_spec as get_epub_parser_spec
from eodinga.content.html import get_parser_spec as get_html_parser_spec
from eodinga.content.hwp import get_parser_spec as get_hwp_parser_spec
from eodinga.content.office import (
    get_docx_parser_spec,
    get_pptx_parser_spec,
    get_xlsx_parser_spec,
)
from eodinga.content.pdf import get_parser_spec as get_pdf_parser_spec
from eodinga.content.text import get_parser_spec as get_text_parser_spec
from eodinga.core.fs import file_size
from eodinga.observability import increment_counter, logger, record_histogram


def _builtin_specs() -> list[ParserSpec]:
    return [
        get_text_parser_spec(),
        get_code_parser_spec(),
        get_html_parser_spec(),
        get_pdf_parser_spec(),
        get_docx_parser_spec(),
        get_pptx_parser_spec(),
        get_xlsx_parser_spec(),
        get_hwp_parser_spec(),
        get_epub_parser_spec(),
    ]


@lru_cache(maxsize=1)
def load_specs() -> tuple[ParserSpec, ...]:
    specs = list(_builtin_specs())
    for entry_point in entry_points(group="eodinga.parsers"):
        try:
            spec = entry_point.load()()
        except Exception:
            increment_counter("parser_errors")
            increment_counter("parsers.entrypoint_load_error")
            logger.exception("Failed to load parser entry point {}", entry_point.name)
            continue
        if all(existing.name != spec.name for existing in specs):
            specs.append(spec)
    return tuple(specs)


def get_spec_for(path: Path) -> ParserSpec | None:
    suffix = path.suffix.lower().lstrip(".")
    if not suffix:
        return None
    for spec in load_specs():
        if suffix in spec.extensions:
            return spec
    return None


def parse(path: Path, max_body_chars: int) -> ParsedContent:
    spec = get_spec_for(path)
    if spec is None:
        return empty_content(path)
    started = perf_counter()
    try:
        size_bytes = file_size(path)
        if size_bytes > spec.max_bytes:
            increment_counter(f"parsers.{spec.name}.skipped_too_large")
            increment_counter("parser_bytes_skipped_too_large", size_bytes)
            increment_counter(f"parsers.{spec.name}.bytes_skipped_too_large", size_bytes)
            return empty_content(path)
        parsed = spec.parse(path, max_body_chars)
        body_chars = len(parsed.body_text)
        increment_counter(f"parsers.{spec.name}.parsed")
        increment_counter("parser_documents_parsed")
        increment_counter("parser_bytes_parsed", size_bytes)
        increment_counter("parser_body_chars_indexed", body_chars)
        increment_counter(f"parsers.{spec.name}.bytes_parsed", size_bytes)
        increment_counter(f"parsers.{spec.name}.body_chars_indexed", body_chars)
        elapsed_ms = (perf_counter() - started) * 1000
        record_histogram("parser_latency_ms", elapsed_ms, parser=spec.name)
        record_histogram("parser_input_bytes", float(size_bytes), parser=spec.name)
        record_histogram("parser_body_chars", float(body_chars), parser=spec.name)
        return parsed
    except Exception:
        increment_counter("parser_errors")
        increment_counter(f"parsers.{spec.name}.error")
        logger.exception("Failed to parse {}", path)
        return empty_content(path)
