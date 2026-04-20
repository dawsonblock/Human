from __future__ import annotations

from subjective_runtime_v2_1.modules.base import Module
from subjective_runtime_v2_1.state.models import AgentStateV2_1, Candidate, InterpretiveBias
from subjective_runtime_v2_1.util.ids import new_id


class DiscrepancyModule(Module):
    name = "discrepancy"

    def run(self, state: AgentStateV2_1, inputs: dict, bias: InterpretiveBias) -> list[Candidate]:
        if not state.raw_observations:
            return []
        observed = state.raw_observations[-1].payload.get("observed_status")
        interpreted = state.interpreted_percepts.get("status")
        if observed and interpreted and observed != interpreted:
            return [Candidate(
                id=new_id("cand"),
                source=self.name,
                kind="status_mismatch",
                content={"observed": observed, "interpreted": interpreted},
                confidence=0.9,
                salience=0.7,
                goal_relevance=0.6,
                uncertainty_reduction=0.6,
                novelty=0.1,
                recency=1.0,
                valuation_alignment=bias.threat_bias,
                continuity_match=bias.continuity_bias,
                conflict_pressure=0.6,
            )]
        return []
