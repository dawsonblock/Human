from __future__ import annotations

from subjective_runtime_v2_1.state.models import AgentStateV2_1

_MEMORY_KIND_ROUTES = {
    "working_note": "working_memory",
    "episodic": "episodic_trace",
    "episode": "episodic_trace",
    "self_history": "self_history",
    "goal_note": "working_memory",
}


class MemorySystem:
    def retrieve(self, state: AgentStateV2_1) -> dict:
        return {
            "working": state.working_memory[-5:],
            "episodic": state.episodic_trace[-5:],
            "self_history": state.self_history[-5:],
        }

    def write_episode(self, state: AgentStateV2_1, summary: dict) -> None:
        state.episodic_trace.append(summary)

    def apply_memory_write(self, state: AgentStateV2_1, entry: dict) -> None:
        """Route a declarative memory write entry into the correct state field."""
        kind = entry.get("kind", "")
        target = _MEMORY_KIND_ROUTES.get(kind)
        if target == "working_memory":
            state.working_memory.append(entry)
        elif target == "episodic_trace":
            state.episodic_trace.append(entry)
        elif target == "self_history":
            state.self_history.append(entry)
        # Unknown kinds are silently ignored here; MemoryWriteTool validates earlier.

    def promote_working_item(
        self,
        state: AgentStateV2_1,
        item: dict,
        max_items: int = 12,
    ) -> None:
        """Append one item to working_memory and trim to cap."""
        state.working_memory.append(item)
        if len(state.working_memory) > max_items:
            state.working_memory = state.working_memory[-max_items:]

    def recent_memory_packet(self, state: AgentStateV2_1) -> dict:
        """Return a compact snapshot of the most recent memory items."""
        return {
            "working": state.working_memory[-3:],
            "episodic": state.episodic_trace[-3:],
            "self_history": state.self_history[-2:],
        }
