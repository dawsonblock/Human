"""Cycle transition contract.

CycleTransition is the single object that RuntimeCore.cycle() produces.
The supervisor is responsible for persisting it atomically via
SQLiteRunStore.apply_cycle_transition() and then fanning events out to live
subscribers via EventManager.publish_persisted_batch().
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from subjective_runtime_v2_1.state.models import ActionOption, AgentStateV2_1


@dataclass(slots=True)
class RuntimeEventDraft:
    """An uncommitted event produced during a cycle."""
    type: str
    payload: dict[str, Any]


@dataclass(slots=True)
class CycleTransition:
    """Pure output of one cognitive cycle.

    Holds everything the supervisor needs to atomically commit state + events
    and fan out to live subscribers.  RuntimeCore must not persist anything;
    it only fills this object.
    """
    run_id: str
    cycle_id: int
    state: AgentStateV2_1
    events: list[RuntimeEventDraft] = field(default_factory=list)
    chosen_action: ActionOption | None = None
    approval_request: dict[str, Any] | None = None
    status_override: str | None = None
    tool_records: list[dict[str, Any]] = field(default_factory=list)
    cycle_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def new_state(self) -> AgentStateV2_1:
        """Backward-compat alias for ``state``."""
        return self.state
