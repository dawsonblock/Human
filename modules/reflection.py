from __future__ import annotations

from subjective_runtime_v2_1.modules.base import Module
from subjective_runtime_v2_1.state.models import AgentStateV2_1, Candidate, InterpretiveBias
from subjective_runtime_v2_1.util.ids import new_id


class ReflectionModule(Module):
    name = "reflection"

    def run(self, state: AgentStateV2_1, inputs: dict, bias: InterpretiveBias) -> list[Candidate]:
        if state.cycle_id % 3 != 0:
            return []
        return [Candidate(
            id=new_id("cand"),
            source=self.name,
            kind="reflection",
            content={"summary": state.pre_narrative.current_scene},
            confidence=0.8,
            salience=0.35,
            goal_relevance=0.4,
            uncertainty_reduction=0.1,
            novelty=0.0,
            recency=0.8,
            valuation_alignment=0.1,
            continuity_match=bias.continuity_bias,
            conflict_pressure=0.0,
        )]
