from __future__ import annotations

from subjective_runtime_v2_1.state.models import AgentStateV2_1


class SelfModelUpdater:
    def update(self, state: AgentStateV2_1) -> dict:
        return state.self_model
