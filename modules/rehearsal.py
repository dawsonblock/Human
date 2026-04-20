from __future__ import annotations

from subjective_runtime_v2_1.modules.base import Module
from subjective_runtime_v2_1.state.models import AgentStateV2_1, Candidate, InterpretiveBias
from subjective_runtime_v2_1.util.ids import new_id


class RehearsalModule(Module):
    name = "rehearsal"

    def run(self, state: AgentStateV2_1, inputs: dict, bias: InterpretiveBias) -> list[Candidate]:
        if not state.pending_options:
            return []
        names = [o.name for o in state.pending_options[:2]]
        return [Candidate(
            id=new_id("cand"),
            source=self.name,
            kind="rehearsal",
            content={"options": names},
            confidence=0.6,
            salience=0.25,
            goal_relevance=0.5,
            uncertainty_reduction=0.2,
            novelty=0.0,
            recency=0.8,
            valuation_alignment=0.0,
            continuity_match=bias.continuity_bias,
            conflict_pressure=0.1,
        )]
