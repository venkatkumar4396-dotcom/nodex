"""
Event bus — in-process pub/sub for real-time SSE streaming.

Design:
  The event bus uses asyncio.Queue per subscriber. When a workflow run emits
  events (node_started, node_completed, run_finished, etc.), they are published
  to all active subscribers of that run_id. The SSE endpoint subscribes on
  connect and unsubscribes on disconnect.

  Why not Redis Pub/Sub?
  For Phase 4, a single-process event bus is simpler and avoids requiring a
  Redis connection just for local dev. In production, you'd swap this for
  Redis Pub/Sub or use Arq's broadcast — but the API stays the same.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID

import structlog

log = structlog.get_logger(__name__)


class EventType(str, Enum):
    """All event types emitted during workflow execution."""
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_PAUSED = "run_paused"
    RUN_RESUMED = "run_resumed"
    RUN_CANCELLED = "run_cancelled"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    NODE_SKIPPED = "node_skipped"
    FEEDBACK_LOOP = "feedback_loop"
    LOG = "log"


@dataclass
class RunEvent:
    """A single event in the lifecycle of a workflow run."""
    run_id: str
    event_type: EventType
    node_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def to_sse_dict(self) -> dict[str, Any]:
        """Serialize for SSE transmission."""
        return {
            "run_id": self.run_id,
            "event": self.event_type.value,
            "node_id": self.node_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class EventBus:
    """
    In-process event bus with per-run fan-out to async subscribers.

    Usage:
        bus = EventBus()

        # SSE endpoint subscribes
        async for event in bus.subscribe(run_id):
            yield event.to_sse_dict()

        # Worker publishes
        await bus.publish(RunEvent(run_id=..., event_type=...))
    """

    def __init__(self) -> None:
        # run_id → list of subscriber queues
        self._subscribers: dict[str, list[asyncio.Queue[RunEvent | None]]] = defaultdict(list)
        # run_id → list of all emitted events (replayed for late joiners)
        self._history: dict[str, list[RunEvent]] = defaultdict(list)

    async def publish(self, event: RunEvent) -> None:
        """Publish an event to all subscribers and retain in history for late connections."""
        run_id = event.run_id
        self._history[run_id].append(event)
        for queue in self._subscribers.get(run_id, []):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                log.warning("event_queue_full", run_id=run_id)

    async def subscribe(self, run_id: str | UUID):
        """Async generator that yields events for a specific run.

        First replays any buffered events (avoiding race conditions with
        instant starts), then yields live events until terminal event.
        """
        queue: asyncio.Queue[RunEvent | None] = asyncio.Queue(maxsize=1000)
        rid = str(run_id)

        # 1. Replay past buffered events
        past_events = list(self._history.get(rid, []))
        for pe in past_events:
            yield pe
            if pe.event_type in (EventType.RUN_COMPLETED, EventType.RUN_FAILED, EventType.RUN_CANCELLED):
                return

        # 2. Subscribe to live stream
        self._subscribers[rid].append(queue)
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
                if event.event_type in (EventType.RUN_COMPLETED, EventType.RUN_FAILED, EventType.RUN_CANCELLED):
                    break
        finally:
            if rid in self._subscribers and queue in self._subscribers[rid]:
                self._subscribers[rid].remove(queue)
            if not self._subscribers.get(rid):
                self._subscribers.pop(rid, None)

    async def close_run(self, run_id: str | UUID) -> None:
        """Send sentinel None to all subscribers of a run, closing their streams."""
        rid = str(run_id)
        for queue in self._subscribers.get(rid, []):
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass


# Global singleton — shared between the API and the worker
event_bus = EventBus()
