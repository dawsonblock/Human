from __future__ import annotations

from subjective_runtime_v2_1.state.models import AgentStateV2_1


class MemorySystem:
    def retrieve(self, state: AgentStateV2_1) -> dict:
        return {
            "working": state.working_memory[-5:],
            "episodic": state.episodic_trace[-5:],
            "self_history": state.self_history[-5:],
        }

    def write_episode(self, state: AgentStateV2_1, summary: dict) -> None:
        state.episodic_trace.append(summary)
