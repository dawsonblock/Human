from __future__ import annotations

from subjective_runtime_v2_1.config import RuntimeConfig
from subjective_runtime_v2_1.state.models import AgentStateV2_1, Candidate


class AttentionGate:
    def __init__(self, config: RuntimeConfig | None = None, max_focus_items: int = 3) -> None:
        self.config = config or RuntimeConfig()
        self.max_focus_items = max_focus_items

    def weights_for_state(self, state: AgentStateV2_1 | None) -> dict[str, float]:
        if state is None:
            return self.config.attention_weights
        weights = dict(self.config.attention_weights_explore if state.cognitive_mode == "EXPLORE" else self.config.attention_weights_exploit)
        overload = state.regulation.get("overload_pressure", 0.0)
        if overload > 0.5:
            weights["novelty"] *= max(0.2, 1.0 - overload)
            weights["conflict_pressure"] *= 1.0 + overload
            weights["salience"] *= 1.0 + overload * 0.5
        weights["novelty"] *= 1.0 + state.risk_appetite * 0.4
        weights["information_gain"] *= 1.0 + state.risk_appetite * 0.3
        return weights

    def score(self, c: Candidate, state: AgentStateV2_1 | None = None) -> float:
        w = self.weights_for_state(state)
        return (
            w["salience"] * c.salience +
            w["goal_relevance"] * c.goal_relevance +
            w["uncertainty_reduction"] * c.uncertainty_reduction +
            w["novelty"] * c.novelty +
            w["recency"] * c.recency +
            w["valuation_alignment"] * c.valuation_alignment +
            w["continuity_match"] * c.continuity_match +
            w["conflict_pressure"] * c.conflict_pressure +
            w["information_gain"] * c.information_gain
        )

    def select(self, items: list[Candidate], state: AgentStateV2_1 | None = None) -> list[Candidate]:
        return sorted(items, key=lambda c: self.score(c, state), reverse=True)[: self.max_focus_items]
