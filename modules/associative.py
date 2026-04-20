from __future__ import annotations

from subjective_runtime_v2_1.modules.base import Module
from subjective_runtime_v2_1.state.models import AgentStateV2_1, Candidate, InterpretiveBias
from subjective_runtime_v2_1.util.ids import new_id


class AssociativeModule(Module):
    name = "associative"

    def run(self, state: AgentStateV2_1, inputs: dict, bias: InterpretiveBias) -> list[Candidate]:
        if state.cognitive_mode != "EXPLORE":
            return []
        if len(state.working_memory) < 2:
            return []
        a = state.working_memory[-1]
        b = state.working_memory[-2]
        kind_a = a.get("kind", "memory")
        kind_b = b.get("kind", "memory")
        if kind_a == kind_b:
            return []
        return [Candidate(
            id=new_id("cand"),
            source=self.name,
            kind="associative_bridge",
            content={
                "bridge": f"Link {kind_a} with {kind_b}",
                "from": [kind_a, kind_b],
            },
            confidence=0.55,
            salience=0.45,
            goal_relevance=0.25,
            uncertainty_reduction=0.05,
            novelty=0.7,
            recency=0.7,
            valuation_alignment=0.1,
            continuity_match=0.2,
            conflict_pressure=0.0,
            information_gain=0.35,
        )]
