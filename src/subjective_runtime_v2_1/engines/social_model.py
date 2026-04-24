from __future__ import annotations

from subjective_runtime_v2_1.state.models import AgentStateV2_1


class SocialModelEngine:
    def update(self, state: AgentStateV2_1) -> dict[str, dict]:
        return state.social_model
