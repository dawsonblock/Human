"""Storage interface Protocol.

All storage backends must satisfy this Protocol.  ``SQLiteBackend`` is the
default implementation.  The Protocol is structural so existing classes that
already implement the required methods are compatible without inheritance.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from subjective_runtime_v2_1.state.models import AgentStateV2_1
from subjective_runtime_v2_1.state.sqlite_store import RunMetadata
from subjective_runtime_v2_1.runtime.transition import CycleTransition


@runtime_checkable
class RunStore(Protocol):
    """Minimal storage contract for the Human Runtime."""

    # ── Run lifecycle ────────────────────────────────────────────────

    def create_run(
        self,
        run_id: str,
        config: dict[str, Any],
        state: AgentStateV2_1 | None = None,
        status: str = "running",
    ) -> None: ...

    def has_run(self, run_id: str) -> bool: ...

    def get_run(self, run_id: str) -> RunMetadata | None: ...

    def list_runs(self) -> list[RunMetadata]: ...

    def list_recoverable_runs(self) -> list[RunMetadata]: ...

    # ── State ────────────────────────────────────────────────────────

    def load_state(self, run_id: str) -> AgentStateV2_1 | None: ...

    def save_state(
        self,
        run_id: str,
        state: AgentStateV2_1,
        status: str | None = None,
    ) -> None: ...

    def transition_run_status_with_event(
        self,
        run_id: str,
        status: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]: ...

    # ── Atomic cycle commit ─────────────────────────────────────────

    def apply_cycle_transition(
        self,
        transition: CycleTransition,
    ) -> list[dict[str, Any]]: ...

    # ── Atomic lifecycle event (fixes sequencing race) ───────────────

    def append_lifecycle_event(
        self,
        run_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]: ...

    # ── Event log ───────────────────────────────────────────────────

    def load_events(
        self,
        run_id: str,
        after_seq: int = 0,
        limit: int = 500,
    ) -> list[dict[str, Any]]: ...

    def get_last_seq(self, run_id: str) -> int: ...

    # ── Artifacts ───────────────────────────────────────────────────

    def list_artifacts(self, run_id: str) -> list[dict[str, Any]]: ...

    # ── Export ──────────────────────────────────────────────────────

    def export_run_bundle(self, run_id: str) -> dict[str, Any]: ...

    # ── Storage metadata ─────────────────────────────────────────────

    def get_storage_stats(self) -> dict[str, Any]: ...

    def close(self) -> None: ...
