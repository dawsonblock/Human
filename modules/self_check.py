from __future__ import annotations

from subjective_runtime_v2_1.modules.base import Module
from subjective_runtime_v2_1.state.models import AgentStateV2_1, Candidate, InterpretiveBias
from subjective_runtime_v2_1.util.ids import new_id


class SelfCheckModule(Module):
    name = "self_check"

    def run(self, state: AgentStateV2_1, inputs: dict, bias: InterpretiveBias) -> list[Candidate]:
        if state.regulation.get("overload_pressure", 0.0) < 0.4:
            return []
        return [Candidate(
            id=new_id("cand"),
            source=self.name,
            kind="overload_warning",
            content={"overload_pressure": state.regulation["overload_pressure"]},
            confidence=1.0,
            salience=state.regulation["overload_pressure"],
            goal_relevance=0.7,
            uncertainty_reduction=0.0,
            novelty=0.0,
            recency=1.0,
            valuation_alignment=bias.threat_bias,
            continuity_match=bias.continuity_bias,
            conflict_pressure=0.0,
        )]
