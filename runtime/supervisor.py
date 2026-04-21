from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Any, Callable

from subjective_runtime_v2_1.runtime.core import RuntimeCore
from subjective_runtime_v2_1.runtime.events import EventManager, RuntimeEvent
from subjective_runtime_v2_1.runtime.transition import CycleTransition, RuntimeEventDraft
from subjective_runtime_v2_1.state.sqlite_store import SQLiteRunStore
from subjective_runtime_v2_1.util.time import now_ts


@dataclass(slots=True)
class RunConfig:
    tick_interval_sec: float = 0.2
    idle_enabled: bool = True
    auto_sleep_when_stable: bool = True
    stability_threshold: float = 0.92


class RunSupervisor:
    def __init__(
        self,
        run_id: str,
        runtime: RuntimeCore,
        events: EventManager,
        config: RunConfig,
        run_store: SQLiteRunStore,
    ) -> None:
        self.run_id = run_id
        self.runtime = runtime
        self.events = events
        self.config = config
        self.run_store = run_store
        self._input_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._paused = False
        self._stopped = False
        self._cycle_lock = asyncio.Lock()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done() and not self._paused and not self._stopped

    @property
    def is_paused(self) -> bool:
        return self._paused and not self._stopped

    async def start(self, initial_inputs: dict[str, Any] | None = None) -> None:
        if initial_inputs:
            await self._input_queue.put(initial_inputs)
        self._stopped = False
        self._paused = False
        state = self.run_store.load_state(self.run_id)
        if state is not None:
            self.run_store.save_state(self.run_id, state, status='running')
            # Seed the runtime's internal InMemoryStateStore with the persisted
            # state so the first cycle reads the correct prior state rather than
            # starting from a blank AgentStateV2_1.
            self.runtime.state_store.save(self.run_id, state)
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop())
        await self.events.publish(self.run_id, 'run_supervisor_started', {'config': asdict(self.config)})

    async def stop(self) -> None:
        self._stopped = True
        self._paused = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        state = self.run_store.load_state(self.run_id)
        if state is not None:
            self.run_store.save_state(self.run_id, state, status='stopped')
        await self.events.publish(self.run_id, 'run_supervisor_stopped', {})

    async def pause(self) -> None:
        self._paused = True
        state = self.run_store.load_state(self.run_id)
        if state is not None:
            self.run_store.save_state(self.run_id, state, status='paused')
        await self.events.publish(self.run_id, 'run_paused', {})

    async def resume(self) -> None:
        self._paused = False
        state = self.run_store.load_state(self.run_id)
        if state is not None:
            self.run_store.save_state(self.run_id, state, status='running')
        await self.events.publish(self.run_id, 'run_resumed', {})

    async def inject_input(self, inputs: dict[str, Any]) -> None:
        await self._input_queue.put(inputs)
        await self.events.publish(self.run_id, 'input_enqueued', {'inputs': inputs})

    async def _mutate_state(
        self,
        fn: Callable,
    ) -> list[dict[str, Any]]:
        """Acquire _cycle_lock, load state, apply mutation, commit atomically.

        ``fn(state) -> list[RuntimeEventDraft]`` mutates state in-place and
        returns the event drafts to persist.  Returning an empty list is the
        signal that nothing matched; in that case no DB write is performed and
        an empty list is returned to the caller.

        Returns the committed event rows (with seq and created_at filled in).
        """
        async with self._cycle_lock:
            state = self.run_store.load_state(self.run_id)
            if state is None:
                return []
            event_drafts = fn(state)
            if not event_drafts:
                return []
            # Sync the runtime's in-memory buffer so the next cycle picks up
            # the mutated state rather than an outdated snapshot.
            self.runtime.state_store.save(self.run_id, state)
            transition = CycleTransition(
                run_id=self.run_id,
                cycle_id=state.cycle_id,
                state=state,
                events=event_drafts,
            )
            return self.run_store.apply_cycle_transition(transition)

    async def approve_action(self, action_id: str) -> bool:
        """Mark the pending approval request as approved and re-queue for execution."""
        decided_at = now_ts()

        def _approve(state):
            for req in state.approval_requests:
                if req.get("action_id") == action_id and req.get("status") == "pending":
                    req["status"] = "approved"
                    req["decided_at"] = decided_at
                    return [RuntimeEventDraft(
                        type="approval_granted",
                        payload={"action_id": action_id, "decided_at": decided_at},
                    )]
            return []

        committed = await self._mutate_state(_approve)
        if not committed:
            return False
        await self.events.publish_persisted_batch([
            RuntimeEvent(
                run_id=row["run_id"],
                seq=row["seq"],
                type=row["type"],
                payload=row["payload"],
                created_at=row["created_at"],
            )
            for row in committed
        ])
        await self._input_queue.put({"_approval_granted": action_id})
        return True

    async def deny_action(self, action_id: str) -> bool:
        """Mark the pending approval request as denied."""
        decided_at = now_ts()

        def _deny(state):
            for req in state.approval_requests:
                if req.get("action_id") == action_id and req.get("status") == "pending":
                    req["status"] = "denied"
                    req["decided_at"] = decided_at
                    return [RuntimeEventDraft(
                        type="approval_denied",
                        payload={"action_id": action_id, "decided_at": decided_at},
                    )]
            return []

        committed = await self._mutate_state(_deny)
        if not committed:
            return False
        await self.events.publish_persisted_batch([
            RuntimeEvent(
                run_id=row["run_id"],
                seq=row["seq"],
                type=row["type"],
                payload=row["payload"],
                created_at=row["created_at"],
            )
            for row in committed
        ])
        return True

    async def _run_loop(self) -> None:
        while not self._stopped:
            if self._paused:
                await asyncio.sleep(self.config.tick_interval_sec)
                continue

            pending_inputs = await self._drain_inputs()
            if not pending_inputs and not self.config.idle_enabled:
                await asyncio.sleep(self.config.tick_interval_sec)
                continue

            merged_inputs = self._merge_inputs(pending_inputs)
            idle_tick = len(pending_inputs) == 0

            async with self._cycle_lock:
                transition = self.runtime.cycle(self.run_id, merged_inputs, idle_tick=idle_tick)
                # Atomically commit state + all cycle events to SQLite inside
                # the same lock so no approve/deny can interleave between
                # compute and commit.
                committed = self.run_store.apply_cycle_transition(transition)

            # Fan-out to SSE subscribers can happen outside the lock — these
            # rows are already durably committed.
            await self.events.publish_persisted_batch([
                RuntimeEvent(
                    run_id=row['run_id'],
                    seq=row['seq'],
                    type=row['type'],
                    payload=row['payload'],
                    created_at=row['created_at'],
                )
                for row in committed
            ])

            await asyncio.sleep(self._compute_sleep_interval(transition.state, idle_tick))

    async def _drain_inputs(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        while len(items) < 64:
            try:
                items.append(self._input_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return items

    def _merge_inputs(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for item in items:
            merged.update(item)
        return merged

    def _compute_sleep_interval(self, state, idle_tick: bool) -> float:
        if not self.config.auto_sleep_when_stable:
            return self.config.tick_interval_sec
        continuity = state.regulation.get('continuity_health', 0.0)
        uncertainty = state.regulation.get('uncertainty_load', 0.0)
        has_tensions = len(state.tensions) > 0
        if idle_tick and not has_tensions and continuity >= self.config.stability_threshold and uncertainty < 0.2:
            return min(self.config.tick_interval_sec * 4.0, 1.0)
        return self.config.tick_interval_sec
