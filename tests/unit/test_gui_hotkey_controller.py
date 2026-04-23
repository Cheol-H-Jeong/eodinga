from __future__ import annotations

from collections.abc import Callable

import pytest

from eodinga.gui.hotkey_controller import LauncherHotkeyController
from eodinga.gui.launcher_window import LauncherWindow


class _ScriptedHotkeyService:
    def __init__(self, fail_attempts: dict[str, set[int]] | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.callback: Callable[[], None] | None = None
        self._fail_attempts = fail_attempts or {}
        self._register_attempts: dict[str, int] = {}

    def register(self, combo: str, callback) -> None:
        self.calls.append(("register", combo))
        self.callback = callback
        attempt = self._register_attempts.get(combo, 0) + 1
        self._register_attempts[combo] = attempt
        if attempt in self._fail_attempts.get(combo, set()):
            raise RuntimeError(f"cannot register {combo}")

    def unregister(self) -> None:
        self.calls.append(("unregister", ""))
        self.callback = None

    def start(self) -> None:
        self.calls.append(("start", ""))

    def stop(self) -> None:
        self.calls.append(("stop", ""))


def test_hotkey_rebind_restores_previous_combo_after_failure(qapp) -> None:
    service = _ScriptedHotkeyService(fail_attempts={"ctrl+alt+k": {1}})
    launcher = LauncherWindow()
    controller = LauncherHotkeyController(launcher, "ctrl+shift+space", hotkey_service=service)

    with pytest.raises(RuntimeError, match="cannot register ctrl\\+alt\\+k"):
        controller.rebind("ctrl+alt+k")

    assert controller.combo == "ctrl+shift+space"
    assert service.calls[-4:] == [
        ("stop", ""),
        ("unregister", ""),
        ("register", "ctrl+shift+space"),
        ("start", ""),
    ]


def test_hotkey_rebind_preserves_original_error_when_rollback_also_fails(qapp) -> None:
    service = _ScriptedHotkeyService(
        fail_attempts={
            "ctrl+alt+k": {1},
            "ctrl+shift+space": {2},
        }
    )
    launcher = LauncherWindow()
    controller = LauncherHotkeyController(launcher, "ctrl+shift+space", hotkey_service=service)

    with pytest.raises(RuntimeError, match="cannot register ctrl\\+alt\\+k") as exc_info:
        controller.rebind("ctrl+alt+k")

    assert controller.combo == "ctrl+shift+space"
    assert exc_info.value.__notes__ == [
        "failed to restore previous launcher hotkey ctrl+shift+space: cannot register ctrl+shift+space"
    ]
