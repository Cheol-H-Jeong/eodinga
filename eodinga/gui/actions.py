from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import cast

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication

from eodinga.common import SearchHit
from eodinga.observability import get_logger


class DesktopActions:
    def __init__(self, app: QApplication | None = None) -> None:
        self._app = app or cast(QApplication, QApplication.instance())

    def open_hit(self, hit: SearchHit) -> None:
        self._open_path(hit.path)

    def reveal_hit(self, hit: SearchHit) -> None:
        if sys.platform.startswith("win"):
            if self._spawn(["explorer", f"/select,{hit.path}"]):
                return
        self._open_path(hit.parent_path)

    def show_properties(self, hit: SearchHit) -> None:
        if sys.platform.startswith("win"):
            command = (
                "$item = Get-Item -LiteralPath $args[0]; "
                "$shell = New-Object -ComObject Shell.Application; "
                "$folder = $shell.Namespace($item.DirectoryName); "
                "if ($null -ne $folder) { $folder.ParseName($item.Name).InvokeVerb('Properties') }"
            )
            if self._spawn(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    command,
                    "--",
                    str(hit.path),
                ]
            ):
                return
        self.reveal_hit(hit)

    def copy_hit_path(self, hit: SearchHit) -> None:
        clipboard = self._app.clipboard()
        clipboard.setText(str(hit.path))

    def _open_path(self, path: Path) -> None:
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            get_logger().warning("failed to open local path {}", path)

    def _spawn(self, argv: list[str]) -> bool:
        try:
            subprocess.Popen(
                argv,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            get_logger().warning("failed to launch desktop action {}", argv[0])
            return False
        return True


__all__ = ["DesktopActions"]
