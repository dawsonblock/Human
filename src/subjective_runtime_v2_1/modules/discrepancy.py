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
        # Compare against the world-model's expected status, not the interpreted
        # percept that was just set from the same input in this cycle — those
        # would always be equal and can never produce a discrepancy.
        expected = state.world_model.get("expected_status")
        if observed and expected and observed != expected:
            return [Candidate(
                id=new_id("cand"),
                source=self.name,
                kind="status_mismatch",
                content={"observed": observed, "expected": expected},
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
