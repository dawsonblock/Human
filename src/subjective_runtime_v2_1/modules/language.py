from __future__ import annotations

from subjective_runtime_v2_1.modules.base import Module
from subjective_runtime_v2_1.state.models import AgentStateV2_1, Candidate, InterpretiveBias
from subjective_runtime_v2_1.util.ids import new_id


class LanguageModule(Module):
    name = "language"

    def run(self, state: AgentStateV2_1, inputs: dict, bias: InterpretiveBias) -> list[Candidate]:
        text = inputs.get("text", "").strip()
        if not text:
            return []
        salience = 0.5 + min(0.3, bias.threat_bias * 0.2 + bias.continuity_bias * 0.2)
        return [Candidate(
            id=new_id("cand"),
            source=self.name,
            kind="language_input",
            content={"text": text},
            confidence=0.95,
            salience=salience,
            goal_relevance=0.7 if state.goal_stack else 0.4,
            uncertainty_reduction=0.2,
            novelty=0.2 + min(0.4, bias.novelty_bias),
            recency=1.0,
            valuation_alignment=min(1.0, bias.threat_bias),
            continuity_match=min(1.0, bias.continuity_bias),
            conflict_pressure=0.2 if state.conflict_field else 0.0,
        )]
