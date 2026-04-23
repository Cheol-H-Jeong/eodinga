from __future__ import annotations

from typing import NamedTuple

from eodinga.core.watcher import WatchService
from eodinga.index.writer import IndexWriter, RecordLoader


class LiveUpdateDrainResult(NamedTuple):
    drained_events: int
    processed_events: int


def apply_live_updates(
    service: WatchService,
    writer: IndexWriter,
    *,
    record_loader: RecordLoader,
    flush: bool = True,
) -> LiveUpdateDrainResult:
    events = service.drain(flush=flush)
    if not events:
        return LiveUpdateDrainResult(drained_events=0, processed_events=0)
    processed = writer.apply_events(events, record_loader=record_loader)
    return LiveUpdateDrainResult(drained_events=len(events), processed_events=processed)


def shutdown_live_updates(
    service: WatchService,
    writer: IndexWriter,
    *,
    record_loader: RecordLoader,
) -> LiveUpdateDrainResult:
    events = service.stop_and_drain()
    if not events:
        return LiveUpdateDrainResult(drained_events=0, processed_events=0)
    processed = writer.apply_events(events, record_loader=record_loader)
    return LiveUpdateDrainResult(drained_events=len(events), processed_events=processed)


__all__ = ["LiveUpdateDrainResult", "apply_live_updates", "shutdown_live_updates"]
