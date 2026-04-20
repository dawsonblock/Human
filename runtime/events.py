from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from typing import Any

from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore


@dataclass(slots=True)
class RuntimeEvent:
    run_id: str
    seq: int
    type: str
    payload: dict[str, Any]
    created_at: float | None = None


class LiveEventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue[RuntimeEvent]]] = {}

    def subscribe_queue(self, run_id: str) -> asyncio.Queue[RuntimeEvent]:
        q: asyncio.Queue[RuntimeEvent] = asyncio.Queue()
        self._subs.setdefault(run_id, []).append(q)
        return q

    def unsubscribe_queue(self, run_id: str, queue: asyncio.Queue[RuntimeEvent]) -> None:
        subs = self._subs.get(run_id, [])
        if queue in subs:
            subs.remove(queue)
        if not subs and run_id in self._subs:
            del self._subs[run_id]

    async def publish_live(self, event: RuntimeEvent) -> None:
        for q in self._subs.get(event.run_id, []):
            await q.put(event)

    @staticmethod
    def encode_sse(event: RuntimeEvent) -> str:
        return (
            f"id: {event.seq}\n"
            f"event: {event.type}\n"
            f"data: {json.dumps(asdict(event), separators=(',', ':'))}\n\n"
        )


class EventManager:
    def __init__(self, store: SQLiteRunStore, live_bus: LiveEventBus | None = None) -> None:
        self.store = store
        self.live_bus = live_bus or LiveEventBus()
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, run_id: str) -> asyncio.Lock:
        if run_id not in self._locks:
            self._locks[run_id] = asyncio.Lock()
        return self._locks[run_id]

    async def publish(self, run_id: str, event_type: str, payload: dict[str, Any]) -> RuntimeEvent:
        """Persist a single event and deliver it to live subscribers.

        Used for lifecycle events (pause, resume, stop, input_enqueued) that
        are not part of a cycle.  Cycle events should go through
        ``SQLiteRunStore.apply_cycle_transition`` + ``fan_out`` instead.
        """
        async with self._lock_for(run_id):
            seq = self.store.get_last_seq(run_id) + 1
            created_at = self.store.append_event(run_id, seq, event_type, payload)
            event = RuntimeEvent(
                run_id=run_id,
                seq=seq,
                type=event_type,
                payload=payload,
                created_at=created_at,
            )
        await self.live_bus.publish_live(event)
        return event

    async def fan_out(self, committed_events: list[dict[str, Any]]) -> None:
        """Push already-persisted events (from apply_cycle_transition) to live subscribers."""
        for item in committed_events:
            event = RuntimeEvent(
                run_id=item['run_id'],
                seq=item['seq'],
                type=item['type'],
                payload=item['payload'],
                created_at=item['created_at'],
            )
            await self.live_bus.publish_live(event)

    async def publish_persisted(self, event: RuntimeEvent) -> None:
        """Deliver one already-persisted event to live subscribers."""
        await self.live_bus.publish_live(event)

    async def publish_persisted_batch(self, events: list[RuntimeEvent]) -> None:
        """Deliver a batch of already-persisted events to live subscribers."""
        for event in events:
            await self.live_bus.publish_live(event)
