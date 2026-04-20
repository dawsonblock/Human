from __future__ import annotations

from subjective_runtime_v2_1.config import RuntimeConfig
from subjective_runtime_v2_1.state.models import AgentStateV2_1


class CognitiveModeEngine:
    def __init__(self, config: RuntimeConfig | None = None) -> None:
        self.config = config or RuntimeConfig()

    def update(self, state: AgentStateV2_1) -> AgentStateV2_1:
        r = state.regulation
        m = self.config.mode_switch
        if r["overload_pressure"] > m["exploit_overload"] or r["error_accumulation"] > m["exploit_error"]:
            state.cognitive_mode = "EXPLOIT"
        elif r["continuity_health"] > m["explore_min_continuity"] and r["unresolved_loop_burden"] < m["explore_max_burden"]:
            state.cognitive_mode = "EXPLORE"
        else:
            state.cognitive_mode = "EXPLOIT"

        budget = self.config.thought_budget["base"]
        if r["error_accumulation"] > 0.5:
            budget = self.config.thought_budget["high_error"]
        elif r["uncertainty_load"] > 0.5:
            budget = self.config.thought_budget["high_uncertainty"]
        state.thought_budget = min(self.config.thought_budget["max"], budget)
        return state
