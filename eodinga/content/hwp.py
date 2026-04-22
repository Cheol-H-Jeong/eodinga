from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import olefile

from eodinga.content.base import ParsedContent, ParserSpec, make_parsed_content


def parse_hwp(path: Path, max_body_chars: int) -> ParsedContent:
    title = path.stem
    if not olefile.isOleFile(str(path)):
        return make_parsed_content(
            title=title,
            head_text="",
            body_text="",
            max_body_chars=max_body_chars,
        )
    command = shutil.which("hwp5txt")
    if command is None:
        return make_parsed_content(
            title=title,
            head_text="",
            body_text="",
            max_body_chars=max_body_chars,
        )
    completed = subprocess.run(
        [command, str(path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    body_text = completed.stdout.strip() if completed.returncode == 0 else ""
    head_text = "\n".join(body_text.splitlines()[:5]).strip()
    return make_parsed_content(
        title=title,
        head_text=head_text,
        body_text=body_text,
        max_body_chars=max_body_chars,
    )


def get_parser_spec() -> ParserSpec:
    return ParserSpec(name="hwp", extensions=frozenset({"hwp"}), parse=parse_hwp)
