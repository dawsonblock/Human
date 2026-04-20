from __future__ import annotations

from subjective_runtime_v2_1.modules.base import Module
from subjective_runtime_v2_1.state.models import AgentStateV2_1, Candidate, InterpretiveBias
from subjective_runtime_v2_1.util.ids import new_id


class PredictionModule(Module):
    name = "prediction"

    def run(self, state: AgentStateV2_1, inputs: dict, bias: InterpretiveBias) -> list[Candidate]:
        if not state.goal_stack:
            return []
        goal = state.goal_stack[0].get("name", "goal")
        return [Candidate(
            id=new_id("cand"),
            source=self.name,
            kind="prediction",
            content={"goal": goal, "next": "progress"},
            confidence=0.6,
            salience=0.3,
            goal_relevance=0.8,
            uncertainty_reduction=0.15,
            novelty=0.0,
            recency=0.8,
            valuation_alignment=0.05,
            continuity_match=bias.continuity_bias,
            conflict_pressure=0.0,
        )]
