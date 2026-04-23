from __future__ import annotations

import signal

from eodinga.runtime import ShutdownRequested, install_shutdown_handlers


def test_install_shutdown_handlers_wraps_and_restores_signal_handlers() -> None:
    original_sigint = signal.getsignal(signal.SIGINT)
    original_sigterm = signal.getsignal(signal.SIGTERM)

    with install_shutdown_handlers():
        assert signal.getsignal(signal.SIGINT) is not original_sigint
        assert signal.getsignal(signal.SIGTERM) is not original_sigterm

    assert signal.getsignal(signal.SIGINT) is original_sigint
    assert signal.getsignal(signal.SIGTERM) is original_sigterm


def test_shutdown_requested_carries_signal_number() -> None:
    error = ShutdownRequested(signal.SIGTERM)

    assert error.signum == signal.SIGTERM
    assert "signal" in str(error)
